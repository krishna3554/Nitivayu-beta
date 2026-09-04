import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from app.config import get_settings

from app.workflows.triage_workflow import ChallengeTriageWorkflow
from app.activities.extract import extract_submission_activity
from app.activities.classify import classify_and_embed_activity
from app.activities.dedup import check_deduplication_activity
from app.activities.route import route_to_universities_activity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONNECT_ATTEMPTS = 12
CONNECT_BACKOFF_SECONDS = 5


async def connect_with_retry(settings) -> Client:
    """Connect to Temporal with bounded retries instead of crashing immediately."""
    last_error: Exception | None = None
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            return await Client.connect(
                settings.TEMPORAL_HOST,
                namespace=settings.TEMPORAL_NAMESPACE,
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Temporal connection attempt %s/%s failed; retrying in %ss",
                attempt,
                CONNECT_ATTEMPTS,
                CONNECT_BACKOFF_SECONDS,
            )
            await asyncio.sleep(CONNECT_BACKOFF_SECONDS)
    raise RuntimeError(f"Could not connect to Temporal at {settings.TEMPORAL_HOST}") from last_error


async def main():
    settings = get_settings()
    logger.info(f"Connecting to Temporal host at {settings.TEMPORAL_HOST}")

    client = await connect_with_retry(settings)

    worker = Worker(
        client,
        task_queue="triage-queue",
        workflows=[ChallengeTriageWorkflow],
        activities=[extract_submission_activity, classify_and_embed_activity, check_deduplication_activity, route_to_universities_activity],
    )

    logger.info("Starting Temporal worker...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
