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
 * Each tile links to the list behind its number (D-70), unless there is nothing to show.
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
        tone="plain"
        label="Outstanding"
        target={summary.outstanding_kobo}
        format={formatNaira}
        context={invoices === 0 ? "Nothing owed right now" : `across ${invoices} open invoice${invoices === 1 ? "" : "s"}`}
        href={invoices === 0 ? undefined : "/invoices?status=open"}
      />
      <Tile
        index={1}
        icon={TrendingUp}
        tone="plain"
        label="Collected this month"
        target={summary.collected_this_month_kobo}
        format={formatNaira}
        context={`matched to invoices since ${monthStart}`}
        href="/statements?tab=allocated"
      />
      <Tile
        index={2}
        icon={Gauge}
        tone="plain"
        label="Auto-match rate"
        target={summary.auto_match_rate}
        format={(rate) => `${rate}%`}
        context={
          summary.auto_match_rate === null
            ? "No payments matched in the last 30 days"
            : "of matches in the last 30 days needed nobody"
        }
        // The Payments tab of the audit log says which matches were automatic and which were made by hand.
        href={summary.auto_match_rate === null ? undefined : "/audit?type=allocation"}
      />
      <Tile
        index={3}
        icon={Inbox}
        // The solid orange tile, like CEK's orange badge, only when something is waiting (same as the sidebar badge).
        tone={summary.needs_review_count === 0 ? "plain" : "highlight"}
        label="Needs review"
        target={summary.needs_review_count}
        format={String}
        context={summary.needs_review_count === 0 ? "All caught up" : "credits waiting to be matched"}
        href={summary.needs_review_count === 0 ? undefined : "/match"}
      />
    </div>
  );
}

// CEK style (D-71): white tiles with an orange icon circle; the "highlight" tile is solid orange with white text.
const TONES = {
  plain: { card: "", icon: "bg-brand-soft text-brand", muted: "text-muted-foreground" },
  highlight: { card: "bg-primary text-primary-foreground ring-0", icon: "bg-white/20 text-white", muted: "text-white/90" },
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
    <Card className={cn("h-full gap-1 p-5", TONES[tone].card, href && "hover-lift")}>
      <div className="flex items-center justify-between gap-2">
        <p className={cn("font-nav text-xs tracking-wider uppercase", TONES[tone].muted)}>{label}</p>
        <span className={cn("flex size-11 items-center justify-center rounded-full", TONES[tone].icon)}>
          <Icon className="size-5" aria-hidden />
        </span>
      </div>
      {/* 30px, tabular figures so the tiles line up (pages/dashboard.md). nowrap: an amount is read as one unit.
          Screen readers read the final figure once (sr-only), never the steps of the count. */}
      <p className="font-heading text-3xl font-black tracking-tight whitespace-nowrap tabular-nums">
        <span className="sr-only">{target === null ? "none" : format(target)}</span>
        <span aria-hidden>{target === null ? "—" : format(shown)}</span>
      </p>
      <p className={cn("flex items-center gap-1 text-sm", TONES[tone].muted)}>
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
      className="animate-rise rounded-2xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {body}
    </Link>
  );
}
