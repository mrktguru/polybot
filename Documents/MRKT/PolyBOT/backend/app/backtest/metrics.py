"""Backtest performance metrics (plan C.8).

Pure functions over an equity/returns series; used by the backtester and
the /backtest admin panel. The event-driven runner itself lands in Phase 4.
"""

from __future__ import annotations

import math


def sharpe(returns: list[float], periods_per_year: int = 365) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(periods_per_year)


def sortino(returns: list[float], periods_per_year: int = 365) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    downside = [min(0.0, r) for r in returns]
    dvar = sum(d**2 for d in downside) / len(returns)
    dstd = math.sqrt(dvar)
    if dstd == 0:
        return 0.0
    return (mean / dstd) * math.sqrt(periods_per_year)


def max_drawdown(equity: list[float]) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction."""
    if not equity:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)
    return max_dd


def win_rate(pnls: list[float]) -> float:
    if not pnls:
        return 0.0
    wins = sum(1 for p in pnls if p > 0)
    return wins / len(pnls)


def profit_factor(pnls: list[float]) -> float:
    gains = sum(p for p in pnls if p > 0)
    losses = -sum(p for p in pnls if p < 0)
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses
