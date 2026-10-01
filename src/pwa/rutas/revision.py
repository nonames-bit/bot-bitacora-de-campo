"""Bandeja "Por revisar": aprobar, corregir o rechazar los eventos delicados
que registró un trabajador (ver src/engine/revision.py).

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py). Se
registra después de sync y manga_ia, que dejan en ``h`` las funciones que
aplican el evento al aprobarlo.
"""
from __future__ import annotations

import logging
from flask import jsonify, request, session
from ...engine import revision as _revision
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
    _error_interno,
    _invalidar_tareas,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def _para_cliente(p: dict) -> dict:
    """Fila de la bandeja sin la foto en base64 (puede pesar megas)."""
    origen = p.get("origen") or "app"
    datos = p.get("datos") or {}
    return {
        "id": p["id"],
        "tipo": p["tipo"],
        "nombre_tipo": _revision.NOMBRE_TIPO.get(p["tipo"], p["tipo"]),
        "resumen": p.get("resumen") or _revision.resumen(origen, p["tipo"], datos),
        "fecha": p.get("fecha"),
        "animal_tag": p.get("animal_tag"),
        "registrado_por": p.get("registrado_por"),
        "registrado_por_nombre": p.get("registrado_por_nombre"),
        "canal": p.get("canal"),
        "creado_en": p.get("creado_en"),
        "estado": p.get("estado"),
        "revisado_por_nombre": p.get("revisado_por_nombre"),
        "revisado_en": p.get("revisado_en"),
        "nota_revision": p.get("nota_revision"),
        "tiene_foto": bool(datos.get("foto_base64") or datos.get("foto_ruta")),
        "campos": _revision.campos_editables(origen, datos),
    }


