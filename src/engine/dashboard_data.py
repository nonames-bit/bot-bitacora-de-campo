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
import re
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
    try:
        cc_critica = _filas_dict(db.query(
            """SELECT a.tag, cc.fecha, cc.valor, cc.notas FROM condicion_corporal cc
               JOIN animales a ON a.id_animal = cc.animal_id
               WHERE a.estado = 'ACTIVO' AND cc.valor < 2.5
               ORDER BY cc.fecha DESC LIMIT 15"""
        ))
    except Exception as e:
        logger.error("seccion condicion_corporal_critica fallo", exc_info=True)
        errores["condicion_corporal_critica"] = str(e)
        cc_critica = []
    out: dict[str, Any] = {
        "fep_30d": fep,
        "celos_recientes": celos,
        "diagnosticos": diags,
        "eco_palp_pendientes": pendientes,
        "condicion_corporal_critica": cc_critica,
    }
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
    try:
        pluviometria = _filas_dict(db.query(
            """SELECT fecha, mm_lluvia, observaciones FROM pluviometria 
               ORDER BY fecha DESC LIMIT 15"""
        ))
    except Exception as e:
        logger.error("seccion pluviometria_reciente fallo", exc_info=True)
        errores["pluviometria_reciente"] = str(e)
        pluviometria = []
    try:
        aforos = _filas_dict(db.query(
            """SELECT p.nombre potrero, af.fecha, af.aforo_kg_m2, af.pct_ms FROM aforos_historico af
               JOIN potreros p ON p.id = af.potrero_id
               ORDER BY af.fecha DESC LIMIT 15"""
        ))
    except Exception as e:
        logger.error("seccion aforos_recientes fallo", exc_info=True)
        errores["aforos_recientes"] = str(e)
        aforos = []
    out: dict[str, Any] = {
        "potreros": potreros,
        "ndvi_reciente": ndvi,
        "pluviometria_reciente": pluviometria,
        "aforos_recientes": aforos,
    }
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
    raw_an = db.get_animal(aid)
    an = dict(raw_an) if raw_an else {}
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

    # --- Secciones enriquecidas para Ficha Zootécnica y Tarjeta QR ---
    hoy_date = date.today()
    hoy_iso = hoy_date.isoformat()

    # 1. Potrero actual
    potrero_nom = "Sin potrero asignado"
    if an.get("potrero_id"):
        try:
            p_row = db.query_one("SELECT id, nombre, codigo FROM potreros WHERE id = ?", (an["potrero_id"],))
            if p_row:
                potrero_nom = p_row["nombre"] or p_row["codigo"] or f"Potrero #{an['potrero_id']}"
        except Exception as e:
            logger.error("seccion potrero fallo", exc_info=True)
            errores["potrero"] = str(e)
    base["potrero"] = potrero_nom
    base["potrero_id"] = an.get("potrero_id")

    # 2. Genealogía y Trazabilidad (3G)
    def _info_ancestro(animal_id: Optional[int]) -> Optional[dict[str, Any]]:
        if not animal_id:
            return None
        try:
            row = db.query_one(
                "SELECT id_animal, tag, nombre, raza, sexo, padre_id, madre_id, estado "
                "FROM animales WHERE id_animal = ?", (animal_id,)
            )
            if not row:
                return None
            return {
                "id_animal": row["id_animal"],
                "tag": row["tag"],
                "nombre": row["nombre"],
                "raza": row["raza"] or "S/D",
                "sexo": row["sexo"] or "S/D",
                "padre_id": row["padre_id"],
                "madre_id": row["madre_id"],
                "estado": row["estado"],
            }
        except Exception:
            return None

    padre_info = _info_ancestro(an.get("padre_id"))
    madre_info = _info_ancestro(an.get("madre_id"))
    base["padre"] = padre_info
    base["madre"] = madre_info

    # Abuelos Paternos y Maternos
    p_abuelo_pat = _info_ancestro(padre_info["padre_id"]) if padre_info else None
    p_abuela_pat = _info_ancestro(padre_info["madre_id"]) if padre_info else None
    m_abuelo_mat = _info_ancestro(madre_info["padre_id"]) if madre_info else None
    m_abuela_mat = _info_ancestro(madre_info["madre_id"]) if madre_info else None

    # Bisabuelos (3G) si están registrados
    p_bisabuelo_pp = _info_ancestro(p_abuelo_pat["padre_id"]) if p_abuelo_pat else None
    p_bisabuela_pp = _info_ancestro(p_abuelo_pat["madre_id"]) if p_abuelo_pat else None
    p_bisabuelo_pm = _info_ancestro(p_abuela_pat["padre_id"]) if p_abuela_pat else None
    p_bisabuela_pm = _info_ancestro(p_abuela_pat["madre_id"]) if p_abuela_pat else None

    m_bisabuelo_mp = _info_ancestro(m_abuelo_mat["padre_id"]) if m_abuelo_mat else None
    m_bisabuela_mp = _info_ancestro(m_abuelo_mat["madre_id"]) if m_abuelo_mat else None
    m_bisabuelo_mm = _info_ancestro(m_abuela_mat["padre_id"]) if m_abuelo_mat else None
    m_bisabuela_mm = _info_ancestro(m_abuela_mat["madre_id"]) if m_abuela_mat else None

    # Crías registradas (tanto si es hembra - madre, como si es macho - padre)
    crias_list: list[dict[str, Any]] = []
    try:
        crias_rows = db.query(
            """
            SELECT a.id_animal, a.tag, a.nombre, a.sexo, a.raza, a.fecha_nacimiento, a.estado,
                   p.fecha AS fecha_parto, p.peso_nacimiento, p.estado_cria
            FROM animales a
            LEFT JOIN partos p ON p.id_cria = a.id_animal
            WHERE a.madre_id = ? OR a.padre_id = ?
               OR (p.vaca_id = ? AND a.id_animal IS NOT NULL)
            GROUP BY a.id_animal
            ORDER BY COALESCE(p.fecha, a.fecha_nacimiento) DESC, a.id_animal DESC
            """,
            (aid, aid, aid),
        )
        crias_list = _filas_dict(crias_rows)

        # Partos sin cría registrada formalmente en animales
        partos_sin_cria = db.query(
            """
            SELECT NULL AS id_animal, 'Sin arete' AS tag, NULL AS nombre, sexo_cria AS sexo,
                   NULL AS raza, fecha AS fecha_nacimiento, 'ACTIVO' AS estado,
                   fecha AS fecha_parto, peso_nacimiento, estado_cria
            FROM partos
            WHERE vaca_id = ? AND id_cria IS NULL
            ORDER BY fecha DESC
            """,
            (aid,),
        )
        for pc in partos_sin_cria:
            crias_list.append(dict(pc))
    except Exception as e:
        logger.error("seccion crias genealogia fallo", exc_info=True)
        errores["crias_genealogia"] = str(e)

    base["crias"] = crias_list

    # Consanguinidad en 3G
    consang_info: dict[str, Any] = {
        "evaluable": False,
        "consanguineo": False,
        "detalle": "No evaluable (registro incompleto de padre o madre)",
        "icono": "circleEmpty",
        "clase": "gris",
    }
    try:
        if an.get("madre_id") and an.get("padre_id"):
            es_c = db.verificar_consanguinidad(an["madre_id"], an["padre_id"])
            consang_info = {
                "evaluable": True,
                "consanguineo": es_c,
                "detalle": "⚠️ Cruzamiento consanguíneo detectado (padres emparentados en 3G)" if es_c else "✅ 0.0% (Líneas independientes en 3 generaciones)",
                "icono": "alert" if es_c else "shieldCheck",
                "clase": "rojo" if es_c else "verde",
            }
    except Exception:
        logger.error("seccion consanguinidad fallo", exc_info=True)

    # Texto ASCII del árbol (idéntico a Telegram)
    try:
        from ..server.formatters import formatear_genealogia_animal_tab
        texto_arbol = formatear_genealogia_animal_tab(db, an["tag"])
    except Exception:
        try:
            from src.server.formatters import formatear_genealogia_animal_tab
            texto_arbol = formatear_genealogia_animal_tab(db, an["tag"])
        except Exception:
            texto_arbol = ""

    base["abuelo_pat"] = p_abuelo_pat
    base["abuela_pat"] = p_abuela_pat
    base["abuelo_mat"] = m_abuelo_mat
    base["abuela_mat"] = m_abuela_mat
    base["consanguinidad"] = consang_info

    base["genealogia_3g"] = {
        "animal": {"id_animal": an.get("id_animal"), "tag": an.get("tag"), "nombre": an.get("nombre"), "raza": an.get("raza"), "sexo": an.get("sexo")},
        "padre": padre_info,
        "madre": madre_info,
        "abuelo_pat": p_abuelo_pat,
        "abuela_pat": p_abuela_pat,
        "abuelo_mat": m_abuelo_mat,
        "abuela_mat": m_abuela_mat,
        "bisabuelos": {
            "pat_pat_p": p_bisabuelo_pp,
            "pat_pat_m": p_bisabuela_pp,
            "pat_mat_p": p_bisabuelo_pm,
            "pat_mat_m": p_bisabuela_pm,
            "mat_pat_p": m_bisabuelo_mp,
            "mat_pat_m": m_bisabuela_mp,
            "mat_mat_p": m_bisabuelo_mm,
            "mat_mat_m": m_bisabuela_mm,
        },
        "consanguinidad": consang_info,
        "crias": crias_list,
        "texto_arbol": texto_arbol,
    }

    # 3. Edad zootécnica y días
    f_nac = to_date_safe(an.get("fecha_nacimiento"))
    edad_str = "S/D"
    edad_dias = None
    if f_nac:
        edad_dias = max(0, (hoy_date - f_nac).days)
        try:
            from .query.helpers import formatear_edad_zootecnica
            edad_str = formatear_edad_zootecnica(f_nac, hoy_date)
        except Exception:
            edad_str = f"{edad_dias} días"
    base["edad_str"] = edad_str
    base["edad_dias"] = edad_dias

    # 4. Categoría Zootécnica SG
    categoria_sg = "Sin clasificar"
    s_raw = str(an.get("sexo") or "").strip().lower()
    es_macho = bool(s_raw.startswith("m") or s_raw in ("macho", "toro", "ternero", "novillo", "buey"))
    if es_hembra:
        if edad_dias is not None:
            if edad_dias < 365:
                categoria_sg = "Hembras <1 año (Ternera)"
            elif edad_dias < 730:
                categoria_sg = "Hembras 1-2 años (Novilla levante)"
            elif edad_dias < 1460:
                categoria_sg = "Hembras 2-4 años (Novilla vientre)"
            elif edad_dias <= 2921:
                categoria_sg = "Hembras 4-8 años (Vaca adulta)"
            elif edad_dias <= 3651:
                categoria_sg = "Hembras 8-10 años"
            else:
                categoria_sg = "Hembras >10 años"
        else:
            categoria_sg = "Hembra adulta"
    elif es_macho:
        txt_info = f"{an.get('nombre') or ''} {an.get('notas') or ''} {an.get('tag') or ''}".upper()
        if re.search(r"\b(?:TORO|REPRODUCTOR|PADRON|SEMEN|PAJILLA)\b", txt_info) or (edad_dias is not None and edad_dias >= 913):
            categoria_sg = "Reproductor (Toro)"
        elif edad_dias is not None:
            if edad_dias < 365:
                categoria_sg = "Machos <1 año (Ternero)"
            elif edad_dias < 730:
                categoria_sg = "Machos 1-2 años (Novillo)"
            else:
                categoria_sg = "Machos >2 años"
        else:
            categoria_sg = "Macho"
    base["categoria_sg"] = categoria_sg

    # 5. Desempeño ponderal
    ultimo_peso = None
    if base.get("pesajes") and len(base["pesajes"]) > 0:
        p0 = base["pesajes"][0]
        ultimo_peso = {
            "peso_kg": p0.get("peso_kg"),
            "fecha": p0.get("fecha"),
            "gmd": p0.get("gmd_calculada"),
        }
    base["ultimo_peso"] = ultimo_peso

    peso_nac = None
    try:
        p_cria = db.query_one(
            "SELECT peso_nacimiento FROM partos WHERE id_cria = ? AND peso_nacimiento IS NOT NULL LIMIT 1",
            (aid,)
        )
        if p_cria and p_cria["peso_nacimiento"] is not None:
            peso_nac = float(p_cria["peso_nacimiento"])
    except Exception:
        pass
    base["peso_nacimiento"] = peso_nac

    # 6. Retiros sanitarios activos
    retiros_activos = []
    try:
        ret_rows = db.query(
            """SELECT producto, dosis, fecha_fin_retiro_leche, fecha_fin_retiro_carne
               FROM tratamientos
               WHERE animal_id = ?
                 AND ((fecha_fin_retiro_leche IS NOT NULL AND fecha_fin_retiro_leche >= ?)
                   OR (fecha_fin_retiro_carne IS NOT NULL AND fecha_fin_retiro_carne >= ?))
               ORDER BY fecha DESC""", (aid, hoy_iso, hoy_iso)
        )
        retiros_activos = _filas_dict(ret_rows)
    except Exception:
        logger.error("seccion retiros_activos fallo", exc_info=True)
    base["retiros_activos"] = retiros_activos
    base["en_retiro"] = len(retiros_activos) > 0

    # 7. Resumen reproductivo
    estado_repro = "Sin datos reproductivos"
    dias_abiertos = None
    if es_hembra:
        ult_diag = base["diagnosticos"][0] if base.get("diagnosticos") else None
        ult_serv = base.get("ultimo_servicio")
        ult_parto = base.get("ultimo_parto")

        f_parto_d = to_date_safe(ult_parto["fecha"]) if ult_parto and ult_parto.get("fecha") else None
        if f_parto_d:
            dias_abiertos = max(0, (hoy_date - f_parto_d).days)

        if ult_diag and str(ult_diag.get("resultado") or "").upper() in ("PREÑADA", "PREGNANT", "POSITIVO"):
            fep_str = f" (FEP: {str(ult_serv['fep_calculada'])[:10]})" if ult_serv and ult_serv.get("fep_calculada") else ""
            estado_repro = f"🟢 Gestante / Preñada{fep_str}"
        elif ult_serv and ult_serv.get("fep_calculada"):
            f_serv_d = to_date_safe(ult_serv.get("fecha"))
            if not f_parto_d or (f_serv_d and f_serv_d >= f_parto_d):
                toro_str = f" · {ult_serv.get('toro_pajilla') or ''}".strip()
                estado_repro = f"🟡 Inseminada / Servida{toro_str} (FEP: {str(ult_serv['fep_calculada'])[:10]})"
            elif f_parto_d:
                estado_repro = f"⚪ Abierta / Vacía ({dias_abiertos} días post-parto)"
        elif f_parto_d:
            estado_repro = f"⚪ Abierta / Vacía ({dias_abiertos} días post-parto)"
        elif edad_dias and edad_dias >= 730:
            estado_repro = "⚪ Novilla de vientre (apta para servicio)"
        elif edad_dias and edad_dias < 730:
            estado_repro = "⚪ Ternera / Novilla de levante"
        else:
            estado_repro = "Hembra activa"
    elif es_macho:
        estado_repro = "Macho reproductor" if "Reproductor" in categoria_sg else "Macho activo"
    base["estado_repro"] = estado_repro
    base["dias_abiertos"] = dias_abiertos

    # 8. Traslados de potrero recientes
    try:
        t_rows = db.query(
            """SELECT t.fecha, t.motivo, po.nombre AS origen, pd.nombre AS destino
               FROM traslados t
               LEFT JOIN potreros po ON po.id = t.potrero_origen
               LEFT JOIN potreros pd ON pd.id = t.potrero_destino
               WHERE t.animal_id = ?
               ORDER BY t.fecha DESC, t.id DESC LIMIT 4""", (aid,)
        )
        base["traslados"] = _filas_dict(t_rows)
    except Exception:
        logger.error("seccion traslados fallo", exc_info=True)
        base["traslados"] = []

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
        # Selector de potreros: con búsqueda vacía se devuelve la lista
        # completa (el input "Potrero" del filtro superior debe poder elegir
        # cualquier potrero sin teclear). Solo potreros, nunca animales.
        try:
            filas_p = db.query(
                "SELECT nombre, codigo FROM potreros WHERE geom_wkt_4326 IS NOT NULL "
                "ORDER BY nombre LIMIT 200"
            )
            out["potreros"] = _filas_dict(filas_p)
        except Exception as e:
            logger.error("seccion potreros_lista_completa fallo", exc_info=True)
            errores["potreros"] = str(e)
        if errores:
            out["errores"] = errores
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
               WHERE geom_wkt_4326 IS NOT NULL
                 AND (UPPER(COALESCE(nombre,'')) LIKE UPPER(?)
                  OR UPPER(COALESCE(codigo,'')) LIKE UPPER(?))
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


