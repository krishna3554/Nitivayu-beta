"""Batch-triage control plane: on-demand runs, cadence schedules, run history.

Runs the real WeeklyBatchTriageWorkflow on the shared triage-queue worker.
EventSource cannot send headers, so the SSE stream takes ?token= like the
public events stream (see routes/events.py).
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as deps_mod
from app.api.deps import get_db, get_temporal_client, require_role
from app.db.models import BatchRun, CadenceConfig, Submission
from temporalio.client import Client
from temporalio.exceptions import TemporalError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/triage", tags=["Batch Triage"])

BATCH_TASK_QUEUE = "triage-queue"
WEEKLY_SCHEDULE_ID = "nitivayu-batch-weekly"
MONTHLY_SCHEDULE_ID = "nitivayu-batch-monthly"
CADENCE_ROW_ID = "default"
VALID_CADENCES = {"weekly"}
_CRON_RE = re.compile(r"^[\d\*,/\-\s,]+$")


class TriggerBatchRequest(BaseModel):
    cadence_type: str = "weekly"
    include_unassigned_only: bool = True


class TriggerBatchResponse(BaseModel):
    batch_workflow_id: str
    status: str
    stream_url: str


class ScheduleResponse(BaseModel):
    active_cadence: str
    cron_expression: str
    next_run_utc: Optional[str] = None
    monthly_macro_cron: str
    monthly_next_run_utc: Optional[str] = None
    pending_count: int = 0
    schedule_status: str = "none"


class UpdateScheduleRequest(BaseModel):
    cron_expression: str = Field(min_length=9, max_length=100)
    monthly_macro_cron: str = Field(min_length=9, max_length=100)
    active_cadence: str = Field(min_length=3, max_length=50)


class BatchJobResponse(BaseModel):
    batch_id: str
    cadence: str
    status: str
    total: int
    processed: int
    failed: int
    duplicates: int
    csv_path: Optional[str] = None
    pdf_path: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None


def _job_to_response(row: BatchRun) -> BatchJobResponse:
    duration = None
    if row.started_at and row.finished_at:
        start = row.started_at if row.started_at.tzinfo else row.started_at.replace(tzinfo=timezone.utc)
        end = row.finished_at if row.finished_at.tzinfo else row.finished_at.replace(tzinfo=timezone.utc)
        duration = round((end - start).total_seconds(), 1)
    return BatchJobResponse(
        batch_id=row.batch_id,
        cadence=row.cadence,
        status=row.status,
        total=row.total or 0,
        processed=row.processed or 0,
        failed=row.failed or 0,
        duplicates=row.duplicates or 0,
        csv_path=row.csv_path,
        pdf_path=row.pdf_path,
        error=row.error,
        started_at=row.started_at.isoformat() if row.started_at else None,
        finished_at=row.finished_at.isoformat() if row.finished_at else None,
        duration_seconds=duration,
    )


async def _get_config(db: AsyncSession) -> CadenceConfig | None:
    return (await db.execute(select(CadenceConfig).where(CadenceConfig.id == CADENCE_ROW_ID))).scalars().first()


def _check_cron(value: str, label: str) -> str:
    cleaned = (value or "").strip()
    if len(cleaned.split()) != 5 or not _CRON_RE.match(cleaned):
        raise HTTPException(status_code=400, detail=f"{label} must be a 5-field cron expression (e.g. '0 0 * * 0').")
    return cleaned


async def _schedule_next_run(client: Client, schedule_id: str) -> Optional[str]:
    try:
        handle = client.get_schedule_handle(schedule_id)
        described = await handle.describe()
        times = list(getattr(getattr(described, "info", None), "next_action_times", None) or [])
        moment = times[0] if times else None
        return moment.isoformat() if moment else None
    except Exception:
        return None


async def _upsert_temporal_schedule(client: Client, *, schedule_id: str, cron: str, workflow: str, workflow_id: str, args: list) -> None:
    """Create or update a Temporal schedule (raises on invalid cron)."""
    from temporalio.client import (
        Schedule,
        ScheduleActionStartWorkflow,
        ScheduleSpec,
    )
    action = ScheduleActionStartWorkflow(
        workflow,
        args=args,
        id=workflow_id,
        task_queue=BATCH_TASK_QUEUE,
    )
    spec = ScheduleSpec(cron_expressions=[cron], time_zone_name="UTC")
    def _converged(exc: Exception) -> bool:
        # An existing schedule with identical identity surfaces as
        # "already running" on some server versions — that IS the converged
        # state, not a failure.
        msg = str(exc).lower()
        return "already running" in msg or "already exists" in msg

    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.describe()
        await handle.update(lambda prev: Schedule(action=action, spec=spec, state=prev.state, policy=prev.policy))
        return
    except Exception as exc:
        if _converged(exc):
            return
        last_error = exc
    try:
        await client.create_schedule(schedule_id, Schedule(action=action, spec=spec))
    except Exception as exc:
        if _converged(exc):
            return
        raise


@router.post("/trigger-batch", response_model=TriggerBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_batch(
    payload: TriggerBatchRequest,
    db: AsyncSession = Depends(get_db),
    temporal_client: Client = Depends(get_temporal_client),
    user=Depends(require_role("admin", "officer")),
):
    """Start a real on-demand weekly batch run via Temporal."""
    cadence = (payload.cadence_type or "weekly").lower()
    if cadence not in VALID_CADENCES:
        raise HTTPException(
            status_code=400,
            detail=f"Cadence '{payload.cadence_type}' is not runnable yet — only 'weekly' batch runs are implemented.",
        )
    batch_id = f"batch-triage-{uuid.uuid4().hex[:8]}"
    db.add(BatchRun(batch_id=batch_id, cadence=cadence, status="RUNNING"))
    await db.commit()
    try:
        await temporal_client.start_workflow(
            "WeeklyBatchTriageWorkflow",
            args=[batch_id, cadence, payload.include_unassigned_only],
            id=batch_id,
            task_queue=BATCH_TASK_QUEUE,
        )
    except Exception as exc:
        logger.warning("Batch workflow start failed for %s", batch_id, exc_info=True)
        row = await db.get(BatchRun, batch_id)
        if row is not None:
            row.status = "FAILED"
            row.error = f"Could not start workflow: {exc}"
            row.finished_at = datetime.now(timezone.utc)
            await db.commit()
        raise HTTPException(status_code=502, detail="Temporal is unreachable — the batch could not start.")
    return TriggerBatchResponse(
        batch_workflow_id=batch_id,
        status="STARTED",
        stream_url=f"/api/v1/admin/triage/batch-jobs/{batch_id}/stream",
    )


@router.get("/schedules", response_model=ScheduleResponse)
async def get_schedules(
    db: AsyncSession = Depends(get_db),
    temporal_client: Client = Depends(get_temporal_client),
    user=Depends(require_role("admin", "officer")),
):
    """Cadence config from DB plus live backlog count and Temporal next runs."""
    config = await _get_config(db)
    pending = (
        await db.execute(select(func.count(Submission.submission_id)).where(Submission.status == "PENDING_TRIAGE"))
    ).scalar_one()
    weekly_next = monthly_next = None
    sched_status = "none"
    try:
        weekly_next = await _schedule_next_run(temporal_client, WEEKLY_SCHEDULE_ID)
        monthly_next = await _schedule_next_run(temporal_client, MONTHLY_SCHEDULE_ID)
        if weekly_next or monthly_next:
            sched_status = "scheduled"
    except Exception:
        sched_status = "temporal-unreachable"
    if config is None:
        return ScheduleResponse(
            active_cadence="weekly",
            cron_expression="0 0 * * 0",
            next_run_utc=weekly_next,
            monthly_macro_cron="0 0 1 * *",
            monthly_next_run_utc=monthly_next,
            pending_count=pending,
            schedule_status=sched_status,
        )
    return ScheduleResponse(
        active_cadence=config.active_cadence,
        cron_expression=config.cron_expression,
        next_run_utc=weekly_next,
        monthly_macro_cron=config.monthly_macro_cron,
        monthly_next_run_utc=monthly_next,
        pending_count=pending,
        schedule_status=sched_status,
    )


@router.put("/schedules")
async def update_schedules(
    payload: UpdateScheduleRequest,
    db: AsyncSession = Depends(get_db),
    temporal_client: Client = Depends(get_temporal_client),
    user=Depends(require_role("admin", "officer")),
):
    """Persist cadence config and (re)create the Temporal schedules.

    WP-11: the monthly macro schedule is created alongside the weekly one —
    previously the cron was stored in the DB but no Temporal schedule existed,
    so MonthlyMacroTriageWorkflow could never run on cadence.
    """
    cron = _check_cron(payload.cron_expression, "cron_expression")
    monthly_cron = _check_cron(payload.monthly_macro_cron, "monthly_macro_cron")
    cadence = (payload.active_cadence or "weekly").lower()
    if cadence not in {"weekly", "continuous"}:
        raise HTTPException(status_code=400, detail="active_cadence must be 'weekly' or 'continuous'.")
    config = await _get_config(db)
    if config is None:
        config = CadenceConfig(id=CADENCE_ROW_ID)
        db.add(config)
    config.active_cadence = cadence
    config.cron_expression = cron
    config.monthly_macro_cron = monthly_cron
    await db.commit()
    schedule_errors: list[str] = []
    if cadence == "weekly":
        try:
            await _upsert_temporal_schedule(
                temporal_client,
                schedule_id=WEEKLY_SCHEDULE_ID,
                cron=cron,
                workflow="WeeklyBatchTriageWorkflow",
                workflow_id="batch-triage-weekly",
                args=[f"batch-triage-sched-{uuid.uuid4().hex[:8]}", "weekly", True],
            )
        except Exception as exc:
            logger.warning("Temporal weekly schedule upsert failed", exc_info=True)
            schedule_errors.append(f"weekly: {exc}")
    try:
        await _upsert_temporal_schedule(
            temporal_client,
            schedule_id=MONTHLY_SCHEDULE_ID,
            cron=monthly_cron,
            workflow="MonthlyMacroTriageWorkflow",
            workflow_id="macro-monthly",
            args=[],
        )
    except Exception as exc:
        logger.warning("Temporal monthly schedule upsert failed", exc_info=True)
        schedule_errors.append(f"monthly: {exc}")
    body: dict = {"status": "success", "message": "Schedule updated"}
    if schedule_errors:
        body["schedule_error"] = "Saved, but Temporal schedule(s) could not be created: " + "; ".join(schedule_errors)
    return body


@router.get("/batch-jobs", response_model=list[BatchJobResponse])
async def list_batch_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "officer")),
):
    """Real run history, newest first."""
    rows = (
        await db.execute(select(BatchRun).order_by(BatchRun.started_at.desc()).limit(limit))
    ).scalars().all()
    return [_job_to_response(row) for row in rows]


@router.get("/batch-jobs/{batch_id}/stream")
async def stream_batch_job(
    batch_id: str,
    token: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    temporal_client: Client = Depends(get_temporal_client),
):
    """Live SSE progress for one batch run (EventSource ?token= auth).

    Polls Temporal workflow describe() every 2s — every event below is live
    state, never scripted. Caps at 20 minutes, then closes the stream.
    """
    user = None
    if token:
        try:
            user = await deps_mod.get_current_user(token)
        except Exception:
            user = None
    role = (user or {}).get("role", "")
    workspace = deps_mod.workspace_of(user) if user else "citizen"
    if workspace not in {"officer", "admin"} and role not in {"officer", "admin"}:
        raise HTTPException(status_code=403, detail="Batch progress is visible to officers and admins.")

    try:
        handle = temporal_client.get_workflow_handle(batch_id)
        described = await handle.describe()
        _ = described
    except Exception:
        row = await db.get(BatchRun, batch_id)
        if row is None:
            raise HTTPException(status_code=404, detail="No batch run with that id.")
        # Workflow gone from Temporal (retention) but row exists: replay history.
        snapshot = _job_to_response(row)

        async def _replay():
            import json as _json

            yield f"event: done\ndata: {_json.dumps(snapshot.model_dump())}\n\n"

        return StreamingResponse(_replay(), media_type="text/event-stream")

    async def event_generator():
        import json as _json

        yield f"event: started\ndata: {_json.dumps({'batch_id': batch_id})}\n\n"
        deadline = asyncio.get_event_loop().time() + 20 * 60
        terminal = {"COMPLETED", "FAILED", "CANCELLED", "TERMINATED", "TIMED_OUT", "CONTINUED_AS_NEW"}
        while True:
            try:
                described = await handle.describe()
                raw_status = described.status
                status_name = getattr(raw_status, "name", str(raw_status)).upper().replace("WORKFLOW_EXECUTION_STATUS_", "")
            except Exception as exc:
                yield f"event: error\ndata: {_json.dumps({'message': f'Lost track of the workflow: {exc}'})}\n\n"
                return
            if status_name in terminal:
                row = await db.get(BatchRun, batch_id)
                if status_name == "COMPLETED":
                    try:
                        result = await handle.result()
                    except TemporalError as exc:
                        result = {"status": "FAILED", "error": str(exc)}
                    if row is not None and row.status == "RUNNING":
                        row.status = "COMPLETED"
                        row.finished_at = datetime.now(timezone.utc)
                        if isinstance(result, dict):
                            row.processed = result.get("processed_count", row.processed)
                            row.csv_path = result.get("csv_report", row.csv_path)
                            row.pdf_path = result.get("pdf_report", row.pdf_path)
                        await db.commit()
                    yield f"event: done\ndata: {_json.dumps(result if isinstance(result, dict) else {'status': status_name})}\n\n"
                else:
                    if row is not None and row.status == "RUNNING":
                        row.status = status_name
                        row.finished_at = datetime.now(timezone.utc)
                        await db.commit()
                    yield f"event: done\ndata: {_json.dumps({'status': status_name})}\n\n"
                return
            elapsed = None
            row = await db.get(BatchRun, batch_id)
            payload = {"status": "RUNNING", "batch_id": batch_id}
            if row is not None:
                payload.update({"processed": row.processed or 0, "total": row.total or 0})
            yield f"event: progress\ndata: {_json.dumps(payload)}\n\n"
            if asyncio.get_event_loop().time() > deadline:
                yield f"event: timeout\ndata: {_json.dumps({'message': 'Still running after 20 minutes — stream closed, history keeps the final result.'})}\n\n"
                return
            await asyncio.sleep(2)
            _ = elapsed

    return StreamingResponse(event_generator(), media_type="text/event-stream")
