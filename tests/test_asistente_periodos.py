"""Preguntas reales del Asistente IA (chat de la app, 2026-11-07) sobre partos
por mes y vacas en ordeño. "Este mes" es el mes de calendario (desde el día 1),
y un mes con nombre ("partos de octubre") es ese mes completo."""
from datetime import date

import pytest

from src.engine.query_engine import QueryEngine

HOY = date(2026, 11, 7)
POLIGONO = "POLYGON((0 0,0 1,1 1,1 0,0 0))"


@pytest.fixture
def qe(db):
    db.registrar_potrero(nombre="ORDENO SANTA MARTHA")
    db.registrar_potrero(nombre="PARITORIO")
    # Código viejo del import (sin polígono): no es un potrero presente.
    db.registrar_potrero(nombre="VACAS TODA LECHE")
    db.execute("UPDATE potreros SET geom_wkt_4326 = ? WHERE nombre != 'VACAS TODA LECHE'", (POLIGONO,))
    partos = [
        ("V050", "2026-11-06", "Hembra"),
        ("A067", "2026-11-04", "Macho"),
        ("V061", "2026-10-22", "Macho"),
        ("V076", "2026-10-19", "Hembra"),
        ("V099", "2026-09-30", "Macho"),
    ]
    for tag, fecha, sexo in partos:
        db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2020-01-01")
        db.registrar_parto(tag, fecha=fecha, sexo_cria=sexo)
    db.registrar_animal("V077", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2020-01-01")
    db.registrar_parto("V077", fecha="2026-10-10", tipo_evento="ABORTO")
    return QueryEngine(db, hoy=HOY)


@pytest.mark.parametrize("pregunta", [
    "partos este mes", "cuantos partos este mes", "vacas paridas este mes",
    "cuantas vacas parieron este mes", "cuantas vacas parieron",
])
def test_partos_este_mes_solo_noviembre(qe, pregunta):
    resp = qe.responder(pregunta)
    assert "noviembre" in resp and "(2)" in resp
    assert "V050" in resp and "A067" in resp
    assert "2026-10" not in resp


@pytest.mark.parametrize("pregunta", [
    "partos de octubre", "partos en octubre", "cuantos partos hubo en octubre",
    "vacas que parieron en octubre", "partos octubre 2026", "partos del mes pasado",
    "nacimientos de octubre",
])
def test_partos_de_un_mes_con_nombre(qe, pregunta):
    resp = qe.responder(pregunta)
    assert "No hay registros" not in resp and "No entendí" not in resp
    assert "octubre" in resp and "(2)" in resp
    assert "V061" in resp and "V076" in resp
    assert "V050" not in resp and "V099" not in resp
    # El aborto no es un parto: se avisa aparte.
    assert "V077" not in resp and "1 aborto" in resp


def test_mes_futuro_es_del_ano_pasado(qe):
    assert "diciembre 2025" in qe.responder("partos de diciembre")


def test_terneras_nacidas_por_mes(qe):
    assert "<b>1</b>" in qe.responder("terneras nacidas este mes")
    assert "<b>1</b>" in qe.responder("terneros machos nacidos en octubre")


@pytest.mark.parametrize("pregunta", [
    "cuantas vacas hay en ordeño", "cuantas vacas hay en ordeno", "cuantas vacas estan en ordeño",
    "vacas en ordeño",
])
def test_vacas_en_ordeno_no_es_un_potrero(qe, pregunta):
    resp = qe.responder(pregunta)
    assert "Vacas en ordeño" in resp
    assert "no existe" not in resp and "VACAS TODA LECHE" not in resp


@pytest.mark.parametrize("pregunta, esperado", [
    ("ventas de octubre", "octubre 2026"),
    ("muertes de octubre", "octubre 2026"),
])
def test_otros_eventos_por_mes(qe, pregunta, esperado):
    resp = qe.responder(pregunta)
    assert esperado in resp and "No hay registros para" not in resp


def test_potrero_por_nombre_sigue_funcionando(qe):
    assert "PARITORIO" in qe.responder("cuantos animales hay en el paritorio")
