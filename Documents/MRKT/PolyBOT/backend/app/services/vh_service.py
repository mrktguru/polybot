"""Volatility Harvesting service."""

from __future__ import annotations

import json

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.data.gamma import fetch_active_markets
from app.strategies.manager import StrategyManager
from app.strategies.volatility_harvest import VolatilityHarvesting

log = get_logger(__name__)
_KEY_VH_POSITIONS = "polybot.vh_positions"


def _build_strategy() -> VolatilityHarvesting:
    return VolatilityHarvesting(budget=settings.total_capital * 0.10)


def detect_spikes() -> dict:
    """Scan active markets for volatility spikes."""
    strategy = _build_strategy()

    try:
        markets = fetch_active_markets(limit=100)
    except Exception as exc:
        log.warning("gamma_fetch_failed_vh", error=str(exc))
        return {"signals": [], "error": str(exc)}

    candidates = []
    for m in markets:
        try:
            bid = float(m.get("bestBid", 0) or 0)
            ask = float(m.get("bestAsk", 0) or 0)
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2
                # Simulate price history (in production, use real snapshots)
                candidates.append({
                    "market_id": str(m.get("conditionId") or m.get("id")),
                    "title": m.get("question", ""),
                    "best_bid": bid,
                    "best_ask": ask,
                    "mid": mid,
                    "volume_24h": float(m.get("volume24hr", 0) or 0),
                    "t_hours": float(m.get("hoursToResolution", 0) or 0),
                    "price_history": [mid * 0.9, mid * 0.95, mid * 0.92, mid * 0.97, mid],
                })
        except (TypeError, ValueError):
            continue

    result = strategy.scan(candidates)
    signals_data = []

    for signal in result.signals:
        signals_data.append({
            "signal_id": signal.signal_id,
            "strategy": signal.strategy,
            "market_id": signal.market_id,
            "direction": signal.direction.value,
            "confidence": signal.confidence,
            "reasoning": signal.reasoning,
        })
        manager = StrategyManager(total_capital=settings.total_capital)
        manager.process_signal(signal)

    return {
        "signals": signals_data,
        "markets_scanned": result.markets_scanned,
        "execution_time_ms": result.execution_time_ms,
    }


def monitor_positions() -> list[dict]:
    """Check open VH positions for TP/SL."""
    strategy = _build_strategy()
    r = get_redis()

    raw = r.get(_KEY_VH_POSITIONS)
    if not raw:
        return []

    positions = json.loads(raw)
    actions = strategy.monitor_open_positions(positions)

    # Remove closed positions
    closed_ids = {a["position_id"] for a in actions if a["action"] == "close"}
    positions = [p for p in positions if p["id"] not in closed_ids]
    r.set(_KEY_VH_POSITIONS, json.dumps(positions))

    return actions
