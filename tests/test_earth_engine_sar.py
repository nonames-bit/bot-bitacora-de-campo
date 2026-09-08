"""Pruebas unitarias del pipeline de Radar SAR (Sentinel-1 GRD) vía Earth Engine.

Mockea el módulo `ee` (Earth Engine) por completo para validar el control de flujo,
el cálculo de RVI (Dual-Pol Radar Vegetation Index), el mapeo a SAR-NDVI,
la estimación de humedad por banda C y el fallback automático desde Sentinel-2
cuando hay nubosidad. No requiere red ni credenciales para correr en CI.
"""
from __future__ import annotations

import sys
import types
from datetime import date

import pytest

from src.gis import earth_engine_ndvi as gee_ndvi
from src.gis import earth_engine_sar as gee_sar

WKT_POTRERO = "POLYGON((-74.07 3.39, -74.06 3.39, -74.06 3.40, -74.07 3.40, -74.07 3.39))"


class _V:
    """Envoltorio que imita `.getInfo()` de Earth Engine."""

    def __init__(self, value):
        self._value = value

    def getInfo(self):
        return self._value


class _DateWrapper:
    def __init__(self, valor):
        self._valor = valor

    def format(self, fmt):
        return _V(self._valor)


class _FakeImage:
    """Imagen SAR falsa: soporta operaciones de bandas, potencia y reducción."""

    def __init__(self, stats: dict, name: str | None = None):
        self.stats = stats
        self.name = name

    def select(self, banda):
        return _FakeImage(self.stats, banda)

    def divide(self, val):
        return self

    def pow(self, exp):
        return self

    def multiply(self, val):
        return self

    def add(self, otra):
        return self

    def subtract(self, otra):
        return self

    def rename(self, nuevo_nombre):
        return self

    def reduceRegion(self, **kwargs):
        return _V(self.stats)

    def get(self, clave):
        if clave == "system:time_start":
            return self.stats.get("fecha_raw", 1700000000000)
        if clave == "orbitProperties_pass":
            return _V(self.stats.get("orbit_pass", "DESCENDING"))
        return _V(None)


class _FakeList:
    def __init__(self, items):
        self._items = items

    def get(self, i):
        return self._items[i]


class _FakeImageCollection:
    def __init__(self, imagenes: list[_FakeImage]):
        self._imagenes = imagenes

    def filterBounds(self, geom):
        return self

    def filterDate(self, ini, fin):
        return self

    def filter(self, expr):
        return self

    def sort(self, campo, reverse=False):
        return self

    def size(self):
        return _V(len(self._imagenes))

    def toList(self, n):
        return _FakeList(self._imagenes[:n])


def _instalar_mock_ee_sar(monkeypatch, imagenes_s1: list[_FakeImage]):
    fake_ee = types.ModuleType("ee")
    fake_ee.ImageCollection = lambda nombre: _FakeImageCollection(imagenes_s1)
    fake_ee.Image = lambda *a, **k: a[0] if a and isinstance(a[0], _FakeImage) else _FakeImage({"VV": -9.0, "VH": -15.0, "RVI": 0.85, "CR": -6.0})
    fake_ee.Image.cat = lambda imgs: imgs[0]
    fake_ee.Geometry = lambda geojson: geojson
    fake_ee.Date = lambda ms: _DateWrapper("2026-08-21")

    class _Filter:
        @staticmethod
        def listContains(prop, val):
            return "filter_list"

        @staticmethod
        def eq(prop, val):
            return "filter_eq"

    fake_ee.Filter = _Filter

    class _Reducer:
        @staticmethod
        def mean():
            return "reducer_mean"

    fake_ee.Reducer = _Reducer

    monkeypatch.setitem(sys.modules, "ee", fake_ee)
    return fake_ee


def test_estimar_humedad_sar():
    pct1, desc1 = gee_sar.estimar_humedad_sar(-7.0)
    assert pct1 == 100.0
    assert "saturado" in desc1

    pct2, desc2 = gee_sar.estimar_humedad_sar(-18.0)
    assert pct2 == 0.0
    assert "seco" in desc2

    pct3, desc3 = gee_sar.estimar_humedad_sar(-12.0)
    assert 50.0 <= pct3 <= 60.0
    assert "favorable" in desc3


def test_calcular_sar_ndvi():
    # RVI bajo (suelo desnudo / sobrepastoreo)
    ndvi_bajo = gee_sar.calcular_sar_ndvi(0.10)
    assert 0.20 <= ndvi_bajo <= 0.30

    # RVI medio (pastura en rebrote)
    ndvi_medio = gee_sar.calcular_sar_ndvi(0.50)
    assert 0.50 <= ndvi_medio <= 0.55

    # RVI alto (pastura densa y vigorosa en reposo)
    ndvi_alto = gee_sar.calcular_sar_ndvi(0.90)
    assert 0.75 <= ndvi_alto <= 0.80

    # Clamping
    assert gee_sar.calcular_sar_ndvi(2.0) == 0.85
    assert gee_sar.calcular_sar_ndvi(-0.5) == 0.20


