"""Capital Allocator (plan C.7).

Dynamic allocation across strategies based on realized performance, with
hard min/max bounds per strategy. Starts from the static weights in the
spec and adjusts by a smoothed performance score.
"""

from __future__ import annotations

from dataclasses import dataclass

# Static base weights from the spec (StrategyManager).
BASE_WEIGHTS: dict[str, float] = {
    "market_making": 0.60,
    "cross_market_corr": 0.10,
    "resolution_arb": 0.05,
    "volatility_harvesting": 0.10,
    "whale_copying": 0.05,
    "sentiment_divergence": 0.05,
    "reserve": 0.05,
}

# Hard bounds (share of capital) to avoid over-concentration.
BOUNDS: dict[str, tuple[float, float]] = {
    "market_making": (0.30, 0.70),
    "cross_market_corr": (0.02, 0.25),
    "resolution_arb": (0.0, 0.15),
    "volatility_harvesting": (0.02, 0.20),
    "whale_copying": (0.0, 0.15),
    "sentiment_divergence": (0.0, 0.15),
}


@dataclass
class CapitalAllocator:
    total_capital: float
    smoothing: float = 0.5  # blend between base weights and performance tilt

    def allocate(self, performance: dict[str, float] | None = None) -> dict[str, float]:
        """Return dollar budgets per strategy.

        `performance` maps strategy -> score (e.g. recent Sharpe or edge).
        Higher score tilts allocation upward within bounds.
        """
        weights = dict(BASE_WEIGHTS)

        if performance:
            tradable = {k: v for k, v in performance.items() if k in BOUNDS}
            total_score = sum(max(0.0, s) for s in tradable.values())
            if total_score > 0:
                for k in tradable:
                    perf_w = max(0.0, performance[k]) / total_score
                    base_w = BASE_WEIGHTS.get(k, 0.0)
                    blended = (1 - self.smoothing) * base_w + self.smoothing * perf_w
                    lo, hi = BOUNDS[k]
                    weights[k] = min(max(blended, lo), hi)

        # Renormalize tradable weights to leave the reserve intact.
        reserve = BASE_WEIGHTS["reserve"]
        tradable_keys = [k for k in weights if k != "reserve"]
        tradable_sum = sum(weights[k] for k in tradable_keys)
        if tradable_sum > 0:
            scale = (1.0 - reserve) / tradable_sum
            for k in tradable_keys:
                weights[k] *= scale

        return {k: round(w * self.total_capital, 2) for k, w in weights.items()}
