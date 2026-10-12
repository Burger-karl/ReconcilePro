"use client";

/** One bank or Paystack line on its own page: what phones get instead of the Statements inspector. */

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Screen } from "@/components/app-shell/screen";
import { TransactionPanel } from "@/components/statements/transaction-panel";
import { Button } from "@/components/ui/button";

export default function TransactionPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <Screen
      title="Statement line"
      actions={
        <Button asChild variant="ghost" size="sm">
          <Link href="/statements">
            <ArrowLeft aria-hidden />
            All lines
          </Link>
        </Button>
      }
    >
      <div className="mx-auto max-w-xl rounded-lg border bg-canvas">
        <TransactionPanel transactionId={id} />
      </div>
    </Screen>
  );
}
