"""Backend Flask liviano del Dashboard PWA ejecutivo — Fase 7 Etapa D.

Solo lectura: cada endpoint es un envoltorio fino sobre ``db.query`` /
``db.query_one`` (nunca ``execute`` de escritura). Reusa RBAC de
``users.json`` para lectura de roles. Puerto 8080.

Si Flask no está instalado el módulo se importa sin romper el bot
(import lazy / try): ``app`` queda como stub y ``crear_app`` devuelve None.
"""
from __future__ import annotations

import json
import logging
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
import mimetypes
import secrets
from typing import Any, Optional

# Flask sirve /static con mimetypes.guess_type; .woff2 no viene registrado y
# se entregaría como application/octet-stream, que algunos navegadores
# rechazan en @font-face. Registro explícito aquí (global).
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")

try:
    from ..db.database import Database
    from ..engine.dashboard_data import (
        _filas_dict as _filas_dict,
        _ruta_relativa_media as _ruta_relativa_media,
        conteos_tablero as _conteos_tablero,
        datos_agenda as _datos_agenda,
        datos_badges as _datos_badges,
        datos_buscar as _datos_buscar,
        datos_ficha_animal as _datos_ficha_animal,
        datos_genetica as _datos_genetica,
        datos_inventario as _datos_inventario,
        datos_leche as _datos_leche,
        datos_pasturas as _datos_pasturas,
        datos_poblacion as _datos_poblacion,
        datos_reproduccion as _datos_reproduccion,
        datos_sanidad as _datos_sanidad,
        resolver_tag_flexible as _resolver_tag_flexible,
    )
except ImportError:  # ejecución directa: python src/pwa/app.py
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.db.database import Database  # type: ignore
    from src.engine.dashboard_data import (  # type: ignore
        _filas_dict as _filas_dict,
        _ruta_relativa_media as _ruta_relativa_media,
        conteos_tablero as _conteos_tablero,
        datos_agenda as _datos_agenda,
        datos_badges as _datos_badges,
        datos_buscar as _datos_buscar,
        datos_ficha_animal as _datos_ficha_animal,
        datos_genetica as _datos_genetica,
        datos_inventario as _datos_inventario,
        datos_leche as _datos_leche,
        datos_pasturas as _datos_pasturas,
        datos_poblacion as _datos_poblacion,
        datos_reproduccion as _datos_reproduccion,
        datos_sanidad as _datos_sanidad,
        resolver_tag_flexible as _resolver_tag_flexible,
    )

logger = logging.getLogger(__name__)

__all__ = ["_ruta_relativa_media"]  # re-export compat WS-2 (fuente: engine.dashboard_data)

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
REPORTES_DIR_DEFAULT = os.path.join(RAIZ_PROYECTO, "data", "reportes")
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


# _ruta_relativa_media y _filas_dict se importan desde engine.dashboard_data
# (fuente única WS-2) y se re-exportan aquí para compatibilidad vía pwa.app.


