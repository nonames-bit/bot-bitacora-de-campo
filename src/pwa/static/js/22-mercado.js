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
      var badgeGanador = esGanador ? " <span class='chip verde' style='font-size:10.5px; font-weight:700;'>" + icon("sparkles", 12) + "Mayor Ingreso</span>" : "";

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
      + "<div class='modal-header'><b>" + icon("clipboard", 15) + " Fuentes Oficiales &amp; Metodología</b><button type='button' class='modal-cerrar' id='btn-cerrar-fuentes-modal' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
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
      + "<div class='modal-header'><b>" + icon("pencil", 15) + " Actualizar Cotización de Mercado</b><button type='button' class='modal-cerrar' id='btn-cerrar-act-modal' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
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
            if (errEl) { errEl.textContent = (res.body.error || "No se pudo actualizar el precio."); errEl.style.display = "block"; }
          }
        }).catch(function (err) {
          if (errEl) { errEl.textContent = "Error de conexión: " + (err && err.message || err); errEl.style.display = "block"; }
        });
    });
  }

  /* ==========================================================================
     MODALES: CATÁLOGO DE INSEMINADORES & SINCRONIZACIONES IATF
     ========================================================================== */

  var _cacheInseminadores = null;
  function cargarListaInseminadores(callback) {
    if (_cacheInseminadores && _cacheInseminadores.length) {
      poblarInseminadores(_cacheInseminadores);
      if (typeof callback === "function") callback(_cacheInseminadores);
      return;
    }
    fetch("/api/inseminadores")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok && d.inseminadores) {
          _cacheInseminadores = d.inseminadores;
          poblarInseminadores(d.inseminadores);
          if (typeof callback === "function") callback(d.inseminadores);
        }
      })
      .catch(function () { /* best-effort */ });

    function poblarInseminadores(insemList) {
      if (!insemList) insemList = [];
      var items = insemList.map(function (it) {
        var label = it.nombre + (it.telefono ? " (" + it.telefono + ")" : "");
        return { value: it.nombre, label: label };
      });
      rellenarDatalist("dl-inseminadores", items);
      rellenarDatalist("dl-responsables", items);
      var miNombre = (window.__usuarioActual && window.__usuarioActual.nombre) || "";
      var inp = document.getElementById("cap-inseminador");
      if (inp && !inp.value && miNombre) {
        inp.value = miNombre;
      }
      var inpPalp = document.getElementById("cap-palp-responsable");
      if (inpPalp && !inpPalp.value && miNombre) {
        inpPalp.value = miNombre;
      }
      var inpChk = document.getElementById("chk-responsable");
      if (inpChk && !inpChk.value && miNombre) {
        inpChk.value = miNombre;
      }
    }
  }

  function mostrarModalNuevoInseminador(onSuccess) {
    var overlay = document.getElementById("inseminador-modal");
    if (overlay) overlay.remove();

    var html = "<div id='inseminador-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:440px;'>"
      + "<div class='modal-header'><b>" + icon("userPlus", 16) + " Registrar Inseminador Oficial</b><button type='button' class='modal-cerrar' id='btn-cerrar-ins-modal' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
      + "<div style='padding:16px;'>"
      + "<form id='form-nuevo-inseminador' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<label style='font-size:12.5px; font-weight:600;'>Nombre Completo del Inseminador / Técnico:*<br>"
      + "<input id='ins-nombre' required placeholder='ej. Carlos Gómez, Dr. Morales' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Teléfono de Contacto (opcional):<br>"
      + "<input id='ins-telefono' type='tel' placeholder='ej. 3101234567' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='display:flex; align-items:center; gap:8px; font-size:12.5px; cursor:pointer; background:var(--superficie-elevada); padding:8px 10px; border-radius:6px; border:1px solid var(--borde);'>"
      + "<input type='checkbox' id='ins-es-usuario' style='width:auto;'> <span>¿Es operario / usuario de la finca?</span></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Notas / Observaciones:<br>"
      + "<input id='ins-notas' placeholder='ej. Especialista en IATF novillas' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<div id='ins-form-error' style='display:none; color:var(--color-rojo-txt, #dc2626); font-size:12px; font-weight:600;'></div>"
      + "<div style='display:flex; justify-content:flex-end; gap:8px; margin-top:6px;'>"
      + "<button type='button' class='tema-btn' id='btn-cancel-ins-modal' style='padding:8px 14px; border-radius:6px;'>Cancelar</button>"
      + "<button type='submit' class='btn-guardar-manga' style='padding:8px 16px; margin:0;'>Guardar Inseminador</button>"
      + "</div>"
      + "</form>"
      + "</div></div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("inseminador-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-ins-modal");
    var btnCan = document.getElementById("btn-cancel-ins-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    if (btnCan) btnCan.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

    var form = document.getElementById("form-nuevo-inseminador");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = document.getElementById("ins-form-error");
      var nom = (document.getElementById("ins-nombre").value || "").trim();
      if (!nom) {
        if (errEl) { errEl.textContent = "El nombre es obligatorio"; errEl.style.display = "block"; }
        return;
      }
      var payload = {
        nombre: nom,
        telefono: (document.getElementById("ins-telefono").value || "").trim() || null,
        es_usuario_sistema: Boolean(document.getElementById("ins-es-usuario").checked),
        notas: (document.getElementById("ins-notas").value || "").trim() || null
      };
      fetch("/api/inseminadores", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.ok) {
            mostrarToast("Inseminador " + nom + " registrado", "verde");
            _cacheInseminadores = null;
            cargarListaInseminadores();
            cerrar();
            if (typeof onSuccess === "function") onSuccess(nom);
          } else {
            if (errEl) { errEl.textContent = res.error || "No se pudo registrar"; errEl.style.display = "block"; }
          }
        }).catch(function (err) {
          if (errEl) { errEl.textContent = "Error de conexión: " + (err && err.message || err); errEl.style.display = "block"; }
        });
    });
  }

