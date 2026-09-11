"""Phase-1 identity service (nitivayu.md §5.5, §6).

- Citizen signup: phone + OTP (no password) or email + password.
- Institutional signup: invite token + email + password; organization_id is
  bound at invite time — no email-substring heuristics.
- JWT claim shape is unchanged ({sub, role, organization_id}) with an added
  `workspace_type` claim new clients use for shell routing.

PII discipline: phone/email values are normalized, then stored only as a
salted SHA-256 hash for lookup. Plaintext PII is never persisted; encrypting
at rest (envelope encryption / KMS) is the documented production follow-up.
"""

import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import create_access_token, hash_password, verify_password
from app.db.models import Industry, Officer, University, User, OtpCode, OrgInvite

logger = logging.getLogger(__name__)

PHONE_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    """Keep last 10 digits; accept +91, spaces, dashes."""
    digits = PHONE_DIGITS.sub("", raw or "")
    if len(digits) > 10:
        digits = digits[-10:]
    return digits


def valid_phone(phone: str) -> bool:
    return phone.isdigit() and 10 <= len(phone) <= 13


def contact_hash(value: str) -> bytes:
    """One-way lookup hash (SHA-256 over normalized value + JWT secret pepper).

    The pepper lives in server config, so a bare DB dump cannot be reversed
    by rainbow tables. See module docstring for the KMS follow-up.
    """
    from app.config import get_settings

    pepper = get_settings().JWT_SECRET.encode()
    return hashlib.sha256(pepper + value.strip().lower().encode()).digest()


