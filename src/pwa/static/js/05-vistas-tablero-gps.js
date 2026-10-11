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

    return "<div style='display:flex; gap:12px; flex-wrap:wrap; margin:10px 0 16px;'>"
      + "<div class='card' style='flex:1; min-width:180px; padding:12px 14px;'>"
      + "<div style='font-size:11px; font-weight:700; color:var(--texto-suave); text-transform:uppercase; display:flex; align-items:center; gap:5px; margin-bottom:6px;'>" + icon("rain", 13) + "Clima hoy</div>"
      + climaHtml
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
  }
  // GPS de ronda (equivale al /aqui del bot): detecta el potrero donde
  // está parado y ofrece guardar la ronda. Sin mapa: funciona con
  // cualquier rol y con guantes (botones grandes). Vive en Registrar
  // desde que se quitó el Modo Campo.
  function localizarGPSRonda() {
    var box = document.getElementById("gps-ronda-box");
    if (!box) return;
    if (!navigator.geolocation) {
      box.innerHTML = "<div class='card gps-ronda'>" + icon("pin", 14) + "Este equipo no da ubicación GPS.</div>";
      return;
    }
    box.innerHTML = "<div class='card gps-ronda'>" + icon("pin", 14) + "Localizando… acepte el permiso de ubicación del navegador.</div>";
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
          box.innerHTML = "<div class='card gps-ronda'>" + icon("pin", 14) + "" + esc((d && d.mensaje) || "Ubicación fuera de los potreros.") + "</div>";
          // El aviso se quita solo para no dejar ocupado el espacio de arriba.
          var aviso = box.firstChild;
          setTimeout(function () { if (aviso && aviso.parentNode === box) box.innerHTML = ""; }, 6000);
          return;
        }
        var pot = d.potrero || {};
        box.innerHTML = "<div class='card gps-ronda' style='border-left:5px solid var(--verde-marca);'>"
          + "<div style='font-size:15px; font-weight:800;'>" + icon("pin", 16) + "Estás en " + esc(pot.nombre || pot.codigo || "potrero") + "</div>"
          + "<div style='font-size:13.5px; color:var(--texto-suave); margin:2px 0 10px;'>"
          + esc(d.total_animales || 0) + " animales aquí · " + esc(Number(lat).toFixed(5)) + ", " + esc(Number(lon).toFixed(5)) + "</div>"
          + "<button type='button' id='btn-gps-guardar-ronda' class='tema-btn' style='width:100%; padding:14px; font-size:15px; background:var(--verde-marca); color:#fff; font-weight:700; border:none;'>Guardar ronda aquí</button>"
          + "</div>";
        var btnG = document.getElementById("btn-gps-guardar-ronda");
        if (btnG) btnG.addEventListener("click", function () {
          btnG.disabled = true;
          btnG.textContent = "Guardando…";
          fetch("/api/gps/ronda", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lat: lat, lon: lon, potrero_id: pot.id || null, potrero_nombre: pot.nombre || null, punto_control: "recorrido" })
          }).then(function (r2) { return r2.json(); }).then(function (ok) {
            if (ok && ok.ok) {
              mostrarToast("Ronda guardada en " + (pot.nombre || "campo"), "verde");
              try { if (navigator.vibrate) navigator.vibrate([30, 50, 30]); } catch (eVib3) {}
            } else {
              mostrarToast(((ok && ok.error) || "No se pudo guardar"), "rojo");
              btnG.disabled = false;
              btnG.textContent = "Guardar ronda aquí";
            }
          }).catch(function (err) {
            mostrarToast("Sin conexión: " + (err && err.message || err), "rojo");
            btnG.disabled = false;
            btnG.textContent = "Guardar ronda aquí";
          });
        });
      }).catch(function () {
        box.innerHTML = "<div class='card gps-ronda'>" + icon("pin", 14) + "Sin conexión: no se pudo detectar el potrero.</div>";
      });
    }, function () {
      box.innerHTML = "<div class='card gps-ronda'>" + icon("pin", 14) + "No se pudo obtener la ubicación. Revise el permiso de GPS del navegador.</div>";
    }, { enableHighAccuracy: true, timeout: 15000 });
  }

  function renderTareasAsignadasTablero(recs, recsComp) {
    recs = recs || [];
    recsComp = recsComp || [];
    var nPendientes = recs.length;
    var badgePend = nPendientes > 0
      ? "<span class='chip ambar' style='font-weight:700;'>" + nPendientes + " pendientes</span>"
      : "<span class='chip verde' style='font-weight:700;'>Al día</span>";

    var h = "<div class='card lt-card-tablero' style='padding:14px 16px; margin-bottom:14px; border-left:4px solid var(--verde-marca);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;'>"
      + "<div style='display:flex; align-items:center; gap:8px; font-size:15px; font-weight:700; color:var(--texto);'>"
      + icon("pin", 17) + "Tareas Asignadas al Equipo " + badgePend
      + "</div>"
      + "<button type='button' class='btn-guardar-manga' id='btn-tablero-nueva-tarea' style='padding:6px 12px; font-size:12.5px; width:auto; display:inline-flex; align-items:center; gap:5px; cursor:pointer;'>"
      + icon("plus", 13) + "Asignar Tarea</button>"
      + "</div>";

    if (!nPendientes) {
      h += "<p class='aviso' style='margin:6px 0 10px; font-size:12.5px;'>" + icon("sparkles", 14) + "Sin tareas asignadas pendientes. Puedes asignar tareas entre el equipo (ej. Jaime a Sebas) con el botón de arriba.</p>";
    } else {
      h += "<div style='display:flex; flex-direction:column; gap:8px; margin-bottom:10px;'>";
      recs.forEach(function (rc) {
        var fh = esc(rc.fecha || "—") + (rc.hora ? " " + esc(rc.hora) : "");
        var objChip = "";
        if (rc.animal_tag) {
          objChip = "<a href='#' class='chip azul ficha-link' data-ir-ficha='" + esc(rc.animal_tag) + "' style='text-decoration:none; display:inline-flex; align-items:center; gap:4px; font-weight:700;'>" + icon("cow", 12) + esc(rc.animal_tag) + "</a> ";
        } else if (rc.potrero_nombre) {
          objChip = "<span class='chip azul'>" + icon("leaf", 12) + esc(rc.potrero_nombre) + "</span> ";
        }

        var deQuien = rc.creado_por_nombre ? ("De: <b>" + esc(rc.creado_por_nombre) + "</b> → ") : "";
        var paraQuien = rc.asignado_a ? ("Para: <b style='color:var(--verde-marca);'>" + esc(rc.asignado_a) + "</b>") : "Equipo";
        var asignacionChip = "<span class='chip verde' style='font-size:11.5px;'>" + icon("user", 12) + deQuien + paraQuien + "</span> ";
        var prioChip = (rc.prioridad === "URGENTE") ? ("<span class='chip rojo' style='font-size:11px; font-weight:700;'>" + icon("alertTriangle", 12) + "URGENTE</span> ") : "";

        var urgChip = "";
        if (rc.faltan_dias != null) {
          var clUrg = rc.faltan_dias <= 0 ? "rojo" : (rc.faltan_dias <= 2 ? "ambar" : "gris");
          var txtUrg = rc.faltan_dias < 0 ? ("Venció " + Math.abs(rc.faltan_dias) + "d") : (rc.faltan_dias === 0 ? "HOY" : ("En " + rc.faltan_dias + "d"));
          urgChip = "<span class='chip " + clUrg + "' style='font-size:11px; font-weight:700;'>" + txtUrg + "</span>";
        }

        h += "<div class='tarea-card " + (rc.prioridad === "URGENTE" ? "urgente" : "normal") + "' style='padding:10px 12px; border:1px solid var(--borde); border-radius:10px; background:var(--superficie); margin-bottom:2px;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:4px;'>"
          + "<div>" + objChip + asignacionChip + prioChip + urgChip + "</div>"
          + "<small style='color:var(--texto-suave); font-weight:600; font-size:11.5px;'>" + icon("calendar", 12) + fh + "</small>"
          + "</div>"
          + "<div style='font-size:14px; font-weight:700; color:var(--texto); margin:4px 0;'>" + esc(rc.mensaje || "—") + "</div>"
          + "<div style='display:flex; justify-content:flex-end; align-items:center; gap:8px; margin-top:6px;'>"
          + (window.__usuarioActual && window.__usuarioActual.rol === "OWNER" ? ("<button type='button' class='btn-eliminar-evento' data-accion='eliminar-evento' data-tipo='tarea' data-id='" + esc(rc.id) + "' data-desc='Tarea: " + esc(rc.mensaje || "") + "' title='Eliminar tarea (solo OWNER)' style='font-size:11px; padding:5px 8px; color:var(--color-rojo-txt); font-weight:600; display:inline-flex; align-items:center; gap:3px; background:none; border:none; cursor:pointer;'>" + icon("trash", 12) + "Eliminar</button>") : "")
          + "<button type='button' class='btn-guardar-manga btn-rec-completar' data-rec-id='" + esc(rc.id) + "' data-rec-msg='" + esc(rc.mensaje || "") + "' data-rec-asig='" + esc(rc.asignado_a || "") + "' data-rec-de='" + esc(rc.creado_por_nombre || "") + "' data-rec-tag='" + esc(rc.animal_tag || "") + "' style='font-size:12px; padding:6px 12px; width:auto; display:inline-flex; align-items:center; gap:5px; cursor:pointer;'>"
          + icon("check", 13) + "Completar / Acknowledge"
          + "</button>"
          + "</div>"
          + "</div>";
      });
      h += "</div>";
    }

    if (recsComp && recsComp.length) {
      h += "<details style='margin-top:10px; border-top:1px dashed var(--borde); padding-top:8px;'>"
        + "<summary style='font-size:12.5px; font-weight:700; color:var(--verde-marca); cursor:pointer; outline:none; display:inline-flex; align-items:center; gap:4px;'>"
        + icon("shieldCheck", 14) + "Ver tareas cumplidas recientemente (" + recsComp.length + ") con foto/soporte"
        + "</summary>"
        + "<div style='display:flex; flex-direction:column; gap:6px; margin-top:8px;'>";

      recsComp.forEach(function (rc) {
        var fechaComp = esc(rc.completado_en || rc.fecha || "—");
        var objChip = "";
        if (rc.animal_tag) {
          objChip = "<span class='chip azul' style='font-size:11px;'>" + icon("cow", 11) + esc(rc.animal_tag) + "</span> ";
        } else if (rc.potrero_nombre) {
          objChip = "<span class='chip azul' style='font-size:11px;'>" + icon("leaf", 11) + esc(rc.potrero_nombre) + "</span> ";
        }
        var quien = esc(rc.completado_por || rc.asignado_a || "Equipo");

        var fotoHtml = "";
        if (rc.foto_completado) {
          fotoHtml = "<div style='margin-top:6px;'><a href='/" + esc(rc.foto_completado) + "' target='_blank' style='display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--verde-marca); text-decoration:none; font-weight:600;'>"
            + "<img src='/" + esc(rc.foto_completado) + "' alt='Comprobante' style='width:44px; height:44px; object-fit:cover; border-radius:6px; border:1px solid var(--borde);'>"
            + "<span>Ver foto soporte ↗</span></a></div>";
        }

        h += "<div style='padding:8px 12px; border:1px solid var(--borde); border-radius:8px; background:var(--superficie); font-size:12.5px; border-left:3px solid var(--verde-marca);'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px;'>"
          + "<div>" + objChip + "<span class='chip verde' style='font-size:10.5px; font-weight:700;'>" + icon("check", 11) + "REALIZADA</span></div>"
          + "<small style='color:var(--texto-suave); font-size:11px;'>" + icon("clock", 12) + fechaComp + "</small>"
          + "</div>"
          + "<div style='font-weight:600; font-size:13px; margin:3px 0;'>" + esc(rc.mensaje || "—") + "</div>"
          + "<div style='font-size:11.5px; color:var(--texto-suave);'>" + icon("user", 12) + "Completada por: <b>" + quien + "</b></div>"
          + (rc.notas_completado ? ("<div style='font-size:11.5px; margin-top:3px; padding:4px 8px; background:var(--fondo); border-radius:4px; font-style:italic;'>" + icon("chat", 12) + esc(rc.notas_completado) + "</div>") : "")
          + fotoHtml
          + "</div>";
      });
      h += "</div></details>";
    }

    h += "</div>";
    return h;
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
    var pdfBtn = botonDescargar("general");
    // Sin botón "Buscar": la lupita flotante abre el mismo buscador
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
    h += renderTareasAsignadasTablero(d.tareas_asignadas, d.tareas_realizadas_hoy);
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
