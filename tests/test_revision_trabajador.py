"""Bandeja "Por revisar": partos, muertes, ventas y traslados de un
TRABAJADOR quedan en pausa hasta que un OWNER/ADMIN los apruebe."""
import json

from src.bot.bot_interface import Bot
from src.db.database import Database
from src.engine import revision
from src.pwa.app import crear_app


def _setup(tmp_path):
    db_path = str(tmp_path / "bitacora.db")
    db = Database(db_path).create_tables()
    db.registrar_animal("47", sexo="Hembra", fecha_nacimiento="2019-01-01", potrero="P1", estado="ACTIVO")
    db.registrar_animal("50", sexo="Hembra", fecha_nacimiento="2018-01-01", potrero="P1", estado="ACTIVO")
    db.close()
    users = [
        {"user_id": 1, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"},
        {"user_id": 2, "nombre": "Admin", "rol": "ADMIN", "pin": "2222"},
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


def _contar(db_path, sql, params=()):
    db = Database(db_path)
    try:
        return db.query_one(sql, params)["n"]
    finally:
        db.close()


def test_requiere_revision_solo_trabajador_y_delicados():
    assert revision.requiere_revision("TRABAJADOR", "parto")
    assert revision.requiere_revision("trabajador", "Muerte")
    assert revision.requiere_revision("TRABAJADOR", "venta")
    assert revision.requiere_revision("TRABAJADOR", "traslado")
    assert not revision.requiere_revision("TRABAJADOR", "pesaje")
    assert not revision.requiere_revision("TRABAJADOR", "celo")
    assert not revision.requiere_revision("ADMIN", "parto")
    assert not revision.requiere_revision("OWNER", "muerte")


def test_trabajador_parto_queda_en_pausa_y_pesaje_entra(tmp_path):
    app, db_path = _setup(tmp_path)
    trab = _cliente(app, "3333")
    r = trab.post("/api/sync", json={"eventos": [
        {"tipo": "parto", "id_local": "p1", "fecha": "2026-09-30",
         "payload": {"vaca_tag": "47", "sexo_cria": "HEMBRA", "id_cria_tag": "47-1"}},
        {"tipo": "muerte", "id_local": "m1", "payload": {"animal_tag": "50", "causa_presunta": "Rayo"}},
        {"tipo": "pesaje", "id_local": "w1", "payload": {"animal_tag": "47", "peso_kg": 420}},
    ]}).get_json()
    assert r["ok"] and r["en_revision"] == 2
    assert sorted(r["ids_ok"]) == ["m1", "p1", "w1"]
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM partos") == 0
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM muertes") == 0
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM animales WHERE tag = '50' AND estado = 'ACTIVO'") == 1
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM pesajes") == 1
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM mensajes_equipo WHERE texto LIKE '%Queda por revisar%'") == 2

    # Reenviar la misma cola offline no duplica los pendientes.
    trab.post("/api/sync", json={"eventos": [
        {"tipo": "parto", "id_local": "p1", "payload": {"vaca_tag": "47"}}]})
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM registros_pendientes") == 2


def test_admin_no_queda_en_pausa(tmp_path):
    app, db_path = _setup(tmp_path)
    adm = _cliente(app, "2222")
    r = adm.post("/api/sync", json={"eventos": [
        {"tipo": "muerte", "id_local": "m1", "payload": {"animal_tag": "50"}}]}).get_json()
    assert r["en_revision"] == 0
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM muertes") == 1


def test_bandeja_solo_para_owner_y_admin(tmp_path):
    app, _ = _setup(tmp_path)
    trab = _cliente(app, "3333")
    trab.post("/api/sync", json={"eventos": [{"tipo": "muerte", "payload": {"animal_tag": "50"}}]})
    assert trab.get("/api/revision/pendientes").status_code == 403
    assert trab.get("/api/revision/contador").get_json()["total"] == 0
    assert trab.post("/api/revision/1/aprobar", json={}).status_code == 403
    assert trab.post("/api/revision/1/rechazar", json={}).status_code == 403
    adm = _cliente(app, "2222")
    assert adm.get("/api/revision/contador").get_json()["total"] == 1


def test_aprobar_registra_a_nombre_del_trabajador(tmp_path):
    app, db_path = _setup(tmp_path)
    _cliente(app, "3333").post("/api/sync", json={"eventos": [
        {"tipo": "muerte", "fecha": "2026-09-30", "payload": {"animal_tag": "50", "causa_presunta": "Rayo"}}]})
    owner = _cliente(app, "1234")
    lista = owner.get("/api/revision/pendientes").get_json()
    assert lista["total"] == 1
    p = lista["pendientes"][0]
    assert p["registrado_por_nombre"] == "Pedro"
    assert p["resumen"] == "Muerte de la 50 · Rayo"
    assert {"clave": "causa_presunta", "etiqueta": "Causa", "valor": "Rayo"} in p["campos"]

    r = owner.post(f"/api/revision/{p['id']}/aprobar", json={}).get_json()
    assert r["ok"] and r["restantes"] == 0
    db = Database(db_path)
    try:
        m = db.query_one("SELECT registrado_por, fecha FROM muertes")
        assert (m["registrado_por"], m["fecha"]) == (4, "2026-09-30")
        assert db.query_one("SELECT estado FROM animales WHERE tag = '50'")["estado"] == "MUERTO"
        fila = db.query_one("SELECT estado, revisado_por_nombre FROM registros_pendientes")
        assert (fila["estado"], fila["revisado_por_nombre"]) == ("APROBADO", "Duenio")
    finally:
        db.close()
    # Aprobar dos veces no registra dos muertes.
    assert owner.post(f"/api/revision/{p['id']}/aprobar", json={}).status_code == 409
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM muertes") == 1


def test_corregir_y_aprobar(tmp_path):
    app, db_path = _setup(tmp_path)
    _cliente(app, "3333").post("/api/sync", json={"eventos": [
        {"tipo": "muerte", "payload": {"animal_tag": "99", "causa_presunta": "Rayo"}}]})
    adm = _cliente(app, "2222")
    pid = adm.get("/api/revision/pendientes").get_json()["pendientes"][0]["id"]
    # Una clave que el registro no traía se ignora.
    r = adm.post(f"/api/revision/{pid}/aprobar",
                 json={"cambios": {"animal_tag": "50", "registrado_por": 1}}).get_json()
    assert r["ok"] and r["corregido"]
    db = Database(db_path)
    try:
        assert db.query_one("SELECT estado FROM animales WHERE tag = '50'")["estado"] == "MUERTO"
        assert db.query_one("SELECT registrado_por FROM muertes")["registrado_por"] == 4
        fila = db.obtener_pendiente(pid)
        assert fila["datos"]["animal_tag"] == "50"
        assert fila["nota_revision"] == "Corregido antes de aprobar"
        assert fila["resumen"] == "Muerte de la 50 · Rayo"
    finally:
        db.close()


def test_aprobar_con_error_lo_deja_pendiente(tmp_path):
    app, db_path = _setup(tmp_path)
    _cliente(app, "3333").post("/api/sync", json={"eventos": [
        {"tipo": "venta", "payload": {"animal_tag": "NOEXISTE", "precio": 1000}}]})
    adm = _cliente(app, "2222")
    pid = adm.get("/api/revision/pendientes").get_json()["pendientes"][0]["id"]
    r = adm.post(f"/api/revision/{pid}/aprobar", json={})
    assert r.status_code == 422
    assert "Venta NO guardada" in r.get_json()["error"]
    assert adm.get("/api/revision/contador").get_json()["total"] == 1


def test_rechazar_no_registra_y_avisa(tmp_path):
    app, db_path = _setup(tmp_path)
    _cliente(app, "3333").post("/api/sync", json={"eventos": [
        {"tipo": "parto", "payload": {"vaca_tag": "47", "sexo_cria": "MACHO"}}]})
    owner = _cliente(app, "1234")
    pid = owner.get("/api/revision/pendientes").get_json()["pendientes"][0]["id"]
    r = owner.post(f"/api/revision/{pid}/rechazar", json={"motivo": "Esa vaca no está preñada"}).get_json()
    assert r["ok"]
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM partos") == 0
    assert _contar(db_path, "SELECT COUNT(*) AS n FROM mensajes_equipo WHERE texto LIKE '%rechazó%no está preñada%'") == 1
    revisados = owner.get("/api/revision/pendientes").get_json()["revisados"]
    assert revisados[0]["estado"] == "RECHAZADO"
    assert owner.post(f"/api/revision/{pid}/rechazar", json={}).status_code == 409


def test_bot_trabajador_parto_queda_por_revisar_y_se_aplica(tmp_path):
    db = Database(str(tmp_path / "b.db")).create_tables()
    db.registrar_animal("47", sexo="Hembra", fecha_nacimiento="2019-01-01", estado="ACTIVO")
    bot = Bot(db)
    resp = bot.procesar_texto("murió la 47", user_id=4, rol="TRABAJADOR", nombre="Pedro")
    assert "quedó por revisar" in resp
    assert db.query_one("SELECT COUNT(*) AS n FROM muertes")["n"] == 0
    p = db.listar_pendientes()[0]
    assert (p["origen"], p["tipo"], p["registrado_por_nombre"], p["canal"]) == ("bot", "muerte", "Pedro", "Telegram")
    bot.aplicar_evento_revisado(p["datos"], user_id=4)
    assert db.query_one("SELECT registrado_por FROM muertes")["registrado_por"] == 4
    # Sin rol (OWNER por Telegram, CLI) se registra de una como siempre.
    db.registrar_animal("48", estado="ACTIVO")
    bot.procesar_texto("murió la 48", user_id=1, rol="OWNER")
    assert db.query_one("SELECT COUNT(*) AS n FROM muertes")["n"] == 2
    db.close()


def test_pantalla_por_revisar_en_la_app(tmp_path):
    from pathlib import Path

    app, _ = _setup(tmp_path)
    html = _cliente(app, "1234").get("/").get_data(as_text=True)
    # Va en Gestión, oculto hasta que el RBAC lo muestre a OWNER/ADMIN.
    assert 'id="btn-nav-revision"' in html and 'id="sheet-item-revision"' in html
    js = (Path(__file__).resolve().parent.parent / "src" / "pwa" / "static" / "app.js").read_text(encoding="utf-8")
    assert "function renderRevision" in js and "/api/revision/pendientes" in js
    assert '"revision"' in js.split("var VISTAS_BADGE")[1].split(";")[0]
