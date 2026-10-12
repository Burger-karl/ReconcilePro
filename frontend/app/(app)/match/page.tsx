import { ComingNext, Screen } from "@/components/app-shell/screen";

export default function MatchPage() {
  return (
    <Screen
      title="Match payments"
      description="Bank credits we couldn't match on our own. Confirm or pick the invoice."
    >
      <ComingNext
        slice="F3"
        points={[
          "Unmatched credits beside open invoices",
          "Candidate scores with plain-English reasons",
          "Accept, allocate part, or not this one, from the keyboard",
        ]}
      />
    </Screen>
  );
}
