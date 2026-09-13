"""Public Reports Feed — every triaged citizen report, visible to the community.

- GET  /feed                        paginated public list (filters + engagement counts + media flags)
- GET  /feed/{problem_id}/media     clean-evidence listing for one report (public)
- GET  /feed/media/{asset_id}       serve one clean photo/audio note (public)
- GET  /feed/{problem_id}/comments  visible comment thread (public read)
- POST /feed/{problem_id}/me-too    "I experience this too" (citizen auth, once per citizen)
- DELETE /feed/{problem_id}/me-too  withdraw a me-too (citizen auth)
- POST /feed/{problem_id}/confirm   "I have seen this firsthand" (citizen auth, once)
- POST /feed/{problem_id}/comments  post to the thread (citizen auth, moderated)
- POST /feed/{problem_id}/like      legacy anonymous like toggle (kept for backwards compat)

Privacy contract (this surface is fully public, unlike the workspace views):
- Reporter names are reduced to first name + last initial; contact channels
  (email/phone) and exact coordinates are never exposed; district/block only.
- Only clean-moderated photos/audio are listed or served here; pending or
  flagged uploads stay behind the role-checked /media/{asset_id} route.
- The tracking token IS returned (small, muted, powers "Share → /track/:token").
  Claiming a report still requires a signed-in citizen account, so a public
  token alone cannot hijack ownership.

Feed-visibility gating (anti-raw-leak):
- PII redaction runs inside the extraction activity BEFORE officer review
  (services/llm.py redact_pii), but intake creates the problem with
  summary=raw_text (unredacted). The feed therefore only lists problems that
  have passed extraction — INGESTED / PENDING_TRIAGE / TRIAGING are excluded —
  plus excludes REJECTED / MERGED / DUPLICATE. Raw unfiltered submissions
  with unredacted PII can never appear here.

Engagement semantics (civic, not social):
- "Me too" = same-issue experience. Genuinely feeds triage: at >=3 me-toos a
  problem below severity 5 is bumped +1 (audit CROWD_SEVERITY_BOOST) so
  duplicate-cluster weight reflects real crowd volume.
- "Confirm" = third-party nearby verification. Weighted differently: it never
  touches severity; at >=2 confirms the report is marked community-
  corroborated (audit CROWD_CONFIRMED) for dedup confidence.
- No generic emoji reactions — they trivialize water/health reports.
"""

import hashlib
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_user_optional,
    get_db,
    parse_uuid,
    workspace_of,
)
from app.db.models import (
    MediaAsset,
    Problem,
    ReportComment,
    ReportConfirmation,
    ReportLike,
    RouteAssignment,
    Submission,
    University,
)
from app.services.audit import make_audit
from app.services.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feed", tags=["feed"])

# Anonymous voter tokens are client-generated UUIDs held in localStorage.
# Hex-with-dashes or bare hex, nothing else — keeps voter_key bounded.
_ANON_VOTER_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")

# --- Feed-visibility gating -------------------------------------------------
# Intake summary is raw_text until extraction redacts + enriches it, so only
# post-extraction statuses are ever public. Terminal/duplicate states stay out.
FEED_VISIBLE_STATUSES = frozenset({
    "PENDING_OFFICER_REVIEW",
    "OFFICER_REVIEW",
    "ROUTED",
    "ROUTED_TO_UNIVERSITY",
    "OFFERED",
    "PENDING_APPROVAL",
    "PLEDGED",
    "ACCEPTED",
    "TEAM_FORMED",
    "IN_PROGRESS",
    "SUBMITTED",
    "VERIFIED",
    "DISBURSED",
    "COMPLETED",
    "RESOLVED",
    "ESCALATED",
    "ESCALATED_TO_SENIOR_OFFICER",
})

# UI status buckets (the feed filter vocabulary) → backend statuses.
STATUS_BUCKETS = {
    "ingested": {"PENDING_OFFICER_REVIEW", "OFFICER_REVIEW"},
    "routed": {"ROUTED", "ROUTED_TO_UNIVERSITY", "OFFERED", "PENDING_APPROVAL", "PLEDGED"},
    "in_progress": {"ACCEPTED", "TEAM_FORMED", "IN_PROGRESS", "SUBMITTED", "VERIFIED"},
    "resolved": {"COMPLETED", "RESOLVED"},
}

