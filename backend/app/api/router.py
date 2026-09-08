"""HTTP API contract consumed by the Nitivayu web application."""

from datetime import datetime, timedelta, timezone
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import create_access_token, get_current_user, get_current_user_optional, get_db, require_role, workspace_of
from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.batch_triage import router as batch_triage_router
from app.api.routes.events import router as events_router
from app.api.routes.meta import router as meta_router
from app.api.routes.admin_exports import router as admin_exports_router
from app.api.routes.citizen import router as citizen_router
from app.api.routes.feed import router as feed_router
from app.db.models import AuditLog, FundingLink, Industry, MediaAsset, Milestone, Problem, ProjectTeam, RouteAssignment, Submission, University
from app.services import auth as auth_svc
from app.services import redis_client as redis_mod
from app.services import storage as storage_svc
from app.services.audit import make_audit
from app.services.events import publish_event
from app.services.outputs import append_audit, write_triage_csv
from app.services.rate_limit import rate_limit
from app.config import get_settings
from temporalio.client import Client

logger = logging.getLogger(__name__)

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(batch_triage_router)
api_router.include_router(events_router)
api_router.include_router(admin_router)
api_router.include_router(admin_exports_router)
api_router.include_router(meta_router)
api_router.include_router(citizen_router)
api_router.include_router(feed_router)

from app.api.routes.casefile import router as casefile_router  # noqa: E402

api_router.include_router(casefile_router)

# Officer decisions use uppercase API values; the triage workflow signal
# contract uses lowercase values. OVERRIDE still routes the problem onward.
WORKFLOW_DECISION_SIGNALS = {"APPROVE": "approve", "REJECT": "reject", "OVERRIDE": "approve"}
OFFICER_SIGNAL_NAME = "officer_approval_signal"
UNIVERSITY_SIGNAL_NAME = "university_acceptance_signal"


def _sla_workflow_id(assignment_id: object) -> str:
    return f"sla-{assignment_id}"


async def _start_sla_workflow(assignment) -> None:
    """WP-4: start the UniversitySLAWorkflow for a routed assignment.

    Best-effort only — the DB decision is authoritative. Temporal being down
    must never undo a recorded routing.
    """
    try:
        client = await Client.connect(get_settings().TEMPORAL_HOST, namespace=get_settings().TEMPORAL_NAMESPACE)
        await client.start_workflow(
            "UniversitySLAWorkflow",
            args=[str(assignment.assignment_id), [str(assignment.university_id)]],
            id=_sla_workflow_id(assignment.assignment_id),
            task_queue="triage-queue",
        )
    except Exception:
        logger.warning("SLA workflow start failed for assignment %s", assignment.assignment_id, exc_info=True)


async def _signal_sla_workflow(assignment_id: object, decision: str) -> None:
    """WP-4: release a waiting UniversitySLAWorkflow after ACCEPT/DECLINE."""
    try:
        client = await Client.connect(get_settings().TEMPORAL_HOST, namespace=get_settings().TEMPORAL_NAMESPACE)
        handle = client.get_workflow_handle(_sla_workflow_id(assignment_id))
        await handle.signal(UNIVERSITY_SIGNAL_NAME, decision)
    except Exception:
        logger.warning("SLA signal failed for assignment %s", assignment_id, exc_info=True)


async def _ensure_project_team(db: AsyncSession, assignment, problem) -> "ProjectTeam":
    """WP-4: auto-create the project team + M1/M2/M3 milestones on ACCEPT.

    Idempotent: returns the existing team when a previous ACCEPT (or a retry)
    already created one. Also bumps the university's persisted current_load so
    batch routing's capacity check reflects reality.
    """
    existing = (await db.execute(
        select(ProjectTeam).where(ProjectTeam.assignment_id == assignment.assignment_id).limit(1)
    )).scalars().first()
    if existing is not None:
        return existing
    settings = get_settings()
    team = ProjectTeam(
        assignment_id=assignment.assignment_id,
        problem_id=assignment.problem_id,
        university_id=assignment.university_id,
        faculty_mentor_name="TBD",
        student_lead_name="TBD",
        proposal_title=problem.title if problem is not None else None,
        status="TEAM_FORMED",
    )
    db.add(team)
    await db.flush()
    now = datetime.now(timezone.utc)
    specs = [
        (1, "M1 · Feasibility Study", settings.MILESTONE_M1_DAYS),
        (2, "M2 · Prototype Design", settings.MILESTONE_M2_DAYS),
        (3, "M3 · Field Validation", settings.MILESTONE_M3_DAYS),
    ]
    for num, title, days in specs:
        db.add(Milestone(team_id=team.team_id, milestone_num=num, title=title, due_date=now + timedelta(days=days), status="PENDING"))
    university = await db.get(University, assignment.university_id)
    if university is not None:
        university.current_load = (university.current_load or 0) + 1
    return team


class LoginRequest(BaseModel):
    email: str
    password: str


class DecisionRequest(BaseModel):
    decision: str
    override_university_id: str | None = None
    comments: str | None = None


class AssignmentResponse(BaseModel):
    response: str


class PledgeRequest(BaseModel):
    problem_id: str
    team_id: str | None = None
    pledged_amount_inr: float = Field(gt=0)


