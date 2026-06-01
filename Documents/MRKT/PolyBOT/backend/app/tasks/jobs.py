"""Celery task implementations.

Phase 1 implements the Market Making loop and circuit breakers concretely.
Strategies from later phases (C.2–C.6) are registered as stubs so the beat
schedule is valid and they can be filled in incrementally.
"""

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


# ── Later-phase stubs (C.2–C.6) ─────────────────────────────
@celery_app.task(name="tasks.correlation_scan")
def correlation_scan() -> dict:
    log.debug("correlation_scan_stub")
    return {"status": "not_implemented"}


@celery_app.task(name="tasks.resolution_arb_poll")
def resolution_arb_poll() -> dict:
    log.debug("resolution_arb_poll_stub")
    return {"status": "not_implemented"}


@celery_app.task(name="tasks.vh_spike_detect")
def vh_spike_detect() -> dict:
    log.debug("vh_spike_detect_stub")
    return {"status": "not_implemented"}


@celery_app.task(name="tasks.vh_position_monitor")
def vh_position_monitor() -> dict:
    log.debug("vh_position_monitor_stub")
    return {"status": "not_implemented"}


@celery_app.task(name="tasks.whale_monitor")
def whale_monitor() -> dict:
    log.debug("whale_monitor_stub")
    return {"status": "not_implemented"}


@celery_app.task(name="tasks.sentiment_scan")
def sentiment_scan() -> dict:
    log.debug("sentiment_scan_stub")
    return {"status": "not_implemented"}
