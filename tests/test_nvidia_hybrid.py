"""Pruebas para NvidiaClient y fallback híbrido Gemini -> NVIDIA."""
import json
from unittest.mock import MagicMock, patch


from src.parsers.event_parser import EventParser, ParsedEvent
from src.llm.nvidia_client import NvidiaClient, extract_json_from_text
from src.llm import try_hybrid_parse


def test_nvidia_client_availability(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = NvidiaClient()
    assert not c.is_available()
    c2 = NvidiaClient(api_key="pegar_aqui_tu_clave_de_nvidia")
    assert not c2.is_available()
    c3 = NvidiaClient(api_key="nvapi-test123456789")
    assert c3.is_available()


def test_nvidia_extract_json_direct():
    payload = '{"tipo": "parto", "animal_tag": "47", "datos": {"sexo_cria": "Macho"}}'
    res = extract_json_from_text(payload)
    assert isinstance(res, dict)
    assert res["tipo"] == "parto"


def test_nvidia_client_parse_single(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-testkey123")
    mock_resp = {
        "choices": [{"message": {"content": json.dumps({"eventos": [{"tipo": "parto", "animal_tag": "47", "datos": {"sexo_cria": "Macho", "estado_cria": "VIVO"}}]})}}]
    }
    with patch("urllib.request.urlopen") as mu:
        m = MagicMock()
        m.read.return_value = json.dumps(mock_resp).encode()
        mu.return_value.__enter__.return_value = m
        c = NvidiaClient(api_key="nvapi-testkey123")
        evs = c.parse_text("pario la 47 macho")
        assert evs is not None
        assert evs[0].tipo == "parto"
        assert evs[0].animal_tag == "47"


def test_hybrid_fallback_gemini_fails_nvidia_succeeds(monkeypatch):
    """Si Gemini no está o falla, el híbrido debe caer a NVIDIA y devolver el evento."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-test")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-testkey123")
    ev_nvidia = ParsedEvent(tipo="parto", texto="test", animal_tag="47", datos={"sexo_cria": "Macho"})
    # Gemini devuelve None (falla), NVIDIA devuelve evento
    with patch("src.llm.orchestrator.try_multiagent_parse", return_value=None) as mock_gem:
        with patch("src.llm.nvidia_client.try_llm_parse", return_value=ev_nvidia) as mock_nv:
            res = try_hybrid_parse("pario la 47 macho")
            assert isinstance(res, ParsedEvent)
            assert res.tipo == "parto"
            mock_gem.assert_called_once()
            mock_nv.assert_called_once()


def test_hybrid_prefiere_gemini_si_responde(monkeypatch):
    """Si Gemini responde, no debe llamar a NVIDIA."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-test")
    ev_gem = ParsedEvent(tipo="tratamiento", texto="test", animal_tag="12", datos={"producto": "oxi"})
    with patch("src.llm.orchestrator.try_multiagent_parse", return_value=ev_gem) as mock_gem:
        with patch("src.llm.nvidia_client.try_llm_parse") as mock_nv:
            res = try_hybrid_parse("texto")
            assert res.tipo == "tratamiento"
            mock_gem.assert_called_once()
            mock_nv.assert_not_called()


def test_event_parser_usa_hibrido_en_nota_compleja(monkeypatch):
    """EventParser debe usar el híbrido para notas complejas y respetar el mock."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy-test")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    ev_parto = ParsedEvent(tipo="parto", texto="", animal_tag="47", datos={"sexo_cria": "Macho"})
    ev_trat = ParsedEvent(tipo="tratamiento", texto="", animal_tag="12", datos={"producto": "oxi"})
    with patch("src.llm.try_hybrid_parse", return_value=[ev_parto, ev_trat]):
        parser = EventParser()
        texto_largo = "Ayer pario la 47 y vacune la 12 con oxi 20ml y ademas nota muy larga con muchos detalles adicionales para superar umbral de veinte palabras y disparar LLM híbrido"
        res = parser.parse(texto_largo)
        assert isinstance(res, list)
        assert len(res) == 2
