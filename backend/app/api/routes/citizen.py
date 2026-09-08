"""Citizen account-scoped endpoints (WP-1).

Submissions were anonymous-only (localStorage hoarding in the UI). These
endpoints make accounts first-class: a signed-in citizen sees every report
they filed from any device, and can claim an anonymous report with its
tracking token (the token is the proof of ownership).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_role
from app.db.models import Problem, RouteAssignment, Submission, University
from app.services.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/citizen", tags=["citizen"])


def _caller_uuid(user: dict) -> uuid.UUID:
    """JWT sub is a users.user_id UUID for registered accounts (email for
    officer logins — those never pass the citizen role gate)."""
    try:
        return uuid.UUID(str(user["user_id"]))
    except (ValueError, AttributeError, TypeError, KeyError):
        raise HTTPException(status_code=403, detail="This account cannot own citizen reports")


class ClaimRequest(BaseModel):
    tracking_token: str = Field(min_length=8, max_length=64)


@router.get("/reports")
async def my_reports(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("citizen"))):
    """All reports owned by the signed-in citizen, newest first."""
    owner = _caller_uuid(user)
    rows = (await db.execute(
        select(Submission, Problem)
        .join(Problem, Problem.submission_id == Submission.submission_id, isouter=True)
        .where(Submission.user_id == owner)
        .order_by(Submission.created_at.desc())
        .limit(200)
    )).all()
    items = []
    for submission, problem in rows:
        matched_university = None
        if problem is not None:
            assignment = (await db.execute(
                select(RouteAssignment)
                .options(selectinload(RouteAssignment.university))
                .where(RouteAssignment.problem_id == problem.problem_id)
                .order_by(RouteAssignment.rank_order)
                .limit(1)
            )).scalars().first()
            if assignment and assignment.university:
                matched_university = assignment.university.name
        items.append({
            "tracking_token": submission.tracking_token,
            "title": problem.title if problem else submission.raw_text[:120],
            "status": (problem.status if problem else submission.status),
            "category": problem.category if problem else None,
            "district": submission.geo_district,
            "matched_university": matched_university,
            "created_at": submission.created_at.isoformat() if submission.created_at else None,
        })
    return {"items": items, "count": len(items)}


@router.post("/reports/claim", dependencies=[Depends(rate_limit(setting="RATE_LIMIT_AUTH_PER_MIN"))])
async def claim_report(payload: ClaimRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("citizen"))):
    """Attach an anonymous report to the signed-in account by tracking token."""
    owner = _caller_uuid(user)
    submission = (await db.execute(
        select(Submission).where(Submission.tracking_token == payload.tracking_token.strip())
    )).scalars().first()
    if submission is None:
        raise HTTPException(status_code=404, detail="No report found for that tracking token")
    if submission.user_id is not None and submission.user_id != owner:
        raise HTTPException(status_code=409, detail="This report is already linked to another account")
    if submission.user_id == owner:
        return {"status": "already_linked", "tracking_token": submission.tracking_token}
    submission.user_id = owner
    await db.commit()
    logger.info("Submission %s claimed by user %s", submission.submission_id, owner)
    return {"status": "claimed", "tracking_token": submission.tracking_token}
