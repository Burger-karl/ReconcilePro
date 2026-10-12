"use client";

/**
 * "Allocate part…" (pages/reconciliation.md): put some or all of a bank credit against one invoice.
 * Opened from a candidate card (invoice fixed), or with M and no card selected (pick any open invoice).
 *
 * The amount is typed in naira and turned into kobo by parseNairaToKobo (text, never a float).
 * The limits checked here are only for quick feedback: allocate() on the server re-checks both sides
 * under a row lock (invariant 4), and its message is shown if it refuses.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import useSWR from "swr";
import { z } from "zod";

import { FormError } from "@/components/auth/auth-card";
import { TextField } from "@/components/auth/text-field";
import { type InvoiceStatus, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { FieldGroup } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { API, ApiError, api, type Schemas } from "@/lib/api";
import { formatNaira, parseNairaToKobo } from "@/lib/money";
import { cn } from "@/lib/utils";

type Credit = Schemas["TransactionRead"];
type Allocation = Schemas["AllocationRead"];
type Target = { invoice_id: string; invoice_number: string; customer_name: string; outstanding_kobo: number };

const OPEN = ["sent", "part_paid", "overdue"];

/** Kobo as plain text for the input: 8062500 → "80625.00" (no ₦ or commas, so it is easy to edit). */
const asInput = (kobo: number) => `${Math.floor(kobo / 100)}.${String(kobo % 100).padStart(2, "0")}`;

export function AllocateDialog({
  credit,
  target,
  open,
  onOpenChange,
  onAllocated,
}: {
  credit: Credit;
  /** The invoice, when opened from a candidate card. Null = let the accountant search for one. */
  target: Target | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAllocated: (allocation: Allocation, invoiceNumber: string) => void;
}) {
  const [picked, setPicked] = useState<Target | null>(target);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const invoice = target ?? picked;
  const maxKobo = invoice ? Math.min(credit.unallocated_kobo, invoice.outstanding_kobo) : credit.unallocated_kobo;

  const schema = z.object({
    amount: z.string().refine((text) => {
      const kobo = parseNairaToKobo(text);
      return kobo !== null && kobo > 0 && kobo <= maxKobo;
    }, `Enter an amount from ₦0.01 up to ${formatNaira(maxKobo)}`),
  });
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { amount: asInput(maxKobo) } });

  // Each time the dialog opens (or a different invoice is picked), start from the largest allowed amount.
  useEffect(() => {
    if (open) form.reset({ amount: asInput(maxKobo) });
  }, [open, maxKobo, form]);

  // Searching only runs while no invoice is fixed. The list endpoint filters by workspace on the server.
  const { data: found } = useSWR<Schemas["InvoiceList"]>(
    open && !target ? `${API}/invoices?limit=20${search.trim() ? `&q=${encodeURIComponent(search.trim())}` : ""}` : null,
  );
  const openInvoices = (found?.items ?? []).filter((item) => OPEN.includes(item.status));

  async function onSubmit(values: z.infer<typeof schema>) {
    if (!invoice) return;
    setError(null);
    try {
      const allocation = await api<Allocation>(`${API}/reconciliation/allocate`, {
        method: "POST",
        body: {
          transaction_id: credit.id,
          invoice_id: invoice.invoice_id,
          amount_kobo: parseNairaToKobo(values.amount),
          method: "manual",
        },
      });
      onAllocated(allocation, invoice.invoice_number);
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setPicked(null);
          setSearch("");
          setError(null);
        }
        onOpenChange(next);
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{target ? `Allocate to ${target.invoice_number}` : "Match to an invoice"}</DialogTitle>
          <DialogDescription>
            {formatNaira(credit.unallocated_kobo)} of this payment is still unmatched. Whatever you don&apos;t
            allocate stays in the queue.
          </DialogDescription>
        </DialogHeader>

        <FormError message={error} />

        {!target && (
          <div className="flex flex-col gap-2">
            <label htmlFor="invoice-search" className="text-sm font-medium">
              Invoice
            </label>
            <Input
              id="invoice-search"
              placeholder="Search by number, reference or customer"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="text-base"
            />
            <ul className="max-h-48 overflow-y-auto rounded-md border" aria-label="Open invoices">
              {openInvoices.length === 0 && (
                <li className="px-3 py-2 text-sm text-muted-foreground">{found ? "No open invoices found." : "Loading…"}</li>
              )}
              {openInvoices.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() =>
                      setPicked({
                        invoice_id: item.id,
                        invoice_number: item.number,
                        customer_name: item.customer_name,
                        outstanding_kobo: item.outstanding_kobo,
                      })
                    }
                    className={cn(
                      "flex w-full cursor-pointer items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-muted/50",
                      picked?.invoice_id === item.id && "bg-muted",
                    )}
                    aria-pressed={picked?.invoice_id === item.id}
                  >
                    <span className="min-w-0">
                      <span className="font-mono">{item.number}</span>{" "}
                      <span className="text-muted-foreground">{item.customer_name}</span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <StatusBadge status={item.status as InvoiceStatus} />
                      <span className="tabular-nums">{formatNaira(item.outstanding_kobo)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <form id="allocate-form" onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <TextField
              control={form.control}
              name="amount"
              label="Amount (₦)"
              description={invoice ? `At most ${formatNaira(maxKobo)}.` : "Pick an invoice first."}
            />
          </FieldGroup>
        </form>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" form="allocate-form" disabled={!invoice || form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Saving…" : "Allocate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
