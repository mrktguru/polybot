"""Whale Copying strategy configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WhaleCopyingConfig:
    # Whale detection
    min_bet_usd: float = 5000
    new_wallet_tx_limit: int = 5
    percentile_threshold: float = 0.95
    copy_delay_sec: int = 30
    copy_size_pct: float = 0.10  # copy 10% of whale bet

    # Smart money criteria
    min_win_rate: float = 0.60
    min_calibration: float = 0.65
    min_total_bets: int = 20

    # Risk
    max_copy_usd: float = 25.0
    max_per_wallet_exposure: float = 50.0

    # Trust decay
    trust_decay_per_day: float = 0.01
