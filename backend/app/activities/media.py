"""Media-processing activities: scan, normalize, transcribe evidence (§5.4).

WP-10: these actually run now (MediaProcessingWorkflow starts at intake when
attachments exist) and do real work:
- scan: magic-byte + size validation, persisted to media_assets; mismatches
  are FLAGGED (hidden from non-officers until cleared), unreadable stores
  stay PENDING (unverified, honest).
- normalize: server-side EXIF strip + ≤1600px re-encode + thumbnail for
  locally stored photos (Pillow, worker image).
- transcribe: local-ASR hook — honest NULL transcript until a model is
  bundled (ASR_ENABLED gate); the text-only triage guarantee holds.

Each step degrades to a marked status instead of failing the workflow.
"""

import logging

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.db.models import MediaAsset
from app.db.worker_session import worker_session

logger = logging.getLogger(__name__)

MAX_IMAGE_EDGE = 1600
THUMB_EDGE = 320

# Magic-byte signatures by media kind.
_PHOTO_MAGIC = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG", "png"),
    (b"GIF8", "gif"),
)
_AUDIO_MAGIC = (
    (b"\x1a\x45\xdf\xa3", "webm"),
    (b"OggS", "ogg"),
    (b"RIFF", "wav?"),  # + "WAVE" at offset 8
    (b"fLaC", "flac"),
)


def _sniff(kind: str, head: bytes) -> str | None:
    if kind == "photo":
        for magic, label in _PHOTO_MAGIC:
            if head.startswith(magic):
                return label
        if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
            return "webp"
        return None
    for magic, label in _AUDIO_MAGIC:
        if head.startswith(magic):
            return label
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "mp4/m4a"
    return None


def _load_bytes(storage_url: str) -> bytes | None:
    """Best-effort byte load for s3:// and local-mirror URLs. None when the
    store cannot be read (inline:// fallbacks, missing files)."""
    if not storage_url or storage_url.startswith("inline://"):
        return None
    try:
        if storage_url.startswith("s3://"):
            from app.services import storage as storage_svc

            client, settings = storage_svc._client()
            key = storage_url.split("/", 3)[3]
            obj = client.get_object(Bucket=settings.S3_BUCKET, Key=key)
            return obj["Body"].read()
        from pathlib import Path

        path = Path(storage_url)
        return path.read_bytes() if path.is_file() else None
    except Exception:
        logger.warning("Media byte load failed for %s", storage_url, exc_info=True)
        return None


@activity.defn
async def scan_media_activity(asset: dict) -> dict:
    """Magic-byte + size validation persisted to the asset row."""
    asset_id = asset.get("asset_id")
    if not asset_id:
        raise ApplicationError("Scan requires an asset_id", non_retryable=True)
    async with worker_session() as session:
        row = await session.get(MediaAsset, asset_id)
        if row is None:
            raise ApplicationError("Media asset not found", non_retryable=True)
        blob = _load_bytes(row.storage_url or "")
        if blob is None:
            verdict, note = "pending", "bytes unreadable; awaiting verification"
        elif not blob:
            verdict, note = "flagged", "empty file"
        elif _sniff(row.kind or "", blob[:12]) is None:
            verdict, note = "flagged", f"content does not match declared kind '{row.kind}'"
        else:
            verdict, note = "clean", f"{_sniff(row.kind or '', blob[:12])} · {len(blob)} bytes verified"
        row.moderation_status = verdict
        await session.commit()
    logger.info("Media scan %s: %s (%s)", asset_id, verdict, note)
    return {"asset_id": asset_id, "moderation_status": verdict, "note": note}


@activity.defn
async def normalize_media_activity(asset: dict) -> dict:
    """Server-side EXIF strip + ≤1600px re-encode + thumbnail for local
    photos. Non-images and object-storage originals are noted, not faked."""
    asset_id = asset.get("asset_id")
    if not asset_id:
        raise ApplicationError("Normalize requires an asset_id", non_retryable=True)
    async with worker_session() as session:
        row = await session.get(MediaAsset, asset_id)
        if row is None:
            raise ApplicationError("Media asset not found", non_retryable=True)
        result = {"asset_id": asset_id, "exif_stripped": False, "thumbnail_url": row.thumbnail_url}
        if (row.kind or "") != "photo" or not (row.storage_url or "") or row.storage_url.startswith(("s3://", "inline://")):
            result["note"] = "server normalize applies to locally stored photos only"
            await session.commit()
            return result
        try:
            from pathlib import Path

            from PIL import Image

            path = Path(row.storage_url)
            if not path.is_file():
                result["note"] = "original file missing; nothing to normalize"
                await session.commit()
                return result
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)
                # Re-save WITHOUT exif= → GPS and all EXIF tags are dropped.
                image.save(path, format="JPEG", quality=82)
                thumb = path.with_name(f"{path.stem}_thumb{path.suffix or '.jpg'}")
                preview = image.copy()
                preview.thumbnail((THUMB_EDGE, THUMB_EDGE), Image.LANCZOS)
                preview.save(thumb, format="JPEG", quality=75)
            row.thumbnail_url = str(thumb)
            result.update({"exif_stripped": True, "thumbnail_url": str(thumb), "note": "EXIF stripped, ≤1600px JPEG, thumbnail generated"})
        except Exception:
            logger.warning("Media normalize failed for %s", asset_id, exc_info=True)
            result["note"] = "normalize failed; original kept as-is"
        await session.commit()
    return result


@activity.defn
async def transcribe_audio_activity(asset: dict) -> dict:
    """Local-ASR hook. Returns an honest NULL transcript until a model is
    bundled — the extraction agent falls back to typed text without waiting.
    A produced transcript is persisted to the asset row when present."""
    from app.config import get_settings

    asset_id = asset.get("asset_id")
    if not asset_id:
        raise ApplicationError("Transcribe requires an asset_id", non_retryable=True)
    if not get_settings().ASR_ENABLED:
        return {"asset_id": asset_id, "transcript": None, "note": "ASR disabled (open decision §10); text-only triage"}
    logger.warning("ASR selected but no model is bundled; falling back to text-only triage")
    return {"asset_id": asset_id, "transcript": None, "note": "ASR model unavailable at runtime"}
