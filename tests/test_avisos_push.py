"""Avisos push: filtro por usuario, estado real, prueba por el servicio push
y avisos del programador (resumen de la mañana y urgentes sin repetir)."""
from datetime import date, timedelta

import pytest

from scripts import programador
from src.db.database import Database
from src.pwa.app import crear_app
from src.server import push_sender

HOY = date.today()


def _d(n):
    return (HOY + timedelta(days=n)).isoformat()


@pytest.fixture
def ruta(tmp_path):
    r = str(tmp_path / "p.db")
    Database(r).create_tables().close()
    return r


def _sus(db, endpoint, uid):
    db.guardar_push_suscripcion(endpoint, user_id=uid, p256dh="k", auth="a")


def test_listar_suscripciones_por_usuario(ruta):
    db = Database(ruta)
    _sus(db, "https://push/1", 1)
    _sus(db, "https://push/2", 2)
    _sus(db, "https://push/sin", None)
    assert {s["endpoint"] for s in db.listar_push_suscripciones(solo_user_ids=[1])} == {"https://push/1"}
    assert {s["endpoint"] for s in db.listar_push_suscripciones(solo_user_ids=[None, 2])} == {"https://push/2", "https://push/sin"}
    assert db.listar_push_suscripciones(solo_user_ids=[]) == []
    db.close()


def test_estado_y_probar_real(ruta, monkeypatch):
    app = crear_app(ruta, password="x")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "x"})
    monkeypatch.setattr(push_sender, "vapid_configurado", lambda: False)
    est = c.get("/api/push/estado").get_json()
    assert est["servidor_listo"] is False and est["suscripciones_reales"] == 0
    assert c.post("/api/push/probar").get_json()["motivo"] == "servidor_sin_llaves"

    monkeypatch.setattr(push_sender, "vapid_configurado", lambda: True)
    assert c.post("/api/push/probar").get_json()["motivo"] == "sin_suscripcion"
    db = Database(ruta)
    _sus(db, "https://push/mio", None)       # contraseña maestra = sin user_id
    _sus(db, "https://push/otro", 99)
    db.close()
    enviados = []
    monkeypatch.setattr(push_sender, "webpush", lambda subscription_info, **kw: enviados.append(subscription_info["endpoint"]))
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "x")
    monkeypatch.setenv("VAPID_CLAIMS_EMAIL", "a@b.c")
    r = c.post("/api/push/probar").get_json()
    assert r["ok"] and r["enviados"] == 1 and enviados == ["https://push/mio"]  # solo los del usuario
    assert c.get("/api/push/estado").get_json()["suscripciones_reales"] == 1


def test_resumen_diario_y_urgentes_sin_repetir(ruta, tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(programador, "DB", __import__("pathlib").Path(ruta))
    users = tmp_path / "u.json"
    users.write_text(json.dumps([{"user_id": 7, "rol": "OWNER"}, {"user_id": 8, "rol": "TRABAJADOR"}]))
    monkeypatch.setattr(programador, "USERS_FILE", users)
    assert programador._destinatarios_push() == [None, 7]
    db = Database(ruta)
    db.registrar_animal("ATR", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-2000))
    db.registrar_diagnostico("ATR", fecha=_d(-300), resultado="PREÑADA", dias_gestacion=10)  # ~310 d: atrasada
    db.registrar_animal("RET", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-2000))
    db.registrar_tratamiento("RET", fecha=_d(-5), producto="Oxitetraciclina", fecha_fin_retiro_leche=_d(0))
    db.close()
    enviados = []
    monkeypatch.setattr(programador, "push", lambda titulo, cuerpo, **kw: enviados.append((titulo, cuerpo, kw)))

    claves = {k.split(":")[0] for k, _ in programador.avisos_urgentes(HOY)}
    assert {"parto_atrasado", "retiro_fin"} <= claves
    n = programador.push_urgentes(HOY)
    assert n >= 2 and enviados and all(kw.get("urgente") for _, _, kw in enviados)
    enviados.clear()
    assert programador.push_urgentes(HOY) == 0 and enviados == []  # no repite

    programador.push_resumen_diario()
    assert enviados and enviados[0][0] == "🐄 Tareas de hoy" and "parto" in enviados[0][1]
