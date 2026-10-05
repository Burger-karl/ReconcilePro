# Dashboard — Page Overrides

> Rules here **override** `design-system/reconcile/MASTER.md`. Anything not listed follows Master.

## Layout (≥1024px)
1. Row of 4 KPI tiles: **Outstanding**, **Collected this month**, **Auto-match rate**, **Needs review** (count, links to the queue).
   Each tile: 12px uppercase label, 30px tabular number, one muted line of context (e.g. "across 14 invoices").
2. Two columns: **Collections by week** (bar chart, last 8 weeks, 2/3 width) and **Ageing** (stacked bar or list:
   current, 1–30, 31–60, 60+ days overdue, 1/3 width).
3. **Recent activity** from audit events (who, what, when, amount), 8 rows, "View all" to the audit page.

Below 768px: tiles become a 2×2 grid, charts stack, activity list stays.

## Density
- Compact (density 8): card padding `p-5`, grid gap `gap-4`.

## Charts
- Load the `dataviz` skill before writing chart code.
- Bars navy (light) / slate-200 (dark). Ageing uses status colours only for the overdue buckets (amber → red as age grows).
- Tooltip shows full ₦ value; y-axis uses compact labels (₦1.2M) but tooltips never round.

## States
- Loading: skeleton tiles with fixed height so the grid does not jump.
- New workspace (no data): replace charts with a 3-step checklist — add a customer, send an invoice, upload a statement.
