import uuid
import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.db.session import get_db
from app.db.models import Submission, ProblemStatement
from app.api.deps import get_current_user, require_role, get_temporal_client
from app.config import get_settings
from temporalio.client import Client

router = APIRouter(prefix="/submissions", tags=["Submissions"])

class SubmissionCreateResponse(BaseModel):
    submission_id: str
    tracking_token: str
    status: str

class MilestoneProgress(BaseModel):
    milestone_id: str
    status: str
    completion_date: Optional[datetime.datetime] = None

class TrackingResponse(BaseModel):
    tracking_token: str
    status: str
    category: Optional[str] = None
    severity: Optional[str] = None
    matched_university: Optional[str] = None
    milestones: List[MilestoneProgress] = []

class SubmissionListResponse(BaseModel):
    id: str
    tracking_token: str
    status: str
    created_at: datetime.datetime

@router.post("", response_model=SubmissionCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_submission(
    raw_text: str = Form(...),
    photo: Optional[UploadFile] = File(None),
    geo_lat: Optional[float] = Form(None),
    geo_lng: Optional[float] = Form(None),
    language_pref: str = Form("en"),
    db: AsyncSession = Depends(get_db),
    temporal_client: Client = Depends(get_temporal_client)
):
    """Create a new citizen submission."""
    tracking_token = f"NITIVAYU-{datetime.datetime.now().year}-JH-{uuid.uuid4().hex[:4].upper()}"
    new_submission = Submission(
        id=str(uuid.uuid4()),
        raw_text=raw_text,
        geo_lat=geo_lat,
        geo_lng=geo_lng,
        language_pref=language_pref,
        tracking_token=tracking_token,
        status="PENDING_TRIAGE"
    )
    db.add(new_submission)
    await db.commit()
    await db.refresh(new_submission)

    try:
        await temporal_client.start_workflow(
            "ChallengeTriageWorkflow",
            {"submission_id": new_submission.id, "text": raw_text},
            id=f"triage-{new_submission.id}",
            task_queue="triage-queue"
        )
    except Exception as e:
        # Log error in real implementation
        pass
        
    return SubmissionCreateResponse(
        submission_id=new_submission.id,
        tracking_token=tracking_token,
        status=new_submission.status
    )

@router.get("/{tracking_token}/track", response_model=TrackingResponse)
async def track_submission(tracking_token: str, db: AsyncSession = Depends(get_db)):
    """Public tracking endpoint for a submission."""
    result = await db.execute(select(Submission).where(Submission.tracking_token == tracking_token))
    submission = result.scalars().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
        
    return TrackingResponse(
        tracking_token=submission.tracking_token,
        status=submission.status,
        category=getattr(submission, 'category', None),
        severity=getattr(submission, 'severity', None),
        matched_university=None,
        milestones=[]
    )

@router.get("", response_model=List[SubmissionListResponse])
async def list_submissions(
    district: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("officer", "admin"))
):
    """List submissions with pagination and filtering."""
    query = select(Submission)
    if district:
        query = query.where(getattr(Submission, 'district', None) == district)
    if status:
        query = query.where(Submission.status == status)
    if start_date:
        query = query.where(Submission.created_at >= start_date)
    if end_date:
        query = query.where(Submission.created_at <= end_date)
        
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    submissions = result.scalars().all()
    
    return [
        SubmissionListResponse(
            id=s.id,
            tracking_token=s.tracking_token,
            status=s.status,
            created_at=s.created_at
        ) for s in submissions
    ]
