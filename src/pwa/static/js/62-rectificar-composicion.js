  /* ---------- Subida y Actualización de Foto de Perfil de Animal ---------- */
  function iniciarCapturaFotoAnimal(tag) {
    window.iniciarCapturaFotoAnimal = iniciarCapturaFotoAnimal;
    if (!tag) {
      tag = (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
    }
    if (!tag) {
      if (typeof mostrarToast === "function") mostrarToast("No se especificó animal.", "ambar");
      return;
    }

    var inp = document.getElementById("input-foto-animal-directo");
    if (!inp) {
      inp = document.createElement("input");
      inp.type = "file";
      inp.id = "input-foto-animal-directo";
      inp.accept = "image/*";
      inp.capture = "environment";
      inp.style.display = "none";
      document.body.appendChild(inp);
    }

    inp.onchange = function () {
      var file = inp.files && inp.files[0];
      if (!file) return;

      var reader = new FileReader();
      reader.onload = function (ev) {
        var img = new Image();
        img.onload = function () {
          var maxDim = 1200;
          var width = img.width;
          var height = img.height;
          if (width > maxDim || height > maxDim) {
            if (width > height) {
              height = Math.round((height * maxDim) / width);
              width = maxDim;
            } else {
              width = Math.round((width * maxDim) / height);
              height = maxDim;
            }
          }

          var canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          var ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, width, height);

          var compressedB64 = canvas.toDataURL("image/jpeg", 0.84);
          var tamKb = Math.round((compressedB64.length * 3) / 4 / 1024);

          inp.value = "";
          mostrarModalSubirFotoAnimal(tag, {
            base64: compressedB64,
            nombre: file.name || ("foto_" + tag + ".jpg"),
            tam_kb: tamKb,
            ancho: width,
            alto: height
          });
        };
        img.src = ev.target.result;
      };
      reader.readAsDataURL(file);
    };

    inp.click();
  }
  window.iniciarCapturaFotoAnimal = iniciarCapturaFotoAnimal;

  function mostrarModalSubirFotoAnimal(tag, fotoData) {
    window.mostrarModalSubirFotoAnimal = mostrarModalSubirFotoAnimal;
    var overlay = document.getElementById("subir-foto-animal-modal");
    if (overlay) overlay.remove();

    var html = "<div id='subir-foto-animal-modal' class='modal-overlay' style='display:flex; align-items:center; justify-content:center; z-index:1050;'>"
      + "<div class='modal-contenido' style='max-width:440px; width:92%; max-height:92vh; overflow-y:auto;'>"
      + "<div class='modal-header' style='display:flex; justify-content:space-between; align-items:center; padding:12px 16px; border-bottom:1px solid var(--borde);'>"
      + "<b style='display:inline-flex; align-items:center; gap:6px; font-size:15px;'>" + icon("camera", 17) + "Foto de Perfil · Animal " + esc(tag) + "</b>"
      + "<button type='button' class='modal-cerrar' id='btn-cerrar-foto-modal' style='background:none; border:none; font-size:18px; cursor:pointer;'>✕</button>"
      + "</div>"
      + "<form id='form-subir-foto-animal' style='padding:16px; display:flex; flex-direction:column; gap:12px;'>"
      + "<div style='text-align:center; background:var(--fondo); border:1px solid var(--borde); border-radius:8px; padding:10px;'>"
      + "<img src='" + fotoData.base64 + "' alt='Vista previa foto " + esc(tag) + "' style='max-height:220px; max-width:100%; border-radius:6px; object-fit:cover; display:block; margin:0 auto; box-shadow:0 2px 8px rgba(0,0,0,0.15);'>"
      + "<div style='font-size:11.5px; color:var(--texto-suave); margin-top:8px; display:flex; justify-content:center; align-items:center; gap:8px; flex-wrap:wrap;'>"
      + "<span class='chip verde' style='font-size:10.5px;'>✓ Optimizada (" + fotoData.tam_kb + " KB)</span>"
      + "<span>" + fotoData.ancho + " × " + fotoData.alto + " px</span>"
      + "</div>"
      + "</div>"
      + "<label style='display:block; font-size:12.5px; font-weight:600;'>Descripción / Nota (opcional)"
      + "<input id='inp-foto-caption' value='Foto de perfil · " + esc(tag) + "' maxlength='120' style='width:100%; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); margin-top:3px; box-sizing:border-box;'>"
      + "</label>"
      + "<p id='foto-form-error' class='aviso' style='display:none; color:var(--color-rojo-txt); background:var(--color-rojo-bg); padding:8px 10px; border-radius:6px;'></p>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:4px; flex-wrap:wrap;'>"
      + "<button type='button' id='btn-otra-foto' class='tema-btn' style='font-size:12px; padding:8px 12px; display:inline-flex; align-items:center; gap:4px;'>"
      + icon("camera", 13) + "Tomar otra</button>"
      + "<div style='display:flex; gap:8px;'>"
      + "<button type='button' id='btn-cancelar-foto' class='tema-btn' style='font-size:12px; padding:8px 12px;'>Cancelar</button>"
      + "<button type='submit' id='btn-submit-foto' class='tema-btn' style='font-size:12px; padding:8px 14px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; box-shadow:0 1px 3px rgba(0,0,0,0.2);'>"
      + icon("check", 14) + "<span id='btn-submit-foto-txt'>Guardar Foto</span></button>"
      + "</div>"
      + "</div>"
      + "</form>"
      + "</div>"
      + "</div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("subir-foto-animal-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-foto-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    var btnCanc = document.getElementById("btn-cancelar-foto");
    if (btnCanc) btnCanc.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

    var btnOtra = document.getElementById("btn-otra-foto");
    if (btnOtra) {
      btnOtra.addEventListener("click", function () {
        cerrar();
        iniciarCapturaFotoAnimal(tag);
      });
    }

    var form = document.getElementById("form-subir-foto-animal");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var capEl = document.getElementById("inp-foto-caption");
      var caption = capEl ? capEl.value.trim() : "";
      var errEl = document.getElementById("foto-form-error");
      var btnSubmit = document.getElementById("btn-submit-foto");
      var btnTxt = document.getElementById("btn-submit-foto-txt");

      if (errEl) { errEl.style.display = "none"; errEl.textContent = ""; }
      if (btnSubmit) { btnSubmit.disabled = true; }
      if (btnTxt) { btnTxt.textContent = "Guardando..."; }

      fetch("/api/animal/" + encodeURIComponent(tag) + "/foto", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          foto_base64: fotoData.base64,
          caption: caption || ("Foto de perfil · " + tag)
        })
      }).then(function (r) {
        return r.json().then(function (d) { return { status: r.status, body: d }; });
      }).then(function (res) {
        if (res.status === 200 && res.body.ok) {
          cerrar();
          if (typeof mostrarToast === "function") {
            mostrarToast("✓ " + (res.body.mensaje || "Foto de perfil actualizada con éxito."), "verde");
          }
          try {
            if (navigator && navigator.vibrate) navigator.vibrate([35]);
          } catch (eVib) {}

          var nuevaUrl = res.body.url;
          var hoy = new Date().toISOString().slice(0, 10);
          var nuevaFotoObj = { url: nuevaUrl, caption: caption, fecha: hoy };

          if (window.__ultimaFicha && String(window.__ultimaFicha.tag).toUpperCase() === String(tag).toUpperCase()) {
            if (!Array.isArray(window.__ultimaFicha.fotos)) {
              window.__ultimaFicha.fotos = [];
            }
            window.__ultimaFicha.fotos.unshift(nuevaFotoObj);
          }

          // Actualizar avatar en vivo en el DOM
          var avatarWrap = document.querySelector(".ficha-avatar-wrap");
          if (avatarWrap) {
            avatarWrap.innerHTML = "<div class='foto-card-mini' title='Toca para agrandar' style='cursor:zoom-in; position:relative; border-radius:8px; overflow:hidden;'>"
              + "<img class='avatar zoomable-img' src='" + esc(nuevaUrl) + "' alt='Foto principal " + esc(tag) + "' style='width:64px; height:64px; border-radius:8px; object-fit:cover; display:block;' data-onerror-hide='parent'>"
              + "<div style='position:absolute; bottom:2px; right:2px; background:rgba(0,0,0,0.65); border-radius:3px; padding:2px 3px; color:#fff; display:flex; align-items:center; pointer-events:none;'>" + icon("search", 10) + "</div>"
              + "</div>";
          }

          // Actualizar galería de fotos en pestaña General si está visible
          var fotosWrap = document.querySelector(".fotos-wrap");
          if (fotosWrap) {
            var nuevaCardHtml = "<div class='foto-card' title='Toca para agrandar imagen'>"
              + "<img class='zoomable-img' src='" + esc(nuevaUrl) + "' alt='Foto nueva · " + esc(tag) + "' loading='lazy' style='max-height:175px; width:auto; border-radius:8px; object-fit:cover; display:block;' data-onerror-hide='parent'>"
              + "<div class='zoom-hint'>" + icon("search", 12) + "Agrandar</div>"
              + "</div>";
            fotosWrap.insertAdjacentHTML("afterbegin", nuevaCardHtml);
          }
        } else {
          if (btnSubmit) btnSubmit.disabled = false;
          if (btnTxt) btnTxt.textContent = "Guardar Foto";
          if (errEl) {
            errEl.textContent = "❌ " + (res.body.error || "No se pudo guardar la foto.");
            errEl.style.display = "block";
          }
        }
      }).catch(function (err) {
        if (btnSubmit) btnSubmit.disabled = false;
        if (btnTxt) btnTxt.textContent = "Guardar Foto";
        if (errEl) {
          errEl.textContent = "❌ Error de conexión: " + (err.message || err);
          errEl.style.display = "block";
        }
      });
    });
  }
  window.mostrarModalSubirFotoAnimal = mostrarModalSubirFotoAnimal;

  function mostrarModalRectificarTag(tagActual) {
    window.mostrarModalRectificarTag = mostrarModalRectificarTag;
    if (!tagActual) {
      tagActual = (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
    }
    var overlay = document.getElementById("rectificar-tag-modal");
    if (overlay) overlay.remove();

    var html = "<div id='rectificar-tag-modal' class='modal-overlay' style='display:flex; align-items:center; justify-content:center;'>"
      + "<div class='modal-contenido' style='max-width:440px; width:92%;'>"
      + "<div class='modal-header'>"
      + "<b style='display:inline-flex; align-items:center; gap:6px;'>" + icon("tag", 16) + "Rectificar Chapeta / Número</b>"
      + "<button type='button' class='modal-cerrar' id='btn-cerrar-rect-modal'>✕</button>"
      + "</div>"
      + "<form id='form-rectificar-tag' style='padding:16px; display:flex; flex-direction:column; gap:12px;'>"
      + "<div class='aviso' style='background:var(--color-ambar-bg); color:var(--color-ambar-txt); border:1px solid var(--color-ambar-txt); border-radius:8px; padding:10px 12px; font-size:12px; line-height:1.4;'>"
      + "👑 <b>Exclusivo Propietario (OWNER)</b><br>"
      + "Utilice este proceso si en campo leyeron o anotaron mal la chapeta (ej. se registró como <b>" + esc(tagActual) + "</b> pero la chapeta real era otra). Todo el historial de eventos se conservará."
      + "</div>"
      + "<label style='display:block; font-size:12.5px; font-weight:600;'>Chapeta / Arete Actual"
      + "<input id='rect-tag-actual' value='" + esc(tagActual) + "' disabled style='width:100%; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); background:var(--fondo); font-weight:700; margin-top:3px; box-sizing:border-box;'>"
      + "</label>"
      + "<label style='display:block; font-size:12.5px; font-weight:600;'>Nueva Chapeta / Arete Correcto *"
      + "<input id='rect-tag-nuevo' placeholder='ej. JA88 o 47' required autofocus style='width:100%; padding:9px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:700; margin-top:3px; text-transform:uppercase; box-sizing:border-box;'>"
      + "</label>"
      + "<div id='rect-box-fusion' style='display:none; background:var(--color-rojo-bg); color:var(--color-rojo-txt); border:1px solid var(--color-rojo-txt); border-radius:8px; padding:10px 12px; font-size:12px; line-height:1.4;'>"
      + "<div id='rect-fusion-mensaje' style='margin-bottom:8px; font-weight:600;'></div>"
      + "<label style='display:flex; align-items:flex-start; gap:8px; font-size:12px; cursor:pointer; font-weight:600;'>"
      + "<input type='checkbox' id='chk-rect-fusion' style='margin-top:2px;'>"
      + "<span>Confirmar fusión: transferir todos los eventos hacia el animal existente y retirar el registro erróneo.</span>"
      + "</label>"
      + "</div>"
      + "<p id='rect-form-error' class='aviso' style='display:none;'></p>"
      + "<div style='display:flex; justify-content:flex-end; gap:8px; margin-top:6px;'>"
      + "<button type='button' id='btn-cancelar-rect' class='tema-btn' style='padding:8px 14px;'>Cancelar</button>"
      + "<button type='submit' id='btn-submit-rect' class='tema-btn' style='padding:8px 16px; background:var(--color-ambar-txt); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:6px;'>"
      + icon("check", 14) + "<span id='rect-btn-txt'>Rectificar Chapeta</span>"
      + "</button>"
      + "</div>"
      + "</form>"
      + "</div>"
      + "</div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("rectificar-tag-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-rect-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    var btnCanc = document.getElementById("btn-cancelar-rect");
    if (btnCanc) btnCanc.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

    var form = document.getElementById("form-rectificar-tag");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var tagAct = (document.getElementById("rect-tag-actual").value || "").trim();
      var tagNv = (document.getElementById("rect-tag-nuevo").value || "").trim();
      var chkFusion = document.getElementById("chk-rect-fusion");
      var fusionar = chkFusion ? chkFusion.checked : false;
      var errEl = document.getElementById("rect-form-error");
      var boxFusion = document.getElementById("rect-box-fusion");
      var msgFusion = document.getElementById("rect-fusion-mensaje");
      var btnTxt = document.getElementById("rect-btn-txt");
      if (errEl) { errEl.style.display = "none"; errEl.textContent = ""; }

      if (!tagNv) return;
      if (tagAct.toUpperCase() === tagNv.toUpperCase()) {
        if (errEl) { errEl.textContent = "❌ El nuevo número es idéntico al actual."; errEl.style.display = "block"; }
        return;
      }

      fetch("/api/animal/rectificar-tag", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tag_actual: tagAct,
          tag_nuevo: tagNv,
          fusionar_si_existe: fusionar
        })
      }).then(function (r) {
        return r.json().then(function (d) { return { status: r.status, body: d }; });
      }).then(function (res) {
        if (res.status === 200 && res.body.ok) {
          cerrar();
          mostrarToast(res.body.mensaje || "Chapeta rectificada con éxito.", "verde");
          var destino = document.getElementById("ficha") || vista;
          abrirFicha(tagNv, destino, true);
          if (typeof irAVista === "function" && actual !== "ficha") irAVista("ficha");
        } else if (res.status === 409 && res.body.requiere_confirmacion_fusion) {
          if (boxFusion && msgFusion) {
            boxFusion.style.display = "block";
            msgFusion.innerHTML = "⚠️ " + esc(res.body.mensaje);
            if (btnTxt) btnTxt.textContent = "Confirmar Fusión y Rectificar";
          }
        } else {
          if (errEl) {
            errEl.textContent = "❌ " + (res.body.error || "No se pudo rectificar el arete.");
            errEl.style.display = "block";
          }
        }
      }).catch(function (err) {
        if (errEl) {
          errEl.textContent = "❌ Error de conexión: " + (err.message || err);
          errEl.style.display = "block";
        }
      });
    });
  }

  function porcentajeAFraccionGanadera(pct) {
    if (pct === null || pct === undefined || isNaN(pct)) return "S/D";
    var p = Number(pct);
    if (p <= 0) return "0%";
    if (p >= 99.5) return "Puro";
    if (p >= 96.5) return "Puro por Cruce (PC)";
    var tabla = [
      [100.0, "Puro"],
      [96.875, "Puro por Cruce (PC)"],
      [93.75, "15/16"],
      [87.5, "7/8"],
      [81.25, "13/16"],
      [75.0, "3/4"],
      [68.75, "11/16"],
      [66.667, "2/3"],
      [62.5, "5/8"],
      [56.25, "9/16"],
      [50.0, "1/2"],
      [43.75, "7/16"],
      [37.5, "3/8"],
      [33.333, "1/3"],
      [31.25, "5/16"],
      [25.0, "1/4"],
      [18.75, "3/16"],
      [12.5, "1/8"],
      [6.25, "1/16"],
      [3.125, "1/32"]
    ];
    for (var i = 0; i < tabla.length; i++) {
      if (Math.abs(p - tabla[i][0]) <= 0.6) {
        return tabla[i][1];
      }
    }
    if (Math.abs(p - Math.round(p)) < 0.05) return Math.round(p) + "%";
    return p.toFixed(1) + "%";
  }

  var COLORES_RAZA = {
    "Ayrshire": "#dc2626", // Rojo teja / carmín lechero característico de Ayrshire
    "Holstein Rojo": "#b91c1c", // Carmesí oscuro
    "Holstein": "#2563eb", // Azul royal / eléctrico
    "Gyr": "#16a34a", // Verde esmeralda vivo
    "Girolando": "#0891b2", // Turquesa / Cyan
    "Gyrolando": "#0891b2",
    "Brahman": "#475569", // Pizarra cebú
    "Cebú Comercial": "#d97706", // Ámbar cálido / ocre
    "Cebú": "#d97706",
    "Guzerá": "#7c3aed", // Púrpura / violeta
    "Nelore": "#4f46e5", // Índigo
    "Pardo Suizo": "#92400e", // Café / bronce
    "Jersey": "#ea580c", // Naranja brillante
    "Simmental": "#e11d48", // Rosa carmín
    "Simbrah": "#f59e0b", // Ámbar dorado
    "Senepol": "#c026d3", // Fucsia
    "Romosinuano": "#ca8a04", // Mostaza
    "Blanco Orejinegro (BON)": "#0d9488", // Teal
    "Costeño con Cuernos (CCC)": "#b45309", // Canela
    "Sanmartinero": "#78350f", // Café oscuro
    "Hartón del Valle": "#854d0e", // Ocre
    "Brangus": "#1e293b", // Negro azulado
    "Angus": "#0f172a", // Negro azabache
    "Charolais": "#94a3b8", // Crema plateado
    "Normando": "#65a30d", // Verde oliva
    "Hereford": "#be123c", // Rojo rubí
    "Shorthorn": "#9333ea", // Morado
    "Velásquez": "#854d0e",
    "Montbéliarde": "#b91c1c",
    "Mestizo": "#64748b",
    "Criollo": "#78716c"
  };
  var PALETA_RESPALDO = [
    "#dc2626", "#2563eb", "#16a34a", "#d97706", "#7c3aed",
    "#0891b2", "#ea580c", "#4f46e5", "#92400e", "#e11d48",
    "#0d9488", "#ca8a04", "#475569", "#b45309", "#c026d3"
  ];
  function colorDeRaza(raza, idx) {
    if (!raza) return PALETA_RESPALDO[(idx || 0) % PALETA_RESPALDO.length];
    var rLower = raza.toLowerCase().trim();
    if (rLower.indexOf("ayrshire") !== -1) return "#dc2626";
    if (rLower.indexOf("holstein rojo") !== -1 || rLower.indexOf("holstein r") !== -1) return "#b91c1c";
    if (rLower.indexOf("holstein") !== -1) return "#2563eb";
    if (rLower.indexOf("gyr") !== -1) return "#16a34a";
    if (rLower.indexOf("girolando") !== -1 || rLower.indexOf("gyrolando") !== -1) return "#0891b2";
    if (rLower.indexOf("guzer") !== -1) return "#7c3aed";
    if (rLower.indexOf("nelore") !== -1) return "#4f46e5";
    if (rLower.indexOf("ceb") !== -1) return "#d97706";
    if (rLower.indexOf("jersey") !== -1) return "#ea580c";
    if (rLower.indexOf("pardo") !== -1) return "#92400e";
    if (rLower.indexOf("brahman") !== -1) return "#475569";
    if (rLower.indexOf("bon") !== -1 || rLower.indexOf("orejinegro") !== -1) return "#0d9488";
    if (rLower.indexOf("normand") !== -1) return "#65a30d";
    if (rLower.indexOf("simmental") !== -1) return "#e11d48";
    if (rLower.indexOf("simbrah") !== -1) return "#f59e0b";
    if (rLower.indexOf("hereford") !== -1) return "#be123c";
    if (rLower.indexOf("shorthorn") !== -1 || rLower.indexOf("shorton") !== -1) return "#9333ea";
    for (var k in COLORES_RAZA) {
      if (rLower.indexOf(k.toLowerCase()) !== -1) return COLORES_RAZA[k];
    }
    return PALETA_RESPALDO[(idx || 0) % PALETA_RESPALDO.length];
  }

  function mostrarModalComposicionRacial(tagActual, compPrevia) {
    window.mostrarModalComposicionRacial = mostrarModalComposicionRacial;
    if (!tagActual) {
      tagActual = (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
    }
    if (!tagActual) return;

    var overlay = document.getElementById("comp-racial-modal");
    if (overlay) overlay.remove();

    var iniciales = [];
    if (Array.isArray(compPrevia) && compPrevia.length) {
      iniciales = JSON.parse(JSON.stringify(compPrevia));
    } else if (window.__ultimaFicha && window.__ultimaFicha.tag === tagActual && Array.isArray(window.__ultimaFicha.composicion_racial) && window.__ultimaFicha.composicion_racial.length) {
      iniciales = JSON.parse(JSON.stringify(window.__ultimaFicha.composicion_racial));
    } else if (window.__ultimaFicha && window.__ultimaFicha.tag === tagActual && window.__ultimaFicha.raza) {
      iniciales = [{ raza: window.__ultimaFicha.raza, porcentaje: 100.0 }];
    } else {
      iniciales = [{ raza: "Brahman", porcentaje: 50.0 }, { raza: "Romosinuano", porcentaje: 50.0 }];
    }

    var html = "<div id='comp-racial-modal' class='modal-overlay' style='display:flex; align-items:center; justify-content:center;'>"
      + "<div class='modal-contenido' style='max-width:480px; width:94%; max-height:85vh; display:flex; flex-direction:column;'>"
      + "<div class='modal-header'>"
      + "<b style='display:inline-flex; align-items:center; gap:6px;'>" + icon("dna", 16) + "Composición Genética · Arete " + esc(tagActual) + "</b>"
      + "<button type='button' class='modal-cerrar' id='btn-cerrar-comp-modal'>✕</button>"
      + "</div>"
      + "<form id='form-comp-racial' style='padding:16px; display:flex; flex-direction:column; gap:12px; overflow-y:auto; flex:1;'>"
      + "<div class='aviso' style='font-size:12.5px; line-height:1.4; margin:0;'>"
      + "🧬 <b>Ingreso multi-raza & cruces zootécnicos</b><br>"
      + "Seleccione las razas del animal e ingrese los porcentajes. El sistema traducirá automáticamente a fracciones estándar (1/2, 3/4, 7/8, PC). La suma total debe ser <b>100%</b>."
      + "</div>"
      + "<datalist id='dl-catalogo-razas'></datalist>"
      + "<div id='comp-filas-wrap' style='display:flex; flex-direction:column; gap:8px;'></div>"
      + "<div>"
      + "<button type='button' id='btn-add-raza-fila' class='tema-btn' style='font-size:12px; padding:6px 12px; background:rgba(34,197,94,0.1); color:var(--verde-marca); border:1px dashed var(--verde-marca); border-radius:6px; font-weight:700; cursor:pointer; display:inline-flex; align-items:center; gap:6px;'>"
      + icon("plus", 13) + "Añadir Raza"
      + "</button>"
      + "</div>"
      + "<div id='comp-totales-bar' style='padding:10px 12px; border-radius:8px; border:1px solid var(--borde); background:var(--superficie); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
      + "<div id='comp-suma-badge'></div>"
      + "<div id='comp-resumen-preview' style='font-size:12px; color:var(--texto-suave); font-weight:600;'></div>"
      + "</div>"
      + "<p id='comp-form-error' class='aviso' style='display:none; color:var(--color-rojo-txt);'></p>"
      + "<div style='display:flex; justify-content:flex-end; gap:8px; margin-top:4px;'>"
      + "<button type='button' id='btn-cancelar-comp' class='tema-btn' style='padding:8px 14px;'>Cancelar</button>"
      + "<button type='submit' id='btn-guardar-comp' class='tema-btn' style='padding:8px 16px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:6px;'>"
      + icon("check", 14) + "Guardar Composición"
      + "</button>"
      + "</div>"
      + "</form>"
      + "</div>"
      + "</div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("comp-racial-modal");
    function cerrar() { if (ov) ov.remove(); }
    var btnC = document.getElementById("btn-cerrar-comp-modal");
    if (btnC) btnC.addEventListener("click", cerrar);
    var btnCanc = document.getElementById("btn-cancelar-comp");
    if (btnCanc) btnCanc.addEventListener("click", cerrar);
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrar(); });

    var dl = document.getElementById("dl-catalogo-razas");
    fetchJSON("/api/genetica/catalogo-razas", function (res) {
      if (res && res.razas && dl) {
        dl.innerHTML = res.razas.map(function (r) {
          return "<option value='" + esc(r) + "'>";
        }).join("");
      }
    });

    var filasWrap = document.getElementById("comp-filas-wrap");
    var sumaBadge = document.getElementById("comp-suma-badge");
    var resumenPrev = document.getElementById("comp-resumen-preview");
    var errEl = document.getElementById("comp-form-error");

    function recalcularTotales() {
      var inputsPct = filasWrap.querySelectorAll(".comp-pct-input");
      var inputsRaza = filasWrap.querySelectorAll(".comp-raza-input");
      var suma = 0;
      var partesResumen = [];

      for (var i = 0; i < inputsPct.length; i++) {
        var v = parseFloat(inputsPct[i].value) || 0;
        suma += v;
        var rVal = (inputsRaza[i] && inputsRaza[i].value.trim()) || "Sin Raza";
        var badgeF = inputsPct[i].closest(".comp-fila").querySelector(".comp-frac-badge");
        var fr = porcentajeAFraccionGanadera(v);
        if (badgeF) {
          if (v <= 0) {
            badgeF.textContent = "0%";
            badgeF.className = "comp-frac-badge chip gris";
          } else if (fr && fr.indexOf("%") === -1 && fr !== "S/D") {
            badgeF.textContent = v + "% (" + fr + ")";
            badgeF.className = "comp-frac-badge chip verde";
          } else {
            badgeF.textContent = v + "%";
            badgeF.className = "comp-frac-badge chip verde";
          }
        }
        if (v > 0) {
          var fCorta = (fr && fr.indexOf("%") === -1 && fr !== "S/D") ? fr : (v + "%");
          if (fCorta.indexOf("1/2") !== -1) fCorta = "1/2";
          else if (fCorta.indexOf("PC") !== -1 || fCorta.indexOf("Puro por Cruce") !== -1) fCorta = "PC";
          partesResumen.push(fCorta + " " + rVal);
        }
      }

      suma = Math.round(suma * 100) / 100;
      if (Math.abs(suma - 100) <= 0.2) {
        sumaBadge.innerHTML = "<span class='chip verde' style='font-size:12.5px; font-weight:700;'>Suma: 100% ✅</span>";
      } else if (suma < 100) {
        var falta = Math.round((100 - suma) * 100) / 100;
        sumaBadge.innerHTML = "<span class='chip ambar' style='font-size:12.5px; font-weight:700;'>Suma: " + suma + "% (Faltan " + falta + "%) ⚠️</span> "
          + "<button type='button' id='btn-autocompletar-comp' class='chip' style='cursor:pointer; font-size:11px; padding:2px 6px; font-weight:600;'>Completar 100%</button>";
        var btnAuto = document.getElementById("btn-autocompletar-comp");
        if (btnAuto) {
          btnAuto.addEventListener("click", function () {
            if (inputsPct.length > 0) {
              var lastInput = inputsPct[inputsPct.length - 1];
              var lastVal = parseFloat(lastInput.value) || 0;
              lastInput.value = Math.round((lastVal + falta) * 100) / 100;
              recalcularTotales();
            }
          });
        }
      } else {
        var exceso = Math.round((suma - 100) * 100) / 100;
        sumaBadge.innerHTML = "<span class='chip rojo' style='font-size:12.5px; font-weight:700;'>Suma: " + suma + "% (Excede por " + exceso + "%) ❌</span>";
      }

      if (resumenPrev) {
        resumenPrev.textContent = partesResumen.length ? ("Vista previa: " + partesResumen.join(" + ")) : "";
      }
    }

    function crearFilaHtml(razaVal, pctVal) {
      var row = document.createElement("div");
      row.className = "comp-fila";
      row.style.cssText = "display:flex; gap:8px; align-items:center; background:var(--superficie); padding:8px 10px; border-radius:8px; border:1px solid var(--borde-fuerte);";

      row.innerHTML = "<div style='flex:3; min-width:110px;'>"
        + "<input class='comp-raza-input' list='dl-catalogo-razas' placeholder='Raza (ej. Brahman)' value='" + esc(razaVal || "") + "' required style='width:100%; padding:7px; border-radius:6px; border:1px solid var(--borde); font-weight:600; box-sizing:border-box;'>"
        + "</div>"
        + "<div style='flex:2; min-width:80px; position:relative;'>"
        + "<input type='number' step='any' min='0' max='100' class='comp-pct-input' placeholder='%' value='" + (pctVal !== undefined ? pctVal : "") + "' required style='width:100%; padding:7px 20px 7px 7px; border-radius:6px; border:1px solid var(--borde); font-weight:700; box-sizing:border-box;'>"
        + "<span style='position:absolute; right:7px; top:8px; font-size:12px; color:var(--texto-suave); font-weight:bold;'>%</span>"
        + "</div>"
        + "<div style='flex:2; text-align:center; min-width:85px;'>"
        + "<span class='comp-frac-badge chip gris' style='font-size:11px; padding:3px 6px; display:inline-block;'>—</span>"
        + "</div>"
        + "<div>"
        + "<button type='button' class='btn-del-raza-fila' style='background:transparent; border:none; color:var(--color-rojo-txt); font-size:16px; cursor:pointer; padding:4px 6px;' title='Eliminar raza'>🗑️</button>"
        + "</div>";

      var inPct = row.querySelector(".comp-pct-input");
      var inRz = row.querySelector(".comp-raza-input");
      var btnDel = row.querySelector(".btn-del-raza-fila");

      inPct.addEventListener("input", recalcularTotales);
      inRz.addEventListener("input", recalcularTotales);
      btnDel.addEventListener("click", function () {
        var totalRows = filasWrap.querySelectorAll(".comp-fila").length;
        if (totalRows <= 1) {
          inPct.value = "";
          inRz.value = "";
          recalcularTotales();
          return;
        }
        row.remove();
        recalcularTotales();
      });

      return row;
    }

    iniciales.forEach(function (c) {
      filasWrap.appendChild(crearFilaHtml(c.raza, c.porcentaje));
    });
    if (!iniciales.length) {
      filasWrap.appendChild(crearFilaHtml("", ""));
    }
    recalcularTotales();

    var btnAdd = document.getElementById("btn-add-raza-fila");
    if (btnAdd) {
      btnAdd.addEventListener("click", function () {
        var inputsPct = filasWrap.querySelectorAll(".comp-pct-input");
        var suma = 0;
        inputsPct.forEach(function (i) { suma += parseFloat(i.value) || 0; });
        var resto = Math.max(0, Math.round((100 - suma) * 100) / 100);
        filasWrap.appendChild(crearFilaHtml("", resto > 0 ? resto : ""));
        recalcularTotales();
        var newInp = filasWrap.lastElementChild.querySelector(".comp-raza-input");
        if (newInp) newInp.focus();
      });
    }

    var form = document.getElementById("form-comp-racial");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      errEl.style.display = "none";

      var inputsRaza = filasWrap.querySelectorAll(".comp-raza-input");
      var inputsPct = filasWrap.querySelectorAll(".comp-pct-input");
      var compPayload = [];
      var suma = 0;

      for (var i = 0; i < inputsRaza.length; i++) {
        var rVal = inputsRaza[i].value.trim();
        var pVal = parseFloat(inputsPct[i].value) || 0;
        if (!rVal) {
          errEl.textContent = "Por favor ingrese el nombre de cada raza.";
          errEl.style.display = "block";
          inputsRaza[i].focus();
          return;
        }
        if (pVal <= 0) {
          errEl.textContent = "Cada porcentaje debe ser mayor a 0%.";
          errEl.style.display = "block";
          inputsPct[i].focus();
          return;
        }
        suma += pVal;
        compPayload.push({ raza: rVal, porcentaje: pVal });
      }

      if (compPayload.length === 0) {
        errEl.textContent = "Debe añadir al menos una raza.";
        errEl.style.display = "block";
        return;
      }

      if (Math.abs(suma - 100) > 1.0) {
        errEl.textContent = "La suma de los porcentajes debe ser 100% (actualmente es " + suma.toFixed(1) + "%).";
        errEl.style.display = "block";
        return;
      }

      var btnG = document.getElementById("btn-guardar-comp");
      if (btnG) { btnG.disabled = true; btnG.textContent = "Guardando..."; }

      fetch("/api/animal/" + encodeURIComponent(tagActual) + "/composicion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ composicion: compPayload })
      }).then(function (r) {
        return r.json().then(function (d) { return { status: r.status, ok: r.ok, body: d }; });
      }).then(function (res) {
        if (btnG) { btnG.disabled = false; btnG.innerHTML = icon("check", 14) + " Guardar Composición"; }
        if (res.ok && res.body && res.body.ok) {
          cerrar();
          if (window.__ultimaFicha && window.__ultimaFicha.tag === tagActual) {
            window.__ultimaFicha.composicion_racial = res.body.composicion;
            window.__ultimaFicha.raza = res.body.resumen;
          }
          if (typeof abrirFicha === "function") {
            var target = document.getElementById("ficha-body") || document.getElementById("vista-ficha");
            if (target) abrirFicha(tagActual, target, false, false);
          }
          if (typeof window.mostrarAviso === "function") {
            window.mostrarAviso("🧬 Composición genética actualizada: " + (res.body.resumen || ""));
          } else {
            alert("Composición genética guardada: " + (res.body.resumen || ""));
          }
        } else {
          errEl.textContent = (res.body && res.body.error) || "Error al guardar composición.";
          errEl.style.display = "block";
        }
      }).catch(function (err) {
        if (btnG) { btnG.disabled = false; btnG.innerHTML = icon("check", 14) + " Guardar Composición"; }
        errEl.textContent = "Error de red: " + (err.message || err);
        errEl.style.display = "block";
      });
    });
  }

  function abrirFicha(tag, target, showIdent, animar, tabId) {

    if (animar === undefined) animar = true;
    if (animar) skeleton(target, "ficha");
    fetchJSON("/api/ficha/" + encodeURIComponent(tag), function (f) {
      if (!f.existe) {
        var rolNf = window.__usuarioActual && window.__usuarioActual.rol;
        var btnCrearNf = (rolNf === "OWNER" || rolNf === "ADMIN")
          ? "<button type='button' class='tema-btn' data-accion='crear-animal' data-tag-nuevo='" + esc(tag) + "' style='padding:8px 14px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;'>" + icon("plus", 15) + "Crear animal " + esc(tag) + "</button>"
          : "";
        var btnBuscarOtro = "<button type='button' class='tema-btn' data-accion='buscar-otro-animal' style='padding:8px 14px; font-weight:600; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;'>" + icon("search", 14) + "Buscar otro animal</button>";
        if (target) montarVista(target, "<h3>" + icon("cow") + "Ficha animal</h3><p>❌ Sin registro para <b>" + esc(tag) + "</b>.</p>"
          + "<p class='aviso'>💡 Si viene de escanear un arete, puede que el tag aún no esté en la base. "
          + "Pruebe escribiendo el número sin guiones (ej. " + esc(String(tag).replace(/\D/g, "") || tag) + ").</p>"
          + "<div style='display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:12px;'>"
          + btnCrearNf
          + btnBuscarOtro
          + "</div>", animar);
        return;
      }
      window.__ultimaFicha = f;
      var catSg = String(f.categoria_sg || "").toUpperCase();
      var esTernero = esAnimalTernero(f);
      var esToro = !esTernero && esAnimalToro(f);
      var esParida = !esTernero && !esToro && ((f.estado_fisiologico && f.estado_fisiologico.codigo === "VACA_ORDENO")
        || (f.lactancia && f.lactancia.estado === "En ordeño" && f.lactancia.del_dias < 200)
        || (f.crias && f.crias.length > 0)
        || (catSg.indexOf("PARIDA") >= 0));
      actualizarVacaHeader({ esFicha: true, esTernero: esTernero, esParida: esParida, esToro: esToro });
      montarVista(target, fichaHtml(f, !!showIdent), animar);
      bindTabs(f);
      if (showIdent) bindIdent();
      // Reabre la ficha en la pestaña pedida. Lo usa pausar/reanudar ordeño
      // (viven en la pestaña Leche): sin esto el re-render vuelve a "General"
      // y el usuario no ve la confirmación ni el botón de reanudar.
      if (tabId) {
        try { window.abrirTabFicha(tabId); } catch (e) {}
      }
    }, target);
  }
  // Devuelve el candidato escrito en el campo #f-tag o #input-tag-ficha-vista si aplica (para RFID).
  function obtenerTextoIdent() {
    var inpVista = document.getElementById("input-tag-ficha-vista");
    if (inpVista && inpVista.value.trim()) return inpVista.value.trim();
    var t = (q("#f-tag") && q("#f-tag").value || "").trim();
    return t || null;
  }
