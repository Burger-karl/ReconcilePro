/**
 * ReconcilePro service worker (DECISIONS D-68).
 *
 * It does ONE thing: when a page can't load because there is no network, show /offline.html instead of the
 * browser's error page. Everything else, including every API call, goes to the network untouched.
 *
 * It deliberately caches NO workspace data: devices can be shared, and signing out clears the app's memory
 * but would not clear a service-worker cache. Stale balances shown offline could also mislead an accountant.
 */

// Change the version when offline.html changes, so the old copy is replaced.
const CACHE = "reconcilepro-offline-v1";
// offline.html is self-contained (no images or stylesheets): only page loads come through here, so
// anything it linked to would need the network it doesn't have.
const OFFLINE_FILES = ["/offline.html"];

// Installing: save the offline page while we still have a network.
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(OFFLINE_FILES)));
  // Take over from an older version straight away instead of waiting for every tab to close.
  self.skipWaiting();
});

// Activating: delete caches left by older versions of this file.
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((name) => name !== CACHE).map((name) => caches.delete(name))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  // Only page loads (typing a URL, clicking a link, opening the installed app). Not calling
  // respondWith() for anything else leaves it to the browser as if this file didn't exist.
  if (event.request.mode !== "navigate") return;

  event.respondWith(
    fetch(event.request).catch(() => caches.match("/offline.html")),
  );
});
