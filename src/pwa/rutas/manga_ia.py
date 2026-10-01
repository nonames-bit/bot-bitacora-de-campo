"""Traslado masivo, manga (pesaje/tratamiento en lote), preguntas, voz y reportes PDF/XLSX.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import os
from datetime import date
import logging
from flask import abort, jsonify, request, send_file, session
from .. import app as _base
from ...engine import revision as _revision
from ...utils import to_date
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
    _error_interno,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def _potrero_real(db_t, nombre: str):
    """Potrero "real" (con geometría georreferenciada) por nombre o código --
    los códigos numéricos legacy de SG sin mapa no cuentan como ubicación."""
    return db_t.query_one(
        "SELECT id, nombre FROM potreros WHERE geom_wkt_4326 IS NOT NULL AND (nombre = ? OR codigo = ?)",
        (nombre, nombre),
    )


def _ejecutar_traslado_masivo(db_t, nombre_origen, nombre_destino, fecha, motivo, uid, solo_validar=False):
    """Mueve todos los animales activos de un potrero a otro. Devuelve
    (ok, cuerpo_json, código_http). Lo usa /api/traslado/masivo y la
    aprobación de un traslado masivo que quedó por revisar."""
    fila_origen = _potrero_real(db_t, nombre_origen)
    fila_destino = _potrero_real(db_t, nombre_destino)
    if not fila_origen:
        return False, {"ok": False, "error": f"'{nombre_origen}' no es un potrero real (sin mapa/geometría) o no existe."}, 404
    if not fila_destino:
        return False, {"ok": False, "error": f"'{nombre_destino}' no es un potrero real (sin mapa/geometría) o no existe."}, 404
    if solo_validar:
        return True, {"ok": True}, 200
    tags = db_t.animales_activos_en_potrero(fila_origen["id"])
    for tag in tags:
        db_t.registrar_traslado(
            animal_tag=tag, fecha=fecha,
            potrero_origen=fila_origen["id"], potrero_destino=fila_destino["id"],
            motivo=motivo, registrado_por=uid,
        )
    return True, {
        "ok": True, "movidos": len(tags), "animales": tags,
        "potrero_origen": fila_origen["nombre"], "potrero_destino": fila_destino["nombre"],
    }, 200


def registrar(app, ctx, h):
    _limite_api = h._limite_api
    _rol_actual = h._rol_actual
    db_path = ctx.db_path
    h._ejecutar_traslado_masivo = _ejecutar_traslado_masivo

    @app.post("/api/traslado/masivo")
    def api_traslado_masivo():
        # Mover TODOS los animales activos de un potrero a otro de una sola
        # vez (rotación Voisin completa del lote), en vez de tener que
        # escribir arete por arete. Solo potreros "reales" (con geometría
        # georreferenciada) -- los códigos numéricos legacy de SG sin mapa no
        # cuentan como ubicación real para este flujo.
        datos = request.get_json(silent=True) or {}
        nombre_origen = (datos.get("potrero_origen") or "").strip()
        nombre_destino = (datos.get("potrero_destino") or "").strip()
        fecha = datos.get("fecha") or date.today().isoformat()
        motivo = (datos.get("motivo") or "").strip() or None
        if not nombre_origen or not nombre_destino:
            return jsonify({"ok": False, "error": "Potrero Origen y Potrero Destino son obligatorios."}), 400
        if nombre_origen.strip().upper() == nombre_destino.strip().upper():
            return jsonify({"ok": False, "error": "El potrero de origen y el de destino no pueden ser el mismo."}), 400

        db_t = _db(db_path)
        try:
            if _revision.requiere_revision(_rol_actual(), "traslado_masivo"):
                # Un trabajador no mueve el lote de una: queda por revisar.
                datos_rev = {"potrero_origen": nombre_origen, "potrero_destino": nombre_destino, "motivo": motivo}
                valido, cuerpo, codigo = _ejecutar_traslado_masivo(db_t, nombre_origen, nombre_destino, fecha,
                                                                   motivo, None, solo_validar=True)
                if not valido:
                    return jsonify(cuerpo), codigo
                _revision.poner_en_revision(
                    db_t, origen="app", tipo="traslado_masivo", datos=datos_rev, fecha=fecha,
                    registrado_por=session.get("user_id"), registrado_por_nombre=session.get("nombre"),
                    canal="App", users_file=ctx.users_file,
                )
                return jsonify({"ok": True, "en_revision": True, "movidos": 0,
                                "potrero_origen": nombre_origen, "potrero_destino": nombre_destino})
            _, cuerpo, codigo = _ejecutar_traslado_masivo(db_t, nombre_origen, nombre_destino, fecha,
                                                          motivo, session.get("user_id"))
            return jsonify(cuerpo), codigo
        except Exception:
            logger.exception("Error en traslado masivo por potrero")
            return _error_interno(400)
        finally:
            db_t.close()

    @app.post("/api/manga/pesaje")
    def api_manga_pesaje():
        datos = request.get_json(silent=True) or request.form
        tag = (datos.get("tag") or "").strip()
        peso_raw = datos.get("peso_kg")
        evento = datos.get("evento") or "PESAJE"
        if not tag or peso_raw is None:
            return jsonify({"error": "Tag y peso_kg son obligatorios."}), 400
        try:
            peso_kg = float(peso_raw)
        except (ValueError, TypeError):
            return jsonify({"error": "peso_kg debe ser un número."}), 400

        db_m = _db(db_path)
        try:
            aid = db_m.resolve_animal(tag, crear=True)
            ult_pesaje = db_m.query_one(
                "SELECT peso_kg, fecha FROM pesajes WHERE animal_id = ? ORDER BY fecha DESC, id DESC LIMIT 1",
                (aid,),
            )
            hoy_iso = date.today().isoformat()
            gmd_val = None
            dias_dif = None
            ult_peso = None

            if ult_pesaje and ult_pesaje["peso_kg"] is not None and ult_pesaje["fecha"]:
                ult_peso = float(ult_pesaje["peso_kg"])
                d_ult = to_date(ult_pesaje["fecha"])
                d_hoy = date.today()
                if d_ult and d_ult < d_hoy:
                    dias_dif = (d_hoy - d_ult).days
                    if dias_dif > 0:
                        gmd_val = round(((peso_kg - ult_peso) / dias_dif) * 1000.0, 1)

            pid = db_m.registrar_pesaje(
                animal_tag=tag,
                fecha=hoy_iso,
                peso_kg=peso_kg,
                gmd_calculada=gmd_val,
                evento=evento,
                registrado_por=session.get("user_id"),
            )
            return jsonify({
                "ok": True,
                "pesaje_id": pid,
                "tag": tag,
                "peso_kg": peso_kg,
                "peso_anterior": ult_peso,
                "dias_entre_pesajes": dias_dif,
                "gmd_g_dia": gmd_val,
            })
        finally:
            db_m.close()

    @app.post("/api/manga/tratamiento_lote")
    def api_manga_tratamiento_lote():
        datos = request.get_json(silent=True) or {}
        tags = datos.get("tags") or []
        producto = (datos.get("producto") or "").strip()
        principio = (datos.get("principio_activo") or "").strip() or None
        dosis = (datos.get("dosis") or "").strip() or None
        via = (datos.get("via") or "").strip() or None
        d_leche = int(datos.get("dias_retiro_leche") or 0)
        d_carne = int(datos.get("dias_retiro_carne") or 0)
        diagnostico = (datos.get("diagnostico") or "").strip() or None

        potrero = (datos.get("potrero") or "").strip()

        db_t = _db(db_path)
        if not tags and potrero:
            try:
                # Potrero vigente (último traslado): misma fuente que Inventario.
                pid_p = db_t.potrero_id(potrero)
                tags = db_t.animales_activos_en_potrero(pid_p) if pid_p is not None else []
            except Exception as e:
                logger.warning("Fallo al buscar animales de potrero %s: %s", potrero, e)

        if not tags or not producto:
            db_t.close()
            return jsonify({"error": "Debe enviar 'tags' o 'potrero' con animales activos, y 'producto'."}), 400

        hoy_iso = date.today().isoformat()
        procesados = 0
        uid = session.get("user_id")

        try:
            for t in tags:
                try:
                    db_t.registrar_tratamiento(
                        animal_tag=str(t).strip(),
                        fecha=hoy_iso,
                        producto=producto,
                        principio_activo=principio,
                        dosis=dosis,
                        via=via,
                        dias_retiro_leche=d_leche,
                        dias_retiro_carne=d_carne,
                        diagnostico=diagnostico,
                        registrado_por=uid,
                    )
                    procesados += 1
                except Exception as e:
                    logger.warning("Fallo al aplicar tratamiento lote a %s: %s", t, e)
            return jsonify({"ok": True, "procesados": procesados, "total": len(tags)})
        finally:
            db_t.close()

    @app.post("/api/preguntar")
    def api_preguntar():
        datos = request.get_json(silent=True) or request.form
        pregunta = (datos.get("pregunta") or "").strip()
        if not pregunta:
            return jsonify({"error": "Debe enviar 'pregunta'."}), 400

        db_q = _db(db_path)
        try:
            try:
                from ...engine.query_engine import QueryEngine
            except ImportError:
                from src.engine.query_engine import QueryEngine  # type: ignore
            qe = QueryEngine(db_q)
            respuesta = qe.responder(pregunta)
            return jsonify({"ok": True, "pregunta": pregunta, "respuesta": respuesta})
        except Exception as e:
            logger.exception("Error al responder pregunta en PWA: %s", e)
            return _error_interno(500)
        finally:
            db_q.close()

    @app.post("/api/voz")
    @_limite_api("voz")
    def api_voz():
        audio_file = request.files.get("audio") if request.files else None
        if not audio_file or not audio_file.filename:
            return jsonify({"error": "Debe enviar un archivo en 'audio'."}), 400

        import tempfile
        ext = os.path.splitext(audio_file.filename)[1] or ".webm"
        tmp_audio = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                f.write(audio_file.read())
                tmp_audio = f.name

            try:
                try:
                    from ...parsers.media_handler import transcribe_audio
                except ImportError:
                    from src.parsers.media_handler import transcribe_audio  # type: ignore
                tr = transcribe_audio(tmp_audio)
                texto_transcripto = tr.texto if tr else ""
            except Exception as e:
                logger.warning("Fallo en transcripción Whisper: %s", e)
                return _error_interno(500)

            if not texto_transcripto:
                return jsonify({"ok": False, "error": "No se detectó voz clara en el audio."})

            db_v = _db(db_path)
            try:
                try:
                    from ...bot.bot_interface import Bot
                except ImportError:
                    from src.bot.bot_interface import Bot  # type: ignore
                bot_inst = Bot(db_v)
                respuesta = bot_inst.procesar_texto(
                    texto_transcripto, user_id=session.get("user_id"), rol=_rol_actual(),
                    nombre=session.get("nombre"), canal="App", users_file=ctx.users_file,
                )
                return jsonify({
                    "ok": True,
                    "transcripcion": texto_transcripto,
                    "respuesta": respuesta,
                })
            finally:
                db_v.close()
        finally:
            if tmp_audio and os.path.isfile(tmp_audio):
                try:
                    os.remove(tmp_audio)
                except Exception:
                    pass

    @app.get("/api/reporte.pdf")
    def api_reporte_pdf():
        if _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"error": "Se requiere rol ADMIN u OWNER para descargar reportes PDF."}), 403

        import time
        seccion = request.args.get("seccion")
        periodo = request.args.get("periodo") or "semanal"
        p_lower = str(periodo).lower().strip()
        dias = 7
        if p_lower in ("semanal", "7", "7d"):
            dias = 7
        elif p_lower in ("quincenal", "15", "15d"):
            dias = 15
        elif p_lower in ("mensual", "30", "30d"):
            dias = 30
        elif p_lower.isdigit():
            dias = max(1, int(p_lower))

        os.makedirs(_base.REPORTES_DIR_DEFAULT, exist_ok=True)
        sec_sufijo = f"_{seccion}" if seccion else ""
        ruta_salida = os.path.join(_base.REPORTES_DIR_DEFAULT, f"reporte_ja{sec_sufijo}_{periodo}_{int(time.time())}.pdf")

        db_rep = _db(db_path)
        try:
            try:
                from ...reports.pdf_report import generar_pdf
            except ImportError:
                from src.reports.pdf_report import generar_pdf  # type: ignore
            ruta = generar_pdf(db_rep, dias=dias, ruta_salida=ruta_salida, periodo=periodo, seccion=seccion)
            if not ruta or not os.path.isfile(ruta):
                abort(500)
            nombre_descarga = f"reporte_ganaderia_ja{sec_sufijo}_{periodo}.pdf"
            return send_file(os.path.abspath(ruta), mimetype="application/pdf",
                             as_attachment=True, download_name=nombre_descarga)
        except Exception as e:
            logger.exception("Error al generar reporte PDF en PWA: %s", e)
            abort(500)
        finally:
            db_rep.close()

    @app.get("/api/reporte.xlsx")
    def api_reporte_xlsx():
        if _rol_actual() not in ("OWNER", "ADMIN"):
            return jsonify({"error": "Se requiere rol ADMIN u OWNER para exportar datos en Excel."}), 403

        import io
        seccion = request.args.get("seccion") or "inventario"
        dias_arg = request.args.get("dias")
        dias = int(dias_arg) if (dias_arg and str(dias_arg).isdigit()) else 90

        db_rep = _db(db_path)
        try:
            try:
                from ...reports.excel_report import exportar_excel_bytes
            except ImportError:
                from src.reports.excel_report import exportar_excel_bytes  # type: ignore
            contenido_xlsx = exportar_excel_bytes(db_rep, seccion=seccion, dias=dias)
            nombre_descarga = f"reporte_{seccion}_ganaderia_ja.xlsx"
            return send_file(
                io.BytesIO(contenido_xlsx),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=nombre_descarga,
            )
        except Exception as e:
            logger.exception("Error al generar reporte Excel en PWA: %s", e)
            return _error_interno(500, con_ok=False)
        finally:
            db_rep.close()
