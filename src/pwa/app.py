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

import functools
import hashlib
import json
import logging
import os
from urllib.parse import urlparse
import re
import shutil
import socket
import sys
import uuid

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
from datetime import date
import hmac
import mimetypes
import secrets
from typing import Any, Optional

_RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ_REPO not in sys.path:
    sys.path.insert(0, _RAIZ_REPO)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_RAIZ_REPO, ".env"))
except ImportError:
    pass

try:
    from ..utils import to_date
except (ImportError, ValueError):
    from src.utils import to_date  # type: ignore

# Flask sirve /static con mimetypes.guess_type; .woff2 no viene registrado y
# se entregaría como application/octet-stream, que algunos navegadores
# rechazan en @font-face. Registro explícito aquí (global).
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")

try:
    from .rate_limit_store import CastigoStore, RateLimitStore
    from ..db.database import Database
    from ..engine.dashboard_data import (
        _filas_dict as _filas_dict,
        _ruta_relativa_media as _ruta_relativa_media,
        conteos_tablero as _conteos_tablero,
        datos_agenda as _datos_agenda,
        datos_badges as _datos_badges,
        datos_buscar as _datos_buscar,
        datos_ficha_animal as _datos_ficha_animal,
        datos_finanzas as _datos_finanzas,
        datos_genetica as _datos_genetica,
        datos_inventario as _datos_inventario,
        datos_leche as _datos_leche,
        datos_pasturas as _datos_pasturas,
        datos_poblacion as _datos_poblacion,
        datos_reproduccion as _datos_reproduccion,
        datos_sanidad as _datos_sanidad,
        resolver_tag_flexible as _resolver_tag_flexible,
        datos_grafico as _datos_grafico,
    )
    from ..engine.genetic_engine import (
        generar_resumen_zootecnico as _generar_resumen_zootecnico,
        CATALOGO_RAZAS_PREDEFINIDAS as _CATALOGO_RAZAS_PREDEFINIDAS,
        normalizar_nombre_raza as _normalizar_nombre_raza,
    )
except ImportError:  # ejecución directa: python src/pwa/app.py
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.pwa.rate_limit_store import CastigoStore, RateLimitStore  # type: ignore
    from src.db.database import Database  # type: ignore
    from src.engine.dashboard_data import (  # type: ignore
        _filas_dict as _filas_dict,
        _ruta_relativa_media as _ruta_relativa_media,
        conteos_tablero as _conteos_tablero,
        datos_agenda as _datos_agenda,
        datos_badges as _datos_badges,
        datos_buscar as _datos_buscar,
        datos_ficha_animal as _datos_ficha_animal,
        datos_finanzas as _datos_finanzas,
        datos_genetica as _datos_genetica,
        datos_inventario as _datos_inventario,
        datos_leche as _datos_leche,
        datos_pasturas as _datos_pasturas,
        datos_poblacion as _datos_poblacion,
        datos_reproduccion as _datos_reproduccion,
        datos_sanidad as _datos_sanidad,
        resolver_tag_flexible as _resolver_tag_flexible,
        datos_grafico as _datos_grafico,
    )
    from src.engine.genetic_engine import (  # type: ignore
        generar_resumen_zootecnico as _generar_resumen_zootecnico,
        CATALOGO_RAZAS_PREDEFINIDAS as _CATALOGO_RAZAS_PREDEFINIDAS,
        normalizar_nombre_raza as _normalizar_nombre_raza,
    )

logger = logging.getLogger(__name__)

__all__ = ["_ruta_relativa_media"]  # re-export compat WS-2 (fuente: engine.dashboard_data)

try:
    from flask import (Flask, abort, jsonify, redirect, render_template,  # type: ignore
                       request, send_file, send_from_directory, session)
    from werkzeug.middleware.proxy_fix import ProxyFix  # type: ignore

    _FLASK_OK = True
except Exception:  # Flask no instalado: no romper el bot
    Flask = None  # type: ignore
    ProxyFix = None  # type: ignore
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

# Cabeceras de seguridad servidas por Flask (defensa en profundidad: las
# mismas que pone scripts/nginx-bitacora.conf; si alguien sirve la PWA sin
# nginx — p. ej. http://IP:8080 directo en LAN — no queda desprotegida).
_CSP_PWA = (
    "default-src 'self'; "
    "img-src 'self' data: https://server.arcgisonline.com; "
    "script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "connect-src 'self' https://server.arcgisonline.com; "
    "object-src 'none'; frame-ancestors 'self'"
)
_PERMISSIONS_PWA = (
    "geolocation=(self), camera=(self), microphone=(self), "
    "bluetooth=(self), payment=(), usb=(), magnetometer=(), gyroscope=()"
)


def _origen_permitido(origen: str, referido: str, host: str) -> bool:
    """Segunda barrera anti-CSRF (además de SameSite=Lax).

    Los navegadores siempre mandan Origin en POST fetch/formulario (y
    Referer salvo política estricta): si alguno viene, su host debe ser el
    nuestro. Si no viene ninguno (curl, clientes viejos), se permite como
    antes — no se pierde nada respecto al estado previo.
    """
    origen = (origen or "").strip()
    referido = (referido or "").strip()
    if not origen and not referido:
        return True
    host_base = (host or "").lower().split(":")[0]
    for url in (origen, referido):
        if not url:
            continue
        try:
            if (urlparse(url).hostname or "").lower() != host_base:
                return False
        except Exception:
            return False
    return True


def _error_interno(codigo: int = 500, con_ok: bool = True, extra: Optional[dict] = None):
    """Respuesta genérica sin fugas: el detalle ya quedó en el log de cada
    sitio (todos llaman logger.exception antes). Nunca devolver str(e) al
    cliente: trae rutas de disco, fragmentos SQL y nombres de columnas."""
    if codigo == 400:
        msg = "No se pudo completar la operación. Revise los datos e intente de nuevo."
    else:
        codigo = 500
        msg = "Error interno del servidor. Intente de nuevo."
    cuerpo: dict = {"error": msg}
    if con_ok:
        cuerpo = {"ok": False, **cuerpo}
    if extra:
        cuerpo.update(extra)
    return jsonify(cuerpo), codigo


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


