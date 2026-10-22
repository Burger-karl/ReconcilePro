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
        <Button asChild className="h-10 px-6 text-[15px]">
          <Link href="/dashboard">Open app</Link>
        </Button>
      ) : (
        <>
          <Link href="/login" className="px-2 font-nav text-[15px] text-muted-foreground transition-colors hover:text-brand-ink">
            Sign in
          </Link>
          {/* CEK's orange pill. White text, also on hover, when it turns near-black. */}
          <Button asChild className="hidden h-10 px-6 text-[15px] sm:inline-flex">
            <Link href="/register">Get Started</Link>
          </Button>
        </>
      )}
    </nav>
  );
}
