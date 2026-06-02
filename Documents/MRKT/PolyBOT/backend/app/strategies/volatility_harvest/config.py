"""Volatility Harvesting strategy configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VolatilityHarvestConfig:
    # Spike detection
    spike_threshold_sigma: float = 3.0  # spike = k * sigma (plan C.4)
    atr_window: int = 14  # ATR periods
    spike_window_minutes: int = 30
    min_uncertainty: float = 0.25
    max_uncertainty: float = 0.75

    # News confirmation
    news_check_window_minutes: int = 35

    # Position management
    contrarian_target: float = 0.60
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.20
    max_position_usd: float = 50.0
    fixed_size: float = 50.0  # default VH size if Kelly not used

    # Liquidity check
    min_liquidity_for_exit: float = 200.0
