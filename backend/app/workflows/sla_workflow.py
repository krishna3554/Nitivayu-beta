from datetime import timedelta
from temporalio import workflow

@workflow.defn
class UniversitySLAWorkflow:
    def __init__(self):
        self.university_decision = None

    @workflow.signal
    def university_acceptance_signal(self, decision: str):
        self.university_decision = decision

    @workflow.run
    async def run(self, assignment_id: str, university_list: list) -> dict:
        for idx, uni in enumerate(university_list):
            self.university_decision = None
            try:
                # wait up to 5 days, if 2 days left send warning
                await workflow.wait_condition(
                    lambda: self.university_decision is not None,
                    timeout=timedelta(days=5)
                )
            except workflow.TimeoutError:
                await workflow.execute_activity(
                    "send_sla_warning_activity",
                    {"assignment_id": assignment_id, "university": uni},
                    schedule_to_close_timeout=timedelta(minutes=1)
                )
                try:
                    await workflow.wait_condition(
                        lambda: self.university_decision is not None,
                        timeout=timedelta(days=2)
                    )
                except workflow.TimeoutError:
                    self.university_decision = "decline"
            
            if self.university_decision == "accept":
                return {"status": "ACCEPTED", "university": uni}
        
        await workflow.execute_activity(
            "escalate_to_state_admin_activity",
            {"assignment_id": assignment_id},
            schedule_to_close_timeout=timedelta(minutes=1)
        )
        return {"status": "ESCALATED"}
