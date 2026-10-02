  /* ---------- Finanzas: Ingresos, Egresos y Utilidad ---------- */
  var _finanzasAno = new Date().getFullYear();
  var _finanzasMovsActuales = [];
  // Mismo orden y nombres que src/engine/finanzas_categorias.py.
  var CATEGORIAS_FINANZAS_LABEL = {
    VENTA_LECHE: "Venta de leche", VENTA_ANIMAL: "Venta de animales",
    COMPRA_ANIMAL: "Compra de animales", OTRO_INGRESO: "Otro ingreso",
    SAL_MINERALES: "Sal y minerales", MEDICAMENTOS: "Drogas / medicamentos",
    ALIMENTO: "Concentrado / alimento", FERTILIZANTES: "Abonos, semillas y venenos de potrero",
    REPRODUCCION: "Pajillas / nitrógeno", INSUMO: "Otros insumos (alambre, herramienta, etc.)",
    NOMINA: "Nómina / jornales", VETERINARIO: "Veterinario (visita / servicio)",
    INFRAESTRUCTURA: "Infraestructura / mantenimiento", COMBUSTIBLE: "Combustible",
    OTRO_EGRESO: "Otro gasto"
  };
  var CATEGORIAS_INGRESO_LISTA = ["VENTA_LECHE", "OTRO_INGRESO"];
  var CATEGORIAS_EGRESO_LISTA = ["SAL_MINERALES", "MEDICAMENTOS", "ALIMENTO", "FERTILIZANTES", "REPRODUCCION",
    "INSUMO", "NOMINA", "VETERINARIO", "INFRAESTRUCTURA", "COMBUSTIBLE", "OTRO_EGRESO"];
  function opcionesCategoriaFinanza(seleccionada) {
    function opts(lista) {
      return lista.map(function (c) {
        return "<option value='" + c + "'" + (c === seleccionada ? " selected" : "") + ">" + esc(CATEGORIAS_FINANZAS_LABEL[c]) + "</option>";
      }).join("");
    }
    return "<optgroup label='Ingresos'>" + opts(CATEGORIAS_INGRESO_LISTA) + "</optgroup>"
      + "<optgroup label='Gastos'>" + opts(CATEGORIAS_EGRESO_LISTA) + "</optgroup>";
  }
  function etiquetaCategoriaFinanza(cat) { return CATEGORIAS_FINANZAS_LABEL[cat] || cat; }

  // De dónde sale el costo por litro y por kg (src/engine/costeo_real.py):
  // los gastos del periodo repartidos entre leche y carne, sin contarlos dos veces.
  function desgloseCostoHtml(filas, unidad) {
    if (!filas || !filas.length) return "";
    return filas.slice(0, 5).map(function (f) {
      return "<span class='chip gris'>" + esc(etiquetaCategoriaFinanza(f.categoria)) + ": " + fmtMoneda(f.por_unidad) + "/" + unidad + "</span>";
    }).join(" ");
  }
  function notaCostoReal(kf) {
    if (kf.sin_gastos) {
      return "<p class='aviso'>" + icon("alertTriangle", 14) + "No hay gastos registrados en este periodo, así que no se puede calcular el costo por litro ni por kilo. Anote sus gastos en <b>+ Ingreso / Gasto</b> o lea las facturas con foto.</p>";
    }
    if (kf.reparto_leche_pct == null) return "";
    var porQue = kf.reparto_metodo === "vacas_ordeno"
      ? kf.vacas_ordeno + " vacas en ordeño de " + kf.total_activos + " animales activos"
      : (kf.reparto_metodo === "ingresos" ? "lo que aporta cada línea a los ingresos (no hay vacas en ordeño identificadas)"
        : (kf.reparto_metodo === "solo_leche" ? "solo hubo leche en este periodo" : "solo hubo ganado en este periodo"));
    var h = "<div class='aviso' style='margin-top:-6px;'>" + icon("info", 14)
      + "<b>Costos reales</b> con sus gastos registrados (" + fmtMoneda(kf.gastos_operativos || 0) + ")"
      + (kf.compras_animales ? " más compras de animales (" + fmtMoneda(kf.compras_animales) + ", van a carne)" : "")
      + ". A la leche le toca el <b>" + kf.reparto_leche_pct + "%</b> de los gastos, según " + esc(porQue) + "; el resto va a carne.";
    var dl = desgloseCostoHtml(kf.desglose_costo_litro, "L");
    var dk = desgloseCostoHtml(kf.desglose_costo_kg, "kg");
    if (dl) h += "<div style='margin-top:6px; display:flex; flex-wrap:wrap; gap:4px; align-items:center;'>" + icon("milk", 13) + "<b>Cada litro:</b> " + dl + "</div>";
    if (dk) h += "<div style='margin-top:4px; display:flex; flex-wrap:wrap; gap:4px; align-items:center;'>" + icon("scale", 13) + "<b>Cada kilo:</b> " + dk + "</div>";
    return h + "</div>";
  }

  function renderFinanzas(d) {
    var r = d.resumen || { total_ingresos: 0, total_egresos: 0, utilidad: 0, categorias: [] };
    var anoActual = new Date().getFullYear();
    var opcionesAno = "";
    for (var y = anoActual; y >= anoActual - 4; y--) {
      opcionesAno += "<option value='" + y + "'" + (y === _finanzasAno ? " selected" : "") + ">" + y + "</option>";
    }
    var btnGasto = "<button type='button' class='tema-btn' id='btn-ir-captura-gasto' style='background:var(--verde-marca); color:#fff; font-weight:700; border:none; cursor:pointer;'>" + icon("receipt", 14) + "+ Ingreso / Gasto</button>";
    var selectAno = "<label style='margin-left:auto;'>Año: <select id='fin-ano'>" + opcionesAno + "</select></label>";

    var h = "<div class='seccion-head-barra finanzas-head-barra'>"
      + "<h3>" + icon("banknote") + "Finanzas: Ingresos, Egresos y Utilidad</h3>"
      + "<div class='head-acciones-fila'>"
      + barraDescargaSeccion("finanzas", "Finanzas")
      + btnGasto
      + selectAno
      + "</div>"
      + "</div>" + erroresHtml(d);

    // Acceso directo al módulo de subastas y precios de mercado
    h += "<div style='margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; background:var(--superficie); padding:10px 14px; border-radius:8px; border:1px solid var(--borde);'>"
      + "<div style='font-size:13px; display:flex; align-items:center; gap:8px;'>" + icon("chartLine", 18) + "<span><b>Indicadores de Mercado:</b> Subastas Sugameta, Catama, Bogotá, precios de leche e insumos Ariari.</span></div>"
      + "<button type='button' class='tema-btn' id='btn-finanzas-ir-mercado' style='font-size:12px; padding:5px 12px; display:inline-flex; align-items:center; gap:5px; font-weight:600; cursor:pointer;'>" + icon("scale", 14) + "Ver Subastas &amp; Fletes</button>"
      + "</div>";

    h += "<div class='kpis'>"
      + kpiIr(kpi(fmtMoneda(r.total_ingresos), "Ingresos " + esc(d.desde || "") + " a " + esc(d.hasta || ""), "ok"), { sec: "Movimientos recientes" })
      + kpiIr(kpi(fmtMoneda(r.total_egresos), "Egresos", "alerta"), { sec: "Desglose por categoría" })
      + kpiIr(kpi(fmtMoneda(r.utilidad), "Utilidad", r.utilidad >= 0 ? "ok" : "alerta"), { sec: "Indicadores de rentabilidad" })
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
      + kpiIr(kpi(kf.margen_utilidad_pct != null ? kf.margen_utilidad_pct + "%" : "—", "Margen global de utilidad", kf.margen_utilidad_pct != null && kf.margen_utilidad_pct < 0 ? "alerta" : "ok"), { sec: "Línea de Producción: Leche" })
      + kpiIr(kpi(kf.costo_por_cabeza != null ? fmtMoneda(kf.costo_por_cabeza) : "—", "Costo por cabeza hato (" + (kf.total_activos != null ? kf.total_activos : 0) + " animales)"), { sec: "Desglose por categoría" })
      + kpiIr(kpi(fmtMoneda(r.total_ingresos - r.total_egresos), "Utilidad Neta Periodo", (r.total_ingresos - r.total_egresos) >= 0 ? "ok" : "alerta"), { sec: "Movimientos recientes" })
      + "</div>";
    h += notaCostoReal(kf);
    if (kf.costo_por_kg_carne != null || kf.ventas_sin_peso) {
      h += "<p class='aviso' style='margin-top:-6px;'>" + icon("alertTriangle", 14) + "Costo por kg de carne es un <b>estimado</b>: usa el último pesaje registrado antes de cada venta (no se pesa el animal en el momento exacto de vender)."
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

    if (fila.foto_ruta && /\.pdf$/i.test(fila.foto_ruta)) {
      var rutaPdf = fila.foto_ruta.indexOf("/") === 0 ? fila.foto_ruta : "/" + fila.foto_ruta;
      cuerpoHtml += "<div style='margin-top:14px;'>"
        + "<span style='color:var(--texto-suave); font-size:11.5px; text-transform:uppercase; display:block; margin-bottom:6px;'>" + icon("receipt", 13) + " Factura en PDF</span>"
        + "<a class='tema-btn' href='" + esc(rutaPdf) + "' target='_blank' rel='noopener' style='display:inline-flex; align-items:center; gap:6px; padding:8px 14px; text-decoration:none;'>" + icon("receipt", 14) + "Abrir la factura</a>"
        + "</div>";
    } else if (fila.foto_ruta) {
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
      + "<div class='modal-header'><b>" + icon("receipt", 15) + " Detalle del Movimiento</b><button type='button' class='modal-cerrar' id='btn-cerrar-fin-detalle' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
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

    var opcionesCategoria = opcionesCategoriaFinanza(null);

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
      + "<div class='modal-header'><b>" + icon("pencil", 15) + " Editar Movimiento</b><button type='button' class='modal-cerrar' id='btn-cerrar-fin-editar' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
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
            errorEl.textContent = (res.body.error || "No se pudo guardar.");
            errorEl.style.display = "block";
          }
        }).catch(function (err) {
          if (errorEl) { errorEl.textContent = String(err && err.message || err); errorEl.style.display = "block"; }
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
          window.alert((res.body.error || "No se pudo eliminar."));
        }
      }).catch(function (err) {
        window.alert(String(err && err.message || err));
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

