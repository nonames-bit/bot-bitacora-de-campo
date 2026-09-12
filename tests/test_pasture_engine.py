"""Pruebas del motor de pasturas (aforo, MS, carga UGG, ocupación Voisin)."""
import pytest

from src.engine.pasture_engine import (
    PastureEngine, capacidad_carga_ugg, dias_ocupacion, evaluar_ronda_voisin,
    kg_ms_disponibles, kg_ms_ha, kg_mv_ha, ugg_de_peso,
)


def test_kg_mv_ha():
    assert kg_mv_ha(0.5) == 5000.0


def test_kg_ms_ha():
    assert kg_ms_ha(5000.0, 22.0) == pytest.approx(1100.0)
    # Probar con el valor por defecto de pasto tropical (22.0%)
    assert kg_ms_ha(5000.0) == pytest.approx(1100.0)


def test_kg_ms_disponibles():
    assert kg_ms_disponibles(0.5, 10.0, 22.0) == pytest.approx(11000.0)
    # Probar con el valor por defecto
    assert kg_ms_disponibles(0.5, 10.0) == pytest.approx(11000.0)


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


def test_evaluar_ronda_voisin():
    # 0.40 kg MV/m² → 1200 kg MS/ha; 1200*5/(10*12.6) ≈ 47.6 días → VERDE
    r = evaluar_ronda_voisin([0.40] * 10, area_has=5.0, num_animales=10)
    assert r["kg_mv_promedio"] == pytest.approx(0.40)
    assert r["kg_ms_ha"] == pytest.approx(1200.0)
    assert r["dias_disponibles"] == pytest.approx(47.6, rel=1e-2)
    assert r["semaforo"] == "VERDE"
    assert r["num_puntos"] == 10
    # 0.05 kg MV/m² → 150*5/126 ≈ 5.95 días → AMARILLO
    r2 = evaluar_ronda_voisin([0.05] * 10, area_has=5.0, num_animales=10)
    assert r2["dias_disponibles"] == pytest.approx(5.95, rel=1e-2)
    assert r2["semaforo"] == "AMARILLO"
    # 0.02 kg MV/m² → 60*5/126 ≈ 2.4 días → ROJO
    r3 = evaluar_ronda_voisin([0.02] * 10, area_has=5.0, num_animales=10)
    assert r3["dias_disponibles"] == pytest.approx(2.4, rel=1e-2)
    assert r3["semaforo"] == "ROJO"
    # Vía el wrapper del engine (misma firma que usa la PWA)
    rw = PastureEngine.evaluar_ronda_voisin([0.40] * 10, 5.0, 10)
    assert rw["semaforo"] == "VERDE"


def test_evaluar_ronda_voisin_sin_area():
    assert evaluar_ronda_voisin([0.40] * 10, area_has=0) is None
    assert evaluar_ronda_voisin([0.40] * 10, area_has=None) is None
    assert evaluar_ronda_voisin([], area_has=5.0) is None
    assert evaluar_ronda_voisin(None, area_has=5.0) is None


def test_db_registrar_ronda_voisin(db):
    pid = db.registrar_potrero(nombre="Ronda Test", area_has=5.0)
    r = evaluar_ronda_voisin([0.40] * 10, area_has=5.0, num_animales=10)
    db.registrar_ronda_voisin(pid, [0.40] * 10, r["num_puntos"], r["kg_mv_promedio"],
                              r["dias_disponibles"], r["semaforo"],
                              kg_ms_ha_val=r["kg_ms_ha"], fecha="2026-09-12")
    filas = db.listar_rondas_voisin(pid)
    assert len(filas) == 1
    assert filas[0]["potrero_nom"] == "Ronda Test"
    assert filas[0]["semaforo"] == "VERDE"
    assert filas[0]["num_puntos"] == 10
