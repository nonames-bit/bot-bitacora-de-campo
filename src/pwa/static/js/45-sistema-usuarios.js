  /* ---------- Sistema & Servidor VPS (Solo OWNER) ---------- */
  function renderSistema(d) {
    var vps = d.vps || {};
    var db = d.db || {};

    var h = "<h3>" + icon("settings", 20) + "Servidor VPS & Sistema Ganadería JA</h3>"
      + "<p class='aviso'>Panel de control ejecutivo y métricas de infraestructura en vivo. Acceso restringido al Propietario (OWNER).</p>";

    var ramTxt = (vps.ram_pct != null && vps.ram_pct !== "") ? vps.ram_pct + "%" : "—";
    var ramSub = (vps.ram_total_mb) ? "RAM (" + (vps.ram_used_mb || 0) + "/" + vps.ram_total_mb + " MB)" : "RAM VPS";
    var ramClase = vps.ram_pct >= 85 ? "alerta" : (vps.ram_pct > 0 ? "ok" : "");

    var diskTxt = (vps.disk_pct != null && vps.disk_pct !== "") ? vps.disk_pct + "%" : "—";
    var diskSub = (vps.disk_total_gb) ? "Disco (" + (vps.disk_used_gb || 0) + "/" + vps.disk_total_gb + " GB)" : "Disco VPS";
    var diskClase = vps.disk_pct >= 85 ? "alerta" : (vps.disk_pct > 0 ? "ok" : "");

    h += "<div class='kpis'>"
      + kpi(ramTxt, ramSub, ramClase)
      + kpi(diskTxt, diskSub, diskClase)
      + kpi((db.tam_mb != null ? db.tam_mb + " MB" : "—"), "Base SQLite")
      + kpiIr(kpi((db.activos != null ? String(db.activos) : "—"), "Hato Activo", "ok"), { vista: "inventario" })
      + (d.en_linea_count !== undefined ? kpiIr(kpi(String(d.en_linea_count), "Usuarios en Línea", d.en_linea_count > 0 ? "ok" : ""), { vista: "usuarios" }) : "")
      + "</div>";

    // 2. Bitácora de Actividad Reciente de los Demás Usuarios
    var actList = d.actividad_reciente || [];
    h += "<div style='background:var(--superficie); border:1px solid var(--borde-fuerte); border-radius:10px; padding:16px; margin:20px 0;'>";
    h += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>";
    h += "<div><h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("clipboard", 16) + "Actividad de Campo & Auditoría de Usuarios</h4>";
    h += "<span style='font-size:11.5px; color:var(--texto-suave);'>Registro en vivo de lo que anotaron mayordomos, administradores y personal de corral</span></div>";
    h += "<div style='display:flex; gap:6px; align-items:center; flex-wrap:wrap;'>";
    h += "<button type='button' class='btn-filtro-act act tema-btn' data-f='todos' style='font-size:11px; padding:3px 8px;'>🌐 Todos</button>";
    h += "<button type='button' class='btn-filtro-act tema-btn' data-f='campo' style='font-size:11px; padding:3px 8px;'>🤠 Campo / Mayordomos</button>";
    h += "<button type='button' class='btn-filtro-act tema-btn' data-f='admin' style='font-size:11px; padding:3px 8px;'>🛡️ Administradores</button>";
    h += "</div></div>";

    if (actList.length) {
      h += "<div class='tabla-scroll' style='max-height:420px; overflow-y:auto;'><table style='width:100%; font-size:12px; border-collapse:collapse;'>";
      h += "<tr style='border-bottom:1px solid var(--borde); text-align:left; color:var(--texto-suave); font-size:11px;'>";
      h += "<th style='padding:6px 8px;'>Usuario / Responsable</th>";
      h += "<th style='padding:6px 8px;'>Evento Realizado</th>";
      h += "<th style='padding:6px 8px; text-align:center;'>Animal</th>";
      h += "<th style='padding:6px 8px;'>Fecha / Hora</th>";
      h += "<th style='padding:6px 8px; text-align:center;'>Canal</th>";
      h += "</tr>";

      actList.forEach(function (ev) {
        var rolCat = (ev.usuario_rol || "TRABAJADOR").toUpperCase();
        var fGrupo = "campo";
        if (rolCat === "OWNER" || rolCat === "ADMIN" || rolCat === "SISTEMA") fGrupo = "admin";

        var badgeRol = rolCat === "OWNER" ? "<span class='chip ambar' style='font-size:9.5px; padding:1px 5px;'>OWNER</span>"
                     : rolCat === "ADMIN" ? "<span class='chip azul' style='font-size:9.5px; padding:1px 5px;'>ADMIN</span>"
                     : rolCat === "SISTEMA" ? "<span class='chip gris' style='font-size:9.5px; padding:1px 5px;'>SISTEMA</span>"
                     : "<span class='chip verde' style='font-size:9.5px; padding:1px 5px;'>CAMPO</span>";

        var icCanal = ev.canal === "Telegram" ? "Telegram" : (ev.canal === "PWA" ? "App" : "Sistema");

        h += "<tr class='fila-act-usr' data-grupo='" + fGrupo + "' style='border-bottom:1px solid var(--borde);'>";
        h += "<td style='padding:7px 8px;'>";
        h += "<div style='display:flex; align-items:center; gap:7px;'>";
        h += renderAvatarBadge(ev.usuario_avatar, ev.usuario_rol, 26, false);
        h += "<div><b>" + esc(ev.usuario_nombre || "Usuario") + "</b> " + badgeRol + "</div>";
        h += "</div></td>";
        h += "<td style='padding:7px 8px;'><span style='font-weight:600; color:var(--texto);'>" + esc(ev.resumen || ev.tabla) + "</span></td>";
        h += "<td style='padding:7px 8px; text-align:center;'>";
        if (ev.tag) {
          h += "<a href='/ficha/" + encodeURIComponent(ev.tag) + "' class='chip azul' style='text-decoration:none; font-weight:600; font-family:var(--font-mono); font-size:11px; padding:2px 6px;'>" + esc(ev.tag) + "</a>";
        } else {
          h += "<span style='color:var(--texto-suave);'>—</span>";
        }
        h += "</td>";
        h += "<td style='padding:7px 8px; color:var(--texto-suave); font-size:11px; white-space:nowrap;'>" + esc(ev.fecha_hora_fmt || ev.fecha || "—") + "</td>";
        h += "<td style='padding:7px 8px; text-align:center;'><span style='font-size:10.5px; color:var(--texto-suave); background:var(--superficie); padding:2px 6px; border-radius:4px; border:1px solid var(--borde);'>" + esc(icCanal) + "</span></td>";
        h += "</tr>";
      });
      h += "</table></div>";
    } else {
      h += "<p style='color:var(--texto-suave); font-size:12px; margin:8px 0;'>No se encontraron eventos recientes registrados en la base de datos.</p>";
    }
    h += "</div>";

    // 3. Usuarios & Presencia en Tiempo Real
    var presList = d.presencias || [];
    if (presList.length) {
      h += "<div style='background:var(--superficie); border:1px solid var(--borde-fuerte); border-radius:10px; padding:16px; margin:20px 0;'>";
      h += "<h4 style='margin:0 0 10px 0; display:flex; align-items:center; gap:6px;'>" + icon("shield", 16) + "Monitoreo de Sesiones y Presencia de Usuarios</h4>";
      h += "<div class='tabla-scroll'><table style='width:100%; font-size:12px; border-collapse:collapse;'>";
      h += "<tr style='border-bottom:1px solid var(--borde); text-align:left; color:var(--texto-suave); font-size:11px;'><th style='padding:5px 8px;'>Usuario</th><th style='padding:5px 8px;'>Rol</th><th style='padding:5px 8px; text-align:center;'>Canal</th><th style='padding:5px 8px;'>Última Actividad</th><th style='padding:5px 8px; text-align:center;'>Estado</th></tr>";
      presList.forEach(function (p) {
        var onCls = p.en_linea ? "chip verde" : "chip gris";
        var onTxt = p.en_linea ? "🟢 En línea" : "⚪ Desconectado";
        h += "<tr style='border-bottom:1px solid var(--borde);'>";
        h += "<td style='padding:6px 8px;'><b>" + esc(p.nombre || ("ID " + p.user_id)) + "</b></td>";
        h += "<td style='padding:6px 8px;'><span style='font-size:11px;'>" + esc(p.rol || "—") + "</span></td>";
        h += "<td style='padding:6px 8px; text-align:center;'><span style='font-size:11px;'>" + esc(p.canal || "—") + "</span></td>";
        h += "<td style='padding:6px 8px; font-size:11px; color:var(--texto-suave);'>" + esc(p.ultima_actividad ? p.ultima_actividad.replace("T", " ") : "—") + "</td>";
        h += "<td style='padding:6px 8px; text-align:center;'><span class='" + onCls + "' style='font-size:10px; padding:2px 6px;'>" + onTxt + "</span></td>";
        h += "</tr>";
      });
      h += "</table></div></div>";
    }

    // 4. Diagnóstico General
    // d.texto viene de formatear_tablero_sistema() (mismo texto que usa el bot de
    // Telegram con parse_mode HTML): trae <b>/<i> intencionales y sus valores
    // dinámicos ya vienen escapados del lado del servidor -- no re-escapar aquí
    // o los tags salen literales en vez de renderizarse.
    h += "<h4>" + icon("grid") + "Diagnóstico General</h4>"
      + "<pre style='background:var(--superficie); color:var(--texto); border:1px solid var(--borde-fuerte); padding:12px; border-radius:8px; font-size:12px; white-space:pre-wrap; overflow-x:auto; line-height:1.4;'>"
      + (d.texto || "Sin diagnóstico disponible.") + "</pre>";

    // 5. Visor de Logs con selector de canal (Todos, Telegram, PWA)
    h += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-top:20px;'>"
      + "<h4>" + icon("clipboard", 16) + "Visor de Logs en Vivo</h4>"
      + "<div style='display:flex; gap:6px; align-items:center; flex-wrap:wrap;'>"
      + "<button type='button' class='btn-canal-log act tema-btn' data-canal='todos' style='font-size:11.5px; padding:4px 9px;'>🌐 Todos</button>"
      + "<button type='button' class='btn-canal-log tema-btn' data-canal='telegram' style='font-size:11.5px; padding:4px 9px;'>🤖 Telegram</button>"
      + "<button type='button' class='btn-canal-log tema-btn' data-canal='pwa' style='font-size:11.5px; padding:4px 9px;'>🐮 PWA Web</button>"
      + "<button type='button' id='btn-refrescar-logs' class='tema-btn' style='font-size:11.5px; padding:4px 10px; margin-left:6px;'>" + icon("refresh", 13) + "Refrescar</button>"
      + "</div></div>"
      + "<pre id='visor-logs' style='background:#121212; color:#39FF14; padding:14px; border-radius:8px; font-family:var(--font-mono); font-size:11.5px; max-height:380px; overflow-y:auto; line-height:1.45; white-space:pre-wrap; word-break:break-all; border:1px solid rgba(255,255,255,0.1);'>Cargando logs del servidor...</pre>";

    return h;
  }

  function bindSistema() {
    var _canalLogsActual = "todos";

    // Filtros de actividad de usuarios
    qa(".btn-filtro-act").forEach(function (b) {
      b.addEventListener("click", function () {
        var f = b.getAttribute("data-f");
        qa(".btn-filtro-act").forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        qa(".fila-act-usr").forEach(function (row) {
          var rG = row.getAttribute("data-grupo") || "";
          if (f === "todos" || rG === f) {
            row.style.display = "";
          } else {
            row.style.display = "none";
          }
        });
      });
    });

    function cargarLogs(canal) {
      if (canal) _canalLogsActual = canal;
      var visor = document.getElementById("visor-logs");
      if (!visor) return;
      visor.textContent = "Cargando logs [" + _canalLogsActual + "]...";

      qa(".btn-canal-log").forEach(function (b) {
        if (b.getAttribute("data-canal") === _canalLogsActual) b.classList.add("act");
        else b.classList.remove("act");
      });

      fetch("/api/logs?canal=" + encodeURIComponent(_canalLogsActual) + "&n=100")
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.logs && d.logs.length) {
            visor.textContent = d.logs.join("\n");
            visor.scrollTop = visor.scrollHeight;
          } else {
            visor.textContent = "Sin logs registrados recientemente para este canal.";
          }
        }).catch(function (err) {
          visor.textContent = "Error al obtener logs: " + err.message;
        });
    }

    cargarLogs(_canalLogsActual);

    var btnRef = document.getElementById("btn-refrescar-logs");
    if (btnRef) btnRef.addEventListener("click", function () { cargarLogs(_canalLogsActual); });

    qa(".btn-canal-log").forEach(function (b) {
      b.addEventListener("click", function () {
        cargarLogs(b.getAttribute("data-canal"));
      });
    });
  }

  /* ---------- Sistema de Avatares & Niveles (Level 1, 2, 3) ---------- */
  var AVATARES = {
    patron: { key: "patron", label: "Patrón / Dueño", ic: "crown", color: "#d97706", bg: "rgba(217,119,6,0.14)" },
    admin: { key: "admin", label: "Administrador", ic: "shieldPlus", color: "#2563eb", bg: "rgba(37,99,235,0.14)" },
    vaquero: { key: "vaquero", label: "Vaquero / Campo", ic: "cowboy", color: "#16a34a", bg: "rgba(22,163,74,0.14)" },
    veterinaria: { key: "veterinaria", label: "Veterinaria", ic: "stethoscope", color: "#9333ea", bg: "rgba(147,51,234,0.14)" },
    pasturas: { key: "pasturas", label: "Pasturas / Forraje", ic: "grass", color: "#059669", bg: "rgba(5,150,105,0.14)" },
    tractor: { key: "tractor", label: "Maquinaria / Tractor", ic: "tractor", color: "#ea580c", bg: "rgba(234,88,12,0.14)" }
  };

  function defaultAvatar(rol) {
    var r = (rol || "").toUpperCase();
    if (r === "OWNER") return "patron";
    if (r === "ADMIN" || r === "ADMINISTRADOR") return "admin";
    return "vaquero";
  }

  function rolToNivel(rol) {
    var r = (rol || "").toUpperCase();
    if (r === "OWNER") return { lvl: 1, txt: "Level 1 (OWNER)", badge: "L1", color: "#d97706", chip: "ambar" };
    if (r === "ADMIN" || r === "ADMINISTRADOR") return { lvl: 2, txt: "Level 2 (ADMIN)", badge: "L2", color: "#2563eb", chip: "azul" };
    return { lvl: 3, txt: "Level 3 (TRABAJADOR)", badge: "L3", color: "#16a34a", chip: "verde" };
  }

  function renderAvatarBadge(avKey, rol, size, showLvl) {
    size = size || 38;
    var av = AVATARES[avKey] || AVATARES[defaultAvatar(rol)] || AVATARES.vaquero;
    var nv = rolToNivel(rol);
    var icSize = Math.max(12, Math.round(size * 0.52));
    var h = "<div class='avatar-box' style='width:" + size + "px; height:" + size + "px; background:" + av.bg + "; color:" + av.color + "; border-color:" + av.color + ";'>";
    h += icon(av.ic, icSize);
    if (showLvl !== false) {
      h += "<span class='avatar-lvl-mini' style='background:" + nv.color + ";'>" + nv.lvl + "</span>";
    }
    h += "</div>";
    return h;
  }

  /* ---------- Gestión de Usuarios & Accesos (Niveles 1, 2, 3) ---------- */
  function renderUsuarios(d) {
    var miRol = (d && d.mi_rol || "ADMIN").toUpperCase();
    var usuarios = (d && d.usuarios) || [];

    var h = "<h3>" + icon("users") + "Gestión de Personal & Accesos (Niveles 1, 2, 3)</h3>"
      + "<p class='aviso'>Control de acceso basado en roles por niveles. Define el nombre, nivel de jerarquía, PIN de acceso de 4 dígitos, ID local secuencial, ID de Telegram y foto/avatar representativo.</p>";

    // Tarjeta Monitor en Vivo (Exclusivo OWNER)
    if (miRol === "OWNER") {
      var onlineUsers = usuarios.filter(function (u) {
        return u.online_info && u.online_info.en_linea;
      });
      var enLineaCount = onlineUsers.length;
      var nombresOnline = onlineUsers.map(function (u) {
        var c = u.online_info && u.online_info.canal ? " (" + u.online_info.canal + ")" : "";
        return (u.nombre || "Usuario") + c;
      }).join(", ");
      h += "<div class='card card-banner'>"
        + "<div>"
        + "<div style='display:flex; align-items:center; gap:8px;'>"
        + "<span style='display:inline-block; width:10px; height:10px; border-radius:50%; background:" + (enLineaCount > 0 ? "#16a34a" : "#9ca3af") + "; box-shadow:" + (enLineaCount > 0 ? "0 0 8px #16a34a" : "none") + ";'></span>"
        + "<b style='font-size:14.5px;'>Monitor de Conexión en Vivo (Exclusivo OWNER)</b>"
        + "</div>"
        + "<div style='font-size:12.5px; color:var(--texto-suave); margin-top:3px;'>"
        + (enLineaCount === 1 ? "<b>1 usuario en línea ahora</b>" : "<b>" + enLineaCount + " usuarios en línea ahora</b>")
        + (enLineaCount > 0 ? " — <span style='color:var(--color-verde-txt, #16a34a); font-weight:600;'>" + esc(nombresOnline) + "</span>" : "")
        + " · Monitoreo confidencial de presencia por Web PWA y Telegram Bot."
        + "</div>"
        + "</div>"
        + "<div>"
        + "<button type='button' id='btn-refrescar-usuarios' class='tema-btn' style='font-size:12px; padding:6px 14px;'>" + icon("refresh", 13) + " Actualizar Estados</button>"
        + "</div>"
        + "</div>";
    }

    // Tarjeta 1: Formulario Agregar / Modificar Usuario
    h += "<div class='card' style='padding:18px; margin-bottom:16px;'>"
      + "<h4>" + icon("pin") + "Crear o Modificar Usuario</h4>"
      + "<form id='form-usuario' style='display:flex; flex-direction:column; gap:14px; margin-top:12px;'>"
      + "<input type='hidden' id='usr-edit-id' value=''>"
      + "<input type='hidden' id='usr-avatar-val' value='vaquero'>"

      // Fila 1: Nombre con máximo espacio horizontal
      + "<div>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>Nombre Completo del Usuario / Trabajador:</label>"
      + "<input id='usr-nombre' placeholder='ej. Don José (Propietario) o Carlos Gómez (Mayordomo)' required style='width:100%; box-sizing:border-box; padding:11px 14px; font-size:15px; border-radius:8px; border:1px solid var(--borde-fuerte);'>"
      + "</div>"

      // Fila 2: Nivel (Rol) y PIN de 4 dígitos
      + "<div style='display:flex; gap:12px; flex-wrap:wrap;'>"
      + "<div style='flex:1.2; min-width:220px;'>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>Nivel de Acceso (Jerarquía):</label>"
      + "<select id='usr-rol' style='width:100%; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-weight:600;'>"
      + "<option value='TRABAJADOR'>Level 3 · TRABAJADOR (Campo: Manga, Captura, Ficha)</option>"
      + "<option value='ADMIN'>Level 2 · ADMIN (Gestión, Tableros, Retiros, Reportes, Usuarios)</option>";
    if (miRol === "OWNER") {
      h += "<option value='OWNER'>Level 1 · OWNER (Dueño / Acceso Total + GPS Rutas + Servidor)</option>";
    }
    h += "</select></div>"
      + "<div style='flex:1; min-width:200px;'>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>PIN de 4 Dígitos (Acceso Celular/PC):</label>"
      + "<div style='display:flex; gap:6px;'>"
      + "<input id='usr-pin' type='text' maxlength='4' pattern='\\d{4}' placeholder='ej. 4521' required style='flex:1; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-family:var(--font-mono); font-size:17px; font-weight:bold; letter-spacing:2px; text-align:center;'>"
      + "<button type='button' id='btn-gen-pin' class='tema-btn' style='font-size:12px; padding:0 12px; white-space:nowrap;'>" + icon("refresh", 13) + " Generar PIN</button>"
      + "</div></div>"
      + "</div>"

      // Fila 3: ID Local e ID Telegram lado a lado
      + "<div style='display:flex; gap:12px; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:180px;'>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>ID Local Sistema:</label>"
      + "<input id='usr-uid' type='number' placeholder='Automático (#1, #2...)' style='width:100%; box-sizing:border-box; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-family:var(--font-mono); background:var(--superficie);'>"
      + "<small style='color:var(--texto-suave); font-size:11px; display:block; margin-top:3px;'>Identificador secuencial interno de la finca.</small>"
      + "</div>"
      + "<div style='flex:1; min-width:180px;'>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>ID Telegram (idtelegram - Opcional):</label>"
      + "<input id='usr-telegram-id' type='number' placeholder='ej. 6123051140' style='width:100%; box-sizing:border-box; padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-family:var(--font-mono);'>"
      + "<small style='color:var(--texto-suave); font-size:11px; display:block; margin-top:3px;'>Identificador de Telegram para autorizar el bot.</small>"
      + "</div>"
      + "</div>"

      // Fila 4: Selector de Foto / Avatar Temático
      + "<div>"
      + "<label style='font-size:12px; font-weight:700; display:block; margin-bottom:4px;'>Foto / Avatar de Usuario (Estilo Ganadería JA):</label>"
      + "<div id='picker-avatares' class='avatar-picker'>";

    Object.keys(AVATARES).forEach(function (k) {
      var av = AVATARES[k];
      var esActivo = k === "vaquero" ? " act" : "";
      h += "<div class='avatar-pick-item" + esActivo + "' data-av='" + k + "'>"
        + renderAvatarBadge(k, "TRABAJADOR", 38, false)
        + "<span>" + esc(av.label) + "</span>"
        + "</div>";
    });

    h += "</div>"
      + "</div>"

      // Botones de acción
      + "<div style='display:flex; gap:10px; align-items:center; margin-top:6px;'>"
      + "<button type='submit' id='btn-guardar-usr' class='btn-guardar-manga' style='max-width:240px;'>" + icon("save", 15) + " Guardar Usuario</button>"
      + "<button type='button' id='btn-cancelar-edit-usr' class='tema-btn' style='display:none; padding:10px 16px;'>Cancelar Edición</button>"
      + "</div>"
      + "</form>"
      + "<div id='usr-feedback' role='status' aria-live='polite' style='margin-top:12px;'></div>"
      + "</div>";

    // Tarjeta 2: Tabla de Usuarios Existentes
    h += "<div class='card' style='padding:16px;'>"
      + "<h4>" + icon("users") + "Personal Registrado (" + usuarios.length + ")</h4>";

    if (!usuarios.length) {
      h += vacio("No hay usuarios registrados.");
    } else {
      h += "<div class='tabla-scroll'><table>"
        + "<tr>"
        + "<th>Usuario / Foto</th>"
        + "<th>Nivel de Acceso</th>"
        + (miRol === "OWNER" ? "<th>Conexión en Vivo</th>" : "")
        + "<th>ID Local</th>"
        + "<th>ID Telegram</th>"
        + "<th>PIN</th>"
        + "<th>Acciones</th>"
        + "</tr>";

      usuarios.forEach(function (u) {
        var rolU = String(u.rol || "").toUpperCase();
        var nv = rolToNivel(rolU);
        var esOwnerTarget = rolU === "OWNER";
        var puedeEditar = miRol === "OWNER" || !esOwnerTarget;
        var avKey = u.avatar || defaultAvatar(rolU);

        h += "<tr>"
          + "<td>"
          + "<div style='display:flex; align-items:center; gap:10px;'>"
          + renderAvatarBadge(avKey, rolU, 36, true)
          + "<div><b style='font-size:13.5px;'>" + esc(u.nombre || "Sin nombre") + "</b></div>"
          + "</div>"
          + "</td>"
          + "<td><span class='chip " + nv.chip + "' style='font-weight:700;'>" + nv.badge + " · " + esc(rolU) + "</span></td>";

        if (miRol === "OWNER") {
          var oi = u.online_info || {};
          var chipClase = "gris";
          var dotColor = "#9ca3af";
          var estadoLabel = "Desconectado";
          if (oi.estado === "online") {
            chipClase = "verde";
            dotColor = "#16a34a";
            estadoLabel = "En línea";
          } else if (oi.estado === "reciente") {
            chipClase = "ambar";
            dotColor = "#d97706";
            estadoLabel = "Reciente";
          }
          var canalBadge = oi.canal ? (" (" + esc(oi.canal) + ")") : "";
          var detalleTxt = oi.hace_texto ? esc(oi.hace_texto) : "Nunca";

          h += "<td>"
            + "<div style='display:flex; flex-direction:column; gap:3px;'>"
            + "<span class='chip " + chipClase + "' style='font-size:11px; font-weight:700; display:inline-flex; align-items:center; gap:5px; width:fit-content;'>"
            + "<span style='width:7px; height:7px; border-radius:50%; background:" + dotColor + "; display:inline-block;'></span>"
            + estadoLabel + canalBadge
            + "</span>"
            + "<small style='font-size:11px; color:var(--texto-suave);'>" + detalleTxt + (oi.ip ? " · <span style='font-family:var(--font-mono); font-size:10px;'>" + esc(oi.ip) + "</span>" : "") + "</small>"
            + "</div>"
            + "</td>";
        }

        h += "<td><span style='font-family:var(--font-mono); font-weight:700; font-size:13px; color:var(--texto);'>#" + esc(u.user_id) + "</span></td>"
          + "<td>" + (u.telegram_id ? "<code style='background:var(--superficie); padding:2px 6px; border-radius:4px; font-size:12px; font-family:var(--font-mono);'>" + esc(u.telegram_id) + "</code>" : "<span style='color:var(--texto-suave); font-size:12px;'>—</span>") + "</td>"
          + "<td><code style='background:var(--superficie); padding:3px 8px; border-radius:4px; border:1px solid var(--borde-fuerte); font-size:14px; font-weight:bold; letter-spacing:1px;'>" + esc(u.pin || "—") + "</code></td>"
          + "<td>";

        if (puedeEditar) {
          h += "<button type='button' class='btn-editar-usr tema-btn' data-uid='" + esc(u.user_id) + "' data-nom='" + esc(u.nombre) + "' data-rol='" + esc(rolU) + "' data-pin='" + esc(u.pin || "") + "' data-tgid='" + esc(u.telegram_id || "") + "' data-avatar='" + esc(avKey) + "' style='font-size:11px; padding:4px 9px; margin-right:6px;'>" + icon("pin", 12) + " Editar</button>";
          var numOwners = usuarios.filter(function (x) { return String(x.rol || "").toUpperCase() === "OWNER"; }).length;
          var bloquearBorrar = esOwnerTarget && numOwners <= 1;
          if (!bloquearBorrar && (miRol === "OWNER" || rolU === "TRABAJADOR")) {
            h += "<button type='button' class='btn-borrar-usr tema-btn' data-uid='" + esc(u.user_id) + "' data-nom='" + esc(u.nombre) + "' style='font-size:11px; padding:4px 9px; color:var(--color-rojo-txt);'>" + icon("xmark", 12) + " Eliminar</button>";
          }
        } else {
          h += "<span style='color:var(--texto-suave); font-size:11px;'>Protegido</span>";
        }

        h += "</td></tr>";
      });
      h += "</table></div>";
    }
    h += "</div>";

    // Tarjeta: Credenciales de huella / Face ID (OWNER/ADMIN)
    if (miRol === "OWNER" || miRol === "ADMIN") {
      h += "<div class='card' style='padding:18px; margin-bottom:16px;'>"
        + "<h4>" + icon("shieldPlus", 16) + "Acceso con huella / Face ID</h4>"
        + "<p class='aviso' style='margin-top:6px;'>Solo se guarda la clave pública de cada dispositivo; la huella nunca sale del teléfono. "
        + "Cada usuario activa su huella desde el menú de perfil; aquí se pueden revocar todas las credenciales.</p>"
        + "<div id='usr-huella-lista'><small style='color:var(--texto-suave);'>Cargando…</small></div>"
        + "</div>";
    }

    return h;
  }

  function bindUsuarios(d) {
    var form = document.getElementById("form-usuario");
    var feed = document.getElementById("usr-feedback");
    var btnGenPin = document.getElementById("btn-gen-pin");
    var pinInp = document.getElementById("usr-pin");
    var editIdInp = document.getElementById("usr-edit-id");
    var avInput = document.getElementById("usr-avatar-val");
    var nomInp = document.getElementById("usr-nombre");
    var rolSel = document.getElementById("usr-rol");
    var uidInp = document.getElementById("usr-uid");
    var tgIdInp = document.getElementById("usr-telegram-id");
    var btnCancelar = document.getElementById("btn-cancelar-edit-usr");
    var btnRefrescarUsr = document.getElementById("btn-refrescar-usuarios");

    if (btnRefrescarUsr) {
      btnRefrescarUsr.addEventListener("click", function () {
        btnRefrescarUsr.disabled = true;
        fetch("/api/heartbeat", { method: "POST" })
          .catch(function () {})
          .finally(function () {
            cargar(true);
          });
      });
    }

    function cargarCredencialesHuellaAdmin() {
      var cont = document.getElementById("usr-huella-lista");
      if (!cont) return;
      fetchJSON("/api/webauthn/credenciales/todas", function (d) {
        var creds = (d && d.credenciales) || [];
        if (!creds.length) {
          cont.innerHTML = "<small style='color:var(--texto-suave);'>Sin credenciales de huella registradas.</small>";
          return;
        }
        cont.innerHTML = creds.map(function (c) {
          var quien = c.nombre_usuario || ((c.user_id === null || c.user_id === undefined) ? "Propietario (clave maestra)" : ("Usuario #" + c.user_id));
          var uso = c.ultimo_uso ? ("Último uso: " + fechaCorta(c.ultimo_uso)) : "Sin usar todavía";
          return "<div class='huella-item'><div><b>" + esc(quien) + "</b> · " + esc(c.nombre_dispositivo || "Dispositivo")
            + "<div style='font-size:11.5px;color:var(--texto-suave);'>" + esc(uso) + "</div></div>"
            + "<button type='button' class='huella-revocar' data-cred-id='" + esc(c.credencial_id) + "'>Revocar</button></div>";
        }).join("");
        qa("#usr-huella-lista .huella-revocar").forEach(function (b) {
          b.addEventListener("click", function () {
            if (!confirm("¿Revocar este acceso con huella?")) return;
            fetch("/api/webauthn/credenciales/" + encodeURIComponent(b.getAttribute("data-cred-id")), { method: "DELETE" })
              .then(function (r) { return r.json().catch(function () { return {}; }).then(function (dd) { return { ok: r.ok, d: dd }; }); })
              .then(function (res) {
                if (res.ok && res.d && res.d.ok) cargarCredencialesHuellaAdmin();
                else alert((res.d && res.d.error) || "No se pudo revocar.");
              })
              .catch(function () { alert("No se pudo revocar. Revise su conexión."); });
          });
        });
      });
    }
    cargarCredencialesHuellaAdmin();

    function seleccionarAvatar(avKey) {
      if (!avKey) avKey = "vaquero";
      if (avInput) avInput.value = avKey;
      qa(".avatar-pick-item").forEach(function (el) {
        if (el.getAttribute("data-av") === avKey) el.classList.add("act");
        else el.classList.remove("act");
      });
    }

    qa(".avatar-pick-item").forEach(function (item) {
      item.addEventListener("click", function () {
        var avKey = item.getAttribute("data-av");
        seleccionarAvatar(avKey);
      });
    });

    if (rolSel) {
      rolSel.addEventListener("change", function () {
        if (!editIdInp.value) {
          seleccionarAvatar(defaultAvatar(rolSel.value));
        }
      });
    }

    if (btnGenPin && pinInp) {
      btnGenPin.addEventListener("click", function () {
        var randomPin = String(Math.floor(1000 + Math.random() * 9000));
        pinInp.value = randomPin;
      });
    }

    if (btnCancelar) {
      btnCancelar.addEventListener("click", function () {
        editIdInp.value = "";
        nomInp.value = "";
        pinInp.value = "";
        uidInp.value = "";
        uidInp.disabled = false;
        if (tgIdInp) tgIdInp.value = "";
        seleccionarAvatar(defaultAvatar(rolSel ? rolSel.value : "TRABAJADOR"));
        btnCancelar.style.display = "none";
        var btnGuardar = document.getElementById("btn-guardar-usr");
        if (btnGuardar) btnGuardar.innerHTML = icon("save", 15) + " Guardar Usuario";
      });
    }

    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var nombre = (nomInp.value || "").trim();
        var rol = rolSel.value;
        var pin = (pinInp.value || "").trim();
        var uidVal = editIdInp.value || (uidInp.value || "").trim();
        var tgIdVal = (tgIdInp && tgIdInp.value || "").trim();
        var avatar = avInput ? avInput.value : defaultAvatar(rol);

        if (!/^\d{4}$/.test(pin)) {
          if (feed) feed.innerHTML = "<div class='chip rojo'>El PIN debe ser de 4 dígitos numéricos (ej. 4521).</div>";
          return;
        }

        var payload = { nombre: nombre, rol: rol, pin: pin, avatar: avatar };
        if (editIdInp.value) {
          payload.user_id = parseInt(editIdInp.value, 10);
          payload.telegram_id = tgIdVal ? parseInt(tgIdVal, 10) : null;
        } else {
          if (uidVal) payload.user_id = parseInt(uidVal, 10);
          if (tgIdVal) payload.telegram_id = parseInt(tgIdVal, 10);
        }

        if (feed) feed.innerHTML = "<div class='aviso'>Guardando usuario...</div>";

        fetch("/api/usuarios", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              if (feed) feed.innerHTML = "<div class='chip verde'>" + esc(res.mensaje || "Usuario guardado con éxito.") + "</div>";
              form.reset();
              editIdInp.value = "";
              uidInp.disabled = false;
              if (tgIdInp) tgIdInp.value = "";
              seleccionarAvatar(defaultAvatar(rolSel.value));
              if (btnCancelar) btnCancelar.style.display = "none";
              setTimeout(function () { cargar(false); }, 700);
            } else {
              if (feed) feed.innerHTML = "<div class='chip rojo'>❌ " + esc(res.error || "No se pudo guardar") + "</div>";
            }
          }).catch(function (err) {
            if (feed) feed.innerHTML = "<div class='chip rojo'>❌ Error de conexión: " + esc(err.message) + "</div>";
          });
      });
    }

    // Botones de editar usuario
    qa(".btn-editar-usr").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var uid = btn.getAttribute("data-uid");
        var nom = btn.getAttribute("data-nom");
        var rol = btn.getAttribute("data-rol");
        var pin = btn.getAttribute("data-pin");
        var tgid = btn.getAttribute("data-tgid");
        var av = btn.getAttribute("data-avatar") || defaultAvatar(rol);

        editIdInp.value = uid;
        nomInp.value = nom;
        rolSel.value = rol;
        // El listado enmascara el PIN como "····": nunca se rellena, el
        // admin debe digitar uno nuevo (el backend valida 4 dígitos).
        pinInp.value = (pin && pin !== "****" && pin !== "····") ? pin : "";
        uidInp.value = uid;
        uidInp.disabled = true;
        if (tgIdInp) tgIdInp.value = tgid || "";
        seleccionarAvatar(av);
        if (btnCancelar) btnCancelar.style.display = "";
        var btnGuardar = document.getElementById("btn-guardar-usr");
        if (btnGuardar) btnGuardar.innerHTML = icon("save", 15) + " Actualizar Usuario";
        form.scrollIntoView({ behavior: "smooth" });
      });
    });

    // Botones de eliminar usuario
    qa(".btn-borrar-usr").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var uid = btn.getAttribute("data-uid");
        var nom = btn.getAttribute("data-nom");
        if (!confirm("¿Está seguro de eliminar al usuario '" + nom + "' (ID: " + uid + ")?")) return;

        fetch("/api/usuarios/" + encodeURIComponent(uid) + "/eliminar", { method: "POST" })
          .then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              alert(res.mensaje || "Usuario eliminado");
              cargar(false);
            } else {
              alert("Error: " + (res.error || "No se pudo eliminar"));
            }
          }).catch(function (err) {
            alert("Error de conexión: " + err.message);
          });
      });
    });
  }

  /* ---------- Exportación a CSV con UTF-8 BOM para Excel ---------- */
  function exportarTablaCSV(nombreArchivo, tablaSelectorOEl) {
    var tabla = typeof tablaSelectorOEl === "string" ? document.querySelector(tablaSelectorOEl) : tablaSelectorOEl;
    if (!tabla) {
      alert("No se encontró ninguna tabla para exportar.");
      return;
    }
    var trs = qa("tr", tabla);
    var csv = [];
    trs.forEach(function (tr) {
      var celdas = qa("th, td", tr);
      if (!celdas.length) return;
      var fila = celdas.map(function (c) {
        var txt = (c.innerText || c.textContent || "").replace(/"/g, '""').trim();
        return '"' + txt + '"';
      });
      csv.push(fila.join(";"));
    });
    var contenido = "\uFEFF" + csv.join("\r\n");
    var blob = new Blob([contenido], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = (nombreArchivo || "export_ganaderia_ja") + "_" + new Date().toISOString().slice(0, 10) + ".csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  window.__exportarInventario = function () {
    exportarTablaCSV("inventario_ganaderia_ja", ".tabla-scroll table");
  };
  window.__exportarRetiros = function () {
    exportarTablaCSV("retiros_sanitarios_ja", ".tabla-scroll table");
  };

