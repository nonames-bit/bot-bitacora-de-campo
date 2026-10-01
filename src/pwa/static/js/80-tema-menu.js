  /* ---------- Selección de Tema (4 Modos) ---------- */
  var selectTema = document.getElementById("select-tema");

  function sincronizarMenuTemas(modo) {
    var chips = qa("#menu-temas-grid .tema-chip-btn");
    chips.forEach(function (btn) {
      if (btn.getAttribute("data-tema") === (modo || "green")) {
        btn.classList.add("activo");
      } else {
        btn.classList.remove("activo");
      }
    });
  }

  function aplicarTema(modo) {
    if (modo === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else if (modo === "light") document.documentElement.setAttribute("data-theme", "light");
    else if (modo === "sun") document.documentElement.setAttribute("data-theme", "sun");
    else document.documentElement.setAttribute("data-theme", "green");
    try { localStorage.setItem("pwa_tema", modo || "green"); } catch (e) { /* noop */ }
    if (selectTema) selectTema.value = modo || "green";
    sincronizarMenuTemas(modo || "green");
    actualizarVacaHeader();
    actualizarClimaHeader();
  }
  function temaInicial() {
    try { return localStorage.getItem("pwa_tema") || "green"; } catch (e) { return "green"; }
  }
  aplicarTema(temaInicial());
  if (selectTema) {
    selectTema.addEventListener("change", function () {
      aplicarTema(selectTema.value);
    });
  }

  /* ---------- Menú Desplegable de Usuario y Control Rápido ---------- */
  function actualizarDotGlobal() {
    var dot = document.getElementById("header-menu-dot");
    if (!dot) return;
    var camp = document.getElementById("notif-dot");
    var nA = camp && camp.textContent ? parseInt(camp.textContent, 10) || 0 : 0;
    var syncCount = document.getElementById("sync-count");
    var nS = syncCount && syncCount.textContent ? parseInt(syncCount.textContent, 10) || 0 : 0;
    if (nA > 0 || nS > 0 || navigator.onLine === false) {
      dot.style.display = "block";
    } else {
      dot.style.display = "none";
    }
  }

  function actualizarMenuEstadoSync(pendientes) {
    var txt = document.getElementById("menu-sync-estado");
    if (pendientes === undefined) {
      var syncCount = document.getElementById("sync-count");
      pendientes = syncCount && syncCount.textContent ? parseInt(syncCount.textContent, 10) || 0 : 0;
    }
    if (txt) {
      if (pendientes > 0) {
        txt.textContent = pendientes + " evento(s) pendientes de sincronizar";
        txt.style.color = "var(--color-ambar-txt)";
      } else if (navigator.onLine === false) {
        txt.textContent = "Sin conexión (modo local activo)";
        txt.style.color = "var(--color-rojo-txt)";
      } else {
        txt.textContent = "Al día con el servidor";
        txt.style.color = "var(--texto-suave)";
      }
    }
    actualizarDotGlobal();
  }

  function actualizarMenuAvisos(nA) {
    var sub = document.getElementById("menu-notif-sub");
    var badge = document.getElementById("menu-notif-dot");
    if (nA === undefined) {
      var camp = document.getElementById("notif-dot");
      nA = camp && camp.textContent ? parseInt(camp.textContent, 10) || 0 : 0;
    }
    if (sub) {
      if (nA > 0) sub.textContent = nA + " aviso(s) pendientes";
      else sub.textContent = "Sin avisos";
    }
    // Número sobre el ícono de la app instalada (Android/escritorio).
    try {
      if (navigator.setAppBadge) {
        if (nA > 0) navigator.setAppBadge(nA); else navigator.clearAppBadge();
      }
    } catch (e) { /* sin soporte */ }
    if (badge) {
      if (nA > 0) {
        badge.textContent = nA > 99 ? "99+" : String(nA);
        badge.style.display = "inline-block";
        badge.classList.add("on");
      } else {
        badge.textContent = "";
        badge.style.display = "none";
        badge.classList.remove("on");
      }
    }
    actualizarDotGlobal();
  }

  function setupMenuUsuario() {
    var modal = document.getElementById("modal-menu-usuario");
    var btnMarca = document.getElementById("marca-header-btn");
    var btnCerrar = document.getElementById("btn-cerrar-menu-usuario");
    if (!modal || !btnMarca) return;

    /* ---------- Acceso con huella / Face ID (WebAuthn) ---------- */
    function huellaSoportada() {
      return !!window.PublicKeyCredential && window.isSecureContext && !!navigator.credentials;
    }

    function huellaB64ToBuf(s) {
      s = String(s || "").replace(/-/g, "+").replace(/_/g, "/");
      var pad = s.length % 4 ? new Array(5 - (s.length % 4)).join("=") : "";
      var raw = atob(s + pad);
      var buf = new Uint8Array(raw.length);
      for (var i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
      return buf.buffer;
    }

    function huellaBufToB64(buf) {
      var bytes = new Uint8Array(buf);
      var bin = "";
      for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
      return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    }

    function huellaCredCreateJSON(cred) {
      var out;
      if (cred && typeof cred.toJSON === "function") {
        out = cred.toJSON();
      } else {
        var r = cred.response || {};
        out = {
          id: cred.id, rawId: huellaBufToB64(cred.rawId), type: cred.type,
          response: { clientDataJSON: huellaBufToB64(r.clientDataJSON), attestationObject: huellaBufToB64(r.attestationObject) },
          clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {}
        };
      }
      try {
        if (cred.response && typeof cred.response.getTransports === "function") {
          out.transports = cred.response.getTransports();
        }
      } catch (e) {}
      return out;
    }

    function actualizarHuellaMenu() {
      var btnHuella = document.getElementById("menu-btn-huella");
      var bloque = document.getElementById("menu-huella-bloque");
      var lista = document.getElementById("menu-huella-lista");
      var sub = document.getElementById("menu-huella-sub");
      if (!btnHuella || !bloque || !lista) return;
      if (!huellaSoportada()) {
        btnHuella.style.display = "none";
        bloque.style.display = "none";
        return;
      }
      btnHuella.style.display = "flex";
      fetchJSON("/api/webauthn/estado", function (d) {
        var creds = (d && d.credenciales) || [];
        if (sub) sub.textContent = creds.length ? (creds.length + " dispositivo(s)") : "Activar en este equipo";
        bloque.style.display = "block";
        if (!creds.length) {
          lista.innerHTML = "<div class='huella-vacio'>Aún no ha activado la huella en ningún dispositivo.</div>";
          return;
        }
        lista.innerHTML = creds.map(function (c) {
          var nombre = c.nombre_dispositivo || "Dispositivo";
          var uso = c.ultimo_uso ? ("Último uso: " + fechaCorta(c.ultimo_uso)) : "Sin usar todavía";
          return "<div class='huella-item'><div><b>" + esc(nombre) + "</b>"
            + "<div style='font-size:11.5px;color:var(--texto-suave);'>" + esc(uso) + "</div></div>"
            + "<button type='button' class='huella-revocar' data-cred-id='" + esc(c.credencial_id) + "'>Revocar</button></div>";
        }).join("");
        qa("#menu-huella-lista .huella-revocar").forEach(function (b) {
          b.addEventListener("click", function () {
            if (!confirm("¿Revocar este acceso con huella?")) return;
            fetch("/api/webauthn/credenciales/" + encodeURIComponent(b.getAttribute("data-cred-id")), { method: "DELETE" })
              .then(function (r) { return r.json().catch(function () { return {}; }).then(function (dd) { return { ok: r.ok, d: dd }; }); })
              .then(function (res) {
                if (res.ok && res.d && res.d.ok) actualizarHuellaMenu();
                else alert((res.d && res.d.error) || "No se pudo revocar.");
              })
              .catch(function () { alert("No se pudo revocar. Revise su conexión."); });
          });
        });
      });
    }

    function registrarHuellaDispositivo() {
      var btn = document.getElementById("menu-btn-huella");
      if (!huellaSoportada()) {
        alert("Este navegador no permite el acceso con huella. Use su PIN.");
        return;
      }
      if (btn) btn.disabled = true;
      fetch("/api/webauthn/registro/opciones", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (dd) { return { ok: r.ok, d: dd }; }); })
        .then(function (res) {
          if (!res.ok || !res.d || !res.d.opciones) throw new Error((res.d && res.d.error) || "opciones");
          var pk = res.d.opciones;
          pk.challenge = huellaB64ToBuf(pk.challenge);
          if (pk.user && pk.user.id) pk.user.id = huellaB64ToBuf(pk.user.id);
          (pk.excludeCredentials || []).forEach(function (c) { c.id = huellaB64ToBuf(c.id); });
          return navigator.credentials.create({ publicKey: pk });
        })
        .then(function (cred) {
          if (!cred) throw new Error("sin_credencial");
          var nombre = (navigator.userAgent || "Dispositivo").slice(0, 60);
          return fetch("/api/webauthn/registro/verificar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ credencial: huellaCredCreateJSON(cred), nombre_dispositivo: nombre })
          }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (dd) { return { ok: r.ok, d: dd }; }); });
        })
        .then(function (res) {
          if (btn) btn.disabled = false;
          if (res.ok && res.d && res.d.ok) {
            try { localStorage.setItem("ja_huella_preferida", "1"); } catch (e) {}
            actualizarHuellaMenu();
            alert("Huella activada. La próxima vez puede entrar tocando 'Ingresar con huella'.");
          } else {
            alert((res.d && res.d.error) || "No se pudo activar la huella.");
          }
        })
        .catch(function () {
          if (btn) btn.disabled = false;
          alert("No se pudo activar la huella en este dispositivo.");
        });
    }

    function abrirMenu() {
      modal.style.display = "flex";
      var actualTema = temaInicial();
      sincronizarMenuTemas(actualTema);
      // Sincronizar estado de instalación
      var topBtnInstalar = document.getElementById("btn-instalar-app");
      var menuBtnInstalar = document.getElementById("menu-btn-instalar");
      var gridAccesos = modal.querySelector(".menu-grid-accesos");
      if (topBtnInstalar && topBtnInstalar.style.display !== "none") {
        if (menuBtnInstalar) menuBtnInstalar.style.display = "flex";
        if (gridAccesos) gridAccesos.classList.add("has-instalar");
      } else {
        if (menuBtnInstalar) menuBtnInstalar.style.display = "none";
        if (gridAccesos) gridAccesos.classList.remove("has-instalar");
      }
      actualizarMenuEstadoSync();
      actualizarMenuAvisos();
      actualizarHuellaMenu();
    }

    function cerrarMenu() {
      modal.style.display = "none";
    }

    window.abrirMenuUsuario = abrirMenu;
    window.cerrarMenuUsuario = cerrarMenu;

    btnMarca.addEventListener("click", function (e) {
      e.preventDefault();
      abrirMenu();
    });
    btnMarca.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        abrirMenu();
      }
    });

    if (btnCerrar) {
      btnCerrar.addEventListener("click", function () {
        cerrarMenu();
      });
    }

    modal.addEventListener("click", function (e) {
      if (e.target === modal) cerrarMenu();
    });

    // Acción buscar ficha rápida desde menú
    var menuBtnBuscar = document.getElementById("menu-btn-buscar-ficha");
    if (menuBtnBuscar) {
      menuBtnBuscar.addEventListener("click", function () {
        cerrarMenu();
        if (typeof window.abrirModalBuscarFichaRapida === "function") {
          window.abrirModalBuscarFichaRapida();
        } else {
          var modalBuscar = document.getElementById("modal-buscar-ficha-rapida");
          if (modalBuscar) modalBuscar.style.display = "flex";
        }
      });
    }

    // Acción sincronizar desde menú
    var menuBtnSync = document.getElementById("menu-btn-sync");
    if (menuBtnSync) {
      menuBtnSync.addEventListener("click", function () {
        sincronizarColaOffline(true);
      });
    }

    // Acción avisos/notificaciones desde menú
    var menuBtnNotif = document.getElementById("menu-btn-notif");
    if (menuBtnNotif) {
      menuBtnNotif.addEventListener("click", function () {
        cerrarMenu();
        abrirPanelCampana();
      });
    }

    // Acción ayuda desde menú
    var menuBtnAyuda = document.getElementById("menu-btn-ayuda");
    if (menuBtnAyuda) {
      menuBtnAyuda.addEventListener("click", function () {
        cerrarMenu();
        var btnAyuda = document.getElementById("btn-ayuda");
        if (btnAyuda) btnAyuda.click();
      });
    }

    // Acción deshacer / últimos eventos desde menú (antes onclick inline,
    // bloqueado por la CSP production script-src 'self').
    var menuBtnDeshacer = document.getElementById("menu-btn-deshacer");
    if (menuBtnDeshacer) {
      menuBtnDeshacer.addEventListener("click", function () {
        cerrarMenu();
        if (typeof window.mostrarModalUltimosEventos === "function") {
          window.mostrarModalUltimosEventos();
        }
      });
    }

    // Acción instalar desde menú
    var menuBtnInstalar = document.getElementById("menu-btn-instalar");
    if (menuBtnInstalar) {
      menuBtnInstalar.addEventListener("click", function () {
        cerrarMenu();
        var topBtnInstalar = document.getElementById("btn-instalar-app");
        if (topBtnInstalar) topBtnInstalar.click();
      });
    }

    // Acción activar huella / Face ID desde menú
    var menuBtnHuella = document.getElementById("menu-btn-huella");
    if (menuBtnHuella) {
      menuBtnHuella.addEventListener("click", function () {
        registrarHuellaDispositivo();
      });
    }

    // Chips de temas en el menú
    qa("#menu-temas-grid .tema-chip-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tema = btn.getAttribute("data-tema");
        if (tema) {
          aplicarTema(tema);
          sincronizarMenuTemas(tema);
        }
      });
    });
  }

  /* ---------- Auto-ocultar Barra de Navegación Inferior al Hacer Scroll en Móvil ---------- */
  function setupScrollAutoHideNav() {
    var nav = document.getElementById("nav-principal");
    var chatDock = document.getElementById("chat-dock");
    if (!nav) return;

    var lastScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    var ticking = false;

    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        ticking = false;
        // Solo aplica en pantallas móviles donde la barra es fija abajo
        if (window.innerWidth > 640) {
          nav.classList.remove("nav-hidden");
          if (chatDock) chatDock.classList.remove("nav-hidden");
          return;
        }

        var currentScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
        var diff = currentScrollY - lastScrollY;

        // Si estamos cerca de la cabecera (top), siempre visible
        if (currentScrollY <= 45) {
          nav.classList.remove("nav-hidden");
          if (chatDock) chatDock.classList.remove("nav-hidden");
          lastScrollY = currentScrollY;
          return;
        }

        // Si llegamos al final de la página, mostrar barra para que no quede inaccesible
        var docHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
        if (window.innerHeight + currentScrollY >= docHeight - 35) {
          nav.classList.remove("nav-hidden");
          if (chatDock) chatDock.classList.remove("nav-hidden");
          lastScrollY = currentScrollY;
          return;
        }

        // Umbral de scroll para evitar temblores o rebotes elásticos
        if (Math.abs(diff) < 8) return;

        if (diff > 0 && currentScrollY > 60) {
          // Scroll hacia abajo -> ocultar barra y bajar botón de chat
          nav.classList.add("nav-hidden");
          if (chatDock) chatDock.classList.add("nav-hidden");
        } else if (diff < 0) {
          // Scroll hacia arriba -> mostrar barra y reposicionar chat
          nav.classList.remove("nav-hidden");
          if (chatDock) chatDock.classList.remove("nav-hidden");
        }

        lastScrollY = currentScrollY;
      });
    }

    window.addEventListener("scroll", onScroll, { passive: true });

    // Si el usuario toca cerca del borde inferior de la pantalla, revelar la barra de inmediato
    window.addEventListener("touchstart", function (e) {
      if (e.touches && e.touches[0] && e.touches[0].clientY > window.innerHeight - 50) {
        nav.classList.remove("nav-hidden");
        if (chatDock) chatDock.classList.remove("nav-hidden");
      }
    }, { passive: true });

    // Cuando cambie la orientación o tamaño de pantalla
    window.addEventListener("resize", function () {
      if (window.innerWidth > 640) {
        nav.classList.remove("nav-hidden");
        if (chatDock) chatDock.classList.remove("nav-hidden");
      }
    });
  }

  /* Al cerrar sesión, borrar la caché del Service Worker (offline lite)
     antes de navegar a /logout. Sin esto, en un equipo compartido alguien
     podría desconectarse de internet después de que otra persona cerró
     sesión y aún ver los datos de la finca que quedaron guardados
     localmente (el SW cachea /api/* y /media/* para el modo sin señal). */
  qa('a[href="/logout"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      if (!("caches" in window)) return; // navegador sin soporte: deja el link normal
      e.preventDefault();
      caches.keys().then(function (keys) {
        return Promise.all(keys.map(function (k) { return caches.delete(k); }));
      }).catch(function () { /* best-effort */ }).then(function () {
        window.location.href = "/logout";
      });
    });
  });

