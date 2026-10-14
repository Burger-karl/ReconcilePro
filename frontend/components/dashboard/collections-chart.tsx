"use client";

/**
 * Money matched to invoices per week (backend D-48), last 8 weeks, as columns.
 * dataviz rules: one series → no legend (the title names it); one colour (teal-600 / teal-400 in dark, D-62;
 * contrast ≥ 3:1 checked with the palette validator); columns ≤ 24px with a 4px rounded top, square at
 * the baseline; hairline horizontal grid; compact ₦ on the axis, full ₦ to the kobo in the tooltip and table.
 */

import { Bar, BarChart, CartesianGrid, type TooltipContentProps, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type ChartConfig, ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import type { Schemas } from "@/lib/api";
import { compactNaira, formatNaira } from "@/lib/money";

const config = {
  collected_kobo: { label: "Collected", theme: { light: "#0d9488", dark: "#2dd4bf" } }, // teal-600 / teal-400 (D-62)
} satisfies ChartConfig;

const shortDate = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short" });
const longDate = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short", year: "numeric" });

// week_start is a plain date ("2026-10-05"). Reading it as local midnight keeps the day from shifting.
const asDate = (isoDate: string) => new Date(`${isoDate}T00:00:00`);

/**
 * Hover/focus readout (dataviz interaction rules): the value leads in strong text, the week follows in
 * muted text, keyed by a short line in the series colour. Text is never in the series colour.
 */
function WeekTooltip({ active, payload }: TooltipContentProps) {
  const week = payload?.[0]?.payload as Schemas["WeekCollected"] | undefined;
  if (!active || !week) return null;
  return (
    <div className="rounded-lg border bg-background px-3 py-2 shadow-lg">
      <p className="text-sm font-semibold tabular-nums">{formatNaira(week.collected_kobo)}</p>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="h-0.5 w-3 rounded-full bg-(--color-collected_kobo)" aria-hidden />
        Week of {longDate.format(asDate(week.week_start))}
      </p>
    </div>
  );
}

export function CollectionsChart({ weeks }: { weeks: Schemas["WeekCollected"][] | undefined }) {
  const total = weeks?.reduce((sum, week) => sum + week.collected_kobo, 0) ?? 0;

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle>Collections by week</CardTitle>
        <CardDescription>
          Money matched to invoices, by the week it arrived.{" "}
          {weeks && <span className="tabular-nums">{formatNaira(total)} over 8 weeks.</span>}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!weeks ? (
          <Skeleton className="h-56 w-full" />
        ) : total === 0 ? (
          <p className="flex h-56 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
            No payments matched to invoices in the last 8 weeks.
          </p>
        ) : (
          <>
            <ChartContainer config={config} className="aspect-auto h-56 w-full">
              <BarChart data={weeks} margin={{ top: 8, right: 4, left: 4, bottom: 0 }} accessibilityLayer>
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="week_start"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  tickFormatter={(value: string) => shortDate.format(asDate(value))}
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={64}
                  tickFormatter={(value: number) => compactNaira(Math.round(value))}
                />
                <ChartTooltip cursor={{ fillOpacity: 0.5 }} content={WeekTooltip} />
                {/* No grow-in animation: numbers shouldn't move (MASTER.md §5), and on a slow device the
                    columns sat at zero height until the animation caught up. */}
                <Bar
                  dataKey="collected_kobo"
                  fill="var(--color-collected_kobo)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={24}
                  isAnimationActive={false}
                />
              </BarChart>
            </ChartContainer>
            {/* The same numbers without hovering: for keyboard, screen reader and anyone checking exact values. */}
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-muted-foreground">View as table</summary>
              <table className="mt-2 w-full">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground">
                    <th className="py-1 font-medium">Week of</th>
                    <th className="py-1 text-right font-medium">Collected</th>
                  </tr>
                </thead>
                <tbody>
                  {weeks.map((week) => (
                    <tr key={week.week_start} className="border-t">
                      <td className="py-1">{longDate.format(asDate(week.week_start))}</td>
                      <td className="py-1 text-right tabular-nums">{formatNaira(week.collected_kobo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </CardContent>
    </Card>
  );
}
