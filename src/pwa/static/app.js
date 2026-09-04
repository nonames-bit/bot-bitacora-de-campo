/* Dashboard PWA Bitácora JA — JS vainilla (<500KB total, sin framework). */
(function () {
  "use strict";
  var vista = document.getElementById("vista");
  var actual = "tablero";
  function q(s) { return document.querySelector(s); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function tabla(filas, cols) {
    if (!filas || !filas.length) return "<p><i>Sin datos.</i></p>";
    var h = "<table><tr>" + cols.map(function (c) { return "<th>" + esc(c[1]) + "</th>"; }).join("") + "</tr>";
    h += filas.map(function (f) { return "<tr>" + cols.map(function (c) { return "<td>" + esc(f[c[0]]) + "</td>"; }).join("") + "</tr>"; }).join("");
    return h + "</table>";
  }
  function render(d) {
    if (!vista) return;
    if (actual === "tablero") {
      vista.innerHTML = "<h3>🐮 Tablero finca</h3><p>Activos: <b>" + d.activos + "</b> (♀ " + d.hembras + " · ♂ " + d.machos + ")</p>"
        + "<p>Partos 7d: <b>" + d.partos_7d + "</b> · Celos 7d: <b>" + d.celos_7d + "</b> · Servicios 7d: <b>" + d.servicios_7d + "</b> · Retiros: <b>" + d.retiros_activos + "</b></p>"
        + tabla(d.por_potrero, [["potrero", "Potrero"], ["n", "Cabezas"]]);
    } else if (actual === "repro") {
      vista.innerHTML = "<h3>🤰 Reproducción</h3><h4>FEP ≤30d</h4>" + tabla(d.fep_30d, [["tag", "Vaca"], ["fecha", "Servicio"], ["fep_calculada", "FEP"]])
        + "<h4>Celos recientes</h4>" + tabla(d.celos_recientes, [["tag", "Vaca"], ["fecha", "Fecha"], ["am_pm", "AM/PM"]])
        + "<h4>Eco/Palp pendientes</h4>" + tabla(d.eco_palp_pendientes, [["tipo_alerta", "Tipo"], ["fecha_programada", "Fecha"]]);
    } else if (actual === "sanidad") {
      vista.innerHTML = "<h3>💉 Sanidad</h3><h4>Retiros activos</h4>" + tabla(d.retiros, [["tag", "Animal"], ["producto", "Producto"], ["fecha_fin_retiro_leche", "Fin leche"], ["fecha_fin_retiro_carne", "Fin carne"]])
        + "<h4>Últimos tratamientos</h4>" + tabla(d.ultimos_tratamientos, [["tag", "Animal"], ["producto", "Producto"], ["fecha", "Fecha"]]);
    } else if (actual === "pasturas") {
      vista.innerHTML = "<h3>🌿 Pasturas (Voisin)</h3>" + tabla(d.potreros, [["nombre", "Potrero"], ["dias_ocupacion", "Ocup."], ["dias_reposo", "Reposo"], ["semaforo", "●"]])
        + "<h4>NDVI reciente</h4>" + tabla(d.ndvi_reciente, [["potrero", "Potrero"], ["fecha", "Fecha"], ["ndvi_promedio", "NDVI"]]);
    } else if (actual === "leche") {
      vista.innerHTML = "<h3>🥛 Leche (tanque)</h3>" + tabla(d.serie_tanque, [["fecha", "Fecha"], ["litros", "Litros"]])
        + "<h4>Controles</h4>" + tabla(d.controles, [["tag", "Vaca"], ["fecha", "Fecha"], ["litros", "L"]]);
    } else if (actual === "ficha") {
      var t = (q("#f-tag") && q("#f-tag").value || "").trim();
      vista.innerHTML = t ? "<p>Cargando ficha " + esc(t) + "…</p>" : "<p>Escribe un tag y pulsa Cargar.</p>";
      if (t) fetch("/api/ficha/" + encodeURIComponent(t)).then(function (r) { return r.json(); }).then(function (f) {
        if (!f.existe) { vista.innerHTML = "<p>❌ Sin registro para " + esc(t) + ".</p>"; return; }
        vista.innerHTML = "<h3>🐮 " + esc(f.tag) + "</h3><p>" + esc(f.sexo || "") + " · " + esc(f.raza || "") + " · QR <code>" + esc(f.qr_payload) + "</code> · <a href='/ficha/" + esc(f.tag) + "'>/ficha/" + esc(f.tag) + "</a></p>"
          + "<h4>Pesajes</h4>" + tabla(f.pesajes, [["fecha", "Fecha"], ["peso_kg", "kg"]])
          + "<h4>Tratamientos</h4>" + tabla(f.tratamientos, [["fecha", "Fecha"], ["producto", "Producto"]]);
      });
      return;
    }
  }
  function cargar() {
    var pot = (q("#f-potrero") && q("#f-potrero").value || "").trim();
    var url = actual === "ficha" ? null : "/api/" + actual + (pot && actual === "tablero" ? "?potrero=" + encodeURIComponent(pot) : "");
    if (!url) { render({}); return; }
    if (vista) vista.textContent = "Cargando…";
    fetch(url).then(function (r) { return r.json(); }).then(render).catch(function (e) { if (vista) vista.textContent = "❌ " + e; });
  }
  document.querySelectorAll("nav button").forEach(function (b) {
    b.addEventListener("click", function () {
      document.querySelectorAll("nav button").forEach(function (x) { x.classList.remove("act"); });
      b.classList.add("act"); actual = b.getAttribute("data-v"); cargar();
    });
  });
  var btn = document.getElementById("btn-cargar");
  if (btn) btn.addEventListener("click", cargar);
  // Ficha dedicada /ficha/<tag>.
  var fb = document.getElementById("ficha");
  if (fb) {
    var tag = document.body.getAttribute("data-tag") || "";
    fetch("/api/ficha/" + encodeURIComponent(tag)).then(function (r) { return r.json(); }).then(function (f) {
      if (!f.existe) { fb.innerHTML = "<p>❌ Sin registro para " + esc(tag) + ".</p>"; return; }
      fb.innerHTML = "<h3>🐮 " + esc(f.tag) + " " + esc(f.nombre || "") + "</h3>"
        + "<p>" + esc(f.sexo || "") + " · " + esc(f.raza || "") + " · Nac: " + esc(f.fecha_nacimiento || "S/D") + "</p>"
        + "<p>QR <code>" + esc(f.qr_payload) + "</code></p>";
    });
  } else { cargar(); }
})();
