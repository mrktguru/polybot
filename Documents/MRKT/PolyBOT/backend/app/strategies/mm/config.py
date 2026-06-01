"""Market Making configuration (from spec, configurable in Settings UI)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MMConfig:
    # Quoting algorithm (Avellaneda–Stoikov)
    gamma: float = 0.10  # risk aversion (0.01–0.5)
    kappa: float = 1.50  # market depth (0.5–5.0)
    q_max: float = 50.0  # max inventory in tokens

    # Market selection
    min_spread: float = 0.03
    min_volume_day: float = 500.0
    max_volume_day: float = 8000.0
    min_days: int = 7
    max_days: int = 90
    min_score: float = 0.45
    max_active_markets: int = 12

    # Risk
    max_position_usd: float = 25.0
    kill_zone_hours: int = 48
    max_price_jump_1h: float = 0.10

    # ── improvements (plan C.1) ────────────────────────────
    fee_per_share: float = 0.0  # Polymarket fees ~0, configurable
    adverse_premium: float = 0.01  # extra spread vs adverse selection
    min_orderbook_depth: int = 3  # skip thin books
    staleness_sec: int = 90  # cancel if book older than this
    requote_threshold: float = 0.005  # re-quote if quotes move > 0.5¢
    vol_window_hours: int = 6  # window for realized sigma (EWMA)

    excluded_categories: list = field(
        default_factory=lambda: [
            "crypto_price_short",
            "breaking_news",
            "sports_live",
        ]
    )
