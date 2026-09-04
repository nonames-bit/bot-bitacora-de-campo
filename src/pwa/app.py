"""Backend Flask liviano del Dashboard PWA ejecutivo — Fase 7 Etapa D.

Solo lectura: cada endpoint es un envoltorio fino sobre ``db.query`` /
``db.query_one`` (nunca ``execute`` de escritura). Reusa RBAC de
``users.json`` para lectura de roles. Puerto 8080.

Si Flask no está instalado el módulo se importa sin romper el bot
(import lazy / try): ``app`` queda como stub y ``crear_app`` devuelve None.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import time

# Fix Windows cp1252: consola sin UTF-8 rompía los print() del banner
# (UnicodeEncodeError) antes de que Flask arrancara. No requiere acción
# del usuario: se fuerza UTF-8 con "replace" y se fija PYTHONIOENCODING.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import hmac
import secrets
from datetime import date, timedelta
from typing import Any, Optional

try:
    from ..db.database import Database
except ImportError:  # ejecución directa: python src/pwa/app.py
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.db.database import Database  # type: ignore

try:
    from flask import (Flask, abort, jsonify, redirect, render_template,  # type: ignore
                       request, send_file, send_from_directory, session)

    _FLASK_OK = True
except Exception:  # Flask no instalado: no romper el bot
    Flask = None  # type: ignore
    _FLASK_OK = False

    def jsonify(*a, **k):  # type: ignore
        return {"json": a, **k}

    def render_template(*a, **k):  # type: ignore
        return ""

    def redirect(*a, **k):  # type: ignore
        return ""

    def send_file(*a, **k):  # type: ignore
        return ""

    def send_from_directory(*a, **k):  # type: ignore
        return ""

    def abort(*a, **k):  # type: ignore
        raise RuntimeError("Flask no instalado")

    request = None  # type: ignore
    session = None  # type: ignore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Raíz del repo (…/src/pwa → …): para resolver data/bitacora.db aunque se
# invoque desde otro cwd y para mensajes de error accionables.
RAIZ_PROYECTO = os.path.dirname(os.path.dirname(BASE_DIR))

# Cargar .env igual que el resto del bot (telegram_bot.py, copias_watcher.py)
# — sin esto, PWA_PASSWORD/PWA_PORT/BITACORA_DB solo se podían fijar como
# variable de entorno real del sistema, nunca desde el .env del proyecto.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(RAIZ_PROYECTO, ".env"))
except Exception:
    pass

DB_PATH_DEFAULT = os.getenv("BITACORA_DB", os.path.join("data", "bitacora.db"))
USERS_FILE_DEFAULT = os.getenv("USERS_FILE", os.path.join("src", "server", "users.json"))
MEDIA_DIR_DEFAULT = os.getenv("MEDIA_DIR", "media")
REPORTES_DIR_DEFAULT = os.path.join("data", "reportes")
# Los gráficos (matplotlib) no cambian minuto a minuto -- el NDVI se
# actualiza semanal, los datos del hato a lo sumo varían unas pocas veces
# al día. Cachear 10 min evita regenerar la misma imagen si dos personas
# abren la misma pestaña casi al tiempo (el servidor Flask de desarrollo
# es de un solo hilo: sin esto, la segunda petición esperaría a que la
# primera termine de renderizar en vez de servir algo instantáneo).
CACHE_GRAFICOS_SEGUNDOS = int(os.getenv("PWA_CACHE_GRAFICOS_SEGUNDOS", "600"))
# Host/puerto configurables por entorno (iniciar_pwa.sh ya usa PWA_PORT).
# Default 0.0.0.0/8080: accesible desde celular/otra PC de la misma red.
PWA_HOST_DEFAULT = os.getenv("PWA_HOST", "0.0.0.0")
try:
    PUERTO = int(os.getenv("PWA_PORT", "8080"))
except ValueError:
    PUERTO = 8080

# Autenticación (cierra el hueco de acceso libre: antes cualquiera que
# llegara al puerto veía todos los datos de la finca sin login). Obligatoria
# por diseño: si no está configurada, la app se sirve pero deniega todo con
# un mensaje claro en vez de quedar abierta por defecto ("fail closed").
PWA_PASSWORD = os.getenv("PWA_PASSWORD", "")
# Clave de firma de la cookie de sesión (Flask/itsdangerous, sin dependencia
# nueva). Si no se configura por entorno, se genera una vez y se guarda en
# disco (fuera del repo) para que la sesión no se invalide en cada reinicio.
_SECRET_KEY_FILE = os.path.join("data", ".pwa_secret_key")


def _obtener_secret_key() -> str:
    env_key = os.getenv("PWA_SECRET_KEY", "").strip()
    if env_key:
        return env_key
    try:
        if os.path.isfile(_SECRET_KEY_FILE):
            with open(_SECRET_KEY_FILE, encoding="utf-8") as f:
                clave = f.read().strip()
            if clave:
                return clave
    except Exception:
        pass
    clave = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(_SECRET_KEY_FILE) or ".", exist_ok=True)
        with open(_SECRET_KEY_FILE, "w", encoding="utf-8") as f:
            f.write(clave)
    except Exception:
        pass  # sin disco escribible: la sesión no sobrevive un reinicio, pero sigue firmada
    return clave


def _resolver_db_existente(db_path: str) -> Optional[str]:
    """Devuelve la ruta real de la DB si existe (cwd o raíz del repo)."""
    candidatos = [db_path]
    if not os.path.isabs(db_path):
        candidatos.append(os.path.join(RAIZ_PROYECTO, db_path))
        candidatos.append(os.path.abspath(db_path))
    for c in candidatos:
        try:
            if c and os.path.isfile(c):
                return c
        except Exception:
            continue
    return None


def _ip_lan() -> str:
    """IP de red local para abrir desde el celular/otra PC (best-effort)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        ip2 = socket.gethostbyname(socket.gethostname())
        if ip2 and not ip2.startswith("127."):
            return ip2
    except Exception:
        pass
    return "TU_IP_LOCAL"


