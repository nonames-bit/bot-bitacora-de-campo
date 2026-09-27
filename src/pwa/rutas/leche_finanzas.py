"""Leche, finanzas, mercado y lectura de recibos/facturas.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import os
import re
import time
import uuid
from datetime import date
import logging
from typing import Optional
from flask import jsonify, request, session
from .. import app as _base
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
    _error_interno,
    _es_imagen_valida,
    datos_finanzas,
    datos_leche,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _rol_actual = h._rol_actual
    db_path = ctx.db_path


    @app.get("/api/leche")
    def api_leche():
        out = datos_leche(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/finanzas")
    def api_finanzas():
        if _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        desde = request.args.get("desde") or None
        hasta = request.args.get("hasta") or None
        out = datos_finanzas(db_path, desde=desde, hasta=hasta)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/mercado")
    @app.get("/api/mercado/precios")
    def api_mercado_precios():
        """Indicadores de mercado, precios de subastas ganaderas, leche e insumos."""
        db_m = _db(db_path)
        try:
            # Auto-sincronización transparente si no se ha ejecutado hoy (cero intervención manual)
            from src.integrations.mercado_sync import consultar_titulares_mercado, sincronizar_precios_mercado
            try:
                sincronizar_precios_mercado(db_m, forzar=False)
            except Exception as se:
                logger.warning("Auto-sincronización de mercado omitida por excepción transitoria: %s", se)

            out = db_m.obtener_datos_mercado_completos()
            out["rol"] = _rol_actual()
            try:
                out["noticias_recientes"] = consultar_titulares_mercado()
            except Exception:
                out["noticias_recientes"] = []
            return jsonify(out)
        except Exception:
            logger.exception("Error al consultar precios de mercado")
            return jsonify({"ok": False, "error": "Error interno al consultar precios de mercado"}), 500
        finally:
            try:
                db_m.close()
            except Exception:
                pass

    @app.post("/api/mercado/sincronizar")
    def api_mercado_sincronizar():
        """Fuerza la sincronización automática con fuentes oficiales (ADMIN/OWNER)."""
        rol = _rol_actual()
        if rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"ok": False, "error": "Acceso denegado. Se requiere rol ADMIN u OWNER."}), 403

        db_m = _db(db_path)
        try:
            from src.integrations.mercado_sync import sincronizar_precios_mercado
            res = sincronizar_precios_mercado(db_m, forzar=True)
            return jsonify(res)
        except Exception:
            logger.exception("Error al forzar sincronización de mercado")
            return _error_interno(500)
        finally:
            try:
                db_m.close()
            except Exception:
                pass

    @app.post("/api/mercado/actualizar")
    def api_mercado_actualizar():
        """Actualizar o registrar un precio de subasta o insumo (ADMIN/OWNER)."""
        rol = _rol_actual()
        if rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"ok": False, "error": "Acceso denegado. Se requiere rol ADMIN u OWNER."}), 403

        datos = request.get_json(silent=True) or {}
        plaza = str(datos.get("plaza") or "").strip().upper()
        producto = str(datos.get("producto") or "").strip().upper()
        precio_promedio = datos.get("precio_promedio")
        precio_maximo = datos.get("precio_maximo")
        precio_minimo = datos.get("precio_minimo")
        unidad = datos.get("unidad") or "$/kg"
        fuente = datos.get("fuente") or "MANUAL"
        fecha = datos.get("fecha") or date.today().isoformat()
        notas = datos.get("notas")

        if not plaza or not producto or precio_promedio is None:
            return jsonify({"ok": False, "error": "Campos obligatorios: plaza, producto y precio_promedio."}), 400

        db_m = _db(db_path)
        try:
            id_p = db_m.registrar_precio_mercado(
                plaza=plaza,
                producto=producto,
                precio_promedio=float(precio_promedio),
                precio_maximo=float(precio_maximo) if precio_maximo is not None else None,
                precio_minimo=float(precio_minimo) if precio_minimo is not None else None,
                unidad=unidad,
                fuente=fuente,
                fecha=fecha,
                notas=notas
            )
            return jsonify({"ok": True, "id": id_p, "mensaje": "Precio registrado correctamente."})
        except Exception:
            logger.exception("Error al registrar precio de mercado")
            return _error_interno(500)
        finally:
            try:
                db_m.close()
            except Exception:
                pass

    @app.post("/api/finanzas")
    def api_finanzas_crear():
        if _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"ok": False, "error": "Permisos insuficientes"}), 403
        datos = request.get_json(silent=True) or {}
        fecha = datos.get("fecha") or date.today().isoformat()
        tipo = str(datos.get("tipo") or "").strip().upper()
        categoria = str(datos.get("categoria") or "").strip().upper()
        if tipo not in ("INGRESO", "EGRESO"):
            return jsonify({"ok": False, "error": "El campo 'tipo' debe ser INGRESO o EGRESO."}), 400
        if not categoria:
            return jsonify({"ok": False, "error": "La categoría es obligatoria."}), 400
        try:
            monto = float(datos.get("monto"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "El monto debe ser un número."}), 400
        if monto <= 0:
            return jsonify({"ok": False, "error": "El monto debe ser mayor a 0."}), 400

        uid = session.get("user_id")
        db_f = _db(db_path)
        try:
            foto_ruta = None
            foto_b64 = datos.get("foto_base64")
            animal_tag = (datos.get("animal_tag") or "").strip() or None
            if foto_b64 and isinstance(foto_b64, str):
                try:
                    import base64
                    import uuid

                    if "," in foto_b64:
                        foto_b64 = foto_b64.split(",", 1)[1]
                    raw_bytes = base64.b64decode(foto_b64)
                    if raw_bytes and _es_imagen_valida(raw_bytes):
                        media_dir_abs = (
                            os.path.join(_base.RAIZ_PROYECTO, _base.MEDIA_DIR_DEFAULT)
                            if not os.path.isabs(_base.MEDIA_DIR_DEFAULT) else _base.MEDIA_DIR_DEFAULT
                        )
                        os.makedirs(media_dir_abs, exist_ok=True)
                        ts = int(time.time())
                        rnd = uuid.uuid4().hex[:6]
                        cat_arch = re.sub(r"[^a-z0-9_]", "", categoria.lower())[:40] or "otro"
                        fname = f"gasto_{cat_arch}_{ts}_{rnd}.jpg"
                        with open(os.path.join(media_dir_abs, fname), "wb") as f:
                            f.write(raw_bytes)
                        foto_ruta = os.path.join("media", fname).replace("\\", "/")
                        db_f.registrar_foto(
                            ruta=foto_ruta, animal_tag=animal_tag, fecha=fecha,
                            caption=f"Factura/Recibo: {categoria}",
                            user_id=uid,
                            notas=(datos.get("concepto") or "").strip() or None,
                        )
                except Exception:
                    logger.exception("No se pudo guardar la foto de la factura adjunta")

            fid = db_f.registrar_finanza(
                fecha=fecha, tipo=tipo, categoria=categoria,
                concepto=(datos.get("concepto") or "").strip() or None,
                monto=monto,
                litros=datos.get("litros"),
                animal_tag=animal_tag,
                potrero=(datos.get("potrero") or "").strip() or None,
                contraparte=(datos.get("contraparte") or "").strip() or None,
                foto_ruta=foto_ruta,
                notas=(datos.get("notas") or "").strip() or None,
                registrado_por=uid,
            )
            return jsonify({"ok": True, "id": fid})
        except Exception:
            logger.exception("Error al registrar finanza")
            return _error_interno(400)
        finally:
            db_f.close()

    @app.put("/api/finanzas/<int:id_finanza>")
    def api_finanzas_editar(id_finanza):
        # Edición reservada a OWNER: un movimiento financiero manual editado
        # sin control queda como si nunca se hubiese registrado bien --
        # a diferencia de crear (ADMIN también puede), corregirlo/borrarlo
        # queda solo para el Propietario.
        if _rol_actual() != "OWNER":
            return jsonify({"ok": False, "error": "Acceso denegado. Se requiere rol OWNER (Propietario)."}), 403
        datos = request.get_json(silent=True) or {}
        tipo = datos.get("tipo")
        if tipo is not None:
            tipo = str(tipo).strip().upper()
            if tipo not in ("INGRESO", "EGRESO"):
                return jsonify({"ok": False, "error": "El campo 'tipo' debe ser INGRESO o EGRESO."}), 400
        monto = datos.get("monto")
        if monto is not None:
            try:
                monto = float(monto)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "El monto debe ser un número."}), 400
            if monto <= 0:
                return jsonify({"ok": False, "error": "El monto debe ser mayor a 0."}), 400

        db_f = _db(db_path)
        try:
            ok = db_f.editar_finanza(
                id_finanza,
                fecha=datos.get("fecha"),
                tipo=tipo,
                categoria=(str(datos.get("categoria")).strip().upper() if datos.get("categoria") is not None else None),
                concepto=datos.get("concepto"),
                monto=monto,
                litros=datos.get("litros"),
                animal_tag=datos.get("animal_tag"),
                potrero=datos.get("potrero"),
                contraparte=datos.get("contraparte"),
                notas=datos.get("notas"),
            )
            if not ok:
                return jsonify({"ok": False, "error": f"No existe ningún movimiento con id {id_finanza}."}), 404
            return jsonify({"ok": True})
        except Exception:
            logger.exception("Error al editar finanza")
            return _error_interno(400)
        finally:
            db_f.close()

    @app.delete("/api/finanzas/<int:id_finanza>")
    def api_finanzas_eliminar(id_finanza):
        if _rol_actual() != "OWNER":
            return jsonify({"ok": False, "error": "Acceso denegado. Se requiere rol OWNER (Propietario)."}), 403
        db_f = _db(db_path)
        try:
            ok = db_f.eliminar_finanza(id_finanza)
            if not ok:
                return jsonify({"ok": False, "error": f"No existe ningún movimiento con id {id_finanza}."}), 404
            return jsonify({"ok": True})
        except Exception:
            logger.exception("Error al eliminar finanza")
            return _error_interno(400)
        finally:
            db_f.close()

    def _guardar_foto_recibo_leche(foto_b64: str, periodo: str, fecha_ref: str) -> Optional[str]:
        """Guarda en disco + tabla fotos la imagen del recibo de leche. Devuelve
        la ruta relativa guardada, o None si falla (nunca lanza)."""
        try:
            try:
                from ...vision.recibo_leche_parser import _extraer_bytes_e_imagen
            except (ImportError, ValueError):
                from src.vision.recibo_leche_parser import _extraer_bytes_e_imagen
            raw_bytes, _ = _extraer_bytes_e_imagen(foto_b64)
            if not _es_imagen_valida(raw_bytes):
                logger.warning("Foto de recibo de leche descartada: no es una imagen válida")
                return None
            media_dir_abs = (
                os.path.join(_base.RAIZ_PROYECTO, _base.MEDIA_DIR_DEFAULT)
                if not os.path.isabs(_base.MEDIA_DIR_DEFAULT) else _base.MEDIA_DIR_DEFAULT
            )
            os.makedirs(media_dir_abs, exist_ok=True)
            ts = int(time.time())
            rnd = uuid.uuid4().hex[:6]
            fname = f"recibo_leche_{ts}_{rnd}.jpg"
            with open(os.path.join(media_dir_abs, fname), "wb") as f:
                f.write(raw_bytes)
            ruta_rel = os.path.join("media", fname).replace("\\", "/")
            db_foto = _db(db_path)
            try:
                db_foto.registrar_foto(
                    ruta=ruta_rel, animal_tag=None, fecha=fecha_ref,
                    caption=f"Recibo Quincenal: {periodo}".strip() or "Recibo Quincenal",
                    user_id=session.get("user_id"),
                    notas="Foto guardada al momento de analizar con IA (evidencia del pago).",
                )
            finally:
                db_foto.close()
            return ruta_rel
        except Exception:
            logger.exception("No se pudo guardar la foto del recibo de leche al analizar")
            return None

    @app.post("/api/leche/analizar-recibo")
    def api_leche_analizar_recibo():
        datos = request.get_json(silent=True) or {}
        foto_b64 = datos.get("foto_base64")
        fecha_ref = datos.get("fecha_referencia") or date.today().isoformat()
        if not foto_b64:
            return jsonify({"ok": False, "error": "No se recibió la foto del recibo."}), 400

        try:
            from ...vision.recibo_leche_parser import analizar_recibo_leche
        except (ImportError, ValueError):
            from src.vision.recibo_leche_parser import analizar_recibo_leche

        res = analizar_recibo_leche(foto_b64, fecha_referencia=fecha_ref)
        # La foto se guarda de una vez como evidencia, sin depender de que el
        # usuario termine de revisar y presione "Guardar Quincena" -- si
        # tomó la foto es porque es la prueba del pago, no debería perderse
        # si cierra la pestaña a mitad de camino.
        res["foto_ruta"] = _guardar_foto_recibo_leche(foto_b64, res.get("periodo") or "", fecha_ref)
        return jsonify(res)

    def _guardar_foto_factura(foto_b64: str, concepto: str, fecha_ref: str) -> Optional[str]:
        """Guarda en disco + tabla fotos la imagen de la factura/recibo de
        gasto o ingreso, igual que ``_guardar_foto_recibo_leche``. Devuelve
        la ruta relativa guardada, o None si falla (nunca lanza)."""
        try:
            try:
                from ...vision.recibo_leche_parser import _extraer_bytes_e_imagen
            except (ImportError, ValueError):
                from src.vision.recibo_leche_parser import _extraer_bytes_e_imagen
            raw_bytes, _ = _extraer_bytes_e_imagen(foto_b64)
            if not _es_imagen_valida(raw_bytes):
                logger.warning("Foto de factura descartada: no es una imagen válida")
                return None
            media_dir_abs = (
                os.path.join(_base.RAIZ_PROYECTO, _base.MEDIA_DIR_DEFAULT)
                if not os.path.isabs(_base.MEDIA_DIR_DEFAULT) else _base.MEDIA_DIR_DEFAULT
            )
            os.makedirs(media_dir_abs, exist_ok=True)
            ts = int(time.time())
            rnd = uuid.uuid4().hex[:6]
            fname = f"factura_{ts}_{rnd}.jpg"
            with open(os.path.join(media_dir_abs, fname), "wb") as f:
                f.write(raw_bytes)
            ruta_rel = os.path.join("media", fname).replace("\\", "/")
            db_foto = _db(db_path)
            try:
                db_foto.registrar_foto(
                    ruta=ruta_rel, animal_tag=None, fecha=fecha_ref,
                    caption=f"Factura/Recibo: {concepto}".strip() or "Factura/Recibo",
                    user_id=session.get("user_id"),
                    notas="Foto guardada al momento de analizar con IA (evidencia del gasto/ingreso).",
                )
            finally:
                db_foto.close()
            return ruta_rel
        except Exception:
            logger.exception("No se pudo guardar la foto de la factura al analizar")
            return None

    @app.post("/api/finanzas/analizar-factura")
    def api_finanzas_analizar_factura():
        datos = request.get_json(silent=True) or {}
        foto_b64 = datos.get("foto_base64")
        fecha_ref = datos.get("fecha_referencia") or date.today().isoformat()
        if not foto_b64:
            return jsonify({"ok": False, "error": "No se recibió la foto de la factura."}), 400

        try:
            from ...vision.recibo_gasto_parser import analizar_factura_gasto
        except (ImportError, ValueError):
            from src.vision.recibo_gasto_parser import analizar_factura_gasto

        res = analizar_factura_gasto(foto_b64, fecha_referencia=fecha_ref)
        # Misma razón que el recibo de leche: la foto es la evidencia del
        # gasto/ingreso, se guarda ya mismo sin depender de que termine de
        # revisar el formulario y presione guardar.
        res["foto_ruta"] = _guardar_foto_factura(foto_b64, res.get("concepto") or "", fecha_ref)
        return jsonify(res)

    @app.post("/api/leche/guardar-quincena")
    def api_leche_guardar_quincena():
        datos = request.get_json(silent=True) or {}
        dias = datos.get("dias") or []
        foto_b64 = datos.get("foto_base64")
        foto_ruta_previa = (datos.get("foto_ruta") or "").strip() or None
        observaciones = datos.get("observaciones") or ""
        periodo = datos.get("periodo") or ""
        acopiador = (datos.get("acopiador") or "").strip() or None
        uid = session.get("user_id")

        if not dias or not isinstance(dias, list):
            return jsonify({"ok": False, "error": "No hay días válidos para registrar."}), 400

        db_inst = _db(db_path)
        guardados = 0
        total_l = 0.0
        ingreso_id = None

        try:
            fecha_primer_dia = dias[0].get("fecha") or date.today().isoformat()
            # Si /api/leche/analizar-recibo ya guardó la foto (caso normal:
            # el usuario la analizó con IA antes de llegar aquí), se reusa esa
            # misma ruta en vez de volver a guardarla duplicada. Solo se
            # guarda una foto nueva aquí si llega base64 sin haber pasado por
            # análisis (registro manual con foto adjunta directamente).
            foto_ruta = foto_ruta_previa
            if not foto_ruta and foto_b64:
                foto_ruta = _guardar_foto_recibo_leche(foto_b64, periodo, fecha_primer_dia)

            for d in dias:
                f = d.get("fecha")
                try:
                    litros = round(float(d.get("litros") or 0.0), 1)
                except (TypeError, ValueError):
                    continue
                if not f or litros < 0:
                    continue

                nota_dia = (d.get("notas") or observaciones or "").strip() or None
                existente = db_inst.query_one(
                    "SELECT id FROM produccion_leche WHERE animal_id IS NULL AND fecha = ?", (f,)
                )
                if existente:
                    db_inst.execute(
                        "UPDATE produccion_leche SET litros = ?, notas = ? WHERE id = ?",
                        (litros, nota_dia, existente["id"])
                    )
                else:
                    db_inst.registrar_produccion_leche(
                        fecha=f, litros=litros, notas=nota_dia, registrado_por=uid
                    )
                guardados += 1
                total_l += litros

            # Si el usuario confirmó el monto que le pagaron por esta
            # quincena, se registra de una vez como ingreso en Finanzas
            # (categoría VENTA_LECHE) con la misma foto del recibo como
            # respaldo -- así no hay que volver a digitarlo aparte.
            monto_pagado_raw = datos.get("monto_pagado")
            if monto_pagado_raw not in (None, ""):
                try:
                    monto_pagado = float(monto_pagado_raw)
                except (TypeError, ValueError):
                    monto_pagado = 0.0
                if monto_pagado > 0:
                    fecha_ingreso = max(
                        (d.get("fecha") for d in dias if d.get("fecha")),
                        default=fecha_primer_dia,
                    )
                    ingreso_id = db_inst.registrar_finanza(
                        fecha=fecha_ingreso, tipo="INGRESO", categoria="VENTA_LECHE",
                        concepto=f"Pago quincenal de leche: {periodo}".strip() or "Pago quincenal de leche",
                        monto=monto_pagado, litros=round(total_l, 1),
                        contraparte=acopiador, foto_ruta=foto_ruta,
                        notas=observaciones or None, registrado_por=uid,
                    )

            return jsonify({
                "ok": True,
                "guardados": guardados,
                "total_litros": round(total_l, 1),
                "periodo": periodo,
                "foto_ruta": foto_ruta,
                "ingreso_id": ingreso_id,
            })
        except Exception as e:
            logger.exception("Error al guardar quincena de leche: %s", e)
            return _error_interno(500)
        finally:
            try:
                db_inst.close()
            except Exception:
                pass
