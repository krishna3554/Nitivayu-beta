from datetime import timedelta
from temporalio import workflow

@workflow.defn
class WeeklyBatchTriageWorkflow:
    @workflow.run
    async def run(self, batch_id: str) -> dict:
        batch_res = await workflow.execute_activity(
            "fetch_pending_batch_submissions_activity",
            {"batch_id": batch_id},
            schedule_to_close_timeout=timedelta(minutes=5)
        )
        
        extract_res = await workflow.execute_activity(
            "batch_extract_and_embed_activity",
            {"batch_id": batch_id},
            schedule_to_close_timeout=timedelta(minutes=15),
            retry_policy={"maximum_attempts": 3}
        )
        
        cluster_res = await workflow.execute_activity(
            "cluster_and_deduplicate_batch_activity",
            {"batch_id": batch_id},
            schedule_to_close_timeout=timedelta(minutes=10)
        )
        
        route_res = await workflow.execute_activity(
            "global_university_routing_activity",
            {"batch_id": batch_id},
            schedule_to_close_timeout=timedelta(minutes=10)
        )
        
        csv_res = await workflow.execute_activity(
            "generate_triage_csv_report_activity",
            {"batch_id": batch_id},
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
            "processed_count": extract_res["count"],
            "csv_report": csv_res["path"],
            "pdf_report": pdf_res["path"],
            "status": "COMPLETED"
        }
