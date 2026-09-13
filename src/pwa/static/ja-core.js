/* Bitácora JA — núcleo de helpers puros (ja-core.js, BLOQUE 3 fase 1).
   Funciones 100% autocontenidas extraídas del monolito app.js sin cambiar
   ninguna llamada: app.js las reexpone vía alias (window.JA.*). Cargar
   SIEMPRE antes que app.js. Las referencias internas (tabla→vacio/esc,
   chipEstado→esc, PARTO_HEADS→COW_BODY_FILL/CALF_HEAD, icon→constantes)
   usan los nombres locales dentro de este IIFE, no JA. */
(function () {
  "use strict";
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  // Toast flotante + vibración: confirmación de guardado que no depende de
  // mirar un lugar específico de la pantalla -- pensado para uso en el
  // potrero, a veces con guantes y sin poder fijar la vista en el celular.
  function mostrarToast(mensaje, tipo) {
    var cont = document.getElementById("toast-contenedor");
    if (!cont) {
      cont = document.createElement("div");
      cont.id = "toast-contenedor";
      cont.setAttribute("role", "status");
      cont.setAttribute("aria-live", "polite");
      cont.setAttribute("aria-atomic", "true");
      document.body.appendChild(cont);
    }
    var t = document.createElement("div");
    t.className = "toast toast-" + (tipo || "verde");
    t.textContent = mensaje;
    cont.appendChild(t);
    requestAnimationFrame(function () { t.classList.add("visible"); });
    setTimeout(function () {
      t.classList.remove("visible");
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 300);
    }, 2800);
  }

  function vibrarConfirmacion() {
    if (navigator.vibrate) {
      try { navigator.vibrate(60); } catch (e) { /* algunos navegadores lo bloquean sin gesto reciente */ }
    }
  }
  // Chips semáforo por estado.
  function chipEstado(v) {
    var t = String(v == null ? "" : v);
    if (/^🟢/.test(t)) return "<span class='chip verde'>" + t + "</span>";
    if (/^🟡/.test(t)) return "<span class='chip ambar'>" + t + "</span>";
    if (/^🔴/.test(t)) return "<span class='chip rojo'>" + t + "</span>";
    if (/^⚪/.test(t)) return "<span class='chip gris'>" + t + "</span>";
    return "<span class='chip gris'>" + esc(t) + "</span>";
  }
  function vacio(msg) { return "<p class='aviso'><span aria-hidden='true'>🌾</span> " + esc(msg || "Sin datos.") + "</p>"; }
  // cols: [clave, etiqueta, 'num'?, render?(valor,fila)]
  function tabla(filas, cols, vacioMsg) {
    if (!filas || !filas.length) return vacio(vacioMsg || "Sin datos.");
    var h = "<div class='tabla-scroll'><table><tr>" + cols.map(function (c) { return "<th>" + esc(c[1]) + "</th>"; }).join("") + "</tr>";
    h += filas.map(function (f) {
      return "<tr>" + cols.map(function (c) {
        var v = f[c[0]];
        var txt = c[3] ? c[3](v, f) : (c[2] === "num" ? String(v == null ? "" : v) : esc(v));
        return "<td>" + txt + "</td>";
      }).join("") + "</tr>";
    }).join("");
    return h + "</table></div>";
  }
  function kpi(numv, etiq, clase) {
    return "<div class='kpi " + (clase || "") + "'><div class='num'>" + numv + "</div><div class='etiq'>" + esc(etiq) + "</div></div>";
  }
  function erroresHtml(d) {
    if (!d || !d.errores) return "";
    var msgs = Object.keys(d.errores).map(function (k) { return esc(k) + ": " + esc(d.errores[k]); });
    return "<p class='aviso'>⚠️ Sección con error: " + msgs.join(" · ") + "</p>";
  }
  function grafico(tipo, alt) {
    return "<div class='grafico-wrap'><img src='/api/grafico/" + tipo + "' alt='" + esc(alt) +
      "' loading='lazy' data-onerror-hide='self'></div>";
  }
  function fechaCorta(v) { return v ? String(v).slice(0, 10) : ""; }
  function fmtMoneda(n) {
    var v = Number(n) || 0;
    return "$" + Math.round(v).toLocaleString("es-CO");
  }

  // SVG Icon helper (estilo Lucide: trazo 2, sin relleno)
  // Cabeza de cría / ternero (adaptación directa de la vaquita favorita: misma silueta, ojos y hocico, pero con frente redondeada sin cuernos de adulto)
  var CALF_HEAD = '<path d="M17.8 15.1a10 10 0 0 0 .9-7.1h.3c1.7 0 3-1.3 3-3C20.5 3.8 18 4.2 16.2 4.9a10 10 0 0 0-8.4 0C6 4.2 3.5 3.8 2 5c0 1.7 1.3 3 3 3h.3a10 10 0 0 0 .9 7.1M9 9.5v.5m6-.5v.5"/><path d="M15 22a4 4 0 1 0-3-6.6A4 4 0 1 0 9 22Zm-6-4h.01M15 18h.01"/>';
  // Vaca adulta (ícono nuevo, silueta de cuerpo completo con relleno) — viewBox 256, distinto del set de trazo estilo Lucide.
  var COW_BODY_FILL = '<path d="M104 192a8 8 0 0 1-8 8H80a8 8 0 0 1 0-16h16a8 8 0 0 1 8 8m72-8h-16a8 8 0 0 0 0 16h16a8 8 0 0 0 0-16m-76-48a12 12 0 1 0-12-12a12 12 0 0 0 12 12m56 0a12 12 0 1 0-12-12a12 12 0 0 0 12 12m88.39-13.88A16 16 0 0 1 232 128h-32v32a40 40 0 0 1-24 72H80a40 40 0 0 1-24-72v-32H24a16 16 0 0 1-15.69-19a56.13 56.13 0 0 1 54.91-45h1.64A55.83 55.83 0 0 1 48 24a8 8 0 0 1 16 0a40 40 0 0 0 40 40h48a40 40 0 0 0 40-40a8 8 0 0 1 16 0a55.83 55.83 0 0 1-16.86 40h1.64a56.13 56.13 0 0 1 54.91 45a15.82 15.82 0 0 1-3.3 13.12M72 152.8a40.6 40.6 0 0 1 8-.8h96a40.6 40.6 0 0 1 8 .8V104a24 24 0 0 0-24-24H96a24 24 0 0 0-24 24ZM56 112v-8a39.8 39.8 0 0 1 8-24h-.8A40.09 40.09 0 0 0 24 112Zm144 80a24 24 0 0 0-24-24H80a24 24 0 0 0 0 48h96a24 24 0 0 0 24-24m32-80a40.08 40.08 0 0 0-39.2-32h-.8a39.8 39.8 0 0 1 8 24v8Z"/>';
  // Evento de Parto / Maternidad: Vaca Madre (izquierda, silueta con relleno) + Cría (derecha, cabeza de trazo).
  // Combina dos estilos en un mismo <svg> viewBox 24x24: cada <g> fija su propio fill/stroke,
  // independiente del wrapper (que por defecto es trazo/sin relleno para el resto de íconos).
  var PARTO_HEADS = '<g transform="translate(-2.3, 2.5) scale(0.058)" fill="currentColor" stroke="none">' + COW_BODY_FILL + '</g><g transform="translate(11.5, 8.3) scale(0.48)" fill="none" stroke="currentColor" stroke-width="2.8">' + CALF_HEAD + '</g>';
  // Evento de Destete: cabeza de cría + flecha (se separa de la madre y se va a levante).
  var DESTETE_ICON = '<g transform="translate(-2, 4) scale(0.62)">' + CALF_HEAD + '</g><path d="M15 12h6M18 9l3 3-3 3"/>';
  function icon(name, size) {
    var s = size || 18;
    // "cow" usa un dibujo de cuerpo completo con relleno (viewBox/estilo propio);
    // el resto de íconos de vaca (cría, combinado de parto) sigue con trazo Lucide.
    if (name === "cow") {
      return '<svg class="svg-icon" viewBox="0 0 256 256" width="' + s + '" height="' + s + '" fill="currentColor" aria-hidden="true" focusable="false" style="display:inline-block; vertical-align:middle; margin-right:6px; position:relative; top:-1px;">' + COW_BODY_FILL + '</svg>';
    }
    var paths = {
      calf: CALF_HEAD,
      cria: CALF_HEAD,
      cowCalf: PARTO_HEADS,
      parto: PARTO_HEADS,
      destete: DESTETE_ICON,
      grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
      calendar: '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
      chartBar: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
      chartLine: '<path d="M3 3v18h18"/><path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"/>',
      dna: '<path d="M7 3C7 8 17 8 17 12C17 16 7 16 7 21M17 3C17 8 7 8 7 12C7 16 17 16 17 21M8 6.5h8M7 12h10M8 17.5h8"/>',
      grass: '<path d="M12 20c0-6 3-10 6-12m-6 12c0-8-3-12-7-14m7 14V4"/>',
      milk: '<path d="M8 2h8"/><path d="M9 2v2.789a4 4 0 0 1-.672 2.219l-.656.984A4 4 0 0 0 7 10.212V20a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-9.789a4 4 0 0 0-.672-2.219l-.656-.984A4 4 0 0 1 15 4.788V2"/><path d="M7 15a6.472 6.472 0 0 1 5 0 6.47 6.47 0 0 0 5 0"/>',
      search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
      eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
      alert: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
      rain: '<path d="M17 10a5 5 0 0 0-10 0 4 4 0 0 0 0 8h10a4 4 0 0 0 0-8zm-8 10l-1 2m4-2l-1 2m4-2l-1 2"/>',
      gauge: '<path d="M3 12a9 9 0 0 1 15 0"/><path d="M12 12L9 9"/>',
      nitrogen: '<path d="M12 2a5 5 0 0 0-5 5v5H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-2V7a5 5 0 0 0-5-5z"/>',
      camera: '<path d="M4 8a2 2 0 0 1 2-2h1.2l1-1.6A1 1 0 0 1 9 4h6a1 1 0 0 1 .8.4L16.8 6H18a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="3.5"/>',
      scale: '<path d="M12 3v18"/><path d="m19 8 3 8a5 5 0 0 1-6 0zV7"/><path d="M3 7h1a17 17 0 0 0 8-2 17 17 0 0 0 8 2h1"/><path d="m5 8 3 8a5 5 0 0 1-6 0zV7"/><path d="M7 21h10"/>', // Lucide scale (balanza romana) — perfecto para pesajes
      weight: '<circle cx="12" cy="5" r="3"/><path d="M6.5 8a2 2 0 0 0-1.905 1.46L2.1 18.5A2 2 0 0 0 4 21h16a2 2 0 0 0 1.925-2.54L19.4 9.5A2 2 0 0 0 17.48 8Z"/>',
      circleEmpty: '<circle cx="12" cy="12" r="9"/>',
      xmark: '<path d="M18 6 6 18M6 6l12 12"/>',
      // --- Iconos Lucide (ISC/MIT) re-importados: trazo fino y minimalista ---
      heartPulse: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/><path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"/>',
      heart: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
      shieldPlus: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1 1 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M9 12h6"/><path d="M12 9v6"/>',
      crown: '<path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.201a4 4 0 0 1-3.86 2.93H8.713a4 4 0 0 1-3.86-2.93L2.019 6.019a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><circle cx="12" cy="19.5" r="1.5"/>',
      cowboy: '<path d="M2 17c0-2.5 4.5-4 10-4s10 1.5 10 4M12 4c-3 0-5 2-5 5v4h10V9c0-3-2-5-5-5zM6 13a6 6 0 0 0-4 4h20a6 6 0 0 0-4-4"/>',
      tractor: '<path d="M3 11V9a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M11 11h3a2 2 0 0 1 2 2v2"/><circle cx="6.5" cy="16.5" r="3.5"/><circle cx="18" cy="17" r="2"/><path d="M10 16.5h6"/><path d="M7 11V8"/>',
      users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
      // Lucide oficiales (ISC/MIT): gestación y diagnóstico
      egg: '<path d="M12 2C8 2 4 8 4 14a8 8 0 0 0 16 0c0-6-4-12-8-12"/>',
      help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
      stethoscope: '<path d="M11 2v2"/><path d="M5 2v2"/><path d="M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1"/><path d="M8 15a6 6 0 0 0 12 0v-3"/><circle cx="20" cy="10" r="2"/>',
      // Espermatozoide (IA) — IconPark 'sperm' (Apache-2.0), dibujo clásico:
      // cabeza ovalada + flagelo con cola ondulada. Coordenadas 48 → escala .5.
      sperm: '<g transform="scale(.5)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="M18.237 24.475c1.856 1.299 2.33 2.674 3.609 3.57c1.4.98 2.947 1.5 4.169 1.014c2.307-.916 3.976-3.908 6.011-6.815c3.96-5.655 3.954-14.385.26-16.971c-3.692-2.586-11.843.433-15.802 6.088c-1.935 2.763-4.47 6.445-4.317 8.002c.129 1.311.57 2.042 1.958 3.275s2.132.45 4.112 1.837Z" clip-rule="evenodd"/><path stroke-linecap="round" d="M13.618 22.317q-5.312 5.847-1.403 8.885q3.908 3.038 9.815-2.995"/><path stroke-linecap="round" d="M12.239 31.227q-4.645 5.081-1.71 9.477c2.937 4.396 8.755 4.155 11.595.879s8.184-11.396 14.059-9.727s4.877 8.088.939 8.762"/></g>',
      // Copo de nieve (frío criogénico N₂) — Lucide ISC
      snowflake: '<path d="m10 20-1.25-2.5L6 18"/><path d="M10 4 8.75 6.5 6 6"/><path d="m14 20 1.25-2.5L18 18"/><path d="m14 4 1.25 2.5L18 6"/><path d="m17 21-3-6h-4"/><path d="m17 3-3 6 1.5 3"/><path d="M2 12h6.5L10 9"/><path d="m20 10-1.5 2 1.5 2"/><path d="M22 12h-6.5L14 15"/><path d="m4 10 1.5 2L4 14"/><path d="m7 21 3-6-1.5-3"/><path d="m7 3 3 6h4"/>',
      // Jeringa oficial Lucide (ISC) — la reemplaza el dibujo anterior
      syringe: '<path d="m18 2 4 4"/><path d="m17 7 3-3"/><path d="M19 9 8.7 19.3c-1 1-2.5 1-3.4 0l-.6-.6c-1-1-1-2.5 0-3.4L15 5"/><path d="m9 11 4 4"/><path d="m5 19-3 3"/><path d="m14 4 6 6"/>',
      // Reloj de arena (tiempo de ocupación/reposo) — Lucide ISC
      hourglass: '<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
      // Tubo de ensayo / pajuelas de inseminación artificial (dos pajuelas francesas)
      testTube: '<rect x="6" y="2" width="4" height="20" rx="1.5"/><rect x="14" y="2" width="4" height="20" rx="1.5"/><line x1="6" y1="6" x2="10" y2="6"/><line x1="14" y1="6" x2="18" y2="6"/><line x1="6" y1="11" x2="10" y2="11"/><line x1="14" y1="11" x2="18" y2="11"/><line x1="6" y1="16" x2="10" y2="16"/><line x1="14" y1="16" x2="18" y2="16"/>',
      pajuelas: '<rect x="6" y="2" width="4" height="20" rx="1.5"/><rect x="14" y="2" width="4" height="20" rx="1.5"/><line x1="6" y1="6" x2="10" y2="6"/><line x1="14" y1="6" x2="18" y2="6"/><line x1="6" y1="11" x2="10" y2="11"/><line x1="14" y1="11" x2="18" y2="11"/><line x1="6" y1="16" x2="10" y2="16"/><line x1="14" y1="16" x2="18" y2="16"/>',
      flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
      // Calavera de vaca (cráneo bovino con cuernos curvados hacia afuera y arriba)
      skull: '<path d="M8.5 8C4.5 7 2 5 2 2c1.5 2.5 4.5 4.5 7 4.5h6c2.5 0 5.5-2 7-4.5 0 3-2.5 5-6.5 6"/><path d="M8.5 8C6 9.5 6 12 8.5 14l1 7h5l1-7c2.5-2 2.5-4.5 0-6"/><circle cx="8" cy="11" r="1.2"/><circle cx="16" cy="11" r="1.2"/><path d="M12 15v3m-1.5 0h3"/>',
      cowSkull: '<path d="M8.5 8C4.5 7 2 5 2 2c1.5 2.5 4.5 4.5 7 4.5h6c2.5 0 5.5-2 7-4.5 0 3-2.5 5-6.5 6"/><path d="M8.5 8C6 9.5 6 12 8.5 14l1 7h5l1-7c2.5-2 2.5-4.5 0-6"/><circle cx="8" cy="11" r="1.2"/><circle cx="16" cy="11" r="1.2"/><path d="M12 15v3m-1.5 0h3"/>',
      corral: '<path d="M4 4v16"/><path d="M12 4v16"/><path d="M20 4v16"/><path d="M2 9h20"/><path d="M2 15h20"/><path d="m2 4 2-2 2 2"/><path d="m10 4 2-2 2 2"/><path d="m18 4 2-2 2 2"/>',
      manga: '<path d="M4 4v16"/><path d="M12 4v16"/><path d="M20 4v16"/><path d="M2 9h20"/><path d="M2 15h20"/><path d="m2 4 2-2 2 2"/><path d="m10 4 2-2 2 2"/><path d="m18 4 2-2 2 2"/>',
      // Cápsula/pastilla (tratamientos) — Lucide ISC
      pill: '<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/>',
      cross: '<path d="M4 9a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h4a1 1 0 0 1 1 1v4a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-4a1 1 0 0 1 1-1h4a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2h-4a1 1 0 0 1-1-1V4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4a1 1 0 0 1-1 1z"/>',
      // Billete (finanzas: ingresos/egresos/utilidad) — Lucide ISC "banknote"
      banknote: '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
      receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M8 7h8M8 11h8M8 15h5"/>',
      // --- Iconos Fase 7 y operacionales estilo Lucide ---
      cloud: '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
      chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
      bluetooth: '<path d="m7 7 10 10-5 5V2l5 5L7 17"/>',
      save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
      pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
      salt: '<path d="M8 2h8v4H8z"/><rect x="6" y="6" width="12" height="15" rx="3"/><path d="M10 11h4"/><path d="M10 15h4"/>',
      droplet: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 15.1 5 17 5 15a7 7 0 0 0 7 7z"/>',
      fence: '<path d="M4 3 2 5v15c0 .6.4 1 1 1h2c.6 0 1-.4 1-1V5L4 3z"/><path d="M12 3l-2 2v15c0 .6.4 1 1 1h2c.6 0 1-.4 1-1V5l-2-2z"/><path d="m20 3-2 2v15c0 .6.4 1 1 1h2c.6 0 1-.4 1-1V5l-2-2z"/><path d="M2 8h20"/><path d="M2 16h20"/>',
      walk: '<path d="M13 4a2 2 0 1 0-4 0 2 2 0 0 0 4 0Z"/><path d="m9 10 3-1 2 4 4 1"/><path d="m6 21 3-7 3-2"/><path d="m14 13 2 8"/>',
      clipboard: '<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
      download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
      refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/>',
      settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
      filePdf: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>',
      mic: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>',
      square: '<rect x="4" y="4" width="16" height="16" rx="2"/>',
      truck: '<path d="M10 17h4V5H2v12h3"/><polygon points="14 8 18 8 21 11 21 17 14 17 14 8"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
      target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
      sparkles: '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/><path d="M19 3v4"/><path d="M21 5h-4"/>',
      plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
      table: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>',
      pencil: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
      trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>',
      newspaper: '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>'
    };
    return '<svg class="svg-icon" viewBox="0 0 24 24" width="' + s + '" height="' + s + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" aria-hidden="true" focusable="false" style="display:inline-block; vertical-align:middle; margin-right:6px; position:relative; top:-1px;">' + (paths[name] || '') + '</svg>';
  }

  window.JA = { esc:esc, mostrarToast:mostrarToast, vibrarConfirmacion:vibrarConfirmacion, chipEstado:chipEstado, vacio:vacio, tabla:tabla, kpi:kpi, erroresHtml:erroresHtml, grafico:grafico, fechaCorta:fechaCorta, fmtMoneda:fmtMoneda, icon:icon };
})();
