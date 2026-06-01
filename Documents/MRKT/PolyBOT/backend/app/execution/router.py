"""OrderRouter — single execution entrypoint (plan A.3).

Strategies never call the CLOB directly. Every order flows through here:
  1. risk pre-trade check (delegated to RiskEngine by caller),
  2. idempotency (dedup by client order key),
  3. route to PaperTradingEngine or real CLOB,
  4. write audit log.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis, publish_event
from app.execution.clob_client import ClobClient
from app.execution.paper_engine import PaperTradingEngine
from app.execution.types import OrderBook, OrderRequest, OrderResult, OrderSide, OrderType

log = get_logger(__name__)

_IDEMPOTENCY_TTL_SEC = 300


class OrderRouter:
    def __init__(
        self,
        paper_engine: PaperTradingEngine | None = None,
        clob: ClobClient | None = None,
    ) -> None:
        self.paper = paper_engine or PaperTradingEngine()
        self.clob = clob or ClobClient()

    def submit(
        self,
        req: OrderRequest,
        book: OrderBook | None = None,
        idempotency_key: str | None = None,
    ) -> OrderResult:
        if idempotency_key and self._seen(idempotency_key):
            log.info("order_deduped", key=idempotency_key)
            return OrderResult(
                order_id=f"dedup-{idempotency_key}",
                market_id=req.market_id,
                side=req.side,
                requested_size=req.size,
                filled_size=0.0,
                avg_price=0.0,
                status="rejected",
                is_paper=settings.paper_trading,
                error="duplicate order suppressed",
            )

        result = (
            self.paper.execute(req, book)
            if settings.paper_trading
            else self._execute_live(req)
        )

        if idempotency_key:
            self._mark(idempotency_key)

        self._audit(req, result)
        publish_event(
            "order.result",
            {
                "order_id": result.order_id,
                "market_id": result.market_id,
                "side": result.side.value,
                "status": result.status,
                "filled_size": result.filled_size,
                "avg_price": result.avg_price,
                "is_paper": result.is_paper,
            },
        )
        return result

    # ── live execution ─────────────────────────────────────
    def _execute_live(self, req: OrderRequest) -> OrderResult:
        try:
            if req.order_type == OrderType.MARKET:
                # Market orders are emulated as aggressive limit at best px.
                book = self.clob.get_orderbook(req.market_id)
                px = book.best_ask if req.side == OrderSide.BUY else book.best_bid
                if px is None:
                    raise RuntimeError("empty orderbook")
                order_id = self.clob.place_limit(
                    req.market_id, req.side.value, px, req.size
                )
                return OrderResult(
                    order_id=order_id,
                    market_id=req.market_id,
                    side=req.side,
                    requested_size=req.size,
                    filled_size=req.size,
                    avg_price=px,
                    status="open",
                    is_paper=False,
                )
            order_id = self.clob.place_limit(
                req.market_id, req.side.value, req.price or 0.0, req.size
            )
            return OrderResult(
                order_id=order_id,
                market_id=req.market_id,
                side=req.side,
                requested_size=req.size,
                filled_size=0.0,
                avg_price=req.price or 0.0,
                status="open",
                is_paper=False,
            )
        except Exception as exc:
            log.error("live_execution_failed", error=str(exc), market=req.market_id)
            return OrderResult(
                order_id="",
                market_id=req.market_id,
                side=req.side,
                requested_size=req.size,
                filled_size=0.0,
                avg_price=0.0,
                status="rejected",
                is_paper=False,
                error=str(exc),
            )

    # ── helpers ────────────────────────────────────────────
    @staticmethod
    def _seen(key: str) -> bool:
        return bool(get_redis().exists(f"polybot.order.idem:{key}"))

    @staticmethod
    def _mark(key: str) -> None:
        get_redis().set(f"polybot.order.idem:{key}", "1", ex=_IDEMPOTENCY_TTL_SEC)

    @staticmethod
    def _audit(req: OrderRequest, result: OrderResult) -> None:
        log.info(
            "order_audit",
            market=req.market_id,
            side=req.side.value,
            requested=req.size,
            filled=result.filled_size,
            status=result.status,
            paper=result.is_paper,
        )
