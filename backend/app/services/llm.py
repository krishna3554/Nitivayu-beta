"""OpenRouter-backed issue extraction with an explicit local fallback.

Successful extractions are cached in Redis (``llm:cache:<sha256>``, 7-day TTL)
keyed by the SHA-256 digest of ``model + redacted text`` so repeated reports of
the same issue skip the paid API call. Every extraction result is normalized to
the workflow schema before it is returned. When no API key is configured the
activity uses the deterministic local extractor and marks
``source="local_fallback"``; it never pretends an AI call succeeded.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings
from app.services import redis_client as redis_mod

logger = logging.getLogger(__name__)

CATEGORIES = (
    "Water",
    "Environment",
    "Infrastructure",
    "Health",
    "Education",
    "Livelihood",
    "Energy",
    "Agriculture",
    "Sanitation",
    "Governance",
)

_CATEGORY_KEYWORDS = {
    "Water": ("water", "drain", "flood", "paani", "handpump", "fluoride", "river", "contamination"),
    "Health": ("health", "hospital", "medical", "phc", "doctor", "disease", "malnutrition", "anganwadi"),
    "Infrastructure": ("road", "bridge", "street", "light", "school building", "roof", "electricity", "power"),
    "Agriculture": ("farm", "crop", "irrigation", "paddy", "mandi", "cold storage", "tomato"),
    "Environment": ("pollution", "waste", "smoke", "dust", "effluent", "emission", "forest fire", "mining"),
    "Education": ("school", "teacher", "student", "education", "classroom"),
    "Livelihood": ("artisan", "handicraft", "livelihood", "employment", "wage", "middlemen"),
    "Energy": ("power cut", "solar", "electricity", "energy"),
    "Sanitation": ("toilet", "sanitation", "defecation", "hygiene", "sewage"),
}

_SEVERITY_WORDS = {"critical": 5, "severe": 5, "urgent": 4, "danger": 4, "high": 4, "broken": 4, "medium": 3, "moderate": 3, "low": 2, "minor": 2}

_CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days


async def _cache_lookup(cache_key: str) -> dict | None:
    """Redis-backed extraction cache; never raises, returns None on any miss."""
    redis = redis_mod.get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(f"llm:cache:{cache_key}")
        if not raw:
            return None
        entry = json.loads(raw)
        return entry if isinstance(entry, dict) else None
    except Exception:
        logger.warning("LLM cache lookup failed", exc_info=True)
        return None


async def _cache_store(cache_key: str, result: dict) -> None:
    """Persist a validated extraction; failures are logged, never raised."""
    redis = redis_mod.get_redis()
    if redis is None:
        return
    try:
        await redis.set(f"llm:cache:{cache_key}", json.dumps(result), ex=_CACHE_TTL_SECONDS)
    except Exception:
        logger.warning("LLM cache store failed", exc_info=True)


def redact_pii(text: str) -> str:
    redacted = re.sub(r"\d{10}", "[REDACTED PHONE]", text)
    return re.sub(r"\d{4}\s\d{4}\s\d{4}", "[REDACTED AADHAAR]", redacted)


def canonicalize_category(value: Any) -> str:
    text = str(value or "").strip().lower()
    for category in CATEGORIES:
        if text == category.lower():
            return category
    mapping = {
        "water pollution": "Water",
        "air pollution": "Environment",
        "economic development": "Livelihood",
    }
    if text in mapping:
        return mapping[text]
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "Governance"


def coerce_severity(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Severity must be an integer between 1 and 5")
    if isinstance(value, (int, float)):
        severity = int(value)
    else:
        severity = _SEVERITY_WORDS.get(str(value or "").strip().lower(), 3)
    if severity < 1 or severity > 5:
        raise ValueError("Severity must be an integer between 1 and 5")
    return severity


def heuristic_category(text: str) -> str:
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Governance"


def heuristic_severity(text: str) -> int:
    lowered = text.lower()
    if any(word in lowered for word in ("urgent", "danger", "flood", "broken", "severe", "critical")):
        return 4
    return 3


def _validate_extraction(payload: Any, *, source: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Extraction result must be a JSON object")
    title = str(payload.get("title") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    location_hint = str(payload.get("location_hint") or "Unknown").strip() or "Unknown"
    if not title:
        raise ValueError("Extraction result is missing a title")
    if not summary:
        raise ValueError("Extraction result is missing a summary")
    return {
        "title": title[:255],
        "summary": summary,
        "category": canonicalize_category(payload.get("category")),
        "severity": coerce_severity(payload.get("severity")),
        "location_hint": location_hint[:255],
        "source": source,
    }


def _local_extraction(raw_text: str) -> dict:
    cleaned = " ".join(raw_text.split())
    sentence = cleaned.split(".")[0].strip() or cleaned
    return _validate_extraction(
        {
            "title": sentence[:120],
            "summary": cleaned[:500],
            "category": heuristic_category(cleaned),
            "severity": heuristic_severity(cleaned),
            "location_hint": "Unknown",
        },
        source="local_fallback",
    )


def _cache_key(raw_text: str, model: str) -> str:
    digest = hashlib.sha256("|".join([model, " ".join(raw_text.split())]).encode("utf-8")).hexdigest()
    return digest


async def extract_issue_details(raw_text: str) -> dict:
    """Extract a structured issue with OpenRouter, else an explicit local fallback."""
    cleaned = redact_pii(raw_text or "").strip()
    if not cleaned:
        raise ValueError("Issue description cannot be blank")
    settings = get_settings()
    cache_key = _cache_key(cleaned, settings.OPENROUTER_MODEL)
    if settings.LLM_CACHE:
        cached = await _cache_lookup(cache_key)
        if cached:
            try:
                result = _validate_extraction(cached, source="cache")
                logger.info("Extraction served from cache")
                return result
            except ValueError as exc:
                logger.warning("Cache entry invalid, ignoring: %s", exc)
    if not settings.OPENROUTER_API_KEY:
        logger.info("No OpenRouter key configured; using deterministic local extraction")
        return _local_extraction(cleaned)

    prompt = (
        "Extract this citizen civic-issue report into JSON with exactly these keys: "
        "title (<=120 chars), summary (<=500 chars), category (one of: "
        + ", ".join(CATEGORIES)
        + "), severity (integer 1-5), location_hint (<=120 chars). "
        "Return JSON only, no markdown. Report: " + cleaned[:2000]
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                json={
                    "model": settings.OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        if status in (401, 403):
            raise ValueError("OpenRouter authentication failed; check OPENROUTER_API_KEY") from exc
        if status == 402:
            # The key is valid but the account cannot pay for inference (most
            # common on free-tier/demo keys). Degrade observably to the
            # deterministic local extractor instead of failing the triage
            # pipeline; the result is marked so downstream data shows it.
            logger.warning("OpenRouter quota exhausted (402); using local extraction fallback")
            return _local_extraction(cleaned)
        raise RuntimeError(f"OpenRouter request failed with status {status}") from exc
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise RuntimeError("OpenRouter request failed") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("OpenRouter response was missing message content") from exc
    text = str(content or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise ValueError("OpenRouter response was not valid JSON") from exc
    result = _validate_extraction(parsed, source="openrouter")
    if settings.LLM_CACHE:
        # Store the raw validated payload (source is re-stamped on read).
        await _cache_store(cache_key, {k: v for k, v in result.items() if k != "source"})
    return result
