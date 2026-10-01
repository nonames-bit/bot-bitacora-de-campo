  function mostrarModalProtocolosInfo(protocolos) {
    var overlay = document.getElementById("iatf-protocolos-info-modal");
    if (overlay) overlay.remove();

    var prots = (protocolos && protocolos.length) ? protocolos : (window.__protocolosIatf || []);

    var htmlProts = prots.map(function (p) {
      var pasos = Array.isArray(p.pasos) ? p.pasos : (typeof p.pasos === "string" ? JSON.parse(p.pasos || "[]") : []);
      var pasosHtml = pasos.map(function (ps) {
        var prodsHtml = (ps.productos || []).map(function (pr) {
          var marcas = (pr.marcas_sugeridas || []).join(", ");
          return "<div style='font-size:11.5px; background:var(--superficie); padding:4px 8px; border-radius:4px; border:1px solid var(--borde); margin-top:3px;'>"
            + "<b>" + esc(pr.tipo || "") + ":</b> " + esc(pr.principio_activo || "") + " · Dosis: <b>" + esc(pr.dosis_sugerida || "") + "</b>"
            + (marcas ? (" · <span style='color:var(--verde-marca);'>Marcas: " + esc(marcas) + "</span>") : "")
            + "</div>";
        }).join("");

        return "<div style='margin-bottom:8px; padding-left:10px; border-left:3px solid var(--azul-marca);'>"
          + "<div style='font-weight:700; font-size:12.5px; color:var(--texto);'>Día " + ps.dia_relativo + ": " + esc(ps.accion) + "</div>"
          + "<div style='font-size:11.5px; color:var(--texto-suave);'>" + esc(ps.descripcion || "") + "</div>"
          + prodsHtml
          + "</div>";
      }).join("");

      return "<div style='background:var(--superficie-elevada); border:1px solid var(--borde); border-radius:8px; padding:12px 14px; margin-bottom:12px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;'>"
        + "<span style='font-size:14px; font-weight:700; color:var(--texto);'>" + esc(p.nombre) + "</span>"
        + "<span class='chip azul' style='font-size:11px;'>Duración: " + p.duracion_dias + " días</span>"
        + "</div>"
        + "<div style='font-size:12px; color:var(--texto-suave); margin-bottom:10px;'>" + esc(p.descripcion || "") + "</div>"
        + pasosHtml
        + "</div>";
    }).join("");

    var html = "<div id='iatf-protocolos-info-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:640px; max-height:85vh; overflow-y:auto;'>"
      + "<div class='modal-header'><b>" + icon("clipboard", 16) + " Biblioteca de Protocolos Hormonales IATF</b><button type='button' class='modal-cerrar' id='btn-cerrar-prots-modal' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
      + "<div style='padding:16px;'>"
      + "<p style='margin:0 0 12px 0; font-size:12.5px; color:var(--texto-suave);'>Protocolos zootécnicos validados con dosis sugeridas y marcas comerciales de referencia (evaluables según respuesta de fertilidad):</p>"
      + htmlProts
      + "</div></div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("iatf-protocolos-info-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-prots-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });
  }

  function mostrarModalNuevoLoteIATF(protocolos, onSuccess) {
    var overlay = document.getElementById("nuevo-lote-iatf-modal");
    if (overlay) overlay.remove();

    var prots = (protocolos && protocolos.length) ? protocolos : (window.__protocolosIatf || []);
    var hoyFmt = new Date().toISOString().slice(0, 10);

    var optsProt = prots.map(function (p) {
      return "<option value='" + p.id + "'>" + esc(p.nombre) + " (" + esc(p.categoria) + " - " + p.duracion_dias + "d)</option>";
    }).join("");

    var html = "<div id='nuevo-lote-iatf-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:560px; max-height:90vh; overflow-y:auto;'>"
      + "<div class='modal-header'><b>" + icon("plus", 16) + " Iniciar Nuevo Lote IATF</b><button type='button' class='modal-cerrar' id='btn-cerrar-lote-modal' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
      + "<div style='padding:16px;'>"
      + "<form id='form-nuevo-lote-iatf' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<label style='font-size:12.5px; font-weight:600;'>Nombre / Identificador del Lote:*<br>"
      + "<input id='lote-nombre' required placeholder='ej. Lote Novillas 2026-A, Vacas DP Grupo 1' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Protocolo Hormonal:*<br>"
      + "<select id='lote-protocolo-id' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'>" + optsProt + "</select></label>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
      + "<label style='flex:1; min-width:130px; font-size:12.5px; font-weight:600;'>Fecha de Inicio (Día 0):*<br>"
      + "<input id='lote-fecha-inicio' type='date' value='" + hoyFmt + "' required style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='flex:1; min-width:110px; font-size:12.5px; font-weight:600;'>Hora de IATF (Día 10):<br>"
      + "<input id='lote-hora-iatf' type='time' value='08:00' required style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "</div>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
      + "<label style='flex:1; min-width:130px; font-size:12.5px; font-weight:600;'>Toro / Pajilla Sugerido:<br>"
      + "<input id='lote-toro' placeholder='ej. GUZ-01' list='dl-toros' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='flex:1; min-width:130px; font-size:12.5px; font-weight:600;'>Inseminador Asignado:<br>"
      + "<input id='lote-inseminador' placeholder='Nombre del técnico' list='dl-inseminadores' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "</div>"
      + "<label style='font-size:12.5px; font-weight:600;'>Aretes de las Hembras a Sincronizar:*<br>"
      + "<span style='font-size:11.5px; color:var(--texto-suave); font-weight:normal;'>Escriba o pegue los tags separados por espacio, coma o salto de línea.</span><br>"
      + "<textarea id='lote-animales-tags' required rows='3' placeholder='ej. 47, 52, JA176, N069, PATRICIA' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); font-family:var(--font-mono); font-size:13px; box-sizing:border-box;'></textarea></label>"
      + "<div id='lote-conteo-preview' style='font-size:12px; font-weight:700; color:var(--azul-marca);'>0 hembras ingresadas</div>"
      + "<label style='font-size:12.5px; font-weight:600;'>Notas / Observaciones:<br>"
      + "<input id='lote-notas' placeholder='ej. Lote con cría al pie, seleccionadas con CC >= 2.75' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<div class='aviso' style='font-size:11.5px; margin:4px 0;'>" + icon("lightbulb", 14) + "Al crear el lote, el sistema programará automáticamente las alertas de drogas en la Agenda PWA, notificaciones push y Telegram para los días exactos de aplicación (Día 0, Día 8 y Día 10).</div>"
      + "<div id='lote-form-error' style='display:none; color:var(--color-rojo-txt, #dc2626); font-size:12px; font-weight:600;'></div>"
      + "<div style='display:flex; justify-content:flex-end; gap:8px; margin-top:6px;'>"
      + "<button type='button' class='tema-btn' id='btn-cancel-lote-modal' style='padding:8px 14px; border-radius:6px;'>Cancelar</button>"
      + "<button type='submit' class='btn-guardar-manga' style='padding:8px 16px; margin:0;'>Iniciar Lote IATF</button>"
      + "</div>"
      + "</form>"
      + "</div></div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("nuevo-lote-iatf-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-lote-modal");
    var btnCan = document.getElementById("btn-cancel-lote-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    if (btnCan) btnCan.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

    var inpIns = document.getElementById("lote-inseminador");
    if (inpIns && window.__usuarioActual && window.__usuarioActual.nombre) {
      inpIns.value = window.__usuarioActual.nombre;
    }
    cargarListaInseminadores();

    var txtTags = document.getElementById("lote-animales-tags");
    var cntPrev = document.getElementById("lote-conteo-preview");
    function actualizarConteo() {
      var val = (txtTags.value || "").trim();
      var arr = val ? val.replace(/,/g, " ").split(/\s+/).filter(Boolean) : [];
      cntPrev.textContent = arr.length + " hembra(s) ingresada(s)";
    }
    if (txtTags) {
      txtTags.addEventListener("input", actualizarConteo);
      txtTags.addEventListener("paste", function () { setTimeout(actualizarConteo, 50); });
    }

    var form = document.getElementById("form-nuevo-lote-iatf");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = document.getElementById("lote-form-error");
      var nom = (document.getElementById("lote-nombre").value || "").trim();
      var protId = document.getElementById("lote-protocolo-id").value;
      var fIni = document.getElementById("lote-fecha-inicio").value;
      var rawTags = (txtTags.value || "").trim();
      var tagsArr = rawTags ? rawTags.replace(/,/g, " ").split(/\s+/).filter(Boolean) : [];

      if (!nom || !protId || !fIni || !tagsArr.length) {
        if (errEl) { errEl.textContent = "Complete todos los campos requeridos y al menos un animal"; errEl.style.display = "block"; }
        return;
      }

      var payload = {
        nombre: nom,
        protocolo_id: Number(protId),
        fecha_inicio: fIni,
        hora_iatf: document.getElementById("lote-hora-iatf").value || "08:00",
        toro_pajuela: (document.getElementById("lote-toro").value || "").trim() || null,
        inseminador: (inpIns.value || "").trim() || null,
        animales_tags: tagsArr,
        notas: (document.getElementById("lote-notas").value || "").trim() || null
      };

      fetch("/api/iatf/lotes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.ok) {
            mostrarToast("Lote " + nom + " (" + tagsArr.length + " vacas) iniciado con alertas", "verde");
            cerrar();
            if (typeof onSuccess === "function") onSuccess();
          } else {
            if (errEl) { errEl.textContent = res.error || "No se pudo crear el lote"; errEl.style.display = "block"; }
          }
        }).catch(function (err) {
          if (errEl) { errEl.textContent = "Error de conexión: " + (err && err.message || err); errEl.style.display = "block"; }
        });
    });
  }

  function mostrarModalPasoIATF(loteId, pasoIdx, onSuccess) {
    var overlay = document.getElementById("iatf-paso-modal");
    if (overlay) overlay.remove();

    var lotes = window.__lotesIatf || [];
    var lote = null;
    for (var i = 0; i < lotes.length; i++) {
      if (Number(lotes[i].id) === Number(loteId)) { lote = lotes[i]; break; }
    }

    var pasos = lote && lote.protocolo_pasos ? lote.protocolo_pasos : [];
    var paso = pasos[pasoIdx] || { accion: "Paso " + pasoIdx, productos: [] };

    var prods = paso.productos || [];
    var marcasSugeridas = [];
    var dosisSugerida = "";
    var prodNombreSugerido = "";
    if (prods.length > 0) {
      prodNombreSugerido = prods.map(function (pr) { return pr.principio_activo || pr.tipo; }).join(" + ");
      prods.forEach(function (pr) {
        if (pr.marcas_sugeridas) marcasSugeridas = marcasSugeridas.concat(pr.marcas_sugeridas);
        if (pr.dosis_sugerida && !dosisSugerida) dosisSugerida = pr.dosis_sugerida;
      });
    }

    var marcaSugeridaStr = marcasSugeridas.join(" / ");

    var html = "<div id='iatf-paso-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:480px;'>"
      + "<div class='modal-header'><b>" + icon("pill", 16) + "Registrar Aplicación de Fármacos</b><button type='button' class='modal-cerrar' id='btn-cerrar-paso-modal' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
      + "<div style='padding:16px;'>"
      + "<div style='background:rgba(2,132,199,0.08); border-left:4px solid #0284c7; padding:8px 12px; border-radius:6px; margin-bottom:12px; font-size:12.5px;'>"
      + "<b>Lote:</b> " + esc(lote ? lote.nombre : ("Lote #" + loteId)) + "<br>"
      + "<b>Acción:</b> " + esc(paso.accion)
      + "</div>"
      + "<form id='form-paso-iatf' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<label style='font-size:12.5px; font-weight:600;'>Fármaco / Principio Activo:*<br>"
      + "<input id='paso-producto' required value='" + esc(prodNombreSugerido) + "' placeholder='ej. Retiro P4 + Cloprostenol + Cipionato + eCG' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Marca Comercial Utilizada:*<br>"
      + "<input id='paso-marca' required placeholder='ej. Ciclase DL + ECP + Novormon 400UI' value='" + esc(marcaSugeridaStr) + "' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Dosis Aplicada:*<br>"
      + "<input id='paso-dosis' required placeholder='ej. 2ml PGF + 0.5ml ECP + 2ml eCG' value='" + esc(dosisSugerida) + "' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Operario / Aplicado Por:<br>"
      + "<input id='paso-operario' placeholder='Nombre del operario' list='dl-inseminadores' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Notas / Observaciones de Campo:<br>"
      + "<input id='paso-notas' placeholder='ej. Retiro normal, 0 pérdidas de dispositivos' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<div id='paso-form-error' style='display:none; color:var(--color-rojo-txt, #dc2626); font-size:12px; font-weight:600;'></div>"
      + "<div style='display:flex; justify-content:flex-end; gap:8px; margin-top:6px;'>"
      + "<button type='button' class='tema-btn' id='btn-cancel-paso-modal' style='padding:8px 14px; border-radius:6px;'>Cancelar</button>"
      + "<button type='submit' class='btn-guardar-manga' style='padding:8px 16px; margin:0;'>Confirmar Aplicación</button>"
      + "</div>"
      + "</form>"
      + "</div></div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("iatf-paso-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-paso-modal");
    var btnCan = document.getElementById("btn-cancel-paso-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    if (btnCan) btnCan.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

    var inpOp = document.getElementById("paso-operario");
    if (inpOp && window.__usuarioActual && window.__usuarioActual.nombre) {
      inpOp.value = window.__usuarioActual.nombre;
    }

    var form = document.getElementById("form-paso-iatf");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = document.getElementById("paso-form-error");
      var payload = {
        paso_index: pasoIdx,
        producto: document.getElementById("paso-producto").value,
        marca: document.getElementById("paso-marca").value,
        dosis: document.getElementById("paso-dosis").value,
        realizado_por: inpOp.value || null,
        notas: document.getElementById("paso-notas").value || null
      };

      fetch("/api/iatf/lotes/" + loteId + "/paso", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.ok) {
            mostrarToast("Paso registrado exitosamente", "verde");
            cerrar();
            if (typeof onSuccess === "function") onSuccess();
          } else {
            if (errEl) { errEl.textContent = res.error || "No se pudo registrar"; errEl.style.display = "block"; }
          }
        }).catch(function (err) {
          if (errEl) { errEl.textContent = "Error de conexión: " + (err && err.message || err); errEl.style.display = "block"; }
        });
    });
  }

  function mostrarModalInseminarLoteIATF(loteId, onSuccess) {
    var overlay = document.getElementById("iatf-inseminar-modal");
    if (overlay) overlay.remove();

    var lotes = window.__lotesIatf || [];
    var lote = null;
    for (var i = 0; i < lotes.length; i++) {
      if (Number(lotes[i].id) === Number(loteId)) { lote = lotes[i]; break; }
    }

    var hoyFmt = new Date().toISOString().slice(0, 10);
    var nHembras = lote ? (lote.animales_activos || lote.total_animales || 0) : 0;

    var html = "<div id='iatf-inseminar-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:500px;'>"
      + "<div class='modal-header'><b>" + icon("dna", 16) + "Inseminación Masiva a 1-Toque (IATF)</b><button type='button' class='modal-cerrar' id='btn-cerrar-ins-lote-modal' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
      + "<div style='padding:16px;'>"
      + "<div style='background:rgba(22,163,74,0.08); border-left:4px solid var(--verde-marca); padding:10px 12px; border-radius:6px; margin-bottom:12px; font-size:12.5px;'>"
      + "Se registrará el servicio por IATF para las <b>" + nHembras + " hembras activas</b> de <b>" + esc(lote ? lote.nombre : ("Lote #" + loteId)) + "</b> "
      + "y se descontarán automáticamente las pajillas del termo criogénico."
      + "</div>"
      + "<form id='form-inseminar-lote' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<label style='font-size:12.5px; font-weight:600;'>Código Toro / Pajilla a Descontar:*<br>"
      + "<input id='ins-lote-toro' required value='" + esc(lote && lote.toro_pajuela ? lote.toro_pajuela : "") + "' placeholder='ej. GUZ-01' list='dl-toros' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='font-size:12.5px; font-weight:600;'>Técnico Inseminador Responsable:*<br>"
      + "<input id='ins-lote-inseminador' required value='" + esc(lote && lote.inseminador ? lote.inseminador : "") + "' placeholder='Nombre del inseminador' list='dl-inseminadores' style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
      + "<label style='flex:1; min-width:130px; font-size:12.5px; font-weight:600;'>Fecha de Inseminación:*<br>"
      + "<input id='ins-lote-fecha' type='date' value='" + hoyFmt + "' required style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "<label style='flex:1; min-width:110px; font-size:12.5px; font-weight:600;'>Hora:*<br>"
      + "<input id='ins-lote-hora' type='time' value='" + esc(lote && lote.hora_iatf ? lote.hora_iatf : "08:00") + "' required style='width:100%; margin-top:4px; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); box-sizing:border-box;'></label>"
      + "</div>"
      + "<div id='ins-lote-form-error' style='display:none; color:var(--color-rojo-txt, #dc2626); font-size:12px; font-weight:600;'></div>"
      + "<div style='display:flex; justify-content:flex-end; gap:8px; margin-top:6px;'>"
      + "<button type='button' class='tema-btn' id='btn-cancel-ins-lote-modal' style='padding:8px 14px; border-radius:6px;'>Cancelar</button>"
      + "<button type='submit' class='btn-guardar-manga' style='padding:8px 16px; margin:0; background:var(--verde-marca); border-color:var(--verde-marca);'>Confirmar Inseminación (" + nHembras + " vacas)</button>"
      + "</div>"
      + "</form>"
      + "</div></div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("iatf-inseminar-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-ins-lote-modal");
    var btnCan = document.getElementById("btn-cancel-ins-lote-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    if (btnCan) btnCan.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

    var inpIns = document.getElementById("ins-lote-inseminador");
    if (inpIns && !inpIns.value && window.__usuarioActual && window.__usuarioActual.nombre) {
      inpIns.value = window.__usuarioActual.nombre;
    }

    var form = document.getElementById("form-inseminar-lote");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = document.getElementById("ins-lote-form-error");
      var payload = {
        toro_pajuela: document.getElementById("ins-lote-toro").value,
        inseminador: inpIns.value,
        fecha: document.getElementById("ins-lote-fecha").value,
        hora: document.getElementById("ins-lote-hora").value
      };

      fetch("/api/iatf/lotes/" + loteId + "/inseminar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }).then(function (r) { return r.json(); })
        .then(function (res) {
          if (res.ok) {
            mostrarToast("Inseminación completada (" + (res.resultado ? res.resultado.servicios_creados : "") + " servicios registrados)", "verde");
            cerrar();
            if (typeof onSuccess === "function") onSuccess();
          } else {
            if (errEl) { errEl.textContent = res.error || "No se pudo inseminar el lote"; errEl.style.display = "block"; }
          }
        }).catch(function (err) {
          if (errEl) { errEl.textContent = "Error de conexión: " + (err && err.message || err); errEl.style.display = "block"; }
        });
    });
  }

  function mostrarModalDetalleLoteIATF(loteId, onSuccess) {
    var overlay = document.getElementById("iatf-detalle-modal");
    if (overlay) overlay.remove();

    fetch("/api/iatf/lotes/" + loteId)
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res.ok || !res.lote) {
          mostrarToast("No se pudo cargar el lote", "rojo");
          return;
        }
        var lote = res.lote;
        var animales = lote.animales || [];
        var pasosHist = lote.historial_pasos || [];

        var histHtml = pasosHist.length ? pasosHist.map(function (h) {
          return "<tr>"
            + "<td><b>" + esc(fechaCorta(h.fecha)) + "</b></td>"
            + "<td>" + esc(h.producto || "—") + "</td>"
            + "<td><span class='chip verde' style='font-size:11px;'>" + esc(h.marca || "—") + "</span></td>"
            + "<td style='font-family:var(--font-mono);'>" + esc(h.dosis || "—") + "</td>"
            + "<td style='font-size:12px; color:var(--texto-suave);'>" + esc(h.realizado_por || "—") + "</td>"
            + "</tr>";
        }).join("") : "<tr><td colspan='5' style='text-align:center; color:var(--texto-suave);'>Sin aplicaciones registradas aún.</td></tr>";

        var animsHtml = animales.map(function (a) {
          var estBadge = a.estado === "ACTIVO" ? "<span class='chip verde' style='font-size:10.5px;'>ACTIVA</span>" :
            "<span class='chip rojo' style='font-size:10.5px;'>" + esc(a.motivo_exclusion || "EXCLUIDA") + "</span>";

          var diagBadge = a.diagnostico_resultado ?
            (a.diagnostico_resultado === "PREÑADA" ? "<span class='chip verde' style='font-weight:700;'>PREÑADA (" + a.diagnostico_dias + "d)</span>" : "<span class='chip rojo'>VACÍA</span>") :
            "<span class='chip gris' style='font-size:11px;'>Pendiente Eco</span>";

          var btnExc = (a.estado === "ACTIVO" && lote.estado === "EN_CURSO") ?
            ("<button type='button' class='btn-exc-animal-iatf' data-tag='" + esc(a.tag) + "' style='font-size:11px; padding:2px 6px; border:1px solid #dc2626; color:#dc2626; background:transparent; border-radius:4px; cursor:pointer;'>Excluir</button>") : "";

          return "<tr>"
            + "<td><a href='#' class='ficha-link' data-ir-ficha='" + esc(a.tag) + "' style='font-weight:700; text-decoration:none;'><b>" + esc(a.tag) + "</b></a></td>"
            + "<td>" + (a.condicion_corporal_inicial ? ("CC: " + a.condicion_corporal_inicial) : "—") + "</td>"
            + "<td>" + estBadge + "</td>"
            + "<td>" + diagBadge + "</td>"
            + "<td style='text-align:right;'>" + btnExc + "</td>"
            + "</tr>";
        }).join("");

        var modalHtml = "<div id='iatf-detalle-modal' class='modal-overlay'>"
          + "<div class='modal-contenido' style='max-width:650px; max-height:85vh; overflow-y:auto;'>"
          + "<div class='modal-header'><b>" + icon("clipboard", 16) + "Detalle del Lote: " + esc(lote.nombre) + "</b><button type='button' class='modal-cerrar' id='btn-cerrar-det-lote-modal' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
          + "<div style='padding:16px;'>"
          + "<div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:12px; font-size:12.5px;'>"
          + "<div>Protocolo: <b>" + esc(lote.protocolo_nombre) + "</b> (" + esc(lote.protocolo_categoria) + ")</div>"
          + "<div>Inicio: <b>" + esc(fechaCorta(lote.fecha_inicio)) + "</b> · IATF: <b>" + esc(lote.hora_iatf) + "</b></div>"
          + "</div>"
          + "<div style='font-size:12.5px; font-weight:700; margin-bottom:4px;'>" + icon("pill", 14) + "Historial de Fármacos, Marcas y Dosis Aplicadas:</div>"
          + "<div class='tabla-scroll' style='margin-bottom:14px;'><table><tr><th>Fecha</th><th>Producto</th><th>Marca Usada</th><th>Dosis</th><th>Operario</th></tr>" + histHtml + "</table></div>"
          + "<div style='font-size:12.5px; font-weight:700; margin-bottom:4px;'>" + icon("cow", 14) + "Hembras del Lote (" + animales.length + "):</div>"
          + "<div class='tabla-scroll'><table><tr><th>Arete</th><th>CC Inicial</th><th>Estado</th><th>Diagnóstico</th><th style='text-align:right;'>Acción</th></tr>" + animsHtml + "</table></div>"
          + "</div></div></div>";

        var wrap = document.createElement("div");
        wrap.innerHTML = modalHtml;
        document.body.appendChild(wrap.firstChild);

        var ov = document.getElementById("iatf-detalle-modal");
        function cerrar() { if (ov) ov.remove(); }
        var btnC = document.getElementById("btn-cerrar-det-lote-modal");
        if (btnC) btnC.addEventListener("click", cerrar);
        ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

        qa(".btn-exc-animal-iatf").forEach(function (btn) {
          btn.addEventListener("click", function () {
            var tag = this.getAttribute("data-tag");
            var motivo = prompt("Motivo de exclusión de " + tag + " (ej. pérdida de dispositivo, celo anticipado, lesión):", "Pérdida de dispositivo");
            if (!motivo) return;
            fetch("/api/iatf/lotes/" + loteId + "/excluir", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tag: tag, motivo: motivo })
            }).then(function (r) { return r.json(); })
              .then(function (rx) {
                if (rx.ok) {
                  mostrarToast("Animal " + tag + " excluido", "ambar");
                  cerrar();
                  mostrarModalDetalleLoteIATF(loteId, onSuccess);
                  if (typeof onSuccess === "function") onSuccess();
                } else {
                  alert(rx.error || "No se pudo excluir");
                }
              });
          });
        });
      });
  }

  function renderKpisMercado(d) {
    var res = d.resumen_tendencias || {};
    var cats = [
      ["MACHO_GORDO", "Macho Gordo", "cow"],
      ["MACHO_LEVANTE", "Macho Levante", "cow"],
      ["TERNERO_DESTETO", "Ternero Desteto", "calf"],
      ["VACA_GORDA", "Vaca Descarte", "cow"]
    ];

    var htmlCards = cats.map(function (c) {
      var k = res[c[0]];
      if (!k) return "";
      var tendBadge = "";
      if (k.tendencia === "SUBIENDO") {
        tendBadge = "<span class='chip-tendencia subiendo'>▲ +" + (k.variacion_pct > 0 ? k.variacion_pct : "") + "% (+$" + Math.abs(k.variacion_pesos) + ")</span>";
      } else if (k.tendencia === "BAJANDO") {
        tendBadge = "<span class='chip-tendencia bajando'>▼ " + k.variacion_pct + "% (-$" + Math.abs(k.variacion_pesos) + ")</span>";
      } else {
        tendBadge = "<span class='chip-tendencia estable'>▬ 0.0% ($0)</span>";
      }

      var grTxt = k.precio_granada ? ("Granada: <b>" + fmtMoneda(k.precio_granada) + "</b>") : "";
      var topTxt = k.plaza_top ? ("Top: <b>" + esc(k.plaza_top.split("(")[0].trim()) + " " + fmtMoneda(k.precio_top) + "</b>") : "";

      return "<div class='mercado-kpi-card'>"
        + "<div class='mercado-kpi-tit'>" + icon(c[2], 13) + "<span>" + esc(c[1]) + "</span></div>"
        + "<div class='mercado-kpi-val'>" + fmtMoneda(k.promedio_mercado) + "<span style='font-size:12px; font-weight:normal; color:var(--texto-suave);'>/kg</span> " + tendBadge + "</div>"
        + "<div class='mercado-kpi-sub'><span>" + grTxt + "</span><span>·</span><span>" + topTxt + "</span></div>"
        + "</div>";
    }).join("");

    return "<div class='mercado-kpi-grid'>" + htmlCards + "</div>";
  }

