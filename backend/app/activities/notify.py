"""Worker-side notifications: officer digests + university SLA warnings.

Delivery is real email (SMTP) to the addresses already on file — officers by
their login emails, universities by their nodal contact — whenever SMTP is
configured; otherwise the intent is logged, never faked (WP-9).
"""

import logging

from sqlalchemy import func, select
from temporalio import activity

from app.db.models import BatchRun, Officer, Problem, RouteAssignment, Submission
from app.db.worker_session import worker_session
from app.services.triage_state import audit_once

logger = logging.getLogger(__name__)


@activity.defn
async def send_sla_warning_activity(data: dict) -> dict:
    """Warn path for a university assignment approaching its SLA deadline."""
    payload = data or {}
    assignment_id = payload.get("assignment_id")
    if not assignment_id:
        from temporalio.exceptions import ApplicationError

        raise ApplicationError("SLA warning requires an assignment_id", non_retryable=True)
    from app.services import notify as notify_svc

    sent = False
    async with worker_session() as session:
        assignment = await session.get(RouteAssignment, assignment_id)
        if assignment is None:
            from temporalio.exceptions import ApplicationError

            raise ApplicationError("Assignment not found", non_retryable=True)
        problem = await session.get(Problem, assignment.problem_id)
        university_name = ""
        nodal_email = None
        try:
            from app.db.models import University

            university = await session.get(University, assignment.university_id)
            university_name = university.name if university else ""
            nodal_email = university.nodal_contact_email if university else None
        except Exception:
            university_name = ""
        message = (
            f"Nitivayu SLA warning: '{problem.title if problem else assignment_id}' "
            f"awaiting your decision at {university_name}; deadline {assignment.sla_deadline}."
        )
        logger.warning("SLA warning: assignment %s (%s) at %s nears deadline %s",
                       assignment_id, problem.title if problem else "?", university_name, assignment.sla_deadline)
        if nodal_email:
            sent = await notify_svc.send_email(nodal_email, "Nitivayu: assignment nearing its SLA deadline", message)
        await audit_once(
            session, entity_type="assignment", entity_id=str(assignment_id),
            action="SLA_WARNING", actor_role="worker",
            after={"university": university_name, "deadline": assignment.sla_deadline.isoformat() if assignment.sla_deadline else None, "emailed": sent},
        )
        await session.commit()
    return {"sent": sent, "assignment_id": str(assignment_id)}


@activity.defn
async def escalate_to_state_admin_activity(data: dict) -> dict:
    """Escalate an unanswered assignment out of the university queue."""
    payload = data or {}
    assignment_id = payload.get("assignment_id")
    if not assignment_id:
        from temporalio.exceptions import ApplicationError

        raise ApplicationError("Escalation requires an assignment_id", non_retryable=True)
    async with worker_session() as session:
        assignment = await session.get(RouteAssignment, assignment_id)
        if assignment is None:
            from temporalio.exceptions import ApplicationError

            raise ApplicationError("Assignment not found", non_retryable=True)
        assignment.status = "ESCALATED"
        problem = await session.get(Problem, assignment.problem_id)
        if problem is not None:
            problem.status = "ESCALATED"
        await audit_once(
            session, entity_type="assignment", entity_id=str(assignment_id),
            action="SLA_ESCALATED", actor_role="worker", after={"problem_id": str(assignment.problem_id)},
        )
        await session.commit()
    # Senior officers are emailed on every escalation when SMTP is on.
    from app.services import notify as notify_svc

    admins = []
    async with worker_session() as session:
        admins = (await session.execute(
            select(Officer.email).where(Officer.role.in_(["state_admin", "senior_officer"]))
        )).scalars().all()
    emailed = 0
    for address in [a for a in admins if a]:
        if await notify_svc.send_email(
            address, "Nitivayu: assignment escalated to state admin",
            f"Assignment {assignment_id} went unanswered past its SLA window and was escalated for your review.",
        ):
            emailed += 1
    logger.error("SLA escalation: assignment %s moved out of the university queue (%d admin emails)", assignment_id, emailed)
    return {"escalated": True, "assignment_id": str(assignment_id), "admins_emailed": emailed}


@activity.defn
async def notify_officers_weekly_digest_activity(data: dict) -> dict:
    """Officer digest for one batch run: counts + report paths, logged."""
    payload = data or {}
    batch_id = payload.get("batch_id", "")
    async with worker_session() as session:
        officers = (await session.execute(select(func.count(Officer.officer_id)))).scalar_one()
        pending_review = (
            await session.execute(select(func.count(Problem.problem_id)).where(Problem.status == "PENDING_OFFICER_REVIEW"))
        ).scalar_one()
        run = await session.get(BatchRun, batch_id) if batch_id else None
        processed = (run.processed or 0) if run else 0
        duplicates = (run.duplicates or 0) if run else 0
        if run is not None and run.status == "RUNNING":
            run.status = "COMPLETED"
            from datetime import datetime, timezone

            run.finished_at = datetime.now(timezone.utc)
        if batch_id:
            await audit_once(
                session, entity_type="batch", entity_id=batch_id,
                action="BATCH_DIGESTED", actor_role="worker",
                after={"processed": processed, "officers": officers},
            )
        await session.commit()
    digest = (
        f"Nitivayu weekly triage digest (batch {batch_id or 'adhoc'}):\n"
        f"- {processed} processed ({duplicates} duplicates)\n"
        f"- {pending_review} awaiting officer review\n"
        f"- reports: {run.csv_path if run else '-'} / {run.pdf_path if run else '-'}"
    )
    logger.info("Weekly digest (batch %s): %s", batch_id, digest.replace("\n", " "))
    from app.services import notify as notify_svc

    emailed = 0
    async with worker_session() as session:
        addresses = (await session.execute(select(Officer.email))).scalars().all()
    for address in [a for a in addresses if a]:
        if await notify_svc.send_email(address, f"Nitivayu weekly digest — batch {batch_id or 'adhoc'}", digest):
            emailed += 1
    return {"batch_id": batch_id, "officers_notified": emailed, "processed": processed}
