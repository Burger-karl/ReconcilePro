import { ComingNext, Screen } from "@/components/app-shell/screen";

export default function OverviewPage() {
  return (
    <Screen title="Overview" description="Where your money is: invoiced, collected, still owed.">
      <ComingNext
        slice="F2"
        points={[
          "Outstanding, collected this month, auto-match rate, needs review",
          "Collections by week and ageing charts",
          "Recent activity from the audit trail",
        ]}
      />
    </Screen>
  );
}
