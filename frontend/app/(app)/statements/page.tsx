"use client";

/**
 * Statements (slice F6): import a bank CSV, then see every money-in line (bank and Paystack) and where its
 * money went. Layout C: ledger + inspector on wide screens, /transactions/[id] on phones.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import useSWR from "swr";

import { Screen } from "@/components/app-shell/screen";
import { TransactionPanel } from "@/components/statements/transaction-panel";
import { UploadCard } from "@/components/statements/upload-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { API, type Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { cn } from "@/lib/utils";

type Line = Schemas["TransactionRead"];

// Each tab is one API filter: state is worked out from non-reversed allocations on the server.
const TABS = [
  { key: "all", label: "All", params: {} },
  { key: "unallocated", label: "Unmatched", params: { kind: "credit", state: "unallocated" } },
  { key: "part", label: "Part matched", params: { state: "part" } },
  { key: "allocated", label: "Matched", params: { state: "allocated" } },
  { key: "settlement", label: "Paystack payouts", params: { kind: "settlement" } },
] as const;
const PAGE = 50;
const shortDate = new Intl.DateTimeFormat("en-NG", { day: "numeric", month: "short" });
const asDate = (isoDate: string) => shortDate.format(new Date(`${isoDate}T00:00:00`));

/** MASTER.md §1: settlement = slate "Settlement"; money still unmatched = amber "Needs review". Word always shown. */
function LineBadge({ line }: { line: Line }) {
  if (line.kind === "settlement") {
    return <Badge variant="outline" className="border-transparent bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400">Settlement</Badge>;
  }
  if (line.unallocated_kobo === 0) {
    return <Badge variant="outline" className="border-transparent bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-400">Matched</Badge>;
  }
  return (
    <Badge variant="outline" className="border-transparent bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
      {line.allocated_kobo > 0 ? "Part matched" : "Needs review"}
    </Badge>
  );
}

export default function StatementsPage() {
  // useSearchParams() needs a Suspense boundary in the App Router (Next 16 docs: use-search-params).
  return (
    <Suspense>
      <StatementsScreen />
    </Suspense>
  );
}

function StatementsScreen() {
  const router = useRouter();
  // The dashboard's "Collected this month" tile links here with ?tab=allocated (D-70).
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>(
    () => TABS.find((entry) => entry.key === searchParams.get("tab"))?.key ?? "all",
  );
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const filter = TABS.find((entry) => entry.key === tab)!.params;
  const params = new URLSearchParams({ ...filter, limit: String(PAGE), offset: String(offset) });
  const { data, error, isLoading } = useSWR<Schemas["TransactionList"]>(`${API}/transactions?${params}`);

  function open(line: Line) {
    if (window.matchMedia("(min-width: 1024px)").matches) setSelectedId(line.id);
    else router.push(`/transactions/${line.id}`);
  }

  return (
    <Screen
      title="Statements"
      description="Import bank statements; every money-in line and where it went."
      inspector={
        selectedId ? (
          <TransactionPanel transactionId={selectedId} />
        ) : (
          <p className="p-5 text-sm text-muted-foreground">Select a line to see which invoices its money paid.</p>
        )
      }
    >
      <div className="flex flex-col gap-6">
        <UploadCard />

        <section className="flex flex-col gap-3">
          <div role="tablist" aria-label="Filter lines" className="flex flex-wrap gap-1">
            {TABS.map((entry) => (
              <Button
                key={entry.key}
                role="tab"
                aria-selected={tab === entry.key}
                size="sm"
                variant={tab === entry.key ? "default" : "ghost"}
                onClick={() => {
                  setTab(entry.key);
                  setOffset(0);
                }}
              >
                {entry.label}
              </Button>
            ))}
          </div>

          {error ? (
            <p className="text-sm text-muted-foreground">{error instanceof Error ? error.message : "Couldn't load lines."}</p>
          ) : isLoading || !data ? (
            <Skeleton className="h-72 w-full" />
          ) : data.items.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              {tab === "all" ? "No lines yet. Import your first statement above." : "No lines in this view."}
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Narration</TableHead>
                    <TableHead className="hidden md:table-cell">Status</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="hidden text-right sm:table-cell">Unmatched</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((line) => (
                    <TableRow
                      key={line.id}
                      onClick={() => open(line)}
                      onKeyDown={(event) => event.key === "Enter" && open(line)}
                      tabIndex={0}
                      aria-selected={line.id === selectedId}
                      className={cn("cursor-pointer", line.id === selectedId && "bg-muted")}
                    >
                      <TableCell className="whitespace-nowrap">{asDate(line.value_date)}</TableCell>
                      <TableCell className="max-w-72">
                        <span className="block truncate font-mono text-xs">{line.narration}</span>
                        <span className="text-xs text-muted-foreground">{line.source === "paystack" ? "Paystack" : "Bank"}</span>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <LineBadge line={line} />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{formatNaira(line.amount_kobo)}</TableCell>
                      <TableCell className="hidden text-right tabular-nums sm:table-cell">
                        {line.kind === "settlement" ? "—" : formatNaira(line.unallocated_kobo)}
                      </TableCell>
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
        </section>
      </div>
    </Screen>
  );
}
