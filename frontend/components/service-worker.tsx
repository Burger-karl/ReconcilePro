"use client";

import { useEffect } from "react";

/**
 * Registers public/sw.js, which shows an offline page when there is no network (DECISIONS D-68).
 *
 * Production builds only: in `next dev` a service worker can serve an old page after a code change and make
 * fast refresh look broken. Renders nothing.
 */
export function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    // updateViaCache "none": always ask the server for a newer sw.js, never the browser's HTTP cache.
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
      // Without it the app still works, it just shows the browser's own offline page.
    });
  }, []);
  return null;
}
