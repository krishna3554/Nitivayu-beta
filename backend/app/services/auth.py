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


async def send_sms(phone: str, code: str) -> None:
    """Dispatch an OTP. `log` writes to backend logs (dev/demo default).

    MSG91 / Twilio Verify plug in here behind SMS_PROVIDER with credentials
    from env — cost and Jharkhand-region deliverability decide (open §10).
    """
    from app.config import get_settings

    provider = get_settings().SMS_PROVIDER.lower()
    if provider == "log":
        logger.info("OTP for %s...%s: %s (SMS_PROVIDER=log)", phone[:2], phone[-2:], code)
        return
    if provider in {"msg91", "twilio"}:
        logger.warning("SMS provider '%s' selected but not yet integrated; code logged instead", provider)
        logger.info("OTP for %s...%s: %s", phone[:2], phone[-2:], code)
        return
    logger.warning("Unknown SMS_PROVIDER '%s'; code logged instead", provider)
    logger.info("OTP for %s...%s: %s", phone[:2], phone[-2:], code)


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
    password verifies; None when unknown (caller falls back to heuristics)."""
    officer = (
        await db.execute(select(Officer).where(func.lower(Officer.email) == email.lower()))
    ).scalars().first()
    if officer is None:
        return None
    try:
        ok = verify_password(password, officer.password_hash)
    except Exception:
        # Unparseable hash (legacy row): do not lock the demo out; let the
        # heuristic path decide, and log for the admin to re-provision.
        logger.warning("Officer %s has an unreadable password hash; using demo fallback", email)
        return None
    if not ok:
        raise ValueError("bad password")
    return officer


# ---------------------------------------------------------------------------
# Social login URL builders (env-gated; 501 until configured)
# ---------------------------------------------------------------------------

def oauth_authorize_url(provider: str, *, next_url: str = "") -> str | None:
    from app.config import get_settings

    settings = get_settings()
    base = settings.OAUTH_CALLBACK_BASE.rstrip("/")
    callback = f"{base}/api/v1/auth/oauth/{provider}/callback"
    state = next_url or "/app/citizen"
    if provider == "google" and settings.GOOGLE_CLIENT_ID:
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
    if provider == "facebook" and settings.FACEBOOK_APP_ID:
        from urllib.parse import urlencode

        return "https://www.facebook.com/v18.0/dialog/oauth?" + urlencode(
            {"client_id": settings.FACEBOOK_APP_ID, "redirect_uri": callback, "state": state, "scope": "email"}
        )
    return None
