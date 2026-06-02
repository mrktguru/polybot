"""Sentiment Divergence strategy configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SentimentDivergenceConfig:
    min_gap: float = 0.08
    min_sources: int = 2

    # Source reliability (initial, will be calibrated)
    source_reliability: dict = field(default_factory=lambda: {
        "metaculus": 0.75,
        "predictit": 0.80,
        "manifold": 0.60,
        "betting_odds": 0.85,
    })

    # Polling intervals
    poll_intervals: dict = field(default_factory=lambda: {
        "metaculus": 900,
        "predictit": 300,
        "manifold": 600,
        "betting_odds": 300,
    })

    # LLM
    llm_model: str = "claude-haiku-4-5-20251001"
