import time
from dataclasses import dataclass

from app.strategies.base import (
    AutomationLevel,
    BaseStrategy,
    Signal,
    SignalDirection,
    StrategyResult,
)


@dataclass
class ArbOpportunity:
    market_id: str
    market_title: str
    outcome: str
    current_price: float
    gap: float
    feed_name: str
    confirmed: bool


class ResolutionArbitrage(BaseStrategy):
    name = "resolution_arb"
    automation_level = AutomationLevel.FULL
    min_confidence = 0.80
    max_auto_size = 25.0

    def __init__(
        self,
        budget: float,
        min_arb_gap: float = 0.03,
        arb_position_size: float = 25.0,
    ) -> None:
        self.budget = budget
        self.min_arb_gap = min_arb_gap
        self.arb_position_size = arb_position_size
        self._feed_data: dict[str, dict] = {}
        self._confirmations: dict[str, tuple[float, str]] = {}
        self._market_feed_map: dict[str, str] = {}

    def scan(self, markets: list[dict]) -> StrategyResult:
        start = time.perf_counter()
        signals = []

        for m in markets:
            feed_name = self._market_feed_map.get(m["market_id"])
            if not feed_name:
                continue

            data = self._feed_data.get(feed_name)
            if not data:
                continue

            outcome = self._determine_outcome(m, data)
            if outcome is None:
                continue

            current_price = m["mid"]
            gap = self._calc_gap(outcome, current_price)

            if gap < self.min_arb_gap:
                continue

            if self._confirm(m["market_id"], outcome):
                signal = self._build_signal(m, outcome, gap, feed_name)
                if signal:
                    signals.append(signal)

        elapsed = int((time.perf_counter() - start) * 1000)
        return StrategyResult(
            signals=signals,
            markets_scanned=len(markets),
            execution_time_ms=elapsed,
        )

    def on_data_update(self, feed_name: str, data: dict) -> list[Signal]:
        """Called when a feed updates. Finds related markets."""
        signals = []

        for m_id, f_name in self._market_feed_map.items():
            if f_name != feed_name:
                continue

            outcome = self._determine_outcome(
                {"market_id": m_id, "mid": 0.5}, data
            )
            if outcome:
                gap = self._calc_gap(outcome, 0.5)
                if gap >= self.min_arb_gap and self._confirm(m_id, outcome):
                    signal = self._build_signal(
                        {"market_id": m_id, "mid": 0.5, "title": f_name},
                        outcome,
                        gap,
                        feed_name,
                    )
                    if signal:
                        signals.append(signal)

        return signals

    def _determine_outcome(self, market: dict, data: dict) -> str | None:
        return data.get("outcome")

    def _calc_gap(self, outcome: str, current_price: float) -> float:
        if outcome == "YES" and current_price < 1.0:
            return 1.0 - current_price
        if outcome == "NO" and current_price > 0.0:
            return current_price
        return 0.0

    def _confirm(self, market_id: str, outcome: str) -> bool:
        """Double confirmation within a 5 min window."""
        now = time.time()
        if market_id in self._confirmations:
            prev_time, prev_outcome = self._confirmations[market_id]
            if prev_outcome == outcome and now - prev_time < 300:
                return True
        self._confirmations[market_id] = (now, outcome)
        return False

    def _build_signal(
        self, market: dict, outcome: str, gap: float, feed_name: str
    ) -> Signal | None:
        edge = gap * 0.8

        return Signal(
            strategy=self.name,
            market_id=market["market_id"],
            market_title=market.get("title", market["market_id"]),
            direction=(
                SignalDirection.BUY_YES
                if outcome == "YES"
                else SignalDirection.BUY_NO
            ),
            confidence=min(0.5 + gap * 2, 0.98),
            edge=edge,
            kelly_size=self.arb_position_size,
            entry_price=market.get("mid", 0.5),
            auto_execute=True,
            reasoning=(
                f"Resolution arb via {feed_name}: {outcome} confirmed, "
                f"gap {gap:.1%}"
            ),
            expires_in_sec=60,
            correlation_tags=["resolution_arb", feed_name],
            metadata={
                "outcome": outcome,
                "feed": feed_name,
                "gap": gap,
                "confirmed": True,
            },
        )

    def register_market_feed(self, market_id: str, feed_name: str) -> None:
        self._market_feed_map[market_id] = feed_name

    def update_feed_data(self, feed_name: str, data: dict) -> None:
        self._feed_data[feed_name] = data
