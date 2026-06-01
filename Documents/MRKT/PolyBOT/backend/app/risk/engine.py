"""Centralized Risk Engine (plan A.3 / C.7).

Performs pre-trade checks (per-market, per-strategy, portfolio, correlation
caps) and post-trade checks (daily loss, drawdown -> circuit breakers).
Circuit-breaker state lives in Redis so all workers see it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.strategies.base import Signal

log = get_logger(__name__)

KEY_PAUSED = "polybot.paused"
KEY_PAUSE_REASON = "polybot.pause_reason"


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""
    adjusted_size: float | None = None


class RiskEngine:
    def __init__(
        self,
        max_per_market: float | None = None,
        max_per_correlation_tag: float | None = None,
    ) -> None:
        self.max_per_market = max_per_market or settings.total_capital * 0.05
        self.max_per_correlation_tag = (
            max_per_correlation_tag or settings.total_capital * 0.15
        )

    # ── global pause / circuit breaker ─────────────────────
    @staticmethod
    def is_paused() -> bool:
        return get_redis().get(KEY_PAUSED) == "1"

    @staticmethod
    def pause(reason: str) -> None:
        r = get_redis()
        r.set(KEY_PAUSED, "1")
        r.set(KEY_PAUSE_REASON, reason)
        log.warning("trading_paused", reason=reason)

    @staticmethod
    def resume() -> None:
        r = get_redis()
        r.delete(KEY_PAUSED)
        r.delete(KEY_PAUSE_REASON)
        log.info("trading_resumed")

    # ── pre-trade ──────────────────────────────────────────
    def check_pre_trade(
        self,
        signal: Signal,
        market_exposure: float,
        tag_exposure: dict[str, float],
    ) -> RiskDecision:
        if self.is_paused():
            return RiskDecision(False, "trading paused (circuit breaker)")

        size = signal.kelly_size
        if size <= 0:
            return RiskDecision(False, "non-positive size")

        # Per-market cap
        if market_exposure + size > self.max_per_market:
            size = max(0.0, self.max_per_market - market_exposure)
            if size <= 0:
                return RiskDecision(False, "per-market cap reached")

        # Per-correlation-tag cap
        for tag in signal.correlation_tags or [signal.strategy]:
            current = tag_exposure.get(tag, 0.0)
            if current + size > self.max_per_correlation_tag:
                size = max(0.0, self.max_per_correlation_tag - current)
                if size <= 0:
                    return RiskDecision(False, f"correlation cap reached for tag={tag}")

        adjusted = size if size != signal.kelly_size else None
        return RiskDecision(True, adjusted_size=adjusted)

    # ── post-trade / circuit breakers ──────────────────────
    def check_circuit_breakers(self, daily_pnl: float, drawdown_pct: float) -> None:
        if daily_pnl < -settings.daily_loss_limit:
            self.pause(f"daily_loss_limit hit: pnl={daily_pnl:.2f}")
        if drawdown_pct > settings.max_drawdown_pct:
            self.pause(f"max_drawdown hit: dd={drawdown_pct:.1%}")
