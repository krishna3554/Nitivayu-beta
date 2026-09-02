from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities.extract import extract_submission_activity
    from app.activities.classify import classify_and_embed_activity
    from app.activities.dedup import check_deduplication_activity
    from app.activities.route import route_to_universities_activity

@workflow.defn
class ChallengeTriageWorkflow:
    def __init__(self):
        self.officer_decision = None

    @workflow.signal
    def officer_approval_signal(self, decision: str):
        self.officer_decision = decision

    @workflow.run
    async def run(self, submission_id: str, raw_text: str, district: str) -> dict:
        # 1. Extract
        extraction_res = await workflow.execute_activity(
            extract_submission_activity,
            {"raw_text": raw_text},
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy={"maximum_attempts": 3}
        )

        # 2. Classify and Embed
        classification_res = await workflow.execute_activity(
            classify_and_embed_activity,
            {"summary": extraction_res["summary"]},
            schedule_to_close_timeout=timedelta(minutes=1)
        )

        # 3. Deduplication
        dedup_res = await workflow.execute_activity(
            check_deduplication_activity,
            {"embedding": classification_res["embedding"], "district": district},
            schedule_to_close_timeout=timedelta(minutes=1)
        )

        if dedup_res["is_duplicate"]:
            return {"status": "DUPLICATE", "duplicate_of": dedup_res["duplicate_id"]}

        # 4. Route
        route_res = await workflow.execute_activity(
            route_to_universities_activity,
            {
                "submission_id": submission_id,
                "embedding": classification_res["embedding"],
                "theme": classification_res["top_category"],
                "district": district
            },
            schedule_to_close_timeout=timedelta(minutes=2)
        )

        # Wait for officer signal (72h timeout)
        try:
            await workflow.wait_condition(
                lambda: self.officer_decision is not None,
                timeout=timedelta(hours=72)
            )
        except workflow.TimeoutError:
            self.officer_decision = "escalate"

        if self.officer_decision == "approve":
            return {"status": "ROUTED_TO_UNIVERSITY"}
        elif self.officer_decision == "reject":
            return {"status": "REJECTED"}
        else:
            return {"status": "ESCALATED_TO_SENIOR_OFFICER"}
