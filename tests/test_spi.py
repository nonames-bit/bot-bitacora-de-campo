"""Pruebas del Índice de Precipitación Estandarizada (SPI).

Matemática pura: sin Earth Engine, sin base de datos. Usa muestras
sintéticas donde se conoce el resultado esperado (sequía/normal/húmedo).
"""
from __future__ import annotations

import random

import pytest

from src.engine.spi import calcular_spi, clasificar_spi

pytest.importorskip("scipy", reason="scipy no está instalado en este entorno")


def _muestra_normal(media: float, dispersion: float, n: int = 30, semilla: int = 42) -> list[float]:
    """Muestra sintética de lluvias anuales alrededor de `media` (nunca negativa)."""
    rnd = random.Random(semilla)
    return [max(0.0, round(rnd.gauss(media, dispersion), 1)) for _ in range(n)]


def test_clasificar_spi_normal():
    assert clasificar_spi(0.0) == "Normal"
    assert clasificar_spi(0.99) == "Normal"
    assert clasificar_spi(-0.99) == "Normal"


def test_clasificar_spi_sequia_moderada():
    assert clasificar_spi(-1.2) == "Sequía moderada"


def test_clasificar_spi_sequia_severa():
    assert clasificar_spi(-1.8) == "Sequía severa"


def test_clasificar_spi_sequia_extrema():
    assert clasificar_spi(-2.5) == "Sequía extrema"


def test_clasificar_spi_humedo():
    assert clasificar_spi(1.2) == "Moderadamente húmedo"
    assert clasificar_spi(1.7) == "Muy húmedo"
    assert clasificar_spi(2.5) == "Extremadamente húmedo"


def test_calcular_spi_valor_bajo_da_sequia():
    """Lluvia muy por debajo de lo histórico -> SPI negativo, sequía."""
    muestra = _muestra_normal(media=80.0, dispersion=20.0, n=30)
    spi = calcular_spi(5.0, muestra)
    assert spi is not None
    assert spi < -1.0
    assert clasificar_spi(spi) in ("Sequía moderada", "Sequía severa", "Sequía extrema")


def test_calcular_spi_valor_cercano_al_promedio_da_normal():
    muestra = _muestra_normal(media=80.0, dispersion=20.0, n=30)
    media = sum(muestra) / len(muestra)
    spi = calcular_spi(media, muestra)
    assert spi is not None
    assert -1.0 <= spi <= 1.0


def test_calcular_spi_valor_alto_da_humedo():
    muestra = _muestra_normal(media=80.0, dispersion=20.0, n=30)
    spi = calcular_spi(250.0, muestra)
    assert spi is not None
    assert spi > 1.0


def test_calcular_spi_muestra_insuficiente_devuelve_none():
    assert calcular_spi(50.0, [10.0, 20.0, 30.0]) is None


def test_calcular_spi_muestra_vacia_devuelve_none():
    assert calcular_spi(50.0, []) is None


def test_calcular_spi_muestra_none_devuelve_none():
    assert calcular_spi(50.0, None) is None


def test_calcular_spi_valor_actual_cero():
    """Un valor actual de 0 mm no debe romper el cálculo (zona con lluvia
    real de cero en algún año de la muestra)."""
    muestra = _muestra_normal(media=80.0, dispersion=20.0, n=30) + [0.0, 0.0]
    spi = calcular_spi(0.0, muestra)
    assert spi is not None
    assert spi < 0


def test_calcular_spi_muestra_casi_toda_cero_devuelve_none():
    """Zona casi siempre seca (pocos valores positivos): no se puede ajustar
    una gamma confiable, mejor devolver None que un número engañoso."""
    muestra = [0.0] * 25 + [1.0, 2.0]
    assert calcular_spi(5.0, muestra) is None