# ------------------------------------------------------------------ #
# Consultas de lectura (envoltorios finos, siempre estado='ACTIVO')
# ------------------------------------------------------------------ #
def datos_tablero(db_path: str = DB_PATH_DEFAULT, potrero: Optional[str] = None) -> dict:
    """Tablero finca: activos por categoría, eventos 7d, retiros activos."""
    # Envoltorio fino WS-2: el SQL vive en engine.dashboard_data.conteos_tablero.
    db = _db(db_path)
    try:
        try:
            return _conteos_tablero(db, potrero=potrero)
        except Exception:
            logger.exception("datos_tablero fallo completo")
            return {
                "activos": 0, "hembras": 0, "machos": 0,
                "partos_7d": 0, "celos_7d": 0, "servicios_7d": 0,
                "retiros_activos": 0, "por_potrero": [],
                "potrero_filtro": potrero, "errores": {"tablero": "error interno"},
            }
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_repro(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Reproducción: FEP≤30d, eco d35 / palpación d60, celos AM-PM pendientes."""
    # Envoltorio fino WS-2: el SQL vive en engine.dashboard_data.datos_reproduccion.
    db = _db(db_path)
    try:
        try:
            return _datos_reproduccion(db)
        except Exception:
            logger.exception("datos_repro fallo completo")
            return {"fep_30d": [], "celos_recientes": [], "diagnosticos": [],
                    "eco_palp_pendientes": [], "errores": {"repro": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_sanidad(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Sanidad: retiros leche/carne con cuenta regresiva + últimos tratamientos."""
    # Envoltorio fino WS-2: el SQL vive en engine.dashboard_data.datos_sanidad.
    db = _db(db_path)
    try:
        try:
            return _datos_sanidad(db)
        except Exception:
            logger.exception("datos_sanidad fallo completo")
            return {"retiros": [], "ultimos_tratamientos": [],
                    "errores": {"sanidad": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_pasturas(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Pasturas: ocupación Voisin (semáforo), reposo y último NDVI."""
    # Envoltorio fino WS-2: el SQL vive en engine.dashboard_data.datos_pasturas.
    db = _db(db_path)
    try:
        try:
            return _datos_pasturas(db)
        except Exception:
            logger.exception("datos_pasturas fallo completo")
            return {"potreros": [], "ndvi_reciente": [],
                    "errores": {"pasturas": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_leche(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Leche: serie del tanque (produccion_leche) + últimos controles."""
    # Envoltorio fino WS-2: el SQL vive en engine.dashboard_data.datos_leche.
    db = _db(db_path)
    try:
        try:
            return _datos_leche(db)
        except Exception:
            logger.exception("datos_leche fallo completo")
            return {"serie_tanque": [], "controles": [],
                    "errores": {"leche": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_ficha(tag: str, db_path: str = DB_PATH_DEFAULT) -> dict:
    """Ficha animal: header + historial resumido + QR payload (abre /ficha/<tag>)."""
    # Envoltorio fino WS-2: el SQL vive en engine.dashboard_data.datos_ficha_animal.
    db = _db(db_path)
    try:
        try:
            return _datos_ficha_animal(db, tag)
        except Exception:
            logger.exception("datos_ficha fallo completo")
            return {"existe": False, "tag": str(tag or "").strip(),
                    "errores": {"ficha": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_inventario(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Inventario SG: brackets etarios (misma fuente que /animales del bot)."""
    db = _db(db_path)
    try:
        try:
            return _datos_inventario(db)
        except Exception:
            logger.exception("datos_inventario fallo completo")
            return {"filas": [], "total_activos": 0, "total_hembras": 0,
                    "total_machos": 0, "total_sin_sexo": 0, "terneros_menor_12m": 0,
                    "errores": {"inventario": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_poblacion(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Población / edades: brackets + edad promedio del hato activo."""
    db = _db(db_path)
    try:
        try:
            return _datos_poblacion(db)
        except Exception:
            logger.exception("datos_poblacion fallo completo")
            return {"filas": [], "total_activos": 0, "total_hembras": 0,
                    "total_machos": 0, "edad_promedio": None,
                    "errores": {"poblacion": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_genetica(db_path: str = DB_PATH_DEFAULT) -> dict:
    """Genética: distribución por raza del hato activo."""
    db = _db(db_path)
    try:
        try:
            return _datos_genetica(db)
        except Exception:
            logger.exception("datos_genetica fallo completo")
            return {"filas": [], "total": 0,
                    "errores": {"genetica": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_agenda(db_path: str = DB_PATH_DEFAULT, dias: int = 7) -> dict:
    """Agenda próxima: alertas PENDIENTES (partos, eco, palpación, secado, N₂)."""
    db = _db(db_path)
    try:
        try:
            return _datos_agenda(db, dias=dias)
        except Exception:
            logger.exception("datos_agenda fallo completo")
            return {"dias": dias, "eventos": [], "retiros": [],
                    "errores": {"agenda": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_buscar(db_path: str = DB_PATH_DEFAULT, q: str = "", limite: int = 8) -> dict:
    """Autocompletar de animales/potreros para el buscador del dashboard."""
    db = _db(db_path)
    try:
        try:
            return _datos_buscar(db, q=q, limite=limite)
        except Exception:
            logger.exception("datos_buscar fallo completo")
            return {"animales": [], "potreros": [],
                    "errores": {"buscar": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_badges(db_path: str = DB_PATH_DEFAULT, dias: int = 7) -> dict:
    """Contadores para los badges de la navegación (Agenda/Repro/Sanidad)."""
    db = _db(db_path)
    try:
        try:
            return _datos_badges(db, dias=dias)
        except Exception:
            logger.exception("datos_badges fallo completo")
            return {"agenda": 0, "repro": 0, "sanidad": 0, "dias": dias,
                    "errores": {"badges": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


# Generadores de gráficos por animal (whitelist, patrón idéntico al de
# /api/grafico/<tipo>): solo estas claves fijas se pueden pedir por URL.
def _generadores_graficos_ficha():
    try:
        from ..engine import charts
    except ImportError:  # ejecución directa: python src/pwa/app.py
        from src.engine import charts  # type: ignore
    return {
        "peso": charts.generar_grafico_peso,
        "lactancia": charts.generar_grafico_lactancia,
    }


def _identificar_foto(db: Database, foto_bytes: bytes, ext: str = ".jpg") -> dict:
    """Ejecuta detección de arete (visión + OCR) sobre una foto subida.

    Lee SOLO la imagen (no persiste en BD ni en media/): guarda un temporal
    en el directorio del sistema, llama a ``detectar_arete_avanzado`` (el
    mismo pipeline del bot de Telegram para fotos de aretes) y resuelve el
    candidato contra la base. Si OCR no está disponible (sin tesseract/
    easyocr) la detección degrada a ``texto_bruto=""`` sin romper nada.
    """
    import tempfile
    from datetime import datetime

    from ..vision.arete_detector import detectar_arete_avanzado
    ext = (ext or ".jpg").lower()
    if not ext.startswith("."):
        ext = "." + ext
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"bitacora_ident_{datetime.now().strftime('%H%M%S')}_",
            suffix=ext, delete=False,
        ) as f:
            f.write(foto_bytes or b"")
            tmp_path = f.name
        det = detectar_arete_avanzado(tmp_path) or {}
        tag_candidato = (det.get("tag") or "").strip() or None
        resultado: dict[str, Any] = {
            "ocr_tag": tag_candidato,
            "ocr_texto": (det.get("texto_bruto") or "")[:200],
            "confianza": det.get("confianza") or 0.0,
            "tipo_arete": det.get("tipo_arete") or "DESCONOCIDO",
        }
        if tag_candidato:
            res = _resolver_tag_flexible(db, tag_candidato)
            resultado.update(res)
            resultado["candidato_leido"] = tag_candidato
        else:
            resultado.update({"existe": False, "sugerencias": []})
            resultado["mensaje"] = (
                "No se pudo leer el arete en la foto (¿muy lejos, oscura o sin "
                "tesseract/easyocr en el servidor?). Pruebe con mejor luz o "
                "escribiendo el arete/RFID en el campo de texto."
            )
        return resultado
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def datos_identificar(db_path: str = DB_PATH_DEFAULT, texto: Optional[str] = None,
                      foto_bytes: Optional[bytes] = None, foto_ext: str = ".jpg") -> dict:
    """Identifica un animal por arete/RFID (texto) o por foto del arete (OCR)."""
    db = _db(db_path)
    try:
        if texto:
            return _resolver_tag_flexible(db, str(texto).strip())
        if not foto_bytes:
            return {"existe": False, "error": "Sin foto ni texto para identificar."}
        try:
            return _identificar_foto(db, foto_bytes, ext=foto_ext)
        except Exception:
            logger.exception("datos_identificar foto fallo completo")
            return {"existe": False, "mensaje": "Error procesando la foto.",
                    "errores": {"foto": "error interno"}}
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
    _RUTAS_PUBLICAS = {"login_form", "login_submit", "static", "manifest", "sw_js", "offline_page"}

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

    @app.errorhandler(500)
    def error_interno(_e):
        logger.exception("error interno PWA")
        try:
            p = request.path if request is not None else ""
        except Exception:
            p = ""
        if p.startswith("/api/") or p.startswith("/media/"):
            return jsonify({"error": "Error interno del servidor"}), 500
        return "Error interno del servidor", 500

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
        resp = redirect("/login")
        # Respaldo del lado del servidor al borrado de caché en JS (app.js):
        # si el navegador soporta Clear-Site-Data, esto limpia la caché del
        # Service Worker aunque JS esté deshabilitado o el logout se dispare
        # por navegación directa (sin pasar por el listener de app.js). En
        # un equipo compartido, sin esto alguien podría ver offline los
        # datos de la finca cacheados por la sesión anterior tras cerrarla.
        resp.headers["Clear-Site-Data"] = '"cache", "storage"'
        return resp

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/ficha/<tag>")
    def ficha(tag):
        return render_template("ficha.html", tag=tag)

    @app.get("/manifest.json")
    def manifest():
        return app.send_static_file("manifest.json")

    @app.get("/sw.js")
    def sw_js():
        # El service worker debe servirse en la raíz de su scope ("/") y sin
        # caché HTTP (los navegadores lo revalidan agresivamente). Público.
        resp = app.send_static_file("sw.js")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
        return resp

    @app.get("/offline.html")
    def offline_page():
        # Página de respaldo para el SW (navegación offline). Público.
        resp = app.send_static_file("offline.html")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

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

    @app.get("/api/agenda")
    def api_agenda():
        try:
            dias = int(request.args.get("dias") or 7)
        except (TypeError, ValueError):
            dias = 7
        dias = max(1, min(dias, 60))
        out = datos_agenda(db_path, dias=dias)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/buscar")
    def api_buscar():
        q = (request.args.get("q") or "").strip()
        out = datos_buscar(db_path, q=q)
        return jsonify(out)

    @app.get("/api/badges")
    def api_badges():
        # Contadores ligeros para los badges de la navegación (Agenda/Repro/Sanidad).
        try:
            dias = int(request.args.get("dias") or 7)
        except (TypeError, ValueError):
            dias = 7
        out = datos_badges(db_path, dias=max(1, min(dias, 60)))
        return jsonify(out)

    @app.post("/api/identificar")
    def api_identificar():
        # Identificación por texto (arete/RFID/lector de corral) o foto del
        # arete. SOLO LECTURA: nunca inserta ni actualiza registros.
        texto = (request.form.get("texto") or "").strip() or None
        foto = request.files.get("foto") if request.files else None
        if not texto and (foto is None or not foto.filename):
            return jsonify({"existe": False, "error": "Envíe 'texto' (arete/RFID) o un archivo 'foto'."}), 400
        if foto is not None and foto.filename:
            ext = os.path.splitext(foto.filename)[1] or ".jpg"
            out = datos_identificar(db_path, foto_bytes=foto.read(), foto_ext=ext)
        else:
            out = datos_identificar(db_path, texto=texto)
        out["rol"] = _rol_actual()
        return jsonify(out)

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
            cache_path = os.path.join(REPORTES_DIR_DEFAULT,
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
                from ..engine.charts import graficos_disponibles
            except ImportError:  # ejecución directa
                from src.engine.charts import graficos_disponibles  # type: ignore
            if not graficos_disponibles():
                abort(404)
            ruta = generador(db_graf, tag, output_dir=REPORTES_DIR_DEFAULT)
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

    def _servir() -> None:
        """Sirve la app con waitress (WSGI de producción, multi-hilo) si está
        instalado; si no, cae al servidor de desarrollo de Flask con un aviso
        (útil en local; nunca recomendado para VPS expuesto)."""
        try:
            from waitress import serve  # type: ignore

            print("▶️  Servidor WSGI: waitress (producción, multi-hilo)", flush=True)
            serve(_app, host=_host, port=_puerto, threads=8)
            return
        except ImportError:
            print(
                "⚠️  waitress no está instalado — usando el servidor de desarrollo "
                "de Flask (solo para local). En producción instale:  pip install waitress\n",
                flush=True,
            )
        _app.run(host=_host, port=_puerto, debug=False)

    try:
        _servir()
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