# A report counts as officer-verified once routing has happened (or a match exists).
OFFICER_VERIFIED_STATUSES = frozenset({
    "ROUTED", "ROUTED_TO_UNIVERSITY", "OFFERED", "PENDING_APPROVAL", "PLEDGED",
    "ACCEPTED", "TEAM_FORMED", "IN_PROGRESS", "SUBMITTED", "VERIFIED",
    "DISBURSED", "COMPLETED", "RESOLVED",
})

# Crowd-signal thresholds.
ME_TOO_SEVERITY_QUORUM = 3
CONFIRM_CORROBORATED_QUORUM = 2
MAX_COMMENT_CHARS = 1000

# Minimal server-side moderation: blocklist + spam heuristics. Kept small and
# legible on purpose; a provider hook can replace _moderate_comment later.
_BLOCKED_WORDS = frozenset({
    "chutiya", "bhosdike", "madarchod", "behenchod", "randi",
})
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_REPEAT_RE = re.compile(r"(.)\1{9,}")


class LikeRequest(BaseModel):
    voter_key: str | None = None


class CommentRequest(BaseModel):
    body: str = ""
    parent_id: str | None = None


def _resolve_voter(user: dict | None, anon_key: str | None) -> str | None:
    """Stable engagement identity: signed-in account wins, anonymous UUID otherwise."""
    if user and user.get("user_id"):
        digest = hashlib.sha256(str(user["user_id"]).encode("utf-8")).hexdigest()[:32]
        return f"u:{digest}"
    if anon_key:
        cleaned = anon_key.strip()
        if _ANON_VOTER_RE.fullmatch(cleaned):
            return f"a:{cleaned.replace('-', '').lower()}"
    return None


def _account_voter(user: dict) -> str:
    """Account-bound voter key for the auth-gated endpoints (no anonymous)."""
    digest = hashlib.sha256(str(user["user_id"]).encode("utf-8")).hexdigest()[:32]
    return f"u:{digest}"


def _require_citizen(user: dict) -> dict:
    """Read is free, acting needs a citizen account (phone-OTP auth)."""
    workspace = workspace_of(user)
    if workspace not in {"citizen", "admin"}:
        raise HTTPException(
            status_code=403,
            detail="A citizen account is required to react or comment. Officers, universities and CSR partners act from their own workspaces.",
        )
    return user


def _public_reporter(name: str | None) -> str:
    """'Krishna Lokhande' -> 'Krishna L.' — enough for a byline, not for PII."""
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return "Anonymous"
    first = parts[0][:40]
    initial = f" {parts[1][0]}." if len(parts) > 1 and parts[1] else ""
    return f"{first}{initial}"


def _moderate_comment(body: str) -> str | None:
    """Return a rejection reason, or None when the comment may be published."""
    text = (body or "").strip()
    if not text:
        return "Comment cannot be blank"
    if len(text) > MAX_COMMENT_CHARS:
        return f"Comment is too long (max {MAX_COMMENT_CHARS} characters)"
    lowered = text.lower()
    if any(word in lowered for word in _BLOCKED_WORDS):
        return "This comment contains language we do not publish"
    if _URL_RE.search(text) and len(text) < 40:
        return "Links alone look like spam — please add context"
    if _REPEAT_RE.search(text):
        return "This comment looks like spam"
    return None


async def _feed_visible_problem(db: AsyncSession, problem_id) -> Problem | None:
    """Fetch a problem only when it is feed-visible (gating, not just existence)."""
    problem = await db.get(Problem, problem_id)
    if problem is None or problem.status not in FEED_VISIBLE_STATUSES:
        return None
    return problem


async def _matched_universities(db: AsyncSession, problem_ids: list) -> dict[str, str | None]:
    """Best (lowest-rank) OFFERED/ACCEPTED university name per problem id."""
    if not problem_ids:
        return {}
    rows = (
        await db.execute(
            select(RouteAssignment.problem_id, University.name)
            .join(University, RouteAssignment.university_id == University.university_id)
            .where(
                RouteAssignment.problem_id.in_(problem_ids),
                RouteAssignment.status.in_(["OFFERED", "ACCEPTED"]),
            )
            .order_by(RouteAssignment.problem_id, RouteAssignment.rank_order)
        )
    ).all()
    matched: dict[str, str | None] = {}
    for problem_id, name in rows:
        key = str(problem_id)
        if key not in matched:
            matched[key] = name
    return matched


