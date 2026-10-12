@AGENTS.md

# Frontend notes

- Next.js App Router. Route groups: (marketing) landing page, (auth) login/register, (app) signed-in screens.
  Public invoice page lives at app/i/[token]/page.tsx and needs no login.
- UI components come from shadcn/ui (components/ui). Add new ones with `npx shadcn@latest add <name>`; don't hand-roll equivalents.
- All API calls go through lib/api.ts, which attaches the bearer token and throws typed errors. No fetch() elsewhere.
- Types come from types/api.ts (generated from the FastAPI OpenAPI schema). Regenerate after API changes; never edit by hand.
  Without a running API: `cd backend && ENVIRONMENT=development python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > ../frontend/openapi.json`,
  then `cd frontend && npx openapi-typescript openapi.json -o types/api.ts` and delete openapi.json. Use them as `Schemas["TokenResponse"]` from lib/api.ts.
- Paths are `${API}/...` (API = "/api/v1" in lib/api.ts). Reads use SWR: `useSWR<Schemas["X"]>(\`${API}/...\`)`; the fetcher is set in app/(app)/layout.tsx.
  After a change, call `mutate(key)` so other screens (e.g. the Match badge) refresh.
- Forms: react-hook-form + zod + shadcn `field` (this shadcn style has no `form` component). Use components/auth/text-field.tsx for inputs.
  Mirror the API's validation rules in the zod schema; still show the API's error message (ApiError.message) above the form.
- Auth: lib/auth.tsx (`useAuth()`). The token is in localStorage; app/(app)/layout.tsx redirects signed-out visitors to /login?next=.
  This is UX only, the API is the security. Never render user data as raw HTML (a token in localStorage is readable by any injected script).
- Layout C (DECISIONS D-50): icon rail (components/app-shell/rail.tsx) + `Screen` (components/app-shell/screen.tsx) with an optional inspector.
- Env (`frontend/.env.local`, never committed): `NEXT_PUBLIC_API_URL` (default http://localhost:8000), `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (empty hides the Google button).
- Money arrives as integer kobo. Format only with lib/money.ts (`formatNaira(kobo)` → "₦1,234,500.00").
  Right-align money columns and use the `tabular-nums` class.
- Status colours: paid green, part_paid amber, overdue red, sent blue, draft grey — one StatusBadge component.
- Show raw bank narrations in a monospace font.
- When building from a Figma frame (Figma MCP), map it to existing shadcn components and Tailwind tokens; don't copy absolute pixel positions.
- The public invoice page must work well on a 375px phone screen.
