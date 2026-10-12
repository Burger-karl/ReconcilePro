/**
 * The only place the frontend calls fetch() (frontend/CLAUDE.md).
 * - Prefixes the API base URL.
 * - Attaches the login token as `Authorization: Bearer <token>`.
 * - Turns any non-2xx response into an ApiError carrying the API's `detail` message,
 *   so screens can show it directly ("Allocation would exceed the invoice outstanding").
 */

import type { components } from "@/types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "reconcile.token";

/** Every API path starts with this (backend DECISIONS D-36). */
export const API = "/api/v1";

/** Request/response shapes generated from the backend (types/api.ts), e.g. Schemas["TokenResponse"]. */
export type Schemas = components["schemas"];

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// The token lives in localStorage for the MVP. Only available in the browser, hence the window checks.
export function getToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown };

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  // FormData (file uploads) must be sent as-is so the browser sets the multipart boundary.
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers, body });
  } catch {
    // fetch only throws when no answer arrived at all (server down, offline, CORS refused).
    // Status 0 = "no HTTP status", so screens can tell this apart from a real API error.
    throw new ApiError(0, "Can't reach the Reconcile server. Check your connection and try again.");
  }

  if (!response.ok) {
    // FastAPI errors look like {"detail": "..."}; validation errors have a list instead of a string.
    let message = response.statusText;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      // body was not JSON; keep statusText
    }
    throw new ApiError(response.status, message);
  }

  // 204 No Content has no body to parse.
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** SWR's fetcher: useSWR(`${API}/dashboard/summary`) calls api() with that path. */
export const swrFetcher = <T>(path: string) => api<T>(path);
