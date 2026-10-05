# Reconciliation Queue — Page Overrides

> Rules here **override** `design-system/reconcile/MASTER.md`. Anything not listed follows Master.
> The generator classified this page as "Checkout / Payment", which is wrong, so this file was rewritten by hand.

This is the signature screen: the accountant clears exceptions here, fast, without leaving the keyboard.

## Layout
- Full width inside the app shell (no 1200px max width). Two panes at ≥1024px:
  - **Left (40%)**: list of unresolved credits. Each row: value date, amount (right, tabular), payer name,
    first line of narration in Plex Mono, truncated. Selected row has a 2px navy left border.
  - **Right (60%)**: the selected credit in full (narration in mono, bank reference, balance), then ranked
    candidate invoices.
- Below 1024px: one pane at a time; selecting a credit pushes the detail view, with a clear Back button.

## Candidate card (one per invoice)
- Invoice number (mono), customer, outstanding amount, StatusBadge.
- **Score breakdown bar**: one horizontal bar, 100 units wide, split into three segments —
  Amount (max 50), Name (max 30), Date (max 20). Filled part solid navy, unfilled part `muted`.
  The total score is shown as a number next to it. Each segment has a text label; colour is not the only signal.
- **Reasons** as a short list in plain English, exactly as the API returns them
  (e.g. "Amount equals the amount outstanding", "Payer 'KOLA AND SONS' matches customer 'Kola & Sons' (100%)").
  Reasons never contain money (D-29); show the credit amount and the outstanding amount beside them.
- Actions: **Accept** (primary), **Allocate part…** (outline, opens dialog with amount input in ₦, converted to kobo),
  **Not this one** (ghost).

## Keyboard
- `J` / `K` next / previous credit, `1`–`3` select candidate, `A` accept selected, `R` reject, `M` manual allocate,
  `?` shows the shortcut sheet. Shortcuts are shown as `kbd` hints next to buttons.

## Density
- Compact (density 8): list rows 44px, card padding `p-4`, gap `gap-3`.

## Feedback
- After Accept: the credit row fades out (200ms, motion-safe), the next one is selected, toast "Allocated ₦90,000.00 to INV-0043 · Undo".
  Undo calls reverse (it is a real reversal with an audit row, not a client-side trick).
- Server confirms before the row disappears; on error the row stays and the error is shown in the card.
- Empty state: "All caught up — no credits need review." with a link to upload a statement.
