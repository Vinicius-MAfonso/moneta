const CACHE_NAME = 'moneta-v1';

self.addEventListener('install', (event) => {
    // Skip caching on install to ensure we don't break dynamic content in MVP
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Basic network-first strategy for a dynamic app
    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});
