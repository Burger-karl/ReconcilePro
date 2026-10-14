"use client";

import { useEffect, useState } from "react";

/**
 * Counts from 0 up to `target` over `ms` milliseconds, for the Overview figures (DECISIONS D-62).
 *
 * Money stays exact: every in-between value is a whole number (kobo), and the last frame is `target` itself,
 * so the figure that stays on screen is precisely the API's number (invariant 1).
 */
export function useCountUp(target: number, ms = 800): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    // No count when nobody should see it move: reduced motion is asked for, or the tab is in the background
    // (browsers don't run animation frames there, so the count would sit at 0). Show the final figure instead.
    // setTimeout, not a direct setValue: React's rules say an effect shouldn't set state synchronously.
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || document.visibilityState === "hidden") {
      const timer = setTimeout(() => setValue(target), 0);
      return () => clearTimeout(timer);
    }

    let frame = 0;
    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min((now - start) / ms, 1);
      const eased = 1 - (1 - progress) ** 3; // ease-out: fast at first, settling gently on the number
      setValue(progress === 1 ? target : Math.round(target * eased));
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame); // stop if the figure changes or the screen closes mid-count
  }, [target, ms]);

  return value;
}
