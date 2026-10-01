  function pintarSugerencias(res) {
    var out = document.getElementById("ident-resultado");
    if (!out) return;
    var mensaje = document.getElementById("ident-estado");
    if (res.existe) { abrirFicha(res.tag, vista, true); return; }
    if (res.error) {
      if (mensaje) mensaje.textContent = "";
      out.innerHTML = "<p class='aviso'>" + icon("xCircle", 14) + esc(res.error) + "</p>";
      return;
    }
    if (res.ocr_tag) {
      if (mensaje) mensaje.textContent = "OCR leyó: " + esc(res.ocr_tag) + (res.confianza ? " (confianza " + Math.round(res.confianza * 100) + "%)" : "");
    } else if (mensaje) {
      mensaje.textContent = "";
    }
    if (res.sugerencias && res.sugerencias.length) {
      var h = "<p class='aviso'>¿Quiso decir alguno de estos?</p>";
      h += "<div class='fotos-wrap'>" + res.sugerencias.map(function (s) {
        return "<button data-tag='" + esc(s.tag) + "' class='chip' style='font-size:13px'>" + icon("cow", 14) + esc(s.tag)
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
  var _qrStream = null;
  var _qrTimer = null;
  function detenerEscanerQR() {
    if (_qrTimer) { clearInterval(_qrTimer); _qrTimer = null; }
    if (_qrStream) {
      _qrStream.getTracks().forEach(function (t) { t.stop(); });
      _qrStream = null;
    }
    var v = document.getElementById("qr-video");
    if (v) { v.style.display = "none"; v.srcObject = null; }
    var boton = document.getElementById("btn-scan-qr");
    if (boton) boton.textContent = "";
    var est = document.getElementById("ident-estado");
    if (boton) boton.innerHTML = icon("camera") + "Escanear QR";
    if (est && est.getAttribute("data-scan") === "1") est.textContent = "";
  }
  function escanearQRCamara() {
    var estado = document.getElementById("ident-estado");
    var video = document.getElementById("qr-video");
    var boton = document.getElementById("btn-scan-qr");
    var out = document.getElementById("ident-resultado");
    if (!video || !boton) return;
    if (_qrStream) { detenerEscanerQR(); return; }
    if (!("BarcodeDetector" in window)) {
      if (estado) estado.textContent = "Tu navegador no permite escanear QR con cámara (usa Chrome/Edge). Escribe el código en el campo Tag.";
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (estado) estado.textContent = "Cámara no disponible en este dispositivo/navegador.";
      return;
    }
    if (estado) { estado.setAttribute("data-scan", "1"); estado.textContent = "Apuntando a un QR de ficha… toca 'Escanear QR' para detener."; }
    if (out) out.innerHTML = "";
    boton.innerHTML = icon("xmark") + "Detener";
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } } })
      .then(function (stream) {
        _qrStream = stream;
        video.srcObject = stream;
        video.style.display = "block";
        video.play().catch(function () { /* noop */ });
        var detector = new window.BarcodeDetector({ formats: ["qr_code"] });
        _qrTimer = setInterval(function () {
          if (!_qrStream) return;
          detector.detect(video).then(function (codes) {
            if (!codes || !codes.length) return;
            var value = (codes[0].rawValue || "").trim();
            var m = value.match(/JA:\/\/animal\/([A-Za-z0-9_-]+)/i) || value.match(/\/ficha\/([A-Za-z0-9_-]+)\/?/i);
            if (!m) { if (estado) estado.textContent = "QR leído, pero no es de una ficha del hato."; return; }
            detenerEscanerQR();
            var tag = m[1];
            if (q("#f-tag")) q("#f-tag").value = tag;
            abrirFicha(tag, vista, true, true);
          }).catch(function () { /* siguiente frame */ });
        }, 350);
      })
      .catch(function (e) {
        if (estado) { estado.removeAttribute("data-scan"); estado.textContent = "No se pudo abrir la cámara (permiso o HTTPS). " + (e && e.name || ""); }
        boton.innerHTML = icon("camera") + "Escanear QR";
      });
  }
  function bindIdent() {
    var btn = document.getElementById("btn-ident");
    var file = document.getElementById("f-ident-foto");
    var btnQr = document.getElementById("btn-scan-qr");
    if (!btn || !file) return;
    file.addEventListener("change", function () {
      var nom = document.getElementById("ident-foto-nombre");
      if (!nom) return;
      nom.textContent = (file.files && file.files[0]) ? file.files[0].name : "Ninguna foto";
    });
    btn.addEventListener("click", function () {
      var estado = document.getElementById("ident-estado");
      var out = document.getElementById("ident-resultado");
      if (out) out.innerHTML = "";
      if (estado) estado.textContent = "Identificando…";
      if (file.files && file.files[0]) {
        var fd = new FormData();
        fd.append("foto", file.files[0]);
        fetch("/api/identificar", { method: "POST", body: fd })
          .then(function (r) { if (r.status === 401) { window.location = "/login"; throw new Error("no autorizado"); } if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
          .then(pintarSugerencias)
          .catch(function (e) { if (estado) estado.textContent = (e && e.message || e); });
      } else {
        var t = obtenerTextoIdent();
        if (!t) { if (estado) estado.textContent = "Escriba el arete/RFID arriba o elija una foto."; return; }
        var fd2 = new FormData();
        fd2.append("texto", t);
        fetch("/api/identificar", { method: "POST", body: fd2 })
          .then(function (r) { if (r.status === 401) { window.location = "/login"; throw new Error("no autorizado"); } if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
          .then(pintarSugerencias)
          .catch(function (e) { if (estado) estado.textContent = (e && e.message || e); });
      }
    });
    if (btnQr) btnQr.addEventListener("click", escanearQRCamara);
  }
  // Autocompletar (datalist) para tag, potrero y toros.
  function rellenarDatalist(id, items) {
    var dl = document.getElementById(id);
    if (!dl || !items) return;
    dl.innerHTML = items.map(function (x) {
      if (typeof x === "object" && x !== null) {
        var val = x.value !== undefined ? String(x.value) : "";
        var lbl = x.label !== undefined ? String(x.label) : "";
        if (lbl && lbl !== val) {
          return "<option value='" + esc(val) + "' label='" + esc(lbl) + "'>" + esc(lbl) + "</option>";
        }
        return "<option value='" + esc(val) + "'>";
      }
      return "<option value='" + esc(x) + "'>";
    }).join("");
  }
  function sugerirDesde(q) {
    if (!q) { cargarListasAutocompletar(); return; }
    fetch("/api/buscar?q=" + encodeURIComponent(q)).then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.animales) {
          rellenarDatalist("dl-tags", d.animales.map(function (a) {
            var desc = (a.tag || "") + (a.nombre ? " · " + a.nombre : "") + (a.categoria ? " (" + a.categoria + ")" : "");
            return { value: a.tag, label: desc };
          }));
        }
        if (d && d.potreros) {
          rellenarDatalist("dl-potreros", d.potreros.map(function (p) { return p.nombre || p.codigo; }));
        }
      }).catch(function () { /* best-effort */ });
  }
  var _deb = null;
  function onInputSugerir(ev) {
    var v = (ev.target && ev.target.value || "").trim();
    if (!v) { cargarListasAutocompletar(); return; }
    clearTimeout(_deb);
    _deb = setTimeout(function () { sugerirDesde(v); }, 250);
  }
  // Llena los datalists de potreros y tags activos con la lista completa.
  function cargarListasAutocompletar() {
    fetch("/api/buscar?q=").then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.potreros) {
          rellenarDatalist("dl-potreros", d.potreros.map(function (p) { return p.nombre || p.codigo; }));
        }
        if (d && d.animales && d.animales.length) {
          rellenarDatalist("dl-tags", d.animales.map(function (a) {
            var desc = (a.tag || "") + (a.nombre ? " · " + a.nombre : "") + (a.categoria ? " (" + a.categoria + ")" : "");
            return { value: a.tag, label: desc };
          }));
        }
        cargarListaInseminadores();
      }).catch(function () { /* best-effort */ });
  }
  var cargarListaPotreros = cargarListasAutocompletar; // Alias de retrocompatibilidad

  function simplificarRazaToro(raza) {
    if (!raza) return "";
    var r = raza.trim();
    if (r.indexOf("+") !== -1) {
      r = r.split("+")[0].trim();
    }
    r = r.replace(/^\s*(\d+\/\d+|\d+(\.\d+)?%)\s*/i, "").trim();
    r = r.replace(/\s+Puro$/i, "").trim();
    return r;
  }

  var _cacheToros = null;
  function cargarListaToros(selEl) {
    function poblar(toros) {
      if (!toros) toros = [];
      var itemsDl = toros.map(function (t) {
        var rCorta = simplificarRazaToro(t.raza);
        var nomLimpio = (t.nombre || "").replace(/\s+/g, " ").trim();
        var desc = (t.tag || "") + (nomLimpio ? " · " + nomLimpio : "") + (rCorta ? " (" + rCorta + ")" : "");
        return { value: t.tag, label: desc };
      });
      rellenarDatalist("dl-toros", itemsDl);

      var sel = selEl || document.getElementById("cap-toro-padre");
      if (sel) {
        var valActual = sel.value || "";
        var optHtml = "<option value=''>-- Sin especificar (opcional) --</option>";
        toros.forEach(function (t) {
          var rCorta = simplificarRazaToro(t.raza);
          var nomLimpio = (t.nombre || "").replace(/\s+/g, " ").trim();
          var label = (t.tag || "") + (nomLimpio ? " · " + nomLimpio : "") + (rCorta ? " (" + rCorta + ")" : "");
          optHtml += "<option value='" + esc(t.tag) + "'>" + esc(label) + "</option>";
        });
        optHtml += "<option value='OTRO'>-- Otro toro / Pajilla / Externo --</option>";
        sel.innerHTML = optHtml;
        if (valActual) sel.value = valActual;
      }
    }

    if (_cacheToros) {
      poblar(_cacheToros);
      return;
    }

    fetch("/api/toros").then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.toros) {
          _cacheToros = d.toros;
          poblar(_cacheToros);
        }
      }).catch(function () { /* best-effort */ });
  }

  function renderFichaBuscador() {
    var ultimoTag = (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
    var chipsSugeridos = "";
    if (ultimoTag) {
      chipsSugeridos += "<button type='button' class='chip verde btn-chip-tag' data-tag='" + esc(ultimoTag) + "' style='font-size:12px; cursor:pointer;'>" + icon("refresh", 13) + "Último visto: <b>" + esc(ultimoTag) + "</b></button>";
    }
    chipsSugeridos += "<button type='button' class='chip azul btn-chip-tag' data-tag='183-4' style='font-size:12px; cursor:pointer;'>" + icon("cow", 13) + "Toro 183-4</button>";
    chipsSugeridos += "<button type='button' class='chip azul btn-chip-tag' data-tag='JA-01' style='font-size:12px; cursor:pointer;'>" + icon("cow", 13) + "Toro JA-01</button>";

    var h = "<div class='ficha-buscador-wrap' style='max-width:760px; margin:0 auto;'>"
      + "<div class='card ficha-buscador-card' style='padding:20px; margin-bottom:16px;'>"
      + "<h3 style='margin:0 0 8px 0; display:flex; align-items:center; gap:8px; font-size:18px; color:var(--verde-marca);'>"
      + icon("cow", 22) + "Buscar Ficha de Animal</h3>"
      + "<p style='margin:0 0 16px 0; font-size:13.5px; color:var(--texto-suave);'>"
      + "Ingresa el número de arete, RFID, tatuaje o nombre para ver genealogía, pesajes, eventos reproductivos y sanitarios."
      + "</p>"
      + "<form id='form-buscar-ficha-vista' style='display:flex; flex-direction:column; gap:12px;'>"
      + "<label style='font-size:13px; font-weight:600; color:var(--texto); display:flex; flex-direction:column; gap:6px;'>"
      + "Arete, RFID o nombre del animal:"
      + "<div class='ficha-buscador-input-wrap'>"
      + "<input type='text' id='input-tag-ficha-vista' list='dl-tags' placeholder='ej. 47, JA176, N069, PATRICIA, TORO...' autocomplete='off' autofocus style='padding:12px 14px; border-radius:8px; border:1.5px solid var(--borde-fuerte); font-size:15px; font-weight:600; color:var(--texto); background:var(--fondo); outline:none; box-sizing:border-box;'>"
      + "<button type='submit' class='tema-btn btn-buscar-ficha-submit' style='background:var(--verde-marca); color:#fff; font-weight:700; padding:12px 18px; border:none; border-radius:8px; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; gap:6px; font-size:14px; white-space:nowrap;'>"
      + icon("search", 15) + "Buscar Ficha</button>"
      + "</div>"
      + "</label>"
      + "<div id='ficha-vista-feedback' style='font-size:12.5px; color:var(--color-rojo-txt); min-height:18px;'></div>"
      + "</form>"
      + (chipsSugeridos ? "<div style='margin-top:8px; display:flex; flex-wrap:wrap; align-items:center; gap:8px;'><span style='font-size:12px; font-weight:600; color:var(--texto-suave);'>Sugerencias rápidas:</span>" + chipsSugeridos + "</div>" : "")
      + "</div>"
      + "<div class='card' style='padding:16px; margin-bottom:16px;'>"
      + "<h4 style='margin:0 0 8px 0; display:flex; align-items:center; gap:8px; font-size:15px;'>"
      + icon("camera", 16) + "O identificar mediante Foto / Arete OCR</h4>"
      + "<p style='margin:0 0 12px 0; font-size:13px; color:var(--texto-suave);'>"
      + "Si tienes una foto del arete tomada en campo o un lector QR, puedes subirla aquí para lectura inteligente."
      + "</p>"
      + identPanelHtml()
      + "</div>"
      + "</div>";

    return h;
  }

  function bindFichaBuscador() {
    var form = document.getElementById("form-buscar-ficha-vista");
    var inp = document.getElementById("input-tag-ficha-vista");
    var feedback = document.getElementById("ficha-vista-feedback");
    try { cargarListasAutocompletar(); } catch (eDl) {}

    if (form && inp) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var tag = (inp.value || "").trim();
        if (!tag) {
          if (feedback) feedback.textContent = "Por favor escribe un arete, RFID o nombre.";
          inp.focus();
          return;
        }
        if (feedback) feedback.textContent = "";
        abrirFichaDesdeTag(tag);
      });
      inp.addEventListener("input", onInputSugerir);
    }

    qa(".btn-chip-tag").forEach(function (b) {
      b.addEventListener("click", function () {
        var t = b.getAttribute("data-tag");
        if (t) {
          if (inp) inp.value = t;
          abrirFichaDesdeTag(t);
        }
      });
    });

    bindIdent();

    setTimeout(function () {
      if (inp) {
        inp.focus();
        inp.select();
      }
    }, 100);
  }

  function cargar(animar) {
    if (animar === undefined) animar = true;
    actualizarFabGlobal();

    var barraFiltros = document.getElementById("barra-filtros");
    if (barraFiltros) {
      if (actual === "tablero") {
        var hayFiltro = (q("#f-potrero") && q("#f-potrero").value.trim()) || (q("#f-tag") && q("#f-tag").value.trim());
        // El forzado solo vive mientras haya filtro: si el usuario lo
        // borra, la barra vuelve a ocultarse sola en el celular.
        if (!hayFiltro) barraFiltros.__forzadoVisible = false;
        if (window.innerWidth <= 640 && !hayFiltro && !barraFiltros.__forzadoVisible) {
          barraFiltros.style.display = "none";
        } else {
          barraFiltros.style.display = "";
        }
      } else {
        barraFiltros.style.display = "none";
      }
    }

    if (actual === "ficha") {
      var t = (q("#f-tag") && q("#f-tag").value || "").trim();
      if (!t) {
        if (vista) {
          montarVista(vista, renderFichaBuscador(), animar);
          bindFichaBuscador();
        }
        return;
      }
      abrirFicha(t, vista, true, animar);
      return;
    }

    if (actual === "manga") {
      if (!animar) return; // En polling silencioso no resetear la manga
      if (vista) {
        montarVista(vista, renderManga(), animar);
        bindManga();
      }
      return;
    }

    if (actual === "captura") {
      if (!animar) return; // En polling silencioso no resetear captura
      if (vista) {
        montarVista(vista, renderCaptura(), animar);
        bindCaptura();
      }
      return;
    }

    if (actual === "ayuda") {
      if (!animar) return; // En polling silencioso no resetear ayuda
      if (vista) {
        montarVista(vista, renderAyuda(), animar);
        bindAyuda();
      }
      return;
    }

    if (actual === "gps") {
      irAVista("mapa");
      cargar(animar);
      return;
    }

    if (actual === "sistema") {
      if (animar) skeleton(vista, "sistema");
      fetchJSON("/api/sistema", function (d) {
        if (!vista) return;
        montarVista(vista, renderSistema(d), animar);
        bindSistema();
      }, animar ? vista : null);
      return;
    }

    if (actual === "revision") {
      if (animar) skeleton(vista, "revision");
      fetchJSON("/api/revision/pendientes", function (d) {
        if (!vista) return;
        // El polling silencioso no borra lo que el revisor está corrigiendo.
        if (!animar && vista.querySelector(".rev-campos:not([hidden]), .rev-rechazo:not([hidden])")) return;
        montarVista(vista, renderRevision(d), animar);
        bindRevision();
      }, animar ? vista : null);
      return;
    }

    if (actual === "usuarios") {
      if (!animar) return; // En polling silencioso no resetear el formulario de usuarios
      if (animar) skeleton(vista, "usuarios");
      fetch("/api/heartbeat", { method: "POST" }).catch(function () {}).finally(function () {
        fetchJSON("/api/usuarios", function (d) {
          if (!vista) return;
          montarVista(vista, renderUsuarios(d), animar);
          bindUsuarios(d);
        }, animar ? vista : null);
      });
      return;
    }

    if (actual === "mapa") {
      var rol = (window.__usuarioActual && window.__usuarioActual.rol || "").toUpperCase();
      if (rol === "TRABAJADOR") {
        irAVista("captura");
        cargar(true);
        return;
      }
      if (animar) skeleton(vista, "mapa");
      var fFecha = _fechaFiltroRutas || (q("#filtro-fecha-rutas") && q("#filtro-fecha-rutas").value) || new Date().toISOString().slice(0, 10);
      fetchJSON("/api/mapa/datos?fecha=" + encodeURIComponent(fFecha), function (d) {
        if (!vista) return;
        montarVista(vista, renderMapa(d), animar);
        cargarLeafletSiFalta(function () { bindMapa(d); });
      }, animar ? vista : null);
      return;
    }

    if (actual === "mercado") {
      var rolMerc = (window.__usuarioActual && window.__usuarioActual.rol || "").toUpperCase();
      if (rolMerc === "TRABAJADOR") {
        irAVista("captura");
        cargar(true);
        return;
      }
      if (animar) skeleton(vista, "mercado");
      fetchJSON("/api/mercado/precios", function (d) {
        if (!vista) return;
        montarVista(vista, renderMercado(d), animar);
        bindMercado(d);
      }, animar ? vista : null);
      return;
    }

    var pot = (q("#f-potrero") && q("#f-potrero").value || "").trim();
    var url = "/api/" + actual + (pot && actual === "tablero" ? "?potrero=" + encodeURIComponent(pot) : "");
    if (actual === "carne" && (_carneRango.desde || _carneRango.hasta)) {
      url += "?desde=" + encodeURIComponent(_carneRango.desde || "") + "&hasta=" + encodeURIComponent(_carneRango.hasta || "");
    }
    if (actual === "repro" && (_reproRango.desde || _reproRango.hasta)) {
      url += "?desde=" + encodeURIComponent(_reproRango.desde || "") + "&hasta=" + encodeURIComponent(_reproRango.hasta || "");
    }
    if (animar) skeleton(vista, actual);
    fetchJSON(url, function (d) {
      if (!vista) return;
      var html;
      if (actual === "tablero") html = renderTablero(d);
      else if (actual === "repro") html = renderRepro(d);
      else if (actual === "carne") html = renderCarne(d);
      else if (actual === "sanidad") html = renderSanidad(d);
      else if (actual === "pasturas") html = renderPasturas(d);
      else if (actual === "leche") html = renderLeche(d);
      else if (actual === "inventario") html = renderInventario(d);
      else if (actual === "poblacion") html = renderInventario(d); // alias (vista unificada)
      else if (actual === "genetica") html = renderGenetica(d);
      else if (actual === "agenda") html = renderAgenda(d);
      else if (actual === "finanzas") html = renderFinanzas(d);
      montarVista(vista, html, animar);
      if (actual === "tablero") bindTablero();
      if (actual === "repro") bindRepro();
      if (actual === "carne") bindCarne();
      if (actual === "pasturas") bindPasturas();
      if (actual === "leche") bindLeche();
      if (actual === "finanzas") bindFinanzas();
      if (actual === "agenda") bindAgenda();
      if (actual === "sanidad") bindSanidad();
      if (actual === "genetica") bindGenetica(d);
      if (actual === "inventario" || actual === "poblacion") bindDatosRevisar();
      if (window.__kpiDestino) {
        var kd = window.__kpiDestino;
        window.__kpiDestino = null;
        setTimeout(function () { aplicarDestinoLocal(null, kd.filtro, kd.sec); }, 80);
      }
    }, animar ? vista : null);
  }

