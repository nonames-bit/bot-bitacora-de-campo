  /* ---------- Carga de datos ---------- */
  // Skeleton mimético por tipo de vista (más pulido que un bloque genérico).
  var ESQUELETOS = {
    tablero:   { kpis: 7, graf: 2, tabla: 7 },
    agenda:    { kpis: 0, graf: 0, tabla: 6 },
    inventario:{ kpis: 5, graf: 0, tabla: 11 },
    poblacion: { kpis: 4, graf: 0, tabla: 6 },
    genetica:  { kpis: 1, graf: 0, tabla: 10 },
    repro:     { kpis: 0, graf: 1, tabla: 12 },
    sanidad:   { kpis: 0, graf: 0, tabla: 9 },
    pasturas:  { kpis: 0, graf: 3, tabla: 8 },
    leche:     { kpis: 3, graf: 2, tabla: 8 },
    finanzas:  { kpis: 3, graf: 0, tabla: 8 },
    ficha:     { kpis: 0, graf: 1, tabla: 7 },
    manga:     { kpis: 0, graf: 0, tabla: 4 },
    captura:   { kpis: 0, graf: 0, tabla: 0 },
    gps:       { kpis: 0, graf: 0, tabla: 4 },
    sistema:   { kpis: 4, graf: 0, tabla: 0 },
    mercado:   { kpis: 3, graf: 0, tabla: 8 },
    usuarios:  { kpis: 0, graf: 0, tabla: 5 },
    revision:  { kpis: 0, graf: 0, tabla: 4 },
    reportes:  { kpis: 0, graf: 0, tabla: 8 }
  };
  function htmlSkeleton(v) {
    var cfg = ESQUELETOS[v] || ESQUELETOS.tablero;
    var h = "";
    if (cfg.kpis) {
      h += "<div class='sk-kpis'>";
      for (var i = 0; i < cfg.kpis; i++) h += "<div class='skeleton'></div>";
      h += "</div>";
    }
    if (cfg.graf) {
      h += "<div class='sk-graficos'>";
      for (var j = 0; j < cfg.graf; j++) h += "<div class='skeleton'></div>";
      h += "</div>";
    }
    if (cfg.tabla) {
      h += "<div class='sk-tabla'>";
      for (var k = 0; k < cfg.tabla; k++) h += "<div class='skeleton'></div>";
      h += "</div>";
    }
    return h || "<div class='skeleton h2'></div><div class='skeleton'></div>";
  }
  function skeleton(target, view) {
    target = target || vista;
    if (target) target.innerHTML = htmlSkeleton(view || actual);
  }
  // Cuenta los números de los KPIs desde 0 hasta su valor (solo valores puros).
  function animarKpis(root) {
    if (!root) return;
    qa(".kpi .num", root).forEach(function (el) {
      var txt = (el.textContent || "").trim();
      if (!/^-?[\d.]+$/.test(txt)) return; // "—", tags, "3.61a", etc.
      var destino = parseFloat(txt.replace(/\./g, ""));
      if (!isFinite(destino)) return;
      var dur = 550, t0 = null;
      function paso(ts) {
        if (!t0) t0 = ts;
        var p = Math.min((ts - t0) / dur, 1);
        p = 1 - Math.pow(1 - p, 3); // ease-out cubic
        el.textContent = String(Math.round(destino * p));
        if (p < 1) requestAnimationFrame(paso);
        else el.textContent = txt;
      }
      requestAnimationFrame(paso);
    });
  }
  // "Escribe" los trazos de cada icono SVG (efecto dibujado, tipo Lucide).
  // Mide cada path/line/circle con getTotalLength y lo anima con
  // stroke-dashoffset. Se salta con prefers-reduced-motion.
  function animarIconos(root) {
    if (!root) return;
    var redu = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (redu) return;
    qa("svg.svg-icon", root).forEach(function (svg, iSvg) {
      var hijos = qa("path,line,circle,rect,polyline,polygon", svg);
      if (!hijos.length) return;
      var largos = hijos.map(function (nd) {
        try { return nd.getTotalLength ? nd.getTotalLength() : 0; }
        catch (e) { return 0; }
      });
      var tieneTrazo = largos.some(function (l) { return l > 0; });
      if (!tieneTrazo) return;
      hijos.forEach(function (nd, i) {
        if (largos[i] <= 0) return;
        nd.style.strokeDasharray = String(largos[i]);
        nd.style.strokeDashoffset = String(largos[i]);
      });
      void svg.getBoundingClientRect(); // forzar reflow para arrancar la transición
      var delay = 80 + iSvg * 40; // pequeño escalonado entre iconos
      setTimeout(function () {
        hijos.forEach(function (nd, i) {
          if (largos[i] > 0) nd.style.strokeDashoffset = "0";
        });
      }, delay);
    });
  }
  // Monta el HTML de una vista con la animación de entrada (si `animar`) y
  // refresca los KPIs. En el polling en silencio se evita la animación para
  // no "parpadear" la pantalla cada minuto.
  function montarVista(el, html, animar) {
    if (!el) return;
    el.innerHTML = html;
    vincularTagsFicha(el); // tags clicables -> ficha del animal
    if (window.JA && window.JA.inicializarGraficos) {
      window.JA.inicializarGraficos(el);
    }
    if (animar) {
      el.classList.remove("vista-entra");
      void el.offsetWidth; // reinicia la animación
      el.classList.add("vista-entra");
      setTimeout(function () { el.classList.remove("vista-entra"); }, 300);
      animarKpis(el);
      animarIconos(el);
    }
  }
  // Convierte la primera columna de tablas (cuando es un arete) en un enlace
  // que abre la ficha del animal sin volver a teclear.
  // Cubre los formatos de arete reales de la finca, incluyendo los sufijos
  // "-N" (generación/lote, ej. JA26-6, V064-6) y "_N" de las crías nuevas
  // (ej. NM_67965) -- sin esto, ~6% del hato activo no era clicable.
  var _TAG_RE = /^([A-Za-z]{0,4}\d{1,6}(-\d{1,3})?|[A-Za-z]{1,4}-\d{1,6}(-\d{1,3})?|\d{1,4}-\d{1,3}(-\d{1,3})?|[A-Za-z]{1,4}_\d{1,8})$/;
  var _CAB_NO_CLICK = /potrero|fecha|categor[ií]a|raza|c[óo]digo|banda|toro|bracket|peso/i;
  function abrirFichaDesdeTag(tag, tabId) {
    if (!tag) return;
    tag = String(tag).trim();
    if (!tag) return;

    var destino = qa("#nav-principal button").filter(function (b) { return b.getAttribute("data-v") === "ficha"; })[0];
    if (!destino) {
      // Si estamos en la página standalone /ficha/<tag> (usa #ficha, no #vista)
      var destinoStandalone = vista || document.getElementById("ficha");
      if (typeof abrirFicha === "function" && destinoStandalone) {
        abrirFicha(tag, destinoStandalone, false, true, tabId);
        try { window.history.pushState(null, "", "/ficha/" + encodeURIComponent(tag)); } catch (e) {}
        try {
          document.title = "Ficha " + tag + " · Bitácora JA";
          var tituloTag = document.querySelector(".marca-titulo b");
          if (tituloTag) tituloTag.textContent = tag;
        } catch (e) {}
      } else {
        window.location = "/ficha/" + encodeURIComponent(tag);
      }
      return;
    }

    var inp = q("#f-tag");
    if (inp) inp.value = tag;

    irAVista("ficha");

    var barraFiltros = document.getElementById("barra-filtros");
    if (barraFiltros) barraFiltros.style.display = "none";

    if (typeof abrirFicha === "function" && vista) {
      abrirFicha(tag, vista, true, true, tabId);
    } else {
      cargar(true);
    }
    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) { window.scrollTo(0, 0); }
  }
  window.abrirFichaDesdeTag = abrirFichaDesdeTag;
  window.abrirTabFicha = function (tabId) {
    var nav = document.getElementById("ficha-tabs");
    if (!nav) return;
    var btn = nav.querySelector("button[data-tab='" + tabId + "']");
    if (btn) btn.click();
  };
  // Helper para renderizar botón de eliminación de eventos (exclusivo OWNER)
  function renderBtnEliminar(tipo, id, desc) {
    var puede = window.__usuarioActual && window.__usuarioActual.rol === "OWNER";
    if (!puede || !id) return "";
    return "<button type='button' class='btn-eliminar-evento' data-accion='eliminar-evento' data-tipo='" + esc(tipo) + "' data-id='" + esc(id) + "' data-desc='" + esc(desc || "") + "' title='Deshacer / Eliminar registro' aria-label='Eliminar'>" + icon("trash", 13) + "</button>";
  }
  window.renderBtnEliminar = renderBtnEliminar;

  function ejecutarEliminacionEvento(tipo, id, desc) {
    var puede = window.__usuarioActual && window.__usuarioActual.rol === "OWNER";
    if (!puede) {
      alert("Acceso restringido: solo el propietario (OWNER) puede eliminar eventos registrados.");
      return;
    }
    if (!tipo || !id) {
      alert("Error: tipo o ID de evento no especificado.");
      return;
    }
    var msg = "¿Seguro que deseas DESHACER / ELIMINAR permanentemente este registro del sistema?\n\n"
      + "• " + (desc || (tipo.toUpperCase() + " #" + id)) + "\n\n"
      + "Esta acción revertirá de forma inteligente estados o potreros derivados si aplica (ej. el animal vuelve a ACTIVO tras una muerte o salida).\n\n¿Continuar?";
    if (!window.confirm(msg)) return;

    mostrarToast("Deshaciendo evento...", "ambar");
    fetch("/api/eventos/eliminar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: tipo, id: parseInt(id, 10) })
    })
    .then(function (r) {
      return r.json().then(function (data) { return { ok: r.ok, status: r.status, data: data }; });
    })
    .then(function (res) {
      if (!res.ok || !res.data.ok) {
        alert("Error al eliminar evento: " + ((res.data && res.data.error) || ("HTTP " + res.status)));
        return;
      }
      mostrarToast((res.data.mensaje || "Registro eliminado correctamente"), "verde");
      vibrarConfirmacion();
      var modalUlt = document.getElementById("modal-ultimos-eventos");
      if (modalUlt && modalUlt.style.display !== "none") {
        mostrarModalUltimosEventos();
      }
      if (window.__ultimaFicha && window.__ultimaFicha.tag) {
        abrirFichaDesdeTag(window.__ultimaFicha.tag);
      }
      cargar(true);
      actualizarBadges();
    })
    .catch(function (err) {
      alert("Error de conexión al eliminar evento: " + err.message);
    });
  }
  window.ejecutarEliminacionEvento = ejecutarEliminacionEvento;

  function mostrarModalUltimosEventos() {
    var modal = document.getElementById("modal-ultimos-eventos");
    var lista = document.getElementById("ultimos-eventos-lista");
    var btnCerrar = document.getElementById("btn-cerrar-modal-ultimos-eventos");
    if (!modal || !lista) return;

    modal.style.display = "flex";
    lista.innerHTML = "<div style='text-align:center; padding:24px; color:var(--texto-suave);'>Cargando eventos recientes de la finca...</div>";

    if (btnCerrar && !btnCerrar._bound) {
      btnCerrar._bound = true;
      btnCerrar.addEventListener("click", function () { modal.style.display = "none"; });
      modal.addEventListener("click", function (e) { if (e.target === modal) modal.style.display = "none"; });
    }

    fetch("/api/eventos/recientes?limite=35")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok || !d.eventos || !d.eventos.length) {
          lista.innerHTML = "<div style='text-align:center; padding:24px; color:var(--texto-suave);'>No hay eventos de campo recientes.</div>";
          return;
        }

        var html = "";
        d.eventos.forEach(function (ev) {
          var tagTxt = ev.tag ? ("#" + esc(ev.tag)) : "Sin arete";
          var fechaTxt = esc(fechaCorta(ev.fecha));
          var creadoTxt = ev.creado_en ? esc(ev.creado_en.replace("T", " ").slice(0, 16)) : "";
          var resumenTxt = esc(ev.resumen || ev.tabla);
          var quienTxt = ev.registrado_por ? ("por " + esc(ev.registrado_por)) : "";

          html += "<div class='card' style='padding:12px 14px; margin:0; display:flex; justify-content:space-between; align-items:center; gap:12px; background:var(--superficie); border:1px solid var(--borde-suave); border-radius:10px; box-shadow:0 1px 3px var(--sombra);'>"
            + "<div style='flex:1; min-width:0;'>"
            + "<div style='display:flex; align-items:center; gap:8px; margin-bottom:3px; flex-wrap:wrap;'>"
            + "<span class='chip' style='font-size:11px; font-weight:700; text-transform:uppercase; background:rgba(47,82,51,0.08); color:var(--verde-marca);'>" + esc(ev.tabla) + "</span>"
            + (ev.tag ? "<a href='#' class='tag-link' onclick='event.preventDefault(); document.getElementById(\"modal-ultimos-eventos\").style.display=\"none\"; abrirFichaDesdeTag(\"" + esc(ev.tag) + "\");' style='font-weight:700; color:var(--verde-marca); text-decoration:none; font-size:13px;'>" + tagTxt + "</a>" : "")
            + "<span style='font-size:11.5px; color:var(--texto-suave);'>" + icon("calendar", 12) + fechaTxt + "</span>"
            + "</div>"
            + "<div style='font-size:13px; font-weight:600; color:var(--texto); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;'>" + resumenTxt + "</div>"
            + "<div style='font-size:11px; color:var(--texto-suave); margin-top:3px;'>" + icon("clock", 12) + creadoTxt + " " + quienTxt + "</div>"
            + "</div>";

          if (d.puede_deshacer) {
            html += "<button type='button' class='btn-deshacer-accion' data-tipo='" + esc(ev.tabla) + "' data-id='" + ev.id + "' data-desc='" + resumenTxt + " (" + tagTxt + ", " + fechaTxt + ")' style='background:rgba(220,38,38,0.08); color:#DC2626; border:1px solid rgba(220,38,38,0.3); padding:8px 12px; font-size:12px; font-weight:700; cursor:pointer; display:inline-flex; align-items:center; gap:4px; flex-shrink:0;'>"
              + icon("trash", 14) + "Deshacer</button>";
          }
          html += "</div>";
        });
        lista.innerHTML = html;

        // Asignar manejador de evento Deshacer en cada tarjeta
        lista.querySelectorAll(".btn-deshacer-accion").forEach(function (b) {
          b.addEventListener("click", function () {
            var t = this.getAttribute("data-tipo");
            var id = this.getAttribute("data-id");
            var desc = this.getAttribute("data-desc");
            ejecutarEliminacionEvento(t, id, desc);
          });
        });
      })
      .catch(function (err) {
        lista.innerHTML = "<div style='color:var(--rojo-alerta); padding:16px;'>Error al cargar eventos: " + esc(err.message) + "</div>";
      });
  }
  window.mostrarModalUltimosEventos = mostrarModalUltimosEventos;

  function ejecutarPausaOrdeno(tag) {
    if (!tag) return;
    var motivo = window.prompt("Motivo de la pausa (ej. Ternero flaco, se suelta con la vaca):", "Ternero suelto con la vaca") || "";
    mostrarToast("Guardando pausa de ordeño...", "ambar");
    fetch("/api/animal/" + encodeURIComponent(tag) + "/pausa-ordeno", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo: motivo })
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          alert("Error al pausar el ordeño: " + ((res.data && res.data.error) || "Error desconocido"));
          return;
        }
        mostrarToast("Ordeño pausado. No se contará en el promedio litros/vaca.", "verde");
        vibrarConfirmacion();
        abrirFichaDesdeTag(tag, "leche");
      })
      .catch(function (err) { alert("Error de conexión: " + err.message); });
  }
  window.ejecutarPausaOrdeno = ejecutarPausaOrdeno;

  function ejecutarReanudarOrdeno(tag) {
    if (!tag) return;
    mostrarToast("Reanudando ordeño...", "ambar");
    fetch("/api/animal/" + encodeURIComponent(tag) + "/reanudar-ordeno", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok || !res.data.ok) {
          alert("Error al reanudar el ordeño: " + ((res.data && res.data.error) || "Error desconocido"));
          return;
        }
        mostrarToast("Ordeño reanudado.", "verde");
        vibrarConfirmacion();
        abrirFichaDesdeTag(tag, "leche");
      })
      .catch(function (err) { alert("Error de conexión: " + err.message); });
  }
  window.ejecutarReanudarOrdeno = ejecutarReanudarOrdeno;

  // Delegado global de clics para HTML inyectado dinámicamente (innerHTML):
  // el CSP de producción (script-src 'self', sin unsafe-inline) bloquea
  // atributos onclick='' inline -- por eso todo lo que se genera con
  // cadenas HTML usa data-ir-ficha / data-ir-tab / data-accion en vez de
  // onclick, y un único listener delegado en document los resuelve aquí.
  document.addEventListener("click", function (e) {
    var elPot = e.target.closest(".btn-listar-animales-pot, .link-potrero-animales, [data-listar-potrero]");
    if (elPot) {
      e.preventDefault();
      var potNom = elPot.getAttribute("data-potrero") || elPot.getAttribute("data-listar-potrero");
      if (potNom) abrirModalAnimalesPotrero(potNom);
      return;
    }
    var elGrupo = e.target.closest(".link-grupo-inventario, .fila-grupo-inventario, [data-grupo-tipo]");
    if (elGrupo) {
      e.preventDefault();
      var gTipo = elGrupo.getAttribute("data-grupo-tipo");
      var gVal = elGrupo.getAttribute("data-grupo-valor");
      var gSexo = elGrupo.getAttribute("data-sexo") || "";
      var gTit = elGrupo.getAttribute("data-grupo-titulo") || "";
      if (gTipo && gVal) {
        abrirModalGrupoInventario(gTipo, gVal, gSexo, gTit);
        return;
      }
    }
    var elFicha = e.target.closest("[data-ir-ficha]");
    if (elFicha) {
      e.preventDefault();
      var modalPot = document.getElementById("modal-animales-potrero") || document.getElementById("modal-animales-lista");
      if (modalPot) modalPot.remove();
      abrirFichaDesdeTag(elFicha.getAttribute("data-ir-ficha"));
      return;
    }
    var elTab = e.target.closest("[data-ir-tab]");
    if (elTab) {
      e.preventDefault();
      window.abrirTabFicha(elTab.getAttribute("data-ir-tab"));
      return;
    }
    var elBtnComp = e.target.closest("#btn-editar-composicion-raza");
    if (elBtnComp) {
      e.preventDefault();
      var tagComp = elBtnComp.getAttribute("data-tag") || (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
      mostrarModalComposicionRacial(tagComp);
      return;
    }
    var elAcc = e.target.closest("[data-accion]");
    if (elAcc) {
      var acc = elAcc.getAttribute("data-accion");
      if (acc === "exportar-inventario") { if (window.__exportarInventario) window.__exportarInventario(); }
      else if (acc === "exportar-retiros") { if (window.__exportarRetiros) window.__exportarRetiros(); }
      else if (acc === "buscar-otro-animal") {
        e.preventDefault();
        if (typeof window.abrirModalBuscarFichaRapida === "function") {
          window.abrirModalBuscarFichaRapida();
        }
      }
      else if (acc === "reload") { location.reload(); }
      else if (acc === "ir-mapa-satelital") { e.preventDefault(); irAVista("mapa"); cargar(); }
      else if (acc === "crear-animal") { mostrarFormularioAnimal(null, elAcc.getAttribute("data-tag-nuevo") || ""); }
      else if (acc === "editar-animal") { mostrarFormularioAnimal(window.__ultimaFicha || null); }
      else if (acc === "capturar-evento" || acc === "vender-animal") {
        e.preventDefault();
        var tipoCap = elAcc.getAttribute("data-tipo") || (acc === "vender-animal" ? "venta" : "pesaje");
        var tagC = elAcc.getAttribute("data-tag") || (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
        var potC = elAcc.getAttribute("data-potrero") || "";
        var farmC = elAcc.getAttribute("data-farmaco") || "";
        var toroC = elAcc.getAttribute("data-toro") || "";

        if (tagC) {
          try { localStorage.setItem("bitacora_ultimo_tag", tagC); } catch (eVTag) {}
          window.__capTagPendiente = tagC;
        }
        if (potC) {
          try { localStorage.setItem("bitacora_ultimo_potrero", potC); } catch (eVPot) {}
          window.__capPotreroPendiente = potC;
        }
        if (farmC) {
          window.__capFarmacoPendiente = farmC;
        }
        if (toroC) {
          window.__capToroPendiente = toroC;
        }

        window.__capPasoInicial = 2;
        _tipoCapturaActual = tipoCap;

        var mAbierto = document.getElementById("modal-animales-lista") || document.getElementById("modal-animales-potrero");
        if (mAbierto) mAbierto.remove();

        irAVista("captura");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eScroll) { window.scrollTo(0, 0); }
      }
      else if (acc === "rectificar-tag") {
        var tTag = elAcc.getAttribute("data-tag") || (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
        mostrarModalRectificarTag(tTag);
      }
      else if (acc === "cambiar-foto-animal") {
        e.preventDefault();
        var fTag = elAcc.getAttribute("data-tag") || (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
        if (fTag && typeof window.iniciarCapturaFotoAnimal === "function") {
          window.iniciarCapturaFotoAnimal(fTag);
        }
      }
      else if (acc === "editar-composicion-raza") {
        var cTag = elAcc.getAttribute("data-tag") || (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
        mostrarModalComposicionRacial(cTag);
      }
      else if (acc === "copiar-arbol") {
        var card = elAcc.closest(".card");
        var pre = card && card.querySelector("pre");
        if (pre) navigator.clipboard.writeText(pre.innerText).then(function () { alert("Árbol copiado al portapapeles"); });
      }
      else if (acc === "eliminar-evento") {
        e.preventDefault();
        var tipoEv = elAcc.getAttribute("data-tipo");
        var idEv = elAcc.getAttribute("data-id");
        var descEv = elAcc.getAttribute("data-desc") || (tipoEv + " #" + idEv);
        ejecutarEliminacionEvento(tipoEv, idEv, descEv);
      }
      else if (acc === "pausar-ordeno") {
        e.preventDefault();
        ejecutarPausaOrdeno(elAcc.getAttribute("data-tag"));
      }
      else if (acc === "reanudar-ordeno") {
        e.preventDefault();
        ejecutarReanudarOrdeno(elAcc.getAttribute("data-tag"));
      }
      else if (acc === "registrar-secado") {
        e.preventDefault();
        var tagSec = elAcc.getAttribute("data-tag");
        if (!tagSec || !confirm("¿Registrar a " + tagSec + " como seca desde hoy?")) return;
        elAcc.disabled = true;
        enviarEventoLt("secado", { animal_tag: tagSec, motivo: "Confirmada seca desde la ficha" }).then(function () {
          mostrarToast(tagSec + " registrada como seca.", "verde");
          abrirFichaDesdeTag(tagSec, "leche");
        });
      }
    }
  });
  // "error" no burbujea, así que este delegado necesita fase de captura.
  document.addEventListener("error", function (e) {
    var el = e.target;
    if (!el || el.tagName !== "IMG" || !el.hasAttribute("data-onerror-hide")) return;
    var objetivo = el.getAttribute("data-onerror-hide") === "parent" ? el.parentElement : el;
    if (objetivo) objetivo.style.display = "none";
  }, true);
  function vincularTagsFicha(root) {
    if (!root) return;
    if (!qa("#nav-principal button").length) return; // solo en el dashboard con navegación
    var trs = qa("table tr", root);
    trs.forEach(function (tr) {
      var celdas = qa("td", tr);
      if (!celdas.length) return;
      var first = celdas[0];
      if (!first || first.querySelector("a, button, input")) return;
      var txt = (first.textContent || "").trim();
      if (!_TAG_RE.test(txt)) return;
      var tablaEl = first.closest("table");
      if (!tablaEl) return;
      var encabezado = tablaEl.querySelector("tr");
      var th0 = encabezado ? encabezado.querySelector("th") : null;
      if (th0 && _CAB_NO_CLICK.test(th0.textContent || "")) return;
      var link = document.createElement("a");
      link.href = "#";
      link.className = "ficha-link";
      link.title = "Ver ficha de " + txt;
      link.textContent = txt;
      link.addEventListener("click", function (e) {
        e.preventDefault();
        abrirFichaDesdeTag(txt);
      });
      first.textContent = "";
      first.appendChild(link);
    });
  }
  function fetchJSON(url, cb, target) {
    target = target || vista;
    var ctrl = ("AbortController" in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctrl) ctrl.abort(); }, 25000);
    fetch(url, ctrl ? { signal: ctrl.signal } : {}).then(function (r) {
      if (r.status === 401) { window.location = "/login"; throw new Error("no autorizado"); }
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (d) { clearTimeout(to); cb(d); })
      .catch(function (e) {
        clearTimeout(to);
        if (target) target.innerHTML = icon("xCircle", 14) + "No se pudo cargar (" + esc(e && e.message || e) + "). <button data-accion='reload'>Reintentar</button>";
      });
  }
  function mostrarFormularioAnimal(f, tagPrellenado, defaults) {
    var esEdicion = !!(f && f.tag);
    var overlay = document.getElementById("animal-form-modal");
    if (overlay) overlay.remove();

    function val(v) { return v == null ? "" : esc(v); }
    var madreTag = (defaults && defaults.madre_tag) || (f && f.madre && f.madre.tag) || "";
    var padreTag = (defaults && defaults.padre_tag) || (f && f.padre && f.padre.tag) || "";
    var nacimiento = (defaults && defaults.fecha_nacimiento) || ((f && f.fecha_nacimiento) ? String(f.fecha_nacimiento).slice(0, 10) : "");
    var sexoDef = (defaults && defaults.sexo) || (f && f.sexo) || "";
    var potreroDef = (defaults && defaults.potrero) || (f && f.potrero && f.potrero !== "Sin potrero asignado" ? f.potrero : "");

    function campo(id, etiqueta, valorAttr, extra) {
      return "<label style='display:block; font-size:12.5px; font-weight:600; margin-bottom:2px;'>" + etiqueta
        + "<input id='" + id + "' value='" + valorAttr + "'" + (extra || "")
        + " style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:400; margin-top:2px;'></label>";
    }

    var esToro = Boolean(
      (f && f.tag && /^T\d+/i.test(f.tag)) ||
      (f && f.notas && (/\[REPRODUCTOR\]/i.test(f.notas) || /\bTORO\b/i.test(f.notas)))
    );

    var html = "<div id='animal-form-modal' class='modal-overlay'>"
      + "<div class='modal-contenido' style='max-width:480px;'>"
      + "<div class='modal-header'><b>" + icon(esEdicion ? "pencil" : "plus", 15) + (esEdicion ? "Editar Animal " + val(f.tag) : "Crear Animal Nuevo") + "</b>"
      + "<button type='button' class='modal-cerrar' id='btn-cerrar-animal-form' aria-label='Cerrar'>" + icon("xmark", 16) + "</button></div>"
      + "<form id='form-animal' style='padding:16px; display:flex; flex-direction:column; gap:10px; max-height:70vh; overflow-y:auto;'>"
      + campo("an-tag", "Arete / Tag *", val((f && f.tag) || tagPrellenado), esEdicion ? " disabled" : " required autofocus placeholder='ej. 47'")
      + (esEdicion && (window.__usuarioActual && window.__usuarioActual.rol === "OWNER")
          ? "<div style='margin-top:-4px; margin-bottom:4px;'><button type='button' id='btn-ir-rectificar' class='chip ambar' style='font-size:11.5px; cursor:pointer; font-weight:600; padding:3px 8px; display:inline-flex; align-items:center; gap:4px;'>" + icon("tag", 12) + " ¿Arete equivocado en campo? Rectificar chapeta aquí</button></div>"
          : "")
      + campo("an-nombre", "Nombre", val(f && f.nombre), " placeholder='ej. Carranga'")
      + "<label style='display:block; font-size:12.5px; font-weight:600;'>Sexo<select id='an-sexo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:400; margin-top:2px;'>"
      + "<option value=''>—</option>"
      + "<option value='Hembra'" + (sexoDef === "Hembra" ? " selected" : "") + ">Hembra</option>"
      + "<option value='Macho'" + (sexoDef === "Macho" ? " selected" : "") + ">Macho</option>"
      + "</select></label>"
      + "<div id='an-toro-wrap' style='display:" + (sexoDef === "Macho" ? "block" : "none") + "; margin:2px 0 4px; padding:8px 12px; background:rgba(34,197,94,0.08); border-radius:6px; border:1px solid rgba(34,197,94,0.25);'>"
      + "<label style='display:flex; align-items:center; gap:8px; font-size:12.5px; font-weight:600; cursor:pointer; margin:0;'>"
      + "<input type='checkbox' id='an-es-toro'" + (esToro ? " checked" : "") + " style='width:16px; height:16px;'> "
      + icon("cow", 14) + "¿Es Reproductor / Toro activo de la finca?"
      + "</label></div>"
      + campo("an-raza", "Raza (código o nombre)", val(f && f.raza), " placeholder='ej. I, T, C, M'")
      + (esEdicion ? "<div style='margin-top:-4px; margin-bottom:4px;'><button type='button' id='btn-ir-comp-desde-form' class='chip ambar' style='font-size:11.5px; cursor:pointer; font-weight:600; padding:3px 8px; display:inline-flex; align-items:center; gap:4px;'>" + icon("dna", 12) + " Configurar Multi-Raza en Porcentajes (%)</button></div>" : "")
      + campo("an-nacimiento", "Fecha de nacimiento", nacimiento, " type='date'")
      + campo("an-madre", "Madre (tag)", val(madreTag), " list='dl-tags' placeholder='ej. 47'")
      + campo("an-padre", "Padre (tag)", val(padreTag), " list='dl-tags' placeholder='ej. T1'")
      + campo("an-potrero", "Potrero", val(potreroDef), " list='dl-potreros' placeholder='ej. Guayabal'")
      + campo("an-hierro", "Hierro / Marca a fuego", val(f && f.hierro), " placeholder='ej. JA'")
      + campo("an-chip", "Chip / RFID", val(f && f.chip), " placeholder='ej. 985...'")
      + campo("an-color", "Color / Pelo", val(f && f.color), " placeholder='ej. Negro'")
      + "<label style='display:block; font-size:12.5px; font-weight:600;'>Notas<textarea id='an-notas' rows='2' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); font-weight:400; margin-top:2px; font-family:inherit;'>" + val(f && f.notas) + "</textarea></label>"
      + "<p id='animal-form-error' class='aviso' style='display:none;'></p>"
      + "<button type='submit' class='tema-btn' style='padding:10px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer;'>" + icon("save", 15) + (esEdicion ? "Guardar Cambios" : "Crear Animal") + "</button>"
      + "</form></div></div>";

    var wrap = document.createElement("div");
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstChild);

    var ov = document.getElementById("animal-form-modal");
    function cerrarModal() { if (ov) ov.remove(); }
    var btnCerrar = document.getElementById("btn-cerrar-animal-form");
    if (btnCerrar) btnCerrar.addEventListener("click", cerrarModal);
    var selSexo = document.getElementById("an-sexo");
    var wrapToro = document.getElementById("an-toro-wrap");
    if (selSexo && wrapToro) {
      selSexo.addEventListener("change", function () {
        wrapToro.style.display = selSexo.value === "Macho" ? "block" : "none";
      });
    }
    var btnIrRect = document.getElementById("btn-ir-rectificar");
    if (btnIrRect) {
      btnIrRect.addEventListener("click", function () {
        var t = (f && f.tag) || "";
        cerrarModal();
        mostrarModalRectificarTag(t);
      });
    }
    var btnIrComp = document.getElementById("btn-ir-comp-desde-form");
    if (btnIrComp) {
      btnIrComp.addEventListener("click", function () {
        var t = (f && f.tag) || "";
        cerrarModal();
        mostrarModalComposicionRacial(t);
      });
    }
    ov.addEventListener("click", function (e) { if (e.target === ov) cerrarModal(); });

    var form = document.getElementById("form-animal");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var tag = (q("#an-tag").value || "").trim();
      var chkEsToro = document.getElementById("an-es-toro");
      var notasVal = (q("#an-notas") && q("#an-notas").value) || "";
      if (chkEsToro && chkEsToro.checked) {
        if (!/\[REPRODUCTOR\]/i.test(notasVal)) {
          notasVal = (notasVal ? notasVal + " " : "") + "[REPRODUCTOR]";
        }
      } else if (chkEsToro && !chkEsToro.checked) {
        notasVal = notasVal.replace(/\[REPRODUCTOR\]/gi, "").trim();
      }
      var payload = {
        nombre: q("#an-nombre").value, sexo: q("#an-sexo").value,
        raza: q("#an-raza").value, fecha_nacimiento: q("#an-nacimiento").value,
        madre_tag: q("#an-madre").value, padre_tag: q("#an-padre").value,
        potrero: q("#an-potrero").value, hierro: q("#an-hierro").value,
        chip: q("#an-chip").value, color: q("#an-color").value,
        notas: notasVal,
      };
      if (!esEdicion) payload.tag = tag;
      var errorEl = document.getElementById("animal-form-error");
      var url = esEdicion ? "/api/animal/" + encodeURIComponent(tag) : "/api/animal";
      var metodo = esEdicion ? "PUT" : "POST";
      fetch(url, {
        method: metodo, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      }).then(function (r) { return r.json().then(function (d) { return { status: r.status, body: d }; }); })
        .then(function (res) {
          if (res.status >= 200 && res.status < 300 && res.body.ok) {
            cerrarModal();
            _cacheToros = null;
            cargarListaToros();
            abrirFicha(tag, vista, true);
            irAVista("ficha");
          } else if (errorEl) {
            errorEl.textContent = (res.body.error || "No se pudo guardar.");
            errorEl.style.display = "block";
          }
        }).catch(function (err) {
          if (errorEl) { errorEl.textContent = (err && err.message || err); errorEl.style.display = "block"; }
        });
    });
  }

