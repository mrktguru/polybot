"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";

interface Market {
  market_id: string;
  title: string;
  mid: number;
  best_bid: number;
  best_ask: number;
  score: number;
  volume_24h: number;
  t_hours: number;
}

interface MarketsResponse {
  markets: Market[];
  total: number;
  error: string | null;
}

export default function MarketsPage() {
  const { data, error, isLoading } = useSWR<MarketsResponse>(
    "/api/markets",
    fetcher,
    { refreshInterval: 60000 },
  );

  if (error) return <div className="text-loss">Failed to load markets.</div>;
  if (isLoading || !data)
    return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">
        Markets ({data.markets.length} of {data.total})
      </h1>
      {data.markets.length === 0 && (
        <div className="text-slate-500">No markets found.</div>
      )}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-panel text-slate-400">
            <tr>
              <th className="p-2 text-left">Market</th>
              <th className="p-2 text-right">Score</th>
              <th className="p-2 text-right">Bid</th>
              <th className="p-2 text-right">Ask</th>
              <th className="p-2 text-right">Spread</th>
              <th className="p-2 text-right">Vol 24h</th>
              <th className="p-2 text-right">Hours</th>
            </tr>
          </thead>
          <tbody>
            {data.markets.map((m) => (
              <tr key={m.market_id} className="border-t border-border">
                <td className="p-2 font-mono text-xs">{m.market_id}</td>
                <td className="p-2 text-right">{m.score.toFixed(2)}</td>
                <td className="p-2 text-right">{m.best_bid.toFixed(3)}</td>
                <td className="p-2 text-right">{m.best_ask.toFixed(3)}</td>
                <td className="p-2 text-right">
                  {(m.best_ask - m.best_bid).toFixed(3)}
                </td>
                <td className="p-2 text-right">
                  ${m.volume_24h.toLocaleString()}
                </td>
                <td className="p-2 text-right">
                  {Math.round(m.t_hours / 24)}d
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
