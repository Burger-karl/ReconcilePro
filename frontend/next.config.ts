import type { NextConfig } from "next";

/**
 * Content-Security-Policy (DECISIONS D-67): the browser refuses anything not on these lists. The login token
 * sits in localStorage, so the aim is that even an injected script can't easily send it anywhere: fetch and
 * images may only reach this site, the API and Google's sign-in.
 *
 * No nonces: they force every page to render on each request (Next.js CSP guide). So inline scripts stay
 * allowed ('unsafe-inline', Next.js needs them), and this is a second line of defence, not the first. The
 * first is still never rendering user data as raw HTML (frontend CLAUDE.md).
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const isDev = process.env.NODE_ENV === "development";
// Google Identity Services, as listed in Google's CSP instructions for the sign-in button.
const GOOGLE = "https://accounts.google.com/gsi/";

const csp = [
  "default-src 'self'",
  // 'unsafe-eval' only in `next dev`, which uses eval for fast refresh.
  `script-src 'self' 'unsafe-inline' ${GOOGLE}client${isDev ? " 'unsafe-eval'" : ""}`,
  `style-src 'self' 'unsafe-inline' ${GOOGLE}style`,
  "img-src 'self' data: blob:",
  "font-src 'self'",
  // Where fetch() may go. ws: is the dev server's live reload.
  `connect-src 'self' ${API_URL} ${GOOGLE}${isDev ? " ws:" : ""}`,
  `frame-src ${GOOGLE}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  // Nobody may show this app inside their own page (clickjacking).
  "frame-ancestors 'none'",
  // Once the API is on https (Render), never load anything over plain http.
  ...(API_URL.startsWith("https://") ? ["upgrade-insecure-requests"] : []),
].join("; ");

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  async headers() {
    return [
      { source: "/(.*)", headers: [{ key: "Content-Security-Policy", value: csp }] },
      // The service worker (D-68): never cached by the browser, so a fixed version reaches users on their
      // next visit instead of whenever an old copy expires.
      {
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
    ];
  },
};

export default nextConfig;
