"""Tests del chat interno del equipo (PWA): canal general, mensajes
directos, no-leídos y validaciones de la API."""
import json

import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora.db")
    Database(ruta).create_tables().close()
    return ruta


@pytest.fixture
def users_file(tmp_path):
    ruta = str(tmp_path / "users.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump([
            {"user_id": 1, "nombre": "Duenio", "rol": "OWNER", "pin": "1234"},
            {"user_id": 2, "nombre": "Mayordomo", "rol": "TRABAJADOR", "pin": "1111"},
            {"user_id": 3, "nombre": "Vaquero", "rol": "TRABAJADOR", "pin": "2222"},
        ], f)
    return ruta


@pytest.fixture
def app(db_file, users_file):
    app = crear_app(db_file, users_file=users_file, password="clave-de-prueba")
    assert app is not None
    app.config.update({"TESTING": True})
    return app


def _cliente(app, pin):
    c = app.test_client()
    r = c.post("/login", data={"pin": pin}, follow_redirects=False)
    assert "/login" not in r.headers.get("Location", "/")
    return c


def test_chat_sin_sesion_devuelve_401(app):
    c = app.test_client()
    for metodo, ep in (("get", "/api/chat/contactos"), ("get", "/api/chat/mensajes"),
                       ("post", "/api/chat/enviar")):
        r = getattr(c, metodo)(ep)
        assert r.status_code == 401, ep


def test_canal_general_visible_para_todos(app):
    c1 = _cliente(app, "1234")
    c2 = _cliente(app, "1111")
    r = c1.post("/api/chat/enviar", json={"con": "general", "texto": "Hola equipo"})
    assert r.status_code == 200 and r.get_json()["ok"]
    msg = r.get_json()["mensaje"]
    assert msg["para"] is None and msg["mio"] is True

    d = c2.get("/api/chat/mensajes?con=general").get_json()
    assert [m["texto"] for m in d["mensajes"]] == ["Hola equipo"]
    assert d["mensajes"][0]["mio"] is False
    assert d["mensajes"][0]["de_nombre"] == "Duenio"


def test_mensaje_directo_solo_entre_los_dos(app):
    c1 = _cliente(app, "1234")
    c2 = _cliente(app, "1111")
    c3 = _cliente(app, "2222")
    r = c2.post("/api/chat/enviar", json={"con": "1", "texto": "la 47 ya pario"})
    assert r.status_code == 200

    d1 = c1.get("/api/chat/mensajes?con=2").get_json()
    assert [m["texto"] for m in d1["mensajes"]] == ["la 47 ya pario"]
    # El tercero no ve el directo ajeno, ni en el general ni en su DM
    assert c3.get("/api/chat/mensajes?con=general").get_json()["mensajes"] == []
    assert c3.get("/api/chat/mensajes?con=1").get_json()["mensajes"] == []
    assert c3.get("/api/chat/mensajes?con=2").get_json()["mensajes"] == []


def test_polling_incremental_desde_id(app):
    c1 = _cliente(app, "1234")
    c2 = _cliente(app, "1111")
    id1 = c1.post("/api/chat/enviar", json={"texto": "uno"}).get_json()["mensaje"]["id"]
    c1.post("/api/chat/enviar", json={"texto": "dos"})
    d = c2.get(f"/api/chat/mensajes?con=general&desde_id={id1}").get_json()
    assert [m["texto"] for m in d["mensajes"]] == ["dos"]


def test_no_leidos_y_badge(app):
    c1 = _cliente(app, "1234")
    c2 = _cliente(app, "1111")
    c1.post("/api/chat/enviar", json={"texto": "general 1"})
    c1.post("/api/chat/enviar", json={"con": "2", "texto": "directo 1"})

    assert c2.get("/api/badges").get_json().get("chat") == 2
    # El remitente no se cuenta a sí mismo
    assert c1.get("/api/badges").get_json().get("chat") == 0

    nl = c2.get("/api/chat/contactos").get_json()["no_leidos"]
    assert nl["total"] == 2
    assert nl["por_conversacion"] == {"general": 1, "1": 1}

    # Leer ambas conversaciones limpia el contador
    c2.get("/api/chat/mensajes?con=general")
    c2.get("/api/chat/mensajes?con=1")
    assert c2.get("/api/badges").get_json().get("chat") == 0

    # marcar=0 consulta sin avanzar el marcador de lectura
    c1.post("/api/chat/enviar", json={"con": "2", "texto": "directo 2"})
    c2.get("/api/chat/mensajes?con=1&marcar=0")
    assert c2.get("/api/badges").get_json().get("chat") == 1


def test_validaciones_de_envio(app):
    c1 = _cliente(app, "1234")
    assert c1.post("/api/chat/enviar", json={"texto": "   "}).status_code == 400
    assert c1.post("/api/chat/enviar", json={"con": "99", "texto": "x"}).status_code == 400
    assert c1.post("/api/chat/enviar", json={"texto": "x" * 2001}).status_code == 400


def test_contactos_excluye_al_propio_y_sin_datos_sensibles(app):
    c1 = _cliente(app, "1234")
    d = c1.get("/api/chat/contactos").get_json()
    nombres = sorted(x["nombre"] for x in d["contactos"])
    assert nombres == ["Mayordomo", "Vaquero"]
    assert d["yo"]["nombre"] == "Duenio"
    for contacto in d["contactos"]:
        assert "pin" not in contacto and "ip" not in contacto


def test_db_chat_directo():
    d = Database(":memory:").create_tables()
    m = d.enviar_mensaje_chat("1", "hola", remitente_nombre="Duenio")
    assert m["id"] > 0 and m["para"] is None
    with pytest.raises(ValueError):
        d.enviar_mensaje_chat("1", "   ")
    d.enviar_mensaje_chat("2", "directo", destinatario_id="1")
    assert d.chat_no_leidos("1") == {"total": 1, "por_conversacion": {"2": 1}}
    d.marcar_chat_leido("1", "2", 99)
    assert d.chat_no_leidos("1")["total"] == 0
    d.close()


def test_presencia_en_vivo_lista_usuarios():
    # Regresión: obtener_usuarios_presencia llamaba a self.query_all (método
    # inexistente) y el except devolvía {} siempre — nadie salía "en línea".
    d = Database(":memory:").create_tables()
    d.registrar_presencia("1", "Duenio", "OWNER")
    pres = d.obtener_usuarios_presencia()
    assert "1" in pres and pres["1"]["en_linea"] is True
    d.close()
