"""Realtime channel: Server-Sent Events over the shared event bus (§5.7).

Clients poll today; they migrate by opening:
  GET /api/v1/events/stream?token=<jwt>&track=<token1,token2>

EventSource cannot set headers, so the JWT travels as a query param over
TLS. Channels are scope-derived (role/org/track) — see services/events.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps as deps_mod
from app.api.deps import get_db
from app.services import events as event_bus

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def stream(
    token: str = Query(default=""),
    track: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    _ = db  # session kept for future per-connection authorization checks
    user = None
    if token:
        try:
            user = await deps_mod.get_current_user(token)
        except Exception:
            user = None
    channels = event_bus.channels_for(user, track)

    async def body():
        async for item in event_bus.subscribe(channels):
            if "retry" in item:
                yield f"retry: {item['retry']}\n\n"
            elif "comment" in item:
                yield f": {item['comment']}\n\n"
            else:
                yield f"event: {item['event']}\ndata: {item['data']}\n\n"

    return StreamingResponse(body(), media_type="text/event-stream")
