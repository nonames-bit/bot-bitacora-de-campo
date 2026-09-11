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
// v37: Sección interactiva de últimos eventos en tablero y solución de colores en pirámide de edades para Sol de Campo.
// v38: Fix de clics rotos por el CSP (script-src 'self') en árbol genealógico, crías, feed de eventos y exportar CSV -- de onclick inline a delegación de eventos.
// v39: Fix navegación de ficha en página standalone /ficha/<tag> (apuntaba al contenedor #vista inexistente en vez de #ficha).
// v40: Botón de ayuda movido al header con ?, navegación directa a ficha desde eventos/crías con scroll suave, icono SVG para crías y retiro de columna Acción.
// v41: Quita los 2 botones "Ver Pedigree 3G" / "Abrir Árbol Genealógico" duplicados en la tarjeta de Identificación -- la pestaña "Genealogía (3G)" ya es el único acceso.
// v42: Icono de cría adaptado fielmente de la vaquita favorita con frente redondeada tierna sin cuernos e icono de parto con Vaca Madre + Cría juntas en estilo idéntico.
// v43: Selector de temas en /ficha/<tag>, botones de Asistente IA (Chat) y Ayuda en header de ficha, e icono SVG Lucide de vaca sin emojis.
// v44: Foto de recibo/planilla quincenal de leche en captura rápida, galería de recibos en vista Leche con zoom táctil.
// v45: Digitalización inteligente de recibos/planillas de leche con IA Multimodal (Gemini Vision) y desglose interactivo.
// v46: Módulo de Finanzas (fase 1) -- libro de ingresos/egresos, resumen de utilidad por año y captura de gastos con foto de factura.
// v47: Eventos de ventas en tablero con vinculación bidireccional Madre ⇄ Cría, iconos dinámicos y navegación a fichas.
// v49: Modal de detalle por movimiento en Finanzas (fecha/categoría/monto/animal/notas y foto de factura ampliable), y la foto de gasto en Captura ahora queda enlazada al registro de finanzas.
// v50: Sincronización de eventos de venta con trazabilidad de crías.
// v51: Barra inferior de 5 botones con bottom sheet categorizado para módulos en móviles (cero scroll horizontal) y sincronización con RBAC.
// v52: Aislamiento estricto de #nav-principal vs #ficha-tabs mini para evitar superposición y bloqueo de navegación en móviles al abrir ficha animal.
// v54: La foto del recibo de leche se guarda al analizarla con IA (no se pierde si no llegas a "Guardar Quincena"); extrae precio/litro y valor pagado del recibo y crea el ingreso en Finanzas (Venta de leche) al guardar la quincena.
// v55: Información explícita de bajas por venta y muerte en ficha animal (banners destacados con fecha exacta, comprador/precio, causa/diagnóstico, vínculos de venta conjunta madre-cría y tabla consolidada de movimientos).
// v56: Estructura del hato (SG: cría/levante/novilla/vaca parida-seca/reproductor con % y UGG estimado) en Inventario, e Indicadores reproductivos del hato (IEP, días abiertos, servicios/concepción, tasa de concepción, edad 1er parto) en Reproducción.
// v57: Integración del Hierro / Marca de fuego de cada animal en ficha técnica (chip de encabezado, tarjeta de identificación, árbol genealógico, reporte PDF y bot).
// v58: Estructura del hato en Inventario ahora usa una barra única apilada por colores (reemplaza las 8 barras de progreso repetidas); Distribución por raza en Genética ahora es un donut real en vez de barras HTML.
// v59: Crear Animal y Editar Animal (identidad, genealogía, potrero, hierro, chip/RFID, color, notas) directamente en la PWA -- primer paso para dejar de depender de Software Ganadero para el alta/edición del hato. Solo ADMIN/OWNER.
// v60: Finanzas Fase 2 -- indicadores de rentabilidad (margen de utilidad, costo por litro de leche, costo por cabeza, costo estimado por kg de carne) y gráfico de flujo de caja mensual; digitalización con IA de facturas/recibos generales de gasto o ingreso (categoría, concepto, monto, proveedor), con la foto guardada de inmediato como evidencia igual que el recibo de leche.
// v61: Pronóstico del clima (Open-Meteo, 7 días) en Pasturas -- ya estaba en el Despacho Matutino del bot, ahora también visible en la PWA con recomendaciones prácticas (fumigar, heno, mover ganado).
// v62: Visor de fotos con arrastre interactivo (manito / pan), zoom suave multi-nivel (+/-, rueda, doble toque/clic) y soporte táctil fluido para inspeccionar detalles de recibos, hierros y ganado.
// v63: Ícono de vaca adulta actualizado a silueta de cuerpo completo con relleno (el de cría/ternero se mantiene sin cambios).
// v64: Ícono combinado de Parto (madre + cría) actualizado para usar la nueva silueta de vaca junto a la cabeza de cría, en vez de las dos cabezas de trazo anteriores.
// v65: Fix Diagnóstico General en Sistema -- las etiquetas <b>/<i> del texto salían literales en vez de renderizarse en negrita/cursiva.
// v66: Recibos y Planillas de Quincena (Leche) ahora es una sección colapsada al final de la vista (antes salía primero); fix del filtro que mezclaba facturas de Finanzas ahí.
// v67: Editar y eliminar movimientos manuales de Finanzas (ingresos/gastos), exclusivo para OWNER, desde "Movimientos recientes".
// v69: Traslado masivo por potrero (mover TODOS los animales activos de un potrero a otro sin escribir cada arete) en Captura; autocompletado de potreros (solo reales) precargado desde el inicio en todos los campos; fix de fondo -- Traslado ahora sí actualiza el potrero actual del animal (antes solo quedaba como nota histórica).
// v70: Mapa Satelital Interactivo con Leaflet, polígonos de potreros, vigor NDVI/SAR y ubicación en vivo de operarios; Indicadores económicos de costo y margen unitario para leche y carne; Soporte de Notificaciones Web Push nativas en celular.
// v71: Botón "Ver simple/técnico" en Pasturas -- Modo Simple (por defecto) muestra SPI y monitoreo satelital como semáforo en palabras (Excelente/Regular/Bajo), sin jerga (NDVI, RVI, SAR, kg/ha); Modo Técnico mantiene el detalle completo de siempre.
// v72: Nuevo evento "Destete" en Captura (separar la cría, pesarla, moverla a levante y opcionalmente secar/mover a la madre -- equivalente a "Secados/Destetos" de SG); Parto ahora permite fijar el potrero de la cría y/o de la madre en el momento del nacimiento.
// v73: Vaquita decorativa pastando en el header (SVG inline COW_HEAD + pasto, solo CSS @keyframes, respeta reduced-motion y queda estática en Sol de Campo).
// v74: Ícono de Destete cambiado a cabeza de cría + flecha (antes reusaba el mismo ícono que "Cría", sin distinguirse a simple vista en el botón de Captura ni en el feed de eventos).
// v75: Unificación de Mapa Satelital y Rutas GPS en un solo módulo para ADMIN y OWNER (bloqueado para TRABAJADOR); dock de chat flotante/expandible con dictado de voz estilo WhatsApp; depuración de terminología zootécnica.
// v77: Unificación definitiva de Mapa Satelital y Rutas GPS (ADMIN y OWNER), dock de chat WhatsApp con notas de voz y depuración integral de terminología.
// v78: "Distribución por potrero" del Tablero sube justo después de "Evolución del rebaño" (antes quedaba al final, después del feed de eventos); se quita el gráfico de torta duplicado con Inventario.
// v81: Vaquita realista comiendo pasto en el header (vaca_comiendo.png con animación de pastar y caminar).
// v82: Tablero visual interactivo de subastas ganaderas con comparativa de plazas, barras de precios relativos a Granada y curvas de tendencia semanal.
// v83: Vaquita animada en GIF convertida de vaca.mp4 con ciclos naturales de pastoreo, masticado y cola en el header.
var CACHE = "pwa-ja-v83"; // subir versión al cambiar app.js/style.css/templates (cache-first)
var PRECACHE = [
  "/",
  "/login",
  "/offline.html",
  "/manifest.json",
  "/static/style.css",
  "/static/app.js",
  "/static/vaca_comiendo.gif",
  "/static/vaca_comiendo.png",
  "/static/leaflet/leaflet.css",
  "/static/leaflet/leaflet.js",
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

// -----------------------------------------------------------------------------
// Web Push Notifications
// -----------------------------------------------------------------------------
self.addEventListener("push", function (event) {
  var data = {
    titulo: "Bitácora JA",
    cuerpo: "Aviso importante de campo o sanidad",
    icono: "/static/icon-192.png",
    tag: "bitacora-notif",
    url: "/"
  };
  if (event.data) {
    try {
      var parsed = event.data.json();
      data = Object.assign(data, parsed);
    } catch (e) {
      data.cuerpo = event.data.text();
    }
  }
  var options = {
    body: data.cuerpo || data.body || "",
    icon: data.icono || data.icon || "/static/icon-192.png",
    badge: "/static/icon-192.png",
    tag: data.tag || "bitacora-push",
    renotify: true,
    data: { url: data.url || "/" }
  };
  event.waitUntil(
    self.registration.showNotification(data.titulo || data.title || "Bitácora JA", options)
  );
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var targetUrl = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clientList) {
      for (var i = 0; i < clientList.length; i++) {
        var client = clientList[i];
        if (client.url && client.url.indexOf(targetUrl) !== -1 && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

