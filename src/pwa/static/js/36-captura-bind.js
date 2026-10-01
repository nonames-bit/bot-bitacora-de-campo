  function bindCaptura() {
    var cCampos = document.getElementById("captura-campos");
    var _fotoActual = null;
    var _facturaIaFotoRuta = null;

    // BLOQUE 4: stepper de captura en 3 pasos (1=tipo, 2=datos, 3=preview)
    // + defaults inteligentes (último potrero / tag desde ficha).
    var _capPaso = 1;
    var _capTipo = _tipoCapturaActual;
    var _capDatos = {};

    function mostrarPasoCap(n) {
      _capPaso = n;
      [1, 2, 3].forEach(function (i) {
        var paso = q(".cap-paso-" + i);
        if (paso) {
          if (i === n) paso.classList.add("act");
          else paso.classList.remove("act");
        }
        var ind = document.getElementById("cap-ind-" + i);
        if (ind) ind.className = "chip " + (i === n ? "verde" : (i < n ? "azul" : "gris"));
      });
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eScrollCap) { window.scrollTo(0, 0); }
    }

    // Defaults inteligentes: último potrero (localStorage), tag desde ficha
    // (?tag= en URL, /ficha/TAG en la ruta, o pendiente dejado por el FAB) y
    // fecha de hoy si quedó vacía (camposHtmlCaptura ya la prellena).
    function aplicarDefaultsCaptura() {
      var tagIni = window.__capTagPendiente || null;
      if (!tagIni) {
        try { tagIni = new URLSearchParams(window.location.search).get("tag"); } catch (eTag1) { tagIni = null; }
      }
      if (!tagIni) {
        try {
          var mFicha = window.location.pathname.match(/\/ficha\/([A-Za-z0-9_-]+)/i);
          if (mFicha) tagIni = mFicha[1];
        } catch (eTag2) { /* noop */ }
      }
      if (tagIni) {
        var fTagDef = document.getElementById("cap-tag");
        if (fTagDef) {
          fTagDef.value = tagIni;
          fTagDef.dispatchEvent(new Event("input"));
          fTagDef.dispatchEvent(new Event("change"));
        }
        var chipTag = document.getElementById("cap-tag-chip");
        if (chipTag) chipTag.innerHTML = "<span class='chip azul'>📋 Animal: " + esc(tagIni) + "</span>";
        window.__capTagPendiente = null;
      }
      var potIni = window.__capPotreroPendiente || null;
      if (potIni) {
        var idsPotIni = ["cap-pot-orig", "cap-fin-potrero", "cap-pot-madre"];
        for (var iOrig = 0; iOrig < idsPotIni.length; iOrig++) {
          var elPotI = document.getElementById(idsPotIni[iOrig]);
          if (elPotI) {
            elPotI.value = potIni;
            elPotI.dispatchEvent(new Event("change"));
            break;
          }
        }
        window.__capPotreroPendiente = null;
      }
      var farmIni = window.__capFarmacoPendiente || null;
      if (farmIni) {
        var elTratP = document.getElementById("cap-trat-producto");
        if (elTratP) {
          elTratP.value = farmIni;
          elTratP.dispatchEvent(new Event("change"));
        }
        window.__capFarmacoPendiente = null;
      }
      var toroIni = window.__capToroPendiente || null;
      if (toroIni) {
        var elToroS = document.getElementById("cap-toro") || document.getElementById("cap-palp-toro");
        if (elToroS) {
          elToroS.value = toroIni;
          elToroS.dispatchEvent(new Event("change"));
        }
        window.__capToroPendiente = null;
      }
      var ultPot = null;
      try { ultPot = localStorage.getItem("bitacora_ultimo_potrero"); } catch (ePot0) { ultPot = null; }
      if (ultPot) {
        var idsPot = ["cap-pot-dest", "cap-fin-potrero", "cap-pot-cria", "cap-pot-madre", "cap-pot-orig"];
        for (var ip = 0; ip < idsPot.length; ip++) {
          var inpPotDef = document.getElementById(idsPot[ip]);
          if (inpPotDef && !inpPotDef.value) {
            inpPotDef.value = ultPot;
            // Chip "último usado": un toque lo reaplica si el operario lo borró.
            (function (inpC, idC) {
              if (document.getElementById("cap-pot-hint-" + idC)) return;
              var hint = document.createElement("button");
              hint.type = "button";
              hint.id = "cap-pot-hint-" + idC;
              hint.className = "cap-potrero-hint";
              hint.textContent = "último usado: " + ultPot;
              hint.addEventListener("click", function () { inpC.value = ultPot; try { inpC.focus(); } catch (eHint) { /* noop */ } });
              if (inpC.parentNode) inpC.parentNode.appendChild(hint);
            })(inpPotDef, idsPot[ip]);
            break;
          }
        }
      }
      var fFechaDef = document.getElementById("cap-fecha");
      if (fFechaDef && !fFechaDef.value) fFechaDef.value = new Date().toISOString().slice(0, 10);

      // Inseminador y Palpador por defecto: usuario en sesión si el campo está presente y vacío
      var fInsemDef = document.getElementById("cap-inseminador");
      if (fInsemDef && !fInsemDef.value && window.__usuarioActual && window.__usuarioActual.nombre) {
        fInsemDef.value = window.__usuarioActual.nombre;
      }
      var fPalpDef = document.getElementById("cap-palp-responsable");
      if (fPalpDef && !fPalpDef.value && window.__usuarioActual && window.__usuarioActual.nombre) {
        fPalpDef.value = window.__usuarioActual.nombre;
      }
      cargarListaInseminadores();

      var btnNuevoInsCap = document.getElementById("btn-nuevo-inseminador-cap");
      if (btnNuevoInsCap && !btnNuevoInsCap.dataset.bound) {
        btnNuevoInsCap.dataset.bound = "1";
        btnNuevoInsCap.addEventListener("click", function () {
          mostrarModalNuevoInseminador(function (nuevoNombre) {
            if (fInsemDef && nuevoNombre) fInsemDef.value = nuevoNombre;
          });
        });
      }
    }

    function recolectarCapDatos() {
      var d = {};
      qa("#captura-campos input, #captura-campos select").forEach(function (el) {
        if (!el.id || el.type === "file" || el.type === "checkbox") return;
        var v = (el.value || "").trim();
        if (v) d[el.id] = v;
      });
      _capDatos = d;
      return d;
    }

    function nombreTipoCap(id) {
      var noms = {
        parto: "Parto", pesaje: "Pesaje", palpacion: "Tacto / Palpación", pajuela: "Stock Pajillas",
        nitrogeno: "Recarga Nitrógeno", tratamiento: "Tratamiento", traslado: "Traslado",
        destete: "Destete", secado: "Secado", celo: "Celo", servicio: "Servicio / IA",
        leche: "Leche", venta: "Venta Animal", muerte: "Muerte / Baja", gasto: "Ingreso / Gasto", tarea: "Asignar Tarea"
      };
      return noms[id] || id;
    }

    function bindCamposPalpacion() {
      if (_tipoCapturaActual !== "palpacion") return;
      var selRes = document.getElementById("cap-palp-resultado");
      var prenadaBox = document.getElementById("cap-palp-prenada-box");
      var fFecha = document.getElementById("cap-fecha");
      var fDias = document.getElementById("cap-palp-dias");
      var fFep = document.getElementById("cap-palp-fep");

      function calcularFep() {
        if (!fFep) return;
        var dias = parseInt(fDias ? fDias.value : 0, 10);
        var fStr = (fFecha && fFecha.value) || new Date().toISOString().slice(0, 10);
        if (!isNaN(dias) && dias > 0 && dias <= 290) {
          var fDate = new Date(fStr + "T12:00:00");
          var diasFaltan = 283 - dias;
          var fepDate = new Date(fDate.getTime() + (diasFaltan * 86400000));
          fFep.value = fepDate.toISOString().slice(0, 10);
        } else {
          fFep.value = "";
        }
      }

      function toggleBox() {
        var esPrenada = !selRes || selRes.value === "PREÑADA";
        if (prenadaBox) prenadaBox.style.display = esPrenada ? "block" : "none";
        if (esPrenada) calcularFep();
      }

      if (selRes) selRes.addEventListener("change", toggleBox);
      if (fDias) fDias.addEventListener("input", calcularFep);
      if (fFecha) fFecha.addEventListener("change", calcularFep);
      toggleBox();
    }

    function bindCamposNitrogeno() {
      if (_tipoCapturaActual !== "nitrogeno") return;
      var fFecha = document.getElementById("cap-fecha");
      var fInterv = document.getElementById("cap-nitr-intervalo");
      var fProx = document.getElementById("cap-nitr-prox");

      function calcularProx() {
        if (!fProx) return;
        var intD = parseInt(fInterv ? fInterv.value : 21, 10);
        var fStr = (fFecha && fFecha.value) || new Date().toISOString().slice(0, 10);
        if (!isNaN(intD) && intD > 0) {
          var fDate = new Date(fStr + "T12:00:00");
          var proxDate = new Date(fDate.getTime() + (intD * 86400000));
          fProx.value = proxDate.toISOString().slice(0, 10);
        }
      }

      if (fInterv) fInterv.addEventListener("input", calcularProx);
      if (fFecha) fFecha.addEventListener("change", calcularProx);
      calcularProx();
    }

    function bindCamposTarea() {
      if (_tipoCapturaActual !== "tarea") return;
      var btns = qa(".cap-obj-btn");
      var wrapAnimal = document.getElementById("cap-wrap-obj-animal");
      var wrapPotrero = document.getElementById("cap-wrap-obj-potrero");
      var inpObj = document.getElementById("cap-tarea-obj");
      btns.forEach(function (b) {
        b.addEventListener("click", function () {
          btns.forEach(function (x) { x.classList.remove("act"); });
          b.classList.add("act");
          var obj = b.getAttribute("data-obj");
          if (inpObj) inpObj.value = obj;
          if (wrapAnimal) wrapAnimal.style.display = (obj === "animal") ? "" : "none";
          if (wrapPotrero) wrapPotrero.style.display = (obj === "potrero") ? "" : "none";
        });
      });
      fetch("/api/equipo/integrantes").then(function (r) { return r.json(); }).then(function (d) {
        if (!d || !d.integrantes) return;
        var dl = document.getElementById("dl-integrantes-equipo");
        if (dl) {
          dl.innerHTML = d.integrantes.map(function (it) {
            return "<option value='" + esc(it.nombre) + "'>" + esc(it.rol ? it.rol : "") + "</option>";
          }).join("");
        }
      }).catch(function () {});
    }

    function obtenerToroPadreSeleccionado() {
      var sel = document.getElementById("cap-toro-padre");
      if (!sel) return null;
      var v = (sel.value || "").trim();
      if (v === "OTRO") {
        var inpOtro = document.getElementById("cap-toro-otro");
        return (inpOtro && inpOtro.value || "").trim() || null;
      }
      return v || null;
    }

    function bindToroParto() {
      if (_tipoCapturaActual !== "parto") return;
      var sel = document.getElementById("cap-toro-padre");
      var wrapOtro = document.getElementById("cap-toro-otro-wrap");
      var inpOtro = document.getElementById("cap-toro-otro");
      if (!sel) return;
      cargarListaToros(sel);
      sel.addEventListener("change", function () {
        if (sel.value === "OTRO") {
          if (wrapOtro) wrapOtro.style.display = "block";
          if (inpOtro) inpOtro.focus();
        } else {
          if (wrapOtro) wrapOtro.style.display = "none";
          if (inpOtro) inpOtro.value = "";
        }
      });
    }

    function bindSugerenciaPadreParto() {
      if (_tipoCapturaActual !== "parto") return;
      var fMadre = document.getElementById("cap-tag");
      var fFecha = document.getElementById("cap-fecha");
      var selToro = document.getElementById("cap-toro-padre");
      var hintToro = document.getElementById("cap-toro-sugerido-hint");
      if (!fMadre || !selToro) return;

      var _toroModificadoManualmente = false;
      var boxCrucePreview = document.getElementById("cap-cruce-cria-preview");

      function actualizarPreviewCruce() {
        if (!boxCrucePreview) return;
        var vm = (fMadre.value || "").trim();
        var vt = (selToro.value || "").trim();
        if (vt === "OTRO") {
          var inOtro = document.getElementById("cap-toro-otro");
          vt = (inOtro && inOtro.value || "").trim();
        }
        if (!vm || !vt) {
          boxCrucePreview.style.display = "none";
          boxCrucePreview.innerHTML = "";
          return;
        }
        fetchJSON("/api/genetica/simular-cruce?madre=" + encodeURIComponent(vm) + "&padre=" + encodeURIComponent(vt), function (res) {
          if (!boxCrucePreview) return;
          if (res && res.ok && res.cria_resumen) {
            boxCrucePreview.style.display = "block";
            boxCrucePreview.innerHTML = "<div style='display:flex; align-items:center; gap:6px; flex-wrap:wrap;'>"
              + "<span style='font-weight:700; color:var(--verde-marca);'>" + icon("dna", 13) + " Genética estimada cría:</span> "
              + "<b>" + esc(res.cria_resumen) + "</b>"
              + "</div>";
          } else {
            boxCrucePreview.style.display = "none";
          }
        });
      }

      selToro.addEventListener("change", function () {
        _toroModificadoManualmente = true;
        actualizarPreviewCruce();
      });
      var inToroOtro = document.getElementById("cap-toro-otro");
      if (inToroOtro) {
        inToroOtro.addEventListener("input", actualizarPreviewCruce);
      }

      var _timerSugPadre = null;
      var _ultVacaConsultada = "";
      var _ultFechaConsultada = "";

      function consultarSugerenciaPadre() {
        var vaca = (fMadre.value || "").trim();
        var fecha = (fFecha && fFecha.value) || new Date().toISOString().slice(0, 10);
        if (!vaca) {
          if (hintToro) hintToro.innerHTML = "";
          return;
        }
        if (vaca === _ultVacaConsultada && fecha === _ultFechaConsultada) return;
        _ultVacaConsultada = vaca;
        _ultFechaConsultada = fecha;

        var url = "/api/parto/sugerir-padre?vaca=" + encodeURIComponent(vaca) + "&fecha=" + encodeURIComponent(fecha);
        fetch(url)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!hintToro) return;
            if (data && data.ok && data.sugerencia) {
              var s = data.sugerencia;
              var tagToro = s.toro_tag || "";
              var nomToro = s.toro_nombre ? (" · " + s.toro_nombre) : "";
              var esMN = s.metodo === "MONTA_NATURAL_POTRERO";
              var iconoMetodo = esMN ? icon("bull", 13) : icon("sperm", 13);
              var badgeMetodo = esMN
                ? "<span class='chip ambar' style='padding:1px 6px; font-size:10.5px; font-weight:700;'>" + iconoMetodo + " Monta Natural</span>"
                : "<span class='chip verde' style='padding:1px 6px; font-size:10.5px; font-weight:700;'>" + iconoMetodo + " " + esc(s.tipo_servicio || "IA") + "</span>";

              var html = "<div style='display:inline-flex; align-items:center; flex-wrap:wrap; gap:6px; background:rgba(217, 119, 6, 0.09); border:1px solid rgba(217, 119, 6, 0.35); border-radius:6px; padding:5px 8px; margin-top:2px;'>"
                + "<span style='font-weight:700; color:var(--texto); font-size:11.5px;'>💡 Sugerencia de Padre:</span> "
                + badgeMetodo
                + "<b style='color:var(--texto); font-size:12px;'>" + esc(tagToro + nomToro) + "</b>"
                + "<small style='color:var(--texto-suave); font-size:11px;'>(" + esc(s.explicacion) + ")</small>"
                + "<button type='button' class='btn-aplicar-toro-sug' style='background:var(--ambar, #d97706); color:#fff; border:none; border-radius:4px; padding:2px 7px; font-size:11px; font-weight:700; cursor:pointer;'>Aplicar</button>"
                + "</div>";

              hintToro.innerHTML = html;

              function aplicarToro() {
                var existe = false;
                for (var i = 0; i < selToro.options.length; i++) {
                  if (selToro.options[i].value.toUpperCase() === tagToro.toUpperCase()) {
                    selToro.selectedIndex = i;
                    existe = true;
                    break;
                  }
                }
                if (!existe) {
                  var opt = document.createElement("option");
                  opt.value = tagToro;
                  opt.textContent = tagToro + nomToro + " (Sugerido)";
                  selToro.insertBefore(opt, selToro.firstChild ? selToro.firstChild.nextSibling : null);
                  selToro.value = tagToro;
                }
                var wrapOtro = document.getElementById("cap-toro-otro-wrap");
                if (wrapOtro) wrapOtro.style.display = "none";
                actualizarPreviewCruce();
              }

              var btnAplicar = hintToro.querySelector(".btn-aplicar-toro-sug");
              if (btnAplicar) {
                btnAplicar.addEventListener("click", function (ev) {
                  ev.preventDefault();
                  aplicarToro();
                });
              }

              // Si el select no ha sido tocado manualmente o está vacío, preseleccionar automáticamente
              if (!_toroModificadoManualmente && (!selToro.value || selToro.value === "")) {
                aplicarToro();
              }
            } else {
              hintToro.innerHTML = "";
            }
          })
          .catch(function () {
            if (hintToro) hintToro.innerHTML = "";
          });
      }

      function dispararDebounce() {
        if (_timerSugPadre) clearTimeout(_timerSugPadre);
        _timerSugPadre = setTimeout(consultarSugerenciaPadre, 350);
      }

      fMadre.addEventListener("input", dispararDebounce);
      fMadre.addEventListener("change", dispararDebounce);
      if (fFecha) fFecha.addEventListener("change", dispararDebounce);

      if (fMadre.value.trim()) {
        dispararDebounce();
      }
    }

    // Paso 3: resumen legible y estructurado antes de guardar.
    function resumenCapHtml() {
      var d = recolectarCapDatos();
      var fechaR = d["cap-fecha"] || new Date().toISOString().slice(0, 10);
      var h = "";

      if (_capTipo === "parto") {
        var tipoEv = d["cap-tipo-evento"] || "PARTO";
        var esPerdida = TIPOS_EVENTO_SIN_CRIA.indexOf(tipoEv) !== -1;
        var vaca = d["cap-tag"] || "—";
        var criaTag = d["cap-cria-tag"] || "(sin arete)";
        var toroPadre = obtenerToroPadreSeleccionado();

        h = "<div style='font-size:14px; font-weight:700; color:var(--texto); margin-bottom:8px;'>"
          + "🐮 " + esc(nombreTipoCap(_capTipo)) + " · " + esc(tipoEv)
          + "</div>"
          + "<div style='display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:10px;'>"
          + "<div style='background:var(--superficie); padding:8px 10px; border-radius:6px; border:1px solid var(--borde);'>"
          + "<small style='color:var(--texto-suave); display:block; font-size:11px; font-weight:600;'>Madre (Vaca):</small>"
          + "<b style='font-size:15px; color:var(--texto); font-family:var(--font-mono);'>" + esc(vaca) + "</b>"
          + "</div>"
          + "<div style='background:var(--superficie); padding:8px 10px; border-radius:6px; border:1px solid var(--borde);'>"
          + "<small style='color:var(--texto-suave); display:block; font-size:11px; font-weight:600;'>Fecha del Parto:</small>"
          + "<b style='font-size:13.5px; color:var(--texto); font-family:var(--font-mono);'>" + esc(fechaCorta(fechaR)) + "</b>"
          + "</div>"
          + "</div>";

        if (!esPerdida) {
          h += "<div style='background:rgba(34, 197, 94, 0.09); border-left:4px solid #22c55e; padding:10px 12px; border-radius:6px; margin-bottom:8px;'>"
            + "<div style='font-size:13px; color:var(--texto);'>"
            + "👶 <b>Número de la Cría:</b> <span style='font-family:var(--font-mono); font-weight:800; font-size:16px; color:#16a34a; margin-left:4px;'>" + esc(criaTag) + "</span>"
            + "</div>"
            + "<div style='font-size:12px; color:var(--texto-suave); margin-top:3px;'>"
            + "Sexo: <b>" + esc(d["cap-sexo"] || "Hembra") + "</b>"
            + " · Estado: <b>" + esc(d["cap-estado-cria"] || "Vivo") + "</b>"
            + (d["cap-peso-nacer"] ? (" · Peso al nacer: <b>" + esc(d["cap-peso-nacer"]) + " kg</b>") : "")
            + "</div>"
            + "</div>";

          if (tipoEv === "GEMELAR") {
            var cria2Tag = d["cap-cria2-tag"] || "(sin arete)";
            h += "<div style='background:rgba(34, 197, 94, 0.09); border-left:4px solid #22c55e; padding:10px 12px; border-radius:6px; margin-bottom:8px;'>"
              + "<div style='font-size:13px; color:var(--texto);'>"
              + "👶 <b>Número de Cría 2 (Gemelo):</b> <span style='font-family:var(--font-mono); font-weight:800; font-size:16px; color:#16a34a; margin-left:4px;'>" + esc(cria2Tag) + "</span>"
              + "</div>"
              + "<div style='font-size:12px; color:var(--texto-suave); margin-top:3px;'>"
              + "Sexo: <b>" + esc(d["cap-sexo2"] || "Hembra") + "</b>"
              + " · Estado: <b>" + esc(d["cap-estado-cria2"] || "Vivo") + "</b>"
              + (d["cap-peso-nacer2"] ? (" · Peso: <b>" + esc(d["cap-peso-nacer2"]) + " kg</b>") : "")
              + "</div>"
              + "</div>";
          }
        }

        if (toroPadre) {
          h += "<div style='margin-bottom:6px; font-size:13px; background:var(--superficie); padding:6px 10px; border-radius:6px; border:1px solid var(--borde);'>"
            + "🐂 <b>Toro / Padre:</b> <b style='color:var(--azul-marca); font-family:var(--font-mono);'>" + esc(toroPadre) + "</b>"
            + "</div>";
        }
        if (!esPerdida && (d["cap-distocia"] === "SI")) {
          h += "<div style='margin-bottom:6px; font-size:13px; background:rgba(220,38,38,0.08); padding:6px 10px; border-radius:6px; border-left:4px solid var(--color-rojo-txt, #dc2626);'>"
            + "⚠️ <b>Parto difícil (distocia):</b> vigilar la vaca en el postparto."
            + "</div>";
        }
        if (d["cap-pot-cria"] || d["cap-pot-madre"]) {
          h += "<div style='margin-bottom:6px; font-size:12.5px; color:var(--texto-suave);'>"
            + "📍 " + (d["cap-pot-madre"] ? ("Madre en <b>" + esc(d["cap-pot-madre"]) + "</b> ") : "")
            + (d["cap-pot-cria"] ? ("· Cría en <b>" + esc(d["cap-pot-cria"]) + "</b>") : "")
            + "</div>";
        }
        if (d["cap-notas"]) {
          h += "<div style='margin-top:4px; font-size:12px; font-style:italic; color:var(--texto-suave);'>💬 " + esc(d["cap-notas"]) + "</div>";
        }
        return h;
      }

      if (_capTipo === "palpacion") {
        var vacaP = d["cap-tag"] || "—";
        var resP = d["cap-palp-resultado"] || "PREÑADA";
        var metP = d["cap-palp-metodo"] === "ECOGRAFO" ? "📟 Ecógrafo" : "🖐️ Manual (Tacto)";
        var chipP = resP === "PREÑADA" ? "verde" : (resP === "VACIA" ? "rojo" : "ambar");
        h = "<div style='font-size:14px; font-weight:700; color:var(--texto); margin-bottom:8px;'>"
          + "🖐️ " + esc(nombreTipoCap(_capTipo)) + " · <span class='chip " + chipP + "'>" + esc(resP) + "</span>"
          + "</div>"
          + "<div style='display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:10px;'>"
          + "<div style='background:var(--superficie); padding:8px 10px; border-radius:6px; border:1px solid var(--borde);'>"
          + "<small style='color:var(--texto-suave); display:block; font-size:11px; font-weight:600;'>Vaca / Arete:</small>"
          + "<b style='font-size:15px; color:var(--texto); font-family:var(--font-mono);'>" + esc(vacaP) + "</b>"
          + "</div>"
          + "<div style='background:var(--superficie); padding:8px 10px; border-radius:6px; border:1px solid var(--borde);'>"
          + "<small style='color:var(--texto-suave); display:block; font-size:11px; font-weight:600;'>Método:</small>"
          + "<b style='font-size:13px; color:var(--texto);'>" + esc(metP) + "</b>"
          + "</div>"
          + "</div>";
        if (resP === "PREÑADA") {
          h += "<div style='background:rgba(46,125,50,0.09); border-left:4px solid #2e7d32; padding:10px 12px; border-radius:6px; margin-bottom:8px;'>"
            + "<div style='font-size:13px;'>🤰 <b>Días de Preñez:</b> <b>" + esc(d["cap-palp-dias"] || "45") + " días</b>"
            + (d["cap-palp-fep"] ? (" · FEP: <b>" + esc(fechaCorta(d["cap-palp-fep"])) + "</b>") : "")
            + "</div>"
            + (d["cap-palp-toro"] ? ("<div style='font-size:12.5px; margin-top:3px;'>🐂 Toro/Pajilla: <b>" + esc(d["cap-palp-toro"]) + "</b></div>") : "")
            + "</div>";
        }
        if (d["cap-palp-hallazgo"]) {
          h += "<div style='margin-bottom:6px; font-size:12.5px; background:var(--superficie); padding:6px 10px; border-radius:6px; border:1px solid var(--borde);'>🔬 Hallazgo: <b>" + esc(d["cap-palp-hallazgo"]) + "</b></div>";
        }
        if (d["cap-cc"] || d["cap-peso"]) {
          h += "<div style='margin-bottom:6px; font-size:12px; color:var(--texto-suave);'>"
            + (d["cap-cc"] ? ("Condición Corporal: <b>" + esc(d["cap-cc"]) + "/5</b> ") : "")
            + (d["cap-peso"] ? ("· Peso: <b>" + esc(d["cap-peso"]) + " kg</b>") : "")
            + "</div>";
        }
        if (d["cap-palp-responsable"]) {
          h += "<div style='font-size:12px; color:var(--texto-suave);'>👨‍⚕️ Profesional: <b>" + esc(d["cap-palp-responsable"]) + "</b></div>";
        }
        if (d["cap-notas"]) {
          h += "<div style='margin-top:4px; font-size:12px; font-style:italic;'>💬 " + esc(d["cap-notas"]) + "</div>";
        }
        return h;
      }

      if (_capTipo === "pajuela") {
        h = "<div style='font-size:14px; font-weight:700; color:var(--texto); margin-bottom:8px;'>❄️ " + esc(nombreTipoCap(_capTipo)) + "</div>"
          + "<div style='background:rgba(30,60,114,0.06); border-left:4px solid var(--azul-marca); padding:10px 12px; border-radius:6px; margin-bottom:8px;'>"
          + "<div style='font-size:14px;'>🐂 <b>Toro:</b> <b>" + esc(d["cap-paj-toro"] || "—") + "</b>"
          + (d["cap-paj-raza"] ? (" (" + esc(d["cap-paj-raza"]) + ")") : "") + "</div>"
          + "<div style='font-size:12.5px; margin-top:3px;'>Canastilla: <b>" + esc(d["cap-paj-canastilla"] || "—") + "</b> · Entrada: <b>" + esc(d["cap-paj-cant"] || "1") + " pajillas</b>"
          + (d["cap-paj-costo"] ? (" · Costo unit: <b>" + fmtMoneda(Number(d["cap-paj-costo"])) + "</b>") : "") + "</div>"
          + (d["cap-paj-procedencia"] ? ("<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>Procedencia: " + esc(d["cap-paj-procedencia"]) + "</div>") : "")
          + "</div>";
        if (d["cap-notas"]) h += "<div style='margin-top:4px; font-size:12px; font-style:italic;'>💬 " + esc(d["cap-notas"]) + "</div>";
        return h;
      }

      if (_capTipo === "nitrogeno") {
        h = "<div style='font-size:14px; font-weight:700; color:var(--texto); margin-bottom:8px;'>❄️ " + esc(nombreTipoCap(_capTipo)) + "</div>"
          + "<div style='background:rgba(30,60,114,0.06); border-left:4px solid var(--azul-marca); padding:10px 12px; border-radius:6px; margin-bottom:8px;'>"
          + "<div style='font-size:13px;'>Intervalo estimado: <b>" + esc(d["cap-nitr-intervalo"] || "21") + " días</b>"
          + (d["cap-nitr-prox"] ? (" · Próxima recarga: <b>" + esc(fechaCorta(d["cap-nitr-prox"])) + "</b>") : "") + "</div>"
          + (d["cap-nitr-proveedor"] ? ("<div style='font-size:12.5px; margin-top:3px;'>Proveedor: <b>" + esc(d["cap-nitr-proveedor"]) + "</b></div>") : "")
          + (d["cap-nitr-costo"] ? ("<div style='font-size:12.5px; margin-top:2px;'>Costo: <b>" + fmtMoneda(Number(d["cap-nitr-costo"])) + "</b></div>") : "")
          + "</div>";
        if (d["cap-notas"]) h += "<div style='margin-top:4px; font-size:12px; font-style:italic;'>💬 " + esc(d["cap-notas"]) + "</div>";
        return h;
      }

      if (_capTipo === "venta") {
        var vTag = d["cap-tag"] || "—";
        var vComp = d["cap-venta-comprador"] || "(sin comprador)";
        var vPrecio = d["cap-venta-precio"] ? fmtMoneda(Number(d["cap-venta-precio"])) : "Sin precio";
        var vPeso = d["cap-venta-peso"] ? (d["cap-venta-peso"] + " kg") : null;
        var vMot = d["cap-venta-motivo"] || "Venta";
        h = "<div style='font-size:14px; font-weight:700; color:var(--texto); margin-bottom:8px;'>💰 Venta de Semoviente</div>"
          + "<div style='background:rgba(217,119,6,0.08); border-left:4px solid #D97706; padding:10px 12px; border-radius:6px; margin-bottom:8px;'>"
          + "<div style='font-size:14px;'>Animal / Tag: <b style='font-family:var(--font-mono); font-size:16px; color:#D97706;'>" + esc(vTag) + "</b> · Fecha: <b>" + esc(fechaCorta(fechaR)) + "</b></div>"
          + "<div style='font-size:13px; margin-top:4px;'>Comprador / Destino: <b>" + esc(vComp) + "</b></div>"
          + "<div style='font-size:13px; margin-top:2px;'>Monto Venta: <b style='color:#16a34a; font-size:15px;'>" + esc(vPrecio) + "</b>" + (vPeso ? (" · Peso báscula: <b>" + esc(vPeso) + "</b>") : "") + "</div>"
          + "<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>Motivo: <b>" + esc(vMot) + "</b> · <i>El animal cambiará a estado VENDIDO.</i></div>"
          + "</div>";
        if (d["cap-notas"]) h += "<div style='margin-top:4px; font-size:12px; font-style:italic;'>💬 " + esc(d["cap-notas"]) + "</div>";
        return h;
      }

      var tagR = d["cap-tag"] || d["cap-cria-tag"] || d["cap-tarea-potrero"] || "—";
      h = "<b>" + esc(nombreTipoCap(_capTipo)) + "</b> · Objetivo: <b>" + esc(tagR) + "</b> · Fecha: <b>" + esc(fechaCorta(fechaR)) + "</b>";
      if (d["cap-cria-tag"] && d["cap-tag"]) {
        h += "<br>Cría a destetar: <b>" + esc(d["cap-cria-tag"]) + "</b>";
      }
      Object.keys(d).forEach(function (k) {
        if (k === "cap-tag" || k === "cap-fecha" || k === "cap-cria-tag" || k === "cap-cria2-tag") return;
        h += "<br>" + esc(k.replace(/^cap-/, "").replace(/-/g, " ")) + ": <b>" + esc(d[k]) + "</b>";
      });
      // Simulador 1-toque (Fase 5.2): en Servicio/IA con vaca y toro se
      // evalúa consanguinidad 3G antes de guardar. Solo avisa, no bloquea.
      if (_capTipo === "servicio") {
        var vacaS = (d["cap-tag"] || "").trim();
        var toroS = (d["cap-toro"] || "").trim();
        if (vacaS && toroS) {
          h += "<div id='sim-consang-box' style='margin-top:8px; font-size:13px;'>⏳ Evaluando consanguinidad 3G…</div>";
          programarSimConsang(vacaS, toroS);
        }
      }
      return h;
    }

    // Evaluación diferida del simulador con caché por pareja: el resumen
    // se re-renderiza al teclear, así no se repite el fetch para la misma
    // vaca + toro y una respuesta tardía no pinta sobre otra pareja.
    var _simConsangKey = "";
    var _simConsangPend = "";
    var _simConsangTimer = null;
    function programarSimConsang(vaca, toro) {
      var key = vaca + "|" + toro;
      if (key === _simConsangKey) return;
      _simConsangPend = key;
      if (_simConsangTimer) clearTimeout(_simConsangTimer);
      _simConsangTimer = setTimeout(function () { evaluarSimConsang(vaca, toro, key); }, 350);
    }
    function evaluarSimConsang(vaca, toro, key) {
      fetch("/api/simular-cruzamiento?vaca=" + encodeURIComponent(vaca) + "&toro=" + encodeURIComponent(toro))
        .then(function (r) { return r.json(); })
        .then(function (sim) {
          if (key !== _simConsangPend) return;
          var box = document.getElementById("sim-consang-box");
          if (!box) return;
          _simConsangKey = key;
          box.innerHTML = htmlSimConsang(sim, vaca, toro);
        })
        .catch(function () {
          if (key !== _simConsangPend) return;
          var box2 = document.getElementById("sim-consang-box");
          if (box2) box2.innerHTML = "<span style='font-size:12px; color:var(--texto-suave);'>⚠️ Sin conexión: no se pudo evaluar consanguinidad.</span>";
        });
    }
    function htmlSimConsang(sim, vaca, toro) {
      if (!sim || !sim.ok) {
        return "<span style='font-size:12px; color:var(--texto-suave);'>⚠️ No se pudo evaluar consanguinidad.</span>";
      }
      if (!sim.evaluable) {
        return "<div style='background:var(--superficie); border:1px solid var(--borde); border-radius:6px; padding:8px 10px; margin-top:4px;'>"
          + "🧬 <b>Consanguinidad 3G:</b> <span class='chip gris'>NO EVALUABLE</span>"
          + "<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>" + esc(sim.detalle || "") + "</div></div>";
      }
      if (sim.apto) {
        return "<div style='background:rgba(34,197,94,0.09); border-left:4px solid #22c55e; padding:8px 10px; border-radius:6px; margin-top:4px;'>"
          + "🧬 <b>Consanguinidad 3G:</b> <span class='chip verde'>APTO</span> <span style='font-size:12px;'>" + esc(vaca) + " × " + esc(toro) + "</span>"
          + (sim.advertencia ? ("<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>⚠️ " + esc(sim.advertencia) + "</div>") : "")
          + "</div>";
      }
      var anc = (sim.ancestros_comunes || []).map(function (a) {
        return esc(a.tag) + " (" + esc(a.parentesco_vaca) + "/" + esc(a.parentesco_toro) + ")";
      }).join(", ");
      return "<div style='background:rgba(220,38,38,0.08); border-left:4px solid var(--color-rojo-txt, #dc2626); padding:8px 10px; border-radius:6px; margin-top:4px;'>"
        + "🧬 <b>Consanguinidad 3G:</b> <span class='chip rojo'>NO RECOMENDADO</span>"
        + "<div style='font-size:12.5px; margin-top:2px;'>" + esc(sim.detalle || "") + "</div>"
        + (anc ? ("<div style='font-size:12px; color:var(--texto-suave);'>En común: " + anc + "</div>") : "")
        + (sim.relacion_directa ? ("<div style='font-size:12px; color:var(--texto-suave);'>" + esc(sim.relacion_directa) + "</div>") : "")
        + "<div style='font-size:12px; color:var(--texto-suave); margin-top:2px;'>Puede guardar igual si el dueño lo autoriza.</div>"
        + "</div>";
    }

    // El avance 2→3 valida los requeridos del paso 2 (respeta el modo
    // masivo de traslado, que quita el required del tag).
    function validarPaso2Cap() {
      var falt = null;
      qa("#captura-campos [required]").forEach(function (el) {
        if (!falt && !(el.value || "").trim() && el.offsetParent !== null) falt = el;
      });
      if (falt) {
        mostrarToast("Falta un campo requerido", "rojo");
        try { falt.focus(); } catch (eFoco) { /* noop */ }
        return false;
      }
      return true;
    }

    // Regenera los campos del paso 2 con TODA la lógica de binding
    // existente (foto, IA recibo, traslado masivo, destete, gemelar) más
    // los defaults inteligentes. No toca ninguna de esas funciones.
    function refrescarCamposCap() {
      if (!cCampos) return;
      cCampos.innerHTML = camposHtmlCaptura(_tipoCapturaActual);
      bindFotoCaptura();
      bindCamposFinanza();
      bindTrasladoMasivo();
      bindDesteteBusquedaCria();
      bindTipoEventoParto();
      bindSugerenciaTagCriaParto();
      bindToroParto();
      bindSugerenciaPadreParto();
      bindCamposTarea();
      bindCamposPalpacion();
      bindCamposNitrogeno();
      aplicarDefaultsCaptura();

      var fTag = document.getElementById("cap-tag");
      if (fTag) {
        fTag.addEventListener("input", onInputSugerir);
        fTag.addEventListener("focus", function () {
          var dl = document.getElementById("dl-tags");
          if (!dl || !dl.children.length) cargarListasAutocompletar();
        });
      }
    }

    function wireStepperCap() {
      var bGps = document.getElementById("btn-cap-gps-ronda");
      if (bGps) bGps.addEventListener("click", localizarGPSRonda);
      var bManga = document.getElementById("btn-cap-ir-manga");
      if (bManga) {
        bManga.addEventListener("click", function () {
          irAVista("manga");
          cargar(true);
          try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) {}
        });
      }
      var bSig1 = document.getElementById("btn-cap-sig1");
      if (bSig1) bSig1.addEventListener("click", function () { mostrarPasoCap(2); });
      var bAtr2 = document.getElementById("btn-cap-atras2");
      if (bAtr2) bAtr2.addEventListener("click", function () { mostrarPasoCap(1); });
      var bSig2 = document.getElementById("btn-cap-sig2");
      if (bSig2) bSig2.addEventListener("click", function () {
        if (!validarPaso2Cap()) return;
        var prev = document.getElementById("cap-preview-resumen");
        if (prev) prev.innerHTML = resumenCapHtml();
        mostrarPasoCap(3);
      });
      var bAtr3 = document.getElementById("btn-cap-atras3");
      if (bAtr3) bAtr3.addEventListener("click", function () { mostrarPasoCap(2); });

      var formCap = document.getElementById("form-captura");
      if (formCap && !formCap.__enterIntercepted) {
        formCap.__enterIntercepted = true;
        formCap.addEventListener("keydown", function (e) {
          if (e.key === "Enter" && e.target && e.target.tagName !== "TEXTAREA") {
            if (_capPaso < 3) {
              e.preventDefault();
              if (_capPaso === 1) {
                mostrarPasoCap(2);
              } else if (_capPaso === 2) {
                if (validarPaso2Cap()) {
                  var prev = document.getElementById("cap-preview-resumen");
                  if (prev) prev.innerHTML = resumenCapHtml();
                  mostrarPasoCap(3);
                }
              }
            }
          }
        });
      }
    }

    function bindFotoCaptura() {
      var btnElegir = document.getElementById("btn-elegir-foto");
      var fileInp = document.getElementById("cap-foto-input");
      var preWrap = document.getElementById("cap-foto-preview-wrap");
      var preImg = document.getElementById("cap-foto-preview");
      var preNom = document.getElementById("cap-foto-nombre");
      var preTam = document.getElementById("cap-foto-tam");
      var btnQuitar = document.getElementById("btn-quitar-foto");

      var boxIa = document.getElementById("box-analizar-recibo-ia");
      var estadoIa = document.getElementById("recibo-ia-estado");
      var previewIa = document.getElementById("recibo-ia-preview");
      var btnAnalizarIa = document.getElementById("btn-analizar-recibo-ia");

      var _esLecheOGasto = _tipoCapturaActual === "leche" || _tipoCapturaActual === "gasto";
      if (_fotoActual && _esLecheOGasto && boxIa) {
        boxIa.style.display = "block";
      }

      if (btnElegir && fileInp) {
        btnElegir.addEventListener("click", function () {
          fileInp.click();
        });
      }

      if (btnQuitar) {
        btnQuitar.addEventListener("click", function () {
          _fotoActual = null;
          _facturaIaFotoRuta = null;
          if (fileInp) fileInp.value = "";
          if (preWrap) preWrap.style.display = "none";
          if (preImg) preImg.src = "";
          if (boxIa) boxIa.style.display = "none";
          if (estadoIa) estadoIa.innerHTML = "";
          if (previewIa) {
            previewIa.style.display = "none";
            previewIa.innerHTML = "";
          }
        });
      }

      if (fileInp) {
        fileInp.addEventListener("change", function () {
          var file = fileInp.files && fileInp.files[0];
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

              var compressedB64 = canvas.toDataURL("image/jpeg", 0.82);
              var tamKb = Math.round((compressedB64.length * 3) / 4 / 1024);

              _fotoActual = {
                base64: compressedB64,
                nombre: file.name || ("foto_" + _tipoCapturaActual + ".jpg"),
                tam_kb: tamKb
              };

              if (preImg) preImg.src = compressedB64;
              if (preNom) preNom.textContent = _fotoActual.nombre;
              if (preTam) preTam.textContent = "Optimizada (" + tamKb + " KB) · Lista para adjuntar";
              if (preWrap) preWrap.style.display = "flex";

              _facturaIaFotoRuta = null;
              if (boxIa && (_tipoCapturaActual === "leche" || _tipoCapturaActual === "gasto")) {
                boxIa.style.display = "block";
                var txtAyudaIa = _tipoCapturaActual === "leche"
                  ? "Presiona <b>Leer Recibo con IA</b> para digitalizar los días de ordeño automáticamente."
                  : "Presiona <b>Leer Factura con IA</b> para llenar categoría, monto y proveedor automáticamente.";
                if (estadoIa) {
                  estadoIa.innerHTML = "<div style='display:flex; align-items:center; gap:8px; padding:6px 10px; background:rgba(47,82,51,0.06); border-radius:6px;'>"
                    + "<span class='chip verde' style='font-size:11px;'>Foto cargada</span>"
                    + "<span style='color:var(--texto-suave); font-size:12px;'>" + txtAyudaIa + "</span>"
                    + "</div>";
                }
                if (previewIa) {
                  previewIa.style.display = "none";
                  previewIa.innerHTML = "";
                }
              }
            };
            img.src = ev.target.result;
          };
          reader.readAsDataURL(file);
        });
      }

      function bindTablaReciboIa(res) {
        function recalcularSuma() {
          var total = 0;
          qa(".inp-ia-litros", previewIa).forEach(function (inp) {
            var val = parseFloat(inp.value);
            if (!isNaN(val) && val > 0) total += val;
          });
          total = Math.round(total * 10) / 10;
          var sumSpan = document.getElementById("ia-suma-total");
          if (sumSpan) sumSpan.textContent = total;
          var fLitros = document.getElementById("cap-litros");
          if (fLitros) fLitros.value = "";
        }

        qa(".inp-ia-litros", previewIa).forEach(function (inp) {
          inp.addEventListener("input", recalcularSuma);
        });

        previewIa.addEventListener("click", function (e) {
          var btnQ = e.target && e.target.closest ? e.target.closest(".btn-ia-quitar-fila") : null;
          if (btnQ) {
            var tr = btnQ.closest("tr");
            if (tr) {
              tr.remove();
              recalcularSuma();
            }
          }
        });

        var btnAgregar = document.getElementById("btn-ia-agregar-dia");
        if (btnAgregar) {
          btnAgregar.addEventListener("click", function () {
            var tbody = previewIa.querySelector("tbody");
            if (!tbody) return;
            var filas = qa("tr.ia-fila-dia", tbody);
            var ultimoDia = filas.length + 1;
            var ultimaFecha = "";
            if (filas.length) {
              var ultInpF = filas[filas.length - 1].querySelector(".inp-ia-fecha");
              if (ultInpF && ultInpF.value) {
                try {
                  var d = new Date(ultInpF.value + "T12:00:00");
                  d.setDate(d.getDate() + 1);
                  ultimaFecha = d.toISOString().slice(0, 10);
                } catch (ex) { /* noop */ }
              }
            }
            if (!ultimaFecha) ultimaFecha = new Date().toISOString().slice(0, 10);

            var tr = document.createElement("tr");
            tr.className = "ia-fila-dia";
            tr.style.borderBottom = "1px solid var(--borde)";
            tr.innerHTML = "<td style='text-align:center; font-weight:bold; font-size:12px; color:var(--texto-suave);'>" + ultimoDia + "</td>"
              + "<td><input type='date' class='inp-ia-fecha' value='" + esc(ultimaFecha) + "' style='width:100%; padding:4px 6px; font-size:12px; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
              + "<td><input type='number' step='0.1' min='0' class='inp-ia-litros' value='0' style='width:100%; padding:4px 6px; font-size:12.5px; font-weight:bold; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
              + "<td><input type='text' class='inp-ia-notas' value='' placeholder='Opcional' style='width:100%; padding:4px 6px; font-size:11.5px; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
              + "<td style='text-align:center;'><button type='button' class='btn-ia-quitar-fila tema-btn' style='padding:2px 6px; font-size:11px; color:var(--color-rojo-txt); cursor:pointer;' title='Eliminar fila'>✕</button></td>";
            tbody.appendChild(tr);
            var nuevoInpL = tr.querySelector(".inp-ia-litros");
            if (nuevoInpL) nuevoInpL.addEventListener("input", recalcularSuma);
            recalcularSuma();
          });
        }

        var btnGuardarQ = document.getElementById("btn-guardar-quincena-ia");
        if (btnGuardarQ) {
          btnGuardarQ.addEventListener("click", function () {
            var filas = qa("tr.ia-fila-dia", previewIa);
            if (!filas.length) {
              alert("No hay días para guardar.");
              return;
            }

            var listaDias = [];
            for (var i = 0; i < filas.length; i++) {
              var tr = filas[i];
              var fInp = tr.querySelector(".inp-ia-fecha");
              var lInp = tr.querySelector(".inp-ia-litros");
              var nInp = tr.querySelector(".inp-ia-notas");

              var fechaVal = fInp ? fInp.value.trim() : "";
              var litVal = lInp ? parseFloat(lInp.value) : 0;
              var notVal = nInp ? nInp.value.trim() : "";

              if (!fechaVal) {
                alert("La fila " + (i + 1) + " no tiene fecha válida.");
                if (fInp) fInp.focus();
                return;
              }
              if (isNaN(litVal) || litVal < 0) {
                alert("La fila " + (i + 1) + " tiene litros inválidos.");
                if (lInp) lInp.focus();
                return;
              }

              listaDias.push({
                dia: i + 1,
                fecha: fechaVal,
                litros: litVal,
                notas: notVal
              });
            }

            btnGuardarQ.disabled = true;
            btnGuardarQ.innerHTML = "⏳ Guardando " + listaDias.length + " días...";

            var inpMonto = document.getElementById("ia-monto-pagado");
            var montoPagado = inpMonto && inpMonto.value ? parseFloat(inpMonto.value) : null;

            var payloadGuardar = {
              periodo: res.periodo || "",
              dias: listaDias,
              // La foto ya quedó guardada al analizarla (foto_ruta); solo se
              // manda foto_base64 como respaldo si por algo no vino foto_ruta.
              foto_ruta: res.foto_ruta || null,
              foto_base64: res.foto_ruta ? null : (_fotoActual ? _fotoActual.base64 : null),
              observaciones: (q("#cap-notas") && q("#cap-notas").value) || "",
              monto_pagado: (montoPagado && montoPagado > 0) ? montoPagado : null,
              acopiador: (res.acopiador && res.acopiador !== "No especificado") ? res.acopiador : null
            };

            fetch("/api/leche/guardar-quincena", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payloadGuardar)
            })
            .then(function (r) {
              if (r.status === 401) { window.location = "/login"; throw new Error("No autorizado"); }
              if (!r.ok) throw new Error("HTTP " + r.status);
              return r.json();
            })
            .then(function (data) {
              btnGuardarQ.disabled = false;
              btnGuardarQ.innerHTML = icon("save", 15) + "Guardar Todos los Días en la Bitácora";

              if (!data.ok) {
                alert("Error al guardar: " + (data.error || "Desconocido"));
                return;
              }

              if (previewIa) previewIa.style.display = "none";
              if (estadoIa) {
                var msgIngreso = data.ingreso_id
                  ? "También se registró el <b>ingreso en Finanzas</b> (Venta de leche) con esa misma foto como respaldo."
                  : "La foto quedó archivada como respaldo en el historial.";
                estadoIa.innerHTML = "<div style='padding:12px; background:rgba(47,82,51,0.12); border-left:4px solid var(--verde-marca); border-radius:6px;'>"
                  + "<div style='font-size:14px; font-weight:bold; color:var(--verde-marca);'>🎉 ¡Quincena guardada con éxito!</div>"
                  + "<div style='margin-top:4px; font-size:12.5px;'>Se registraron <b>" + data.guardados + " días</b> con un total de <b>" + data.total_litros + " Litros</b>. " + msgIngreso + "</div>"
                  + "<div style='margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;'>"
                  + "<button type='button' id='btn-ia-ir-leche' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:bold; padding:6px 12px; font-size:12px; border:none; border-radius:4px; cursor:pointer;'>" + icon("milk", 13) + "Ver en Producción de Leche</button>"
                  + (data.ingreso_id ? "<button type='button' id='btn-ia-ir-finanzas' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:bold; padding:6px 12px; font-size:12px; border:none; border-radius:4px; cursor:pointer;'>" + icon("banknote", 13) + "Ver en Finanzas</button>" : "")
                  + "</div>"
                  + "</div>";

                var btnIrLeche = document.getElementById("btn-ia-ir-leche");
                if (btnIrLeche) {
                  btnIrLeche.addEventListener("click", function () {
                    irAVista("leche");
                    cargar(true);
                    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
                  });
                }
                var btnIrFinanzas = document.getElementById("btn-ia-ir-finanzas");
                if (btnIrFinanzas) {
                  btnIrFinanzas.addEventListener("click", function () {
                    irAVista("finanzas");
                    cargar(true);
                    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
                  });
                }
              }

              actualizarBadges();
            })
            .catch(function (err) {
              btnGuardarQ.disabled = false;
              btnGuardarQ.innerHTML = icon("save", 15) + "Reintentar Guardar";
              alert("Error al guardar: " + err.message);
            });
          });
        }
      }

      function renderizarTablaReciboIa(res) {
        var dias = res.dias || [];
        var per = res.periodo || "Quincena detectada";
        var motor = res.motor || "IA";
        var totDetectado = res.total_litros_detectado != null ? Number(res.total_litros_detectado) : null;

        var sumaInicial = 0;
        dias.forEach(function (d) { sumaInicial += (Number(d.litros) || 0); });
        sumaInicial = Math.round(sumaInicial * 10) / 10;

        var fLitros = document.getElementById("cap-litros");
        if (fLitros) fLitros.value = sumaInicial;
        var fNotas = document.getElementById("cap-notas");
        if (fNotas && !fNotas.value) {
          fNotas.value = "Recibo " + per + " (" + dias.length + " días)";
        }

        var hEstado = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;'>"
          + "<div><span class='chip verde'>✓ Lectura Exitosa</span> <b>" + esc(per) + "</b> · " + dias.length + " días leídos</div>"
          + "<div style='font-size:11px; color:var(--texto-suave);'>Motor: " + esc(motor) + "</div>"
          + "</div>";

        if (res.discrepancia_total) {
          hEstado += "<div style='margin-top:6px; padding:6px 10px; background:rgba(217,119,6,0.1); border-left:3px solid #d97706; border-radius:4px; font-size:12px;'>"
            + "⚠️ <b>Discrepancia en la suma:</b> La suma de los días da <b>" + sumaInicial + " L</b> pero en el papel dice <b>" + totDetectado + " L</b>. Por favor revisa los días abajo y ajusta cualquier número si es necesario."
            + "</div>";
        }
        if (estadoIa) estadoIa.innerHTML = hEstado;

        var hTabla = "<div style='background:var(--superficie); border:1px solid var(--borde); border-radius:8px; padding:10px; margin-top:10px;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>"
          + "<h4 style='margin:0; font-size:13px; display:flex; align-items:center; gap:6px;'>" + icon("table", 14) + "Desglose Diario Detectado</h4>"
          + "<button type='button' id='btn-ia-agregar-dia' class='tema-btn' style='font-size:11.5px; padding:3px 8px;'>" + icon("plus", 12) + "Agregar Día</button>"
          + "</div>"
          + "<div class='tabla-scroll' style='max-height:280px; overflow-y:auto;'>"
          + "<table style='width:100%; border-collapse:collapse;' id='tabla-recibo-dias'>"
          + "<thead><tr style='border-bottom:2px solid var(--borde-fuerte); text-align:left;'>"
          + "<th style='width:36px; text-align:center;'>Día</th>"
          + "<th style='min-width:130px;'>Fecha</th>"
          + "<th style='min-width:95px;'>Litros</th>"
          + "<th>Notas</th>"
          + "<th style='width:28px;'></th>"
          + "</tr></thead>"
          + "<tbody>";

        dias.forEach(function (d, idx) {
          var diaNum = d.dia || (idx + 1);
          var fIso = d.fecha || "";
          var lts = d.litros != null ? d.litros : 0;
          var not = d.notas || "";

          hTabla += "<tr class='ia-fila-dia' style='border-bottom:1px solid var(--borde);'>"
            + "<td style='text-align:center; font-weight:bold; font-size:12px; color:var(--texto-suave);'>" + diaNum + "</td>"
            + "<td><input type='date' class='inp-ia-fecha' value='" + esc(fIso) + "' style='width:100%; padding:4px 6px; font-size:12px; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
            + "<td><input type='number' step='0.1' min='0' class='inp-ia-litros' value='" + esc(lts) + "' style='width:100%; padding:4px 6px; font-size:12.5px; font-weight:bold; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
            + "<td><input type='text' class='inp-ia-notas' value='" + esc(not) + "' placeholder='Opcional' style='width:100%; padding:4px 6px; font-size:11.5px; border-radius:4px; border:1px solid var(--borde-fuerte);'></td>"
            + "<td style='text-align:center;'><button type='button' class='btn-ia-quitar-fila tema-btn' style='padding:2px 6px; font-size:11px; color:var(--color-rojo-txt); cursor:pointer;' title='Eliminar fila'>✕</button></td>"
            + "</tr>";
        });

        hTabla += "</tbody>"
          + "<tfoot>"
          + "<tr style='background:rgba(47,82,51,0.05); font-weight:bold;'>"
          + "<td colspan='2' style='text-align:right; padding:8px;'>Suma Total:</td>"
          + "<td style='padding:8px;'><span id='ia-suma-total' style='color:var(--verde-marca); font-size:14px;'>" + sumaInicial + "</span> L</td>"
          + "<td colspan='2' style='font-size:11px; color:var(--texto-suave); padding:8px;'>" + (totDetectado != null ? ("(Papel: " + totDetectado + " L)") : "") + "</td>"
          + "</tr>"
          + "</tfoot>"
          + "</table></div>";

        var montoDetectado = res.valor_total_pagado != null ? res.valor_total_pagado : "";
        var precioLitroDetectado = res.precio_litro != null ? fmtMoneda(res.precio_litro) + "/L" : "";
        hTabla += "<div style='margin-top:12px; padding:10px; background:rgba(47,82,51,0.05); border:1px dashed var(--verde-marca); border-radius:8px;'>"
          + "<label style='font-size:12.5px; font-weight:700; display:flex; align-items:center; gap:6px;'>" + icon("banknote", 14) + "Monto Pagado en esta Quincena ($) <span style='font-weight:normal; font-size:11px; color:var(--texto-suave);'>(opcional -- si lo llenas, se registra el ingreso en Finanzas)</span></label>"
          + "<input type='number' step='1' min='0' id='ia-monto-pagado' value='" + esc(montoDetectado) + "' placeholder='ej. 10184000' style='width:100%; padding:8px; margin-top:6px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:bold;'>"
          + (precioLitroDetectado ? "<small style='color:var(--texto-suave); display:block; margin-top:4px;'>Precio detectado en el recibo: <b>" + esc(precioLitroDetectado) + "</b></small>" : "")
          + "</div>";

        hTabla += "<button type='button' id='btn-guardar-quincena-ia' class='tema-btn' style='margin-top:12px; width:100%; background:var(--verde-marca); color:#fff; font-weight:bold; font-size:13.5px; padding:10px; border:none; border-radius:6px; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px;'>"
          + icon("save", 15) + "Guardar Todos los Días en la Bitácora"
          + "</button>"
          + "</div>";

        if (previewIa) {
          previewIa.innerHTML = hTabla;
          previewIa.style.display = "block";
          bindTablaReciboIa(res);
        }
      }

      function rellenarCamposFactura(res) {
        _facturaIaFotoRuta = res.foto_ruta || null;
        if (estadoIa) estadoIa.innerHTML = "";
        var selCat = document.getElementById("cap-fin-categoria");
        var fConcepto = document.getElementById("cap-fin-concepto");
        var fMonto = document.getElementById("cap-fin-monto");
        var fContraparte = document.getElementById("cap-fin-contraparte");
        var fFecha = document.getElementById("cap-fecha");
        if (selCat && res.categoria_sugerida) selCat.value = res.categoria_sugerida;
        if (selCat) selCat.dispatchEvent(new Event("change"));
        if (fConcepto && res.concepto) fConcepto.value = res.concepto;
        if (fMonto && res.monto_total != null) fMonto.value = res.monto_total;
        if (fContraparte && res.proveedor) fContraparte.value = res.proveedor;
        if (fFecha && res.fecha) fFecha.value = res.fecha;
        if (previewIa) {
          previewIa.style.display = "block";
          previewIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--verde-marca);'>"
            + "✅ <b>Factura leída.</b> Revisa los campos de arriba (categoría, concepto, monto, proveedor) antes de guardar."
            + (res.observaciones ? "<br><small>" + esc(res.observaciones) + "</small>" : "")
            + "</div>";
        }
      }

      if (btnAnalizarIa) {
        btnAnalizarIa.addEventListener("click", function () {
          if (!_fotoActual || !_fotoActual.base64) {
            alert("Por favor toma o selecciona primero una foto del recibo o factura.");
            return;
          }
          var esGasto = _tipoCapturaActual === "gasto";
          btnAnalizarIa.disabled = true;
          btnAnalizarIa.innerHTML = "⏳ Analizando...";
          if (estadoIa) {
            var txtEsperaIa = esGasto
              ? "<b style='color:var(--verde-marca);'>Digitalizando factura con Visión Artificial...</b><br><small style='color:var(--texto-suave);'>Extrayendo monto, fecha, proveedor y categoría. Esto toma 5-10 segundos.</small>"
              : "<b style='color:var(--verde-marca);'>Digitalizando recibo con Visión Artificial...</b><br><small style='color:var(--texto-suave);'>Extrayendo días, fechas y litros de las anotaciones manuscritas. Esto toma 5-10 segundos.</small>";
            estadoIa.innerHTML = "<div style='display:flex; align-items:center; gap:10px; padding:10px; background:rgba(47,82,51,0.06); border-radius:6px;'>"
              + "<span style='font-size:18px;'>⏳</span><div>" + txtEsperaIa + "</div></div>";
          }
          if (previewIa) previewIa.style.display = "none";

          var fechaRef = (q("#cap-fecha") && q("#cap-fecha").value) || new Date().toISOString().slice(0, 10);
          var url = esGasto ? "/api/finanzas/analizar-factura" : "/api/leche/analizar-recibo";
          fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              foto_base64: _fotoActual.base64,
              fecha_referencia: fechaRef
            })
          })
          .then(function (r) {
            if (r.status === 401) { window.location = "/login"; throw new Error("No autorizado"); }
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
          })
          .then(function (res) {
            btnAnalizarIa.disabled = false;
            btnAnalizarIa.innerHTML = icon("sparkles", 14) + (esGasto ? "Re-analizar Factura" : "Re-analizar Recibo");

            if (!res.ok) {
              if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-rojo-txt);'>❌ <b>Error:</b> " + esc(res.error || "No se pudo procesar la imagen.") + "</div>";
              return;
            }

            if (esGasto) {
              if (!res.es_factura) {
                var obsF = res.observaciones || "No se detectó una factura o recibo legible en la imagen.";
                if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-ambar);'>⚠️ <b>No parece una factura válida:</b><br><small style='color:var(--texto);'>" + esc(obsF) + "</small></div>";
                return;
              }
              rellenarCamposFactura(res);
              return;
            }

            if (!res.es_recibo_leche || !res.dias || !res.dias.length) {
              var obs = res.observaciones || "No se detectaron anotaciones numéricas de producción lechera diaria.";
              if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-ambar);'>⚠️ <b>No parece un recibo de leche válido:</b><br><small style='color:var(--texto);'>" + esc(obs) + "</small></div>";
              return;
            }

            renderizarTablaReciboIa(res);
          })
          .catch(function (err) {
            btnAnalizarIa.disabled = false;
            btnAnalizarIa.innerHTML = icon("sparkles", 14) + "Reintentar";
            if (estadoIa) estadoIa.innerHTML = "<div class='aviso' style='border-left:4px solid var(--color-rojo-txt);'>❌ Error de conexión: " + esc(err.message) + "</div>";
          });
        });
      }
    }

    function bindCamposFinanza() {
      var selCat = document.getElementById("cap-fin-categoria");
      var wrapLitros = document.getElementById("cap-fin-litros-wrap");
      if (!selCat || !wrapLitros) return;
      function toggleLitros() { wrapLitros.style.display = selCat.value === "VENTA_LECHE" ? "block" : "none"; }
      selCat.addEventListener("change", toggleLitros);
      toggleLitros();
    }

    function bindTrasladoMasivo() {
      var chk = document.getElementById("cap-trasl-masivo");
      var tagWrap = document.getElementById("cap-trasl-tag-wrap");
      var fTag = document.getElementById("cap-tag");
      var fOrigen = document.getElementById("cap-pot-orig");
      if (!chk || !tagWrap) return;
      function toggle() {
        if (chk.checked) {
          tagWrap.style.display = "none";
          if (fTag) { fTag.required = false; fTag.value = ""; }
          if (fOrigen) fOrigen.required = true;
        } else {
          tagWrap.style.display = "";
          if (fTag) fTag.required = true;
          if (fOrigen) fOrigen.required = false;
        }
      }
      chk.addEventListener("change", toggle);
      toggle();
    }

    // Destete: el operario busca por el arete de la VACA (lo recuerda
    // mejor que el de una cría reciente); la cría activa sin destetar se
    // resuelve sola vía /api/cria-activa y queda editable por si hay
    // mellizos o el auto-match falla.
    function bindDesteteBusquedaCria() {
      if (_tipoCapturaActual !== "destete") return;
      var fVaca = document.getElementById("cap-tag");
      var fCria = document.getElementById("cap-cria-tag");
      var info = document.getElementById("cap-destete-cria-info");
      if (!fVaca || !fCria || !info) return;
      var timerBusqueda = null;
      function buscar() {
        var vaca = fVaca.value.trim();
        if (!vaca) { info.textContent = ""; return; }
        info.textContent = "Buscando cría de " + vaca + "...";
        fetch("/api/cria-activa?vaca=" + encodeURIComponent(vaca))
          .then(function (r) { return r.json(); })
          .then(function (res) {
            if (res && res.encontrada) {
              fCria.value = res.cria_tag;
              info.textContent = "✓ Cría encontrada: " + res.cria_tag;
            } else {
              info.textContent = "No se encontró cría activa sin destetar para esta vaca -- escriba el arete manualmente.";
            }
          })
          .catch(function () { info.textContent = ""; });
      }
      fVaca.addEventListener("blur", buscar);
      fVaca.addEventListener("input", function () {
        clearTimeout(timerBusqueda);
        timerBusqueda = setTimeout(buscar, 600);
      });
    }

    // Parto: alterna el bloque de "Cría 2" cuando el tipo elegido es
    // GEMELAR (parto múltiple), ver camposHtmlCaptura('parto').
    var TIPOS_EVENTO_SIN_CRIA = ["ABORTO", "REABSORCION", "MOMIFICACION", "MACERACION", "MUERTE_FETAL"];
    function bindTipoEventoParto() {
      var sel = document.getElementById("cap-tipo-evento");
      var wrapCria = document.getElementById("cap-parto-cria-wrap");
      var wrap2 = document.getElementById("cap-gemelo2-wrap");
      var labelCria1 = document.getElementById("cap-cria1-label");
      var avisoPerdida = document.getElementById("cap-perdida-aviso");
      if (!sel || !wrap2) return;
      function toggle() {
        var esGemelar = sel.value === "GEMELAR";
        var esPerdida = TIPOS_EVENTO_SIN_CRIA.indexOf(sel.value) !== -1;
        wrap2.style.display = esGemelar ? "block" : "none";
        if (wrapCria) wrapCria.style.display = esPerdida ? "none" : "block";
        if (avisoPerdida) avisoPerdida.style.display = esPerdida ? "block" : "none";
        // La distocia solo aplica a nacimientos, no a pérdidas.
        var wrapDis = document.getElementById("cap-distocia-wrap");
        if (wrapDis) wrapDis.style.display = esPerdida ? "none" : "block";
        if (labelCria1) labelCria1.firstChild.textContent = esGemelar ? "Arete de la Cría 1: " : "Arete de la Cría (Nuevo): ";
      }
      sel.addEventListener("change", toggle);
      toggle();
    }

    // Sugerencia de arete de cría para Parto (Madre + "-" + digitoAno, ej. n088-6, JA457-6 como en SG).
    function bindSugerenciaTagCriaParto() {
      if (_tipoCapturaActual !== "parto") return;
      var fMadre = document.getElementById("cap-tag");
      var fFecha = document.getElementById("cap-fecha");
      var fCria = document.getElementById("cap-cria-tag");
      var hint = document.getElementById("cap-cria-sugerido-hint");
      var fCria2 = document.getElementById("cap-cria2-tag");
      if (!fMadre || !fCria) return;

      var _tagModificadoManualmente = false;

      fCria.addEventListener("input", function () {
        _tagModificadoManualmente = true;
      });

      function calcularSugerencia() {
        var madre = (fMadre.value || "").trim();
        if (!madre) {
          if (hint) hint.innerHTML = "";
          return null;
        }
        var fecha = (fFecha && fFecha.value) || new Date().toISOString().slice(0, 10);
        var anoStr = fecha.split("-")[0] || String(new Date().getFullYear());
        var digitoAno = anoStr.slice(-1); // e.g. 2026 -> "6"
        var sug = madre + "-" + digitoAno;
        return sug;
      }

      function actualizarSugerencia(forzar) {
        var sug = calcularSugerencia();
        if (!sug) return;
        if (hint) {
          hint.innerHTML = "Sugerencia de arete: <span style='text-decoration:underline;'>" + esc(sug) + "</span> <small style='color:var(--texto-suave); font-weight:normal;'>(opcional, clic para aplicar)</small>";
        }
        if (forzar || !_tagModificadoManualmente || !fCria.value.trim()) {
          fCria.value = sug;
          _tagModificadoManualmente = false;
        }
        if (fCria2 && !fCria2.value.trim()) {
          fCria2.placeholder = "ej. " + sug + "-2";
        }
      }

      if (hint) {
        hint.addEventListener("click", function () {
          var sug = calcularSugerencia();
          if (sug) {
            fCria.value = sug;
            _tagModificadoManualmente = false;
            fCria.focus();
          }
        });
      }

      fMadre.addEventListener("input", function () { actualizarSugerencia(false); });
      fMadre.addEventListener("change", function () { actualizarSugerencia(false); });
      if (fFecha) {
        fFecha.addEventListener("change", function () { actualizarSugerencia(false); });
      }

      if (fMadre.value.trim()) {
        actualizarSugerencia(false);
      }
    }

    function ejecutarTrasladoMasivo(fecha) {
      var origen = (q("#cap-pot-orig") && q("#cap-pot-orig").value || "").trim();
      var destino = (q("#cap-pot-dest") && q("#cap-pot-dest").value || "").trim();
      var motivo = (q("#cap-motivo") && q("#cap-motivo").value) || null;
      var feed = document.getElementById("captura-feedback");
      if (!origen || !destino) {
        if (feed) feed.innerHTML = "<div class='chip rojo' style='font-size:14px; padding:8px 12px;'>❌ Elegí Potrero Origen y Potrero Destino.</div>";
        return;
      }
      if (!window.confirm("¿Mover TODOS los animales activos de \"" + origen + "\" a \"" + destino + "\"?")) return;
      if (feed) feed.innerHTML = "<div class='chip ambar' style='font-size:14px; padding:8px 12px;'>⏳ Moviendo animales...</div>";
      fetch("/api/traslado/masivo", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ potrero_origen: origen, potrero_destino: destino, motivo: motivo, fecha: fecha }),
      }).then(function (r) { return r.json().then(function (b) { return { status: r.status, body: b }; }); })
        .then(function (res) {
          if (res.status >= 200 && res.status < 300 && res.body.ok) {
            enviarTelemetriaSilenciosa("captura_traslado_masivo");
            if (feed) {
              feed.innerHTML = "<div class='chip verde' style='font-size:14px; padding:8px 12px;'>✅ " + res.body.movidos
                + " animal(es) movidos de " + esc(res.body.potrero_origen) + " a " + esc(res.body.potrero_destino) + ".</div>";
            }
            var formEl = document.getElementById("form-captura");
            if (formEl) formEl.reset();
            refrescarCamposCap();
            actualizarBadges();
          } else if (feed) {
            feed.innerHTML = "<div class='chip rojo' style='font-size:14px; padding:8px 12px;'>❌ " + esc((res.body && res.body.error) || "No se pudo mover el lote.") + "</div>";
          }
        }).catch(function (err) {
          if (feed) feed.innerHTML = "<div class='chip rojo' style='font-size:14px; padding:8px 12px;'>❌ " + esc(err && err.message || err) + "</div>";
        });
    }

    refrescarCamposCap();
    wireStepperCap();
    if (window.__capPasoInicial) {
      mostrarPasoCap(window.__capPasoInicial);
      window.__capPasoInicial = null;
    } else {
      mostrarPasoCap(1);
    }

    qa("button[data-cap-tipo]").forEach(function (b) {
      b.addEventListener("click", function () {
        qa("button[data-cap-tipo]").forEach(function (x) { x.classList.remove("act"); });
        b.classList.add("act");
        _tipoCapturaActual = b.getAttribute("data-cap-tipo");
        _capTipo = _tipoCapturaActual;
        _fotoActual = null;
        // Al cambiar el tipo en el paso 1 se regeneran los campos del paso
        // 2 en segundo plano (el operario sigue en el paso 1).
        refrescarCamposCap();
      });
    });

    var form = document.getElementById("form-captura");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var fecha = (q("#cap-fecha") && q("#cap-fecha").value) || new Date().toISOString().slice(0, 10);

        var chkTrasladoMasivo = document.getElementById("cap-trasl-masivo");
        if (_tipoCapturaActual === "traslado" && chkTrasladoMasivo && chkTrasladoMasivo.checked) {
          ejecutarTrasladoMasivo(fecha);
          return;
        }

        var payload = {};
        // Aborto/Pérdida (y sus subtipos) usan el mismo formulario de Parto,
        // con tipo_evento eligiendo el subtipo -- un solo tipo de evento/tabla
        // en el backend, distinguido por payload.tipo_evento.
        var tipoEnvio = _tipoCapturaActual;

        if (_tipoCapturaActual === "parto") {
          payload.tipo_evento = (q("#cap-tipo-evento") && q("#cap-tipo-evento").value) || "PARTO";
          var esPerdidaEnvio = TIPOS_EVENTO_SIN_CRIA.indexOf(payload.tipo_evento) !== -1;
          payload.vaca_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.id_cria_tag = esPerdidaEnvio ? null : ((q("#cap-cria-tag") && q("#cap-cria-tag").value || "").trim() || null);
          payload.sexo_cria = (q("#cap-sexo") && q("#cap-sexo").value) || "HEMBRA";
          payload.estado_cria = esPerdidaEnvio ? "MUERTO" : ((q("#cap-estado-cria") && q("#cap-estado-cria").value) || "VIVO");
          payload.peso_nacimiento = parseFloat(q("#cap-peso-nacer") && q("#cap-peso-nacer").value) || null;
          payload.potrero_cria = (q("#cap-pot-cria") && q("#cap-pot-cria").value || "").trim() || null;
          payload.potrero_madre = (q("#cap-pot-madre") && q("#cap-pot-madre").value || "").trim() || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || "";
          payload.distocia = (q("#cap-distocia") && q("#cap-distocia").value === "SI") && !esPerdidaEnvio;
          var toroPadre = (typeof obtenerToroPadreSeleccionado === "function") ? obtenerToroPadreSeleccionado() : null;
          if (toroPadre) {
            payload.padre_tag = toroPadre;
            payload.toro = toroPadre;
          }
          if (payload.tipo_evento === "GEMELAR") {
            payload.gemelo = {
              id_cria_tag: (q("#cap-cria2-tag") && q("#cap-cria2-tag").value || "").trim() || null,
              sexo_cria: (q("#cap-sexo2") && q("#cap-sexo2").value) || "HEMBRA",
              estado_cria: (q("#cap-estado-cria2") && q("#cap-estado-cria2").value) || "VIVO",
              peso_nacimiento: parseFloat(q("#cap-peso-nacer2") && q("#cap-peso-nacer2").value) || null,
            };
          }
        } else if (_tipoCapturaActual === "destete") {
          payload.cria_tag = (q("#cap-cria-tag") && q("#cap-cria-tag").value || "").trim();
          payload.peso_kg = parseFloat(q("#cap-peso") && q("#cap-peso").value) || null;
          payload.potrero_cria = (q("#cap-pot-cria") && q("#cap-pot-cria").value || "").trim() || null;
          payload.peso_madre_kg = parseFloat(q("#cap-peso-madre") && q("#cap-peso-madre").value) || null;
          payload.cond_corporal_madre = parseFloat(q("#cap-cc-madre") && q("#cap-cc-madre").value) || null;
          payload.potrero_madre = (q("#cap-pot-madre") && q("#cap-pot-madre").value || "").trim() || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || "";
        } else if (_tipoCapturaActual === "manejo") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.tipo_manejo = (q("#cap-tipo-manejo") && q("#cap-tipo-manejo").value) || null;
          payload.producto = (q("#cap-producto") && q("#cap-producto").value || "").trim() || null;
          payload.lote_producto = (q("#cap-lote-producto") && q("#cap-lote-producto").value || "").trim() || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value || "").trim() || null;
        } else if (_tipoCapturaActual === "secado") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.cond_corporal = parseFloat(q("#cap-cc") && q("#cap-cc").value) || null;
          payload.potrero_destino = (q("#cap-pot-secado") && q("#cap-pot-secado").value || "").trim() || null;
          payload.motivo = (q("#cap-motivo-secado") && q("#cap-motivo-secado").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || "";
        } else if (_tipoCapturaActual === "pesaje") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.peso_kg = parseFloat(q("#cap-peso") && q("#cap-peso").value) || null;
          payload.evento = "PESAJE";
        } else if (_tipoCapturaActual === "tratamiento") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.producto = (q("#cap-producto") && q("#cap-producto").value || "").trim();
          payload.principio_activo = (q("#cap-principio") && q("#cap-principio").value || "").trim() || null;
          payload.dosis = (q("#cap-dosis") && q("#cap-dosis").value) || null;
          payload.via = (q("#cap-via") && q("#cap-via").value) || "IM";
          payload.dias_retiro_leche = parseInt(q("#cap-ret-leche") && q("#cap-ret-leche").value || 0, 10);
          payload.dias_retiro_carne = parseInt(q("#cap-ret-carne") && q("#cap-ret-carne").value || 0, 10);
          payload.diagnostico = (q("#cap-diag") && q("#cap-diag").value) || null;
        } else if (_tipoCapturaActual === "traslado") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.potrero_origen = (q("#cap-pot-orig") && q("#cap-pot-orig").value) || null;
          payload.potrero_destino = (q("#cap-pot-dest") && q("#cap-pot-dest").value || "").trim();
          payload.motivo = (q("#cap-motivo") && q("#cap-motivo").value) || null;
        } else if (_tipoCapturaActual === "celo") {
          payload.vaca_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.am_pm = (q("#cap-am-pm") && q("#cap-am-pm").value) || "AM";
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        } else if (_tipoCapturaActual === "servicio") {
          payload.vaca_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.tipo_servicio = (q("#cap-tipo-serv") && q("#cap-tipo-serv").value) || "IA";
          payload.toro_pajilla = (q("#cap-toro") && q("#cap-toro").value) || null;
          payload.inseminador = (q("#cap-inseminador") && q("#cap-inseminador").value) || null;
        } else if (_tipoCapturaActual === "leche") {
          payload.litros = parseFloat(q("#cap-litros") && q("#cap-litros").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        } else if (_tipoCapturaActual === "venta") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.comprador = (q("#cap-venta-comprador") && q("#cap-venta-comprador").value || "").trim();
          payload.precio = parseFloat(q("#cap-venta-precio") && q("#cap-venta-precio").value) || null;
          payload.peso_kg = parseFloat(q("#cap-venta-peso") && q("#cap-venta-peso").value) || null;
          payload.motivo = (q("#cap-venta-motivo") && q("#cap-venta-motivo").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        } else if (_tipoCapturaActual === "muerte") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.causa_presunta = (q("#cap-causa") && q("#cap-causa").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        } else if (_tipoCapturaActual === "gasto") {
          var finCategoria = (q("#cap-fin-categoria") && q("#cap-fin-categoria").value) || "OTRO_EGRESO";
          var CATEGORIAS_INGRESO = ["VENTA_LECHE", "OTRO_INGRESO"];
          payload.categoria = finCategoria;
          payload.tipo_finanza = CATEGORIAS_INGRESO.indexOf(finCategoria) !== -1 ? "INGRESO" : "EGRESO";
          payload.concepto = (q("#cap-fin-concepto") && q("#cap-fin-concepto").value || "").trim();
          payload.monto = parseFloat(q("#cap-fin-monto") && q("#cap-fin-monto").value) || 0;
          payload.litros = parseFloat(q("#cap-fin-litros") && q("#cap-fin-litros").value) || null;
          payload.contraparte = (q("#cap-fin-contraparte") && q("#cap-fin-contraparte").value) || null;
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim() || null;
          payload.potrero = (q("#cap-fin-potrero") && q("#cap-fin-potrero").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value) || null;
        } else if (_tipoCapturaActual === "tarea") {
          var objTipo = (q("#cap-tarea-obj") && q("#cap-tarea-obj").value) || "animal";
          payload.tipo_objetivo = objTipo.toUpperCase();
          if (objTipo === "animal") {
            payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
            payload.tag = payload.animal_tag;
          } else if (objTipo === "potrero") {
            payload.potrero_nombre = (q("#cap-tarea-potrero") && q("#cap-tarea-potrero").value || "").trim();
            payload.potrero = payload.potrero_nombre;
          }
          payload.tipo_tarea = (q("#cap-tarea-tipo") && q("#cap-tarea-tipo").value) || "GENERAL";
          var txtDesc = (q("#cap-tarea-desc") && q("#cap-tarea-desc").value || "").trim();
          var prefix = (objTipo === "animal" && payload.animal_tag) ? (payload.animal_tag + ": ") : ((objTipo === "potrero" && payload.potrero_nombre) ? (payload.potrero_nombre + ": ") : "");
          payload.mensaje = prefix + txtDesc;
          payload.descripcion = txtDesc;
          payload.asignado_a = (q("#cap-tarea-asignado") && q("#cap-tarea-asignado").value || "").trim() || "Encargado";
          payload.prioridad = (q("#cap-tarea-prioridad") && q("#cap-tarea-prioridad").value) || "NORMAL";
          payload.hora = (q("#cap-tarea-hora") && q("#cap-tarea-hora").value) || null;
        } else if (_tipoCapturaActual === "palpacion") {
          payload.animal_tag = (q("#cap-tag") && q("#cap-tag").value || "").trim();
          payload.vaca_tag = payload.animal_tag;
          payload.tag = payload.animal_tag;
          payload.metodo = (q("#cap-palp-metodo") && q("#cap-palp-metodo").value) || "TACTO";
          payload.resultado = (q("#cap-palp-resultado") && q("#cap-palp-resultado").value) || "PREÑADA";
          var diasGest = parseInt(q("#cap-palp-dias") && q("#cap-palp-dias").value, 10);
          payload.dias_gestacion = (!isNaN(diasGest) && diasGest > 0) ? diasGest : null;
          payload.reproductor = (q("#cap-palp-toro") && q("#cap-palp-toro").value || "").trim() || null;
          payload.toro_pajuela = payload.reproductor;
          payload.hallazgo = (q("#cap-palp-hallazgo") && q("#cap-palp-hallazgo").value || "").trim() || null;
          payload.cond_corporal = parseFloat(q("#cap-cc") && q("#cap-cc").value) || null;
          payload.peso_kg = parseFloat(q("#cap-peso") && q("#cap-peso").value) || null;
          payload.responsable = (q("#cap-palp-responsable") && q("#cap-palp-responsable").value || "").trim() || null;
          payload.veterinario = payload.responsable;
          payload.detalle = (q("#cap-notas") && q("#cap-notas").value || "").trim() || null;
          payload.notas = payload.detalle;
        } else if (_tipoCapturaActual === "pajuela") {
          payload.codigo_toro = (q("#cap-paj-toro") && q("#cap-paj-toro").value || "").trim();
          payload.toro = payload.codigo_toro;
          payload.raza = (q("#cap-paj-raza") && q("#cap-paj-raza").value || "").trim() || null;
          payload.canastilla = (q("#cap-paj-canastilla") && q("#cap-paj-canastilla").value || "").trim() || null;
          payload.cantidad = parseInt(q("#cap-paj-cant") && q("#cap-paj-cant").value || 1, 10);
          payload.costo = parseFloat(q("#cap-paj-costo") && q("#cap-paj-costo").value) || 0.0;
          payload.procedencia = (q("#cap-paj-procedencia") && q("#cap-paj-procedencia").value || "").trim() || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value || "").trim() || null;
        } else if (_tipoCapturaActual === "nitrogeno") {
          payload.dias_intervalo = parseInt(q("#cap-nitr-intervalo") && q("#cap-nitr-intervalo").value || 21, 10);
          payload.proxima_recarga = (q("#cap-nitr-prox") && q("#cap-nitr-prox").value) || null;
          payload.proveedor = (q("#cap-nitr-proveedor") && q("#cap-nitr-proveedor").value || "").trim() || null;
          payload.costo = parseFloat(q("#cap-nitr-costo") && q("#cap-nitr-costo").value) || null;
          payload.notas = (q("#cap-notas") && q("#cap-notas").value || "").trim() || null;
        }

        // Adjuntar foto opcional. Si ya se analizó con IA (leche/gasto), la
        // foto quedó guardada en ese momento -- se enlaza por ruta en vez de
        // volver a subir los mismos bytes.
        if (_tipoCapturaActual === "gasto" && _facturaIaFotoRuta) {
          payload.foto_ruta = _facturaIaFotoRuta;
        } else if (_fotoActual && _fotoActual.base64) {
          payload.foto_base64 = _fotoActual.base64;
          payload.foto_nombre = _fotoActual.nombre;
        }

        var feed = document.getElementById("captura-feedback");

        function mostrarExito(online) {
          enviarTelemetriaSilenciosa("captura_" + _tipoCapturaActual);
          var fotoTxt = payload.foto_base64 ? " 📸 (con foto adjunta)" : "";
          if (feed) {
            feed.innerHTML = "<div class='chip " + (online ? "verde" : "ambar") + "' style='font-size:14px; padding:8px 12px;'>"
              + (online ? "✅ Evento" + fotoTxt + " registrado en el servidor." : "💾 Evento" + fotoTxt + " guardado en cola local offline (se enviará al volver la señal).") + "</div>";
            if (_tipoCapturaActual === "parto" && (!payload.tipo_evento || payload.tipo_evento === "PARTO" || payload.tipo_evento === "GEMELAR")) {
              var vMadre = payload.vaca_tag || "";
              var fParto = fecha || new Date().toISOString().slice(0, 10);
              var potMadre = payload.potrero_madre || "";
              var crSexo = payload.sexo_cria || "";
              feed.innerHTML += "<div style='margin-top:10px; padding:10px; background:var(--superficie); border-radius:8px; border:1px solid var(--borde); display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;'>"
                + "<span>🐣 <b>¿Deseas registrar la cría en el inventario ahora?</b></span>"
                + "<button type='button' class='tema-btn' id='btn-crear-cria-parto' style='background:var(--verde-marca); color:#fff; font-weight:700; border:none; padding:6px 12px; border-radius:6px; cursor:pointer; font-size:12px; display:inline-flex; align-items:center; gap:5px;'>"
                + icon("cowCalf", 14) + "Registrar Arete de la Cría</button>"
                + "</div>";
              setTimeout(function () {
                var bCr = document.getElementById("btn-crear-cria-parto");
                if (bCr) {
                  bCr.addEventListener("click", function () {
                    if (typeof mostrarFormularioAnimal === "function") {
                      mostrarFormularioAnimal(null, "", {
                        madre_tag: vMadre,
                        fecha_nacimiento: fParto,
                        potrero: potMadre,
                        sexo: crSexo === "HEMBRA" ? "Hembra" : (crSexo === "MACHO" ? "Macho" : "")
                      });
                    }
                  });
                }
              }, 50);
            }
          }
          mostrarToast(online ? "Guardado ✓" : "Guardado offline, se enviará al volver la señal", online ? "verde" : "ambar");
          vibrarConfirmacion();
          // BLOQUE 4: persistir defaults inteligentes (potrero + tag).
          try {
            var potsG = ["cap-pot-dest", "cap-fin-potrero", "cap-pot-cria", "cap-pot-madre", "cap-pot-orig"];
            for (var ig = 0; ig < potsG.length; ig++) {
              var inpG = q("#" + potsG[ig]);
              if (inpG && (inpG.value || "").trim()) { localStorage.setItem("bitacora_ultimo_potrero", inpG.value.trim()); break; }
            }
            var tagG = (q("#cap-tag") && q("#cap-tag").value || "").trim();
            if (tagG) localStorage.setItem("bitacora_ultimo_tag", tagG);
          } catch (eGuard) { /* almacenamiento no disponible */ }
          _fotoActual = null;
          form.reset();
          refrescarCamposCap();
          actualizarBadges();
          // Tras guardar se vuelve al paso 1 para el siguiente registro.
          mostrarPasoCap(1);
        }

        if (navigator.onLine === false) {
          encolarOffline(tipoEnvio, payload, fecha).then(function () {
            mostrarExito(false);
          });
          return;
        }

        fetch("/api/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ eventos: [{ tipo: tipoEnvio, payload: payload, fecha: fecha }] })
        }).then(function (r) { return r.json(); })
          .then(function (res) {
            if (res.ok && res.procesados > 0) mostrarExito(true);
            else {
              encolarOffline(tipoEnvio, payload, fecha).then(function () { mostrarExito(false); });
            }
          }).catch(function () {
            encolarOffline(tipoEnvio, payload, fecha).then(function () { mostrarExito(false); });
          });
      });
    }
  }

