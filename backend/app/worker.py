import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from app.config import get_settings

from app.workflows.triage_workflow import ChallengeTriageWorkflow
from app.workflows.media_workflow import MediaProcessingWorkflow
from app.workflows.weekly_batch import WeeklyBatchTriageWorkflow
from app.workflows.monthly_macro import MonthlyMacroTriageWorkflow
from app.workflows.sla_workflow import UniversitySLAWorkflow
from app.activities.extract import extract_submission_activity
from app.activities.extract import fetch_pending_batch_submissions_activity, batch_extract_and_embed_activity
from app.activities.classify import classify_and_embed_activity
from app.activities.dedup import check_deduplication_activity
from app.activities.route import route_to_universities_activity, global_university_routing_activity
from app.activities.cluster import cluster_and_deduplicate_batch_activity
from app.activities.report_gen import (
    generate_triage_csv_report_activity,
    generate_weekly_routing_pdf_report_activity,
    generate_csr_excel_export_activity,
)
from app.activities.notify import (
    notify_officers_weekly_digest_activity,
    send_sla_warning_activity,
    escalate_to_state_admin_activity,
)
from app.activities.media import (
    normalize_media_activity,
    scan_media_activity,
    transcribe_audio_activity,
)
from app.activities.macro import (
    apply_seasonal_weight_adjustments_activity,
    audit_officer_overrides_activity,
    recompute_theme_centroid_embeddings_activity,
    run_csr_matching_activity,
)

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
        workflows=[ChallengeTriageWorkflow, MediaProcessingWorkflow, WeeklyBatchTriageWorkflow, MonthlyMacroTriageWorkflow, UniversitySLAWorkflow],
        activities=[extract_submission_activity, classify_and_embed_activity, check_deduplication_activity, route_to_universities_activity, scan_media_activity, normalize_media_activity, transcribe_audio_activity, fetch_pending_batch_submissions_activity, batch_extract_and_embed_activity, cluster_and_deduplicate_batch_activity, global_university_routing_activity, generate_triage_csv_report_activity, generate_weekly_routing_pdf_report_activity, generate_csr_excel_export_activity, notify_officers_weekly_digest_activity, send_sla_warning_activity, escalate_to_state_admin_activity, audit_officer_overrides_activity, recompute_theme_centroid_embeddings_activity, apply_seasonal_weight_adjustments_activity, run_csr_matching_activity],
    )

    logger.info("Starting Temporal worker...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
