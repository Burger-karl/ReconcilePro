"use client";

import { ArrowRight, Gauge, Inbox, type LucideIcon, TrendingUp, Wallet } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { useCountUp } from "@/lib/use-count-up";
import { cn } from "@/lib/utils";

/**
 * The four numbers Overview leads with (pages/dashboard.md). Definitions live in the backend
 * (DECISIONS D-48); the frontend only formats them. Money is shown to the kobo, never rounded.
 * Each tile has a coloured icon, arrives a moment after the one before, and counts up to its figure (D-62).
 */
export function KpiTiles({ summary }: { summary: Schemas["Summary"] | undefined }) {
  if (!summary) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true" aria-label="Loading figures">
        {[0, 1, 2, 3].map((n) => (
          <Skeleton key={n} className="h-[118px]" />
        ))}
      </div>
    );
  }

  const monthStart = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short" }).format(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const invoices = summary.open_invoice_count;

  // One column on phones, 2×2 up to 1280px, then a row of four: a ₦ amount to the kobo must fit on one
  // line without being rounded or broken mid-number (DECISIONS D-52).
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Tile
        index={0}
        icon={Wallet}
        tone="teal"
        label="Outstanding"
        target={summary.outstanding_kobo}
        format={formatNaira}
        context={invoices === 0 ? "Nothing owed right now" : `across ${invoices} open invoice${invoices === 1 ? "" : "s"}`}
      />
      <Tile
        index={1}
        icon={TrendingUp}
        tone="green"
        label="Collected this month"
        target={summary.collected_this_month_kobo}
        format={formatNaira}
        context={`matched to invoices since ${monthStart}`}
      />
      <Tile
        index={2}
        icon={Gauge}
        tone="sky"
        label="Auto-match rate"
        target={summary.auto_match_rate}
        format={(rate) => `${rate}%`}
        context={
          summary.auto_match_rate === null
            ? "No payments matched in the last 30 days"
            : "of matches in the last 30 days needed nobody"
        }
      />
      <Tile
        index={3}
        icon={Inbox}
        // Amber only when something is waiting: the same "needs review" colour as the rail badge.
        tone={summary.needs_review_count === 0 ? "teal" : "amber"}
        label="Needs review"
        target={summary.needs_review_count}
        format={String}
        context={summary.needs_review_count === 0 ? "All caught up" : "credits waiting to be matched"}
        href={summary.needs_review_count === 0 ? undefined : "/match"}
      />
    </div>
  );
}

// Icon chip colours. Green = money in, amber = waiting on someone; teal and sky are neutral brand tints.
const TONES = {
  teal: "bg-teal-50 text-teal-700 dark:bg-teal-400/15 dark:text-teal-300",
  green: "bg-green-50 text-green-700 dark:bg-green-400/15 dark:text-green-300",
  sky: "bg-sky-50 text-sky-700 dark:bg-sky-400/15 dark:text-sky-300",
  amber: "bg-amber-50 text-amber-800 dark:bg-amber-400/15 dark:text-amber-300",
} as const;

function Tile({
  index,
  icon: Icon,
  tone,
  label,
  target,
  format,
  context,
  href,
}: {
  index: number;
  icon: LucideIcon;
  tone: keyof typeof TONES;
  label: string;
  /** The exact figure from the API (kobo, a percentage or a count); null shows a dash. */
  target: number | null;
  format: (value: number) => string;
  context: string;
  href?: string;
}) {
  const shown = useCountUp(target ?? 0);
  const body = (
    <Card className={cn("h-full gap-1 p-5", href && "hover-lift")}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
        <span className={cn("flex size-8 items-center justify-center rounded-lg", TONES[tone])}>
          <Icon className="size-4" aria-hidden />
        </span>
      </div>
      {/* 30px, tabular figures so the tiles line up (pages/dashboard.md). nowrap: an amount is read as one unit.
          Screen readers read the final figure once (sr-only), never the steps of the count. */}
      <p className="text-3xl font-semibold tracking-tight whitespace-nowrap tabular-nums">
        <span className="sr-only">{target === null ? "none" : format(target)}</span>
        <span aria-hidden>{target === null ? "—" : format(shown)}</span>
      </p>
      <p className="flex items-center gap-1 text-sm text-muted-foreground">
        {context}
        {href && <ArrowRight className="size-3.5 shrink-0" aria-hidden />}
      </p>
    </Card>
  );
  const style = { "--i": index } as React.CSSProperties; // stagger order for .animate-rise (globals.css)
  if (!href) {
    return (
      <div className="animate-rise" style={style}>
        {body}
      </div>
    );
  }
  return (
    <Link
      href={href}
      style={style}
      className="animate-rise rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {body}
    </Link>
  );
}
