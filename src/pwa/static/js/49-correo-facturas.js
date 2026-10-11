  /* ---------- Correo de facturas: Sistema → Correo, solo OWNER ----------
     El dueño pega el correo de la finca y la contraseña de aplicación de
     Gmail; el servidor los prueba antes de guardarlos y nunca devuelve la
     clave. Muestra cuándo se revisó el buzón por última vez. Rutas en
     src/pwa/rutas/sistema.py (/api/correo-facturas). */

  var MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

  function horaRevision(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || "");
    if (!m) return (iso || "").replace("T", " ");
    var h = Number(m[4]);
    return Number(m[3]) + " " + MESES_CORTOS[Number(m[2]) - 1] + ", " + (h % 12 || 12) + ":" + m[5]
      + (h < 12 ? " a. m." : " p. m.");
  }

  function htmlEstadoBuzon(d) {
    var e = (d && d.estado) || {};
    if (!e.revisado_en) {
      return "<p class='cf-estado'>" + icon("clock", 14) + "Todavía no se ha revisado. La app mira el buzón cada "
        + esc(d.cada_minutos || 15) + " minutos.</p>";
    }
    if (e.ok) {
      var n = Number(e.facturas || 0);
      return "<p class='cf-estado cf-ok'>" + icon("check", 14) + "Revisado " + esc(horaRevision(e.revisado_en))
        + (n ? " · " + n + (n === 1 ? " factura nueva" : " facturas nuevas") + " en Por revisar" : " · sin facturas nuevas")
        + "</p>";
    }
    return "<p class='cf-estado cf-error'>" + icon("alert", 14) + "Falló la revisión de " + esc(horaRevision(e.revisado_en))
      + ": " + esc(e.error || "error desconocido") + "</p>";
  }

  var ICONO_RESULTADO = { por_revisar: "check", ya_estaba: "check", sin_adjunto: "info", no_factura: "info", error: "alert" };

  function htmlUltimosCorreos(correos) {
    if (!correos || !correos.length) return "";
    return "<div class='cf-correos'><small>Últimos correos leídos</small>" + correos.map(function (c) {
      var cls = c.resultado === "error" ? "cf-error" : (c.resultado === "por_revisar" || c.resultado === "ya_estaba" ? "cf-ok" : "");
      return "<div class='cf-correo " + cls + "'>" + icon(ICONO_RESULTADO[c.resultado] || "info", 14)
        + "<div><b>" + esc(c.asunto || "(sin asunto)") + "</b><span>" + esc(c.nota || "") + "</span></div></div>";
    }).join("") + "</div>";
  }

  function htmlFormCorreo(usuario) {
    return "<form id='cf-form' class='cf-form' autocomplete='off'>"
      + "<label for='cf-usuario'>Correo de la finca</label>"
      + "<input id='cf-usuario' type='email' inputmode='email' autocapitalize='none' placeholder='finca@gmail.com' value='" + esc(usuario || "") + "'>"
      + "<label for='cf-clave'>Contraseña de aplicación (16 letras)</label>"
      + "<input id='cf-clave' type='password' autocomplete='new-password' autocapitalize='none' spellcheck='false' placeholder='abcd efgh ijkl mnop'>"
      + "<small>No es la clave normal del correo. Se saca en myaccount.google.com/apppasswords con la verificación en 2 pasos activa.</small>"
      + "<button type='submit' id='cf-guardar'>" + icon("check", 14) + "Probar y guardar</button>"
      + "</form>";
  }

  function htmlCorreoFacturas(d) {
    var h = "<h4 style='margin:0 0 6px;'>" + icon("receipt", 16) + "Correo de facturas</h4>"
      + "<p class='aviso' style='margin:0 0 10px;'>Las facturas que lleguen a este correo (PDF, .zip de factura electrónica o foto) "
      + "se leen solas y quedan en Gestión → Por revisar para que las apruebes.</p>";
    if (!d.configurado) return h + htmlFormCorreo("");
    h += "<div class='cf-actual'><div><small>Revisando</small><b>" + esc(d.usuario) + "</b></div>"
      + "<div class='resp-acciones'>"
      + "<button type='button' id='cf-revisar'>" + icon("search", 14) + "Revisar ahora</button>"
      + "<button type='button' class='btn-sec' id='cf-probar'>" + icon("refresh", 14) + "Probar conexión</button>"
      + (d.origen === "app" ? "<button type='button' class='btn-sec' id='cf-cambiar'>" + icon("pencil", 14) + "Cambiar</button>" : "")
      + "</div></div>"
      + htmlEstadoBuzon(d)
      + "<p id='cf-resultado' class='cf-estado' hidden></p>"
      + htmlUltimosCorreos((d.estado || {}).correos);
    if (d.origen === "servidor") {
      h += "<p class='cf-estado'>" + icon("info", 14) + "Este correo está puesto en el servidor (.env). Para cambiarlo desde aquí, "
        + "<a href='#' id='cf-cambiar-servidor'>escribe otro</a>; lo de la app reemplaza al del servidor.</p>";
    }
    h += "<div id='cf-cambio' hidden>" + htmlFormCorreo(d.usuario)
      + (d.origen === "app" ? "<button type='button' class='btn-peligro' id='cf-quitar' style='margin-top:10px;'>" + icon("trash", 14) + "Dejar de revisar este correo</button>" : "")
      + "</div>";
    return h;
  }

  function cargarCorreoFacturas() {
    var panel = document.getElementById("correo-facturas-panel");
    if (!panel) return;
    fetch("/api/correo-facturas").then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.ok) throw new Error((d && d.error) || "Sin acceso");
      panel.innerHTML = htmlCorreoFacturas(d);
      bindCorreoFacturas(panel);
    }).catch(function (e) {
      panel.innerHTML = "<p class='aviso'>No se pudo cargar el correo de facturas: " + esc(e.message) + "</p>";
    });
  }

  function pedirCorreo(metodo, url, cuerpo) {
    return fetch(url, {
      method: metodo, headers: { "Content-Type": "application/json" },
      body: cuerpo ? JSON.stringify(cuerpo) : undefined
    }).then(function (r) { return r.json(); });
  }

  function bindCorreoFacturas(panel) {
    var form = panel.querySelector("#cf-form");
    if (form) form.addEventListener("submit", function (e) {
      e.preventDefault();
      var b = panel.querySelector("#cf-guardar");
      var usuario = panel.querySelector("#cf-usuario").value.trim();
      var clave = panel.querySelector("#cf-clave").value;
      b.disabled = true;
      b.textContent = "Probando con Gmail…";
      pedirCorreo("POST", "/api/correo-facturas", { usuario: usuario, clave: clave }).then(function (d) {
        if (!d.ok) throw new Error(d.error || "No se pudo guardar.");
        var n = Number(d.sin_leer || 0);
        mostrarToast("Correo conectado. " + (n ? n + " sin leer; se revisan en los próximos minutos." : "El buzón está vacío."), "verde");
        cargarCorreoFacturas();
      }).catch(function (err) {
        mostrarToast(err.message, "rojo");
        b.disabled = false;
        b.innerHTML = icon("check", 14) + "Probar y guardar";
      });
    });
    var bRevisar = panel.querySelector("#cf-revisar");
    if (bRevisar) bRevisar.addEventListener("click", function () {
      bRevisar.disabled = true;
      bRevisar.textContent = "Leyendo el correo…";
      pedirCorreo("POST", "/api/correo-facturas/revisar").then(function (d) {
        if (!d.ok) throw new Error(d.error || "No se pudo revisar el correo.");
        var n = Number(d.facturas || 0);
        mostrarToast(n ? n + (n === 1 ? " factura nueva en Por revisar" : " facturas nuevas en Por revisar")
          : (d.correos && d.correos.length ? "Revisado. Mira abajo qué pasó con cada correo." : "No hay correos de los últimos 3 días."),
          n ? "verde" : "ambar");
        cargarCorreoFacturas();
      }).catch(function (err) {
        mostrarToast(err.message, "rojo");
        bRevisar.disabled = false;
        bRevisar.innerHTML = icon("search", 14) + "Revisar ahora";
      });
    });
    var bProbar = panel.querySelector("#cf-probar");
    if (bProbar) bProbar.addEventListener("click", function () {
      var out = panel.querySelector("#cf-resultado");
      bProbar.disabled = true;
      pedirCorreo("POST", "/api/correo-facturas/probar").then(function (d) {
        out.hidden = false;
        out.className = "cf-estado " + (d.ok ? "cf-ok" : "cf-error");
        out.innerHTML = d.ok
          ? icon("check", 14) + "Conectado. Hay " + Number(d.sin_leer || 0) + " correo(s) sin leer en el buzón."
          : icon("alert", 14) + esc(d.error || "No se pudo entrar al correo.");
      }).catch(function (err) { mostrarToast(err.message, "rojo"); })
        .then(function () { bProbar.disabled = false; });
    });
    function abrirCambio(e) {
      if (e) e.preventDefault();
      var c = panel.querySelector("#cf-cambio");
      c.hidden = false;
      panel.querySelector("#cf-clave").focus();
    }
    var bCambiar = panel.querySelector("#cf-cambiar");
    if (bCambiar) bCambiar.addEventListener("click", abrirCambio);
    var aServidor = panel.querySelector("#cf-cambiar-servidor");
    if (aServidor) aServidor.addEventListener("click", abrirCambio);
    var bQuitar = panel.querySelector("#cf-quitar");
    if (bQuitar) bQuitar.addEventListener("click", function () {
      if (!confirm("¿Dejar de revisar este correo? Las facturas que ya están en Finanzas no se tocan.")) return;
      pedirCorreo("DELETE", "/api/correo-facturas").then(function (d) {
        if (!d.ok) throw new Error(d.error || "No se pudo quitar.");
        mostrarToast("Ya no se revisa ese correo", "verde");
        cargarCorreoFacturas();
      }).catch(function (err) { mostrarToast(err.message, "rojo"); });
    });
  }
