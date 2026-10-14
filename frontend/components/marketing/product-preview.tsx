import { Gauge, Inbox, TrendingUp, Wallet } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { formatNaira } from "@/lib/money";

/**
 * A picture of the app for the landing page (DECISIONS D-65): the Overview and Match screens inside a browser
 * frame, drawn with the app's own pieces (StatusBadge, formatNaira) rather than a screenshot, so it stays sharp
 * and follows the theme. The figures are the seed demo's. Decoration only (aria-hidden): the text around it
 * says what it shows. It leans back in 3D and straightens as it scrolls into view (.tilt-in, globals.css).
 */

const KPIS = [
  { icon: Wallet, label: "Outstanding", value: formatNaira(43_750_000), tone: "bg-teal-50 text-teal-700 dark:bg-teal-400/15 dark:text-teal-300" },
  { icon: TrendingUp, label: "Collected this month", value: formatNaira(8_062_500), tone: "bg-green-50 text-green-700 dark:bg-green-400/15 dark:text-green-300" },
  { icon: Gauge, label: "Auto-match rate", value: "67%", tone: "bg-sky-50 text-sky-700 dark:bg-sky-400/15 dark:text-sky-300" },
  { icon: Inbox, label: "Needs review", value: "2", tone: "bg-amber-50 text-amber-800 dark:bg-amber-400/15 dark:text-amber-300" },
];
// Bar heights for "collections by week", as a share of the tallest week.
const WEEKS = [30, 52, 41, 68, 47, 84, 62, 100];
const QUEUE = [
  { narration: "NIP/BISI STORES LTD/OCT", amount: 5_375_000, invoice: "INV-0002", score: 88 },
  { narration: "TRF FROM TUNDE PRINTING", amount: 2_150_000, invoice: "INV-0003", score: 74 },
];

export function ProductPreview() {
  return (
    <div className="tilt-in mx-auto w-full max-w-5xl" aria-hidden>
      <div className="overflow-hidden rounded-2xl border bg-card shadow-2xl shadow-teal-900/20 ring-1 ring-black/5">
        {/* Browser bar */}
        <div className="flex items-center gap-3 border-b bg-muted/60 px-4 py-2.5">
          <span className="flex gap-1.5">
            <span className="size-2.5 rounded-full bg-red-400" />
            <span className="size-2.5 rounded-full bg-amber-400" />
            <span className="size-2.5 rounded-full bg-green-400" />
          </span>
          <span className="mx-auto w-full max-w-xs truncate rounded-md bg-background px-3 py-1 text-center text-xs text-muted-foreground">
            ReconcilePro · Overview
          </span>
        </div>

        <div className="flex">
          {/* Mini rail */}
          <div className="hidden w-14 shrink-0 flex-col items-center gap-3 bg-slate-900 py-4 sm:flex">
            {[0, 1, 2, 3, 4].map((n) => (
              <span key={n} className={n === 0 ? "size-7 rounded-md bg-teal-900 ring-1 ring-teal-400/40" : "size-7 rounded-md bg-white/5"} />
            ))}
          </div>

          <div className="min-w-0 flex-1 space-y-4 bg-canvas p-4 sm:p-6">
            <div>
              <p className="text-lg font-semibold">Overview</p>
              <p className="text-xs text-muted-foreground">Where your money is: owed, collected, and what needs you.</p>
            </div>

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {KPIS.map((kpi) => (
                <div key={kpi.label} className="rounded-xl border bg-card p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[10px] font-medium tracking-wide text-muted-foreground uppercase">{kpi.label}</span>
                    <span className={`flex size-6 shrink-0 items-center justify-center rounded-md ${kpi.tone}`}>
                      <kpi.icon className="size-3.5" />
                    </span>
                  </div>
                  <p className="mt-1 truncate text-base font-semibold tabular-nums sm:text-lg">{kpi.value}</p>
                </div>
              ))}
            </div>

            <div className="grid gap-3 lg:grid-cols-5">
              <div className="rounded-xl border bg-card p-4 lg:col-span-3">
                <p className="text-sm font-medium">Collections by week</p>
                <div className="mt-4 flex h-28 items-end gap-2">
                  {WEEKS.map((height, index) => (
                    <span
                      key={index}
                      className="flex-1 rounded-t-sm bg-linear-to-t from-teal-600 to-cyan-400"
                      style={{ height: `${height}%` }}
                    />
                  ))}
                </div>
              </div>
              <div className="rounded-xl border bg-card p-4 lg:col-span-2">
                <p className="text-sm font-medium">Needs review</p>
                <ul className="mt-3 space-y-2">
                  {QUEUE.map((line) => (
                    <li key={line.invoice} className="rounded-lg border p-2.5">
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="truncate font-mono">{line.narration}</span>
                        <span className="font-semibold tabular-nums">{formatNaira(line.amount)}</span>
                      </div>
                      <div className="mt-1.5 flex items-center justify-between gap-2 text-xs">
                        <span className="flex items-center gap-1.5">
                          <span className="font-mono">{line.invoice}</span>
                          <StatusBadge status="overdue" />
                        </span>
                        <span className="font-semibold text-brand tabular-nums">{line.score}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
