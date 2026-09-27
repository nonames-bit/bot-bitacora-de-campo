"""Ficha y datos de cada animal, ordeño, lote de ordeño, inventario y genética.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import logging
from flask import jsonify, request, session
from ...engine import lactancia as _lactancia
from ...engine.genetic_engine import CATALOGO_RAZAS_PREDEFINIDAS as _CATALOGO_RAZAS_PREDEFINIDAS
from ...engine.genetic_engine import generar_resumen_zootecnico as _generar_resumen_zootecnico
from ...engine.genetic_engine import normalizar_nombre_raza as _normalizar_nombre_raza
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
    _error_interno,
    _invalidar_tareas,
    datos_ficha,
    datos_genetica,
    datos_inventario,
    datos_poblacion,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _rol_actual = h._rol_actual
    db_path = ctx.db_path

    @app.get("/api/ficha/<tag>")
    def api_ficha(tag):
        out = datos_ficha(tag, db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    def _campo_texto(datos, nombre):
        v = datos.get(nombre)
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    @app.post("/api/animal")
    def api_animal_crear():
        """Crea un animal nuevo (datos maestros: identidad y genealogía) sin
        pasar por un evento de campo -- hasta ahora los animales solo se
        creaban implícitamente al registrar un parto/pesaje/etc."""
        if _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"ok": False, "error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403
        datos = request.get_json(silent=True) or {}
        tag = str(datos.get("tag") or "").strip()
        if not tag:
            return jsonify({"ok": False, "error": "El arete/tag es obligatorio."}), 400
        db_a = _db(db_path)
        try:
            if db_a.animal_id(tag) is not None:
                return jsonify({"ok": False, "error": f"Ya existe un animal con el tag '{tag}'. Use editar en su lugar."}), 409
            db_a.registrar_animal(
                tag,
                nombre=_campo_texto(datos, "nombre"), sexo=_campo_texto(datos, "sexo"),
                raza=_campo_texto(datos, "raza"), fecha_nacimiento=_campo_texto(datos, "fecha_nacimiento"),
                madre_tag=_campo_texto(datos, "madre_tag"), padre_tag=_campo_texto(datos, "padre_tag"),
                potrero=_campo_texto(datos, "potrero"), estado=_campo_texto(datos, "estado") or "ACTIVO",
                notas=_campo_texto(datos, "notas"), hierro=_campo_texto(datos, "hierro"),
                chip=_campo_texto(datos, "chip"), color=_campo_texto(datos, "color"),
            )
            return jsonify({"ok": True, "tag": tag})
        except Exception as e:
            logger.exception("Error al crear animal %s: %s", tag, e)
            return _error_interno(500)
        finally:
            try:
                db_a.close()
            except Exception:
                pass

    @app.put("/api/animal/<tag>")
    def api_animal_editar(tag):
        """Edita los datos maestros de un animal existente (nombre, sexo,
        raza, nacimiento, padres, potrero, hierro, chip, color, notas). El
        tag no se puede cambiar aquí (identidad del registro); el estado
        tampoco -- venta/muerte tienen su propio flujo dedicado en Captura y
        no deben editarse a mano para no perder la trazabilidad."""
        if _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"ok": False, "error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403
        datos = request.get_json(silent=True) or {}
        db_a = _db(db_path)
        try:
            if db_a.animal_id(tag) is None:
                return jsonify({"ok": False, "error": f"No existe ningún animal con el tag '{tag}'."}), 404
            db_a.registrar_animal(
                tag,
                nombre=_campo_texto(datos, "nombre"), sexo=_campo_texto(datos, "sexo"),
                raza=_campo_texto(datos, "raza"), fecha_nacimiento=_campo_texto(datos, "fecha_nacimiento"),
                madre_tag=_campo_texto(datos, "madre_tag"), padre_tag=_campo_texto(datos, "padre_tag"),
                potrero=_campo_texto(datos, "potrero"),
                notas=_campo_texto(datos, "notas"), hierro=_campo_texto(datos, "hierro"),
                chip=_campo_texto(datos, "chip"), color=_campo_texto(datos, "color"),
            )
            return jsonify({"ok": True, "tag": tag})
        except Exception as e:
            logger.exception("Error al editar animal %s: %s", tag, e)
            return _error_interno(500)
        finally:
            try:
                db_a.close()
            except Exception:
                pass

    @app.get("/api/animal/<tag>/composicion")
    def api_animal_composicion_get(tag):
        """Devuelve la composición racial y fracciones zootécnicas de un animal."""
        db_a = _db(db_path)
        try:
            from ...engine.genetic_engine import generar_resumen_zootecnico
            aid = db_a.animal_id(tag)
            if aid is None:
                return jsonify({"ok": False, "error": f"No existe animal '{tag}'"}), 404
            comp = db_a.obtener_composicion_racial(aid)
            resumen = generar_resumen_zootecnico(comp)
            return jsonify({
                "ok": True,
                "tag": tag,
                "composicion": comp,
                "resumen": resumen,
            })
        except Exception as e:
            logger.exception("Error al consultar composicion de %s: %s", tag, e)
            return _error_interno(500)
        finally:
            try:
                db_a.close()
            except Exception:
                pass

    @app.post("/api/animal/<tag>/composicion")
    def api_animal_composicion_post(tag):
        """Guarda la composición racial manual (multi-raza con porcentajes) de un animal."""
        if _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"ok": False, "error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403
        datos = request.get_json(silent=True) or {}
        comp_lista = datos.get("composicion") or []
        if not comp_lista:
            return jsonify({"ok": False, "error": "Debe especificar al menos una raza con porcentaje."}), 400

        db_a = _db(db_path)
        try:
            aid = db_a.animal_id(tag)
            if aid is None:
                return jsonify({"ok": False, "error": f"No existe animal '{tag}'"}), 404
            ok = db_a.guardar_composicion_racial(
                aid,
                comp_lista,
                registrado_por=session.get("user_id"),
                actualizar_string_raza=True,
            )
            if not ok:
                return jsonify({"ok": False, "error": "No se pudo guardar la composición. Verifique porcentajes válidos."}), 400
            comp = db_a.obtener_composicion_racial(aid)
            resumen = _generar_resumen_zootecnico(comp)
            return jsonify({
                "ok": True,
                "tag": tag,
                "composicion": comp,
                "resumen": resumen,
                "mensaje": "Composición genética actualizada correctamente.",
            })
        except Exception as e:
            logger.exception("Error al guardar composicion de %s: %s", tag, e)
            return _error_interno(500)
        finally:
            try:
                db_a.close()
            except Exception:
                pass

    @app.post("/api/potrero/<int:pid>/ordeno")
    def api_potrero_ordeno(pid):
        """Marca un potrero como lote de ordeño (true), no ordeño (false) o
        automático (null). Ver engine/lactancia.py."""
        if _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"ok": False, "error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403
        datos = request.get_json(silent=True) or {}
        valor = datos.get("valor")
        if valor not in (True, False, None):
            return jsonify({"ok": False, "error": "valor debe ser true, false o null."}), 400
        db_p = _db(db_path)
        try:
            if not db_p.query_one("SELECT 1 FROM potreros WHERE id = ?", (pid,)):
                return jsonify({"ok": False, "error": "Potrero no encontrado."}), 404
            _lactancia.marcar_potrero_ordeno(db_p, pid, valor)
            _invalidar_tareas()
            return jsonify({"ok": True})
        except Exception:
            logger.exception("Error al marcar potrero de ordeño %s", pid)
            return _error_interno(500)
        finally:
            db_p.close()

    @app.post("/api/animal/<tag>/pausa-ordeno")
    def api_animal_pausa_ordeno(tag):
        """Marca que la vaca <tag> dejó de ordeñarse TEMPORALMENTE (ej. se
        soltó el ternero con la vaca porque nació flaco), sin secarla -- ver
        Database.registrar_pausa_ordeno. Afecta el promedio litros/vaca/día
        del recibo de quincena (Leche), no el estado de lactancia."""
        datos = request.get_json(silent=True) or {}
        db_a = _db(db_path)
        try:
            if db_a.animal_id(tag) is None:
                return jsonify({"ok": False, "error": f"No existe ningún animal con el tag '{tag}'."}), 404
            db_a.registrar_pausa_ordeno(
                tag, fecha_inicio=datos.get("fecha"), motivo=_campo_texto(datos, "motivo"),
                notas=_campo_texto(datos, "notas"), registrado_por=session.get("user_id"),
            )
            return jsonify({"ok": True})
        except Exception as e:
            logger.exception("Error al pausar ordeño de %s: %s", tag, e)
            return _error_interno(500)
        finally:
            try:
                db_a.close()
            except Exception:
                pass

    @app.post("/api/animal/<tag>/reanudar-ordeno")
    def api_animal_reanudar_ordeno(tag):
        """Cierra la pausa de ordeño abierta de la vaca <tag> -- vuelve a
        contarse como vaca que se está ordeñando de verdad."""
        datos = request.get_json(silent=True) or {}
        db_a = _db(db_path)
        try:
            if db_a.animal_id(tag) is None:
                return jsonify({"ok": False, "error": f"No existe ningún animal con el tag '{tag}'."}), 404
            db_a.reanudar_ordeno(tag, fecha_fin=datos.get("fecha"), registrado_por=session.get("user_id"))
            return jsonify({"ok": True})
        except Exception as e:
            logger.exception("Error al reanudar ordeño de %s: %s", tag, e)
            return _error_interno(500)
        finally:
            try:
                db_a.close()
            except Exception:
                pass

    @app.post("/api/animal/rectificar-tag")
    def api_animal_rectificar_tag():
        """Proceso especial para rectificar o corregir el número/chapeta de un animal
        (ej. cuando se leyó mal en campo: JA83 era en realidad JA88).
        RESERVADO EXCLUSIVAMENTE AL PROPIETARIO (OWNER).
        """
        if _rol_actual() != "OWNER":
            return jsonify({
                "ok": False,
                "error": "Acceso denegado. Este proceso especial de rectificación de chapeta está reservado exclusivamente para el Propietario (OWNER)."
            }), 403

        datos = request.get_json(silent=True) or request.form or {}
        tag_actual = (datos.get("tag_actual") or "").strip()
        tag_nuevo = (datos.get("tag_nuevo") or "").strip()
        fusionar = bool(datos.get("fusionar_si_existe"))

        if not tag_actual or not tag_nuevo:
            return jsonify({"ok": False, "error": "Debe especificar 'tag_actual' y 'tag_nuevo'."}), 400

        db_r = _db(db_path)
        try:
            res = db_r.rectificar_tag_animal(
                tag_actual=tag_actual,
                tag_nuevo=tag_nuevo,
                fusionar_si_existe=fusionar,
                usuario_id=session.get("user_id")
            )
            status_code = 200 if res.get("ok") else (409 if res.get("requiere_confirmacion_fusion") else 400)
            return jsonify(res), status_code
        except Exception as e:
            logger.exception("Error al rectificar tag %s -> %s: %s", tag_actual, tag_nuevo, e)
            return _error_interno(500)
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.get("/api/cria-activa")
    def api_cria_activa():
        """Resuelve la cría ACTIVA sin destetar de una vaca, para Captura >
        Destete (el operario busca por el arete de la VACA, no de la cría)."""
        vaca = (request.args.get("vaca") or "").strip()
        if not vaca:
            return jsonify({"encontrada": False, "error": "Falta el parámetro 'vaca'."}), 400
        db_c = _db(db_path)
        try:
            cria = db_c.cria_activa_de_madre(vaca)
            if cria:
                return jsonify({"encontrada": True, "cria_tag": cria["tag"], "fecha_nacimiento": cria.get("fecha_nacimiento")})
            return jsonify({"encontrada": False})
        except Exception:
            logger.exception("Error al resolver cría activa de la vaca %s", vaca)
            return jsonify({"encontrada": False, "error": "Error interno."}), 500
        finally:
            try:
                db_c.close()
            except Exception:
                pass

    @app.get("/api/inventario")
    def api_inventario():
        out = datos_inventario(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/poblacion")
    def api_poblacion():
        out = datos_poblacion(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/genetica")
    def api_genetica():
        out = datos_genetica(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/genetica/simular-cruce")
    def api_genetica_simular_cruce():
        """Simula la composición genética de la cría resultante de cruzar una madre y un padre/pajuela."""
        madre = request.args.get("madre")
        padre = request.args.get("padre")
        if not madre or not padre:
            return jsonify({"ok": False, "error": "Se requieren parámetros 'madre' y 'padre'."}), 400
        db_a = _db(db_path)
        try:
            comp_cria, resumen = db_a.calcular_composicion_cruce_animales(madre, padre)
            return jsonify({
                "ok": True,
                "madre": madre,
                "padre": padre,
                "cria_composicion": comp_cria,
                "cria_resumen": resumen,
            })
        except Exception as e:
            logger.exception("Error al simular cruce genético: %s", e)
            return _error_interno(500)
        finally:
            try:
                db_a.close()
            except Exception:
                pass

    @app.get("/api/genetica/catalogo-razas")
    def api_genetica_catalogo_razas():
        """Devuelve el catálogo de razas predefinidas unificado y normalizado sin duplicados."""
        db_a = _db(db_path)
        try:
            filas = db_a.query("SELECT DISTINCT raza FROM composicion_racial WHERE raza IS NOT NULL AND raza != ''")
            razas_db = []
            for r in filas:
                norm = _normalizar_nombre_raza(r["raza"])
                if norm:
                    razas_db.append(norm)
            filas_an = db_a.query("SELECT DISTINCT raza FROM animales WHERE raza IS NOT NULL AND raza != ''")
            for r in filas_an:
                val = (r["raza"] or "").strip()
                if val and "+" not in val and "%" not in val and "/" not in val:
                    norm = _normalizar_nombre_raza(val)
                    if norm:
                        razas_db.append(norm)
            todas = list(dict.fromkeys(_CATALOGO_RAZAS_PREDEFINIDAS + razas_db))
            todas.sort()
            return jsonify({"ok": True, "razas": todas})
        except Exception:
            return jsonify({"ok": True, "razas": sorted(list(dict.fromkeys(_CATALOGO_RAZAS_PREDEFINIDAS)))})
        finally:
            try:
                db_a.close()
            except Exception:
                pass