def test_sar_region_sentinel1_exito(monkeypatch):
    stats = {
        "VV": -9.87,
        "VH": -15.40,
        "RVI": 0.946,
        "CR": -5.53,
        "orbit_pass": "DESCENDING",
        "fecha_raw": 1724236920000,
    }
    _instalar_mock_ee_sar(monkeypatch, [_FakeImage(stats)])

    res = gee_sar._sar_region_sentinel1(WKT_POTRERO, date(2026, 8, 25))
    assert res is not None
    assert res["rvi"] == 0.946
    assert 0.75 <= res["ndvi_promedio"] <= 0.85
    assert res["vv_db"] == -9.87
    assert res["vh_db"] == -15.40
    assert res["cr_db"] == -5.53
    assert res["cobertura_nubes_pct"] == 0.0
    assert res["orbit_pass"] == "DESCENDING"
    assert res["fecha_imagen"] == "2026-08-21"
    assert 70.0 <= res["humedad_pct"] <= 80.0


def test_sar_region_sentinel1_sin_imagenes(monkeypatch):
    _instalar_mock_ee_sar(monkeypatch, [])
    res = gee_sar._sar_region_sentinel1(WKT_POTRERO, date(2026, 8, 25))
    assert res is None


def test_actualizar_lecturas_sar(monkeypatch):
    stats = {"VV": -10.0, "VH": -15.0, "RVI": 0.80, "CR": -5.0}
    _instalar_mock_ee_sar(monkeypatch, [_FakeImage(stats)])
    monkeypatch.setattr(gee_sar, "inicializar_ee", lambda: None)

    potreros = [
        {"id": 1, "nombre": "Potrero A", "area_has": 10.0, "geom_wkt_4326": WKT_POTRERO},
        {"id": 2, "nombre": "Sin Geom", "area_has": 5.0, "geom_wkt_4326": None},
    ]

    lecturas = gee_sar.actualizar_lecturas_sar(potreros, fecha=date(2026, 8, 25))
    assert len(lecturas) == 1
    l = lecturas[0]
    assert l["potrero_id"] == 1
    assert l["potrero_nombre"] == "Potrero A"
    assert "Sentinel-1 SAR" in l["fuente"]
    assert l["cobertura_nubes_pct"] == 0.0
    assert l["aforo_estimado_kg_m2"] > 0
    assert l["biomasa_estimada_kg_ha"] > 0
    assert l["rvi"] == 0.80
    assert l["sensor"] == "SAR_SENTINEL1"


def test_fallback_automatico_sentinel2_a_sentinel1(monkeypatch):
    """Verifica que si Sentinel-2 óptico no tiene imagen limpia (nubes),
    actualizar_lecturas_reales recurre automáticamente al radar SAR Sentinel-1."""
    # Simular que Sentinel-2 no tiene imagen limpia
    monkeypatch.setattr(gee_ndvi, "_ndvi_region_sentinel2", lambda geom, f: None)
    monkeypatch.setattr(gee_ndvi, "inicializar_ee", lambda: None)

    # Simular que Sentinel-1 SAR sí tiene lectura
    stats_sar = {
        "rvi": 0.88,
        "ndvi_promedio": 0.77,
        "ndvi_min": 0.73,
        "ndvi_max": 0.81,
        "vv_db": -9.5,
        "vh_db": -15.1,
        "cr_db": -5.6,
        "humedad_pct": 77.3,
        "humedad_desc": "Suelo muy húmedo / saturado",
        "orbit_pass": "DESCENDING",
        "cobertura_nubes_pct": 0.0,
        "fecha_imagen": "2026-08-21",
    }
    monkeypatch.setattr(gee_sar, "_sar_region_sentinel1", lambda geom, f, **k: stats_sar)

    potreros = [{"id": 4, "nombre": "Potrero Nublado", "area_has": 12.0, "geom_wkt_4326": WKT_POTRERO}]
    res = gee_ndvi.actualizar_lecturas_reales(potreros, modo="auto")

    assert len(res) == 1
    item = res[0]
    assert item["potrero_nombre"] == "Potrero Nublado"
    assert "Sentinel-1 SAR" in item["fuente"]
    assert item["sensor"] == "SAR_SENTINEL1"
    assert item["ndvi_promedio"] == 0.77
    assert item["rvi"] == 0.88
    assert item["cobertura_nubes_pct"] == 0.0
