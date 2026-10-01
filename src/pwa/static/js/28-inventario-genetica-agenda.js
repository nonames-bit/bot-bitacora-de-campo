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
      segs += "<div class='link-grupo-inventario' data-grupo-tipo='estructura' data-grupo-valor='" + esc(f.categoria) + "' style='width:" + pct + "%; background:" + color + "; cursor:pointer;' title=\"" + esc(f.categoria) + ": " + esc(f.n) + " (" + esc(f.pct) + "%) — Clic para listar\"></div>";
      leyenda += "<span class='link-grupo-inventario' data-grupo-tipo='estructura' data-grupo-valor='" + esc(f.categoria) + "' style='display:inline-flex; align-items:center; gap:5px; cursor:pointer; padding:2px 4px; border-radius:4px;' title='Clic para listar " + esc(f.categoria) + "'>"
        + "<span style='width:10px; height:10px; border-radius:2px; background:" + color + "; display:inline-block; flex-shrink:0;'></span>"
        + esc(f.categoria) + " <b>" + esc(f.n) + "</b> (" + esc(f.pct) + "%)</span>";
    });
    return "<div style='display:flex; height:30px; border-radius:7px; overflow:hidden; border:1px solid var(--borde-fuerte); margin-bottom:12px;'>" + segs + "</div>"
      + "<div style='display:flex; flex-wrap:wrap; gap:8px 16px; font-size:12.5px; margin-bottom:6px;'>" + leyenda + "</div>";
  }
  // Lista de potreros con barra proporcional al más cargado y clic directo para listar animales
  function barraDistribucionPotreros(filas) {
    if (!filas || !filas.length) return vacio("Ningún potrero con animales.");
    var max = 0;
    filas.forEach(function (f) { max = Math.max(max, Number(f.n) || 0); });
    var h = "<div style='display:flex; flex-direction:column; gap:10px;'>";
    filas.forEach(function (f) {
      var nom = String(f.potrero || "");
      var n = Number(f.n) || 0;
      var pct = max > 0 ? Math.max(4, Math.round((n / max) * 100)) : 0;
      var etiqueta = "<a href='#' class='link-potrero-animales' data-potrero='" + esc(nom) + "' style='font-weight:700; font-size:13px; text-decoration:none; color:var(--verde-marca); display:inline-flex; align-items:center; gap:4px;' title='Ver " + n + " animales en " + esc(nom) + "'>"
        + icon("grass", 13) + esc(nom) + "</a>";
      h += "<div style='background:var(--tarjeta-fondo); padding:8px 12px; border-radius:8px; border:1px solid var(--borde);'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px;'>"
        + "<span>" + etiqueta + "</span>"
        + "<button type='button' class='tema-btn btn-listar-animales-pot' data-potrero='" + esc(nom) + "' style='font-size:11.5px; padding:2px 8px; border-radius:5px; font-weight:700; display:inline-flex; align-items:center; gap:4px;'>"
        + icon("cow", 12) + "<span>" + esc(n) + " cab.</span></button>"
        + "</div>"
        + "<div class='btn-listar-animales-pot' data-potrero='" + esc(nom) + "' style='cursor:pointer; background:var(--superficie); border-radius:6px; height:14px; overflow:hidden; border:1px solid var(--borde-suave);' title='Clic para ver animales en " + esc(nom) + "'>"
        + "<div style='width:" + pct + "%; height:100%; background:var(--verde-marca); border-radius:6px;'></div>"
        + "</div>"
        + "</div>";
    });
    h += "</div>";
    return h;
  }
  // "Animales sin…" (calidad de datos, estilo Software Ganadero): cuántos
  // animales activos no tienen cada dato. Tocar una fila abre la lista con el
  // mismo modal de los grupos de inventario (tipo "sin").
  function renderAnimalesSin(as) {
    if (!as || !as.filas || !as.filas.length) return "";
    var h = "<h4>" + icon("clipboard") + "Animales sin…</h4>";
    h += "<p class='aviso' style='margin:0 0 6px;'>Datos que faltan en los " + esc(as.total_activos) + " animales activos. Toque una fila para ver cuáles son y complételos desde la ficha o la Captura.</p>";
    h += "<div class='tabla-scroll tabla-responsive-auto'><table class='tabla-inventario-compacta'><tr><th class='col-cat'>Sin…</th><th class='col-cab' style='text-align:center;'>Animales</th><th class='col-pct' style='text-align:right;'>%</th></tr>";
    as.filas.forEach(function (f) {
      var n = Number(f.total) || 0;
      if (n === 0) {
        h += "<tr><td class='col-cat' title='" + esc(f.ayuda) + "'>" + esc(f.etiqueta) + "</td>"
          + "<td class='col-cab' style='text-align:center;'><span class='chip verde' style='padding:2px 6px; font-size:11px;'>" + icon("check", 12) + "0</span></td>"
          + "<td class='col-pct' style='text-align:right; color:var(--texto-suave, #64748b);'>0%</td></tr>";
        return;
      }
      var attrs = " data-grupo-tipo='sin' data-grupo-valor='" + esc(f.clave) + "' data-grupo-titulo='" + esc("Animales sin: " + f.etiqueta) + "'";
      var chipCls = f.pct >= 50 ? "rojo" : (f.pct >= 10 ? "ambar" : "gris");
      h += "<tr class='fila-grupo-inventario'" + attrs + " style='cursor:pointer;'>"
        + "<td class='col-cat' title='" + esc(f.ayuda) + "'><a href='#' class='link-grupo-inventario'" + attrs + " style='font-weight:700; color:var(--verde-marca); text-decoration:none;'>" + esc(f.etiqueta) + "</a></td>"
        + "<td class='col-cab' style='text-align:center;'><span class='chip " + chipCls + "' style='font-weight:700; padding:2px 6px; font-size:11px;'>" + esc(n) + "</span></td>"
        + "<td class='col-pct' style='text-align:right; font-weight:500;'>" + esc(f.pct) + "%</td></tr>";
    });
    h += "</table></div>";
    return h;
  }

  // Registros imposibles o sospechosos (engine/calidad_datos.py). Se
  // corrigen desde la ficha de cada animal.
  var GRAVEDAD_ICONO = { alta: dot("rojo"), media: dot("naranja"), baja: dot("gris") };
  var DR_MAX_FILAS = 30;
  function renderDatosRevisar(lista) {
    if (!lista) return "";
    var h = "<div class='card lt-card'><h4 style='margin:0 0 6px;'>" + icon("eraser", 16) + "Datos a revisar (" + lista.length + ")</h4>";
    if (!lista.length) return h + vacio("No se encontraron registros imposibles en el hato activo.") + "</div>";
    h += "<p class='aviso' style='margin:0 0 8px;'>Registros que no pueden ser ciertos (casi siempre errores de digitación "
      + "o de la importación). Abra la ficha y corríjalos: mientras tanto pueden descuadrar listas y conteos.</p>";
    var tipos = [], por = {};
    lista.forEach(function (p) {
      if (!por[p.tipo]) { por[p.tipo] = []; tipos.push(p.tipo); }
      por[p.tipo].push(p);
    });
    h += "<div class='gen-filtros'>";
    tipos.forEach(function (t, i) {
      var p0 = por[t][0];
      h += "<button type='button' class='chip btn-dr" + (i === 0 ? " act" : "") + "' data-dr='" + esc(t) + "'>"
        + (GRAVEDAD_ICONO[p0.gravedad] || "") + esc(p0.titulo) + " <b>" + por[t].length + "</b></button>";
    });
    h += "</div>";
    tipos.forEach(function (t, i) {
      h += "<div class='dr-panel' data-dr='" + esc(t) + "'" + (i === 0 ? "" : " hidden") + ">";
      por[t].forEach(function (p, j) {
        h += "<div class='fila-pes'" + (j >= DR_MAX_FILAS ? " data-dr-extra hidden" : "") + "><div class='fila-pes-cab'><span>" + enlaceFicha(p.tag)
          + (p.nombre ? " <small>" + esc(p.nombre) + "</small>" : "") + "</span>"
          + (p.potrero ? "<small>" + esc(p.potrero) + "</small>" : "") + "</div><small>" + esc(p.detalle) + "</small></div>";
      });
      if (por[t].length > DR_MAX_FILAS) {
        h += "<button type='button' class='tema-btn btn-dr-todos'>Ver todos (" + por[t].length + ")</button>";
      }
      h += "</div>";
    });
    return h + "</div>";
  }
  function bindDatosRevisar() {
    qa(".btn-dr").forEach(function (b) {
      b.addEventListener("click", function () {
        var t = b.getAttribute("data-dr");
        qa(".btn-dr").forEach(function (o) { o.classList.toggle("act", o === b); });
        qa(".dr-panel").forEach(function (p) { p.hidden = p.getAttribute("data-dr") !== t; });
      });
    });
    qa(".btn-dr-todos").forEach(function (b) {
      b.addEventListener("click", function () {
        b.closest(".dr-panel").querySelectorAll("[data-dr-extra]").forEach(function (f) { f.hidden = false; });
        b.remove();
      });
    });
  }

  function renderInventario(d) {
    // Vista única Inventario + Población: tabla SG + pirámide + GMD + gráficos.
    var expBtn = "<button type='button' class='tema-btn' data-accion='exportar-inventario' style='font-size:12px; padding:6px 12px; display:inline-flex; align-items:center; gap:4px;'>" + icon("download", 14) + "Exportar CSV</button>";
    var rolInv = window.__usuarioActual && window.__usuarioActual.rol;
    if (rolInv === "OWNER" || rolInv === "ADMIN") {
      expBtn = "<button type='button' class='tema-btn' data-accion='crear-animal' style='font-size:12px; padding:6px 12px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; display:inline-flex; align-items:center; gap:4px;'>" + icon("plus", 14) + "Crear Animal</button>" + expBtn;
    }
    var h = "<div class='inv-head-barra' style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:14px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("cow") + "Inventario y Población</h3>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap;'>" + barraDescargaSeccion("inventario", "Inventario") + expBtn + "</div>"
      + "</div>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpiIr(kpi(d.total_activos, "Activos totales"), { sec: "Estructura del hato" })
      + kpiIr(kpi(d.total_hembras, "Hembras"), { sec: "Pirámide de edades" }) + kpiIr(kpi(d.total_machos, "Machos"), { sec: "Pirámide de edades" })
      + kpiIr(kpi(d.edad_promedio != null ? d.edad_promedio + "a" : "—", "Edad promedio"), { sec: "Distribución por Categorías de Edad" })
      + kpiIr(kpi(d.total_sin_sexo, "Sin clasificar", d.total_sin_sexo > 0 ? "alerta" : ""), { sec: "Animales sin" })
      + kpiIr(kpi(d.terneros_menor_12m, "Crías <12m"), { sec: "Pirámide de edades" })
      + (d.tasa_descarte ? kpiIr(kpi(d.tasa_descarte.pct + "%", "Tasa de descarte " + d.tasa_descarte.ano, d.tasa_descarte.pct > 20 ? "alerta" : ""), { vista: "carne", lt: "descarte" }) : "")
      + "</div>";
    h += grafico("waterfall_inventario", "Movimientos del hato (entradas/salidas)");
    var eh = d.estructura_hato;
    h += "<h4>" + icon("cow") + "Estructura del hato</h4>";
    if (!eh || !eh.filas || !eh.filas.length) {
      h += vacio("Sin animales activos para clasificar.");
    } else {
      h += barraApiladaCategorias(eh.filas);
      h += "<div class='tabla-scroll tabla-responsive-auto'><table class='tabla-inventario-compacta'><tr><th class='col-cat'>Categoría</th><th class='col-cab' style='text-align:center;'>Cabezas</th><th class='col-pct' style='text-align:right;'>%</th><th class='col-ugg' style='text-align:right;'>UGG</th><th class='col-act' style='text-align:center;'>Acción</th></tr>";
      eh.filas.forEach(function (f) {
        h += "<tr>"
          + "<td class='col-cat'><a href='#' class='link-grupo-inventario' data-grupo-tipo='estructura' data-grupo-valor='" + esc(f.categoria) + "' style='font-weight:700; color:var(--verde-marca); text-decoration:none;' title='Ver animales'>" + esc(f.categoria) + "</a></td>"
          + "<td class='col-cab' style='text-align:center;'><span class='chip link-grupo-inventario' data-grupo-tipo='estructura' data-grupo-valor='" + esc(f.categoria) + "' style='cursor:pointer; font-weight:700; padding:2px 5px; font-size:11px;'>" + esc(f.n) + "</span></td>"
          + "<td class='col-pct' style='text-align:right; font-weight:500;'>" + esc(f.pct) + "%</td>"
          + "<td class='col-ugg' style='text-align:right; font-weight:500;'>" + esc(f.ugg) + "</td>"
          + "<td class='col-act' style='text-align:center;'><button type='button' class='tema-btn link-grupo-inventario' data-grupo-tipo='estructura' data-grupo-valor='" + esc(f.categoria) + "' style='font-size:10.5px; padding:2px 6px; border-radius:4px;'>Ver</button></td>"
          + "</tr>";
      });
      h += "<tr style='font-weight:700;'><td class='col-cat'>Total</td><td class='col-cab' style='text-align:center;'>" + esc(eh.total) + "</td><td class='col-pct' style='text-align:right;'>100%</td><td class='col-ugg' style='text-align:right;'>" + esc(eh.total_ugg) + "</td><td class='col-act'></td></tr>";
      h += "</table></div>";
      h += "<p class='aviso' style='margin-top:6px;'>UGG (Unidad Gran Ganado) estimado con factores estándar por categoría, no con el peso real de cada animal.</p>";
    }
    h += renderAnimalesSin(d.animales_sin);
    h += renderDatosRevisar(d.datos_revisar);
    h += "<h4>" + icon("chartLine") + "Distribución por Categorías de Edad</h4>";
    h += "<div class='tabla-scroll tabla-responsive-auto'><table class='tabla-inventario-compacta'><tr><th class='col-cat'>Categoría</th><th class='col-cab' style='text-align:center;'>Cabezas</th><th class='col-pct' style='text-align:right;' title='Distribución porcentual'>% Dist.</th><th class='col-acum' style='text-align:right;' title='Porcentaje acumulado'>% Acum.</th><th class='col-act' style='text-align:center;'>Acción</th></tr>";
    (d.filas || []).forEach(function (f) {
      h += "<tr>"
        + "<td class='col-cat'><a href='#' class='link-grupo-inventario' data-grupo-tipo='bracket' data-grupo-valor='" + esc(f.categoria) + "' style='font-weight:700; color:var(--verde-marca); text-decoration:none;' title='Ver animales'>" + esc(f.categoria) + "</a></td>"
        + "<td class='col-cab' style='text-align:center;'><span class='chip link-grupo-inventario' data-grupo-tipo='bracket' data-grupo-valor='" + esc(f.categoria) + "' style='cursor:pointer; font-weight:700; padding:2px 5px; font-size:11px;'>" + esc(f.n) + "</span></td>"
        + "<td class='col-pct' style='text-align:right; font-weight:500;'>" + esc(f.pct) + "%</td>"
        + "<td class='col-acum' style='text-align:right; font-weight:500;'>" + esc(f.acum) + "%</td>"
        + "<td class='col-act' style='text-align:center;'><button type='button' class='tema-btn link-grupo-inventario' data-grupo-tipo='bracket' data-grupo-valor='" + esc(f.categoria) + "' style='font-size:10.5px; padding:2px 6px; border-radius:4px;'>Ver</button></td>"
        + "</tr>";
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
          + "<div class='pir-pista der'><div class='pir-barra hembra link-grupo-inventario' data-grupo-tipo='piramide' data-grupo-valor='" + esc(f.banda) + "' data-sexo='H' style='width:" + hB + "%; cursor:pointer;' title='Ver " + esc(f.hembras) + " hembras (" + esc(f.banda) + ")'></div></div>"
          + "<div class='pir-banda link-grupo-inventario' data-grupo-tipo='piramide' data-grupo-valor='" + esc(f.banda) + "' style='cursor:pointer;' title='Ver animales en banda " + esc(f.banda) + "'>"
          + esc(f.banda) + "<br><small><span class='link-grupo-inventario' data-grupo-tipo='piramide' data-grupo-valor='" + esc(f.banda) + "' data-sexo='H' style='color:var(--verde-marca); font-weight:700;'>" + esc(f.hembras) + " H</span> · "
          + "<span class='link-grupo-inventario' data-grupo-tipo='piramide' data-grupo-valor='" + esc(f.banda) + "' data-sexo='M' style='color:#1976d2; font-weight:700;'>" + esc(f.machos) + " M</span></small></div>"
          + "<div class='pir-pista izq'><div class='pir-barra macho link-grupo-inventario' data-grupo-tipo='piramide' data-grupo-valor='" + esc(f.banda) + "' data-sexo='M' style='width:" + mB + "%; cursor:pointer;' title='Ver " + esc(f.machos) + " machos (" + esc(f.banda) + ")'></div></div>"
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
  // Colores de los grados de sangre (legibles en tema claro y oscuro).
  var GEN_COLOR_GRADO = {
    morado: "#8e5cc4", verde: "#3f9142", azul: "#2f7fc1", ambar: "#d49a1a",
    cyan: "#1f9aa6", lima: "#8fa82a", naranja: "#e0782a", gris: "#9aa19b"
  };
  var GEN_ICONO_GRADO = {
    PURO: icon("sparkles", 12), F1_1_2: icon("dna", 12), "3_4": icon("ruler", 12), "5_8": icon("scale", 12), "7_8": icon("target", 12), "15_16": icon("award", 12),
    "13_16": icon("ruler", 12), "11_16": icon("ruler", 12), "9_16": icon("ruler", 12), "1_2": icon("leaf", 12), MULTI: icon("refresh", 12),
    PARCIAL: icon("grid", 12), CEBU: icon("cow", 12), TAURINO: icon("cow", 12), INDET: icon("help", 12), SIN_CLASIFICAR: icon("help", 12)
  };
  // Grados sin raza confiable: al final, en gris y cerrados por defecto.
  var GEN_SIN_DESGLOSE = { PARCIAL: 1, CEBU: 1, TAURINO: 1, INDET: 1, SIN_CLASIFICAR: 1 };

  function genChipsTags(tags, idx) {
    var chip = function (tg) {
      return "<button type='button' class='chip tag-chip-genetica' data-tag='" + esc(tg) + "' title='Ver ficha de " + esc(tg) + "'>" + esc(tg) + "</button>";
    };
    var max = 12;
    var h = tags.slice(0, max).map(chip).join("");
    var ocultos = tags.slice(max);
    if (ocultos.length) {
      var id = "tags-ocultos-gen-" + idx;
      h += "<span id='" + id + "' hidden>" + ocultos.map(chip).join("") + "</span>"
        + "<button type='button' class='chip btn-expandir-tags' data-target='" + id + "'>+" + ocultos.length + " más</button>";
    }
    return h;
  }

  function renderGenetica(d) {
    var h = "<h3>" + icon("dna") + "Composición Genética & Razas del Hato</h3>" + erroresHtml(d);

    var totalAct = d.total_activos || d.total || 0;
    var tip = d.tipificados || 0;
    var pctTip = d.pct_tipificados || (totalAct ? ((tip / totalAct) * 100).toFixed(1) : 0);
    var grados = d.grados_resumen || [];

    // 1. KPIs
    h += "<div class='kpis'>"
      + kpiIr(kpi(totalAct, "Hato activo"), { sec: "Grados de sangre" })
      + kpiIr(kpi(tip, "Con desglose racial (" + pctTip + "%)", "ok"), { sec: "Pool genético" })
      + kpiIr(kpi(d.indeterminados || 0, "Sin desglose de raza"), { sec: "Familias de cruce" })
      + "</div>";

    // 2. Grados de sangre: barra apilada + leyenda (clic = filtra familias)
    if (grados.length) {
      h += "<h4>" + icon("dna") + "Grados de sangre</h4><div class='gen-barra' role='img' aria-label='Distribución por grados de sangre'>";
      grados.forEach(function (g) {
        var ancho = Math.max(0.6, Number(g.pct_hato) || 0);
        h += "<span style='width:" + ancho + "%; background:" + (GEN_COLOR_GRADO[g.color] || GEN_COLOR_GRADO.gris) + ";' title='" + esc(g.nombre) + ": " + esc(g.cabezas) + " (" + esc(g.pct_hato) + "%)'></span>";
      });
      h += "</div><div class='gen-leyenda'>";
      grados.forEach(function (g) {
        h += "<button type='button' class='gen-ley-item btn-filtro-gen' data-grado='" + esc(g.codigo) + "'>"
          + "<i style='background:" + (GEN_COLOR_GRADO[g.color] || GEN_COLOR_GRADO.gris) + ";'></i>"
          + "<span>" + esc(g.nombre) + "</span><b>" + esc(g.cabezas) + "</b><small>" + esc(g.pct_hato) + "%</small></button>";
      });
      h += "</div>";
    }

    // 3. Pool genético: % de sangre de cada raza entre los animales con desglose
    var pool = d.pool_racial || [];
    if (pool.length) {
      var maxPct = pool.reduce(function (m, p) { return Math.max(m, Number(p.pct) || 0); }, 1);
      h += "<h4>" + icon("chartBar") + "Pool genético (% de sangre)</h4>"
        + "<p class='aviso'>Proporción de sangre de cada raza en los " + esc(tip) + " animales con desglose. Cabezas = animales que portan esa raza.</p>"
        + "<div class='gen-pool'>";
      pool.forEach(function (p) {
        var col = p.color || "var(--verde-marca)";
        h += "<div class='gen-pool-fila'>"
          + "<span class='gen-pool-raza'>" + esc(p.raza) + "</span>"
          + "<span class='gen-pool-pista'><span style='width:" + ((Number(p.pct) || 0) / maxPct * 100).toFixed(1) + "%; background:" + esc(col) + ";'></span></span>"
          + "<b>" + esc(p.pct) + "%</b><small>" + esc(p.cabezas_portadoras) + " cab.</small>"
          + "</div>";
      });
      h += "</div>";
      if (Number(d.pool_sin_dato_pct) > 0) {
        h += "<p class='aviso'>" + icon("grid", 14) + "Además, el " + esc(d.pool_sin_dato_pct) + "% de la sangre de estos animales no tiene dato (padre o madre sin raza registrada); no se cuenta como raza.</p>";
      }
    }

    // 4. Familias de cruce, agrupadas por grado
    var patrones = d.patrones_cruces || [];
    if (patrones.length) {
      h += "<h4>" + icon("dna") + "Familias de cruce</h4>"
        + "<div class='gen-filtros'><button type='button' class='chip btn-filtro-gen act' data-grado='TODOS'>Todos</button>";
      grados.forEach(function (g) {
        h += "<button type='button' class='chip btn-filtro-gen' data-grado='" + esc(g.codigo) + "'>" + (GEN_ICONO_GRADO[g.codigo] || "") + esc(g.chip) + "</button>";
      });
      h += "</div>"
        + "<input id='buscar-genetica-input' class='gen-buscar' type='search' placeholder='Buscar cruce, raza o arete (ej: Gyr, 3/4, JA45)'>";

      var grupos = [], porGrado = {};
      patrones.forEach(function (p) {
        var g = p.grado_codigo || "SIN_CLASIFICAR";
        if (!porGrado[g]) { porGrado[g] = { codigo: g, nombre: p.grado_nombre, color: p.chip_color, cabezas: 0, items: [] }; grupos.push(porGrado[g]); }
        porGrado[g].cabezas += Number(p.cabezas) || 0;
        porGrado[g].items.push(p);
      });
      var resumenPorGrado = {};
      grados.forEach(function (g) { resumenPorGrado[g.codigo] = g; });

      var idx = 0;
      grupos.forEach(function (gr) {
        var res = resumenPorGrado[gr.codigo] || {};
        var abierto = !GEN_SIN_DESGLOSE[gr.codigo];
        h += "<details class='gen-grupo' data-grado='" + esc(gr.codigo) + "'" + (abierto ? " open" : "") + ">"
          + "<summary><i style='background:" + (GEN_COLOR_GRADO[gr.color] || GEN_COLOR_GRADO.gris) + ";'></i>"
          + "<span>" + (GEN_ICONO_GRADO[gr.codigo] || "") + esc(res.nombre || gr.nombre) + "</span>"
          + "<b>" + esc(gr.cabezas) + "</b><small>" + esc(res.pct_hato != null ? res.pct_hato + "%" : "") + "</small></summary>";
        gr.items.forEach(function (p) {
          var tags = p.animales || [];
          h += "<div class='fila-patron-gen' data-grado='" + esc(gr.codigo) + "' data-search='" + esc((p.nombre + " " + p.fraccion + " " + tags.join(" ")).toLowerCase()) + "'>"
            + "<div class='gen-patron-cab'><span>" + esc(p.nombre) + "</span><b>" + esc(p.cabezas) + "</b></div>"
            + "<div class='gen-tags'>" + genChipsTags(tags, idx++) + "</div>"
            + "</div>";
        });
        h += "</details>";
      });
      h += "<p class='aviso' id='gen-sin-resultados' hidden>Ningún cruce coincide con el filtro.</p>";
    } else {
      h += vacio("Sin información genética registrada en el hato activo.");
    }

    // 5. Pajillas y termo
    var pj = d.pajillas_inventario || d.pajuelas_inventario || [];
    var tot = d.pajillas_totales || d.pajuelas_totales || {};
    h += "<h4>" + icon("pajillas") + "Inventario de pajillas (semen para I.A.)</h4>";
    if (tot.toros) {
      h += "<p class='aviso'><b>" + esc(tot.toros) + "</b> toros con existencias · <b>" + esc(tot.unidades) + "</b> pajillas en total"
        + (tot.toros > pj.length ? " · se muestran los " + pj.length + " con más pajillas" : "") + ".</p>";
    }
    var canastillas = {};
    pj.forEach(function (r) { canastillas[r.canastilla || ""] = 1; });
    var colsPj = [["codigo_toro", "Código"], ["raza", "Raza"], ["procedencia", "Toro / procedencia"]];
    if (Object.keys(canastillas).length > 1) colsPj.push(["canastilla", "Canastilla"]);
    colsPj.push(["cantidad", "Pajillas", "num", function (v) {
      var n = Number(v);
      var c = n >= 10 ? "verde" : n >= 3 ? "ambar" : "rojo";
      return "<span class='chip " + c + "'>" + esc(n) + "</span>";
    }]);
    h += tabla(pj, colsPj, "Sin inventario activo de pajillas registrado.");

    var pjinact = d.pajillas_inactivas || d.pajuelas_inactivas || [];
    if (pjinact.length) {
      h += "<details style='margin-top:10px; font-size:12px; background:var(--superficie-2); border:1px solid var(--borde-suave); border-radius:8px; padding:8px 12px;'>"
        + "<summary style='cursor:pointer; font-weight:600; color:var(--texto-suave);'>" + icon("package", 14) + "Catálogo histórico / pajillas inactivas (" + pjinact.length + " toros antiguos)</summary>"
        + "<p style='margin:6px 0; color:var(--texto-suave); font-size:11px;'>Toros del histórico archivados para no generar falsas alertas en el termo actual.</p>"
        + "<div class='tabla-scroll' style='max-height:200px; overflow-y:auto; margin-top:6px;'>"
        + tabla(pjinact, [
          ["codigo_toro", "Código"],
          ["raza", "Raza"],
          ["procedencia", "Procedencia"],
          ["cantidad", "Saldo Ant.", "num", function (v) { return "<span class='chip gris'>" + esc(v) + " un.</span>"; }]
        ], "Sin registros históricos.")
        + "</div></details>";
    }

    h += "<h4>" + icon("snowflake") + "Recargas del termo de nitrógeno</h4>";
    var te = d.termo_estado;
    if (te && te.vencido) {
      var dv = Number(te.dias_vencido) || 0;
      var hace = dv >= 730 ? Math.floor(dv / 365) + " años" : dv >= 60 ? Math.floor(dv / 30) + " meses" : dv + " días";
      h += "<p><span class='chip rojo'>" + icon("alertTriangle", 12) + "Recarga vencida hace " + esc(hace) + "</span> <small class='aviso'>Registra la última recarga para retomar el control.</small></p>";
    }
    h += tabla(d.termo_nitrogeno, [
      ["fecha_recarga", "Última recarga", "text", function (v) { return esc(fechaCorta(v)); }],
      ["proxima_recarga", "Próxima recarga", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }],
      ["dias_intervalo", "Intervalo (días)", "num"]
    ], "Sin historial de recargas de nitrógeno.");

    return h;
  }

  function bindGenetica(d) {
    var botonesFiltro = qa(".btn-filtro-gen");
    var grupos = qa(".gen-grupo");
    var inputBuscar = q("#buscar-genetica-input");
    var gradoSel = "TODOS";

    function aplicarFiltros() {
      var txt = ((inputBuscar && inputBuscar.value) || "").trim().toLowerCase();
      var visibles = 0;
      grupos.forEach(function (gr) {
        var filasVis = 0;
        var okGrado = gradoSel === "TODOS" || gr.getAttribute("data-grado") === gradoSel;
        gr.querySelectorAll(".fila-patron-gen").forEach(function (f) {
          var ok = okGrado && (!txt || (f.getAttribute("data-search") || "").indexOf(txt) !== -1);
          f.hidden = !ok;
          if (ok) filasVis++;
        });
        gr.hidden = !filasVis;
        // Al filtrar se abren los grupos con coincidencias, incluso los grises.
        if (filasVis && (txt || gradoSel !== "TODOS")) gr.open = true;
        visibles += filasVis;
      });
      var sinRes = q("#gen-sin-resultados");
      if (sinRes) sinRes.hidden = visibles > 0;
    }

    botonesFiltro.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var g = btn.getAttribute("data-grado") || "TODOS";
        gradoSel = (g === gradoSel && g !== "TODOS") ? "TODOS" : g;
        botonesFiltro.forEach(function (b) { b.classList.toggle("act", b.getAttribute("data-grado") === gradoSel); });
        aplicarFiltros();
        if (btn.classList.contains("gen-ley-item")) {
          var destino = q(".gen-filtros");
          if (destino && destino.scrollIntoView) destino.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
    if (inputBuscar) inputBuscar.addEventListener("input", aplicarFiltros);

    qa(".btn-expandir-tags").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var el = document.getElementById(btn.getAttribute("data-target"));
        if (el) { el.hidden = false; btn.hidden = true; }
      });
    });

    qa(".tag-chip-genetica").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var tag = chip.getAttribute("data-tag");
        if (tag) {
          irAVista("ficha");
          var inTag = q("#f-tag");
          if (inTag) inTag.value = tag;
          cargar(true);
        }
      });
    });
  }
  function renderAgenda(d) {
    var pdfBtn = "<a href='/api/reporte.pdf' class='tema-btn' download style='float:right; font-size:12px; text-decoration:none; padding:4px 10px; margin-top:-4px;'>" + icon("filePdf", 14) + "Reporte PDF</a>";
    var h = "<h3>" + icon("calendar") + "Agenda próximos " + esc(d.dias) + " días" + pdfBtn + "</h3>" + erroresHtml(d);
    // Crear evento/recordatorio (misma tabla de /programar): formulario móvil
    // apilado, táctil grande, sin recargar la página.
    // Crear evento / tarea asignada de campo: formulario móvil táctil grande
    var hoyIso = new Date().toISOString().slice(0, 10);
    h += "<div class='card' style='padding:14px 16px; margin:10px 0 16px; border-left:4px solid var(--verde-marca);'>"
      + "<b style='font-size:14px; display:flex; align-items:center; gap:6px;'>" + icon("plus", 14) + "Nueva Tarea / Evento Asignado</b>"
      + "<p class='aviso' style='margin:4px 0 10px; font-size:12px;'>Asigna tareas a un responsable (ej. Encargado, Administrador) para un animal o potrero. Genera recordatorios en el Despacho, la campanita y permite confirmar cumplimiento con foto y notas.</p>"
      + "<form id='form-nuevo-recordatorio' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<div style='display:flex; gap:8px;'>"
      + "<button type='button' class='tema-btn ag-obj-btn act' data-obj='animal' style='flex:1; padding:8px; font-size:13px;'>" + icon("cow", 14) + "Animal</button>"
      + "<button type='button' class='tema-btn ag-obj-btn' data-obj='potrero' style='flex:1; padding:8px; font-size:13px;'>" + icon("leaf", 14) + "Potrero</button>"
      + "<button type='button' class='tema-btn ag-obj-btn' data-obj='general' style='flex:1; padding:8px; font-size:13px;'>" + icon("clipboard", 14) + "General</button>"
      + "</div>"
      + "<input type='hidden' id='ag-obj-tipo' value='animal'>"
      + "<div id='ag-wrap-animal'>"
      + "<label style='font-size:13px; font-weight:600;'>Chapeta / Tag del Animal:<br>"
      + "<input id='ag-tag' placeholder='ej. JA457' list='dl-tags' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:15px; box-sizing:border-box;'>"
      + "</label>"
      + "</div>"
      + "<div id='ag-wrap-potrero' style='display:none;'>"
      + "<label style='font-size:13px; font-weight:600;'>Potrero:<br>"
      + "<input id='ag-potrero' placeholder='ej. OLEGARIO I' list='dl-potreros' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:15px; box-sizing:border-box;'>"
      + "</label>"
      + "</div>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap;'>"
      + "<label style='flex:1; min-width:140px; font-size:13px; font-weight:600;'>Tipo de Tarea:<br>"
      + "<select id='ag-tipo-tarea' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:14px; min-height:44px; box-sizing:border-box;'>"
      + "<option value='MEDICAMENTO'>Aplicar medicamento</option>"
      + "<option value='FUMIGAR'>Fumigar</option>"
      + "<option value='REVISION'>Revisión / Chequeo</option>"
      + "<option value='TRASLADO'>Traslado</option>"
      + "<option value='CERCA'>Arreglo de cerca</option>"
      + "<option value='PESAJE'>Pesaje</option>"
      + "<option value='GENERAL'>General</option>"
      + "</select></label>"
      + "<label style='flex:1; min-width:140px; font-size:13px; font-weight:600;'>Adjudicar / Asignar a:<br>"
      + "<input id='ag-asignado' list='dl-equipo-agenda' placeholder='ej. Encargado o Administrador' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:14px; min-height:44px; box-sizing:border-box;'>"
      + "<datalist id='dl-equipo-agenda'>"
      + "<option value='Encargado'></option>"
      + "<option value='Administrador'></option>"
      + "<option value='Veterinario'></option>"
      + "<option value='Trabajador'></option>"
      + "</datalist></label>"
      + "</div>"
      + "<label style='font-size:13px; font-weight:600;'>Instrucción / ¿Qué hay que hacer?<br>"
      + "<input id='ag-mensaje' maxlength='500' placeholder='ej. Aplicar 10ml oxitetraciclina IM o fumigar maleza en callejón' autocomplete='off' required style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:15px; min-height:44px; box-sizing:border-box;'>"
      + "</label>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap;'>"
      + "<label style='flex:1; min-width:130px; font-size:13px; font-weight:600;'>Fecha límite<br><input id='ag-fecha' type='date' value='" + hoyIso + "' required style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:15px; min-height:44px; box-sizing:border-box;'></label>"
      + "<label style='flex:1; min-width:110px; font-size:13px; font-weight:600;'>Hora (opcional)<br><input id='ag-hora' type='time' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:15px; min-height:44px; box-sizing:border-box;'></label>"
      + "<label style='flex:1; min-width:110px; font-size:13px; font-weight:600;'>Prioridad<br><select id='ag-prioridad' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:14px; min-height:44px; box-sizing:border-box;'><option value='NORMAL'>Normal</option><option value='URGENTE'>Urgente</option></select></label>"
      + "</div>"
      + "<button type='submit' id='btn-ag-guardar' class='btn-guardar-manga' style='margin-top:4px; font-size:14px;'>" + icon("plus", 14) + "Asignar Tarea / Programar Evento</button>"
      + "<div id='ag-form-feedback' role='status' aria-live='polite' style='font-size:13px;'></div>"
      + "</form></div>";
    // Recordatorios y tareas asignadas pendientes
    var recs = d.recordatorios || [];
    var recsComp = d.recordatorios_completados || [];
    var evs = d.eventos || [];
    var urgencia = function (f) {
      if (f.faltan_dias == null) return "gris";
      return f.faltan_dias <= 0 ? "rojo" : f.faltan_dias <= 2 ? "ambar" : "verde";
    };
    var chipUrg = function (v) {
      return "<span class='chip " + urgencia(v) + "'>" + esc(v.faltan_dias != null ? (v.faltan_dias <= 0 ? "HOY" : v.faltan_dias + "d") : "PENDIENTE") + "</span>";
    };

    if (recs.length) {
      h += "<h4>" + icon("calendar") + "Tareas Asignadas y Recordatorios Pendientes (" + recs.length + ")</h4>";
      h += "<div style='display:flex; flex-direction:column; gap:10px; margin-bottom:16px;'>";
      recs.forEach(function (rc) {
        var fh = esc(rc.fecha || "—") + (rc.hora ? " " + esc(rc.hora) : "");
        var objChip = "";
        if (rc.animal_tag) objChip = "<span class='chip azul'>" + icon("cow", 12) + esc(rc.animal_tag) + "</span> ";
        else if (rc.potrero_nombre) objChip = "<span class='chip azul'>" + icon("leaf", 12) + esc(rc.potrero_nombre) + "</span> ";

        var asigChip = rc.asignado_a ? ("<span class='chip verde' style='font-size:11.5px;'>" + icon("user", 12) + esc(rc.asignado_a) + "</span> ") : "";
        var prioChip = (rc.prioridad === "URGENTE") ? "<span class='chip rojo' style='font-size:11px;'>" + icon("alertTriangle", 12) + "URGENTE</span> " : "";

        h += "<div class='tarea-card " + (rc.prioridad === "URGENTE" ? "urgente" : "normal") + "'>"
          + "<div class='tarea-card-header'>"
          + "<div>" + objChip + asigChip + prioChip + chipUrg(rc) + "</div>"
          + "<small style='color:var(--texto-suave); font-weight:600;'>" + icon("calendar", 14) + fh + "</small>"
          + "</div>"
          + "<div style='font-size:14px; font-weight:700; color:var(--texto); margin:4px 0;'>" + esc(rc.mensaje || "—") + "</div>"
          + "<div style='display:flex; justify-content:flex-end; align-items:center; gap:8px; margin-top:4px;'>"
          + (window.__usuarioActual && window.__usuarioActual.rol === "OWNER" ? ("<button type='button' class='btn-eliminar-evento' data-accion='eliminar-evento' data-tipo='tarea' data-id='" + esc(rc.id) + "' data-desc='Tarea: " + esc(rc.mensaje || "") + "' title='Eliminar tarea (solo OWNER)' style='font-size:12px; padding:6px 8px; color:var(--color-rojo-txt); font-weight:600; display:inline-flex; align-items:center; gap:4px;'>" + icon("trash", 13) + "<span>Eliminar</span></button>") : "")
          + "<button type='button' class='btn-guardar-manga btn-rec-completar' data-rec-id='" + esc(rc.id) + "' data-rec-msg='" + esc(rc.mensaje || "") + "' data-rec-asig='" + esc(rc.asignado_a || "") + "' data-rec-tag='" + esc(rc.animal_tag || "") + "' style='font-size:12.5px; padding:7px 14px; width:auto; display:inline-flex; align-items:center; gap:6px; cursor:pointer;'>"
          + icon("check", 14) + "Marcar Realizado (Acknowledge)"
          + "</button>"
          + "</div>"
          + "</div>";
      });
      h += "</div>";
    } else {
      h += "<p class='aviso'>" + icon("sparkles", 14) + "Sin tareas asignadas pendientes. Use el formulario de arriba para asignar o agendar una nueva tarea.</p>";
    }

    if (recsComp.length) {
      h += "<h4>" + icon("shieldCheck") + "Bitácora de Tareas Cumplidas / Realizadas (" + recsComp.length + ")</h4>";
      h += "<div style='display:flex; flex-direction:column; gap:8px; margin-bottom:16px;'>";
      recsComp.forEach(function (rc) {
        var fechaComp = esc(rc.completado_en || rc.fecha || "—");
        var objChip = "";
        if (rc.animal_tag) objChip = "<span class='chip azul'>" + icon("cow", 12) + esc(rc.animal_tag) + "</span> ";
        else if (rc.potrero_nombre) objChip = "<span class='chip azul'>" + icon("leaf", 12) + esc(rc.potrero_nombre) + "</span> ";
        var quien = esc(rc.completado_por || rc.asignado_a || "Equipo");

        var fotoHtml = "";
        if (rc.foto_completado) {
          fotoHtml = "<div style='margin-top:6px;'><a href='/" + esc(rc.foto_completado) + "' target='_blank' style='display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--verde-marca); text-decoration:none; font-weight:600;'>"
            + "<img src='/" + esc(rc.foto_completado) + "' alt='Comprobante' style='width:48px; height:48px; object-fit:cover; border-radius:6px; border:1px solid var(--borde);'>"
            + "<span>Ver foto comprobante ↗</span></a></div>";
        }

        h += "<div style='padding:10px 14px; border:1px solid var(--borde); border-radius:8px; background:var(--superficie); border-left:4px solid var(--verde-marca);'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;'>"
          + "<div>" + objChip + "<span class='chip verde' style='font-size:11px;'>" + icon("check", 12) + "REALIZADO</span></div>"
          + "<small style='color:var(--texto-suave);'>" + icon("clock", 14) + fechaComp + "</small>"
          + "</div>"
          + "<div style='font-weight:600; font-size:13.5px; margin:4px 0;'>" + esc(rc.mensaje || "—") + "</div>"
          + "<div style='font-size:12.5px; color:var(--texto-suave);'>" + icon("user", 14) + "Ejecutado por: <b>" + quien + "</b></div>"
          + (rc.notas_completado ? ("<div style='font-size:12px; margin-top:4px; padding:6px 10px; background:var(--fondo); border-radius:6px; font-style:italic;'>" + icon("chat", 14) + esc(rc.notas_completado) + "</div>") : "")
          + fotoHtml
          + (window.__usuarioActual && window.__usuarioActual.rol === "OWNER" ? ("<div style='display:flex; justify-content:flex-end; margin-top:6px;'><button type='button' class='btn-eliminar-evento' data-accion='eliminar-evento' data-tipo='tarea' data-id='" + esc(rc.id) + "' data-desc='Tarea realizada: " + esc(rc.mensaje || "") + "' title='Eliminar registro de tarea' style='font-size:11.5px; color:var(--color-rojo-txt);'>" + icon("trash", 12) + " Eliminar del historial</button></div>") : "")
          + "</div>";
      });
      h += "</div>";
    }

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

