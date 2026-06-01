"""InventorySkewMM — Avellaneda–Stoikov quoting (plan C.1 improvements).

Improvements over the spec:
- sigma is realized vol from a price window (caller supplies it),
- spread floor based on fees + adverse-selection premium,
- symmetric inventory skew (works for YES/NO net inventory),
- staleness / thin-book guards via `compute_quotes` returning cancel_all.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.strategies.mm.config import MMConfig


@dataclass
class QuoteResult:
    action: str  # "quote" | "cancel_all"
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    reservation: float | None = None
    reason: str | None = None


class InventorySkewMM:
    def __init__(self, config: MMConfig) -> None:
        self.cfg = config

    def compute_quotes(
        self,
        mid: float,
        q: float,
        sigma: float,
        t_hours: float,
        orderbook_depth: int = 99,
        book_age_sec: float = 0.0,
    ) -> QuoteResult:
        cfg = self.cfg

        # ── guards (plan C.1: staleness + thin book + kill zone) ──
        if t_hours < cfg.kill_zone_hours:
            return QuoteResult("cancel_all", reason="kill_zone")
        if abs(q) >= cfg.q_max:
            return QuoteResult("cancel_all", reason="inventory_max")
        if orderbook_depth < cfg.min_orderbook_depth:
            return QuoteResult("cancel_all", reason="thin_book")
        if book_age_sec > cfg.staleness_sec:
            return QuoteResult("cancel_all", reason="stale_book")

        t = t_hours / 24.0  # days

        # Reservation price — shifts against accumulated inventory (symmetric).
        r = mid - q * cfg.gamma * (sigma**2) * t

        # Optimal half-spread (Avellaneda–Stoikov).
        delta = cfg.gamma * (sigma**2) * t + (2.0 / cfg.gamma) * math.log(
            1.0 + cfg.gamma / cfg.kappa
        )

        # ── cost-based spread floor (plan C.1) ─────────────
        min_half_spread = cfg.fee_per_share + cfg.adverse_premium
        half = max(delta / 2.0, min_half_spread)

        bid = max(0.01, min(r - half, 0.98))
        ask = max(0.02, min(r + half, 0.99))
        if ask <= bid:
            ask = min(0.99, bid + 0.02)

        return QuoteResult(
            action="quote",
            bid=round(bid, 3),
            ask=round(ask, 3),
            spread=round(ask - bid, 3),
            reservation=round(r, 4),
        )

    def quotes_changed(
        self, prev_bid: float | None, prev_ask: float | None, new: QuoteResult
    ) -> bool:
        """Re-quote only if quotes moved beyond the configured threshold."""
        if new.action != "quote":
            return True
        if prev_bid is None or prev_ask is None:
            return True
        thr = self.cfg.requote_threshold
        return abs(new.bid - prev_bid) > thr or abs(new.ask - prev_ask) > thr
