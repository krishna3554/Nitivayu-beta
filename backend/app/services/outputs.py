"""Append-only operational artefacts required by the LokSetu output specification."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def _output_root() -> Path:
    try:
        from app.config import get_settings

        return Path(get_settings().OUTPUT_ROOT)
    except Exception:
        import os as _os

        return Path(_os.getenv("OUTPUT_ROOT", "/app/output"))


# Kept as a module attr for tests that monkeypatch outputs.OUTPUT_ROOT.
OUTPUT_ROOT = _output_root()

def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

def append_audit(event: dict) -> str:
    directory = OUTPUT_ROOT / "audit"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"loksetu_audit_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **event}, default=str) + "\n")
    return str(path)

def write_triage_csv(rows: list[dict]) -> str:
    directory = OUTPUT_ROOT / "triage"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"loksetu_triage_{utc_stamp()}.csv"
    headers = ["submission_id", "timestamp_submitted", "raw_text_preview", "category", "severity", "geo_district", "triage_status"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader(); writer.writerows(rows)
    return str(path)


def write_sla_log(rows: list[dict], name: str = "") -> str:
    """SLA & escalation log export (CSV)."""
    directory = OUTPUT_ROOT / "sla"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (f"{name}_{utc_stamp()}.csv" if name else f"sla_log_{utc_stamp()}.csv")
    headers = ["timestamp", "entity_type", "entity_id", "action", "actor_role", "detail"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader(); writer.writerows(rows)
    return str(path)


def write_audit_jsonl(rows: list[dict], name: str = "") -> str:
    """System audit log export (JSONL, one row per line)."""
    directory = OUTPUT_ROOT / "audit"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (f"{name}_{utc_stamp()}.jsonl" if name else f"audit_export_{utc_stamp()}.jsonl")
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, default=str) + "\n")
    return str(path)


def write_routing_pdf(lines: list[str], title: str, name: str = "") -> str:
    """Department routing briefing (PDF). Shared by the batch worker activity
    and the on-demand admin export — single implementation."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    directory = OUTPUT_ROOT / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (f"{name}_{utc_stamp()}.pdf" if name else f"routing_report_{utc_stamp()}.pdf")
    doc = canvas.Canvas(str(path), pagesize=A4)
    doc.setTitle(title)
    text = doc.beginText(20 * mm, 270 * mm)
    text.setFont("Helvetica", 10)
    for line in lines:
        for chunk in [line[i:i + 100] for i in range(0, max(len(line), 1), 100)] or [""]:
            if text.getY() < 20 * mm:
                doc.drawText(text)
                doc.showPage()
                text = doc.beginText(20 * mm, 270 * mm)
                text.setFont("Helvetica", 10)
            text.textLine(chunk)
    doc.drawText(text)
    doc.save()
    return str(path)


CSR_MATRIX_HEADERS = ["Problem", "Category", "Severity", "District", "Status", "Industry", "Pledged INR", "Pledge status"]


def mirror_export(path: str, fallback_download: str) -> dict:
    """Mirror a generated export to object storage with a presigned URL when
    enabled; otherwise point at a same-origin download endpoint.

    Shared by admin and industry exports — single implementation.
    """
    import logging as _logging

    body: dict = {"path": path}
    try:
        from app.services import storage as storage_svc

        if storage_svc.enabled():
            key = storage_svc.object_key("exports", Path(path).name)
            storage_svc.put_bytes(key, Path(path).read_bytes(), "application/octet-stream")
            body["download_url"] = storage_svc.presigned_get(key)
            return body
    except Exception:
        _logging.getLogger(__name__).warning("Export object-storage mirror failed", exc_info=True)
    body["download_url"] = fallback_download
    return body


def find_export_file(filename: str) -> Path | None:
    """Locate a generated export by bare filename, contained to the report
    subdirectories (no path traversal). Shared by download endpoints."""
    safe = Path(filename).name
    if safe != filename or ".." in filename or not safe:
        return None
    root = OUTPUT_ROOT
    for sub in ("sla", "reports", "audit", "csr", "triage"):
        try:
            base = (root / sub).resolve()
        except Exception:
            continue
        candidate = (root / sub / safe).resolve()
        if str(candidate).startswith(str(base)) and candidate.is_file():
            return candidate
    return None


def write_csr_matrix(rows: list[list], name: str = "") -> str:
    """CSR funding matrix export (XLSX). Plain row lists under
    CSR_MATRIX_HEADERS. Shared by the batch/monthly activities and exports."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    directory = OUTPUT_ROOT / "csr"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (f"{name}_{utc_stamp()}.xlsx" if name else f"csr_matrix_{utc_stamp()}.xlsx")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "CSR matches"
    sheet.append(CSR_MATRIX_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(list(row))
    workbook.save(path)
    return str(path)
