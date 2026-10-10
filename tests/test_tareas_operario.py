"""Tareas del operario (Jaime, 2026-10-10): el dueño y el administrador
asignan; el operario no asigna, solo ve las suyas y las completa con foto."""
import base64
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.database import Database  # noqa: E402
from src.pwa import tareas_equipo  # noqa: E402
from src.pwa.app import crear_app  # noqa: E402

USUARIOS = [
    {"user_id": 1, "telegram_id": 111, "nombre": "Jaime", "rol": "OWNER", "pin": "1234"},
    {"user_id": 2, "telegram_id": 222, "nombre": "Pepito Perez", "rol": "TRABAJADOR", "pin": "5678"},
    {"user_id": 3, "telegram_id": 333, "nombre": "Sebas", "rol": "TRABAJADOR", "pin": "9012"},
    {"user_id": 4, "telegram_id": 444, "nombre": "Ana", "rol": "ADMIN", "pin": "3456"},
]


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    db_file = str(tmp_path / "t.db")
    users_file = str(tmp_path / "users.json")
    Path(users_file).write_text(json.dumps(USUARIOS), encoding="utf-8")
    Database(db_file).create_tables().close()
    avisos = []
    monkeypatch.setattr(
        tareas_equipo, "avisar",
        lambda db, titulo, cuerpo, user_ids, url="/?v=captura": avisos.append((titulo, list(user_ids))),
    )
    app = crear_app(db_file, users_file=users_file, password="x")
    app.config["TESTING"] = True
    c = app.test_client()
    c.avisos = avisos
    return c


def _entrar(c, uid):
    u = next(u for u in USUARIOS if u["user_id"] == uid)
    with c.session_transaction() as s:
        s["autenticado"] = True
        s["user_id"] = uid
        s["nombre"] = u["nombre"]
        s["rol"] = u["rol"]


def _foto():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "green").save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _crear(c, **extra):
    datos = {"mensaje": "Revisar cerca del potrero 3", "fecha": "2026-10-11"}
    datos.update(extra)
    return c.post("/api/agenda/recordatorio", json=datos)


def test_operario_no_asigna_tareas(cliente):
    _entrar(cliente, 2)
    r = _crear(cliente, asignado_a="Sebas")
    assert r.status_code == 403
    r = cliente.post("/api/sync", json={"eventos": [
        {"tipo": "tarea", "id_local": "x1", "payload": {"mensaje": "algo", "fecha": "2026-10-11"}},
    ]})
    assert r.status_code == 200
    _entrar(cliente, 1)
    assert cliente.get("/api/agenda").get_json()["recordatorios"] == []


def test_admin_asigna_a_una_persona_y_le_llega_aviso(cliente):
    _entrar(cliente, 4)
    r = _crear(cliente, asignado_a="Pepito Perez", asignado_a_id=2, prioridad="URGENTE")
    assert r.status_code == 200
    assert r.get_json()["asignado_a_id"] == 2
    assert cliente.avisos == [("📋 URGENTE · Tarea de Ana", [2])]


def test_operario_ve_solo_sus_tareas(cliente):
    _entrar(cliente, 1)
    _crear(cliente, mensaje="Para Pepito", asignado_a_id=2)
    _crear(cliente, mensaje="Para Sebas", asignado_a="Sebas")  # solo nombre: se resuelve a id 3
    _crear(cliente, mensaje="Para todos", asignado_a="Todo el equipo")
    assert sorted(cliente.avisos[-1][1]) == [2, 3]  # "Todo el equipo" avisa a los operarios

    _entrar(cliente, 2)
    mias = [t["mensaje"] for t in cliente.get("/api/tareas/mias").get_json()["tareas"]]
    assert sorted(mias) == ["Para Pepito", "Para todos"]
    agenda = [t["mensaje"] for t in cliente.get("/api/agenda").get_json()["recordatorios"]]
    assert sorted(agenda) == ["Para Pepito", "Para todos"]

    _entrar(cliente, 1)
    assert len(cliente.get("/api/agenda").get_json()["recordatorios"]) == 3


def test_operario_completa_con_foto_obligatoria(cliente):
    _entrar(cliente, 1)
    rid = _crear(cliente, asignado_a_id=2).get_json()["id"]
    otra = _crear(cliente, asignado_a_id=3).get_json()["id"]

    _entrar(cliente, 2)
    r = cliente.post(f"/api/agenda/recordatorio/{rid}/completar", json={"notas": "Listo"})
    assert r.status_code == 400  # sin foto
    r = cliente.post(f"/api/agenda/recordatorio/{otra}/completar", json={"foto_base64": _foto()})
    assert r.status_code == 403  # es de Sebas
    r = cliente.post(f"/api/agenda/recordatorio/{rid}/completar",
                     json={"foto_base64": _foto(), "notas": "Listo", "completado_por": "Jaime"})
    assert r.status_code == 200
    assert r.get_json()["completado_por"] == "Pepito Perez"  # firma con su nombre, no el que mande
    assert cliente.avisos[-1] == ("✅ Pepito Perez terminó una tarea", [1])
    assert cliente.get("/api/tareas/mias").get_json()["tareas"] == []
    r = cliente.post(f"/api/agenda/recordatorio/{rid}/completar", json={"foto_base64": _foto()})
    assert r.status_code == 409


def test_integrantes_trae_ids_de_personas(cliente):
    _entrar(cliente, 1)
    integ = cliente.get("/api/equipo/integrantes").get_json()["integrantes"]
    pepito = next(i for i in integ if i["nombre"] == "Pepito Perez")
    assert pepito["id"] == 2
    assert any(i["nombre"] == "Todo el equipo" for i in integ)


def test_numero_de_agenda_del_operario_cuenta_solo_las_suyas(cliente):
    _entrar(cliente, 1)
    _crear(cliente, asignado_a_id=2)
    _crear(cliente, asignado_a_id=3)
    assert cliente.get("/api/badges").get_json()["agenda"] == 2
    _entrar(cliente, 2)
    assert cliente.get("/api/badges").get_json()["agenda"] == 1


def test_dueno_ve_todas_admin_solo_suyas_y_de_trabajadores(cliente):
    _entrar(cliente, 1)
    _crear(cliente, mensaje="Para Pepito", asignado_a_id=2)
    _crear(cliente, mensaje="Para Ana", asignado_a_id=4)
    rid_jaime = _crear(cliente, mensaje="Para Jaime", asignado_a_id=1).get_json()["id"]
    assert len(cliente.get("/api/agenda").get_json()["recordatorios"]) == 3
    assert len(cliente.get("/api/tablero").get_json()["tareas_asignadas"]) == 3

    _entrar(cliente, 4)
    agenda = sorted(t["mensaje"] for t in cliente.get("/api/agenda").get_json()["recordatorios"])
    assert agenda == ["Para Ana", "Para Pepito"]
    tablero = sorted(t["mensaje"] for t in cliente.get("/api/tablero").get_json()["tareas_asignadas"])
    assert tablero == ["Para Ana", "Para Pepito"]
    r = cliente.post(f"/api/agenda/recordatorio/{rid_jaime}/completar", json={"notas": "x"})
    assert r.status_code == 403
