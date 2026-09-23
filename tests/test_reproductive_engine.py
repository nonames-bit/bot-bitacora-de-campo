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


def test_indice_fertilidad():
    # Caso 1: 50 preñadas + 10 descanso / 80 vientres = 60 / 80 = 75.0%
    res1 = ReproductiveEngine.indice_fertilidad(50, 10, 80)
    assert res1["indice_pct"] == 75.0
    assert res1["semaforo"] == "🟢"
    assert res1["numerador_util"] == 60

    # Caso 2: 40 preñadas + 8 descanso / 80 vientres = 48 / 80 = 60.0%
    res2 = ReproductiveEngine.indice_fertilidad(40, 8, 80)
    assert res2["indice_pct"] == 60.0
    assert res2["semaforo"] == "🟡"

    # Caso 3: 30 preñadas + 5 descanso / 80 vientres = 35 / 80 = 43.75%
    res3 = ReproductiveEngine.indice_fertilidad(30, 5, 80)
    assert res3["indice_pct"] == 43.75
    assert res3["semaforo"] == "🔴"

    # Caso borde: 0 vientres
    res0 = ReproductiveEngine.indice_fertilidad(0, 0, 0)
    assert res0["indice_pct"] == 0.0


def test_tramos_zootecnicos():
    # Días abiertos
    assert ReproductiveEngine.categorizar_dias_abiertos(75) == "0-90"
    assert ReproductiveEngine.categorizar_dias_abiertos(110) == "91-120"
    assert ReproductiveEngine.categorizar_dias_abiertos(145) == "121-150"
    assert ReproductiveEngine.categorizar_dias_abiertos(350) == ">300"
    assert ReproductiveEngine.categorizar_dias_abiertos(None) == "Sin dato"

    # IEP
    assert ReproductiveEngine.categorizar_iep(350) == "<365"
    assert ReproductiveEngine.categorizar_iep(380) == "365-395"
    assert ReproductiveEngine.categorizar_iep(410) == "396-425"
    assert ReproductiveEngine.categorizar_iep(500) == ">485"
    assert ReproductiveEngine.categorizar_iep(None) == "Sin dato"

    # DEL (Días En Leche)
    assert ReproductiveEngine.categorizar_del(60) == "0-100 (Pico)"
    assert ReproductiveEngine.categorizar_del(150) == "101-200 (Meseta)"
    assert ReproductiveEngine.categorizar_del(250) == "201-340 (Descenso)"
    assert ReproductiveEngine.categorizar_del(380) == ">340 (Prolongada)"
    assert ReproductiveEngine.categorizar_del(None) == "Sin dato"

