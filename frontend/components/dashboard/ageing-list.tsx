"use client";

/**
 * What is still owed, by how late it is (backend D-48), as a labelled list with a bar per bucket.
 *
 * Colour is a STATUS here, not decoration (MASTER.md §6): "not yet due" is neutral slate, then
 * amber → red → dark red as invoices get later. The palette was checked with the dataviz validator:
 * every pair stays distinct for colour-blind and normal vision in both themes (DECISIONS D-52).
 * Each row also says its bucket and amount in words, so colour is never the only signal.
 * A bucket with invoices in it links to the invoice list filtered to that bucket (D-70).
 */

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

type Bucket = Schemas["AgeingBucket"]["bucket"];

export const BUCKETS: Record<Bucket, { label: string; bar: string }> = {
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
              <li key={bucket.bucket} className="animate-rise" style={{ "--i": index } as React.CSSProperties}>
                <BucketRow bucket={bucket}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span>
                    {BUCKETS[bucket.bucket].label}
                    <span className="ml-1.5 text-muted-foreground">
                      · {bucket.count} invoice{bucket.count === 1 ? "" : "s"}
                    </span>
                  </span>
                  <span className="flex items-center gap-1 font-medium tabular-nums">
                    {formatNaira(bucket.outstanding_kobo)}
                    {bucket.count > 0 && <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />}
                  </span>
                </div>
                {/* Track = a lighter step behind the fill; the bar is decoration, the text above carries the value. */}
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
                  <div
                    // Grows from the left on first render (animate-grow, globals.css); its final width is the real share.
                    className={cn("animate-grow h-full origin-left rounded-full", BUCKETS[bucket.bucket].bar)}
                    style={{ width: `${(bucket.outstanding_kobo / largest) * 100}%` }}
                  />
                </div>
                </BucketRow>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/** A bucket with invoices opens them on the Invoices screen; an empty one has nothing to show, so it isn't a link. */
function BucketRow({ bucket, children }: { bucket: Schemas["AgeingBucket"]; children: React.ReactNode }) {
  if (bucket.count === 0) return <div className="flex flex-col gap-1.5">{children}</div>;
  const invoices = `${bucket.count} invoice${bucket.count === 1 ? "" : "s"}`;
  return (
    <Link
      href={`/invoices?ageing=${bucket.bucket}`}
      aria-label={`${BUCKETS[bucket.bucket].label}: ${invoices}, ${formatNaira(bucket.outstanding_kobo)}. Show them`}
      className="-mx-2 flex flex-col gap-1.5 rounded-md px-2 py-1 transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {children}
    </Link>
  );
}
