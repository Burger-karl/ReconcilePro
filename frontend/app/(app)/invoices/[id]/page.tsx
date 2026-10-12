"use client";

/** One invoice on its own page: what phones get instead of the inspector, and a link that can be shared. */

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useSWRConfig } from "swr";

import { Screen } from "@/components/app-shell/screen";
import { InvoiceFormDialog } from "@/components/invoices/invoice-form-dialog";
import { InvoicePanel } from "@/components/invoices/invoice-panel";
import { Button } from "@/components/ui/button";
import type { Schemas } from "@/lib/api";
import { refreshAfterChange } from "@/lib/refresh";

export default function InvoicePage() {
  const { id } = useParams<{ id: string }>();
  const { mutate } = useSWRConfig();
  const [editing, setEditing] = useState<Schemas["InvoiceRead"] | null>(null);

  return (
    <Screen
      title="Invoice"
      actions={
        <Button asChild variant="ghost" size="sm">
          <Link href="/invoices">
            <ArrowLeft aria-hidden />
            All invoices
          </Link>
        </Button>
      }
    >
      <div className="mx-auto max-w-xl rounded-lg border bg-canvas">
        <InvoicePanel invoiceId={id} onEdit={setEditing} />
      </div>
      <InvoiceFormDialog
        open={editing !== null}
        invoice={editing ?? undefined}
        onOpenChange={(open) => !open && setEditing(null)}
        onSaved={() => void refreshAfterChange(mutate)}
      />
    </Screen>
  );
}
