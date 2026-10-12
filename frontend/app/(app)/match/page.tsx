"use client";

/**
 * Match payments (slice F3, pages/reconciliation.md): the signature screen.
 * Left: bank credits with money still unmatched. Right: the selected credit in full and up to three
 * ranked candidate invoices, each with its score breakdown and plain-English reasons.
 *
 * Every money movement is a POST to /reconciliation/allocate, which goes through allocate() on the
 * server (invariant 4). The screen never changes a number itself: after each action it asks the API
 * again (SWR mutate), so what you see is always what the database says.
 */

import { ArrowLeft, Keyboard, Upload } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import useSWR, { useSWRConfig } from "swr";

import { Screen } from "@/components/app-shell/screen";
import { AllocateDialog } from "@/components/match/allocate-dialog";
import { CandidateCard } from "@/components/match/candidate-card";
import { CreditList, formatValueDate } from "@/components/match/credit-list";
import { ShortcutsDialog } from "@/components/match/shortcuts-dialog";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { Skeleton } from "@/components/ui/skeleton";
import { API, ApiError, api, type Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

type Item = Schemas["QueueItem"];
type Candidate = Schemas["CandidateRead"];
type Allocation = Schemas["AllocationRead"];
type DialogTarget = { invoice_id: string; invoice_number: string; customer_name: string; outstanding_kobo: number };

const QUEUE = `${API}/reconciliation/queue`;
const FADE_MS = 200; // the resolved row fades out this long before the list refreshes (pages/reconciliation.md)

const message = (caught: unknown) => (caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");

export default function MatchPage() {
  const { data, error, isLoading } = useSWR<Schemas["Queue"]>(QUEUE);
  const { mutate } = useSWRConfig();
  const items = useMemo(() => data?.items ?? [], [data]);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [busyInvoice, setBusyInvoice] = useState<string | null>(null);
  const [cardError, setCardError] = useState<{ invoiceId: string; text: string } | null>(null);
  const [leavingId, setLeavingId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{ open: boolean; target: DialogTarget | null }>({ open: false, target: null });
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  // Below 1024px only one pane shows at a time; this says which.
  const [showDetail, setShowDetail] = useState(false);

  // The selected credit: the one clicked, or the first in the queue.
  const index = Math.max(0, items.findIndex((item) => item.transaction.id === selectedId));
  const item: Item | undefined = items[index];

  const select = useCallback((id: string, openDetail = true) => {
    setSelectedId(id);
    setCardError(null);
    if (openDetail) setShowDetail(true);
  }, []);

  // When the credit changes, preselect its suggested invoice (or the best candidate).
  const creditId = item?.transaction.id;
  const suggestedIndex = item ? Math.max(0, item.candidates.findIndex((c) => c.invoice_id === item.suggested_invoice_id)) : 0;
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset the highlighted card when another credit is shown
    setCandidateIndex(suggestedIndex);
  }, [creditId, suggestedIndex]);

  /** Ask the API again: the queue, and the dashboard summary that feeds the rail's badge. */
  const refresh = useCallback(
    () => Promise.all([mutate(QUEUE), mutate(`${API}/dashboard/summary`)]),
    [mutate],
  );

  const undo = useCallback(
    async (allocationId: string) => {
      try {
        // A real reversal with its own audit row (invariant 7), not a client-side trick.
        await api(`${API}/allocations/${allocationId}/reverse`, {
          method: "POST",
          body: { reason: "Undone straight after matching" },
        });
        toast.success("Match undone. The payment is back in the queue.");
      } catch (caught) {
        toast.error(message(caught));
      }
      await refresh();
    },
    [refresh],
  );

  /** After the server confirmed an allocation: toast with Undo, fade the row if it's fully matched, refresh. */
  const afterAllocated = useCallback(
    async (credit: Item["transaction"], allocation: Allocation, invoiceNumber: string) => {
      toast.success(`Allocated ${formatNaira(allocation.amount_kobo)} to ${invoiceNumber}`, {
        action: { label: "Undo", onClick: () => void undo(allocation.id) },
      });
      if (allocation.amount_kobo >= credit.unallocated_kobo) {
        const position = items.findIndex((entry) => entry.transaction.id === credit.id);
        const next = items[position + 1] ?? items[position - 1];
        setLeavingId(credit.id);
        await new Promise((resolve) => setTimeout(resolve, FADE_MS));
        setSelectedId(next?.transaction.id ?? null);
        setLeavingId(null);
      }
      await refresh();
    },
    [items, refresh, undo],
  );

  const accept = useCallback(
    async (credit: Item, candidate: Candidate) => {
      setBusyInvoice(candidate.invoice_id);
      setCardError(null);
      try {
        const allocation = await api<Allocation>(`${API}/reconciliation/allocate`, {
          method: "POST",
          body: {
            transaction_id: credit.transaction.id,
            invoice_id: candidate.invoice_id,
            amount_kobo: Math.min(credit.transaction.unallocated_kobo, candidate.outstanding_kobo),
            // "suggested" when the matcher proposed this invoice, otherwise the accountant chose it.
            method: candidate.invoice_id === credit.suggested_invoice_id ? "suggested" : "manual",
          },
        });
        await afterAllocated(credit.transaction, allocation, candidate.invoice_number);
      } catch (caught) {
        // The server refused (e.g. someone else matched it first): the row stays, the reason shows on the card.
        setCardError({ invoiceId: candidate.invoice_id, text: message(caught) });
      } finally {
        setBusyInvoice(null);
      }
    },
    [afterAllocated],
  );

  const reject = useCallback(
    async (credit: Item, candidate: Candidate) => {
      setBusyInvoice(candidate.invoice_id);
      setCardError(null);
      try {
        // Recorded as an audit event; this pair is never suggested again (backend D-28).
        await api(`${API}/reconciliation/reject`, {
          method: "POST",
          body: { transaction_id: credit.transaction.id, invoice_id: candidate.invoice_id },
        });
        toast(`${candidate.invoice_number} won't be suggested for this payment again.`);
        await refresh();
      } catch (caught) {
        setCardError({ invoiceId: candidate.invoice_id, text: message(caught) });
      } finally {
        setBusyInvoice(null);
      }
    },
    [refresh],
  );

  const openAllocate = useCallback((candidate: Candidate | undefined) => {
    setDialog({
      open: true,
      target: candidate
        ? {
            invoice_id: candidate.invoice_id,
            invoice_number: candidate.invoice_number,
            customer_name: candidate.customer_name,
            outstanding_kobo: candidate.outstanding_kobo,
          }
        : null,
    });
  }, []);

  // Keyboard: J/K, 1–3, A, M, R, ? (pages/reconciliation.md). Ignored while typing or while a dialog is open.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey || dialog.open || shortcutsOpen) return;
      // The target can be the window itself (not an element), so check before calling closest().
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest("input, textarea, select, [contenteditable=true], [role=dialog]")) return;
      const key = event.key.toLowerCase();
      if (key === "?") return setShortcutsOpen(true);
      if (!item) return;
      const candidate = item.candidates[candidateIndex];
      if (key === "j" && items[index + 1]) select(items[index + 1].transaction.id, false);
      else if (key === "k" && items[index - 1]) select(items[index - 1].transaction.id, false);
      else if (["1", "2", "3"].includes(key) && item.candidates[Number(key) - 1]) setCandidateIndex(Number(key) - 1);
      else if (key === "a" && candidate && !busyInvoice) void accept(item, candidate);
      else if (key === "r" && candidate && !busyInvoice) void reject(item, candidate);
      else if (key === "m") openAllocate(candidate);
      else return;
      event.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item, items, index, candidateIndex, busyInvoice, dialog.open, shortcutsOpen, select, accept, reject, openAllocate]);

  const shortcutsButton = (
    <Button variant="outline" size="sm" onClick={() => setShortcutsOpen(true)}>
      <Keyboard aria-hidden />
      Shortcuts
      <Kbd>?</Kbd>
    </Button>
  );

  return (
    <Screen
      title="Match payments"
      description={
        data ? `${data.total} payment${data.total === 1 ? "" : "s"} waiting. Confirm the match, or pick the invoice.` : undefined
      }
      actions={shortcutsButton}
      flush
    >
      {isLoading ? (
        <div className="flex flex-1 gap-4 p-4 sm:p-6">
          <Skeleton className="h-full w-full lg:w-2/5" />
          <Skeleton className="hidden h-full flex-1 lg:block" />
        </div>
      ) : error ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-sm">
          <p className="text-muted-foreground">{message(error)}</p>
          <Button variant="outline" onClick={() => void mutate(QUEUE)}>
            Try again
          </Button>
        </div>
      ) : !item ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
          <p className="text-lg font-medium">All caught up: no payments need review.</p>
          <p className="text-sm text-muted-foreground">New bank lines are matched as soon as you import a statement.</p>
          <Button asChild variant="outline">
            <Link href="/statements">
              <Upload aria-hidden />
              Upload a statement
            </Link>
          </Button>
        </div>
      ) : (
        <>
          {/* Left pane, 40% (pages/reconciliation.md). On phones it hides while a payment is open. */}
          <div className={cn("w-full overflow-y-auto border-r lg:block lg:w-2/5", showDetail && "hidden")}>
            <CreditList items={items} selectedId={item.transaction.id} leavingId={leavingId} onSelect={select} />
          </div>

          {/* Right pane, 60%: the selected payment in full, then its candidates. */}
          <section
            aria-label="Selected payment"
            className={cn("flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-6 lg:flex", showDetail ? "flex" : "hidden")}
          >
            <Button variant="ghost" size="sm" className="self-start lg:hidden" onClick={() => setShowDetail(false)}>
              <ArrowLeft aria-hidden />
              All payments
            </Button>

            <div className="rounded-lg border bg-canvas p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                    {item.transaction.source === "paystack" ? "Paystack payment" : "Bank credit"} ·{" "}
                    {formatValueDate(item.transaction.value_date)}
                  </p>
                  <p className="mt-1 font-medium">{item.transaction.payer_name ?? "Payer not recognised"}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">Still to match</p>
                  <p className="text-xl font-semibold tabular-nums">{formatNaira(item.transaction.unallocated_kobo)}</p>
                  {item.transaction.allocated_kobo > 0 && (
                    <p className="text-xs text-muted-foreground tabular-nums">
                      of {formatNaira(item.transaction.amount_kobo)}
                    </p>
                  )}
                </div>
              </div>
              {/* The narration exactly as the bank wrote it, in mono (frontend/CLAUDE.md). */}
              <p className="mt-3 rounded bg-background px-3 py-2 font-mono text-sm break-all">{item.transaction.narration}</p>
              {(item.transaction.bank_reference || item.transaction.balance_kobo !== null) && (
                <p className="mt-2 flex flex-wrap gap-x-4 text-xs text-muted-foreground">
                  {item.transaction.bank_reference && (
                    <span>
                      Bank reference <span className="font-mono text-foreground">{item.transaction.bank_reference}</span>
                    </span>
                  )}
                  {item.transaction.balance_kobo !== null && (
                    <span>
                      Balance after <span className="text-foreground tabular-nums">{formatNaira(item.transaction.balance_kobo)}</span>
                    </span>
                  )}
                </p>
              )}
            </div>

            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-medium">
                {item.candidates.length === 0 ? "No likely invoice found" : "Likely invoices, best first"}
              </h2>
              <Button variant="outline" size="sm" onClick={() => openAllocate(undefined)}>
                Match to another invoice…
              </Button>
            </div>

            {item.candidates.map((candidate, position) => (
              <CandidateCard
                key={candidate.invoice_id}
                candidate={candidate}
                position={position + 1}
                creditUnallocatedKobo={item.transaction.unallocated_kobo}
                suggested={candidate.invoice_id === item.suggested_invoice_id}
                selected={position === candidateIndex}
                busy={busyInvoice === candidate.invoice_id}
                error={cardError?.invoiceId === candidate.invoice_id ? cardError.text : null}
                onSelect={() => setCandidateIndex(position)}
                onAccept={() => void accept(item, candidate)}
                onAllocatePart={() => openAllocate(candidate)}
                onReject={() => void reject(item, candidate)}
              />
            ))}
          </section>

          <AllocateDialog
            key={`${item.transaction.id}-${dialog.target?.invoice_id ?? "any"}`}
            credit={item.transaction}
            target={dialog.target}
            open={dialog.open}
            onOpenChange={(open) => setDialog((current) => ({ ...current, open }))}
            onAllocated={(allocation, invoiceNumber) => void afterAllocated(item.transaction, allocation, invoiceNumber)}
          />
        </>
      )}
      <ShortcutsDialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
    </Screen>
  );
}
