/**
 * Landing page section: E-invoicing, coming soon (DECISIONS D-72). Nothing here is built yet and nothing is sent
 * anywhere: FIRS integration is listed under "Later" in the project rules, so this only describes the plan.
 *
 * The plan: invoices are pulled from the business's ERP (Sage 200 or Sage 300), checked by ReconcilePro, then
 * passed through an accredited Access Point Provider (for example Interswitch) to the FIRS MBS e-invoicing
 * platform, now run by the Nigeria Revenue Service (NRS). The platform validates each invoice and gives it an
 * Invoice Reference Number (IRN) and a QR code; the signed invoice comes back the same way, is stored with the
 * invoice, and is matched to payments as today. Names describe the plan; there is no partnership.
 */

import { ArrowDown, ArrowRight, BadgeCheck, Building2, Database, FileCheck2, Landmark, Send, ShieldCheck } from "lucide-react";

// The four parties in the flow, left to right. `does` says what each one does with the invoice.
const FLOW = [
  { icon: Database, name: "Sage 200 / Sage 300", role: "Your ERP", does: "Invoices are retrieved from your accounting system." },
  { icon: FileCheck2, name: "ReconcilePro", role: "Checks and prepares", does: "Required fields (TINs, VAT, items) are checked and put in the e-invoice format." },
  { icon: Send, name: "Access Point Provider", role: "For example Interswitch", does: "An accredited provider validates the invoice and transmits it securely." },
  { icon: Landmark, name: "FIRS MBS (NRS)", role: "Tax authority platform", does: "The invoice is validated and given an IRN and QR code, then sent back." },
];

const BENEFITS = [
  { icon: Building2, title: "No double entry", text: "Invoices come straight from Sage, so nobody types them in twice." },
  { icon: ShieldCheck, title: "Checked before sending", text: "Missing TINs or wrong VAT are caught before the tax authority rejects them." },
  { icon: BadgeCheck, title: "Signed invoices kept", text: "Each invoice's IRN and QR code are stored with it, ready to share." },
  { icon: FileCheck2, title: "Matched like today", text: "Signed invoices go into the same matching against your payments." },
];

export function EInvoicingSection() {
  return (
    <section id="e-invoicing" aria-labelledby="e-invoicing-heading" className="scroll-mt-20 px-4 py-20 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-brand-soft px-4 py-1.5 font-nav text-sm text-brand-ink">
            <span className="size-2 rounded-full bg-primary ring-4 ring-primary/25" aria-hidden />
            Coming soon
          </span>
          <h2 id="e-invoicing-heading" className="mt-5 text-3xl leading-tight font-extrabold tracking-tight sm:text-4xl">
            Connect Sage. <span className="text-brand-ink">Get every invoice signed for e-invoicing.</span>
          </h2>
          <p className="mt-4 text-lg font-light text-muted-foreground">
            ReconcilePro will retrieve invoices from Sage 200 and Sage 300 and pass them through an accredited Access
            Point Provider to the FIRS MBS e-invoicing platform, now run by the Nigeria Revenue Service (NRS). Each invoice
            comes back validated and signed with an Invoice Reference Number (IRN) and a QR code, as the e-invoicing
            rules require.
          </p>
        </div>

        <ol className="grid gap-5 lg:grid-cols-4">
          {FLOW.map((step, index) => (
            <li key={step.name} className="relative flex flex-col gap-3 rounded-2xl bg-card p-6 shadow-card">
              <div className="flex items-center justify-between">
                <span className="flex size-12 items-center justify-center rounded-full bg-brand-soft text-brand">
                  <step.icon className="size-5" aria-hidden />
                </span>
                <span className="font-heading text-4xl leading-none font-black text-brand-soft" aria-hidden>
                  0{index + 1}
                </span>
              </div>
              <div>
                <h3 className="text-lg font-extrabold">{step.name}</h3>
                <p className="font-nav text-xs tracking-wide text-brand-ink uppercase">{step.role}</p>
              </div>
              <p className="text-sm text-muted-foreground">{step.does}</p>
              {/* Arrows between the steps: right on wide screens, down when they stack. Decoration. */}
              {index < FLOW.length - 1 && (
                <>
                  <ArrowRight className="absolute top-1/2 -right-4.5 z-10 hidden size-8 -translate-y-1/2 rounded-full bg-primary p-1.5 text-primary-foreground lg:block" aria-hidden />
                  <ArrowDown className="absolute -bottom-4.5 left-1/2 z-10 size-8 -translate-x-1/2 rounded-full bg-primary p-1.5 text-primary-foreground lg:hidden" aria-hidden />
                </>
              )}
            </li>
          ))}
        </ol>
        <p className="mt-6 flex items-center gap-2 rounded-xl bg-brand-soft px-5 py-3.5 text-sm">
          <ArrowRight className="size-4 shrink-0 rotate-180 text-brand" aria-hidden />
          The signed invoice, with its IRN and QR code, comes back through the Access Point Provider and is stored in
          ReconcilePro next to the original.
        </p>

        <ul className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {BENEFITS.map((benefit) => (
            <li key={benefit.title} className="flex gap-4">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
                <benefit.icon className="size-5" aria-hidden />
              </span>
              <div>
                <h3 className="font-extrabold">{benefit.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{benefit.text}</p>
              </div>
            </li>
          ))}
        </ul>

        <p className="mt-10 text-xs text-muted-foreground">
          Not available yet. ReconcilePro isn&apos;t connected to Sage, to any Access Point Provider or to the NRS today.
          Sage, Interswitch, FIRS and NRS are named only to describe the planned flow.
        </p>
      </div>
    </section>
  );
}
