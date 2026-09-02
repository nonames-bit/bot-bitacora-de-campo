"""Pruebas para GenericOpenAIClient (OpenRouter / CheaperInference / OpenCode Go)."""
import json
from unittest.mock import MagicMock, patch

from src.llm.generic_client import GenericOpenAIClient, try_generic_parse


def _limpiar_env(monkeypatch, prefix):
    for suf in ("_API_KEY", "_MODEL", "_BASE_URL"):
        monkeypatch.delenv(prefix + suf, raising=False)


def test_generic_client_no_disponible_sin_configurar(monkeypatch):
    _limpiar_env(monkeypatch, "OPENROUTER")
    c = GenericOpenAIClient(provider="openrouter", env_prefix="OPENROUTER")
    assert not c.is_available()


def test_generic_client_no_disponible_con_placeholder(monkeypatch):
    _limpiar_env(monkeypatch, "OPENROUTER")
    monkeypatch.setenv("OPENROUTER_API_KEY", "pegar_aqui_tu_clave_de_openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "algun-modelo")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
    c = GenericOpenAIClient(provider="openrouter", env_prefix="OPENROUTER")
    assert not c.is_available()


def test_generic_client_no_disponible_sin_modelo(monkeypatch):
    """Aunque haya API key, sin MODEL configurado no debe activarse (evita adivinar)."""
    _limpiar_env(monkeypatch, "OPENROUTER")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test123456")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
    c = GenericOpenAIClient(provider="openrouter", env_prefix="OPENROUTER")
    assert not c.is_available()


def test_generic_client_disponible_bien_configurado(monkeypatch):
    _limpiar_env(monkeypatch, "CHEAPERINFERENCE")
    monkeypatch.setenv("CHEAPERINFERENCE_API_KEY", "ci_live_test123456")
    monkeypatch.setenv("CHEAPERINFERENCE_MODEL", "algun-modelo-del-catalogo")
    monkeypatch.setenv("CHEAPERINFERENCE_BASE_URL", "https://api.cheaperinference.com/v1/chat/completions")
    c = GenericOpenAIClient(provider="cheaperinference", env_prefix="CHEAPERINFERENCE")
    assert c.is_available()
    assert c.model == "algun-modelo-del-catalogo"
    assert c.api_url == "https://api.cheaperinference.com/v1/chat/completions"


def test_generic_client_parse_single_event(monkeypatch):
    _limpiar_env(monkeypatch, "OPENCODE")
    monkeypatch.setenv("OPENCODE_API_KEY", "oc-test123456")
    monkeypatch.setenv("OPENCODE_MODEL", "opencode-go/kimi-k3")
    monkeypatch.setenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1/chat/completions")
    c = GenericOpenAIClient(provider="opencode_go", env_prefix="OPENCODE")

    mock_resp = {
        "choices": [{"message": {"content": json.dumps({
            "eventos": [{"tipo": "parto", "animal_tag": "47", "datos": {"sexo_cria": "Macho", "estado_cria": "VIVO"}}]
        })}}]
    }
    with patch("urllib.request.urlopen") as mu:
        m = MagicMock()
        m.read.return_value = json.dumps(mock_resp).encode()
        mu.return_value.__enter__.return_value = m
        res = try_generic_parse(c, "pario la 47 macho")
        assert res is not None
        assert res.tipo == "parto"
        assert res.animal_tag == "47"


def test_try_generic_parse_sin_cliente_disponible_no_llama_red(monkeypatch):
    _limpiar_env(monkeypatch, "OPENROUTER")
    c = GenericOpenAIClient(provider="openrouter", env_prefix="OPENROUTER")
    with patch("urllib.request.urlopen") as mu:
        res = try_generic_parse(c, "pario la 47 macho")
        assert res is None
        mu.assert_not_called()
