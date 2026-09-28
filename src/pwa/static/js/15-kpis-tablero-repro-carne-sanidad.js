  // ---------- Recuadros (KPI) tocables en todas las vistas ----------
  // kpiIr(html, {vista, lt, sec, tab, filtro}): vista = ir a otra pantalla;
  // lt = abrir esa lista de trabajo; sec = texto del título de la sección a
  // la que se baja; tab = pestaña de la ficha; filtro = filtro de la agenda
  // de pesaje (NUNCA / VENCIDO).
  function kpiIr(html, dest) {
    dest = dest || {};
    var attrs = "";
    ["vista", "lt", "sec", "tab", "filtro"].forEach(function (k) {
      if (dest[k]) attrs += " data-" + k + "='" + esc(dest[k]) + "'";
    });
    return "<div class='kpi-link' role='button' tabindex='0'" + attrs + ">" + html + "</div>";
  }
  // Busca el título de sección por su texto propio (sin contar el de sus
  // hijos, para no confundirlo con el contenedor de toda la vista).
  function irASeccion(texto) {
    if (!texto) return;
    var cont = document.getElementById("vista") || document.body;
    var t = String(texto).toLowerCase();
    var todos = cont.querySelectorAll("h3, h4, summary, b, div, span, p");
    for (var j = 0; j < todos.length; j++) {
      var el = todos[j];
      if (el.closest(".kpi-link, .kpis")) continue;
      var propio = "";
      for (var n = 0; n < el.childNodes.length; n++) {
        if (el.childNodes[n].nodeType === 3) propio += el.childNodes[n].nodeValue;
      }
      if (propio.toLowerCase().indexOf(t) === -1) continue;
      // Resaltar la tarjeta de la sección, salvo que sea la de toda la vista.
      var card = el.closest(".card, details");
      var marco = (card && !card.querySelector(".kpis")) ? card : el;
      var y = el.getBoundingClientRect().top + window.pageYOffset - 80;
      try { window.scrollTo({ top: y, behavior: "smooth" }); } catch (e) { window.scrollTo(0, y); }
      marco.classList.add("kpi-destacado");
      setTimeout(function () { marco.classList.remove("kpi-destacado"); }, 1800);
      return;
    }
  }
  function aplicarDestinoLocal(lt, filtro, sec) {
    if (lt) {
      var bl = q(".lt-card .btn-lt[data-lt='" + lt + "']");
      if (bl) { bl.click(); if (!sec) { var card = bl.closest(".lt-card"); if (card) card.scrollIntoView({ behavior: "smooth", block: "start" }); } }
    }
    if (filtro) {
      var bf = q(".btn-filtro-pes[data-filtro='est'][data-valor='" + filtro + "']");
      if (bf) bf.click();
    }
    if (sec) irASeccion(sec);
  }
  function irADestinoKpi(el) {
    var v = el.getAttribute("data-vista"), lt = el.getAttribute("data-lt"),
        sec = el.getAttribute("data-sec"), tab = el.getAttribute("data-tab"),
        filtro = el.getAttribute("data-filtro");
    if (tab) {
      var bt = q("#ficha-tabs button[data-tab='" + tab + "']");
      if (bt) { bt.click(); try { bt.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (e) { /* noop */ } }
      if (sec) setTimeout(function () { irASeccion(sec); }, 60);
      return;
    }
    if (v && v !== actual) {
      window.__ltAbrir = lt || null;
      window.__kpiDestino = (sec || filtro) ? { sec: sec, filtro: filtro } : null;
      irAVista(v);
      cargar(true);
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e2) { window.scrollTo(0, 0); }
      return;
    }
    aplicarDestinoLocal(lt, filtro, sec);
  }
  document.addEventListener("click", function (e) {
    var el = e.target && e.target.closest ? e.target.closest(".kpi-link, .btn-ir-tareas") : null;
    if (el) irADestinoKpi(el);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var el = e.target && e.target.classList && e.target.classList.contains("kpi-link") ? e.target : null;
    if (el) { e.preventDefault(); irADestinoKpi(el); }
  });

  // Tarjeta "Tareas de hoy" del Tablero: conteos por vista.
  var LT_VISTAS = [
    { vista: "repro", nombre: "Reproducción", claves: ["palpar", "secar", "servir", "novillas", "partos", "celos", "repetidoras"] },
    { vista: "leche", nombre: "Leche", claves: ["secar", "pausas", "control_leche"] },
    { vista: "carne", nombre: "Carne", claves: ["destetar", "topizar", "castrar", "marcar", "bajo_peso", "venta", "descarte", "categoria"] },
    { vista: "sanidad", nombre: "Sanidad", claves: ["vac_brucelosis", "vac_aftosa", "tratamientos"] }
  ];
  function ltClaves(vista) {
    for (var i = 0; i < LT_VISTAS.length; i++) if (LT_VISTAS[i].vista === vista) return LT_VISTAS[i].claves;
    return [];
  }
  function renderTareasHoy(c, nRevisar) {
    if (!c) return "";
    var h = "<div class='card lt-card-tablero'><div class='lt-titulo'>" + icon("calendar", 16) + "Tareas de hoy</div><div class='gen-filtros'>";
    LT_VISTAS.forEach(function (v) {
      var n = v.claves.reduce(function (s, k) { return s + (c[k] || 0); }, 0);
      h += "<button type='button' class='chip btn-ir-tareas' data-vista='" + v.vista + "'>" + esc(v.nombre) + " <b>" + n + "</b></button>";
    });
    if (c.chequeo) h += "<button type='button' class='chip btn-ir-tareas' data-vista='repro'>⚠️ Chequeo <b>" + esc(c.chequeo) + "</b></button>";
    if (nRevisar) h += "<button type='button' class='chip btn-ir-tareas' data-vista='inventario' data-sec='Datos a revisar'>🧹 Datos a revisar <b>" + esc(nRevisar) + "</b></button>";
    return h + "</div></div>";
  }

  function renderRepro(d) {
    var h = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("sperm", 22) + "Reproducción y Genética</h3>"
      + barraDescargaSeccion("reproduccion", "Reproducción")
      + "</div>" + erroresHtml(d);
    window.__listaTrabajo = d.lista_trabajo || null;
    window.__responsablesSugeridos = d.responsables_sugeridos || window.__responsablesSugeridos || [];
    h += renderListaTrabajo(d.lista_trabajo, ltClaves("repro")) + grafico("reproductivo_hato", "Estado reproductivo del hato");

    // Banco de Semen & Termo Criogénico (Software Ganadero)
    var termo = d.termo;
    var pajuelas = d.pajuelas || d.pajillas || [];
    var pajuelasInactivas = d.pajuelas_inactivas || d.pajillas_inactivas || [];
    var totalPaj = pajuelas.reduce(function (s, p) { return s + (Number(p.cantidad) || 0); }, 0);
    var alertasPaj = d.alertas_pajuelas || d.alertas_pajillas || [];

    var semNitr = !termo ? "gris" : (termo.dias_restantes <= 3 ? "rojo" : (termo.dias_restantes <= 7 ? "ambar" : "verde"));
    var txtNitr = !termo ? "Sin datos de recarga" : (termo.dias_restantes > 0 ? (termo.dias_restantes + " días restantes") : "¡Recarga vencida!");

    h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie); border-left:5px solid var(--azul-marca);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;'>"
      + "<div style='font-size:14px; font-weight:700; color:var(--texto); display:flex; align-items:center; gap:6px;'>"
      + icon("snowflake", 16) + "Banco de Semen &amp; Termo Criogénico"
      + "</div>"
      + "<div style='display:flex; gap:6px; flex-wrap:wrap;'>"
      + "<button type='button' class='tema-btn btn-ir-cap-directo' data-tipo='palpacion' style='font-size:11.5px; padding:5px 10px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;'>"
      + icon("stethoscope", 13) + "Tacto / Palpación</button>"
      + "<button type='button' class='tema-btn btn-ir-cap-directo' data-tipo='pajuela' style='font-size:11.5px; padding:5px 10px; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;'>"
      + icon("sperm", 13) + "➕ Entrada Pajillas</button>"
      + "<button type='button' class='tema-btn btn-ir-cap-directo' data-tipo='nitrogeno' style='font-size:11.5px; padding:5px 10px; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;'>"
      + icon("snowflake", 13) + "❄️ Recarga Nitrógeno</button>"
      + "</div>"
      + "</div>"
      + "<div class='kpis' style='margin-bottom:12px;'>"
      + kpiIr(kpi("<span class='chip " + semNitr + "' style='font-size:13px; font-weight:700;'><b>" + esc(txtNitr) + "</b></span>", "Termo Nitrógeno Líquido", termo && termo.dias_restantes <= 3 ? "alerta" : "ok"), { sec: "Banco de Semen" })
      + kpiIr(kpi(esc(totalPaj) + " pajillas", "Stock Total de Semen", "ok"), { sec: "Banco de Semen" })
      + kpiIr(kpi(esc(pajuelas.length) + " toros activos", "Reproductores Disponibles"), { sec: "Banco de Semen" })
      + (alertasPaj.length ? kpiIr(kpi("<span class='chip rojo'><b>" + alertasPaj.length + " en riesgo</b></span>", "Alertas Stock ≤ 3 pajillas", "alerta"), { sec: "Banco de Semen" }) : "")
      + "</div>";

    if (pajuelas.length) {
      h += "<div style='font-size:12px; font-weight:700; color:var(--texto-suave); margin-bottom:6px; text-transform:uppercase;'>Inventario Activo de Pajillas:</div>"
        + "<div class='tabla-scroll'><table><tr><th>Toro / Pajilla</th><th>Raza</th><th style='text-align:center;'>Canastilla</th><th style='text-align:right;'>Cantidad</th><th style='text-align:right;'>Costo Unit.</th><th>Procedencia</th><th style='text-align:center;'>Estado</th></tr>";
      h += pajuelas.map(function (p) {
        var cant = Number(p.cantidad) || 0;
        var cantChip = cant <= 2 ? "<span class='chip rojo'><b>" + cant + " un.</b></span>" : (cant <= 5 ? "<span class='chip ambar'><b>" + cant + " un.</b></span>" : "<span class='chip verde'><b>" + cant + " un.</b></span>");
        var costoStr = p.costo ? ("$" + Number(p.costo).toLocaleString("es-CO")) : "—";
        return "<tr>"
          + "<td><b>" + esc(p.codigo_toro) + "</b></td>"
          + "<td>" + esc(p.raza || "—") + "</td>"
          + "<td style='text-align:center;'><span class='chip gris'>" + esc(p.canastilla || "—") + "</span></td>"
          + "<td style='text-align:right;'>" + cantChip + "</td>"
          + "<td style='text-align:right; font-family:var(--font-mono);'>" + esc(costoStr) + "</td>"
          + "<td style='font-size:11.5px; color:var(--texto-suave);'>" + esc(p.procedencia || "—") + "</td>"
          + "<td style='text-align:center;'><button type='button' class='btn-cambiar-estado-pajilla' data-id='" + esc(p.id) + "' data-estado='INACTIVO' style='font-size:10.5px; padding:3px 7px; border:1px solid var(--borde-fuerte); border-radius:4px; background:var(--superficie-2); cursor:pointer;'>Marcar Inactiva</button></td>"
          + "</tr>";
      }).join("");
      h += "</table></div>";
    } else {
      h += vacio("No hay pajillas activas con saldo en el termo criogénico. Las existencias antiguas de Software Ganadero están archivadas como inactivas/usadas. Use el botón «➕ Entrada Pajillas» para registrar compras nuevas.");
    }

    if (pajuelasInactivas.length) {
      h += "<details style='margin-top:14px; background:var(--superficie-2); border-radius:8px; padding:10px 14px; border:1px solid var(--borde-suave);'>"
        + "<summary style='cursor:pointer; font-weight:700; font-size:12px; color:var(--texto-suave);'>"
        + "📁 Catálogo histórico / Pajillas inactivas o usadas (" + pajuelasInactivas.length + " toros) — Toca para desplegar"
        + "</summary>"
        + "<p style='font-size:11px; color:var(--texto-suave); margin:6px 0 8px;'>Toros del histórico importado de Software Ganadero (2013–2018) archivados para no generar falsas alertas en el termo actual. Puede reactivar cualquiera o entrar stock nuevo.</p>"
        + "<div class='tabla-scroll' style='max-height:240px; overflow-y:auto;'><table><tr><th>Toro / Pajilla</th><th>Raza</th><th style='text-align:center;'>Canastilla</th><th style='text-align:right;'>Saldo Ant.</th><th>Procedencia</th><th style='text-align:center;'>Acción</th></tr>"
        + pajuelasInactivas.map(function (p) {
          return "<tr>"
            + "<td><b>" + esc(p.codigo_toro) + "</b></td>"
            + "<td>" + esc(p.raza || "—") + "</td>"
            + "<td style='text-align:center;'><span class='chip gris'>" + esc(p.canastilla || "—") + "</span></td>"
            + "<td style='text-align:right; color:var(--texto-suave);'>" + esc(p.cantidad || 0) + " un.</td>"
            + "<td style='font-size:11.5px; color:var(--texto-suave);'>" + esc(p.procedencia || "—") + "</td>"
            + "<td style='text-align:center;'><button type='button' class='btn-cambiar-estado-pajilla' data-id='" + esc(p.id) + "' data-estado='ACTIVO' style='font-size:10.5px; padding:3px 7px; border:1px solid var(--verde-marca); color:var(--verde-marca); border-radius:4px; background:transparent; cursor:pointer;'>Reactivar</button></td>"
            + "</tr>";
        }).join("")
        + "</table></div></details>";
    }
    h += "</div>";

    // Guardar colecciones IATF e inseminadores en window para modales
    window.__protocolosIatf = (d.iatf && d.iatf.protocolos) || [];
    window.__lotesIatf = (d.iatf && d.iatf.lotes) || [];
    window.__evaluacionInseminadores = d.evaluacion_inseminadores || [];

    // 🧬 Sincronizaciones IATF (Inseminación Artificial a Tiempo Fijo)
    var iatf = d.iatf || {};
    var lotesIatf = iatf.lotes || [];
    var metricasIatf = iatf.metricas || {};

    h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie); border-left:5px solid #0284c7;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;'>"
      + "<div style='font-size:14px; font-weight:700; color:var(--texto); display:flex; align-items:center; gap:6px;'>"
      + icon("clipboard", 16) + "Sincronizaciones IATF & Cronograma de Fármacos"
      + "</div>"
      + "<div style='display:flex; gap:6px; flex-wrap:wrap;'>"
      + "<button type='button' class='tema-btn' id='btn-ver-protocolos-iatf' style='font-size:11.5px; padding:5px 10px; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; border:1px solid var(--borde-fuerte); background:var(--superficie-elevada); color:var(--texto);'>"
      + icon("clipboard", 13) + "📖 Protocolos & Marcas</button>"
      + "<button type='button' class='tema-btn' id='btn-nuevo-lote-iatf' style='font-size:11.5px; padding:5px 10px; background:#0284c7; color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;'>"
      + icon("plus", 13) + "➕ Iniciar Lote IATF</button>"
      + "</div>"
      + "</div>"
      + "<div class='kpis' style='margin-bottom:12px;'>"
      + kpiIr(kpi(esc(metricasIatf.lotes_en_curso || 0) + " activo(s)", "Lotes en Curso", (metricasIatf.lotes_en_curso > 0 ? "ok" : "")), { sec: "Sincronizaciones IATF" })
      + kpiIr(kpi(esc(metricasIatf.total_hembras_sincronizadas || 0) + " vientres", "Hembras Sincronizadas", "ok"), { sec: "Sincronizaciones IATF" })
      + kpiIr(kpi((metricasIatf.total_prenadas || 0) + " / " + (metricasIatf.total_diagnosticadas || 0), "Preñadas IATF Confirmadas"), { sec: "Sincronizaciones IATF" })
      + kpiIr(kpi(metricasIatf.tasa_prenez_global_pct != null ? (metricasIatf.tasa_prenez_global_pct + "%") : "—", "Tasa Preñez IATF", metricasIatf.tasa_prenez_global_pct != null && metricasIatf.tasa_prenez_global_pct >= 50 ? "ok" : ""), { sec: "Sincronizaciones IATF" })
      + "</div>";

    if (lotesIatf.length) {
      h += "<div style='font-size:12px; font-weight:700; color:var(--texto-suave); margin-bottom:8px; text-transform:uppercase;'>Lotes de Sincronización Registrados:</div>"
        + "<div style='display:flex; flex-direction:column; gap:12px;'>";

      lotesIatf.forEach(function (lote) {
        var estadoBadge = lote.estado === "EN_CURSO" ? "<span class='chip azul'><b>EN CURSO</b></span>" :
          (lote.estado === "IATF_REALIZADA" ? "<span class='chip ambar'><b>IATF REALIZADA</b></span>" :
          (lote.estado === "FINALIZADO" ? "<span class='chip verde'><b>FINALIZADO</b></span>" : "<span class='chip gris'>" + esc(lote.estado) + "</span>"));

        var catBadge = lote.protocolo_categoria === "CARNE" ? "<span class='chip' style='background:#fee2e2; color:#991b1b; font-size:10.5px;'>Carne / DP</span>" :
          (lote.protocolo_categoria === "LECHE" ? "<span class='chip' style='background:#e0f2fe; color:#075985; font-size:10.5px;'>Lechería</span>" :
          "<span class='chip' style='background:#fef3c7; color:#92400e; font-size:10.5px;'>Novillas</span>");

        var pasos = lote.protocolo_pasos || [];
        var stepperHtml = "<div style='display:flex; gap:6px; overflow-x:auto; padding:6px 0; -webkit-overflow-scrolling:touch; margin:8px 0;'>";
        pasos.forEach(function (p, idx) {
          var yaPaso = idx < lote.paso_actual;
          var esActual = idx === lote.paso_actual && lote.estado === "EN_CURSO";
          var bdrColor = yaPaso ? "var(--verde-marca, #16a34a)" : (esActual ? "#0284c7" : "var(--borde)");
          var bgStep = yaPaso ? "rgba(22,163,74,0.08)" : (esActual ? "rgba(2,132,199,0.1)" : "var(--superficie)");
          var iconStep = yaPaso ? "✅" : (esActual ? "👉" : "⏳");

          stepperHtml += "<div style='flex:1; min-width:130px; border:1px solid " + bdrColor + "; background:" + bgStep + "; border-radius:6px; padding:6px 8px; font-size:11px;'>"
            + "<div style='font-weight:700; color:var(--texto); display:flex; justify-content:space-between;'>"
            + "<span>Día " + p.dia_relativo + "</span> <span>" + iconStep + "</span>"
            + "</div>"
            + "<div style='color:var(--texto-suave); font-size:10.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;' title='" + esc(p.accion) + "'>" + esc(p.accion) + "</div>"
            + "</div>";
        });
        stepperHtml += "</div>";

        var btnsAccion = "<div style='display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;'>";
        if (lote.estado === "EN_CURSO") {
          if (lote.paso_actual < 2) {
            btnsAccion += "<button type='button' class='tema-btn btn-paso-iatf' data-lote-id='" + lote.id + "' data-paso-idx='" + lote.paso_actual + "' style='font-size:11.5px; padding:4px 9px; background:#0284c7; color:#fff; border:none; border-radius:5px; cursor:pointer; font-weight:600;'>"
              + "💊 Registrar Dosis / Fármaco</button>";
          }
          if (lote.paso_actual === 2 || lote.paso_actual === 1) {
            btnsAccion += "<button type='button' class='tema-btn btn-inseminar-lote-iatf' data-lote-id='" + lote.id + "' style='font-size:11.5px; padding:4px 9px; background:var(--verde-marca); color:#fff; border:none; border-radius:5px; cursor:pointer; font-weight:700;'>"
              + "🧬 Inseminar Lote Completo (1-Toque)</button>";
          }
        }
        btnsAccion += "<button type='button' class='tema-btn btn-detalle-lote-iatf' data-lote-id='" + lote.id + "' style='font-size:11.5px; padding:4px 9px; border:1px solid var(--borde-fuerte); border-radius:5px; cursor:pointer; background:var(--superficie); color:var(--texto);'>"
          + "📋 Ver Hembras (" + (lote.animales_activos || lote.total_animales) + ")</button>";
        btnsAccion += "</div>";

        h += "<div style='border:1px solid var(--borde); background:var(--superficie-elevada, rgba(0,0,0,0.02)); border-radius:8px; padding:12px 14px;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
          + "<div>"
          + "<span style='font-weight:700; font-size:13.5px; color:var(--texto);'>" + esc(lote.nombre) + "</span> "
          + catBadge + " "
          + estadoBadge
          + "</div>"
          + "<div style='font-size:11.5px; color:var(--texto-suave);'>Inicio: <b>" + esc(fechaCorta(lote.fecha_inicio)) + "</b> · IATF: <b>" + esc(lote.hora_iatf || "08:00") + "</b></div>"
          + "</div>"
          + "<div style='font-size:12px; color:var(--texto-suave); margin-top:4px;'>"
          + "Protocolo: <b>" + esc(lote.protocolo_nombre) + "</b> · Toro sugerido: <b>" + esc(lote.toro_pajuela || "Sin asignar") + "</b> · Inseminador: <b>" + esc(lote.inseminador || "Sin asignar") + "</b>"
          + "</div>"
          + stepperHtml
          + btnsAccion
          + "</div>";
      });
      h += "</div>";
    } else {
      h += vacio("No hay lotes IATF en curso. Use «➕ Iniciar Lote IATF» para programar sincronizaciones hormonales en novillas o vacas.");
    }
    h += "</div>";

    // Evaluación de palpadores: palpaciones del último año por responsable.
    h += "<div class='card' style='padding:16px; margin-bottom:14px; border-left:5px solid #0ea5e9;'>"
      + "<div style='font-size:14px; font-weight:700; margin-bottom:6px;'>" + icon("stethoscope", 16) + " Evaluación de palpadores (último año)</div>"
      + "<p class='aviso' style='margin:0 0 8px;'>«Contradichas»: preñadas que otro diagnóstico dio vacías en menos de 90 días (error o pérdida).</p>"
      + tabla(d.evaluacion_palpadores, [
        ["responsable", "Responsable"], ["palpaciones", "Palpaciones", "num"],
        ["prenadas", "Preñadas", "num"], ["vacias", "Vacías", "num"],
        ["pct_prenez", "% preñez", "text", function (v) { return esc(v) + "%"; }],
        ["contradichas", "Contradichas", "text", function (v) { return v ? "<span class='chip ambar'>" + esc(v) + "</span>" : "0"; }]
      ], "Sin palpaciones registradas en el último año.")
      + "</div>";

    // 🏆 Evaluación y Efectividad de Inseminadores
    var insems = d.evaluacion_inseminadores || [];

    h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie); border-left:5px solid #8b5cf6;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;'>"
      + "<div style='font-size:14px; font-weight:700; color:var(--texto); display:flex; align-items:center; gap:6px;'>"
      + icon("chartBar", 16) + "Evaluación & Efectividad de Inseminadores"
      + "</div>"
      + "<button type='button' class='tema-btn' id='btn-nuevo-inseminador' style='font-size:11.5px; padding:5px 10px; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; background:var(--superficie-elevada, #f3f4f6); color:var(--texto); border:1px solid var(--borde-fuerte);'>"
      + icon("userPlus", 13) + "➕ Nuevo Inseminador</button>"
      + "</div>"
      + "<div style='font-size:12px; color:var(--texto-suave); margin-bottom:12px;'>"
      + "Monitoreo zootécnico del desempeño por técnico: tasa de concepción y servicios requeridos por preñez."
      + "</div>";

    if (insems.length) {
      h += "<div class='tabla-scroll'><table><tr><th>Inseminador / Técnico</th><th style='text-align:right;'>Total IAs</th><th style='text-align:right;'>Preñadas</th><th style='text-align:right;'>Vacías</th><th style='text-align:right;'>Concepción</th><th style='text-align:right;'>Serv / Conc (S/C)</th><th>Teléfono</th></tr>";
      h += insems.map(function (ins) {
        var semColor = ins.semaforo === "VERDE" ? "verde" : (ins.semaforo === "AMARILLO" ? "ambar" : (ins.semaforo === "ROJO" ? "rojo" : "gris"));
        var tasaTxt = ins.tasa_concepcion_pct != null ? (ins.tasa_concepcion_pct + "%") : "—";
        var scTxt = ins.servicios_por_concepcion != null ? (ins.servicios_por_concepcion.toFixed(1)) : "—";
        var badgeUser = ins.es_usuario_sistema ? "<span class='chip azul' style='font-size:10px; padding:2px 5px; margin-left:5px;'>Usuario App</span>" : "";
        return "<tr>"
          + "<td><b>" + esc(ins.inseminador) + "</b>" + badgeUser + "</td>"
          + "<td style='text-align:right; font-weight:700;'>" + (ins.total_ias || 0) + "</td>"
          + "<td style='text-align:right; color:var(--verde-marca, #16a34a); font-weight:700;'>" + (ins.prenadas || 0) + "</td>"
          + "<td style='text-align:right; color:var(--color-rojo-txt, #dc2626);'>" + (ins.vacias || 0) + "</td>"
          + "<td style='text-align:right;'><span class='chip " + semColor + "' style='font-weight:700; font-size:12px;'>" + tasaTxt + "</span></td>"
          + "<td style='text-align:right; font-family:var(--font-mono); font-weight:600;'>" + scTxt + "</td>"
          + "<td style='font-size:12px; color:var(--texto-suave);'>" + esc(ins.telefono || "—") + "</td>"
          + "</tr>";
      }).join("");
      h += "</table></div>";
    } else {
      h += vacio("No hay inseminadores registrados. Use el botón «➕ Nuevo Inseminador» para darlos de alta o registre servicios por IA.");
    }
    h += "</div>";

    // 1. Tarjeta Destacada: Índice de Fertilidad Oficial (Software Ganadero)
    var ifInfo = d.indice_fertilidad || {};
    if (ifInfo.indice_pct != null) {
      var semColor = ifInfo.indice_pct >= 75 ? "var(--verde-marca)" : (ifInfo.indice_pct >= 60 ? "#D97706" : "#DC2626");
      h += "<div class='card' style='padding:16px; margin-bottom:14px; border-left:5px solid " + semColor + "; background:var(--superficie); box-shadow:0 2px 6px var(--sombra);'>"
        + "<div style='display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:10px;'>"
        + "<div>"
        + "<div style='font-size:12px; font-weight:700; color:var(--texto-suave); text-transform:uppercase; letter-spacing:0.5px;'>Índice de Fertilidad Oficial (Software Ganadero)</div>"
        + "<div style='font-size:28px; font-weight:800; color:" + semColor + "; line-height:1.2; margin:4px 0;'>"
        + (ifInfo.semaforo || "🟢") + " " + ifInfo.indice_pct + "%"
        + "</div>"
        + "<div style='font-size:13px; font-weight:600; color:var(--texto);'>" + esc(ifInfo.diagnostico || "Eficiencia reproductiva") + "</div>"
        + "</div>"
        + "<div style='display:flex; gap:12px; flex-wrap:wrap; font-size:12.5px; background:rgba(0,0,0,0.03); padding:10px 14px; border-radius:8px;'>"
        + "<div><span style='color:var(--texto-suave); display:block; font-size:11px;'>Preñadas</span><b>" + (ifInfo.prenadas || 0) + "</b></div>"
        + "<div><span style='color:var(--texto-suave); display:block; font-size:11px;'>En descanso (&le;120d)</span><b>" + (ifInfo.en_descanso || 0) + "</b></div>"
        + "<div><span style='color:var(--texto-suave); display:block; font-size:11px;'>Vientres aptos</span><b>" + (ifInfo.total_vientres || 0) + "</b></div>"
        + "</div>"
        + "</div>"
        + "<div style='font-size:11px; color:var(--texto-suave); margin-top:10px; border-top:1px dashed var(--borde-suave); padding-top:6px;'>"
        + "Fórmula oficial: ((Preñadas + Vacas &le; 120 días postparto) / Vientres con edad &ge; 3 años o paridas) &times; 100"
        + "</div>"
        + "</div>";
    }

    var k = d.kpis || {};
    h += "<h4>" + icon("chartBar") + "Indicadores del hato</h4>";
    var pm = d.perdidas || {};
    h += "<div class='kpis'>"
      + kpiIr(kpi(k.iep_promedio_dias != null ? k.iep_promedio_dias + "d" : "—", "IEP promedio"), { sec: "Intervalo Entre Partos" })
      + kpiIr(kpi(k.dias_abiertos_promedio != null ? k.dias_abiertos_promedio + "d" : "—", "Días abiertos (" + (k.dias_abiertos_n || 0) + " vaca(s))", k.dias_abiertos_promedio > 150 ? "alerta" : ""), { sec: "Días Abiertos" })
      + kpiIr(kpi(k.servicios_por_concepcion != null ? k.servicios_por_concepcion : "—", "Servicios/Concepción"), { sec: "Efectividad de Inseminadores" })
      + kpiIr(kpi(k.tasa_concepcion != null ? k.tasa_concepcion + "%" : "—", "Tasa de concepción", k.tasa_concepcion != null && k.tasa_concepcion < 50 ? "alerta" : "ok"), { sec: "Efectividad de Inseminadores" })
      + kpiIr(kpi(k.edad_primer_parto_meses != null ? k.edad_primer_parto_meses + "m" : "—", "Edad 1er parto"), { sec: "Novillas entoradas" })
      + kpiIr(kpi((pm.tasa_perdida_pct != null ? pm.tasa_perdida_pct + "%" : "—"), "Pérdidas gestacionales (" + (pm.perdidas || 0) + ")", (pm.tasa_perdida_pct || 0) >= 5 ? "alerta" : ""), { sec: "Diagnósticos de gestación recientes" })
      + kpiIr(kpi((pm.tasa_distocia_pct != null ? pm.tasa_distocia_pct + "%" : "—"), "Partos difíciles (" + (pm.distocias || 0) + ")", (pm.tasa_distocia_pct || 0) >= 10 ? "alerta" : ""), { sec: "Diagnósticos de gestación recientes" })
      + "</div>";

    // Pérdidas gestacionales y distocias (cierre Fase 5.2): últimas
    // pérdidas y vacas reincidentes que el mayordomo debe vigilar.
    if (pm && (pm.perdidas || pm.distocias)) {
      h += "<div class='card' style='padding:14px 16px; margin-bottom:14px; background:var(--superficie); border-left:5px solid var(--color-rojo-txt, #dc2626);'>"
        + "<div style='font-size:14px; font-weight:700; margin-bottom:6px;'>⚠️ Pérdidas gestacionales y partos difíciles</div>"
        + "<div style='font-size:12.5px; color:var(--texto-suave); margin-bottom:8px;'>"
        + esc(pm.partos || 0) + " partos · " + esc(pm.perdidas || 0) + " pérdidas (" + esc(pm.tasa_perdida_pct || 0) + "%) · "
        + esc(pm.distocias || 0) + " difíciles (" + esc(pm.tasa_distocia_pct || 0) + "%) · "
        + esc(pm.crias_muertas_parto || 0) + " crías muertas al nacer</div>";
      if (pm.reincidentes && pm.reincidentes.length) {
        h += "<div style='font-size:12.5px; font-weight:700; margin-bottom:4px;'>🔁 Vacas reincidentes (≥2 pérdidas):</div>"
          + "<div style='display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px;'>"
          + pm.reincidentes.map(function (r) {
            return "<a href='#' class='ficha-link chip rojo' data-ir-ficha='" + esc(r.vaca) + "' style='font-size:12px; padding:3px 8px; font-weight:bold; text-decoration:none;'>" + esc(r.vaca) + " ×" + esc(r.perdidas) + "</a>";
          }).join("") + "</div>";
      }
      if (pm.recientes && pm.recientes.length) {
        h += "<div style='font-size:12.5px; font-weight:700; margin-bottom:4px;'>Últimas pérdidas:</div>"
          + "<div style='font-size:12.5px; display:flex; flex-direction:column; gap:3px;'>"
          + pm.recientes.slice(0, 5).map(function (r) {
            return "<div>• <b>" + esc(r.vaca) + "</b> · " + esc(r.tipo_evento) + " · " + esc(fechaCorta(r.fecha)) + "</div>";
          }).join("") + "</div>";
      }
      h += "</div>";
    }

    // 2. Distribución de Días Abiertos (DA) por tramos (Software Ganadero)
    if (d.distribucion_dias_abiertos && d.distribucion_dias_abiertos.length) {
      h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie);'>"
        + "<div style='font-size:14px; font-weight:700; margin-bottom:4px; display:flex; align-items:center; gap:6px;'>"
        + icon("chartBar", 16) + "Distribución de Frecuencias [Días Abiertos]"
        + "</div>"
        + "<div style='font-size:12px; color:var(--texto-suave); margin-bottom:12px;'>Desglose de vacas abiertas según tramos de días postparto (referencia SG)</div>"
        + "<div style='display:flex; flex-direction:column; gap:6px;'>";
      d.distribucion_dias_abiertos.forEach(function (tr) {
        var barColor = (tr.tramo === "0-90" || tr.tramo === "91-120") ? "var(--verde-marca)" : (tr.tramo === "121-150" || tr.tramo === "151-180" ? "#D97706" : "#DC2626");
        h += "<div style='display:flex; align-items:center; gap:8px; font-size:12px;'>"
          + "<span style='width:65px; font-weight:600; white-space:nowrap; text-align:right;'>" + tr.tramo + " d</span>"
          + "<div style='flex:1; background:rgba(0,0,0,0.06); height:16px; border-radius:4px; overflow:hidden;'>"
          + "<div style='width:" + Math.max(tr.pct, tr.cantidad > 0 ? 3 : 0) + "%; background:" + barColor + "; height:100%; border-radius:4px; transition:width 0.3s;'></div>"
          + "</div>"
          + "<span style='width:75px; font-weight:700; color:var(--texto);'>" + tr.cantidad + " (" + tr.pct + "%)</span>"
          + "</div>";
      });
      h += "</div></div>";
    }

    // 3. Distribución de Intervalo Entre Partos (IEP) por tramos
    if (d.distribucion_iep && d.distribucion_iep.length) {
      h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie);'>"
        + "<div style='font-size:14px; font-weight:700; margin-bottom:4px; display:flex; align-items:center; gap:6px;'>"
        + icon("calendar", 16) + "Intervalo Entre Partos (IEP) por Tramos"
        + "</div>"
        + "<div style='font-size:12px; color:var(--texto-suave); margin-bottom:12px;'>Frecuencias de partos consecutivos en el hato</div>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:8px;'>";
      d.distribucion_iep.forEach(function (tr) {
        var cBg = tr.tramo === "<365" || tr.tramo === "365-395" ? "rgba(16,185,129,0.12)" : (tr.tramo === "396-425" || tr.tramo === "426-455" ? "rgba(245,158,11,0.12)" : "rgba(239,68,68,0.12)");
        var cBdr = tr.tramo === "<365" || tr.tramo === "365-395" ? "var(--verde-marca)" : (tr.tramo === "396-425" || tr.tramo === "426-455" ? "#D97706" : "#DC2626");
        h += "<div style='border:1px solid " + cBdr + "; background:" + cBg + "; padding:10px; border-radius:8px; text-align:center;'>"
          + "<div style='font-size:12px; font-weight:600;'>" + tr.tramo + " días</div>"
          + "<div style='font-size:18px; font-weight:800; margin:2px 0;'>" + tr.cantidad + "</div>"
          + "<div style='font-size:11px; color:var(--texto-suave);'>" + tr.pct + "%</div>"
          + "</div>";
      });
      h += "</div></div>";
    }

    h += "<h4>" + icon("calendar") + "FEP ≤30d (próximos partos)</h4>"
      + tabla(d.fep_30d, [
        ["tag", "Vaca"], ["fecha", "Servicio"], ["toro_pajilla", "Toro"],
        ["fep_calculada", "FEP", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }]
      ], "Sin partos próximos en 30 días.");
    h += "<h4>" + icon("stethoscope") + "Diagnósticos de gestación recientes</h4>"
      + tabla(d.diagnosticos, [
        ["tag", "Vaca", "text", function (v) { return "<b>" + esc(v) + "</b>"; }],
        ["fecha", "Fecha"],
        ["resultado", "Resultado", "text", function (v) { return chipEstado(v); }],
        ["dias_gestacion", "Días gest.", "text", function (v) { return v ? (v + " d") : "—"; }],
        ["metodo", "Método", "text", function (v) { return v === "ECOGRAFIA" ? "<span class='chip azul' style='font-size:11px;'>📡 Ecografía</span>" : "<span class='chip gris' style='font-size:11px;'>✋ Tacto</span>"; }],
        ["hallazgo", "Hallazgo / Notas", "text", function (v, r) {
          var hTxt = v || (r && r.detalle) || "—";
          var toro = (r && r.toro_pajuela) ? ("<br><small style='color:var(--verde-marca); font-weight:600;'>Toro: " + esc(r.toro_pajuela) + "</small>") : "";
          return esc(hTxt) + toro;
        }],
        ["responsable", "Profesional"]
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

    // --- Gaps estilo Software Ganadero (menú Reproducción) ---
    var debieron = d.debieron_parir || [];
    h += "<h4>" + icon("alert") + "Hembras que debían haber parido (FEP vencida)</h4>"
      + tabla(debieron, [
        ["tag", "Vaca", "text", function (v) { return enlaceFicha(v); }],
        ["fecha_servicio", "Servicio"],
        ["toro_pajilla", "Toro / Pajilla"],
        ["fep_calculada", "FEP", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }],
        ["dias_atraso", "Atraso", "text", function (v) { return "<span class='chip rojo'><b>" + esc(v) + " d</b></span>"; }]
      ], "Ninguna vaca con FEP vencida sin parto registrado. 🎉");

    var sinProg = d.sin_programar || [];
    h += "<h4>" + icon("calendar") + "Hembras sin programar (abiertas &gt; 60 días)</h4>"
      + tabla(sinProg, [
        ["tag", "Vaca", "text", function (v) { return enlaceFicha(v); }],
        ["nombre", "Nombre"],
        ["ultimo_parto", "Último parto", "text", function (v) { return esc(fechaCorta(v)); }],
        ["dias_abiertos", "Días abiertos", "text", function (v) { return "<span class='chip " + (v > 150 ? "rojo" : "ambar") + "'><b>" + esc(v) + " d</b></span>"; }]
      ], "Todas las vacas abiertas están programadas o dentro del periodo voluntario. 🎉");

    var celosProx = d.proyeccion_celos || [];
    h += "<h4>" + icon("flame") + "Proyección de celos (próximos 30 días)</h4>"
      + tabla(celosProx, [
        ["tag", "Vaca", "text", function (v) { return enlaceFicha(v); }],
        ["fuente", "Base"],
        ["fecha_base", "Fecha base", "text", function (v) { return esc(fechaCorta(v)); }],
        ["proximo_celo", "Próximo celo", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }],
        ["en_dias", "En", "text", function (v) { return esc(v) + " d"; }]
      ], "Sin celos proyectados en los próximos 30 días.");

    var rangoServ = d.servicios_rango || {};
    var servs = d.servicios_realizados || [];
    h += "<div class='card' style='padding:14px 16px; margin:12px 0; background:var(--superficie); border-left:5px solid var(--azul-marca);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<div style='font-size:14px; font-weight:700; display:flex; align-items:center; gap:6px;'>" + icon("clipboard", 16) + "Servicios realizados</div>"
      + "<form id='form-repro-rango-serv' style='display:flex; gap:6px; align-items:flex-end; flex-wrap:wrap;'>"
      + "<label style='font-size:11.5px; font-weight:600;'>Desde<br><input id='repro-serv-desde' type='date' value='" + esc(rangoServ.desde || "") + "' style='padding:6px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label style='font-size:11.5px; font-weight:600;'>Hasta<br><input id='repro-serv-hasta' type='date' value='" + esc(rangoServ.hasta || "") + "' style='padding:6px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<button type='submit' class='tema-btn' style='padding:6px 12px; font-weight:700; border-radius:6px;'>Filtrar</button>"
      + "</form></div>"
      + tabla(servs, [
        ["fecha", "Fecha", "text", function (v) { return esc(fechaCorta(v)); }],
        ["tag", "Vaca", "text", function (v) { return enlaceFicha(v); }],
        ["tipo_servicio", "Tipo"],
        ["toro_pajilla", "Toro / Pajilla"],
        ["inseminador", "Técnico"],
        ["resultado_diag", "Resultado", "text", function (v) { return v ? chipEstado(v) : "—"; }]
      ], "Sin servicios registrados en el rango.")
      + "</div>";

    var entoradas = d.novillas_entoradas || [];
    h += "<h4>" + icon("cow") + "Novillas entoradas (primer parto, últimos 12 meses)</h4>"
      + tabla(entoradas, [
        ["tag", "Animal", "text", function (v) { return enlaceFicha(v); }],
        ["nombre", "Nombre"],
        ["primer_parto", "Primer parto", "text", function (v) { return esc(fechaCorta(v)); }],
        ["edad_primer_parto_meses", "Edad 1er parto", "text", function (v) { return v != null ? (esc(v) + " m") : "—"; }],
        ["estado_reproductivo", "Estado actual"]
      ], "Sin novillas entoradas en los últimos 12 meses.");

    var torosEstado = d.reproductores_estado || [];
    h += "<h4>" + icon("cow") + "Reproductores en servicio / descanso</h4>"
      + tabla(torosEstado, [
        ["tag", "Toro", "text", function (v) { return enlaceFicha(v); }],
        ["nombre", "Nombre"],
        ["raza", "Raza"],
        ["estado", "Estado", "text", function (v) { return v === "EN_SERVICIO" ? "<span class='chip verde'><b>En servicio</b></span>" : "<span class='chip gris'>En descanso</span>"; }],
        ["motivo", "Motivo"],
        ["tag", "", "text", function (v, t) { return botonToroEstado(t); }]
      ], "Sin reproductores registrados.");
    return h;
  }
  // Rangos de fecha de la prueba de comportamiento (Carne) y de servicios
  // realizados (Repro). null = usar el default del servidor.
  var _carneRango = { desde: null, hasta: null };
  var _reproRango = { desde: null, hasta: null };

  function renderCarne(d) {
    var h = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("scale", 22) + "Carne (Pesajes, Destete &amp; Comportamiento)</h3>"
      + "</div>" + erroresHtml(d);

    var k = d.kpis || {};
    h += "<div class='kpis' style='margin-bottom:14px;'>"
      + kpiIr(kpi(esc(k.sin_pesar_nunca || 0), "Nunca pesados", (k.sin_pesar_nunca > 0 ? "alerta" : "ok")), { sec: "Agenda de pesaje", filtro: "NUNCA" })
      + kpiIr(kpi(esc(k.sin_pesar_vencidos || 0), "Sin pesar > 60 d", (k.sin_pesar_vencidos > 0 ? "alerta" : "ok")), { sec: "Agenda de pesaje", filtro: "VENCIDO" })
      + kpiIr(kpi(esc(k.a_pesar_edad || 0), "Pendientes de pesar", (k.a_pesar_edad > 0 ? "alerta" : "ok")), { sec: "Agenda de pesaje" })
      + kpiIr(kpi(esc(k.destetes_12m || 0), "Destetes (12m)"), { sec: "Destete / Índice productivo" })
      + kpiIr(kpi(esc(k.proyeccion_destetes || 0), "Destetes proyectados"), { sec: "Proyección de destetes" })
      + kpiIr(kpi(esc(k.prueba_n || 0), "En prueba"), { sec: "Prueba de comportamiento" })
      + "</div>";
    h += renderListaTrabajo(d.tareas, ltClaves("carne"), "Lista de trabajo · Carne");

    // 1) Agenda de pesaje: una sola lista (nunca pesados + vencidos por edad),
    // agrupada por potrero porque así se sale a pesar.
    var aPesar = d.a_pesar_edad || [];
    var nActivos = k.activos || 0;
    h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie); border-left:5px solid var(--azul-marca);'>"
      + "<div style='font-size:14px; font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:6px;'>" + icon("scale", 16) + "Agenda de pesaje</div>"
      + "<p class='aviso' style='margin:0 0 8px;'>Frecuencia: crías &lt;8 m cada 30 d · levantes 8-18 m cada 60 d · adultos &gt;18 m cada 90 d.</p>";
    if (!aPesar.length) {
      h += vacio("Ningún animal activo tiene su pesaje vencido. 🎉");
    } else {
      if (nActivos && aPesar.length >= nActivos * 0.9) {
        h += "<p class='aviso' style='margin:0 0 10px;'>⚠️ Casi todo el hato (" + esc(aPesar.length) + " de " + esc(nActivos)
          + ") está sin pesaje reciente. Conviene empezar por las crías y los levantes, que son los que más cambian de peso.</p>";
      }
      var cont = { cat: {}, est: { NUNCA: 0, VENCIDO: 0 } };
      aPesar.forEach(function (a) {
        cont.cat[a.categoria] = (cont.cat[a.categoria] || 0) + 1;
        cont.est[a.estado_pesaje] = (cont.est[a.estado_pesaje] || 0) + 1;
      });
      var CAT_NOMBRE = { CRIA: "Crías", LEVANTE: "Levantes", ADULTO: "Adultos", SIN_EDAD: "Sin fecha nac." };
      h += "<div class='gen-filtros' data-grupo-filtro='cat'><button type='button' class='chip btn-filtro-pes act' data-filtro='cat' data-valor='TODOS'>Todos " + aPesar.length + "</button>";
      ["CRIA", "LEVANTE", "ADULTO", "SIN_EDAD"].forEach(function (c) {
        if (cont.cat[c]) h += "<button type='button' class='chip btn-filtro-pes' data-filtro='cat' data-valor='" + c + "'>" + CAT_NOMBRE[c] + " " + cont.cat[c] + "</button>";
      });
      h += "</div><div class='gen-filtros'><button type='button' class='chip btn-filtro-pes act' data-filtro='est' data-valor='TODOS'>Cualquier estado</button>"
        + (cont.est.NUNCA ? "<button type='button' class='chip btn-filtro-pes' data-filtro='est' data-valor='NUNCA'>Nunca pesados " + cont.est.NUNCA + "</button>" : "")
        + (cont.est.VENCIDO ? "<button type='button' class='chip btn-filtro-pes' data-filtro='est' data-valor='VENCIDO'>Pesaje vencido " + cont.est.VENCIDO + "</button>" : "")
        + "</div>";

      var porPot = {}, pots = [];
      aPesar.forEach(function (a) {
        var p = a.potrero || "Sin potrero";
        if (!porPot[p]) { porPot[p] = []; pots.push(p); }
        porPot[p].push(a);
      });
      pots.sort(function (x, y) { return porPot[y].length - porPot[x].length || x.localeCompare(y); });
      var abrir = aPesar.length <= 30;
      pots.forEach(function (p) {
        var filas = porPot[p];
        h += "<details class='gen-grupo pes-grupo'" + (abrir ? " open" : "") + "><summary><span>" + esc(p) + "</span>"
          + "<b class='pes-grupo-n'>" + filas.length + "</b><small>animales</small></summary>";
        filas.forEach(function (a) {
          var detalle = a.estado_pesaje === "NUNCA"
            ? "<span class='chip gris'>Nunca pesado</span>"
            : "<span class='chip ambar'>Vencido hace " + esc(edadCorta(a.dias_vencido)) + "</span> <small>último " + esc(fechaCorta(a.ultimo_pesaje)) + "</small>";
          h += "<div class='fila-pes' data-cat='" + esc(a.categoria) + "' data-est='" + esc(a.estado_pesaje) + "'>"
            + "<div class='fila-pes-cab'><span>" + enlaceFicha(a.tag) + (a.nombre ? " <small>" + esc(a.nombre) + "</small>" : "") + "</span>"
            + "<small>" + (a.edad_dias != null ? esc(edadCorta(a.edad_dias)) : "edad ?") + " · " + esc(CAT_NOMBRE[a.categoria] || "") + "</small></div>"
            + "<div>" + detalle + "</div></div>";
        });
        h += "</details>";
      });
      h += "<p class='aviso' id='pes-sin-resultados' hidden>Ningún animal coincide con el filtro.</p>";
    }
    h += "</div>";

    // 3) Destete / Índice productivo
    var destetes = d.destetes || [];
    var indices = d.indice_productivo || [];
    h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie); border-left:5px solid var(--verde-marca);'>"
      + "<div style='font-size:14px; font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:6px;'>" + icon("calf", 16) + "Destete / Índice productivo (últimos 12 meses)</div>"
      + tabla(destetes, [
        ["fecha", "Destete", "text", function (v) { return esc(fechaCorta(v)); }],
        ["tag", "Cría", "text", function (v) { return enlaceFicha(v); }],
        ["madre", "Madre", "text", function (v) { return v ? enlaceFicha(v) : "—"; }],
        ["edad_destete_dias", "Edad (d)", "text", function (v) { return v != null ? esc(v) : "—"; }],
        ["peso_kg", "Peso real", "text", function (v) { return v != null ? (esc(v) + " kg") : "—"; }],
        ["peso_ajustado_205", "Ajustado 205d", "text", function (v) { return v != null ? ("<b>" + esc(v) + " kg</b>") : "<span class='chip gris'>sin ajuste</span>"; }],
        ["gmd_predestete_g_dia", "GMD pre-destete", "text", function (v) { return v != null ? (esc(v) + " g/d") : "—"; }]
      ], "Sin destetes en los últimos 12 meses.")
      + "<div style='font-size:12px; font-weight:700; color:var(--texto-suave); margin:12px 0 4px; text-transform:uppercase;'>Índice productivo por vaca (% vs promedio del hato)</div>"
      + tabla(indices, [
        ["madre", "Vaca", "text", function (v) { return enlaceFicha(v); }],
        ["nombre", "Nombre"],
        ["n_crias", "Crías"],
        ["peso_ajustado_prom", "Peso ajustado prom.", "text", function (v) { return esc(v) + " kg"; }],
        ["indice_pct", "Índice", "text", function (v) { return v != null ? ("<span class='chip " + (v >= 100 ? "verde" : (v >= 90 ? "ambar" : "rojo")) + "'><b>" + esc(v) + "%</b></span>") : "—"; }]
      ], "Sin crías con peso ajustable (falta peso al nacer o al destete).")
      + "</div>";

    // 4) Proyección de destetes
    var proy = d.proyeccion_destetes || [];
    var proyMes = d.proyeccion_destetes_mes || [];
    h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie); border-left:5px solid var(--azul-marca);'>"
      + "<div style='font-size:14px; font-weight:700; margin-bottom:6px; display:flex; align-items:center; gap:6px;'>" + icon("calendar", 16) + "Proyección de destetes (FEP + 205d)</div>";
    if (proyMes.length) {
      h += "<div style='display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px;'>"
        + proyMes.map(function (m) { return "<span class='chip azul'>" + esc(m.mes) + ": <b>" + esc(m.n) + "</b></span>"; }).join("")
        + "</div>";
    }
    h += tabla(proy, [
        ["tag", "Vaca", "text", function (v) { return enlaceFicha(v); }],
        ["nombre", "Nombre"],
        ["base", "Base"],
        ["fep", "FEP", "text", function (v) { return esc(fechaCorta(v)); }],
        ["destete_estimado", "Destete estimado", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }]
      ], "Sin vacas preñadas con destete proyectado.")
      + "<div style='font-size:11.5px; color:var(--texto-suave); margin-top:6px;'>Estimación: FEP + 205 días. La fecha real puede variar por adelanto o atraso del parto.</div>"
      + "</div>";

    // 5) Prueba de comportamiento
    var pc = d.prueba_comportamiento || {};
    var animalesPC = pc.animales || [];
    h += "<div class='card' style='padding:16px; margin-bottom:14px; background:var(--superficie); border-left:5px solid #8b5cf6;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<div style='font-size:14px; font-weight:700; display:flex; align-items:center; gap:6px;'>" + icon("weight", 16) + "Prueba de comportamiento (ranking GMD)</div>"
      + "<form id='form-carne-rango' style='display:flex; gap:6px; align-items:flex-end; flex-wrap:wrap;'>"
      + "<label style='font-size:11.5px; font-weight:600;'>Desde<br><input id='carne-desde' type='date' value='" + esc(pc.desde || "") + "' style='padding:6px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label style='font-size:11.5px; font-weight:600;'>Hasta<br><input id='carne-hasta' type='date' value='" + esc(pc.hasta || "") + "' style='padding:6px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<button type='submit' class='tema-btn' style='padding:6px 12px; font-weight:700; border-radius:6px;'>Aplicar</button>"
      + "</form></div>"
      + "<div style='font-size:12px; color:var(--texto-suave); margin-bottom:8px;'>Machos activos con 2+ pesajes en el rango. GMD del lote: <b>"
      + (pc.gmd_promedio != null ? (esc(pc.gmd_promedio) + " g/d") : "—") + "</b>"
      + (pc.negativos ? (" · <span class='chip rojo'>" + esc(pc.negativos) + " con GMD negativa</span>") : "") + ".</div>"
      + tabla(animalesPC, [
        ["tag", "Animal", "text", function (v) { return enlaceFicha(v); }],
        ["nombre", "Nombre"],
        ["raza", "Raza"],
        ["peso_inicial", "Peso inicial", "text", function (v) { return v != null ? (esc(v) + " kg") : "—"; }],
        ["peso_final", "Peso final", "text", function (v) { return v != null ? (esc(v) + " kg") : "—"; }],
        ["dias_prueba", "Días", "text", function (v) { return esc(v) + " d"; }],
        ["gmd_g_dia", "GMD", "text", function (v) { return "<span class='chip " + (v >= 0 ? "verde" : "rojo") + "'><b>" + esc(v) + " g/d</b></span>"; }]
      ], "Ningún macho activo con 2+ pesajes en el rango seleccionado.")
      + "</div>";
    return h;
  }

  // Edad o lapso en días → "12 d", "8 m", "7 a".
  function edadCorta(dias) {
    var n = Number(dias) || 0;
    if (n < 60) return n + " d";
    if (n < 730) return Math.floor(n / 30.4) + " m";
    return Math.floor(n / 365.25) + " a";
  }

  function bindCarne() {
    bindListaTrabajo();
    var filtro = { cat: "TODOS", est: "TODOS" };
    var botones = qa(".btn-filtro-pes");
    function aplicar() {
      var total = 0;
      qa(".pes-grupo").forEach(function (gr) {
        var n = 0;
        gr.querySelectorAll(".fila-pes").forEach(function (f) {
          var ok = (filtro.cat === "TODOS" || f.getAttribute("data-cat") === filtro.cat)
            && (filtro.est === "TODOS" || f.getAttribute("data-est") === filtro.est);
          f.hidden = !ok;
          if (ok) n++;
        });
        gr.hidden = !n;
        var cnt = gr.querySelector(".pes-grupo-n");
        if (cnt) cnt.textContent = n;
        total += n;
      });
      var sr = q("#pes-sin-resultados");
      if (sr) sr.hidden = total > 0;
    }
    botones.forEach(function (b) {
      b.addEventListener("click", function () {
        var tipo = b.getAttribute("data-filtro");
        filtro[tipo] = b.getAttribute("data-valor");
        botones.forEach(function (o) {
          if (o.getAttribute("data-filtro") === tipo) o.classList.toggle("act", o === b);
        });
        aplicar();
      });
    });
    var form = document.getElementById("form-carne-rango");
    if (form && !form.__bound) {
      form.__bound = true;
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        _carneRango.desde = (document.getElementById("carne-desde") || {}).value || null;
        _carneRango.hasta = (document.getElementById("carne-hasta") || {}).value || null;
        cargar(true);
      });
    }
  }

  function renderSanidad(d) {
    var h = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("shieldPlus") + "Sanidad</h3>"
      + barraDescargaSeccion("sanidad", "Sanidad")
      + "</div>" + erroresHtml(d);
    // Alta operativa directa (misma tabla que Telegram/Captura vía POST /api/sanidad/tratamiento).
    var hoySan = new Date().toISOString().slice(0, 10);
    h += "<div class='card' style='padding:12px 14px; margin-bottom:12px; border-left:4px solid var(--verde-marca);'>"
      + "<b>" + icon("syringe", 14) + " Registrar tratamiento</b>"
      + "<div style='font-size:12px; color:var(--texto-suave); margin:2px 0 8px;'>Solo animales ACTIVOS. Calcula solo el retiro (leche/carne) con días restantes.</div>"
      + "<form id='form-nuevo-tratamiento' style='display:flex; flex-direction:column; gap:8px;'>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap;'>"
      + "<label style='flex:1; min-width:110px; font-size:13px; font-weight:600;'>Arete*<br><input id='san-tag' placeholder='ej. 47' list='dl-tags' required autocomplete='off' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:16px; min-height:44px; box-sizing:border-box;'></label>"
      + "<label style='flex:1; min-width:130px; font-size:13px; font-weight:600;'>Fecha<br><input id='san-fecha' type='date' value='" + hoySan + "' required style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:16px; min-height:44px; box-sizing:border-box;'></label>"
      + "</div>"
      + "<label style='font-size:13px; font-weight:600;'>Producto / Fármaco*<br><input id='san-producto' placeholder='ej. Oxitetraciclina 20%' required maxlength='120' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:16px; min-height:44px; box-sizing:border-box;'></label>"
      + "<label style='font-size:13px; font-weight:600;'>Principio activo (si figura en frasco)<br><input id='san-principio' placeholder='ej. Oxitetraciclina' maxlength='120' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:16px; min-height:44px; box-sizing:border-box;'></label>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap;'>"
      + "<label style='flex:1; min-width:110px; font-size:13px; font-weight:600;'>Dosis<br><input id='san-dosis' placeholder='ej. 20 ml' maxlength='60' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:16px; min-height:44px; box-sizing:border-box;'></label>"
      + "<label style='flex:1; min-width:110px; font-size:13px; font-weight:600;'>Vía<br><select id='san-via' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:16px; min-height:44px; box-sizing:border-box;'><option value='IM'>IM</option><option value='SC'>SC</option><option value='IV'>IV</option><option value='ORAL'>Oral</option><option value='POUR-ON'>Pour-on</option></select></label>"
      + "</div>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap;'>"
      + "<label style='flex:1; min-width:110px; font-size:13px; font-weight:600;'>Retiro leche (días)<br><input id='san-ret-leche' type='number' min='0' max='365' value='0' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:16px; min-height:44px; box-sizing:border-box;'></label>"
      + "<label style='flex:1; min-width:110px; font-size:13px; font-weight:600;'>Retiro carne (días)<br><input id='san-ret-carne' type='number' min='0' max='365' value='0' style='width:100%; margin-top:4px; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-size:16px; min-height:44px; box-sizing:border-box;'></label>"
      + "</div>"
      + "<button type='submit' id='btn-san-guardar' class='btn-guardar-manga' style='margin-top:4px;'>Guardar tratamiento</button>"
      + "<div id='san-form-feedback' role='status' aria-live='polite' style='font-size:13px;'></div>"
      + "</form></div>";
    h += renderListaTrabajo(d.tareas, ltClaves("sanidad"), "Lista de trabajo · Sanidad");
    h += "<h4>" + icon("alert") + "Retiros activos (leche / carne)</h4>";
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
        var prod = esc(r.producto) + (r.principio_activo ? "<br><small style='color:var(--texto-suave);'>" + esc(r.principio_activo) + "</small>" : "");
        return "<tr><td><b>" + esc(r.tag) + "</b></td><td>" + prod + "</td>" + celda("fecha_fin_retiro_leche") + celda("fecha_fin_retiro_carne") + "</tr>";
      }).join("");
      h += "</table></div>";
    }
    h += "<h4>" + icon("pill") + "Últimos tratamientos</h4>"
      + tabla(d.ultimos_tratamientos, [
        ["tag", "Animal"], ["fecha", "Fecha"], ["producto", "Producto"],
        ["principio_activo", "P. activo"], ["dosis", "Dosis"], ["via", "Vía"]
      ], "Sin tratamientos registrados.");
    return h;
  }
  function bindSanidad() {
    bindListaTrabajo();
    // Alta de tratamiento desde Sanidad (POST /api/sanidad/tratamiento).
    var formT = document.getElementById("form-nuevo-tratamiento");
    if (formT && !formT.__bound) {
      formT.__bound = true;
      formT.addEventListener("submit", function (e) {
        e.preventDefault();
        var fb = document.getElementById("san-form-feedback");
        var btn = document.getElementById("btn-san-guardar");
        var tag = ((document.getElementById("san-tag") || {}).value || "").trim();
        var producto = ((document.getElementById("san-producto") || {}).value || "").trim();
        var fecha = ((document.getElementById("san-fecha") || {}).value || "").trim();
        var principio = ((document.getElementById("san-principio") || {}).value || "").trim() || null;
        var dosis = ((document.getElementById("san-dosis") || {}).value || "").trim() || null;
        var via = ((document.getElementById("san-via") || {}).value || "").trim() || null;
        var rLeche = parseInt((document.getElementById("san-ret-leche") || {}).value || 0, 10) || 0;
        var rCarne = parseInt((document.getElementById("san-ret-carne") || {}).value || 0, 10) || 0;
        if (!tag) { if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>⚠️ Escriba el arete del animal.</span>"; return; }
        if (!producto) { if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>⚠️ Escriba el producto aplicado.</span>"; return; }
        if (!fecha) { if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>⚠️ Elija la fecha.</span>"; return; }
        if (btn) btn.disabled = true;
        if (fb) fb.textContent = "⏳ Guardando...";
        fetch("/api/sanidad/tratamiento", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tag: tag, producto: producto, principio_activo: principio, dosis: dosis, via: via, fecha: fecha, dias_retiro_leche: rLeche, dias_retiro_carne: rCarne })
        }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
          .then(function (out) {
            if (btn) btn.disabled = false;
            if (!out.ok || !out.j.ok) {
              if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>❌ " + esc((out.j && out.j.error) || "No se pudo guardar.") + "</span>";
              return;
            }
            mostrarToast("Tratamiento guardado", "verde");
            vibrarConfirmacion();
            cargar(true);
            actualizarBadges();
          }).catch(function (err) {
            if (btn) btn.disabled = false;
            if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>❌ Sin conexión: " + esc(err.message || err) + "</span>";
          });
      });
    }
  }