def parse_uuid(value: str, label: str = "id") -> uuid.UUID:
    """Validate path/payload identifiers so malformed values return 422 instead of a 500."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=422, detail=f"Invalid {label}: expected a UUID")


def classify_issue(text: str) -> tuple[str, int]:
    """Deterministic intake fallback used until the Temporal LLM worker completes enrichment."""
    lowered = text.lower()
    categories = {"Water": ["water", "drain", "flood", "paani"], "Health": ["health", "hospital", "medical"], "Infrastructure": ["road", "bridge", "street", "light"], "Agriculture": ["farm", "crop", "irrigation"], "Environment": ["pollution", "waste", "smoke"]}
    for category, words in categories.items():
        if any(word in lowered for word in words):
            return category, 4 if any(word in lowered for word in ("urgent", "danger", "flood", "broken")) else 3
    return "Governance", 3


@api_router.post("/auth/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Identity provider: verified passwords only (B2.11/B2.12 fail-closed).

    Order: officer row (bcrypt enforced) → User row from register/invite
    (bcrypt enforced) → exact university/industry contact-email demo match
    (no password stored; demo-only, logged) → 401. No email-substring role
    guessing: unknown emails are rejected, never auto-citizen.
    """
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required")
    email = payload.email.lower()
    role = "citizen"
    # Hardened path: known officer accounts must present the right password.
    officer_row = None
    try:
        officer_row = await auth_svc.verify_officer_password(db, email, payload.password)
    except ValueError:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if officer_row is not None:
        role = "admin" if officer_row.role == "state_admin" else "officer"
    matched_university = None
    matched_industry = None
    account = None
    if officer_row is None:
        # Registered / invited users: verify the stored bcrypt password.
        from app.api.deps import verify_password as _verify
        from app.db.models import User as _User

        account = (
            await db.execute(select(_User).where(_User.email_encrypted == auth_svc.contact_hash(email)))
        ).scalars().first()
        if account is not None:
            if not account.password_hash:
                raise HTTPException(status_code=401, detail="Incorrect email or password")
            try:
                ok = _verify(payload.password, account.password_hash)
            except Exception:
                raise HTTPException(status_code=401, detail="Incorrect email or password")
            if not ok:
                raise HTTPException(status_code=401, detail="Incorrect email or password")
            # Role follows the provisioned workspace, not the email text.
            ws = (account.workspace_type or "citizen").lower()
            if ws == "university":
                role = "university"
            elif ws in {"corporate", "industry"}:
                role = "industry"
            elif ws == "admin":
                role = "admin"
            elif ws == "officer":
                role = "officer"
            else:
                role = "citizen"
            # Invited accounts already carry organization_id — honor it; fall
            # back to the existing workspace-scoping block below when absent.
            if account.organization_id:
                from app.api.deps import ROLE_WORKSPACE as _RW

                _ws_type = _RW.get(role, "citizen")
                _org_name = None
                if role == "university":
                    _uni = await db.get(University, account.organization_id)
                    _org_name = _uni.name if _uni else None
                elif role == "industry":
                    _ind = await db.get(Industry, account.organization_id)
                    _org_name = _ind.name if _ind else None
                if _org_name is not None or account.organization_id is not None:
                    _token = create_access_token(
                        {"sub": str(account.user_id), "role": role, "organization_id": str(account.organization_id), "workspace_type": _ws_type}
                    )
                    return {
                        "access_token": _token,
                        "token_type": "bearer",
                        "role": role,
                        "workspace_type": _ws_type,
                        "organization_id": str(account.organization_id),
                        "organization_name": _org_name,
                        "display_name": account.display_name,
                    }
            # No org pinned (citizen self-serve): token with no organization
            # scope — must return here, the demo lookups below would 401.
            if role == "citizen":
                from app.api.deps import ROLE_WORKSPACE as _RW2

                _ws2 = _RW2.get(role, "citizen")
                _tok2 = create_access_token(
                    {"sub": str(account.user_id), "role": role, "organization_id": None, "workspace_type": _ws2}
                )
                return {
                    "access_token": _tok2,
                    "token_type": "bearer",
                    "role": role,
                    "workspace_type": _ws2,
                    "organization_id": None,
                    "organization_name": None,
                    "display_name": account.display_name,
                }
            # Non-citizen without org (shouldn't happen): fall through to the
            # generic scoping block below.
        # Exact workspace matches so seeded nodal/contact emails land in the
        # right portal (demo-only: these tables carry no password). B2.12:
        # no substring heuristics (no "admin in email", no ".ac.in" guessing).
        matched_university = (await db.execute(
            select(University).where(func.lower(University.nodal_contact_email) == email)
        )).scalars().first()
        if matched_university is None:
            matched_industry = (await db.execute(
                select(Industry).where(func.lower(Industry.contact_email) == email)
            )).scalars().first()
        if matched_university is not None:
            logger.warning("Demo login (no password) for university contact %s", email)
            role = "university"
        elif matched_industry is not None:
            logger.warning("Demo login (no password) for industry contact %s", email)
            role = "industry"
        else:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
    # Portal data must be scoped to the signed-in university/industry workspace.
    organization_id = None
    organization_name = None
    # Display name: officer rows and industry contacts carry real names;
    # citizen self-serve accounts carry display_name when set at signup.
    display_name = officer_row.name if officer_row is not None else None
    if role == "university":
        university = matched_university
        if university is None:
            university = (await db.execute(select(University).order_by(University.name).limit(1))).scalars().first()
        if university is None:
            raise HTTPException(status_code=503, detail="No university workspace is configured")
        organization_id = str(university.university_id)
        organization_name = university.name
    elif role == "industry":
        industry = matched_industry
        if industry is None:
            industry = (await db.execute(select(Industry).order_by(Industry.name).limit(1))).scalars().first()
        if industry is None:
            raise HTTPException(status_code=503, detail="No industry workspace is configured")
        organization_id = str(industry.industry_id)
        organization_name = industry.name
        if display_name is None:
            display_name = industry.contact_person
    elif role == "citizen" and account is not None:
        display_name = account.display_name
    from app.api.deps import ROLE_WORKSPACE

    workspace_type = ROLE_WORKSPACE.get(role, "citizen")
    token = create_access_token(
        {"sub": email, "role": role, "organization_id": organization_id, "workspace_type": workspace_type}
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "workspace_type": workspace_type,
        "organization_id": organization_id,
        "organization_name": organization_name,
        "display_name": display_name,
    }


