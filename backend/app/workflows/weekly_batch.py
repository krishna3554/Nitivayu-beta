from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

@workflow.defn
class WeeklyBatchTriageWorkflow:
    @workflow.run
    async def run(self, batch_id: str, cadence: str = "weekly", unassigned_only: bool = True) -> dict:
        batch_res = await workflow.execute_activity(
            "fetch_pending_batch_submissions_activity",
            {"batch_id": batch_id, "unassigned_only": unassigned_only},
            schedule_to_close_timeout=timedelta(minutes=5)
        )
        submission_ids = batch_res.get("submission_ids", [])
        
        extract_res = await workflow.execute_activity(
            "batch_extract_and_embed_activity",
            {"batch_id": batch_id, "submission_ids": submission_ids},
            schedule_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        processed_ids = extract_res.get("submission_ids", submission_ids)

        cluster_res = await workflow.execute_activity(
            "cluster_and_deduplicate_batch_activity",
            {"batch_id": batch_id, "submission_ids": processed_ids},
            schedule_to_close_timeout=timedelta(minutes=10)
        )

        route_res = await workflow.execute_activity(
            "global_university_routing_activity",
            {"batch_id": batch_id, "submission_ids": processed_ids},
            schedule_to_close_timeout=timedelta(minutes=10)
        )

        csv_res = await workflow.execute_activity(
            "generate_triage_csv_report_activity",
            {"batch_id": batch_id, "submission_ids": processed_ids},
            schedule_to_close_timeout=timedelta(minutes=5)
        )

        pdf_res = await workflow.execute_activity(
            "generate_weekly_routing_pdf_report_activity",
            {"batch_id": batch_id},
            schedule_to_close_timeout=timedelta(minutes=5)
        )

        notify_res = await workflow.execute_activity(
            "notify_officers_weekly_digest_activity",
            {"batch_id": batch_id},
            schedule_to_close_timeout=timedelta(minutes=2)
        )

        return {
            "batch_id": batch_id,
            "processed_count": route_res.get("routed", extract_res.get("count", 0)),
            "duplicates": len(cluster_res.get("merged", [])),
            "csv_report": csv_res.get("path"),
            "pdf_report": pdf_res.get("path"),
            "status": "COMPLETED"
        }
