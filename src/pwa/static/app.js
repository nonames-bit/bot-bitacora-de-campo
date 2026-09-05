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
      "' loading='lazy' onerror='this.style.display=\"none\"'></div>";
  }
  function fechaCorta(v) { return v ? String(v).slice(0, 10) : ""; }

  // SVG Icon helper (estilo Lucide: trazo 2, sin relleno)
  // Cabeza de vaca real (Lucide Lab 'cow-head', ISC) — frontal, con orejas y morro.
  var COW_HEAD = '<path d="M17.8 15.1a10 10 0 0 0 .9-7.1h.3c1.7 0 3-1.3 3-3V3h-3c-1.3 0-2.4.8-2.8 1.9a10 10 0 0 0-8.4 0C7.4 3.8 6.3 3 5 3H2v2c0 1.7 1.3 3 3 3h.3a10 10 0 0 0 .9 7.1M9 9.5v.5m6-.5v.5"/><path d="M15 22a4 4 0 1 0-3-6.6A4 4 0 1 0 9 22Zm-6-4h.01M15 18h.01"/>';
  function icon(name, size) {
    var paths = {
      cow: COW_HEAD,
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
      users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
      // Lucide oficiales (ISC/MIT): gestación y diagnóstico
      egg: '<path d="M12 2C8 2 4 8 4 14a8 8 0 0 0 16 0c0-6-4-12-8-12"/>',
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
      // Tubo de ensayo (pajuelas de semen en el termo) — Lucide ISC
      testTube: '<path d="M14.5 2v17.5c0 1.4-1.1 2.5-2.5 2.5c-1.4 0-2.5-1.1-2.5-2.5V2"/><path d="M8.5 2h7"/><path d="M14.5 16h-5"/>',
      // Cápsula/pastilla (tratamientos) — Lucide ISC
      pill: '<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/>',
      cross: '<path d="M4 9a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h4a1 1 0 0 1 1 1v4a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-4a1 1 0 0 1 1-1h4a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2h-4a1 1 0 0 1-1-1V4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4a1 1 0 0 1-1 1z"/>'
    };
    var s = size || 18;
    return '<svg class="svg-icon" viewBox="0 0 24 24" width="' + s + '" height="' + s + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" style="display:inline-block; vertical-align:middle; margin-right:6px; position:relative; top:-1px;">' + (paths[name] || '') + '</svg>';
  }

  /* ---------- Vistas principales ---------- */
  function renderTablero(d) {
    var pot = d.potrero_filtro ? " — potrero: <b>" + esc(d.potrero_filtro) + "</b>" : "";
    var pdfBtn = "<a href='/api/reporte.pdf' class='tema-btn' download style='float:right; font-size:12px; text-decoration:none; padding:5px 12px; margin-top:-4px;'>📄 Reporte PDF</a>";
    var h = "<h3>" + icon("grid") + "Tablero finca" + pot + pdfBtn + "</h3>";
    h += "<div class='kpis'>"
      + kpi(d.activos, "Activos ♀♂") + kpi(d.hembras, "Hembras") + kpi(d.machos, "Machos")
      + kpi(d.partos_7d, "Partos 7d", d.partos_7d > 0 ? "alerta" : "")
      + kpi(d.celos_7d, "Celos 7d") + kpi(d.servicios_7d, "Serv. 7d")
      + kpi(d.retiros_activos, "Retiros", d.retiros_activos > 0 ? "alerta" : "") + "</div>";
    h += erroresHtml(d);
    h += grafico("evolucion", "Evolución del rebaño") + grafico("categorias", "Categorías del hato");
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
    h += "<h4>" + icon("calendar") + "Celos recientes</h4>"
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
    var h = "<h3>" + icon("milk") + "Leche (tanque)</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.controles.length, "Controles") + kpi(total.toFixed(0), "L últimos 30 días");
    var mejor = (d.ranking_vacas && d.ranking_vacas.length) ? d.ranking_vacas[0] : null;
    if (mejor) {
      h += kpi(esc(mejor.tag), "Mejor vaca", "ok");
    }
    h += "</div>";
    h += grafico("leche_total", "Producción total de leche") + grafico("eficiencia_lechera", "Eficiencia lechera");
    h += grafico("ranking_vacas_leche", "Ranking de producción por vaca");
    h += "<h4>" + icon("chartBar") + "Ranking de vacas por litros (acumulado)</h4>"
      + tabla(d.ranking_vacas, [
        ["tag", "Vaca"], ["total_litros", "Total L", "num"], ["controles", "Controles", "num"],
        ["ultima_fecha", "Último control", "text", function (v) { return v ? esc(fechaCorta(v)) : "—"; }]
      ], "Sin producción por vaca registrada.");
    h += "<h4>" + icon("chartLine") + "Producción por día</h4>"
      + tabla(d.serie_tanque, [["fecha", "Fecha"], ["litros", "Litros", "num"]], "Sin registros de tanque.");
    h += "<h4>" + icon("calendar") + "Controles individuales</h4>"
      + tabla(d.controles, [["tag", "Vaca"], ["fecha", "Fecha"], ["litros", "L", "num"]], "Sin controles individuales.");
    return h;
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
    var expBtn = "<button type='button' class='tema-btn' onclick='window.__exportarInventario()' style='float:right; font-size:12px; padding:4px 10px; margin-top:-4px;'>📥 Exportar CSV</button>";
    var h = "<h3>" + icon("cow") + "Inventario y Población" + expBtn + "</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.total_activos, "Activos totales")
      + kpi(d.total_hembras, "Hembras") + kpi(d.total_machos, "Machos")
      + kpi(d.edad_promedio != null ? d.edad_promedio + "a" : "—", "Edad promedio")
      + kpi(d.total_sin_sexo, "Sin clasificar", d.total_sin_sexo > 0 ? "alerta" : "")
      + kpi(d.terneros_menor_12m, "Crías <12m") + "</div>";
    h += grafico("waterfall_inventario", "Movimientos del hato (entradas/salidas)");
    h += "<h4>" + icon("chartLine") + "Brackets de edad (Software Ganadero)</h4>";
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
    h += "<h4>" + icon("testTube") + "Inventario de Pajuelas (Semen para I.A.)</h4>"
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
    var pdfBtn = "<a href='/api/reporte.pdf' class='tema-btn' download style='float:right; font-size:12px; text-decoration:none; padding:4px 10px; margin-top:-4px;'>📄 Reporte PDF</a>";
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
      var expRetBtn = "<button type='button' class='tema-btn' onclick='window.__exportarRetiros()' style='float:right; font-size:12px; padding:4px 10px; margin-top:-4px;'>📥 Exportar Retiros CSV</button>";
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
    var h = "<h3>" + icon("scale") + "Manga de Corral — Pesajes y Lotes</h3>";
    h += "<div class='manga-tabs'>"
      + "<button type='button' class='manga-tab-btn act' data-mtab='pesaje'>⚖️ Pesaje Rápido & GMD</button>"
      + "<button type='button' class='manga-tab-btn' data-mtab='lote'>💉 Tratamiento en Lote</button>"
      + "<button type='button' class='manga-tab-btn' data-mtab='ble'>📶 Báscula / RFID BLE</button>"
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
      + "<button type='button' id='btn-manga-guardar-peso' class='btn-guardar-manga'>💾 Guardar Pesaje (Enter)</button>"
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
      + "<button type='button' id='btn-manga-guardar-lote' class='btn-guardar-manga' style='margin-top:10px; background:#1F6C9F;'>💉 Aplicar Tratamiento en Lote</button>"
      + "</div>"
      + "</div>";
    h += "</div>";

    // Panel 3: BLE
    h += "<div id='manga-panel-ble' style='display:none;'>";
    h += "<div class='gps-box'>"
      + "<h4>" + icon("alert") + "Conexión Web Bluetooth a Báscula / RFID</h4>"
      + "<p class='aviso'>Permite recibir el peso o arete leído automáticamente desde básculas electrónicas (Tru-Test, Gallagher) o bastones RFID (Allflex) por Bluetooth BLE sin teclear.</p>"
      + "<button type='button' id='btn-manga-ble-conectar' class='btn-guardar-manga' style='max-width:320px; margin:14px auto;'>📶 Conectar Dispositivo BLE</button>"
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
      { id: "parto", nom: "🐣 Parto" },
      { id: "pesaje", nom: "⚖️ Pesaje" },
      { id: "tratamiento", nom: "💊 Tratamiento" },
      { id: "traslado", nom: "🚚 Traslado" },
      { id: "celo", nom: "🎯 Celo" },
      { id: "servicio", nom: "🧬 Servicio / IA" },
      { id: "leche", nom: "🥛 Leche" },
      { id: "muerte", nom: "⚠️ Muerte / Descarte" }
    ];

    var h = "<h3>" + icon("alert") + "Captura Rápida de Campo (Online / Offline)</h3>";
    h += "<p class='aviso'>Registra eventos directamente en el potrero. Si estás sin señal, se guardarán en la cola local de tu celular y se sincronizarán al volver a la casa.</p>";

    h += "<div style='display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px;'>";
    tipos.forEach(function (t) {
      var act = t.id === _tipoCapturaActual ? "act" : "";
      h += "<button type='button' class='btn-punto " + act + "' data-cap-tipo='" + t.id + "' style='font-size:13px;'>" + t.nom + "</button>";
    });
    h += "</div>";

    h += "<div class='card' style='padding:16px;'>"
      + "<form id='form-captura' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<div id='captura-campos'></div>"
      + "<button type='submit' id='btn-guardar-captura' class='btn-guardar-manga' style='margin-top:12px;'>💾 Guardar Registro</button>"
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
      h += "<label>Litros Totales Ordeño: <input type='number' step='0.5' id='cap-litros' placeholder='ej. 185' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Observaciones: <input id='cap-notas' placeholder='Tanque de enfriamiento, retiro aplicado, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "muerte") {
      h += "<label>Arete / Tag: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Causa Presunta: <input id='cap-causa' placeholder='ej. Mordedura de serpiente, timpanismo, descarte vejez' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Observaciones: <input id='cap-notas' placeholder='Detalles o destino' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    }

    return h;
  }

  function bindCaptura() {
    var cCampos = document.getElementById("captura-campos");
    if (cCampos) cCampos.innerHTML = camposHtmlCaptura(_tipoCapturaActual);

    qa("button[data-cap-tipo]").forEach(function (b) {
      b.addEventListener("click", function () {
        qa("button[data-cap-tipo]").forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        _tipoCapturaActual = b.getAttribute("data-cap-tipo");
        if (cCampos) cCampos.innerHTML = camposHtmlCaptura(_tipoCapturaActual);
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
        }

        var feed = document.getElementById("captura-feedback");

        function mostrarExito(online) {
          if (feed) {
            feed.innerHTML = "<div class='chip " + (online ? "verde" : "ambar") + "' style='font-size:14px; padding:8px 12px;'>"
              + (online ? "✅ Evento registrado en el servidor." : "💾 Evento guardado en cola local offline (se enviará al volver la señal).") + "</div>";
          }
          form.reset();
          if (cCampos) cCampos.innerHTML = camposHtmlCaptura(_tipoCapturaActual);
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

  /* ---------- GPS Potrero & Rondas de Campo ---------- */
  var _gpsUltimaPos = null;
  var _gpsUltimoPotrero = null;
  var _puntoRondaSeleccionado = "saladero";

  function renderGps(d) {
    var h = "<h3>" + icon("search") + "GPS Potrero & Auditoría de Rondas</h3>"
      + "<p class='aviso'>Verifica mediante el GPS del celular en qué potrero te encuentras y audita las visitas a saladeros, bebederos y cercas con hora exacta.</p>";

    h += "<div class='gps-box'>"
      + "<button type='button' id='btn-gps-detectar' class='btn-guardar-manga' style='max-width:320px; margin:0 auto 12px; font-size:16px;'>📍 Obtener Mi Ubicación GPS</button>"
      + "<div id='gps-estado' style='font-size:13px; color:var(--texto-suave);'>Toque el botón para geolocalizar este teléfono.</div>"
      + "<div id='gps-resultado-box' style='margin-top:14px; display:none;'></div>"
      + "</div>";

    h += "<div class='card' style='margin-top:14px; padding:16px;'>"
      + "<h4>" + icon("alert") + "Registrar Punto de Ronda de Campo</h4>"
      + "<p class='aviso' style='margin:4px 0;'>Selecciona el punto de control que estás revisando en este momento:</p>"
      + "<div class='puntos-control-grid'>"
      + "<button type='button' class='btn-punto act' data-punto='saladero'>🧂 Saladero</button>"
      + "<button type='button' class='btn-punto' data-punto='bebedero'>💧 Bebedero</button>"
      + "<button type='button' class='btn-punto' data-punto='cercas'>🪵 Cercas</button>"
      + "<button type='button' class='btn-punto' data-punto='conteo'>🐄 Conteo</button>"
      + "<button type='button' class='btn-punto' data-punto='recorrido'>🚶 Recorrido</button>"
      + "</div>"
      + "<input id='gps-ronda-notas' placeholder='Novedad (ej. falta sal mineralizada, alambre caído, todo OK)' style='width:100%; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); margin-bottom:12px;'>"
      + "<button type='button' id='btn-gps-guardar-ronda' class='btn-guardar-manga'>📋 Registrar Parada en Ronda</button>"
      + "<div id='gps-ronda-feedback' style='margin-top:10px;'></div>"
      + "</div>";

    var rondas = (d && d.rondas) || [];
    h += "<div style='display:flex; justify-content:space-between; align-items:center; margin-top:20px;'>"
      + "<h4>" + icon("calendar") + "Rondas Realizadas Hoy (" + rondas.length + ")</h4>"
      + "<button type='button' id='btn-exportar-rondas-csv' class='tema-btn' style='font-size:12px; padding:4px 10px;'>📥 Exportar CSV</button>"
      + "</div>";

    if (!rondas.length) {
      h += vacio("No hay rondas registradas en el día.");
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

    return h;
  }

  function bindGps(d) {
    var btnDetectar = document.getElementById("btn-gps-detectar");
    var est = document.getElementById("gps-estado");
    var resBox = document.getElementById("gps-resultado-box");

    if (btnDetectar) {
      btnDetectar.addEventListener("click", function () {
        if (!navigator.geolocation) {
          if (est) est.textContent = "❌ Geolocalización no disponible en este dispositivo.";
          return;
        }
        if (est) est.innerHTML = "⏳ Conectando con satélites GPS... (espere unos segundos)";
        navigator.geolocation.getCurrentPosition(function (pos) {
          _gpsUltimaPos = pos;
          var lat = pos.coords.latitude;
          var lon = pos.coords.longitude;
          var acc = Math.round(pos.coords.accuracy || 0);
          if (est) est.innerHTML = "📡 Coordenadas: <b>" + lat.toFixed(6) + ", " + lon.toFixed(6) + "</b> (Precisión: ±" + acc + " m)";

          fetch("/api/gps/potrero", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lat: lat, lon: lon })
          }).then(function (r) { return r.json(); })
            .then(function (data) {
              if (resBox) resBox.style.display = "block";
              if (data.detectado && data.potrero) {
                _gpsUltimoPotrero = data.potrero;
                var anims = data.animales || [];
                var h = "<div class='gps-potrero-tit'>🌾 " + esc(data.potrero.nombre || data.potrero.codigo) + "</div>"
                  + "<p style='margin:4px 0; font-size:13px;'>Detectado por " + esc(data.potrero.metodo || "polígono") + " · Ocupación actual: <b>" + data.total_animales + " animales</b></p>";
                if (anims.length) {
                  h += "<div style='font-size:12px; color:var(--texto-suave); margin-top:6px;'>Animales en potrero: "
                    + anims.slice(0, 15).map(function (a) { return "<b>" + esc(a.tag) + "</b>"; }).join(", ")
                    + (anims.length > 15 ? " y " + (anims.length - 15) + " más..." : "") + "</div>";
                }
                if (resBox) resBox.innerHTML = h;
              } else {
                _gpsUltimoPotrero = null;
                if (resBox) resBox.innerHTML = "<p class='aviso'>⚠️ " + esc(data.mensaje || "Ubicación fuera de los polígonos de la finca.") + "</p>";
              }
            }).catch(function (err) {
              if (resBox) {
                resBox.style.display = "block";
                resBox.innerHTML = "<p class='aviso'>⚠️ Sin conexión para consultar el polígono del potrero. Coordenadas guardadas localmente.</p>";
              }
            });
        }, function (err) {
          if (est) est.innerHTML = "❌ Error GPS: " + esc(err.message) + ". Verifique que el GPS esté encendido y que el navegador tenga permiso de ubicación.";
        }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
      });
    }

    qa(".puntos-control-grid button").forEach(function (b) {
      b.addEventListener("click", function () {
        qa(".puntos-control-grid button").forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        _puntoRondaSeleccionado = b.getAttribute("data-punto") || "recorrido";
      });
    });

    var btnRonda = document.getElementById("btn-gps-guardar-ronda");
    if (btnRonda) {
      btnRonda.addEventListener("click", function () {
        var notas = (q("#gps-ronda-notas") && q("#gps-ronda-notas").value || "").trim();
        var lat = _gpsUltimaPos ? _gpsUltimaPos.coords.latitude : null;
        var lon = _gpsUltimaPos ? _gpsUltimaPos.coords.longitude : null;
        var potId = _gpsUltimoPotrero ? _gpsUltimoPotrero.id : null;
        var potNom = _gpsUltimoPotrero ? (_gpsUltimoPotrero.nombre || _gpsUltimoPotrero.codigo) : null;
        var feed = document.getElementById("gps-ronda-feedback");

        var payload = {
          lat: lat,
          lon: lon,
          potrero_id: potId,
          potrero_nombre: potNom,
          punto_control: _puntoRondaSeleccionado,
          notas: notas,
          hora: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })
        };

        if (navigator.onLine === false) {
          encolarOffline("ronda", payload).then(function () {
            if (feed) feed.innerHTML = "<div class='chip ambar'>💾 Parada de ronda guardada offline. Se sincronizará al volver la señal.</div>";
            if (q("#gps-ronda-notas")) q("#gps-ronda-notas").value = "";
          });
          return;
        }

        fetch("/api/gps/ronda", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              if (feed) feed.innerHTML = "<div class='chip verde'>✅ Parada de ronda registrada con éxito.</div>";
              if (q("#gps-ronda-notas")) q("#gps-ronda-notas").value = "";
              setTimeout(function () { cargar(false); }, 1000);
            } else {
              encolarOffline("ronda", payload).then(function () {
                if (feed) feed.innerHTML = "<div class='chip ambar'>💾 Guardado offline (" + esc(res.error || "error") + ")</div>";
              });
            }
          }).catch(function () {
            encolarOffline("ronda", payload).then(function () {
              if (feed) feed.innerHTML = "<div class='chip ambar'>💾 Guardado offline en cola local.</div>";
            });
          });
      });
    }

    var btnCsv = document.getElementById("btn-exportar-rondas-csv");
    if (btnCsv) {
      btnCsv.addEventListener("click", function () {
        exportarTablaCSV("rondas_campo", "#tabla-rondas");
      });
    }
  }

  /* ---------- Sistema & Servidor VPS (Solo OWNER) ---------- */
  function renderSistema(d) {
    var vps = d.vps || {};
    var db = d.db || {};

    var h = "<h3>⚙️ Servidor VPS & Sistema Ganadería JA</h3>"
      + "<p class='aviso'>Panel de control ejecutivo y métricas de infraestructura en vivo. Acceso restringido al Propietario (OWNER).</p>";

    h += "<div class='kpis'>"
      + kpi((vps.ram_pct != null ? vps.ram_pct + "%" : "—"), "RAM VPS (" + (vps.ram_used_mb || 0) + "/" + (vps.ram_total_mb || 0) + " MB)")
      + kpi((vps.disk_pct != null ? vps.disk_pct + "%" : "—"), "Disco (" + (vps.disk_used_gb || 0) + "/" + (vps.disk_total_gb || 0) + " GB)")
      + kpi((db.tam_mb != null ? db.tam_mb + " MB" : "—"), "Base de Datos SQLite")
      + kpi((db.activos != null ? String(db.activos) : "—"), "Hato Activo SG", "ok")
      + "</div>";

    h += "<h4>" + icon("grid") + "Diagnóstico General</h4>"
      + "<pre style='background:var(--superficie); color:var(--texto); border:1px solid var(--borde-fuerte); padding:12px; border-radius:8px; font-size:12px; white-space:pre-wrap; overflow-x:auto; line-height:1.4;'>"
      + esc(d.texto || "Sin diagnóstico disponible.") + "</pre>";

    h += "<div style='display:flex; justify-content:space-between; align-items:center; margin-top:20px;'>"
      + "<h4>📜 Visor de Logs del Servidor (Últimas 80 líneas)</h4>"
      + "<button type='button' id='btn-refrescar-logs' class='tema-btn' style='font-size:12px; padding:4px 10px;'>🔄 Refrescar Logs</button>"
      + "</div>"
      + "<pre id='visor-logs' style='background:#121212; color:#39FF14; padding:14px; border-radius:8px; font-family:var(--font-mono); font-size:11.5px; max-height:360px; overflow-y:auto; line-height:1.4;'>Cargando logs del servidor...</pre>";

    return h;
  }

  function bindSistema() {
    function cargarLogs() {
      var visor = document.getElementById("visor-logs");
      if (!visor) return;
      visor.textContent = "Cargando logs...";
      fetch("/api/logs").then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.logs) {
            visor.textContent = d.logs.join("\n");
            visor.scrollTop = visor.scrollHeight;
          } else {
            visor.textContent = "Sin logs disponibles.";
          }
        }).catch(function (err) {
          visor.textContent = "Error al obtener logs: " + err.message;
        });
    }

    cargarLogs();
    var btnRef = document.getElementById("btn-refrescar-logs");
    if (btnRef) btnRef.addEventListener("click", cargarLogs);
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
            var formateada = esc(resp).replace(/\n/g, "<br>");
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
      if (btnAccion) { btnAccion.textContent = "⏹️ Detener y Enviar"; btnAccion.style.display = ""; }
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
          if (estado) estado.textContent = "⏳ Transcribiendo con Whisper y procesando en el bot...";
          if (onda) onda.style.display = "none";

          var blob = new Blob(_audioChunks, { type: _mediaRecorder.mimeType || "audio/webm" });
          var fd = new FormData();
          fd.append("audio", blob, "nota_campo.webm");

          fetch("/api/voz", { method: "POST", body: fd })
            .then(function (r) { return r.json(); })
            .then(function (data) {
              if (resBox) resBox.style.display = "block";
              if (data.ok) {
                if (estado) estado.textContent = "✅ Nota procesada con éxito.";
                resBox.innerHTML = "<b>Transcripción:</b> <i>\"" + esc(data.transcripcion) + "\"</i><br><br>"
                  + "<b>Respuesta del Bot:</b><br>" + esc(data.respuesta || "Registrado.");
                if (btnAccion) btnAccion.textContent = "🎤 Grabar Otra Nota";
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
    fetch("/api/usuario").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (u) {
      usuarioActual = u || {};
      window.__usuarioActual = usuarioActual;
      aplicarRBAC(usuarioActual);
    }).catch(function () { /* modo seguro */ });
  }

  function aplicarRBAC(u) {
    var badge = document.getElementById("user-badge");
    if (badge && u.nombre) {
      var rol = (u.rol || "INVITADO").toUpperCase();
      badge.textContent = u.nombre + " · " + rol;
      badge.style.display = "inline-block";
    }

    var rol = (u.rol || "").toUpperCase();
    var btnSistema = document.getElementById("btn-nav-sistema");

    if (rol === "OWNER") {
      if (btnSistema) btnSistema.style.display = "";
      qa("nav > button").forEach(function (b) { b.style.display = ""; });
    } else if (rol === "ADMIN" || rol === "ADMINISTRADOR") {
      if (btnSistema) btnSistema.style.display = "none";
      qa("nav > button").forEach(function (b) {
        if (b.getAttribute("data-v") === "sistema") b.style.display = "none";
        else b.style.display = "";
      });
    } else if (rol === "TRABAJADOR") {
      if (btnSistema) btnSistema.style.display = "none";
      var permitidas = ["captura", "manga", "gps", "ficha"];
      qa("nav > button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        if (permitidas.indexOf(v) !== -1) {
          b.style.display = "";
        } else {
          b.style.display = "none";
        }
      });
      if (permitidas.indexOf(actual) === -1) {
        irAVista("captura");
        cargar();
      }
    }
  }

  /* ---------- Ficha con pestañas ---------- */
  var TABS = [
    { id: "general", label: icon("cow") + "General" },
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
    var head = "<div class='ficha-head'>";
    if (f.fotos && f.fotos.length && f.fotos[0].url) {
      head += "<img class='avatar' src='" + esc(f.fotos[0].url) + "' alt='foto' onerror='this.style.display=\"none\"'>";
    }
    head += "<div class='datos'><b>" + icon("cow") + esc(f.tag) + " " + esc(f.nombre || "") + "</b><br>"
      + "<span class='meta'>" + esc(f.sexo || "") + " · " + esc(f.raza || "S/D") + " · " + esc(f.estado || "") + "</span><br>"
      + "<span class='meta'>Nac: " + esc(fechaCorta(f.fecha_nacimiento) || "S/D") + "</span></div></div>";
    var html = (showIdent ? identPanelHtml() : "") + head + erroresHtml(f);
    html += "<div id='ficha-tabs'><nav class='mini'>"
      + TABS.map(function (t) { return "<button data-tab='" + t.id + "' class='act'>" + t.label + "</button>"; }).join("")
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
        + "/grafico/lactancia' alt='Curva de lactancia' loading='lazy' onerror='this.style.display=\"none\"'></div>";
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
        + "/grafico/peso' alt='Curva de peso' loading='lazy' onerror='this.style.display=\"none\"'></div>";
      return h2;
    }
    var fotos = "";
    if (f.fotos && f.fotos.length) {
      fotos = "<div class='fotos-wrap'>" + f.fotos.filter(function (x) { return x.url; })
        .map(function (x) { return "<img src='" + esc(x.url) + "' alt='foto' loading='lazy' onerror='this.style.display=\"none\"'>"; }).join("") + "</div>";
    } else { fotos = vacio("Sin fotos para este animal."); }
    var qr = f.qr_payload ? "<p class='aviso'>QR <code>" + esc(f.qr_payload) + "</code> · <a href='" + esc(f.qr_url || "") + "'>abrir ficha</a></p>" : "";
    var pdf = (f.qr_url)
      ? "<p><a class='qr-pdf' href='/api/ficha/" + encodeURIComponent(f.tag) + "/qr.pdf' download>Descargar tarjeta QR (PDF)</a></p>"
      : "";
    return "<h4>General</h4>" + fotos + qr + pdf;
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
    ficha:     { kpis: 0, graf: 1, tabla: 7 },
    manga:     { kpis: 0, graf: 0, tabla: 4 },
    captura:   { kpis: 0, graf: 0, tabla: 0 },
    gps:       { kpis: 0, graf: 0, tabla: 4 },
    sistema:   { kpis: 4, graf: 0, tabla: 0 }
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
    var destino = qa("nav > button").filter(function (b) { return b.getAttribute("data-v") === "ficha"; })[0];
    if (!destino) return; // vista dedicada /ficha/<tag> (QR): sin nav
    var inp = q("#f-tag");
    if (inp) inp.value = tag;
    destino.click();
  }
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
        if (target) target.innerHTML = "❌ No se pudo cargar (" + esc(e && e.message || e) + "). <button onclick='location.reload()'>Reintentar</button>";
      });
  }
  function abrirFicha(tag, target, showIdent, animar) {
    if (animar === undefined) animar = true;
    skeleton(target, "ficha");
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
      if (vista) {
        montarVista(vista, renderManga(), animar);
        bindManga();
      }
      return;
    }

    if (actual === "captura") {
      if (vista) {
        montarVista(vista, renderCaptura(), animar);
        bindCaptura();
      }
      return;
    }

    if (actual === "gps") {
      skeleton(vista, "gps");
      fetchJSON("/api/gps/rondas", function (d) {
        if (!vista) return;
        montarVista(vista, renderGps(d), animar);
        bindGps(d);
      }, vista);
      return;
    }

    if (actual === "sistema") {
      skeleton(vista, "sistema");
      fetchJSON("/api/sistema", function (d) {
        if (!vista) return;
        montarVista(vista, renderSistema(d), animar);
        bindSistema();
      }, vista);
      return;
    }

    var pot = (q("#f-potrero") && q("#f-potrero").value || "").trim();
    var url = "/api/" + actual + (pot && actual === "tablero" ? "?potrero=" + encodeURIComponent(pot) : "");
    skeleton(vista, actual);
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
      montarVista(vista, html, animar);
    }, vista);
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
    if (document.hidden || navigator.onLine === false || actual === "ficha") { if (!document.hidden) actualizarBadges(); return; }
    cargar(false); // polling en silencio: sin animación ni count-up
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
  if (fb) {
    var tag = document.body.getAttribute("data-tag") || "";
    abrirFicha(tag, fb, false, false); // QR ya identifica el animal: sin panel de foto
  } else {
    cargarUsuario();
    setupSyncOffline();
    setupChatModal();
    setupVozModal();
    crearBadgesNav();
    setupCampana();
    actualizarBadges();
    actualizarContadorSync();
    // Primer refresco de badges y cola offline al reconectar tras estar sin señal.
    window.addEventListener("online", function () {
      actualizarBadges();
      sincronizarColaOffline(false);
    });
    arrancarDesdeUrl();
  }
})();
