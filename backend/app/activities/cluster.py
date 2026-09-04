from temporalio import activity
from temporalio.exceptions import ApplicationError


@activity.defn
async def cluster_and_deduplicate_batch_activity(data: dict) -> dict:
    raise ApplicationError(
        "Batch clustering is not implemented on the triage worker",
        non_retryable=True,
    )
