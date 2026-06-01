"""Celery application and beat schedule (from spec)."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "polybot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.jobs"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_max_tasks_per_child=200,
)

celery_app.conf.beat_schedule = {
    # Market Making
    "mm-quote-update": {"task": "tasks.mm_quote_update", "schedule": 60.0},
    "mm-market-refresh": {"task": "tasks.mm_market_refresh", "schedule": 3600.0},
    "mm-price-snapshot": {"task": "tasks.price_snapshot", "schedule": 1800.0},
    # Cross-Market Correlation
    "corr-scan": {"task": "tasks.correlation_scan", "schedule": 3600.0},
    # Resolution Arbitrage
    "res-arb-poll": {"task": "tasks.resolution_arb_poll", "schedule": 60.0},
    # Volatility Harvesting
    "vh-spike-detect": {"task": "tasks.vh_spike_detect", "schedule": 30.0},
    "vh-position-monitor": {"task": "tasks.vh_position_monitor", "schedule": 60.0},
    # Whale Copying
    "whale-monitor": {"task": "tasks.whale_monitor", "schedule": 30.0},
    # Sentiment Divergence
    "sentiment-scan": {"task": "tasks.sentiment_scan", "schedule": 900.0},
    # General
    "circuit-breakers": {"task": "tasks.check_circuit_breakers", "schedule": 60.0},
    "daily-report": {"task": "tasks.daily_report", "schedule": crontab(hour=0, minute=0)},
}
