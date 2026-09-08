"""Casefile routes: full submission payload for review workspaces (P2/P3/P4).

- GET /officer/problems/{id}            full officer review detail
- GET /officer/universities              override picker list
- GET /officer/problems/{id}/updates     officer-visible update log
- GET /university/assignments/{id}       full university casefile (org-checked)
- GET+POST /university/teams/{id}/updates  progress updates (P4)
- GET /media/{asset_id}                  evidence bytes (role/org-checked)

Media serving: local-mirror files stream via FileResponse (contained under
configured output dirs only); s3:// references 302 to a presigned URL.
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, parse_uuid, require_role
from app.db.models import (
    MediaAsset,
    Milestone,
    Problem,
    ProjectTeam,
    ProjectUpdate,
    RouteAssignment,
    Submission,
    University,
)
from app.services import storage as storage_svc
from app.services.audit import make_audit
from app.services.events import publish_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["casefile"])


def _media_list(assets) -> list[dict]:
    return [
        {
            "asset_id": str(a.asset_id),
            "kind": a.kind,
            "size_bytes": a.size_bytes,
            "moderation_status": a.moderation_status,
            "transcript": a.transcript,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in assets
    ]


async def _assets_for(db: AsyncSession, submission_id) -> list:
    result = await db.execute(
        select(MediaAsset)
        .where(MediaAsset.submission_id == submission_id)
        .order_by(MediaAsset.created_at)
    )
    return result.scalars().all()


async def _assignments_for(db: AsyncSession, problem_id) -> list[dict]:
    result = await db.execute(
        select(RouteAssignment)
        .options(selectinload(RouteAssignment.university))
        .where(RouteAssignment.problem_id == problem_id)
        .order_by(RouteAssignment.rank_order)
    )
    out = []
    for a in result.scalars().all():
        out.append(
            {
                "assignment_id": str(a.assignment_id),
                "university_id": str(a.university_id),
                "university_name": a.university.name if a.university else None,
                "rank_order": a.rank_order,
                "match_score": a.match_score,
                "score_breakdown": a.score_breakdown,
                "sla_deadline": a.sla_deadline.isoformat() if a.sla_deadline else None,
                "status": a.status,
                "responded_at": a.responded_at.isoformat() if a.responded_at else None,
            }
        )
    return out


def _sla_hours(assignments: list[dict]) -> int | None:
    from datetime import datetime, timezone

    deadlines = [a["sla_deadline"] for a in assignments if a.get("sla_deadline")]
    if not deadlines:
        return None
    try:
        soonest = min(datetime.fromisoformat(d) for d in deadlines)
        if soonest.tzinfo is None:
            soonest = soonest.replace(tzinfo=timezone.utc)
        return max(0, int((soonest - datetime.now(timezone.utc)).total_seconds() // 3600))
    except Exception:
        return None


def _milestone_json(m: Milestone) -> dict:
    return {
        "milestone_id": str(m.milestone_id),
        "milestone_num": m.milestone_num,
        "title": m.title,
        "status": m.status,
        "evidence_url": m.evidence_url,
        "verified_at": m.verified_at.isoformat() if m.verified_at else None,
        "due_date": m.due_date.isoformat() if m.due_date else None,
    }


async def _milestones_for_team(db: AsyncSession, team_id) -> list[dict]:
    rows = (
        await db.execute(select(Milestone).where(Milestone.team_id == team_id).order_by(Milestone.milestone_num))
    ).scalars().all()
    return [_milestone_json(m) for m in rows]


async def _updates_for_problem(db: AsyncSession, problem_id) -> list[dict]:
    result = await db.execute(
        select(ProjectUpdate).where(ProjectUpdate.problem_id == problem_id).order_by(ProjectUpdate.created_at)
    )
    return [_update_json(u) for u in result.scalars().all()]


def _update_json(u: ProjectUpdate) -> dict:
    return {
        "update_id": str(u.update_id),
        "team_id": str(u.team_id),
        "author_name": u.author_name,
        "note": u.note,
        "milestone": u.milestone,
        "photo_urls": u.photo_urls or [],
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


async def _team_for_university(db: AsyncSession, team_id, organization_id: str) -> ProjectTeam:
    team = await db.get(ProjectTeam, parse_uuid(team_id, "team_id"))
    if not team:
        raise HTTPException(status_code=404, detail="Project team not found")
    if str(team.university_id) != organization_id:
        raise HTTPException(status_code=403, detail="This project belongs to another university")
    return team


@router.get("/officer/problems/{problem_id}")
async def officer_problem_detail(
    problem_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))
):
    problem = await db.get(Problem, parse_uuid(problem_id, "problem_id"))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    submission = await db.get(Submission, problem.submission_id)
    assignments = await _assignments_for(db, problem.problem_id)
    media = await _assets_for(db, problem.submission_id) if submission else []
    updates = await _updates_for_problem(db, problem.problem_id)
    # WP-5: accepted problems carry their live team + milestone pipeline.
    milestones: list[dict] = []
    team_rows = (
        await db.execute(select(ProjectTeam).where(ProjectTeam.problem_id == problem.problem_id).limit(1))
    ).scalars().first()
    if team_rows is not None:
        milestones = await _milestones_for_team(db, team_rows.team_id)
    return {
        "problem_id": str(problem.problem_id),
        "title": problem.title,
        "summary": problem.summary,
        "category": problem.category,
        "severity": problem.severity_score,
        "confidence": problem.confidence_score,
        "status": problem.status,
        "is_duplicate": problem.is_duplicate,
        "created_at": problem.created_at.isoformat() if problem.created_at else None,
        "submission": (
            {
                "submission_id": str(submission.submission_id),
                "raw_text": submission.raw_text,
                "language_pref": submission.language_pref,
                "district": submission.geo_district,
                "block": submission.geo_block,
                "geo_lat": submission.geo_lat,
                "geo_lng": submission.geo_lng,
                "geo_source": submission.geo_source,
                "tracking_token": submission.tracking_token,
                "reporter_name": submission.reporter_name,
                "submitted_at": submission.created_at.isoformat() if submission.created_at else None,
            }
            if submission
            else None
        ),
        "media": _media_list(media),
        "assignments": assignments,
        "sla_hours_remaining": _sla_hours(assignments),
        "updates": updates,
        "milestones": milestones,
    }


@router.get("/officer/universities")
async def officer_university_list(
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))
):
    result = await db.execute(select(University).order_by(University.name))
    return [
        {"university_id": str(u.university_id), "name": u.name, "district": u.district}
        for u in result.scalars().all()
    ]


@router.get("/officer/problems/{problem_id}/updates")
async def officer_problem_updates(
    problem_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))
):
    problem = await db.get(Problem, parse_uuid(problem_id, "problem_id"))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return await _updates_for_problem(db, problem.problem_id)


@router.get("/university/assignments/{assignment_id}")
async def university_assignment_detail(
    assignment_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))
):
    organization_id = user.get("organization_id")
    assignment = await db.get(RouteAssignment, parse_uuid(assignment_id, "assignment_id"))
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if str(assignment.university_id) != organization_id:
        raise HTTPException(status_code=403, detail="This assignment belongs to another university")
    problem = await db.get(Problem, assignment.problem_id)
    submission = await db.get(Submission, problem.submission_id) if problem else None
    university = await db.get(University, assignment.university_id)
    media = await _assets_for(db, problem.submission_id) if problem and submission else []
    team = (
        await db.execute(select(ProjectTeam).where(ProjectTeam.assignment_id == assignment.assignment_id).limit(1))
    ).scalars().first()
    milestones = await _milestones_for_team(db, team.team_id) if team else []
    return {
        "assignment_id": str(assignment.assignment_id),
        "status": assignment.status,
        "match_score": assignment.match_score,
        "score_breakdown": assignment.score_breakdown,
        "sla_deadline": assignment.sla_deadline.isoformat() if assignment.sla_deadline else None,
        "responded_at": assignment.responded_at.isoformat() if assignment.responded_at else None,
        "problem": (
            {
                "problem_id": str(problem.problem_id),
                "title": problem.title,
                "summary": problem.summary,
                "category": problem.category,
                "severity": problem.severity_score,
                "status": problem.status,
                "tracking_token": submission.tracking_token if submission else None,
            }
            if problem
            else None
        ),
        "submission": (
            {
                "raw_text": submission.raw_text,
                "language_pref": submission.language_pref,
                "district": submission.geo_district,
                "block": submission.geo_block,
                "geo_lat": submission.geo_lat,
                "geo_lng": submission.geo_lng,
                "geo_source": submission.geo_source,
            }
            if submission
            else None
        ),
        "media": _media_list(media),
        "assigned_department": (university.domain_specializations or [None])[0] if university else None,
        "specializations": university.domain_specializations if university else [],
        "team": (
            {
                "team_id": str(team.team_id),
                "faculty_mentor_name": team.faculty_mentor_name,
                "student_lead_name": team.student_lead_name,
                "proposal_title": team.proposal_title,
                "status": team.status,
            }
            if team
            else None
        ),
        "milestones": milestones,
        "updates": await _updates_for_problem(db, assignment.problem_id),
    }


class UpdateRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    milestone: str | None = Field(default=None, pattern="^(M1|M2|M3|general)$")


@router.post("/university/teams/{team_id}/updates", status_code=status.HTTP_201_CREATED)
async def post_project_update(
    team_id: str,
    note: str = Form(...),
    milestone: str | None = Form(None),
    photos: list[UploadFile] = File(default=[]),
    background: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("university")),
):
    from app.config import get_settings

    organization_id = user.get("organization_id")
    if not organization_id:
        raise HTTPException(status_code=403, detail="University account is not linked to a workspace")
    team = await _team_for_university(db, team_id, organization_id)
    note = (note or "").strip()
    if not note:
        raise HTTPException(status_code=422, detail="Progress note cannot be blank")
    if len(note) > 2000:
        raise HTTPException(status_code=422, detail="Progress note is too long (max 2000 characters)")
    if milestone and milestone not in {"M1", "M2", "M3", "general"}:
        raise HTTPException(status_code=422, detail="Milestone must be M1, M2, M3, or general")
    photo_urls: list[str] = []
    for upload in (photos or [])[:3]:
        blob = await upload.read()
        if not blob:
            continue
        if len(blob) > get_settings().MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Photo exceeds the maximum allowed size of 5 MB")
        try:
            photo_urls.append(
                storage_svc.put_bytes(
                    storage_svc.object_key(f"teams/{team.team_id}/updates", upload.filename or "fieldwork"),
                    blob,
                    "image/webp",
                )
            )
        except Exception:
            logger.warning("Update photo store failed for team %s", team.team_id, exc_info=True)
    update = ProjectUpdate(
        team_id=team.team_id,
        problem_id=team.problem_id,
        author_user_id=user.get("user_id"),
        author_name=None,
        note=note,
        milestone=milestone or "general",
        photo_urls=photo_urls,
        notified=False,
    )
    db.add(update)
    await db.flush()
    university = await db.get(University, team.university_id)
    if university and not update.author_name:
        update.author_name = university.name
    db.add(
        make_audit(
            entity_type="project_team",
            entity_id=str(team.team_id),
            action="PROJECT_UPDATE",
            actor_id=user.get("user_id") or "university",
            actor_role=user.get("role") or "university",
            after={"update_id": str(update.update_id), "milestone": update.milestone},
        )
    )
    await db.commit()
    # Fan out: citizen tracker (by token) + officer visibility via audit.
    # Reporter mail/SMS goes to opt-in contacts (plaintext by necessity);
    # hashed citizen identity is never reversed for delivery.
    try:
        problem = await db.get(Problem, team.problem_id) if team.problem_id else None
        submission = await db.get(Submission, problem.submission_id) if problem else None
        if submission and submission.tracking_token:
            await publish_event(
                f"track:{submission.tracking_token}",
                {"type": "project.update", "data": _update_json(update)},
            )
        logger.info(
            "Project update %s posted for team %s",
            update.update_id,
            team.team_id,
        )
        if submission is not None and submission.notify_consent and (submission.contact_email or submission.contact_phone):
            from app.services import notify_reporter as notify_mod

            background.add_task(
                notify_mod.notify_reporter,
                submission.contact_email, submission.contact_phone,
                kind="update", tracking_token=submission.tracking_token or "",
                title=problem.title if problem else "",
                detail=f"{update.author_name or 'University team'} ({update.milestone}): {note[:200]}",
            )
            update.notified = True
        else:
            update.notified = False
        await db.commit()
    except Exception:
        logger.warning("Update fan-out failed for team %s", team.team_id, exc_info=True)
    return _update_json(update)


@router.get("/university/teams/{team_id}/updates")
async def list_team_updates(
    team_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))
):
    organization_id = user.get("organization_id")
    if not organization_id:
        raise HTTPException(status_code=403, detail="University account is not linked to a workspace")
    team = await _team_for_university(db, team_id, organization_id)
    result = await db.execute(
        select(ProjectUpdate).where(ProjectUpdate.team_id == team.team_id).order_by(ProjectUpdate.created_at)
    )
    return [_update_json(u) for u in result.scalars().all()]


@router.post("/university/milestones/{milestone_id}/submit")
async def submit_milestone(
    milestone_id: str,
    note: str = Form(""),
    evidence: UploadFile | None = File(None),
    background: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("university")),
):
    """WP-5: university submits milestone evidence for officer verification.

    Only PENDING/REJECTED milestones accept submissions. Evidence is stored
    via object storage (local mirror in dev) and the milestone flips to
    SUBMITTED; officers are notified on the role channel.
    """
    from app.config import get_settings

    organization_id = user.get("organization_id")
    if not organization_id:
        raise HTTPException(status_code=403, detail="University account is not linked to a workspace")
    milestone = await db.get(Milestone, parse_uuid(milestone_id, "milestone_id"))
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    team = await db.get(ProjectTeam, milestone.team_id) if milestone.team_id else None
    if not team:
        raise HTTPException(status_code=404, detail="Milestone has no project team")
    if str(team.university_id) != organization_id:
        raise HTTPException(status_code=403, detail="This project belongs to another university")
    if milestone.status not in {"PENDING", "REJECTED"}:
        raise HTTPException(status_code=409, detail="This milestone is already submitted or verified")
    evidence_url = milestone.evidence_url
    if evidence is not None:
        blob = await evidence.read()
        if blob:
            if len(blob) > get_settings().MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Evidence exceeds the maximum allowed size of 5 MB")
            try:
                evidence_url = storage_svc.put_bytes(
                    storage_svc.object_key(
                        f"teams/{team.team_id}/milestones/m{milestone.milestone_num or 'x'}",
                        evidence.filename or "evidence",
                    ),
                    blob,
                    evidence.content_type or "application/octet-stream",
                )
            except Exception:
                logger.warning("Milestone evidence store failed for %s", milestone.milestone_id, exc_info=True)
                raise HTTPException(status_code=502, detail="Could not store the evidence file")
    milestone.evidence_url = evidence_url
    milestone.status = "SUBMITTED"
    db.add(
        make_audit(
            entity_type="milestone",
            entity_id=str(milestone.milestone_id),
            action="MILESTONE_SUBMITTED",
            actor_id=user.get("user_id") or "university",
            actor_role=user.get("role") or "university",
            after={
                "team_id": str(team.team_id),
                "problem_id": str(team.problem_id) if team.problem_id else None,
                "note": (note or "").strip()[:500],
            },
        )
    )
    await db.commit()
    try:
        payload = _milestone_json(milestone)
        await publish_event(f"org:{team.university_id}", {"type": "milestone.submitted", "data": payload})
        await publish_event("role:officer", {"type": "milestone.submitted", "data": payload})
    except Exception:
        logger.warning("SSE publish failed for milestone %s", milestone.milestone_id, exc_info=True)
    # Reporter notification (opt-in contacts only, backgrounded).
    try:
        problem = await db.get(Problem, team.problem_id) if team.problem_id else None
        submission = await db.get(Submission, problem.submission_id) if problem else None
        if submission is not None and submission.notify_consent and (submission.contact_email or submission.contact_phone):
            from app.services import notify_reporter as notify_mod

            background.add_task(
                notify_mod.notify_reporter, submission.contact_email, submission.contact_phone,
                kind="milestone", tracking_token=submission.tracking_token or "",
                title=problem.title if problem else "",
                detail=f"Milestone {milestone.milestone_num or ''} evidence submitted for verification.".strip(),
            )
    except Exception:
        logger.warning("Milestone notify failed for %s", milestone.milestone_id, exc_info=True)
    return payload


class TeamPatch(BaseModel):
    faculty_mentor_name: str | None = Field(default=None, min_length=1, max_length=255)
    student_lead_name: str | None = Field(default=None, min_length=1, max_length=255)
    proposal_title: str | None = Field(default=None, max_length=255)
    team_members: dict | None = None


@router.patch("/university/teams/{team_id}")
async def update_team(
    team_id: str, payload: TeamPatch, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))
):
    """WP-4: fill in team details after auto-creation on ACCEPT (org-scoped)."""
    organization_id = user.get("organization_id")
    if not organization_id:
        raise HTTPException(status_code=403, detail="University account is not linked to a workspace")
    team = await _team_for_university(db, team_id, organization_id)
    updates = payload.model_dump(exclude_unset=True)
    if "faculty_mentor_name" in updates:
        team.faculty_mentor_name = (updates["faculty_mentor_name"] or "").strip()[:255] or team.faculty_mentor_name
    if "student_lead_name" in updates:
        team.student_lead_name = (updates["student_lead_name"] or "").strip()[:255] or team.student_lead_name
    if "proposal_title" in updates:
        team.proposal_title = (updates["proposal_title"] or "").strip()[:255] or None
    if "team_members" in updates:
        team.team_members = updates["team_members"]
    db.add(
        make_audit(
            entity_type="project_team", entity_id=str(team.team_id), action="TEAM_UPDATED",
            actor_id=user.get("user_id") or "university", actor_role=user.get("role") or "university",
            after={"faculty_mentor_name": team.faculty_mentor_name, "student_lead_name": team.student_lead_name},
        )
    )
    await db.commit()
    return {"status": "updated", "team_id": str(team.team_id)}


@router.get("/media/{asset_id}")
async def serve_media(
    asset_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin", "university"))
):
    asset = await db.get(MediaAsset, parse_uuid(asset_id, "asset_id"))
    if not asset:
        raise HTTPException(status_code=404, detail="Evidence not found")
    # WP-10: flagged evidence stays hidden until an officer clears it.
    if asset.moderation_status == "flagged" and (user.get("role") or "").lower() not in {"officer", "admin"}:
        raise HTTPException(status_code=403, detail="This evidence is under moderation review")
    if (user.get("role") or "").lower() == "university":
        # Universities see only evidence routed to their own organization.
        rows = await db.execute(
            select(RouteAssignment.university_id).where(RouteAssignment.problem_id.in_(
                select(Problem.problem_id).where(Problem.submission_id == asset.submission_id)
            ))
        )
        orgs = {str(r[0]) for r in rows.all()}
        if user.get("organization_id") not in orgs:
            raise HTTPException(status_code=403, detail="This evidence belongs to another university")
    url = asset.storage_url or ""
    if url.startswith("s3://"):
        try:
            key = url.split("/", 3)[3]
            return RedirectResponse(storage_svc.presigned_get(key), status_code=302)
        except Exception:
            raise HTTPException(status_code=502, detail="Could not sign the download URL")
    path = Path(url)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file is no longer on this host")
    # Contain local serving to configured output dirs (no path traversal).
    from app.config import get_settings

    allowed = [Path(get_settings().MEDIA_DIR).resolve(), Path("/app/output").resolve()]
    try:
        resolved = path.resolve()
    except Exception:
        raise HTTPException(status_code=404, detail="Evidence file is no longer on this host")
    if not any(str(resolved).startswith(str(base)) for base in allowed):
        raise HTTPException(status_code=403, detail="Evidence is not servable from this host")
    media_type = "image/webp" if asset.kind == "photo" else "audio/webm"
    return FileResponse(resolved, media_type=media_type, filename=f"{asset.kind}-{asset.asset_id}")
