"""Pruebas del login con huella / Face ID (WebAuthn) de la PWA.

Se mockean las primitivas de py_webauthn (en CI no hay autenticador real): lo
que se prueba es el flujo del servidor -- challenge de un solo uso, alta y
revocación de credenciales, revalidación de rol contra users.json, rechazo por
retroceso de sign_count, rate-limit y degradación cuando falta la librería.
"""
import json
import types

import pytest

from src.db.database import Database
from src.pwa import webauthn as wa_mod
from src.pwa.app import crear_app

_CRED_ID = b"cred-abc-1"
_CRED_ID_B64 = wa_mod.b64url_encode(_CRED_ID)


def _cred_id_de(raw: str) -> str:
    """Id almacenado (base64url) para un rawId dado (misma codificación que el servidor)."""
    return wa_mod.b64url_encode(str(raw).encode("utf-8"))


# --------------------------------------------------------------------------- #
# Mock de py_webauthn
# --------------------------------------------------------------------------- #
def _opciones_registro(*, rp_id, rp_name, user_id, user_name, user_display_name,
                       challenge, excluir_ids=None):
    return {
        "challenge": wa_mod.b64url_encode(challenge),
        "rp": {"id": rp_id, "name": rp_name},
        "user": {"id": wa_mod.b64url_encode(b"u"), "name": user_name,
                 "displayName": user_display_name},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
        "excludeCredentials": [],
    }


def _opciones_login(*, rp_id, challenge):
    return {
        "challenge": wa_mod.b64url_encode(challenge),
        "rpId": rp_id,
        "allowCredentials": [],
        "userVerification": "required",
    }


def _verificar_registro(*, credencial, challenge, rp_id, origin):
    # El navegador manda rawId ya en base64url; el servidor real lo decodifica.
    raw = credencial.get("rawId") or credencial.get("id") or _CRED_ID_B64
    return types.SimpleNamespace(
        credential_id=wa_mod.b64url_decode(raw),
        credential_public_key=b"pubkey-abc-1",
        sign_count=0,
        aaguid="00000000-0000-0000-0000-000000000000",
    )


def _verificar_login_factory(new_sign=1):
    def _f(*, credencial, challenge, rp_id, origin, clave_publica, sign_count):
        return types.SimpleNamespace(new_sign_count=new_sign)
    return _f


@pytest.fixture
def wa(monkeypatch):
    """Mockea el módulo WebAuthn dejándolo disponible."""
    monkeypatch.setattr(wa_mod, "disponible", lambda: True)
    monkeypatch.setattr(wa_mod, "opciones_registro", _opciones_registro)
    monkeypatch.setattr(wa_mod, "opciones_login", _opciones_login)
    monkeypatch.setattr(wa_mod, "verificar_registro", _verificar_registro)
    monkeypatch.setattr(wa_mod, "verificar_login", _verificar_login_factory(1))
    return wa_mod


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora.db")
    d = Database(ruta)
    d.create_tables()
    d.close()
    return ruta