_EXTENSIONES_IMAGEN_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _es_imagen_valida(raw_bytes: Optional[bytes]) -> bool:
    """Verifica que los bytes sean una imagen real decodificable, no solo
    datos con extensión/nombre de foto. Cierra el hueco de subir cualquier
    archivo (o basura) disfrazado de .jpg desde captura rápida/recibos."""
    if not raw_bytes:
        return False
    try:
        from PIL import Image
        import io as _io
        with Image.open(_io.BytesIO(raw_bytes)) as img:
            img.verify()
        return True
    except Exception:
        return False


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
        "composicion_racial": charts.generar_grafico_composicion_racial,
        "flujo_caja": charts.generar_grafico_flujo_caja,
        "leche_total": charts.generar_grafico_leche_total_hato,
        "eficiencia_lechera": charts.generar_grafico_eficiencia_lechera,
        "reproductivo_hato": charts.generar_grafico_estado_reproductivo_hato,
        # Extras (WS 2): gráficos de hato/leche/población que faltaban en la PWA.
        "gmd_hato": charts.generar_grafico_gmd_hato,
        "ranking_vacas_leche": charts.generar_grafico_ranking_vacas_leche,
        "waterfall_inventario": charts.generar_grafico_waterfall_inventario,
        "subastas_comparativa": charts.generar_grafico_subastas_comparativa,
        "subastas_tendencia": charts.generar_grafico_subastas_tendencia,
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
            return {"potreros": [], "ndvi_reciente": [], "satelite_resumen": {},
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


def datos_finanzas(db_path: str = DB_PATH_DEFAULT, desde: str | None = None, hasta: str | None = None) -> dict:
    """Finanzas: resumen de Ingresos/Egresos/Utilidad + movimientos recientes."""
    db = _db(db_path)
    try:
        try:
            return _datos_finanzas(db, desde=desde, hasta=hasta)
        except Exception:
            logger.exception("datos_finanzas fallo completo")
            return {"resumen": {"total_ingresos": 0, "total_egresos": 0, "utilidad": 0, "categorias": []},
                    "recientes": [], "ventas_compras": [],
                    "errores": {"finanzas": "error interno"}}
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
# Versión automática de la PWA (BLOQUE 3): SHA1 (8 hex) de los bytes
# concatenados de los estáticos principales, en este orden fijo. Se calcula
# una sola vez al crear la app (barato y determinista) para no subir `?v=`
# ni `CACHE` a mano nunca más. Falla rápido si falta un estático crítico
# (un hash silencioso con b"" serviría una versión fantasma inconsistente).
PWA_VERSION = "dev"


def _calcular_pwa_version() -> str:
    """Calcula el hash de versión PWA desde el contenido de los estáticos."""
    h = hashlib.sha1()
    for _nombre in ("app.js", "ja-core.js", "style.css", "sw-register.js", "login.js"):
        _ruta = os.path.join(BASE_DIR, "static", _nombre)
        if not os.path.isfile(_ruta):
            raise RuntimeError(f"PWA_VERSION: falta estático crítico '{_nombre}' en {_ruta}")
        with open(_ruta, "rb") as _f:
            h.update(_f.read())
    return h.hexdigest()[:8]


def crear_app(db_path: str = DB_PATH_DEFAULT, users_file: str = USERS_FILE_DEFAULT,
              password: Optional[str] = None, login_store_path: Optional[str] = None):
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
    # BLOQUE 3: versión automática de la PWA (hash SHA1 de los estáticos,
    # calculada una sola vez al arrancar; barata y determinista).
    global PWA_VERSION
    PWA_VERSION = _calcular_pwa_version()
    app.config["PWA_VERSION"] = PWA_VERSION
    pwa_version = PWA_VERSION

    # Waitress solo escucha en loopback; Nginx es el único que le habla
    # directo (1 salto). Sin esto, request.remote_addr y el X-Forwarded-For
    # que lee _cliente_ip() vienen tal cual los mande el cliente -- nginx
    # normalmente AGREGA la IP real al final del header en vez de
    # reemplazarlo, así que cualquiera puede mandar su propio
    # X-Forwarded-For falso y colarse como "primera IP" para eludir el
    # rate-limit de /login por IP.
    if ProxyFix is not None:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)  # type: ignore

    # Cookie de sesión: Secure (solo por HTTPS), HttpOnly (ya es el default
    # de Flask, pero se deja explícito) y SameSite=Lax (bloquea que un sitio
    # externo dispare peticiones autenticadas contra /api/* del visitante).
    # PWA_COOKIE_SECURE=0 es la única razón para desactivar Secure: correr
    # el servidor local por HTTP plano sin Nginx/TLS delante (desarrollo).
    _cookie_secure = os.getenv("PWA_COOKIE_SECURE", "1").strip().lower() not in ("0", "false", "no")
    app.config.update(
        SESSION_COOKIE_SECURE=_cookie_secure,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Nginx ya limita a 25 MB (client_max_body_size); esto es la misma
        # cota del lado de Flask, por si algún día se sirve sin Nginx delante.
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
    )

    # Rutas que no requieren sesión iniciada (nombres de endpoint de Flask,
    # es decir el nombre de la función de vista, no la URL).
    _RUTAS_PUBLICAS = {"login_form", "login_submit", "static", "manifest", "sw_js", "offline_page"}

    # Rate limit del login: el PIN individual son solo 4 dígitos (10.000
    # combinaciones) -- sin esto cualquiera con acceso a /login (la app está
    # expuesta a internet, no solo LAN) podría fuerza-bruta un PIN en
    # segundos. Persistido en data/login_intentos.json (RateLimitStore) en
    # vez de un dict en memoria: un `systemctl restart` en cada deploy ya
    # no reabre la ventana de fuerza bruta.
    if login_store_path:
        _login_store = RateLimitStore(login_store_path)
        _castigo_store = CastigoStore(login_store_path + ".castigos")
        _api_store = RateLimitStore(login_store_path + ".api")
    elif os.environ.get("PYTEST_CURRENT_TEST"):
        import tempfile, time
        _sfx = f"pytest_{os.getpid()}_{time.time_ns()}"
        _tmp = tempfile.gettempdir()
        _login_store = RateLimitStore(os.path.join(_tmp, f"pytest_login_{_sfx}.json"))
        _castigo_store = CastigoStore(os.path.join(_tmp, f"pytest_castigo_{_sfx}.json"))
        _api_store = RateLimitStore(os.path.join(_tmp, f"pytest_api_{_sfx}.json"))
    else:
        _login_store = RateLimitStore(os.path.join(RAIZ_PROYECTO, "data", "login_intentos.json"))
        _castigo_store = CastigoStore(os.path.join(RAIZ_PROYECTO, "data", "login_castigos.json"))
        _api_store = RateLimitStore(os.path.join(RAIZ_PROYECTO, "data", "api_limites.json"))
    _LOGIN_MAX_INTENTOS = 8
    # Ventana de 5 minutos (no 60 s): cada intento fallido verifica el PIN
    # contra TODOS los usuarios (hash intencionalmente costoso), así que en
    # hardware modesto 8 fallos tardan ~1 min y con 60 s la ventana se
    # deslizaba y el bloqueo nunca se activaba de forma determinista.
    # 8 intentos / 5 min sigue siendo holgado para uso real y más estricto
    # contra fuerza bruta; el mensaje de 429 ya dice la espera real.
    _LOGIN_VENTANA_SEG = 300.0

    # Cuotas por usuario+IP en endpoints costosos: sin esto, cualquier
    # sesión autenticada (o robada) puede saturar los hilos de waitress
    # golpeando Whisper/OCR/satélite/matplotlib y tumbar la PWA para todos.
    # Límites holgados para uso real en campo con reintentos por mala señal.
    _API_LIMITES = {
        "voz": (12, 60.0),
        "identificar": (30, 60.0),
        "satelite": (6, 300.0),
        "grafico": (40, 60.0),
        "sync": (40, 60.0),
        "mensajes": (90, 60.0),
    }

    def _limite_api(bucket: str):
        def _deco(fn):
            @functools.wraps(fn)
            def _envuelta(*args, **kwargs):
                max_n, ventana = _API_LIMITES[bucket]
                uid = session.get("user_id") if session is not None else None
                clave = f"{bucket}|{_cliente_ip()}|{uid}"
                if _api_store.bloqueado(clave, max_n, ventana):
                    resp = jsonify({
                        "ok": False,
                        "error": "Demasiadas solicitudes. Espere un momento e intente de nuevo.",
                    })
                    resp.status_code = 429
                    resp.headers["Retry-After"] = str(int(ventana))
                    return resp
                _api_store.registrar(clave)
                return fn(*args, **kwargs)
            return _envuelta
        return _deco

    def _cliente_ip() -> str:
        # request.remote_addr ya viene corregido por ProxyFix (confía en
        # exactamente 1 salto = Nginx) -- no leer X-Forwarded-For a mano
        # aquí, porque el valor crudo del header es falsificable por el
        # cliente y volvería a abrir el bypass del rate-limit de /login.
        return request.remote_addr or "desconocido"

    def _login_bloqueado(ip: str) -> bool:
        return _login_store.bloqueado(ip, _LOGIN_MAX_INTENTOS, _LOGIN_VENTANA_SEG)

    def _login_registrar_intento(ip: str) -> None:
        _login_store.registrar(ip)

    def _texto_espera(segundos: float) -> str:
        """Texto humano para un bloqueo ("un minuto", "~3 minutos")."""
        mins = max(1, int(round(segundos / 60.0)))
        return "un minuto" if mins <= 1 else f"~{mins} minutos"

    def _rol_actual() -> Optional[str]:
        if session is None:
            return None
        uid = session.get("user_id")
        if uid is not None:
            try:
                int_uid = int(uid)
                rol_json = _rol_de(int_uid, users_file)
                if not rol_json:
                    return None
                return rol_json
            except (ValueError, TypeError):
                pass
        rol_sesion = session.get("rol")
        if rol_sesion:
            return str(rol_sesion).strip().upper()
        return None

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

    @app.after_request
    def _cabeceras_seguridad(resp):
        try:
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            resp.headers.setdefault("Content-Security-Policy", _CSP_PWA)
            resp.headers.setdefault("Permissions-Policy", _PERMISSIONS_PWA)
            if request is not None and request.is_secure:
                resp.headers.setdefault(
                    "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
                )
        except Exception:
            pass
        return resp

    @app.before_request
    def _requerir_login():
        if request is None:
            return None
        # Chequeo de origen en escrituras: si el navegador manda Origin o
        # Referer y no es el nuestro, es un POST entre sitios (CSRF) y se
        # bloquea con 403 antes de tocar sesión o base de datos. Va ANTES
        # de la vía pública porque /login también acepta POST.
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            _ruta = request.path or ""
            if _ruta.startswith("/api/") or _ruta == "/login":
                if not _origen_permitido(
                    request.headers.get("Origin") or "",
                    request.headers.get("Referer") or "",
                    request.host or "",
                ):
                    logger.warning(
                        "POST entre sitios bloqueado: ruta=%s ip=%s", _ruta, _cliente_ip()
                    )
                    if _ruta.startswith("/api/"):
                        return jsonify({"ok": False, "error": "Origen no permitido."}), 403
                    return ("⛔ Origen no permitido.", 403)
        if request.endpoint in _RUTAS_PUBLICAS:
            return None
        if session.get("autenticado"):
            uid = session.get("user_id")
            if uid is not None:
                try:
                    int_uid = int(uid)
                    if not _rol_de(int_uid, users_file):
                        session.clear()
                        if request.path.startswith("/api/") or request.path.startswith("/media/"):
                            return jsonify({"error": "Sesión inválida o usuario revocado."}), 401
                        return redirect("/login")
                except (ValueError, TypeError):
                    pass
            try:
                db_inst = _db(db_path)
                uid_pres = uid or session.get("nombre")
                nom = session.get("nombre") or ""
                rol = session.get("rol") or "TRABAJADOR"
                ip = _cliente_ip()
                db_inst.registrar_presencia(user_id=uid_pres, nombre=nom, rol=rol, canal="PWA", ip=ip)
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
        return render_template("login.html", error=request.args.get("error"), pwa_v=pwa_version)

    @app.post("/login")
    def login_submit():
        if not clave_esperada:
            return (
                "⚠️ PWA_PASSWORD no está configurada en el entorno (.env).",
                503,
            )
        ip = _cliente_ip()
        # Backoff progresivo: cada ventana agotada duplica el bloqueo
        # (60s, 120s, 240s… tope 1h). Sin esto, el PIN de 4 dígitos se
        # barre en días rotando pocos IPs.
        castigo = _castigo_store.segundos_restantes(ip)
        if castigo > 0:
            return (
                f"⚠️ Demasiados intentos fallidos. Espere {_texto_espera(castigo)} e intente de nuevo.",
                429,
            )
        if _login_bloqueado(ip):
            espera = _castigo_store.castigar(ip)
            return (
                f"⚠️ Demasiados intentos fallidos. Espere {_texto_espera(espera)} e intente de nuevo.",
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
            # Éxito: se levantan ventana y castigo de esta IP y se rota la
            # sesión (no arrastrar claves previas en equipos compartidos).
            _login_store.olvidar(ip)
            _castigo_store.perdonar(ip)
            # Rotación de sesión: no arrastrar claves de una sesión previa
            # (ej. telegram_id de otro usuario en un equipo compartido).
            session.clear()
            session["autenticado"] = True
            session["user_id"] = user_auth.get("user_id")
            session["telegram_id"] = user_auth.get("telegram_id")
            session["nombre"] = user_auth.get("nombre") or "Usuario"
            session["rol"] = user_auth.get("rol") or "TRABAJADOR"
            session["avatar"] = user_auth.get("avatar") or "vaquero"
            return redirect("/")

        # 2. Intentar autenticar por contraseña maestra (PWA_PASSWORD)
        if clave_esperada and intento and hmac.compare_digest(intento, clave_esperada):
            # El user_id del formulario no es confiable (el login.html ni
            # siquiera lo pide): solo se adopta si existe en users.json.
            # Un ID inexistente o revocado se descarta en vez de firmar
            # eventos y presencia a nombre de otro usuario.
            uid_verificado = None
            if uid_form is not None:
                try:
                    _uid_candidato = int(uid_form)
                except (ValueError, TypeError):
                    _uid_candidato = None
                if _uid_candidato is not None and _rol_de(_uid_candidato, users_file):
                    uid_verificado = _uid_candidato
            _login_store.olvidar(ip)
            _castigo_store.perdonar(ip)
            session.clear()
            session["autenticado"] = True
            session["user_id"] = uid_verificado
            session["rol"] = _rol_de(uid_verificado, users_file) or "OWNER"
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
        return render_template("index.html", pwa_v=pwa_version)

    @app.get("/ficha/<tag>")
    def ficha(tag):
        return render_template("ficha.html", tag=tag, pwa_v=pwa_version)

    @app.get("/manifest.json")
    def manifest():
        return app.send_static_file("manifest.json")

    @app.get("/sw.js")
    def sw_js():
        # El service worker debe servirse en la raíz de su scope ("/") y sin
        # caché HTTP (los navegadores lo revalidan agresivamente). Público.
        # BLOQUE 3: se sirve con el token __PWA_VERSION__ sustituido por el
        # hash calculado al arrancar (versionado automático, sin bump manual).
        with open(os.path.join(app.static_folder, "sw.js"), encoding="utf-8") as _f:
            cuerpo_sw = _f.read().replace("__PWA_VERSION__", pwa_version)
        resp = app.response_class(cuerpo_sw, content_type="application/javascript; charset=utf-8")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    @app.get("/offline.html")
    def offline_page():
        # Página de respaldo para el SW (navegación offline). Público.
        # BLOQUE 3: versionado automático — cualquier ?v=... del fichero se
        # reescribe al hash calculado al arrancar (cubre también el token
        # __PWA_VERSION__ que trae offline.html en disco).
        with open(os.path.join(app.static_folder, "offline.html"), encoding="utf-8") as _f:
            cuerpo_off = _f.read().replace("__PWA_VERSION__", pwa_version)
            cuerpo_off = re.sub(r"\?v=[A-Za-z0-9._-]+", "?v=" + pwa_version, cuerpo_off)
        resp = app.response_class(cuerpo_off, content_type="text/html; charset=utf-8")
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
                from ..engine.dashboard_data import animales_de_potrero
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
                from ..engine.dashboard_data import animales_por_grupo_inventario
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
            from ..engine.pasture_engine import PastureEngine
        except (ImportError, ValueError):
            from src.engine.pasture_engine import PastureEngine  # type: ignore
        try:
            from ..server.formatters import formatear_ronda_voisin
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
                from ..gis.earth_engine_ndvi import actualizar_lecturas_reales
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
                if os.path.isdir(REPORTES_DIR_DEFAULT):
                    for arch in os.listdir(REPORTES_DIR_DEFAULT):
                        if arch.startswith("_pwa_cache_"):
                            try:
                                os.remove(os.path.join(REPORTES_DIR_DEFAULT, arch))
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


    @app.get("/api/leche")
    def api_leche():
        out = datos_leche(db_path)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/finanzas")
    def api_finanzas():
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
                            os.path.join(RAIZ_PROYECTO, MEDIA_DIR_DEFAULT)
                            if not os.path.isabs(MEDIA_DIR_DEFAULT) else MEDIA_DIR_DEFAULT
                        )
                        os.makedirs(media_dir_abs, exist_ok=True)
                        ts = int(time.time())
                        rnd = uuid.uuid4().hex[:6]
                        fname = f"gasto_{categoria.lower()}_{ts}_{rnd}.jpg"
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
                from ..vision.recibo_leche_parser import _extraer_bytes_e_imagen
            except (ImportError, ValueError):
                from src.vision.recibo_leche_parser import _extraer_bytes_e_imagen
            raw_bytes, _ = _extraer_bytes_e_imagen(foto_b64)
            if not _es_imagen_valida(raw_bytes):
                logger.warning("Foto de recibo de leche descartada: no es una imagen válida")
                return None
            media_dir_abs = (
                os.path.join(RAIZ_PROYECTO, MEDIA_DIR_DEFAULT)
                if not os.path.isabs(MEDIA_DIR_DEFAULT) else MEDIA_DIR_DEFAULT
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
            from ..vision.recibo_leche_parser import analizar_recibo_leche
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
                from ..vision.recibo_leche_parser import _extraer_bytes_e_imagen
            except (ImportError, ValueError):
                from src.vision.recibo_leche_parser import _extraer_bytes_e_imagen
            raw_bytes, _ = _extraer_bytes_e_imagen(foto_b64)
            if not _es_imagen_valida(raw_bytes):
                logger.warning("Foto de factura descartada: no es una imagen válida")
                return None
            media_dir_abs = (
                os.path.join(RAIZ_PROYECTO, MEDIA_DIR_DEFAULT)
                if not os.path.isabs(MEDIA_DIR_DEFAULT) else MEDIA_DIR_DEFAULT
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
            from ..vision.recibo_gasto_parser import analizar_factura_gasto
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
            from ..engine.genetic_engine import generar_resumen_zootecnico
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

    @app.post("/api/agenda/recordatorio")
    def api_agenda_crear_recordatorio():
        """Crea un evento/recordatorio o tarea asignada de campo (misma tabla de /programar)."""
        datos = request.get_json(silent=True) or request.form or {}
        mensaje = str(datos.get("mensaje") or "").strip()
        fecha = str(datos.get("fecha") or "").strip()
        hora = str(datos.get("hora") or "").strip() or None
        asignado_a = str(datos.get("asignado_a") or "").strip() or None
        tipo_objetivo = str(datos.get("tipo_objetivo") or "").strip().upper() or None
        animal_tag = str(datos.get("animal_tag") or datos.get("tag") or "").strip().upper() or None
        potrero_nombre = str(datos.get("potrero_nombre") or datos.get("potrero") or "").strip() or None
        tipo_tarea = str(datos.get("tipo_tarea") or "").strip().upper() or None
        prioridad = str(datos.get("prioridad") or "NORMAL").strip().upper()
        if not mensaje:
            return jsonify({"ok": False, "error": "El mensaje o descripción de la tarea es obligatorio."}), 400
        if len(mensaje) > 500:
            return jsonify({"ok": False, "error": "El mensaje no puede superar 500 caracteres."}), 400
        if not fecha:
            return jsonify({"ok": False, "error": "Fecha inválida. Use YYYY-MM-DD."}), 400
        try:
            if to_date(fecha) is None:
                return jsonify({"ok": False, "error": "Fecha inválida. Use YYYY-MM-DD."}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Fecha inválida. Use YYYY-MM-DD."}), 400
        if hora and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", hora):
            return jsonify({"ok": False, "error": "Hora inválida. Use HH:MM (24h)."}), 400
        db_r = _db(db_path)
        try:
            uid = session.get("user_id") if session is not None else None
            rid = db_r.registrar_recordatorio(
                mensaje=mensaje,
                fecha_programada=fecha,
                hora=hora,
                creado_por=uid,
                asignado_a=asignado_a,
                tipo_objetivo=tipo_objetivo,
                animal_tag=animal_tag,
                potrero_nombre=potrero_nombre,
                tipo_tarea=tipo_tarea,
                prioridad=prioridad,
            )
            # Notificar al canal del equipo
            try:
                dest = f" a {asignado_a}" if asignado_a else ""
                obj = f" ({animal_tag or potrero_nombre})" if (animal_tag or potrero_nombre) else ""
                texto_aviso = f"📋 Tarea asignada{dest}{obj}: {mensaje}"
                nombre_creador = session.get("nombre") or (_rol_actual() or "Usuario")
                db_r.conn.execute(
                    "INSERT INTO mensajes_equipo (user_id, nombre, rol, texto, creado_en) VALUES (?, ?, ?, ?, ?)",
                    (uid, nombre_creador, _rol_actual() or "USUARIO", texto_aviso, db_r._ahora()),
                )
                db_r.conn.commit()
            except Exception:
                pass
            return jsonify({"ok": True, "id": rid, "fecha": fecha, "hora": hora, "asignado_a": asignado_a})
        except Exception:
            logger.exception("Error creando recordatorio de agenda")
            return jsonify({"ok": False, "error": "No se pudo crear el recordatorio."}), 500
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.post("/api/agenda/recordatorio/<int:rid>/completar")
    def api_agenda_completar_recordatorio(rid: int):
        """Marca un recordatorio PENDIENTE como REALIZADO (acknowledge con notas y foto opcional)."""
        datos = request.get_json(silent=True) or request.form or {}
        notas = str(datos.get("notas") or datos.get("notas_completado") or "").strip() or None
        foto_b64 = datos.get("foto_base64")
        completado_por = str(datos.get("completado_por") or session.get("nombre") or (_rol_actual() or "Usuario")).strip()
        db_r = _db(db_path)
        try:
            fila = db_r.query_one(
                "SELECT * FROM recordatorios_programados WHERE id = ?", (rid,),
            )
            if not fila:
                return jsonify({"ok": False, "error": "El recordatorio no existe."}), 404
            uid = session.get("user_id") if session is not None else None
            foto_ruta = None
            if foto_b64 and isinstance(foto_b64, str):
                tag_ref = fila.get("animal_tag") or "tarea"
                fid_foto = _guardar_foto_evento(db_r, {"foto_base64": foto_b64, "animal_tag": tag_ref}, "tarea", date.today().isoformat(), uid)
                if fid_foto:
                    foto_row = db_r.query_one("SELECT ruta FROM fotos WHERE id = ?", (fid_foto,))
                    if foto_row and foto_row.get("ruta"):
                        foto_ruta = foto_row["ruta"]

            db_r.completar_recordatorio(
                rid,
                completado_por=completado_por,
                completado_por_id=uid,
                notas_completado=notas,
                foto_completado=foto_ruta,
            )
            # Notificar al canal del equipo
            try:
                obj = f" ({fila.get('animal_tag') or fila.get('potrero_nombre')})" if (fila.get('animal_tag') or fila.get('potrero_nombre')) else ""
                detalle = f" · {notas}" if notas else ""
                texto_aviso = f"✅ Tarea realizada por {completado_por}{obj}: {fila.get('mensaje')}{detalle}"
                db_r.conn.execute(
                    "INSERT INTO mensajes_equipo (user_id, nombre, rol, texto, creado_en) VALUES (?, ?, ?, ?, ?)",
                    (uid, completado_por, _rol_actual() or "USUARIO", texto_aviso, db_r._ahora()),
                )
                db_r.conn.commit()
            except Exception:
                pass

            return jsonify({
                "ok": True,
                "id": rid,
                "estado": "REALIZADO",
                "completado_por": completado_por,
                "notas": notas,
                "foto_ruta": foto_ruta,
            })
        except Exception:
            logger.exception("Error completando recordatorio de agenda")
            return jsonify({"ok": False, "error": "No se pudo completar el recordatorio."}), 500
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.post("/api/eventos/eliminar")
    def api_eliminar_evento():
        """Elimina un evento registrado en la base de datos con reversión inteligente de estados.
        Restringido a roles OWNER y ADMIN.
        """
        rol = _rol_actual()
        if rol != "OWNER":
            return jsonify({
                "ok": False,
                "error": "Acceso restringido: solo el propietario (OWNER) puede eliminar eventos del sistema.",
            }), 403

        datos = request.get_json(silent=True) or request.form or {}
        tipo = str(datos.get("tipo") or "").strip()
        try:
            eid = int(datos.get("id"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "ID de evento inválido o faltante."}), 400

        if not tipo:
            return jsonify({"ok": False, "error": "Tipo de evento no especificado."}), 400

        db_r = _db(db_path)
        try:
            uid = session.get("user_id") if session is not None else None
            res = db_r.eliminar_evento(tipo=tipo, eid=eid, user_id=uid)
            if not res.get("ok"):
                return jsonify(res), 404

            # Notificar al canal de auditoría / equipo
            try:
                nombre_autor = session.get("nombre") or session.get("username") or "Administrador"
                texto_aviso = f"🗑️ Evento de {tipo.upper()} #{eid} eliminado del sistema por {nombre_autor} ({rol})."
                db_r.conn.execute(
                    "INSERT INTO mensajes_equipo (user_id, nombre, rol, texto, creado_en) VALUES (?, ?, ?, ?, ?)",
                    (uid, nombre_autor, rol, texto_aviso, db_r._ahora()),
                )
                db_r.conn.commit()
            except Exception:
                pass

            return jsonify(res)
        except Exception as e:
            logger.exception("Error al eliminar evento %s #%s: %s", tipo, eid, e)
            return _error_interno(500)
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.get("/api/eventos/recientes")
    def api_eventos_recientes():
        """Lista los últimos eventos de campo registrados con datos para deshacer."""
        rol = _rol_actual()
        limite = request.args.get("limite", 30, type=int)
        limite = max(5, min(100, limite))
        db_r = _db(db_path)
        try:
            filas = db_r.ultimos_registros(limite=limite)
            eventos = []
            for f in filas:
                eventos.append({
                    "id": f["id"],
                    "tabla": f["tabla"],
                    "tag": f["tag"],
                    "fecha": f["fecha"],
                    "resumen": f["resumen"],
                    "creado_en": f["creado_en"],
                    "registrado_por": f["registrado_por"],
                })
            return jsonify({
                "ok": True,
                "eventos": eventos,
                "puede_deshacer": rol == "OWNER",
                "rol": rol,
            })
        except Exception as e:
            logger.exception("Error al listar eventos recientes: %s", e)
            return _error_interno(500)
        finally:
            try:
                db_r.close()
            except Exception:
                pass

    @app.get("/api/equipo/integrantes")
    def api_equipo_integrantes():
        """Lista roles estándar y usuarios activos para asignación de tareas de campo."""
        roles_base = ["Encargado", "Administrador", "Veterinario", "Trabajador"]
        integrantes = [{"nombre": r, "tipo": "ROL"} for r in roles_base]
        try:
            try:
                from ..server.auth import Auth
            except (ImportError, ValueError):
                from src.server.auth import Auth
            auth_inst = Auth(users_file)
            for u in auth_inst.listar_usuarios():
                nom = (u.get("nombre") or u.get("username") or "").strip()
                if nom and not any(it["nombre"].lower() == nom.lower() for it in integrantes):
                    integrantes.append({"nombre": nom, "rol": u.get("rol"), "tipo": "USUARIO"})
        except Exception:
            pass
        return jsonify({"ok": True, "integrantes": integrantes})

    @app.get("/api/buscar")
    def api_buscar():
        q = (request.args.get("q") or "").strip()
        out = datos_buscar(db_path, q=q)
        return jsonify(out)

    @app.get("/api/toros")
    def api_toros():
        """Lista de toros reproductores activos oficiales de la finca (T01..T05, prefijo T+número o marca [REPRODUCTOR])."""
        db_t = _db(db_path)
        try:
            filas = db_t.query("""
                SELECT tag, nombre, raza, fecha_nacimiento, notas FROM animales
                WHERE estado = 'ACTIVO' AND (
                    tag GLOB 'T[0-9]*'
                    OR UPPER(COALESCE(notas, '')) LIKE '%[REPRODUCTOR]%'
                    OR UPPER(COALESCE(notas, '')) LIKE '%TORO%'
                )
                ORDER BY CASE WHEN tag GLOB 'T[0-9]*' THEN 0 ELSE 1 END, tag ASC
            """)
            toros = []
            for r in filas:
                nom = " ".join((r["nombre"] or "").split())
                raza_raw = (r["raza"] or "").strip()
                raza_corta = raza_raw
                if "+" in raza_raw:
                    raza_corta = raza_raw.split("+")[0].strip()
                import re as _re
                raza_corta = _re.sub(r'^\s*(\d+/\d+|\d+(\.\d+)?%)\s*', '', raza_corta).strip()
                raza_corta = _re.sub(r'\s+Puro$', '', raza_corta).strip()
                toros.append({
                    "tag": r["tag"],
                    "nombre": nom,
                    "raza": raza_corta or raza_raw,
                    "raza_completa": raza_raw,
                    "fecha_nacimiento": r["fecha_nacimiento"] or "",
                    "es_reproductor": True,
                })
            return jsonify({"ok": True, "toros": toros})
        except Exception as e:
            logger.exception("Error al listar toros: %s", e)
            return _error_interno(500, extra={"toros": []})
        finally:
            try:
                db_t.close()
            except Exception:
                pass

    @app.get("/api/parto/sugerir-padre")
    def api_parto_sugerir_padre():
        """Sugiere el padre más probable para un parto según servicios previos o toros en el mismo potrero."""
        vaca = (request.args.get("vaca") or request.args.get("tag") or "").strip()
        fecha = (request.args.get("fecha") or "").strip() or None
        if not vaca:
            return jsonify({"ok": False, "error": "Parámetro 'vaca' requerido."}), 400
        db_s = _db(db_path)
        try:
            res = db_s.sugerir_padre_parto(vaca, fecha)
            return jsonify(res)
        except Exception as e:
            logger.exception("Error al sugerir padre de parto: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500
        finally:
            try:
                db_s.close()
            except Exception:
                pass

    @app.get("/api/simular-cruzamiento")
    def api_simular_cruzamiento():
        """Simulador de cruzamiento en 1 toque (Fase 5.2): vaca + toro ->
        veredicto de consanguinidad 3G ANTES de servir. Solo lectura
        (nunca crea animales) y abierto a todos los roles autenticados,
        porque el trabajador lo necesita en el corral al inseminar."""
        vaca = (request.args.get("vaca") or "").strip()
        toro = (request.args.get("toro") or "").strip()
        if not vaca or not toro:
            return jsonify({"ok": False, "error": "Indique vaca y toro (ej. ?vaca=JA457&toro=T01)."}), 400
        db_s = _db(db_path)
        try:
            sim = db_s.simular_cruzamiento(vaca, toro)
            sim["ok"] = True
            return jsonify(sim)
        except Exception:
            logger.exception("Error al simular cruzamiento %s x %s", vaca, toro)
            return jsonify({"ok": False, "error": "No se pudo evaluar el cruzamiento."}), 500
        finally:
            try:
                db_s.close()
            except Exception:
                pass

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
    @_limite_api("identificar")
    def api_identificar():
        # Identificación por texto (arete/RFID/lector de corral) o foto del
        # arete. SOLO LECTURA: nunca inserta ni actualiza registros.
        texto = (request.form.get("texto") or "").strip() or None
        foto = request.files.get("foto") if request.files else None
        if not texto and (foto is None or not foto.filename):
            return jsonify({"existe": False, "error": "Envíe 'texto' (arete/RFID) o un archivo 'foto'."}), 400
        if foto is not None and foto.filename:
            ext = (os.path.splitext(foto.filename)[1] or ".jpg").lower()
            if ext not in _EXTENSIONES_IMAGEN_PERMITIDAS:
                ext = ".jpg"
            foto_bytes = foto.read()
            if not _es_imagen_valida(foto_bytes):
                return jsonify({"existe": False, "error": "El archivo enviado no es una imagen válida."}), 400
            out = datos_identificar(db_path, foto_bytes=foto_bytes, foto_ext=ext)
        else:
            out = datos_identificar(db_path, texto=texto)
        out["rol"] = _rol_actual()
        return jsonify(out)

    @app.get("/api/usuario")
    def api_usuario():
        return jsonify(_usuario_actual())

    def _resolver_presencia_usuario(u: dict, presencias: dict[str, dict]) -> dict:
        uid = str(u.get("user_id"))
        tg_id = str(u.get("telegram_id")) if u.get("telegram_id") else None
        rol_u = str(u.get("rol", "")).upper()

        candidatos = []
        if uid in presencias:
            candidatos.append(presencias[uid])
        if tg_id and tg_id in presencias:
            candidatos.append(presencias[tg_id])
        if rol_u == "OWNER" and "Propietario" in presencias:
            candidatos.append(presencias["Propietario"])

        if not candidatos:
            return {}

        # Priorizar sesión que esté 'en_linea'; en empate, la de menor segundos_desde (más reciente)
        candidatos.sort(key=lambda c: (0 if c.get("en_linea") else 1, c.get("segundos_desde", 999999)))
        return candidatos[0]

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
            # El PIN se guarda hasheado (no recuperable) -- nunca se manda el
            # valor crudo al frontend, solo si tiene uno asignado o no.
            for u in usuarios:
                u["pin"] = "····" if u.get("pin") else ""

            # EXCLUSIVO OWNER: adjuntar presencia en vivo
            if rol == "OWNER":
                try:
                    db_u = _db(db_path)
                    presencias = db_u.obtener_usuarios_presencia()
                    db_u.close()
                except Exception:
                    presencias = {}
                for u in usuarios:
                    p = _resolver_presencia_usuario(u, presencias)
                    u["online_info"] = {
                        "en_linea": p.get("en_linea", False),
                        "estado": p.get("estado", "offline"),
                        "canal": p.get("canal", ""),
                        "ip": p.get("ip", ""),
                        "ultima_actividad": p.get("ultima_actividad", ""),
                        "hace_texto": p.get("hace_texto", "Nunca"),
                    }
            return jsonify({"ok": True, "usuarios": usuarios, "mi_rol": rol})
        except Exception:
            logger.exception("Error al listar usuarios")
            return _error_interno(500, con_ok=False)

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
                p = _resolver_presencia_usuario(u, presencias)
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

    @app.get("/api/mensajes-equipo")
    @_limite_api("mensajes")
    def api_mensajes_equipo():
        """Lista el canal único de avisos del equipo (broadcast, cualquier rol autenticado)."""
        try:
            despues_de = int(request.args.get("despues_de") or 0)
        except (TypeError, ValueError):
            despues_de = 0
        try:
            limite = int(request.args.get("limite") or 50)
        except (TypeError, ValueError):
            limite = 50
        db_m = _db(db_path)
        try:
            filas = db_m.listar_mensajes_equipo(despues_de_id=despues_de, limite=limite)
            mensajes = [dict(f) for f in filas]
            ultimo_id = mensajes[-1]["id"] if mensajes else despues_de
            return jsonify({"ok": True, "mensajes": mensajes, "ultimo_id": ultimo_id})
        finally:
            db_m.close()

    @app.post("/api/mensajes-equipo")
    @_limite_api("mensajes")
    def api_mensajes_equipo_crear():
        """Publica un mensaje en el canal de equipo (cualquier rol autenticado)."""
        datos = request.get_json(silent=True) or {}
        texto = str(datos.get("texto") or "").strip()
        if not texto:
            return jsonify({"ok": False, "error": "El mensaje no puede estar vacío."}), 400
        if len(texto) > 500:
            return jsonify({"ok": False, "error": "El mensaje no puede superar 500 caracteres."}), 400

        uid = session.get("user_id")
        nombre = session.get("nombre") or "Usuario"
        rol = session.get("rol") or _rol_actual() or "TRABAJADOR"
        db_m = _db(db_path)
        try:
            mid = db_m.registrar_mensaje_equipo(user_id=uid, nombre=nombre, rol=rol, texto=texto)
            fila = db_m.obtener_mensaje_equipo(mid)
            try:
                from ..server.push_sender import enviar_push
            except (ImportError, ValueError):
                from src.server.push_sender import enviar_push  # type: ignore
            try:
                enviar_push(
                    db_m,
                    titulo=f"👥 {nombre}",
                    cuerpo=texto[:120],
                    url="/",
                    tag="chat-equipo",
                    excluir_user_id=uid,
                )
            except Exception:
                logger.exception("No se pudo enviar push del chat de equipo")
            return jsonify({"ok": True, "mensaje": dict(fila) if fila else None})
        finally:
            db_m.close()

    @app.delete("/api/mensajes-equipo/<int:id_mensaje>")
    def api_mensajes_equipo_eliminar(id_mensaje):
        """Borra un mensaje del canal de equipo (autor propio, u OWNER/ADMIN para moderar)."""
        mi_uid = session.get("user_id")
        mi_rol = _rol_actual()
        db_m = _db(db_path)
        try:
            fila = db_m.obtener_mensaje_equipo(id_mensaje)
            if not fila:
                return jsonify({"ok": False, "error": "El mensaje no existe."}), 404
            es_autor = mi_uid is not None and str(fila["user_id"]) == str(mi_uid)
            es_moderador = mi_rol in ("OWNER", "ADMIN", "ADMINISTRADOR")
            if not (es_autor or es_moderador):
                return jsonify({"ok": False, "error": "Solo el autor o un OWNER/ADMIN pueden borrar este mensaje."}), 403
            db_m.eliminar_mensaje_equipo(id_mensaje)
            return jsonify({"ok": True})
        finally:
            db_m.close()

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
        borrar_tg = False
        if tg_id_raw is not None and str(tg_id_raw).strip() != "":
            try:
                tg_id = int(tg_id_raw)
            except (ValueError, TypeError):
                return jsonify({"error": "El ID de Telegram debe ser un número entero (ej. 6123051140)."}), 400
        elif "telegram_id" in datos and (tg_id_raw is None or str(tg_id_raw).strip() == ""):
            borrar_tg = True

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

            # Verificar que el PIN no esté en colisión con OTRO usuario. Los
            # PIN se guardan hasheados, así que no se puede comparar por
            # igualdad de string -- usuario_con_pin verifica contra cada hash.
            # Mensaje genérico a propósito: no revela el PIN ni a quién
            # pertenece, para que un ADMIN no pueda cosechar PINs ajenos.
            u_dup = auth_inst.usuario_con_pin(pin, excluir_user_id=uid)
            if u_dup is not None:
                return jsonify({"error": "Ese PIN ya está asignado a otro usuario. Elija un PIN de 4 dígitos diferente."}), 400

            auth_inst.agregar_usuario(
                user_id=uid,
                nombre=nombre,
                rol=rol_nuevo,
                pin=pin,
                telegram_id=tg_id,
                avatar=avatar,
                borrar_telegram_id=borrar_tg,
            )
            usr_guardado = auth_inst.obtener_usuario(uid) or {}
            # El PIN nunca vuelve al cliente: ya quedó hasheado en
            # users.json y el frontend solo muestra "····". Quien creó el
            # usuario debe dictar el PIN en persona, no por la red.
            return jsonify({
                "ok": True,
                "mensaje": f"Usuario '{nombre}' (Level {1 if rol_nuevo=='OWNER' else 2 if rol_nuevo=='ADMIN' else 3}) guardado exitosamente.",
                "usuario": {
                    "user_id": uid,
                    "telegram_id": usr_guardado.get("telegram_id"),
                    "nombre": nombre,
                    "rol": rol_nuevo,
                    "avatar": usr_guardado.get("avatar") or ("patron" if rol_nuevo=="OWNER" else "admin" if rol_nuevo=="ADMIN" else "vaquero"),
                }
            })
        except Exception:
            logger.exception("Error al guardar usuario")
            return _error_interno(400, con_ok=False)

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

            # Verificar colisión de PIN (contra cada hash, ver usuario_con_pin).
            # Genérico a propósito: no revela el PIN ni a quién pertenece.
            u_dup = auth_inst.usuario_con_pin(nuevo_pin, excluir_user_id=target_uid)
            if u_dup is not None:
                return jsonify({"error": "Ese PIN ya está asignado a otro usuario. Ingrese un PIN diferente."}), 400

            auth_inst.asignar_pin(target_uid, nuevo_pin)
            return jsonify({"ok": True, "mensaje": "PIN actualizado exitosamente."})
        except Exception:
            logger.exception("Error al cambiar PIN")
            return _error_interno(400, con_ok=False)

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
        except Exception:
            logger.exception("Error al eliminar usuario")
            return _error_interno(400, con_ok=False)

    def _guardar_foto_evento(db_inst, payload: dict, tipo: str, fecha: str, uid_user: Optional[int]) -> Optional[int]:
        """Procesa y almacena una foto adjunta (opcional) enviada en base64 desde la captura rápida."""
        foto_b64 = payload.get("foto_base64")
        if not foto_b64 or not isinstance(foto_b64, str):
            return None
        try:
            import base64
            import uuid

            if "," in foto_b64:
                foto_b64 = foto_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(foto_b64)
            if not raw_bytes or not _es_imagen_valida(raw_bytes):
                return None

            media_dir_abs = os.path.join(RAIZ_PROYECTO, MEDIA_DIR_DEFAULT) if not os.path.isabs(MEDIA_DIR_DEFAULT) else MEDIA_DIR_DEFAULT
            os.makedirs(media_dir_abs, exist_ok=True)

            # Determinar el tag del animal involucrado
            tag_asoc = None
            if tipo == "parto":
                tag_asoc = payload.get("id_cria_tag") or payload.get("vaca_tag") or payload.get("tag")
            elif tipo == "destete":
                tag_asoc = payload.get("cria_tag") or payload.get("animal_tag") or payload.get("tag")
            elif tipo in ("tratamiento", "muerte", "pesaje", "traslado"):
                tag_asoc = payload.get("animal_tag") or payload.get("tag")
            elif tipo in ("celo", "servicio"):
                tag_asoc = payload.get("vaca_tag") or payload.get("tag")
            else:
                tag_asoc = payload.get("animal_tag") or payload.get("vaca_tag") or payload.get("tag")

            tag_clean = re.sub(r"[^A-Za-z0-9_-]+", "_", str(tag_asoc or "campo"))
            ts = int(time.time())
            rnd = uuid.uuid4().hex[:6]
            fname = f"cap_{tipo}_{tag_clean}_{ts}_{rnd}.jpg"
            dest_file = os.path.join(media_dir_abs, fname)
            with open(dest_file, "wb") as f:
                f.write(raw_bytes)

            ruta_rel = os.path.join("media", fname).replace("\\", "/")
            caption_txt = f"Captura {tipo.capitalize()} · {tag_asoc or ''}".strip()
            if tipo == "parto":
                caption_txt = f"Parto: cría {payload.get('id_cria_tag') or 'S/D'} (madre {payload.get('vaca_tag') or 'S/D'})".strip()
            elif tipo == "tratamiento":
                caption_txt = f"Tratamiento: {payload.get('producto') or ''} ({tag_asoc or ''})".strip()
            elif tipo == "muerte":
                caption_txt = f"Muerte: {payload.get('causa_presunta') or ''} ({tag_asoc or ''})".strip()
            elif tipo == "destete":
                caption_txt = f"Destete: cría {tag_asoc or 'S/D'}".strip()
            elif tipo == "secado":
                caption_txt = f"Secado: {tag_asoc or 'S/D'}".strip()
            elif tipo == "leche":
                litros_str = f"{payload.get('litros')} L" if payload.get("litros") is not None else ""
                caption_txt = f"Recibo/Planilla de Leche: {litros_str} · {fecha}".strip()
            elif tipo == "gasto":
                caption_txt = f"Factura/Recibo: {payload.get('categoria') or ''} · {payload.get('concepto') or ''}".strip(" ·")

            fid = db_inst.registrar_foto(
                ruta=ruta_rel,
                animal_tag=tag_asoc,
                fecha=fecha,
                caption=caption_txt,
                user_id=uid_user,
                notas=f"Captura rápida en campo ({tipo}): {payload.get('notas') or payload.get('diagnostico') or ''}".strip(),
            )

            # Para parto, si se especificaron cría y madre, vincular también a la madre
            if tipo == "parto" and payload.get("id_cria_tag") and payload.get("vaca_tag") and str(payload.get("id_cria_tag")) != str(payload.get("vaca_tag")):
                try:
                    db_inst.registrar_foto(
                        ruta=ruta_rel,
                        animal_tag=payload.get("vaca_tag"),
                        fecha=fecha,
                        caption=caption_txt,
                        user_id=uid_user,
                        notas=f"Parto madre {payload.get('vaca_tag')} de la cría {payload.get('id_cria_tag')}",
                    )
                except Exception:
                    pass

            return fid
        except Exception as err:
            logger.exception("Error al guardar foto adjunta de captura: %s", err)
            return None

    @app.post("/api/sync")
    @_limite_api("sync")
    def api_sync():
        from datetime import datetime

        datos = request.get_json(silent=True) or {}
        eventos = datos.get("eventos", [])
        if not isinstance(eventos, list):
            return jsonify({"error": "Se esperaba una lista en 'eventos'."}), 400

        db_sync = _db(db_path)
        procesados = 0
        errores = []
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
                if not isinstance(id_local, str) or not id_local.strip():
                    id_local = None
                else:
                    id_local = id_local.strip()[:128]

                # Idempotencia (P0.1): si este id_local ya fue procesado, el
                # reintento del cliente (respuesta perdida en conexión rural)
                # NO debe volver a registrar el evento; se devuelve en ids_ok
                # para que el cliente purgue la cola igual que la primera vez.
                if id_local:
                    ya_procesado = db_sync.query_one(
                        "SELECT 1 AS ok FROM sync_ids_procesados WHERE id_local = ?",
                        (id_local,),
                    )
                    if ya_procesado:
                        ids_ok.append(id_local)
                        procesados += 1
                        continue

                n_ids_previos = len(ids_ok)
                try:
                    if tipo == "parto":
                        tipo_evento = str(payload.get("tipo_evento") or "PARTO").upper()
                        padre_tag = payload.get("padre_tag") or payload.get("toro_tag") or payload.get("toro") or None
                        primer_id = db_sync.registrar_parto(
                            vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                            fecha=fecha,
                            sexo_cria=payload.get("sexo_cria"),
                            estado_cria=payload.get("estado_cria", "VIVO"),
                            peso_nacimiento=payload.get("peso_nacimiento"),
                            id_cria_tag=payload.get("id_cria_tag"),
                            notas=payload.get("notas"),
                            potrero_cria=payload.get("potrero_cria"),
                            potrero_madre=payload.get("potrero_madre"),
                            registrado_por=uid,
                            tipo_evento=tipo_evento,
                            padre_tag=padre_tag,
                            distocia=bool(payload.get("distocia")),
                        )
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                        # Parto gemelar: el segundo gemelo viaja en
                        # payload.gemelo y se registra como una segunda fila
                        # de partos agrupada por grupo_parto_id (ver
                        # Database.registrar_parto, que ya dejó grupo_parto_id
                        # = primer_id en la primera fila).
                        gemelo = payload.get("gemelo") if tipo_evento == "GEMELAR" else None
                        if gemelo and primer_id:
                            db_sync.registrar_parto(
                                vaca_tag=payload.get("vaca_tag") or payload.get("tag"),
                                fecha=fecha,
                                sexo_cria=gemelo.get("sexo_cria"),
                                estado_cria=gemelo.get("estado_cria", "VIVO"),
                                peso_nacimiento=gemelo.get("peso_nacimiento"),
                                id_cria_tag=gemelo.get("id_cria_tag"),
                                notas=payload.get("notas"),
                                potrero_cria=payload.get("potrero_cria"),
                                registrado_por=uid,
                                tipo_evento="GEMELAR",
                                grupo_parto_id=primer_id,
                                padre_tag=padre_tag,
                            )
                    elif tipo == "destete":
                        db_sync.registrar_destete(
                            cria_tag=payload.get("cria_tag") or payload.get("animal_tag") or payload.get("tag"),
                            fecha=fecha,
                            peso_kg=payload.get("peso_kg"),
                            potrero_cria=payload.get("potrero_cria"),
                            potrero_madre=payload.get("potrero_madre"),
                            peso_madre_kg=payload.get("peso_madre_kg"),
                            cond_corporal_madre=payload.get("cond_corporal_madre"),
                            notas=payload.get("notas"),
                            registrado_por=uid,
                        )
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "secado":
                        db_sync.registrar_secado(
                            vaca_tag=payload.get("animal_tag") or payload.get("vaca_tag") or payload.get("tag"),
                            fecha=fecha,
                            potrero_destino=payload.get("potrero_destino"),
                            cond_corporal=payload.get("cond_corporal"),
                            motivo=payload.get("motivo"),
                            notas=payload.get("notas"),
                            registrado_por=uid,
                        )
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
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
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
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
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
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
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
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
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
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
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
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
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "leche":
                        db_sync.registrar_produccion_leche(
                            fecha=fecha,
                            litros=payload.get("litros"),
                            notas=payload.get("notas"),
                        )
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo == "gasto":
                        fid_finanza = db_sync.registrar_finanza(
                            fecha=fecha,
                            tipo=payload.get("tipo_finanza") or "EGRESO",
                            categoria=payload.get("categoria"),
                            concepto=payload.get("concepto"),
                            monto=payload.get("monto"),
                            litros=payload.get("litros"),
                            animal_tag=payload.get("animal_tag") or None,
                            potrero=payload.get("potrero") or None,
                            contraparte=payload.get("contraparte") or None,
                            notas=payload.get("notas"),
                            registrado_por=uid,
                        )
                        foto_ruta_directa = (payload.get("foto_ruta") or "").strip() or None
                        if foto_ruta_directa:
                            # La foto ya se guardó al analizar la factura con IA
                            # (ver /api/finanzas/analizar-factura) -- solo se
                            # enlaza, no se vuelve a subir el mismo archivo.
                            db_sync.execute(
                                "UPDATE finanzas SET foto_ruta = ? WHERE id = ?",
                                (foto_ruta_directa, fid_finanza),
                            )
                        else:
                            fid_foto = _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                            if fid_foto:
                                foto_fila = db_sync.query_one("SELECT ruta FROM fotos WHERE id = ?", (fid_foto,))
                                if foto_fila and foto_fila["ruta"]:
                                    db_sync.execute(
                                        "UPDATE finanzas SET foto_ruta = ? WHERE id = ?",
                                        (foto_fila["ruta"], fid_finanza),
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
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo in ("tarea", "recordatorio"):
                        msg_tarea = payload.get("mensaje") or payload.get("descripcion") or f"Tarea: {payload.get('tipo_tarea', 'Campo')}"
                        db_sync.registrar_recordatorio(
                            mensaje=msg_tarea,
                            fecha_programada=fecha,
                            hora=payload.get("hora"),
                            creado_por=uid,
                            asignado_a=payload.get("asignado_a"),
                            tipo_objetivo=payload.get("tipo_objetivo"),
                            animal_tag=payload.get("animal_tag") or payload.get("tag"),
                            potrero_nombre=payload.get("potrero_nombre") or payload.get("potrero"),
                            tipo_tarea=payload.get("tipo_tarea"),
                            prioridad=payload.get("prioridad") or "NORMAL",
                        )
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
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
                    elif tipo in ("palpacion", "tacto", "diagnostico"):
                        p_peso = payload.get("peso_kg")
                        p_cc = payload.get("cond_corporal")
                        peso_val = float(p_peso) if (p_peso and str(p_peso).replace(".", "", 1).isdigit()) else None
                        cc_val = float(p_cc) if (p_cc and str(p_cc).replace(".", "", 1).isdigit()) else None
                        db_sync.registrar_diagnostico(
                            vaca_tag=payload.get("animal_tag") or payload.get("tag") or payload.get("vaca_tag"),
                            fecha=fecha,
                            resultado=payload.get("resultado") or "PREÑADA",
                            dias_gestacion=payload.get("dias_gestacion"),
                            responsable=payload.get("responsable") or payload.get("veterinario"),
                            registrado_por=uid,
                            metodo=payload.get("metodo") or "TACTO",
                            hallazgo=payload.get("hallazgo"),
                            detalle=payload.get("detalle") or payload.get("notas"),
                            toro_pajuela=payload.get("toro_pajuela") or payload.get("reproductor"),
                            peso_kg=peso_val,
                            cond_corporal=cc_val,
                        )
                        _guardar_foto_evento(db_sync, payload, tipo, fecha, uid)
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo in ("nitrogeno", "recarga_nitrogeno"):
                        db_sync.registrar_recarga_nitrogeno(
                            fecha_recarga=fecha,
                            dias_intervalo=int(payload.get("dias_intervalo") or 21),
                            proxima_recarga=payload.get("proxima_recarga"),
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo in ("pajuela", "pajuela_add", "inventario_pajuela"):
                        db_sync.registrar_pajuela(
                            codigo_toro=payload.get("codigo_toro") or payload.get("toro"),
                            raza=payload.get("raza"),
                            procedencia=payload.get("procedencia"),
                            canastilla=payload.get("canastilla"),
                            cantidad=int(payload.get("cantidad") or 1),
                            costo=float(payload.get("costo") or 0.0),
                            fecha_ingreso=fecha,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo in ("aforo", "aforo_potrero"):
                        afo_val = float(payload.get("aforo_kg_m2") or payload.get("aforo") or 0.0)
                        db_sync.registrar_aforo(
                            potrero_id_o_nom=payload.get("potrero_id") or payload.get("potrero") or payload.get("nombre"),
                            aforo_kg_m2=afo_val,
                            fecha=fecha,
                            metodo=payload.get("metodo") or "CUADRO_1M2",
                            registrado_por=uid,
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo in ("inseminador", "nuevo_inseminador"):
                        db_sync.registrar_inseminador(
                            nombre=payload.get("nombre"),
                            telefono=payload.get("telefono"),
                            notas=payload.get("notas"),
                        )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo in ("iatf_paso", "droga_iatf"):
                        lid_p = payload.get("lote_id")
                        if lid_p:
                            db_sync.registrar_avance_paso_iatf(
                                lote_id=int(lid_p),
                                paso_index=int(payload.get("paso_index") or 0),
                                producto_aplicado=payload.get("producto"),
                                dosis=payload.get("dosis"),
                                marca=payload.get("marca"),
                                realizado_por=payload.get("realizado_por") or str(uid or ""),
                                notas=payload.get("notas"),
                            )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    elif tipo in ("iatf_inseminar", "lote_iatf_inseminar"):
                        lid_i = payload.get("lote_id")
                        if lid_i:
                            db_sync.ejecutar_inseminacion_lote_iatf(
                                lote_id=int(lid_i),
                                toro_pajuela=payload.get("toro_pajuela") or payload.get("toro"),
                                inseminador=payload.get("inseminador"),
                                fecha=fecha,
                            )
                        procesados += 1
                        if id_local:
                            ids_ok.append(id_local)
                    else:
                        errores.append(f"Tipo de evento no reconocido: {tipo}")

                    # Idempotencia (P0.1): el evento se procesó bien en esta
                    # pasada -> persistir su id_local para que un reintento
                    # futuro (misma cola offline reenviada) no lo duplique.
                    if id_local and len(ids_ok) > n_ids_previos:
                        db_sync.execute(
                            "INSERT OR IGNORE INTO sync_ids_procesados "
                            "(id_local, user_id, tipo_evento, procesado_en) "
                            "VALUES (?, ?, ?, ?)",
                            (id_local, uid, tipo, datetime.now().isoformat(timespec="seconds")),
                        )
                except Exception as e:
                    logger.exception("Error al sincronizar evento %s: %s", id_local, e)
                    errores.append(f"Error en evento {id_local or tipo}")

            # Poda barata de la tabla de idempotencia: los reintentos del
            # cliente ocurren a los minutos/horas, no a los meses. Ventana de
            # 7 días cubre cualquier cola offline larga sin crecimiento
            # ilimitado en el SQLite del VPS.
            try:
                db_sync.execute(
                    "DELETE FROM sync_ids_procesados "
                    "WHERE procesado_en < datetime('now', '-7 days', 'localtime')"
                )
            except Exception:
                pass

            return jsonify({
                "ok": True,
                "procesados": procesados,
                "total": len(eventos),
                "errores": errores,
                "ids_ok": ids_ok,
            })
        finally:
            db_sync.close()

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
            fila_origen = db_t.query_one(
                "SELECT id, nombre FROM potreros WHERE geom_wkt_4326 IS NOT NULL AND (nombre = ? OR codigo = ?)",
                (nombre_origen, nombre_origen),
            )
            fila_destino = db_t.query_one(
                "SELECT id, nombre FROM potreros WHERE geom_wkt_4326 IS NOT NULL AND (nombre = ? OR codigo = ?)",
                (nombre_destino, nombre_destino),
            )
            if not fila_origen:
                return jsonify({"ok": False, "error": f"'{nombre_origen}' no es un potrero real (sin mapa/geometría) o no existe."}), 404
            if not fila_destino:
                return jsonify({"ok": False, "error": f"'{nombre_destino}' no es un potrero real (sin mapa/geometría) o no existe."}), 404

            tags = db_t.animales_activos_en_potrero(fila_origen["id"])
            uid = session.get("user_id")
            for tag in tags:
                db_t.registrar_traslado(
                    animal_tag=tag, fecha=fecha,
                    potrero_origen=fila_origen["id"], potrero_destino=fila_destino["id"],
                    motivo=motivo, registrado_por=uid,
                )
            return jsonify({
                "ok": True, "movidos": len(tags), "animales": tags,
                "potrero_origen": fila_origen["nombre"], "potrero_destino": fila_destino["nombre"],
            })
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
                from ..engine.query_engine import QueryEngine
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
                    from ..parsers.media_handler import transcribe_audio
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

        os.makedirs(REPORTES_DIR_DEFAULT, exist_ok=True)
        sec_sufijo = f"_{seccion}" if seccion else ""
        ruta_salida = os.path.join(REPORTES_DIR_DEFAULT, f"reporte_ja{sec_sufijo}_{periodo}_{int(time.time())}.pdf")

        db_rep = _db(db_path)
        try:
            try:
                from ..reports.pdf_report import generar_pdf
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
                from ..reports.excel_report import exportar_excel_bytes
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

    @app.get("/api/pajuelas")
    def api_pajuelas():
        db_inst = _db(db_path)
        try:
            pajuelas = _filas_dict(db_inst.listar_pajuelas())
            alertas = _filas_dict(db_inst.alertas_stock_pajuelas(3))
            termo = db_inst.ultimo_estado_termo()
            return jsonify({
                "ok": True,
                "pajuelas": pajuelas,
                "alertas_stock": alertas,
                "termo": termo,
                "total_pajuelas": sum(p.get("cantidad", 0) for p in pajuelas),
                "total_toros": len(pajuelas),
            })
        finally:
            db_inst.close()

    @app.post("/api/pajuelas")
    def api_pajuelas_crear():
        if _rol_actual() not in ("OWNER", "ADMIN", "MAYORDOMO"):
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
            return _error_interno(400, con_ok=False)
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
                    r_dict["usuario_nombre"] = "Software Ganadero (SG)"
                    r_dict["usuario_rol"] = "SISTEMA"
                    r_dict["usuario_avatar"] = "admin"
                    r_dict["canal"] = "Backup SG"

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
                from ..engine.mapa_data import datos_mapa_finca
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
                from ..reports.qr_fichas import generar_ficha_qr_individual
            except ImportError:  # ejecución directa
                from src.reports.qr_fichas import generar_ficha_qr_individual  # type: ignore
            # URL pública para imprimir en la tarjeta: la de la propia petición.
            try:
                base_url = request.host_url.rstrip("/")
            except Exception:
                base_url = ""
            tag_clean = unquote(str(tag or "")).strip()
            ruta = generar_ficha_qr_individual(
                db_pdf, tag_clean, media_dir=MEDIA_DIR_DEFAULT, base_url=base_url,
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
    @_limite_api("grafico")
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
