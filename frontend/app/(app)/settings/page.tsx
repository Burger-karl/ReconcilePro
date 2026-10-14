"use client";

/**
 * Settings: the bank account customers pay into by transfer (backend D-61). It is printed on every public
 * invoice next to the payment reference. Only the owner can change it (the API answers 403 to a member):
 * changing where money goes is a classic fraud move, so every change is in the Audit log with old and new.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Screen } from "@/components/app-shell/screen";
import { FormError } from "@/components/auth/auth-card";
import { TextField } from "@/components/auth/text-field";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { API, ApiError, api, type Schemas } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Mirrors the API (backend workspaces/schemas.py): all three required; a NUBAN is exactly 10 digits.
const schema = z.object({
  bank_name: z.string().trim().min(2, "Enter the bank's name").max(100),
  bank_account_number: z
    .string()
    .trim()
    .regex(/^\d{10}$/, "Nigerian account numbers are exactly 10 digits"),
  bank_account_name: z.string().trim().min(2, "Enter the name on the account").max(200),
});
type Values = z.infer<typeof schema>;

export default function SettingsPage() {
  const auth = useAuth();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { bank_name: "", bank_account_number: "", bank_account_name: "" },
  });
  const me = auth.status === "signed-in" ? auth.me : null;
  const workspace = me?.workspace ?? null;

  // Fill the form with what is saved, once the signed-in user (and their workspace) has loaded.
  useEffect(() => {
    if (!workspace) return;
    form.reset({
      bank_name: workspace.bank_name ?? "",
      bank_account_number: workspace.bank_account_number ?? "",
      bank_account_name: workspace.bank_account_name ?? "",
    });
  }, [workspace, form]);

  async function onSubmit(values: Values) {
    setError(null);
    try {
      await api<Schemas["WorkspaceRead"]>(`${API}/workspace/bank-details`, { method: "PUT", body: values });
      toast.success("Bank details saved. They now show on every invoice.");
      auth.retry(); // reload /auth/me so the saved details are the new starting point
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  return (
    <Screen title="Settings" description="How customers pay you by bank transfer.">
      {!me ? (
        <Skeleton className="h-80 max-w-lg" />
      ) : (
        <section className="flex max-w-lg flex-col gap-4 rounded-xl border bg-card p-6">
          <div className="flex flex-col gap-1">
            <h2 className="font-semibold">Bank account for transfers</h2>
            <p className="text-sm text-muted-foreground">
              Shown on every invoice link, next to the payment reference your customers should quote.
            </p>
          </div>

          {me.user.role !== "owner" ? (
            // A member sees what customers see, but can't change it.
            <p className="text-sm">
              {workspace?.bank_account_number
                ? `${workspace.bank_name} · ${workspace.bank_account_number} · ${workspace.bank_account_name}`
                : "No bank account saved yet."}{" "}
              <span className="text-muted-foreground">Only the workspace owner can change this.</span>
            </p>
          ) : (
            <>
              <FormError message={error} />
              <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
                <FieldGroup>
                  <TextField control={form.control} name="bank_name" label="Bank" />
                  <TextField
                    control={form.control}
                    name="bank_account_number"
                    label="Account number"
                    inputMode="numeric"
                    description="10 digits (NUBAN). Check it carefully: customers send money here."
                  />
                  <TextField
                    control={form.control}
                    name="bank_account_name"
                    label="Account name"
                    description="As the bank shows it, so customers recognise it when they transfer."
                  />
                </FieldGroup>
                <Button type="submit" className="self-start" disabled={form.formState.isSubmitting}>
                  {form.formState.isSubmitting ? "Saving…" : "Save bank details"}
                </Button>
              </form>
            </>
          )}
        </section>
      )}
    </Screen>
  );
}
