"""Modo Campo (mayordomo): el TRABAJADOR abre Captura, Agenda-hoy,
Ficha y GPS desde 4 botones grandes; las APIs que usa responden 200."""
import json

import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")


def _app_trabajador(tmp_path):
    from src.db.database import Database
    from src.pwa.app import crear_app

    ruta = str(tmp_path / "campo.db")
    d = Database(ruta)
    d.create_tables()
    d.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    d.close()
    u_path = str(tmp_path / "users_campo.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump([{"user_id": 300, "nombre": "T", "rol": "TRABAJADOR", "pin": "1111"}], f)
    app = crear_app(ruta, users_file=u_path, password="x")
    assert app is not None
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"pin": "1111"})
    return app, c


def test_trabajador_abre_agenda(tmp_path):
    _, c = _app_trabajador(tmp_path)
    r = c.get("/api/agenda?dias=7")
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert "eventos" in cuerpo and "retiros" in cuerpo and "recordatorios" in cuerpo


def test_trabajador_gps_sin_mapa(tmp_path):
    # El mapa satelital es solo oficina (403), pero el GPS de campo
    # (detectar potrero + guardar ronda, como el /aqui del bot) sí abre.
    _, c = _app_trabajador(tmp_path)
    assert c.get("/api/mapa/datos").status_code == 403
    r = c.post("/api/gps/potrero", json={"lat": 3.395, "lon": -74.065})
    assert r.status_code == 200
    assert r.get_json()["detectado"] is False
    r2 = c.post("/api/gps/ronda", json={"lat": 3.395, "lon": -74.065,
                                        "potrero_nombre": "Prueba",
                                        "punto_control": "recorrido"})
    assert r2.status_code == 200
    assert r2.get_json()["ok"] is True


def test_index_trae_vista_campo(tmp_path):
    _, c = _app_trabajador(tmp_path)
    html = c.get("/").get_data(as_text=True)
    assert 'data-v="campo"' in html
    assert "Modo Campo" in html
