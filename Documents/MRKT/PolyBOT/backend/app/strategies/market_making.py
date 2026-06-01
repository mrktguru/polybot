"""Market Making strategy — 100% automation, primary income (spec strategy 1).

Wires MarketSelector + InventorySkewMM into the BaseStrategy interface.
Quoting is exposed via `compute_market_quotes`; `scan` returns informational
signals (MM acts via the dedicated quote-update Celery task, not generic
signal execution).
"""

from __future__ import annotations

import time

from app.strategies.base import (
    AutomationLevel,
    BaseStrategy,
    Signal,
    SignalDirection,
    StrategyResult,
)
from app.strategies.mm.config import MMConfig
from app.strategies.mm.quoting import InventorySkewMM, QuoteResult
from app.strategies.mm.selector import MarketSelector
from app.strategies.mm.volatility import realized_sigma


class MarketMaking(BaseStrategy):
    name = "market_making"
    automation_level = AutomationLevel.FULL
    min_confidence = 0.0  # MM auto-quotes; confidence not the gate
    max_auto_size = 25.0

    def __init__(self, budget: float, config: MMConfig | None = None) -> None:
        self.budget = budget
        self.cfg = config or MMConfig()
        self.cfg.max_position_usd = min(self.cfg.max_position_usd, budget * 0.20)
        self.selector = MarketSelector(self.cfg)
        self.quoter = InventorySkewMM(self.cfg)

    def scan(self, markets: list[dict]) -> StrategyResult:
        start = time.perf_counter()
        selected = self.selector.select(markets)
        signals: list[Signal] = []
        for m in selected:
            signals.append(
                Signal(
                    strategy=self.name,
                    market_id=m["market_id"],
                    market_title=m.get("title", m["market_id"]),
                    direction=SignalDirection.HOLD,
                    confidence=float(m["score"]),
                    edge=m["best_ask"] - m["best_bid"],
                    kelly_size=self.cfg.max_position_usd,
                    entry_price=m["mid"],
                    reasoning=f"MM candidate score={m['score']:.2f}",
                    auto_execute=False,  # quoting handled by mm task
                    expires_in_sec=3600,
                    correlation_tags=["market_making", m.get("category", "uncat")],
                    metadata={"score": m["score"]},
                )
            )
        elapsed = int((time.perf_counter() - start) * 1000)
        return StrategyResult(
            signals=signals, markets_scanned=len(markets), execution_time_ms=elapsed
        )

    def compute_market_quotes(
        self,
        mid: float,
        inventory: float,
        price_history: list[float],
        t_hours: float,
        orderbook_depth: int = 99,
        book_age_sec: float = 0.0,
    ) -> QuoteResult:
        sigma = realized_sigma(price_history)
        return self.quoter.compute_quotes(
            mid=mid,
            q=inventory,
            sigma=sigma,
            t_hours=t_hours,
            orderbook_depth=orderbook_depth,
            book_age_sec=book_age_sec,
        )
