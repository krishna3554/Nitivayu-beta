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

async def main():
    settings = get_settings()
    logger.info(f"Connecting to Temporal host at {settings.TEMPORAL_HOST}")
    
    client = await Client.connect(
        settings.TEMPORAL_HOST, 
        namespace=settings.TEMPORAL_NAMESPACE
    )
    
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
