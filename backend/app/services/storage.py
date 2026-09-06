"""Evidence + export storage: S3-compatible object storage with a local fallback.

- S3_ENABLED=true  -> MinIO/S3 bucket, presigned PUT for direct browser
  uploads (heavy bytes bypass the API), presigned GET for downloads.
- S3_ENABLED=false -> local MEDIA_DIR mirror (mounted output_data volume).

The bucket is auto-created on first use so MinIO needs no extra bootstrap
container. Nothing here raises when storage is unconfigured; callers check
`enabled()`.
"""

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def enabled() -> bool:
    from app.config import get_settings

    return bool(get_settings().S3_ENABLED)


def _client():
    from app.config import get_settings

    settings = get_settings()
    import boto3

    kwargs = {
        "service_name": "s3",
        "region_name": settings.S3_REGION,
        "aws_access_key_id": settings.S3_ACCESS_KEY,
        "aws_secret_access_key": settings.S3_SECRET_KEY,
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client(**kwargs), settings


def ensure_bucket() -> str:
    client, settings = _client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:
        try:
            params = {"Bucket": settings.S3_BUCKET}
            if settings.S3_REGION != "us-east-1" and not settings.S3_ENDPOINT_URL:
                params["CreateBucketConfiguration"] = {"LocationConstraint": settings.S3_REGION}
            client.create_bucket(**params)
            logger.info("Created object-storage bucket %s", settings.S3_BUCKET)
        except Exception:
            logger.warning("Bucket ensure failed for %s", settings.S3_BUCKET, exc_info=True)
    return settings.S3_BUCKET


def object_key(prefix: str, filename: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "._-") else "_" for c in (filename or "upload"))[-120:]
    return f"{prefix.strip('/')}/{uuid.uuid4().hex[:12]}-{safe}"


def presigned_put(key: str, content_type: str = "application/octet-stream") -> str:
    client, settings = _client()
    ensure_bucket()
    return client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=settings.S3_PRESIGN_TTL_SECONDS,
    )


def presigned_get(key: str) -> str:
    client, settings = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=settings.S3_PRESIGN_TTL_SECONDS,
    )


def public_url(key: str) -> str:
    """Canonical reference stored in Postgres (s3://…); resolved at read time."""
    from app.config import get_settings

    return f"s3://{get_settings().S3_BUCKET}/{key}"


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Server-side upload path (compat + small files). Returns the stored URL."""
    if enabled():
        client, settings = _client()
        ensure_bucket()
        client.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=content_type)
        return public_url(key)
    from app.config import get_settings

    directory = Path(get_settings().MEDIA_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / key.replace("/", "_")
    path.write_bytes(data)
    return str(path)


async def ping() -> bool:
    if not enabled():
        return False
    try:
        import asyncio

        return await asyncio.to_thread(lambda: ensure_bucket() is not None)
    except Exception:
        return False
