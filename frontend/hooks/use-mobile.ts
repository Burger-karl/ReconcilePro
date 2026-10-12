import { useSyncExternalStore } from "react";

const MOBILE_BREAKPOINT = 768;
const QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`;

// Rewritten from shadcn's version (which set state inside an effect, flagged by the React lint rules).
// useSyncExternalStore is React's own way to read a value that lives outside React, like screen width.
function subscribe(onChange: () => void) {
  const query = window.matchMedia(QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** True below 768px. On the server there is no screen, so it reports desktop until the browser takes over. */
export function useIsMobile() {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}
