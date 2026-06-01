"""MarketSelector — scoring for MM market selection (from spec + C.1).

Adds an optional maker-rewards bonus so subsidized markets are prioritized.
A market dict is expected with keys:
  best_ask, best_bid, volume_24h, t_hours, sigma, mid, max_jump_1h,
  orderbook_depth, category, (optional) maker_reward_score.
"""

from __future__ import annotations

from app.strategies.mm.config import MMConfig


class MarketSelector:
    def __init__(self, config: MMConfig) -> None:
        self.cfg = config

    def score(self, market: dict) -> float | None:
        cfg = self.cfg
        spread = market["best_ask"] - market["best_bid"]
        t_hours = market["t_hours"]

        # Hard filters
        if spread < cfg.min_spread:
            return None
        if t_hours < cfg.kill_zone_hours:
            return None

        spread_score = min(spread / 0.15, 1.0)

        v = market["volume_24h"]
        if v < 200:
            liq_score = 0.0
        elif v < 500:
            liq_score = v / 500 * 0.4
        elif v <= 8000:
            liq_score = 0.4 + (v - 500) / 7500 * 0.6
        else:
            liq_score = max(0.0, 1.0 - (v - 8000) / 20000)

        t = t_hours / 24.0
        if t < 7:
            time_score = (t - 2) / 5 * 0.5
        elif t <= 30:
            time_score = 1.0
        elif t <= 90:
            time_score = 1.0 - (t - 30) / 60 * 0.4
        else:
            time_score = 0.6

        sigma = market["sigma"]
        if sigma < 0.01:
            vol_score = 0.2
        elif sigma <= 0.05:
            vol_score = 1.0
        elif sigma <= 0.12:
            vol_score = 1.0 - (sigma - 0.05) / 0.07 * 0.6
        else:
            vol_score = 0.0

        # Penalties
        penalty = 0.0
        if market["mid"] < 0.05 or market["mid"] > 0.95:
            penalty += 0.4
        if market.get("max_jump_1h", 0.0) > cfg.max_price_jump_1h:
            penalty += 0.3
        if market.get("orderbook_depth", 99) < cfg.min_orderbook_depth:
            penalty += 0.2
        if market.get("category") in cfg.excluded_categories:
            penalty += 0.25

        raw = (
            0.35 * spread_score
            + 0.25 * liq_score
            + 0.20 * time_score
            + 0.20 * vol_score
        )

        # Maker-rewards bonus (plan C.1): prioritize subsidized markets.
        reward_bonus = 0.10 * market.get("maker_reward_score", 0.0)

        return max(0.0, raw - penalty + reward_bonus)

    def select(self, markets: list[dict]) -> list[dict]:
        """Return scored markets above threshold, capped to max_active."""
        scored: list[dict] = []
        for m in markets:
            s = self.score(m)
            if s is not None and s >= self.cfg.min_score:
                scored.append({**m, "score": s})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: self.cfg.max_active_markets]
