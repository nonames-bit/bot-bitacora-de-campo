"""Tests Etapa D Fase 7: backend PWA (solo lectura, URL de ficha QR)."""
import os

import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.db.database import Database
from src.pwa.app import crear_app, datos_ficha, datos_tablero


@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora.db")
    d = Database(ruta)
    d.create_tables()
    d.registrar_potrero(nombre="Guayabal", codigo="G1")
    d.registrar_animal("47", sexo="Hembra", raza="C", estado="ACTIVO",
                       potrero="Guayabal", fecha_nacimiento="2022-01-10")
    d.registrar_animal("99", sexo="Hembra", estado="VENDIDO", potrero="Guayabal")
    d.registrar_parto("47", fecha="2026-08-20", sexo_cria="Macho")
    d.close()
    return ruta


@pytest.fixture
def client(db_file):
    app = crear_app(db_file)
    assert app is not None
    app.config.update({"TESTING": True})
    return app.test_client()


def test_import_app_y_tablero_lectura(client):
    r = client.get("/api/tablero")
    assert r.status_code == 200
    d = r.get_json()
    assert d["activos"] == 1  # estricto ACTIVO: 47 sí, 99 no
    assert "por_potrero" in d


def test_endpoints_lectura_repro_sanidad_pasturas_leche(client):
    for ep in ("/api/repro", "/api/sanidad", "/api/pasturas", "/api/leche"):
        r = client.get(ep)
        assert r.status_code == 200, ep
        assert isinstance(r.get_json(), dict)


def test_ficha_qr_url(client, db_file):
    r = client.get("/api/ficha/47")
    assert r.status_code == 200
    d = r.get_json()
    assert d["existe"] is True
    assert d["qr_payload"] == "JA://animal/47"
    assert d["qr_url"] == "/ficha/47"
    # Vista HTML de la ficha QR.
    html = client.get("/ficha/47")
    assert html.status_code == 200
    # Helper directo también respeta el payload.
    assert datos_ficha("47", db_file)["qr_url"] == "/ficha/47"
    assert datos_tablero(db_file)["activos"] == 1
