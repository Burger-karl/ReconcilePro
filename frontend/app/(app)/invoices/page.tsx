"use client";

/**
 * Invoices (slice F4): a dense ledger with status tabs and search; the selected invoice opens in the
 * layout C inspector on the right (wide screens) or on its own page (phones: /invoices/[id]).
 */

import { Plus, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR, { useSWRConfig } from "swr";

import { Screen } from "@/components/app-shell/screen";
import { InvoiceFormDialog } from "@/components/invoices/invoice-form-dialog";
import { InvoicePanel } from "@/components/invoices/invoice-panel";
import { type InvoiceStatus, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { API, type Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { refreshAfterChange } from "@/lib/refresh";
import { cn } from "@/lib/utils";

type Invoice = Schemas["InvoiceRead"];

const TABS: { value: InvoiceStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Drafts" },
  { value: "sent", label: "Sent" },
  { value: "part_paid", label: "Part paid" },
  { value: "overdue", label: "Overdue" },
  { value: "paid", label: "Paid" },
  { value: "void", label: "Void" },
];
const PAGE = 50;
const shortDate = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short" });
const asDate = (isoDate: string) => shortDate.format(new Date(`${isoDate}T00:00:00`));

export default function InvoicesPage() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const [status, setStatus] = useState<InvoiceStatus | "all">("all");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState(""); // the search actually sent, a moment after typing stops
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<{ open: boolean; invoice?: Invoice }>({ open: false });

  // Wait 300ms after the last keystroke before searching, instead of one request per letter.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search.trim());
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
  if (status !== "all") params.set("status", status);
  if (query) params.set("q", query);
  const { data, error, isLoading } = useSWR<Schemas["InvoiceList"]>(`${API}/invoices?${params}`);

  function open(invoice: Invoice) {
    // Wide screens: show it in the inspector. Phones: the inspector is hidden, so go to its own page.
    if (window.matchMedia("(min-width: 1024px)").matches) setSelectedId(invoice.id);
    else router.push(`/invoices/${invoice.id}`);
  }

  return (
    <Screen
      title="Invoices"
      description="Status is worked out from the payments matched to each invoice."
      actions={
        <Button onClick={() => setForm({ open: true })}>
          <Plus aria-hidden />
          New invoice
        </Button>
      }
      inspector={
        selectedId ? (
          <InvoicePanel invoiceId={selectedId} onEdit={(invoice) => setForm({ open: true, invoice })} />
        ) : (
          <p className="p-5 text-sm text-muted-foreground">Select an invoice to see its payments and actions.</p>
        )
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="tablist" aria-label="Filter by status" className="flex flex-wrap gap-1">
            {TABS.map((tab) => (
              <Button
                key={tab.value}
                role="tab"
                aria-selected={status === tab.value}
                size="sm"
                variant={status === tab.value ? "default" : "ghost"}
                onClick={() => {
                  setStatus(tab.value);
                  setOffset(0);
                }}
              >
                {tab.label}
              </Button>
            ))}
          </div>
          <div className="relative w-full sm:w-64">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              aria-label="Search invoices"
              placeholder="Number, reference or customer"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="pl-8 text-base sm:text-sm"
            />
          </div>
        </div>

        {error ? (
          <p className="text-sm text-muted-foreground">{error instanceof Error ? error.message : "Couldn't load invoices."}</p>
        ) : isLoading || !data ? (
          <Skeleton className="h-80 w-full" />
        ) : data.items.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
            {query || status !== "all" ? "No invoices match this filter." : "No invoices yet. Create your first one."}
          </div>
        ) : (
          // The table scrolls sideways inside its own box on narrow screens, never the whole page (MASTER.md §9).
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Number</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead className="hidden md:table-cell">Due</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="text-right">Outstanding</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((invoice) => (
                  <TableRow
                    key={invoice.id}
                    onClick={() => open(invoice)}
                    onKeyDown={(event) => event.key === "Enter" && open(invoice)}
                    tabIndex={0}
                    aria-selected={invoice.id === selectedId}
                    className={cn("cursor-pointer", invoice.id === selectedId && "bg-muted")}
                  >
                    <TableCell className="font-mono">{invoice.number}</TableCell>
                    <TableCell className="max-w-48 truncate">{invoice.customer_name}</TableCell>
                    <TableCell className="hidden md:table-cell">{asDate(invoice.due_date)}</TableCell>
                    <TableCell>
                      <StatusBadge status={invoice.status as InvoiceStatus} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{formatNaira(invoice.total_kobo)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNaira(invoice.outstanding_kobo)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {data && data.total > PAGE && (
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
                Previous
              </Button>
              <Button variant="outline" size="sm" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      <InvoiceFormDialog
        open={form.open}
        invoice={form.invoice}
        onOpenChange={(next) => setForm((current) => ({ ...current, open: next }))}
        onSaved={(saved) => {
          setSelectedId(saved.id);
          void refreshAfterChange(mutate);
        }}
      />
    </Screen>
  );
}
