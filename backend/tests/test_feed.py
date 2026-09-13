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
from app.api.routes.feed import _moderate_comment, _public_reporter, _resolve_voter  # noqa: E402
from app.db.models import Problem, ReportComment, ReportConfirmation, ReportLike, Submission  # noqa: E402
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
        TuplesResult([(problem, submission, 7, 2, 1)]),        # page rows
        TuplesResult([]),                                      # matched universities
        TuplesResult([]),                                      # clean media summary
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
    assert item["me_too_count"] == 7
    assert item["confirm_count"] == 2
    assert item["comment_count"] == 1
    assert item["liked_by_me"] is False
    assert item["me_too_by_me"] is False
    assert item["reporter"] == "Krishna L."
    assert item["district"] == "Ranchi"
    # Share powers the public tracker link, so the token ships (muted, small).
    assert item["tracking_token"] == submission.tracking_token
    # Exact coordinates and contact channels are never exposed.
    assert "geo_lat" not in item
    assert "geo_lng" not in item
    assert "contact_email" not in item
    assert "contact_phone" not in item
    # Internal AI internals stay internal.
    assert "confidence_score" not in item
    assert "score_breakdown" not in item
    assert "summary_embedding" not in item


def test_feed_flags_liked_rows_for_anonymous_voter():
    submission = _submission()
    problem = _problem(submission_id=submission.submission_id)
    session = ScriptedSession([
        FakeResult(scalar=1),
        TuplesResult([(problem, submission, 3, 1, 0)]),
        TuplesResult([(problem.problem_id,)]),                 # me-too lookup
        TuplesResult([(problem.problem_id,)]),                 # confirm lookup
        TuplesResult([]),                                      # matched universities
        TuplesResult([]),                                      # clean media summary
    ])
    client = make_client(session)
    response = client.get("/api/v1/feed", params={"voter": ANON_VOTER})
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["liked_by_me"] is True
    assert item["me_too_by_me"] is True
    assert item["confirmed_by_me"] is True


def test_feed_rejects_unknown_status_bucket():
    session = ScriptedSession([])
    client = make_client(session)
    response = client.get("/api/v1/feed", params={"status": "bogus"})
    assert response.status_code == 422, response.text


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


# ---------------------------------------------------------------------------
# Civic engagement: me-too / confirm / comments / media
# ---------------------------------------------------------------------------

def _authed_client(session, role="citizen"):
    return make_client(session, role=role, sub=str(uuid.uuid4()))


def test_me_too_requires_auth():
    problem = _problem()
    session = _problem_get_session(problem, [])
    client = make_client(session)  # anonymous
    response = client.post(f"/api/v1/feed/{problem.problem_id}/me-too")
    assert response.status_code in {401, 403}, response.text


def test_me_too_adds_row_once_then_409():
    problem = _problem(severity_score=3)
    session = _problem_get_session(problem, [
        FakeResult([]),            # no existing me-too
        FakeResult(scalar=1),      # count after insert
    ])
    client = _authed_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/me-too")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["me_too"] is True
    assert body["me_too_count"] == 1
    assert body["severity_boosted"] is False
    assert len(session.added) == 1
    assert isinstance(session.added[0], ReportLike)
    assert session.commits == 1


def test_me_too_duplicate_is_409_not_double_count():
    problem = _problem()
    existing = ReportLike(problem_id=problem.problem_id, voter_key="u:abc")
    session = _problem_get_session(problem, [FakeResult([existing])])
    client = _authed_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/me-too")
    assert response.status_code == 409, response.text
    assert not session.added


def test_me_too_quorum_boosts_severity():
    problem = _problem(severity_score=3)
    session = _problem_get_session(problem, [
        FakeResult([]),
        FakeResult(scalar=3),      # quorum reached
    ])
    client = _authed_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/me-too")
    assert response.status_code == 200, response.text
    assert response.json()["severity_boosted"] is True
    assert problem.severity_score == 4


def test_me_too_hidden_for_gated_statuses():
    gated = _problem(status="PENDING_TRIAGE")  # pre-extraction: unredacted raw_text
    session = _problem_get_session(gated, [])
    client = _authed_client(session)
    response = client.post(f"/api/v1/feed/{gated.problem_id}/me-too")
    assert response.status_code == 404, response.text


