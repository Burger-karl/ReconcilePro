import { ArrowLeftRight } from "lucide-react";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";

/** Sign-in, register and password pages: one centred card on the canvas colour. */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col bg-canvas">
      <header className="flex items-center justify-between px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <ArrowLeftRight className="size-4" aria-hidden />
          </span>
          Reconcile
        </Link>
        <ThemeToggle />
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pt-8 pb-16 sm:items-center sm:pt-0">
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}
