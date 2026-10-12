"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthCard, FormError } from "@/components/auth/auth-card";
import { TextField } from "@/components/auth/text-field";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { API, ApiError, api, type Schemas } from "@/lib/api";

const schema = z.object({ email: z.email("Enter a valid email address") });
type Values = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [sentMessage, setSentMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "" } });

  async function onSubmit(values: Values) {
    setError(null);
    try {
      // The API answers the same for every email (backend D-39), so this page can't reveal who has an account.
      const response = await api<Schemas["MessageResponse"]>(`${API}/auth/forgot-password`, {
        method: "POST",
        body: values,
      });
      setSentMessage(response.detail);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  const backToSignIn = (
    <Link href="/login" className="font-medium text-foreground underline underline-offset-4">
      Back to sign in
    </Link>
  );

  if (sentMessage) {
    return (
      <AuthCard title="Check your email" footer={backToSignIn}>
        <div className="flex gap-3 text-sm">
          <MailCheck className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden />
          <p>
            {sentMessage} The link works once, for 30 minutes. Check your spam folder if it doesn&apos;t arrive.
          </p>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Reset your password"
      description="Enter the email you sign in with and we'll send you a link to choose a new password."
      footer={backToSignIn}
    >
      <FormError message={error} />
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
        <FieldGroup>
          <TextField control={form.control} name="email" label="Email" type="email" autoComplete="email" />
        </FieldGroup>
        <Button type="submit" size="lg" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Sending…" : "Send reset link"}
        </Button>
      </form>
    </AuthCard>
  );
}
