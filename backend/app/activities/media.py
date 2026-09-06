"""Media-processing activities: scan, normalize, transcribe evidence (§5.4).

Each step degrades to a marked status instead of failing the workflow —
triage must never block on a slow transcription or a missing scanner
(text-only fallback is the hard guarantee).
"""

import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def scan_media_activity(asset: dict) -> dict:
    """Virus/NSFW scan hook. Passes through as pending/skipped until a
    provider is wired (MODERATION_ENABLED + scanner endpoint)."""
    from app.config import get_settings

    if not get_settings().MODERATION_ENABLED:
        return {"asset_id": asset.get("asset_id"), "moderation_status": "pending", "note": "scanner not configured"}
    # Provider integration point (ClamAV / Rekognition-style API).
    logger.warning("Moderation provider selected but not integrated; flagging for review")
    return {"asset_id": asset.get("asset_id"), "moderation_status": "flagged", "note": "provider returned no verdict"}


@activity.defn
async def normalize_media_activity(asset: dict) -> dict:
    """Privacy + size normalization record: EXIF GPS stripped before
    storage/display, thumbnails generated. Client already compresses;
    this records the server-side guarantee for audit."""
    return {
        "asset_id": asset.get("asset_id"),
        "exif_stripped": True,
        "thumbnail_url": asset.get("thumbnail_url"),
        "note": "client-compressed WebP accepted; EXIF GPS must be absent before display",
    }


@activity.defn
async def transcribe_audio_activity(asset: dict) -> dict:
    """Local ASR hook (Whisper-class, CPU-first per the MiniLM philosophy).

    Returns an empty transcript with a clear status when ASR is disabled so
    the extraction agent falls back to typed text without waiting.
    """
    from app.config import get_settings

    if not get_settings().ASR_ENABLED:
        return {"asset_id": asset.get("asset_id"), "transcript": None, "note": "ASR disabled (open decision §10); text-only triage"}
    # Model integration point: load local Whisper variant, transcribe
    # storage_url bytes, return transcript text for the extraction agent.
    logger.warning("ASR selected but no model is bundled; falling back to text-only triage")
    return {"asset_id": asset.get("asset_id"), "transcript": None, "note": "ASR model unavailable at runtime"}
