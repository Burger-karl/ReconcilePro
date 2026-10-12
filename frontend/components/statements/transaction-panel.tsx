"use client";

/** One bank or Paystack line in full: where its money went, including matches that were reversed. */

import Link from "next/link";
import useSWR from "swr";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { API, type Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

type Detail = Schemas["TransactionDetail"];

const date = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short", year: "numeric" });
const asDate = (isoDate: string) => date.format(new Date(`${isoDate}T00:00:00`));
const METHOD: Record<string, string> = { auto: "Matched automatically", suggested: "Suggestion accepted", manual: "Matched by hand" };

export function TransactionPanel({ transactionId }: { transactionId: string }) {
  const { data: line, error } = useSWR<Detail>(`${API}/transactions/${transactionId}`);

  if (error) return <p className="p-5 text-sm text-muted-foreground">{error instanceof Error ? error.message : "Couldn't load this line."}</p>;
  if (!line) return <Skeleton className="m-5 h-80" />;

  const settlement = line.kind === "settlement";

  return (
    <div className="flex flex-col gap-5 p-5">
      <header>
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {line.source === "paystack" ? "Paystack payment" : "Bank statement"} · {asDate(line.value_date)}
        </p>
        <p className="mt-1 font-medium">{line.payer_name ?? (settlement ? "Paystack payout" : "Payer not recognised")}</p>
        {/* The narration exactly as the bank wrote it, in mono (frontend/CLAUDE.md). */}
        <p className="mt-2 rounded bg-background px-3 py-2 font-mono text-sm break-all">{line.narration}</p>
        {line.bank_reference && (
          <p className="mt-1 text-xs text-muted-foreground">
            Bank reference <span className="font-mono text-foreground">{line.bank_reference}</span>
          </p>
        )}
      </header>

      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Amount</dt>
        <dd className="text-right tabular-nums">{formatNaira(line.amount_kobo)}</dd>
        {/* A payout is never matched, so "still to match" would be misleading for it (invariant 6). */}
        {!settlement && (
          <>
            <dt className="text-muted-foreground">Matched to invoices</dt>
            <dd className="text-right tabular-nums">{formatNaira(line.allocated_kobo)}</dd>
            <dt className="font-semibold">Still to match</dt>
            <dd className="text-right font-semibold tabular-nums">{formatNaira(line.unallocated_kobo)}</dd>
          </>
        )}
      </dl>

      {settlement ? (
        // Invariant 6: the payments inside a payout were already recorded one by one by the Paystack webhook.
        <p className="rounded-lg border bg-background p-3 text-sm text-muted-foreground">
          This is Paystack paying out money it collected. The customer payments inside it were recorded when each one
          arrived, so it is never matched to an invoice (that would count the money twice).
        </p>
      ) : (
        line.unallocated_kobo > 0 && (
          <Button asChild variant="outline" className="self-start">
            <Link href="/match">Match this payment</Link>
          </Button>
        )
      )}

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Where the money went</h3>
        {line.allocations.length === 0 ? (
          <p className="text-sm text-muted-foreground">Not matched to any invoice yet.</p>
        ) : (
          <ul className="divide-y rounded-lg border bg-background">
            {line.allocations.map((allocation) => {
              const reversed = allocation.reversed_at !== null;
              return (
                <li key={allocation.id} className="flex items-center justify-between gap-3 p-3 text-sm">
                  <div className="min-w-0">
                    <Link href={`/invoices/${allocation.invoice_id}`} className="font-mono underline-offset-4 hover:underline">
                      {allocation.invoice_number}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {reversed ? `Reversed: ${allocation.reversal_reason}` : (METHOD[allocation.method] ?? allocation.method)}
                    </p>
                  </div>
                  <span className={cn("tabular-nums", reversed && "text-muted-foreground line-through")}>
                    {formatNaira(allocation.amount_kobo)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
