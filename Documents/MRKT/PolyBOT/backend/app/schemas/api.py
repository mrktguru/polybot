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
