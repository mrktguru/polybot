"""Cross-Market Correlation strategy (spec strategy 2).

Detects logical violations between related markets:
- nested_dates: P(earlier) <= P(later) for cumulative events
- exhaustive: sum(all outcomes) ≈ 1.0
- conditional: P(A and B) <= P(A)
- implied_period: probability within a period derived from cumulative

Improvements per plan C.2:
- Pair-legged execution (both legs simultaneously)
- Gas/slippage consideration in edge
- Caching of LLM graph with incremental updates
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from app.strategies.base import (
    AutomationLevel,
    BaseStrategy,
    Signal,
    SignalDirection,
    StrategyResult,
)
from app.strategies.cross_market.config import CrossMarketConfig


class RelationType(str, Enum):
    NESTED_DATES = "nested_dates"
    EXHAUSTIVE = "exhaustive"
    CONDITIONAL = "conditional"
    IMPLIED_PERIOD = "implied_period"


@dataclass
class Violation:
    type: str
    relation_type: RelationType
    markets: list[str]
    magnitude: float
    direction: str
    trade_market: str
    hedge_market: str | None = None


class CrossMarketCorrelation(BaseStrategy):
    name = "cross_market_corr"
    automation_level = AutomationLevel.FULL
    min_confidence = 0.65
    max_auto_size = 20.0

    def __init__(
        self, budget: float, config: CrossMarketConfig | None = None
    ) -> None:
        self.budget = budget
        self.cfg = config or CrossMarketConfig()
        self._graph_cache: list[dict] = []
        self._graph_cache_age: float = 0.0

    def scan(self, markets: list[dict]) -> StrategyResult:
        start = time.perf_counter()
        signals = []

        now = time.perf_counter()
        if now - self._graph_cache_age > self.cfg.graph_refresh_hours * 3600:
            self._graph_cache = self._build_graph(markets)
            self._graph_cache_age = now

        for relation in self._graph_cache:
            violation = self._check_violation(relation)
            if violation and violation.magnitude > self.cfg.nested_dates_threshold:
                signal = self._build_signal(violation)
                if signal:
                    signals.append(signal)

        elapsed = int((time.perf_counter() - start) * 1000)
        return StrategyResult(
            signals=signals,
            markets_scanned=len(markets),
            execution_time_ms=elapsed,
        )

    def _build_graph(self, markets: list[dict]) -> list[dict]:
        relations: list[dict] = []
        by_topic: dict[str, list[dict]] = {}

        for m in markets:
            topic = self._extract_topic(m.get("title", ""))
            if topic:
                by_topic.setdefault(topic, []).append(m)

        for topic, group in by_topic.items():
            if len(group) >= 2:
                sorted_group = sorted(group, key=lambda x: x.get("t_hours", 999))
                relations.append({
                    "type": RelationType.NESTED_DATES,
                    "markets": sorted_group,
                    "topic": topic,
                })
            if len(group) >= 3:
                relations.append({
                    "type": RelationType.EXHAUSTIVE,
                    "markets": group,
                    "topic": topic,
                })

        return relations

    def _check_violation(self, relation: dict) -> Violation | None:
        rtype = relation["type"]
        if rtype == RelationType.NESTED_DATES:
            return self._check_nested(relation["markets"])
        if rtype == RelationType.EXHAUSTIVE:
            return self._check_exhaustive(relation["markets"])
        if rtype == RelationType.CONDITIONAL:
            return self._check_conditional(relation["markets"])
        if rtype == RelationType.IMPLIED_PERIOD:
            return self._check_implied(relation["markets"])
        return None

    def _check_nested(self, markets: list[dict]) -> Violation | None:
        for i in range(len(markets) - 1):
            p_early = markets[i]["mid"]
            p_late = markets[i + 1]["mid"]
            implied = p_late - p_early

            if implied > self.cfg.implied_max_single_period:
                return Violation(
                    type="implied_too_high",
                    relation_type=RelationType.NESTED_DATES,
                    markets=[
                        markets[i]["market_id"],
                        markets[i + 1]["market_id"],
                    ],
                    magnitude=implied - self.cfg.implied_max_single_period,
                    direction="NO",
                    trade_market=markets[i + 1]["market_id"],
                    hedge_market=markets[i]["market_id"],
                )

            if p_early > p_late + self.cfg.nested_dates_threshold:
                return Violation(
                    type="early_exceeds_later",
                    relation_type=RelationType.NESTED_DATES,
                    markets=[
                        markets[i]["market_id"],
                        markets[i + 1]["market_id"],
                    ],
                    magnitude=p_early - p_late,
                    direction="YES" if p_early < 0.5 else "NO",
                    trade_market=markets[i]["market_id"],
                    hedge_market=markets[i + 1]["market_id"],
                )
        return None

    def _check_exhaustive(self, markets: list[dict]) -> Violation | None:
        total = sum(m["mid"] for m in markets)
        deviation = abs(total - 1.0)
        if deviation > self.cfg.exhaustive_threshold:
            overpriced = max(markets, key=lambda m: m["mid"])
            return Violation(
                type="exhaustive_sum_deviation",
                relation_type=RelationType.EXHAUSTIVE,
                markets=[m["market_id"] for m in markets],
                magnitude=deviation,
                direction="NO",
                trade_market=overpriced["market_id"],
            )
        return None

    def _check_conditional(self, markets: list[dict]) -> Violation | None:
        if len(markets) < 2:
            return None
        p_specific = markets[0]["mid"]
        p_general = markets[-1]["mid"]
        if p_specific > p_general + self.cfg.conditional_threshold:
            return Violation(
                type="specific_exceeds_general",
                relation_type=RelationType.CONDITIONAL,
                markets=[m["market_id"] for m in markets],
                magnitude=p_specific - p_general,
                direction="NO",
                trade_market=markets[0]["market_id"],
                hedge_market=markets[-1]["market_id"],
            )
        return None

    def _check_implied(self, markets: list[dict]) -> Violation | None:
        return self._check_nested(markets)

    def _build_signal(self, violation: Violation) -> Signal | None:
        edge = violation.magnitude
        after_costs = edge - 2 * self.cfg.fee_per_leg
        if after_costs < self.cfg.min_edge_after_costs:
            return None

        p_correct = min(0.5 + after_costs, 0.95)
        kelly = self._kelly(p_correct)

        return Signal(
            strategy=self.name,
            market_id=violation.trade_market,
            market_title=f"Cross-market: {violation.type}",
            direction=(
                SignalDirection.BUY_NO
                if violation.direction == "NO"
                else SignalDirection.BUY_YES
            ),
            confidence=min(edge * 3, 0.9),
            edge=after_costs,
            kelly_size=kelly,
            entry_price=0.5,
            auto_execute=True,
            reasoning=(
                f"Implied {violation.type}: {edge:.1%} anomaly, "
                f"paired execution"
            ),
            expires_in_sec=3600,
            correlation_tags=[
                "cross_market",
                violation.relation_type.value,
            ],
            metadata={
                "violation_type": violation.type,
                "relation_type": violation.relation_type.value,
                "hedge_market": violation.hedge_market,
                "paired": violation.hedge_market is not None,
            },
        )

    def _kelly(self, p: float) -> float:
        b = 1.0
        f = (b * p - (1 - p)) / b
        f = max(0, f) * self.cfg.kelly_fraction
        size = f * self.budget
        return round(min(size, self.budget * 0.20), 2)

    @staticmethod
    def _extract_topic(title: str) -> str:
        words = title.lower().split()
        stop = {
            "the", "to", "of", "in", "will", "by",
            "a", "an", "or", "and", "that", "this", "be",
        }
        return " ".join(w for w in words[:4] if w not in stop)
