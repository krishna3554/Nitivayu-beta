"""Server-Sent Events bus for live inbox/SLA/batch updates (§5.7).

Channels are scoped (`org:<uuid>`, `role:officer`, `track:<token>`) so no
workspace can snoop another's stream. Delivery is in-process asyncio queues;
when Redis is configured, publishes also fan out on Redis pub/sub so any API
replica holding a client's SSE connection can deliver events published by
another replica.

Frontend polling keeps working — this is additive. Clients migrate by
swapping their 30s pollers for `new EventSource('/api/v1/events/stream?...')`.
"""

import asyncio
import json
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

_local_subscribers: dict[str, set] = defaultdict(set)
_REDIS_CHANNEL = "nitivayu:sse"
_redis_listener_started = False


def channels_for(user: dict | None, track: str = "") -> list[str]:
    channels = ["public"]
    if user:
        role = (user.get("role") or "").lower()
        if role:
            channels.append(f"role:{role}")
        org = user.get("organization_id")
        if org:
            channels.append(f"org:{org}")
    for token in (track or "").split(","):
        token = token.strip()
        if token:
            channels.append(f"track:{token}")
    return channels


async def _ensure_redis_listener() -> None:
    """Single background fan-in: Redis -> local subscriber queues."""
    global _redis_listener_started
    if _redis_listener_started:
        return
    _redis_listener_started = True
    from app.services import redis_client as redis_mod

    client = redis_mod.get_redis()
    if client is None:
        return
    try:
        pubsub = client.pubsub()
        await pubsub.subscribe(_REDIS_CHANNEL)

        async def pump():
            try:
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        payload = json.loads(message["data"])
                    except Exception:
                        continue
                    channel = payload.get("channel")
                    for queue in list(_local_subscribers.get(channel, ())):
                        try:
                            queue.put_nowait(payload.get("event", {}))
                        except asyncio.QueueFull:
                            pass
            except Exception:
                logger.warning("SSE redis fan-in stopped", exc_info=True)

        asyncio.get_running_loop().create_task(pump())
    except Exception:
        logger.warning("SSE redis fan-in failed; local-only delivery", exc_info=True)


async def publish_event(channel: str, event: dict) -> None:
    """Publish to local subscribers now + Redis fan-out for other replicas."""
    await _ensure_redis_listener()
    for queue in list(_local_subscribers.get(channel, ())):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
    from app.services import redis_client as redis_mod

    client = redis_mod.get_redis()
    if client is not None:
        try:
            await client.publish(_REDIS_CHANNEL, json.dumps({"channel": channel, "event": event}, default=str))
        except Exception:
            pass


async def subscribe(channels: list[str], heartbeat_seconds: int = 25):
    """Async generator yielding SSE-ready dicts for the given channels."""
    await _ensure_redis_listener()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    for channel in channels:
        _local_subscribers[channel].add(queue)
    try:
        # Retry directive first so clients back off sanely on disconnects.
        yield {"retry": 15000}
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except asyncio.TimeoutError:
                yield {"comment": "ping"}
                continue
            yield {"event": event.get("type", "message"), "data": json.dumps(event.get("data", {}), default=str)}
    finally:
        for channel in channels:
            _local_subscribers[channel].discard(queue)
