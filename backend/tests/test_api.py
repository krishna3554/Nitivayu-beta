"""High-value API contract tests that run without a live database."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.router import parse_uuid
from app.main import app


class _FakeScalars:
    def __init__(self, rows=None):
        self._rows = rows or []

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return _FakeScalars(self._rows)

    def all(self):
        return [(row,) for row in self._rows]

    def scalar_one(self):
        return 0


class FakeSession:
    """Async session stub: every query returns empty results."""

    async def execute(self, *args, **kwargs):
        return _FakeResult()

    async def get(self, model, key):
        return None

    async def flush(self):
        return None

    async def commit(self):
        return None

    def add(self, obj):
        return None


async def _fake_get_db():
    yield FakeSession()


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = _fake_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_endpoint_responds(client):
    response = client.get("/api/health")
    assert response.status_code in (200, 503)
    assert response.json()["service"] == "nitivayu-backend"


def test_login_returns_citizen_token(client):
    response = client.post("/api/v1/auth/login", json={"email": "ramesh@example.com", "password": "x"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "citizen"
    assert body["access_token"]


def test_login_requires_password(client):
    response = client.post("/api/v1/auth/login", json={"email": "ramesh@example.com", "password": ""})
    assert response.status_code == 400


def test_login_validation_error_is_structured(client):
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422
    assert response.json()["detail"] == "Validation failed"


def test_review_queue_requires_auth(client):
    response = client.get("/api/v1/officer/review-queue")
    assert response.status_code == 401


def test_track_unknown_submission_returns_404(client):
    response = client.get("/api/v1/submissions/NITIVAYU-2026-JH-NOPE00/track")
    assert response.status_code == 404
    assert response.json()["detail"] == "Submission not found"


def test_submission_rejects_blank_text(client):
    response = client.post("/api/v1/submissions", data={"raw_text": "   "})
    assert response.status_code == 422


def test_parse_uuid_rejects_invalid_values():
    with pytest.raises(HTTPException) as exc_info:
        parse_uuid("not-a-uuid", "problem_id")
    assert exc_info.value.status_code == 422
