"""Regresiones de seguridad de la revisión integral (RBAC de la PWA y users.json)."""
import json

from src.pwa.app import crear_app
from src.server.auth import Auth
from src.db.database import Database


def _setup(tmp_path):
    db_path = str(tmp_path / "bitacora.db")
    Database(db_path).create_tables().close()
    users = [
        {"user_id": 1, "nombre": "Duenio", "rol": "OWNER", "pin": "1234", "telegram_id": 6123051140},
        {"user_id": 2, "nombre": "Admin", "rol": "ADMIN", "pin": "2222"},
        {"user_id": 3, "nombre": "Admin2", "rol": "ADMIN", "pin": "4444"},
        {"user_id": 4, "nombre": "Trabajador", "rol": "TRABAJADOR", "pin": "3333"},
    ]
    u_path = str(tmp_path / "users.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump(users, f)
    app = crear_app(db_path, users_file=u_path, password="master-password")
    app.config.update({"TESTING": True})
    return app, u_path, db_path


def _cliente(app, pin):
    c = app.test_client()
    c.post("/login", data={"pin": pin})
    return c


def test_admin_no_cambia_pin_del_owner_via_telegram_id(tmp_path):
    app, u_path, _ = _setup(tmp_path)
    adm = _cliente(app, "2222")
    r = adm.post("/api/usuarios/6123051140/pin", json={"pin": "1111"})
    assert r.status_code == 403
    # El PIN del OWNER sigue siendo el original
    assert Auth(u_path).usuario_con_pin("1234")["user_id"] == 1
    assert Auth(u_path).usuario_con_pin("1111") is None


def test_admin_no_modifica_otro_admin(tmp_path):
    app, _, _ = _setup(tmp_path)
    adm = _cliente(app, "2222")
    assert adm.post("/api/usuarios/3/pin", json={"pin": "9999"}).status_code == 403
    r = adm.post("/api/usuarios", json={"user_id": 3, "nombre": "X", "rol": "TRABAJADOR", "pin": "8888"})
    assert r.status_code == 403
    # Sí puede cambiar su propio PIN y el de un TRABAJADOR
    assert adm.post("/api/usuarios/2/pin", json={"pin": "5555"}).status_code == 200
    assert adm.post("/api/usuarios/4/pin", json={"pin": "6666"}).status_code == 200


def test_admin_no_reutiliza_telegram_id_ajeno(tmp_path):
    app, _, _ = _setup(tmp_path)
    adm = _cliente(app, "2222")
    r = adm.post("/api/usuarios", json={"nombre": "Nuevo", "rol": "TRABAJADOR", "pin": "7777",
                                        "telegram_id": 6123051140})
    assert r.status_code == 400


def test_sync_bloquea_iatf_e_ingreso_para_trabajador(tmp_path):
    app, _, db_path = _setup(tmp_path)
    trab = _cliente(app, "3333")
    r = trab.post("/api/sync", json={"eventos": [
        {"tipo": "inseminador", "id_local": "a1", "payload": {"nombre": "Pepe"}},
        {"tipo": "gasto", "id_local": "a2", "payload": {"tipo_finanza": "INGRESO", "categoria": "LECHE", "monto": 100}},
        {"tipo": "gasto", "id_local": "a3", "payload": {"tipo_finanza": "EGRESO", "categoria": "SAL", "monto": -5}},
        {"tipo": "gasto", "id_local": "a4", "payload": {"tipo_finanza": "EGRESO", "categoria": "SAL", "monto": 50,
                                                          "foto_ruta": "../../etc/passwd"}},
    ]}).get_json()
    assert r["ids_ok"] == ["a4"]
    assert len(r["errores"]) == 3
    db = Database(db_path)
    try:
        filas = db.query("SELECT tipo, monto, foto_ruta FROM finanzas")
        assert [(f["tipo"], f["monto"], f["foto_ruta"]) for f in filas] == [("EGRESO", 50, None)]
        assert db.query_one("SELECT COUNT(*) AS n FROM inseminadores WHERE nombre = 'Pepe'")["n"] == 0
    finally:
        db.close()


def test_finanzas_y_soportes_solo_owner_admin(tmp_path, monkeypatch):
    import src.pwa.app as pwa_app
    media = tmp_path / "media"
    media.mkdir()
    (media / "gasto_sal_1_abc.jpg").write_bytes(b"x")
    (media / "a047.jpg").write_bytes(b"x")
    monkeypatch.setattr(pwa_app, "MEDIA_DIR_DEFAULT", str(media))
    app, _, _ = _setup(tmp_path)
    trab = _cliente(app, "3333")
    assert trab.get("/api/finanzas").status_code == 403
    assert trab.post("/api/finanzas", json={"tipo": "EGRESO", "categoria": "SAL", "monto": 5}).status_code == 403
    assert trab.get("/media/gasto_sal_1_abc.jpg").status_code == 403
    assert trab.get("/media/a047.jpg").status_code == 200
    adm = _cliente(app, "2222")
    assert adm.get("/api/finanzas").status_code == 200
    assert adm.get("/media/gasto_sal_1_abc.jpg").status_code == 200


def test_logout_cross_site_no_cierra_sesion(tmp_path):
    app, _, _ = _setup(tmp_path)
    c = _cliente(app, "1234")
    c.get("/logout", headers={"Sec-Fetch-Site": "cross-site"})
    assert c.get("/api/usuarios").status_code == 200
    c.get("/logout", headers={"Sec-Fetch-Site": "same-origin"})
    assert c.get("/api/usuarios").status_code == 401


def test_auth_recarga_antes_de_escribir(tmp_path):
    """Un proceso con lista vieja no debe resucitar un usuario revocado por otro."""
    u_path = str(tmp_path / "users.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump([{"user_id": 1, "nombre": "D", "rol": "OWNER"},
                   {"user_id": 5, "nombre": "X", "rol": "TRABAJADOR"}], f)
    bot = Auth(u_path)          # proceso del bot, lista en memoria
    pwa = Auth(u_path)          # proceso de la PWA
    pwa.quitar_usuario(5)
    import os
    import time
    # Asegurar mtime distinto aunque el FS tenga resolución gruesa
    st = os.stat(u_path)
    os.utime(u_path, (st.st_atime, st.st_mtime + 2))
    time.sleep(0)
    bot.agregar_usuario(user_id=6, nombre="Y", rol="TRABAJADOR")
    ids = sorted(u["user_id"] for u in Auth(u_path).listar_usuarios())
    assert ids == [1, 6]
