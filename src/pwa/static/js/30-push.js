  /* ---------- Notificaciones Nativas & Web Push ---------- */
  function mostrarNotificacionNativa(titulo, opts) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    opts = opts || {};
    opts.icon = opts.icon || "/static/icon-192.png";
    // badge (no icon): Android lo pinta como silueta desde el canal alfa --
    // icon-192.png es opaco (medalla plateada), así que salía como un
    // cuadrado blanco sólido en la barra de estado. badge-96.png es una
    // silueta blanca sobre transparente, hecha para esto.
    opts.badge = opts.badge || "/static/badge-96.png";
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.ready.then(function (reg) {
        if (reg && reg.showNotification) {
          var pr = reg.showNotification(titulo, opts);
          if (pr && pr.catch) pr.catch(function () { /* permiso revocado: se ignora */ });
        } else {
          new Notification(titulo, opts);
        }
      }).catch(function () {
        try { new Notification(titulo, opts); } catch (e) {}
      });
    } else {
      try { new Notification(titulo, opts); } catch (e) {}
    }
  }

  function registrarSuscripcionPushEnServidor(endpoint, keys) {
    fetch("/api/push/suscribir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: endpoint,
        keys: keys || {}
      })
    }).catch(function () {});
  }

  // Convierte la llave pública VAPID (base64url, la que expone el backend)
  // al Uint8Array que exige PushManager.subscribe({applicationServerKey}).
  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var rawData = window.atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
    return outputArray;
  }

  // Crea una suscripción Web Push REAL contra el navegador (antes de esto,
  // sin llave VAPID configurada en el servidor, nunca se llamaba a
  // subscribe() -- solo se guardaba un endpoint de relleno "pwa-local://"
  // que nunca pudo recibir nada). Si el servidor todavía no tiene VAPID
  // configurada, o el navegador no soporta Push, el .catch() de quien la
  // llama cae al mismo endpoint de relleno de siempre (para que al menos
  // las notificaciones locales sigan funcionando con la pestaña abierta).
  function suscribirPushReal(reg) {
    return fetch("/api/push/vapid-key").then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.publicKey) throw new Error("vapid_no_configurada");
        return reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(d.publicKey)
        });
      })
      .then(function (sub) {
        var sJson = sub.toJSON ? sub.toJSON() : {};
        registrarSuscripcionPushEnServidor(sub.endpoint, sJson.keys);
      });
  }

  function iniciarWebPush(mostrarFeedback) {
    if (!("Notification" in window)) {
      if (mostrarFeedback) alert("Este navegador no soporta notificaciones Web Push.");
      return Promise.reject("no_support");
    }
    return Notification.requestPermission().then(function (perm) {
      if (perm === "granted") {
        if ("serviceWorker" in navigator) {
          navigator.serviceWorker.ready.then(function (reg) {
            if ("PushManager" in window && reg.pushManager) {
              var devEndpointFallback = function () {
                var devEndpoint = "pwa-local://" + (localStorage.getItem("bitacora_dev_id") || (function () {
                  var nid = "dev_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
                  localStorage.setItem("bitacora_dev_id", nid);
                  return nid;
                })());
                registrarSuscripcionPushEnServidor(devEndpoint, {});
              };
              reg.pushManager.getSubscription().then(function (sub) {
                if (sub) {
                  var sJson = sub.toJSON ? sub.toJSON() : {};
                  registrarSuscripcionPushEnServidor(sub.endpoint, sJson.keys);
                  return true;
                }
                return suscribirPushReal(reg).then(function () { return true; });
              }).catch(function () { devEndpointFallback(); return false; })
                .then(function (real) {
                  if (!mostrarFeedback) return;
                  // Solo se confirma "activadas" si quedó una suscripción real:
                  // antes salía el aviso aunque el servidor no pudiera enviar nada.
                  if (real) {
                    mostrarToast("Avisos activados en este celular. Toque «Probar» para confirmar con la app cerrada.", "verde");
                  } else {
                    mostrarToast("Por ahora solo habrá avisos con la app abierta.", "ambar");
                  }
                });
            }
          });
        }
        verificarAlertasPush();
      } else if (mostrarFeedback) {
        alert("Las notificaciones fueron denegadas o bloqueadas.");
      }
      return perm;
    });
  }

  // Estado real de los avisos: permiso del navegador + si este celular tiene
  // una suscripción push + si el servidor puede enviar (llaves VAPID).
  // ok = llegan con la app cerrada.
  function estadoAvisos() {
    var est = { soporta: "Notification" in window && "serviceWorker" in navigator && "PushManager" in window,
                permiso: ("Notification" in window) ? Notification.permission : "no", suscrito: false,
                servidor_listo: false, ok: false };
    if (!est.soporta) return Promise.resolve(est);
    var pServ = fetch("/api/push/estado").then(function (r) { return r.json(); })
      .then(function (d) { est.servidor_listo = !!(d && d.servidor_listo); est.reales = d && d.suscripciones_reales; })
      .catch(function () {});
    var pSub = navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.getSubscription();
    }).then(function (sub) { est.suscrito = !!sub; }).catch(function () {});
    return Promise.all([pServ, pSub]).then(function () {
      est.ok = est.permiso === "granted" && est.suscrito && est.servidor_listo;
      return est;
    });
  }

  function textoEstadoAvisos(est) {
    if (!est.soporta) return "<span style='color:var(--texto-suave);'>" + icon("xCircle", 14) + "Este navegador no permite avisos. En Android use Chrome con la app instalada.</span>";
    if (est.permiso === "denied") return "<span style='color:var(--rojo-alerta); font-weight:600;'>" + icon("ban", 14) + "Bloqueados en este celular.</span> Toque el candado junto a la dirección → Permisos → Notificaciones → Permitir.";
    if (!est.servidor_listo) {
      // El detalle técnico (llaves VAPID) solo le sirve al propietario.
      var esOwner = window.__usuarioActual && window.__usuarioActual.rol === "OWNER";
      return "<span style='color:var(--ambar-alerta); font-weight:600;'>" + icon("alertTriangle", 14) + "Los avisos con la app cerrada aún no están activos.</span> "
        + (esOwner ? "Al servidor le faltan las llaves VAPID." : "Por ahora solo se ven con la app abierta.");
    }
    if (est.permiso !== "granted" || !est.suscrito) return "<span style='color:var(--ambar-alerta); font-weight:600;'>" + icon("alertTriangle", 14) + "Este celular no está suscrito.</span> Toque «Activar» para recibir partos, retiros y alertas con la app cerrada.";
    return "<span style='color:var(--verde-marca); font-weight:600;'>" + icon("checkCircle", 14) + "Activos en este celular.</span> Llegan con la app cerrada: resumen a las 6:30 a. m. y avisos urgentes (partos, retiros, servidor).";
  }

  // Tablero: si este celular no recibe avisos con la app cerrada, lo dice
  // arriba con un botón para activarlos. "Ahora no" lo oculta 7 días.
  var CLAVE_BANNER_AVISOS = "ja_banner_avisos_oculto_hasta";
  function mostrarBannerAvisos() {
    var oculto = 0;
    try { oculto = parseInt(localStorage.getItem(CLAVE_BANNER_AVISOS) || "0", 10) || 0; } catch (e) { /* sin almacenamiento */ }
    if (Date.now() < oculto) return;
    estadoAvisos().then(function (est) {
      if (est.ok || !est.soporta || document.getElementById("banner-avisos")) return;
      var vistaEl = document.getElementById("vista");
      if (!vistaEl || actual !== "tablero") return;
      var div = document.createElement("div");
      div.id = "banner-avisos";
      div.className = "card";
      div.style.cssText = "border-left:4px solid var(--color-ambar-txt, #D97706); padding:12px 14px;";
      var puedeActivar = est.permiso !== "denied" && est.servidor_listo;
      div.innerHTML = "<b>" + icon("bell", 16) + "Avisos al celular</b><p style='margin:6px 0 8px; font-size:13px;'>" + textoEstadoAvisos(est) + "</p>"
        + "<div style='display:flex; gap:8px; flex-wrap:wrap;'>"
        + (puedeActivar ? "<button type='button' class='tema-btn' id='btn-banner-activar-avisos'>Activar avisos</button>" : "")
        + "<button type='button' class='tema-btn' id='btn-banner-ocultar-avisos' style='background:var(--bg-suave); color:var(--texto-base);'>Ahora no</button></div>";
      vistaEl.insertBefore(div, vistaEl.firstChild);
      var bAct = document.getElementById("btn-banner-activar-avisos");
      if (bAct) bAct.addEventListener("click", function () {
        bAct.disabled = true;
        iniciarWebPush(true).then(function () {
          setTimeout(function () {
            estadoAvisos().then(function (e2) { if (e2.ok) div.remove(); else bAct.disabled = false; });
          }, 1500);
        }).catch(function () { bAct.disabled = false; });
      });
      document.getElementById("btn-banner-ocultar-avisos").addEventListener("click", function () {
        try { localStorage.setItem(CLAVE_BANNER_AVISOS, String(Date.now() + 7 * 86400000)); } catch (e) { /* sin almacenamiento */ }
        div.remove();
      });
    });
  }

  function verificarAlertasPush() {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    fetch("/api/push/alertas").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (d) {
      if (!d || !d.alertas || !d.alertas.length) return;
      var storageKey = "bitacora_push_notified";
      var notificados = {};
      try { notificados = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch (e) {}

      d.alertas.forEach(function (al) {
        var idAl = al.tipo + "_" + (al.tag || al.potrero || "finca") + "_" + (al.mensaje || "");
        var lastTime = notificados[idAl] || 0;
        var now = Date.now();
        // Notificar como máximo una vez cada 8 horas por la misma alerta
        if (now - lastTime < 8 * 3600 * 1000) return;

        notificados[idAl] = now;
        var targetUrl = "/?v=agenda";
        if (al.tipo === "voisin_sobrepastoreo") targetUrl = "/?v=mapa";
        else if (al.tipo === "celo_am_pm") targetUrl = "/?v=repro";

        mostrarNotificacionNativa(al.titulo || "Alerta Bitácora JA", {
          body: al.mensaje,
          tag: idAl,
          data: { url: targetUrl }
        });
      });

      try { localStorage.setItem(storageKey, JSON.stringify(notificados)); } catch (e) {}
    }).catch(function () {});
  }

  function bindAgenda() {
    // Selector de objetivo (Animal / Potrero / General) en formulario de agenda
    var agBtns = qa(".ag-obj-btn");
    var wrapAgAnimal = document.getElementById("ag-wrap-animal");
    var wrapAgPotrero = document.getElementById("ag-wrap-potrero");
    var inpAgObj = document.getElementById("ag-obj-tipo");
    agBtns.forEach(function (b) {
      b.addEventListener("click", function () {
        agBtns.forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        var obj = b.getAttribute("data-obj");
        if (inpAgObj) inpAgObj.value = obj;
        if (wrapAgAnimal) wrapAgAnimal.style.display = (obj === "animal") ? "" : "none";
        if (wrapAgPotrero) wrapAgPotrero.style.display = (obj === "potrero") ? "" : "none";
      });
    });
    fetch("/api/equipo/integrantes").then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.integrantes) return;
      var dl = document.getElementById("dl-equipo-agenda");
      if (dl) {
        dl.innerHTML = d.integrantes.map(function (it) {
          return "<option value='" + esc(it.nombre) + "'>" + esc(it.rol ? it.rol : "") + "</option>";
        }).join("");
      }
    }).catch(function () {});

    // Alta de evento/tarea asignada desde la Agenda (POST /api/agenda/recordatorio).
    var formRec = document.getElementById("form-nuevo-recordatorio");
    if (formRec && !formRec.__bound) {
      formRec.__bound = true;
      formRec.addEventListener("submit", function (e) {
        e.preventDefault();
        var fb = document.getElementById("ag-form-feedback");
        var btn = document.getElementById("btn-ag-guardar");
        var objTipo = (inpAgObj && inpAgObj.value) || "animal";
        var tag = (document.getElementById("ag-tag") || {}).value || "";
        var pot = (document.getElementById("ag-potrero") || {}).value || "";
        var tipoTarea = (document.getElementById("ag-tipo-tarea") || {}).value || "GENERAL";
        var asignado = (document.getElementById("ag-asignado") || {}).value || "";
        var desc = ((document.getElementById("ag-mensaje") || {}).value || "").trim();
        var fecha = ((document.getElementById("ag-fecha") || {}).value || "").trim();
        var hora = ((document.getElementById("ag-hora") || {}).value || "").trim();
        var prioridad = (document.getElementById("ag-prioridad") || {}).value || "NORMAL";

        if (!desc) { if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>" + icon("alertTriangle", 14) + "Escriba qué hay que hacer.</span>"; return; }
        if (!fecha) { if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>" + icon("alertTriangle", 14) + "Elija la fecha de la tarea.</span>"; return; }

        var prefix = (objTipo === "animal" && tag.trim()) ? (tag.trim() + ": ") : ((objTipo === "potrero" && pot.trim()) ? (pot.trim() + ": ") : "");
        var mensajeFinal = prefix + desc;

        if (btn) btn.disabled = true;
        if (fb) fb.textContent = "Guardando tarea...";
        fetch("/api/agenda/recordatorio", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mensaje: mensajeFinal,
            fecha: fecha,
            hora: hora || null,
            asignado_a: asignado.trim() || "Encargado",
            tipo_objetivo: objTipo.toUpperCase(),
            animal_tag: objTipo === "animal" ? tag.trim() : null,
            potrero_nombre: objTipo === "potrero" ? pot.trim() : null,
            tipo_tarea: tipoTarea,
            prioridad: prioridad
          })
        }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
          .then(function (out) {
            if (btn) btn.disabled = false;
            if (!out.ok || !out.j.ok) {
              if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>" + icon("xCircle", 14) + esc((out.j && out.j.error) || "No se pudo guardar.") + "</span>";
              return;
            }
            mostrarToast("Tarea asignada y agendada", "verde");
            vibrarConfirmacion();
            cargar(true);
            actualizarBadges();
          }).catch(function (err) {
            if (btn) btn.disabled = false;
            if (fb) fb.innerHTML = "<span style='color:var(--rojo-alerta);'>" + icon("xCircle", 14) + "Sin conexión: " + esc(err.message || err) + "</span>";
          });
      });
    }

    // Modal de Acknowledge / Realización de tarea con foto opcional y notas
    var modalAck = document.getElementById("modal-ack-tarea");
    var formAck = document.getElementById("form-ack-tarea");
    var inpAckId = document.getElementById("ack-rec-id");
    var txtAckInfo = document.getElementById("ack-tarea-info");
    var inpAckPor = document.getElementById("ack-completado-por");
    var inpAckNotas = document.getElementById("ack-notas");
    var inpAckFoto = document.getElementById("ack-foto-input");
    var prevAckWrap = document.getElementById("ack-foto-preview");
    var prevAckImg = document.getElementById("ack-foto-img");
    var btnCerrarAck = document.getElementById("btn-cerrar-modal-ack");
    var btnCancelarAck = document.getElementById("btn-cancelar-ack");
    var _ackFotoB64 = null;

    function cerrarModalAck() {
      if (modalAck) modalAck.style.display = "none";
      if (inpAckId) inpAckId.value = "";
      if (inpAckNotas) inpAckNotas.value = "";
      if (inpAckFoto) inpAckFoto.value = "";
      if (prevAckWrap) prevAckWrap.style.display = "none";
      if (prevAckImg) prevAckImg.src = "";
      _ackFotoB64 = null;
    }

    if (btnCerrarAck && !btnCerrarAck.__bound) {
      btnCerrarAck.__bound = true;
      btnCerrarAck.addEventListener("click", cerrarModalAck);
    }
    if (btnCancelarAck && !btnCancelarAck.__bound) {
      btnCancelarAck.__bound = true;
      btnCancelarAck.addEventListener("click", cerrarModalAck);
    }
    if (modalAck && !modalAck.__bound) {
      modalAck.__bound = true;
      modalAck.addEventListener("click", function (e) {
        if (e.target === modalAck) cerrarModalAck();
      });
    }

    if (inpAckFoto && !inpAckFoto.__bound) {
      inpAckFoto.__bound = true;
      inpAckFoto.addEventListener("change", function () {
        var file = inpAckFoto.files && inpAckFoto.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function (ev) {
          var img = new Image();
          img.onload = function () {
            var maxDim = 1200;
            var width = img.width;
            var height = img.height;
            if (width > maxDim || height > maxDim) {
              if (width > height) {
                height = Math.round((height * maxDim) / width);
                width = maxDim;
              } else {
                width = Math.round((width * maxDim) / height);
                height = maxDim;
              }
            }
            var canvas = document.createElement("canvas");
            canvas.width = width;
            canvas.height = height;
            var ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0, width, height);
            _ackFotoB64 = canvas.toDataURL("image/jpeg", 0.82);
            if (prevAckImg) prevAckImg.src = _ackFotoB64;
            if (prevAckWrap) prevAckWrap.style.display = "block";
          };
          img.src = ev.target.result;
        };
        reader.readAsDataURL(file);
      });
    }

    // Al pulsar "Marcar Realizado (Acknowledge)"
    qa(".btn-rec-completar").forEach(function (b) {
      b.addEventListener("click", function () {
        var rid = b.getAttribute("data-rec-id");
        var msg = b.getAttribute("data-rec-msg") || "";
        var asig = b.getAttribute("data-rec-asig") || "";
        if (!rid) return;
        if (inpAckId) inpAckId.value = rid;
        if (txtAckInfo) {
          var asigInfo = asig ? ("<br><small style='color:var(--texto-suave);'>Asignado a: <b>" + esc(asig) + "</b></small>") : "";
          txtAckInfo.innerHTML = "<b>" + icon("pin", 14) + esc(msg) + "</b>" + asigInfo;
        }
        var miNombre = (window.__usuarioActual && (window.__usuarioActual.nombre || window.__usuarioActual.username)) || asig || "Encargado";
        if (inpAckPor) inpAckPor.value = miNombre;
        if (modalAck) modalAck.style.display = "flex";
      });
    });

    if (formAck && !formAck.__bound) {
      formAck.__bound = true;
      formAck.addEventListener("submit", function (e) {
        e.preventDefault();
        var rid = (inpAckId && inpAckId.value) || "";
        if (!rid) return;
        var btnConf = document.getElementById("btn-confirmar-ack");
        var fbAck = document.getElementById("ack-feedback");
        if (btnConf) btnConf.disabled = true;
        if (fbAck) fbAck.textContent = "Registrando cumplimiento...";
        var payloadAck = {
          notas: (inpAckNotas && inpAckNotas.value || "").trim(),
          completado_por: (inpAckPor && inpAckPor.value || "").trim(),
          foto_base64: _ackFotoB64 || null
        };
        fetch("/api/agenda/recordatorio/" + encodeURIComponent(rid) + "/completar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payloadAck)
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (btnConf) btnConf.disabled = false;
            if (res && res.ok) {
              cerrarModalAck();
              mostrarToast("¡Tarea marcada como realizada!", "verde");
              vibrarConfirmacion();
              cargar(true);
              actualizarBadges();
            } else {
              if (fbAck) fbAck.innerHTML = "<span style='color:var(--rojo-alerta);'>" + icon("xCircle", 14) + esc((res && res.error) || "Error al completar.") + "</span>";
            }
          }).catch(function (err) {
            if (btnConf) btnConf.disabled = false;
            if (fbAck) fbAck.innerHTML = "<span style='color:var(--rojo-alerta);'>" + icon("xCircle", 14) + "Error de conexión: " + esc(err.message || err) + "</span>";
          });
      });
    }
    var estadoEl = document.getElementById("push-estado-txt");
    var btnActivar = document.getElementById("btn-activar-push");
    var btnProbar = document.getElementById("btn-probar-push");

    function actualizarTextoEstado() {
      if (!estadoEl) return;
      estadoAvisos().then(function (est) {
        estadoEl.innerHTML = textoEstadoAvisos(est);
        if (btnActivar) {
          btnActivar.disabled = est.permiso === "denied";
          btnActivar.textContent = est.ok ? "Re-sincronizar" : "Activar";
        }
      });
      return;
      if (!("Notification" in window)) {
        estadoEl.innerHTML = "<span style='color:var(--texto-suave);'>" + icon("xCircle", 14) + "Tu navegador no soporta notificaciones nativas.</span>";
        if (btnActivar) btnActivar.style.display = "none";
        if (btnProbar) btnProbar.style.display = "none";
        return;
      }
      if (Notification.permission === "granted") {
        estadoEl.innerHTML = "<span style='color:var(--verde-marca); font-weight:600;'>" + icon("checkCircle", 14) + "Notificaciones activas en este dispositivo.</span> Recibirás alertas de retiros de carne/leche, celos AM-PM, termo criogénico y Voisin.";
        if (btnActivar) btnActivar.textContent = "Re-sincronizar";
      } else if (Notification.permission === "denied") {
        estadoEl.innerHTML = "<span style='color:var(--rojo-alerta); font-weight:600;'>" + icon("ban", 14) + "Notificaciones bloqueadas.</span> Habilita los permisos en la barra de direcciones o ajustes del navegador.";
        if (btnActivar) btnActivar.disabled = true;
      } else {
        estadoEl.innerHTML = "<span style='color:var(--ambar-alerta); font-weight:600;'>" + icon("alertTriangle", 14) + "Desactivadas.</span> Actívalas para recibir alertas de retiros sanitarios, celos e inventario crítico.";
        if (btnActivar) btnActivar.disabled = false;
      }
    }

    actualizarTextoEstado();

    if (btnActivar) {
      btnActivar.addEventListener("click", function () {
        btnActivar.disabled = true;
        iniciarWebPush(true).finally(function () {
          btnActivar.disabled = false;
          actualizarTextoEstado();
        });
      });
    }

    if (btnProbar) {
      btnProbar.addEventListener("click", function () {
        if (!("Notification" in window) || Notification.permission !== "granted") {
          iniciarWebPush(true).then(function (perm) {
            if (perm === "granted") lanzarPruebaPush();
          });
        } else {
          lanzarPruebaPush();
        }
      });
    }

    // Prueba REAL: el servidor envía por el servicio push. Si llega con la
    // app cerrada, todo funciona (antes era una notificación local que decía
    // "prueba exitosa" aunque el servidor no pudiera enviar nada).
    function lanzarPruebaPush() {
      fetch("/api/push/probar", { method: "POST" })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res && res.ok) {
            mostrarToast("Enviada a " + res.enviados + " dispositivo(s). Debe llegar en segundos; cierre la app para comprobarlo.", "verde");
          } else if (res && res.motivo === "sin_suscripcion") {
            mostrarToast("Este celular no está suscrito: toque «Activar».", "ambar");
          } else if (res && res.motivo === "servidor_sin_llaves") {
            mostrarToast("Los avisos con la app cerrada aún no están activos en el servidor.", "ambar");
          } else {
            mostrarToast("No se pudo enviar (" + ((res && res.fallidos) || 0) + " fallidos). Toque «Re-sincronizar» y pruebe de nuevo.", "rojo");
          }
          actualizarTextoEstado();
        })
        .catch(function () { mostrarToast("Sin conexión con el servidor.", "rojo"); });
    }
  }

