"""WebSocket endpoint that fans out Redis events to connected clients."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import CHANNEL_EVENTS

log = get_logger(__name__)
ws_router = APIRouter()


@ws_router.websocket("/ws")
async def events_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(CHANNEL_EVENTS)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                await websocket.send_text(message["data"])
            else:
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        log.info("ws_client_disconnected")
    finally:
        await pubsub.unsubscribe(CHANNEL_EVENTS)
        await pubsub.close()
        await client.close()
