/**
 * Landing page (slice F9, design-system MASTER.md §7; look in DECISIONS D-62, D-63, D-65).
 *
 * Sections: hero (promise + floating matched-payment cards), a scrolling feature strip, a 3D preview of the
 * app, before/after, "follow one payment", how it works, features, who it's for (shadcn Tabs), FAQ (shadcn
 * Accordion), and a closing call to action. The brand mark is the owner's logo (components/brand/logo.tsx).
 *
 * A server component: rendered once and sent as plain HTML (fast, indexable). The only browser code is in
 * small pieces: AuthNav and StartButtons (signed in or not), and the shadcn Tabs/Accordion.
 * Every claim is something the product really does; comments name the rule behind it for the viva.
 * Motion is CSS only (globals.css): only transform and opacity move, and prefers-reduced-motion stops it.
 */

import {
  Banknote,
  Check,
  CreditCard,
  FileSpreadsheet,
  FileUp,
  History,
  ListChecks,
  Mail,
  ShieldCheck,
  Sigma,
  Sparkles,
  X,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Logo, LogoMark } from "@/components/brand/logo";
import { AudienceTabs } from "@/components/marketing/audience-tabs";
import { AuthNav } from "@/components/marketing/auth-nav";
import { Faq } from "@/components/marketing/faq";
import { HeroVisual } from "@/components/marketing/hero-visual";
import { PaymentFlow } from "@/components/marketing/payment-flow";
import { ProductPreview } from "@/components/marketing/product-preview";
import { StartButtons } from "@/components/marketing/start-buttons";
import { Badge } from "@/components/ui/badge";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "ReconcilePro — know which invoices are paid",
  description:
    "ReconcilePro reads your bank statements and Paystack payments, matches each one to the right invoice, and only asks you about the ones it isn't sure of.",
};

// The scrolling strip under the hero. Each item is a feature the app has today.
const STRIP = [
  "Bank statement CSV import", // statements feature
  "Paystack card payments", // paystack webhook + pay link
  "Matching by payment reference", // matching: exact reference
  "Ranked suggestions with reasons", // matching: score + reasons
  "VAT at 7.5%, to the kobo", // invoices: VAT rounding rule
  "Invoice links customers can pay", // public invoice page
  "Emailed invoices", // D-60
  "Full audit log", // invariant 7
];

const STEPS = [
  {
    icon: FileUp,
    title: "Upload your bank statement",
    // Invariant 2: unique fingerprint per line + ON CONFLICT DO NOTHING.
    text: "Export a CSV from your bank and drop it in. Overlapping statements are fine: a line already imported is never added twice.",
  },
  {
    icon: Sparkles,
    title: "We match what we can",
    // Matching rules in CLAUDE.md: exact reference → auto; otherwise amount 50 / name 30 / date 20.
    text: "A payment that quotes the invoice reference is matched straight away. Paystack card payments are recorded the moment they succeed.",
  },
  {
    icon: ListChecks,
    title: "You review the rest",
    // Match screen: score breakdown + plain-English reasons, keyboard shortcuts.
    text: "Anything uncertain waits in one queue, with the likely invoices ranked and the reasons in plain English. Accept with one key.",
  },
];

const BEFORE = [
  "Scrolling statements line by line",
  "Guessing which invoice a transfer was for",
  "Totals that drift from rounding",
  "No record of who changed what",
];
const AFTER = [
  "Statements imported in seconds, duplicates skipped", // invariant 2
  "Payments matched by reference, the rest ranked with reasons", // matching
  "Every amount in whole kobo", // invariant 1
  "A full audit trail of every change", // invariant 7
];

