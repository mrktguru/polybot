# PolyBOT — Polymarket Algorithmic Trading Bot

Implementation of the strategy spec in
[`polymarket-bot-strategies.md`](./polymarket-bot-strategies.md).

This repository contains **Phase 0 (foundation) + Phase 1 core** from the
implementation plan: the backend skeleton, execution/risk layers, the
Market Making strategy with the C.1 improvements, the Celery schedule, the
admin API, and a Next.js admin dashboard. Later phases (other 5 strategies,
backtester runner, analytics) plug into the same interfaces.

## Architecture

```
backend/   FastAPI + Celery + SQLAlchemy + Redis
frontend/  Next.js 14 + React + Tailwind admin dashboard
infra/     docker-compose (Postgres/TimescaleDB, Redis, api, worker, beat, frontend)
```

### Key design decisions (improvements over the spec)
- **Single execution layer** (`app/execution`): strategies return `Signal`s;
  the `OrderRouter` performs idempotency + audit and routes to the
  `PaperTradingEngine` (MVP) or the real CLOB.
- **Centralized Risk Engine** (`app/risk`): pre-trade caps (per-market /
  per-correlation-tag), fractional Kelly, and Redis-backed circuit breakers.
- **Dynamic Capital Allocator** with hard per-strategy bounds.
- **Unified position state machine** + persisted signal queue for the
  semi-auto approve flow.
- **Market Making C.1 fixes**: realized (EWMA) volatility, cost/adverse-
  selection spread floor, symmetric inventory skew, staleness & thin-book
  guards, re-quote threshold, maker-rewards bonus in selection scoring.

## Quick start (Docker)

```bash
cp .env.example .env        # fill in keys; PAPER_TRADING=true for the MVP
cd infra && docker compose up --build
# API   -> http://localhost:8000/docs
# Admin -> http://localhost:3000
```

## Local backend development

```bash
cd backend
uv venv --python 3.12 .venv          # or python3.12 -m venv .venv
uv pip install --python .venv -e ".[dev]"
.venv/bin/pytest -q                  # run tests
.venv/bin/ruff check app tests       # lint
.venv/bin/uvicorn app.main:app --reload
```

Workers:
```bash
celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO
celery -A app.tasks.celery_app:celery_app beat   --loglevel=INFO
```

## Status

| Component | State |
|-----------|-------|
| Core config / logging / db / redis | ✅ |
| BaseStrategy + Signal (extended)   | ✅ |
| Execution (router, paper, CLOB)    | ✅ |
| Risk (kelly, engine, allocator)    | ✅ |
| Market Making (selector + quoting) | ✅ |
| StrategyManager                    | ✅ |
| Celery tasks + beat                | ✅ (MM concrete, others stubbed) |
| Admin API + WebSocket              | ✅ |
| Next.js admin (overview/signals/risk) | ✅ |
| Backtest metrics                   | ✅ (runner = Phase 4) |
| Strategies 2–6                     | ⏳ interfaces ready, logic = later phases |

Tests: `27 passed`. Lint: clean.
