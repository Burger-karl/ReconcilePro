"use client";

/**
 * What is still owed, by how late it is (backend D-48), as a labelled list with a bar per bucket.
 *
 * Colour is a STATUS here, not decoration (MASTER.md §6): "not yet due" is neutral slate, then
 * amber → red → dark red as invoices get later. The palette was checked with the dataviz validator:
 * every pair stays distinct for colour-blind and normal vision in both themes (DECISIONS D-52).
 * Each row also says its bucket and amount in words, so colour is never the only signal.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

type Bucket = Schemas["AgeingBucket"]["bucket"];

const BUCKETS: Record<Bucket, { label: string; bar: string }> = {
  current: { label: "Not yet due", bar: "bg-brand" }, // brand teal: on time is the healthy bucket (D-62)
  "1_30": { label: "1–30 days late", bar: "bg-amber-500 dark:bg-amber-400" },
  "31_60": { label: "31–60 days late", bar: "bg-red-500 dark:bg-red-400" },
  "60_plus": { label: "Over 60 days late", bar: "bg-red-800 dark:bg-red-700" },
};

export function AgeingList({ buckets }: { buckets: Schemas["AgeingBucket"][] | undefined }) {
  const largest = Math.max(1, ...(buckets ?? []).map((bucket) => bucket.outstanding_kobo));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ageing</CardTitle>
        <CardDescription>Still owed, by days past the due date.</CardDescription>
      </CardHeader>
      <CardContent>
        {!buckets ? (
          <Skeleton className="h-56 w-full" />
        ) : (
          <ul className="flex flex-col gap-4">
            {buckets.map((bucket, index) => (
              <li key={bucket.bucket} className="animate-rise flex flex-col gap-1.5" style={{ "--i": index } as React.CSSProperties}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span>
                    {BUCKETS[bucket.bucket].label}
                    <span className="ml-1.5 text-muted-foreground">
                      · {bucket.count} invoice{bucket.count === 1 ? "" : "s"}
                    </span>
                  </span>
                  <span className="font-medium tabular-nums">{formatNaira(bucket.outstanding_kobo)}</span>
                </div>
                {/* Track = a lighter step behind the fill; the bar is decoration, the text above carries the value. */}
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
                  <div
                    // Grows from the left on first render (animate-grow, globals.css); its final width is the real share.
                    className={cn("animate-grow h-full origin-left rounded-full", BUCKETS[bucket.bucket].bar)}
                    style={{ width: `${(bucket.outstanding_kobo / largest) * 100}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