@api_router.post("/submissions", status_code=status.HTTP_202_ACCEPTED)
async def create_submission(
    raw_text: str = Form(...),
    language_pref: str = Form("english"),
    district: str | None = Form(None),
    block: str | None = Form(None),
    geo_lat: float | None = Form(None),
    geo_lng: float | None = Form(None),
    geo_source: str | None = Form(None),
    reporter_name: str | None = Form(None),
    contact_email: str | None = Form(None),
    contact_phone: str | None = Form(None),
    notify_consent: str | None = Form(None),
    photo: UploadFile | None = File(None),
    photos: list[UploadFile] = File(default=[]),
    audio_note: UploadFile | None = File(None),
    background: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    _limited: bool = Depends(rate_limit(setting="RATE_LIMIT_SUBMIT_PER_MIN")),
    caller: dict | None = Depends(get_current_user_optional),
):
    raw_text = raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="Issue description cannot be blank")
    if len(raw_text) > 5000:
        raise HTTPException(status_code=422, detail="Issue description is too long (max 5000 characters)")
    clean_reporter = (reporter_name or "").strip()[:120] or None
    from app.services import notify_reporter as notify_mod

    clean_email = notify_mod.normalize_email(contact_email)
    clean_phone = notify_mod.normalize_phone(contact_phone)
    consent = notify_mod.parse_consent(notify_consent) and bool(clean_email or clean_phone)
    attachments: list[tuple[str, bytes, str]] = []  # (kind, bytes, filename)
    # The UI sends up to 4 photos as `photo`, `photo_2`… — merge the declared
    # extras (photo_N) and any repeated `photos` field into one photo list.
    extra_photos: list[UploadFile] = list(photos or [])
    uploads = [photo] if photo is not None else []
    uploads.extend(extra_photos)
    for upload in uploads[:4]:
        contents = await upload.read()
        if len(contents) > get_settings().MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Photo exceeds the maximum allowed size of 5 MB")
        if contents:
            attachments.append(("photo", contents, upload.filename or "photo"))
    if audio_note is not None:
        audio_bytes = await audio_note.read()
        if len(audio_bytes) > get_settings().MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Audio note exceeds the maximum allowed size of 5 MB")
        if audio_bytes:
            attachments.append(("audio", audio_bytes, audio_note.filename or "audio-note.webm"))
    tracking_token = f"NITIVAYU-{datetime.now().year}-JH-{uuid.uuid4().hex[:6].upper()}"
    has_coords = geo_lat is not None and geo_lng is not None
    # WP-1: when a signed-in citizen submits, link the report to their account
    # so "My reports" works across devices. Anonymous intake stays allowed.
    owner_id = None
    if caller:
        try:
            owner_id = uuid.UUID(str(caller.get("user_id")))
        except (ValueError, AttributeError, TypeError):
            owner_id = None
    submission = Submission(
        raw_text=raw_text,
        language_pref=(language_pref or "english")[:10],
        geo_district=district,
        geo_block=block,
        geo_lat=geo_lat,
        geo_lng=geo_lng,
        geo_source=(geo_source if geo_source in {"gps", "manual"} else ("gps" if has_coords else "district")),
        photo_url=None,
        tracking_token=tracking_token,
        reporter_name=clean_reporter,
        contact_email=clean_email if consent else None,
        contact_phone=clean_phone if consent else None,
        notify_consent=consent,
        status="PENDING_TRIAGE",
    )
    db.add(submission)
    await db.flush()
    # Persist evidence: object storage when enabled, local media mirror
    # otherwise. First photo doubles as legacy `photo_url` for old consumers.
    media_assets: list[dict] = []
    for kind, blob, filename in attachments:
        content_type = "image/webp" if kind == "photo" else "audio/webm"
        try:
            stored_url = storage_svc.put_bytes(
                storage_svc.object_key(f"submissions/{submission.submission_id}", filename), blob, content_type
            )
        except Exception:
            logger.warning("Evidence store failed for submission %s", submission.submission_id, exc_info=True)
            stored_url = f"inline://{kind}/{filename}"
        if kind == "photo" and not submission.photo_url:
            submission.photo_url = stored_url
        asset = MediaAsset(
            submission_id=submission.submission_id,
            kind=kind,
            storage_url=stored_url,
            size_bytes=len(blob),
            moderation_status="pending",
        )
        db.add(asset)
        await db.flush()
        media_assets.append({"asset_id": str(asset.asset_id), "kind": kind, "storage_url": stored_url})
    category, severity = classify_issue(raw_text)
    problem = Problem(submission_id=submission.submission_id, title=raw_text[:120], summary=raw_text, category=category, severity_score=severity, status="PENDING_OFFICER_REVIEW")
    db.add(problem)
    await db.flush()
    university = (await db.execute(select(University).order_by(University.current_load.asc()).limit(1))).scalars().first()
    if university:
        db.add(RouteAssignment(problem_id=problem.problem_id, university_id=university.university_id, rank_order=1, match_score=0.70, score_breakdown={"fallback": 0.70}, sla_deadline=datetime.now(timezone.utc) + timedelta(days=7), status="PENDING_APPROVAL"))
    db.add(make_audit(entity_type="submission", entity_id=str(submission.submission_id), action="SUBMITTED", actor_id=str(owner_id) if owner_id else "anonymous", actor_role="citizen", after={"status": submission.status}))
    await db.commit()
    append_audit({"entity_type": "submission", "entity_id": str(submission.submission_id), "action": "SUBMITTED", "actor_role": "citizen"})
    workflow_id = f"triage-{submission.submission_id}"
    try:
        client = await Client.connect(get_settings().TEMPORAL_HOST, namespace=get_settings().TEMPORAL_NAMESPACE)
        await client.start_workflow(
            "ChallengeTriageWorkflow",
            args=[
                str(submission.submission_id),
                raw_text,
                district or "Unknown",
            ],
            id=workflow_id,
            task_queue="triage-queue",
        )
        problem.temporal_workflow_id = workflow_id
        await db.commit()
    except Exception:
        logger.warning("Temporal unavailable; submission %s processed via deterministic fallback only", submission.submission_id, exc_info=True)
    # WP-10: process stored evidence asynchronously (scan → normalize →
    # transcribe). Triage proceeds on text alone if media is slow or down.
    if media_assets:
        try:
            media_client = await Client.connect(get_settings().TEMPORAL_HOST, namespace=get_settings().TEMPORAL_NAMESPACE)
            await media_client.start_workflow(
                "MediaProcessingWorkflow",
                args=[{"submission_id": str(submission.submission_id), "assets": media_assets}],
                id=f"media-{submission.submission_id}",
                task_queue="triage-queue",
            )
        except Exception:
            logger.warning("Media workflow start failed for submission %s", submission.submission_id, exc_info=True)
    # Best-effort live fan-out (polling clients are unaffected if this fails).
    try:
        await publish_event(f"track:{tracking_token}", {"type": "submission.ingested", "data": {"tracking_token": tracking_token, "status": submission.status}})
        await publish_event("public", {"type": "submission.ingested", "data": {"tracking_token": tracking_token, "district": district}})
    except Exception:
        logger.warning("SSE publish failed for submission %s", submission.submission_id, exc_info=True)
    # Reporter confirmation (mail/SMS) for opt-in contacts — backgrounded so
    # slow gateways never block intake; best-effort, never raises.
    if consent:
        background.add_task(
            notify_mod.notify_reporter, clean_email, clean_phone,
            kind="submitted", tracking_token=tracking_token, title=raw_text[:140],
        )
    return {"submission_id": str(submission.submission_id), "tracking_token": tracking_token, "status": submission.status}


