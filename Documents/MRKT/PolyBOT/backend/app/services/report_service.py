"""Daily report builder."""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.risk_service import get_daily_pnl, get_drawdown_pct


def build_daily_report() -> dict:
    return {
        "date": datetime.now(UTC).date().isoformat(),
        "daily_pnl": get_daily_pnl(),
        "drawdown_pct": get_drawdown_pct(),
    }
