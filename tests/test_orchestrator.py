"""Pruebas del orquestador multi-agente (router -> extractor(es) / clasificador)."""
import time
from unittest.mock import patch

import pytest

from src.llm.orchestrator import try_multiagent_parse
from src.parsers.event_parser import ParsedEvent


@pytest.fixture(autouse=True)
def gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-test123456789")


def test_orchestrator_un_dominio():
    ev = ParsedEvent(tipo="parto", texto="pario la 47", animal_tag="47")
    with (
        patch("src.llm.orchestrator.reproduccion.parse", return_value=[ev]) as m_repro,
        patch("src.llm.orchestrator.sanidad.parse") as m_sanidad,
        patch("src.llm.orchestrator.manejo.parse") as m_manejo,
        patch("src.llm.orchestrator.clasificador.clasificar_dominios") as m_clasif,
    ):
        res = try_multiagent_parse("pario la 47 un ternero macho")

    assert isinstance(res, ParsedEvent)
    assert res.tipo == "parto"
    m_repro.assert_called_once()
    m_sanidad.assert_not_called()
    m_manejo.assert_not_called()
    m_clasif.assert_not_called()


def test_orchestrator_dos_dominios_paralelo_orden_determinista():
    ev_parto = ParsedEvent(tipo="parto", texto="", animal_tag="47")
    ev_trat = ParsedEvent(tipo="tratamiento", texto="", animal_tag="12")

    def repro_lento(*args, **kwargs):
        time.sleep(0.08)
        return [ev_parto]

    def sanidad_rapido(*args, **kwargs):
        time.sleep(0.01)
        return [ev_trat]

    with (
        patch("src.llm.orchestrator.reproduccion.parse", side_effect=repro_lento),
        patch("src.llm.orchestrator.sanidad.parse", side_effect=sanidad_rapido),
    ):
        res = try_multiagent_parse("pario la 47 y vacune la 12 con oxitetraciclina")

    assert isinstance(res, list)
    assert len(res) == 2
    # El orden de salida sigue el orden alfabético de dominios (reproduccion
    # antes que sanidad), no el orden de llegada de red (sanidad responde antes).
    assert res[0].tipo == "parto"
    assert res[1].tipo == "tratamiento"


def test_orchestrator_cero_dominios_usa_clasificador():
    ev = ParsedEvent(tipo="pesaje", texto="", animal_tag="8")
    with (
        patch("src.llm.orchestrator.clasificador.clasificar_dominios", return_value=["manejo"]) as m_clasif,
        patch("src.llm.orchestrator.manejo.parse", return_value=[ev]) as m_manejo,
    ):
        res = try_multiagent_parse("jerga rara sin patron conocido")

    m_clasif.assert_called_once()
    m_manejo.assert_called_once()
    assert isinstance(res, ParsedEvent)
    assert res.tipo == "pesaje"


def test_orchestrator_clasificador_no_reconoce_nada():
    with patch("src.llm.orchestrator.clasificador.clasificar_dominios", return_value=[]):
        res = try_multiagent_parse("jerga rara sin patron conocido")
    assert res is None


def test_orchestrator_fallo_parcial_en_paralelo():
    ev_trat = ParsedEvent(tipo="tratamiento", texto="", animal_tag="12")

    def repro_falla(*args, **kwargs):
        raise RuntimeError("timeout simulado")

    with (
        patch("src.llm.orchestrator.reproduccion.parse", side_effect=repro_falla),
        patch("src.llm.orchestrator.sanidad.parse", return_value=[ev_trat]),
    ):
        res = try_multiagent_parse("pario la 47 y vacune la 12 con oxitetraciclina")

    assert isinstance(res, ParsedEvent)
    assert res.tipo == "tratamiento"


def test_orchestrator_sin_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("src.llm.orchestrator.clasificador.clasificar_dominios") as m_clasif:
        res = try_multiagent_parse("pario la 47")
    m_clasif.assert_not_called()
    assert res is None
