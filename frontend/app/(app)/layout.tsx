"use client";

/**
 * Every signed-in screen: the session check, then layout C's shell (icon rail + screen).
 *
 * The check here is for the person using the app (send them to sign in instead of showing broken pages).
 * It is NOT the security: the API refuses every request without a valid token (backend invariant 8).
 */

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { SWRConfig } from "swr";

import { Rail } from "@/components/app-shell/rail";
import { Button } from "@/components/ui/button";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, swrFetcher } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (auth.status === "signed-out") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [auth.status, pathname, router]);

  if (auth.status === "unreachable") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="max-w-sm text-sm text-muted-foreground">{auth.message}</p>
        <Button variant="outline" onClick={auth.retry}>
          Try again
        </Button>
      </div>
    );
  }
  if (auth.status !== "signed-in") {
    // Same shape as the real shell, so nothing jumps when it arrives (MASTER.md: skeletons reserve space).
    return (
      <div className="flex flex-1" aria-busy="true" aria-label="Loading">
        <Skeleton className="w-12 rounded-none" />
        <div className="flex flex-1 flex-col gap-4 p-6">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }

  return (
    <SWRConfig
      value={{
        fetcher: swrFetcher,
        // A 401 on any screen means the token stopped working (expired, or a password reset elsewhere).
        onError: (error) => {
          if (error instanceof ApiError && error.status === 401) auth.signOut();
        },
      }}
    >
      {/* Always collapsed to icons on desktop: layout C has a rail, not a full sidebar. */}
      {/* The shell is exactly one screen tall; each screen scrolls inside its own area (so Match's two
          panes can scroll independently, and the rail never scrolls away). */}
      <SidebarProvider open={false} className="h-svh">
        <Rail />
        <SidebarInset className="min-h-0 min-w-0 overflow-hidden bg-wash">
          {/* Phones: the rail becomes a slide-out menu opened from this bar. */}
          <div className="flex items-center gap-2 border-b px-3 py-2 md:hidden">
            <SidebarTrigger aria-label="Open navigation" />
            <span className="font-semibold tracking-tight">Reconcile</span>
          </div>
          {children}
        </SidebarInset>
      </SidebarProvider>
    </SWRConfig>
  );
}
