/**
 * Landing page (slice F9, design-system MASTER.md §7): hero with a real-looking reconciliation card,
 * how it works in three steps, why the numbers can be trusted, and one call to action.
 *
 * A server component: it has no state, so it is rendered once and sent as plain HTML (fast, indexable).
 * Only the header buttons (AuthNav) run in the browser, to tell visitors from signed-in users.
 * Every claim here is something the product really does, with the rule that makes it true in brackets
 * in the comments, so it can be defended in the viva.
 */

import { ArrowLeftRight, ArrowRight, FileUp, History, ListChecks, ShieldCheck, Sparkles, Sigma } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { AuthNav } from "@/components/marketing/auth-nav";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { formatNaira } from "@/lib/money";

export const metadata: Metadata = {
  title: "Reconcile — know which invoices are paid",
  description:
    "Reconcile reads your bank statements and Paystack payments, matches each one to the right invoice, and only asks you about the ones it isn't sure of.",
};

const STEPS = [
  {
    icon: FileUp,
    title: "Upload your bank statement",
    // Invariant 2: unique fingerprint per line + ON CONFLICT DO NOTHING.
    text: "Export a CSV from your bank and drop it in. Overlapping statements are fine: a line already imported is never added twice.",
  },
  {
    icon: Sparkles,
    title: "We match what we can",
    // Matching rules in CLAUDE.md: exact reference → auto; otherwise amount 50 / name 30 / date 20.
    text: "A payment that quotes the invoice reference is matched straight away. Paystack card payments are recorded the moment they succeed.",
  },
  {
    icon: ListChecks,
    title: "You review the rest",
    // Match screen: score breakdown + plain-English reasons, keyboard shortcuts.
    text: "Anything uncertain waits in one queue, with the likely invoices ranked and the reasons in plain English. Accept with one key.",
  },
];

const TRUST = [
  {
    icon: Sigma,
    title: "Every kobo counted",
    // Invariant 1: money is integer kobo end to end, formatted only in the UI.
    text: "Amounts are stored as whole kobo, never rounded floats. ₦90,000.00 is exactly 9,000,000 kobo, every time.",
  },
  {
    icon: ShieldCheck,
    title: "Never paid twice",
    // Invariants 3 and 4: unique Paystack reference; allocate() locks rows and refuses over-allocation.
    text: "A repeated Paystack notification records the payment once, and no invoice or bank line can ever be allocated more than its amount.",
  },
  {
    icon: History,
    title: "Nothing disappears",
    // Invariant 7: allocations are reversed, never deleted; every manual action writes an audit row.
    text: "A wrong match is reversed with a reason, never deleted. Every change is in the audit log: who, what and when.",
  },
];

// Landing-page buttons: 44px tall (this shadcn style's "lg" is only 36px), easy to hit on a phone.
const CTA = "h-11 px-5 text-base";

/** The hero's picture: a real-looking matched payment, built from the app's own pieces (not an image). */
function MatchPreview() {
  const parts = [
    { label: "Amount", score: 50, max: 50 },
    { label: "Name", score: 30, max: 30 },
    { label: "Date", score: 16, max: 20 },
  ];
  return (
    <figure className="w-full max-w-md rounded-xl border bg-card p-5 shadow-sm">
      <figcaption className="sr-only">Example: a bank payment matched to an invoice, with its score and reasons</figcaption>
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Bank credit · 14 Oct</p>
      <div className="mt-1 flex items-baseline justify-between gap-3">
        <span className="font-medium">KOLA AND SONS</span>
        <span className="font-semibold tabular-nums">{formatNaira(9_675_000)}</span>
      </div>
      <p className="mt-2 rounded bg-muted px-3 py-2 font-mono text-xs">NIP/KOLA AND SONS/SUPPLIES OCT</p>

      <div className="mt-4 rounded-lg border p-4">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2">
            <span className="font-mono text-sm">INV-0042</span>
            <StatusBadge status="sent" />
          </span>
          <span className="text-lg font-semibold tabular-nums">96</span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">Kola &amp; Sons · owes {formatNaira(9_675_000)}</p>
        <div className="mt-3 flex gap-0.5" aria-hidden>
          {parts.map((part) => (
            <div key={part.label} className="flex flex-col gap-1" style={{ width: `${part.max}%` }}>
              <div className="h-2 overflow-hidden rounded-sm bg-muted">
                <div className="h-full bg-primary" style={{ width: `${(part.score / part.max) * 100}%` }} />
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

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <ArrowLeftRight className="size-4" aria-hidden />
            </span>
            Reconcile
          </Link>
          <AuthNav />
        </div>
      </header>

      <main className="flex-1">
        {/* Hero: one-line promise + the reconciliation card as the visual. */}
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div className="flex flex-col gap-6">
            <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
              Know which invoices are paid, without the spreadsheet.
            </h1>
            <p className="max-w-xl text-lg text-muted-foreground">
              Reconcile reads your bank statements and Paystack payments, matches each one to the right invoice, and only
              asks you about the ones it isn&apos;t sure of.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button asChild size="lg" className={CTA}>
                <Link href="/register">
                  Create free workspace
                  <ArrowRight aria-hidden />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline" className={CTA}>
                <Link href="/login">Sign in</Link>
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">For Nigerian small businesses. Amounts in naira, to the kobo.</p>
          </div>
          <div className="flex justify-center lg:justify-end">
            <MatchPreview />
          </div>
        </section>

        <section className="border-t bg-canvas" aria-labelledby="how-heading">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
            <h2 id="how-heading" className="text-2xl font-semibold tracking-tight sm:text-3xl">
              How it works
            </h2>
            <ol className="mt-10 grid gap-8 md:grid-cols-3">
              {STEPS.map((step, index) => (
                <li key={step.title} className="flex flex-col gap-3">
                  <span className="flex items-center gap-3">
                    <span className="flex size-9 items-center justify-center rounded-lg border bg-background">
                      <step.icon className="size-5" aria-hidden />
                    </span>
                    <span className="text-sm font-medium text-muted-foreground">Step {index + 1}</span>
                  </span>
                  <h3 className="text-lg font-semibold">{step.title}</h3>
                  <p className="text-muted-foreground">{step.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="border-t" aria-labelledby="trust-heading">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
            <h2 id="trust-heading" className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Numbers you can stand behind
            </h2>
            <div className="mt-10 grid gap-8 md:grid-cols-3">
              {TRUST.map((item) => (
                <div key={item.title} className="flex flex-col gap-3 rounded-xl border p-6">
                  <item.icon className="size-6" aria-hidden />
                  <h3 className="text-lg font-semibold">{item.title}</h3>
                  <p className="text-muted-foreground">{item.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t bg-canvas">
          <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-4 py-16 text-center sm:px-6 lg:py-24">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Stop matching payments by hand.</h2>
            <p className="max-w-xl text-muted-foreground">
              Create a workspace, add your customers, and import last month&apos;s statement. It takes a few minutes.
            </p>
            <Button asChild size="lg" className={CTA}>
              <Link href="/register">
                Create free workspace
                <ArrowRight aria-hidden />
              </Link>
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-6 text-sm text-muted-foreground sm:px-6">
          <span>Reconcile</span>
          <span>Bank statements, Paystack and invoices, matched.</span>
        </div>
      </footer>
    </div>
  );
}
