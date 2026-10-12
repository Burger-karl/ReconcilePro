import { ComingNext, Screen } from "@/components/app-shell/screen";

export default function AuditPage() {
  return (
    <Screen title="Audit log" description="Every change, who made it and when.">
      <ComingNext slice="F7" points={["Newest first, filtered by what changed"]} />
    </Screen>
  );
}
