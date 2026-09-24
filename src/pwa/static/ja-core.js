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
    // (P2.11) Se EXTRAE el emoji semáforo inicial y se escapa SIEMPRE el resto:
    // antes se inyectaba crudo cualquier string que empezara con emoji, lo que
    // abría una vía de inyección de HTML desde datos de la BD (p. ej. un
    // resultado de diagnóstico manipulado).
    var colores = [["🟢", "verde"], ["🟡", "ambar"], ["🔴", "rojo"], ["⚪", "gris"]];
    for (var i = 0; i < colores.length; i++) {
      var emoji = colores[i][0];
      if (t.indexOf(emoji) === 0) {
        var resto = t.slice(emoji.length).replace(/^\s+/, "");
        return "<span class='chip " + colores[i][1] + "'>" + emoji + (resto ? " " + esc(resto) : "") + "</span>";
      }
    }
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
  function fechaCorta(v) { return v ? String(v).slice(0, 10) : ""; }
  function fmtMoneda(n) {
    var v = Number(n) || 0;
    return "$" + Math.round(v).toLocaleString("es-CO");
  }

  // ------------------------------------------------------------------ //
  // Motor de Gráficos Vectoriales SVG Nativos Adaptados a Temas (PWA)
  // ------------------------------------------------------------------ //
  function grafico(tipo, alt, datosDirectos) {
    var idUnico = "grafico-box-" + String(tipo || "").replace(/[^a-zA-Z0-9_-]/g, "") + "-" + Math.random().toString(36).substring(2, 7);
    var tNow = Date.now();
    var datosJsonAttr = datosDirectos ? " data-datos-inline='" + esc(JSON.stringify(datosDirectos)) + "'" : "";

    var h = "<div class='tarjeta-grafico-ja' id='" + idUnico + "' data-chart-tipo='" + esc(tipo) + "' data-chart-alt='" + esc(alt) + "'" + datosJsonAttr + " style='background:var(--superficie); border:1px solid var(--borde); border-radius:10px; padding:14px; margin:16px 0; box-shadow:0 1px 4px var(--sombra);'>"
      + "<div class='grafico-header-ja' style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
      + "<div>"
      + "<div style='font-size:14px; font-weight:700; color:var(--texto); display:flex; align-items:center; gap:6px;'>"
      + icon("chartBar", 16) + "<span>" + esc(alt) + "</span>"
      + "</div>"
      + "<small class='grafico-sub-info' style='color:var(--texto-suave); font-size:11.5px; display:block; margin-top:2px;'>Visualización vectorial interactiva · adaptada al tema activo</small>"
      + "</div>"
      + "<div style='display:flex; align-items:center; gap:6px;'>"
      + "<span class='chip' style='font-size:11px; padding:2px 8px; border-radius:12px; background:rgba(46,125,50,0.1); color:var(--verde-marca); font-weight:600;'>Vectorial Interactivo</span>"
      + "</div>"
      + "</div>";

    // Contenedor interactivo (SVG nativo responsivo)
    h += "<div class='grafico-svg-target' style='width:100%; min-height:160px;'>"
      + "<div style='text-align:center; padding:28px 10px; color:var(--texto-suave); font-size:12px;'>"
      + "<div style='font-size:20px; margin-bottom:6px;'>⏳</div>Cargando visualización..."
      + "</div>"
      + "</div>";

    // Opción desplegable dual con Matplotlib (igual que en Leche)
    h += "<details class='grafico-details-servidor' style='margin-top:12px; border-top:1px dashed var(--borde); padding-top:6px;'>"
      + "<summary style='cursor:pointer; font-size:12px; font-weight:600; color:var(--texto-suave); padding:4px 0; display:inline-flex; align-items:center; gap:5px;'>"
      + icon("image", 13) + "Ver gráfico original del servidor (Matplotlib PNG)"
      + "</summary>"
      + "<div class='grafico-wrap' style='margin-top:8px; border:none; padding:0; background:transparent;'><img src='/api/grafico/" + tipo + "?t=" + tNow + "' alt='" + esc(alt) + "' loading='lazy' data-onerror-hide='self'></div>"
      + "</details>";

    h += "</div>";
    return h;
  }

  function renderSvgEvolucion(d) {
    var series = (d && d.series) || [];
    if (!series.length) return vacio("Sin datos de evolución para graficar.");
    var n = series.length;
    var maxVal = 1;
    var maxNivel = 1;
    series.forEach(function (s) {
      var m = Math.max(s.nacimientos || 0, s.compras || 0, s.ventas || 0, s.muertes || 0);
      if (m > maxVal) maxVal = m;
      if ((s.inventario || 0) > maxNivel) maxNivel = s.inventario;
    });
    var yMaxBarras = Math.ceil(maxVal * 1.2) || 10;
    var yMaxNivel = Math.ceil(maxNivel * 1.15) || 400;

    var w = Math.max(520, n * 44);
    var h = 250;
    var padL = 38, padR = 44, padT = 26, padB = 48;
    var chW = w - padL - padR;
    var chH = h - padT - padB;
    var slotW = chW / n;

    var svg = "<div style='width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch;'>";
    svg += "<svg viewBox='0 0 " + w + " " + h + "' style='width:100%; min-width:480px; height:auto; display:block; font-family:var(--font-base,sans-serif);'>";

    // Grid horizontal
    for (var g = 0; g <= 4; g++) {
      var yP = padT + chH - (g / 4) * chH;
      var valB = Math.round((yMaxBarras / 4) * g);
      var valN = Math.round((yMaxNivel / 4) * g);
      svg += "<line x1='" + padL + "' y1='" + yP + "' x2='" + (w - padR) + "' y2='" + yP + "' stroke='var(--borde)' stroke-width='1' stroke-dasharray='" + (g === 0 ? "none" : "3,3") + "' />";
      svg += "<text x='" + (padL - 6) + "' y='" + (yP + 3.5) + "' fill='var(--texto-suave)' font-size='9' text-anchor='end'>" + valB + "</text>";
      svg += "<text x='" + (w - padR + 6) + "' y='" + (yP + 3.5) + "' fill='#d97706' font-size='9' text-anchor='start'>" + valN + "</text>";
    }

    // Leyenda superior (con 'Nacimientos (crías)' explícito para total claridad)
    svg += "<g transform='translate(" + padL + ", 12)' font-size='9' font-weight='600'>"
      + "<rect x='0' y='-8' width='9' height='9' rx='2' fill='var(--verde-marca)' /><text x='13' y='0' fill='var(--texto)'>Nacimientos (crías)<title>Nacimientos: crías nacidas registradas en la finca durante el mes</title></text>"
      + "<rect x='114' y='-8' width='9' height='9' rx='2' fill='#66bb6a' /><text x='127' y='0' fill='var(--texto)'>Compras</text>"
      + "<rect x='184' y='-8' width='9' height='9' rx='2' fill='#8d6e63' /><text x='197' y='0' fill='var(--texto)'>Ventas</text>"
      + "<rect x='248' y='-8' width='9' height='9' rx='2' fill='#ef5350' /><text x='261' y='0' fill='var(--texto)'>Muertes</text>"
      + "<circle cx='318' cy='-3.5' r='3.5' fill='#d97706' /><line x1='310' y1='-3.5' x2='326' y2='-3.5' stroke='#d97706' stroke-width='2' /><text x='332' y='0' fill='#d97706'>Inventario</text>"
      + "</g>";

    // Puntos para la línea de inventario
    var puntosNivel = [];

    series.forEach(function (s, i) {
      var xCenter = padL + (i + 0.5) * slotW;
      var bW = Math.max(5, Math.min(8, slotW * 0.2));

      // 4 barras por mes
      var tiposB = [
        { v: s.nacimientos || 0, c: "var(--verde-marca)", n: "Nacimientos" },
        { v: s.compras || 0, c: "#66bb6a", n: "Compras" },
        { v: s.ventas || 0, c: "#8d6e63", n: "Ventas" },
        { v: s.muertes || 0, c: "#ef5350", n: "Muertes" }
      ];

      tiposB.forEach(function (tb, bi) {
        var bH = (tb.v / yMaxBarras) * chH;
        var bX = xCenter + (bi - 1.5) * (bW + 2) - bW / 2;
        var bY = padT + chH - bH;
        if (tb.v > 0) {
          svg += "<rect x='" + bX + "' y='" + bY + "' width='" + bW + "' height='" + bH + "' rx='2' fill='" + tb.c + "'>"
            + "<title>" + esc(s.mes) + " · " + tb.n + ": " + tb.v + "</title></rect>";
        }
      });

      // Punto inventario
      var yNiv = padT + chH - ((s.inventario || 0) / yMaxNivel) * chH;
      puntosNivel.push({ x: xCenter, y: yNiv, val: s.inventario, mes: s.mes });

      // Etiqueta eje X compacta (rotada -45° con año corto ej. "Sep '25" para eliminar solapamientos)
      var lblCorto = s.mes || "";
      var partesMes = String(s.mes || "").trim().split(/\s+/);
      if (partesMes.length >= 2) {
        lblCorto = partesMes[0] + " '" + partesMes[1].slice(-2);
      }
      var yLbl = padT + chH + 8;
      svg += "<g transform='translate(" + (xCenter - 1) + "," + yLbl + ") rotate(-45)'><text x='0' y='0' fill='var(--texto-suave)' font-size='8' font-weight='500' text-anchor='end'>" + esc(lblCorto) + "<title>" + esc(s.mes) + "</title></text></g>";
    });

    // Dibujar línea de inventario
    if (puntosNivel.length > 1) {
      var pathD = "M " + puntosNivel.map(function (p) { return p.x + " " + p.y; }).join(" L ");
      svg += "<path d='" + pathD + "' fill='none' stroke='#d97706' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' />";
      puntosNivel.forEach(function (p, idx) {
        svg += "<circle cx='" + p.x + "' cy='" + p.y + "' r='3.5' fill='#d97706' stroke='var(--superficie)' stroke-width='1.5'>"
          + "<title>" + esc(p.mes) + " · Inventario: " + p.val + " cabezas</title></circle>";
        if (idx === puntosNivel.length - 1 || idx === 0) {
          svg += "<text x='" + p.x + "' y='" + (p.y - 7) + "' fill='#d97706' font-size='9' font-weight='700' text-anchor='middle'>" + p.val + "</text>";
        }
      });
    }

    svg += "</svg></div>";
    return svg;
  }

  function renderSvgRepro(d) {
    var cats = (d && d.categorias) || [];
    var total = (d && d.total_hembras) || 0;
    var tasa = (d && d.tasa_prenez) || 0;
    if (!cats.length) return vacio("Sin datos reproductivos.");

    var h = "<div style='display:flex; flex-direction:column; gap:12px;'>";
    h += "<div style='display:flex; justify-content:space-between; align-items:center; padding:8px 12px; background:var(--verde-marca-pastel, rgba(46,125,50,0.08)); border-radius:8px;'>"
      + "<div style='font-size:13px; font-weight:700; color:var(--verde-marca);'>Tasa de Preñez (sobre expuestas): <b>" + tasa + "%</b></div>"
      + "<div style='font-size:12px; color:var(--texto-suave);'>Total: <b>" + total + "</b> hembras ≥1a</div>"
      + "</div>";

    cats.forEach(function (c) {
      var pct = total > 0 ? Math.round((c.n / total) * 100) : 0;
      h += "<div style='padding:10px 12px; background:var(--tarjeta-fondo, var(--superficie)); border:1px solid var(--borde); border-radius:8px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>"
        + "<b style='font-size:13px; color:var(--texto);'>" + esc(c.nombre) + "</b>"
        + "<span style='font-size:12.5px; font-weight:700; color:" + c.color + ";'>" + c.n + " cab. (" + pct + "%)</span>"
        + "</div>"
        + "<div style='background:var(--borde); border-radius:6px; height:12px; overflow:hidden;'>"
        + "<div style='width:" + pct + "%; height:100%; background:" + c.color + "; border-radius:6px; transition:width 0.4s ease;'></div>"
        + "</div>"
        + "</div>";
    });
    h += "</div>";
    return h;
  }

  function renderSvgOcupacion(d) {
    var potreros = (d && d.potreros) || [];
    if (!potreros.length) return vacio("No hay potreros ocupados en este momento.");

    var maxDias = potreros.reduce(function (m, p) { return Math.max(m, p.dias || 0); }, 7);
    var xMax = Math.ceil((maxDias * 1.15) / 5) * 5;

    var h = "<div style='display:flex; flex-direction:column; gap:8px;'>";
    potreros.forEach(function (p) {
      var pct = Math.min(100, Math.round(((p.dias || 0) / xMax) * 100));
      var col = p.color || (p.dias <= 3 ? "var(--verde-marca)" : (p.dias <= 6 ? "#f9a825" : "#ef5350"));
      var sem = p.semaforo || (p.dias <= 3 ? "🟢" : (p.dias <= 6 ? "🟡" : "🔴"));

      h += "<div style='padding:8px 12px; background:var(--tarjeta-fondo, var(--superficie)); border:1px solid var(--borde); border-radius:8px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px;'>"
        + "<a href='#' class='link-potrero-animales' data-potrero='" + esc(p.nombre) + "' style='font-size:13px; font-weight:700; color:var(--verde-marca); text-decoration:none; display:inline-flex; align-items:center; gap:4px;'>"
        + icon("grass", 13) + esc(p.nombre) + "</a>"
        + "<div style='display:flex; align-items:center; gap:8px; font-size:12px;'>"
        + "<span style='font-weight:700; color:" + col + ";'>" + sem + " " + p.dias + " d</span>"
        + "<button type='button' class='tema-btn btn-listar-animales-pot' data-potrero='" + esc(p.nombre) + "' style='font-size:11px; padding:2px 7px; border-radius:4px;'>"
        + icon("cow", 11) + p.animales + " cab.</button>"
        + "</div>"
        + "</div>"
        + "<div style='position:relative; background:var(--borde); border-radius:5px; height:12px; overflow:hidden;'>"
        + "<div style='width:" + pct + "%; height:100%; background:" + col + "; border-radius:5px;'></div>"
        + "</div>"
        + "</div>";
    });
    h += "</div>";
    return h;
  }

  function renderSvgAforo(d) {
    var potreros = (d && d.potreros) || [];
    if (!potreros.length) return vacio("Sin mediciones de aforo cargadas en los potreros.");

    var maxAforo = potreros.reduce(function (m, p) { return Math.max(m, p.aforo_kg_m2 || 0); }, 3.0);
    var xMax = Math.ceil(maxAforo * 1.2);
    var prom = d.promedio || 0;

    var h = "<div style='display:flex; flex-direction:column; gap:8px;'>";
    if (prom > 0) {
      h += "<div style='font-size:12px; color:var(--texto-suave); margin-bottom:4px;'>Aforo promedio de la finca: <b style='color:var(--verde-marca);'>" + prom + " kg/m²</b></div>";
    }
    potreros.forEach(function (p) {
      var pct = Math.min(100, Math.round(((p.aforo_kg_m2 || 0) / xMax) * 100));
      h += "<div style='padding:8px 12px; background:var(--tarjeta-fondo, var(--superficie)); border:1px solid var(--borde); border-radius:8px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;'>"
        + "<div><b style='font-size:13px; color:var(--texto);'>" + esc(p.nombre) + "</b> <small style='color:var(--texto-suave);'>(" + esc(p.tipo_pasto) + ")</small></div>"
        + "<b style='font-size:12.5px; color:var(--verde-marca);'>" + (p.aforo_kg_m2 ? p.aforo_kg_m2.toFixed(2) : "—") + " kg/m²</b>"
        + "</div>"
        + "<div style='background:var(--borde); border-radius:5px; height:12px; overflow:hidden;'>"
        + "<div style='width:" + pct + "%; height:100%; background:var(--verde-marca); border-radius:5px;'></div>"
        + "</div>"
        + "</div>";
    });
    h += "</div>";
    return h;
  }

  function renderSvgFlujoCaja(d) {
    var meses = (d && d.meses) || [];
    if (!meses.length) return vacio("Sin movimientos financieros en el periodo.");

    var n = meses.length;
    var maxVal = 1;
    meses.forEach(function (m) {
      var v = Math.max(m.ingresos || 0, m.egresos || 0, Math.abs(m.utilidad || 0));
      if (v > maxVal) maxVal = v;
    });
    var yMax = Math.ceil((maxVal * 1.15) / 1000000) * 1000000;
    if (yMax <= 0) yMax = 5000000;

    var w = Math.max(520, n * 52);
    var h = 230;
    var padL = 60, padR = 20, padT = 24, padB = 40;
    var chW = w - padL - padR;
    var chH = h - padT - padB;
    var slotW = chW / n;
    var bW = Math.max(8, Math.min(18, slotW * 0.32));

    var svg = "<div style='width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch;'>";
    svg += "<svg viewBox='0 0 " + w + " " + h + "' style='width:100%; min-width:340px; height:auto; display:block; font-family:var(--font-base,sans-serif);'>";

    // Grid horizontal
    for (var g = 0; g <= 4; g++) {
      var yP = padT + chH - (g / 4) * chH;
      var val = (yMax / 4) * g;
      var lbl = val >= 1000000 ? (val / 1000000).toFixed(1) + "M" : (val / 1000) + "k";
      svg += "<line x1='" + padL + "' y1='" + yP + "' x2='" + (w - padR) + "' y2='" + yP + "' stroke='var(--borde)' stroke-width='1' stroke-dasharray='" + (g === 0 ? "none" : "3,3") + "' />";
      svg += "<text x='" + (padL - 6) + "' y='" + (yP + 3.5) + "' fill='var(--texto-suave)' font-size='9.5' text-anchor='end'>$" + lbl + "</text>";
    }

    // Barras de ingresos y egresos
    meses.forEach(function (m, i) {
      var xCenter = padL + (i + 0.5) * slotW;
      var hIng = ((m.ingresos || 0) / yMax) * chH;
      var hEgr = ((m.egresos || 0) / yMax) * chH;

      var xIng = xCenter - bW - 2;
      var yIng = padT + chH - hIng;
      var xEgr = xCenter + 2;
      var yEgr = padT + chH - hEgr;

      if (hIng > 0) {
        svg += "<rect x='" + xIng + "' y='" + yIng + "' width='" + bW + "' height='" + hIng + "' rx='2' fill='var(--verde-marca)'>"
          + "<title>" + esc(m.mes) + " · Ingresos: " + fmtMoneda(m.ingresos) + "</title></rect>";
      }
      if (hEgr > 0) {
        svg += "<rect x='" + xEgr + "' y='" + yEgr + "' width='" + bW + "' height='" + hEgr + "' rx='2' fill='#ef5350'>"
          + "<title>" + esc(m.mes) + " · Egresos: " + fmtMoneda(m.egresos) + "</title></rect>";
      }

      svg += "<text x='" + xCenter + "' y='" + (h - padB + 16) + "' fill='var(--texto-suave)' font-size='9.5' font-weight='500' text-anchor='middle'>" + esc(m.mes) + "</text>";
    });

    svg += "</svg></div>";
    return svg;
  }

  function renderSvgWaterfall(d) {
    var pasos = (d && d.pasos) || [];
    if (!pasos.length) return vacio("Sin balance de inventario para graficar.");

    var n = pasos.length;
    var maxVal = pasos.reduce(function (m, p) { return Math.max(m, p.valor || 0, (p.base || 0) + (p.valor || 0)); }, 400);
    var yMax = Math.ceil((maxVal * 1.15) / 50) * 50;

    var w = Math.max(540, n * 48);
    var h = 230;
    var padL = 40, padR = 20, padT = 24, padB = 40;
    var chW = w - padL - padR;
    var chH = h - padT - padB;
    var slotW = chW / n;
    var bW = Math.max(14, Math.min(26, slotW * 0.6));

    var svg = "<div style='width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch;'>";
    svg += "<svg viewBox='0 0 " + w + " " + h + "' style='width:100%; min-width:360px; height:auto; display:block; font-family:var(--font-base,sans-serif);'>";

    for (var g = 0; g <= 4; g++) {
      var yP = padT + chH - (g / 4) * chH;
      var val = Math.round((yMax / 4) * g);
      svg += "<line x1='" + padL + "' y1='" + yP + "' x2='" + (w - padR) + "' y2='" + yP + "' stroke='var(--borde)' stroke-width='1' stroke-dasharray='" + (g === 0 ? "none" : "3,3") + "' />";
      svg += "<text x='" + (padL - 6) + "' y='" + (yP + 3.5) + "' fill='var(--texto-suave)' font-size='9.5' text-anchor='end'>" + val + "</text>";
    }

    pasos.forEach(function (p, i) {
      var xCenter = padL + (i + 0.5) * slotW;
      var xBar = xCenter - bW / 2;
      var esBase = p.tipo === "base";
      var dVal = p.delta != null ? p.delta : 0;
      var col = esBase ? "var(--texto-suave)" : (dVal >= 0 ? "var(--verde-marca)" : "#ef5350");

      var bBottom = esBase ? (padT + chH) : (padT + chH - ((p.base || 0) / yMax) * chH);
      var bH = esBase ? (((p.valor || 0) / yMax) * chH) : ((Math.abs(dVal) / yMax) * chH);
      var yBar = bBottom - bH;

      svg += "<rect x='" + xBar + "' y='" + yBar + "' width='" + bW + "' height='" + Math.max(3, bH) + "' rx='2' fill='" + col + "'>"
        + "<title>" + esc(p.etiqueta) + ": " + (esBase ? p.valor : (dVal > 0 ? "+" + dVal : dVal)) + "</title></rect>";

      var txtLbl = esBase ? p.valor : (dVal > 0 ? "+" + dVal : dVal);
      svg += "<text x='" + xCenter + "' y='" + (yBar - 5) + "' fill='" + col + "' font-size='9' font-weight='700' text-anchor='middle'>" + txtLbl + "</text>";
      svg += "<text x='" + xCenter + "' y='" + (h - padB + 16) + "' fill='var(--texto-suave)' font-size='9.5' font-weight='500' text-anchor='middle'>" + esc(p.etiqueta) + "</text>";
    });

    svg += "</svg></div>";
    return svg;
  }

  function renderSvgGmd(d) {
    var hem = (d && d.hembras) || [];
    var mac = (d && d.machos) || [];
    var todos = hem.concat(mac);
    if (!todos.length) return vacio("Se requieren al menos 2 animales con 2+ pesajes para calcular GMD.");

    var med = d.mediana || 0;
    var w = 540, h = 230;
    var padL = 45, padR = 20, padT = 24, padB = 40;
    var chW = w - padL - padR, chH = h - padT - padB;

    var svg = "<div style='width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch;'>";
    svg += "<svg viewBox='0 0 " + w + " " + h + "' style='width:100%; min-width:340px; height:auto; display:block; font-family:var(--font-base,sans-serif);'>";

    // Eje X: 0 .. 1200 días. Eje Y: -0.2 .. 1.2 kg/día
    var yMin = -0.2, yMax = 1.2;
    var xMax = 1200;

    // Línea 0
    var y0 = padT + chH - ((0 - yMin) / (yMax - yMin)) * chH;
    svg += "<line x1='" + padL + "' y1='" + y0 + "' x2='" + (w - padR) + "' y2='" + y0 + "' stroke='#888' stroke-width='1.2' stroke-dasharray='2,2' />";
    svg += "<text x='" + (padL - 6) + "' y='" + (y0 + 3.5) + "' fill='var(--texto-suave)' font-size='9' text-anchor='end'>0.0</text>";

    // Línea mediana
    var yMed = padT + chH - ((med - yMin) / (yMax - yMin)) * chH;
    svg += "<line x1='" + padL + "' y1='" + yMed + "' x2='" + (w - padR) + "' y2='" + yMed + "' stroke='var(--verde-marca)' stroke-width='1.5' stroke-dasharray='4,3' />";
    svg += "<text x='" + (w - padR) + "' y='" + (yMed - 5) + "' fill='var(--verde-marca)' font-size='9.5' font-weight='700' text-anchor='end'>Mediana: " + med + " kg/d</text>";

    // Puntos hembras
    hem.forEach(function (p) {
      var xP = padL + Math.min(chW, (p.edad_dias / xMax) * chW);
      var yP = padT + chH - Math.max(0, Math.min(chH, ((p.gmd - yMin) / (yMax - yMin)) * chH));
      svg += "<circle cx='" + xP + "' cy='" + yP + "' r='3.5' fill='var(--verde-marca)' opacity='0.75'>"
        + "<title>" + esc(p.tag) + " (Hembra): " + p.gmd + " kg/d · " + p.edad_dias + " d</title></circle>";
    });

    // Puntos machos
    mac.forEach(function (p) {
      var xP = padL + Math.min(chW, (p.edad_dias / xMax) * chW);
      var yP = padT + chH - Math.max(0, Math.min(chH, ((p.gmd - yMin) / (yMax - yMin)) * chH));
      svg += "<circle cx='" + xP + "' cy='" + yP + "' r='3.5' fill='#d97706' opacity='0.75'>"
        + "<title>" + esc(p.tag) + " (Macho): " + p.gmd + " kg/d · " + p.edad_dias + " d</title></circle>";
    });

    svg += "<text x='" + (w / 2) + "' y='" + (h - 6) + "' fill='var(--texto-suave)' font-size='10' text-anchor='middle'>Edad al último pesaje (días)</text>";
    svg += "</svg></div>";
    return svg;
  }

  function renderSvgComposicionRacial(d) {
    var razas = (d && d.items) || [];
    var total = (d && d.total) || 0;
    if (!razas.length) return vacio("Sin datos raciales registrados.");

    var h = "<div style='display:flex; flex-wrap:wrap; align-items:center; gap:20px; justify-content:center; padding:10px 0;'>";

    // Donut SVG
    var size = 180, r = 68, c = 2 * Math.PI * r;
    var acumuladoPct = 0;
    var pathsSvg = "";

    razas.forEach(function (rz) {
      var pct = (rz.pct || 0) / 100;
      var dash = pct * c;
      var offset = (1 - acumuladoPct) * c;
      pathsSvg += "<circle cx='90' cy='90' r='" + r + "' fill='none' stroke='" + (rz.color || "var(--verde-marca)") + "' stroke-width='28' "
        + "stroke-dasharray='" + dash + " " + (c - dash) + "' stroke-dashoffset='" + offset + "'>"
        + "<title>" + esc(rz.nombre) + ": " + rz.n + " (" + rz.pct + "%)</title></circle>";
      acumuladoPct += pct;
    });

    h += "<div style='width:180px; height:180px; flex-shrink:0; position:relative;'>"
      + "<svg viewBox='0 0 " + size + " " + size + "' style='width:100%; height:100%; transform:rotate(-90deg);'>"
      + pathsSvg
      + "</svg>"
      + "<div style='position:absolute; top:0; left:0; width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; pointer-events:none;'>"
      + "<b style='font-size:22px; color:var(--verde-marca); line-height:1;'>" + total + "</b>"
      + "<span style='font-size:11px; color:var(--texto-suave); margin-top:2px;'>animales</span>"
      + "</div>"
      + "</div>";

    // Leyenda lateral
    h += "<div style='display:flex; flex-direction:column; gap:8px; flex:1; min-width:200px;'>";
    razas.forEach(function (rz) {
      h += "<div style='display:flex; justify-content:space-between; align-items:center; padding:6px 10px; background:var(--tarjeta-fondo, var(--superficie)); border:1px solid var(--borde); border-radius:6px;'>"
        + "<div style='display:flex; align-items:center; gap:8px;'>"
        + "<span style='width:12px; height:12px; border-radius:3px; background:" + (rz.color || "var(--verde-marca)") + "; display:inline-block;'></span>"
        + "<span style='font-size:12.5px; font-weight:600; color:var(--texto);'>" + esc(rz.nombre) + "</span>"
        + "</div>"
        + "<span style='font-size:12px; font-weight:700; color:var(--texto);'>" + rz.n + " <small style='color:var(--texto-suave);'>(" + rz.pct + "%)</small></span>"
        + "</div>";
    });
    h += "</div></div>";
    return h;
  }

  function renderSvgSubastasComparativa(d) {
    var plazas = (d && d.plazas) || [];
    if (!plazas.length) return vacio("Sin cotizaciones de subastas registradas.");

    var maxP = plazas.reduce(function (m, p) { return Math.max(m, p.precio || 0); }, 10000);
    var prom = d.promedio_nacional || 0;

    var h = "<div style='display:flex; flex-direction:column; gap:8px;'>";
    if (prom > 0) {
      h += "<div style='font-size:12px; color:var(--texto-suave); margin-bottom:4px;'>Promedio Nacional: <b style='color:var(--texto);'>$" + Math.round(prom).toLocaleString("es-CO") + "/kg</b></div>";
    }

    plazas.forEach(function (pz) {
      var pct = Math.min(100, Math.round(((pz.precio || 0) / maxP) * 100));
      var esLocal = pz.es_local;
      var esMejor = pz.es_mejor;
      var col = esLocal ? "var(--verde-marca)" : (esMejor ? "#2e7d32" : "#52796f");

      h += "<div style='padding:8px 12px; background:var(--tarjeta-fondo, var(--superficie)); border:1px solid " + (esLocal ? "var(--verde-marca)" : "var(--borde)") + "; border-radius:8px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;'>"
        + "<div><b style='font-size:13px; color:var(--texto);'>" + esc(pz.nombre) + "</b> <small style='color:var(--texto-suave);'>(" + esc(pz.distancia) + ")</small></div>"
        + "<b style='font-size:13px; color:" + col + ";'>$" + Math.round(pz.precio || 0).toLocaleString("es-CO") + "/kg</b>"
        + "</div>"
        + "<div style='background:var(--borde); border-radius:5px; height:12px; overflow:hidden;'>"
        + "<div style='width:" + pct + "%; height:100%; background:" + col + "; border-radius:5px;'></div>"
        + "</div>"
        + "</div>";
    });
    h += "</div>";
    return h;
  }

  function renderSvgMapaPotreros(d) {
    var potreros = (d && d.potreros) || [];
    if (!potreros.length) return vacio("Sin potreros reales registrados.");

    var colorEstado = { "🟢": "var(--verde-marca)", "🟡": "#e0a400", "🔴": "#d64545", "🌱": "var(--texto-suave)" };
    var h = "<div style='font-size:11px; color:var(--texto-suave); margin-bottom:8px;'>"
      + "🟢 óptimo / listo · 🟡 rotar pronto · 🔴 sobreocupado · 🌱 en reposo · ordenado por urgencia de rotación</div>";
    h += "<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:8px; margin-bottom:12px;'>";
    potreros.forEach(function (p) {
      var nAnim = Number(p.animales) || 0;
      var sem = p.semaforo || (nAnim > 0 ? "🟢" : "🌱");
      var haTxt = p.area_has != null ? Number(p.area_has).toFixed(1) + " ha" : "—";
      var borde = colorEstado[sem] || "var(--borde)";
      var linea1, linea2 = "";
      if (nAnim > 0) {
        linea1 = icon("cow", 11) + nAnim + " cab.";
        var partes = [];
        if (p.dias_ocupacion != null) partes.push(p.dias_ocupacion + " d");
        if (p.carga_cab_ha != null) partes.push(p.carga_cab_ha + " cab/ha");
        linea2 = partes.join(" · ");
      } else {
        linea1 = p.dias_reposo != null ? "Reposo " + p.dias_reposo + " d" : "En reposo";
      }
      var titulo = p.estado_rotacion ? " title='" + esc(p.estado_rotacion) + "'" : "";
      h += "<div style='background:var(--tarjeta-fondo, var(--superficie)); border:1px solid var(--borde); border-left:3px solid " + borde + "; border-radius:8px; padding:8px 10px;'" + titulo + ">"
        + "<div style='display:flex; justify-content:space-between; align-items:center;'>"
        + "<span style='font-size:14px;'>" + sem + "</span>"
        + "<span style='font-size:11px; color:var(--texto-suave);'>" + haTxt + "</span>"
        + "</div>"
        + "<div style='font-size:12px; font-weight:700; color:var(--texto); margin:4px 0 2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>" + esc(p.nombre) + "</div>"
        + "<div style='font-size:11.5px; color:" + borde + "; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>"
        + linea1
        + "</div>"
        + (linea2 ? "<div style='font-size:10.5px; color:var(--texto-suave); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>" + esc(linea2) + "</div>" : "")
        + "</div>";
    });
    h += "</div>";
    h += "<div style='text-align:center;'><button type='button' class='tema-btn' id='btn-ir-mapa-satelital-desde-past' data-accion='ir-mapa-satelital' style='font-size:12px; padding:6px 14px; font-weight:700; background:var(--verde-marca); color:#fff; border-radius:6px;'>"
      + icon("mapPin", 14) + "Abrir Mapa Satelital GPS Completo</button></div>";
    return h;
  }

  function renderSvgCargaAnimal(d) {
    var potreros = (d && d.potreros) || [];
    if (!potreros.length) return vacio("Sin datos de carga animal.");

    var h = "<div style='display:flex; flex-direction:column; gap:8px;'>";
    potreros.forEach(function (p) {
      var cVal = p.carga_ugg_ha || 0;
      var col = cVal <= 1.8 ? "var(--verde-marca)" : (cVal <= 2.8 ? "#f9a825" : "#ef5350");
      h += "<div style='padding:8px 12px; background:var(--tarjeta-fondo, var(--superficie)); border:1px solid var(--borde); border-radius:8px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;'>"
        + "<div><b style='font-size:13px; color:var(--texto);'>" + esc(p.nombre) + "</b> <small style='color:var(--texto-suave);'>(" + p.animales + " cab. en " + (p.area_has ? p.area_has.toFixed(1) : "?") + " ha)</small></div>"
        + "<b style='font-size:12.5px; color:" + col + ";'>" + cVal.toFixed(2) + " cab/ha</b>"
        + "</div>"
        + "</div>";
    });
    h += "</div>";
    return h;
  }

  function renderizarGraficoVectorial(targetEl, tipo, data, cardEl) {
    if (!targetEl || !data) return;
    var t = String(tipo || "").toLowerCase();
    var html = "";

    if (t === "evolucion") html = renderSvgEvolucion(data);
    else if (t === "reproductivo_hato" || t === "reproductivo") html = renderSvgRepro(data);
    else if (t === "ocupacion" || t === "ocupacion_potreros") html = renderSvgOcupacion(data);
    else if (t === "aforo" || t === "aforo_potreros") html = renderSvgAforo(data);
    else if (t === "flujo_caja" || t === "flujo") html = renderSvgFlujoCaja(data);
    else if (t === "waterfall_inventario" || t === "waterfall") html = renderSvgWaterfall(data);
    else if (t === "gmd_hato" || t === "gmd") html = renderSvgGmd(data);
    else if (t === "composicion_racial" || t === "razas") html = renderSvgComposicionRacial(data);
    else if (t === "subastas_comparativa" || t === "subastas_tendencia" || t === "subastas") html = renderSvgSubastasComparativa(data);
    else if (t === "mapa_potreros" || t === "mapa") html = renderSvgMapaPotreros(data);
    else if (t === "carga_animal" || t === "carga") html = renderSvgCargaAnimal(data);
    else {
      html = "<div style='text-align:center; padding:20px; color:var(--texto-suave); font-size:12px;'>Visualización vectorial disponible en el desplegable de abajo.</div>";
    }

    targetEl.innerHTML = html;
    if (cardEl && data.subtitulo) {
      var sub = cardEl.querySelector(".grafico-sub-info");
      if (sub) sub.textContent = data.subtitulo;
    }
  }

  function inicializarGraficos(rootEl) {
    var root = rootEl || document;
    var cards = root.querySelectorAll ? root.querySelectorAll(".tarjeta-grafico-ja:not([data-iniciado])") : [];
    if (!cards || !cards.length) return;

    Array.from(cards).forEach(function (card) {
      card.setAttribute("data-iniciado", "1");
      var tipo = card.getAttribute("data-chart-tipo");
      var target = card.querySelector(".grafico-svg-target");
      if (!target || !tipo) return;

      var inlineStr = card.getAttribute("data-datos-inline");
      if (inlineStr) {
        try {
          var inlineData = JSON.parse(inlineStr);
          renderizarGraficoVectorial(target, tipo, inlineData, card);
          return;
        } catch (e) { /* fallback a fetch */ }
      }

      fetch("/api/grafico-datos/" + encodeURIComponent(tipo))
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(function (data) {
          renderizarGraficoVectorial(target, tipo, data, card);
        })
        .catch(function () {
          target.innerHTML = "<div style='text-align:center; padding:18px 10px; color:var(--texto-suave); font-size:12px;'>"
            + "<span style='font-size:16px;'>📊</span> Visualización vectorial no disponible en este momento. "
            + "<br><small>Puedes consultar el gráfico del servidor en el desplegable de abajo.</small></div>";
        });
    });
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

  window.JA = {
    esc: esc,
    mostrarToast: mostrarToast,
    vibrarConfirmacion: vibrarConfirmacion,
    chipEstado: chipEstado,
    vacio: vacio,
    tabla: tabla,
    kpi: kpi,
    erroresHtml: erroresHtml,
    grafico: grafico,
    fechaCorta: fechaCorta,
    fmtMoneda: fmtMoneda,
    icon: icon,
    inicializarGraficos: inicializarGraficos,
    renderizarGraficoVectorial: renderizarGraficoVectorial
  };
})();

