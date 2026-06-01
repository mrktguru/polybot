"""Kelly criterion sizing (plan C.7: fractional Kelly + caps)."""

from __future__ import annotations


def kelly_fraction(p: float, price: float) -> float:
    """Full Kelly fraction for a binary YES/NO bet at `price` (0..1).

    For a contract bought at `price` that pays 1 on win, 0 on loss:
      net odds b = (1 - price) / price
      f* = (b * p - (1 - p)) / b = p - (1 - p) / b
    Returns a fraction of bankroll in [0, 1]; negative edge -> 0.
    """
    price = min(max(price, 1e-6), 1 - 1e-6)
    p = min(max(p, 0.0), 1.0)
    b = (1.0 - price) / price
    if b <= 0:
        return 0.0
    f = (b * p - (1.0 - p)) / b
    return max(0.0, min(f, 1.0))


def kelly_size(
    p: float,
    price: float,
    capital: float,
    fraction: float = 0.33,
    max_pct: float = 0.20,
) -> float:
    """Dollar position size with fractional Kelly and a per-position cap.

    - `fraction`: fraction of full Kelly to use (default 1/3 — plan C.7).
    - `max_pct`: hard cap as a share of `capital`.
    """
    f = kelly_fraction(p, price) * fraction
    size = f * capital
    return round(min(size, capital * max_pct), 2)
