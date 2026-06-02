export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const fetcher = async (path: string) => {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
};

export async function post(path: string, body?: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

// ── Types mirrored from backend OpenAPI (plan D.7) ──────────
export interface StrategyStatus {
  name: string;
  automation_level: string;
  enabled: boolean;
  budget: number;
  today_pnl: number;
  open_positions: number;
}

export interface Overview {
  total_equity: number;
  today_pnl: number;
  open_exposure: number;
  daily_loss_limit: number;
  drawdown_pct: number;
  paused: boolean;
  pause_reason: string | null;
  strategies: StrategyStatus[];
}

export interface SignalOut {
  signal_id: string;
  strategy: string;
  market_id: string;
  market_title: string;
  direction: string;
  confidence: number;
  edge: number;
  kelly_size: number;
  entry_price: number;
  reasoning: string;
  status: string;
}

export interface PositionOut {
  id: number;
  strategy: string;
  market_id: string;
  side: string;
  size: number;
  entry_price: number;
  status: string;
  realized_pnl: number;
  unrealized_pnl: number;
}

export interface WhaleAlert {
  wallet: string;
  market_id: string;
  market_title: string;
  side: string;
  usd_value: number;
  metrics: Record<string, unknown>;
  is_smart_money: boolean;
  copy_size: number;
}

export interface BacktestResult {
  strategy_name: string;
  start_equity: number;
  end_equity: number;
  max_drawdown: number;
  sharpe: number;
  sortino: number;
  win_rate: number;
  profit_factor: number;
  total_fees: number;
  signals_executed: number;
  execution_time_ms: number;
}
