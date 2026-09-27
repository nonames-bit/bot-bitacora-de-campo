"""Notificaciones push, ficha PDF/QR, gráficos y archivos de media.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import os
import re
import shutil
import time
import logging
from flask import abort, jsonify, request, send_file, send_from_directory, session
from .. import app as _base
from ...engine.dashboard_data import datos_grafico as _datos_grafico
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    CACHE_GRAFICOS_SEGUNDOS,
    _db,
    _generadores_graficos_ficha,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _limite_api = h._limite_api
    _rol_actual = h._rol_actual
    db_path = ctx.db_path

    @app.post("/api/push/suscribir")
    def api_push_suscribir():
        """Registra una suscripción de navegador para notificaciones Web Push."""
        datos = request.get_json(silent=True) or {}
        endpoint = str(datos.get("endpoint") or "").strip()
        if not endpoint:
            return jsonify({"ok": False, "error": "Endpoint requerido."}), 400
        keys = datos.get("keys") or {}
        p256dh = str(keys.get("p256dh") or "").strip() or None
        auth_key = str(keys.get("auth") or "").strip() or None
        uid = session.get("user_id")

        db_p = _db(db_path)
        try:
            sid = db_p.guardar_push_suscripcion(endpoint, user_id=uid, p256dh=p256dh, auth=auth_key)
            return jsonify({"ok": True, "suscripcion_id": sid})
        finally:
            db_p.close()

    @app.post("/api/push/desuscribir")
    def api_push_desuscribir():
        """Elimina una suscripción de notificaciones Web Push."""
        datos = request.get_json(silent=True) or {}
        endpoint = str(datos.get("endpoint") or "").strip()
        if not endpoint:
            return jsonify({"ok": False, "error": "Endpoint requerido."}), 400
        db_p = _db(db_path)
        try:
            ok = db_p.eliminar_push_suscripcion(endpoint)
            return jsonify({"ok": ok})
        finally:
            db_p.close()

    @app.get("/api/push/vapid-key")
    def api_push_vapid_key():
        """Llave pública VAPID para reg.pushManager.subscribe() en el navegador.

        Sin esto el frontend no puede crear una suscripción real -- antes de
        esta ruta, iniciarWebPush() nunca llamaba a subscribe() (no tenía con
        qué), solo guardaba un endpoint local de relleno."""
        return jsonify({"publicKey": os.getenv("VAPID_PUBLIC_KEY") or ""})

    @app.get("/api/push/alertas")
    def api_push_alertas():
        """Retorna alertas activas de alta prioridad para notificación en campo."""
        db_p = _db(db_path)
        try:
            alertas = db_p.alertas_pendientes_push()
            return jsonify({"ok": True, "alertas": alertas, "total": len(alertas)})
        finally:
            db_p.close()

    @app.post("/api/push/probar")
    def api_push_probar():
        """Genera un aviso de prueba para verificar el funcionamiento en el celular."""
        return jsonify({
            "ok": True,
            "notificacion": {
                "titulo": "🔔 Notificación Bitácora JA",
                "cuerpo": "¡Prueba exitosa! Las notificaciones nativas de campo están activas en tu celular.",
                "tag": "prueba-pwa",
                "icono": "/static/icon-192.png",
                "url": "/",
            }
        })



    @app.get("/api/ficha/<tag>/qr.pdf")
    @app.get("/api/ficha/<tag>/pdf")
    @app.get("/ficha/<tag>/pdf")
    def api_ficha_qr_pdf(tag):
        # Exporta la tarjeta QR del animal como PDF (botón "Descargar QR").
        from urllib.parse import unquote
        db_pdf = _db(db_path)
        try:
            try:
                from ...reports.qr_fichas import generar_ficha_qr_individual
            except ImportError:  # ejecución directa
                from src.reports.qr_fichas import generar_ficha_qr_individual  # type: ignore
            # URL pública para imprimir en la tarjeta: la de la propia petición.
            try:
                base_url = request.host_url.rstrip("/")
            except Exception:
                base_url = ""
            tag_clean = unquote(str(tag or "")).strip()
            ruta = generar_ficha_qr_individual(
                db_pdf, tag_clean, media_dir=_base.MEDIA_DIR_DEFAULT, base_url=base_url,
            )
            if not ruta or not os.path.isfile(ruta):
                abort(404)
            tag_safe = re.sub(r"[^A-Za-z0-9_-]+", "_", tag_clean) or "animal"
            return send_file(os.path.abspath(ruta), mimetype="application/pdf",
                             as_attachment=True, download_name=f"ficha_qr_{tag_safe}.pdf")
        except ValueError as e:
            logger.warning("qr.pdf no encontrado para %s: %s", tag, e)
            abort(404)
        except Exception:
            logger.exception("error generando qr.pdf para %s", tag)
            abort(500)
        finally:
            try:
                db_pdf.close()
            except Exception:
                pass

    @app.get("/api/ficha/<tag>/grafico/<tipo>")
    def api_ficha_grafico(tag, tipo):
        # Gráfico por animal (curva de peso, lactancia) con caché por tag+tipo.
        generadores = _generadores_graficos_ficha()
        generador = generadores.get(tipo)
        if generador is None:
            abort(404)
        db_graf = _db(db_path)
        try:
            aid = db_graf.resolve_animal(tag, crear=False)
            if aid is None:
                abort(404)
            cache_path = os.path.join(_base.REPORTES_DIR_DEFAULT,
                                      f"_pwa_cache_ficha_{aid}_{tipo}.png")
            try:
                fresco = (
                    os.path.isfile(cache_path)
                    and (time.time() - os.path.getmtime(cache_path)) < CACHE_GRAFICOS_SEGUNDOS
                )
            except Exception:
                fresco = False
            if fresco:
                return send_file(os.path.abspath(cache_path), mimetype="image/png")
            try:
                from ...engine.charts import graficos_disponibles
            except ImportError:  # ejecución directa
                from src.engine.charts import graficos_disponibles  # type: ignore
            if not graficos_disponibles():
                abort(404)
            ruta = generador(db_graf, tag, output_dir=_base.REPORTES_DIR_DEFAULT)
            if not ruta or not os.path.isfile(ruta):
                abort(404)
            try:
                shutil.copyfile(ruta, cache_path)
            except Exception:
                cache_path = ruta
            return send_file(os.path.abspath(cache_path), mimetype="image/png")
        finally:
            db_graf.close()

    @app.get("/api/grafico/<tipo>")
    @_limite_api("grafico")
    def api_grafico(tipo):
        generadores = _base._generadores_graficos_pwa()
        generador = generadores.get(tipo)
        if generador is None:
            abort(404)

        # Caché por tipo (independiente del nombre de archivo que use cada
        # generador internamente): si ya hay una copia servida hace menos
        # de CACHE_GRAFICOS_SEGUNDOS, se devuelve sin volver a renderizar.
        cache_path = os.path.join(_base.REPORTES_DIR_DEFAULT, f"_pwa_cache_{tipo}.png")
        try:
            fresco = (
                os.path.isfile(cache_path)
                and (time.time() - os.path.getmtime(cache_path)) < CACHE_GRAFICOS_SEGUNDOS
            )
        except Exception:
            fresco = False
        if fresco:
            return send_file(os.path.abspath(cache_path), mimetype="image/png")

        try:
            from ...engine.charts import graficos_disponibles
        except ImportError:  # ejecución directa: python src/pwa/app.py
            from src.engine.charts import graficos_disponibles  # type: ignore

        if not graficos_disponibles():
            abort(404)
        db_graf = _db(db_path)
        try:
            ruta = generador(db_graf, output_dir=_base.REPORTES_DIR_DEFAULT)
        finally:
            db_graf.close()
        if not ruta or not os.path.isfile(ruta):
            abort(404)
        try:
            shutil.copyfile(ruta, cache_path)
        except Exception:
            cache_path = ruta  # si falla la copia, se sirve igual el original
        return send_file(os.path.abspath(cache_path), mimetype="image/png")

    @app.get("/api/grafico-datos/<tipo>")
    @_limite_api("grafico")
    def api_grafico_datos(tipo):
        """Devuelve los datos estructurados JSON de un gráfico para renderizado
        vectorial SVG/HTML interactivo adaptado a los temas en el cliente."""
        db_graf = _db(db_path)
        try:
            datos = _datos_grafico(db_graf, tipo)
        finally:
            db_graf.close()
        if "error" in datos:
            return jsonify(datos), 404
        return jsonify(datos)

    @app.get("/media/<path:rel>")
    def media(rel):
        # send_from_directory ya previene path traversal (rechaza "..").
        # Soportes financieros (facturas, recibos de leche, gastos) solo para
        # OWNER/ADMIN: son evidencia de pagos y no se muestran a roles de campo.
        nombre_arch = os.path.basename(rel).lower()
        if nombre_arch.startswith(("gasto_", "factura_", "recibo_leche_")) and _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"error": "Permisos insuficientes"}), 403
        media_root = os.path.join(_base.RAIZ_PROYECTO, _base.MEDIA_DIR_DEFAULT)
        return send_from_directory(media_root, rel)
