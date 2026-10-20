import type { MetadataRoute } from "next";

/**
 * Web app manifest (DECISIONS D-68): what the phone or desktop needs to install ReconcilePro as an app,
 * with its own icon and window. Next.js serves this at /manifest.webmanifest and links it from every page.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ReconcilePro",
    short_name: "ReconcilePro",
    description: "Match bank credits and Paystack payments to invoices automatically.",
    // Open straight into the app; a signed-out visitor is sent on to /login by app/(app)/layout.tsx.
    start_url: "/dashboard",
    scope: "/",
    // Its own window, without the browser's address bar.
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#0f766e", // --primary (teal-700) in globals.css
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // Padded on a white tile, so Android can crop it to a circle without cutting the logo off.
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
