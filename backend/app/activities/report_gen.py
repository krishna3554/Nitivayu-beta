from temporalio import activity
from temporalio.exceptions import ApplicationError


@activity.defn
async def generate_triage_csv_report_activity(data: dict) -> dict:
    raise ApplicationError(
        "Batch triage reports are not implemented on the triage worker",
        non_retryable=True,
    )


@activity.defn
async def generate_weekly_routing_pdf_report_activity(data: dict) -> dict:
    raise ApplicationError(
        "Batch routing reports are not implemented on the triage worker",
        non_retryable=True,
    )


@activity.defn
async def generate_csr_excel_export_activity(data: dict) -> dict:
    raise ApplicationError(
        "CSR exports are not implemented on the triage worker",
        non_retryable=True,
    )
