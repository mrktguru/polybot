"use client";

import { useEvents } from "@/lib/useEvents";

export function EventFeed() {
  const events = useEvents();

  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <div className="mb-3 text-sm font-semibold text-slate-300">
        Live events
      </div>
      <div className="flex max-h-80 flex-col gap-1 overflow-y-auto text-xs">
        {events.length === 0 && (
          <div className="text-slate-500">Waiting for events…</div>
        )}
        {events.map((e, i) => (
          <div
            key={i}
            className="flex items-center justify-between rounded bg-bg px-2 py-1"
          >
            <span className="font-mono text-accent">{e.type}</span>
            <span className="truncate text-slate-400">
              {JSON.stringify(e.payload)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
