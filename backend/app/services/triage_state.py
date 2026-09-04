"""Idempotent persistence helpers for the Temporal triage pipeline.

The API creates the submission/problem/fallback assignment synchronously, so
activities only advance records that are still in a pre-decision state. Manual
officer, university, CSR, or completion states are never overwritten.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Problem, RouteAssignment, Submission

PRE_DECISION_STATUSES = frozenset({"INGESTED", "PENDING_TRIAGE", "TRIAGING", "PENDING_OFFICER_REVIEW", "OFFICER_REVIEW"})
AUTO_ASSIGNMENT_STATUS = "PENDING_APPROVAL"


def parse_uuid(value: str, *, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"Invalid {label}: expected a UUID") from exc


async def load_submission_problem(session: AsyncSession, submission_id: str) -> tuple[Submission, Problem | None]:
    submission_uuid = parse_uuid(submission_id, label="submission_id")
    submission = await session.get(Submission, submission_uuid)
    if submission is None:
        raise ValueError("Submission not found")
    problem = (
        await session.execute(select(Problem).where(Problem.submission_id == submission.submission_id))
    ).scalars().first()
    return submission, problem


def advance_status(entity, status: str) -> bool:
    """Advance only pre-decision records; return whether the status changed."""
    if entity.status in PRE_DECISION_STATUSES and entity.status != status:
        entity.status = status
        return True
    return False


async def audit_once(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_role: str,
    after: dict | None = None,
) -> bool:
    exists = (
        await session.execute(
            select(AuditLog.log_id).where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
                AuditLog.action == action,
            )
        )
    ).first()
    if exists:
        return False
    session.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id="temporal-worker",
            actor_role=actor_role,
            after_snapshot=after or {},
        )
    )
    return True


async def replace_auto_route_offers(
    session: AsyncSession,
    *,
    problem: Problem,
    offers: list[dict],
    sla_days: int = 7,
) -> list[RouteAssignment]:
    """Replace only system-generated pending offers; preserve manual decisions."""
    existing = (
        await session.execute(
            select(RouteAssignment).where(
                RouteAssignment.problem_id == problem.problem_id,
                RouteAssignment.status == AUTO_ASSIGNMENT_STATUS,
            )
        )
    ).scalars().all()
    for row in existing:
        await session.delete(row)
    await session.flush()
    deadline = datetime.now(timezone.utc) + timedelta(days=sla_days)
    created: list[RouteAssignment] = []
    for rank, offer in enumerate(offers[:3], start=1):
        created.append(
            RouteAssignment(
                problem_id=problem.problem_id,
                university_id=parse_uuid(offer["university_id"], label="university_id"),
                rank_order=rank,
                match_score=float(offer["match_score"]),
                score_breakdown=dict(offer.get("score_breakdown") or {}),
                sla_deadline=deadline,
                status=AUTO_ASSIGNMENT_STATUS,
            )
        )
        session.add(created[-1])
    return created
