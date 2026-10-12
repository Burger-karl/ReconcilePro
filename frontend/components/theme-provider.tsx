"use client";

// next-themes stores the light/dark choice and puts the "dark" class on <html>.
// It must be a client component because it reads localStorage.
import { usePathname } from "next/navigation";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider(props: React.ComponentProps<typeof NextThemesProvider>) {
  // The public invoice page (/i/...) is always light: customers never chose a theme, and light prints and
  // screenshots well (design-system pages/public-invoice.md). The accountant's own choice is left untouched.
  const pathname = usePathname();
  const forcedTheme = pathname.startsWith("/i/") ? "light" : undefined;
  return <NextThemesProvider {...props} forcedTheme={forcedTheme} />;
}
