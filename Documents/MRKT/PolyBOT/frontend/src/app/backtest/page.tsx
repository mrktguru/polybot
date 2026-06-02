"use client";

import { useState } from "react";
import { fetcher, post } from "@/lib/api";
import useSWR from "swr";

interface BacktestResult {
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

const strategies = [
  { value: "market_making", label: "Market Making" },
  { value: "cross_market_corr", label: "Cross-Market Correlation" },
  { value: "resolution_arb", label: "Resolution Arbitrage" },
  { value: "volatility_harvesting", label: "Volatility Harvesting" },
  { value: "whale_copying", label: "Whale Copying" },
  { value: "sentiment_divergence", label: "Sentiment Divergence" },
];

export default function BacktestPage() {
  const [strategy, setStrategy] = useState("market_making");
  const [capital, setCapital] = useState(1000);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);

  const runBacktest = async () => {
    setRunning(true);
    setResult(null);
    try {
      const res = await post("/api/backtest", {
        strategy,
        initial_capital: capital,
      });
      setResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Backtest</h1>

      <div className="flex gap-4">
        <select
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
          className="rounded border border-border bg-panel px-3 py-2 text-sm"
        >
          {strategies.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <input
          type="number"
          value={capital}
          onChange={(e) => setCapital(Number(e.target.value))}
          className="w-32 rounded border border-border bg-panel px-3 py-2 text-sm"
          placeholder="Capital"
        />
        <button
          onClick={runBacktest}
          disabled={running}
          className="rounded bg-accent px-4 py-2 text-sm font-semibold disabled:opacity-50"
        >
          {running ? "Running…" : "Run"}
        </button>
      </div>

      {result && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="End Equity" value={`$${result.end_equity.toFixed(2)}`} />
          <MetricCard label="Sharpe" value={result.sharpe.toFixed(2)} />
          <MetricCard label="Sortino" value={result.sortino.toFixed(2)} />
          <MetricCard label="Max DD" value={`${(result.max_drawdown * 100).toFixed(1)}%`} />
          <MetricCard label="Win Rate" value={`${(result.win_rate * 100).toFixed(0)}%`} />
          <MetricCard label="Profit Factor" value={result.profit_factor.toFixed(2)} />
          <MetricCard label="Signals" value={result.signals_executed.toString()} />
          <MetricCard label="Fees" value={`$${result.total_fees.toFixed(2)}`} />
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </div>
  );
}
