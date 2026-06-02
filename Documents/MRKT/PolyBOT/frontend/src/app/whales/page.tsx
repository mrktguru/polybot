"use client";

import useSWR from "swr";
import { fetcher, type WhaleAlert } from "@/lib/api";

export default function WhalesPage() {
  const { data, error, isLoading } = useSWR<WhaleAlert[]>(
    "/api/whales",
    fetcher,
    { refreshInterval: 10000 },
  );

  if (error) return <div className="text-loss">Failed to load whale alerts.</div>;
  if (isLoading || !data)
    return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Whale Alerts</h1>
      {data.length === 0 && (
        <div className="text-slate-500">No whale alerts.</div>
      )}
      <div className="grid gap-3">
        {data.map((w, i) => (
          <div key={i} className="rounded-lg border border-border bg-panel p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{w.market_title}</span>
              <span
                className={`rounded px-2 py-0.5 text-xs ${
                  w.is_smart_money
                    ? "bg-profit/20 text-profit"
                    : "bg-slate-600/30 text-slate-300"
                }`}
              >
                {w.is_smart_money ? "✅ Smart" : "❓ Unknown"}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-4 gap-2 text-xs text-slate-400">
              <div>
                Wallet<div className="font-mono text-slate-200">{w.wallet.slice(0, 10)}...</div>
              </div>
              <div>
                Side<div className="text-slate-200">{w.side}</div>
              </div>
              <div>
                Size<div className="text-slate-200">${w.usd_value.toLocaleString()}</div>
              </div>
              <div>
                Copy<div className="text-profit">${w.copy_size.toFixed(0)}</div>
              </div>
            </div>
            {w.metrics && (
              <div className="mt-2 text-xs text-slate-500">
                Win rate: {(w.metrics.win_rate * 100).toFixed(0)}% |
                Total bets: {w.metrics.total_bets} |
                Calibration: {(w.metrics.calibration * 100).toFixed(0)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
