"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";

/**
 * The four numbers Overview leads with (pages/dashboard.md). Definitions live in the backend
 * (DECISIONS D-48); the frontend only formats them. Money is shown to the kobo, never rounded.
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
        label="Outstanding"
        value={formatNaira(summary.outstanding_kobo)}
        context={invoices === 0 ? "Nothing owed right now" : `across ${invoices} open invoice${invoices === 1 ? "" : "s"}`}
      />
      <Tile
        label="Collected this month"
        value={formatNaira(summary.collected_this_month_kobo)}
        context={`matched to invoices since ${monthStart}`}
      />
      <Tile
        label="Auto-match rate"
        value={summary.auto_match_rate === null ? "—" : `${summary.auto_match_rate}%`}
        context={
          summary.auto_match_rate === null
            ? "No payments matched in the last 30 days"
            : "of matches in the last 30 days needed nobody"
        }
      />
      <Tile
        label="Needs review"
        value={String(summary.needs_review_count)}
        context={summary.needs_review_count === 0 ? "All caught up" : "credits waiting to be matched"}
        href={summary.needs_review_count === 0 ? undefined : "/match"}
      />
    </div>
  );
}

function Tile({ label, value, context, href }: { label: string; value: string; context: string; href?: string }) {
  const body = (
    <Card className="h-full gap-1 p-5">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
      {/* 30px, tabular figures so the tiles line up (pages/dashboard.md). nowrap: an amount is read as one unit. */}
      <p className="text-3xl font-semibold tracking-tight whitespace-nowrap tabular-nums">{value}</p>
      <p className="flex items-center gap-1 text-sm text-muted-foreground">
        {context}
        {href && <ArrowRight className="size-3.5 shrink-0" aria-hidden />}
      </p>
    </Card>
  );
  if (!href) return body;
  return (
    <Link href={href} className="rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none [&>div]:transition-colors [&>div]:hover:bg-muted/50">
      {body}
    </Link>
  );
}
