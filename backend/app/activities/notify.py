from temporalio import activity

@activity.defn
async def send_sla_warning_activity(data: dict) -> dict:
    return {"status": "sent"}

@activity.defn
async def escalate_to_state_admin_activity(data: dict) -> dict:
    return {"status": "escalated"}

@activity.defn
async def notify_officers_weekly_digest_activity(data: dict) -> dict:
    return {"status": "sent"}
