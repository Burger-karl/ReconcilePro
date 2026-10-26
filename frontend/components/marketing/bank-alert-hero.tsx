/**
 * The landing page hero (DECISIONS D-73): a phone showing bank credit alerts, and the invoice the top one paid
 * getting stamped PAID. It shows the product's one job with things every Nigerian business owner already knows:
 * the GTBank/NIP credit alert and a paper invoice with a payment reference.
 *
 * A server component. The phone, invoice and stamp are decoration (aria-hidden): the heading and text say the
 * same thing in words. The stamp's thump is CSS (.animate-stamp in globals.css) and stays still for reduced motion.
 */

import { Check } from "lucide-react";

import { StartButtons } from "@/components/marketing/start-buttons";
import { formatNaira } from "@/lib/money";

// What the phone shows: two credit alerts and a Paystack settlement (all made up, amounts as banks print them).
const ALERTS = [
  { from: "GTBank", when: "now", lines: ["Acct: ****1234", "Amt: NGN107,500.00 CR", "Desc: NIP/ADAEZE FOODS/RCN-7Q4K"], highlight: true },
  { from: "GTBank", when: "12m", lines: ["Acct: ****1234", "Amt: NGN40,000.00 CR", "Desc: MOB TRF/KOLA/FOODSTUFF"] },
  { from: "Paystack", when: "1h", lines: ["Settlement of NGN412,860.00", "sent to ****1234"] },
];

// The invoice the first alert paid: ₦100,000 + 7.5% VAT, in kobo (invariant 1).
const INVOICE = { subtotal: 10_000_000, vat: 750_000, total: 10_750_000 };

function Phone() {
  return (
    <div className="relative h-[470px] w-[270px] shrink-0 rounded-[38px] bg-stone-900 p-3 shadow-[0_30px_60px_rgb(0_0_0/0.25)]">
      <span className="absolute top-[18px] left-1/2 h-5 w-20 -translate-x-1/2 rounded-full bg-black" />
      <div className="h-full overflow-hidden rounded-[28px] bg-linear-to-b from-stone-700 to-stone-900 px-3 pt-9">
        <p className="text-center font-heading text-4xl font-extrabold tracking-tight text-white">9:41</p>
        <p className="mb-4 text-center text-xs text-white/70">Monday</p>
        {ALERTS.map((alert) => (
          <div
            key={alert.lines.join()}
            className={`mb-2 rounded-2xl bg-white/95 px-3 py-2.5 text-stone-800 ${alert.highlight ? "ring-3 ring-primary" : ""}`}
          >
            <p className="mb-0.5 flex justify-between font-nav text-[11px] font-bold text-stone-950">
              {alert.from}
              <span className="font-normal text-stone-500">{alert.when}</span>
            </p>
            <p className="font-mono text-[10.5px] leading-snug">
              {alert.lines.map((line) => (
                <span key={line} className="block">
                  {line}
                </span>
              ))}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function StampedInvoice() {
  return (
    // Always on paper colours, in both themes: it's a printed invoice.
    <div className="relative w-[300px] rotate-[2.5deg] rounded-md bg-[#fffdf8] px-6 pt-6 pb-7 text-stone-700 shadow-[0_20px_45px_rgb(0_0_0/0.14)]">
      <div className="flex items-baseline justify-between border-b-2 border-stone-800 pb-2">
        <b className="font-heading text-xl font-black text-stone-900">INVOICE</b>
        <span className="font-mono text-xs">INV-0042</span>
      </div>
      {[
        ["Adaeze Foods Ltd", "21 Oct"],
        ["Supplies", formatNaira(INVOICE.subtotal)],
        ["VAT 7.5%", formatNaira(INVOICE.vat)],
      ].map(([left, right]) => (
        <p key={left} className="flex justify-between border-b border-dashed border-stone-300 py-1.5 text-[13px]">
          <span>{left}</span>
          <span className="tabular-nums">{right}</span>
        </p>
      ))}
      <p className="flex justify-between pt-2.5 font-heading text-lg font-black text-stone-900">
        <span>Total</span>
        <span className="tabular-nums">{formatNaira(INVOICE.total)}</span>
      </p>
      <p className="mt-2 text-xs">
        Pay with reference <code className="rounded bg-stone-200/70 px-1.5 font-mono">RCN-7Q4K</code>
      </p>
      {/* The rubber stamp. -14° and multiply blending make it look inked onto the paper. */}
      <div className="animate-stamp absolute right-5 bottom-9 -rotate-[14deg] rounded-lg border-4 border-orange-700 px-3.5 py-0.5 text-center text-orange-700 opacity-90 mix-blend-multiply">
        <span className="block font-heading text-3xl font-black tracking-[0.15em]">PAID</span>
        <span className="block font-nav text-[9px] tracking-widest">26 OCT · AUTO</span>
      </div>
    </div>
  );
}

export function BankAlertHero() {
  return (
    <section aria-labelledby="hero-heading" className="overflow-hidden bg-canvas px-4 sm:px-6">
      <div className="mx-auto grid max-w-6xl items-center gap-14 py-16 lg:grid-cols-[1fr_1.05fr] lg:py-20">
        <div>
          <p className="flex items-center gap-2 font-nav text-sm tracking-[0.15em] text-brand-ink uppercase before:h-0.5 before:w-8 before:bg-primary">
            Bank alerts, sorted
          </p>
          <h1 id="hero-heading" className="mt-4 text-4xl leading-[1.1] font-black tracking-tight text-balance sm:text-5xl">
            Your phone says <span className="text-primary">{formatNaira(10_750_000)} came in.</span> We tell you which
            invoice it paid.
          </h1>
          <p className="mt-5 max-w-xl text-lg text-muted-foreground">
            ReconcilePro reads your bank statements and Paystack payments, stamps the right invoice paid, and only asks
            you about the ones it isn&apos;t sure of.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <StartButtons />
            <a
              href="#how"
              className="inline-flex h-11 items-center rounded-full border-2 border-foreground px-6 font-nav text-base font-medium transition-colors hover:bg-foreground hover:text-background"
            >
              See how it works
            </a>
          </div>
        </div>

        {/* The scene. Wide screens: phone left, invoice right, a dashed line from the alert to the invoice. */}
        <div className="relative mx-auto w-full max-w-[560px] lg:min-h-[470px]" aria-hidden>
          <div className="flex flex-col items-center gap-10 sm:flex-row sm:items-start sm:justify-between">
            <Phone />
            <div className="sm:mt-12">
              <StampedInvoice />
            </div>
          </div>
          <span className="absolute top-[160px] left-[230px] hidden h-0.5 w-[70px] border-t-2 border-dashed border-primary sm:block" />
          <div className="absolute top-[320px] left-[190px] hidden items-center gap-2.5 rounded-2xl bg-card px-4 py-2.5 text-sm shadow-card sm:flex">
            <span className="flex size-7 items-center justify-center rounded-full bg-green-100 text-green-700">
              <Check className="size-4" />
            </span>
            Matched by reference, no one lifted a finger
          </div>
        </div>
      </div>
    </section>
  );
}
