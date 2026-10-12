"use client";

/**
 * Create an invoice, or edit one while it is still a draft (the API refuses edits after sending: 409).
 *
 * The amount is typed in naira and sent as integer kobo (parseNairaToKobo works on the text, never a float).
 * VAT and the total are NOT worked out here: the server computes them (backend D-02, 7.5% rounded half up)
 * and the saved invoice shows its figures. One place doing money maths means no two answers to disagree.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import useSWR from "swr";
import { z } from "zod";

import { FormError } from "@/components/auth/auth-card";
import { TextField } from "@/components/auth/text-field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { API, ApiError, api, type Schemas } from "@/lib/api";
import { parseNairaToKobo } from "@/lib/money";

type Invoice = Schemas["InvoiceRead"];

/** "2026-10-12" for today in the browser's time zone (what a date input expects). */
function isoDay(offsetDays = 0): string {
  const day = new Date();
  day.setDate(day.getDate() + offsetDays);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

const asInput = (kobo: number) => `${Math.floor(kobo / 100)}.${String(kobo % 100).padStart(2, "0")}`;

// Mirrors the API's rules (backend invoices/schemas.py) so most mistakes are caught before sending.
const schema = z
  .object({
    customer_id: z.string().min(1, "Choose a customer"),
    description: z.string().trim().min(1, "Describe what was sold").max(500),
    amount: z.string().refine((text) => {
      const kobo = parseNairaToKobo(text);
      return kobo !== null && kobo > 0;
    }, "Enter an amount in naira, e.g. 90,000 or 1250.50"),
    issue_date: z.string().min(1, "Choose the issue date"),
    due_date: z.string().min(1, "Choose the due date"),
  })
  .refine((values) => values.due_date >= values.issue_date, {
    message: "The due date can't be before the issue date",
    path: ["due_date"],
  });
type Values = z.infer<typeof schema>;

export function InvoiceFormDialog({
  open,
  onOpenChange,
  invoice,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** A draft to edit; leave out to create a new invoice. */
  invoice?: Invoice;
  onSaved: (invoice: Invoice) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const { data: customers } = useSWR<Schemas["CustomerList"]>(open ? `${API}/customers?limit=200` : null);

  const form = useForm<Values>({ resolver: zodResolver(schema) });

  // Fill the form every time it opens: blank for a new invoice, the draft's values when editing.
  useEffect(() => {
    if (!open) return;
    form.reset(
      invoice
        ? {
            customer_id: invoice.customer_id,
            description: invoice.description,
            amount: asInput(invoice.subtotal_kobo),
            issue_date: invoice.issue_date,
            due_date: invoice.due_date,
          }
        : { customer_id: "", description: "", amount: "", issue_date: isoDay(), due_date: isoDay(14) },
    );
  }, [open, invoice, form]);

  async function onSubmit(values: Values) {
    setError(null);
    const body = {
      customer_id: values.customer_id,
      description: values.description,
      subtotal_kobo: parseNairaToKobo(values.amount),
      issue_date: values.issue_date,
      due_date: values.due_date,
    };
    try {
      const saved = invoice
        ? await api<Invoice>(`${API}/invoices/${invoice.id}`, { method: "PATCH", body })
        : await api<Invoice>(`${API}/invoices`, { method: "POST", body });
      onSaved(saved);
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  const noCustomers = customers && customers.items.length === 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setError(null); // start clean next time it opens
        onOpenChange(next);
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{invoice ? `Edit ${invoice.number}` : "New invoice"}</DialogTitle>
          <DialogDescription>
            Saved as a draft. VAT (7.5%) and the total are worked out when you save.
          </DialogDescription>
        </DialogHeader>

        <FormError message={error} />

        {noCustomers ? (
          <p className="text-sm">
            Add a customer first.{" "}
            <Link href="/customers" className="font-medium underline underline-offset-4">
              Go to Customers
            </Link>
          </p>
        ) : (
          <form id="invoice-form" onSubmit={form.handleSubmit(onSubmit)} noValidate>
            <FieldGroup>
              <Controller
                control={form.control}
                name="customer_id"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="customer_id">Customer</FieldLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="customer_id" aria-invalid={fieldState.invalid} className="w-full text-base">
                        <SelectValue placeholder={customers ? "Choose a customer" : "Loading…"} />
                      </SelectTrigger>
                      <SelectContent>
                        {customers?.items.map((customer) => (
                          <SelectItem key={customer.id} value={customer.id}>
                            {customer.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
                  </Field>
                )}
              />
              <TextField control={form.control} name="description" label="What was sold" />
              <TextField
                control={form.control}
                name="amount"
                label="Amount before VAT (₦)"
                description="VAT is added on top by the server."
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <TextField control={form.control} name="issue_date" label="Issue date" type="date" />
                <TextField control={form.control} name="due_date" label="Due date" type="date" />
              </div>
              {!invoice && (
                <FieldDescription>
                  A number (INV-0001…) and a payment reference are given to the invoice when it is saved.
                </FieldDescription>
              )}
            </FieldGroup>
          </form>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" form="invoice-form" disabled={noCustomers || form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Saving…" : invoice ? "Save changes" : "Save draft"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
