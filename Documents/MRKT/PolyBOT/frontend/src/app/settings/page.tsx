"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher, post } from "@/lib/api";

interface StrategyDetail {
  name: string;
  automation_level: string;
  min_confidence: float;
  max_auto_size: float;
  budget: float;
  enabled: boolean;
  positions_count: number;
  today_pnl: number;
}

const strategies = [
  "market_making",
  "cross_market_corr",
  "resolution_arb",
  "volatility_harvesting",
  "whale_copying",
  "sentiment_divergence",
];

export default function SettingsPage() {
  const [saving, setSaving] = useState(false);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Settings</h1>

      <div className="flex flex-col gap-4">
        <h2 className="text-sm font-semibold text-slate-300">Strategies</h2>
        {strategies.map((name) => (
          <StrategyCard key={name} name={name} />
        ))}
      </div>
    </div>
  );
}

function StrategyCard({ name }: { name: string }) {
  const { data, isLoading } = useSWR<StrategyDetail>(
    `/api/strategies/${name}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  if (isLoading || !data) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <div className="flex items-center justify-between">
        <span className="font-medium">{name.replace(/_/g, " ")}</span>
        <span
          className={`rounded px-2 py-0.5 text-xs uppercase ${
            data.automation_level === "full"
              ? "bg-accent/20 text-accent"
              : "bg-slate-600/30 text-slate-300"
          }`}
        >
          {data.automation_level}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-3 text-xs text-slate-400">
        <div>
          Budget<div className="text-slate-200">${data.budget.toFixed(0)}</div>
        </div>
        <div>
          Min Confidence<div className="text-slate-200">{data.min_confidence}</div>
        </div>
        <div>
          Max Auto Size<div className="text-slate-200">${data.max_auto_size}</div>
        </div>
        <div>
          Positions<div className="text-slate-200">{data.positions_count}</div>
        </div>
      </div>
    </div>
  );
}
