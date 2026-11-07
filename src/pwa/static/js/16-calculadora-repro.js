  // ---------- Calculadora reproductiva (Reproducción → pestaña "Calculadora") ----------
  // Cuentas de fechas para cuando no hay registro: "se sirvió hoy, ¿cuándo pare?",
  // "parió hoy, ¿cuándo la sirvieron?", "está preñada de X meses". No guarda nada:
  // todo se calcula en el celular. Mismas reglas que engine/reproductive_engine.py
  // y engine/tareas.py: gestación 283 d, celo cada 21 d, ecografía día 35,
  // palpación día 60, secar 2 meses antes del parto (Jaime, 2026-11-07: se ordeña
  // hasta ese momento), servir desde 45 d posparto.
  var CALC_GESTACION = 283;
  var CALC_RANGO_PARTO = 10;  // un parto normal cae ±10 días de la fecha probable
  var CALC_SECAR_ANTES = 60;
  var CALC_CELO = 21;
  var CALC_ECOGRAFIA = 35;
  var CALC_PALPACION = 60;
  var CALC_SERVIR_POSPARTO = 45;
  var CALC_DIAS_MES = 30;
  var CALC_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  var CALC_DIAS_SEM = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  var _calcModo = "servicio";

  function calcHoyIso() {
    var d = new Date();
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  // Fechas a mediodía local para que el cambio de hora nunca corra un día.
  function calcFecha(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
    return m ? new Date(+m[1], +m[2] - 1, +m[3], 12) : null;
  }
  function calcSumar(f, dias) { return new Date(f.getFullYear(), f.getMonth(), f.getDate() + dias, 12); }
  function calcDiasEntre(a, b) { return Math.round((b - a) / 86400000); }
  function calcTexto(f) {
    return CALC_DIAS_SEM[f.getDay()] + " " + f.getDate() + " " + CALC_MESES[f.getMonth()] + " " + f.getFullYear();
  }
  function calcRelativo(f) {
    var n = calcDiasEntre(calcFecha(calcHoyIso()), f);
    if (n === 0) return "hoy";
    if (n === 1) return "mañana";
    if (n === -1) return "ayer";
    return n > 0 ? "en " + n + " días" : "hace " + (-n) + " días";
  }

  // Filas del resultado: [nombre, fecha, nota, destacada]. Pura, sin DOM.
  function calcularFechasRepro(modo, fechaIso, meses) {
    var f = calcFecha(fechaIso);
    if (!f) return null;
    var filas = [];
    if (modo === "servicio") {
      var parto = calcSumar(f, CALC_GESTACION);
      filas.push(["Si no quedó preñada, vuelve a calentar", calcSumar(f, CALC_CELO), "y otra vez el " + calcTexto(calcSumar(f, 2 * CALC_CELO)), false]);
      filas.push(["Ecografía", calcSumar(f, CALC_ECOGRAFIA), "día " + CALC_ECOGRAFIA, false]);
      filas.push(["Palpación", calcSumar(f, CALC_PALPACION), "día " + CALC_PALPACION, false]);
      filas.push(["Secar", calcSumar(parto, -CALC_SECAR_ANTES), "2 meses antes del parto", false]);
      filas.push(["Parto probable", parto, "entre el " + calcTexto(calcSumar(parto, -CALC_RANGO_PARTO)) + " y el " + calcTexto(calcSumar(parto, CALC_RANGO_PARTO)), true]);
    } else if (modo === "parto") {
      var serv = calcSumar(f, -CALC_GESTACION);
      filas.push(["Servicio probable", serv, "entre el " + calcTexto(calcSumar(serv, -CALC_RANGO_PARTO)) + " y el " + calcTexto(calcSumar(serv, CALC_RANGO_PARTO)), true]);
      filas.push(["Se puede volver a servir desde", calcSumar(f, CALC_SERVIR_POSPARTO), CALC_SERVIR_POSPARTO + " días después del parto", false]);
      filas.push(["Para un ternero por año, preñarla antes del", calcSumar(f, 365 - CALC_GESTACION), "a los " + (365 - CALC_GESTACION) + " días del parto", false]);
    } else if (modo === "prenada") {
      var m = parseInt(meses, 10);
      if (!(m >= 1 && m <= 9)) return null;
      var gest = m * CALC_DIAS_MES;
      var partoP = calcSumar(f, CALC_GESTACION - gest);
      var secar = calcSumar(partoP, -CALC_SECAR_ANTES);
      filas.push(["Servicio aproximado", calcSumar(f, -gest), "hace unos " + m + (m === 1 ? " mes" : " meses"), false]);
      filas.push(["Secar", secar, secar < calcFecha(calcHoyIso()) ? "ya debería estar seca" : "2 meses antes del parto", false]);
      filas.push(["Parto probable", partoP, "entre el " + calcTexto(calcSumar(partoP, -15)) + " y el " + calcTexto(calcSumar(partoP, 15)), true]);
    } else {
      return null;
    }
    return filas;
  }

  function calcResultadoHtml(fecha, meses) {
    var filas = calcularFechasRepro(_calcModo, fecha, meses);
    if (!filas) return "<p class='aviso'>Escoja una fecha.</p>";
    var h = "<div class='calc-filas'>";
    filas.forEach(function (r) {
      h += "<div class='calc-fila" + (r[3] ? " calc-destacada" : "") + "'>"
        + "<div class='calc-nombre'>" + esc(r[0]) + "</div>"
        + "<div class='calc-fecha'><b>" + esc(calcTexto(r[1])) + "</b> <span class='calc-rel'>· " + esc(calcRelativo(r[1])) + "</span></div>"
        + (r[2] ? "<div class='calc-nota'>" + esc(r[2]) + "</div>" : "")
        + "</div>";
    });
    h += "</div>";
    if (_calcModo === "prenada") h += "<p class='aviso'>La palpación por meses tiene margen de 2 semanas. Con ecografía o la fecha del servicio sale más exacto.</p>";
    return h;
  }

  function renderCalculadoraRepro(fecha) {
    fecha = fecha || calcHoyIso();
    var modos = [
      ["servicio", "Se sirvió / inseminó"],
      ["parto", "Parió"],
      ["prenada", "Está preñada de…"]
    ];
    var etiqueta = { servicio: "Fecha del servicio", parto: "Fecha del parto", prenada: "Fecha de la palpación" }[_calcModo];
    var h = "<div class='card calc-card'>"
      + "<div class='lt-titulo'>" + icon("hourglass", 16) + "Calculadora de fechas</div>"
      + "<p class='aviso' style='margin:0 0 8px;'>Para sacar cuentas rápidas. No guarda nada en el registro.</p>"
      + "<div class='gen-filtros' role='group' aria-label='Qué pasó'>";
    modos.forEach(function (m) {
      h += "<button type='button' class='chip calc-modo" + (_calcModo === m[0] ? " act" : "") + "' data-calc-modo='" + m[0] + "'>" + esc(m[1]) + "</button>";
    });
    h += "</div><div class='calc-campos'>"
      + "<label>" + esc(etiqueta) + "<input type='date' id='calc-fecha' value='" + esc(fecha) + "'></label>";
    if (_calcModo === "prenada") {
      h += "<label>Meses de preñez<select id='calc-meses'>";
      for (var i = 1; i <= 9; i++) h += "<option value='" + i + "'" + (i === 3 ? " selected" : "") + ">" + i + (i === 1 ? " mes" : " meses") + "</option>";
      h += "</select></label>";
    }
    h += "</div><div id='calc-resultado'>" + calcResultadoHtml(fecha, 3) + "</div></div>";
    return h;
  }

  function calcRefrescar() {
    var out = document.getElementById("calc-resultado");
    var fEl = document.getElementById("calc-fecha");
    var mEl = document.getElementById("calc-meses");
    if (out) out.innerHTML = calcResultadoHtml(fEl && fEl.value, mEl && mEl.value);
  }
  function calcCambiarModo(modo) {
    var card = document.querySelector(".calc-card");
    if (!card) return;
    var fEl = document.getElementById("calc-fecha");
    var fecha = fEl && fEl.value;
    _calcModo = modo;
    var tmp = document.createElement("div");
    tmp.innerHTML = renderCalculadoraRepro(fecha);
    card.parentNode.replaceChild(tmp.firstChild, card);
  }
  document.addEventListener("click", function (e) {
    var b = e.target && e.target.closest ? e.target.closest("[data-calc-modo]") : null;
    if (b) calcCambiarModo(b.getAttribute("data-calc-modo"));
  });
  ["input", "change"].forEach(function (ev) {
    document.addEventListener(ev, function (e) {
      var id = e.target && e.target.id;
      if (id === "calc-fecha" || id === "calc-meses") calcRefrescar();
    });
  });
