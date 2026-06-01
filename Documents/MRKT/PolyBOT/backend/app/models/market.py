"""Market-making ORM models (from spec, adapted to SQLAlchemy 2.0)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MMPosition(Base):
    __tablename__ = "mm_positions"

    market_id: Mapped[str] = mapped_column(String, primary_key=True)
    inventory: Mapped[float] = mapped_column(Float, default=0.0)
    current_bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_bought: Mapped[float] = mapped_column(Float, default=0.0)
    total_sold: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MMOrder(Base):
    __tablename__ = "mm_orders"

    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    market_id: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String)  # buy | sell
    price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="open")  # open|filled|cancelled
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PriceSnapshot(Base):
    """Mid-price snapshots for sigma computation (TimescaleDB hypertable)."""

    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String, index=True)
    mid_price: Mapped[float] = mapped_column(Float)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
