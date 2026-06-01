import type { StrategyStatus } from "@/lib/api";

export function StrategyGrid({ strategies }: { strategies: StrategyStatus[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      {strategies.map((s) => (
        <div
          key={s.name}
          className="rounded-lg border border-border bg-panel p-4"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium capitalize">
              {s.name.replace(/_/g, " ")}
            </span>
            <span
              className={`rounded px-2 py-0.5 text-[10px] uppercase ${
                s.automation_level === "full"
                  ? "bg-accent/20 text-accent"
                  : "bg-slate-600/30 text-slate-300"
              }`}
            >
              {s.automation_level}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
            <div>
              Budget
              <div className="text-sm text-slate-100">
                ${s.budget.toFixed(0)}
              </div>
            </div>
            <div>
              Today PnL
              <div
                className={`text-sm ${
                  s.today_pnl >= 0 ? "text-profit" : "text-loss"
                }`}
              >
                ${s.today_pnl.toFixed(2)}
              </div>
            </div>
            <div>
              Positions
              <div className="text-sm text-slate-100">{s.open_positions}</div>
            </div>
            <div>
              Status
              <div className="text-sm text-slate-100">
                {s.enabled ? "on" : "off"}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
