"""Pruebas unitarias e integración para el cliente LLM NVIDIA NIM y capa NLU híbrida."""
import json
import os
import urllib.error
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.bot.bot_interface import Bot
from src.llm.nvidia_client import (
    DEFAULT_MODEL,
    NvidiaClient,
    extract_json_from_text,
    try_llm_parse,
)
from src.parsers.event_parser import EventParser, ParsedEvent


# ---------------------------------------------------------------------------
# 1. Disponibilidad y configuración del cliente
# ---------------------------------------------------------------------------
def test_nvidia_client_availability(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    client = NvidiaClient()
    assert not client.is_available()

    # Clave de placeholder debe considerarse deshabilitada
    client_ph = NvidiaClient(api_key="pegar_aqui_tu_clave_de_nvidia")
    assert not client_ph.is_available()

    # Clave real o de prueba
    client_valid = NvidiaClient(api_key="nvapi-test123456789")
    assert client_valid.is_available()
    assert client_valid.model == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# 2. Extracción robusta de JSON de respuestas LLM
# ---------------------------------------------------------------------------
def test_extract_json_direct_object():
    payload = '{"tipo": "parto", "animal_tag": "47", "datos": {"sexo_cria": "Macho"}}'
    res = extract_json_from_text(payload)
    assert isinstance(res, dict)
    assert res["tipo"] == "parto"
    assert res["animal_tag"] == "47"


def test_extract_json_with_markdown_fences():
    payload = """```json
    {
      "eventos": [
        {"tipo": "parto", "animal_tag": "47", "datos": {"sexo_cria": "Macho"}},
        {"tipo": "tratamiento", "animal_tag": "12", "datos": {"producto": "oxitetraciclina"}}
      ]
    }
    ```"""
    res = extract_json_from_text(payload)
    assert isinstance(res, dict)
    assert len(res["eventos"]) == 2


def test_extract_json_surrounded_by_chatter():
    payload = """Aquí está el resultado del análisis zootécnico:
    [
      {"tipo": "muerte", "animal_tag": "105", "datos": {"causa_presunta": "culebra"}}
    ]
    Espero que esta información sea de ayuda."""
    res = extract_json_from_text(payload)
    assert isinstance(res, list)
    assert res[0]["animal_tag"] == "105"


def test_extract_json_invalid():
    assert extract_json_from_text("Texto sin ningun json") is None
    assert extract_json_from_text("") is None


# ---------------------------------------------------------------------------
# 3. Parseo de eventos vía NvidiaClient (con mock HTTP)
# ---------------------------------------------------------------------------
def test_nvidia_client_parse_single_event():
    mock_llm_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "eventos": [
                            {
                                "tipo": "parto",
                                "animal_tag": "47",
                                "fecha": "2026-08-24",
                                "datos": {
                                    "sexo_cria": "Macho",
                                    "estado_cria": "VIVO",
                                    "peso_nacimiento": 38.5,
                                    "id_cria": "cria-01",
                                },
                            }
                        ]
                    })
                }
            }
        ]
    }

    client = NvidiaClient(api_key="nvapi-validkey")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_llm_json).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        eventos = client.parse_text("pario la vaca 47 un ternero macho de 38.5 kg")
        assert eventos is not None
        assert len(eventos) == 1
        ev = eventos[0]
        assert ev.tipo == "parto"
        assert ev.animal_tag == "47"
        assert ev.datos["sexo_cria"] == "Macho"
        assert ev.datos["peso_nacimiento"] == 38.5
        assert ev.datos["id_cria"] == "cria-01"


def test_nvidia_client_parse_multiple_events():
    mock_llm_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "eventos": [
                            {
                                "tipo": "parto",
                                "animal_tag": "47",
                                "datos": {"sexo_cria": "Hembra", "estado_cria": "VIVO"},
                            },
                            {
                                "tipo": "tratamiento",
                                "animal_tag": "12",
                                "datos": {
                                    "producto": "oxitetraciclina",
                                    "dosis": "20ml",
                                    "dias_retiro": 14,
                                },
                            },
                        ]
                    })
                }
            }
        ]
    }

    client = NvidiaClient(api_key="nvapi-validkey")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_llm_json).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        eventos = client.parse_text("pario la 47 una ternera y vacune la 12 con oxitetraciclina 20ml")
        assert eventos is not None
        assert len(eventos) == 2
        assert eventos[0].tipo == "parto"
        assert eventos[0].animal_tag == "47"
        assert eventos[1].tipo == "tratamiento"
        assert eventos[1].animal_tag == "12"
        assert eventos[1].datos["dias_retiro_carne"] == 14


