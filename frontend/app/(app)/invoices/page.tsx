import { ComingNext, Screen } from "@/components/app-shell/screen";

export default function InvoicesPage() {
  return (
    <Screen title="Invoices" description="Every invoice with its live status.">
      <ComingNext
        slice="F4"
        points={[
          "Invoice ledger filtered by status",
          "Inspector with the payments received",
          "Create, send and void invoices",
        ]}
      />
    </Screen>
  );
}
