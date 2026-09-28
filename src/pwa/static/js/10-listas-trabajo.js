  // ---------- Listas de trabajo (todas las vistas) + chequeo del hato ----------
  // manejo: tipo que registra el botón "Hecho" (evento "manejo" en /api/sync).
  var LT_INFO = {
    palpar: { nombre: "Palpar", icono: "✋", vacio: "Ninguna vaca servida pendiente de palpar." },
    secar: { nombre: "Secar", icono: "🍼", vacio: "Ninguna vaca en ordeño para secar (preñez ≥ 7 meses o más de 305 días en leche)." },
    servir: { nombre: "Servir", icono: "💉", vacio: "Ninguna vaca parida pendiente de servir." },
    novillas: { nombre: "Novillas a entorar", icono: "🐄", vacio: "Ninguna novilla lista para entorar." },
    partos: { nombre: "Partos", icono: "🐣", vacio: "Ningún parto próximo ni atrasado." },
    celos: { nombre: "Celos", icono: "💗", vacio: "Ningún celo esperado en los próximos días." },
    repetidoras: { nombre: "Repetidoras", icono: "⚠️", vacio: "Ninguna vaca con problema reproductivo." },
    destetar: { nombre: "Destetar", icono: "🐮", vacio: "Ninguna cría pendiente de destete." },
    topizar: { nombre: "Topizar", icono: "✂️", vacio: "Ningún ternero pendiente de topizar.", manejo: "TOPIZADO" },
    castrar: { nombre: "Castrar", icono: "🔪", vacio: "Ningún macho pendiente de castrar.", manejo: "CASTRACION" },
    marcar: { nombre: "Marcar", icono: "🔥", vacio: "Ningún animal pendiente de marcar.", manejo: "MARCACION" },
    vac_brucelosis: { nombre: "Brucelosis", icono: "💉", vacio: "Ninguna ternera pendiente de vacuna de brucelosis.", manejo: "VACUNA_BRUCELOSIS" },
    vac_aftosa: { nombre: "Aftosa", icono: "💉", vacio: "Todo el hato está vacunado de aftosa en este ciclo.", manejo: "VACUNA_AFTOSA" },
    tratamientos: { nombre: "Tratamientos y retiros", icono: "💊", vacio: "Ningún tratamiento en seguimiento ni retiro por vencer." },
    pausas: { nombre: "A toda leche / pausadas", icono: "⏸️", vacio: "Ninguna vaca a toda leche ni con el ordeño pausado." },
    control_leche: { nombre: "Control lechero", icono: "🥛", vacio: "Todas las vacas en ordeño tienen control del último mes." },
    bajo_peso: { nombre: "Bajo peso", icono: "📉", vacio: "Ningún animal con ganancia baja en los últimos pesajes." },
    venta: { nombre: "Venta", icono: "💰", vacio: "Ningún macho en peso de venta (≥ 400 kg)." },
    descarte: { nombre: "Descarte", icono: "🚫", vacio: "Ninguna vaca candidata a descarte." },
    categoria: { nombre: "Cambio de categoría", icono: "🔁", vacio: "Ningún animal cambió de categoría este mes." }
  };

  function ltDetalle(clave, a) {
    var edad = a.edad_dias != null ? esc(edadCorta(a.edad_dias)) : "";
    switch (clave) {
      case "palpar": return "Servida " + esc(fechaCorta(a.fecha_servicio)) + " · hace " + esc(a.dias) + " d" + (a.toro ? " · " + esc(a.toro) : "");
      case "secar": return esc(a.motivo);
      case "servir": return "Parió " + esc(fechaCorta(a.ultimo_parto)) + " · " + esc(a.dias_abiertos) + " d abiertos";
      case "novillas": return edad + " · " + (a.peso_kg != null ? esc(a.peso_kg) + " kg" : "sin peso");
      case "partos": return a.estado === "ATRASADO"
        ? "<span class='chip rojo'>Atrasada " + esc(-a.en_dias) + " d</span> FEP " + esc(fechaCorta(a.fep))
        : "Parto en " + esc(a.en_dias) + " d (" + esc(fechaCorta(a.fep)) + ")";
      case "celos": return "Celo " + (a.en_dias === 0 ? "hoy" : a.en_dias < 0 ? "ayer" : "en " + esc(a.en_dias) + " d") + " (" + esc(fechaCorta(a.proximo_celo)) + ") · AM → inseminar PM";
      case "repetidoras": case "descarte": return esc(a.motivo);
      case "destetar": return edad + (a.madre ? " · madre " + esc(a.madre) : "");
      case "vac_aftosa": return a.ultima ? "Última aftosa " + esc(fechaCorta(a.ultima)) : "Sin aftosa registrada";
      case "tratamientos": return esc(a.detalle);
      case "control_leche": return esc(a.motivo) + (a.del_dias != null ? " · " + esc(a.del_dias) + " DEL" : "");
      case "pausas": return "Sin ordeñar desde " + esc(fechaCorta(a.desde)) + " (" + esc(a.dias) + " d)" + (a.motivo ? " · " + esc(a.motivo) : "");
      case "bajo_peso": return esc(a.gmd_g) + " g/día · " + esc(a.peso_kg) + " kg (" + esc(fechaCorta(a.fecha)) + ")";
      case "venta": return esc(a.peso_kg) + " kg" + (edad ? " · " + edad : "");
      case "categoria": return esc(a.cambio) + " · " + edad;
      default: return edad;
    }
  }

  function ltGruposPorPotrero(filas, filaHtml, abrir, accionGrupo) {
    var por = {}, pots = [];
    filas.forEach(function (a) {
      var p = a.potrero || "Sin potrero";
      if (!por[p]) { por[p] = []; pots.push(p); }
      por[p].push(a);
    });
    pots.sort(function (x, y) { return por[y].length - por[x].length || x.localeCompare(y); });
    return pots.map(function (p) {
      var tags = por[p].map(function (a) { return a.tag; }).join(",");
      return "<details class='gen-grupo pes-grupo'" + (abrir ? " open" : "") + "><summary><span>" + esc(p) + "</span><b>" + por[p].length
        + "</b><small>animales</small></summary>"
        + (accionGrupo ? "<div class='lt-grupo-accion'><button type='button' class='chip btn-lt-todos' data-tags='" + esc(tags) + "' data-potrero='" + esc(p) + "'>✓ Todos los de " + esc(p) + "</button></div>" : "")
        + por[p].map(filaHtml).join("") + "</details>";
    }).join("");
  }

  function ltFilaHtml(clave, a) {
    var info = LT_INFO[clave] || {};
    var acciones = "";
    if (clave === "castrar") {
      acciones = "<button type='button' class='chip btn-lt-hecho' data-tipo='CASTRACION'>Castrado</button>"
        + "<button type='button' class='chip btn-lt-hecho' data-tipo='ENTERO'>Queda entero</button>";
    } else if (clave === "secar") {
      acciones = "<button type='button' class='chip btn-lt-secado'>🍼 Secada / ya está seca</button>";
    } else if (info.manejo) {
      acciones = "<button type='button' class='chip btn-lt-hecho' data-tipo='" + info.manejo + "'>✓ Hecho</button>";
    }
    return "<div class='fila-pes fila-lt' data-tag='" + esc(a.tag) + "'><div class='fila-pes-cab'><span>" + enlaceFicha(a.tag)
      + (a.nombre ? " <small>" + esc(a.nombre) + "</small>" : "") + "</span></div><small>" + ltDetalle(clave, a) + "</small>"
      + (acciones ? "<div class='chk-acciones'>" + acciones + "</div><div class='chk-ok' hidden></div>" : "") + "</div>";
  }

  // t = datos_tareas (dict con listas + conteos); claves = listas de la vista.
  function renderListaTrabajo(t, claves, titulo) {
    if (!t) return "";
    if (t.responsables_sugeridos) window.__responsablesSugeridos = t.responsables_sugeridos;
    var c = t.conteos || {};
    var h = "<div class='card lt-card'>" + datalistResponsables() + "<div class='lt-titulo'>" + icon("calendar", 16) + esc(titulo || "Lista de trabajo") + "</div>";
    if (claves.indexOf("palpar") !== -1 && c.chequeo) {
      h += "<div class='lt-chequeo-aviso'><span>⚠️ <b>" + esc(c.chequeo) + "</b> hembras sin dato reproductivo en el último año. "
        + "Pálpalas y marca su estado para retomar el control.</span>"
        + "<button type='button' class='tema-btn btn-iniciar-chequeo'>Iniciar chequeo del hato</button></div>";
    }
    var primera = claves.filter(function (k) { return c[k]; })[0] || claves[0];
    if (window.__ltAbrir && claves.indexOf(window.__ltAbrir) !== -1) { primera = window.__ltAbrir; window.__ltAbrir = null; }
    h += "<div class='gen-filtros'>";
    claves.forEach(function (k) {
      h += "<button type='button' class='chip btn-lt" + (k === primera ? " act" : "") + "' data-lt='" + k + "'>"
        + LT_INFO[k].icono + " " + LT_INFO[k].nombre + " " + esc(c[k] || 0) + "</button>";
    });
    h += "</div>";
    claves.forEach(function (k) {
      var filas = t[k] || [];
      var info = LT_INFO[k];
      h += "<div class='lt-panel' data-lt='" + k + "'" + (k === primera ? "" : " hidden") + ">";
      if (k === "vac_aftosa" && t.ciclo_aftosa) h += "<p class='aviso'>Ciclo " + esc(t.ciclo_aftosa) + " (ICA). Anota producto y lote antes de marcar.</p>";
      if (info.manejo && filas.length) {
        h += "<div class='lt-producto'><input class='lt-resp-input' list='dl-responsables' placeholder='¿Quién lo hace?'>"
          + (k.indexOf("vac_") === 0 ? "<input class='lt-prod-input' placeholder='Producto'><input class='lt-lote-input' placeholder='Lote'>" : "")
          + "</div>";
      }
      h += filas.length ? ltGruposPorPotrero(filas, function (a) { return ltFilaHtml(k, a); }, filas.length <= 15, !!info.manejo && k !== "castrar")
        : vacio(info.vacio);
      h += "</div>";
    });
    return h + "</div>";
  }

  // "¿Quién palpa / quién lo hace?": se recuerda en este celular y se
  // sugiere con los inseminadores y responsables ya usados.
  function responsableGuardado() {
    var v = "";
    try { v = (localStorage.getItem("ja_responsable_campo") || "").trim(); } catch (e) { /* sin almacenamiento */ }
    if (!v || /^\d+$/.test(v) || v.toUpperCase().indexOf("HISTORIC") !== -1) {
      v = (window.__usuarioActual && window.__usuarioActual.nombre) || "";
      if (!v) {
        var yo = document.getElementById("menu-usuario-nombre");
        v = (yo && yo.textContent || "").trim();
        if (v === "Ganadería JA") v = "";
      }
    }
    return v;
  }
  function guardarResponsable(v) {
    try { localStorage.setItem("ja_responsable_campo", v); } catch (e) { /* sin almacenamiento */ }
  }
  function datalistResponsables() {
    var nombres = window.__responsablesSugeridos || [];
    if (!nombres.length && typeof _cacheInseminadores !== "undefined" && _cacheInseminadores && _cacheInseminadores.length) {
      nombres = _cacheInseminadores.map(function (it) { return it.nombre; });
    }
    return "<datalist id='dl-responsables'>" + nombres.map(function (n) { return "<option value='" + esc(n) + "'>"; }).join("") + "</datalist>";
  }

  function renderChequeoHato(lt) {
    var filas = (lt && lt.chequeo) || [];
    var h = "<div class='lt-chequeo'><div class='lt-chequeo-cab'><b>Chequeo del hato</b>"
      + "<span class='lt-progreso'>Hechas <b id='lt-hechas'>0</b> de " + filas.length + "</span>"
      + "<button type='button' class='tema-btn btn-cerrar-chequeo'>Cerrar</button></div>"
      + "<p class='aviso'>Marca cada vaca después de palparla. Si está preñada, elige los meses. Marca «Seca» si ya no se ordeña.</p>"
      + "<label class='lt-resp'>¿Quién palpa? <input id='chk-responsable' list='dl-responsables' placeholder='Palpador / veterinario' value='" + esc(responsableGuardado()) + "'></label>";
    h += ltGruposPorPotrero(filas, function (a) {
      var meses = "";
      for (var m = 1; m <= 9; m++) meses += "<button type='button' class='chip btn-chk-mes' data-mes='" + m + "'>" + m + "</button>";
      return "<div class='fila-pes fila-chk' data-tag='" + esc(a.tag) + "'>"
        + "<div class='fila-pes-cab'><span>" + enlaceFicha(a.tag) + (a.nombre ? " <small>" + esc(a.nombre) + "</small>" : "") + "</span>"
        + "<small>" + (a.fecha_ultimo_dato ? esc(a.ultimo_dato) + " " + esc(fechaCorta(a.fecha_ultimo_dato)) : "sin datos") + "</small></div>"
        + "<div class='chk-acciones'><button type='button' class='chip btn-chk' data-res='PREÑADA'>Preñada</button>"
        + "<button type='button' class='chip btn-chk' data-res='VACIA'>Vacía</button>"
        + "<label class='chk-seca'><input type='checkbox' class='chk-seca-input'> Seca</label></div>"
        + "<div class='chk-meses' hidden><small>Meses de preñez:</small> " + meses + "</div>"
        + "<div class='chk-ok' hidden>✓ Guardado</div></div>";
    }, false);
    return h + "</div>";
  }

  function enviarEventoLt(tipo, payload) {
    var fecha = new Date().toISOString().slice(0, 10);
    if (navigator.onLine === false) return encolarOffline(tipo, payload, fecha);
    return fetch("/api/sync", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ eventos: [{ tipo: tipo, payload: payload, fecha: fecha }] })
    }).then(function (r) { return r.json(); }).then(function (res) {
      if (!(res.ok && res.procesados > 0)) return encolarOffline(tipo, payload, fecha);
    }).catch(function () { return encolarOffline(tipo, payload, fecha); });
  }

  function ltMarcarHecha(fila, texto) {
    fila.classList.add("hecha");
    var acc = fila.querySelector(".chk-acciones");
    if (acc) acc.hidden = true;
    var ok = fila.querySelector(".chk-ok");
    if (ok) { ok.textContent = "✓ " + texto; ok.hidden = false; }
  }

  function bindListaTrabajo() {
    qa(".lt-resp-input").forEach(function (i) { if (!i.value) i.value = responsableGuardado(); });
    qa(".lt-card").forEach(function (card) {
      card.querySelectorAll(".btn-lt").forEach(function (b) {
        b.addEventListener("click", function () {
          var k = b.getAttribute("data-lt");
          card.querySelectorAll(".btn-lt").forEach(function (o) { o.classList.toggle("act", o === b); });
          card.querySelectorAll(".lt-panel").forEach(function (p) { p.hidden = p.getAttribute("data-lt") !== k; });
        });
      });
    });
    function extras(panel) {
      var prod = panel && panel.querySelector(".lt-prod-input");
      var lote = panel && panel.querySelector(".lt-lote-input");
      var resp = panel && panel.querySelector(".lt-resp-input");
      if (resp && resp.value.trim()) guardarResponsable(resp.value.trim());
      return { producto: (prod && prod.value.trim()) || null, lote_producto: (lote && lote.value.trim()) || null,
               responsable: (resp && resp.value.trim()) || null };
    }
    qa(".btn-lt-hecho").forEach(function (b) {
      b.addEventListener("click", function () {
        var fila = b.closest(".fila-lt");
        var tipo = b.getAttribute("data-tipo");
        var ex = extras(b.closest(".lt-panel"));
        fila.querySelectorAll("button").forEach(function (x) { x.disabled = true; });
        enviarEventoLt("manejo", { animal_tag: fila.getAttribute("data-tag"), tipo_manejo: tipo, producto: ex.producto, lote_producto: ex.lote_producto, responsable: ex.responsable })
          .then(function () { ltMarcarHecha(fila, b.textContent.replace("✓", "").trim()); });
      });
    });
    qa(".btn-lt-secado").forEach(function (b) {
      b.addEventListener("click", function () {
        var fila = b.closest(".fila-lt");
        b.disabled = true;
        enviarEventoLt("secado", { animal_tag: fila.getAttribute("data-tag"), motivo: "Marcada en la lista Secar" })
          .then(function () { ltMarcarHecha(fila, "Seca"); });
      });
    });
    qa(".btn-lt-todos").forEach(function (b) {
      b.addEventListener("click", function () {
        var tags = (b.getAttribute("data-tags") || "").split(",").filter(Boolean);
        var panel = b.closest(".lt-panel");
        var hecho = panel && panel.querySelector(".btn-lt-hecho");
        if (!tags.length || !hecho) return;
        if (!confirm("¿Marcar como hechos los " + tags.length + " animales de " + b.getAttribute("data-potrero") + "?")) return;
        var ex = extras(panel);
        b.disabled = true;
        enviarEventoLt("manejo", { animal_tags: tags, tipo_manejo: hecho.getAttribute("data-tipo"), producto: ex.producto, lote_producto: ex.lote_producto, responsable: ex.responsable })
          .then(function () {
            b.closest("details").querySelectorAll(".fila-lt").forEach(function (f) { ltMarcarHecha(f, "Hecho"); });
            b.textContent = "✓ " + tags.length + " marcados";
          });
      });
    });
    var btnIni = q(".btn-iniciar-chequeo");
    var lt = window.__listaTrabajo;
    if (!btnIni || !lt) return;
    btnIni.addEventListener("click", function () {
      var card = btnIni.closest(".lt-card");
      var cont = document.createElement("div");
      cont.innerHTML = renderChequeoHato(lt);
      card.parentNode.insertBefore(cont.firstChild, card.nextSibling);
      card.hidden = true;
      bindChequeoHato();
      var chk = q(".lt-chequeo");
      if (chk && chk.scrollIntoView) chk.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function bindChequeoHato() {
    var hechas = 0;
    function guardar(fila, resultado, meses) {
      var inpResp = q("#chk-responsable");
      var responsable = ((inpResp && inpResp.value) || "").trim();
      if (!responsable) {
        alert("Escribe quién palpa antes de marcar las vacas: así se puede evaluar al palpador.");
        if (inpResp) inpResp.focus();
        return;
      }
      guardarResponsable(responsable);
      var tag = fila.getAttribute("data-tag");
      var seca = fila.querySelector(".chk-seca-input").checked;
      var payload = { animal_tag: tag, resultado: resultado, metodo: "TACTO", detalle: "Chequeo del hato", responsable: responsable };
      if (meses) payload.dias_gestacion = meses * 30;
      fila.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
      enviarEventoLt("diagnostico", payload).then(function () {
        if (seca) return enviarEventoLt("secado", { animal_tag: tag, motivo: "Chequeo del hato", notas: "Palpó: " + responsable });
      }).then(function () {
        fila.querySelector(".chk-meses").hidden = true;
        ltMarcarHecha(fila, (resultado === "VACIA" ? "Vacía" : "Preñada " + meses + " m") + (seca ? " · Seca" : ""));
        hechas++;
        var el = q("#lt-hechas");
        if (el) el.textContent = hechas;
      });
    }
    qa(".fila-chk").forEach(function (fila) {
      fila.querySelectorAll(".btn-chk").forEach(function (b) {
        b.addEventListener("click", function () {
          if (b.getAttribute("data-res") === "VACIA") guardar(fila, "VACIA", null);
          else fila.querySelector(".chk-meses").hidden = false;
        });
      });
      fila.querySelectorAll(".btn-chk-mes").forEach(function (b) {
        b.addEventListener("click", function () { guardar(fila, "PREÑADA", Number(b.getAttribute("data-mes"))); });
      });
    });
    var cerrar = q(".btn-cerrar-chequeo");
    if (cerrar) cerrar.addEventListener("click", function () { cargar(true); });
  }

  // Toro: un solo estado (en servicio / descanso) con botón para cambiarlo.
  function botonToroEstado(t) {
    var enServ = t.estado === "EN_SERVICIO";
    return "<button type='button' class='chip btn-toro-estado' data-tag='" + esc(t.tag) + "' data-tipo='"
      + (enServ ? "TORO_DESCANSO" : "TORO_SERVICIO") + "'>" + (enServ ? "Poner en descanso" : "Poner en servicio") + "</button>";
  }
  function renderToroServicio(t) {
    var enServ = t.estado === "EN_SERVICIO";
    return "<div class='card toro-card " + (enServ ? "en-servicio" : "") + "'>"
      + "<div class='toro-card-cab'><b>" + icon("crown", 16) + " Reproductor</b>"
      + "<span class='chip " + (enServ ? "verde" : "gris") + "'><b>" + (enServ ? "En servicio" : "En descanso") + "</b></span></div>"
      + "<p class='toro-card-det'>" + esc(t.motivo)
      + (t.ultima_monta ? " · última monta " + esc(fechaCorta(t.ultima_monta)) : "")
      + " · " + esc(t.n_crias || 0) + " crías registradas</p>"
      + botonToroEstado(t) + "</div>";
  }
  document.addEventListener("click", function (e) {
    var b = e.target && e.target.closest ? e.target.closest(".btn-toro-estado") : null;
    if (!b) return;
    b.disabled = true;
    enviarEventoLt("manejo", { animal_tag: b.getAttribute("data-tag"), tipo_manejo: b.getAttribute("data-tipo") })
      .then(function () {
        if (/^\/ficha\//.test(location.pathname)) location.reload();
        else cargar(true);
      });
  });

