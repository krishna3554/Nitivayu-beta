"""HTTP API contract consumed by the Nitivayu web application."""

from datetime import datetime, timedelta, timezone
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import create_access_token, get_current_user, get_db, get_temporal_client, require_role
from app.db.models import AuditLog, FundingLink, Industry, Problem, ProjectTeam, RouteAssignment, Submission, University
from app.services.outputs import append_audit, write_triage_csv
from temporalio.service import RPCStatusCode

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

api_router = APIRouter()

# Officer decisions use uppercase API values; the triage workflow signal
# contract uses lowercase values. OVERRIDE still routes the problem onward.
WORKFLOW_DECISION_SIGNALS = {"APPROVE": "approve", "REJECT": "reject", "OVERRIDE": "approve"}
OFFICER_SIGNAL_NAME = "officer_approval_signal"


class LoginRequest(BaseModel):
    email: str
    password: str


class DecisionRequest(BaseModel):
    decision: str
    override_university_id: str | None = None
    comments: str | None = None


class AssignmentResponse(BaseModel):
    response: str


class BatchRequest(BaseModel):
    cadence_type: str = "weekly"
    include_unassigned_only: bool = True


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
    """Demo identity provider that returns a signed token for each portal role."""
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required")
    email = payload.email.lower()
    role = "citizen"
    # Prefer exact workspace matches so seeded nodal/contact emails always land
    # in the right portal; fall back to heuristic markers for ad-hoc demos.
    matched_university = (await db.execute(
        select(University).where(func.lower(University.nodal_contact_email) == email)
    )).scalars().first()
    matched_industry = None
    if matched_university is None:
        matched_industry = (await db.execute(
            select(Industry).where(func.lower(Industry.contact_email) == email)
        )).scalars().first()
    if "admin" in email or "officer" in email:
        role = "admin" if "admin" in email else "officer"
    elif matched_university is not None:
        role = "university"
    elif matched_industry is not None:
        role = "industry"
    elif any(marker in email for marker in ("uni", "iit", "nit", "prof", "iic", ".ac.in", ".edu")):
        role = "university"
    elif any(marker in email for marker in ("csr", "industry", "tata")):
        role = "industry"
    # Portal data must be scoped to the signed-in university/industry workspace.
    organization_id = None
    organization_name = None
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
    token = create_access_token({"sub": email, "role": role, "organization_id": organization_id})
    return {"access_token": token, "token_type": "bearer", "role": role, "organization_name": organization_name}


@api_router.post("/submissions", status_code=status.HTTP_202_ACCEPTED)
async def create_submission(
    request: Request,
    raw_text: str = Form(...),
    language_pref: str = Form("english"),
    district: str | None = Form(None),
    block: str | None = Form(None),
    photo: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    raw_text = raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="Issue description cannot be blank")
    if len(raw_text) > 5000:
        raise HTTPException(status_code=422, detail="Issue description is too long (max 5000 characters)")
    photo_name = None
    if photo is not None:
        contents = await photo.read()
        if len(contents) > get_settings().MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Photo exceeds the maximum allowed size of 5 MB")
        photo_name = photo.filename
    tracking_token = f"NITIVAYU-{datetime.now().year}-JH-{uuid.uuid4().hex[:6].upper()}"
    submission = Submission(
        raw_text=raw_text,
        geo_district=district,
        geo_block=block,
        photo_url=photo_name,
        tracking_token=tracking_token,
        status="PENDING_TRIAGE",
    )
    db.add(submission)
    await db.flush()
    category, severity = classify_issue(raw_text)
    problem = Problem(submission_id=submission.submission_id, title=raw_text[:120], summary=raw_text, category=category, severity_score=severity, status="PENDING_OFFICER_REVIEW")
    db.add(problem)
    await db.flush()
    university = (await db.execute(select(University).order_by(University.current_load.asc()).limit(1))).scalars().first()
    if university:
        db.add(RouteAssignment(problem_id=problem.problem_id, university_id=university.university_id, rank_order=1, match_score=0.70, score_breakdown={"fallback": 0.70}, sla_deadline=datetime.now(timezone.utc) + timedelta(days=7), status="PENDING_APPROVAL"))
    db.add(AuditLog(entity_type="submission", entity_id=str(submission.submission_id), action="SUBMITTED", actor_id="citizen", actor_role="citizen", after_snapshot={"status": submission.status}))
    await db.commit()
    append_audit({"entity_type": "submission", "entity_id": str(submission.submission_id), "action": "SUBMITTED", "actor_role": "citizen"})
    workflow_id = f"triage-{submission.submission_id}"
    try:
        client = await get_temporal_client(request)
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
        logger.warning("Temporal workflow start failed for submission %s; intake fallback retained", submission.submission_id, exc_info=True)
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
                {"milestone_id": str(m.milestone_id), "title": m.title, "status": m.status, "due_date": m.due_date.isoformat() if m.due_date else None}
                for m in milestone_rows
            ]
        audit_rows = (await db.execute(
            select(AuditLog).where(AuditLog.entity_id.in_([str(submission.submission_id), str(problem.problem_id)])).order_by(AuditLog.timestamp.desc()).limit(10)
        )).scalars().all()
        activity = [
            {"action": row.action, "actor_role": row.actor_role, "timestamp": row.timestamp.isoformat() if row.timestamp else None}
            for row in audit_rows
        ]
    return {
        "tracking_token": submission.tracking_token,
        "status": submission.status if not problem else problem.status,
        "title": problem.title if problem else None,
        "category": problem.category if problem else None,
        "severity": str(problem.severity_score) if problem and problem.severity_score else None,
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
            "status": problem.status, "sla_hours_remaining": sla_hours, "top_matches": top_matches,
        })
    return items


