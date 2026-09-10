"""Pruebas unitarias para la sincronización automática de precios de mercado.

Valida:
1. Consulta de TRM oficial con datos abiertos y tolerancia a fallos/fallbacks.
2. Consulta de titulares ganaderos y subastas vía RSS.
3. Sincronización desatendida ("sin nada manual") e idempotencia en la base de datos.
"""
from __future__ import annotations

import io
import json
import urllib.request
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.db.database import Database
from src.integrations.mercado_sync import (
    consultar_titulares_mercado,
    consultar_trm_oficial,
    sincronizar_precios_mercado,
)


def test_consultar_trm_oficial_socrata_exito():
    fake_json = json.dumps([{
        "valor": "4125.50",
        "unidad": "COP",
        "vigenciadesde": "2026-09-09T00:00:00.000",
        "vigenciahasta": "2026-09-09T00:00:00.000"
    }]).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_json
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = consultar_trm_oficial()

    assert res["ok"] is True
    assert res["valor"] == 4125.50
    assert "Superintendencia Financiera" in res["fuente"]


def test_consultar_trm_oficial_fallback_dolarapi():
    # Socrata falla, DolarAPI responde
    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "datos.gov.co" in url:
            raise urllib.error.URLError("Timeout en Socrata")
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "valor": 4150.25,
            "fechaActualizacion": "2026-09-09T10:00:00.000Z"
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        res = consultar_trm_oficial()

    assert res["ok"] is True
    assert res["valor"] == 4150.25
    assert "DolarAPI" in res["fuente"]


def test_consultar_trm_oficial_ambos_fallan():
    with patch("urllib.request.urlopen", side_effect=Exception("Sin conexión")):
        res = consultar_trm_oficial()

    assert res["ok"] is False
    assert res["valor"] == 4085.0
    assert "Referencia Base" in res["fuente"]


def test_consultar_titulares_mercado_rss(monkeypatch):
    from src.integrations import mercado_sync
    # Reset in-memory cache
    monkeypatch.setattr(mercado_sync, "_CACHE_TITULARES", {"fecha": None, "items": []})

    rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title><![CDATA[Alzas contundentes en subastas del Meta - CONtexto Ganadero]]></title>
          <link>https://example.com/noticia-1</link>
          <pubDate>Mon, 07 Sep 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = rss_content
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        noticias = consultar_titulares_mercado()

    assert len(noticias) == 1
    assert "Alzas contundentes en subastas del Meta" in noticias[0]["titulo"]
    assert noticias[0]["enlace"] == "https://example.com/noticia-1"


def test_sincronizar_precios_mercado_completo(tmp_path):
    db_file = tmp_path / "test_mercado.db"
    db = Database(str(db_file)).create_tables()

    # Mock de red para no depender de internet en el test unitario
    with patch("src.integrations.mercado_sync.consultar_trm_oficial", return_value={
        "valor": 4120.0,
        "fecha": date.today().isoformat(),
        "fuente": "AUTOMATICO: Datos Abiertos (Test)",
        "ok": True
    }), patch("src.integrations.mercado_sync.consultar_titulares_mercado", return_value=[]):
        
        # 1. Primera ejecución: debe actualizar todos los precios
        res1 = sincronizar_precios_mercado(db, forzar=False)
        assert res1["ok"] is True
        assert res1["actualizado"] is True
        assert res1["trm"] == 4120.0
        assert res1["filas_actualizadas"] >= 40

        # Verificar en base de datos
        datos = db.obtener_datos_mercado_completos()
        assert datos["trm_actual"] == 4120.0
        assert datos["actualizacion_automatica"] is True

        plazas_guardadas = {s["plaza_key"] for s in datos["subastas"]}
        assert "GRANADA" in plazas_guardadas
        assert "GUAMAL" in plazas_guardadas
        assert "CATAMA" in plazas_guardadas
        assert "BOGOTA" in plazas_guardadas

        # 2. Segunda ejecución (mismo día): idempotencia (no reescribe a menos que se fuerce)
        res2 = sincronizar_precios_mercado(db, forzar=False)
        assert res2["ok"] is True
        assert res2["actualizado"] is False

        # 3. Tercera ejecución con forzar=True: debe actualizar
        res3 = sincronizar_precios_mercado(db, forzar=True)
        assert res3["ok"] is True
        assert res3["actualizado"] is True

    db.close()
