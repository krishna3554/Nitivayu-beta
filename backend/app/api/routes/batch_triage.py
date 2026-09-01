import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.session import get_db
from app.db.models import CadenceConfig
from app.api.deps import require_role, get_temporal_client
from temporalio.client import Client

router = APIRouter(prefix="/admin/triage", tags=["Batch Triage"])

class TriggerBatchRequest(BaseModel):
    cadence_type: str
    include_unassigned_only: bool = True

class TriggerBatchResponse(BaseModel):
    batch_workflow_id: str
    status: str
    stream_url: str

class ScheduleResponse(BaseModel):
    active_cadence: str
    cron_expression: str
    next_run_utc: Optional[str]
    monthly_macro_cron: str
    monthly_next_run_utc: Optional[str]

class UpdateScheduleRequest(BaseModel):
    cron_expression: str
    monthly_macro_cron: str
    active_cadence: str

@router.post("/trigger-batch", response_model=TriggerBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_batch(
    payload: TriggerBatchRequest,
    temporal_client: Client = Depends(get_temporal_client),
    user=Depends(require_role("admin"))
):
    """Start on-demand batch triage via Temporal."""
    batch_id = f"batch-triage-{uuid.uuid4().hex[:8]}"
    
    try:
        await temporal_client.start_workflow(
            "BatchTriageWorkflow",
            {"cadence": payload.cadence_type, "unassigned_only": payload.include_unassigned_only},
            id=batch_id,
            task_queue="batch-queue"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")
        
    return TriggerBatchResponse(
        batch_workflow_id=batch_id,
        status="STARTED",
        stream_url=f"/admin/triage/batch-jobs/{batch_id}/stream"
    )

@router.get("/schedules", response_model=ScheduleResponse)
async def get_schedules(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin"))
):
    """Return active cadence config."""
    result = await db.execute(select(CadenceConfig).limit(1))
    config = result.scalars().first()
    
    if not config:
        return ScheduleResponse(
            active_cadence="WEEKLY",
            cron_expression="0 0 * * 0",
            next_run_utc=None,
            monthly_macro_cron="0 0 1 * *",
            monthly_next_run_utc=None
        )
        
    return ScheduleResponse(
        active_cadence=config.active_cadence,
        cron_expression=config.cron_expression,
        next_run_utc=str(config.next_run_utc) if getattr(config, 'next_run_utc', None) else None,
        monthly_macro_cron=config.monthly_macro_cron,
        monthly_next_run_utc=str(config.monthly_next_run_utc) if getattr(config, 'monthly_next_run_utc', None) else None
    )

@router.put("/schedules")
async def update_schedules(
    payload: UpdateScheduleRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin"))
):
    """Update cadence schedule."""
    result = await db.execute(select(CadenceConfig).limit(1))
    config = result.scalars().first()
    
    if not config:
        config = CadenceConfig(id=str(uuid.uuid4()))
        db.add(config)
        
    config.cron_expression = payload.cron_expression
    config.monthly_macro_cron = payload.monthly_macro_cron
    config.active_cadence = payload.active_cadence
    
    await db.commit()
    return {"status": "success", "message": "Schedule updated"}

@router.get("/batch-jobs/{batch_id}/stream")
async def stream_batch_job(batch_id: str, user=Depends(require_role("admin"))):
    """SSE endpoint streaming batch job progress updates."""
    async def event_generator():
        yield "data: {\"status\": \"running\", \"progress\": 50}\n\n"
        # In reality, this would poll Temporal or listen to a pub/sub stream
    return StreamingResponse(event_generator(), media_type="text/event-stream")
