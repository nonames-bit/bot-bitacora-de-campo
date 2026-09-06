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
// v22: homogeneización completa de interfaz con iconos vectoriales SVG Lucide
// v23: Módulo interactivo de Gestión de Usuarios y Roles (RBAC) para Admin y Owner.
// v24: SVG manga corral, celo, muerte, pajuelas, logo Ganadería JA y fix safe-area celular.
// v25: Motor de telemetría GPS silenciosa en segundo plano y auditoría de rutas para OWNER.
// v26: Niveles de acceso (Level 1, 2, 3), IDs locales y Telegram, campo nombre ampliado y avatares temáticos.
// v27: Eliminación de parpadeos y skeletons en auto-refresco en segundo plano y carga inicial fluida.
// v28: Formateo enriquecido y tablas monospaciadas en Asistente IA y dictado por voz con copiado rápido.
// v29: Reparación de endpoint de reporte PDF general, ficha técnica animal zootécnica ejecutiva y tarjeta QR completa A4.
// v30: Visor Lightbox interactivo con zoom táctil y descarga para imágenes de ficha animal y gráficos.
// v31: Métricas de RAM/Disco en vivo para VPS, selector multi-canal de logs (Telegram, PWA, Copias) y auto-recarga de usuarios.
// v32: Logo oficial Ganadería JA, desvinculación de SG y monitor de presencia de usuarios en vivo (exclusivo OWNER).
// v33: Captura de foto opcional en eventos de campo (partos/crías, tratamientos y muertes) con compresión client-side.
// v34: Instalación directa como App en pantalla de inicio (Android, iPhone iOS y PC) con manifest enriquecido y guía táctil.
var CACHE = "pwa-ja-v34"; // subir versión al cambiar app.js/style.css/templates (cache-first)
var PRECACHE = [
  "/",
  "/login",
  "/offline.html",
  "/manifest.json",
  "/static/style.css",
  "/static/app.js",
  "/static/favicon.svg",
  "/static/favicon.png",
  "/static/logo.jpg",
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
