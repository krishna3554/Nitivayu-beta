import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.session import get_db
from app.db.models import ProblemStatement, Assignment, ProjectTeam, Milestone
from app.api.deps import require_role, get_current_user

router = APIRouter(prefix="/university", tags=["University"])

class InboxItem(BaseModel):
    assignment_id: str
    problem_id: str
    problem_title: str
    match_score: float
    status: str

class RespondAssignmentRequest(BaseModel):
    response: str # ACCEPT or DECLINE
    reason: Optional[str] = None
    faculty_mentor_name: Optional[str] = None
    student_lead_name: Optional[str] = None
    team_members: Optional[List[str]] = None

class MilestoneResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str

class SubmitMilestoneRequest(BaseModel):
    evidence_url: str
    notes: Optional[str] = None

@router.get("/inbox", response_model=List[InboxItem])
async def get_inbox(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("university"))
):
    """University's assigned challenges with match scores."""
    # Assuming user.organization_id holds the university ID
    query = select(Assignment).where(Assignment.university_id == getattr(user, 'organization_id', ''))
    result = await db.execute(query)
    assignments = result.scalars().all()
    
    # Needs a join with ProblemStatement for titles in a complete version
    return [
        InboxItem(
            assignment_id=a.id,
            problem_id=a.problem_id,
            problem_title="Sample Title",
            match_score=a.match_score,
            status=a.status
        ) for a in assignments
    ]

@router.post("/assignments/{assignment_id}/respond")
async def respond_assignment(
    assignment_id: str,
    payload: RespondAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("university"))
):
    """Accept or decline an assignment."""
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if payload.response not in ["ACCEPT", "DECLINE"]:
        raise HTTPException(status_code=400, detail="Invalid response")
        
    assignment.status = payload.response
    
    if payload.response == "ACCEPT":
        team = ProjectTeam(
            id=str(uuid.uuid4()),
            assignment_id=assignment.id,
            university_id=assignment.university_id,
            faculty_mentor_name=payload.faculty_mentor_name,
            student_lead_name=payload.student_lead_name,
            team_members=payload.team_members or []
        )
        db.add(team)
        
    await db.commit()
    return {"status": "success", "message": f"Assignment {payload.response.lower()}ed"}

@router.get("/teams/{team_id}/milestones", response_model=List[MilestoneResponse])
async def get_team_milestones(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("university"))
):
    """Get milestone status for a team."""
    query = select(Milestone).where(Milestone.team_id == team_id)
    result = await db.execute(query)
    milestones = result.scalars().all()
    
    return [MilestoneResponse(
        id=m.id,
        title=m.title,
        description=m.description,
        status=m.status
    ) for m in milestones]

@router.post("/milestones/{milestone_id}/submit")
async def submit_milestone(
    milestone_id: str,
    payload: SubmitMilestoneRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("university"))
):
    """Submit milestone evidence."""
    milestone = await db.get(Milestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
        
    milestone.evidence_url = payload.evidence_url
    milestone.notes = payload.notes
    milestone.status = "UNDER_REVIEW"
    
    await db.commit()
    return {"status": "success"}
