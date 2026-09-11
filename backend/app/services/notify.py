"""Outbound notifications (WP-9): SMS via MSG91/Twilio, email via SMTP.

Every sender degrades honestly: when its provider is unconfigured it logs
the intent and returns False ("not delivered") instead of pretending. Callers
use the boolean to decide copy (e.g. admin invite copy-paste fallback) and
the `notified` flags on ProjectUpdate.

Citizen phones: PII is hash-only by default, so there is no number to text.
When PHONE_FERNET_KEY is configured, the OTP-verify step stores a
reversibly-encrypted copy (users.phone_enc) and status SMS goes out only to
citizens who opted in (users.notify_sms).
"""

import asyncio
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def sms_configured() -> bool:
    return get_settings().SMS_PROVIDER.lower() in {"msg91", "twilio"}


def _smtp_username(settings) -> str:
    # Canonical name is SMTP_USER; SMTP_USERNAME is accepted as an alias
    # (both are read from the same root .env).
    return (settings.SMTP_USER or getattr(settings, "SMTP_USERNAME", "") or "").strip()


def _twilio_from(settings) -> str:
    # Canonical name is TWILIO_FROM_NUMBER; TWILIO_FROM is accepted as alias.
    return (settings.TWILIO_FROM_NUMBER or getattr(settings, "TWILIO_FROM", "") or "").strip()


def _msg91_sender(settings) -> str:
    return (settings.MSG91_SENDER_ID or getattr(settings, "MSG91_SENDER", "") or "NITIVU").strip()


def format_sms_to(raw: str) -> str:
    """E.164 destination without mangling non-Indian numbers.

    The OTP subsystem keys identity to the last 10 digits (India), but the
    reporter channel carries full international numbers — never force +91.
    """
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if (raw or "").strip().startswith("+") and digits:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    if digits:
        return f"+{digits}"
    return raw


def email_configured() -> bool:
    settings = get_settings()
    return bool(settings.SMTP_HOST and _smtp_username(settings) and settings.SMTP_PASSWORD)


async def send_sms(phone: str, message: str) -> bool:
    """Send an SMS; True when handed to a real provider, False when logged."""
    settings = get_settings()
    provider = settings.SMS_PROVIDER.lower()
    if provider == "msg91":
        return await _send_msg91(phone, message)
    if provider == "twilio":
        return await _send_twilio(phone, message)
    if provider != "log":
        logger.warning("Unknown SMS_PROVIDER '%s'; logging instead", provider)
    logger.info("SMS to %s...%s (logged, not sent): %s", phone[:2], phone[-2:], message)
    return False


async def _send_msg91(phone: str, message: str) -> bool:
    settings = get_settings()
    if not settings.MSG91_AUTH_KEY:
        logger.warning("SMS_PROVIDER=msg91 but MSG91_AUTH_KEY is unset; logging instead")
        return False
    digits = "".join(ch for ch in phone if ch.isdigit())[-10:]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.msg91.com/api/sendhttp.php",
                data={
                    "authkey": settings.MSG91_AUTH_KEY,
                    "mobiles": f"91{digits}",
                    "message": message,
                    "sender": settings.MSG91_SENDER_ID,
                    "route": "4",
                    "country": "91",
                },
            )
            response.raise_for_status()
        logger.info("SMS sent via msg91 to %s...%s", phone[:2], phone[-2:])
        return True
    except Exception:
        logger.warning("msg91 send failed; message logged instead", exc_info=True)
        return False


async def _send_twilio(phone: str, message: str) -> bool:
    settings = get_settings()
    twilio_from = _twilio_from(settings)
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and twilio_from):
        logger.warning("SMS_PROVIDER=twilio but TWILIO_* credentials are incomplete; logging instead")
        return False
    to = format_sms_to(phone)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                data={"From": twilio_from, "To": to, "Body": message},
            )
            response.raise_for_status()
        logger.info("SMS sent via twilio to %s...%s", phone[:2], phone[-2:])
        return True
    except Exception:
        logger.warning("twilio send failed; message logged instead", exc_info=True)
        return False


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send a transactional email; True when handed to SMTP, False when logged."""
    settings = get_settings()
    if not email_configured():
        logger.info("Email to %s (logged, SMTP unconfigured) — subject: %s", to, subject)
        return False

    def _send() -> None:
        import smtplib
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(_smtp_username(settings), settings.SMTP_PASSWORD)
            smtp.send_message(message)

    try:
        await asyncio.to_thread(_send)
        logger.info("Email sent to %s — subject: %s", to, subject)
        return True
    except Exception:
        logger.warning("SMTP send to %s failed; logged instead", to, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Citizen contact channel (Fernet-encrypted phone, opt-in only)
# ---------------------------------------------------------------------------

def _fernet():
    key = (get_settings().PHONE_FERNET_KEY or "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode())
    except Exception:
        logger.warning("PHONE_FERNET_KEY is not a valid Fernet key; citizen SMS disabled")
        return None


def encrypt_phone(phone: str) -> bytes | None:
    cipher = _fernet()
    if cipher is None:
        return None
    return cipher.encrypt(phone.encode())


def decrypt_phone(blob: bytes) -> str | None:
    cipher = _fernet()
    if cipher is None or not blob:
        return None
    try:
        return cipher.decrypt(bytes(blob)).decode()
    except Exception:
        logger.warning("Could not decrypt stored citizen phone", exc_info=True)
        return None


async def notify_citizen(db, user_id, message: str) -> bool:
    """Status SMS to one opted-in citizen. False when no channel exists —
    callers must not treat False as delivered."""
    from app.db.models import User

    try:
        user = await db.get(User, user_id)
    except Exception:
        return False
    if user is None or not user.notify_sms or not getattr(user, "phone_enc", None):
        return False
    phone = decrypt_phone(user.phone_enc)
    if not phone:
        return False
    return await send_sms(phone, message)
