"""Pruebas del motor de crecimiento (GMD y peso ajustado al destete)."""
import pytest

from src.engine.growth_engine import GrowthEngine, gmd, peso_ajustado_destete


def test_gmd():
    assert gmd(420.0, 350.0, 70) == pytest.approx(1.0)


def test_gmd_cero_dias():
    assert gmd(420.0, 350.0, 0) == 0.0


def test_gmd_perdida():
    assert gmd(340.0, 350.0, 10) == pytest.approx(-1.0)


def test_peso_ajustado_205():
    # (210 - 35)/210 * 205 + 35 = 205.833
    assert peso_ajustado_destete(210.0, 35.0, 210) == pytest.approx(205.833, rel=1e-3)


def test_peso_ajustado_edad_cero():
    assert peso_ajustado_destete(210.0, 35.0, 0) == 210.0


def test_engine_wrapper():
    assert GrowthEngine.gmd(420.0, 350.0, 70) == pytest.approx(1.0)
