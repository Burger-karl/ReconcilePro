import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * The ReconcilePro logo (DECISIONS D-65): the owner's "R" mark (public/brand/logo-mark.png, cut from the
 * uploaded logo) plus the wordmark as live text (logotypes are exempt from WCAG contrast rules; the link
 * still has an accessible name). Text, not the PNG wordmark: the PNG's navy letters would
 * disappear on dark backgrounds, while text follows the theme. "Pro" keeps the logo's green.
 *
 * `onDark`: for navy surfaces (app rail, auth brand panel, dark cards). The mark then sits on a white tile,
 * because its navy "R" would blend into the background.
 */
export function Logo({
  href = "/",
  onDark = false,
  wordmark = true,
  size = 32,
  className,
}: {
  href?: string;
  onDark?: boolean;
  wordmark?: boolean;
  /** Mark height in px. */
  size?: number;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={cn("group/logo flex items-center gap-2 font-semibold tracking-tight", className)}
      aria-label="ReconcilePro home"
    >
      <span
        className={cn(
          "flex shrink-0 items-center justify-center transition-transform duration-300 group-hover/logo:-rotate-6 group-hover/logo:scale-105",
          onDark && "rounded-lg bg-white p-1 shadow-md shadow-black/20",
        )}
      >
        {/* priority: the logo is above the fold on every page, so load it first. */}
        {/* On a white tile the image is 8px smaller, so the tile (4px padding each side) stays `size` tall. */}
        <Image src="/brand/logo-mark.png" alt="" width={onDark ? size - 8 : size} height={onDark ? size - 8 : size} priority />
      </span>
      {wordmark && (
        <span className={cn("text-lg", onDark ? "text-white" : "text-[#0b2a6f] dark:text-white")}>
          Reconcile
          <span className="bg-linear-to-r from-emerald-500 to-green-600 bg-clip-text text-transparent dark:from-emerald-300 dark:to-green-400">
            Pro
          </span>
        </span>
      )}
    </Link>
  );
}

/** Just the mark, not a link: for decoration inside cards (the CTA card, the "With ReconcilePro" card). */
export function LogoMark({ size = 32, onDark = false }: { size?: number; onDark?: boolean }) {
  return (
    <span className={cn("inline-flex shrink-0", onDark && "rounded-xl bg-white p-1.5 shadow-md shadow-black/20")}>
      <Image src="/brand/logo-mark.png" alt="" width={size} height={size} />
    </span>
  );
}
