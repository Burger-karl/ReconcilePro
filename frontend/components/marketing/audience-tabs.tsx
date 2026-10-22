import { Briefcase, Calculator, Check, Smartphone } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/**
 * "Built for everyone who touches the money" (DECISIONS D-65), on shadcn's Tabs. Each point is a feature
 * that exists today; the comment names it.
 */
const AUDIENCES = [
  {
    value: "owner",
    label: "Business owner",
    icon: Briefcase,
    title: "See what you're owed at a glance",
    points: [
      "Outstanding, collected this month and overdue invoices on one screen", // Overview, D-48
      "Invoices emailed to customers with a link they can pay from", // D-60
      "Your bank details printed on every invoice", // D-61
    ],
  },
  {
    value: "accountant",
    label: "Accountant",
    icon: Calculator,
    title: "Review only what needs a person",
    points: [
      "Uncertain payments wait in one queue, best match first, with reasons", // Match screen
      "Accept or reject with the keyboard", // Match shortcuts
      "Every change in the audit log: who, what and when", // invariant 7
    ],
  },
  {
    value: "customer",
    label: "Your customer",
    icon: Smartphone,
    title: "Pay in a minute, from any phone",
    points: [
      "One link per invoice: no account, no app", // public invoice page /i/[token], D-58
      "Pay by card through Paystack, or by bank transfer", // D-34, D-61
      "A reference to quote, so the transfer is matched automatically", // matching: exact reference
    ],
  },
];

export function AudienceTabs() {
  return (
    <Tabs defaultValue="owner" className="w-full">
      <TabsList className="mx-auto h-auto flex-wrap justify-center">
        {AUDIENCES.map((audience) => (
          <TabsTrigger key={audience.value} value={audience.value} className="gap-2 px-4 py-2">
            <audience.icon className="size-4" aria-hidden />
            {audience.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {AUDIENCES.map((audience) => (
        // animate-rise on the panel: switching tabs fades the new content up.
        <TabsContent key={audience.value} value={audience.value} className="animate-rise mt-8">
          <div className="lift-card tone tone-sky mx-auto max-w-3xl rounded-2xl border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-semibold">{audience.title}</h3>
            <ul className="mt-5 grid gap-3">
              {audience.points.map((point) => (
                <li key={point} className="flex items-start gap-3">
                  <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
                    <Check className="size-3.5" aria-hidden />
                  </span>
                  {point}
                </li>
              ))}
            </ul>
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}
