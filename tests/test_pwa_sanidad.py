"""Sanidad PWA: registro directo de tratamientos y retiros con días restantes."""
from datetime import date, timedelta

import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora.db")
    d = Database(ruta)
    d.create_tables()
    d.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    d.registrar_animal("99", sexo="Hembra", estado="VENDIDO")
    d.close()
    return ruta


@pytest.fixture
def client(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    assert app is not None
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave-de-prueba"})
    return c


def test_sanidad_sin_sesion_401(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    c = app.test_client()
    assert c.get("/api/sanidad").status_code == 401
    assert c.post("/api/sanidad/tratamiento", json={}).status_code == 401


def test_crear_tratamiento_y_ver_retiro_con_dias(client):
    hoy = date.today().isoformat()
    r = client.post("/api/sanidad/tratamiento", json={
        "tag": "47", "producto": "Oxitetraciclina 20%",
        "principio_activo": "Oxitetraciclina", "dosis": "20 ml",
        "via": "IM", "fecha": hoy,
        "dias_retiro_leche": 3, "dias_retiro_carne": 21,
    })
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["ok"] is True
    assert body["tag"] == "47"

    san = client.get("/api/sanidad").get_json()
    assert any(t["tag"] == "47" and t.get("principio_activo") == "Oxitetraciclina"
               for t in san["ultimos_tratamientos"])
    fin_carne = (date.today() + timedelta(days=21)).isoformat()
    ret = next(x for x in san["retiros"] if x["tag"] == "47")
    assert ret["fecha_fin_retiro_carne"] == fin_carne
    assert ret["fecha_fin_retiro_carne_dias"] == 21
    assert ret["fecha_fin_retiro_leche_dias"] == 3


def test_crear_tratamiento_rechaza_no_activo_e_inexistente(client):
    r = client.post("/api/sanidad/tratamiento", json={"tag": "99", "producto": "Ivermectina"})
    assert r.status_code == 400
    r2 = client.post("/api/sanidad/tratamiento", json={"tag": "XX999", "producto": "Ivermectina"})
    assert r2.status_code == 404


def test_crear_tratamiento_valida_campos(client):
    assert client.post("/api/sanidad/tratamiento", json={"producto": "X"}).status_code == 400
    assert client.post("/api/sanidad/tratamiento", json={"tag": "47"}).status_code == 400
    assert client.post("/api/sanidad/tratamiento",
                       json={"tag": "47", "producto": "X", "via": "NOPE"}).status_code == 400
    assert client.post("/api/sanidad/tratamiento",
                       json={"tag": "47", "producto": "X", "fecha": "no-fecha"}).status_code == 400
    assert client.post("/api/sanidad/tratamiento",
                       json={"tag": "47", "producto": "X", "dias_retiro_leche": 999}).status_code == 400
