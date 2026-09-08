"""Civic feed tests: public list shape/privacy, like toggle idempotency.

DB-free FakeSession pattern (see test_plan4.py).
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")

import uuid  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import create_access_token, get_db  # noqa: E402
from app.api.routes.feed import _public_reporter, _resolve_voter  # noqa: E402
from app.db.models import Problem, ReportLike, Submission  # noqa: E402
from app.main import app  # noqa: E402


class FakeScalars:
    def __init__(self, rows=None):
        self._rows = rows or []

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        return FakeScalars(self._rows)

    def all(self):
        return [(row,) for row in self._rows]

    def scalar_one(self):
        return self._scalar


class TuplesResult:
    """Fake for multi-entity selects: .all() returns raw row tuples."""

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class ScriptedSession:
    def __init__(self, script):
        self._script = list(script)
        self.added = []
        self.deleted = []
        self.commits = 0

    async def execute(self, *args, **kwargs):
        assert self._script, "unexpected query: session script exhausted"
        return self._script.pop(0)

    async def get(self, model, key):
        return None

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1


def make_client(session, role=None, sub=None):
    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    client = TestClient(app, raise_server_exceptions=False)
    if role:
        token = create_access_token({"sub": sub or f"test-{role}", "role": role, "organization_id": None})
        client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def teardown_function():
    app.dependency_overrides.clear()


def _submission(**kwargs):
    defaults = dict(
        submission_id=uuid.uuid4(),
        raw_text="Handpump water is contaminated near the village well",
        tracking_token="NITIVAYU-2026-JH-T1",
        status="PENDING_TRIAGE",
        geo_district="Ranchi",
        reporter_name="Krishna Lokhande",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Submission(**defaults)


def _problem(submission_id=None, **kwargs):
    defaults = dict(
        problem_id=uuid.uuid4(),
        submission_id=submission_id or uuid.uuid4(),
        title="Contaminated handpump",
        summary="Handpump water is contaminated",
        category="Water",
        severity_score=4,
        status="ROUTED",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Problem(**defaults)


ANON_VOTER = "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed"


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def test_public_reporter_reduces_name():
    assert _public_reporter("Krishna Lokhande") == "Krishna L."
    assert _public_reporter("Krishna") == "Krishna"
    assert _public_reporter(None) == "Anonymous"
    assert _public_reporter("   ") == "Anonymous"


def test_resolve_voter_prefers_account_over_anon_key():
    voter = _resolve_voter({"user_id": str(uuid.uuid4())}, ANON_VOTER)
    assert voter.startswith("u:")
    assert _resolve_voter(None, ANON_VOTER) == "a:1b9d6bcdbbfd4b2d9b5dab8dfbbd4bed"
    assert _resolve_voter(None, "not-a-uuid") is None
    assert _resolve_voter(None, None) is None


# ---------------------------------------------------------------------------
# GET /feed
# ---------------------------------------------------------------------------

def test_feed_returns_public_shape_without_secrets():
    submission = _submission()
    problem = _problem(submission_id=submission.submission_id)
    session = ScriptedSession([
        FakeResult(scalar=1),                                  # total count
        TuplesResult([(problem, submission, 7)]),              # page rows
    ])
    client = make_client(session)  # anonymous: no Authorization header
    response = client.get("/api/v1/feed")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["has_more"] is False
    item = body["items"][0]
    assert item["problem_id"] == str(problem.problem_id)
    assert item["like_count"] == 7
    assert item["liked_by_me"] is False
    assert item["reporter"] == "Krishna L."
    assert item["district"] == "Ranchi"
    # The tracking token doubles as the report-claim secret: never public.
    assert "tracking_token" not in item
    assert submission.tracking_token not in response.text


def test_feed_flags_liked_rows_for_anonymous_voter():
    submission = _submission()
    problem = _problem(submission_id=submission.submission_id)
    session = ScriptedSession([
        FakeResult(scalar=1),
        TuplesResult([(problem, submission, 3)]),
        TuplesResult([(problem.problem_id,)]),                 # liked lookup
    ])
    client = make_client(session)
    response = client.get("/api/v1/feed", params={"voter": ANON_VOTER})
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["liked_by_me"] is True


def test_feed_empty_when_no_reports():
    session = ScriptedSession([FakeResult(scalar=0), TuplesResult([])])
    client = make_client(session)
    response = client.get("/api/v1/feed")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


# ---------------------------------------------------------------------------
# POST /feed/{problem_id}/like
# ---------------------------------------------------------------------------

def _problem_get_session(problem, script):
    session = ScriptedSession(script)

    async def _get(model, key):
        if model is Problem:
            return problem
        return None

    session.get = _get
    return session


def test_like_requires_voter_key_when_anonymous():
    problem = _problem()
    session = _problem_get_session(problem, [])
    client = make_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/like", json={})
    assert response.status_code == 422, response.text


def test_like_adds_row_and_returns_count():
    problem = _problem()
    session = _problem_get_session(problem, [
        FakeResult([]),            # no existing like
        FakeResult(scalar=1),      # count after insert
    ])
    client = make_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/like", json={"voter_key": ANON_VOTER})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"liked": True, "like_count": 1}
    assert len(session.added) == 1
    assert isinstance(session.added[0], ReportLike)
    assert session.added[0].voter_key == "a:1b9d6bcdbbfd4b2d9b5dab8dfbbd4bed"
    assert session.commits == 1


def test_like_toggle_removes_existing_row():
    problem = _problem()
    existing = ReportLike(problem_id=problem.problem_id, voter_key="a:1b9d6bcdbbfd4b2d9b5dab8dfbbd4bed")
    session = _problem_get_session(problem, [
        FakeResult([existing]),    # existing like found
        FakeResult(scalar=0),      # count after delete
    ])
    client = make_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/like", json={"voter_key": ANON_VOTER})
    assert response.status_code == 200, response.text
    assert response.json() == {"liked": False, "like_count": 0}
    assert session.deleted == [existing]
    assert not session.added


def test_like_signed_in_user_needs_no_voter_key():
    problem = _problem()
    session = _problem_get_session(problem, [FakeResult([]), FakeResult(scalar=1)])
    client = make_client(session, role="citizen", sub=str(uuid.uuid4()))
    response = client.post(f"/api/v1/feed/{problem.problem_id}/like", json={})
    assert response.status_code == 200, response.text
    assert session.added[0].voter_key.startswith("u:")


def test_like_rejected_or_missing_problem_is_404():
    missing = _problem_get_session(None, [])
    client = make_client(missing)
    response = client.post(f"/api/v1/feed/{uuid.uuid4()}/like", json={"voter_key": ANON_VOTER})
    assert response.status_code == 404

    rejected = _problem(status="REJECTED")
    session = _problem_get_session(rejected, [])
    client = make_client(session)
    response = client.post(f"/api/v1/feed/{rejected.problem_id}/like", json={"voter_key": ANON_VOTER})
    assert response.status_code == 404