@api_router.post("/officer/reviews/{problem_id}/decision")
async def decide_problem(problem_id: str, payload: DecisionRequest, request: Request, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))):
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
    db.add(AuditLog(entity_type="problem", entity_id=str(problem.problem_id), action=f"OFFICER_{payload.decision}", actor_id=user["user_id"], actor_role=user["role"], after_snapshot={"status": problem.status, "comments": payload.comments}))
    await db.commit()
    append_audit({"entity_type": "problem", "entity_id": str(problem.problem_id), "action": f"OFFICER_{payload.decision}", "actor_id": user["user_id"], "actor_role": user["role"]})
    # The database decision is authoritative; also release any running triage
    # workflow waiting on the officer signal. Signal failures must not undo the
    # recorded decision (e.g. workflow already completed or Temporal is down).
    if problem.temporal_workflow_id:
        try:
            client = await get_temporal_client(request)
            handle = client.get_workflow_handle(problem.temporal_workflow_id)
            await handle.signal(OFFICER_SIGNAL_NAME, WORKFLOW_DECISION_SIGNALS[payload.decision])
        except Exception:
            logger.warning("Officer signal failed for workflow %s", problem.temporal_workflow_id, exc_info=True)
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
async def signal_problem_workflow(problem_id: str, payload: WorkflowSignalRequest, request: Request, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))):
    """Send the officer decision signal to a running triage workflow."""
    if payload.decision not in {"APPROVE", "REJECT"}:
        raise HTTPException(status_code=400, detail="Decision must be APPROVE or REJECT")
    problem = await db.get(Problem, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if not problem.temporal_workflow_id:
        raise HTTPException(status_code=404, detail="No Temporal workflow is linked to this problem")
    signal_value = WORKFLOW_DECISION_SIGNALS[payload.decision]
    try:
        client = await get_temporal_client(request)
        handle = client.get_workflow_handle(problem.temporal_workflow_id)
        await handle.signal(OFFICER_SIGNAL_NAME, signal_value)
    except Exception as exc:
        if _signal_error_status(exc) == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=404, detail="Temporal workflow not found or already completed")
        logger.warning("Temporal signal failed for workflow %s", problem.temporal_workflow_id, exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to signal the Temporal workflow")
    return WorkflowSignalResponse(status="success", workflow_id=problem.temporal_workflow_id, signal=signal_value)


@api_router.get("/admin/triage/schedules")
async def batch_schedule(user: dict = Depends(require_role("admin", "officer"))):
    return {"active_cadence": "weekly", "cron_expression": "0 0 * * 0", "next_run_utc": None}


@api_router.post("/admin/triage/trigger-batch", status_code=status.HTTP_202_ACCEPTED)
async def trigger_batch(payload: BatchRequest, user: dict = Depends(require_role("admin", "officer"))):
    batch_id = f"batch-triage-{uuid.uuid4().hex[:8]}"
    return {"batch_workflow_id": batch_id, "status": "QUEUED", "stream_url": f"/api/v1/admin/triage/batch-jobs/{batch_id}/stream"}


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
            "match_score": item.match_score,
            "sla_deadline": item.sla_deadline.isoformat() if item.sla_deadline else None,
            "status": item.status,
        }
        for item in result.scalars().all()
    ]


@api_router.post("/university/assignments/{assignment_id}/respond")
async def respond_assignment(assignment_id: str, payload: AssignmentResponse, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))):
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
        db.add(AuditLog(entity_type="problem", entity_id=str(assignment.problem_id), action="UNIVERSITY_ACCEPT", actor_id=user["user_id"], actor_role=user["role"], after_snapshot={"assignment_id": str(assignment.assignment_id)}))
    await db.commit()
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
                {"milestone_id": str(m.milestone_id), "milestone_num": m.milestone_num, "title": m.title, "status": m.status, "due_date": m.due_date.isoformat() if m.due_date else None}
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
    db.add(AuditLog(entity_type="problem", entity_id=str(problem.problem_id), action="CSR_PLEDGE", actor_id=user["user_id"], actor_role=user["role"], after_snapshot={"amount_inr": payload.pledged_amount_inr}))
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


@api_router.get("/analytics/overview")
async def analytics_overview(db: AsyncSession = Depends(get_db)):
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
    return {
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


@api_router.post("/admin/reports/triage")
async def export_triage_report(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin", "officer"))):
    result = await db.execute(select(Problem).options(selectinload(Problem.submission)))
    rows = [{"submission_id": str(problem.submission_id), "timestamp_submitted": problem.created_at.isoformat(), "raw_text_preview": problem.summary[:200], "category": problem.category, "severity": problem.severity_score, "geo_district": problem.submission.geo_district if problem.submission else "", "triage_status": problem.status} for problem in result.scalars().all()]
    return {"path": write_triage_csv(rows), "count": len(rows)}
