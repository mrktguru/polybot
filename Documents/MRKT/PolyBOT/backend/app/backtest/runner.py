"""Event-driven backtest runner (plan C.8).

Replays historical data through a strategy and collects performance metrics.
Works with the same BaseStrategy interface used in live trading, so the
exact same strategy code runs in both backtest and production.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.backtest.metrics import max_drawdown, profit_factor, sharpe, sortino, win_rate
from app.strategies.base import BaseStrategy


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    equity_curve: list[float] = field(default_factory=list)
    pnls: list[float] = field(default_factory=list)
    signals_generated: int = 0
    signals_executed: int = 0
    total_fees: float = 0.0
    start_equity: float = 0.0
    end_equity: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    execution_time_ms: int = 0
    strategy_name: str = ""


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    initial_capital: float = 1000.0
    fee_per_trade: float = 0.0
    slippage_bps: float = 0.0  # Basis points
    position_size_pct: float = 0.02  # Max 2% per trade
    max_positions: int = 10


class EventDrivenBacktester:
    """Event-driven backtest runner.

    Processes historical price events through a strategy and simulates
    execution with configurable fees and slippage.
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.cfg = config or BacktestConfig()

    def run(
        self,
        strategy: BaseStrategy,
        historical_events: list[dict],
    ) -> BacktestResult:
        """Run backtest on historical events.

        Each event is a dict with:
          - timestamp: float (unix timestamp)
          - market_id: str
          - mid_price: float
          - price_history: list[float] (recent prices for sigma calculation)
          - volume: float (optional)
          - t_hours: float (optional, time to resolution)
        """
        start_time = time.perf_counter()
        equity = self.cfg.initial_capital
        equity_curve: list[float] = [equity]
        pnls: list[float] = []
        positions: dict[str, dict] = {}  # market_id -> position
        signals_executed = 0
        total_fees = 0.0

        # Group events by time window for strategy scan
        events_by_window: dict[str, list[dict]] = {}
        for event in historical_events:
            # Bucket by hour
            ts = event.get("timestamp", 0)
            window = str(int(ts // 3600))
            events_by_window.setdefault(window, []).append(event)

        for _window, events in sorted(events_by_window.items()):
            # Prepare market data for strategy scan
            market_data = []
            for event in events:
                market_data.append({
                    "market_id": event["market_id"],
                    "title": event.get("title", ""),
                    "mid": event["mid_price"],
                    "best_bid": event["mid_price"] * 0.99,
                    "best_ask": event["mid_price"] * 1.01,
                    "volume_24h": event.get("volume", 0),
                    "t_hours": event.get("t_hours", 240),
                    "price_history": event.get("price_history", [event["mid_price"]]),
                })

            # Run strategy scan
            result = strategy.scan(market_data)

            # Process signals
            for signal in result.signals:
                max_size = min(
                    signal.kelly_size,
                    equity * self.cfg.position_size_pct,
                    equity * 0.10,  # Never more than 10% of equity
                )

                if max_size > 0 and len(positions) < self.cfg.max_positions:
                    # Simulate execution
                    fill_price = self._apply_slippage(signal.entry_price)
                    fee = max_size * self.cfg.fee_per_trade

                    positions[signal.market_id] = {
                        "entry_price": fill_price,
                        "size": max_size,
                        "signal": signal,
                    }
                    signals_executed += 1
                    total_fees += fee

            # Update positions (simulate PnL)
            window_pnl = 0.0
            for market_id, pos in list(positions.items()):
                # Find current price for this market in events
                for event in events:
                    if event["market_id"] == market_id:
                        current_price = event["mid_price"]
                        entry_price = pos["entry_price"]
                        direction = pos["signal"].direction.value

                        # Calculate PnL
                        if direction == "buy_yes":
                            pnl = (current_price - entry_price) * pos["size"]
                        else:  # buy_no
                            pnl = ((1 - current_price) - (1 - entry_price)) * pos["size"]

                        pos["unrealized_pnl"] = pnl
                        window_pnl += pnl

            equity += window_pnl
            equity_curve.append(equity)
            if window_pnl != 0:
                pnls.append(window_pnl)

            # Close expired positions (simplified: close after some time)
            for _market_id in list(positions.keys()):
                # In real backtest, check resolution
                pass

        # Calculate metrics
        elapsed = int((time.perf_counter() - start_time) * 1000)

        return BacktestResult(
            equity_curve=equity_curve,
            pnls=pnls,
            signals_generated=sum(
                len(strategy.scan([e])) for e in historical_events[:100]
            ),
            signals_executed=signals_executed,
            total_fees=round(total_fees, 2),
            start_equity=self.cfg.initial_capital,
            end_equity=round(equity, 2),
            max_drawdown=round(max_drawdown(equity_curve), 4),
            sharpe=round(sharpe(pnls), 4),
            sortino=round(sortino(pnls), 4),
            win_rate=round(win_rate(pnls), 4),
            profit_factor=round(profit_factor(pnls), 4),
            execution_time_ms=elapsed,
            strategy_name=strategy.name,
        )

    def _apply_slippage(self, price: float) -> float:
        """Apply slippage to simulated fill price."""
        slip = self.cfg.slippage_bps / 10000
        return round(price * (1 + slip), 4)

    def run_parameter_sweep(
        self,
        strategy_factory,
        historical_events: list[dict],
        param_grid: dict[str, list],
    ) -> list[BacktestResult]:
        """Run backtest with multiple parameter combinations.

        strategy_factory: callable that takes config kwargs and returns a strategy
        param_grid: dict of param_name -> list of values to try
        """
        from itertools import product

        param_names = list(param_grid.keys())
        param_values = list(product(*param_grid.values()))

        results = []
        for values in param_values:
            config = dict(zip(param_names, values, strict=True))
            strategy = strategy_factory(**config)
            result = self.run(strategy, historical_events)
            result.strategy_name = f"{strategy.name} - {config}"
            results.append(result)

        # Sort by Sharpe (descending)
        results.sort(key=lambda r: r.sharpe, reverse=True)
        return results
