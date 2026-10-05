import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * The one place invoice status colours are defined (design-system MASTER.md §1).
 * Tinted background + darker text keeps contrast at 4.5:1 or better, and the label is always
 * shown, so colour is never the only signal.
 *
 * `status` is the DERIVED status from the API (invariant 5); the frontend never computes it.
 */
export type InvoiceStatus = "draft" | "sent" | "part_paid" | "paid" | "overdue" | "void";

const STYLES: Record<InvoiceStatus, { label: string; badge: string; dot: string }> = {
  paid: {
    label: "Paid",
    badge: "bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-400",
    dot: "bg-green-600 dark:bg-green-400",
  },
  part_paid: {
    label: "Part paid",
    badge: "bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
    dot: "bg-amber-500 dark:bg-amber-400",
  },
  overdue: {
    label: "Overdue",
    badge: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-400",
    dot: "bg-red-600 dark:bg-red-400",
  },
  sent: {
    label: "Sent",
    badge: "bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400",
    dot: "bg-blue-600 dark:bg-blue-400",
  },
  draft: {
    label: "Draft",
    badge: "bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400",
    dot: "bg-slate-400 dark:bg-slate-500",
  },
  void: {
    label: "Void",
    badge: "bg-slate-100 text-slate-500 line-through dark:bg-slate-500/15 dark:text-slate-500",
    dot: "bg-slate-400 dark:bg-slate-500",
  },
};

export function StatusBadge({ status, className }: { status: InvoiceStatus; className?: string }) {
  const style = STYLES[status];
  return (
    <Badge variant="outline" className={cn("gap-1.5 border-transparent", style.badge, className)}>
      <span aria-hidden className={cn("size-1.5 rounded-full", style.dot)} />
      {style.label}
    </Badge>
  );
}
