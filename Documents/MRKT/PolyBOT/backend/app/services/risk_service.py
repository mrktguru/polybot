"""Risk service — evaluates circuit breakers from current PnL/drawdown."""

from __future__ import annotations

from app.core.logging import get_logger
from app.risk.engine import RiskEngine

log = get_logger(__name__)


def get_daily_pnl() -> float:
    """Aggregate realized + unrealized PnL for the current day.

    Placeholder: returns 0.0 until the positions/fills pipeline is wired to
    a real ledger. Kept side-effect free so the scheduler is safe.
    """
    return 0.0


def get_drawdown_pct() -> float:
    return 0.0


def evaluate_circuit_breakers() -> bool:
    engine = RiskEngine()
    engine.check_circuit_breakers(get_daily_pnl(), get_drawdown_pct())
    return engine.is_paused()
