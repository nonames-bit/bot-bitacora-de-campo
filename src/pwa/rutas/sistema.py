"""Estado del sistema, logs, GPS, telemetría y mapa.

Rutas registradas sobre la app de ``crear_app`` (ver src/pwa/app.py).
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import date
import logging
from flask import jsonify, request, session
from .. import app as _base
from ...engine.dashboard_data import _filas_dict
from ...utils import to_date
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _db,
)

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def registrar(app, ctx, h):
    _rol_actual = h._rol_actual
    db_path = ctx.db_path
    users_file = ctx.users_file

    @app.get("/api/sistema")
    def api_sistema():
        if _rol_actual() != "OWNER":
            return jsonify({"error": "Acceso denegado. Se requiere rol OWNER (Propietario)."}), 403

        db_inst = _db(db_path)
        try:
            try:
                try:
                    from ...server.formatters import formatear_tablero_sistema
                    from ...server.auth import Auth
                except ImportError:
                    from src.server.formatters import formatear_tablero_sistema  # type: ignore
                    from src.server.auth import Auth  # type: ignore
                auth_inst = Auth(users_file)
                texto_sistema = formatear_tablero_sistema(db_inst, auth_inst, db_path)
            except Exception as e:
                texto_sistema = f"Error al formatear tablero del sistema: {e}"

            import platform
            info_vps = {
                "so": platform.platform(),
                "python": platform.python_version(),
            }
            try:
                import psutil
                mem = psutil.virtual_memory()
                ruta_disco = "/" if hasattr(os, "statvfs") or sys.platform != "win32" else "C:\\"
                disk = psutil.disk_usage(ruta_disco)
                info_vps["ram_total_mb"] = mem.total // (1024 * 1024)
                info_vps["ram_used_mb"] = mem.used // (1024 * 1024)
                info_vps["ram_pct"] = round(mem.percent, 1)
                info_vps["disk_total_gb"] = round(disk.total / (1024**3), 1)
                info_vps["disk_used_gb"] = round(disk.used / (1024**3), 1)
                info_vps["disk_pct"] = round(disk.percent, 1)
                proc = psutil.Process(os.getpid())
                info_vps["proc_ram_mb"] = round(proc.memory_info().rss / (1024 * 1024), 1)
            except Exception:
                # Fallback sin dependencias externas (Linux /proc/meminfo y os.statvfs)
                try:
                    if os.path.exists("/proc/meminfo"):
                        mem_info = {}
                        with open("/proc/meminfo", "r", encoding="utf-8") as mf:
                            for line in mf:
                                parts = line.split(":")
                                if len(parts) == 2:
                                    k = parts[0].strip()
                                    v = parts[1].strip().split()[0]
                                    mem_info[k] = int(v)  # kB
                        if "MemTotal" in mem_info and "MemAvailable" in mem_info:
                            tot_mb = mem_info["MemTotal"] // 1024
                            avail_mb = mem_info["MemAvailable"] // 1024
                            used_mb = max(0, tot_mb - avail_mb)
                            info_vps["ram_total_mb"] = tot_mb
                            info_vps["ram_used_mb"] = used_mb
                            info_vps["ram_pct"] = round((used_mb / tot_mb) * 100, 1) if tot_mb else 0.0

                    if hasattr(os, "statvfs"):
                        st = os.statvfs("/")
                        total_gb = round((st.f_blocks * st.f_frsize) / (1024**3), 1)
                        avail_gb = round((st.f_bavail * st.f_frsize) / (1024**3), 1)
                        used_gb = round(max(0.0, total_gb - avail_gb), 1)
                        info_vps["disk_total_gb"] = total_gb
                        info_vps["disk_used_gb"] = used_gb
                        info_vps["disk_pct"] = round((used_gb / total_gb) * 100, 1) if total_gb else 0.0
                except Exception:
                    pass

            tam_bytes = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
            tam_mb = round(tam_bytes / (1024 * 1024), 2)
            row_a = db_inst.query_one("SELECT COUNT(*) as n FROM animales WHERE estado = 'ACTIVO'")
            row_tot = db_inst.query_one("SELECT COUNT(*) as n FROM animales")
            termo = db_inst.query_one("SELECT * FROM termo_nitrogeno ORDER BY fecha_recarga DESC LIMIT 1")
            try:
                presencias = db_inst.obtener_usuarios_presencia()
                en_linea_cnt = sum(1 for p in presencias.values() if p.get("en_linea"))
            except Exception:
                presencias = {}
                en_linea_cnt = 0

            # 1. Sincronización Software Ganadero (SG)
            ult_sync_row = db_inst.ultimo_import_sg()
            historial_sync_rows = db_inst.query(
                "SELECT id, fecha_iso, archivo, nuevos, duplicados FROM import_sg_historial ORDER BY id DESC LIMIT 10"
            )
            sync_sg = None
            if ult_sync_row:
                d_sync = dict(ult_sync_row)
                f_iso = d_sync.get("fecha_iso")
                dias_diff = None
                tiempo_str = "Reciente"
                if f_iso:
                    try:
                        f_d = to_date(f_iso[:10])
                        if f_d:
                            diff = (date.today() - f_d).days
                            dias_diff = diff
                            if diff == 0:
                                tiempo_str = "Hoy"
                            elif diff == 1:
                                tiempo_str = "Ayer"
                            else:
                                tiempo_str = f"Hace {diff} días"
                    except Exception:
                        pass
                d_sync["tiempo_relativo"] = tiempo_str
                d_sync["dias_desde_sync"] = dias_diff
                d_sync["al_dia"] = (dias_diff is not None and dias_diff <= 7)
                sync_sg = {
                    "ultimo": d_sync,
                    "historial": [dict(r) for r in (historial_sync_rows or [])],
                }

            # 2. Auditoría de Actividad Reciente de los Demás Usuarios
            ult_eventos = db_inst.ultimos_registros(limite=35)
            actividad_reciente = []
            for ev in ult_eventos:
                r_dict = dict(ev)
                reg_por = r_dict.get("registrado_por")
                u_info = auth_inst.obtener_usuario(reg_por) if (reg_por and auth_inst) else None
                if u_info:
                    r_dict["usuario_nombre"] = u_info.get("nombre", f"Usuario #{reg_por}")
                    r_dict["usuario_rol"] = u_info.get("rol", "TRABAJADOR")
                    r_dict["usuario_avatar"] = u_info.get("avatar") or ("patron" if u_info.get("rol") == "OWNER" else "admin" if u_info.get("rol") == "ADMIN" else "vaquero")
                    r_dict["canal"] = "Telegram" if (isinstance(reg_por, int) and reg_por > 1000000) else "PWA"
                elif reg_por:
                    r_dict["usuario_nombre"] = f"Usuario #{reg_por}"
                    r_dict["usuario_rol"] = "TRABAJADOR"
                    r_dict["usuario_avatar"] = "vaquero"
                    r_dict["canal"] = "Telegram" if (isinstance(reg_por, int) and reg_por > 1000000) else "PWA"
                else:
                    r_dict["usuario_nombre"] = "Importación histórica"
                    r_dict["usuario_rol"] = "SISTEMA"
                    r_dict["usuario_avatar"] = "admin"
                    r_dict["canal"] = "Sistema"

                c_en = r_dict.get("creado_en") or r_dict.get("fecha")
                if c_en:
                    try:
                        c_clean = str(c_en).replace("T", " ")[:16]
                        r_dict["fecha_hora_fmt"] = c_clean
                    except Exception:
                        r_dict["fecha_hora_fmt"] = str(c_en)
                else:
                    r_dict["fecha_hora_fmt"] = "—"

                actividad_reciente.append(r_dict)

            return jsonify({
                "texto": texto_sistema,
                "vps": info_vps,
                "en_linea_count": en_linea_cnt,
                "presencias": list(presencias.values()) if presencias else [],
                "db": {
                    "path": db_path,
                    "tam_mb": tam_mb,
                    "activos": row_a["n"] if row_a else 0,
                    "total": row_tot["n"] if row_tot else 0,
                },
                "sync_sg": sync_sg,
                "actividad_reciente": actividad_reciente,
                "termo": dict(termo) if termo else None,
                "rol": "OWNER",
            })
        finally:
            db_inst.close()

    @app.get("/api/logs")
    def api_logs():
        if _rol_actual() != "OWNER":
            return jsonify({"error": "Acceso denegado. Se requiere rol OWNER (Propietario)."}), 403

        import subprocess
        canal = str(request.args.get("canal", "todos")).lower().strip()
        try:
            limite = min(300, max(20, int(request.args.get("n", 100))))
        except Exception:
            limite = 100

        lineas: list[str] = []

        # 1. En Linux / VPS: intentar capturar journalctl de los servicios systemd
        if sys.platform != "win32" and shutil.which("journalctl"):
            try:
                cmd = ["journalctl", "-n", str(limite), "--no-pager"]
                if canal == "telegram":
                    cmd.extend(["-u", "bitacora-bot"])
                elif canal == "pwa":
                    cmd.extend(["-u", "bitacora-pwa"])
                elif canal == "copias":
                    cmd = None
                else:  # "todos"
                    cmd.extend(["-u", "bitacora-bot", "-u", "bitacora-pwa"])

                if cmd:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if res.returncode == 0 and res.stdout:
                        lineas = [l.strip() for l in res.stdout.splitlines() if l.strip()]
            except Exception as e:
                logger.warning("Error ejecutando journalctl: %s", e)

        # 2. Agregar o consultar archivos de log físicos
        candidatos_log: list[str] = []
        if canal in ("copias", "todos"):
            candidatos_log.append(os.path.join(_base.RAIZ_PROYECTO, "data", "copias_import.log"))
        if canal in ("telegram", "todos"):
            candidatos_log.extend([
                os.path.join(_base.RAIZ_PROYECTO, "data", "bot.log"),
                os.path.join(_base.RAIZ_PROYECTO, "bot.log"),
                os.path.join(_base.RAIZ_PROYECTO, "data", "telegram.log"),
            ])
        if canal in ("pwa", "todos"):
            candidatos_log.extend([
                os.path.join(_base.RAIZ_PROYECTO, "data", "bitacora.log"),
                os.path.join(_base.RAIZ_PROYECTO, "bitacora.log"),
            ])

        for c in candidatos_log:
            if os.path.isfile(c):
                try:
                    with open(c, "r", encoding="utf-8", errors="replace") as f:
                        sub_lineas = [l.strip() for l in f.readlines()[-limite:] if l.strip()]
                        if canal == "todos" and lineas:
                            lineas.extend(sub_lineas[-25:])
                        else:
                            lineas.extend(sub_lineas)
                except Exception:
                    pass

        if not lineas:
            lineas = [f"Sin registros recientes disponibles para el canal '{canal}'."]

        return jsonify({"logs": lineas[-limite:], "canal": canal, "total": len(lineas), "rol": "OWNER"})

    @app.post("/api/gps/potrero")
    def api_gps_potrero():
        datos = request.get_json(silent=True) or request.form
        try:
            lat = float(datos.get("lat"))
            lon = float(datos.get("lon"))
        except (TypeError, ValueError):
            return jsonify({"error": "lat y lon deben ser números válidos."}), 400

        db_gps = _db(db_path)
        try:
            det = db_gps.detectar_potrero_gps(lat, lon)
            if not det:
                return jsonify({"detectado": False, "mensaje": "Ubicación fuera del área de potreros de la finca."})

            animales = db_gps.query(
                "SELECT id_animal, tag, nombre, sexo, raza FROM animales WHERE potrero_id = ? AND estado = 'ACTIVO' ORDER BY tag",
                (det["id"],),
            )
            return jsonify({
                "detectado": True,
                "potrero": det,
                "animales": _filas_dict(animales),
                "total_animales": len(animales),
            })
        finally:
            db_gps.close()

    @app.post("/api/gps/ronda")
    def api_gps_ronda():
        datos = request.get_json(silent=True) or request.form
        lat = datos.get("lat")
        lon = datos.get("lon")
        punto = datos.get("punto_control") or "recorrido"
        notas = datos.get("notas")
        pot_id = datos.get("potrero_id")
        pot_nom = datos.get("potrero_nombre")

        db_gps = _db(db_path)
        try:
            ronda_id = db_gps.registrar_ronda_campo(
                user_id=session.get("user_id"),
                usuario_nombre=session.get("nombre") or (_rol_actual() or "Usuario"),
                lat=lat,
                lon=lon,
                potrero_id=pot_id,
                potrero_nombre=pot_nom,
                punto_control=punto,
                notas=notas,
            )
            return jsonify({"ok": True, "ronda_id": ronda_id})
        finally:
            db_gps.close()

    @app.get("/api/gps/rondas")
    def api_gps_listar_rondas():
        db_gps = _db(db_path)
        try:
            fecha = request.args.get("fecha")
            filas = db_gps.listar_rondas_campo(fecha=fecha, limite=50)
            return jsonify({"rondas": _filas_dict(filas)})
        finally:
            db_gps.close()

    @app.post("/api/telemetria/ping")
    def api_telemetria_ping():
        """Ping silencioso en segundo plano de ubicación de operarios en la finca."""
        datos = request.get_json(silent=True) or request.form
        try:
            lat = float(datos.get("lat"))
            lon = float(datos.get("lon"))
        except (TypeError, ValueError):
            return jsonify({"error": "lat y lon son requeridos y deben ser numéricos."}), 400

        acc = datos.get("precision_m")
        try:
            acc_f = float(acc) if acc is not None else None
        except (ValueError, TypeError):
            acc_f = None

        evento = (datos.get("evento_origen") or "interaccion_app").strip()
        uid = session.get("user_id")
        nombre = session.get("nombre") or "Usuario"
        rol = _rol_actual() or "TRABAJADOR"

        db_tele = _db(db_path)
        try:
            t_id = db_tele.registrar_telemetria_gps(
                user_id=uid,
                usuario_nombre=nombre,
                rol=rol,
                lat=lat,
                lon=lon,
                precision_m=acc_f,
                evento_origen=evento,
            )
            if not t_id:
                return jsonify({
                    "ok": True,
                    "ignorado": True,
                    "motivo": "Ubicación fuera del área de la finca (no se registra telemetría)",
                    "potrero": None
                })
            det = db_tele.detectar_potrero_gps(lat, lon) or {"nombre": "Casa / Corrales / Finca", "dentro": False}
            return jsonify({"ok": True, "telemetria_id": t_id, "potrero": det})
        finally:
            db_tele.close()

    @app.get("/api/telemetria/rutas")
    def api_telemetria_rutas():
        """Consulta rutas y desplazamientos de operarios (ADMIN y OWNER)."""
        rol = _rol_actual()
        if rol == "TRABAJADOR":
            return jsonify({"error": "Acceso denegado. Las rutas y mapa GPS son exclusivos para administración y gerencia."}), 403

        fecha = request.args.get("fecha")
        db_tele = _db(db_path)
        try:
            rutas = db_tele.resumen_rutas_operarios(fecha=fecha)
            rondas = [dict(r) for r in db_tele.listar_rondas_campo(fecha=fecha, limite=50)]
            return jsonify({"ok": True, "rutas": rutas, "rondas": rondas})
        finally:
            db_tele.close()

    @app.get("/api/mapa/datos")
    def api_mapa_datos():
        """Retorna GeoJSON de potreros, vigor NDVI/SAR, ocupación, operarios en vivo y rutas."""
        mi_rol = _rol_actual()
        if mi_rol == "TRABAJADOR":
            return jsonify({"error": "Acceso denegado. El mapa y rutas GPS son exclusivos para administración y gerencia."}), 403
        db_map = _db(db_path)
        try:
            try:
                from ...engine.mapa_data import datos_mapa_finca
            except (ImportError, ValueError):
                from src.engine.mapa_data import datos_mapa_finca
            res = datos_mapa_finca(db_map)
            res["rol"] = mi_rol
            fecha_req = request.args.get("fecha")
            res["rutas"] = db_map.resumen_rutas_operarios(fecha=fecha_req)
            res["rondas"] = [dict(r) for r in db_map.listar_rondas_campo(fecha=fecha_req, limite=50)]
            return jsonify(res)
        finally:
            db_map.close()
