"use client";

/** The landing page header's buttons: "Sign in" for visitors, "Open app" for someone already signed in. */

import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

export function AuthNav() {
  const auth = useAuth();
  return (
    <nav className="flex items-center gap-2" aria-label="Account">
      <ThemeToggle />
      {auth.status === "signed-in" ? (
        <Button asChild>
          <Link href="/dashboard">Open app</Link>
        </Button>
      ) : (
        <>
          <Button asChild variant="ghost">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild className="hidden sm:inline-flex">
            <Link href="/register">Create free workspace</Link>
          </Button>
        </>
      )}
    </nav>
  );
}
