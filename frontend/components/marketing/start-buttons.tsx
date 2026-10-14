"use client";

/**
 * The landing page's main buttons. A visitor gets "Create free workspace" (and, in the hero, "Sign in");
 * someone already signed in gets "Open your dashboard" instead, so no button leads to a page that would only
 * say "you're already signed in". Until the browser knows (auth loading), the visitor version shows, which
 * is also what the server-rendered HTML contains.
 */

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

// Landing-page buttons: 44px tall (this shadcn style's "lg" is only 36px), easy to hit on a phone.
const CTA = "h-11 px-5 text-base";

export function StartButtons({
  primaryClassName,
  withSignIn = false,
}: {
  /** Extra classes for the main button (the closing band uses white on navy). */
  primaryClassName?: string;
  /** The hero also offers "Sign in" next to the main button. */
  withSignIn?: boolean;
}) {
  const signedIn = useAuth().status === "signed-in";
  return (
    <>
      <Button asChild size="lg" className={cn(CTA, "group", primaryClassName)}>
        <Link href={signedIn ? "/dashboard" : "/register"}>
          {signedIn ? "Open your dashboard" : "Create free workspace"}
          {/* Slides right on hover: transform only, the button keeps its size. */}
          <ArrowRight className="transition-transform duration-200 group-hover:translate-x-1" aria-hidden />
        </Link>
      </Button>
      {withSignIn && !signedIn && (
        <Button asChild size="lg" variant="outline" className={cn(CTA, "bg-background")}>
          <Link href="/login">Sign in</Link>
        </Button>
      )}
    </>
  );
}
