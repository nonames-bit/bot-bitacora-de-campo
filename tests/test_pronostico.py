"""Tests del pronóstico del clima (Open-Meteo) integrado al Despacho Matutino.

SIN red: ningún test consulta Open-Meteo real. Se inyecta JSON sintético
o se mockea ``urllib.request.urlopen`` / ``obtener_pronostico``.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from src.db.database import Database
from src.engine import pronostico as P
from src.engine.pronostico import (
    _parsear_respuesta_open_meteo,
    coordenadas_finca,
    formatear_pronostico_despacho,
    interpretar_pronostico,
    obtener_pronostico,
    obtener_pronostico_para_despacho,
)
from src.server.formatters import formatear_despacho_matutino


def _dia(fecha_iso: str, tmax=28.0, tmin=18.0, mm=0.0, prob=None) -> dict:
    return {
        "fecha": date.fromisoformat(fecha_iso),
        "temp_max_c": tmax,
        "temp_min_c": tmin,
        "lluvia_mm": mm,
        "prob_lluvia_pct": prob,
    }


def _pron_base() -> dict:
    # Semana estable neutra: sin reglas (lluvias moderadas, temps suaves).
    return {
        "lat": 4.5,
        "lon": -74.0,
        "dias": [_dia(f"2026-09-{d:02d}", tmax=27.0, tmin=17.0, mm=3.0, prob=20.0) for d in range(1, 8)],
    }


def _json_open_meteo_realista() -> dict:
    return {
        "latitude": 4.5,
        "longitude": -74.0,
        "daily": {
            "time": ["2026-09-01", "2026-09-02", "2026-09-03"],
            "temperature_2m_max": [29.5, 30.1, 28.0],
            "temperature_2m_min": [18.2, 17.9, 18.5],
            "precipitation_sum": [0.0, 12.4, 1.1],
            "precipitation_probability_max": [10, 85, None],
        },
    }


# 1. Parser de respuesta real Open-Meteo.
def test_parsear_respuesta_open_meteo():
    pron = _parsear_respuesta_open_meteo(_json_open_meteo_realista(), lat=4.5, lon=-74.0)
    assert len(pron["dias"]) == 3
    d0 = pron["dias"][0]
    assert d0["fecha"] == date(2026, 9, 1)
    assert d0["temp_max_c"] == 29.5
    assert d0["lluvia_mm"] == 0.0
    assert d0["prob_lluvia_pct"] == 10.0
    assert pron["dias"][2]["prob_lluvia_pct"] is None


def test_obtener_pronostico_nunca_lanza_sin_red(monkeypatch):
    import urllib.request

    def _falla(req, timeout=None):
        raise OSError("sin red en tests")

    monkeypatch.setattr(urllib.request, "urlopen", _falla)
    assert obtener_pronostico(4.5, -74.0) is None


# 2. Una prueba por regla determinista.
def test_interpretar_lluvia_hoy():
    pron = _pron_base()
    pron["dias"][0] = _dia("2026-09-01", mm=12.0, prob=90.0)
    recs = interpretar_pronostico(pron)
    assert any("Lluvia probable" in r and "NO fumigar" in r for r in recs)


def test_interpretar_ventana_seca():
    pron = _pron_base()
    for i in range(3):
        pron["dias"][i] = _dia(f"2026-09-0{i + 1}", mm=0.0, prob=5.0)
    recs = interpretar_pronostico(pron)
    assert any("Ventana seca de" in r and "heno" in r for r in recs)


def test_interpretar_lluvia_acumulada_alta():
    pron = _pron_base()
    for i in range(7):
        pron["dias"][i] = _dia(f"2026-09-0{i + 1}", mm=10.0, prob=50.0)
    recs = interpretar_pronostico(pron)
    assert any("Lluvia fuerte acumulada" in r for r in recs)


def test_interpretar_sequia():
    pron = _pron_base()
    for i in range(7):
        pron["dias"][i] = _dia(f"2026-09-0{i + 1}", mm=0.0, prob=5.0)
    recs = interpretar_pronostico(pron)
    assert any("muy seca" in r and "bebederos" in r for r in recs)


def test_interpretar_calor():
    pron = _pron_base()
    pron["dias"][2] = _dia("2026-09-03", tmax=34.0, tmin=20.0, mm=3.0, prob=10.0)
    recs = interpretar_pronostico(pron)
    assert any("calurosos" in r and "sombra" in r for r in recs)


def test_interpretar_frio():
    pron = _pron_base()
    pron["dias"][4] = _dia("2026-09-05", tmax=22.0, tmin=6.0, mm=3.0, prob=10.0)
    recs = interpretar_pronostico(pron)
    assert any("frías" in r and "terneros" in r for r in recs)


def test_interpretar_estable():
    recs = interpretar_pronostico(_pron_base())
    assert recs == ["🌤️ Semana estable: sin alertas climáticas para la operación."]


# 3. Formateo del bloque.
def test_formatear_con_datos():
    txt = formatear_pronostico_despacho(_pron_base())
    assert "⛅ <b>CLIMA & PRONÓSTICO (7 DÍAS):</b>" in txt
    assert "Lluvia estimada" in txt
    assert "🌤️ Semana estable" in txt


def test_formatear_none_devuelve_vacio():
    assert formatear_pronostico_despacho(None) == ""
    assert formatear_pronostico_despacho({}) == ""
    assert formatear_pronostico_despacho({"dias": []}) == ""


def test_formatear_avisa_cache_viejo():
    pron = _pron_base()
    pron["desactualizado_horas"] = 9.0
    txt = formatear_pronostico_despacho(pron)
    assert "hace 9 h" in txt


# 4. Coordenadas de la finca.
def test_coordenadas_promedio(db: Database, monkeypatch):
    monkeypatch.delenv("FINCA_LAT", raising=False)
    monkeypatch.delenv("FINCA_LON", raising=False)
    db.insert("potreros", {"nombre": "P1", "geom_wkt_4326": "POINT (1 1)", "centroide_lat": 4.0, "centroide_lon": -74.0})
    db.insert("potreros", {"nombre": "P2", "geom_wkt_4326": "POINT (2 2)", "centroide_lat": 5.0, "centroide_lon": -75.0})
    # Potrero sin geometría: debe ignorarse.
    db.insert("potreros", {"nombre": "LEGACY", "centroide_lat": 99.0, "centroide_lon": 99.0})
    lat, lon = coordenadas_finca(db)
    assert lat == 4.5
    assert lon == -74.5


def test_coordenadas_fallback_env(db: Database, monkeypatch):
    monkeypatch.delenv("FINCA_LAT", raising=False)
    monkeypatch.delenv("FINCA_LON", raising=False)
    assert coordenadas_finca(db) is None
    monkeypatch.setenv("FINCA_LAT", "4.7")
    monkeypatch.setenv("FINCA_LON", "-74.1")
    assert coordenadas_finca(db) == (4.7, -74.1)


# 5. Cache en disco con TTL.
def _guardar_cache(ruta: str, horas_atras: float, pron: dict, lat=4.7, lon=-74.1):
    payload = {
        "guardado_en": (datetime.now() - timedelta(hours=horas_atras)).isoformat(),
        "lat": lat,
        "lon": lon,
        "pron": {
            **pron,
            "dias": [{**d, "fecha": d["fecha"].isoformat()} for d in pron["dias"]],
        },
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def test_cache_vigente_no_pega_red(db: Database, monkeypatch, tmp_path):
    cache = str(tmp_path / "pron_cache.json")
    monkeypatch.setenv("PRONOSTICO_CACHE", cache)
    monkeypatch.setenv("FINCA_LAT", "4.7")
    monkeypatch.setenv("FINCA_LON", "-74.1")
    _guardar_cache(cache, horas_atras=1.0, pron=_pron_base())

    llamadas = []

    def _api_espia(lat, lon, dias=7, timeout=8.0):
        llamadas.append((lat, lon))
        raise AssertionError("no debe llamar a la API con cache vigente")

    monkeypatch.setattr(P, "obtener_pronostico", _api_espia)
    pron = obtener_pronostico_para_despacho(db)
    assert pron is not None and len(pron["dias"]) == 7
    assert llamadas == []
    assert "desactualizado_horas" not in pron


def test_cache_viejo_marca_desactualizado_si_api_falla(db: Database, monkeypatch, tmp_path):
    cache = str(tmp_path / "pron_cache.json")
    monkeypatch.setenv("PRONOSTICO_CACHE", cache)
    monkeypatch.setenv("FINCA_LAT", "4.7")
    monkeypatch.setenv("FINCA_LON", "-74.1")
    _guardar_cache(cache, horas_atras=10.0, pron=_pron_base())
    monkeypatch.setattr(P, "obtener_pronostico", lambda *a, **k: None)
    pron = obtener_pronostico_para_despacho(db)
    assert pron is not None
    assert pron["desactualizado_horas"] >= 9.0
    assert "⛅" in formatear_pronostico_despacho(pron)


# 6. Integración en el despacho.
def test_despacho_con_pronostico_primera_seccion(db: Database):
    hoy = date(2026, 8, 30)
    db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO")
    texto = formatear_despacho_matutino(db, hoy=hoy, pronostico=_pron_base())
    assert "⛅ <b>CLIMA & PRONÓSTICO (7 DÍAS):</b>" in texto
    # Clima va ANTES de las secciones clásicas (retiros / inseminaciones / recordatorios).
    assert texto.index("⛅") < texto.index("Inseminaciones AM")


def test_despacho_sin_pronostico_sin_seccion_clima(db: Database):
    hoy = date(2026, 8, 30)
    db.registrar_animal(tag="101", sexo="Hembra", estado="ACTIVO")
    texto = formatear_despacho_matutino(db, hoy=hoy)
    assert "⛅" not in texto
    assert "DESPACHO MATUTINO" in texto
