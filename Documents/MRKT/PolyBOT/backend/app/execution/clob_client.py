"""Thin wrapper around the Polymarket CLOB client.

Isolates the third-party `py-clob-client` dependency behind a small,
typed surface. In paper mode or when credentials are absent, methods that
require auth raise, and execution is handled by PaperTradingEngine instead.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.execution.types import OrderBook

log = get_logger(__name__)


class ClobClient:
    """Lazy wrapper; real client is constructed on first use."""

    def __init__(self) -> None:
        self._client = None

    def _ensure(self) -> None:
        if self._client is not None:
            return
        try:
            from py_clob_client.client import ClobClient as _Real  # type: ignore

            self._client = _Real(
                host=settings.clob_host,
                key=settings.clob_api_key or None,
                secret=settings.clob_api_secret or None,
                passphrase=settings.clob_api_passphrase or None,
            )
        except Exception as exc:  # pragma: no cover - depends on optional dep
            log.warning("clob_client_unavailable", error=str(exc))
            raise

    def get_orderbook(self, market_id: str) -> OrderBook:
        """Fetch current orderbook for a market token id."""
        self._ensure()
        raw = self._client.get_order_book(market_id)  # type: ignore[union-attr]
        bids = [(float(b.price), float(b.size)) for b in getattr(raw, "bids", [])]
        asks = [(float(a.price), float(a.size)) for a in getattr(raw, "asks", [])]
        bids.sort(key=lambda x: x[0], reverse=True)
        asks.sort(key=lambda x: x[0])
        return OrderBook(market_id=market_id, bids=bids, asks=asks)

    def get_mid(self, market_id: str) -> float | None:
        return self.get_orderbook(market_id).mid

    def place_limit(self, market_id: str, side: str, price: float, size: float) -> str:
        self._ensure()
        resp = self._client.create_and_post_order(  # type: ignore[union-attr]
            {"token_id": market_id, "side": side, "price": price, "size": size}
        )
        return str(resp.get("orderID", ""))

    def cancel_all(self, market_id: str) -> None:
        self._ensure()
        self._client.cancel_market_orders(market_id)  # type: ignore[union-attr]
