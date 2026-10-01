  /* ---------- Por revisar (OWNER/ADMIN) ----------
     Partos, muertes, ventas y traslados que registra un TRABAJADOR quedan en
     pausa hasta que alguien de la oficina los apruebe, los corrija o los
     rechace (ver src/engine/revision.py). */
  var ICONO_REVISION = {
    parto: "parto", muerte: "skull", venta: "banknote", movimiento: "banknote",
    traslado: "truck", traslado_masivo: "truck"
  };

  function fechaHoraRevision(iso) {
    if (!iso) return "";
    var s = String(iso);
    var f = s.slice(8, 10) + "/" + s.slice(5, 7);
    return s.length > 15 ? f + " " + s.slice(11, 16) : f;
  }

  function tarjetaRevision(p) {
    var quien = esc(p.registrado_por_nombre || "Trabajador");
    var meta = quien + " · " + esc(p.canal || "App") + " · enviado " + esc(fechaHoraRevision(p.creado_en));
    if (p.fecha) meta += " · fecha del evento " + esc(fechaHoraRevision(p.fecha));
    var h = "<article class='rev-tarjeta' data-id='" + p.id + "'>"
      + "<div class='rev-cab'><span class='rev-ico'>" + icon(ICONO_REVISION[p.tipo] || "clipboard", 20) + "</span>"
      + "<div class='rev-txt'><b>" + esc(p.resumen) + "</b><small>" + meta + "</small>"
      + (p.tiene_foto ? "<small>Trae foto adjunta</small>" : "") + "</div></div>";
    if (p.campos && p.campos.length) {
      h += "<div class='rev-campos' hidden>";
      p.campos.forEach(function (c) {
        h += "<label class='rev-campo'><span>" + esc(c.etiqueta) + "</span>"
          + "<input type='text' data-clave='" + esc(c.clave) + "' data-original='" + esc(c.valor) + "' value='" + esc(c.valor) + "'></label>";
      });
      h += "</div>";
    }
    h += "<div class='rev-rechazo' hidden><label class='rev-campo'><span>Motivo del rechazo (opcional)</span>"
      + "<input type='text' class='rev-motivo' maxlength='300' placeholder='Ej. esa vaca no está preñada'></label></div>"
      + "<div class='rev-error' hidden></div>"
      + "<div class='rev-acciones'>"
      + "<button type='button' class='rev-btn rev-aprobar' data-accion-rev='aprobar'>Aprobar</button>"
      + (p.campos && p.campos.length ? "<button type='button' class='rev-btn rev-corregir' data-accion-rev='corregir'>Corregir</button>" : "")
      + "<button type='button' class='rev-btn rev-rechazar' data-accion-rev='rechazar'>Rechazar</button>"
      + "</div></article>";
    return h;
  }

  function renderRevision(d) {
    var pend = (d && d.pendientes) || [];
    var revisados = (d && d.revisados) || [];
    var h = "<h3>" + icon("clipboard", 20) + "Por revisar</h3>"
      + "<p class='aviso'>Partos, muertes, ventas y traslados que registran los trabajadores esperan aquí. "
      + "Al aprobarlos quedan registrados a nombre de quien los envió.</p>";
    if (!pend.length) {
      h += "<div class='rev-vacio'>" + icon("clipboard", 22) + "<b>No hay registros por revisar.</b></div>";
    } else {
      h += "<div class='rev-lista' id='rev-lista'>" + pend.map(tarjetaRevision).join("") + "</div>";
    }
    if (revisados.length) {
      h += "<h4 class='rev-subtitulo'>Revisados hace poco</h4><div class='rev-historial'>";
      revisados.forEach(function (p) {
        var ok = p.estado === "APROBADO";
        h += "<div class='rev-hist-fila'><span class='chip " + (ok ? "verde" : "rojo") + "'>" + (ok ? "Aprobado" : "Rechazado") + "</span>"
          + "<div class='rev-txt'><b>" + esc(p.resumen) + "</b><small>" + esc(p.registrado_por_nombre || "Trabajador")
          + " · revisó " + esc(p.revisado_por_nombre || "") + " " + esc(fechaHoraRevision(p.revisado_en))
          + (p.nota_revision ? " · " + esc(p.nota_revision) : "") + "</small></div></div>";
      });
      h += "</div>";
    }
    return h;
  }

  function bindRevision() {
    var lista = document.getElementById("rev-lista");
    if (!lista) return;
    lista.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-accion-rev]");
      if (!btn) return;
      var tarjeta = btn.closest(".rev-tarjeta");
      var id = tarjeta && tarjeta.getAttribute("data-id");
      if (!id) return;
      var accion = btn.getAttribute("data-accion-rev");
      var campos = tarjeta.querySelector(".rev-campos");
      var rechazo = tarjeta.querySelector(".rev-rechazo");
      var errorBox = tarjeta.querySelector(".rev-error");

      if (accion === "corregir") {
        if (campos) campos.hidden = !campos.hidden;
        if (rechazo) rechazo.hidden = true;
        btn.classList.toggle("activo", campos && !campos.hidden);
        var primero = campos && !campos.hidden && campos.querySelector("input");
        if (primero) primero.focus();
        return;
      }
      if (accion === "rechazar" && rechazo && rechazo.hidden) {
        // Primer toque: pedir el motivo. El segundo confirma.
        rechazo.hidden = false;
        if (campos) campos.hidden = true;
        btn.textContent = "Confirmar rechazo";
        var mot = rechazo.querySelector("input");
        if (mot) mot.focus();
        return;
      }

      var cuerpo = {};
      if (accion === "aprobar" && campos && !campos.hidden) {
        var cambios = {};
        campos.querySelectorAll("input[data-clave]").forEach(function (inp) {
          if (inp.value !== inp.getAttribute("data-original")) cambios[inp.getAttribute("data-clave")] = inp.value;
        });
        cuerpo.cambios = cambios;
      }
      if (accion === "rechazar") {
        var motInp = rechazo && rechazo.querySelector("input");
        cuerpo.motivo = motInp ? motInp.value : "";
      }
      tarjeta.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
      fetch("/api/revision/" + encodeURIComponent(id) + "/" + accion, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo)
      }).then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
        .then(function (res) {
          if (!res.ok || !res.body.ok) throw new Error((res.body && res.body.error) || "No se pudo guardar.");
          mostrarToast(accion === "aprobar" ? (res.body.corregido ? "Corregido y registrado" : "Aprobado y registrado") : "Rechazado", "verde");
          vibrarConfirmacion();
          tarjeta.classList.add("rev-saliendo");
          setTimeout(function () {
            if (tarjeta.parentNode) tarjeta.parentNode.removeChild(tarjeta);
            if (!document.querySelector(".rev-tarjeta")) cargar(false);
          }, 250);
          actualizarBadges();
        }).catch(function (err) {
          tarjeta.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
          if (errorBox) { errorBox.textContent = err && err.message || String(err); errorBox.hidden = false; }
        });
    });
  }

