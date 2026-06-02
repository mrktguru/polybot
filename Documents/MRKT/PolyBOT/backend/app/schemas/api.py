"""Pydantic API schemas (shared contract with the Next.js frontend via OpenAPI)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    environment: str
    paper_trading: bool
    version: str


class StrategyStatus(BaseModel):
    name: str
    automation_level: str
    enabled: bool
    budget: float
    today_pnl: float
    open_positions: int


class OverviewResponse(BaseModel):
    total_equity: float
    today_pnl: float
    open_exposure: float
    daily_loss_limit: float
    drawdown_pct: float
    paused: bool
    pause_reason: str | None
    strategies: list[StrategyStatus]


class SignalOut(BaseModel):
    signal_id: str
    strategy: str
    market_id: str
    market_title: str
    direction: str
    confidence: float
    edge: float
    kelly_size: float
    entry_price: float
    reasoning: str
    status: str
    created_at: datetime | None = None
    expires_at: datetime | None = None


class SignalAction(BaseModel):
    edited_size: float | None = None  # allow editing size before approve (plan D.4)


class PauseRequest(BaseModel):
    reason: str = "manual kill switch"


class PositionOut(BaseModel):
    id: int
    strategy: str
    market_id: str
    side: str
    size: float
    entry_price: float
    status: str
    realized_pnl: float
    unrealized_pnl: float
    opened_at: datetime | None = None


class StrategyDetail(BaseModel):
    name: str
    automation_level: str
    min_confidence: float
    max_auto_size: float
    budget: float
    enabled: bool
    positions_count: int
    today_pnl: float


class StrategyConfigUpdate(BaseModel):
    params: dict


class MarketScanResult(BaseModel):
    markets: list[dict]
    total: int = 0
    error: str | None = None


class WhaleAlert(BaseModel):
    wallet: str
    market_id: str
    market_title: str
    side: str
    usd_value: float
    metrics: dict
    is_smart_money: bool
    copy_size: float


class BacktestRequest(BaseModel):
    strategy: str = "market_making"
    initial_capital: float | None = None
    fee_per_trade: float | None = None
    slippage_bps: float | None = None
    position_size_pct: float | None = None
    params: dict | None = None
    events: list[dict] | None = None


class BacktestResult(BaseModel):
    strategy_name: str
    start_equity: float
    end_equity: float
    max_drawdown: float
    sharpe: float
    sortino: float
    win_rate: float
    profit_factor: float
    total_fees: float
    signals_executed: int
    execution_time_ms: int
