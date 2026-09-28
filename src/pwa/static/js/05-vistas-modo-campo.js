  /* ---------- Vistas principales ---------- */
  function htmlClimaMm(opts) {
    var lluvia = Number(opts.lluvia_mm) || 0;
    var prob = opts.prob_lluvia_pct;
    var ahora = !!opts.esta_lloviendo || Number(opts.lluvia_actual_mm) > 0.1;
    var alerta = ahora ? "rojo" : (lluvia >= 8 ? "ambar" : "verde");
    var html = "<span class='chip " + alerta + "' style='font-size:11px;'>" + icon("droplet", 11) + esc(lluvia.toFixed(1)) + " mm</span>";
    if (ahora) html += "<span class='chip rojo' style='font-size:11px;'>Lloviendo ahora</span>";
    if (prob != null && prob !== "") {
      html += "<span style='font-size:11px; color:var(--texto-suave);'>" + esc(Math.round(prob)) + "% prob. del día</span>";
    }
    return html;
  }
  function renderResumenDiaTablero(d) {
    var clima = d.clima_hoy;
    var climaHtml;
    if (clima) {
      climaHtml = "<div style='display:flex; align-items:center; gap:6px; flex-wrap:wrap;'>"
        + "<b style='font-size:15px;'>" + esc(Math.round(clima.temp_max_c)) + "° / " + esc(clima.temp_min_c == null ? "—" : Math.round(clima.temp_min_c)) + "°</b>"
        + htmlClimaMm(clima)
        + "</div>";
    } else {
      climaHtml = "<span style='font-size:12.5px; color:var(--texto-suave);'>Sin pronóstico disponible.</span>";
    }

    var precio = d.precio_hoy;
    var precioHtml;
    if (precio) {
      var v = Number(precio.variacion_pct) || 0;
      var colorV = v > 0 ? "verde" : v < 0 ? "rojo" : "gris";
      var flecha = v > 0 ? "▲" : v < 0 ? "▼" : "—";
      var labelPlaza = precio.plaza_label || (precio.plaza === "BOGOTA" ? "Bogotá · Frig. Guadalupe" : (precio.plaza || "Bogotá · Guadalupe"));
      var labelProd = precio.producto_label || "Macho Gordo (400+ kg)";
      precioHtml = "<div style='display:flex; align-items:center; gap:6px; flex-wrap:wrap;'>"
        + "<b style='font-size:15px;'>" + fmtMoneda(precio.precio) + "/kg</b>"
        + "<span class='chip " + colorV + "' style='font-size:11px;'>" + flecha + " " + esc(Math.abs(v)) + "%</span>"
        + "</div>"
        + "<div style='font-size:11px; color:var(--texto-suave); margin-top:2px;'>" + esc(labelProd) + " · " + esc(labelPlaza) + "</div>";
    } else {
      precioHtml = "<span style='font-size:12.5px; color:var(--texto-suave);'>Sin cotizaciones registradas.</span>";
    }

    return "<div style='display:flex; gap:12px; flex-wrap:wrap; margin:10px 0 16px;'>"
      + "<div class='card' style='flex:1; min-width:180px; padding:12px 14px;'>"
      + "<div style='font-size:11px; font-weight:700; color:var(--texto-suave); text-transform:uppercase; display:flex; align-items:center; gap:5px; margin-bottom:6px;'>" + icon("rain", 13) + "Clima hoy</div>"
      + climaHtml
      + "</div>"
      + "<div class='card' style='flex:1; min-width:180px; padding:12px 14px;'>"
      + "<div style='font-size:11px; font-weight:700; color:var(--texto-suave); text-transform:uppercase; display:flex; align-items:center; justify-content:space-between; gap:5px; margin-bottom:6px;'>"
      + "<span style='display:flex; align-items:center; gap:5px;'>" + icon("scale", 13) + "Precio del día</span>"
      + "<a href='#' id='link-tablero-mercado' style='font-size:11px; font-weight:600; text-decoration:none; color:var(--verde-marca);'>Ver Subastas →</a>"
      + "</div>"
      + precioHtml
      + "</div>"
      + "</div>";
  }
  function bindTablero() {
    mostrarBannerAvisos();
    var btnVerTodos = document.getElementById("btn-ver-todos-eventos-tablero");
    if (btnVerTodos) {
      btnVerTodos.addEventListener("click", function () {
        qa(".fila-evento-extra").forEach(function (tr) { tr.style.display = ""; });
        btnVerTodos.style.display = "none";
      });
    }
    var linkMercado = document.getElementById("link-tablero-mercado");
    if (linkMercado) {
      linkMercado.addEventListener("click", function (e) {
        e.preventDefault();
        irAVista("mercado");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e2) { window.scrollTo(0, 0); }
      });
    }
  }
  /* ---------- Modo Campo (mayordomo): 4 botones grandes + hoy ---------- */
  function renderCampo() {
    var nom = (window.__usuarioActual && window.__usuarioActual.nombre) || "Mayordomo";
    var hoy = new Date();
    var fechaLarga = hoy.toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });
    var h = "<div class='campo-head'>"
      + "<div style='font-size:15px; color:var(--texto-suave); text-transform:capitalize;'>" + esc(fechaLarga) + "</div>"
      + "<div style='font-size:22px; font-weight:800;'>🤠 Hola, " + esc(nom) + "</div>"
      + "<div style='font-size:13.5px; color:var(--texto-suave);'>¿Qué vamos a hacer hoy en el corral?</div>"
      + "</div>"
      + "<div class='campo-grid'>"
      + "<button type='button' class='campo-tile campo-tile-captura' data-ir='captura'>" + icon("plus", 30) + "<b>Registrar</b><small>Parto, celo, pesaje…</small></button>"
      + "<button type='button' class='campo-tile' data-ir='agenda'>" + icon("calendar", 30) + "<b>Hoy</b><small id='campo-hoy-sub'>Ver pendientes…</small></button>"
      + "<button type='button' class='campo-tile' data-ir='ficha'>" + icon("search", 30) + "<b>Ficha</b><small>Buscar por arete</small></button>"
      + "<button type='button' class='campo-tile' data-ir='mapa'>" + icon("pin", 30) + "<b>GPS</b><small>Dónde estoy</small></button>"
      + "</div>"
      + "<div class='card campo-hoy' id='campo-hoy-box'>"
      + "<div style='font-size:15px; font-weight:800; margin-bottom:6px;'>📅 Hoy en la finca</div>"
      + "<div style='font-size:13.5px; color:var(--texto-suave);'>⏳ Cargando pendientes…</div>"
      + "</div>"
      + "<div id='campo-gps-box'></div>";
    var rol = (window.__usuarioActual && window.__usuarioActual.rol || "").toUpperCase();
    if (rol !== "TRABAJADOR") {
      h += "<button type='button' id='btn-campo-salir' class='tema-btn' style='width:100%; padding:12px; font-size:14px;'>← Volver a la vista de oficina</button>";
    }
    return h;
  }
  function bindCampo() {
    qa(".campo-tile").forEach(function (t) {
      t.addEventListener("click", function () {
        var v = t.getAttribute("data-ir");
        if (!v) return;
        try { if (navigator.vibrate) navigator.vibrate(15); } catch (eVib) {}
        // GPS sin mapa: localiza y ofrece guardar la ronda aquí mismo.
        // El mapa satelital es solo oficina (/api/mapa/datos da 403).
        if (v === "mapa") {
          localizarGPSCampo();
          try { window.scrollTo(0, document.body.scrollHeight); } catch (eSc2) {}
          return;
        }
        irAVista(v);
        cargar(true);
        try { window.scrollTo(0, 0); } catch (eSc) { window.scrollTo(0, 0); }
      });
    });
    var salir = document.getElementById("btn-campo-salir");
    if (salir) salir.addEventListener("click", function () {
      irAVista("tablero");
      cargar(true);
    });
    fetch("/api/agenda?dias=7").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (d) {
      pintarResumenCampo(d || {});
    }).catch(function () {
      var box = document.getElementById("campo-hoy-box");
      if (box) box.innerHTML = "<div style='font-size:15px; font-weight:800; margin-bottom:6px;'>📅 Hoy en la finca</div>"
        + "<div style='font-size:13.5px; color:var(--texto-suave);'>⚠️ Sin conexión: abra la Agenda cuando vuelva la señal.</div>";
    });
  }
  function pintarResumenCampo(d) {
    var box = document.getElementById("campo-hoy-box");
    if (!box) return;
    var urg = [];
    (d.eventos || []).forEach(function (e) {
      if (e.faltan_dias == null || e.faltan_dias <= 0) urg.push({ txt: (e.etiqueta || e.tipo || "Alerta"), det: e.tag ? ("Arete " + e.tag) : (e.descripcion || ""), dias: e.faltan_dias });
    });
    (d.recordatorios || []).forEach(function (r) {
      if (r.faltan_dias == null || r.faltan_dias <= 0) urg.push({ txt: r.mensaje || "Tarea", det: (r.hora ? ("Hora " + r.hora + " · ") : "") + (r.animal_tag || r.potrero_nombre || ""), dias: r.faltan_dias });
    });
    urg = urg.slice(0, 6);
    var nRet = (d.retiros || []).length;
    var sub = document.getElementById("campo-hoy-sub");
    var total = urg.length + nRet;
    if (sub) sub.textContent = total ? (total + " pendiente" + (total === 1 ? "" : "s")) : "Todo al día ✓";
    var h = "<div style='font-size:15px; font-weight:800; margin-bottom:6px;'>📅 Hoy en la finca</div>";
    if (!urg.length && !nRet) {
      h += "<div style='font-size:15px;'>✅ Todo al día. Buen trabajo en el corral.</div>";
    } else {
      h += "<div style='display:flex; flex-direction:column; gap:8px;'>"
        + urg.map(function (u) {
          var cuando = (u.dias == null) ? "Sin fecha" : (u.dias <= 0 ? (u.dias === 0 ? "Hoy" : ("Hace " + Math.abs(u.dias) + " d")) : ("En " + u.dias + " d"));
          return "<div style='background:var(--fondo); border-radius:8px; padding:10px 12px; border:1px solid var(--borde);'>"
            + "<div style='font-size:15px; font-weight:700;'>" + esc(u.txt) + "</div>"
            + "<div style='font-size:13px; color:var(--texto-suave);'>" + esc(cuando) + (u.det ? (" · " + esc(u.det)) : "") + "</div></div>";
        }).join("");
      if (nRet) {
        h += "<div style='background:var(--fondo); border-radius:8px; padding:10px 12px; border:1px solid var(--borde);'>"
          + "<div style='font-size:15px; font-weight:700;'>💉 " + nRet + " en retiro sanitario</div>"
          + "<div style='font-size:13px; color:var(--texto-suave);'>Revise leche y carne antes de entregar</div></div>";
      }
      h += "</div>";
    }
    h += "<button type='button' id='btn-campo-ver-agenda' class='tema-btn' style='width:100%; margin-top:10px; padding:12px; font-size:14px;'>Ver agenda completa →</button>";
    box.innerHTML = h;
    var btnA = document.getElementById("btn-campo-ver-agenda");
    if (btnA) btnA.addEventListener("click", function () { irAVista("agenda"); cargar(true); });
  }
  // GPS del modo campo (equivale al /aqui del bot): detecta el potrero
  // donde está parado y ofrece guardar la ronda. Sin mapa: funciona con
  // cualquier rol y con guantes (botones grandes).
  function localizarGPSCampo() {
    var box = document.getElementById("campo-gps-box");
    if (!box) return;
    if (!navigator.geolocation) {
      box.innerHTML = "<div class='card campo-hoy'>📍 Este equipo no da ubicación GPS.</div>";
      return;
    }
    box.innerHTML = "<div class='card campo-hoy'>📍 Localizando… acepte el permiso de ubicación del navegador.</div>";
    try { if (navigator.vibrate) navigator.vibrate(15); } catch (eVib2) {}
    navigator.geolocation.getCurrentPosition(function (pos) {
      var lat = pos.coords.latitude;
      var lon = pos.coords.longitude;
      fetch("/api/gps/potrero", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: lat, lon: lon })
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d || !d.detectado) {
          box.innerHTML = "<div class='card campo-hoy'>📍 " + esc((d && d.mensaje) || "Ubicación fuera de los potreros.") + "</div>";
          return;
        }
        var pot = d.potrero || {};
        box.innerHTML = "<div class='card campo-hoy' style='border-left:5px solid var(--verde-marca);'>"
          + "<div style='font-size:15px; font-weight:800;'>📍 Estás en " + esc(pot.nombre || pot.codigo || "potrero") + "</div>"
          + "<div style='font-size:13.5px; color:var(--texto-suave); margin:2px 0 10px;'>"
          + esc(d.total_animales || 0) + " animales aquí · " + esc(Number(lat).toFixed(5)) + ", " + esc(Number(lon).toFixed(5)) + "</div>"
          + "<button type='button' id='btn-campo-guardar-ronda' class='tema-btn' style='width:100%; padding:14px; font-size:15px; background:var(--verde-marca); color:#fff; font-weight:700; border:none;'>Guardar ronda aquí</button>"
          + "</div>";
        var btnG = document.getElementById("btn-campo-guardar-ronda");
        if (btnG) btnG.addEventListener("click", function () {
          btnG.disabled = true;
          btnG.textContent = "Guardando…";
          fetch("/api/gps/ronda", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lat: lat, lon: lon, potrero_id: pot.id || null, potrero_nombre: pot.nombre || null, punto_control: "recorrido" })
          }).then(function (r2) { return r2.json(); }).then(function (ok) {
            if (ok && ok.ok) {
              mostrarToast("✅ Ronda guardada en " + (pot.nombre || "campo"), "verde");
              try { if (navigator.vibrate) navigator.vibrate([30, 50, 30]); } catch (eVib3) {}
            } else {
              mostrarToast("❌ " + ((ok && ok.error) || "No se pudo guardar"), "rojo");
              btnG.disabled = false;
              btnG.textContent = "Guardar ronda aquí";
            }
          }).catch(function (err) {
            mostrarToast("❌ Sin conexión: " + (err && err.message || err), "rojo");
            btnG.disabled = false;
            btnG.textContent = "Guardar ronda aquí";
          });
        });
      }).catch(function () {
        box.innerHTML = "<div class='card campo-hoy'>📍 Sin conexión: no se pudo detectar el potrero.</div>";
      });
    }, function () {
      box.innerHTML = "<div class='card campo-hoy'>📍 No se pudo obtener la ubicación. Revise el permiso de GPS del navegador.</div>";
    }, { enableHighAccuracy: true, timeout: 15000 });
  }

  function renderTablero(d) {
    window.__datosUltimoTablero = d;
    if (d && d.clima_hoy) {
      actualizarClimaHeader(d.clima_hoy);
    } else if (d && d.pronostico && d.pronostico.dias && d.pronostico.dias.length) {
      actualizarClimaHeader(d.pronostico.dias[0]);
    } else {
      actualizarClimaHeader();
    }
    var pot = d.potrero_filtro ? " — potrero: <b>" + esc(d.potrero_filtro) + "</b>" : "";
    var pdfBtn = "<a href='/api/reporte.pdf' class='tema-btn' download style='font-size:12px; text-decoration:none; padding:5px 12px; display:inline-flex; align-items:center; gap:4px;'>" + icon("filePdf", 14) + "Reporte PDF</a>";
    // Sin botón "Buscar": la lupita flotante (🔍) abre el mismo buscador
    // con arete Y potrero, para no duplicar controles en el celular.
    var h = "<div class='tablero-head-barra' style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px; font-size:18px;'>" + icon("grid") + "Tablero finca" + pot + "</h3>"
      + "<div style='display:flex; gap:6px; align-items:center;'>" + pdfBtn + "</div>"
      + "</div>";
    // KPIs tocables: llevan a la vista (y a la lista de trabajo) de cada dato.
    function kpiLink(html, vista, lt, sec) { return kpiIr(html, { vista: vista, lt: lt, sec: sec }); }
    h += "<div class='kpis'>"
      + kpiLink(kpi(d.activos, "Activos"), "inventario", null, "Estructura del hato")
      + kpiLink(kpi(d.hembras, "Hembras"), "inventario", null, "Estructura del hato")
      + kpiLink(kpi(d.machos, "Machos"), "inventario", null, "Estructura del hato")
      + kpiLink(kpi(d.partos_7d, "Partos 7d", d.partos_7d > 0 ? "alerta" : ""), "repro", "partos")
      + kpiLink(kpi(d.celos_7d, "Celos 7d"), "repro", "celos") + kpiLink(kpi(d.servicios_7d, "Serv. 7d"), "repro", "palpar")
      + kpiLink(kpi(d.retiros_activos, "Retiros", d.retiros_activos > 0 ? "alerta" : ""), "sanidad", "tratamientos") + "</div>";
    h += erroresHtml(d);
    h += renderTareasHoy(d.tareas_conteos, d.datos_revisar_n);
    h += renderResumenDiaTablero(d);
    h += grafico("evolucion", "Evolución del rebaño");

    // Últimos Eventos de la Finca (Partos, Muertes, Ventas, Traslados, Pesajes...)
    // Solo los 8 más recientes por defecto -- el listado completo (35) y el
    // desglose por potrero ya viven en Inventario, sin duplicarlos aquí.
    var eventos = d.eventos_recientes || [];
    var LIMITE_EVENTOS_TABLERO = 8;
    var hayMasEventos = eventos.length > LIMITE_EVENTOS_TABLERO;
    h += "<div class='card' style='padding:16px; margin-top:16px; margin-bottom:16px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;'>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("calendar", 17) + "Últimos Eventos de la Finca</h4>"
      + "<span class='meta' style='font-size:12px; font-weight:600;'>" + eventos.length + " eventos recientes</span>"
      + "</div>"
      + "<p class='aviso' style='margin:4px 0 12px 0; font-size:12.5px;'>Registro cronológico de actividad del hato. Toca cualquier arete o cría para abrir su ficha técnica inmediata.</p>";

    if (!eventos.length) {
      h += vacio("No hay eventos recientes registrados.");
    } else {
      var esOwnerTab = window.__usuarioActual && (window.__usuarioActual.rol === "OWNER");
      h += "<div class='tabla-scroll tabla-eventos'><table class='tabla-eventos' id='tabla-eventos-tablero'>"
        + "<tr>"
        + "<th>Tipo Evento</th>"
        + "<th>Fecha</th>"
        + "<th>Animal / Arete</th>"
        + "<th>Detalle de la Actividad</th>"
        + (esOwnerTab ? "<th style='width:36px; text-align:center;'></th>" : "")
        + "</tr>";

      eventos.forEach(function (ev, idxEv) {
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
        } else if (tipo === "PAUSA_ORDENO") {
          chipHtml = "<span class='chip ambar' style='font-weight:700;'>" + icon("milk", 13) + " Pausa ordeño</span>";
        } else if (tipo === "REANUDAR_ORDENO") {
          chipHtml = "<span class='chip verde' style='font-weight:700;'>" + icon("milk", 13) + " Reanudó ordeño</span>";
        } else if (tipo === "PESAJE") {
          chipHtml = "<span class='chip gris' style='font-weight:700;'>" + icon("scale", 13) + " Pesaje</span>";
        } else if (tipo === "TRATAMIENTO") {
          chipHtml = "<span class='chip rojo' style='font-weight:700;'>" + icon("pill", 13) + " Tratamiento</span>";
        } else if (tipo === "SERVICIO") {
          var descUpper = (ev.descripcion || "").toUpperCase();
          var esMonta = descUpper.indexOf("MONTA") >= 0 || descUpper.indexOf("MN") === 0 || descUpper.indexOf("TORO") >= 0;
          var esIATF = descUpper.indexOf("IATF") >= 0;
          if (esMonta) {
            chipHtml = "<span class='chip ambar' style='font-weight:700;'>" + icon("bull", 13) + " Monta Natural</span>";
          } else if (esIATF) {
            chipHtml = "<span class='chip verde' style='font-weight:700;'>" + icon("sperm", 13) + " IATF</span>";
          } else {
            chipHtml = "<span class='chip verde' style='font-weight:700;'>" + icon("sperm", 13) + " Inseminación</span>";
          }
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

        var btnBorrarTab = (esOwnerTab && ev.id)
          ? ("<td style='text-align:center;'>" + renderBtnEliminar(tipo.toLowerCase(), ev.id, ev.tipo + " - " + ev.tag + " (" + fechaCorta(ev.fecha) + ")") + "</td>")
          : (esOwnerTab ? "<td></td>" : "");

        var filaOculta = idxEv >= LIMITE_EVENTOS_TABLERO;
        h += "<tr" + (filaOculta ? " class='fila-evento-extra' style='display:none'" : "") + ">"
          + "<td data-label='Tipo Evento'>" + chipHtml + "</td>"
          + "<td data-label='Fecha'><b style='font-family:var(--font-mono); font-size:12px;'>" + esc(fechaCorta(ev.fecha)) + "</b></td>"
          + "<td data-label='Animal / Arete'>" + linkAnimal + detalleExtra + "</td>"
          + "<td data-label='Detalle de la Actividad'>" + descHtml + "</td>"
          + btnBorrarTab
          + "</tr>";
      });

      h += "</table></div>";
      if (hayMasEventos) {
        h += "<button type='button' id='btn-ver-todos-eventos-tablero' class='tema-btn' style='margin-top:10px; font-size:12px; padding:6px 12px;'>"
          + "Ver los " + eventos.length + " eventos →</button>";
      }
    }
    h += "</div>";
    return h;
  }
  function enlaceFicha(tag, opts) {
    var t = esc(tag);
    var chip = (opts && opts.chip) ? (" chip " + opts.chip) : "";
    return "<a href='#' class='ficha-link" + chip + "' data-ir-ficha='" + t + "' style='font-weight:700; text-decoration:none;'>" + t + "</a>";
  }
