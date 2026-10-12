"use client";

import Link from "next/link";

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Schemas } from "@/lib/api";
import { describeEvent, formatDateTime, timeAgo } from "@/lib/audit-text";
import { formatNaira } from "@/lib/money";

/** The last 8 audit events (pages/dashboard.md §3): what happened, who did it, when, how much. */
export function RecentActivity({ events }: { events: Schemas["AuditEventRead"][] | undefined }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent activity</CardTitle>
        <CardDescription>Every change is recorded and can&apos;t be edited.</CardDescription>
        <CardAction>
          <Link href="/audit" className="text-sm font-medium underline underline-offset-4">
            View all
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent>
        {!events ? (
          <Skeleton className="h-64 w-full" />
        ) : events.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing has happened yet. Add a customer to get started.</p>
        ) : (
          <ul className="divide-y">
            {events.map((event) => {
              const { text, amountKobo } = describeEvent(event);
              return (
                <li key={event.id} className="flex items-center justify-between gap-4 py-2.5 text-sm">
                  <div className="min-w-0">
                    <p className="truncate">{text}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {event.actor_email ?? "System"} ·{" "}
                      <time dateTime={event.created_at} title={formatDateTime(event.created_at)}>
                        {timeAgo(event.created_at)}
                      </time>
                    </p>
                  </div>
                  {amountKobo !== null && (
                    <span className="shrink-0 font-medium tabular-nums">{formatNaira(amountKobo)}</span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