def _piramide_desde_brackets(brackets: dict) -> list[dict]:
    """Pirámide hembras/machos en 3 bandas comparables (<1, 1-2, 2+).

    Mismo origen que ``calcular_brackets_inventario_sg``: las hembras "2+"
    suman sus brackets 2-4/4-8/8-10/>10 y los machos "2+" suman >2 años más
    reproductores (SG separa reproductores solo en machos).
    """
    if not brackets:
        return []
    hb = brackets.get("h_brackets", {})
    mb = brackets.get("m_brackets", {})

    def _s(d, *k):
        return int(sum(int(d.get(x, 0)) for x in k))

    return [
        {"banda": "< 1 año", "hembras": _s(hb, "menor_1"), "machos": _s(mb, "menor_1")},
        {"banda": "1 - 2 años", "hembras": _s(hb, "1_2"), "machos": _s(mb, "1_2")},
        {"banda": "2+ años", "hembras": _s(hb, "2_4", "4_8", "8_10", "mayor_10"),
         "machos": _s(mb, "mayor_2", "reproductor")},
    ]


def _edad_promedio_anios(db: Database) -> Optional[float]:
    """Edad promedio (años) de animales ACTIVOS con fecha de nacimiento."""
    try:
        row = db.query_one(
            """SELECT AVG(julianday('now') - julianday(fecha_nacimiento)) AS dias
               FROM animales WHERE estado='ACTIVO' AND fecha_nacimiento IS NOT NULL"""
        )
        if row and row["dias"] is not None:
            return round(float(row["dias"]) / 365.25, 2)
    except Exception:
        logger.error("seccion edad_promedio fallo", exc_info=True)
    return None