@api_router.get("/submissions/{tracking_token}/track")
async def track_submission(tracking_token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Submission).where(Submission.tracking_token == tracking_token))
    submission = result.scalars().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    problem_result = await db.execute(select(Problem).where(Problem.submission_id == submission.submission_id))
    problem = problem_result.scalars().first()
    assignment = None
    milestones: list[dict] = []
    activity: list[dict] = []
    if problem:
        assignment_result = await db.execute(
            select(RouteAssignment).options(selectinload(RouteAssignment.university)).where(
                RouteAssignment.problem_id == problem.problem_id
            ).order_by(RouteAssignment.rank_order)
        )
        assignment = assignment_result.scalars().first()
        team = (await db.execute(
            select(ProjectTeam).where(ProjectTeam.problem_id == problem.problem_id).limit(1)
        )).scalars().first()
        if team:
            milestone_rows = (await db.execute(
                select(Milestone).where(Milestone.team_id == team.team_id).order_by(Milestone.milestone_num)
            )).scalars().all()
            milestones = [
                {"milestone_id": str(m.milestone_id), "title": m.title, "status": m.status,
                 "evidence_url": m.evidence_url, "verified_at": m.verified_at.isoformat() if m.verified_at else None,
                 "due_date": m.due_date.isoformat() if m.due_date else None}
                for m in milestone_rows
            ]
        audit_rows = (await db.execute(
            select(AuditLog).where(AuditLog.entity_id.in_([str(submission.submission_id), str(problem.problem_id)])).order_by(AuditLog.timestamp.desc()).limit(10)
        )).scalars().all()
        activity = [
            {"action": row.action, "actor_role": row.actor_role, "timestamp": row.timestamp.isoformat() if row.timestamp else None}
            for row in audit_rows
        ]
        # P4: university progress updates surface on the citizen tracker in
        # plain language, reusing the same activity feed (no new visual style).
        try:
            from app.db.models import ProjectUpdate

            update_rows = (
                await db.execute(
                    select(ProjectUpdate)
                    .where(ProjectUpdate.problem_id == problem.problem_id)
                    .order_by(ProjectUpdate.created_at)
                )
            ).scalars().all()
            for update in update_rows:
                activity.append(
                    {
                        "action": "PROJECT_UPDATE",
                        "actor_role": "university",
                        "timestamp": update.created_at.isoformat() if update.created_at else None,
                        "note": update.note,
                        "milestone": update.milestone,
                        "author_name": update.author_name,
                    }
                )
        except Exception:
            logger.warning("Tracker update merge failed for %s", problem.problem_id, exc_info=True)
    return {
        "tracking_token": submission.tracking_token,
        "status": submission.status if not problem else problem.status,
        "title": problem.title if problem else None,
        "category": problem.category if problem else None,
        "severity": str(problem.severity_score) if problem and problem.severity_score else None,
        "reporter_name": submission.reporter_name,
        "district": submission.geo_district,
        "submitted_at": submission.created_at.isoformat() if submission.created_at else None,
        "matched_university": assignment.university.name if assignment else None,
        "milestones": milestones,
        "activity": activity,
    }


