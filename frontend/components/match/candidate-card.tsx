"use client";

/**
 * One invoice the selected bank credit might pay (pages/reconciliation.md "Candidate card").
 * The score and reasons come from the backend's matcher (backend D-25); this card only shows them.
 */

import { CircleAlert } from "lucide-react";

import { type InvoiceStatus, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import type { Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

type Candidate = Schemas["CandidateRead"];

// The three parts of the score and their maximum points (backend matching: amount 50, name 30, date 20).
const PARTS = [
  { key: "amount", label: "Amount", max: 50 },
  { key: "name", label: "Name", max: 30 },
  { key: "date", label: "Date", max: 20 },
] as const;

/**
 * One bar, 100 units wide, split into Amount / Name / Date. Each part is as wide as its maximum; the filled
 * share is what this candidate scored. Navy fill, muted track, a 2px gap between parts, and every part is
 * labelled with its points, so colour is never the only signal (MASTER.md §8).
 */
function ScoreBar({ breakdown, score }: { breakdown: Candidate["breakdown"]; score: number }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex flex-1 gap-0.5" role="img" aria-label={`Score ${score} of 100`}>
        {PARTS.map((part) => (
          <div key={part.key} className="flex flex-col gap-1" style={{ width: `${part.max}%` }}>
            <div className="h-2 overflow-hidden rounded-sm bg-muted">
              <div className="h-full bg-primary" style={{ width: `${(breakdown[part.key] / part.max) * 100}%` }} />
            </div>
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {part.label} {breakdown[part.key]}/{part.max}
            </span>
          </div>
        ))}
      </div>
      <span className="w-10 self-start text-right text-lg leading-none font-semibold tabular-nums">{score}</span>
    </div>
  );
}

export function CandidateCard({
  candidate,
  position,
  creditUnallocatedKobo,
  suggested,
  selected,
  busy,
  error,
  onSelect,
  onAccept,
  onAllocatePart,
  onReject,
}: {
  candidate: Candidate;
  /** 1, 2 or 3: the number key that selects this card. */
  position: number;
  creditUnallocatedKobo: number;
  suggested: boolean;
  selected: boolean;
  busy: boolean;
  error: string | null;
  onSelect: () => void;
  onAccept: () => void;
  onAllocatePart: () => void;
  onReject: () => void;
}) {
  // Accepting moves as much as both sides allow; allocate() on the server re-checks this under a lock.
  const acceptKobo = Math.min(creditUnallocatedKobo, candidate.outstanding_kobo);

  return (
    <article
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "flex cursor-pointer flex-col gap-3 rounded-lg border bg-card p-4",
        selected && "border-primary ring-1 ring-primary",
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex items-center gap-2">
            <Kbd aria-hidden>{position}</Kbd>
            <span className="font-mono text-sm font-medium">{candidate.invoice_number}</span>
            <StatusBadge status={candidate.status as InvoiceStatus} />
            {suggested && (
              <span className="rounded-full bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground">
                Suggested
              </span>
            )}
          </p>
          <p className="mt-1 truncate text-sm">{candidate.customer_name}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted-foreground">Outstanding</p>
          <p className="font-semibold tabular-nums">{formatNaira(candidate.outstanding_kobo)}</p>
        </div>
      </header>

      <ScoreBar breakdown={candidate.breakdown} score={candidate.score} />

      {/* Reasons hold no money (backend D-29), so the two amounts they compare are shown beside them. */}
      <div className="grid gap-2 text-sm sm:grid-cols-[1fr_auto]">
        <ul className="list-disc space-y-0.5 pl-5">
          {candidate.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        <dl className="grid grid-cols-[auto_auto] gap-x-3 text-xs text-muted-foreground sm:text-right">
          <dt>Credit left</dt>
          <dd className="text-foreground tabular-nums">{formatNaira(creditUnallocatedKobo)}</dd>
          <dt>Invoice owes</dt>
          <dd className="text-foreground tabular-nums">{formatNaira(candidate.outstanding_kobo)}</dd>
        </dl>
      </div>

      {error && (
        <p role="alert" className="flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2" onClick={(event) => event.stopPropagation()}>
        <Button onClick={onAccept} disabled={busy}>
          {busy ? "Saving…" : `Accept ${formatNaira(acceptKobo)}`}
          <Kbd className="ml-1 hidden bg-primary-foreground/15 text-primary-foreground sm:inline-flex">A</Kbd>
        </Button>
        <Button variant="outline" onClick={onAllocatePart} disabled={busy}>
          Allocate part…
          <Kbd className="ml-1 hidden sm:inline-flex">M</Kbd>
        </Button>
        <Button variant="ghost" onClick={onReject} disabled={busy}>
          Not this one
          <Kbd className="ml-1 hidden sm:inline-flex">R</Kbd>
        </Button>
      </div>
    </article>
  );
}
