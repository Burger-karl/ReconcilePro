/**
 * One signed-in screen in layout C: a title bar, the main work area, and an optional inspector on the
 * right that explains whatever is selected (DECISIONS D-50). The inspector hides below 1024px.
 * The title bar has a light teal wash and the body fades up when the screen opens (D-62).
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
        <header className="flex flex-wrap items-center justify-between gap-3 border-b bg-linear-to-r from-brand-soft to-background px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            {description && <p className="text-sm text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
        <div className={flush ? "animate-rise flex min-h-0 flex-1" : "animate-rise flex-1 overflow-auto p-4 sm:p-6"}>{children}</div>
      </div>
      {inspector && (
        <aside className="hidden w-96 shrink-0 overflow-y-auto border-l bg-canvas lg:block">{inspector}</aside>
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
