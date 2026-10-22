import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Nunito, Roboto, Ubuntu } from "next/font/google";

import { ServiceWorker } from "@/components/service-worker";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

// next/font downloads the fonts at build time and serves them from our own domain,
// so there is no request to Google from the browser and no layout shift while they load.
// The CEK Alpha pairing (DECISIONS D-71): Roboto for text, Nunito for headings, Ubuntu for navigation and buttons.
const roboto = Roboto({
  variable: "--font-roboto",
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
});
const nunito = Nunito({
  variable: "--font-nunito",
  subsets: ["latin"],
  weight: ["600", "700", "800", "900"],
});
const ubuntu = Ubuntu({
  variable: "--font-ubuntu",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

// Mono is for raw bank narrations, references and invoice numbers (design-system MASTER.md §2).
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "ReconcilePro",
  description: "Match bank credits and Paystack payments to invoices automatically.",
  // iPhones ignore most of app/manifest.ts; these tags make "Add to Home Screen" open its own window (D-68).
  appleWebApp: { capable: true, title: "ReconcilePro", statusBarStyle: "default" },
};

// Colour of the phone's status bar and the installed app's title bar: the page background, light or dark.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0d0d" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: next-themes adds the "dark" class before React hydrates.
    <html
      lang="en"
      className={`${roboto.variable} ${nunito.variable} ${ubuntu.variable} ${plexMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="flex min-h-full flex-col">
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
          <TooltipProvider>
            {/* Who is signed in, shared by the auth pages and the app (lib/auth.tsx). */}
            <AuthProvider>{children}</AuthProvider>
          </TooltipProvider>
          <Toaster />
          <ServiceWorker />
        </ThemeProvider>
      </body>
    </html>
  );
}
