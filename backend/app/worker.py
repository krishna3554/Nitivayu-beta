import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from app.config import get_settings

# Import workflows and activities when created
# from app.workflows import ...
# from app.activities import ...

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
        task_queue="nitivayu-triage-queue",
        workflows=[], # TODO: Register workflows
        activities=[], # TODO: Register activities
    )
    
    logger.info("Starting Temporal worker...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
