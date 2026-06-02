"""Sentiment Divergence service."""

from __future__ import annotations

import json

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.data.gamma import fetch_active_markets
from app.strategies.manager import StrategyManager
from app.strategies.sentiment_divergence import SentimentDivergence

log = get_logger(__name__)
_KEY_SENTIMENT_SIGNALS = "polybot.sentiment_signals"

SOURCES = {
    "metaculus": "https://www.metaculus.com/api2/questions/?limit=50",
    "predictit": "https://www.predictit.org/api/marketdata/all/",
    "manifold": "https://manifold.markets/api/v0/markets?limit=50",
}


def _build_strategy() -> SentimentDivergence:
    return SentimentDivergence(budget=settings.total_capital * 0.05)


def _fetch_external(source: str) -> list[dict]:
    """Fetch data from an external prediction market."""
    url = SOURCES.get(source)
    if not url:
        return []

    try:
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if source == "metaculus":
            return [
                {
                    "id": str(q.get("id")),
                    "title": q.get("title", ""),
                    "prob": q.get("community_prediction", 0.5),
                }
                for q in (data if isinstance(data, list) else data.get("results", []))
            ]
        elif source == "predictit":
            return [
                {
                    "id": str(m.get("id")),
                    "title": m.get("name", ""),
                    "prob": m.get("lastTradePrice", 0.5) / 100
                    if m.get("lastTradePrice")
                    else 0.5,
                }
                for m in (data if isinstance(data, list) else data.get("markets", []))
            ]
        elif source == "manifold":
            return [
                {
                    "id": str(m.get("id")),
                    "title": m.get("question", ""),
                    "prob": m.get("probability", 0.5),
                }
                for m in (data if isinstance(data, list) else [])
            ]
    except Exception as exc:
        log.warning("external_fetch_failed", source=source, error=str(exc))
    return []


def run_sentiment_scan() -> dict:
    """Fetch external data, scan for divergences."""
    strategy = _build_strategy()

    external_data = {}
    for source in SOURCES:
        markets = _fetch_external(source)
        if markets:
            external_data[source] = markets

    try:
        markets = fetch_active_markets(limit=50)
    except Exception as exc:
        log.warning("gamma_fetch_failed_sentiment", error=str(exc))
        return {"signals": [], "error": str(exc)}

    candidates = []
    for m in markets:
        try:
            bid = float(m.get("bestBid", 0) or 0)
            ask = float(m.get("bestAsk", 0) or 0)
            if bid > 0 and ask > 0:
                candidates.append({
                    "market_id": str(m.get("conditionId") or m.get("id")),
                    "title": m.get("question", ""),
                    "best_bid": bid,
                    "best_ask": ask,
                    "mid": (bid + ask) / 2,
                    "volume_24h": float(m.get("volume24hr", 0) or 0),
                    "t_hours": float(m.get("hoursToResolution", 0) or 0),
                })
        except (TypeError, ValueError):
            continue

    result = strategy.scan(candidates, external_data=external_data)
    signals_data = []

    for signal in result.signals:
        signals_data.append({
            "signal_id": signal.signal_id,
            "strategy": signal.strategy,
            "market_id": signal.market_id,
            "market_title": signal.market_title,
            "direction": signal.direction.value,
            "confidence": signal.confidence,
            "reasoning": signal.reasoning,
            "metadata": signal.metadata,
        })
        manager = StrategyManager(total_capital=settings.total_capital)
        manager.process_signal(signal)

    r = get_redis()
    r.set(_KEY_SENTIMENT_SIGNALS, json.dumps(signals_data), ex=14400)

    return {
        "signals": signals_data,
        "markets_scanned": result.markets_scanned,
        "execution_time_ms": result.execution_time_ms,
    }
