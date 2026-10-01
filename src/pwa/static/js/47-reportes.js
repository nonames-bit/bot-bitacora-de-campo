  /* ---------- Reportes (Fase E): todos los PDF y Excel en una pantalla ----------
     Cada pantalla tiene un solo botón "Descargar" (botonDescargar) que trae
     aquí con su reporte resaltado. Los archivos los arman /api/reporte.pdf,
     /api/reporte.xlsx y /api/ficha/<tag>/pdf (solo OWNER y ADMIN). */
  var REPORTES = [
    { k: "general", t: "Informe general de campo", d: "Resumen del hato, eventos y alertas de la semana o el período elegido.", icono: "grid", pdf: "" },
    { k: "inventario", t: "Inventario", d: "Hato activo por categoría, potrero y peso.", icono: "cow", pdf: "inventario", xlsx: "inventario" },
    { k: "censo_ica", t: "Censo ICA", d: "Formato para movilización y vacunación.", icono: "shieldCheck", pdf: "censo_ica" },
    { k: "reproduccion", t: "Reproducción", d: "Servicios, tactos, partos y banco de semen.", icono: "sperm", pdf: "reproduccion", xlsx: "reproduccion" },
    { k: "sanidad", t: "Sanidad", d: "Tratamientos, vacunas y retiros de leche o carne.", icono: "shieldPlus", pdf: "sanidad", xlsx: "sanidad" },
    { k: "leche", t: "Leche", d: "Producción diaria y entregas.", icono: "milk", pdf: "leche", xlsx: "leche" },
    { k: "pasturas", t: "Potreros y pasturas", d: "Ocupación, reposo y aforos.", icono: "sprout", pdf: "pasturas", xlsx: "pasturas" },
    { k: "finanzas", t: "Finanzas", d: "Ingresos, gastos y flujo de caja.", icono: "banknote", pdf: "finanzas", xlsx: "finanzas" }
  ];
  var PERIODOS_REPORTE = [
    { dias: 7, t: "7 días", pdf: "semanal" },
    { dias: 15, t: "15 días", pdf: "quincenal" },
    { dias: 30, t: "30 días", pdf: "mensual" },
    { dias: 90, t: "90 días", pdf: "90" }
  ];

  function puedeDescargar() {
    var u = window.__usuarioActual;
    return !!(u && (u.rol === "OWNER" || u.rol === "ADMIN"));
  }

  // El único botón de descarga de cada pantalla.
  function botonDescargar(clave) {
    if (!puedeDescargar()) return "";
    return "<button type='button' class='tema-btn btn-ir-reportes' data-reporte='" + esc(clave || "") + "'"
      + " style='font-size:12px; padding:5px 12px; display:inline-flex; align-items:center; gap:5px;'>"
      + icon("download", 14) + "Descargar</button>";
  }

  function periodoReporte() {
    var dias = 7;
    try { dias = parseInt(localStorage.getItem("ja_reporte_dias"), 10) || 7; } catch (e) { /* sin almacenamiento */ }
    return PERIODOS_REPORTE.filter(function (p) { return p.dias === dias; })[0] || PERIODOS_REPORTE[0];
  }

  function enlacesReporte(r, per) {
    var h = "";
    if (r.pdf !== undefined) {
      var qs = [];
      if (r.pdf) qs.push("seccion=" + encodeURIComponent(r.pdf));
      if (r.k !== "inventario" && r.k !== "censo_ica") qs.push("periodo=" + encodeURIComponent(per.pdf));
      h += "<a class='rep-btn' target='_blank' rel='noopener' href='/api/reporte.pdf" + (qs.length ? "?" + qs.join("&") : "") + "'>"
        + icon("filePdf", 15) + "PDF</a>";
    }
    if (r.xlsx) {
      h += "<a class='rep-btn rep-btn-sec' target='_blank' rel='noopener' href='/api/reporte.xlsx?seccion="
        + encodeURIComponent(r.xlsx) + "&dias=" + per.dias + "'>" + icon("table", 15) + "Excel</a>";
    }
    return h;
  }

  function renderReportes() {
    var per = periodoReporte();
    var h = "<h3>" + icon("download", 20) + "Reportes</h3>";
    if (!puedeDescargar()) {
      return h + "<p class='aviso'>Los reportes los descarga el propietario o un administrador.</p>";
    }
    h += "<p class='aviso'>Escoge el período y descarga el reporte en PDF para imprimir o en Excel para trabajar los datos.</p>";
    h += "<div class='rep-periodo' role='group' aria-label='Período'>"
      + PERIODOS_REPORTE.map(function (p) {
        return "<button type='button' class='tema-btn rep-per" + (p.dias === per.dias ? " act" : "") + "' data-dias='" + p.dias + "'>" + esc(p.t) + "</button>";
      }).join("") + "</div>";
    h += "<div class='rep-lista'>";
    REPORTES.forEach(function (r) {
      h += "<div class='card rep-item' data-reporte='" + esc(r.k) + "'>"
        + "<div class='rep-info'><span class='rep-ico'>" + icon(r.icono, 20) + "</span>"
        + "<div><b>" + esc(r.t) + "</b><small>" + esc(r.d) + "</small></div></div>"
        + "<div class='rep-acciones'>" + enlacesReporte(r, per) + "</div></div>";
    });
    // Ficha de un animal: no depende del período.
    h += "<div class='card rep-item' data-reporte='ficha'>"
      + "<div class='rep-info'><span class='rep-ico'>" + icon("tag", 20) + "</span>"
      + "<div><b>Ficha de un animal</b><small>Datos, genealogía, pesos y sanidad de un arete.</small></div></div>"
      + "<form class='rep-acciones rep-ficha' autocomplete='off'>"
      + "<input id='rep-ficha-tag' placeholder='Arete, ej. 47' list='dl-tags' aria-label='Arete'>"
      + "<button type='submit' class='rep-btn'>" + icon("filePdf", 15) + "PDF</button></form></div>";
    h += "</div>";
    return h;
  }

  function bindReportes() {
    qa(".rep-per").forEach(function (b) {
      b.addEventListener("click", function () {
        try { localStorage.setItem("ja_reporte_dias", b.getAttribute("data-dias")); } catch (e) { /* sin almacenamiento */ }
        var per = periodoReporte();
        qa(".rep-per").forEach(function (x) { x.classList.toggle("act", x === b); });
        qa(".rep-item").forEach(function (it) {
          var r = REPORTES.filter(function (x) { return x.k === it.getAttribute("data-reporte"); })[0];
          if (r) it.querySelector(".rep-acciones").innerHTML = enlacesReporte(r, per);
        });
      });
    });
    var f = q(".rep-ficha");
    if (f) f.addEventListener("submit", function (e) {
      e.preventDefault();
      var tag = (q("#rep-ficha-tag").value || "").trim();
      if (!tag) { mostrarToast("Escribe el arete del animal.", "ambar"); return; }
      window.open("/api/ficha/" + encodeURIComponent(tag) + "/pdf", "_blank", "noopener");
    });
    var foco = window.__reporteFoco;
    window.__reporteFoco = null;
    var it = foco ? q(".rep-item[data-reporte='" + foco + "']") : null;
    if (it) {
      setTimeout(function () {
        it.scrollIntoView({ behavior: "smooth", block: "center" });
        it.classList.add("kpi-destacado");
        setTimeout(function () { it.classList.remove("kpi-destacado"); }, 1800);
      }, 80);
    }
  }

  document.addEventListener("click", function (e) {
    var b = e.target && e.target.closest ? e.target.closest(".btn-ir-reportes") : null;
    if (!b) return;
    window.__reporteFoco = b.getAttribute("data-reporte") || null;
    irAVista("reportes");
    cargar(true);
    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e2) { window.scrollTo(0, 0); }
  });
