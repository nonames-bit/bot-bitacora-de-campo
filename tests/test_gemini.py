"""Pruebas de integración end-to-end de la Capa 2 multi-agente (Gemini)."""
from unittest.mock import patch

from src.bot.bot_interface import Bot
from src.parsers.event_parser import EventParser, ParsedEvent


def test_event_parser_uses_regex_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    parser = EventParser()
    ev = parser.parse("pario la 47, ternero macho")
    assert isinstance(ev, ParsedEvent)
    assert ev.tipo == "parto"
    assert ev.animal_tag == "47"


def test_event_parser_calls_llm_on_complex_multi_event(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-test123456789")
    ev_parto = ParsedEvent(tipo="parto", texto="", animal_tag="47", datos={"sexo_cria": "Macho", "estado_cria": "VIVO"})
    ev_trat = ParsedEvent(
        tipo="tratamiento",
        texto="",
        animal_tag="12",
        datos={"producto": "oxitetraciclina", "dosis": "20ml"},
    )
    with patch("src.llm.orchestrator.try_multiagent_parse", return_value=[ev_parto, ev_trat]):
        parser = EventParser()
        res = parser.parse("Ayer pario la 47 un ternero macho y tambien vacunamos a la 12 con oxitetraciclina 20ml")

    assert isinstance(res, list)
    assert len(res) == 2
    assert res[0].tipo == "parto"
    assert res[1].tipo == "tratamiento"


def test_bot_procesar_texto_multiples_eventos(db, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-test123456789")
    ev_parto = ParsedEvent(
        tipo="parto", texto="", animal_tag="47", datos={"sexo_cria": "Macho", "estado_cria": "VIVO"}
    )
    ev_trat = ParsedEvent(
        tipo="tratamiento",
        texto="",
        animal_tag="12",
        datos={
            "producto": "oxitetraciclina",
            "dosis": "20ml",
            "dias_retiro": 14,
            "dias_retiro_leche": 0,
            "dias_retiro_carne": 14,
        },
    )

    with patch("src.llm.orchestrator.try_multiagent_parse", return_value=[ev_parto, ev_trat]):
        bot = Bot(db)
        resp = bot.procesar_texto("pario la 47 ternero macho y vacune la 12 con oxitetraciclina 20ml")

    assert db.count("partos") == 1
    assert db.count("tratamientos") == 1
    assert db.get_animal("47") is not None
    assert db.get_animal("12") is not None

    alertas = db.query(
        "SELECT tipo_alerta FROM alertas WHERE animal_id = (SELECT id_animal FROM animales WHERE tag = '12')"
    )
    assert len(alertas) >= 1

    assert "parto de la 47" in resp.lower()
    assert "tratamiento de 12" in resp.lower()
