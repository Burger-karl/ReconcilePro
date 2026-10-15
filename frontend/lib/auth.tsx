"use client";

/**
 * Who is signed in, for the whole app.
 *
 * The login token lives in localStorage (lib/api.ts). On first load we ask the API who the token belongs
 * to (GET /auth/me). That answer, not the token's mere presence, decides whether someone is signed in:
 * the token may have expired or been revoked by a password reset (backend D-41).
 *
 * This only decides what the browser SHOWS. The real protection is the API: every endpoint checks the
 * token and the workspace on its own (backend invariant 8), so hiding a page here protects nothing.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useSWRConfig } from "swr";

import { API, ApiError, api, getToken, setToken, type Schemas } from "@/lib/api";
// Side effect only: zod settings, loaded here because this file runs in the browser on every page.
import "@/lib/zod-config";

type Me = Schemas["MeResponse"];

export type AuthState =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; me: Me }
  // The API couldn't be reached; we don't know yet, so we don't throw the token away.
  | { status: "unreachable"; message: string };

type AuthContextValue = AuthState & {
  /** Store the token from a login/register response and load the user. */
  signIn: (response: Schemas["TokenResponse"]) => Promise<void>;
  /** Forget the token here and ask the API to cancel it (and the user's other sessions, backend D-67). */
  signOut: () => void;
  retry: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const { mutate } = useSWRConfig();

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setState({ status: "signed-out" });
      return;
    }
    try {
      setState({ status: "signed-in", me: await api<Me>(`${API}/auth/me`) });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setToken(null); // expired, forged, or logged out by a password reset
        setState({ status: "signed-out" });
      } else {
        setState({ status: "unreachable", message: error instanceof Error ? error.message : "Something went wrong" });
      }
    }
  }, []);

  useEffect(() => {
    // Reading localStorage only works in the browser, so this runs after the first render.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loading the session once on mount
    void loadMe();
  }, [loadMe]);

  const signIn = useCallback(
    async (response: Schemas["TokenResponse"]) => {
      setToken(response.access_token);
      await loadMe();
    },
    [loadMe],
  );

  const signOut = useCallback(() => {
    const token = getToken();
    setToken(null);
    // Cancel the token on the server too, so a copy someone stole stops working now, not in two hours
    // (backend D-67). Sent with the token we just removed; failures are ignored: after a 401 the token is
    // already dead, and if the API is unreachable the browser is still signed out.
    if (token) {
      api(`${API}/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
    }
    // Forget every cached API answer, so the next person on this browser never sees this workspace's data.
    void mutate(() => true, undefined, { revalidate: false });
    setState({ status: "signed-out" });
  }, [mutate]);

  const value = useMemo(() => ({ ...state, signIn, signOut, retry: loadMe }), [state, signIn, signOut, loadMe]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}

/**
 * Where to go after signing in. Only paths inside this app are allowed: "/login?next=https://evil.example"
 * or "//evil.example" must not turn our login page into a redirect to someone else's site (open redirect).
 */
export function safeNextPath(next: string | null): string {
  if (next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\")) return next;
  return "/dashboard";
}
