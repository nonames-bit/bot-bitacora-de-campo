/* Dashboard PWA Bitácora JA — JS vainilla (sin framework).
   WS-3: KPIs, chips semáforo, skeleton, banner offline, polling 60s,
   modo oscuro, errores visibles por sección y ficha con pestañas. */
(function () {
  "use strict";
  var vista = document.getElementById("vista");
  var actual = "tablero";
  function q(s) { return document.querySelector(s); }
  function qa(s, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(s)); }
  // Alias a ja-core.js (cargar antes que app.js) — los helpers puros se
  // definen en /static/ja-core.js (BLOQUE 3 fase 1; 100% autocontenidos:
  // no usan vista/actual/q/qa/fetchJSON); aquí solo se aliasan para no
  // tocar ninguna llamada. Las constantes CALF_HEAD/COW_BODY_FILL/
  // PARTO_HEADS/DESTETE_ICON solo se usan vía icon(), por eso quedan
  // encapsuladas en JA sin alias local.
  var esc = window.JA.esc;
  var mostrarToast = window.JA.mostrarToast;
  var vibrarConfirmacion = window.JA.vibrarConfirmacion;
  var chipEstado = window.JA.chipEstado;
  var vacio = window.JA.vacio;
  var tabla = window.JA.tabla;
  var kpi = window.JA.kpi;
  var erroresHtml = window.JA.erroresHtml;
  var grafico = window.JA.grafico;
  var fechaCorta = window.JA.fechaCorta;
  var fmtMoneda = window.JA.fmtMoneda;

  var icon = window.JA.icon;

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
    h += grafico("evolucion", "Evolución del rebaño");

    h += "<h4>" + icon("grass") + "Distribución por potrero (toca para filtrar)</h4>";
    h += barraDistribucionPotreros(d.por_potrero);

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
      h += "<div class='tabla-scroll tabla-eventos'><table class='tabla-eventos'>"
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
        } else if (tipo === "GEMELAR") {
          chipHtml = "<span class='chip verde' style='font-weight:700;'>" + icon("cowCalf", 13) + " Gemelar</span>";
        } else if (tipo === "ABORTO") {
          chipHtml = "<span class='chip rojo' style='font-weight:700;'>" + icon("alert", 13) + " Aborto</span>";
        } else if (tipo === "REABSORCION" || tipo === "MOMIFICACION" || tipo === "MACERACION" || tipo === "MUERTE_FETAL") {
          chipHtml = "<span class='chip rojo' style='font-weight:700;'>" + icon("alert", 13) + " " + esc(tipo.replace("_", " ")) + "</span>";
        } else if (tipo === "MUERTE") {
          chipHtml = "<span class='chip rojo' style='font-weight:700;'>" + icon("skull", 13) + " Muerte</span>";
        } else if (tipo === "VENTA" || tipo === "DESCARTE" || tipo === "COMPRA") {
          chipHtml = "<span class='chip ambar' style='font-weight:700;'>" + icon("truck", 13) + " " + esc(tipo) + "</span>";
        } else if (tipo === "TRASLADO") {
          chipHtml = "<span class='chip azul' style='font-weight:700;'>" + icon("grass", 13) + " Traslado</span>";
        } else if (tipo === "DESTETE") {
          chipHtml = "<span class='chip verde' style='font-weight:700;'>" + icon("destete", 13) + " Destete</span>";
        } else if (tipo === "SECADO") {
          chipHtml = "<span class='chip azul' style='font-weight:700;'>" + icon("milk", 13) + " Secado</span>";
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
          + "<td data-label='Tipo Evento'>" + chipHtml + "</td>"
          + "<td data-label='Fecha'><b style='font-family:var(--font-mono); font-size:12px;'>" + esc(fechaCorta(ev.fecha)) + "</b></td>"
          + "<td data-label='Animal / Arete'>" + linkAnimal + detalleExtra + "</td>"
          + "<td data-label='Detalle de la Actividad'>" + descHtml + "</td>"
          + "</tr>";
      });

      h += "</table></div>";
    }
    h += "</div>";
    return h;
  }
  function renderRepro(d) {
    var h = "<h3>" + icon("sperm") + "Reproducción</h3>" + erroresHtml(d) + grafico("reproductivo_hato", "Estado reproductivo del hato");
    var k = d.kpis || {};
    h += "<h4>" + icon("chartBar") + "Indicadores del hato</h4>";
    h += "<div class='kpis'>"
      + kpi(k.iep_promedio_dias != null ? k.iep_promedio_dias + "d" : "—", "IEP promedio")
      + kpi(k.dias_abiertos_promedio != null ? k.dias_abiertos_promedio + "d" : "—", "Días abiertos (" + (k.dias_abiertos_n || 0) + " vaca(s))", k.dias_abiertos_promedio > 150 ? "alerta" : "")
      + kpi(k.servicios_por_concepcion != null ? k.servicios_por_concepcion : "—", "Servicios/Concepción")
      + kpi(k.tasa_concepcion != null ? k.tasa_concepcion + "%" : "—", "Tasa de concepción", k.tasa_concepcion != null && k.tasa_concepcion < 50 ? "alerta" : "ok")
      + kpi(k.edad_primer_parto_meses != null ? k.edad_primer_parto_meses + "m" : "—", "Edad 1er parto")
      + "</div>";
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
  // Modo Simple (default) vs Técnico para SPI y Monitoreo Satelital en Pasturas:
  // los números crudos (NDVI, RVI, SPI, kg/ha) son ilegibles para un ganadero
  // que no es agrónomo -- Simple muestra solo el semáforo/palabra clave,
  // Técnico muestra todo el detalle igual que antes. Se recuerda por navegador.
  function modoPasturasEsSimple() {
    return localStorage.getItem("modoPasturasSimple") !== "tecnico";
  }
  function renderPasturas(d) {
    var simple = modoPasturasEsSimple();
    var btnModo = "<button type='button' id='btn-toggle-modo-pasturas' class='tema-btn' style='float:right; font-size:12px; padding:5px 12px; margin-top:-4px;'>"
      + (simple ? "🔬 Ver técnico" : "😊 Ver simple") + "</button>";
    var h = "<h3>" + icon("grass") + "Pasturas (Voisin)" + btnModo + "</h3>" + erroresHtml(d);

    var pron = d.pronostico;
    h += "<h4>" + icon("rain") + "Pronóstico del clima (7 días)</h4>";
    if (!pron || !pron.dias || !pron.dias.length) {
      h += vacio("Sin pronóstico disponible (requiere al menos un potrero con geometría/coordenadas registradas).");
    } else {
      h += "<div style='display:flex; gap:8px; overflow-x:auto; padding-bottom:8px;'>";
      pron.dias.forEach(function (dd) {
        var prob = dd.prob_lluvia_pct;
        var lluvia = Number(dd.lluvia_mm) || 0;
        var alerta = (lluvia >= 10 || (prob != null && prob >= 70)) ? "rojo"
          : (lluvia >= 2 || (prob != null && prob >= 40)) ? "ambar" : "verde";
        h += "<div class='card' style='min-width:110px; flex-shrink:0; padding:10px; text-align:center;'>"
          + "<div style='font-size:11px; font-weight:700; color:var(--texto-suave); text-transform:uppercase;'>" + esc(fechaCorta(dd.fecha)) + "</div>"
          + "<div style='font-size:13px; font-weight:700; margin:4px 0;'>" + esc(Math.round(dd.temp_max_c)) + "° / " + esc(Math.round(dd.temp_min_c)) + "°</div>"
          + "<span class='chip " + alerta + "' style='font-size:11px;'>" + icon("droplet", 11) + esc(lluvia.toFixed(1)) + " mm</span>"
          + (prob != null ? "<div style='font-size:10.5px; color:var(--texto-suave); margin-top:4px;'>" + esc(Math.round(prob)) + "% prob.</div>" : "")
          + "</div>";
      });
      h += "</div>";
      if (pron.recomendaciones && pron.recomendaciones.length) {
        h += "<div class='card' style='padding:10px 14px;'>"
          + pron.recomendaciones.map(function (r) { return "<div style='font-size:13px; margin:3px 0;'>• " + esc(r) + "</div>"; }).join("")
          + "</div>";
      }
      if (pron.desactualizado_horas != null) {
        h += "<p class='aviso'>⚠️ Datos del pronóstico de hace " + Math.round(pron.desactualizado_horas) + " h (sin conexión a Open-Meteo en la última actualización).</p>";
      }
    }

    h += "<h4>" + icon("alert") + (simple ? "¿Cómo viene la lluvia?" : "Alerta Temprana de Sequía (SPI)") + "</h4>";
    if (!d.spi_sequia || !d.spi_sequia.length) {
      h += vacio("Sin cálculo de SPI todavía (se genera en la corrida semanal del job de lluvia satelital).");
    } else {
      var ETIQUETAS_VENTANA_SPI = { 30: "Último mes", 60: "Últimos 2 meses", 90: "Últimos 3 meses" };
      h += "<div style='display:flex; gap:10px; flex-wrap:wrap;'>";
      d.spi_sequia.forEach(function (s) {
        var spi = s.spi_valor;
        var color = spi == null ? "gris" : spi <= -1.5 ? "rojo" : spi <= -1.0 ? "ambar" : spi >= 1.0 ? "verde" : "gris";
        if (simple) {
          h += "<div class='card' style='flex:1; min-width:130px; padding:14px; text-align:center;'>"
            + "<div style='font-size:11px; font-weight:700; color:var(--texto-suave); text-transform:uppercase;'>" + esc(ETIQUETAS_VENTANA_SPI[s.dias_ventana] || (s.dias_ventana + " días")) + "</div>"
            + "<span class='chip " + color + "' style='font-size:14px; font-weight:700; padding:6px 14px; margin:8px 0; display:inline-block;'>" + esc(s.clasificacion || "Sin datos") + "</span>"
            + "<div style='font-size:11px; color:var(--texto-suave); margin-top:4px;'>" + (s.mm_actual != null ? esc(s.mm_actual) + " mm de lluvia" : "—") + "</div>"
            + "</div>";
          return;
        }
        h += "<div class='card' style='flex:1; min-width:130px; padding:12px; text-align:center;'>"
          + "<div style='font-size:11px; font-weight:700; color:var(--texto-suave); text-transform:uppercase;'>SPI " + esc(s.dias_ventana) + " días</div>"
          + "<div style='font-size:22px; font-weight:700; margin:4px 0;'>" + (spi != null ? esc(spi) : "—") + "</div>"
          + "<span class='chip " + color + "' style='font-size:11px;'>" + esc(s.clasificacion || "Sin datos") + "</span>"
          + "<div style='font-size:10.5px; color:var(--texto-suave); margin-top:4px;'>" + (s.mm_actual != null ? esc(s.mm_actual) + " mm" : "—") + " · " + esc(fechaCorta(s.fecha)) + "</div>"
          + "</div>";
      });
      h += "</div>";
      h += simple
        ? "<p class='aviso' style='margin-top:8px;'>Compara la lluvia reciente contra lo normal para esta época del año en la finca (últimos ~30 años).</p>"
        : "<p class='aviso' style='margin-top:8px;'>SPI: compara la lluvia acumulada actual contra el clima histórico de ~30 años de la zona (CHIRPS/Earth Engine). Valores por debajo de -1.0 indican sequía; por debajo de -1.5, sequía severa.</p>";
    }

    // Sección Satelital Todo Clima: Sentinel-1 SAR Radar + Sentinel-2 Óptico
    var sat = d.satelite_resumen || {};
    var tieneSat = sat.total_potreros > 0;

    var btnSyncSar = "<button type='button' class='tema-btn btn-satelite-sar' id='btn-sync-satelite-sar'>"
      + icon("sparkles", 13) + (simple ? "🔄 Actualizar (con nubes)" : "📡 Radar SAR (Todo Clima)") + "</button>";
    var btnSyncAuto = "<button type='button' class='tema-btn' id='btn-sync-satelite-auto' style='font-size:12px; padding:6px 12px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; box-shadow:0 2px 4px rgba(0,0,0,0.15);'>"
      + icon("sparkles", 13) + (simple ? "🔄 Actualizar (rápido)" : "⚡ Auto (S2 + S1)") + "</button>";

    h += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin:18px 0 10px;'>"
      + "<h4 style='margin:0;'>" + icon("chartLine") + (simple ? "Estado del Pasto (satélite)" : "Monitoreo Satelital (Radar SAR Sentinel-1 & Óptico S2)") + "</h4>"
      + "<div style='display:flex; gap:6px;'>" + btnSyncSar + btnSyncAuto + "</div>"
      + "</div>";

    h += "<div id='satelite-status-box' style='display:none; margin:10px 0; padding:12px 16px; border-radius:8px; font-size:13px; transition:all 0.3s ease;'></div>";

    if (tieneSat) {
      var ndviProm = sat.promedio_ndvi != null ? sat.promedio_ndvi : null;
      var chipNdvi = ndviProm == null ? "gris" : Number(ndviProm) >= 0.6 ? "verde" : Number(ndviProm) >= 0.4 ? "ambar" : "rojo";
      if (simple) {
        var etiquetaEstado = ndviProm == null ? "Sin datos" : Number(ndviProm) >= 0.6 ? "Excelente" : Number(ndviProm) >= 0.4 ? "Regular" : "Bajo";
        h += "<div class='kpis'>"
          + kpi("<span class='chip " + chipNdvi + "' style='font-size:16px; padding:6px 14px;'><b>" + esc(etiquetaEstado) + "</b></span>", "Estado general del pasto")
          + "</div>";
      } else {
        h += "<div class='kpis'>"
          + kpi("<span class='chip " + chipNdvi + "' style='font-size:14px;'><b>" + esc(ndviProm != null ? ndviProm : "—") + "</b></span>", "NDVI Promedio Finca")
          + kpi(esc(sat.modo_activo || "Radar SAR"), "Sensor Principal")
          + (sat.promedio_biomasa_kg_ha != null ? kpi(esc(Math.round(sat.promedio_biomasa_kg_ha).toLocaleString()) + " kg/ha", "Biomasa Promedio MS") : "")
          + (sat.promedio_aforo_kg_m2 != null ? kpi(esc(sat.promedio_aforo_kg_m2) + " kg/m²", "Aforo Promedio MV") : "")
          + kpi(esc(sat.cobertura_clima || "100% Todo Clima"), "Cobertura Climática", "ok")
          + "</div>";
      }
    }

    if (!simple) {
      h += "<div class='card' style='padding:10px 14px; margin-bottom:14px; background:rgba(30, 60, 114, 0.05); border-left:4px solid #2a5298;'>"
        + "<div style='font-size:12.5px; line-height:1.45; color:var(--texto-color);'>"
        + "<b>📡 Monitoreo Radar SAR Sentinel-1 (C-band 10m):</b> En época de lluvias, la nubosidad bloquea el sensor óptico Sentinel-2. "
        + "El radar SAR emite microondas que penetran nubes, lluvia y neblina, calculando el índice dual de vegetación (RVI) y biomasa estimada sin perder continuidad temporal."
        + "</div></div>";
    }

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
    var columnasNdvi = simple ? [
      ["potrero", "Potrero"],
      ["ndvi_promedio", "Estado", "text", function (v) {
        var n = Number(v);
        var c = n >= 0.6 ? "verde" : n >= 0.4 ? "ambar" : n > 0 ? "rojo" : "gris";
        var etq = n >= 0.6 ? "Excelente" : n >= 0.4 ? "Regular" : n > 0 ? "Bajo" : "Sin datos";
        return "<span class='chip " + c + "'><b>" + esc(etq) + "</b></span>";
      }],
      ["fecha", "Fecha"],
    ] : [
      ["potrero", "Potrero"],
      ["fuente", "Sensor / Modo", "text", function (v) {
        var s = String(v || "");
        if (s.indexOf("Sentinel-1") >= 0 || s.indexOf("SAR") >= 0 || s.indexOf("Radar") >= 0) {
          return "<span class='chip azul' style='font-size:11px; font-weight:700;' title='" + esc(s) + "'>📡 Radar SAR (S1)</span>";
        }
        return "<span class='chip verde' style='font-size:11px;' title='" + esc(s) + "'>🛰️ Óptico (S2)</span>";
      }],
      ["fecha", "Fecha"],
      ["ndvi_promedio", "NDVI / Proxy", "text", function (v) {
        var n = Number(v);
        var c = n >= 0.6 ? "verde" : n >= 0.4 ? "ambar" : n > 0 ? "rojo" : "gris";
        return "<span class='chip " + c + "'><b>" + esc(Number(v).toFixed(3)) + "</b></span>";
      }],
      ["biomasa_estimada_kg_ha", "Biomasa MS", "text", function (v) {
        return v != null ? esc(Math.round(v).toLocaleString()) + " kg/ha" : "—";
      }],
      ["aforo_estimado_kg_m2", "Aforo MV", "text", function (v) {
        return v != null ? esc(Number(v).toFixed(2)) + " kg/m²" : "—";
      }],
      ["cobertura_nubes_pct", "Condición", "text", function (v, row) {
        var f = String(row && row.fuente || "");
        if (f.indexOf("Sentinel-1") >= 0 || f.indexOf("SAR") >= 0) {
          return "<span style='font-size:11.5px; color:#1e3c72; font-weight:600;'>🛡️ Penetra nubes</span>";
        }
        var n = Number(v) || 0;
        return n > 0 ? "<span style='font-size:11.5px;'>☁️ " + esc(n.toFixed(0)) + "% nubes</span>" : "<span style='font-size:11.5px; color:#2e7d32;'>☀️ Despejado</span>";
      }]
    ];
    h += "<h4>" + icon("chartLine") + (simple ? "Estado Reciente por Potrero" : "Lecturas Satelitales Recientes por Potrero") + "</h4>"
      + tabla(d.ndvi_reciente, columnasNdvi, "Sin lecturas satelitales recientes.");
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

  function bindPasturas() {
    var btnToggleModoPasturas = document.getElementById("btn-toggle-modo-pasturas");
    if (btnToggleModoPasturas) {
      btnToggleModoPasturas.addEventListener("click", function () {
        localStorage.setItem("modoPasturasSimple", modoPasturasEsSimple() ? "tecnico" : "simple");
        cargar(true);
      });
    }
    function ejecutarSyncSatelite(modo) {
      var btnSar = document.getElementById("btn-sync-satelite-sar");
      var btnAuto = document.getElementById("btn-sync-satelite-auto");
      var box = document.getElementById("satelite-status-box");

      if (btnSar) btnSar.disabled = true;
      if (btnAuto) btnAuto.disabled = true;

      var textoModo = (modo === "radar" || modo === "s1")
        ? "Radar SAR Sentinel-1 C-band (penetrando nubes)"
        : "Multi-sensor Auto (Sentinel-2 Óptico con respaldo Radar SAR)";

      if (box) {
        box.style.display = "block";
        box.style.background = "rgba(30, 60, 114, 0.1)";
        box.style.border = "1px solid #2a5298";
        box.style.color = "#1e3c72";
        box.innerHTML = "<div style='display:flex; align-items:center; gap:10px;'>"
          + "<span style='font-size:22px;'>🛰️</span>"
          + "<div><b>Consultando Google Earth Engine en tiempo real...</b><br>"
          + "<span style='font-size:12px;'>Procesando reflectancia " + esc(textoModo) + " para los 20 potreros de la finca. Esto toma ~10-15 segundos.</span></div>"
          + "</div>";
      }

      fetch("/api/satelite/actualizar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modo: modo })
      })
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (err) { throw new Error(err.error || ("HTTP " + r.status)); });
        }
        return r.json();
      })
      .then(function (data) {
        if (btnSar) btnSar.disabled = false;
        if (btnAuto) btnAuto.disabled = false;
        if (data.ok) {
          if (box) {
            box.style.background = "rgba(46, 125, 50, 0.1)";
            box.style.border = "1px solid #2e7d32";
            box.style.color = "#1b5e20";
            box.innerHTML = "<b>✅ " + esc(data.mensaje || "Sincronización satelital exitosa.") + "</b>"
              + "<div style='font-size:12px; margin-top:4px;'>Refrescando mapa de vigor satelital y tablas...</div>";
          }
          setTimeout(function () {
            cargar(true);
          }, 1500);
        } else {
          if (box) {
            box.style.background = "rgba(211, 47, 47, 0.1)";
            box.style.border = "1px solid #d32f2f";
            box.style.color = "#c62828";
            box.innerHTML = "<b>⚠️ Error:</b> " + esc(data.error || "No se pudo sincronizar");
          }
        }
      })
      .catch(function (err) {
        if (btnSar) btnSar.disabled = false;
        if (btnAuto) btnAuto.disabled = false;
        if (box) {
          box.style.background = "rgba(211, 47, 47, 0.1)";
          box.style.border = "1px solid #d32f2f";
          box.style.color = "#c62828";
          box.innerHTML = "<b>❌ Error de sincronización satelital:</b> " + esc(err.message || err);
        }
      });
    }

    var btnSar = document.getElementById("btn-sync-satelite-sar");
    if (btnSar) {
      btnSar.addEventListener("click", function () {
        ejecutarSyncSatelite("radar");
      });
    }
    var btnAuto = document.getElementById("btn-sync-satelite-auto");
    if (btnAuto) {
      btnAuto.addEventListener("click", function () {
        ejecutarSyncSatelite("auto");
      });
    }
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

    if (d.fotos_recibos && d.fotos_recibos.length) {
      h += "<details style='margin-top:18px;'>"
        + "<summary style='cursor:pointer; font-weight:700; padding:6px 0; display:flex; align-items:center; gap:6px;'>" + icon("camera", 16) + "Recibos y Planillas de Quincena (Fotos de Respaldo) — " + d.fotos_recibos.length + "</summary>"
        + "<p class='aviso' style='margin:10px 0;'>Fotos de recibos o planillas manuales de leche. Toca cualquier imagen para abrirla en pantalla completa con zoom táctil y verificar las anotaciones diarias.</p>"
        + "<div class='fotos-wrap' style='display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:10px;'>";
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
      h += "</div></details>";
    }

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
  var _finanzasMovsActuales = [];
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

    // Acceso directo al módulo de subastas y precios de mercado
    h += "<div style='margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; background:var(--superficie); padding:10px 14px; border-radius:8px; border:1px solid var(--borde);'>"
      + "<div style='font-size:13px; display:flex; align-items:center; gap:8px;'>" + icon("chartLine", 18) + "<span><b>Indicadores de Mercado:</b> Subastas Sugameta, Catama, Bogotá, precios de leche e insumos Ariari.</span></div>"
      + "<button type='button' class='tema-btn' id='btn-finanzas-ir-mercado' style='font-size:12px; padding:5px 12px; display:inline-flex; align-items:center; gap:5px; font-weight:600; cursor:pointer;'>" + icon("scale", 14) + "Ver Subastas &amp; Fletes</button>"
      + "</div>";

    h += "<div class='kpis'>"
      + kpi(fmtMoneda(r.total_ingresos), "Ingresos " + esc(d.desde || "") + " a " + esc(d.hasta || ""), "ok")
      + kpi(fmtMoneda(r.total_egresos), "Egresos", "alerta")
      + kpi(fmtMoneda(r.utilidad), "Utilidad", r.utilidad >= 0 ? "ok" : "alerta")
      + "</div>";

    var kf = d.kpis || {};
    h += "<h4>" + icon("chartLine") + "Indicadores de rentabilidad y eficiencia unitaria</h4>";

    // Tarjetas de Eficiencia Lechería y Carne
    h += "<div class='grid-economia'>";

    // Card 1: Lechería
    var prLeche = kf.precio_promedio_litro_leche;
    var costLeche = kf.costo_por_litro_leche;
    var mgLeche = kf.margen_por_litro_leche;
    var mgLechePct = kf.margen_leche_pct;
    var chipMgLeche = mgLeche != null
      ? ("<span class='chip " + (mgLeche >= 0 ? "verde" : "rojo") + "' style='font-weight:700;'>" + (mgLeche >= 0 ? "+" : "") + fmtMoneda(mgLeche) + "/L (" + mgLechePct + "%)</span>")
      : "<span class='chip gris'>Sin ventas registradas</span>";

    h += "<div class='card-economia'>"
      + "<div class='card-economia-header'>"
      + "<div class='card-economia-titulo'>" + icon("milk", 20) + "Línea de Producción: Leche</div>"
      + chipMgLeche
      + "</div>"
      + "<div class='kpis-economia'>"
      + "<div class='kpi-eco-box'><div class='kpi-eco-val'>" + (kf.litros_producidos != null ? kf.litros_producidos.toLocaleString("es-CO") : "0") + " L</div><div class='kpi-eco-etiq'>Volumen Producido</div></div>"
      + "<div class='kpi-eco-box'><div class='kpi-eco-val'>" + (prLeche != null ? fmtMoneda(prLeche) : "—") + "</div><div class='kpi-eco-etiq'>Precio Venta / Litro</div></div>"
      + "<div class='kpi-eco-box'><div class='kpi-eco-val' style='color:var(--rojo-alerta);'>" + (costLeche != null ? fmtMoneda(costLeche) : "—") + "</div><div class='kpi-eco-etiq'>Costo Operativo / L</div></div>"
      + "<div class='kpi-eco-box'><div class='kpi-eco-val' style='color:" + (mgLeche >= 0 ? "var(--verde-marca)" : "var(--rojo-alerta)") + ";'>" + (mgLeche != null ? fmtMoneda(mgLeche) : "—") + "</div><div class='kpi-eco-etiq'>Margen Neto / Litro</div></div>"
      + "</div>"
      + "<div class='progreso-margen-wrap'><div style='display:flex; justify-content:space-between; font-size:11.5px;'><span>Ingresos Leche: <b>" + fmtMoneda(kf.ingresos_leche || 0) + "</b></span><span>Rentabilidad: <b>" + (mgLechePct != null ? mgLechePct + "%" : "—") + "</b></span></div>"
      + "<div class='progreso-margen-bar'><div class='progreso-margen-fill' style='width:" + Math.min(100, Math.max(0, mgLechePct || 0)) + "%; background:" + (mgLeche >= 0 ? "var(--verde-marca)" : "var(--rojo-alerta)") + ";'></div></div></div>"
      + "</div>";

    // Card 2: Carne
    var prCarne = kf.precio_promedio_kg_carne;
    var costCarne = kf.costo_por_kg_carne;
    var mgCarne = kf.margen_por_kg_carne;
    var mgCarnePct = kf.margen_carne_pct;
    var chipMgCarne = mgCarne != null
      ? ("<span class='chip " + (mgCarne >= 0 ? "verde" : "rojo") + "' style='font-weight:700;'>" + (mgCarne >= 0 ? "+" : "") + fmtMoneda(mgCarne) + "/kg (" + mgCarnePct + "%)</span>")
      : "<span class='chip gris'>Sin ventas con peso</span>";

    h += "<div class='card-economia'>"
      + "<div class='card-economia-header'>"
      + "<div class='card-economia-titulo'>" + icon("scale", 20) + "Línea de Ganado: Carne &amp; Levante</div>"
      + chipMgCarne
      + "</div>"
      + "<div class='kpis-economia'>"
      + "<div class='kpi-eco-box'><div class='kpi-eco-val'>" + (kf.animales_vendidos != null ? kf.animales_vendidos : 0) + " cab (" + (kf.kg_carne_estimados != null ? Math.round(kf.kg_carne_estimados) : 0) + " kg)</div><div class='kpi-eco-etiq'>Ventas Realizadas</div></div>"
      + "<div class='kpi-eco-box'><div class='kpi-eco-val'>" + (prCarne != null ? fmtMoneda(prCarne) : (kf.precio_promedio_animal ? fmtMoneda(kf.precio_promedio_animal) + "/cab" : "—")) + "</div><div class='kpi-eco-etiq'>Precio Venta / kg</div></div>"
      + "<div class='kpi-eco-box'><div class='kpi-eco-val' style='color:var(--rojo-alerta);'>" + (costCarne != null ? fmtMoneda(costCarne) : "—") + "</div><div class='kpi-eco-etiq'>Costo Producción / kg</div></div>"
      + "<div class='kpi-eco-box'><div class='kpi-eco-val' style='color:" + (mgCarne >= 0 ? "var(--verde-marca)" : "var(--rojo-alerta)") + ";'>" + (mgCarne != null ? fmtMoneda(mgCarne) : "—") + "</div><div class='kpi-eco-etiq'>Margen Neto / kg</div></div>"
      + "</div>"
      + "<div class='progreso-margen-wrap'><div style='display:flex; justify-content:space-between; font-size:11.5px;'><span>Ingresos Venta Ganado: <b>" + fmtMoneda(kf.ingresos_carne || 0) + "</b></span><span>Rentabilidad: <b>" + (mgCarnePct != null ? mgCarnePct + "%" : "—") + "</b></span></div>"
      + "<div class='progreso-margen-bar'><div class='progreso-margen-fill' style='width:" + Math.min(100, Math.max(0, mgCarnePct || 0)) + "%; background:" + (mgCarne >= 0 ? "var(--verde-marca)" : "var(--rojo-alerta)") + ";'></div></div></div>"
      + "</div>";

    h += "</div>";

    // Resumen Global de Rentabilidad
    h += "<div class='kpis'>"
      + kpi(kf.margen_utilidad_pct != null ? kf.margen_utilidad_pct + "%" : "—", "Margen global de utilidad", kf.margen_utilidad_pct != null && kf.margen_utilidad_pct < 0 ? "alerta" : "ok")
      + kpi(kf.costo_por_cabeza != null ? fmtMoneda(kf.costo_por_cabeza) : "—", "Costo por cabeza hato (" + (kf.total_activos != null ? kf.total_activos : 0) + " animales)")
      + kpi(fmtMoneda(r.total_ingresos - r.total_egresos), "Utilidad Neta Periodo", (r.total_ingresos - r.total_egresos) >= 0 ? "ok" : "alerta")
      + "</div>";
    if (kf.costo_por_kg_carne != null || kf.ventas_sin_peso) {
      h += "<p class='aviso' style='margin-top:-6px;'>⚠️ Costo por kg de carne es un <b>estimado</b>: usa el último pesaje registrado antes de cada venta (no se pesa el animal en el momento exacto de vender)."
        + (kf.ventas_sin_peso ? " " + kf.ventas_sin_peso + " venta(s) sin ningún pesaje previo quedaron fuera del cálculo." : "") + "</p>";
    }
    h += grafico("flujo_caja", "Flujo de caja mensual");

    h += "<h4>" + icon("chartBar") + "Desglose por categoría</h4>"
      + tabla(r.categorias, [
        ["tipo", "Tipo", "text", function (v) { return "<span class='chip " + (v === "INGRESO" ? "verde" : "rojo") + "'>" + esc(v) + "</span>"; }],
        ["categoria", "Categoría", "text", function (v) { return esc(etiquetaCategoriaFinanza(v)); }],
        ["total", "Monto", "text", function (v) { return "<b>" + fmtMoneda(v) + "</b>"; }],
        ["n", "# Registros", "num"]
      ], "Sin ingresos ni egresos registrados en este periodo.");

    var movs = (d.recientes || []).map(function (f) {
      return {
        id: f.id, origen: "finanza",
        fecha: f.fecha, tipo: f.tipo, categoria: etiquetaCategoriaFinanza(f.categoria), categoria_raw: f.categoria,
        detalle: f.concepto || "", monto: f.monto, litros: f.litros,
        animal_tag: f.animal_tag || null,
        otro_txt: f.animal_tag ? "" : (f.contraparte || f.potrero_nombre || ""),
        contraparte: f.contraparte || null, potrero_nombre: f.potrero_nombre || null,
        notas: f.notas || null, foto_ruta: f.foto_ruta || null
      };
    }).concat((d.ventas_compras || []).map(function (m) {
      return {
        id: m.id, origen: "movimiento",
        fecha: m.fecha, tipo: m.tipo_movimiento === "VENTA" ? "INGRESO" : "EGRESO",
        categoria: m.tipo_movimiento === "VENTA" ? "Venta de animales" : "Compra de animales", categoria_raw: null,
        detalle: m.notas || "", monto: m.precio, litros: null,
        animal_tag: m.animal_tag || null,
        otro_txt: m.procedencia_destino || "",
        contraparte: m.procedencia_destino || null, potrero_nombre: null,
        notas: null, foto_ruta: null
      };
    })).sort(function (a, b) { return (b.fecha || "").localeCompare(a.fecha || ""); });
    _finanzasMovsActuales = movs;

    var rolFin = window.__usuarioActual && window.__usuarioActual.rol;

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
        ["monto", "Monto", "text", function (v) { return fmtMoneda(v); }],
        ["fecha", "Acciones", "text", function (v, fila) {
          var idx = movs.indexOf(fila);
          var conFoto = fila.foto_ruta ? icon("camera", 12) : "";
          var btns = "<button type='button' class='tema-btn' data-fin-ver='" + idx + "' style='font-size:11px; padding:4px 8px; display:inline-flex; align-items:center; gap:4px;' title='Ver detalle'>" + icon("eye", 13) + conFoto + "</button>";
          if (rolFin === "OWNER" && fila.origen === "finanza") {
            btns += " <button type='button' class='tema-btn' data-fin-editar='" + idx + "' style='font-size:11px; padding:4px 8px; display:inline-flex; align-items:center;' title='Editar'>" + icon("pencil", 13) + "</button>"
              + " <button type='button' class='tema-btn' data-fin-eliminar='" + idx + "' style='font-size:11px; padding:4px 8px; display:inline-flex; align-items:center; color:var(--rojo-alerta, #c0392b);' title='Eliminar'>" + icon("xmark", 13) + "</button>";
          }
          return btns;
        }]
      ], "Sin movimientos recientes en este periodo.");

    return h;
  }

  function mostrarDetalleFinanza(fila) {
    if (!fila) return;
    var overlay = document.getElementById("fin-detalle-modal");
    if (overlay) overlay.remove();

    var animalHtml = fila.animal_tag
      ? ("<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(fila.animal_tag) + "\" style='font-weight:bold; text-decoration:none; display:inline-flex; align-items:center; gap:5px;'>" + icon("cow", 15) + "<span>" + esc(fila.animal_tag) + "</span></a>")
      : "—";

    var filasDetalle = [
      ["Fecha", esc(fechaCorta(fila.fecha))],
      ["Tipo", "<span class='chip " + (fila.tipo === "INGRESO" ? "verde" : "rojo") + "'>" + esc(fila.tipo) + "</span>"],
      ["Categoría", esc(fila.categoria)],
      ["Concepto", esc(fila.detalle) || "—"],
      ["Monto", "<b style='font-size:16px;'>" + fmtMoneda(fila.monto) + "</b>"],
      ["Animal", animalHtml]
    ];
    if (fila.litros != null) filasDetalle.push(["Litros", esc(fila.litros) + " L"]);
    if (fila.contraparte) filasDetalle.push(["Proveedor / Comprador / Trabajador", esc(fila.contraparte)]);
    if (fila.potrero_nombre) filasDetalle.push(["Potrero", esc(fila.potrero_nombre)]);
    if (fila.notas) filasDetalle.push(["Notas", esc(fila.notas)]);

    var cuerpoHtml = "<div style='display:flex; flex-direction:column; gap:8px; font-size:13.5px;'>"
      + filasDetalle.map(function (par) {
        return "<div><span style='color:var(--texto-suave); font-size:11.5px; text-transform:uppercase; display:block;'>" + esc(par[0]) + "</span>" + par[1] + "</div>";
      }).join("")
      + "</div>";

    if (fila.foto_ruta) {
      var ruta = fila.foto_ruta.indexOf("/") === 0 ? fila.foto_ruta : "/" + fila.foto_ruta;
      cuerpoHtml += "<div style='margin-top:14px;'>"
        + "<span style='color:var(--texto-suave); font-size:11.5px; text-transform:uppercase; display:block; margin-bottom:6px;'>" + icon("camera", 13) + " Foto de la Factura / Recibo</span>"
        + "<img class='zoomable-img' src='" + esc(ruta) + "' alt='Factura: " + esc(fila.detalle || fila.categoria) + "' style='max-width:100%; border-radius:8px; border:1px solid var(--borde); cursor:zoom-in; display:block;' data-onerror-hide='self'>"
        + "<small style='color:var(--texto-suave);'>Toca la imagen para ampliarla.</small>"
        + "</div>";
    } else {
      cuerpoHtml += "<p class='aviso' style='margin-top:14px;'>" + icon("camera", 13) + "Sin foto adjunta.</p>";
    }

    var html = "<div id='fin-detalle-modal' class='modal-overlay'>"
      + "<div class='modal-contenido'>"
      + "<div class='modal-header'><b>" + icon("receipt", 15) + " Detalle del Movimiento</b><button type='button' class='modal-cerrar' id='btn-cerrar-fin-detalle'>✕</button></div>"
      + "<div style='padding:16px;'>" + cuerpoHtml + "</div>"
      + "</div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("fin-detalle-modal");
    function cerrarModal() { if (ov) ov.remove(); }
    var btnCerrar = document.getElementById("btn-cerrar-fin-detalle");
    if (btnCerrar) btnCerrar.addEventListener("click", cerrarModal);
    ov.addEventListener("click", function (e) {
      if (e.target === ov || e.target.closest("[data-ir-ficha]")) cerrarModal();
    });
  }

  var CATEGORIAS_INGRESO_FINANZA = ["VENTA_LECHE", "OTRO_INGRESO"];

  function mostrarEditarFinanza(fila) {
    if (!fila) return;
    var overlay = document.getElementById("fin-editar-modal");
    if (overlay) overlay.remove();

    var opcionesCategoria = ""
      + "<optgroup label='💰 Ingresos'>"
      + "<option value='VENTA_LECHE'>Venta de leche</option>"
      + "<option value='OTRO_INGRESO'>Otro ingreso</option>"
      + "</optgroup>"
      + "<optgroup label='💸 Egresos'>"
      + "<option value='INSUMO'>Insumos (sal, alambre, herramienta, etc.)</option>"
      + "<option value='NOMINA'>Nómina / Jornales</option>"
      + "<option value='VETERINARIO'>Veterinario / Medicamentos</option>"
      + "<option value='INFRAESTRUCTURA'>Infraestructura / Mantenimiento</option>"
      + "<option value='COMBUSTIBLE'>Combustible</option>"
      + "<option value='OTRO_EGRESO'>Otro gasto</option>"
      + "</optgroup>";

    var cuerpoHtml = "<form id='form-editar-finanza' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<label>Fecha: <input type='date' id='ef-fecha' value='" + esc(fechaCorta(fila.fecha)) + "' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label>Categoría: <select id='ef-categoria' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>" + opcionesCategoria + "</select></label>"
      + "<label>Concepto: <input id='ef-concepto' value=\"" + esc(fila.detalle || "") + "\" style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label>Monto ($): <input type='number' step='1' min='0.01' id='ef-monto' value='" + esc(fila.monto) + "' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<div id='ef-litros-wrap' style='display:none;'><label>Litros vendidos: <input type='number' step='0.5' id='ef-litros' value='" + esc(fila.litros != null ? fila.litros : "") + "' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
      + "<label>Proveedor / Comprador / Trabajador: <input id='ef-contraparte' value=\"" + esc(fila.contraparte || "") + "\" style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label>Arete / Animal relacionado: <input id='ef-tag' value=\"" + esc(fila.animal_tag || "") + "\" list='dl-tags' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label>Notas: <input id='ef-notas' value=\"" + esc(fila.notas || "") + "\" style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<p id='ef-error' class='aviso' style='display:none; border-left:4px solid var(--rojo-alerta, #c0392b);'></p>"
      + "<div style='display:flex; gap:8px; justify-content:flex-end; margin-top:6px;'>"
      + "<button type='button' class='tema-btn' id='btn-cancelar-ef'>Cancelar</button>"
      + "<button type='submit' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:700; border:none;'>" + icon("save", 14) + "Guardar cambios</button>"
      + "</div></form>";

    var html = "<div id='fin-editar-modal' class='modal-overlay'>"
      + "<div class='modal-contenido'>"
      + "<div class='modal-header'><b>" + icon("pencil", 15) + " Editar Movimiento</b><button type='button' class='modal-cerrar' id='btn-cerrar-fin-editar'>✕</button></div>"
      + "<div style='padding:16px;'>" + cuerpoHtml + "</div>"
      + "</div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("fin-editar-modal");
    function cerrarModal() { if (ov) ov.remove(); }
    var btnCerrar = document.getElementById("btn-cerrar-fin-editar");
    if (btnCerrar) btnCerrar.addEventListener("click", cerrarModal);
    var btnCancelar = document.getElementById("btn-cancelar-ef");
    if (btnCancelar) btnCancelar.addEventListener("click", cerrarModal);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrarModal(); });

    var selCat = document.getElementById("ef-categoria");
    var wrapLitros = document.getElementById("ef-litros-wrap");
    selCat.value = fila.categoria_raw || "OTRO_EGRESO";
    function toggleLitros() { wrapLitros.style.display = selCat.value === "VENTA_LECHE" ? "block" : "none"; }
    selCat.addEventListener("change", toggleLitros);
    toggleLitros();

    var form = document.getElementById("form-editar-finanza");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var categoria = selCat.value;
      var payload = {
        fecha: q("#ef-fecha").value,
        categoria: categoria,
        tipo: CATEGORIAS_INGRESO_FINANZA.indexOf(categoria) !== -1 ? "INGRESO" : "EGRESO",
        concepto: q("#ef-concepto").value.trim(),
        monto: parseFloat(q("#ef-monto").value) || 0,
        litros: categoria === "VENTA_LECHE" ? (parseFloat(q("#ef-litros").value) || null) : null,
        contraparte: q("#ef-contraparte").value.trim(),
        animal_tag: q("#ef-tag").value.trim(),
        notas: q("#ef-notas").value.trim(),
      };
      var errorEl = document.getElementById("ef-error");
      fetch("/api/finanzas/" + fila.id, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      }).then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
        .then(function (res) {
          if (res.status >= 200 && res.status < 300 && res.body.ok) {
            cerrarModal();
            cargarFinanzasPeriodo();
          } else if (errorEl) {
            errorEl.textContent = "❌ " + (res.body.error || "No se pudo guardar.");
            errorEl.style.display = "block";
          }
        }).catch(function (err) {
          if (errorEl) { errorEl.textContent = "❌ " + (err && err.message || err); errorEl.style.display = "block"; }
        });
    });
  }

  function eliminarFinanzaConfirm(fila) {
    if (!fila) return;
    if (!window.confirm("¿Eliminar este movimiento (" + (fila.detalle || fila.categoria) + ", " + fmtMoneda(fila.monto) + ")? Esta acción no se puede deshacer.")) return;
    fetch("/api/finanzas/" + fila.id, { method: "DELETE" })
      .then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
      .then(function (res) {
        if (res.status >= 200 && res.status < 300 && res.body.ok) {
          cargarFinanzasPeriodo();
        } else {
          window.alert("❌ " + (res.body.error || "No se pudo eliminar."));
        }
      }).catch(function (err) {
        window.alert("❌ " + (err && err.message || err));
      });
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
    qa("[data-fin-ver]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = parseInt(btn.getAttribute("data-fin-ver"), 10);
        mostrarDetalleFinanza(_finanzasMovsActuales[idx]);
      });
    });
    qa("[data-fin-editar]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = parseInt(btn.getAttribute("data-fin-editar"), 10);
        mostrarEditarFinanza(_finanzasMovsActuales[idx]);
      });
    });
    qa("[data-fin-eliminar]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = parseInt(btn.getAttribute("data-fin-eliminar"), 10);
        eliminarFinanzaConfirm(_finanzasMovsActuales[idx]);
      });
    });
    var btnIrMercado = document.getElementById("btn-finanzas-ir-mercado");
    if (btnIrMercado) {
      btnIrMercado.addEventListener("click", function () {
        irAVista("mercado");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
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

  /* ---------- Vista: Indicadores de Mercado & Subastas Ganaderas ---------- */
  var _mercadoDatos = null;
  var _mercadoTabActual = "subastas";
  var _calcCat = "MACHO_GORDO";
  var _calcPeso = 420;
  var _calcCabezas = 15;
  var _mercadoCatGrafico = "MACHO_GORDO";
  var _mercadoVistaSubastas = "graficas"; // "graficas" o "fichas"
  var _mercadoTipoGrafico = "barras"; // "barras", "tendencia_tiempo", "oficial_ja"

  var CATEGORIAS_MERCADO_LABEL = {
    MACHO_GORDO: "Macho Gordo (400+ kg)",
    MACHO_1_1_2: "Macho 1 ½ años (Levante)",
    MACHO_LEVANTE: "Macho 1 ½ años (Levante)",
    HEMBRA_GORDA: "Hembra Gorda",
    HEMBRA_1_1_2: "Hembra 1 ½ años",
    HEMBRA_LEVANTE: "Hembra 1 ½ años",
    TERNERO_DESTETE: "Ternero(a) Destete",
    TERNERO_DESTETO: "Ternero(a) Destete",
    VACAS_DESCARTE: "Vaca Descarte",
    VACA_GORDA: "Vaca Descarte / Gorda",
    LECHE_QUESERA: "Leche Quesera Artesanal",
    LECHE_INDUSTRIA: "Leche Industria Pasteurizadora",
    LECHE_RESOLUCION_USP: "Resolución MinAgricultura USP Región 2",
    SAL_MINERAL_8: "Sal Mineralizada 8% P (40 kg)",
    SAL_MINERAL_10: "Sal Mineralizada 10% P (40 kg)",
    UREA_50KG: "Urea Agrícola 46% (50 kg)",
    ALAMBRE_PUAS_400M: "Alambre de Púas Ganadero (400 m)",
    DOLAR_TRM: "Dólar TRM Oficial (Banco República)"
  };

  function etiquetaMercado(c) { return CATEGORIAS_MERCADO_LABEL[c] || c; }

  function renderCardPlazaMercado(pz) {
    var prods = pz.productos || {};
    var filasProdHtml = "";
    var claves = Object.keys(prods);
    if (!claves.length) {
      filasProdHtml = "<div class='aviso' style='font-size:12px; margin:4px 0;'>Sin cotizaciones recientes registradas.</div>";
    } else {
      claves.forEach(function (k) {
        var it = prods[k];
        var precioTxt = fmtMoneda(it.precio_promedio) + " " + esc(it.unidad || "$/kg");
        var rangoTxt = "";
        if (it.precio_minimo && it.precio_maximo && (it.precio_minimo !== it.precio_promedio || it.precio_maximo !== it.precio_promedio)) {
          rangoTxt = " <small style='color:var(--texto-suave); font-weight:normal; font-size:11px;'>(" + fmtMoneda(it.precio_minimo) + " - " + fmtMoneda(it.precio_maximo) + ")</small>";
        }
        var iconKey = "scale";
        if (k.indexOf("MACHO") !== -1) iconKey = "cow";
        else if (k.indexOf("HEMBRA") !== -1 || k.indexOf("VACAS") !== -1 || k.indexOf("VACA_") !== -1) iconKey = "cow";
        else if (k.indexOf("TERNERO") !== -1) iconKey = "calf";

        var tendBadge = "";
        if (it.tendencia === "SUBIENDO") {
          tendBadge = " <span class='chip-tendencia subiendo' title='Subió $" + Math.abs(it.variacion_pesos) + "/kg vs semana anterior'>▲ +" + (it.variacion_pct > 0 ? it.variacion_pct : "") + "%</span>";
        } else if (it.tendencia === "BAJANDO") {
          tendBadge = " <span class='chip-tendencia bajando' title='Bajó $" + Math.abs(it.variacion_pesos) + "/kg vs semana anterior'>▼ " + it.variacion_pct + "%</span>";
        } else if (it.precio_anterior) {
          tendBadge = " <span class='chip-tendencia estable' title='Sin variación vs semana anterior'>▬ 0%</span>";
        }

        filasProdHtml += "<div class='fila-precio'>"
          + "<div class='fila-precio-etiq'>" + icon(iconKey, 14) + "<span>" + esc(etiquetaMercado(k)) + "</span></div>"
          + "<div class='fila-precio-val'><span>" + precioTxt + rangoTxt + "</span>" + tendBadge + "</div>"
          + "</div>";
      });
    }

    var distHtml = "";
    if (pz.distancia_km && pz.distancia_km > 0) {
      distHtml = "<div class='card-plaza-dist'>" + icon("pin", 13) + "<span><b>" + pz.distancia_km + " km</b> de Mesetas · ~" + pz.horas_viaje + "h vía · Merma est. <b>" + pz.desbaste_pct + "%</b> · Flete ~" + fmtMoneda(pz.flete_cab) + "/cab</span></div>";
    } else {
      distHtml = "<div class='card-plaza-dist'>" + icon("target", 13) + "<span>Promedio ponderado nacional según FEDEGÁN</span></div>";
    }

    return "<div class='card-plaza'>"
      + "<div class='card-plaza-header'>"
      + "<div>"
      + "<div class='card-plaza-titulo'>" + esc(pz.nombre) + "</div>"
      + "<div style='font-size:12px; color:var(--texto-suave); margin-top:1px;'>" + esc(pz.subtitulo) + "</div>"
      + distHtml
      + "</div>"
      + "</div>"
      + "<div class='card-plaza-precios'>" + filasProdHtml + "</div>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; font-size:11px; color:var(--texto-suave); border-top:1px solid var(--borde); padding-top:6px; margin-top:4px;'>"
      + "<span>Semana: <b>" + esc(fechaCorta(pz.fecha_actualizacion)) + "</b></span>"
      + "<span style='text-overflow:ellipsis; overflow:hidden; white-space:nowrap; max-width:160px;'>" + esc(pz.productos[claves[0]] ? pz.productos[claves[0]].fuente : "Boletín Subasta") + "</span>"
      + "</div>"
      + "</div>";
  }

  function calcularRendimientoPlaza(pz, cat, pesoFinca, cabezas) {
    var pprod = (pz.productos && pz.productos[cat]) || (pz.productos && pz.productos["MACHO_GORDO"]) || { precio_promedio: 8000 };
    var precioKg = Number(pprod.precio_promedio) || 8000;
    var desbastePct = Number(pz.desbaste_pct) || 0;
    var fleteCab = Number(pz.flete_cab) || 0;
    var totalFlete = fleteCab * cabezas;

    var pesoLlegadaCab = pesoFinca * (1 - (desbastePct / 100));
    var pesoTotalLlegada = Math.round(pesoLlegadaCab * cabezas);
    var ingresoBruto = Math.round(pesoTotalLlegada * precioKg);
    var comisionSubasta = Math.round(ingresoBruto * 0.025); // 2.5% estándar subasta
    var ingresoNeto = ingresoBruto - totalFlete - comisionSubasta;
    var precioNetoKgFinca = Math.round(ingresoNeto / (pesoFinca * cabezas));

    return {
      plaza_key: pz.plaza_key,
      nombre: pz.nombre,
      subtitulo: pz.subtitulo,
      distancia_km: pz.distancia_km,
      horas_viaje: pz.horas_viaje,
      desbaste_pct: desbastePct,
      flete_cab: fleteCab,
      total_flete: totalFlete,
      precio_kg: precioKg,
      peso_llegada_cab: Math.round(pesoLlegadaCab * 10) / 10,
      peso_total_llegada: pesoTotalLlegada,
      ingreso_bruto: ingresoBruto,
      comision_subasta: comisionSubasta,
      ingreso_neto: ingresoNeto,
      precio_neto_kg_finca: precioNetoKgFinca
    };
  }

  function renderCalculadoraFleteHtml(d) {
    var subastasReales = (d.subastas || []).filter(function (s) { return s.plaza_key !== "PROMEDIO_NACIONAL"; });
    var simulaciones = subastasReales.map(function (pz) {
      return calcularRendimientoPlaza(pz, _calcCat, _calcPeso, _calcCabezas);
    });

    simulaciones.sort(function (a, b) { return b.ingreso_neto - a.ingreso_neto; });
    var mejor = simulaciones[0];

    var opcionesCat = [
      ["MACHO_GORDO", "Macho Gordo (400+ kg)"],
      ["MACHO_1_1_2", "Macho 1 ½ años (Levante)"],
      ["HEMBRA_GORDA", "Hembra Gorda"],
      ["HEMBRA_1_1_2", "Hembra 1 ½ años"],
      ["TERNERO_DESTETE", "Ternero(a) Destete"],
      ["VACAS_DESCARTE", "Vaca Descarte"]
    ].map(function (c) {
      return "<option value='" + c[0] + "'" + (c[0] === _calcCat ? " selected" : "") + ">" + c[1] + "</option>";
    }).join("");

    var filasTabla = simulaciones.map(function (sim) {
      var esGanador = mejor && sim.plaza_key === mejor.plaza_key;
      var claseFila = esGanador ? "calc-resultado-ganador" : "";
      var badgeGanador = esGanador ? " <span class='chip verde' style='font-size:10.5px; font-weight:700;'>🌟 Mayor Ingreso</span>" : "";

      return "<tr class='" + claseFila + "'>"
        + "<td><b>" + esc(sim.nombre) + "</b>" + badgeGanador + "<div style='font-size:11px; color:var(--texto-suave);'>" + sim.distancia_km + " km · ~" + sim.horas_viaje + "h</div></td>"
        + "<td><span class='chip ambar' style='font-size:11.5px;'>" + sim.desbaste_pct + "%</span></td>"
        + "<td><b>" + sim.peso_llegada_cab + " kg</b><div style='font-size:11px; color:var(--texto-suave);'>Tot: " + sim.peso_total_llegada.toLocaleString("es-CO") + " kg</div></td>"
        + "<td><b>" + fmtMoneda(sim.precio_kg) + "</b></td>"
        + "<td>" + fmtMoneda(sim.ingreso_bruto) + "</td>"
        + "<td style='color:var(--rojo-alerta);'>-" + fmtMoneda(sim.total_flete) + "<div style='font-size:10.5px; color:var(--texto-suave);'>" + fmtMoneda(sim.flete_cab) + "/cab</div></td>"
        + "<td style='color:var(--rojo-alerta);'>-" + fmtMoneda(sim.comision_subasta) + "</td>"
        + "<td style='background:rgba(47,82,51,0.06);'><b style='font-size:14px; color:var(--verde-marca);'>" + fmtMoneda(sim.ingreso_neto) + "</b></td>"
        + "<td><b style='font-size:13px;'>" + fmtMoneda(sim.precio_neto_kg_finca) + "/kg</b><div style='font-size:10.5px; color:var(--texto-suave);'>puesto finca</div></td>"
        + "</tr>";
    }).join("");

    var resumenMejorHtml = "";
    if (mejor) {
      var diffGranada = 0;
      var granadaSim = simulaciones.filter(function (s) { return s.plaza_key === "GRANADA"; })[0];
      var comparativaTexto = "";
      if (granadaSim && mejor.plaza_key !== "GRANADA") {
        diffGranada = mejor.ingreso_neto - granadaSim.ingreso_neto;
        comparativaTexto = " Al enviar a <b>" + esc(mejor.nombre) + "</b> ganas <b>" + fmtMoneda(diffGranada) + " más</b> en total que vendiendo en Granada, compensando con creces el mayor flete y el desbaste por distancia.";
      } else if (granadaSim && mejor.plaza_key === "GRANADA") {
        var segundo = simulaciones[1];
        if (segundo) {
          comparativaTexto = " Por la cercanía (68 km, 1.5h) y baja merma de peso (2.5%), vender en <b>Granada</b> te deja <b>" + fmtMoneda(mejor.ingreso_neto - segundo.ingreso_neto) + " más neto en el bolsillo</b> que llevarlos a " + esc(segundo.nombre) + ".";
        }
      }

      resumenMejorHtml = "<div class='card' style='background:rgba(22,163,74,0.08); border:1.5px solid #16a34a; padding:14px; margin-top:14px; border-radius:10px;'>"
        + "<div style='display:flex; align-items:center; gap:8px; font-weight:700; color:var(--verde-marca); font-size:14px; margin-bottom:4px;'>"
        + icon("sparkles", 18) + "<span>Opción Más Rentable desde Mesetas: " + esc(mejor.nombre) + "</span>"
        + "</div>"
        + "<p style='margin:0; font-size:13px; line-height:1.5;'>"
        + "Para un lote de <b>" + _calcCabezas + " cabezas</b> de " + esc(etiquetaMercado(_calcCat)) + " (" + _calcPeso + " kg promedio), el ingreso neto en tu bolsillo es de <b>" + fmtMoneda(mejor.ingreso_neto) + "</b> (equivalente a <b>" + fmtMoneda(mejor.precio_neto_kg_finca) + "/kg</b> neto puesto en báscula de tu finca)."
        + comparativaTexto
        + "</p>"
        + "</div>";
    }

    return "<div class='calc-flete-box'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
      + "<div>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("truck", 18) + "Calculadora de Flete, Merma (Desbaste) &amp; Ingreso Neto</h4>"
      + "<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>Simulación de rentabilidad real saliendo desde <b>Mesetas, Meta</b> hacia las diferentes subastas y frigoríficos.</div>"
      + "</div>"
      + "<div class='chip azul' style='font-size:11px;'>Comisión subasta: 2.5%</div>"
      + "</div>"
      + "<div class='calc-flete-inputs'>"
      + "<label style='font-size:12px; font-weight:600;'>Categoría de Ganado:<select id='calc-cat' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:4px; font-size:13px;'>" + opcionesCat + "</select></label>"
      + "<label style='font-size:12px; font-weight:600;'>Peso Promedio Finca (kg):<input type='number' id='calc-peso' value='" + _calcPeso + "' min='100' max='900' step='5' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:4px; font-size:13px;'></label>"
      + "<label style='font-size:12px; font-weight:600;'>Cantidad de Cabezas:<input type='number' id='calc-cabezas' value='" + _calcCabezas + "' min='1' max='200' step='1' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:4px; font-size:13px;'></label>"
      + "</div>"
      + "<div class='tabla-scroll'><table>"
      + "<tr>"
      + "<th>Plaza Destino</th>"
      + "<th>Merma (Desbaste)</th>"
      + "<th>Peso Llegada</th>"
      + "<th>Precio Subasta</th>"
      + "<th>Ingreso Bruto</th>"
      + "<th>Flete Total</th>"
      + "<th>Comisión (2.5%)</th>"
      + "<th>Ingreso Neto Bolsillo</th>"
      + "<th>$/kg Neto Finca</th>"
      + "</tr>"
      + filasTabla
      + "</table></div>"
      + resumenMejorHtml
      + "</div>";
  }

  function renderLecheInsumosHtml(d) {
    var leche = d.leche || {};
    var insumos = d.insumos || [];
    var prFincaReal = leche.precio_finca_real;

    var bannerLecheFinca = "";
    if (prFincaReal) {
      bannerLecheFinca = "<div class='card' style='background:rgba(47,82,51,0.06); border:1px solid var(--verde-marca); padding:12px 16px; margin-bottom:12px; border-radius:8px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
        + "<div><div style='font-size:11.5px; color:var(--texto-suave); text-transform:uppercase; font-weight:700;'>Tu Liquidación Real en la Finca</div>"
        + "<div style='font-size:22px; font-weight:800; color:var(--verde-marca);'>" + fmtMoneda(prFincaReal) + " <span style='font-size:13px; font-weight:600;'>/ litro</span></div></div>"
        + "<div style='font-size:12px; color:var(--texto); max-width:340px;'>Calculado automáticamente a partir de tus registros de venta de leche en Finanzas.</div>"
        + "</div>";
    }

    var refLecheHtml = (leche.referencias || []).map(function (it) {
      return "<div class='card-insumo'>"
        + "<div style='display:flex; justify-content:space-between; align-items:flex-start;'>"
        + "<div><div style='font-size:13.5px; font-weight:700; color:var(--texto);'>" + esc(it.nombre) + "</div><div style='font-size:11.5px; color:var(--texto-suave); margin-top:2px;'>" + esc(it.fuente) + "</div></div>"
        + "<div style='font-size:16px; font-weight:800; color:var(--verde-marca);'>" + fmtMoneda(it.precio) + " <span style='font-size:11px;'>/" + esc(it.unidad) + "</span></div>"
        + "</div>"
        + "</div>";
    }).join("");

    var cardsInsumosHtml = insumos.map(function (ins) {
      var novilloRel = "";
      if (ins.kg_novillo_equivalentes && ins.codigo !== "DOLAR_TRM") {
        novilloRel = "<div style='margin-top:8px; padding-top:6px; border-top:1px dashed var(--borde); font-size:12px; display:flex; align-items:center; gap:5px; color:var(--texto-suave);'>"
          + icon("scale", 13) + "<span>Equivale a: <b>" + ins.kg_novillo_equivalentes + " kg</b> de novillo gordo en Granada</span></div>";
      }
      return "<div class='card-insumo'>"
        + "<div style='display:flex; justify-content:space-between; align-items:flex-start;'>"
        + "<div><div style='font-size:13.5px; font-weight:700; color:var(--texto);'>" + esc(ins.nombre) + "</div><div style='font-size:11.5px; color:var(--texto-suave); margin-top:2px;'>" + esc(ins.fuente) + " · " + esc(fechaCorta(ins.fecha)) + "</div></div>"
        + "<div style='font-size:16px; font-weight:800; color:var(--verde-marca);'>" + fmtMoneda(ins.precio) + " <span style='font-size:11px;'>/" + esc(ins.unidad) + "</span></div>"
        + "</div>"
        + novilloRel
        + "</div>";
    }).join("");

    return "<div>"
      + "<h4>" + icon("milk", 18) + "Precios de Referencia del Litro de Leche</h4>"
      + bannerLecheFinca
      + "<div class='grid-insumos' style='margin-bottom:20px;'>" + refLecheHtml + "</div>"
      + "<h4>" + icon("salt", 18) + "Insumos Clave en el Ariari &amp; Poder Adquisitivo</h4>"
      + "<p class='aviso' style='margin:4px 0 10px 0; font-size:12.5px;'>Relación de intercambio: cuántos kilos de novillo en pie se requieren para adquirir cada insumo comercial en la región.</p>"
      + "<div class='grid-insumos'>" + cardsInsumosHtml + "</div>"
      + "</div>";
  }

  function mostrarModalFuentesMercado(fuentes) {
    var overlay = document.getElementById("mercado-fuentes-modal");
    if (overlay) overlay.remove();

    var listaHtml = (fuentes || []).map(function (f) {
      return "<div style='background:var(--superficie); border:1px solid var(--borde); border-radius:8px; padding:10px 14px; margin-bottom:8px;'>"
        + "<div style='font-weight:700; font-size:13.5px; color:var(--texto);'>" + esc(f.nombre) + "</div>"
        + "<div style='font-size:12.5px; color:var(--texto-suave); margin-top:2px;'>" + esc(f.descripcion) + "</div>"
        + "</div>";
    }).join("");

    var cuerpoHtml = "<div style='font-size:13px; line-height:1.5;'>"
      + "<p style='margin:0 0 12px 0;'>La información del módulo de mercado consolida cotizaciones oficiales semanales y precios observados en el comercio agropecuario del Piedemonte y Ariari:</p>"
      + listaHtml
      + "<div style='margin-top:12px; font-size:12px; color:var(--texto-suave); font-style:italic;'>"
      + "Nota: Los datos de fletes y desbaste son estimados para camión ganadero saliendo desde Mesetas, Meta, según el estado vial habitual."
      + "</div>"
      + "</div>";

    var html = "<div id='mercado-fuentes-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:500px;'>"
      + "<div class='modal-header'><b>" + icon("clipboard", 15) + " Fuentes Oficiales &amp; Metodología</b><button type='button' class='modal-cerrar' id='btn-cerrar-fuentes-modal'>✕</button></div>"
      + "<div style='padding:16px;'>" + cuerpoHtml + "</div>"
      + "</div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("mercado-fuentes-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-fuentes-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });
  }

  function mostrarModalActualizarMercado(d) {
    var overlay = document.getElementById("mercado-actualizar-modal");
    if (overlay) overlay.remove();

    var plazasOpciones = [
      ["GRANADA", "Granada (Meta) - Sugameta"],
      ["GUAMAL", "Guamal (Meta) - Sugameta"],
      ["SAN_MARTIN", "San Martín (Meta) - Sugameta"],
      ["CATAMA", "Villavicencio - Subagaucho Catama"],
      ["PUERTO_LOPEZ", "Puerto López - Suballanos"],
      ["YOPAL", "Yopal (Casanare) - Subacasanare"],
      ["BOGOTA", "Bogotá - Frigorífico Guadalupe"],
      ["PROMEDIO_NACIONAL", "Promedio Nacional - FEDEGÁN"],
      ["META_REGIONAL", "Meta Regional (General)"],
      ["ARIARI_LOCAL", "Comercio Local Ariari (Insumos)"]
    ].map(function (p) { return "<option value='" + p[0] + "'>" + p[1] + "</option>"; }).join("");

    var productosOpciones = [
      ["MACHO_GORDO", "Macho Gordo (400+ kg)"],
      ["MACHO_1_1_2", "Macho 1 ½ años (Levante)"],
      ["HEMBRA_GORDA", "Hembra Gorda"],
      ["HEMBRA_1_1_2", "Hembra 1 ½ años"],
      ["TERNERO_DESTETE", "Ternero(a) Destete"],
      ["VACAS_DESCARTE", "Vaca Descarte"],
      ["LECHE_QUESERA", "Leche Quesera Artesanal ($/L)"],
      ["LECHE_INDUSTRIA", "Leche Industria Pasteurizadora ($/L)"],
      ["LECHE_RESOLUCION_USP", "Leche Resolución USP Región 2 ($/L)"],
      ["SAL_MINERAL_8", "Sal Mineralizada 8% P (Bulto 40kg)"],
      ["SAL_MINERAL_10", "Sal Mineralizada 10% P (Bulto 40kg)"],
      ["UREA_50KG", "Urea Agrícola 46% (Bulto 50kg)"],
      ["ALAMBRE_PUAS_400M", "Alambre de Púas Ganadero (Rollo 400m)"],
      ["DOLAR_TRM", "Dólar TRM Oficial (Banco República)"]
    ].map(function (pr) { return "<option value='" + pr[0] + "'>" + pr[1] + "</option>"; }).join("");

    var hoyFmt = new Date().toISOString().slice(0, 10);

    var formHtml = "<form id='form-actualizar-mercado' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<label style='font-size:12.5px; font-weight:600;'>Plaza / Mercado:"
      + "<select id='up-plaza' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'>" + plazasOpciones + "</select></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Producto o Categoría:"
      + "<select id='up-producto' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'>" + productosOpciones + "</select></label>"
      + "<div style='display:flex; gap:10px;'>"
      + "<label style='flex:1; font-size:12.5px; font-weight:600;'>Precio Promedio ($):"
      + "<input type='number' id='up-promedio' step='1' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'></label>"
      + "<label style='flex:1; font-size:12.5px; font-weight:600;'>Unidad de Medida:"
      + "<select id='up-unidad' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'>"
      + "<option value='$/kg'>$/kg</option><option value='$/litro'>$/litro</option><option value='$/bulto 40kg'>$/bulto 40kg</option><option value='$/bulto 50kg'>$/bulto 50kg</option><option value='$/rollo 400m'>$/rollo 400m</option><option value='COP/USD'>COP/USD</option>"
      + "</select></label>"
      + "</div>"
      + "<div style='display:flex; gap:10px;'>"
      + "<label style='flex:1; font-size:12px; font-weight:600;'>Precio Máximo ($ opcional):"
      + "<input type='number' id='up-max' step='1' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'></label>"
      + "<label style='flex:1; font-size:12px; font-weight:600;'>Precio Mínimo ($ opcional):"
      + "<input type='number' id='up-min' step='1' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'></label>"
      + "</div>"
      + "<div style='display:flex; gap:10px;'>"
      + "<label style='flex:1; font-size:12px; font-weight:600;'>Fuente:"
      + "<input type='text' id='up-fuente' placeholder='ej. Sugameta Martes' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'></label>"
      + "<label style='flex:1; font-size:12px; font-weight:600;'>Fecha Cotización:"
      + "<input type='date' id='up-fecha' value='" + hoyFmt + "' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'></label>"
      + "</div>"
      + "<label style='font-size:12px; font-weight:600;'>Notas / Observaciones:"
      + "<input type='text' id='up-notas' placeholder='ej. Lote cebú comercial' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:2px;'></label>"
      + "<div id='up-mercado-error' style='color:var(--rojo-alerta); font-size:12.5px; display:none;'></div>"
      + "<button type='submit' class='tema-btn' style='margin-top:6px; background:var(--verde-marca); color:#fff; font-weight:700; padding:10px; border:none; border-radius:6px; cursor:pointer;'>Guardar Precio en la Base de Datos</button>"
      + "</form>";

    var html = "<div id='mercado-actualizar-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:480px;'>"
      + "<div class='modal-header'><b>" + icon("pencil", 15) + " Actualizar Cotización de Mercado</b><button type='button' class='modal-cerrar' id='btn-cerrar-act-modal'>✕</button></div>"
      + "<div style='padding:16px;'>" + formHtml + "</div>"
      + "</div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("mercado-actualizar-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-act-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

    var selProd = document.getElementById("up-producto");
    var selUni = document.getElementById("up-unidad");
    if (selProd && selUni) {
      selProd.addEventListener("change", function () {
        var v = selProd.value;
        if (v.indexOf("LECHE") !== -1) selUni.value = "$/litro";
        else if (v.indexOf("SAL_") !== -1) selUni.value = "$/bulto 40kg";
        else if (v.indexOf("UREA") !== -1) selUni.value = "$/bulto 50kg";
        else if (v.indexOf("ALAMBRE") !== -1) selUni.value = "$/rollo 400m";
        else if (v === "DOLAR_TRM") selUni.value = "COP/USD";
        else selUni.value = "$/kg";
      });
    }

    var form = document.getElementById("form-actualizar-mercado");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = document.getElementById("up-mercado-error");
      var pProm = parseFloat(document.getElementById("up-promedio").value);
      var pMax = document.getElementById("up-max").value ? parseFloat(document.getElementById("up-max").value) : null;
      var pMin = document.getElementById("up-min").value ? parseFloat(document.getElementById("up-min").value) : null;

      if (!pProm || isNaN(pProm)) {
        if (errEl) { errEl.textContent = "El precio promedio es requerido y debe ser un número."; errEl.style.display = "block"; }
        return;
      }

      var payload = {
        plaza: document.getElementById("up-plaza").value,
        producto: document.getElementById("up-producto").value,
        precio_promedio: pProm,
        precio_maximo: pMax,
        precio_minimo: pMin,
        unidad: document.getElementById("up-unidad").value,
        fuente: document.getElementById("up-fuente").value || "MANUAL",
        fecha: document.getElementById("up-fecha").value,
        notas: document.getElementById("up-notas").value
      };

      fetch("/api/mercado/actualizar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
        .then(function (res) {
          if (res.ok && res.body.ok) {
            cerrar();
            cargar(true);
          } else {
            if (errEl) { errEl.textContent = "❌ " + (res.body.error || "No se pudo actualizar el precio."); errEl.style.display = "block"; }
          }
        }).catch(function (err) {
          if (errEl) { errEl.textContent = "❌ Error de conexión: " + (err && err.message || err); errEl.style.display = "block"; }
        });
    });
  }

  function renderKpisMercado(d) {
    var res = d.resumen_tendencias || {};
    var cats = [
      ["MACHO_GORDO", "Macho Gordo", "cow"],
      ["MACHO_LEVANTE", "Macho Levante", "cow"],
      ["TERNERO_DESTETO", "Ternero Desteto", "calf"],
      ["VACA_GORDA", "Vaca Descarte", "cow"]
    ];

    var htmlCards = cats.map(function (c) {
      var k = res[c[0]];
      if (!k) return "";
      var tendBadge = "";
      if (k.tendencia === "SUBIENDO") {
        tendBadge = "<span class='chip-tendencia subiendo'>▲ +" + (k.variacion_pct > 0 ? k.variacion_pct : "") + "% (+$" + Math.abs(k.variacion_pesos) + ")</span>";
      } else if (k.tendencia === "BAJANDO") {
        tendBadge = "<span class='chip-tendencia bajando'>▼ " + k.variacion_pct + "% (-$" + Math.abs(k.variacion_pesos) + ")</span>";
      } else {
        tendBadge = "<span class='chip-tendencia estable'>▬ 0.0% ($0)</span>";
      }

      var grTxt = k.precio_granada ? ("Granada: <b>" + fmtMoneda(k.precio_granada) + "</b>") : "";
      var topTxt = k.plaza_top ? ("Top: <b>" + esc(k.plaza_top.split("(")[0].trim()) + " " + fmtMoneda(k.precio_top) + "</b>") : "";

      return "<div class='mercado-kpi-card'>"
        + "<div class='mercado-kpi-tit'>" + icon(c[2], 13) + "<span>" + esc(c[1]) + "</span></div>"
        + "<div class='mercado-kpi-val'>" + fmtMoneda(k.promedio_mercado) + "<span style='font-size:12px; font-weight:normal; color:var(--texto-suave);'>/kg</span> " + tendBadge + "</div>"
        + "<div class='mercado-kpi-sub'><span>" + grTxt + "</span><span>·</span><span>" + topTxt + "</span></div>"
        + "</div>";
    }).join("");

    return "<div class='mercado-kpi-grid'>" + htmlCards + "</div>";
  }

  function renderPillsCategoriasMercado() {
    var cats = [
      ["MACHO_GORDO", "Macho Gordo (400+ kg)", "cow"],
      ["MACHO_LEVANTE", "Macho Levante", "cow"],
      ["TERNERO_DESTETO", "Ternero Desteto", "calf"],
      ["HEMBRA_LEVANTE", "Hembra Levante", "cow"],
      ["VACA_GORDA", "Vaca Descarte", "cow"]
    ];
    return "<div class='mercado-cat-pills'>"
      + cats.map(function (c) {
        var act = (c[0] === _mercadoCatGrafico) ? " act" : "";
        return "<button type='button' class='mercado-pill" + act + "' data-cat-pill='" + c[0] + "'>"
          + icon(c[2], 14) + "<span>" + esc(c[1]) + "</span>"
          + "</button>";
      }).join("")
      + "</div>";
  }

  function renderBarrasComparativasHtml(d, cat) {
    var comp = (d.comparativa_por_categoria && d.comparativa_por_categoria[cat]) || [];
    if (!comp.length) {
      return "<div class='aviso'>No hay cotizaciones registradas para " + esc(etiquetaMercado(cat)) + "</div>";
    }

    var precios = comp.map(function (c) { return c.precio_promedio; });
    var maxPrecio = Math.max.apply(null, precios);
    var minPrecio = Math.min.apply(null, precios);
    var rango = maxPrecio - minPrecio;
    if (rango <= 0) rango = 1000;
    var baseMin = Math.max(0, minPrecio - rango * 0.35);

    var filasHtml = comp.map(function (c, idx) {
      var p = c.precio_promedio;
      var pctAncho = Math.round(((p - baseMin) / (maxPrecio - baseMin)) * 75 + 25);
      pctAncho = Math.min(100, Math.max(15, pctAncho));

      var esGranada = (c.plaza_key === "GRANADA");
      var esTop = (idx === 0);
      var esNal = (c.plaza_key === "PROMEDIO_NACIONAL");

      var claseRow = "mercado-bar-row";
      if (esGranada) claseRow += " destacado-granada";
      if (esTop && !esGranada) claseRow += " destacado-top";

      var badgePlaza = "";
      if (esGranada) {
        badgePlaza = " <span class='chip verde' style='font-size:10px; font-weight:700;'>📍 Plaza Local Finca</span>";
      } else if (esTop) {
        badgePlaza = " <span class='chip ambar' style='font-size:10px; font-weight:700;'>👑 Mayor Precio</span>";
      } else if (esNal) {
        badgePlaza = " <span class='chip gris' style='font-size:10px; font-weight:600;'>🇨🇴 Consolidado</span>";
      }

      var colFill = "#3b7a57";
      if (esGranada) colFill = "var(--verde-marca)";
      else if (esTop) colFill = "#16a34a";
      else if (esNal) colFill = "#64748b";

      var tendBadge = "";
      if (c.tendencia === "SUBIENDO") {
        tendBadge = "<span class='chip-tendencia subiendo'>▲ +" + (c.variacion_pct > 0 ? c.variacion_pct : "") + "% (+$" + Math.abs(c.variacion_pesos) + ")</span>";
      } else if (c.tendencia === "BAJANDO") {
        tendBadge = "<span class='chip-tendencia bajando'>▼ " + c.variacion_pct + "% (-$" + Math.abs(c.variacion_pesos) + ")</span>";
      } else {
        tendBadge = "<span class='chip-tendencia estable'>▬ 0.0% ($0)</span>";
      }

      var diffGranadaHtml = "";
      if (!esGranada && c.diff_granada !== undefined && c.diff_granada !== null) {
        if (c.diff_granada > 0) {
          diffGranadaHtml = "<span style='color:#16a34a; font-weight:700;'>+" + fmtMoneda(c.diff_granada) + "/kg vs Granada</span>";
        } else if (c.diff_granada < 0) {
          diffGranadaHtml = "<span style='color:var(--texto-suave);'>" + fmtMoneda(c.diff_granada) + "/kg vs Granada</span>";
        } else {
          diffGranadaHtml = "<span style='color:var(--texto-suave);'>Igual a Granada</span>";
        }
      } else if (esGranada) {
        diffGranadaHtml = "<span style='color:var(--verde-marca); font-weight:700;'>Base Local (68 km)</span>";
      }

      var distTxt = c.distancia_km > 0
        ? (c.distancia_km + " km · ~" + c.horas_viaje + "h vía")
        : "Consolidado País";

      return "<div class='" + claseRow + "'>"
        + "<div class='mercado-bar-meta'>"
        + "<div><b>#" + (idx + 1) + " " + esc(c.nombre) + "</b>" + badgePlaza + "</div>"
        + "<div style='display:flex; align-items:center; gap:8px;'>"
        + "<b style='font-size:15px; color:var(--texto);'>" + fmtMoneda(p) + " <span style='font-size:11px; font-weight:normal;'>/kg</span></b>"
        + tendBadge
        + "</div>"
        + "</div>"
        + "<div class='mercado-bar-track'><div class='mercado-bar-fill' style='width:" + pctAncho + "%; background:" + colFill + ";'></div></div>"
        + "<div class='mercado-bar-sub'>"
        + "<span>" + icon("pin", 12) + " " + esc(distTxt) + " · Merma est: <b>" + c.desbaste_pct + "%</b></span>"
        + "<div>" + diffGranadaHtml + "</div>"
        + "</div>"
        + "</div>";
    }).join("");

    return "<div class='mercado-chart-box'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
      + "<div>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("chartBar", 18) + "Comparativa de Cotizaciones · " + esc(etiquetaMercado(cat)) + "</h4>"
      + "<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>Precios en pie ordenados de mayor a menor con variación vs semana anterior y diferencial con Granada.</div>"
      + "</div>"
      + "<div class='chip verde' style='font-size:11px;'>8 Plazas Ganaderas</div>"
      + "</div>"
      + filasHtml
      + "</div>";
  }

  function renderSvgTendenciaSemanalHtml(d, cat) {
    var comp = (d.comparativa_por_categoria && d.comparativa_por_categoria[cat]) || [];
    if (!comp.length) return "";

    var plazasClave = [
      { key: "GRANADA", nombre: "Granada (Local)", color: "#2F5233", dash: "" },
      { key: "CATAMA", nombre: "Catama (Villavicencio)", color: "#16a34a", dash: "" },
      { key: "BOGOTA", nombre: "Bogotá (Guadalupe)", color: "#2563eb", dash: "" },
      { key: "PROMEDIO_NACIONAL", nombre: "Promedio Nacional", color: "#64748b", dash: "5,4" }
    ];

    var series = [];
    var todasFechasSet = {};

    plazasClave.forEach(function (pc) {
      var c = comp.filter(function (x) { return x.plaza_key === pc.key; })[0];
      if (c && c.historico_semanal && c.historico_semanal.length) {
        c.historico_semanal.forEach(function (h) { todasFechasSet[h.fecha] = true; });
        series.push({
          key: pc.key,
          nombre: pc.nombre,
          color: pc.color,
          dash: pc.dash,
          historico: c.historico_semanal
        });
      }
    });

    var fechas = Object.keys(todasFechasSet).sort();
    if (fechas.length < 2) {
      return "<div class='aviso'>Datos históricos en recopilación para graficar tendencia temporal.</div>";
    }

    var W = 620, H = 270;
    var padTop = 25, padRight = 65, padBottom = 35, padLeft = 55;
    var plotW = W - padLeft - padRight;
    var plotH = H - padTop - padBottom;

    var allPrecios = [];
    series.forEach(function (s) {
      s.historico.forEach(function (h) { allPrecios.push(h.precio); });
    });
    var minP = Math.min.apply(null, allPrecios);
    var maxP = Math.max.apply(null, allPrecios);
    var spanP = maxP - minP;
    if (spanP <= 0) spanP = 500;
    var yMin = Math.floor((minP - spanP * 0.15) / 100) * 100;
    var yMax = Math.ceil((maxP + spanP * 0.15) / 100) * 100;
    var ySpan = yMax - yMin;

    function getX(idx) {
      return padLeft + Math.round((idx / (fechas.length - 1)) * plotW);
    }
    function getY(p) {
      return padTop + plotH - Math.round(((p - yMin) / ySpan) * plotH);
    }

    var gridLinesHtml = "";
    var pasosY = 4;
    for (var step = 0; step <= pasosY; step++) {
      var valY = yMin + (ySpan / pasosY) * step;
      var yCoord = getY(valY);
      gridLinesHtml += "<line x1='" + padLeft + "' y1='" + yCoord + "' x2='" + (W - padRight) + "' y2='" + yCoord + "' stroke='var(--borde)' stroke-dasharray='3,3' stroke-width='1'/>"
        + "<text x='" + (padLeft - 6) + "' y='" + (yCoord + 4) + "' fill='var(--texto-suave)' font-size='10' text-anchor='end'>$" + Math.round(valY).toLocaleString('es-CO') + "</text>";
    }

    var xLabelsHtml = "";
    fechas.forEach(function (f, idx) {
      var xC = getX(idx);
      var partesF = String(f).split("-");
      var dObj = partesF.length === 3 ? new Date(+partesF[0], +partesF[1] - 1, +partesF[2]) : null;
      var txtF = dObj ? (dObj.getDate() + " " + ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"][dObj.getMonth()]) : f;
      xLabelsHtml += "<text x='" + xC + "' y='" + (H - 12) + "' fill='var(--texto-suave)' font-size='10' text-anchor='middle'>" + esc(txtF) + "</text>";
    });

    var pathsHtml = "";
    series.forEach(function (s) {
      var pts = [];
      var circlesHtml = "";
      var mapaFec = {};
      s.historico.forEach(function (h) { mapaFec[h.fecha] = h.precio; });

      fechas.forEach(function (f, idx) {
        if (mapaFec[f] !== undefined) {
          var xC = getX(idx);
          var yC = getY(mapaFec[f]);
          pts.push(xC + "," + yC);
          circlesHtml += "<circle cx='" + xC + "' cy='" + yC + "' r='4.5' fill='" + s.color + "' stroke='var(--superficie)' stroke-width='1.5'>"
            + "<title>" + esc(s.nombre) + ": $" + mapaFec[f].toLocaleString('es-CO') + " (" + f + ")</title></circle>";
        }
      });

      if (pts.length > 1) {
        var dashAttr = s.dash ? " stroke-dasharray='" + s.dash + "'" : "";
        pathsHtml += "<polyline fill='none' stroke='" + s.color + "' stroke-width='2.5' points='" + pts.join(" ") + "'" + dashAttr + "/>"
          + circlesHtml;

        var ultFec = fechas[fechas.length - 1];
        if (mapaFec[ultFec] !== undefined) {
          var ultX = getX(fechas.length - 1);
          var ultY = getY(mapaFec[ultFec]);
          pathsHtml += "<text x='" + (ultX + 7) + "' y='" + (ultY + 4) + "' fill='" + s.color + "' font-size='10.5' font-weight='bold'>$" + mapaFec[ultFec].toLocaleString('es-CO') + "</text>";
        }
      }
    });

    var leyendaHtml = "<div style='display:flex; flex-wrap:wrap; gap:14px; margin-top:8px; font-size:12px; justify-content:center;'>"
      + series.map(function (s) {
        var dashStyle = s.dash ? "border-top:2px dashed " + s.color : "background:" + s.color;
        return "<div style='display:flex; align-items:center; gap:6px;'>"
          + "<span style='display:inline-block; width:16px; height:4px; " + dashStyle + "; border-radius:2px;'></span>"
          + "<span><b>" + esc(s.nombre) + "</b></span>"
          + "</div>";
      }).join("")
      + "</div>";

    var resTend = d.resumen_tendencias && d.resumen_tendencias[cat];
    var insightHtml = "";
    if (resTend) {
      var flechaTend = resTend.tendencia === "SUBIENDO" ? "📈" : (resTend.tendencia === "BAJANDO" ? "📉" : "📊");
      var dirTxt = resTend.tendencia === "SUBIENDO" ? "ALCISTA" : (resTend.tendencia === "BAJANDO" ? "BAJISTA" : "ESTABLE");
      insightHtml = "<div class='mercado-insight-box'>"
        + "<div><b>" + flechaTend + " Interpretación de Mercado (" + esc(etiquetaMercado(cat)) + "):</b></div>"
        + "<div style='margin-top:4px;'>Tendencia semanal <b>" + dirTxt + "</b> con variación promedio del <b>" + (resTend.variacion_pct > 0 ? "+" : "") + resTend.variacion_pct + "%</b> (" + fmtMoneda(resTend.variacion_pesos) + "/kg). En <b>Granada</b> cotiza a <b>" + fmtMoneda(resTend.precio_granada) + "/kg</b> (" + (resTend.variacion_granada_pct > 0 ? "+" : "") + resTend.variacion_granada_pct + "%). La plaza más alta es <b>" + esc(resTend.plaza_top) + "</b> (" + fmtMoneda(resTend.precio_top) + "/kg).</div>"
        + "</div>";
    }

    return "<div class='mercado-chart-box'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<div>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("chartLine", 18) + "Tendencia Histórica Semanal · " + esc(etiquetaMercado(cat)) + "</h4>"
      + "<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>Evolución de cotizaciones semanales ($/kg en pie) en las últimas 7 semanas.</div>"
      + "</div>"
      + "<div class='chip azul' style='font-size:11px;'>Evolución 7 Semanas</div>"
      + "</div>"
      + "<div class='mercado-svg-wrap'>"
      + "<svg viewBox='0 0 " + W + " " + H + "' width='100%' height='auto'>"
      + gridLinesHtml
      + xLabelsHtml
      + pathsHtml
      + "</svg>"
      + "</div>"
      + leyendaHtml
      + insightHtml
      + "</div>";
  }

  function renderGraficaOficialJaHtml(d, cat) {
    var tNow = Date.now();
    return "<div class='mercado-chart-box'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
      + "<div>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("sparkles", 18) + "Gráfica Oficial Ganadería JA</h4>"
      + "<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>Renderizada con tipografía de alta resolución y marca de agua institucional.</div>"
      + "</div>"
      + "<div class='chip verde' style='font-size:11px;'>Alta Definición</div>"
      + "</div>"
      + "<div style='display:flex; flex-direction:column; gap:16px;'>"
      + "<div class='grafico-wrap'><img src='/api/grafico/subastas_comparativa?t=" + tNow + "' alt='Comparativa de Subastas Ganadería JA' loading='lazy'></div>"
      + "<div class='grafico-wrap'><img src='/api/grafico/subastas_tendencia?t=" + tNow + "' alt='Tendencia Semanal Subastas Ganadería JA' loading='lazy'></div>"
      + "</div>"
      + "</div>";
  }

  function renderSubastasTabHtml(d) {
    var viewBtns = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
      + "<div style='display:flex; gap:6px; align-items:center;'>"
      + "<button type='button' class='tema-btn" + (_mercadoVistaSubastas === "graficas" ? " act' style='background:var(--verde-marca); color:#fff; font-weight:700;'" : "'") + " data-subastas-view='graficas'>" + icon("chartBar", 13) + " Gráficas &amp; Comparativas</button>"
      + "<button type='button' class='tema-btn" + (_mercadoVistaSubastas === "fichas" ? " act' style='background:var(--verde-marca); color:#fff; font-weight:700;'" : "'") + " data-subastas-view='fichas'>" + icon("clipboard", 13) + " Fichas por Plaza (8)</button>"
      + "</div>"
      + "</div>";

    if (_mercadoVistaSubastas === "fichas") {
      var cardsPlazas = (d.subastas || []).map(renderCardPlazaMercado).join("");
      return viewBtns + "<div class='grid-plazas'>" + cardsPlazas + "</div>";
    }

    // Modo Gráficas
    var kpisHtml = renderKpisMercado(d);
    var pillsHtml = renderPillsCategoriasMercado();

    var chartModeBtns = "<div style='display:flex; gap:6px; align-items:center; flex-wrap:wrap; margin-bottom:10px;'>"
      + "<span style='font-size:12px; font-weight:700; color:var(--texto-suave);'>Vista:</span>"
      + "<button type='button' class='tema-btn" + (_mercadoTipoGrafico === "barras" ? " act' style='background:var(--verde-marca); color:#fff; font-weight:700;'" : "'") + " data-chart-mode='barras'>" + icon("chartBar", 13) + " Barras Comparativas</button>"
      + "<button type='button' class='tema-btn" + (_mercadoTipoGrafico === "tendencia_tiempo" ? " act' style='background:var(--verde-marca); color:#fff; font-weight:700;'" : "'") + " data-chart-mode='tendencia_tiempo'>" + icon("chartLine", 13) + " Evolución Semanal</button>"
      + "<button type='button' class='tema-btn" + (_mercadoTipoGrafico === "oficial_ja" ? " act' style='background:var(--verde-marca); color:#fff; font-weight:700;'" : "'") + " data-chart-mode='oficial_ja'>" + icon("sparkles", 13) + " Gráfica Oficial JA</button>"
      + "</div>";

    var chartContent = "";
    if (_mercadoTipoGrafico === "barras") {
      chartContent = renderBarrasComparativasHtml(d, _mercadoCatGrafico);
    } else if (_mercadoTipoGrafico === "tendencia_tiempo") {
      chartContent = renderSvgTendenciaSemanalHtml(d, _mercadoCatGrafico);
    } else {
      chartContent = renderGraficaOficialJaHtml(d, _mercadoCatGrafico);
    }

    return viewBtns + kpisHtml + pillsHtml + chartModeBtns + "<div id='mercado-grafico-contenedor'>" + chartContent + "</div>";
  }

  function renderMercado(d) {
    _mercadoDatos = d;
    var rol = (d.rol || (window.__usuarioActual && window.__usuarioActual.rol) || "").toUpperCase();
    var puedeEditar = (rol === "OWNER" || rol === "ADMIN" || rol === "ADMINISTRADOR");

    var btnActPrecios = puedeEditar
      ? "<button type='button' class='tema-btn' id='btn-actualizar-precios-mercado' style='font-size:12px; padding:6px 12px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;'>" + icon("pencil", 13) + "Actualizar Precios</button>"
      : "";

    var btnSincronizar = puedeEditar
      ? "<button type='button' class='tema-btn' id='btn-sincronizar-mercado' style='font-size:12px; padding:6px 12px; display:inline-flex; align-items:center; gap:5px; font-weight:600; cursor:pointer;'>" + icon("refresh", 13) + "Sincronizar Ahora</button>"
      : "";

    var badgeSync = "<div style='display:inline-flex; align-items:center; gap:6px; font-size:11.5px; background:rgba(30,126,52,0.12); color:#155724; padding:3px 10px; border-radius:12px; font-weight:600; border:1px solid rgba(30,126,52,0.25);'>"
      + "<span style='display:inline-block; width:7px; height:7px; border-radius:50%; background:#28a745;'></span>"
      + "Auto-sincronizado: <b>" + esc(fechaCorta(d.ultima_actualizacion || d.fecha_consulta)) + "</b>"
      + (d.trm_actual ? " · TRM: <b>" + fmtMoneda(d.trm_actual) + " COP</b>" : "")
      + "</div>";

    var headerHtml = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;'>"
      + "<div>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("chartLine", 22) + "Indicadores Económicos &amp; Subastas Ganaderas</h3>"
      + "<div style='display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:4px;'>"
      + "<span style='font-size:12px; color:var(--texto-suave);'>" + icon("pin", 12) + "Finca: <b>" + esc(d.ubicacion_finca || "Mesetas, Meta") + "</b></span>"
      + badgeSync
      + "</div>"
      + "</div>"
      + "<div style='display:flex; gap:8px; align-items:center; flex-wrap:wrap;'>"
      + "<button type='button' class='tema-btn' id='btn-fuentes-mercado' style='font-size:12px; padding:6px 12px; display:inline-flex; align-items:center; gap:5px;'>" + icon("clipboard", 13) + "Fuentes Oficiales</button>"
      + btnSincronizar
      + btnActPrecios
      + "</div>"
      + "</div>";

    var subnavHtml = "<div class='mercado-subnav'>"
      + "<button type='button' class='mercado-tab-btn" + (_mercadoTabActual === "subastas" ? " act" : "") + "' data-mercado-tab='subastas'>" + icon("scale", 14) + "Subastas Ganado (8 Plazas)</button>"
      + "<button type='button' class='mercado-tab-btn" + (_mercadoTabActual === "calculadora" ? " act" : "") + "' data-mercado-tab='calculadora'>" + icon("truck", 14) + "Calculadora Flete &amp; Venta</button>"
      + "<button type='button' class='mercado-tab-btn" + (_mercadoTabActual === "leche_insumos" ? " act" : "") + "' data-mercado-tab='leche_insumos'>" + icon("milk", 14) + "Leche &amp; Insumos Ariari</button>"
      + "</div>";

    var cuerpoHtml = "";
    if (_mercadoTabActual === "subastas") {
      var subastasHtml = renderSubastasTabHtml(d);
      var noticiasHtml = "";
      if (d.noticias_recientes && d.noticias_recientes.length > 0) {
        var itemsNoticias = d.noticias_recientes.map(function (n) {
          return "<li style='margin-bottom:6px; font-size:12px;'>"
            + "<a href='" + esc(n.enlace) + "' target='_blank' rel='noopener noreferrer' style='color:var(--verde-marca); font-weight:600; text-decoration:none; display:inline-flex; align-items:center; gap:4px;'>"
            + icon("newspaper", 13) + esc(n.titulo)
            + "</a>"
            + (n.fecha ? " <span style='color:var(--texto-suave); font-size:11px;'>(" + esc(fechaCorta(n.fecha)) + ")</span>" : "")
            + "</li>";
        }).join("");
        noticiasHtml = "<div class='card' style='margin-top:14px; padding:14px 16px; background:var(--tarjeta-bg); border:1px solid var(--borde); border-radius:8px;'>"
          + "<div style='font-weight:700; font-size:13px; margin-bottom:8px; display:flex; align-items:center; gap:6px;'>"
          + icon("newspaper", 16) + "Últimos Boletines y Noticias Ganaderas (FEDEGÁN / CONtexto Ganadero)"
          + "</div>"
          + "<ul style='margin:0; padding-left:18px; line-height:1.45;'>" + itemsNoticias + "</ul>"
          + "</div>";
      }
      cuerpoHtml = subastasHtml + noticiasHtml;
    } else if (_mercadoTabActual === "calculadora") {
      cuerpoHtml = renderCalculadoraFleteHtml(d);
    } else if (_mercadoTabActual === "leche_insumos") {
      cuerpoHtml = renderLecheInsumosHtml(d);
    }

    var avisoReferencia = (d && d.es_datos_referencia)
      ? "<div class='chip ambar' style='margin-bottom:10px;'>⚠️ Datos de referencia de jul-sep 2026. Actualiza con el botón Sincronizar.</div>"
      : "";

    return headerHtml + avisoReferencia + subnavHtml + "<div id='mercado-contenido-tab'>" + cuerpoHtml + "</div>";
  }

  function bindMercado(d) {
    _mercadoDatos = d;

    // Pestañas internas
    qa(".mercado-tab-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tab = btn.getAttribute("data-mercado-tab");
        if (tab && tab !== _mercadoTabActual) {
          _mercadoTabActual = tab;
          montarVista(vista, renderMercado(_mercadoDatos), false);
          bindMercado(_mercadoDatos);
        }
      });
    });

    // Sub-vistas en Subastas (Gráficas vs Fichas)
    qa("[data-subastas-view]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = btn.getAttribute("data-subastas-view");
        if (v && v !== _mercadoVistaSubastas) {
          _mercadoVistaSubastas = v;
          montarVista(vista, renderMercado(_mercadoDatos), false);
          bindMercado(_mercadoDatos);
        }
      });
    });

    // Modos de gráfico (Barras vs Tendencia en el Tiempo vs Gráfica Oficial JA)
    qa("[data-chart-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var m = btn.getAttribute("data-chart-mode");
        if (m && m !== _mercadoTipoGrafico) {
          _mercadoTipoGrafico = m;
          montarVista(vista, renderMercado(_mercadoDatos), false);
          bindMercado(_mercadoDatos);
        }
      });
    });

    // Pills de selección de categoría zootécnica
    qa("[data-cat-pill]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var c = btn.getAttribute("data-cat-pill");
        if (c && c !== _mercadoCatGrafico) {
          _mercadoCatGrafico = c;
          montarVista(vista, renderMercado(_mercadoDatos), false);
          bindMercado(_mercadoDatos);
        }
      });
    });

    // Botón Fuentes Oficiales
    var btnFuentes = document.getElementById("btn-fuentes-mercado");
    if (btnFuentes) {
      btnFuentes.addEventListener("click", function () {
        mostrarModalFuentesMercado(d.fuentes_oficiales);
      });
    }

    // Botón Sincronizar Ahora (Fuerza actualización automática)
    var btnSync = document.getElementById("btn-sincronizar-mercado");
    if (btnSync) {
      btnSync.addEventListener("click", function () {
        btnSync.disabled = true;
        btnSync.innerHTML = icon("refresh", 13) + " Sincronizando...";
        fetch("/api/mercado/sincronizar", {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          btnSync.disabled = false;
          btnSync.innerHTML = icon("refresh", 13) + " Sincronizar Ahora";
          if (res && res.ok) {
            cargar(true);
          } else {
            alert("No se pudo sincronizar: " + ((res && res.error) || "Error desconocido"));
          }
        })
        .catch(function (err) {
          btnSync.disabled = false;
          btnSync.innerHTML = icon("refresh", 13) + " Sincronizar Ahora";
          alert("Error de conexión al sincronizar: " + (err && err.message || err));
        });
      });
    }

    // Botón Actualizar Precios
    var btnAct = document.getElementById("btn-actualizar-precios-mercado");
    if (btnAct) {
      btnAct.addEventListener("click", function () {
        mostrarModalActualizarMercado(d);
      });
    }

    // Eventos de la Calculadora de Fletes
    if (_mercadoTabActual === "calculadora") {
      var selCat = document.getElementById("calc-cat");
      var inPeso = document.getElementById("calc-peso");
      var inCab = document.getElementById("calc-cabezas");

      function recalcular() {
        if (selCat) _calcCat = selCat.value;
        if (inPeso) _calcPeso = Math.max(100, Math.min(1000, parseFloat(inPeso.value) || 420));
        if (inCab) _calcCabezas = Math.max(1, Math.min(500, parseInt(inCab.value, 10) || 15));
        var box = document.getElementById("mercado-contenido-tab");
        if (box) {
          box.innerHTML = renderCalculadoraFleteHtml(_mercadoDatos);
          bindMercadoInputsCalc();
        }
      }

      function bindMercadoInputsCalc() {
        var sc = document.getElementById("calc-cat");
        var ip = document.getElementById("calc-peso");
        var ic = document.getElementById("calc-cabezas");
        if (sc) sc.addEventListener("change", recalcular);
        if (ip) ip.addEventListener("input", recalcular);
        if (ic) ic.addEventListener("input", recalcular);
      }

      bindMercadoInputsCalc();
    }
  }

  /* ---------- Vistas WS-5: Inventario / Población / Genética / Agenda ---------- */
  var COLORES_HATO_SG = {
    "Cría macho": "#66bb6a", "Cría hembra": "#2e7d32",
    "Levante macho": "#26a69a", "Levante hembra": "#00838f",
    "Novilla de vientre": "#5c6bc0", "Vaca parida": "#1b5e20",
    "Vaca seca": "#f9a825", "Macho de ceba/levante adulto": "#8d6e63",
    "Reproductor": "#6d4c41"
  };
  function barraApiladaCategorias(filas) {
    if (!filas || !filas.length) return vacio("Sin datos.");
    var segs = "", leyenda = "";
    filas.forEach(function (f) {
      var color = COLORES_HATO_SG[f.categoria] || "#90a4ae";
      var pct = Math.max(0, Number(f.pct) || 0);
      segs += "<div style='width:" + pct + "%; background:" + color + ";' title=\"" + esc(f.categoria) + ": " + esc(f.n) + " (" + esc(f.pct) + "%)\"></div>";
      leyenda += "<span style='display:inline-flex; align-items:center; gap:5px;'>"
        + "<span style='width:10px; height:10px; border-radius:2px; background:" + color + "; display:inline-block; flex-shrink:0;'></span>"
        + esc(f.categoria) + " <b>" + esc(f.n) + "</b> (" + esc(f.pct) + "%)</span>";
    });
    return "<div style='display:flex; height:30px; border-radius:7px; overflow:hidden; border:1px solid var(--borde-fuerte); margin-bottom:12px;'>" + segs + "</div>"
      + "<div style='display:flex; flex-wrap:wrap; gap:8px 16px; font-size:12.5px; margin-bottom:6px;'>" + leyenda + "</div>";
  }
  // Lista de potreros con barra proporcional al más cargado (reemplaza la
  // tabla plana "Potrero | Cabezas" -- de un vistazo se ve cuál potrero
  // concentra más animales, sin tener que leer y comparar números).
  function barraDistribucionPotreros(filas) {
    if (!filas || !filas.length) return vacio("Ningún potrero con animales.");
    var max = 0;
    filas.forEach(function (f) { max = Math.max(max, Number(f.n) || 0); });
    var h = "<div style='display:flex; flex-direction:column; gap:7px;'>";
    filas.forEach(function (f) {
      var nom = String(f.potrero || "");
      var n = Number(f.n) || 0;
      var pct = max > 0 ? Math.max(4, Math.round((n / max) * 100)) : 0;
      var esReal = nom && nom.toLowerCase() !== "sin potrero";
      var etiqueta = esReal
        ? "<a href='/?v=tablero&potrero=" + encodeURIComponent(nom) + "' style='font-weight:600; font-size:13px; text-decoration:none; color:var(--texto-color);'>" + esc(nom) + "</a>"
        : "<span style='font-weight:600; font-size:13px; color:var(--texto-suave);'>" + esc(nom) + "</span>";
      h += "<div style='display:flex; align-items:center; gap:10px;'>"
        + "<div style='min-width:130px; max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;' title=\"" + esc(nom) + "\">" + etiqueta + "</div>"
        + "<div style='flex:1; background:var(--superficie); border-radius:6px; height:20px; overflow:hidden; border:1px solid var(--borde-suave);'>"
        + "<div style='width:" + pct + "%; height:100%; background:var(--verde-marca); border-radius:6px;'></div>"
        + "</div>"
        + "<b style='min-width:32px; text-align:right; font-size:13px;'>" + esc(n) + "</b>"
        + "</div>";
    });
    h += "</div>";
    return h;
  }
  function renderInventario(d) {
    // Vista única Inventario + Población: tabla SG + pirámide + GMD + gráficos.
    var expBtn = "<button type='button' class='tema-btn' data-accion='exportar-inventario' style='float:right; font-size:12px; padding:4px 10px; margin-top:-4px;'>" + icon("download", 14) + "Exportar CSV</button>";
    var rolInv = window.__usuarioActual && window.__usuarioActual.rol;
    if (rolInv === "OWNER" || rolInv === "ADMIN") {
      expBtn = "<button type='button' class='tema-btn' data-accion='crear-animal' style='float:right; font-size:12px; padding:4px 10px; margin-top:-4px; margin-right:8px; background:var(--verde-marca); color:#fff; font-weight:700; border:none;'>" + icon("plus", 14) + "Crear Animal</button>" + expBtn;
    }
    var h = "<h3>" + icon("cow") + "Inventario y Población" + expBtn + "</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.total_activos, "Activos totales")
      + kpi(d.total_hembras, "Hembras") + kpi(d.total_machos, "Machos")
      + kpi(d.edad_promedio != null ? d.edad_promedio + "a" : "—", "Edad promedio")
      + kpi(d.total_sin_sexo, "Sin clasificar", d.total_sin_sexo > 0 ? "alerta" : "")
      + kpi(d.terneros_menor_12m, "Crías <12m")
      + (d.tasa_descarte ? kpi(d.tasa_descarte.pct + "%", "Tasa de descarte " + d.tasa_descarte.ano, d.tasa_descarte.pct > 20 ? "alerta" : "") : "")
      + "</div>";
    h += grafico("waterfall_inventario", "Movimientos del hato (entradas/salidas)");
    var eh = d.estructura_hato;
    h += "<h4>" + icon("cow") + "Estructura del hato</h4>";
    if (!eh || !eh.filas || !eh.filas.length) {
      h += vacio("Sin animales activos para clasificar.");
    } else {
      h += barraApiladaCategorias(eh.filas);
      h += "<div class='tabla-scroll'><table><tr><th>Categoría</th><th>Cabezas</th><th>%</th><th>UGG (est.)</th></tr>";
      eh.filas.forEach(function (f) {
        h += "<tr><td>" + esc(f.categoria) + "</td><td>" + esc(f.n) + "</td><td>" + esc(f.pct) + "%</td><td>" + esc(f.ugg) + "</td></tr>";
      });
      h += "<tr style='font-weight:700;'><td>Total</td><td>" + esc(eh.total) + "</td><td>100%</td><td>" + esc(eh.total_ugg) + "</td></tr>";
      h += "</table></div>";
      h += "<p class='aviso' style='margin-top:6px;'>UGG (Unidad Gran Ganado) estimado con factores estándar por categoría, no con el peso real de cada animal.</p>";
    }
    h += "<h4>" + icon("chartLine") + "Distribución por Categorías de Edad</h4>";
    h += "<div class='tabla-scroll'><table><tr><th>Categoría</th><th>Nro</th><th>Distrib.</th><th>Acum.</th></tr>";
    (d.filas || []).forEach(function (f) {
      h += "<tr><td>" + esc(f.categoria) + "</td><td>" + esc(f.n) + "</td><td>" + esc(f.pct) + "%</td><td>" + esc(f.acum) + "%</td></tr>";
    });
    h += "</table></div>";
    h += "<h4>" + icon("grass") + "Distribución por potrero</h4>";
    h += barraDistribucionPotreros(d.por_potrero);
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
      h += "<h4>" + icon("chartBar") + "Distribución por raza</h4>" + grafico("composicion_racial", "Composición genética (razas)");
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

    // Panel de Notificaciones Web Push (Alertas Sanitarias, Celos AM-PM, Voisin, Nitrógeno)
    h += "<div class='card' style='margin-top:16px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>"
      + "<div style='flex:1; min-width:240px;'>"
      + "<h4 style='margin:0 0 4px 0; display:flex; align-items:center; gap:6px;'>" + icon("bell", 16) + "Notificaciones Push en este Celular / Dispositivo</h4>"
      + "<p id='push-estado-txt' style='margin:0; font-size:12.5px; color:var(--texto-suave);'>Consultando permisos del dispositivo...</p>"
      + "</div>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap;'>"
      + "<button type='button' id='btn-activar-push' class='tema-btn' style='padding:6px 12px; font-size:12px;'>" + icon("bell", 14) + "Activar Alertas</button>"
      + "<button type='button' id='btn-probar-push' class='tema-btn' style='padding:6px 12px; font-size:12px; background:var(--bg-suave); color:var(--texto-base);'>" + icon("send", 14) + "Probar Notificación</button>"
      + "</div>"
      + "</div>"
      + "</div>";

    return h;
  }

  /* ---------- Notificaciones Nativas & Web Push ---------- */
  function mostrarNotificacionNativa(titulo, opts) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    opts = opts || {};
    opts.icon = opts.icon || "/static/icon-192.png";
    opts.badge = opts.badge || "/static/icon-192.png";
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.ready.then(function (reg) {
        if (reg && reg.showNotification) {
          reg.showNotification(titulo, opts);
        } else {
          new Notification(titulo, opts);
        }
      }).catch(function () {
        try { new Notification(titulo, opts); } catch (e) {}
      });
    } else {
      try { new Notification(titulo, opts); } catch (e) {}
    }
  }

  function registrarSuscripcionPushEnServidor(endpoint, keys) {
    fetch("/api/push/suscribir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: endpoint,
        keys: keys || {}
      })
    }).catch(function () {});
  }

  function iniciarWebPush(mostrarFeedback) {
    if (!("Notification" in window)) {
      if (mostrarFeedback) alert("Este navegador no soporta notificaciones Web Push.");
      return Promise.reject("no_support");
    }
    return Notification.requestPermission().then(function (perm) {
      if (perm === "granted") {
        if ("serviceWorker" in navigator) {
          navigator.serviceWorker.ready.then(function (reg) {
            if ("PushManager" in window && reg.pushManager) {
              reg.pushManager.getSubscription().then(function (sub) {
                if (sub) {
                  var sJson = sub.toJSON ? sub.toJSON() : {};
                  registrarSuscripcionPushEnServidor(sub.endpoint, sJson.keys);
                } else {
                  var devEndpoint = "pwa-local://" + (localStorage.getItem("bitacora_dev_id") || (function () {
                    var nid = "dev_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
                    localStorage.setItem("bitacora_dev_id", nid);
                    return nid;
                  })());
                  registrarSuscripcionPushEnServidor(devEndpoint, {});
                }
              }).catch(function () {
                var devEndpoint = "pwa-local://" + (localStorage.getItem("bitacora_dev_id") || "dev_default");
                registrarSuscripcionPushEnServidor(devEndpoint, {});
              });
            }
          });
        }
        if (mostrarFeedback) {
          mostrarNotificacionNativa("🔔 Notificaciones Activadas", {
            body: "¡Listo! Recibirás alertas sanitarias, celos AM-PM y avisos de potrero en este dispositivo.",
            tag: "push-bienvenida"
          });
        }
        verificarAlertasPush();
      } else if (mostrarFeedback) {
        alert("Las notificaciones fueron denegadas o bloqueadas.");
      }
      return perm;
    });
  }

  function verificarAlertasPush() {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    fetch("/api/push/alertas").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (d) {
      if (!d || !d.alertas || !d.alertas.length) return;
      var storageKey = "bitacora_push_notified";
      var notificados = {};
      try { notificados = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch (e) {}

      d.alertas.forEach(function (al) {
        var idAl = al.tipo + "_" + (al.tag || al.potrero || "finca") + "_" + (al.mensaje || "");
        var lastTime = notificados[idAl] || 0;
        var now = Date.now();
        // Notificar como máximo una vez cada 8 horas por la misma alerta
        if (now - lastTime < 8 * 3600 * 1000) return;

        notificados[idAl] = now;
        var targetUrl = "/?v=agenda";
        if (al.tipo === "voisin_sobrepastoreo") targetUrl = "/?v=mapa";
        else if (al.tipo === "celo_am_pm") targetUrl = "/?v=repro";

        mostrarNotificacionNativa(al.titulo || "Alerta Bitácora JA", {
          body: al.mensaje,
          tag: idAl,
          data: { url: targetUrl }
        });
      });

      try { localStorage.setItem(storageKey, JSON.stringify(notificados)); } catch (e) {}
    }).catch(function () {});
  }

  function bindAgenda() {
    var estadoEl = document.getElementById("push-estado-txt");
    var btnActivar = document.getElementById("btn-activar-push");
    var btnProbar = document.getElementById("btn-probar-push");

    function actualizarTextoEstado() {
      if (!estadoEl) return;
      if (!("Notification" in window)) {
        estadoEl.innerHTML = "<span style='color:var(--texto-suave);'>❌ Tu navegador no soporta notificaciones nativas.</span>";
        if (btnActivar) btnActivar.style.display = "none";
        if (btnProbar) btnProbar.style.display = "none";
        return;
      }
      if (Notification.permission === "granted") {
        estadoEl.innerHTML = "<span style='color:var(--verde-marca); font-weight:600;'>✅ Notificaciones activas en este dispositivo.</span> Recibirás alertas de retiros de carne/leche, celos AM-PM, termo criogénico y Voisin.";
        if (btnActivar) btnActivar.textContent = "Re-sincronizar";
      } else if (Notification.permission === "denied") {
        estadoEl.innerHTML = "<span style='color:var(--rojo-alerta); font-weight:600;'>🚫 Notificaciones bloqueadas.</span> Habilita los permisos en la barra de direcciones o ajustes del navegador.";
        if (btnActivar) btnActivar.disabled = true;
      } else {
        estadoEl.innerHTML = "<span style='color:var(--ambar-alerta); font-weight:600;'>⚠️ Desactivadas.</span> Actívalas para recibir alertas de retiros sanitarios, celos e inventario crítico.";
        if (btnActivar) btnActivar.disabled = false;
      }
    }

    actualizarTextoEstado();

    if (btnActivar) {
      btnActivar.addEventListener("click", function () {
        btnActivar.disabled = true;
        iniciarWebPush(true).finally(function () {
          btnActivar.disabled = false;
          actualizarTextoEstado();
        });
      });
    }

    if (btnProbar) {
      btnProbar.addEventListener("click", function () {
        if (!("Notification" in window) || Notification.permission !== "granted") {
          iniciarWebPush(true).then(function (perm) {
            if (perm === "granted") lanzarPruebaPush();
          });
        } else {
          lanzarPruebaPush();
        }
      });
    }

    function lanzarPruebaPush() {
      fetch("/api/push/probar", { method: "POST" })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res && res.notificacion) {
            var n = res.notificacion;
            mostrarNotificacionNativa(n.titulo, {
              body: n.cuerpo,
              tag: n.tag,
              data: { url: n.url }
            });
          }
        });
    }
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
      + "<input id='manga-peso' type='number' step='0.5' inputmode='decimal' class='manga-input-grande' placeholder='0.0' style='color:var(--verde-marca); font-size:38px; margin-bottom:12px;'>"
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
          // BLOQUE 4 (ráfaga): vibración corta de error + campo en rojo.
          if (navigator.vibrate) { try { navigator.vibrate([40, 40, 40]); } catch (eVibManga) { /* noop */ } }
          if (inpPeso) inpPeso.style.borderColor = "var(--color-rojo-txt)";
          alert("El peso debe ser un número válido mayor a 0.");
          return;
        }
        if (inpPeso) inpPeso.style.borderColor = "";

        var resBox = document.getElementById("manga-resultado-kpi");

        function procesarResultadoLocal(data) {
          enviarTelemetriaSilenciosa("pesaje_manga");
          // BLOQUE 4 (ráfaga): vibración larga de éxito. Solo se limpian tag
          // y peso (el resto del formulario se mantiene) y el cursor vuelve
          // al tag para pesar el siguiente animal sin tocar la pantalla.
          if (navigator.vibrate) { try { navigator.vibrate([80, 40, 80]); } catch (eVibOk) { /* noop */ } }
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
            if (navigator.vibrate) { try { navigator.vibrate([80, 40, 80]); } catch (eVibOff) { /* noop */ } }
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
            if (navigator.vibrate) { try { navigator.vibrate([80, 40, 80]); } catch (eVibOff2) { /* noop */ } }
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
      { id: "destete", nom: "Destete", ico: "destete" },
      { id: "secado", nom: "Secado", ico: "milk" },
      { id: "celo", nom: "Celo", ico: "flame" },
      { id: "servicio", nom: "Servicio / IA", ico: "sperm" },
      { id: "leche", nom: "Leche", ico: "milk" },
      { id: "muerte", nom: "Muerte / Descarte", ico: "cowSkull" },
      { id: "gasto", nom: "Ingreso / Gasto", ico: "banknote" }
    ];

    var h = "<h3>" + icon("clipboard") + "Captura Rápida de Campo (Online / Offline)</h3>";
    h += "<p class='aviso'>Registra eventos directamente en el potrero. Si estás sin señal, se guardarán en la cola local de tu celular y se sincronizarán al volver a la casa.</p>";

    // BLOQUE 4: stepper de captura en 3 pasos (1=tipo, 2=datos, 3=preview).
    // El form envuelve los 3 pasos; el submit real solo vive en el paso 3.
    h += "<div class='cap-pasos' aria-hidden='true'>"
      + "<span class='chip verde' id='cap-ind-1'>1 · Tipo</span>"
      + "<span class='chip gris' id='cap-ind-2'>2 · Datos</span>"
      + "<span class='chip gris' id='cap-ind-3'>3 · Guardar</span>"
      + "</div>";

    h += "<div class='card' style='padding:16px;'>"
      + "<form id='form-captura' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<div class='cap-paso cap-paso-1 act'>"
      + "<div class='cap-paso-num'>1/3: ¿Qué evento desea registrar?</div>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;'>";
    tipos.forEach(function (t) {
      var act = t.id === _tipoCapturaActual ? "act" : "";
      h += "<button type='button' class='btn-punto " + act + "' data-cap-tipo='" + t.id + "' style='font-size:15px; padding:12px 16px;'>" + icon(t.ico, 16) + t.nom + "</button>";
    });
    h += "</div>"
      + "<button type='button' id='btn-cap-sig1' class='btn-guardar-manga'>Siguiente →</button>"
      + "</div>"
      + "<div class='cap-paso cap-paso-2'>"
      + "<div class='cap-paso-num'>2/3: Datos del evento</div>"
      + "<div id='cap-tag-chip' style='margin-bottom:8px;'></div>"
      + "<div id='captura-campos'></div>"
      + "<div style='display:flex; gap:8px; margin-top:12px;'>"
      + "<button type='button' id='btn-cap-atras2' class='tema-btn' style='flex:1; padding:12px; cursor:pointer;'>← Atrás</button>"
      + "<button type='button' id='btn-cap-sig2' class='btn-guardar-manga' style='flex:2;'>Siguiente →</button>"
      + "</div>"
      + "</div>"
      + "<div class='cap-paso cap-paso-3'>"
      + "<div class='cap-paso-num'>3/3: Revise y guarde</div>"
      + "<div id='cap-preview-resumen' class='aviso' style='font-size:13px; line-height:1.6;'></div>"
      + "<div style='margin-top:12px;'><button type='button' id='btn-cap-atras3' class='tema-btn' style='width:100%; padding:12px; cursor:pointer;'>← Atrás</button></div>"
      + "<div class='cap-guardar-sticky'><button type='submit' id='btn-guardar-captura' class='btn-guardar-manga'>" + icon("save", 15) + "Guardar Registro</button></div>"
      + "</div>"
      + "</form>"
      + "<div id='captura-feedback' role='status' aria-live='polite' style='margin-top:12px;'></div>"
      + "</div>";

    return h;
  }

  function camposHtmlCaptura(tipo) {
    var hoy = new Date().toISOString().slice(0, 10);
    var h = "<label>Fecha del evento: <input type='date' id='cap-fecha' value='" + hoy + "' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";

    if (tipo === "parto") {
      h += "<label>Tipo de evento: <select id='cap-tipo-evento' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='PARTO'>Parto sencillo (1 cría)</option><option value='GEMELAR'>Parto gemelar (2 crías)</option><option value='ABORTO'>Aborto</option><option value='REABSORCION'>Reabsorción embrionaria</option><option value='MOMIFICACION'>Momificación fetal</option><option value='MACERACION'>Maceración fetal</option><option value='MUERTE_FETAL'>Muerte fetal</option></select></label>"
        + "<label>Arete / Tag de la Madre (Vaca): <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div id='cap-parto-cria-wrap'>"
        + "<label id='cap-cria1-label'>Arete de la Cría (Nuevo): <input id='cap-cria-tag' placeholder='ej. 102 o NM_102' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Sexo de la Cría: <select id='cap-sexo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='HEMBRA'>Hembra</option><option value='MACHO'>Macho</option></select></label></div>"
        + "<div style='flex:1;'><label>Estado Cría: <select id='cap-estado-cria' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='VIVO'>Vivo / Normal</option><option value='MUERTO'>Nacido Muerto</option></select></label></div>"
        + "</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Peso al nacer (kg): <input type='number' step='0.5' id='cap-peso-nacer' placeholder='ej. 32' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<div id='cap-gemelo2-wrap' style='display:none; padding:10px; border:1px dashed var(--borde-fuerte); border-radius:8px;'>"
        + "<p class='aviso' style='margin:2px 0 8px;'>Segunda cría (gemelo/a):</p>"
        + "<label>Arete de la Cría 2: <input id='cap-cria2-tag' placeholder='ej. 103' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap; margin-top:8px;'>"
        + "<div style='flex:1;'><label>Sexo Cría 2: <select id='cap-sexo2' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='HEMBRA'>Hembra</option><option value='MACHO'>Macho</option></select></label></div>"
        + "<div style='flex:1;'><label>Estado Cría 2: <select id='cap-estado-cria2' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='VIVO'>Vivo / Normal</option><option value='MUERTO'>Nacido Muerto</option></select></label></div>"
        + "</div>"
        + "<div style='margin-top:8px;'><label>Peso al nacer Cría 2 (kg): <input type='number' step='0.5' id='cap-peso-nacer2' placeholder='ej. 28' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Potrero de la Cría (opcional): <input id='cap-pot-cria' placeholder='ej. Levante' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Potrero de la Madre (opcional): <input id='cap-pot-madre' placeholder='ej. Maternidad' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "</div>"
        + "<p id='cap-perdida-aviso' class='aviso' style='display:none; margin:2px 0;'>Se registra como un evento reproductivo de la vaca (sin cría), separado de un Parto normal.</p>"
        + "<label>Observaciones / Notas: <input id='cap-notas' placeholder='Parto distócico, ternero vigoroso, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "destete") {
      h += "<label>Arete de la Vaca (Madre): <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div id='cap-destete-cria-info' style='font-size:12.5px; color:var(--texto-suave); margin:-4px 0 2px 2px; min-height:16px;'></div>"
        + "<label>Arete de la Cría a Destetar: <input id='cap-cria-tag' placeholder='se completa solo al escribir la vaca' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Peso al destete (kg): <input type='number' step='0.5' id='cap-peso' placeholder='ej. 120' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Potrero nuevo de la Cría: <input id='cap-pot-cria' placeholder='ej. Levante' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<p class='aviso' style='margin:2px 0;'>Datos de la madre en este mismo momento (opcional, solo informativo -- el destete NO seca a la vaca; si dejó de ordeñarse use el botón <b>Secado</b> aparte):</p>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Peso de la Madre (kg): <input type='number' step='0.5' id='cap-peso-madre' placeholder='ej. 410' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Cond. Corporal Madre (1-5): <select id='cap-cc-madre' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0'>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0</option></select></label></div>"
        + "</div>"
        + "<label>Potrero nuevo de la Madre (opcional): <input id='cap-pot-madre' placeholder='ej. Vacas Secas' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Observaciones / Motivo: <input id='cap-notas' placeholder='Destete normal, adelantado por sequía, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "secado") {
      h += "<label>Arete / Tag de la Vaca: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Cond. Corporal (1-5): <select id='cap-cc' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0'>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0</option></select></label></div>"
        + "<div style='flex:1;'><label>Potrero nuevo (opcional): <input id='cap-pot-secado' placeholder='ej. Vacas Secas' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Motivo: <select id='cap-motivo-secado' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='Fin de lactancia'>Fin de lactancia (programado)</option><option value='Baja producción'>Baja producción</option><option value='Mastitis'>Mastitis / problema de ubre</option><option value='Preparación para el parto'>Preparación para el próximo parto</option><option value='Otro'>Otro</option></select></label>"
        + "<label>Observaciones: <input id='cap-notas' placeholder='ej. Se secó sola, sin problema' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<p class='aviso' style='margin:2px 0;'>Evento independiente del destete de la cría: registra que esta vaca dejó de ordeñarse de verdad.</p>";
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
      h += "<label style='display:flex; align-items:flex-start; gap:8px; background:var(--superficie); padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-weight:600; cursor:pointer;'>"
        + "<input type='checkbox' id='cap-trasl-masivo' style='width:auto; margin-top:3px;'>"
        + "<span>Mover TODOS los animales activos de este potrero<span style='display:block; font-weight:400; font-size:12px; color:var(--texto-suave); margin-top:2px;'>Sin escribir cada arete: elegí solo Potrero Origen y Potrero Destino.</span></span>"
        + "</label>"
        + "<div id='cap-trasl-tag-wrap'><label>Arete / Tag: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
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
    } else if (tipo === "destete") {
      titFoto = "Foto del Destete";
      hintFoto = "Foto de la cría destetada o de la madre en ese momento";
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
      + "<input type='file' id='cap-foto-input' accept='image/*' style='display:none;'>"
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

    if (tipo === "leche" || tipo === "gasto") {
      var tituloIa = tipo === "leche" ? "Digitalización Inteligente de Recibo (IA)" : "Digitalización Inteligente de Factura (IA)";
      var descIa = tipo === "leche"
        ? "Lee automáticamente cada renglón manuscrito, detecta fechas y suma los litros diarios."
        : "Lee automáticamente el monto, la fecha, el proveedor y sugiere la categoría del gasto o ingreso.";
      var btnTxtIa = tipo === "leche" ? "Leer Recibo con IA" : "Leer Factura con IA";
      h += "<div id='box-analizar-recibo-ia' style='display:none; margin-top:14px; padding:14px; border-radius:8px; background:var(--superficie); border:1.5px solid var(--verde-marca); box-shadow:0 2px 6px var(--sombra);'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>"
        + "<div>"
        + "<div style='font-weight:700; font-size:13.5px; color:var(--verde-marca); display:flex; align-items:center; gap:6px;'>"
        + icon("sparkles", 16) + tituloIa
        + "</div>"
        + "<small style='color:var(--texto-suave); font-size:11.5px; display:block; margin-top:2px;'>" + esc(descIa) + "</small>"
        + "</div>"
        + "<button type='button' id='btn-analizar-recibo-ia' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:700; font-size:12.5px; padding:7px 14px; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:6px;'>"
        + icon("sparkles", 14) + esc(btnTxtIa)
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
    var _facturaIaFotoRuta = null;

    // BLOQUE 4: stepper de captura en 3 pasos (1=tipo, 2=datos, 3=preview)
    // + defaults inteligentes (último potrero / tag desde ficha).
    var _capPaso = 1;
    var _capTipo = _tipoCapturaActual;
    var _capDatos = {};

    function mostrarPasoCap(n) {
      _capPaso = n;
      [1, 2, 3].forEach(function (i) {
        var paso = q(".cap-paso-" + i);
        if (paso) {
          if (i === n) paso.classList.add("act");
          else paso.classList.remove("act");
        }
        var ind = document.getElementById("cap-ind-" + i);
        if (ind) ind.className = "chip " + (i === n ? "verde" : (i < n ? "azul" : "gris"));
      });
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eScrollCap) { window.scrollTo(0, 0); }
    }

    // Defaults inteligentes: último potrero (localStorage), tag desde ficha
    // (?tag= en URL, /ficha/TAG en la ruta, o pendiente dejado por el FAB) y
    // fecha de hoy si quedó vacía (camposHtmlCaptura ya la prellena).
    function aplicarDefaultsCaptura() {
      var tagIni = window.__capTagPendiente || null;
      if (!tagIni) {
        try { tagIni = new URLSearchParams(window.location.search).get("tag"); } catch (eTag1) { tagIni = null; }
      }
      if (!tagIni) {
        try {
          var mFicha = window.location.pathname.match(/\/ficha\/([A-Za-z0-9_-]+)/i);
          if (mFicha) tagIni = mFicha[1];
        } catch (eTag2) { /* noop */ }
      }
      if (tagIni) {
        var fTagDef = document.getElementById("cap-tag");
        if (fTagDef && !fTagDef.value) fTagDef.value = tagIni;
        var chipTag = document.getElementById("cap-tag-chip");
        if (chipTag) chipTag.innerHTML = "<span class='chip azul'>📋 Animal: " + esc(tagIni) + "</span>";
        window.__capTagPendiente = null;
      }
      var ultPot = null;
      try { ultPot = localStorage.getItem("bitacora_ultimo_potrero"); } catch (ePot0) { ultPot = null; }
      if (ultPot) {
        var idsPot = ["cap-pot-dest", "cap-fin-potrero", "cap-pot-cria", "cap-pot-madre", "cap-pot-orig"];
        for (var ip = 0; ip < idsPot.length; ip++) {
          var inpPotDef = document.getElementById(idsPot[ip]);
          if (inpPotDef && !inpPotDef.value) {
            inpPotDef.value = ultPot;
            // Chip "último usado": un toque lo reaplica si el operario lo borró.
            (function (inpC, idC) {
              if (document.getElementById("cap-pot-hint-" + idC)) return;
              var hint = document.createElement("button");
              hint.type = "button";
              hint.id = "cap-pot-hint-" + idC;
              hint.className = "cap-potrero-hint";
              hint.textContent = "último usado: " + ultPot;
              hint.addEventListener("click", function () { inpC.value = ultPot; try { inpC.focus(); } catch (eHint) { /* noop */ } });
              if (inpC.parentNode) inpC.parentNode.appendChild(hint);
            })(inpPotDef, idsPot[ip]);
            break;
          }
        }
      }
      var fFechaDef = document.getElementById("cap-fecha");
      if (fFechaDef && !fFechaDef.value) fFechaDef.value = new Date().toISOString().slice(0, 10);
    }

    function recolectarCapDatos() {
      var d = {};
      qa("#captura-campos input, #captura-campos select").forEach(function (el) {
        if (!el.id || el.type === "file" || el.type === "checkbox") return;
        var v = (el.value || "").trim();
        if (v) d[el.id] = v;
      });
      _capDatos = d;
      return d;
    }

    function nombreTipoCap(id) {
      var noms = { parto: "Parto", pesaje: "Pesaje", tratamiento: "Tratamiento", traslado: "Traslado", destete: "Destete", celo: "Celo", servicio: "Servicio / IA", leche: "Leche", muerte: "Muerte / Descarte", gasto: "Ingreso / Gasto" };
      return noms[id] || id;
    }

    // Paso 3: resumen legible en texto plano antes de guardar.
    function resumenCapHtml() {
      var d = recolectarCapDatos();
      var tagR = d["cap-tag"] || d["cap-cria-tag"] || "—";
      var fechaR = d["cap-fecha"] || new Date().toISOString().slice(0, 10);
      var h = "<b>" + esc(nombreTipoCap(_capTipo)) + "</b> · Vaca/Animal: <b>" + esc(tagR) + "</b> · Fecha: <b>" + esc(fechaR) + "</b>";
      Object.keys(d).forEach(function (k) {
        if (k === "cap-tag" || k === "cap-fecha" || k === "cap-cria-tag") return;
        h += "<br>" + esc(k.replace(/^cap-/, "").replace(/-/g, " ")) + ": <b>" + esc(d[k]) + "</b>";
      });
      return h;
    }

    // El avance 2→3 valida los requeridos del paso 2 (respeta el modo
    // masivo de traslado, que quita el required del tag).
    function validarPaso2Cap() {
      var falt = null;
      qa("#captura-campos [required]").forEach(function (el) {
        if (!falt && !(el.value || "").trim() && el.offsetParent !== null) falt = el;
      });
      if (falt) {
        mostrarToast("Falta un campo requerido", "rojo");
        try { falt.focus(); } catch (eFoco) { /* noop */ }
        return false;
      }
      return true;
    }

    // Regenera los campos del paso 2 con TODA la lógica de binding
    // existente (foto, IA recibo, traslado masivo, destete, gemelar) más
    // los defaults inteligentes. No toca ninguna de esas funciones.
    function refrescarCamposCap() {
      if (!cCampos) return;
      cCampos.innerHTML = camposHtmlCaptura(_tipoCapturaActual);
      bindFotoCaptura();
      bindCamposFinanza();
      bindTrasladoMasivo();
      bindDesteteBusquedaCria();
      bindTipoEventoParto();
      aplicarDefaultsCaptura();
    }

    function wireStepperCap() {
      var bSig1 = document.getElementById("btn-cap-sig1");
      if (bSig1) bSig1.addEventListener("click", function () { mostrarPasoCap(2); });
      var bAtr2 = document.getElementById("btn-cap-atras2");
      if (bAtr2) bAtr2.addEventListener("click", function () { mostrarPasoCap(1); });
      var bSig2 = document.getElementById("btn-cap-sig2");
      if (bSig2) bSig2.addEventListener("click", function () {
        if (!validarPaso2Cap()) return;
        var prev = document.getElementById("cap-preview-resumen");
        if (prev) prev.innerHTML = resumenCapHtml();
        mostrarPasoCap(3);
      });
      var bAtr3 = document.getElementById("btn-cap-atras3");
      if (bAtr3) bAtr3.addEventListener("click", function () { mostrarPasoCap(2); });
    }

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

      var _esLecheOGasto = _tipoCapturaActual === "leche" || _tipoCapturaActual === "gasto";
      if (_fotoActual && _esLecheOGasto && boxIa) {
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
          _facturaIaFotoRuta = null;
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

              _facturaIaFotoRuta = null;
              if (boxIa && (_tipoCapturaActual === "leche" || _tipoCapturaActual === "gasto")) {
                boxIa.style.display = "block";
                var txtAyudaIa = _tipoCapturaActual === "leche"
                  ? "Presiona <b>Leer Recibo con IA</b> para digitalizar los días de ordeño automáticamente."
                  : "Presiona <b>Leer Factura con IA</b> para llenar categoría, monto y proveedor automáticamente.";
                if (estadoIa) {
                  estadoIa.innerHTML = "<div style='display:flex; align-items:center; gap:8px; padding:6px 10px; background:rgba(47,82,51,0.06); border-radius:6px;'>"
                    + "<span class='chip verde' style='font-size:11px;'>Foto cargada</span>"
                    + "<span style='color:var(--texto-suave); font-size:12px;'>" + txtAyudaIa + "</span>"
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

            var inpMonto = document.getElementById("ia-monto-pagado");
            var montoPagado = inpMonto && inpMonto.value ? parseFloat(inpMonto.value) : null;

            var payloadGuardar = {
              periodo: res.periodo || "",
              dias: listaDias,
              // La foto ya quedó guardada al analizarla (foto_ruta); solo se
              // manda foto_base64 como respaldo si por algo no vino foto_ruta.
              foto_ruta: res.foto_ruta || null,
              foto_base64: res.foto_ruta ? null : (_fotoActual ? _fotoActual.base64 : null),
              observaciones: (q("#cap-notas") && q("#cap-notas").value) || "",
              monto_pagado: (montoPagado && montoPagado > 0) ? montoPagado : null,
              acopiador: (res.acopiador && res.acopiador !== "No especificado") ? res.acopiador : null
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
                var msgIngreso = data.ingreso_id
                  ? "También se registró el <b>ingreso en Finanzas</b> (Venta de leche) con esa misma foto como respaldo."
                  : "La foto quedó archivada como respaldo en el historial.";
                estadoIa.innerHTML = "<div style='padding:12px; background:rgba(47,82,51,0.12); border-left:4px solid var(--verde-marca); border-radius:6px;'>"
                  + "<div style='font-size:14px; font-weight:bold; color:var(--verde-marca);'>🎉 ¡Quincena guardada con éxito!</div>"
                  + "<div style='margin-top:4px; font-size:12.5px;'>Se registraron <b>" + data.guardados + " días</b> con un total de <b>" + data.total_litros + " Litros</b>. " + msgIngreso + "</div>"
                  + "<div style='margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;'>"
                  + "<button type='button' id='btn-ia-ir-leche' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:bold; padding:6px 12px; font-size:12px; border:none; border-radius:4px; cursor:pointer;'>" + icon("milk", 13) + "Ver en Producción de Leche</button>"
                  + (data.ingreso_id ? "<button type='button' id='btn-ia-ir-finanzas' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:bold; padding:6px 12px; font-size:12px; border:none; border-radius:4px; cursor:pointer;'>" + icon("banknote", 13) + "Ver en Finanzas</button>" : "")
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
                var btnIrFinanzas = document.getElementById("btn-ia-ir-finanzas");
                if (btnIrFinanzas) {
                  btnIrFinanzas.addEventListener("click", function () {
                    irAVista("finanzas");
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
          + "</table></div>";

        var montoDetectado = res.valor_total_pagado != null ? res.valor_total_pagado : "";
        var precioLitroDetectado = res.precio_litro != null ? fmtMoneda(res.precio_litro) + "/L" : "";
        hTabla += "<div style='margin-top:12px; padding:10px; background:rgba(47,82,51,0.05); border:1px dashed var(--verde-marca); border-radius:8px;'>"
          + "<label style='font-size:12.5px; font-weight:700; display:flex; align-items:center; gap:6px;'>" + icon("banknote", 14) + "Monto Pagado en esta Quincena ($) <span style='font-weight:normal; font-size:11px; color:var(--texto-suave);'>(opcional -- si lo llenas, se registra el ingreso en Finanzas)</span></label>"
          + "<input type='number' step='1' min='0' id='ia-monto-pagado' value='" + esc(montoDetectado) + "' placeholder='ej. 10184000' style='width:100%; padding:8px; margin-top:6px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:bold;'>"
          + (precioLitroDetectado ? "<small style='color:var(--texto-suave); display:block; margin-top:4px;'>Precio detectado en el recibo: <b>" + esc(precioLitroDetectado) + "</b></small>" : "")
          + "</div>";

        hTabla += "<button type='button' id='btn-guardar-quincena-ia' class='tema-btn' style='margin-top:12px; width:100%; background:var(--verde-marca); color:#fff; font-weight:bold; font-size:13.5px; padding:10px; border:none; border-radius:6px; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px;'>"
          + icon("save", 15) + "Guardar Todos los Días en la Bitácora"
          + "</button>"
          + "</div>";

        if (previewIa) {
          previewIa.innerHTML = hTabla;
          previewIa.style.display = "block";
          bindTablaReciboIa(res);
        }
      }

      function rellenarCamposFactura(res) {
        _facturaIaFotoRuta = res.foto_ruta || null;
        if (estadoIa) estadoIa.innerHTML = "";
        var selCat = document.getElementById("cap-fin-categoria");
        var fConcepto = document.getElementById("cap-fin-concepto");
        var fMonto = document.getElementById("cap-fin-monto");
        var fContraparte = document.getElementById("cap-fin-contraparte");
        var fFecha = document.getElementById("cap-fecha");
        if (selCat && res.categoria_sugerida) selCat.value = res.categoria_sugerida;
        if (selCat) selCat.dispatchEvent(new Event("change"));
        if (fConcepto && res.concepto) fConcepto.value = res.concepto;
        if (fMonto && res.monto_total != null) fMonto.value = res.monto_total;
        if (fContraparte && res.proveedor) fContraparte.value = res.proveedor;
        if (fFecha && res.fecha) fFecha.value = res.fecha;
        if (previewIa) {
          previewIa.style.display = "block";
          previewIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--verde-marca);'>"
            + "✅ <b>Factura leída.</b> Revisa los campos de arriba (categoría, concepto, monto, proveedor) antes de guardar."
            + (res.observaciones ? "<br><small>" + esc(res.observaciones) + "</small>" : "")
            + "</div>";
        }
      }

      if (btnAnalizarIa) {
        btnAnalizarIa.addEventListener("click", function () {
          if (!_fotoActual || !_fotoActual.base64) {
            alert("Por favor toma o selecciona primero una foto del recibo o factura.");
            return;
          }
          var esGasto = _tipoCapturaActual === "gasto";
          btnAnalizarIa.disabled = true;
          btnAnalizarIa.innerHTML = "⏳ Analizando...";
          if (estadoIa) {
            var txtEsperaIa = esGasto
              ? "<b style='color:var(--verde-marca);'>Digitalizando factura con Visión Artificial...</b><br><small style='color:var(--texto-suave);'>Extrayendo monto, fecha, proveedor y categoría. Esto toma 5-10 segundos.</small>"
              : "<b style='color:var(--verde-marca);'>Digitalizando recibo con Visión Artificial...</b><br><small style='color:var(--texto-suave);'>Extrayendo días, fechas y litros de las anotaciones manuscritas. Esto toma 5-10 segundos.</small>";
            estadoIa.innerHTML = "<div style='display:flex; align-items:center; gap:10px; padding:10px; background:rgba(47,82,51,0.06); border-radius:6px;'>"
              + "<span style='font-size:18px;'>⏳</span><div>" + txtEsperaIa + "</div></div>";
          }
          if (previewIa) previewIa.style.display = "none";

          var fechaRef = (q("#cap-fecha") && q("#cap-fecha").value) || new Date().toISOString().slice(0, 10);
          var url = esGasto ? "/api/finanzas/analizar-factura" : "/api/leche/analizar-recibo";
          fetch(url, {
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
            btnAnalizarIa.innerHTML = icon("sparkles", 14) + (esGasto ? "Re-analizar Factura" : "Re-analizar Recibo");

            if (!res.ok) {
              if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-rojo-txt);'>❌ <b>Error:</b> " + esc(res.error || "No se pudo procesar la imagen.") + "</div>";
              return;
            }

            if (esGasto) {
              if (!res.es_factura) {
                var obsF = res.observaciones || "No se detectó una factura o recibo legible en la imagen.";
                if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-ambar);'>⚠️ <b>No parece una factura válida:</b><br><small style='color:var(--texto);'>" + esc(obsF) + "</small></div>";
                return;
              }
              rellenarCamposFactura(res);
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

    function bindTrasladoMasivo() {
      var chk = document.getElementById("cap-trasl-masivo");
      var tagWrap = document.getElementById("cap-trasl-tag-wrap");
      var fTag = document.getElementById("cap-tag");
      var fOrigen = document.getElementById("cap-pot-orig");
      if (!chk || !tagWrap) return;
      function toggle() {
        if (chk.checked) {
          tagWrap.style.display = "none";
          if (fTag) { fTag.required = false; fTag.value = ""; }
          if (fOrigen) fOrigen.required = true;
        } else {
          tagWrap.style.display = "";
          if (fTag) fTag.required = true;
          if (fOrigen) fOrigen.required = false;
        }
      }
      chk.addEventListener("change", toggle);
      toggle();
    }

    // Destete: el operario busca por el arete de la VACA (lo recuerda
    // mejor que el de una cría reciente); la cría activa sin destetar se
    // resuelve sola vía /api/cria-activa y queda editable por si hay
    // mellizos o el auto-match falla.
    function bindDesteteBusquedaCria() {
      if (_tipoCapturaActual !== "destete") return;
      var fVaca = document.getElementById("cap-tag");
      var fCria = document.getElementById("cap-cria-tag");
      var info = document.getElementById("cap-destete-cria-info");
      if (!fVaca || !fCria || !info) return;
      var timerBusqueda = null;
      function buscar() {
        var vaca = fVaca.value.trim();
        if (!vaca) { info.textContent = ""; return; }
        info.textContent = "Buscando cría de " + vaca + "...";
        fetch("/api/cria-activa?vaca=" + encodeURIComponent(vaca))
          .then(function (r) { return r.json(); })
          .then(function (res) {
            if (res && res.encontrada) {
              fCria.value = res.cria_tag;
              info.textContent = "✓ Cría encontrada: " + res.cria_tag;
            } else {
              info.textContent = "No se encontró cría activa sin destetar para esta vaca -- escriba el arete manualmente.";
            }
          })
          .catch(function () { info.textContent = ""; });
      }
      fVaca.addEventListener("blur", buscar);
      fVaca.addEventListener("input", function () {
        clearTimeout(timerBusqueda);
        timerBusqueda = setTimeout(buscar, 600);
      });
    }

    // Parto: alterna el bloque de "Cría 2" cuando el tipo elegido es
    // GEMELAR (parto múltiple), ver camposHtmlCaptura('parto').
    var TIPOS_EVENTO_SIN_CRIA = ["ABORTO", "REABSORCION", "MOMIFICACION", "MACERACION", "MUERTE_FETAL"];
    function bindTipoEventoParto() {
      var sel = document.getElementById("cap-tipo-evento");
      var wrapCria = document.getElementById("cap-parto-cria-wrap");
      var wrap2 = document.getElementById("cap-gemelo2-wrap");
      var labelCria1 = document.getElementById("cap-cria1-label");
      var avisoPerdida = document.getElementById("cap-perdida-aviso");
      if (!sel || !wrap2) return;
      function toggle() {
        var esGemelar = sel.value === "GEMELAR";
        var esPerdida = TIPOS_EVENTO_SIN_CRIA.indexOf(sel.value) !== -1;
        wrap2.style.display = esGemelar ? "block" : "none";
        if (wrapCria) wrapCria.style.display = esPerdida ? "none" : "block";
        if (avisoPerdida) avisoPerdida.style.display = esPerdida ? "block" : "none";
        if (labelCria1) labelCria1.firstChild.textContent = esGemelar ? "Arete de la Cría 1: " : "Arete de la Cría (Nuevo): ";
      }
      sel.addEventListener("change", toggle);
      toggle();
    }

    function ejecutarTrasladoMasivo(fecha) {
      var origen = (q("#cap-pot-orig") && q("#cap-pot-orig").value || "").trim();
      var destino = (q("#cap-pot-dest") && q("#cap-pot-dest").value || "").trim();
      var motivo = (q("#cap-motivo") && q("#cap-motivo").value) || null;
      var feed = document.getElementById("captura-feedback");
      if (!origen || !destino) {
        if (feed) feed.innerHTML = "<div class='chip rojo' style='font-size:14px; padding:8px 12px;'>❌ Elegí Potrero Origen y Potrero Destino.</div>";
        return;
      }
      if (!window.confirm("¿Mover TODOS los animales activos de \"" + origen + "\" a \"" + destino + "\"?")) return;
      if (feed) feed.innerHTML = "<div class='chip ambar' style='font-size:14px; padding:8px 12px;'>⏳ Moviendo animales...</div>";
      fetch("/api/traslado/masivo", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ potrero_origen: origen, potrero_destino: destino, motivo: motivo, fecha: fecha }),
      }).then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
        .then(function (res) {
          if (res.status >= 200 && res.status < 300 && res.body.ok) {
            enviarTelemetriaSilenciosa("captura_traslado_masivo");
            if (feed) {
              feed.innerHTML = "<div class='chip verde' style='font-size:14px; padding:8px 12px;'>✅ " + res.body.movidos
                + " animal(es) movidos de " + esc(res.body.potrero_origen) + " a " + esc(res.body.potrero_destino) + ".</div>";
            }
            var formEl = document.getElementById("form-captura");
            if (formEl) formEl.reset();
            refrescarCamposCap();
            actualizarBadges();
          } else if (feed) {
            feed.innerHTML = "<div class='chip rojo' style='font-size:14px; padding:8px 12px;'>❌ " + esc((res.body && res.body.error) || "No se pudo mover el lote.") + "</div>";
          }
        }).catch(function (err) {
          if (feed) feed.innerHTML = "<div class='chip rojo' style='font-size:14px; padding:8px 12px;'>❌ " + esc(err && err.message || err) + "</div>";
        });
    }

    refrescarCamposCap();
    wireStepperCap();
    mostrarPasoCap(1);

    qa("button[data-cap-tipo]").forEach(function (b) {
      b.addEventListener("click", function () {
        qa("button[data-cap-tipo]").forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        _tipoCapturaActual = b.getAttribute("data-cap-tipo");
        _capTipo = _tipoCapturaActual;
        _fotoActual = null;
        // Al cambiar el tipo en el paso 1 se regeneran los campos del paso
        // 2 en segundo plano (el operario sigue en el paso 1).
        refrescarCamposCap();
      });
    });

    var form = document.getElementById("form-captura");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var fecha = (q("#cap-fecha") && q("#cap-fecha").value) || new Date().toISOString().slice(0, 10);

        var chkTrasladoMasivo = document.getElementById("cap-trasl-masivo");
        if (_tipoCapturaActual === "traslado" && chkTrasladoMasivo && chkTrasladoMasivo.checked) {
          ejecutarTrasladoMasivo(fecha);
          return;
        }

        var payload = {};
        // Aborto/Pérdida (y sus subtipos) usan el mismo formulario de Parto,
        // con tipo_evento eligiendo el subtipo -- un solo tipo de evento/tabla
        // en el backend, distinguido por payload.tipo_evento.
        var tipoEnvio = _tipoCapturaActual;

        if (_tipoCapturaActual === "parto") {
          payload.tipo_evento = (q("#cap-tipo-evento") && q("#cap-tipo-evento").value) || "PARTO";
          var esPerdidaEnvio = TIPOS_EVENTO_SIN_CRIA.indexOf(payload.tipo_evento) !== -1;
          payload.vaca_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.id_cria_tag = esPerdidaEnvio ? null : ((q("#cap-cria-tag") && q("#cap-cria-tag").value || "").trim() || null);
          payload.sexo_cria = (q("#cap-sexo") && q("#cap-sexo").value) || "HEMBRA";
          payload.estado_cria = esPerdidaEnvio ? "MUERTO" : ((q("#cap-estado-cria") && q("#cap-estado-cria").value) || "VIVO");
          payload.peso_nacimiento = parseFloat(q("#cap-peso-nacer") && q("#cap-peso-nacer").value) || null;
          payload.potrero_cria = (q("#cap-pot-cria") && q("#cap-pot-cria").value || "").trim() || null;
          payload.potrero_madre = (q("#cap-pot-madre") && q("#cap-pot-madre").value || "").trim() || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || "";
          if (payload.tipo_evento === "GEMELAR") {
            payload.gemelo = {
              id_cria_tag: (q("#cap-cria2-tag") && q("#cap-cria2-tag").value || "").trim() || null,
              sexo_cria: (q("#cap-sexo2") && q("#cap-sexo2").value) || "HEMBRA",
              estado_cria: (q("#cap-estado-cria2") && q("#cap-estado-cria2").value) || "VIVO",
              peso_nacimiento: parseFloat(q("#cap-peso-nacer2") && q("#cap-peso-nacer2").value) || null,
            };
          }
        } else if (_tipoCapturaActual === "destete") {
          payload.cria_tag = (q("#cap-cria-tag") && q("#cap-cria-tag").value || "").trim();
          payload.peso_kg = parseFloat(q("#cap-peso") && q("#cap-peso").value) || null;
          payload.potrero_cria = (q("#cap-pot-cria") && q("#cap-pot-cria").value || "").trim() || null;
          payload.peso_madre_kg = parseFloat(q("#cap-peso-madre") && q("#cap-peso-madre").value) || null;
          payload.cond_corporal_madre = parseFloat(q("#cap-cc-madre") && q("#cap-cc-madre").value) || null;
          payload.potrero_madre = (q("#cap-pot-madre") && q("#cap-pot-madre").value || "").trim() || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || "";
        } else if (_tipoCapturaActual === "secado") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.cond_corporal = parseFloat(q("#cap-cc") && q("#cap-cc").value) || null;
          payload.potrero_destino = (q("#cap-pot-secado") && q("#cap-pot-secado").value || "").trim() || null;
          payload.motivo = (q("#cap-motivo-secado") && q("#cap-motivo-secado").value) || null;
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

        // Adjuntar foto opcional. Si ya se analizó con IA (leche/gasto), la
        // foto quedó guardada en ese momento -- se enlaza por ruta en vez de
        // volver a subir los mismos bytes.
        if (_tipoCapturaActual === "gasto" && _facturaIaFotoRuta) {
          payload.foto_ruta = _facturaIaFotoRuta;
        } else if (_fotoActual && _fotoActual.base64) {
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
          mostrarToast(online ? "Guardado ✓" : "Guardado offline, se enviará al volver la señal", online ? "verde" : "ambar");
          vibrarConfirmacion();
          // BLOQUE 4: persistir defaults inteligentes (potrero + tag).
          try {
            var potsG = ["cap-pot-dest", "cap-fin-potrero", "cap-pot-cria", "cap-pot-madre", "cap-pot-orig"];
            for (var ig = 0; ig < potsG.length; ig++) {
              var inpG = q("#" + potsG[ig]);
              if (inpG && (inpG.value || "").trim()) { localStorage.setItem("bitacora_ultimo_potrero", inpG.value.trim()); break; }
            }
            var tagG = (q("#cap-tag") && q("#cap-tag").value || "").trim();
            if (tagG) localStorage.setItem("bitacora_ultimo_tag", tagG);
          } catch (eGuard) { /* almacenamiento no disponible */ }
          _fotoActual = null;
          form.reset();
          refrescarCamposCap();
          actualizarBadges();
          // Tras guardar se vuelve al paso 1 para el siguiente registro.
          mostrarPasoCap(1);
        }

        if (navigator.onLine === false) {
          encolarOffline(tipoEnvio, payload, fecha).then(function () {
            mostrarExito(false);
          });
          return;
        }

        fetch("/api/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ eventos: [{ tipo: tipoEnvio, payload: payload, fecha: fecha }] })
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok && res.procesados > 0) mostrarExito(true);
            else {
              encolarOffline(tipoEnvio, payload, fecha).then(function () { mostrarExito(false); });
            }
          }).catch(function () {
            encolarOffline(tipoEnvio, payload, fecha).then(function () { mostrarExito(false); });
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
      + "<small style='color:var(--texto-suave);'>Eventos de manejo y campo con foto de evidencia opcional</small>"
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
      + "<li>El motor de transcripción e inteligencia artificial estructurará el registro automáticamente para que solo confirmes con un toque.</li>"
      + "</ol>"
      + "</div></div>";

    // Tarjeta 6: Asistente IA & Preguntas Frecuentes
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("chat", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>🤖 Asistente Inteligente IA & Chat</h4>"
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

  /* ---------- Vista Mapa Satelital Interactivo & Operarios ---------- */
  var _mapaInstancia = null;
  var _mapaCapaPotreros = null;
  var _mapaCapaUsuarios = null;
  var _mapaCapaRastros = null;
  var _mapaModoActual = "vigor"; // 'vigor', 'voisin', 'satelite'
  var _mapaVerOperarios = true;
  var _mapaMarkerSelf = null;
  var _mapaCircleSelf = null;
  var _mapaCapaSelf = null;
  var _mapaWatchGpsId = null;
  var _mapaTimerRefresh = null;

  function renderMapa(d) {
    var totalPot = (d && d.finca && d.finca.total_potreros) || (d && d.potreros_geojson && d.potreros_geojson.features ? d.potreros_geojson.features.length : 0);
    var uActivos = (d && d.usuarios_activos) ? d.usuarios_activos.filter(function (u) { return u.dist_finca_km == null || u.dist_finca_km <= 35.0; }) : [];

    var h = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>"
      + icon("grid", 20) + "Mapa Satelital de Potreros &amp; Operarios"
      + "</h3>"
      + "<span class='meta' style='font-size:12px; font-weight:600;'>🌾 " + totalPot + " potreros · 🤠 " + uActivos.length + " operarios con señal</span>"
      + "</div>";

    // Barra de herramientas del Mapa
    h += "<div class='mapa-toolbar'>"
      + "<div class='mapa-grupos'>"
      + "<span style='font-size:12px; font-weight:700; color:var(--texto-suave); margin-right:4px;'>Capa:</span>"
      + "<button type='button' class='mapa-btn" + (_mapaModoActual === "vigor" ? " act" : "") + "' data-modo-mapa='vigor'>🌿 Vigor NDVI/SAR</button>"
      + "<button type='button' class='mapa-btn" + (_mapaModoActual === "voisin" ? " act" : "") + "' data-modo-mapa='voisin'>🐄 Ocupación &amp; Voisin</button>"
      + "<button type='button' class='mapa-btn" + (_mapaModoActual === "satelite" ? " act" : "") + "' data-modo-mapa='satelite'>🛰️ Satelital</button>"
      + "</div>"
      + "<div class='mapa-grupos'>"
      + "<button type='button' class='mapa-btn" + (_mapaVerOperarios ? " act" : "") + "' id='btn-toggle-operarios'>🤠 Operarios (" + uActivos.length + ")</button>"
      + "<button type='button' class='mapa-btn' id='btn-mi-ubicacion-mapa'>📍 Mi GPS</button>"
      + "<button type='button' class='mapa-btn' id='btn-centrar-finca'>🌾 Toda la Finca</button>"
      + "<button type='button' class='mapa-btn' id='btn-refrescar-mapa' title='Actualizar posiciones y datos'>🔄</button>"
      + "</div>"
      + "</div>";

    // Contenedor del Mapa
    h += "<div class='mapa-wrap'>"
      + "<div id='mapa-finca'></div>"
      + "</div>";

    // Barra de Leyenda Dinámica
    h += "<div id='mapa-leyenda-dinamica' class='mapa-leyenda'>";
    if (_mapaModoActual === "voisin") {
      h += "<span style='font-weight:700; margin-right:6px;'>Leyenda Voisin:</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#2e7d32;'></span> Ocupado (≤3d)</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#c62828;'></span> Alerta (>3d Sobrepastoreo)</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#1565c0;'></span> Reposado (≥30d Listo)</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#00838f;'></span> En descanso (20-29d)</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#ef6c00;'></span> Recién salido (&lt;20d)</span>";
    } else if (_mapaModoActual === "vigor") {
      h += "<span style='font-weight:700; margin-right:6px;'>Vigor Forrajero:</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#1b5e20;'></span> Excelente / Denso</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#388e3c;'></span> Bueno / Creciendo</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#fbc02d;'></span> Medio</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#f57c00;'></span> Bajo / Reposo</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#d32f2f;'></span> Crítico</span>";
    } else {
      h += "<span style='font-weight:700; margin-right:6px;'>Capa:</span> Vista satelital óptica de alta resolución (Esri World Imagery) con linderos de potrero.";
    }
    h += "</div>";

    // Panel de Operarios en Campo
    h += "<div class='card' style='padding:14px; margin-top:14px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("users", 16) + "Operarios &amp; Personal de Campo (" + uActivos.length + ")</h4>"
      + "<span style='font-size:12px; color:var(--texto-suave);'>Posiciones satelitales en tiempo real</span>"
      + "</div>";

    if (!uActivos.length) {
      h += vacio("No hay posiciones GPS registradas recientemente. Al abrir la app en potrero, los vaqueros y administradores transmiten su ubicación.");
    } else {
      h += "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:10px;'>";
      uActivos.forEach(function (u, uIdx) {
        var rolClase = (u.rol === "OWNER") ? "rojo" : ((u.rol === "ADMIN") ? "ambar" : "verde");
        var estadoTxt = u.en_linea
          ? "<span class='chip verde' style='font-size:11px;'>🟢 En línea (" + (u.minutos_hace != null ? "hace " + u.minutos_hace + "m" : "ahora") + ")</span>"
          : "<span class='chip gris' style='font-size:11px;'>⚪ " + esc(u.fecha) + " " + esc(u.hora ? u.hora.slice(0, 5) : "") + "</span>";

        h += "<div class='card' style='padding:10px; margin:0; border:1px solid var(--borde); display:flex; flex-direction:column; justify-content:space-between;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>"
          + "<div><b>" + esc(u.nombre) + "</b> <span class='chip " + rolClase + "' style='font-size:10.5px;'>" + esc(u.rol) + "</span></div>"
          + estadoTxt
          + "</div>"
          + "<div style='font-size:12.5px; color:var(--texto-suave); margin-bottom:8px;'>"
          + "📍 Potrero: <b style='color:var(--texto);'>" + esc(u.potrero_actual) + "</b>"
          + (u.precision_m ? " <small>(±" + Math.round(u.precision_m) + "m)</small>" : "")
          + "</div>"
          + "<div style='display:flex; gap:6px;'>"
          + "<button type='button' class='tema-btn' data-ir-usuario='" + uIdx + "' style='font-size:11.5px; padding:4px 10px; flex:1;'>🎯 Enfocar</button>"
          + (u.rastro_hoy && u.rastro_hoy.length ? "<button type='button' class='tema-btn' data-rastro-usuario='" + uIdx + "' style='font-size:11.5px; padding:4px 10px; flex:1;'>👣 Ver rastro (" + u.rastro_hoy.length + ")</button>" : "")
          + "</div>"
          + "</div>";
      });
      h += "</div>";
    }
    h += "</div>";

    // Sección de Auditoría de Rutas, Desplazamientos y Rondas GPS (Unificada)
    var rutas = (d && d.rutas) || [];
    var rondas = (d && d.rondas) || [];
    var fFecha = (d && d.fecha_filtro) || _fechaFiltroRutas || new Date().toISOString().slice(0, 10);

    h += "<div class='card' style='padding:14px; margin-top:14px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;'>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("pin", 16) + "Auditoría de Rutas, Desplazamientos &amp; Telemetría</h4>"
      + "<div style='display:flex; flex-wrap:wrap; gap:8px; align-items:center;'>"
      + "<label style='font-size:12px; font-weight:600; color:var(--texto-suave); display:flex; align-items:center; gap:6px;'>"
      + icon("calendar", 14) + "Fecha: "
      + "<input type='date' id='filtro-fecha-rutas' value='" + esc(fFecha) + "' style='padding:4px 8px; border-radius:6px; border:1px solid var(--borde); font-size:12px;'>"
      + "</label>"
      + "<button type='button' id='btn-refrescar-rutas' class='tema-btn' style='font-size:12px; padding:4px 10px;'>" + icon("search", 13) + "Consultar Rutas</button>"
      + (rutas.length ? "<button type='button' id='btn-exportar-rutas-csv' class='tema-btn' style='font-size:12px; padding:4px 10px;'>" + icon("download", 13) + "Exportar CSV</button>" : "")
      + "</div>"
      + "</div>";

    if (!rutas.length) {
      h += vacio("No hay desplazamientos registrados para la fecha " + fechaCorta(fFecha) + ". Los puntos GPS se capturan en segundo plano al interactuar con la app en campo.");
    } else {
      rutas.forEach(function (r, rIdx) {
        var rolBadge = r.rol === "OWNER" ? "rojo" : (r.rol === "ADMIN" ? "ambar" : "verde");
        h += "<div class='card-operario-ruta' style='margin-bottom:10px; border:1px solid var(--borde); padding:10px; border-radius:8px;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
          + "<div><b style='font-size:15px;'>" + esc(r.usuario_nombre) + "</b> <span class='chip " + rolBadge + "' style='font-size:10.5px;'>" + esc(r.rol) + "</span></div>"
          + "<div style='display:flex; align-items:center; gap:8px;'>"
          + "<span style='font-size:12px; color:var(--texto-suave);'>🕒 " + esc(r.hora_inicio || "—") + " a " + esc(r.hora_fin || "—") + " · 📍 <b>" + r.total_puntos + " puntos</b></span>"
          + (r.puntos && r.puntos.length ? "<button type='button' class='tema-btn' data-trazar-ruta-mapa='" + rIdx + "' style='font-size:11.5px; padding:3px 9px;'>🗺️ Ver rastro en mapa</button>" : "")
          + "</div>"
          + "</div>";

        // Timeline de potreros
        h += "<div class='timeline-rutas' style='margin-bottom:6px;'>";
        if (!r.secuencia_potreros || !r.secuencia_potreros.length) {
          h += "<span style='font-size:12px; color:var(--texto-suave);'>Sin visitas a potreros registradas</span>";
        } else {
          r.secuencia_potreros.forEach(function (s, sIdx) {
            if (sIdx > 0) h += "<span class='chip-flecha'>➔</span>";
            h += "<span class='chip-ruta'>" + icon("pin", 12) + "<b>" + esc(s.hora) + "</b> 🌾 " + esc(s.potrero) + "</span>";
          });
        }
        h += "</div>";

        // Desglose de coordenadas colapsable
        var tablaId = "tabla-pts-" + rIdx;
        h += "<details style='font-size:12px; margin-top:6px;'>"
          + "<summary style='cursor:pointer; font-weight:600; color:var(--verde-marca); padding:3px 0;'>🔍 Ver desglose de coordenadas (" + (r.puntos ? r.puntos.length : 0) + " registros)</summary>"
          + "<div class='tabla-scroll' style='margin-top:6px;'>"
          + "<table id='" + tablaId + "'><tr><th>Hora</th><th>Potrero</th><th>Latitud</th><th>Longitud</th><th>Precisión</th><th>Evento</th><th>Google Maps</th></tr>";
        (r.puntos || []).forEach(function (pt) {
          var mapsUrl = "https://maps.google.com/?q=" + pt.lat + "," + pt.lon;
          h += "<tr>"
            + "<td><b>" + esc(pt.hora) + "</b></td>"
            + "<td><b>" + esc(pt.potrero_nombre || "Área de la Finca") + "</b></td>"
            + "<td>" + Number(pt.lat).toFixed(6) + "</td>"
            + "<td>" + Number(pt.lon).toFixed(6) + "</td>"
            + "<td>±" + (pt.precision_m ? Math.round(pt.precision_m) + " m" : "—") + "</td>"
            + "<td><span class='chip gris' style='font-size:10.5px;'>" + esc(pt.evento_origen || "auto") + "</span></td>"
            + "<td><a href='" + esc(mapsUrl) + "' target='_blank' rel='noopener' class='chip azul' style='font-size:10.5px; text-decoration:none;'>🗺️ Maps</a></td>"
            + "</tr>";
        });
        h += "</table></div></details></div>";
      });
    }

    // Rondas manuales de campo
    if (rondas && rondas.length) {
      h += "<div style='margin-top:16px; border-top:1px solid var(--borde); padding-top:12px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>"
        + "<h5 style='margin:0;'>" + icon("calendar", 14) + "Puntos de Ronda Manuales (" + rondas.length + ")</h5>"
        + "<button type='button' id='btn-exportar-rondas-csv' class='tema-btn' style='font-size:11px; padding:3px 8px;'>Exportar Rondas CSV</button>"
        + "</div>"
        + "<div class='tabla-scroll'><table id='tabla-rondas'><tr><th>Hora</th><th>Potrero</th><th>Punto</th><th>Usuario</th><th>Notas</th></tr>";
      rondas.forEach(function (ro) {
        h += "<tr><td><b>" + esc(ro.hora || fechaCorta(ro.fecha)) + "</b></td>"
          + "<td><b>" + esc(ro.potrero_nombre || "—") + "</b></td>"
          + "<td><span class='chip verde'>" + esc(ro.punto_control || "recorrido") + "</span></td>"
          + "<td>" + esc(ro.usuario_nombre || "—") + "</td>"
          + "<td>" + esc(ro.notas || "—") + "</td></tr>";
      });
      h += "</table></div></div>";
    }

    h += "</div>";

    return h;
  }

  var _leafletCargando = false;
  var _leafletCallbacksEnEspera = [];

  // Leaflet (CSS+JS, ~150KB) ya no va fijo en el <head>/</body> -- se pedía
  // en TODAS las páginas aunque el 90% de las visitas nunca abren Mapa &
  // GPS. Se inyecta bajo demanda solo la primera vez que se entra a ese
  // módulo, y queda cacheado por el Service Worker para las siguientes.
  function cargarLeafletSiFalta(callback) {
    if (typeof L !== "undefined") { callback(); return; }
    _leafletCallbacksEnEspera.push(callback);
    if (_leafletCargando) return;
    _leafletCargando = true;

    if (!document.getElementById("leaflet-css")) {
      var link = document.createElement("link");
      link.id = "leaflet-css";
      link.rel = "stylesheet";
      link.href = "/static/leaflet/leaflet.css";
      document.head.appendChild(link);
    }
    var script = document.createElement("script");
    script.src = "/static/leaflet/leaflet.js";
    script.onload = function () {
      var pendientes = _leafletCallbacksEnEspera;
      _leafletCallbacksEnEspera = [];
      _leafletCargando = false;
      pendientes.forEach(function (cb) { cb(); });
    };
    script.onerror = function () {
      _leafletCargando = false;
      var mapEl = document.getElementById("mapa-finca");
      if (mapEl) mapEl.innerHTML = "<p class='aviso' style='padding:30px; text-align:center;'>⚠️ No se pudo cargar el componente de mapas. Verifica tu conexión e intenta de nuevo.</p>";
    };
    document.body.appendChild(script);
  }

  function bindMapa(d) {
    if (typeof L === "undefined") {
      var mapEl = document.getElementById("mapa-finca");
      if (mapEl) mapEl.innerHTML = "<p class='aviso' style='padding:30px; text-align:center;'>⚠️ Cargando componente de mapas Leaflet… Si no carga, verifica tu conexión.</p>";
      return;
    }

    var mapEl = document.getElementById("mapa-finca");
    if (!mapEl) return;

    if (_mapaInstancia) {
      try { _mapaInstancia.remove(); } catch (e) {}
      _mapaInstancia = null;
    }
    if (_mapaTimerRefresh) {
      clearInterval(_mapaTimerRefresh);
      _mapaTimerRefresh = null;
    }

    var centro = (d.finca && d.finca.centroide) || [3.402, -74.088];
    var map = L.map("mapa-finca", {
      zoomControl: true,
      attributionControl: true
    }).setView(centro, 14);
    _mapaInstancia = map;

    // Capa base satelital Esri
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 19,
      attribution: "Tiles &copy; Esri &mdash; Ganader&iacute;a JA"
    }).addTo(map);

    // Ajustar zoom a los límites de la finca
    if (d.finca && d.finca.bbox) {
      try {
        map.fitBounds(d.finca.bbox, { padding: [25, 25] });
      } catch (e) {}
    }

    _mapaCapaPotreros = L.layerGroup().addTo(map);
    _mapaCapaUsuarios = L.layerGroup().addTo(map);
    _mapaCapaRastros = L.layerGroup().addTo(map);
    _mapaCapaSelf = L.layerGroup().addTo(map);

    setTimeout(function () { if (_mapaInstancia) _mapaInstancia.invalidateSize(); }, 150);
    setTimeout(function () { if (_mapaInstancia) _mapaInstancia.invalidateSize(); }, 500);

    function colorParaPotrero(props) {
      if (_mapaModoActual === "satelite") return { fill: true, fillColor: "#2ecc71", color: "#f1c40f", weight: 2.2, fillOpacity: 0.12 };
      if (_mapaModoActual === "voisin") return { fill: true, fillColor: props.color_voisin || "#2e7d32", color: "#ffffff", weight: 1.5, fillOpacity: 0.5 };
      return { fill: true, fillColor: props.color_ndvi || "#2e7d32", color: "#ffffff", weight: 1.5, fillOpacity: 0.55 };
    }

    function pintarPotreros() {
      _mapaCapaPotreros.clearLayers();
      if (!d.potreros_geojson || !d.potreros_geojson.features) return;

      var layer = L.geoJSON(d.potreros_geojson, {
        style: function (feat) {
          var est = colorParaPotrero(feat.properties);
          return {
            fill: est.fill,
            fillColor: est.fillColor,
            fillOpacity: est.fillOpacity,
            color: est.color,
            weight: est.weight
          };
        },
        onEachFeature: function (feat, lyr) {
          var p = feat.properties;
          var nAnim = p.animales_count || 0;
          var labelTxt = p.nombre + (nAnim > 0 ? " (" + nAnim + " anim)" : "");

          lyr.bindTooltip(labelTxt, {
            permanent: _mapaModoActual === "satelite",
            direction: "center",
            className: "mapa-tooltip-potrero"
          });

          // Popup al tocar potrero
          var popHtml = "<div style='font-family:sans-serif; min-width:200px; padding:4px;'>"
            + "<h4 style='margin:0 0 6px 0; color:#1b4d3e; font-size:15px; border-bottom:1px solid #ddd; padding-bottom:4px;'>" + esc(p.nombre) + "</h4>"
            + "<div style='font-size:12px; line-height:1.5;'>"
            + "📐 <b>Área:</b> " + p.area_has + " ha<br>"
            + "🐄 <b>Ocupación:</b> " + (nAnim > 0 ? ("<b>" + nAnim + " cabezas</b>") : "Desocupado") + "<br>"
            + "⏱️ <b>Voisin:</b> " + esc(p.estado_voisin || "—") + "<br>"
            + "🌿 <b>Vigor NDVI:</b> " + (p.ndvi_valor != null ? ("<b>" + p.ndvi_valor.toFixed(3) + "</b> (" + esc(p.categoria_ndvi) + ")") : "—") + "<br>"
            + (p.biomasa_kg_ha ? ("🌾 <b>Biomasa:</b> " + Math.round(p.biomasa_kg_ha) + " kg MS/ha<br>") : "")
            + "</div>";

          if (p.animales_tags && p.animales_tags.length) {
            popHtml += "<div style='margin-top:6px; font-size:11px; color:#666;'>Tags: " + esc(p.animales_tags.join(", ")) + (nAnim > p.animales_tags.length ? "..." : "") + "</div>";
          }
          popHtml += "</div>";
          lyr.bindPopup(popHtml);

          lyr.on("mouseover", function () { lyr.setStyle({ weight: 3.5, color: "#ffffff" }); });
          lyr.on("mouseout", function () {
            var orig = colorParaPotrero(p);
            lyr.setStyle({ weight: orig.weight, color: orig.color, fillColor: orig.fillColor, fillOpacity: orig.fillOpacity });
          });
        }
      });
      _mapaCapaPotreros.addLayer(layer);
    }

    function pintarUsuarios() {
      _mapaCapaUsuarios.clearLayers();
      if (!_mapaVerOperarios || !d.usuarios_activos) return;

      d.usuarios_activos.forEach(function (u, idx) {
        if (u.dist_finca_km != null && u.dist_finca_km > 35.0) return;
        if (!u.lat || !u.lon) return;

        var rolClase = (u.rol === "OWNER") ? "owner" : ((u.rol === "ADMIN") ? "admin" : "trabajador");
        var pulseClase = u.en_linea ? "" : " offline";
        var htmlPin = "<div class='user-marker-pin' data-uidx='" + idx + "'>"
          + "<div class='user-marker-badge " + rolClase + "'>🤠 " + esc(u.nombre) + "</div>"
          + "<div class='user-pulse-dot" + pulseClase + "'></div>"
          + "</div>";

        var iconCustom = L.divIcon({
          className: "user-div-icon",
          html: htmlPin,
          iconSize: [120, 42],
          iconAnchor: [60, 42]
        });

        var m = L.marker([u.lat, u.lon], { icon: iconCustom });
        var popU = "<div style='font-family:sans-serif; min-width:180px; padding:4px;'>"
          + "<b style='font-size:14px;'>" + esc(u.nombre) + "</b> <span style='font-size:11px;'>(" + esc(u.rol) + ")</span><br>"
          + "<div style='font-size:12px; margin-top:4px; line-height:1.4;'>"
          + "📍 Potrero: <b>" + esc(u.potrero_actual) + "</b><br>"
          + "🕒 Hora: <b>" + esc(u.hora || u.fecha) + "</b>" + (u.minutos_hace != null ? " (hace " + u.minutos_hace + "m)" : "") + "<br>"
          + (u.precision_m ? "📡 Precisión: ±" + Math.round(u.precision_m) + "m<br>" : "")
          + "</div></div>";
        m.bindPopup(popU);
        _mapaCapaUsuarios.addLayer(m);
      });
    }

    function actualizarPosicionPropia(myLat, myLon, myAcc, centrarSiCerca) {
      if (!_mapaInstancia || !_mapaCapaSelf) return;
      _mapaCapaSelf.clearLayers();

      if (myAcc && myAcc > 5) {
        _mapaCircleSelf = L.circle([myLat, myLon], {
          radius: myAcc,
          color: "#0288d1",
          fillColor: "#0288d1",
          fillOpacity: 0.12,
          weight: 1.2
        }).addTo(_mapaCapaSelf);
      }

      var iconSelf = L.divIcon({
        className: "self-gps-icon",
        html: "<div class='self-pulse-dot' title='Mi ubicación GPS'></div>",
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      });

      _mapaMarkerSelf = L.marker([myLat, myLon], { icon: iconSelf }).addTo(_mapaCapaSelf);

      var cFinca = (d.finca && d.finca.centroide) || [3.402, -74.088];
      var distFincaKm = Math.sqrt(Math.pow((myLat - cFinca[0]) * 111.0, 2) + Math.pow((myLon - cFinca[1]) * 111.0, 2));
      var textoUbic = distFincaKm <= 3.5
        ? "<b>📍 Estás en la Finca</b>"
        : ("<b>📍 Tu ubicación actual</b><br><small style='color:#666;'>A " + distFincaKm.toFixed(1) + " km de la finca</small>");

      _mapaMarkerSelf.bindPopup(
        "<div style='font-family:sans-serif; min-width:160px; padding:4px;'>"
        + textoUbic + "<br>"
        + "<span style='font-size:11.5px;'>Precisión: ±" + Math.round(myAcc) + "m</span>"
        + "</div>"
      );

      if (centrarSiCerca && distFincaKm <= 5.0) {
        _mapaInstancia.setView([myLat, myLon], 16);
      }

      fetch("/api/telemetria/ping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: myLat, lon: myLon, accuracy: myAcc, evento: "mapa_activo" })
      }).catch(function () {});
    }

    function iniciarRastreoGps(centrarSiCerca) {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(function (pos) {
        actualizarPosicionPropia(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy || 0, centrarSiCerca);
      }, function (err) {
        console.warn("GPS no disponible:", err && err.message);
      }, { enableHighAccuracy: true, timeout: 10000 });

      if (!_mapaWatchGpsId) {
        _mapaWatchGpsId = navigator.geolocation.watchPosition(function (pos) {
          actualizarPosicionPropia(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy || 0, false);
        }, function () {}, { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 });
      }
    }

    pintarPotreros();
    pintarUsuarios();
    iniciarRastreoGps(true);

    // Botones de selector de modo
    qa(".mapa-btn[data-modo-mapa]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        qa(".mapa-btn[data-modo-mapa]").forEach(function (b) { b.classList.remove("act"); });
        btn.classList.add("act");
        _mapaModoActual = btn.getAttribute("data-modo-mapa");
        pintarPotreros();
        var leyEl = document.getElementById("mapa-leyenda-dinamica");
        if (leyEl) {
          if (_mapaModoActual === "voisin") {
            leyEl.innerHTML = "<span style='font-weight:700; margin-right:6px;'>Leyenda Voisin:</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#2e7d32;'></span> Ocupado (≤3d)</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#c62828;'></span> Alerta (>3d Sobrepastoreo)</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#1565c0;'></span> Reposado (≥30d Listo)</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#00838f;'></span> En descanso (20-29d)</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#ef6c00;'></span> Recién salido (&lt;20d)</span>";
          } else if (_mapaModoActual === "vigor") {
            leyEl.innerHTML = "<span style='font-weight:700; margin-right:6px;'>Vigor Forrajero:</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#1b5e20;'></span> Excelente / Denso</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#388e3c;'></span> Bueno / Creciendo</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#fbc02d;'></span> Medio</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#f57c00;'></span> Bajo / Reposo</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#d32f2f;'></span> Crítico</span>";
          } else {
            leyEl.innerHTML = "<span style='font-weight:700; margin-right:6px;'>Capa:</span> Vista satelital óptica de alta resolución (Esri World Imagery) con linderos de potrero.";
          }
        }
      });
    });

    // Toggle ver operarios
    var btnToggleOp = document.getElementById("btn-toggle-operarios");
    if (btnToggleOp) {
      btnToggleOp.addEventListener("click", function () {
        _mapaVerOperarios = !_mapaVerOperarios;
        if (_mapaVerOperarios) btnToggleOp.classList.add("act");
        else btnToggleOp.classList.remove("act");
        pintarUsuarios();
      });
    }

    // Centrar en toda la finca
    var btnCentrar = document.getElementById("btn-centrar-finca");
    if (btnCentrar) {
      btnCentrar.addEventListener("click", function () {
        if (d.finca && d.finca.bbox) map.fitBounds(d.finca.bbox, { padding: [30, 30] });
        else map.setView(centro, 14);
      });
    }

    // Botón refrescar
    var btnRefrescar = document.getElementById("btn-refrescar-mapa");
    if (btnRefrescar) {
      btnRefrescar.addEventListener("click", function () {
        btnRefrescar.textContent = "⏳";
        fetchJSON("/api/mapa/datos", function (nuevoD) {
          btnRefrescar.textContent = "🔄";
          d = nuevoD;
          pintarPotreros();
          pintarUsuarios();
        });
      });
    }

    // Auto-refresh silencioso de operarios cada 25 segundos
    _mapaTimerRefresh = setInterval(function () {
      if (actual !== "mapa") {
        clearInterval(_mapaTimerRefresh);
        _mapaTimerRefresh = null;
        return;
      }
      fetchJSON("/api/mapa/datos", function (nuevoD) {
        if (!nuevoD || !_mapaInstancia) return;
        d = nuevoD;
        pintarUsuarios();
      });
    }, 25000);

    // Botón "Mi Ubicación GPS"
    var btnMiGps = document.getElementById("btn-mi-ubicacion-mapa");
    if (btnMiGps) {
      btnMiGps.addEventListener("click", function () {
        if (!navigator.geolocation) {
          alert("Geolocalización no soportada en este navegador.");
          return;
        }
        btnMiGps.textContent = "📡 Buscando...";
        navigator.geolocation.getCurrentPosition(function (pos) {
          btnMiGps.textContent = "📍 Mi GPS";
          var myLat = pos.coords.latitude;
          var myLon = pos.coords.longitude;
          var myAcc = pos.coords.accuracy || 0;
          actualizarPosicionPropia(myLat, myLon, myAcc, false);
          if (_mapaInstancia) {
            _mapaInstancia.setView([myLat, myLon], 16);
            if (_mapaMarkerSelf) _mapaMarkerSelf.openPopup();
          }
        }, function (err) {
          btnMiGps.textContent = "📍 Mi GPS";
          alert("No fue posible obtener tu ubicación GPS: " + (err.message || "Permiso denegado."));
        }, { enableHighAccuracy: true, timeout: 10000 });
      });
    }

    // Delegación para botones "Enfocar" y "Ver rastro"
    qa("button[data-ir-usuario]").forEach(function (b) {
      b.addEventListener("click", function () {
        var idx = parseInt(b.getAttribute("data-ir-usuario"), 10);
        var u = d.usuarios_activos && d.usuarios_activos[idx];
        if (u && map) {
          map.setView([u.lat, u.lon], 17);
          try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
        }
      });
    });

    qa("button[data-rastro-usuario]").forEach(function (b) {
      b.addEventListener("click", function () {
        var idx = parseInt(b.getAttribute("data-rastro-usuario"), 10);
        var u = d.usuarios_activos && d.usuarios_activos[idx];
        if (!u || !u.rastro_hoy || !u.rastro_hoy.length) return;

        _mapaCapaRastros.clearLayers();
        var latlngs = u.rastro_hoy.map(function (pt) { return [pt[0], pt[1]]; });
        var poly = L.polyline(latlngs, {
          color: "#f39c12",
          weight: 3.5,
          dashArray: "6, 8",
          opacity: 0.85
        });
        _mapaCapaRastros.addLayer(poly);
        map.fitBounds(poly.getBounds(), { padding: [40, 40] });
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
      });
    });

    // Trazar ruta de operario en el mapa satelital
    qa("button[data-trazar-ruta-mapa]").forEach(function (b) {
      b.addEventListener("click", function () {
        var rIdx = parseInt(b.getAttribute("data-trazar-ruta-mapa"), 10);
        var r = d.rutas && d.rutas[rIdx];
        if (!r || !r.puntos || !r.puntos.length || !_mapaCapaRastros || !_mapaInstancia) return;

        _mapaCapaRastros.clearLayers();
        var latlngs = r.puntos.map(function (pt) { return [pt.lat, pt.lon]; });
        var poly = L.polyline(latlngs, {
          color: "#e67e22",
          weight: 4,
          dashArray: "6, 8",
          opacity: 0.95
        });
        _mapaCapaRastros.addLayer(poly);
        _mapaInstancia.fitBounds(poly.getBounds(), { padding: [35, 35] });

        var mapEl = document.getElementById("mapa-finca");
        if (mapEl) {
          try { mapEl.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (e) {}
        }
      });
    });

    // Control de fecha y recarga de auditoría de rutas
    var btnRefrescarRutas = document.getElementById("btn-refrescar-rutas");
    var inpFechaRutas = document.getElementById("filtro-fecha-rutas");
    if (btnRefrescarRutas && inpFechaRutas) {
      btnRefrescarRutas.addEventListener("click", function () {
        _fechaFiltroRutas = inpFechaRutas.value;
        cargar(true);
      });
      inpFechaRutas.addEventListener("change", function () {
        _fechaFiltroRutas = inpFechaRutas.value;
        cargar(true);
      });
    }

    // Ping manual de GPS para prueba
    var btnPingManual = document.getElementById("btn-ping-manual-gps");
    if (btnPingManual) {
      btnPingManual.addEventListener("click", function () {
        if (!navigator.geolocation) {
          alert("Geolocalización no disponible en este dispositivo.");
          return;
        }
        btnPingManual.textContent = "📡 Obteniendo GPS...";
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
              evento_origen: "prueba_manual_gps"
            })
          }).then(function (r) { return r.json(); })
            .then(function (res) {
              btnPingManual.textContent = "✅ Posición Registrada";
              setTimeout(function () { cargar(false); }, 800);
            }).catch(function (err) {
              btnPingManual.textContent = "❌ Error: " + err.message;
            });
        }, function (err) {
          btnPingManual.textContent = "❌ " + err.message;
        }, { enableHighAccuracy: true, timeout: 10000 });
      });
    }

    // Exportación CSV de Rutas
    var btnCsvRutas = document.getElementById("btn-exportar-rutas-csv");
    if (btnCsvRutas) {
      btnCsvRutas.addEventListener("click", function () {
        var fFechaSel = _fechaFiltroRutas || new Date().toISOString().slice(0, 10);
        var lineas = [["Usuario", "Rol", "Fecha", "Hora", "Potrero", "Latitud", "Longitud", "Precision_m", "Evento_Origen"]];
        (d.rutas || []).forEach(function (r) {
          (r.puntos || []).forEach(function (p) {
            lineas.push([
              r.usuario_nombre || "",
              r.rol || "",
              p.fecha || fFechaSel,
              p.hora || "",
              p.potrero_nombre || "Área de la Finca",
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
        a.download = "rutas_telemetria_ja_" + fFechaSel + ".csv";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }

    // Exportación CSV de Rondas
    var btnCsvRondas = document.getElementById("btn-exportar-rondas-csv");
    if (btnCsvRondas) {
      btnCsvRondas.addEventListener("click", function () {
        var fFechaSel = _fechaFiltroRutas || new Date().toISOString().slice(0, 10);
        exportarTablaCSV("rondas_campo_" + fFechaSel, "#tabla-rondas");
      });
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
      var badgeCls = syncUlt.al_dia ? "chip verde" : "chip ambar";
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

        var badgeRol = rolCat === "OWNER" ? "<span class='chip ambar' style='font-size:9.5px; padding:1px 5px;'>OWNER</span>"
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
    // d.texto viene de formatear_tablero_sistema() (mismo texto que usa el bot de
    // Telegram con parse_mode HTML): trae <b>/<i> intencionales y sus valores
    // dinámicos ya vienen escapados del lado del servidor -- no re-escapar aquí
    // o los tags salen literales en vez de renderizarse.
    h += "<h4>" + icon("grid") + "Diagnóstico General</h4>"
      + "<pre style='background:var(--superficie); color:var(--texto); border:1px solid var(--borde-fuerte); padding:12px; border-radius:8px; font-size:12px; white-space:pre-wrap; overflow-x:auto; line-height:1.4;'>"
      + (d.texto || "Sin diagnóstico disponible.") + "</pre>";

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
    if (r === "OWNER") return { lvl: 1, txt: "Level 1 (OWNER)", badge: "L1", color: "#d97706", chip: "ambar" };
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
      h += "<div class='card card-banner'>"
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
      + "<div id='usr-feedback' role='status' aria-live='polite' style='margin-top:12px;'></div>"
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
            chipClase = "ambar";
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

  /* ---------- Chat Dock Flotante Expansible Estilo WhatsApp con Micrófono ---------- */
  var _chatMediaRecorder = null;
  var _chatAudioChunks = [];
  var _chatAudioTimerInterval = null;
  var _chatAudioSegundos = 0;

  function setupChatDock() {
    var dock = document.getElementById("chat-dock") || document.getElementById("modal-chat");
    var btnChat = document.getElementById("btn-chat");
    var btnBurbuja = document.getElementById("chat-dock-burbuja");
    var btnExpandir = document.getElementById("btn-expandir-chat");
    var btnColapsar = document.getElementById("btn-colapsar-chat");
    var btnCerrar = document.getElementById("btn-cerrar-chat");
    var btnLimpiar = document.getElementById("btn-limpiar-chat");
    var form = document.getElementById("form-chat");
    var inp = document.getElementById("chat-input");
    var hist = document.getElementById("chat-historial");
    var btnMic = document.getElementById("chat-btn-mic");
    var btnHeaderMic = document.getElementById("btn-mic");
    var barAudio = document.getElementById("chat-audio-grabando");
    var timerAudio = document.getElementById("chat-audio-timer");
    var btnCancelarAudio = document.getElementById("btn-cancelar-audio");
    var btnEnviarAudio = document.getElementById("btn-enviar-audio");
    var tabIA = document.getElementById("tab-chat-ia");
    var tabEquipo = document.getElementById("tab-chat-equipo");
    var histEquipo = document.getElementById("chat-historial-equipo");
    var dotEquipo = document.getElementById("equipo-dot");

    if (!dock) return;

    function expandirChat(enfocar) {
      dock.classList.remove("colapsado");
      dock.classList.add("expandido");
      if (dock.classList.contains("modal-overlay")) dock.style.display = "flex";
      if (equipoTabActiva) {
        if (histEquipo) histEquipo.scrollTop = histEquipo.scrollHeight;
        equipoMarcarVisto(equipoUltimoId);
      } else if (hist) {
        hist.scrollTop = hist.scrollHeight;
      }
      if (enfocar && inp) setTimeout(function () { inp.focus(); }, 120);
    }

    function colapsarChat() {
      dock.classList.remove("expandido");
      dock.classList.add("colapsado");
      detenerAudioGrabacion(true);
    }

    function toggleChat() {
      if (dock.classList.contains("expandido")) colapsarChat();
      else expandirChat(true);
    }

    /* ---------- Chat de Equipo (canal de avisos entre usuarios conectados) ---------- */
    var ROL_ICONO_EQUIPO = { OWNER: "👑", ADMIN: "🛡️", TRABAJADOR: "👷" };
    var LS_EQUIPO_VISTO = "ja_chat_equipo_visto_id";
    var equipoTabActiva = false;
    var equipoUltimoId = 0;
    var equipoUltimoVistoId = parseInt(localStorage.getItem(LS_EQUIPO_VISTO) || "0", 10) || 0;

    function equipoHoraCorta(iso) {
      if (!iso) return "";
      var d = new Date(String(iso).replace(" ", "T"));
      if (isNaN(d.getTime())) return "";
      var hh = d.getHours(), mm = d.getMinutes();
      return (hh < 10 ? "0" : "") + hh + ":" + (mm < 10 ? "0" : "") + mm;
    }

    function equipoMarcarVisto(id) {
      equipoUltimoVistoId = id;
      try { localStorage.setItem(LS_EQUIPO_VISTO, String(id)); } catch (e) {}
      if (dotEquipo) dotEquipo.classList.remove("on");
      var bd = btnBurbuja && btnBurbuja.querySelector(".nav-badge");
      if (bd) bd.classList.remove("on");
    }

    function equipoEncenderNoLeido() {
      if (dotEquipo) dotEquipo.classList.add("on");
      if (btnBurbuja) {
        var bd = btnBurbuja.querySelector(".nav-badge");
        if (!bd) {
          bd = document.createElement("span");
          bd.className = "nav-badge";
          btnBurbuja.appendChild(bd);
        }
        bd.classList.add("on");
      }
    }

    function renderMensajeEquipo(m) {
      if (!histEquipo) return;
      var yo = window.__usuarioActual || {};
      var esMio = yo.user_id != null && String(yo.user_id) === String(m.user_id);
      var puedeBorrar = esMio || yo.rol === "OWNER" || yo.rol === "ADMIN";
      var div = document.createElement("div");
      div.className = "chat-msg equipo " + (esMio ? "mio" : "otro");
      div.setAttribute("data-id", m.id);
      var html = "";
      if (!esMio) {
        var ic = ROL_ICONO_EQUIPO[m.rol] || "👤";
        html += "<div class='chat-msg-cabecera'>" + ic + " " + esc(m.nombre) + "<span class='chat-msg-rol'>" + esc(m.rol) + "</span></div>";
      }
      html += "<div class='chat-msg-texto'>" + esc(m.texto) + "</div>";
      html += "<div class='chat-msg-hora'>" + equipoHoraCorta(m.creado_en);
      if (puedeBorrar) html += " <span class='chat-msg-borrar' data-id='" + m.id + "' title='Borrar mensaje'>🗑</span>";
      html += "</div>";
      div.innerHTML = html;
      histEquipo.appendChild(div);
    }

    function cargarMensajesEquipo() {
      fetch("/api/mensajes-equipo?despues_de=" + equipoUltimoId + "&limite=50")
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d || !d.ok) return;
          var nuevos = d.mensajes || [];
          nuevos.forEach(renderMensajeEquipo);
          if (typeof d.ultimo_id === "number") equipoUltimoId = d.ultimo_id;
          if (nuevos.length) {
            if (histEquipo) histEquipo.scrollTop = histEquipo.scrollHeight;
            if (equipoTabActiva && dock.classList.contains("expandido")) {
              equipoMarcarVisto(equipoUltimoId);
            } else if (equipoUltimoId > equipoUltimoVistoId) {
              equipoEncenderNoLeido();
            }
          }
        }).catch(function () {});
    }

    function enviarMensajeEquipo(txt) {
      fetch("/api/mensajes-equipo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: txt })
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.ok && d.mensaje) {
            if (typeof d.mensaje.id === "number" && d.mensaje.id > equipoUltimoId) equipoUltimoId = d.mensaje.id;
            renderMensajeEquipo(d.mensaje);
            if (histEquipo) histEquipo.scrollTop = histEquipo.scrollHeight;
            equipoMarcarVisto(equipoUltimoId);
          } else if (d && d.error) {
            mostrarToast(d.error, "rojo");
          }
        }).catch(function (err) {
          mostrarToast("Error de conexión: " + err.message, "rojo");
        });
    }

    function activarPestanaChat(cual) {
      equipoTabActiva = (cual === "equipo");
      if (tabIA) tabIA.classList.toggle("activa", cual === "ia");
      if (tabEquipo) tabEquipo.classList.toggle("activa", cual === "equipo");
      if (hist) hist.style.display = cual === "ia" ? "" : "none";
      if (histEquipo) histEquipo.style.display = cual === "equipo" ? "" : "none";
      if (btnMic) btnMic.style.display = cual === "ia" ? "" : "none";
      if (inp) inp.placeholder = cual === "ia" ? "Pregunta algo o pulsa 🎙️..." : "Escribe un aviso para el equipo...";
      if (cual === "equipo") {
        equipoMarcarVisto(equipoUltimoId);
        if (histEquipo) histEquipo.scrollTop = histEquipo.scrollHeight;
      }
    }

    if (tabIA) tabIA.addEventListener("click", function () { activarPestanaChat("ia"); });
    if (tabEquipo) {
      tabEquipo.addEventListener("click", function () {
        activarPestanaChat("equipo");
        expandirChat(false);
      });
    }

    if (histEquipo) {
      histEquipo.addEventListener("click", function (e) {
        var btn = e.target && e.target.closest ? e.target.closest(".chat-msg-borrar") : null;
        if (!btn) return;
        var id = btn.getAttribute("data-id");
        if (!id) return;
        fetch("/api/mensajes-equipo/" + encodeURIComponent(id), { method: "DELETE" })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d && d.ok) {
              var fila = histEquipo.querySelector(".chat-msg[data-id='" + id + "']");
              if (fila) fila.remove();
            } else if (d && d.error) {
              mostrarToast(d.error, "rojo");
            }
          }).catch(function () {});
      });
    }

    // Se expone en window: la carga inicial se dispara después de conocer
    // al usuario actual (ver cargarUsuario().finally en el arranque de la
    // app), para que "esMio" ya pueda distinguir bien desde el primer
    // pintado; el setInterval de polling junto al heartbeat reutiliza la
    // misma función.
    window.__cargarMensajesEquipo = cargarMensajesEquipo;

    if (btnChat) btnChat.addEventListener("click", function () { expandirChat(true); });
    if (btnBurbuja) btnBurbuja.addEventListener("click", function () { expandirChat(true); });
    if (btnExpandir) btnExpandir.addEventListener("click", function (e) { e.preventDefault(); toggleChat(); });
    if (btnColapsar) btnColapsar.addEventListener("click", function (e) { e.preventDefault(); colapsarChat(); });
    if (btnCerrar) btnCerrar.addEventListener("click", function (e) { e.preventDefault(); colapsarChat(); });

    if (inp) {
      inp.addEventListener("focus", function () {
        if (dock.classList.contains("colapsado")) expandirChat(false);
      });
      inp.addEventListener("click", function () {
        if (dock.classList.contains("colapsado")) expandirChat(false);
      });
    }

    if (btnLimpiar && hist) {
      btnLimpiar.addEventListener("click", function () {
        hist.innerHTML = "<div class='chat-msg bot'>Conversación reiniciada. Puedes hacerme cualquier consulta sobre el ganado o dictarme notas de voz 🎙️.</div>";
      });
    }

    // Copiar bloques de código/tablas en el chat
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

    qa(".chip-sug", dock).forEach(function (chip) {
      chip.addEventListener("click", function () {
        var p = chip.getAttribute("data-p");
        if (inp) inp.value = p;
        if (form) form.dispatchEvent(new Event("submit"));
      });
    });

    // Envío de mensaje escrito
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var txt = (inp && inp.value || "").trim();
        if (!txt) return;

        if (equipoTabActiva) {
          if (inp) inp.value = "";
          enviarMensajeEquipo(txt);
          return;
        }

        expandirChat(false);

        var botPlaceholder;
        if (hist) {
          hist.innerHTML += "<div class='chat-msg user'>" + esc(txt) + "</div>";
          botPlaceholder = document.createElement("div");
          botPlaceholder.className = "chat-msg bot";
          botPlaceholder.innerHTML = "<i>Consultando información ganadera...</i>";
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

    // Grabación de Audio Estilo WhatsApp
    function detenerAudioGrabacion(descartar) {
      if (_chatAudioTimerInterval) {
        clearInterval(_chatAudioTimerInterval);
        _chatAudioTimerInterval = null;
      }
      _chatAudioSegundos = 0;
      if (barAudio) barAudio.style.display = "none";
      if (form) form.style.display = "";

      if (_chatMediaRecorder) {
        if (descartar) {
          _chatAudioChunks = [];
          try {
            if (_chatMediaRecorder.stream) {
              _chatMediaRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
            }
          } catch (e) {}
          try { _chatMediaRecorder.stop(); } catch (e) {}
          _chatMediaRecorder = null;
        }
      }
    }

    function iniciarGrabacionWhatsApp() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("Tu navegador no soporta captura de audio desde el micrófono.");
        return;
      }

      expandirChat(false);

      if (form) form.style.display = "none";
      if (barAudio) barAudio.style.display = "flex";
      _chatAudioSegundos = 0;
      if (timerAudio) timerAudio.textContent = "0:00";
      if (_chatAudioTimerInterval) clearInterval(_chatAudioTimerInterval);
      _chatAudioTimerInterval = setInterval(function () {
        _chatAudioSegundos++;
        var m = Math.floor(_chatAudioSegundos / 60);
        var s = _chatAudioSegundos % 60;
        if (timerAudio) timerAudio.textContent = m + ":" + (s < 10 ? "0" : "") + s;
      }, 1000);

      _chatAudioChunks = [];
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        _chatMediaRecorder = new MediaRecorder(stream);
        _chatMediaRecorder.ondataavailable = function (e) {
          if (e.data && e.data.size > 0) _chatAudioChunks.push(e.data);
        };
        _chatMediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
        };
        _chatMediaRecorder.start();
      }).catch(function (err) {
        detenerAudioGrabacion(true);
        alert("No fue posible acceder al micrófono: " + err.message);
      });
    }

    if (btnMic) btnMic.addEventListener("click", function (e) { e.preventDefault(); iniciarGrabacionWhatsApp(); });
    if (btnHeaderMic) {
      btnHeaderMic.addEventListener("click", function (e) {
        e.preventDefault();
        iniciarGrabacionWhatsApp();
      });
    }

    if (btnCancelarAudio) {
      btnCancelarAudio.addEventListener("click", function (e) {
        e.preventDefault();
        detenerAudioGrabacion(true);
      });
    }

    if (btnEnviarAudio) {
      btnEnviarAudio.addEventListener("click", function (e) {
        e.preventDefault();
        if (!_chatMediaRecorder || _chatMediaRecorder.state !== "recording") {
          detenerAudioGrabacion(true);
          return;
        }

        if (_chatAudioTimerInterval) {
          clearInterval(_chatAudioTimerInterval);
          _chatAudioTimerInterval = null;
        }

        // Crear placeholders en chat mientras procesa
        var userMsgPlaceholder = document.createElement("div");
        userMsgPlaceholder.className = "chat-msg user";
        userMsgPlaceholder.innerHTML = "🎙️ <i>Audio enviado (procesando nota de voz)...</i>";
        if (hist) {
          hist.appendChild(userMsgPlaceholder);
          hist.scrollTop = hist.scrollHeight;
        }

        var botPlaceholder = document.createElement("div");
        botPlaceholder.className = "chat-msg bot";
        botPlaceholder.innerHTML = "<i>Transcribiendo con Whisper y consultando información ganadera...</i>";
        if (hist) {
          hist.appendChild(botPlaceholder);
          hist.scrollTop = hist.scrollHeight;
        }

        _chatMediaRecorder.addEventListener("stop", function () {
          if (!_chatAudioChunks.length) {
            userMsgPlaceholder.innerHTML = "🎙️ <i>Audio vacío.</i>";
            botPlaceholder.innerHTML = "⚠️ No se detectó sonido.";
            detenerAudioGrabacion(true);
            return;
          }

          var blob = new Blob(_chatAudioChunks, { type: _chatMediaRecorder.mimeType || "audio/webm" });
          detenerAudioGrabacion(false);

          var fd = new FormData();
          fd.append("audio", blob, "nota_campo.webm");

          fetch("/api/voz", { method: "POST", body: fd })
            .then(function (r) { return r.json(); })
            .then(function (data) {
              if (data.ok) {
                userMsgPlaceholder.innerHTML = "🎙️ <b>\"" + esc(data.transcripcion || "Nota de voz") + "\"</b>";
                botPlaceholder.innerHTML = formatearMensajeChat(data.respuesta || "Registrado correctamente.");
                actualizarBadges();
              } else {
                userMsgPlaceholder.innerHTML = "🎙️ <i>Nota de voz</i>";
                botPlaceholder.innerHTML = "⚠️ " + esc(data.error || "No se pudo procesar el audio.");
              }
              if (hist) hist.scrollTop = hist.scrollHeight;
            }).catch(function (err) {
              userMsgPlaceholder.innerHTML = "🎙️ <i>Nota de voz</i>";
              botPlaceholder.innerHTML = "❌ Error de conexión: " + esc(err.message);
              if (hist) hist.scrollTop = hist.scrollHeight;
            });
        }, { once: true });

        try { _chatMediaRecorder.stop(); } catch (e) { detenerAudioGrabacion(true); }
      });
    }
  }
  var setupChatModal = setupChatDock;

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
    var btnMapa = document.getElementById("btn-nav-mapa");
    var sheetSistema = document.getElementById("sheet-item-sistema");
    var sheetUsuarios = document.getElementById("sheet-item-usuarios");
    var sheetGps = document.getElementById("sheet-item-gps");
    var sheetMapa = document.getElementById("sheet-item-mapa");

    if (rol === "OWNER") {
      if (btnSistema) btnSistema.style.display = "";
      if (btnUsuarios) btnUsuarios.style.display = "";
      if (btnGps) btnGps.style.display = "none";
      if (btnMapa) btnMapa.style.display = "";
      if (sheetSistema) sheetSistema.style.display = "";
      if (sheetUsuarios) sheetUsuarios.style.display = "";
      if (sheetGps) sheetGps.style.display = "none";
      if (sheetMapa) sheetMapa.style.display = "";
      qa("#nav-principal > button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        if (v === "gps") b.style.display = "none";
        else b.style.display = "";
      });
      qa("#modal-mas-modulos .modulo-item").forEach(function (m) {
        var v = m.getAttribute("data-v");
        if (v === "gps") m.style.display = "none";
        else if (v !== "sistema" && v !== "usuarios") m.style.display = "";
      });
    } else if (rol === "ADMIN" || rol === "ADMINISTRADOR") {
      if (btnSistema) btnSistema.style.display = "none";
      if (btnGps) btnGps.style.display = "none";
      if (btnMapa) btnMapa.style.display = "";
      if (btnUsuarios) btnUsuarios.style.display = "";
      if (sheetSistema) sheetSistema.style.display = "none";
      if (sheetGps) sheetGps.style.display = "none";
      if (sheetMapa) sheetMapa.style.display = "";
      if (sheetUsuarios) sheetUsuarios.style.display = "";
      qa("#nav-principal > button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        if (v === "sistema" || v === "gps") b.style.display = "none";
        else b.style.display = "";
      });
      qa("#modal-mas-modulos .modulo-item").forEach(function (m) {
        var v = m.getAttribute("data-v");
        if (v === "sistema" || v === "gps") m.style.display = "none";
        else if (v !== "usuarios") m.style.display = "";
      });
    } else if (rol === "TRABAJADOR") {
      if (btnSistema) btnSistema.style.display = "none";
      if (btnUsuarios) btnUsuarios.style.display = "none";
      if (btnGps) btnGps.style.display = "none";
      if (btnMapa) btnMapa.style.display = "none";
      if (sheetSistema) sheetSistema.style.display = "none";
      if (sheetUsuarios) sheetUsuarios.style.display = "none";
      if (sheetGps) sheetGps.style.display = "none";
      if (sheetMapa) sheetMapa.style.display = "none";
      var permitidas = ["captura", "manga", "ficha"];
      qa("#nav-principal > button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        if (!v) return; // e.g. #btn-nav-mas
        if (permitidas.indexOf(v) !== -1) {
          b.style.display = "";
        } else {
          b.style.display = "none";
        }
      });
      qa("#modal-mas-modulos .modulo-item").forEach(function (m) {
        var v = m.getAttribute("data-v");
        if (permitidas.indexOf(v) !== -1) {
          m.style.display = "";
        } else {
          m.style.display = "none";
        }
      });
      if (permitidas.indexOf(actual) === -1 && actual !== "ayuda") {
        irAVista("captura");
        cargar();
      }
    }

    // Ocultar categorías sin módulos disponibles para este rol
    qa("#modal-mas-modulos .modulo-seccion").forEach(function (sec) {
      var items = qa(".modulo-item", sec);
      var visible = items.some(function (it) { return it.style.display !== "none"; });
      sec.style.display = visible ? "" : "none";
    });
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
      + "<input type='file' id='f-ident-foto' accept='image/*' style='min-height:40px; flex:1'>"
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
    if (stUpper === "ACTIVO") {
      estadoChip = "<span class='chip verde'>ACTIVO</span>";
    } else if (stUpper === "VENDIDO") {
      var fVenta = (f.venta && f.venta.fecha) ? (" · " + fechaCorta(f.venta.fecha)) : "";
      estadoChip = "<span class='chip ambar' style='font-weight:600; display:inline-flex; align-items:center; gap:4px;'>" + icon("receipt", 12) + "<span>VENDIDO" + esc(fVenta) + "</span></span>";
    } else if (stUpper === "MUERTO") {
      var fMuerte = (f.muerte && f.muerte.fecha) ? (" · " + fechaCorta(f.muerte.fecha)) : "";
      estadoChip = "<span class='chip rojo' style='font-weight:600; display:inline-flex; align-items:center; gap:4px;'>" + icon("cowSkull", 12) + "<span>MUERTO" + esc(fMuerte) + "</span></span>";
    } else if (stUpper === "DESCARTADO") {
      var fDesc = (f.venta && f.venta.fecha) ? (" · " + fechaCorta(f.venta.fecha)) : ((f.muerte && f.muerte.fecha) ? (" · " + fechaCorta(f.muerte.fecha)) : "");
      estadoChip = "<span class='chip ambar' style='font-weight:600;'>" + esc(f.estado) + esc(fDesc) + "</span>";
    } else if (f.estado) {
      estadoChip = "<span class='chip gris'>" + esc(f.estado) + "</span>";
    }

    var potChip = f.potrero ? "<span class='chip gris' style='margin-left:4px;'>" + icon("grass", 13) + esc(f.potrero) + "</span>" : "";
    var catChip = f.categoria_sg ? "<span class='chip gris' style='margin-left:4px;'>" + esc(f.categoria_sg) + "</span>" : "";
    var hierroChip = f.hierro ? ("<span class='chip ambar' style='margin-left:4px; font-weight:600;' title='Hierro / Marca a fuego de la ganadería'>" + icon("flame", 12) + "Hierro <b>" + esc(f.hierro) + "</b></span>") : "";
    var retiroChip = f.en_retiro ? "<span class='chip rojo' style='margin-left:4px; font-weight:bold;'>" + icon("alert", 13) + "EN RETIRO</span>" : "";

    head += "<div class='datos' style='flex:1; min-width:0;'>"
      + "<div style='display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin-bottom:4px;'>"
      + "<b style='font-size:18px; letter-spacing:-0.02em;'>" + esc(f.tag) + (f.nombre ? " · " + esc(f.nombre) : "") + "</b>"
      + estadoChip + retiroChip
      + "</div>"
      + "<div style='display:flex; flex-wrap:wrap; gap:4px; align-items:center; margin-bottom:4px;'>"
      + potChip + catChip + hierroChip
      + "</div>"
      + "<span class='meta' style='font-size:12px; color:var(--texto-suave);'>"
      + esc(f.sexo || "") + " · " + esc(f.raza || "S/D")
      + (f.hierro ? " · Hierro: <b>" + esc(f.hierro) + "</b>" : "")
      + (f.edad_str ? " · <b>" + esc(f.edad_str) + "</b>" : (f.fecha_nacimiento ? " · Nac: " + esc(fechaCorta(f.fecha_nacimiento)) : ""))
      + "</span>"
      + "</div>";

    var rolEd = window.__usuarioActual && window.__usuarioActual.rol;
    var btnEditar = (rolEd === "OWNER" || rolEd === "ADMIN")
      ? "<button type='button' class='tema-btn' data-accion='editar-animal' style='font-size:12px; padding:6px 10px; white-space:nowrap; display:inline-flex; align-items:center; cursor:pointer;'>" + icon("pencil", 15) + "Editar</button>"
      : "";
    head += "<div style='display:flex; flex-direction:column; gap:6px; align-self:flex-start;'>"
      + "<a href='/api/ficha/" + encodeURIComponent(f.tag) + "/qr.pdf' target='_blank' download class='tema-btn' style='font-size:12px; padding:6px 10px; text-decoration:none; white-space:nowrap; display:inline-flex; align-items:center;'>"
      + icon("filePdf", 15) + "Ficha PDF</a>"
      + btnEditar
      + "</div>";

    head += "</div>";

    // BLOQUE 4: FAB "Registrar evento" — salta a Captura con el tag actual.
    head += "<button id='btn-ficha-registrar' class='fab-registrar' title='Registrar evento' aria-label='Registrar evento'>"
      + icon("plus", 20)
      + "<span style='position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap;'>Registrar evento</span>"
      + "</button>";

    var html = (showIdent ? identPanelHtml() : "") + head + erroresHtml(f);
    html += "<div id='ficha-tabs' role='tablist'><div class='mini'>"
      + TABS.map(function (t, i) { return "<button role='tab' aria-selected='" + (i === 0 ? "true" : "false") + "' data-tab='" + t.id + "' class='" + (i === 0 ? "act" : "") + "'>" + t.label + "</button>"; }).join("")
      + "</div></div><div id='ficha-panel'>" + fichaTab("general", f) + "</div>";
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
        + "<div style='font-size:11.5px; color:var(--texto-suave); margin-top:3px;'>Regla de control de 3 generaciones antes de autorizar cruzamiento o servicio de monta/I.A.</div>"
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
        var hie = an.hierro ? (" <span class='chip ambar' style='font-size:10px; padding:1px 4px;' title='Hierro'>" + esc(an.hierro) + "</span>") : "";
        return "<div style='background:var(--superficie); border:1px solid var(--borde-fuerte); border-radius:8px; padding:10px; font-size:12.5px; box-shadow:0 1px 3px var(--sombra);'>"
          + "<div style='font-weight:600; font-size:11px; text-transform:uppercase; color:var(--texto-suave); margin-bottom:4px;'>" + icono + " " + esc(label) + "</div>"
          + "<div><a href='#' class='ficha-link' " + click + " style='font-weight:bold; font-size:14px; text-decoration:none;'><b>" + esc(an.tag) + "</b></a>" + nom + " <span class='chip gris' style='font-size:11px; padding:1px 5px;'>" + esc(an.raza || "S/D") + "</span>" + hie + "</div>"
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
        var txtEstado = lac.estado_confirmado && lac.fecha_secado
          ? esc(lac.estado) + " (secada el " + esc(lac.fecha_secado) + ")"
          : esc(lac.estado) + (lac.estado === "Seca" ? " (estimado por días, sin secado registrado)" : "");
        h3 += "<p class='aviso'>" + icon("milk", 14) + txtEstado + " · <b>" + esc(lac.del_dias) + "</b> DEL (parto " + esc(lac.fecha_parto) + ")</p>";
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
    var stUpper = String(f.estado || "").toUpperCase();

    // Banner destacado si el animal fue VENDIDO
    if (stUpper === "VENDIDO" || (f.venta && f.venta.fecha)) {
      var v = f.venta || {};
      var fecVenta = v.fecha ? fechaCorta(v.fecha) : (f.fecha_salida ? fechaCorta(f.fecha_salida) : "Fecha no registrada");
      var destVenta = v.procedencia_destino ? esc(v.procedencia_destino) : "Destino no especificado";
      var precioVenta = (v.precio != null && Number(v.precio) > 0) ? (" · <b>" + fmtMoneda(v.precio) + "</b>") : "";

      var extraVenta = "";
      if (v.madre_tag) {
        extraVenta += "<div style='margin-top:4px;'><span style='color:var(--texto-suave);'>Venta conjunta (cría al pie):</span> Se vendió junto a su madre <a href='#' class='ficha-link' data-ir-ficha=\"" + esc(v.madre_tag) + "\"><b>" + esc(v.madre_tag) + "</b>" + (v.madre_nombre ? " (" + esc(v.madre_nombre) + ")" : "") + "</a></div>";
      }
      if (v.crias_vendidas && v.crias_vendidas.length) {
        var cvLinks = v.crias_vendidas.map(function (cv) {
          return "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(cv.tag) + "\"><b>" + esc(cv.tag) + "</b>" + (cv.nombre ? " (" + esc(cv.nombre) + ")" : "") + "</a>";
        }).join(", ");
        extraVenta += "<div style='margin-top:4px;'><span style='color:var(--texto-suave);'>Venta conjunta con cría(s):</span> Vendida en la misma fecha junto a " + cvLinks + "</div>";
      }
      var notasVenta = v.notas ? ("<div style='margin-top:6px; font-size:12.5px; background:var(--superficie); padding:6px 10px; border-radius:6px; border:1px solid var(--borde);'><b>Observaciones de venta:</b> " + esc(v.notas) + "</div>") : "";

      h += "<div class='banner-baja banner-baja-venta'>"
        + "<div style='color:var(--color-ambar-txt); margin-top:2px; flex-shrink:0;'>" + icon("receipt", 24) + "</div>"
        + "<div style='flex:1; min-width:0;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;'>"
        + "<div class='titulo-baja'>REGISTRO DE VENTA · ANIMAL VENDIDO</div>"
        + "<span class='chip ambar' style='font-size:12px; font-weight:bold;'>" + icon("calendar", 12) + "Vendido el: " + esc(fecVenta) + "</span>"
        + "</div>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:6px; font-size:13px;'>"
        + "<div><span style='color:var(--texto-suave);'>Fecha de Venta:</span> <b>" + esc(fecVenta) + "</b></div>"
        + "<div><span style='color:var(--texto-suave);'>Comprador / Destino:</span> <b>" + destVenta + "</b>" + precioVenta + "</div>"
        + "</div>"
        + extraVenta
        + notasVenta
        + "</div></div>";
    }

    // Banner destacado si el animal está MUERTO
    if (stUpper === "MUERTO" || (f.muerte && f.muerte.fecha)) {
      var m = f.muerte || {};
      var fecMuerte = m.fecha ? fechaCorta(m.fecha) : (f.fecha_baja ? fechaCorta(f.fecha_baja) : "Fecha no registrada");
      var causaMuerte = m.causa_presunta ? esc(m.causa_presunta) : "Sin causa registrada";
      var notasMuerte = m.notas ? ("<div style='margin-top:6px; font-size:12.5px; background:var(--superficie); padding:6px 10px; border-radius:6px; border:1px solid var(--borde);'><b>Diagnóstico / Necropsia / Notas:</b> " + esc(m.notas) + "</div>") : "";

      h += "<div class='banner-baja banner-baja-muerte'>"
        + "<div style='color:var(--color-rojo-txt); margin-top:2px; flex-shrink:0;'>" + icon("cowSkull", 24) + "</div>"
        + "<div style='flex:1; min-width:0;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;'>"
        + "<div class='titulo-baja'>BAJA POR MUERTE · ANIMAL FALLECIDO</div>"
        + "<span class='chip rojo' style='font-size:12px; font-weight:bold;'>" + icon("calendar", 12) + "Murió el: " + esc(fecMuerte) + "</span>"
        + "</div>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:6px; font-size:13px;'>"
        + "<div><span style='color:var(--texto-suave);'>Fecha de Muerte:</span> <b>" + esc(fecMuerte) + "</b></div>"
        + "<div><span style='color:var(--texto-suave);'>Causa Presunta:</span> <b style='color:var(--color-rojo-txt);'>" + causaMuerte + "</b></div>"
        + "</div>"
        + notasMuerte
        + "</div></div>";
    }

    // Banner si fue DESCARTADO
    if (stUpper === "DESCARTADO" && !(f.venta && f.venta.fecha) && !(f.muerte && f.muerte.fecha)) {
      h += "<div class='banner-baja banner-baja-descarte'>"
        + "<div style='color:var(--color-gris-txt); margin-top:2px; flex-shrink:0;'>" + icon("alert", 24) + "</div>"
        + "<div style='flex:1; min-width:0;'>"
        + "<div class='titulo-baja'>ANIMAL DESCARTADO</div>"
        + "<p style='margin:4px 0 0 0; font-size:13px; color:var(--texto-suave);'>Este animal ha sido dado de baja o descartado del hato activo.</p>"
        + "</div></div>";
    }

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

    var potreroKpiLabel = "Potrero Actual";
    var potreroKpiVal = f.potrero ? esc(f.potrero) : "Sin asignar";
    if (stUpper === "VENDIDO") {
      potreroKpiLabel = "Estado Hato";
      potreroKpiVal = "Vendido";
    } else if (stUpper === "MUERTO") {
      potreroKpiLabel = "Estado Hato";
      potreroKpiVal = "Baja (Muerte)";
    } else if (stUpper === "DESCARTADO") {
      potreroKpiLabel = "Estado Hato";
      potreroKpiVal = "Descartado";
    }

    h += "<div class='kpis' style='margin-bottom:14px;'>"
      + kpi(potreroKpiVal, potreroKpiLabel)
      + kpi(f.edad_str ? esc(f.edad_str) : (f.edad_dias != null ? f.edad_dias + " d" : "—"), "Edad")
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
      + "<div><span style='color:var(--texto-suave);'>Hierro / Marca:</span> <b>" + (f.hierro ? ("<span style='color:var(--verde-marca);'>" + icon("flame", 13) + esc(f.hierro) + "</span>") : "S/D") + "</b></div>"
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

    // 6. Historial de Bajas, Ventas y Movimientos
    var bajasList = (f.historial_bajas && f.historial_bajas.length) ? f.historial_bajas : (f.movimientos || []);
    if (bajasList && bajasList.length) {
      h += "<h4 style='margin-top:16px;'>" + icon("receipt") + "Historial de Bajas, Ventas y Movimientos</h4>"
        + tabla(bajasList, [
          ["fecha", "Fecha", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }],
          ["tipo", "Tipo", "text", function (v, row) {
            var t = String(v || row.tipo_movimiento || "MOVIMIENTO").toUpperCase();
            if (t === "VENTA") return "<span class='chip ambar' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("receipt", 12) + "<span>Venta</span></span>";
            if (t === "MUERTE") return "<span class='chip rojo' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("cowSkull", 12) + "<span>Muerte</span></span>";
            if (t === "COMPRA") return "<span class='chip verde' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("plus", 12) + "<span>Compra</span></span>";
            if (t === "TRASLADO") return "<span class='chip gris' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("truck", 12) + "<span>Traslado</span></span>";
            return "<span class='chip gris'>" + esc(t) + "</span>";
          }],
          ["destino_causa", "Destino / Causa / Detalle", "text", function (v, row) {
            var d = v || row.procedencia_destino || row.causa_presunta || "—";
            return esc(d);
          }],
          ["precio", "Precio / Valor", "text", function (v) {
            return (v != null && Number(v) > 0) ? ("<b>" + fmtMoneda(v) + "</b>") : "—";
          }],
          ["notas", "Observaciones", "text", function (v) { return esc(v || "—"); }]
        ], "Sin movimientos ni bajas registradas.");
    }

    // 6. Tarjeta de Código QR & Ficha Oficial PDF
    h += "<div class='card' style='padding:16px; margin-top:14px; background:var(--superficie); border:1px solid var(--borde); border-radius:8px;'>"
      + "<div style='display:flex; gap:16px; align-items:center; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:220px;'>"
      + "<h4 style='margin-top:0;'>" + icon("camera") + "Código QR & Ficha Técnica del Animal</h4>"
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
    qa(".mini button", nav).forEach(function (b) {
      b.addEventListener("click", function () {
        qa(".mini button", nav).forEach(function (x) { x.classList.remove("act"); x.setAttribute("aria-selected", "false"); });
        b.classList.add("act");
        b.setAttribute("aria-selected", "true");
        var panel = document.getElementById("ficha-panel");
        if (panel) panel.innerHTML = fichaTab(b.getAttribute("data-tab"), ficha || window.__ultimaFicha || {});
      });
    });
    // BLOQUE 4: el FAB lleva a Captura prellenando el tag de esta ficha.
    var btnFab = document.getElementById("btn-ficha-registrar");
    if (btnFab) {
      btnFab.addEventListener("click", function () {
        var tagFab = (ficha && ficha.tag) || (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
        tagFab = String(tagFab || "").trim();
        if (tagFab) {
          try { localStorage.setItem("bitacora_ultimo_tag", tagFab); } catch (eFabTag) { /* noop */ }
          window.__capTagPendiente = tagFab;
        }
        irAVista("captura");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eFabScroll) { window.scrollTo(0, 0); }
      });
    }
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
    mercado:   { kpis: 3, graf: 0, tabla: 8 },
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

    var destino = qa("#nav-principal > button").filter(function (b) { return b.getAttribute("data-v") === "ficha"; })[0];
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

    irAVista("ficha");

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
      else if (acc === "crear-animal") { mostrarFormularioAnimal(null, elAcc.getAttribute("data-tag-nuevo") || ""); }
      else if (acc === "editar-animal") { mostrarFormularioAnimal(window.__ultimaFicha || null); }
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
    if (!qa("#nav-principal > button").length) return; // solo en el dashboard con navegación
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
  function mostrarFormularioAnimal(f, tagPrellenado) {
    var esEdicion = !!(f && f.tag);
    var overlay = document.getElementById("animal-form-modal");
    if (overlay) overlay.remove();

    function val(v) { return v == null ? "" : esc(v); }
    var madreTag = (f && f.madre && f.madre.tag) || "";
    var padreTag = (f && f.padre && f.padre.tag) || "";
    var nacimiento = (f && f.fecha_nacimiento) ? String(f.fecha_nacimiento).slice(0, 10) : "";

    function campo(id, etiqueta, valorAttr, extra) {
      return "<label style='display:block; font-size:12.5px; font-weight:600; margin-bottom:2px;'>" + etiqueta
        + "<input id='" + id + "' value='" + valorAttr + "'" + (extra || "")
        + " style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:400; margin-top:2px;'></label>";
    }

    var html = "<div id='animal-form-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:480px;'>"
      + "<div class='modal-header'><b>" + icon(esEdicion ? "pencil" : "plus", 15) + (esEdicion ? "Editar Animal " + val(f.tag) : "Crear Animal Nuevo") + "</b>"
      + "<button type='button' class='modal-cerrar' id='btn-cerrar-animal-form'>✕</button></div>"
      + "<form id='form-animal' style='padding:16px; display:flex; flex-direction:column; gap:10px; max-height:70vh; overflow-y:auto;'>"
      + campo("an-tag", "Arete / Tag *", val((f && f.tag) || tagPrellenado), esEdicion ? " disabled" : " required autofocus placeholder='ej. 47'")
      + campo("an-nombre", "Nombre", val(f && f.nombre), " placeholder='ej. Carranga'")
      + "<label style='display:block; font-size:12.5px; font-weight:600;'>Sexo<select id='an-sexo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:400; margin-top:2px;'>"
      + "<option value=''>—</option>"
      + "<option value='Hembra'" + ((f && f.sexo) === "Hembra" ? " selected" : "") + ">Hembra</option>"
      + "<option value='Macho'" + ((f && f.sexo) === "Macho" ? " selected" : "") + ">Macho</option>"
      + "</select></label>"
      + campo("an-raza", "Raza (código o nombre)", val(f && f.raza), " placeholder='ej. I, T, C, M'")
      + campo("an-nacimiento", "Fecha de nacimiento", nacimiento, " type='date'")
      + campo("an-madre", "Madre (tag)", val(madreTag), " list='dl-tags' placeholder='ej. 47'")
      + campo("an-padre", "Padre (tag)", val(padreTag), " list='dl-tags' placeholder='ej. T1'")
      + campo("an-potrero", "Potrero", val(f && f.potrero && f.potrero !== "Sin potrero asignado" ? f.potrero : ""), " list='dl-potreros' placeholder='ej. Guayabal'")
      + campo("an-hierro", "Hierro / Marca a fuego", val(f && f.hierro), " placeholder='ej. JA'")
      + campo("an-chip", "Chip / RFID", val(f && f.chip), " placeholder='ej. 985...'")
      + campo("an-color", "Color / Pelo", val(f && f.color), " placeholder='ej. Negro'")
      + "<label style='display:block; font-size:12.5px; font-weight:600;'>Notas<textarea id='an-notas' rows='2' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:400; margin-top:2px; font-family:inherit;'>" + val(f && f.notas) + "</textarea></label>"
      + "<p id='animal-form-error' class='aviso' style='display:none;'></p>"
      + "<button type='submit' class='tema-btn' style='padding:10px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer;'>" + icon("save", 15) + (esEdicion ? "Guardar Cambios" : "Crear Animal") + "</button>"
      + "</form></div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("animal-form-modal");
    function cerrarModal() { if (ov) ov.remove(); }
    var btnCerrar = document.getElementById("btn-cerrar-animal-form");
    if (btnCerrar) btnCerrar.addEventListener("click", cerrarModal);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrarModal(); });

    var form = document.getElementById("form-animal");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var tag = (q("#an-tag").value || "").trim();
      var payload = {
        nombre: q("#an-nombre").value, sexo: q("#an-sexo").value,
        raza: q("#an-raza").value, fecha_nacimiento: q("#an-nacimiento").value,
        madre_tag: q("#an-madre").value, padre_tag: q("#an-padre").value,
        potrero: q("#an-potrero").value, hierro: q("#an-hierro").value,
        chip: q("#an-chip").value, color: q("#an-color").value,
        notas: q("#an-notas").value,
      };
      if (!esEdicion) payload.tag = tag;
      var errorEl = document.getElementById("animal-form-error");
      var url = esEdicion ? "/api/animal/" + encodeURIComponent(tag) : "/api/animal";
      var metodo = esEdicion ? "PUT" : "POST";
      fetch(url, {
        method: metodo, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      }).then(function (r) { return r.json().then(function (d) { return { status: r.status, body: d }; }); })
        .then(function (res) {
          if (res.status >= 200 && res.status < 300 && res.body.ok) {
            cerrarModal();
            abrirFicha(tag, vista, true);
            irAVista("ficha");
          } else if (errorEl) {
            errorEl.textContent = "❌ " + (res.body.error || "No se pudo guardar.");
            errorEl.style.display = "block";
          }
        }).catch(function (err) {
          if (errorEl) { errorEl.textContent = "❌ " + (err && err.message || err); errorEl.style.display = "block"; }
        });
    });
  }
  function abrirFicha(tag, target, showIdent, animar) {
    if (animar === undefined) animar = true;
    if (animar) skeleton(target, "ficha");
    fetchJSON("/api/ficha/" + encodeURIComponent(tag), function (f) {
      if (!f.existe) {
        var rolNf = window.__usuarioActual && window.__usuarioActual.rol;
        var btnCrearNf = (rolNf === "OWNER" || rolNf === "ADMIN")
          ? "<button type='button' class='tema-btn' data-accion='crear-animal' data-tag-nuevo='" + esc(tag) + "' style='margin-top:10px; padding:8px 14px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center;'>" + icon("plus", 15) + "Crear animal " + esc(tag) + "</button>"
          : "";
        if (target) montarVista(target, "<h3>" + icon("cow") + "Ficha animal</h3><p>❌ Sin registro para <b>" + esc(tag) + "</b>.</p>"
          + "<p class='aviso'>💡 Si viene de escanear un arete, puede que el tag aún no esté en la base. "
          + "Pruebe escribiendo el número sin guiones (ej. " + esc(String(tag).replace(/\D/g, "") || tag) + ").</p>"
          + btnCrearNf, animar);
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
      irAVista("mapa");
      cargar(animar);
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

    if (actual === "mapa") {
      var rol = (window.__usuarioActual && window.__usuarioActual.rol || "").toUpperCase();
      if (rol === "TRABAJADOR") {
        irAVista("captura");
        cargar(true);
        return;
      }
      if (animar) skeleton(vista, "mapa");
      var fFecha = _fechaFiltroRutas || (q("#filtro-fecha-rutas") && q("#filtro-fecha-rutas").value) || new Date().toISOString().slice(0, 10);
      fetchJSON("/api/mapa/datos?fecha=" + encodeURIComponent(fFecha), function (d) {
        if (!vista) return;
        montarVista(vista, renderMapa(d), animar);
        cargarLeafletSiFalta(function () { bindMapa(d); });
      }, animar ? vista : null);
      return;
    }

    if (actual === "mercado") {
      var rolMerc = (window.__usuarioActual && window.__usuarioActual.rol || "").toUpperCase();
      if (rolMerc === "TRABAJADOR") {
        irAVista("captura");
        cargar(true);
        return;
      }
      if (animar) skeleton(vista, "mercado");
      fetchJSON("/api/mercado/precios", function (d) {
        if (!vista) return;
        montarVista(vista, renderMercado(d), animar);
        bindMercado(d);
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
      if (actual === "pasturas") bindPasturas();
      if (actual === "leche") bindLeche();
      if (actual === "finanzas") bindFinanzas();
      if (actual === "agenda") bindAgenda();
    }, animar ? vista : null);
  }

  /* ---------- Badges de contadores en la navegación ---------- */
  var VISTAS_BADGE = ["agenda", "repro", "sanidad"];
  var badgesCache = {};
  function crearBadgesNav() {
    VISTAS_BADGE.forEach(function (v) {
      var btn = qa("#nav-principal > button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
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
        var totalSecundario = 0;
        VISTAS_BADGE.forEach(function (v) {
          var n = parseInt(d && d[v], 10) || 0;
          var btn = qa("#nav-principal > button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
          if (btn) {
            var span = btn.querySelector(".nav-badge");
            if (span) {
              if (n > 0) { span.textContent = n > 99 ? "99+" : String(n); span.classList.add("on"); }
              else { span.textContent = ""; span.classList.remove("on"); }
            }
          }
          var item = document.querySelector("#modal-mas-modulos .modulo-item[data-v='" + v + "']");
          if (item) {
            var bSpan = item.querySelector(".badge-sheet");
            if (!bSpan) {
              bSpan = document.createElement("span");
              bSpan.className = "badge-sheet";
              item.appendChild(bSpan);
            }
            if (n > 0) {
              bSpan.textContent = n > 99 ? "99+" : String(n);
              bSpan.style.display = "inline-block";
            } else {
              bSpan.textContent = "";
              bSpan.style.display = "none";
            }
          }
          totalSecundario += n;
        });

        var btnMas = document.getElementById("btn-nav-mas");
        if (btnMas) {
          var spanMas = btnMas.querySelector(".nav-badge");
          if (!spanMas) {
            spanMas = document.createElement("span");
            spanMas.className = "nav-badge";
            btnMas.appendChild(spanMas);
          }
          if (totalSecundario > 0) {
            spanMas.textContent = totalSecundario > 99 ? "99+" : String(totalSecundario);
            spanMas.classList.add("on");
          } else {
            spanMas.textContent = "";
            spanMas.classList.remove("on");
          }
        }

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
        verificarAlertasPush();
      }).catch(function () { /* sin red: se ocultan */ });
  }

  function setupCampana() {
    var camp = document.getElementById("btn-notif");
    if (!camp) return;
    camp.addEventListener("click", function () {
      if ("Notification" in window && Notification.permission === "default") {
        iniciarWebPush(false).catch(function () {});
      }
      var destino = qa("#nav-principal > button").filter(function (b) { return b.getAttribute("data-v") === "agenda"; })[0];
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
      irAVista("ayuda");
      var barraFiltros = document.getElementById("barra-filtros");
      if (barraFiltros) barraFiltros.style.display = "none";
      cargar(true);
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
    });
  }

  var VISTAS_PRIMARIAS = ["tablero", "captura", "inventario", "finanzas"];
  var NOMBRES_VISTA = {
    tablero: "Tablero",
    captura: "Captura",
    inventario: "Inventario",
    finanzas: "Finanzas",
    mapa: "Mapa & GPS",
    manga: "Manga",
    agenda: "Agenda",
    repro: "Repro",
    leche: "Leche",
    sanidad: "Sanidad",
    pasturas: "Pasturas",
    genetica: "Genética",
    ficha: "Ficha",
    gps: "Mapa & GPS",
    usuarios: "Usuarios",
    sistema: "Sistema",
    mercado: "Subastas",
    ayuda: "Ayuda"
  };

  function setupModalMas() {
    var modalMas = document.getElementById("modal-mas-modulos");
    var btnNavMas = document.getElementById("btn-nav-mas");
    var btnCerrarMas = document.getElementById("btn-cerrar-mas");

    function abrirModalMas() {
      if (!modalMas) return;
      modalMas.style.display = "flex";
      qa("#modal-mas-modulos .modulo-item").forEach(function (it) {
        if (it.getAttribute("data-v") === actual) it.classList.add("act");
        else it.classList.remove("act");
      });
    }

    function cerrarModalMas() {
      if (!modalMas) return;
      modalMas.style.display = "none";
    }

    window.__abrirModalMas = abrirModalMas;
    window.__cerrarModalMas = cerrarModalMas;

    if (btnNavMas) {
      btnNavMas.addEventListener("click", function (e) {
        e.stopPropagation();
        abrirModalMas();
      });
    }

    if (btnCerrarMas) {
      btnCerrarMas.addEventListener("click", function (e) {
        e.stopPropagation();
        cerrarModalMas();
      });
    }

    if (modalMas) {
      modalMas.addEventListener("click", function (e) {
        if (e.target === modalMas) cerrarModalMas();
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modalMas && modalMas.style.display === "flex") {
        cerrarModalMas();
      }
    });

    qa("#modal-mas-modulos .modulo-item").forEach(function (item) {
      item.addEventListener("click", function () {
        var v = item.getAttribute("data-v");
        if (!v) return;
        cerrarModalMas();
        irAVista(v);
        var barraFiltros = document.getElementById("barra-filtros");
        if (barraFiltros) {
          barraFiltros.style.display = (v === "ayuda") ? "none" : "";
        }
        cargar();
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
      });
    });
  }

  qa("#nav-principal > button").forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.id === "btn-nav-mas") {
        if (typeof window.__abrirModalMas === "function") window.__abrirModalMas();
        return;
      }
      var v = b.getAttribute("data-v");
      if (!v) return;
      irAVista(v);
      cargar();
      if (VISTAS_BADGE.indexOf(actual) !== -1) {
        var span = b.querySelector(".nav-badge");
        if (span) { span.textContent = ""; span.classList.remove("on"); }
      }
    });
  });

  // Cambia de pestaña activa sin recargar
  function irAVista(v) {
    if (actual === "mapa" && v !== "mapa") {
      if (_mapaTimerRefresh) {
        clearInterval(_mapaTimerRefresh);
        _mapaTimerRefresh = null;
      }
      if (_mapaWatchGpsId && navigator.geolocation) {
        navigator.geolocation.clearWatch(_mapaWatchGpsId);
        _mapaWatchGpsId = null;
      }
      _mapaMarkerSelf = null;
      _mapaCircleSelf = null;
      _mapaCapaSelf = null;
      if (_mapaInstancia) {
        try { _mapaInstancia.remove(); } catch (e) {}
        _mapaInstancia = null;
      }
    }
    actual = v;
    qa("#nav-principal > button").forEach(function (x) { x.classList.remove("act"); });
    qa("#nav-principal button[data-v]").forEach(function (b) { b.removeAttribute("aria-current"); });
    var destino = qa("#nav-principal > button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
    if (destino) { destino.classList.add("act"); if (destino.hasAttribute("data-v")) destino.setAttribute("aria-current", "page"); }

    // Sincronizar botón Más en barra móvil
    var btnMas = document.getElementById("btn-nav-mas");
    var txtMas = document.getElementById("txt-nav-mas");
    if (btnMas) {
      if (VISTAS_PRIMARIAS.indexOf(v) !== -1) {
        btnMas.classList.remove("act");
        if (txtMas) txtMas.textContent = "Más";
      } else {
        btnMas.classList.add("act");
        if (txtMas) txtMas.textContent = NOMBRES_VISTA[v] || "Más";
      }
    }

    // Sincronizar ítem activo en modal de módulos
    qa("#modal-mas-modulos .modulo-item").forEach(function (it) {
      if (it.getAttribute("data-v") === v) { it.classList.add("act"); it.setAttribute("aria-current", "page"); }
      else { it.classList.remove("act"); it.removeAttribute("aria-current"); }
    });
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
  // El datalist #dl-potreros es compartido por TODOS los campos de potrero de
  // la app (filtro superior, Traslado, Finanzas, Manga, editar animal), pero
  // antes solo se llenaba al tocar el campo del filtro superior -- si el
  // usuario nunca pasaba por ahí, los demás campos (con list='dl-potreros'
  // en su HTML) se veían sin autocompletar. Se precarga una vez al iniciar
  // para que esté listo en cualquier campo desde el principio.
  cargarListaPotreros();

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
      irAVista("ayuda");
      var barraFiltros = document.getElementById("barra-filtros");
      if (barraFiltros) barraFiltros.style.display = "none";
      cargar(true);
      return;
    }
    if (pot && q("#f-potrero")) q("#f-potrero").value = pot;
    if (tag && q("#f-tag")) q("#f-tag").value = tag;
    if (!v && (pot || tag)) v = pot ? "tablero" : "ficha";
    if (v && qa("#nav-principal > button").length) {
      var destino = qa("#nav-principal > button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
      if (destino) {
        irAVista(v);
        cargar();
        return;
      }
    }
    cargar();
  }

  /* ---------- Visor Lightbox de Imágenes (Agrandar y Mover con la Mano) ---------- */
  function mostrarLightbox(src, titulo) {
    if (!src) return;
    var existente = document.getElementById("lightbox-visor");
    if (existente && existente.parentNode) existente.parentNode.removeChild(existente);

    var lb = document.createElement("div");
    lb.id = "lightbox-visor";
    lb.className = "lightbox-overlay";
    lb.setAttribute("role", "dialog");
    lb.setAttribute("aria-label", "Visor de imagen agrandada");

    var tit = titulo || "Fotografía";
    var h = "<div class='lightbox-topbar'>"
      + "<div class='lightbox-titulo'>" + icon("camera", 16) + esc(tit) + "</div>"
      + "<div class='lightbox-acciones'>"
      + "<button type='button' id='lb-btn-zoom-out' class='lightbox-btn' title='Alejar (Zoom -)'>" + icon("search", 13) + "<span>-</span></button>"
      + "<button type='button' id='lb-btn-zoom-in' class='lightbox-btn' title='Acercar (Zoom +)'>" + icon("plus", 13) + "<span>+</span></button>"
      + "<button type='button' id='lb-btn-zoom-toggle' class='lightbox-btn' title='Alternar Zoom'><span id='lb-zoom-text'>Zoom 2x</span></button>"
      + "<a href='" + esc(src) + "' target='_blank' download class='lightbox-btn' title='Descargar / Abrir en pestaña nueva'>" + icon("download", 13) + "<span>Descargar</span></a>"
      + "<button type='button' id='lb-btn-cerrar' class='lightbox-btn lightbox-btn-cerrar' title='Cerrar (Esc)'>" + icon("xmark", 13) + "<span>Cerrar</span></button>"
      + "</div></div>"
      + "<div class='lightbox-img-wrap' id='lb-img-wrap'>"
      + "<img class='lightbox-img' id='lb-img' src='" + esc(src) + "' alt='" + esc(tit) + "' draggable='false'>"
      + "</div>"
      + "<div style='color:rgba(255,255,255,0.75); font-size:11.5px; margin-top:8px; text-align:center; pointer-events:none; user-select:none;'>"
      + "✋ Arrastra con la mano para mover · 🔍 Rueda o doble toque para zoom · Esc para salir</div>";

    lb.innerHTML = h;
    document.body.appendChild(lb);
    document.body.style.overflow = "hidden"; // bloquear scroll del fondo

    var wrap = lb.querySelector("#lb-img-wrap");
    var img = lb.querySelector("#lb-img");
    var btnCerrar = lb.querySelector("#lb-btn-cerrar");
    var btnZoomIn = lb.querySelector("#lb-btn-zoom-in");
    var btnZoomOut = lb.querySelector("#lb-btn-zoom-out");
    var btnZoomToggle = lb.querySelector("#lb-btn-zoom-toggle");
    var zoomText = lb.querySelector("#lb-zoom-text");

    var scale = 1.0;
    var panX = 0;
    var panY = 0;
    var isDragging = false;
    var hasMoved = false;
    var startX = 0;
    var startY = 0;
    var pinchStartDist = 0;
    var pinchStartScale = 1.0;
    var lastTapTime = 0;

    function applyTransform(withTransition) {
      if (!img) return;
      if (withTransition) {
        img.style.transition = "transform 0.18s cubic-bezier(0.2, 0.8, 0.2, 1)";
      } else {
        img.style.transition = "none";
      }

      if (scale <= 1.05) {
        scale = 1.0;
        panX = 0;
        panY = 0;
        img.classList.remove("zoomed", "grabbing");
        img.style.cursor = "zoom-in";
        if (zoomText) zoomText.textContent = "Zoom 2x";
      } else {
        img.classList.add("zoomed");
        img.style.cursor = isDragging ? "grabbing" : "grab";
        if (zoomText) zoomText.textContent = Math.round(scale * 100) + "% (Alejar)";

        // Limitar pan según escala y dimensiones del contenedor para no perder la foto fuera de pantalla
        var wrapRect = wrap ? wrap.getBoundingClientRect() : { width: window.innerWidth * 0.9, height: window.innerHeight * 0.8 };
        var maxPanX = Math.max(60, (wrapRect.width * (scale - 1)) / 2 + 150);
        var maxPanY = Math.max(60, (wrapRect.height * (scale - 1)) / 2 + 150);
        if (panX > maxPanX) panX = maxPanX;
        if (panX < -maxPanX) panX = -maxPanX;
        if (panY > maxPanY) panY = maxPanY;
        if (panY < -maxPanY) panY = -maxPanY;
      }

      img.style.transform = "translate3d(" + panX + "px, " + panY + "px, 0) scale(" + scale + ")";
    }

    // Cerrar visor y limpiar listeners de window
    function cerrar() {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      lb.style.opacity = "0";
      setTimeout(function () { if (lb && lb.parentNode) lb.parentNode.removeChild(lb); }, 150);
    }

    function onKey(e) {
      if (e.key === "Escape") cerrar();
      else if (e.key === "+" || e.key === "=") zoomIn();
      else if (e.key === "-" || e.key === "_") zoomOut();
    }
    window.addEventListener("keydown", onKey);

    function zoomIn() {
      scale = Math.min(4.0, (scale < 1.1 ? 2.0 : scale + 0.5));
      applyTransform(true);
    }

    function zoomOut() {
      scale = Math.max(1.0, scale - 0.5);
      applyTransform(true);
    }

    function toggleZoom() {
      if (scale > 1.05) {
        scale = 1.0;
        panX = 0;
        panY = 0;
      } else {
        scale = 2.2;
      }
      applyTransform(true);
    }

    if (btnCerrar) btnCerrar.addEventListener("click", cerrar);
    if (btnZoomIn) btnZoomIn.addEventListener("click", function (e) { e.stopPropagation(); zoomIn(); });
    if (btnZoomOut) btnZoomOut.addEventListener("click", function (e) { e.stopPropagation(); zoomOut(); });
    if (btnZoomToggle) btnZoomToggle.addEventListener("click", function (e) { e.stopPropagation(); toggleZoom(); });

    // ---------- Mouse Dragging con la Mano (Desktop) ----------
    function onMouseDown(e) {
      if (e.button !== 0) return; // Solo clic izquierdo
      e.preventDefault();
      isDragging = true;
      hasMoved = false;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
      img.classList.add("grabbing");
      img.style.cursor = "grabbing";
      img.style.transition = "none";
    }

    function onMouseMove(e) {
      if (!isDragging) return;
      var newPanX = e.clientX - startX;
      var newPanY = e.clientY - startY;
      if (Math.hypot(newPanX - panX, newPanY - panY) > 3) {
        hasMoved = true;
      }
      panX = newPanX;
      panY = newPanY;
      applyTransform(false);
    }

    function onMouseUp() {
      if (!isDragging) return;
      isDragging = false;
      img.classList.remove("grabbing");
      if (scale > 1.0) img.style.cursor = "grab";
      applyTransform(true);
    }

    if (img) {
      img.addEventListener("mousedown", onMouseDown);
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);

    // Clic en la imagen (distingue clic de arrastre con la mano)
    if (img) {
      img.addEventListener("click", function (e) {
        e.stopPropagation();
        if (hasMoved) return; // El usuario estaba arrastrando con la mano
        toggleZoom();
      });
    }

    // Rueda del mouse (desktop) para zoom suave hacia la posición del cursor
    if (wrap) {
      wrap.addEventListener("wheel", function (e) {
        e.preventDefault();
        var delta = e.deltaY < 0 ? 0.3 : -0.3;
        var prevScale = scale;
        scale = Math.min(4.0, Math.max(1.0, scale + delta));
        if (scale !== prevScale && scale > 1.0) {
          var rect = wrap.getBoundingClientRect();
          var ox = e.clientX - (rect.left + rect.width / 2);
          var oy = e.clientY - (rect.top + rect.height / 2);
          panX -= ox * (scale / prevScale - 1) * 0.4;
          panY -= oy * (scale / prevScale - 1) * 0.4;
        }
        applyTransform(true);
      }, { passive: false });
    }

    // ---------- Touch Dragging & Pinch en Pantallas Táctiles (Móvil / Tablet) ----------
    if (wrap) {
      wrap.addEventListener("touchstart", function (e) {
        if (e.touches.length === 1) {
          isDragging = true;
          hasMoved = false;
          startX = e.touches[0].clientX - panX;
          startY = e.touches[0].clientY - panY;
          img.style.transition = "none";
        } else if (e.touches.length === 2) {
          isDragging = false;
          hasMoved = true;
          pinchStartDist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
          pinchStartScale = scale;
        }
      }, { passive: true });

      wrap.addEventListener("touchmove", function (e) {
        if (e.touches.length === 1 && isDragging) {
          e.preventDefault();
          var newPanX = e.touches[0].clientX - startX;
          var newPanY = e.touches[0].clientY - startY;
          if (Math.hypot(newPanX - panX, newPanY - panY) > 4) {
            hasMoved = true;
          }
          panX = newPanX;
          panY = newPanY;
          applyTransform(false);
        } else if (e.touches.length === 2 && pinchStartDist > 0) {
          e.preventDefault();
          hasMoved = true;
          var dist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
          scale = Math.min(4.0, Math.max(1.0, pinchStartScale * (dist / pinchStartDist)));
          applyTransform(false);
        }
      }, { passive: false });

      wrap.addEventListener("touchend", function (e) {
        if (isDragging) {
          isDragging = false;
          applyTransform(true);
        }
        // Doble toque rápido para zoom
        if (!hasMoved && e.touches.length === 0) {
          var now = Date.now();
          if (now - lastTapTime < 300) {
            toggleZoom();
            lastTapTime = 0;
          } else {
            lastTapTime = now;
          }
        }
      }, { passive: true });
    }

    // Clic en el fondo oscuro para cerrar
    lb.addEventListener("click", function (e) {
      if (e.target === lb || e.target.id === "lb-img-wrap") {
        cerrar();
      }
    });

    // Iniciar con escala 1.0 centrada
    applyTransform(false);
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
    setupModalMas();
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
    // Refresco del chat de equipo (cada 20s con pestaña activa): más
    // frecuente que el heartbeat porque un canal de avisos pierde utilidad
    // si tarda un minuto en aparecer, sin bajar a segundos para no generar
    // tráfico innecesario sobre SQLite en modo WAL.
    setInterval(function () {
      if (!document.hidden && navigator.onLine && window.__cargarMensajesEquipo) {
        window.__cargarMensajesEquipo();
      }
    }, 20000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && navigator.onLine) {
        fetch("/api/heartbeat", { method: "POST" }).catch(function () {});
        if (window.__cargarMensajesEquipo) window.__cargarMensajesEquipo();
      }
    });
    // Primer refresco de badges y cola offline al reconectar tras estar sin señal.
    window.addEventListener("online", function () {
      actualizarBadges();
      sincronizarColaOffline(false);
    });
    cargarUsuario().finally(function () {
      arrancarDesdeUrl();
      if (window.__cargarMensajesEquipo) window.__cargarMensajesEquipo();
    });
  }
})();
