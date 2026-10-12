"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CircleCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthCard, FormError } from "@/components/auth/auth-card";
import { TextField } from "@/components/auth/text-field";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { API, ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const schema = z
  .object({
    new_password: z.string().min(8, "Use at least 8 characters").max(128, "Use at most 128 characters"),
    confirm: z.string(),
  })
  .refine((values) => values.new_password === values.confirm, {
    message: "The two passwords don't match",
    path: ["confirm"],
  });
type Values = z.infer<typeof schema>;

/**
 * The emailed link is /reset-password#token=... The token is after "#", which browsers never send to any
 * server (backend D-40), so it can't leak into server logs. Only this page's JavaScript can read it.
 */
function tokenFromHash(): string | null {
  return new URLSearchParams(window.location.hash.slice(1)).get("token");
}

export default function ResetPasswordPage() {
  const auth = useAuth();
  // undefined = not read yet (the hash only exists in the browser); null = the link has no token.
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { new_password: "", confirm: "" } });

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the hash can only be read after mounting
    setToken(tokenFromHash());
    // Remove the token from the address bar and history, so it isn't left behind on a shared computer.
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function onSubmit(values: Values) {
    setError(null);
    try {
      await api(`${API}/auth/reset-password`, {
        method: "POST",
        body: { token, new_password: values.new_password },
      });
      // The reset logged out every session (backend D-41), including one in this browser.
      if (auth.status === "signed-in") auth.signOut();
      setDone(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  const askForNewLink = (
    <Link href="/forgot-password" className="font-medium text-foreground underline underline-offset-4">
      Get a new link
    </Link>
  );

  if (done) {
    return (
      <AuthCard title="Password changed">
        <div className="flex gap-3 text-sm">
          <CircleCheck className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden />
          <p>Your new password is set, and you&apos;ve been signed out everywhere else.</p>
        </div>
        <Button asChild size="lg">
          <Link href="/login">Sign in</Link>
        </Button>
      </AuthCard>
    );
  }

  if (token === null) {
    return (
      <AuthCard title="This link is incomplete" footer={askForNewLink}>
        <p className="text-sm text-muted-foreground">
          Open the link from your email again, or ask for a new one.
        </p>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Choose a new password" footer={askForNewLink}>
      <FormError message={error} />
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
        <FieldGroup>
          <TextField
            control={form.control}
            name="new_password"
            label="New password"
            type="password"
            autoComplete="new-password"
            description="At least 8 characters."
          />
          <TextField control={form.control} name="confirm" label="Type it again" type="password" autoComplete="new-password" />
        </FieldGroup>
        <Button type="submit" size="lg" disabled={!token || form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Saving…" : "Set new password"}
        </Button>
      </form>
    </AuthCard>
  );
}
