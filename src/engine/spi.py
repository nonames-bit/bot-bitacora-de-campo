"""Índice de Precipitación Estandarizada (SPI) — McKee, Doesken & Kleist (1993).

Compara la lluvia acumulada actual contra su propia climatología histórica
(no contra un umbral fijo): se ajusta una distribución gamma a la muestra de
años anteriores para la misma ventana de días, se ubica el valor actual
dentro de esa distribución, y se convierte a un z-score de la normal
estándar. Es el mismo método que usan los boletines oficiales de sequía.

Este módulo es matemática pura (solo necesita la muestra histórica ya
descargada, no toca Earth Engine ni la base de datos) para que sea testeable
sin red ni credenciales -- ver ``src.gis.earth_engine_lluvia.
climatologia_historica_chirps`` para cómo se obtiene esa muestra.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("bitacora.engine.spi")

MUESTRA_MINIMA = 10  # McKee recomienda 30+ años; bajo esto el ajuste no es confiable.

# (límite inferior inclusive, límite superior exclusivo, nombre) — McKee et al. 1993.
_CLASIFICACION_SPI = (
    (2.0, float("inf"), "Extremadamente húmedo"),
    (1.5, 2.0, "Muy húmedo"),
    (1.0, 1.5, "Moderadamente húmedo"),
    (-1.0, 1.0, "Normal"),
    (-1.5, -1.0, "Sequía moderada"),
    (-2.0, -1.5, "Sequía severa"),
    (float("-inf"), -2.0, "Sequía extrema"),
)


def clasificar_spi(valor: float) -> str:
    """Etiqueta McKee et al. 1993 para un valor de SPI ya calculado."""
    for lo, hi, nombre in _CLASIFICACION_SPI:
        if lo <= valor < hi:
            return nombre
    return "Normal"


def calcular_spi(valor_actual: float, muestra_historica: list[float]) -> Optional[float]:
    """SPI de `valor_actual` (mm acumulados) contra `muestra_historica`
    (mm acumulados de la misma ventana en años anteriores).

    Devuelve `None` si no hay muestra suficiente (`MUESTRA_MINIMA`) o si
    scipy no está disponible -- nunca lanza, para que una climatología
    incompleta no tumbe el resto del reporte de pasturas."""
    muestra = [m for m in (muestra_historica or []) if m is not None]
    n = len(muestra)
    if n < MUESTRA_MINIMA:
        return None

    try:
        from scipy import stats
    except ImportError:
        logger.warning("scipy no disponible; no se puede calcular SPI")
        return None

    positivos = [m for m in muestra if m > 0]
    if len(positivos) < 5:
        # Casi toda la muestra es cero (zona muy árida o ventana muy corta):
        # el ajuste gamma no es confiable con tan pocos valores positivos.
        return None

    prob_cero = (n - len(positivos)) / n

    if valor_actual <= 0:
        prob_acumulada = prob_cero
    else:
        try:
            forma, _loc, escala = stats.gamma.fit(positivos, floc=0)
            prob_acumulada = prob_cero + (1 - prob_cero) * stats.gamma.cdf(valor_actual, forma, loc=0, scale=escala)
        except Exception as e:
            logger.warning("calcular_spi: fallo el ajuste gamma: %s", e)
            return None

    # Evita 0/1 exactos, que llevarían a +/-infinito en la inversa normal.
    prob_acumulada = min(max(prob_acumulada, 1e-6), 1 - 1e-6)
    return round(float(stats.norm.ppf(prob_acumulada)), 2)
