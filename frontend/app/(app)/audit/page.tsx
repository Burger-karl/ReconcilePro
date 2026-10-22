"use client";

/**
 * Audit log (slice F7): every recorded change in the workspace, newest first (invariant 7: manual actions
 * always write a row; rows are never edited or deleted). Read-only. Layout C: list + inspector on wide
 * screens; on phones the selected event's details open under its row.
 */

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import useSWR from "swr";

import { Screen } from "@/components/app-shell/screen";
import { EventDetails } from "@/components/audit/event-details";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { API, type Schemas } from "@/lib/api";
import { describeEvent, formatDateTime, timeAgo } from "@/lib/audit-text";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

type Event = Schemas["AuditEventRead"];

// Each tab is the API's entity_type filter (the backend's record() calls).
const TABS = [
  { type: "", label: "All" },
  { type: "invoice", label: "Invoices" },
  { type: "allocation", label: "Payments" },
  { type: "transaction", label: "Bank lines" },
  { type: "customer", label: "Customers" },
  { type: "statement", label: "Imports" },
  { type: "user", label: "Sign-in & security" },
  { type: "workspace", label: "Settings" },
] as const;
const PAGE = 50;

export default function AuditPage() {
  // useSearchParams() needs a Suspense boundary in the App Router (Next 16 docs: use-search-params).
  return (
    <Suspense>
      <AuditScreen />
    </Suspense>
  );
}

function AuditScreen() {
  // The dashboard's "Auto-match rate" tile links here with ?type=allocation (D-70).
  const searchParams = useSearchParams();
  const [type, setType] = useState<(typeof TABS)[number]["type"]>(
    () => TABS.find((tab) => tab.type === searchParams.get("type"))?.type ?? "",
  );
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Event | null>(null);

  const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
  if (type) params.set("entity_type", type);
  const { data, error, isLoading } = useSWR<Schemas["AuditEventList"]>(`${API}/audit?${params}`);

  return (
    <Screen
      title="Audit log"
      description="Every change, who made it and when. Nothing here can be edited or deleted."
      inspector={
        selected ? (
          <EventDetails event={selected} />
        ) : (
          <p className="p-5 text-sm text-muted-foreground">Select an event to see everything recorded with it.</p>
        )
      }
    >
      <div className="flex flex-col gap-4">
        <div role="tablist" aria-label="Filter by what changed" className="flex flex-wrap gap-1">
          {TABS.map((tab) => (
            <Button
              key={tab.label}
              role="tab"
              aria-selected={type === tab.type}
              size="sm"
              variant={type === tab.type ? "default" : "ghost"}
              onClick={() => {
                setType(tab.type);
                setOffset(0);
                setSelected(null);
              }}
            >
              {tab.label}
            </Button>
          ))}
        </div>

        {error ? (
          <p className="text-sm text-muted-foreground">{error instanceof Error ? error.message : "Couldn't load the audit log."}</p>
        ) : isLoading || !data ? (
          <Skeleton className="h-96 w-full" />
        ) : data.items.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
            Nothing recorded here yet.
          </div>
        ) : (
          <ul className="divide-y rounded-lg border">
            {data.items.map((event) => {
              const { text, amountKobo } = describeEvent(event);
              const isSelected = selected?.id === event.id;
              return (
                <li key={event.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(isSelected ? null : event)}
                    aria-expanded={isSelected}
                    className={cn(
                      "flex w-full cursor-pointer items-center justify-between gap-4 px-4 py-3 text-left text-sm hover:bg-muted/50",
                      isSelected && "bg-muted",
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block truncate">{text}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {event.actor_email ?? "System"} ·{" "}
                        <time dateTime={event.created_at} title={formatDateTime(event.created_at)}>
                          {timeAgo(event.created_at)}
                        </time>
                      </span>
                    </span>
                    {amountKobo !== null && (
                      <span className="shrink-0 font-medium tabular-nums">{formatNaira(amountKobo)}</span>
                    )}
                  </button>
                  {/* Phones have no inspector: the details open under the row instead. */}
                  {isSelected && (
                    <div className="border-t bg-canvas lg:hidden">
                      <EventDetails event={event} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {data && data.total > PAGE && (
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
                Newer
              </Button>
              <Button variant="outline" size="sm" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>
                Older
              </Button>
            </div>
          </div>
        )}
      </div>
    </Screen>
  );
}
