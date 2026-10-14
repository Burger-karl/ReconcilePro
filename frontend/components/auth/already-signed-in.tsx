"use client";

import { ArrowRight, LogOut } from "lucide-react";
import Link from "next/link";

import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

/**
 * Shown on the login and register pages to someone who is already signed in, instead of silently sending
 * them to the dashboard (which looked like the "Create workspace" button was broken). They can carry on,
 * or sign out here, which brings the form back (e.g. to register a second business).
 */
export function AlreadySignedIn({ continueTo = "/dashboard" }: { continueTo?: string }) {
  const auth = useAuth();
  if (auth.status !== "signed-in") return null;
  const { user, workspace } = auth.me;

  return (
    <AuthCard title="You're already signed in" description={`As ${user.email}, in ${workspace.name}.`}>
      <Button asChild size="lg" className="group">
        <Link href={continueTo}>
          Go to your dashboard
          <ArrowRight className="transition-transform duration-200 group-hover:translate-x-1" aria-hidden />
        </Link>
      </Button>
      {/* Signing out flips the auth state, so the page this sits in shows its form again. */}
      <Button variant="outline" size="lg" onClick={auth.signOut}>
        <LogOut aria-hidden />
        Sign out and use another account
      </Button>
    </AuthCard>
  );
}
