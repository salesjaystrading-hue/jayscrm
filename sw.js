/* JAYS CRM PRO - app-shell service worker.
   Job: let the installed app OPEN with no signal (field staff in areas with
   patchy connectivity). It does NOT cache live CRM data - customers,
   visits, quotations etc. all still come straight from Supabase when
   online; that's handled separately by the app's own localStorage offline
   cache/queue (Store.cacheOfflineSnapshot / FieldSync), not this file.

   Strategy: network-first for same-origin shell files, falling back to
   whatever was last cached when the network is unavailable, and always
   refreshing the cache on a successful fetch so staff get the latest
   version as soon as they're back online (never stuck on a stale cached
   copy of the CRM). Cross-origin requests (Supabase, CDN libraries, fonts)
   are left completely alone - untouched pass-through to the network. */
const CACHE_NAME = 'jays-crm-shell-v1';
const SHELL_FILES = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png', './icon-maskable-512.png'];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES).catch(() => {}))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never intercept writes - those always go straight to Supabase
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // Supabase/CDN/fonts - pass through untouched

  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return res;
      })
      .catch(() => caches.match(req).then((cached) => cached || caches.match('./index.html')))
  );
});
