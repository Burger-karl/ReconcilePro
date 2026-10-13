/**
 * Plain-English text for audit events (used by Overview's "Recent activity" and the Audit log).
 * Event data was written by the backend, but parts of it came from users (customer names, file names,
 * reasons), so it is only ever rendered as text by React, never as HTML.
 */

import type { Schemas } from "@/lib/api";

type AuditEvent = Schemas["AuditEventRead"];

export type DescribedEvent = {
  text: string;
  /** The money this event moved or concerned, if any (integer kobo). */
  amountKobo: number | null;
};

const str = (value: unknown): string | null => (typeof value === "string" && value.trim() ? value : null);
const kobo = (value: unknown): number | null => (Number.isSafeInteger(value) ? (value as number) : null);

export function describeEvent(event: AuditEvent): DescribedEvent {
  const data = event.data ?? {};
  const invoice = str(data.number) ?? str(data.invoice_number) ?? "an invoice";

  switch (event.action) {
    case "allocation.created":
      return {
        text: data.method === "auto" ? `Payment matched automatically to ${invoice}` : `Payment matched to ${invoice}`,
        amountKobo: kobo(data.amount_kobo),
      };
    case "allocation.reversed":
      return { text: "Payment match reversed", amountKobo: kobo(data.amount_kobo) };
    case "paystack.payment_received":
      return { text: `Paystack payment received for ${invoice}`, amountKobo: kobo(data.amount_kobo) };
    case "invoice.created":
      return { text: `Invoice ${invoice} created`, amountKobo: kobo(data.total_kobo) };
    case "invoice.sent":
      return {
        text: str(data.emailed_to) ? `Invoice ${invoice} sent and emailed to ${data.emailed_to}` : `Invoice ${invoice} sent`,
        amountKobo: kobo(data.total_kobo),
      };
    case "invoice.emailed":
      return { text: `Invoice ${invoice} emailed to ${str(data.emailed_to) ?? "the customer"}`, amountKobo: null };
    case "invoice.updated":
      return { text: "Draft invoice edited", amountKobo: null };
    case "invoice.voided":
      return { text: `Invoice ${invoice} voided`, amountKobo: null };
    case "customer.created":
      return { text: `Customer ${str(data.name) ?? ""} added`.replace("  ", " "), amountKobo: null };
    case "customer.updated":
      return { text: "Customer details changed", amountKobo: null };
    case "statement.imported": {
      const added = kobo(data.added);
      return {
        text: added === null ? "Bank statement imported" : `Bank statement imported: ${added} new line${added === 1 ? "" : "s"}`,
        amountKobo: null,
      };
    }
    case "match.rejected":
      return { text: "Suggested match rejected", amountKobo: null };
    case "user.google_linked":
      return { text: "Google sign-in linked", amountKobo: null };
    case "user.password_reset_requested":
      return { text: "Password reset requested", amountKobo: null };
    case "user.password_reset":
      return { text: "Password changed", amountKobo: null };
    default:
      // A new backend action shows up readably instead of breaking the list.
      return { text: event.action.replace(/[._]/g, " "), amountKobo: null };
  }
}

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

/** "5 minutes ago", "yesterday". Older than a week shows the date. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  if (Math.abs(seconds) < 60) return "just now";
  if (Math.abs(seconds) >= 7 * 86_400) return formatDateTime(iso);
  for (const [unit, size] of STEPS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

/** "12 Oct 2026, 09:14" in the browser's time zone. */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-NG", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

// --- details and links (Audit log page) ---------------------------------------------------------------

/** "invoice_number" → "Invoice number". Keys come from the backend's record() calls. */
const humanise = (key: string) => {
  const words = key.replace(/_kobo$/, "").replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
};

/** One value as text: kobo fields as ₦ (they end in _kobo, invariant 1), null as "none", objects as JSON. */
function valueText(key: string, value: unknown, formatMoney: (kobo: number) => string): string {
  if (value === null || value === undefined || value === "") return "none";
  if (key.endsWith("_kobo") && Number.isSafeInteger(value)) return formatMoney(value as number);
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export type DetailRow = { label: string; value: string };

/**
 * Everything recorded with the event, as label/value rows. Ids are left out (the links cover them).
 * Edits ({"changes": {"subtotal_kobo": {"from": 1500000, "to": 2000000}}}) become "Subtotal: ₦15,000.00 → ₦20,000.00".
 */
export function eventDetails(event: AuditEvent, formatMoney: (kobo: number) => string): DetailRow[] {
  const rows: DetailRow[] = [];
  for (const [key, value] of Object.entries(event.data ?? {})) {
    if (key === "changes" && value && typeof value === "object") {
      for (const [field, change] of Object.entries(value as Record<string, { from: unknown; to: unknown }>)) {
        rows.push({
          label: humanise(field),
          value: `${valueText(field, change?.from, formatMoney)} → ${valueText(field, change?.to, formatMoney)}`,
        });
      }
    } else if (!key.endsWith("_id")) {
      rows.push({ label: humanise(key), value: valueText(key, value, formatMoney) });
    }
  }
  return rows;
}

/** Where to look at the thing the event is about. Only links to screens that exist. */
export function eventLinks(event: AuditEvent): { href: string; label: string }[] {
  const data = event.data ?? {};
  const id = (value: unknown) => (typeof value === "string" && /^[0-9a-f-]{36}$/i.test(value) ? value : null);
  switch (event.entity_type) {
    case "invoice":
      return [{ href: `/invoices/${event.entity_id}`, label: "Open invoice" }];
    case "customer":
      return [{ href: `/customers/${event.entity_id}`, label: "Open customer" }];
    case "transaction":
      return [{ href: `/transactions/${event.entity_id}`, label: "Open bank line" }];
    case "allocation": {
      const links = [];
      if (id(data.invoice_id)) links.push({ href: `/invoices/${data.invoice_id}`, label: "Open invoice" });
      if (id(data.transaction_id)) links.push({ href: `/transactions/${data.transaction_id}`, label: "Open bank line" });
      return links;
    }
    case "statement":
      return [{ href: "/statements", label: "Open statements" }];
    default:
      return [];
  }
}
