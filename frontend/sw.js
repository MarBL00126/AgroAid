const CACHE_NAME = "agroaid-v3";

// Shell minimo para abrir la app sin conexion.
const STATIC_ASSETS = [
  "/",
  "/mapa",
  "/prevuelo",
  "/recetas",
  "/static/shared.js",
  "/static/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      // allSettled-like: una ruta que falle no debe romper la instalacion
      .then((cache) => Promise.all(
        STATIC_ASSETS.map((url) => cache.add(url).catch(() => null))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  // API y auth: siempre red; si falla, JSON de "sin conexion"
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/auth/")) {
    event.respondWith(
      fetch(request).catch(() => new Response(
        JSON.stringify({
          ok: false,
          offline: true,
          detail: "AgroAid esta sin conexion. Intenta nuevamente cuando recuperes Internet."
        }),
        {
          status: 503,
          headers: { "Content-Type": "application/json" }
        }
      ))
    );
    return;
  }

  // Paginas: network-first (para ver siempre la ultima version), cache como respaldo offline
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match("/")))
    );
    return;
  }

  // Assets estaticos: cache-first
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(request).then((response) => {
        if (response && response.status === 200 && response.type === "basic") {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    })
  );
});
