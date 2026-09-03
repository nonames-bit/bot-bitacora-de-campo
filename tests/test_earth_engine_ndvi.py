"""Pruebas unitarias del pipeline de NDVI real vía Google Earth Engine (Fase C).

Todas las pruebas mockean el módulo `ee` (Earth Engine) por completo — no hacen
llamadas de red reales ni requieren credenciales. Validan el control de flujo
propio del módulo: selección de la imagen más reciente con cobertura útil sobre
el polígono, manejo de ventanas sin datos aprovechables, y mapeo del resultado
al formato que consume `Database.registrar_lectura_ndvi`.
"""
from __future__ import annotations

import sys
import types

import pytest

from src.gis import earth_engine_ndvi as gee

WKT_CUADRADO = "POLYGON((-74.07 3.39, -74.06 3.39, -74.06 3.40, -74.07 3.40, -74.07 3.39))"


class _V:
    """Envoltorio que imita el `.getInfo()` de Earth Engine sobre un valor ya resuelto."""

    def __init__(self, value):
        self._value = value

    def getInfo(self):
        return self._value


class _ReducerObj:
    def combine(self, otro, sharedInputs=True):
        return self


class _DateWrapper:
    def __init__(self, valor):
        self._valor = valor

    def format(self, fmt):
        return _V(self._valor)


class _FakeImage:
    """Imagen falsa; el perfil (`profile`) decide qué devuelve `reduceRegion` según
    el último nombre de banda asignado con `.rename()` (replica el flujo real del
    módulo: máscara SCL renombrada a "frac", NDVI renombrado a "NDVI")."""

    def __init__(self, profile: dict, name: str | None = None):
        self.profile = profile
        self.name = name

    def select(self, banda):
        return _FakeImage(self.profile, banda)

    def eq(self, valor):
        return _FakeImage(self.profile, "mask_parte")

    def Or(self, otra):
        return _FakeImage(self.profile, "mask")

    def rename(self, nombre):
        return _FakeImage(self.profile, nombre)

    def updateMask(self, mascara):
        return self

    def normalizedDifference(self, bandas):
        return _FakeImage(self.profile, "ndvi_crudo")

    def reduceRegion(self, **kwargs):
        if self.name == "frac":
            return _V({"frac": self.profile["frac"]})
        if self.name == "NDVI":
            return _V({
                "NDVI_mean": self.profile["ndvi_mean"],
                "NDVI_min": self.profile["ndvi_min"],
                "NDVI_max": self.profile["ndvi_max"],
            })
        return _V({})

    def get(self, clave):
        return self.profile["fecha"]


class _FakeList:
    def __init__(self, items):
        self._items = items

    def get(self, i):
        return self._items[i]


class _FakeImageCollection:
    def __init__(self, imagenes):
        self._imagenes = imagenes

    def filterBounds(self, geom):
        return self

    def filterDate(self, ini, fin):
        return self

    def sort(self, *a, **k):
        return self

    def size(self):
        return _V(len(self._imagenes))

    def toList(self, n):
        return _FakeList(self._imagenes[:n])


def _fake_ee_module(imagenes: list[_FakeImage]):
    ee = types.SimpleNamespace()
    ee.Geometry = lambda geojson: geojson
    ee.Image = lambda x: x
    ee.ImageCollection = lambda nombre: _FakeImageCollection(list(imagenes))
    ee.Date = lambda x: _DateWrapper(x)

    class _Reducer:
        @staticmethod
        def mean():
            return _ReducerObj()

        @staticmethod
        def minMax():
            return _ReducerObj()

    ee.Reducer = _Reducer
    ee.ServiceAccountCredentials = lambda email, key: ("creds", email, key)
    ee.Initialize = lambda creds, project=None: None
    return ee


@pytest.fixture(autouse=True)
def _reset_inicializado(monkeypatch):
    monkeypatch.setattr(gee, "_inicializado", False)
    yield
    gee._inicializado = False


def test_inicializar_ee_falla_sin_credenciales(monkeypatch):
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_EMAIL", raising=False)
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_KEY_PATH", raising=False)
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module([]))

    with pytest.raises(RuntimeError, match="Faltan credenciales"):
        gee.inicializar_ee()


