/**
 * Landing page in the CEK Alpha style (DECISIONS D-71, replacing D-62/D-63/D-65's look).
 *
 * Sections, in CEK's order: a white sticky header; the hero (rotating photos behind a dark gradient, the
 * promise on the left and an example "today's import" card on the right); About Us (photo with two badges,
 * three features); How it works (on the beige band, three numbered cards); E-invoicing, coming soon (D-72);
 * a dark call to action; FAQ; and a dark footer.
 *
 * A server component: rendered once and sent as plain HTML (fast, indexable). The only browser code is in
 * small pieces: AuthNav and StartButtons (signed in or not), the hero photos, and the shadcn Accordion.
 * Every claim is something the product really does; comments name the rule behind it for the viva.
 */

import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Clock,
  CreditCard,
  FileUp,
  Inbox,
  Landmark,
  MapPin,
  Rocket,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { AuthNav } from "@/components/marketing/auth-nav";
import { EInvoicingSection } from "@/components/marketing/e-invoicing-section";
import { Faq } from "@/components/marketing/faq";
import { HeroCarousel } from "@/components/marketing/hero-carousel";
import { StartButtons } from "@/components/marketing/start-buttons";
import { formatNaira } from "@/lib/money";

export const metadata: Metadata = {
  title: "ReconcilePro — know which invoices are paid",
  description:
    "ReconcilePro reads your bank statements and Paystack payments, matches each one to the right invoice, and only asks you about the ones it isn't sure of.",
};

// The example card in the hero. Decoration that shows the three things an import does (amounts in kobo).
const IMPORT_LINES = [
  { narration: "NIP/ADAEZE FOODS/RCN-7Q4K", kobo: 10_750_000, tag: "Matched", tone: "ok", note: "INV-0042 · reference in narration" }, // exact reference
  { narration: "MOB TRF/KOLA/FOODSTUFF", kobo: 4_000_000, tag: "Suggested", tone: "suggested", note: "INV-0040 · amount and name match" }, // score ≥ 70
  { narration: "PAYSTACK SETTLEMENT 0193884", kobo: 41_286_000, tag: "Paystack payout", tone: "settlement", note: "already counted, set aside" }, // invariant 6
] as const;

const TAG_STYLES = {
  ok: "bg-green-100 text-green-800",
  suggested: "bg-orange-100 text-orange-800",
  settlement: "bg-stone-200 text-stone-700",
} as const;

const FEATURES = [
  {
    icon: FileUp,
    title: "Bank statement import",
    // Invariant 2: unique fingerprint per line + ON CONFLICT DO NOTHING.
    text: "Upload a CSV from your bank. Upload last month's again by mistake and nothing is added twice.",
  },
  {
    icon: Sparkles,
    title: "Automatic matching",
    // Matching: exact reference → auto; otherwise a score with reasons.
    text: "A payment that quotes the invoice reference is matched straight away. The rest are ranked with reasons in plain English.",
  },
  {
    icon: CreditCard,
    title: "Paystack payments",
    // Invariants 3 and 6: a webhook pays once; settlement lines are never matched.
    text: "Card payments are recorded the moment Paystack confirms them, and the lump settlement on your statement is never counted again.",
  },
];

const STEPS = [
  {
    icon: FileUp,
    title: "Upload your statement",
    text: "Export a CSV from your bank and drop it in. Overlapping statements are fine: a line already imported is skipped.",
  },
  {
    icon: Sparkles,
    title: "We match what we can",
    // Exact reference match, case- and space-insensitive.
    text: "A narration like NIP/KOLA AND SONS/RCN-4F2K pays invoice RCN-4F2K. Paystack payments match themselves.",
  },
  {
    icon: Inbox,
    title: "You review the rest",
    // Match screen: candidates ranked, reasons shown, keyboard shortcuts.
    text: "Uncertain payments wait in one queue with the likely invoices ranked and the reasons shown. Accept with one key.",
  },
];

const CHECKS = [
  "Statements imported in seconds, duplicates skipped", // invariant 2
  "Payments matched by reference, the rest ranked with reasons", // matching
  "A full audit trail of every change", // invariant 7
];

