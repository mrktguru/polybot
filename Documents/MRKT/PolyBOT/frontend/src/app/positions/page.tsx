"use client";

import useSWR from "swr";
import { fetcher, type PositionOut } from "@/lib/api";

export default function PositionsPage() {
  const { data, error, isLoading } = useSWR<PositionOut[]>(
    "/api/positions",
    fetcher,
    { refreshInterval: 5000 },
  );

  if (error) return <div className="text-loss">Failed to load positions.</div>;
  if (isLoading || !data)
    return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Positions</h1>
      {data.length === 0 && (
        <div className="text-slate-500">No positions.</div>
      )}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-panel text-slate-400">
            <tr>
              <th className="p-2 text-left">Strategy</th>
              <th className="p-2 text-left">Market</th>
              <th className="p-2 text-left">Side</th>
              <th className="p-2 text-right">Size</th>
              <th className="p-2 text-right">Entry</th>
              <th className="p-2 text-right">PnL</th>
              <th className="p-2 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.id} className="border-t border-border">
                <td className="p-2">{p.strategy.replace(/_/g, " ")}</td>
                <td className="p-2 font-mono text-xs">{p.market_id}</td>
                <td className="p-2">{p.side}</td>
                <td className="p-2 text-right">${p.size.toFixed(2)}</td>
                <td className="p-2 text-right">{p.entry_price.toFixed(3)}</td>
                <td
                  className={`p-2 text-right ${
                    p.realized_pnl >= 0 ? "text-profit" : "text-loss"
                  }`}
                >
                  ${p.realized_pnl.toFixed(2)}
                </td>
                <td className="p-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs ${
                      p.status === "open"
                        ? "bg-accent/20 text-accent"
                        : "bg-slate-600/30 text-slate-300"
                    }`}
                  >
                    {p.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
