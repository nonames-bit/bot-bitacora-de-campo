"""Pruebas del parser de eventos y del motor NLU."""
import pytest

from src.parsers.event_parser import EventParser, ParsedEvent
from src.parsers import nlp_engine as nlu


@pytest.fixture
def parser():
    return EventParser()


# ---------------------------------------------------------------------------
# Clasificación de intenciones
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("texto, esperado", [
    ("pario la 47, ternero macho", "parto"),
    ("se murio el 105 mordedura de culebra", "muerte"),
    ("insemine la 47 con toro brahman 502", "servicio"),
    ("la 47 esta en celo", "celo"),
    ("le puse oxitetraciclina 20ml a la 47", "tratamiento"),
    ("pesaje de la 12 peso 420 kg", "pesaje"),
    ("pase el lote 2 del potrero bajo al potrero norte", "traslado"),
    ("entraron 15 novillas compradas en subasta", "movimiento"),
])
def test_clasificar(texto, esperado):
    assert nlu.clasificar(texto) == esperado


def test_consulta_detectada(parser):
    ev = parser.parse("¿cuándo parió la 47?")
    assert ev.tipo == "consulta"


# ---------------------------------------------------------------------------
# Extracción por evento
# ---------------------------------------------------------------------------
def test_parse_parto(parser):
    ev = parser.parse("pario la 47, ternero macho")
    assert ev.tipo == "parto"
    assert ev.animal_tag == "47"
    assert ev.datos["sexo_cria"] == "Macho"
    assert ev.datos["estado_cria"] == "VIVO"


def test_parse_parto_hembra_muerto(parser):
    ev = parser.parse("la 47 pario una ternera muerta")
    assert ev.tipo == "parto"
    assert ev.datos["sexo_cria"] == "Hembra"
    assert ev.datos["estado_cria"] == "MUERTO"


def test_parse_muerte(parser):
    ev = parser.parse("se murio el 105 mordedura de culebra")
    assert ev.tipo == "muerte"
    assert ev.animal_tag == "105"
    assert "mordedura" in ev.datos["causa_presunta"]


def test_parse_servicio(parser):
    ev = parser.parse("insemine la 47 con toro brahman 502")
    assert ev.tipo == "servicio"
    assert ev.animal_tag == "47"
    assert ev.datos["tipo_servicio"] == "IA"
    assert ev.datos["toro_pajilla"] == "502"
    assert ev.datos["raza_toro"] == "brahman"


def test_parse_servicio_monta(parser):
    ev = parser.parse("monte la 12 con el toro 33")
    assert ev.tipo == "servicio"
    assert ev.datos["tipo_servicio"] == "MONTA"


def test_parse_celo(parser):
    ev = parser.parse("la 47 esta en celo en la tarde")
    assert ev.tipo == "celo"
    assert ev.animal_tag == "47"
    assert ev.datos["am_pm"] == "PM"


def test_parse_tratamiento(parser):
    ev = parser.parse("le puse oxitetraciclina 20ml a la 47 con 14 dias de retiro")
    assert ev.tipo == "tratamiento"
    assert ev.animal_tag == "47"
    assert ev.datos["producto"] == "oxitetraciclina"
    assert ev.datos["dosis"] == "20ml"
    assert ev.datos["dias_retiro"] == 14


def test_parse_tratamiento_retiro_carne_por_defecto(parser):
    ev = parser.parse("le puse oxitetraciclina 20ml a la 47 con 14 dias de retiro")
    assert ev.datos["dias_retiro_leche"] is None
    assert ev.datos["dias_retiro_carne"] == 14


def test_parse_tratamiento_retiro_leche(parser):
    ev = parser.parse("le puse oxitetraciclina a la 47 con 14 dias de retiro en leche")
    assert ev.datos["dias_retiro_leche"] == 14
    assert ev.datos["dias_retiro_carne"] is None


def test_prefijo_del_no_captura_tag(parser):
    ev = parser.parse("pase del potrero 5 al potrero 6")
    assert ev.tipo == "traslado"
    assert ev.animal_tag is None


def test_parse_pesaje(parser):
    ev = parser.parse("pesaje de la 12 peso 420 kg")
    assert ev.tipo == "pesaje"
    assert ev.animal_tag == "12"
    assert ev.datos["peso_kg"] == 420.0


def test_parse_traslado(parser):
    ev = parser.parse("pase el lote 2 del potrero bajo al potrero norte")
    assert ev.tipo == "traslado"
    assert ev.datos["lote"] == "2"
    assert ev.datos["potrero_origen"] == "bajo"
    assert ev.datos["potrero_destino"] == "norte"


def test_parse_movimiento_compra(parser):
    ev = parser.parse("entraron 15 novillas compradas en subasta")
    assert ev.tipo == "movimiento"
    assert ev.datos["tipo_movimiento"] == "COMPRA"
    assert ev.datos["cantidad"] == 15


def test_parse_desconocido(parser):
    ev = parser.parse("bla bla bla")
    assert ev.tipo == "desconocido"


def test_parse_fecha_hoy(parser):
    ev = parser.parse("pario la 47 hoy")
    assert ev.fecha is not None
    assert ev.fecha == parser.hoy.isoformat()
