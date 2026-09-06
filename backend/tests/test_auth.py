"""Phase-1 identity + contract tests. DB-free: scripted FakeSession like test_api."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")
os.environ.setdefault("ALLOW_DEV_OTP", "true")

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_db, require_workspace, workspace_of  # noqa: E402
from app.db.models import MediaAsset, Officer, OrgInvite, OtpCode, User  # noqa: E402
from app.main import app  # noqa: E402
from app.services import auth as auth_svc  # noqa: E402
from app.services.events import channels_for  # noqa: E402
from app.services.rate_limit import _allow_memory  # noqa: E402


class FakeScalars:
    def __init__(self, rows=None):
        self._rows = rows or []

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return FakeScalars(self._rows)


class ScriptedSession:
    """FakeSession with scripted execute() results and write capture."""

    def __init__(self, script):
        self._script = list(script)
        self.added = []
        self.commits = 0

    async def execute(self, *args, **kwargs):
        assert self._script, "unexpected query: session script exhausted"
        return self._script.pop(0)

    async def get(self, model, key):
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        return None


def make_client(session):
    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def future(**kwargs):
    return datetime.now(timezone.utc) + timedelta(**kwargs)


# ---------------------------------------------------------------------------
# Citizen email registration
# ---------------------------------------------------------------------------

def test_register_creates_citizen_and_logs_in(_clear_overrides):
    session = ScriptedSession([FakeResult([])])
    client = make_client(session)
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Test Citizen", "email": "citizen@example.com", "password": "password123", "district": "Ranchi"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["access_token"] and body["workspace_type"] == "citizen" and body["role"] == "citizen"
    users = [o for o in session.added if isinstance(o, User)]
    assert len(users) == 1 and users[0].district == "Ranchi"


def test_register_rejects_duplicate(_clear_overrides):
    existing = User(email_encrypted=auth_svc.contact_hash("dup@example.com"), password_hash="x")
    session = ScriptedSession([FakeResult([existing])])
    client = make_client(session)
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Dup", "email": "dup@example.com", "password": "password123"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Phone OTP
# ---------------------------------------------------------------------------

def test_otp_request_and_verify_roundtrip(_clear_overrides):
    session = ScriptedSession([FakeResult([]), FakeResult([])])
    client = make_client(session)
    response = client.post("/api/v1/auth/request-otp", json={"phone": "+91 98765 43210"})
    assert response.status_code == 200, response.text
    assert response.json()["sent"] is True
    assert [o for o in session.added if isinstance(o, User)]
    assert [o for o in session.added if isinstance(o, OtpCode)]


def _otp_session(code="123456", expired=False):
    user = User(phone_encrypted=auth_svc.contact_hash("9876543210"), workspace_type="citizen")
    otp = OtpCode(
        user_id=user.user_id,
        code_hash=auth_svc._code_hash(code, user.user_id),
        channel="sms",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=-1 if expired else 600),
        attempts=0,
    )
    return ScriptedSession([FakeResult([user]), FakeResult([otp])])


def test_otp_verify_success(_clear_overrides):
    client = make_client(_otp_session())
    response = client.post("/api/v1/auth/verify-otp", json={"phone": "9876543210", "code": "123456"})
    assert response.status_code == 200, response.text
    assert response.json()["workspace_type"] == "citizen"


def test_otp_verify_wrong_code_is_401(_clear_overrides):
    client = make_client(_otp_session())
    response = client.post("/api/v1/auth/verify-otp", json={"phone": "9876543210", "code": "000000"})
    assert response.status_code == 401


def test_otp_verify_expired_is_401(_clear_overrides):
    client = make_client(_otp_session(expired=True))
    response = client.post("/api/v1/auth/verify-otp", json={"phone": "9876543210", "code": "123456"})
    assert response.status_code == 401


def test_otp_verify_unknown_number_is_404(_clear_overrides):
    session = ScriptedSession([FakeResult([])])
    client = make_client(session)
    response = client.post("/api/v1/auth/verify-otp", json={"phone": "9000000000", "code": "123456"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Institutional invites
# ---------------------------------------------------------------------------

def _invite(token="tok-abc-123", email="new.iic@univ.ac.in"):
    import hashlib

    return OrgInvite(
        organization_type="university",
        organization_name="Ranchi University",
        email=email,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        status="pending",
        expires_at=future(days=7),
    )


def test_accept_invite_creates_workspace_account(_clear_overrides):
    session = ScriptedSession([FakeResult([_invite()])])
    client = make_client(session)
    response = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": "tok-abc-123", "email": "new.iic@univ.ac.in", "name": "IIC Head", "password": "password123"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted" and body["role"] == "university"
    users = [o for o in session.added if isinstance(o, User)]
    assert users and users[0].workspace_type == "university"


def test_accept_invite_unknown_token_is_404(_clear_overrides):
    session = ScriptedSession([FakeResult([])])
    client = make_client(session)
    response = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": "nope", "email": "a@b.ac.in", "name": "X", "password": "password123"},
    )
    assert response.status_code == 404


def test_invite_endpoints_require_admin(_clear_overrides):
    from app.api.deps import create_access_token

    citizen_token = create_access_token({"sub": "x", "role": "citizen"})
    admin_token = create_access_token({"sub": "a", "role": "admin"})
    headers = {"Authorization": f"Bearer {citizen_token}"}
    session = ScriptedSession([])
    client = make_client(session)
    response = client.post(
        "/api/v1/admin/invites",
        json={"email": "x@univ.ac.in", "organization_type": "university"},
        headers=headers,
    )
    assert response.status_code == 403
    # Admin path reaches the service (empty org match -> invite created).
    session2 = ScriptedSession([FakeResult([])])
    client2 = make_client(session2)
    response2 = client2.post(
        "/api/v1/admin/invites",
        json={"email": "x@univ.ac.in", "organization_type": "university", "organization_name": "Nope"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response2.status_code == 201, response2.text
    assert response2.json()["token"]


# ---------------------------------------------------------------------------
# Login hardening + extended contract
# ---------------------------------------------------------------------------

def test_login_response_carries_workspace_contract(_clear_overrides):
    session = ScriptedSession([FakeResult([]), FakeResult([]), FakeResult([])])
    client = make_client(session)
    response = client.post("/api/v1/auth/login", json={"email": "ramesh@example.com", "password": "x"})
    assert response.status_code == 200
    body = response.json()
    assert body["workspace_type"] == "citizen" and body["organization_id"] is None


def test_login_enforces_officer_password(_clear_overrides):
    from app.api.deps import hash_password

    officer = Officer(
        name="Anil",
        department="District Administration",
        district="Ranchi",
        role="district_officer",
        email="officer@nitivayu.gov.in",
        password_hash=hash_password("password123"),
    )
    good = ScriptedSession([FakeResult([officer])])
    response = make_client(good).post(
        "/api/v1/auth/login", json={"email": "officer@nitivayu.gov.in", "password": "password123"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "officer"

    bad = ScriptedSession([FakeResult([officer])])
    response = make_client(bad).post(
        "/api/v1/auth/login", json={"email": "officer@nitivayu.gov.in", "password": "wrongpass1"}
    )
    assert response.status_code == 401


def test_oauth_url_unconfigured_is_501(_clear_overrides):
    session = ScriptedSession([])
    client = make_client(session)
    for provider in ("google", "facebook"):
        response = client.get(f"/api/v1/auth/oauth/{provider}/url")
        assert response.status_code == 501, provider


# ---------------------------------------------------------------------------
# Intake with geo + audio + media rows
# ---------------------------------------------------------------------------

def test_submission_persists_geo_audio_and_media_rows(_clear_overrides, monkeypatch):
    import app.api.router as router_mod
    import app.services.storage as storage_mod

    monkeypatch.setattr(storage_mod, "put_bytes", lambda key, data, ct="application/octet-stream": f"local://{key}")
    monkeypatch.setattr(router_mod, "append_audit", lambda event: "mocked")

    async def _no_temporal(*args, **kwargs):
        raise ConnectionError("temporal disabled in tests")

    monkeypatch.setattr("temporalio.client.Client.connect", _no_temporal)

    class FakeUniversity:
        university_id = "11111111-2222-4333-8444-555555555555"
        current_load = 0

    session = ScriptedSession([FakeResult([FakeUniversity()])])
    client = make_client(session)
    response = client.post(
        "/api/v1/submissions",
        data={"raw_text": "Handpump water is yellow in Garhwa", "district": "Garhwa", "geo_lat": "24.1", "geo_lng": "83.8"},
        files={"photo": ("p.webp", b"\x00" * 64, "image/webp"), "audio_note": ("a.webm", b"\x01" * 64, "audio/webm")},
    )
    assert response.status_code == 202, response.text
    media = [o for o in session.added if isinstance(o, MediaAsset)]
    assert {m.kind for m in media} == {"photo", "audio"}
    submissions = [o for o in session.added if type(o).__name__ == "Submission"]
    assert submissions and submissions[0].geo_lat == 24.1 and submissions[0].photo_url.startswith("local://")


# ---------------------------------------------------------------------------
# Workspace gate, SSE channels, rate limiter, misc contracts
# ---------------------------------------------------------------------------

def test_workspace_gate_allows_admin_preview_and_blocks_cross_workspace():
    import asyncio

    assert workspace_of({"role": "industry"}) == "corporate"
    assert workspace_of({"role": "officer", "workspace_type": "officer"}) == "officer"

    checker = require_workspace("officer")
    # Depends defaults are bypassed by passing current_user explicitly.
    result = asyncio.run(checker(current_user={"user_id": "a", "role": "admin", "organization_id": None}))
    assert result["role"] == "admin"
    officer_gate = require_workspace("officer")
    try:
        asyncio.run(officer_gate(current_user={"user_id": "u", "role": "university", "organization_id": "org-1"}))
        raise AssertionError("cross-workspace access should be forbidden")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    scoped = require_workspace("university")
    try:
        asyncio.run(scoped(current_user={"user_id": "u", "role": "university", "organization_id": None}))
        raise AssertionError("unlinked org access should be forbidden")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403


def test_sse_channels_are_scope_derived():
    channels = channels_for({"role": "university", "organization_id": "org-9"}, track="NITIVAYU-1, NITIVAYU-2")
    assert "org:org-9" in channels and "track:NITIVAYU-1" in channels
    assert channels_for(None) == ["public"]


def test_memory_rate_limiter_trips():
    key = "pytest-rl-probe"
    assert _allow_memory(key, 2, 60) and _allow_memory(key, 2, 60)
    assert not _allow_memory(key, 2, 60)


def test_metrics_and_oauth_helpers():
    assert auth_svc.oauth_authorize_url("google", next_url="/x") is None
    assert auth_svc.normalize_phone("+91 98765-43210") == "9876543210"
    assert auth_svc.valid_phone("9876543210") and not auth_svc.valid_phone("123")


def test_metrics_endpoint(_clear_overrides):
    session = ScriptedSession([])
    client = make_client(session)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "nitivayu_http_requests_total" in response.text
