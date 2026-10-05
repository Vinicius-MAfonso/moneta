// Bump this version whenever the caching strategy changes so old caches are purged on activate.
const CACHE_NAME = 'moneta-v2';
const STATIC_ASSETS = [
    '/static/images/icon-192.png',
    '/static/images/icon-512.png',
    '/manifest.json'
];

// Only public, non-user-specific resources may be cached.
function isCacheableRequest(request, url) {
    if (request.headers.get('HX-Request')) return false;
    return url.pathname.startsWith('/static/') || url.pathname === '/manifest.json';
}

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;
    if (!event.request.url.startsWith('http')) return;

    const url = new URL(event.request.url);

    // Never proxy cross-origin requests (CDN scripts, fonts). Inside a service worker,
    // fetch() is bound by the SW's own CSP `connect-src 'self'`, which would block them
    // and break Alpine.js/HTMX on every page controlled by this worker.
    if (url.origin !== self.location.origin) return;

    // Authenticated pages, HTMX fragments and API calls go straight to the network.
    if (!isCacheableRequest(event.request, url)) return;

    event.respondWith(
        fetch(event.request).then((response) => {
            if (!response || response.status !== 200 || response.type !== 'basic') {
                return response;
            }

            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
                cache.put(event.request, responseToCache);
            });

            return response;
        }).catch(() => {
            return caches.match(event.request);
        })
    );
});

self.addEventListener('push', function(event) {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: '/static/images/icon-192.png',
            badge: '/static/images/icon-192.png',
            vibrate: [100, 50, 100],
            data: {
                dateOfArrival: Date.now(),
                url: data.url || '/'
            }
        };
        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    if (event.notification.data.url) {
        event.waitUntil(
            clients.openWindow(event.notification.data.url)
        );
    }
});
