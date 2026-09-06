"""Backend Flask liviano del Dashboard PWA ejecutivo — Fase 7 Etapa D+.

Empezó siendo solo lectura; desde la unificación de sincronización offline
(``/api/sync``, ``/api/manga/*``, ``/api/gps/*``) también escribe eventos de
campo (pesajes, tratamientos, traslados, rondas GPS...) reusando las mismas
funciones ``registrar_*`` de ``Database`` que ya usa el bot de Telegram.
Reusa RBAC de ``users.json`` para lectura de roles. Puerto 8080.

Si Flask no está instalado el módulo se importa sin romper el bot
(import lazy / try): ``app`` queda como stub y ``crear_app`` devuelve None.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import sys
import threading
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
from datetime import date, datetime
import hmac
import mimetypes
import secrets
from typing import Any, Optional

_RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ_REPO not in sys.path:
    sys.path.insert(0, _RAIZ_REPO)

try:
    from ..utils import iso, to_date
except (ImportError, ValueError):
    from src.utils import iso, to_date  # type: ignore

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

DB_PATH_DEFAULT = os.getenv("BITACORA_DB", os.path.join(RAIZ_PROYECTO, "data", "bitacora.db"))
USERS_FILE_DEFAULT = os.getenv("USERS_FILE", os.path.join(RAIZ_PROYECTO, "src", "server", "users.json"))
MEDIA_DIR_DEFAULT = os.getenv("MEDIA_DIR", os.path.join(RAIZ_PROYECTO, "media"))
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
        # Extras (WS 2): gráficos de hato/leche/población que faltaban en la PWA.
        "gmd_hato": charts.generar_grafico_gmd_hato,
        "ranking_vacas_leche": charts.generar_grafico_ranking_vacas_leche,
        "waterfall_inventario": charts.generar_grafico_waterfall_inventario,
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

    try:
        from ..vision.arete_detector import detectar_arete_avanzado
    except (ImportError, ValueError):
        from src.vision.arete_detector import detectar_arete_avanzado  # type: ignore
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

    # Asegurar tablas e índices en la base de datos (migración idempotente al inicio)
    try:
        if db_path and db_path != ":memory:":
            _db_exist = _resolver_db_existente(db_path)
            if _db_exist:
                _dbtmp = Database(_db_exist)
                _dbtmp.create_tables()
                _dbtmp.close()
    except Exception:
        logger.exception("No se pudo ejecutar la migración idempotente de tablas al iniciar PWA")

    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"),
                static_folder=os.path.join(BASE_DIR, "static"))
    app.secret_key = _obtener_secret_key()
    clave_esperada = password if password is not None else PWA_PASSWORD

    # Rutas que no requieren sesión iniciada (nombres de endpoint de Flask,
    # es decir el nombre de la función de vista, no la URL).
    _RUTAS_PUBLICAS = {"login_form", "login_submit", "static", "manifest", "sw_js", "offline_page"}

    # Rate limit del login: el PIN individual son solo 4 dígitos (10.000
    # combinaciones) guardado en texto plano en users.json -- sin esto
    # cualquiera con acceso a /login (la app está expuesta a internet, no
    # solo LAN) podría fuerza-bruta un PIN en segundos. Estado en memoria
    # por proceso (alcanza para un solo droplet/worker); se resetea si el
    # servicio reinicia, lo cual es aceptable para este caso de uso.
    _login_lock = threading.Lock()
    _login_intentos: dict[str, list[float]] = {}
    _LOGIN_MAX_INTENTOS = 8
    _LOGIN_VENTANA_SEG = 60.0

    def _cliente_ip() -> str:
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        return request.remote_addr or "desconocido"

    def _login_bloqueado(ip: str) -> bool:
        ahora = time.time()
        with _login_lock:
            vivos = [t for t in _login_intentos.get(ip, ()) if ahora - t < _LOGIN_VENTANA_SEG]
            _login_intentos[ip] = vivos
            return len(vivos) >= _LOGIN_MAX_INTENTOS

    def _login_registrar_intento(ip: str) -> None:
        with _login_lock:
            _login_intentos.setdefault(ip, []).append(time.time())

    def _rol_actual() -> Optional[str]:
        if session is None:
            return None
        rol_sesion = session.get("rol")
        if rol_sesion:
            return str(rol_sesion).strip().upper()
        uid = session.get("user_id")
        return _rol_de(uid, users_file) if uid else None

    def _usuario_actual() -> dict[str, Any]:
        if session is None:
            return {"autenticado": False, "rol": None, "nombre": None, "user_id": None}
        rol_act = _rol_actual() or "TRABAJADOR"
        default_av = "patron" if rol_act == "OWNER" else "admin" if rol_act == "ADMIN" else "vaquero"
        return {
            "autenticado": bool(session.get("autenticado")),
            "rol": rol_act,
            "nombre": session.get("nombre") or "Usuario",
            "user_id": session.get("user_id"),
            "telegram_id": session.get("telegram_id"),
            "avatar": session.get("avatar") or default_av,
        }

    @app.before_request
    def _requerir_login():
        if request is None or request.endpoint in _RUTAS_PUBLICAS:
            return None
        if session.get("autenticado"):
            try:
                db_inst = _db(db_path)
                uid = session.get("user_id") or session.get("nombre")
                nom = session.get("nombre") or ""
                rol = session.get("rol") or "TRABAJADOR"
                ip = _cliente_ip()
                db_inst.registrar_presencia(user_id=uid, nombre=nom, rol=rol, canal="PWA", ip=ip)
                db_inst.close()
            except Exception:
                pass
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
        ip = _cliente_ip()
        if _login_bloqueado(ip):
            return (
                "⚠️ Demasiados intentos fallidos. Espere un minuto e intente de nuevo.",
                429,
            )
        intento = (request.form.get("password") or request.form.get("pin") or "").strip()
        uid_form = (request.form.get("user_id") or "").strip() or None

        # 1. Intentar autenticar por PIN individual de users.json
        try:
            try:
                from ..server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            user_auth = auth_inst.autenticar_pin(intento)
        except Exception as e:
            logger.warning("Fallo autenticando PIN: %s", e)
            user_auth = None

        if user_auth:
            session["autenticado"] = True
            session["user_id"] = user_auth.get("user_id")
            session["telegram_id"] = user_auth.get("telegram_id")
            session["nombre"] = user_auth.get("nombre") or "Usuario"
            session["rol"] = user_auth.get("rol") or "TRABAJADOR"
            session["avatar"] = user_auth.get("avatar") or "vaquero"
            return redirect("/")

        # 2. Intentar autenticar por contraseña maestra (PWA_PASSWORD)
        if clave_esperada and intento and hmac.compare_digest(intento, clave_esperada):
            session["autenticado"] = True
            session["user_id"] = uid_form
            session["rol"] = _rol_de(uid_form, users_file) or "OWNER"
            session["nombre"] = "Propietario" if session["rol"] == "OWNER" else "Usuario"
            session["avatar"] = "patron" if session["rol"] == "OWNER" else "admin"
            return redirect("/")

        _login_registrar_intento(ip)
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

    @app.get("/api/usuario")
    def api_usuario():
        return jsonify(_usuario_actual())

    @app.get("/api/usuarios")
    def api_listar_usuarios():
        rol = _rol_actual()
        if rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403
        try:
            try:
                from ..server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()
            # Si quien consulta es ADMIN, ocultar el PIN de los usuarios OWNER por seguridad
            if rol != "OWNER":
                for u in usuarios:
                    if str(u.get("rol", "")).strip().upper() == "OWNER":
                        u["pin"] = "****"

            # EXCLUSIVO OWNER: adjuntar presencia en vivo
            if rol == "OWNER":
                try:
                    db_u = _db(db_path)
                    presencias = db_u.obtener_usuarios_presencia()
                    db_u.close()
                except Exception:
                    presencias = {}
                for u in usuarios:
                    uid = str(u.get("user_id"))
                    p = presencias.get(uid, {})
                    u["online_info"] = {
                        "en_linea": p.get("en_linea", False),
                        "estado": p.get("estado", "offline"),
                        "canal": p.get("canal", ""),
                        "ip": p.get("ip", ""),
                        "ultima_actividad": p.get("ultima_actividad", ""),
                        "hace_texto": p.get("hace_texto", "Nunca"),
                    }
            return jsonify({"ok": True, "usuarios": usuarios, "mi_rol": rol})
        except Exception as e:
            logger.exception("Error al listar usuarios")
            return jsonify({"error": f"Error al leer usuarios: {e}"}), 500

    @app.get("/api/usuarios/online")
    def api_usuarios_online():
        """Consulta de usuarios conectados en vivo (EXCLUSIVO OWNER)."""
        rol = _rol_actual()
        if rol != "OWNER":
            return jsonify({"error": "Acceso denegado. Solo el rol OWNER puede ver usuarios conectados."}), 403

        db_inst = _db(db_path)
        try:
            presencias = db_inst.obtener_usuarios_presencia()
            try:
                from ..server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()

            resultado = []
            en_linea_cnt = 0
            for u in usuarios:
                uid = str(u.get("user_id"))
                p = presencias.get(uid, {})
                en_linea = p.get("en_linea", False)
                if en_linea:
                    en_linea_cnt += 1
                resultado.append({
                    "user_id": u.get("user_id"),
                    "nombre": u.get("nombre"),
                    "rol": u.get("rol"),
                    "telegram_id": u.get("telegram_id"),
                    "avatar": u.get("avatar"),
                    "en_linea": en_linea,
                    "estado": p.get("estado", "offline"),
                    "canal": p.get("canal", ""),
                    "ip": p.get("ip", ""),
                    "ultima_actividad": p.get("ultima_actividad", ""),
                    "hace_texto": p.get("hace_texto", "Nunca"),
                })
            return jsonify({
                "ok": True,
                "total": len(resultado),
                "en_linea_count": en_linea_cnt,
                "usuarios": resultado,
            })
        finally:
            db_inst.close()

    @app.route("/api/heartbeat", methods=["GET", "POST"])
    def api_heartbeat():
        """Latido para mantener activo el estado de conexión en la PWA."""
        if not session.get("autenticado"):
            return jsonify({"error": "No autenticado"}), 401
        try:
            db_inst = _db(db_path)
            uid = session.get("user_id") or session.get("nombre")
            nom = session.get("nombre") or ""
            rol = session.get("rol") or "TRABAJADOR"
            ip = _cliente_ip()
            db_inst.registrar_presencia(user_id=uid, nombre=nom, rol=rol, canal="PWA", ip=ip)
            db_inst.close()
        except Exception:
            pass
        return jsonify({"ok": True})

    @app.post("/api/usuarios")
    def api_guardar_usuario():
        mi_rol = _rol_actual()
        if mi_rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403

        datos = request.get_json(silent=True) or request.form
        nombre = (datos.get("nombre") or "").strip()
        rol_nuevo = str(datos.get("rol") or "TRABAJADOR").strip().upper()
        pin = str(datos.get("pin") or "").strip()
        uid_raw = datos.get("user_id")
        tg_id_raw = datos.get("telegram_id")
        avatar = str(datos.get("avatar") or "").strip() or None

        tg_id = None
        if tg_id_raw is not None and str(tg_id_raw).strip() != "":
            try:
                tg_id = int(tg_id_raw)
            except (ValueError, TypeError):
                return jsonify({"error": "El ID de Telegram debe ser un número entero (ej. 6123051140)."}), 400

        if not nombre:
            return jsonify({"error": "El nombre del usuario es obligatorio."}), 400
        if rol_nuevo not in ("OWNER", "ADMIN", "TRABAJADOR"):
            return jsonify({"error": f"Rol inválido: {rol_nuevo}. Permitidos: OWNER (Level 1), ADMIN (Level 2), TRABAJADOR (Level 3)."}), 400

        # Un ADMIN no puede crear usuarios OWNER ni auto-promocionarse
        if mi_rol != "OWNER" and rol_nuevo == "OWNER":
            return jsonify({"error": "Solo un OWNER (Level 1) puede crear o asignar el rol OWNER."}), 403

        # Validar PIN: 4 dígitos numéricos
        if not re.match(r"^\d{4}$", pin):
            return jsonify({"error": "El PIN debe tener exactamente 4 dígitos numéricos (ej. 4521)."}), 400

        try:
            try:
                from ..server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()

            # Resolver o generar ID local secuencial (1, 2, 3...)
            if uid_raw:
                try:
                    uid = int(uid_raw)
                except (ValueError, TypeError):
                    return jsonify({"error": "user_id debe ser un entero numérico."}), 400
            else:
                ids_existentes = [int(u.get("user_id", 0)) for u in usuarios if isinstance(u.get("user_id"), int) and int(u.get("user_id", 0)) < 1000000]
                uid = (max(ids_existentes) + 1) if ids_existentes else 1

            # Si es ADMIN y está editando un usuario existente, no puede editar a un OWNER
            if mi_rol != "OWNER":
                for u in usuarios:
                    if u.get("user_id") == uid and str(u.get("rol", "")).strip().upper() == "OWNER":
                        return jsonify({"error": "Un ADMIN no puede modificar a un usuario OWNER (Level 1)."}), 403

            # Verificar que el PIN no esté en colisión con OTRO usuario
            for u in usuarios:
                if u.get("user_id") != uid and str(u.get("pin", "")).strip() == pin:
                    return jsonify({"error": f"El PIN '{pin}' ya está en uso por '{u.get('nombre')}'. Cada usuario debe tener un PIN único."}), 400

            auth_inst.agregar_usuario(
                user_id=uid,
                nombre=nombre,
                rol=rol_nuevo,
                pin=pin,
                telegram_id=tg_id,
                avatar=avatar,
            )
            return jsonify({
                "ok": True,
                "mensaje": f"Usuario '{nombre}' (Level {1 if rol_nuevo=='OWNER' else 2 if rol_nuevo=='ADMIN' else 3}) guardado exitosamente.",
                "usuario": {
                    "user_id": uid,
                    "telegram_id": tg_id,
                    "nombre": nombre,
                    "rol": rol_nuevo,
                    "pin": pin,
                    "avatar": avatar or ("patron" if rol_nuevo=="OWNER" else "admin" if rol_nuevo=="ADMIN" else "vaquero"),
                }
            })
        except Exception as e:
            logger.exception("Error al guardar usuario")
            return jsonify({"error": str(e)}), 400

    @app.post("/api/usuarios/<int:target_uid>/pin")
    def api_cambiar_pin_usuario(target_uid: int):
        mi_rol = _rol_actual()
        if mi_rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403

        datos = request.get_json(silent=True) or request.form
        nuevo_pin = str(datos.get("pin") or "").strip()
        if not re.match(r"^\d{4}$", nuevo_pin):
            return jsonify({"error": "El nuevo PIN debe tener exactamente 4 dígitos numéricos."}), 400

        try:
            try:
                from ..server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()

            # Si es ADMIN, no puede cambiarle el PIN a un OWNER
            if mi_rol != "OWNER":
                for u in usuarios:
                    if u.get("user_id") == target_uid and str(u.get("rol", "")).strip().upper() == "OWNER":
                        return jsonify({"error": "Un ADMIN no puede modificar el PIN de un OWNER."}), 403

            # Verificar colisión de PIN
            for u in usuarios:
                if u.get("user_id") != target_uid and str(u.get("pin", "")).strip() == nuevo_pin:
                    return jsonify({"error": f"El PIN '{nuevo_pin}' ya está en uso por '{u.get('nombre')}'. Ingrese un PIN diferente."}), 400

            auth_inst.asignar_pin(target_uid, nuevo_pin)
            return jsonify({"ok": True, "mensaje": "PIN actualizado exitosamente."})
        except Exception as e:
            logger.exception("Error al cambiar PIN")
            return jsonify({"error": str(e)}), 400

    @app.post("/api/usuarios/<int:target_uid>/eliminar")
    def api_eliminar_usuario(target_uid: int):
        mi_rol = _rol_actual()
        if mi_rol not in ("OWNER", "ADMIN", "ADMINISTRADOR"):
            return jsonify({"error": "Acceso denegado. Se requiere rol ADMIN o OWNER."}), 403

        try:
            try:
                from ..server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth  # type: ignore
            auth_inst = Auth(users_file)
            usuarios = auth_inst.listar_usuarios()

            target_user = next((u for u in usuarios if u.get("user_id") == target_uid), None)
            if not target_user:
                return jsonify({"error": f"Usuario con ID {target_uid} no encontrado."}), 404

            target_rol = str(target_user.get("rol", "")).strip().upper()

            # Si es ADMIN, no puede eliminar OWNER ni otro ADMIN
            if mi_rol != "OWNER" and target_rol in ("OWNER", "ADMIN"):
                return jsonify({"error": "Un ADMIN solo puede eliminar usuarios de rol TRABAJADOR."}), 403

            auth_inst.quitar_usuario(target_uid)
            return jsonify({"ok": True, "mensaje": f"Usuario '{target_user.get('nombre')}' eliminado exitosamente."})
        except Exception as e:
            logger.exception("Error al eliminar usuario")
            return jsonify({"error": str(e)}), 400

    @app.post("/api/sync")
    def api_sync():
        datos = request.get_json(silent=True) or {}
        eventos = datos.get("eventos", [])
        if not isinstance(eventos, list):
            return jsonify({"error": "Se esperaba una lista en 'eventos'."}), 400

        db_sync = _db(db_path)
        procesados = 0
        errores = []
        # IDs locales (los de la cola IndexedDB del cliente) que sí se
        # guardaron -- el cliente solo debe borrar de su cola offline los
        # eventos confirmados aquí. Antes se borraba TODA la cola con solo
        # un HTTP 200 de la petición, aunque un evento individual fallara
        # (ej. tag inexistente): el evento fallido desaparecía de la cola
        # local sin haberse guardado en el servidor -- pérdida de datos de
        # campo silenciosa, sobre todo durante la sincronización automática
        # en segundo plano (sin aviso visible al usuario).
        ids_ok = []
        uid = session.get("user_id")

        try:
            for ev in eventos:
                if not isinstance(ev, dict):
                    continue
                tipo = str(ev.get("tipo", "")).lower().strip()
                payload = ev.get("payload") or {}
                fecha = ev.get("fecha") or payload.get("fecha") or date.today().isoformat()
                id_local = ev.get("id_local")

                try:
                    if tipo == "parto":
                        db_sync.registrar_parto(
                            vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                            fecha=fecha,
                            sexo_cria=payload.get("sexo_cria"),
                            estado_cria=payload.get("estado_cria", "VIVO"),
                            peso_nacimiento=payload.get("peso_nacimiento"),
                            id_cria_tag=payload.get("id_cria_tag"),
                            notas=payload.get("notas"),
                            registrado_por=uid,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "pesaje":
                        db_sync.registrar_pesaje(
                            animal_tag=payload.get("animal_tag") or payload.get("tag"),
                            fecha=fecha,
                            peso_kg=payload.get("peso_kg"),
                            gmd_calculada=payload.get("gmd"),
                            evento=payload.get("evento") or "PESAJE",
                            registrado_por=uid,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "tratamiento":
                        db_sync.registrar_tratamiento(
                            animal_tag=payload.get("animal_tag") or payload.get("tag"),
                            fecha=fecha,
                            producto=payload.get("producto"),
                            principio_activo=payload.get("principio_activo"),
                            dosis=payload.get("dosis"),
                            via=payload.get("via"),
                            dias_retiro_leche=int(payload.get("dias_retiro_leche") or 0),
                            dias_retiro_carne=int(payload.get("dias_retiro_carne") or 0),
                            diagnostico=payload.get("diagnostico"),
                            registrado_por=uid,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "traslado":
                        db_sync.registrar_traslado(
                            animal_tag=payload.get("animal_tag") or payload.get("tag"),
                            fecha=fecha,
                            lote=payload.get("lote"),
                            potrero_origen=payload.get("potrero_origen"),
                            potrero_destino=payload.get("potrero_destino"),
                            motivo=payload.get("motivo"),
                            registrado_por=uid,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "celo":
                        db_sync.registrar_celo(
                            vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                            fecha=fecha,
                            am_pm=payload.get("am_pm"),
                            notas=payload.get("notas"),
                            registrado_por=uid,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "servicio":
                        db_sync.registrar_servicio(
                            vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                            fecha=fecha,
                            tipo_servicio=payload.get("tipo_servicio"),
                            toro_pajilla=payload.get("toro_pajilla"),
                            raza_toro=payload.get("raza_toro"),
                            inseminador=payload.get("inseminador"),
                            fep_calculada=payload.get("fep_calculada"),
                            estado=payload.get("estado"),
                            registrado_por=uid,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "muerte":
                        db_sync.registrar_muerte(
                            animal_tag=payload.get("animal_tag") or payload.get("tag"),
                            fecha=fecha,
                            causa_presunta=payload.get("causa_presunta"),
                            notas=payload.get("notas"),
                            registrado_por=uid,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "leche":
                        db_sync.registrar_produccion_leche(
                            fecha=fecha,
                            litros=payload.get("litros"),
                            notas=payload.get("notas"),
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "ronda":
                        db_sync.registrar_ronda_campo(
                            user_id=uid,
                            usuario_nombre=session.get("nombre") or (_rol_actual() or "Usuario"),
                            fecha=fecha,
                            hora=payload.get("hora"),
                            lat=payload.get("lat"),
                            lon=payload.get("lon"),
                            potrero_id=payload.get("potrero_id"),
                            potrero_nombre=payload.get("potrero_nombre"),
                            punto_control=payload.get("punto_control"),
                            notas=payload.get("notas"),
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo in ("telemetria", "telemetria_ping"):
                        db_sync.registrar_telemetria_gps(
                            user_id=uid,
                            usuario_nombre=session.get("nombre") or (_rol_actual() or "Usuario"),
                            rol=_rol_actual() or "TRABAJADOR",
                            lat=payload.get("lat"),
                            lon=payload.get("lon"),
                            precision_m=payload.get("precision_m"),
                            evento_origen=payload.get("evento_origen") or "sync_offline",
                            fecha=fecha,
                            hora=payload.get("hora"),
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    else:
                        errores.append(f"Tipo de evento no reconocido: {tipo}")
                except Exception as e:
                    logger.exception("Error al sincronizar evento %s: %s", id_local, e)
                    errores.append(f"Error en evento {id_local or tipo}: {str(e)}")

            return jsonify({
                "ok": True,
                "procesados": procesados,
                "total": len(eventos),
                "errores": errores,
                "ids_ok": ids_ok,
            })
        finally:
            db_sync.close()

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
                filas_p = db_t.query(
                    "SELECT a.tag FROM animales a JOIN potreros p ON a.potrero_id = p.id "
                    "WHERE (p.nombre = ? OR p.codigo = ?) AND a.estado = 'ACTIVO'",
                    (potrero, potrero),
                )
                tags = [f["tag"] for f in filas_p]
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
                from ..engine.query_engine import QueryEngine
            except ImportError:
                from src.engine.query_engine import QueryEngine  # type: ignore
            qe = QueryEngine(db_q)
            respuesta = qe.responder(pregunta)
            return jsonify({"ok": True, "pregunta": pregunta, "respuesta": respuesta})
        except Exception as e:
            logger.exception("Error al responder pregunta en PWA: %s", e)
            return jsonify({"ok": False, "error": f"Error al procesar consulta: {e}"}), 500
        finally:
            db_q.close()

    @app.post("/api/voz")
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
                    from ..parsers.media_handler import transcribe_audio
                except ImportError:
                    from src.parsers.media_handler import transcribe_audio  # type: ignore
                tr = transcribe_audio(tmp_audio)
                texto_transcripto = tr.texto if tr else ""
            except Exception as e:
                logger.warning("Fallo en transcripción Whisper: %s", e)
                return jsonify({"ok": False, "error": f"No se pudo transcribir el audio: {e}"}), 500

            if not texto_transcripto:
                return jsonify({"ok": False, "error": "No se detectó voz clara en el audio."})

            db_v = _db(db_path)
            try:
                try:
                    from ..bot.bot_interface import Bot
                except ImportError:
                    from src.bot.bot_interface import Bot  # type: ignore
                bot_inst = Bot(db_v)
                respuesta = bot_inst.procesar_texto(texto_transcripto, user_id=session.get("user_id"))
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

        os.makedirs(REPORTES_DIR_DEFAULT, exist_ok=True)
        ruta_salida = os.path.join(REPORTES_DIR_DEFAULT, f"reporte_ja_{periodo}_{int(time.time())}.pdf")

        db_rep = _db(db_path)
        try:
            try:
                from ..reports.pdf_report import generar_pdf
            except ImportError:
                from src.reports.pdf_report import generar_pdf  # type: ignore
            ruta = generar_pdf(db_rep, dias=dias, ruta_salida=ruta_salida, periodo=periodo)
            if not ruta or not os.path.isfile(ruta):
                abort(500)
            nombre_descarga = f"reporte_ganaderia_ja_{periodo}.pdf"
            return send_file(os.path.abspath(ruta), mimetype="application/pdf",
                             as_attachment=True, download_name=nombre_descarga)
        except Exception as e:
            logger.exception("Error al generar reporte PDF en PWA: %s", e)
            abort(500)
        finally:
            db_rep.close()

    @app.get("/api/sistema")
    def api_sistema():
        if _rol_actual() != "OWNER":
            return jsonify({"error": "Acceso denegado. Se requiere rol OWNER (Propietario)."}), 403

        db_inst = _db(db_path)
        try:
            try:
                try:
                    from ..server.formatters import formatear_tablero_sistema
                    from ..server.auth import Auth
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
                en_linea_cnt = 0

            return jsonify({
                "texto": texto_sistema,
                "vps": info_vps,
                "en_linea_count": en_linea_cnt,
                "db": {
                    "path": db_path,
                    "tam_mb": tam_mb,
                    "activos": row_a["n"] if row_a else 0,
                    "total": row_tot["n"] if row_tot else 0,
                },
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
            candidatos_log.append(os.path.join(RAIZ_PROYECTO, "data", "copias_import.log"))
        if canal in ("telegram", "todos"):
            candidatos_log.extend([
                os.path.join(RAIZ_PROYECTO, "data", "bot.log"),
                os.path.join(RAIZ_PROYECTO, "bot.log"),
                os.path.join(RAIZ_PROYECTO, "data", "telegram.log"),
            ])
        if canal in ("pwa", "todos"):
            candidatos_log.extend([
                os.path.join(RAIZ_PROYECTO, "data", "bitacora.log"),
                os.path.join(RAIZ_PROYECTO, "bitacora.log"),
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
            det = db_tele.detectar_potrero_gps(lat, lon)
            if not det:
                return jsonify({
                    "ok": True,
                    "ignorado": True,
                    "motivo": "Ubicación fuera del área de la finca (no se registra telemetría)",
                    "potrero": None
                })
            t_id = db_tele.registrar_telemetria_gps(
                user_id=uid,
                usuario_nombre=nombre,
                rol=rol,
                lat=lat,
                lon=lon,
                precision_m=acc_f,
                evento_origen=evento,
            )
            return jsonify({"ok": True, "telemetria_id": t_id, "potrero": det})
        finally:
            db_tele.close()

    @app.get("/api/telemetria/rutas")
    def api_telemetria_rutas():
        """Consulta rutas y desplazamientos de operarios (EXCLUSIVO OWNER)."""
        rol = _rol_actual()
        if rol != "OWNER":
            return jsonify({"error": "Acceso denegado. Solo el rol OWNER tiene acceso a la auditoría de rutas."}), 403

        fecha = request.args.get("fecha")
        db_tele = _db(db_path)
        try:
            rutas = db_tele.resumen_rutas_operarios(fecha=fecha)
            rondas = [dict(r) for r in db_tele.listar_rondas_campo(fecha=fecha, limite=50)]
            return jsonify({"ok": True, "rutas": rutas, "rondas": rondas})
        finally:
            db_tele.close()


    @app.get("/api/ficha/<tag>/qr.pdf")
    def api_ficha_qr_pdf(tag):
        # Exporta la tarjeta QR del animal como PDF (botón "Descargar QR").
        db_pdf = _db(db_path)
        try:
            try:
                from ..reports.qr_fichas import generar_ficha_qr_individual
            except ImportError:  # ejecución directa
                from src.reports.qr_fichas import generar_ficha_qr_individual  # type: ignore
            # URL pública para imprimir en la tarjeta: la de la propia petición.
            try:
                base_url = request.host_url.rstrip("/")
            except Exception:
                base_url = ""
            ruta = generar_ficha_qr_individual(
                db_pdf, str(tag), media_dir=MEDIA_DIR_DEFAULT, base_url=base_url,
            )
            if not ruta or not os.path.isfile(ruta):
                abort(404)
            tag_safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(tag)) or "animal"
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
