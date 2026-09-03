"""Append-only operational artefacts required by the LokSetu output specification."""
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Defaults to the repo-level ./output directory; containers override via OUTPUT_ROOT=/app/output.
OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", Path(__file__).resolve().parents[3] / "output"))

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
