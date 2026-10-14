"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AlreadySignedIn } from "@/components/auth/already-signed-in";
import { AuthCard, FormError, OrDivider } from "@/components/auth/auth-card";
import { TextField } from "@/components/auth/text-field";
import { GOOGLE_SIGN_IN_ENABLED, GoogleSignInButton } from "@/components/google-sign-in-button";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { API, ApiError, api, type Schemas } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Same rules as the API (backend auth/schemas.py), so most mistakes are caught before a request is sent.
const workspaceName = z.string().trim().min(1, "Enter your business name").max(200);
const schema = z.object({
  workspace_name: workspaceName,
  email: z.email("Enter a valid email address"),
  password: z.string().min(8, "Use at least 8 characters").max(128, "Use at most 128 characters"),
});
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const auth = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  // True from the moment this form creates the account, so the "already signed in" card doesn't flash up.
  const [signingIn, setSigningIn] = useState(false);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { workspace_name: "", email: "", password: "" },
  });

  async function finish(request: Promise<Schemas["TokenResponse"]>) {
    setError(null);
    try {
      const token = await request;
      setSigningIn(true);
      await auth.signIn(token);
      router.replace("/dashboard");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  const onSubmit = (values: Values) =>
    finish(api(`${API}/auth/register`, { method: "POST", body: values }));

  // Google gives us the person, not the business: the workspace name still has to come from this form.
  async function onGoogle(credential: string) {
    const valid = await form.trigger("workspace_name");
    if (!valid) {
      setError("Enter your business name first, then continue with Google.");
      return;
    }
    await finish(
      api(`${API}/auth/google/register`, {
        method: "POST",
        body: { credential, workspace_name: form.getValues("workspace_name") },
      }),
    );
  }

  // Already signed in (e.g. clicked "Create free workspace" on the landing page): say so, rather than
  // redirecting silently. Signing out there brings this form back, to register another business.
  if (auth.status === "signed-in" && !signingIn) return <AlreadySignedIn />;

  return (
    <AuthCard
      title="Create your workspace"
      description="One workspace per business. You'll be its owner."
      footer={
        <span>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-foreground underline underline-offset-4">
            Sign in
          </Link>
        </span>
      }
    >
      <FormError message={error} />
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
        <FieldGroup>
          <TextField
            control={form.control}
            name="workspace_name"
            label="Business name"
            autoComplete="organization"
            description="Shown to your customers on invoices."
          />
        </FieldGroup>
        {GOOGLE_SIGN_IN_ENABLED && (
          <>
            <GoogleSignInButton text="signup_with" onCredential={onGoogle} />
            <OrDivider />
          </>
        )}
        <FieldGroup>
          <TextField control={form.control} name="email" label="Email" type="email" autoComplete="email" />
          <TextField
            control={form.control}
            name="password"
            label="Password"
            type="password"
            autoComplete="new-password"
            description="At least 8 characters."
          />
        </FieldGroup>
        <Button type="submit" size="lg" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Creating workspace…" : "Create workspace"}
        </Button>
      </form>
    </AuthCard>
  );
}
