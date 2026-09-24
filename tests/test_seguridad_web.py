"""Cierre de seguridad web (opción 1): cabeceras en Flask, errores sin
fugas y chequeo de origen en escrituras."""
import json

import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.pwa.app import _CSP_PWA, _error_interno, _origen_permitido


def _app(tmp_path):
    from src.db.database import Database
    from src.pwa.app import crear_app

    ruta = str(tmp_path / "web.db")
    d = Database(ruta)
    d.create_tables()
    d.close()
    u_path = str(tmp_path / "users_web.json")
    with open(u_path, "w", encoding="utf-8") as f:
        json.dump([{"user_id": 100, "nombre": "O", "rol": "OWNER", "pin": "1234"}], f)
    app = crear_app(ruta, users_file=u_path, password="x")
    assert app is not None
    app.config.update({"TESTING": True})
    return app


def test_cabeceras_seguridad_en_respuestas(tmp_path):
    app = _app(tmp_path)
    c = app.test_client()
    c.post("/login", data={"pin": "1234"})
    r = c.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in r.headers
    csp = r.headers.get("Content-Security-Policy", "")
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
    assert "frame-ancestors 'self'" in csp
    # HTTP plano: sin HSTS (el navegador lo ignoraría; solo tiene sentido en HTTPS).
    assert "Strict-Transport-Security" not in r.headers


def test_csp_igual_al_de_nginx():
    assert "https://server.arcgisonline.com" in _CSP_PWA
    assert "object-src 'none'" in _CSP_PWA


@pytest.mark.parametrize("origen,referido,host,ok", [
    ("", "", "localhost", True),  # curl / clientes viejos: como antes
    ("http://localhost", "", "localhost", True),
    ("http://localhost:5000", "", "localhost:5000", True),
    ("https://ganaderiaja.duckdns.org", "", "ganaderiaja.duckdns.org", True),
    ("", "https://ganaderiaja.duckdns.org/tablero", "ganaderiaja.duckdns.org", True),
    ("https://evil.com", "", "localhost", False),
    ("", "https://evil.com/x", "localhost", False),
    ("https://evil.com", "https://localhost/", "localhost", False),
    ("http://localhost.evil.com", "", "localhost", False),
    ("not-a-url", "", "localhost", False),
])
def test_origen_permitido(origen, referido, host, ok):
    assert _origen_permitido(origen, referido, host) is ok


def test_post_entre_sitios_bloqueado(tmp_path):
    app = _app(tmp_path)
    c = app.test_client()
    c.post("/login", data={"pin": "1234"})
    r = c.post("/api/mensajes-equipo", json={"mensaje": "hola"},
               headers={"Origin": "https://evil.com"})
    assert r.status_code == 403
    r2 = c.post("/api/mensajes-equipo", json={"mensaje": "hola"},
                headers={"Origin": "http://localhost"})
    assert r2.status_code != 403
    # Sin Origin: flujo normal (aquí 400 por payload incompleto, no 403).
    r3 = c.post("/api/mensajes-equipo", json={"mensaje": "hola"})
    assert r3.status_code != 403


def test_login_origen_falso_bloqueado(tmp_path):
    app = _app(tmp_path)
    c = app.test_client()
    r = c.post("/login", data={"pin": "1234"}, headers={"Origin": "https://evil.com"})
    assert r.status_code == 403
    r2 = c.post("/login", data={"pin": "1234"})
    assert r2.status_code in (301, 302, 303, 307, 308)


def test_error_interno_generico(tmp_path):
    app = _app(tmp_path)
    with app.test_request_context("/"):
        cuerpo500, codigo500 = _error_interno(500)
        assert codigo500 == 500
        assert cuerpo500.get_json() == {"ok": False, "error": "Error interno del servidor. Intente de nuevo."}
        cuerpo400, codigo400 = _error_interno(400)
        assert codigo400 == 400
        assert "Revise los datos" in cuerpo400.get_json()["error"]
        cuerpo_sin_ok, _ = _error_interno(400, con_ok=False)
        assert set(cuerpo_sin_ok.get_json().keys()) == {"error"}
        cuerpo_extra, _ = _error_interno(500, extra={"toros": []})
        assert cuerpo_extra.get_json()["toros"] == []


def test_pin_inexistente_no_filtra_detalle(tmp_path):
    # PIN válido contra usuario inexistente: 400 genérico, sin texto de la excepción.
    app = _app(tmp_path)
    c = app.test_client()
    c.post("/login", data={"pin": "1234"})
    r = c.post("/api/usuarios/999/pin", json={"pin": "8888"})
    assert r.status_code == 400
    cuerpo = r.get_json()
    assert cuerpo["error"] == "No se pudo completar la operación. Revise los datos e intente de nuevo."
