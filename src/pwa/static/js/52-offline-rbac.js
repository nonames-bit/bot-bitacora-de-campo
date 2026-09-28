  /* ---------- Cola Offline con IndexedDB (ja_bitacora_offline) ---------- */
  function abrirDB() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) return reject(new Error("IndexedDB no soportado"));
      var req = window.indexedDB.open("ja_bitacora_offline", 1);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains("outbox")) {
          db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
        }
      };
      req.onsuccess = function (e) { resolve(e.target.result); };
      req.onerror = function (e) { reject(e.target.error); };
    });
  }

  function encolarOffline(tipo, payload, fecha) {
    return abrirDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction("outbox", "readwrite");
        var store = tx.objectStore("outbox");
        var ev = {
          tipo: tipo,
          payload: payload || {},
          fecha: fecha || new Date().toISOString().slice(0, 10),
          id_local: "loc_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6),
          creado_en: new Date().toISOString()
        };
        var req = store.add(ev);
        req.onsuccess = function () {
          resolve(ev);
          actualizarContadorSync();
        };
        req.onerror = function (e) { reject(e.target.error); };
      });
    }).catch(function (err) {
      console.warn("Fallo encolar offline:", err);
    });
  }

  function obtenerColaOffline() {
    return abrirDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction("outbox", "readonly");
        var store = tx.objectStore("outbox");
        var req = store.getAll();
        req.onsuccess = function () { resolve(req.result || []); };
        req.onerror = function (e) { reject(e.target.error); };
      });
    }).catch(function () { return []; });
  }

  function eliminarDeColaOffline(ids) {
    if (!ids || !ids.length) return Promise.resolve();
    return abrirDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction("outbox", "readwrite");
        var store = tx.objectStore("outbox");
        ids.forEach(function (id) { store.delete(id); });
        tx.oncomplete = function () {
          resolve();
          actualizarContadorSync();
        };
        tx.onerror = function (e) { reject(e.target.error); };
      });
    });
  }

  function actualizarContadorSync() {
    obtenerColaOffline().then(function (lista) {
      var badge = document.getElementById("sync-count");
      var n = lista.length;
      if (badge) {
        if (n > 0) {
          badge.textContent = n > 99 ? "99+" : String(n);
          badge.style.display = "";
          badge.classList.add("on");
        } else {
          badge.textContent = "0";
          badge.style.display = "none";
          badge.classList.remove("on");
        }
      }
      actualizarMenuEstadoSync(n);
    });
  }

  function sincronizarColaOffline(mostrarAviso) {
    obtenerColaOffline().then(function (lista) {
      if (!lista || !lista.length) {
        if (mostrarAviso) alert("No hay eventos pendientes por sincronizar en la cola local.");
        return;
      }
      if (navigator.onLine === false) {
        if (mostrarAviso) alert("Sin conexión a internet. Los " + lista.length + " eventos se sincronizarán al recuperar la señal.");
        return;
      }
      var btnSync = document.getElementById("btn-sync");
      if (btnSync) btnSync.classList.add("girando");
      var menuBtnSync = document.getElementById("menu-btn-sync");
      if (menuBtnSync) menuBtnSync.classList.add("girando");

      fetch("/api/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventos: lista })
      }).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).then(function (res) {
        if (btnSync) btnSync.classList.remove("girando");
        if (menuBtnSync) menuBtnSync.classList.remove("girando");

        // Solo se borran de la cola local los eventos que el servidor
        // confirmó explícitamente (ids_ok, correlacionado por id_local) --
        // antes se borraba TODA la cola con un simple HTTP 200, aunque un
        // evento individual hubiera fallado (ej. tag inexistente): ese
        // evento desaparecía de la cola sin haberse guardado, una pérdida
        // de datos de campo silenciosa (peor aún en la sincronización
        // automática en segundo plano, sin aviso visible).
        var okSet = {};
        (res.ids_ok || []).forEach(function (idl) { okSet[idl] = true; });
        var idsBorrar = lista.filter(function (x) { return okSet[x.id_local]; })
          .map(function (x) { return x.id; });
        var pendientes = lista.length - idsBorrar.length;
        eliminarDeColaOffline(idsBorrar).then(function () {
          if (mostrarAviso) {
            var msg = "✅ Sincronizados " + (res.procesados || 0) + " eventos con éxito.";
            if (pendientes > 0) msg += "\n⚠️ " + pendientes + " evento(s) no se pudieron guardar y siguen en la cola local.";
            if (res.errores && res.errores.length) {
              msg += "\n⚠️ Avisos: " + res.errores.join("; ");
            }
            alert(msg);
          } else if (pendientes > 0) {
            console.warn("Sincronización en segundo plano: " + pendientes + " evento(s) siguen en cola.", res.errores);
          }
          actualizarBadges();
          if (actual !== "manga" && actual !== "captura") cargar(false);
        });
      }).catch(function (err) {
        if (mostrarAviso) alert("Error al sincronizar con el servidor: " + err.message);
      });
    });
  }

  function setupSyncOffline() {
    var btnSync = document.getElementById("btn-sync");
    if (btnSync) {
      btnSync.addEventListener("click", function () {
        sincronizarColaOffline(true);
      });
    }
  }

  /* ---------- Usuario y Control de Acceso (RBAC) ---------- */
  var usuarioActual = null;
  function cargarUsuario() {
    return fetch("/api/usuario").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (u) {
      usuarioActual = u || {};
      window.__usuarioActual = usuarioActual;
      aplicarRBAC(usuarioActual);
      return usuarioActual;
    }).catch(function () { /* modo seguro */ });
  }

  function aplicarRBAC(u) {
    var badge = document.getElementById("user-badge");
    if (badge && u && u.nombre) {
      var rol = (u.rol || "INVITADO").toUpperCase();
      var nv = rolToNivel(rol);
      var avKey = u.avatar || defaultAvatar(rol);
      badge.innerHTML = renderAvatarBadge(avKey, rol, 20, false)
        + "<span style='margin-left:4px; font-weight:600;'>" + esc(u.nombre) + "</span>"
        + "<span class='chip " + nv.chip + "' style='font-size:10px; padding:1px 6px; margin-left:5px; line-height:1.2;'>" + nv.badge + "</span>";
      badge.style.display = "inline-flex";
    }

    // Actualizar datos del perfil en el menú desplegable de usuario
    var mNombre = document.getElementById("menu-usuario-nombre");
    var mRol = document.getElementById("menu-usuario-rol");
    var mAvatar = document.getElementById("menu-avatar-wrap");
    if (u && u.nombre) {
      if (mNombre) mNombre.textContent = u.nombre;
      if (mRol) {
        var rolTexto = (u.rol || "INVITADO").toUpperCase();
        var rolNv = rolToNivel(rolTexto);
        mRol.className = "chip " + rolNv.chip;
        mRol.textContent = rolNv.badge + " · " + rolTexto;
      }
      if (mAvatar) {
        var rolAv = (u.rol || "INVITADO").toUpperCase();
        var avKeyModal = u.avatar || defaultAvatar(rolAv);
        mAvatar.innerHTML = renderAvatarBadge(avKeyModal, rolAv, 38, false);
      }
    }

    var rol = (u.rol || "").toUpperCase();
    var btnSistema = document.getElementById("btn-nav-sistema");
    var btnUsuarios = document.getElementById("btn-nav-usuarios");
    var btnGps = document.getElementById("btn-nav-gps");
    var btnMapa = document.getElementById("btn-nav-mapa");
    var sheetSistema = document.getElementById("sheet-item-sistema");
    var sheetUsuarios = document.getElementById("sheet-item-usuarios");
    var sheetGps = document.getElementById("sheet-item-gps");
    var sheetMapa = document.getElementById("sheet-item-mapa");
    var sheetDeshacer = document.getElementById("sheet-item-deshacer");

    if (rol === "OWNER") {
      if (btnSistema) btnSistema.style.display = "";
      if (btnUsuarios) btnUsuarios.style.display = "";
      if (btnGps) btnGps.style.display = "none";
      if (btnMapa) btnMapa.style.display = "";
      if (sheetSistema) sheetSistema.style.display = "";
      if (sheetUsuarios) sheetUsuarios.style.display = "";
      if (sheetGps) sheetGps.style.display = "none";
      if (sheetMapa) sheetMapa.style.display = "";
      if (sheetDeshacer) sheetDeshacer.style.display = "";
      qa("#nav-principal button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        // El botón Campo de la barra es exclusivo del mayordomo
        // (oficina entra por el sheet "Modo Campo").
        if (v === "gps" || v === "campo") b.style.display = "none";
        else b.style.display = "";
      });
      qa("#modal-mas-modulos .modulo-item").forEach(function (m) {
        var v = m.getAttribute("data-v");
        if (v === "gps") m.style.display = "none";
        else if (v !== "sistema" && v !== "usuarios") m.style.display = "";
      });
    } else if (rol === "ADMIN" || rol === "ADMINISTRADOR") {
      if (btnSistema) btnSistema.style.display = "none";
      if (btnGps) btnGps.style.display = "none";
      if (btnMapa) btnMapa.style.display = "";
      if (btnUsuarios) btnUsuarios.style.display = "";
      if (sheetSistema) sheetSistema.style.display = "none";
      if (sheetGps) sheetGps.style.display = "none";
      if (sheetMapa) sheetMapa.style.display = "";
      if (sheetUsuarios) sheetUsuarios.style.display = "";
      if (sheetDeshacer) sheetDeshacer.style.display = "none";
      qa("#nav-principal button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        if (v === "sistema" || v === "gps" || v === "campo") b.style.display = "none";
        else b.style.display = "";
      });
      qa("#modal-mas-modulos .modulo-item").forEach(function (m) {
        var v = m.getAttribute("data-v");
        if (v === "sistema" || v === "gps" || m.id === "sheet-item-deshacer") m.style.display = "none";
        else if (v !== "usuarios") m.style.display = "";
      });
    } else if (rol === "TRABAJADOR") {
      if (btnSistema) btnSistema.style.display = "none";
      if (btnUsuarios) btnUsuarios.style.display = "none";
      if (btnGps) btnGps.style.display = "none";
      if (btnMapa) btnMapa.style.display = "none";
      if (sheetSistema) sheetSistema.style.display = "none";
      if (sheetUsuarios) sheetUsuarios.style.display = "none";
      if (sheetGps) sheetGps.style.display = "none";
      if (sheetMapa) sheetMapa.style.display = "none";
      if (sheetDeshacer) sheetDeshacer.style.display = "none";
      if (sheetMapa) sheetMapa.style.display = "none";
      // Modo Campo: el mayordomo entra a 4 botones grandes (Captura,
      // Agenda-hoy, Ficha, GPS) en vez del tablero de oficina. La Agenda
      // es lectura/consulta que ya necesita en el corral. El mapa
      // satelital sigue exclusivo de oficina (ver /api/mapa/datos): el
      // botón GPS del modo campo localiza y guarda la ronda sin mapa.
      var permitidas = ["captura", "manga", "ficha", "campo", "agenda"];
      var btnCampo = document.getElementById("btn-nav-campo");
      if (btnCampo) btnCampo.style.display = "";
      qa("#nav-principal button").forEach(function (b) {
        var v = b.getAttribute("data-v");
        if (!v) return; // e.g. #btn-nav-mas
        if (v === "mapa") {
          b.style.display = "none";
          return;
        }
        if (permitidas.indexOf(v) !== -1) {
          b.style.display = "";
        } else {
          b.style.display = "none";
        }
      });
      qa("#modal-mas-modulos .modulo-item").forEach(function (m) {
        var v = m.getAttribute("data-v");
        if (v === "mapa") {
          m.style.display = "none";
          return;
        }
        if (permitidas.indexOf(v) !== -1) {
          m.style.display = "";
        } else {
          m.style.display = "none";
        }
      });
      if (permitidas.indexOf(actual) === -1 && actual !== "ayuda") {
        irAVista("campo");
        cargar();
      }
    }

    // Ocultar categorías sin módulos disponibles para este rol
    qa("#modal-mas-modulos .modulo-seccion").forEach(function (sec) {
      var items = qa(".modulo-item", sec);
      var visible = items.some(function (it) { return it.style.display !== "none"; });
      sec.style.display = visible ? "" : "none";
    });
  }

