"""Monthly macro triage (WP-11, repaired): override audit → theme centroids →
seasonal weights → CSR matching → CSR matrix export.

Previously referenced four activities that did not exist and invoked the CSR
export without its required argument — the workflow could never run.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities.macro import (
        apply_seasonal_weight_adjustments_activity,
        audit_officer_overrides_activity,
        recompute_theme_centroid_embeddings_activity,
        run_csr_matching_activity,
    )
    from app.activities.report_gen import generate_csr_excel_export_activity


@workflow.defn
class MonthlyMacroTriageWorkflow:
    @workflow.run
    async def run(self, month: str | None = None) -> dict:
        payload = {"month": month} if month else {}
        audit_res = await workflow.execute_activity(
            audit_officer_overrides_activity,
            payload,
            schedule_to_close_timeout=timedelta(minutes=10),
        )

        recompute_res = await workflow.execute_activity(
            recompute_theme_centroid_embeddings_activity,
            payload,
            schedule_to_close_timeout=timedelta(minutes=15),
        )

        weights_res = await workflow.execute_activity(
            apply_seasonal_weight_adjustments_activity,
            payload,
            schedule_to_close_timeout=timedelta(minutes=5),
        )

        csr_res = await workflow.execute_activity(
            run_csr_matching_activity,
            payload,
            schedule_to_close_timeout=timedelta(minutes=10),
        )

        export_res = await workflow.execute_activity(
            generate_csr_excel_export_activity,
            {"industry_id": None},
            schedule_to_close_timeout=timedelta(minutes=5),
        )

        return {
            "status": "SUCCESS",
            "overrides": audit_res.get("count", 0),
            "centroid_categories": recompute_res.get("categories", 0),
            "seasonal_weights": weights_res.get("weights", {}),
            "csr_suggested": csr_res.get("suggested", 0),
            "csr_export": export_res.get("path"),
        }