def _gmd_recientes(db: Database, limite: int = 15) -> list[dict]:
    """Últimos pesajes con GMD de animales ACTIVOS (para la vista unificada)."""
    try:
        return _filas_dict(db.query(
            """SELECT a.tag, p.fecha, p.peso_kg, p.gmd_calculada FROM pesajes p
               JOIN animales a ON a.id_animal = p.animal_id
               WHERE a.estado = 'ACTIVO' AND p.gmd_calculada IS NOT NULL
               ORDER BY p.fecha DESC LIMIT ?""",
            (limite,),
        ))
    except Exception:
        logger.error("seccion gmd_reciente fallo", exc_info=True)
        return []


def _por_potrero(db: Database) -> list[dict]:
    """Cabezas ACTIVAS agrupadas por potrero (mismo criterio que el Tablero:
    incluye "Sin potrero" y potreros legacy si de verdad tienen animales
    activos ahí -- es el estado real de la base, no un listado de opciones)."""
    try:
        return _filas_dict(db.query(
            "SELECT COALESCE(p.nombre, p.codigo, 'Sin potrero') potrero, COUNT(*) n "
            "FROM animales a LEFT JOIN potreros p ON p.id = a.potrero_id "
            "WHERE a.estado = 'ACTIVO' GROUP BY potrero ORDER BY n DESC LIMIT 20"
        ))
    except Exception:
        logger.error("seccion por_potrero fallo", exc_info=True)
        return []


