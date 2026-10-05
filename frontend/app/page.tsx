import { StatusBadge, type InvoiceStatus } from "@/components/status-badge";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNaira } from "@/lib/money";

/**
 * Temporary scaffold page: shows the design tokens working (fonts, colours, badges, money).
 * It is replaced by the real landing page in app/(marketing) when the UI is built.
 */

const STATUSES: InvoiceStatus[] = ["paid", "part_paid", "overdue", "sent", "draft", "void"];

const SAMPLE_ROWS = [
  { number: "INV-0042", customer: "Adaeze Foods", kobo: 25_000_000, status: "paid" },
  { number: "INV-0043", customer: "Kola & Sons", kobo: 9_000_000, status: "part_paid" },
  { number: "INV-0044", customer: "Tunde Print", kobo: 4_000_050, status: "overdue" },
] as const;

export default function Home() {
  return (
    <div className="flex-1 bg-canvas">
      <header className="flex items-center justify-between border-b bg-background px-6 py-3">
        <span className="font-semibold tracking-tight">Reconcile</span>
        <ThemeToggle />
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
        <div>
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Scaffold check</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Design tokens</h1>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Invoice status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {STATUSES.map((status) => (
              <StatusBadge key={status} status={status} />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Money and narrations</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <ul className="divide-y text-sm">
              {SAMPLE_ROWS.map((row) => (
                <li key={row.number} className="flex items-center gap-4 py-2">
                  <span className="w-20 font-mono">{row.number}</span>
                  <span className="flex-1">{row.customer}</span>
                  <span className="text-right tabular-nums">{formatNaira(row.kobo)}</span>
                  <StatusBadge status={row.status} />
                </li>
              ))}
            </ul>
            <p className="rounded-md bg-muted px-3 py-2 font-mono text-xs text-muted-foreground">
              TRF/KOLA AND SONS/INV0043 PART PYMT/FBN
            </p>
            <div className="flex gap-2">
              <Button>Accept match</Button>
              <Button variant="outline">Allocate part…</Button>
              <Button variant="ghost">Not this one</Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
