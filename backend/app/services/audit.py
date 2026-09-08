"""Request-scoped audit context (WP-3).

Every HTTP request gets a request-id (contextvar, set by middleware) and the
client IP. Audit rows written during the request automatically carry
``ip_address``/``request_id`` — previously never populated. Temporal
activities run outside request context; those fields stay NULL there, which
honestly marks worker-written rows.
"""

import contextvars
import logging
import uuid

from app.db.models import AuditLog

logger = logging.getLogger(__name__)

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("nitivayu_request_id", default=None)
_request_ip: contextvars.ContextVar[str | None] = contextvars.ContextVar("nitivayu_request_ip", default=None)


def set_request_context(request_id: str | None, ip: str | None) -> tuple:
    """Called by middleware; returns tokens for reset."""
    return _request_id.set(request_id), _request_ip.set(ip)


def reset_request_context(tokens: tuple) -> None:
    _request_id.reset(tokens[0])
    _request_ip.reset(tokens[1])


def current_request_id() -> str | None:
    return _request_id.get()


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def make_audit(
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: str,
    actor_role: str,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog:
    """Build an AuditLog with the request context filled in."""
    return AuditLog(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        actor_id=str(actor_id),
        actor_role=actor_role,
        before_snapshot=before,
        after_snapshot=after,
        ip_address=_request_ip.get(),
        request_id=_request_id.get(),
    )
