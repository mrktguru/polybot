"""Cross-Market Correlation service."""

from __future__ import annotations

import json

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.data.gamma import fetch_active_markets
from app.strategies.cross_market import CrossMarketCorrelation

log = get_logger(__name__)
_KEY_CORR_SIGNALS = "polybot.corr_signals"


def _build_strategy() -> CrossMarketCorrelation:
    return CrossMarketCorrelation(budget=settings.total_capital * 0.10)


def run_correlation_scan() -> dict:
    """Fetch markets, scan for correlations, queue signals."""
    strategy = _build_strategy()

    try:
        markets = fetch_active_markets(limit=100)
    except Exception as exc:
        log.warning("gamma_fetch_failed_corr", error=str(exc))
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
                    "sigma": float(m.get("sigma", 0.03) or 0.03),
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
            "edge": signal.edge,
            "kelly_size": signal.kelly_size,
            "reasoning": signal.reasoning,
        })
        # Queue for UI (semi-auto) or auto-execute
        from app.strategies.manager import StrategyManager
        manager = StrategyManager(total_capital=settings.total_capital)
        manager.process_signal(signal)

    r = get_redis()
    r.set(_KEY_CORR_SIGNALS, json.dumps(signals_data), ex=7200)

    return {
        "signals": signals_data,
        "markets_scanned": result.markets_scanned,
        "execution_time_ms": result.execution_time_ms,
    }
