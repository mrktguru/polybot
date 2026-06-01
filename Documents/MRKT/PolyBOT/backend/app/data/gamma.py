"""Polymarket Gamma API client + MM candidate normalization.

Fetches active markets and maps them into the dict shape expected by
MarketSelector. Network/parse errors propagate to the caller, which is
responsible for graceful degradation.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.gamma_host, timeout=15.0)


def fetch_active_markets(limit: int = 200) -> list[dict[str, Any]]:
    """Fetch active, non-closed markets from Gamma."""
    with _client() as client:
        resp = client.get(
            "/markets",
            params={"active": "true", "closed": "false", "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, list) else data.get("data", [])


def _to_candidate(m: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a Gamma market into the selector candidate shape."""
    try:
        best_bid = float(m.get("bestBid", 0) or 0)
        best_ask = float(m.get("bestAsk", 0) or 0)
        if best_bid <= 0 or best_ask <= 0:
            return None
        mid = (best_bid + best_ask) / 2
        return {
            "market_id": str(m.get("conditionId") or m.get("id")),
            "title": m.get("question", ""),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid": mid,
            "volume_24h": float(m.get("volume24hr", 0) or 0),
            "t_hours": float(m.get("hoursToResolution", 0) or 0),
            "sigma": float(m.get("sigma", 0.03) or 0.03),
            "max_jump_1h": float(m.get("maxJump1h", 0) or 0),
            "orderbook_depth": int(m.get("orderbookDepth", 99) or 99),
            "category": m.get("category", "uncat"),
            "maker_reward_score": float(m.get("makerRewardScore", 0) or 0),
            "inventory": 0.0,
            "price_history": [mid],
            "book_age_sec": 0.0,
        }
    except (TypeError, ValueError) as exc:
        log.debug("candidate_parse_skip", error=str(exc))
        return None


def fetch_mm_candidates(limit: int = 200) -> list[dict[str, Any]]:
    raw = fetch_active_markets(limit=limit)
    candidates = [c for c in (_to_candidate(m) for m in raw) if c is not None]
    log.info("mm_candidates_fetched", raw=len(raw), usable=len(candidates))
    return candidates
