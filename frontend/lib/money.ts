/**
 * Money helpers. The API sends every amount as an integer number of kobo (100 kobo = ₦1).
 * This is the ONLY place kobo becomes naira text (CLAUDE.md invariant 1).
 *
 * We never divide by 100 and print the float: 0.1 + 0.2 style errors would show up in totals.
 * Instead we split the integer into whole naira and leftover kobo with integer maths.
 */

const nairaGrouping = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 });

/** formatNaira(123450000) → "₦1,234,500.00"; formatNaira(-5050) → "-₦50.50" */
export function formatNaira(kobo: number): string {
  if (!Number.isSafeInteger(kobo)) {
    throw new Error(`formatNaira expects an integer number of kobo, got ${kobo}`);
  }
  const sign = kobo < 0 ? "-" : "";
  const abs = Math.abs(kobo);
  const naira = Math.floor(abs / 100); // whole naira
  const rest = abs % 100; // leftover kobo, 0–99
  return `${sign}₦${nairaGrouping.format(naira)}.${String(rest).padStart(2, "0")}`;
}

const nairaCompact = new Intl.NumberFormat("en-NG", { notation: "compact", maximumFractionDigits: 1 });

/**
 * compactNaira(120_000_000) → "₦1.2M". ONLY for chart axis ticks, where space is tight and the exact
 * value is one hover away. Anywhere a reader needs the amount (tiles, tables, tooltips) use formatNaira:
 * the design system forbids rounded money (MASTER.md §8).
 */
export function compactNaira(kobo: number): string {
  if (!Number.isSafeInteger(kobo)) {
    throw new Error(`compactNaira expects an integer number of kobo, got ${kobo}`);
  }
  // Dividing is fine here only because the result is deliberately rounded for display.
  return `₦${nairaCompact.format(kobo / 100)}`;
}

/**
 * Parse what a user typed in a ₦ field ("90,000", "90000.5", "₦1,250.75") into kobo.
 * Works on the text, not on a float, so "0.29" becomes exactly 29 kobo.
 * Returns null when the input is not a valid amount with at most 2 decimal places.
 */
export function parseNairaToKobo(input: string): number | null {
  const cleaned = input.replace(/[₦,\s]/g, "");
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(cleaned);
  if (!match) return null;
  const naira = Number(match[1]);
  const kobo = Number((match[2] ?? "").padEnd(2, "0"));
  const total = naira * 100 + kobo;
  return Number.isSafeInteger(total) ? total : null;
}