async def _clean_media_summary(db: AsyncSession, submission_ids: list) -> dict[str, dict]:
    """Per-submission clean-evidence summary (cover photo, counts)."""
    summary: dict[str, dict] = {}
    if not submission_ids:
        return summary
    rows = (
        await db.execute(
            select(MediaAsset.submission_id, MediaAsset.asset_id, MediaAsset.kind)
            .where(
                MediaAsset.submission_id.in_(submission_ids),
                MediaAsset.moderation_status == "clean",
            )
            .order_by(MediaAsset.created_at)
        )
    ).all()
    for submission_id, asset_id, kind in rows:
        key = str(submission_id)
        entry = summary.setdefault(key, {"cover_asset_id": None, "photo_count": 0, "has_audio": False})
        if kind == "photo":
            entry["photo_count"] += 1
            if entry["cover_asset_id"] is None:
                entry["cover_asset_id"] = str(asset_id)
        elif kind == "audio":
            entry["has_audio"] = True
    return summary


@router.get("")
async def list_feed(
    skip: int = 0,
    limit: int = 12,
    category: str | None = None,
    district: str | None = None,
    status: str | None = None,
    sort: str = "recent",
    voter: str | None = None,
    near_lat: float | None = None,
    near_lng: float | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
):
    """Public report feed, newest first (or most-supported with sort=top).

    Mirrors the review-queue contract ({items, total, skip, limit, has_more})
    so pagination behaves the same everywhere. `voter` is the anonymous
    localStorage token used only to flag `liked_by_me`; signed-in callers are
    recognized from their bearer token instead. `status` accepts the UI
    buckets ingested/routed/in_progress/resolved. `near_lat/near_lng` surface
    nearby reports first without ever returning coordinates.
    """
    limit = max(1, min(limit, 50))
    skip = max(0, skip)
    me_too_counts = (
        select(ReportLike.problem_id.label("problem_id"), func.count(ReportLike.like_id).label("like_count"))
        .group_by(ReportLike.problem_id)
        .subquery()
    )
    confirm_counts = (
        select(ReportConfirmation.problem_id.label("problem_id"), func.count(ReportConfirmation.confirmation_id).label("confirm_count"))
        .group_by(ReportConfirmation.problem_id)
        .subquery()
    )
    comment_counts = (
        select(ReportComment.problem_id.label("problem_id"), func.count(ReportComment.comment_id).label("comment_count"))
        .where(ReportComment.status == "visible")
        .group_by(ReportComment.problem_id)
        .subquery()
    )
    me_too_col = func.coalesce(me_too_counts.c.like_count, 0)
    confirm_col = func.coalesce(confirm_counts.c.confirm_count, 0)
    comment_col = func.coalesce(comment_counts.c.comment_count, 0)
    base_filter = Problem.status.in_(FEED_VISIBLE_STATUSES)

    count_stmt = (
        select(func.count(Problem.problem_id))
        .join(Submission, Problem.submission_id == Submission.submission_id)
        .where(base_filter)
    )
    stmt = (
        select(Problem, Submission, me_too_col.label("me_too_count"), confirm_col.label("confirm_count"), comment_col.label("comment_count"))
        .join(Submission, Problem.submission_id == Submission.submission_id)
        .outerjoin(me_too_counts, me_too_counts.c.problem_id == Problem.problem_id)
        .outerjoin(confirm_counts, confirm_counts.c.problem_id == Problem.problem_id)
        .outerjoin(comment_counts, comment_counts.c.problem_id == Problem.problem_id)
        .where(base_filter)
    )
    if category:
        count_stmt = count_stmt.where(Problem.category == category)
        stmt = stmt.where(Problem.category == category)
    if district:
        count_stmt = count_stmt.where(Submission.geo_district == district)
        stmt = stmt.where(Submission.geo_district == district)
    if status:
        bucket = STATUS_BUCKETS.get(str(status).lower())
        if bucket is None:
            raise HTTPException(
                status_code=422,
                detail="Invalid status filter: expected ingested, routed, in_progress or resolved",
            )
        count_stmt = count_stmt.where(Problem.status.in_(bucket))
        stmt = stmt.where(Problem.status.in_(bucket))
    near_me = near_lat is not None and near_lng is not None
    if sort == "top":
        stmt = stmt.order_by((me_too_col + confirm_col).desc(), Problem.created_at.desc())
    elif near_me:
        distance = (
            (Submission.geo_lat - float(near_lat)) * (Submission.geo_lat - float(near_lat))
            + (Submission.geo_lng - float(near_lng)) * (Submission.geo_lng - float(near_lng))
        )
        stmt = stmt.order_by(
            case((or_(Submission.geo_lat.is_(None), Submission.geo_lng.is_(None)), 1), else_=0),
            distance,
            Problem.created_at.desc(),
        )
    else:
        stmt = stmt.order_by(Problem.created_at.desc())

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt.offset(skip).limit(limit))).all()

    voter_key = _resolve_voter(user, voter)
    page_ids = [problem.problem_id for problem, _, _, _, _ in rows]
    me_too_ids: set[str] = set()
    confirmed_ids: set[str] = set()
    if voter_key and page_ids:
        me_rows = (
            await db.execute(
                select(ReportLike.problem_id).where(
                    ReportLike.voter_key == voter_key,
                    ReportLike.problem_id.in_(page_ids),
                )
            )
        ).all()
        me_too_ids = {str(row[0]) for row in me_rows}
        confirm_rows = (
            await db.execute(
                select(ReportConfirmation.problem_id).where(
                    ReportConfirmation.voter_key == voter_key,
                    ReportConfirmation.problem_id.in_(page_ids),
                )
            )
        ).all()
        confirmed_ids = {str(row[0]) for row in confirm_rows}

    matched = await _matched_universities(db, page_ids)
    media = await _clean_media_summary(db, [s.submission_id for _, s, _, _, _ in rows])

    items = []
    for problem, submission, me_too_count, confirm_count, comment_count in rows:
        pid = str(problem.problem_id)
        university = matched.get(pid)
        items.append(
            {
                "problem_id": pid,
                "tracking_token": submission.tracking_token,
                "title": problem.title,
                "summary": problem.summary,
                "category": problem.category,
                "severity": problem.severity_score,
                "status": problem.status,
                "district": submission.geo_district,
                "block": submission.geo_block,
                "reporter": _public_reporter(submission.reporter_name),
                "created_at": problem.created_at.isoformat() if problem.created_at else None,
                # Engagement (civic vocabulary first; legacy aliases kept).
                "me_too_count": int(me_too_count or 0),
                "confirm_count": int(confirm_count or 0),
                "comment_count": int(comment_count or 0),
                "me_too_by_me": pid in me_too_ids,
                "confirmed_by_me": pid in confirmed_ids,
                "like_count": int(me_too_count or 0),
                "liked_by_me": pid in me_too_ids,
                # Clean-evidence flags only — never pending/flagged.
                "cover_asset_id": (media.get(str(submission.submission_id)) or {}).get("cover_asset_id"),
                "photo_count": ((media.get(str(submission.submission_id)) or {}).get("photo_count")) or 0,
                "has_audio": bool((media.get(str(submission.submission_id)) or {}).get("has_audio")),
                # Trust strip inputs.
                "matched_university": university,
                "officer_verified": problem.status in OFFICER_VERIFIED_STATUSES or university is not None,
            }
        )
    return {"items": items, "total": total, "skip": skip, "limit": limit, "has_more": skip + len(items) < total}


