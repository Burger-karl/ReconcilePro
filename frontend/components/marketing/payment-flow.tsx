import { ArrowDown, Check, Landmark, ScanSearch } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { formatNaira } from "@/lib/money";

/**
 * "Follow one payment" (DECISIONS D-65): a bank credit, the match (score and reasons), the invoice paid.
 * Dots travel along the tracks between the stages (.animate-travel in globals.css) to show money moving.
 * The steps are what the backend really does: import (invariant 2), score (matching rules in CLAUDE.md),
 * allocate() with the derived "paid" status (invariants 4 and 5).
 */

function Track({ delay }: { delay: number }) {
  return (
    // Wide screens: a horizontal track with travelling dots. Phones: a simple arrow, since the stages stack.
    <div className="flex items-center justify-center lg:flex-1">
      <ArrowDown className="size-5 text-brand lg:hidden" aria-hidden />
      <div className="flow-track relative hidden h-1 w-full rounded-full bg-teal-100 lg:block dark:bg-teal-950" aria-hidden>
        {[0, 1].map((n) => (
          <span
            key={n}
            className="animate-travel absolute -top-1 left-0 size-3 rounded-full bg-linear-to-r from-teal-400 to-cyan-400 shadow-[0_0_12px_rgb(45_212_191/0.8)]"
            style={{ "--i": delay + n } as React.CSSProperties}
          />
        ))}
      </div>
    </div>
  );
}

const STAGE = "lift-card w-full rounded-2xl border bg-card p-5 shadow-sm lg:w-72 lg:shrink-0";

export function PaymentFlow() {
  return (
    <div className="flex flex-col items-stretch gap-4 lg:flex-row lg:items-center lg:gap-6">
      <div className={STAGE}>
        <div className="flex items-center gap-2 text-sm font-medium">
          <span className="lift-icon flex size-8 items-center justify-center rounded-lg bg-sky-50 text-sky-700 dark:bg-sky-400/15 dark:text-sky-300">
            <Landmark className="size-4" aria-hidden />
          </span>
          1 · Money arrives
        </div>
        <p className="mt-3 truncate rounded-md bg-muted px-2.5 py-1.5 font-mono text-xs">NIP/KOLA AND SONS/RCN-4F2K</p>
        <p className="mt-2 text-2xl font-semibold tabular-nums">{formatNaira(9_675_000)}</p>
        <p className="text-xs text-muted-foreground">Bank credit, imported from your statement</p>
      </div>

      <Track delay={0} />

      <div className={STAGE}>
        <div className="flex items-center gap-2 text-sm font-medium">
          <span className="lift-icon flex size-8 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-400/15 dark:text-teal-300">
            <ScanSearch className="size-4" aria-hidden />
          </span>
          2 · We find the invoice
        </div>
        <div className="mt-3 flex items-baseline justify-between">
          <span className="font-mono text-sm">INV-0042</span>
          {/* An exact reference is matched outright, with no score (matching rules in CLAUDE.md). */}
          <span className="rounded-full bg-brand-soft px-2.5 py-1 text-xs font-semibold text-teal-800 dark:text-teal-200">
            Exact match
          </span>
        </div>
        <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
          <li className="flex items-center gap-1.5">
            <Check className="size-3.5 text-green-600" aria-hidden />
            Reference RCN-4F2K is in the narration
          </li>
          <li className="flex items-center gap-1.5">
            <Check className="size-3.5 text-green-600" aria-hidden />
            Amount equals what is owed
          </li>
        </ul>
      </div>

      <Track delay={1} />

      <div className={STAGE}>
        <div className="flex items-center gap-2 text-sm font-medium">
          <span className="lift-icon flex size-8 items-center justify-center rounded-lg bg-green-50 text-green-700 dark:bg-green-400/15 dark:text-green-300">
            <Check className="size-4" aria-hidden />
          </span>
          3 · Invoice paid
        </div>
        <div className="mt-3 flex items-center justify-between">
          <span className="font-mono text-sm">INV-0042</span>
          <StatusBadge status="paid" />
        </div>
        <p className="mt-2 text-2xl font-semibold tabular-nums">{formatNaira(0)}</p>
        <p className="text-xs text-muted-foreground">Outstanding, to the kobo. Logged in the audit trail.</p>
      </div>
    </div>
  );
}
