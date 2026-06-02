"""StrategyManager — orchestrates strategies, capital, and execution.

Improved over the spec (plan A.3 / C.7):
- routes ALL execution through OrderRouter (no direct CLOB calls),
- uses the centralized RiskEngine for pre-trade checks and circuit breakers,
- uses the dynamic CapitalAllocator for budgets,
- persists semi-auto signals for the UI approve-flow.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.redis import publish_event
from app.execution.router import OrderRouter
from app.execution.types import OrderBook, OrderRequest, OrderSide, OrderType
from app.risk.allocator import CapitalAllocator
from app.risk.engine import RiskEngine
from app.strategies.base import Signal, SignalDirection
from app.strategies.cross_market import CrossMarketCorrelation
from app.strategies.market_making import MarketMaking
from app.strategies.resolution_arb import ResolutionArbitrage
from app.strategies.sentiment_divergence import SentimentDivergence
from app.strategies.volatility_harvest import VolatilityHarvesting
from app.strategies.whale_copying import WhaleCopying

log = get_logger(__name__)


class StrategyManager:
    def __init__(self, total_capital: float) -> None:
        self.capital = total_capital
        self.allocator = CapitalAllocator(total_capital=total_capital)
        self.budgets = self.allocator.allocate()
        self.risk = RiskEngine()
        self.router = OrderRouter()

        self.strategies = {
            "market_making": MarketMaking(self.budgets.get("market_making", 0.0)),
            "cross_market_corr": CrossMarketCorrelation(
                self.budgets.get("cross_market_corr", 0.0)
            ),
            "resolution_arb": ResolutionArbitrage(
                self.budgets.get("resolution_arb", 0.0)
            ),
            "volatility_harvesting": VolatilityHarvesting(
                self.budgets.get("volatility_harvesting", 0.0)
            ),
            "whale_copying": WhaleCopying(
                self.budgets.get("whale_copying", 0.0)
            ),
            "sentiment_divergence": SentimentDivergence(
                self.budgets.get("sentiment_divergence", 0.0)
            ),
        }

    # ── signal handling ────────────────────────────────────
    def process_signal(
        self,
        signal: Signal,
        market_exposure: float = 0.0,
        tag_exposure: dict[str, float] | None = None,
        book: OrderBook | None = None,
    ) -> None:
        strategy = self.strategies.get(signal.strategy)
        if strategy is None:
            log.warning("unknown_strategy", strategy=signal.strategy)
            return

        errors = strategy.validate(signal)
        if errors:
            log.warning("signal_invalid", strategy=signal.strategy, errors=errors)
            return

        if strategy.should_auto_execute(signal):
            self._execute(signal, market_exposure, tag_exposure or {}, book)
        else:
            self._queue_for_ui(signal)

    def _execute(
        self,
        signal: Signal,
        market_exposure: float,
        tag_exposure: dict[str, float],
        book: OrderBook | None,
    ) -> None:
        decision = self.risk.check_pre_trade(signal, market_exposure, tag_exposure)
        if not decision.allowed:
            log.info("trade_blocked", reason=decision.reason, signal=signal.signal_id)
            return

        size = decision.adjusted_size if decision.adjusted_size is not None else signal.kelly_size
        side = (
            OrderSide.BUY
            if signal.direction in (SignalDirection.BUY_YES, SignalDirection.BUY_NO)
            else OrderSide.SELL
        )
        req = OrderRequest(
            market_id=signal.market_id,
            side=side,
            size=size,
            order_type=OrderType.MARKET,
        )
        result = self.router.submit(req, book=book, idempotency_key=signal.signal_id)
        log.info("trade_executed", signal=signal.signal_id, status=result.status, size=size)

    @staticmethod
    def _queue_for_ui(signal: Signal) -> None:
        publish_event(
            "signal.new",
            {
                "signal_id": signal.signal_id,
                "strategy": signal.strategy,
                "market_id": signal.market_id,
                "market_title": signal.market_title,
                "direction": signal.direction.value,
                "confidence": signal.confidence,
                "edge": signal.edge,
                "kelly_size": signal.kelly_size,
                "reasoning": signal.reasoning,
                "expires_in_sec": signal.expires_in_sec,
            },
        )
        log.info("signal_queued", signal=signal.signal_id, strategy=signal.strategy)

    # ── circuit breakers ───────────────────────────────────
    def check_circuit_breakers(self, daily_pnl: float, drawdown_pct: float) -> None:
        self.risk.check_circuit_breakers(daily_pnl, drawdown_pct)
