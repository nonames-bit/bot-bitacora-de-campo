"""Pruebas del motor de consultas en lenguaje natural."""
from datetime import date

import pytest

from src.engine.query_engine import QueryEngine

HOY = date(2026, 9, 1)


@pytest.fixture
def qe(db):
    db.registrar_parto(vaca_tag="47", fecha="2026-05-01")
    db.registrar_servicio(vaca_tag="47", fecha="2026-08-15",
                          fep_calculada="2027-05-25")
    db.registrar_tratamiento(animal_tag="20", fecha="2026-08-20",
                             dias_retiro_carne=14,
                             fecha_fin_retiro_carne="2026-09-03")
    db.registrar_pesaje(animal_tag="12", fecha="2026-01-01", peso_kg=350.0)
    db.registrar_pesaje(animal_tag="12", fecha="2026-03-11", peso_kg=420.0)
    db.registrar_potrero(nombre="Norte", dias_reposo=30, aforo_kg_m2=0.5)
    db.registrar_potrero(nombre="Bajo", dias_reposo=5)
    return QueryEngine(db, hoy=HOY)


def test_ultimo_parto(qe):
    assert "2026-05-01" in qe.responder("¿cuándo parió la 47?")


def test_palpacion_pendiente(qe):
    resp = qe.responder("¿qué vacas tienen palpación pendiente?")
    assert "47" in resp
    assert "2026-10-14" in resp


def test_secado(qe):
    resp = qe.responder("¿cuándo le toca el secado a la 47?")
    assert "2027-03-26" in resp


def test_en_retiro(qe):
    resp = qe.responder("¿qué animales están en tiempo de retiro?")
    assert "20" in resp


def test_historial(qe):
    resp = qe.responder("¿cuál es el historial de la vaca 47?")
    assert "partos: 1" in resp
    assert "servicios: 1" in resp


def test_pesaje_y_ganancia(qe):
    resp = qe.responder("¿cuánto pesó la 12 y cuál fue su ganancia diaria?")
    assert "420" in resp
    assert "ganancia" in resp


def test_potreros_listos(qe):
    resp = qe.responder("¿qué potreros están listos para pastoreo?")
    assert "Norte" in resp
    assert "Bajo" not in resp


def test_inseminacion_programada(db):
    db.registrar_celo(vaca_tag="47", fecha="2026-08-15", am_pm="PM")
    db.registrar_alerta("47", "INSEMINACION_PROGRAMADA", "2026-08-16",
                        descripcion="Inseminación programada (regla AM-PM) en la mañana")
    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("¿qué vacas debo inseminar?")
    assert "47" in resp
    assert "2026-08-16" in resp
    assert "mañana" in resp


def test_inseminacion_sin_pendientes(db):
    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("¿a qué vacas les toca servicio?")
    assert "No hay vacas pendientes de inseminación" in resp


def test_sin_datos(db):
    qe = QueryEngine(db, hoy=HOY)
    assert "No hay registro de parto" in qe.responder("¿cuándo parió la 47?")
