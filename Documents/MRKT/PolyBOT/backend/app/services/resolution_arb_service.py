"""Resolution Arbitrage service."""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.data.gamma import fetch_active_markets
from app.strategies.resolution_arb import ResolutionArbitrage
from app.strategies.resolution_arb.feeds import ALL_FEEDS

log = get_logger(__name__)


def _build_strategy() -> ResolutionArbitrage:
    strat = ResolutionArbitrage(budget=settings.total_capital * 0.05)
    # Register market-feed mappings (would be populated from DB in production)
    return strat


def _poll_feed(feed_name: str) -> dict | None:
    """Poll a single data feed and return parsed data."""
    import httpx

    for feed in ALL_FEEDS:
        if feed.name == feed_name:
            try:
                if "http" in feed.url and "ws" not in feed.url:
                    resp = httpx.get(feed.url, timeout=10)
                    return {"outcome": None, "data": resp.text[:500]}
                else:
                    return {"outcome": None, "data": f"WebSocket feed: {feed.url}"}
            except Exception as exc:
                log.warning("feed_poll_failed", feed=feed_name, error=str(exc))
                return None
    return None


def poll_all_feeds() -> dict:
    """Poll all feeds and check for arb opportunities."""
    strategy = _build_strategy()

    try:
        markets = fetch_active_markets(limit=50)
    except Exception as exc:
        log.warning("gamma_fetch_failed_arb", error=str(exc))
        return {"signals_found": 0, "error": str(exc)}

    # Update strategy with market data
    for m in markets:
        try:
            market_id = str(m.get("conditionId") or m.get("id"))
            title = m.get("question", "")

            # Simple keyword matching to map markets to feeds
            title_lower = title.lower()
            for feed in ALL_FEEDS:
                for keyword in feed.keywords:
                    if keyword.lower() in title_lower:
                        strategy.register_market_feed(market_id, feed.name)
                        break
        except (TypeError, ValueError):
            continue

    # Poll feeds
    signals_found = 0
    for feed in ALL_FEEDS:
        data = _poll_feed(feed.name)
        if data:
            strategy.update_feed_data(feed.name, data)

    # Run scan
    result = strategy.scan([
        {
            "market_id": str(m.get("conditionId") or m.get("id")),
            "mid": (float(m.get("bestBid", 0) or 0) + float(m.get("bestAsk", 0) or 0)) / 2,
            "title": m.get("question", ""),
        }
        for m in markets
        if m.get("bestBid") and m.get("bestAsk")
    ])

    for signal in result.signals:
        from app.strategies.manager import StrategyManager
        manager = StrategyManager(total_capital=settings.total_capital)
        manager.process_signal(signal)
        signals_found += 1

    return {
        "signals_found": signals_found,
        "markets_scanned": result.markets_scanned,
        "feeds_polled": len([f for f in ALL_FEEDS if strategy._feed_data.get(f.name)]),
    }
