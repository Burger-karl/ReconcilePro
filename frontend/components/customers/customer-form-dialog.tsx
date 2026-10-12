"use client";

/**
 * Add or edit a customer. Aliases are the names this customer appears under on bank statements
 * ("KOLA AND SONS LTD" for "Kola & Sons"): the matcher compares the payer name with the name AND every
 * alias, worth up to 30 of the 100 match points (backend D-25). One alias per line, because a bank name can
 * itself contain a comma.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { FormError } from "@/components/auth/auth-card";
import { TextField } from "@/components/auth/text-field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { API, ApiError, api, type Schemas } from "@/lib/api";

type Customer = Schemas["CustomerRead"];

const toLines = (text: string) =>
  text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

// Mirrors the API (backend customers/schemas.py): name required, email valid or blank, at most 20 aliases.
const schema = z.object({
  name: z.string().trim().min(1, "Enter the customer's name").max(200),
  email: z.union([z.literal(""), z.email("Enter a valid email address, or leave it blank")]),
  phone: z.string().trim().max(40),
  aliases: z.string().refine((text) => toLines(text).length <= 20, "At most 20 aliases"),
});
type Values = z.infer<typeof schema>;

export function CustomerFormDialog({
  open,
  onOpenChange,
  customer,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The customer to edit; leave out to add a new one. */
  customer?: Customer;
  onSaved: (customer: Customer) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: customer?.name ?? "",
      email: customer?.email ?? "",
      phone: customer?.phone ?? "",
      aliases: (customer?.aliases ?? []).join("\n"),
    });
  }, [open, customer, form]);

  async function onSubmit(values: Values) {
    setError(null);
    // An empty email or phone is sent as null, which clears it on the server.
    const body = {
      name: values.name,
      email: values.email.trim() || null,
      phone: values.phone.trim() || null,
      aliases: toLines(values.aliases),
    };
    try {
      const saved = customer
        ? await api<Customer>(`${API}/customers/${customer.id}`, { method: "PATCH", body })
        : await api<Customer>(`${API}/customers`, { method: "POST", body });
      onSaved(saved);
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setError(null);
        onOpenChange(next);
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{customer ? `Edit ${customer.name}` : "Add a customer"}</DialogTitle>
          <DialogDescription>Only the name is required.</DialogDescription>
        </DialogHeader>

        <FormError message={error} />

        <form id="customer-form" onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <TextField control={form.control} name="name" label="Name" autoComplete="organization" />
            <TextField
              control={form.control}
              name="email"
              label="Email"
              type="email"
              description="Needed for online payment: Paystack sends the receipt here."
            />
            <TextField control={form.control} name="phone" label="Phone" autoComplete="tel" />
            <Controller
              control={form.control}
              name="aliases"
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="aliases">Names on bank statements</FieldLabel>
                  <Textarea
                    {...field}
                    id="aliases"
                    rows={3}
                    placeholder={"KOLA AND SONS\nKOLA&SONS LTD"}
                    aria-invalid={fieldState.invalid}
                    className="font-mono text-base sm:text-sm"
                  />
                  {fieldState.invalid ? (
                    <FieldError errors={[fieldState.error]} />
                  ) : (
                    <FieldDescription>
                      One per line. Payments from these names are matched to this customer.
                    </FieldDescription>
                  )}
                </Field>
              )}
            />
          </FieldGroup>
        </form>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" form="customer-form" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Saving…" : customer ? "Save changes" : "Add customer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
