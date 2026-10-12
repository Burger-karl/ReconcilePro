/**
 * After anything that changes invoices or money, re-ask the API for every cached list that could show it.
 * The browser never patches numbers itself: it always shows what the database says (DECISIONS D-53).
 */

import type { ScopedMutator } from "swr";

import { API } from "@/lib/api";

const AFFECTED = ["invoices", "dashboard", "audit", "reconciliation", "customers", "transactions"].map(
  (feature) => `${API}/${feature}`,
);

export function refreshAfterChange(mutate: ScopedMutator) {
  return mutate((key) => typeof key === "string" && AFFECTED.some((prefix) => key.startsWith(prefix)));
}
