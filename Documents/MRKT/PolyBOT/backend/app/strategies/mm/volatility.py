"""Realized volatility estimation for MM (plan C.1).

Computes EWMA realized volatility from a series of mid prices/timestamps,
annualized to the per-day scale used by the Avellaneda–Stoikov quoting.
"""

from __future__ import annotations

import math


def realized_sigma(mids: list[float], halflife: int = 20) -> float:
    """EWMA volatility of log-returns over a mid-price series.

    Returns a per-snapshot sigma; callers scale by horizon T. Falls back to
    a small floor when insufficient data so quoting stays conservative.
    """
    if len(mids) < 3:
        return 0.02  # conservative default

    rets: list[float] = []
    for prev, cur in zip(mids, mids[1:], strict=False):
        if prev > 0 and cur > 0:
            rets.append(math.log(cur / prev))
    if not rets:
        return 0.02

    alpha = 1.0 - math.exp(math.log(0.5) / max(1, halflife))
    ewma_var = rets[0] ** 2
    for r in rets[1:]:
        ewma_var = alpha * (r**2) + (1 - alpha) * ewma_var

    sigma = math.sqrt(max(ewma_var, 1e-8))
    # Clamp to a sensible band for prediction-market prices.
    return min(max(sigma, 0.005), 0.30)
