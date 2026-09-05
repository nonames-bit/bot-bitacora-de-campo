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

  /* ---------- Vistas principales ---------- */
  function renderTablero(d) {
    var pot = d.potrero_filtro ? " — potrero: <b>" + esc(d.potrero_filtro) + "</b>" : "";
    var h = "<h3>🐮 Tablero finca" + pot + "</h3>";
    h += "<div class='kpis'>"
      + kpi(d.activos, "Activos ♀♂") + kpi(d.hembras, "Hembras") + kpi(d.machos, "Machos")
      + kpi(d.partos_7d, "Partos 7d", d.partos_7d > 0 ? "alerta" : "")
      + kpi(d.celos_7d, "Celos 7d") + kpi(d.servicios_7d, "Serv. 7d")
      + kpi(d.retiros_activos, "Retiros", d.retiros_activos > 0 ? "alerta" : "") + "</div>";
    h += erroresHtml(d);
    h += grafico("evolucion", "Evolución del rebaño") + grafico("categorias", "Categorías del hato");
    h += "<h4>Distribución por potrero (toca para filtrar)</h4>";
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
    var h = "<h3>🤰 Reproducción</h3>" + erroresHtml(d) + grafico("reproductivo_hato", "Estado reproductivo del hato");
    h += "<h4>📅 FEP ≤30d (próximos partos)</h4>"
      + tabla(d.fep_30d, [
        ["tag", "Vaca"], ["fecha", "Servicio"], ["toro_pajilla", "Toro"],
        ["fep_calculada", "FEP", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }]
      ], "Sin partos próximos en 30 días.");
    h += "<h4>Diagnósticos de gestación recientes</h4>"
      + tabla(d.diagnosticos, [
        ["tag", "Vaca"], ["fecha", "Fecha"],
        ["resultado", "Resultado", "text", function (v) { return chipEstado(v); }],
        ["dias_gestacion", "Días gest."]
      ], "Sin diagnósticos recientes.");
    h += "<h4>Celos recientes</h4>"
      + tabla(d.celos_recientes, [["tag", "Vaca"], ["fecha", "Fecha"], ["am_pm", "AM/PM"]], "Sin celos recientes.");
    h += "<h4>Eco / Palpación pendientes</h4>"
      + tabla(d.eco_palp_pendientes, [
        ["tipo_alerta", "Tipo"],
        ["fecha_programada", "Fecha", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }],
        ["descripcion", "Detalle"]
      ], "Sin eco/palpaciones programadas.");
    return h;
  }
  function renderSanidad(d) {
    var h = "<h3>💉 Sanidad</h3>" + erroresHtml(d) + "<h4>⛔ Retiros activos (leche / carne)</h4>";
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
    h += "<h4>Últimos tratamientos</h4>"
      + tabla(d.ultimos_tratamientos, [
        ["tag", "Animal"], ["fecha", "Fecha"], ["producto", "Producto"],
        ["dosis", "Dosis"], ["via", "Vía"]
      ], "Sin tratamientos registrados.");
    return h;
  }
  function renderPasturas(d) {
    var h = "<h3>🌿 Pasturas (Voisin)</h3>" + erroresHtml(d);
    h += grafico("mapa_potreros", "Mapa de potreros") + grafico("ocupacion", "Ocupación de potreros") + grafico("aforo", "Aforo de forraje");
    h += "<h4>Ocupación y reposo por potrero</h4>";
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
    h += "<h4>🛰️ NDVI reciente (satélite)</h4>"
      + tabla(d.ndvi_reciente, [
        ["potrero", "Potrero"], ["fecha", "Fecha"],
        ["ndvi_promedio", "NDVI", "text", function (v) {
          var n = Number(v);
          var c = n >= 0.6 ? "verde" : n >= 0.4 ? "ambar" : n > 0 ? "rojo" : "gris";
          return "<span class='chip " + c + "'>" + esc(v) + "</span>";
        }]
      ], "Sin lecturas NDVI recientes.");
    return h;
  }
  function renderLeche(d) {
    var total = 0;
    (d.serie_tanque || []).forEach(function (f) { total += Number(f.litros) || 0; });
    var h = "<h3>🥛 Leche (tanque)</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.controles.length, "Controles") + kpi(total.toFixed(0), "L últimos 30 días");
    var mejor = (d.ranking_vacas && d.ranking_vacas.length) ? d.ranking_vacas[0] : null;
    if (mejor) {
      h += kpi(esc(mejor.tag), "Mejor vaca", "ok");
    }
    h += "</div>";
    h += grafico("leche_total", "Producción total de leche") + grafico("eficiencia_lechera", "Eficiencia lechera");
    h += "<h4>Ranking de vacas por litros (acumulado)</h4>"
      + tabla(d.ranking_vacas, [
        ["tag", "Vaca"], ["total_litros", "Total L", "num"], ["controles", "Controles", "num"],
        ["ultima_fecha", "Último control", "text", function (v) { return v ? esc(fechaCorta(v)) : "—"; }]
      ], "Sin producción por vaca registrada.");
    h += "<h4>Producción por día</h4>"
      + tabla(d.serie_tanque, [["fecha", "Fecha"], ["litros", "Litros", "num"]], "Sin registros de tanque.");
    h += "<h4>Controles individuales</h4>"
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
    var h = "<h3>📊 Inventario SG</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.total_activos, "Activos totales")
      + kpi(d.total_hembras, "Hembras") + kpi(d.total_machos, "Machos")
      + kpi(d.total_sin_sexo, "Sin clasificar", d.total_sin_sexo > 0 ? "alerta" : "")
      + kpi(d.terneros_menor_12m, "Crías <12m") + "</div>";
    h += "<h4>Brackets de edad (Software Ganadero)</h4>";
    h += "<div class='tabla-scroll'><table><tr><th>Categoría</th><th>Nro</th><th>Distrib.</th><th>Acum.</th></tr>";
    (d.filas || []).forEach(function (f) {
      h += "<tr><td>" + esc(f.categoria) + "</td><td>" + esc(f.n) + "</td><td>" + esc(f.pct) + "%</td><td>" + esc(f.acum) + "%</td></tr>";
    });
    h += "</table></div>";
    return h;
  }
  function renderPoblacion(d) {
    var h = "<h3>📈 Población y edades</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.total_activos, "Activos") + kpi(d.total_hembras, "Hembras")
      + kpi(d.total_machos, "Machos") + kpi(d.edad_promedio != null ? d.edad_promedio + "a" : "—", "Edad promedio") + "</div>";
    h += "<h4>Composición por bracket de edad</h4>";
    var maxN = 1;
    (d.filas || []).forEach(function (f) { if (Number(f.n) > maxN) maxN = Number(f.n); });
    var filasBar = (d.filas || []).map(function (f) { return { categoria: f.categoria, n: f.n, pct: (Number(f.n) / maxN) * 100 }; });
    h += barrasDeFilas(filasBar, "pct", "n");
    return h;
  }
  function renderGenetica(d) {
    var h = "<h3>🧬 Composición genética (razas)</h3>" + erroresHtml(d);
    h += "<div class='kpis'>" + kpi(d.total, "Animales tipificados") + "</div>";
    if (d.filas && d.filas.length) {
      var porNombre = (d.filas || []).map(function (f) { return { categoria: f.raza_nombre || f.raza, n: f.n, pct: f.pct }; });
      h += "<h4>Distribución por raza</h4>" + barrasDeFilas(porNombre, "pct", "n");
      h += "<h4>Detalle</h4>" + tabla(d.filas, [["raza_nombre", "Raza"], ["raza", "Código"], ["n", "Cabezas", "num"], ["pct", "% del hato"]], "Sin datos.");
    } else {
      h += vacio("Sin razas registradas en el hato activo.");
    }
    return h;
  }
  function renderAgenda(d) {
    var h = "<h3>📋 Agenda próximos " + esc(d.dias) + " días</h3>" + erroresHtml(d);
    var evs = d.eventos || [];
    var urgencia = function (f) {
      if (f.faltan_dias == null) return "gris";
      return f.faltan_dias <= 0 ? "rojo" : f.faltan_dias <= 2 ? "ambar" : "verde";
    };
    var chipUrg = function (v) {
      return "<span class='chip " + urgencia(v) + "'>" + esc(v.faltan_dias != null ? (v.faltan_dias <= 0 ? "HOY" : v.faltan_dias + "d") : "?") + "</span>";
    };
    if (evs.length) {
      h += "<h4>🔔 Alertas programadas</h4><div class='tabla-scroll'><table><tr><th>Fecha</th><th>Tipo</th><th>Animal</th><th>Detalle</th><th>En</th></tr>";
      evs.forEach(function (e) {
        h += "<tr><td><b>" + esc(e.fecha) + "</b></td><td>" + esc(e.etiqueta) + "</td><td>" + esc(e.tag || "—") + "</td><td>" + esc(e.descripcion || "—") + "</td><td>" + chipUrg(e) + "</td></tr>";
      });
      h += "</table></div>";
    } else {
      h += "<p class='aviso'>🔔 Sin alertas programadas en los próximos " + esc(d.dias) + " días.</p>";
    }
    var ret = d.retiros || [];
    if (ret.length) {
      h += "<h4>⛔ Retiros sanitarios activos</h4><div class='tabla-scroll'><table><tr><th>Animal</th><th>Producto</th><th>Fin leche</th><th>Fin carne</th></tr>";
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

  /* ---------- Ficha con pestañas ---------- */
  var TABS = [
    { id: "general", label: "🐮 General" },
    { id: "repro", label: "🤰 Reproducción" },
    { id: "sanidad", label: "💉 Tratamientos" },
    { id: "leche", label: "🥛 Leche" },
    { id: "pesos", label: "⚖️ Pesos" }
  ];
  // HTML del panel "identificar por foto del arete" (solo en el dashboard,
  // no en la página /ficha/<tag> que llega desde el QR ya identificado).
  function identPanelHtml() {
    return "<div class='card ident-box' style='margin-bottom:10px'>"
      + "<b>📷 Identificar por foto del arete</b>"
      + "<p class='aviso' style='margin:4px 0'>Tome la foto del arete con el celular o pegue un código RFID/arete arriba y pulse Cargar.</p>"
      + "<input type='file' id='f-ident-foto' accept='image/*' capture='environment' style='min-height:40px'>"
      + "<button id='btn-ident' type='button'>🔎 Identificar</button>"
      + "<span id='ident-estado' class='aviso'></span>"
      + "<div id='ident-resultado'></div></div>";
  }
  function fichaHtml(f, showIdent) {
    var head = "<div class='ficha-head'>";
    if (f.fotos && f.fotos.length && f.fotos[0].url) {
      head += "<img class='avatar' src='" + esc(f.fotos[0].url) + "' alt='foto' onerror='this.style.display=\"none\"'>";
    }
    head += "<div class='datos'><b>🐮 " + esc(f.tag) + " " + esc(f.nombre || "") + "</b><br>"
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
    if (s === "PREÑADA" || s === "PREGNANT") return "<span class='chip verde'>🤰 PREÑADA</span>";
    if (s === "VACIA" || s === "VACÍA") return "<span class='chip ambar'>⭕ VACÍA</span>";
    if (s === "FALLIDO") return "<span class='chip rojo'>✖ FALLIDO</span>";
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
        h += "<p class='aviso'>📅 FEP (parto estimado): <b>" + esc(fechaCorta(f.ultimo_servicio.fep_calculada)) + "</b></p>";
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
        h3 += "<p class='aviso'>🥛 " + esc(lac.estado) + " · <b>" + esc(lac.del_dias) + "</b> DEL (parto " + esc(lac.fecha_parto) + ")</p>";
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
            var n = Number(v);
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
    return "<h4>General</h4>" + fotos + qr;
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
  function skeleton(target) {
    target = target || vista;
    if (target) target.innerHTML = "<div class='skeleton h2'></div><div class='skeleton'></div><div class='skeleton'></div><div class='skeleton' style='width:70%'></div>";
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
  function abrirFicha(tag, target, showIdent) {
    skeleton(target);
    fetchJSON("/api/ficha/" + encodeURIComponent(tag), function (f) {
      if (!f.existe) {
        if (target) target.innerHTML = "<h3>🔎 Ficha animal</h3><p>❌ Sin registro para <b>" + esc(tag) + "</b>.</p>"
          + "<p class='aviso'>💡 Si viene de escanear un arete, puede que el tag aún no esté en la base. "
          + "Pruebe escribiendo el número sin guiones (ej. " + esc(String(tag).replace(/\D/g, "") || tag) + ").</p>";
        return;
      }
      window.__ultimaFicha = f;
      if (target) target.innerHTML = fichaHtml(f, !!showIdent);
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
        return "<button data-tag='" + esc(s.tag) + "' class='chip' style='font-size:13px'>🐮 " + esc(s.tag)
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
  function bindIdent() {
    var btn = document.getElementById("btn-ident");
    var file = document.getElementById("f-ident-foto");
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
    if (!v) return;
    clearTimeout(_deb);
    _deb = setTimeout(function () { sugerirDesde(v); }, 250);
  }
  function cargar() {
    if (actual === "ficha") {
      var t = (q("#f-tag") && q("#f-tag").value || "").trim();
      if (!t) { if (vista) vista.innerHTML = "<h3>🔎 Identificar / Ficha animal</h3><p class='aviso'>Escribe un arete, RFID o nombre (ej. 47, N069, JA26) y pulsa Cargar — o usa el panel de foto de abajo.</p>" + identPanelHtml(); if (vista) bindIdent(); return; }
      abrirFicha(t, vista, true);
      return;
    }
    var pot = (q("#f-potrero") && q("#f-potrero").value || "").trim();
    var url = "/api/" + actual + (pot && actual === "tablero" ? "?potrero=" + encodeURIComponent(pot) : "");
    skeleton(vista);
    fetchJSON(url, function (d) {
      if (!vista) return;
      if (actual === "tablero") vista.innerHTML = renderTablero(d);
      else if (actual === "repro") vista.innerHTML = renderRepro(d);
      else if (actual === "sanidad") vista.innerHTML = renderSanidad(d);
      else if (actual === "pasturas") vista.innerHTML = renderPasturas(d);
      else if (actual === "leche") vista.innerHTML = renderLeche(d);
      else if (actual === "inventario") vista.innerHTML = renderInventario(d);
      else if (actual === "poblacion") vista.innerHTML = renderPoblacion(d);
      else if (actual === "genetica") vista.innerHTML = renderGenetica(d);
      else if (actual === "agenda") vista.innerHTML = renderAgenda(d);
    }, vista);
  }

  qa("nav > button").forEach(function (b) {
    b.addEventListener("click", function () {
      qa("nav > button").forEach(function (x) { x.classList.remove("act"); });
      b.classList.add("act");
      actual = b.getAttribute("data-v");
      cargar();
    });
  });
  var btn = document.getElementById("btn-cargar");
  if (btn) btn.addEventListener("click", cargar);
  // Enter en los campos de filtro dispara Cargar.
  ["f-potrero", "f-tag"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("keydown", function (e) { if (e.key === "Enter") cargar(); });
  });
  // Autocompletar: tecleo en tag/potrero consulta /api/buscar y llena datalist.
  ["f-potrero", "f-tag"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("input", onInputSugerir);
  });

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
    if (document.hidden || navigator.onLine === false || actual === "ficha") return;
    cargar();
  }, 60000);

  /* ---------- Modo oscuro ---------- */
  var temaBtn = document.getElementById("btn-tema");
  function aplicarTema(modo) {
    if (modo === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else if (modo === "light") document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.removeAttribute("data-theme");
    try { localStorage.setItem("pwa_tema", modo || ""); } catch (e) { /* noop */ }
  }
  function temaInicial() {
    try { return localStorage.getItem("pwa_tema") || ""; } catch (e) { return ""; }
  }
  aplicarTema(temaInicial());
  if (temaBtn) {
    var actualizarIconoTema = function () { temaBtn.textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "🌙" : "☀️"; };
    actualizarIconoTema();
    temaBtn.addEventListener("click", function () {
      var oscuro = document.documentElement.getAttribute("data-theme") !== "dark";
      aplicarTema(oscuro ? "dark" : "light");
      actualizarIconoTema();
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
    abrirFicha(tag, fb, false); // QR ya identifica el animal: sin panel de foto
  } else {
    arrancarDesdeUrl();
  }
})();
