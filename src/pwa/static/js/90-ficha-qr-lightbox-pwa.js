  /* ---------- Página dedicada /ficha/<tag> (destino del QR) ---------- */
  var fb = document.getElementById("ficha");
  function arrancarDesdeUrl() {
    var params = new URLSearchParams(window.location.search);
    var v = params.get("v");
    var pot = params.get("potrero");
    var tag = params.get("tag");
    // Alias: la vista de población se unificó dentro de Inventario.
    if (v === "poblacion") v = "inventario";
    if (v === "ayuda") {
      irAVista("ayuda");
      var barraFiltros = document.getElementById("barra-filtros");
      if (barraFiltros) barraFiltros.style.display = "none";
      cargar(true);
      return;
    }
    if (pot && q("#f-potrero")) q("#f-potrero").value = pot;
    if (tag && q("#f-tag")) q("#f-tag").value = tag;
    if (!v && (pot || tag)) v = pot ? "tablero" : "ficha";
    if (v && qa("#nav-principal button").length) {
      var destino = qa("#nav-principal button").filter(function (b) { return b.getAttribute("data-v") === v; })[0];
      if (destino) {
        irAVista(v);
        cargar();
        return;
      }
    }
    cargar();
  }

  /* ---------- Visor Lightbox de Imágenes (Agrandar y Mover con la Mano) ---------- */
  function mostrarLightbox(src, titulo) {
    if (!src) return;
    var existente = document.getElementById("lightbox-visor");
    if (existente && existente.parentNode) existente.parentNode.removeChild(existente);

    var lb = document.createElement("div");
    lb.id = "lightbox-visor";
    lb.className = "lightbox-overlay";
    lb.setAttribute("role", "dialog");
    lb.setAttribute("aria-label", "Visor de imagen agrandada");

    var tit = titulo || "Fotografía";
    var h = "<div class='lightbox-topbar'>"
      + "<div class='lightbox-titulo'>" + icon("camera", 16) + esc(tit) + "</div>"
      + "<div class='lightbox-acciones'>"
      + "<button type='button' id='lb-btn-zoom-out' class='lightbox-btn' title='Alejar (Zoom -)'>" + icon("search", 13) + "<span>-</span></button>"
      + "<button type='button' id='lb-btn-zoom-in' class='lightbox-btn' title='Acercar (Zoom +)'>" + icon("plus", 13) + "<span>+</span></button>"
      + "<button type='button' id='lb-btn-zoom-toggle' class='lightbox-btn' title='Alternar Zoom'><span id='lb-zoom-text'>Zoom 2x</span></button>"
      + "<a href='" + esc(src) + "' target='_blank' download class='lightbox-btn' title='Descargar / Abrir en pestaña nueva'>" + icon("download", 13) + "<span>Descargar</span></a>"
      + "<button type='button' id='lb-btn-cerrar' class='lightbox-btn lightbox-btn-cerrar' title='Cerrar (Esc)'>" + icon("xmark", 13) + "<span>Cerrar</span></button>"
      + "</div></div>"
      + "<div class='lightbox-img-wrap' id='lb-img-wrap'>"
      + "<img class='lightbox-img' id='lb-img' src='" + esc(src) + "' alt='" + esc(tit) + "' draggable='false'>"
      + "</div>"
      + "<div style='color:rgba(255,255,255,0.75); font-size:11.5px; margin-top:8px; text-align:center; pointer-events:none; user-select:none;'>"
      + icon("hand", 12) + "Arrastra con la mano para mover · " + icon("search", 12) + "Rueda o doble toque para zoom · Esc para salir</div>";

    lb.innerHTML = h;
    document.body.appendChild(lb);
    document.body.style.overflow = "hidden"; // bloquear scroll del fondo

    var wrap = lb.querySelector("#lb-img-wrap");
    var img = lb.querySelector("#lb-img");
    var btnCerrar = lb.querySelector("#lb-btn-cerrar");
    var btnZoomIn = lb.querySelector("#lb-btn-zoom-in");
    var btnZoomOut = lb.querySelector("#lb-btn-zoom-out");
    var btnZoomToggle = lb.querySelector("#lb-btn-zoom-toggle");
    var zoomText = lb.querySelector("#lb-zoom-text");

    var scale = 1.0;
    var panX = 0;
    var panY = 0;
    var isDragging = false;
    var hasMoved = false;
    var startX = 0;
    var startY = 0;
    var pinchStartDist = 0;
    var pinchStartScale = 1.0;
    var lastTapTime = 0;

    function applyTransform(withTransition) {
      if (!img) return;
      if (withTransition) {
        img.style.transition = "transform 0.18s cubic-bezier(0.2, 0.8, 0.2, 1)";
      } else {
        img.style.transition = "none";
      }

      if (scale <= 1.05) {
        scale = 1.0;
        panX = 0;
        panY = 0;
        img.classList.remove("zoomed", "grabbing");
        img.style.cursor = "zoom-in";
        if (zoomText) zoomText.textContent = "Zoom 2x";
      } else {
        img.classList.add("zoomed");
        img.style.cursor = isDragging ? "grabbing" : "grab";
        if (zoomText) zoomText.textContent = Math.round(scale * 100) + "% (Alejar)";

        // Limitar pan según escala y dimensiones del contenedor para no perder la foto fuera de pantalla
        var wrapRect = wrap ? wrap.getBoundingClientRect() : { width: window.innerWidth * 0.9, height: window.innerHeight * 0.8 };
        var maxPanX = Math.max(60, (wrapRect.width * (scale - 1)) / 2 + 150);
        var maxPanY = Math.max(60, (wrapRect.height * (scale - 1)) / 2 + 150);
        if (panX > maxPanX) panX = maxPanX;
        if (panX < -maxPanX) panX = -maxPanX;
        if (panY > maxPanY) panY = maxPanY;
        if (panY < -maxPanY) panY = -maxPanY;
      }

      img.style.transform = "translate3d(" + panX + "px, " + panY + "px, 0) scale(" + scale + ")";
    }

    // Cerrar visor y limpiar listeners de window
    function cerrar() {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      lb.style.opacity = "0";
      setTimeout(function () { if (lb && lb.parentNode) lb.parentNode.removeChild(lb); }, 150);
    }

    function onKey(e) {
      if (e.key === "Escape") cerrar();
      else if (e.key === "+" || e.key === "=") zoomIn();
      else if (e.key === "-" || e.key === "_") zoomOut();
    }
    window.addEventListener("keydown", onKey);

    function zoomIn() {
      scale = Math.min(4.0, (scale < 1.1 ? 2.0 : scale + 0.5));
      applyTransform(true);
    }

    function zoomOut() {
      scale = Math.max(1.0, scale - 0.5);
      applyTransform(true);
    }

    function toggleZoom() {
      if (scale > 1.05) {
        scale = 1.0;
        panX = 0;
        panY = 0;
      } else {
        scale = 2.2;
      }
      applyTransform(true);
    }

    if (btnCerrar) btnCerrar.addEventListener("click", cerrar);
    if (btnZoomIn) btnZoomIn.addEventListener("click", function (e) { e.stopPropagation(); zoomIn(); });
    if (btnZoomOut) btnZoomOut.addEventListener("click", function (e) { e.stopPropagation(); zoomOut(); });
    if (btnZoomToggle) btnZoomToggle.addEventListener("click", function (e) { e.stopPropagation(); toggleZoom(); });

    // ---------- Mouse Dragging con la Mano (Desktop) ----------
    function onMouseDown(e) {
      if (e.button !== 0) return; // Solo clic izquierdo
      e.preventDefault();
      isDragging = true;
      hasMoved = false;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
      img.classList.add("grabbing");
      img.style.cursor = "grabbing";
      img.style.transition = "none";
    }

    function onMouseMove(e) {
      if (!isDragging) return;
      var newPanX = e.clientX - startX;
      var newPanY = e.clientY - startY;
      if (Math.hypot(newPanX - panX, newPanY - panY) > 3) {
        hasMoved = true;
      }
      panX = newPanX;
      panY = newPanY;
      applyTransform(false);
    }

    function onMouseUp() {
      if (!isDragging) return;
      isDragging = false;
      img.classList.remove("grabbing");
      if (scale > 1.0) img.style.cursor = "grab";
      applyTransform(true);
    }

    if (img) {
      img.addEventListener("mousedown", onMouseDown);
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);

    // Clic en la imagen (distingue clic de arrastre con la mano)
    if (img) {
      img.addEventListener("click", function (e) {
        e.stopPropagation();
        if (hasMoved) return; // El usuario estaba arrastrando con la mano
        toggleZoom();
      });
    }

    // Rueda del mouse (desktop) para zoom suave hacia la posición del cursor
    if (wrap) {
      wrap.addEventListener("wheel", function (e) {
        e.preventDefault();
        var delta = e.deltaY < 0 ? 0.3 : -0.3;
        var prevScale = scale;
        scale = Math.min(4.0, Math.max(1.0, scale + delta));
        if (scale !== prevScale && scale > 1.0) {
          var rect = wrap.getBoundingClientRect();
          var ox = e.clientX - (rect.left + rect.width / 2);
          var oy = e.clientY - (rect.top + rect.height / 2);
          panX -= ox * (scale / prevScale - 1) * 0.4;
          panY -= oy * (scale / prevScale - 1) * 0.4;
        }
        applyTransform(true);
      }, { passive: false });
    }

    // ---------- Touch Dragging & Pinch en Pantallas Táctiles (Móvil / Tablet) ----------
    if (wrap) {
      wrap.addEventListener("touchstart", function (e) {
        if (e.touches.length === 1) {
          isDragging = true;
          hasMoved = false;
          startX = e.touches[0].clientX - panX;
          startY = e.touches[0].clientY - panY;
          img.style.transition = "none";
        } else if (e.touches.length === 2) {
          isDragging = false;
          hasMoved = true;
          pinchStartDist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
          pinchStartScale = scale;
        }
      }, { passive: true });

      wrap.addEventListener("touchmove", function (e) {
        if (e.touches.length === 1 && isDragging) {
          e.preventDefault();
          var newPanX = e.touches[0].clientX - startX;
          var newPanY = e.touches[0].clientY - startY;
          if (Math.hypot(newPanX - panX, newPanY - panY) > 4) {
            hasMoved = true;
          }
          panX = newPanX;
          panY = newPanY;
          applyTransform(false);
        } else if (e.touches.length === 2 && pinchStartDist > 0) {
          e.preventDefault();
          hasMoved = true;
          var dist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
          scale = Math.min(4.0, Math.max(1.0, pinchStartScale * (dist / pinchStartDist)));
          applyTransform(false);
        }
      }, { passive: false });

      wrap.addEventListener("touchend", function (e) {
        if (isDragging) {
          isDragging = false;
          applyTransform(true);
        }
        // Doble toque rápido para zoom
        if (!hasMoved && e.touches.length === 0) {
          var now = Date.now();
          if (now - lastTapTime < 300) {
            toggleZoom();
            lastTapTime = 0;
          } else {
            lastTapTime = now;
          }
        }
      }, { passive: true });
    }

    // Clic en el fondo oscuro para cerrar
    lb.addEventListener("click", function (e) {
      if (e.target === lb || e.target.id === "lb-img-wrap") {
        cerrar();
      }
    });

    // Iniciar con escala 1.0 centrada
    applyTransform(false);
  }
  window.mostrarLightbox = mostrarLightbox;

  function setupLightboxVisor() {
    document.addEventListener("click", function (e) {
      var target = e.target;
      if (!target) return;
      var imgEl = null;
      if (target.tagName === "IMG") {
        if (target.classList.contains("zoomable-img") ||
            target.closest(".fotos-wrap") ||
            target.closest(".foto-card") ||
            target.closest(".foto-card-mini") ||
            (target.classList.contains("avatar") && target.closest(".ficha-head")) ||
            target.closest(".grafico-wrap")) {
          imgEl = target;
        }
      } else {
        var card = target.closest(".foto-card") || target.closest(".foto-card-mini") || target.closest(".grafico-wrap");
        if (card) {
          imgEl = card.querySelector("img");
        }
      }

      if (imgEl && imgEl.src) {
        e.preventDefault();
        var titulo = imgEl.alt || imgEl.title || "Imagen";
        var tagAnimal = (window.__ultimaFicha && window.__ultimaFicha.tag) || (document.body.getAttribute("data-tag")) || "";
        if (tagAnimal && titulo.indexOf(tagAnimal) === -1) {
          titulo += " · Animal " + tagAnimal;
        }
        mostrarLightbox(imgEl.src, titulo);
      }
    });
  }

  /* ---------- Instalación de la Aplicación (PWA Standalone) ---------- */
  function setupInstalacionApp() {
    var deferredPrompt = null;
    var btnInstalar = document.getElementById("btn-instalar-app");
    var modalInstalar = document.getElementById("modal-instalar-app");
    var cuerpoGuia = document.getElementById("instalar-cuerpo-guia");
    var btnCerrar = document.getElementById("btn-cerrar-instalar");
    var btnEntendido = document.getElementById("btn-entendido-instalar");

    var esStandalone = window.matchMedia("(display-mode: standalone)").matches 
      || window.navigator.standalone 
      || document.referrer.indexOf("android-app://") !== -1;
    var esIos = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

    function cerrarModalGuia() {
      if (modalInstalar) modalInstalar.style.display = "none";
    }

    if (btnCerrar) btnCerrar.addEventListener("click", cerrarModalGuia);
    if (btnEntendido) btnEntendido.addEventListener("click", cerrarModalGuia);
    if (modalInstalar) {
      modalInstalar.addEventListener("click", function (e) {
        if (e.target === modalInstalar) cerrarModalGuia();
      });
    }

    // Si ya está corriendo como app instalada (standalone), ocultar botón
    if (esStandalone) {
      if (btnInstalar) btnInstalar.style.display = "none";
      return;
    }

    // En iOS o navegadores estándar, mostrar botón de instalación en el header
    if (btnInstalar) {
      btnInstalar.style.display = "inline-flex";
    }

    // Captura de evento de instalación nativa (Chrome, Edge, Brave, Android)
    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
      if (btnInstalar) {
        btnInstalar.style.display = "inline-flex";
      }
    });

    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      if (btnInstalar) btnInstalar.style.display = "none";
    });

    if (btnInstalar) {
      btnInstalar.addEventListener("click", function () {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          deferredPrompt.userChoice.then(function (choice) {
            if (choice && choice.outcome === "accepted") {
              if (btnInstalar) btnInstalar.style.display = "none";
            }
            deferredPrompt = null;
          });
        } else if (esIos) {
          if (cuerpoGuia) {
            cuerpoGuia.innerHTML = 
              "<div class='guia-pasos-box'>" +
                "<p class='guia-intro'>Instala <b>Bitácora JA</b> en tu iPhone o iPad para usarla a pantalla completa y sin conexión:</p>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>1</div>" +
                  "<div class='paso-txt'>Toca el botón <b>Compartir</b> <svg class='svg-icon inline' viewBox='0 0 24 24' width='16' height='16' stroke='currentColor' stroke-width='2' fill='none'><path d='M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8'/><polyline points='16 6 12 2 8 6'/><line x1='12' y1='2' x2='12' y2='15'/></svg> en la barra inferior de Safari.</div>" +
                "</div>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>2</div>" +
                  "<div class='paso-txt'>Desliza la lista de opciones y toca " + icon("plus", 14) + "<b>'Agregar a la pantalla de inicio'</b>.</div>" +
                "</div>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>3</div>" +
                  "<div class='paso-txt'>Toca <b>'Agregar'</b> en la esquina superior derecha. ¡Quedará con el logo oficial en tu inicio!</div>" +
                "</div>" +
              "</div>";
          }
          if (modalInstalar) modalInstalar.style.display = "flex";
        } else {
          if (cuerpoGuia) {
            cuerpoGuia.innerHTML = 
              "<div class='guia-pasos-box'>" +
                "<p class='guia-intro'>Instala <b>Bitácora JA</b> como aplicación nativa en tu dispositivo:</p>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>1</div>" +
                  "<div class='paso-txt'>Toca los <b>tres puntos (⋮)</b> del menú arriba a la derecha en Chrome o Edge.</div>" +
                "</div>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>2</div>" +
                  "<div class='paso-txt'>Selecciona la opción <b>'Instalar aplicación'</b> o <b>'Agregar a la pantalla principal'</b>.</div>" +
                "</div>" +
                "<div class='paso-item'>" +
                  "<div class='paso-num'>3</div>" +
                  "<div class='paso-txt'>Confirma tocando <b>'Instalar'</b>. Se abrirá sola a pantalla completa sin barra de direcciones.</div>" +
                "</div>" +
              "</div>";
          }
          if (modalInstalar) modalInstalar.style.display = "flex";
        }
      });
    }
  }

  // Inicializar visor lightbox para fichas y gráficos en toda la app
  setupLightboxVisor();
  setupInstalacionApp();
  setupVacaHeaderInteractivo();
  setupMenuUsuario();
  setupScrollAutoHideNav();
  window.mostrarModalRectificarTag = mostrarModalRectificarTag;

  if (fb) {
    var tag = document.body.getAttribute("data-tag") || "";
    cargarUsuario().finally(function () {
      abrirFicha(tag, fb, false, false); // QR ya identifica el animal: sin panel de foto
    });
    setupChatModal();
    setupHeaderAyuda();
    setupFabGlobal();
    actualizarFabGlobal();
  } else {
    setupSyncOffline();
    setupChatModal();
    setupVozModal();
    setupModalMas();
    setupFabGlobal();
    actualizarFabGlobal();
    crearBadgesNav();
    setupCampana();
    setupHeaderAyuda();
    actualizarBadges();
    actualizarContadorSync();
    // (P1.4b) Aviso de datos servidos desde la caché del Service Worker. El SW
    // marca con X-SW-Stored-At cada respuesta /api/* que guarda; si una
    // respuesta llega con esa marca (típico sin señal) se muestra la antigüedad
    // y se oculta al llegar una fresca de red.
    function instalarAvisoDatosRancios() {
      if (!window.fetch || window.__avisoRanciosInstalado) return;
      window.__avisoRanciosInstalado = true;
      var fetchOriginal = window.fetch;
      window.fetch = function () {
        var args = arguments;
        return fetchOriginal.apply(window, args).then(function (resp) {
          try {
            if (resp && resp.headers && resp.headers.get) {
              actualizarAvisoRancios(resp.headers.get("X-SW-Stored-At"));
            }
          } catch (e) { /* respuesta opaca o sin headers */ }
          return resp;
        });
      };
    }
    function actualizarAvisoRancios(selloIso) {
      var el = document.getElementById("aviso-datos-rancios");
      if (!selloIso) {
        if (el) el.style.display = "none";
        return;
      }
      var ms = Date.now() - new Date(selloIso).getTime();
      if (!isFinite(ms) || ms < 0) ms = 0;
      var horas = Math.floor(ms / 3600000);
      var texto = horas >= 1
        ? ("datos de hace " + horas + " h")
        : "datos guardados hace unos minutos";
      if (!el) {
        el = document.createElement("div");
        el.id = "aviso-datos-rancios";
        el.setAttribute("role", "status");
        el.style.cssText = "position:fixed; left:0; right:0; bottom:0; z-index:9998; " +
          "background:#8a6d00; color:#fff; font-size:12px; text-align:center; " +
          "padding:6px 10px; box-shadow:0 -1px 4px rgba(0,0,0,0.25);";
        document.body.appendChild(el);
      }
      el.textContent = "Sin conexión: " + texto + ". Algunos datos pueden estar desactualizados.";
      el.style.display = "";
    }
    instalarAvisoDatosRancios();
    // Hook de verificación (no funcional): CDP no emula "offline" en el contexto
    // del Service Worker, así que los scripts de verificación ejercitan la lógica
    // del banner directamente con un sello de tiempo.
    window.__actualizarAvisoRancios = actualizarAvisoRancios;

    fetch("/api/heartbeat", { method: "POST" }).catch(function () {});
    enviarTelemetriaSilenciosa("apertura_app");
    setInterval(function () {
      enviarTelemetriaSilenciosa("latido_periodico");
    }, 180000);
    // Latido de presencia en vivo de usuario (cada 60 segundos con pestaña activa)
    setInterval(function () {
      if (!document.hidden && navigator.onLine) {
        fetch("/api/heartbeat", { method: "POST" }).catch(function () {});
      }
    }, 60000);
    // Refresco del chat de equipo (cada 20s con pestaña activa): más
    // frecuente que el heartbeat porque un canal de avisos pierde utilidad
    // si tarda un minuto en aparecer, sin bajar a segundos para no generar
    // tráfico innecesario sobre SQLite en modo WAL.
    setInterval(function () {
      if (!document.hidden && navigator.onLine && window.__cargarMensajesEquipo) {
        window.__cargarMensajesEquipo();
      }
    }, 20000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && navigator.onLine) {
        fetch("/api/heartbeat", { method: "POST" }).catch(function () {});
        if (window.__cargarMensajesEquipo) window.__cargarMensajesEquipo();
      }
    });
    // Primer refresco de badges y cola offline al reconectar tras estar sin señal.
    window.addEventListener("online", function () {
      actualizarBadges();
      sincronizarColaOffline(false);
      // Al volver la señal se oculta el aviso de datos rancios (llegarán frescos).
      actualizarAvisoRancios(null);
    });
    cargarUsuario().finally(function () {
      arrancarDesdeUrl();
      iniciarHistorial();
      if (window.__cargarMensajesEquipo) window.__cargarMensajesEquipo();
    });
  }
