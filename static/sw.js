// Versión optimizada para almacenamiento nativo cross-origin
const CACHE_NAME = 'censo-canino-native-v11';

// Listado de recursos críticos internos y externos (CDNs) que se guardarán en el dispositivo
const assetsToCache = [
  '/',
  '/login',
  '/registro',
  '/hospitalizacion',
  '/inventario',
  '/manifest.json',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://cdn.jsdelivr.net/npm/sweetalert2@11',
  'https://unpkg.com/html5-qrcode',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// Instala el Service Worker y precacha todos los activos necesarios
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[PWA] Almacenando App Shell y CDNs en memoria local...');
        return cache.addAll(assetsToCache);
      })
      .then(() => self.skipWaiting())
  );
});

// Limpia las cachés antiguas para evitar conflictos de versiones de datos
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log('[PWA] Eliminando caché obsoleta:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Interceptor de peticiones de red inteligente
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Estrategia Cache-First para librerías fijas y CDNs (Bootstrap, Leaflet, etc.)
  if (assetsToCache.includes(event.request.url) || url.hostname.includes('cdn') || url.hostname.includes('unpkg')) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        return cachedResponse || fetch(event.request).then(networkResponse => {
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
        });
      })
    );
    return;
  }

  // Estrategia Network-First con caída a Caché para las páginas dinámicas de la app
  event.respondWith(
    fetch(event.request)
      .then(networkResponse => {
        // Si la red responde de forma correcta, actualizamos la copia de seguridad de la página
        if (networkResponse.status === 200) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseClone));
        }
        return networkResponse;
      })
      .catch(() => {
        // Si falla la red (Modo Offline), servimos la interfaz desde la memoria nativa
        return caches.match(event.request).then(cachedResponse => {
          if (cachedResponse) return cachedResponse;
          
          // Si el usuario intenta acceder a rutas médicas sin internet, mostramos una alerta amigable
          if (event.request.mode === 'navigate') {
            return caches.match('/');
          }
        });
      })
  );
});