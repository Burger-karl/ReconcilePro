"use client";

/** One customer: contact details, the names they pay under, what they owe, and their invoices. */

import { Mail, Pencil, Phone } from "lucide-react";
import Link from "next/link";
import useSWR from "swr";

import { type InvoiceStatus, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { API, type Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";

type Detail = Schemas["CustomerDetail"];

export function CustomerPanel({ customerId, onEdit }: { customerId: string; onEdit: (customer: Detail) => void }) {
  const { data: customer, error } = useSWR<Detail>(`${API}/customers/${customerId}`);

  if (error) return <p className="p-5 text-sm text-muted-foreground">{error instanceof Error ? error.message : "Couldn't load this customer."}</p>;
  if (!customer) return <Skeleton className="m-5 h-96" />;

  return (
    <div className="flex flex-col gap-5 p-5">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{customer.name}</h2>
          <div className="mt-1 flex flex-col gap-0.5 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Mail className="size-3.5" aria-hidden />
              {customer.email ?? "No email: they can't pay online yet"}
            </span>
            {customer.phone && (
              <span className="flex items-center gap-1.5">
                <Phone className="size-3.5" aria-hidden />
                {customer.phone}
              </span>
            )}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => onEdit(customer)}>
          <Pencil aria-hidden />
          Edit
        </Button>
      </header>

      <div className="rounded-lg border bg-background p-4">
        <p className="text-xs text-muted-foreground">Outstanding</p>
        <p className="text-2xl font-semibold tabular-nums">{formatNaira(customer.outstanding_kobo)}</p>
      </div>

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Names on bank statements</h3>
        {customer.aliases.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            None yet. Add the name their bank shows (e.g. in capitals) so their payments match by name.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {customer.aliases.map((alias) => (
              <li key={alias} className="rounded-md bg-muted px-2 py-0.5 font-mono text-xs">
                {alias}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Invoices ({customer.invoices.length})
        </h3>
        {customer.invoices.length === 0 ? (
          <p className="text-sm text-muted-foreground">No invoices yet.</p>
        ) : (
          <ul className="divide-y rounded-lg border bg-background">
            {customer.invoices.map((invoice) => (
              <li key={invoice.id}>
                <Link
                  href={`/invoices/${invoice.id}`}
                  className="flex items-center justify-between gap-3 px-3 py-2 text-sm hover:bg-muted/50"
                >
                  <span className="flex items-center gap-2">
                    <span className="font-mono">{invoice.number}</span>
                    <StatusBadge status={invoice.status as InvoiceStatus} />
                  </span>
                  <span className="text-right tabular-nums">
                    {formatNaira(invoice.outstanding_kobo)}
                    <span className="block text-xs text-muted-foreground">of {formatNaira(invoice.total_kobo)}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
