import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import ProblemStatement, Pledge, IndustryPartner
from app.api.deps import require_role, get_current_user

router = APIRouter(prefix="/industry", tags=["Industry"])

class OpportunityResponse(BaseModel):
    problem_id: str
    title: str
    description: str
    category: str
    match_score: float

class CreatePledgeRequest(BaseModel):
    problem_id: str
    team_id: Optional[str] = None
    pledged_amount_inr: float

class PledgeResponse(BaseModel):
    id: str
    problem_id: str
    amount: float
    status: str

class PartnerResponse(BaseModel):
    id: str
    name: str
    focus_areas: List[str]

@router.get("/opportunities", response_model=List[OpportunityResponse])
async def list_opportunities(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """List fundable problems matched to industry CSR focus areas."""
    # Simplified logic
    query = select(ProblemStatement).where(ProblemStatement.status == "ROUTED").limit(20)
    result = await db.execute(query)
    problems = result.scalars().all()
    
    return [
        OpportunityResponse(
            problem_id=p.id,
            title=p.title,
            description=p.description,
            category=p.category,
            match_score=0.95
        ) for p in problems
    ]

@router.post("/pledges", response_model=PledgeResponse)
async def create_pledge(
    payload: CreatePledgeRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("industry"))
):
    """Create funding pledge."""
    pledge = Pledge(
        id=str(uuid.uuid4()),
        industry_partner_id=getattr(user, 'organization_id', ''),
        problem_id=payload.problem_id,
        team_id=payload.team_id,
        amount=payload.pledged_amount_inr,
        status="PENDING"
    )
    db.add(pledge)
    await db.commit()
    await db.refresh(pledge)
    
    return PledgeResponse(
        id=pledge.id,
        problem_id=pledge.problem_id,
        amount=pledge.amount,
        status=pledge.status
    )

@router.get("/pledges", response_model=List[PledgeResponse])
async def list_pledges(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("industry", "admin"))
):
    """List all pledges with status tracking."""
    query = select(Pledge)
    # If not admin, restrict to their own
    if user.role != "admin":
        query = query.where(Pledge.industry_partner_id == getattr(user, 'organization_id', ''))
        
    result = await db.execute(query)
    pledges = result.scalars().all()
    
    return [
        PledgeResponse(id=p.id, problem_id=p.problem_id, amount=p.amount, status=p.status)
        for p in pledges
    ]

@router.get("/partners", response_model=List[PartnerResponse])
async def list_partners(
    db: AsyncSession = Depends(get_db)
):
    """List registered industry partners."""
    query = select(IndustryPartner)
    result = await db.execute(query)
    partners = result.scalars().all()
    
    return [
        PartnerResponse(id=p.id, name=p.name, focus_areas=p.focus_areas or [])
        for p in partners
    ]
