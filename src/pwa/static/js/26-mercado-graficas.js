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
        badgePlaza = " <span class='chip verde' style='font-size:10px; font-weight:700;'>" + icon("pin", 12) + "Plaza Local Finca</span>";
      } else if (esTop) {
        badgePlaza = " <span class='chip ambar' style='font-size:10px; font-weight:700;'>" + icon("crown", 12) + "Mayor Precio</span>";
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
      var flechaTend = resTend.tendencia === "SUBIENDO" ? icon("trendUp", 14) : (resTend.tendencia === "BAJANDO" ? icon("trendDown", 14) : icon("chartBar", 14));
      var dirTxt = resTend.tendencia === "SUBIENDO" ? "ALCISTA" : (resTend.tendencia === "BAJANDO" ? "BAJISTA" : "ESTABLE");
      insightHtml = "<div class='mercado-insight-box'>"
        + "<div><b>" + flechaTend + "Interpretación de Mercado (" + esc(etiquetaMercado(cat)) + "):</b></div>"
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
      + grafico("subastas_comparativa", "Comparativa de Subastas Ganadería JA")
      + grafico("subastas_tendencia", "Tendencia Semanal Subastas Ganadería JA")
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
      ? "<div class='chip ambar' style='margin-bottom:10px;'>" + icon("alertTriangle", 12) + "Datos de referencia de jul-sep 2026. Actualiza con el botón Sincronizar.</div>"
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

