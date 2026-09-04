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
    pledged_amount_inr: float


def classify_issue(text: str) -> tuple[str, int]:
    """Deterministic intake fallback used until the Temporal LLM worker completes enrichment."""
    lowered = text.lower()
    categories = {"water": ["water", "drain", "flood", "paani"], "Health": ["health", "hospital", "medical"], "Infrastructure": ["road", "bridge", "street", "light"], "Agriculture": ["farm", "crop", "irrigation"], "Environment": ["pollution", "waste", "smoke"]}
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
    if "admin" in email or "officer" in email:
        role = "admin" if "admin" in email else "officer"
    elif any(marker in email for marker in ("uni", "iit", "nit", "prof")):
        role = "university"
    elif any(marker in email for marker in ("csr", "industry", "tata")):
        role = "industry"
    # Portal data must be scoped to the signed-in university.  The previous
    # implementation issued every university user an unscoped token, which
    # made the inbox either empty or expose offers for every institution.
    organization_id = None
    if role == "university":
        university = (await db.execute(
            select(University).where(University.nodal_contact_email == email)
        )).scalars().first()
        if university is None:
            university = (await db.execute(select(University).order_by(University.name).limit(1))).scalars().first()
        if university is None:
            raise HTTPException(status_code=503, detail="No university workspace is configured")
        organization_id = str(university.university_id)
    elif role == "industry":
        industry = (await db.execute(
            select(Industry).where(Industry.contact_email == email)
        )).scalars().first()
        if industry is None:
            industry = (await db.execute(select(Industry).order_by(Industry.name).limit(1))).scalars().first()
        if industry is None:
            raise HTTPException(status_code=503, detail="No industry workspace is configured")
        organization_id = str(industry.industry_id)
    token = create_access_token({"sub": email, "role": role, "organization_id": organization_id})
    return {"access_token": token, "token_type": "bearer", "role": role}


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
    tracking_token = f"NITIVAYU-{datetime.now().year}-JH-{uuid.uuid4().hex[:6].upper()}"
    submission = Submission(
        raw_text=raw_text,
        geo_district=district,
        geo_block=block,
        photo_url=photo.filename if photo else None,
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
    if problem:
        assignment_result = await db.execute(
            select(RouteAssignment).options(selectinload(RouteAssignment.university)).where(
                RouteAssignment.problem_id == problem.problem_id
            ).order_by(RouteAssignment.rank_order)
        )
        assignment = assignment_result.scalars().first()
    return {
        "tracking_token": submission.tracking_token,
        "status": submission.status if not problem else problem.status,
        "category": problem.category if problem else None,
        "severity": str(problem.severity_score) if problem and problem.severity_score else None,
        "matched_university": assignment.university.name if assignment else None,
        "milestones": [],
    }


@api_router.get("/officer/review-queue")
async def review_queue(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("officer", "admin")),
):
    result = await db.execute(select(Problem).options(selectinload(Problem.submission)).where(Problem.status == "PENDING_OFFICER_REVIEW").offset(skip).limit(limit))
    return [{
        "id": str(problem.problem_id), "title": problem.title, "description": problem.summary,
        "category": problem.category, "severity": str(problem.severity_score or 1),
        "district": problem.submission.geo_district if problem.submission else "Unspecified",
        "status": problem.status, "sla_hours_remaining": 48, "top_matches": [],
    } for problem in result.scalars().all()]


@api_router.post("/officer/reviews/{problem_id}/decision")
async def decide_problem(problem_id: str, payload: DecisionRequest, request: Request, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("officer", "admin"))):
    if payload.decision not in {"APPROVE", "REJECT", "OVERRIDE"}:
        raise HTTPException(status_code=400, detail="Decision must be APPROVE, REJECT, or OVERRIDE")
    problem = await db.get(Problem, problem_id)
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
        university = await db.get(University, payload.override_university_id)
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


@api_router.get("/university/inbox")
async def university_inbox(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))):
    university_id = user.get("organization_id")
    if not university_id:
        raise HTTPException(status_code=403, detail="University account is not linked to a workspace")
    result = await db.execute(
        select(RouteAssignment).options(selectinload(RouteAssignment.problem)).where(
            RouteAssignment.status == "OFFERED",
            RouteAssignment.university_id == university_id,
        )
    )
    return [{"assignment_id": str(item.assignment_id), "problem_id": str(item.problem_id), "problem_title": item.problem.title, "match_score": item.match_score, "status": item.status} for item in result.scalars().all()]


@api_router.post("/university/assignments/{assignment_id}/respond")
async def respond_assignment(assignment_id: str, payload: AssignmentResponse, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("university"))):
    if payload.response not in {"ACCEPT", "DECLINE"}:
        raise HTTPException(status_code=400, detail="Response must be ACCEPT or DECLINE")
    assignment = await db.get(RouteAssignment, assignment_id)
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
    await db.commit()
    return {"status": "success"}


@api_router.get("/industry/opportunities")
async def csr_opportunities(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("industry"))):
    result = await db.execute(select(Problem).where(Problem.status == "ROUTED").limit(50))
    return [{"problem_id": str(p.problem_id), "title": p.title, "description": p.summary, "category": p.category, "match_score": p.confidence_score or 0.0} for p in result.scalars().all()]


@api_router.post("/industry/pledges", status_code=status.HTTP_201_CREATED)
async def create_pledge(payload: PledgeRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("industry"))):
    if payload.pledged_amount_inr <= 0:
        raise HTTPException(status_code=422, detail="Pledge amount must be greater than zero")
    if not user.get("organization_id"):
        raise HTTPException(status_code=403, detail="Industry account is not linked to a workspace")
    problem = await db.get(Problem, payload.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    if problem.status != "ROUTED":
        raise HTTPException(status_code=409, detail="Only routed problems can receive pledges")
    if payload.team_id:
        team = await db.get(ProjectTeam, payload.team_id)
        if not team or team.problem_id != problem.problem_id:
            raise HTTPException(status_code=422, detail="Team must belong to the pledged problem")
    pledge = FundingLink(
        problem_id=problem.problem_id,
        team_id=payload.team_id,
        industry_id=user["organization_id"],
        pledged_amount_inr=payload.pledged_amount_inr,
        status="PLEDGED",
    )
    db.add(pledge)
    await db.commit()
    await db.refresh(pledge)
    return {"id": str(pledge.link_id), "problem_id": str(pledge.problem_id), "amount": pledge.pledged_amount_inr, "status": pledge.status}


@api_router.get("/analytics/overview")
async def analytics_overview(db: AsyncSession = Depends(get_db)):
    submissions = (await db.execute(select(Submission))).scalars().all()
    return {"total_submissions": len(submissions), "triage_throughput": 0, "sla_compliance_percent": 100.0, "active_workers": 0, "category_distribution": {}, "district_distribution": {}, "severity_distribution": {}}

@api_router.post("/admin/reports/triage")
async def export_triage_report(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin", "officer"))):
    result = await db.execute(select(Problem).options(selectinload(Problem.submission)))
    rows = [{"submission_id": str(problem.submission_id), "timestamp_submitted": problem.created_at.isoformat(), "raw_text_preview": problem.summary[:200], "category": problem.category, "severity": problem.severity_score, "geo_district": problem.submission.geo_district if problem.submission else "", "triage_status": problem.status} for problem in result.scalars().all()]
    return {"path": write_triage_csv(rows), "count": len(rows)}
