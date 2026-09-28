  /* ---------- Modo Manga de Corral (Pesajes, Tratamientos Masivos, BLE) ---------- */
  var _sesionManga = [];
  function renderManga() {
    var h = "<h3>" + icon("corral") + "Manga de Corral — Pesajes y Lotes</h3>";
    h += "<div class='manga-tabs'>"
      + "<button type='button' class='manga-tab-btn act' data-mtab='pesaje'>" + icon("scale", 14) + "Pesaje Rápido & GMD</button>"
      + "<button type='button' class='manga-tab-btn' data-mtab='lote'>" + icon("syringe", 14) + "Tratamiento en Lote</button>"
      + "<button type='button' class='manga-tab-btn' data-mtab='ble'>" + icon("bluetooth", 14) + "Báscula / RFID BLE</button>"
      + "</div>";

    // Panel 1: Pesaje Rápido
    h += "<div id='manga-panel-pesaje'>";
    h += "<div class='manga-pesaje-box'>"
      + "<label style='font-size:13px; font-weight:600;'>Arete / Tag:</label>"
      + "<input id='manga-tag' class='manga-input-grande' placeholder='ej. 47' autocomplete='off' list='dl-tags' autofocus style='margin-bottom:12px;'>"
      + "<label style='font-size:13px; font-weight:600;'>Peso Actual (kg):</label>"
      + "<input id='manga-peso' type='number' step='0.5' inputmode='decimal' class='manga-input-grande' placeholder='0.0' style='color:var(--verde-marca); font-size:38px; margin-bottom:12px;'>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px;'>"
      + "<div style='flex:1; min-width:130px;'><label style='font-size:12px;'>Condición Corporal:</label>"
      + "<select id='manga-cc' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
      + "<option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0'>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0 (Gorda)</option></select></div>"
      + "<div style='flex:1; min-width:130px;'><label style='font-size:12px;'>Evento:</label>"
      + "<select id='manga-evento' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
      + "<option value='PESAJE'>Control Periódico</option><option value='DESTETE'>Destete</option><option value='ENTRADA'>Entrada / Compra</option><option value='VENTA'>Venta / Salida</option></select></div>"
      + "</div>"
      + "<button type='button' id='btn-manga-guardar-peso' class='btn-guardar-manga'>" + icon("save", 15) + "Guardar Pesaje (Enter)</button>"
      + "</div>";

    h += "<div id='manga-resultado-kpi' style='display:none;' class='manga-pesaje-box'></div>";

    h += "<h4>" + icon("chartBar") + "Historial de esta Sesión en Manga</h4>";
    h += "<div id='manga-historial-wrap'>" + renderTablaSesionManga() + "</div>";
    h += "</div>";

    // Panel 2: Tratamiento en Lote
    h += "<div id='manga-panel-lote' style='display:none;'>";
    h += "<div class='card' style='margin-bottom:14px;'>"
      + "<h4>" + icon("syringe") + "Aplicación Masiva de Tratamiento por Potrero / Lote</h4>"
      + "<p class='aviso'>Aplica automáticamente el tratamiento y los tiempos de retiro a todos los animales activos del potrero seleccionado.</p>"
      + "<div style='display:flex; flex-direction:column; gap:10px; margin-top:12px;'>"
      + "<label>Potrero a tratar: <input id='manga-lote-potrero' placeholder='ej. Guayabal' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label>O aretes individuales (opcional, separados por coma): <input id='manga-lote-tags' placeholder='ej. 47, JA26-6, 88' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<label>Tipo de tratamiento: <select id='manga-lote-tipo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='Desparasitante'>Desparasitante</option><option value='Vacuna'>Vacuna</option><option value='Vitaminas'>Vitaminas / Mineralizante</option><option value='Antibiótico'>Antibiótico</option><option value='Otro'>Otro</option></select></label>"
      + "<label>Fármaco / Producto: <input id='manga-lote-producto' placeholder='Nombre comercial (ej. Ivermectina 1%, Albendazol)' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:140px;'><label>Dosis: <input id='manga-lote-dosis' placeholder='ej. 1 ml / 50kg' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
      + "<div style='flex:1; min-width:140px;'><label>Vía: <select id='manga-lote-via' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='SC'>Subcutánea (SC)</option><option value='IM'>Intramuscular (IM)</option><option value='Oral'>Oral</option><option value='Pour-on'>Pour-on / Tópico</option><option value='IV'>Intravenosa (IV)</option></select></label></div>"
      + "</div>"
      + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:140px;'><label>Retiro Leche (días): <input type='number' id='manga-lote-ret-leche' value='0' min='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
      + "<div style='flex:1; min-width:140px;'><label>Retiro Carne (días): <input type='number' id='manga-lote-ret-carne' value='0' min='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
      + "</div>"
      + "<label>Diagnóstico / Motivo: <input id='manga-lote-diag' placeholder='ej. Control preventivo parásitos época seca' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
      + "<button type='button' id='btn-manga-guardar-lote' class='btn-guardar-manga' style='margin-top:10px; background:#1F6C9F;'>" + icon("syringe", 15) + "Aplicar Tratamiento en Lote</button>"
      + "</div>"
      + "</div>";
    h += "</div>";

    // Panel 3: BLE
    h += "<div id='manga-panel-ble' style='display:none;'>";
    h += "<div class='gps-box'>"
      + "<h4>" + icon("alert") + "Conexión Web Bluetooth a Báscula / RFID</h4>"
      + "<p class='aviso'>Permite recibir el peso o arete leído automáticamente desde básculas electrónicas (Tru-Test, Gallagher) o bastones RFID (Allflex) por Bluetooth BLE sin teclear.</p>"
      + "<button type='button' id='btn-manga-ble-conectar' class='btn-guardar-manga' style='max-width:320px; margin:14px auto;'>" + icon("bluetooth", 15) + "Conectar Dispositivo BLE</button>"
      + "<div id='manga-ble-estado' class='aviso' style='margin-top:14px;'>Estado: Desconectado.</div>"
      + "</div>";
    h += "</div>";

    return h;
  }

  function renderTablaSesionManga() {
    if (!_sesionManga || !_sesionManga.length) {
      return vacio("Aún no se han registrado pesajes en esta sesión de manga.");
    }
    var h = "<div class='tabla-scroll'><table><tr><th>Hora</th><th>Tag</th><th>Peso (kg)</th><th>GMD</th><th>Estado</th></tr>";
    _sesionManga.forEach(function (f) {
      var chipGmd = f.gmd != null && !isNaN(f.gmd)
        ? "<span class='chip " + (Number(f.gmd) >= 600 ? "verde" : Number(f.gmd) > 0 ? "ambar" : "rojo") + "'>" + (Number(f.gmd) > 0 ? "+" : "") + Number(f.gmd).toFixed(0) + " g/d</span>"
        : (f.gmd || "—");
      h += "<tr><td>" + esc(f.hora) + "</td><td><b>" + esc(f.tag) + "</b></td><td><b>" + esc(f.peso) + " kg</b></td><td>" + chipGmd + "</td><td>" + esc(f.estado) + "</td></tr>";
    });
    h += "</table></div>";
    return h;
  }

  function bindManga() {
    var tabs = qa(".manga-tab-btn");
    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        tabs.forEach(function (b) { b.classList.remove("act"); });
        btn.classList.add("act");
        var mtab = btn.getAttribute("data-mtab");
        var pPesaje = document.getElementById("manga-panel-pesaje");
        var pLote = document.getElementById("manga-panel-lote");
        var pBle = document.getElementById("manga-panel-ble");
        if (pPesaje) pPesaje.style.display = mtab === "pesaje" ? "block" : "none";
        if (pLote) pLote.style.display = mtab === "lote" ? "block" : "none";
        if (pBle) pBle.style.display = mtab === "ble" ? "block" : "none";
        if (mtab === "pesaje") {
          var inp = document.getElementById("manga-tag");
          if (inp) inp.focus();
        }
      });
    });

    var inpTag = document.getElementById("manga-tag");
    var inpPeso = document.getElementById("manga-peso");
    var btnGuardar = document.getElementById("btn-manga-guardar-peso");
    if (inpTag && inpPeso) {
      inpTag.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          inpPeso.focus();
        }
      });
      inpPeso.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          if (btnGuardar) btnGuardar.click();
        }
      });
    }

    if (btnGuardar) {
      btnGuardar.addEventListener("click", function () {
        var tag = (inpTag && inpTag.value || "").trim();
        var pesoStr = (inpPeso && inpPeso.value || "").trim();
        var cc = (q("#manga-cc") && q("#manga-cc").value) || null;
        var evento = (q("#manga-evento") && q("#manga-evento").value) || "PESAJE";

        if (!tag || !pesoStr) {
          alert("Debe escribir el arete/tag y el peso en kg.");
          return;
        }
        var peso = parseFloat(pesoStr);
        if (isNaN(peso) || peso <= 0) {
          // BLOQUE 4 (ráfaga): vibración corta de error + campo en rojo.
          if (navigator.vibrate) { try { navigator.vibrate([40, 40, 40]); } catch (eVibManga) { /* noop */ } }
          if (inpPeso) inpPeso.style.borderColor = "var(--color-rojo-txt)";
          alert("El peso debe ser un número válido mayor a 0.");
          return;
        }
        if (inpPeso) inpPeso.style.borderColor = "";

        var resBox = document.getElementById("manga-resultado-kpi");

        function procesarResultadoLocal(data) {
          enviarTelemetriaSilenciosa("pesaje_manga");
          // BLOQUE 4 (ráfaga): vibración larga de éxito. Solo se limpian tag
          // y peso (el resto del formulario se mantiene) y el cursor vuelve
          // al tag para pesar el siguiente animal sin tocar la pantalla.
          if (navigator.vibrate) { try { navigator.vibrate([80, 40, 80]); } catch (eVibOk) { /* noop */ } }
          var gmd = data.gmd_g_dia;
          var chipGmd = gmd != null && !isNaN(gmd)
            ? "<span class='chip " + (gmd >= 600 ? "verde" : gmd > 0 ? "ambar" : "rojo") + "'>" + (gmd > 0 ? "+" : "") + Number(gmd).toFixed(0) + " g/d</span>"
            : "<span class='chip gris'>Primer pesaje</span>";

          if (resBox) {
            resBox.style.display = "block";
            resBox.innerHTML = "<b>✅ Pesaje Registrado:</b> Animal <b>" + esc(tag) + "</b> — <b>" + peso + " kg</b><br>"
              + (data.peso_anterior != null
                ? "Anterior: <b>" + esc(data.peso_anterior) + " kg</b> (hace " + esc(data.dias_entre_pesajes) + " días) · GMD: " + chipGmd
                : "Primer pesaje registrado para este animal.");
          }

          _sesionManga.unshift({
            hora: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }),
            tag: tag,
            peso: peso,
            gmd: gmd,
            estado: "🟢 Guardado"
          });
          var wrap = document.getElementById("manga-historial-wrap");
          if (wrap) wrap.innerHTML = renderTablaSesionManga();

          if (inpPeso) inpPeso.value = "";
          if (inpTag) { inpTag.value = ""; inpTag.focus(); }
        }

        if (navigator.onLine === false) {
          encolarOffline("pesaje", { animal_tag: tag, peso_kg: peso, evento: evento, condicion_corporal: cc }).then(function () {
            if (navigator.vibrate) { try { navigator.vibrate([80, 40, 80]); } catch (eVibOff) { /* noop */ } }
            if (resBox) {
              resBox.style.display = "block";
              resBox.innerHTML = "<b>💾 Pesaje Guardado Offline:</b> Animal <b>" + esc(tag) + "</b> — <b>" + peso + " kg</b> (en cola para sincronizar al volver la señal)";
            }
            _sesionManga.unshift({
              hora: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }),
              tag: tag,
              peso: peso,
              gmd: "—",
              estado: "💾 Offline"
            });
            var wrap = document.getElementById("manga-historial-wrap");
            if (wrap) wrap.innerHTML = renderTablaSesionManga();
            if (inpPeso) inpPeso.value = "";
            if (inpTag) { inpTag.value = ""; inpTag.focus(); }
          });
          return;
        }

        fetch("/api/manga/pesaje", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tag: tag, peso_kg: peso, evento: evento, condicion_corporal: cc })
        }).then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        }).then(function (data) {
          if (data.ok) procesarResultadoLocal(data);
          else alert("Error: " + (data.error || "No se pudo registrar"));
        }).catch(function (err) {
          encolarOffline("pesaje", { animal_tag: tag, peso_kg: peso, evento: evento, condicion_corporal: cc }).then(function () {
            if (navigator.vibrate) { try { navigator.vibrate([80, 40, 80]); } catch (eVibOff2) { /* noop */ } }
            if (resBox) {
              resBox.style.display = "block";
              resBox.innerHTML = "<b>💾 Guardado Offline:</b> Animal <b>" + esc(tag) + "</b> (" + esc(err.message) + " — en cola local)";
            }
            _sesionManga.unshift({
              hora: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }),
              tag: tag,
              peso: peso,
              gmd: "—",
              estado: "💾 Offline"
            });
            var wrap = document.getElementById("manga-historial-wrap");
            if (wrap) wrap.innerHTML = renderTablaSesionManga();
            if (inpPeso) inpPeso.value = "";
            if (inpTag) { inpTag.value = ""; inpTag.focus(); }
          });
        });
      });
    }

    var btnLote = document.getElementById("btn-manga-guardar-lote");
    if (btnLote) {
      btnLote.addEventListener("click", function () {
        var pot = (q("#manga-lote-potrero") && q("#manga-lote-potrero").value || "").trim();
        var tagsTxt = (q("#manga-lote-tags") && q("#manga-lote-tags").value || "").trim();
        var prod = (q("#manga-lote-producto") && q("#manga-lote-producto").value || "").trim();
        var tipo = (q("#manga-lote-tipo") && q("#manga-lote-tipo").value) || "Tratamiento";
        var dosis = (q("#manga-lote-dosis") && q("#manga-lote-dosis").value) || "";
        var via = (q("#manga-lote-via") && q("#manga-lote-via").value) || "SC";
        var rLeche = parseInt(q("#manga-lote-ret-leche") && q("#manga-lote-ret-leche").value || 0, 10);
        var rCarne = parseInt(q("#manga-lote-ret-carne") && q("#manga-lote-ret-carne").value || 0, 10);
        var diag = (q("#manga-lote-diag") && q("#manga-lote-diag").value) || "";

        if (!prod) { alert("Debe especificar el fármaco o producto a aplicar."); return; }
        if (!pot && !tagsTxt) { alert("Debe indicar el potrero o la lista de tags."); return; }

        var payload = {
          producto: prod,
          potrero: pot,
          tipo: tipo,
          dosis: dosis,
          via: via,
          dias_retiro_leche: rLeche,
          dias_retiro_carne: rCarne,
          diagnostico: diag
        };
        if (tagsTxt) {
          payload.tags = tagsTxt.split(/[\s,;]+/).filter(Boolean);
        }

        if (!confirm("¿Desea aplicar '" + prod + "' a los animales de " + (pot ? "potrero " + pot : tagsTxt) + "?")) {
          return;
        }

        fetch("/api/manga/tratamiento_lote", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok) {
              alert("✅ Tratamiento aplicado a " + res.procesados + " animales con éxito.");
              if (q("#manga-lote-producto")) q("#manga-lote-producto").value = "";
              if (q("#manga-lote-tags")) q("#manga-lote-tags").value = "";
              actualizarBadges();
            } else {
              alert("Error: " + (res.error || "No se pudo aplicar"));
            }
          }).catch(function (err) { alert("Error de red: " + err.message); });
      });
    }

    var btnBle = document.getElementById("btn-manga-ble-conectar");
    if (btnBle) {
      btnBle.addEventListener("click", function () {
        var estado = document.getElementById("manga-ble-estado");
        if (!navigator.bluetooth) {
          if (estado) estado.innerHTML = "❌ Tu navegador no soporta Web Bluetooth.<br><small>Recomendado: Chrome o Edge en Android o PC con Bluetooth activo.</small>";
          return;
        }
        if (estado) estado.textContent = "🔍 Buscando báscula o bastón RFID Bluetooth...";
        navigator.bluetooth.requestDevice({
          acceptAllDevices: true,
          optionalServices: ["0000181d-0000-1000-8000-00805f9b34fb", "battery_service"]
        }).then(function (device) {
          if (estado) estado.innerHTML = "🟢 Conectado a <b>" + esc(device.name || "Dispositivo BLE") + "</b>.<br>Listo para recibir lecturas.";
        }).catch(function (err) {
          if (estado) estado.textContent = "Conexión BLE cancelada o no disponible (" + err.message + ").";
        });
      });
    }
  }

