import { Check, ShieldCheck, Sigma, Sparkles } from "lucide-react";

import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { formatNaira } from "@/lib/money";

/**
 * Sign-in, register and password pages (DECISIONS D-64). On wide screens: a navy brand panel on the left
 * (what ReconcilePro does, the owner's logo, a floating example of a matched payment) and the form on the right. On phones the
 * panel is hidden, so the form comes first. Motion is CSS only (globals.css) and stops for reduced motion.
 * The glows are radial gradients, not blur filters, so slow machines aren't redrawing them (D-63).
 */

// Each point is something the product really does (the invariant is in brackets for the viva).
const POINTS = [
  { icon: Sparkles, text: "Payments that quote the invoice reference are matched for you" }, // matching
  { icon: Sigma, text: "Every amount kept in whole kobo, never rounded" }, // invariant 1
  { icon: ShieldCheck, text: "A payment is never recorded twice" }, // invariants 2 and 3
];

const order = (i: number) => ({ "--i": i }) as React.CSSProperties;

/** The brand panel (an aside: supporting content next to the form). Hidden below 1024px. */
function BrandPanel() {
  return (
    <aside className="relative isolate hidden overflow-hidden bg-slate-900 p-10 text-white lg:flex lg:flex-col">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden>
        <div className="glow animate-drift absolute -top-40 -left-32 size-[34rem] [--glow:rgb(45_212_191/0.35)]" style={order(0)} />
        <div className="glow animate-drift absolute -right-40 -bottom-40 size-[30rem] [--glow:rgb(34_211_238/0.25)]" style={order(1)} />
        <div className="bg-dots absolute inset-0 opacity-30" />
      </div>

      <Logo onDark size={36} className="animate-rise" />

      <div className="my-auto flex max-w-md flex-col gap-8 py-12">
        <h2 className="animate-rise text-4xl leading-tight font-semibold tracking-tight" style={order(1)}>
          Every payment, matched to the{" "}
          <span className="bg-linear-to-r from-teal-300 to-cyan-300 bg-clip-text text-transparent">right invoice.</span>
        </h2>
        <ul className="flex flex-col gap-4">
          {POINTS.map((point, index) => (
            <li key={point.text} className="animate-rise flex items-center gap-3 text-slate-200" style={order(index + 2)}>
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/10 text-teal-300 ring-1 ring-white/15">
                <point.icon className="size-4" aria-hidden />
              </span>
              {point.text}
            </li>
          ))}
        </ul>

        {/* A floating example card, like the one on the landing page but smaller. Decoration only. */}
        <div className="animate-rise" style={order(5)} aria-hidden>
          <div className="animate-float w-full max-w-sm rounded-2xl border border-white/10 bg-white/5 p-4 shadow-2xl shadow-black/30">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-mono text-xs text-slate-300">NIP/KOLA AND SONS/RCN-4F2K</span>
              <span className="font-semibold tabular-nums">{formatNaira(9_675_000)}</span>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-white/5 px-3 py-2 text-sm">
              <span className="font-mono">INV-0042</span>
              <span className="flex items-center gap-1.5 text-teal-200">
                <span className="animate-pop flex size-5 items-center justify-center rounded-full bg-teal-500 text-slate-900 [animation-delay:1100ms]">
                  <Check className="size-3" />
                </span>
                Matched automatically
              </span>
            </div>
          </div>
        </div>
      </div>

      <p className="animate-rise text-sm text-slate-400" style={order(6)}>
        For Nigerian small businesses. Amounts in naira, to the kobo.
      </p>
    </aside>
  );
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid flex-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <BrandPanel />
      <div className="relative isolate flex flex-col bg-canvas">
        {/* A soft teal glow at the top of the form side (the only colour on phones, where the panel is hidden). */}
        <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-72 bg-linear-to-b from-brand-soft to-transparent" aria-hidden />
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
