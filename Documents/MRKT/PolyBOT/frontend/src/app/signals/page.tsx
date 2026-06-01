"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher, post, type SignalOut } from "@/lib/api";

function SignalCard({ s, onDone }: { s: SignalOut; onDone: () => void }) {
  const [size, setSize] = useState(s.kelly_size);
  const [busy, setBusy] = useState(false);

  const act = async (action: "approve" | "reject") => {
    setBusy(true);
    try {
      await post(`/api/signals/${s.signal_id}/${action}`, {
        edited_size: action === "approve" ? size : undefined,
      });
      onDone();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{s.market_title}</span>
        <span className="rounded bg-accent/20 px-2 py-0.5 text-[10px] uppercase text-accent">
          {s.strategy.replace(/_/g, " ")}
        </span>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-400">
        <div>
          Direction<div className="text-slate-100">{s.direction}</div>
        </div>
        <div>
          Confidence
          <div className="text-slate-100">{(s.confidence * 100).toFixed(0)}%</div>
        </div>
        <div>
          Edge<div className="text-slate-100">{(s.edge * 100).toFixed(1)}%</div>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-400">{s.reasoning}</p>
      <div className="mt-3 flex items-center gap-2">
        <label className="text-xs text-slate-400">Size $</label>
        <input
          type="number"
          value={size}
          onChange={(e) => setSize(parseFloat(e.target.value))}
          className="w-24 rounded border border-border bg-bg px-2 py-1 text-sm"
        />
        <button
          disabled={busy}
          onClick={() => act("approve")}
          className="rounded bg-profit/20 px-3 py-1 text-sm text-profit hover:bg-profit/30 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={busy}
          onClick={() => act("reject")}
          className="rounded bg-loss/20 px-3 py-1 text-sm text-loss hover:bg-loss/30 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

export default function SignalsPage() {
  const { data, error, isLoading, mutate } = useSWR<SignalOut[]>(
    "/api/signals?status=pending",
    fetcher,
    { refreshInterval: 4000 },
  );

  if (error) return <div className="text-loss">Failed to load signals.</div>;
  if (isLoading || !data)
    return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Pending signals</h1>
      {data.length === 0 && (
        <div className="text-slate-500">No pending signals.</div>
      )}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {data.map((s) => (
          <SignalCard key={s.signal_id} s={s} onDone={() => mutate()} />
        ))}
      </div>
    </div>
  );
}
