"""Datos de lectura del Dashboard PWA (WS-2).

Funciones puras que reciben ``db`` (instancia Database) como primer
parámetro y devuelven la MISMA forma de datos que produce ``src/pwa/app.py``.
SQL movido tal cual desde pwa/app.py (con sus comentarios). Cada sección SQL
está envuelta en su propio try/except: si falla, se loguea con
``logger.error(..., exc_info=True)`` y se acumula en ``errores`` en vez de
devolver un "falso 0/empty" silencioso.

Solo puede importar de ``src.db.database``, ``src.utils`` y stdlib.
NO importa pwa.app ni charts (evita ciclos).
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

try:
    from ..db.database import Database
except ImportError:  # ejecución directa
    from src.db.database import Database  # type: ignore

logger = logging.getLogger(__name__)

MEDIA_DIR_DEFAULT = os.getenv("MEDIA_DIR", "media")


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


def conteos_tablero(db: Database, potrero: Optional[str] = None) -> dict:
    """Tablero finca: activos por categoría, eventos 7d, retiros activos."""
    hoy = date.today()
    hace7 = (hoy - timedelta(days=7)).isoformat()
    hoy_iso = hoy.isoformat()
    errores: dict[str, str] = {}
    filtro_pot = ""
    params: tuple = ()
    if potrero:
        try:
            pid = db.potrero_id(potrero)
        except Exception as e:
            logger.error("seccion potrero_filtro fallo al resolver potrero", exc_info=True)
            errores["potrero_filtro"] = str(e)
            pid = None
        if pid is not None:
            filtro_pot = " AND (a.potrero_id = ? OR a.id_animal IN (SELECT animal_id FROM traslados WHERE potrero_destino = ?))"
            params = (pid, pid)
    base = f"FROM animales a WHERE a.estado = 'ACTIVO'{filtro_pot}"
    try:
        n = db.query_one(f"SELECT COUNT(*) n {base}", params)
        hem = db.query_one(f"SELECT COUNT(*) n {base} AND UPPER(a.sexo) LIKE 'H%'", params)
        mac = db.query_one(f"SELECT COUNT(*) n {base} AND UPPER(a.sexo) LIKE 'M%'", params)
        activos = int(n["n"]) if n else 0
        hembras = int(hem["n"]) if hem else 0
        machos = int(mac["n"]) if mac else 0
    except Exception as e:
        logger.error("seccion conteos_tablero fallo en conteos base", exc_info=True)
        errores["conteos"] = str(e)
        activos, hembras, machos = 0, 0, 0

    def _cnt(tabla: str, col: str = "vaca_id", fid: str = "id_animal") -> int:
        # Eventos 7d restringidos a animales ACTIVOS (y potrero si se filtra).
        r = db.query_one(
            f"SELECT COUNT(*) n FROM {tabla} e JOIN animales a ON a.id_animal = e.{col} "
            f"WHERE a.estado = 'ACTIVO' AND e.fecha >= ? AND e.fecha <= ?{filtro_pot}",
            (hace7, hoy_iso) + params,
        )
        return int(r["n"]) if r else 0

    try:
        partos_7d = _cnt("partos")
    except Exception as e:
        logger.error("seccion partos_7d fallo", exc_info=True)
        errores["partos_7d"] = str(e)
        partos_7d = 0
    try:
        celos_7d = _cnt("celos")
    except Exception as e:
        logger.error("seccion celos_7d fallo", exc_info=True)
        errores["celos_7d"] = str(e)
        celos_7d = 0
    try:
        servicios_7d = _cnt("servicios")
    except Exception as e:
        logger.error("seccion servicios_7d fallo", exc_info=True)
        errores["servicios_7d"] = str(e)
        servicios_7d = 0
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
    except Exception as e:
        logger.error("seccion retiros_activos fallo", exc_info=True)
        errores["retiros_activos"] = str(e)
        retiros = 0
    try:
        por_potrero = _filas_dict(db.query(
            "SELECT COALESCE(p.nombre, p.codigo, 'Sin potrero') potrero, COUNT(*) n "
            "FROM animales a LEFT JOIN potreros p ON p.id = a.potrero_id "
            "WHERE a.estado = 'ACTIVO' GROUP BY potrero ORDER BY n DESC LIMIT 20"
        ))
    except Exception as e:
        logger.error("seccion por_potrero fallo", exc_info=True)
        errores["por_potrero"] = str(e)
        por_potrero = []
    out = {
        "activos": activos,
        "hembras": hembras,
        "machos": machos,
        "partos_7d": partos_7d,
        "celos_7d": celos_7d,
        "servicios_7d": servicios_7d,
        "retiros_activos": retiros,
        "por_potrero": por_potrero,
        "potrero_filtro": potrero,
    }
    if errores:
        out["errores"] = errores
    return out


def datos_reproduccion(db: Database) -> dict:
    """Reproducción: FEP≤30d, eco d35 / palpación d60, celos AM-PM pendientes."""
    hoy = date.today()
    hoy_iso_repro = hoy.isoformat()
    lim = (hoy + timedelta(days=30)).isoformat()
    errores: dict[str, str] = {}
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
    except Exception as e:
        logger.error("seccion fep_30d fallo", exc_info=True)
        errores["fep_30d"] = str(e)
        fep = []
    try:
        celos = _filas_dict(db.query(
            """SELECT a.tag, c.fecha, c.am_pm FROM celos c
               JOIN animales a ON a.id_animal = c.vaca_id
               WHERE a.estado = 'ACTIVO' ORDER BY c.fecha DESC LIMIT 20"""))
    except Exception as e:
        logger.error("seccion celos_recientes fallo", exc_info=True)
        errores["celos_recientes"] = str(e)
        celos = []
    try:
        diags = _filas_dict(db.query(
            """SELECT a.tag, d.fecha, d.resultado, d.dias_gestacion FROM diagnosticos_gestacion d
               JOIN animales a ON a.id_animal = d.vaca_id
               WHERE a.estado = 'ACTIVO' ORDER BY d.fecha DESC LIMIT 20"""))
    except Exception as e:
        logger.error("seccion diagnosticos fallo", exc_info=True)
        errores["diagnosticos"] = str(e)
        diags = []
    try:
        pendientes = _filas_dict(db.query(
            "SELECT tipo_alerta, fecha_programada, descripcion FROM alertas "
            "WHERE estado = 'PENDIENTE' AND tipo_alerta IN ('ECOGRAFIA','PALPACION') "
            "ORDER BY fecha_programada LIMIT 30"))
    except Exception as e:
        logger.error("seccion eco_palp_pendientes fallo", exc_info=True)
        errores["eco_palp_pendientes"] = str(e)
        pendientes = []
    out: dict[str, Any] = {"fep_30d": fep, "celos_recientes": celos, "diagnosticos": diags,
            "eco_palp_pendientes": pendientes}
    if errores:
        out["errores"] = errores
    return out


def datos_sanidad(db: Database) -> dict:
    """Sanidad: retiros leche/carne con cuenta regresiva + últimos tratamientos."""
    hoy = date.today()
    hoy_iso = hoy.isoformat()
    errores: dict[str, str] = {}
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
    except Exception as e:
        logger.error("seccion retiros fallo", exc_info=True)
        errores["retiros"] = str(e)
        retiros = []
    try:
        ultimos = _filas_dict(db.query(
            """SELECT a.tag, t.producto, t.dosis, t.via, t.fecha FROM tratamientos t
               JOIN animales a ON a.id_animal = t.animal_id
               WHERE a.estado = 'ACTIVO' ORDER BY t.fecha DESC, t.id DESC LIMIT 20"""))
    except Exception as e:
        logger.error("seccion ultimos_tratamientos fallo", exc_info=True)
        errores["ultimos_tratamientos"] = str(e)
        ultimos = []
    out: dict[str, Any] = {"retiros": retiros, "ultimos_tratamientos": ultimos}
    if errores:
        out["errores"] = errores
    return out


def datos_pasturas(db: Database) -> dict:
    """Pasturas: ocupación Voisin (semáforo), reposo y último NDVI."""
    errores: dict[str, str] = {}
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
    except Exception as e:
        logger.error("seccion potreros fallo", exc_info=True)
        errores["potreros"] = str(e)
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
    except Exception as e:
        logger.error("seccion ndvi_reciente fallo", exc_info=True)
        errores["ndvi_reciente"] = str(e)
        ndvi = []
    out: dict[str, Any] = {"potreros": potreros, "ndvi_reciente": ndvi}
    if errores:
        out["errores"] = errores
    return out


def datos_leche(db: Database) -> dict:
    """Leche: serie del tanque (produccion_leche) + últimos controles.

    WS-X4: agrega ``ranking_vacas`` (top vacas por litros acumulados, con su
    último control) para KPIs de leche por animal en el dashboard.
    """
    errores: dict[str, str] = {}
    try:
        serie = _filas_dict(db.query(
            "SELECT fecha, SUM(litros) litros FROM produccion_leche "
            "GROUP BY fecha ORDER BY fecha DESC LIMIT 30"))
        serie = list(reversed(serie))
    except Exception as e:
        logger.error("seccion serie_tanque fallo", exc_info=True)
        errores["serie_tanque"] = str(e)
        serie = []
    try:
        controles = _filas_dict(db.query(
            """SELECT a.tag, l.fecha, l.litros FROM produccion_leche l
               LEFT JOIN animales a ON a.id_animal = l.animal_id
               ORDER BY l.fecha DESC LIMIT 20"""))
    except Exception as e:
        logger.error("seccion controles fallo", exc_info=True)
        errores["controles"] = str(e)
        controles = []
    try:
        ranking = _filas_dict(db.query(
            """SELECT a.tag, COUNT(l.id) AS controles, SUM(l.litros) AS total_litros,
                      MAX(l.fecha) AS ultima_fecha
               FROM produccion_leche l JOIN animales a ON a.id_animal = l.animal_id
               WHERE a.estado = 'ACTIVO' AND l.litros IS NOT NULL
               GROUP BY a.id_animal, a.tag
               HAVING SUM(l.litros) > 0
               ORDER BY total_litros DESC LIMIT 8"""))
        for r in ranking:
            try:
                r["total_litros"] = round(float(r["total_litros"]), 1)
            except (TypeError, ValueError):
                r["total_litros"] = 0
    except Exception as e:
        logger.error("seccion ranking_vacas fallo", exc_info=True)
        errores["ranking_vacas"] = str(e)
        ranking = []
    out: dict[str, Any] = {"serie_tanque": serie, "controles": controles,
                           "ranking_vacas": ranking}
    if errores:
        out["errores"] = errores
    return out


def datos_ficha_animal(db: Database, tag: str) -> dict:
    """Ficha animal: header + historial resumido + QR payload (abre /ficha/<tag>)."""
    errores: dict[str, str] = {}
    t = str(tag or "").strip()
    try:
        aid = db.resolve_animal(t)
    except Exception as e:
        logger.error("seccion ficha resolve_animal fallo", exc_info=True)
        errores["resolve"] = str(e)
        aid = None
    if aid is None:
        out: dict[str, Any] = {"existe": False, "tag": t}
        if errores:
            out["errores"] = errores
        return out
    an = db.get_animal(aid)
    base: dict[str, Any] = {"existe": True, "tag": an["tag"], "nombre": an["nombre"],
            "sexo": an["sexo"], "raza": an["raza"],
            "fecha_nacimiento": an["fecha_nacimiento"], "estado": an["estado"],
            "qr_payload": f"JA://animal/{an['tag']}", "qr_url": f"/ficha/{an['tag']}"}
    try:
        base["ultimo_parto"] = dict(db.ultimo_parto(aid)) if db.ultimo_parto(aid) else None
    except Exception as e:
        logger.error("seccion ultimo_parto fallo", exc_info=True)
        errores["ultimo_parto"] = str(e)
        base["ultimo_parto"] = None
    try:
        base["ultimo_servicio"] = dict(db.ultimo_servicio(aid)) if db.ultimo_servicio(aid) else None
    except Exception as e:
        logger.error("seccion ultimo_servicio fallo", exc_info=True)
        errores["ultimo_servicio"] = str(e)
        base["ultimo_servicio"] = None
    try:
        base["pesajes"] = _filas_dict(db.query(
            "SELECT fecha, peso_kg, gmd_calculada FROM pesajes WHERE animal_id = ? "
            "ORDER BY fecha DESC LIMIT 5", (aid,)))
    except Exception as e:
        logger.error("seccion pesajes fallo", exc_info=True)
        errores["pesajes"] = str(e)
        base["pesajes"] = []
    try:
        base["tratamientos"] = _filas_dict(db.query(
            "SELECT fecha, producto, dosis, fecha_fin_retiro_leche, fecha_fin_retiro_carne "
            "FROM tratamientos WHERE animal_id = ? ORDER BY fecha DESC LIMIT 5", (aid,)))
    except Exception as e:
        logger.error("seccion tratamientos fallo", exc_info=True)
        errores["tratamientos"] = str(e)
        base["tratamientos"] = []
    try:
        fotos = db.fotos_de(aid, limit=3)
        base["fotos"] = [
            {"fecha": f["fecha"], "caption": f["caption"],
             "url": f"/media/{_ruta_relativa_media(f['ruta'])}" if f["ruta"] else None}
            for f in fotos
        ]
    except Exception as e:
        logger.error("seccion fotos fallo", exc_info=True)
        errores["fotos"] = str(e)
        base["fotos"] = []
    # --- WS-X4: secciones enriquecidas de la ficha (reproducción + leche) ---
    es_hembra = str(an["sexo"] or "").lower().startswith("h") or str(an["sexo"] or "").lower().startswith("f")
    try:
        base["partos"] = _filas_dict(db.query(
            """SELECT p.fecha, p.sexo_cria, p.estado_cria, p.peso_nacimiento, c.tag AS cria_tag
               FROM partos p LEFT JOIN animales c ON c.id_animal = p.id_cria
               WHERE p.vaca_id = ? AND (p.id_cria IS NULL OR p.id_cria != ?)
               ORDER BY p.fecha DESC LIMIT 8""", (aid, aid)))
    except Exception as e:
        logger.error("seccion partos fallo", exc_info=True)
        errores["partos"] = str(e)
        base["partos"] = []
    try:
        base["servicios"] = _filas_dict(db.query(
            """SELECT fecha, tipo_servicio, toro_pajilla, inseminador, fep_calculada, estado
               FROM servicios WHERE vaca_id = ? ORDER BY fecha DESC, id DESC LIMIT 8""", (aid,)))
    except Exception as e:
        logger.error("seccion servicios fallo", exc_info=True)
        errores["servicios"] = str(e)
        base["servicios"] = []
    try:
        base["diagnosticos"] = _filas_dict(db.query(
            """SELECT fecha, resultado, dias_gestacion FROM diagnosticos_gestacion
               WHERE vaca_id = ? ORDER BY fecha DESC, id DESC LIMIT 6""", (aid,)))
    except Exception as e:
        logger.error("seccion diagnosticos fallo", exc_info=True)
        errores["diagnosticos"] = str(e)
        base["diagnosticos"] = []
    lactancia: Optional[dict[str, Any]] = None
    try:
        if es_hembra and base.get("ultimo_parto") and base["ultimo_parto"].get("fecha"):
            f_parto = to_date_safe(base["ultimo_parto"]["fecha"])
            if f_parto:
                del_dias = max(0, (date.today() - f_parto).days)
                lactancia = {
                    "del_dias": del_dias,
                    "estado": "En ordeño" if del_dias < 300 else "Seca",
                    "fecha_parto": base["ultimo_parto"]["fecha"],
                }
    except Exception as e:
        logger.error("seccion lactancia fallo", exc_info=True)
        errores["lactancia"] = str(e)
    base["lactancia"] = lactancia
    try:
        base["controles_leche"] = _filas_dict(db.query(
            "SELECT fecha, litros FROM produccion_leche WHERE animal_id = ? "
            "ORDER BY fecha DESC, id DESC LIMIT 8", (aid,)))
    except Exception as e:
        logger.error("seccion controles_leche fallo", exc_info=True)
        errores["controles_leche"] = str(e)
        base["controles_leche"] = []
    if errores:
        base["errores"] = errores
    return base


def to_date_safe(v) -> Optional[date]:
    """Convierte fecha ISO/texto a date sin lanzar (None si no puede)."""
    if v is None:
        return None
    try:
        from ..utils import to_date
        return to_date(str(v)[:10])
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# WS-X5 / WS-X2 — Búsqueda (autocompletar) y resolución flexible de arete/RFID
# --------------------------------------------------------------------------- #

def datos_buscar(db: Database, q: str, limite: int = 8) -> dict:
    """Autocompletar: animales ACTIVOS y potreros cuyo tag/nombre contenga ``q``.

    Usado por el buscador de la PWA (datalist). Siempre restringe el
    inventario a ``estado='ACTIVO'`` (regla fundamental AGENTS.md).
    """
    texto = str(q or "").strip()
    out: dict[str, Any] = {"animales": [], "potreros": []}
    errores: dict[str, str] = {}
    if not texto:
        return out
    try:
        like = f"%{texto}%"
        filas = db.query(
            """SELECT a.tag, a.nombre, a.sexo, a.raza FROM animales a
               WHERE a.estado = 'ACTIVO' AND a.tag IS NOT NULL
                 AND (UPPER(a.tag) LIKE UPPER(?) OR UPPER(COALESCE(a.nombre,'')) LIKE UPPER(?))
               ORDER BY a.tag LIMIT ?""",
            (like, like, limite),
        )
        out["animales"] = _filas_dict(filas)
    except Exception as e:
        logger.error("seccion buscar_animales fallo", exc_info=True)
        errores["animales"] = str(e)
    try:
        like = f"%{texto}%"
        filas_p = db.query(
            """SELECT nombre, codigo FROM potreros
               WHERE UPPER(COALESCE(nombre,'')) LIKE UPPER(?)
                  OR UPPER(COALESCE(codigo,'')) LIKE UPPER(?)
               ORDER BY nombre LIMIT ?""",
            (like, like, limite),
        )
        out["potreros"] = _filas_dict(filas_p)
    except Exception as e:
        logger.error("seccion buscar_potreros fallo", exc_info=True)
        errores["potreros"] = str(e)
    if errores:
        out["errores"] = errores
    return out


def resolver_tag_flexible(db: Database, candidato: str, limite: int = 6) -> dict:
    """Resuelve un identificador (arete/RFID/lector de corral) a un animal.

    Estrategias en orden:
    1. match exacto / normalizado (sin guiones, espacios, puntos) vía db.animal_id.
    2. si el candidato es numérico, probar variantes con prefijos conocidos
       (a009, n069, v047, ja26) y relleno con ceros — patrón real de los
       aretes de la finca (misma lógica que ``buscar_foto_animal``).
    3. si el candidato parece código RFID largo (>=10 dígitos), probar los
       últimos 3-8 dígitos como tag numérico.
    4. si no hay match exacto, devolver sugerencias de animales parecidos.

    Devuelve dict con ``existe``/datos del animal o ``sugerencias``. Solo
    lectura, nunca crea ni modifica animales.
    """
    errores: dict[str, str] = {}
    t = str(candidato or "").strip()
    if not t:
        return {"existe": False, "sugerencias": []}
    try:
        aid = db.resolve_animal(t, crear=False)
        if aid is None:
            t_clean = t.upper().replace("-", "").replace(" ", "").replace(".", "")
            aid = db.animal_id(t_clean)
        # Candidato numérico: probar prefijos habituales (a/n/v/ja).
        if aid is None and t_clean.isdigit():
            digitos = t_clean.lstrip("0")
            for pref in ("A", "N", "V", "JA"):
                for pad in (3, 2):
                    variante = f"{pref}{digitos.zfill(pad)}"
                    aid = db.animal_id(variante)
                    if aid:
                        break
                if aid:
                    break
            if aid is None and len(t_clean) >= 6:
                # Posible código RFID largo: usar la cola numérica.
                for n in range(4, 2, -1):
                    aid = db.animal_id(t_clean[-n:].lstrip("0") or t_clean[-n:])
                    if aid:
                        break
        if aid is not None:
            an = db.get_animal(aid)
            # Regla fundamental de inventario: la identificación en corral es
            # para el hato PRESENTE. Un animal VENDIDO/MUERTO/HISTORICO no debe
            # devolverse como match exacto de una lectura de arete (caería a
            # sugerencias de animales ACTIVOS).
            if an and str(an["estado"] or "").upper() == "ACTIVO":
                return {"existe": True, "tag": an["tag"], "nombre": an["nombre"],
                        "sexo": an["sexo"], "raza": an["raza"],
                        "estado": an["estado"]}
        # Sugerencias difusas sobre animales ACTIVOS (tag con substring o dígitos comunes).
        sugs: list[dict] = []
        try:
            like = f"%{t_clean[-5:]}%"
            filas = db.query(
                """SELECT tag, nombre, sexo FROM animales
                   WHERE estado='ACTIVO' AND tag IS NOT NULL
                     AND (UPPER(tag) LIKE UPPER(?) OR REPLACE(REPLACE(REPLACE(UPPER(tag),'-',''),' ',''),'.','') LIKE UPPER(?))
                   ORDER BY tag LIMIT ?""",
                (like, like, limite),
            )
            sugs = _filas_dict(filas)
        except Exception as e:
            logger.error("seccion sugerencias fallo", exc_info=True)
            errores["sugerencias"] = str(e)
        out: dict[str, Any] = {"existe": False, "sugerencias": sugs}
        if errores:
            out["errores"] = errores
        return out
    except Exception as e:
        logger.error("seccion resolver_tag fallo", exc_info=True)
        errores["resolver"] = str(e)
        return {"existe": False, "sugerencias": [], "errores": errores}


# --------------------------------------------------------------------------- #
# WS-5 — Nuevas vistas del dashboard (Inventario SG, Población, Genética, Agenda)
# --------------------------------------------------------------------------- #

def _brackets_a_filas(datos_brackets: dict) -> list[dict]:
    """Convierte el dict de ``calcular_brackets_inventario_sg`` (helpers.py)
    en filas serializables para el frontend (WS-5). Fuente única de la regla
    de brackets: NO se redefine aquí, solo se adapta la forma."""
    filas = []
    for label, count, pct, acum in datos_brackets.get("filas", []):
        filas.append({
            "categoria": label,
            "n": count,
            "pct": round(pct, 2),
            "acum": round(acum, 2),
        })
    return filas


def datos_inventario(db: Database) -> dict:
    """Resumen de inventario SG: brackets etarios exactos + totales por sexo.

    Reutiliza ``engine.query.helpers.calcular_brackets_inventario_sg`` (la
    misma función que usa el bot de Telegram para /animales y /status) para
    que la PWA y Telegram nunca muestren brackets distintos.
    """
    errores: dict[str, str] = {}
    try:
        from .query.helpers import calcular_brackets_inventario_sg
        brackets = calcular_brackets_inventario_sg(db)
    except Exception as e:
        logger.error("seccion inventario_brackets fallo", exc_info=True)
        errores["brackets"] = str(e)
        brackets = {}
    out: dict[str, Any] = {
        "filas": _brackets_a_filas(brackets) if brackets else [],
        "total_activos": brackets.get("total_activos", 0) if brackets else 0,
        "total_hembras": brackets.get("total_hembras", 0) if brackets else 0,
        "total_machos": brackets.get("total_machos", 0) if brackets else 0,
        "total_sin_sexo": brackets.get("total_sin_sexo", 0) if brackets else 0,
        "terneros_menor_12m": brackets.get("terneros_menor_12m", 0) if brackets else 0,
    }
    if errores:
        out["errores"] = errores
    return out


def datos_poblacion(db: Database) -> dict:
    """Composición etaria del hato: brackets SG + edad promedio en años.

    Mismo origen de datos que ``datos_inventario``; añade la edad promedio
    (por animal ACTIVO con fecha de nacimiento resoluble) para la vista
    "Población / Edades".
    """
    errores: dict[str, str] = {}
    try:
        from .query.helpers import calcular_brackets_inventario_sg
        brackets = calcular_brackets_inventario_sg(db)
    except Exception as e:
        logger.error("seccion poblacion_brackets fallo", exc_info=True)
        errores["brackets"] = str(e)
        brackets = {}
    edad_promedio = None
    try:
        # Promedio de edad (días) de animales ACTIVOS con fecha resoluble.
        row = db.query_one(
            """SELECT AVG(julianday('now') - julianday(fecha_nacimiento)) AS dias
               FROM animales WHERE estado='ACTIVO' AND fecha_nacimiento IS NOT NULL"""
        )
        if row and row["dias"] is not None:
            edad_promedio = round(float(row["dias"]) / 365.25, 2)
    except Exception as e:
        logger.error("seccion edad_promedio fallo", exc_info=True)
        errores["edad_promedio"] = str(e)
    out: dict[str, Any] = {
        "filas": _brackets_a_filas(brackets) if brackets else [],
        "total_activos": brackets.get("total_activos", 0) if brackets else 0,
        "total_hembras": brackets.get("total_hembras", 0) if brackets else 0,
        "total_machos": brackets.get("total_machos", 0) if brackets else 0,
        "edad_promedio": edad_promedio,
    }
    if errores:
        out["errores"] = errores
    return out


def datos_genetica(db: Database) -> dict:
    """Distribución racial (genética) del hato ACTIVO: raza -> cabezas + %.

    Usa el MISMO mapa de nombres que el panel /genetica del bot de Telegram
    (src/server/formatters.py ``formatear_genetica_panel``) para que los
    códigos de 1 letra de Software Ganadero (I/T/C/M) se muestren igual en
    la PWA y en Telegram.
    """
    # Mapa canónico de códigos de raza SG (fuente única: formatters.py).
    NOMBRES_RAZAS = {
        "I": "Holstein / Cruce Lechero",
        "T": "Tricross / Cebú Comercial",
        "C": "Cebú / Brahman / Gyr",
        "M": "Mestizo / Doble Propósito",
        "SIN RAZA": "Sin Clasificar",
    }
    errores: dict[str, str] = {}
    filas: list[dict] = []
    total = 0
    try:
        rows = db.query(
            "SELECT COALESCE(NULLIF(TRIM(raza), ''), 'SIN RAZA') raza, COUNT(*) n "
            "FROM animales WHERE estado = 'ACTIVO' GROUP BY raza ORDER BY n DESC"
        )
        total = sum(int(r["n"]) for r in rows)
        for r in rows:
            n = int(r["n"])
            codigo = r["raza"]
            filas.append({
                "raza": codigo,
                "raza_nombre": NOMBRES_RAZAS.get(codigo, codigo),
                "n": n,
                "pct": round(n / total * 100.0, 1) if total else 0.0,
            })
    except Exception as e:
        logger.error("seccion genetica fallo", exc_info=True)
        errores["genetica"] = str(e)
    out: dict[str, Any] = {"filas": filas, "total": total}
    if errores:
        out["errores"] = errores
    return out


_ETIQUETA_TIPO_ALERTA = {
    "PARTO_ESPERADO": "🐄 Parto esperado",
    "ECOGRAFIA": "🩺 Ecografía (d35)",
    "PALPACION": "✋ Palpación (d60)",
    "SECADO": "🥛 Secado",
    "RECARGA_NITROGENO": "❄️ Recarga N₂",
    "CELO_PROGRAMADO": "🌡️ Inseminación programada",
    "INSUMINACION_PROGRAMADA": "🌡️ Inseminación programada",
    "RETIRO_LECHE": "⛔ Fin retiro leche",
    "RETIRO_CARNE": "⛔ Fin retiro carne",
    "DESTETE": "🍼 Destete",
}


def datos_agenda(db: Database, dias: int = 7) -> dict:
    """Agenda próxima (ventana de ``dias``): alertas PENDIENTES con fecha
    programada (partos, eco d35, palpación d60, secados, recargas de N₂) más
    los retiros sanitarios ACTIVOS — lo que el mayordomo debe saber HOY.
    """
    errores: dict[str, str] = {}
    hoy = date.today()
    hoy_iso = hoy.isoformat()
    limite = (hoy + timedelta(days=dias)).isoformat()
    eventos: list[dict] = []
    try:
        rows = db.query(
            """SELECT a.tipo_alerta, a.fecha_programada, a.descripcion, a.animal_id,
                      an.tag AS animal_tag
               FROM alertas a LEFT JOIN animales an ON an.id_animal = a.animal_id
               WHERE a.estado = 'PENDIENTE'
                 AND a.fecha_programada IS NOT NULL
                 AND a.fecha_programada >= ? AND a.fecha_programada <= ?
               ORDER BY a.fecha_programada, a.id LIMIT 80""",
            (hoy_iso, limite),
        )
        for r in _filas_dict(rows):
            fprog = str(r.get("fecha_programada") or "")[:10]
            try:
                faltan = (date.fromisoformat(fprog) - hoy).days if fprog else None
            except Exception:
                faltan = None
            eventos.append({
                "tipo": r.get("tipo_alerta"),
                "etiqueta": _ETIQUETA_TIPO_ALERTA.get(r.get("tipo_alerta"), r.get("tipo_alerta")),
                "fecha": fprog,
                "faltan_dias": faltan,
                "descripcion": r.get("descripcion"),
                "tag": r.get("animal_tag"),
            })
    except Exception as e:
        logger.error("seccion agenda_alertas fallo", exc_info=True)
        errores["alertas"] = str(e)
    retiros: list[dict] = []
    try:
        rows_ret = db.query(
            """SELECT a.tag, t.producto, t.fecha_fin_retiro_leche, t.fecha_fin_retiro_carne
               FROM tratamientos t JOIN animales a ON a.id_animal = t.animal_id
               WHERE a.estado = 'ACTIVO'
               AND ((t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
                OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?))
               ORDER BY t.fecha DESC LIMIT 20""",
            (hoy_iso, hoy_iso),
        )
        for r in _filas_dict(rows_ret):
            leche = r.get("fecha_fin_retiro_leche")
            carne = r.get("fecha_fin_retiro_carne")
            def _faltan(f: Optional[str]) -> Optional[int]:
                if not f:
                    return None
                try:
                    return (date.fromisoformat(str(f)[:10]) - hoy).days
                except Exception:
                    return None
            retiros.append({
                "tag": r.get("tag"),
                "producto": r.get("producto"),
                "fin_leche": str(leche)[:10] if leche else None,
                "fin_carne": str(carne)[:10] if carne else None,
                "fin_leche_dias": _faltan(leche),
                "fin_carne_dias": _faltan(carne),
            })
    except Exception as e:
        logger.error("seccion agenda_retiros fallo", exc_info=True)
        errores["retiros"] = str(e)
    out: dict[str, Any] = {
        "dias": dias,
        "eventos": eventos,
        "retiros": retiros,
    }
    if errores:
        out["errores"] = errores
    return out

