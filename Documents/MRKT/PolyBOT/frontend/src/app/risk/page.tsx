"use client";

import useSWR from "swr";
import { fetcher, type Overview } from "@/lib/api";
import { KillSwitch } from "@/components/KillSwitch";
import { KpiCard } from "@/components/KpiCard";

export default function RiskPage() {
  const { data, error, isLoading, mutate } = useSWR<Overview>(
    "/api/overview",
    fetcher,
    { refreshInterval: 5000 },
  );

  if (error) return <div className="text-loss">Failed to load.</div>;
  if (isLoading || !data) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Risk</h1>
        <KillSwitch
          paused={data.paused}
          reason={data.pause_reason}
          onChange={() => mutate()}
        />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <KpiCard
          label="Drawdown"
          value={`${(data.drawdown_pct * 100).toFixed(1)}%`}
          tone={data.drawdown_pct > 0.1 ? "loss" : "neutral"}
        />
        <KpiCard
          label="Daily Loss Limit"
          value={`$${data.daily_loss_limit.toFixed(0)}`}
        />
        <KpiCard
          label="State"
          value={data.paused ? "PAUSED" : "ACTIVE"}
          tone={data.paused ? "loss" : "profit"}
        />
      </div>
    </div>
  );
}