def _imprimir_banner(host: str, puerto: int) -> None:
    """Banner en español con la URL exacta local y de red."""
    ip = _ip_lan()
    print("", flush=True)
    print("==============================================================", flush=True)
    print("  🐮 PWA Bitácora JA lista — abra esta dirección en el navegador:", flush=True)
    print(f"     👉 Local (este PC):  http://localhost:{puerto}", flush=True)
    print(f"     👉 Red (celular/otra PC):  http://{ip}:{puerto}", flush=True)
    print("  Si no abre: verifique que usa http:// (no https://) y el puerto.", flush=True)
    print("  Para otro puerto:  set PWA_PORT=8081  (o $env:PWA_PORT=8081)", flush=True)
    print("  Para detener: pulse Ctrl+C en esta ventana.", flush=True)
    print("==============================================================", flush=True)
    print("", flush=True)


def _rol_de(user_id: Any, users_file: str = USERS_FILE_DEFAULT) -> Optional[str]:
    """Lee el rol desde users.json sin mutar nada (solo lectura RBAC)."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    try:
        with open(users_file, encoding="utf-8") as f:
            datos = json.load(f)
        for u in datos:
            if isinstance(u, dict) and u.get("user_id") == uid:
                return str(u.get("rol", "")).strip().upper() or None
    except Exception:
        return None
    return None


def _db(db_path: str) -> Database:
    return Database(db_path)


# Whitelist de gráficos servibles por /api/grafico/<tipo> — mismo patrón de
# seguridad que GRAFICOS_PANEL en telegram_bot.py: nunca se ejecuta un
# nombre de función arbitrario, solo estas claves fijas. Import perezoso
# (dentro de la función) para no exigir matplotlib si la PWA no lo usa.
def _generadores_graficos_pwa():
    try:
        from ..engine import charts
    except ImportError:  # ejecución directa: python src/pwa/app.py
        from src.engine import charts  # type: ignore

    return {
        "mapa_potreros": charts.generar_mapa_potreros,
        "ocupacion": charts.generar_grafico_ocupacion_potreros,
        "aforo": charts.generar_grafico_aforo_potreros,
        "carga_animal": charts.generar_grafico_carga_animal_potrero,
        "evolucion": charts.generar_grafico_evolucion_rebano,
        "categorias": charts.generar_grafico_categorias,
        "leche_total": charts.generar_grafico_leche_total_hato,
        "eficiencia_lechera": charts.generar_grafico_eficiencia_lechera,
        "reproductivo_hato": charts.generar_grafico_estado_reproductivo_hato,
    }


def _filas_dict(filas) -> list[dict]:
    return [dict(r) for r in (filas or [])]


def _ruta_relativa_media(ruta: str, media_dir: str = MEDIA_DIR_DEFAULT) -> str:
    """`fotos.ruta` en la BD ya incluye el prefijo del directorio de media
    (ej. `media/5953-2.jpg`, ver telegram_bot.py/dbf_importer.py) — esto lo
    recorta para no duplicarlo al armar la URL `/media/<rel>`."""
    r = str(ruta or "").replace("\\", "/").lstrip("/")
    prefijo = media_dir.replace("\\", "/").strip("/") + "/"
    if r.startswith(prefijo):
        return r[len(prefijo):]
    return os.path.basename(r)


# ------------------------------------------------------------------ #
# Consultas de lectura (envoltorios finos, siempre estado='ACTIVO')
# ------------------------------------------------------------------ #
def datos_tablero(db_path: str = DB_PATH_DEFAULT, potrero: Optional[str] = None) -> dict:
    """Tablero finca: activos por categoría, eventos 7d, retiros activos."""
    db = _db(db_path)
    try:
        hoy = date.today()
        hace7 = (hoy - timedelta(days=7)).isoformat()
        hoy_iso = hoy.isoformat()
        filtro_pot = ""
        params: tuple = ()
        if potrero:
            pid = db.potrero_id(potrero)
            if pid is not None:
                filtro_pot = " AND (a.potrero_id = ? OR a.id_animal IN (SELECT animal_id FROM traslados WHERE potrero_destino = ?))"
                params = (pid, pid)
        base = f"FROM animales a WHERE a.estado = 'ACTIVO'{filtro_pot}"
        n = db.query_one(f"SELECT COUNT(*) n {base}", params)
        hem = db.query_one(f"SELECT COUNT(*) n {base} AND UPPER(a.sexo) LIKE 'H%'", params)
        mac = db.query_one(f"SELECT COUNT(*) n {base} AND UPPER(a.sexo) LIKE 'M%'", params)

        def _cnt(tabla: str, col: str = "vaca_id", fid: str = "id_animal") -> int:
            # Eventos 7d restringidos a animales ACTIVOS (y potrero si se filtra).
            r = db.query_one(
                f"SELECT COUNT(*) n FROM {tabla} e JOIN animales a ON a.id_animal = e.{col} "
                f"WHERE a.estado = 'ACTIVO' AND e.fecha >= ? AND e.fecha <= ?{filtro_pot}",
                (hace7, hoy_iso) + params,
            )
            return int(r["n"]) if r else 0

        try:
            ret = db.query_one(
                """SELECT COUNT(DISTINCT t.animal_id) n FROM tratamientos t
                   JOIN animales a ON a.id_animal = t.animal_id
                   WHERE a.estado = 'ACTIVO'
                   AND ((t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
                    OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?))""",
                (hoy_iso, hoy_iso),
            )
            retiros = int(ret["n"]) if ret else 0
        except Exception:
            retiros = 0
        por_potrero: list[dict] = []
        try:
            por_potrero = _filas_dict(db.query(
                "SELECT COALESCE(p.nombre, p.codigo, 'Sin potrero') potrero, COUNT(*) n "
                "FROM animales a LEFT JOIN potreros p ON p.id = a.potrero_id "
                "WHERE a.estado = 'ACTIVO' GROUP BY potrero ORDER BY n DESC LIMIT 20"
            ))
        except Exception:
            pass
        return {
            "activos": int(n["n"]) if n else 0,
            "hembras": int(hem["n"]) if hem else 0,
            "machos": int(mac["n"]) if mac else 0,
            "partos_7d": _cnt("partos"),
            "celos_7d": _cnt("celos"),
            "servicios_7d": _cnt("servicios"),
            "retiros_activos": retiros,
            "por_potrero": por_potrero,
            "potrero_filtro": potrero,
        }
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_repro(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Reproducción: FEP≤30d, eco d35 / palpación d60, celos AM-PM pendientes."""
    db = _db(db_path)
    try:
        hoy = date.today()
        hoy_iso_repro = hoy.isoformat()
        lim = (hoy + timedelta(days=30)).isoformat()
        try:
            # "FEP ≤30d" = próximos partos, ventana hacia adelante desde hoy.
            # Faltaba el límite inferior: sin él, traía las 30 fechas MÁS
            # ANTIGUAS de toda la tabla (años atrás) en vez de las próximas.
            fep = _filas_dict(db.query(
                """SELECT a.tag, s.fecha, s.tipo_servicio, s.toro_pajilla, s.fep_calculada
                   FROM servicios s JOIN animales a ON a.id_animal = s.vaca_id
                   WHERE a.estado = 'ACTIVO' AND s.fep_calculada IS NOT NULL
                   AND s.fep_calculada >= ? AND s.fep_calculada <= ?
                   ORDER BY s.fep_calculada LIMIT 30""", (hoy_iso_repro, lim)))
        except Exception:
            fep = []
        try:
            celos = _filas_dict(db.query(
                """SELECT a.tag, c.fecha, c.am_pm FROM celos c
                   JOIN animales a ON a.id_animal = c.vaca_id
                   WHERE a.estado = 'ACTIVO' ORDER BY c.fecha DESC LIMIT 20"""))
        except Exception:
            celos = []
        try:
            diags = _filas_dict(db.query(
                """SELECT a.tag, d.fecha, d.resultado, d.dias_gestacion FROM diagnosticos_gestacion d
                   JOIN animales a ON a.id_animal = d.vaca_id
                   WHERE a.estado = 'ACTIVO' ORDER BY d.fecha DESC LIMIT 20"""))
        except Exception:
            diags = []
        try:
            pendientes = _filas_dict(db.query(
                "SELECT tipo_alerta, fecha_programada, descripcion FROM alertas "
                "WHERE estado = 'PENDIENTE' AND tipo_alerta IN ('ECOGRAFIA','PALPACION') "
                "ORDER BY fecha_programada LIMIT 30"))
        except Exception:
            pendientes = []
        return {"fep_30d": fep, "celos_recientes": celos, "diagnosticos": diags,
                "eco_palp_pendientes": pendientes}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_sanidad(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Sanidad: retiros leche/carne con cuenta regresiva + últimos tratamientos."""
    db = _db(db_path)
    try:
        hoy = date.today()
        hoy_iso = hoy.isoformat()
        try:
            retiros = _filas_dict(db.query(
                """SELECT a.tag, t.producto, t.fecha, t.fecha_fin_retiro_leche,
                          t.fecha_fin_retiro_carne FROM tratamientos t
                   JOIN animales a ON a.id_animal = t.animal_id
                   WHERE a.estado = 'ACTIVO'
                   AND ((t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
                    OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?))
                   ORDER BY t.fecha DESC LIMIT 30""", (hoy_iso, hoy_iso)))
            for r in retiros:
                for k in ("fecha_fin_retiro_leche", "fecha_fin_retiro_carne"):
                    if r.get(k):
                        try:
                            r[k + "_dias"] = (date.fromisoformat(r[k]) - hoy).days
                        except Exception:
                            r[k + "_dias"] = None
        except Exception:
            retiros = []
        try:
            ultimos = _filas_dict(db.query(
                """SELECT a.tag, t.producto, t.dosis, t.via, t.fecha FROM tratamientos t
                   JOIN animales a ON a.id_animal = t.animal_id
                   WHERE a.estado = 'ACTIVO' ORDER BY t.fecha DESC, t.id DESC LIMIT 20"""))
        except Exception:
            ultimos = []
        return {"retiros": retiros, "ultimos_tratamientos": ultimos}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_pasturas(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Pasturas: ocupación Voisin (semáforo), reposo y último NDVI."""
    db = _db(db_path)
    try:
        try:
            # Solo potreros con geometría real (Fase B del plan geoespacial)
            # — mismo criterio que Database.resumen_ndvi_finca(): los
            # códigos legacy (numéricos/L/G) no son potreros reales/actuales
            # de la finca (confirmado por el usuario contra el reporte
            # nativo de Software Ganadero SG) y no deben listarse como si
            # fueran potreros activos.
            potreros = _filas_dict(db.query(
                "SELECT id, nombre, codigo, area_has, dias_ocupacion, dias_reposo, "
                "fecha_entrada, fecha_salida FROM potreros "
                "WHERE geom_wkt_4326 IS NOT NULL ORDER BY nombre"))
        except Exception:
            potreros = []
        for p in potreros:
            oc = p.get("dias_ocupacion")
            try:
                oc_i = int(oc) if oc is not None else None
            except Exception:
                oc_i = None
            # Semáforo Voisin: 1-3 verde, 4-6 amarillo, ≥7 rojo.
            p["semaforo"] = ("🟢" if (oc_i is not None and oc_i <= 3)
                             else "🟡" if (oc_i is not None and oc_i <= 6)
                             else "🔴" if oc_i is not None else "⚪")
        try:
            ndvi = _filas_dict(db.query(
                """SELECT p.nombre potrero, n.fecha, n.ndvi_promedio FROM monitoreo_satelital_ndvi n
                   JOIN potreros p ON p.id = n.potrero_id ORDER BY n.fecha DESC LIMIT 10"""))
        except Exception:
            ndvi = []
        return {"potreros": potreros, "ndvi_reciente": ndvi}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_leche(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Leche: serie del tanque (produccion_leche) + últimos controles."""
    db = _db(db_path)
    try:
        try:
            serie = _filas_dict(db.query(
                "SELECT fecha, SUM(litros) litros FROM produccion_leche "
                "GROUP BY fecha ORDER BY fecha DESC LIMIT 30"))
            serie = list(reversed(serie))
        except Exception:
            serie = []
        try:
            controles = _filas_dict(db.query(
                """SELECT a.tag, l.fecha, l.litros FROM produccion_leche l
                   LEFT JOIN animales a ON a.id_animal = l.animal_id
                   ORDER BY l.fecha DESC LIMIT 20"""))
        except Exception:
            controles = []
        return {"serie_tanque": serie, "controles": controles}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_ficha(tag: str, db_path: str = DB_PATH_DEFAULT) -> dict:
    """Ficha animal: header + historial resumido + QR payload (abre /ficha/<tag>)."""
    db = _db(db_path)
    try:
        t = str(tag or "").strip()
        aid = db.resolve_animal(t)
        if aid is None:
            return {"existe": False, "tag": t}
        an = db.get_animal(aid)
        base = {"existe": True, "tag": an["tag"], "nombre": an["nombre"],
                "sexo": an["sexo"], "raza": an["raza"],
                "fecha_nacimiento": an["fecha_nacimiento"], "estado": an["estado"],
                "qr_payload": f"JA://animal/{an['tag']}", "qr_url": f"/ficha/{an['tag']}"}
        try:
            base["ultimo_parto"] = dict(db.ultimo_parto(aid)) if db.ultimo_parto(aid) else None
        except Exception:
            base["ultimo_parto"] = None
        try:
            base["ultimo_servicio"] = dict(db.ultimo_servicio(aid)) if db.ultimo_servicio(aid) else None
        except Exception:
            base["ultimo_servicio"] = None
        try:
            base["pesajes"] = _filas_dict(db.query(
                "SELECT fecha, peso_kg, gmd_calculada FROM pesajes WHERE animal_id = ? "
                "ORDER BY fecha DESC LIMIT 5", (aid,)))
        except Exception:
            base["pesajes"] = []
        try:
            base["tratamientos"] = _filas_dict(db.query(
                "SELECT fecha, producto, dosis, fecha_fin_retiro_leche, fecha_fin_retiro_carne "
                "FROM tratamientos WHERE animal_id = ? ORDER BY fecha DESC LIMIT 5", (aid,)))
        except Exception:
            base["tratamientos"] = []
        try:
            fotos = db.fotos_de(aid, limit=3)
            base["fotos"] = [
                {"fecha": f["fecha"], "caption": f["caption"],
                 "url": f"/media/{_ruta_relativa_media(f['ruta'])}" if f["ruta"] else None}
                for f in fotos
            ]
        except Exception:
            base["fotos"] = []
        return base
    finally:
        try:
            db.close()
        except Exception:
            pass


# ------------------------------------------------------------------ #
# App Flask (solo se construye si Flask está instalado)
# ------------------------------------------------------------------ #
def crear_app(db_path: str = DB_PATH_DEFAULT, users_file: str = USERS_FILE_DEFAULT,
             password: Optional[str] = None):
    """Construye la app Flask. Devuelve None si Flask no está instalado.

    `password`: para tests/uso programático; si no se pasa, se lee de
    `PWA_PASSWORD` (variable de entorno) al momento de crear la app.
    """
    if not _FLASK_OK:
        return None
    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"),
                static_folder=os.path.join(BASE_DIR, "static"))
    app.secret_key = _obtener_secret_key()
    clave_esperada = password if password is not None else PWA_PASSWORD

    # Rutas que no requieren sesión iniciada (nombres de endpoint de Flask,
    # es decir el nombre de la función de vista, no la URL).
    _RUTAS_PUBLICAS = {"login_form", "login_submit", "static", "manifest"}

    def _rol_actual() -> Optional[str]:
        if session is None:
            return None
        uid = session.get("user_id")
        return _rol_de(uid, users_file) if uid else None

    @app.before_request
    def _requerir_login():
        if request is None or request.endpoint in _RUTAS_PUBLICAS:
            return None
        if session.get("autenticado"):
            return None
        if request.path.startswith("/api/") or request.path.startswith("/media/"):
            return jsonify({"error": "No autenticado. Inicie sesión en /login."}), 401
        return redirect("/login")

    @app.get("/login")
    def login_form():
        if not clave_esperada:
            return (
                "⚠️ PWA_PASSWORD no está configurada en el entorno (.env). "
                "El dashboard permanece bloqueado hasta que se configure una "
                "contraseña — no se sirve sin autenticación.",
                503,
            )
        return render_template("login.html", error=request.args.get("error"))

    @app.post("/login")
    def login_submit():
        if not clave_esperada:
            return (
                "⚠️ PWA_PASSWORD no está configurada en el entorno (.env).",
                503,
            )
        intento = (request.form.get("password") or "").strip()
        # Comparación en tiempo constante: evita filtrar la contraseña por
        # cuánto tarda la respuesta (timing attack), aunque el riesgo real
        # aquí es bajo (red local), es una buena práctica sin costo.
        if intento and hmac.compare_digest(intento, clave_esperada):
            session["autenticado"] = True
            session["user_id"] = (request.form.get("user_id") or "").strip() or None
            return redirect("/")
        return redirect("/login?error=1")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/ficha/<tag>")
    def ficha(tag):
        return render_template("ficha.html", tag=tag)

    @app.get("/manifest.json")
    def manifest():
        return app.send_static_file("manifest.json")

    @app.get("/api/tablero")
    def api_tablero():
        pot = (request.args.get("potrero") or "").strip() or None
        out = datos_tablero(db_path, potrero=pot)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/repro")
    def api_repro():
        out = datos_repro(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/sanidad")
    def api_sanidad():
        out = datos_sanidad(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/pasturas")
    def api_pasturas():
        out = datos_pasturas(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/leche")
    def api_leche():
        out = datos_leche(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/ficha/<tag>")
    def api_ficha(tag):
        out = datos_ficha(tag, db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/grafico/<tipo>")
    def api_grafico(tipo):
        generadores = _generadores_graficos_pwa()
        generador = generadores.get(tipo)
        if generador is None:
            abort(404)

        # Caché por tipo (independiente del nombre de archivo que use cada
        # generador internamente): si ya hay una copia servida hace menos
        # de CACHE_GRAFICOS_SEGUNDOS, se devuelve sin volver a renderizar.
        cache_path = os.path.join(REPORTES_DIR_DEFAULT, f"_pwa_cache_{tipo}.png")
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
            from ..engine.charts import graficos_disponibles
        except ImportError:  # ejecución directa: python src/pwa/app.py
            from src.engine.charts import graficos_disponibles  # type: ignore

        if not graficos_disponibles():
            abort(404)
        db_graf = _db(db_path)
        try:
            ruta = generador(db_graf, output_dir=REPORTES_DIR_DEFAULT)
        finally:
            db_graf.close()
        if not ruta or not os.path.isfile(ruta):
            abort(404)
        try:
            shutil.copyfile(ruta, cache_path)
        except Exception:
            cache_path = ruta  # si falla la copia, se sirve igual el original
        return send_file(os.path.abspath(cache_path), mimetype="image/png")

    @app.get("/media/<path:rel>")
    def media(rel):
        # send_from_directory ya previene path traversal (rechaza "..").
        media_root = os.path.join(RAIZ_PROYECTO, MEDIA_DIR_DEFAULT)
        return send_from_directory(media_root, rel)

    return app


# Objeto estándar para `flask run` / tests. None si Flask falta (no rompe el bot).
try:
    app = crear_app()
except Exception:
    app = None


if __name__ == "__main__":  # pragma: no cover
    # Refuerzo anti-cp1252 al arrancar (por si stdout fue redirigido).
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    # 1) Flask ausente: mensaje claro en español, sin traceback feo.
    if not _FLASK_OK:
        print("❌ Flask no está instalado.", flush=True)
        print("   Instálelo con:  pip install flask", flush=True)
        print("   Luego arranque de nuevo con:  python src/pwa/app.py", flush=True)
        raise SystemExit(2)
    # 2) Releer entorno aquí (no solo en import) para PWA_HOST/PWA_PORT.
    _db_arg = os.getenv("BITACORA_DB", DB_PATH_DEFAULT)
    _host = os.getenv("PWA_HOST", PWA_HOST_DEFAULT) or "0.0.0.0"
    try:
        _puerto = int(os.getenv("PWA_PORT", str(PUERTO)))
    except ValueError:
        print("❌ PWA_PORT inválido (debe ser un número, ej. 8080).", flush=True)
        print("   Ejemplo:  set PWA_PORT=8080  (o $env:PWA_PORT=8080 en PowerShell)", flush=True)
        raise SystemExit(2)
    # 3) DB ausente: mensaje claro, sin traceback.
    _db_real = _resolver_db_existente(_db_arg)
    if _db_real is None:
        print(f"❌ No se encontró la base de datos: {_db_arg}", flush=True)
        print(f"   Verifique que existe: {os.path.join(RAIZ_PROYECTO, 'data', 'bitacora.db')}", flush=True)
        print("   Si la DB está en otra ruta, arranque con:", flush=True)
        print('     set BITACORA_DB=ruta\\a\\bitacora.db  (o $env:BITACORA_DB="ruta/a/bitacora.db")', flush=True)
        print("   Y restaure con:  bash scripts/importar_backup.sh /tmp/<copia>.zip", flush=True)
        raise SystemExit(1)
    print(f"ℹ️  DB: {_db_real} | Host: {_host} | Puerto: {_puerto}", flush=True)
    if not PWA_PASSWORD:
        print("⚠️  PWA_PASSWORD no está configurada en .env — el dashboard quedará", flush=True)
        print("   bloqueado (sin login) hasta que la defina. Vea .env.example.", flush=True)
    _app = crear_app(_db_arg)
    if _app is None:
        print("❌ No se pudo crear la app Flask (Flask no disponible).", flush=True)
        print("   Instálelo con:  pip install flask", flush=True)
        raise SystemExit(2)
    _imprimir_banner(_host, _puerto)
    try:
        _app.run(host=_host, port=_puerto, debug=False)
    except OSError as e:
        # 4) Puerto ocupado (WinError 10048 / errno 48/98): mensaje accionable.
        msg = str(e).lower()
        if ("address already in use" in msg or "only one usage" in msg
                or "10048" in msg or getattr(e, "errno", None) in (48, 98, 10048)):
            print(f"❌ El puerto {_puerto} ya está ocupado (quizás la PWA ya corre).", flush=True)
            print("   Opciones:", flush=True)
            print(f"     1) Abra la que ya corre:  http://localhost:{_puerto}", flush=True)
            print(f"     2) Use otro puerto:  set PWA_PORT={_puerto + 1}  y arranque de nuevo", flush=True)
            print('        En PowerShell:  $env:PWA_PORT="8081"; python src/pwa/app.py', flush=True)
            raise SystemExit(3)
        raise
