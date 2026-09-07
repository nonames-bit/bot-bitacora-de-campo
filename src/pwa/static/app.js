/* Dashboard PWA Bitácora JA — JS vainilla (sin framework).
   WS-3: KPIs, chips semáforo, skeleton, banner offline, polling 60s,
   modo oscuro, errores visibles por sección y ficha con pestañas. */
(function () {
  "use strict";
  var vista = document.getElementById("vista");
  var actual = "tablero";
  function q(s) { return document.querySelector(s); }
  function qa(s, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  // Chips semáforo por estado.
  function chipEstado(v) {
    var t = String(v == null ? "" : v);
    if (/^🟢/.test(t)) return "<span class='chip verde'>" + t + "</span>";
    if (/^🟡/.test(t)) return "<span class='chip ambar'>" + t + "</span>";
    if (/^🔴/.test(t)) return "<span class='chip rojo'>" + t + "</span>";
    if (/^⚪/.test(t)) return "<span class='chip gris'>" + t + "</span>";
    return "<span class='chip gris'>" + esc(t) + "</span>";
  }
  function vacio(msg) { return "<p class='aviso'>🌾 " + esc(msg || "Sin datos.") + "</p>"; }
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
  // Cabeza de vaca real (Lucide Lab 'cow-head', ISC) — frontal, con orejas y morro.
  var COW_HEAD = '<path d="M17.8 15.1a10 10 0 0 0 .9-7.1h.3c1.7 0 3-1.3 3-3V3h-3c-1.3 0-2.4.8-2.8 1.9a10 10 0 0 0-8.4 0C7.4 3.8 6.3 3 5 3H2v2c0 1.7 1.3 3 3 3h.3a10 10 0 0 0 .9 7.1M9 9.5v.5m6-.5v.5"/><path d="M15 22a4 4 0 1 0-3-6.6A4 4 0 1 0 9 22Zm-6-4h.01M15 18h.01"/>';
  // Cabeza de cría / ternero (adaptación directa de la vaquita favorita: misma silueta, ojos y hocico, pero con frente redondeada sin cuernos de adulto)
  var CALF_HEAD = '<path d="M17.8 15.1a10 10 0 0 0 .9-7.1h.3c1.7 0 3-1.3 3-3C20.5 3.8 18 4.2 16.2 4.9a10 10 0 0 0-8.4 0C6 4.2 3.5 3.8 2 5c0 1.7 1.3 3 3 3h.3a10 10 0 0 0 .9 7.1M9 9.5v.5m6-.5v.5"/><path d="M15 22a4 4 0 1 0-3-6.6A4 4 0 1 0 9 22Zm-6-4h.01M15 18h.01"/>';
  // Evento de Parto / Maternidad: Vaca Madre (izquierda) + Cría (derecha), ambas con el estilo idéntico de la vaquita favorita
  var PARTO_HEADS = '<g transform="translate(-1.5, 1) scale(0.68)" stroke-width="2.3">' + COW_HEAD + '</g><g transform="translate(10.5, 7.5) scale(0.53)" stroke-width="2.6">' + CALF_HEAD + '</g>';
  function icon(name, size) {
    var paths = {
      cow: COW_HEAD,
      calf: CALF_HEAD,
      cria: CALF_HEAD,
      cowCalf: PARTO_HEADS,
      parto: PARTO_HEADS,
      grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
      calendar: '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
      chartBar: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
      chartLine: '<path d="M3 3v18h18"/><path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"/>',
      dna: '<path d="M7 3C7 8 17 8 17 12C17 16 7 16 7 21M17 3C17 8 7 8 7 12C7 16 17 16 17 21M8 6.5h8M7 12h10M8 17.5h8"/>',
      grass: '<path d="M12 20c0-6 3-10 6-12m-6 12c0-8-3-12-7-14m7 14V4"/>',
      milk: '<path d="M8 2h8"/><path d="M9 2v2.789a4 4 0 0 1-.672 2.219l-.656.984A4 4 0 0 0 7 10.212V20a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-9.789a4 4 0 0 0-.672-2.219l-.656-.984A4 4 0 0 1 15 4.788V2"/><path d="M7 15a6.472 6.472 0 0 1 5 0 6.47 6.47 0 0 0 5 0"/>',
      search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
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
      // Espermatozoide (IA) — IconPark \'sperm\' (Apache-2.0), dibujo clásico:
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
      table: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>'
    };
    var s = size || 18;
    return '<svg class="svg-icon" viewBox="0 0 24 24" width="' + s + '" height="' + s + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" style="display:inline-block; vertical-align:middle; margin-right:6px; position:relative; top:-1px;">' + (paths[name] || '') + '</svg>';
  }

  /* ---------- Vistas principales ---------- */
  function renderTablero(d) {
    var pot = d.potrero_filtro ? " — potrero: <b>" + esc(d.potrero_filtro) + "</b>" : "";
    var pdfBtn = "<a href='/api/reporte.pdf' class='tema-btn' download style='float:right; font-size:12px; text-decoration:none; padding:5px 12px; margin-top:-4px;'>" + icon("filePdf", 14) + "Reporte PDF</a>";
    var h = "<h3>" + icon("grid") + "Tablero finca" + pot + pdfBtn + "</h3>";
    h += "<div class='kpis'>"
      + kpi(d.activos, "Activos ♀♂") + kpi(d.hembras, "Hembras") + kpi(d.machos, "Machos")
      + kpi(d.partos_7d, "Partos 7d", d.partos_7d > 0 ? "alerta" : "")
      + kpi(d.celos_7d, "Celos 7d") + kpi(d.servicios_7d, "Serv. 7d")
      + kpi(d.retiros_activos, "Retiros", d.retiros_activos > 0 ? "alerta" : "") + "</div>";
    h += erroresHtml(d);
    h += grafico("evolucion", "Evolución del rebaño") + grafico("categorias", "Categorías del hato");

    // Últimos Eventos de la Finca (Partos, Muertes, Ventas, Traslados, Pesajes...)
    var eventos = d.eventos_recientes || [];
    h += "<div class='card' style='padding:16px; margin-top:16px; margin-bottom:16px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;'>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("calendar", 17) + "Últimos Eventos de la Finca (Partos, Muertes, Ventas...)</h4>"
      + "<span class='meta' style='font-size:12px; font-weight:600;'>" + eventos.length + " eventos recientes</span>"
      + "</div>"
      + "<p class='aviso' style='margin:4px 0 12px 0; font-size:12.5px;'>Registro cronológico de actividad del hato. Toca cualquier arete o cría para abrir su ficha técnica inmediata.</p>";

    if (!eventos.length) {
      h += vacio("No hay eventos recientes registrados.");
    } else {
      h += "<div class='tabla-scroll'><table>"
        + "<tr>"
        + "<th>Tipo Evento</th>"
        + "<th>Fecha</th>"
        + "<th>Animal / Arete</th>"
        + "<th>Detalle de la Actividad</th>"
        + "</tr>";

      eventos.forEach(function (ev) {
        var tipo = String(ev.tipo || "").toUpperCase();
        var chipHtml = "";
        if (tipo === "PARTO") {
          chipHtml = "<span class='chip verde' style='font-weight:700;'>" + icon("cowCalf", 13) + " Parto</span>";
        } else if (tipo === "MUERTE") {
          chipHtml = "<span class='chip rojo' style='font-weight:700;'>" + icon("skull", 13) + " Muerte</span>";
        } else if (tipo === "VENTA" || tipo === "DESCARTE" || tipo === "COMPRA") {
          chipHtml = "<span class='chip ambar' style='font-weight:700;'>" + icon("truck", 13) + " " + esc(tipo) + "</span>";
        } else if (tipo === "TRASLADO") {
          chipHtml = "<span class='chip azul' style='font-weight:700;'>" + icon("grass", 13) + " Traslado</span>";
        } else if (tipo === "PESAJE") {
          chipHtml = "<span class='chip gris' style='font-weight:700;'>" + icon("scale", 13) + " Pesaje</span>";
        } else if (tipo === "TRATAMIENTO") {
          chipHtml = "<span class='chip rojo' style='font-weight:700;'>" + icon("pill", 13) + " Tratamiento</span>";
        } else if (tipo === "SERVICIO") {
          chipHtml = "<span class='chip verde' style='font-weight:700;'>" + icon("sperm", 13) + " Inseminación</span>";
        } else {
          chipHtml = "<span class='chip gris'>" + esc(tipo) + "</span>";
        }

        var nomHtml = ev.nombre ? (" <small style='color:var(--texto-suave); font-weight:normal;'>(" + esc(ev.nombre) + ")</small>") : "";
        var esCria = (ev.detalle_label === "Madre");
        var iconoAnimal = esCria ? icon("calf", 15) : icon("cow", 15);
        var linkAnimal = "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(ev.tag) + "\" style='font-size:13.5px; font-weight:bold; display:inline-flex; align-items:center; gap:5px; text-decoration:none;'>" + iconoAnimal + "<span>" + esc(ev.tag) + "</span></a>" + nomHtml;

        var detalleExtra = "";
        if (ev.detalle_tag) {
          var labelDetalle = ev.detalle_label || "Cría";
          var icoDetalle = (labelDetalle.toLowerCase().indexOf("madre") >= 0) ? icon("cow", 13) : icon("calf", 13);
          detalleExtra = "<div style='margin-top:4px;'><small style='color:var(--texto-suave); margin-right:4px;'>" + esc(labelDetalle) + ":</small><a href='#' class='ficha-link chip verde' data-ir-ficha=\"" + esc(ev.detalle_tag) + "\" style='font-size:11.5px; padding:2px 7px; font-weight:bold; text-decoration:none; display:inline-flex; align-items:center; gap:4px;'>" + icoDetalle + "<span>" + esc(ev.detalle_tag) + "</span></a></div>";
        }

        var descHtml = "<b>" + esc(ev.descripcion || "") + "</b>";
        if (ev.notas && String(ev.notas).trim() && String(ev.notas).trim() !== String(ev.descripcion).trim()) {
          descHtml += "<div style='font-size:11.5px; color:var(--texto-suave); margin-top:2px;'>" + esc(ev.notas) + "</div>";
        }

        h += "<tr>"
          + "<td>" + chipHtml + "</td>"
          + "<td><b style='font-family:var(--font-mono); font-size:12px;'>" + esc(fechaCorta(ev.fecha)) + "</b></td>"
          + "<td>" + linkAnimal + detalleExtra + "</td>"
          + "<td>" + descHtml + "</td>"
          + "</tr>";
      });

      h += "</table></div>";
    }
    h += "</div>";

    h += "<h4>" + icon("grass") + "Distribución por potrero (toca para filtrar)</h4>";
    if (!d.por_potrero || !d.por_potrero.length) {
      h += vacio("Ningún potrero con animales.");
    } else {
      h += "<div class='tabla-scroll'><table><tr><th>Potrero</th><th>Cabezas</th></tr>";
      (d.por_potrero || []).forEach(function (f) {
        var nom = String(f.potrero || "");
        var celda = (nom && nom.toLowerCase() !== "sin potrero")
          ? "<a href='/?v=tablero&potrero=" + encodeURIComponent(nom) + "'>" + esc(nom) + "</a>"
          : esc(nom);
        h += "<tr><td>" + celda + "</td><td>" + esc(f.n) + "</td></tr>";
      });
      h += "</table></div>";
    }
    return h;
  }
  function renderRepro(d) {
    var h = "<h3>" + icon("sperm") + "Reproducción</h3>" + erroresHtml(d) + grafico("reproductivo_hato", "Estado reproductivo del hato");
    h += "<h4>" + icon("calendar") + "FEP ≤30d (próximos partos)</h4>"
      + tabla(d.fep_30d, [
        ["tag", "Vaca"], ["fecha", "Servicio"], ["toro_pajilla", "Toro"],
        ["fep_calculada", "FEP", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }]
      ], "Sin partos próximos en 30 días.");
    h += "<h4>" + icon("stethoscope") + "Diagnósticos de gestación recientes</h4>"
      + tabla(d.diagnosticos, [
        ["tag", "Vaca"], ["fecha", "Fecha"],
        ["resultado", "Resultado", "text", function (v) { return chipEstado(v); }],
        ["dias_gestacion", "Días gest."]
      ], "Sin diagnósticos recientes.");
    h += "<h4>" + icon("flame") + "Celos recientes</h4>"
      + tabla(d.celos_recientes, [["tag", "Vaca"], ["fecha", "Fecha"], ["am_pm", "AM/PM"]], "Sin celos recientes.");
    h += "<h4>" + icon("alert") + "Eco / Palpación pendientes</h4>"
      + tabla(d.eco_palp_pendientes, [
        ["tipo_alerta", "Tipo"],
        ["fecha_programada", "Fecha", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }],
        ["descripcion", "Detalle"]
      ], "Sin eco/palpaciones programadas.");
    h += "<h4>" + icon("alert") + "Condición Corporal Crítica (&lt; 2.5)</h4>"
      + tabla(d.condicion_corporal_critica, [
        ["tag", "Animal"], ["fecha", "Fecha"],
        ["valor", "Condición CC", "text", function (v) { return "<span class='chip rojo'>" + esc(v) + "</span>"; }],
        ["notas", "Observaciones"]
      ], "Ningún animal con condición corporal crítica registrada. 🎉");
    return h;
  }
  function renderSanidad(d) {
    var h = "<h3>" + icon("shieldPlus") + "Sanidad</h3>" + erroresHtml(d) + "<h4>" + icon("alert") + "Retiros activos (leche / carne)</h4>";
    if (!d.retiros || !d.retiros.length) { h += vacio("Ningún animal en retiro. 🎉"); }
    else {
      h += "<div class='tabla-scroll'><table><tr><th>Animal</th><th>Producto</th><th>Fin leche</th><th>Fin carne</th></tr>";
      h += d.retiros.map(function (r) {
        function celda(k) {
          if (!r[k]) return "<td>—</td>";
          var rest = r[k + "_dias"];
          var b = rest != null && rest <= 0 ? "rojo" : (rest != null && rest <= 3 ? "ambar" : "verde");
          return "<td><span class='chip " + b + "'>" + esc(r[k]) + (rest != null ? " (" + rest + "d)" : "") + "</span></td>";
        }
        return "<tr><td><b>" + esc(r.tag) + "</b></td><td>" + esc(r.producto) + "</td>" + celda("fecha_fin_retiro_leche") + celda("fecha_fin_retiro_carne") + "</tr>";
      }).join("");
      h += "</table></div>";
    }
    h += "<h4>" + icon("pill") + "Últimos tratamientos</h4>"
      + tabla(d.ultimos_tratamientos, [
        ["tag", "Animal"], ["fecha", "Fecha"], ["producto", "Producto"],
        ["dosis", "Dosis"], ["via", "Vía"]
      ], "Sin tratamientos registrados.");
    return h;
  }
  function renderPasturas(d) {
    var h = "<h3>" + icon("grass") + "Pasturas (Voisin)</h3>" + erroresHtml(d);
    h += grafico("mapa_potreros", "Mapa de potreros") + grafico("ocupacion", "Ocupación de potreros") + grafico("aforo", "Aforo de forraje");
    h += "<h4>" + icon("hourglass") + "Ocupación y reposo por potrero</h4>";
    if (!d.potreros || !d.potreros.length) { h += vacio("Sin potreros con geometría registrada."); }
    else {
      h += "<div class='tabla-scroll'><table><tr><th>Potrero</th><th>Estado</th><th>Ocupación</th><th>Reposo</th><th>Ha</th></tr>";
      h += d.potreros.map(function (p) {
        var st = p.semaforo === "🟢" ? "Descanso ok" : p.semaforo === "🟡" ? "Rotar pronto" : p.semaforo === "🔴" ? "Sobreocupado" : "Sin datos";
        return "<tr><td><b>" + esc(p.nombre || p.codigo || p.id) + "</b></td><td>" + chipEstado(p.semaforo + " " + st) + "</td>"
          + "<td>" + (p.dias_ocupacion != null ? p.dias_ocupacion + " d" : "—") + "</td>"
          + "<td>" + (p.dias_reposo != null ? p.dias_reposo + " d" : "—") + "</td>"
          + "<td>" + (p.area_has != null ? p.area_has + " ha" : "—") + "</td></tr>";
      }).join("");
      h += "</table></div>";
    }
    h += "<h4>" + icon("chartLine") + "NDVI reciente (satélite)</h4>"
      + tabla(d.ndvi_reciente, [
        ["potrero", "Potrero"], ["fecha", "Fecha"],
        ["ndvi_promedio", "NDVI", "text", function (v) {
          var n = Number(v);
          var c = n >= 0.6 ? "verde" : n >= 0.4 ? "ambar" : n > 0 ? "rojo" : "gris";
          return "<span class='chip " + c + "'>" + esc(v) + "</span>";
        }]
      ], "Sin lecturas NDVI recientes.");
    h += "<h4>" + icon("rain") + "Pluviómetro Local Reciente</h4>"
      + tabla(d.pluviometria_reciente, [
        ["fecha", "Fecha"],
        ["mm_lluvia", "Lluvia", "text", function (v) {
          return "<b>" + esc(v) + " mm</b>";
        }],
        ["observaciones", "Observaciones"]
      ], "Sin registros de pluviometría manual.");
    h += "<h4>" + icon("grass") + "Aforos de Pasto Recientes</h4>"
      + tabla(d.aforos_recientes, [
        ["potrero", "Potrero"], ["fecha", "Fecha"],
        ["aforo_kg_m2", "Aforo MV", "text", function (v) {
          return "<b>" + esc(v) + " kg/m²</b>";
        }],
        ["pct_ms", "% MS", "text", function (v) {
          return esc(v) + " %";
        }]
      ], "Sin aforos históricos registrados.");
    return h;
  }
  function renderLeche(d) {
    var total = 0;
    (d.serie_tanque || []).forEach(function (f) { total += Number(f.litros) || 0; });
    var btnIa = "<button type='button' class='tema-btn' id='btn-ir-captura-leche' style='float:right; font-size:12px; padding:5px 12px; margin-top:-4px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer;'>" + icon("sparkles", 14) + "Digitalizar Recibo con IA</button>";
    var h = "<h3>" + icon("milk") + "Producción de Leche (Recibos y Control)" + btnIa + "</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.controles.length, "Controles") + kpi(total.toFixed(0), "L últimos 30 días");
    var mejor = (d.ranking_vacas && d.ranking_vacas.length) ? d.ranking_vacas[0] : null;
    if (mejor) {
      h += kpi(esc(mejor.tag), "Mejor vaca", "ok");
    }
    h += "</div>";

    if (d.fotos_recibos && d.fotos_recibos.length) {
      h += "<h4>" + icon("camera") + "Recibos y Planillas de Quincena (Fotos de Respaldo)</h4>";
      h += "<p class='aviso' style='margin-bottom:10px;'>Fotos de recibos o planillas manuales de leche. Toca cualquier imagen para abrirla en pantalla completa con zoom táctil y verificar las anotaciones diarias.</p>";
      h += "<div class='fotos-wrap' style='display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:10px; margin-bottom:18px;'>";
      d.fotos_recibos.forEach(function (f) {
        var ruta = f.ruta ? (f.ruta.startsWith("/") ? f.ruta : "/" + f.ruta) : "";
        h += "<div class='foto-card' style='border:1px solid var(--borde-suave); border-radius:8px; overflow:hidden; background:var(--superficie); padding:6px;'>"
          + "<div style='aspect-ratio:4/3; overflow:hidden; border-radius:6px; background:#111; display:flex; align-items:center; justify-content:center; cursor:pointer;'>"
          + "<img src='" + esc(ruta) + "' alt='" + esc(f.caption || "Recibo de leche") + "' class='zoomable-img' style='width:100%; height:100%; object-fit:cover;'>"
          + "</div>"
          + "<div style='font-size:11px; font-weight:600; margin-top:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>" + esc(f.caption || "Recibo") + "</div>"
          + "<div style='font-size:10px; color:var(--texto-suave);'>" + esc(fechaCorta(f.fecha)) + "</div>"
          + "</div>";
      });
      h += "</div>";
    }

    h += grafico("leche_total", "Producción total de leche") + grafico("eficiencia_lechera", "Eficiencia lechera");
    h += grafico("ranking_vacas_leche", "Ranking de producción por vaca");
    h += "<h4>" + icon("chartBar") + "Ranking de vacas por litros (acumulado)</h4>"
      + tabla(d.ranking_vacas, [
        ["tag", "Vaca"], ["total_litros", "Total L", "num"], ["controles", "Controles", "num"],
        ["ultima_fecha", "Último control", "text", function (v) { return v ? esc(fechaCorta(v)) : "—"; }]
      ], "Sin producción por vaca registrada.");
    h += "<h4>" + icon("chartLine") + "Producción por día</h4>"
      + tabla(d.serie_tanque, [["fecha", "Fecha"], ["litros", "Litros", "num"]], "Sin registros de producción o recibos.");
    h += "<h4>" + icon("calendar") + "Controles individuales</h4>"
      + tabla(d.controles, [["tag", "Vaca"], ["fecha", "Fecha"], ["litros", "L", "num"]], "Sin controles individuales.");
    return h;
  }

  function bindLeche() {
    var btnIa = document.getElementById("btn-ir-captura-leche");
    if (btnIa) {
      btnIa.addEventListener("click", function () {
        _tipoCapturaActual = "leche";
        irAVista("captura");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
      });
    }
  }

  /* ---------- Finanzas: Ingresos, Egresos y Utilidad ---------- */
  var _finanzasAno = new Date().getFullYear();
  var CATEGORIAS_FINANZAS_LABEL = {
    VENTA_LECHE: "Venta de leche", VENTA_ANIMAL: "Venta de animales",
    COMPRA_ANIMAL: "Compra de animales", NOMINA: "Nómina / Jornales",
    INSUMO: "Insumos (sal, alambre, etc.)", VETERINARIO: "Veterinario / Medicamentos",
    INFRAESTRUCTURA: "Infraestructura / Mantenimiento", COMBUSTIBLE: "Combustible",
    OTRO_INGRESO: "Otro ingreso", OTRO_EGRESO: "Otro gasto"
  };
  function etiquetaCategoriaFinanza(cat) { return CATEGORIAS_FINANZAS_LABEL[cat] || cat; }

  function renderFinanzas(d) {
    var r = d.resumen || { total_ingresos: 0, total_egresos: 0, utilidad: 0, categorias: [] };
    var btnGasto = "<button type='button' class='tema-btn' id='btn-ir-captura-gasto' style='float:right; font-size:12px; padding:5px 12px; margin-top:-4px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer;'>" + icon("receipt", 14) + "Registrar Ingreso / Gasto</button>";
    var h = "<h3>" + icon("banknote") + "Finanzas: Ingresos, Egresos y Utilidad" + btnGasto + "</h3>" + erroresHtml(d);

    var anoActual = new Date().getFullYear();
    var opcionesAno = "";
    for (var y = anoActual; y >= anoActual - 4; y--) {
      opcionesAno += "<option value='" + y + "'" + (y === _finanzasAno ? " selected" : "") + ">" + y + "</option>";
    }
    h += "<div style='margin-bottom:12px;'><label style='font-size:13px; font-weight:600;'>Año: "
      + "<select id='fin-ano' style='padding:6px 10px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-left:6px;'>" + opcionesAno + "</select></label></div>";

    h += "<div class='kpis'>"
      + kpi(fmtMoneda(r.total_ingresos), "Ingresos " + esc(d.desde || "") + " a " + esc(d.hasta || ""), "ok")
      + kpi(fmtMoneda(r.total_egresos), "Egresos", "alerta")
      + kpi(fmtMoneda(r.utilidad), "Utilidad", r.utilidad >= 0 ? "ok" : "alerta")
      + "</div>";

    h += "<h4>" + icon("chartBar") + "Desglose por categoría</h4>"
      + tabla(r.categorias, [
        ["tipo", "Tipo", "text", function (v) { return "<span class='chip " + (v === "INGRESO" ? "verde" : "rojo") + "'>" + esc(v) + "</span>"; }],
        ["categoria", "Categoría", "text", function (v) { return esc(etiquetaCategoriaFinanza(v)); }],
        ["total", "Monto", "text", function (v) { return "<b>" + fmtMoneda(v) + "</b>"; }],
        ["n", "# Registros", "num"]
      ], "Sin ingresos ni egresos registrados en este periodo.");

    var movs = (d.recientes || []).map(function (f) {
      return {
        fecha: f.fecha, tipo: f.tipo, categoria: etiquetaCategoriaFinanza(f.categoria),
        detalle: f.concepto || "", monto: f.monto,
        animal_tag: f.animal_tag || null,
        otro_txt: f.animal_tag ? "" : (f.contraparte || f.potrero_nombre || "")
      };
    }).concat((d.ventas_compras || []).map(function (m) {
      return {
        fecha: m.fecha, tipo: m.tipo_movimiento === "VENTA" ? "INGRESO" : "EGRESO",
        categoria: m.tipo_movimiento === "VENTA" ? "Venta de animales" : "Compra de animales",
        detalle: m.notas || "", monto: m.precio,
        animal_tag: m.animal_tag || null,
        otro_txt: m.procedencia_destino || ""
      };
    })).sort(function (a, b) { return (b.fecha || "").localeCompare(a.fecha || ""); });

    h += "<h4>" + icon("calendar") + "Movimientos recientes</h4>"
      + tabla(movs, [
        ["fecha", "Fecha", "text", function (v) { return esc(fechaCorta(v)); }],
        ["tipo", "Tipo", "text", function (v) { return "<span class='chip " + (v === "INGRESO" ? "verde" : "rojo") + "'>" + esc(v) + "</span>"; }],
        ["categoria", "Categoría"],
        ["animal_tag", "Animal / Contraparte", "text", function (v, fila) {
          var link = v ? ("<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(v) + "\" style='font-weight:bold; text-decoration:none; display:inline-flex; align-items:center; gap:4px;'>" + icon("cow", 13) + "<span>" + esc(v) + "</span></a>") : "";
          var extra = fila.otro_txt ? esc(fila.otro_txt) : "";
          if (link && extra) return link + " · " + extra;
          return link || extra || "—";
        }],
        ["detalle", "Detalle"],
        ["monto", "Monto", "text", function (v) { return fmtMoneda(v); }]
      ], "Sin movimientos recientes en este periodo.");

    return h;
  }

  function bindFinanzas() {
    var btnGasto = document.getElementById("btn-ir-captura-gasto");
    if (btnGasto) {
      btnGasto.addEventListener("click", function () {
        _tipoCapturaActual = "gasto";
        irAVista("captura");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
      });
    }
    var selAno = document.getElementById("fin-ano");
    if (selAno) {
      selAno.addEventListener("change", function () {
        _finanzasAno = parseInt(selAno.value, 10) || new Date().getFullYear();
        cargarFinanzasPeriodo();
      });
    }
  }

  function cargarFinanzasPeriodo() {
    var desde = _finanzasAno + "-01-01";
    var hasta = _finanzasAno + "-12-31";
    skeleton(vista, "finanzas");
    fetchJSON("/api/finanzas?desde=" + desde + "&hasta=" + hasta, function (d) {
      if (!vista) return;
      montarVista(vista, renderFinanzas(d), true);
      bindFinanzas();
    }, vista);
  }

  /* ---------- Vistas WS-5: Inventario / Población / Genética / Agenda ---------- */
  function barrasDeFilas(filas, pctKey, nKey) {
    if (!filas || !filas.length) return vacio("Sin datos.");
    var h = "";
    filas.forEach(function (f) {
      var pct = Math.max(0, Math.min(100, Number(f[pctKey]) || 0));
      h += "<div class='barra-fila'><span class='et'>" + esc(f.categoria || f.raza) + "</span>"
        + "<span class='pista'><span class='relleno' style='width:" + pct + "%'></span></span>"
        + "<span class='num'>" + esc(f[nKey]) + "</span></div>";
    });
    return h;
  }
  function renderInventario(d) {
    // Vista única Inventario + Población: tabla SG + pirámide + GMD + gráficos.
    var expBtn = "<button type='button' class='tema-btn' data-accion='exportar-inventario' style='float:right; font-size:12px; padding:4px 10px; margin-top:-4px;'>" + icon("download", 14) + "Exportar CSV</button>";
    var h = "<h3>" + icon("cow") + "Inventario y Población" + expBtn + "</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.total_activos, "Activos totales")
      + kpi(d.total_hembras, "Hembras") + kpi(d.total_machos, "Machos")
      + kpi(d.edad_promedio != null ? d.edad_promedio + "a" : "—", "Edad promedio")
      + kpi(d.total_sin_sexo, "Sin clasificar", d.total_sin_sexo > 0 ? "alerta" : "")
      + kpi(d.terneros_menor_12m, "Crías <12m") + "</div>";
    h += grafico("waterfall_inventario", "Movimientos del hato (entradas/salidas)");
    h += "<h4>" + icon("chartLine") + "Distribución por Categorías de Edad</h4>";
    h += "<div class='tabla-scroll'><table><tr><th>Categoría</th><th>Nro</th><th>Distrib.</th><th>Acum.</th></tr>";
    (d.filas || []).forEach(function (f) {
      h += "<tr><td>" + esc(f.categoria) + "</td><td>" + esc(f.n) + "</td><td>" + esc(f.pct) + "%</td><td>" + esc(f.acum) + "%</td></tr>";
    });
    h += "</table></div>";
    h += "<h4>" + icon("grass") + "Distribución por potrero</h4>";
    if (!d.por_potrero || !d.por_potrero.length) {
      h += vacio("Ningún potrero con animales.");
    } else {
      h += "<div class='tabla-scroll'><table><tr><th>Potrero</th><th>Cabezas</th></tr>";
      (d.por_potrero || []).forEach(function (f) {
        var nom = String(f.potrero || "");
        var celda = (nom && nom.toLowerCase() !== "sin potrero")
          ? "<a href='/?v=tablero&potrero=" + encodeURIComponent(nom) + "'>" + esc(nom) + "</a>"
          : esc(nom);
        h += "<tr><td>" + celda + "</td><td>" + esc(f.n) + "</td></tr>";
      });
      h += "</table></div>";
    }
    // Pirámide de edades
    var maxP = 1;
    (d.piramide || []).forEach(function (f) { maxP = Math.max(maxP, Number(f.hembras) || 0, Number(f.machos) || 0); });
    h += "<h4>" + icon("chartBar") + "Pirámide de edades (hembras · machos)</h4>";
    if (!d.piramide || !d.piramide.length) {
      h += vacio("Sin datos de edad para dibujar la pirámide.");
    } else {
      h += "<div class='piramide'>";
      (d.piramide || []).forEach(function (f) {
        var hB = Math.round((Number(f.hembras) || 0) / maxP * 100);
        var mB = Math.round((Number(f.machos) || 0) / maxP * 100);
        h += "<div class='pir-fila'>"
          + "<div class='pir-pista der'><div class='pir-barra hembra' style='width:" + hB + "%'></div></div>"
          + "<div class='pir-banda'>" + esc(f.banda) + "<br><small>" + esc(f.hembras) + " H · " + esc(f.machos) + " M</small></div>"
          + "<div class='pir-pista izq'><div class='pir-barra macho' style='width:" + mB + "%'></div></div>"
          + "</div>";
      });
      h += "</div>";
    }
    h += "<h4>" + icon("scale") + "Últimos Pesajes y GMD (Ganancia Media Diaria)</h4>"
      + grafico("gmd_hato", "GMD del hato (kg/día)")
      + tabla(d.gmd_reciente, [
        ["tag", "Animal"], ["fecha", "Fecha"], ["peso_kg", "Peso (kg)", "num"],
        ["gmd_calculada", "GMD (g/día)", "text", function (v) {
          var n = Number(v) * 1000;
          var c = n >= 600 ? "verde" : n >= 300 ? "ambar" : n > 0 ? "gris" : "rojo";
          return "<span class='chip " + c + "'>" + esc(n.toFixed(0)) + " g</span>";
        }]
      ], "Sin pesajes con GMD calculada recientemente.");
    return h;
  }
  function renderGenetica(d) {
    var h = "<h3>" + icon("dna") + "Composición genética (razas)</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.total, "Animales tipificados") + "</div>";
    if (d.filas && d.filas.length) {
      var porNombre = (d.filas || []).map(function (f) { return { categoria: f.raza_nombre || f.raza, n: f.n, pct: f.pct }; });
      h += "<h4>" + icon("chartBar") + "Distribución por raza</h4>" + barrasDeFilas(porNombre, "pct", "n");
      h += "<h4>" + icon("chartLine") + "Detalle</h4>" + tabla(d.filas, [["raza_nombre", "Raza"], ["raza", "Código"], ["n", "Cabezas", "num"], ["pct", "% del hato"]], "Sin datos.");
    } else {
      h += vacio("Sin razas registradas en el hato activo.");
    }
    h += "<h4>" + icon("pajuelas") + "Inventario de Pajuelas (Semen para I.A.)</h4>"
      + tabla(d.pajuelas_inventario, [
        ["codigo_toro", "Código Toro"], ["raza", "Raza"],
        ["procedencia", "Procedencia"], ["canastilla", "Canastilla"],
        ["cantidad", "Pajuelas", "num", function (v) {
          var n = Number(v);
          var c = n >= 10 ? "verde" : n >= 3 ? "ambar" : "rojo";
          return "<span class='chip " + c + "'>" + esc(n) + "</span>";
        }]
      ], "Sin inventario de pajuelas registrado.");
    h += "<h4>" + icon("snowflake") + "Recargas del Termo de Nitrógeno</h4>"
      + tabla(d.termo_nitrogeno, [
        ["fecha_recarga", "Última Recarga"],
        ["proxima_recarga", "Próxima Recarga", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }],
        ["dias_intervalo", "Intervalo (días)", "num"]
      ], "Sin historial de recargas de nitrógeno.");
    return h;
  }
  function renderAgenda(d) {
    var pdfBtn = "<a href='/api/reporte.pdf' class='tema-btn' download style='float:right; font-size:12px; text-decoration:none; padding:4px 10px; margin-top:-4px;'>" + icon("filePdf", 14) + "Reporte PDF</a>";
    var h = "<h3>" + icon("calendar") + "Agenda próximos " + esc(d.dias) + " días" + pdfBtn + "</h3>" + erroresHtml(d);
    var evs = d.eventos || [];
    var urgencia = function (f) {
      if (f.faltan_dias == null) return "gris";
      return f.faltan_dias <= 0 ? "rojo" : f.faltan_dias <= 2 ? "ambar" : "verde";
    };
    var chipUrg = function (v) {
      return "<span class='chip " + urgencia(v) + "'>" + esc(v.faltan_dias != null ? (v.faltan_dias <= 0 ? "HOY" : v.faltan_dias + "d") : "?") + "</span>";
    };
    if (evs.length) {
      h += "<h4>" + icon("alert") + "Alertas programadas</h4><div class='tabla-scroll'><table><tr><th>Fecha</th><th>Tipo</th><th>Animal</th><th>Detalle</th><th>En</th></tr>";
      evs.forEach(function (e) {
        h += "<tr><td><b>" + esc(e.fecha) + "</b></td><td>" + esc(e.etiqueta) + "</td><td>" + esc(e.tag || "—") + "</td><td>" + esc(e.descripcion || "—") + "</td><td>" + chipUrg(e) + "</td></tr>";
      });
      h += "</table></div>";
    } else {
      h += "<p class='aviso'>Sin alertas programadas en los próximos " + esc(d.dias) + " días.</p>";
    }
    var ret = d.retiros || [];
    if (ret.length) {
      var expRetBtn = "<button type='button' class='tema-btn' data-accion='exportar-retiros' style='float:right; font-size:12px; padding:4px 10px; margin-top:-4px;'>" + icon("download", 14) + "Exportar Retiros CSV</button>";
      h += "<h4>" + icon("alert") + "Retiros sanitarios activos" + expRetBtn + "</h4><div class='tabla-scroll'><table><tr><th>Animal</th><th>Producto</th><th>Fin leche</th><th>Fin carne</th></tr>";
      ret.forEach(function (r) {
        function c(f, df) {
          if (!f) return "<td>—</td>";
          var b = df != null && df <= 0 ? "rojo" : df != null && df <= 3 ? "ambar" : "verde";
          return "<td><span class='chip " + b + "'>" + esc(f) + (df != null ? " (" + df + "d)" : "") + "</span></td>";
        }
        h += "<tr><td><b>" + esc(r.tag) + "</b></td><td>" + esc(r.producto) + "</td>" + c(r.fin_leche, r.fin_leche_dias) + c(r.fin_carne, r.fin_carne_dias) + "</tr>";
      });
      h += "</table></div>";
    }
    return h;
  }

  /* ---------- Modo Manga de Corral (Pesajes, Tratamientos Masivos, BLE) ---------- */
  var _sesionManga = [];
  function renderManga() {
    var h = "<h3>" + icon("corral") + "Manga de Corral — Pesajes y Lotes</h3>";
    h += "<div class='manga-tabs'>"
      + "<button type='button' class='manga-tab-btn act' data-mtab='pesaje'>" + icon("scale", 14) + "Pesaje Rápido & GMD</button>"
      + "<button type='button' class='manga-tab-btn' data-mtab='lote'>" + icon("syringe", 14) + "Tratamiento en Lote</button>"
      + "<button type='button' class='manga-tab-btn' data-mtab='ble'>" + icon("bluetooth", 14) + "Báscula / RFID BLE</button>"
      + "</div>";

    // Panel 1: Pesaje Rápido
    h += "<div id='manga-panel-pesaje'>";
    h += "<div class='manga-pesaje-box'>"
      + "<label style='font-size:13px; font-weight:600;'>Arete / Tag:</label>"
      + "<input id='manga-tag' class='manga-input-grande' placeholder='ej. 47' autocomplete='off' list='dl-tags' autofocus style='margin-bottom:12px;'>"
      + "<label style='font-size:13px; font-weight:600;'>Peso Actual (kg):</label>"
      + "<input id='manga-peso' type='number' step='0.5' class='manga-input-grande' placeholder='0.0' style='color:var(--verde-marca); font-size:38px; margin-bottom:12px;'>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px;'>"
      + "<div style='flex:1; min-width:130px;'><label style='font-size:12px;'>Condición Corporal:</label>"
      + "<select id='manga-cc' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
      + "<option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0'>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0 (Gorda)</option></select></div>"
      + "<div style='flex:1; min-width:130px;'><label style='font-size:12px;'>Evento:</label>"
      + "<select id='manga-evento' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
      + "<option value='PESAJE'>Control Periódico</option><option value='DESTETE'>Destete</option><option value='ENTRADA'>Entrada / Compra</option><option value='VENTA'>Venta / Salida</option></select></div>"
      + "</div>"
      + "<button type='button' id='btn-manga-guardar-peso' class='btn-guardar-manga'>" + icon("save", 15) + "Guardar Pesaje (Enter)</button>"
      + "</div>";

    h += "<div id='manga-resultado-kpi' style='display:none;' class='manga-pesaje-box'></div>";

    h += "<h4>" + icon("chartBar") + "Historial de esta Sesión en Manga</h4>";
    h += "<div id='manga-historial-wrap'>" + renderTablaSesionManga() + "</div>";
    h += "</div>";

    // Panel 2: Tratamiento en Lote
    h += "<div id='manga-panel-lote' style='display:none;'>";
    h += "<div class='card' style='margin-bottom:14px;'>"
      + "<h4>" + icon("syringe") + "Aplicación Masiva de Tratamiento por Potrero / Lote</h4>"
      + "<p class='aviso'>Aplica automáticamente el tratamiento y los tiempos de retiro a todos los animales activos del potrero seleccionado.</p>"
      + "<div style='display:flex; flex-direction:column; gap:10px; margin-top:12px;'>"
      + "<label>Potrero a tratar: <input id='manga-lote-potrero' placeholder='ej. Guayabal' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label>O aretes individuales (opcional, separados por coma): <input id='manga-lote-tags' placeholder='ej. 47, JA26-6, 88' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label>Tipo de tratamiento: <select id='manga-lote-tipo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='Desparasitante'>Desparasitante</option><option value='Vacuna'>Vacuna</option><option value='Vitaminas'>Vitaminas / Mineralizante</option><option value='Antibiótico'>Antibiótico</option><option value='Otro'>Otro</option></select></label>"
      + "<label>Fármaco / Producto: <input id='manga-lote-producto' placeholder='Nombre comercial (ej. Ivermectina 1%, Albendazol)' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:140px;'><label>Dosis: <input id='manga-lote-dosis' placeholder='ej. 1 ml / 50kg' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
      + "<div style='flex:1; min-width:140px;'><label>Vía: <select id='manga-lote-via' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='SC'>Subcutánea (SC)</option><option value='IM'>Intramuscular (IM)</option><option value='Oral'>Oral</option><option value='Pour-on'>Pour-on / Tópico</option><option value='IV'>Intravenosa (IV)</option></select></label></div>"
      + "</div>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:140px;'><label>Retiro Leche (días): <input type='number' id='manga-lote-ret-leche' value='0' min='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
      + "<div style='flex:1; min-width:140px;'><label>Retiro Carne (días): <input type='number' id='manga-lote-ret-carne' value='0' min='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
      + "</div>"
      + "<label>Diagnóstico / Motivo: <input id='manga-lote-diag' placeholder='ej. Control preventivo parásitos época seca' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<button type='button' id='btn-manga-guardar-lote' class='btn-guardar-manga' style='margin-top:10px; background:#1F6C9F;'>" + icon("syringe", 15) + "Aplicar Tratamiento en Lote</button>"
      + "</div>"
      + "</div>";
    h += "</div>";

    // Panel 3: BLE
    h += "<div id='manga-panel-ble' style='display:none;'>";
    h += "<div class='gps-box'>"
      + "<h4>" + icon("alert") + "Conexión Web Bluetooth a Báscula / RFID</h4>"
      + "<p class='aviso'>Permite recibir el peso o arete leído automáticamente desde básculas electrónicas (Tru-Test, Gallagher) o bastones RFID (Allflex) por Bluetooth BLE sin teclear.</p>"
      + "<button type='button' id='btn-manga-ble-conectar' class='btn-guardar-manga' style='max-width:320px; margin:14px auto;'>" + icon("bluetooth", 15) + "Conectar Dispositivo BLE</button>"
      + "<div id='manga-ble-estado' class='aviso' style='margin-top:14px;'>Estado: Desconectado.</div>"
      + "</div>";
    h += "</div>";

    return h;
  }

  function renderTablaSesionManga() {
    if (!_sesionManga || !_sesionManga.length) {
      return vacio("Aún no se han registrado pesajes en esta sesión de manga.");
    }
    var h = "<div class='tabla-scroll'><table><tr><th>Hora</th><th>Tag</th><th>Peso (kg)</th><th>GMD</th><th>Estado</th></tr>";
    _sesionManga.forEach(function (f) {
      var chipGmd = f.gmd != null && !isNaN(f.gmd)
        ? "<span class='chip " + (Number(f.gmd) >= 600 ? "verde" : Number(f.gmd) > 0 ? "ambar" : "rojo") + "'>" + (Number(f.gmd) > 0 ? "+" : "") + Number(f.gmd).toFixed(0) + " g/d</span>"
        : (f.gmd || "—");
      h += "<tr><td>" + esc(f.hora) + "</td><td><b>" + esc(f.tag) + "</b></td><td><b>" + esc(f.peso) + " kg</b></td><td>" + chipGmd + "</td><td>" + esc(f.estado) + "</td></tr>";
    });
    h += "</table></div>";
    return h;
  }

  function bindManga() {
    var tabs = qa(".manga-tab-btn");
    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        tabs.forEach(function (b) { b.classList.remove("act"); });
        btn.classList.add("act");
        var mtab = btn.getAttribute("data-mtab");
        var pPesaje = document.getElementById("manga-panel-pesaje");
        var pLote = document.getElementById("manga-panel-lote");
        var pBle = document.getElementById("manga-panel-ble");
        if (pPesaje) pPesaje.style.display = mtab === "pesaje" ? "block" : "none";
        if (pLote) pLote.style.display = mtab === "lote" ? "block" : "none";
        if (pBle) pBle.style.display = mtab === "ble" ? "block" : "none";
        if (mtab === "pesaje") {
          var inp = document.getElementById("manga-tag");
          if (inp) inp.focus();
        }
      });
    });

    var inpTag = document.getElementById("manga-tag");
    var inpPeso = document.getElementById("manga-peso");
    var btnGuardar = document.getElementById("btn-manga-guardar-peso");
    if (inpTag && inpPeso) {
      inpTag.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          inpPeso.focus();
        }
      });
      inpPeso.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          if (btnGuardar) btnGuardar.click();
        }
      });
    }

    if (btnGuardar) {
      btnGuardar.addEventListener("click", function () {
        var tag = (inpTag && inpTag.value || "").trim();
        var pesoStr = (inpPeso && inpPeso.value || "").trim();
        var cc = (q("#manga-cc") && q("#manga-cc").value) || null;
        var evento = (q("#manga-evento") && q("#manga-evento").value) || "PESAJE";

        if (!tag || !pesoStr) {
          alert("Debe escribir el arete/tag y el peso en kg.");
          return;
        }
        var peso = parseFloat(pesoStr);
        if (isNaN(peso) || peso <= 0) {
          alert("El peso debe ser un número válido mayor a 0.");
          return;
        }

        var resBox = document.getElementById("manga-resultado-kpi");

        function procesarResultadoLocal(data) {
          enviarTelemetriaSilenciosa("pesaje_manga");
          var gmd = data.gmd_g_dia;
          var chipGmd = gmd != null && !isNaN(gmd)
            ? "<span class='chip " + (gmd >= 600 ? "verde" : gmd > 0 ? "ambar" : "rojo") + "'>" + (gmd > 0 ? "+" : "") + Number(gmd).toFixed(0) + " g/d</span>"
            : "<span class='chip gris'>Primer pesaje</span>";

          if (resBox) {
            resBox.style.display = "block";
            resBox.innerHTML = "<b>✅ Pesaje Registrado:</b> Animal <b>" + esc(tag) + "</b> — <b>" + peso + " kg</b><br>"
              + (data.peso_anterior != null
                ? "Anterior: <b>" + esc(data.peso_anterior) + " kg</b> (hace " + esc(data.dias_entre_pesajes) + " días) · GMD: " + chipGmd
                : "Primer pesaje registrado para este animal.");
          }

          _sesionManga.unshift({
            hora: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }),
            tag: tag,
            peso: peso,
            gmd: gmd,
            estado: "🟢 Guardado"
          });
          var wrap = document.getElementById("manga-historial-wrap");
          if (wrap) wrap.innerHTML = renderTablaSesionManga();

          if (inpPeso) inpPeso.value = "";
          if (inpTag) { inpTag.value = ""; inpTag.focus(); }
        }

        if (navigator.onLine === false) {
          encolarOffline("pesaje", { animal_tag: tag, peso_kg: peso, evento: evento, condicion_corporal: cc }).then(function () {
            if (resBox) {
              resBox.style.display = "block";
              resBox.innerHTML = "<b>💾 Pesaje Guardado Offline:</b> Animal <b>" + esc(tag) + "</b> — <b>" + peso + " kg</b> (en cola para sincronizar al volver la señal)";
            }
            _sesionManga.unshift({
              hora: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }),
              tag: tag,
              peso: peso,
              gmd: "—",
              estado: "💾 Offline"
            });
            var wrap = document.getElementById("manga-historial-wrap");
            if (wrap) wrap.innerHTML = renderTablaSesionManga();
            if (inpPeso) inpPeso.value = "";
            if (inpTag) { inpTag.value = ""; inpTag.focus(); }
          });
          return;
        }

        fetch("/api/manga/pesaje", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tag: tag, peso_kg: peso, evento: evento, condicion_corporal: cc })
        }).then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        }).then(function (data) {
          if (data.ok) procesarResultadoLocal(data);
          else alert("Error: " + (data.error || "No se pudo registrar"));
        }).catch(function (err) {
          encolarOffline("pesaje", { animal_tag: tag, peso_kg: peso, evento: evento, condicion_corporal: cc }).then(function () {
            if (resBox) {
              resBox.style.display = "block";
              resBox.innerHTML = "<b>💾 Guardado Offline:</b> Animal <b>" + esc(tag) + "</b> (" + esc(err.message) + " — en cola local)";
            }
            _sesionManga.unshift({
              hora: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }),
              tag: tag,
              peso: peso,
              gmd: "—",
              estado: "💾 Offline"
            });
            var wrap = document.getElementById("manga-historial-wrap");
            if (wrap) wrap.innerHTML = renderTablaSesionManga();
            if (inpPeso) inpPeso.value = "";
            if (inpTag) { inpTag.value = ""; inpTag.focus(); }
          });
        });
      });
    }

    var btnLote = document.getElementById("btn-manga-guardar-lote");
    if (btnLote) {
      btnLote.addEventListener("click", function () {
        var pot = (q("#manga-lote-potrero") && q("#manga-lote-potrero").value || "").trim();
        var tagsTxt = (q("#manga-lote-tags") && q("#manga-lote-tags").value || "").trim();
        var prod = (q("#manga-lote-producto") && q("#manga-lote-producto").value || "").trim();
        var tipo = (q("#manga-lote-tipo") && q("#manga-lote-tipo").value) || "Tratamiento";
        var dosis = (q("#manga-lote-dosis") && q("#manga-lote-dosis").value) || "";
        var via = (q("#manga-lote-via") && q("#manga-lote-via").value) || "SC";
        var rLeche = parseInt(q("#manga-lote-ret-leche") && q("#manga-lote-ret-leche").value || 0, 10);
        var rCarne = parseInt(q("#manga-lote-ret-carne") && q("#manga-lote-ret-carne").value || 0, 10);
        var diag = (q("#manga-lote-diag") && q("#manga-lote-diag").value) || "";

        if (!prod) { alert("Debe especificar el fármaco o producto a aplicar."); return; }
        if (!pot && !tagsTxt) { alert("Debe indicar el potrero o la lista de tags."); return; }

        var payload = {
          producto: prod,
          potrero: pot,
          tipo: tipo,
          dosis: dosis,
          via: via,
          dias_retiro_leche: rLeche,
          dias_retiro_carne: rCarne,
          diagnostico: diag
        };
        if (tagsTxt) {
          payload.tags = tagsTxt.split(/[\s,;]+/).filter(Boolean);
        }

        if (!confirm("¿Desea aplicar '" + prod + "' a los animales de " + (pot ? "potrero " + pot : tagsTxt) + "?")) {
          return;
        }

        fetch("/api/manga/tratamiento_lote", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              alert("✅ Tratamiento aplicado a " + res.procesados + " animales con éxito.");
              if (q("#manga-lote-producto")) q("#manga-lote-producto").value = "";
              if (q("#manga-lote-tags")) q("#manga-lote-tags").value = "";
              actualizarBadges();
            } else {
              alert("Error: " + (res.error || "No se pudo aplicar"));
            }
          }).catch(function (err) { alert("Error de red: " + err.message); });
      });
    }

    var btnBle = document.getElementById("btn-manga-ble-conectar");
    if (btnBle) {
      btnBle.addEventListener("click", function () {
        var estado = document.getElementById("manga-ble-estado");
        if (!navigator.bluetooth) {
          if (estado) estado.innerHTML = "❌ Tu navegador no soporta Web Bluetooth.<br><small>Recomendado: Chrome o Edge en Android o PC con Bluetooth activo.</small>";
          return;
        }
        if (estado) estado.textContent = "🔍 Buscando báscula o bastón RFID Bluetooth...";
        navigator.bluetooth.requestDevice({
          acceptAllDevices: true,
          optionalServices: ["0000181d-0000-1000-8000-00805f9b34fb", "battery_service"]
        }).then(function (device) {
          if (estado) estado.innerHTML = "🟢 Conectado a <b>" + esc(device.name || "Dispositivo BLE") + "</b>.<br>Listo para recibir lecturas.";
        }).catch(function (err) {
          if (estado) estado.textContent = "Conexión BLE cancelada o no disponible (" + err.message + ").";
        });
      });
    }
  }

  /* ---------- Captura Rápida de Campo (Offline Real) ---------- */
  var _tipoCapturaActual = "parto";
  function renderCaptura() {
    var tipos = [
      { id: "parto", nom: "Parto", ico: "cowCalf" },
      { id: "pesaje", nom: "Pesaje", ico: "scale" },
      { id: "tratamiento", nom: "Tratamiento", ico: "syringe" },
      { id: "traslado", nom: "Traslado", ico: "truck" },
      { id: "celo", nom: "Celo", ico: "flame" },
      { id: "servicio", nom: "Servicio / IA", ico: "sperm" },
      { id: "leche", nom: "Leche", ico: "milk" },
      { id: "muerte", nom: "Muerte / Descarte", ico: "cowSkull" },
      { id: "gasto", nom: "Ingreso / Gasto", ico: "banknote" }
    ];

    var h = "<h3>" + icon("clipboard") + "Captura Rápida de Campo (Online / Offline)</h3>";
    h += "<p class='aviso'>Registra eventos directamente en el potrero. Si estás sin señal, se guardarán en la cola local de tu celular y se sincronizarán al volver a la casa.</p>";

    h += "<div style='display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px;'>";
    tipos.forEach(function (t) {
      var act = t.id === _tipoCapturaActual ? "act" : "";
      h += "<button type='button' class='btn-punto " + act + "' data-cap-tipo='" + t.id + "' style='font-size:13px;'>" + icon(t.ico, 14) + t.nom + "</button>";
    });
    h += "</div>";

    h += "<div class='card' style='padding:16px;'>"
      + "<form id='form-captura' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<div id='captura-campos'></div>"
      + "<button type='submit' id='btn-guardar-captura' class='btn-guardar-manga' style='margin-top:12px;'>" + icon("save", 15) + "Guardar Registro</button>"
      + "</form>"
      + "<div id='captura-feedback' style='margin-top:12px;'></div>"
      + "</div>";

    return h;
  }

  function camposHtmlCaptura(tipo) {
    var hoy = new Date().toISOString().slice(0, 10);
    var h = "<label>Fecha del evento: <input type='date' id='cap-fecha' value='" + hoy + "' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";

    if (tipo === "parto") {
      h += "<label>Arete / Tag de la Madre (Vaca): <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Arete de la Cría (Nuevo): <input id='cap-cria-tag' placeholder='ej. 102 o NM_102' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Sexo de la Cría: <select id='cap-sexo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='HEMBRA'>Hembra</option><option value='MACHO'>Macho</option></select></label></div>"
        + "<div style='flex:1;'><label>Estado Cría: <select id='cap-estado-cria' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='VIVO'>Vivo / Normal</option><option value='MUERTO'>Nacido Muerto</option></select></label></div>"
        + "</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Peso al nacer (kg): <input type='number' step='0.5' id='cap-peso-nacer' placeholder='ej. 32' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Observaciones / Notas: <input id='cap-notas' placeholder='Parto distócico, ternero vigoroso, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "pesaje") {
      h += "<label>Arete / Tag del animal: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Peso (kg): <input type='number' step='0.5' id='cap-peso' placeholder='ej. 430' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Condición Corporal (1-5): <select id='cap-cc' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0'>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0</option></select></label>";
    } else if (tipo === "tratamiento") {
      h += "<label>Arete / Tag: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Producto / Fármaco: <input id='cap-producto' placeholder='ej. Oxitetraciclina 20%' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Dosis: <input id='cap-dosis' placeholder='ej. 20 ml' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Vía: <select id='cap-via' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='IM'>IM (Intramuscular)</option><option value='SC'>SC (Subcutánea)</option><option value='IV'>IV</option><option value='Oral'>Oral</option><option value='Pour-on'>Pour-on</option></select></label></div>"
        + "</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Retiro Leche (días): <input type='number' id='cap-ret-leche' value='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Retiro Carne (días): <input type='number' id='cap-ret-carne' value='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Diagnóstico / Causa: <input id='cap-diag' placeholder='ej. Mastitis clínica cuarto anterior izquierdo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "traslado") {
      h += "<label>Arete / Tag (o Lote): <input id='cap-tag' placeholder='ej. 47 o Todo el lote' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Potrero Origen: <input id='cap-pot-orig' placeholder='ej. Guayabal' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Potrero Destino: <input id='cap-pot-dest' placeholder='ej. Morichal' list='dl-potreros' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Motivo de rotación: <input id='cap-motivo' placeholder='Rotación Voisin, cambio de pastura, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "celo") {
      h += "<label>Arete / Vaca: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Horario Celo: <select id='cap-am-pm' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='AM'>Mañana (AM) — Inseminar en la tarde</option><option value='PM'>Tarde (PM) — Inseminar en la mañana siguiente</option></select></label>"
        + "<label>Observaciones de Celo: <input id='cap-notas' placeholder='Acepta monta, moco cristalino, bramidos' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "servicio") {
      h += "<label>Arete / Vaca: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Tipo de Servicio: <select id='cap-tipo-serv' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='IA'>Inseminación Artificial (I.A.)</option><option value='MN'>Monta Natural</option><option value='IATF'>IATF Protocolo</option></select></label>"
        + "<label>Código Toro / Pajuela: <input id='cap-toro' placeholder='ej. GUZ-01' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Inseminador: <input id='cap-inseminador' placeholder='Nombre del técnico' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "leche") {
      h += "<label>Litros Totales (Ordeño o Quincena): <input type='number' step='0.5' id='cap-litros' placeholder='ej. 1850' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Observaciones / Detalle: <input id='cap-notas' placeholder='ej. Recibo quincena 1-15, control diario, planilla manual, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "muerte") {
      h += "<label>Arete / Tag: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Causa Presunta: <input id='cap-causa' placeholder='ej. Mordedura de serpiente, timpanismo, descarte vejez' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Observaciones: <input id='cap-notas' placeholder='Detalles o destino' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "gasto") {
      h += "<label>Categoría: <select id='cap-fin-categoria' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
        + "<optgroup label='💰 Ingresos'>"
        + "<option value='VENTA_LECHE'>Venta de leche</option>"
        + "<option value='OTRO_INGRESO'>Otro ingreso</option>"
        + "</optgroup>"
        + "<optgroup label='💸 Egresos'>"
        + "<option value='INSUMO' selected>Insumos (sal, alambre, herramienta, etc.)</option>"
        + "<option value='NOMINA'>Nómina / Jornales</option>"
        + "<option value='VETERINARIO'>Veterinario / Medicamentos</option>"
        + "<option value='INFRAESTRUCTURA'>Infraestructura / Mantenimiento</option>"
        + "<option value='COMBUSTIBLE'>Combustible</option>"
        + "<option value='OTRO_EGRESO'>Otro gasto</option>"
        + "</optgroup>"
        + "</select></label>"
        + "<label>Concepto: <input id='cap-fin-concepto' placeholder='ej. Sal mineralizada 40kg, Jornal Andrés' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Monto ($): <input type='number' step='1' min='0' id='cap-fin-monto' placeholder='ej. 180000' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div id='cap-fin-litros-wrap' style='display:none;'><label>Litros vendidos (solo venta de leche): <input type='number' step='0.5' id='cap-fin-litros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<label>Proveedor / Comprador / Trabajador (opcional): <input id='cap-fin-contraparte' placeholder='ej. Agropecuaria X, Andrés' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Arete / Animal relacionado (opcional): <input id='cap-tag' placeholder='ej. N069' list='dl-tags' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Potrero relacionado (opcional): <input id='cap-fin-potrero' placeholder='ej. Olegario' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Notas: <input id='cap-notas' placeholder='Detalles adicionales' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    }

    var hintFoto = "Foto de respaldo en campo";
    var titFoto = "Foto del Evento";
    var txtBtnFoto = " Tomar o Subir Foto";

    if (tipo === "parto") {
      titFoto = "Foto del Parto / Cría";
      hintFoto = "Foto de la cría recién nacida, ubre o condición de la madre";
    } else if (tipo === "muerte") {
      titFoto = "Foto del Hallazgo / Necropsia";
      hintFoto = "Foto del animal fallecido, necropsia o causa de muerte";
    } else if (tipo === "tratamiento") {
      titFoto = "Foto del Medicamento / Receta";
      hintFoto = "Foto del frasco/lote de medicamento, receta o zona tratada";
    } else if (tipo === "pesaje") {
      titFoto = "Foto de Báscula / Animal";
      hintFoto = "Foto del animal en báscula, arete o condición corporal";
    } else if (tipo === "celo") {
      titFoto = "Foto de Manifestación de Celo";
      hintFoto = "Foto de manifestación de celo (moco, monta, comportamiento)";
    } else if (tipo === "servicio") {
      titFoto = "Foto de Pajuela / Procedimiento";
      hintFoto = "Foto de la pajuela, catálogo del toro o procedimiento IA";
    } else if (tipo === "traslado") {
      titFoto = "Foto del Lote / Potrero";
      hintFoto = "Foto del lote o potrero de destino";
    } else if (tipo === "leche") {
      titFoto = "Foto del Recibo / Planilla de Leche";
      hintFoto = "Foto del recibo de quincena o planilla donde anotan la leche diaria";
      txtBtnFoto = " Tomar o Subir Recibo / Hoja";
    } else if (tipo === "gasto") {
      titFoto = "Foto de la Factura / Recibo";
      hintFoto = "Foto de la factura de compra, recibo de pago o comprobante";
      txtBtnFoto = " Tomar o Subir Factura";
    }

    h += "<div class='cap-foto-box' style='margin-top:12px; padding:12px; border:1.5px dashed var(--borde-fuerte); border-radius:8px; background:var(--superficie);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
      + "<div>"
      + "<div style='font-size:12.5px; font-weight:700; display:flex; align-items:center; gap:6px;'>"
      + icon("camera", 15)
      + titFoto + " <span style='font-size:11px; font-weight:normal; color:var(--texto-suave);'>(Opcional)</span>"
      + "</div>"
      + "<small style='font-size:11px; color:var(--texto-suave); display:block; margin-top:2px;'>" + esc(hintFoto) + "</small>"
      + "</div>"
      + "<div style='display:flex; gap:8px; align-items:center;'>"
      + "<input type='file' id='cap-foto-input' accept='image/*' capture='environment' style='display:none;'>"
      + "<button type='button' id='btn-elegir-foto' class='tema-btn' style='font-size:12px; padding:6px 12px; display:inline-flex; align-items:center; gap:6px; cursor:pointer;'>"
      + icon("camera", 13) + txtBtnFoto
      + "</button>"
      + "</div>"
      + "</div>"
      + "<div id='cap-foto-preview-wrap' style='display:none; margin-top:10px; padding-top:10px; border-top:1px solid var(--borde-fuerte); align-items:center; gap:12px;'>"
      + "<img id='cap-foto-preview' src='' alt='Vista previa' style='width:64px; height:64px; object-fit:cover; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
      + "<div style='flex:1; min-width:140px;'>"
      + "<div id='cap-foto-nombre' style='font-size:12px; font-weight:700; word-break:break-all;'>foto.jpg</div>"
      + "<div id='cap-foto-tam' style='font-size:11px; color:var(--texto-suave);'>Optimizada</div>"
      + "</div>"
      + "<button type='button' id='btn-quitar-foto' class='tema-btn' style='color:var(--color-rojo-txt); font-size:11.5px; padding:4px 9px; cursor:pointer;'>" + icon("xmark", 12) + " Quitar</button>"
      + "</div>"
      + "</div>";

    if (tipo === "leche") {
      h += "<div id='box-analizar-recibo-ia' style='display:none; margin-top:14px; padding:14px; border-radius:8px; background:var(--superficie); border:1.5px solid var(--verde-marca); box-shadow:0 2px 6px var(--sombra);'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>"
        + "<div>"
        + "<div style='font-weight:700; font-size:13.5px; color:var(--verde-marca); display:flex; align-items:center; gap:6px;'>"
        + icon("sparkles", 16) + "Digitalización Inteligente de Recibo (IA)"
        + "</div>"
        + "<small style='color:var(--texto-suave); font-size:11.5px; display:block; margin-top:2px;'>Lee automáticamente cada renglón manuscrito, detecta fechas y suma los litros diarios.</small>"
        + "</div>"
        + "<button type='button' id='btn-analizar-recibo-ia' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:700; font-size:12.5px; padding:7px 14px; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:6px;'>"
        + icon("sparkles", 14) + "Leer Recibo con IA"
        + "</button>"
        + "</div>"
        + "<div id='recibo-ia-estado' style='margin-top:10px; font-size:12.5px;'></div>"
        + "<div id='recibo-ia-preview' style='margin-top:12px; display:none;'></div>"
        + "</div>";
    }

    return h;
  }

  function bindCaptura() {
    var cCampos = document.getElementById("captura-campos");
    var _fotoActual = null;

    function bindFotoCaptura() {
      var btnElegir = document.getElementById("btn-elegir-foto");
      var fileInp = document.getElementById("cap-foto-input");
      var preWrap = document.getElementById("cap-foto-preview-wrap");
      var preImg = document.getElementById("cap-foto-preview");
      var preNom = document.getElementById("cap-foto-nombre");
      var preTam = document.getElementById("cap-foto-tam");
      var btnQuitar = document.getElementById("btn-quitar-foto");

      var boxIa = document.getElementById("box-analizar-recibo-ia");
      var estadoIa = document.getElementById("recibo-ia-estado");
      var previewIa = document.getElementById("recibo-ia-preview");
      var btnAnalizarIa = document.getElementById("btn-analizar-recibo-ia");

      if (_fotoActual && _tipoCapturaActual === "leche" && boxIa) {
        boxIa.style.display = "block";
      }

      if (btnElegir && fileInp) {
        btnElegir.addEventListener("click", function () {
          fileInp.click();
        });
      }

      if (btnQuitar) {
        btnQuitar.addEventListener("click", function () {
          _fotoActual = null;
          if (fileInp) fileInp.value = "";
          if (preWrap) preWrap.style.display = "none";
          if (preImg) preImg.src = "";
          if (boxIa) boxIa.style.display = "none";
          if (estadoIa) estadoIa.innerHTML = "";
          if (previewIa) {
            previewIa.style.display = "none";
            previewIa.innerHTML = "";
          }
        });
      }

      if (fileInp) {
        fileInp.addEventListener("change", function () {
          var file = fileInp.files && fileInp.files[0];
          if (!file) return;

          var reader = new FileReader();
          reader.onload = function (ev) {
            var img = new Image();
            img.onload = function () {
              var maxDim = 1200;
              var width = img.width;
              var height = img.height;
              if (width > maxDim || height > maxDim) {
                if (width > height) {
                  height = Math.round((height * maxDim) / width);
                  width = maxDim;
                } else {
                  width = Math.round((width * maxDim) / height);
                  height = maxDim;
                }
              }

              var canvas = document.createElement("canvas");
              canvas.width = width;
              canvas.height = height;
              var ctx = canvas.getContext("2d");
              ctx.drawImage(img, 0, 0, width, height);

              var compressedB64 = canvas.toDataURL("image/jpeg", 0.82);
              var tamKb = Math.round((compressedB64.length * 3) / 4 / 1024);

              _fotoActual = {
                base64: compressedB64,
                nombre: file.name || ("foto_" + _tipoCapturaActual + ".jpg"),
                tam_kb: tamKb
              };

              if (preImg) preImg.src = compressedB64;
              if (preNom) preNom.textContent = _fotoActual.nombre;
              if (preTam) preTam.textContent = "Optimizada (" + tamKb + " KB) · Lista para adjuntar";
              if (preWrap) preWrap.style.display = "flex";

              if (boxIa && _tipoCapturaActual === "leche") {
                boxIa.style.display = "block";
                if (estadoIa) {
                  estadoIa.innerHTML = "<div style='display:flex; align-items:center; gap:8px; padding:6px 10px; background:rgba(47,82,51,0.06); border-radius:6px;'>"
                    + "<span class='chip verde' style='font-size:11px;'>Foto cargada</span>"
                    + "<span style='color:var(--texto-suave); font-size:12px;'>Presiona <b>Leer Recibo con IA</b> para digitalizar los días de ordeño automáticamente.</span>"
                    + "</div>";
                }
                if (previewIa) {
                  previewIa.style.display = "none";
                  previewIa.innerHTML = "";
                }
              }
            };
            img.src = ev.target.result;
          };
          reader.readAsDataURL(file);
        });
      }

      function bindTablaReciboIa(res) {
        function recalcularSuma() {
          var total = 0;
          qa(".inp-ia-litros", previewIa).forEach(function (inp) {
            var val = parseFloat(inp.value);
            if (!isNaN(val) && val > 0) total += val;
          });
          total = Math.round(total * 10) / 10;
          var sumSpan = document.getElementById("ia-suma-total");
          if (sumSpan) sumSpan.textContent = total;
          var fLitros = document.getElementById("cap-litros");
          if (fLitros) fLitros.value = total;
        }

        qa(".inp-ia-litros", previewIa).forEach(function (inp) {
          inp.addEventListener("input", recalcularSuma);
        });

        previewIa.addEventListener("click", function (e) {
          var btnQ = e.target && e.target.closest ? e.target.closest(".btn-ia-quitar-fila") : null;
          if (btnQ) {
            var tr = btnQ.closest("tr");
            if (tr) {
              tr.remove();
              recalcularSuma();
            }
          }
        });

        var btnAgregar = document.getElementById("btn-ia-agregar-dia");
        if (btnAgregar) {
          btnAgregar.addEventListener("click", function () {
            var tbody = previewIa.querySelector("tbody");
            if (!tbody) return;
            var filas = qa("tr.ia-fila-dia", tbody);
            var ultimoDia = filas.length + 1;
            var ultimaFecha = "";
            if (filas.length) {
              var ultInpF = filas[filas.length - 1].querySelector(".inp-ia-fecha");
              if (ultInpF && ultInpF.value) {
                try {
                  var d = new Date(ultInpF.value + "T12:00:00");
                  d.setDate(d.getDate() + 1);
                  ultimaFecha = d.toISOString().slice(0, 10);
                } catch (ex) { /* noop */ }
              }
            }
            if (!ultimaFecha) ultimaFecha = new Date().toISOString().slice(0, 10);

            var tr = document.createElement("tr");
            tr.className = "ia-fila-dia";
            tr.style.borderBottom = "1px solid var(--borde)";
            tr.innerHTML = "<td style='text-align:center; font-weight:bold; font-size:12px; color:var(--texto-suave);'>" + ultimoDia + "</td>"
              + "<td><input type='date' class='inp-ia-fecha' value='" + esc(ultimaFecha) + "' style='width:100%; padding:4px 6px; font-size:12px; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
              + "<td><input type='number' step='0.1' min='0' class='inp-ia-litros' value='0' style='width:100%; padding:4px 6px; font-size:12.5px; font-weight:bold; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
              + "<td><input type='text' class='inp-ia-notas' value='' placeholder='Opcional' style='width:100%; padding:4px 6px; font-size:11.5px; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
              + "<td style='text-align:center;'><button type='button' class='btn-ia-quitar-fila tema-btn' style='padding:2px 6px; font-size:11px; color:var(--color-rojo-txt); cursor:pointer;' title='Eliminar fila'>✕</button></td>";
            tbody.appendChild(tr);
            var nuevoInpL = tr.querySelector(".inp-ia-litros");
            if (nuevoInpL) nuevoInpL.addEventListener("input", recalcularSuma);
            recalcularSuma();
          });
        }

        var btnGuardarQ = document.getElementById("btn-guardar-quincena-ia");
        if (btnGuardarQ) {
          btnGuardarQ.addEventListener("click", function () {
            var filas = qa("tr.ia-fila-dia", previewIa);
            if (!filas.length) {
              alert("No hay días para guardar.");
              return;
            }

            var listaDias = [];
            for (var i = 0; i < filas.length; i++) {
              var tr = filas[i];
              var fInp = tr.querySelector(".inp-ia-fecha");
              var lInp = tr.querySelector(".inp-ia-litros");
              var nInp = tr.querySelector(".inp-ia-notas");

              var fechaVal = fInp ? fInp.value.trim() : "";
              var litVal = lInp ? parseFloat(lInp.value) : 0;
              var notVal = nInp ? nInp.value.trim() : "";

              if (!fechaVal) {
                alert("La fila " + (i + 1) + " no tiene fecha válida.");
                if (fInp) fInp.focus();
                return;
              }
              if (isNaN(litVal) || litVal < 0) {
                alert("La fila " + (i + 1) + " tiene litros inválidos.");
                if (lInp) lInp.focus();
                return;
              }

              listaDias.push({
                dia: i + 1,
                fecha: fechaVal,
                litros: litVal,
                notas: notVal
              });
            }

            btnGuardarQ.disabled = true;
            btnGuardarQ.innerHTML = "⏳ Guardando " + listaDias.length + " días...";

            var payloadGuardar = {
              periodo: res.periodo || "",
              dias: listaDias,
              foto_base64: _fotoActual ? _fotoActual.base64 : null,
              observaciones: (q("#cap-notas") && q("#cap-notas").value) || ""
            };

            fetch("/api/leche/guardar-quincena", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payloadGuardar)
            })
            .then(function (r) {
              if (r.status === 401) { window.location = "/login"; throw new Error("No autorizado"); }
              if (!r.ok) throw new Error("HTTP " + r.status);
              return r.json();
            })
            .then(function (data) {
              btnGuardarQ.disabled = false;
              btnGuardarQ.innerHTML = icon("save", 15) + "Guardar Todos los Días en la Bitácora";

              if (!data.ok) {
                alert("Error al guardar: " + (data.error || "Desconocido"));
                return;
              }

              if (previewIa) previewIa.style.display = "none";
              if (estadoIa) {
                estadoIa.innerHTML = "<div style='padding:12px; background:rgba(47,82,51,0.12); border-left:4px solid var(--verde-marca); border-radius:6px;'>"
                  + "<div style='font-size:14px; font-weight:bold; color:var(--verde-marca);'>🎉 ¡Quincena guardada con éxito!</div>"
                  + "<div style='margin-top:4px; font-size:12.5px;'>Se registraron <b>" + data.guardados + " días</b> con un total de <b>" + data.total_litros + " Litros</b>. La foto quedó archivada como respaldo en el historial.</div>"
                  + "<div style='margin-top:10px; display:flex; gap:8px;'>"
                  + "<button type='button' id='btn-ia-ir-leche' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:bold; padding:6px 12px; font-size:12px; border:none; border-radius:4px; cursor:pointer;'>" + icon("milk", 13) + "Ver en Producción de Leche</button>"
                  + "</div>"
                  + "</div>";

                var btnIrLeche = document.getElementById("btn-ia-ir-leche");
                if (btnIrLeche) {
                  btnIrLeche.addEventListener("click", function () {
                    irAVista("leche");
                    cargar(true);
                    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
                  });
                }
              }

              actualizarBadges();
            })
            .catch(function (err) {
              btnGuardarQ.disabled = false;
              btnGuardarQ.innerHTML = icon("save", 15) + "Reintentar Guardar";
              alert("Error al guardar: " + err.message);
            });
          });
        }
      }

      function renderizarTablaReciboIa(res) {
        var dias = res.dias || [];
        var per = res.periodo || "Quincena detectada";
        var motor = res.motor || "IA";
        var totDetectado = res.total_litros_detectado != null ? Number(res.total_litros_detectado) : null;

        var sumaInicial = 0;
        dias.forEach(function (d) { sumaInicial += (Number(d.litros) || 0); });
        sumaInicial = Math.round(sumaInicial * 10) / 10;

        var fLitros = document.getElementById("cap-litros");
        if (fLitros) fLitros.value = sumaInicial;
        var fNotas = document.getElementById("cap-notas");
        if (fNotas && !fNotas.value) {
          fNotas.value = "Recibo " + per + " (" + dias.length + " días)";
        }

        var hEstado = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;'>"
          + "<div><span class='chip verde'>✓ Lectura Exitosa</span> <b>" + esc(per) + "</b> · " + dias.length + " días leídos</div>"
          + "<div style='font-size:11px; color:var(--texto-suave);'>Motor: " + esc(motor) + "</div>"
          + "</div>";

        if (res.discrepancia_total) {
          hEstado += "<div style='margin-top:6px; padding:6px 10px; background:rgba(217,119,6,0.1); border-left:3px solid #d97706; border-radius:4px; font-size:12px;'>"
            + "⚠️ <b>Discrepancia en la suma:</b> La suma de los días da <b>" + sumaInicial + " L</b> pero en el papel dice <b>" + totDetectado + " L</b>. Por favor revisa los días abajo y ajusta cualquier número si es necesario."
            + "</div>";
        }
        if (estadoIa) estadoIa.innerHTML = hEstado;

        var hTabla = "<div style='background:var(--superficie); border:1px solid var(--borde); border-radius:8px; padding:10px; margin-top:10px;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>"
          + "<h4 style='margin:0; font-size:13px; display:flex; align-items:center; gap:6px;'>" + icon("table", 14) + "Desglose Diario Detectado</h4>"
          + "<button type='button' id='btn-ia-agregar-dia' class='tema-btn' style='font-size:11.5px; padding:3px 8px;'>" + icon("plus", 12) + "Agregar Día</button>"
          + "</div>"
          + "<div class='tabla-scroll' style='max-height:280px; overflow-y:auto;'>"
          + "<table style='width:100%; border-collapse:collapse;' id='tabla-recibo-dias'>"
          + "<thead><tr style='border-bottom:2px solid var(--borde-fuerte); text-align:left;'>"
          + "<th style='width:36px; text-align:center;'>Día</th>"
          + "<th style='min-width:130px;'>Fecha</th>"
          + "<th style='min-width:95px;'>Litros</th>"
          + "<th>Notas</th>"
          + "<th style='width:28px;'></th>"
          + "</tr></thead>"
          + "<tbody>";

        dias.forEach(function (d, idx) {
          var diaNum = d.dia || (idx + 1);
          var fIso = d.fecha || "";
          var lts = d.litros != null ? d.litros : 0;
          var not = d.notas || "";

          hTabla += "<tr class='ia-fila-dia' style='border-bottom:1px solid var(--borde);'>"
            + "<td style='text-align:center; font-weight:bold; font-size:12px; color:var(--texto-suave);'>" + diaNum + "</td>"
            + "<td><input type='date' class='inp-ia-fecha' value='" + esc(fIso) + "' style='width:100%; padding:4px 6px; font-size:12px; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
            + "<td><input type='number' step='0.1' min='0' class='inp-ia-litros' value='" + esc(lts) + "' style='width:100%; padding:4px 6px; font-size:12.5px; font-weight:bold; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
            + "<td><input type='text' class='inp-ia-notas' value='" + esc(not) + "' placeholder='Opcional' style='width:100%; padding:4px 6px; font-size:11.5px; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
            + "<td style='text-align:center;'><button type='button' class='btn-ia-quitar-fila tema-btn' style='padding:2px 6px; font-size:11px; color:var(--color-rojo-txt); cursor:pointer;' title='Eliminar fila'>✕</button></td>"
            + "</tr>";
        });

        hTabla += "</tbody>"
          + "<tfoot>"
          + "<tr style='background:rgba(47,82,51,0.05); font-weight:bold;'>"
          + "<td colspan='2' style='text-align:right; padding:8px;'>Suma Total:</td>"
          + "<td style='padding:8px;'><span id='ia-suma-total' style='color:var(--verde-marca); font-size:14px;'>" + sumaInicial + "</span> L</td>"
          + "<td colspan='2' style='font-size:11px; color:var(--texto-suave); padding:8px;'>" + (totDetectado != null ? ("(Papel: " + totDetectado + " L)") : "") + "</td>"
          + "</tr>"
          + "</tfoot>"
          + "</table></div>"
          + "<button type='button' id='btn-guardar-quincena-ia' class='tema-btn' style='margin-top:12px; width:100%; background:var(--verde-marca); color:#fff; font-weight:bold; font-size:13.5px; padding:10px; border:none; border-radius:6px; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px;'>"
          + icon("save", 15) + "Guardar Todos los Días en la Bitácora"
          + "</button>"
          + "</div>";

        if (previewIa) {
          previewIa.innerHTML = hTabla;
          previewIa.style.display = "block";
          bindTablaReciboIa(res);
        }
      }

      if (btnAnalizarIa) {
        btnAnalizarIa.addEventListener("click", function () {
          if (!_fotoActual || !_fotoActual.base64) {
            alert("Por favor toma o selecciona primero una foto del recibo o planilla.");
            return;
          }
          btnAnalizarIa.disabled = true;
          btnAnalizarIa.innerHTML = "⏳ Analizando...";
          if (estadoIa) {
            estadoIa.innerHTML = "<div style='display:flex; align-items:center; gap:10px; padding:10px; background:rgba(47,82,51,0.06); border-radius:6px;'>"
              + "<span style='font-size:18px;'>⏳</span>"
              + "<div><b style='color:var(--verde-marca);'>Digitalizando recibo con Visión Artificial...</b><br><small style='color:var(--texto-suave);'>Extrayendo días, fechas y litros de las anotaciones manuscritas. Esto toma 5-10 segundos.</small></div>"
              + "</div>";
          }
          if (previewIa) previewIa.style.display = "none";

          var fechaRef = (q("#cap-fecha") && q("#cap-fecha").value) || new Date().toISOString().slice(0, 10);
          fetch("/api/leche/analizar-recibo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              foto_base64: _fotoActual.base64,
              fecha_referencia: fechaRef
            })
          })
          .then(function (r) {
            if (r.status === 401) { window.location = "/login"; throw new Error("No autorizado"); }
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
          })
          .then(function (res) {
            btnAnalizarIa.disabled = false;
            btnAnalizarIa.innerHTML = icon("sparkles", 14) + "Re-analizar Recibo";

            if (!res.ok) {
              if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-rojo-txt);'>❌ <b>Error:</b> " + esc(res.error || "No se pudo procesar el recibo.") + "</div>";
              return;
            }

            if (!res.es_recibo_leche || !res.dias || !res.dias.length) {
              var obs = res.observaciones || "No se detectaron anotaciones numéricas de producción lechera diaria.";
              if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-ambar);'>⚠️ <b>No parece un recibo de leche válido:</b><br><small style='color:var(--texto);'>" + esc(obs) + "</small></div>";
              return;
            }

            renderizarTablaReciboIa(res);
          })
          .catch(function (err) {
            btnAnalizarIa.disabled = false;
            btnAnalizarIa.innerHTML = icon("sparkles", 14) + "Reintentar";
            if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-rojo-txt);'>❌ Error de conexión: " + esc(err.message) + "</div>";
          });
        });
      }
    }

    function bindCamposFinanza() {
      var selCat = document.getElementById("cap-fin-categoria");
      var wrapLitros = document.getElementById("cap-fin-litros-wrap");
      if (!selCat || !wrapLitros) return;
      function toggleLitros() { wrapLitros.style.display = selCat.value === "VENTA_LECHE" ? "block" : "none"; }
      selCat.addEventListener("change", toggleLitros);
      toggleLitros();
    }

    if (cCampos) {
      cCampos.innerHTML = camposHtmlCaptura(_tipoCapturaActual);
      bindFotoCaptura();
      bindCamposFinanza();
    }

    qa("button[data-cap-tipo]").forEach(function (b) {
      b.addEventListener("click", function () {
        qa("button[data-cap-tipo]").forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        _tipoCapturaActual = b.getAttribute("data-cap-tipo");
        _fotoActual = null;
        if (cCampos) {
          cCampos.innerHTML = camposHtmlCaptura(_tipoCapturaActual);
          bindFotoCaptura();
          bindCamposFinanza();
        }
        var fTag = document.getElementById("cap-tag");
        if (fTag) fTag.focus();
      });
    });

    var form = document.getElementById("form-captura");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var fecha = (q("#cap-fecha") && q("#cap-fecha").value) || new Date().toISOString().slice(0, 10);
        var payload = {};

        if (_tipoCapturaActual === "parto") {
          payload.vaca_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.id_cria_tag = (q("#cap-cria-tag") && q("#cap-cria-tag").value || "").trim() || null;
          payload.sexo_cria = (q("#cap-sexo") && q("#cap-sexo").value) || "HEMBRA";
          payload.estado_cria = (q("#cap-estado-cria") && q("#cap-estado-cria").value) || "VIVO";
          payload.peso_nacimiento = parseFloat(q("#cap-peso-nacer") && q("#cap-peso-nacer").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || "";
        } else if (_tipoCapturaActual === "pesaje") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.peso_kg = parseFloat(q("#cap-peso") && q("#cap-peso").value) || null;
          payload.evento = "PESAJE";
        } else if (_tipoCapturaActual === "tratamiento") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.producto = (q("#cap-producto") && q("#cap-producto").value || "").trim();
          payload.dosis = (q("#cap-dosis") && q("#cap-dosis").value) || null;
          payload.via = (q("#cap-via") && q("#cap-via").value) || "IM";
          payload.dias_retiro_leche = parseInt(q("#cap-ret-leche") && q("#cap-ret-leche").value || 0, 10);
          payload.dias_retiro_carne = parseInt(q("#cap-ret-carne") && q("#cap-ret-carne").value || 0, 10);
          payload.diagnostico = (q("#cap-diag") && q("#cap-diag").value) || null;
        } else if (_tipoCapturaActual === "traslado") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.potrero_origen = (q("#cap-pot-orig") && q("#cap-pot-orig").value) || null;
          payload.potrero_destino = (q("#cap-pot-dest") && q("#cap-pot-dest").value || "").trim();
          payload.motivo = (q("#cap-motivo") && q("#cap-motivo").value) || null;
        } else if (_tipoCapturaActual === "celo") {
          payload.vaca_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.am_pm = (q("#cap-am-pm") && q("#cap-am-pm").value) || "AM";
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        } else if (_tipoCapturaActual === "servicio") {
          payload.vaca_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.tipo_servicio = (q("#cap-tipo-serv") && q("#cap-tipo-serv").value) || "IA";
          payload.toro_pajilla = (q("#cap-toro") && q("#cap-toro").value) || null;
          payload.inseminador = (q("#cap-inseminador") && q("#cap-inseminador").value) || null;
        } else if (_tipoCapturaActual === "leche") {
          payload.litros = parseFloat(q("#cap-litros") && q("#cap-litros").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        } else if (_tipoCapturaActual === "muerte") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.causa_presunta = (q("#cap-causa") && q("#cap-causa").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        } else if (_tipoCapturaActual === "gasto") {
          var finCategoria = (q("#cap-fin-categoria") && q("#cap-fin-categoria").value) || "OTRO_EGRESO";
          var CATEGORIAS_INGRESO = ["VENTA_LECHE", "OTRO_INGRESO"];
          payload.categoria = finCategoria;
          payload.tipo_finanza = CATEGORIAS_INGRESO.indexOf(finCategoria) !== -1 ? "INGRESO" : "EGRESO";
          payload.concepto = (q("#cap-fin-concepto") && q("#cap-fin-concepto").value || "").trim();
          payload.monto = parseFloat(q("#cap-fin-monto") && q("#cap-fin-monto").value) || 0;
          payload.litros = parseFloat(q("#cap-fin-litros") && q("#cap-fin-litros").value) || null;
          payload.contraparte = (q("#cap-fin-contraparte") && q("#cap-fin-contraparte").value) || null;
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim() || null;
          payload.potrero = (q("#cap-fin-potrero") && q("#cap-fin-potrero").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        }

        // Adjuntar foto opcional
        if (_fotoActual && _fotoActual.base64) {
          payload.foto_base64 = _fotoActual.base64;
          payload.foto_nombre = _fotoActual.nombre;
        }

        var feed = document.getElementById("captura-feedback");

        function mostrarExito(online) {
          enviarTelemetriaSilenciosa("captura_" + _tipoCapturaActual);
          var fotoTxt = payload.foto_base64 ? " 📸 (con foto adjunta)" : "";
          if (feed) {
            feed.innerHTML = "<div class='chip " + (online ? "verde" : "ambar") + "' style='font-size:14px; padding:8px 12px;'>"
              + (online ? "✅ Evento" + fotoTxt + " registrado en el servidor." : "💾 Evento" + fotoTxt + " guardado en cola local offline (se enviará al volver la señal).") + "</div>";
          }
          _fotoActual = null;
          form.reset();
          if (cCampos) {
            cCampos.innerHTML = camposHtmlCaptura(_tipoCapturaActual);
            bindFotoCaptura();
            bindCamposFinanza();
          }
          actualizarBadges();
        }

        if (navigator.onLine === false) {
          encolarOffline(_tipoCapturaActual, payload, fecha).then(function () {
            mostrarExito(false);
          });
          return;
        }

        fetch("/api/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ eventos: [{ tipo: _tipoCapturaActual, payload: payload, fecha: fecha }] })
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok && res.procesados > 0) mostrarExito(true);
            else {
              encolarOffline(_tipoCapturaActual, payload, fecha).then(function () { mostrarExito(false); });
            }
          }).catch(function () {
            encolarOffline(_tipoCapturaActual, payload, fecha).then(function () { mostrarExito(false); });
          });
      });
    }
  }

  /* ---------- Sección de Ayuda & Guía Operativa ---------- */
  var _tabAyudaInstalar = "android";
  function renderAyuda() {
    var h = "<h3>" + icon("help") + "Centro de Ayuda & Guía de Uso</h3>";
    h += "<p class='aviso'>Aprende a instalar la aplicación en tu celular, operar en el potrero sin internet, registrar pesajes continuos y aprovechar la Inteligencia Artificial de la bitácora.</p>";

    h += "<div class='ayuda-grid'>";

    // Tarjeta 1: Instalación de la App
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("download", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>📲 Cómo Instalar la App en tu Celular o PC</h4>"
      + "<small style='color:var(--texto-suave);'>Instálala como aplicación nativa, pantalla completa y sin barra de navegador</small>"
      + "</div>"
      + "</div>"
      + "<div class='ayuda-tabs-row' style='margin-top:12px;'>"
      + "<button type='button' class='btn-punto " + (_tabAyudaInstalar === "android" ? "act" : "") + "' data-ayuda-tab='android' style='font-size:12px; padding:6px 12px;'>Android (Chrome)</button>"
      + "<button type='button' class='btn-punto " + (_tabAyudaInstalar === "ios" ? "act" : "") + "' data-ayuda-tab='ios' style='font-size:12px; padding:6px 12px;'>iPhone / iPad (iOS)</button>"
      + "<button type='button' class='btn-punto " + (_tabAyudaInstalar === "pc" ? "act" : "") + "' data-ayuda-tab='pc' style='font-size:12px; padding:6px 12px;'>Computador (Chrome/Edge)</button>"
      + "</div>"
      + "<div id='ayuda-tab-cuerpo' style='margin-top:10px; font-size:13px; line-height:1.5;'>";

    if (_tabAyudaInstalar === "android") {
      h += "<p><b>En tu teléfono o tablet Android:</b></p>"
        + "<ol style='padding-left:18px; margin:6px 0;'>"
        + "<li>Toca el botón verde <b>'Instalar App'</b> en la barra superior o usa el botón de abajo.</li>"
        + "<li>Si no aparece, abre el menú de tres puntos (<b>⋮</b>) arriba a la derecha en Chrome.</li>"
        + "<li>Selecciona <b>'Instalar aplicación'</b> o <b>'Agregar a la pantalla principal'</b>.</li>"
        + "<li>Confirma en <b>'Instalar'</b>. ¡Listo! Se creará el icono de <i>Bitácora JA</i> junto a tus demás aplicaciones.</li>"
        + "</ol>"
        + "<div style='margin-top:10px;'><button type='button' id='btn-ayuda-disparar-instalar' class='tema-btn' style='background:var(--color-verde-btn, #2e7d32); color:#fff; font-weight:bold; font-size:13px; padding:8px 14px; border-radius:6px; cursor:pointer;'>" + icon("download", 15) + "Instalar Bitácora Ganadera Ahora</button></div>";
    } else if (_tabAyudaInstalar === "ios") {
      h += "<p><b>En iPhone o iPad (usando Safari):</b></p>"
        + "<ol style='padding-left:18px; margin:6px 0;'>"
        + "<li>Abre <b>Safari</b> e ingresa a <code>https://ganaderiaja.duckdns.org/</code>.</li>"
        + "<li>Toca el botón <b>Compartir</b> (el icono de un cuadro con una flecha hacia arriba <b>⎋</b> en la barra inferior de Safari).</li>"
        + "<li>Desplaza hacia abajo en la lista y toca <b>'Agregar al inicio'</b> (o <i>'Add to Home Screen'</i> <b>+</b>).</li>"
        + "<li>Toca <b>'Agregar'</b> arriba a la derecha. La app se abrirá sin barras ni pestañas de navegador, como app nativa.</li>"
        + "</ol>";
    } else {
      h += "<p><b>En Windows, Mac o Linux (Chrome / Edge):</b></p>"
        + "<ol style='padding-left:18px; margin:6px 0;'>"
        + "<li>En la barra de direcciones de tu navegador, haz clic en el icono de instalación <b>(+)</b> o monitor con flecha.</li>"
        + "<li>O abre el menú (<b>⋮</b> o <b>…</b>) y selecciona <b>'Instalar Bitácora Ganadera JA'</b>.</li>"
        + "<li>Se abrirá en su propia ventana independiente con acceso directo en tu escritorio.</li>"
        + "</ol>";
    }

    h += "</div></div>";

    // Tarjeta 2: Modo Offline Real
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("cloud", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>📶 Modo Offline Real (Sin Cobertura Celular)</h4>"
      + "<small style='color:var(--texto-suave);'>Trabaja con total confianza en el potrero o la manga</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>La Bitácora está equipada con tecnología <b>PWA Offline Real</b>:</p>"
      + "<ul style='padding-left:18px; margin:6px 0;'>"
      + "<li><b>Guardado local inmediato:</b> Todos los pesajes, partos, celos, traslados y drogas aplicadas se guardan en tu celular mediante <i>IndexedDB</i>, aunque estés en modo avión o sin señal.</li>"
      + "<li><b>Indicador de estado:</b> El icono de nube en la barra superior muestra el estado de la conexión y la cantidad de registros pendientes por subir.</li>"
      + "<li><b>Sincronización automática:</b> Al regresar a la casa de la finca o recuperar datos móviles, la app envía automáticamente todos los registros acumulados al servidor sin perder nada.</li>"
      + "</ul>"
      + "</div></div>";

    // Tarjeta 3: Manga y Pesaje Continuo
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("scale", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>⚖️ Trabajo en Manga & Pesaje Continuo</h4>"
      + "<small style='color:var(--texto-suave);'>Flujo rápido para jornadas de pesaje de hato completo</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>Diseñado para no frenar el paso de los animales en el corral:</p>"
      + "<ol style='padding-left:18px; margin:6px 0;'>"
      + "<li>Entra en la pestaña <b>'Manga'</b>.</li>"
      + "<li>Escribe el arete/tag (o léelo por RFID/código de barras) y digita el peso en kg.</li>"
      + "<li>Pulsa <b>Enter</b> o 'Guardar Pesaje'. Al instante verás la <b>GMD (Ganancia Media Diaria)</b> calculada contra el pesaje anterior del animal.</li>"
      + "<li>El cursor vuelve automáticamente al campo de arete listo para el siguiente animal de la manga.</li>"
      + "<li>También puedes registrar tratamientos grupales (desparasitante, vacunas, vitaminas) aplicados a toda la jornada.</li>"
      + "</ol>"
      + "</div></div>";

    // Tarjeta 4: Captura Rápida & Fotos
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("camera", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>📸 Captura Rápida & Respaldo Fotográfico</h4>"
      + "<small style='color:var(--texto-suave);'>Eventos zootécnicos con foto de evidencia opcional</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>En la pestaña <b>'Captura'</b> tienes botones directos para cada evento:</p>"
      + "<ul style='padding-left:18px; margin:6px 0;'>"
      + "<li><b>" + icon("cowCalf", 14) + "Partos:</b> Registra arete de la madre, nuevo arete de la cría, sexo, peso al nacer y foto del ternero.</li>"
      + "<li><b>" + icon("syringe", 14) + "Tratamientos:</b> Producto, dosis, vía y control automático de días de retiro para leche y carne.</li>"
      + "<li><b>" + icon("cowSkull", 14) + "Muerte / Descarte:</b> Causa presunta, notas de necropsia y foto de respaldo.</li>"
      + "<li><b>" + icon("flame", 14) + "Celo / " + icon("sperm", 14) + "Servicio IA:</b> Horario AM-PM, código de pajuela/toro e inseminador.</li>"
      + "<li><b>Fotos ligeras:</b> Las fotos tomadas se optimizan automáticamente a menos de 150 KB para no consumir memoria ni datos en campo.</li>"
      + "</ul>"
      + "</div></div>";

    // Tarjeta 5: Dictado por Voz (Whisper)
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("mic", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>🎙️ Dictado por Voz con Inteligencia Artificial</h4>"
      + "<small style='color:var(--texto-suave);'>Registra novedades hablando naturalmente mientras caminas</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>Si tienes las manos ocupadas en el corral:</p>"
      + "<ol style='padding-left:18px; margin:6px 0;'>"
      + "<li>Entra en la pestaña <b>'Voz'</b> y presiona el micrófono.</li>"
      + "<li>Habla claro, por ejemplo: <i>'Ayer parió la vaca 47 ternero macho vivo de 34 kilos'</i> o <i>'Pesé la novilla 102 con 380 kilos'</i>.</li>"
      + "<li>El motor de transcripción e IA zootécnica estructurará el registro automáticamente para que solo confirmes con un toque.</li>"
      + "</ol>"
      + "</div></div>";

    // Tarjeta 6: Asistente IA & Preguntas Frecuentes
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("chat", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>🤖 Asistente Zootécnico IA & Chat</h4>"
      + "<small style='color:var(--texto-suave);'>Pregunta sobre tus animales o sobre el funcionamiento de la app</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>Toca el botón flotante verde <b>🤖</b> abajo a la derecha en cualquier momento:</p>"
      + "<ul style='padding-left:18px; margin:6px 0;'>"
      + "<li><b>Preguntas de hato:</b> <i>'¿Cuántas vacas activas hay en Guayabal?'</i>, <i>'¿Quiénes están en retiro de leche?'</i>, <i>'Ficha del toro GUZ-01'</i>.</li>"
      + "<li><b>Preguntas de la aplicación:</b> <i>'¿Cómo instalo la app?'</i>, <i>'¿Cómo funciona sin internet?'</i>, <i>'¿Cómo peso en la manga?'</i>.</li>"
      + "<li>El asistente responderá de inmediato con datos en vivo o explicaciones paso a paso.</li>"
      + "</ul>"
      + "</div></div>";

    h += "</div>"; // fin ayuda-grid
    return h;
  }

  function bindAyuda() {
    var tabs = qa("button[data-ayuda-tab]");
    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        _tabAyudaInstalar = btn.getAttribute("data-ayuda-tab") || "android";
        var vistaEl = document.getElementById("vista");
        if (vistaEl) {
          montarVista(vistaEl, renderAyuda(), false);
          bindAyuda();
        }
      });
    });

    var btnInstalar = document.getElementById("btn-ayuda-disparar-instalar");
    if (btnInstalar) {
      btnInstalar.addEventListener("click", function () {
        var topBtn = document.getElementById("btn-instalar-app");
        if (topBtn && topBtn.style.display !== "none") {
          topBtn.click();
        } else if (window.__pwaInstallPrompt) {
          window.__pwaInstallPrompt.prompt();
        } else {
          alert("Para instalar en Android: abre el menú ⋮ de Chrome y selecciona 'Instalar aplicación' o 'Agregar a la pantalla principal'.");
        }
      });
    }
  }

  /* ---------- GPS Potrero & Rondas de Campo ---------- */
  var _gpsUltimaPos = null;
  /* ---------- Telemetría Silenciosa GPS en Segundo Plano ---------- */
  function enviarTelemetriaSilenciosa(evento) {
    if (!navigator.geolocation) return;
    try {
      navigator.geolocation.getCurrentPosition(function (pos) {
        var lat = pos.coords.latitude;
        var lon = pos.coords.longitude;
        var acc = pos.coords.accuracy ? Math.round(pos.coords.accuracy) : null;
        var ahora = new Date();
        var horaStr = ahora.toTimeString().split(" ")[0];
        var fechaStr = ahora.toISOString().slice(0, 10);
        var payload = {
          lat: lat,
          lon: lon,
          precision_m: acc,
          evento_origen: evento || "interaccion_app",
          fecha: fechaStr,
          hora: horaStr
        };

        if (navigator.onLine === false) {
          encolarOffline("telemetria_ping", payload).catch(function () {});
          return;
        }

        fetch("/api/telemetria/ping", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }).catch(function () {
          encolarOffline("telemetria_ping", payload).catch(function () {});
        });
      }, function (err) {
        // Silencioso: no molestar al operario si no hay señal de satélite o está desactivado
      }, {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000
      });
    } catch (e) {
      // Ignorar de forma silenciosa
    }
  }

  var _fechaFiltroRutas = null;
  var _gpsUltimoPotrero = null;
  var _puntoRondaSeleccionado = "saladero";
  var _gpsUltimaPos = null;

  function renderGps(d, fFecha) {
    fFecha = fFecha || _fechaFiltroRutas || new Date().toISOString().slice(0, 10);
    var rutas = (d && d.rutas) || [];
    var rondas = (d && d.rondas) || [];

    var h = "<h3>" + icon("pin", 20) + "Auditoría de Rutas y Telemetría de Campo (Solo OWNER)</h3>"
      + "<p class='aviso'>Monitoreo cronológico y automático de los desplazamientos de operarios en la finca. Identifica qué potreros visitaron, hora de entrada, permanencia y cobertura satelital.</p>";

    // Barra de control de fecha
    h += "<div class='card' style='padding:12px; margin-bottom:14px; display:flex; flex-wrap:wrap; gap:10px; align-items:center;'>"
      + "<label style='font-size:13px; font-weight:600; color:var(--texto-suave); display:flex; align-items:center; gap:6px;'>"
      + icon("calendar", 15) + "Fecha a Auditar: "
      + "<input type='date' id='filtro-fecha-rutas' value='" + esc(fFecha) + "' style='padding:6px 10px; border-radius:6px; border:1px solid var(--borde); font-size:13px;'>"
      + "</label>"
      + "<button type='button' id='btn-refrescar-rutas' class='tema-btn' style='font-size:13px; padding:6px 14px;'>" + icon("search", 14) + "Consultar Rutas</button>"
      + "<button type='button' id='btn-ping-manual-gps' class='chip azul' style='font-size:13px; cursor:pointer;'>" + icon("pin", 14) + "Probar Mi GPS Ahora</button>"
      + "</div>";

    // Resumen de rutas por operario
    h += "<div style='display:flex; justify-content:space-between; align-items:center; margin-top:16px; margin-bottom:10px;'>"
      + "<h4>" + icon("walk", 16) + "Desplazamientos y Recorridos Detectados (" + rutas.length + ")</h4>"
      + (rutas.length ? "<button type='button' id='btn-exportar-rutas-csv' class='tema-btn' style='font-size:12px; padding:4px 10px;'>" + icon("download", 14) + "Exportar Rutas CSV</button>" : "")
      + "</div>";

    if (!rutas.length) {
      h += vacio("No hay desplazamientos registrados para la fecha " + fechaCorta(fFecha) + ". Los puntos se capturan automáticamente en segundo plano cuando el operario interactúa con la aplicación en campo.");
    } else {
      rutas.forEach(function (r, idx) {
        var rolBadge = r.rol === "OWNER" ? "rojo" : (r.rol === "ADMIN" ? "ambar" : "verde");
        h += "<div class='card-operario-ruta'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;'>"
          + "<div><b style='font-size:16px;'>" + esc(r.usuario_nombre) + "</b> <span class='chip " + rolBadge + "' style='font-size:11px;'>" + esc(r.rol) + "</span></div>"
          + "<div style='font-size:12.5px; color:var(--texto-suave);'>"
          + "🕒 Horario: <b>" + esc(r.hora_inicio || "—") + "</b> a <b>" + esc(r.hora_fin || "—") + "</b> · 📍 <b>" + r.total_puntos + " puntos GPS</b>"
          + "</div>"
          + "</div>";

        // Secuencia cronológica de potreros
        h += "<div style='font-size:12px; font-weight:600; color:var(--texto-suave); margin-bottom:4px;'>LÍNEA DE TIEMPO DE POTREROS VISITADOS:</div>";
        h += "<div class='timeline-rutas'>";
        if (!r.secuencia_potreros || !r.secuencia_potreros.length) {
          h += "<span style='font-size:12px; color:var(--texto-suave);'>Sin visitas a potreros registradas</span>";
        } else {
          r.secuencia_potreros.forEach(function (s, sIdx) {
            if (sIdx > 0) h += "<span class='chip-flecha'>➔</span>";
            h += "<span class='chip-ruta'>" + icon("pin", 12) + "<b>" + esc(s.hora) + "</b> 🌾 " + esc(s.potrero) + "</span>";
          });
        }
        h += "</div>";

        // Detalle colapsable de puntos exactos
        var tablaId = "tabla-pts-" + idx;
        h += "<details style='margin-top:10px; font-size:13px;'>"
          + "<summary style='cursor:pointer; font-weight:600; color:var(--verde-marca); padding:4px 0;'>🔍 Ver desglose de coordenadas (" + (r.puntos ? r.puntos.length : 0) + " registros)</summary>"
          + "<div class='tabla-scroll' style='margin-top:8px;'>"
          + "<table id='" + tablaId + "'><tr><th>Hora</th><th>Potrero</th><th>Latitud</th><th>Longitud</th><th>Precisión</th><th>Evento</th><th>Google Maps</th></tr>";

        (r.puntos || []).forEach(function (pt) {
          var mapsUrl = "https://maps.google.com/?q=" + pt.lat + "," + pt.lon;
          var origen = pt.evento_origen || "interaccion";
          h += "<tr>"
            + "<td><b>" + esc(pt.hora) + "</b></td>"
            + "<td><b>" + esc(pt.potrero_nombre || "Área Externa") + "</b></td>"
            + "<td>" + Number(pt.lat).toFixed(6) + "</td>"
            + "<td>" + Number(pt.lon).toFixed(6) + "</td>"
            + "<td>±" + (pt.precision_m ? Math.round(pt.precision_m) + " m" : "—") + "</td>"
            + "<td><span class='chip gris' style='font-size:11px;'>" + esc(origen) + "</span></td>"
            + "<td><a href='" + esc(mapsUrl) + "' target='_blank' rel='noopener' class='chip azul' style='font-size:11px; text-decoration:none;'>🗺️ Abrir Mapa</a></td>"
            + "</tr>";
        });
        h += "</table></div></details>";

        h += "</div>";
      });
    }

    // Sección de Rondas de Campo Manuales
    h += "<div class='card' style='margin-top:20px; padding:16px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>"
      + "<h4>" + icon("calendar", 16) + "Puntos de Ronda Manuales (" + rondas.length + ")</h4>"
      + (rondas.length ? "<button type='button' id='btn-exportar-rondas-csv' class='tema-btn' style='font-size:12px; padding:4px 10px;'>" + icon("download", 14) + "Exportar Rondas CSV</button>" : "")
      + "</div>";

    if (!rondas.length) {
      h += vacio("No hay rondas manuales registradas en esta fecha.");
    } else {
      h += "<div class='tabla-scroll'><table id='tabla-rondas'><tr><th>Hora</th><th>Potrero</th><th>Punto</th><th>Usuario</th><th>Notas</th></tr>";
      rondas.forEach(function (r) {
        h += "<tr><td><b>" + esc(r.hora || fechaCorta(r.fecha)) + "</b></td>"
          + "<td><b>" + esc(r.potrero_nombre || "—") + "</b></td>"
          + "<td><span class='chip verde'>" + esc(r.punto_control || "recorrido") + "</span></td>"
          + "<td>" + esc(r.usuario_nombre || "—") + "</td>"
          + "<td>" + esc(r.notas || "—") + "</td></tr>";
      });
      h += "</table></div>";
    }
    h += "</div>";

    return h;
  }

  function bindGps(d, fFecha) {
    fFecha = fFecha || _fechaFiltroRutas || new Date().toISOString().slice(0, 10);

    var btnRefrescar = document.getElementById("btn-refrescar-rutas");
    var inpFecha = document.getElementById("filtro-fecha-rutas");
    if (btnRefrescar && inpFecha) {
      btnRefrescar.addEventListener("click", function () {
        _fechaFiltroRutas = inpFecha.value;
        cargar(true);
      });
      inpFecha.addEventListener("change", function () {
        _fechaFiltroRutas = inpFecha.value;
        cargar(true);
      });
    }

    var btnPing = document.getElementById("btn-ping-manual-gps");
    if (btnPing) {
      btnPing.addEventListener("click", function () {
        if (!navigator.geolocation) {
          alert("Geolocalización no disponible en este dispositivo.");
          return;
        }
        btnPing.textContent = "📡 Obteniendo GPS...";
        navigator.geolocation.getCurrentPosition(function (pos) {
          var lat = pos.coords.latitude;
          var lon = pos.coords.longitude;
          var acc = Math.round(pos.coords.accuracy || 0);
          fetch("/api/telemetria/ping", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              lat: lat,
              lon: lon,
              precision_m: acc,
              evento_origen: "prueba_manual_owner"
            })
          }).then(function (r) { return r.json(); })
            .then(function (res) {
              btnPing.textContent = "✅ Posición Registrada";
              setTimeout(function () { cargar(false); }, 700);
            }).catch(function (err) {
              btnPing.textContent = "❌ Error: " + err.message;
            });
        }, function (err) {
          btnPing.textContent = "❌ " + err.message;
        }, { enableHighAccuracy: true, timeout: 10000 });
      });
    }

    var btnCsvRutas = document.getElementById("btn-exportar-rutas-csv");
    if (btnCsvRutas) {
      btnCsvRutas.addEventListener("click", function () {
        var lineas = [["Usuario", "Rol", "Fecha", "Hora", "Potrero", "Latitud", "Longitud", "Precision_m", "Evento_Origen"]];
        (d.rutas || []).forEach(function (r) {
          (r.puntos || []).forEach(function (p) {
            lineas.push([
              r.usuario_nombre || "",
              r.rol || "",
              p.fecha || fFecha,
              p.hora || "",
              p.potrero_nombre || "Área Externa",
              p.lat || "",
              p.lon || "",
              p.precision_m != null ? p.precision_m : "",
              p.evento_origen || ""
            ]);
          });
        });
        var csvContent = "\uFEFF" + lineas.map(function (row) {
          return row.map(function (val) {
            return '"' + String(val).replace(/"/g, '""') + '"';
          }).join(";");
        }).join("\r\n");
        var blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "rutas_telemetria_ja_" + fFecha + ".csv";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }

    var btnCsvRondas = document.getElementById("btn-exportar-rondas-csv");
    if (btnCsvRondas) {
      btnCsvRondas.addEventListener("click", function () {
        exportarTablaCSV("rondas_campo_" + fFecha, "#tabla-rondas");
      });
    }
  }


  /* ---------- Sistema & Servidor VPS (Solo OWNER) ---------- */
  function renderSistema(d) {
    var vps = d.vps || {};
    var db = d.db || {};

    var h = "<h3>" + icon("settings", 20) + "Servidor VPS & Sistema Ganadería JA</h3>"
      + "<p class='aviso'>Panel de control ejecutivo y métricas de infraestructura en vivo. Acceso restringido al Propietario (OWNER).</p>";

    var ramTxt = (vps.ram_pct != null && vps.ram_pct !== "") ? vps.ram_pct + "%" : "—";
    var ramSub = (vps.ram_total_mb) ? "RAM (" + (vps.ram_used_mb || 0) + "/" + vps.ram_total_mb + " MB)" : "RAM VPS";
    var ramClase = vps.ram_pct >= 85 ? "alerta" : (vps.ram_pct > 0 ? "ok" : "");

    var diskTxt = (vps.disk_pct != null && vps.disk_pct !== "") ? vps.disk_pct + "%" : "—";
    var diskSub = (vps.disk_total_gb) ? "Disco (" + (vps.disk_used_gb || 0) + "/" + vps.disk_total_gb + " GB)" : "Disco VPS";
    var diskClase = vps.disk_pct >= 85 ? "alerta" : (vps.disk_pct > 0 ? "ok" : "");

    var syncUlt = (d.sync_sg && d.sync_sg.ultimo) ? d.sync_sg.ultimo : null;
    var kpiSyncTxt = syncUlt ? esc(syncUlt.tiempo_relativo || "Reciente") : "Sin Sync";
    var kpiSyncSub = syncUlt ? esc(syncUlt.archivo || "Software Ganadero") : "Backup SG";
    var kpiSyncCls = (syncUlt && syncUlt.al_dia) ? "ok" : (syncUlt ? "alerta" : "");

    h += "<div class='kpis'>"
      + kpi(kpiSyncTxt, kpiSyncSub, kpiSyncCls)
      + kpi(ramTxt, ramSub, ramClase)
      + kpi(diskTxt, diskSub, diskClase)
      + kpi((db.tam_mb != null ? db.tam_mb + " MB" : "—"), "Base SQLite")
      + kpi((db.activos != null ? String(db.activos) : "—"), "Hato Activo", "ok")
      + (d.en_linea_count !== undefined ? kpi(String(d.en_linea_count), "Usuarios en Línea", d.en_linea_count > 0 ? "ok" : "") : "")
      + "</div>";

    // 1. Sincronización Software Ganadero (SG)
    var syncHist = (d.sync_sg && d.sync_sg.historial) ? d.sync_sg.historial : [];
    h += "<div style='background:var(--superficie); border:1px solid var(--borde-fuerte); border-radius:10px; padding:16px; margin:20px 0;'>";
    h += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>";
    h += "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("refresh", 16) + "Sincronización con Software Ganadero (SG)</h4>";
    if (syncUlt) {
      var badgeCls = syncUlt.al_dia ? "chip verde" : "chip amarillo";
      var badgeTxt = syncUlt.al_dia ? "✅ Al día (" + esc(syncUlt.tiempo_relativo) + ")" : "⚠️ Requiere actualización (" + esc(syncUlt.tiempo_relativo) + ")";
      h += "<span class='" + badgeCls + "'>" + badgeTxt + "</span>";
    } else {
      h += "<span class='chip gris'>Sin sincronizaciones registradas</span>";
    }
    h += "</div>";

    if (syncUlt) {
      h += "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-bottom:14px; background:var(--tarjeta-bg); padding:12px; border-radius:8px; border:1px solid var(--borde);'>";
      h += "<div><span style='color:var(--texto-suave); font-size:11px; display:block;'>📦 Último Backup Procesado</span><b style='font-family:var(--font-mono); font-size:13px;'>" + esc(syncUlt.archivo || "backup.zip") + "</b></div>";
      h += "<div><span style='color:var(--texto-suave); font-size:11px; display:block;'>📅 Fecha de Importación</span><b style='font-size:13px;'>" + esc(syncUlt.fecha_iso ? syncUlt.fecha_iso.replace("T", " ") : "—") + "</b></div>";
      h += "<div><span style='color:var(--texto-suave); font-size:11px; display:block;'>✨ Registros Nuevos</span><b style='color:var(--color-verde-txt); font-size:13px;'>+" + esc(String(syncUlt.nuevos || 0)) + " incorporados</b></div>";
      h += "<div><span style='color:var(--texto-suave); font-size:11px; display:block;'>🔄 Registros Existentes</span><b style='color:var(--texto); font-size:13px;'>" + esc(String(syncUlt.duplicados || 0)) + " verificados (idempotentes)</b></div>";
      h += "</div>";

      if (syncHist.length > 1) {
        h += "<div style='margin-top:10px;'><span style='font-size:12px; font-weight:600; color:var(--texto-suave); display:block; margin-bottom:6px;'>📜 Historial Reciente de Backups SG:</span>";
        h += "<div class='tabla-scroll'><table style='width:100%; font-size:11.5px; border-collapse:collapse;'>";
        h += "<tr style='border-bottom:1px solid var(--borde); text-align:left; color:var(--texto-suave);'><th style='padding:5px 8px;'>Fecha</th><th style='padding:5px 8px;'>Archivo</th><th style='padding:5px 8px; text-align:center;'>Nuevos</th><th style='padding:5px 8px; text-align:center;'>Existentes</th><th style='padding:5px 8px; text-align:center;'>Estado</th></tr>";
        syncHist.slice(0, 5).forEach(function (sh) {
          h += "<tr style='border-bottom:1px solid var(--borde);'>";
          h += "<td style='padding:5px 8px;'>" + esc(sh.fecha_iso ? sh.fecha_iso.replace("T", " ") : "—") + "</td>";
          h += "<td style='padding:5px 8px;'><code style='font-size:11px;'>" + esc(sh.archivo || "—") + "</code></td>";
          h += "<td style='padding:5px 8px; text-align:center; color:var(--color-verde-txt); font-weight:600;'>+" + esc(String(sh.nuevos || 0)) + "</td>";
          h += "<td style='padding:5px 8px; text-align:center; color:var(--texto-suave);'>" + esc(String(sh.duplicados || 0)) + "</td>";
          h += "<td style='padding:5px 8px; text-align:center;'><span class='chip verde' style='font-size:10px; padding:2px 6px;'>Exitoso</span></td>";
          h += "</tr>";
        });
        h += "</table></div></div>";
      }
    } else {
      h += "<p style='color:var(--texto-suave); font-size:12px; margin:6px 0;'>Aún no se registran importaciones de Software Ganadero en la base de datos.</p>";
    }
    h += "<p style='font-size:11px; color:var(--texto-suave); margin:8px 0 0 0;'>💡 <i>Los backups se sincronizan en segundo plano vía carpeta COPIAS o en Telegram enviando el .Zip con /confirmar_importar. Las notas de campo capturadas por los trabajadores nunca se borran.</i></p>";
    h += "</div>";

    // 2. Bitácora de Actividad Reciente de los Demás Usuarios
    var actList = d.actividad_reciente || [];
    h += "<div style='background:var(--superficie); border:1px solid var(--borde-fuerte); border-radius:10px; padding:16px; margin:20px 0;'>";
    h += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>";
    h += "<div><h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("clipboard", 16) + "Actividad de Campo & Auditoría de Usuarios</h4>";
    h += "<span style='font-size:11.5px; color:var(--texto-suave);'>Registro en vivo de lo que anotaron mayordomos, administradores y personal de corral</span></div>";
    h += "<div style='display:flex; gap:6px; align-items:center; flex-wrap:wrap;'>";
    h += "<button type='button' class='btn-filtro-act act tema-btn' data-f='todos' style='font-size:11px; padding:3px 8px;'>🌐 Todos</button>";
    h += "<button type='button' class='btn-filtro-act tema-btn' data-f='campo' style='font-size:11px; padding:3px 8px;'>🤠 Campo / Mayordomos</button>";
    h += "<button type='button' class='btn-filtro-act tema-btn' data-f='admin' style='font-size:11px; padding:3px 8px;'>🛡️ Administradores</button>";
    h += "<button type='button' class='btn-filtro-act tema-btn' data-f='sg' style='font-size:11px; padding:3px 8px;'>📁 Software Ganadero</button>";
    h += "</div></div>";

    if (actList.length) {
      h += "<div class='tabla-scroll' style='max-height:420px; overflow-y:auto;'><table style='width:100%; font-size:12px; border-collapse:collapse;'>";
      h += "<tr style='border-bottom:1px solid var(--borde); text-align:left; color:var(--texto-suave); font-size:11px;'>";
      h += "<th style='padding:6px 8px;'>Usuario / Responsable</th>";
      h += "<th style='padding:6px 8px;'>Evento Realizado</th>";
      h += "<th style='padding:6px 8px; text-align:center;'>Animal</th>";
      h += "<th style='padding:6px 8px;'>Fecha / Hora</th>";
      h += "<th style='padding:6px 8px; text-align:center;'>Canal</th>";
      h += "</tr>";

      actList.forEach(function (ev) {
        var rolCat = (ev.usuario_rol || "TRABAJADOR").toUpperCase();
        var fGrupo = "campo";
        if (rolCat === "OWNER" || rolCat === "ADMIN") fGrupo = "admin";
        else if (rolCat === "SISTEMA") fGrupo = "sg";

        var badgeRol = rolCat === "OWNER" ? "<span class='chip amarillo' style='font-size:9.5px; padding:1px 5px;'>OWNER</span>"
                     : rolCat === "ADMIN" ? "<span class='chip azul' style='font-size:9.5px; padding:1px 5px;'>ADMIN</span>"
                     : rolCat === "SISTEMA" ? "<span class='chip gris' style='font-size:9.5px; padding:1px 5px;'>SISTEMA</span>"
                     : "<span class='chip verde' style='font-size:9.5px; padding:1px 5px;'>CAMPO</span>";

        var icCanal = ev.canal === "Telegram" ? "🤖 Telegram" : (ev.canal === "PWA" ? "📱 PWA" : "📁 SG");

        h += "<tr class='fila-act-usr' data-grupo='" + fGrupo + "' style='border-bottom:1px solid var(--borde);'>";
        h += "<td style='padding:7px 8px;'>";
        h += "<div style='display:flex; align-items:center; gap:7px;'>";
        h += renderAvatarBadge(ev.usuario_avatar, ev.usuario_rol, 26, false);
        h += "<div><b>" + esc(ev.usuario_nombre || "Usuario") + "</b> " + badgeRol + "</div>";
        h += "</div></td>";
        h += "<td style='padding:7px 8px;'><span style='font-weight:600; color:var(--texto);'>" + esc(ev.resumen || ev.tabla) + "</span></td>";
        h += "<td style='padding:7px 8px; text-align:center;'>";
        if (ev.tag) {
          h += "<a href='/ficha/" + encodeURIComponent(ev.tag) + "' class='chip azul' style='text-decoration:none; font-weight:600; font-family:var(--font-mono); font-size:11px; padding:2px 6px;'>" + esc(ev.tag) + "</a>";
        } else {
          h += "<span style='color:var(--texto-suave);'>—</span>";
        }
        h += "</td>";
        h += "<td style='padding:7px 8px; color:var(--texto-suave); font-size:11px; white-space:nowrap;'>" + esc(ev.fecha_hora_fmt || ev.fecha || "—") + "</td>";
        h += "<td style='padding:7px 8px; text-align:center;'><span style='font-size:10.5px; color:var(--texto-suave); background:var(--superficie); padding:2px 6px; border-radius:4px; border:1px solid var(--borde);'>" + esc(icCanal) + "</span></td>";
        h += "</tr>";
      });
      h += "</table></div>";
    } else {
      h += "<p style='color:var(--texto-suave); font-size:12px; margin:8px 0;'>No se encontraron eventos recientes registrados en la base de datos.</p>";
    }
    h += "</div>";

    // 3. Usuarios & Presencia en Tiempo Real
    var presList = d.presencias || [];
    if (presList.length) {
      h += "<div style='background:var(--superficie); border:1px solid var(--borde-fuerte); border-radius:10px; padding:16px; margin:20px 0;'>";
      h += "<h4 style='margin:0 0 10px 0; display:flex; align-items:center; gap:6px;'>" + icon("shield", 16) + "Monitoreo de Sesiones y Presencia de Usuarios</h4>";
      h += "<div class='tabla-scroll'><table style='width:100%; font-size:12px; border-collapse:collapse;'>";
      h += "<tr style='border-bottom:1px solid var(--borde); text-align:left; color:var(--texto-suave); font-size:11px;'><th style='padding:5px 8px;'>Usuario</th><th style='padding:5px 8px;'>Rol</th><th style='padding:5px 8px; text-align:center;'>Canal</th><th style='padding:5px 8px;'>Última Actividad</th><th style='padding:5px 8px; text-align:center;'>Estado</th></tr>";
      presList.forEach(function (p) {
        var onCls = p.en_linea ? "chip verde" : "chip gris";
        var onTxt = p.en_linea ? "🟢 En línea" : "⚪ Desconectado";
        h += "<tr style='border-bottom:1px solid var(--borde);'>";
        h += "<td style='padding:6px 8px;'><b>" + esc(p.nombre || ("ID " + p.user_id)) + "</b></td>";
        h += "<td style='padding:6px 8px;'><span style='font-size:11px;'>" + esc(p.rol || "—") + "</span></td>";
        h += "<td style='padding:6px 8px; text-align:center;'><span style='font-size:11px;'>" + esc(p.canal || "—") + "</span></td>";
        h += "<td style='padding:6px 8px; font-size:11px; color:var(--texto-suave);'>" + esc(p.ultima_actividad ? p.ultima_actividad.replace("T", " ") : "—") + "</td>";
        h += "<td style='padding:6px 8px; text-align:center;'><span class='" + onCls + "' style='font-size:10px; padding:2px 6px;'>" + onTxt + "</span></td>";
        h += "</tr>";
      });
      h += "</table></div></div>";
    }

    // 4. Diagnóstico General
    h += "<h4>" + icon("grid") + "Diagnóstico General</h4>"
      + "<pre style='background:var(--superficie); color:var(--texto); border:1px solid var(--borde-fuerte); padding:12px; border-radius:8px; font-size:12px; white-space:pre-wrap; overflow-x:auto; line-height:1.4;'>"
      + esc(d.texto || "Sin diagnóstico disponible.") + "</pre>";

    // 5. Visor de Logs con selector de canal (Todos, Telegram, PWA, Copias)
    h += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-top:20px;'>"
      + "<h4>" + icon("clipboard", 16) + "Visor de Logs en Vivo</h4>"
      + "<div style='display:flex; gap:6px; align-items:center; flex-wrap:wrap;'>"
      + "<button type='button' class='btn-canal-log act tema-btn' data-canal='todos' style='font-size:11.5px; padding:4px 9px;'>🌐 Todos</button>"
      + "<button type='button' class='btn-canal-log tema-btn' data-canal='telegram' style='font-size:11.5px; padding:4px 9px;'>🤖 Telegram</button>"
      + "<button type='button' class='btn-canal-log tema-btn' data-canal='pwa' style='font-size:11.5px; padding:4px 9px;'>🐮 PWA Web</button>"
      + "<button type='button' class='btn-canal-log tema-btn' data-canal='copias' style='font-size:11.5px; padding:4px 9px;'>📁 Copias de Seguridad</button>"
      + "<button type='button' id='btn-refrescar-logs' class='tema-btn' style='font-size:11.5px; padding:4px 10px; margin-left:6px;'>" + icon("refresh", 13) + "Refrescar</button>"
      + "</div></div>"
      + "<pre id='visor-logs' style='background:#121212; color:#39FF14; padding:14px; border-radius:8px; font-family:var(--font-mono); font-size:11.5px; max-height:380px; overflow-y:auto; line-height:1.45; white-space:pre-wrap; word-break:break-all; border:1px solid rgba(255,255,255,0.1);'>Cargando logs del servidor...</pre>";

    return h;
  }

  function bindSistema() {
    var _canalLogsActual = "todos";

    // Filtros de actividad de usuarios
    qa(".btn-filtro-act").forEach(function (b) {
      b.addEventListener("click", function () {
        var f = b.getAttribute("data-f");
        qa(".btn-filtro-act").forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        qa(".fila-act-usr").forEach(function (row) {
          var rG = row.getAttribute("data-grupo") || "";
          if (f === "todos" || rG === f) {
            row.style.display = "";
          } else {
            row.style.display = "none";
          }
        });
      });
    });

    function cargarLogs(canal) {
      if (canal) _canalLogsActual = canal;
      var visor = document.getElementById("visor-logs");
      if (!visor) return;
      visor.textContent = "Cargando logs [" + _canalLogsActual + "]...";

      qa(".btn-canal-log").forEach(function (b) {
        if (b.getAttribute("data-canal") === _canalLogsActual) b.classList.add("act");
        else b.classList.remove("act");
      });

      fetch("/api/logs?canal=" + encodeURIComponent(_canalLogsActual) + "&n=100")
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.logs && d.logs.length) {
            visor.textContent = d.logs.join("\n");
            visor.scrollTop = visor.scrollHeight;
          } else {
            visor.textContent = "Sin logs registrados recientemente para este canal.";
          }
        }).catch(function (err) {
          visor.textContent = "Error al obtener logs: " + err.message;
        });
    }

    cargarLogs(_canalLogsActual);

    var btnRef = document.getElementById("btn-refrescar-logs");
    if (btnRef) btnRef.addEventListener("click", function () { cargarLogs(_canalLogsActual); });

    qa(".btn-canal-log").forEach(function (b) {
      b.addEventListener("click", function () {
        cargarLogs(b.getAttribute("data-canal"));
      });
    });
  }

  /* ---------- Sistema de Avatares & Niveles (Level 1, 2, 3) ---------- */
  var AVATARES = {
    patron: { key: "patron", label: "Patrón / Dueño", ic: "crown", color: "#d97706", bg: "rgba(217,119,6,0.14)" },
    admin: { key: "admin", label: "Administrador", ic: "shieldPlus", color: "#2563eb", bg: "rgba(37,99,235,0.14)" },
    vaquero: { key: "vaquero", label: "Vaquero / Campo", ic: "cowboy", color: "#16a34a", bg: "rgba(22,163,74,0.14)" },
    veterinaria: { key: "veterinaria", label: "Veterinaria", ic: "stethoscope", color: "#9333ea", bg: "rgba(147,51,234,0.14)" },
    pasturas: { key: "pasturas", label: "Pasturas / Forraje", ic: "grass", color: "#059669", bg: "rgba(5,150,105,0.14)" },
    tractor: { key: "tractor", label: "Maquinaria / Tractor", ic: "tractor", color: "#ea580c", bg: "rgba(234,88,12,0.14)" }
  };

  function defaultAvatar(rol) {
    var r = (rol || "").toUpperCase();
    if (r === "OWNER") return "patron";
    if (r === "ADMIN" || r === "ADMINISTRADOR") return "admin";
    return "vaquero";
  }

  function rolToNivel(rol) {
    var r = (rol || "").toUpperCase();
    if (r === "OWNER") return { lvl: 1, txt: "Level 1 (OWNER)", badge: "L1", color: "#d97706", chip: "amarillo" };
    if (r === "ADMIN" || r === "ADMINISTRADOR") return { lvl: 2, txt: "Level 2 (ADMIN)", badge: "L2", color: "#2563eb", chip: "azul" };
    return { lvl: 3, txt: "Level 3 (TRABAJADOR)", badge: "L3", color: "#16a34a", chip: "verde" };
  }

  function renderAvatarBadge(avKey, rol, size, showLvl) {
    size = size || 38;
    var av = AVATARES[avKey] || AVATARES[defaultAvatar(rol)] || AVATARES.vaquero;
    var nv = rolToNivel(rol);
    var icSize = Math.max(12, Math.round(size * 0.52));
    var h = "<div class='avatar-box' style='width:" + size + "px; height:" + size + "px; background:" + av.bg + "; color:" + av.color + "; border-color:" + av.color + ";'>";
    h += icon(av.ic, icSize);
    if (showLvl !== false) {
      h += "<span class='avatar-lvl-mini' style='background:" + nv.color + ";'>" + nv.lvl + "</span>";
    }
    h += "</div>";
    return h;
  }

  /* ---------- Gestión de Usuarios & Accesos (Niveles 1, 2, 3) ---------- */
  function renderUsuarios(d) {
    var miRol = (d && d.mi_rol || "ADMIN").toUpperCase();
    var usuarios = (d && d.usuarios) || [];

    var h = "<h3>" + icon("users") + "Gestión de Personal & Accesos (Niveles 1, 2, 3)</h3>"
      + "<p class='aviso'>Control de acceso basado en roles por niveles. Define el nombre, nivel de jerarquía, PIN de acceso de 4 dígitos, ID local secuencial, ID de Telegram y foto/avatar representativo.</p>";

    // Tarjeta Monitor en Vivo (Exclusivo OWNER)
    if (miRol === "OWNER") {
      var enLineaCount = usuarios.filter(function (u) {
        return u.online_info && u.online_info.en_linea;
      }).length;
      h += "<div class='card' style='padding:14px 18px; margin-bottom:16px; background:linear-gradient(135deg, rgba(22,163,74,0.08), rgba(37,99,235,0.06)); border:1px solid var(--borde-fuerte); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;'>"
        + "<div>"
        + "<div style='display:flex; align-items:center; gap:8px;'>"
        + "<span style='display:inline-block; width:10px; height:10px; border-radius:50%; background:" + (enLineaCount > 0 ? "#16a34a" : "#9ca3af") + "; box-shadow:" + (enLineaCount > 0 ? "0 0 8px #16a34a" : "none") + ";'></span>"
        + "<b style='font-size:14.5px;'>Monitor de Conexión en Vivo (Exclusivo OWNER)</b>"
        + "</div>"
        + "<div style='font-size:12.5px; color:var(--texto-suave); margin-top:3px;'>"
        + (enLineaCount === 1 ? "<b>1 usuario en línea ahora</b>" : "<b>" + enLineaCount + " usuarios en línea ahora</b>")
        + " · Monitoreo confidencial de presencia por Web PWA y Telegram Bot."
        + "</div>"
        + "</div>"
        + "<div>"
        + "<button type='button' id='btn-refrescar-usuarios' class='tema-btn' style='font-size:12px; padding:6px 14px;'>" + icon("refresh", 13) + " Actualizar Estados</button>"
        + "</div>"
        + "</div>";
    }

    // Tarjeta 1: Formulario Agregar / Modificar Usuario
    h += "<div class='card' style='padding:18px; margin-bottom:16px;'>"
      + "<h4>" + icon("pin") + "Crear o Modificar Usuario</h4>"
      + "<form id='form-usuario' style='display:flex; flex-direction:column; gap:14px; margin-top:12px;'>"
      + "<input type='hidden' id='usr-edit-id' value=''>"
      + "<input type='hidden' id='usr-avatar-val' value='vaquero'>"

      // Fila 1: Nombre con máximo espacio horizontal
      + "<div>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>Nombre Completo del Usuario / Trabajador:</label>"
      + "<input id='usr-nombre' placeholder='ej. Don José (Propietario) o Carlos Gómez (Mayordomo)' required style='width:100%; box-sizing:border-box; padding:11px 14px; font-size:15px; border-radius:8px; border:1px solid var(--borde-fuerte);'>"
      + "</div>"

      // Fila 2: Nivel (Rol) y PIN de 4 dígitos
      + "<div style='display:flex; gap:12px; flex-wrap:wrap;'>"
      + "<div style='flex:1.2; min-width:220px;'>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>Nivel de Acceso (Jerarquía):</label>"
      + "<select id='usr-rol' style='width:100%; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-weight:600;'>"
      + "<option value='TRABAJADOR'>Level 3 · TRABAJADOR (Campo: Manga, Captura, Ficha)</option>"
      + "<option value='ADMIN'>Level 2 · ADMIN (Gestión, Tableros, Retiros, Reportes, Usuarios)</option>";
    if (miRol === "OWNER") {
      h += "<option value='OWNER'>Level 1 · OWNER (Dueño / Acceso Total + GPS Rutas + Servidor)</option>";
    }
    h += "</select></div>"
      + "<div style='flex:1; min-width:200px;'>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>PIN de 4 Dígitos (Acceso Celular/PC):</label>"
      + "<div style='display:flex; gap:6px;'>"
      + "<input id='usr-pin' type='text' maxlength='4' pattern='\\d{4}' placeholder='ej. 4521' required style='flex:1; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-family:var(--font-mono); font-size:17px; font-weight:bold; letter-spacing:2px; text-align:center;'>"
      + "<button type='button' id='btn-gen-pin' class='tema-btn' style='font-size:12px; padding:0 12px; white-space:nowrap;'>" + icon("refresh", 13) + " Generar PIN</button>"
      + "</div></div>"
      + "</div>"

      // Fila 3: ID Local e ID Telegram lado a lado
      + "<div style='display:flex; gap:12px; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:180px;'>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>ID Local Sistema:</label>"
      + "<input id='usr-uid' type='number' placeholder='Automático (#1, #2...)' style='width:100%; box-sizing:border-box; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-family:var(--font-mono); background:var(--superficie);'>"
      + "<small style='color:var(--texto-suave); font-size:11px; display:block; margin-top:3px;'>Identificador secuencial interno de la finca.</small>"
      + "</div>"
      + "<div style='flex:1; min-width:180px;'>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>ID Telegram (idtelegram - Opcional):</label>"
      + "<input id='usr-telegram-id' type='number' placeholder='ej. 6123051140' style='width:100%; box-sizing:border-box; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-family:var(--font-mono);'>"
      + "<small style='color:var(--texto-suave); font-size:11px; display:block; margin-top:3px;'>Identificador de Telegram para autorizar el bot.</small>"
      + "</div>"
      + "</div>"

      // Fila 4: Selector de Foto / Avatar Temático
      + "<div>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>Foto / Avatar de Usuario (Estilo Ganadería JA):</label>"
      + "<div id='picker-avatares' class='avatar-picker'>";

    Object.keys(AVATARES).forEach(function (k) {
      var av = AVATARES[k];
      var esActivo = k === "vaquero" ? " act" : "";
      h += "<div class='avatar-pick-item" + esActivo + "' data-av='" + k + "'>"
        + renderAvatarBadge(k, "TRABAJADOR", 38, false)
        + "<span>" + esc(av.label) + "</span>"
        + "</div>";
    });

    h += "</div>"
      + "</div>"

      // Botones de acción
      + "<div style='display:flex; gap:10px; align-items:center; margin-top:6px;'>"
      + "<button type='submit' id='btn-guardar-usr' class='btn-guardar-manga' style='max-width:240px;'>" + icon("save", 15) + " Guardar Usuario</button>"
      + "<button type='button' id='btn-cancelar-edit-usr' class='tema-btn' style='display:none; padding:10px 16px;'>Cancelar Edición</button>"
      + "</div>"
      + "</form>"
      + "<div id='usr-feedback' style='margin-top:12px;'></div>"
      + "</div>";

    // Tarjeta 2: Tabla de Usuarios Existentes
    h += "<div class='card' style='padding:16px;'>"
      + "<h4>" + icon("users") + "Personal Registrado (" + usuarios.length + ")</h4>";

    if (!usuarios.length) {
      h += vacio("No hay usuarios registrados.");
    } else {
      h += "<div class='tabla-scroll'><table>"
        + "<tr>"
        + "<th>Usuario / Foto</th>"
        + "<th>Nivel de Acceso</th>"
        + (miRol === "OWNER" ? "<th>Conexión en Vivo</th>" : "")
        + "<th>ID Local</th>"
        + "<th>ID Telegram</th>"
        + "<th>PIN</th>"
        + "<th>Acciones</th>"
        + "</tr>";

      usuarios.forEach(function (u) {
        var rolU = String(u.rol || "").toUpperCase();
        var nv = rolToNivel(rolU);
        var esOwnerTarget = rolU === "OWNER";
        var puedeEditar = miRol === "OWNER" || !esOwnerTarget;
        var avKey = u.avatar || defaultAvatar(rolU);

        h += "<tr>"
          + "<td>"
          + "<div style='display:flex; align-items:center; gap:10px;'>"
          + renderAvatarBadge(avKey, rolU, 36, true)
          + "<div><b style='font-size:13.5px;'>" + esc(u.nombre || "Sin nombre") + "</b></div>"
          + "</div>"
          + "</td>"
          + "<td><span class='chip " + nv.chip + "' style='font-weight:700;'>" + nv.badge + " · " + esc(rolU) + "</span></td>";

        if (miRol === "OWNER") {
          var oi = u.online_info || {};
          var chipClase = "gris";
          var dotColor = "#9ca3af";
          var estadoLabel = "Desconectado";
          if (oi.estado === "online") {
            chipClase = "verde";
            dotColor = "#16a34a";
            estadoLabel = "En línea";
          } else if (oi.estado === "reciente") {
            chipClase = "amarillo";
            dotColor = "#d97706";
            estadoLabel = "Reciente";
          }
          var canalBadge = oi.canal ? (" (" + esc(oi.canal) + ")") : "";
          var detalleTxt = oi.hace_texto ? esc(oi.hace_texto) : "Nunca";

          h += "<td>"
            + "<div style='display:flex; flex-direction:column; gap:3px;'>"
            + "<span class='chip " + chipClase + "' style='font-size:11px; font-weight:700; display:inline-flex; align-items:center; gap:5px; width:fit-content;'>"
            + "<span style='width:7px; height:7px; border-radius:50%; background:" + dotColor + "; display:inline-block;'></span>"
            + estadoLabel + canalBadge
            + "</span>"
            + "<small style='font-size:11px; color:var(--texto-suave);'>" + detalleTxt + (oi.ip ? " · <span style='font-family:var(--font-mono); font-size:10px;'>" + esc(oi.ip) + "</span>" : "") + "</small>"
            + "</div>"
            + "</td>";
        }

        h += "<td><span style='font-family:var(--font-mono); font-weight:700; font-size:13px; color:var(--texto);'>#" + esc(u.user_id) + "</span></td>"
          + "<td>" + (u.telegram_id ? "<code style='background:var(--superficie); padding:2px 6px; border-radius:4px; font-size:12px; font-family:var(--font-mono);'>" + esc(u.telegram_id) + "</code>" : "<span style='color:var(--texto-suave); font-size:12px;'>—</span>") + "</td>"
          + "<td><code style='background:var(--superficie); padding:3px 8px; border-radius:4px; border:1px solid var(--borde-fuerte); font-size:14px; font-weight:bold; letter-spacing:1px;'>" + esc(u.pin || "—") + "</code></td>"
          + "<td>";

        if (puedeEditar) {
          h += "<button type='button' class='btn-editar-usr tema-btn' data-uid='" + esc(u.user_id) + "' data-nom='" + esc(u.nombre) + "' data-rol='" + esc(rolU) + "' data-pin='" + esc(u.pin || "") + "' data-tgid='" + esc(u.telegram_id || "") + "' data-avatar='" + esc(avKey) + "' style='font-size:11px; padding:4px 9px; margin-right:6px;'>" + icon("pin", 12) + " Editar</button>";
          var numOwners = usuarios.filter(function (x) { return String(x.rol || "").toUpperCase() === "OWNER"; }).length;
          var bloquearBorrar = esOwnerTarget && numOwners <= 1;
          if (!bloquearBorrar && (miRol === "OWNER" || rolU === "TRABAJADOR")) {
            h += "<button type='button' class='btn-borrar-usr tema-btn' data-uid='" + esc(u.user_id) + "' data-nom='" + esc(u.nombre) + "' style='font-size:11px; padding:4px 9px; color:var(--color-rojo-txt);'>" + icon("xmark", 12) + " Eliminar</button>";
          }
        } else {
          h += "<span style='color:var(--texto-suave); font-size:11px;'>Protegido</span>";
        }

        h += "</td></tr>";
      });
      h += "</table></div>";
    }
    h += "</div>";

    return h;
  }

  function bindUsuarios(d) {
    var form = document.getElementById("form-usuario");
    var feed = document.getElementById("usr-feedback");
    var btnGenPin = document.getElementById("btn-gen-pin");
    var pinInp = document.getElementById("usr-pin");
    var editIdInp = document.getElementById("usr-edit-id");
    var avInput = document.getElementById("usr-avatar-val");
    var nomInp = document.getElementById("usr-nombre");
    var rolSel = document.getElementById("usr-rol");
    var uidInp = document.getElementById("usr-uid");
    var tgIdInp = document.getElementById("usr-telegram-id");
    var btnCancelar = document.getElementById("btn-cancelar-edit-usr");
    var btnRefrescarUsr = document.getElementById("btn-refrescar-usuarios");

    if (btnRefrescarUsr) {
      btnRefrescarUsr.addEventListener("click", function () {
        cargar(true);
      });
    }

    function seleccionarAvatar(avKey) {
      if (!avKey) avKey = "vaquero";
      if (avInput) avInput.value = avKey;
      qa(".avatar-pick-item").forEach(function (el) {
        if (el.getAttribute("data-av") === avKey) el.classList.add("act");
        else el.classList.remove("act");
      });
    }

    qa(".avatar-pick-item").forEach(function (item) {
      item.addEventListener("click", function () {
        var avKey = item.getAttribute("data-av");
        seleccionarAvatar(avKey);
      });
    });

    if (rolSel) {
      rolSel.addEventListener("change", function () {
        if (!editIdInp.value) {
          seleccionarAvatar(defaultAvatar(rolSel.value));
        }
      });
    }

    if (btnGenPin && pinInp) {
      btnGenPin.addEventListener("click", function () {
        var randomPin = String(Math.floor(1000 + Math.random() * 9000));
        pinInp.value = randomPin;
      });
    }

    if (btnCancelar) {
      btnCancelar.addEventListener("click", function () {
        editIdInp.value = "";
        nomInp.value = "";
        pinInp.value = "";
        uidInp.value = "";
        uidInp.disabled = false;
        if (tgIdInp) tgIdInp.value = "";
        seleccionarAvatar(defaultAvatar(rolSel ? rolSel.value : "TRABAJADOR"));
        btnCancelar.style.display = "none";
        var btnGuardar = document.getElementById("btn-guardar-usr");
        if (btnGuardar) btnGuardar.innerHTML = icon("save", 15) + " Guardar Usuario";
      });
    }

    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var nombre = (nomInp.value || "").trim();
        var rol = rolSel.value;
        var pin = (pinInp.value || "").trim();
        var uidVal = editIdInp.value || (uidInp.value || "").trim();
        var tgIdVal = (tgIdInp && tgIdInp.value || "").trim();
        var avatar = avInput ? avInput.value : defaultAvatar(rol);

        if (!/^\d{4}$/.test(pin)) {
          if (feed) feed.innerHTML = "<div class='chip rojo'>El PIN debe ser de 4 dígitos numéricos (ej. 4521).</div>";
          return;
        }

        var payload = { nombre: nombre, rol: rol, pin: pin, avatar: avatar };
        if (editIdInp.value) {
          payload.user_id = parseInt(editIdInp.value, 10);
          payload.telegram_id = tgIdVal ? parseInt(tgIdVal, 10) : null;
        } else {
          if (uidVal) payload.user_id = parseInt(uidVal, 10);
          if (tgIdVal) payload.telegram_id = parseInt(tgIdVal, 10);
        }

        if (feed) feed.innerHTML = "<div class='aviso'>Guardando usuario...</div>";

        fetch("/api/usuarios", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              if (feed) feed.innerHTML = "<div class='chip verde'>" + esc(res.mensaje || "Usuario guardado con éxito.") + "</div>";
              form.reset();
              editIdInp.value = "";
              uidInp.disabled = false;
              if (tgIdInp) tgIdInp.value = "";
              seleccionarAvatar(defaultAvatar(rolSel.value));
              if (btnCancelar) btnCancelar.style.display = "none";
              setTimeout(function () { cargar(false); }, 700);
            } else {
              if (feed) feed.innerHTML = "<div class='chip rojo'>❌ " + esc(res.error || "No se pudo guardar") + "</div>";
            }
          }).catch(function (err) {
            if (feed) feed.innerHTML = "<div class='chip rojo'>❌ Error de conexión: " + esc(err.message) + "</div>";
          });
      });
    }

    // Botones de editar usuario
    qa(".btn-editar-usr").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var uid = btn.getAttribute("data-uid");
        var nom = btn.getAttribute("data-nom");
        var rol = btn.getAttribute("data-rol");
        var pin = btn.getAttribute("data-pin");
        var tgid = btn.getAttribute("data-tgid");
        var av = btn.getAttribute("data-avatar") || defaultAvatar(rol);

        editIdInp.value = uid;
        nomInp.value = nom;
        rolSel.value = rol;
        pinInp.value = (pin && pin !== "****") ? pin : "";
        uidInp.value = uid;
        uidInp.disabled = true;
        if (tgIdInp) tgIdInp.value = tgid || "";
        seleccionarAvatar(av);
        if (btnCancelar) btnCancelar.style.display = "";
        var btnGuardar = document.getElementById("btn-guardar-usr");
        if (btnGuardar) btnGuardar.innerHTML = icon("save", 15) + " Actualizar Usuario";
        form.scrollIntoView({ behavior: "smooth" });
      });
    });

    // Botones de eliminar usuario
    qa(".btn-borrar-usr").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var uid = btn.getAttribute("data-uid");
        var nom = btn.getAttribute("data-nom");
        if (!confirm("¿Está seguro de eliminar al usuario '" + nom + "' (ID: " + uid + ")?")) return;

        fetch("/api/usuarios/" + encodeURIComponent(uid) + "/eliminar", { method: "POST" })
          .then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              alert(res.mensaje || "Usuario eliminado");
              cargar(false);
            } else {
              alert("Error: " + (res.error || "No se pudo eliminar"));
            }
          }).catch(function (err) {
            alert("Error de conexión: " + err.message);
          });
      });
    });
  }

  /* ---------- Exportación a CSV con UTF-8 BOM para Excel ---------- */
  function exportarTablaCSV(nombreArchivo, tablaSelectorOEl) {
    var tabla = typeof tablaSelectorOEl === "string" ? document.querySelector(tablaSelectorOEl) : tablaSelectorOEl;
    if (!tabla) {
      alert("No se encontró ninguna tabla para exportar.");
      return;
    }
    var trs = qa("tr", tabla);
    var csv = [];
    trs.forEach(function (tr) {
      var celdas = qa("th, td", tr);
      if (!celdas.length) return;
      var fila = celdas.map(function (c) {
        var txt = (c.innerText || c.textContent || "").replace(/"/g, '""').trim();
        return '"' + txt + '"';
      });
      csv.push(fila.join(";"));
    });
    var contenido = "\uFEFF" + csv.join("\r\n");
    var blob = new Blob([contenido], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = (nombreArchivo || "export_ganaderia_ja") + "_" + new Date().toISOString().slice(0, 10) + ".csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  window.__exportarInventario = function () {
    exportarTablaCSV("inventario_ganaderia_ja", ".tabla-scroll table");
  };
  window.__exportarRetiros = function () {
    exportarTablaCSV("retiros_sanitarios_ja", ".tabla-scroll table");
  };

  /* ---------- Asistente IA (Chat Natural) ---------- */
  function formatearMensajeChat(raw) {
    if (!raw) return "";
    var str = String(raw);

    // 1. Extraer bloques <pre>...</pre> para proteger su formateo monoespaciado
    var pres = [];
    str = str.replace(/<pre(?:\s+[^>]*)?>([\s\S]*?)<\/pre>/gi, function (_, contenido) {
      var dec = contenido
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&amp;/g, "&")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'");
      var seguro = esc(dec.trim());
      pres.push(
        "<div class='chat-pre-wrap'>" +
          "<button class='btn-pre-copy' type='button' title='Copiar tabla'>📋 Copiar</button>" +
          "<pre>" + seguro + "</pre>" +
        "</div>"
      );
      return "___PRE_BLOCK_" + (pres.length - 1) + "___";
    });

    // 2. Extraer bloques <code>...</code>
    var codes = [];
    str = str.replace(/<code(?:\s+[^>]*)?>([\s\S]*?)<\/code>/gi, function (_, contenido) {
      var dec = contenido
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&amp;/g, "&");
      codes.push("<code>" + esc(dec) + "</code>");
      return "___CODE_BLOCK_" + (codes.length - 1) + "___";
    });

    // 3. Extraer enlaces seguros <a href="...">...</a>
    var links = [];
    str = str.replace(/<a\s+href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, function (_, url, texto) {
      var safeUrl = /^https?:\/\//i.test(url) || url.charAt(0) === "/" ? esc(url) : "#";
      links.push("<a href='" + safeUrl + "' target='_blank' rel='noopener noreferrer'>" + esc(texto) + "</a>");
      return "___LINK_BLOCK_" + (links.length - 1) + "___";
    });

    // 4. Proteger tags seguros de formato HTML: <b>, <strong>, <i>, <em>, <u>, <s>
    str = str
      .replace(/<\/?b>/gi, function (m) { return m.toLowerCase() === "<b>" ? "___B_OPEN___" : "___B_CLOSE___"; })
      .replace(/<\/?strong>/gi, function (m) { return m.toLowerCase() === "<strong>" ? "___B_OPEN___" : "___B_CLOSE___"; })
      .replace(/<\/?i>/gi, function (m) { return m.toLowerCase() === "<i>" ? "___I_OPEN___" : "___I_CLOSE___"; })
      .replace(/<\/?em>/gi, function (m) { return m.toLowerCase() === "<em>" ? "___I_OPEN___" : "___I_CLOSE___"; })
      .replace(/<\/?u>/gi, function (m) { return m.toLowerCase() === "<u>" ? "___U_OPEN___" : "___U_CLOSE___"; })
      .replace(/<\/?s>/gi, function (m) { return m.toLowerCase() === "<s>" ? "___S_OPEN___" : "___S_CLOSE___"; });

    // 5. Escapar todo el texto restante para neutralizar inyecciones XSS
    str = esc(str);

    // 6. Restaurar tags de formato seguro
    str = str
      .replace(/___B_OPEN___/g, "<b>")
      .replace(/___B_CLOSE___/g, "</b>")
      .replace(/___I_OPEN___/g, "<i>")
      .replace(/___I_CLOSE___/g, "</i>")
      .replace(/___U_OPEN___/g, "<u>")
      .replace(/___U_CLOSE___/g, "</u>")
      .replace(/___S_OPEN___/g, "<s>")
      .replace(/___S_CLOSE___/g, "</s>");

    // 7. Formato Markdown común (**negrita**, *cursiva*, `código`)
    str = str
      .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
      .replace(/(^|[^\w])\*([^*\n]+)\*([^\w]|$)/g, "$1<b>$2</b>$3")
      .replace(/(^|[^\w])_([^_\n]+)_([^\w]|$)/g, "$1<i>$2</i>$3")
      .replace(/`([^`\n]+)`/g, "<code>$1</code>");

    // 8. Convertir saltos de línea a <br> fuera de <pre>
    str = str.replace(/\n/g, "<br>");
    str = str.replace(/<br>(<div class='chat-pre-wrap'>)/g, "$1").replace(/(<\/div>)<br>/g, "$1");

    // 9. Restaurar enlaces, codes y pres protegidos
    str = str.replace(/___LINK_BLOCK_(\d+)___/g, function (_, idx) {
      return links[parseInt(idx, 10)] || "";
    });
    str = str.replace(/___CODE_BLOCK_(\d+)___/g, function (_, idx) {
      return codes[parseInt(idx, 10)] || "";
    });
    str = str.replace(/___PRE_BLOCK_(\d+)___/g, function (_, idx) {
      return pres[parseInt(idx, 10)] || "";
    });

    return str;
  }

  function setupChatModal() {
    var btnChat = document.getElementById("btn-chat");
    var modal = document.getElementById("modal-chat");
    var btnCerrar = document.getElementById("btn-cerrar-chat");
    var form = document.getElementById("form-chat");
    var inp = document.getElementById("chat-input");
    var hist = document.getElementById("chat-historial");

    if (!btnChat || !modal) return;

    btnChat.addEventListener("click", function () {
      modal.style.display = "flex";
      if (inp) inp.focus();
    });

    if (btnCerrar) {
      btnCerrar.addEventListener("click", function () {
        modal.style.display = "none";
      });
    }

    modal.addEventListener("click", function (e) {
      if (e.target === modal) modal.style.display = "none";
    });

    if (hist) {
      hist.addEventListener("click", function (e) {
        var btn = e.target && e.target.closest ? e.target.closest(".btn-pre-copy") : null;
        if (!btn) return;
        var pre = btn.parentElement ? btn.parentElement.querySelector("pre") : null;
        if (pre && navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(pre.innerText || pre.textContent).then(function () {
            var old = btn.textContent;
            btn.textContent = "✓ Copiado";
            setTimeout(function () { btn.textContent = old; }, 1800);
          });
        }
      });
    }

    qa(".chip-sug", modal).forEach(function (chip) {
      chip.addEventListener("click", function () {
        var p = chip.getAttribute("data-p");
        if (inp) inp.value = p;
        if (form) form.dispatchEvent(new Event("submit"));
      });
    });

    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var txt = (inp && inp.value || "").trim();
        if (!txt) return;

        var botPlaceholder;
        if (hist) {
          hist.innerHTML += "<div class='chat-msg user'>" + esc(txt) + "</div>";
          botPlaceholder = document.createElement("div");
          botPlaceholder.className = "chat-msg bot";
          botPlaceholder.innerHTML = "<i>Consultando información zootécnica...</i>";
          hist.appendChild(botPlaceholder);
          hist.scrollTop = hist.scrollHeight;
        }

        if (inp) inp.value = "";

        fetch("/api/preguntar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pregunta: txt })
        }).then(function (r) { return r.json(); })
          .then(function (d) {
            var resp = d.respuesta || d.error || "Sin respuesta.";
            var formateada = formatearMensajeChat(resp);
            if (botPlaceholder) botPlaceholder.innerHTML = formateada;
            if (hist) hist.scrollTop = hist.scrollHeight;
          }).catch(function (err) {
            if (botPlaceholder) botPlaceholder.innerHTML = "❌ Error de conexión: " + esc(err.message);
          });
      });
    }
  }

  /* ---------- Dictado por Voz (Whisper) ---------- */
  var _mediaRecorder = null;
  var _audioChunks = [];
  function setupVozModal() {
    var btnMic = document.getElementById("btn-mic");
    var modal = document.getElementById("modal-voz");
    var btnCerrar = document.getElementById("btn-cerrar-voz");
    var btnAccion = document.getElementById("btn-voz-accion");
    var estado = document.getElementById("voz-estado");
    var resBox = document.getElementById("voz-resultado");
    var onda = document.getElementById("voz-onda");

    if (!btnMic || !modal) return;

    function detenerGrabacion() {
      if (_mediaRecorder && _mediaRecorder.state === "recording") {
        try { _mediaRecorder.stop(); } catch (e) { /* noop */ }
      }
    }

    btnMic.addEventListener("click", function () {
      modal.style.display = "flex";
      if (resBox) { resBox.style.display = "none"; resBox.innerHTML = ""; }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (estado) estado.textContent = "❌ Tu navegador no soporta grabación de micrófono.";
        if (btnAccion) btnAccion.style.display = "none";
        return;
      }
      if (estado) estado.textContent = "Iniciando micrófono...";
      if (btnAccion) { btnAccion.innerHTML = icon("square", 14) + "Detener y Enviar"; btnAccion.style.display = ""; }
      if (onda) onda.style.display = "block";

      _audioChunks = [];
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        _mediaRecorder = new MediaRecorder(stream);
        _mediaRecorder.ondataavailable = function (e) {
          if (e.data && e.data.size > 0) _audioChunks.push(e.data);
        };
        _mediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          if (!_audioChunks.length) {
            if (estado) estado.textContent = "No se capturó audio.";
            return;
          }
          if (estado) estado.textContent = "Transcribiendo con Whisper y procesando en el bot...";
          if (onda) onda.style.display = "none";

          var blob = new Blob(_audioChunks, { type: _mediaRecorder.mimeType || "audio/webm" });
          var fd = new FormData();
          fd.append("audio", blob, "nota_campo.webm");

          fetch("/api/voz", { method: "POST", body: fd })
            .then(function (r) { return r.json(); })
            .then(function (data) {
              if (resBox) resBox.style.display = "block";
              if (data.ok) {
                if (estado) estado.textContent = "Nota procesada con éxito.";
                resBox.innerHTML = "<b>Transcripción:</b> <i>\"" + esc(data.transcripcion) + "\"</i><br><br>"
                  + "<b>Respuesta del Bot:</b><br>" + formatearMensajeChat(data.respuesta || "Registrado.");
                if (btnAccion) btnAccion.innerHTML = icon("mic", 14) + "Grabar Otra Nota";
                actualizarBadges();
              } else {
                if (estado) estado.textContent = "⚠️ " + esc(data.error || "No se pudo procesar");
                if (btnAccion) btnAccion.textContent = "Reintentar";
              }
            }).catch(function (err) {
              if (estado) estado.textContent = "❌ Error de conexión: " + esc(err.message);
              if (btnAccion) btnAccion.textContent = "Reintentar";
            });
        };
        _mediaRecorder.start();
        if (estado) estado.textContent = "🔴 Grabando... hable ahora con claridad.";
      }).catch(function (err) {
        if (estado) estado.textContent = "❌ No se pudo acceder al micrófono: " + err.message;
        if (btnAccion) btnAccion.style.display = "none";
      });
    });

    if (btnCerrar) {
      btnCerrar.addEventListener("click", function () {
        detenerGrabacion();
        modal.style.display = "none";
      });
    }

    modal.addEventListener("click", function (e) {
      if (e.target === modal) {
        detenerGrabacion();
        modal.style.display = "none";
      }
    });

    if (btnAccion) {
      btnAccion.addEventListener("click", function () {
        if (_mediaRecorder && _mediaRecorder.state === "recording") {
          _mediaRecorder.stop();
        } else {
          btnMic.click();
        }
      });
    }

    if (resBox) {
      resBox.addEventListener("click", function (e) {
        var btn = e.target && e.target.closest ? e.target.closest(".btn-pre-copy") : null;
        if (!btn) return;
        var pre = btn.parentElement ? btn.parentElement.querySelector("pre") : null;
        if (pre && navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(pre.innerText || pre.textContent).then(function () {
            var old = btn.textContent;
            btn.textContent = "✓ Copiado";
            setTimeout(function () { btn.textContent = old; }, 1800);
          });
        }
      });
    }
  }

  /* ---------- Cola Offline con IndexedDB (ja_bitacora_offline) ---------- */
  function abrirDB() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) return reject(new Error("IndexedDB no soportado"));
      var req = window.indexedDB.open("ja_bitacora_offline", 1);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains("outbox")) {
          db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
        }
      };
      req.onsuccess = function (e) { resolve(e.target.result); };
      req.onerror = function (e) { reject(e.target.error); };
    });
  }

  function encolarOffline(tipo, payload, fecha) {
    return abrirDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction("outbox", "readwrite");
        var store = tx.objectStore("outbox");
        var ev = {
          tipo: tipo,
          payload: payload || {},
          fecha: fecha || new Date().toISOString().slice(0, 10),
          id_local: "loc_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6),
          creado_en: new Date().toISOString()
        };
        var req = store.add(ev);
        req.onsuccess = function () {
          resolve(ev);
          actualizarContadorSync();
        };
        req.onerror = function (e) { reject(e.target.error); };
      });
    }).catch(function (err) {
      console.warn("Fallo encolar offline:", err);
    });
  }

  function obtenerColaOffline() {
    return abrirDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction("outbox", "readonly");
        var store = tx.objectStore("outbox");
        var req = store.getAll();
        req.onsuccess = function () { resolve(req.result || []); };
        req.onerror = function (e) { reject(e.target.error); };
      });
    }).catch(function () { return []; });
  }

  function eliminarDeColaOffline(ids) {
    if (!ids || !ids.length) return Promise.resolve();
    return abrirDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction("outbox", "readwrite");
        var store = tx.objectStore("outbox");
        ids.forEach(function (id) { store.delete(id); });
        tx.oncomplete = function () {
          resolve();
          actualizarContadorSync();
        };
        tx.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function actualizarContadorSync() {
    obtenerColaOffline().then(function (lista) {
      var badge = document.getElementById("sync-count");
      if (!badge) return;
      var n = lista.length;
      if (n > 0) {
        badge.textContent = n > 99 ? "99+" : String(n);
        badge.style.display = "";
        badge.classList.add("on");
      } else {
        badge.textContent = "0";
        badge.style.display = "none";
        badge.classList.remove("on");
      }
    });
  }

  function sincronizarColaOffline(mostrarAviso) {
    obtenerColaOffline().then(function (lista) {
      if (!lista || !lista.length) {
        if (mostrarAviso) alert("No hay eventos pendientes por sincronizar en la cola local.");
        return;
      }
      if (navigator.onLine === false) {
        if (mostrarAviso) alert("Sin conexión a internet. Los " + lista.length + " eventos se sincronizarán al recuperar la señal.");
        return;
      }
      fetch("/api/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventos: lista })
      }).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).then(function (res) {
        // Solo se borran de la cola local los eventos que el servidor
        // confirmó explícitamente (ids_ok, correlacionado por id_local) --
        // antes se borraba TODA la cola con un simple HTTP 200, aunque un
        // evento individual hubiera fallado (ej. tag inexistente): ese
        // evento desaparecía de la cola sin haberse guardado, una pérdida
        // de datos de campo silenciosa (peor aún en la sincronización
        // automática en segundo plano, sin aviso visible).
        var okSet = {};
        (res.ids_ok || []).forEach(function (idl) { okSet[idl] = true; });
        var idsBorrar = lista.filter(function (x) { return okSet[x.id_local]; })
          .map(function (x) { return x.id; });
        var pendientes = lista.length - idsBorrar.length;
        eliminarDeColaOffline(idsBorrar).then(function () {
          if (mostrarAviso) {
            var msg = "✅ Sincronizados " + (res.procesados || 0) + " eventos con éxito.";
            if (pendientes > 0) msg += "\n⚠️ " + pendientes + " evento(s) no se pudieron guardar y siguen en la cola local.";
            if (res.errores && res.errores.length) {
              msg += "\n⚠️ Avisos: " + res.errores.join("; ");
            }
            alert(msg);
          } else if (pendientes > 0) {
            console.warn("Sincronización en segundo plano: " + pendientes + " evento(s) siguen en cola.", res.errores);
          }
          actualizarBadges();
          if (actual !== "manga" && actual !== "captura") cargar(false);
        });
      }).catch(function (err) {
        if (mostrarAviso) alert("Error al sincronizar con el servidor: " + err.message);
      });
    });
  }

  function setupSyncOffline() {
    var btnSync = document.getElementById("btn-sync");
    if (btnSync) {
      btnSync.addEventListener("click", function () {
        sincronizarColaOffline(true);
      });
    }
  }

  /* ---------- Usuario y Control de Acceso (RBAC) ---------- */
  var usuarioActual = null;
  function cargarUsuario() {
    return fetch("/api/usuario").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (u) {
      usuarioActual = u || {};
      window.__usuarioActual = usuarioActual;
      aplicarRBAC(usuarioActual);
      return usuarioActual;
    }).catch(function () { /* modo seguro */ });
  }

  function aplicarRBAC(u) {
    var badge = document.getElementById("user-badge");
    if (badge && u && u.nombre) {
      var rol = (u.rol || "INVITADO").toUpperCase();
      var nv = rolToNivel(rol);
      var avKey = u.avatar || defaultAvatar(rol);
      badge.innerHTML = renderAvatarBadge(avKey, rol, 20, false)
        + "<span style='margin-left:4px; font-weight:600;'>" + esc(u.nombre) + "</span>"
        + "<span class='chip " + nv.chip + "' style='font-size:10px; padding:1px 6px; margin-left:5px; line-height:1.2;'>" + nv.badge + "</span>";
      badge.style.display = "inline-flex";
    }

    var rol = (u.rol || "").toUpperCase();
    var btnSistema = document.getElementById("btn-nav-sistema");
    var btnUsuarios = document.getElementById("btn-nav-usuarios");
    var btnGps = document.getElementById("btn-nav-gps");

    if (rol === "OWNER") {
      if (btnSistema) btnSistema.style.display = "";
      if (btnUsuarios) btnUsuarios.style.display = "";
      if (btnGps) btnGps.style.display = "";
      qa("nav > button").forEach(function (b) { b.style.display = ""; });
    } else if (rol === "ADMIN" || rol === "ADMINISTRADOR") {
      if (btnSistema) btnSistema.style.display = "none";
      if (btnGps) btnGps.style.display = "none";
      if (btnUsuarios) btnUsuarios.style.display = "";
      qa("nav > button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        if (v === "sistema" || v === "gps") b.style.display = "none";
        else b.style.display = "";
      });
    } else if (rol === "TRABAJADOR") {
      if (btnSistema) btnSistema.style.display = "none";
      if (btnUsuarios) btnUsuarios.style.display = "none";
      if (btnGps) btnGps.style.display = "none";
      var permitidas = ["captura", "manga", "ficha"];
      qa("nav > button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        if (permitidas.indexOf(v) !== -1) {
          b.style.display = "";
        } else {
          b.style.display = "none";
        }
      });
      if (permitidas.indexOf(actual) === -1 && actual !== "ayuda") {
        irAVista("captura");
        cargar();
      }
    }
  }

  /* ---------- Ficha con pestañas ---------- */
  var TABS = [
    { id: "general", label: icon("cow") + "General" },
    { id: "genealogia", label: icon("dna") + "Genealogía (3G)" },
    { id: "repro", label: icon("sperm") + "Reproducción" },
    { id: "sanidad", label: icon("shieldPlus") + "Tratamientos" },
    { id: "leche", label: icon("milk") + "Leche" },
    { id: "pesos", label: icon("scale") + "Pesos" }
  ];
  // HTML del panel "identificar por foto del arete" (solo en el dashboard,
  // no en la página /ficha/<tag> que llega desde el QR ya identificado).
  function identPanelHtml() {
    return "<div class='card ident-box' style='margin-bottom:10px'>"
      + "<b>" + icon("camera") + "Identificar por foto del arete</b>"
      + "<p class='aviso' style='margin:4px 0'>Tome la foto del arete con el celular o pegue un código RFID/arete arriba y pulse Cargar. También puede <b>escanear un QR</b> de las fichas de corral.</p>"
      + "<div style='display:flex; gap: 8px; flex-wrap:wrap; align-items:center; margin:6px 0'>"
      + "<input type='file' id='f-ident-foto' accept='image/*' capture='environment' style='min-height:40px; flex:1'>"
      + "<button id='btn-ident' type='button'>" + icon("search") + "Identificar</button>"
      + "<button id='btn-scan-qr' type='button'>" + icon("camera") + "Escanear QR</button>"
      + "</div>"
      + "<span id='ident-estado' class='aviso'></span>"
      + "<div id='ident-resultado'></div>"
      + "<video id='qr-video' style='display:none; width:100%; max-width:320px; border-radius:8px; margin-top:8px' autoplay playsinline></video>"
      + "</div>";
  }
  function fichaHtml(f, showIdent) {
    var head = "<div class='ficha-head' style='display:flex; gap:14px; align-items:center; background:var(--superficie); padding:14px; border:1px solid var(--borde); border-radius:10px; margin-bottom:12px;'>";
    if (f.fotos && f.fotos.length && f.fotos[0].url) {
      head += "<div class='foto-card-mini' title='Toca para agrandar' style='cursor:zoom-in; position:relative; flex-shrink:0; border-radius:8px; overflow:hidden;'>"
        + "<img class='avatar zoomable-img' src='" + esc(f.fotos[0].url) + "' alt='Foto principal " + esc(f.tag) + "' style='width:64px; height:64px; border-radius:8px; object-fit:cover; display:block;' data-onerror-hide='parent'>"
        + "<div style='position:absolute; bottom:2px; right:2px; background:rgba(0,0,0,0.65); border-radius:3px; padding:2px 3px; color:#fff; display:flex; align-items:center; pointer-events:none;'>" + icon("search", 10) + "</div>"
        + "</div>";
    } else {
      head += "<div style='width:64px; height:64px; border-radius:8px; background:var(--verde-marca-pastel); color:var(--verde-marca); display:flex; align-items:center; justify-content:center; flex-shrink:0;'>" + icon("cow", 32) + "</div>";
    }
    var estadoChip = "";
    var stUpper = String(f.estado || "").toUpperCase();
    if (stUpper === "ACTIVO") estadoChip = "<span class='chip verde'>ACTIVO</span>";
    else if (stUpper === "VENDIDO" || stUpper === "DESCARTADO") estadoChip = "<span class='chip ambar'>" + esc(f.estado) + "</span>";
    else if (stUpper === "MUERTO") estadoChip = "<span class='chip rojo'>MUERTO</span>";
    else if (f.estado) estadoChip = "<span class='chip gris'>" + esc(f.estado) + "</span>";

    var potChip = f.potrero ? "<span class='chip gris' style='margin-left:4px;'>" + icon("grass", 13) + esc(f.potrero) + "</span>" : "";
    var catChip = f.categoria_sg ? "<span class='chip gris' style='margin-left:4px;'>" + esc(f.categoria_sg) + "</span>" : "";
    var retiroChip = f.en_retiro ? "<span class='chip rojo' style='margin-left:4px; font-weight:bold;'>" + icon("alert", 13) + "EN RETIRO</span>" : "";

    head += "<div class='datos' style='flex:1; min-width:0;'>"
      + "<div style='display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin-bottom:4px;'>"
      + "<b style='font-size:18px; letter-spacing:-0.02em;'>" + esc(f.tag) + (f.nombre ? " · " + esc(f.nombre) : "") + "</b>"
      + estadoChip + retiroChip
      + "</div>"
      + "<div style='display:flex; flex-wrap:wrap; gap:4px; align-items:center; margin-bottom:4px;'>"
      + potChip + catChip
      + "</div>"
      + "<span class='meta' style='font-size:12px; color:var(--texto-suave);'>"
      + esc(f.sexo || "") + " · " + esc(f.raza || "S/D")
      + (f.edad_str ? " · <b>" + esc(f.edad_str) + "</b>" : (f.fecha_nacimiento ? " · Nac: " + esc(fechaCorta(f.fecha_nacimiento)) : ""))
      + "</span>"
      + "</div>";

    head += "<div style='display:flex; flex-direction:column; gap:6px; align-self:flex-start;'>"
      + "<a href='/api/ficha/" + encodeURIComponent(f.tag) + "/qr.pdf' target='_blank' download class='tema-btn' style='font-size:12px; padding:6px 10px; text-decoration:none; white-space:nowrap; display:inline-flex; align-items:center;'>"
      + icon("filePdf", 15) + "Ficha PDF</a>"
      + "</div>";

    head += "</div>";

    var html = (showIdent ? identPanelHtml() : "") + head + erroresHtml(f);
    html += "<div id='ficha-tabs'><nav class='mini'>"
      + TABS.map(function (t, i) { return "<button data-tab='" + t.id + "' class='" + (i === 0 ? "act" : "") + "'>" + t.label + "</button>"; }).join("")
      + "</nav></div><div id='ficha-panel'>" + fichaTab("general", f) + "</div>";
    return html;
  }
  function chipResultado(v) {
    var s = String(v == null ? "" : v).toUpperCase();
    if (s === "PREÑADA" || s === "PREGNANT") return "<span class='chip verde'>" + icon("sperm", 14) + "PREÑADA</span>";
    if (s === "VACIA" || s === "VACÍA") return "<span class='chip ambar'>" + icon("circleEmpty", 14) + "VACÍA</span>";
    if (s === "FALLIDO") return "<span class='chip rojo'>" + icon("xmark", 14) + "FALLIDO</span>";
    if (!s) return "—";
    return "<span class='chip gris'>" + esc(v) + "</span>";
  }
  function fichaTab(id, f) {
    if (id === "genealogia") {
      var g = f.genealogia_3g || {};
      var cons = g.consanguinidad || f.consanguinidad || {};
      var hg = "";

      // 1. Título y Semáforo de Consanguinidad
      hg += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
        + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("dna") + "Árbol Genealógico & Trazabilidad (3G)</h3>"
        + "</div>";

      var cClase = cons.clase || (cons.consanguineo ? "rojo" : (cons.evaluable ? "verde" : "gris"));
      var cIcon = cons.consanguineo ? icon("alert", 16) : (cons.evaluable ? icon("shieldCheck", 16) : icon("circleEmpty", 16));
      var cTxt = cons.detalle || (cons.consanguineo ? "Cruzamiento consanguíneo detectado" : (cons.evaluable ? "0.0% Consanguinidad en 3G" : "No evaluable"));

      hg += "<div class='card' style='padding:12px 14px; margin-bottom:14px; display:flex; align-items:center; gap:10px; border-left:4px solid var(--" + (cClase === "verde" ? "color-verde-txt" : (cClase === "rojo" ? "color-rojo-txt" : "borde-fuerte")) + ");'>"
        + "<div style='font-size:20px;'>" + cIcon + "</div>"
        + "<div style='flex:1; font-size:13px;'>"
        + "<b>Control de Consanguinidad Parental:</b> <span class='chip " + cClase + "'>" + esc(cTxt) + "</span>"
        + "<div style='font-size:11.5px; color:var(--texto-suave); margin-top:3px;'>Regla zootécnica de 3 generaciones antes de autorizar cruzamiento o servicio de monta/I.A.</div>"
        + "</div>"
        + "</div>";

      // Helper nodo animal
      function nodoAnimal(an, label, icono) {
        if (!an || !an.tag) {
          return "<div style='background:var(--superficie); border:1px dashed var(--borde-fuerte); border-radius:8px; padding:10px; font-size:12px; color:var(--texto-suave);'>"
            + "<div style='font-weight:600; font-size:11px; text-transform:uppercase; color:var(--texto-suave); margin-bottom:2px;'>" + icono + " " + esc(label) + "</div>"
            + "<div>Desconocido / Sin Registro</div>"
            + "</div>";
        }
        var nom = an.nombre ? " · " + esc(an.nombre) : "";
        var rz = an.raza ? " [" + esc(an.raza) + "]" : "";
        var click = "data-ir-ficha='" + esc(an.tag) + "'";
        return "<div style='background:var(--superficie); border:1px solid var(--borde-fuerte); border-radius:8px; padding:10px; font-size:12.5px; box-shadow:0 1px 3px var(--sombra);'>"
          + "<div style='font-weight:600; font-size:11px; text-transform:uppercase; color:var(--texto-suave); margin-bottom:4px;'>" + icono + " " + esc(label) + "</div>"
          + "<div><a href='#' class='ficha-link' " + click + " style='font-weight:bold; font-size:14px; text-decoration:none;'><b>" + esc(an.tag) + "</b></a>" + nom + " <span class='chip gris' style='font-size:11px; padding:1px 5px;'>" + esc(an.raza || "S/D") + "</span></div>"
          + "</div>";
      }

      // 2. Pedigree Diagram
      hg += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
        + "<h4 style='margin-top:0;'>" + icon("gitBranch", 16) + "Pedigree Estructurado (3 Generaciones)</h4>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; margin-top:10px;'>"

        // Línea Paterna
        + "<div style='background:rgba(47,82,51,0.03); border:1px solid var(--borde); border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:10px;'>"
        + "<div style='font-weight:bold; color:var(--verde-marca); border-bottom:1px solid var(--borde); padding-bottom:6px; font-size:13px; display:flex; align-items:center; gap:6px;'>🐂 LÍNEA PATERNA</div>"
        + nodoAnimal(f.padre, "Padre", "🐂")
        + "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte); display:flex; flex-direction:column; gap:8px;'>"
        + nodoAnimal(f.abuelo_pat || g.abuelo_pat, "Abuelo Paterno", "🐂")
        + (g.bisabuelos && g.bisabuelos.pat_pat_p ? "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte);'>" + nodoAnimal(g.bisabuelos.pat_pat_p, "Bisabuelo (PP)", "🧬") + "</div>" : "")
        + nodoAnimal(f.abuela_pat || g.abuela_pat, "Abuela Paterna", "🐄")
        + (g.bisabuelos && g.bisabuelos.pat_mat_m ? "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte);'>" + nodoAnimal(g.bisabuelos.pat_mat_m, "Bisabuela (PM)", "🧬") + "</div>" : "")
        + "</div>"
        + "</div>"

        // Línea Materna
        + "<div style='background:rgba(47,82,51,0.03); border:1px solid var(--borde); border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:10px;'>"
        + "<div style='font-weight:bold; color:var(--verde-marca); border-bottom:1px solid var(--borde); padding-bottom:6px; font-size:13px; display:flex; align-items:center; gap:6px;'>🐄 LÍNEA MATERNA</div>"
        + nodoAnimal(f.madre, "Madre", "🐄")
        + "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte); display:flex; flex-direction:column; gap:8px;'>"
        + nodoAnimal(f.abuelo_mat || g.abuelo_mat, "Abuelo Materno", "🐂")
        + (g.bisabuelos && g.bisabuelos.mat_pat_p ? "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte);'>" + nodoAnimal(g.bisabuelos.mat_pat_p, "Bisabuelo (MP)", "🧬") + "</div>" : "")
        + nodoAnimal(f.abuela_mat || g.abuela_mat, "Abuela Materna", "🐄")
        + (g.bisabuelos && g.bisabuelos.mat_mat_m ? "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte);'>" + nodoAnimal(g.bisabuelos.mat_mat_m, "Bisabuela (MM)", "🧬") + "</div>" : "")
        + "</div>"
        + "</div>"

        + "</div></div>";

      // 3. Descendencia / Crías Registradas
      var crias = (f.crias && f.crias.length) ? f.crias : ((g.crias && g.crias.length) ? g.crias : (f.partos || []));
      hg += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
        + "<h4 style='margin-top:0; display:flex; align-items:center; gap:6px;'>" + icon("cowCalf", 18) + "Descendencia & Crías Registradas (" + crias.length + ")</h4>";

      if (crias.length) {
        hg += "<div style='display:flex; flex-direction:column; gap:8px; margin-top:10px;'>";
        crias.forEach(function (c) {
          var cTag = c.cria_tag || c.tag || "Sin arete";
          var cNom = c.nombre ? " (" + esc(c.nombre) + ")" : "";
          var cSx = c.sexo_cria || c.sexo || "S/D";
          var cFec = fechaCorta(c.fecha_parto || c.fecha || c.fecha_nacimiento) || "S/D";
          var cEst = String(c.estado_cria || c.estado || "VIVO").toUpperCase();
          var estChip = cEst === "MUERTO" ? "<span class='chip rojo'>Muerto</span>" : "<span class='chip verde'>Vivo</span>";
          var pNac = c.peso_nacimiento ? " · " + c.peso_nacimiento + " kg" : "";

          var linkTag = cTag !== "Sin arete"
            ? "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(cTag) + "\" style='font-size:14px; font-weight:bold; display:inline-flex; align-items:center; gap:5px; text-decoration:none;'>" + icon("calf", 14) + "<span>" + esc(cTag) + "</span></a>"
            : "<span style='color:var(--texto-suave); display:inline-flex; align-items:center; gap:5px;'>" + icon("calf", 14) + "<span>Sin arete</span></span>";

          hg += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; background:var(--superficie); border:1px solid var(--borde); border-radius:8px; padding:10px 12px;'>"
            + "<div>" + linkTag + " <span style='font-size:13px; color:var(--texto);'>" + cNom + "</span> <span class='meta' style='font-size:12px;'>· " + esc(cSx) + " · Nac: <b>" + esc(cFec) + "</b>" + pNac + "</span></div>"
            + "<div>" + estChip + "</div>"
            + "</div>";
        });
        hg += "</div>";
      } else {
        hg += "<p class='aviso' style='margin:8px 0;'>" + icon("info", 14) + "No tiene crías descendientes registradas en la base de datos.</p>";
      }
      hg += "</div>";

      // 4. Vista de Texto Resumido (Telegram / WhatsApp)
      var txtArbol = (g.texto_arbol || "").trim();
      if (txtArbol) {
        hg += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>"
          + "<h4 style='margin:0; font-size:13px;'>" + icon("notes", 15) + "Formato de Texto Compartible (Telegram / WhatsApp)</h4>"
          + "<button type='button' class='tema-btn' data-accion='copiar-arbol' style='font-size:11px; padding:4px 8px;'>" + icon("copy", 12) + "Copiar Árbol</button>"
          + "</div>"
          + "<pre style='background:var(--fondo); border:1px solid var(--borde); border-radius:6px; padding:10px; font-size:11.5px; line-height:1.45; overflow-x:auto; margin:0; font-family:var(--font-mono); white-space:pre-wrap;'>" + esc(txtArbol) + "</pre>"
          + "</div>";
      }

      return hg;
    }
    if (id === "repro") {
      var h = "";
      h += "<h4>Partos registrados</h4>" + tabla(f.partos, [
        ["fecha", "Fecha"], ["cria_tag", "Cría"], ["sexo_cria", "Sexo"],
        ["peso_nacimiento", "Peso nac.", "num"],
        ["estado_cria", "Estado", "text", function (v) {
          return String(v || "").toUpperCase() === "MUERTO"
            ? "<span class='chip rojo'>Muerto</span>" : "<span class='chip verde'>Vivo</span>";
        }]
      ], "Sin partos registrados.");
      h += "<h4>Servicios / IA</h4>" + tabla(f.servicios, [
        ["fecha", "Fecha"], ["tipo_servicio", "Tipo"], ["toro_pajilla", "Toro"],
        ["fep_calculada", "FEP", "text", function (v) { return v ? esc(fechaCorta(v)) : "—"; }],
        ["estado", "Estado", "text", function (v) { return chipResultado(v); }]
      ], "Sin servicios registrados.");
      h += "<h4>Diagnósticos de gestación</h4>" + tabla(f.diagnosticos, [
        ["fecha", "Fecha"], ["resultado", "Resultado", "text", function (v) { return chipResultado(v); }],
        ["dias_gestacion", "Días gest."]
      ], "Sin diagnósticos registrados.");
      if (f.ultimo_servicio && f.ultimo_servicio.fep_calculada) {
        h += "<p class='aviso'>" + icon("calendar", 14) + "FEP (parto estimado): <b>" + esc(fechaCorta(f.ultimo_servicio.fep_calculada)) + "</b></p>";
      }
      return h;
    }
    if (id === "sanidad") {
      return "<h4>Tratamientos y retiros</h4>"
        + tabla(f.tratamientos, [
          ["fecha", "Fecha"], ["producto", "Producto"], ["dosis", "Dosis"],
          ["fecha_fin_retiro_leche", "Fin leche", "text", function (v) { return v ? esc(v) : "—"; }],
          ["fecha_fin_retiro_carne", "Fin carne", "text", function (v) { return v ? esc(v) : "—"; }]
        ], "Sin tratamientos registrados.");
    }
    if (id === "leche") {
      var lac = f.lactancia || {};
      var h3 = "<h4>Estado de lactancia</h4>";
      if (lac && lac.fecha_parto) {
        h3 += "<p class='aviso'>" + icon("milk", 14) + esc(lac.estado) + " · <b>" + esc(lac.del_dias) + "</b> DEL (parto " + esc(lac.fecha_parto) + ")</p>";
      } else {
        h3 += vacio("Sin lactancia activa (sin parto registrado o es macho).");
      }
      h3 += "<h4>Controles de leche</h4>"
        + tabla(f.controles_leche, [["fecha", "Fecha"], ["litros", "Litros", "num"]], "Sin controles individuales.");
      var img = "<div class='grafico-wrap'><img src='/api/ficha/" + encodeURIComponent(f.tag)
        + "/grafico/lactancia' alt='Curva de lactancia' loading='lazy' data-onerror-hide='self'></div>";
      h3 += img;
      return h3;
    }
    if (id === "pesos") {
      var ult = f.pesajes && f.pesajes.length ? f.pesajes[0] : null;
      var h2 = "<h4>Historial de pesajes</h4>"
        + tabla(f.pesajes, [
          ["fecha", "Fecha"], ["peso_kg", "kg", "num"],
          ["gmd_calculada", "GMD (g/d)", "text", function (v) {
            if (v == null) return "—";
            var n = Number(v) * 1000;
            var c = n < 0 ? "rojo" : n > 0 ? "verde" : "gris";
            return "<span class='chip " + c + "'>" + esc(n.toFixed(0)) + "</span>";
          }]
        ], "Sin pesajes registrados.");
      if (ult) h2 += "<p class='aviso'>Último peso: <b>" + esc(ult.peso_kg) + " kg</b> el " + esc(fechaCorta(ult.fecha)) + "</p>";
      h2 += "<div class='grafico-wrap'><img src='/api/ficha/" + encodeURIComponent(f.tag)
        + "/grafico/peso' alt='Curva de peso' loading='lazy' data-onerror-hide='self'></div>";
      return h2;
    }
    // Tab "general"
    var h = "";

    // 1. Alerta de Retiro Sanitario si está en período de retiro
    if (f.en_retiro && f.retiros_activos && f.retiros_activos.length) {
      h += "<div class='card' style='background:var(--color-rojo-bg); color:var(--color-rojo-txt); border:1px solid var(--color-rojo-txt); padding:12px; border-radius:8px; margin-bottom:14px;'>"
        + "<div style='font-weight:bold; font-size:14px; margin-bottom:4px;'>" + icon("alert", 16) + "¡ATENCIÓN! Animal en período de retiro sanitario activo</div>"
        + "<p style='margin:0 0 6px 0; font-size:12.5px;'>No comercializar ni consumir productos de este animal hasta el cumplimiento de los días de retiro reglamentarios:</p>"
        + "<ul style='margin:0; padding-left:18px; font-size:12px;'>";
      f.retiros_activos.forEach(function (r) {
        var det = esc(r.producto || "Fármaco");
        if (r.dosis) det += " (" + esc(r.dosis) + ")";
        if (r.fecha_fin_retiro_leche) det += " · <b>Leche hasta:</b> " + esc(r.fecha_fin_retiro_leche);
        if (r.fecha_fin_retiro_carne) det += " · <b>Carne hasta:</b> " + esc(r.fecha_fin_retiro_carne);
        h += "<li>" + det + "</li>";
      });
      h += "</ul></div>";
    }

    // 2. Fila de KPIs rápidos
    var ultPesoTxt = "—";
    if (f.ultimo_peso && f.ultimo_peso.peso_kg != null) {
      ultPesoTxt = f.ultimo_peso.peso_kg + " kg";
    } else if (f.peso_nacimiento != null) {
      ultPesoTxt = f.peso_nacimiento + " kg (nac)";
    }

    h += "<div class='kpis' style='margin-bottom:14px;'>"
      + kpi(f.potrero ? esc(f.potrero) : "Sin asignar", "Potrero Actual")
      + kpi(f.edad_str ? esc(f.edad_str) : (f.edad_dias != null ? f.edad_dias + " d" : "—"), "Edad Zootécnica")
      + kpi(ultPesoTxt, "Último Pesaje")
      + kpi(f.en_retiro ? "EN RETIRO" : "APTO", "Inocuidad Sanitaria", f.en_retiro ? "alerta" : "ok")
      + "</div>";

    // 3. Tarjeta de Identificación & Genealogía (el pedigree completo vive en
    // la pestaña "Genealogía (3G)" -- sin botones duplicados hacia lo mismo)
    h += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
      + "<h4 style='margin:0;'>" + icon("dna") + "Identificación & Genealogía</h4>"
      + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:13px; margin-top:10px;'>"
      + "<div><span style='color:var(--texto-suave);'>Arete / Tag:</span> <b>" + esc(f.tag) + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Nombre:</span> <b>" + esc(f.nombre || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Sexo:</span> <b>" + esc(f.sexo || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Raza:</span> <b>" + esc(f.raza || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Color / Pelo:</span> <b>" + esc(f.color || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Categoría:</span> <b>" + esc(f.categoria_sg || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Fecha Nacimiento:</span> <b>" + esc(fechaCorta(f.fecha_nacimiento) || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Peso al Nacer:</span> <b>" + (f.peso_nacimiento ? f.peso_nacimiento + " kg" : "S/D") + "</b></div>";

    // Madre con enlace interactivo si existe
    var madreHtml = "S/D";
    if (f.madre && f.madre.tag) {
      madreHtml = "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(f.madre.tag) + "\" title='Ver ficha de la madre'><b>" + esc(f.madre.tag) + "</b> (" + esc(f.madre.nombre || f.madre.raza || "Madre") + ")</a>";
    }
    h += "<div><span style='color:var(--texto-suave);'>Madre:</span> " + madreHtml + "</div>";

    // Padre con enlace si existe
    var padreHtml = "S/D";
    if (f.padre && f.padre.tag) {
      padreHtml = "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(f.padre.tag) + "\" title='Ver ficha del padre'><b>" + esc(f.padre.tag) + "</b> (" + esc(f.padre.nombre || f.padre.raza || "Padre") + ")</a>";
    }
    h += "<div><span style='color:var(--texto-suave);'>Padre / Toro:</span> " + padreHtml + "</div>";

    // Abuelos Paternos & Maternos
    var g = f.genealogia_3g || {};
    var abPatTxt = (f.abuelo_pat && f.abuelo_pat.tag ? f.abuelo_pat.tag : (g.abuelo_pat && g.abuelo_pat.tag ? g.abuelo_pat.tag : "S/D"))
      + " / " + (f.abuela_pat && f.abuela_pat.tag ? f.abuela_pat.tag : (g.abuela_pat && g.abuela_pat.tag ? g.abuela_pat.tag : "S/D"));
    var abMatTxt = (f.abuelo_mat && f.abuelo_mat.tag ? f.abuelo_mat.tag : (g.abuelo_mat && g.abuelo_mat.tag ? g.abuelo_mat.tag : "S/D"))
      + " / " + (f.abuela_mat && f.abuela_mat.tag ? f.abuela_mat.tag : (g.abuela_mat && g.abuela_mat.tag ? g.abuela_mat.tag : "S/D"));

    h += "<div><span style='color:var(--texto-suave);'>Abuelos Pat.:</span> <b>" + esc(abPatTxt) + "</b></div>";
    h += "<div><span style='color:var(--texto-suave);'>Abuelos Mat.:</span> <b>" + esc(abMatTxt) + "</b></div>";

    h += "</div>";

    // Descendencia / Crías registradas directamente en la tarjeta de Identificación
    var criasGen = (f.crias && f.crias.length) ? f.crias : ((g.crias && g.crias.length) ? g.crias : (f.partos || []));
    if (criasGen.length) {
      h += "<div style='margin-top:12px; padding-top:10px; border-top:1px solid var(--borde);'>"
        + "<div style='font-size:12.5px; font-weight:600; margin-bottom:6px; color:var(--texto); display:flex; align-items:center; gap:6px;'>"
        + icon("cowCalf", 16) + "Descendencia / Crías Registradas (" + criasGen.length + "):</div>"
        + "<div style='display:flex; flex-wrap:wrap; gap:6px;'>";
      criasGen.forEach(function (c) {
        var cTag = c.cria_tag || c.tag || "Sin arete";
        var cSx = c.sexo_cria || c.sexo || "";
        var cFec = fechaCorta(c.fecha_parto || c.fecha || c.fecha_nacimiento);
        var chipTxt = "<b>" + esc(cTag) + "</b>" + (cSx ? " (" + esc(cSx) + ")" : "") + (cFec ? " [" + esc(cFec) + "]" : "");
        if (cTag !== "Sin arete") {
          h += "<a href='#' class='ficha-link chip verde' data-ir-ficha=\"" + esc(cTag) + "\" style='text-decoration:none; font-size:12px; padding:3px 8px; font-weight:bold; display:inline-flex; align-items:center; gap:5px;'>" + icon("calf", 13) + "<span>" + chipTxt + "</span></a>";
        } else {
          h += "<span class='chip gris' style='font-size:12px; padding:3px 8px; display:inline-flex; align-items:center; gap:5px;'>" + icon("calf", 13) + "<span>" + chipTxt + "</span></span>";
        }
      });
      h += "</div></div>";
    }

    h += "</div>";

    // 4. Tarjeta Estado Reproductivo Actual
    h += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
      + "<h4>" + icon("sperm") + "Estado Reproductivo Actual</h4>"
      + "<div style='font-size:14px; margin:8px 0;'>" + esc(f.estado_repro || "Sin datos") + "</div>";
    if (f.dias_abiertos != null) {
      h += "<p class='aviso' style='margin:4px 0;'>" + icon("hourglass", 14) + "Días abiertos (post-parto): <b>" + f.dias_abiertos + " días</b></p>";
    }
    if (f.ultimo_servicio && f.ultimo_servicio.fep_calculada) {
      h += "<p class='aviso' style='margin:4px 0;'>" + icon("calendar", 14) + "Fecha Estimada de Parto (FEP): <b>" + esc(fechaCorta(f.ultimo_servicio.fep_calculada)) + "</b></p>";
    }
    h += "</div>";

    // 5. Traslados de potrero recientes
    if (f.traslados && f.traslados.length) {
      h += "<h4>" + icon("truck") + "Últimos movimientos de potrero</h4>"
        + tabla(f.traslados, [
          ["fecha", "Fecha", "text", function (v) { return esc(fechaCorta(v)); }],
          ["origen", "Origen", "text", function (v) { return esc(v || "—"); }],
          ["destino", "Destino", "text", function (v) { return "<b>" + esc(v || "—") + "</b>"; }],
          ["motivo", "Motivo", "text", function (v) { return esc(v || "Rotación"); }]
        ], "Sin traslados registrados.");
    }

    // 6. Tarjeta de Código QR & Ficha Oficial PDF
    h += "<div class='card' style='padding:16px; margin-top:14px; background:var(--superficie); border:1px solid var(--borde); border-radius:8px;'>"
      + "<div style='display:flex; gap:16px; align-items:center; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:220px;'>"
      + "<h4 style='margin-top:0;'>" + icon("camera") + "Código QR & Ficha Técnica Zootécnica</h4>"
      + "<p style='font-size:12.5px; color:var(--texto-suave); margin:6px 0 12px 0; line-height:1.4;'>"
      + "El código QR contiene el enlace web directo a la PWA. Al escanearlo con la cámara de cualquier teléfono en el campo o manga, abre de inmediato esta ficha viva e interactiva. "
      + "Para llevar el registro impreso a la manga o carpeta de potrero, descargue la <b>Ficha Técnica A4 Oficial</b> con semáforos, genealogía y pesajes."
      + "</p>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap; align-items:center;'>"
      + "<a class='btn-guardar-manga' style='display:inline-flex; align-items:center; text-decoration:none; font-size:13px; padding:8px 14px;' href='/api/ficha/" + encodeURIComponent(f.tag) + "/qr.pdf' target='_blank' download>"
      + icon("filePdf", 16) + "Descargar Ficha Técnica PDF</a>"
      + "<span class='meta' style='font-size:12px;'>Payload: <code>" + esc(f.qr_payload || ("JA://animal/" + f.tag)) + "</code></span>"
      + "</div></div>"
      + "</div></div>";

    // 7. Fotos del animal
    var fotosHtml = "";
    if (f.fotos && f.fotos.length) {
      fotosHtml = "<div class='fotos-wrap' style='margin-top:8px; display:flex; gap:12px; flex-wrap:wrap;'>" + f.fotos.filter(function (x) { return x.url; })
        .map(function (x, idx) {
          return "<div class='foto-card' title='Toca para agrandar imagen'>"
            + "<img class='zoomable-img' src='" + esc(x.url) + "' alt='Foto #" + (idx + 1) + " · " + esc(f.tag) + "' loading='lazy' style='max-height:175px; width:auto; border-radius:8px; object-fit:cover; display:block;' data-onerror-hide='parent'>"
            + "<div class='zoom-hint'>" + icon("search", 12) + "Agrandar</div>"
            + "</div>";
        }).join("") + "</div>";
    } else {
      fotosHtml = vacio("Sin fotos para este animal.");
    }
    h += "<h4 style='margin-top:16px;'>" + icon("camera") + "Registro Fotográfico (Toca una foto para agrandarla)</h4>" + fotosHtml;

    return h;
  }
  function bindTabs(ficha) {
    var nav = document.getElementById("ficha-tabs");
    if (!nav) return;
    // Closure con la ficha de ESTE render: evita condiciones de carrera si se
    // abre otra ficha mientras se navega por las pestañas de la anterior.
    qa("nav.mini button", nav).forEach(function (b) {
      b.addEventListener("click", function () {
        qa("nav.mini button", nav).forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        var panel = document.getElementById("ficha-panel");
        if (panel) panel.innerHTML = fichaTab(b.getAttribute("data-tab"), ficha || window.__ultimaFicha || {});
      });
    });
  }

  /* ---------- Carga de datos ---------- */
  // Skeleton mimético por tipo de vista (más pulido que un bloque genérico).
  var ESQUELETOS = {
    tablero:   { kpis: 7, graf: 2, tabla: 7 },
    agenda:    { kpis: 0, graf: 0, tabla: 6 },
    inventario:{ kpis: 5, graf: 0, tabla: 11 },
    poblacion: { kpis: 4, graf: 0, tabla: 6 },
    genetica:  { kpis: 1, graf: 0, tabla: 10 },
    repro:     { kpis: 0, graf: 1, tabla: 12 },
    sanidad:   { kpis: 0, graf: 0, tabla: 9 },
    pasturas:  { kpis: 0, graf: 3, tabla: 8 },
    leche:     { kpis: 3, graf: 2, tabla: 8 },
    finanzas:  { kpis: 3, graf: 0, tabla: 8 },
    ficha:     { kpis: 0, graf: 1, tabla: 7 },
    manga:     { kpis: 0, graf: 0, tabla: 4 },
    captura:   { kpis: 0, graf: 0, tabla: 0 },
    gps:       { kpis: 0, graf: 0, tabla: 4 },
    sistema:   { kpis: 4, graf: 0, tabla: 0 },
    usuarios:  { kpis: 0, graf: 0, tabla: 5 }
  };
  function htmlSkeleton(v) {
    var cfg = ESQUELETOS[v] || ESQUELETOS.tablero;
    var h = "";
    if (cfg.kpis) {
      h += "<div class='sk-kpis'>";
      for (var i = 0; i < cfg.kpis; i++) h += "<div class='skeleton'></div>";
      h += "</div>";
    }
    if (cfg.graf) {
      h += "<div class='sk-graficos'>";
      for (var j = 0; j < cfg.graf; j++) h += "<div class='skeleton'></div>";
      h += "</div>";
    }
    if (cfg.tabla) {
      h += "<div class='sk-tabla'>";
      for (var k = 0; k < cfg.tabla; k++) h += "<div class='skeleton'></div>";
      h += "</div>";
    }
    return h || "<div class='skeleton h2'></div><div class='skeleton'></div>";
  }
  function skeleton(target, view) {
    target = target || vista;
    if (target) target.innerHTML = htmlSkeleton(view || actual);
  }
  // Cuenta los números de los KPIs desde 0 hasta su valor (solo valores puros).
  function animarKpis(root) {
    if (!root) return;
    qa(".kpi .num", root).forEach(function (el) {
      var txt = (el.textContent || "").trim();
      if (!/^-?[\d.]+$/.test(txt)) return; // "—", tags, "3.61a", etc.
      var destino = parseFloat(txt.replace(/\./g, ""));
      if (!isFinite(destino)) return;
      var dur = 550, t0 = null;
      function paso(ts) {
        if (!t0) t0 = ts;
        var p = Math.min((ts - t0) / dur, 1);
        p = 1 - Math.pow(1 - p, 3); // ease-out cubic
        el.textContent = String(Math.round(destino * p));
        if (p < 1) requestAnimationFrame(paso);
        else el.textContent = txt;
      }
      requestAnimationFrame(paso);
    });
  }
  // "Escribe" los trazos de cada icono SVG (efecto dibujado, tipo Lucide).
  // Mide cada path/line/circle con getTotalLength y lo anima con
  // stroke-dashoffset. Se salta con prefers-reduced-motion.
  function animarIconos(root) {
    if (!root) return;
    var redu = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (redu) return;
    qa("svg.svg-icon", root).forEach(function (svg, iSvg) {
      var hijos = qa("path,line,circle,rect,polyline,polygon", svg);
      if (!hijos.length) return;
      var largos = hijos.map(function (nd) {
        try { return nd.getTotalLength ? nd.getTotalLength() : 0; }
        catch (e) { return 0; }
      });
      var tieneTrazo = largos.some(function (l) { return l > 0; });
      if (!tieneTrazo) return;
      hijos.forEach(function (nd, i) {
        if (largos[i] <= 0) return;
        nd.style.strokeDasharray = String(largos[i]);
        nd.style.strokeDashoffset = String(largos[i]);
      });
      void svg.getBoundingClientRect(); // forzar reflow para arrancar la transición
      var delay = 80 + iSvg * 40; // pequeño escalonado entre iconos
      setTimeout(function () {
        hijos.forEach(function (nd, i) {
          if (largos[i] > 0) nd.style.strokeDashoffset = "0";
        });
      }, delay);
    });
  }
  // Monta el HTML de una vista con la animación de entrada (si `animar`) y
  // refresca los KPIs. En el polling en silencio se evita la animación para
  // no "parpadear" la pantalla cada minuto.
  function montarVista(el, html, animar) {
    if (!el) return;
    el.innerHTML = html;
    vincularTagsFicha(el); // tags clicables -> ficha del animal
    if (animar) {
      el.classList.remove("vista-entra");
      void el.offsetWidth; // reinicia la animación
      el.classList.add("vista-entra");
      setTimeout(function () { el.classList.remove("vista-entra"); }, 300);
      animarKpis(el);
      animarIconos(el);
    }
  }
  // Convierte la primera columna de tablas (cuando es un arete) en un enlace
  // que abre la ficha del animal sin volver a teclear.
  // Cubre los formatos de arete reales de la finca, incluyendo los sufijos
  // "-N" (generación/lote, ej. JA26-6, V064-6) y "_N" de las crías nuevas
  // (ej. NM_67965) -- sin esto, ~6% del hato activo no era clicable.
  var _TAG_RE = /^([A-Za-z]{0,4}\d{1,6}(-\d{1,3})?|[A-Za-z]{1,4}-\d{1,6}(-\d{1,3})?|\d{1,4}-\d{1,3}(-\d{1,3})?|[A-Za-z]{1,4}_\d{1,8})$/;
  var _CAB_NO_CLICK = /potrero|fecha|categor[ií]a|raza|c[óo]digo|banda|toro|bracket|peso/i;
  function abrirFichaDesdeTag(tag) {
    if (!tag) return;
    tag = String(tag).trim();
    if (!tag) return;

    var destino = qa("nav > button").filter(function (b) { return b.getAttribute("data-v") === "ficha"; })[0];
    if (!destino) {
      // Si estamos en la página standalone /ficha/<tag> (usa #ficha, no #vista)
      var destinoStandalone = vista || document.getElementById("ficha");
      if (typeof abrirFicha === "function" && destinoStandalone) {
        abrirFicha(tag, destinoStandalone, false, true);
        try { window.history.pushState(null, "", "/ficha/" + encodeURIComponent(tag)); } catch (e) {}
        try {
          document.title = "Ficha " + tag + " · Bitácora JA";
          var tituloTag = document.querySelector(".marca-titulo b");
          if (tituloTag) tituloTag.textContent = tag;
        } catch (e) {}
      } else {
        window.location = "/ficha/" + encodeURIComponent(tag);
      }
      return;
    }

    var inp = q("#f-tag");
    if (inp) inp.value = tag;

    qa("nav > button").forEach(function (x) { x.classList.remove("act"); });
    destino.classList.add("act");
    actual = "ficha";

    var barraFiltros = document.getElementById("barra-filtros");
    if (barraFiltros) barraFiltros.style.display = "";

    if (typeof abrirFicha === "function" && vista) {
      abrirFicha(tag, vista, true, true);
    } else {
      cargar(true);
    }
    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
  }
  window.abrirFichaDesdeTag = abrirFichaDesdeTag;
  window.abrirTabFicha = function (tabId) {
    var nav = document.getElementById("ficha-tabs");
    if (!nav) return;
    var btn = nav.querySelector("button[data-tab='" + tabId + "']");
    if (btn) btn.click();
  };
  // Delegado global de clics para HTML inyectado dinámicamente (innerHTML):
  // el CSP de producción (script-src 'self', sin unsafe-inline) bloquea
  // atributos onclick='' inline -- por eso todo lo que se genera con
  // cadenas HTML usa data-ir-ficha / data-ir-tab / data-accion en vez de
  // onclick, y un único listener delegado en document los resuelve aquí.
  document.addEventListener("click", function (e) {
    var elFicha = e.target.closest("[data-ir-ficha]");
    if (elFicha) {
      e.preventDefault();
      abrirFichaDesdeTag(elFicha.getAttribute("data-ir-ficha"));
      return;
    }
    var elTab = e.target.closest("[data-ir-tab]");
    if (elTab) {
      e.preventDefault();
      window.abrirTabFicha(elTab.getAttribute("data-ir-tab"));
      return;
    }
    var elAcc = e.target.closest("[data-accion]");
    if (elAcc) {
      var acc = elAcc.getAttribute("data-accion");
      if (acc === "exportar-inventario") { if (window.__exportarInventario) window.__exportarInventario(); }
      else if (acc === "exportar-retiros") { if (window.__exportarRetiros) window.__exportarRetiros(); }
      else if (acc === "reload") { location.reload(); }
      else if (acc === "copiar-arbol") {
        var card = elAcc.closest(".card");
        var pre = card && card.querySelector("pre");
        if (pre) navigator.clipboard.writeText(pre.innerText).then(function () { alert("Árbol copiado al portapapeles"); });
      }
    }
  });
  // "error" no burbujea, así que este delegado necesita fase de captura.
  document.addEventListener("error", function (e) {
    var el = e.target;
    if (!el || el.tagName !== "IMG" || !el.hasAttribute("data-onerror-hide")) return;
    var objetivo = el.getAttribute("data-onerror-hide") === "parent" ? el.parentElement : el;
    if (objetivo) objetivo.style.display = "none";
  }, true);
  function vincularTagsFicha(root) {
    if (!root) return;
    if (!qa("nav > button").length) return; // solo en el dashboard con navegación
    var trs = qa("table tr", root);
    trs.forEach(function (tr) {
      var celdas = qa("td", tr);
      if (!celdas.length) return;
      var first = celdas[0];
      if (!first || first.querySelector("a, button, input")) return;
      var txt = (first.textContent || "").trim();
      if (!_TAG_RE.test(txt)) return;
      var tablaEl = first.closest("table");
      if (!tablaEl) return;
      var encabezado = tablaEl.querySelector("tr");
      var th0 = encabezado ? encabezado.querySelector("th") : null;
      if (th0 && _CAB_NO_CLICK.test(th0.textContent || "")) return;
      var link = document.createElement("a");
      link.href = "#";
      link.className = "ficha-link";
      link.title = "Ver ficha de " + txt;
      link.textContent = txt;
      link.addEventListener("click", function (e) {
        e.preventDefault();
        abrirFichaDesdeTag(txt);
      });
      first.textContent = "";
      first.appendChild(link);
    });
  }
  function fetchJSON(url, cb, target) {
    target = target || vista;
    var ctrl = ("AbortController" in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctrl) ctrl.abort(); }, 25000);
    fetch(url, ctrl ? { signal: ctrl.signal } : {}).then(function (r) {
      if (r.status === 401) { window.location = "/login"; throw new Error("no autorizado"); }
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (d) { clearTimeout(to); cb(d); })
      .catch(function (e) {
        clearTimeout(to);
        if (target) target.innerHTML = "❌ No se pudo cargar (" + esc(e && e.message || e) + "). <button data-accion='reload'>Reintentar</button>";
      });
  }
  function abrirFicha(tag, target, showIdent, animar) {
    if (animar === undefined) animar = true;
    if (animar) skeleton(target, "ficha");
    fetchJSON("/api/ficha/" + encodeURIComponent(tag), function (f) {
      if (!f.existe) {
        if (target) montarVista(target, "<h3>" + icon("cow") + "Ficha animal</h3><p>❌ Sin registro para <b>" + esc(tag) + "</b>.</p>"
          + "<p class='aviso'>💡 Si viene de escanear un arete, puede que el tag aún no esté en la base. "
          + "Pruebe escribiendo el número sin guiones (ej. " + esc(String(tag).replace(/\D/g, "") || tag) + ").</p>", animar);
        return;
      }
      window.__ultimaFicha = f;
      montarVista(target, fichaHtml(f, !!showIdent), animar);
      bindTabs(f);
      if (showIdent) bindIdent();
    }, target);
  }
  // Devuelve el candidato escrito en el campo #f-tag si aplica (para RFID).
  function obtenerTextoIdent() {
    var t = (q("#f-tag") && q("#f-tag").value || "").trim();
    return t || null;
  }
  function pintarSugerencias(res) {
    var out = document.getElementById("ident-resultado");
    if (!out) return;
    var mensaje = document.getElementById("ident-estado");
    if (res.existe) { abrirFicha(res.tag, vista, true); return; }
    if (res.error) {
      if (mensaje) mensaje.textContent = "";
      out.innerHTML = "<p class='aviso'>❌ " + esc(res.error) + "</p>";
      return;
    }
    if (res.ocr_tag) {
      if (mensaje) mensaje.textContent = "🔍 OCR leyó: " + esc(res.ocr_tag) + (res.confianza ? " (confianza " + Math.round(res.confianza * 100) + "%)" : "");
    } else if (mensaje) {
      mensaje.textContent = "";
    }
    if (res.sugerencias && res.sugerencias.length) {
      var h = "<p class='aviso'>¿Quiso decir alguno de estos?</p>";
      h += "<div class='fotos-wrap'>" + res.sugerencias.map(function (s) {
        return "<button data-tag='" + esc(s.tag) + "' class='chip' style='font-size:13px'>" + icon("cow", 14) + esc(s.tag)
          + (s.nombre ? " " + esc(s.nombre) : "") + "</button>";
      }).join("") + "</div>";
      out.innerHTML = h;
      qa("button[data-tag]", out).forEach(function (b) {
        b.addEventListener("click", function () {
          if (q("#f-tag")) q("#f-tag").value = b.getAttribute("data-tag");
          abrirFicha(b.getAttribute("data-tag"), vista, true);
        });
      });
    } else {
      out.innerHTML = "<p class='aviso'>" + esc(res.mensaje || "No se encontró ese identificador en la base.") + "</p>";
    }
  }
  var _qrStream = null;
  var _qrTimer = null;
  function detenerEscanerQR() {
    if (_qrTimer) { clearInterval(_qrTimer); _qrTimer = null; }
    if (_qrStream) {
      _qrStream.getTracks().forEach(function (t) { t.stop(); });
      _qrStream = null;
    }
    var v = document.getElementById("qr-video");
    if (v) { v.style.display = "none"; v.srcObject = null; }
    var boton = document.getElementById("btn-scan-qr");
    if (boton) boton.textContent = "";
    var est = document.getElementById("ident-estado");
    if (boton) boton.innerHTML = icon("camera") + "Escanear QR";
    if (est && est.getAttribute("data-scan") === "1") est.textContent = "";
  }
  function escanearQRCamara() {
    var estado = document.getElementById("ident-estado");
    var video = document.getElementById("qr-video");
    var boton = document.getElementById("btn-scan-qr");
    var out = document.getElementById("ident-resultado");
    if (!video || !boton) return;
    if (_qrStream) { detenerEscanerQR(); return; }
    if (!("BarcodeDetector" in window)) {
      if (estado) estado.textContent = "Tu navegador no permite escanear QR con cámara (usa Chrome/Edge). Escribe el código en el campo Tag.";
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (estado) estado.textContent = "Cámara no disponible en este dispositivo/navegador.";
      return;
    }
    if (estado) { estado.setAttribute("data-scan", "1"); estado.textContent = "Apuntando a un QR de ficha… toca 'Escanear QR' para detener."; }
    if (out) out.innerHTML = "";
    boton.innerHTML = icon("xmark") + "Detener";
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } } })
      .then(function (stream) {
        _qrStream = stream;
        video.srcObject = stream;
        video.style.display = "block";
        video.play().catch(function () { /* noop */ });
        var detector = new window.BarcodeDetector({ formats: ["qr_code"] });
        _qrTimer = setInterval(function () {
          if (!_qrStream) return;
          detector.detect(video).then(function (codes) {
            if (!codes || !codes.length) return;
            var value = (codes[0].rawValue || "").trim();
            var m = value.match(/JA:\/\/animal\/([A-Za-z0-9_-]+)/i) || value.match(/\/ficha\/([A-Za-z0-9_-]+)\/?/i);
            if (!m) { if (estado) estado.textContent = "QR leído, pero no es de una ficha del hato."; return; }
            detenerEscanerQR();
            var tag = m[1];
            if (q("#f-tag")) q("#f-tag").value = tag;
            abrirFicha(tag, vista, true, true);
          }).catch(function () { /* siguiente frame */ });
        }, 350);
      })
      .catch(function (e) {
        if (estado) { estado.removeAttribute("data-scan"); estado.textContent = "No se pudo abrir la cámara (permiso o HTTPS). " + (e && e.name || ""); }
        boton.innerHTML = icon("camera") + "Escanear QR";
      });
  }
  function bindIdent() {
    var btn = document.getElementById("btn-ident");
    var file = document.getElementById("f-ident-foto");
    var btnQr = document.getElementById("btn-scan-qr");
    if (!btn || !file) return;
    btn.addEventListener("click", function () {
      var estado = document.getElementById("ident-estado");
      var out = document.getElementById("ident-resultado");
      if (out) out.innerHTML = "";
      if (estado) estado.textContent = "⏳ Identificando…";
      if (file.files && file.files[0]) {
        var fd = new FormData();
        fd.append("foto", file.files[0]);
        fetch("/api/identificar", { method: "POST", body: fd })
          .then(function (r) { if (r.status === 401) { window.location = "/login"; throw new Error("no autorizado"); } if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
          .then(pintarSugerencias)
          .catch(function (e) { if (estado) estado.textContent = "❌ " + (e && e.message || e); });
      } else {
        var t = obtenerTextoIdent();
        if (!t) { if (estado) estado.textContent = "Escriba el arete/RFID arriba o elija una foto."; return; }
        var fd2 = new FormData();
        fd2.append("texto", t);
        fetch("/api/identificar", { method: "POST", body: fd2 })
          .then(function (r) { if (r.status === 401) { window.location = "/login"; throw new Error("no autorizado"); } if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
          .then(pintarSugerencias)
          .catch(function (e) { if (estado) estado.textContent = "❌ " + (e && e.message || e); });
      }
    });
    if (btnQr) btnQr.addEventListener("click", escanearQRCamara);
  }
  // Autocompletar (datalist) para tag y potrero.
  function rellenarDatalist(id, items) {
    var dl = document.getElementById(id);
    if (!dl) return;
    dl.innerHTML = items.map(function (x) { return "<option value='" + esc(x) + "'>"; }).join("");
  }
  function sugerirDesde(q) {
    if (!q) return;
    fetch("/api/buscar?q=" + encodeURIComponent(q)).then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.animales) rellenarDatalist("dl-tags", d.animales.map(function (a) { return a.tag; }));
        if (d && d.potreros) rellenarDatalist("dl-potreros", d.potreros.map(function (p) { return p.nombre || p.codigo; }));
      }).catch(function () { /* best-effort */ });
  }
  var _deb = null;
  function onInputSugerir(ev) {
    var v = (ev.target.value || "").trim();
    if (!v) { cargarListaPotreros(); return; }
    clearTimeout(_deb);
    _deb = setTimeout(function () { sugerirDesde(v); }, 250);
  }
  // Llena el datalist de potreros con la lista COMPLETA (selector desplegable).
  function cargarListaPotreros() {
    fetch("/api/buscar?q=").then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.potreros) {
          rellenarDatalist("dl-potreros", d.potreros.map(function (p) { return p.nombre || p.codigo; }));
        }
      }).catch(function () { /* best-effort */ });
  }
  function cargar(animar) {
    if (animar === undefined) animar = true;

    var barraFiltros = document.getElementById("barra-filtros");
    if (barraFiltros) {
      if (actual === "tablero" || actual === "ficha" || actual === "inventario") {
        barraFiltros.style.display = "";
      } else {
        barraFiltros.style.display = "none";
      }
    }

    if (actual === "ficha") {
      var t = (q("#f-tag") && q("#f-tag").value || "").trim();
      if (!t) {
        if (vista) montarVista(vista, "<h3>" + icon("cow") + "Identificar / Ficha animal</h3><p class='aviso'>Escribe un arete, RFID o nombre (ej. 47, N069, JA26) y pulsa Cargar — o usa el panel de foto de abajo.</p>" + identPanelHtml(), animar);
        if (vista) bindIdent();
        return;
      }
      abrirFicha(t, vista, true, animar);
      return;
    }

    if (actual === "manga") {
      if (!animar) return; // En polling silencioso no resetear la manga
      if (vista) {
        montarVista(vista, renderManga(), animar);
        bindManga();
      }
      return;
    }

    if (actual === "captura") {
      if (!animar) return; // En polling silencioso no resetear captura
      if (vista) {
        montarVista(vista, renderCaptura(), animar);
        bindCaptura();
      }
      return;
    }

    if (actual === "ayuda") {
      if (!animar) return; // En polling silencioso no resetear ayuda
      if (vista) {
        montarVista(vista, renderAyuda(), animar);
        bindAyuda();
      }
      return;
    }

    if (actual === "gps") {
      if (animar) skeleton(vista, "gps");
      var fFecha = _fechaFiltroRutas || (q("#filtro-fecha-rutas") && q("#filtro-fecha-rutas").value) || new Date().toISOString().slice(0, 10);
      fetchJSON("/api/telemetria/rutas?fecha=" + encodeURIComponent(fFecha), function (d) {
        if (!vista) return;
        montarVista(vista, renderGps(d, fFecha), animar);
        bindGps(d, fFecha);
      }, animar ? vista : null);
      return;
    }

    if (actual === "sistema") {
      if (animar) skeleton(vista, "sistema");
      fetchJSON("/api/sistema", function (d) {
        if (!vista) return;
        montarVista(vista, renderSistema(d), animar);
        bindSistema();
      }, animar ? vista : null);
      return;
    }

    if (actual === "usuarios") {
      if (!animar) return; // En polling silencioso no resetear el formulario de usuarios
      if (animar) skeleton(vista, "usuarios");
      fetchJSON("/api/usuarios", function (d) {
        if (!vista) return;
        montarVista(vista, renderUsuarios(d), animar);
        bindUsuarios(d);
      }, animar ? vista : null);
      return;
    }

    var pot = (q("#f-potrero") && q("#f-potrero").value || "").trim();
    var url = "/api/" + actual + (pot && actual === "tablero" ? "?potrero=" + encodeURIComponent(pot) : "");
    if (animar) skeleton(vista, actual);
    fetchJSON(url, function (d) {
      if (!vista) return;
      var html;
      if (actual === "tablero") html = renderTablero(d);
      else if (actual === "repro") html = renderRepro(d);
      else if (actual === "sanidad") html = renderSanidad(d);
      else if (actual === "pasturas") html = renderPasturas(d);
      else if (actual === "leche") html = renderLeche(d);
      else if (actual === "inventario") html = renderInventario(d);
      else if (actual === "poblacion") html = renderInventario(d); // alias (vista unificada)
      else if (actual === "genetica") html = renderGenetica(d);
      else if (actual === "agenda") html = renderAgenda(d);
      else if (actual === "finanzas") html = renderFinanzas(d);
      montarVista(vista, html, animar);
      if (actual === "leche") bindLeche();
      if (actual === "finanzas") bindFinanzas();
    }, animar ? vista : null);
  }

  /* ---------- Badges de contadores en la navegación ---------- */
  var VISTAS_BADGE = ["agenda", "repro", "sanidad"];
  var badgesCache = {};
  function crearBadgesNav() {
    VISTAS_BADGE.forEach(function (v) {
      var btn = qa("nav > button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
      if (!btn || btn.querySelector(".nav-badge")) return;
      var span = document.createElement("span");
      span.className = "nav-badge";
      span.textContent = "";
      btn.appendChild(span);
    });
  }
  function actualizarBadges() {
    if (navigator.onLine === false) return;
    fetch("/api/badges").then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) {
        badgesCache = d || {};
        VISTAS_BADGE.forEach(function (v) {
          var btn = qa("nav > button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
          if (!btn) return;
          var span = btn.querySelector(".nav-badge");
          if (!span) return;
          var n = parseInt(d && d[v], 10) || 0;
          if (n > 0) { span.textContent = n > 99 ? "99+" : String(n); span.classList.add("on"); }
          else { span.textContent = ""; span.classList.remove("on"); }
        });
        // Campana del header (total = agenda) + notificación al aumentar.
        var camp = document.getElementById("notif-dot");
        var nA = parseInt(d && d.agenda, 10) || 0;
        if (camp) {
          if (nA > 0) { camp.textContent = nA > 99 ? "99+" : String(nA); camp.classList.add("on"); }
          else { camp.textContent = ""; camp.classList.remove("on"); }
        }
        var prev = window.__agendaPrev || -1;
        if (prev >= 0 && nA > prev && nA > 0 && document.hidden
            && "Notification" in window && Notification.permission === "granted") {
          try {
            var notif = new Notification("Bitácora JA", {
              body: nA + " aviso(s) pendientes en la Agenda (partos, secado, retiros).",
              tag: "bitacora-aviso", icon: "/static/icon-192.png"
            });
            notif.onclick = function () { window.focus(); };
          } catch (e) { /* noop */ }
        }
        window.__agendaPrev = nA;
      }).catch(function () { /* sin red: se ocultan */ });
  }

  function setupCampana() {
    var camp = document.getElementById("btn-notif");
    if (!camp) return;
    camp.addEventListener("click", function () {
      if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission().then(function (p) {
          // concedida o denegada: se guarda implícito en el navegador
          var s = document.getElementById("notif-dot");
          if (s) s.title = p === "granted" ? "Notificaciones activadas" : "Notificaciones apagadas";
        });
      }
      var destino = qa("nav > button").filter(function (b) { return b.getAttribute("data-v") === "agenda"; })[0];
      if (destino) destino.click();
    });
  }

  function setupHeaderAyuda() {
    var btnAyuda = document.getElementById("btn-ayuda");
    if (!btnAyuda) return;
    btnAyuda.addEventListener("click", function () {
      if (fb) {
        window.location = "/?v=ayuda";
        return;
      }
      qa("nav > button").forEach(function (x) { x.classList.remove("act"); });
      actual = "ayuda";
      var barraFiltros = document.getElementById("barra-filtros");
      if (barraFiltros) barraFiltros.style.display = "none";
      cargar(true);
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
    });
  }

  qa("nav > button").forEach(function (b) {
    b.addEventListener("click", function () {
      qa("nav > button").forEach(function (x) { x.classList.remove("act"); });
      b.classList.add("act");
      actual = b.getAttribute("data-v");
      cargar();
      if (VISTAS_BADGE.indexOf(actual) !== -1) {
        // Al abrir la vista, los datos frescos actualizan su badge al instante.
        var span = b.querySelector(".nav-badge");
        if (span) { span.textContent = ""; span.classList.remove("on"); }
      }
    });
  });
  // Cambia de pestaña activa sin recargar (usado por el buscador de arriba:
  // si el usuario escribe un tag/potrero estando en OTRA vista, hay que
  // saltar a la vista que sabe usar ese campo antes de cargar).
  function irAVista(v) {
    actual = v;
    qa("nav > button").forEach(function (x) { x.classList.remove("act"); });
    var destino = qa("nav > button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
    if (destino) destino.classList.add("act");
  }
  // Cargar manual (botón o Enter): el tag manda a Ficha y el potrero manda a
  // Tablero (únicas vistas que usan esos campos), sin importar qué pestaña
  // estaba activa antes.
  function cargarManual() {
    var t = (q("#f-tag") && q("#f-tag").value || "").trim();
    var pot = (q("#f-potrero") && q("#f-potrero").value || "").trim();
    if (t && actual !== "ficha") irAVista("ficha");
    else if (!t && pot && actual !== "tablero") irAVista("tablero");
    cargar();
  }
  var btn = document.getElementById("btn-cargar");
  if (btn) btn.addEventListener("click", cargarManual);
  // Enter en los campos de filtro dispara Cargar.
  ["f-potrero", "f-tag"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("keydown", function (e) { if (e.key === "Enter") cargarManual(); });
  });
  // Autocompletar: tecleo en tag/potrero consulta /api/buscar y llena datalist.
  var inpPotrero = document.getElementById("f-potrero");
  var inpTag = document.getElementById("f-tag");
  if (inpTag) inpTag.addEventListener("input", onInputSugerir);
  if (inpPotrero) {
    inpPotrero.addEventListener("input", onInputSugerir);
    // Al enfocar (o tocar en móvil) se ofrece la lista completa para elegir.
    inpPotrero.addEventListener("focus", function () { cargarListaPotreros(); });
    inpPotrero.addEventListener("click", function () { cargarListaPotreros(); });
  }

  /* ---------- Online/offline + polling ---------- */
  var barra = document.getElementById("barra-red");
  function actualizarRed() {
    if (!barra) return;
    if (navigator.onLine === false) barra.classList.add("visible");
    else barra.classList.remove("visible");
  }
  window.addEventListener("online", actualizarRed);
  window.addEventListener("offline", actualizarRed);
  actualizarRed();

  var reloj = document.getElementById("reloj-hora");
  function tick() {
    if (reloj) {
      try { reloj.textContent = new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }); } catch (e) { /* noop */ }
    }
  }
  tick();
  setInterval(function () {
    tick();
    if (document.hidden || navigator.onLine === false || actual !== "tablero") {
      if (!document.hidden) actualizarBadges();
      return;
    }
    cargar(false); // polling en silencio: sin animación ni skeleton, solo en el tablero
    actualizarBadges();
  }, 60000);

  /* ---------- Selección de Tema (4 Modos) ---------- */
  var selectTema = document.getElementById("select-tema");
  function aplicarTema(modo) {
    if (modo === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else if (modo === "light") document.documentElement.setAttribute("data-theme", "light");
    else if (modo === "sun") document.documentElement.setAttribute("data-theme", "sun");
    else document.documentElement.setAttribute("data-theme", "green");
    try { localStorage.setItem("pwa_tema", modo || "green"); } catch (e) { /* noop */ }
    if (selectTema) selectTema.value = modo || "green";
  }
  function temaInicial() {
    try { return localStorage.getItem("pwa_tema") || "green"; } catch (e) { return "green"; }
  }
  aplicarTema(temaInicial());
  if (selectTema) {
    selectTema.addEventListener("change", function () {
      aplicarTema(selectTema.value);
    });
  }

  /* Al cerrar sesión, borrar la caché del Service Worker (offline lite)
     antes de navegar a /logout. Sin esto, en un equipo compartido alguien
     podría desconectarse de internet después de que otra persona cerró
     sesión y aún ver los datos de la finca que quedaron guardados
     localmente (el SW cachea /api/* y /media/* para el modo sin señal). */
  qa('a[href="/logout"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      if (!("caches" in window)) return; // navegador sin soporte: deja el link normal
      e.preventDefault();
      caches.keys().then(function (keys) {
        return Promise.all(keys.map(function (k) { return caches.delete(k); }));
      }).catch(function () { /* best-effort */ }).then(function () {
        window.location.href = "/logout";
      });
    });
  });

  /* ---------- Página dedicada /ficha/<tag> (destino del QR) ---------- */
  var fb = document.getElementById("ficha");
  function arrancarDesdeUrl() {
    var params = new URLSearchParams(window.location.search);
    var v = params.get("v");
    var pot = params.get("potrero");
    var tag = params.get("tag");
    // Alias: la vista de población se unificó dentro de Inventario.
    if (v === "poblacion") v = "inventario";
    if (v === "ayuda") {
      qa("nav > button").forEach(function (x) { x.classList.remove("act"); });
      actual = "ayuda";
      var barraFiltros = document.getElementById("barra-filtros");
      if (barraFiltros) barraFiltros.style.display = "none";
      cargar(true);
      return;
    }
    if (pot && q("#f-potrero")) q("#f-potrero").value = pot;
    if (tag && q("#f-tag")) q("#f-tag").value = tag;
    if (!v && (pot || tag)) v = pot ? "tablero" : "ficha";
    if (v && qa("nav > button").length) {
      var destino = qa("nav > button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
      if (destino) {
        destino.click(); // activa pestaña + cargar() con los campos ya puestos
        return;
      }
    }
    cargar();
  }

  /* ---------- Visor Lightbox de Imágenes (Agrandar al dar clic) ---------- */
  function mostrarLightbox(src, titulo) {
    if (!src) return;
    var existente = document.getElementById("lightbox-visor");
    if (existente && existente.parentNode) existente.parentNode.removeChild(existente);

    var lb = document.createElement("div");
    lb.id = "lightbox-visor";
    lb.className = "lightbox-overlay";
    lb.setAttribute("role", "dialog");
    lb.setAttribute("aria-label", "Visor de imagen agrandada");

    var tit = titulo || "Fotografía del Animal";
    var h = "<div class='lightbox-topbar'>"
      + "<div class='lightbox-titulo'>" + icon("camera", 16) + esc(tit) + "</div>"
      + "<div class='lightbox-acciones'>"
      + "<button type='button' id='lb-btn-zoom' class='lightbox-btn' title='Zoom 1.5x'>" + icon("search", 13) + "<span>Zoom</span></button>"
      + "<a href='" + esc(src) + "' target='_blank' download class='lightbox-btn' title='Descargar / Abrir en pestaña nueva'>" + icon("download", 13) + "<span>Descargar</span></a>"
      + "<button type='button' id='lb-btn-cerrar' class='lightbox-btn lightbox-btn-cerrar' title='Cerrar (Esc)'>" + icon("xmark", 13) + "<span>Cerrar</span></button>"
      + "</div></div>"
      + "<div class='lightbox-img-wrap' id='lb-img-wrap'>"
      + "<img class='lightbox-img' id='lb-img' src='" + esc(src) + "' alt='" + esc(tit) + "'>"
      + "</div>"
      + "<div style='color:rgba(255,255,255,0.7); font-size:11.5px; margin-top:8px;'>Toca la imagen para alternar zoom · Presiona Cerrar o Esc para salir</div>";

    lb.innerHTML = h;
    document.body.appendChild(lb);
    document.body.style.overflow = "hidden"; // bloquear scroll del fondo

    function cerrar() {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
      lb.style.opacity = "0";
      setTimeout(function () { if (lb && lb.parentNode) lb.parentNode.removeChild(lb); }, 150);
    }

    function onKey(e) {
      if (e.key === "Escape") cerrar();
    }
    window.addEventListener("keydown", onKey);

    var img = lb.querySelector("#lb-img");
    var btnCerrar = lb.querySelector("#lb-btn-cerrar");
    var btnZoom = lb.querySelector("#lb-btn-zoom");

    if (btnCerrar) btnCerrar.addEventListener("click", cerrar);

    function toggleZoom(e) {
      if (e) e.stopPropagation();
      if (!img) return;
      img.classList.toggle("zoomed");
      if (btnZoom) {
        var isZoomed = img.classList.contains("zoomed");
        var sp = btnZoom.querySelector("span");
        if (sp) sp.textContent = isZoomed ? "Alejar" : "Zoom";
      }
    }

    if (img) img.addEventListener("click", toggleZoom);
    if (btnZoom) btnZoom.addEventListener("click", toggleZoom);

    lb.addEventListener("click", function (e) {
      if (e.target === lb || e.target.id === "lb-img-wrap") {
        cerrar();
      }
    });
  }
  window.mostrarLightbox = mostrarLightbox;

  function setupLightboxVisor() {
    document.addEventListener("click", function (e) {
      var target = e.target;
      if (!target) return;
      var imgEl = null;
      if (target.tagName === "IMG") {
        if (target.classList.contains("zoomable-img") ||
            target.closest(".fotos-wrap") ||
            target.closest(".foto-card") ||
            target.closest(".foto-card-mini") ||
            (target.classList.contains("avatar") && target.closest(".ficha-head")) ||
            target.closest(".grafico-wrap")) {
          imgEl = target;
        }
      } else {
        var card = target.closest(".foto-card") || target.closest(".foto-card-mini") || target.closest(".grafico-wrap");
        if (card) {
          imgEl = card.querySelector("img");
        }
      }

      if (imgEl && imgEl.src) {
        e.preventDefault();
        var titulo = imgEl.alt || imgEl.title || "Imagen";
        var tagAnimal = (window.__ultimaFicha && window.__ultimaFicha.tag) || (document.body.getAttribute("data-tag")) || "";
        if (tagAnimal && titulo.indexOf(tagAnimal) === -1) {
          titulo += " · Animal " + tagAnimal;
        }
        mostrarLightbox(imgEl.src, titulo);
      }
    });
  }

  /* ---------- Instalación de la Aplicación (PWA Standalone) ---------- */
  function setupInstalacionApp() {
    var deferredPrompt = null;
    var btnInstalar = document.getElementById("btn-instalar-app");
    var modalInstalar = document.getElementById("modal-instalar-app");
    var cuerpoGuia = document.getElementById("instalar-cuerpo-guia");
    var btnCerrar = document.getElementById("btn-cerrar-instalar");
    var btnEntendido = document.getElementById("btn-entendido-instalar");

    var esStandalone = window.matchMedia("(display-mode: standalone)").matches 
      || window.navigator.standalone 
      || document.referrer.indexOf("android-app://") !== -1;
    var esIos = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

    function cerrarModalGuia() {
      if (modalInstalar) modalInstalar.style.display = "none";
    }

    if (btnCerrar) btnCerrar.addEventListener("click", cerrarModalGuia);
    if (btnEntendido) btnEntendido.addEventListener("click", cerrarModalGuia);
    if (modalInstalar) {
      modalInstalar.addEventListener("click", function (e) {
        if (e.target === modalInstalar) cerrarModalGuia();
      });
    }

    // Si ya está corriendo como app instalada (standalone), ocultar botón
    if (esStandalone) {
      if (btnInstalar) btnInstalar.style.display = "none";
      return;
    }

    // En iOS o navegadores estándar, mostrar botón de instalación en el header
    if (btnInstalar) {
      btnInstalar.style.display = "inline-flex";
    }

    // Captura de evento de instalación nativa (Chrome, Edge, Brave, Android)
    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
      if (btnInstalar) {
        btnInstalar.style.display = "inline-flex";
      }
    });

    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      if (btnInstalar) btnInstalar.style.display = "none";
    });

    if (btnInstalar) {
      btnInstalar.addEventListener("click", function () {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          deferredPrompt.userChoice.then(function (choice) {
            if (choice && choice.outcome === "accepted") {
              if (btnInstalar) btnInstalar.style.display = "none";
            }
            deferredPrompt = null;
          });
        } else if (esIos) {
          if (cuerpoGuia) {
            cuerpoGuia.innerHTML = 
              "<div class='guia-pasos-box'>" +
                "<p class='guia-intro'>Instala <b>Bitácora JA</b> en tu iPhone o iPad para usarla a pantalla completa y sin conexión:</p>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>1</div>" +
                  "<div class='paso-txt'>Toca el botón <b>Compartir</b> <svg class='svg-icon inline' viewBox='0 0 24 24' width='16' height='16' stroke='currentColor' stroke-width='2' fill='none'><path d='M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8'/><polyline points='16 6 12 2 8 6'/><line x1='12' y1='2' x2='12' y2='15'/></svg> en la barra inferior de Safari.</div>" +
                "</div>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>2</div>" +
                  "<div class='paso-txt'>Desliza la lista de opciones y toca <b>'Agregar a la pantalla de inicio'</b> ➕.</div>" +
                "</div>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>3</div>" +
                  "<div class='paso-txt'>Toca <b>'Agregar'</b> en la esquina superior derecha. ¡Quedará con el logo oficial en tu inicio!</div>" +
                "</div>" +
              "</div>";
          }
          if (modalInstalar) modalInstalar.style.display = "flex";
        } else {
          if (cuerpoGuia) {
            cuerpoGuia.innerHTML = 
              "<div class='guia-pasos-box'>" +
                "<p class='guia-intro'>Instala <b>Bitácora JA</b> como aplicación nativa en tu dispositivo:</p>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>1</div>" +
                  "<div class='paso-txt'>Toca los <b>tres puntos (⋮)</b> del menú arriba a la derecha en Chrome o Edge.</div>" +
                "</div>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>2</div>" +
                  "<div class='paso-txt'>Selecciona la opción <b>'Instalar aplicación'</b> o <b>'Agregar a la pantalla principal'</b>.</div>" +
                "</div>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>3</div>" +
                  "<div class='paso-txt'>Confirma tocando <b>'Instalar'</b>. Se abrirá sola a pantalla completa sin barra de direcciones.</div>" +
                "</div>" +
              "</div>";
          }
          if (modalInstalar) modalInstalar.style.display = "flex";
        }
      });
    }
  }

  // Inicializar visor lightbox para fichas y gráficos en toda la app
  setupLightboxVisor();
  setupInstalacionApp();

  if (fb) {
    var tag = document.body.getAttribute("data-tag") || "";
    abrirFicha(tag, fb, false, false); // QR ya identifica el animal: sin panel de foto
    setupChatModal();
    setupHeaderAyuda();
  } else {
    setupSyncOffline();
    setupChatModal();
    setupVozModal();
    crearBadgesNav();
    setupCampana();
    setupHeaderAyuda();
    actualizarBadges();
    actualizarContadorSync();
    enviarTelemetriaSilenciosa("apertura_app");
    setInterval(function () {
      enviarTelemetriaSilenciosa("latido_periodico");
    }, 180000);
    // Latido de presencia en vivo de usuario (cada 60 segundos con pestaña activa)
    setInterval(function () {
      if (!document.hidden && navigator.onLine) {
        fetch("/api/heartbeat", { method: "POST" }).catch(function () {});
      }
    }, 60000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && navigator.onLine) {
        fetch("/api/heartbeat", { method: "POST" }).catch(function () {});
      }
    });
    // Primer refresco de badges y cola offline al reconectar tras estar sin señal.
    window.addEventListener("online", function () {
      actualizarBadges();
      sincronizarColaOffline(false);
    });
    cargarUsuario().finally(function () {
      arrancarDesdeUrl();
    });
  }
})();
