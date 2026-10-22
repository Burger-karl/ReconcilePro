import Image from "next/image";

import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme-toggle";

/**
 * Sign-in, register and password pages in the CEK style (DECISIONS D-71, replacing D-64's navy panel).
 * On wide screens: a photo panel on the left with a dark gradient, the heading's second line in orange and
 * three product facts; the form sits in a white card on CEK's beige. On phones the panel is hidden, so the
 * form comes first.
 */

// Each fact is something the product really does (the rule behind it in brackets for the viva).
const FACTS = [
  { value: "3", label: "ways to match" }, // reference, scored suggestion, by hand
  { value: "0", label: "double counts" }, // invariants 2 and 3
  { value: "₦", label: "to the kobo" }, // invariant 1
];

/** The photo panel (an aside: supporting content next to the form). Hidden below 1024px. */
function PhotoPanel() {
  return (
    <aside className="relative isolate hidden overflow-hidden bg-neutral-950 p-12 text-white lg:flex lg:flex-col lg:justify-between">
      {/* Decoration only: alt="" so screen readers skip it. */}
      <Image src="/images/hero-2.jpg" alt="" fill priority sizes="50vw" className="-z-20 object-cover" />
      <div className="absolute inset-0 -z-10 bg-linear-to-b from-neutral-950/55 to-neutral-950/85" aria-hidden />

      <Logo onDark size={36} className="animate-rise" />

      <div className="animate-rise max-w-md">
        <h2 className="text-4xl leading-tight font-black tracking-tight">
          Embrace clear books. <span className="text-primary">Know who has paid.</span>
        </h2>
        <span className="mt-5 block h-1 w-16 rounded-full bg-primary" aria-hidden />
        <p className="mt-5 text-white/80">
          Sign in to see what you&apos;re owed, what came in this month and the payments waiting for you.
        </p>
      </div>

      <ul className="animate-rise flex flex-wrap gap-3">
        {FACTS.map((fact) => (
          <li key={fact.label} className="rounded-xl border border-white/15 bg-white/10 px-5 py-3">
            <span className="block font-heading text-2xl font-black text-primary">{fact.value}</span>
            <span className="text-sm text-white/75">{fact.label}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid flex-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <PhotoPanel />
      <div className="flex flex-col bg-canvas">
        <header className="flex items-center justify-between px-4 py-3 sm:px-6">
          <Logo className="lg:invisible" />
          <ThemeToggle />
        </header>
        <main className="flex flex-1 items-start justify-center px-4 pt-6 pb-16 sm:items-center sm:pt-0">
          <div className="animate-rise w-full max-w-md">{children}</div>
        </main>
      </div>
    </div>
  );
}