def issue_jwt(user: User, role: str) -> dict:
    token = create_access_token(
        {
            "sub": str(user.user_id),
            "role": role,
            "organization_id": str(user.organization_id) if user.organization_id else None,
            "workspace_type": user.workspace_type,
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "workspace_type": user.workspace_type,
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "display_name": getattr(user, "display_name", None),
    }


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------

def _otp_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _code_hash(code: str, user_id: object) -> str:
    from app.config import get_settings

    return hmac.new(
        get_settings().JWT_SECRET.encode(), f"{user_id}:{code}".encode(), hashlib.sha256
    ).hexdigest()


async def send_sms(phone: str, code: str) -> bool:
    """Dispatch an OTP through the configured provider (WP-9).

    Returns True when a real SMS provider accepted the message. `log` (the
    default) writes to backend logs for dev/demo.
    """
    from app.services import notify as notify_svc

    return await notify_svc.send_sms(
        phone, f"Your Nitivayu verification code is {code}. It expires in 10 minutes. Never share it."
    )


async def get_or_create_citizen(db: AsyncSession, *, phone: str | None = None, email: str | None = None, district: str | None = None) -> User:
    user = None
    if phone:
        user = (await db.execute(select(User).where(User.phone_encrypted == contact_hash(phone)))).scalars().first()
    if user is None and email:
        user = (await db.execute(select(User).where(User.email_encrypted == contact_hash(email)))).scalars().first()
    if user is None:
        user = User(
            phone_encrypted=contact_hash(phone) if phone else None,
            email_encrypted=contact_hash(email) if email else None,
            workspace_type="citizen",
            district=district,
            is_verified=False,
        )
        db.add(user)
        await db.flush()
    elif district and not user.district:
        user.district = district
    return user


async def request_otp(db: AsyncSession, *, phone: str, district: str | None = None) -> tuple[User, OtpCode, str]:
    from app.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    user = await get_or_create_citizen(db, phone=phone, district=district)
    # Resend throttle: reuse a live code instead of spamming SMS.
    recent = (
        await db.execute(
            select(OtpCode)
            .where(
                OtpCode.user_id == user.user_id,
                OtpCode.consumed_at.is_(None),
                OtpCode.expires_at > now,
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if recent and (now - recent.created_at.replace(tzinfo=timezone.utc)).total_seconds() < settings.OTP_RESEND_SECONDS:
        raise ValueError("A code was just sent. Wait a minute before requesting another.")
    code = _otp_code()
    otp = OtpCode(
        user_id=user.user_id,
        code_hash=_code_hash(code, user.user_id),
        channel="sms",
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    db.add(otp)
    await db.flush()
    await send_sms(phone, code)
    return user, otp, code


async def verify_otp(db: AsyncSession, *, phone: str, code: str) -> User:
    from app.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    user = (await db.execute(select(User).where(User.phone_encrypted == contact_hash(phone)))).scalars().first()
    if user is None:
        raise LookupError("No account for this number. Request a code first.")
    otp = (
        await db.execute(
            select(OtpCode)
            .where(OtpCode.user_id == user.user_id, OtpCode.consumed_at.is_(None))
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if otp is None:
        raise LookupError("No active code. Request a new one.")
    otp.attempts += 1
    if otp.attempts > settings.OTP_MAX_ATTEMPTS:
        raise PermissionError("Too many wrong attempts. Request a new code.")
    exp = otp.expires_at if otp.expires_at.tzinfo else otp.expires_at.replace(tzinfo=timezone.utc)
    if exp <= now:
        raise PermissionError("That code expired. Request a new one.")
    if not hmac.compare_digest(otp.code_hash, _code_hash(code.strip(), user.user_id)):
        await db.flush()
        raise PermissionError("That code did not match. Check the SMS and try again.")
    otp.consumed_at = now
    user.is_verified = True
    user.last_login_at = now
    # WP-9: store the opt-in SMS channel while the verified number is in hand.
    # No key configured => stays NULL and citizen SMS stays hash-only.
    try:
        from app.services import notify as notify_svc

        encrypted = notify_svc.encrypt_phone(phone)
        if encrypted is not None:
            user.phone_enc = encrypted
    except Exception:
        logger.warning("Could not store citizen SMS channel", exc_info=True)
    await db.flush()
    return user


# ---------------------------------------------------------------------------
# Email registration (citizen self-serve) + institutional invites
# ---------------------------------------------------------------------------

async def register_email(db: AsyncSession, *, name: str, email: str, password: str, district: str | None = None) -> User:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    existing = (await db.execute(select(User).where(User.email_encrypted == contact_hash(email)))).scalars().first()
    if existing and existing.password_hash:
        raise ValueError("An account with this email already exists. Sign in instead.")
    user = existing or User(email_encrypted=contact_hash(email), workspace_type="citizen")
    user.password_hash = hash_password(password)
    user.display_name = (name or "").strip()[:120] or user.display_name
    user.is_verified = True  # email ownership proven by mailbox access at login time
    if district:
        user.district = district
    if existing is None:
        db.add(user)
    await db.flush()
    user.last_login_at = datetime.now(timezone.utc)
    return user


def _invite_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, digest


async def create_invite(
    db: AsyncSession,
    *,
    email: str,
    organization_type: str,
    organization_name: str | None,
    invited_by: str | None,
) -> tuple[OrgInvite, str]:
    from app.config import get_settings

    if organization_type not in {"university", "industry"}:
        raise ValueError("organization_type must be university or industry.")
    organization_id = None
    if organization_name:
        if organization_type == "university":
            org = (
                await db.execute(
                    select(University).where(func.lower(University.name) == organization_name.strip().lower())
                )
            ).scalars().first()
            organization_id = org.university_id if org else None
        else:
            org = (
                await db.execute(
                    select(Industry).where(func.lower(Industry.name) == organization_name.strip().lower())
                )
            ).scalars().first()
            organization_id = org.industry_id if org else None
    raw, digest = _invite_token()
    invite = OrgInvite(
        organization_id=organization_id,
        organization_type=organization_type,
        organization_name=organization_name,
        email=email.strip().lower(),
        token_hash=digest,
        status="pending",
        invited_by=invited_by,
        expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.flush()
    logger.info("Invite %s issued to %s (%s)", invite.invite_id, email, organization_type)
    return invite, raw


async def accept_invite(db: AsyncSession, *, token: str, email: str, name: str, password: str) -> tuple[User, str]:
    digest = hashlib.sha256(token.strip().encode()).hexdigest()
    invite = (await db.execute(select(OrgInvite).where(OrgInvite.token_hash == digest))).scalars().first()
    if invite is None or invite.status != "pending":
        raise LookupError("That invite is invalid, already used, or revoked.")
    exp = invite.expires_at if invite.expires_at.tzinfo else invite.expires_at.replace(tzinfo=timezone.utc)
    if exp <= datetime.now(timezone.utc):
        invite.status = "expired"
        await db.flush()
        raise PermissionError("That invite expired. Ask your admin for a new one.")
    if invite.email != email.strip().lower():
        raise PermissionError("That invite was issued to a different email.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    workspace = "university" if invite.organization_type == "university" else "corporate"
    role = "university" if invite.organization_type == "university" else "industry"
    user = User(
        email_encrypted=contact_hash(email),
        password_hash=hash_password(password),
        display_name=(name or "").strip()[:120] or None,
        workspace_type=workspace,
        organization_id=invite.organization_id,
        is_verified=True,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    invite.status = "accepted"
    await db.flush()
    return user, role


# ---------------------------------------------------------------------------
# Institutional password check (hardens demo login without breaking it)
# ---------------------------------------------------------------------------

async def verify_officer_password(db: AsyncSession, email: str, password: str) -> Officer | None:
    """Return the officer row when the email is a known officer AND the
    password verifies; None when unknown (caller tries the next auth source).

    B2.11 fail-closed: a known officer with a wrong password raises
    ValueError (→ 401); a known officer with an unreadable legacy hash ALSO
    raises instead of falling through to demo heuristics — the admin must
    re-provision the row. Only truly unknown emails return None.
    """
    officer = (
        await db.execute(select(Officer).where(func.lower(Officer.email) == email.lower()))
    ).scalars().first()
    if officer is None:
        return None
    try:
        ok = verify_password(password, officer.password_hash)
    except Exception:
        # Unparseable hash (legacy row): fail closed, do not demo-fallback.
        logger.warning("Officer %s has an unreadable password hash; rejecting until re-provisioned", email)
        raise ValueError("bad password")
    if not ok:
        raise ValueError("bad password")
    return officer


# ---------------------------------------------------------------------------
# Social login URL builders (env-gated; 501 until configured)
# Google-only deployment (owner decision U4): Facebook path is retained as a
# deprecated stub that always returns None so the API answers 501.
# ---------------------------------------------------------------------------

OAUTH_STATE_TTL_SECONDS = 600
_ALLOWED_NEXT_PREFIXES = ("/app/", "/login", "/signup", "/track", "/")


def sanitize_next(next_url: str | None) -> str:
    """Allowlist `next` targets to the local app shell (B2.3).

    Only same-origin absolute paths are allowed; anything else falls back to
    the citizen workspace. Rejects protocol-relative (//), backslash, scheme,
    and encoded-traversal tricks.
    """
    fallback = "/app/citizen"
    if not next_url or not isinstance(next_url, str):
        return fallback
    candidate = next_url.strip()
    if not candidate.startswith("/") or candidate.startswith("//") or "\\" in candidate:
        return fallback
    lowered = candidate.lower()
    if ":" in candidate or lowered.startswith(("/\\", "/%5c", "/%2f%2f")):
        return fallback
    if ".." in candidate or "%2e" in lowered or "%00" in lowered:
        return fallback
    if candidate == "/" or candidate.startswith(_ALLOWED_NEXT_PREFIXES):
        # Cut off over-long values (abuse / log-bloat guard).
        return candidate[:256]
    return fallback


def _state_secret() -> bytes:
    from app.config import get_settings

    return get_settings().JWT_SECRET.encode()


def create_oauth_state(next_url: str = "") -> str:
    """Mint a signed, timestamped `state` nonce (B2.2).

    Stateless HMAC-SHA256 over {next, exp, nonce}: the callback can verify
    authenticity + TTL without server-side storage, so no session affinity is
    needed across API replicas. TTL = OAUTH_STATE_TTL_SECONDS.
    """
    import base64
    import json
    import time

    safe_next = sanitize_next(next_url)
    payload = {
        "next": safe_next,
        "exp": int(time.time()) + OAUTH_STATE_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(16),
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_state_secret(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def validate_oauth_state(state: str | None) -> str:
    """Verify `state` and return the safe `next` target (B2.2/B2.3)."""
    import base64
    import json
    import time

    fallback = "/app/citizen"
    if not state or not isinstance(state, str) or "." not in state:
        # Back-compat: very old links passed raw `next`; still sanitize it.
        if state and state.startswith("/"):
            return sanitize_next(state)
        return fallback
    raw, _, sig = state.rpartition(".")
    if not raw or not sig:
        return fallback
    expected = hmac.new(_state_secret(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        logger.warning("OAuth state signature mismatch; ignoring state")
        return fallback
    try:
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if int(payload.get("exp", 0)) < int(time.time()):
            logger.warning("OAuth state expired; ignoring state")
            return fallback
        return sanitize_next(payload.get("next", fallback))
    except Exception:
        logger.warning("OAuth state decode failed; ignoring state", exc_info=True)
        return fallback


def oauth_authorize_url(provider: str, *, next_url: str = "") -> str | None:
    from app.config import get_settings

    settings = get_settings()
    base = (settings.OAUTH_CALLBACK_BASE or "").rstrip("/")
    if not base:
        return None
    callback = f"{base}/api/v1/auth/oauth/{provider}/callback"
    state = create_oauth_state(next_url or "/app/citizen")
    # B2.4: require BOTH id and secret — an ID without a secret can start the
    # flow but can never complete the code exchange, so fail early with 501.
    if provider == "google" and settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
        from urllib.parse import urlencode

        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": callback,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "access_type": "online",
                "prompt": "select_account",
            }
        )
    if provider == "facebook":
        # Deprecated: pinned Graph v18.0 is retired; Google-only per owner U4.
        # Always 501 — do not wire FACEBOOK_* even if present.
        logger.info("Facebook sign-in requested but deployment is Google-only; returning unconfigured")
        return None
    return None


# ---------------------------------------------------------------------------
# One-time OAuth code store (B2.7): the callback never puts the JWT in ?token=.
# It mints a single-use random code (60s TTL) backed by Redis with an
# in-process fallback, then 302s to /login?code=. The frontend exchanges the
# code once via POST /auth/oauth/consume.
# ---------------------------------------------------------------------------

OAUTH_CODE_TTL_SECONDS = 60
_oauth_code_memory: dict[str, tuple[dict, float]] = {}


async def store_oauth_session(payload: dict) -> str:
    """Persist the post-login token payload; return the one-time code."""
    import time

    code = secrets.token_urlsafe(32)
    try:
        from app.services import redis_client as redis_mod

        client = redis_mod.get_redis()
        if client is not None:
            import json as _json

            await client.setex(f"oauth:code:{code}", OAUTH_CODE_TTL_SECONDS, _json.dumps(payload))
            return code
    except Exception:
        logger.warning("OAuth code Redis store failed; using memory fallback", exc_info=True)
    import time as _t

    _oauth_code_memory[code] = (payload, _t.monotonic() + OAUTH_CODE_TTL_SECONDS)
    # Opportunistic prune.
    now = _t.monotonic()
    for key in [k for k, (_, exp) in _oauth_code_memory.items() if exp <= now]:
        _oauth_code_memory.pop(key, None)
    # Bound memory.
    if len(_oauth_code_memory) > 5000:
        _oauth_code_memory.clear()
    return code


async def consume_oauth_session(code: str | None) -> dict | None:
    """Fetch-and-delete the one-time payload; None when unknown/expired/used."""
    import time as _t

    if not code or not isinstance(code, str) or len(code) < 16:
        return None
    try:
        from app.services import redis_client as redis_mod

        client = redis_mod.get_redis()
        if client is not None:
            import json as _json

            key = f"oauth:code:{code}"
            raw = await client.get(key)
            if raw:
                try:
                    await client.delete(key)
                except Exception:
                    pass
                if isinstance(raw, bytes):
                    raw = raw.decode()
                return _json.loads(raw)
    except Exception:
        logger.warning("OAuth code Redis fetch failed; trying memory fallback", exc_info=True)
    entry = _oauth_code_memory.pop(code, None)
    if not entry:
        return None
    payload, exp = entry
    if _t.monotonic() > exp:
        return None
    return payload


async def resolve_oauth_workspace(db: AsyncSession, *, email: str) -> tuple[str, str | None, str]:
    """Map an OAuth-verified email to (role, organization_id, workspace_type).

    Owner decision U5 = linkable: institutional emails land in their workspace
    instead of always becoming citizen. Unknown emails stay citizen. Officer
    match is by exact email; university/industry by their contact emails.
    """
    normalized = (email or "").strip().lower()
    if not normalized:
        return "citizen", None, "citizen"
    # Officer first (strongest privilege) — exact match only, no substrings.
    try:
        officer = (
            await db.execute(select(Officer).where(func.lower(Officer.email) == normalized))
        ).scalars().first()
        if officer is not None:
            role = "admin" if getattr(officer, "role", "") == "state_admin" else "officer"
            ws = "admin" if role == "admin" else "officer"
            return role, None, ws
    except Exception:
        logger.warning("OAuth officer lookup failed; defaulting to citizen", exc_info=True)
    try:
        uni = (
            await db.execute(select(University).where(func.lower(University.nodal_contact_email) == normalized))
        ).scalars().first()
        if uni is not None:
            return "university", str(uni.university_id), "university"
    except Exception:
        logger.warning("OAuth university lookup failed", exc_info=True)
    try:
        ind = (
            await db.execute(select(Industry).where(func.lower(Industry.contact_email) == normalized))
        ).scalars().first()
        if ind is not None:
            return "industry", str(ind.industry_id), "corporate"
    except Exception:
        logger.warning("OAuth industry lookup failed", exc_info=True)
    return "citizen", None, "citizen"
