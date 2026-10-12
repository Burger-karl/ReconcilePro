"use client";

/**
 * Customers (slice F5): who owes what, and the names they pay under. Layout C: list + inspector on wide
 * screens, /customers/[id] on phones.
 */

import { Plus, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR, { useSWRConfig } from "swr";

import { Screen } from "@/components/app-shell/screen";
import { CustomerFormDialog } from "@/components/customers/customer-form-dialog";
import { CustomerPanel } from "@/components/customers/customer-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { API, type Schemas } from "@/lib/api";
import { formatNaira } from "@/lib/money";
import { refreshAfterChange } from "@/lib/refresh";
import { cn } from "@/lib/utils";

type Customer = Schemas["CustomerRead"];
const PAGE = 50;

export default function CustomersPage() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<{ open: boolean; customer?: Customer }>({ open: false });

  // Search a moment after typing stops (300ms), not on every keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search.trim());
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
  if (query) params.set("q", query);
  const { data, error, isLoading } = useSWR<Schemas["CustomerList"]>(`${API}/customers?${params}`);

  function open(customer: Customer) {
    if (window.matchMedia("(min-width: 1024px)").matches) setSelectedId(customer.id);
    else router.push(`/customers/${customer.id}`);
  }

  return (
    <Screen
      title="Customers"
      description="Who owes you, and the names they pay under."
      actions={
        <Button onClick={() => setForm({ open: true })}>
          <Plus aria-hidden />
          Add customer
        </Button>
      }
      inspector={
        selectedId ? (
          <CustomerPanel customerId={selectedId} onEdit={(customer) => setForm({ open: true, customer })} />
        ) : (
          <p className="p-5 text-sm text-muted-foreground">Select a customer to see their invoices and bank names.</p>
        )
      }
    >
      <div className="flex flex-col gap-4">
        <div className="relative w-full sm:w-72">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            aria-label="Search customers"
            placeholder="Name or bank name"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="pl-8 text-base sm:text-sm"
          />
        </div>

        {error ? (
          <p className="text-sm text-muted-foreground">{error instanceof Error ? error.message : "Couldn't load customers."}</p>
        ) : isLoading || !data ? (
          <Skeleton className="h-72 w-full" />
        ) : data.items.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
            {query ? "No customer matches that name." : "No customers yet. Add the businesses you invoice."}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="hidden md:table-cell">Names on bank statements</TableHead>
                  <TableHead className="hidden sm:table-cell">Email</TableHead>
                  <TableHead className="text-right">Outstanding</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((customer) => (
                  <TableRow
                    key={customer.id}
                    onClick={() => open(customer)}
                    onKeyDown={(event) => event.key === "Enter" && open(customer)}
                    tabIndex={0}
                    aria-selected={customer.id === selectedId}
                    className={cn("cursor-pointer", customer.id === selectedId && "bg-muted")}
                  >
                    <TableCell className="font-medium">{customer.name}</TableCell>
                    <TableCell className="hidden max-w-64 truncate font-mono text-xs text-muted-foreground md:table-cell">
                      {customer.aliases.join(" · ") || "—"}
                    </TableCell>
                    <TableCell className="hidden max-w-56 truncate text-muted-foreground sm:table-cell">
                      {customer.email ?? "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{formatNaira(customer.outstanding_kobo)}</TableCell>
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

      <CustomerFormDialog
        open={form.open}
        customer={form.customer}
        onOpenChange={(next) => setForm((current) => ({ ...current, open: next }))}
        onSaved={(saved) => {
          setSelectedId(saved.id);
          void refreshAfterChange(mutate);
        }}
      />
    </Screen>
  );
}
