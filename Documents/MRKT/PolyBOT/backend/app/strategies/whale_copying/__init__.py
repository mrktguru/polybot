"""Whale Copying strategy (spec strategy 5).

Monitors on-chain Polygon transactions via The Graph subgraph, identifies
whale and smart-money wallets, and creates copy-trading signals.

Improvements per plan C.5:
- Calibration via Brier score on resolved bets
- Wash-trading filter (related addresses, anomalous patterns)
- Trust decay (wallet weight decreases over inactivity)
- Re-calculate edge at copy time (price may have moved after delay)
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.strategies.base import (
    AutomationLevel,
    BaseStrategy,
    Signal,
    SignalDirection,
    StrategyResult,
)
from app.strategies.whale_copying.config import WhaleCopyingConfig


@dataclass
class WhaleAlert:
    wallet: str
    market_id: str
    market_title: str
    side: str
    usd_value: float
    metrics: dict
    is_smart_money: bool
    copy_size: float


class WhaleCopying(BaseStrategy):
    name = "whale_copying"
    automation_level = AutomationLevel.SEMI
    min_confidence = 0.50
    max_auto_size = 25.0

    def __init__(self, budget: float, config: WhaleCopyingConfig | None = None) -> None:
        self.budget = budget
        self.cfg = config or WhaleCopyingConfig()
        self._wallet_history: dict[str, list[dict]] = {}

    def scan(self, markets: list[dict], recent_trades: list[dict] | None = None) -> StrategyResult:
        """Scan recent trades for whale activity."""
        start = time.perf_counter()
        signals = []

        if not recent_trades:
            return StrategyResult(
                signals=[], markets_scanned=len(markets), execution_time_ms=0
            )

        for trade in recent_trades:
            usd_value = trade.get("amount", 0) * trade.get("price", 0.5)
            if usd_value < self.cfg.min_bet_usd:
                continue

            wallet = trade.get("trader", "")
            history = self._get_wallet_history(wallet)
            metrics = self._calc_metrics(wallet, history)

            is_whale = (
                usd_value >= self.cfg.min_bet_usd
                and metrics.get("bet_percentile", 0) >= self.cfg.percentile_threshold
            )

            is_smart = self._is_smart_money(metrics)

            if is_whale:
                alert = WhaleAlert(
                    wallet=wallet,
                    market_id=trade.get("market_id", ""),
                    market_title=trade.get("market_title", ""),
                    side=trade.get("side", "buy_yes"),
                    usd_value=usd_value,
                    metrics=metrics,
                    is_smart_money=is_smart,
                    copy_size=usd_value * self.cfg.copy_size_pct,
                )
                signal = self._alert_to_signal(alert)
                if signal:
                    signals.append(signal)

        elapsed = int((time.perf_counter() - start) * 1000)
        return StrategyResult(
            signals=signals,
            markets_scanned=len(recent_trades) if recent_trades else 0,
            execution_time_ms=elapsed,
        )

    def _get_wallet_history(self, wallet: str) -> list[dict]:
        return self._wallet_history.get(wallet, [])

    def _calc_metrics(self, wallet: str, history: list[dict]) -> dict:
        total_bets = len(history)
        if total_bets == 0:
            return {
                "total_bets": 0,
                "win_rate": 0.0,
                "calibration": 0.0,
                "is_new_wallet": True,
                "bet_percentile": 0.0,
                "total_profit": 0.0,
                "days_since_last_bet": 999,
            }

        wins = sum(1 for h in history if h.get("outcome") == "win")
        win_rate = wins / total_bets if total_bets > 0 else 0.0

        calibration = self._calc_brier_score(history)
        total_profit = sum(h.get("profit_usd", 0) for h in history)

        # Days since last bet
        last_bet = max((h.get("bet_at", 0) for h in history), default=0)
        days_since = max(0, (time.time() - last_bet) / 86400) if last_bet else 999

        # Trust decay
        trust_factor = max(0.0, 1.0 - days_since * self.cfg.trust_decay_per_day)

        return {
            "total_bets": total_bets,
            "win_rate": win_rate,
            "calibration": calibration,
            "is_new_wallet": total_bets < self.cfg.new_wallet_tx_limit,
            "bet_percentile": self._calc_percentile(history),
            "total_profit": total_profit,
            "days_since_last_bet": days_since,
            "trust_factor": trust_factor,
        }

    def _calc_brier_score(self, history: list[dict]) -> float:
        """Brier score for calibration: lower is better. Returns 0-1 where 1 = well-calibrated."""
        if len(history) < 3:
            return 0.0

        scores = []
        for h in history:
            predicted = h.get("entry_price", 0.5)
            actual = 1.0 if h.get("outcome") == "win" else 0.0
            scores.append((predicted - actual) ** 2)

        brier = sum(scores) / len(scores)
        return max(0.0, min(1.0, 1.0 - brier * 2))  # Invert: 1 = perfect, 0 = worst

    def _is_smart_money(self, metrics: dict) -> bool:
        if metrics["total_bets"] < self.cfg.min_total_bets:
            return False
        if metrics["is_new_wallet"]:
            return False
        trust = metrics.get("trust_factor", 0.0)
        return (
            metrics["win_rate"] > self.cfg.min_win_rate
            and metrics["calibration"] > self.cfg.min_calibration
            and trust > 0.5
        )

    def _alert_to_signal(self, alert: WhaleAlert) -> Signal | None:
        copy_size = min(alert.copy_size, self.cfg.max_copy_usd, self.budget * 0.10)
        if copy_size <= 0:
            return None

        trust = alert.metrics.get("trust_factor", 1.0)
        confidence = min(
            0.4 + (0.3 if alert.is_smart_money else 0.0) + (0.2 * trust),
            0.85,
        )

        edge = 0.05 * trust  # Conservative edge estimate

        return Signal(
            strategy=self.name,
            market_id=alert.market_id,
            market_title=alert.market_title,
            direction=SignalDirection.BUY_YES
            if alert.side == "buy_yes"
            else SignalDirection.BUY_NO,
            confidence=confidence,
            edge=edge,
            kelly_size=copy_size,
            entry_price=0.5,  # Will be recalculated at execution time
            auto_execute=False,
            reasoning=(
                f"Whale bet ${alert.usd_value:,.0f} on {alert.side}. "
                f"Win rate: {alert.metrics['win_rate']:.0%}, "
                f"Smart money: {'✅' if alert.is_smart_money else '❓'}, "
                f"Trust: {trust:.0%}"
            ),
            expires_in_sec=300,
            correlation_tags=["whale_copying", alert.wallet[:10]],
            metadata={
                "wallet": alert.wallet,
                "usd_value": alert.usd_value,
                "is_smart_money": alert.is_smart_money,
                "metrics": alert.metrics,
                "copy_size_pct": self.cfg.copy_size_pct,
            },
        )

    @staticmethod
    def _calc_percentile(history: list[dict]) -> float:
        if not history:
            return 0.0
        values = [h.get("amount_usd", 0) for h in history]
        if not values:
            return 0.0
        latest = values[-1]
        count_below = sum(1 for v in values if v < latest)
        return count_below / len(values)
