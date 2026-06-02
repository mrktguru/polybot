"""REST API routers for the admin dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import settings
from app.core.db import get_session
from app.core.redis import get_redis, publish_event
from app.models.trading import Position, SignalRecord, StrategyConfig
from app.models.market import MMPosition, PriceSnapshot
from app.risk.allocator import CapitalAllocator
from app.risk.engine import KEY_PAUSE_REASON, RiskEngine
from app.schemas.api import (
    HealthResponse,
    OverviewResponse,
    PauseRequest,
    PositionOut,
    SignalAction,
    SignalOut,
    StrategyConfigUpdate,
    StrategyDetail,
    StrategyStatus,
    WhaleAlert,
    MarketScanResult,
    BacktestRequest,
    BacktestResult,
)
from app.strategies.manager import StrategyManager

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        paper_trading=settings.paper_trading,
        version=__version__,
    )


@router.get("/overview", response_model=OverviewResponse, tags=["dashboard"])
def overview() -> OverviewResponse:
    budgets = CapitalAllocator(total_capital=settings.total_capital).allocate()
    paused = RiskEngine.is_paused()
    reason = get_redis().get(KEY_PAUSE_REASON)

    strategy_auto = {
        "market_making": "full",
        "resolution_arb": "full",
        "cross_market_corr": "full",
        "volatility_harvesting": "semi",
        "whale_copying": "semi",
        "sentiment_divergence": "semi",
    }

    strategies = [
        StrategyStatus(
            name=name,
            automation_level=strategy_auto.get(name, "semi"),
            enabled=True,
            budget=budget,
            today_pnl=0.0,
            open_positions=0,
        )
        for name, budget in budgets.items()
        if name != "reserve"
    ]

    return OverviewResponse(
        total_equity=settings.total_capital,
        today_pnl=0.0,
        open_exposure=0.0,
        daily_loss_limit=settings.daily_loss_limit,
        drawdown_pct=0.0,
        paused=paused,
        pause_reason=reason,
        strategies=strategies,
    )


# ── Signals ──────────────────────────────────────────────────
@router.get("/signals", response_model=list[SignalOut], tags=["signals"])
def list_signals(
    status: str = "pending", session: Session = Depends(get_session)
) -> list[SignalOut]:
    stmt = (
        select(SignalRecord)
        .where(SignalRecord.status == status)
        .order_by(SignalRecord.created_at.desc())
        .limit(200)
    )
    rows = session.execute(stmt).scalars().all()
    return [
        SignalOut(
            signal_id=r.signal_id,
            strategy=r.strategy,
            market_id=r.market_id,
            market_title=r.market_title,
            direction=r.direction,
            confidence=r.confidence,
            edge=r.edge,
            kelly_size=r.kelly_size,
            entry_price=r.entry_price,
            reasoning=r.reasoning,
            status=r.status,
            created_at=r.created_at,
            expires_at=r.expires_at,
        )
        for r in rows
    ]


@router.post("/signals/{signal_id}/approve", tags=["signals"])
def approve_signal(
    signal_id: str, action: SignalAction, session: Session = Depends(get_session)
) -> dict:
    rec = session.get(SignalRecord, signal_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="signal not found")
    if rec.status != "pending":
        raise HTTPException(status_code=409, detail=f"signal already {rec.status}")
    if action.edited_size is not None:
        rec.kelly_size = action.edited_size
    rec.status = "approved"
    publish_event("signal.approved", {"signal_id": signal_id})
    return {"signal_id": signal_id, "status": "approved"}


@router.post("/signals/{signal_id}/reject", tags=["signals"])
def reject_signal(signal_id: str, session: Session = Depends(get_session)) -> dict:
    rec = session.get(SignalRecord, signal_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="signal not found")
    rec.status = "rejected"
    publish_event("signal.rejected", {"signal_id": signal_id})
    return {"signal_id": signal_id, "status": "rejected"}


# ── Positions ───────────────────────────────────────────────
@router.get("/positions", response_model=list[PositionOut], tags=["positions"])
def list_positions(
    status: str | None = None, session: Session = Depends(get_session)
) -> list[PositionOut]:
    stmt = select(Position).order_by(Position.opened_at.desc()).limit(200)
    if status:
        stmt = stmt.where(Position.status == status)
    rows = session.execute(stmt).scalars().all()
    return [
        PositionOut(
            id=r.id,
            strategy=r.strategy,
            market_id=r.market_id,
            side=r.side,
            size=r.size,
            entry_price=r.entry_price,
            status=r.status,
            realized_pnl=r.realized_pnl,
            unrealized_pnl=r.unrealized_pnl,
            opened_at=r.opened_at,
        )
        for r in rows
    ]


# ── Strategy Details ────────────────────────────────────────
@router.get("/strategies/{name}", response_model=StrategyDetail, tags=["strategies"])
def get_strategy(name: str) -> StrategyDetail:
    mgr = StrategyManager(total_capital=settings.total_capital)
    strategy = mgr.strategies.get(name)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"strategy {name} not found")

    budget = mgr.budgets.get(name, 0.0)
    return StrategyDetail(
        name=strategy.name,
        automation_level=strategy.automation_level.value,
        min_confidence=strategy.min_confidence,
        max_auto_size=strategy.max_auto_size,
        budget=budget,
        enabled=True,
        positions_count=0,
        today_pnl=0.0,
    )


@router.post("/strategies/{name}/config", tags=["strategies"])
def update_strategy_config(
    name: str, update: StrategyConfigUpdate, session: Session = Depends(get_session)
) -> dict:
    config = StrategyConfig(
        strategy=name,
        config=update.params.model_dump(),
        active=True,
    )
    session.add(config)
    publish_event("config.updated", {"strategy": name})
    return {"strategy": name, "status": "updated"}


# ── Markets Scanner ─────────────────────────────────────────
@router.get("/markets", response_model=MarketScanResult, tags=["markets"])
def scan_markets() -> MarketScanResult:
    from app.data.gamma import fetch_mm_candidates
    from app.strategies.mm.selector import MarketSelector
    from app.strategies.mm.config import MMConfig

    try:
        candidates = fetch_mm_candidates()
    except Exception:
        return MarketScanResult(markets=[], error="failed to fetch")

    selector = MarketSelector(MMConfig())
    selected = selector.select(candidates)
    return MarketScanResult(markets=selected, total=len(candidates))


# ── Whales ──────────────────────────────────────────────────
@router.get("/whales", response_model=list[WhaleAlert], tags=["whales"])
def list_whales() -> list[WhaleAlert]:
    import json
    r = get_redis()
    raw = r.get("polybot.whale_alerts")
    if not raw:
        return []
    data = json.loads(raw)
    return [WhaleAlert(**item) for item in data]


# ── Backtest ────────────────────────────────────────────────
@router.post("/backtest", response_model=BacktestResult, tags=["backtest"])
def run_backtest(req: BacktestRequest) -> BacktestResult:
    from app.backtest.runner import EventDrivenBacktester, BacktestConfig
    from app.strategies.market_making import MarketMaking
    from app.strategies.mm.config import MMConfig

    bt_config = BacktestConfig(
        initial_capital=req.initial_capital or 1000.0,
        fee_per_trade=req.fee_per_trade or 0.0,
        slippage_bps=req.slippage_bps or 0.0,
        position_size_pct=req.position_size_pct or 0.02,
    )

    strategy = MarketMaking(
        budget=req.initial_capital or 1000.0,
        config=MMConfig(**req.params) if req.params else None,
    )

    tester = EventDrivenBacktester(bt_config)
    events = req.events or []
    result = tester.run(strategy, events)

    return BacktestResult(
        strategy_name=result.strategy_name,
        start_equity=result.start_equity,
        end_equity=result.end_equity,
        max_drawdown=result.max_drawdown,
        sharpe=result.sharpe,
        sortino=result.sortino,
        win_rate=result.win_rate,
        profit_factor=result.profit_factor,
        total_fees=result.total_fees,
        signals_executed=result.signals_executed,
        execution_time_ms=result.execution_time_ms,
    )


# ── Risk ────────────────────────────────────────────────────
@router.post("/risk/pause", tags=["risk"])
def pause(req: PauseRequest) -> dict:
    RiskEngine.pause(req.reason)
    return {"paused": True, "reason": req.reason}


@router.post("/risk/resume", tags=["risk"])
def resume() -> dict:
    RiskEngine.resume()
    return {"paused": False}
