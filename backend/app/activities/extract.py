from temporalio import activity
from temporalio.exceptions import ApplicationError

from sqlalchemy import select

from app.config import get_settings
from app.db.models import BatchRun, Submission
from app.db.worker_session import worker_session
from app.services.embeddings import embed_text
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
async def fetch_pending_batch_submissions_activity(data: dict) -> dict:
    """Collect the batch window: unprocessed intake, oldest first, capped."""
    payload = data or {}
    batch_id = payload.get("batch_id", "")
    unassigned_only = payload.get("unassigned_only", True)
    limit = int(get_settings().BATCH_MAX_SUBMISSIONS)
    statuses = ("PENDING_TRIAGE",) if unassigned_only else ("PENDING_TRIAGE", "PENDING_OFFICER_REVIEW")
    async with worker_session() as session:
        submissions = (
            await session.execute(
                select(Submission)
                .where(Submission.status.in_(statuses))
                .order_by(Submission.created_at.asc())
                .limit(limit)
            )
        ).scalars().all()
        ids = [str(s.submission_id) for s in submissions]
        if batch_id:
            # WP-11: stamp batch membership so submissions.batch_id is live
            # data instead of a never-written column.
            for submission in submissions:
                submission.batch_id = batch_id
            run = await session.get(BatchRun, batch_id)
            if run is not None:
                run.total = len(ids)
            await session.commit()
    return {"batch_id": batch_id, "submission_ids": ids, "count": len(ids)}


@activity.defn
async def batch_extract_and_embed_activity(data: dict) -> dict:
    """Run extraction + embedding over the batch window.

    Per-item failures are recorded and skipped (never fail the whole batch).
    Mirrors the real-time extract/classify rules so batch and live agree.
    """
    from app.services.llm import canonicalize_category

    payload = data or {}
    batch_id = payload.get("batch_id", "")
    ids = list(payload.get("submission_ids") or [])
    processed: list[str] = []
    failed: list[dict] = []
    async with worker_session() as session:
        for submission_id in ids:
            # SAVEPOINT per item: a poisoned statement aborts only this item,
            # never the whole batch (one bad row must not fail twelve).
            nested = await session.begin_nested()
            try:
                submission, problem = await load_submission_problem(session, str(submission_id))
                extraction = await extract_issue_details(submission.raw_text or "")
                embedding = embed_text(" ".join(str(extraction.get("summary") or "").split()))
                advance_status(submission, "TRIAGING")
                if problem is not None and problem.status in {
                    "INGESTED", "PENDING_TRIAGE", "TRIAGING",
                    "PENDING_OFFICER_REVIEW", "OFFICER_REVIEW",
                }:
                    problem.title = extraction["title"]
                    problem.summary = extraction["summary"]
                    problem.category = extraction["category"]
                    problem.severity_score = extraction["severity"]
                    problem.summary_embedding = embedding
                    problem.confidence_score = 0.85
                    if not problem.category or problem.category == "Governance":
                        problem.category = canonicalize_category(extraction["category"])
                await audit_once(
                    session, entity_type="submission", entity_id=str(submission.submission_id),
                    action="BATCH_EXTRACTED", actor_role="worker",
                    after={"batch_id": batch_id, "category": extraction.get("category")},
                )
                processed.append(str(submission_id))
            except Exception as exc:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "Batch %s item %s failed: %s", batch_id, submission_id, exc, exc_info=True
                )
                try:
                    await nested.rollback()
                except Exception:
                    pass
                failed.append({"submission_id": str(submission_id), "error": str(exc)[:200]})
            else:
                try:
                    await nested.commit()
                except Exception:
                    pass
        if batch_id:
            run = await session.get(BatchRun, batch_id)
            if run is not None:
                run.processed = len(processed)
                run.failed = len(failed)
        await session.commit()
    return {"batch_id": batch_id, "count": len(processed), "failed": failed, "submission_ids": processed}