const FACTS = [
  { icon: Landmark, title: "Your bank", text: "CSV exports, header found automatically." },
  { icon: CreditCard, title: "Paystack", text: "Card payments recorded once." }, // invariant 3
  { icon: ShieldCheck, title: "Your data", text: "Each workspace sees only its own records." }, // invariant 8
  { icon: Clock, title: "Month end", text: "Minutes of review instead of a day." },
];

/** CEK's section title: uppercase heading with an orange rule, and a line of explanation under it. */
function SectionTitle({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <div className="mb-12">
      <h2 id={id} className="flex items-center gap-3 text-2xl font-extrabold tracking-wide uppercase after:h-0.5 after:w-28 after:bg-primary">
        {title}
      </h2>
      <p className="mt-2 max-w-2xl font-heading font-semibold text-muted-foreground">{children}</p>
    </div>
  );
}

/** An orange icon in a soft orange circle (CEK's feature icon). */
function IconCircle({ icon: Icon, className = "size-14" }: { icon: React.ElementType; className?: string }) {
  return (
    <span className={`flex shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand ${className}`}>
      <Icon className="size-6" aria-hidden />
    </span>
  );
}

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col bg-background">
      <header className="sticky top-0 z-30 bg-card shadow-[0_2px_15px_rgb(0_0_0/0.08)]">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
          <Logo size={36} />
          <nav aria-label="Sections" className="hidden items-center gap-7 font-nav text-[15px] text-muted-foreground lg:flex">
            {[
              ["#about", "About"],
              ["#how", "How it works"],
              ["#e-invoicing", "E-invoicing"],
              ["#faq", "FAQ"],
            ].map(([href, label]) => (
              <a key={href} href={href} className="transition-colors hover:text-brand-ink">
                {label}
              </a>
            ))}
          </nav>
          <AuthNav />
        </div>
      </header>

      <main className="flex-1">
        {/* ── Hero ─────────────────────────────────────────────────────────────────────────────── */}
        <section aria-label="Introduction" className="relative isolate overflow-hidden bg-neutral-950 text-white">
          <HeroCarousel />
          {/* Dark on the left (behind the text), lighter on the right, plus a soft orange glow top right. */}
          <div className="absolute inset-0 -z-10 bg-linear-to-r from-neutral-950/95 via-neutral-950/80 to-neutral-950/45" aria-hidden />
          <div className="absolute -top-40 -right-32 -z-10 size-[32rem] rounded-full bg-[radial-gradient(circle,rgb(234_124_0/0.35),transparent_65%)]" aria-hidden />

          <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-20 pb-28 sm:px-6 lg:grid-cols-[1.15fr_1fr] lg:pt-24">
            <div>
              <span className="inline-flex items-center gap-2.5 rounded-full border border-primary/40 bg-primary/15 px-4 py-1.5 font-nav text-sm text-orange-200">
                <span className="size-2 rounded-full bg-primary ring-4 ring-primary/25" aria-hidden />
                For Nigerian businesses that send invoices
              </span>
              <h1 className="mt-6 text-4xl leading-[1.08] font-black tracking-tight text-balance sm:text-5xl lg:text-6xl">
                Every payment, matched. <span className="text-primary">Every kobo accounted for.</span>
              </h1>
              <span className="my-6 block h-1 w-20 rounded-full bg-primary" aria-hidden />
              <p className="max-w-xl text-lg font-light text-white/80">
                ReconcilePro reads your bank statements and Paystack payments, matches each one to the invoice it paid,
                and only asks you about the ones it isn&apos;t sure of.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <StartButtons primaryClassName="hover:bg-white hover:text-neutral-950" />
                <a
                  href="#how"
                  className="inline-flex h-11 items-center rounded-full border-2 border-white/60 px-6 font-nav text-base font-medium transition-colors hover:bg-white hover:text-neutral-950"
                >
                  See how it works
                </a>
              </div>
              <ul className="mt-9 flex flex-wrap gap-x-6 gap-y-2 text-sm text-white/85">
                {["Bank CSV and Paystack", "Never counted twice", "Full audit trail"].map((fact) => (
                  <li key={fact} className="flex items-center gap-2">
                    <CheckCircle2 className="size-4.5 text-primary" aria-hidden />
                    {fact}
                  </li>
                ))}
              </ul>
            </div>

            {/* The example import card: always light, like a sheet of paper on the photo. Decoration. */}
            <div className="relative rounded-3xl bg-white/95 p-6 text-stone-700 shadow-[0_30px_60px_rgb(0_0_0/0.45)]" aria-hidden>
              <div className="flex items-center justify-between gap-3 border-b border-stone-200 pb-4">
                <div>
                  <p className="font-heading text-lg font-black text-stone-900">Today&apos;s import</p>
                  <p className="text-xs text-stone-500">GTBank statement · 38 lines</p>
                </div>
                <span className="flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 font-nav text-xs text-green-800">
                  <span className="size-1.5 rounded-full bg-green-600" />
                  Matching
                </span>
              </div>
              <ul className="divide-y divide-dashed divide-stone-200">
                {IMPORT_LINES.map((line) => (
                  <li key={line.narration} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 py-3.5">
                    <span className="font-mono text-xs break-all text-stone-900">{line.narration}</span>
                    <span className="text-right font-heading font-extrabold text-stone-900 tabular-nums">{formatNaira(line.kobo)}</span>
                    <span className="col-span-2 flex items-center gap-2 text-xs text-stone-500">
                      <span className={`rounded-full px-2.5 py-0.5 font-nav font-medium ${TAG_STYLES[line.tone]}`}>{line.tag}</span>
                      {line.note}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-3">
                <p className="flex justify-between text-sm text-stone-500">
                  Matched automatically <b className="text-stone-900 tabular-nums">31 of 38</b>
                </p>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-stone-200">
                  <div className="h-full w-[82%] rounded-full bg-linear-to-r from-orange-400 to-primary" />
                </div>
              </div>
              <div className="absolute -bottom-7 left-4 flex items-center gap-3 rounded-2xl bg-primary px-5 py-3 text-white shadow-[0_16px_34px_rgb(234_124_0/0.4)] sm:-left-7">
                <span className="flex size-9 items-center justify-center rounded-full bg-white/20">
                  <CheckCircle2 className="size-5" />
                </span>
                <div>
                  <p className="font-heading text-lg font-black tabular-nums">+{formatNaira(10_750_000)}</p>
                  <p className="text-xs text-white/90">INV-0042 is now paid</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── About ────────────────────────────────────────────────────────────────────────────── */}
        <section id="about" aria-labelledby="about-heading" className="scroll-mt-20 px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <SectionTitle id="about-heading" title="About Us">
              <b className="text-brand-ink">ReconcilePro</b> matches bank-statement credits and Paystack payments to your
              invoices automatically, and sends anything uncertain to one short queue for your accountant.
            </SectionTitle>
            <div className="grid items-center gap-16 lg:grid-cols-2">
              <div className="relative pr-10 pb-12">
                <div className="relative aspect-[4/4.4] overflow-hidden rounded-3xl shadow-[0_0_45px_rgb(0_0_0/0.08)]">
                  <Image src="/images/about.jpg" alt="An accountant reviewing figures" fill sizes="(min-width: 1024px) 40vw, 90vw" className="object-cover" />
                </div>
                <div className="absolute bottom-0 -left-2 min-w-44 rounded-xl bg-card px-6 py-5 shadow-card">
                  <p className="font-heading text-5xl leading-none font-black text-brand">0</p>
                  {/* Invariants 2 and 3: re-imports and duplicate webhooks add nothing. */}
                  <p className="mt-2 text-xs font-medium tracking-wide uppercase">Payments counted twice</p>
                </div>
                <div className="absolute top-10 right-0 min-w-40 rounded-l-xl bg-primary px-5 py-4 text-primary-foreground">
                  <p className="font-heading text-4xl leading-none font-black">7.5%</p>
                  {/* VAT on the subtotal, rounded half up to the kobo. */}
                  <p className="mt-2 text-xs tracking-wide uppercase">VAT worked out to the kobo</p>
                </div>
              </div>
              <div>
                <h3 className="text-3xl leading-tight font-extrabold tracking-tight sm:text-4xl">
                  Built for Nigerian businesses that send invoices.
                </h3>
                <p className="mt-4 text-lg font-light text-muted-foreground">
                  Your customers pay by transfer and by card. We turn a month-end of scrolling statements into a few
                  minutes of review, in these areas:
                </p>
                <ul className="mt-8 flex flex-col gap-7">
                  {FEATURES.map((feature) => (
                    <li key={feature.title} className="flex gap-5">
                      <IconCircle icon={feature.icon} />
                      <div>
                        <h4 className="text-lg font-bold">{feature.title}</h4>
                        <p className="mt-1 text-muted-foreground">{feature.text}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* ── How it works ─────────────────────────────────────────────────────────────────────── */}
        <section id="how" aria-labelledby="how-heading" className="scroll-mt-20 bg-canvas px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <SectionTitle id="how-heading" title="How it works">
              The same rules every time, so you can explain any match to your accountant or your auditor.
            </SectionTitle>
            <div className="grid items-center gap-16 lg:grid-cols-2">
              <div>
                <p className="flex items-center gap-3 font-nav text-sm font-medium tracking-[0.15em] text-brand-ink uppercase before:h-0.5 before:w-9 before:bg-primary">
                  Three steps
                </p>
                <h3 className="mt-4 text-3xl leading-tight font-extrabold tracking-tight sm:text-4xl">
                  From bank statement to paid invoice, without the spreadsheet.
                </h3>
                <p className="mt-5 text-muted-foreground">
                  Upload your statement, let ReconcilePro match what it can, and review the rest in one queue. Every action
                  is recorded, and a wrong match is reversed with a reason, never deleted.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  <StartButtons />
                </div>
              </div>
              <div className="relative p-8">
                <div className="absolute top-0 right-0 size-44 rounded-full border-[18px] border-brand-soft" aria-hidden />
                <div className="absolute bottom-0 left-0 size-28 rounded-2xl bg-primary/90" aria-hidden />
                <div className="relative aspect-[3/2] overflow-hidden rounded-3xl shadow-card">
                  <Image src="/images/services.jpg" alt="Invoices and a laptop on a desk" fill sizes="(min-width: 1024px) 40vw, 90vw" className="object-cover" />
                </div>
              </div>
            </div>
            <ol className="mt-14 grid gap-6 md:grid-cols-3">
              {STEPS.map((step, index) => (
                <li
                  key={step.title}
                  className="group relative overflow-hidden rounded-2xl bg-card p-8 shadow-card transition-transform duration-300 before:absolute before:inset-x-0 before:top-0 before:h-1 before:origin-left before:scale-x-0 before:bg-primary before:transition-transform before:duration-500 hover:-translate-y-1.5 hover:before:scale-x-100"
                >
                  <span className="absolute top-5 right-6 font-heading text-5xl leading-none font-black text-brand-soft" aria-hidden>
                    0{index + 1}
                  </span>
                  <IconCircle icon={step.icon} />
                  <h4 className="mt-5 text-xl font-extrabold">
                    <span className="sr-only">Step {index + 1}: </span>
                    {step.title}
                  </h4>
                  <p className="mt-2 text-muted-foreground">{step.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ── E-invoicing: coming soon (D-72) ──────────────────────────────────────────────────── */}
        <EInvoicingSection />

        {/* ── Call to action (dark, like CEK's) ────────────────────────────────────────────────── */}
        <section aria-labelledby="cta-heading" className="relative isolate overflow-hidden bg-neutral-950 px-4 py-20 text-white sm:px-6">
          <Image src="/images/hero-3.jpg" alt="" fill sizes="100vw" className="-z-10 object-cover opacity-20" />
          <div className="mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-[1.1fr_1fr]">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full bg-primary/15 px-4 py-1.5 font-nav text-sm text-orange-300">
                <Rocket className="size-4" aria-hidden />
                Clear books, every month
              </span>
              <h2 id="cta-heading" className="mt-5 text-3xl leading-tight font-black tracking-tight sm:text-5xl">
                Take a leap and stop matching payments by hand!
              </h2>
              <p className="mt-5 text-lg font-light text-white/75">
                From <b className="font-bold text-primary">bank transfers and Paystack card payments to part payments and reversals</b>,
                you&apos;ll see what every customer owes without opening a spreadsheet.
              </p>
            </div>
            <div>
              <ul className="flex flex-col gap-3.5">
                {CHECKS.map((item) => (
                  <li key={item} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-5 py-4">
                    <CheckCircle2 className="size-5 shrink-0 text-primary" aria-hidden />
                    {item}
                  </li>
                ))}
              </ul>
              <div className="mt-7 flex flex-wrap gap-3">
                <StartButtons primaryClassName="hover:bg-white hover:text-neutral-950" />
                <Link
                  href="/login"
                  className="inline-flex h-11 items-center rounded-full border-2 border-white/60 px-6 font-nav text-base font-medium transition-colors hover:bg-white hover:text-neutral-950"
                >
                  Sign in
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* ── FAQ ──────────────────────────────────────────────────────────────────────────────── */}
        <section id="faq" aria-labelledby="faq-heading" className="scroll-mt-20 bg-canvas px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <SectionTitle id="faq-heading" title="FAQ">
              How ReconcilePro handles your statements, your customers&apos; payments and your mistakes.
            </SectionTitle>
            <div className="grid items-start gap-12 lg:grid-cols-[1fr_1.4fr]">
              <ul className="grid gap-4 sm:grid-cols-2">
                {FACTS.map((fact) => (
                  <li key={fact.title} className="rounded-2xl bg-card p-6 shadow-card">
                    <IconCircle icon={fact.icon} className="size-12" />
                    <h3 className="mt-3 text-base font-extrabold">{fact.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{fact.text}</p>
                  </li>
                ))}
              </ul>
              <Faq />
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-neutral-950 text-stone-400">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 pt-16 pb-10 sm:grid-cols-2 sm:px-6 lg:grid-cols-[1.4fr_1fr_1fr_1.2fr]">
          <div>
            <Logo onDark size={34} />
            <p className="mt-4">Bank and Paystack payments matched to your invoices, for Nigerian small businesses.</p>
          </div>
          {[
            { title: "Product", links: [["#about", "About"], ["#how", "How it works"], ["#e-invoicing", "E-invoicing (soon)"], ["#faq", "FAQ"]] },
            { title: "Account", links: [["/login", "Sign in"], ["/register", "Create a workspace"]] },
          ].map((column) => (
            <nav key={column.title} aria-label={column.title}>
              <h2 className="relative mb-4 pb-3 text-base font-extrabold text-white after:absolute after:bottom-0 after:left-0 after:h-0.5 after:w-10 after:bg-primary">
                {column.title}
              </h2>
              <ul className="flex flex-col gap-2.5">
                {column.links.map(([href, label]) => (
                  <li key={href}>
                    <Link href={href} className="inline-flex items-center gap-1.5 transition-colors hover:text-primary">
                      <ChevronRight className="size-3.5" aria-hidden />
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
          <div>
            <h2 className="relative mb-4 pb-3 text-base font-extrabold text-white after:absolute after:bottom-0 after:left-0 after:h-0.5 after:w-10 after:bg-primary">
              Get started
            </h2>
            <p className="flex items-center gap-2">
              <MapPin className="size-4 shrink-0 text-primary" aria-hidden />
              Made for businesses in Nigeria
            </p>
            <Link href="/register" className="mt-4 inline-flex items-center gap-1.5 font-nav text-primary hover:underline">
              Create your free workspace <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        </div>
        <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-3 border-t border-white/10 px-4 py-5 text-sm sm:px-6">
          <span>© {new Date().getFullYear()} ReconcilePro.</span>
          <span>Amounts in naira, to the kobo.</span>
        </div>
      </footer>
    </div>
  );
}
