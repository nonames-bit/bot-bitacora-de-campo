"""Vista del operario (TRABAJADOR), pedida por Jaime el 2026-10-10: no
registra ventas ni ingresos/gastos ("ellos no venden nada") y tiene la
pantalla "Potreros" para verificar en campo si están todos los animales."""
import json
from pathlib import Path

from src.db.database import Database
from src.engine.dashboard_data import listado_potreros
from src.pwa.app import crear_app


def _setup(tmp_path):
    db_path = str(tmp_path / "bitacora.db")
    db = Database(db_path).create_tables()
    db.registrar_potrero(nombre="La Loma", codigo="P1")
    db.registrar_potrero(nombre="El Bajo", codigo="P2")
    db.registrar_animal("47", nombre="Carranga", sexo="Hembra", fecha_nacimiento="2019-01-01",
                        potrero="La Loma", estado="ACTIVO")
    db.registrar_animal("50", sexo="Hembra", fecha_nacimiento="2025-06-01", potrero="La Loma", estado="ACTIVO")
    db.registrar_animal("60", sexo="Macho", fecha_nacimiento="2024-01-01", potrero="El Bajo", estado="ACTIVO")
    db.registrar_animal("99", sexo="Hembra", fecha_nacimiento="2018-01-01", potrero="La Loma", estado="VENDIDO")
    db.registrar_animal("70", sexo="Macho", fecha_nacimiento="2024-01-01", estado="ACTIVO")
    db.close()
    users = [
        {"user_id": 1, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"},
        {"user_id": 4, "nombre": "Pedro", "rol": "TRABAJADOR", "pin": "3333"},
    ]
    u_path = str(tmp_path / "users.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump(users, f)
    app = crear_app(db_path, users_file=u_path, password="master-password")
    app.config.update({"TESTING": True})
    return app, db_path


def _cliente(app, pin):
    c = app.test_client()
    c.post("/login", data={"pin": pin})
    return c


def _contar(db_path, sql):
    db = Database(db_path)
    try:
        return db.query_one(sql)["n"]
    finally:
        db.close()


def test_operario_no_registra_ventas_ni_dinero(tmp_path):
    app, db_path = _setup(tmp_path)
    r = _cliente(app, "3333").post("/api/sync", json={"eventos": [
        {"tipo": "venta", "id_local": "v1", "payload": {"animal_tag": "47", "precio": 1000}},
        {"tipo": "gasto", "id_local": "g1", "payload": {"tipo_finanza": "EGRESO", "monto": 5000,
                                                         "categoria": "SAL"}},
        {"tipo": "pesaje", "id_local": "p1", "payload": {"animal_tag": "47", "peso": 450}},
    ]}).get_json()
    assert len(r["errores"]) == 2 and all("operario" in e for e in r["errores"])
    # Salen de la cola offline: reintentarlos no los arregla.
    assert set(r["ids_ok"]) == {"v1", "g1", "p1"}
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM finanzas") == 0
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM registros_pendientes") == 0
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM animales WHERE tag = '47' AND estado = 'ACTIVO'") == 1


def test_operario_no_lee_facturas(tmp_path):
    app, _ = _setup(tmp_path)
    r = _cliente(app, "3333").post("/api/finanzas/analizar-factura", json={"foto_base64": "x"})
    assert r.status_code == 403


def test_owner_sigue_vendiendo(tmp_path):
    app, db_path = _setup(tmp_path)
    r = _cliente(app, "1234").post("/api/sync", json={"eventos": [
        {"tipo": "venta", "payload": {"animal_tag": "47", "precio": 1000}}]}).get_json()
    assert r["errores"] == []
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM animales WHERE tag = '47' AND estado = 'ACTIVO'") == 0


def test_listado_potreros_solo_activos(tmp_path):
    _, db_path = _setup(tmp_path)
    db = Database(db_path)
    try:
        res = listado_potreros(db)
    finally:
        db.close()
    pots = {p["nombre"]: p for p in res["potreros"]}
    assert [p["nombre"] for p in res["potreros"]] == ["El Bajo", "La Loma", "Sin potrero"]
    assert sorted(a["tag"] for a in pots["La Loma"]["animales"]) == ["47", "50"]  # el 99 está vendido
    assert pots["La Loma"]["total"] == 2
    assert [a["tag"] for a in pots["Sin potrero"]["animales"]] == ["70"]
    assert res["total_animales"] == 4
    vaca = next(a for a in pots["La Loma"]["animales"] if a["tag"] == "47")
    assert vaca["nombre"] == "Carranga" and vaca["categoria"]


def test_operario_abre_potreros(tmp_path):
    app, _ = _setup(tmp_path)
    r = _cliente(app, "3333").get("/api/potreros/listado")
    assert r.status_code == 200
    assert r.get_json()["total_animales"] == 4


def test_app_js_vista_del_operario():
    js = (Path(__file__).resolve().parent.parent / "src" / "pwa" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'var TIPOS_SOLO_GESTION = ["venta", "gasto"]' in js
    assert '"agenda", "potreros"]' in js
    assert "function renderPotreros" in js and "precargarPotreros();" in js


def test_conteo_de_potrero_queda_registrado(tmp_path):
    # Jaime (2026-10-10): cada conteo queda como registro con fecha, quién
    # contó y qué animales faltaron. Llega por la cola offline (/api/sync).
    app, db_path = _setup(tmp_path)
    trab = _cliente(app, "3333")
    r = trab.post("/api/sync", json={"eventos": [
        {"tipo": "conteo_potrero", "id_local": "c1", "fecha": "2026-10-10",
         "payload": {"potrero_id": 1, "potrero_nombre": "La Loma", "hora": "15:20",
                     "vistos": ["47"], "faltantes": ["50"]}},
        {"tipo": "conteo_potrero", "id_local": "c2", "payload": {"potrero_id": 1, "vistos": [], "faltantes": []}},
    ]}).get_json()
    assert set(r["ids_ok"]) == {"c1", "c2"}
    assert len(r["errores"]) == 1 and "Conteo NO guardado" in r["errores"][0]
    # Reenviar el mismo conteo desde la cola no lo duplica.
    trab.post("/api/sync", json={"eventos": [
        {"tipo": "conteo_potrero", "id_local": "c1", "payload": {"potrero_id": 1, "vistos": ["47"]}}]})
    conteos = _cliente(app, "1234").get("/api/potreros/conteos?potrero_id=1").get_json()["conteos"]
    assert len(conteos) == 1
    c = conteos[0]
    assert (c["fecha"], c["hora"], c["potrero"], c["total"], c["vistos"]) == ("2026-10-10", "15:20", "La Loma", 2, 1)
    assert c["faltantes"] == ["50"] and c["por"] == "Pedro"
    # No toca el inventario.
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO'") == 4


def test_app_js_conteo_con_ficha_e_inventario():
    js = (Path(__file__).resolve().parent.parent / "src" / "pwa" / "static" / "app.js").read_text(encoding="utf-8")
    assert "data-accion='ir-conteo-potreros'" in js  # botón en Inventario
    assert "pot-ver-ficha" in js and "btn-volver-conteo" in js
    assert 'enviarEventoLt("conteo_potrero"' in js
