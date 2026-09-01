import uuid
import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.db.session import get_db
from app.db.models import ProblemStatement, UniversityMatch, AuditLog
from app.api.deps import require_role, get_temporal_client, get_current_user
from temporalio.client import Client

router = APIRouter(prefix="/officer", tags=["Officer"])

class UniversityMatchResponse(BaseModel):
    university_id: str
    university_name: str
    match_score: float

class ProblemReviewItem(BaseModel):
    id: str
    title: str
    description: str
    category: str
    severity: str
    district: str
    status: str
    sla_hours_remaining: int
    top_matches: List[UniversityMatchResponse]

class DecisionRequest(BaseModel):
    decision: str = Field(..., description="APPROVE, REJECT, or OVERRIDE")
    override_university_id: Optional[str] = None
    comments: Optional[str] = None

class StatsResponse(BaseModel):
    total_reviewed: int
    pending_review: int
    sla_compliance_percent: float
    recent_activity: List[str]

@router.get("/review-queue", response_model=List[ProblemReviewItem])
async def get_review_queue(
    category: Optional[str] = None,
    district: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("officer"))
):
    """Returns paginated list of problems pending officer review."""
    query = select(ProblemStatement).where(ProblemStatement.status == "PENDING_OFFICER_REVIEW")
    
    if category:
        query = query.where(ProblemStatement.category == category)
    if district:
        query = query.where(ProblemStatement.district == district)
    if severity:
        query = query.where(ProblemStatement.severity == severity)
        
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    problems = result.scalars().all()
    
    response = []
    for p in problems:
        # Mock calculation for SLA
        sla = 48 - (datetime.datetime.now(datetime.timezone.utc) - p.created_at.replace(tzinfo=datetime.timezone.utc)).total_seconds() // 3600
        response.append(ProblemReviewItem(
            id=p.id,
            title=p.title,
            description=p.description,
            category=p.category,
            severity=p.severity,
            district=p.district,
            status=p.status,
            sla_hours_remaining=int(max(0, sla)),
            top_matches=[] # In a real scenario, join with UniversityMatch
        ))
    return response

@router.post("/reviews/{problem_id}/decision")
async def make_decision(
    problem_id: str,
    payload: DecisionRequest,
    db: AsyncSession = Depends(get_db),
    temporal_client: Client = Depends(get_temporal_client),
    user=Depends(require_role("officer"))
):
    """Accept, reject, or override routing for a problem."""
    problem = await db.get(ProblemStatement, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
        
    if payload.decision not in ["APPROVE", "REJECT", "OVERRIDE"]:
        raise HTTPException(status_code=400, detail="Invalid decision")

    if payload.decision == "OVERRIDE" and not payload.override_university_id:
        raise HTTPException(status_code=400, detail="override_university_id required for OVERRIDE")

    problem.status = "ROUTED" if payload.decision != "REJECT" else "REJECTED"
    
    log = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user.id,
        action="DECISION_MADE",
        resource_id=problem_id,
        details=payload.model_dump_json()
    )
    db.add(log)
    await db.commit()

    # Send signal to workflow
    try:
        await temporal_client.get_workflow_handle(f"triage-{problem.submission_id}").signal(
            "officer_decision_signal",
            {"decision": payload.decision, "override_id": payload.override_university_id}
        )
    except Exception:
        pass

    return {"status": "success", "message": "Decision recorded"}

@router.get("/stats", response_model=StatsResponse)
async def get_officer_stats(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("officer"))
):
    """Officer dashboard stats."""
    # Dummy implementation for stats
    return StatsResponse(
        total_reviewed=120,
        pending_review=45,
        sla_compliance_percent=92.5,
        recent_activity=["Reviewed PRB-123", "Approved PRB-124"]
    )
