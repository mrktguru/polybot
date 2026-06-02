"""Cross-Market Correlation strategy configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrossMarketConfig:
    # Violation detection
    nested_dates_threshold: float = 0.05
    exhaustive_threshold: float = 0.08
    conditional_threshold: float = 0.05
    implied_max_single_period: float = 0.60

    # LLM graph building
    llm_batch_size: int = 30
    graph_refresh_hours: int = 1

    # Position sizing
    kelly_fraction: float = 0.33
    max_pair_exposure_usd: float = 50.0

    # Execution
    min_edge_after_costs: float = 0.02
    fee_per_leg: float = 0.0