def test_inicializar_ee_falla_si_no_existe_el_archivo(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module([]))
    ruta_inexistente = tmp_path / "no-existe.json"

    with pytest.raises(RuntimeError, match="No existe el archivo"):
        gee.inicializar_ee(
            service_account_email="bot@proyecto.iam.gserviceaccount.com",
            key_path=str(ruta_inexistente),
        )


def test_inicializar_ee_exitoso(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module([]))
    key_file = tmp_path / "clave.json"
    key_file.write_text("{}", encoding="utf-8")

    gee.inicializar_ee(
        service_account_email="bot@proyecto.iam.gserviceaccount.com",
        key_path=str(key_file),
        project_id="proyecto-x",
    )
    assert gee._inicializado is True


def test_actualizar_lecturas_reales_omite_potrero_sin_geometria(monkeypatch):
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module([]))
    gee._inicializado = True

    potreros = [{"id": 1, "nombre": "Sin Geometría", "area_has": 10.0}]
    resultado = gee.actualizar_lecturas_reales(potreros)
    assert resultado == []


def test_actualizar_lecturas_reales_elige_la_imagen_mas_reciente_con_cobertura_util(monkeypatch):
    perfil_nublado = {"frac": 0.3, "fecha": "2026-08-30", "ndvi_mean": 0.9, "ndvi_min": 0.9, "ndvi_max": 0.9}
    perfil_bueno = {"frac": 0.8, "fecha": "2026-08-25", "ndvi_mean": 0.612, "ndvi_min": 0.55, "ndvi_max": 0.70}

    imagenes = [_FakeImage(perfil_nublado), _FakeImage(perfil_bueno)]
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module(imagenes))
    gee._inicializado = True

    potreros = [{"id": 25, "nombre": "Corral Santamartha", "area_has": 1.24, "geom_wkt_4326": WKT_CUADRADO}]
    resultado = gee.actualizar_lecturas_reales(potreros)

    assert len(resultado) == 1
    lectura = resultado[0]
    assert lectura["potrero_id"] == 25
    assert lectura["fecha"] == "2026-08-25"  # se saltó la imagen nublada del 30
    assert lectura["ndvi_promedio"] == pytest.approx(0.612)
    assert lectura["ndvi_min"] == pytest.approx(0.55)
    assert lectura["ndvi_max"] == pytest.approx(0.70)
    assert lectura["cobertura_nubes_pct"] == pytest.approx(20.0)  # 100 * (1 - 0.8)
    assert "Google Earth Engine" in lectura["fuente"]
    assert lectura["categoria"] in ("ÓPTIMO / REPOSO", "EXCELENTE")


def test_actualizar_lecturas_reales_sin_imagen_util_devuelve_vacio(monkeypatch):
    perfil_muy_nublado = {"frac": 0.1, "fecha": "2026-08-30", "ndvi_mean": 0.6, "ndvi_min": 0.5, "ndvi_max": 0.7}
    imagenes = [_FakeImage(perfil_muy_nublado)]
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module(imagenes))
    gee._inicializado = True

    potreros = [{"id": 30, "nombre": "Potrero Nublado", "area_has": 5.0, "geom_wkt_4326": WKT_CUADRADO}]
    resultado = gee.actualizar_lecturas_reales(potreros)
    assert resultado == []


def test_actualizar_lecturas_reales_continua_si_un_potrero_falla(monkeypatch):
    perfil_bueno = {"frac": 0.9, "fecha": "2026-08-25", "ndvi_mean": 0.60, "ndvi_min": 0.55, "ndvi_max": 0.65}
    monkeypatch.setitem(sys.modules, "ee", _fake_ee_module([_FakeImage(perfil_bueno)]))
    gee._inicializado = True

    llamadas = {"n": 0}
    original = gee._ndvi_region_sentinel2

    def _falla_primero(geom_wkt, fecha_fin, **kwargs):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise RuntimeError("timeout simulado de Earth Engine")
        return original(geom_wkt, fecha_fin, **kwargs)

    monkeypatch.setattr(gee, "_ndvi_region_sentinel2", _falla_primero)

    potreros = [
        {"id": 1, "nombre": "Potrero A (falla)", "area_has": 5.0, "geom_wkt_4326": WKT_CUADRADO},
        {"id": 2, "nombre": "Potrero B (ok)", "area_has": 5.0, "geom_wkt_4326": WKT_CUADRADO},
    ]
    resultado = gee.actualizar_lecturas_reales(potreros)

    assert len(resultado) == 1
    assert resultado[0]["potrero_id"] == 2
