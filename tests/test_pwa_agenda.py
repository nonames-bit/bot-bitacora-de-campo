"""Agenda PWA: crear/completar eventos y campanita (recordatorios /programar)."""
import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora.db")
    d = Database(ruta)
    d.create_tables()
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


def test_agenda_sin_sesion_401(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    c = app.test_client()
    assert c.get("/api/agenda").status_code == 401
    assert c.post("/api/agenda/recordatorio", json={}).status_code == 401


def test_crear_recordatorio_y_listarlo_en_agenda(client, db_file):
    r = client.post("/api/agenda/recordatorio", json={
        "mensaje": "Vacunar aftosa lote ordeño",
        "fecha": "2026-09-20",
        "hora": "06:30",
    })
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    agenda = client.get("/api/agenda").get_json()
    msgs = [x["mensaje"] for x in agenda["recordatorios"]]
    assert "Vacunar aftosa lote ordeño" in msgs
    rec = next(x for x in agenda["recordatorios"] if x["mensaje"] == "Vacunar aftosa lote ordeño")
    assert rec["estado"] == "PENDIENTE"
    assert rec["fecha"] == "2026-09-20"

    badges = client.get("/api/badges").get_json()
    assert badges["agenda"] >= 1


def test_crear_recordatorio_valida_campos(client):
    assert client.post("/api/agenda/recordatorio", json={"fecha": "2026-09-20"}).status_code == 400
    assert client.post("/api/agenda/recordatorio", json={"mensaje": "X", "fecha": "no-fecha"}).status_code == 400
    assert client.post("/api/agenda/recordatorio", json={
        "mensaje": "X", "fecha": "2026-09-20", "hora": "25:00"}).status_code == 400
    assert client.post("/api/agenda/recordatorio", json={
        "mensaje": "x" * 501, "fecha": "2026-09-20"}).status_code == 400


def test_completar_recordatorio_cambia_estado(client):
    rid = client.post("/api/agenda/recordatorio", json={
        "mensaje": "Rotar potrero", "fecha": "2026-09-21"}).get_json()["id"]
    r = client.post(f"/api/agenda/recordatorio/{rid}/completar")
    assert r.status_code == 200
    assert r.get_json()["estado"] == "ENVIADO"
    # Ya no aparece entre pendientes de la agenda.
    agenda = client.get("/api/agenda").get_json()
    assert all(x["id"] != rid for x in agenda["recordatorios"])


def test_completar_inexistente_404(client):
    assert client.post("/api/agenda/recordatorio/999999/completar").status_code == 404
