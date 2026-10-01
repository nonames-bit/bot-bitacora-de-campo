  /* ---------- Sección de Ayuda & Guía Operativa ---------- */
  var _tabAyudaInstalar = "android";
  function renderAyuda() {
    var h = "<h3>" + icon("help") + "Centro de Ayuda & Guía de Uso</h3>";
    h += "<p class='aviso'>Aprende a instalar la aplicación en tu celular, operar en el potrero sin internet, registrar pesajes continuos y aprovechar la Inteligencia Artificial de la bitácora.</p>";

    h += "<div class='ayuda-grid'>";

    // Tarjeta 1: Instalación de la App
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("download", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>" + icon("phone", 16) + "Cómo Instalar la App en tu Celular o PC</h4>"
      + "<small style='color:var(--texto-suave);'>Instálala como aplicación nativa, pantalla completa y sin barra de navegador</small>"
      + "</div>"
      + "</div>"
      + "<div class='ayuda-tabs-row' style='margin-top:12px;'>"
      + "<button type='button' class='btn-punto " + (_tabAyudaInstalar === "android" ? "act" : "") + "' data-ayuda-tab='android' style='font-size:12px; padding:6px 12px;'>Android (Chrome)</button>"
      + "<button type='button' class='btn-punto " + (_tabAyudaInstalar === "ios" ? "act" : "") + "' data-ayuda-tab='ios' style='font-size:12px; padding:6px 12px;'>iPhone / iPad (iOS)</button>"
      + "<button type='button' class='btn-punto " + (_tabAyudaInstalar === "pc" ? "act" : "") + "' data-ayuda-tab='pc' style='font-size:12px; padding:6px 12px;'>Computador (Chrome/Edge)</button>"
      + "</div>"
      + "<div id='ayuda-tab-cuerpo' style='margin-top:10px; font-size:13px; line-height:1.5;'>";

    if (_tabAyudaInstalar === "android") {
      h += "<p><b>En tu teléfono o tablet Android:</b></p>"
        + "<ol style='padding-left:18px; margin:6px 0;'>"
        + "<li>Toca el botón verde <b>'Instalar App'</b> en la barra superior o usa el botón de abajo.</li>"
        + "<li>Si no aparece, abre el menú de tres puntos (<b>⋮</b>) arriba a la derecha en Chrome.</li>"
        + "<li>Selecciona <b>'Instalar aplicación'</b> o <b>'Agregar a la pantalla principal'</b>.</li>"
        + "<li>Confirma en <b>'Instalar'</b>. ¡Listo! Se creará el icono de <i>Bitácora JA</i> junto a tus demás aplicaciones.</li>"
        + "</ol>"
        + "<div style='margin-top:10px;'><button type='button' id='btn-ayuda-disparar-instalar' class='tema-btn' style='background:var(--color-verde-btn, #2e7d32); color:#fff; font-weight:bold; font-size:13px; padding:8px 14px; border-radius:6px; cursor:pointer;'>" + icon("download", 15) + "Instalar Bitácora Ganadera Ahora</button></div>";
    } else if (_tabAyudaInstalar === "ios") {
      h += "<p><b>En iPhone o iPad (usando Safari):</b></p>"
        + "<ol style='padding-left:18px; margin:6px 0;'>"
        + "<li>Abre <b>Safari</b> e ingresa a <code>https://ganaderiaja.duckdns.org/</code>.</li>"
        + "<li>Toca el botón <b>Compartir</b> (el icono de un cuadro con una flecha hacia arriba en la barra inferior de Safari).</li>"
        + "<li>Desplaza hacia abajo en la lista y toca <b>'Agregar al inicio'</b> (o <i>'Add to Home Screen'</i> <b>+</b>).</li>"
        + "<li>Toca <b>'Agregar'</b> arriba a la derecha. La app se abrirá sin barras ni pestañas de navegador, como app nativa.</li>"
        + "</ol>";
    } else {
      h += "<p><b>En Windows, Mac o Linux (Chrome / Edge):</b></p>"
        + "<ol style='padding-left:18px; margin:6px 0;'>"
        + "<li>En la barra de direcciones de tu navegador, haz clic en el icono de instalación <b>(+)</b> o monitor con flecha.</li>"
        + "<li>O abre el menú (<b>⋮</b> o <b>…</b>) y selecciona <b>'Instalar Bitácora Ganadera JA'</b>.</li>"
        + "<li>Se abrirá en su propia ventana independiente con acceso directo en tu escritorio.</li>"
        + "</ol>";
    }

    h += "</div></div>";

    // Tarjeta 2: Modo Offline Real
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("cloud", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>" + icon("wifi", 16) + "Modo Offline Real (Sin Cobertura Celular)</h4>"
      + "<small style='color:var(--texto-suave);'>Trabaja con total confianza en el potrero o la manga</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>La Bitácora está equipada con tecnología <b>PWA Offline Real</b>:</p>"
      + "<ul style='padding-left:18px; margin:6px 0;'>"
      + "<li><b>Guardado local inmediato:</b> Todos los pesajes, partos, celos, traslados y drogas aplicadas se guardan en tu celular mediante <i>IndexedDB</i>, aunque estés en modo avión o sin señal.</li>"
      + "<li><b>Indicador de estado:</b> El icono de nube en la barra superior muestra el estado de la conexión y la cantidad de registros pendientes por subir.</li>"
      + "<li><b>Sincronización automática:</b> Al regresar a la casa de la finca o recuperar datos móviles, la app envía automáticamente todos los registros acumulados al servidor sin perder nada.</li>"
      + "</ul>"
      + "</div></div>";

    // Tarjeta 3: Manga y Pesaje Continuo
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("scale", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>" + icon("scale", 16) + "Trabajo en Manga & Pesaje Continuo</h4>"
      + "<small style='color:var(--texto-suave);'>Flujo rápido para jornadas de pesaje de hato completo</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>Diseñado para no frenar el paso de los animales en el corral:</p>"
      + "<ol style='padding-left:18px; margin:6px 0;'>"
      + "<li>Entra en la pestaña <b>'Manga'</b>.</li>"
      + "<li>Escribe el arete/tag (o léelo por RFID/código de barras) y digita el peso en kg.</li>"
      + "<li>Pulsa <b>Enter</b> o 'Guardar Pesaje'. Al instante verás la <b>GMD (Ganancia Media Diaria)</b> calculada contra el pesaje anterior del animal.</li>"
      + "<li>El cursor vuelve automáticamente al campo de arete listo para el siguiente animal de la manga.</li>"
      + "<li>También puedes registrar tratamientos grupales (desparasitante, vacunas, vitaminas) aplicados a toda la jornada.</li>"
      + "</ol>"
      + "</div></div>";

    // Tarjeta 4: Captura Rápida & Fotos
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("camera", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>" + icon("camera", 16) + "Captura Rápida & Respaldo Fotográfico</h4>"
      + "<small style='color:var(--texto-suave);'>Eventos de manejo y campo con foto de evidencia opcional</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>En la pestaña <b>'Captura'</b> tienes botones directos para cada evento:</p>"
      + "<ul style='padding-left:18px; margin:6px 0;'>"
      + "<li><b>" + icon("cowCalf", 14) + "Partos:</b> Registra arete de la madre, nuevo arete de la cría, sexo, peso al nacer y foto del ternero.</li>"
      + "<li><b>" + icon("syringe", 14) + "Tratamientos:</b> Producto, dosis, vía y control automático de días de retiro para leche y carne.</li>"
      + "<li><b>" + icon("cowSkull", 14) + "Muerte / Descarte:</b> Causa presunta, notas de necropsia y foto de respaldo.</li>"
      + "<li><b>" + icon("flame", 14) + "Celo / " + icon("sperm", 14) + "Servicio IA:</b> Horario AM-PM, código de pajilla/toro e inseminador.</li>"
      + "<li><b>Fotos ligeras:</b> Las fotos tomadas se optimizan automáticamente a menos de 150 KB para no consumir memoria ni datos en campo.</li>"
      + "</ul>"
      + "</div></div>";

    // Tarjeta 5: Dictado por Voz (Whisper)
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("mic", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>" + icon("mic", 16) + "Dictado por Voz con Inteligencia Artificial</h4>"
      + "<small style='color:var(--texto-suave);'>Registra novedades hablando naturalmente mientras caminas</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>Si tienes las manos ocupadas en el corral:</p>"
      + "<ol style='padding-left:18px; margin:6px 0;'>"
      + "<li>Entra en la pestaña <b>'Voz'</b> y presiona el micrófono.</li>"
      + "<li>Habla claro, por ejemplo: <i>'Ayer parió la vaca 47 ternero macho vivo de 34 kilos'</i> o <i>'Pesé la novilla 102 con 380 kilos'</i>.</li>"
      + "<li>El motor de transcripción e inteligencia artificial estructurará el registro automáticamente para que solo confirmes con un toque.</li>"
      + "</ol>"
      + "</div></div>";

    // Tarjeta 6: Asistente IA & Preguntas Frecuentes
    h += "<div class='card ayuda-card'>"
      + "<div class='ayuda-card-header'>"
      + "<div class='ayuda-badge-ico'>" + icon("chat", 20) + "</div>"
      + "<div>"
      + "<h4 style='margin:0;'>" + icon("bot", 16) + "Asistente Inteligente IA & Chat</h4>"
      + "<small style='color:var(--texto-suave);'>Pregunta sobre tus animales o sobre el funcionamiento de la app</small>"
      + "</div>"
      + "</div>"
      + "<div style='margin-top:10px; font-size:13px; line-height:1.5;'>"
      + "<p>Toca el botón flotante verde <b>" + icon("bot", 14) + "</b> abajo a la derecha en cualquier momento:</p>"
      + "<ul style='padding-left:18px; margin:6px 0;'>"
      + "<li><b>Preguntas de hato:</b> <i>'¿Cuántas vacas activas hay en Guayabal?'</i>, <i>'¿Quiénes están en retiro de leche?'</i>, <i>'Ficha del toro GUZ-01'</i>.</li>"
      + "<li><b>Preguntas de la aplicación:</b> <i>'¿Cómo instalo la app?'</i>, <i>'¿Cómo funciona sin internet?'</i>, <i>'¿Cómo peso en la manga?'</i>.</li>"
      + "<li>El asistente responderá de inmediato con datos en vivo o explicaciones paso a paso.</li>"
      + "</ul>"
      + "</div></div>";

    h += "</div>"; // fin ayuda-grid
    return h;
  }

  function bindAyuda() {
    var tabs = qa("button[data-ayuda-tab]");
    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        _tabAyudaInstalar = btn.getAttribute("data-ayuda-tab") || "android";
        var vistaEl = document.getElementById("vista");
        if (vistaEl) {
          montarVista(vistaEl, renderAyuda(), false);
          bindAyuda();
        }
      });
    });

    var btnInstalar = document.getElementById("btn-ayuda-disparar-instalar");
    if (btnInstalar) {
      btnInstalar.addEventListener("click", function () {
        var topBtn = document.getElementById("btn-instalar-app");
        if (topBtn && topBtn.style.display !== "none") {
          topBtn.click();
        } else if (window.__pwaInstallPrompt) {
          window.__pwaInstallPrompt.prompt();
        } else {
          alert("Para instalar en Android: abre el menú ⋮ de Chrome y selecciona 'Instalar aplicación' o 'Agregar a la pantalla principal'.");
        }
      });
    }
  }

  /* ---------- GPS Potrero & Rondas de Campo ---------- */
  var _gpsUltimaPos = null;
  /* ---------- Telemetría Silenciosa GPS en Segundo Plano ---------- */
  function enviarTelemetriaSilenciosa(evento) {
    if (!navigator.geolocation) return;
    try {
      navigator.geolocation.getCurrentPosition(function (pos) {
        var lat = pos.coords.latitude;
        var lon = pos.coords.longitude;
        var acc = pos.coords.accuracy ? Math.round(pos.coords.accuracy) : null;
        var ahora = new Date();
        var horaStr = ahora.toTimeString().split(" ")[0];
        var fechaStr = ahora.toISOString().slice(0, 10);
        var payload = {
          lat: lat,
          lon: lon,
          precision_m: acc,
          evento_origen: evento || "interaccion_app",
          fecha: fechaStr,
          hora: horaStr
        };

        if (navigator.onLine === false) {
          encolarOffline("telemetria_ping", payload).catch(function () {});
          return;
        }

        fetch("/api/telemetria/ping", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }).catch(function () {
          encolarOffline("telemetria_ping", payload).catch(function () {});
        });
      }, function (err) {
        // Silencioso: no molestar al operario si no hay señal de satélite o está desactivado
      }, {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000
      });
    } catch (e) {
      // Ignorar de forma silenciosa
    }
  }

  /* ---------- Vista Mapa Satelital Interactivo & Operarios ---------- */
  var _mapaInstancia = null;
  var _mapaCapaPotreros = null;
  var _mapaCapaUsuarios = null;
  var _mapaCapaRastros = null;
  var _mapaModoActual = "vigor"; // 'vigor', 'voisin', 'satelite'
  var _mapaVerOperarios = true;
  var _mapaMarkerSelf = null;
  var _mapaCircleSelf = null;
  var _mapaCapaSelf = null;
  var _mapaWatchGpsId = null;
  var _mapaTimerRefresh = null;

  function renderMapa(d) {
    var totalPot = (d && d.finca && d.finca.total_potreros) || (d && d.potreros_geojson && d.potreros_geojson.features ? d.potreros_geojson.features.length : 0);
    var uActivos = (d && d.usuarios_activos) ? d.usuarios_activos.filter(function (u) { return u.dist_finca_km == null || u.dist_finca_km <= 35.0; }) : [];

    var h = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>"
      + icon("grid", 20) + "Mapa Satelital de Potreros &amp; Operarios"
      + "</h3>"
      + "<span class='meta' style='font-size:12px; font-weight:600;'>" + icon("grass", 12) + totalPot + " potreros · " + icon("cowboy", 12) + uActivos.length + " operarios con señal</span>"
      + "</div>";

    // Barra de herramientas del Mapa
    h += "<div class='mapa-toolbar'>"
      + "<div class='mapa-grupos'>"
      + "<span style='font-size:12px; font-weight:700; color:var(--texto-suave); margin-right:4px;'>Capa:</span>"
      + "<button type='button' class='mapa-btn" + (_mapaModoActual === "vigor" ? " act" : "") + "' data-modo-mapa='vigor'>" + icon("leaf", 14) + "Vigor NDVI/SAR</button>"
      + "<button type='button' class='mapa-btn" + (_mapaModoActual === "voisin" ? " act" : "") + "' data-modo-mapa='voisin'>" + icon("cow", 14) + "Ocupación &amp; Voisin</button>"
      + "<button type='button' class='mapa-btn" + (_mapaModoActual === "satelite" ? " act" : "") + "' data-modo-mapa='satelite'>" + icon("satellite", 14) + "Satelital</button>"
      + "</div>"
      + "<div class='mapa-grupos'>"
      + "<button type='button' class='mapa-btn" + (_mapaVerOperarios ? " act" : "") + "' id='btn-toggle-operarios'>" + icon("cowboy", 14) + "Operarios (" + uActivos.length + ")</button>"
      + "<button type='button' class='mapa-btn' id='btn-mi-ubicacion-mapa'>" + icon("pin", 14) + "Mi GPS</button>"
      + "<button type='button' class='mapa-btn' id='btn-centrar-finca'>" + icon("grass", 14) + "Toda la Finca</button>"
      + "<button type='button' class='mapa-btn' id='btn-refrescar-mapa' title='Actualizar posiciones y datos'>" + icon("refresh", 14) + "</button>"
      + "</div>"
      + "</div>";

    // Contenedor del Mapa
    h += "<div class='mapa-wrap'>"
      + "<div id='mapa-finca'></div>"
      + "</div>";

    // Barra de Leyenda Dinámica
    h += "<div id='mapa-leyenda-dinamica' class='mapa-leyenda'>";
    if (_mapaModoActual === "voisin") {
      h += "<span style='font-weight:700; margin-right:6px;'>Leyenda Voisin:</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#2e7d32;'></span> Ocupado (≤3d)</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#c62828;'></span> Alerta (>3d Sobrepastoreo)</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#1565c0;'></span> Reposado (≥30d Listo)</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#00838f;'></span> En descanso (20-29d)</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#ef6c00;'></span> Recién salido (&lt;20d)</span>";
    } else if (_mapaModoActual === "vigor") {
      h += "<span style='font-weight:700; margin-right:6px;'>Vigor Forrajero:</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#1b5e20;'></span> Excelente / Denso</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#388e3c;'></span> Bueno / Creciendo</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#fbc02d;'></span> Medio</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#f57c00;'></span> Bajo / Reposo</span>"
        + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#d32f2f;'></span> Crítico</span>";
    } else {
      h += "<span style='font-weight:700; margin-right:6px;'>Capa:</span> Vista satelital óptica de alta resolución (Esri World Imagery) con linderos de potrero.";
    }
    h += "</div>";

    // Panel de Operarios en Campo
    h += "<div class='card' style='padding:14px; margin-top:14px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("users", 16) + "Operarios &amp; Personal de Campo (" + uActivos.length + ")</h4>"
      + "<span style='font-size:12px; color:var(--texto-suave);'>Posiciones satelitales en tiempo real</span>"
      + "</div>";

    if (!uActivos.length) {
      h += vacio("No hay posiciones GPS registradas recientemente. Al abrir la app en potrero, los vaqueros y administradores transmiten su ubicación.");
    } else {
      h += "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:10px;'>";
      uActivos.forEach(function (u, uIdx) {
        var rolClase = (u.rol === "OWNER") ? "rojo" : ((u.rol === "ADMIN") ? "ambar" : "verde");
        var estadoTxt = u.en_linea
          ? "<span class='chip verde' style='font-size:11px;'>" + dot("verde") + "En línea (" + (u.minutos_hace != null ? "hace " + u.minutos_hace + "m" : "ahora") + ")</span>"
          : "<span class='chip gris' style='font-size:11px;'>" + dot("gris") + esc(u.fecha) + " " + esc(u.hora ? u.hora.slice(0, 5) : "") + "</span>";

        h += "<div class='card' style='padding:10px; margin:0; border:1px solid var(--borde); display:flex; flex-direction:column; justify-content:space-between;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;'>"
          + "<div><b>" + esc(u.nombre) + "</b> <span class='chip " + rolClase + "' style='font-size:10.5px;'>" + esc(u.rol) + "</span></div>"
          + estadoTxt
          + "</div>"
          + "<div style='font-size:12.5px; color:var(--texto-suave); margin-bottom:8px;'>"
          + icon("pin", 14) + "Potrero: <b style='color:var(--texto);'>" + esc(u.potrero_actual) + "</b>"
          + (u.precision_m ? " <small>(±" + Math.round(u.precision_m) + "m)</small>" : "")
          + "</div>"
          + "<div style='display:flex; gap:6px;'>"
          + "<button type='button' class='tema-btn' data-ir-usuario='" + uIdx + "' style='font-size:11.5px; padding:4px 10px; flex:1;'>" + icon("target", 12) + "Enfocar</button>"
          + (u.rastro_hoy && u.rastro_hoy.length ? "<button type='button' class='tema-btn' data-rastro-usuario='" + uIdx + "' style='font-size:11.5px; padding:4px 10px; flex:1;'>" + icon("walk", 12) + "Ver rastro (" + u.rastro_hoy.length + ")</button>" : "")
          + "</div>"
          + "</div>";
      });
      h += "</div>";
    }
    h += "</div>";

    // Sección de Auditoría de Rutas, Desplazamientos y Rondas GPS (Unificada)
    var rutas = (d && d.rutas) || [];
    var rondas = (d && d.rondas) || [];
    var fFecha = (d && d.fecha_filtro) || _fechaFiltroRutas || new Date().toISOString().slice(0, 10);

    h += "<div class='card' style='padding:14px; margin-top:14px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;'>"
      + "<h4 style='margin:0; display:flex; align-items:center; gap:6px;'>" + icon("pin", 16) + "Auditoría de Rutas, Desplazamientos &amp; Telemetría</h4>"
      + "<div style='display:flex; flex-wrap:wrap; gap:8px; align-items:center;'>"
      + "<label style='font-size:12px; font-weight:600; color:var(--texto-suave); display:flex; align-items:center; gap:6px;'>"
      + icon("calendar", 14) + "Fecha: "
      + "<input type='date' id='filtro-fecha-rutas' value='" + esc(fFecha) + "' style='padding:4px 8px; border-radius:6px; border:1px solid var(--borde); font-size:12px;'>"
      + "</label>"
      + "<button type='button' id='btn-refrescar-rutas' class='tema-btn' style='font-size:12px; padding:4px 10px;'>" + icon("search", 13) + "Consultar Rutas</button>"
      + (rutas.length ? "<button type='button' id='btn-exportar-rutas-csv' class='tema-btn' style='font-size:12px; padding:4px 10px;'>" + icon("download", 13) + "Exportar CSV</button>" : "")
      + "</div>"
      + "</div>";

    if (!rutas.length) {
      h += vacio("No hay desplazamientos registrados para la fecha " + fechaCorta(fFecha) + ". Los puntos GPS se capturan en segundo plano al interactuar con la app en campo.");
    } else {
      rutas.forEach(function (r, rIdx) {
        var rolBadge = r.rol === "OWNER" ? "rojo" : (r.rol === "ADMIN" ? "ambar" : "verde");
        h += "<div class='card-operario-ruta' style='margin-bottom:10px; border:1px solid var(--borde); padding:10px; border-radius:8px;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
          + "<div><b style='font-size:15px;'>" + esc(r.usuario_nombre) + "</b> <span class='chip " + rolBadge + "' style='font-size:10.5px;'>" + esc(r.rol) + "</span></div>"
          + "<div style='display:flex; align-items:center; gap:8px;'>"
          + "<span style='font-size:12px; color:var(--texto-suave);'>" + icon("clock", 12) + esc(r.hora_inicio || "—") + " a " + esc(r.hora_fin || "—") + " · " + icon("pin", 12) + "<b>" + r.total_puntos + " puntos</b></span>"
          + (r.puntos && r.puntos.length ? "<button type='button' class='tema-btn' data-trazar-ruta-mapa='" + rIdx + "' style='font-size:11.5px; padding:3px 9px;'>" + icon("map", 12) + "Ver rastro en mapa</button>" : "")
          + "</div>"
          + "</div>";

        // Timeline de potreros
        h += "<div class='timeline-rutas' style='margin-bottom:6px;'>";
        if (!r.secuencia_potreros || !r.secuencia_potreros.length) {
          h += "<span style='font-size:12px; color:var(--texto-suave);'>Sin visitas a potreros registradas</span>";
        } else {
          r.secuencia_potreros.forEach(function (s, sIdx) {
            if (sIdx > 0) h += "<span class='chip-flecha'>" + icon("arrowRight", 12) + "</span>";
            h += "<span class='chip-ruta'>" + icon("pin", 12) + "<b>" + esc(s.hora) + "</b> " + icon("grass", 12) + esc(s.potrero) + "</span>";
          });
        }
        h += "</div>";

        // Desglose de coordenadas colapsable
        var tablaId = "tabla-pts-" + rIdx;
        h += "<details style='font-size:12px; margin-top:6px;'>"
          + "<summary style='cursor:pointer; font-weight:600; color:var(--verde-marca); padding:3px 0;'>" + icon("search", 14) + "Ver desglose de coordenadas (" + (r.puntos ? r.puntos.length : 0) + " registros)</summary>"
          + "<div class='tabla-scroll' style='margin-top:6px;'>"
          + "<table id='" + tablaId + "'><tr><th>Hora</th><th>Potrero</th><th>Latitud</th><th>Longitud</th><th>Precisión</th><th>Evento</th><th>Google Maps</th></tr>";
        (r.puntos || []).forEach(function (pt) {
          var mapsUrl = "https://maps.google.com/?q=" + pt.lat + "," + pt.lon;
          h += "<tr>"
            + "<td><b>" + esc(pt.hora) + "</b></td>"
            + "<td><b>" + esc(pt.potrero_nombre || "Área de la Finca") + "</b></td>"
            + "<td>" + Number(pt.lat).toFixed(6) + "</td>"
            + "<td>" + Number(pt.lon).toFixed(6) + "</td>"
            + "<td>±" + (pt.precision_m ? Math.round(pt.precision_m) + " m" : "—") + "</td>"
            + "<td><span class='chip gris' style='font-size:10.5px;'>" + esc(pt.evento_origen || "auto") + "</span></td>"
            + "<td><a href='" + esc(mapsUrl) + "' target='_blank' rel='noopener' class='chip azul' style='font-size:10.5px; text-decoration:none;'>" + icon("map", 12) + "Maps</a></td>"
            + "</tr>";
        });
        h += "</table></div></details></div>";
      });
    }

    // Rondas manuales de campo
    if (rondas && rondas.length) {
      h += "<div style='margin-top:16px; border-top:1px solid var(--borde); padding-top:12px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>"
        + "<h5 style='margin:0;'>" + icon("calendar", 14) + "Puntos de Ronda Manuales (" + rondas.length + ")</h5>"
        + "<button type='button' id='btn-exportar-rondas-csv' class='tema-btn' style='font-size:11px; padding:3px 8px;'>Exportar Rondas CSV</button>"
        + "</div>"
        + "<div class='tabla-scroll'><table id='tabla-rondas'><tr><th>Hora</th><th>Potrero</th><th>Punto</th><th>Usuario</th><th>Notas</th></tr>";
      rondas.forEach(function (ro) {
        h += "<tr><td><b>" + esc(ro.hora || fechaCorta(ro.fecha)) + "</b></td>"
          + "<td><b>" + esc(ro.potrero_nombre || "—") + "</b></td>"
          + "<td><span class='chip verde'>" + esc(ro.punto_control || "recorrido") + "</span></td>"
          + "<td>" + esc(ro.usuario_nombre || "—") + "</td>"
          + "<td>" + esc(ro.notas || "—") + "</td></tr>";
      });
      h += "</table></div></div>";
    }

    h += "</div>";

    return h;
  }

  var _leafletCargando = false;
  var _leafletCallbacksEnEspera = [];

  // Leaflet (CSS+JS, ~150KB) ya no va fijo en el <head>/</body> -- se pedía
  // en TODAS las páginas aunque el 90% de las visitas nunca abren Mapa &
  // GPS. Se inyecta bajo demanda solo la primera vez que se entra a ese
  // módulo, y queda cacheado por el Service Worker para las siguientes.
  function cargarLeafletSiFalta(callback) {
    if (typeof L !== "undefined") { callback(); return; }
    _leafletCallbacksEnEspera.push(callback);
    if (_leafletCargando) return;
    _leafletCargando = true;

    if (!document.getElementById("leaflet-css")) {
      var link = document.createElement("link");
      link.id = "leaflet-css";
      link.rel = "stylesheet";
      link.href = "/static/leaflet/leaflet.css";
      document.head.appendChild(link);
    }
    var script = document.createElement("script");
    script.src = "/static/leaflet/leaflet.js";
    script.onload = function () {
      var pendientes = _leafletCallbacksEnEspera;
      _leafletCallbacksEnEspera = [];
      _leafletCargando = false;
      pendientes.forEach(function (cb) { cb(); });
    };
    script.onerror = function () {
      _leafletCargando = false;
      var mapEl = document.getElementById("mapa-finca");
      if (mapEl) mapEl.innerHTML = "<p class='aviso' style='padding:30px; text-align:center;'>" + icon("alertTriangle", 14) + "No se pudo cargar el componente de mapas. Verifica tu conexión e intenta de nuevo.</p>";
    };
    document.body.appendChild(script);
  }

  function bindMapa(d) {
    if (typeof L === "undefined") {
      var mapEl = document.getElementById("mapa-finca");
      if (mapEl) mapEl.innerHTML = "<p class='aviso' style='padding:30px; text-align:center;'>" + icon("alertTriangle", 14) + "Cargando componente de mapas Leaflet… Si no carga, verifica tu conexión.</p>";
      return;
    }

    var mapEl = document.getElementById("mapa-finca");
    if (!mapEl) return;

    if (_mapaInstancia) {
      try { _mapaInstancia.remove(); } catch (e) {}
      _mapaInstancia = null;
    }
    if (_mapaTimerRefresh) {
      clearInterval(_mapaTimerRefresh);
      _mapaTimerRefresh = null;
    }

    var centro = (d.finca && d.finca.centroide) || [3.402, -74.088];
    var map = L.map("mapa-finca", {
      zoomControl: true,
      attributionControl: true
    }).setView(centro, 14);
    _mapaInstancia = map;

    // Capa base satelital Esri
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 19,
      attribution: "Tiles &copy; Esri &mdash; Ganader&iacute;a JA"
    }).addTo(map);

    // Ajustar zoom a los límites de la finca
    if (d.finca && d.finca.bbox) {
      try {
        map.fitBounds(d.finca.bbox, { padding: [25, 25] });
      } catch (e) {}
    }

    _mapaCapaPotreros = L.layerGroup().addTo(map);
    _mapaCapaUsuarios = L.layerGroup().addTo(map);
    _mapaCapaRastros = L.layerGroup().addTo(map);
    _mapaCapaSelf = L.layerGroup().addTo(map);

    setTimeout(function () { if (_mapaInstancia) _mapaInstancia.invalidateSize(); }, 150);
    setTimeout(function () { if (_mapaInstancia) _mapaInstancia.invalidateSize(); }, 500);

    function colorParaPotrero(props) {
      if (_mapaModoActual === "satelite") return { fill: true, fillColor: "#2ecc71", color: "#f1c40f", weight: 2.2, fillOpacity: 0.12 };
      if (_mapaModoActual === "voisin") return { fill: true, fillColor: props.color_voisin || "#2e7d32", color: "#ffffff", weight: 1.5, fillOpacity: 0.5 };
      return { fill: true, fillColor: props.color_ndvi || "#2e7d32", color: "#ffffff", weight: 1.5, fillOpacity: 0.55 };
    }

    function pintarPotreros() {
      _mapaCapaPotreros.clearLayers();
      if (!d.potreros_geojson || !d.potreros_geojson.features) return;

      var layer = L.geoJSON(d.potreros_geojson, {
        style: function (feat) {
          var est = colorParaPotrero(feat.properties);
          return {
            fill: est.fill,
            fillColor: est.fillColor,
            fillOpacity: est.fillOpacity,
            color: est.color,
            weight: est.weight
          };
        },
        onEachFeature: function (feat, lyr) {
          var p = feat.properties;
          var nAnim = p.animales_count || 0;
          var labelTxt = p.nombre + (nAnim > 0 ? " (" + nAnim + " anim)" : "");

          lyr.bindTooltip(labelTxt, {
            permanent: _mapaModoActual === "satelite",
            direction: "center",
            className: "mapa-tooltip-potrero"
          });

          // Popup al tocar potrero
          var popHtml = "<div style='font-family:sans-serif; min-width:200px; padding:4px;'>"
            + "<h4 style='margin:0 0 6px 0; color:#1b4d3e; font-size:15px; border-bottom:1px solid #ddd; padding-bottom:4px;'>" + esc(p.nombre) + "</h4>"
            + "<div style='font-size:12px; line-height:1.5;'>"
            + icon("ruler", 12) + "<b>Área:</b> " + p.area_has + " ha<br>"
            + icon("cow", 12) + "<b>Ocupación:</b> " + (nAnim > 0 ? ("<b>" + nAnim + " cabezas</b>") : "Desocupado") + "<br>"
            + icon("hourglass", 12) + "<b>Voisin:</b> " + esc(p.estado_voisin || "—") + "<br>"
            + icon("leaf", 12) + "<b>Vigor NDVI:</b> " + (p.ndvi_valor != null ? ("<b>" + p.ndvi_valor.toFixed(3) + "</b> (" + esc(p.categoria_ndvi) + ")") : "—") + "<br>"
            + (p.biomasa_kg_ha ? (icon("grass", 12) + "<b>Biomasa:</b> " + Math.round(p.biomasa_kg_ha) + " kg MS/ha<br>") : "")
            + "</div>";

          if (p.animales_tags && p.animales_tags.length) {
            popHtml += "<div style='margin-top:6px; font-size:11px; color:#666;'>Tags: " + esc(p.animales_tags.join(", ")) + (nAnim > p.animales_tags.length ? "..." : "") + "</div>";
          }
          popHtml += "</div>";
          lyr.bindPopup(popHtml);

          lyr.on("mouseover", function () { lyr.setStyle({ weight: 3.5, color: "#ffffff" }); });
          lyr.on("mouseout", function () {
            var orig = colorParaPotrero(p);
            lyr.setStyle({ weight: orig.weight, color: orig.color, fillColor: orig.fillColor, fillOpacity: orig.fillOpacity });
          });
        }
      });
      _mapaCapaPotreros.addLayer(layer);
    }

    function pintarUsuarios() {
      _mapaCapaUsuarios.clearLayers();
      if (!_mapaVerOperarios || !d.usuarios_activos) return;

      d.usuarios_activos.forEach(function (u, idx) {
        if (u.dist_finca_km != null && u.dist_finca_km > 35.0) return;
        if (!u.lat || !u.lon) return;

        var rolClase = (u.rol === "OWNER") ? "owner" : ((u.rol === "ADMIN") ? "admin" : "trabajador");
        var pulseClase = u.en_linea ? "" : " offline";
        var htmlPin = "<div class='user-marker-pin' data-uidx='" + idx + "'>"
          + "<div class='user-marker-badge " + rolClase + "'>" + icon("cowboy", 12) + esc(u.nombre) + "</div>"
          + "<div class='user-pulse-dot" + pulseClase + "'></div>"
          + "</div>";

        var iconCustom = L.divIcon({
          className: "user-div-icon",
          html: htmlPin,
          iconSize: [120, 42],
          iconAnchor: [60, 42]
        });

        var m = L.marker([u.lat, u.lon], { icon: iconCustom });
        var popU = "<div style='font-family:sans-serif; min-width:180px; padding:4px;'>"
          + "<b style='font-size:14px;'>" + esc(u.nombre) + "</b> <span style='font-size:11px;'>(" + esc(u.rol) + ")</span><br>"
          + "<div style='font-size:12px; margin-top:4px; line-height:1.4;'>"
          + icon("pin", 12) + "Potrero: <b>" + esc(u.potrero_actual) + "</b><br>"
          + icon("clock", 12) + "Hora: <b>" + esc(u.hora || u.fecha) + "</b>" + (u.minutos_hace != null ? " (hace " + u.minutos_hace + "m)" : "") + "<br>"
          + (u.precision_m ? icon("satellite", 12) + "Precisión: ±" + Math.round(u.precision_m) + "m<br>" : "")
          + "</div></div>";
        m.bindPopup(popU);
        _mapaCapaUsuarios.addLayer(m);
      });
    }

    function actualizarPosicionPropia(myLat, myLon, myAcc, centrarSiCerca) {
      if (!_mapaInstancia || !_mapaCapaSelf) return;
      _mapaCapaSelf.clearLayers();

      if (myAcc && myAcc > 5) {
        _mapaCircleSelf = L.circle([myLat, myLon], {
          radius: myAcc,
          color: "#0288d1",
          fillColor: "#0288d1",
          fillOpacity: 0.12,
          weight: 1.2
        }).addTo(_mapaCapaSelf);
      }

      var iconSelf = L.divIcon({
        className: "self-gps-icon",
        html: "<div class='self-pulse-dot' title='Mi ubicación GPS'></div>",
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      });

      _mapaMarkerSelf = L.marker([myLat, myLon], { icon: iconSelf }).addTo(_mapaCapaSelf);

      var cFinca = (d.finca && d.finca.centroide) || [3.402, -74.088];
      var distFincaKm = Math.sqrt(Math.pow((myLat - cFinca[0]) * 111.0, 2) + Math.pow((myLon - cFinca[1]) * 111.0, 2));
      var textoUbic = distFincaKm <= 3.5
        ? "<b>" + icon("pin", 14) + "Estás en la Finca</b>"
        : ("<b>" + icon("pin", 14) + "Tu ubicación actual</b><br><small style='color:#666;'>A " + distFincaKm.toFixed(1) + " km de la finca</small>");

      _mapaMarkerSelf.bindPopup(
        "<div style='font-family:sans-serif; min-width:160px; padding:4px;'>"
        + textoUbic + "<br>"
        + "<span style='font-size:11.5px;'>Precisión: ±" + Math.round(myAcc) + "m</span>"
        + "</div>"
      );

      if (centrarSiCerca && distFincaKm <= 5.0) {
        _mapaInstancia.setView([myLat, myLon], 16);
      }

      fetch("/api/telemetria/ping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: myLat, lon: myLon, accuracy: myAcc, evento: "mapa_activo" })
      }).catch(function () {});
    }

    function iniciarRastreoGps(centrarSiCerca) {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(function (pos) {
        actualizarPosicionPropia(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy || 0, centrarSiCerca);
      }, function (err) {
        console.warn("GPS no disponible:", err && err.message);
      }, { enableHighAccuracy: true, timeout: 10000 });

      if (!_mapaWatchGpsId) {
        _mapaWatchGpsId = navigator.geolocation.watchPosition(function (pos) {
          actualizarPosicionPropia(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy || 0, false);
        }, function () {}, { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 });
      }
    }

    pintarPotreros();
    pintarUsuarios();
    iniciarRastreoGps(true);

    // Botones de selector de modo
    qa(".mapa-btn[data-modo-mapa]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        qa(".mapa-btn[data-modo-mapa]").forEach(function (b) { b.classList.remove("act"); });
        btn.classList.add("act");
        _mapaModoActual = btn.getAttribute("data-modo-mapa");
        pintarPotreros();
        var leyEl = document.getElementById("mapa-leyenda-dinamica");
        if (leyEl) {
          if (_mapaModoActual === "voisin") {
            leyEl.innerHTML = "<span style='font-weight:700; margin-right:6px;'>Leyenda Voisin:</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#2e7d32;'></span> Ocupado (≤3d)</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#c62828;'></span> Alerta (>3d Sobrepastoreo)</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#1565c0;'></span> Reposado (≥30d Listo)</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#00838f;'></span> En descanso (20-29d)</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#ef6c00;'></span> Recién salido (&lt;20d)</span>";
          } else if (_mapaModoActual === "vigor") {
            leyEl.innerHTML = "<span style='font-weight:700; margin-right:6px;'>Vigor Forrajero:</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#1b5e20;'></span> Excelente / Denso</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#388e3c;'></span> Bueno / Creciendo</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#fbc02d;'></span> Medio</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#f57c00;'></span> Bajo / Reposo</span>"
              + "<span class='mapa-leyenda-item'><span class='leyenda-muestra' style='background:#d32f2f;'></span> Crítico</span>";
          } else {
            leyEl.innerHTML = "<span style='font-weight:700; margin-right:6px;'>Capa:</span> Vista satelital óptica de alta resolución (Esri World Imagery) con linderos de potrero.";
          }
        }
      });
    });

    // Toggle ver operarios
    var btnToggleOp = document.getElementById("btn-toggle-operarios");
    if (btnToggleOp) {
      btnToggleOp.addEventListener("click", function () {
        _mapaVerOperarios = !_mapaVerOperarios;
        if (_mapaVerOperarios) btnToggleOp.classList.add("act");
        else btnToggleOp.classList.remove("act");
        pintarUsuarios();
      });
    }

    // Centrar en toda la finca
    var btnCentrar = document.getElementById("btn-centrar-finca");
    if (btnCentrar) {
      btnCentrar.addEventListener("click", function () {
        if (d.finca && d.finca.bbox) map.fitBounds(d.finca.bbox, { padding: [30, 30] });
        else map.setView(centro, 14);
      });
    }

    // Botón refrescar
    var btnRefrescar = document.getElementById("btn-refrescar-mapa");
    if (btnRefrescar) {
      btnRefrescar.addEventListener("click", function () {
        btnRefrescar.innerHTML = icon("hourglass", 14);
        fetchJSON("/api/mapa/datos", function (nuevoD) {
          btnRefrescar.innerHTML = icon("refresh", 14);
          d = nuevoD;
          pintarPotreros();
          pintarUsuarios();
        });
      });
    }

    // Auto-refresh silencioso de operarios cada 25 segundos
    _mapaTimerRefresh = setInterval(function () {
      if (actual !== "mapa") {
        clearInterval(_mapaTimerRefresh);
        _mapaTimerRefresh = null;
        return;
      }
      fetchJSON("/api/mapa/datos", function (nuevoD) {
        if (!nuevoD || !_mapaInstancia) return;
        d = nuevoD;
        pintarUsuarios();
      });
    }, 25000);

    // Botón "Mi Ubicación GPS"
    var btnMiGps = document.getElementById("btn-mi-ubicacion-mapa");
    if (btnMiGps) {
      btnMiGps.addEventListener("click", function () {
        if (!navigator.geolocation) {
          alert("Geolocalización no soportada en este navegador.");
          return;
        }
        btnMiGps.innerHTML = icon("satellite", 14) + "Buscando...";
        navigator.geolocation.getCurrentPosition(function (pos) {
          btnMiGps.innerHTML = icon("pin", 14) + "Mi GPS";
          var myLat = pos.coords.latitude;
          var myLon = pos.coords.longitude;
          var myAcc = pos.coords.accuracy || 0;
          actualizarPosicionPropia(myLat, myLon, myAcc, false);
          if (_mapaInstancia) {
            _mapaInstancia.setView([myLat, myLon], 16);
            if (_mapaMarkerSelf) _mapaMarkerSelf.openPopup();
          }
        }, function (err) {
          btnMiGps.innerHTML = icon("pin", 14) + "Mi GPS";
          alert("No fue posible obtener tu ubicación GPS: " + (err.message || "Permiso denegado."));
        }, { enableHighAccuracy: true, timeout: 10000 });
      });
    }

    // Delegación para botones "Enfocar" y "Ver rastro"
    qa("button[data-ir-usuario]").forEach(function (b) {
      b.addEventListener("click", function () {
        var idx = parseInt(b.getAttribute("data-ir-usuario"), 10);
        var u = d.usuarios_activos && d.usuarios_activos[idx];
        if (u && map) {
          map.setView([u.lat, u.lon], 17);
          try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
        }
      });
    });

    qa("button[data-rastro-usuario]").forEach(function (b) {
      b.addEventListener("click", function () {
        var idx = parseInt(b.getAttribute("data-rastro-usuario"), 10);
        var u = d.usuarios_activos && d.usuarios_activos[idx];
        if (!u || !u.rastro_hoy || !u.rastro_hoy.length) return;

        _mapaCapaRastros.clearLayers();
        var latlngs = u.rastro_hoy.map(function (pt) { return [pt[0], pt[1]]; });
        var poly = L.polyline(latlngs, {
          color: "#f39c12",
          weight: 3.5,
          dashArray: "6, 8",
          opacity: 0.85
        });
        _mapaCapaRastros.addLayer(poly);
        map.fitBounds(poly.getBounds(), { padding: [40, 40] });
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
      });
    });

    // Trazar ruta de operario en el mapa satelital
    qa("button[data-trazar-ruta-mapa]").forEach(function (b) {
      b.addEventListener("click", function () {
        var rIdx = parseInt(b.getAttribute("data-trazar-ruta-mapa"), 10);
        var r = d.rutas && d.rutas[rIdx];
        if (!r || !r.puntos || !r.puntos.length || !_mapaCapaRastros || !_mapaInstancia) return;

        _mapaCapaRastros.clearLayers();
        var latlngs = r.puntos.map(function (pt) { return [pt.lat, pt.lon]; });
        var poly = L.polyline(latlngs, {
          color: "#e67e22",
          weight: 4,
          dashArray: "6, 8",
          opacity: 0.95
        });
        _mapaCapaRastros.addLayer(poly);
        _mapaInstancia.fitBounds(poly.getBounds(), { padding: [35, 35] });

        var mapEl = document.getElementById("mapa-finca");
        if (mapEl) {
          try { mapEl.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (e) {}
        }
      });
    });

    // Control de fecha y recarga de auditoría de rutas
    var btnRefrescarRutas = document.getElementById("btn-refrescar-rutas");
    var inpFechaRutas = document.getElementById("filtro-fecha-rutas");
    if (btnRefrescarRutas && inpFechaRutas) {
      btnRefrescarRutas.addEventListener("click", function () {
        _fechaFiltroRutas = inpFechaRutas.value;
        cargar(true);
      });
      inpFechaRutas.addEventListener("change", function () {
        _fechaFiltroRutas = inpFechaRutas.value;
        cargar(true);
      });
    }

    // Ping manual de GPS para prueba
    var btnPingManual = document.getElementById("btn-ping-manual-gps");
    if (btnPingManual) {
      btnPingManual.addEventListener("click", function () {
        if (!navigator.geolocation) {
          alert("Geolocalización no disponible en este dispositivo.");
          return;
        }
        btnPingManual.textContent = "Obteniendo GPS...";
        navigator.geolocation.getCurrentPosition(function (pos) {
          var lat = pos.coords.latitude;
          var lon = pos.coords.longitude;
          var acc = Math.round(pos.coords.accuracy || 0);
          fetch("/api/telemetria/ping", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              lat: lat,
              lon: lon,
              precision_m: acc,
              evento_origen: "prueba_manual_gps"
            })
          }).then(function (r) { return r.json(); })
            .then(function (res) {
              btnPingManual.textContent = "Posición Registrada";
              setTimeout(function () { cargar(false); }, 800);
            }).catch(function (err) {
              btnPingManual.textContent = "Error: " + err.message;
            });
        }, function (err) {
          btnPingManual.textContent = "" + err.message;
        }, { enableHighAccuracy: true, timeout: 10000 });
      });
    }

    // Exportación CSV de Rutas
    var btnCsvRutas = document.getElementById("btn-exportar-rutas-csv");
    if (btnCsvRutas) {
      btnCsvRutas.addEventListener("click", function () {
        var fFechaSel = _fechaFiltroRutas || new Date().toISOString().slice(0, 10);
        var lineas = [["Usuario", "Rol", "Fecha", "Hora", "Potrero", "Latitud", "Longitud", "Precision_m", "Evento_Origen"]];
        (d.rutas || []).forEach(function (r) {
          (r.puntos || []).forEach(function (p) {
            lineas.push([
              r.usuario_nombre || "",
              r.rol || "",
              p.fecha || fFechaSel,
              p.hora || "",
              p.potrero_nombre || "Área de la Finca",
              p.lat || "",
              p.lon || "",
              p.precision_m != null ? p.precision_m : "",
              p.evento_origen || ""
            ]);
          });
        });
        var csvContent = "\uFEFF" + lineas.map(function (row) {
          return row.map(function (val) {
            return '"' + String(val).replace(/"/g, '""') + '"';
          }).join(";");
        }).join("\r\n");
        var blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "rutas_telemetria_ja_" + fFechaSel + ".csv";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }

    // Exportación CSV de Rondas
    var btnCsvRondas = document.getElementById("btn-exportar-rondas-csv");
    if (btnCsvRondas) {
      btnCsvRondas.addEventListener("click", function () {
        var fFechaSel = _fechaFiltroRutas || new Date().toISOString().slice(0, 10);
        exportarTablaCSV("rondas_campo_" + fFechaSel, "#tabla-rondas");
      });
    }
  }

  var _fechaFiltroRutas = null;
  var _gpsUltimoPotrero = null;
  var _puntoRondaSeleccionado = "saladero";
  var _gpsUltimaPos = null;

  function renderGps(d, fFecha) {
    fFecha = fFecha || _fechaFiltroRutas || new Date().toISOString().slice(0, 10);
    var rutas = (d && d.rutas) || [];
    var rondas = (d && d.rondas) || [];

    var h = "<h3>" + icon("pin", 20) + "Auditoría de Rutas y Telemetría de Campo (Solo OWNER)</h3>"
      + "<p class='aviso'>Monitoreo cronológico y automático de los desplazamientos de operarios en la finca. Identifica qué potreros visitaron, hora de entrada, permanencia y cobertura satelital.</p>";

    // Barra de control de fecha
    h += "<div class='card' style='padding:12px; margin-bottom:14px; display:flex; flex-wrap:wrap; gap:10px; align-items:center;'>"
      + "<label style='font-size:13px; font-weight:600; color:var(--texto-suave); display:flex; align-items:center; gap:6px;'>"
      + icon("calendar", 15) + "Fecha a Auditar: "
      + "<input type='date' id='filtro-fecha-rutas' value='" + esc(fFecha) + "' style='padding:6px 10px; border-radius:6px; border:1px solid var(--borde); font-size:13px;'>"
      + "</label>"
      + "<button type='button' id='btn-refrescar-rutas' class='tema-btn' style='font-size:13px; padding:6px 14px;'>" + icon("search", 14) + "Consultar Rutas</button>"
      + "<button type='button' id='btn-ping-manual-gps' class='chip azul' style='font-size:13px; cursor:pointer;'>" + icon("pin", 14) + "Probar Mi GPS Ahora</button>"
      + "</div>";

    // Resumen de rutas por operario
    h += "<div style='display:flex; justify-content:space-between; align-items:center; margin-top:16px; margin-bottom:10px;'>"
      + "<h4>" + icon("walk", 16) + "Desplazamientos y Recorridos Detectados (" + rutas.length + ")</h4>"
      + (rutas.length ? "<button type='button' id='btn-exportar-rutas-csv' class='tema-btn' style='font-size:12px; padding:4px 10px;'>" + icon("download", 14) + "Exportar Rutas CSV</button>" : "")
      + "</div>";

    if (!rutas.length) {
      h += vacio("No hay desplazamientos registrados para la fecha " + fechaCorta(fFecha) + ". Los puntos se capturan automáticamente en segundo plano cuando el operario interactúa con la aplicación en campo.");
    } else {
      rutas.forEach(function (r, idx) {
        var rolBadge = r.rol === "OWNER" ? "rojo" : (r.rol === "ADMIN" ? "ambar" : "verde");
        h += "<div class='card-operario-ruta'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;'>"
          + "<div><b style='font-size:16px;'>" + esc(r.usuario_nombre) + "</b> <span class='chip " + rolBadge + "' style='font-size:11px;'>" + esc(r.rol) + "</span></div>"
          + "<div style='font-size:12.5px; color:var(--texto-suave);'>"
          + icon("clock", 14) + "Horario: <b>" + esc(r.hora_inicio || "—") + "</b> a <b>" + esc(r.hora_fin || "—") + "</b> · " + icon("pin", 14) + "<b>" + r.total_puntos + " puntos GPS</b>"
          + "</div>"
          + "</div>";

        // Secuencia cronológica de potreros
        h += "<div style='font-size:12px; font-weight:600; color:var(--texto-suave); margin-bottom:4px;'>LÍNEA DE TIEMPO DE POTREROS VISITADOS:</div>";
        h += "<div class='timeline-rutas'>";
        if (!r.secuencia_potreros || !r.secuencia_potreros.length) {
          h += "<span style='font-size:12px; color:var(--texto-suave);'>Sin visitas a potreros registradas</span>";
        } else {
          r.secuencia_potreros.forEach(function (s, sIdx) {
            if (sIdx > 0) h += "<span class='chip-flecha'>" + icon("arrowRight", 12) + "</span>";
            h += "<span class='chip-ruta'>" + icon("pin", 12) + "<b>" + esc(s.hora) + "</b> " + icon("grass", 12) + esc(s.potrero) + "</span>";
          });
        }
        h += "</div>";

        // Detalle colapsable de puntos exactos
        var tablaId = "tabla-pts-" + idx;
        h += "<details style='margin-top:10px; font-size:13px;'>"
          + "<summary style='cursor:pointer; font-weight:600; color:var(--verde-marca); padding:4px 0;'>" + icon("search", 14) + "Ver desglose de coordenadas (" + (r.puntos ? r.puntos.length : 0) + " registros)</summary>"
          + "<div class='tabla-scroll' style='margin-top:8px;'>"
          + "<table id='" + tablaId + "'><tr><th>Hora</th><th>Potrero</th><th>Latitud</th><th>Longitud</th><th>Precisión</th><th>Evento</th><th>Google Maps</th></tr>";

        (r.puntos || []).forEach(function (pt) {
          var mapsUrl = "https://maps.google.com/?q=" + pt.lat + "," + pt.lon;
          var origen = pt.evento_origen || "interaccion";
          h += "<tr>"
            + "<td><b>" + esc(pt.hora) + "</b></td>"
            + "<td><b>" + esc(pt.potrero_nombre || "Área Externa") + "</b></td>"
            + "<td>" + Number(pt.lat).toFixed(6) + "</td>"
            + "<td>" + Number(pt.lon).toFixed(6) + "</td>"
            + "<td>±" + (pt.precision_m ? Math.round(pt.precision_m) + " m" : "—") + "</td>"
            + "<td><span class='chip gris' style='font-size:11px;'>" + esc(origen) + "</span></td>"
            + "<td><a href='" + esc(mapsUrl) + "' target='_blank' rel='noopener' class='chip azul' style='font-size:11px; text-decoration:none;'>" + icon("map", 12) + "Abrir Mapa</a></td>"
            + "</tr>";
        });
        h += "</table></div></details>";

        h += "</div>";
      });
    }

    // Sección de Rondas de Campo Manuales
    h += "<div class='card' style='margin-top:20px; padding:16px;'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>"
      + "<h4>" + icon("calendar", 16) + "Puntos de Ronda Manuales (" + rondas.length + ")</h4>"
      + (rondas.length ? "<button type='button' id='btn-exportar-rondas-csv' class='tema-btn' style='font-size:12px; padding:4px 10px;'>" + icon("download", 14) + "Exportar Rondas CSV</button>" : "")
      + "</div>";

    if (!rondas.length) {
      h += vacio("No hay rondas manuales registradas en esta fecha.");
    } else {
      h += "<div class='tabla-scroll'><table id='tabla-rondas'><tr><th>Hora</th><th>Potrero</th><th>Punto</th><th>Usuario</th><th>Notas</th></tr>";
      rondas.forEach(function (r) {
        h += "<tr><td><b>" + esc(r.hora || fechaCorta(r.fecha)) + "</b></td>"
          + "<td><b>" + esc(r.potrero_nombre || "—") + "</b></td>"
          + "<td><span class='chip verde'>" + esc(r.punto_control || "recorrido") + "</span></td>"
          + "<td>" + esc(r.usuario_nombre || "—") + "</td>"
          + "<td>" + esc(r.notas || "—") + "</td></tr>";
      });
      h += "</table></div>";
    }
    h += "</div>";

    return h;
  }

  function bindGps(d, fFecha) {
    fFecha = fFecha || _fechaFiltroRutas || new Date().toISOString().slice(0, 10);

    var btnRefrescar = document.getElementById("btn-refrescar-rutas");
    var inpFecha = document.getElementById("filtro-fecha-rutas");
    if (btnRefrescar && inpFecha) {
      btnRefrescar.addEventListener("click", function () {
        _fechaFiltroRutas = inpFecha.value;
        cargar(true);
      });
      inpFecha.addEventListener("change", function () {
        _fechaFiltroRutas = inpFecha.value;
        cargar(true);
      });
    }

    var btnPing = document.getElementById("btn-ping-manual-gps");
    if (btnPing) {
      btnPing.addEventListener("click", function () {
        if (!navigator.geolocation) {
          alert("Geolocalización no disponible en este dispositivo.");
          return;
        }
        btnPing.textContent = "Obteniendo GPS...";
        navigator.geolocation.getCurrentPosition(function (pos) {
          var lat = pos.coords.latitude;
          var lon = pos.coords.longitude;
          var acc = Math.round(pos.coords.accuracy || 0);
          fetch("/api/telemetria/ping", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              lat: lat,
              lon: lon,
              precision_m: acc,
              evento_origen: "prueba_manual_owner"
            })
          }).then(function (r) { return r.json(); })
            .then(function (res) {
              btnPing.textContent = "Posición Registrada";
              setTimeout(function () { cargar(false); }, 700);
            }).catch(function (err) {
              btnPing.textContent = "Error: " + err.message;
            });
        }, function (err) {
          btnPing.textContent = "" + err.message;
        }, { enableHighAccuracy: true, timeout: 10000 });
      });
    }

    var btnCsvRutas = document.getElementById("btn-exportar-rutas-csv");
    if (btnCsvRutas) {
      btnCsvRutas.addEventListener("click", function () {
        var lineas = [["Usuario", "Rol", "Fecha", "Hora", "Potrero", "Latitud", "Longitud", "Precision_m", "Evento_Origen"]];
        (d.rutas || []).forEach(function (r) {
          (r.puntos || []).forEach(function (p) {
            lineas.push([
              r.usuario_nombre || "",
              r.rol || "",
              p.fecha || fFecha,
              p.hora || "",
              p.potrero_nombre || "Área Externa",
              p.lat || "",
              p.lon || "",
              p.precision_m != null ? p.precision_m : "",
              p.evento_origen || ""
            ]);
          });
        });
        var csvContent = "\uFEFF" + lineas.map(function (row) {
          return row.map(function (val) {
            return '"' + String(val).replace(/"/g, '""') + '"';
          }).join(";");
        }).join("\r\n");
        var blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "rutas_telemetria_ja_" + fFecha + ".csv";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }

    var btnCsvRondas = document.getElementById("btn-exportar-rondas-csv");
    if (btnCsvRondas) {
      btnCsvRondas.addEventListener("click", function () {
        exportarTablaCSV("rondas_campo_" + fFecha, "#tabla-rondas");
      });
    }
  }


