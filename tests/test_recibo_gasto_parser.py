"""Pruebas unitarias para el parser de facturas/recibos de gastos e ingresos con IA."""
import base64
from unittest.mock import MagicMock, patch

from src.vision.recibo_gasto_parser import analizar_factura_gasto


def test_analizar_factura_gasto_exitoso():
    sample_json = {
        "es_factura": True,
        "tipo": "EGRESO",
        "fecha": "2026-09-01",
        "proveedor": "Agrotienda El Ganadero",
        "concepto": "Sal mineralizada 3 bultos x 40kg",
        "categoria_sugerida": "INSUMO",
        "monto_total": 450000.0,
        "observaciones": "Factura #1234",
        "confianza": "alta",
    }
    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_gemini.generate_vision_structured.return_value = sample_json
    dummy_img = base64.b64encode(b"dummy_image").decode("utf-8")

    with patch("src.vision.recibo_gasto_parser.GeminiClient", return_value=mock_gemini):
        res = analizar_factura_gasto(dummy_img, fecha_referencia="2026-09-01")

    assert res["ok"] is True
    assert res["es_factura"] is True
    assert res["tipo"] == "EGRESO"
    assert res["proveedor"] == "Agrotienda El Ganadero"
    assert res["categoria_sugerida"] == "INSUMO"
    assert res["monto_total"] == 450000.0


def test_analizar_factura_gasto_categoria_invalida_cae_a_otro():
    sample_json = {
        "es_factura": True, "tipo": "EGRESO", "fecha": "2026-09-01",
        "proveedor": "X", "concepto": "Y", "categoria_sugerida": "NO_EXISTE",
        "monto_total": 1000.0, "observaciones": "", "confianza": "media",
    }
    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_gemini.generate_vision_structured.return_value = sample_json
    dummy_img = base64.b64encode(b"dummy_image").decode("utf-8")

    with patch("src.vision.recibo_gasto_parser.GeminiClient", return_value=mock_gemini):
        res = analizar_factura_gasto(dummy_img)

    assert res["categoria_sugerida"] == "OTRO_EGRESO"


def test_analizar_factura_gasto_tipo_invalido_cae_a_egreso():
    sample_json = {
        "es_factura": True, "tipo": "ALGO_RARO", "fecha": "2026-09-01",
        "proveedor": "X", "concepto": "Y", "categoria_sugerida": "INSUMO",
        "monto_total": 1000.0, "observaciones": "", "confianza": "media",
    }
    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_gemini.generate_vision_structured.return_value = sample_json
    dummy_img = base64.b64encode(b"dummy_image").decode("utf-8")

    with patch("src.vision.recibo_gasto_parser.GeminiClient", return_value=mock_gemini):
        res = analizar_factura_gasto(dummy_img)

    assert res["tipo"] == "EGRESO"


def test_analizar_factura_gasto_fecha_invalida_usa_referencia():
    sample_json = {
        "es_factura": True, "tipo": "EGRESO", "fecha": "no es una fecha",
        "proveedor": "X", "concepto": "Y", "categoria_sugerida": "INSUMO",
        "monto_total": 1000.0, "observaciones": "", "confianza": "media",
    }
    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_gemini.generate_vision_structured.return_value = sample_json
    dummy_img = base64.b64encode(b"dummy_image").decode("utf-8")

    with patch("src.vision.recibo_gasto_parser.GeminiClient", return_value=mock_gemini):
        res = analizar_factura_gasto(dummy_img, fecha_referencia="2026-09-07")

    assert res["fecha"] == "2026-09-07"


def test_analizar_factura_gasto_sin_keys():
    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = False
    dummy_img = base64.b64encode(b"dummy_image").decode("utf-8")

    with patch("src.vision.recibo_gasto_parser.GeminiClient", return_value=mock_gemini), \
         patch.dict("os.environ", {}, clear=True):
        res = analizar_factura_gasto(dummy_img)

    assert res["ok"] is False
    assert "configure" in res["error"].lower() or "llave" in res["error"].lower() or "api_key" in res["error"].lower()
