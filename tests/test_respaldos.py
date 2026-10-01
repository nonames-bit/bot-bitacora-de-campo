"""Fase F: copias de seguridad desde la app (Sistema → Copias, solo OWNER)
y restauración sin systemctl (sirve con Docker)."""
import json
import sqlite3

import pytest

from src.db.database import Database
from src.engine import respaldos
from src.pwa.app import crear_app


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    db_path = tmp_path / "bitacora.db"
    db = Database(str(db_path)).create_tables()
    db.registrar_animal("47", sexo="Hembra", fecha_nacimiento="2019-01-01", estado="ACTIVO")
    db.close()
    dir_b = tmp_path / "backups"
    dir_b.mkdir()
    monkeypatch.setenv("BACKUPS_DIR", str(dir_b))
    u = tmp_path / "users.json"
    u.write_text(json.dumps([
        {"user_id": 1, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"},
        {"user_id": 2, "nombre": "Admin", "rol": "ADMIN", "pin": "2222"},
    ]), encoding="utf-8")
    app = crear_app(str(db_path), users_file=str(u), password="master-password")
    app.config.update({"TESTING": True})
    return app, db_path, dir_b


def _tags(db_path):
    with sqlite3.connect(db_path) as c:
        return sorted(r[0] for r in c.execute("SELECT tag FROM animales"))


def _cliente(app, pin):
    c = app.test_client()
    c.post("/login", data={"pin": pin})
    return c


def test_copiar_y_restaurar_con_copia_previa(entorno):
    _, db_path, dir_b = entorno
    nombre = respaldos.crear_copia(db_path, dir_b)
    assert nombre.startswith("manual_") and (dir_b / nombre).is_file()
    db = Database(str(db_path))
    db.registrar_animal("99", estado="ACTIVO")
    db.close()
    assert _tags(db_path) == ["47", "99"]

    previa = respaldos.restaurar(nombre, db_path, dir_b)
    assert _tags(db_path) == ["47"]
    # Lo que había antes quedó guardado y se puede volver a ello.
    assert previa.startswith("antes_de_restaurar_")
    respaldos.restaurar(previa, db_path, dir_b)
    assert _tags(db_path) == ["47", "99"]


def test_no_acepta_nombres_fuera_de_backups(entorno):
    _, db_path, dir_b = entorno
    for malo in ("../bitacora.db", "/etc/passwd", "2026-01-01.db", "x.db"):
        with pytest.raises(ValueError):
            respaldos.ruta_copia(malo, dir_b)


def test_no_restaura_una_copia_danada(entorno):
    _, db_path, dir_b = entorno
    (dir_b / "2026-09-30.db").write_bytes(b"no es una base")
    with pytest.raises(ValueError):
        respaldos.restaurar("2026-09-30.db", db_path, dir_b)
    assert _tags(db_path) == ["47"]


def test_rutas_solo_para_owner(entorno):
    app, _, _ = entorno
    adm = _cliente(app, "2222")
    assert adm.get("/api/respaldos").status_code == 403
    assert adm.post("/api/respaldos/crear").status_code == 403
    assert adm.post("/api/respaldos/2026-09-30.db/restaurar", json={"confirmacion": "RESTAURAR"}).status_code == 403


def test_flujo_desde_la_app(entorno):
    app, db_path, _ = entorno
    owner = _cliente(app, "1234")
    nombre = owner.post("/api/respaldos/crear").get_json()["nombre"]
    copias = owner.get("/api/respaldos").get_json()["copias"]
    assert [c["nombre"] for c in copias] == [nombre]
    r = owner.get(f"/api/respaldos/{nombre}/descargar")
    assert r.status_code == 200 and r.data[:16] == b"SQLite format 3\x00"

    db = Database(str(db_path))
    db.registrar_animal("99", estado="ACTIVO")
    db.close()
    # Sin escribir RESTAURAR no hace nada.
    assert owner.post(f"/api/respaldos/{nombre}/restaurar", json={}).status_code == 400
    assert _tags(db_path) == ["47", "99"]
    res = owner.post(f"/api/respaldos/{nombre}/restaurar", json={"confirmacion": "restaurar"}).get_json()
    assert res["ok"] and res["copia_previa"].startswith("antes_de_restaurar_")
    assert _tags(db_path) == ["47"]
    with sqlite3.connect(db_path) as c:
        assert c.execute("SELECT COUNT(*) FROM mensajes_equipo WHERE texto LIKE '%restauró la base%'").fetchone()[0] == 1


def test_script_ya_no_usa_systemctl():
    from pathlib import Path
    sh = (Path(__file__).resolve().parent.parent / "scripts" / "restaurar_backup.sh").read_text(encoding="utf-8")
    assert "systemctl" not in sh and "src.engine.respaldos" in sh
