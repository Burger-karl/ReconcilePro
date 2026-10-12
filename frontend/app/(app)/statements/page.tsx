import { ComingNext, Screen } from "@/components/app-shell/screen";

export default function StatementsPage() {
  return (
    <Screen title="Statements" description="Upload bank statements; we match what we can.">
      <ComingNext slice="F6" points={["CSV upload with an import summary", "Every bank and Paystack credit"]} />
    </Screen>
  );
}
