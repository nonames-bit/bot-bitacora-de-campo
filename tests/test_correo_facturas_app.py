"""Correo de facturas configurado desde la app (Sistema → Correo, solo OWNER):
el dueño pega el correo y la contraseña de aplicación sin tocar el .env."""
import imaplib
import json
import os
import stat
from pathlib import Path

import pytest

from src.db.database import Database
from src.integrations import correo_facturas
from src.pwa.app import crear_app
from scripts import programador


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    db_path = tmp_path / "bitacora.db"
    Database(str(db_path)).create_tables().close()
    monkeypatch.setenv("BITACORA_DB", str(db_path))
    for k in ("FACTURAS_CONFIG_FILE", "FACTURAS_IMAP_USUARIO", "FACTURAS_IMAP_CLAVE", "FACTURAS_IMAP_HOST"):
        monkeypatch.delenv(k, raising=False)
    u = tmp_path / "users.json"
    u.write_text(json.dumps([
        {"user_id": 1, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"},
        {"user_id": 2, "nombre": "Admin", "rol": "ADMIN", "pin": "2222"},
    ]), encoding="utf-8")
    app = crear_app(str(db_path), users_file=str(u), password="master-password")
    app.config.update({"TESTING": True})
    return app, tmp_path


def _cliente(app, pin):
    c = app.test_client()
    c.post("/login", data={"pin": pin})
    return c


class ImapPrueba:
    def __init__(self, sin_leer=2, falla=None):
        self.sin_leer, self.falla = sin_leer, falla
        self.cred = None

    def __call__(self, cred):
        if self.falla:
            raise self.falla
        self.cred = cred
        return self

    def select(self, carpeta, readonly=False):
        return "OK", [b"5"]

    def search(self, charset, criterio):
        return "OK", [b" ".join(str(i).encode() for i in range(1, self.sin_leer + 1))]

    def logout(self):
        pass


def test_credenciales_de_la_app_reemplazan_al_env(entorno, monkeypatch):
    _, tmp = entorno
    assert not correo_facturas.configurado()
    monkeypatch.setenv("FACTURAS_IMAP_USUARIO", "viejo@gmail.com")
    monkeypatch.setenv("FACTURAS_IMAP_CLAVE", "clavevieja")
    assert correo_facturas.credenciales()["origen"] == "servidor"
    correo_facturas.guardar_ajustes(" ja.ganaderia@gmail.com ", "abcd efgh ijkl mnop")
    cred = correo_facturas.credenciales()
    assert cred == {"usuario": "ja.ganaderia@gmail.com", "clave": "abcdefghijklmnop",
                    "host": "imap.gmail.com", "origen": "app"}
    ruta = Path(correo_facturas.ruta_ajustes())
    assert ruta.parent == tmp, "queda junto a la base (data/ en Docker)"
    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o600
    correo_facturas.borrar_ajustes()
    assert correo_facturas.credenciales()["origen"] == "servidor"


def test_probar_conexion_explica_clave_mala():
    falla = imaplib.IMAP4.error("b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'")
    res = correo_facturas.probar_conexion("a@gmail.com", "x", conectar=ImapPrueba(falla=falla))
    assert not res["ok"] and "contraseña de aplicación" in res["error"]
    res = correo_facturas.probar_conexion("a@gmail.com", "ab cd", conectar=ImapPrueba(sin_leer=3))
    assert res == {"ok": True, "sin_leer": 3}


def test_guardar_desde_la_app_prueba_antes_y_no_devuelve_la_clave(entorno, monkeypatch):
    app, _ = entorno
    imap = ImapPrueba(sin_leer=4)
    monkeypatch.setattr(correo_facturas, "_conectar_imap", imap)
    c = _cliente(app, "1234")
    d = c.get("/api/correo-facturas").get_json()
    assert d["ok"] and d["configurado"] is False

    r = c.post("/api/correo-facturas", json={"usuario": "ja.ganaderia@gmail.com", "clave": "abcd efgh ijkl mnop"})
    d = r.get_json()
    assert r.status_code == 200 and d["configurado"] and d["origen"] == "app" and d["sin_leer"] == 4
    assert imap.cred["clave"] == "abcdefghijklmnop"
    texto = json.dumps(c.get("/api/correo-facturas").get_json())
    assert "abcdefghijklmnop" not in texto and "ja.ganaderia@gmail.com" in texto

    assert c.post("/api/correo-facturas/probar").get_json() == {"ok": True, "sin_leer": 4}
    assert c.delete("/api/correo-facturas").get_json()["configurado"] is False


def test_clave_mala_no_se_guarda(entorno, monkeypatch):
    app, _ = entorno
    monkeypatch.setattr(correo_facturas, "_conectar_imap",
                        ImapPrueba(falla=imaplib.IMAP4.error("AUTHENTICATIONFAILED")))
    c = _cliente(app, "1234")
    r = c.post("/api/correo-facturas", json={"usuario": "ja.ganaderia@gmail.com", "clave": "clave normal"})
    assert r.status_code == 422 and "16 letras" in r.get_json()["error"]
    assert not os.path.exists(correo_facturas.ruta_ajustes())
    assert c.post("/api/correo-facturas", json={"usuario": "sin-arroba", "clave": "x"}).status_code == 400


def test_solo_el_owner(entorno):
    app, _ = entorno
    adm = _cliente(app, "2222")
    assert adm.get("/api/correo-facturas").status_code == 403
    assert adm.post("/api/correo-facturas", json={"usuario": "a@b.co", "clave": "x"}).status_code == 403
    assert adm.post("/api/correo-facturas/probar").status_code == 403
    assert adm.delete("/api/correo-facturas").status_code == 403


def test_programador_anota_cada_revision(entorno, monkeypatch):
    correo_facturas.guardar_ajustes("ja.ganaderia@gmail.com", "abcdefghijklmnop")
    monkeypatch.setattr(correo_facturas, "revisar_correo", lambda db, **kw: 2)
    monkeypatch.setattr(programador, "_db", lambda: type("D", (), {"close": lambda self: None})())
    assert programador.revisar_correo_facturas() == 2
    e = correo_facturas.leer_estado()
    assert e["ok"] and e["facturas"] == 2 and e["revisado_en"]

    def falla(db, **kw):
        raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
    monkeypatch.setattr(correo_facturas, "revisar_correo", falla)
    with pytest.raises(imaplib.IMAP4.error):
        programador.revisar_correo_facturas()
    e = correo_facturas.leer_estado()
    assert not e["ok"] and "contraseña de aplicación" in e["error"]
