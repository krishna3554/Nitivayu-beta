"""Reporter notifications: email (SMTP) + SMS (Twilio/MSG91) with log fallback.

Design rules:
- Contact comes only from explicit opt-in at intake (`notify_consent`); the
  hashed citizen identity columns are never reversed for delivery.
- Delivery is best-effort and NEVER raises: every provider call is wrapped,
  anything failing degrades to a backend-log line. Endpoints schedule this
  via BackgroundTasks so slow SMTP/SMS gateways never block responses.
- `log` (default) writes the exact message that WOULD be sent — the full
  flow is verifiable without credentials.
"""

import logging
import re

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_DIGITS = re.compile(r"\D+")

CONSENT_TRUE = {"true", "1", "yes", "y", "on"}


def normalize_email(raw: str | None) -> str | None:
    cleaned = (raw or "").strip().lower()
    if not cleaned or len(cleaned) > 255 or not _EMAIL_RE.match(cleaned):
        return None
    return cleaned


def normalize_phone(raw: str | None) -> str | None:
    digits = _PHONE_DIGITS.sub("", raw or "")
    if len(digits) > 13:
        digits = digits[-13:]
    if len(digits) < 10 or len(digits) > 13:
        return None
    return digits


def parse_consent(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in CONSENT_TRUE


# ---------------------------------------------------------------------------
# Message composition (one place: mail subject + SMS share the wording)
# ---------------------------------------------------------------------------

_SUBJECTS = {
    "submitted": "Nitivayu: report received [{token}]",
    "approved": "Nitivayu: officer approved your report [{token}]",
    "rejected": "Nitivayu: update on your report [{token}]",
    "overridden": "Nitivayu: officer routed your report [{token}]",
    "accepted": "Nitivayu: university accepted your report [{token}]",
    "declined": "Nitivayu: update on your report [{token}]",
    "update": "Nitivayu: progress update on [{token}]",
    "milestone": "Nitivayu: milestone submitted for [{token}]",
}


def compose(kind: str, *, tracking_token: str, title: str, detail: str = "") -> tuple[str, str]:
    """Return (subject, body) for a notification kind. Unknown kinds are generic."""
    token = tracking_token or "your report"
    headline = {
        "submitted": f"Your civic report has been received. Tracking token: {token}.",
        "approved": "A nodal officer approved your report. It is now routed to a university for action.",
        "rejected": "A nodal officer reviewed your report and marked it non-actionable.",
        "overridden": "A nodal officer reviewed your report and routed it to a university.",
        "accepted": "A university accepted your report and is forming a project team.",
        "declined": "A university could not take up your report; it returns to the routing pool.",
        "update": "The university posted a progress update on your report.",
        "milestone": "The university submitted milestone evidence for officer verification.",
    }.get(kind, "There is an update on your civic report.")
    subject = _SUBJECTS.get(kind, "Nitivayu update [{token}]").format(token=token)
    lines = [
        headline,
        f"Report: {(title or '')[:140]}",
        f"Track live: /track/{token}",
    ]
    if detail:
        lines.append(str(detail)[:300])
    lines.append("— Team Nitivayu (Jharkhand civic pipeline)")
    return subject, "\n".join(lines)


# ---------------------------------------------------------------------------
# Providers (all best-effort; return True when actually dispatched)
# ---------------------------------------------------------------------------

def _redact(value: str) -> str:
    if not value:
        return "—"
    if "@" in value:
        user, _, domain = value.partition("@")
        return f"{user[:2]}***@{domain}"
    return f"{value[:2]}***{value[-2:]}"


def send_email(to: str, subject: str, body: str) -> bool:
    """SMTP email; False (log-only) when SMTP_HOST is unset or on any error."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.SMTP_HOST or not to:
        logger.info("MAIL to %s :: %s\n%s", _redact(to), subject, body)
        return False
    try:
        import smtplib
        from email.mime.text import MIMEText

        message = MIMEText(body, "plain", "utf-8")
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM
        message["To"] = to
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as client:
            if settings.SMTP_USE_TLS:
                client.starttls()
            if settings.SMTP_USERNAME:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            client.sendmail(settings.SMTP_FROM, [to], message.as_string())
        logger.info("MAIL sent to %s :: %s", _redact(to), subject)
        return True
    except Exception as exc:
        logger.warning("MAIL to %s failed (%s); logged instead\n%s", _redact(to), exc, body)
        return False


def send_sms(to: str, message: str) -> bool:
    """SMS via SMS_PROVIDER (log/twilio/msg91); False unless dispatched."""
    from app.config import get_settings

    settings = get_settings()
    provider = (settings.SMS_PROVIDER or "log").lower()
    if not to:
        return False
    if provider == "twilio":
        return _send_twilio(settings, to, message)
    if provider == "msg91":
        return _send_msg91(settings, to, message)
    if provider != "log":
        logger.warning("Unknown SMS_PROVIDER '%s'; logging instead", provider)
    logger.info("SMS to %s :: %s", _redact(to), message)
    return False


def _send_twilio(settings, to: str, message: str) -> bool:
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM):
        logger.warning("Twilio selected but TWILIO_* incomplete; logging instead")
        logger.info("SMS to %s :: %s", _redact(to), message)
        return False
    try:
        import httpx

        response = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            data={"From": settings.TWILIO_FROM, "To": f"+{to}" if not to.startswith("+") else to, "Body": message},
            timeout=15,
        )
        response.raise_for_status()
        logger.info("SMS sent via Twilio to %s", _redact(to))
        return True
    except Exception as exc:
        logger.warning("Twilio SMS to %s failed (%s); logged instead", _redact(to), exc)
        logger.info("SMS to %s :: %s", _redact(to), message)
        return False


def _send_msg91(settings, to: str, message: str) -> bool:
    if not settings.MSG91_AUTH_KEY:
        logger.warning("MSG91 selected but MSG91_AUTH_KEY unset; logging instead")
        logger.info("SMS to %s :: %s", _redact(to), message)
        return False
    try:
        import httpx

        payload: dict = {
            "authkey": settings.MSG91_AUTH_KEY,
            "mobiles": to,
            "message": message,
            "sender": settings.MSG91_SENDER,
            "route": settings.MSG91_ROUTE,
        }
        if settings.MSG91_DLT_TEMPLATE_ID:
            payload["DLT_TE_ID"] = settings.MSG91_DLT_TEMPLATE_ID
        response = httpx.post("https://api.msg91.com/api/v5/sms", json=payload, timeout=15)
        response.raise_for_status()
        logger.info("SMS sent via MSG91 to %s", _redact(to))
        return True
    except Exception as exc:
        logger.warning("MSG91 SMS to %s failed (%s); logged instead", _redact(to), exc)
        logger.info("SMS to %s :: %s", _redact(to), message)
        return False


# ---------------------------------------------------------------------------
# Fan-out entry point (called from BackgroundTasks — sync, never raises)
# ---------------------------------------------------------------------------

def notify_reporter(
    contact_email: str | None,
    contact_phone: str | None,
    *,
    kind: str,
    tracking_token: str,
    title: str = "",
    detail: str = "",
) -> dict:
    """Send mail and/or SMS for one lifecycle event. Returns what was tried.

    Never raises — safe to schedule unconditionally from request handlers.
    """
    result: dict = {"kind": kind, "email": False, "sms": False}
    try:
        subject, body = compose(kind, tracking_token=tracking_token, title=title, detail=detail)
        sms_body = f"{subject} {(title or '')[:100]} Track: {tracking_token}".strip()[:320]
        if contact_email:
            result["email"] = send_email(contact_email, subject, body)
        if contact_phone:
            result["sms"] = send_sms(contact_phone, sms_body)
        if not contact_email and not contact_phone:
            logger.info("NOTIFY skipped (%s %s): no opt-in contact", kind, tracking_token)
    except Exception as exc:
        logger.warning("NOTIFY %s %s failed safely: %s", kind, tracking_token, exc)
    return result
