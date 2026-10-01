  /* ---------- Pestañas dentro de una vista (Fase D) ----------
     Las vistas largas (Reproducción, Leche, Sistema) marcan sus bloques con
     marcaPestana("clave") mientras arman el HTML; armarPestanas() los agrupa
     en paneles y pone la barra de pestañas debajo del encabezado. Lo que va
     antes de la primera marca (título, botones de descarga) queda siempre
     visible. La pestaña elegida se recuerda por vista en este navegador. */
  function marcaPestana(clave) { return "<!--pestana:" + clave + "-->"; }

  function pestanaGuardada(vistaId, claves) {
    try {
      var v = localStorage.getItem("ja_pestana_" + vistaId);
      if (v && claves.indexOf(v) !== -1) return v;
    } catch (e) { /* almacenamiento no disponible */ }
    return claves[0];
  }

  function armarPestanas(vistaId, html, lista) {
    var partes = String(html).split(/<!--pestana:([a-z0-9_]+)-->/);
    var cabecera = partes[0];
    var paneles = {};
    for (var i = 1; i < partes.length; i += 2) paneles[partes[i]] = (paneles[partes[i]] || "") + (partes[i + 1] || "");
    var visibles = lista.filter(function (p) { return paneles[p.k]; });
    if (visibles.length < 2) return cabecera + visibles.map(function (p) { return paneles[p.k]; }).join("");
    var activa = pestanaGuardada(vistaId, visibles.map(function (p) { return p.k; }));
    var barra = "<div class='pestanas' role='tablist' data-vista-pestanas='" + esc(vistaId) + "'>"
      + visibles.map(function (p) {
        var on = p.k === activa;
        return "<button type='button' class='pestana" + (on ? " activa" : "") + "' role='tab' aria-selected='" + on
          + "' data-pestana='" + esc(p.k) + "'>" + (p.icono ? icon(p.icono, 15) : "") + esc(p.t) + "</button>";
      }).join("") + "</div>";
    var cuerpo = visibles.map(function (p) {
      return "<section class='pestana-panel' role='tabpanel' data-panel='" + esc(p.k) + "'"
        + (p.k === activa ? "" : " hidden") + ">" + paneles[p.k] + "</section>";
    }).join("");
    return cabecera + barra + cuerpo;
  }

  // Abre la pestaña que contiene a `el` (los atajos de los KPI saltan a
  // secciones que pueden estar en una pestaña oculta).
  function mostrarPestanaDe(el) {
    var panel = el && el.closest ? el.closest(".pestana-panel[hidden]") : null;
    if (!panel) return;
    var barra = panel.parentNode.querySelector(".pestanas");
    var b = barra && barra.querySelector(".pestana[data-pestana='" + panel.getAttribute("data-panel") + "']");
    if (b) b.click();
  }

  document.addEventListener("click", function (e) {
    var b = e.target && e.target.closest ? e.target.closest(".pestanas .pestana") : null;
    if (!b) return;
    var barra = b.parentNode;
    var clave = b.getAttribute("data-pestana");
    Array.prototype.forEach.call(barra.children, function (x) {
      var on = x === b;
      x.classList.toggle("activa", on);
      x.setAttribute("aria-selected", on ? "true" : "false");
    });
    Array.prototype.forEach.call(barra.parentNode.children, function (sec) {
      if (sec.classList && sec.classList.contains("pestana-panel")) sec.hidden = sec.getAttribute("data-panel") !== clave;
    });
    try { localStorage.setItem("ja_pestana_" + barra.getAttribute("data-vista-pestanas"), clave); } catch (e2) { /* sin almacenamiento */ }
    // Los gráficos que se dibujaron ocultos recalculan su ancho.
    try { window.dispatchEvent(new Event("resize")); } catch (e3) { /* navegador viejo */ }
    if (barra.getBoundingClientRect().top < 0) barra.scrollIntoView({ block: "start" });
  });

