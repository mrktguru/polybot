"""Shared execution types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


@dataclass
class OrderRequest:
    market_id: str
    side: OrderSide
    size: float  # in USD notional
    order_type: OrderType = OrderType.MARKET
    price: float | None = None  # required for LIMIT
    max_slippage: float = 0.03  # cap for market orders


@dataclass
class OrderResult:
    order_id: str
    market_id: str
    side: OrderSide
    requested_size: float
    filled_size: float
    avg_price: float
    status: str  # filled | partial | rejected | open
    is_paper: bool
    error: str | None = None


@dataclass
class OrderBook:
    market_id: str
    bids: list[tuple[float, float]]  # (price, size)
    asks: list[tuple[float, float]]

    @property
    def best_bid(self) -> float | None:
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0][0] if self.asks else None

    @property
    def mid(self) -> float | None:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def depth(self) -> int:
        return len(self.bids) + len(self.asks)
