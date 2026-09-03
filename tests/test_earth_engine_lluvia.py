"""Pruebas unitarias del pipeline de lluvia satelital vía Google Earth Engine (Fase D).

Todas las pruebas mockean el módulo `ee` (Earth Engine) por completo — no hacen
llamadas de red reales ni requieren credenciales. Validan la búsqueda de la
fecha más reciente disponible en CHIRPS (que puede estar semanas atrás de
"hoy", ver docstring de `earth_engine_lluvia.py`), la agregación de la
ventana de acumulación y el manejo de zonas sin cobertura CHIRPS.
"""
from __future__ import annotations

import sys
import types

import pytest

from src.gis import earth_engine_lluvia as gee_lluvia
from src.gis import earth_engine_ndvi as gee_ndvi


class _V:
    """Envoltorio que imita el `.getInfo()` de Earth Engine sobre un valor ya resuelto."""

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
    def __init__(self, fecha_str):
        self._fecha = fecha_str

    def get(self, clave):
        return self._fecha


class _FakeAccumImage:
    def __init__(self, mm):
        self._mm = mm

    def reduceRegion(self, **kwargs):
        return _V({"precipitation": self._mm})


class _FakeImageCollection:
    """Colección CHIRPS falsa: `n_imagenes` decide si hay cobertura en absoluto;
    `fecha_reciente` es lo que devuelve la búsqueda de la fecha más reciente
    disponible; `mm_total` es lo que suma la ventana de acumulación."""

    def __init__(self, n_imagenes: int, fecha_reciente=None, mm_total=0.0):
        self._n = n_imagenes
        self._fecha_reciente = fecha_reciente
        self._mm_total = mm_total

    def filterBounds(self, geom):
        return self

    def filterDate(self, ini, fin):
        return self

    def sort(self, *a, **k):
        return self

    def size(self):
        return _V(self._n)

    def first(self):
        return _FakeImage(self._fecha_reciente)

    def select(self, banda):
        return self

    def sum(self):
        return _FakeAccumImage(self._mm_total)


def _fake_ee_module(n_imagenes: int, fecha_reciente=None, mm_total: float = 0.0):
    ee = types.SimpleNamespace()

    class _Point:
        def __init__(self, coords):
            self.coords = coords

        def buffer(self, radio_m):
            return ("buffer", self.coords, radio_m)

    ee.Geometry = types.SimpleNamespace(Point=_Point)
    ee.ImageCollection = lambda nombre: _FakeImageCollection(n_imagenes, fecha_reciente, mm_total)
    ee.Image = lambda x: x
    ee.Date = lambda x: _DateWrapper(x)

    class _Reducer:
        @staticmethod
        def mean():
            return object()

    ee.Reducer = _Reducer
    ee.ServiceAccountCredentials = lambda email, key: ("creds", email, key)
    ee.Initialize = lambda creds, project=None: None
    return ee


@pytest.fixture(autouse=True)
def _reset_inicializado(monkeypatch):
    monkeypatch.setattr(gee_ndvi, "_inicializado", False)
    yield
    gee_ndvi._inicializado = False


def test_estimar_lluvia_finca_usa_la_fecha_mas_reciente_disponible_no_hoy(monkeypatch):
    # CHIRPS tiene latencia real: la última imagen disponible puede estar semanas
    # antes de la fecha de corrida del job (hallazgo probado en vivo el 2026-09-03).
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module(n_imagenes=1, fecha_reciente="2026-07-31", mm_total=87.4))
    gee_ndvi._inicializado = True

    resultado = gee_lluvia.estimar_lluvia_finca(3.40, -74.08)

    assert resultado is not None
    assert resultado["fecha_fin"] == "2026-07-31"  # no la fecha de hoy
    assert resultado["mm_estimado"] == pytest.approx(87.4)
    assert resultado["dias_acumulados"] == 30
    assert "CHIRPS" in resultado["fuente"]


def test_estimar_lluvia_finca_sin_cobertura_en_absoluto_devuelve_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module(n_imagenes=0))
    gee_ndvi._inicializado = True

    resultado = gee_lluvia.estimar_lluvia_finca(3.40, -74.08)
    assert resultado is None


def test_estimar_lluvia_finca_redondea_a_un_decimal(monkeypatch):
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module(n_imagenes=1, fecha_reciente="2026-08-15", mm_total=42.3333))
    gee_ndvi._inicializado = True

    resultado = gee_lluvia.estimar_lluvia_finca(3.40, -74.08)
    assert resultado["mm_estimado"] == pytest.approx(42.3)


def test_estimar_lluvia_finca_maneja_error_de_earth_engine(monkeypatch):
    ee = types.SimpleNamespace()
    ee.Geometry = types.SimpleNamespace(Point=lambda coords: types.SimpleNamespace(buffer=lambda r: None))

    def _falla(nombre):
        raise RuntimeError("timeout simulado de Earth Engine")

    ee.ImageCollection = _falla
    ee.ServiceAccountCredentials = lambda email, key: ("creds", email, key)
    ee.Initialize = lambda creds, project=None: None
    monkeypatch.setitem(sys.modules, "ee", ee)
    gee_ndvi._inicializado = True

    resultado = gee_lluvia.estimar_lluvia_finca(3.40, -74.08)
    assert resultado is None
