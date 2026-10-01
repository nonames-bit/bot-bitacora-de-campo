"""Sincronización de eventos de campo (/api/sync), incluida la cola offline.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

from datetime import date
import logging
from typing import Any, Optional
from flask import jsonify, request, session
from ...engine import lactancia as _lactancia
from ...engine import revision as _revision
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
    _invalidar_tareas,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _guardar_foto_evento = h._guardar_foto_evento
    _limite_api = h._limite_api
    _rol_actual = h._rol_actual
    db_path = ctx.db_path
    users_file = ctx.users_file


    # Tipos de /api/sync restringidos por rol. Se alinean con lo que la UI
    # ofrece a cada rol: la Captura Rápida del TRABAJADOR incluye pajuelas,
    # nitrógeno y gastos (EGRESO), pero IATF e inseminadores solo existen en
    # la vista de Reproducción (OWNER/ADMIN) y sus endpoints dedicados los
    # prohíben a roles de campo. Sin este mapa, /api/sync era una puerta
    # trasera a esas acciones.
    _ROLES_GESTION = ("OWNER", "ADMIN", "MAYORDOMO")
    _ROLES_SYNC = {
        "inseminador": _ROLES_GESTION,
        "nuevo_inseminador": _ROLES_GESTION,
        "iatf_paso": _ROLES_GESTION,
        "droga_iatf": _ROLES_GESTION,
        "iatf_inseminar": _ROLES_GESTION,
        "lote_iatf_inseminar": _ROLES_GESTION,
    }

    def _foto_media_existente(db_inst, ruta: Any) -> Optional[str]:
        """Acepta la ruta de foto que envía el cliente solo si es una foto ya
        registrada por el servidor directamente dentro de media/ (lo que
        devuelve /api/finanzas/analizar-factura). Cualquier otra ruta
        (absoluta, con "..", subcarpetas o no registrada) se descarta."""
        ruta = str(ruta or "").strip().replace("\\", "/")
        if not ruta.startswith("media/"):
            return None
        nombre = ruta[len("media/"):]
        if not nombre or "/" in nombre or nombre.startswith("."):
            return None
        fila = db_inst.query_one("SELECT 1 AS ok FROM fotos WHERE ruta = ? LIMIT 1", (ruta,))
        return ruta if fila else None

    def _procesar_eventos(db_sync, eventos, uid, rol_sync, nombre_usuario=None, revisar=True):
        """Registra una lista de eventos de /api/sync. Con ``revisar`` los
        eventos delicados de un TRABAJADOR (parto, muerte, venta, traslado)
        no se aplican: quedan en ``registros_pendientes`` hasta que un OWNER
        o ADMIN los apruebe (ver rutas/revision.py, que llama a esta misma
        función con revisar=False al aprobar)."""
        from datetime import datetime

        procesados = 0
        en_revision = 0
        errores = []
        ids_ok = []
        for ev in eventos:
            if not isinstance(ev, dict):
                continue
            tipo = str(ev.get("tipo", "")).lower().strip()
            payload = ev.get("payload") or {}
            fecha = ev.get("fecha") or payload.get("fecha") or date.today().isoformat()
            id_local = ev.get("id_local")
            if not isinstance(id_local, str) or not id_local.strip():
                id_local = None
            else:
                id_local = id_local.strip()[:128]

            # Idempotencia (P0.1): si este id_local ya fue procesado, el
            # reintento del cliente (respuesta perdida en conexión rural)
            # NO debe volver a registrar el evento; se devuelve en ids_ok
            # para que el cliente purgue la cola igual que la primera vez.
            if id_local:
                ya_procesado = db_sync.query_one(
                    "SELECT 1 AS ok FROM sync_ids_procesados WHERE id_local = ?",
                    (id_local,),
                )
                if ya_procesado:
                    ids_ok.append(id_local)
                    procesados += 1
                    continue

            # Mismos permisos que los endpoints dedicados: /api/sync no
            # puede ser una puerta trasera para roles de campo.
            roles_req = _ROLES_SYNC.get(tipo)
            if roles_req and rol_sync not in roles_req:
                errores.append(f"Permisos insuficientes para '{tipo}' ({id_local or tipo})")
                continue

            n_ids_previos = len(ids_ok)
            try:
                if revisar and _revision.requiere_revision(rol_sync, tipo):
                    # Evento delicado de un trabajador: queda en pausa hasta
                    # que un OWNER/ADMIN lo apruebe. Para el cliente cuenta
                    # como recibido (sale de la cola offline).
                    _revision.poner_en_revision(
                        db_sync, origen="app", tipo=tipo, datos=payload, fecha=fecha,
                        registrado_por=uid, registrado_por_nombre=nombre_usuario,
                        canal="App", users_file=users_file,
                    )
                    en_revision += 1
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "parto":
                    tipo_evento = str(payload.get("tipo_evento") or "PARTO").upper()
                    padre_tag = payload.get("padre_tag") or payload.get("toro_tag") or payload.get("toro") or None
                    # Parto con la "vaca" de < 15 meses: casi siempre es el
                    # parto de la madre anotado en la cría. No se guarda;
                    # se avisa y se saca de la cola para no reintentarlo.
                    vaca_tag_p = str(payload.get("vaca_tag") or payload.get("tag") or "").strip()
                    fila_v = db_sync.query_one(
                        "SELECT fecha_nacimiento FROM animales WHERE UPPER(tag) = UPPER(?)", (vaca_tag_p,))
                    if fila_v and _lactancia.parto_imposible(fila_v["fecha_nacimiento"], fecha):
                        errores.append(
                            f"Parto de {vaca_tag_p} NO guardado: nació el {fila_v['fecha_nacimiento']} y es "
                            f"muy joven para parir. ¿Era el parto de su madre?")
                        if id_local:
                            ids_ok.append(id_local)
                        continue
                    primer_id = db_sync.registrar_parto(
                        vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                        fecha=fecha,
                        sexo_cria=payload.get("sexo_cria"),
                        estado_cria=payload.get("estado_cria", "VIVO"),
                        peso_nacimiento=payload.get("peso_nacimiento"),
                        id_cria_tag=payload.get("id_cria_tag"),
                        notas=payload.get("notas"),
                        potrero_cria=payload.get("potrero_cria"),
                        potrero_madre=payload.get("potrero_madre"),
                        registrado_por=uid,
                        tipo_evento=tipo_evento,
                        padre_tag=padre_tag,
                        distocia=bool(payload.get("distocia")),
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                    # Parto gemelar: el segundo gemelo viaja en
                    # payload.gemelo y se registra como una segunda fila
                    # de partos agrupada por grupo_parto_id (ver
                    # Database.registrar_parto, que ya dejó grupo_parto_id
                    # = primer_id en la primera fila).
                    gemelo = payload.get("gemelo") if tipo_evento == "GEMELAR" else None
                    if gemelo and primer_id:
                        db_sync.registrar_parto(
                            vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                            fecha=fecha,
                            sexo_cria=gemelo.get("sexo_cria"),
                            estado_cria=gemelo.get("estado_cria", "VIVO"),
                            peso_nacimiento=gemelo.get("peso_nacimiento"),
                            id_cria_tag=gemelo.get("id_cria_tag"),
                            notas=payload.get("notas"),
                            potrero_cria=payload.get("potrero_cria"),
                            registrado_por=uid,
                            tipo_evento="GEMELAR",
                            grupo_parto_id=primer_id,
                            padre_tag=padre_tag,
                        )
                elif tipo == "destete":
                    db_sync.registrar_destete(
                        cria_tag=payload.get("cria_tag") or payload.get("animal_tag") or payload.get("tag"),
                        fecha=fecha,
                        peso_kg=payload.get("peso_kg"),
                        potrero_cria=payload.get("potrero_cria"),
                        potrero_madre=payload.get("potrero_madre"),
                        peso_madre_kg=payload.get("peso_madre_kg"),
                        cond_corporal_madre=payload.get("cond_corporal_madre"),
                        notas=payload.get("notas"),
                        registrado_por=uid,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "manejo":
                    tags_m = payload.get("animal_tags")
                    if not isinstance(tags_m, list) or not tags_m:
                        tags_m = [payload.get("animal_tag") or payload.get("tag")]
                    for tag_m in tags_m[:500]:
                        if tag_m:
                            db_sync.registrar_manejo(
                                animal_tag=str(tag_m), tipo=payload.get("tipo_manejo"), fecha=fecha,
                                producto=payload.get("producto"), lote_producto=payload.get("lote_producto"),
                                notas=payload.get("notas"), registrado_por=uid,
                                responsable=payload.get("responsable"),
                            )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "secado":
                    db_sync.registrar_secado(
                        vaca_tag=payload.get("animal_tag") or payload.get("vaca_tag") or payload.get("tag"),
                        fecha=fecha,
                        potrero_destino=payload.get("potrero_destino"),
                        cond_corporal=payload.get("cond_corporal"),
                        motivo=payload.get("motivo"),
                        notas=payload.get("notas"),
                        registrado_por=uid,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "pesaje":
                    db_sync.registrar_pesaje(
                        animal_tag=payload.get("animal_tag") or payload.get("tag"),
                        fecha=fecha,
                        peso_kg=payload.get("peso_kg"),
                        gmd_calculada=payload.get("gmd"),
                        evento=payload.get("evento") or "PESAJE",
                        registrado_por=uid,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "tratamiento":
                    db_sync.registrar_tratamiento(
                        animal_tag=payload.get("animal_tag") or payload.get("tag"),
                        fecha=fecha,
                        producto=payload.get("producto"),
                        principio_activo=payload.get("principio_activo"),
                        dosis=payload.get("dosis"),
                        via=payload.get("via"),
                        dias_retiro_leche=int(payload.get("dias_retiro_leche") or 0),
                        dias_retiro_carne=int(payload.get("dias_retiro_carne") or 0),
                        diagnostico=payload.get("diagnostico"),
                        registrado_por=uid,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "traslado":
                    db_sync.registrar_traslado(
                        animal_tag=payload.get("animal_tag") or payload.get("tag"),
                        fecha=fecha,
                        lote=payload.get("lote"),
                        potrero_origen=payload.get("potrero_origen"),
                        potrero_destino=payload.get("potrero_destino"),
                        motivo=payload.get("motivo"),
                        registrado_por=uid,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "celo":
                    db_sync.registrar_celo(
                        vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                        fecha=fecha,
                        am_pm=payload.get("am_pm"),
                        notas=payload.get("notas"),
                        registrado_por=uid,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "servicio":
                    db_sync.registrar_servicio(
                        vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                        fecha=fecha,
                        tipo_servicio=payload.get("tipo_servicio"),
                        toro_pajilla=payload.get("toro_pajilla"),
                        raza_toro=payload.get("raza_toro"),
                        inseminador=payload.get("inseminador"),
                        fep_calculada=payload.get("fep_calculada"),
                        estado=payload.get("estado"),
                        registrado_por=uid,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "muerte":
                    db_sync.registrar_muerte(
                        animal_tag=payload.get("animal_tag") or payload.get("tag"),
                        fecha=fecha,
                        causa_presunta=payload.get("causa_presunta"),
                        notas=payload.get("notas"),
                        registrado_por=uid,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "movimiento" and str(payload.get("tipo_movimiento") or "").strip().upper() != "VENTA":
                    # Movimiento genérico (entrada, compra, descarte...): se
                    # guarda con su propio tipo. Sin tipo no se adivina,
                    # porque tratarlo como venta sacaría al animal del hato.
                    tipo_mov = str(payload.get("tipo_movimiento") or "").strip().upper()
                    if not tipo_mov:
                        errores.append(
                            f"Movimiento {id_local or ''} NO guardado: falta el tipo (entrada, compra, venta…).")
                        if id_local:
                            ids_ok.append(id_local)
                        continue
                    p_precio = payload.get("precio")
                    try:
                        precio_num = float(p_precio) if p_precio is not None and str(p_precio).strip() != "" else None
                    except (ValueError, TypeError):
                        precio_num = None
                    db_sync.registrar_movimiento(
                        animal_tag=payload.get("animal_tag") or payload.get("tag"),
                        fecha=fecha,
                        tipo_movimiento=tipo_mov,
                        procedencia_destino=payload.get("procedencia_destino"),
                        precio=precio_num,
                        notas=payload.get("notas"),
                        registrado_por=uid,
                    )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("venta", "movimiento"):
                    p_tag = payload.get("animal_tag") or payload.get("tag")
                    p_comprador = payload.get("comprador") or payload.get("procedencia_destino") or payload.get("destino")
                    p_precio = payload.get("precio") or payload.get("monto") or payload.get("valor")
                    try:
                        precio_num = float(p_precio) if p_precio is not None and str(p_precio).strip() != "" else None
                    except (ValueError, TypeError):
                        precio_num = None
                    p_peso = payload.get("peso_kg") or payload.get("peso")
                    p_motivo = payload.get("motivo")
                    p_notas = payload.get("notas")
                    try:
                        db_sync.registrar_venta(
                            animal_tag=p_tag,
                            fecha=fecha,
                            comprador=p_comprador,
                            precio=precio_num,
                            peso_kg=p_peso,
                            motivo=p_motivo,
                            notas=p_notas,
                            registrado_por=uid,
                        )
                    except ValueError as e:
                        # Animal inexistente o ya fuera del hato: reintentar
                        # no lo arregla, así que se avisa y sale de la cola.
                        errores.append(f"Venta NO guardada: {e}.")
                        if id_local:
                            ids_ok.append(id_local)
                        continue
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "leche":
                    db_sync.registrar_produccion_leche(
                        fecha=fecha,
                        litros=payload.get("litros"),
                        notas=payload.get("notas"),
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "control_leche":
                    # Control lechero de varias vacas (AM + PM). Idempotente
                    # por vaca y fecha: reenviar desde la cola offline no duplica.
                    regs = payload.get("registros") if isinstance(payload.get("registros"), list) else []
                    for reg in regs[:500]:
                        if not isinstance(reg, dict) or not reg.get("tag"):
                            continue
                        try:
                            db_sync.registrar_control_leche(
                                animal_tag=str(reg["tag"]), fecha=fecha, litros_am=reg.get("am"),
                                litros_pm=reg.get("pm"), registrado_por=uid,
                            )
                        except ValueError:
                            errores.append(f"Control lechero: no existe la vaca {reg.get('tag')}")
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "gasto":
                    tipo_fin = str(payload.get("tipo_finanza") or "EGRESO").strip().upper()
                    try:
                        monto_ok = float(payload.get("monto")) > 0
                    except (TypeError, ValueError):
                        monto_ok = False
                    if tipo_fin not in ("INGRESO", "EGRESO") or not monto_ok:
                        errores.append(f"Gasto inválido ({id_local or tipo}): tipo INGRESO/EGRESO y monto > 0")
                        continue
                    if tipo_fin == "INGRESO" and rol_sync not in ("OWNER", "ADMIN"):
                        errores.append(f"Permisos insuficientes para registrar INGRESO ({id_local or tipo})")
                        continue
                    fid_finanza = db_sync.registrar_finanza(
                        fecha=fecha,
                        tipo=tipo_fin,
                        categoria=payload.get("categoria"),
                        concepto=payload.get("concepto"),
                        monto=payload.get("monto"),
                        litros=payload.get("litros"),
                        animal_tag=payload.get("animal_tag") or None,
                        potrero=payload.get("potrero") or None,
                        contraparte=payload.get("contraparte") or None,
                        notas=payload.get("notas"),
                        registrado_por=uid,
                    )
                    foto_ruta_directa = _foto_media_existente(db_sync, payload.get("foto_ruta"))
                    if foto_ruta_directa:
                        # La foto ya se guardó al analizar la factura con IA
                        # (ver /api/finanzas/analizar-factura) -- solo se
                        # enlaza, no se vuelve a subir el mismo archivo.
                        db_sync.execute(
                            "UPDATE finanzas SET foto_ruta = ? WHERE id = ?",
                            (foto_ruta_directa, fid_finanza),
                        )
                    else:
                        fid_foto = _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                        if fid_foto:
                            foto_fila = db_sync.query_one("SELECT ruta FROM fotos WHERE id = ?", (fid_foto,))
                            if foto_fila and foto_fila["ruta"]:
                                db_sync.execute(
                                    "UPDATE finanzas SET foto_ruta = ? WHERE id = ?",
                                    (foto_fila["ruta"], fid_finanza),
                                )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo == "ronda":
                    db_sync.registrar_ronda_campo(
                        user_id=uid,
                        usuario_nombre=session.get("nombre") or (_rol_actual() or "Usuario"),
                        fecha=fecha,
                        hora=payload.get("hora"),
                        lat=payload.get("lat"),
                        lon=payload.get("lon"),
                        potrero_id=payload.get("potrero_id"),
                        potrero_nombre=payload.get("potrero_nombre"),
                        punto_control=payload.get("punto_control"),
                        notas=payload.get("notas"),
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("tarea", "recordatorio"):
                    msg_tarea = payload.get("mensaje") or payload.get("descripcion") or f"Tarea: {payload.get('tipo_tarea', 'Campo')}"
                    db_sync.registrar_recordatorio(
                        mensaje=msg_tarea,
                        fecha_programada=fecha,
                        hora=payload.get("hora"),
                        creado_por=uid,
                        asignado_a=payload.get("asignado_a"),
                        tipo_objetivo=payload.get("tipo_objetivo"),
                        animal_tag=payload.get("animal_tag") or payload.get("tag"),
                        potrero_nombre=payload.get("potrero_nombre") or payload.get("potrero"),
                        tipo_tarea=payload.get("tipo_tarea"),
                        prioridad=payload.get("prioridad") or "NORMAL",
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("telemetria", "telemetria_ping"):
                    db_sync.registrar_telemetria_gps(
                        user_id=uid,
                        usuario_nombre=session.get("nombre") or (_rol_actual() or "Usuario"),
                        rol=_rol_actual() or "TRABAJADOR",
                        lat=payload.get("lat"),
                        lon=payload.get("lon"),
                        precision_m=payload.get("precision_m"),
                        evento_origen=payload.get("evento_origen") or "sync_offline",
                        fecha=fecha,
                        hora=payload.get("hora"),
                    )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("palpacion", "tacto", "diagnostico"):
                    p_peso = payload.get("peso_kg")
                    p_cc = payload.get("cond_corporal")
                    peso_val = float(p_peso) if (p_peso and str(p_peso).replace(".", "", 1).isdigit()) else None
                    cc_val = float(p_cc) if (p_cc and str(p_cc).replace(".", "", 1).isdigit()) else None
                    db_sync.registrar_diagnostico(
                        vaca_tag=payload.get("animal_tag") or payload.get("tag") or payload.get("vaca_tag"),
                        fecha=fecha,
                        resultado=payload.get("resultado") or "PREÑADA",
                        dias_gestacion=payload.get("dias_gestacion"),
                        responsable=payload.get("responsable") or payload.get("veterinario"),
                        registrado_por=uid,
                        metodo=payload.get("metodo") or "TACTO",
                        hallazgo=payload.get("hallazgo"),
                        detalle=payload.get("detalle") or payload.get("notas"),
                        toro_pajuela=payload.get("toro_pajuela") or payload.get("reproductor"),
                        peso_kg=peso_val,
                        cond_corporal=cc_val,
                    )
                    _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("nitrogeno", "recarga_nitrogeno"):
                    db_sync.registrar_recarga_nitrogeno(
                        fecha_recarga=fecha,
                        dias_intervalo=int(payload.get("dias_intervalo") or 21),
                        proxima_recarga=payload.get("proxima_recarga"),
                    )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("pajuela", "pajuela_add", "inventario_pajuela"):
                    db_sync.registrar_pajuela(
                        codigo_toro=payload.get("codigo_toro") or payload.get("toro"),
                        raza=payload.get("raza"),
                        procedencia=payload.get("procedencia"),
                        canastilla=payload.get("canastilla"),
                        cantidad=int(payload.get("cantidad") or 1),
                        costo=float(payload.get("costo") or 0.0),
                        fecha_ingreso=fecha,
                    )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("aforo", "aforo_potrero"):
                    afo_val = float(payload.get("aforo_kg_m2") or payload.get("aforo") or 0.0)
                    db_sync.registrar_aforo(
                        potrero_id_o_nom=payload.get("potrero_id") or payload.get("potrero") or payload.get("nombre"),
                        aforo_kg_m2=afo_val,
                        fecha=fecha,
                        metodo=payload.get("metodo") or "CUADRO_1M2",
                        registrado_por=uid,
                    )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("inseminador", "nuevo_inseminador"):
                    db_sync.registrar_inseminador(
                        nombre=payload.get("nombre"),
                        telefono=payload.get("telefono"),
                        notas=payload.get("notas"),
                    )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("iatf_paso", "droga_iatf"):
                    lid_p = payload.get("lote_id")
                    if lid_p:
                        db_sync.registrar_avance_paso_iatf(
                            lote_id=int(lid_p),
                            paso_index=int(payload.get("paso_index") or 0),
                            producto_aplicado=payload.get("producto"),
                            dosis=payload.get("dosis"),
                            marca=payload.get("marca"),
                            realizado_por=payload.get("realizado_por") or str(uid or ""),
                            notas=payload.get("notas"),
                        )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                elif tipo in ("iatf_inseminar", "lote_iatf_inseminar"):
                    lid_i = payload.get("lote_id")
                    if lid_i:
                        db_sync.ejecutar_inseminacion_lote_iatf(
                            lote_id=int(lid_i),
                            toro_pajuela=payload.get("toro_pajuela") or payload.get("toro"),
                            inseminador=payload.get("inseminador"),
                            fecha=fecha,
                        )
                    procesados += 1
                    if id_local:
                        ids_ok.append(id_local)
                else:
                    errores.append(f"Tipo de evento no reconocido: {tipo}")

                # Idempotencia (P0.1): el evento se procesó bien en esta
                # pasada -> persistir su id_local para que un reintento
                # futuro (misma cola offline reenviada) no lo duplique.
                if id_local and len(ids_ok) > n_ids_previos:
                    db_sync.execute(
                        "INSERT OR IGNORE INTO sync_ids_procesados "
                        "(id_local, user_id, tipo_evento, procesado_en) "
                        "VALUES (?, ?, ?, ?)",
                        (id_local, uid, tipo, datetime.now().isoformat(timespec="seconds")),
                    )
            except Exception as e:
                logger.exception("Error al sincronizar evento %s: %s", id_local, e)
                errores.append(f"Error en evento {id_local or tipo}")
        return {"procesados": procesados, "errores": errores, "ids_ok": ids_ok, "en_revision": en_revision}

    h._procesar_eventos_sync = _procesar_eventos

    @app.post("/api/sync")
    @_limite_api("sync")
    def api_sync():
        datos = request.get_json(silent=True) or {}
        eventos = datos.get("eventos", [])
        if not isinstance(eventos, list):
            return jsonify({"error": "Se esperaba una lista en 'eventos'."}), 400

        db_sync = _db(db_path)
        uid = session.get("user_id")
        rol_sync = _rol_actual()

        try:
            res = _procesar_eventos(db_sync, eventos, uid, rol_sync,
                                    nombre_usuario=session.get("nombre"))
            procesados = res["procesados"]

            # Poda barata de la tabla de idempotencia: los reintentos del
            # cliente ocurren a los minutos/horas, no a los meses. Ventana de
            # 7 días cubre cualquier cola offline larga sin crecimiento
            # ilimitado en el SQLite del VPS.
            try:
                db_sync.execute(
                    "DELETE FROM sync_ids_procesados "
                    "WHERE procesado_en < datetime('now', '-7 days', 'localtime')"
                )
            except Exception:
                pass
            if procesados:
                _invalidar_tareas()

            return jsonify({
                "ok": True,
                "procesados": procesados,
                "total": len(eventos),
                "errores": res["errores"],
                "ids_ok": res["ids_ok"],
                "en_revision": res["en_revision"],
            })
        finally:
            db_sync.close()
