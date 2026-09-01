from datetime import timedelta
from temporalio import workflow

@workflow.defn
class MonthlyMacroTriageWorkflow:
    @workflow.run
    async def run(self) -> dict:
        audit_res = await workflow.execute_activity(
            "audit_officer_overrides_activity",
            schedule_to_close_timeout=timedelta(minutes=10)
        )
        
        recompute_res = await workflow.execute_activity(
            "recompute_theme_centroid_embeddings_activity",
            schedule_to_close_timeout=timedelta(minutes=15)
        )
        
        weights_res = await workflow.execute_activity(
            "apply_seasonal_weight_adjustments_activity",
            schedule_to_close_timeout=timedelta(minutes=5)
        )
        
        csr_res = await workflow.execute_activity(
            "run_csr_matching_activity",
            schedule_to_close_timeout=timedelta(minutes=10)
        )
        
        export_res = await workflow.execute_activity(
            "generate_csr_excel_export_activity",
            schedule_to_close_timeout=timedelta(minutes=5)
        )
        
        return {"status": "SUCCESS"}
