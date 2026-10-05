# Public Invoice (`/i/[token]`) — Page Overrides

> Rules here **override** `design-system/reconcile/MASTER.md`. Anything not listed follows Master.
> The customer sees this page, usually on a phone, with no login.

## Layout
- **Design for 375px first.** Single column, max width 640px, centred on larger screens on the `canvas` background.
- Order: business name, invoice number (mono) + StatusBadge, **amount due** (36px, tabular), due date,
  bill-to, simple line summary (subtotal, VAT 7.5%, total), **Pay with Paystack** button, bank transfer details
  with the invoice reference to quote (with a Copy button), footer "Powered by Reconcile".

## Density
- Spacious (density 3): section gaps `gap-6`, card padding `p-6` (mobile) / `p-8` (desktop).

## Components
- Pay button: full width on mobile, 48px tall, navy primary. Shows a spinner and disables while redirecting.
- Copy reference button: 44×44px touch target, `aria-label="Copy payment reference"`, toast "Reference copied".

## States
- **Paid**: green "Paid" badge, amount due ₦0.00, pay button replaced by "Thank you — payment received on <date>".
- **Part paid**: show paid so far and outstanding; Pay button charges the outstanding amount.
- **Void**: "This invoice was cancelled." No pay button.
- Unknown token: plain 404 page, no hints about other invoices.

## Theme
- Light only on this page (customers did not choose a theme; light prints and screenshots well).
