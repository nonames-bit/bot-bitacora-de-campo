"""Vistas de campo: tablero, reproducción, carne, sanidad, pasturas, potreros y satélite.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import os
from datetime import date
import logging
from flask import jsonify, request, session
from .. import app as _base
from ...utils import to_date
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
    _error_interno,
    datos_carne,
    datos_pasturas,
    datos_repro,
    datos_sanidad,
    datos_tablero,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _limite_api = h._limite_api
    _rol_actual = h._rol_actual
    db_path = ctx.db_path

    @app.get("/api/tablero")
    def api_tablero():
        pot = (request.args.get("potrero") or "").strip() or None
        out = datos_tablero(db_path, potrero=pot)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/repro")
    def api_repro():
        desde = (request.args.get("desde") or "").strip() or None
        hasta = (request.args.get("hasta") or "").strip() or None
        out = datos_repro(db_path, desde=desde, hasta=hasta)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/carne")
    def api_carne():
        """Reportes de carne estilo Software Ganadero (solo lectura, PWA)."""
        desde = (request.args.get("desde") or "").strip() or None
        hasta = (request.args.get("hasta") or "").strip() or None
        out = datos_carne(db_path, desde=desde, hasta=hasta)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/sanidad")
    def api_sanidad():
        out = datos_sanidad(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.post("/api/sanidad/tratamiento")
    def api_sanidad_crear_tratamiento():
        """Registra un tratamiento individual desde la vista Sanidad (online).

        Reusa Database.registrar_tratamiento (misma tabla que Telegram/Captura
        y /api/sync) sin duplicar lógica de retiros. Exige animal con
        estado='ACTIVO' (Regla Fundamental de Inventario): no crea animales
        nuevos aquí — eso queda para Captura/Sync. Auth ya validada por
        _requerir_login; cualquier rol autenticado puede registrar.
        """
        datos = request.get_json(silent=True) or {}
        tag = str(datos.get("tag") or datos.get("animal_tag") or "").strip()
        producto = str(datos.get("producto") or "").strip()
        principio = str(datos.get("principio_activo") or "").strip() or None
        dosis = str(datos.get("dosis") or "").strip() or None
        via = str(datos.get("via") or "").strip().upper() or None
        fecha = str(datos.get("fecha") or "").strip() or date.today().isoformat()
        diagnostico = str(datos.get("diagnostico") or "").strip() or None
        if not tag:
            return jsonify({"ok": False, "error": "El arete/tag del animal es obligatorio."}), 400
        if not producto:
            return jsonify({"ok": False, "error": "El producto/fármaco es obligatorio."}), 400
        if len(producto) > 120 or (principio and len(principio) > 120):
            return jsonify({"ok": False, "error": "Producto/principio activo demasiado largo (máx 120)."}), 400
        if dosis and len(dosis) > 60:
            return jsonify({"ok": False, "error": "Dosis demasiado larga (máx 60)."}), 400
        if via and via not in ("IM", "SC", "IV", "ORAL", "POUR-ON", "TOPICO", "INTRAMAMARIA"):
            return jsonify({"ok": False, "error": "Vía inválida (IM/SC/IV/Oral/Pour-on/Tópico/Intramamaria)."}), 400
        try:
            if to_date(fecha) is None:
                return jsonify({"ok": False, "error": "Fecha inválida. Use YYYY-MM-DD."}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Fecha inválida. Use YYYY-MM-DD."}), 400
        try:
            d_leche = int(datos.get("dias_retiro_leche") or 0)
            d_carne = int(datos.get("dias_retiro_carne") or 0)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Días de retiro deben ser números enteros."}), 400
        if d_leche < 0 or d_carne < 0 or d_leche > 365 or d_carne > 365:
            return jsonify({"ok": False, "error": "Días de retiro entre 0 y 365."}), 400
        db_s = _db(db_path)
        try:
            aid = db_s.resolve_animal(tag)
            if aid is None:
                return jsonify({"ok": False, "error": f"No se encontró el animal '{tag}'."}), 404
            fila = db_s.get_animal(aid)
            if not fila or (fila["estado"] or "") != "ACTIVO":
                return jsonify({"ok": False, "error": f"El animal '{tag}' no está ACTIVO; no se puede tratar."}), 400
            uid = session.get("user_id") if session is not None else None
            tid = db_s.registrar_tratamiento(
                animal_tag=fila["tag"], fecha=fecha, producto=producto,
                principio_activo=principio, dosis=dosis, via=via,
                dias_retiro_leche=d_leche, dias_retiro_carne=d_carne,
                diagnostico=diagnostico, registrado_por=uid,
            )
            fila_t = db_s.query_one(
                "SELECT fecha_fin_retiro_leche, fecha_fin_retiro_carne FROM tratamientos WHERE id = ?",
                (tid,),
            )
            return jsonify({
                "ok": True, "id": tid, "tag": fila["tag"], "fecha": fecha,
                "fecha_fin_retiro_leche": fila_t["fecha_fin_retiro_leche"] if fila_t else None,
                "fecha_fin_retiro_carne": fila_t["fecha_fin_retiro_carne"] if fila_t else None,
            })
        except Exception:
            logger.exception("Error registrando tratamiento de sanidad")
            return jsonify({"ok": False, "error": "No se pudo registrar el tratamiento."}), 500
        finally:
            try:
                db_s.close()
            except Exception:
                pass

    @app.get("/api/pasturas")
    def api_pasturas():
        out = datos_pasturas(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/potrero/<potrero_ref>/animales")
    @app.get("/api/potreros/<potrero_ref>/animales")
    def api_potrero_animales(potrero_ref):
        """Lista animales activos de un potrero (número, nombre, edad, categoría SG y días en potrero)."""
        from urllib.parse import unquote
        pot_clean = unquote(str(potrero_ref or "")).strip()
        db_p = _db(db_path)
        try:
            try:
                from ...engine.dashboard_data import animales_de_potrero
            except (ImportError, ValueError):
                from src.engine.dashboard_data import animales_de_potrero  # type: ignore
            res = animales_de_potrero(db_p, pot_clean)
            if not res.get("ok"):
                return jsonify(res), 404
            return jsonify(res)
        finally:
            db_p.close()

    @app.get("/api/potrero/animales")
    def api_potrero_animales_query():
        pot_ref = request.args.get("potrero") or request.args.get("q") or ""
        if not pot_ref:
            return jsonify({"ok": False, "error": "Parámetro 'potrero' requerido."}), 400
        return api_potrero_animales(pot_ref)

    @app.get("/api/inventario/animales")
    def api_inventario_animales():
        """Lista animales activos pertenecientes a un grupo de inventario:
        - tipo='estructura' (o 'categoria_sg'): valor=Vaca parida, Cría hembra...
        - tipo='bracket': valor=Hembras <1 año, Hembras 1-2 años...
        - tipo='potrero': valor=ORDENO SANTA MARTHA...
        - tipo='piramide': valor=< 1 año, 1 - 2 años, 2+ años; sexo=H/M
        Cumple estrictamente la Regla Fundamental de Inventario (estado = 'ACTIVO').
        """
        tipo = request.args.get("tipo") or "estructura"
        valor = request.args.get("valor") or ""
        sexo = request.args.get("sexo") or ""
        db_p = _db(db_path)
        try:
            try:
                from ...engine.dashboard_data import animales_por_grupo_inventario
            except (ImportError, ValueError):
                from src.engine.dashboard_data import animales_por_grupo_inventario  # type: ignore
            res = animales_por_grupo_inventario(db_p, tipo=tipo, valor=valor, sexo=sexo)
            return jsonify(res)
        finally:
            db_p.close()

    @app.post("/api/pasturas/ronda")
    def api_pasturas_ronda():
        """Evalúa y registra una ronda Voisin de aforo (D2). Cualquier rol
        autenticado puede grabar (incluido TRABAJADOR, vía _requerir_login)."""
        datos = request.get_json(silent=True) or {}
        potrero = str(datos.get("potrero") or "").strip()
        mediciones = datos.get("mediciones") or []
        try:
            num_animales = int(datos.get("num_animales") or 1)
        except (TypeError, ValueError):
            num_animales = 1
        fecha = str(datos.get("fecha") or "").strip() or date.today().isoformat()
        if not potrero or not isinstance(mediciones, list) or not mediciones:
            return jsonify({"error": "Se requieren 'potrero' y 'mediciones' (lista no vacía)."}), 400
        try:
            from ...engine.pasture_engine import PastureEngine
        except (ImportError, ValueError):
            from src.engine.pasture_engine import PastureEngine  # type: ignore
        try:
            from ...server.formatters import formatear_ronda_voisin
        except (ImportError, ValueError):
            from src.server.formatters import formatear_ronda_voisin  # type: ignore
        db_r = _db(db_path)
        try:
            pid = db_r.potrero_id(potrero)
            if pid is None:
                fila_ci = db_r.query_one(
                    "SELECT id FROM potreros WHERE UPPER(nombre) = UPPER(?) OR UPPER(codigo) = UPPER(?) LIMIT 1",
                    (potrero, potrero),
                )
                pid = int(fila_ci["id"]) if fila_ci else None
            if pid is None:
                return jsonify({"error": f"No se encontró el potrero '{potrero}'."}), 404
            prow = db_r.get_potrero(pid)
            area = (prow["area_has"] if prow and prow["area_has"] else None)
            res = PastureEngine.evaluar_ronda_voisin(mediciones, area, num_animales)
            if res is None:
                return jsonify({"error": "Datos invalidos o potrero sin area"}), 400
            uid = session.get("user_id")
            db_r.registrar_ronda_voisin(
                pid, mediciones, res["num_puntos"], res["kg_mv_promedio"],
                res["dias_disponibles"], res["semaforo"],
                kg_ms_ha_val=res["kg_ms_ha"], fecha=fecha, registrado_por=uid,
            )
            ronda = {"potrero_nom": (prow["nombre"] if prow and prow["nombre"] else potrero),
                     "fecha": fecha, **res}
            return jsonify({"ok": True, "ronda": ronda,
                            "mensaje": formatear_ronda_voisin(ronda)})
        except Exception:
            logger.exception("Error en ronda Voisin")
            return jsonify({"error": "No se pudo registrar la ronda."}), 500
        finally:
            db_r.close()

    @app.get("/api/pasturas/rondas")
    def api_pasturas_rondas():
        """Últimas 10 rondas Voisin, opcionalmente filtradas por potrero."""
        potrero = (request.args.get("potrero") or "").strip() or None
        db_r = _db(db_path)
        try:
            pid = None
            if potrero:
                pid = db_r.potrero_id(potrero)
                if pid is None:
                    fila_ci = db_r.query_one(
                        "SELECT id FROM potreros WHERE UPPER(nombre) = UPPER(?) OR UPPER(codigo) = UPPER(?) LIMIT 1",
                        (potrero, potrero),
                    )
                    pid = int(fila_ci["id"]) if fila_ci else None
                if pid is None:
                    return jsonify({"ok": True, "rondas": []})
            filas = db_r.listar_rondas_voisin(pid, limite=10)
            return jsonify({"ok": True, "rondas": [dict(f) for f in filas]})
        finally:
            db_r.close()

    @app.post("/api/satelite/actualizar")
    @_limite_api("satelite")
    def api_satelite_actualizar():
        """Sincroniza lecturas satelitales (Sentinel-1 SAR Radar o Sentinel-2 Óptico)
        directamente vía Google Earth Engine para los potreros con geometría real.
        """
        datos = request.get_json(silent=True) or {}
        modo = str(datos.get("modo") or "auto").strip().lower()
        if modo not in ("auto", "radar", "s1", "s2"):
            modo = "auto"

        db_s = _db(db_path)
        try:
            try:
                from ...gis.earth_engine_ndvi import actualizar_lecturas_reales
            except (ImportError, ValueError):
                from src.gis.earth_engine_ndvi import actualizar_lecturas_reales

            filas_pot = db_s.query(
                "SELECT id, nombre, area_has, geom_wkt_4326 FROM potreros "
                "WHERE geom_wkt_4326 IS NOT NULL ORDER BY nombre"
            )
            potreros = [dict(f) for f in filas_pot]
            if not potreros:
                return jsonify({"ok": False, "error": "No hay potreros con geometría WKT registrada."}), 400

            lecturas = actualizar_lecturas_reales(potreros, modo=modo)
            if not lecturas:
                return jsonify({
                    "ok": False,
                    "error": "No se obtuvieron imágenes satelitales en la ventana de tiempo especificada."
                }), 502

            uid = session.get("user_id")
            actualizados = 0
            for r in lecturas:
                db_s.registrar_lectura_ndvi(
                    potrero_id_o_nom=r["potrero_id"],
                    fecha=r["fecha"],
                    ndvi_promedio=r["ndvi_promedio"],
                    ndvi_min=r.get("ndvi_min"),
                    ndvi_max=r.get("ndvi_max"),
                    biomasa_estimada_kg_ha=r.get("biomasa_estimada_kg_ha"),
                    aforo_estimado_kg_m2=r.get("aforo_estimado_kg_m2"),
                    cobertura_nubes_pct=r.get("cobertura_nubes_pct", 0.0),
                    fuente=r.get("fuente", "Sentinel-2 L2A"),
                    registrado_por=uid,
                )
                actualizados += 1

            # Invalidar cache de gráficos en disco para que el mapa de potreros se refresque inmediatamente
            try:
                if os.path.isdir(_base.REPORTES_DIR_DEFAULT):
                    for arch in os.listdir(_base.REPORTES_DIR_DEFAULT):
                        if arch.startswith("_pwa_cache_"):
                            try:
                                os.remove(os.path.join(_base.REPORTES_DIR_DEFAULT, arch))
                            except Exception:
                                pass
            except Exception:
                pass

            n_sar = sum(1 for r in lecturas if "SAR" in (r.get("fuente") or "").upper() or "SENTINEL-1" in (r.get("fuente") or "").upper())
            n_opt = len(lecturas) - n_sar
            sensor_principal = "Radar SAR Sentinel-1 (Todo Clima)" if n_sar > 0 else "Sentinel-2 Óptico"
            msg = f"Sincronizados {actualizados} potreros ({n_sar} Radar SAR, {n_opt} Óptico)"
            return jsonify({
                "ok": True,
                "actualizados": actualizados,
                "sar": n_sar,
                "optico": n_opt,
                "sensor_principal": sensor_principal,
                "modo": modo,
                "mensaje": msg,
            })
        except Exception as e:
            logger.exception("Error actualizando satelite desde PWA: %s", e)
            return _error_interno(500)
        finally:
            try:
                db_s.close()
            except Exception:
                pass
