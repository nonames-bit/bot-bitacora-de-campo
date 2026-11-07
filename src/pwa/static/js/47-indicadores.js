  /* ---------- Indicadores (Más → Indicadores) ----------
     Todos los indicadores del hato con su meta y color (verde = cumple,
     ámbar = cerca, rojo = lejos, gris = sin datos). Los calcula
     /api/indicadores (engine/indicadores.py) con los últimos 12 meses.
     Solo OWNER y ADMIN. Arriba van las listas para actuar: vacas problema
     y lactancias largas. Tocar una tarjeta muestra cómo se calcula. */
  var IND_ICONOS = { reproduccion: "sperm", leche: "milk", carne: "cow", sanidad: "shieldPlus", pasturas: "sprout" };
  var IND_COLOR = { verde: "var(--color-verde-txt)", ambar: "var(--color-ambar-txt)", rojo: "var(--color-rojo-txt)", gris: "var(--texto-suave)" };
  var IND_PALABRA = { verde: "Cumple", ambar: "Cerca", rojo: "Lejos", gris: "Sin datos" };

  function indTarjeta(it) {
    var c = it.color || "gris";
    var base = it.n ? "Con " + it.n + " dato" + (it.n === 1 ? "" : "s") : "Sin datos todavía";
    return "<details class='card ind-card ind-" + esc(c) + "'>"
      + "<summary>"
      + "<span class='ind-nombre'>" + esc(it.nombre) + "</span>"
      + "<span class='ind-valor' style='color:" + IND_COLOR[c] + "'>" + esc(it.texto) + "</span>"
      + "<span class='ind-meta'>" + (it.meta
        ? esc(it.meta) + (it.valor != null ? " · <b style='color:" + IND_COLOR[c] + "'>" + IND_PALABRA[c] + "</b>" : "")
        : (it.valor != null ? "Dato para seguir (sin meta)" : "")) + "</span>"
      + (it.detalle ? "<span class='ind-meta'>" + esc(it.detalle) + "</span>" : "")
      + "</summary>"
      + "<p class='ind-ayuda'>" + esc(it.ayuda || "") + " " + esc(base) + ".</p>"
      + "</details>";
  }

  function indLista(titulo, ico, filas, vacioTxt) {
    var h = "<div class='card ind-lista'><div class='ind-lista-tit'>" + icon(ico, 16) + esc(titulo)
      + " <span class='chip'>" + filas.length + "</span></div>";
    if (!filas.length) return h + "<p class='ind-ayuda'>" + esc(vacioTxt) + "</p></div>";
    h += "<ul>";
    filas.slice(0, 30).forEach(function (f) {
      h += "<li><button type='button' class='ind-ficha' data-tag='" + esc(f.tag) + "'>" + esc(f.tag) + "</button>"
        + (f.nombre ? " <small>" + esc(f.nombre) + "</small>" : "")
        + "<div class='ind-motivo'>" + esc(f.motivo) + "</div></li>";
    });
    if (filas.length > 30) h += "<li><small>y " + (filas.length - 30) + " más…</small></li>";
    return h + "</ul></div>";
  }

  function renderIndicadores(d) {
    var h = "<h3>" + icon("chartBar", 20) + "Indicadores del hato</h3>";
    if (d && d.error) return h + "<p class='aviso'>" + esc(d.error) + "</p>";
    h += erroresHtml(d);
    var r = d.resumen || {};
    h += "<p class='aviso'>Últimos 12 meses (" + esc(fechaCorta(d.desde)) + " a " + esc(fechaCorta(d.hasta)) + "). "
      + "Toque una tarjeta para ver cómo se calcula. Las metas son de referencia para doble propósito.</p>";
    h += "<div class='ind-resumen'>"
      + "<span class='ind-chip ind-verde'>" + (r.verde || 0) + " cumplen</span>"
      + "<span class='ind-chip ind-ambar'>" + (r.ambar || 0) + " cerca</span>"
      + "<span class='ind-chip ind-rojo'>" + (r.rojo || 0) + " lejos</span>"
      + "<span class='ind-chip ind-gris'>" + (r.gris || 0) + " sin datos</span>"
      + "</div>";
    h += indLista("Vacas problema", "alertTriangle", d.vacas_problema || [],
      "Ninguna vaca vacía con más de 150 días de parida ni con 3 servicios o más.");
    h += indLista("Lactancias largas (vacías)", "milk", d.lactancias_largas || [],
      "Ninguna vaca vacía con más de 305 días en leche.");
    (d.grupos || []).forEach(function (g) {
      h += "<h4>" + icon(IND_ICONOS[g.k] || "chartBar", 18) + esc(g.titulo) + "</h4>";
      h += "<div class='ind-grid'>" + (g.items || []).map(indTarjeta).join("") + "</div>";
    });
    return h;
  }

  function bindIndicadores() {
    qa(".ind-ficha").forEach(function (b) {
      b.addEventListener("click", function () {
        var tag = b.getAttribute("data-tag");
        if (tag) abrirFichaDesdeTag(tag);
      });
    });
  }
