"use client";

/**
 * "/" for now: straight into the app if signed in, otherwise to sign in.
 * Becomes the marketing landing page in slice F9 (design-system MASTER.md §7).
 */

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";

export default function Home() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.status === "signed-in") router.replace("/dashboard");
    else if (auth.status === "signed-out") router.replace("/login");
  }, [auth.status, router]);

  return <div className="flex-1 bg-canvas" aria-busy="true" />;
}
