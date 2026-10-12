"use client";

/** One customer on its own page: what phones get instead of the inspector. */

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useSWRConfig } from "swr";

import { Screen } from "@/components/app-shell/screen";
import { CustomerFormDialog } from "@/components/customers/customer-form-dialog";
import { CustomerPanel } from "@/components/customers/customer-panel";
import { Button } from "@/components/ui/button";
import type { Schemas } from "@/lib/api";
import { refreshAfterChange } from "@/lib/refresh";

export default function CustomerPage() {
  const { id } = useParams<{ id: string }>();
  const { mutate } = useSWRConfig();
  const [editing, setEditing] = useState<Schemas["CustomerRead"] | null>(null);

  return (
    <Screen
      title="Customer"
      actions={
        <Button asChild variant="ghost" size="sm">
          <Link href="/customers">
            <ArrowLeft aria-hidden />
            All customers
          </Link>
        </Button>
      }
    >
      <div className="mx-auto max-w-xl rounded-lg border bg-canvas">
        <CustomerPanel customerId={id} onEdit={setEditing} />
      </div>
      <CustomerFormDialog
        open={editing !== null}
        customer={editing ?? undefined}
        onOpenChange={(open) => !open && setEditing(null)}
        onSaved={() => void refreshAfterChange(mutate)}
      />
    </Screen>
  );
}
