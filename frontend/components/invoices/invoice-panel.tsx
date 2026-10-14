"use client";

/**
 * One invoice in full: the layout C inspector on wide screens, a full page on phones (/invoices/[id]).
 * Status, paid and outstanding are DERIVED by the API from non-reversed allocations (invariant 5);
 * this panel shows them and offers only the actions the API allows in that status.
 */

import { Check, Copy, Mail, Pencil, Send, Undo2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import useSWR, { useSWRConfig } from "swr";

import { ReasonDialog } from "@/components/invoices/reason-dialog";
import { type InvoiceStatus, StatusBadge } from "@/components/status-badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { API, ApiError, api, type Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { refreshAfterChange } from "@/lib/refresh";
import { cn } from "@/lib/utils";

type Detail = Schemas["InvoiceDetail"];
type Payment = Schemas["InvoicePayment"];

const OPEN: InvoiceStatus[] = ["sent", "part_paid", "overdue"];
const date = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short", year: "numeric" });
const asDate = (isoDate: string) => date.format(new Date(`${isoDate}T00:00:00`));
const METHOD: Record<string, string> = { auto: "Matched automatically", suggested: "Suggestion accepted", manual: "Matched by hand" };

export function InvoicePanel({ invoiceId, onEdit }: { invoiceId: string; onEdit: (invoice: Detail) => void }) {
  const { data: invoice, error } = useSWR<Detail>(`${API}/invoices/${invoiceId}`);
  const { mutate } = useSWRConfig();
  const [sendOpen, setSendOpen] = useState(false);
  const [voidOpen, setVoidOpen] = useState(false);
  const [reversing, setReversing] = useState<Payment | null>(null);
  const [copied, setCopied] = useState(false);
  const [emailing, setEmailing] = useState(false);

  if (error) return <p className="p-5 text-sm text-muted-foreground">{error instanceof Error ? error.message : "Couldn't load this invoice."}</p>;
  if (!invoice) return <Skeleton className="m-5 h-96" />;

  const status = invoice.status as InvoiceStatus;
  const number = invoice.number;
  // No link for a void invoice: there is nothing to pay (the API refuses payment for it anyway).
  const link =
    invoice.public_token && status !== "void" ? `${window.location.origin}/i/${invoice.public_token}` : null;
  const refresh = () => refreshAfterChange(mutate);
  // Read the id here, not inside the dialog's callback with `reversing!.id`: the React Compiler caches that
  // callback and checks what it reads on EVERY render, so `reversing!.id` crashed while nothing was selected.
  const reversingId = reversing?.id ?? null;

  async function send() {
    try {
      // The API emails the payment link itself when the customer has an email (backend D-60).
      const sent = await api<Schemas["SentInvoice"]>(`${API}/invoices/${invoiceId}/send`, { method: "POST" });
      toast.success(
        sent.emailed_to
          ? `${number} sent and emailed to ${sent.emailed_to}.`
          : `${number} sent. This customer has no email, so copy the payment link and share it yourself.`,
      );
      await refresh();
    } catch (caught) {
      toast.error(caught instanceof ApiError ? caught.message : "Couldn't send the invoice.");
    }
  }

  async function emailAgain() {
    setEmailing(true);
    try {
      const result = await api<Schemas["EmailResult"]>(`${API}/invoices/${invoiceId}/email`, { method: "POST" });
      toast.success(`Payment link emailed to ${result.emailed_to}.`);
      await refresh();
    } catch (caught) {
      // e.g. 409 "This customer has no email address. Add one on the Customers page, or copy the payment link."
      toast.error(caught instanceof ApiError ? caught.message : "Couldn't email the invoice.");
    } finally {
      setEmailing(false);
    }
  }

  async function copyLink() {
    if (!link) return;
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex flex-col gap-5 p-5">
      <header className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h2 className="font-mono text-lg font-semibold">{invoice.number}</h2>
          <StatusBadge status={status} />
        </div>
        <p className="text-sm">{invoice.customer_name}</p>
        <p className="text-sm text-muted-foreground">{invoice.description}</p>
      </header>

      {/* Money, right-aligned with tabular figures (frontend/CLAUDE.md). */}
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Subtotal</dt>
        <dd className="text-right tabular-nums">{formatNaira(invoice.subtotal_kobo)}</dd>
        <dt className="text-muted-foreground">VAT 7.5%</dt>
        <dd className="text-right tabular-nums">{formatNaira(invoice.vat_kobo)}</dd>
        <dt className="font-medium">Total</dt>
        <dd className="text-right font-medium tabular-nums">{formatNaira(invoice.total_kobo)}</dd>
        <dt className="text-muted-foreground">Paid</dt>
        <dd className="text-right tabular-nums">{formatNaira(invoice.paid_kobo)}</dd>
        <dt className="font-semibold">Outstanding</dt>
        <dd className="text-right font-semibold tabular-nums">{formatNaira(invoice.outstanding_kobo)}</dd>
      </dl>

      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">Issued</dt>
          <dd>{asDate(invoice.issue_date)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Due</dt>
          <dd>{asDate(invoice.due_date)}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-xs text-muted-foreground">Payment reference</dt>
          <dd>
            <span className="font-mono">{invoice.reference}</span>
            <span className="block text-xs text-muted-foreground">
              Ask the customer to put this in the transfer narration: it is matched automatically.
            </span>
          </dd>
        </div>
      </dl>

      <div className="flex flex-wrap gap-2">
        {status === "draft" && (
          <>
            <Button onClick={() => setSendOpen(true)}>
              <Send aria-hidden />
              Send
            </Button>
            <Button variant="outline" onClick={() => onEdit(invoice)}>
              <Pencil aria-hidden />
              Edit
            </Button>
          </>
        )}
        {link && (
          <Button variant="outline" onClick={() => void copyLink()}>
            {copied ? <Check className="animate-pop" aria-hidden /> : <Copy aria-hidden />}
            {copied ? "Copied" : "Copy payment link"}
          </Button>
        )}
        {OPEN.includes(status) && invoice.outstanding_kobo > 0 && (
          <Button variant="outline" onClick={() => void emailAgain()} disabled={emailing}>
            <Mail aria-hidden />
            {emailing ? "Emailing…" : "Email to customer"}
          </Button>
        )}
        {(status === "draft" || OPEN.includes(status)) && (
          <Button
            variant="ghost"
            className="text-destructive"
            onClick={() => setVoidOpen(true)}
            // The API refuses to void an invoice with money on it (409): reverse its payments first.
            disabled={invoice.paid_kobo > 0}
            title={invoice.paid_kobo > 0 ? "Reverse its payments first" : undefined}
          >
            Void
          </Button>
        )}
      </div>

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Payments</h3>
        {invoice.payments.length === 0 ? (
          <p className="text-sm text-muted-foreground">No payments yet.</p>
        ) : (
          <ul className="divide-y rounded-lg border bg-background">
            {invoice.payments.map((payment) => {
              const reversed = payment.reversed_at !== null;
              return (
                <li key={payment.id} className="flex flex-col gap-1 p-3 text-sm">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className={cn("font-medium tabular-nums", reversed && "text-muted-foreground line-through")}>
                      {formatNaira(payment.amount_kobo)}
                    </span>
                    <span className="text-xs text-muted-foreground">{asDate(payment.value_date)}</span>
                  </div>
                  <p className="truncate font-mono text-xs text-muted-foreground" title={payment.narration}>
                    {payment.narration}
                  </p>
                  <div className="flex items-center justify-between gap-3 text-xs">
                    <span className="text-muted-foreground">
                      {reversed ? `Reversed: ${payment.reversal_reason}` : (METHOD[payment.method] ?? payment.method)}
                    </span>
                    {!reversed && (
                      <Button variant="ghost" size="sm" className="h-7" onClick={() => setReversing(payment)}>
                        <Undo2 aria-hidden />
                        Reverse
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <AlertDialog open={sendOpen} onOpenChange={setSendOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Send {invoice.number}?</AlertDialogTitle>
            <AlertDialogDescription>
              It can&apos;t be edited after this. It gets a payment link, emailed to {invoice.customer_name} if they
              have an email address on file.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void send()}>Send invoice</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ReasonDialog
        open={voidOpen}
        onOpenChange={setVoidOpen}
        title={`Void ${invoice.number}?`}
        description="A void invoice stays in your records but is never owed or matched. This can't be undone."
        confirmLabel="Void invoice"
        onConfirm={async (reason) => {
          await api(`${API}/invoices/${invoiceId}/void`, { method: "POST", body: { reason } });
          toast.success(`${invoice.number} voided.`);
          await refresh();
        }}
      />

      <ReasonDialog
        open={reversing !== null}
        onOpenChange={(open) => !open && setReversing(null)}
        title={`Reverse ${reversing ? formatNaira(reversing.amount_kobo) : ""}?`}
        description="The payment goes back to the Match queue. The original record stays, marked reversed."
        confirmLabel="Reverse payment"
        onConfirm={async (reason) => {
          if (!reversingId) return;
          await api(`${API}/allocations/${reversingId}/reverse`, { method: "POST", body: { reason } });
          toast.success("Payment reversed. It is back in the Match queue.");
          await refresh();
        }}
      />
    </div>
  );
}
