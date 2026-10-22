"use client";

/**
 * The customer's invoice page (slice F8, design-system pages/public-invoice.md). No login: the only key is
 * the unguessable token in the link (backend D-12). Built for a 375px phone first.
 *
 * Paying online: "Pay with Paystack" asks our API for a checkout link for exactly what is still owed
 * (backend D-34) and sends the customer there. Paystack then sends them back here with ?reference=... in the
 * URL. That URL proves nothing (anyone can type it), so this page never says "paid" because of it: it shows
 * "confirming" and re-asks the API until the Paystack webhook has recorded the money (backend D-30).
 *
 * Look (D-71): orange line on top of the card, light orange wash behind it, the card fades up, the paid tick pops in.
 */

import { Check, CircleAlert, Copy, Loader2 } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";
import useSWR from "swr";

import { type InvoiceStatus, StatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { API, ApiError, api, swrFetcher, type Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";

type PublicInvoice = Schemas["PublicInvoice"];

const OPEN: InvoiceStatus[] = ["sent", "part_paid", "overdue"];
const CONFIRM_FOR_MS = 60_000; // how long to keep re-checking after returning from Paystack
const date = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "long", year: "numeric" });
const asDate = (isoDate: string) => date.format(new Date(`${isoDate}T00:00:00`));

/**
 * Only ever send the customer to Paystack's own checkout. The URL comes from our API (which got it from
 * Paystack), but checking the address costs one line and stops this page becoming a redirect to anywhere.
 */
function isPaystackCheckout(url: string): boolean {
  try {
    const { protocol, hostname } = new URL(url);
    return protocol === "https:" && (hostname === "paystack.com" || hostname.endsWith(".paystack.com"));
  } catch {
    return false;
  }
}

