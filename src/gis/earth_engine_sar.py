"""Pipeline de monitoreo por Radar SAR (Sentinel-1 C-Band GRD) vía Google Earth Engine.

Monitoreo de biomasa forrajera y humedad de suelo que opera bajo cualquier condición
atmosférica (lluvias intensas, nubes densas, neblina y noche). Resuelve la limitación
del NDVI óptico (Sentinel-2) durante la temporada de lluvias en los Llanos Orientales
(Mesetas, Meta), garantizando continuidad temporal 365 días al año.

Utiliza la colección COPERNICUS/S1_GRD con polarizaciones duales (VV y VH) en modo IW
(Interferometric Wide Swath) a 10m de resolución espacial.

Fórmulas biofísicas de microondas:
  1. Conversión de decibeles (dB) a potencia lineal:
       σ°_lin = 10^(σ°_dB / 10)
  2. Dual-Pol Radar Vegetation Index (RVI, Mandal et al., 2020):
       RVI = (4 * VH_lin) / (VV_lin + VH_lin)
       Rango típico: 0.10 - 0.25 (suelo desnudo / sobrepastoreo severo),
                     0.25 - 0.50 (pastura en rebrote / baja biomasa),
                     0.50 - 0.85+ (pastura vigorosa / alta biomasa en reposo).
  3. Relación cruzada de polarización (Cross-Ratio CR):
       CR_dB = VH_dB - VV_dB
  4. Proxy SAR-NDVI (NDVI equivalente estimado por radar):
       NDVI_radar = clip(0.40 + 0.17 * RVI, 0.10, 0.88)

       Calibrado por regresión lineal (mínimos cuadrados) contra NDVI óptico
       REAL de Sentinel-2 en los 20 potreros con geometría de la finca
       (2026-09-08, imágenes despejadas 2026-08-25/2026-09-04; RVI observado
       0.80-1.01, NDVI real 0.42-0.63). La fórmula anterior (0.20 + 0.65*RVI,
       sin respaldo empírico) sobreestimaba sistemáticamente ~0.15-0.30
       puntos de NDVI y, al truncar RVI en min(1.0, RVI), aplanaba a todos
       los potreros con vegetación densa en el mismo valor techo (0.85) --
       el mapa mostraba "EXCELENTE" parejo aunque hubiera diferencias reales
       entre potreros. Ver scripts/diag_calibracion_sar.py para repetir el
       ajuste cuando haya más muestras (sobre todo de pastura degradada/RVI
       bajo, fuera del rango 0.80-1.01 cubierto por esta calibración).
  5. Proxy de humedad de suelo / forraje (sensibilidad dieléctrica de banda C en VV):
       humedad_pct = clip(((VV_dB - (-18.0)) / ((-7.0) - (-18.0))) * 100.0, 0.0, 100.0)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

from .earth_engine_ndvi import _wkt_a_geojson_geom, inicializar_ee

logger = logging.getLogger("bitacora.gis.earth_engine_sar")


def estimar_humedad_sar(vv_db: float) -> tuple[float, str]:
    """Estima el nivel de humedad superficial del suelo y pastura a partir de VV en dB.

    La constante dieléctrica del agua incrementa la retrodispersión VV de ~ -18 dB
    (suelo seco) a ~ -7 dB (suelo encharcado o saturado por lluvia).
    """
    pct = max(0.0, min(100.0, ((vv_db - (-18.0)) / ((-7.0) - (-18.0))) * 100.0))
    pct_redondeado = round(pct, 1)
    if pct >= 75.0:
        desc = "Suelo muy húmedo / saturado (lluvia reciente)"
    elif pct >= 45.0:
        desc = "Humedad favorable en suelo y pastura"
    elif pct >= 25.0:
        desc = "Humedad moderada"
    else:
        desc = "Suelo seco / déficit hídrico"
    return pct_redondeado, desc


def calcular_sar_ndvi(rvi: float) -> float:
    """Calcula el proxy SAR-NDVI a partir del Dual-Pol Radar Vegetation Index (RVI).

    Regresión lineal ajustada contra NDVI óptico real de Sentinel-2 (ver
    módulo, sección 4) -- NO es una fórmula estándar de la literatura, es una
    calibración empírica de esta finca. La fórmula anterior (0.20 + 0.65*RVI,
    sin validar) truncaba RVI en 1.0 antes de escalarlo, así que cualquier
    potrero con vegetación densa (RVI real observado hasta 1.01) caía en el
    mismo valor techo -- el mapa no podía distinguir "bueno" de "muy bueno"
    entre potreros, aunque el NDVI óptico real sí variaba entre ellos.
    """
    rvi_clamped = max(0.0, min(3.0, float(rvi)))
    ndvi = 0.40 + 0.17 * rvi_clamped
    return round(max(0.10, min(0.88, ndvi)), 3)


def _sar_region_sentinel1(
    geom_wkt: str,
    fecha_fin: date,
    dias_ventana: int = 45,
) -> Optional[dict[str, Any]]:
    """Consulta la adquisición Sentinel-1 GRD más reciente sobre el polígono y calcula índices SAR.

    Como el radar penetra nubes, lluvia y neblina, no se descartan imágenes por
    nubosidad. Devuelve los estadísticos de retrodispersión y el proxy de biomasa.
    """
    import ee

    geom = ee.Geometry(_wkt_a_geojson_geom(geom_wkt))
    fecha_ini = (fecha_fin - timedelta(days=dias_ventana)).isoformat()

    coleccion = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(geom)
        .filterDate(fecha_ini, fecha_fin.isoformat())
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .sort("system:time_start", False)
    )

    total = coleccion.size().getInfo()
    if total == 0:
        return None

    imagenes = coleccion.toList(total)

    for i in range(total):
        imagen = ee.Image(imagenes.get(i))
        vv = imagen.select("VV")
        vh = imagen.select("VH")

        # Conversión dB a escala lineal: 10^(dB / 10)
        vv_lin = ee.Image(10.0).pow(vv.divide(10.0))
        vh_lin = ee.Image(10.0).pow(vh.divide(10.0))

        # Dual-Pol RVI = (4 * VH_lin) / (VV_lin + VH_lin)
        rvi = vh_lin.multiply(4.0).divide(vv_lin.add(vh_lin)).rename("RVI")
        cr = vh.subtract(vv).rename("CR")

        combined = ee.Image.cat([vv, vh, rvi, cr])
        stats = combined.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=10,
            maxPixels=1e9,
            bestEffort=True,
        ).getInfo()

        if stats.get("RVI") is None or stats.get("VV") is None:
            continue

        vv_val = float(stats["VV"])
        vh_val = float(stats["VH"])
        rvi_val = float(stats["RVI"])
        cr_val = float(stats.get("CR", vh_val - vv_val))

        ndvi_proxy = calcular_sar_ndvi(rvi_val)
        humedad_pct, humedad_desc = estimar_humedad_sar(vv_val)
        fecha_img = ee.Date(imagen.get("system:time_start")).format("YYYY-MM-dd").getInfo()

        try:
            orbit_pass = str(imagen.get("orbitProperties_pass").getInfo() or "UNKNOWN")
        except Exception:
            orbit_pass = "UNKNOWN"

        return {
            "rvi": round(rvi_val, 3),
            "ndvi_promedio": ndvi_proxy,
            "ndvi_min": max(0.10, round(ndvi_proxy - 0.04, 3)),
            "ndvi_max": min(0.88, round(ndvi_proxy + 0.04, 3)),
            "vv_db": round(vv_val, 2),
            "vh_db": round(vh_val, 2),
            "cr_db": round(cr_val, 2),
            "humedad_pct": humedad_pct,
            "humedad_desc": humedad_desc,
            "orbit_pass": orbit_pass,
            "cobertura_nubes_pct": 0.0,  # 100% libre de nubes gracias a la penetración de microondas SAR
            "fecha_imagen": fecha_img,
        }

    return None


def actualizar_lecturas_sar(
    potreros: list[dict],
    fecha: Optional[date] = None,
    dias_ventana: int = 45,
) -> list[dict]:
    """Genera lecturas satelitales basadas en radar SAR Sentinel-1 para potreros con geometría.

    Formato totalmente compatible con `Database.registrar_lectura_ndvi` y
    con las vistas del bot (`/ndvi`, `/aforo`, `/balance_forrajero`) y la PWA.
    """
    from .sentinel_ndvi import clasificar_ndvi, estimar_aforo_kg_m2_desde_ndvi, estimar_biomasa_ms_ha

    inicializar_ee()
    fecha_ref = fecha or date.today()
    resultados = []

    for p in potreros:
        geom_wkt = p.get("geom_wkt_4326")
        if not geom_wkt:
            continue

        try:
            stats = _sar_region_sentinel1(geom_wkt, fecha_ref, dias_ventana=dias_ventana)
        except Exception as e:
            logger.error(
                "Error consultando Sentinel-1 SAR para potrero %s: %s",
                p.get("nombre"), e, exc_info=True
            )
            continue

        if not stats:
            logger.warning(
                "Sin adquisición Sentinel-1 reciente para potrero %s en ventana de %d días",
                p.get("nombre"), dias_ventana
            )
            continue

        ndvi_val = stats["ndvi_promedio"]
        cls_info = clasificar_ndvi(ndvi_val)

        resultados.append({
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
            "cobertura_nubes_pct": 0.0,
            "fuente": "Sentinel-1 SAR GRD (Radar C-band, vía Google Earth Engine)",
            "sensor": "SAR_SENTINEL1",
            "rvi": stats["rvi"],
            "vv_db": stats["vv_db"],
            "vh_db": stats["vh_db"],
            "cr_db": stats["cr_db"],
            "humedad_pct": stats["humedad_pct"],
            "humedad_desc": stats["humedad_desc"],
            "orbit_pass": stats["orbit_pass"],
        })

    return resultados
