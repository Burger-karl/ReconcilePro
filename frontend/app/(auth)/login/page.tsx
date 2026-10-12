"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthCard, FormError, OrDivider } from "@/components/auth/auth-card";
import { TextField } from "@/components/auth/text-field";
import { GOOGLE_SIGN_IN_ENABLED, GoogleSignInButton } from "@/components/google-sign-in-button";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import { API, ApiError, api, type Schemas } from "@/lib/api";
import { safeNextPath, useAuth } from "@/lib/auth";

const schema = z.object({
  email: z.string().trim().min(1, "Enter your email"),
  password: z.string().min(1, "Enter your password"),
});
type Values = z.infer<typeof schema>;

function LoginForm() {
  const auth = useAuth();
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  // Already signed in (e.g. pressed Back): go straight in.
  useEffect(() => {
    if (auth.status === "signed-in") router.replace(next);
  }, [auth.status, next, router]);

  async function finish(request: Promise<Schemas["TokenResponse"]>) {
    setError(null);
    try {
      await auth.signIn(await request);
      router.replace(next);
    } catch (caught) {
      // 401 wrong password, 429 too many attempts (backend D-42), 0 server unreachable: show the API's words.
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    }
  }

  const onSubmit = (values: Values) =>
    finish(api(`${API}/auth/login`, { method: "POST", body: values }));
  const onGoogle = (credential: string) =>
    finish(api(`${API}/auth/google/login`, { method: "POST", body: { credential } }));

  return (
    <AuthCard
      title="Sign in"
      description="Welcome back. Your unmatched payments are waiting."
      footer={
        <span>
          New to Reconcile?{" "}
          <Link href="/register" className="font-medium text-foreground underline underline-offset-4">
            Create a workspace
          </Link>
        </span>
      }
    >
      <FormError message={error} />
      {GOOGLE_SIGN_IN_ENABLED && (
        <>
          <GoogleSignInButton text="signin_with" onCredential={onGoogle} />
          <OrDivider />
        </>
      )}
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
        <FieldGroup>
          <TextField control={form.control} name="email" label="Email" type="email" autoComplete="email" />
          <TextField control={form.control} name="password" label="Password" type="password" autoComplete="current-password" />
        </FieldGroup>
        <div className="flex flex-col gap-3">
          <Button type="submit" size="lg" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
          <Link href="/forgot-password" className="self-center text-sm text-muted-foreground underline underline-offset-4">
            Forgot your password?
          </Link>
        </div>
      </form>
    </AuthCard>
  );
}

export default function LoginPage() {
  // useSearchParams() needs a Suspense boundary in the App Router (Next 16 docs: use-search-params).
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
