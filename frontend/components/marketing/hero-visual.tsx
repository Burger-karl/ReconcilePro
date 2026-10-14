import { Check, CreditCard, Sparkles } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { formatNaira } from "@/lib/money";

/**
 * The landing hero's picture (D-63, D-65): a matched bank payment (the app's own pieces, not an image), with a
 * Paystack payment card and an "auto-matched" chip floating around it, out of step (.animate-float, --i).
 * Each card also tips slightly towards you on hover (.lift-card).
 */

const order = (i: number) => ({ "--i": i }) as React.CSSProperties;

function MatchPreview() {
  const parts = [
    { label: "Amount", score: 50, max: 50 },
    { label: "Name", score: 30, max: 30 },
    { label: "Date", score: 16, max: 20 },
  ];
  return (
    <figure className="lift-card w-full max-w-md rounded-2xl border bg-card p-5 shadow-2xl shadow-teal-900/10">
      <figcaption className="sr-only">Example: a bank payment matched to an invoice, with its score and reasons</figcaption>
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Bank credit · 14 Oct</p>
      <div className="mt-1 flex items-baseline justify-between gap-3">
        <span className="font-medium">KOLA AND SONS</span>
        <span className="font-semibold tabular-nums">{formatNaira(9_675_000)}</span>
      </div>
      <p className="mt-2 rounded bg-muted px-3 py-2 font-mono text-xs">NIP/KOLA AND SONS/SUPPLIES OCT</p>

      <div className="mt-4 rounded-xl border p-4">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            <span className="font-mono text-sm">INV-0042</span>
            <StatusBadge status="sent" />
          </span>
          <span className="flex items-center gap-1.5 text-lg font-semibold tabular-nums">
            {/* Pops in after the card arrives: the match is confirmed. */}
            <span className="animate-pop flex size-5 items-center justify-center rounded-full bg-green-600 text-white [animation-delay:900ms]">
              <Check className="size-3" aria-hidden />
            </span>
            96
          </span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">Kola &amp; Sons · owes {formatNaira(9_675_000)}</p>
        {/* Score parts, as in the matching rules: amount 50, name 30, date 20. */}
        <div className="mt-3 flex gap-0.5" aria-hidden>
          {parts.map((part) => (
            <div key={part.label} className="flex flex-col gap-1" style={{ width: `${part.max}%` }}>
              <div className="h-2 overflow-hidden rounded-sm bg-muted">
                <div
                  className="animate-grow h-full origin-left bg-linear-to-r from-teal-500 to-cyan-500 [animation-delay:500ms]"
                  style={{ width: `${(part.score / part.max) * 100}%` }}
                />
              </div>
              <span className="text-[11px] text-muted-foreground">
                {part.label} {part.score}/{part.max}
              </span>
            </div>
          ))}
        </div>
        <ul className="mt-3 list-disc space-y-0.5 pl-5 text-sm">
          <li>Amount equals the amount outstanding</li>
          <li>Payer &apos;KOLA AND SONS&apos; matches customer &apos;Kola &amp; Sons&apos;</li>
        </ul>
        <div className="mt-3 flex gap-2">
          <span className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground">Accept</span>
          <span className="rounded-md border px-3 py-1.5 text-xs">Not this one</span>
        </div>
      </div>
    </figure>
  );
}

/** A Paystack payment recorded and the invoice paid (backend D-30). */
function PaystackPreview() {
  return (
    <div className="lift-card w-64 rounded-2xl border bg-card p-4 shadow-xl shadow-teal-900/10" aria-hidden>
      <div className="flex items-center gap-2">
        <span className="flex size-8 items-center justify-center rounded-lg bg-sky-50 text-sky-700 dark:bg-sky-400/15 dark:text-sky-300">
          <CreditCard className="size-4" />
        </span>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">Paystack · card</p>
          <p className="text-sm font-semibold tabular-nums">{formatNaira(4_515_000)}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 text-xs">
        <span className="font-mono">INV-0039</span>
        <StatusBadge status="paid" />
      </div>
    </div>
  );
}

export function HeroVisual() {
  return (
    <div className="relative flex justify-center lg:justify-end">
      <div className="animate-rise w-full max-w-md" style={order(3)}>
        <div className="animate-float" style={order(0)}>
          <MatchPreview />
        </div>
      </div>
      <div className="absolute -bottom-10 -left-4 hidden sm:block lg:-left-16">
        <div className="animate-rise" style={order(6)}>
          <div className="animate-float" style={order(1)}>
            <PaystackPreview />
          </div>
        </div>
      </div>
      <div className="absolute -top-5 right-2 hidden sm:block">
        <div className="animate-rise" style={order(7)}>
          <p
            className="animate-float flex items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-xs font-medium shadow-lg"
            style={order(2)}
            aria-hidden
          >
            <Sparkles className="size-3.5 text-brand" />
            Matched automatically
          </p>
        </div>
      </div>
    </div>
  );
}
