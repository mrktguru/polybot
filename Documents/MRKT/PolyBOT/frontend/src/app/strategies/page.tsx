"use client";

import useSWR from "swr";
import { fetcher, type Overview } from "@/lib/api";
import { StrategyGrid } from "@/components/StrategyGrid";

export default function StrategiesPage() {
  const { data, error, isLoading } = useSWR<Overview>(
    "/api/overview",
    fetcher,
    { refreshInterval: 5000 },
  );

  if (error) return <div className="text-loss">Failed to load.</div>;
  if (isLoading || !data) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Strategies</h1>
      <StrategyGrid strategies={data.strategies} />
    </div>
  );
}
