"""Whale Copying service."""

from __future__ import annotations

import json
import time

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.strategies.manager import StrategyManager
from app.strategies.whale_copying import WhaleCopying

log = get_logger(__name__)
_KEY_WHALE_ALERTS = "polybot.whale_alerts"
_KEY_LAST_CHECK = "polybot.whale_last_check"

POLYMARKET_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/..."


def _build_strategy() -> WhaleCopying:
    return WhaleCopying(budget=settings.total_capital * 0.05)


def _fetch_recent_trades() -> list[dict]:
    """Fetch recent trades from Polymarket subgraph."""
    last_check = int(time.time()) - 3600  # Last hour
    query = f"""
    {{
      positionTrades(
        first: 100,
        orderBy: timestamp,
        orderDirection: desc,
        where: {{ timestamp_gte: {last_check} }}
      ) {{
        trader {{ id }}
        market {{ id question }}
        side
        amount
        price
        timestamp
      }}
    }}
    """

    try:
        resp = httpx.post(
            POLYMARKET_SUBGRAPH,
            json={"query": query},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        trades = data.get("data", {}).get("positionTrades", [])
        return [
            {
                "trader": t.get("trader", {}).get("id", ""),
                "market_id": t.get("market", {}).get("id", ""),
                "market_title": t.get("market", {}).get("question", ""),
                "side": t.get("side", "buy_yes"),
                "amount": float(t.get("amount", 0)),
                "price": float(t.get("price", 0.5)),
                "timestamp": int(t.get("timestamp", 0)),
            }
            for t in trades
        ]
    except Exception as exc:
        log.warning("whale_subgraph_fetch_failed", error=str(exc))
        return []


def monitor_whales() -> dict:
    """Monitor recent trades for whale activity."""
    strategy = _build_strategy()

    trades = _fetch_recent_trades()
    if not trades:
        return {"signals": [], "error": "no trades fetched"}

    # Load wallet history from Redis
    r = get_redis()
    wallet_history_raw = r.get("polybot.wallet_history")
    if wallet_history_raw:
        strategy._wallet_history = json.loads(wallet_history_raw)

    result = strategy.scan([], recent_trades=trades)
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

    # Save updated wallet history
    r.set("polybot.wallet_history", json.dumps(strategy._wallet_history), ex=86400)
    r.set(_KEY_WHALE_ALERTS, json.dumps(signals_data), ex=7200)

    return {
        "signals": signals_data,
        "markets_scanned": len(trades),
        "execution_time_ms": result.execution_time_ms,
    }
