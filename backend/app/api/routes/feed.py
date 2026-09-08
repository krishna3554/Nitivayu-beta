"""Public civic feed — every non-rejected report, visible to anyone.

- GET  /feed                    paginated public list (filters + like counts)
- POST /feed/{problem_id}/like  idempotent like/unlike toggle

Privacy contract (this surface is fully public, unlike the workspace views):
- tracking_token is NEVER returned — it doubles as the report-claim secret.
- reporter names are reduced to first name + last initial; contact channels
  (email/phone) and exact coordinates are never exposed; district only.
- evidence photos/audio stay behind the role-checked /media/{asset_id} route;
  the feed is text-only so unmoderated uploads can never leak here.
- REJECTED problems are excluded from the feed entirely.
"""

import hashlib
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, get_db, parse_uuid
from app.db.models import Problem, ReportLike, Submission
from app.services.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feed", tags=["feed"])

# Anonymous voter tokens are client-generated UUIDs held in localStorage.
# Hex-with-dashes or bare hex, nothing else — keeps voter_key bounded.
_ANON_VOTER_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")


class LikeRequest(BaseModel):
    voter_key: str | None = None


def _resolve_voter(user: dict | None, anon_key: str | None) -> str | None:
    """Stable like identity: signed-in account wins, anonymous UUID otherwise."""
    if user and user.get("user_id"):
        digest = hashlib.sha256(str(user["user_id"]).encode("utf-8")).hexdigest()[:32]
        return f"u:{digest}"
    if anon_key:
        cleaned = anon_key.strip()
        if _ANON_VOTER_RE.fullmatch(cleaned):
            return f"a:{cleaned.replace('-', '').lower()}"
    return None


def _public_reporter(name: str | None) -> str:
    """'Krishna Lokhande' -> 'Krishna L.' — enough for a byline, not for PII."""
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return "Anonymous"
    first = parts[0][:40]
    initial = f" {parts[1][0]}." if len(parts) > 1 and parts[1] else ""
    return f"{first}{initial}"


@router.get("")
async def list_feed(
    skip: int = 0,
    limit: int = 12,
    category: str | None = None,
    district: str | None = None,
    sort: str = "recent",
    voter: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """Public report feed, newest first (or most-liked with sort=top).

    Mirrors the review-queue contract ({items, total, skip, limit, has_more})
    so pagination behaves the same everywhere. `voter` is the anonymous
    localStorage token used only to flag `liked_by_me`; signed-in callers are
    recognized from their bearer token instead.
    """
    limit = max(1, min(limit, 50))
    skip = max(0, skip)
    like_counts = (
        select(ReportLike.problem_id.label("problem_id"), func.count(ReportLike.like_id).label("like_count"))
        .group_by(ReportLike.problem_id)
        .subquery()
    )
    like_count_col = func.coalesce(like_counts.c.like_count, 0)
    base_filter = Problem.status != "REJECTED"

    count_stmt = (
        select(func.count(Problem.problem_id))
        .join(Submission, Problem.submission_id == Submission.submission_id)
        .where(base_filter)
    )
    stmt = (
        select(Problem, Submission, like_count_col.label("like_count"))
        .join(Submission, Problem.submission_id == Submission.submission_id)
        .outerjoin(like_counts, like_counts.c.problem_id == Problem.problem_id)
        .where(base_filter)
    )
    if category:
        count_stmt = count_stmt.where(Problem.category == category)
        stmt = stmt.where(Problem.category == category)
    if district:
        count_stmt = count_stmt.where(Submission.geo_district == district)
        stmt = stmt.where(Submission.geo_district == district)
    if sort == "top":
        stmt = stmt.order_by(like_count_col.desc(), Problem.created_at.desc())
    else:
        stmt = stmt.order_by(Problem.created_at.desc())

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.offset(skip).limit(limit))).all()

    voter_key = _resolve_voter(user, voter)
    liked_ids: set[str] = set()
    page_ids = [problem.problem_id for problem, _, _ in rows]
    if voter_key and page_ids:
        liked_rows = (
            await db.execute(
                select(ReportLike.problem_id).where(
                    ReportLike.voter_key == voter_key,
                    ReportLike.problem_id.in_(page_ids),
                )
            )
        ).all()
        liked_ids = {str(row[0]) for row in liked_rows}

    items = [
        {
            "problem_id": str(problem.problem_id),
            "title": problem.title,
            "summary": problem.summary,
            "category": problem.category,
            "severity": problem.severity_score,
            "status": problem.status,
            "district": submission.geo_district,
            "reporter": _public_reporter(submission.reporter_name),
            "created_at": problem.created_at.isoformat() if problem.created_at else None,
            "like_count": int(like_count or 0),
            "liked_by_me": str(problem.problem_id) in liked_ids,
        }
        for problem, submission, like_count in rows
    ]
    return {"items": items, "total": total, "skip": skip, "limit": limit, "has_more": skip + len(items) < total}


@router.post("/{problem_id}/like")
async def toggle_like(
    problem_id: str,
    payload: LikeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
    _limited: bool = Depends(rate_limit(limit=30, window_seconds=60)),
):
    """Idempotent like/unlike toggle. Anonymous callers pass their
    localStorage voter UUID; signed-in callers are keyed to their account so
    likes follow them across devices."""
    problem = await db.get(Problem, parse_uuid(problem_id, "problem_id"))
    if problem is None or problem.status == "REJECTED":
        raise HTTPException(status_code=404, detail="Report not found")
    voter = _resolve_voter(user, payload.voter_key)
    if voter is None:
        raise HTTPException(status_code=422, detail="A voter_key is required to like a report")
    existing = (
        await db.execute(
            select(ReportLike).where(
                ReportLike.problem_id == problem.problem_id,
                ReportLike.voter_key == voter,
            ).limit(1)
        )
    ).scalars().first()
    if existing is not None:
        await db.delete(existing)
        liked = False
    else:
        db.add(ReportLike(problem_id=problem.problem_id, voter_key=voter))
        liked = True
    await db.flush()
    like_count = (
        await db.execute(select(func.count(ReportLike.like_id)).where(ReportLike.problem_id == problem.problem_id))
    ).scalar_one()
    await db.commit()
    return {"liked": liked, "like_count": int(like_count or 0)}
