import math

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.config import get_settings
from app.db.models import Problem
from app.db.worker_session import worker_session
from app.services.embeddings import EMBEDDING_DIMENSIONS
from app.services.triage_state import PRE_DECISION_STATUSES, audit_once, load_submission_problem


def _validate_embedding(value) -> list[float]:
    values = list(value or [])
    if len(values) != EMBEDDING_DIMENSIONS or any(
        not isinstance(item, (int, float)) or not math.isfinite(item) for item in values
    ):
        raise ApplicationError("Deduplication requires a valid 384-dimensional embedding", non_retryable=True)
    return [float(item) for item in values]


@activity.defn
async def check_deduplication_activity(data: dict) -> dict:
    payload = data or {}
    embedding = _validate_embedding(payload.get("embedding"))
    submission_id = payload.get("submission_id")
    if not submission_id:
        raise ApplicationError("Deduplication requires a submission_id", non_retryable=True)
    threshold = float(get_settings().DEDUP_SIMILARITY_THRESHOLD)
    if not 0.0 < threshold <= 1.0:
        raise ApplicationError("DEDUP_SIMILARITY_THRESHOLD must be within (0, 1]", non_retryable=True)
    max_distance = 1.0 - threshold

    async with worker_session() as session:
        submission, problem = await load_submission_problem(session, str(submission_id))
        if problem is None:
            raise ApplicationError("Problem not found for submission", non_retryable=True)
        distance_column = Problem.summary_embedding.cosine_distance(embedding).label("distance")
        nearest = (
            await session.execute(
                select(Problem, distance_column)
                .where(
                    Problem.problem_id != problem.problem_id,
                    Problem.summary_embedding.is_not(None),
                )
                .order_by(distance_column)
                .limit(1)
            )
        ).first()
        duplicate_id: str | None = None
        if nearest is not None:
            candidate, distance = nearest
            if distance is not None and float(distance) <= max_distance:
                duplicate_id = str(candidate.problem_id)

        if duplicate_id is not None and problem.status in PRE_DECISION_STATUSES:
            problem.is_duplicate = True
            problem.duplicate_of_id = candidate.problem_id
            problem.status = "MERGED"
            if submission.status in PRE_DECISION_STATUSES:
                submission.status = "MERGED"
        await audit_once(
            session,
            entity_type="problem",
            entity_id=str(problem.problem_id),
            action="TRIAGE_DEDUP_CHECKED",
            actor_role="worker",
            after={"is_duplicate": duplicate_id is not None, "duplicate_of": duplicate_id},
        )
        await session.commit()

    return {"is_duplicate": duplicate_id is not None, "duplicate_id": duplicate_id}
