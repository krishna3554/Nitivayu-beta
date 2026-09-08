"""MediaProcessingWorkflow (§5.4): decouple "citizen gets a tracking token"
(fast, <1s) from "media is fully processed" (seconds, retryable).

Triggered after intake stores media_assets rows (or by an object-storage
event in the direct-upload future). Completes with per-asset statuses;
triage proceeds on text alone if media is slow — never blocked.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities.media import (
        normalize_media_activity,
        scan_media_activity,
        transcribe_audio_activity,
    )


@workflow.defn
class MediaProcessingWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        assets: list = payload.get("assets", [])
        results = []
        for asset in assets:
            scanned = await workflow.execute_activity(
                scan_media_activity,
                asset,
                start_to_close_timeout=timedelta(minutes=2),
            )
            normalized = await workflow.execute_activity(
                normalize_media_activity,
                asset,
                start_to_close_timeout=timedelta(minutes=2),
            )
            transcript = {"transcript": None}
            if asset.get("kind") == "audio":
                transcript = await workflow.execute_activity(
                    transcribe_audio_activity,
                    asset,
                    start_to_close_timeout=timedelta(minutes=5),
                )
            results.append(
                {
                    "asset_id": asset.get("asset_id"),
                    "moderation": scanned,
                    "normalized": normalized,
                    "transcript": transcript.get("transcript"),
                }
            )
        return {"processed": len(results), "assets": results, "status": "COMPLETED"}
