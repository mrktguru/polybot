"""Market Making service — orchestration glue for the MM Celery tasks.

Reads candidate markets from the data layer, scores/selects them, persists
the active set to Redis, and drives quote updates through the MM strategy
and OrderRouter. Designed to degrade gracefully when external data is
unavailable (returns 0 instead of crashing the worker).
"""

from __future__ import annotations

import json

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import KEY_ACTIVE_MM_MARKETS, get_redis
from app.data.gamma import fetch_mm_candidates
from app.execution.types import OrderRequest, OrderSide, OrderType
from app.risk.allocator import CapitalAllocator
from app.strategies.market_making import MarketMaking

log = get_logger(__name__)


def _build_strategy() -> MarketMaking:
    budgets = CapitalAllocator(total_capital=settings.total_capital).allocate()
    return MarketMaking(budget=budgets.get("market_making", settings.total_capital * 0.6))


def refresh_market_selection() -> int:
    """Hourly: fetch + filter + score markets, store active set in Redis."""
    strategy = _build_strategy()
    try:
        candidates = fetch_mm_candidates()
    except Exception as exc:
        log.warning("gamma_fetch_failed", error=str(exc))
        return 0

    selected = strategy.selector.select(candidates)
    r = get_redis()
    r.set(KEY_ACTIVE_MM_MARKETS, json.dumps(selected))
    return len(selected)


def update_quotes() -> int:
    """Every 60s: recompute quotes for active markets and route orders."""
    r = get_redis()
    raw = r.get(KEY_ACTIVE_MM_MARKETS)
    if not raw:
        return 0

    strategy = _build_strategy()
    router = strategy_router()
    markets = json.loads(raw)
    updated = 0

    for m in markets:
        quote = strategy.compute_market_quotes(
            mid=m["mid"],
            inventory=m.get("inventory", 0.0),
            price_history=m.get("price_history", [m["mid"]]),
            t_hours=m["t_hours"],
            orderbook_depth=m.get("orderbook_depth", 99),
            book_age_sec=m.get("book_age_sec", 0.0),
        )
        if quote.action == "cancel_all":
            continue

        # Post bid and ask via the router (paper mode in MVP).
        router.submit(
            OrderRequest(
                market_id=m["market_id"],
                side=OrderSide.BUY,
                size=strategy.cfg.max_position_usd,
                order_type=OrderType.LIMIT,
                price=quote.bid,
            ),
            idempotency_key=f"mm-bid-{m['market_id']}-{quote.bid}",
        )
        router.submit(
            OrderRequest(
                market_id=m["market_id"],
                side=OrderSide.SELL,
                size=strategy.cfg.max_position_usd,
                order_type=OrderType.LIMIT,
                price=quote.ask,
            ),
            idempotency_key=f"mm-ask-{m['market_id']}-{quote.ask}",
        )
        updated += 1

    return updated


def snapshot_prices() -> int:
    """Every 30m: persist mid-price snapshots for sigma computation."""
    r = get_redis()
    raw = r.get(KEY_ACTIVE_MM_MARKETS)
    if not raw:
        return 0
    markets = json.loads(raw)
    # In a full build this writes to the price_snapshots hypertable.
    return len(markets)


_router_singleton = None


def strategy_router():
    global _router_singleton
    if _router_singleton is None:
        from app.execution.router import OrderRouter

        _router_singleton = OrderRouter()
    return _router_singleton
