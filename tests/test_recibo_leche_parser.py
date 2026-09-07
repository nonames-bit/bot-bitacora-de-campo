"""Pruebas unitarias para el parser de recibos y planillas de leche con IA."""
import base64
from unittest.mock import MagicMock, patch
import pytest

from src.vision.recibo_leche_parser import (
    _extraer_bytes_e_imagen,
    _ajustar_fechas_dias,
    analizar_recibo_leche,
)


def test_extraer_bytes_e_imagen_raw():
    data = b"GIF89a\x01\x00"
    raw, mime = _extraer_bytes_e_imagen(data)
    assert raw == data
    assert mime == "image/gif"


def test_extraer_bytes_e_imagen_base64_data_url():
    original = b"fake_jpeg_content"
    b64 = base64.b64encode(original).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"
    raw, mime = _extraer_bytes_e_imagen(data_url)
    assert raw == original
    assert mime == "image/jpeg"


def test_ajustar_fechas_dias():
    dias = [
        {"dia": 2, "litros": 180.5, "notas": "normal"},
        {"dia": 1, "litros": "175.0", "notas": ""},
        {"dia": 15, "litros": 190, "notas": "pico"},
    ]
    res = _ajustar_fechas_dias(dias, "2026-05-10", mes_nombre="Mayo", ano_int=2026)
    assert len(res) == 3
    assert res[0]["dia"] == 1
    assert res[0]["fecha"] == "2026-05-01"
    assert res[0]["litros"] == 175.0
    assert res[1]["dia"] == 2
    assert res[1]["fecha"] == "2026-05-02"
    assert res[2]["dia"] == 15
    assert res[2]["fecha"] == "2026-05-15"


def test_analizar_recibo_leche_gemini_exitoso():
    sample_json = {
        "es_recibo_leche": True,
        "periodo": "1 al 15 de Mayo 2026",
        "mes": "Mayo",
        "ano": 2026,
        "acopiador": "Colanta",
        "total_litros_declarado": 545.5,
        "observaciones": "Grasa: 3.8%",
        "dias": [
            {"dia": 1, "litros": 180.0, "notas": "AM 100, PM 80"},
            {"dia": 2, "litros": 182.5, "notas": ""},
            {"dia": 3, "litros": 183.0, "notas": ""},
        ],
        "confianza": "alta",
    }

    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_gemini.generate_vision_structured.return_value = sample_json

    dummy_img = base64.b64encode(b"dummy_image").decode("utf-8")

    with patch("src.vision.recibo_leche_parser.GeminiClient", return_value=mock_gemini):
        res = analizar_recibo_leche(dummy_img, fecha_referencia="2026-05-15")

    assert res["ok"] is True
    assert res["es_recibo_leche"] is True
    assert res["acopiador"] == "Colanta"
    assert len(res["dias"]) == 3
    assert res["total_litros_calculado"] == 545.5
    assert res["discrepancia_litros"] == 0.0
    assert res["dias"][0]["fecha"] == "2026-05-01"


def test_analizar_recibo_leche_sin_keys():
    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = False

    dummy_img = base64.b64encode(b"dummy_image").decode("utf-8")

    with patch("src.vision.recibo_leche_parser.GeminiClient", return_value=mock_gemini), \
         patch.dict("os.environ", {}, clear=True):
        res = analizar_recibo_leche(dummy_img)

    assert res["ok"] is False
    assert "configure" in res["error"].lower() or "llave" in res["error"].lower() or "api_key" in res["error"].lower()
