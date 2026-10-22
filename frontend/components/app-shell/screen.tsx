import { ThemeToggle } from "@/components/theme-toggle";

/**
 * One signed-in screen: a white top bar (breadcrumb, title, actions), the main work area on the beige
 * canvas, and an optional inspector on the right that explains whatever is selected (DECISIONS D-50).
 * CEK style (D-71): Nunito titles, white surfaces with a soft shadow. The inspector hides below 1024px.
 */
export function Screen({
  title,
  description,
  actions,
  inspector,
  flush = false,
  children,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  inspector?: React.ReactNode;
  /** Edge-to-edge body with no padding and no page scroll, for screens that lay out their own panes. */
  flush?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="relative z-10 flex flex-wrap items-center justify-between gap-3 bg-card px-4 py-4 shadow-[0_2px_15px_rgb(0_0_0/0.05)] sm:px-8">
          <div className="min-w-0">
            <p className="font-nav text-xs text-muted-foreground">Home / {title}</p>
            <h1 className="text-2xl font-black tracking-tight">{title}</h1>
            {description && <p className="text-sm text-muted-foreground">{description}</p>}
          </div>
          <div className="flex items-center gap-2">
            {actions}
            <ThemeToggle />
          </div>
        </header>
        <div className={flush ? "animate-rise flex min-h-0 flex-1" : "animate-rise flex-1 overflow-auto p-4 sm:p-8"}>{children}</div>
      </div>
      {inspector && (
        <aside className="hidden w-96 shrink-0 overflow-y-auto border-l bg-card lg:block">{inspector}</aside>
      )}
    </div>
  );
}

/** Placeholder body for screens that arrive in later slices (F2–F7). Removed as each one is built. */
export function ComingNext({ slice, points }: { slice: string; points: string[] }) {
  return (
    <div className="max-w-xl rounded-lg border border-dashed p-6">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Coming in {slice}</p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
        {points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
    </div>
  );
}
