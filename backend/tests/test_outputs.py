from pathlib import Path

from app.services import outputs
from app.api.router import classify_issue


def test_triage_export_has_specified_headers(tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_ROOT", tmp_path)
    path = Path(outputs.write_triage_csv([{"submission_id": "sub-1", "timestamp_submitted": "2026-01-01T00:00:00Z", "raw_text_preview": "test", "category": "Water", "severity": 3, "geo_district": "Ranchi", "triage_status": "PENDING"}]))
    assert path.exists()
    assert path.read_text(encoding="utf-8-sig").splitlines()[0].startswith("submission_id")


def test_audit_log_is_append_only(tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_ROOT", tmp_path)
    outputs.append_audit({"action": "CREATED"})
    outputs.append_audit({"action": "APPROVED"})
    assert len(list((tmp_path / "audit").glob("*.jsonl"))[0].read_text().splitlines()) == 2


def test_classification_is_case_insensitive_and_assigns_urgent_severity():
    assert classify_issue("URGENT water flood near the market") == ("Water", 4)


def test_classification_defaults_to_governance():
    assert classify_issue("pension not released for months") == ("Governance", 3)
