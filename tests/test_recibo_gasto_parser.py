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


def _analizar(sample_json):
    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_gemini.generate_vision_structured.return_value = sample_json
    dummy_img = base64.b64encode(b"dummy_image").decode("utf-8")
    with patch("src.vision.recibo_gasto_parser.GeminiClient", return_value=mock_gemini):
        return analizar_factura_gasto(dummy_img, fecha_referencia="2026-10-01")


def test_factura_con_sal_y_droga_se_reparte_por_categoria_y_cuadra_con_el_total():
    # Renglones sin IVA (400.000) y total con IVA (476.000): cada categoría
    # se escala para que la suma dé lo que se pagó.
    res = _analizar({
        "es_factura": True, "tipo": "EGRESO", "fecha": "2026-10-01",
        "proveedor": "Agrotienda El Ganadero", "concepto": "Sal y droga",
        "categoria_sugerida": "MEDICAMENTOS", "monto_total": 476000,
        "items": [
            {"descripcion": "Sal mineralizada 8% x3", "valor": 300000, "categoria": "SAL_MINERALES"},
            {"descripcion": "Ivermectina 1% 500ml", "valor": 80000, "categoria": "MEDICAMENTOS"},
            {"descripcion": "Jeringa 20ml", "valor": 20000, "categoria": "medicamentos"},
            {"descripcion": "renglón vacío", "valor": 0, "categoria": "INSUMO"},
        ],
    })
    assert [i["categoria"] for i in res["items"]] == ["SAL_MINERALES", "MEDICAMENTOS", "MEDICAMENTOS"]
    desglose = {g["categoria"]: g for g in res["desglose"]}
    assert set(desglose) == {"SAL_MINERALES", "MEDICAMENTOS"}
    assert desglose["SAL_MINERALES"]["monto"] == 357000
    assert desglose["MEDICAMENTOS"]["monto"] == 119000
    assert sum(g["monto"] for g in res["desglose"]) == 476000
    assert "Ivermectina" in desglose["MEDICAMENTOS"]["concepto"]
    # La sugerida es la que más plata se lleva, no la que dijo la IA.
    assert res["categoria_sugerida"] == "SAL_MINERALES"


def test_factura_de_una_sola_categoria_queda_en_un_solo_movimiento():
    res = _analizar({
        "es_factura": True, "tipo": "EGRESO", "concepto": "Concentrado 10 bultos",
        "categoria_sugerida": "ALIMENTO", "monto_total": 950000,
        "items": [{"descripcion": "Concentrado lechero", "valor": 950000, "categoria": "ALIMENTO"}],
    })
    assert res["desglose"] == [{"categoria": "ALIMENTO", "concepto": "Concentrado 10 bultos", "monto": 950000}]


def test_factura_sin_renglones_ni_total_suma_lo_que_haya():
    res = _analizar({"es_factura": True, "tipo": "EGRESO", "categoria_sugerida": "COMBUSTIBLE",
                     "monto_total": None, "items": []})
    assert res["monto_total"] is None
    assert len(res["desglose"]) == 1
