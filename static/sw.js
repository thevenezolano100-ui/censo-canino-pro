// Aumentamos la versión para forzar la limpieza de caché en los navegadores
const CACHE_NAME = 'censo-canino-v3';
const urlsToCache = [
  '/',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Lógica mejorada de navegación
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request).catch(() => {
      // Si estamos sin internet, comprobamos qué está pidiendo el usuario
      const url = new URL(event.request.url);
      
      // Si está intentando entrar a una ruta específica (como /historial o /carnet) sin internet
      if (url.pathname.includes('/historial') || url.pathname.includes('/carnet')) {
          // Retornamos un error amigable en lugar de romper la app
          return new Response('Estás sin conexión a internet. No puedes ver historiales ni carnets en modo Offline.', {
              headers: { 'Content-Type': 'text/plain; charset=utf-8' }
          });
      }
      
      // Si está pidiendo la página principal, se la damos de la caché
      return caches.match(event.request).then(response => {
        return response || caches.match('/');
      });
    })
  );
});