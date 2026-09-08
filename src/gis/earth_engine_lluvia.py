"""Pipeline de lluvia satelital de referencia vía Google Earth Engine (CHIRPS).

Fase D del plan geoespacial (ver docs/PLAN_GEO_SATELITAL_6.2_8.2.md): un dato
de *contraste*, no de reemplazo, del pluviómetro físico registrado a mano con
`/lluvia` (tabla `pluviometria`). CHIRPS tiene resolución ~5.5 km, así que no
distingue microclima entre sectores de una sola finca — se calcula un único
valor a nivel de finca completa, centrado en el centroide promedio de los
potreros con geometría real (Fase B). Reutiliza la misma autenticación de
Earth Engine que el pipeline de NDVI (Fase C, `earth_engine_ndvi.py`).

**Hallazgo clave (probado en vivo, 2026-09-03):** a diferencia de Sentinel-2,
la colección `UCSB-CHG/CHIRPS/DAILY` de Earth Engine tiene una latencia real
de ~30-45 días — la imagen más reciente disponible NO es "hoy menos unos
días", sino que puede estar a más de un mes de la fecha de corrida del job.
Por eso este módulo primero busca la fecha más reciente con dato disponible
(`_fecha_mas_reciente_disponible`, ventana de búsqueda amplia) y acumula los
`dias_ventana` días terminando ahí — no asume que "hoy" tiene cobertura.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from . import earth_engine_ndvi as _gee_ndvi
from .earth_engine_ndvi import inicializar_ee

logger = logging.getLogger("bitacora.gis.earth_engine_lluvia")

# Radio del punto-buffer usado como AOI: la mitad de la resolución nativa de
# CHIRPS (~5566 m), suficiente para cubrir la finca completa (~243 ha) sin
# necesidad de construir la unión de los polígonos de los 20 potreros.
_RADIO_AOI_M = 2750

# CHIRPS puede tardar semanas en publicar su dato más reciente en el catálogo
# de Earth Engine; se busca hacia atrás hasta este límite antes de rendirse.
_DIAS_BUSQUEDA_MAX = 75


def _fecha_mas_reciente_disponible(geom, fecha_limite: date, dias_busqueda_max: int) -> Optional[date]:
    """Devuelve la fecha de la imagen CHIRPS más reciente disponible sobre `geom`.

    Busca en una ventana amplia hacia atrás desde `fecha_limite` porque CHIRPS
    no publica datos en tiempo real (ver nota de latencia en el docstring del
    módulo). Devuelve `None` si no hay ninguna imagen en esa ventana.
    """
    import ee

    fecha_ini = (fecha_limite - timedelta(days=dias_busqueda_max)).isoformat()
    coleccion = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterBounds(geom)
        .filterDate(fecha_ini, fecha_limite.isoformat())
        .sort("system:time_start", False)
    )

    if coleccion.size().getInfo() == 0:
        return None

    ultima = ee.Image(coleccion.first())
    fecha_str = ee.Date(ultima.get("system:time_start")).format("YYYY-MM-dd").getInfo()
    return date.fromisoformat(fecha_str)


def _lluvia_acumulada_chirps(
    lat: float,
    lon: float,
    fecha_fin: date,
    dias_ventana: int = 30,
    radio_m: int = _RADIO_AOI_M,
    dias_busqueda_max: int = _DIAS_BUSQUEDA_MAX,
) -> Optional[tuple[float, date]]:
    """Suma la precipitación diaria de CHIRPS en una ventana de `dias_ventana` días,
    terminando en la fecha más reciente con dato disponible (no necesariamente `fecha_fin`).

    Devuelve `(mm_acumulados, fecha_real_fin)` o `None` si no hay cobertura CHIRPS
    en absoluto dentro de `dias_busqueda_max` días antes de `fecha_fin`.
    """
    import ee

    geom = ee.Geometry.Point([lon, lat]).buffer(radio_m)

    fecha_real_fin = _fecha_mas_reciente_disponible(geom, fecha_fin, dias_busqueda_max)
    if fecha_real_fin is None:
        return None

    fecha_ini = (fecha_real_fin - timedelta(days=dias_ventana)).isoformat()
    coleccion = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterBounds(geom)
        .filterDate(fecha_ini, (fecha_real_fin + timedelta(days=1)).isoformat())
    )

    acumulado = coleccion.select("precipitation").sum()
    stats = acumulado.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=5566,
        maxPixels=1e9,
        bestEffort=True,
    ).getInfo()

    mm = stats.get("precipitation")
    if mm is None:
        return None
    return round(mm, 1), fecha_real_fin


def estimar_lluvia_finca(
    lat: float,
    lon: float,
    fecha_fin: Optional[date] = None,
    dias_ventana: int = 30,
) -> Optional[dict]:
    """Estima la lluvia acumulada de la finca en `dias_ventana` días vía CHIRPS.

    `lat`/`lon`: centroide de referencia de la finca (promedio de los
    centroides de los potreros con geometría real). `fecha_fin` es el límite
    superior de búsqueda (por defecto hoy), no necesariamente la fecha real
    del dato: CHIRPS tiene latencia propia, así que el resultado refleja la
    ventana más reciente que el catálogo realmente tiene disponible. Devuelve
    `None` si no hay ninguna imagen CHIRPS en absoluto para esa zona.
    """
    if not _gee_ndvi._inicializado:
        inicializar_ee()

    fecha_ref = fecha_fin or date.today()

    try:
        resultado = _lluvia_acumulada_chirps(lat, lon, fecha_ref, dias_ventana)
    except Exception as e:
        logger.error("Error consultando CHIRPS vía Earth Engine: %s", e, exc_info=True)
        return None

    if resultado is None:
        logger.warning(
            "Sin cobertura CHIRPS en absoluto para la zona (buscando hasta %s días antes de %s)",
            _DIAS_BUSQUEDA_MAX, fecha_ref,
        )
        return None

    mm, fecha_real_fin = resultado
    return {
        "mm_estimado": mm,
        "dias_acumulados": dias_ventana,
        "fecha_fin": fecha_real_fin.isoformat(),
        "fuente": "CHIRPS (UCSB-CHG, vía Google Earth Engine)",
    }


def _lluvia_acumulada_periodo(
    lat: float, lon: float, fecha_ini: date, fecha_fin: date, radio_m: int = _RADIO_AOI_M,
) -> Optional[float]:
    """Suma la precipitación CHIRPS entre `fecha_ini` y `fecha_fin` (ambas
    inclusive), sin buscar "la fecha más reciente disponible" -- a diferencia
    de ``_lluvia_acumulada_chirps``, aquí el rango ya es histórico (años
    atrás) y se asume que CHIRPS sí tiene cobertura completa. Usado para
    construir la climatología del SPI, no para la lectura semanal actual."""
    import ee

    geom = ee.Geometry.Point([lon, lat]).buffer(radio_m)
    coleccion = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterBounds(geom)
        .filterDate(fecha_ini.isoformat(), (fecha_fin + timedelta(days=1)).isoformat())
    )
    acumulado = coleccion.select("precipitation").sum()
    stats = acumulado.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geom, scale=5566, maxPixels=1e9, bestEffort=True,
    ).getInfo()
    mm = stats.get("precipitation")
    return None if mm is None else round(mm, 1)


def climatologia_historica_chirps(
    lat: float,
    lon: float,
    dias_ventana: int,
    fecha_referencia: Optional[date] = None,
    anos_historicos: int = 30,
    radio_m: int = _RADIO_AOI_M,
) -> list[float]:
    """Lluvia acumulada de `dias_ventana` días en cada uno de los
    `anos_historicos` años anteriores, terminando en el mismo día-del-año que
    `fecha_referencia` (o hoy). CHIRPS cubre desde 1981, así que 30 años de
    climatología son un rango realista. Es la muestra que ``engine.spi``
    necesita para ajustar la distribución gamma del SPI -- sin esto, "SPI"
    sería solo un nombre para comparar contra la nada.

    Nunca lanza: un año sin cobertura se omite de la muestra en vez de
    abortar toda la climatología por un solo hueco de datos."""
    if not _gee_ndvi._inicializado:
        inicializar_ee()

    fecha_ref = fecha_referencia or date.today()
    muestras: list[float] = []
    for i in range(1, anos_historicos + 1):
        try:
            fin = fecha_ref.replace(year=fecha_ref.year - i)
        except ValueError:  # 29 de febrero sin año bisiesto equivalente
            fin = fecha_ref.replace(year=fecha_ref.year - i, day=28)
        ini = fin - timedelta(days=dias_ventana)
        try:
            mm = _lluvia_acumulada_periodo(lat, lon, ini, fin, radio_m)
        except Exception as e:
            logger.warning("climatologia_historica_chirps: fallo año %s: %s", fin.year, e)
            mm = None
        if mm is not None:
            muestras.append(mm)
    return muestras