@pytest.fixture
def users_file(tmp_path):
    ruta = str(tmp_path / "users.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump([], f)
    return ruta


def _app(db_file, users_file, password="master-secret"):
    app = crear_app(db_file, users_file=users_file, password=password)
    assert app is not None
    app.config.update({"TESTING": True})
    return app


def _credencial_json(nombre="cred-abc-1", transportes=None):
    cid = _cred_id_de(nombre)
    return {"rawId": cid, "id": cid, "type": "public-key",
            "transports": transportes or ["internal"]}


# --------------------------------------------------------------------------- #
# Rutas públicas / sesión
# --------------------------------------------------------------------------- #
def test_disponible_publico_sin_credenciales(db_file, users_file, wa):
    c = _app(db_file, users_file).test_client()
    r = c.get("/api/webauthn/disponible")
    assert r.status_code == 200
    assert r.get_json()["disponible"] is False


def test_estado_requiere_sesion(db_file, users_file, wa):
    c = _app(db_file, users_file).test_client()
    assert c.get("/api/webauthn/estado").status_code == 401


def test_login_opciones_es_publico(db_file, users_file, wa):
    c = _app(db_file, users_file).test_client()
    r = c.post("/api/webauthn/login/opciones", json={})
    assert r.status_code == 200
    assert r.get_json()["opciones"]["challenge"]


def test_post_cross_site_bloqueado(db_file, users_file, wa):
    c = _app(db_file, users_file).test_client()
    r = c.post("/api/webauthn/login/opciones", json={},
               headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


# --------------------------------------------------------------------------- #
# Alta y login
# --------------------------------------------------------------------------- #
def test_registro_y_login_con_huella(db_file, users_file, wa):
    c = _app(db_file, users_file).test_client()
    c.post("/login", data={"password": "master-secret"})

    r = c.post("/api/webauthn/registro/opciones")
    assert r.status_code == 200
    assert r.get_json()["opciones"]["challenge"]

    r2 = c.post("/api/webauthn/registro/verificar",
                json={"credencial": _credencial_json()})
    assert r2.status_code == 200
    assert r2.get_json()["ok"] is True

    estado = c.get("/api/webauthn/estado").get_json()
    assert len(estado["credenciales"]) == 1
    assert estado["credenciales"][0]["credencial_id"] == _CRED_ID_B64

    # Sin sesión, la huella registrada debe permitir entrar sola.
    c.get("/logout")
    assert c.post("/api/webauthn/login/opciones", json={}).status_code == 200
    r3 = c.post("/api/webauthn/login/verificar",
                json={"credencial": _credencial_json()})
    assert r3.status_code == 200
    assert r3.get_json()["redirect"] == "/"
    assert c.get("/api/tablero").status_code == 200


def test_disponible_true_con_credencial(db_file, users_file, wa):
    c = _app(db_file, users_file).test_client()
    c.post("/login", data={"password": "master-secret"})
    c.post("/api/webauthn/registro/opciones")
    c.post("/api/webauthn/registro/verificar", json={"credencial": _credencial_json()})
    c.get("/logout")
    assert c.get("/api/webauthn/disponible").get_json()["disponible"] is True


def test_challenge_de_un_solo_uso(db_file, users_file, wa):
    c = _app(db_file, users_file).test_client()
    c.post("/login", data={"password": "master-secret"})
    c.post("/api/webauthn/registro/opciones")
    assert c.post("/api/webauthn/registro/verificar",
                  json={"credencial": _credencial_json()}).status_code == 200
    # Reintentar el mismo registro sin pedir un challenge nuevo debe fallar.
    assert c.post("/api/webauthn/registro/verificar",
                  json={"credencial": _credencial_json()}).status_code == 409


# --------------------------------------------------------------------------- #
# Seguridad
# --------------------------------------------------------------------------- #
def test_usuario_revocado_rechaza_y_borra_credencial(db_file, tmp_path, wa):
    users = str(tmp_path / "users.json")
    with open(users, "w", encoding="utf-8") as f:
        json.dump([{"user_id": 300, "nombre": "Trabajador", "rol": "TRABAJADOR",
                    "pin": "7777"}], f)
    c = _app(db_file, users).test_client()
    c.post("/login", data={"pin": "7777"})
    c.post("/api/webauthn/registro/opciones")
    assert c.post("/api/webauthn/registro/verificar",
                  json={"credencial": _credencial_json()}).status_code == 200

    # Se revoca el usuario en users.json.
    with open(users, "w", encoding="utf-8") as f:
        json.dump([], f)

    c.get("/logout")
    c.post("/api/webauthn/login/opciones", json={})
    r = c.post("/api/webauthn/login/verificar", json={"credencial": _credencial_json()})
    assert r.status_code == 401

    d = Database(db_file)
    try:
        assert d.obtener_credencial_webauthn(_CRED_ID_B64) is None
    finally:
        d.close()


def test_sign_count_que_retrocede_se_rechaza(db_file, users_file, wa, monkeypatch):
    c = _app(db_file, users_file).test_client()
    c.post("/login", data={"password": "master-secret"})
    c.post("/api/webauthn/registro/opciones")
    c.post("/api/webauthn/registro/verificar", json={"credencial": _credencial_json()})

    d = Database(db_file)
    try:
        d.actualizar_uso_credencial_webauthn(_CRED_ID_B64, 5)
    finally:
        d.close()
    monkeypatch.setattr(wa_mod, "verificar_login", _verificar_login_factory(3))

    c.get("/logout")
    c.post("/api/webauthn/login/opciones", json={})
    r = c.post("/api/webauthn/login/verificar", json={"credencial": _credencial_json()})
    assert r.status_code == 401


def test_rate_limit_tras_fallos_de_huella(db_file, users_file, wa):
    c = _app(db_file, users_file).test_client()
    codigos = []
    for _ in range(10):
        c.post("/api/webauthn/login/opciones", json={})
        codigos.append(c.post("/api/webauthn/login/verificar",
                              json={"credencial": _credencial_json("cred-inexistente")}).status_code)
    assert 429 in codigos


def test_revocar_propia_ajena_y_admin(db_file, tmp_path, wa):
    users = str(tmp_path / "users.json")
    with open(users, "w", encoding="utf-8") as f:
        json.dump([
            {"user_id": 1, "nombre": "Dueño", "rol": "OWNER", "pin": "1111"},
            {"user_id": 2, "nombre": "Peón", "rol": "TRABAJADOR", "pin": "2222"},
        ], f)
    app = _app(db_file, users)

    c_owner = app.test_client()
    c_owner.post("/login", data={"pin": "1111"})
    c_owner.post("/api/webauthn/registro/opciones")
    c_owner.post("/api/webauthn/registro/verificar",
                 json={"credencial": _credencial_json("cred-owner")})

    c_peon = app.test_client()
    c_peon.post("/login", data={"pin": "2222"})
    c_peon.post("/api/webauthn/registro/opciones")
    c_peon.post("/api/webauthn/registro/verificar",
                json={"credencial": _credencial_json("cred-peon")})

    # El trabajador no puede revocar la credencial del OWNER...
    assert c_peon.delete(
        "/api/webauthn/credenciales/" + _cred_id_de("cred-owner")).status_code == 403
    # ...pero sí la suya; y el OWNER puede revocar cualquiera.
    assert c_peon.delete(
        "/api/webauthn/credenciales/" + _cred_id_de("cred-peon")).status_code == 200
    assert c_owner.delete(
        "/api/webauthn/credenciales/" + _cred_id_de("cred-owner")).status_code == 200

    # Solo OWNER/ADMIN ve el listado global.
    assert c_peon.get("/api/webauthn/credenciales/todas").status_code == 403


def test_sin_libreria_degrada_sin_tumbar_la_pwa(db_file, users_file, monkeypatch):
    monkeypatch.setattr(wa_mod, "disponible", lambda: False)
    c = _app(db_file, users_file).test_client()
    c.post("/login", data={"password": "master-secret"})
    assert c.post("/api/webauthn/registro/opciones").status_code == 503
    r = c.get("/api/webauthn/disponible")
    assert r.status_code == 200
    assert r.get_json()["disponible"] is False
    # El resto de la PWA sigue funcionando.
    assert c.get("/api/tablero").status_code == 200