def test_confirm_requires_auth_and_never_boosts_severity():
    problem = _problem(severity_score=3)
    anon_session = _problem_get_session(problem, [])
    anon_client = make_client(anon_session)
    response = anon_client.post(f"/api/v1/feed/{problem.problem_id}/confirm")
    assert response.status_code in {401, 403}, response.text

    session = _problem_get_session(problem, [
        FakeResult([]),            # no existing confirmation
        FakeResult(scalar=5),      # well past corroboration quorum
    ])
    client = _authed_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/confirm")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"confirmed": True, "confirm_count": 5, "corroborated": True}
    assert problem.severity_score == 3  # verification weight != experience weight
    assert isinstance(session.added[0], ReportConfirmation)


def test_confirm_duplicate_is_409():
    problem = _problem()
    existing = ReportConfirmation(problem_id=problem.problem_id, voter_key="u:abc")
    session = _problem_get_session(problem, [FakeResult([existing])])
    client = _authed_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/confirm")
    assert response.status_code == 409, response.text


def test_moderate_comment_blocks_profanity_spam_and_blanks():
    assert _moderate_comment("   ") == "Comment cannot be blank"
    assert _moderate_comment("x" * 1001).startswith("Comment is too long")
    assert _moderate_comment("you chutiya officer") == "This comment contains language we do not publish"
    assert _moderate_comment("https://spam.example") == "Links alone look like spam — please add context"
    assert _moderate_comment("gooooooooood workkkkkkkkkk") == "This comment looks like spam"
    assert _moderate_comment("The handpump near our ward still gives red water.") is None


def test_post_comment_requires_auth_and_validates():
    problem = _problem()
    session = _problem_get_session(problem, [])
    client = make_client(session)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/comments", json={"body": "hello"})
    assert response.status_code in {401, 403}, response.text

    authed = _problem_get_session(problem, [])
    client = _authed_client(authed)
    response = client.post(f"/api/v1/feed/{problem.problem_id}/comments", json={"body": "   "})
    assert response.status_code == 422, response.text


def test_post_comment_persists_visible_row():
    problem = _problem()
    session = _problem_get_session(problem, [])
    client = _authed_client(session)
    response = client.post(
        f"/api/v1/feed/{problem.problem_id}/comments",
        json={"body": "Our lane faces the same issue since June."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"] == "Our lane faces the same issue since June."
    assert body["parent_id"] is None
    assert len(session.added) == 1
    assert isinstance(session.added[0], ReportComment)
    assert session.added[0].status == "visible"


def test_feed_media_serves_clean_only():
    import pathlib

    from app.db.models import MediaAsset

    problem = _problem()
    clean = MediaAsset(
        submission_id=problem.submission_id, kind="photo",
        storage_url="/nonexistent/clean.webp", moderation_status="clean",
    )
    flagged = MediaAsset(
        submission_id=problem.submission_id, kind="photo",
        storage_url="/nonexistent/flagged.webp", moderation_status="flagged",
    )

    class MediaSession(ScriptedSession):
        def __init__(self, asset, prob):
            super().__init__([])
            self._asset = asset
            self._prob = prob

        async def get(self, model, key):
            if model is MediaAsset:
                return self._asset
            return None

        async def execute(self, *args, **kwargs):
            class _Rows:
                def __init__(self, prob):
                    self._prob = prob

                def scalars(self):
                    class _S:
                        def __init__(self, prob):
                            self._prob = prob

                        def first(self):
                            return self._prob

                    return _S(self._prob)

            return _Rows(self._prob)

    # Flagged evidence is invisible from the public feed (404, not 403).
    client = make_client(MediaSession(flagged, problem))
    response = client.get(f"/api/v1/feed/media/{uuid.uuid4()}")
    assert response.status_code == 404, response.text

    # Clean but missing file on disk is also a 404 (never a 500).
    real_asset_id = uuid.uuid4()
    session = MediaSession(clean, problem)

    async def _get(model, key):
        if model is MediaAsset:
            clean.asset_id = real_asset_id
            return clean
        return None

    session.get = _get
    client = make_client(session)
    assert pathlib.Path("/nonexistent/clean.webp").exists() is False
    response = client.get(f"/api/v1/feed/media/{real_asset_id}")
    assert response.status_code == 404, response.text
