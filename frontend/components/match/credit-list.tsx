"use client";

/** Left pane: bank credits that still have unmatched money (pages/reconciliation.md). */

import type { Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

type Item = Schemas["QueueItem"];

const dateFormat = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short" });
// value_date is a calendar date ("2026-10-08"); reading it as local midnight keeps the day from shifting.
export const formatValueDate = (isoDate: string) => dateFormat.format(new Date(`${isoDate}T00:00:00`));

export function CreditList({
  items,
  selectedId,
  leavingId,
  onSelect,
}: {
  items: Item[];
  selectedId: string | null;
  /** A row the accountant just resolved: it fades out before the list refreshes. */
  leavingId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <ul className="divide-y" aria-label="Payments to match">
      {items.map(({ transaction, suggested_invoice_id }) => {
        const selected = transaction.id === selectedId;
        return (
          <li key={transaction.id}>
            <button
              type="button"
              onClick={() => onSelect(transaction.id)}
              aria-current={selected ? "true" : undefined}
              className={cn(
                // 44px rows, 2px navy left border when selected (pages/reconciliation.md).
                "flex min-h-11 w-full cursor-pointer flex-col gap-0.5 border-l-2 border-transparent px-4 py-2.5 text-left hover:bg-muted/50",
                "motion-safe:transition-opacity motion-safe:duration-200",
                selected && "border-primary bg-muted/60",
                leavingId === transaction.id && "opacity-0",
              )}
            >
              <span className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate font-medium">{transaction.payer_name ?? "Unknown payer"}</span>
                <span className="shrink-0 font-semibold tabular-nums">{formatNaira(transaction.unallocated_kobo)}</span>
              </span>
              <span className="flex items-baseline justify-between gap-3 text-xs text-muted-foreground">
                {/* Raw bank narrations in mono (frontend/CLAUDE.md). */}
                <span className="truncate font-mono">{transaction.narration}</span>
                <span className="shrink-0">
                  {suggested_invoice_id && <span className="mr-2 font-medium text-foreground">Suggested</span>}
                  {formatValueDate(transaction.value_date)}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
