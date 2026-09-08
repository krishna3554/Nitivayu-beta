import logging

from sqlalchemy import select
from temporalio import activity

from app.config import get_settings
from app.db.models import BatchRun, Problem, Submission
from app.db.worker_session import worker_session
from app.services.triage_state import PRE_DECISION_STATUSES, audit_once, load_submission_problem

logger = logging.getLogger(__name__)


@activity.defn
async def cluster_and_deduplicate_batch_activity(data: dict) -> dict:
    """Cross-district agglomerative clustering over batch embeddings.

    Union-find on cosine similarity (>= DEDUP_SIMILARITY_THRESHOLD): members
    share a cluster_group_id; the newest duplicate of a cluster merges into
    the oldest (status MERGED, pre-decision rows only — officer decisions win).
    """
    from app.activities.route import _cosine_similarity

    payload = data or {}
    batch_id = payload.get("batch_id", "")
    ids = list(payload.get("submission_ids") or [])
    threshold = float(get_settings().DEDUP_SIMILARITY_THRESHOLD)
    async with worker_session() as session:
        problems: list[Problem] = []
        for submission_id in ids:
            submission, problem = await load_submission_problem(session, str(submission_id))
            if problem is not None and problem.summary_embedding is not None:
                problems.append(problem)
        parent = {i: i for i in range(len(problems))}

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        for i in range(len(problems)):
            for j in range(i + 1, len(problems)):
                sim = _cosine_similarity(problems[i].summary_embedding, problems[j].summary_embedding)
                if sim is not None and sim >= threshold:
                    union(i, j)
        clusters: dict[int, list[int]] = {}
        for i in range(len(problems)):
            clusters.setdefault(find(i), []).append(i)
        merged: list[str] = []
        multi = sum(1 for members in clusters.values() if len(members) > 1)
        for members in clusters.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda i: problems[i].created_at or problems[i].problem_id)
            group_id = f"cluster-{batch_id}-{members[0]}" if batch_id else f"cluster-{members[0]}"
            for i in members:
                problems[i].cluster_group_id = group_id
            for i in members[1:]:
                dup = problems[i]
                if dup.status in PRE_DECISION_STATUSES:
                    dup.is_duplicate = True
                    dup.duplicate_of_id = problems[members[0]].problem_id
                    dup.status = "MERGED"
                    submission = await session.get(Submission, dup.submission_id)
                    if submission is not None and submission.status in PRE_DECISION_STATUSES:
                        submission.status = "MERGED"
                    merged.append(str(dup.problem_id))
            for i in members:
                await audit_once(
                    session, entity_type="problem", entity_id=str(problems[i].problem_id),
                    action="BATCH_CLUSTERED", actor_role="worker",
                    after={"batch_id": batch_id, "cluster": group_id, "merged": str(problems[i].problem_id) in merged},
                )
        if batch_id:
            run = await session.get(BatchRun, batch_id)
            if run is not None:
                run.duplicates = len(merged)
        await session.commit()
    logger.info("Batch %s clustering: %d problems, %d multi clusters, %d merged", batch_id, len(problems), multi, len(merged))
    return {"batch_id": batch_id, "clustered": len(problems), "clusters": multi, "merged": merged}
