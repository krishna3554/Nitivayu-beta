"""Admin compliance exports + service health (WP-6).

Four on-demand exports behind POST /admin/exports/{kind}, all returning
{path, download_url?, count} — the same S3-mirror + presigned-URL pattern as
the triage CSV. A contained download endpoint serves files when object
storage is disabled (dev). GET /admin/health/services replaces the
dashboard's hardcoded "Live" badges with real dependency checks.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_role
from app.config import get_settings
from app.db.models import AuditLog, FundingLink, Problem, RouteAssignment, Submission
from app.services import storage as storage_svc
from app.services.outputs import (
    find_export_file,
    mirror_export,
    write_audit_jsonl,
    write_csr_matrix,
    write_routing_pdf,
    write_sla_log,
)

router = APIRouter(prefix="/admin", tags=["admin-exports"])

EXPORT_KINDS = ("sla-log", "routing-pdf", "audit-jsonl", "csr-matrix")


def _export_response(path: str, count: int | None = None) -> dict:
    """Mirror to object storage with a signed URL when enabled; otherwise a
    same-origin download URL served by GET /admin/exports/download/{file}."""
    body = mirror_export(path, f"/api/v1/admin/exports/download/{Path(path).name}")
    if count is not None:
        body["count"] = count
    return body


@router.post("/exports/{kind}")
async def run_export(kind: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))):
    if kind not in EXPORT_KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown export kind. Choose one of: {', '.join(EXPORT_KINDS)}")
    if kind == "sla-log":
        rows = (await db.execute(
            select(AuditLog).where(
                AuditLog.action.like("%SLA%") | AuditLog.action.like("%ESCALAT%")
                | AuditLog.action.like("OFFICER_%") | AuditLog.action.like("UNIVERSITY_%")
            ).order_by(AuditLog.timestamp.desc()).limit(5000)
        )).scalars().all()
        export_rows = [
            {
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                "entity_type": r.entity_type, "entity_id": r.entity_id,
                "action": r.action, "actor_role": r.actor_role,
                "detail": str(r.after_snapshot or ""),
            }
            for r in rows
        ]
        return _export_response(write_sla_log(export_rows, "sla_escalation_log"), len(export_rows))
    if kind == "audit-jsonl":
        rows = (await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10000))).scalars().all()
        export_rows = [
            {
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                "entity_type": r.entity_type, "entity_id": r.entity_id,
                "action": r.action, "actor_id": r.actor_id, "actor_role": r.actor_role,
                "before": r.before_snapshot, "after": r.after_snapshot,
                "request_id": r.request_id,
            }
            for r in rows
        ]
        return _export_response(write_audit_jsonl(export_rows, "audit_export"), len(export_rows))
    if kind == "routing-pdf":
        problems = (await db.execute(select(Problem).order_by(Problem.created_at.desc()).limit(200))).scalars().all()
        by_category: dict[str, int] = {}
        for problem in problems:
            by_category[problem.category or "Unknown"] = by_category.get(problem.category or "Unknown", 0) + 1
        assignments = (await db.execute(
            select(RouteAssignment).options(selectinload(RouteAssignment.university))
            .order_by(RouteAssignment.assigned_at.desc()).limit(200)
        )).scalars().all()
        by_uni: dict[str, int] = {}
        for assignment in assignments:
            name = assignment.university.name if assignment.university else "Unassigned"
            by_uni[name] = by_uni.get(name, 0) + 1
        from datetime import datetime, timezone

        lines = [
            "University routing report — on-demand admin export",
            f"Generated (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            f"Problems in window: {len(problems)}",
            "", "By category:",
            *[f"  - {category}: {count}" for category, count in sorted(by_category.items(), key=lambda kv: -kv[1])[:10]],
            "", "Routing leaderboard:",
            *[f"  - {name}: {count}" for name, count in sorted(by_uni.items(), key=lambda kv: -kv[1])[:10]],
        ]
        return _export_response(
            write_routing_pdf(lines, "Nitivayu routing report", "Nitivayu_routing_admin"), len(problems)
        )
    # csr-matrix
    from app.activities.report_gen import collect_csr_matrix_rows

    matrix = await collect_csr_matrix_rows(db)
    return _export_response(write_csr_matrix(matrix, "Nitivayu_csr_matrix"), len(matrix))


@router.get("/exports/download/{filename}")
async def download_export(filename: str, user: dict = Depends(require_role("admin"))):
    """Stream a generated export file (dev path when S3 is disabled)."""
    found = find_export_file(filename)
    if found is None:
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(found, filename=found.name)


@router.get("/health/services")
async def service_health(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))):
    """Live dependency checks for the telemetry dashboard (replaces the
    hardcoded green 'Live' badges). Each entry: {name, status, detail}."""
    services: list[dict] = []

    async def _check(name: str, coro) -> None:
        try:
            detail = await coro()
            ok = detail is not False and detail is not None
            services.append({"name": name, "status": "up" if ok else "degraded", "detail": detail if isinstance(detail, str) else ""})
        except Exception as exc:
            services.append({"name": name, "status": "down", "detail": str(exc)[:200]})

    async def _db():
        from sqlalchemy import text

        from app.db.session import get_engine

        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        return "SELECT 1 ok"

    async def _redis():
        from app.services import redis_client as redis_mod

        return "ping ok" if await redis_mod.ping() else False

    async def _temporal():
        from temporalio.client import Client

        settings = get_settings()
        client = await Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE)
        await client.get_workflow_service_client().describe_namespace(settings.TEMPORAL_NAMESPACE)
        return f"{settings.TEMPORAL_HOST} reachable"

    async def _storage():
        settings = get_settings()
        if not storage_svc.enabled():
            media_dir = Path(settings.MEDIA_DIR)
            media_dir.mkdir(parents=True, exist_ok=True)
            probe = media_dir / ".health"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            return "local mirror writable"
        return "bucket ok" if await storage_svc.ping() else False

    async def _llm():
        settings = get_settings()
        if not settings.OPENROUTER_API_KEY:
            return "no key — local fallback active"
        return f"key configured · model {settings.OPENROUTER_MODEL}"

    await _check("FastAPI Backend", lambda: _db())
    await _check("PostgreSQL + pgvector", lambda: _db())
    await _check("Redis", lambda: _redis())
    await _check("Temporal Workflows", lambda: _temporal())
    await _check("Object Storage", lambda: _storage())
    await _check("LLM Extraction", lambda: _llm())

    try:
        total = (await db.execute(select(func.coalesce(func.sum(FundingLink.pledged_amount_inr), 0)))).scalar_one()
        subs = (await db.execute(select(func.count(Submission.submission_id)))).scalar_one()
        services.append({"name": "Pipeline Stats", "status": "up", "detail": f"{subs} submissions · ₹{float(total or 0):,.0f} pledged"})
    except Exception:
        services.append({"name": "Pipeline Stats", "status": "degraded", "detail": "stats query failed"})
    return {"services": services}
