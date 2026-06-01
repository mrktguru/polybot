"use client";

import useSWR from "swr";
import { fetcher, type Overview } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { KillSwitch } from "@/components/KillSwitch";
import { EventFeed } from "@/components/EventFeed";
import { StrategyGrid } from "@/components/StrategyGrid";

export default function OverviewPage() {
  const { data, error, isLoading, mutate } = useSWR<Overview>(
    "/api/overview",
    fetcher,
    { refreshInterval: 5000 },
  );

  if (error)
    return (
      <div className="text-loss">Failed to load overview. Is the API up?</div>
    );
  if (isLoading || !data) return <div className="text-slate-400">Loading…</div>;

  const lossPct =
    data.daily_loss_limit > 0
      ? Math.min(100, (Math.max(0, -data.today_pnl) / data.daily_loss_limit) * 100)
      : 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Overview</h1>
        <KillSwitch
          paused={data.paused}
          reason={data.pause_reason}
          onChange={() => mutate()}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard
          label="Total Equity"
          value={`$${data.total_equity.toFixed(2)}`}
        />
        <KpiCard
          label="Today PnL"
          value={`$${data.today_pnl.toFixed(2)}`}
          tone={data.today_pnl >= 0 ? "profit" : "loss"}
        />
        <KpiCard
          label="Open Exposure"
          value={`$${data.open_exposure.toFixed(2)}`}
        />
        <KpiCard
          label="Daily Loss"
          value={`${lossPct.toFixed(0)}%`}
          sub={`limit $${data.daily_loss_limit.toFixed(0)}`}
          tone={lossPct > 80 ? "loss" : "neutral"}
        />
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-300">
          Strategies
        </h2>
        <StrategyGrid strategies={data.strategies} />
      </section>

      <EventFeed />
    </div>
  );
}