@api_router.get("/officer/review-queue")
async def review_queue(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("officer", "admin")),
):
    limit = max(1, min(limit, 100))
    skip = max(0, skip)
    total = (await db.execute(
        select(func.count(Problem.problem_id)).where(Problem.status == "PENDING_OFFICER_REVIEW")
    )).scalar_one()
    result = await db.execute(
        select(Problem).options(
            selectinload(Problem.submission),
            selectinload(Problem.route_assignments).selectinload(RouteAssignment.university),
        ).where(Problem.status == "PENDING_OFFICER_REVIEW").order_by(Problem.created_at.desc()).offset(skip).limit(limit)
    )
    now = datetime.now(timezone.utc)
    items = []
    for problem in result.scalars().all():
        assignments = sorted(problem.route_assignments, key=lambda a: a.rank_order)
        top_matches = [
            {"university_id": str(a.university_id), "university_name": a.university.name if a.university else None, "match_score": a.match_score}
            for a in assignments[:3]
        ]
        sla_deadline = assignments[0].sla_deadline if assignments else None
        sla_hours = max(0, int((sla_deadline - now).total_seconds() // 3600)) if sla_deadline else 48
        items.append({
            "id": str(problem.problem_id), "title": problem.title, "description": problem.summary,
            "category": problem.category, "severity": str(problem.severity_score or 1),
            "district": problem.submission.geo_district if problem.submission else "Unspecified",
            "reporter_name": problem.submission.reporter_name if problem.submission else None,
            "status": problem.status, "sla_hours_remaining": sla_hours, "top_matches": top_matches,
        })
    return {"items": items, "total": total, "skip": skip, "limit": limit, "has_more": skip + len(items) < total}


@api_router.get("/officer/escalations")
async def officer_escalations(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("officer", "admin")),
):
    """Server-side escalation list (WP-3): problems breaching the officer SLA
    window (80% of OFFICER_SLA_HOURS elapsed without a decision), critical
    severity-5 items still pending, and anything already ESCALATED by the
    triage workflow. Replaces the client-side queue filter with hardcoded rules.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    warn_cutoff = now - timedelta(hours=settings.OFFICER_SLA_HOURS * 0.8)
    result = await db.execute(
        select(Problem).options(
            selectinload(Problem.submission),
            selectinload(Problem.route_assignments).selectinload(RouteAssignment.university),
        ).where(
            (Problem.status == "ESCALATED")
            | ((Problem.status == "PENDING_OFFICER_REVIEW") & (Problem.created_at <= warn_cutoff))
            | ((Problem.status == "PENDING_OFFICER_REVIEW") & (Problem.severity_score == 5))
        ).order_by(Problem.severity_score.desc().nullslast(), Problem.created_at.asc()).limit(100)
    )
    items = []
    for problem in result.scalars().all():
        assignments = sorted(problem.route_assignments, key=lambda a: a.rank_order)
        age_hours = max(0, int((now - problem.created_at).total_seconds() // 3600)) if problem.created_at else None
        if problem.status == "ESCALATED":
            reason = "ESCALATED"
        elif problem.severity_score == 5:
            reason = "SEVERITY_CRITICAL"
        else:
            reason = "SLA_BREACH_RISK"
        items.append({
            "id": str(problem.problem_id), "title": problem.title, "description": problem.summary,
            "category": problem.category, "severity": str(problem.severity_score or 1),
            "district": problem.submission.geo_district if problem.submission else "Unspecified",
            "reporter_name": problem.submission.reporter_name if problem.submission else None,
            "status": problem.status, "age_hours": age_hours, "reason": reason,
            "top_matches": [
                {"university_id": str(a.university_id), "university_name": a.university.name if a.university else None, "match_score": a.match_score}
                for a in assignments[:3]
            ],
        })
    return {"items": items, "total": len(items), "sla_hours": settings.OFFICER_SLA_HOURS}


@api_router.post("/officer/reviews/{problem_id}/decision")
async def decide_problem(problem_id: str, payload: DecisionRequest, background: BackgroundTasks, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))):
    if payload.decision not in {"APPROVE", "REJECT", "OVERRIDE"}:
        raise HTTPException(status_code=400, detail="Decision must be APPROVE, REJECT, or OVERRIDE")
    problem = await db.get(Problem, parse_uuid(problem_id, "problem_id"))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if problem.status != "PENDING_OFFICER_REVIEW":
        raise HTTPException(status_code=409, detail="This problem has already been reviewed")
    if payload.decision == "OVERRIDE" and not payload.override_university_id:
        raise HTTPException(status_code=400, detail="An override university is required")
    problem.status = "ROUTED" if payload.decision != "REJECT" else "REJECTED"
    assignment_result = await db.execute(select(RouteAssignment).where(RouteAssignment.problem_id == problem.problem_id))
    assignments = assignment_result.scalars().all()
    assignment = assignments[0] if assignments else None
    if payload.decision == "OVERRIDE":
        university = await db.get(University, parse_uuid(payload.override_university_id, "override_university_id"))
        if not university:
            raise HTTPException(status_code=404, detail="Override university not found")
        if assignment:
            assignment.university_id = university.university_id
        else:
            assignment = RouteAssignment(
                problem_id=problem.problem_id,
                university_id=university.university_id,
                rank_order=1,
                match_score=1.0,
                score_breakdown={"officer_override": 1.0},
                sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
            )
            db.add(assignment)
    if assignment:
        assignment.status = "OFFERED" if payload.decision != "REJECT" else "CANCELLED"
    if payload.decision == "REJECT":
        for route_assignment in assignments:
            route_assignment.status = "CANCELLED"
    submission = await db.get(Submission, problem.submission_id)
    if submission:
        submission.status = "ROUTED" if payload.decision != "REJECT" else "REJECTED"
    db.add(make_audit(entity_type="problem", entity_id=str(problem.problem_id), action=f"OFFICER_{payload.decision}", actor_id=user["user_id"], actor_role=user["role"], after={"status": problem.status, "comments": payload.comments}))
    # WP-3: record which officer decided (resolvable for officer-email logins
    # and UUID-sub officer accounts alike).
    try:
        from app.db.models import Officer as _Officer

        officer_row = (await db.execute(select(_Officer).where(_Officer.email == str(user["user_id"]).lower()))).scalars().first()
        if officer_row is None:
            officer_row = await db.get(_Officer, parse_uuid(str(user["user_id"]), "user_id"))
        if officer_row is not None:
            problem.assigned_officer_id = officer_row.officer_id
    except Exception:
        logger.warning("Could not resolve deciding officer for %s", problem.problem_id, exc_info=True)
    await db.commit()
    append_audit({"entity_type": "problem", "entity_id": str(problem.problem_id), "action": f"OFFICER_{payload.decision}", "actor_id": user["user_id"], "actor_role": user["role"]})
    try:
        if submission and submission.tracking_token:
            await publish_event(f"track:{submission.tracking_token}", {"type": "officer.decision", "data": {"problem_id": str(problem.problem_id), "status": problem.status}})
        if assignment:
            await publish_event(f"org:{assignment.university_id}", {"type": "officer.decision", "data": {"problem_id": str(problem.problem_id), "status": problem.status}})
    except Exception:
        logger.warning("SSE publish failed for decision on %s", problem.problem_id, exc_info=True)
    # The database decision is authoritative; also release any running triage
    # workflow waiting on the officer signal. Signal failures must not undo the
    # recorded decision (e.g. workflow already completed or Temporal is down).
    if problem.temporal_workflow_id:
        try:
            signal_client = await Client.connect(get_settings().TEMPORAL_HOST, namespace=get_settings().TEMPORAL_NAMESPACE)
            handle = signal_client.get_workflow_handle(problem.temporal_workflow_id)
            await handle.signal(OFFICER_SIGNAL_NAME, WORKFLOW_DECISION_SIGNALS[payload.decision])
        except Exception:
            logger.warning("Officer signal failed for workflow %s", problem.temporal_workflow_id, exc_info=True)
    # WP-4: a routed problem enters the university-acceptance SLA window.
    if payload.decision != "REJECT" and assignment is not None:
        await _start_sla_workflow(assignment)
    # Reporter decision notification (opt-in contacts only, backgrounded).
    if submission is not None and submission.notify_consent and (submission.contact_email or submission.contact_phone):
        from app.services import notify_reporter as _notify_mod

        kind = {"APPROVE": "approved", "REJECT": "rejected", "OVERRIDE": "overridden"}.get(payload.decision, "update")
        detail = ""
        if payload.decision == "OVERRIDE" and assignment is not None:
            try:
                _uni = await db.get(University, assignment.university_id)
                detail = f"Routed to {_uni.name}." if _uni else ""
            except Exception:
                detail = ""
        elif payload.decision == "APPROVE" and assignment is not None:
            try:
                _uni = await db.get(University, assignment.university_id)
                detail = f"Matched with {_uni.name}." if _uni else ""
            except Exception:
                detail = ""
        background.add_task(
            _notify_mod.notify_reporter, submission.contact_email, submission.contact_phone,
            kind=kind, tracking_token=submission.tracking_token or "", title=problem.title,
            detail=f"{detail} {payload.comments or ''}".strip(),
        )
    return {"status": "success", "message": "Decision recorded"}


class WorkflowSignalRequest(BaseModel):
    decision: str


class WorkflowSignalResponse(BaseModel):
    status: str
    workflow_id: str
    signal: str


def _signal_error_status(exc: Exception) -> int | None:
    # temporalio.service.RPCError exposes `.status`; the underlying
    # temporal_sdk_bridge.RPCError exposes `.code`. NOT_FOUND (5) means the
    # workflow is gone or already completed.
    from temporalio.service import RPCStatusCode
    for attribute in ("status", "status_code", "code"):
        status_code = getattr(exc, attribute, None)
        if status_code is None:
            continue
        try:
            if int(status_code) == int(RPCStatusCode.NOT_FOUND):
                return status.HTTP_404_NOT_FOUND
        except (TypeError, ValueError):
            continue
    return None


@api_router.post("/officer/reviews/{problem_id}/signal", response_model=WorkflowSignalResponse)
async def signal_problem_workflow(problem_id: str, payload: WorkflowSignalRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))):
    """Send the officer decision signal to a running triage workflow."""
    if payload.decision not in {"APPROVE", "REJECT"}:
        raise HTTPException(status_code=400, detail="Decision must be APPROVE or REJECT")
    problem = await db.get(Problem, parse_uuid(problem_id, "problem_id"))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if not problem.temporal_workflow_id:
        raise HTTPException(status_code=404, detail="No Temporal workflow is linked to this problem")
    signal_value = WORKFLOW_DECISION_SIGNALS[payload.decision]
    try:
        client = await Client.connect(get_settings().TEMPORAL_HOST, namespace=get_settings().TEMPORAL_NAMESPACE)
        handle = client.get_workflow_handle(problem.temporal_workflow_id)
        await handle.signal(OFFICER_SIGNAL_NAME, signal_value)
    except Exception as exc:
        if _signal_error_status(exc) == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=404, detail="Temporal workflow not found or already completed")
        logger.warning("Temporal signal failed for workflow %s", problem.temporal_workflow_id, exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to signal the Temporal workflow")
    return WorkflowSignalResponse(status="success", workflow_id=problem.temporal_workflow_id, signal=signal_value)


class MilestoneVerifyRequest(BaseModel):
    decision: str  # VERIFY | REJECT
    comments: str | None = None


@api_router.post("/officer/milestones/{milestone_id}/verify")
async def verify_milestone(milestone_id: str, payload: MilestoneVerifyRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))):
    """WP-5: officer verifies or rejects submitted milestone evidence.

    Verifying M3 completes the whole problem (COMPLETED + frees university
    capacity); events fan out to the citizen tracker and the university. Only
    SUBMITTED milestones can be decided.
    """
    if payload.decision not in {"VERIFY", "REJECT"}:
        raise HTTPException(status_code=400, detail="Decision must be VERIFY or REJECT")
    milestone = await db.get(Milestone, parse_uuid(milestone_id, "milestone_id"))
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if milestone.status != "SUBMITTED":
        raise HTTPException(status_code=409, detail="This milestone is not awaiting verification")
    team = await db.get(ProjectTeam, milestone.team_id) if milestone.team_id else None
    problem = await db.get(Problem, team.problem_id) if team and team.problem_id else None
    submission = await db.get(Submission, problem.submission_id) if problem else None
    officer_id = None
    try:
        from app.db.models import Officer as _Officer

        officer_row = (await db.execute(select(_Officer).where(_Officer.email == str(user["user_id"]).lower()))).scalars().first()
        if officer_row is None:
            officer_row = await db.get(_Officer, parse_uuid(str(user["user_id"]), "user_id"))
        officer_id = officer_row.officer_id if officer_row is not None else None
    except Exception:
        logger.warning("Could not resolve verifying officer", exc_info=True)
    now = datetime.now(timezone.utc)
    if payload.decision == "VERIFY":
        milestone.status = "VERIFIED"
        milestone.verified_by = officer_id
        milestone.verified_at = now
        action = "MILESTONE_VERIFIED"
        # M3 verification resolves the challenge end-to-end.
        if milestone.milestone_num == 3 and problem is not None:
            problem.status = "COMPLETED"
            if submission is not None:
                submission.status = "COMPLETED"
            if team is not None:
                university = await db.get(University, team.university_id)
                if university is not None:
                    university.current_load = max(0, (university.current_load or 0) - 1)
    else:
        milestone.status = "REJECTED"
        action = "MILESTONE_REJECTED"
    db.add(make_audit(
        entity_type="milestone", entity_id=str(milestone.milestone_id), action=action,
        actor_id=user["user_id"], actor_role=user["role"],
        after={"decision": payload.decision, "comments": payload.comments, "problem_status": problem.status if problem else None},
    ))
    await db.commit()
    try:
        event = {
            "milestone_id": str(milestone.milestone_id),
            "milestone_num": milestone.milestone_num,
            "status": milestone.status,
            "problem_status": problem.status if problem else None,
        }
        if submission and submission.tracking_token:
            await publish_event(f"track:{submission.tracking_token}", {"type": "milestone.verified", "data": event})
        if team and team.university_id:
            await publish_event(f"org:{team.university_id}", {"type": "milestone.verified", "data": event})
    except Exception:
        logger.warning("SSE publish failed for milestone %s", milestone.milestone_id, exc_info=True)
    # WP-9: status SMS to opted-in citizens (no-op without the SMS channel).
    try:
        if submission is not None and submission.user_id is not None:
            from app.services import notify as notify_svc

            if payload.decision == "VERIFY" and problem is not None:
                done = " Your issue is now resolved." if problem.status == "COMPLETED" else ""
                await notify_svc.notify_citizen(
                    db, submission.user_id,
                    f"Nitivayu update on {submission.tracking_token}: milestone {milestone.milestone_num} verified.{done}",
                )
    except Exception:
        logger.warning("Citizen notify failed for milestone %s", milestone.milestone_id, exc_info=True)
    return {"status": "success", "milestone_status": milestone.status, "problem_status": problem.status if problem else None}


@api_router.post("/officer/media/{asset_id}/clear")
async def clear_flagged_media(asset_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))):
    """WP-10: officer clears FLAGGED evidence after review so it becomes
    visible to universities again. Anything else is a 409."""
    asset = await db.get(MediaAsset, parse_uuid(asset_id, "asset_id"))
    if not asset:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if asset.moderation_status != "flagged":
        raise HTTPException(status_code=409, detail="Only flagged evidence needs clearing")
    asset.moderation_status = "clean"
    db.add(make_audit(
        entity_type="media_asset", entity_id=str(asset.asset_id), action="MEDIA_CLEARED",
        actor_id=user["user_id"], actor_role=user["role"], after={"submission_id": str(asset.submission_id)},
    ))
    await db.commit()
    return {"status": "cleared"}


# NOTE: real batch-triage endpoints (trigger/schedules/history/stream) live in
# app/api/routes/batch_triage.py and are included below — no stubs here.


@api_router.get("/university/workspace")
async def university_workspace(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))):
    university_id = user.get("organization_id")
    if not university_id:
        raise HTTPException(status_code=403, detail="University account is not linked to a workspace")
    university = await db.get(University, parse_uuid(university_id, "organization_id"))
    if not university:
        raise HTTPException(status_code=404, detail="University workspace not found")
    return {
        "university_id": str(university.university_id),
        "name": university.name,
        "short_code": university.short_code,
        "district": university.district,
        "domain_specializations": university.domain_specializations or [],
        "active_capacity": university.active_capacity,
        "current_load": university.current_load,
    }


@api_router.get("/university/inbox")
async def university_inbox(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))):
    university_id = user.get("organization_id")
    if not university_id:
        raise HTTPException(status_code=403, detail="University account is not linked to a workspace")
    result = await db.execute(
        select(RouteAssignment).options(
            selectinload(RouteAssignment.problem).selectinload(Problem.submission)
        ).where(
            RouteAssignment.status == "OFFERED",
            RouteAssignment.university_id == university_id,
        ).order_by(RouteAssignment.assigned_at.desc())
    )
    return [
        {
            "assignment_id": str(item.assignment_id),
            "problem_id": str(item.problem_id),
            "problem_title": item.problem.title,
            "summary": item.problem.summary,
            "category": item.problem.category,
            "severity": item.problem.severity_score,
            "district": item.problem.submission.geo_district if item.problem.submission else None,
            "reporter_name": item.problem.submission.reporter_name if item.problem.submission else None,
            "match_score": item.match_score,
            "sla_deadline": item.sla_deadline.isoformat() if item.sla_deadline else None,
            "status": item.status,
        }
        for item in result.scalars().all()
    ]


@api_router.post("/university/assignments/{assignment_id}/respond")
async def respond_assignment(assignment_id: str, payload: AssignmentResponse, background: BackgroundTasks, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))):
    if payload.response not in {"ACCEPT", "DECLINE"}:
        raise HTTPException(status_code=400, detail="Response must be ACCEPT or DECLINE")
    assignment = await db.get(RouteAssignment, parse_uuid(assignment_id, "assignment_id"))
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if str(assignment.university_id) != user.get("organization_id"):
        raise HTTPException(status_code=403, detail="This assignment belongs to another university")
    if assignment.status != "OFFERED":
        raise HTTPException(status_code=409, detail="This assignment has already been answered")
    assignment.status = "ACCEPTED" if payload.response == "ACCEPT" else "DECLINED"
    assignment.responded_at = datetime.now(timezone.utc)
    if payload.response == "ACCEPT":
        problem = await db.get(Problem, assignment.problem_id)
        if problem:
            problem.status = "ACCEPTED"
        # WP-4: live teams + milestones replace seed-only project data.
        await _ensure_project_team(db, assignment, problem)
        db.add(make_audit(entity_type="problem", entity_id=str(assignment.problem_id), action="UNIVERSITY_ACCEPT", actor_id=user["user_id"], actor_role=user["role"], after={"assignment_id": str(assignment.assignment_id)}))
    else:
        db.add(make_audit(entity_type="problem", entity_id=str(assignment.problem_id), action="UNIVERSITY_DECLINE", actor_id=user["user_id"], actor_role=user["role"], after={"assignment_id": str(assignment.assignment_id)}))
    await db.commit()
    # WP-4: release the SLA workflow waiting on this assignment (best-effort).
    await _signal_sla_workflow(assignment.assignment_id, "accept" if payload.response == "ACCEPT" else "decline")
    # Reporter notification on accept AND decline (opt-in contacts only).
    try:
        problem = await db.get(Problem, assignment.problem_id)
        submission = await db.get(Submission, problem.submission_id) if problem else None
        if submission is not None and submission.notify_consent and (submission.contact_email or submission.contact_phone):
            from app.services import notify_reporter as _notify_mod

            uni_name = ""
            try:
                _uni = await db.get(University, assignment.university_id)
                uni_name = _uni.name if _uni else ""
            except Exception:
                uni_name = ""
            background.add_task(
                _notify_mod.notify_reporter, submission.contact_email, submission.contact_phone,
                kind="accepted" if payload.response == "ACCEPT" else "declined",
                tracking_token=submission.tracking_token or "",
                title=problem.title if problem else "",
                detail=f"{uni_name} accepted your report." if payload.response == "ACCEPT" else "",
            )
    except Exception:
        logger.warning("Citizen notify failed for assignment %s", assignment.assignment_id, exc_info=True)
    try:
        problem = await db.get(Problem, assignment.problem_id)
        if problem:
            submission = await db.get(Submission, problem.submission_id)
            if submission and submission.tracking_token:
                await publish_event(f"track:{submission.tracking_token}", {"type": "university.response", "data": {"assignment_id": str(assignment.assignment_id), "response": payload.response}})
    except Exception:
        logger.warning("SSE publish failed for assignment %s", assignment.assignment_id, exc_info=True)
    return {"status": "success"}


@api_router.get("/university/projects")
async def university_projects(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))):
    university_id = user.get("organization_id")
    if not university_id:
        raise HTTPException(status_code=403, detail="University account is not linked to a workspace")
    result = await db.execute(
        select(ProjectTeam).options(
            selectinload(ProjectTeam.problem),
            selectinload(ProjectTeam.milestones),
        ).where(ProjectTeam.university_id == university_id).order_by(ProjectTeam.created_at.desc())
    )
    projects = []
    for team in result.scalars().all():
        milestones = sorted(team.milestones, key=lambda m: m.milestone_num or 0)
        current = next((m for m in milestones if m.status != "VERIFIED"), None)
        projects.append({
            "team_id": str(team.team_id),
            "problem_id": str(team.problem_id) if team.problem_id else None,
            "title": team.proposal_title or (team.problem.title if team.problem else "Untitled project"),
            "faculty_mentor_name": team.faculty_mentor_name,
            "student_lead_name": team.student_lead_name,
            "status": team.status,
            "current_milestone": current.milestone_num if current else 3,
            "milestones": [
                {"milestone_id": str(m.milestone_id), "milestone_num": m.milestone_num, "title": m.title, "status": m.status,
                 "evidence_url": m.evidence_url, "verified_at": m.verified_at.isoformat() if m.verified_at else None,
                 "due_date": m.due_date.isoformat() if m.due_date else None}
                for m in milestones
            ],
        })
    return projects


@api_router.get("/industry/opportunities")
async def csr_opportunities(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("industry"))):
    result = await db.execute(
        select(Problem).options(
            selectinload(Problem.submission),
            selectinload(Problem.route_assignments).selectinload(RouteAssignment.university),
            selectinload(Problem.project_teams),
        ).where(Problem.status.in_(["ROUTED", "ACCEPTED"])).order_by(Problem.created_at.desc()).limit(50)
    )
    problems = result.scalars().all()
    pledge_rows = (await db.execute(
        select(FundingLink.problem_id, func.coalesce(func.sum(FundingLink.pledged_amount_inr), 0))
        .where(FundingLink.problem_id.in_([p.problem_id for p in problems]))
        .group_by(FundingLink.problem_id)
    )).all() if problems else []
    pledged_by_problem = {problem_id: float(total) for problem_id, total in pledge_rows}
    opportunities = []
    for p in problems:
        assignment = next((a for a in p.route_assignments if a.status in ("OFFERED", "ACCEPTED")), None)
        opportunities.append({
            "problem_id": str(p.problem_id),
            "title": p.title,
            "description": p.summary,
            "category": p.category,
            "severity": p.severity_score,
            "district": p.submission.geo_district if p.submission else None,
            "reporter_name": p.submission.reporter_name if p.submission else None,
            "university": assignment.university.name if assignment and assignment.university else None,
            "status": p.status,
            "pledged_amount_inr": pledged_by_problem.get(p.problem_id, 0.0),
            "match_score": p.confidence_score or 0.0,
        })
    return opportunities


@api_router.post("/industry/pledges", status_code=status.HTTP_201_CREATED)
async def create_pledge(payload: PledgeRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("industry"))):
    if not user.get("organization_id"):
        raise HTTPException(status_code=403, detail="Industry account is not linked to a workspace")
    problem = await db.get(Problem, parse_uuid(payload.problem_id, "problem_id"))
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if problem.status not in {"ROUTED", "ACCEPTED"}:
        raise HTTPException(status_code=409, detail="Only routed problems can receive pledges")
    team_uuid = None
    if payload.team_id:
        team_uuid = parse_uuid(payload.team_id, "team_id")
        team = await db.get(ProjectTeam, team_uuid)
        if not team or team.problem_id != problem.problem_id:
            raise HTTPException(status_code=422, detail="Team must belong to the pledged problem")
    pledge = FundingLink(
        problem_id=problem.problem_id,
        team_id=team_uuid,
        industry_id=user["organization_id"],
        pledged_amount_inr=payload.pledged_amount_inr,
        status="PLEDGED",
    )
    db.add(pledge)
    db.add(make_audit(entity_type="problem", entity_id=str(problem.problem_id), action="CSR_PLEDGE", actor_id=user["user_id"], actor_role=user["role"], after={"amount_inr": payload.pledged_amount_inr}))
    await db.commit()
    await db.refresh(pledge)
    return {"id": str(pledge.link_id), "problem_id": str(pledge.problem_id), "amount": pledge.pledged_amount_inr, "status": pledge.status}


@api_router.get("/industry/pledges")
async def list_pledges(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("industry"))):
    if not user.get("organization_id"):
        raise HTTPException(status_code=403, detail="Industry account is not linked to a workspace")
    result = await db.execute(
        select(FundingLink, Problem.title).join(Problem, FundingLink.problem_id == Problem.problem_id, isouter=True)
        .where(FundingLink.industry_id == user["organization_id"]).order_by(FundingLink.created_at.desc())
    )
    pledges = [
        {"id": str(link.link_id), "problem_id": str(link.problem_id), "problem_title": title, "amount": link.pledged_amount_inr, "status": link.status, "created_at": link.created_at.isoformat() if link.created_at else None}
        for link, title in result.all()
    ]
    return {
        "pledges": pledges,
        "total_pledged_inr": sum(p["amount"] or 0 for p in pledges),
        "projects_funded": len({p["problem_id"] for p in pledges}),
    }


@api_router.get("/industry/impact")
async def industry_impact(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("industry"))):
    """WP-7: real impact numbers for the corporate impact tab — the caller's
    own pledges plus milestone progress on the problems they fund."""
    if not user.get("organization_id"):
        raise HTTPException(status_code=403, detail="Industry account is not linked to a workspace")
    org_id = parse_uuid(user["organization_id"], "organization_id")
    links = (await db.execute(
        select(FundingLink).where(FundingLink.industry_id == org_id)
    )).scalars().all()
    problem_ids = {link.problem_id for link in links if link.problem_id}
    milestones_verified = 0
    districts: set[str] = set()
    if problem_ids:
        milestones_verified = (await db.execute(
            select(func.count(Milestone.milestone_id))
            .join(ProjectTeam, Milestone.team_id == ProjectTeam.team_id)
            .where(ProjectTeam.problem_id.in_(problem_ids), Milestone.status == "VERIFIED")
        )).scalar_one()
        district_rows = (await db.execute(
            select(Submission.geo_district).join(Problem, Problem.submission_id == Submission.submission_id)
            .where(Problem.problem_id.in_(problem_ids), Submission.geo_district.isnot(None))
        )).all()
        districts = {row[0] for row in district_rows if row[0]}
    return {
        "total_pledged_inr": sum(link.pledged_amount_inr or 0 for link in links),
        "projects_funded": len(problem_ids),
        "pledges": len(links),
        "milestones_verified": milestones_verified,
        "districts_reached": sorted(districts),
    }


@api_router.post("/industry/exports/monthly-matrix")
async def industry_monthly_matrix(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("industry"))):
    """WP-7: the caller's own CSR funding matrix (XLSX) — replaces the
    hardcoded 'monthly matrix' pointer row on the corporate impact tab."""
    from pathlib import Path as _Path

    if not user.get("organization_id"):
        raise HTTPException(status_code=403, detail="Industry account is not linked to a workspace")
    from app.activities.report_gen import collect_csr_matrix_rows
    from app.services.outputs import mirror_export as _mirror

    matrix = await collect_csr_matrix_rows(db, industry_id=parse_uuid(user["organization_id"], "organization_id"))
    path = write_csr_matrix(matrix, "Nitivayu_csr_matrix_org")
    body = _mirror(path, f"/api/v1/industry/exports/download/{_Path(path).name}")
    body["count"] = len(matrix)
    return body


@api_router.get("/industry/exports/download/{filename}")
async def industry_download_export(filename: str, user: dict = Depends(require_role("industry"))):
    """Stream a generated export file (dev path when S3 is disabled)."""
    from fastapi.responses import FileResponse

    from app.services.outputs import find_export_file

    found = find_export_file(filename)
    if found is None:
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(found, filename=found.name)


@api_router.get("/analytics/overview")
async def analytics_overview(db: AsyncSession = Depends(get_db)):
    import json

    cache_key = "analytics:overview"
    redis = redis_mod.get_redis()
    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
    total_submissions = (await db.execute(select(func.count(Submission.submission_id)))).scalar_one()
    problems = (await db.execute(select(Problem.category, Problem.status, Problem.severity_score, Submission.geo_district).join(Submission, Problem.submission_id == Submission.submission_id, isouter=True))).all()
    category_distribution: dict[str, int] = {}
    district_distribution: dict[str, int] = {}
    severity_distribution: dict[str, int] = {}
    routed_or_beyond = 0
    for category, status_value, severity, district in problems:
        category_distribution[category] = category_distribution.get(category, 0) + 1
        if district:
            district_distribution[district] = district_distribution.get(district, 0) + 1
        if severity:
            severity_distribution[str(severity)] = severity_distribution.get(str(severity), 0) + 1
        if status_value in {"ROUTED", "ACCEPTED", "COMPLETED"}:
            routed_or_beyond += 1
    total_problems = len(problems)
    active_universities = (await db.execute(select(func.count(University.university_id)))).scalar_one()
    total_pledged = (await db.execute(select(func.coalesce(func.sum(FundingLink.pledged_amount_inr), 0)))).scalar_one()
    body = {
        "total_submissions": total_submissions,
        "total_problems": total_problems,
        "triage_throughput": total_problems,
        "sla_compliance_percent": round(100.0 * routed_or_beyond / total_problems, 1) if total_problems else 100.0,
        "active_workers": active_universities,
        "total_pledged_inr": float(total_pledged or 0),
        "category_distribution": category_distribution,
        "district_distribution": district_distribution,
        "severity_distribution": severity_distribution,
    }
    if redis is not None:
        try:
            await redis.set(cache_key, json.dumps(body), ex=get_settings().ANALYTICS_CACHE_TTL_SECONDS)
        except Exception:
            pass
    return body


@api_router.post("/admin/reports/triage")
async def export_triage_report(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin", "officer"))):
    result = await db.execute(select(Problem).options(selectinload(Problem.submission)))
    rows = [{"submission_id": str(problem.submission_id), "timestamp_submitted": problem.created_at.isoformat(), "raw_text_preview": problem.summary[:200], "category": problem.category, "severity": problem.severity_score, "geo_district": problem.submission.geo_district if problem.submission else "", "triage_status": problem.status} for problem in result.scalars().all()]
    path = write_triage_csv(rows)
    from pathlib import Path as _Path

    from app.services.outputs import mirror_export as _mirror_export

    body = _mirror_export(path, f"/api/v1/admin/exports/download/{_Path(path).name}")
    body["count"] = len(rows)
    return body