@router.get("/{problem_id}/media")
async def feed_media_list(problem_id: str, db: AsyncSession = Depends(get_db)):
    """Clean-evidence listing for one feed-visible report (public)."""
    problem = await _feed_visible_problem(db, parse_uuid(problem_id, "problem_id"))
    if problem is None:
        raise HTTPException(status_code=404, detail="Report not found")
    rows = (
        await db.execute(
            select(MediaAsset.asset_id, MediaAsset.kind)
            .where(
                MediaAsset.submission_id == problem.submission_id,
                MediaAsset.moderation_status == "clean",
            )
            .order_by(MediaAsset.created_at)
        )
    ).all()
    return {
        "problem_id": str(problem.problem_id),
        "assets": [{"asset_id": str(asset_id), "kind": kind} for asset_id, kind in rows],
    }


@router.get("/media/{asset_id}")
async def serve_feed_media(asset_id: str, db: AsyncSession = Depends(get_db)):
    """Serve one clean photo/audio note (public). Pending/flagged → 404 so
    moderation state cannot be probed from the public feed."""
    asset = await db.get(MediaAsset, parse_uuid(asset_id, "asset_id"))
    if asset is None or asset.moderation_status != "clean":
        raise HTTPException(status_code=404, detail="Evidence not found")
    problem = (
        await db.execute(select(Problem).where(Problem.submission_id == asset.submission_id).limit(1))
    ).scalars().first()
    if problem is None or problem.status not in FEED_VISIBLE_STATUSES:
        raise HTTPException(status_code=404, detail="Evidence not found")
    url = asset.storage_url or ""
    path = Path(url)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file is no longer on this host")
    from app.config import get_settings

    allowed = [Path(get_settings().MEDIA_DIR).resolve(), Path("/app/output").resolve()]
    try:
        resolved = path.resolve()
    except Exception:
        raise HTTPException(status_code=404, detail="Evidence file is no longer on this host")
    if not any(str(resolved).startswith(str(base)) for base in allowed):
        raise HTTPException(status_code=404, detail="Evidence not found")
    media_type = "image/webp" if asset.kind == "photo" else "audio/webm"
    return FileResponse(resolved, media_type=media_type, filename=f"{asset.kind}-{asset.asset_id}")