def registrar(app, ctx, h):
    _rol_actual = h._rol_actual
    db_path = ctx.db_path

    def _es_revisor() -> bool:
        return _rol_actual() in _revision.ROLES_REVISORES

    def _sin_permiso():
        return jsonify({"ok": False, "error": "Solo el propietario o un administrador revisa registros."}), 403

    def _aplicar(db_r, p: dict, datos: dict) -> tuple[bool, list]:
        """Aplica el evento como si llegara ahora, a nombre de quien lo
        registró. Devuelve (ok, errores)."""
        origen = p.get("origen") or "app"
        autor = p.get("registrado_por")
        if origen == "bot":
            try:
                from ...bot.bot_interface import Bot
            except ImportError:
                from src.bot.bot_interface import Bot  # type: ignore
            try:
                Bot(db_r).aplicar_evento_revisado(datos, user_id=autor)
            except ValueError as e:
                return False, [str(e)]
            return True, []
        if p["tipo"] == "traslado_masivo":
            ok, cuerpo, _ = h._ejecutar_traslado_masivo(
                db_r, datos.get("potrero_origen") or "", datos.get("potrero_destino") or "",
                p.get("fecha"), datos.get("motivo"), autor)
            return ok, ([] if ok else [cuerpo.get("error") or "No se pudo mover el lote."])
        res = h._procesar_eventos_sync(
            db_r, [{"tipo": p["tipo"], "payload": datos, "fecha": p.get("fecha")}],
            autor, _rol_actual(), nombre_usuario=p.get("registrado_por_nombre"), revisar=False)
        return res["procesados"] > 0 and not res["errores"], res["errores"]

    @app.get("/api/revision/pendientes")
    def api_revision_pendientes():
        if not _es_revisor():
            return _sin_permiso()
        db_r = _db(db_path)
        try:
            pendientes = [_para_cliente(p) for p in db_r.listar_pendientes("PENDIENTE")]
            revisados = [_para_cliente(p) for p in db_r.listar_pendientes("REVISADOS", limite=15)]
            return jsonify({"ok": True, "pendientes": pendientes, "revisados": revisados,
                            "total": len(pendientes)})
        except Exception:
            logger.exception("Error al listar registros por revisar")
            return _error_interno(500)
        finally:
            db_r.close()

    @app.get("/api/revision/contador")
    def api_revision_contador():
        if not _es_revisor():
            return jsonify({"ok": True, "total": 0})
        db_r = _db(db_path)
        try:
            return jsonify({"ok": True, "total": db_r.contar_pendientes()})
        finally:
            db_r.close()

    @app.post("/api/revision/<int:pid>/aprobar")
    def api_revision_aprobar(pid):
        if not _es_revisor():
            return _sin_permiso()
        cuerpo = request.get_json(silent=True) or {}
        db_r = _db(db_path)
        try:
            p = db_r.obtener_pendiente(pid)
            if not p:
                return jsonify({"ok": False, "error": "Ese registro ya no existe."}), 404
            if not db_r.tomar_pendiente(pid):
                return jsonify({"ok": False, "error": "Ese registro ya fue revisado."}), 409
            origen = p.get("origen") or "app"
            cambios = cuerpo.get("cambios")
            datos = _revision.aplicar_cambios(origen, p.get("datos") or {}, cambios)
            try:
                ok, errores = _aplicar(db_r, p, datos)
            except Exception:
                logger.exception("Error al aplicar el registro por revisar #%s", pid)
                ok, errores = False, ["No se pudo registrar. Revisa los datos e intenta de nuevo."]
            if not ok:
                db_r.soltar_pendiente(pid)
                return jsonify({"ok": False, "error": "; ".join(errores) or "No se pudo registrar."}), 422

            revisor = session.get("nombre") or "Administrador"
            corregido = bool(cambios) and datos != (p.get("datos") or {})
            texto_res = _revision.resumen(origen, p["tipo"], datos)
            db_r.cerrar_pendiente(pid, "APROBADO", revisado_por=session.get("user_id"),
                                  revisado_por_nombre=revisor,
                                  nota="Corregido antes de aprobar" if corregido else None,
                                  datos=datos if corregido else None,
                                  resumen=texto_res if corregido else None)
            _revision.avisar_equipo(
                db_r, f"{revisor} aprobó{' con correcciones' if corregido else ''} "
                      f"el registro de {p.get('registrado_por_nombre') or 'un trabajador'}: {texto_res}.",
                user_id=session.get("user_id"), nombre=revisor, rol=_rol_actual() or "ADMIN")
            _invalidar_tareas()
            return jsonify({"ok": True, "corregido": corregido, "restantes": db_r.contar_pendientes()})
        except Exception:
            logger.exception("Error al aprobar el registro por revisar #%s", pid)
            return _error_interno(500)
        finally:
            db_r.close()

    @app.post("/api/revision/<int:pid>/rechazar")
    def api_revision_rechazar(pid):
        if not _es_revisor():
            return _sin_permiso()
        cuerpo = request.get_json(silent=True) or {}
        motivo = str(cuerpo.get("motivo") or "").strip()[:300] or None
        db_r = _db(db_path)
        try:
            p = db_r.obtener_pendiente(pid)
            if not p:
                return jsonify({"ok": False, "error": "Ese registro ya no existe."}), 404
            revisor = session.get("nombre") or "Administrador"
            if not db_r.cerrar_pendiente(pid, "RECHAZADO", revisado_por=session.get("user_id"),
                                         revisado_por_nombre=revisor, nota=motivo):
                return jsonify({"ok": False, "error": "Ese registro ya fue revisado."}), 409
            _revision.avisar_equipo(
                db_r, f"{revisor} rechazó el registro de {p.get('registrado_por_nombre') or 'un trabajador'}: "
                      f"{p.get('resumen') or p['tipo']}." + (f" Motivo: {motivo}" if motivo else ""),
                user_id=session.get("user_id"), nombre=revisor, rol=_rol_actual() or "ADMIN")
            return jsonify({"ok": True, "restantes": db_r.contar_pendientes()})
        except Exception:
            logger.exception("Error al rechazar el registro por revisar #%s", pid)
            return _error_interno(500)
        finally:
            db_r.close()
