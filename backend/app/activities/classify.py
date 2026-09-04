from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.db.worker_session import worker_session
from app.services.embeddings import embed_text
from app.services.llm import canonicalize_category
from app.services.triage_state import audit_once, load_submission_problem


@activity.defn
async def classify_and_embed_activity(data: dict) -> dict:
    summary = (data or {}).get("summary", "")
    submission_id = (data or {}).get("submission_id")
    cleaned = " ".join(str(summary or "").split())
    if not cleaned:
        raise ApplicationError("Cannot classify blank summary", non_retryable=True)
    try:
        embedding = embed_text(cleaned)
    except ValueError as exc:
        raise ApplicationError(str(exc), non_retryable=True) from exc
    except RuntimeError as exc:
        # Model/config failures are observable; the workflow retry policy bounds retries.
        raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    category = canonicalize_category(cleaned)
    if submission_id:
        async with worker_session() as session:
            submission, problem = await load_submission_problem(session, str(submission_id))
            if problem is not None and problem.status in {
                "INGESTED",
                "PENDING_TRIAGE",
                "TRIAGING",
                "PENDING_OFFICER_REVIEW",
                "OFFICER_REVIEW",
            }:
                problem.summary_embedding = embedding
                problem.confidence_score = 0.85
                # The extraction stage owns the category; only fill it in when
                # the stored value is still the unset/API fallback default.
                if not problem.category or problem.category == "Governance":
                    problem.category = category
                else:
                    category = canonicalize_category(problem.category)
            await audit_once(
                session,
                entity_type="submission",
                entity_id=str(submission.submission_id),
                action="TRIAGE_CLASSIFIED",
                actor_role="worker",
                after={"category": category},
            )
            await session.commit()

    return {
        "top_category": category,
        "confidence": 0.85,
        "embedding": embedding,
    }
