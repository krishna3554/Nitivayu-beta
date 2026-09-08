"""Batch report writers: triage CSV snapshot + weekly routing PDF (worker side)."""

import csv
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from temporalio import activity

from app.db.models import BatchRun, Problem, RouteAssignment, Submission
from app.db.worker_session import worker_session
from app.services.triage_state import audit_once

logger = logging.getLogger(__name__)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


@activity.defn
async def generate_triage_csv_report_activity(data: dict) -> dict:
    """Full batch snapshot CSV (spec-aligned Nitivayu_batch_* filename)."""
    from app.config import get_settings
    from pathlib import Path

    payload = data or {}
    batch_id = payload.get("batch_id", "")
    ids = list(payload.get("submission_ids") or [])
    root = Path(get_settings().OUTPUT_ROOT) / "triage"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"Nitivayu_batch_{batch_id}_{_stamp()}.csv" if batch_id else root / f"Nitivayu_batch_{_stamp()}.csv"
    headers = [
        "tracking_token", "title", "category", "severity", "district", "reporter_name",
        "uni_match_1", "score_1", "uni_match_2", "score_2", "uni_match_3", "score_3",
        "triage_status",
    ]
    count = 0
    async with worker_session() as session:
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            for submission_id in ids:
                submission = await session.get(Submission, submission_id)
                if submission is None:
                    continue
                problem = (
                    await session.execute(select(Problem).where(Problem.submission_id == submission.submission_id))
                ).scalars().first()
                matches = []
                if problem is not None:
                    rows = (
                        await session.execute(
                            select(RouteAssignment)
                            .options(selectinload(RouteAssignment.university))
                            .where(RouteAssignment.problem_id == problem.problem_id)
                            .order_by(RouteAssignment.rank_order)
                            .limit(3)
                        )
                    ).scalars().all()
                    matches = [(r.university.name if r.university else "", r.match_score) for r in rows]
                while len(matches) < 3:
                    matches.append(("", ""))
                writer.writerow({
                    "tracking_token": submission.tracking_token or "",
                    "title": (problem.title if problem else submission.raw_text[:120]) or "",
                    "category": problem.category if problem else "",
                    "severity": problem.severity_score if problem else "",
                    "district": submission.geo_district or "",
                    "reporter_name": submission.reporter_name or "",
                    "uni_match_1": matches[0][0], "score_1": matches[0][1],
                    "uni_match_2": matches[1][0], "score_2": matches[1][1],
                    "uni_match_3": matches[2][0], "score_3": matches[2][1],
                    "triage_status": problem.status if problem else submission.status,
                })
                count += 1
        if batch_id:
            run = await session.get(BatchRun, batch_id)
            if run is not None:
                run.csv_path = str(path)
            await audit_once(
                session, entity_type="batch", entity_id=batch_id,
                action="BATCH_CSV_WRITTEN", actor_role="worker", after={"path": str(path), "rows": count},
            )
            await session.commit()
    logger.info("Batch %s CSV: %s (%d rows)", batch_id, path, count)
    return {"batch_id": batch_id, "path": str(path), "count": count}


@activity.defn
async def generate_weekly_routing_pdf_report_activity(data: dict) -> dict:
    """Department briefing PDF: summary, leaderboard, per-item routing."""
    from app.services import outputs as outputs_svc

    payload = data or {}
    batch_id = payload.get("batch_id", "")
    lines: list[str] = []
    total = routed = 0
    by_category: dict[str, int] = {}
    by_uni: dict[str, int] = {}
    async with worker_session() as session:
        if batch_id:
            run = await session.get(BatchRun, batch_id)
            total = (run.total or 0) if run else 0
            routed = (run.processed or 0) if run else 0
        problems = (await session.execute(select(Problem).order_by(Problem.created_at.desc()).limit(200))).scalars().all()
        for problem in problems:
            by_category[problem.category or "Unknown"] = by_category.get(problem.category or "Unknown", 0) + 1
        assignments = (
            await session.execute(
                select(RouteAssignment).options(selectinload(RouteAssignment.university)).order_by(RouteAssignment.assigned_at.desc()).limit(200)
            )
        ).scalars().all()
        for assignment in assignments:
            name = assignment.university.name if assignment.university else "Unassigned"
            by_uni[name] = by_uni.get(name, 0) + 1
    lines.append(f"Weekly routing report — batch {batch_id or 'adhoc'}")
    lines.append(f"Generated (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(f"Window submissions: {total} · routed in batch: {routed}")
    lines.append("")
    lines.append("By category:")
    for category, count in sorted(by_category.items(), key=lambda kv: -kv[1])[:10]:
        lines.append(f"  - {category}: {count}")
    lines.append("")
    lines.append("Recent routing leaderboard:")
    for name, count in sorted(by_uni.items(), key=lambda kv: -kv[1])[:10]:
        lines.append(f"  - {name}: {count}")
    path = outputs_svc.write_routing_pdf(
        lines, f"Nitivayu weekly routing — {batch_id}", f"Nitivayu_routing_{batch_id}" if batch_id else ""
    )
    async with worker_session() as session:
        if batch_id:
            run = await session.get(BatchRun, batch_id)
            if run is not None:
                run.pdf_path = str(path)
            await audit_once(
                session, entity_type="batch", entity_id=batch_id,
                action="BATCH_PDF_WRITTEN", actor_role="worker", after={"path": str(path)},
            )
            await session.commit()
    logger.info("Batch %s PDF: %s", batch_id, path)
    return {"batch_id": batch_id, "path": str(path)}


async def collect_csr_matrix_rows(session, industry_id=None) -> list[list]:
    """Plain CSR-matrix rows shared by the monthly activity and exports."""
    from app.db.models import FundingLink, Industry

    query = (
        select(Problem, Industry.name, FundingLink.pledged_amount_inr, FundingLink.status)
        .join(FundingLink, FundingLink.problem_id == Problem.problem_id)
        .join(Industry, FundingLink.industry_id == Industry.industry_id, isouter=True)
        .order_by(FundingLink.created_at.desc())
        .limit(1000)
    )
    if industry_id is not None:
        query = query.where(FundingLink.industry_id == industry_id)
    rows = (await session.execute(query)).all()
    out = []
    for problem, industry_name, amount, pledge_status in rows:
        district = ""
        try:
            submission = await session.get(Submission, problem.submission_id)
            district = (submission.geo_district if submission else "") or ""
        except Exception:
            district = ""
        out.append([
            (problem.title or "")[:120], problem.category or "",
            problem.severity_score or "", district, problem.status or "",
            industry_name or "", float(amount or 0), pledge_status or "",
        ])
    return out


@activity.defn
async def generate_csr_excel_export_activity(data: dict) -> dict:
    """Monthly CSR funding matrix (problems x pledged funding).

    Accepts an optional payload: {"industry_id": <uuid>} for per-org exports
    (used by the industry monthly-matrix download); full matrix by default.
    """
    from app.services import outputs as outputs_svc

    payload = data or {}
    industry_id = payload.get("industry_id")
    async with worker_session() as session:
        matrix = await collect_csr_matrix_rows(session, industry_id=industry_id)
    path = outputs_svc.write_csr_matrix(matrix, "Nitivayu_csr_matches")
    logger.info("CSR export: %s", path)
    return {"path": str(path), "rows": len(matrix)}
