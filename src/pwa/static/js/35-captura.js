  /* ---------- Captura Rápida de Campo (Offline Real) ---------- */
  var _tipoCapturaActual = "parto";
  function renderCaptura() {
    var tipos = [
      { id: "parto", nom: "Parto", ico: "cowCalf" },
      { id: "pesaje", nom: "Pesaje", ico: "scale" },
      { id: "palpacion", nom: "Tacto / Palpación", ico: "stethoscope" },
      { id: "pajuela", nom: "Stock Pajillas", ico: "sperm" },
      { id: "nitrogeno", nom: "Recarga Nitrógeno", ico: "snowflake" },
      { id: "tratamiento", nom: "Tratamiento", ico: "syringe" },
      { id: "traslado", nom: "Traslado", ico: "truck" },
      { id: "destete", nom: "Destete", ico: "destete" },
      { id: "secado", nom: "Secado", ico: "milk" },
      { id: "manejo", nom: "Manejo / Vacuna", ico: "syringe" },
      { id: "celo", nom: "Celo", ico: "flame" },
      { id: "servicio", nom: "Servicio / IA", ico: "sperm" },
      { id: "leche", nom: "Leche", ico: "milk" },
      { id: "muerte", nom: "Muerte / Descarte", ico: "cowSkull" },
      { id: "gasto", nom: "Ingreso / Gasto", ico: "banknote" },
      { id: "tarea", nom: "Asignar Tarea", ico: "calendar" }
    ];

    var h = "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:10px;'>"
      + "<h3 style='margin:0;'>" + icon("clipboard") + "Captura Rápida de Campo (Online / Offline)</h3>"
      + "<button type='button' id='btn-cap-ir-manga' class='btn-guardar-manga' style='padding:8px 14px; font-size:13px; font-weight:600; width:auto; display:inline-flex; align-items:center; gap:6px; cursor:pointer;'>"
      + icon("manga", 16) + "Manga Corral (Trabajo en Lote) →"
      + "</button>"
      + "</div>";
    h += "<p class='aviso' style='margin:4px 0 10px; font-size:12.5px;'>Para procesar o pesar varios animales seguidos en lote, usa <b>Manga Corral</b>.</p>";

    // BLOQUE 4: stepper de captura en 3 pasos (1=tipo, 2=datos, 3=preview).
    // El form envuelve los 3 pasos; el submit real solo vive en el paso 3.
    h += "<div class='cap-pasos' aria-hidden='true'>"
      + "<span class='chip verde' id='cap-ind-1'>1 · Tipo</span>"
      + "<span class='chip gris' id='cap-ind-2'>2 · Datos</span>"
      + "<span class='chip gris' id='cap-ind-3'>3 · Guardar</span>"
      + "</div>";

    h += "<div class='card' style='padding:16px;'>"
      + "<form id='form-captura' style='display:flex; flex-direction:column; gap:10px;'>"
      + "<div class='cap-paso cap-paso-1 act'>"
      + "<div class='cap-paso-num'>1/3: ¿Qué evento desea registrar?</div>"
      + "<div class='cap-tipos-grid'>";
    tipos.forEach(function (t) {
      var act = t.id === _tipoCapturaActual ? "act" : "";
      h += "<button type='button' class='btn-punto " + act + "' data-cap-tipo='" + t.id + "'>" + icon(t.ico, 16) + "<span>" + t.nom + "</span></button>";
    });
    h += "</div>"
      + "<button type='button' id='btn-cap-sig1' class='btn-guardar-manga'>Siguiente →</button>"
      + "</div>"
      + "<div class='cap-paso cap-paso-2'>"
      + "<div class='cap-paso-num'>2/3: Datos del evento</div>"
      + "<div id='cap-tag-chip' style='margin-bottom:8px;'></div>"
      + "<div id='captura-campos'></div>"
      + "<div style='display:flex; gap:8px; margin-top:12px;'>"
      + "<button type='button' id='btn-cap-atras2' class='tema-btn' style='flex:1; padding:12px; cursor:pointer;'>← Atrás</button>"
      + "<button type='button' id='btn-cap-sig2' class='btn-guardar-manga' style='flex:2;'>Siguiente →</button>"
      + "</div>"
      + "</div>"
      + "<div class='cap-paso cap-paso-3'>"
      + "<div class='cap-paso-num'>3/3: Revise y guarde</div>"
      + "<div id='cap-preview-resumen' class='aviso' style='font-size:13px; line-height:1.6;'></div>"
      + "<div style='margin-top:12px;'><button type='button' id='btn-cap-atras3' class='tema-btn' style='width:100%; padding:12px; cursor:pointer;'>← Atrás</button></div>"
      + "<div class='cap-guardar-sticky'><button type='submit' id='btn-guardar-captura' class='btn-guardar-manga'>" + icon("save", 15) + "Guardar Registro</button></div>"
      + "</div>"
      + "</form>"
      + "<div id='captura-feedback' role='status' aria-live='polite' style='margin-top:12px;'></div>"
      + "</div>";

    return h;
  }

  function camposHtmlCaptura(tipo) {
    var hoy = new Date().toISOString().slice(0, 10);
    var h = "<label>Fecha del evento: <input type='date' id='cap-fecha' value='" + hoy + "' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";

    if (tipo === "parto") {
      h += "<label>Tipo de evento: <select id='cap-tipo-evento' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='PARTO'>Parto sencillo (1 cría)</option><option value='GEMELAR'>Parto gemelar (2 crías)</option><option value='ABORTO'>Aborto</option><option value='REABSORCION'>Reabsorción embrionaria</option><option value='MOMIFICACION'>Momificación fetal</option><option value='MACERACION'>Maceración fetal</option><option value='MUERTE_FETAL'>Muerte fetal</option></select></label>"
        + "<label>Arete / Tag de la Madre (Vaca): <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required autocomplete='off' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div id='cap-parto-cria-wrap'>"
        + "<label id='cap-cria1-label'>Arete de la Cría (Nuevo): <input id='cap-cria-tag' placeholder='ej. 102 o NM_102' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div id='cap-cria-sugerido-hint' style='font-size:11.5px; color:var(--verde-marca); margin:-4px 0 8px 2px; cursor:pointer; font-weight:600;'></div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Sexo de la Cría: <select id='cap-sexo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='HEMBRA'>Hembra</option><option value='MACHO'>Macho</option></select></label></div>"
        + "<div style='flex:1;'><label>Estado Cría: <select id='cap-estado-cria' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='VIVO'>Vivo / Normal</option><option value='MUERTO'>Nacido Muerto</option></select></label></div>"
        + "</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Peso al nacer (kg): <input type='number' step='0.5' id='cap-peso-nacer' placeholder='ej. 32' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<div id='cap-distocia-wrap' style='margin-top:2px;'><label>¿Parto difícil / asistido (distocia)? <select id='cap-distocia' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='NO'>No, parto normal</option><option value='SI'>Sí, difícil o asistido</option></select></label></div>"
        + "<div style='margin-top:6px; margin-bottom:8px;'>"
        + "<label>Toro / Padre de la cría (opcional): <select id='cap-toro-padre' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value=''>-- Sin especificar (opcional) --</option></select></label>"
        + "<div id='cap-toro-sugerido-hint' style='font-size:12px; margin:4px 0 6px 2px; min-height:18px;'></div>"
        + "<div id='cap-toro-otro-wrap' style='display:none; margin-top:4px;'><input id='cap-toro-otro' placeholder='Escribir código de toro o pajilla...' list='dl-toros' autocomplete='off' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></div>"
        + "<div id='cap-cruce-cria-preview' style='display:none; margin:4px 0 8px; padding:6px 10px; background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.3); border-radius:6px; font-size:12px; color:var(--texto); line-height:1.4;'></div>"
        + "</div>"
        + "<div id='cap-gemelo2-wrap' style='display:none; padding:10px; border:1px dashed var(--borde-fuerte); border-radius:8px;'>"
        + "<p class='aviso' style='margin:2px 0 8px;'>Segunda cría (gemelo/a):</p>"
        + "<label>Arete de la Cría 2: <input id='cap-cria2-tag' placeholder='ej. 103' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap; margin-top:8px;'>"
        + "<div style='flex:1;'><label>Sexo Cría 2: <select id='cap-sexo2' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='HEMBRA'>Hembra</option><option value='MACHO'>Macho</option></select></label></div>"
        + "<div style='flex:1;'><label>Estado Cría 2: <select id='cap-estado-cria2' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='VIVO'>Vivo / Normal</option><option value='MUERTO'>Nacido Muerto</option></select></label></div>"
        + "</div>"
        + "<div style='margin-top:8px;'><label>Peso al nacer Cría 2 (kg): <input type='number' step='0.5' id='cap-peso-nacer2' placeholder='ej. 28' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Potrero de la Cría (opcional): <input id='cap-pot-cria' placeholder='ej. Levante' list='dl-potreros' autocomplete='off' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Potrero de la Madre (opcional): <input id='cap-pot-madre' placeholder='ej. Maternidad' list='dl-potreros' autocomplete='off' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "</div>"
        + "<p id='cap-perdida-aviso' class='aviso' style='display:none; margin:2px 0;'>Se registra como un evento reproductivo de la vaca (sin cría), separado de un Parto normal.</p>"
        + "<label>Observaciones / Notas: <input id='cap-notas' placeholder='Parto distócico, ternero vigoroso, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "destete") {
      h += "<label>Arete de la Vaca (Madre): <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div id='cap-destete-cria-info' style='font-size:12.5px; color:var(--texto-suave); margin:-4px 0 2px 2px; min-height:16px;'></div>"
        + "<label>Arete de la Cría a Destetar: <input id='cap-cria-tag' placeholder='se completa solo al escribir la vaca' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Peso al destete (kg): <input type='number' step='0.5' id='cap-peso' placeholder='ej. 120' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Potrero nuevo de la Cría: <input id='cap-pot-cria' placeholder='ej. Levante' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<p class='aviso' style='margin:2px 0;'>Datos de la madre en este mismo momento (opcional, solo informativo -- el destete NO seca a la vaca; si dejó de ordeñarse use el botón <b>Secado</b> aparte):</p>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Peso de la Madre (kg): <input type='number' step='0.5' id='cap-peso-madre' placeholder='ej. 410' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Cond. Corporal Madre (1-5): <select id='cap-cc-madre' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0'>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0</option></select></label></div>"
        + "</div>"
        + "<label>Potrero nuevo de la Madre (opcional): <input id='cap-pot-madre' placeholder='ej. Vacas Secas' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Observaciones / Motivo: <input id='cap-notas' placeholder='Destete normal, adelantado por sequía, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "manejo") {
      h += "<label>Arete / Tag: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Manejo: <select id='cap-tipo-manejo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
        + "<option value='TOPIZADO'>Topizado (descornado)</option><option value='CASTRACION'>Castración</option>"
        + "<option value='ENTERO'>Queda entero (reproductor)</option><option value='MARCACION'>Marcación / herrado</option>"
        + "<option value='VACUNA_AFTOSA'>Vacuna aftosa</option><option value='VACUNA_BRUCELOSIS'>Vacuna brucelosis</option>"
        + "<option value='VACUNA_OTRA'>Otra vacuna</option></select></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Producto (vacunas): <input id='cap-producto' placeholder='ej. Aftogan' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Lote: <input id='cap-lote-producto' placeholder='ej. L2345' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Notas (en marcación: el hierro): <input id='cap-notas' placeholder='ej. Hierro JA' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "secado") {
      h += "<label>Arete / Tag de la Vaca: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Cond. Corporal (1-5): <select id='cap-cc' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0'>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0</option></select></label></div>"
        + "<div style='flex:1;'><label>Potrero nuevo (opcional): <input id='cap-pot-secado' placeholder='ej. Vacas Secas' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Motivo: <select id='cap-motivo-secado' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='Fin de lactancia'>Fin de lactancia (programado)</option><option value='Baja producción'>Baja producción</option><option value='Mastitis'>Mastitis / problema de ubre</option><option value='Preparación para el parto'>Preparación para el próximo parto</option><option value='Otro'>Otro</option></select></label>"
        + "<label>Observaciones: <input id='cap-notas' placeholder='ej. Se secó sola, sin problema' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<p class='aviso' style='margin:2px 0;'>Evento independiente del destete de la cría: registra que esta vaca dejó de ordeñarse de verdad.</p>";
    } else if (tipo === "pesaje") {
      h += "<label>Arete / Tag del animal: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Peso (kg): <input type='number' step='0.5' id='cap-peso' placeholder='ej. 430' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Condición Corporal (1-5): <select id='cap-cc' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0'>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0</option></select></label>";
    } else if (tipo === "tratamiento") {
      h += "<label>Arete / Tag: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Producto / Fármaco: <input id='cap-producto' placeholder='ej. Oxitetraciclina 20%' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Principio activo (si figura en frasco): <input id='cap-principio' placeholder='ej. Oxitetraciclina' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Dosis: <input id='cap-dosis' placeholder='ej. 20 ml' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Vía: <select id='cap-via' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='IM'>IM (Intramuscular)</option><option value='SC'>SC (Subcutánea)</option><option value='IV'>IV</option><option value='Oral'>Oral</option><option value='Pour-on'>Pour-on</option></select></label></div>"
        + "</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Retiro Leche (días): <input type='number' id='cap-ret-leche' value='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Retiro Carne (días): <input type='number' id='cap-ret-carne' value='0' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Diagnóstico / Causa: <input id='cap-diag' placeholder='ej. Mastitis clínica cuarto anterior izquierdo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "traslado") {
      h += "<label style='display:flex; align-items:flex-start; gap:8px; background:var(--superficie); padding:10px; border-radius:8px; border:1px solid var(--borde-fuerte); font-weight:600; cursor:pointer;'>"
        + "<input type='checkbox' id='cap-trasl-masivo' style='width:auto; margin-top:3px;'>"
        + "<span>Mover TODOS los animales activos de este potrero<span style='display:block; font-weight:400; font-size:12px; color:var(--texto-suave); margin-top:2px;'>Sin escribir cada arete: elegí solo Potrero Origen y Potrero Destino.</span></span>"
        + "</label>"
        + "<div id='cap-trasl-tag-wrap'><label>Arete / Tag: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<label>Potrero Origen: <input id='cap-pot-orig' placeholder='ej. Guayabal' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Potrero Destino: <input id='cap-pot-dest' placeholder='ej. Morichal' list='dl-potreros' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Motivo de rotación: <input id='cap-motivo' placeholder='Rotación Voisin, cambio de pastura, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "celo") {
      h += "<label>Arete / Vaca: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Horario Celo: <select id='cap-am-pm' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='AM'>Mañana (AM) — Inseminar en la tarde</option><option value='PM'>Tarde (PM) — Inseminar en la mañana siguiente</option></select></label>"
        + "<label>Observaciones de Celo: <input id='cap-notas' placeholder='Acepta monta, moco cristalino, bramidos' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "servicio") {
      h += "<label>Arete / Vaca: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Tipo de Servicio: <select id='cap-tipo-serv' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='IA'>Inseminación Artificial (I.A.)</option><option value='MN'>Monta Natural</option><option value='IATF'>IATF Protocolo</option></select></label>"
        + "<label>Código Toro / Pajilla: <input id='cap-toro' placeholder='ej. GUZ-01' list='dl-toros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Inseminador / Técnico: <div style='display:flex; gap:6px; align-items:center;'><input id='cap-inseminador' placeholder='Nombre del técnico' list='dl-inseminadores' style='flex:1; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><button type='button' id='btn-nuevo-inseminador-cap' title='Registrar nuevo inseminador' style='padding:8px 10px; border-radius:6px; border:1px solid var(--borde-fuerte); background:var(--superficie); color:var(--texto); cursor:pointer;'>➕</button></div><datalist id='dl-inseminadores'></datalist></label>";
    } else if (tipo === "leche") {
      h += "<label>Litros del Día (Entregados al Tanque / Acopiador): <input type='number' step='0.5' id='cap-litros' placeholder='ej. 320' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<p class='aviso' style='margin:2px 0 6px 0; font-size:11.5px;'>💡 Si tienes la foto del recibo o planilla de quincena, sube la foto abajo y presiona <b>Leer Recibo con IA</b> para digitalizar y guardar cada día automáticamente.</p>"
        + "<label>Observaciones / Detalle: <input id='cap-notas' placeholder='ej. Ordeño del día, control tanque, etc.' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "muerte") {
      h += "<label>Arete / Tag: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Causa Presunta: <input id='cap-causa' placeholder='ej. Mordedura de serpiente, timpanismo, descarte vejez' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Observaciones: <input id='cap-notas' placeholder='Detalles o destino' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "gasto") {
      h += "<label>Categoría: <select id='cap-fin-categoria' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
        + "<optgroup label='💰 Ingresos'>"
        + "<option value='VENTA_LECHE'>Venta de leche</option>"
        + "<option value='OTRO_INGRESO'>Otro ingreso</option>"
        + "</optgroup>"
        + "<optgroup label='💸 Egresos'>"
        + "<option value='INSUMO' selected>Insumos (sal, alambre, herramienta, etc.)</option>"
        + "<option value='NOMINA'>Nómina / Jornales</option>"
        + "<option value='VETERINARIO'>Veterinario / Medicamentos</option>"
        + "<option value='INFRAESTRUCTURA'>Infraestructura / Mantenimiento</option>"
        + "<option value='COMBUSTIBLE'>Combustible</option>"
        + "<option value='OTRO_EGRESO'>Otro gasto</option>"
        + "</optgroup>"
        + "</select></label>"
        + "<label>Concepto: <input id='cap-fin-concepto' placeholder='ej. Sal mineralizada 40kg, Jornal Andrés' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Monto ($): <input type='number' step='1' min='0' id='cap-fin-monto' placeholder='ej. 180000' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div id='cap-fin-litros-wrap' style='display:none;'><label>Litros vendidos (solo venta de leche): <input type='number' step='0.5' id='cap-fin-litros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<label>Proveedor / Comprador / Trabajador (opcional): <input id='cap-fin-contraparte' placeholder='ej. Agropecuaria X, Andrés' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Arete / Animal relacionado (opcional): <input id='cap-tag' placeholder='ej. N069' list='dl-tags' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Potrero relacionado (opcional): <input id='cap-fin-potrero' placeholder='ej. Olegario' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Notas: <input id='cap-notas' placeholder='Detalles adicionales' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "palpacion") {
      h += "<label>Arete / Vaca: <input id='cap-tag' placeholder='ej. 47' list='dl-tags' required autocomplete='off' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Método de Diagnóstico: <select id='cap-palp-metodo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='TACTO'>Manual (Tacto rectal)</option><option value='ECOGRAFO'>Ecógrafo (Ultrasonido)</option></select></label></div>"
        + "<div style='flex:1;'><label>Resultado: <select id='cap-palp-resultado' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='PREÑADA' selected>Preñada (P)</option><option value='VACIA'>Vacía (V)</option><option value='DUDOSA'>Dudosa (D)</option></select></label></div>"
        + "</div>"
        + "<div id='cap-palp-prenada-box' style='padding:10px; border-radius:8px; background:rgba(46,125,50,0.06); border:1px solid rgba(46,125,50,0.3); margin:6px 0;'>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Días de Preñez / Gestación: <input type='number' min='1' max='300' id='cap-palp-dias' placeholder='ej. 45' value='45' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>FEP Calculada: <input type='date' id='cap-palp-fep' readonly style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); background:var(--fondo-card); font-weight:700;'></label></div>"
        + "</div>"
        + "<div style='margin-top:8px;'><label>Reproductor / Toro de la Preñez: <input id='cap-palp-toro' placeholder='ej. GUZ-01 o Nombre de Toro/Pajilla' list='dl-toros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Hallazgo Zootécnico / Ovario (opcional): <input id='cap-palp-hallazgo' placeholder='ej. CL derecho 22mm, Folículo preovulatorio, Quiste, Útero normal...' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Condición Corporal (1-5): <select id='cap-cc' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value=''>CC (Opcional)</option><option value='2.0'>2.0 (Flaca)</option><option value='2.5'>2.5</option><option value='3.0' selected>3.0 (Óptima)</option><option value='3.5'>3.5</option><option value='4.0'>4.0</option></select></label></div>"
        + "<div style='flex:1;'><label>Peso actual (kg, opcional): <input type='number' step='0.5' id='cap-peso' placeholder='ej. 450' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Veterinario / Profesional: <input id='cap-palp-responsable' list='dl-responsables' placeholder='ej. Jaime, Pipe, Sebas...' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Observaciones / Detalle: <input id='cap-notas' placeholder='ej. Confirmación ecográfica 45 días' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "pajuela") {
      h += "<label>Código o Nombre del Toro: <input id='cap-paj-toro' placeholder='ej. GUZ-01 / DON FULANO' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Raza: <input id='cap-paj-raza' placeholder='ej. Gyr, Brahman, Guzerat' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Canastilla: <input id='cap-paj-canastilla' placeholder='ej. Canastilla 1, A-2' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Cantidad de pajillas que ingresan: <input type='number' min='1' id='cap-paj-cant' value='5' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Costo por pajilla ($): <input type='number' step='100' id='cap-paj-costo' placeholder='ej. 45000' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>"
        + "<label>Procedencia / Casa Genética: <input id='cap-paj-procedencia' placeholder='ej. Ciale, Semex, Ganadería El Oasis' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Notas adicionales: <input id='cap-notas' placeholder='ej. Registro Asocebú 89123' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    } else if (tipo === "nitrogeno") {
      h += "<div class='aviso' style='margin:2px 0 8px;'>❄️ Registro de recarga de nitrógeno líquido en termo criogénico para mantener la viabilidad del semen.</div>"
        + "<div style='display:flex; gap:10px; flex-wrap:wrap;'>"
        + "<div style='flex:1;'><label>Intervalo de autonomía (días estimados): <input type='number' min='1' max='90' id='cap-nitr-intervalo' value='21' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "<div style='flex:1;'><label>Próxima recarga calculada: <input type='date' id='cap-nitr-prox' readonly style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte); background:var(--fondo-card); font-weight:700;'></label></div>"
        + "</div>"
        + "<label>Proveedor / Empresa de recarga: <input id='cap-nitr-proveedor' placeholder='ej. Linde, CryoGas, Técnico IA' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Costo de la recarga ($): <input type='number' step='1000' id='cap-nitr-costo' placeholder='ej. 120000' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label>Notas / Nivel medido con regla (cm): <input id='cap-notas' placeholder='ej. Lleno al tope, medido con varilla 14 cm' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>";
    }

    var hintFoto = "Foto de respaldo en campo";
    var titFoto = "Foto del Evento";
    var txtBtnFoto = " Tomar o Subir Foto";

    if (tipo === "parto") {
      titFoto = "Foto del Parto / Cría";
      hintFoto = "Foto de la cría recién nacida, ubre o condición de la madre";
    } else if (tipo === "destete") {
      titFoto = "Foto del Destete";
      hintFoto = "Foto de la cría destetada o de la madre en ese momento";
    } else if (tipo === "muerte") {
      titFoto = "Foto del Hallazgo / Necropsia";
      hintFoto = "Foto del animal fallecido, necropsia o causa de muerte";
    } else if (tipo === "tratamiento") {
      titFoto = "Foto del Medicamento / Receta";
      hintFoto = "Foto del frasco/lote de medicamento, receta o zona tratada";
    } else if (tipo === "pesaje") {
      titFoto = "Foto de Báscula / Animal";
      hintFoto = "Foto del animal en báscula, arete o condición corporal";
    } else if (tipo === "palpacion") {
      titFoto = "Foto Ecografía / Ficha Reproductiva";
      hintFoto = "Foto de la pantalla del ecógrafo, ovario o útero palpado";
    } else if (tipo === "pajuela") {
      titFoto = "Foto de Pajilla / Catálogo";
      hintFoto = "Foto de la pajilla, catálogo del toro o certificado genético";
    } else if (tipo === "nitrogeno") {
      titFoto = "Foto del Termo / Comprobante Recarga";
      hintFoto = "Foto del termo criogénico o recibo de recarga de nitrógeno";
    } else if (tipo === "celo") {
      titFoto = "Foto de Manifestación de Celo";
      hintFoto = "Foto de manifestación de celo (moco, monta, comportamiento)";
    } else if (tipo === "servicio") {
      titFoto = "Foto de Pajilla / Procedimiento";
      hintFoto = "Foto de la pajilla, catálogo del toro o procedimiento IA";
    } else if (tipo === "traslado") {
      titFoto = "Foto del Lote / Potrero";
      hintFoto = "Foto del lote o potrero de destino";
    } else if (tipo === "leche") {
      titFoto = "Foto del Recibo / Planilla de Leche";
      hintFoto = "Foto del recibo de quincena o planilla donde anotan la leche diaria";
      txtBtnFoto = " Tomar o Subir Recibo / Hoja";
    } else if (tipo === "gasto") {
      titFoto = "Foto de la Factura / Recibo";
      hintFoto = "Foto de la factura de compra, recibo de pago o comprobante";
      txtBtnFoto = " Tomar o Subir Factura";
    }

    h += "<div class='cap-foto-box' style='margin-top:12px; padding:12px; border:1.5px dashed var(--borde-fuerte); border-radius:8px; background:var(--superficie);'>"
      + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>"
      + "<div>"
      + "<div style='font-size:12.5px; font-weight:700; display:flex; align-items:center; gap:6px;'>"
      + icon("camera", 15)
      + titFoto + " <span style='font-size:11px; font-weight:normal; color:var(--texto-suave);'>(Opcional)</span>"
      + "</div>"
      + "<small style='font-size:11px; color:var(--texto-suave); display:block; margin-top:2px;'>" + esc(hintFoto) + "</small>"
      + "</div>"
      + "<div style='display:flex; gap:8px; align-items:center;'>"
      + "<input type='file' id='cap-foto-input' accept='image/*' style='display:none;'>"
      + "<button type='button' id='btn-elegir-foto' class='tema-btn' style='font-size:12px; padding:6px 12px; display:inline-flex; align-items:center; gap:6px; cursor:pointer;'>"
      + icon("camera", 13) + txtBtnFoto
      + "</button>"
      + "</div>"
      + "</div>"
      + "<div id='cap-foto-preview-wrap' style='display:none; margin-top:10px; padding-top:10px; border-top:1px solid var(--borde-fuerte); align-items:center; gap:12px;'>"
      + "<img id='cap-foto-preview' src='' alt='Vista previa' style='width:64px; height:64px; object-fit:cover; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
      + "<div style='flex:1; min-width:140px;'>"
      + "<div id='cap-foto-nombre' style='font-size:12px; font-weight:700; word-break:break-all;'>foto.jpg</div>"
      + "<div id='cap-foto-tam' style='font-size:11px; color:var(--texto-suave);'>Optimizada</div>"
      + "</div>"
      + "<button type='button' id='btn-quitar-foto' class='tema-btn' style='color:var(--color-rojo-txt); font-size:11.5px; padding:4px 9px; cursor:pointer;'>" + icon("xmark", 12) + " Quitar</button>"
      + "</div>"
      + "</div>";

    if (tipo === "leche" || tipo === "gasto") {
      var tituloIa = tipo === "leche" ? "Digitalización Inteligente de Recibo (IA)" : "Digitalización Inteligente de Factura (IA)";
      var descIa = tipo === "leche"
        ? "Lee automáticamente cada renglón manuscrito, detecta fechas y suma los litros diarios."
        : "Lee automáticamente el monto, la fecha, el proveedor y sugiere la categoría del gasto o ingreso.";
      var btnTxtIa = tipo === "leche" ? "Leer Recibo con IA" : "Leer Factura con IA";
      h += "<div id='box-analizar-recibo-ia' style='display:none; margin-top:14px; padding:14px; border-radius:8px; background:var(--superficie); border:1.5px solid var(--verde-marca); box-shadow:0 2px 6px var(--sombra);'>"
        + "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>"
        + "<div>"
        + "<div style='font-weight:700; font-size:13.5px; color:var(--verde-marca); display:flex; align-items:center; gap:6px;'>"
        + icon("sparkles", 16) + tituloIa
        + "</div>"
        + "<small style='color:var(--texto-suave); font-size:11.5px; display:block; margin-top:2px;'>" + esc(descIa) + "</small>"
        + "</div>"
        + "<button type='button' id='btn-analizar-recibo-ia' class='tema-btn' style='background:var(--verde-marca); color:#fff; font-weight:700; font-size:12.5px; padding:7px 14px; border:none; border-radius:6px; cursor:pointer; display:inline-flex; align-items:center; gap:6px;'>"
        + icon("sparkles", 14) + esc(btnTxtIa)
        + "</button>"
        + "</div>"
        + "<div id='recibo-ia-estado' style='margin-top:10px; font-size:12.5px;'></div>"
        + "<div id='recibo-ia-preview' style='margin-top:12px; display:none;'></div>"
        + "</div>";
    }

    if (tipo === "tarea") {
      h += "<div style='display:flex; gap:8px; margin-bottom:10px;'>"
        + "<button type='button' class='tema-btn cap-obj-btn act' data-obj='animal' style='flex:1; padding:8px; font-size:13px;'>🐄 Animal</button>"
        + "<button type='button' class='tema-btn cap-obj-btn' data-obj='potrero' style='flex:1; padding:8px; font-size:13px;'>🌿 Potrero</button>"
        + "<button type='button' class='tema-btn cap-obj-btn' data-obj='general' style='flex:1; padding:8px; font-size:13px;'>📋 General</button>"
        + "</div>"
        + "<input type='hidden' id='cap-tarea-obj' value='animal'>"
        + "<div id='cap-wrap-obj-animal'>"
        + "<label>Chapeta / Tag del Animal: <input id='cap-tag' placeholder='ej. JA457' list='dl-tags' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "</div>"
        + "<div id='cap-wrap-obj-potrero' style='display:none;'>"
        + "<label>Potrero: <input id='cap-tarea-potrero' placeholder='ej. OLEGARIO I' list='dl-potreros' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "</div>"
        + "<label style='margin-top:6px;'>Tipo de Acción / Tarea: "
        + "<select id='cap-tarea-tipo' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
        + "<option value='MEDICAMENTO'>💉 Aplicar medicamento / Tratamiento</option>"
        + "<option value='FUMIGAR'>🌿 Fumigar maleza / Potrero</option>"
        + "<option value='REVISION'>🔍 Revisión veterinaria / Chequeo</option>"
        + "<option value='TRASLADO'>🚚 Traslado de potrero</option>"
        + "<option value='CERCA'>⚡ Arreglar cerca / Mantenimiento</option>"
        + "<option value='PESAJE'>⚖️ Pesaje de control</option>"
        + "<option value='OTRO'>📋 Otra tarea / General</option>"
        + "</select></label>"
        + "<label style='margin-top:6px;'>Indicación / Descripción de la tarea: <input id='cap-tarea-desc' placeholder='ej. Aplicar 10ml oxitetraciclina IM o fumigar borde cerca' required style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label>"
        + "<label style='margin-top:6px;'>Adjudicar / Asignar a: "
        + "<input id='cap-tarea-asignado' list='dl-integrantes-equipo' placeholder='ej. Encargado, Administrador, o nombre...' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'>"
        + "<datalist id='dl-integrantes-equipo'>"
        + "<option value='Encargado'></option>"
        + "<option value='Administrador'></option>"
        + "<option value='Veterinario'></option>"
        + "<option value='Trabajador'></option>"
        + "</datalist></label>"
        + "<div style='display:flex; gap:10px; margin-top:6px;'>"
        + "<div style='flex:1;'><label>Prioridad: <select id='cap-tarea-prioridad' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'><option value='NORMAL'>Normal</option><option value='URGENTE'>🚨 Urgente</option></select></label></div>"
        + "<div style='flex:1;'><label>Hora límite (opc): <input type='time' id='cap-tarea-hora' style='width:100%; padding:8px; border-radius:6px; border:1px solid var(--borde-fuerte);'></label></div>"
        + "</div>";
    }

    return h;
  }