@router.get("/{problem_id}/comments")
async def list_comments(problem_id: str, db: AsyncSession = Depends(get_db)):
    """Visible comment thread for one feed-visible report (public read)."""
    problem = await _feed_visible_problem(db, parse_uuid(problem_id, "problem_id"))
    if problem is None:
        raise HTTPException(status_code=404, detail="Report not found")
    rows = (
        await db.execute(
            select(ReportComment)
            .where(ReportComment.problem_id == problem.problem_id, ReportComment.status == "visible")
            .order_by(ReportComment.created_at)
            .limit(100)
        )
    ).scalars().all()
    return {
        "problem_id": str(problem.problem_id),
        "comments": [
            {
                "comment_id": str(c.comment_id),
                "author": _public_reporter(c.author_name),
                "body": c.body,
                "parent_id": str(c.parent_id) if c.parent_id else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ],
    }


@router.post("/{problem_id}/comments")
async def post_comment(
    problem_id: str,
    payload: CommentRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    _limited: bool = Depends(rate_limit(limit=30, window_seconds=60)),
):
    """Post to a report thread. Citizen accounts only; moderated server-side."""
    _require_citizen(user)
    problem = await _feed_visible_problem(db, parse_uuid(problem_id, "problem_id"))
    if problem is None:
        raise HTTPException(status_code=404, detail="Report not found")
    rejection = _moderate_comment(payload.body)
    if rejection is not None:
        raise HTTPException(status_code=422, detail=rejection)
    parent_uuid = None
    if payload.parent_id:
        parent_uuid = parse_uuid(payload.parent_id, "parent_id")
        parent = await db.get(ReportComment, parent_uuid)
        if parent is None or parent.problem_id != problem.problem_id or parent.status != "visible":
            raise HTTPException(status_code=422, detail="Replies must target a visible comment on this report")
    display = (user.get("display_name") or user.get("user_id") or "Citizen")
    comment = ReportComment(
        problem_id=problem.problem_id,
        author_user_id=str(user.get("user_id")),
        author_name=str(display)[:255],
        body=payload.body.strip(),
        parent_id=parent_uuid,
        status="visible",
    )
    db.add(comment)
    await db.flush()
    await db.commit()
    return {
        "comment_id": str(comment.comment_id),
        "author": _public_reporter(comment.author_name),
        "body": comment.body,
        "parent_id": str(comment.parent_id) if comment.parent_id else None,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.post("/{problem_id}/me-too")
async def add_me_too(
    problem_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    _limited: bool = Depends(rate_limit(limit=30, window_seconds=60)),
):
    """Record "I experience this too". One per citizen (unique constraint);
    repeats are a 409, never a double count. At quorum the problem severity
    is bumped so crowd volume genuinely feeds triage priority."""
    _require_citizen(user)
    problem = await _feed_visible_problem(db, parse_uuid(problem_id, "problem_id"))
    if problem is None:
        raise HTTPException(status_code=404, detail="Report not found")
    voter = _account_voter(user)
    existing = (
        await db.execute(
            select(ReportLike).where(
                ReportLike.problem_id == problem.problem_id,
                ReportLike.voter_key == voter,
            ).limit(1)
        )
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already marked 'me too' on this report")
    db.add(ReportLike(problem_id=problem.problem_id, voter_key=voter))
    await db.flush()
    me_too_count = (
        await db.execute(select(func.count(ReportLike.like_id)).where(ReportLike.problem_id == problem.problem_id))
    ).scalar_one()
    boosted = False
    if int(me_too_count or 0) >= ME_TOO_SEVERITY_QUORUM and (problem.severity_score or 0) < 5:
        problem.severity_score = min(5, (problem.severity_score or 3) + 1)
        boosted = True
        db.add(make_audit(
            entity_type="problem", entity_id=str(problem.problem_id), action="CROWD_SEVERITY_BOOST",
            actor_id=str(user.get("user_id")), actor_role=user.get("role") or "citizen",
            after={"me_too_count": int(me_too_count or 0), "severity": problem.severity_score},
        ))
    await db.commit()
    return {"me_too": True, "me_too_count": int(me_too_count or 0), "severity_boosted": boosted}


@router.delete("/{problem_id}/me-too")
async def remove_me_too(
    problem_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Withdraw a me-too (no severity rollback — boosts are audit-logged facts)."""
    _require_citizen(user)
    problem = await _feed_visible_problem(db, parse_uuid(problem_id, "problem_id"))
    if problem is None:
        raise HTTPException(status_code=404, detail="Report not found")
    voter = _account_voter(user)
    existing = (
        await db.execute(
            select(ReportLike).where(
                ReportLike.problem_id == problem.problem_id,
                ReportLike.voter_key == voter,
            ).limit(1)
        )
    ).scalars().first()
    if existing is None:
        raise HTTPException(status_code=404, detail="No 'me too' to withdraw on this report")
    await db.delete(existing)
    await db.flush()
    me_too_count = (
        await db.execute(select(func.count(ReportLike.like_id)).where(ReportLike.problem_id == problem.problem_id))
    ).scalar_one()
    await db.commit()
    return {"me_too": False, "me_too_count": int(me_too_count or 0)}


@router.post("/{problem_id}/confirm")
async def add_confirm(
    problem_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    _limited: bool = Depends(rate_limit(limit=30, window_seconds=60)),
):
    """Record firsthand nearby verification. One per citizen; never touches
    severity (verification weight ≠ experience weight). At quorum the report
    is audit-marked community-corroborated for dedup confidence."""
    _require_citizen(user)
    problem = await _feed_visible_problem(db, parse_uuid(problem_id, "problem_id"))
    if problem is None:
        raise HTTPException(status_code=404, detail="Report not found")
    voter = _account_voter(user)
    existing = (
        await db.execute(
            select(ReportConfirmation).where(
                ReportConfirmation.problem_id == problem.problem_id,
                ReportConfirmation.voter_key == voter,
            ).limit(1)
        )
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already confirmed this report")
    db.add(ReportConfirmation(problem_id=problem.problem_id, voter_key=voter))
    await db.flush()
    confirm_count = (
        await db.execute(select(func.count(ReportConfirmation.confirmation_id)).where(ReportConfirmation.problem_id == problem.problem_id))
    ).scalar_one()
    corroborated = int(confirm_count or 0) >= CONFIRM_CORROBORATED_QUORUM
    if corroborated:
        db.add(make_audit(
            entity_type="problem", entity_id=str(problem.problem_id), action="CROWD_CONFIRMED",
            actor_id=str(user.get("user_id")), actor_role=user.get("role") or "citizen",
            after={"confirm_count": int(confirm_count or 0)},
        ))
    await db.commit()
    return {"confirmed": True, "confirm_count": int(confirm_count or 0), "corroborated": corroborated}


@router.post("/{problem_id}/like")
async def toggle_like(
    problem_id: str,
    payload: LikeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_current_user_optional),
    _limited: bool = Depends(rate_limit(limit=30, window_seconds=60)),
):
    """Legacy idempotent like/unlike toggle (anonymous voter UUID or account).

    Kept for backwards compatibility; new clients should use the civic
    me-too / confirm endpoints above. Anonymous callers pass their
    localStorage voter UUID; signed-in callers are keyed to their account so
    likes follow them across devices.
    """
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
