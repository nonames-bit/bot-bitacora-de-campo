"""Cobertura de endpoints (P2.14): telemetría GPS y pesaje de manga.

El CI medía 66% en `src/pwa/app.py` (4.7k líneas); estos endpoints no tenían
prueba dedicada. Todos los apps usan DB y `users.json` temporales (ver
`tests/test_aislamiento_rutas.py`).
"""
import json
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora.db")
    d = Database(ruta)
    d.create_tables()
    d.registrar_potrero(nombre="Guayabal", codigo="G1")
    d.registrar_animal("T1", sexo="Hembra", raza="C", estado="ACTIVO",
                       potrero="Guayabal", fecha_nacimiento="2022-01-10")
    d.close()
    return ruta


@pytest.fixture
def client_owner(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave-de-prueba"})
    return c


@pytest.fixture
def client_trabajador(tmp_path, db_file):
    users = [{"user_id": 300, "nombre": "Carlos", "rol": "TRABAJADOR", "pin": "7777"}]
    u_path = str(tmp_path / "users_trab.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump(users, f)
    app = crear_app(db_file, users_file=u_path, password="master-password")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"pin": "7777"})
    return c


# ---------------------------------------------------------------- telemetría GPS

def test_telemetria_ping_sin_coordenadas_400(client_owner):
    assert client_owner.post("/api/telemetria/ping", json={}).status_code == 400


def test_telemetria_ping_coordenadas_no_numericas_400(client_owner):
    r = client_owner.post("/api/telemetria/ping", json={"lat": "x", "lon": "y"})
    assert r.status_code == 400


def test_telemetria_ping_valido(client_owner):
    r = client_owner.post("/api/telemetria/ping",
                          json={"lat": 3.395, "lon": -74.065, "precision_m": 5,
                                "evento_origen": "test"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    # Dentro de la finca devuelve telemetria_id; fuera, "ignorado" — ambos válidos.
    assert "telemetria_id" in d or d.get("ignorado") is True


def test_telemetria_rutas_owner_ok(client_owner):
    r = client_owner.get("/api/telemetria/rutas")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True and "rutas" in d and "rondas" in d


def test_telemetria_rutas_trabajador_403(client_trabajador):
    r = client_trabajador.get("/api/telemetria/rutas")
    assert r.status_code == 403


# ------------------------------------------------------------------ pesaje manga

def test_manga_pesaje_sin_datos_400(client_owner):
    assert client_owner.post("/api/manga/pesaje", json={}).status_code == 400
    assert client_owner.post("/api/manga/pesaje", json={"tag": "T1"}).status_code == 400


def test_manga_pesaje_peso_no_numerico_400(client_owner):
    r = client_owner.post("/api/manga/pesaje", json={"tag": "T1", "peso_kg": "pesado"})
    assert r.status_code == 400


def test_manga_pesaje_valido_sin_pesaje_previo(client_owner):
    r = client_owner.post("/api/manga/pesaje", json={"tag": "T1", "peso_kg": 300})
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True and d["tag"] == "T1" and d["peso_kg"] == 300.0
    assert d["peso_anterior"] is None
    assert d["gmd_g_dia"] is None


def test_manga_pesaje_calcula_gmd_con_pesaje_previo(client_owner, db_file):
    # Pesaje previo 30 días antes: 270 kg -> 300 kg hoy => GMD 1000 g/día.
    d = Database(db_file)
    try:
        aid = d.animal_id("T1")
        hace_30 = (date.today() - timedelta(days=30)).isoformat()
        d.execute(
            "INSERT INTO pesajes (animal_id, fecha, peso_kg, evento) VALUES (?, ?, ?, ?)",
            (aid, hace_30, 270.0, "PESAJE"),
        )
    finally:
        d.close()

    r = client_owner.post("/api/manga/pesaje", json={"tag": "T1", "peso_kg": 300})
    assert r.status_code == 200
    d = r.get_json()
    assert d["peso_anterior"] == 270.0
    assert d["dias_entre_pesajes"] == 30
    assert d["gmd_g_dia"] == 1000.0
