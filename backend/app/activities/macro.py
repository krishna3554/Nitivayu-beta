"""Monthly macro-triage activities (WP-11): the four activities the
MonthlyMacroTriageWorkflow references, implemented for real.

- audit_officer_overrides: this month's OVERRIDE decisions → JSON report.
- recompute_theme_centroids: mean summary_embedding per category → theme_centroids.
- apply_seasonal_weights: calendar-month routing adjustments → seasonal_weights.
- run_csr_matching: problem categories × industry CSR focus overlap →
  funding_links rows with status SUGGESTED for CSR desks to act on.
"""

import calendar
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from temporalio import activity

from app.db.models import AuditLog, FundingLink, Industry, Problem, SeasonalWeight, ThemeCentroid
from app.db.worker_session import worker_session
from app.services.triage_state import audit_once

logger = logging.getLogger(__name__)


@activity.defn
async def audit_officer_overrides_activity(data: dict) -> dict:
    """Collect this month's officer OVERRIDE decisions into a JSON report."""
    from pathlib import Path

    from app.config import get_settings

    payload = data or {}
    month = payload.get("month") or datetime.now(timezone.utc).strftime("%Y-%m")
    if isinstance(month, int):
        month = f"{datetime.now(timezone.utc):%Y}-{month:02d}"
    async with worker_session() as session:
        rows = (await session.execute(
            select(AuditLog).where(
                AuditLog.action == "OFFICER_OVERRIDE",
                func.to_char(AuditLog.timestamp, "YYYY-MM") == month,
            ).order_by(AuditLog.timestamp.desc()).limit(1000)
        )).scalars().all()
        overrides = [
            {
                "entity_id": r.entity_id, "actor_id": r.actor_id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "after": r.after_snapshot,
            }
            for r in rows
        ]
    import json as _json

    directory = Path(get_settings().OUTPUT_ROOT) / "audit"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"overrides-{month}.json"
    path.write_text(_json.dumps({"month": month, "count": len(overrides), "overrides": overrides}, default=str), encoding="utf-8")
    logger.info("Officer overrides audit for %s: %d rows → %s", month, len(overrides), path)
    return {"month": month, "count": len(overrides), "path": str(path)}


@activity.defn
async def recompute_theme_centroid_embeddings_activity(data: dict) -> dict:
    """Mean problem embedding per category over verified/routed volume."""
    updated = 0
    async with worker_session() as session:
        categories = (await session.execute(
            select(Problem.category).where(
                Problem.summary_embedding.isnot(None),
                Problem.status.in_(["ROUTED", "ACCEPTED", "COMPLETED"]),
            ).distinct()
        )).scalars().all()
        for category in categories:
            if not category:
                continue
            vectors = (await session.execute(
                select(Problem.summary_embedding).where(
                    Problem.category == category,
                    Problem.summary_embedding.isnot(None),
                    Problem.status.in_(["ROUTED", "ACCEPTED", "COMPLETED"]),
                ).limit(2000)
            )).scalars().all()
            matrix = [[float(v) for v in list(vec)] for vec in vectors if vec is not None]
            if not matrix:
                continue
            dim = len(matrix[0])
            centroid = [sum(col) / len(matrix) for col in zip(*matrix)]
            row = await session.get(ThemeCentroid, category)
            if row is None:
                row = ThemeCentroid(category=category, embedding=centroid, sample_count=len(matrix))
                session.add(row)
            else:
                row.embedding = centroid
                row.sample_count = len(matrix)
            updated += 1
        await session.commit()
    logger.info("Theme centroids recomputed for %d categories", updated)
    return {"categories": updated}


# Month → category multipliers applied on top of base routing weights.
# Rationale documented in-row: monsoon (Jun–Sep) lifts Water/Environment and
# Health (waterborne disease); Oct–Nov harvest season lifts Agriculture;
# Dec–Jan winter lifts Energy (heating/power cuts).
_SEASONAL_PROFILE = {
    6: {"Water": 1.25, "Environment": 1.15, "Health": 1.1},
    7: {"Water": 1.3, "Environment": 1.15, "Health": 1.15},
    8: {"Water": 1.3, "Environment": 1.15, "Health": 1.15},
    9: {"Water": 1.2, "Environment": 1.1, "Health": 1.1},
    10: {"Agriculture": 1.2, "Livelihood": 1.1},
    11: {"Agriculture": 1.2, "Livelihood": 1.1},
    12: {"Energy": 1.2, "Health": 1.05},
    1: {"Energy": 1.2, "Health": 1.05},
}


@activity.defn
async def apply_seasonal_weight_adjustments_activity(data: dict) -> dict:
    """Persist this month's theme multipliers to seasonal_weights."""
    payload = data or {}
    raw_month = payload.get("month")
    try:
        # Accepts 9, "9", or "2026-09" (the workflow passes YYYY-MM).
        month = int(str(raw_month).split("-")[-1])
    except (TypeError, ValueError):
        month = datetime.now(timezone.utc).month
    weights = _SEASONAL_PROFILE.get(month, {})
    async with worker_session() as session:
        row = await session.get(SeasonalWeight, month)
        if row is None:
            session.add(SeasonalWeight(month=month, theme_weights=weights))
        else:
            row.theme_weights = weights
        await session.commit()
    month_name = calendar.month_name[month]
    logger.info("Seasonal weights for %s (%d): %s", month_name, month, weights or "neutral")
    return {"month": month, "weights": weights}


@activity.defn
async def run_csr_matching_activity(data: dict) -> dict:
    """Suggest CSR matches: ROUTED/ACCEPTED problems whose category overlaps
    an industry's csr_focus_areas → funding_links(status='SUGGESTED')."""
    suggested = 0
    async with worker_session() as session:
        industries = (await session.execute(select(Industry))).scalars().all()
        problems = (await session.execute(
            select(Problem).where(Problem.status.in_(["ROUTED", "ACCEPTED"])).order_by(Problem.created_at.desc()).limit(500)
        )).scalars().all()
        existing = (await session.execute(
            select(FundingLink.problem_id, FundingLink.industry_id).where(FundingLink.status == "SUGGESTED")
        )).all()
        seen = set(existing)
        for problem in problems:
            category = (problem.category or "").strip().lower()
            if not category:
                continue
            for industry in industries:
                focus = {str(f).strip().lower() for f in (industry.csr_focus_areas or [])}
                if category not in focus:
                    continue
                if (problem.problem_id, industry.industry_id) in seen:
                    continue
                session.add(FundingLink(
                    problem_id=problem.problem_id,
                    team_id=None,
                    industry_id=industry.industry_id,
                    pledged_amount_inr=0,
                    status="SUGGESTED",
                ))
                seen.add((problem.problem_id, industry.industry_id))
                suggested += 1
        await audit_once(
            session, entity_type="batch", entity_id="monthly-macro",
            action="CSR_MATCHED", actor_role="worker", after={"suggested": suggested},
        )
        await session.commit()
    logger.info("CSR matching suggested %d links", suggested)
    return {"suggested": suggested}
