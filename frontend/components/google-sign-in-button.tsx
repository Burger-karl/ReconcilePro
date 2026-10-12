"use client";

/**
 * "Sign in with Google" (backend DECISIONS D-37).
 *
 * Google's script draws its own button. When the person picks an account, Google calls our callback with
 * an ID token (a JWT signed by Google). We post it to the API, which checks Google's signature and returns
 * OUR login token. The browser never sees a Google password, and we never see one either.
 *
 * Hidden when NEXT_PUBLIC_GOOGLE_CLIENT_ID is not set (the API would answer 503 anyway).
 */

import Script from "next/script";
import { useTheme } from "next-themes";
import { useCallback, useEffect, useRef } from "react";

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

/** False when no Google client id is configured; pages then hide the button and its "or" line. */
export const GOOGLE_SIGN_IN_ENABLED = CLIENT_ID !== "";

// The small part of Google's script (accounts.google.com/gsi/client) we use.
type GoogleIdentity = {
  accounts: {
    id: {
      initialize: (options: { client_id: string; callback: (response: { credential: string }) => void }) => void;
      renderButton: (parent: HTMLElement, options: Record<string, string | number>) => void;
    };
  };
};

declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

export function GoogleSignInButton({
  text,
  onCredential,
}: {
  text: "signin_with" | "signup_with";
  /** Called with Google's ID token; the page decides which API endpoint gets it. */
  onCredential: (credential: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();
  // Google keeps the first callback it was given, so it must always call the LATEST onCredential.
  const latest = useRef(onCredential);
  useEffect(() => {
    latest.current = onCredential;
  }, [onCredential]);

  const render = useCallback(() => {
    if (!window.google || !container.current) return;
    window.google.accounts.id.initialize({
      client_id: CLIENT_ID,
      callback: (response) => latest.current(response.credential),
    });
    window.google.accounts.id.renderButton(container.current, {
      type: "standard",
      theme: resolvedTheme === "dark" ? "filled_black" : "outline",
      size: "large",
      text,
      width: container.current.offsetWidth || 320,
    });
  }, [resolvedTheme, text]);

  // Re-draw when the theme changes (the script may already be loaded).
  useEffect(() => {
    render();
  }, [render]);

  if (!CLIENT_ID) return null;
  return (
    <>
      {/* onReady runs on every mount, so the button is drawn again after moving between login and register. */}
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={render} />
      <div ref={container} className="flex min-h-10 w-full justify-center" />
    </>
  );
}
