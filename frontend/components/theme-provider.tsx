"use client";

// next-themes stores the light/dark choice and puts the "dark" class on <html>.
// It must be a client component because it reads localStorage.
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider(props: React.ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props} />;
}
