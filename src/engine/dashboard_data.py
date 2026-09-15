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

    try:
        query_eventos = """
            SELECT * FROM (
                SELECT COALESCE(p.tipo_evento, 'PARTO') AS tipo,
                       p.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       COALESCE(c.tag, '') AS detalle_tag,
                       'Cría' AS detalle_label,
                       CASE COALESCE(p.tipo_evento, 'PARTO')
                           WHEN 'GEMELAR' THEN 'Parto gemelar'
                           WHEN 'ABORTO' THEN 'Aborto registrado'
                           WHEN 'REABSORCION' THEN 'Reabsorción embrionaria'
                           WHEN 'MOMIFICACION' THEN 'Momificación fetal'
                           WHEN 'MACERACION' THEN 'Maceración fetal'
                           WHEN 'MUERTE_FETAL' THEN 'Muerte fetal'
                           WHEN 'PARTO' THEN CASE WHEN p.sexo_cria IS NOT NULL THEN 'Cría ' || p.sexo_cria ELSE 'Parto registrado' END
                           ELSE 'Parto registrado'
                       END ||
                       CASE WHEN p.peso_nacimiento IS NOT NULL THEN ' (' || ROUND(p.peso_nacimiento, 1) || ' kg)' ELSE '' END AS descripcion,
                       COALESCE(p.notas, p.estado_cria, '') AS notas, p.id AS id
                FROM partos p
                JOIN animales a ON a.id_animal = p.vaca_id
                LEFT JOIN animales c ON c.id_animal = p.id_cria

                UNION ALL

                SELECT 'MUERTE' AS tipo, m.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       '' AS detalle_tag,
                       '' AS detalle_label,
                       COALESCE(m.causa_presunta, 'Muerte registrada') AS descripcion,
                       COALESCE(m.notas, '') AS notas, m.id AS id
                FROM muertes m
                JOIN animales a ON a.id_animal = m.animal_id

                UNION ALL

                SELECT COALESCE(mo.tipo_movimiento, 'VENTA') AS tipo, mo.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       CASE
                           -- Si la cría se vendió en la misma fecha que su madre:
                           WHEN a.madre_id IS NOT NULL AND m_parent.tag IS NOT NULL AND EXISTS (
                               SELECT 1 FROM movimientos m_madre
                               WHERE m_madre.animal_id = a.madre_id
                                 AND m_madre.fecha = mo.fecha
                                 AND UPPER(m_madre.tipo_movimiento) = 'VENTA'
                           ) THEN m_parent.tag
                           -- Si la vaca se vendió con cría en la misma fecha (o cría lactante reciente):
                           ELSE COALESCE(
                               (SELECT c.tag FROM animales c
                                JOIN movimientos mc ON mc.animal_id = c.id_animal
                                WHERE c.madre_id = a.id_animal
                                  AND mc.fecha = mo.fecha
                                  AND UPPER(mc.tipo_movimiento) = 'VENTA'
                                LIMIT 1),
                               (SELECT c.tag FROM partos p
                                JOIN animales c ON c.id_animal = p.id_cria
                                WHERE p.vaca_id = a.id_animal
                                  AND (julianday(mo.fecha) - julianday(p.fecha)) BETWEEN 0 AND 365
                                ORDER BY p.fecha DESC LIMIT 1),
                               ''
                           )
                       END AS detalle_tag,
                       CASE
                           WHEN a.madre_id IS NOT NULL AND m_parent.tag IS NOT NULL AND EXISTS (
                               SELECT 1 FROM movimientos m_madre
                               WHERE m_madre.animal_id = a.madre_id
                                 AND m_madre.fecha = mo.fecha
                                 AND UPPER(m_madre.tipo_movimiento) = 'VENTA'
                           ) THEN 'Madre'
                           WHEN (
                               EXISTS (
                                   SELECT 1 FROM animales c
                                   JOIN movimientos mc ON mc.animal_id = c.id_animal
                                   WHERE c.madre_id = a.id_animal
                                     AND mc.fecha = mo.fecha
                                     AND UPPER(mc.tipo_movimiento) = 'VENTA'
                               )
                               OR EXISTS (
                                   SELECT 1 FROM partos p
                                   JOIN animales c ON c.id_animal = p.id_cria
                                   WHERE p.vaca_id = a.id_animal
                                     AND (julianday(mo.fecha) - julianday(p.fecha)) BETWEEN 0 AND 365
                               )
                           ) THEN 'Cría'
                           ELSE ''
                       END AS detalle_label,
                       CASE
                           WHEN UPPER(COALESCE(mo.tipo_movimiento, 'VENTA')) = 'VENTA' THEN
                               CASE
                                   WHEN a.madre_id IS NOT NULL AND m_parent.tag IS NOT NULL AND EXISTS (
                                       SELECT 1 FROM movimientos m_madre
                                       WHERE m_madre.animal_id = a.madre_id
                                         AND m_madre.fecha = mo.fecha
                                         AND UPPER(m_madre.tipo_movimiento) = 'VENTA'
                                   ) THEN 'Venta (cría de ' || m_parent.tag || ')'
                                   WHEN EXISTS (
                                       SELECT 1 FROM animales c
                                       JOIN movimientos mc ON mc.animal_id = c.id_animal
                                       WHERE c.madre_id = a.id_animal
                                         AND mc.fecha = mo.fecha
                                         AND UPPER(mc.tipo_movimiento) = 'VENTA'
                                   ) THEN 'Venta con cría'
                                   WHEN mo.procedencia_destino IS NOT NULL AND TRIM(mo.procedencia_destino) != '' THEN 'Venta a ' || TRIM(mo.procedencia_destino)
                                   ELSE 'Venta registrada'
                               END
                           ELSE COALESCE(mo.procedencia_destino, 'Movimiento registrado')
                       END ||
                       CASE WHEN mo.precio IS NOT NULL AND mo.precio > 0 THEN ' · $' || ROUND(mo.precio, 0) ELSE '' END AS descripcion,
                       COALESCE(mo.notas, '') AS notas, mo.id AS id
                FROM movimientos mo
                JOIN animales a ON a.id_animal = mo.animal_id
                LEFT JOIN animales m_parent ON m_parent.id_animal = a.madre_id

                UNION ALL

                SELECT 'TRASLADO' AS tipo, t.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       '' AS detalle_tag,
                       '' AS detalle_label,
                       COALESCE(po.nombre, po.codigo, 'Origen') || ' ➔ ' || COALESCE(pd.nombre, pd.codigo, 'Destino') AS descripcion,
                       COALESCE(t.motivo, '') AS notas, t.id AS id
                FROM traslados t
                JOIN animales a ON a.id_animal = t.animal_id
                LEFT JOIN potreros po ON po.id = t.potrero_origen
                LEFT JOIN potreros pd ON pd.id = t.potrero_destino

                UNION ALL

                SELECT 'DESTETE' AS tipo, de.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       '' AS detalle_tag,
                       '' AS detalle_label,
                       'Destete' ||
                       CASE WHEN de.peso_kg IS NOT NULL THEN ' · ' || de.peso_kg || ' kg' ELSE '' END ||
                       CASE WHEN pd_cria.nombre IS NOT NULL OR pd_cria.codigo IS NOT NULL
                            THEN ' ➔ ' || COALESCE(pd_cria.nombre, pd_cria.codigo) ELSE '' END AS descripcion,
                       COALESCE(de.notas, '') AS notas, de.id AS id
                FROM destetes de
                JOIN animales a ON a.id_animal = de.animal_id
                LEFT JOIN potreros pd_cria ON pd_cria.id = de.potrero_cria

                UNION ALL

                SELECT 'SECADO' AS tipo, se.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       '' AS detalle_tag,
                       '' AS detalle_label,
                       COALESCE(se.motivo, 'Secado registrado') ||
                       CASE WHEN pd_seca.nombre IS NOT NULL OR pd_seca.codigo IS NOT NULL
                            THEN ' ➔ ' || COALESCE(pd_seca.nombre, pd_seca.codigo) ELSE '' END AS descripcion,
                       COALESCE(se.notas, '') AS notas, se.id AS id
                FROM secados se
                JOIN animales a ON a.id_animal = se.animal_id
                LEFT JOIN potreros pd_seca ON pd_seca.id = se.potrero_destino

                UNION ALL

                SELECT 'PESAJE' AS tipo, pe.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       '' AS detalle_tag,
                       '' AS detalle_label,
                       pe.peso_kg || ' kg' ||
                       CASE WHEN pe.gmd_calculada IS NOT NULL AND pe.gmd_calculada > 0
                            THEN ' (+' || ROUND(pe.gmd_calculada * 1000, 0) || ' g/d)'
                            ELSE '' END AS descripcion,
                       COALESCE(pe.evento, '') AS notas, pe.id AS id
                FROM pesajes pe
                JOIN animales a ON a.id_animal = pe.animal_id

                UNION ALL

                SELECT 'TRATAMIENTO' AS tipo, tr.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       '' AS detalle_tag,
                       '' AS detalle_label,
                       tr.producto || CASE WHEN tr.dosis IS NOT NULL THEN ' ' || tr.dosis ELSE '' END AS descripcion,
                       COALESCE(tr.diagnostico, '') AS notas, tr.id AS id
                FROM tratamientos tr
                JOIN animales a ON a.id_animal = tr.animal_id

                UNION ALL

                SELECT 'SERVICIO' AS tipo, s.fecha AS fecha, a.tag AS tag, a.nombre AS nombre,
                       '' AS detalle_tag,
                       '' AS detalle_label,
                       COALESCE(s.tipo_servicio, 'Servicio/IA') ||
                       CASE WHEN s.toro_pajilla IS NOT NULL THEN ' · ' || s.toro_pajilla ELSE '' END AS descripcion,
                       COALESCE(s.estado, '') AS notas, s.id AS id
                FROM servicios s
                JOIN animales a ON a.id_animal = s.vaca_id
            )
            WHERE fecha IS NOT NULL AND TRIM(fecha) != ''
            ORDER BY fecha DESC, id DESC
            LIMIT 35
        """
        eventos_recientes = _filas_dict(db.query(query_eventos))
    except Exception as e:
        logger.error("seccion eventos_recientes fallo", exc_info=True)
        errores["eventos_recientes"] = str(e)
        eventos_recientes = []

    try:
        from .pronostico import obtener_pronostico_para_despacho
        _pron_hoy = obtener_pronostico_para_despacho(db)
        _dia_hoy = _pron_hoy["dias"][0] if _pron_hoy and _pron_hoy.get("dias") else None
        clima_hoy = None
        if _dia_hoy:
            _f = _dia_hoy.get("fecha")
            clima_hoy = {
                "fecha": _f.isoformat() if hasattr(_f, "isoformat") else str(_f),
                "temp_max_c": _dia_hoy.get("temp_max_c"),
                "temp_min_c": _dia_hoy.get("temp_min_c"),
                "lluvia_mm": _dia_hoy.get("lluvia_mm"),
                "prob_lluvia_pct": _dia_hoy.get("prob_lluvia_pct"),
            }
    except Exception as e:
        logger.error("seccion clima_hoy fallo", exc_info=True)
        errores["clima_hoy"] = str(e)
        clima_hoy = None

    try:
        precio_hoy = db.precio_referencia_hoy(plaza="BOGOTA", producto="MACHO_GORDO")
    except Exception as e:
        logger.error("seccion precio_hoy fallo", exc_info=True)
        errores["precio_hoy"] = str(e)
        precio_hoy = None

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
        "eventos_recientes": eventos_recientes,
        "clima_hoy": clima_hoy,
        "precio_hoy": precio_hoy,
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
    try:
        conc = db.kpis_reproductivos_concepcion()
    except Exception as e:
        logger.error("seccion kpis_concepcion fallo", exc_info=True)
        errores["kpis_concepcion"] = str(e)
        conc = None
    try:
        dias_ab = db.dias_abiertos_promedio_hato(hoy)
    except Exception as e:
        logger.error("seccion dias_abiertos fallo", exc_info=True)
        errores["dias_abiertos"] = str(e)
        dias_ab = None
    try:
        iep = db.iep_promedio_hato()
    except Exception as e:
        logger.error("seccion iep fallo", exc_info=True)
        errores["iep"] = str(e)
        iep = None
    try:
        edad_1p = db.edad_primer_parto_promedio_meses()
    except Exception as e:
        logger.error("seccion edad_1er_parto fallo", exc_info=True)
        errores["edad_1er_parto"] = str(e)
        edad_1p = None

    kpis = {
        "iep_promedio_dias": iep["iep_promedio_dias"] if iep else None,
        "dias_abiertos_promedio": dias_ab["dias_abiertos_promedio"] if dias_ab else None,
        "dias_abiertos_n": dias_ab["n"] if dias_ab else 0,
        "servicios_por_concepcion": conc["servicios_por_concepcion"] if conc else None,
        "tasa_concepcion": conc["tasa_concepcion"] if conc else None,
        "edad_primer_parto_meses": edad_1p["edad_primer_parto_meses"] if edad_1p else None,
    }

    out: dict[str, Any] = {
        "fep_30d": fep,
        "celos_recientes": celos,
        "diagnosticos": diags,
        "eco_palp_pendientes": pendientes,
        "condicion_corporal_critica": cc_critica,
        "kpis": kpis,
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
            """SELECT a.tag, a.nombre, t.producto, t.principio_activo, t.dosis, t.via,
                      t.fecha, t.dias_retiro_leche, t.dias_retiro_carne,
                      t.fecha_fin_retiro_leche, t.fecha_fin_retiro_carne FROM tratamientos t
                JOIN animales a ON a.id_animal = t.animal_id
                WHERE a.estado = 'ACTIVO'
                AND ((t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
                 OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?))
                ORDER BY t.fecha DESC LIMIT 30""", (hoy_iso, hoy_iso)))
        for r in retiros:
            for k in ("fecha_fin_retiro_leche", "fecha_fin_retiro_carne"):
                if r.get(k):
                    try:
                        r[k + "_dias"] = (date.fromisoformat(str(r[k])[:10]) - hoy).days
                    except Exception:
                        r[k + "_dias"] = None
            # Estado operativo del retiro con días restantes (skill @plan-sanitario:
            # Fin = última dosis + días de retiro; se muestra la cuenta regresiva).
            d_leche = r.get("fecha_fin_retiro_leche_dias")
            d_carne = r.get("fecha_fin_retiro_carne_dias")
            dias = [d for d in (d_leche, d_carne) if isinstance(d, int)]
            r["dias_restantes"] = max(dias) if dias else None
            r["estado"] = "EN_RETIRO"
    except Exception as e:
        logger.error("seccion retiros fallo", exc_info=True)
        errores["retiros"] = str(e)
        retiros = []
    try:
        ultimos = _filas_dict(db.query(
            """SELECT a.tag, t.producto, t.principio_activo, t.dosis, t.via, t.fecha,
                      t.dias_retiro_leche, t.dias_retiro_carne FROM tratamientos t
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
        p["total_animales"] = 0

    hoy_date = date.today()
    from ..utils import to_date

    # Conteo dinámico de animales activos y fecha de ingreso más reciente por potrero
    info_por_pot: dict[int, dict] = {}
    try:
        sql_anim = """
            WITH ult_traslado AS (
                SELECT animal_id, potrero_destino, fecha,
                       ROW_NUMBER() OVER (PARTITION BY animal_id ORDER BY fecha DESC, id DESC) as rn
                FROM traslados
            )
            SELECT COALESCE(ut.potrero_destino, a.potrero_id) as pot_id,
                   COUNT(*) as total_animales,
                   MAX(ut.fecha) as ult_fecha_ingreso
            FROM animales a
            LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1
            WHERE a.estado = 'ACTIVO' AND COALESCE(ut.potrero_destino, a.potrero_id) IS NOT NULL
            GROUP BY COALESCE(ut.potrero_destino, a.potrero_id)
        """
        for f in db.query(sql_anim):
            info_por_pot[f["pot_id"]] = dict(f)
    except Exception:
        logger.error("error calculando animales por potrero en pasturas", exc_info=True)

    # Última salida registrada para potreros en reposo
    info_salida: dict[int, str] = {}
    try:
        sql_sal = """
            SELECT potrero_origen, MAX(fecha) as ult_fecha_salida
            FROM traslados
            WHERE potrero_origen IS NOT NULL
            GROUP BY potrero_origen
        """
        for f in db.query(sql_sal):
            if f["potrero_origen"] is not None and f["ult_fecha_salida"]:
                info_salida[f["potrero_origen"]] = f["ult_fecha_salida"]
    except Exception:
        logger.error("error calculando fechas de salida en pasturas", exc_info=True)

    for p in potreros:
        pid = p["id"]
        anim = info_por_pot.get(pid)
        n_anim = anim["total_animales"] if anim else 0
        p["total_animales"] = n_anim

        if n_anim > 0:
            # Potrero ocupado
            f_ing = (anim.get("ult_fecha_ingreso") if anim else None) or p.get("fecha_entrada")
            dias_ocup = None
            if f_ing and to_date(f_ing):
                dias_ocup = max(1, (hoy_date - to_date(f_ing)).days)
            elif p.get("dias_ocupacion") and int(p["dias_ocupacion"]) > 0:
                dias_ocup = int(p["dias_ocupacion"])

            p["dias_ocupacion"] = dias_ocup
            p["dias_reposo"] = None  # En pastoreo activo

            if dias_ocup is not None:
                if dias_ocup <= 3:
                    p["semaforo"] = "🟢"
                    p["estado_rotacion"] = f"Pastoreo óptimo ({dias_ocup} d)"
                elif dias_ocup <= 6:
                    p["semaforo"] = "🟡"
                    p["estado_rotacion"] = f"Rotar pronto ({dias_ocup} d)"
                else:
                    p["semaforo"] = "🔴"
                    p["estado_rotacion"] = f"Sobreocupado ({dias_ocup} d)"
            else:
                p["semaforo"] = "🟢"
                p["estado_rotacion"] = "Pastoreo activo"
        else:
            # Potrero desocupado / en reposo
            p["dias_ocupacion"] = None
            dias_rep = None
            f_sal = p.get("fecha_salida") or info_salida.get(pid)
            if f_sal and to_date(f_sal):
                dias_rep = max(0, (hoy_date - to_date(f_sal)).days)
            elif p.get("dias_reposo") is not None:
                try:
                    dias_rep = int(p["dias_reposo"])
                except Exception:
                    dias_rep = None

            p["dias_reposo"] = dias_rep
            if dias_rep is not None and dias_rep >= 30:
                p["semaforo"] = "🟢"
                p["estado_rotacion"] = f"Listo pastoreo ({dias_rep} d)"
            elif dias_rep is not None:
                p["semaforo"] = "🌱"
                p["estado_rotacion"] = f"En reposo ({dias_rep} d)"
            else:
                p["semaforo"] = "🌱"
                p["estado_rotacion"] = "En reposo"
    try:
        ndvi = _filas_dict(db.query(
            """SELECT p.nombre potrero, n.fecha, n.ndvi_promedio, n.biomasa_estimada_kg_ha,
                      n.aforo_estimado_kg_m2, n.cobertura_nubes_pct, n.fuente
               FROM monitoreo_satelital_ndvi n
               JOIN potreros p ON p.id = n.potrero_id
               ORDER BY n.id DESC LIMIT 25"""
        ))
    except Exception as e:
        logger.error("seccion ndvi_reciente fallo", exc_info=True)
        errores["ndvi_reciente"] = str(e)
        ndvi = []

    satelite_resumen = {}
    try:
        filas_sat = _filas_dict(db.query(
            """SELECT p.id, p.nombre, p.area_has, n.fecha, n.ndvi_promedio,
                      n.biomasa_estimada_kg_ha, n.aforo_estimado_kg_m2, n.fuente, n.cobertura_nubes_pct
               FROM potreros p
               JOIN monitoreo_satelital_ndvi n ON n.id = (
                   SELECT id FROM monitoreo_satelital_ndvi
                   WHERE potrero_id = p.id ORDER BY id DESC LIMIT 1
               )
               WHERE p.geom_wkt_4326 IS NOT NULL"""
        ))
        if filas_sat:
            total_sar = sum(1 for f in filas_sat if "SENTINEL-1" in (f.get("fuente") or "").upper() or "SAR" in (f.get("fuente") or "").upper())
            total_s2 = sum(1 for f in filas_sat if "SENTINEL-2" in (f.get("fuente") or "").upper())
            prom_ndvi = sum(f["ndvi_promedio"] for f in filas_sat if f.get("ndvi_promedio") is not None) / len(filas_sat)
            biomasas = [f["biomasa_estimada_kg_ha"] for f in filas_sat if f.get("biomasa_estimada_kg_ha") is not None]
            prom_bio = sum(biomasas) / len(biomasas) if biomasas else None
            aforos = [f["aforo_estimado_kg_m2"] for f in filas_sat if f.get("aforo_estimado_kg_m2") is not None]
            prom_af = sum(aforos) / len(aforos) if aforos else None
            fechas = [f["fecha"] for f in filas_sat if f.get("fecha")]
            ult_fecha = max(fechas) if fechas else None
            
            satelite_resumen = {
                "total_potreros": len(filas_sat),
                "total_sar": total_sar,
                "total_optico": total_s2,
                "promedio_ndvi": round(prom_ndvi, 3),
                "promedio_biomasa_kg_ha": round(prom_bio, 1) if prom_bio is not None else None,
                "promedio_aforo_kg_m2": round(prom_af, 2) if prom_af is not None else None,
                "ultima_fecha": ult_fecha,
                "modo_activo": "Radar SAR Sentinel-1 (Todo Clima)" if total_sar > 0 else "Óptico Sentinel-2",
                "cobertura_clima": "100% Todo Clima (Microondas C-band)" if total_sar > 0 else "Óptico (Sensible a nubes)"
            }
    except Exception as e:
        logger.error("seccion satelite_resumen fallo", exc_info=True)
        errores["satelite_resumen"] = str(e)
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
    try:
        from .pronostico import obtener_pronostico_para_despacho, interpretar_pronostico
        _pron = obtener_pronostico_para_despacho(db)
        if _pron:
            pronostico = {
                "dias": [
                    {
                        "fecha": d["fecha"].isoformat() if hasattr(d["fecha"], "isoformat") else str(d["fecha"]),
                        "temp_max_c": d.get("temp_max_c"),
                        "temp_min_c": d.get("temp_min_c"),
                        "lluvia_mm": d.get("lluvia_mm"),
                        "prob_lluvia_pct": d.get("prob_lluvia_pct"),
                    }
                    for d in _pron.get("dias", [])
                ],
                "recomendaciones": interpretar_pronostico(_pron),
                "desactualizado_horas": _pron.get("desactualizado_horas"),
            }
        else:
            pronostico = None
    except Exception as e:
        logger.error("seccion pronostico fallo", exc_info=True)
        errores["pronostico"] = str(e)
        pronostico = None

    try:
        spi_sequia = _filas_dict(db.ultimos_spi_sequia())
    except Exception as e:
        logger.error("seccion spi_sequia fallo", exc_info=True)
        errores["spi_sequia"] = str(e)
        spi_sequia = []

    out: dict[str, Any] = {
        "potreros": potreros,
        "ndvi_reciente": ndvi,
        "satelite_resumen": satelite_resumen,
        "pluviometria_reciente": pluviometria,
        "aforos_recientes": aforos,
        "pronostico": pronostico,
        "spi_sequia": spi_sequia,
    }
    if errores:
        out["errores"] = errores
    return out


def animales_de_potrero(db: Database, potrero_ref: str | int, hoy: Optional[date] = None) -> dict:
    """Retorna los animales ACTIVOS en el potrero indicado, con su clasificación
    zootécnica SG (NV, VS, VP, CH, CM, HL, ML, MC, TR/RP), edad y días en el potrero.
    Cumple estrictamente la Regla Fundamental de Inventario (estado = 'ACTIVO').
    """
    hoy_date = hoy or date.today()
    from ..utils import to_date, normalizar

    p_row = None
    pot_id = None
    if isinstance(potrero_ref, int) or (isinstance(potrero_ref, str) and str(potrero_ref).isdigit()):
        pot_id = int(potrero_ref)
        p_row = db.get_potrero(pot_id)

    if not p_row:
        pot_id = db.resolve_potrero(potrero_ref)
        if pot_id:
            p_row = db.get_potrero(pot_id)

    if not p_row:
        norm_ref = normalizar(str(potrero_ref)).strip().upper()
        if norm_ref in ("SIN POTRERO", "SIN_POTRERO", "NINGUNO", "NULL", "SIN"):
            pot_id = -1
            nom_potrero = "Sin potrero"
            p_row = {"id": -1, "nombre": "Sin potrero", "codigo": "SIN"}
        else:
            todos_p = db.query("SELECT * FROM potreros")
            for p in todos_p:
                nom_p = normalizar(p["nombre"] or p["codigo"] or "").strip().upper()
                if nom_p and (norm_ref == nom_p or norm_ref in nom_p):
                    p_row = p
                    pot_id = p["id"]
                    break

    if not p_row or pot_id is None:
        return {
            "ok": False,
            "error": f"Potrero '{potrero_ref}' no encontrado.",
            "animales": [],
            "total": 0,
        }

    nom_potrero = p_row["nombre"] or p_row["codigo"] or f"Potrero #{pot_id}"

    if pot_id == -1:
        sql = """
            WITH ult_traslado AS (
                SELECT animal_id, potrero_destino, fecha,
                       ROW_NUMBER() OVER (PARTITION BY animal_id ORDER BY fecha DESC, id DESC) as rn
                FROM traslados
            )
            SELECT a.id_animal, a.tag, a.nombre, a.sexo, a.fecha_nacimiento, a.notas,
                   COALESCE(ut.potrero_destino, a.potrero_id) as pot_actual,
                   ut.fecha as fecha_ingreso
            FROM animales a
            LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1
            WHERE a.estado = 'ACTIVO' AND COALESCE(ut.potrero_destino, a.potrero_id) IS NULL
            ORDER BY a.tag ASC
        """
        filas = db.query(sql)
    else:
        sql = """
            WITH ult_traslado AS (
                SELECT animal_id, potrero_destino, fecha,
                       ROW_NUMBER() OVER (PARTITION BY animal_id ORDER BY fecha DESC, id DESC) as rn
                FROM traslados
            )
            SELECT a.id_animal, a.tag, a.nombre, a.sexo, a.fecha_nacimiento, a.notas,
                   COALESCE(ut.potrero_destino, a.potrero_id) as pot_actual,
                   ut.fecha as fecha_ingreso
            FROM animales a
            LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1
            WHERE a.estado = 'ACTIVO' AND COALESCE(ut.potrero_destino, a.potrero_id) = ?
            ORDER BY a.tag ASC
        """
        filas = db.query(sql, (pot_id,))

    animales_out = []
    conteo_cat: dict[str, int] = {}

    for f in filas:
        aid = f["id_animal"]
        tag = f["tag"] or str(aid)
        nombre = f["nombre"] or "—"
        sexo = (f["sexo"] or "").strip().lower()
        es_hembra = bool(sexo.startswith("h") or sexo.startswith("f") or sexo in ("vaca", "novilla", "ternera"))

        # Edad
        f_nac = to_date(f["fecha_nacimiento"])
        edad_dias = max(0, (hoy_date - f_nac).days) if f_nac else None
        if f_nac and edad_dias is not None:
            if edad_dias < 30:
                edad_str = f"{edad_dias}d"
            elif edad_dias < 365:
                meses = edad_dias // 30
                edad_str = f"{meses}m"
            else:
                anios = edad_dias // 365
                meses_rem = (edad_dias % 365) // 30
                edad_str = f"{anios}a {meses_rem}m" if meses_rem > 0 else f"{anios}a"
        else:
            edad_str = "S/D"

        # Días en potrero
        f_ing = to_date(f["fecha_ingreso"])
        if f_ing:
            dias_pot = max(0, (hoy_date - f_ing).days)
        else:
            dias_pot = None

        # Categoría SG
        if es_hembra:
            if edad_dias is not None and edad_dias < 365:
                cat = "CH"
                cat_desc = "Cria Hembra (<1 año)"
            elif edad_dias is not None and edad_dias < 730:
                cat = "HL"
                cat_desc = "Hembra Levante (1-2 años)"
            else:
                p_ult = db.ultimo_parto(aid)
                if p_ult and p_ult["fecha"] and to_date(p_ult["fecha"]):
                    dp = (hoy_date - to_date(p_ult["fecha"])).days
                    if dp <= 305:
                        cat = "VP"
                        cat_desc = "Vaca Parida (<=305 DEL)"
                    else:
                        cat = "VS"
                        cat_desc = "Vaca Seca / Escotera (>305 DEL)"
                else:
                    cat = "NV"
                    cat_desc = "Novilla de Vientre (>=2 años)"
        else:
            nom_m = f"{f['nombre'] or ''} {f['notas'] or ''} {f['tag'] or ''}".upper()
            if "REPRODUCTOR" in nom_m or "PADRON" in nom_m or "TORO" in nom_m or (edad_dias is not None and edad_dias >= 1095):
                cat = "TR"
                cat_desc = "Toro Reproductor"
            elif edad_dias is not None and edad_dias < 365:
                cat = "CM"
                cat_desc = "Cría Macho (<1 año)"
            elif edad_dias is not None and edad_dias < 730:
                cat = "ML"
                cat_desc = "Macho Levante (1-2 años)"
            else:
                cat = "MC"
                cat_desc = "Macho Ceba / Torete (>2 años)"

        conteo_cat[cat] = conteo_cat.get(cat, 0) + 1

        animales_out.append({
            "id_animal": aid,
            "tag": tag,
            "nombre": nombre,
            "sexo": "Hembra" if es_hembra else "Macho",
            "edad": edad_str,
            "edad_dias": edad_dias,
            "estado": cat,
            "estado_desc": cat_desc,
            "categoria_sg": cat,
            "categoria_desc": cat_desc,
            "dias_en_potrero": dias_pot,
            "dias_texto": f"{dias_pot} d" if dias_pot is not None else "—",
            "fecha_ingreso": str(f["fecha_ingreso"]) if f["fecha_ingreso"] else None,
        })

    p_dict = dict(p_row) if p_row else {}
    return {
        "ok": True,
        "potrero": {
            "id": pot_id,
            "nombre": nom_potrero,
            "codigo": p_dict.get("codigo"),
            "area_has": p_dict.get("area_has"),
            "dias_ocupacion": p_dict.get("dias_ocupacion"),
            "dias_reposo": p_dict.get("dias_reposo"),
        },
        "potrero_nombre": nom_potrero,
        "total": len(animales_out),
        "total_animales": len(animales_out),
        "resumen_categorias": conteo_cat,
        "animales": animales_out,
    }


def animales_por_grupo_inventario(
    db: Database,
    tipo: str,
    valor: str,
    sexo: Optional[str] = None,
    hoy: Optional[date] = None,
) -> dict:
    """Retorna los animales ACTIVOS de un grupo del inventario (Estructura del hato,
    Categorías de edad / Brackets, Distribución por potrero, o Pirámide).
    Cumple estrictamente la Regla Fundamental de Inventario (estado = 'ACTIVO').
    """
    hoy_date = hoy or date.today()
    from ..utils import to_date, normalizar

    tipo_norm = (tipo or "").strip().lower()
    valor_norm = normalizar(str(valor or "")).strip().lower()
    sexo_norm = (sexo or "").strip().upper()

    # Si el tipo es potrero, delegar a animales_de_potrero
    if tipo_norm in ("potrero", "potreros"):
        res = animales_de_potrero(db, valor, hoy=hoy_date)
        if res.get("ok"):
            return {
                "ok": True,
                "tipo": "potrero",
                "valor": valor,
                "titulo": f"Potrero: {res.get('potrero_nombre', valor)}",
                "total": res.get("total", 0),
                "total_animales": res.get("total_animales", 0),
                "resumen_categorias": res.get("resumen_categorias", {}),
                "animales": res.get("animales", []),
            }

    sql = """
        WITH ult_traslado AS (
            SELECT animal_id, potrero_destino, fecha, lote,
                   ROW_NUMBER() OVER (PARTITION BY animal_id ORDER BY fecha DESC, id DESC) as rn
            FROM traslados
        ),
        ult_parto AS (
            SELECT vaca_id, MAX(fecha) as ult_parto_fecha
            FROM partos
            GROUP BY vaca_id
        )
        SELECT a.id_animal, a.tag, a.nombre, a.sexo, a.raza, a.fecha_nacimiento, a.madre_id, a.notas,
               COALESCE(ut.potrero_destino, a.potrero_id) as pot_id,
               p.nombre as potrero_nombre,
               ut.fecha as fecha_traslado,
               up.ult_parto_fecha
        FROM animales a
        LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1
        LEFT JOIN ult_parto up ON up.vaca_id = a.id_animal
        LEFT JOIN potreros p ON p.id = COALESCE(ut.potrero_destino, a.potrero_id)
        WHERE a.estado = 'ACTIVO'
        ORDER BY a.tag ASC
    """
    filas = _filas_dict(db.query(sql))

    todos = []
    for a in filas:
        aid = a["id_animal"]
        tag = a["tag"] or str(aid)
        nombre = a["nombre"] or "—"

        fn = to_date(a["fecha_nacimiento"])
        if not fn:
            p = db.query_one(
                "SELECT fecha FROM partos WHERE id_cria = ? AND (vaca_id IS NULL OR vaca_id != ?) ORDER BY fecha DESC LIMIT 1",
                (aid, aid),
            )
            if p and p["fecha"]:
                fn = to_date(p["fecha"])
            elif a["madre_id"] and a["madre_id"] != aid:
                p_m = db.query_one(
                    "SELECT fecha FROM partos WHERE vaca_id = ? AND fecha IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                    (a["madre_id"],),
                )
                if p_m and p_m["fecha"]:
                    d_m = to_date(p_m["fecha"])
                    if d_m and (hoy_date - d_m).days <= 450:
                        fn = d_m

        edad_dias = max(0, (hoy_date - fn).days) if fn else None
        if fn and edad_dias is not None:
            if edad_dias < 30:
                edad_str = f"{edad_dias}d"
            elif edad_dias < 365:
                edad_str = f"{edad_dias // 30}m"
            else:
                anios = edad_dias // 365
                meses_rem = (edad_dias % 365) // 30
                edad_str = f"{anios}a {meses_rem}m" if meses_rem > 0 else f"{anios}a"
        else:
            edad_str = "S/D"

        s_raw = (a["sexo"] or "").strip().lower()
        if not s_raw or s_raw in ("i", "indefinido", "indeterminado", "desconocido", "?"):
            p_cria = db.query_one(
                "SELECT sexo_cria FROM partos WHERE id_cria = ? AND sexo_cria IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                (aid,),
            )
            if p_cria and p_cria["sexo_cria"]:
                s_raw = p_cria["sexo_cria"].strip().lower()

        es_macho = bool(s_raw.startswith("m") or s_raw in ("macho", "toro", "ternero", "novillo", "buey"))
        es_hembra = bool(s_raw.startswith("h") or s_raw in ("hembra", "vaca", "novilla", "ternera"))

        cat_sg = "S/C"
        cat_desc = "Sin clasificar"
        bracket = "Sin clasificar"
        pir_banda = "Desconocida"
        estado_reprod = ""

        if es_hembra:
            sexo_str = "Hembra"
            if edad_dias is not None and edad_dias < 365:
                cat_sg = "CH"
                cat_desc = "Cría hembra"
                bracket = "Hembras <1 año"
                pir_banda = "< 1 año"
                estado_reprod = "Cría al pie"
            elif edad_dias is not None and edad_dias < 730:
                cat_sg = "HL"
                cat_desc = "Levante hembra"
                bracket = "Hembras 1-2 años"
                pir_banda = "1 - 2 años"
                estado_reprod = "Levante"
            else:
                pir_banda = "2+ años"
                if edad_dias is not None:
                    if edad_dias < 1460:
                        bracket = "Hembras 2-4 años"
                    elif edad_dias <= 2921:
                        bracket = "Hembras 4-8 años"
                    elif edad_dias <= 3651:
                        bracket = "Hembras 8-10 años"
                    else:
                        bracket = "Hembras >10 años"
                else:
                    bracket = "Hembras >10 años"

                ult_p = a.get("ult_parto_fecha")
                if ult_p and to_date(ult_p):
                    del_dias = (hoy_date - to_date(ult_p)).days
                    if del_dias <= 305:
                        cat_sg = "VP"
                        cat_desc = "Vaca parida"
                        estado_reprod = f"Parida ({del_dias} DEL)"
                    else:
                        cat_sg = "VS"
                        cat_desc = "Vaca seca"
                        estado_reprod = f"Seca ({del_dias} DEL)"
                else:
                    cat_sg = "NV"
                    cat_desc = "Novilla de vientre"
                    estado_reprod = "Novilla de vientre"
        elif es_macho:
            sexo_str = "Macho"
            nom_m = f"{a['nombre'] or ''} {a['notas'] or ''} {a['tag'] or ''}".upper()
            if "REPRODUCTOR" in nom_m or "PADRON" in nom_m or "TORO" in nom_m or (edad_dias is not None and edad_dias >= 1095):
                cat_sg = "TR"
                cat_desc = "Reproductor"
                bracket = "Reproductor"
                pir_banda = "2+ años"
                estado_reprod = "Toro reproductor"
            elif edad_dias is not None and edad_dias < 365:
                cat_sg = "CM"
                cat_desc = "Cría macho"
                bracket = "Machos <1 año"
                pir_banda = "< 1 año"
                estado_reprod = "Cría al pie"
            elif edad_dias is not None and edad_dias < 730:
                cat_sg = "ML"
                cat_desc = "Levante macho"
                bracket = "Machos 1-2 años"
                pir_banda = "1 - 2 años"
                estado_reprod = "Levante"
            else:
                cat_sg = "MC"
                cat_desc = "Macho de ceba/levante adulto"
                bracket = "Machos >2 años"
                pir_banda = "2+ años"
                estado_reprod = "Ceba / Engorde"
        else:
            sexo_str = "Indefinido"
            cat_sg = "MC"
            cat_desc = "Macho de ceba/levante adulto"
            bracket = "Sin clasificar"
            pir_banda = "Desconocida"

        pot_nom = a["potrero_nombre"] or "Sin potrero"
        f_ing = to_date(a["fecha_traslado"])
        dias_pot = max(0, (hoy_date - f_ing).days) if f_ing else None

        todos.append({
            "id_animal": aid,
            "tag": tag,
            "nombre": nombre,
            "sexo": sexo_str,
            "edad": edad_str,
            "edad_dias": edad_dias,
            "categoria_sg": cat_sg,
            "categoria_desc": cat_desc,
            "bracket": bracket,
            "piramide_banda": pir_banda,
            "potrero_id": a["pot_id"],
            "potrero_nombre": pot_nom,
            "dias_en_potrero": dias_pot,
            "dias_texto": f"{dias_pot} d" if dias_pot is not None else "—",
            "estado_reprod": estado_reprod,
        })

    filtrados = []
    titulo = valor

    if tipo_norm in ("estructura", "categoria_sg", "categoria"):
        for anim in todos:
            c_desc_norm = normalizar(anim["categoria_desc"]).strip().lower()
            c_sg_norm = anim["categoria_sg"].strip().lower()
            if valor_norm in (c_desc_norm, c_sg_norm) or c_desc_norm.startswith(valor_norm) or valor_norm in c_desc_norm:
                filtrados.append(anim)
        titulo = f"Estructura del hato: {valor}"

    elif tipo_norm in ("bracket", "edad", "categoria_edad"):
        for anim in todos:
            b_norm = normalizar(anim["bracket"]).strip().lower()
            if valor_norm == b_norm or valor_norm in b_norm or b_norm.startswith(valor_norm):
                filtrados.append(anim)
        titulo = f"Categoría de Edad: {valor}"

    elif tipo_norm in ("piramide", "piramide_edad"):
        for anim in todos:
            b_norm = normalizar(anim["piramide_banda"]).strip().lower()
            banda_match = (valor_norm in b_norm or b_norm in valor_norm or
                           ("< 1" in valor_norm and "< 1" in b_norm) or
                           ("1 - 2" in valor_norm and "1 - 2" in b_norm) or
                           ("2+" in valor_norm and "2+" in b_norm))
            if banda_match:
                if sexo_norm:
                    if sexo_norm.startswith("H") and anim["sexo"] == "Hembra":
                        filtrados.append(anim)
                    elif sexo_norm.startswith("M") and anim["sexo"] == "Macho":
                        filtrados.append(anim)
                else:
                    filtrados.append(anim)
        sexo_txt = "Hembras" if sexo_norm.startswith("H") else ("Machos" if sexo_norm.startswith("M") else "Hato")
        titulo = f"Pirámide: {sexo_txt} ({valor})"

    elif tipo_norm in ("potrero", "potreros"):
        for anim in todos:
            p_norm = normalizar(anim["potrero_nombre"]).strip().lower()
            if valor_norm in p_norm or p_norm in valor_norm:
                filtrados.append(anim)
        titulo = f"Potrero: {valor}"
    else:
        filtrados = todos
        titulo = "Animales Activos"

    resumen_cats: dict[str, int] = {}
    for anim in filtrados:
        cat_k = anim["categoria_sg"]
        resumen_cats[cat_k] = resumen_cats.get(cat_k, 0) + 1

    return {
        "ok": True,
        "tipo": tipo,
        "valor": valor,
        "titulo": titulo,
        "total": len(filtrados),
        "total_animales": len(filtrados),
        "resumen_categorias": resumen_cats,
        "animales": filtrados,
    }


def datos_leche(db: Database) -> dict:
    """Leche: producción total diaria de la finca (tanque / recibos de quincena) +
    controles zootécnicos.

    Diseñado para el flujo real de finca donde la producción diaria se carga a partir
    de la digitalización o fotos de los recibos de leche (producción total del hato),
    sin mezclar controles individuales históricos obsoletos (2016-2018).
    """
    errores: dict[str, str] = {}
    # 1. Producción diaria del hato (Tanque / Recibos)
    # Si existen registros de la era moderna (>= 2024), aislamos estrictamente el ciclo productivo
    # activo para no mezclar controles individuales de 2016-2018 en la serie diaria.
    try:
        hay_modernos = db.query_one(
            "SELECT 1 FROM produccion_leche WHERE fecha >= '2024-01-01' LIMIT 1"
        )
        filtro_activo = "fecha >= '2024-01-01'" if hay_modernos else "1=1"

        filas_serie = db.query(f"""
            SELECT fecha, SUM(litros) AS litros, 
                   COUNT(id) AS n_registros,
                   MAX(notas) AS notas
            FROM produccion_leche
            WHERE litros IS NOT NULL AND litros > 0 AND {filtro_activo}
            GROUP BY fecha
            ORDER BY fecha ASC
        """)
        
        serie = []
        for r in filas_serie:
            try:
                l = round(float(r["litros"]), 1)
            except (TypeError, ValueError):
                continue
            serie.append({
                "fecha": r["fecha"],
                "litros": l,
                "notas": r["notas"] or None,
            })
    except Exception as e:
        logger.error("seccion serie_tanque fallo", exc_info=True)
        errores["serie_tanque"] = str(e)
        serie = []

    # 2. Métricas ejecutivas y KPIs de producción diaria
    total_litros = round(sum(r["litros"] for r in serie), 1)
    dias_count = len(serie)
    promedio_diario = round(total_litros / dias_count, 1) if dias_count else 0.0
    pico_max = max(serie, key=lambda r: r["litros"]) if serie else None
    piso_min = min(serie, key=lambda r: r["litros"]) if serie else None

    # Variación de cada día respecto al promedio para visualización instantánea
    for r in serie:
        diff = round(r["litros"] - promedio_diario, 1)
        pct = round((diff / promedio_diario) * 100, 1) if promedio_diario > 0 else 0.0
        r["diff_promedio"] = diff
        r["pct_promedio"] = pct

    resumen = {
        "total_litros": total_litros,
        "dias": dias_count,
        "promedio_diario": promedio_diario,
        "pico_max": pico_max,
        "piso_min": piso_min,
        "fecha_inicio": serie[0]["fecha"] if serie else None,
        "fecha_fin": serie[-1]["fecha"] if serie else None,
        "periodo_notas": serie[0].get("notas") if (serie and serie[0].get("notas")) else None,
    }

    # 3. Controles individuales y ranking (solo si hay datos modernos con tag)
    try:
        controles_modernos = _filas_dict(db.query(
            """SELECT a.tag, l.fecha, l.litros FROM produccion_leche l
               JOIN animales a ON a.id_animal = l.animal_id
               WHERE l.animal_id IS NOT NULL AND l.fecha >= '2024-01-01'
               ORDER BY l.fecha DESC LIMIT 20"""
        ))
    except Exception as e:
        logger.error("seccion controles fallo", exc_info=True)
        errores["controles"] = str(e)
        controles_modernos = []

    try:
        ranking = _filas_dict(db.query(
            """SELECT a.tag, COUNT(l.id) AS controles, SUM(l.litros) AS total_litros,
                      MAX(l.fecha) AS ultima_fecha
               FROM produccion_leche l JOIN animales a ON a.id_animal = l.animal_id
               WHERE a.estado = 'ACTIVO' AND l.litros IS NOT NULL AND l.fecha >= '2024-01-01'
               GROUP BY a.id_animal, a.tag
               HAVING SUM(l.litros) > 0
               ORDER BY total_litros DESC LIMIT 8"""
        ))
        for r in ranking:
            try:
                r["total_litros"] = round(float(r["total_litros"]), 1)
            except (TypeError, ValueError):
                r["total_litros"] = 0
    except Exception as e:
        logger.error("seccion ranking_vacas fallo", exc_info=True)
        errores["ranking_vacas"] = str(e)
        ranking = []

    # 4. Fotos de recibos y planillas de quincena
    try:
        fotos_recibos = _filas_dict(db.query(
            """SELECT id, ruta, fecha, caption, notas
               FROM fotos
               WHERE caption LIKE 'Recibo Quincenal%' OR caption LIKE '%Recibo%Leche%'
               ORDER BY fecha DESC, id DESC LIMIT 12"""
        ))
    except Exception:
        logger.error("seccion fotos_recibos fallo", exc_info=True)
        fotos_recibos = []

    # 5. Conteo histórico informativo de SG 2016-2018
    try:
        hist_row = db.query_one(
            "SELECT COUNT(*) AS c FROM produccion_leche WHERE fecha < '2024-01-01'"
        )
        total_historico = int(hist_row["c"]) if hist_row else 0
    except Exception:
        total_historico = 0

    out: dict[str, Any] = {
        "serie_tanque": serie,
        "resumen": resumen,
        "controles": controles_modernos,
        "ranking_vacas": ranking,
        "fotos_recibos": fotos_recibos,
        "total_historico_sg": total_historico,
    }
    if errores:
        out["errores"] = errores
    return out


CATEGORIAS_FINANZAS = {
    "INGRESO": ["VENTA_LECHE", "OTRO_INGRESO"],
    "EGRESO": ["NOMINA", "INSUMO", "VETERINARIO", "INFRAESTRUCTURA", "COMBUSTIBLE", "OTRO_EGRESO"],
}


def datos_finanzas(db: Database, desde: Optional[str] = None, hasta: Optional[str] = None) -> dict:
    """Libro de Ingresos/Egresos + resumen de Utilidad. La venta/compra de
    animales no vive en `finanzas` (ya está en `movimientos` con su precio);
    `resumen_finanzas` la suma desde allá para no duplicar el dato."""
    hoy = date.today()
    desde = desde or date(hoy.year, 1, 1).isoformat()
    hasta = hasta or date(hoy.year, 12, 31).isoformat()

    errores: dict[str, str] = {}
    resumen: dict[str, Any] = {"total_ingresos": 0.0, "total_egresos": 0.0, "utilidad": 0.0, "categorias": []}
    try:
        resumen = db.resumen_finanzas(desde, hasta)
    except Exception as e:
        logger.error("seccion resumen_finanzas fallo", exc_info=True)
        errores["resumen"] = str(e)

    try:
        recientes = _filas_dict(db.query(
            """SELECT f.id, f.fecha, f.tipo, f.categoria, f.concepto, f.monto, f.litros,
                      f.contraparte, f.foto_ruta, f.notas, a.tag AS animal_tag, p.nombre AS potrero_nombre
               FROM finanzas f
               LEFT JOIN animales a ON a.id_animal = f.animal_id
               LEFT JOIN potreros p ON p.id = f.potrero_id
               WHERE f.fecha >= ? AND f.fecha <= ?
               ORDER BY f.fecha DESC, f.id DESC LIMIT 60""",
            (desde, hasta),
        ))
    except Exception as e:
        logger.error("seccion finanzas_recientes fallo", exc_info=True)
        errores["recientes"] = str(e)
        recientes = []

    try:
        ventas_compras = _filas_dict(db.query(
            """SELECT m.id, m.fecha, UPPER(m.tipo_movimiento) AS tipo_movimiento,
                      m.precio, m.procedencia_destino, m.notas, a.tag AS animal_tag
               FROM movimientos m JOIN animales a ON a.id_animal = m.animal_id
               WHERE m.fecha >= ? AND m.fecha <= ? AND m.precio IS NOT NULL AND m.precio > 0
               ORDER BY m.fecha DESC, m.id DESC LIMIT 60""",
            (desde, hasta),
        ))
    except Exception as e:
        logger.error("seccion finanzas_ventas_compras fallo", exc_info=True)
        errores["ventas_compras"] = str(e)
        ventas_compras = []

    try:
        kpis = db.kpis_financieros(desde, hasta)
    except Exception as e:
        logger.error("seccion kpis_financieros fallo", exc_info=True)
        errores["kpis"] = str(e)
        kpis = None

    out: dict[str, Any] = {
        "desde": desde, "hasta": hasta,
        "resumen": resumen,
        "recientes": recientes,
        "ventas_compras": ventas_compras,
        "categorias_disponibles": CATEGORIAS_FINANZAS,
        "kpis": kpis,
    }
    if errores:
        out["errores"] = errores
    return out


def to_date_safe(v) -> Optional[date]:
    """Convierte fecha ISO/texto a date sin lanzar (None si no puede)."""
    if v is None:
        return None
    try:
        from ..utils import to_date
        return to_date(str(v)[:10])
    except Exception:
        try:
            from src.utils import to_date
            return to_date(str(v)[:10])
        except Exception:
            return None


def calcular_estados_zootecnicos(f: dict) -> dict:
    """Calcula con rigor zootécnico el estado fisiológico y reproductivo del animal."""
    hoy = date.today()
    sexo = str(f.get("sexo") or "").strip().lower()
    es_hembra = sexo.startswith("h") or sexo.startswith("f")
    es_macho = bool(sexo.startswith("m") or sexo in ("macho", "toro", "ternero", "novillo"))
    edad_dias = f.get("edad_dias")
    tag = str(f.get("tag") or "").strip()
    notas = str(f.get("notas") or "")
    nombre = str(f.get("nombre") or "")
    txt_info = f"{tag} {nombre} {notas}".upper()

    # 1. Estado Fisiológico / Productivo
    cod_fisio = "ADULTO"
    titulo_fisio = "Adulto"
    badge_fisio = "Adulto"
    color_fisio = "gris"
    icono_fisio = "cow"
    detalle_fisio = ""

    es_toro = bool(
        re.match(r"^T\d+", tag, re.IGNORECASE)
        or re.search(r"\b(?:TORO|REPRODUCTOR|PADRON)\b", txt_info)
    )

    if es_macho:
        if es_toro:
            cod_fisio = "TORO"
            titulo_fisio = "Toro Reproductor"
            badge_fisio = "Toro Reproductor"
            color_fisio = "azul"
            icono_fisio = "bull"
            detalle_fisio = "Macho reproductor activo de la finca"
        elif edad_dias is not None and edad_dias < 365:
            cod_fisio = "CRIA_MACHO"
            titulo_fisio = "Cría (Ternero)"
            badge_fisio = "Cría (Ternero)"
            color_fisio = "verde"
            icono_fisio = "calf"
            detalle_fisio = f"Lactante / Levante inicial ({f.get('edad_str') or ''})"
        elif edad_dias is not None and edad_dias < 730:
            cod_fisio = "NOVILLO_LEVANTE"
            titulo_fisio = "Novillo de levante"
            badge_fisio = "Novillo levante"
            color_fisio = "ambar"
            icono_fisio = "cow"
            detalle_fisio = f"En desarrollo ({f.get('edad_str') or ''})"
        else:
            cod_fisio = "NOVILLO"
            titulo_fisio = "Novillo / Macho"
            badge_fisio = "Novillo"
            color_fisio = "gris"
            icono_fisio = "cow"
            detalle_fisio = f"Macho ({f.get('edad_str') or ''})"

    elif es_hembra:
        lactancia = f.get("lactancia") or {}
        ult_parto = f.get("ultimo_parto") or {}
        tiene_partos = bool(ult_parto and ult_parto.get("fecha")) or bool(f.get("partos"))
        del_dias = lactancia.get("del_dias")

        if edad_dias is not None and edad_dias < 365 and not tiene_partos:
            cod_fisio = "CRIA_HEMBRA"
            titulo_fisio = "Cría (Ternera)"
            badge_fisio = "Cría (Ternera)"
            color_fisio = "verde"
            icono_fisio = "calf"
            detalle_fisio = f"Lactante al pie ({f.get('edad_str') or ''})"
        elif edad_dias is not None and edad_dias < 730 and not tiene_partos:
            cod_fisio = "NOVILLA_LEVANTE"
            titulo_fisio = "Novilla de levante"
            badge_fisio = "Novilla levante"
            color_fisio = "ambar"
            icono_fisio = "cow"
            detalle_fisio = f"En desarrollo ({f.get('edad_str') or ''})"
        elif edad_dias is not None and edad_dias < 1095 and not tiene_partos:
            cod_fisio = "NOVILLA_VIENTRE"
            titulo_fisio = "Novilla de vientre"
            badge_fisio = "Novilla vientre"
            color_fisio = "purpura"
            icono_fisio = "cow"
            detalle_fisio = "Apta para primer servicio / IA"
        else:
            # Vaca Adulta
            if lactancia.get("estado") == "En ordeño":
                cod_fisio = "VACA_ORDENO"
                titulo_fisio = "Vaca en Ordeño"
                badge_fisio = f"En Ordeño ({del_dias} DEL)" if del_dias is not None else "En Ordeño"
                color_fisio = "verde"
                icono_fisio = "milk"
                f_p = ult_parto.get("fecha")
                detalle_fisio = f"Lactancia activa: {del_dias} Días En Leche (parto: {f_p})" if f_p else "Lactancia activa"
            elif lactancia.get("estado") == "Seca":
                cod_fisio = "VACA_SECA"
                titulo_fisio = "Vaca Seca"
                badge_fisio = "Vaca Seca"
                color_fisio = "ambar"
                icono_fisio = "grass"
                f_sec = lactancia.get("fecha_secado")
                detalle_fisio = f"Secada el {f_sec} (preparación para parto)" if f_sec else "Período seco (sin ordeño)"
            else:
                pot_nom = str(f.get("potrero") or "").upper()
                if "ORDEÑO" in pot_nom or "PARIDA" in pot_nom:
                    cod_fisio = "VACA_ORDENO"
                    titulo_fisio = "Vaca en Ordeño"
                    badge_fisio = "En Ordeño"
                    color_fisio = "verde"
                    icono_fisio = "milk"
                    detalle_fisio = "En lote de ordeño activo"
                else:
                    cod_fisio = "VACA_SECA"
                    titulo_fisio = "Vaca Seca"
                    badge_fisio = "Vaca Seca"
                    color_fisio = "ambar"
                    icono_fisio = "grass"
                    detalle_fisio = "Vaca en período seco / horra"

    # 2. Estado Reproductivo (Ciclo Vigente)
    cod_repro = "SIN_DATOS"
    titulo_repro = "Sin datos reproductivos"
    badge_repro = "Sin datos"
    color_repro = "gris"
    dias_abiertos = None
    dias_gestacion = None
    fep_iso = None
    alerta_repro = None
    detalle_repro = ""

    if es_hembra:
        ult_parto = f.get("ultimo_parto")
        f_parto_d = to_date_safe(ult_parto["fecha"]) if ult_parto and ult_parto.get("fecha") else None

        # Servicios y diagnósticos del ciclo VIGENTE (posteriores al último parto)
        servicios_ciclo = []
        for s in f.get("servicios") or []:
            f_s = to_date_safe(s.get("fecha"))
            if f_s and (not f_parto_d or f_s >= f_parto_d):
                servicios_ciclo.append(s)

        diag_ciclo = []
        for d in f.get("diagnosticos") or []:
            f_d = to_date_safe(d.get("fecha"))
            if f_d and (not f_parto_d or f_d >= f_parto_d):
                diag_ciclo.append(d)

        ult_serv_ciclo = servicios_ciclo[0] if servicios_ciclo else None
        ult_diag_ciclo = diag_ciclo[0] if diag_ciclo else None

        if f_parto_d:
            dias_abiertos = max(0, (hoy - f_parto_d).days)

        # ¿Está confirmada preñada en este ciclo?
        es_prenada = False
        if ult_diag_ciclo and str(ult_diag_ciclo.get("resultado") or "").upper() in ("PREÑADA", "PREGNANT", "POSITIVO"):
            es_prenada = True
        elif ult_serv_ciclo and str(ult_serv_ciclo.get("estado") or "").upper() in ("CONFIRMADA", "PREÑADA"):
            es_prenada = True

        if es_prenada:
            cod_repro = "PREÑADA"
            f_serv_d = to_date_safe(ult_serv_ciclo.get("fecha")) if ult_serv_ciclo else None
            fep_iso = str(ult_serv_ciclo["fep_calculada"])[:10] if ult_serv_ciclo and ult_serv_ciclo.get("fep_calculada") else None
            if f_serv_d:
                dias_gestacion = max(0, (hoy - f_serv_d).days)
            elif ult_diag_ciclo and ult_diag_ciclo.get("dias_gestacion"):
                dias_gestacion = int(ult_diag_ciclo["dias_gestacion"])

            meses_gest = round(dias_gestacion / 30.4, 1) if dias_gestacion is not None else None
            gest_txt = f" · {dias_gestacion} d gestación (~{meses_gest} m)" if dias_gestacion is not None else ""
            fep_txt = f" (FEP: {fep_iso})" if fep_iso else ""

            titulo_repro = f"Preñada / Gestante{fep_txt}{gest_txt}"
            badge_repro = f"Preñada ({dias_gestacion}d)" if dias_gestacion else "Preñada"
            color_repro = "verde"
            detalle_repro = f"Gestación confirmada. FEP estimada: {fep_iso or 'S/D'}{gest_txt}"

            if fep_iso:
                f_fep = to_date_safe(fep_iso)
                if f_fep:
                    dias_para_parto = (f_fep - hoy).days
                    if 0 < dias_para_parto <= 60 and cod_fisio == "VACA_ORDENO":
                        alerta_repro = f"⚠️ Próxima al parto ({dias_para_parto} días restantes). Programar SECADO."

        elif ult_serv_ciclo:
            f_serv_d = to_date_safe(ult_serv_ciclo.get("fecha"))
            dias_post_serv = (hoy - f_serv_d).days if f_serv_d else 0
            fep_iso = str(ult_serv_ciclo["fep_calculada"])[:10] if ult_serv_ciclo.get("fep_calculada") else None
            toro_txt = f" con {ult_serv_ciclo.get('toro_pajilla')}" if ult_serv_ciclo.get("toro_pajilla") else ""

            f_diag_d = to_date_safe(ult_diag_ciclo.get("fecha")) if ult_diag_ciclo else None
            if ult_diag_ciclo and f_diag_d and f_serv_d and f_diag_d >= f_serv_d and str(ult_diag_ciclo.get("resultado") or "").upper() in ("VACIA", "VACÍA", "NEGATIVO"):
                cod_repro = "VACIA_PALPADA"
                titulo_repro = f"Vacía (Palpada negativa el {f_diag_d})"
                badge_repro = "Vacía (Palpada)"
                color_repro = "rojo"
                detalle_repro = f"Diagnóstico de gestación negativo ({f_diag_d}). Requiere servicio en próximo celo."
                alerta_repro = "⚠️ Palpación negativa: observar celo para reinseminar."
            else:
                cod_repro = "SERVIDA_SIN_PALPAR"
                fep_txt = f" · FEP: {fep_iso}" if fep_iso else ""
                titulo_repro = f"Servida / Sin palpar ({dias_post_serv} días post-servicio{toro_txt}){fep_txt}"
                badge_repro = f"Servida ({dias_post_serv}d sin palpar)"
                color_repro = "ambar"
                detalle_repro = f"Servicio / IA el {f_serv_d}{toro_txt}. FEP estimada: {fep_iso or 'S/D'}."

                if dias_post_serv >= 60:
                    alerta_repro = f"⚠️ Palpación pendiente ({dias_post_serv} días post-servicio, >60d)."
                elif dias_post_serv >= 35:
                    alerta_repro = f"⚠️ Ecografía pendiente ({dias_post_serv} días post-servicio, >35d)."

        elif f_parto_d:
            cod_repro = "VACIA_SIN_PALPAR"
            titulo_repro = f"Vacía / Abierta ({dias_abiertos} días post-parto)"
            badge_repro = f"Vacía ({dias_abiertos}d abiertos)"
            color_repro = "gris"
            detalle_repro = f"Último parto el {f_parto_d}. Lleva {dias_abiertos} días abiertos sin nuevo servicio."

            if dias_abiertos > 150:
                color_repro = "rojo"
                alerta_repro = f"⚠️ Días abiertos críticos ({dias_abiertos} días post-parto > 150d). Revisar condición ovárica."
            elif dias_abiertos > 90:
                color_repro = "ambar"
                alerta_repro = f"⚠️ Días abiertos elevados ({dias_abiertos} días > 90d). Programar servicio pronto."

        elif cod_fisio == "NOVILLA_VIENTRE":
            cod_repro = "NOVILLA_APTA"
            titulo_repro = "Novilla apta para primer servicio"
            badge_repro = "Apta para servicio"
            color_repro = "purpura"
            detalle_repro = "Edad y desarrollo adecuados para inseminación o monta."
        elif edad_dias is not None and edad_dias >= 1095:
            cod_repro = "VACIA_SIN_PALPAR"
            titulo_repro = "Vaca Vacía / Sin palpar"
            badge_repro = "Vacía (Sin palpar)"
            color_repro = "gris"
            detalle_repro = "Vaca adulta sin servicio ni diagnóstico de preñez reciente registrado."
        else:
            cod_repro = "CRECIMIENTO"
            titulo_repro = "En crecimiento / Levante"
            badge_repro = "En crecimiento"
            color_repro = "gris"
            detalle_repro = "Hembra joven en etapa de desarrollo antes de edad reproductiva."

    elif es_macho:
        if es_toro:
            cod_repro = "TORO_REPRODUCTOR"
            titulo_repro = "Toro reproductor activo"
            badge_repro = "Toro Reproductor"
            color_repro = "azul"
            detalle_repro = "Macho padre reproductor disponible en el hato."
        else:
            cod_repro = "MACHO_ACTIVO"
            titulo_repro = "Macho en desarrollo / ceba"
            badge_repro = "Macho"
            color_repro = "gris"
            detalle_repro = "Macho no reproductor."

    return {
        "fisiologico": {
            "codigo": cod_fisio,
            "titulo": titulo_fisio,
            "badge": badge_fisio,
            "color": color_fisio,
            "icono": icono_fisio,
            "detalle": detalle_fisio,
        },
        "reproductivo": {
            "codigo": cod_repro,
            "titulo": titulo_repro,
            "badge": badge_repro,
            "color": color_repro,
            "dias_abiertos": dias_abiertos,
            "dias_gestacion": dias_gestacion,
            "fep": fep_iso,
            "alerta": alerta_repro,
            "detalle": detalle_repro,
        }
    }


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
            "hierro": an.get("hierro"), "chip": an.get("chip"), "color": an.get("color"),
            "notas": an.get("notas"),
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
            "SELECT id, fecha, peso_kg, gmd_calculada FROM pesajes WHERE animal_id = ? "
            "ORDER BY fecha DESC LIMIT 15", (aid,)))
    except Exception as e:
        logger.error("seccion pesajes fallo", exc_info=True)
        errores["pesajes"] = str(e)
        base["pesajes"] = []
    try:
        base["tratamientos"] = _filas_dict(db.query(
            "SELECT id, fecha, producto, dosis, fecha_fin_retiro_leche, fecha_fin_retiro_carne "
            "FROM tratamientos WHERE animal_id = ? ORDER BY fecha DESC LIMIT 15", (aid,)))
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
            """SELECT p.id, p.fecha, p.sexo_cria, p.estado_cria, p.peso_nacimiento, c.tag AS cria_tag
               FROM partos p LEFT JOIN animales c ON c.id_animal = p.id_cria
               WHERE p.vaca_id = ? AND (p.id_cria IS NULL OR p.id_cria != ?)
               ORDER BY p.fecha DESC LIMIT 15""", (aid, aid)))
    except Exception as e:
        logger.error("seccion partos fallo", exc_info=True)
        errores["partos"] = str(e)
        base["partos"] = []
    try:
        base["servicios"] = _filas_dict(db.query(
            """SELECT id, fecha, tipo_servicio, toro_pajilla, inseminador, fep_calculada, estado
               FROM servicios WHERE vaca_id = ? ORDER BY fecha DESC, id DESC LIMIT 15""", (aid,)))
    except Exception as e:
        logger.error("seccion servicios fallo", exc_info=True)
        errores["servicios"] = str(e)
        base["servicios"] = []
    try:
        base["diagnosticos"] = _filas_dict(db.query(
            """SELECT id, fecha, resultado, dias_gestacion FROM diagnosticos_gestacion
               WHERE vaca_id = ? ORDER BY fecha DESC, id DESC LIMIT 10""", (aid,)))
    except Exception as e:
        logger.error("seccion diagnosticos fallo", exc_info=True)
        errores["diagnosticos"] = str(e)
        base["diagnosticos"] = []
    lactancia: Optional[dict[str, Any]] = None
    try:
        if es_hembra and base.get("ultimo_parto") and base["ultimo_parto"].get("fecha"):
            fecha_parto_iso = base["ultimo_parto"]["fecha"]
            f_parto = to_date_safe(fecha_parto_iso)
            if f_parto:
                del_dias = max(0, (date.today() - f_parto).days)
                # Secado real (tabla `secados`) posterior al último parto:
                # reemplaza el estimado por días con la fecha confirmada --
                # un destete de la cría NO seca a la vaca, solo un secado
                # explícito lo hace (ver Database.registrar_secado).
                secado_row = db.query_one(
                    "SELECT fecha FROM secados WHERE animal_id = ? AND fecha >= ? "
                    "ORDER BY fecha DESC, id DESC LIMIT 1",
                    (aid, fecha_parto_iso),
                )
                if secado_row and secado_row["fecha"]:
                    lactancia = {
                        "del_dias": del_dias,
                        "estado": "Seca",
                        "estado_confirmado": True,
                        "fecha_secado": secado_row["fecha"],
                        "fecha_parto": fecha_parto_iso,
                    }
                else:
                    lactancia = {
                        "del_dias": del_dias,
                        "estado": "En ordeño" if del_dias < 300 else "Seca",
                        "estado_confirmado": False,
                        "fecha_parto": fecha_parto_iso,
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
                "SELECT id_animal, tag, nombre, raza, sexo, padre_id, madre_id, estado, hierro "
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
                "hierro": row["hierro"] if "hierro" in row.keys() else None,
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
            SELECT a.id_animal, a.tag, a.nombre, a.sexo, a.raza, a.fecha_nacimiento, a.estado, a.hierro,
                   p.id AS parto_id, p.fecha AS fecha_parto, p.peso_nacimiento, p.estado_cria
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
            SELECT p.id AS parto_id, NULL AS id_animal, 'Sin arete' AS tag, NULL AS nombre, p.sexo_cria AS sexo,
                   NULL AS raza, p.fecha AS fecha_nacimiento, 'ACTIVO' AS estado,
                   p.fecha AS fecha_parto, p.peso_nacimiento, p.estado_cria
            FROM partos p
            WHERE p.vaca_id = ? AND p.id_cria IS NULL
            ORDER BY p.fecha DESC
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

    # Texto ASCII del árbol para copiar y pegar a mano en Telegram/WhatsApp.
    # formatear_genealogia_animal_tab() devuelve HTML (<b>/<i>) porque el bot lo
    # envía con parse_mode="HTML" vía la API; aquí se convierte a *negrita*/_cursiva_
    # estilo WhatsApp, porque un chat manual no interpreta esas etiquetas HTML.
    try:
        from ..server.formatters import formatear_genealogia_animal_tab, html_telegram_a_texto_compartible
        texto_arbol = html_telegram_a_texto_compartible(formatear_genealogia_animal_tab(db, an["tag"]))
    except Exception:
        try:
            from src.server.formatters import formatear_genealogia_animal_tab, html_telegram_a_texto_compartible
            texto_arbol = html_telegram_a_texto_compartible(formatear_genealogia_animal_tab(db, an["tag"]))
        except Exception:
            texto_arbol = ""

    base["abuelo_pat"] = p_abuelo_pat
    base["abuela_pat"] = p_abuela_pat
    base["abuelo_mat"] = m_abuelo_mat
    base["abuela_mat"] = m_abuela_mat
    base["consanguinidad"] = consang_info
    base["texto_arbol"] = texto_arbol

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

    # 7. Resumen zootécnico (fisiológico y reproductivo con rigor)
    estados_z = calcular_estados_zootecnicos(base)
    base["estado_fisiologico"] = estados_z["fisiologico"]
    base["estado_reproductivo"] = estados_z["reproductivo"]
    base["estado_repro"] = estados_z["reproductivo"]["titulo"]
    base["dias_abiertos"] = estados_z["reproductivo"]["dias_abiertos"]
    base["alerta_repro"] = estados_z["reproductivo"]["alerta"]

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

    # 9. Movimientos (ventas, compras, traslados, bajas)
    try:
        m_rows = db.query(
            """SELECT fecha, tipo_movimiento, procedencia_destino, precio, notas
               FROM movimientos
               WHERE animal_id = ?
               ORDER BY fecha DESC, id DESC LIMIT 20""", (aid,)
        )
        base["movimientos"] = _filas_dict(m_rows)
    except Exception:
        logger.error("seccion movimientos fallo", exc_info=True)
        base["movimientos"] = []

    # 10. Datos específicos de venta (solo aplicable si el animal está en estado VENDIDO)
    venta_info: Optional[dict[str, Any]] = None
    try:
        if str(an.get("estado") or "").upper() == "VENDIDO":
            v_row = db.query_one(
                """SELECT fecha, tipo_movimiento, procedencia_destino, precio, notas
                   FROM movimientos
                   WHERE animal_id = ? AND UPPER(tipo_movimiento) = 'VENTA'
                   ORDER BY fecha DESC, id DESC LIMIT 1""", (aid,)
            )
            if v_row:
                venta_info = dict(v_row)
                f_v = venta_info.get("fecha")
                # Verificar si se vendió junto a su madre en la misma fecha
                if an.get("madre_id") and f_v:
                    m_v = db.query_one(
                        """SELECT a.tag, a.nombre FROM movimientos mo
                           JOIN animales a ON a.id_animal = mo.animal_id
                           WHERE mo.animal_id = ? AND mo.fecha = ? AND UPPER(mo.tipo_movimiento) = 'VENTA' LIMIT 1""",
                        (an["madre_id"], f_v)
                    )
                    if m_v:
                        venta_info["madre_tag"] = m_v["tag"]
                        venta_info["madre_nombre"] = m_v["nombre"]
                # Verificar si se vendió con crías en la misma fecha
                if f_v:
                    c_v = db.query(
                        """SELECT a.tag, a.nombre FROM movimientos mo
                           JOIN animales a ON a.id_animal = mo.animal_id
                           WHERE a.madre_id = ? AND mo.fecha = ? AND UPPER(mo.tipo_movimiento) = 'VENTA'""",
                        (aid, f_v)
                    )
                    if c_v:
                        venta_info["crias_vendidas"] = [{"tag": r["tag"], "nombre": r["nombre"]} for r in c_v]
            else:
                venta_info = {
                    "fecha": None,
                    "tipo_movimiento": "VENTA",
                    "procedencia_destino": None,
                    "precio": None,
                    "notas": "Estado marcado como VENDIDO en base de datos",
                }
    except Exception as e:
        logger.error("seccion venta fallo", exc_info=True)
        errores["venta"] = str(e)
    base["venta"] = venta_info

    # 11. Datos específicos de muerte (si existe registro en muertes)
    muerte_info: Optional[dict[str, Any]] = None
    try:
        mu_row = db.query_one(
            """SELECT fecha, causa_presunta, notas
               FROM muertes
               WHERE animal_id = ?
               ORDER BY fecha DESC, id DESC LIMIT 1""", (aid,)
        )
        if mu_row:
            muerte_info = dict(mu_row)
        elif str(an.get("estado") or "").upper() == "MUERTO":
            muerte_info = {
                "fecha": None,
                "causa_presunta": "Sin causa registrada",
                "notas": "Estado marcado como MUERTO en base de datos",
            }
    except Exception as e:
        logger.error("seccion muerte fallo", exc_info=True)
        errores["muerte"] = str(e)
    base["muerte"] = muerte_info

    # 12. Historial consolidado de bajas y movimientos
    historial_bajas: list[dict[str, Any]] = []
    if base.get("movimientos"):
        for m in base["movimientos"]:
            historial_bajas.append({
                "fecha": m.get("fecha"),
                "tipo": m.get("tipo_movimiento") or "MOVIMIENTO",
                "destino_causa": m.get("procedencia_destino") or "",
                "precio": m.get("precio"),
                "notas": m.get("notas") or "",
            })
    if muerte_info and muerte_info.get("fecha"):
        ya_existe = any(h.get("tipo", "").upper() in ("MUERTE", "BAJA") and h.get("fecha") == muerte_info["fecha"] for h in historial_bajas)
        if not ya_existe:
            historial_bajas.append({
                "fecha": muerte_info.get("fecha"),
                "tipo": "MUERTE",
                "destino_causa": muerte_info.get("causa_presunta") or "Muerte registrada",
                "precio": None,
                "notas": muerte_info.get("notas") or "",
            })
    historial_bajas.sort(key=lambda x: str(x.get("fecha") or ""), reverse=True)
    base["historial_bajas"] = historial_bajas

    if errores:
        base["errores"] = errores
    return base



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
        # Selector de potreros y animales activos: con búsqueda vacía se devuelve
        # la lista completa de potreros vigentes y de animales activos para
        # alimentar los datalists de la PWA (#dl-potreros y #dl-tags).
        try:
            filas_p = db.query(
                "SELECT nombre, codigo FROM potreros WHERE geom_wkt_4326 IS NOT NULL "
                "ORDER BY nombre LIMIT 200"
            )
            out["potreros"] = _filas_dict(filas_p)
        except Exception as e:
            logger.error("seccion potreros_lista_completa fallo", exc_info=True)
            errores["potreros"] = str(e)
        try:
            filas_a = db.query(
                """SELECT a.tag, a.nombre, a.sexo, a.raza FROM animales a
                   WHERE a.estado = 'ACTIVO' AND a.tag IS NOT NULL
                   ORDER BY a.tag LIMIT 500"""
            )
            out["animales"] = _filas_dict(filas_a)
        except Exception as e:
            logger.error("seccion animales_lista_completa fallo", exc_info=True)
            errores["animales"] = str(e)
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
            (like, like, max(limite, 50)),
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
        "estructura_hato": _estructura_hato(db),
        "tasa_descarte": _tasa_descarte_anual(db),
    }
    if errores:
        out["errores"] = errores
    return out


def _estructura_hato(db: Database) -> dict:
    """Estructura del hato (9 categorías SG: CH/HL/NV/VP/VS/CM/ML/MC/REP) con
    % y UGG estimado, para la sección "Estructura del hato" de Inventario."""
    try:
        from .query.helpers import calcular_estructura_hato_sg
        return calcular_estructura_hato_sg(db)
    except Exception:
        logger.error("seccion estructura_hato fallo", exc_info=True)
        return {"filas": [], "total": 0, "total_ugg": 0.0}


def _tasa_descarte_anual(db: Database, hoy: Optional[date] = None) -> Optional[dict]:
    """% de salidas (venta + muerte) del año calendario actual, sobre una base
    que aproxima el hato de inicio de año (activos actuales + salidas del
    año) para no necesitar un snapshot histórico que no existe."""
    hoy = hoy or date.today()
    try:
        ano = hoy.year
        desde = f"{ano}-01-01"
        ventas = db.query_one(
            "SELECT COUNT(*) n FROM movimientos WHERE tipo_movimiento = 'VENTA' AND fecha >= ?",
            (desde,),
        )["n"]
        muertes = db.query_one(
            "SELECT COUNT(*) n FROM muertes WHERE fecha >= ?", (desde,)
        )["n"]
        activos = db.query_one("SELECT COUNT(*) n FROM animales WHERE estado = 'ACTIVO'")["n"]
        salidas = ventas + muertes
        base = activos + salidas
        return {
            "ano": ano,
            "ventas": ventas,
            "muertes": muertes,
            "salidas": salidas,
            "pct": round(salidas / base * 100, 2) if base else 0.0,
        }
    except Exception:
        logger.error("seccion tasa_descarte fallo", exc_info=True)
        return None


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
    Incluye además los recordatorios de campo PENDIENTES
    (``recordatorios_programados``, misma tabla del comando ``/programar``:
    vencidos + próximos dentro de la ventana) para que la vista Agenda y la
    campanita muestren una sola lista coherente sin duplicar lógica.
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
    # Recordatorios de campo (/programar): vencidos + próximos en ventana.
    # Reusa la misma tabla y estados PENDIENTE/ENVIADO/REALIZADO del Despacho Matutino.
    recordatorios: list[dict] = []
    recordatorios_completados: list[dict] = []
    try:
        rows_rec = db.query(
            """SELECT id, mensaje, fecha_programada, hora, estado, creado_por,
                      asignado_a, asignado_a_id, tipo_objetivo, animal_tag, potrero_nombre,
                      tipo_tarea, prioridad, completado_en, completado_por,
                      notas_completado, foto_completado
               FROM recordatorios_programados
               WHERE estado = 'PENDIENTE'
                 AND (fecha_programada IS NULL OR fecha_programada <= ?)
               ORDER BY
                 CASE WHEN fecha_programada IS NULL THEN 1 ELSE 0 END,
                 fecha_programada, hora, id LIMIT 80""",
            (limite,),
        )
        for r in _filas_dict(rows_rec):
            fprog = str(r.get("fecha_programada") or "")[:10] or None
            try:
                faltan = (date.fromisoformat(fprog) - hoy).days if fprog else None
            except Exception:
                faltan = None
            recordatorios.append({
                "id": r.get("id"),
                "mensaje": r.get("mensaje"),
                "fecha": fprog,
                "hora": r.get("hora"),
                "faltan_dias": faltan,
                "estado": r.get("estado") or "PENDIENTE",
                "asignado_a": r.get("asignado_a"),
                "tipo_objetivo": r.get("tipo_objetivo"),
                "animal_tag": r.get("animal_tag"),
                "potrero_nombre": r.get("potrero_nombre"),
                "tipo_tarea": r.get("tipo_tarea"),
                "prioridad": r.get("prioridad") or "NORMAL",
            })
    except Exception as e:
        logger.error("seccion agenda_recordatorios fallo", exc_info=True)
        errores["recordatorios"] = str(e)

    try:
        rows_comp = db.query(
            """SELECT id, mensaje, fecha_programada, hora, estado, creado_por,
                      asignado_a, asignado_a_id, tipo_objetivo, animal_tag, potrero_nombre,
                      tipo_tarea, prioridad, completado_en, completado_por,
                      notas_completado, foto_completado
               FROM recordatorios_programados
               WHERE estado IN ('REALIZADO', 'ENVIADO')
               ORDER BY COALESCE(completado_en, fecha_programada) DESC, id DESC LIMIT 30"""
        )
        for r in _filas_dict(rows_comp):
            recordatorios_completados.append({
                "id": r.get("id"),
                "mensaje": r.get("mensaje"),
                "fecha": str(r.get("fecha_programada") or "")[:10] or None,
                "hora": r.get("hora"),
                "estado": r.get("estado") or "REALIZADO",
                "asignado_a": r.get("asignado_a"),
                "tipo_objetivo": r.get("tipo_objetivo"),
                "animal_tag": r.get("animal_tag"),
                "potrero_nombre": r.get("potrero_nombre"),
                "tipo_tarea": r.get("tipo_tarea"),
                "prioridad": r.get("prioridad") or "NORMAL",
                "completado_en": r.get("completado_en"),
                "completado_por": r.get("completado_por"),
                "notas_completado": r.get("notas_completado"),
                "foto_completado": r.get("foto_completado"),
            })
    except Exception:
        logger.error("seccion agenda_recordatorios_completados fallo", exc_info=True)

    out: dict[str, Any] = {
        "dias": dias,
        "eventos": eventos,
        "retiros": retiros,
        "recordatorios": recordatorios,
        "recordatorios_completados": recordatorios_completados,
    }
    if errores:
        out["errores"] = errores
    return out


def datos_badges(db: Database, dias: int = 7) -> dict:
    """Contadores mínimos para los badges de la navegación PWA.

    Un único endpoint liviano (una llamada por polling en vez de 3) con los
    totales que el mayordomo debe ver sin abrir cada vista:
    - agenda:  alertas PENDIENTES con fecha en [hoy, hoy+dias] + retiros activos
    + recordatorios PENDIENTES vencidos/próximos (misma ventana que la vista)
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
        # Recordatorios de campo pendientes (vencidos + ventana): misma fuente
        # que datos_agenda, sin duplicar lógica de negocio en la PWA.
        try:
            rr = db.query_one(
                "SELECT COUNT(*) n FROM recordatorios_programados "
                "WHERE estado='PENDIENTE' AND (fecha_programada IS NULL OR fecha_programada <= ?)",
                (lim,),
            )
            recs = int(rr["n"]) if rr else 0
        except Exception:
            recs = 0
        agenda = alertas + retiros + recs
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


# ------------------------------------------------------------------ #
# Extracción de Datos Estructurados JSON para Gráficos Vectoriales (PWA)
# ------------------------------------------------------------------ #
def datos_grafico(db: Database, tipo: str, hoy: Optional[date] = None, **kwargs) -> dict[str, Any]:
    """Extrae y estructura los datos para que el cliente PWA dibuje gráficos
    vectoriales interactivos (SVG/HTML) adaptados a los temas CSS sin depender
    de imágenes estáticas del servidor. Mantiene retrocompatibilidad."""
    import statistics
    hoy = hoy or date.today()
    tipo = (tipo or "").strip().lower()

    if tipo == "evolucion":
        meses = kwargs.get("meses", 12)
        periodos = []
        y, m = hoy.year, hoy.month
        for _ in range(meses):
            periodos.append((y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        periodos.reverse()

        nacimientos, muertes_m, compras, ventas, etiquetas = [], [], [], [], []
        meses_es = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        for (yy, mm) in periodos:
            desde = date(yy, mm, 1).isoformat()
            hasta = (date(yy + 1, 1, 1) if mm == 12 else date(yy, mm + 1, 1)).isoformat()
            n_nac = db.query_one(
                "SELECT COUNT(*) AS n FROM partos WHERE fecha >= ? AND fecha < ? AND (id_cria IS NULL OR id_cria != vaca_id)",
                (desde, hasta),
            )["n"]
            n_mue = db.query_one(
                "SELECT COUNT(*) AS n FROM muertes WHERE fecha >= ? AND fecha < ?", (desde, hasta)
            )["n"]
            n_compra = db.query_one(
                "SELECT COUNT(*) AS n FROM movimientos WHERE fecha >= ? AND fecha < ? AND UPPER(tipo_movimiento) IN ('COMPRA', 'ENTRADA')",
                (desde, hasta),
            )["n"]
            n_venta = db.query_one(
                "SELECT COUNT(*) AS n FROM movimientos WHERE fecha >= ? AND fecha < ? AND UPPER(tipo_movimiento) IN ('VENTA', 'SALIDA')",
                (desde, hasta),
            )["n"]
            nacimientos.append(n_nac)
            muertes_m.append(n_mue)
            compras.append(n_compra)
            ventas.append(n_venta)
            etiquetas.append(f"{meses_es[mm]} {yy}")

        activos_hoy = db.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado='ACTIVO'")["n"]
        niveles = [0] * len(periodos)
        niveles[-1] = activos_hoy
        for i in range(len(periodos) - 2, -1, -1):
            delta_sig = nacimientos[i + 1] + compras[i + 1] - muertes_m[i + 1] - ventas[i + 1]
            niveles[i] = niveles[i + 1] - delta_sig

        series = []
        for i in range(len(etiquetas)):
            series.append({
                "mes": etiquetas[i],
                "nacimientos": nacimientos[i],
                "compras": compras[i],
                "ventas": ventas[i],
                "muertes": muertes_m[i],
                "inventario": niveles[i],
            })

        return {
            "ok": True,
            "tipo": "evolucion",
            "titulo": "Evolución del Rebaño",
            "subtitulo": f"{len(etiquetas)} meses · inventario final estimado: {niveles[-1]} animales",
            "series": series,
            "totales": {
                "nacimientos": sum(nacimientos),
                "compras": sum(compras),
                "ventas": sum(ventas),
                "muertes": sum(muertes_m),
                "inventario_final": niveles[-1],
            },
        }

    if tipo in ("reproductivo_hato", "reproductivo"):
        hembras = db.query(
            "SELECT id_animal, fecha_nacimiento FROM animales "
            "WHERE estado = 'ACTIVO' AND LOWER(SUBSTR(sexo, 1, 1)) = 'h'"
        )
        n_prenadas = 0
        n_vacias_servidas = 0
        n_nunca_servidas = 0
        for h in hembras:
            fnac = to_date_safe(h["fecha_nacimiento"])
            if fnac and (hoy - fnac).days < 365:
                continue
            ult_serv = db.ultimo_servicio(h["id_animal"])
            if ult_serv is None:
                n_nunca_servidas += 1
                continue
            parto_post = db.query_one(
                "SELECT 1 FROM partos WHERE vaca_id = ? AND fecha >= ?",
                (h["id_animal"], ult_serv["fecha"]),
            )
            if not parto_post:
                n_prenadas += 1
            else:
                n_vacias_servidas += 1

        expuestas = n_prenadas + n_vacias_servidas
        tasa = (n_prenadas / expuestas * 100) if expuestas > 0 else 0.0
        total_hembras = expuestas + n_nunca_servidas

        return {
            "ok": True,
            "tipo": "reproductivo_hato",
            "titulo": "Estado Reproductivo del Hato",
            "subtitulo": f"{total_hembras} hembras activas ≥1 año · Tasa preñez sobre expuestas: {tasa:.1f}%",
            "total_hembras": total_hembras,
            "expuestas": expuestas,
            "tasa_prenez": round(tasa, 1),
            "categorias": [
                {
                    "nombre": "Preñadas (est.)",
                    "n": n_prenadas,
                    "pct": round(n_prenadas / total_hembras * 100, 1) if total_hembras else 0,
                    "color": "var(--verde-marca)",
                },
                {
                    "nombre": "Vacías (servidas)",
                    "n": n_vacias_servidas,
                    "pct": round(n_vacias_servidas / total_hembras * 100, 1) if total_hembras else 0,
                    "color": "#f9a825",
                },
                {
                    "nombre": "Nunca servidas",
                    "n": n_nunca_servidas,
                    "pct": round(n_nunca_servidas / total_hembras * 100, 1) if total_hembras else 0,
                    "color": "#78909c",
                },
            ],
        }

    if tipo in ("ocupacion", "ocupacion_potreros"):
        from .query.helpers import calcular_existencias_potreros_sg
        grupos = calcular_existencias_potreros_sg(db, hoy)
        items = []
        for g in (grupos or []):
            f_ingreso = g.get("fecha_ingreso_reciente")
            d = (hoy - to_date_safe(f_ingreso)).days if f_ingreso and to_date_safe(f_ingreso) else None
            if d is None:
                continue
            color = "#2e7d32" if d <= 3 else ("#f9a825" if d <= 6 else "#c62828")
            sem = "🟢" if d <= 3 else ("🟡" if d <= 6 else "🔴")
            items.append({
                "nombre": g["display"],
                "dias": d,
                "animales": g.get("total", 0),
                "semaforo": sem,
                "color": color,
            })
        items.sort(key=lambda x: -x["dias"])
        return {
            "ok": True,
            "tipo": "ocupacion",
            "titulo": "Ocupación de Potreros (Rotación Voisin)",
            "subtitulo": f"{len(items)} potrero(s) ocupado(s) · Meta Voisin: ≤3 días",
            "meta_dias": 3,
            "potreros": items,
        }

    if tipo in ("aforo", "aforo_potreros"):
        potreros = db.query(
            "SELECT nombre, codigo, tipo_pasto, aforo_kg_m2 FROM potreros "
            "WHERE aforo_kg_m2 IS NOT NULL ORDER BY aforo_kg_m2 DESC"
        )
        items = []
        for p in (potreros or []):
            val = float(p["aforo_kg_m2"])
            items.append({
                "nombre": (p["nombre"] or p["codigo"] or "?"),
                "aforo_kg_m2": val,
                "tipo_pasto": (p["tipo_pasto"] or "Sin dato"),
            })
        prom = sum(it["aforo_kg_m2"] for it in items) / len(items) if items else 0.0
        return {
            "ok": True,
            "tipo": "aforo",
            "titulo": "Aforo de Forraje por Potrero",
            "subtitulo": f"{len(items)} potrero(s) con aforo registrado · Promedio: {prom:.2f} kg/m²",
            "promedio": round(prom, 2),
            "potreros": items,
        }

    if tipo in ("flujo_caja", "flujo"):
        desde = date(hoy.year, 1, 1).isoformat()
        hasta = date(hoy.year, 12, 31).isoformat()
        filas = db.flujo_caja_mensual(desde, hasta)
        items = []
        for f in (filas or []):
            items.append({
                "mes": f["mes"],
                "ingresos": float(f["ingresos"] or 0),
                "egresos": float(f["egresos"] or 0),
                "utilidad": float(f["utilidad"] or 0),
            })
        total_util = sum(it["utilidad"] for it in items)
        return {
            "ok": True,
            "tipo": "flujo_caja",
            "titulo": "Flujo de Caja Mensual",
            "subtitulo": f"{len(items)} mes(es) · Utilidad total del periodo: ${total_util:,.0f}".replace(",", "."),
            "total_utilidad": total_util,
            "meses": items,
        }

    if tipo in ("waterfall_inventario", "waterfall"):
        meses = kwargs.get("meses", 12)
        evol = datos_grafico(db, "evolucion", hoy, meses=meses)
        series = evol.get("series", [])
        if not series:
            return {"ok": True, "tipo": "waterfall_inventario", "inicio": 0, "actual": 0, "pasos": []}
        deltas = [s["nacimientos"] + s["compras"] - s["muertes"] - s["ventas"] for s in series]
        inicio = series[0]["inventario"] - deltas[0]
        niveles = [inicio] + [s["inventario"] for s in series]

        pasos = [{"etiqueta": "Inicio", "tipo": "base", "valor": inicio, "base": 0}]
        for i, s in enumerate(series):
            pasos.append({
                "etiqueta": s["mes"],
                "tipo": "delta",
                "delta": deltas[i],
                "base": min(niveles[i], niveles[i + 1]),
                "valor": abs(deltas[i]),
                "nuevo": niveles[i + 1],
            })
        pasos.append({"etiqueta": "Actual", "tipo": "base", "valor": niveles[-1], "base": 0})

        return {
            "ok": True,
            "tipo": "waterfall_inventario",
            "titulo": "Waterfall de Inventario Mensual",
            "subtitulo": f"{len(series)} meses · balance neto acumulado",
            "inicio": inicio,
            "actual": niveles[-1],
            "pasos": pasos,
        }

    if tipo in ("gmd_hato", "gmd"):
        animales = db.query(
            "SELECT id_animal, tag, sexo, fecha_nacimiento FROM animales WHERE estado='ACTIVO'"
        )
        puntos_h, puntos_m = [], []
        for a in animales:
            pesajes = db.query(
                "SELECT fecha, peso_kg FROM pesajes WHERE animal_id = ? AND peso_kg IS NOT NULL "
                "ORDER BY fecha DESC LIMIT 2", (a["id_animal"],),
            )
            if len(pesajes) < 2:
                continue
            ultimo, anterior = pesajes[0], pesajes[1]
            f1, f2 = to_date_safe(anterior["fecha"]), to_date_safe(ultimo["fecha"])
            fnac = to_date_safe(a["fecha_nacimiento"])
            if not f1 or not f2 or (f2 - f1).days <= 0 or not fnac:
                continue
            gmd = (float(ultimo["peso_kg"]) - float(anterior["peso_kg"])) / (f2 - f1).days
            edad = (f2 - fnac).days
            sexo = (a["sexo"] or "").strip().lower()
            punto = {"tag": a["tag"], "edad_dias": edad, "gmd": round(gmd, 3)}
            if sexo.startswith("h"):
                puntos_h.append(punto)
            elif sexo.startswith("m"):
                puntos_m.append(punto)

        todos = [p["gmd"] for p in (puntos_h + puntos_m)]
        mediana = statistics.median(todos) if todos else 0.0
        negativos = sum(1 for v in todos if v < 0)

        return {
            "ok": True,
            "tipo": "gmd_hato",
            "titulo": "Ganancia Media Diaria del Hato",
            "subtitulo": f"{len(todos)} animales con 2+ pesajes · Mediana: {mediana:.2f} kg/día",
            "mediana": round(mediana, 2),
            "n_negativos": negativos,
            "hembras": puntos_h,
            "machos": puntos_m,
        }

    if tipo in ("composicion_racial", "razas"):
        NOMBRES_RAZAS = {
            "I": "Holstein / Cruce Lechero",
            "T": "Tricross / Cebú Comercial",
            "C": "Cebú / Brahman / Gyr",
            "M": "Mestizo / Doble Propósito",
            "SIN RAZA": "Sin Clasificar",
        }
        COLORES_RAZAS = {
            "I": "var(--verde-marca)",
            "T": "#66bb6a",
            "C": "#8d6e63",
            "M": "#78909c",
            "SIN RAZA": "#d4a373",
        }
        rows = db.query(
            "SELECT COALESCE(NULLIF(TRIM(raza), ''), 'SIN RAZA') raza, COUNT(*) n "
            "FROM animales WHERE estado = 'ACTIVO' GROUP BY raza ORDER BY n DESC"
        )
        total = sum(int(r["n"]) for r in rows)
        items = []
        for r in rows:
            c = r["raza"]
            n = int(r["n"])
            items.append({
                "codigo": c,
                "nombre": NOMBRES_RAZAS.get(c, c),
                "n": n,
                "pct": round(n / total * 100, 1) if total else 0.0,
                "color": COLORES_RAZAS.get(c, "#52796f"),
            })
        return {
            "ok": True,
            "tipo": "composicion_racial",
            "titulo": "Composición Genética (Razas)",
            "subtitulo": f"{total} animales activos al {hoy.isoformat()}",
            "total": total,
            "items": items,
        }

    if tipo in ("subastas_comparativa", "subastas_tendencia", "subastas"):
        datos = db.obtener_datos_mercado_completos()
        comp = datos.get("comparativa_por_categoria", {}).get("MACHO_GORDO", [])
        prom_nal = next((x["precio_promedio"] for x in comp if x["plaza_key"] == "PROMEDIO_NACIONAL"), None)

        plazas = []
        for it in comp:
            plazas.append({
                "plaza_key": it["plaza_key"],
                "nombre": it["nombre"],
                "distancia": f"{it['distancia_km']}km" if it.get("distancia_km") else "Nacional",
                "precio": it["precio_promedio"],
                "es_local": (it["plaza_key"] == "GRANADA"),
                "es_mejor": it.get("es_mejor_precio", False),
                "tendencia": it.get("tendencia", "ESTABLE"),
                "variacion_pct": it.get("variacion_pct", 0),
            })
        plazas.sort(key=lambda x: x["precio"])
        return {
            "ok": True,
            "tipo": tipo,
            "titulo": "Subastas Ganaderas · Comparativa de Precios ($/kg)",
            "subtitulo": "Macho Gordo en plazas comerciales relevantes",
            "promedio_nacional": prom_nal,
            "plazas": plazas,
        }

    if tipo in ("mapa_potreros", "mapa"):
        potreros = db.query(
            "SELECT id, nombre, codigo, area_has FROM potreros ORDER BY nombre"
        )
        items = []
        for p in (potreros or []):
            nom = p["nombre"] or p["codigo"] or str(p["id"])
            cnt = db.query_one(
                "SELECT COUNT(*) n FROM animales WHERE estado='ACTIVO' AND potrero_id = ?",
                (p["id"],),
            )
            n = int(cnt["n"]) if cnt else 0
            items.append({
                "id": p["id"],
                "nombre": nom,
                "area_has": p["area_has"],
                "animales": n,
                "estado": "Ocupado" if n > 0 else "Reposo",
                "semaforo": "🟢" if n > 0 else "🌱",
            })
        return {
            "ok": True,
            "tipo": "mapa_potreros",
            "titulo": "Mapa y Estado de Potreros",
            "subtitulo": f"{len(items)} potreros registrados en la finca",
            "potreros": items,
        }

    if tipo in ("carga_animal", "carga"):
        from .query.helpers import calcular_existencias_potreros_sg
        grupos = calcular_existencias_potreros_sg(db, hoy)
        items = []
        for g in (grupos or []):
            area = g.get("area_has")
            tot_anim = g.get("total", 0)
            if area and float(area) > 0:
                carga = tot_anim / float(area)
                items.append({
                    "nombre": g["display"],
                    "carga_ugg_ha": round(carga, 2),
                    "animales": tot_anim,
                    "area_has": area,
                })
        items.sort(key=lambda x: -x["carga_ugg_ha"])
        return {
            "ok": True,
            "tipo": "carga_animal",
            "titulo": "Carga Animal por Potrero (Cab/ha)",
            "subtitulo": f"{len(items)} potreros con área registrada",
            "potreros": items,
        }

    return {
        "ok": False,
        "tipo": tipo,
        "error": f"Tipo de gráfico '{tipo}' no soportado para datos estructurados.",
    }


