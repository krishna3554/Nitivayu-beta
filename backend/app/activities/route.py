import math

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.db.models import University
from app.db.worker_session import worker_session
from app.services.triage_state import (
    PRE_DECISION_STATUSES,
    advance_status,
    audit_once,
    load_submission_problem,
    replace_auto_route_offers,
)


def _cosine_similarity(left, right) -> float | None:
    try:
        left_values = [float(value) for value in list(left)]
        right_values = [float(value) for value in list(right)]
    except (TypeError, ValueError):
        return None
    if len(left_values) != len(right_values) or not left_values:
        return None
    if any(not math.isfinite(value) for value in left_values + right_values):
        return None
    denominator = math.sqrt(sum(value * value for value in left_values)) * math.sqrt(
        sum(value * value for value in right_values)
    )
    if denominator == 0:
        return None
    return sum(a * b for a, b in zip(left_values, right_values)) / denominator


def score_universities(category: str, summary: str, district: str | None, embedding, universities) -> list[dict]:
    """Deterministically score universities; explainable via ``score_breakdown``."""
    category_token = (category or "").strip().lower()
    summary_words = {word for word in (summary or "").lower().split() if len(word) > 4}
    scored = []
    for university in universities:
        available = (university.active_capacity or 0) - (university.current_load or 0)
        if available <= 0:
            continue
        profile = " ".join([university.name or "", university.district or "", *list(university.domain_specializations or [])]).lower()
        if category_token and category_token in profile:
            theme = 1.0
        elif summary_words and any(word in profile for word in summary_words):
            theme = 0.7
        else:
            theme = 0.3
        semantic = _cosine_similarity(embedding, university.capability_embedding)
        semantic_score = round(max(0.0, min(1.0, (semantic + 1.0) / 2.0)), 4) if semantic is not None else 0.5
        capacity = round(max(0.0, min(1.0, available / max(university.active_capacity or 1, 1))), 4)
        geo = 1.0 if district and university.district == district else 0.5
        match_score = round(0.4 * theme + 0.3 * semantic_score + 0.2 * capacity + 0.1 * geo, 4)
        scored.append(
            {
                "university_id": str(university.university_id),
                "university_name": university.name,
                "match_score": match_score,
                "score_breakdown": {"semantic": semantic_score, "theme": theme, "capacity": capacity, "geo": geo},
            }
        )
    scored.sort(key=lambda item: (-item["match_score"], item["university_name"]))
    return scored


@activity.defn
async def route_to_universities_activity(data: dict) -> dict:
    payload = data or {}
    submission_id = payload.get("submission_id")
    if not submission_id:
        raise ApplicationError("Routing requires a submission_id", non_retryable=True)

    async with worker_session() as session:
        submission, problem = await load_submission_problem(session, str(submission_id))
        if problem is None:
            raise ApplicationError("Problem not found for submission", non_retryable=True)
        universities = (await session.execute(select(University).order_by(University.name))).scalars().all()
        ranked = score_universities(
            problem.category,
            problem.summary,
            submission.geo_district,
            problem.summary_embedding,
            universities,
        )
        offers = ranked[:3]
        if offers and problem.status in PRE_DECISION_STATUSES:
            await replace_auto_route_offers(session, problem=problem, offers=offers)
            advance_status(submission, "OFFICER_REVIEW")
        await audit_once(
            session,
            entity_type="problem",
            entity_id=str(problem.problem_id),
            action="TRIAGE_ROUTED",
            actor_role="worker",
            after={"offers": [{k: offer[k] for k in ("university_id", "match_score")} for offer in offers] or "NO_CAPACITY"},
        )
        await session.commit()

    top = {offer["university_name"]: offer["match_score"] for offer in offers}
    return {"top_3": [offer["university_name"] for offer in offers], "scores": top}


@activity.defn
async def global_university_routing_activity(data: dict) -> dict:
    raise ApplicationError(
        "Global batch routing is not implemented on the triage worker",
        non_retryable=True,
    )
