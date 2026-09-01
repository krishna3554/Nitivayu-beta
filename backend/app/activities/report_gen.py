from temporalio import activity
import datetime

@activity.defn
async def generate_triage_csv_report_activity(data: dict) -> dict:
    return {"path": "/app/output/triage/Nitivayu_triage.csv"}

@activity.defn
async def generate_weekly_routing_pdf_report_activity(data: dict) -> dict:
    return {"path": "/app/output/reports/Nitivayu_routing.pdf"}

@activity.defn
async def generate_csr_excel_export_activity(data: dict) -> dict:
    return {"path": "/app/output/csr/Nitivayu_csr.xlsx"}
