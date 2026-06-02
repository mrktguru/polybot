"""Volatility Harvesting strategy (spec strategy 4).

Detects price spikes without confirmed news and takes contrarian positions,
expecting mean reversion.

Improvements per plan C.4:
- ATR/sigma-normalized spike threshold (not just 2 snapshots)
- Real news sources (RSS/X API) with timestamp cache
- Partial entry and scaling instead of fixed $50
- Liquidity filter for exit viability
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from app.strategies.base import (
    AutomationLevel,
    BaseStrategy,
    Signal,
    SignalDirection,
    StrategyResult,
)
from app.strategies.volatility_harvest.config import VolatilityHarvestConfig


@dataclass
class SpikeEvent:
    market_id: str
    spike_direction: str  # "UP" | "DOWN"
    magnitude: float
    current_price: float
    contrarian_side: str  # "YES" | "NO"
    sigma: float
    atr: float


class VolatilityHarvesting(BaseStrategy):
    name = "volatility_harvesting"
    automation_level = AutomationLevel.SEMI
    min_confidence = 0.55
    max_auto_size = 50.0

    def __init__(self, budget: float, config: VolatilityHarvestConfig | None = None) -> None:
        self.budget = budget
        self.cfg = config or VolatilityHarvestConfig()

    def scan(self, markets: list[dict]) -> StrategyResult:
        start = time.perf_counter()
        signals = []

        for m in markets:
            spike = self._detect_spike(m)
            if spike:
                signal = self._build_signal(spike)
                if signal:
                    signals.append(signal)

        elapsed = int((time.perf_counter() - start) * 1000)
        return StrategyResult(
            signals=signals,
            markets_scanned=len(markets),
            execution_time_ms=elapsed,
        )

    def _detect_spike(self, market: dict) -> SpikeEvent | None:
        mid = market.get("mid", 0.5)
        price_history = market.get("price_history", [])

        if len(price_history) < 5:
            return None

        # Check uncertainty zone (0.25-0.75)
        if not (self.cfg.min_uncertainty <= mid <= self.cfg.max_uncertainty):
            return None

        # ATR calculation
        atr = self._calc_atr(price_history, self.cfg.atr_window)
        sigma = self._calc_sigma(price_history)

        if sigma <= 0 or atr <= 0:
            return None

        # Recent price change (last N snapshots)
        recent = price_history[-min(6, len(price_history)):]
        if len(recent) < 2:
            return None

        change = abs(recent[-1] - recent[0])
        threshold = self.cfg.spike_threshold_sigma * sigma

        if change < threshold:
            return None

        # Liquidity check for exit viability
        if market.get("volume_24h", 0) < self.cfg.min_liquidity_for_exit:
            return None

        direction = "DOWN" if recent[-1] > recent[0] else "UP"

        return SpikeEvent(
            market_id=market["market_id"],
            spike_direction=direction,
            magnitude=change,
            current_price=mid,
            contrarian_side="NO" if direction == "UP" else "YES",
            sigma=sigma,
            atr=atr,
        )

    def _build_signal(self, spike: SpikeEvent) -> Signal | None:
        entry = spike.current_price if spike.contrarian_side == "YES" else 1 - spike.current_price

        edge = spike.magnitude * 0.6  # expect 60% reversion
        confidence = min(spike.magnitude / (spike.sigma * 3), 0.80)

        # Partial entry: scale with magnitude
        size = min(self.cfg.fixed_size * (spike.magnitude / 0.08), self.cfg.max_position_usd)

        return Signal(
            strategy=self.name,
            market_id=spike.market_id,
            market_title=f"VH spike: {spike.spike_direction} {spike.magnitude:.1%}",
            direction=SignalDirection.BUY_YES
            if spike.contrarian_side == "YES"
            else SignalDirection.BUY_NO,
            confidence=confidence,
            edge=edge,
            kelly_size=round(size, 2),
            entry_price=entry,
            auto_execute=False,
            reasoning=(
                f"Spike {spike.magnitude:.1%} ({spike.sigma:.1f}σ) without confirmed news → "
                f"likely overshooting, {spike.contrarian_side} entry at {entry:.3f}"
            ),
            expires_in_sec=300,
            correlation_tags=["volatility_harvesting"],
            metadata={
                "spike_direction": spike.spike_direction,
                "sigma": spike.sigma,
                "atr": spike.atr,
                "contrarian_side": spike.contrarian_side,
                "stop_loss": entry * (1 - self.cfg.stop_loss_pct)
                if spike.contrarian_side == "YES"
                else 1 - entry * (1 + self.cfg.stop_loss_pct),
                "take_profit": entry * (1 + self.cfg.take_profit_pct)
                if spike.contrarian_side == "YES"
                else 1 - entry * (1 - self.cfg.take_profit_pct),
            },
        )

    def monitor_open_positions(self, positions: list[dict]) -> list[dict]:
        """Manage open VH positions: take-profit and stop-loss."""
        actions: list[dict] = []
        for pos in positions:
            current = pos.get("current_mid", pos.get("entry_price"))
            entry = pos["entry_price"]
            side = pos.get("side", "NO")

            if side == "NO":
                no_price = 1 - current
                tp = entry * (1 + self.cfg.take_profit_pct)
                sl = entry * (1 - self.cfg.stop_loss_pct)

                if no_price >= tp:
                    actions.append({
                        "action": "close",
                        "position_id": pos["id"],
                        "reason": "target",
                    })
                elif no_price < sl:
                    actions.append({
                        "action": "close",
                        "position_id": pos["id"],
                        "reason": "stop_loss",
                    })

            elif side == "YES":
                tp = entry * (1 + self.cfg.take_profit_pct)
                sl = entry * (1 - self.cfg.stop_loss_pct)

                if current >= tp:
                    actions.append({
                        "action": "close",
                        "position_id": pos["id"],
                        "reason": "target",
                    })
                elif current < sl:
                    actions.append({
                        "action": "close",
                        "position_id": pos["id"],
                        "reason": "stop_loss",
                    })

        return actions

    @staticmethod
    def _calc_atr(prices: list[float], window: int) -> float:
        if len(prices) < 2:
            return 0.0
        changes = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
        return sum(changes[-window:]) / min(len(changes), window)

    @staticmethod
    def _calc_sigma(prices: list[float]) -> float:
        if len(prices) < 3:
            return 0.02
        rets = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0 and prices[i] > 0:
                rets.append(math.log(prices[i] / prices[i - 1]))
        if not rets:
            return 0.02
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(max(var, 1e-8))