def datos_inventario(db: Database) -> dict:
    """Resumen unificado Inventario + Población (vista única del hato).

    Reutiliza ``engine.query.helpers.calcular_brackets_inventario_sg`` (la
    misma función que usa el bot de Telegram para /animales y /status) para
    que la PWA y Telegram nunca muestren brackets distintos. Incluye la
    pirámide etaria, la edad promedio, los últimos pesajes con GMD y la
    distribución por potrero para mostrar todo el hato en una sola vista sin
    repetir información.
    """
    errores: dict[str, str] = {}
    try:
        from .query.helpers import calcular_brackets_inventario_sg
        brackets = calcular_brackets_inventario_sg(db)
    except Exception as e:
        logger.error("seccion inventario_brackets fallo", exc_info=True)
        errores["brackets"] = str(e)
        brackets = {}
    gmd = _gmd_recientes(db)
    out: dict[str, Any] = {
        "filas": _brackets_a_filas(brackets) if brackets else [],
        "total_activos": brackets.get("total_activos", 0) if brackets else 0,
        "total_hembras": brackets.get("total_hembras", 0) if brackets else 0,
        "total_machos": brackets.get("total_machos", 0) if brackets else 0,
        "total_sin_sexo": brackets.get("total_sin_sexo", 0) if brackets else 0,
        "terneros_menor_12m": brackets.get("terneros_menor_12m", 0) if brackets else 0,
        "piramide": _piramide_desde_brackets(brackets),
        "edad_promedio": _edad_promedio_anios(db),
        "gmd_reciente": gmd,
        "por_potrero": _por_potrero(db),
    }
    if errores:
        out["errores"] = errores
    return out


