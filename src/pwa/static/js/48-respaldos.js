  /* ---------- Copias de seguridad (Fase F): Sistema → Copias, solo OWNER ----------
     Lista las copias de backups/ (diarias de las 3 a. m., manuales y las que
     se guardan antes de restaurar), permite hacer una ahora, descargarla y
     restaurarla escribiendo RESTAURAR. Rutas en src/pwa/rutas/sistema.py. */
  var NOMBRE_TIPO_COPIA = { diaria: "Automática", manual: "Hecha a mano", antes_de_restaurar: "Antes de restaurar" };

  function fechaCopia(c) {
    var m = /^(\d{4}-\d{2}-\d{2})\.db$/.exec(c.nombre);
    var f = (c.fecha || "").replace("T", " ");
    return m ? m[1] + " · 3:00 a. m." : f;
  }

  function htmlRespaldos(d) {
    var copias = (d && d.copias) || [];
    var h = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
      + "<h4 style='margin:0;'>" + icon("archive", 16) + "Copias de seguridad</h4>"
      + "<button type='button' id='btn-copia-ahora'>" + icon("plus", 14) + "Hacer copia ahora</button></div>"
      + "<p class='aviso' style='margin:10px 0;'>Todos los días a las 3:00 a. m. se guarda una copia de la base y se conservan "
      + esc((d && d.dias_guardadas) || 30) + " días. Restaurar devuelve la finca a como estaba en esa copia: "
      + "se pierde lo registrado después, pero antes se guarda la base actual por si hay que volver.</p>";
    if (!copias.length) return h + "<p style='color:var(--texto-suave);'>Todavía no hay copias en el servidor.</p>";
    h += "<div class='resp-lista'>";
    copias.forEach(function (c) {
      var n = esc(c.nombre);
      h += "<div class='resp-item' data-nombre='" + n + "'>"
        + "<div class='resp-info'><b>" + esc(fechaCopia(c)) + "</b>"
        + "<small>" + esc(NOMBRE_TIPO_COPIA[c.tipo] || c.tipo) + " · " + esc(c.tam_mb) + " MB</small></div>"
        + "<div class='resp-acciones'>"
        + "<a class='rep-btn rep-btn-sec' href='/api/respaldos/" + encodeURIComponent(c.nombre) + "/descargar'>" + icon("download", 14) + "Descargar</a>"
        + "<button type='button' class='btn-peligro btn-resp-restaurar'>" + icon("refresh", 14) + "Restaurar</button></div>"
        + "<form class='resp-confirmar' hidden>"
        + "<label>Escribe <b>RESTAURAR</b> para volver a la copia de " + esc(fechaCopia(c)) + ":</label>"
        + "<div class='resp-confirmar-fila'><input autocomplete='off' autocapitalize='characters' aria-label='Confirmación'>"
        + "<button type='submit' class='btn-peligro'>Confirmar</button>"
        + "<button type='button' class='btn-sec btn-resp-cancelar'>Cancelar</button></div></form>"
        + "</div>";
    });
    return h + "</div>";
  }

  function cargarRespaldos() {
    var panel = document.getElementById("respaldos-panel");
    if (!panel) return;
    fetch("/api/respaldos").then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.ok) throw new Error((d && d.error) || "Sin acceso");
      panel.innerHTML = htmlRespaldos(d);
      bindRespaldos(panel);
    }).catch(function (e) {
      panel.innerHTML = "<p class='aviso'>No se pudieron cargar las copias: " + esc(e.message) + "</p>";
    });
  }

  function bindRespaldos(panel) {
    var bCopia = document.getElementById("btn-copia-ahora");
    if (bCopia) bCopia.addEventListener("click", function () {
      bCopia.disabled = true;
      fetch("/api/respaldos/crear", { method: "POST" }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) throw new Error(d.error || "No se pudo hacer la copia.");
        mostrarToast("Copia guardada", "verde");
        cargarRespaldos();
      }).catch(function (e) { mostrarToast(e.message, "rojo"); bCopia.disabled = false; });
    });
    panel.querySelectorAll(".resp-item").forEach(function (it) {
      var form = it.querySelector(".resp-confirmar");
      it.querySelector(".btn-resp-restaurar").addEventListener("click", function () {
        panel.querySelectorAll(".resp-confirmar").forEach(function (f) { f.hidden = f !== form; });
        form.hidden = false;
        form.querySelector("input").focus();
      });
      it.querySelector(".btn-resp-cancelar").addEventListener("click", function () { form.hidden = true; });
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var txt = (form.querySelector("input").value || "").trim().toUpperCase();
        if (txt !== "RESTAURAR") { mostrarToast("Escribe RESTAURAR para confirmar.", "ambar"); return; }
        var bOk = form.querySelector("button[type=submit]");
        bOk.disabled = true;
        bOk.textContent = "Restaurando…";
        fetch("/api/respaldos/" + encodeURIComponent(it.getAttribute("data-nombre")) + "/restaurar", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmacion: txt })
        }).then(function (r) { return r.json(); }).then(function (d) {
          if (!d.ok) throw new Error(d.error || "No se pudo restaurar.");
          mostrarToast("Base restaurada. Lo de antes quedó guardado como otra copia.", "verde");
          cargar(true);
        }).catch(function (e2) {
          mostrarToast(e2.message, "rojo");
          bOk.disabled = false;
          bOk.textContent = "Confirmar";
        });
      });
    });
  }
