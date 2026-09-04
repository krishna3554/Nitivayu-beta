from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.db.worker_session import worker_session
from app.services.llm import extract_issue_details
from app.services.triage_state import advance_status, audit_once, load_submission_problem


@activity.defn
async def extract_submission_activity(data: dict) -> dict:
    raw_text = (data or {}).get("raw_text", "")
    submission_id = (data or {}).get("submission_id")
    try:
        extraction = await extract_issue_details(raw_text)
    except ValueError as exc:
        raise ApplicationError(str(exc), non_retryable=True) from exc

    if submission_id:
        async with worker_session() as session:
            submission, problem = await load_submission_problem(session, str(submission_id))
            advance_status(submission, "TRIAGING")
            if problem is not None and problem.status in {
                "INGESTED",
                "PENDING_TRIAGE",
                "TRIAGING",
                "PENDING_OFFICER_REVIEW",
                "OFFICER_REVIEW",
            }:
                problem.title = extraction["title"]
                problem.summary = extraction["summary"]
                problem.category = extraction["category"]
                problem.severity_score = extraction["severity"]
            await audit_once(
                session,
                entity_type="submission",
                entity_id=str(submission.submission_id),
                action="TRIAGE_EXTRACTED",
                actor_role="worker",
                after={"category": extraction["category"], "source": extraction["source"]},
            )
            await session.commit()

    return {
        "title": extraction["title"],
        "summary": extraction["summary"],
        "category": extraction["category"],
        "severity": extraction["severity"],
        "location_hint": extraction["location_hint"],
        "source": extraction["source"],
    }


@activity.defn
async def batch_extract_and_embed_activity(data: dict) -> dict:
    raise ApplicationError(
        "Batch extraction is not implemented on the triage worker",
        non_retryable=True,
    )
