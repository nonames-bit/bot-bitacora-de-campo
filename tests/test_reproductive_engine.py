"""Pruebas del motor reproductivo (FEP, ecografía, palpación, secado, IEP)."""
from datetime import date


from src.engine.reproductive_engine import (
    ReproductiveEngine, dias_abiertos, fecha_ecografia, fecha_estimada_parto,
    fecha_palpacion, fecha_secado, iep_proyectado, programar_inseminacion,
)


def test_fep():
    assert fecha_estimada_parto(date(2026, 8, 15)) == date(2027, 5, 25)


def test_fep_string():
    assert fecha_estimada_parto("2026-08-15") == date(2027, 5, 25)


def test_ecografia():
    assert fecha_ecografia(date(2026, 8, 15)) == date(2026, 9, 19)


def test_palpacion():
    assert fecha_palpacion(date(2026, 8,15)) == date(2026, 10, 14)


def test_secado():
    fep = fecha_estimada_parto(date(2026, 8, 15))
    assert fecha_secado(fep) == date(2027, 3, 26)


def test_dias_abiertos():
    assert dias_abiertos(date(2026, 8, 15), date(2026, 5, 1)) == 106


def test_iep_proyectado():
    assert iep_proyectado(106) == 389


def test_programar_calendario():
    prog = ReproductiveEngine.programar(date(2026, 8, 15))
    assert prog["fep"] == "2027-05-25"
    assert prog["ecografia"] == "2026-09-19"
    assert prog["palpacion"] == "2026-10-14"
    assert prog["secado"] == "2027-03-26"


def test_programar_inseminacion_am():
    prog = programar_inseminacion(date(2026, 8, 15), "AM")
    assert prog["fecha"] == date(2026, 8, 15)
    assert prog["franja"] == "tarde"


def test_programar_inseminacion_pm():
    prog = programar_inseminacion(date(2026, 8, 15), "PM")
    assert prog["fecha"] == date(2026, 8, 16)
    assert prog["franja"] == "mañana"


def test_programar_inseminacion_sin_franja():
    prog = programar_inseminacion(date(2026, 8, 15), None)
    assert prog["fecha"] == date(2026, 8, 15)
    assert prog["franja"] == "tarde"
