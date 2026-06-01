"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.api.websocket import ws_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(
        "startup",
        environment=settings.environment,
        paper_trading=settings.paper_trading,
        version=__version__,
    )
    yield
    log.info("shutdown")


app = FastAPI(
    title="PolyBOT API",
    version=__version__,
    description="Polymarket algorithmic trading bot — admin & control API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(ws_router)


@app.get("/")
def root() -> dict:
    return {"name": "PolyBOT", "version": __version__, "docs": "/docs"}
