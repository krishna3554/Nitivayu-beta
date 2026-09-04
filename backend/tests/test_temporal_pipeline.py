"""Unit tests for the Temporal triage pipeline (no DB, network, or model needed)."""

from types import SimpleNamespace

import pytest
from temporalio.exceptions import ApplicationError

from app.activities import dedup as dedup_activity
from app.activities import route as route_activity
from app.api.router import OFFICER_SIGNAL_NAME, WORKFLOW_DECISION_SIGNALS
from app.services import embeddings as embedding_service
from app.services import llm as llm_service
from app.services.triage_state import advance_status


@pytest.fixture()
def _settings_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("LLM_CACHE", "0")
    llm_service.get_settings.cache_clear()
    embedding_service.get_settings.cache_clear()
    yield
    llm_service.get_settings.cache_clear()
    embedding_service.get_settings.cache_clear()


def test_category_canonicalization_maps_display_labels():
    assert llm_service.canonicalize_category("Water Pollution") == "Water"
    assert llm_service.canonicalize_category("Air Pollution") == "Environment"
    assert llm_service.canonicalize_category("Infrastructure") == "Infrastructure"
    assert llm_service.canonicalize_category("something unknown") == "Governance"


def test_severity_coercion_accepts_labels_and_rejects_out_of_range():
    assert llm_service.coerce_severity("High") == 4
    assert llm_service.coerce_severity(5) == 5
    with pytest.raises(ValueError):
        llm_service.coerce_severity(7)


def test_extraction_validation_rejects_missing_summary():
    with pytest.raises(ValueError):
        llm_service._validate_extraction({"title": "Only a title"}, source="test")


@pytest.mark.asyncio
async def test_local_extraction_without_api_key_is_marked_fallback(_settings_env):
    result = await llm_service.extract_issue_details("URGENT water flood near the market, handpump broken")
    assert result["source"] == "local_fallback"
    assert result["category"] == "Water"
    assert result["title"]
    assert result["summary"]


@pytest.mark.asyncio
async def test_local_extraction_rejects_blank_text(_settings_env):
    with pytest.raises(ValueError):
        await llm_service.extract_issue_details("   ")


class _FakeModel:
    def __init__(self, vector):
        self._vector = vector

    def encode(self, _text, normalize_embeddings=True):  # noqa: ARG002
        return list(self._vector)

    def get_sentence_embedding_dimension(self):
        return 384


def test_embed_text_rejects_wrong_dimensions(monkeypatch):
    monkeypatch.setattr(embedding_service, "get_embedding_model", lambda: _FakeModel([0.1] * 10))
    with pytest.raises(ValueError):
        embedding_service.embed_text("road broken near market")


def test_embed_text_accepts_valid_vector(monkeypatch):
    monkeypatch.setattr(embedding_service, "get_embedding_model", lambda: _FakeModel([0.1] * 384))
    assert embedding_service.embed_text("road broken near market") == [0.1] * 384


def test_dedup_rejects_invalid_embedding():
    with pytest.raises(ApplicationError):
        dedup_activity._validate_embedding([0.1] * 10)


def _university(name, specializations, district, capacity, load, capability=None):
    return SimpleNamespace(
        university_id=f"id-{name}",
        name=name,
        domain_specializations=specializations,
        district=district,
        active_capacity=capacity,
        current_load=load,
        capability_embedding=capability,
    )


def test_routing_prefers_theme_match_and_skips_full_universities():
    universities = [
        _university("Full Institute", ["Water"], "Ranchi", 10, 10),
        _university("Mismatch College", ["Music"], "Ranchi", 10, 0),
        _university("Water Institute", ["Water Purification"], "Ranchi", 10, 2),
    ]
    ranked = route_activity.score_universities("Water", "handpump fluoride contamination", "Ranchi", [0.1] * 384, universities)
    assert [item["university_name"] for item in ranked] == ["Water Institute", "Mismatch College"]
    assert set(ranked[0]["score_breakdown"]) == {"semantic", "theme", "capacity", "geo"}
    assert ranked[0]["match_score"] >= ranked[1]["match_score"]


def test_status_guard_never_overwrites_decided_records():
    assert advance_status(SimpleNamespace(status="ROUTED"), "OFFICER_REVIEW") is False
    record = SimpleNamespace(status="TRIAGING")
    assert advance_status(record, "OFFICER_REVIEW") is True
    assert record.status == "OFFICER_REVIEW"


def test_workflow_signal_contract():
    assert OFFICER_SIGNAL_NAME == "officer_approval_signal"
    assert WORKFLOW_DECISION_SIGNALS == {"APPROVE": "approve", "REJECT": "reject", "OVERRIDE": "approve"}
