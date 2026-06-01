"""Redis client and pub/sub helpers."""

from __future__ import annotations

import json
from typing import Any

import redis

from app.core.config import settings

_pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


# ── Channels ────────────────────────────────────────────────
CHANNEL_EVENTS = "polybot.events"  # generic WS broadcast channel

# ── Keys ────────────────────────────────────────────────────
KEY_ACTIVE_MM_MARKETS = "active_mm_markets"


def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    """Publish an event for WebSocket fan-out."""
    r = get_redis()
    r.publish(CHANNEL_EVENTS, json.dumps({"type": event_type, "payload": payload}))