// Bento features. `wide` cards span two columns on large screens.
const FEATURES = [
  {
    icon: FileSpreadsheet,
    title: "Bank imports that never double count",
    text: "Upload overlapping statements without fear: each line has a fingerprint and is only ever added once.", // invariant 2
    wide: true,
    tone: "tone-sky",
  },
  {
    icon: CreditCard,
    title: "Paystack, recorded once",
    text: "A card payment is recorded when Paystack confirms it, and a repeated notification changes nothing.", // invariant 3
    tone: "tone-violet",
  },
  {
    icon: Mail,
    title: "Invoices that get paid",
    text: "Send an invoice and your customer gets an email with a link to pay by card or transfer.", // D-60
    tone: "tone-amber",
  },
  {
    icon: ShieldCheck,
    title: "Never over-allocated",
    text: "No invoice or bank line can be allocated more than its amount, even with two people working at once.", // invariant 4
    tone: "tone-teal",
  },
  {
    icon: History,
    title: "Nothing disappears",
    text: "A wrong match is reversed with a reason, never deleted, and the audit log keeps who, what and when.", // invariant 7
    wide: true,
    tone: "tone-sky",
  },
];

// Stagger order for .animate-rise / .animate-float (globals.css): element n starts a little after element n-1.
const order = (i: number) => ({ "--i": i }) as React.CSSProperties;
// Teal icon tile used across sections.
const ICON_TILE =
  "lift-icon flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand ring-1 ring-teal-200 dark:ring-teal-800";
// Cards that lift and tilt towards you on hover (.lift-card in globals.css: transform only).
const CARD = "lift-card rounded-2xl border bg-card";
// Card tints (.tone in globals.css, D-69), one per "How it works" step.
const STEP_TONES = ["tone-teal", "tone-sky", "tone-violet"];