def test_try_llm_parse_helper():
    mock_llm_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "eventos": [
                            {
                                "tipo": "servicio",
                                "animal_tag": "n069",
                                "datos": {
                                    "tipo_servicio": "IA",
                                    "toro_pajilla": "502",
                                    "raza_toro": "brahman",
                                },
                            }
                        ]
                    })
                }
            }
        ]
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_llm_json).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Single event -> returns ParsedEvent instance
        res = try_llm_parse("insemine la N-069 con pajuela brahman 502", api_key="nvapi-test")
        assert isinstance(res, ParsedEvent)
        assert res.tipo == "servicio"
        assert res.animal_tag == "n069"


# ---------------------------------------------------------------------------
# 4. Fallback y tolerancia a fallos de red / API
# ---------------------------------------------------------------------------
def test_nvidia_client_network_error_fallback():
    client = NvidiaClient(api_key="nvapi-validkey")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        res = client.parse_text("texto de prueba")
        assert res is None


def test_nvidia_client_http_error_fallback():
    client = NvidiaClient(api_key="nvapi-validkey")
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("http://nvidia", 401, "Unauthorized", {}, None)):
        res = client.parse_text("texto de prueba")
        assert res is None


def test_nvidia_client_timeout_fallback():
    client = NvidiaClient(api_key="nvapi-validkey")
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        res = client.parse_text("texto de prueba")
        assert res is None


# ---------------------------------------------------------------------------
# 5. Capa híbrida en EventParser
# ---------------------------------------------------------------------------
def test_event_parser_uses_regex_when_no_api_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    parser = EventParser()
    ev = parser.parse("pario la 47, ternero macho")
    assert isinstance(ev, ParsedEvent)
    assert ev.tipo == "parto"
    assert ev.animal_tag == "47"


def test_event_parser_calls_llm_on_complex_multi_event(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-validkey")
    mock_llm_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "eventos": [
                            {
                                "tipo": "parto",
                                "animal_tag": "47",
                                "datos": {"sexo_cria": "Macho", "estado_cria": "VIVO"},
                            },
                            {
                                "tipo": "tratamiento",
                                "animal_tag": "12",
                                "datos": {"producto": "oxitetraciclina", "dosis": "20ml"},
                            },
                        ]
                    })
                }
            }
        ]
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_llm_json).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        parser = EventParser()
        res = parser.parse("Ayer pario la 47 un ternero macho y tambien vacunamos a la 12 con oxitetraciclina 20ml")
        assert isinstance(res, list)
        assert len(res) == 2
        assert res[0].tipo == "parto"
        assert res[1].tipo == "tratamiento"


# ---------------------------------------------------------------------------
# 6. Integración del Bot con múltiples eventos
# ---------------------------------------------------------------------------
def test_bot_procesar_texto_multiples_eventos(db, monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-validkey")
    mock_llm_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "eventos": [
                            {
                                "tipo": "parto",
                                "animal_tag": "47",
                                "datos": {"sexo_cria": "Macho", "estado_cria": "VIVO"},
                            },
                            {
                                "tipo": "tratamiento",
                                "animal_tag": "12",
                                "datos": {
                                    "producto": "oxitetraciclina",
                                    "dosis": "20ml",
                                    "dias_retiro": 14,
                                },
                            },
                        ]
                    })
                }
            }
        ]
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_llm_json).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        bot = Bot(db)
        resp = bot.procesar_texto("pario la 47 ternero macho y vacune la 12 con oxitetraciclina 20ml")

        # Verificar que ambos eventos se registraron en SQLite
        assert db.count("partos") == 1
        assert db.count("tratamientos") == 1
        assert db.get_animal("47") is not None
        assert db.get_animal("12") is not None

        # Verificar que se generaron alertas correspondientes
        alertas = db.query("SELECT tipo_alerta FROM alertas WHERE animal_id = (SELECT id_animal FROM animales WHERE tag = '12')")
        assert len(alertas) >= 1

        # Verificar mensaje de confirmación consolidado
        assert "parto de la 47" in resp.lower()
        assert "tratamiento de 12" in resp.lower()
