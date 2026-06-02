"""Celery task implementations — all 6 strategies fully wired."""

from __future__ import annotations

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

log = get_logger(__name__)


# ── Market Making ───────────────────────────────────────────
@celery_app.task(name="tasks.mm_market_refresh")
def mm_market_refresh() -> dict:
    """Refresh MM market selection hourly (Gamma -> filter -> score -> Redis)."""
    from app.services.mm_service import refresh_market_selection

    count = refresh_market_selection()
    log.info("mm_market_refresh_done", selected=count)
    return {"selected": count}


@celery_app.task(name="tasks.mm_quote_update")
def mm_quote_update() -> dict:
    """Recompute and (re)post quotes for active MM markets every 60s."""
    from app.services.mm_service import update_quotes

    updated = update_quotes()
    return {"updated": updated}


@celery_app.task(name="tasks.price_snapshot")
def price_snapshot() -> dict:
    from app.services.mm_service import snapshot_prices

    n = snapshot_prices()
    return {"snapshots": n}


# ── Cross-Market Correlation ───────────────────────────────
@celery_app.task(name="tasks.correlation_scan")
def correlation_scan() -> dict:
    """Scan all markets for cross-market correlation violations."""
    from app.services.cross_market_service import run_correlation_scan

    result = run_correlation_scan()
    log.info("correlation_scan_done", signals=len(result.get("signals", [])))
    return result


# ── Resolution Arbitrage ───────────────────────────────────
@celery_app.task(name="tasks.resolution_arb_poll")
def resolution_arb_poll() -> dict:
    """Poll all data feeds and check for resolution arbitrage opportunities."""
    from app.services.resolution_arb_service import poll_all_feeds

    result = poll_all_feeds()
    log.info("resolution_arb_poll_done", signals=result.get("signals_found", 0))
    return result


# ── Volatility Harvesting ──────────────────────────────────
@celery_app.task(name="tasks.vh_spike_detect")
def vh_spike_detect() -> dict:
    """Detect price spikes for volatility harvesting opportunities."""
    from app.services.vh_service import detect_spikes

    result = detect_spikes()
    log.info("vh_spike_detect_done", signals=len(result.get("signals", [])))
    return result


@celery_app.task(name="tasks.vh_position_monitor")
def vh_position_monitor() -> dict:
    """Monitor open VH positions for take-profit and stop-loss."""
    from app.services.vh_service import monitor_positions

    actions = monitor_positions()
    log.info("vh_position_monitor_done", actions=len(actions))
    return {"actions": actions}


# ── Whale Copying ──────────────────────────────────────────
@celery_app.task(name="tasks.whale_monitor")
def whale_monitor() -> dict:
    """Monitor on-chain transactions for whale activity."""
    from app.services.whale_service import monitor_whales

    result = monitor_whales()
    log.info("whale_monitor_done", alerts=len(result.get("signals", [])))
    return result


# ── Sentiment Divergence ───────────────────────────────────
@celery_app.task(name="tasks.sentiment_scan")
def sentiment_scan() -> dict:
    """Scan external sources for sentiment divergences vs Polymarket."""
    from app.services.sentiment_service import run_sentiment_scan

    result = run_sentiment_scan()
    log.info("sentiment_scan_done", signals=len(result.get("signals", [])))
    return result


# ── General ─────────────────────────────────────────────────
@celery_app.task(name="tasks.check_circuit_breakers")
def check_circuit_breakers() -> dict:
    from app.services.risk_service import evaluate_circuit_breakers

    paused = evaluate_circuit_breakers()
    return {"paused": paused}


@celery_app.task(name="tasks.daily_report")
def daily_report() -> dict:
    from app.services.report_service import build_daily_report

    return build_daily_report()
