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
from types import SimpleNamespace
import os
from urllib.parse import urlparse
import socket
import sys

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
import mimetypes
import secrets
import time
from typing import Any, Optional

_RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ_REPO not in sys.path:
    sys.path.insert(0, _RAIZ_REPO)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_RAIZ_REPO, ".env"))
except ImportError:
    pass

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
        datos_carne as _datos_carne,
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
        datos_carne as _datos_carne,
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
    "bluetooth=(self), payment=(), usb=(), magnetometer=(), gyroscope=(), "
    "publickey-credentials-get=(self), publickey-credentials-create=(self)"
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
def _invalidar_tareas() -> None:
    """Las listas de trabajo se cachean 60 s para los badges; un evento nuevo
    las debe refrescar al instante."""
    try:
        from src.engine.tareas import invalidar_cache
        invalidar_cache()
    except Exception:
        logger.debug("no se pudo invalidar el caché de tareas", exc_info=True)


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


def datos_repro(db_path: str = DB_PATH_DEFAULT, desde: Optional[str] = None,
                hasta: Optional[str] = None) -> dict:
    """Reproducción: FEP≤30d, eco d35 / palpación d60, celos AM-PM pendientes."""
    # Envoltorio fino WS-2: el SQL vive en engine.dashboard_data.datos_reproduccion.
    db = _db(db_path)
    try:
        try:
            return _datos_reproduccion(db, desde=desde, hasta=hasta)
        except Exception:
            logger.exception("datos_repro fallo completo")
            return {"fep_30d": [], "celos_recientes": [], "diagnosticos": [],
                    "eco_palp_pendientes": [], "errores": {"repro": "error interno"}}
    finally:
        try:
            db.close()
        except Exception:
            pass


def datos_carne(db_path: str = DB_PATH_DEFAULT, desde: Optional[str] = None,
                hasta: Optional[str] = None) -> dict:
    """Carne: sin pesar, a pesar por edad, destete/índice, proyección y prueba."""
    # Envoltorio fino WS-2: el SQL vive en engine.dashboard_data.datos_carne.
    db = _db(db_path)
    try:
        try:
            return _datos_carne(db, desde=desde, hasta=hasta)
        except Exception:
            logger.exception("datos_carne fallo completo")
            return {"sin_pesar": {"nunca": [], "vencidos": []}, "a_pesar_edad": [],
                    "destetes": [], "indice_productivo": [],
                    "proyeccion_destetes": [], "proyeccion_destetes_mes": [],
                    "prueba_comportamiento": {"animales": []},
                    "errores": {"carne": "error interno"}}
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
    _RUTAS_PUBLICAS = {
        "login_form", "login_submit", "static", "manifest", "sw_js", "offline_page",
        # WebAuthn: el login con huella ocurre SIN sesión todavía. El POST ya
        # queda protegido por el chequeo de Origin/Referer de más abajo.
        "webauthn_disponible", "webauthn_login_opciones", "webauthn_login_verificar",
    }

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
        # OJO: no importar `time` aquí. Un import dentro de esta función haría
        # que `time` fuese una variable LOCAL de `crear_app` para todo el
        # compilador, sin valor cuando la rama no se ejecuta (producción), y
        # cualquier `time.time()` de la app (caché de gráficos, WebAuthn…)
        # reventaría con UnboundLocalError. El import de módulo ya existe.
        import tempfile
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
        "chat": (40, 60.0),
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

    def _bloqueo_gestion_usuario(mi_rol: Optional[str], objetivo: Optional[dict]) -> Optional[str]:
        """Regla de jerarquía al modificar un usuario existente (PIN, rol, datos).

        ``objetivo`` debe resolverse con ``Auth.obtener_usuario`` (que busca por
        user_id Y por telegram_id): comparar solo ``user_id`` dejaba que un ADMIN
        llegara al OWNER usando su telegram_id. Devuelve el mensaje de error o None.
        """
        if not objetivo or mi_rol == "OWNER":
            return None
        rol_obj = str(objetivo.get("rol", "")).strip().upper()
        if rol_obj == "OWNER":
            return "Un ADMIN no puede modificar a un usuario OWNER (Level 1)."
        if rol_obj in ("ADMIN", "ADMINISTRADOR"):
            try:
                mi_uid = int(session.get("user_id")) if session.get("user_id") is not None else None
            except (TypeError, ValueError):
                mi_uid = None
            if mi_uid is None or mi_uid not in (objetivo.get("user_id"), objetivo.get("telegram_id")):
                return "Un ADMIN solo puede modificar su propio usuario o usuarios TRABAJADOR."
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
    # Rutas por dominio (src/pwa/rutas/*.py). Comparten el estado de este
    # cierre por ctx (valores) y h (funciones), sin cambiar nombres de
    # endpoint ni URLs.
    ctx = SimpleNamespace(
        _castigo_store=_castigo_store,
        _login_store=_login_store,
        clave_esperada=clave_esperada,
        db_path=db_path,
        pwa_version=pwa_version,
        users_file=users_file,
    )
    h = SimpleNamespace(
        _bloqueo_gestion_usuario=_bloqueo_gestion_usuario,
        _cliente_ip=_cliente_ip,
        _limite_api=_limite_api,
        _login_bloqueado=_login_bloqueado,
        _login_registrar_intento=_login_registrar_intento,
        _rol_actual=_rol_actual,
        _texto_espera=_texto_espera,
        _usuario_actual=_usuario_actual,
    )
    try:
        from .rutas import registrar_todas
    except ImportError:  # ejecución directa: python src/pwa/app.py
        from src.pwa.rutas import registrar_todas  # type: ignore
    registrar_todas(app, ctx, h)

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
            # clear_untrusted_proxy_headers=False: waitress por defecto borra
            # X-Forwarded-Proto/For del proxy (Caddy/nginx) y la app veía
            # "http" y la IP del proxy -> WebAuthn fallaba por origen y el
            # rate-limit de /login trataba a todos como una sola IP. ProxyFix
            # (1 salto, ver crear_app) ya decide en qué confiar.
            serve(_app, host=_host, port=_puerto, threads=8,
                  clear_untrusted_proxy_headers=False)
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
