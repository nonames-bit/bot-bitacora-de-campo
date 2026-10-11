  /* ---------- Versión de la app y aviso "Hay una versión nueva" ----------
     La versión es el hash que el servidor pone en ?v= al servir la página
     (BLOQUE 3). La app recuerda con cuál arrancó, la compara con
     /api/version al abrir, al volver a la app y cada 30 min, y si el
     servidor ya tiene otra muestra un aviso arriba: al tocarlo se recarga.
     El menú de usuario (y Sistema → Estado) dice qué versión está corriendo
     y si está al día. Nunca recarga sola: puede haber un formulario a medias. */
  var VERSION_CARGADA = (function () {
    var s = document.currentScript || document.querySelector("script[src*='/static/app.js']");
    var m = s && s.src ? /[?&]v=([^&#]+)/.exec(s.src) : null;
    return m ? decodeURIComponent(m[1]) : "dev";
  })();
  var _versionServidor = null;   // { version, fecha } de la última consulta
  var _versionSinRed = false;
  var _avisoVersionCerrado = false;
  var _teniaControlador = !!(navigator.serviceWorker && navigator.serviceWorker.controller);

  var MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

  // "2026-10-11 10:15" -> "11 oct 2026, 10:15 a. m."
  function fechaVersionLegible(txt) {
    var m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(txt || "");
    if (!m) return "";
    var r = parseInt(m[3], 10) + " " + MESES_CORTOS[parseInt(m[2], 10) - 1] + " " + m[1];
    if (m[4]) {
      var hh = parseInt(m[4], 10);
      var ampm = hh < 12 ? "a. m." : "p. m.";
      var h12 = hh % 12 === 0 ? 12 : hh % 12;
      r += ", " + h12 + ":" + m[5] + " " + ampm;
    }
    return r;
  }

  // Fecha de la versión cargada: la da el servidor cuando coincide; se
  // guarda para poder mostrarla también sin señal.
  function fechaVersionCargada() {
    if (_versionServidor && _versionServidor.version === VERSION_CARGADA) return _versionServidor.fecha || "";
    try {
      var g = JSON.parse(localStorage.getItem("ja_version_fecha") || "null");
      if (g && g.v === VERSION_CARGADA) return g.f || "";
    } catch (e) { /* almacenamiento no disponible */ }
    return "";
  }

  function hayVersionNueva() {
    return !!(_versionServidor && _versionServidor.version && VERSION_CARGADA !== "dev"
      && _versionServidor.version !== VERSION_CARGADA);
  }

  function htmlEstadoVersion() {
    var fecha = fechaVersionLegible(fechaVersionCargada());
    var h = "<div class='version-app-linea'><b>" + (fecha ? "Del " + esc(fecha) : "Versión cargada")
      + "</b> <span class='version-app-codigo'>" + esc(VERSION_CARGADA) + "</span></div>";
    if (hayVersionNueva()) {
      var fn = fechaVersionLegible(_versionServidor.fecha);
      h += "<div class='version-app-estado nueva'>" + dot("ambar") + "Hay una versión nueva"
        + (fn ? " (del " + esc(fn) + ")" : "") + "</div>"
        + "<button type='button' class='version-app-actualizar'>" + icon("refresh", 14) + "Actualizar ahora</button>";
    } else if (_versionServidor) {
      h += "<div class='version-app-estado al-dia'>" + dot("verde") + "Al día: es la última versión</div>";
    } else if (_versionSinRed) {
      h += "<div class='version-app-estado'>" + dot("gris") + "Sin conexión: no se pudo comprobar</div>";
    } else {
      h += "<div class='version-app-estado'>Comprobando…</div>";
    }
    return h;
  }

  function pintarEstadoVersion() {
    ["menu-version-estado", "sistema-version-estado"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.innerHTML = htmlEstadoVersion();
    });
    var aviso = document.getElementById("aviso-version-nueva");
    if (hayVersionNueva() && !_avisoVersionCerrado) {
      if (!aviso) {
        aviso = document.createElement("div");
        aviso.id = "aviso-version-nueva";
        aviso.className = "aviso-version-nueva";
        aviso.setAttribute("role", "status");
        aviso.innerHTML = "<button type='button' class='aviso-version-btn version-app-actualizar'>"
          + icon("refresh", 16) + "<span>Hay una versión nueva. <b>Toca para actualizar</b></span></button>"
          + "<button type='button' class='aviso-version-cerrar' aria-label='Ahora no'>×</button>";
        document.body.appendChild(aviso);
      }
    } else if (aviso) {
      aviso.parentNode.removeChild(aviso);
    }
  }

  function comprobarVersion() {
    return fetch("/api/version", { cache: "no-store", credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.version || d._offline) { _versionSinRed = true; pintarEstadoVersion(); return; }
        _versionSinRed = false;
        _versionServidor = { version: String(d.version), fecha: String(d.fecha || "") };
        if (_versionServidor.version === VERSION_CARGADA) {
          try { localStorage.setItem("ja_version_fecha", JSON.stringify({ v: VERSION_CARGADA, f: _versionServidor.fecha })); }
          catch (e) { /* almacenamiento no disponible */ }
        }
        pintarEstadoVersion();
      })
      .catch(function () { _versionSinRed = true; pintarEstadoVersion(); });
  }

  // Recarga con la versión nueva: primero le pide al service worker que se
  // actualice (si no, la recarga podría salir aún de la copia vieja) y
  // recarga cuando el nuevo toma el control, o a los pocos segundos.
  var _recargando = false;
  function actualizarAhora() {
    if (_recargando) return;
    _recargando = true;
    qa(".version-app-actualizar").forEach(function (b) { b.disabled = true; b.textContent = "Actualizando…"; });
    var hecho = false;
    function recargar() { if (hecho) return; hecho = true; window.location.reload(); }
    setTimeout(recargar, 8000);
    if (!("serviceWorker" in navigator)) { recargar(); return; }
    navigator.serviceWorker.addEventListener("controllerchange", recargar);
    navigator.serviceWorker.getRegistration().then(function (reg) {
      if (!reg) { recargar(); return; }
      return reg.update().then(function () {
        // Ya estaba al día el service worker: recargar de una vez.
        if (!reg.installing && !reg.waiting) recargar();
      });
    }).catch(recargar);
  }

  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target : null;
    if (!t) return;
    if (t.closest(".version-app-actualizar")) { actualizarAhora(); return; }
    if (t.closest(".aviso-version-cerrar")) { _avisoVersionCerrado = true; pintarEstadoVersion(); return; }
    if (t.closest("#menu-btn-version")) {
      _versionServidor = null; _versionSinRed = false; pintarEstadoVersion(); comprobarVersion();
    }
  });

  // Si mientras la app está abierta llega un service worker nuevo, es que
  // el servidor se actualizó: avisar (sin recargar sola).
  if (navigator.serviceWorker) {
    navigator.serviceWorker.addEventListener("controllerchange", function () {
      if (_teniaControlador && !_recargando) comprobarVersion();
      _teniaControlador = true;
    });
  }
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") comprobarVersion();
  });
  setInterval(function () { if (document.visibilityState === "visible") comprobarVersion(); }, 30 * 60 * 1000);
  pintarEstadoVersion();
  setTimeout(comprobarVersion, 2500);
