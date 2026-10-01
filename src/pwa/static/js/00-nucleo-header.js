  var vista = document.getElementById("vista");
  var actual = "tablero";
  function q(s) { return document.querySelector(s); }
  function qa(s, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(s)); }
  // Alias a ja-core.js (cargar antes que app.js) — los helpers puros se
  // definen en /static/ja-core.js (BLOQUE 3 fase 1; 100% autocontenidos:
  // no usan vista/actual/q/qa/fetchJSON); aquí solo se aliasan para no
  // tocar ninguna llamada. Las constantes CALF_HEAD/COW_BODY_FILL/
  // PARTO_HEADS/DESTETE_ICON solo se usan vía icon(), por eso quedan
  // encapsuladas en JA sin alias local.
  var esc = window.JA.esc;
  // Permite solo <b> y <br> después de escapar. Cualquier otra etiqueta queda texto.
  function htmlBasico(s) {
    return esc(s).replace(/&lt;(\/?)(b|br)\s*\/?&gt;/gi, "<$1$2>");
  }
  var mostrarToast = window.JA.mostrarToast;
  var vibrarConfirmacion = window.JA.vibrarConfirmacion;
  var chipEstado = window.JA.chipEstado;
  var vacio = window.JA.vacio;
  var tabla = window.JA.tabla;
  var kpi = window.JA.kpi;
  var erroresHtml = window.JA.erroresHtml;
  var grafico = window.JA.grafico;
  var fechaCorta = window.JA.fechaCorta;
  var fmtMoneda = window.JA.fmtMoneda;

  var icon = window.JA.icon;
  var dot = window.JA.dot;

  // Un solo botón "Descargar" por pantalla: lleva a Reportes con el de
  // esta sección resaltado (ver 47-reportes.js).
  function barraDescargaSeccion(seccion) {
    return botonDescargar(seccion);
  }

  var _pasturasGraficoActivo = "mapa_potreros";

  /* ---------- Vaquita Interactiva y Animaciones del Header ---------- */
  var _vacaEstadoActual = null; // 'dia', 'noche', 'cria', 'toro', 'ternero'
  var _vacaBubbleTimer = null;
  var _vacaFraseIdx = 0;
  var _vacaContexto = { esFicha: false, esParida: false, esToro: false, esTernero: false };

  function esAnimalTernero(f) {
    if (!f) return false;
    var catSg = String(f.categoria_sg || "").toUpperCase().trim();
    if (catSg === "CH" || catSg === "CM" || catSg.indexOf("CRIA") >= 0 || catSg.indexOf("TERNER") >= 0) {
      return true;
    }
    if (f.estado_fisiologico && (f.estado_fisiologico.codigo === "CRIA_MACHO" || f.estado_fisiologico.codigo === "CRIA_HEMBRA" || f.estado_fisiologico.icono === "calf")) {
      return true;
    }
    if (f.estado_reproductivo && /TERNER/i.test(f.estado_reproductivo.badge || f.estado_reproductivo.titulo || "")) {
      return true;
    }
    var ultP = f.ultimo_parto || {};
    var tieneP = Boolean(ultP && ultP.fecha) || Boolean(f.partos && f.partos.length);
    if (f.edad_dias != null && f.edad_dias < 365 && !tieneP) {
      return true;
    }
    if (/\b(?:TERNERO|TERNERA|CRIA|BECERRO|BECERRA)\b/i.test(catSg + " " + (f.nombre || "") + " " + (f.notas || "") + " " + (f.tag || ""))) {
      return true;
    }
    return false;
  }

  function esAnimalToro(f) {
    if (!f) return false;
    if (esAnimalTernero(f)) return false;
    var catSg = String(f.categoria_sg || "").toUpperCase();
    var sx = String(f.sexo || "").toUpperCase();
    return (sx === "M" || sx === "MACHO") && (
      String(f.tag || "").match(/^T\d+/i)
      || /TORO|REPRODUCTOR|PADROTE|CEBA/i.test(catSg + " " + (f.nombre || "") + " " + (f.notas || "") + " " + (f.tag || ""))
      || (f.estado_reproductivo && String(f.estado_reproductivo.codigo || "").indexOf("TORO") >= 0)
      || (f.edad_dias == null || f.edad_dias >= 365)
    );
  }

  function obtenerHoraColombia() {
    try {
      var str = new Date().toLocaleString("en-US", { timeZone: "America/Bogota" });
      var d = new Date(str);
      return { hora: d.getHours(), min: d.getMinutes() };
    } catch (e) {
      var d2 = new Date();
      return { hora: d2.getHours(), min: d2.getMinutes() };
    }
  }

  function actualizarVacaHeader(opts) {
    if (opts) {
      if (opts.esFicha !== undefined) {
        _vacaContexto.esFicha = Boolean(opts.esFicha);
        if (!_vacaContexto.esFicha) {
          _vacaContexto.esToro = false;
          _vacaContexto.esParida = false;
          _vacaContexto.esTernero = false;
        }
      }
      if (opts.esTernero !== undefined) _vacaContexto.esTernero = Boolean(opts.esTernero);
      if (opts.esParida !== undefined) _vacaContexto.esParida = Boolean(opts.esParida);
      if (opts.esToro !== undefined) _vacaContexto.esToro = Boolean(opts.esToro);
    } else {
      // Llamada periódica sin parámetros (tick de reloj o cambio de tema).
      // Si estamos en la vista de ficha o la ficha está montada en el DOM, preservamos el contexto del animal activo
      var estaEnFicha = (typeof actual !== "undefined" && actual === "ficha")
        || Boolean(document.body && document.body.getAttribute("data-tag"))
        || Boolean(document.getElementById("ficha") && window.__ultimaFicha && (document.getElementById("ficha").offsetParent !== null || document.getElementById("ficha").innerHTML.indexOf("ficha-head") !== -1));

      if (estaEnFicha && window.__ultimaFicha) {
        _vacaContexto.esFicha = true;
        _vacaContexto.esTernero = esAnimalTernero(window.__ultimaFicha);
        _vacaContexto.esToro = !_vacaContexto.esTernero && esAnimalToro(window.__ultimaFicha);
        _vacaContexto.esParida = !_vacaContexto.esTernero && !_vacaContexto.esToro && Boolean(
          (window.__ultimaFicha.estado_fisiologico && window.__ultimaFicha.estado_fisiologico.codigo === "VACA_ORDENO")
          || (window.__ultimaFicha.lactancia && window.__ultimaFicha.lactancia.estado === "En ordeño" && window.__ultimaFicha.lactancia.del_dias < 200)
          || (window.__ultimaFicha.crias && window.__ultimaFicha.crias.length > 0)
          || (window.__ultimaFicha.categoria_sg && String(window.__ultimaFicha.categoria_sg).toLowerCase().indexOf("parida") >= 0)
        );
      } else if (!estaEnFicha) {
        _vacaContexto.esFicha = false;
        _vacaContexto.esParida = false;
        _vacaContexto.esToro = false;
        _vacaContexto.esTernero = false;
      }
    }

    var img = document.getElementById("header-vaca-img");
    if (!img) return;

    var col = obtenerHoraColombia();
    var esNocheHora = (col.hora > 18 || (col.hora === 18 && col.min >= 30) || col.hora < 5 || (col.hora === 5 && col.min < 30));
    // Día/noche por la hora de la finca, no por el tema oscuro de la app.
    var esNoche = esNocheHora;

    var nuevoEstado = "dia";
    if (_vacaContexto.esFicha && _vacaContexto.esTernero) {
      nuevoEstado = "ternero";
    } else if (_vacaContexto.esFicha && _vacaContexto.esToro) {
      nuevoEstado = "toro";
    } else if (_vacaContexto.esFicha && _vacaContexto.esParida) {
      nuevoEstado = "cria";
    } else if (_vacaContexto.esFicha) {
      nuevoEstado = esNoche ? "noche" : "dia";
    } else if (esNoche) {
      nuevoEstado = "noche";
    } else {
      nuevoEstado = "dia";
    }

    if (nuevoEstado === _vacaEstadoActual) return;
    _vacaEstadoActual = nuevoEstado;

    var vParam = window.__PWA_V__ ? ("?v=" + encodeURIComponent(window.__PWA_V__)) : "";
    // (P1.5) El header animado usa WebP (antes GIF: 763 KB -> ~263 KB). Si el
    // usuario pidió reducir movimiento, se usa el PNG estático equivalente.
    var reduVaca = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    function _assetVaca(base) { return "/static/" + base + (reduVaca ? ".png" : ".webp") + vParam; }
    if (nuevoEstado === "ternero") {
      img.src = _assetVaca("ternero");
      img.alt = "Ternero alegre en el potrero";
      img.title = "Ternero / Cría lactante · Toca para ver estado rápido";
    } else if (nuevoEstado === "toro") {
      img.src = _assetVaca("toro_reproductor");
      img.alt = "Toro reproductor en el potrero";
      img.title = "Toro reproductor / Padrote · Toca para ver estado rápido";
    } else if (nuevoEstado === "cria") {
      img.src = _assetVaca("vaca_con_cria");
      img.alt = "Vaca con su cría en el potrero";
      img.title = "Vaca parida con cría al pie · Toca para ver estado rápido";
    } else if (nuevoEstado === "noche") {
      img.src = _assetVaca("vaca_echada");
      img.alt = "Vaca descansando y rumiando";
      img.title = "Ganado en reposo nocturno · Toca para ver estado rápido";
    } else {
      img.src = _assetVaca("vaca_comiendo");
      img.alt = "Vaca pastando forraje";
      img.title = "Vaca pastando en rotación Voisin · Toca para ver estado rápido";
    }
  }

  var _climaEstadoActual = "soleado";
  function actualizarClimaHeader(climaDatos) {
    if (climaDatos) {
      window.__ultimoClimaPronostico = climaDatos;
    }
    var dClima = window.__ultimoClimaPronostico;
    if (!dClima && window.__datosUltimoTablero && window.__datosUltimoTablero.clima_hoy) {
      dClima = window.__datosUltimoTablero.clima_hoy;
    }
    if (!dClima && window.__datosUltimoPasturas && window.__datosUltimoPasturas.pronostico) {
      dClima = window.__datosUltimoPasturas.pronostico;
    }
    if (!dClima && window.__datosUltimoPasturas && window.__datosUltimoPasturas.pronostico && window.__datosUltimoPasturas.pronostico.dias) {
      dClima = window.__datosUltimoPasturas.pronostico.dias[0];
    }

    var col = obtenerHoraColombia();
    var esNocheHora = (col.hora > 18 || (col.hora === 18 && col.min >= 30) || col.hora < 5 || (col.hora === 5 && col.min < 30));
    // Día/noche por la hora de la finca, no por el tema oscuro de la app.
    var esNoche = esNocheHora;

    // Detección de lluvia en tiempo real:
    // IMPORTANTE: NO basarse en lluvia_mm diaria acumulada ni en prob_lluvia máxima de 24h,
    // ya que en el trópico de Mesetas (Meta) casi cualquier día tiene pronóstico acumulado >= 1.5mm,
    // lo que causaba que la cortina de lluvia animada permaneciera activa 24/7.
    // Solo debe llover sobre las vacas si está lloviendo EN ESTE MOMENTO (telemetría actual).
    var estaLloviendo = false;
    var tieneTelemetriaActual = false;
    var wcode = null;

    if (dClima) {
      if (typeof dClima.esta_lloviendo === "boolean") {
        estaLloviendo = dClima.esta_lloviendo;
        tieneTelemetriaActual = true;
      }
      if (dClima.current) {
        if (typeof dClima.current.esta_lloviendo === "boolean") {
          estaLloviendo = dClima.current.esta_lloviendo;
          tieneTelemetriaActual = true;
        }
        if (dClima.current.weather_code !== undefined && dClima.current.weather_code !== null) {
          wcode = Number(dClima.current.weather_code);
        }
      }
      if (wcode === null && dClima.weather_code !== undefined && dClima.weather_code !== null) {
        wcode = Number(dClima.weather_code);
      }
    }

    if (!tieneTelemetriaActual) {
      var dTabClima = window.__datosUltimoTablero && window.__datosUltimoTablero.clima_hoy;
      if (dTabClima) {
        if (typeof dTabClima.esta_lloviendo === "boolean") {
          estaLloviendo = dTabClima.esta_lloviendo;
          tieneTelemetriaActual = true;
        } else if (dTabClima.current && typeof dTabClima.current.esta_lloviendo === "boolean") {
          estaLloviendo = dTabClima.current.esta_lloviendo;
          tieneTelemetriaActual = true;
        }
        if (wcode === null && dTabClima.current && dTabClima.current.weather_code !== undefined && dTabClima.current.weather_code !== null) {
          wcode = Number(dTabClima.current.weather_code);
        }
      }
    }

    if (!tieneTelemetriaActual) {
      var dPastPron = window.__datosUltimoPasturas && window.__datosUltimoPasturas.pronostico;
      if (dPastPron) {
        if (typeof dPastPron.esta_lloviendo === "boolean") {
          estaLloviendo = dPastPron.esta_lloviendo;
          tieneTelemetriaActual = true;
        } else if (dPastPron.current && typeof dPastPron.current.esta_lloviendo === "boolean") {
          estaLloviendo = dPastPron.current.esta_lloviendo;
          tieneTelemetriaActual = true;
        }
        if (wcode === null && dPastPron.current && dPastPron.current.weather_code !== undefined && dPastPron.current.weather_code !== null) {
          wcode = Number(dPastPron.current.weather_code);
        }
      }
    }

    var hayLluvia = estaLloviendo;

    // Nubes: según código meteorológico WMO en tiempo real si está disponible:
    // WMO 0, 1: despejado / sol radiante
    // WMO 2: parcialmente nublado
    // WMO 3, 45, 48: muy nublado / niebla
    // WMO >= 51: precipitación
    var hayNubes = false;
    if (wcode !== null && !isNaN(wcode)) {
      hayNubes = (wcode >= 2);
    } else if (dClima) {
      var probLluvia = Number(dClima.prob_lluvia_pct) || 0;
      var lluviaMm = Number(dClima.lluvia_mm) || 0;
      hayNubes = (probLluvia >= 65 || lluviaMm >= 8.0);
    }

    var solEl = document.getElementById("header-clima-sol");
    var lunaEl = document.getElementById("header-clima-luna");
    var nubesEl = document.getElementById("header-clima-nubes");
    var lluviaEl = document.getElementById("header-lluvia");

    if (lluviaEl) {
      lluviaEl.style.display = hayLluvia ? "block" : "none";
    }

    if (esNoche) {
      if (solEl) solEl.style.display = "none";
      if (lunaEl) lunaEl.style.display = "inline-flex";
      if (nubesEl) nubesEl.style.display = hayNubes ? "block" : "none";
      _climaEstadoActual = hayLluvia ? "lluvia-noche" : "noche";
    } else {
      if (lunaEl) lunaEl.style.display = "none";
      if (hayLluvia) {
        if (solEl) solEl.style.display = "none";
        if (nubesEl) nubesEl.style.display = "block";
        _climaEstadoActual = "lluvia";
      } else if (hayNubes) {
        if (solEl) solEl.style.display = "none";
        if (nubesEl) nubesEl.style.display = "block";
        _climaEstadoActual = "nublado";
      } else {
        if (solEl) solEl.style.display = "inline-flex";
        if (nubesEl) nubesEl.style.display = "none";
        _climaEstadoActual = "soleado";
      }
    }
  }

  function actualizarLluviaHeader(hayLluvia) {
    actualizarClimaHeader({
      lluvia_mm: hayLluvia ? 5.0 : 0,
      prob_lluvia_pct: hayLluvia ? 90 : 0,
      esta_lloviendo: Boolean(hayLluvia),
      current: {
        esta_lloviendo: Boolean(hayLluvia),
        lluvia_mm: hayLluvia ? 5.0 : 0,
        weather_code: hayLluvia ? 61 : 0
      }
    });
  }
  window.actualizarClimaHeader = actualizarClimaHeader;
  window.actualizarLluviaHeader = actualizarLluviaHeader;

  function tocarVaquitaHeader() {
    if (navigator.vibrate) {
      try { navigator.vibrate([15, 30, 15]); } catch (e) {}
    }
    var img = document.getElementById("header-vaca-img");
    if (img) {
      img.classList.remove("vaca-anim-tap");
      void img.offsetWidth;
      img.classList.add("vaca-anim-tap");
      setTimeout(function () { if (img) img.classList.remove("vaca-anim-tap"); }, 250);
    }

    var bubble = document.getElementById("vaca-bubble");
    if (!bubble) return;

    var dTab = window.__datosUltimoTablero || {};
    var dPast = window.__datosUltimoPasturas || {};
    var totalActivos = dTab.activos || dTab.total_activos || 0;
    var nPotreros = (dTab.por_potrero && dTab.por_potrero.length) || (dPast.potreros && dPast.potreros.length) || 0;

    var topDescanso = null;
    var topDias = -1;
    if (dPast.potreros && dPast.potreros.length) {
      dPast.potreros.forEach(function (p) {
        var dr = Number(p.dias_reposo) || 0;
        if (dr > topDias) { topDias = dr; topDescanso = p.nombre || p.codigo; }
      });
    }

    var frases = [];
    if (_vacaEstadoActual === "ternero") {
      frases.push(icon("calf", 14) + "¡Mmuuu! Ternero alegre y vigoroso correteando en el potrero.");
      frases.push(icon("sprout", 14) + "Cría lactante con excelente vitalidad y buen peso al destete.");
      frases.push(icon("milk", 14) + "Creciendo fuerte al pie de la madre en Ganadería JA.");
    } else if (_vacaEstadoActual === "toro") {
      frases.push(icon("cow", 14) + "¡Toro reproductor de alta genética y vigor en el lote!");
      frases.push(icon("zap", 14) + "Padrote activo transmitiendo ganancia de peso y rusticidad.");
    } else if (_vacaEstadoActual === "cria") {
      frases.push(icon("calf", 14) + "¡Amor maternal! Cría al pie con excelente vitalidad.");
      frases.push(icon("cow", 14) + "Vaca madre en óptima nutrición y lactancia.");
    } else if (_vacaEstadoActual === "noche") {
      frases.push(icon("moon", 14) + "Rumiando en calma bajo la noche llanera.");
      frases.push(icon("moon", 14) + "Vacas en descanso nocturno recuperando energías.");
    } else {
      frases.push(icon("grass", 14) + "Pastando forraje fresco bajo rotación Voisin.");
      frases.push("¡Muuu! " + icon("cow", 14) + "Cero garrapatas y ganado al día.");
    }

    if (_climaEstadoActual === "lluvia" || _climaEstadoActual === "lluvia-noche") {
      frases.push(icon("rain", 14) + "¡Lluvia en la finca! Pastos verdes y buen aforo asegurado.");
    } else if (_climaEstadoActual === "nublado") {
      frases.push(icon("cloud", 14) + "Día fresco y nublado en Mesetas, ideal para el pastoreo.");
    } else if (_climaEstadoActual === "soleado") {
      frases.push(icon("sun", 14) + "Día soleado en la sabana: ganado en pleno pastoreo.");
    }

    if (totalActivos > 0) {
      frases.push(icon("chartBar", 14) + "Hato activo: " + totalActivos + " cabezas registradas.");
    }
    if (nPotreros > 0) {
      frases.push(icon("sprout", 14) + nPotreros + " potreros en descanso y pastoreo.");
    }
    if (topDescanso && topDias > 0) {
      frases.push(icon("grass", 14) + "Más reposo: " + esc(topDescanso) + " (" + topDias + " d).");
    }
    frases.push(icon("sparkles", 14) + "Ganadería JA: genética y trazabilidad 100%.");

    var txt = frases[_vacaFraseIdx % frases.length];
    _vacaFraseIdx++;

    bubble.innerHTML = txt;
    bubble.style.display = "block";
    try {
      if (window.innerWidth > 640) {
        bubble.style.transform = "translateX(-50%)";
        var rect = bubble.getBoundingClientRect();
        if (rect.left < 10) {
          var diffL = 10 - rect.left;
          bubble.style.transform = "translateX(calc(-50% + " + Math.ceil(diffL) + "px))";
        } else if (rect.right > window.innerWidth - 10) {
          var diffR = rect.right - (window.innerWidth - 10);
          bubble.style.transform = "translateX(calc(-50% - " + Math.ceil(diffR) + "px))";
        }
      } else {
        bubble.style.transform = "none";
      }
    } catch (e) { /* noop */ }

    if (_vacaBubbleTimer) clearTimeout(_vacaBubbleTimer);
    _vacaBubbleTimer = setTimeout(function () {
      if (bubble) bubble.style.display = "none";
    }, 4500);
  }

  function setupVacaHeaderInteractivo() {
    var headerPasto = document.getElementById("header-pasto");
    if (headerPasto && !headerPasto.__boundVaca) {
      headerPasto.__boundVaca = true;
      headerPasto.addEventListener("click", function (e) {
        e.stopPropagation();
        tocarVaquitaHeader();
      });
    }
    actualizarVacaHeader();
    actualizarClimaHeader();
  }

