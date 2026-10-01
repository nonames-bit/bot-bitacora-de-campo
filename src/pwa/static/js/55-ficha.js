  /* ---------- Ficha con pestañas ---------- */
  var TABS = [
    { id: "general", label: icon("cow") + "General" },
    { id: "genealogia", label: icon("dna") + "Genealogía (3G)" },
    { id: "repro", label: icon("sperm") + "Reproducción" },
    { id: "sanidad", label: icon("shieldPlus") + "Tratamientos" },
    { id: "leche", label: icon("milk") + "Leche" },
    { id: "pesos", label: icon("scale") + "Pesos" }
  ];
  // HTML del panel "identificar por foto del arete" (solo en el dashboard,
  // no en la página /ficha/<tag> que llega desde el QR ya identificado).
  function inputFotoIdentHtml() {
    return "<input type='file' id='f-ident-foto' class='input-foto-oculto' accept='image/*' capture='environment'>"
      + "<label for='f-ident-foto' class='btn-foto-campo'>" + icon("camera", 15) + "Tomar foto o elegir</label>"
      + "<span class='foto-nombre' id='ident-foto-nombre'>Ninguna foto</span>";
  }
  function identPanelHtml(colapsable) {
    if (colapsable) {
      return "<details class='card ident-box' style='margin-top:10px; margin-bottom:12px; padding:10px 14px;'>"
        + "<summary style='cursor:pointer; font-weight:600; font-size:13px; color:var(--texto-suave); user-select:none; display:flex; align-items:center; justify-content:space-between; outline:none;'>"
        + "<span>" + icon("camera", 15) + " 📷 Identificar otro animal por foto o QR</span>"
        + "<span style='font-size:11px; opacity:0.75;'>▼ desplegar</span>"
        + "</summary>"
        + "<div style='margin-top:10px;'>"
        + "<p class='aviso' style='margin:4px 0 8px; font-size:12px;'>Tome la foto del arete con el celular o pegue un código RFID/arete y pulse Cargar. También puede <b>escanear un QR</b> de las fichas de corral.</p>"
        + "<div style='display:flex; gap: 8px; flex-wrap:wrap; align-items:center; margin:6px 0'>"
        + inputFotoIdentHtml()
        + "<button id='btn-ident' type='button'>" + icon("search") + "Identificar</button>"
        + "<button id='btn-scan-qr' type='button'>" + icon("camera") + "Escanear QR</button>"
        + "</div>"
        + "<span id='ident-estado' class='aviso'></span>"
        + "<div id='ident-resultado'></div>"
        + "<video id='qr-video' style='display:none; width:100%; max-width:320px; border-radius:8px; margin-top:8px' autoplay playsinline></video>"
        + "</div>"
        + "</details>";
    }
    return "<div class='card ident-box' style='margin-bottom:10px'>"
      + "<b>" + icon("camera") + "Identificar por foto del arete</b>"
      + "<p class='aviso' style='margin:4px 0'>Tome la foto del arete con el celular o pegue un código RFID/arete arriba y pulse Cargar. También puede <b>escanear un QR</b> de las fichas de corral.</p>"
      + "<div style='display:flex; gap: 8px; flex-wrap:wrap; align-items:center; margin:6px 0'>"
      + inputFotoIdentHtml()
      + "<button id='btn-ident' type='button'>" + icon("search") + "Identificar</button>"
      + "<button id='btn-scan-qr' type='button'>" + icon("camera") + "Escanear QR</button>"
      + "</div>"
      + "<span id='ident-estado' class='aviso'></span>"
      + "<div id='ident-resultado'></div>"
      + "<video id='qr-video' style='display:none; width:100%; max-width:320px; border-radius:8px; margin-top:8px' autoplay playsinline></video>"
      + "</div>";
  }
  function resolverEstadosFicha(f) {
    if (f.estado_fisiologico && f.estado_reproductivo) {
      return { fisio: f.estado_fisiologico, repro: f.estado_reproductivo };
    }
    var sx = String(f.sexo || "").toLowerCase();
    var esH = sx.indexOf("h") === 0 || sx.indexOf("f") === 0;
    var esM = sx.indexOf("m") === 0;
    var edadD = f.edad_dias;
    var lac = f.lactancia || {};
    var ultP = f.ultimo_parto || {};
    var tieneP = Boolean(ultP && ultP.fecha) || Boolean(f.partos && f.partos.length);
    var tag = String(f.tag || "");
    var isToro = tag.match(/^T\d+/i) || /TORO|REPRODUCTOR/i.test(tag + " " + (f.nombre || "") + " " + (f.notas || ""));

    var fisio = { codigo: "ADULTO", titulo: "Adulto", badge: "Adulto", color: "gris", icono: "cow", detalle: "" };
    var repro = { codigo: "SIN_DATOS", titulo: f.estado_repro || "Sin datos", badge: f.estado_repro || "Sin datos", color: "gris", dias_abiertos: f.dias_abiertos, alerta: null, detalle: "" };

    if (esM) {
      if (isToro) {
        fisio = { codigo: "TORO", titulo: "Toro Reproductor", badge: "Toro Reproductor", color: "azul", icono: "bull", detalle: "Macho reproductor activo de la finca" };
        repro = { codigo: "TORO_REPRODUCTOR", titulo: "Toro reproductor activo", badge: "Toro Reproductor", color: "azul", detalle: "Macho padre reproductor" };
      } else if (edadD != null && edadD < 365) {
        fisio = { codigo: "CRIA_MACHO", titulo: "Cría (Ternero)", badge: "Cría (Ternero)", color: "verde", icono: "calf", detalle: "Lactante al pie" };
        repro = { codigo: "MACHO", titulo: "Macho en levante", badge: "Ternero", color: "gris" };
      } else {
        fisio = { codigo: "NOVILLO", titulo: "Novillo / Macho", badge: "Novillo", color: "gris", icono: "cow", detalle: "Macho en desarrollo" };
        repro = { codigo: "MACHO", titulo: "Macho", badge: "Macho", color: "gris" };
      }
    } else if (esH) {
      if (edadD != null && edadD < 365 && !tieneP) {
        fisio = { codigo: "CRIA_HEMBRA", titulo: "Cría (Ternera)", badge: "Cría (Ternera)", color: "verde", icono: "calf", detalle: "Lactante al pie" };
        repro = { codigo: "CRECIMIENTO", titulo: "En desarrollo / Crecimiento", badge: "Ternera", color: "gris" };
      } else if (edadD != null && edadD < 730 && !tieneP) {
        fisio = { codigo: "NOVILLA_LEVANTE", titulo: "Novilla de levante", badge: "Novilla levante", color: "ambar", icono: "cow", detalle: "En crecimiento" };
        repro = { codigo: "CRECIMIENTO", titulo: "En levante", badge: "Novilla levante", color: "gris" };
      } else if (edadD != null && edadD < 1095 && !tieneP) {
        fisio = { codigo: "NOVILLA_VIENTRE", titulo: "Novilla de vientre", badge: "Novilla vientre", color: "purpura", icono: "cow", detalle: "Apta para primer servicio / IA" };
        repro = { codigo: "NOVILLA_APTA", titulo: "Novilla apta para servicio", badge: "Apta para servicio", color: "purpura" };
      } else {
        if (lac.estado === "En ordeño") {
          fisio = { codigo: "VACA_ORDENO", titulo: "Vaca en Ordeño", badge: lac.del_dias != null ? "En Ordeño (" + lac.del_dias + " DEL)" : "En Ordeño", color: "verde", icono: "milk", detalle: "Lactancia activa" };
        } else {
          fisio = { codigo: "VACA_SECA", titulo: "Vaca Seca", badge: "Vaca Seca", color: "ambar", icono: "grass", detalle: "Período seco / horra" };
        }
        var da = f.dias_abiertos;
        if (da != null) {
          var daCol = da > 150 ? "rojo" : (da > 90 ? "ambar" : "gris");
          repro = { codigo: "VACIA_SIN_PALPAR", titulo: "Vacía / Abierta (" + da + " días post-parto)", badge: "Vacía (" + da + "d abiertos)", color: daCol, dias_abiertos: da };
        } else {
          repro = { codigo: "VACIA_SIN_PALPAR", titulo: "Vaca Vacía / Sin palpar", badge: "Vacía (Sin palpar)", color: "gris" };
        }
      }
    }
    return { fisio: fisio, repro: repro };
  }
  function fichaHtml(f, showIdent) {
    var catSg = String(f.categoria_sg || "").toUpperCase();
    var esTernero = esAnimalTernero(f);
    var esToro = !esTernero && esAnimalToro(f);
    var esParida = !esTernero && !esToro && ((f.estado_fisiologico && f.estado_fisiologico.codigo === "VACA_ORDENO")
      || (f.lactancia && f.lactancia.estado === "En ordeño" && f.lactancia.del_dias < 200)
      || (f.crias && f.crias.length > 0)
      || (catSg.indexOf("PARIDA") >= 0));

    var head = "<div class='ficha-head' style='display:flex; gap:14px; align-items:center; background:var(--superficie); padding:14px; border:1px solid var(--borde); border-radius:10px; margin-bottom:12px;'>";
    if (f.fotos && f.fotos.length && f.fotos[0].url) {
      head += "<div class='foto-card-mini' title='Toca para agrandar' style='cursor:zoom-in; position:relative; flex-shrink:0; border-radius:8px; overflow:hidden;'>"
        + "<img class='avatar zoomable-img' src='" + esc(f.fotos[0].url) + "' alt='Foto principal " + esc(f.tag) + "' style='width:64px; height:64px; border-radius:8px; object-fit:cover; display:block;' data-onerror-hide='parent'>"
        + "<div style='position:absolute; bottom:2px; right:2px; background:rgba(0,0,0,0.65); border-radius:3px; padding:2px 3px; color:#fff; display:flex; align-items:center; pointer-events:none;'>" + icon("search", 10) + "</div>"
        + "</div>";
    } else {
      // (P1.5) Miniatura 60x32: PNG estático (no necesita animar y pesa ~10 KB
      // frente a los cientos de KB del WebP/GIF animado).
      var defaultAnim = esTernero ? "/static/ternero.png" : (esToro ? "/static/toro_reproductor.png" : (esParida ? "/static/vaca_con_cria.png" : "/static/vaca_comiendo.png"));
      var defaultTitle = esTernero ? "Ternero / Cría" : (esToro ? "Toro reproductor" : "Bovino");
      head += "<div style='width:64px; height:64px; border-radius:8px; background:var(--verde-marca-pastel); color:var(--verde-marca); display:flex; align-items:center; justify-content:center; flex-shrink:0; overflow:hidden;' title='" + defaultTitle + "'>"
        + "<img src='" + defaultAnim + "' alt='Ilustración' style='width:60px; height:32px; object-fit:contain; display:block;'>"
        + "</div>";
    }
    var estadoChip = "";
    var stUpper = String(f.estado || "").toUpperCase();
    if (stUpper === "ACTIVO") {
      estadoChip = "<span class='chip verde'>ACTIVO</span>";
    } else if (stUpper === "VENDIDO") {
      var fVenta = (f.venta && f.venta.fecha) ? (" · " + fechaCorta(f.venta.fecha)) : "";
      estadoChip = "<span class='chip ambar' style='font-weight:600; display:inline-flex; align-items:center; gap:4px;'>" + icon("receipt", 12) + "<span>VENDIDO" + esc(fVenta) + "</span></span>";
    } else if (stUpper === "MUERTO") {
      var fMuerte = (f.muerte && f.muerte.fecha) ? (" · " + fechaCorta(f.muerte.fecha)) : "";
      estadoChip = "<span class='chip rojo' style='font-weight:600; display:inline-flex; align-items:center; gap:4px;'>" + icon("cowSkull", 12) + "<span>MUERTO" + esc(fMuerte) + "</span></span>";
    } else if (stUpper === "DESCARTADO") {
      var fDesc = (f.venta && f.venta.fecha) ? (" · " + fechaCorta(f.venta.fecha)) : ((f.muerte && f.muerte.fecha) ? (" · " + fechaCorta(f.muerte.fecha)) : "");
      estadoChip = "<span class='chip ambar' style='font-weight:600;'>" + esc(f.estado) + esc(fDesc) + "</span>";
    } else if (f.estado) {
      estadoChip = "<span class='chip gris'>" + esc(f.estado) + "</span>";
    }

    var z = resolverEstadosFicha(f);
    var ef = z.fisio;
    var er = z.repro;

    var fisioChip = "";
    if (ef && ef.badge) {
      var fIcon = ef.icono === "milk" ? icon("milk", 12)
                : ef.icono === "calf" ? icon("calf", 12)
                : ef.icono === "grass" ? icon("grass", 12)
                : icon("cow", 12);
      fisioChip = "<span class='chip " + (ef.color || "gris") + "' style='font-weight:700; display:inline-flex; align-items:center; gap:4px;' title='" + esc(ef.detalle || ef.titulo || "") + "'>" + fIcon + "<span>" + esc(ef.badge) + "</span></span>";
    }

    var reproChip = "";
    if (er && er.badge && er.codigo !== "TORO_REPRODUCTOR" && er.codigo !== "MACHO" && er.codigo !== "CRECIMIENTO") {
      var rIcon = er.codigo === "PREÑADA" ? icon("sperm", 12)
                : er.codigo === "SERVIDA_SIN_PALPAR" ? icon("hourglass", 12)
                : er.alerta ? icon("alert", 12)
                : icon("circleEmpty", 12);
      reproChip = "<span class='chip " + (er.color || "gris") + "' style='font-weight:700; display:inline-flex; align-items:center; gap:4px;' title='" + esc(er.detalle || er.titulo || "") + "'>" + rIcon + "<span>" + esc(er.badge) + "</span></span>";
    }

    var potChip = f.potrero ? "<span class='chip gris' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("grass", 12) + "<span>" + esc(f.potrero) + "</span></span>" : "";
    var hierroChip = f.hierro ? ("<span class='chip ambar' style='font-weight:600; display:inline-flex; align-items:center; gap:3px;' title='Hierro / Marca de la ganadería'>" + icon("flame", 12) + "<span>Hierro <b>" + esc(f.hierro) + "</b></span></span>") : "";
    var retiroChip = f.en_retiro ? "<span class='chip rojo' style='font-weight:bold; display:inline-flex; align-items:center; gap:4px;'>" + icon("alert", 12) + "<span>EN RETIRO</span></span>" : "";

    head += "<div class='datos' style='flex:1; min-width:0;'>"
      + "<div style='display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin-bottom:5px;'>"
      + "<b style='font-size:19px; letter-spacing:-0.02em;'>" + esc(f.tag) + (f.nombre ? " · " + esc(f.nombre) : "") + "</b>"
      + estadoChip + retiroChip
      + "</div>"
      + "<div style='display:flex; flex-wrap:wrap; gap:5px; align-items:center; margin-bottom:5px;'>"
      + fisioChip + reproChip + potChip + hierroChip
      + "</div>"
      + "<span class='meta' style='font-size:12px; color:var(--texto-suave);'>"
      + esc(f.sexo || "") + " · " + esc(f.raza || "S/D")
      + (f.edad_str ? " · <b>" + esc(f.edad_str) + "</b>" : (f.fecha_nacimiento ? " · Nac: " + esc(fechaCorta(f.fecha_nacimiento)) : ""))
      + (f.categoria_sg ? " · " + esc(f.categoria_sg) : "")
      + "</span>"
      + "</div>";

    var rolEd = window.__usuarioActual && window.__usuarioActual.rol;
    var btnEditar = (rolEd === "OWNER" || rolEd === "ADMIN")
      ? "<button type='button' class='tema-btn' data-accion='editar-animal' style='font-size:12px; padding:6px 10px; white-space:nowrap; display:inline-flex; align-items:center; cursor:pointer;'>" + icon("pencil", 15) + "Editar</button>"
      : "";
    var btnRectificar = (rolEd === "OWNER")
      ? "<button type='button' class='tema-btn btn-rectificar-tag' data-accion='rectificar-tag' data-tag='" + esc(f.tag) + "' style='font-size:12px; padding:6px 10px; white-space:nowrap; display:inline-flex; align-items:center; gap:5px; cursor:pointer; background:var(--color-ambar-bg); color:var(--color-ambar-txt); border:1px solid var(--color-ambar-txt); font-weight:600;' title='Proceso especial: rectificar chapeta mal leída en campo'>" + icon("tag", 14) + "Rectificar Chapeta</button>"
      : "";
    var barraAccionesCampo = "";
    if (stUpper === "ACTIVO") {
      var esHembra = (f.sexo || "").toLowerCase().indexOf("h") === 0;
      var potreroAnim = (f.potrero && f.potrero !== "Sin potrero asignado") ? f.potrero : "";

      barraAccionesCampo = "<div class='ficha-acciones-campo' style='margin:10px 0 12px; padding:10px 12px; background:var(--tarjeta-fondo); border:1px solid var(--borde); border-radius:8px;'>"
        + "<div style='font-size:11px; font-weight:700; color:var(--texto-suave); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px; display:flex; align-items:center; gap:6px;'>"
        + icon("clipboard", 13) + "Acciones Rápidas en Manga / Corral (Prellenado Automático)</div>"
        + "<div style='display:flex; gap:6px; flex-wrap:wrap; align-items:center;'>"
        + "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='pesaje' data-tag='" + esc(f.tag) + "' style='cursor:pointer; font-weight:600; padding:6px 10px; display:inline-flex; align-items:center; gap:5px;' title='Registrar peso en báscula'>" + icon("scale", 14) + "Pesar</button>"
        + (esHembra ? "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='palpacion' data-tag='" + esc(f.tag) + "' style='cursor:pointer; font-weight:600; padding:6px 10px; display:inline-flex; align-items:center; gap:5px;' title='Diagnóstico de preñez / tacto'>" + icon("stethoscope", 14) + "Palpar</button>" : "")
        + "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='tratamiento' data-tag='" + esc(f.tag) + "' style='cursor:pointer; font-weight:600; padding:6px 10px; display:inline-flex; align-items:center; gap:5px;' title='Aplicar fármaco / tratamiento'>" + icon("syringe", 14) + "Tratar</button>"
        + "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='traslado' data-tag='" + esc(f.tag) + "' data-potrero='" + esc(potreroAnim) + "' style='cursor:pointer; font-weight:600; padding:6px 10px; display:inline-flex; align-items:center; gap:5px;' title='Trasladar a otro potrero'>" + icon("truck", 14) + "Mover</button>"
        + (esHembra ? "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='servicio' data-tag='" + esc(f.tag) + "' style='cursor:pointer; font-weight:600; padding:6px 10px; display:inline-flex; align-items:center; gap:5px;' title='Inseminar o registrar monta'>" + icon("sperm", 14) + "Servicio / IA</button>" : "")
        + (esHembra ? "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='parto' data-tag='" + esc(f.tag) + "' style='cursor:pointer; font-weight:600; padding:6px 10px; display:inline-flex; align-items:center; gap:5px;' title='Registrar nuevo parto'>" + icon("cowCalf", 14) + "Parto</button>" : "")
        + "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='venta' data-tag='" + esc(f.tag) + "' style='cursor:pointer; font-weight:600; padding:6px 10px; display:inline-flex; align-items:center; gap:5px; background:rgba(217,119,6,0.12); color:#D97706; border-color:#D97706;' title='Registrar venta del animal'>" + icon("receipt", 14) + "Vender</button>"
        + "<button type='button' class='chip' data-accion='capturar-evento' data-tipo='muerte' data-tag='" + esc(f.tag) + "' style='cursor:pointer; font-weight:600; padding:6px 10px; display:inline-flex; align-items:center; gap:5px; background:rgba(220,38,38,0.08); color:var(--color-rojo-txt); border-color:var(--color-rojo-txt);' title='Registrar baja o muerte'>" + icon("cowSkull", 14) + "Baja</button>"
        + "</div></div>";
    }

    head += "<div class='ficha-head-acciones' style='display:flex; flex-direction:column; gap:6px; align-self:flex-start;'>"
      + "<button type='button' class='tema-btn' data-accion='buscar-otro-animal' style='font-size:12px; padding:6px 10px; white-space:nowrap; display:inline-flex; align-items:center; gap:5px; cursor:pointer; font-weight:600;' title='Buscar otra ficha de animal (Ctrl+K)'>"
      + icon("search", 14) + "Buscar otro</button>"
      + "<a href='/api/ficha/" + encodeURIComponent(f.tag) + "/pdf' target='_blank' class='tema-btn' style='font-size:12px; padding:6px 10px; text-decoration:none; white-space:nowrap; display:inline-flex; align-items:center; gap:5px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; box-shadow:0 1px 3px rgba(0,0,0,0.12);' title='Descargar Ficha Técnica Oficial (PDF) con semáforo zootécnico y genealogía'>"
      + icon("filePdf", 15) + "Ficha PDF</a>"
      + btnEditar
      + btnRectificar
      + "</div>";

    head += "</div>";

    var html = head + barraAccionesCampo + erroresHtml(f) + (showIdent ? identPanelHtml(true) : "");
    html += "<div id='ficha-tabs' role='tablist'><div class='mini'>"
      + TABS.map(function (t, i) { return "<button role='tab' aria-selected='" + (i === 0 ? "true" : "false") + "' data-tab='" + t.id + "' class='" + (i === 0 ? "act" : "") + "'>" + t.label + "</button>"; }).join("")
      + "</div></div><div id='ficha-panel'>" + fichaTab("general", f) + "</div>";
    return html;
  }
  function chipResultado(v) {
    var s = String(v == null ? "" : v).toUpperCase();
    if (s === "PREÑADA" || s === "PREGNANT") return "<span class='chip verde'>" + icon("sperm", 14) + "PREÑADA</span>";
    if (s === "VACIA" || s === "VACÍA") return "<span class='chip ambar'>" + icon("circleEmpty", 14) + "VACÍA</span>";
    if (s === "FALLIDO") return "<span class='chip rojo'>" + icon("xmark", 14) + "FALLIDO</span>";
    if (!s) return "—";
    return "<span class='chip gris'>" + esc(v) + "</span>";
  }
  function fichaTab(id, f) {
    var esOwner = window.__usuarioActual && (window.__usuarioActual.rol === "OWNER");
    if (id === "genealogia") {
      var g = f.genealogia_3g || {};
      var cons = g.consanguinidad || f.consanguinidad || {};
      var hg = "";

      // 1. Título y Semáforo de Consanguinidad
      hg += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
        + "<h3 style='margin:0; display:flex; align-items:center; gap:8px;'>" + icon("dna") + "Árbol Genealógico & Trazabilidad (3G)</h3>"
        + "</div>";

      var cClase = cons.clase || (cons.consanguineo ? "rojo" : (cons.evaluable ? "verde" : "gris"));
      var cIcon = cons.consanguineo ? icon("alert", 16) : (cons.evaluable ? icon("shieldCheck", 16) : icon("circleEmpty", 16));
      var cTxt = cons.detalle || (cons.consanguineo ? "Cruzamiento consanguíneo detectado" : (cons.evaluable ? "0.0% Consanguinidad en 3G" : "No evaluable"));

      hg += "<div class='card' style='padding:12px 14px; margin-bottom:14px; display:flex; align-items:center; gap:10px; border-left:4px solid var(--" + (cClase === "verde" ? "color-verde-txt" : (cClase === "rojo" ? "color-rojo-txt" : "borde-fuerte")) + ");'>"
        + "<div style='font-size:20px;'>" + cIcon + "</div>"
        + "<div style='flex:1; font-size:13px;'>"
        + "<b>Control de Consanguinidad Parental:</b> <span class='chip " + cClase + "'>" + esc(cTxt) + "</span>"
        + "<div style='font-size:11.5px; color:var(--texto-suave); margin-top:3px;'>Regla de control de 3 generaciones antes de autorizar cruzamiento o servicio de monta/I.A.</div>"
        + "</div>"
        + "</div>";

      // Helper nodo animal
      function nodoAnimal(an, label, icono) {
        if (!an || !an.tag) {
          return "<div style='background:var(--superficie); border:1px dashed var(--borde-fuerte); border-radius:8px; padding:10px; font-size:12px; color:var(--texto-suave);'>"
            + "<div style='font-weight:600; font-size:11px; text-transform:uppercase; color:var(--texto-suave); margin-bottom:2px;'>" + icono + " " + esc(label) + "</div>"
            + "<div>Desconocido / Sin Registro</div>"
            + "</div>";
        }
        var nom = an.nombre ? " · " + esc(an.nombre) : "";
        var rz = an.raza ? " [" + esc(an.raza) + "]" : "";
        var hie = an.hierro ? (" <span class='chip ambar' style='font-size:10px; padding:1px 4px;' title='Hierro'>" + esc(an.hierro) + "</span>") : "";
        return "<div style='background:var(--superficie); border:1px solid var(--borde-fuerte); border-radius:8px; padding:10px; font-size:12.5px; box-shadow:0 1px 3px var(--sombra);'>"
          + "<div style='font-weight:600; font-size:11px; text-transform:uppercase; color:var(--texto-suave); margin-bottom:4px;'>" + icono + " " + esc(label) + "</div>"
          + "<div><a href='#' class='ficha-link' data-ir-ficha=\"" + esc(an.tag) + "\" style='font-weight:bold; font-size:14px; text-decoration:none;'><b>" + esc(an.tag) + "</b></a>" + nom + " <span class='chip gris' style='font-size:11px; padding:1px 5px;'>" + esc(an.raza || "S/D") + "</span>" + hie + "</div>"
          + "</div>";
      }

      // 2. Pedigree Diagram
      hg += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
        + "<h4 style='margin-top:0;'>" + icon("gitBranch", 16) + "Pedigree Estructurado (3 Generaciones)</h4>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; margin-top:10px;'>"

        // Línea Paterna
        + "<div style='background:rgba(47,82,51,0.03); border:1px solid var(--borde); border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:10px;'>"
        + "<div style='font-weight:bold; color:var(--verde-marca); border-bottom:1px solid var(--borde); padding-bottom:6px; font-size:13px; display:flex; align-items:center; gap:6px;'>🐂 LÍNEA PATERNA</div>"
        + nodoAnimal(f.padre, "Padre", "🐂")
        + "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte); display:flex; flex-direction:column; gap:8px;'>"
        + nodoAnimal(f.abuelo_pat || g.abuelo_pat, "Abuelo Paterno", "🐂")
        + (g.bisabuelos && g.bisabuelos.pat_pat_p ? "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte);'>" + nodoAnimal(g.bisabuelos.pat_pat_p, "Bisabuelo (PP)", "🧬") + "</div>" : "")
        + nodoAnimal(f.abuela_pat || g.abuela_pat, "Abuela Paterna", "🐄")
        + (g.bisabuelos && g.bisabuelos.pat_mat_m ? "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte);'>" + nodoAnimal(g.bisabuelos.pat_mat_m, "Bisabuela (PM)", "🧬") + "</div>" : "")
        + "</div>"
        + "</div>"

        // Línea Materna
        + "<div style='background:rgba(47,82,51,0.03); border:1px solid var(--borde); border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:10px;'>"
        + "<div style='font-weight:bold; color:var(--verde-marca); border-bottom:1px solid var(--borde); padding-bottom:6px; font-size:13px; display:flex; align-items:center; gap:6px;'>🐄 LÍNEA MATERNA</div>"
        + nodoAnimal(f.madre, "Madre", "🐄")
        + "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte); display:flex; flex-direction:column; gap:8px;'>"
        + nodoAnimal(f.abuelo_mat || g.abuelo_mat, "Abuelo Materno", "🐂")
        + (g.bisabuelos && g.bisabuelos.mat_pat_p ? "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte);'>" + nodoAnimal(g.bisabuelos.mat_pat_p, "Bisabuelo (MP)", "🧬") + "</div>" : "")
        + nodoAnimal(f.abuela_mat || g.abuela_mat, "Abuela Materna", "🐄")
        + (g.bisabuelos && g.bisabuelos.mat_mat_m ? "<div style='padding-left:10px; border-left:2px solid var(--borde-fuerte);'>" + nodoAnimal(g.bisabuelos.mat_mat_m, "Bisabuela (MM)", "🧬") + "</div>" : "")
        + "</div>"
        + "</div>"

        + "</div></div>";

      // 3. Descendencia / Crías Registradas
      var crias = (f.crias && f.crias.length) ? f.crias : ((g.crias && g.crias.length) ? g.crias : (f.partos || []));
      hg += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
        + "<h4 style='margin-top:0; display:flex; align-items:center; gap:6px;'>" + icon("cowCalf", 18) + "Descendencia & Crías Registradas (" + crias.length + ")</h4>";

      if (crias.length) {
        hg += "<div style='display:flex; flex-direction:column; gap:8px; margin-top:10px;'>";
        crias.forEach(function (c) {
          var cTag = c.cria_tag || c.tag || "Sin arete";
          var cNom = c.nombre ? " (" + esc(c.nombre) + ")" : "";
          var cSx = c.sexo_cria || c.sexo || "S/D";
          var cFec = fechaCorta(c.fecha_parto || c.fecha || c.fecha_nacimiento) || "S/D";
          var cEst = String(c.estado_cria || c.estado || "VIVO").toUpperCase();
          var estChip = cEst === "MUERTO" ? "<span class='chip rojo'>Muerto</span>" : "<span class='chip verde'>Vivo</span>";
          var pNac = c.peso_nacimiento ? " · " + c.peso_nacimiento + " kg" : "";

          var linkTag = cTag !== "Sin arete"
            ? "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(cTag) + "\" style='font-size:14px; font-weight:bold; display:inline-flex; align-items:center; gap:5px; text-decoration:none;'>" + icon("calf", 14) + "<span>" + esc(cTag) + "</span></a>"
            : "<span style='color:var(--texto-suave); display:inline-flex; align-items:center; gap:5px;'>" + icon("calf", 14) + "<span>Sin arete</span></span>";

          var btnBorrarCria = (esOwner && c.parto_id)
            ? (" " + renderBtnEliminar("parto", c.parto_id, "Parto " + cTag + " (" + cFec + ")"))
            : "";

          hg += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; background:var(--superficie); border:1px solid var(--borde); border-radius:8px; padding:10px 12px;'>"
            + "<div>" + linkTag + " <span style='font-size:13px; color:var(--texto);'>" + cNom + "</span> <span class='meta' style='font-size:12px;'>· " + esc(cSx) + " · Nac: <b>" + esc(cFec) + "</b>" + pNac + "</span></div>"
            + "<div style='display:flex; align-items:center; gap:6px;'>" + estChip + btnBorrarCria + "</div>"
            + "</div>";
        });
        hg += "</div>";
      } else {
        hg += "<p class='aviso' style='margin:8px 0;'>" + icon("info", 14) + "No tiene crías descendientes registradas en la base de datos.</p>";
      }
      hg += "</div>";

      // 4. Vista de Texto Resumido (Telegram / WhatsApp)
      var txtArbol = (g.texto_arbol || "").trim();
      if (txtArbol) {
        hg += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
          + "<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>"
          + "<h4 style='margin:0; font-size:13px;'>" + icon("notes", 15) + "Formato de Texto Compartible (Telegram / WhatsApp)</h4>"
          + "<button type='button' class='tema-btn' data-accion='copiar-arbol' style='font-size:11px; padding:4px 8px;'>" + icon("copy", 12) + "Copiar Árbol</button>"
          + "</div>"
          + "<pre style='background:var(--fondo); border:1px solid var(--borde); border-radius:6px; padding:10px; font-size:11.5px; line-height:1.45; overflow-x:auto; margin:0; font-family:var(--font-mono); white-space:pre-wrap;'>" + esc(txtArbol) + "</pre>"
          + "</div>";
      }

      return hg;
    }
    if (id === "repro") {
      var h = "";
      var esHembra = String(f.sexo || "").toUpperCase() === "HEMBRA" || f.sexo === "H";
      if (esHembra) {
        h += "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px; background:var(--superficie); padding:10px 12px; border-radius:8px; border:1px solid var(--borde);'>"
          + "<div style='font-size:13px; font-weight:700; color:var(--texto); display:flex; align-items:center; gap:6px;'>" + icon("stethoscope", 16) + "Control Reproductivo & Tactos</div>"
          + "<button type='button' class='tema-btn btn-palpar-ficha-directo' data-tag='" + esc(f.tag) + "' style='font-size:12px; padding:6px 12px; background:var(--verde-marca); color:#fff; font-weight:700; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:5px;'>"
          + icon("stethoscope", 13) + "🖐️ Palpación / Eco</button>"
          + "</div>";
      }
      var colsPartos = [
        ["fecha", "Fecha"], ["cria_tag", "Cría"], ["sexo_cria", "Sexo"],
        ["peso_nacimiento", "Peso nac.", "num"],
        ["estado_cria", "Estado", "text", function (v) {
          return String(v || "").toUpperCase() === "MUERTO"
            ? "<span class='chip rojo'>Muerto</span>" : "<span class='chip verde'>Vivo</span>";
        }]
      ];
      if (esOwner) {
        colsPartos.push(["id", "", "text", function (id, r) {
          return renderBtnEliminar("parto", id, "Parto " + (r.cria_tag || "cría") + " (" + fechaCorta(r.fecha) + ")");
        }]);
      }
      h += "<h4>Partos registrados</h4>" + tabla(f.partos, colsPartos, "Sin partos registrados.");

      var colsServ = [
        ["fecha", "Fecha"],
        ["tipo_servicio", "Tipo", "text", function (v) {
          var t = (v || "").toUpperCase();
          if (t === "MONTA" || t === "MN" || t.indexOf("MONTA") >= 0) return "<span class='chip ambar' style='font-size:11px; font-weight:700;'>" + icon("bull", 12) + " Monta</span>";
          if (t === "IATF") return "<span class='chip verde' style='font-size:11px; font-weight:700;'>" + icon("sperm", 12) + " IATF</span>";
          return "<span class='chip verde' style='font-size:11px; font-weight:700;'>" + icon("sperm", 12) + " IA</span>";
        }],
        ["toro_pajilla", "Toro / Pajilla"],
        ["fep_calculada", "FEP", "text", function (v) { return v ? esc(fechaCorta(v)) : "—"; }],
        ["estado", "Estado", "text", function (v) { return chipResultado(v); }]
      ];
      if (esOwner) {
        colsServ.push(["id", "", "text", function (id, r) {
          return renderBtnEliminar("servicio", id, "Servicio " + (r.tipo_servicio || "") + " (" + fechaCorta(r.fecha) + ")");
        }]);
      }
      h += "<h4>Servicios / IA</h4>" + tabla(f.servicios, colsServ, "Sin servicios registrados.");

      var colsDiag = [
        ["fecha", "Fecha"],
        ["resultado", "Resultado", "text", function (v) { return chipResultado(v); }],
        ["metodo", "Método", "text", function (v) { return v === "ECOGRAFO" ? "<span class='chip azul' style='font-size:11px;'>📟 Ecógrafo</span>" : "<span class='chip gris' style='font-size:11px;'>🖐️ Tacto</span>"; }],
        ["dias_gestacion", "Días", "text", function (v) { return v ? (esc(v) + " d") : "—"; }],
        ["toro_pajuela", "Toro / Pajilla", "text", function (v) { return v ? esc(v) : "—"; }],
        ["hallazgo", "Hallazgo / Notas", "text", function (v, r) {
          var p = [];
          if (v) p.push("<b>" + esc(v) + "</b>");
          if (r && r.detalle) p.push("<small style='color:var(--texto-suave);'>" + esc(r.detalle) + "</small>");
          return p.length ? p.join("<br>") : "—";
        }]
      ];
      if (esOwner) {
        colsDiag.push(["id", "", "text", function (id, r) {
          return renderBtnEliminar("diagnostico", id, "Diagnóstico " + (r.resultado || "") + " (" + fechaCorta(r.fecha) + ")");
        }]);
      }
      h += "<h4>Diagnósticos de gestación</h4>" + tabla(f.diagnosticos, colsDiag, "Sin diagnósticos registrados.");
      if (f.ultimo_servicio && f.ultimo_servicio.fep_calculada) {
        h += "<p class='aviso'>" + icon("calendar", 14) + "FEP (parto estimado): <b>" + esc(fechaCorta(f.ultimo_servicio.fep_calculada)) + "</b></p>";
      }
      return h;
    }
    if (id === "sanidad") {
      var colsTrat = [
        ["fecha", "Fecha"], ["producto", "Producto"], ["dosis", "Dosis"],
        ["fecha_fin_retiro_leche", "Fin leche", "text", function (v) { return v ? esc(v) : "—"; }],
        ["fecha_fin_retiro_carne", "Fin carne", "text", function (v) { return v ? esc(v) : "—"; }]
      ];
      if (esOwner) {
        colsTrat.push(["id", "", "text", function (id, r) {
          return renderBtnEliminar("tratamiento", id, "Tratamiento " + (r.producto || "") + " (" + fechaCorta(r.fecha) + ")");
        }]);
      }
      return "<h4>Tratamientos y retiros</h4>" + tabla(f.tratamientos, colsTrat, "Sin tratamientos registrados.");
    }
    if (id === "leche") {
      var lac = f.lactancia || {};
      var h3 = "<h4>Estado de lactancia</h4>";
      if (lac && lac.fecha_parto) {
        var txtEstado = lac.estado_confirmado && lac.fecha_secado
          ? esc(lac.estado) + " (secada el " + esc(lac.fecha_secado) + ")"
          : esc(lac.estado) + (lac.motivo ? " (" + esc(lac.motivo) + ")" : "");
        h3 += "<p class='aviso'>" + icon("milk", 14) + txtEstado + " · <b>" + esc(lac.del_dias) + "</b> DEL (parto " + esc(lac.fecha_parto) + ")</p>";
        if (lac.estado === "En ordeño") {
          if (lac.en_pausa) {
            h3 += "<div class='card' style='padding:10px 14px; margin:8px 0; border-left:3px solid var(--color-ambar-txt, #D97706);'>"
              + "<p style='margin:0 0 8px; font-size:13px;'>⏸ <b>Ordeño en pausa" + (lac.pausa_motivo ? " · " + esc(lac.pausa_motivo) : "") + "</b>"
              + (lac.pausa_fecha_inicio ? " (desde " + esc(fechaCorta(lac.pausa_fecha_inicio)) + ")" : "")
              + " — no se cuenta en el promedio litros/vaca/día.</p>"
              + "<button type='button' class='tema-btn' data-accion='reanudar-ordeno' data-tag='" + esc(f.tag) + "' style='padding:8px 14px; cursor:pointer;'>▶ Reanudar ordeño</button>"
              + "</div>";
          } else {
            h3 += "<div style='margin:8px 0; display:flex; gap:8px; flex-wrap:wrap;'>"
              + "<button type='button' class='tema-btn' data-accion='pausar-ordeno' data-tag='" + esc(f.tag) + "' style='padding:8px 14px; cursor:pointer;'>⏸ Pausar ordeño (no se está ordeñando)</button>"
              + "<button type='button' class='tema-btn' data-accion='registrar-secado' data-tag='" + esc(f.tag) + "' style='padding:8px 14px; cursor:pointer;'>🍼 Ya está seca</button>"
              + "</div>";
          }
        }
      } else {
        h3 += vacio("Sin lactancia activa (sin parto registrado o es macho).");
      }
      h3 += "<h4>Controles de leche</h4>"
        + tabla(f.controles_leche, [["fecha", "Fecha"], ["litros", "Litros", "num"]], "Sin controles individuales.");
      var img = "<div class='grafico-wrap'><img src='/api/ficha/" + encodeURIComponent(f.tag)
        + "/grafico/lactancia' alt='Curva de lactancia' loading='lazy' data-onerror-hide='self'></div>";
      h3 += img;
      return h3;
    }
    if (id === "pesos") {
      var ult = f.pesajes && f.pesajes.length ? f.pesajes[0] : null;
      var colsPes = [
        ["fecha", "Fecha"], ["peso_kg", "kg", "num"],
        ["gmd_calculada", "GMD (g/d)", "text", function (v) {
          if (v == null) return "—";
          var n = Number(v) * 1000;
          var c = n < 0 ? "rojo" : n > 0 ? "verde" : "gris";
          return "<span class='chip " + c + "'>" + esc(n.toFixed(0)) + "</span>";
        }]
      ];
      if (esOwner) {
        colsPes.push(["id", "", "text", function (id, r) {
          return renderBtnEliminar("pesaje", id, "Pesaje " + (r.peso_kg || "") + " kg (" + fechaCorta(r.fecha) + ")");
        }]);
      }
      var h2 = "<h4>Historial de pesajes</h4>" + tabla(f.pesajes, colsPes, "Sin pesajes registrados.");
      if (ult) h2 += "<p class='aviso'>Último peso: <b>" + esc(ult.peso_kg) + " kg</b> el " + esc(fechaCorta(ult.fecha)) + "</p>";
      h2 += "<div class='grafico-wrap'><img src='/api/ficha/" + encodeURIComponent(f.tag)
        + "/grafico/peso' alt='Curva de peso' loading='lazy' data-onerror-hide='self'></div>";
      return h2;
    }
    // Tab "general"
    var h = "";
    var stUpper = String(f.estado || "").toUpperCase();

    // Banner destacado si el animal fue VENDIDO
    if (stUpper === "VENDIDO") {
      var v = f.venta || {};
      var fecVenta = v.fecha ? fechaCorta(v.fecha) : (f.fecha_salida ? fechaCorta(f.fecha_salida) : "Fecha no registrada");
      var destVenta = v.procedencia_destino ? esc(v.procedencia_destino) : "Destino no especificado";
      var precioVenta = (v.precio != null && Number(v.precio) > 0) ? (" · <b>" + fmtMoneda(v.precio) + "</b>") : "";

      var extraVenta = "";
      if (v.madre_tag) {
        extraVenta += "<div style='margin-top:4px;'><span style='color:var(--texto-suave);'>Venta conjunta (cría al pie):</span> Se vendió junto a su madre <a href='#' class='ficha-link' data-ir-ficha=\"" + esc(v.madre_tag) + "\"><b>" + esc(v.madre_tag) + "</b>" + (v.madre_nombre ? " (" + esc(v.madre_nombre) + ")" : "") + "</a></div>";
      }
      if (v.crias_vendidas && v.crias_vendidas.length) {
        var cvLinks = v.crias_vendidas.map(function (cv) {
          return "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(cv.tag) + "\"><b>" + esc(cv.tag) + "</b>" + (cv.nombre ? " (" + esc(cv.nombre) + ")" : "") + "</a>";
        }).join(", ");
        extraVenta += "<div style='margin-top:4px;'><span style='color:var(--texto-suave);'>Venta conjunta con cría(s):</span> Vendida en la misma fecha junto a " + cvLinks + "</div>";
      }
      var notasVenta = v.notas ? ("<div style='margin-top:6px; font-size:12.5px; background:var(--superficie); padding:6px 10px; border-radius:6px; border:1px solid var(--borde);'><b>Observaciones de venta:</b> " + esc(v.notas) + "</div>") : "";

      h += "<div class='banner-baja banner-baja-venta'>"
        + "<div style='color:var(--color-ambar-txt); margin-top:2px; flex-shrink:0;'>" + icon("receipt", 24) + "</div>"
        + "<div style='flex:1; min-width:0;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;'>"
        + "<div class='titulo-baja'>REGISTRO DE VENTA · ANIMAL VENDIDO</div>"
        + "<span class='chip ambar' style='font-size:12px; font-weight:bold;'>" + icon("calendar", 12) + "Vendido el: " + esc(fecVenta) + "</span>"
        + "</div>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:6px; font-size:13px;'>"
        + "<div><span style='color:var(--texto-suave);'>Fecha de Venta:</span> <b>" + esc(fecVenta) + "</b></div>"
        + "<div><span style='color:var(--texto-suave);'>Comprador / Destino:</span> <b>" + destVenta + "</b>" + precioVenta + "</div>"
        + "</div>"
        + extraVenta
        + notasVenta
        + "</div></div>";
    }

    // Banner destacado si el animal está MUERTO
    if (stUpper === "MUERTO" || (f.muerte && f.muerte.fecha)) {
      var m = f.muerte || {};
      var fecMuerte = m.fecha ? fechaCorta(m.fecha) : (f.fecha_baja ? fechaCorta(f.fecha_baja) : "Fecha no registrada");
      var causaMuerte = m.causa_presunta ? esc(m.causa_presunta) : "Sin causa registrada";
      var notasMuerte = m.notas ? ("<div style='margin-top:6px; font-size:12.5px; background:var(--superficie); padding:6px 10px; border-radius:6px; border:1px solid var(--borde);'><b>Diagnóstico / Necropsia / Notas:</b> " + esc(m.notas) + "</div>") : "";

      h += "<div class='banner-baja banner-baja-muerte'>"
        + "<div style='color:var(--color-rojo-txt); margin-top:2px; flex-shrink:0;'>" + icon("cowSkull", 24) + "</div>"
        + "<div style='flex:1; min-width:0;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;'>"
        + "<div class='titulo-baja'>BAJA POR MUERTE · ANIMAL FALLECIDO</div>"
        + "<span class='chip rojo' style='font-size:12px; font-weight:bold;'>" + icon("calendar", 12) + "Murió el: " + esc(fecMuerte) + "</span>"
        + "</div>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:6px; font-size:13px;'>"
        + "<div><span style='color:var(--texto-suave);'>Fecha de Muerte:</span> <b>" + esc(fecMuerte) + "</b></div>"
        + "<div><span style='color:var(--texto-suave);'>Causa Presunta:</span> <b style='color:var(--color-rojo-txt);'>" + causaMuerte + "</b></div>"
        + "</div>"
        + notasMuerte
        + "</div></div>";
    }

    // Banner si fue DESCARTADO
    if (stUpper === "DESCARTADO" && !(f.venta && f.venta.fecha) && !(f.muerte && f.muerte.fecha)) {
      h += "<div class='banner-baja banner-baja-descarte'>"
        + "<div style='color:var(--color-gris-txt); margin-top:2px; flex-shrink:0;'>" + icon("alert", 24) + "</div>"
        + "<div style='flex:1; min-width:0;'>"
        + "<div class='titulo-baja'>ANIMAL DESCARTADO</div>"
        + "<p style='margin:4px 0 0 0; font-size:13px; color:var(--texto-suave);'>Este animal ha sido dado de baja o descartado del hato activo.</p>"
        + "</div></div>";
    }

    // 1. Alerta de Retiro Sanitario si está en período de retiro
    if (f.en_retiro && f.retiros_activos && f.retiros_activos.length) {
      h += "<div class='card' style='background:var(--color-rojo-bg); color:var(--color-rojo-txt); border:1px solid var(--color-rojo-txt); padding:12px; border-radius:8px; margin-bottom:14px;'>"
        + "<div style='font-weight:bold; font-size:14px; margin-bottom:4px;'>" + icon("alert", 16) + "¡ATENCIÓN! Animal en período de retiro sanitario activo</div>"
        + "<p style='margin:0 0 6px 0; font-size:12.5px;'>No comercializar ni consumir productos de este animal hasta el cumplimiento de los días de retiro reglamentarios:</p>"
        + "<ul style='margin:0; padding-left:18px; font-size:12px;'>";
      f.retiros_activos.forEach(function (r) {
        var det = esc(r.producto || "Fármaco");
        if (r.dosis) det += " (" + esc(r.dosis) + ")";
        if (r.fecha_fin_retiro_leche) det += " · <b>Leche hasta:</b> " + esc(r.fecha_fin_retiro_leche);
        if (r.fecha_fin_retiro_carne) det += " · <b>Carne hasta:</b> " + esc(r.fecha_fin_retiro_carne);
        h += "<li>" + det + "</li>";
      });
      h += "</ul></div>";
    }

    // 2. Fila de KPIs rápidos dinámicos
    var z = resolverEstadosFicha(f);
    var ef = z.fisio;
    var er = z.repro;
    var sx = String(f.sexo || "").toLowerCase();
    var esHembra = sx.indexOf("h") === 0 || sx.indexOf("f") === 0;

    var ultPesoTxt = "—";
    if (f.ultimo_peso && f.ultimo_peso.peso_kg != null) {
      ultPesoTxt = f.ultimo_peso.peso_kg + " kg";
    } else if (f.peso_nacimiento != null) {
      ultPesoTxt = f.peso_nacimiento + " kg (nac)";
    }

    var potreroKpiLabel = "Potrero Actual";
    var potreroKpiVal = f.potrero ? esc(f.potrero) : "Sin asignar";
    if (stUpper === "VENDIDO") {
      potreroKpiLabel = "Estado Hato";
      potreroKpiVal = "Vendido";
    } else if (stUpper === "MUERTO") {
      potreroKpiLabel = "Estado Hato";
      potreroKpiVal = "Baja (Muerte)";
    } else if (stUpper === "DESCARTADO") {
      potreroKpiLabel = "Estado Hato";
      potreroKpiVal = "Descartado";
    }

    if (esHembra && (f.edad_dias == null || f.edad_dias >= 365 || (f.partos && f.partos.length))) {
      var reproKpiVal = er.badge ? esc(er.badge) : "Sin datos";
      var reproKpiClase = er.color === "verde" ? "ok" : (er.color === "rojo" || er.color === "ambar" ? "alerta" : "");

      var daOgestVal = "—";
      var daOgestLabel = "Días Abiertos";
      if (er.codigo === "PREÑADA" && er.dias_gestacion != null) {
        daOgestVal = er.dias_gestacion + " d";
        daOgestLabel = "Gestación";
      } else if (er.dias_abiertos != null) {
        daOgestVal = er.dias_abiertos + " d";
        daOgestLabel = "Días Abiertos";
      }

      var lacKpiVal = "—";
      if (ef.codigo === "VACA_ORDENO") {
        lacKpiVal = (f.lactancia && f.lactancia.del_dias != null) ? (f.lactancia.del_dias + " DEL") : "En ordeño";
      } else if (ef.codigo === "VACA_SECA") {
        lacKpiVal = "Seca";
      } else {
        lacKpiVal = esc(ef.badge);
      }

      h += "<div class='kpis' style='margin-bottom:14px;'>"
        + kpiIr(kpi(reproKpiVal, "Estado Repro", reproKpiClase), { tab: "repro" })
        + kpiIr(kpi(daOgestVal, daOgestLabel, (daOgestLabel === "Días Abiertos" && er.dias_abiertos > 90) ? "alerta" : ""), { tab: "repro" })
        + kpiIr(kpi(lacKpiVal, "Lactancia"), { tab: "leche" })
        + kpiIr(kpi(potreroKpiVal, potreroKpiLabel), { sec: "Últimos movimientos de potrero" })
        + kpiIr(kpi(f.en_retiro ? "EN RETIRO" : ultPesoTxt, f.en_retiro ? "Inocuidad" : "Último Pesaje", f.en_retiro ? "alerta" : ""), { tab: "pesos" })
        + "</div>";
    } else {
      var rolKpi = esc(ef.badge || f.categoria_sg || "Activo");
      h += "<div class='kpis' style='margin-bottom:14px;'>"
        + kpiIr(kpi(rolKpi, "Categoría / Estado"), { tab: "genealogia" })
        + kpiIr(kpi(potreroKpiVal, potreroKpiLabel), { sec: "Últimos movimientos de potrero" })
        + kpi(f.edad_str ? esc(f.edad_str) : (f.edad_dias != null ? f.edad_dias + " d" : "—"), "Edad")
        + kpiIr(kpi(ultPesoTxt, "Último Pesaje"), { tab: "pesos" })
        + kpiIr(kpi(f.en_retiro ? "EN RETIRO" : "APTO", "Inocuidad Sanitaria", f.en_retiro ? "alerta" : "ok"), { tab: "sanidad" })
        + "</div>";
    }

    var avisosDatos = (f.aviso_datos ? [f.aviso_datos] : []).concat(f.avisos_datos || []);
    if (avisosDatos.length) {
      h += "<div class='card' style='border-left:4px solid var(--color-ambar-txt, #D97706); padding:12px 14px;'>"
        + "<b>⚠️ " + (avisosDatos.length > 1 ? avisosDatos.length + " datos a revisar" : "Dato a revisar") + "</b>"
        + avisosDatos.map(function (t) { return "<p style='margin:6px 0 0; font-size:13px;'>" + esc(t) + "</p>"; }).join("")
        + "</div>";
    }
    if (ef.codigo === "TORO" && f.toro_servicio) {
      h += renderToroServicio(f.toro_servicio);
    } else {
    // 3. Tarjeta Destacada: Estado Fisiológico & Reproductivo (Prioridad #1 en Ficha)
    var fisioIcon = ef.icono === "milk" ? icon("milk", 16)
                  : ef.icono === "calf" ? icon("calf", 16)
                  : ef.icono === "grass" ? icon("grass", 16)
                  : icon("cow", 16);
    var reproIcon = er.codigo === "PREÑADA" ? icon("sperm", 16)
                  : er.codigo === "SERVIDA_SIN_PALPAR" ? icon("hourglass", 16)
                  : er.codigo === "TORO_REPRODUCTOR" ? icon("crown", 16)
                  : (er.alerta ? icon("alert", 16) : icon("circleEmpty", 16));

    var bordeColor = er.color === "verde" ? "var(--color-verde-txt)"
                   : er.color === "rojo" ? "var(--color-rojo-txt)"
                   : er.color === "ambar" ? "var(--color-ambar-txt)"
                   : "var(--verde-marca)";

    var fisioBadgeHtml = "<span class='chip " + (ef.color || "gris") + "' style='font-weight:700; display:inline-flex; align-items:center; gap:4px;'>" + fisioIcon + "<span>" + esc(ef.badge) + "</span></span>";
    var reproBadgeHtml = er.badge ? ("<span class='chip " + (er.color || "gris") + "' style='font-weight:700; display:inline-flex; align-items:center; gap:4px;'>" + reproIcon + "<span>" + esc(er.badge) + "</span></span>") : "";

    h += "<div class='card card-estado-zootecnico' style='padding:16px; margin-bottom:16px; border-left:5px solid " + bordeColor + ";'>";
    h += "<div style='display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>";
    h += "<h4 style='margin:0; border:none; padding:0; font-size:15px; display:flex; align-items:center; gap:8px; color:var(--texto);'>" + icon("heartPulse", 18) + "<span>Estado Fisiológico & Reproductivo</span></h4>";
    h += "<div style='display:flex; gap:6px; flex-wrap:wrap;'>" + fisioBadgeHtml + reproBadgeHtml + "</div>";
    h += "</div>";

    h += "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:12px;'>";

    // Columna 1: Estado Fisiológico / Producción
    h += "<div style='background:var(--fondo); border:1px solid var(--borde); border-radius:8px; padding:12px;'>";
    h += "<div style='font-size:11px; text-transform:uppercase; font-family:var(--font-mono); letter-spacing:0.05em; color:var(--texto-suave); margin-bottom:4px;'>Estado Fisiológico / Producción</div>";
    h += "<div style='font-size:15px; font-weight:700; color:var(--texto); margin-bottom:4px; display:flex; align-items:center; gap:6px;'>" + fisioIcon + "<span>" + esc(ef.titulo) + "</span></div>";
    h += "<div style='font-size:12.5px; color:var(--texto-suave); line-height:1.4;'>" + esc(ef.detalle || "Sin observaciones fisiológicas") + "</div>";
    if (f.lactancia && f.lactancia.fecha_parto) {
      h += "<div style='margin-top:8px; padding-top:6px; border-top:1px solid var(--borde); font-size:12px; display:flex; flex-wrap:gap; gap:8px;'>";
      h += "<span>Último parto: <b>" + esc(fechaCorta(f.lactancia.fecha_parto)) + "</b></span>";
      if (f.lactancia.del_dias != null) {
        h += "<span>· <b>" + f.lactancia.del_dias + "</b> DEL</span>";
      }
      if (f.lactancia.fecha_secado) {
        h += "<span>· Secada: <b>" + esc(fechaCorta(f.lactancia.fecha_secado)) + "</b></span>";
      }
      h += "</div>";
    }
    h += "</div>";

    // Columna 2: Estado Reproductivo (Ciclo Actual)
    h += "<div style='background:var(--fondo); border:1px solid var(--borde); border-radius:8px; padding:12px;'>";
    h += "<div style='font-size:11px; text-transform:uppercase; font-family:var(--font-mono); letter-spacing:0.05em; color:var(--texto-suave); margin-bottom:4px;'>Estado Reproductivo (Ciclo Actual)</div>";
    h += "<div style='font-size:15px; font-weight:700; color:var(--texto); margin-bottom:4px; display:flex; align-items:center; gap:6px;'>" + reproIcon + "<span>" + esc(er.titulo) + "</span></div>";
    h += "<div style='font-size:12.5px; color:var(--texto-suave); line-height:1.4;'>" + esc(er.detalle || "Sin registros reproductivos vigentes") + "</div>";

    if (er.dias_abiertos != null && er.codigo !== "PREÑADA") {
      var da = er.dias_abiertos;
      var semClase = da <= 90 ? "verde" : (da <= 150 ? "ambar" : "rojo");
      var semTxt = da <= 90 ? "Rango óptimo / Período voluntario de espera" : (da <= 150 ? "Alerta: programar servicio o IA" : "Crítico: días abiertos excesivos");
      h += "<div style='margin-top:10px; padding:8px 10px; border-radius:6px; background:var(--color-" + semClase + "-bg); color:var(--color-" + semClase + "-txt); font-size:12px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;'>";
      h += "<div>" + icon("hourglass", 14) + "<b>" + da + " días abiertos</b> · " + semTxt + "</div>";
      h += "</div>";
    }

    if (er.codigo === "PREÑADA" && er.dias_gestacion != null) {
      var dg = Math.min(285, Math.max(0, er.dias_gestacion));
      var pct = Math.round((dg / 285) * 100);
      var mesGest = (dg / 30.4).toFixed(1);
      h += "<div style='margin-top:10px;'>";
      h += "<div style='display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;'>";
      h += "<span>" + icon("calendar", 13) + "<b>" + dg + " días gestación</b> (~" + mesGest + " meses)</span>";
      h += "<span>FEP: <b>" + esc(fechaCorta(er.fep) || "S/D") + "</b></span>";
      h += "</div>";
      h += "<div style='height:8px; border-radius:4px; background:var(--borde); overflow:hidden;'>";
      h += "<div style='height:100%; width:" + pct + "%; background:var(--color-verde-txt); border-radius:4px;'></div>";
      h += "</div>";
      h += "</div>";
    }

    h += "</div>"; // fin columna 2
    h += "</div>"; // fin grid

    if (er.alerta) {
      h += "<div style='margin-top:12px; padding:10px 12px; border-radius:6px; background:var(--color-ambar-bg); color:var(--color-ambar-txt); border:1px solid var(--color-ambar-txt); font-size:12.5px; font-weight:600; display:flex; align-items:center; gap:8px;'>";
      h += icon("alert", 16) + "<span>" + esc(er.alerta) + "</span>";
      h += "</div>";
    }

    h += "</div>"; // fin tarjeta estado zootecnico
    }

    // 3. Tarjeta de Identificación & Genealogía (el pedigree completo vive en
    // la pestaña "Genealogía (3G)" -- sin botones duplicados hacia lo mismo)
    h += "<div class='card' style='padding:14px; margin-bottom:14px;'>"
      + "<h4 style='margin:0;'>" + icon("dna") + "Identificación & Genealogía</h4>"
      + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:13px; margin-top:10px;'>"
      + "<div><span style='color:var(--texto-suave);'>Arete / Tag:</span> <b>" + esc(f.tag) + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Nombre:</span> <b>" + esc(f.nombre || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Hierro / Marca:</span> <b>" + (f.hierro ? ("<span style='color:var(--verde-marca);'>" + icon("flame", 13) + esc(f.hierro) + "</span>") : "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Sexo:</span> <b>" + esc(f.sexo || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Raza:</span> <b>" + esc(f.raza || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Color / Pelo:</span> <b>" + esc(f.color || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Categoría:</span> <b>" + esc(f.categoria_sg || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Fecha Nacimiento:</span> <b>" + esc(fechaCorta(f.fecha_nacimiento) || "S/D") + "</b></div>"
      + "<div><span style='color:var(--texto-suave);'>Peso al Nacer:</span> <b>" + (f.peso_nacimiento ? f.peso_nacimiento + " kg" : "S/D") + "</b></div>";

    // Madre con enlace interactivo si existe
    var madreHtml = "S/D";
    if (f.madre && f.madre.tag) {
      madreHtml = "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(f.madre.tag) + "\" title='Ver ficha de la madre'><b>" + esc(f.madre.tag) + "</b> (" + esc(f.madre.nombre || f.madre.raza || "Madre") + ")</a>";
    }
    h += "<div><span style='color:var(--texto-suave);'>Madre:</span> " + madreHtml + "</div>";

    // Padre con enlace si existe
    var padreHtml = "S/D";
    if (f.padre && f.padre.tag) {
      padreHtml = "<a href='#' class='ficha-link' data-ir-ficha=\"" + esc(f.padre.tag) + "\" title='Ver ficha del padre'><b>" + esc(f.padre.tag) + "</b> (" + esc(f.padre.nombre || f.padre.raza || "Padre") + ")</a>";
    }
    h += "<div><span style='color:var(--texto-suave);'>Padre / Toro:</span> " + padreHtml + "</div>";

    // Abuelos Paternos & Maternos
    var g = f.genealogia_3g || {};
    var abPatTxt = (f.abuelo_pat && f.abuelo_pat.tag ? f.abuelo_pat.tag : (g.abuelo_pat && g.abuelo_pat.tag ? g.abuelo_pat.tag : "S/D"))
      + " / " + (f.abuela_pat && f.abuela_pat.tag ? f.abuela_pat.tag : (g.abuela_pat && g.abuela_pat.tag ? g.abuela_pat.tag : "S/D"));
    var abMatTxt = (f.abuelo_mat && f.abuelo_mat.tag ? f.abuelo_mat.tag : (g.abuelo_mat && g.abuelo_mat.tag ? g.abuelo_mat.tag : "S/D"))
      + " / " + (f.abuela_mat && f.abuela_mat.tag ? f.abuela_mat.tag : (g.abuela_mat && g.abuela_mat.tag ? g.abuela_mat.tag : "S/D"));

    h += "<div><span style='color:var(--texto-suave);'>Abuelos Pat.:</span> <b>" + esc(abPatTxt) + "</b></div>";
    h += "<div><span style='color:var(--texto-suave);'>Abuelos Mat.:</span> <b>" + esc(abMatTxt) + "</b></div>";

    h += "</div>";

    // Descendencia / Crías registradas directamente en la tarjeta de Identificación
    var criasGen = (f.crias && f.crias.length) ? f.crias : ((g.crias && g.crias.length) ? g.crias : (f.partos || []));
    if (criasGen.length) {
      h += "<div style='margin-top:12px; padding-top:10px; border-top:1px solid var(--borde);'>"
        + "<div style='font-size:12.5px; font-weight:600; margin-bottom:6px; color:var(--texto); display:flex; align-items:center; gap:6px;'>"
        + icon("cowCalf", 16) + "Descendencia / Crías Registradas (" + criasGen.length + "):</div>"
        + "<div style='display:flex; flex-wrap:wrap; gap:6px;'>";
      criasGen.forEach(function (c) {
        var cTag = c.cria_tag || c.tag || "Sin arete";
        var cSx = c.sexo_cria || c.sexo || "";
        var cFec = fechaCorta(c.fecha_parto || c.fecha || c.fecha_nacimiento);
        var chipTxt = "<b>" + esc(cTag) + "</b>" + (cSx ? " (" + esc(cSx) + ")" : "") + (cFec ? " [" + esc(cFec) + "]" : "");
        if (cTag !== "Sin arete") {
          h += "<a href='#' class='ficha-link chip verde' data-ir-ficha=\"" + esc(cTag) + "\" style='text-decoration:none; font-size:12px; padding:3px 8px; font-weight:bold; display:inline-flex; align-items:center; gap:5px;'>" + icon("calf", 13) + "<span>" + chipTxt + "</span></a>";
        } else {
          h += "<span class='chip gris' style='font-size:12px; padding:3px 8px; display:inline-flex; align-items:center; gap:5px;'>" + icon("calf", 13) + "<span>" + chipTxt + "</span></span>";
        }
      });
      h += "</div></div>";
    }

    // 3.1 Bloque visual de Composición Genética Multi-Raza
    var compRacial = (f.composicion_racial && f.composicion_racial.length) ? f.composicion_racial : [];
    var rolActual = window.__usuarioActual && window.__usuarioActual.rol;
    var esAdminOwer = (rolActual === "OWNER" || rolActual === "ADMIN");

    h += "<div style='margin-top:14px; padding-top:12px; border-top:1px solid var(--borde);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;'>"
      + "<div style='font-size:13px; font-weight:700; display:flex; align-items:center; gap:6px; color:var(--texto);'>"
      + icon("dna", 16) + "Composición Genética Multi-Raza</div>"
      + (esAdminOwer ? ("<button type='button' id='btn-editar-composicion-raza' data-tag='" + esc(f.tag) + "' class='chip ambar' style='cursor:pointer; font-weight:600; padding:4px 10px; font-size:12px; display:inline-flex; align-items:center; gap:5px; border:none;'>" + icon("pencil", 12) + "Editar Razas</button>") : "")
      + "</div>";

    if (compRacial.length > 0) {
      // Barra apilada multicolor
      h += "<div style='display:flex; width:100%; height:18px; border-radius:9px; overflow:hidden; background:var(--borde); margin-bottom:10px; box-shadow:inset 0 1px 2px rgba(0,0,0,0.1);'>";
      compRacial.forEach(function (cr, idx) {
        var col = colorDeRaza(cr.raza, idx);
        var ancho = Math.max(cr.porcentaje, 1);
        var fTitle = (cr.fraccion && cr.fraccion.indexOf("%") === -1) ? (" · " + cr.fraccion) : "";
        h += "<div style='width:" + ancho + "%; background:" + col + "; height:100%;' title='" + esc(cr.raza) + ": " + cr.porcentaje + "%" + esc(fTitle) + "'></div>";
      });
      h += "</div>";

      // Chips con fracciones y porcentajes (evitando redundancias como 30% (30%))
      h += "<div style='display:flex; flex-wrap:wrap; gap:6px;'>";
      compRacial.forEach(function (cr, idx) {
        var col = colorDeRaza(cr.raza, idx);
        var fLabel = cr.fraccion || porcentajeAFraccionGanadera(cr.porcentaje);
        var detallePct = "";
        if (fLabel && fLabel.indexOf("%") === -1 && fLabel !== "S/D") {
          detallePct = "<span style='color:var(--verde-marca); font-weight:700;'>" + esc(fLabel) + "</span> (" + esc(cr.porcentaje) + "%)";
        } else {
          detallePct = "<span style='color:var(--verde-marca); font-weight:700;'>" + esc(cr.porcentaje) + "%</span>";
        }
        h += "<span class='chip' style='background:rgba(0,0,0,0.04); border:1px solid " + col + "; color:var(--texto); font-size:12px; padding:3px 8px; font-weight:600; display:inline-flex; align-items:center; gap:5px;'>"
          + "<span style='display:inline-block; width:8px; height:8px; border-radius:50%; background:" + col + ";'></span>"
          + "<b>" + esc(cr.raza) + "</b> " + detallePct
          + "</span>";
      });
      h += "</div>";
    } else {
      var rzTxt = f.raza || "Sin clasificar";
      h += "<div style='display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; font-size:12.5px; color:var(--texto-suave);'>"
        + "<span>Raza registrada: <b>" + esc(rzTxt) + "</b> (sin desglose de porcentajes).</span>"
        + (esAdminOwer ? ("<button type='button' class='chip verde' data-accion='editar-composicion-raza' data-tag='" + esc(f.tag) + "' style='cursor:pointer; font-weight:600; padding:3px 8px; font-size:11.5px; display:inline-flex; align-items:center; gap:4px; border:none;'>" + icon("plus", 11) + "Definir Multi-Raza</button>") : "")
        + "</div>";
    }
    h += "</div>";

    h += "</div>";

    // 3.2 Tarjeta de Costeo Zootécnico & Valoración Comercial en Pie
    var cz = f.costeo_zootecnico;
    if (cz && cz.disponible) {
      var valPieHtml = (cz.valor_comercial_estimado != null)
        ? ("<span style='font-size:20px; font-weight:800; color:var(--verde-marca);'>" + fmtMoneda(cz.valor_comercial_estimado) + "</span>")
        : "<span class='meta' style='font-size:13px;'>Requiere pesaje reciente</span>";
      var subValHtml = (cz.peso_kg != null)
        ? (cz.peso_kg + " kg @ " + fmtMoneda(cz.precio_kg_mercado) + "/kg")
        : ("Precio ref: " + fmtMoneda(cz.precio_kg_mercado) + "/kg");

      var margenHtml = "";
      if (cz.margen_bruto_estimado != null) {
        var mColor = cz.margen_bruto_estimado >= 0 ? "var(--verde-marca)" : "var(--color-rojo-txt)";
        var mPctStr = cz.margen_bruto_pct != null ? (" (" + cz.margen_bruto_pct + "%)") : "";
        margenHtml = "<span style='font-size:18px; font-weight:800; color:" + mColor + ";'>" + fmtMoneda(cz.margen_bruto_estimado) + "</span>"
          + "<span class='chip verde' style='font-size:11px; padding:2px 6px; font-weight:700; margin-left:6px;'>" + mPctStr + "</span>";
      } else {
        margenHtml = "<span class='meta' style='font-size:13px;'>Calculable tras pesaje</span>";
      }

      h += "<div class='card card-costeo-animal' style='padding:16px; margin-top:14px; margin-bottom:14px; border-left:5px solid #10b981; background:var(--superficie); border-radius:8px;'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;'>"
        + "<h4 style='margin:0; font-size:14px; display:flex; align-items:center; gap:8px; color:var(--texto);'>"
        + icon("receipt", 16) + "<span>Valoración Comercial en Pie & Costeo Zootécnico</span></h4>"
        + "<span class='chip' style='background:rgba(16,185,129,0.1); color:var(--verde-marca); border:1px solid rgba(16,185,129,0.3); font-weight:700; font-size:11px;'>"
        + icon("flame", 12) + esc(cz.fuente_mercado) + "</span>"
        + "</div>"
        + "<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin-bottom:10px;'>"
        + "<div style='background:var(--fondo); border:1px solid var(--borde); border-radius:8px; padding:12px;'>"
        + "<div style='font-size:11px; text-transform:uppercase; font-family:var(--font-mono); letter-spacing:0.04em; color:var(--texto-suave); margin-bottom:4px;'>Valor Estimado en Pie</div>"
        + "<div style='margin-bottom:4px;'>" + valPieHtml + "</div>"
        + "<div style='font-size:12px; color:var(--texto-suave);'>" + esc(subValHtml) + "</div>"
        + "</div>"
        + "<div style='background:var(--fondo); border:1px solid var(--borde); border-radius:8px; padding:12px;'>"
        + "<div style='font-size:11px; text-transform:uppercase; font-family:var(--font-mono); letter-spacing:0.04em; color:var(--texto-suave); margin-bottom:4px;'>Costos Directos Acumulados</div>"
        + "<div style='font-size:18px; font-weight:800; color:var(--texto); margin-bottom:4px;'>" + fmtMoneda(cz.costo_total_acumulado) + "</div>"
        + "<div style='display:flex; flex-wrap:wrap; gap:4px; font-size:11px;'>"
        + (cz.costo_inseminacion > 0 ? ("<span class='chip gris' title='Pajuelas e IATF'>IA: " + fmtMoneda(cz.costo_inseminacion) + "</span>") : "")
        + (cz.costo_tratamientos > 0 ? ("<span class='chip gris' title='Fármacos y tratamientos'>Sanidad: " + fmtMoneda(cz.costo_tratamientos) + "</span>") : "")
        + (cz.costo_sostenimiento > 0 ? ("<span class='chip gris' title='Pasturas y sales mineralizadas'>Manejo: " + fmtMoneda(cz.costo_sostenimiento) + "</span>") : "")
        + "</div>"
        + "</div>"
        + "<div style='background:var(--fondo); border:1px solid var(--borde); border-radius:8px; padding:12px;'>"
        + "<div style='font-size:11px; text-transform:uppercase; font-family:var(--font-mono); letter-spacing:0.04em; color:var(--texto-suave); margin-bottom:4px;'>Margen Bruto Estimado</div>"
        + "<div style='display:flex; align-items:center; gap:6px; margin-bottom:4px; flex-wrap:wrap;'>" + margenHtml + "</div>"
        + "<div style='font-size:12px; color:var(--texto-suave);'>Margen sobre costos directos</div>"
        + "</div>"
        + "</div>"
        + "<div style='font-size:11.5px; color:var(--texto-suave); display:flex; align-items:center; gap:5px;'>"
        + icon("info", 13) + "Cotización de subastas de la región (actualizada a " + esc(fechaCorta(cz.fecha_mercado)) + ")."
        + "</div>"
        + "</div>";
    }

    // 4. Traslados de potrero recientes
    if (f.traslados && f.traslados.length) {
      h += "<h4>" + icon("truck") + "Últimos movimientos de potrero</h4>"
        + tabla(f.traslados, [
          ["fecha", "Fecha", "text", function (v) { return esc(fechaCorta(v)); }],
          ["origen", "Origen", "text", function (v) { return esc(v || "—"); }],
          ["destino", "Destino", "text", function (v) { return "<b>" + esc(v || "—") + "</b>"; }],
          ["motivo", "Motivo", "text", function (v) { return esc(v || "Rotación"); }]
        ], "Sin traslados registrados.");
    }

    // 6. Historial de Bajas, Ventas y Movimientos
    var bajasList = (f.historial_bajas && f.historial_bajas.length) ? f.historial_bajas : (f.movimientos || []);
    if (bajasList && bajasList.length) {
      h += "<h4 style='margin-top:16px;'>" + icon("receipt") + "Historial de Bajas, Ventas y Movimientos</h4>"
        + tabla(bajasList, [
          ["fecha", "Fecha", "text", function (v) { return "<b>" + esc(fechaCorta(v)) + "</b>"; }],
          ["tipo", "Tipo", "text", function (v, row) {
            var t = String(v || row.tipo_movimiento || "MOVIMIENTO").toUpperCase();
            if (t === "VENTA") return "<span class='chip ambar' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("receipt", 12) + "<span>Venta</span></span>";
            if (t === "MUERTE") return "<span class='chip rojo' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("cowSkull", 12) + "<span>Muerte</span></span>";
            if (t === "COMPRA") return "<span class='chip verde' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("plus", 12) + "<span>Compra</span></span>";
            if (t === "TRASLADO") return "<span class='chip gris' style='display:inline-flex; align-items:center; gap:4px;'>" + icon("truck", 12) + "<span>Traslado</span></span>";
            return "<span class='chip gris'>" + esc(t) + "</span>";
          }],
          ["destino_causa", "Destino / Causa / Detalle", "text", function (v, row) {
            var d = v || row.procedencia_destino || row.causa_presunta || "—";
            return esc(d);
          }],
          ["precio", "Precio / Valor", "text", function (v) {
            return (v != null && Number(v) > 0) ? ("<b>" + fmtMoneda(v) + "</b>") : "—";
          }],
          ["notas", "Observaciones", "text", function (v) { return esc(v || "—"); }]
        ], "Sin movimientos ni bajas registradas.");
    }

    // 6. Tarjeta de Código QR & Ficha Oficial PDF
    h += "<div class='card' style='padding:16px; margin-top:14px; background:var(--superficie); border:1px solid var(--borde); border-radius:8px;'>"
      + "<div style='display:flex; gap:16px; align-items:center; flex-wrap:wrap;'>"
      + "<div style='flex:1; min-width:220px;'>"
      + "<h4 style='margin-top:0;'>" + icon("camera") + "Código QR & Ficha Técnica del Animal</h4>"
      + "<p style='font-size:12.5px; color:var(--texto-suave); margin:6px 0 12px 0; line-height:1.4;'>"
      + "El código QR contiene el enlace web directo a la PWA. Al escanearlo con la cámara de cualquier teléfono en el campo o manga, abre de inmediato esta ficha viva e interactiva. "
      + "Para llevar el registro impreso a la manga o carpeta de potrero, descargue la <b>Ficha Técnica A4 Oficial</b> con semáforos, genealogía y pesajes."
      + "</p>"
      + "<div style='display:flex; gap:8px; flex-wrap:wrap; align-items:center;'>"
      + "<a class='btn-guardar-manga' style='display:inline-flex; align-items:center; text-decoration:none; font-size:13px; padding:8px 14px;' href='/api/ficha/" + encodeURIComponent(f.tag) + "/qr.pdf' target='_blank' download>"
      + icon("filePdf", 16) + "Descargar Ficha Técnica PDF</a>"
      + "<span class='meta' style='font-size:12px;'>Payload: <code>" + esc(f.qr_payload || ("JA://animal/" + f.tag)) + "</code></span>"
      + "</div></div>"
      + "</div></div>";

    // 7. Fotos del animal
    var fotosHtml = "";
    if (f.fotos && f.fotos.length) {
      fotosHtml = "<div class='fotos-wrap' style='margin-top:8px; display:flex; gap:12px; flex-wrap:wrap;'>" + f.fotos.filter(function (x) { return x.url; })
        .map(function (x, idx) {
          return "<div class='foto-card' title='Toca para agrandar imagen'>"
            + "<img class='zoomable-img' src='" + esc(x.url) + "' alt='Foto #" + (idx + 1) + " · " + esc(f.tag) + "' loading='lazy' style='max-height:175px; width:auto; border-radius:8px; object-fit:cover; display:block;' data-onerror-hide='parent'>"
            + "<div class='zoom-hint'>" + icon("search", 12) + "Agrandar</div>"
            + "</div>";
        }).join("") + "</div>";
    } else {
      fotosHtml = vacio("Sin fotos para este animal.");
    }
    h += "<h4 style='margin-top:16px;'>" + icon("camera") + "Registro Fotográfico (Toca una foto para agrandarla)</h4>" + fotosHtml;

    return h;
  }
  function bindTabs(ficha) {
    var nav = document.getElementById("ficha-tabs");
    if (!nav) return;
    // Closure con la ficha de ESTE render: evita condiciones de carrera si se
    // abre otra ficha mientras se navega por las pestañas de la anterior.
    qa(".mini button", nav).forEach(function (b) {
      b.addEventListener("click", function () {
        qa(".mini button", nav).forEach(function (x) { x.classList.remove("act"); x.setAttribute("aria-selected", "false"); });
        b.classList.add("act");
        b.setAttribute("aria-selected", "true");
        var panel = document.getElementById("ficha-panel");
        if (panel) panel.innerHTML = fichaTab(b.getAttribute("data-tab"), ficha || window.__ultimaFicha || {});
      });
    });

    var panelEl = document.getElementById("ficha-panel");
    if (panelEl && !panelEl.__palpBound) {
      panelEl.__palpBound = true;
      panelEl.addEventListener("click", function (e) {
        var btnPalp = e.target.closest(".btn-palpar-ficha-directo");
        if (btnPalp) {
          var t = btnPalp.getAttribute("data-tag");
          if (t) {
            try { localStorage.setItem("bitacora_ultimo_tag", t); } catch (eTag) {}
            window.__capTagPendiente = t;
          }
          _tipoCapturaActual = "palpacion";
          irAVista("captura");
          cargar(true);
          try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eScroll) { window.scrollTo(0, 0); }
        }
      });
    }

    // BLOQUE 4: el FAB lleva a Captura prellenando el tag de esta ficha.
    var btnFab = document.getElementById("btn-ficha-registrar");
    if (btnFab) {
      btnFab.addEventListener("click", function () {
        var tagFab = (ficha && ficha.tag) || (window.__ultimaFicha && window.__ultimaFicha.tag) || "";
        tagFab = String(tagFab || "").trim();
        if (tagFab) {
          try { localStorage.setItem("bitacora_ultimo_tag", tagFab); } catch (eFabTag) { /* noop */ }
          window.__capTagPendiente = tagFab;
        }
        irAVista("captura");
        cargar(true);
        try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (eFabScroll) { window.scrollTo(0, 0); }
      });
    }
  }

