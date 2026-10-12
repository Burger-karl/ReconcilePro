import { ComingNext, Screen } from "@/components/app-shell/screen";

export default function CustomersPage() {
  return (
    <Screen title="Customers" description="Who owes you, and the names they pay under.">
      <ComingNext slice="F5" points={["Customer list with the amount owed", "Aliases used for name matching"]} />
    </Screen>
  );
}
