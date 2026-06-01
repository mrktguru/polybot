"""Core trading ORM models (plan part E).

Unified `Position` state machine, `SignalRecord` queue, `AuditLog`, and
`StrategyConfig` versioning. Replaces the scattered fields in the spec.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Position(Base):
    """Unified position with a state machine (pending|open|closing|closed|failed)."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String, index=True)
    market_id: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String)  # buy_yes | buy_no
    size: Mapped[float] = mapped_column(Float, default=0.0)
    entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    correlation_tags: Mapped[list | None] = mapped_column(JSON, default=list)
    is_paper: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SignalRecord(Base):
    """Persisted signal queue for semi-auto strategies."""

    __tablename__ = "signals"

    signal_id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy: Mapped[str] = mapped_column(String, index=True)
    market_id: Mapped[str] = mapped_column(String, index=True)
    market_title: Mapped[str] = mapped_column(String, default="")
    direction: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    kelly_size: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    reasoning: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    # pending|approved|rejected|expired|executed
    signal_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    """Append-only audit log of executions and risk events."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String, default="system")
    event_type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, default=dict)


class StrategyConfig(Base):
    """Versioned strategy parameter configs."""

    __tablename__ = "strategy_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String, index=True)
    config: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[str] = mapped_column(String, default="user")
