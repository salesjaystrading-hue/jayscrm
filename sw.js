/* JAYS CRM PRO — service worker
   Scope is intentionally narrow: this app's whole value is LIVE Supabase
   data, so nothing here ever caches API calls or CDN scripts. It only
   caches the app shell (this HTML file + icons) so:
     1) Chrome/Android's install-prompt criteria are met (a fetch handler
        is required), and
     2) if someone opens the app with genuinely no network, they see the
        last-loaded shell instead of a browser error page.
   Every navigation still tries the network FIRST and only falls back to
   the cached shell on failure - so anyone online always gets the live,
   current file, never a stale cached one. */
const CACHE = 'jays-crm-shell-v1';
const SHELL = ['./index.html', './manifest.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', e=>{
  e.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', e=>{
  const req = e.request;
  const url = new URL(req.url);

  // Only ever touch same-origin GET requests for the shell files above.
  // Everything else (Supabase API/auth, jsPDF/XLSX CDN scripts, any POST)
  // passes straight through to the network, untouched.
  if(req.method !== 'GET' || url.origin !== self.location.origin){
    return; // no e.respondWith() => default network behavior
  }

  e.respondWith(
    fetch(req).then(res=>{
      // Keep the cached shell fresh whenever we're online.
      const copy = res.clone();
      caches.open(CACHE).then(c=>c.put(req, copy));
      return res;
    }).catch(()=>caches.match(req).then(cached=>cached || caches.match('./index.html')))
  );
});
