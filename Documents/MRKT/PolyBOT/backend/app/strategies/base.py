"""BaseStrategy interface and signal types.

Extended from the spec (`polymarket-bot-strategies.md`) per plan C.0:
- `Signal` gains `signal_id`, `created_at`, `correlation_tags`, `cost_usd`.
- Strategies NEVER trade directly; they only return signals. Execution
  is centralized in the execution layer (`app.execution`).
- Adds `validate()` sanity-check hook and `risk_tags()`.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class AutomationLevel(str, Enum):
    FULL = "full"  # bot trades autonomously
    SEMI = "semi"  # bot proposes, human confirms
    HUMAN = "human"  # informational only


class SignalDirection(str, Enum):
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    CLOSE = "close"
    HOLD = "hold"


def _now() -> datetime:
    return datetime.now(UTC)


def make_signal_id(strategy: str, market_id: str, bucket: str, direction: str) -> str:
    """Deterministic signal id for dedup (plan C.0 / A.3).

    `bucket` should be a coarse time bucket (e.g. ISO minute/hour) so the
    same opportunity within a window collapses to a single id.
    """
    raw = f"{strategy}|{market_id}|{bucket}|{direction}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class Signal:
    strategy: str
    market_id: str
    market_title: str
    direction: SignalDirection
    confidence: float  # 0.0–1.0
    edge: float  # our edge vs market
    kelly_size: float  # $ position size suggestion
    entry_price: float
    reasoning: str
    auto_execute: bool  # True = execute without confirmation
    expires_in_sec: int
    metadata: dict = field(default_factory=dict)

    # ── extensions (plan C.0) ──────────────────────────────
    signal_id: str = ""
    created_at: datetime = field(default_factory=_now)
    correlation_tags: list[str] = field(default_factory=list)
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not self.signal_id:
            bucket = self.created_at.strftime("%Y%m%d%H%M")
            self.signal_id = make_signal_id(
                self.strategy, self.market_id, bucket, self.direction.value
            )


@dataclass
class StrategyResult:
    signals: list[Signal]
    markets_scanned: int
    execution_time_ms: int
    errors: list[str] = field(default_factory=list)
    cost_usd: float = 0.0  # spend on LLM / external API for this scan
    latency_breakdown: dict[str, int] = field(default_factory=dict)


class BaseStrategy(ABC):
    """Common interface for all strategies.

    Concrete strategies set `name`, `automation_level`, `min_confidence`,
    `max_auto_size` and implement `scan()`. They do NOT execute orders;
    they return `Signal`s for the execution layer.
    """

    name: str = "base"
    automation_level: AutomationLevel = AutomationLevel.HUMAN
    min_confidence: float = 0.6
    max_auto_size: float = 25.0

    @abstractmethod
    def scan(self, markets: list[dict]) -> StrategyResult:
        """Scan markets and return signals."""

    def validate(self, signal: Signal) -> list[str]:
        """Sanity-check a signal. Returns a list of error strings (empty = ok)."""
        errors: list[str] = []
        if not (0.0 <= signal.confidence <= 1.0):
            errors.append("confidence out of [0,1]")
        if not (0.0 < signal.entry_price < 1.0):
            errors.append("entry_price must be in (0,1)")
        if signal.kelly_size < 0:
            errors.append("kelly_size negative")
        return errors

    def risk_tags(self, signal: Signal) -> list[str]:
        """Tags used by the risk engine for correlation grouping."""
        return signal.correlation_tags or [self.name]

    def should_auto_execute(self, signal: Signal) -> bool:
        return (
            self.automation_level == AutomationLevel.FULL
            and signal.auto_execute
            and signal.confidence >= self.min_confidence
            and signal.kelly_size <= self.max_auto_size
        )
