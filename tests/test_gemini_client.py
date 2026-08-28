"""Pruebas unitarias del cliente HTTP bajo nivel para Gemini."""
import json
import urllib.error
from unittest.mock import MagicMock, patch

from src.llm.gemini_client import DEFAULT_MODEL, GeminiClient

SCHEMA_DUMMY = {"type": "object", "properties": {"eventos": {"type": "array"}}}


def _mock_response(payload_text: str):
    mock_response = MagicMock()
    envelope = {
        "candidates": [
            {"content": {"parts": [{"text": payload_text}]}}
        ]
    }
    mock_response.read.return_value = json.dumps(envelope).encode("utf-8")
    return mock_response


def test_gemini_client_availability(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = GeminiClient()
    assert not client.is_available()

    client_ph = GeminiClient(api_key="pegar_aqui_tu_clave_de_gemini")
    assert not client_ph.is_available()

    client_valid = GeminiClient(api_key="AIzaSy-test123456789")
    assert client_valid.is_available()
    assert client_valid.model == DEFAULT_MODEL


def test_gemini_client_generate_structured_success():
    client = GeminiClient(api_key="AIzaSy-test123456789")
    body = json.dumps({"eventos": [{"tipo": "parto", "animal_tag": "47"}]})
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _mock_response(body)
        res = client.generate_structured("system prompt", "texto de prueba", SCHEMA_DUMMY)
    assert res == {"eventos": [{"tipo": "parto", "animal_tag": "47"}]}


def test_gemini_client_empty_candidates():
    client = GeminiClient(api_key="AIzaSy-test123456789")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"candidates": []}).encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response
        res = client.generate_structured("system prompt", "texto", SCHEMA_DUMMY)
    assert res is None


def test_gemini_client_network_error_fallback():
    client = GeminiClient(api_key="AIzaSy-test123456789")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        res = client.generate_structured("system", "texto", SCHEMA_DUMMY)
    assert res is None


def test_gemini_client_http_error_fallback():
    client = GeminiClient(api_key="AIzaSy-test123456789")
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError("http://gemini", 401, "Unauthorized", {}, None),
    ):
        res = client.generate_structured("system", "texto", SCHEMA_DUMMY)
    assert res is None


def test_gemini_client_timeout_fallback():
    client = GeminiClient(api_key="AIzaSy-test123456789")
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        res = client.generate_structured("system", "texto", SCHEMA_DUMMY)
    assert res is None


def test_gemini_client_malformed_json_in_text():
    client = GeminiClient(api_key="AIzaSy-test123456789")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _mock_response("no es json valido")
        res = client.generate_structured("system", "texto", SCHEMA_DUMMY)
    assert res is None


def test_gemini_client_no_api_key_returns_none_without_network():
    client = GeminiClient(api_key="")
    with patch("urllib.request.urlopen") as mock_urlopen:
        res = client.generate_structured("system", "texto", SCHEMA_DUMMY)
        mock_urlopen.assert_not_called()
    assert res is None