def datos_poblacion(db: Database) -> dict:
    """Composición etaria del hato (endpoint compatible; vista unificada usa
    ``datos_inventario`` que ahora incluye pirámide/edad/GMD)."""
    errores: dict[str, str] = {}
    try:
        from .query.helpers import calcular_brackets_inventario_sg
        brackets = calcular_brackets_inventario_sg(db)
    except Exception as e:
        logger.error("seccion poblacion_brackets fallo", exc_info=True)
        errores["brackets"] = str(e)
        brackets = {}
    gmd = _gmd_recientes(db)
    out: dict[str, Any] = {
        "filas": _brackets_a_filas(brackets) if brackets else [],
        "total_activos": brackets.get("total_activos", 0) if brackets else 0,
        "total_hembras": brackets.get("total_hembras", 0) if brackets else 0,
        "total_machos": brackets.get("total_machos", 0) if brackets else 0,
        "edad_promedio": _edad_promedio_anios(db),
        "gmd_reciente": gmd,
        "piramide": _piramide_desde_brackets(brackets),
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
    try:
        pajuelas = _filas_dict(db.query(
            """SELECT codigo_toro, raza, procedencia, canastilla, cantidad FROM pajuelas_inventario
               ORDER BY cantidad DESC LIMIT 20"""
        ))
    except Exception as e:
        logger.error("seccion pajuelas_inventario fallo", exc_info=True)
        errores["pajuelas_inventario"] = str(e)
        pajuelas = []
    try:
        termos = _filas_dict(db.query(
            """SELECT fecha_recarga, proxima_recarga, dias_intervalo FROM termo_nitrogeno
               ORDER BY fecha_recarga DESC LIMIT 10"""
        ))
    except Exception as e:
        logger.error("seccion termo_nitrogeno fallo", exc_info=True)
        errores["termo_nitrogeno"] = str(e)
        termos = []
    out: dict[str, Any] = {
        "filas": filas,
        "total": total,
        "pajuelas_inventario": pajuelas,
        "termo_nitrogeno": termos,
    }
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


def datos_badges(db: Database, dias: int = 7) -> dict:
    """Contadores mínimos para los badges de la navegación PWA.

    Un único endpoint liviano (una llamada por polling en vez de 3) con los
    totales que el mayordomo debe ver sin abrir cada vista:
    - agenda:  alertas PENDIENTES con fecha en [hoy, hoy+dias] + retiros activos
    - repro:   vacas con FEP ≤30d + eco/palpaciones pendientes
    - sanidad: animales en retiro activo (leche/carne)

    Todas las consultas restringen a animales ACTIVOS (regla AGENTS.md).
    """
    errores: dict[str, str] = {}
    hoy = date.today()
    hoy_iso = hoy.isoformat()
    lim = (hoy + timedelta(days=dias)).isoformat()
    lim30 = (hoy + timedelta(days=30)).isoformat()

    agenda = repro = sanidad = 0

    def _cnt_retiros_activos() -> int:
        r = db.query_one(
            """SELECT COUNT(DISTINCT t.animal_id) n FROM tratamientos t
               JOIN animales a ON a.id_animal = t.animal_id
               WHERE a.estado = 'ACTIVO'
               AND ((t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
                OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?))""",
            (hoy_iso, hoy_iso),
        )
        return int(r["n"]) if r else 0

    try:
        r = db.query_one(
            "SELECT COUNT(*) n FROM alertas WHERE estado='PENDIENTE' "
            "AND fecha_programada IS NOT NULL AND fecha_programada >= ? AND fecha_programada <= ?",
            (hoy_iso, lim),
        )
        alertas = int(r["n"]) if r else 0
        retiros = _cnt_retiros_activos()
        agenda = alertas + retiros
    except Exception as e:
        logger.error("seccion badges_agenda fallo", exc_info=True)
        errores["agenda"] = str(e)

    try:
        retiros = _cnt_retiros_activos()
        sanidad = retiros
    except Exception as e:
        logger.error("seccion badges_sanidad fallo", exc_info=True)
        errores["sanidad"] = str(e)

    try:
        r1 = db.query_one(
            """SELECT COUNT(*) n FROM servicios s JOIN animales a ON a.id_animal = s.vaca_id
               WHERE a.estado='ACTIVO' AND s.fep_calculada IS NOT NULL
               AND s.fep_calculada >= ? AND s.fep_calculada <= ?""",
            (hoy_iso, lim30),
        )
        r2 = db.query_one(
            "SELECT COUNT(*) n FROM alertas WHERE estado='PENDIENTE' "
            "AND tipo_alerta IN ('ECOGRAFIA','PALPACION') AND fecha_programada >= ? AND fecha_programada <= ?",
            (hoy_iso, lim),
        )
        repro = int(r1["n"]) if r1 else 0
        repro += int(r2["n"]) if r2 else 0
    except Exception as e:
        logger.error("seccion badges_repro fallo", exc_info=True)
        errores["repro"] = str(e)

    out: dict[str, Any] = {"agenda": agenda, "repro": repro, "sanidad": sanidad, "dias": dias}
    if errores:
        out["errores"] = errores
    return out

