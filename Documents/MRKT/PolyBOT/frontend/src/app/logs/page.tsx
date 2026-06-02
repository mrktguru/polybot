"use client";

import { useEvents } from "@/lib/useEvents";

export default function LogsPage() {
  const events = useEvents(200);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Event Logs</h1>
      <div className="flex max-h-[70vh] flex-col gap-1 overflow-y-auto rounded-lg border border-border bg-panel p-4 font-mono text-xs">
        {events.length === 0 && (
          <div className="text-slate-500">Waiting for events…</div>
        )}
        {events.map((e, i) => (
          <div key={i} className="flex gap-3 border-b border-border/30 py-1">
            <span className="shrink-0 text-slate-500">
              {new Date(e.receivedAt).toLocaleTimeString()}
            </span>
            <span className="shrink-0 text-accent">{e.type}</span>
            <span className="truncate text-slate-300">
              {JSON.stringify(e.payload)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
