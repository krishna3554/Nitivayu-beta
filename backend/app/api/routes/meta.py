"""Public meta/config endpoints — the single source of truth for values the UI
used to hardcode: SLA windows, routing weights, categories, districts, and
(demo-mode only) seeded login credentials. Also serves the public marketing
data (stats, partners, featured cases) so the landing page shows real numbers.

All endpoints here are unauthenticated but heavily cacheable (Redis, 1h).
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import FundingLink, Industry, Problem, RouteAssignment, Submission, University
from app.api.deps import get_db
from app.services import redis_client as redis_mod
from app.services.llm import CATEGORIES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meta", tags=["meta"])

META_CACHE_TTL_SECONDS = 3600

# Canonical Jharkhand district list — previously hardcoded in the frontend
# (ui/EvidenceComposer.jsx). The UI fetches this and only falls back to a
# bundled copy when the API is unreachable.
JHARKHAND_DISTRICTS = [
    "Ranchi", "Dhanbad", "Bokaro", "East Singhbhum", "West Singhbhum", "Seraikela-Kharsawan",
    "Palamu", "Garhwa", "Latehar", "Chatra", "Hazaribagh", "Koderma", "Giridih", "Deoghar",
    "Dumka", "Godda", "Sahebganj", "Pakur", "Jamtara", "Lohardaga", "Gumla", "Simdega",
    "Khunti", "Ramgarh",
]

LANGUAGES = ["hindi", "hinglish", "english"]


async def _cached_json(key: str):
    redis = redis_mod.get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def _store_json(key: str, body) -> None:
    redis = redis_mod.get_redis()
    if redis is None:
        return
    try:
        await redis.set(key, json.dumps(body), ex=META_CACHE_TTL_SECONDS)
    except Exception:
        pass


@router.get("/config")
async def meta_config():
    """Pipeline constants the UI renders (SLA countdowns, score breakdowns,
    intake limits). Cached briefly; values come from Settings so ops can tune
    them without redeploying the frontend."""
    cached = await _cached_json("meta:config")
    if cached is not None:
        return cached
    settings = get_settings()
    body = {
        "officer_sla_hours": settings.OFFICER_SLA_HOURS,
        "university_sla_hours": settings.UNIVERSITY_SLA_HOURS,
        "score_weights": {
            "theme": settings.SCORE_WEIGHT_THEME,
            "semantic": settings.SCORE_WEIGHT_SEMANTIC,
            "capacity": settings.SCORE_WEIGHT_CAPACITY,
            "geo": settings.SCORE_WEIGHT_GEO,
        },
        "categories": list(CATEGORIES),
        "languages": LANGUAGES,
        "districts": JHARKHAND_DISTRICTS,
        "max_upload_mb": settings.MAX_UPLOAD_BYTES // 1_000_000,
        "milestone_structure": [
            {"num": 1, "code": "M1", "title": "Feasibility Study", "days": settings.MILESTONE_M1_DAYS},
            {"num": 2, "code": "M2", "title": "Prototype Design", "days": settings.MILESTONE_M2_DAYS},
            {"num": 3, "code": "M3", "title": "Field Validation", "days": settings.MILESTONE_M3_DAYS},
        ],
    }
    await _store_json("meta:config", body)
    return body


@router.get("/demo-accounts")
async def demo_accounts():
    """Seeded credentials for the login page demo panel. 404 unless DEMO_MODE
    is explicitly enabled — production builds never expose this."""
    if not get_settings().DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "accounts": [
            {"role": "Officer", "email": "officer@nitivayu.gov.in", "password": "password123"},
            {"role": "Admin", "email": "admin@nitivayu.in", "password": "admin"},
            {"role": "University", "email": "iic.head@bitmesra.ac.in", "password": "demo1234", "note": "any password works"},
            {"role": "CSR", "email": "csr@tatasteel.com", "password": "demo1234", "note": "any password works"},
        ]
    }


@router.get("/public-stats")
async def public_stats(db: AsyncSession = Depends(get_db)):
    """Landing/impact page hero numbers — real aggregates, no auth."""
    cached = await _cached_json("meta:public-stats")
    if cached is not None:
        return cached
    total_submissions = (await db.execute(select(func.count(Submission.submission_id)))).scalar_one()
    resolved = (await db.execute(
        select(func.count(Problem.problem_id)).where(Problem.status.in_(["COMPLETED", "ACCEPTED", "ROUTED"]))
    )).scalar_one()
    active_universities = (await db.execute(select(func.count(University.university_id)))).scalar_one()
    total_pledged = (await db.execute(select(func.coalesce(func.sum(FundingLink.pledged_amount_inr), 0)))).scalar_one()
    districts_covered = (await db.execute(
        select(func.count(func.distinct(Submission.geo_district))).where(Submission.geo_district.isnot(None))
    )).scalar_one()
    body = {
        "total_submissions": total_submissions,
        "resolved": resolved,
        "active_universities": active_universities,
        "total_pledged_inr": float(total_pledged or 0),
        "districts_covered": districts_covered,
    }
    await _store_json("meta:public-stats", body)
    return body


@router.get("/partners")
async def partners(db: AsyncSession = Depends(get_db)):
    """Public-safe listing of the university network and CSR partners."""
    cached = await _cached_json("meta:partners")
    if cached is not None:
        return cached
    universities = (await db.execute(select(University).order_by(University.name))).scalars().all()
    industries = (await db.execute(select(Industry).order_by(Industry.name))).scalars().all()
    body = {
        "universities": [
            {"name": u.name, "district": u.district, "specializations": list(u.domain_specializations or [])}
            for u in universities
        ],
        "industries": [
            {"name": i.name, "sector": i.sector}
            for i in industries
        ],
    }
    await _store_json("meta:partners", body)
    return body


@router.get("/featured-cases")
async def featured_cases(db: AsyncSession = Depends(get_db)):
    """Latest genuinely completed (or accepted) challenges with their real
    routing match scores — powers the landing-page case rail. Empty list when
    nothing has resolved yet; the UI hides the rail rather than fabricate."""
    cached = await _cached_json("meta:featured-cases")
    if cached is not None:
        return cached
    rows = (await db.execute(
        select(Problem, Submission.geo_district)
        .join(Submission, Problem.submission_id == Submission.submission_id, isouter=True)
        .where(Problem.status.in_(["COMPLETED", "ACCEPTED"]))
        .order_by(Problem.updated_at.desc())
        .limit(4)
    )).all()
    cases = []
    for problem, district in rows:
        assignment = (await db.execute(
            select(RouteAssignment)
            .where(RouteAssignment.problem_id == problem.problem_id, RouteAssignment.status.in_(["OFFERED", "ACCEPTED"]))
            .order_by(RouteAssignment.rank_order)
            .limit(1)
        )).scalars().first()
        university_name = None
        if assignment is not None:
            university = await db.get(University, assignment.university_id)
            university_name = university.name if university else None
        cases.append({
            "title": problem.title,
            "category": problem.category,
            "severity": problem.severity_score,
            "district": district,
            "status": problem.status,
            "university_name": university_name,
            "match_score": assignment.match_score if assignment else None,
        })
    body = {"cases": cases}
    await _store_json("meta:featured-cases", body)
    return body
