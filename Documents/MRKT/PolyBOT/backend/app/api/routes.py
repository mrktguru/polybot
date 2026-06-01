"""REST API routers for the admin dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import settings
from app.core.db import get_session
from app.core.redis import get_redis, publish_event
from app.models.trading import SignalRecord
from app.risk.allocator import CapitalAllocator
from app.risk.engine import KEY_PAUSE_REASON, RiskEngine
from app.schemas.api import (
    HealthResponse,
    OverviewResponse,
    PauseRequest,
    SignalAction,
    SignalOut,
    StrategyStatus,
)

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

    strategies = [
        StrategyStatus(
            name=name,
            automation_level="full" if name == "market_making" else "semi",
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


@router.get("/signals", response_model=list[SignalOut], tags=["signals"])
def list_signals(
    status: str = "pending", session: Session = Depends(get_session)
) -> list[SignalOut]:
    stmt = select(SignalRecord).where(SignalRecord.status == status).limit(200)
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


@router.post("/risk/pause", tags=["risk"])
def pause(req: PauseRequest) -> dict:
    RiskEngine.pause(req.reason)
    return {"paused": True, "reason": req.reason}


@router.post("/risk/resume", tags=["risk"])
def resume() -> dict:
    RiskEngine.resume()
    return {"paused": False}