function InvoiceView() {
  const { token } = useParams<{ token: string }>();
  const returnedFromPaystack = useSearchParams().has("reference");
  // Flips to true a minute after returning from Paystack; until then the page keeps re-checking.
  const [windowOver, setWindowOver] = useState(false);
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);
  // Which value was just copied ("reference" or "account"), so only that button shows a tick.
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    if (!returnedFromPaystack) return;
    const timer = setTimeout(() => setWindowOver(true), CONFIRM_FOR_MS);
    return () => clearTimeout(timer);
  }, [returnedFromPaystack]);

  const { data: invoice, error } = useSWR<PublicInvoice>(`${API}/public/invoices/${encodeURIComponent(token)}`, swrFetcher, {
    // Back from Paystack and not paid yet: ask again every 3 seconds for up to a minute, until the webhook lands.
    refreshInterval: (latest) =>
      returnedFromPaystack && !windowOver && latest?.status !== "paid" ? 3000 : 0,
    // SWR normally pauses polling in a background tab. Keep going during this one minute (at most ~20 small
    // requests): a customer who switches to their banking app should come back to an up-to-date page.
    refreshWhenHidden: true,
  });

  async function pay() {
    setPaying(true);
    setPayError(null);
    try {
      const link = await api<Schemas["PaymentLink"]>(`${API}/public/invoices/${encodeURIComponent(token)}/pay`, {
        method: "POST",
      });
      if (!isPaystackCheckout(link.authorization_url)) throw new Error("Unexpected payment address.");
      window.location.href = link.authorization_url; // the button stays disabled while the browser leaves
    } catch (caught) {
      // e.g. 409 "Online payment isn't set up for this invoice. Please pay by bank transfer." or 502.
      setPayError(caught instanceof ApiError ? caught.message : "Online payment is unavailable right now. Please try again.");
      setPaying(false);
    }
  }

  async function copy(what: "reference" | "account", value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(what);
    toast.success(what === "reference" ? "Reference copied" : "Account number copied");
    setTimeout(() => setCopied(null), 2000);
  }

  if (error) {
    // Unknown or mistyped link: say so plainly, with no hints about other invoices.
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <p className="text-lg font-semibold">{notFound ? "Invoice not found" : "This invoice can't be shown right now"}</p>
        <p className="text-sm text-muted-foreground">
          {notFound ? "Check the link you were sent, or ask the business for a new one." : "Please try again in a moment."}
        </p>
      </div>
    );
  }
  if (!invoice) return <Skeleton className="h-[560px] w-full rounded-xl" />;

  const status = invoice.status as InvoiceStatus;
  const open = OPEN.includes(status) && invoice.outstanding_kobo > 0;
  const confirming = returnedFromPaystack && open && !windowOver;
  const account = invoice.bank_account_number; // null until the business saves its bank details

  return (
    <article className="animate-rise flex flex-col gap-6 rounded-xl border border-t-4 border-t-primary bg-card p-6 shadow-lg sm:p-8">
      <header className="flex flex-col gap-2">
        <p className="text-sm text-muted-foreground">Invoice from</p>
        <h1 className="text-xl font-semibold">{invoice.business_name}</h1>
        <p className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm">{invoice.number}</span>
          <StatusBadge status={status} />
        </p>
      </header>

      {status === "void" ? (
        <p className="rounded-lg bg-muted p-4 text-sm">This invoice was cancelled. There is nothing to pay.</p>
      ) : (
        <section aria-label="Amount due">
          <p className="text-sm text-muted-foreground">Amount due</p>
          {/* 36px, the one number this page is about (pages/public-invoice.md). */}
          <p className="text-4xl font-semibold tracking-tight tabular-nums">{formatNaira(invoice.outstanding_kobo)}</p>
          {status !== "paid" && <p className="mt-1 text-sm text-muted-foreground">Due {asDate(invoice.due_date)}</p>}
        </section>
      )}

      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Bill to</dt>
        <dd>{invoice.customer_name}</dd>
        <dt className="text-muted-foreground">For</dt>
        <dd>{invoice.description}</dd>
        <dt className="text-muted-foreground">Issued</dt>
        <dd>{asDate(invoice.issue_date)}</dd>
      </dl>

      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 border-t pt-4 text-sm">
        <dt className="text-muted-foreground">Subtotal</dt>
        <dd className="text-right tabular-nums">{formatNaira(invoice.subtotal_kobo)}</dd>
        <dt className="text-muted-foreground">VAT 7.5%</dt>
        <dd className="text-right tabular-nums">{formatNaira(invoice.vat_kobo)}</dd>
        <dt className="font-medium">Total</dt>
        <dd className="text-right font-medium tabular-nums">{formatNaira(invoice.total_kobo)}</dd>
        {invoice.paid_kobo > 0 && (
          <>
            <dt className="text-muted-foreground">Paid so far</dt>
            <dd className="text-right tabular-nums">{formatNaira(invoice.paid_kobo)}</dd>
          </>
        )}
      </dl>

      {status === "paid" && (
        <p className="flex items-center gap-2 rounded-lg bg-green-50 p-4 text-sm font-medium text-green-700">
          <Check className="animate-pop size-5 shrink-0" aria-hidden />
          {/* last_paid_on: the day the latest payment reached the business's account (backend D-61). */}
          Thank you — payment received{invoice.last_paid_on ? ` on ${asDate(invoice.last_paid_on)}` : ""}.
        </p>
      )}

      {confirming && (
        <p role="status" className="flex items-center gap-2 rounded-lg bg-muted p-4 text-sm">
          <Loader2 className="size-5 shrink-0 motion-safe:animate-spin" aria-hidden />
          Thanks! We&apos;re confirming your payment with Paystack. This page updates by itself.
        </p>
      )}
      {returnedFromPaystack && open && !confirming && (
        <p role="status" className="rounded-lg bg-muted p-4 text-sm">
          Your payment hasn&apos;t shown up yet. That can take a few minutes; Paystack has emailed you a receipt. Refresh
          this page later.
        </p>
      )}

      {open && !confirming && (
        <div className="flex flex-col gap-2">
          {payError && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden />
              <AlertDescription>{payError}</AlertDescription>
            </Alert>
          )}
          {/* Full width, 48px tall, charges exactly what is still owed (pages/public-invoice.md, backend D-34). */}
          <Button onClick={() => void pay()} disabled={paying} className="h-12 w-full text-base">
            {paying && <Loader2 className="motion-safe:animate-spin" aria-hidden />}
            {paying ? "Opening Paystack…" : `Pay ${formatNaira(invoice.outstanding_kobo)} with Paystack`}
          </Button>
        </div>
      )}

      {open && (
        <section className="flex flex-col gap-2 rounded-lg border bg-canvas p-4">
          <h2 className="text-sm font-medium">Or pay by bank transfer</h2>
          {/* The business's account, saved by its owner in Settings (backend D-61). Until then the customer
              is told to ask, rather than shown nothing and left guessing. */}
          {account ? (
            <div className="flex flex-col gap-1">
              <p className="text-sm">
                {invoice.bank_name} · {invoice.bank_account_name}
              </p>
              <div className="flex items-center gap-2">
                <span className="flex-1 rounded-md border bg-background px-3 py-2 font-mono text-lg tracking-wider">
                  {account}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  className="size-11"
                  aria-label="Copy account number"
                  onClick={() => void copy("account", account)}
                >
                  {copied === "account" ? <Check className="animate-pop" aria-hidden /> : <Copy aria-hidden />}
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Ask {invoice.business_name} for their account details.</p>
          )}
          <p className="text-sm text-muted-foreground">
            Put this reference in the transfer description so your payment is matched to this invoice straight away.
          </p>
          <div className="flex items-center gap-2">
            <span className="flex-1 rounded-md border bg-background px-3 py-2 font-mono text-lg tracking-wider">
              {invoice.reference}
            </span>
            <Button
              variant="outline"
              size="icon"
              className="size-11"
              aria-label="Copy payment reference"
              onClick={() => void copy("reference", invoice.reference)}
            >
              {copied === "reference" ? <Check className="animate-pop" aria-hidden /> : <Copy aria-hidden />}
            </Button>
          </div>
        </section>
      )}
    </article>
  );
}

export default function PublicInvoicePage() {
  return (
    <main className="flex flex-1 flex-col items-center bg-linear-to-b from-brand-soft to-canvas px-4 py-8 sm:py-12">
      <div className="flex w-full max-w-xl flex-col gap-6">
        {/* useSearchParams() needs a Suspense boundary (Next 16 docs). */}
        <Suspense fallback={<Skeleton className="h-[560px] w-full rounded-xl" />}>
          <InvoiceView />
        </Suspense>
        <p className="text-center text-xs text-muted-foreground">Powered by Reconcile</p>
      </div>
    </main>
  );
}
