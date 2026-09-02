from pathlib import Path

from app.services import outputs


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
