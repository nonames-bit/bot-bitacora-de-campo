"""Pruebas del motor de pasturas (aforo, MS, carga UGG, ocupación Voisin)."""
import pytest

from src.engine.pasture_engine import (
    PastureEngine, capacidad_carga_ugg, dias_ocupacion, kg_ms_disponibles,
    kg_ms_ha, kg_mv_ha, ugg_de_peso,
)


def test_kg_mv_ha():
    assert kg_mv_ha(0.5) == 5000.0


def test_kg_ms_ha():
    assert kg_ms_ha(5000.0, 22.0) == pytest.approx(1100.0)


def test_kg_ms_disponibles():
    assert kg_ms_disponibles(0.5, 10.0, 22.0) == pytest.approx(11000.0)


def test_capacidad_carga_ugg():
    # 11000 kg MS / 12 kg MS por UGG-día = 916.67 UGG
    assert capacidad_carga_ugg(11000.0) == pytest.approx(916.6666, rel=1e-3)


def test_dias_ocupacion():
    # 11000 kg MS / (100 animales * 12 kg) = 9.17 días
    assert dias_ocupacion(11000.0, 100, 12.0) == pytest.approx(9.1666, rel=1e-3)


def test_ugg_de_peso():
    assert ugg_de_peso(450.0) == 1.0
    assert ugg_de_peso(900.0) == 2.0


def test_engine_wrapper():
    assert PastureEngine.kg_mv_ha(1.0) == 10000.0
