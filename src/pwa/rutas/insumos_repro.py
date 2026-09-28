"""Pajuelas, termo de nitrógeno, inseminadores e IATF.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import logging
from flask import jsonify, request, session
from ...engine.dashboard_data import _filas_dict
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
    _error_interno,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _rol_actual = h._rol_actual
    db_path = ctx.db_path

    @app.get("/api/pajuelas")
    @app.get("/api/pajillas")
    def api_pajuelas():
        db_inst = _db(db_path)
        try:
            pajuelas = _filas_dict(db_inst.listar_pajuelas(solo_activas=True))
            pajuelas_inactivas = _filas_dict(db_inst.listar_pajuelas_inactivas())
            alertas = _filas_dict(db_inst.alertas_stock_pajuelas(3))
            termo = db_inst.ultimo_estado_termo()
            return jsonify({
                "ok": True,
                "pajuelas": pajuelas,
                "pajillas": pajuelas,
                "pajuelas_inactivas": pajuelas_inactivas,
                "pajillas_inactivas": pajuelas_inactivas,
                "inactivas": pajuelas_inactivas,
                "alertas_stock": alertas,
                "termo": termo,
                "total_pajuelas": sum(p.get("cantidad", 0) for p in pajuelas),
                "total_pajillas": sum(p.get("cantidad", 0) for p in pajuelas),
                "total_toros": len(pajuelas),
            })
        finally:
            db_inst.close()

    @app.post("/api/pajuelas")
    @app.post("/api/pajillas")
    def api_pajuelas_crear():
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO", "TRABAJADOR"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        data = request.get_json(silent=True) or {}
        toro = (data.get("codigo_toro") or data.get("toro") or "").strip()
        if not toro:
            return jsonify({"error": "Código de toro requerido"}), 400
        db_inst = _db(db_path)
        try:
            pid = db_inst.registrar_pajuela(
                codigo_toro=toro,
                raza=data.get("raza"),
                procedencia=data.get("procedencia"),
                canastilla=data.get("canastilla"),
                cantidad=int(data.get("cantidad") or 1),
                costo=float(data.get("costo") or 0.0),
                fecha_ingreso=data.get("fecha") or data.get("fecha_ingreso"),
            )
            return jsonify({"ok": True, "id": pid})
        except Exception:
            logger.exception("Error al registrar pajuela")
            return _error_interno(500, con_ok=False)
        finally:
            db_inst.close()

    @app.post("/api/pajuelas/estado")
    @app.post("/api/pajillas/estado")
    def api_pajuelas_estado():
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO", "TRABAJADOR"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        data = request.get_json(silent=True) or {}
        pid = data.get("id") or data.get("codigo_toro")
        nuevo_estado = data.get("estado", "INACTIVO")
        if not pid:
            return jsonify({"error": "id o codigo_toro requerido"}), 400
        db_inst = _db(db_path)
        try:
            ok = db_inst.actualizar_estado_pajuela(pid, nuevo_estado)
            return jsonify({"ok": ok, "estado": nuevo_estado})
        except Exception:
            logger.exception("Error al cambiar estado de pajilla")
            return _error_interno(500, con_ok=False)
        finally:
            db_inst.close()

    @app.get("/api/termo-nitrogeno")
    def api_termo_nitrogeno():
        db_inst = _db(db_path)
        try:
            estado = db_inst.ultimo_estado_termo()
            recargas = _filas_dict(db_inst.listar_recargas_nitrogeno(10))
            return jsonify({"ok": True, "termo": estado, "recargas": recargas})
        finally:
            db_inst.close()

    @app.post("/api/termo-nitrogeno/recarga")
    def api_termo_recarga():
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        data = request.get_json(silent=True) or {}
        db_inst = _db(db_path)
        try:
            rid = db_inst.registrar_recarga_nitrogeno(
                fecha_recarga=data.get("fecha") or data.get("fecha_recarga"),
                dias_intervalo=int(data.get("dias_intervalo") or 21),
                proxima_recarga=data.get("proxima_recarga"),
            )
            return jsonify({"ok": True, "id": rid})
        except Exception:
            logger.exception("Error al registrar recarga de nitrógeno")
            return _error_interno(400, con_ok=False)
        finally:
            db_inst.close()

    @app.get("/api/inseminadores")
    def api_inseminadores():
        db_inst = _db(db_path)
        try:
            inseminadores = [dict(i) for i in db_inst.listar_inseminadores()]
            evaluacion = db_inst.evaluar_inseminadores()
            return jsonify({"ok": True, "inseminadores": inseminadores, "evaluacion": evaluacion})
        except Exception:
            logger.exception("Error al listar inseminadores")
            return _error_interno(500)
        finally:
            db_inst.close()

    @app.post("/api/inseminadores")
    def api_inseminadores_crear():
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        if not nombre:
            return jsonify({"ok": False, "error": "El nombre del inseminador es obligatorio"}), 400
        db_inst = _db(db_path)
        try:
            iid = db_inst.registrar_inseminador(
                nombre=nombre,
                telefono=data.get("telefono"),
                es_usuario_sistema=bool(data.get("es_usuario_sistema")),
                user_id=data.get("user_id"),
                notas=data.get("notas"),
            )
            return jsonify({"ok": True, "id": iid})
        except Exception:
            logger.exception("Error al registrar inseminador")
            return _error_interno(400)
        finally:
            db_inst.close()

    @app.get("/api/iatf/protocolos")
    def api_iatf_protocolos():
        db_inst = _db(db_path)
        try:
            protocolos = db_inst.listar_protocolos_iatf()
            return jsonify({"ok": True, "protocolos": protocolos})
        except Exception:
            logger.exception("Error al listar protocolos IATF")
            return _error_interno(500)
        finally:
            db_inst.close()

    @app.get("/api/iatf/lotes")
    def api_iatf_lotes():
        estado = request.args.get("estado")
        db_inst = _db(db_path)
        try:
            lotes = db_inst.listar_lotes_iatf(estado=estado)
            metricas = db_inst.evaluar_metricas_iatf()
            return jsonify({"ok": True, "lotes": lotes, "metricas": metricas})
        except Exception:
            logger.exception("Error al listar lotes IATF")
            return _error_interno(500)
        finally:
            db_inst.close()

    @app.get("/api/iatf/lotes/<int:lote_id>")
    def api_iatf_lote_detalle(lote_id):
        db_inst = _db(db_path)
        try:
            lote = db_inst.obtener_detalle_lote_iatf(lote_id)
            if not lote:
                return jsonify({"ok": False, "error": "Lote IATF no encontrado"}), 404
            return jsonify({"ok": True, "lote": lote})
        except Exception:
            logger.exception("Error al obtener detalle del lote IATF %s", lote_id)
            return _error_interno(500)
        finally:
            db_inst.close()

    @app.post("/api/iatf/lotes")
    def api_iatf_lotes_crear():
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        protocolo_id = data.get("protocolo_id")
        fecha_inicio = data.get("fecha_inicio") or data.get("fecha")
        animales_tags = data.get("animales_tags") or data.get("tags") or []

        if not nombre or not protocolo_id or not fecha_inicio or not animales_tags:
            return jsonify({
                "ok": False,
                "error": "Nombre, protocolo, fecha de inicio y lista de animales son obligatorios"
            }), 400

        if isinstance(animales_tags, str):
            animales_tags = [t.strip().upper() for t in animales_tags.replace(",", " ").split() if t.strip()]

        db_inst = _db(db_path)
        try:
            uid = session.get("user_id")
            lid = db_inst.crear_lote_iatf(
                nombre=nombre,
                protocolo_id=int(protocolo_id),
                fecha_inicio=str(fecha_inicio)[:10],
                animales_tags=animales_tags,
                toro_pajuela=data.get("toro_pajuela") or data.get("toro"),
                inseminador=data.get("inseminador"),
                hora_iatf=data.get("hora_iatf") or "08:00",
                categoria=data.get("categoria"),
                notas=data.get("notas"),
                creado_por=uid,
            )
            return jsonify({"ok": True, "id": lid})
        except Exception as e:
            logger.exception("Error al crear lote IATF")
            return jsonify({"ok": False, "error": str(e)}), 400
        finally:
            db_inst.close()

    @app.post("/api/iatf/lotes/<int:lote_id>/paso")
    def api_iatf_lote_paso(lote_id):
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        data = request.get_json(silent=True) or {}
        paso_index = data.get("paso_index")
        if paso_index is None:
            return jsonify({"ok": False, "error": "Índice de paso requerido"}), 400
        db_inst = _db(db_path)
        try:
            uid = session.get("user_id")
            u_nom = session.get("nombre") or session.get("username") or str(uid or "")
            ok = db_inst.registrar_avance_paso_iatf(
                lote_id=lote_id,
                paso_index=int(paso_index),
                producto_aplicado=data.get("producto") or data.get("producto_aplicado"),
                dosis=data.get("dosis"),
                marca=data.get("marca"),
                realizado_por=data.get("realizado_por") or u_nom,
                notas=data.get("notas"),
            )
            return jsonify({"ok": ok})
        except Exception as e:
            logger.exception("Error al avanzar paso IATF en lote %s", lote_id)
            return jsonify({"ok": False, "error": str(e)}), 400
        finally:
            db_inst.close()

    @app.post("/api/iatf/lotes/<int:lote_id>/inseminar")
    def api_iatf_lote_inseminar(lote_id):
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        data = request.get_json(silent=True) or {}
        db_inst = _db(db_path)
        try:
            res = db_inst.ejecutar_inseminacion_lote_iatf(
                lote_id=lote_id,
                toro_pajuela=data.get("toro_pajuela") or data.get("toro"),
                inseminador=data.get("inseminador"),
                fecha=data.get("fecha"),
                hora=data.get("hora"),
            )
            return jsonify({"ok": True, "resultado": res})
        except Exception as e:
            logger.exception("Error al ejecutar inseminación de lote IATF %s", lote_id)
            return jsonify({"ok": False, "error": str(e)}), 400
        finally:
            db_inst.close()

    @app.post("/api/iatf/lotes/<int:lote_id>/excluir")
    def api_iatf_lote_excluir(lote_id):
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        data = request.get_json(silent=True) or {}
        tag = (data.get("tag") or "").strip().upper()
        motivo = (data.get("motivo") or "Exclusión operativa").strip()
        if not tag:
            return jsonify({"ok": False, "error": "Tag del animal requerido"}), 400
        db_inst = _db(db_path)
        try:
            ok = db_inst.excluir_animal_lote_iatf(lote_id=lote_id, tag=tag, motivo=motivo)
            return jsonify({"ok": ok})
        except Exception as e:
            logger.exception("Error al excluir animal de lote IATF")
            return jsonify({"ok": False, "error": str(e)}), 400
        finally:
            db_inst.close()
