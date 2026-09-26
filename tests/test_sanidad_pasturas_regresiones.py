"""Regresiones de sanidad y pasturas (revisión integral)."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.pasture_engine import evaluar_ronda_voisin
from src.engine.query_engine import QueryEngine

HOY = date(2026, 9, 25)


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "b.db")).create_tables()
    yield d
    d.close()


def test_retiro_largo_no_se_oculta_tras_tratamientos_recientes(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    f0 = HOY - timedelta(days=20)
    db.registrar_tratamiento("47", fecha=f0.isoformat(), producto="Ivermectina LA",
                             dias_retiro_carne=60, fecha_fin_retiro_carne=(f0 + timedelta(days=60)).isoformat())
    for i in range(6):
        db.registrar_tratamiento("47", fecha=(HOY - timedelta(days=i)).isoformat(), producto=f"Vitamina {i}")
    txt = QueryEngine(db, hoy=HOY)._retiro_animal("47")
    assert "Ivermectina LA" in txt and "carne" in txt


def test_potrero_listo_calcula_reposo_hoy_y_excluye_ocupados(db):
    db.registrar_potrero(nombre="Norte", aforo_kg_m2=1.5,
                         fecha_salida=(HOY - timedelta(days=30)).isoformat(), dias_reposo=2)
    db.registrar_potrero(nombre="Sur", aforo_kg_m2=1.5,
                         fecha_salida=(HOY - timedelta(days=40)).isoformat(), dias_reposo=40)
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero="Sur")
    txt = QueryEngine(db, hoy=HOY)._potreros_listos()
    assert "Norte" in txt       # reposo real 30 días aunque dias_reposo guardado sea 2
    assert "Sur" not in txt     # tiene animales activos


def test_ronda_voisin_marca_puntos_insuficientes():
    assert evaluar_ronda_voisin([1.2] * 3, 2.0, 10)["puntos_insuficientes"] is True
    assert evaluar_ronda_voisin([1.2] * 12, 2.0, 10)["puntos_insuficientes"] is False
