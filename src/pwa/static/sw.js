/* Service Worker — PWA Bitácora JA (Fase 7, Etapa B "lite": lectura offline).

Estrategia:
- Precarga del app-shell al instalar (/, /login, /offline.html, css, js, íconos).
- Estáticos (mismo origen): cache-first (rápido y offline).
- /api/* y /media/*: network-first con respaldo a la última copia en caché;
  si no hay copia y no hay red, se responde JSON 503 (la UI muestra aviso).
- Navegaciones: network-first; si no hay red se sirve /offline.html.

La PWA es SOLO LECTURA (no escribe en SQLite), así que este SW nunca encola
escrituras. No cachear respuestas de login/logout (no GET) ni rutas no-GET.
*/
// v7: iconos SVG en la ficha (reemplaza emojis) + animacion de iconos + icono dna real.
var CACHE = "pwa-ja-v7";
var PRECACHE = [
  "/",
  "/login",
  "/offline.html",
  "/manifest.json",
  "/static/style.css",
  "/static/app.js",
  "/static/favicon.svg",
  "/static/icon-192.png",
  "/static/icon-512.png"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return c.addAll(PRECACHE).catch(function () { /* parcial ok */ });
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

function guardarEnCache(request, response) {
  if (response && response.ok && request.method === "GET") {
    var clon = response.clone();
    caches.open(CACHE).then(function (c) { c.put(request, clon); });
  }
  return response;
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== location.origin) return; // solo mismo origen

  // Navegaciones (documento HTML): red primero, offline.html como respaldo.
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).then(function (r) { return guardarEnCache(req, r); })
        .catch(function () {
          return caches.match(req).then(function (hit) {
            return hit || caches.match("/offline.html");
          });
        })
    );
    return;
  }

  // API y media: red primero con copia de respaldo.
  if (url.pathname.indexOf("/api/") === 0 || url.pathname.indexOf("/media/") === 0) {
    e.respondWith(
      fetch(req).then(function (r) { return guardarEnCache(req, r); })
        .catch(function () {
          return caches.match(req).then(function (hit) {
            if (hit) return hit;
            if (url.pathname.indexOf("/api/") === 0) {
              return new Response(JSON.stringify({
                errores: { red: "Sin conexión y sin copia local." },
                _offline: true
              }), { status: 503, headers: { "Content-Type": "application/json" } });
            }
            return new Response("", { status: 503 });
          });
        })
    );
    return;
  }

  // Estáticos: cache-first.
  e.respondWith(
    caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (r) { return guardarEnCache(req, r); });
    })
  );
});
