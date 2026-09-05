/* Service Worker — PWA Bitácora JA (Fase 7, Etapa B "lite": lectura offline
   + Etapa D+: escritura de eventos de campo con cola offline en IndexedDB).

Estrategia:
- Precarga del app-shell al instalar (/, /login, /offline.html, css, js, íconos).
- Estáticos (mismo origen): cache-first (rápido y offline).
- /api/* y /media/*: network-first con respaldo a la última copia en caché;
  si no hay copia y no hay red, se responde JSON 503 (la UI muestra aviso).
- Navegaciones: network-first; si no hay red se sirve /offline.html.

Este SW en sí sigue sin interceptar escrituras (no cachea respuestas de
login/logout ni rutas no-GET): la cola offline de eventos de campo (Manga,
GPS, etc.) la maneja app.js directo contra IndexedDB, no este archivo.
*/
// v21: rate limit en /login (el PIN son 4 digitos en texto plano en
// users.json -- sin limite de intentos era fuerza-bruteable en segundos),
// fix perdida de datos en la cola offline (antes se borraba TODA la cola
// con un solo HTTP 200 aunque un evento individual fallara), variables de
// color --gris que faltaban en el tema "sun".
// OJO: nunca bajar este numero -- un cliente que ya haya tenido una cache
// con ese mismo nombre la trataria como "al dia" y se quedaria con el
// HTML/JS/CSS viejo indefinidamente.
var CACHE = "pwa-ja-v21"; // subir versión al cambiar app.js/style.css/templates (cache-first)
var PRECACHE = [
  "/",
  "/login",
  "/offline.html",
  "/manifest.json",
  "/static/style.css",
  "/static/app.js",
  "/static/favicon.svg",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/fonts/geist-sans-latin-400-normal.woff2",
  "/static/fonts/geist-sans-latin-500-normal.woff2",
  "/static/fonts/geist-sans-latin-600-normal.woff2",
  "/static/fonts/geist-sans-latin-700-normal.woff2"
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
