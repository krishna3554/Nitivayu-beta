"""Reporter notification tests: validators, composition, safe fan-out."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")

from app.services import notify_reporter as notify_mod  # noqa: E402


def test_normalize_email():
    assert notify_mod.normalize_email("  RAMESH@Example.COM ") == "ramesh@example.com"
    assert notify_mod.normalize_email("not-an-email") is None
    assert notify_mod.normalize_email("") is None
    assert notify_mod.normalize_email(None) is None


def test_normalize_phone():
    assert notify_mod.normalize_phone("+91 98765 43210") == "919876543210"
    assert notify_mod.normalize_phone("9876543210") == "9876543210"
    assert notify_mod.normalize_phone("123") is None
    assert notify_mod.normalize_phone(None) is None


def test_parse_consent():
    assert notify_mod.parse_consent(True) is True
    assert notify_mod.parse_consent("true") is True
    assert notify_mod.parse_consent("1") is True
    assert notify_mod.parse_consent("false") is False
    assert notify_mod.parse_consent("") is False
    assert notify_mod.parse_consent(None) is False


def test_compose_covers_kinds():
    for kind in ("submitted", "approved", "rejected", "overridden", "accepted", "declined", "update", "milestone", "bogus"):
        subject, body = notify_mod.compose(kind, tracking_token="NITIVAYU-1", title="Handpump")
        assert "NITIVAYU-1" in subject and "Handpump" in body


def test_notify_log_provider_never_raises_and_reports(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("SMS_PROVIDER", "log")
    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    try:
        result = notify_mod.notify_reporter(
            "citizen@example.com", "9876543210",
            kind="approved", tracking_token="NITIVAYU-1", title="Handpump",
        )
        assert result["kind"] == "approved"
        # log provider dispatches nothing but must not raise.
        assert result == {"kind": "approved", "email": False, "sms": False}
    finally:
        get_settings.cache_clear()


def test_notify_without_contact_skips_safely():
    assert notify_mod.notify_reporter(None, None, kind="update", tracking_token="T", title="x")


def test_notify_bad_provider_selection_never_raises(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("SMS_PROVIDER", "carrier-pigeon")
    get_settings.cache_clear()
    try:
        result = notify_mod.notify_reporter(None, "9876543210", kind="submitted", tracking_token="T", title="x")
        assert result["sms"] is False
    finally:
        get_settings.cache_clear()


def test_send_email_without_smtp_logs_and_returns_false(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    try:
        assert notify_mod.send_email("a@example.com", "s", "b") is False
        assert notify_mod.send_email("", "s", "b") is False
    finally:
        get_settings.cache_clear()


def test_format_sms_to_preserves_international():
    from app.services.notify import format_sms_to

    assert format_sms_to("+18777804236") == "+18777804236"
    assert format_sms_to("+91 98765 43210") == "+919876543210"
    assert format_sms_to("9876543210") == "+919876543210"
    assert format_sms_to("919876543210") == "+919876543210"


def test_twilio_from_alias_resolves(monkeypatch):
    from app.config import get_settings
    from app.services import notify as notify_svc

    monkeypatch.setenv("TWILIO_FROM_NUMBER", "")
    monkeypatch.setenv("TWILIO_FROM", "+15550001111")
    get_settings.cache_clear()
    try:
        assert notify_svc._twilio_from(get_settings()) == "+15550001111"
    finally:
        get_settings.cache_clear()


def test_otp_sms_uses_twilio_with_alias_creds(monkeypatch):
    import httpx
    from app.config import get_settings
    from app.services import notify as notify_svc

    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, auth=None, data=None, **kwargs):
            calls.update(url=url, auth=auth, data=data)
            return FakeResponse()

    monkeypatch.setenv("SMS_PROVIDER", "twilio")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "")
    monkeypatch.setenv("TWILIO_FROM", "+15550001111")
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    get_settings.cache_clear()
    try:
        import asyncio

        assert asyncio.run(notify_svc.send_sms("+18777804236", "Your Nitivayu verification code is 123456.")) is True
        assert calls["data"]["To"] == "+18777804236"
        assert calls["data"]["From"] == "+15550001111"
        assert calls["auth"] == ("ACtest", "tok")
        assert "Accounts/ACtest/Messages.json" in calls["url"]
    finally:
        get_settings.cache_clear()