function SectionHeading({ eyebrow, title, text, id }: { eyebrow: string; title: string; text?: string; id: string }) {
  return (
    <div className="reveal mx-auto max-w-2xl text-center">
      <Badge variant="outline" className="border-teal-200 bg-brand-soft text-teal-800 dark:border-teal-800 dark:text-teal-200">
        {eyebrow}
      </Badge>
      <h2 id={id} className="mt-4 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      {text && <p className="mt-4 text-lg text-muted-foreground">{text}</p>}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col bg-wash">
      {/* Sticky glass header: stays on top while scrolling, the page shows through blurred. */}
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Logo />
          <nav aria-label="Sections" className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            {[
              ["#product", "Product"],
              ["#how", "How it works"],
              ["#features", "Features"],
              ["#faq", "FAQ"],
            ].map(([href, label]) => (
              <a key={href} href={href} className="transition-colors hover:text-foreground">
                {label}
              </a>
            ))}
          </nav>
          <AuthNav />
        </div>
      </header>

      <main className="flex-1">
        {/* ── Hero ─────────────────────────────────────────────────────────────────────────────── */}
        <div className="relative isolate overflow-hidden">
          {/* Decoration only: drifting soft glows and a faint dot grid. -z-10 keeps them behind the text. */}
          <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden>
            <div className="absolute inset-0 bg-linear-to-b from-brand-soft via-background to-background" />
            <div className="bg-dots absolute inset-0" />
            <div className="glow animate-drift absolute -top-40 -left-40 size-[36rem] [--glow:rgb(45_212_191/0.28)]" style={order(0)} />
            <div className="glow animate-drift absolute -top-10 -right-32 size-[32rem] [--glow:rgb(37_99_235/0.18)]" style={order(1)} />
            <div className="glow animate-drift absolute -bottom-40 left-1/4 size-[28rem] [--glow:rgb(34_197_94/0.18)]" style={order(2)} />
          </div>

          <section className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-16 pb-20 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:pt-24 lg:pb-28">
            <div className="flex flex-col gap-6">
              <p
                className="animate-rise inline-flex w-fit items-center gap-2 rounded-full border border-teal-200 bg-background px-3 py-1 text-sm text-teal-800 dark:border-teal-800 dark:text-teal-200"
                style={order(0)}
              >
                <span className="relative flex size-2" aria-hidden>
                  <span className="absolute inline-flex size-full rounded-full bg-teal-500 opacity-75 motion-safe:animate-ping" />
                  <span className="relative inline-flex size-2 rounded-full bg-teal-500" />
                </span>
                Smarter reconciliation. Healthier books.
              </p>
              {/* Gradient text is large (≥ 36px semibold), so the 3:1 large-text contrast rule applies.
                  Blue to green, like the logo. */}
              <h1
                className="animate-rise text-4xl font-semibold tracking-tight text-balance sm:text-6xl sm:leading-[1.05]"
                style={order(1)}
              >
                Know which invoices are paid,{" "}
                <span className="bg-linear-to-r from-blue-700 via-teal-600 to-green-600 bg-clip-text text-transparent dark:from-blue-400 dark:via-teal-300 dark:to-green-400">
                  without the spreadsheet.
                </span>
              </h1>
              <p className="animate-rise max-w-xl text-lg text-muted-foreground" style={order(2)}>
                ReconcilePro reads your bank statements and Paystack payments, matches each one to the right invoice, and
                only asks you about the ones it isn&apos;t sure of.
              </p>
              <div className="animate-rise flex flex-wrap gap-3" style={order(3)}>
                {/* Signed in already? These become "Open your dashboard" (components/marketing/start-buttons.tsx). */}
                <StartButtons withSignIn primaryClassName="shadow-lg shadow-teal-700/25" />
              </div>
              <ul className="animate-rise flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground" style={order(4)}>
                {["Every kobo counted", "Duplicate-safe imports", "Full audit trail"].map((point) => (
                  <li key={point} className="flex items-center gap-1.5">
                    <Check className="size-4 text-brand" aria-hidden />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
            <HeroVisual />
          </section>
        </div>

        {/* ── Feature strip: the list twice, sliding left by half, so it loops without a seam ────── */}
        <section aria-label="Features at a glance" className="border-y bg-canvas py-4">
          <div className="overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]">
            <div className="animate-marquee flex w-max gap-3">
              {[0, 1].map((copy) => (
                <ul key={copy} className="flex gap-3" aria-hidden={copy === 1 || undefined}>
                  {STRIP.map((item) => (
                    <li key={item} className="flex items-center gap-2 rounded-full border bg-background px-4 py-1.5 text-sm whitespace-nowrap">
                      <span className="size-1.5 rounded-full bg-brand" aria-hidden />
                      {item}
                    </li>
                  ))}
                </ul>
              ))}
            </div>
          </div>
        </section>

        {/* ── Product preview ─────────────────────────────────────────────────────────────────── */}
        <section id="product" aria-labelledby="product-heading" className="scroll-mt-20 overflow-hidden px-4 py-20 sm:px-6 lg:py-28">
          <SectionHeading
            id="product-heading"
            eyebrow="The product"
            title="Your money, at a glance"
            text="What you're owed, what came in this month, and the few payments that need a person. Everything else is already matched."
          />
          <div className="mt-14">
            <ProductPreview />
          </div>
        </section>

        {/* ── Before / after ──────────────────────────────────────────────────────────────────── */}
        <section aria-labelledby="compare-heading" className="border-t bg-canvas px-4 py-20 sm:px-6 lg:py-28">
          <SectionHeading id="compare-heading" eyebrow="Why switch" title="From spreadsheet to sorted" />
          <div className="mx-auto mt-14 grid max-w-5xl gap-6 md:grid-cols-2">
            <div className={cn(CARD, "tone tone-amber reveal p-7")}>
              <p className="flex items-center gap-2 font-semibold text-muted-foreground">
                <FileSpreadsheet className="size-5" aria-hidden />
                The spreadsheet way
              </p>
              <ul className="mt-5 space-y-3">
                {BEFORE.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-muted-foreground">
                    <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400">
                      <X className="size-3.5" aria-hidden />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className={cn(CARD, "tone tone-teal reveal relative overflow-hidden border-teal-300 p-7 dark:border-teal-800")}>
              <div className="glow pointer-events-none absolute -top-24 -right-24 size-64 [--glow:rgb(45_212_191/0.25)]" aria-hidden />
              <p className="flex items-center gap-2 font-semibold">
                <LogoMark size={22} />
                With ReconcilePro
              </p>
              <ul className="mt-5 space-y-3">
                {AFTER.map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-400">
                      <Check className="size-3.5" aria-hidden />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ── Follow one payment ──────────────────────────────────────────────────────────────── */}
        <section aria-labelledby="flow-heading" className="px-4 py-20 sm:px-6 lg:py-28">
          <SectionHeading
            id="flow-heading"
            eyebrow="Follow one payment"
            title="From bank alert to paid invoice"
            text="A customer pays by transfer and quotes the invoice reference. This is everything that happens next, without you."
          />
          <div className="reveal mx-auto mt-14 max-w-6xl">
            <PaymentFlow />
          </div>
        </section>

        {/* ── How it works ────────────────────────────────────────────────────────────────────── */}
        <section id="how" aria-labelledby="how-heading" className="scroll-mt-20 border-t bg-canvas px-4 py-20 sm:px-6 lg:py-28">
          <SectionHeading id="how-heading" eyebrow="How it works" title="Three steps from bank statement to paid invoices" />
          <ol className="relative mx-auto mt-14 grid max-w-6xl gap-6 md:grid-cols-3">
            {/* The line joining the three steps on wide screens (decoration). */}
            <span
              className="absolute top-14 right-[16%] left-[16%] hidden h-px bg-linear-to-r from-transparent via-teal-400/60 to-transparent md:block"
              aria-hidden
            />
            {STEPS.map((step, index) => (
              <li key={step.title} className={cn(CARD, "tone reveal relative flex flex-col gap-4 p-6", STEP_TONES[index])}>
                <div className="flex items-center justify-between">
                  <span className={ICON_TILE}>
                    <step.icon className="size-5" aria-hidden />
                  </span>
                  <span
                    className="bg-linear-to-br from-blue-600 to-green-500 bg-clip-text text-4xl font-semibold text-transparent tabular-nums"
                    aria-hidden
                  >
                    0{index + 1}
                  </span>
                </div>
                <h3 className="text-lg font-semibold">
                  <span className="sr-only">Step {index + 1}: </span>
                  {step.title}
                </h3>
                <p className="text-muted-foreground">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ── Features (bento) ────────────────────────────────────────────────────────────────── */}
        <section id="features" aria-labelledby="features-heading" className="scroll-mt-20 px-4 py-20 sm:px-6 lg:py-28">
          <SectionHeading
            id="features-heading"
            eyebrow="Built for money"
            title="Numbers you can stand behind"
            text="The rules that keep your books right are enforced by the system, not left to care."
          />
          <div className="mx-auto mt-14 grid max-w-6xl gap-6 lg:grid-cols-3">
            {/* The kobo card shows the maths it promises. Invariant 1: integer kobo end to end. */}
            <div className={cn(CARD, "tone tone-teal reveal flex flex-col gap-4 p-6 lg:row-span-2")}>
              <span className={ICON_TILE}>
                <Sigma className="size-5" aria-hidden />
              </span>
              <h3 className="text-lg font-semibold">Every kobo counted</h3>
              <p className="text-muted-foreground">
                Amounts are stored as whole kobo, never rounded floats, so totals always add up to the exact naira.
              </p>
              <div className="mt-auto space-y-2 rounded-xl border bg-background p-4 font-mono text-sm">
                {[
                  ["Subtotal", 9_000_000],
                  ["VAT 7.5%", 675_000],
                  ["Total", 9_675_000],
                ].map(([label, kobo]) => (
                  <div key={label} className="flex justify-between gap-3">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="tabular-nums">{formatNaira(kobo as number)}</span>
                  </div>
                ))}
                <div className="flex justify-between gap-3 border-t pt-2">
                  <span className="text-muted-foreground">Stored as</span>
                  <span className="rounded bg-brand-soft px-1.5 text-teal-800 tabular-nums dark:text-teal-200">9,675,000 kobo</span>
                </div>
              </div>
            </div>
            {FEATURES.map((feature) => (
              <div key={feature.title} className={cn(CARD, "tone reveal flex flex-col gap-3 p-6", feature.tone, feature.wide && "lg:col-span-2")}>
                <span className={ICON_TILE}>
                  <feature.icon className="size-5" aria-hidden />
                </span>
                <h3 className="text-lg font-semibold">{feature.title}</h3>
                <p className="text-muted-foreground">{feature.text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Who it's for (shadcn Tabs) ──────────────────────────────────────────────────────── */}
        <section aria-labelledby="who-heading" className="border-t bg-canvas px-4 py-20 sm:px-6 lg:py-28">
          <SectionHeading id="who-heading" eyebrow="Who it's for" title="Built for everyone who touches the money" />
          <div className="reveal mx-auto mt-10 max-w-4xl">
            <AudienceTabs />
          </div>
        </section>

        {/* ── FAQ (shadcn Accordion) ──────────────────────────────────────────────────────────── */}
        <section id="faq" aria-labelledby="faq-heading" className="scroll-mt-20 px-4 py-20 sm:px-6 lg:py-28">
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1fr_1.4fr]">
            <div className="reveal">
              <Badge variant="outline" className="border-teal-200 bg-brand-soft text-teal-800 dark:border-teal-800 dark:text-teal-200">
                FAQ
              </Badge>
              <h2 id="faq-heading" className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Questions, answered
              </h2>
              <p className="mt-4 text-muted-foreground">
                How ReconcilePro handles your statements, your customers&apos; payments and your mistakes.
              </p>
            </div>
            <div className="reveal">
              <Faq />
            </div>
          </div>
        </section>

        {/* ── Closing call to action: navy card, teal glow. White on slate-900 is ~17:1. ──────── */}
        <section className="px-4 pb-20 sm:px-6 lg:pb-28">
          <div className="reveal relative isolate mx-auto max-w-5xl overflow-hidden rounded-3xl bg-slate-900 px-6 py-16 text-center text-white shadow-2xl sm:px-12">
            <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden>
              <div className="glow animate-drift absolute -top-56 left-1/4 size-[36rem] [--glow:rgb(20_184_166/0.45)]" />
              <div className="glow animate-drift absolute -right-40 -bottom-56 size-[30rem] [--glow:rgb(37_99_235/0.35)]" style={order(1)} />
              <div className="bg-dots absolute inset-0 opacity-40" />
            </div>
            <div className="mx-auto mb-6 flex w-fit">
              <LogoMark onDark size={40} />
            </div>
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Stop matching payments by hand.</h2>
            <p className="mx-auto mt-4 max-w-xl text-slate-300">
              Create a workspace, add your customers, and import last month&apos;s statement. It takes a few minutes.
            </p>
            <div className="mt-8 flex justify-center">
              <StartButtons primaryClassName="bg-white text-slate-900 shadow-lg shadow-teal-500/30 hover:bg-teal-50" />
            </div>
            <p className="mt-6 flex items-center justify-center gap-2 text-sm text-slate-400">
              <Banknote className="size-4" aria-hidden />
              Amounts in naira, to the kobo.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t bg-canvas">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex flex-col gap-2">
            <Logo />
            <p className="text-sm text-muted-foreground">Smarter reconciliation. Healthier books.</p>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
            <a href="#product" className="hover:text-foreground">Product</a>
            <a href="#features" className="hover:text-foreground">Features</a>
            <a href="#faq" className="hover:text-foreground">FAQ</a>
            <Link href="/login" className="hover:text-foreground">Sign in</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
