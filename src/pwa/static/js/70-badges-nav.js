  /* ---------- Badges de contadores en la navegación ---------- */
  var VISTAS_BADGE = ["agenda", "repro", "sanidad"];
  var badgesCache = {};
  function crearBadgesNav() {
    VISTAS_BADGE.forEach(function (v) {
      var btn = qa("#nav-principal button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
      if (!btn || btn.querySelector(".nav-badge")) return;
      var span = document.createElement("span");
      span.className = "nav-badge";
      span.textContent = "";
      btn.appendChild(span);
    });
  }
  function actualizarBadges() {
    if (navigator.onLine === false) return;
    fetch("/api/badges").then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) {
        badgesCache = d || {};
        var totalSecundario = 0;
        VISTAS_BADGE.forEach(function (v) {
          var n = parseInt(d && d[v], 10) || 0;
          var btn = qa("#nav-principal button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
          if (btn) {
            var span = btn.querySelector(".nav-badge");
            if (span) {
              if (n > 0) { span.textContent = n > 99 ? "99+" : String(n); span.classList.add("on"); }
              else { span.textContent = ""; span.classList.remove("on"); }
            }
          }
          var item = document.querySelector("#modal-mas-modulos .modulo-item[data-v='" + v + "']");
          if (item) {
            var bSpan = item.querySelector(".badge-sheet");
            if (!bSpan) {
              bSpan = document.createElement("span");
              bSpan.className = "badge-sheet";
              item.appendChild(bSpan);
            }
            if (n > 0) {
              bSpan.textContent = n > 99 ? "99+" : String(n);
              bSpan.style.display = "inline-block";
            } else {
              bSpan.textContent = "";
              bSpan.style.display = "none";
            }
          }
          totalSecundario += n;
        });

        var btnMas = document.getElementById("btn-nav-mas");
        if (btnMas) {
          var spanMas = btnMas.querySelector(".nav-badge");
          if (!spanMas) {
            spanMas = document.createElement("span");
            spanMas.className = "nav-badge";
            btnMas.appendChild(spanMas);
          }
          if (totalSecundario > 0) {
            spanMas.textContent = totalSecundario > 99 ? "99+" : String(totalSecundario);
            spanMas.classList.add("on");
          } else {
            spanMas.textContent = "";
            spanMas.classList.remove("on");
          }
        }

        // Campana del header (total = agenda) + notificación al aumentar.
        var camp = document.getElementById("notif-dot");
        var nA = parseInt(d && d.agenda, 10) || 0;
        if (camp) {
          if (nA > 0) { camp.textContent = nA > 99 ? "99+" : String(nA); camp.classList.add("on"); }
          else { camp.textContent = ""; camp.classList.remove("on"); }
        }
        actualizarMenuAvisos(nA);
        var prev = window.__agendaPrev || -1;
        if (prev >= 0 && nA > prev && nA > 0 && document.hidden
            && "Notification" in window && Notification.permission === "granted") {
          try {
            var notif = new Notification("Bitácora JA", {
              body: nA + " aviso(s) pendientes en la Agenda (partos, secado, retiros).",
              tag: "bitacora-aviso", icon: "/static/icon-192.png"
            });
            notif.onclick = function () { window.focus(); };
          } catch (e) { /* noop */ }
        }
        window.__agendaPrev = nA;
        verificarAlertasPush();
      }).catch(function () { /* sin red: se ocultan */ });
  }

  // Panel de la campanita: muestra pendientes/próximos (alertas + eventos +
  // retiros) en un modal táctil y ofrece ir a la Agenda completa. Reusa
  // /api/agenda, sin duplicar la lógica de renderAgenda.
  function abrirPanelCampana() {
    if (document.getElementById("modal-campana-agenda")) return;
    var html = "<div id='modal-campana-agenda' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:520px; max-height:86vh; display:flex; flex-direction:column; overflow:hidden;'>"
      + "<div class='modal-header'><b>🔔 Pendientes y próximos</b><button type='button' class='modal-cerrar' id='btn-cerrar-campana'>✕</button></div>"
      + "<div id='campana-cuerpo' style='padding:14px 16px; overflow-y:auto; -webkit-overflow-scrolling:touch; font-size:13.5px;'>Cargando agenda...</div>"
      + "<div style='padding:10px 16px; border-top:1px solid var(--borde); display:flex; gap:8px;'>"
      + "<button type='button' id='btn-campana-ver-agenda' class='btn-guardar-manga' style='flex:1;'>Abrir Agenda completa</button>"
      + "</div></div></div>";
    document.body.insertAdjacentHTML("beforeend", html);
    var ov = document.getElementById("modal-campana-agenda");
    function cerrar() { if (ov) ov.remove(); }
    document.getElementById("btn-cerrar-campana").addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });
    document.getElementById("btn-campana-ver-agenda").addEventListener("click", function () {
      cerrar();
      var destino = qa("#nav-principal button").filter(function (b) { return b.getAttribute("data-v") === "agenda"; })[0];
      if (destino) destino.click();
    });
    var cuerpo = document.getElementById("campana-cuerpo");
    fetch("/api/agenda?dias=7").then(function (r) { return r.json(); }).then(function (d) {
      if (!cuerpo) return;
      var evs = (d && d.eventos) || [];
      var recs = (d && d.recordatorios) || [];
      var rets = (d && d.retiros) || [];
      if (!evs.length && !recs.length && !rets.length) {
        cuerpo.innerHTML = "<p class='aviso'>🎉 Sin pendientes en los próximos " + esc((d && d.dias) || 7) + " días.</p>";
        return;
      }
      var h = "";
      recs.slice(0, 5).forEach(function (rc) {
        h += "<div style='padding:8px 10px; border:1px solid var(--borde); border-radius:8px; margin-bottom:8px;'>"
          + "<b>📌 " + esc(rc.mensaje || "Evento") + "</b><br>"
          + "<small style='color:var(--texto-suave);'>" + esc(rc.fecha || "—") + (rc.hora ? " " + esc(rc.hora) : "") + " · " + esc(rc.faltan_dias != null ? (rc.faltan_dias <= 0 ? "HOY" : "en " + rc.faltan_dias + "d") : "PENDIENTE") + "</small></div>";
      });
      evs.slice(0, 5).forEach(function (e) {
        h += "<div style='padding:8px 10px; border:1px solid var(--borde); border-radius:8px; margin-bottom:8px;'>"
          + "<b>" + esc(e.etiqueta || e.tipo || "Alerta") + "</b> · " + esc(e.fecha || "") + "<br>"
          + "<small style='color:var(--texto-suave);'>" + esc((e.tag ? e.tag + " — " : "") + (e.descripcion || "")) + "</small></div>";
      });
      rets.slice(0, 3).forEach(function (r) {
        h += "<div style='padding:8px 10px; border:1px solid var(--borde); border-radius:8px; margin-bottom:8px;'>"
          + "<b>💊 Retiro: " + esc(r.tag || "") + "</b><br>"
          + "<small style='color:var(--texto-suave);'>" + esc(r.producto || "") + "</small></div>";
      });
      cuerpo.innerHTML = h;
    }).catch(function () {
      if (cuerpo) cuerpo.innerHTML = "<p class='aviso'>⚠️ Sin conexión: no se pudo cargar la agenda.</p>";
    });
  }

  function setupCampana() {
    var camp = document.getElementById("btn-notif");
    if (!camp) return;
    camp.addEventListener("click", function () {
      if ("Notification" in window && Notification.permission === "default") {
        iniciarWebPush(false).catch(function () {});
      }
      abrirPanelCampana();
    });
  }

  function setupHeaderAyuda() {
    var btnAyuda = document.getElementById("btn-ayuda");
    if (!btnAyuda) return;
    btnAyuda.addEventListener("click", function () {
      if (fb) {
        window.location = "/?v=ayuda";
        return;
      }
      irAVista("ayuda");
      var barraFiltros = document.getElementById("barra-filtros");
      if (barraFiltros) barraFiltros.style.display = "none";
      cargar(true);
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
    });
  }

  var VISTAS_PRIMARIAS = ["tablero", "captura", "inventario", "finanzas"];
  var NOMBRES_VISTA = {
    tablero: "Tablero",
    captura: "Registrar",
    inventario: "Inventario",
    finanzas: "Finanzas",
    mapa: "Mapa & GPS",
    manga: "Manga",
    agenda: "Agenda",
    repro: "Repro",
    leche: "Leche",
    sanidad: "Sanidad",
    pasturas: "Pasturas",
    genetica: "Genética",
    ficha: "Ficha",
    gps: "Mapa & GPS",
    usuarios: "Usuarios",
    sistema: "Sistema",
    mercado: "Subastas",
    ayuda: "Ayuda"
  };

  function setupModalMas() {
    var modalMas = document.getElementById("modal-mas-modulos");
    var btnNavMas = document.getElementById("btn-nav-mas");
    var btnCerrarMas = document.getElementById("btn-cerrar-mas");

    function abrirModalMas() {
      if (!modalMas) return;
      modalMas.style.display = "flex";
      qa("#modal-mas-modulos .modulo-item").forEach(function (it) {
        if (it.getAttribute("data-v") === actual) it.classList.add("act");
        else it.classList.remove("act");
      });
    }

    function cerrarModalMas() {
      if (!modalMas) return;
      modalMas.style.display = "none";
    }

    window.__abrirModalMas = abrirModalMas;
    window.__cerrarModalMas = cerrarModalMas;

    if (btnNavMas) {
      btnNavMas.addEventListener("click", function (e) {
        e.stopPropagation();
        abrirModalMas();
      });
    }

    if (btnCerrarMas) {
      btnCerrarMas.addEventListener("click", function (e) {
        e.stopPropagation();
        cerrarModalMas();
      });
    }

    if (modalMas) {
      modalMas.addEventListener("click", function (e) {
        if (e.target === modalMas) cerrarModalMas();
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modalMas && modalMas.style.display === "flex") {
        cerrarModalMas();
      }
    });

    qa("#modal-mas-modulos .modulo-item").forEach(function (item) {
      item.addEventListener("click", function () {
        var v = item.getAttribute("data-v");
        if (!v) return;
        cerrarModalMas();
        irAVista(v);
        cargar();
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
      });
    });

    // El ítem "Deshacer" no navega a una vista (no tiene data-v): al tocarlo
    // cierra el sheet y abre el modal de últimos eventos. Antes era onclick
    // inline, bloqueado por la CSP production script-src 'self'.
    var sheetDeshacer = document.getElementById("sheet-item-deshacer");
    if (sheetDeshacer) {
      sheetDeshacer.addEventListener("click", function () {
        cerrarModalMas();
        if (typeof window.mostrarModalUltimosEventos === "function") {
          window.mostrarModalUltimosEventos();
        }
      });
    }
  }

  function actualizarFabGlobal() {
    var stack = document.getElementById("fab-stack-global");
    var fabReg = document.getElementById("fab-global-registrar");
    var fabBus = document.getElementById("fab-global-buscar");
    if (!stack && !fabReg) return;

    if (fabReg) {
      fabReg.style.display = (actual === "captura") ? "none" : "flex";
    }
    if (fabBus) {
      fabBus.style.display = "flex";
    }
    if (stack) {
      stack.style.display = (actual === "manga") ? "none" : "flex";
    }
  }

  function setupFabGlobal() {
    var fabReg = document.getElementById("fab-global-registrar");
    if (fabReg) {
      fabReg.addEventListener("click", function (e) {
        e.preventDefault();
        vibrarConfirmacion();
        var tagFab = "";
        if (actual === "ficha") {
          tagFab = (window.__ultimaFicha && window.__ultimaFicha.tag) || (q("#f-tag") && q("#f-tag").value.trim()) || "";
        } else {
          var inpTag = document.getElementById("f-tag");
          if (inpTag && inpTag.value.trim()) {
            tagFab = inpTag.value.trim();
          }
        }
        if (tagFab) {
          try { localStorage.setItem("bitacora_ultimo_tag", tagFab); } catch (eFabTag) { /* noop */ }
          window.__capTagPendiente = tagFab;
        }
        irAVista("captura");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eFabScroll) { window.scrollTo(0, 0); }
      });
    }

    var fabBuscar = document.getElementById("fab-global-buscar");
    var modalBuscar = document.getElementById("modal-buscar-ficha-rapida");
    var inputTagRapido = document.getElementById("input-tag-buscar-rapido");
    var inputPotreroRapido = document.getElementById("input-potrero-buscar-rapido");
    var btnFiltrarTablero = document.getElementById("btn-filtrar-tablero-buscar");
    var formBuscarRapido = document.getElementById("form-buscar-ficha-rapida");
    var feedbackBuscar = document.getElementById("buscar-ficha-feedback");
    var btnCerrarBuscar = document.getElementById("btn-cerrar-modal-buscar-ficha");
    var btnCancelarBuscar = document.getElementById("btn-cancelar-buscar-ficha");
    var btnHeaderBuscar = document.getElementById("btn-header-buscar-animal");

    function cerrarModalBuscar() {
      if (modalBuscar) modalBuscar.style.display = "none";
      if (feedbackBuscar) feedbackBuscar.textContent = "";
    }

    function abrirModalBuscar() {
      if (!modalBuscar) return;
      vibrarConfirmacion();
      modalBuscar.style.display = "flex";
      try { cargarListasAutocompletar(); } catch (eDl) {}
      if (inputTagRapido) {
        var tagSugerido = (window.__ultimaFicha && window.__ultimaFicha.tag) || (q("#f-tag") && q("#f-tag").value.trim()) || "";
        inputTagRapido.value = tagSugerido;
        setTimeout(function () {
          inputTagRapido.focus();
          inputTagRapido.select();
        }, 150);
      }
      // El potrero arranca con el filtro vigente del Tablero, si lo hay.
      if (inputPotreroRapido && !inputPotreroRapido.value) {
        var potVigente = (q("#f-potrero") && q("#f-potrero").value.trim()) || "";
        if (potVigente) inputPotreroRapido.value = potVigente;
      }
    }
    // "Ver en Tablero": aplica potrero (y arete, si se escribió) al filtro
    // del Tablero y lo muestra, para no depender de la barra superior.
    function filtrarTableroDesdeModal() {
      var tag = (inputTagRapido && inputTagRapido.value.trim()) || "";
      var pot = (inputPotreroRapido && inputPotreroRapido.value.trim()) || "";
      if (!tag && !pot) {
        if (feedbackBuscar) feedbackBuscar.textContent = "Escribe un arete o un potrero para filtrar.";
        return;
      }
      cerrarModalBuscar();
      vibrarConfirmacion();
      var inpPot = document.getElementById("f-potrero");
      if (inpPot) inpPot.value = pot;
      var inpTag = document.getElementById("f-tag");
      if (inpTag) inpTag.value = tag;
      irAVista("tablero");
      var bf = document.getElementById("barra-filtros");
      if (bf) {
        bf.style.display = "";
        bf.__forzadoVisible = true;
      }
      cargar(true);
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eScrollTab) { window.scrollTo(0, 0); }
    }
    window.abrirModalBuscarFichaRapida = abrirModalBuscar;

    if (fabBuscar) {
      fabBuscar.addEventListener("click", function (e) {
        e.preventDefault();
        abrirModalBuscar();
      });
    }
    if (btnHeaderBuscar) {
      btnHeaderBuscar.addEventListener("click", function (e) {
        e.preventDefault();
        abrirModalBuscar();
      });
    }
    if (btnCerrarBuscar) btnCerrarBuscar.addEventListener("click", cerrarModalBuscar);
    if (btnCancelarBuscar) btnCancelarBuscar.addEventListener("click", cerrarModalBuscar);
    if (modalBuscar) {
      modalBuscar.addEventListener("click", function (e) {
        if (e.target === modalBuscar) cerrarModalBuscar();
      });
    }
    if (btnFiltrarTablero) {
      btnFiltrarTablero.addEventListener("click", function (e) {
        e.preventDefault();
        filtrarTableroDesdeModal();
      });
    }
    if (formBuscarRapido) {
      formBuscarRapido.addEventListener("submit", function (e) {
        e.preventDefault();
        var tag = (inputTagRapido && inputTagRapido.value.trim()) || "";
        if (!tag) {
          // Sin arete, el Enter equivale a filtrar el Tablero.
          filtrarTableroDesdeModal();
          return;
        }
        cerrarModalBuscar();
        vibrarConfirmacion();
        abrirFichaDesdeTag(tag);
      });
    }

    // Atajo global Ctrl+K o / para buscar animal rápidamente desde cualquier pantalla
    if (!window.__tecladoBuscarRegistrado) {
      window.__tecladoBuscarRegistrado = true;
      document.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
          e.preventDefault();
          abrirModalBuscar();
        } else if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement && document.activeElement.tagName)) {
          e.preventDefault();
          abrirModalBuscar();
        } else if (e.key === "Escape" && modalBuscar && modalBuscar.style.display === "flex") {
          cerrarModalBuscar();
        }
      });
    }
  }

  qa("#nav-principal button").forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.id === "btn-nav-mas") {
        if (typeof window.__abrirModalMas === "function") window.__abrirModalMas();
        return;
      }
      var v = b.getAttribute("data-v");
      if (!v) return;
      if (v === "ficha" && actual === "ficha") {
        var inpFicha = q("#f-tag");
        if (inpFicha) inpFicha.value = "";
      }
      irAVista(v);
      cargar();
      if (VISTAS_BADGE.indexOf(actual) !== -1) {
        var span = b.querySelector(".nav-badge");
        if (span) { span.textContent = ""; span.classList.remove("on"); }
      }
    });
  });

  // Cambia de pestaña activa sin recargar
  function irAVista(v) {
    var vistaPrevia = actual;
    if (actual === "mapa" && v !== "mapa") {
      if (_mapaTimerRefresh) {
        clearInterval(_mapaTimerRefresh);
        _mapaTimerRefresh = null;
      }
      if (_mapaWatchGpsId && navigator.geolocation) {
        navigator.geolocation.clearWatch(_mapaWatchGpsId);
        _mapaWatchGpsId = null;
      }
      _mapaMarkerSelf = null;
      _mapaCircleSelf = null;
      _mapaCapaSelf = null;
      if (_mapaInstancia) {
        try { _mapaInstancia.remove(); } catch (e) {}
        _mapaInstancia = null;
      }
    }
    actual = v;
    if (_historialListo && !_navegandoHistorial && v !== vistaPrevia) {
      try { window.history.pushState({ ja: "vista", v: v }, ""); } catch (eHist) {}
    }
    actualizarFabGlobal();
    var navEl = document.getElementById("nav-principal");
    if (navEl) navEl.classList.remove("nav-hidden");
    var chatDockEl = document.getElementById("chat-dock");
    if (chatDockEl) chatDockEl.classList.remove("nav-hidden");
    if (v !== "ficha") {
      actualizarVacaHeader({ esFicha: false });
    }
    qa("#nav-principal button").forEach(function (x) { x.classList.remove("act"); });
    qa("#nav-principal button[data-v]").forEach(function (b) { b.removeAttribute("aria-current"); });
    var destino = qa("#nav-principal button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
    if (destino) { destino.classList.add("act"); if (destino.hasAttribute("data-v")) destino.setAttribute("aria-current", "page"); }

    // Sincronizar botón Más en barra móvil
    var btnMas = document.getElementById("btn-nav-mas");
    var txtMas = document.getElementById("txt-nav-mas");
    if (btnMas) {
      if (VISTAS_PRIMARIAS.indexOf(v) !== -1) {
        btnMas.classList.remove("act");
        if (txtMas) txtMas.textContent = "Más";
      } else {
        btnMas.classList.add("act");
        if (txtMas) txtMas.textContent = NOMBRES_VISTA[v] || "Más";
      }
    }

    // Sincronizar ítem activo en modal de módulos
    qa("#modal-mas-modulos .modulo-item").forEach(function (it) {
      if (it.getAttribute("data-v") === v) { it.classList.add("act"); it.setAttribute("aria-current", "page"); }
      else { it.classList.remove("act"); it.removeAttribute("aria-current"); }
    });
  }
  /* ---------- Botón atrás del celular (historial de pantallas) ----------
     Cada cambio de vista deja una entrada en el historial del navegador, así
     la flecha atrás de Android vuelve a la vista anterior en vez de cerrar
     la app. Antes de cambiar de vista, atrás cierra lo que esté abierto
     encima (modal, menú "Más", visor de fotos, chat) o retrocede un paso de
     Registrar. Desde la vista de inicio avisa y el siguiente atrás sale.
     Pila: [raiz, vista inicial, vista 2, ...]; "raiz" es la entrada de
     guarda que recibe el último atrás. */
  var _historialListo = false;
  var _navegandoHistorial = false;

  function vistaInicio() {
    var rol = (window.__usuarioActual && window.__usuarioActual.rol || "").toUpperCase();
    return rol === "TRABAJADOR" ? "captura" : "tablero";
  }

  function iniciarHistorial() {
    if (_historialListo || !window.history || !window.history.pushState) return;
    if (!document.getElementById("nav-principal")) return;
    try {
      window.history.replaceState({ ja: "raiz" }, "");
      window.history.pushState({ ja: "vista", v: actual }, "");
      _historialListo = true;
    } catch (eIni) {}
  }

  function capaVisible(el) {
    if (!el || !el.isConnected) return false;
    try { return window.getComputedStyle(el).display !== "none"; } catch (eCs) { return false; }
  }

  // Cierra la capa abierta más arriba. Devuelve true si cerró algo.
  function cerrarCapaAbierta() {
    var lb = document.getElementById("lightbox-visor");
    if (lb && lb.isConnected) {
      var lbCerrar = lb.querySelector("#lb-btn-cerrar");
      if (lbCerrar) lbCerrar.click();
      if (lb.isConnected) { lb.remove(); document.body.style.overflow = ""; }
      return true;
    }
    var abiertos = qa(".modal-overlay").filter(function (m) { return m.id !== "chat-dock" && capaVisible(m); });
    if (abiertos.length) {
      var m = abiertos[abiertos.length - 1];
      var cerrar = m.querySelector(".modal-cerrar, [id^='btn-cerrar'], .btn-cerrar, [data-cerrar], [aria-label='Cerrar']");
      if (cerrar) cerrar.click();
      if (capaVisible(m)) m.style.display = "none";
      return true;
    }
    var dock = document.getElementById("chat-dock");
    if (dock && dock.classList.contains("expandido")) {
      var btnCol = document.getElementById("btn-colapsar-chat");
      if (btnCol) btnCol.click();
      else { dock.classList.remove("expandido"); dock.classList.add("colapsado"); }
      return true;
    }
    if (actual === "captura") {
      var paso3 = q(".cap-paso-3.act");
      var paso2 = q(".cap-paso-2.act");
      var btnAtras = paso3 ? document.getElementById("btn-cap-atras3") : (paso2 ? document.getElementById("btn-cap-atras2") : null);
      if (btnAtras) { btnAtras.click(); return true; }
    }
    return false;
  }

  window.addEventListener("popstate", function (e) {
    if (!_historialListo) return;
    var st = e.state || {};
    if (cerrarCapaAbierta()) {
      // El atrás se gastó cerrando la capa: se repone la entrada de la vista actual.
      try { window.history.pushState({ ja: "vista", v: actual }, ""); } catch (eP) {}
      return;
    }
    if (st.ja === "vista" && st.v) {
      if (st.v !== actual) {
        _navegandoHistorial = true;
        try { irAVista(st.v); } finally { _navegandoHistorial = false; }
        cargar();
        try { window.scrollTo(0, 0); } catch (eSc) {}
      }
      return;
    }
    // Entrada de guarda: si no está en el inicio, va al inicio; si ya está,
    // avisa y deja que el siguiente atrás cierre la app.
    var inicio = vistaInicio();
    if (actual !== inicio) {
      _navegandoHistorial = true;
      try { irAVista(inicio); } finally { _navegandoHistorial = false; }
      cargar();
      try { window.history.pushState({ ja: "vista", v: inicio }, ""); } catch (eP2) {}
      try { window.scrollTo(0, 0); } catch (eSc2) {}
      return;
    }
    mostrarToast("Toca atrás otra vez para salir", "verde");
  });

  // Cargar manual (botón o Enter): el tag manda a Ficha y el potrero manda a
  // Tablero (únicas vistas que usan esos campos), sin importar qué pestaña
  // estaba activa antes.
  function cargarManual() {
    var t = (q("#f-tag") && q("#f-tag").value || "").trim();
    var pot = (q("#f-potrero") && q("#f-potrero").value || "").trim();
    if (t && actual !== "ficha") irAVista("ficha");
    else if (!t && pot && actual !== "tablero") irAVista("tablero");
    cargar();
  }
  var btn = document.getElementById("btn-cargar");
  if (btn) btn.addEventListener("click", cargarManual);
  // Enter en los campos de filtro dispara Cargar.
  ["f-potrero", "f-tag"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("keydown", function (e) { if (e.key === "Enter") cargarManual(); });
  });
  // Autocompletar: tecleo en tag/potrero consulta /api/buscar y llena datalist.
  var inpPotrero = document.getElementById("f-potrero");
  var inpTag = document.getElementById("f-tag");
  if (inpTag) {
    inpTag.addEventListener("input", onInputSugerir);
    inpTag.addEventListener("focus", function () { cargarListasAutocompletar(); });
    inpTag.addEventListener("click", function () { cargarListasAutocompletar(); });
  }
  if (inpPotrero) {
    inpPotrero.addEventListener("input", onInputSugerir);
    inpPotrero.addEventListener("focus", function () { cargarListasAutocompletar(); });
    inpPotrero.addEventListener("click", function () { cargarListasAutocompletar(); });
  }
  // Delegación global para inputs con datalist para que siempre estén precargados al enfocar o teclear
  document.addEventListener("focusin", function (e) {
    var list = e.target && e.target.getAttribute && e.target.getAttribute("list");
    if (list === "dl-tags" || list === "dl-potreros") {
      cargarListasAutocompletar();
    } else if (list === "dl-toros") {
      cargarListaToros();
    }
  });
  document.addEventListener("input", function (e) {
    var list = e.target && e.target.getAttribute && e.target.getAttribute("list");
    if (list === "dl-tags" || list === "dl-potreros") {
      onInputSugerir(e);
    }
  });
  cargarListasAutocompletar();
  cargarListaToros();

  /* ---------- Online/offline + polling ---------- */
  var barra = document.getElementById("barra-red");
  function actualizarRed() {
    if (!barra) return;
    if (navigator.onLine === false) barra.classList.add("visible");
    else barra.classList.remove("visible");
  }
  window.addEventListener("online", actualizarRed);
  window.addEventListener("offline", actualizarRed);
  actualizarRed();

  var reloj = document.getElementById("reloj-hora");
  function tick() {
    if (reloj) {
      try {
        var ahora = new Date();
        var fStr = ahora.toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short" });
        if (fStr) {
          fStr = fStr.replace(/^\w/, function (c) { return c.toUpperCase(); }).replace(/\./g, "");
        }
        var hStr = ahora.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
        reloj.innerHTML = "<span class='reloj-fecha'>" + esc(fStr) + "</span> <span class='reloj-sep'>·</span> <span class='reloj-hora'>" + esc(hStr) + "</span>";
        var menuHora = document.getElementById("menu-usuario-hora");
        if (menuHora) menuHora.textContent = fStr + " · " + hStr;
      } catch (e) { /* noop */ }
    }
    actualizarVacaHeader();
    actualizarClimaHeader();
  }
  tick();
  setInterval(function () {
    tick();
    if (document.hidden || navigator.onLine === false || actual !== "tablero") {
      if (!document.hidden) actualizarBadges();
      return;
    }
    cargar(false); // polling en silencio: sin animación ni skeleton, solo en el tablero
    actualizarBadges();
  }, 60000);

