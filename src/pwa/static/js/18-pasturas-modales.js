  // Modo Simple (default) vs Técnico para SPI y Monitoreo Satelital en Pasturas:
  // los números crudos (NDVI, RVI, SPI, kg/ha) son ilegibles para un ganadero
  // que no es agrónomo -- Simple muestra solo el semáforo/palabra clave,
  // Técnico muestra todo el detalle igual que antes. Se recuerda por navegador.
  function modoPasturasEsSimple() {
    return localStorage.getItem("modoPasturasSimple") !== "tecnico";
  }
  // Cache de potreros de la última respuesta /api/pasturas para el modal D2.
  var potrerosRondaCache = [];
  function renderPasturas(d) {
    window.__datosUltimoPasturas = d;
    if (d && d.pronostico) {
      actualizarClimaHeader(d.pronostico);
    } else {
      actualizarClimaHeader();
    }
    var simple = modoPasturasEsSimple();
    var btnModo = "<button type='button' id='btn-toggle-modo-pasturas' class='tema-btn' style='font-size:12px; padding:5px 12px; margin-left:8px;'>"
      + (simple ? icon("stethoscope", 14) + "Ver técnico" : "Ver simple") + "</button>";
    var h = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("grass", 22) + "Pasturas (Voisin & Aforos)" + btnModo + "</h3>"
      + barraDescargaSeccion("pasturas", "Pasturas")
      + "</div>" + erroresHtml(d);

    var pron = d.pronostico;
    h += "<h4>" + icon("rain") + "Pronóstico del clima (7 días)</h4>";
    if (!pron || !pron.dias || !pron.dias.length) {
      h += vacio("Sin pronóstico disponible (requiere al menos un potrero con geometría/coordenadas registradas).");
    } else {
      h += "<div style='display:flex; gap:8px; overflow-x:auto; padding-bottom:8px;'>";
      pron.dias.forEach(function (dd) {
        var prob = dd.prob_lluvia_pct;
        var lluvia = Number(dd.lluvia_mm) || 0;
        var alerta = lluvia >= 8 ? "ambar" : "verde";
        h += "<div class='card' style='min-width:110px; flex-shrink:0; padding:10px; text-align:center;'>"
          + "<div style='font-size:11px; font-weight:700; color:var(--texto-suave); text-transform:uppercase;'>" + esc(fechaCorta(dd.fecha)) + "</div>"
          + "<div style='font-size:13px; font-weight:700; margin:4px 0;'>" + esc(Math.round(dd.temp_max_c)) + "° / " + esc(dd.temp_min_c == null ? "—" : Math.round(dd.temp_min_c)) + "°</div>"
          + "<span class='chip " + alerta + "' style='font-size:11px;'>" + icon("droplet", 11) + esc(lluvia.toFixed(1)) + " mm</span>"
          + (prob != null ? "<div style='font-size:10.5px; color:var(--texto-suave); margin-top:4px;'>" + esc(Math.round(prob)) + "% prob. del día</div>" : "")
          + "</div>";
      });
      h += "</div>";
      if (pron.recomendaciones && pron.recomendaciones.length) {
        h += "<div class='card' style='padding:10px 14px;'>"
          + pron.recomendaciones.map(function (r) { return "<div style='font-size:13px; margin:3px 0;'>• " + esc(r) + "</div>"; }).join("")
          + "</div>";
      }
      if (pron.desactualizado_horas != null) {
        h += "<p class='aviso'>" + icon("alertTriangle", 14) + "Datos del pronóstico de hace " + Math.round(pron.desactualizado_horas) + " h (sin conexión a Open-Meteo en la última actualización).</p>";
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
      + icon("sparkles", 13) + (simple ? "Actualizar (con nubes)" : "Radar SAR (Todo Clima)") + "</button>";
    var btnSyncAuto = "<button type='button' class='tema-btn' id='btn-sync-satelite-auto' style='font-size:12px; padding:6px 12px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; box-shadow:0 2px 4px rgba(0,0,0,0.15);'>"
      + icon("sparkles", 13) + (simple ? "Actualizar (rápido)" : "Auto (S2 + S1)") + "</button>";

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
          + kpiIr(kpi("<span class='chip " + chipNdvi + "' style='font-size:16px; padding:6px 14px;'><b>" + esc(etiquetaEstado) + "</b></span>", "Estado general del pasto"), { sec: "Tablero Integral de Potreros" })
          + "</div>";
      } else {
        h += "<div class='kpis'>"
          + kpiIr(kpi("<span class='chip " + chipNdvi + "' style='font-size:14px;'><b>" + esc(ndviProm != null ? ndviProm : "—") + "</b></span>", "NDVI Promedio Finca"), { sec: "Visualización Gráfica de Potreros" })
          + kpiIr(kpi(esc(sat.modo_activo || "Radar SAR"), "Sensor Principal"), { sec: "Visualización Gráfica de Potreros" })
          + (sat.promedio_biomasa_kg_ha != null ? kpiIr(kpi(esc(Math.round(sat.promedio_biomasa_kg_ha).toLocaleString()) + " kg/ha", "Biomasa Promedio MS"), { sec: "Tablero Integral de Potreros" }) : "")
          + (sat.promedio_aforo_kg_m2 != null ? kpiIr(kpi(esc(sat.promedio_aforo_kg_m2) + " kg/m²", "Aforo Promedio MV"), { sec: "Tablero Integral de Potreros" }) : "")
          + kpiIr(kpi(esc(sat.cobertura_clima || "100% Todo Clima"), "Cobertura Climática", "ok"), { sec: "Pluviómetro Local" })
          + "</div>";
      }
    }

    if (!simple) {
      h += "<div class='card' style='padding:10px 14px; margin-bottom:14px; background:rgba(30, 60, 114, 0.05); border-left:4px solid #2a5298;'>"
        + "<div style='font-size:12.5px; line-height:1.45; color:var(--texto-color);'>"
        + "<b>" + icon("satellite", 14) + "Monitoreo Radar SAR Sentinel-1 (C-band 10m):</b> En época de lluvias, la nubosidad bloquea el sensor óptico Sentinel-2. "
        + "El radar SAR emite microondas que penetran nubes, lluvia y neblina, calculando el índice dual de vegetación (RVI) y biomasa estimada sin perder continuidad temporal."
        + "</div></div>";
    }

    // Indexación de aforos y lecturas satelitales por nombre de potrero (evita tablas repetidas)
    var aforosPorPot = {};
    (d.aforos_recientes || []).forEach(function (a) {
      var k = String(a.potrero || "").toUpperCase().trim();
      if (k && !aforosPorPot[k]) aforosPorPot[k] = a;
    });
    var satPorPot = {};
    (d.ndvi_reciente || []).forEach(function (s) {
      var k = String(s.potrero || "").toUpperCase().trim();
      if (k && !satPorPot[k]) satPorPot[k] = s;
    });

    // 1. Selector de Pestañas de Gráficos (evita apilar 3 gráficos verticales gigantes)
    var graficosPasturas = [
      { id: "mapa_potreros", nom: icon("map", 12) + "Mapa Potreros (Voisin)", desc: "Distribución satelital y rotación" },
      { id: "ocupacion", nom: icon("chartBar", 12) + "Ocupación y Carga", desc: "Carga animal por potrero" },
      { id: "aforo", nom: icon("grass", 12) + "Aforos y Forraje", desc: "Disponibilidad de forraje verde" }
    ];
    h += "<div class='card' style='padding:12px; margin:14px 0 10px; background:var(--superficie); border-left:4px solid var(--verde-marca);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<div style='font-size:13px; font-weight:700; color:var(--texto); display:flex; align-items:center; gap:6px;'>"
      + icon("chartLine", 15) + "Visualización Gráfica de Potreros"
      + "</div>"
      + "<div class='tabs-graficos-pasturas' style='display:flex; gap:6px; flex-wrap:wrap;'>";
    graficosPasturas.forEach(function (g) {
      var act = _pasturasGraficoActivo === g.id ? " act' style='background:var(--verde-marca); color:#fff; font-weight:700; border:none;'" : "'";
      h += "<button type='button' class='tema-btn btn-tab-graf-pasturas" + act + " data-graf='" + g.id + "' style='font-size:11.5px; padding:5px 11px; border-radius:6px; cursor:pointer;'>" + g.nom + "</button>";
    });
    h += "</div></div>";

    if (_pasturasGraficoActivo === "mapa_potreros") {
      h += grafico("mapa_potreros", "Rotación de potreros (Voisin)");
    } else if (_pasturasGraficoActivo === "ocupacion") {
      h += grafico("ocupacion", "Ocupación de potreros");
    } else if (_pasturasGraficoActivo === "aforo") {
      h += grafico("aforo", "Aforo de forraje");
    }
    h += "</div>";

    // 2. Tablero Integral Unificado de Potreros (Consolida Ocupación, Reposo, Animales y Aforo en una sola vista)
    h += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin:18px 0 8px;'>"
      + "<h4 style='margin:0;'>" + icon("hourglass") + "Tablero Integral de Potreros (Voisin, Carga & Aforos)</h4>"
      + "<div style='font-size:12px; color:var(--texto-suave);'>Consolidado oficial del hato activo</div>"
      + "</div>";

    if (!d.potreros || !d.potreros.length) {
      h += vacio("Sin potreros con geometría registrada.");
    } else {
      function iconoPastoVoisin(dias) {
        if (dias == null) return dot("gris") + " ";
        var num = Number(dias);
        if (num < 12) return "<span title='Rebrote tierno (" + num + " d)' style='font-size:14px; margin-right:4px;'>" + icon("sprout", 14) + "</span>";
        if (num <= 24) return "<span title='En desarrollo (" + num + " d)' style='font-size:14px; margin-right:4px;'>" + icon("leaf", 14) + "</span>";
        if (num <= 45) return "<span title='Punto óptimo Voisin (" + num + " d)' style='font-size:14px; margin-right:4px;'>" + icon("grass", 14) + "</span>";
        return "<span title='Pasado de reposo (" + num + " d)' style='font-size:14px; margin-right:4px;'>" + icon("leaf", 14) + "</span>";
      }

      h += "<div class='tabla-scroll'><table>"
        + "<tr>"
        + "<th>Potrero</th>"
        + "<th>Estado Voisin</th>"
        + "<th style='text-align:center;'>Ocupación / Reposo</th>"
        + "<th style='text-align:center;'>Animales</th>"
        + "<th style='text-align:right;'>Aforo / Forraje</th>"
        + "<th style='text-align:right;'>Biomasa MS</th>"
        + "<th style='text-align:center;'>Acción</th>"
        + "</tr>";

      h += d.potreros.map(function (p) {
        var nom = p.nombre || p.codigo || p.id;
        var nomKey = String(nom).toUpperCase().trim();
        var nAnim = Number(p.total_animales) || 0;
        var st = p.estado_rotacion || (nAnim > 0 ? (p.semaforo === "🟢" ? "Pastoreo óptimo" : p.semaforo === "🟡" ? "Rotar pronto" : "Sobreocupado") : "En reposo");
        var haTxt = p.area_has != null ? (!isNaN(Number(p.area_has)) ? Number(p.area_has).toFixed(1) : p.area_has) + " ha" : "";

        var tiempoTxt = nAnim > 0
          ? "<span style='font-weight:700; color:var(--verde-marca);'>" + icon("hourglass", 14) + "Ocupado " + (p.dias_ocupacion != null ? p.dias_ocupacion + "d" : "activo") + "</span>"
          : (iconoPastoVoisin(p.dias_reposo) + "<span style='color:var(--texto);'>Reposo " + (p.dias_reposo != null ? p.dias_reposo + "d" : "—") + "</span>");

        var animCol = nAnim > 0
          ? "<button type='button' class='tema-btn btn-listar-animales-pot' data-potrero='" + esc(nom) + "' style='font-size:11.5px; padding:3px 9px; border-radius:5px; font-weight:700; display:inline-flex; align-items:center; gap:5px; background:rgba(46,125,50,0.12); color:var(--verde-marca); border:1px solid var(--verde-marca);' title='Ver " + nAnim + " animales en " + esc(nom) + "'>"
            + icon("cow", 12) + "<span><b>" + nAnim + "</b> cab.</span></button>"
          : "<span style='color:var(--texto-suave); font-size:12px;'>0 (Vacío)</span>";

        // Cruce con aforos recientes y satélite
        var afoRec = aforosPorPot[nomKey];
        var satRec = satPorPot[nomKey];

        var aforoStr = "—";
        if (afoRec && afoRec.aforo_kg_m2 != null) {
          aforoStr = "<b>" + Number(afoRec.aforo_kg_m2).toFixed(2) + "</b> kg/m²";
        } else if (satRec && satRec.aforo_estimado_kg_m2 != null) {
          aforoStr = "<b>" + Number(satRec.aforo_estimado_kg_m2).toFixed(2) + "</b> kg/m² <small style='color:var(--texto-suave);'>(sat)</small>";
        }

        var biomasaStr = "—";
        if (satRec && satRec.biomasa_estimada_kg_ha != null) {
          biomasaStr = Math.round(satRec.biomasa_estimada_kg_ha).toLocaleString("es-CO") + " kg/ha";
        }

        return "<tr>"
          + "<td style='white-space:nowrap;'>"
          + "<a href='#' class='link-potrero-animales' data-potrero='" + esc(nom) + "' style='font-weight:700; color:var(--verde-marca); text-decoration:none;' title='Ver animales en " + esc(nom) + "'>" + esc(nom) + "</a>"
          + (haTxt ? ("<br><small style='color:var(--texto-suave); font-size:11px;'>" + esc(haTxt) + "</small>") : "")
          + "</td>"
          + "<td style='white-space:nowrap;'>" + chipEstado(p.semaforo + " " + st) + "</td>"
          + "<td style='text-align:center; white-space:nowrap;'>" + tiempoTxt + "</td>"
          + "<td style='text-align:center; white-space:nowrap;'>" + animCol + "</td>"
          + "<td style='text-align:right; white-space:nowrap;'>" + aforoStr + "</td>"
          + "<td style='text-align:right; white-space:nowrap; font-family:var(--font-mono); font-size:12px;'>" + biomasaStr + "</td>"
          + "<td style='text-align:center; white-space:nowrap;'>"
          + "<div style='display:inline-flex; gap:4px;'>"
          + "<button type='button' class='tema-btn btn-listar-animales-pot' data-potrero='" + esc(nom) + "' style='font-size:11px; padding:3px 8px; border-radius:5px;' title='Listar aretes'>" + icon("cow", 11) + "Listar</button>"
          + "<button type='button' class='tema-btn btn-aforar-pot-directo' data-potrero='" + esc(nom) + "' style='font-size:11px; padding:3px 8px; border-radius:5px; color:var(--verde-marca); border:1px solid var(--verde-marca);' title='Registrar aforo'>" + icon("grass", 11) + "Aforo</button>"
          + "</div></td>"
          + "</tr>";
      }).join("");

      h += "</table></div>";
    }

    h += "<h4>" + icon("rain") + "Pluviómetro Local Reciente</h4>"
      + tabla(d.pluviometria_reciente, [
        ["fecha", "Fecha"],
        ["mm_lluvia", "Lluvia", "text", function (v) {
          return "<b>" + esc(v) + " mm</b>";
        }],
        ["observaciones", "Observaciones"]
      ], "Sin registros de pluviometría manual.");
    // D2 — Checklist de Ronda Voisin: flujo en 3 pasos (potrero → 10-15
    // puntos GPS → resultado con semáforo). La lista de potreros se guarda
    // en potrerosRondaCache para el modal (bindPasturas la reutiliza).
    potrerosRondaCache = (d.potreros || []).map(function (p) {
      return { id: p.id, nombre: p.nombre || p.codigo || ("#" + p.id) };
    });
    h += "<div class='card' style='padding:12px 14px; margin-top:14px; border-left:4px solid var(--verde-marca);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;'>"
      + "<div><b>" + icon("sprout", 16) + "Checklist de Ronda Voisin</b><div style='font-size:12px; color:var(--texto-suave);'>10-15 puntos de aforo por potrero → días de forraje + semáforo</div></div>"
      + "<button type='button' class='tema-btn' id='btn-nueva-ronda' style='background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; padding:8px 14px; cursor:pointer;'>+ Nueva Ronda Voisin</button>"
      + "</div><div id='rondas-recientes' style='margin-top:8px; font-size:12.5px;'></div></div>";
    return h;
  }

  // D2 — Modal de ronda Voisin (usa .modal-overlay/.modal-contenido existentes).
  function abrirModalRonda() {
    if (document.getElementById("ronda-voisin-modal")) return;
    var opts = potrerosRondaCache.map(function (p) {
      return "<option value='" + esc(p.nombre) + "'>" + esc(p.nombre) + "</option>";
    }).join("");
    var html = "<div id='ronda-voisin-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:520px;'>"
      + "<div class='modal-header'><b>" + icon("sprout", 16) + "Nueva Ronda Voisin</b><button type='button' class='modal-cerrar' id='btn-cerrar-ronda' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
      + "<div style='padding:14px 16px; display:flex; flex-direction:column; gap:10px; overflow-y:auto;'>"
      + "<label style='font-size:13px;'><b>1. Potrero</b><br><select id='rv-potrero' class='ronda-campo' style='width:100%; margin-top:4px;'>" + opts + "</select></label>"
      + "<label style='font-size:13px;'><b>2. Nº de animales en pastoreo</b><br><input id='rv-num-animales' class='ronda-campo' type='number' min='1' value='1' style='width:100%; margin-top:4px;'></label>"
      + "<label style='font-size:13px;'><b>3. Mediciones (g MV/m² por punto, 10-15 pts)</b><br>"
      + "<textarea id='rv-mediciones' class='ronda-campo' rows='3' style='width:100%; margin-top:4px;' placeholder='450, 380, 420, 390, 410, 440, 370, 400, 430, 385'></textarea>"
      + "<span style='font-size:11.5px; color:var(--texto-suave);'>Separadas por coma o espacio. Valores &gt; 10 se leen como gramos y se convierten a kg.</span></label>"
      + "<button type='button' class='tema-btn' id='rv-evaluar' style='background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; padding:10px; cursor:pointer;'>Evaluar Ronda</button>"
      + "<div id='rv-resultado' style='font-size:13.5px; line-height:1.5;'></div>"
      + "<div id='rv-historial' style='font-size:12.5px; color:var(--texto-suave);'></div>"
      + "</div></div></div>";
    document.body.insertAdjacentHTML("beforeend", html);
    var ov = document.getElementById("ronda-voisin-modal");
    function cerrar() { if (ov) ov.remove(); }
    document.getElementById("btn-cerrar-ronda").addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });
    function pintarHistorial(pot) {
      var hist = document.getElementById("rv-historial");
      if (!hist) return;
      fetch("/api/pasturas/rondas?potrero=" + encodeURIComponent(pot || ""))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var filas = (data && data.rondas) || [];
          if (!filas.length) { hist.innerHTML = "Sin rondas previas en este potrero."; return; }
          hist.innerHTML = "Últimas rondas: " + filas.slice(0, 5).map(function (x) {
            var c = x.semaforo === "VERDE" ? "verde" : x.semaforo === "AMARILLO" ? "ambar" : "rojo";
            return "<span class='chip " + c + "' style='font-size:11px; margin:2px;'>" + esc(x.fecha) + " · " + esc(x.dias_disponibles) + " d</span>";
          }).join("");
        })
        .catch(function () { /* sin historial offline: no bloquea */ });
    }
    var selPot = document.getElementById("rv-potrero");
    if (selPot) {
      selPot.addEventListener("change", function () { pintarHistorial(selPot.value); });
      pintarHistorial(selPot.value);
    }
    document.getElementById("rv-evaluar").addEventListener("click", function () {
      var res = document.getElementById("rv-resultado");
      var btn = document.getElementById("rv-evaluar");
      var txt = (document.getElementById("rv-mediciones").value || "").trim();
      var vals = txt.split(/[,;\s]+/).map(function (x) { return parseFloat(x); }).filter(isFinite);
      // El trabajador anota en gramos (ej. 450); la API espera kg MV/m².
      vals = vals.map(function (v) { return v > 10 ? v / 1000 : v; });
      if (!vals.length) { res.innerHTML = "<p class='aviso'>" + icon("alertTriangle", 14) + "Ingresa al menos una medición válida.</p>"; return; }
      var nAnim = parseInt((document.getElementById("rv-num-animales").value || "1"), 10) || 1;
      btn.disabled = true;
      res.innerHTML = icon("hourglass", 14) + "Evaluando...";
      fetch("/api/pasturas/ronda", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ potrero: selPot ? selPot.value : "", mediciones: vals, num_animales: nAnim })
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (out) {
          btn.disabled = false;
          if (!out.ok || !out.j.ok) {
            res.innerHTML = "<p class='aviso'>" + icon("xCircle", 14) + esc((out.j && out.j.error) || "No se pudo evaluar (¿potrero sin área?).") + "</p>";
            return;
          }
          var ronda = out.j.ronda || {};
          var chip = ronda.semaforo === "VERDE" ? "verde" : ronda.semaforo === "AMARILLO" ? "ambar" : "rojo";
          // `mensaje` lo genera el servidor (formatear_ronda_voisin) con <b> intencional.
          // Se escapa todo y solo se restauran <b> y <br>, para no pintar HTML arbitrario.
          res.innerHTML = "<div>" + htmlBasico(out.j.mensaje || "") + "</div>"
            + "<div style='margin-top:6px;'><span class='chip " + chip + "' style='font-size:14px;'><b>" + esc(ronda.semaforo || "") + " · " + esc(ronda.dias_disponibles) + " días</b></span></div>";
          if (selPot) pintarHistorial(selPot.value);
          var box = document.getElementById("rondas-recientes");
          if (box) cargarRondasRecientes();
        })
        .catch(function (err) {
          btn.disabled = false;
          res.innerHTML = "<p class='aviso'>" + icon("xCircle", 14) + "Error de red: " + esc(err.message || err) + "</p>";
        });
    });
  }

  function abrirModalListaAnimales(cfg) {
    if (!cfg || !cfg.url) return;
    var idModal = "modal-animales-lista";
    var previo = document.getElementById(idModal) || document.getElementById("modal-animales-potrero");
    if (previo) previo.remove();

    var icName = cfg.icono || "cow";
    var tituloModal = cfg.titulo || "Animales Activos";

    var html = "<div id='" + idModal + "' class='modal-overlay' style='display:flex; align-items:center; justify-content:center; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:9999; padding:12px; box-sizing:border-box;'>"
      + "<div class='modal-contenido' style='max-width:640px; width:100%; max-height:88vh; display:flex; flex-direction:column; background:var(--superficie); border-radius:10px; box-shadow:0 8px 32px rgba(0,0,0,0.3); overflow:hidden;'>"
      + "<div class='modal-header' style='display:flex; justify-content:space-between; align-items:center;'>"
      + "<div style='display:flex; align-items:center; gap:8px; font-size:15px; font-weight:700; color:#fff; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>"
      + icon(icName, 18)
      + "<span style='overflow:hidden; text-overflow:ellipsis;'>" + esc(tituloModal) + "</span>"
      + "</div>"
      + "<button type='button' class='modal-cerrar' id='btn-cerrar-modal-lista-anim' style='color:#fff; font-size:20px; padding:4px 8px;' aria-label='Cerrar'>" + icon("xmark", 16) + "</button>"
      + "</div>"
      + "<div id='modal-lista-anim-body' style='padding:14px 16px; overflow-y:auto; flex:1; -webkit-overflow-scrolling:touch;'>"
      + "<div style='text-align:center; padding:28px 10px; color:var(--texto-suave);'>"
      + "<div style='font-size:24px; margin-bottom:8px;'>" + icon("hourglass", 24) + "</div>"
      + "Consultando animales activos..."
      + "</div>"
      + "</div>"
      + "</div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById(idModal);
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-modal-lista-anim");
    if (btnC) btnC.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) {
      if (e.target === ov) cerrar();
    });

    fetch(cfg.url)
      .then(function (r) {
        if (!r.ok) throw new Error("Error HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        var body = document.getElementById("modal-lista-anim-body");
        if (!body) return;
        if (!data || !data.ok) {
          body.innerHTML = "<p class='aviso'>" + icon("alertTriangle", 14) + esc((data && data.error) || "No se pudo cargar la información de los animales.") + "</p>";
          return;
        }
        var animales = data.animales || [];
        var total = data.total != null ? data.total : (data.total_animales || animales.length);
        var categorias = data.resumen_categorias || {};

        var catsHtml = "";
        Object.keys(categorias).forEach(function (cat) {
          catsHtml += "<span class='chip' style='font-size:11px; padding:2px 7px; margin-right:4px;'><b>" + esc(cat) + "</b>: " + esc(categorias[cat]) + "</span>";
        });

        var btnMoverLote = cfg.esPotrero && cfg.nombrePotrero
          ? "<button type='button' class='tema-btn' data-accion='capturar-evento' data-tipo='traslado' data-potrero='" + esc(cfg.nombrePotrero) + "' style='font-size:11px; padding:3px 8px; font-weight:700; background:rgba(30,60,114,0.1); color:var(--azul-marca); border:1px solid var(--azul-marca); border-radius:5px; cursor:pointer; display:inline-flex; align-items:center; gap:4px;'>" + icon("truck", 12) + "Trasladar Lote</button>"
          : "";

        var content = "<div class='modal-potrero-kpis' style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px; padding:8px 12px; background:var(--tarjeta-fondo); border-radius:6px; border:1px solid var(--borde);'>"
          + "<div style='display:flex; align-items:center; gap:8px; flex-wrap:wrap;'><b>Total: " + esc(total) + "</b> " + (total === 1 ? "animal activo" : "animales activos") + btnMoverLote + "</div>"
          + "<div style='display:flex; gap:4px; flex-wrap:wrap;'>" + catsHtml + "</div>"
          + "</div>";

        if (!animales.length) {
          content += "<div style='text-align:center; padding:30px 10px; color:var(--texto-suave);'>"
            + "<div style='font-size:28px; margin-bottom:8px;'>" + icon("grass", 28) + "</div>"
            + "No hay animales activos registrados en este grupo actualmente."
            + "</div>";
          body.innerHTML = content;
          return;
        }

        content += "<input type='search' id='filtro-animal-lista' class='modal-potrero-busqueda' placeholder='Filtrar por número, nombre, potrero o categoría...' autocomplete='off' style='width:100%; box-sizing:border-box; margin-bottom:10px; padding:8px 10px; font-size:13px; border-radius:6px; border:1px solid var(--borde-fuerte); background:var(--superficie); color:var(--texto);'>";

        var col5Tit = cfg.esPotrero ? "Días" : "Potrero";

        content += "<div class='tabla-scroll' style='max-height:50vh; overflow-y:auto; overflow-x:hidden;'><table id='tabla-modal-lista' style='width:100%; font-size:12px; border-collapse:collapse; table-layout:fixed;'>"
          + "<thead><tr>"
          + "<th style='width:22%; text-align:left; padding:6px 4px;'>Número</th>"
          + "<th style='width:24%; text-align:left; padding:6px 4px;'>Nombre</th>"
          + "<th style='width:13%; text-align:center; padding:6px 2px;'>Edad</th>"
          + "<th style='width:13%; text-align:center; padding:6px 2px;'>Estado</th>"
          + "<th style='width:14%; text-align:" + (cfg.esPotrero ? "right" : "left") + "; padding:6px 4px;'>" + col5Tit + "</th>"
          + "<th style='width:14%; text-align:center; padding:6px 2px;'>Acción</th>"
          + "</tr></thead>"
          + "<tbody>";

        animales.forEach(function (a) {
          var tagLink = "<a href='#' class='ficha-link' data-ir-ficha='" + esc(a.tag) + "' style='font-weight:700; color:var(--verde-marca); text-decoration:none; display:inline-flex; align-items:center; gap:3px; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;' title='Ver ficha'>"
            + icon(a.sexo === "Macho" ? "bull" : "cow", 12)
            + "<span style='overflow:hidden; text-overflow:ellipsis;'>" + esc(a.tag) + "</span></a>";

          var nomTxt = a.nombre && a.nombre !== a.tag ? esc(a.nombre) : "<span style='color:var(--texto-suave);'>—</span>";
          var edadTxt = a.edad || "—";
          var chipCat = "<span class='chip' style='font-size:10.5px; font-weight:700; padding:2px 4px;' title='" + esc(a.categoria_desc || a.categoria_sg) + (a.estado_reprod ? " · " + esc(a.estado_reprod) : "") + "'>" + esc(a.categoria_sg || "—") + "</span>";

          var col5Val;
          if (cfg.esPotrero) {
            col5Val = a.dias_texto || (a.dias_en_potrero != null ? a.dias_en_potrero + " d" : "—");
          } else {
            col5Val = a.potrero_nombre || "Sin potrero";
          }

          var potFila = a.potrero_nombre || cfg.nombrePotrero || "";
          var accionHtml = "<div style='display:flex; justify-content:center; gap:4px;'>"
            + "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='pesaje' data-tag='" + esc(a.tag) + "' data-potrero='" + esc(potFila) + "' style='padding:2px 5px; cursor:pointer;' title='Pesar'>" + icon("scale", 11) + "</button>"
            + "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='traslado' data-tag='" + esc(a.tag) + "' data-potrero='" + esc(potFila) + "' style='padding:2px 5px; cursor:pointer;' title='Mover'>" + icon("truck", 11) + "</button>"
            + "</div>";

          var bStr = (a.tag + " " + (a.nombre || "") + " " + (a.categoria_sg || "") + " " + (a.categoria_desc || "") + " " + (a.potrero_nombre || "") + " " + (a.estado_reprod || "")).toLowerCase();

          content += "<tr data-busqueda='" + esc(bStr) + "'>"
            + "<td style='padding:6px 4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>" + tagLink + "</td>"
            + "<td style='padding:6px 4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;' title='" + (a.nombre || "") + "'>" + nomTxt + "</td>"
            + "<td style='padding:6px 2px; text-align:center; white-space:nowrap; font-size:11px;'>" + esc(edadTxt) + "</td>"
            + "<td style='padding:6px 2px; text-align:center; white-space:nowrap;'>" + chipCat + "</td>"
            + "<td style='padding:6px 4px; text-align:" + (cfg.esPotrero ? "right" : "left") + "; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11.5px;' title='" + esc(col5Val) + "'>" + esc(col5Val) + "</td>"
            + "<td style='padding:6px 2px; text-align:center; white-space:nowrap;'>" + accionHtml + "</td>"
            + "</tr>";
        });

        content += "</tbody></table></div>";
        content += "<div id='conteo-filtrados-lista' style='margin-top:8px; font-size:11.5px; color:var(--texto-suave); text-align:right;'>Mostrando " + animales.length + " de " + total + "</div>";
        body.innerHTML = content;

        var inputFiltro = document.getElementById("filtro-animal-lista");
        var contadorEl = document.getElementById("conteo-filtrados-lista");
        if (inputFiltro) {
          inputFiltro.addEventListener("input", function () {
            var qVal = (this.value || "").trim().toLowerCase();
            var filas = body.querySelectorAll("tbody tr");
            var visibles = 0;
            filas.forEach(function (tr) {
              var str = tr.getAttribute("data-busqueda") || "";
              if (!qVal || str.indexOf(qVal) >= 0) {
                tr.style.display = "";
                visibles++;
              } else {
                tr.style.display = "none";
              }
            });
            if (contadorEl) {
              contadorEl.textContent = "Mostrando " + visibles + " de " + total;
            }
          });
        }
      })
      .catch(function (err) {
        var body = document.getElementById("modal-lista-anim-body");
        if (body) {
          body.innerHTML = "<p class='aviso'>" + icon("xCircle", 14) + "Error de conexión al consultar animales: " + esc(err.message || err) + "</p>";
        }
      });
  }

  function abrirModalAnimalesPotrero(nomPotrero) {
    if (!nomPotrero) return;
    abrirModalListaAnimales({
      titulo: "Potrero: " + nomPotrero,
      url: "/api/potrero/" + encodeURIComponent(nomPotrero) + "/animales",
      icono: "grass",
      esPotrero: true,
      nombrePotrero: nomPotrero
    });
  }
  window.abrirModalAnimalesPotrero = abrirModalAnimalesPotrero;

  function abrirModalGrupoInventario(tipo, valor, sexo, titulo) {
    if (!tipo || !valor) return;
    var tit = titulo || (tipo === "estructura" ? "Estructura del hato: " + valor : (tipo === "bracket" ? "Categoría de edad: " + valor : valor));
    var url = "/api/inventario/animales?tipo=" + encodeURIComponent(tipo) + "&valor=" + encodeURIComponent(valor);
    if (sexo) url += "&sexo=" + encodeURIComponent(sexo);
    abrirModalListaAnimales({
      titulo: tit,
      url: url,
      icono: tipo === "potrero" ? "grass" : "cow",
      esPotrero: (tipo === "potrero")
    });
  }
  window.abrirModalGrupoInventario = abrirModalGrupoInventario;

  function cargarRondasRecientes() {
    var box = document.getElementById("rondas-recientes");
    if (!box) return;
    fetch("/api/pasturas/rondas")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var filas = (data && data.rondas) || [];
        if (!filas.length) { box.innerHTML = "<span style='color:var(--texto-suave);'>Sin rondas registradas todavía.</span>"; return; }
        box.innerHTML = filas.slice(0, 5).map(function (x) {
          var c = x.semaforo === "VERDE" ? "verde" : x.semaforo === "AMARILLO" ? "ambar" : "rojo";
          return "<span class='chip " + c + "' style='font-size:11px; margin:2px;'>" + esc(x.potrero_nom || "") + " · " + esc(x.fecha) + " · " + esc(x.dias_disponibles) + " d</span>";
        }).join("");
      })
      .catch(function () { box.innerHTML = ""; });
  }

  function bindPasturas() {
    var btnToggleModoPasturas = document.getElementById("btn-toggle-modo-pasturas");
    if (btnToggleModoPasturas) {
      btnToggleModoPasturas.addEventListener("click", function () {
        localStorage.setItem("modoPasturasSimple", modoPasturasEsSimple() ? "tecnico" : "simple");
        cargar(true);
      });
    }
    // D2 — botón del checklist de ronda Voisin + historial reciente.
    var btnRonda = document.getElementById("btn-nueva-ronda");
    if (btnRonda) {
      btnRonda.addEventListener("click", function () { abrirModalRonda(); });
    }
    cargarRondasRecientes();
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
          + "<span style='font-size:22px;'>" + icon("satellite", 22) + "</span>"
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
            box.innerHTML = "<b>" + icon("checkCircle", 14) + esc(data.mensaje || "Sincronización satelital exitosa.") + "</b>"
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
            box.innerHTML = "<b>" + icon("alertTriangle", 14) + "Error:</b> " + esc(data.error || "No se pudo sincronizar");
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
          box.innerHTML = "<b>" + icon("xCircle", 14) + "Error de sincronización satelital:</b> " + esc(err.message || err);
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

    // Selector de pestañas de gráficos en Pasturas (Voisin, Ocupación, Aforo)
    qa(".btn-tab-graf-pasturas").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var g = this.getAttribute("data-graf");
        if (g) {
          _pasturasGraficoActivo = g;
          cargar(true);
        }
      });
    });

    // Botón Aforo Directo desde la tabla de potreros
    qa(".btn-aforar-pot-directo").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pot = this.getAttribute("data-potrero");
        try { localStorage.setItem("bitacora_ultimo_potrero", pot); } catch (ePot) {}
        _tipoCapturaActual = "pesaje"; // o abrir modal de aforo
        irAVista("captura");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eScroll) { window.scrollTo(0, 0); }
      });
    });
  }

  function bindRepro() {
    bindListaTrabajo();
    qa(".btn-ir-cap-directo").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tipo = this.getAttribute("data-tipo");
        if (tipo) {
          _tipoCapturaActual = tipo;
          irAVista("captura");
          cargar(true);
          try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
        }
      });
    });

    qa(".btn-cambiar-estado-pajilla").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = this.getAttribute("data-id");
        var nuevoEstado = this.getAttribute("data-estado");
        if (!id || !nuevoEstado) return;
        var accionTxt = nuevoEstado === "INACTIVO" ? "marcar como inactiva / usada" : "reactivar en el termo";
        if (!confirm("¿Desea " + accionTxt + " esta pajilla?")) return;
        btn.disabled = true;
        fetch("/api/pajillas/estado", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: Number(id), estado: nuevoEstado })
        })
          .then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              mostrarToast(nuevoEstado === "INACTIVO" ? "Pajilla archivada como inactiva" : "Pajilla reactivada en inventario", "verde");
              cargar(false);
            } else {
              mostrarToast(res.error || "No se pudo actualizar el estado", "rojo");
              btn.disabled = false;
            }
          })
          .catch(function () {
            mostrarToast("Error de conexión al actualizar pajilla", "rojo");
            btn.disabled = false;
          });
      });
    });

    var btnNuevoIns = document.getElementById("btn-nuevo-inseminador");
    if (btnNuevoIns) {
      btnNuevoIns.addEventListener("click", function () {
        mostrarModalNuevoInseminador(function () { cargar(true); });
      });
    }

    var btnNuevoLote = document.getElementById("btn-nuevo-lote-iatf");
    if (btnNuevoLote) {
      btnNuevoLote.addEventListener("click", function () {
        mostrarModalNuevoLoteIATF(window.__protocolosIatf || [], function () { cargar(true); });
      });
    }

    var btnVerProts = document.getElementById("btn-ver-protocolos-iatf");
    if (btnVerProts) {
      btnVerProts.addEventListener("click", function () {
        mostrarModalProtocolosInfo(window.__protocolosIatf || []);
      });
    }

    qa(".btn-paso-iatf").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var lid = this.getAttribute("data-lote-id");
        var pidx = this.getAttribute("data-paso-idx");
        if (lid) mostrarModalPasoIATF(Number(lid), Number(pidx || 0), function () { cargar(true); });
      });
    });

    qa(".btn-inseminar-lote-iatf").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var lid = this.getAttribute("data-lote-id");
        if (lid) mostrarModalInseminarLoteIATF(Number(lid), function () { cargar(true); });
      });
    });

    qa(".btn-detalle-lote-iatf").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var lid = this.getAttribute("data-lote-id");
        if (lid) mostrarModalDetalleLoteIATF(Number(lid), function () { cargar(true); });
      });
    });

    var formServ = document.getElementById("form-repro-rango-serv");
    if (formServ && !formServ.__bound) {
      formServ.__bound = true;
      formServ.addEventListener("submit", function (e) {
        e.preventDefault();
        _reproRango.desde = (document.getElementById("repro-serv-desde") || {}).value || null;
        _reproRango.hasta = (document.getElementById("repro-serv-hasta") || {}).value || null;
        cargar(true);
      });
    }
  }

  function fechaDiaSemana(fStr) {
    if (!fStr) return "—";
    try {
      var partes = fStr.split("-");
      if (partes.length === 3) {
        var d = new Date(parseInt(partes[0], 10), parseInt(partes[1], 10) - 1, parseInt(partes[2], 10));
        var dias = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
        var meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
        return dias[d.getDay()] + ", " + d.getDate() + " de " + meses[d.getMonth()];
      }
    } catch (e) { /* fallback */ }
    return fechaCorta(fStr);
  }

  function renderSvgGraficoLeche(serie, promDiario) {
    if (!serie || !serie.length) return "";
    var n = serie.length;
    var maxVal = 0;
    serie.forEach(function (d) { if (d.litros > maxVal) maxVal = d.litros; });
    var yMax = Math.ceil((maxVal * 1.18) / 50) * 50;
    if (yMax <= 0) yMax = 400;

    var w = Math.max(540, n * 36);
    var h = 230;
    var padLeft = 45;
    var padRight = 92;
    var padTop = 26;
    var padBottom = 42;
    var chartW = w - padLeft - padRight;
    var chartH = h - padTop - padBottom;

    var slotW = chartW / n;
    var barWidth = Math.max(14, Math.min(26, slotW * 0.65));

    var svg = "<div style='width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch;'>";
    svg += "<svg viewBox='0 0 " + w + " " + h + "' style='width:100%; min-width:" + (n > 10 ? (n * 32) : 340) + "px; height:auto; display:block; font-family:system-ui,-apple-system,sans-serif;'>";

    var gridSteps = 4;
    for (var g = 0; g <= gridSteps; g++) {
      var yVal = Math.round((yMax / gridSteps) * g);
      var yPos = padTop + chartH - (yVal / yMax) * chartH;
      svg += "<line x1='" + padLeft + "' y1='" + yPos + "' x2='" + (w - padRight) + "' y2='" + yPos + "' stroke='var(--borde)' stroke-width='1' stroke-dasharray='" + (g === 0 ? "none" : "3,3") + "' />";
      svg += "<text x='" + (padLeft - 6) + "' y='" + (yPos + 4) + "' fill='var(--texto-suave)' font-size='10' text-anchor='end'>" + yVal + "</text>";
    }

    if (promDiario > 0 && promDiario <= yMax) {
      var yProm = padTop + chartH - (promDiario / yMax) * chartH;
      svg += "<line x1='" + padLeft + "' y1='" + yProm + "' x2='" + (w - padRight) + "' y2='" + yProm + "' stroke='#D97706' stroke-width='1.8' stroke-dasharray='4,3' />";
      // Etiqueta del promedio en el margen derecho, FUERA del área de barras:
      // antes se dibujaba encima de las últimas columnas y tapaba sus valores.
      svg += "<rect x='" + (w - padRight + 5) + "' y='" + (yProm - 9) + "' width='84' height='17' rx='3' fill='#D97706' />";
      svg += "<text x='" + (w - padRight + 47) + "' y='" + (yProm + 3) + "' fill='#FFFFFF' font-size='9' font-weight='bold' text-anchor='middle'>Prom " + promDiario + " L/d</text>";
    }

    serie.forEach(function (d, i) {
      var xCenter = padLeft + (i + 0.5) * slotW;
      var xBar = xCenter - barWidth / 2;
      var barH = Math.max(4, (d.litros / yMax) * chartH);
      var yBar = padTop + chartH - barH;
      var esPico = (d.litros === maxVal);
      var colorBarra = esPico ? "#15803D" : "var(--verde-marca)";

      var diff = d.diff_promedio != null ? d.diff_promedio : Math.round((d.litros - promDiario) * 10) / 10;
      var diffSign = diff >= 0 ? "+" : "";
      var tooltip = esc(fechaDiaSemana(d.fecha)) + ": " + d.litros + " L (" + diffSign + diff + " L vs prom)";

      svg += "<rect x='" + xBar + "' y='" + yBar + "' width='" + barWidth + "' height='" + barH + "' rx='3' fill='" + colorBarra + "' opacity='0.92'>";
      svg += "<title>" + tooltip + "</title>";
      svg += "</rect>";

      svg += "<text x='" + xCenter + "' y='" + (yBar - 5) + "' fill='" + (esPico ? "#15803D" : "var(--texto)") + "' font-size='" + (barWidth < 18 ? "8.5" : "9.5") + "' font-weight='" + (esPico ? "bold" : "600") + "' text-anchor='middle'>" + Math.round(d.litros) + "</text>";

      var labelFecha = "";
      try {
        var p = d.fecha.split("-");
        labelFecha = p[2] + "/" + p[1];
      } catch (ex) { labelFecha = d.fecha; }

      svg += "<text x='" + xCenter + "' y='" + (h - padBottom + 16) + "' fill='var(--texto-suave)' font-size='9.5' font-weight='500' text-anchor='middle' transform='rotate(35 " + xCenter + " " + (h - padBottom + 16) + ")'>" + labelFecha + "</text>";
    });

    svg += "</svg></div>";
    return svg;
  }

  // Lote de ordeño: define qué vacas se cuentan en ordeño (Secar, ficha,
  // litros/vaca). Se detecta solo donde están las recién paridas; aquí se
  // corrige tocando el potrero (Automático → Sí → No).
  var LOTE_MODO = { manual: "fijado a mano", nombre: "por el nombre", auto: "hay recién paridas", no: "" };
  function renderLotesOrdeno(lotes) {
    if (!lotes || !lotes.length) return "";
    var h = "<div class='card'><h4 style='margin:0 0 6px;'>" + icon("milk", 16) + "Lote de ordeño</h4>"
      + "<p class='aviso' style='margin:0 0 8px;'>Solo las vacas de los potreros marcados cuentan como <b>en ordeño</b> "
      + "(lista Secar, ficha y litros/vaca). Las demás paridas se toman como secas. Toque un potrero para corregirlo.</p>"
      + "<div class='gen-filtros'>";
    lotes.forEach(function (p) {
      h += "<button type='button' class='chip btn-lote-ordeno" + (p.ordeno ? " act" : "") + "' data-pid='" + esc(p.id)
        + "' data-modo='" + esc(p.modo) + "' data-ordeno='" + (p.ordeno ? 1 : 0) + "' title='" + esc(LOTE_MODO[p.modo] || "") + "'>"
        + (p.ordeno ? icon("milk", 12) : "") + esc(p.nombre) + " · " + esc(p.vacas_paridas) + " paridas"
        + (p.modo === "manual" ? " " + icon("pin", 12) : "") + "</button>";
    });
    return h + "</div><small>" + icon("pin", 12) + "= fijado a mano. Toque: automático → sí es ordeño → no es ordeño.</small></div>";
  }
  function bindLotesOrdeno() {
    qa(".btn-lote-ordeno").forEach(function (b) {
      b.addEventListener("click", function () {
        var modo = b.getAttribute("data-modo"), ordeno = b.getAttribute("data-ordeno") === "1";
        // Ciclo: automático -> fijo sí -> fijo no -> automático
        var valor = modo !== "manual" ? true : (ordeno ? false : null);
        b.disabled = true;
        fetch("/api/potrero/" + b.getAttribute("data-pid") + "/ordeno", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ valor: valor })
        }).then(function (r) { return r.json(); }).then(function (res) {
          if (!res.ok) { alert(res.error || "No se pudo guardar."); b.disabled = false; return; }
          cargar(true);
        }).catch(function () { alert("Sin conexión."); b.disabled = false; });
      });
    });
  }

  // Control lechero (AM + PM, mensual): captura en el corral y resumen del
  // último control con listas para actuar (engine/control_lechero.py).
  function renderControlLechero(cl) {
    if (!cl) return "";
    var vacas = cl.vacas || [], r = cl.resumen || {}, u = r.ultimo;
    var h = "<div class='card' id='card-control-lechero'><h4 style='margin:0 0 6px;'>" + icon("milk", 16) + "Control lechero</h4>";
    if (u) {
      h += "<p style='margin:0 0 8px; font-size:13px;'>Último control <b>" + esc(fechaCorta(u.fecha)) + "</b>: "
        + esc(u.vacas) + " vacas · <b>" + esc(u.promedio) + " L/vaca</b> · total " + esc(u.total_litros) + " L"
        + (u.tanque_litros ? " (tanque " + esc(u.tanque_litros) + " L, " + esc(u.cobertura_pct) + " %)" : "") + "</p>";
    } else {
      h += "<p class='aviso' style='margin:0 0 8px;'>Todavía no hay controles por vaca. Un control al mes (ordeño de la mañana y de la tarde) da el promedio real por vaca, la curva de lactancia y avisa las vacas que bajan.</p>";
    }
    h += "<button type='button' class='tema-btn' id='btn-hacer-control'" + (vacas.length ? "" : " disabled") + ">"
      + "Hacer control (" + vacas.length + " vacas en ordeño)</button>";
    h += "<div id='control-captura' hidden style='margin-top:10px;'>"
      + "<label style='font-size:13px;'>Fecha del control <input type='date' id='control-fecha' value='" + new Date().toISOString().slice(0, 10) + "'></label>"
      + "<p style='font-size:12px; color:var(--texto-suave); margin:6px 0;'>Litros por vaca. Deje vacío si no se ordeñó.</p>";
    var porPot = {}, pots = [];
    vacas.forEach(function (v) { if (!porPot[v.potrero]) { porPot[v.potrero] = []; pots.push(v.potrero); } porPot[v.potrero].push(v); });
    pots.forEach(function (p) {
      h += "<div style='font-weight:700; margin:10px 0 4px;'>" + esc(p) + " · " + porPot[p].length + "</div>";
      porPot[p].forEach(function (v) {
        h += "<div class='fila-control' data-tag='" + esc(v.tag) + "' style='display:grid; grid-template-columns:1fr 72px 72px; gap:6px; align-items:center; padding:4px 0; border-bottom:1px solid var(--borde);'>"
          + "<span>" + enlaceFicha(v.tag) + (v.pausada ? " <small>(pausada)</small>" : "") + "<br><small>" + esc(v.del_dias) + " DEL"
          + (v.ultimo_litros != null ? " · antes " + esc(v.ultimo_litros) + " L" : "") + "</small></span>"
          + "<input type='number' inputmode='decimal' step='0.1' min='0' class='ctrl-am' placeholder='AM' aria-label='Litros mañana " + esc(v.tag) + "' style='min-height:44px; font-size:16px;'>"
          + "<input type='number' inputmode='decimal' step='0.1' min='0' class='ctrl-pm' placeholder='PM' aria-label='Litros tarde " + esc(v.tag) + "' style='min-height:44px; font-size:16px;'>"
          + "</div>";
      });
    });
    h += "<p id='control-total' style='font-weight:700; margin:10px 0;'>Total: 0 L · 0 vacas</p>"
      + "<button type='button' class='tema-btn' id='btn-guardar-control'>Guardar control</button></div>";
    var listas = [["caida", icon("trendDown", 14) + "Caída fuerte (posible mastitis)"], ["baja_produccion", icon("trendDown", 14) + "Baja producción"], ["sin_control", icon("clock", 14) + "Sin control"]];
    if (r.top && r.top.length) {
      h += "<div style='margin-top:10px;'><b>" + icon("award", 14) + "Mejores</b> " + r.top.map(function (t) { return enlaceFicha(t.tag) + " " + esc(t.litros) + " L"; }).join(" · ") + "</div>";
    }
    listas.forEach(function (par) {
      var filas = r[par[0]] || [];
      if (!filas.length) return;
      h += "<details style='margin-top:8px;'><summary><b>" + par[1] + " · " + filas.length + "</b></summary>"
        + filas.slice(0, 30).map(function (f) {
          return "<div class='fila-pes'><span>" + enlaceFicha(f.tag) + (f.nombre ? " <small>" + esc(f.nombre) + "</small>" : "")
            + "</span><small>" + esc(f.motivo || "") + "</small></div>";
        }).join("") + "</details>";
    });
    return h + "</div>";
  }
  function bindControlLechero() {
    var btn = document.getElementById("btn-hacer-control"), cap = document.getElementById("control-captura");
    if (!btn || !cap) return;
    btn.addEventListener("click", function () { cap.hidden = !cap.hidden; });
    function num(inp) { var v = parseFloat(String(inp.value || "").replace(",", ".")); return isNaN(v) || v < 0 ? null : v; }
    function recalcular() {
      var total = 0, n = 0;
      cap.querySelectorAll(".fila-control").forEach(function (f) {
        var am = num(f.querySelector(".ctrl-am")), pm = num(f.querySelector(".ctrl-pm"));
        if (am !== null || pm !== null) { n++; total += (am || 0) + (pm || 0); }
      });
      document.getElementById("control-total").textContent = "Total: " + (Math.round(total * 10) / 10) + " L · " + n + " vacas";
    }
    cap.addEventListener("input", recalcular);
    document.getElementById("btn-guardar-control").addEventListener("click", function () {
      var regs = [];
      cap.querySelectorAll(".fila-control").forEach(function (f) {
        var am = num(f.querySelector(".ctrl-am")), pm = num(f.querySelector(".ctrl-pm"));
        if (am !== null || pm !== null) regs.push({ tag: f.getAttribute("data-tag"), am: am, pm: pm });
      });
      if (!regs.length) { mostrarToast("Anote los litros de al menos una vaca.", "ambar"); return; }
      var b = this, fecha = document.getElementById("control-fecha").value;
      b.disabled = true;
      var ev = { tipo: "control_leche", payload: { registros: regs }, fecha: fecha };
      var envio = navigator.onLine === false ? encolarOffline(ev.tipo, ev.payload, fecha)
        : fetch("/api/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ eventos: [ev] }) })
          .then(function (r) { return r.json(); })
          .then(function (res) { if (!(res.ok && res.procesados > 0)) return encolarOffline(ev.tipo, ev.payload, fecha); })
          .catch(function () { return encolarOffline(ev.tipo, ev.payload, fecha); });
      Promise.resolve(envio).then(function () {
        mostrarToast("Control guardado: " + regs.length + " vacas.", "verde");
        vibrarConfirmacion();
        cargar(true);
      });
    });
  }

  function renderLeche(d) {
    var serie = d.serie_tanque || [];
    var res = d.resumen || {};
    var totalLitros = res.total_litros || 0;
    var diasCount = res.dias || serie.length;
    var promDiario = res.promedio_diario || (diasCount ? Math.round((totalLitros / diasCount) * 10) / 10 : 0);
    var pico = res.pico_max || (serie.length ? serie.reduce(function (m, it) { return (it.litros > m.litros) ? it : m; }, serie[0]) : null);
    var piso = res.piso_min || (serie.length ? serie.reduce(function (m, it) { return (it.litros < m.litros) ? it : m; }, serie[0]) : null);
    var ord = d.resumen_ordeno || {};
    var litrosPorVaca = res.litros_por_vaca_dia;

    var btnIa = "<button type='button' class='tema-btn' id='btn-ir-captura-leche' style='float:right; font-size:12px; padding:6px 14px; margin-top:-4px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:6px;'>"
      + icon("sparkles", 14) + "Digitalizar Recibo con IA</button>";

    var h = "<div class='leche-head-barra' style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:14px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("milk", 22) + "Producción de Leche (Total Diario · Finca)</h3>"
      + "<div style='display:flex; align-items:center; gap:8px; flex-wrap:wrap;'>"
      + barraDescargaSeccion("leche", "Leche")
      + btnIa
      + "</div>"
      + "</div>" + erroresHtml(d);
    h += renderListaTrabajo(d.tareas, ltClaves("leche"), "Lista de trabajo · Leche");
    h += renderLotesOrdeno(d.lotes_ordeno);
    h += renderControlLechero(d.control_lechero);
    if (d.tareas && d.tareas.conteos && !d.tareas.conteos.secar && d.tareas.conteos.chequeo) {
      h += "<p class='aviso'>" + icon("alertTriangle", 14) + "Las preñeces no están al día (" + esc(d.tareas.conteos.chequeo) + " vacas sin dato reciente): haz el <b>chequeo del hato</b> en Reproducción para que aparezcan las vacas a secar.</p>";
    }

    // 1. KPIs Ejecutivos de Producción
    h += "<div class='kpis'>"
      + kpiIr(kpi(totalLitros.toLocaleString("es-CO") + " L", "Total período (" + diasCount + " días)", "ok"), { sec: "Detalle de Entregas Diarias" })
      + kpiIr(kpi(promDiario.toLocaleString("es-CO") + " L/d", "Promedio diario", "ok"), { sec: "Curva de Producción Diaria" })
      + (pico ? kpiIr(kpi(pico.litros + " L", "Pico más alto (" + fechaCorta(pico.fecha) + ")"), { sec: "Curva de Producción Diaria" }) : "")
      + (piso ? kpiIr(kpi(piso.litros + " L", "Piso más bajo (" + fechaCorta(piso.fecha) + ")"), { sec: "Curva de Producción Diaria" }) : "")
      + (litrosPorVaca != null ? kpiIr(kpi(litrosPorVaca.toLocaleString("es-CO") + " L", "Promedio litros/vaca/día"), { sec: "Vacas paridas" }) : "")
      + "</div>";

    // 1b. Vacas en ordeño vs realmente ordeñándose -- el "litros/vaca/día"
    // de arriba se calcula dividiendo entre "ordenandose" (en ordeño menos
    // las que están en pausa), no entre el total en ordeño.
    h += "<div class='card' style='padding:14px 16px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;'>"
      + "<div style='display:flex; align-items:center; gap:8px; font-size:13.5px; font-weight:600;'>" + icon("cowCalf", 16) + "Vacas paridas</div>"
      + "<div style='display:flex; gap:16px; flex-wrap:wrap; align-items:center; font-size:12.5px;'>"
      + "<span><b>" + (ord.en_ordeno || 0) + "</b> paridas</span>"
      + "<span style='color:var(--verde-marca); font-weight:700;'>Ordeñándose: " + (ord.ordenandose || 0) + "</span>"
      + "<span style='color:var(--color-ambar-txt, #D97706); font-weight:700;'>En pausa: " + (ord.en_pausa || 0) + "</span>"
      + "</div>"
      + "</div>";

    // 1c. Análisis de DEL (Días En Leche) y Etapas de Lactancia (Software Ganadero)
    var delInfo = d.analisis_del || {};
    if (delInfo.total_vacas > 0) {
      h += "<div class='card' style='padding:14px 16px; margin-bottom:16px; background:var(--superficie); border-left:4px solid var(--verde-marca);'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;'>"
        + "<div>"
        + "<div style='font-size:13.5px; font-weight:700; display:flex; align-items:center; gap:6px;'>" + icon("milk", 16) + "Días En Leche (DEL) &amp; Curva de Lactancia</div>"
        + "<small style='color:var(--texto-suave); font-size:11.5px;'>Promedio del lote activo: <b>" + delInfo.promedio_del + " días</b> (" + delInfo.total_vacas + " vacas evaluadas)</small>"
        + "</div>"
        + "</div>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:8px;'>";
      (delInfo.etapas || []).forEach(function (et) {
        h += "<div style='background:rgba(0,0,0,0.03); border:1px solid var(--borde-suave); border-radius:8px; padding:10px; text-align:center;'>"
          + "<div style='font-size:11.5px; font-weight:600; color:var(--texto-suave);'>" + esc(et.etapa) + "</div>"
          + "<div style='font-size:18px; font-weight:800; color:var(--texto); margin:2px 0;'>" + et.cantidad + "</div>"
          + "<div style='font-size:11px; font-weight:600; color:var(--verde-marca);'>" + et.pct + "%</div>"
          + "</div>";
      });
      h += "</div></div>";
    }

    // 2. Gráfico Interactivo de Producción Diaria (SVG responsivo)
    h += "<div class='tarjeta-leche-grafico' style='background:var(--superficie); border:1px solid var(--borde); border-radius:10px; padding:16px; margin:16px 0; box-shadow:0 1px 4px var(--sombra);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
      + "<div>"
      + "<div style='font-size:14.5px; font-weight:700; color:var(--texto); display:flex; align-items:center; gap:6px;'>"
      + icon("chartBar", 18) + "Curva de Producción Diaria de Leche (Tanque / Recibos)"
      + "</div>"
      + "<small style='color:var(--texto-suave); font-size:11.5px; display:block; margin-top:2px;'>Litros entregados por día según el recibo de leche o planilla de acopio</small>"
      + "</div>"
      + "<div style='display:flex; align-items:center; gap:12px; font-size:11.5px;'>"
      + "<span style='display:inline-flex; align-items:center; gap:5px;'><span style='display:inline-block; width:12px; height:12px; background:var(--verde-marca); border-radius:2px;'></span> Litros/día</span>"
      + "<span style='display:inline-flex; align-items:center; gap:5px;'><span style='display:inline-block; width:14px; height:2px; background:#D97706; border-top:2px dashed #D97706;'></span> Promedio (" + promDiario + " L)</span>"
      + "</div>"
      + "</div>";

    if (serie.length > 0) {
      h += renderSvgGraficoLeche(serie, promDiario);
    } else {
      h += "<p class='aviso' style='margin:12px 0;'>No hay registros de producción de leche cargados en este período. Escanea un recibo con el botón superior para comenzar.</p>";
    }
    h += "</div>";

    // 3. Gráfico de Respaldo / Exportación del Servidor
    var tNow = Date.now();
    h += "<details style='margin-bottom:18px;'>"
      + "<summary style='cursor:pointer; font-size:12.5px; font-weight:600; color:var(--texto-suave); padding:4px 0;'>" + icon("image", 14) + " Ver gráfico generado por servidor (Matplotlib)</summary>"
      + "<div class='grafico-wrap' style='margin-top:8px;'><img src='/api/grafico/leche_total?t=" + tNow + "' alt='Gráfico Producción Total de Leche' loading='lazy'></div>"
      + "</details>";

    // 4. Tabla Detallada Día a Día
    h += "<h4>" + icon("calendar", 16) + "Detalle de Entregas Diarias al Acopiador</h4>";
    if (serie.length > 0) {
      h += "<div style='overflow-x:auto; -webkit-overflow-scrolling:touch; margin-top:8px;'>"
        + "<table class='tabla' style='width:100%; border-collapse:collapse; font-size:12.5px;'>"
        + "<thead><tr style='background:rgba(47,82,51,0.08);'>"
        + "<th style='text-align:left; padding:8px 10px;'>Fecha</th>"
        + "<th style='text-align:right; padding:8px 10px;'>Litros Diarios</th>"
        + "<th style='text-align:center; padding:8px 10px;'>vs Promedio (" + promDiario + " L)</th>"
        + "<th style='text-align:left; padding:8px 10px;'>Respaldo / Notas</th>"
        + "</tr></thead><tbody>";

      var serieDesc = serie.slice().reverse();
      serieDesc.forEach(function (dia) {
        var diff = dia.diff_promedio != null ? dia.diff_promedio : Math.round((dia.litros - promDiario) * 10) / 10;
        var diffTxt = (diff >= 0 ? "+" : "") + diff + " L";
        var diffChip = diff >= 0
          ? "<span class='chip verde' style='font-size:11px; font-weight:700;'>" + diffTxt + "</span>"
          : "<span class='chip ambar' style='font-size:11px; font-weight:700;'>" + diffTxt + "</span>";

        h += "<tr style='border-bottom:1px solid var(--borde);'>"
          + "<td style='padding:8px 10px; font-weight:600; white-space:nowrap;'>" + esc(fechaDiaSemana(dia.fecha)) + "</td>"
          + "<td style='text-align:right; padding:8px 10px; font-weight:700; font-size:13px; color:var(--texto);'>" + dia.litros.toLocaleString("es-CO") + " L</td>"
          + "<td style='text-align:center; padding:8px 10px;'>" + diffChip + "</td>"
          + "<td style='padding:8px 10px; color:var(--texto-suave); font-size:12px;'>" + esc(dia.notas || "Recibo de quincena") + "</td>"
          + "</tr>";
      });
      h += "</tbody></table></div>";
    } else {
      h += "<p class='aviso'>Sin registros de entregas de leche en el período.</p>";
    }

    // 5. Galería de Fotos de Recibos y Planillas
    if (d.fotos_recibos && d.fotos_recibos.length) {
      h += "<details style='margin-top:20px;' open>"
        + "<summary style='cursor:pointer; font-weight:700; font-size:13.5px; padding:8px 0; display:flex; align-items:center; gap:6px;'>"
        + icon("camera", 16) + "Recibos y Planillas de Quincena (Fotos de Respaldo) — " + d.fotos_recibos.length + "</summary>"
        + "<p class='aviso' style='margin:6px 0 10px 0;'>Fotos de los recibos de leche o planillas manuales. Toca cualquier imagen para abrirla en pantalla completa con zoom táctil y verificar las anotaciones diarias.</p>"
        + "<div class='fotos-wrap' style='display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:10px;'>";
      d.fotos_recibos.forEach(function (f) {
        var ruta = f.ruta ? (f.ruta.startsWith("/") ? f.ruta : "/" + f.ruta) : "";
        h += "<div class='foto-card' style='border:1px solid var(--borde-suave); border-radius:8px; overflow:hidden; background:var(--superficie); padding:6px; box-shadow:0 1px 3px var(--sombra);'>"
          + "<div style='aspect-ratio:4/3; overflow:hidden; border-radius:6px; background:#111; display:flex; align-items:center; justify-content:center; cursor:pointer;'>"
          + "<img src='" + esc(ruta) + "' alt='" + esc(f.caption || "Recibo de leche") + "' class='zoomable-img' style='width:100%; height:100%; object-fit:cover;'>"
          + "</div>"
          + "<div style='font-size:11px; font-weight:600; margin-top:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>" + esc(f.caption || "Recibo") + "</div>"
          + "<div style='font-size:10px; color:var(--texto-suave);'>" + esc(fechaCorta(f.fecha)) + "</div>"
          + "</div>";
      });
      h += "</div></details>";
    }

    // 6. Sección Histórica Archivado (Software Ganadero 2016-2018)
    if (d.total_historico_sg && d.total_historico_sg > 0) {
      h += "<details style='margin-top:20px; opacity:0.85;'>"
        + "<summary style='cursor:pointer; font-size:12px; color:var(--texto-suave); padding:6px 0;'>"
        + icon("archive", 14) + " Archivo histórico de controles individuales (" + d.total_historico_sg + " registros 2016-2018)"
        + "</summary>"
        + "<p class='aviso' style='font-size:11.5px; margin:6px 0;'>Estos registros corresponden a pesajes individuales antiguos por vaca importados del sistema anterior (2016-2018). Se mantienen preservados en la base de datos histórica sin alterar los totales ni gráficos de la producción actual de la finca.</p>"
        + "</details>";
    }

    return h;
  }

  function bindLeche() {
    bindListaTrabajo();
    bindLotesOrdeno();
    bindControlLechero();
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

