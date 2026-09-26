# -*- coding: utf-8 -*-
"""Pruebas para eliminación de eventos (solo rol OWNER)."""
import os
import tempfile
import pytest
from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    d = Database(path)
    d.create_tables()
    yield d
    try:
        d.close()
    except Exception:
        pass
    try:
        os.remove(path)
    except Exception:
        pass


def test_eliminar_parto_con_cria_fantasma(db):
    """Eliminar un parto accidental debe borrar el parto y la cría si no tiene otros eventos."""
    vaca_id = db.resolve_animal("VACA_TEST", crear=True, sexo="Hembra")
    pid = db.registrar_parto(
        vaca_tag="VACA_TEST",
        fecha="2026-09-13",
        id_cria_tag="CRIA_FANTASMA_01",
        sexo_cria="Macho",
        estado_cria="VIVO",
    )
    assert pid is not None
    cria_id = db.resolve_animal("CRIA_FANTASMA_01")
    assert cria_id is not None

    # Eliminar el parto
    res = db.eliminar_evento("parto", pid)
    assert res["ok"] is True
    assert res["tipo"] == "parto"

    # Verificar que el parto ya no existe
    assert db.query_one("SELECT id FROM partos WHERE id = ?", (pid,)) is None

    # Verificar que la cría fantasma fue removida
    assert db.query_one("SELECT id_animal FROM animales WHERE id_animal = ?", (cria_id,)) is None


def test_eliminar_pesaje(db):
    aid = db.resolve_animal("ANIMAL_PES", crear=True)
    pes_id = db.registrar_pesaje(animal_tag="ANIMAL_PES", fecha="2026-09-13", peso_kg=450.0)
    assert pes_id is not None
    assert db.query_one("SELECT id FROM pesajes WHERE id = ?", (pes_id,)) is not None

    res = db.eliminar_evento("pesaje", pes_id)
    assert res["ok"] is True
    assert db.query_one("SELECT id FROM pesajes WHERE id = ?", (pes_id,)) is None


def test_eliminar_tratamiento(db):
    aid = db.resolve_animal("ANIMAL_TRAT", crear=True)
    tid = db.registrar_tratamiento(
        animal_tag="ANIMAL_TRAT",
        fecha="2026-09-13",
        producto="Oxitetraciclina",
        dosis="20ml",
        dias_retiro_carne=15,
        dias_retiro_leche=5,
    )
    assert tid is not None

    res = db.eliminar_evento("tratamiento", tid)
    assert res["ok"] is True
    assert db.query_one("SELECT id FROM tratamientos WHERE id = ?", (tid,)) is None


def test_eliminar_traslado_restaura_potrero(db):
    pot_a = db.execute("INSERT INTO potreros (nombre) VALUES ('Potrero A')").lastrowid
    pot_b = db.execute("INSERT INTO potreros (nombre) VALUES ('Potrero B')").lastrowid
    aid = db.resolve_animal("ANIMAL_TRAS", crear=True)
    db.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (pot_a, aid))

    # Trasladar a potrero B
    tras_id = db.registrar_traslado(animal_tag="ANIMAL_TRAS", potrero_destino="Potrero B", potrero_origen="Potrero A", fecha="2026-09-13")
    an_tras = db.get_animal("ANIMAL_TRAS")
    assert an_tras["potrero_id"] == pot_b

    # Eliminar traslado -> debe restaurar a potrero A
    res = db.eliminar_evento("traslado", tras_id)
    assert res["ok"] is True
    an_restaurado = db.get_animal("ANIMAL_TRAS")
    assert an_restaurado["potrero_id"] == pot_a


def test_eliminar_muerte_restaura_activo(db):
    aid = db.resolve_animal("ANIMAL_MUERTO", crear=True)
    mid = db.registrar_muerte(animal_tag="ANIMAL_MUERTO", fecha="2026-09-13", causa_presunta="Desconocida")
    an = db.get_animal("ANIMAL_MUERTO")
    assert an["estado"] == "MUERTO"

    res = db.eliminar_evento("muerte", mid)
    assert res["ok"] is True
    an_revivido = db.get_animal("ANIMAL_MUERTO")
    assert an_revivido["estado"] == "ACTIVO"


