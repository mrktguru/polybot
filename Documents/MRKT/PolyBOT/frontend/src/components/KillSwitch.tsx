"use client";

import { useState } from "react";
import { post } from "@/lib/api";

export function KillSwitch({
  paused,
  reason,
  onChange,
}: {
  paused: boolean;
  reason: string | null;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    if (!paused && !confirm("Pause ALL trading (kill switch)?")) return;
    setBusy(true);
    try {
      await post(paused ? "/api/risk/resume" : "/api/risk/pause", {
        reason: "manual kill switch",
      });
      onChange();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      {paused && (
        <span className="text-sm text-loss">
          PAUSED{reason ? `: ${reason}` : ""}
        </span>
      )}
      <button
        onClick={toggle}
        disabled={busy}
        className={`rounded px-4 py-2 text-sm font-semibold disabled:opacity-50 ${
          paused
            ? "bg-profit/20 text-profit hover:bg-profit/30"
            : "bg-loss/20 text-loss hover:bg-loss/30"
        }`}
      >
        {paused ? "RESUME" : "KILL SWITCH"}
      </button>
    </div>
  );
}
