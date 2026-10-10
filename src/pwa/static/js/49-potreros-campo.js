  /* ---------- Potreros: ¿están todos? (consulta del operario) ----------
     Jaime (2026-10-10): el operario necesita ver qué animales hay en cada
     potrero para verificar en campo si están todos o falta alguno. Solo
     lectura: las marcas de "lo vi" son ayuda en pantalla, no crean
     registros, y se guardan en este celular solo por hoy. Los datos vienen
     de /api/potreros/listado en una sola respuesta; el service worker guarda
     la última copia, así que funciona sin señal en el potrero. */
  var _potListado = null;
  var _potSel = null; // id del potrero abierto (null = lista de potreros)
  var _potSoloFaltan = false;
  var _potConteos = null; // historial de /api/potreros/conteos (null = sin cargar)
  var _potVolverTag = null; // animal cuya ficha se abrió desde el conteo

  function _potEsOperario() {
    return ((window.__usuarioActual && window.__usuarioActual.rol) || "").toUpperCase() === "TRABAJADOR";
  }

  function _potClaveMarcas() {
    return "potreros_marcas_" + new Date().toISOString().slice(0, 10);
  }
  function _potLeerMarcas() {
    try {
      var m = JSON.parse(localStorage.getItem(_potClaveMarcas()) || "{}");
      return m && typeof m === "object" ? m : {};
    } catch (e) { return {}; }
  }
  var _potMarcas = _potLeerMarcas();
  function _potGuardarMarcas() {
    try {
      // Las marcas de días anteriores ya no sirven: se borran.
      for (var i = localStorage.length - 1; i >= 0; i--) {
        var k = localStorage.key(i);
        if (k && k.indexOf("potreros_marcas_") === 0 && k !== _potClaveMarcas()) localStorage.removeItem(k);
      }
      localStorage.setItem(_potClaveMarcas(), JSON.stringify(_potMarcas));
    } catch (e) { /* sin almacenamiento: las marcas viven mientras la app esté abierta */ }
  }
  function _potVistos(p) {
    var m = _potMarcas[String(p.id)] || {};
    return p.animales.filter(function (a) { return m[a.tag]; }).length;
  }

  function renderPotreros(d) {
    _potListado = d || { potreros: [] };
    var pots = _potListado.potreros || [];
    var sel = _potSel === null ? null : pots.filter(function (p) { return String(p.id) === String(_potSel); })[0];
    if (sel) return _renderPotreroDetalle(sel);
    _potSel = null;

    // Para OWNER/ADMIN el conteo vive dentro de Inventario (Jaime,
    // 2026-10-10); el operario lo tiene directo en su barra.
    var h = (_potEsOperario() ? "" : "<button type='button' class='tema-btn pot-a-inventario'>← Inventario</button>")
      + "<h3>" + icon("fence", 20) + "Contar por potrero</h3>"
      + "<p class='aviso'>Toque un potrero para ver sus animales y márquelos a medida que los vea. "
      + "Sirve sin señal con la última lista descargada"
      + (_potListado.fecha ? " (" + esc(_potListado.fecha) + ")" : "") + ".</p>";
    if (!pots.length) return h + "<p class='aviso'>No hay animales activos en ningún potrero.</p>";
    h += "<div class='pot-lista'>";
    pots.forEach(function (p) {
      var vistos = _potVistos(p);
      var estado = vistos === 0 ? ""
        : vistos >= p.total ? "<span class='chip verde'>" + icon("check", 12) + "Todos</span>"
          : "<span class='chip ambar'>" + vistos + " de " + p.total + "</span>";
      h += "<button type='button' class='card pot-item' data-pot='" + esc(p.id) + "'>"
        + "<span class='pot-ico'>" + icon("grass", 20) + "</span>"
        + "<span class='pot-info'><b>" + esc(p.nombre) + "</b><small>" + p.total + (p.total === 1 ? " animal" : " animales") + "</small></span>"
        + estado + "</button>";
    });
    h += "</div>";
    return h + _potHtmlHistorial(null, 10);
  }

  // Últimos conteos guardados (de todos los potreros o de uno).
  function _potHtmlHistorial(potId, max) {
    if (!_potConteos) return "<div class='pot-historial' data-pot-hist='" + esc(potId === null ? "" : potId) + "'></div>";
    var lista = _potConteos.filter(function (c) { return potId === null || String(c.potrero_id) === String(potId); }).slice(0, max);
    var h = "<div class='pot-historial'><h4>" + icon("clipboard", 16) + (potId === null ? "Últimos conteos guardados" : "Conteos anteriores de este potrero") + "</h4>";
    if (!lista.length) return h + "<p class='aviso'>Todavía no hay conteos guardados.</p></div>";
    lista.forEach(function (c) {
      var completo = c.vistos >= c.total;
      var faltan = (c.faltantes || []);
      h += "<div class='card pot-hist-item'>"
        + "<div class='pot-hist-cab'><b>" + esc(c.potrero || "Potrero") + "</b>"
        + "<span class='chip " + (completo ? "verde" : "ambar") + "'>" + c.vistos + " de " + c.total + "</span></div>"
        + "<small>" + esc(c.fecha || "") + (c.hora ? " · " + esc(c.hora) : "") + (c.por ? " · " + esc(c.por) : "") + "</small>"
        + (completo ? "<small class='pot-hist-ok'>Estaban todos.</small>"
          : "<small class='pot-hist-falta'>Faltaron: " + faltan.map(esc).join(", ") + "</small>")
        + "</div>";
    });
    return h + "</div>";
  }

  function _potCargarHistorial() {
    fetch("/api/potreros/conteos?limite=60").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (d) {
      _potConteos = (d && d.conteos) || [];
      if (actual === "potreros") _potRepintar(true);
    }).catch(function () { /* sin señal y sin copia: no se muestra historial */ });
  }

  function _potHoraAhora() {
    var d = new Date();
    return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  }

  // Guarda el conteo como registro (auditoría). Va por /api/sync y, sin
  // señal, queda en la cola offline hasta que haya conexión.
  function _potGuardarConteo(p) {
    var m = _potMarcas[String(p.id)] || {};
    var vistos = [], faltantes = [];
    p.animales.forEach(function (a) { (m[a.tag] ? vistos : faltantes).push(a.tag); });
    if (!vistos.length) {
      mostrarToast("Marque los animales que vio antes de guardar.", "ambar");
      return;
    }
    var pregunta = faltantes.length
      ? "Faltan " + faltantes.length + ": " + faltantes.slice(0, 12).join(", ") + (faltantes.length > 12 ? "…" : "") + ".\n¿Guardar el conteo así?"
      : "Están todos (" + p.total + "). ¿Guardar el conteo?";
    if (!confirm(pregunta)) return;
    var fecha = new Date().toISOString().slice(0, 10);
    var hora = _potHoraAhora();
    var nombreUsuario = (window.__usuarioActual && window.__usuarioActual.nombre) || "";
    var sinSenal = navigator.onLine === false;
    enviarEventoLt("conteo_potrero", {
      potrero_id: p.id, potrero_nombre: p.nombre, hora: hora,
      vistos: vistos, faltantes: faltantes
    });
    // Se muestra de una en el historial, aunque aún no haya subido.
    _potConteos = _potConteos || [];
    _potConteos.unshift({ fecha: fecha, hora: hora, potrero_id: p.id, potrero: p.nombre, total: p.total,
      vistos: vistos.length, faltantes: faltantes, por: nombreUsuario });
    delete _potMarcas[String(p.id)];
    _potGuardarMarcas();
    _potSel = null;
    _potRepintar();
    window.scrollTo(0, 0);
    mostrarToast(sinSenal ? "Conteo guardado. Se envía cuando haya señal." : "Conteo guardado.", "verde");
  }

  function _renderPotreroDetalle(p) {
    var m = _potMarcas[String(p.id)] || {};
    var vistos = _potVistos(p);
    var faltan = p.total - vistos;
    var h = "<button type='button' class='tema-btn pot-volver'>← Potreros</button>"
      + "<h3>" + icon("grass", 20) + esc(p.nombre) + "</h3>"
      + "<div class='card pot-resumen" + (faltan === 0 ? " completo" : "") + "' role='status' aria-live='polite'>"
      + (faltan === 0
        ? icon("checkCircle", 18) + "<b>Están todos: " + p.total + " de " + p.total + ".</b>"
        : "<b>Vistos " + vistos + " de " + p.total + "</b><span>Faltan " + faltan + "</span>")
      + "</div>"
      + "<div class='pot-herramientas'>"
      + "<input type='search' id='pot-buscar' placeholder='Buscar número o nombre' aria-label='Buscar animal' autocomplete='off'>"
      + "<label class='pot-filtro'><input type='checkbox' id='pot-solo-faltan'" + (_potSoloFaltan ? " checked" : "") + "> Solo los que faltan</label>"
      + "</div>"
      + "<div class='pot-animales'>";
    p.animales.forEach(function (a) {
      var visto = !!m[a.tag];
      var nombre = a.nombre && a.nombre !== "—" ? a.nombre : "";
      h += "<label class='pot-animal" + (visto ? " visto" : "") + "' data-tag='" + esc(a.tag) + "' data-busca='"
        + esc((a.tag + " " + nombre).toLowerCase()) + "'" + (_potSoloFaltan && visto ? " hidden" : "") + ">"
        + "<input type='checkbox' data-tag='" + esc(a.tag) + "'" + (visto ? " checked" : "") + ">"
        + "<span class='pot-tag'>" + esc(a.tag) + "</span>"
        + "<span class='pot-nombre'>" + esc(nombre) + "<small>" + esc(a.categoria_desc || a.categoria || "") + (a.edad && a.edad !== "S/D" ? " · " + esc(a.edad) : "") + "</small></span>"
        + "<button type='button' class='pot-ver-ficha' data-tag='" + esc(a.tag) + "' aria-label='Ver ficha de " + esc(a.tag) + "'>"
        + icon("eye", 16) + "<span>Ficha</span></button>"
        + "</label>";
    });
    h += "</div>";
    h += "<button type='button' class='btn-guardar-manga pot-guardar'>" + icon("save", 16) + "Guardar conteo</button>";
    if (vistos) h += "<button type='button' class='btn-sec pot-borrar'>Empezar de nuevo</button>";
    return h + _potHtmlHistorial(p.id, 3);
  }

  function bindPotreros() {
    if (!vista) return;
    qa(".pot-item", vista).forEach(function (b) {
      b.addEventListener("click", function () {
        _potSel = b.getAttribute("data-pot");
        _potSoloFaltan = false;
        _potRepintar();
        window.scrollTo(0, 0);
      });
    });
    var volver = vista.querySelector(".pot-volver");
    if (volver) volver.addEventListener("click", function () {
      _potSel = null;
      _potRepintar();
      window.scrollTo(0, 0);
    });
    qa(".pot-animal input[type=checkbox]", vista).forEach(function (cb) {
      cb.addEventListener("change", function () {
        var k = String(_potSel);
        _potMarcas[k] = _potMarcas[k] || {};
        if (cb.checked) _potMarcas[k][cb.getAttribute("data-tag")] = 1;
        else delete _potMarcas[k][cb.getAttribute("data-tag")];
        _potGuardarMarcas();
        _potRepintar(true);
      });
    });
    var solo = vista.querySelector("#pot-solo-faltan");
    if (solo) solo.addEventListener("change", function () {
      _potSoloFaltan = solo.checked;
      _potRepintar(true);
    });
    var buscar = vista.querySelector("#pot-buscar");
    if (buscar) buscar.addEventListener("input", function () {
      var t = buscar.value.trim().toLowerCase();
      qa(".pot-animal", vista).forEach(function (el) {
        var oculto = (t && el.getAttribute("data-busca").indexOf(t) === -1)
          || (_potSoloFaltan && el.classList.contains("visto"));
        el.hidden = !!oculto;
      });
    });
    // Ver la ficha (color, foto) cuando el número no se lee bien, y volver al
    // mismo potrero con las marcas intactas (están en _potMarcas).
    qa(".pot-ver-ficha", vista).forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        _potVolverTag = b.getAttribute("data-tag");
        abrirFichaDesdeTag(_potVolverTag);
        _potMostrarVolver();
      });
    });
    var aInv = vista.querySelector(".pot-a-inventario");
    if (aInv) aInv.addEventListener("click", function () {
      irAVista("inventario");
      cargar();
      window.scrollTo(0, 0);
    });
    var guardar = vista.querySelector(".pot-guardar");
    if (guardar) guardar.addEventListener("click", function () {
      var p = (_potListado.potreros || []).filter(function (x) { return String(x.id) === String(_potSel); })[0];
      if (p) _potGuardarConteo(p);
    });
    var borrar = vista.querySelector(".pot-borrar");
    if (borrar) borrar.addEventListener("click", function () {
      if (!confirm("¿Borrar las marcas de este potrero y empezar a contar de nuevo?")) return;
      delete _potMarcas[String(_potSel)];
      _potGuardarMarcas();
      _potRepintar(true);
    });
  }

  // Vuelve a pintar con los datos ya descargados (no pide nada al servidor).
  // Con mantenerScroll el operario no pierde el sitio en una lista larga.
  function _potRepintar(mantenerScroll) {
    if (!vista || !_potListado) return;
    var y = window.scrollY;
    var busq = vista.querySelector("#pot-buscar");
    var textoBusq = mantenerScroll && busq ? busq.value : "";
    montarVista(vista, renderPotreros(_potListado), false);
    bindPotreros();
    if (textoBusq) {
      var nb = vista.querySelector("#pot-buscar");
      if (nb) { nb.value = textoBusq; nb.dispatchEvent(new Event("input")); }
    }
    if (mantenerScroll) window.scrollTo(0, y);
  }

  // Botón fijo "Volver al conteo" mientras se mira la ficha. Usa el atrás
  // del historial (igual que el botón atrás del celular) para no apilar vistas.
  function _potMostrarVolver() {
    var viejo = document.getElementById("btn-volver-conteo");
    if (viejo) viejo.remove();
    var p = (_potListado && _potListado.potreros || []).filter(function (x) { return String(x.id) === String(_potSel); })[0];
    var b = document.createElement("button");
    b.type = "button";
    b.id = "btn-volver-conteo";
    b.innerHTML = icon("arrowRight", 16) + "<span>Volver al conteo" + (p ? " de " + esc(p.nombre) : "") + "</span>";
    b.addEventListener("click", function () {
      b.remove();
      if (_historialListo && window.history.length > 1) {
        window.history.back();
      } else {
        irAVista("potreros");
        cargar();
      }
    });
    document.body.appendChild(b);
  }
  function _potQuitarVolver() {
    var b = document.getElementById("btn-volver-conteo");
    if (b) b.remove();
  }

  // Al volver de la ficha se deja a la vista el animal que se fue a mirar.
  function _potIrAlAnimal() {
    if (!_potVolverTag || !vista) return;
    var tag = _potVolverTag;
    _potVolverTag = null;
    var fila = qa(".pot-animal", vista).filter(function (el) { return el.getAttribute("data-tag") === tag; })[0];
    if (fila && fila.scrollIntoView) fila.scrollIntoView({ block: "center" });
  }

  // El operario abre "Potreros" en el potrero, donde casi nunca hay señal:
  // se descarga la lista al entrar a la app para que quede guardada.
  function precargarPotreros() {
    try { fetch("/api/potreros/listado").catch(function () {}); } catch (e) { /* sin red */ }
  }
