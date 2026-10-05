# Frontend notes

- Next.js App Router. Route groups: (marketing) landing page, (auth) login/register, (app) signed-in screens.
  Public invoice page lives at app/i/[token]/page.tsx and needs no login.
- UI components come from shadcn/ui (components/ui). Add new ones with `npx shadcn@latest add <name>`; don't hand-roll equivalents.
- All API calls go through lib/api.ts, which attaches the bearer token and throws typed errors. No fetch() elsewhere.
- Types come from types/api.ts (generated from the FastAPI OpenAPI schema). Regenerate after API changes; never edit by hand.
- Money arrives as integer kobo. Format only with lib/money.ts (`formatNaira(kobo)` → "₦1,234,500.00").
  Right-align money columns and use the `tabular-nums` class.
- Status colours: paid green, part_paid amber, overdue red, sent blue, draft grey — one StatusBadge component.
- Show raw bank narrations in a monospace font.
- When building from a Figma frame (Figma MCP), map it to existing shadcn components and Tailwind tokens; don't copy absolute pixel positions.
- The public invoice page must work well on a 375px phone screen.
