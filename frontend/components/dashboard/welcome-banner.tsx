"use client";

/**
 * The top of Overview in the CEK style (DECISIONS D-71): a photo behind a dark gradient, a greeting with the
 * workspace's name, and the one thing that needs attention in orange. The button goes where the work is:
 * the Match screen when payments are waiting, otherwise Statements to import the next one.
 */

import { ArrowRight } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import type { Schemas } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// "Good morning" by the Lagos clock, since every date in ReconcilePro is a Lagos date (backend D-13).
function greeting(): string {
  const hour = Number(new Intl.DateTimeFormat("en-NG", { hour: "numeric", hourCycle: "h23", timeZone: "Africa/Lagos" }).format(new Date()));
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export function WelcomeBanner({ summary }: { summary: Schemas["Summary"] | undefined }) {
  const auth = useAuth();
  const name = auth.status === "signed-in" ? auth.me.workspace.name : "";
  const waiting = summary?.needs_review_count ?? 0;

  return (
    <section className="relative isolate overflow-hidden rounded-2xl bg-neutral-950 text-white shadow-card">
      {/* Decoration only: alt="" so screen readers skip it. `sizes` lets Next serve a smaller file on phones. */}
      <Image src="/images/hero-1.jpg" alt="" fill priority sizes="(min-width: 1024px) 75vw, 100vw" className="-z-20 object-cover" />
      <div className="absolute inset-0 -z-10 bg-linear-to-r from-neutral-950/90 via-neutral-950/75 to-neutral-950/40" aria-hidden />
      <div className="flex flex-wrap items-center justify-between gap-6 px-6 py-8 sm:px-9">
        <div className="max-w-xl">
          <h2 className="text-2xl font-black tracking-tight sm:text-3xl">
            {greeting()}
            {name && `, ${name}`}.{" "}
            <span className="text-primary">
              {waiting === 0 ? "You're all caught up." : `${waiting} payment${waiting === 1 ? " needs" : "s need"} you.`}
            </span>
          </h2>
          <p className="mt-2 text-white/80">
            {waiting === 0
              ? "Every payment so far is matched. Import your next statement when it arrives."
              : "Everything else was matched automatically. Review the rest in a minute."}
          </p>
        </div>
        <Button asChild size="lg" className="h-11 px-6 text-base hover:bg-white hover:text-neutral-950">
          <Link href={waiting === 0 ? "/statements" : "/match"}>
            {waiting === 0 ? "Import a statement" : "Review payments"}
            <ArrowRight aria-hidden />
          </Link>
        </Button>
      </div>
    </section>
  );
}