def test_api_eliminar_evento_control_acceso_rbac():
    """Solo el rol OWNER puede llamar a /api/eventos/eliminar (401/403 para otros roles)."""
    fd_db, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd_db)
    fd_u, users_path = tempfile.mkstemp(suffix=".json")
    os.close(fd_u)
    import json
    users_data = [
        {"user_id": 1, "username": "owner", "rol": "OWNER"},
        {"user_id": 2, "username": "pepe", "rol": "TRABAJADOR"},
        {"user_id": 3, "username": "admin", "rol": "ADMIN"},
    ]
    with open(users_path, "w", encoding="utf-8") as f:
        json.dump(users_data, f)

    d = Database(db_path)
    d.create_tables()
    pid = d.registrar_pesaje("TAG_X", "2026-09-13", 380.0)
    d.close()

    app = crear_app(db_path=db_path, users_file=users_path)
    client = app.test_client()

    # 1. Sin sesión -> 401
    r = client.post("/api/eventos/eliminar", json={"tipo": "pesaje", "id": pid})
    assert r.status_code == 401

    # 2. Con rol TRABAJADOR -> 403
    with client.session_transaction() as sess:
        sess["autenticado"] = True
        sess["user_id"] = 2
        sess["username"] = "pepe"
        sess["rol"] = "TRABAJADOR"
    r2 = client.post("/api/eventos/eliminar", json={"tipo": "pesaje", "id": pid})
    assert r2.status_code == 403

    # 3. Con rol ADMIN -> 403 Forbidden (exclusivo para rol OWNER)
    with client.session_transaction() as sess:
        sess["autenticado"] = True
        sess["user_id"] = 3
        sess["username"] = "admin"
        sess["rol"] = "ADMIN"
    # Registrar otro pesaje para intentar borrar con admin
    d_admin = Database(db_path)
    pid_admin = d_admin.registrar_pesaje("TAG_X", "2026-09-14", 390.0)
    d_admin.close()
    r3 = client.post("/api/eventos/eliminar", json={"tipo": "pesaje", "id": pid_admin})
    assert r3.status_code == 403
    assert r3.get_json()["ok"] is False

    # 4. Con rol OWNER -> 200 OK y eliminado
    with client.session_transaction() as sess:
        sess["autenticado"] = True
        sess["user_id"] = 1
        sess["username"] = "owner"
        sess["rol"] = "OWNER"
    r4 = client.post("/api/eventos/eliminar", json={"tipo": "pesaje", "id": pid})
    assert r4.status_code == 200
    data = r4.get_json()
    assert data["ok"] is True

    # Eliminar también el segundo con rol OWNER
    r4_admin = client.post("/api/eventos/eliminar", json={"tipo": "pesaje", "id": pid_admin})
    assert r4_admin.status_code == 200

    # Verificar que ambos pesajes fueron eliminados por OWNER
    d_check = Database(db_path)
    assert d_check.query_one("SELECT id FROM pesajes WHERE id = ?", (pid,)) is None
    assert d_check.query_one("SELECT id FROM pesajes WHERE id = ?", (pid_admin,)) is None
    d_check.close()

    # 5. Probar GET /api/eventos/recientes
    r_recientes = client.get("/api/eventos/recientes?limite=10")
    assert r_recientes.status_code == 200
    rec_data = r_recientes.get_json()
    assert rec_data["ok"] is True
    assert isinstance(rec_data["eventos"], list)

    for p in (db_path, users_path):
        try:
            os.remove(p)
        except Exception:
            pass


def test_potrero_resolucion_prioriza_vigente_sobre_historico():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = Database(db_path).create_tables()
        # Crear potrero 17 histórico y potrero 29 vigente ambos llamados OLEGARIO II
        id_hist = db.insert("potreros", {"codigo": "17", "nombre": "OLEGARIO II"})
        id_vig = db.insert("potreros", {"codigo": "B02", "nombre": "OLEGARIO II", "geom_wkt_4326": "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"})

        # Resolver por nombre debe dar el vigente
        assert db.resolve_potrero("OLEGARIO II") == id_vig
        # Resolver por código exacto debe respetar el código
        assert db.resolve_potrero("17") == id_hist
        assert db.resolve_potrero("B02") == id_vig

        # Probar saneamiento de animal en potrero histórico
        db.conn.execute("INSERT INTO animales (tag, potrero_id, estado, fecha_nacimiento) VALUES ('JA457', ?, 'HISTORICO', '2020-06-07')", (id_hist,))
        db.conn.commit()
        db.create_tables()
        an = db.get_animal("JA457")
        assert an["potrero_id"] == id_vig
        assert an["estado"] == "ACTIVO"
        db.close()
    finally:
        try:
            os.remove(db_path)
        except Exception:
            pass

