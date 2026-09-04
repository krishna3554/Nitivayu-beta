from temporalio import activity
from temporalio.exceptions import ApplicationError


@activity.defn
async def send_sla_warning_activity(data: dict) -> dict:
    raise ApplicationError(
        "SLA notifications are not implemented on the triage worker",
        non_retryable=True,
    )


@activity.defn
async def escalate_to_state_admin_activity(data: dict) -> dict:
    raise ApplicationError(
        "SLA escalation is not implemented on the triage worker",
        non_retryable=True,
    )


@activity.defn
async def notify_officers_weekly_digest_activity(data: dict) -> dict:
    raise ApplicationError(
        "Weekly officer digests are not implemented on the triage worker",
        non_retryable=True,
    )
