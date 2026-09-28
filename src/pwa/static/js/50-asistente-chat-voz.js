  /* ---------- Asistente IA (Chat Natural) ---------- */
  function formatearMensajeChat(raw) {
    if (!raw) return "";
    var str = String(raw);

    // 1. Extraer bloques <pre>...</pre> para proteger su formateo monoespaciado
    var pres = [];
    str = str.replace(/<pre(?:\s+[^>]*)?>([\s\S]*?)<\/pre>/gi, function (_, contenido) {
      var dec = contenido
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&amp;/g, "&")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'");
      var seguro = esc(dec.trim());
      pres.push(
        "<div class='chat-pre-wrap'>" +
          "<button class='btn-pre-copy' type='button' title='Copiar tabla'>📋 Copiar</button>" +
          "<pre>" + seguro + "</pre>" +
        "</div>"
      );
      return "___PRE_BLOCK_" + (pres.length - 1) + "___";
    });

    // 2. Extraer bloques <code>...</code>
    var codes = [];
    str = str.replace(/<code(?:\s+[^>]*)?>([\s\S]*?)<\/code>/gi, function (_, contenido) {
      var dec = contenido
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&amp;/g, "&");
      codes.push("<code>" + esc(dec) + "</code>");
      return "___CODE_BLOCK_" + (codes.length - 1) + "___";
    });

    // 3. Extraer enlaces seguros <a href="...">...</a>
    var links = [];
    str = str.replace(/<a\s+href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, function (_, url, texto) {
      // Rutas internas "/x" sí; "//dominio" (protocol-relative) y "/\\" no.
      var esInterna = url.charAt(0) === "/" && url.charAt(1) !== "/" && url.charAt(1) !== "\\";
      var safeUrl = /^https?:\/\//i.test(url) || esInterna ? esc(url) : "#";
      links.push("<a href='" + safeUrl + "' target='_blank' rel='noopener noreferrer'>" + esc(texto) + "</a>");
      return "___LINK_BLOCK_" + (links.length - 1) + "___";
    });

    // 4. Proteger tags seguros de formato HTML: <b>, <strong>, <i>, <em>, <u>, <s>
    str = str
      .replace(/<\/?b>/gi, function (m) { return m.toLowerCase() === "<b>" ? "___B_OPEN___" : "___B_CLOSE___"; })
      .replace(/<\/?strong>/gi, function (m) { return m.toLowerCase() === "<strong>" ? "___B_OPEN___" : "___B_CLOSE___"; })
      .replace(/<\/?i>/gi, function (m) { return m.toLowerCase() === "<i>" ? "___I_OPEN___" : "___I_CLOSE___"; })
      .replace(/<\/?em>/gi, function (m) { return m.toLowerCase() === "<em>" ? "___I_OPEN___" : "___I_CLOSE___"; })
      .replace(/<\/?u>/gi, function (m) { return m.toLowerCase() === "<u>" ? "___U_OPEN___" : "___U_CLOSE___"; })
      .replace(/<\/?s>/gi, function (m) { return m.toLowerCase() === "<s>" ? "___S_OPEN___" : "___S_CLOSE___"; });

    // 5. Escapar todo el texto restante para neutralizar inyecciones XSS
    str = esc(str);

    // 6. Restaurar tags de formato seguro
    str = str
      .replace(/___B_OPEN___/g, "<b>")
      .replace(/___B_CLOSE___/g, "</b>")
      .replace(/___I_OPEN___/g, "<i>")
      .replace(/___I_CLOSE___/g, "</i>")
      .replace(/___U_OPEN___/g, "<u>")
      .replace(/___U_CLOSE___/g, "</u>")
      .replace(/___S_OPEN___/g, "<s>")
      .replace(/___S_CLOSE___/g, "</s>");

    // 7. Formato Markdown común (**negrita**, *cursiva*, `código`)
    str = str
      .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
      .replace(/(^|[^\w])\*([^*\n]+)\*([^\w]|$)/g, "$1<b>$2</b>$3")
      .replace(/(^|[^\w])_([^_\n]+)_([^\w]|$)/g, "$1<i>$2</i>$3")
      .replace(/`([^`\n]+)`/g, "<code>$1</code>");

    // 8. Convertir saltos de línea a <br> fuera de <pre>
    str = str.replace(/\n/g, "<br>");
    str = str.replace(/<br>(<div class='chat-pre-wrap'>)/g, "$1").replace(/(<\/div>)<br>/g, "$1");

    // 9. Restaurar enlaces, codes y pres protegidos
    str = str.replace(/___LINK_BLOCK_(\d+)___/g, function (_, idx) {
      return links[parseInt(idx, 10)] || "";
    });
    str = str.replace(/___CODE_BLOCK_(\d+)___/g, function (_, idx) {
      return codes[parseInt(idx, 10)] || "";
    });
    str = str.replace(/___PRE_BLOCK_(\d+)___/g, function (_, idx) {
      return pres[parseInt(idx, 10)] || "";
    });

    return str;
  }

  /* ---------- Chat Dock Flotante Expansible Estilo WhatsApp con Micrófono ---------- */
  var _chatMediaRecorder = null;
  var _chatAudioChunks = [];
  var _chatAudioTimerInterval = null;
  var _chatAudioSegundos = 0;

  function setupChatDock() {
    var dock = document.getElementById("chat-dock") || document.getElementById("modal-chat");
    var btnChat = document.getElementById("btn-chat");
    var btnBurbuja = document.getElementById("chat-dock-burbuja");
    var btnExpandir = document.getElementById("btn-expandir-chat");
    var btnColapsar = document.getElementById("btn-colapsar-chat");
    var btnCerrar = document.getElementById("btn-cerrar-chat");
    var btnLimpiar = document.getElementById("btn-limpiar-chat");
    var form = document.getElementById("form-chat");
    var inp = document.getElementById("chat-input");
    var hist = document.getElementById("chat-historial");
    var btnMic = document.getElementById("chat-btn-mic");
    var btnHeaderMic = document.getElementById("btn-mic");
    var barAudio = document.getElementById("chat-audio-grabando");
    var timerAudio = document.getElementById("chat-audio-timer");
    var btnCancelarAudio = document.getElementById("btn-cancelar-audio");
    var btnEnviarAudio = document.getElementById("btn-enviar-audio");
    var tabIA = document.getElementById("tab-chat-ia");
    var tabEquipo = document.getElementById("tab-chat-equipo");
    var histEquipo = document.getElementById("chat-historial-equipo");
    var dotEquipo = document.getElementById("equipo-dot");

    if (!dock) return;

    function expandirChat(enfocar) {
      dock.classList.remove("colapsado");
      dock.classList.add("expandido");
      if (dock.classList.contains("modal-overlay")) dock.style.display = "flex";
      if (equipoTabActiva) {
        if (histEquipo) histEquipo.scrollTop = histEquipo.scrollHeight;
        equipoMarcarVisto(equipoUltimoId);
      } else if (hist) {
        hist.scrollTop = hist.scrollHeight;
      }
      if (enfocar && inp) setTimeout(function () { inp.focus(); }, 120);
    }

    function colapsarChat() {
      dock.classList.remove("expandido");
      dock.classList.add("colapsado");
      detenerAudioGrabacion(true);
    }

    function toggleChat() {
      if (dock.classList.contains("expandido")) colapsarChat();
      else expandirChat(true);
    }

    /* ---------- Chat de Equipo (canal de avisos entre usuarios conectados) ---------- */
    var ROL_ICONO_EQUIPO = { OWNER: "👑", ADMIN: "🛡️", TRABAJADOR: "👷" };
    var LS_EQUIPO_VISTO = "ja_chat_equipo_visto_id";
    var equipoTabActiva = false;
    var equipoUltimoId = 0;
    var equipoUltimoVistoId = parseInt(localStorage.getItem(LS_EQUIPO_VISTO) || "0", 10) || 0;

    function horaCortaActual() {
      try {
        return new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
      } catch (e) {
        var d = new Date();
        var hh = d.getHours(), mm = d.getMinutes();
        return (hh < 10 ? "0" : "") + hh + ":" + (mm < 10 ? "0" : "") + mm;
      }
    }

    function formatearHora(iso) {
      if (!iso) return horaCortaActual();
      var s = String(iso).trim();
      var d = new Date(s.replace(" ", "T"));
      if (!isNaN(d.getTime())) {
        try {
          return d.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
        } catch (e) {
          var hh = d.getHours(), mm = d.getMinutes();
          return (hh < 10 ? "0" : "") + hh + ":" + (mm < 10 ? "0" : "") + mm;
        }
      }
      var m = s.match(/(\d{1,2}):(\d{2})/);
      if (m) return m[1] + ":" + m[2];
      return horaCortaActual();
    }

    function equipoHoraCorta(iso) {
      return formatearHora(iso);
    }

    function equipoMarcarVisto(id) {
      equipoUltimoVistoId = id;
      try { localStorage.setItem(LS_EQUIPO_VISTO, String(id)); } catch (e) {}
      if (dotEquipo) dotEquipo.classList.remove("on");
      var bd = btnBurbuja && btnBurbuja.querySelector(".nav-badge");
      if (bd) bd.classList.remove("on");
    }

    function equipoEncenderNoLeido() {
      if (dotEquipo) dotEquipo.classList.add("on");
      if (btnBurbuja) {
        var bd = btnBurbuja.querySelector(".nav-badge");
        if (!bd) {
          bd = document.createElement("span");
          bd.className = "nav-badge";
          btnBurbuja.appendChild(bd);
        }
        bd.classList.add("on");
      }
    }

    function renderMensajeEquipo(m) {
      if (!histEquipo) return;
      var yo = window.__usuarioActual || {};
      var esMio = yo.user_id != null && String(yo.user_id) === String(m.user_id);
      var puedeBorrar = esMio || yo.rol === "OWNER" || yo.rol === "ADMIN";
      var div = document.createElement("div");
      div.className = "chat-msg equipo " + (esMio ? "mio" : "otro");
      div.setAttribute("data-id", m.id);
      var html = "";
      if (!esMio) {
        var ic = ROL_ICONO_EQUIPO[m.rol] || "👤";
        html += "<div class='chat-msg-cabecera'>" + ic + " " + esc(m.nombre) + "<span class='chat-msg-rol'>" + esc(m.rol) + "</span></div>";
      }
      html += "<div class='chat-msg-texto'>" + esc(m.texto) + "</div>";
      html += "<div class='chat-msg-hora'>" + equipoHoraCorta(m.creado_en);
      if (puedeBorrar) html += " <span class='chat-msg-borrar' data-id='" + m.id + "' title='Borrar mensaje'>🗑</span>";
      html += "</div>";
      div.innerHTML = html;
      histEquipo.appendChild(div);
    }

    function cargarMensajesEquipo() {
      fetch("/api/mensajes-equipo?despues_de=" + equipoUltimoId + "&limite=50")
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d || !d.ok) return;
          var nuevos = d.mensajes || [];
          nuevos.forEach(renderMensajeEquipo);
          if (typeof d.ultimo_id === "number") equipoUltimoId = d.ultimo_id;
          if (nuevos.length) {
            if (histEquipo) histEquipo.scrollTop = histEquipo.scrollHeight;
            if (equipoTabActiva && dock.classList.contains("expandido")) {
              equipoMarcarVisto(equipoUltimoId);
            } else if (equipoUltimoId > equipoUltimoVistoId) {
              equipoEncenderNoLeido();
            }
          }
        }).catch(function () {});
    }

    function enviarMensajeEquipo(txt) {
      fetch("/api/mensajes-equipo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: txt })
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.ok && d.mensaje) {
            if (typeof d.mensaje.id === "number" && d.mensaje.id > equipoUltimoId) equipoUltimoId = d.mensaje.id;
            renderMensajeEquipo(d.mensaje);
            if (histEquipo) histEquipo.scrollTop = histEquipo.scrollHeight;
            equipoMarcarVisto(equipoUltimoId);
          } else if (d && d.error) {
            mostrarToast(d.error, "rojo");
          }
        }).catch(function (err) {
          mostrarToast("Error de conexión: " + err.message, "rojo");
        });
    }

    function activarPestanaChat(cual) {
      equipoTabActiva = (cual === "equipo");
      if (tabIA) tabIA.classList.toggle("activa", cual === "ia");
      if (tabEquipo) tabEquipo.classList.toggle("activa", cual === "equipo");
      if (hist) hist.style.display = cual === "ia" ? "" : "none";
      if (histEquipo) histEquipo.style.display = cual === "equipo" ? "" : "none";
      if (btnMic) btnMic.style.display = cual === "ia" ? "" : "none";
      if (inp) inp.placeholder = cual === "ia" ? "Pregunta algo o pulsa 🎙️..." : "Escribe un aviso para el equipo...";
      if (cual === "equipo") {
        equipoMarcarVisto(equipoUltimoId);
        if (histEquipo) histEquipo.scrollTop = histEquipo.scrollHeight;
      }
    }

    if (tabIA) tabIA.addEventListener("click", function () { activarPestanaChat("ia"); });
    if (tabEquipo) {
      tabEquipo.addEventListener("click", function () {
        activarPestanaChat("equipo");
        expandirChat(false);
      });
    }

    if (histEquipo) {
      histEquipo.addEventListener("click", function (e) {
        var btn = e.target && e.target.closest ? e.target.closest(".chat-msg-borrar") : null;
        if (!btn) return;
        var id = btn.getAttribute("data-id");
        if (!id) return;
        fetch("/api/mensajes-equipo/" + encodeURIComponent(id), { method: "DELETE" })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d && d.ok) {
              var fila = histEquipo.querySelector(".chat-msg[data-id='" + id + "']");
              if (fila) fila.remove();
            } else if (d && d.error) {
              mostrarToast(d.error, "rojo");
            }
          }).catch(function () {});
      });
    }

    // Se expone en window: la carga inicial se dispara después de conocer
    // al usuario actual (ver cargarUsuario().finally en el arranque de la
    // app), para que "esMio" ya pueda distinguir bien desde el primer
    // pintado; el setInterval de polling junto al heartbeat reutiliza la
    // misma función.
    window.__cargarMensajesEquipo = cargarMensajesEquipo;

    if (btnChat) btnChat.addEventListener("click", function () { expandirChat(true); });
    if (btnBurbuja) btnBurbuja.addEventListener("click", function () { expandirChat(true); });
    if (btnExpandir) btnExpandir.addEventListener("click", function (e) { e.preventDefault(); toggleChat(); });
    if (btnColapsar) btnColapsar.addEventListener("click", function (e) { e.preventDefault(); colapsarChat(); });
    if (btnCerrar) btnCerrar.addEventListener("click", function (e) { e.preventDefault(); colapsarChat(); });

    if (inp) {
      inp.addEventListener("focus", function () {
        if (dock.classList.contains("colapsado")) expandirChat(false);
      });
      inp.addEventListener("click", function () {
        if (dock.classList.contains("colapsado")) expandirChat(false);
      });
    }

    if (btnLimpiar && hist) {
      btnLimpiar.addEventListener("click", function () {
        hist.innerHTML = "<div class='chat-msg bot'><div class='chat-msg-texto'>Conversación reiniciada. Puedes hacerme cualquier consulta sobre el ganado o dictarme notas de voz 🎙️.</div><div class='chat-msg-hora'>" + horaCortaActual() + "</div></div>";
      });
    }

    // Copiar bloques de código/tablas en el chat
    if (hist) {
      hist.addEventListener("click", function (e) {
        var btn = e.target && e.target.closest ? e.target.closest(".btn-pre-copy") : null;
        if (!btn) return;
        var pre = btn.parentElement ? btn.parentElement.querySelector("pre") : null;
        if (pre && navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(pre.innerText || pre.textContent).then(function () {
            var old = btn.textContent;
            btn.textContent = "✓ Copiado";
            setTimeout(function () { btn.textContent = old; }, 1800);
          });
        }
      });
    }

    qa(".chip-sug", dock).forEach(function (chip) {
      chip.addEventListener("click", function () {
        var p = chip.getAttribute("data-p");
        if (inp) inp.value = p;
        if (form) form.dispatchEvent(new Event("submit"));
      });
    });

    // Envío de mensaje escrito
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var txt = (inp && inp.value || "").trim();
        if (!txt) return;

        if (equipoTabActiva) {
          if (inp) inp.value = "";
          enviarMensajeEquipo(txt);
          return;
        }

        expandirChat(false);

        var botPlaceholder;
        if (hist) {
          var hUser = horaCortaActual();
          hist.innerHTML += "<div class='chat-msg user'><div class='chat-msg-texto'>" + esc(txt) + "</div><div class='chat-msg-hora'>" + hUser + "</div></div>";
          botPlaceholder = document.createElement("div");
          botPlaceholder.className = "chat-msg bot";
          botPlaceholder.innerHTML = "<div class='chat-msg-texto'><i>Consultando información ganadera...</i></div>";
          hist.appendChild(botPlaceholder);
          hist.scrollTop = hist.scrollHeight;
        }

        if (inp) inp.value = "";

        fetch("/api/preguntar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pregunta: txt })
        }).then(function (r) { return r.json(); })
          .then(function (d) {
            var resp = d.respuesta || d.error || "Sin respuesta.";
            var formateada = formatearMensajeChat(resp);
            var hBot = horaCortaActual();
            if (botPlaceholder) botPlaceholder.innerHTML = "<div class='chat-msg-texto'>" + formateada + "</div><div class='chat-msg-hora'>" + hBot + "</div>";
            if (hist) hist.scrollTop = hist.scrollHeight;
          }).catch(function (err) {
            var hErr = horaCortaActual();
            if (botPlaceholder) botPlaceholder.innerHTML = "<div class='chat-msg-texto'>❌ Error de conexión: " + esc(err.message) + "</div><div class='chat-msg-hora'>" + hErr + "</div>";
          });
      });
    }

    // Grabación de Audio Estilo WhatsApp
    function detenerAudioGrabacion(descartar) {
      if (_chatAudioTimerInterval) {
        clearInterval(_chatAudioTimerInterval);
        _chatAudioTimerInterval = null;
      }
      _chatAudioSegundos = 0;
      if (barAudio) barAudio.style.display = "none";
      if (form) form.style.display = "";

      if (_chatMediaRecorder) {
        if (descartar) {
          _chatAudioChunks = [];
          try {
            if (_chatMediaRecorder.stream) {
              _chatMediaRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
            }
          } catch (e) {}
          try { _chatMediaRecorder.stop(); } catch (e) {}
          _chatMediaRecorder = null;
        }
      }
    }

    function iniciarGrabacionWhatsApp() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("Tu navegador no soporta captura de audio desde el micrófono.");
        return;
      }

      expandirChat(false);

      if (form) form.style.display = "none";
      if (barAudio) barAudio.style.display = "flex";
      _chatAudioSegundos = 0;
      if (timerAudio) timerAudio.textContent = "0:00";
      if (_chatAudioTimerInterval) clearInterval(_chatAudioTimerInterval);
      _chatAudioTimerInterval = setInterval(function () {
        _chatAudioSegundos++;
        var m = Math.floor(_chatAudioSegundos / 60);
        var s = _chatAudioSegundos % 60;
        if (timerAudio) timerAudio.textContent = m + ":" + (s < 10 ? "0" : "") + s;
      }, 1000);

      _chatAudioChunks = [];
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        _chatMediaRecorder = new MediaRecorder(stream);
        _chatMediaRecorder.ondataavailable = function (e) {
          if (e.data && e.data.size > 0) _chatAudioChunks.push(e.data);
        };
        _chatMediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
        };
        _chatMediaRecorder.start();
      }).catch(function (err) {
        detenerAudioGrabacion(true);
        alert("No fue posible acceder al micrófono: " + err.message);
      });
    }

    if (btnMic) btnMic.addEventListener("click", function (e) { e.preventDefault(); iniciarGrabacionWhatsApp(); });
    if (btnHeaderMic) {
      btnHeaderMic.addEventListener("click", function (e) {
        e.preventDefault();
        iniciarGrabacionWhatsApp();
      });
    }

    if (btnCancelarAudio) {
      btnCancelarAudio.addEventListener("click", function (e) {
        e.preventDefault();
        detenerAudioGrabacion(true);
      });
    }

    if (btnEnviarAudio) {
      btnEnviarAudio.addEventListener("click", function (e) {
        e.preventDefault();
        if (!_chatMediaRecorder || _chatMediaRecorder.state !== "recording") {
          detenerAudioGrabacion(true);
          return;
        }

        if (_chatAudioTimerInterval) {
          clearInterval(_chatAudioTimerInterval);
          _chatAudioTimerInterval = null;
        }

        // Crear placeholders en chat mientras procesa
        var hAudio = horaCortaActual();
        var userMsgPlaceholder = document.createElement("div");
        userMsgPlaceholder.className = "chat-msg user";
        userMsgPlaceholder.innerHTML = "<div class='chat-msg-texto'>🎙️ <i>Audio enviado (procesando nota de voz)...</i></div><div class='chat-msg-hora'>" + esc(hAudio) + "</div>";
        if (hist) {
          hist.appendChild(userMsgPlaceholder);
          hist.scrollTop = hist.scrollHeight;
        }

        var botPlaceholder = document.createElement("div");
        botPlaceholder.className = "chat-msg bot";
        botPlaceholder.innerHTML = "<div class='chat-msg-texto'><i>Transcribiendo con Whisper y consultando información ganadera...</i></div>";
        if (hist) {
          hist.appendChild(botPlaceholder);
          hist.scrollTop = hist.scrollHeight;
        }

        _chatMediaRecorder.addEventListener("stop", function () {
          if (!_chatAudioChunks.length) {
            userMsgPlaceholder.innerHTML = "<div class='chat-msg-texto'>🎙️ <i>Audio vacío.</i></div><div class='chat-msg-hora'>" + esc(hAudio) + "</div>";
            botPlaceholder.innerHTML = "<div class='chat-msg-texto'>⚠️ No se detectó sonido.</div><div class='chat-msg-hora'>" + esc(horaCortaActual()) + "</div>";
            detenerAudioGrabacion(true);
            return;
          }

          var blob = new Blob(_chatAudioChunks, { type: _chatMediaRecorder.mimeType || "audio/webm" });
          detenerAudioGrabacion(false);

          var fd = new FormData();
          fd.append("audio", blob, "nota_campo.webm");

          fetch("/api/voz", { method: "POST", body: fd })
            .then(function (r) { return r.json(); })
            .then(function (data) {
              var hBot = horaCortaActual();
              if (data.ok) {
                userMsgPlaceholder.innerHTML = "<div class='chat-msg-texto'>🎙️ <b>\"" + esc(data.transcripcion || "Nota de voz") + "\"</b></div><div class='chat-msg-hora'>" + esc(hAudio) + "</div>";
                botPlaceholder.innerHTML = "<div class='chat-msg-texto'>" + formatearMensajeChat(data.respuesta || "Registrado correctamente.") + "</div><div class='chat-msg-hora'>" + esc(hBot) + "</div>";
                actualizarBadges();
              } else {
                userMsgPlaceholder.innerHTML = "<div class='chat-msg-texto'>🎙️ <i>Nota de voz</i></div><div class='chat-msg-hora'>" + esc(hAudio) + "</div>";
                botPlaceholder.innerHTML = "<div class='chat-msg-texto'>⚠️ " + esc(data.error || "No se pudo procesar el audio.") + "</div><div class='chat-msg-hora'>" + esc(hBot) + "</div>";
              }
              if (hist) hist.scrollTop = hist.scrollHeight;
            }).catch(function (err) {
              var hBot = horaCortaActual();
              userMsgPlaceholder.innerHTML = "<div class='chat-msg-texto'>🎙️ <i>Nota de voz</i></div><div class='chat-msg-hora'>" + esc(hAudio) + "</div>";
              botPlaceholder.innerHTML = "<div class='chat-msg-texto'>❌ Error de conexión: " + esc(err.message) + "</div><div class='chat-msg-hora'>" + esc(hBot) + "</div>";
              if (hist) hist.scrollTop = hist.scrollHeight;
            });
        }, { once: true });

        try { _chatMediaRecorder.stop(); } catch (e) { detenerAudioGrabacion(true); }
      });
    }
  }
  var setupChatModal = setupChatDock;

  /* ---------- Dictado por Voz (Whisper) ---------- */
  var _mediaRecorder = null;
  var _audioChunks = [];
  function setupVozModal() {
    var btnMic = document.getElementById("btn-mic");
    var modal = document.getElementById("modal-voz");
    var btnCerrar = document.getElementById("btn-cerrar-voz");
    var btnAccion = document.getElementById("btn-voz-accion");
    var estado = document.getElementById("voz-estado");
    var resBox = document.getElementById("voz-resultado");
    var onda = document.getElementById("voz-onda");

    if (!btnMic || !modal) return;

    function detenerGrabacion() {
      if (_mediaRecorder && _mediaRecorder.state === "recording") {
        try { _mediaRecorder.stop(); } catch (e) { /* noop */ }
      }
    }

    btnMic.addEventListener("click", function () {
      modal.style.display = "flex";
      if (resBox) { resBox.style.display = "none"; resBox.innerHTML = ""; }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (estado) estado.textContent = "❌ Tu navegador no soporta grabación de micrófono.";
        if (btnAccion) btnAccion.style.display = "none";
        return;
      }
      if (estado) estado.textContent = "Iniciando micrófono...";
      if (btnAccion) { btnAccion.innerHTML = icon("square", 14) + "Detener y Enviar"; btnAccion.style.display = ""; }
      if (onda) onda.style.display = "block";

      _audioChunks = [];
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        _mediaRecorder = new MediaRecorder(stream);
        _mediaRecorder.ondataavailable = function (e) {
          if (e.data && e.data.size > 0) _audioChunks.push(e.data);
        };
        _mediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          if (!_audioChunks.length) {
            if (estado) estado.textContent = "No se capturó audio.";
            return;
          }
          if (estado) estado.textContent = "Transcribiendo con Whisper y procesando en el bot...";
          if (onda) onda.style.display = "none";

          var blob = new Blob(_audioChunks, { type: _mediaRecorder.mimeType || "audio/webm" });
          var fd = new FormData();
          fd.append("audio", blob, "nota_campo.webm");

          fetch("/api/voz", { method: "POST", body: fd })
            .then(function (r) { return r.json(); })
            .then(function (data) {
              if (resBox) resBox.style.display = "block";
              if (data.ok) {
                if (estado) estado.textContent = "Nota procesada con éxito.";
                resBox.innerHTML = "<b>Transcripción:</b> <i>\"" + esc(data.transcripcion) + "\"</i><br><br>"
                  + "<b>Respuesta del Bot:</b><br>" + formatearMensajeChat(data.respuesta || "Registrado.");
                if (btnAccion) btnAccion.innerHTML = icon("mic", 14) + "Grabar Otra Nota";
                actualizarBadges();
              } else {
                if (estado) estado.textContent = "⚠️ " + esc(data.error || "No se pudo procesar");
                if (btnAccion) btnAccion.textContent = "Reintentar";
              }
            }).catch(function (err) {
              if (estado) estado.textContent = "❌ Error de conexión: " + esc(err.message);
              if (btnAccion) btnAccion.textContent = "Reintentar";
            });
        };
        _mediaRecorder.start();
        if (estado) estado.textContent = "🔴 Grabando... hable ahora con claridad.";
      }).catch(function (err) {
        if (estado) estado.textContent = "❌ No se pudo acceder al micrófono: " + err.message;
        if (btnAccion) btnAccion.style.display = "none";
      });
    });

    if (btnCerrar) {
      btnCerrar.addEventListener("click", function () {
        detenerGrabacion();
        modal.style.display = "none";
      });
    }

    modal.addEventListener("click", function (e) {
      if (e.target === modal) {
        detenerGrabacion();
        modal.style.display = "none";
      }
    });

    if (btnAccion) {
      btnAccion.addEventListener("click", function () {
        if (_mediaRecorder && _mediaRecorder.state === "recording") {
          _mediaRecorder.stop();
        } else {
          btnMic.click();
        }
      });
    }

    if (resBox) {
      resBox.addEventListener("click", function (e) {
        var btn = e.target && e.target.closest ? e.target.closest(".btn-pre-copy") : null;
        if (!btn) return;
        var pre = btn.parentElement ? btn.parentElement.querySelector("pre") : null;
        if (pre && navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(pre.innerText || pre.textContent).then(function () {
            var old = btn.textContent;
            btn.textContent = "✓ Copiado";
            setTimeout(function () { btn.textContent = old; }, 1800);
          });
        }
      });
    }
  }

