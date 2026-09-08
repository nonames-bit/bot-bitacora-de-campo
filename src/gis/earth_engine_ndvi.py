"""Pipeline de NDVI real vía Google Earth Engine (Sentinel-2 L2A).

Reemplaza la simulación de `sentinel_ndvi.SentinelNDVI.simular_lecturas_potreros`
por una consulta satelital real, usando los polígonos WGS84 ya guardados en
`potreros.geom_wkt_4326` (Fase B del plan geoespacial, ver
docs/PLAN_GEO_SATELITAL_6.2_8.2.md). El resultado se persiste en
`monitoreo_satelital_ndvi` vía `Database.registrar_lectura_ndvi`; no se calcula
al vuelo en el chat — corre como job programado (ver scripts/actualizar_ndvi_satelital.py).
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger("bitacora.gis.earth_engine")

_inicializado = False


try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def inicializar_ee(
    service_account_email: Optional[str] = None,
    key_path: Optional[str] = None,
    project_id: Optional[str] = None,
) -> None:
    """Autentica e inicializa la sesión de Earth Engine con una cuenta de servicio."""
    global _inicializado
    import ee

    email = service_account_email or os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")
    key = key_path or os.getenv("GEE_SERVICE_ACCOUNT_KEY_PATH")
    project = project_id or os.getenv("GEE_PROJECT_ID")

    if not email or not key:
        raise RuntimeError(
            "Faltan credenciales de Earth Engine: define GEE_SERVICE_ACCOUNT_EMAIL "
            "y GEE_SERVICE_ACCOUNT_KEY_PATH en .env (ver docs/PLAN_GEO_SATELITAL_6.2_8.2.md)"
        )
    if not os.path.isfile(key):
        raise RuntimeError(f"No existe el archivo de credenciales de Earth Engine: {key}")

    credenciales = ee.ServiceAccountCredentials(email, key)
    ee.Initialize(credenciales, project=project)
    _inicializado = True


def _wkt_a_geojson_geom(wkt: str) -> dict:
    from shapely import wkt as shapely_wkt
    from shapely.geometry import mapping

    return mapping(shapely_wkt.loads(wkt))


# Clases de la banda SCL (Scene Classification Layer) de Sentinel-2 L2A que se
# consideran "limpias" para NDVI de pastura: 4=vegetación, 5=suelo desnudo,
# 6=agua, 7=no clasificado, 11=nieve/hielo. Se excluyen nubes, sombra de nube,
# cirros y píxeles saturados/defectuosos.
_CLASES_SCL_VALIDAS = (4, 5, 6, 7, 11)


def _ndvi_region_sentinel2(
    geom_wkt: str,
    fecha_fin: date,
    dias_ventana: int = 45,
    fraccion_valida_min: float = 0.6,
) -> Optional[dict]:
    """Busca la imagen Sentinel-2 más reciente con cobertura útil sobre un polígono y calcula su NDVI.

    A diferencia de filtrar por `CLOUDY_PIXEL_PERCENTAGE` (metadato de la escena
    completa, ~110x110 km), evalúa la nubosidad píxel a píxel con la banda SCL
    directamente sobre el polígono del potrero — necesario porque los potreros
    son pequeños (~1-50 ha) y en clima tropical (Meta, Colombia) es común que
    una escena mayormente nublada tenga, aun así, el potrero despejado, o
    viceversa. Recorre las imágenes de la ventana de la más reciente a la más
    antigua y devuelve la primera con al menos `fraccion_valida_min` de píxeles
    limpios sobre el AOI. Devuelve None si ninguna imagen de la ventana alcanza
    ese umbral (ventana muy nublada / sin revisita reciente).
    """
    import ee

    geom = ee.Geometry(_wkt_a_geojson_geom(geom_wkt))
    fecha_ini = (fecha_fin - timedelta(days=dias_ventana)).isoformat()

    coleccion = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(fecha_ini, fecha_fin.isoformat())
        .sort("system:time_start", False)
    )

    total = coleccion.size().getInfo()
    if total == 0:
        return None

    imagenes = coleccion.toList(total)

    for i in range(total):
        imagen = ee.Image(imagenes.get(i))
        scl = imagen.select("SCL")
        mascara_valida = scl.eq(_CLASES_SCL_VALIDAS[0])
        for clase in _CLASES_SCL_VALIDAS[1:]:
            mascara_valida = mascara_valida.Or(scl.eq(clase))

        frac_info = mascara_valida.rename("frac").reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=20,
            maxPixels=1e9,
            bestEffort=True,
        ).getInfo()
        fraccion_valida = frac_info.get("frac")

        if fraccion_valida is None or fraccion_valida < fraccion_valida_min:
            continue

        ndvi_img = imagen.normalizedDifference(["B8", "B4"]).updateMask(mascara_valida).rename("NDVI")
        stats = ndvi_img.reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True),
            geometry=geom,
            scale=10,
            maxPixels=1e9,
            bestEffort=True,
        ).getInfo()

        if stats.get("NDVI_mean") is None:
            continue

        fecha_img = ee.Date(imagen.get("system:time_start")).format("YYYY-MM-dd").getInfo()

        return {
            "ndvi_promedio": round(stats["NDVI_mean"], 3),
            "ndvi_min": round(stats.get("NDVI_min", stats["NDVI_mean"]), 3),
            "ndvi_max": round(stats.get("NDVI_max", stats["NDVI_mean"]), 3),
            "cobertura_nubes_pct": round(100.0 * (1.0 - fraccion_valida), 1),
            "fecha_imagen": fecha_img,
        }

    return None


def actualizar_lecturas_reales(
    potreros: list[dict],
    fecha: Optional[date] = None,
    modo: str = "auto",
) -> list[dict]:
    """Consulta Earth Engine para cada potrero con `geom_wkt_4326` y arma lecturas reales.

    Parámetros:
      potreros: lista de dicts con al menos `id`, `nombre`, `area_has`, `geom_wkt_4326`.
      fecha: fecha de referencia (default: hoy).
      modo:
        - "auto" (default): Intenta Sentinel-2 óptico; si el potrero está cubierto
          por nubes o sin revisita útil, recurre automáticamente al radar SAR
          Sentinel-1 (todo clima, penetra nubes) para garantizar continuidad temporal.
        - "s2": Solo Sentinel-2 óptico (omite potreros nublados).
        - "s1" o "radar": Solo radar SAR Sentinel-1 (independiente de nubes).
    """
    from .sentinel_ndvi import clasificar_ndvi, estimar_aforo_kg_m2_desde_ndvi, estimar_biomasa_ms_ha

    if modo in ("s1", "radar"):
        from .earth_engine_sar import actualizar_lecturas_sar
        return actualizar_lecturas_sar(potreros, fecha=fecha)

    if not _inicializado:
        inicializar_ee()

    fecha_ref = fecha or date.today()
    resultados = []

    for p in potreros:
        geom_wkt = p.get("geom_wkt_4326")
        if not geom_wkt:
            continue

        stats = None
        fuente = "Sentinel-2 L2A (Copernicus, vía Google Earth Engine)"
        sensor = "OPTICO_SENTINEL2"
        detalles_radar = {}

        try:
            stats = _ndvi_region_sentinel2(geom_wkt, fecha_ref)
        except Exception as e:
            logger.error(
                "Error consultando Sentinel-2 óptico para potrero %s: %s", p.get("nombre"), e, exc_info=True
            )

        # Si no hay imagen óptica limpia y modo es "auto", recurrir a Sentinel-1 SAR
        if not stats and modo in ("auto", "fusion"):
            try:
                from .earth_engine_sar import _sar_region_sentinel1
                sar_stats = _sar_region_sentinel1(geom_wkt, fecha_ref)
                if sar_stats:
                    logger.info(
                        "Potrero %s cubierto de nubes en Sentinel-2; usando radar SAR Sentinel-1 como respaldo todo clima.",
                        p.get("nombre"),
                    )
                    stats = sar_stats
                    fuente = "Sentinel-1 SAR GRD (Radar C-band, vía Google Earth Engine)"
                    sensor = "SAR_SENTINEL1"
                    detalles_radar = {
                        "rvi": sar_stats.get("rvi"),
                        "vv_db": sar_stats.get("vv_db"),
                        "vh_db": sar_stats.get("vh_db"),
                        "cr_db": sar_stats.get("cr_db"),
                        "humedad_pct": sar_stats.get("humedad_pct"),
                        "humedad_desc": sar_stats.get("humedad_desc"),
                        "orbit_pass": sar_stats.get("orbit_pass"),
                    }
            except Exception as e:
                logger.error(
                    "Error en respaldo Sentinel-1 SAR para potrero %s: %s", p.get("nombre"), e, exc_info=True
                )

        if not stats:
            logger.warning(
                "Sin imagen satelital reciente para potrero %s (óptica bloqueada por nubes y radar sin adquisición)", p.get("nombre")
            )
            continue

        ndvi_val = stats["ndvi_promedio"]
        cls_info = clasificar_ndvi(ndvi_val)

        item = {
            "potrero_id": p.get("id"),
            "potrero_nombre": p.get("nombre") or f"Potrero {p.get('id')}",
            "area_has": p.get("area_has") or 5.0,
            "fecha": stats["fecha_imagen"],
            "ndvi_promedio": ndvi_val,
            "ndvi_min": stats["ndvi_min"],
            "ndvi_max": stats["ndvi_max"],
            "aforo_estimado_kg_m2": estimar_aforo_kg_m2_desde_ndvi(ndvi_val),
            "biomasa_estimada_kg_ha": estimar_biomasa_ms_ha(ndvi_val),
            "categoria": cls_info["categoria"],
            "emoji": cls_info["emoji"],
            "alerta": cls_info["alerta"],
            "cobertura_nubes_pct": stats.get("cobertura_nubes_pct", 0.0),
            "fuente": fuente,
            "sensor": sensor,
        }
        if detalles_radar:
            item.update(detalles_radar)
        resultados.append(item)

    return resultados
