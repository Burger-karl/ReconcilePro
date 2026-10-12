"use client";

/**
 * One audit event in full: what happened, who, exactly when, everything recorded with it, and links to
 * the thing it is about. Audit rows are never edited or deleted (invariant 7), so there are no actions here.
 */

import Link from "next/link";

import { Button } from "@/components/ui/button";
import type { Schemas } from "@/lib/api";
import { describeEvent, eventDetails, eventLinks, formatDateTime } from "@/lib/audit-text";
import { formatNaira } from "@/lib/money";

export function EventDetails({ event }: { event: Schemas["AuditEventRead"] }) {
  const { text, amountKobo } = describeEvent(event);
  const details = eventDetails(event, formatNaira);
  const links = eventLinks(event);

  return (
    <div className="flex flex-col gap-4 p-5">
      <header>
        <p className="font-medium">{text}</p>
        {amountKobo !== null && <p className="text-xl font-semibold tabular-nums">{formatNaira(amountKobo)}</p>}
      </header>

      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">By</dt>
        <dd>{event.actor_email ?? "System (automatic, or someone not signed in)"}</dd>
        <dt className="text-muted-foreground">When</dt>
        <dd>
          <time dateTime={event.created_at}>{formatDateTime(event.created_at)}</time>
        </dd>
        <dt className="text-muted-foreground">Action</dt>
        <dd className="font-mono text-xs">{event.action}</dd>
      </dl>

      {details.length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Recorded details</h3>
          {/* Values may come from what people typed (names, reasons), so they are shown as plain text only. */}
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg border bg-background p-3 text-sm">
            {details.map((row, index) => (
              <div key={`${row.label}-${index}`} className="contents">
                <dt className="text-muted-foreground">{row.label}</dt>
                <dd className="break-words tabular-nums">{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {links.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {links.map((link) => (
            <Button key={link.href} asChild variant="outline" size="sm">
              <Link href={link.href}>{link.label}</Link>
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
