const CACHE_NAME = 'censo-canino-v2';
const urlsToCache = [
  '/',
  '/manifest.json'
];

// Instalación: Guardamos solo lo vital para no fallar
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Cacheando archivos base...');
        return cache.addAll(urlsToCache);
      })
      .then(() => self.skipWaiting())
  );
});

// Activación: Limpiamos memorias viejas
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

// Interceptar peticiones: Si no hay internet, mostramos la caché
self.addEventListener('fetch', event => {
  // Solo interceptamos las lecturas (GET), no los envíos de formularios (POST)
  if (event.request.method !== 'GET') return;
  
  event.respondWith(
    fetch(event.request).catch(() => {
      // Si falla la red (offline), buscamos en la caché
      return caches.match(event.request).then(response => {
        // Si encontramos el recurso, lo damos. Si no, entregamos la página principal (/)
        return response || caches.match('/');
      });
    })
  );
});