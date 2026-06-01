"""Paper Trading Engine (plan A.3).

First-class simulated execution with the same interface as the real
executor. Fills market orders against a provided orderbook (or a supplied
mid price) and applies a simple slippage model. Used for the $500 MVP and
as the forward-test layer on top of the backtester.
"""

from __future__ import annotations

import uuid

from app.core.logging import get_logger
from app.execution.types import OrderBook, OrderRequest, OrderResult, OrderSide, OrderType

log = get_logger(__name__)


class PaperTradingEngine:
    def __init__(self, fee_bps: float = 0.0) -> None:
        # Polymarket maker/taker fees are currently ~0; kept configurable.
        self.fee_bps = fee_bps

    def execute(self, req: OrderRequest, book: OrderBook | None) -> OrderResult:
        oid = f"paper-{uuid.uuid4().hex[:12]}"

        ref_price = self._reference_price(req, book)
        if ref_price is None:
            return OrderResult(
                order_id=oid,
                market_id=req.market_id,
                side=req.side,
                requested_size=req.size,
                filled_size=0.0,
                avg_price=0.0,
                status="rejected",
                is_paper=True,
                error="no reference price",
            )

        fill_price = self._apply_slippage(req, ref_price)

        # Reject if slippage exceeds cap for market orders.
        if req.order_type == OrderType.MARKET and abs(fill_price - ref_price) > req.max_slippage:
            return OrderResult(
                order_id=oid,
                market_id=req.market_id,
                side=req.side,
                requested_size=req.size,
                filled_size=0.0,
                avg_price=ref_price,
                status="rejected",
                is_paper=True,
                error="slippage exceeds cap",
            )

        log.info(
            "paper_fill",
            market=req.market_id,
            side=req.side.value,
            size=req.size,
            price=fill_price,
        )
        return OrderResult(
            order_id=oid,
            market_id=req.market_id,
            side=req.side,
            requested_size=req.size,
            filled_size=req.size,
            avg_price=round(fill_price, 4),
            status="filled",
            is_paper=True,
        )

    @staticmethod
    def _reference_price(req: OrderRequest, book: OrderBook | None) -> float | None:
        if req.order_type == OrderType.LIMIT and req.price is not None:
            return req.price
        if book is None:
            return None
        if req.side == OrderSide.BUY:
            return book.best_ask or book.mid
        return book.best_bid or book.mid

    @staticmethod
    def _apply_slippage(req: OrderRequest, ref_price: float) -> float:
        # Simple linear slippage proportional to size (toy model).
        slip = min(0.02, req.size / 5000.0)
        if req.side == OrderSide.BUY:
            return min(0.99, ref_price + slip)
        return max(0.01, ref_price - slip)
