"""Chat de la PWA: consultas se responden, registros esperan confirmación."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.bot.bot_interface import Bot
from src.db.database import Database
from src.engine import chat_pwa
from src.pwa.app import crear_app


@pytest.fixture(autouse=True)
def _sin_llm(monkeypatch):
    # Tests sin red: la capa LLM del parser nunca responde.
    monkeypatch.setattr("src.llm.try_hybrid_parse", lambda *a, **k: None)


@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora.db")
    d = Database(ruta)
    d.create_tables()
    d.registrar_potrero(nombre="Guayabal", codigo="G1")
    d.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero="Guayabal", fecha_nacimiento="2022-01-10")
    d.close()
    return ruta


@pytest.fixture
def db(db_file):
    d = Database(db_file)
    yield d
    d.close()


def _pesajes(db):
    return db.count("pesajes")


def test_consulta_se_responde_y_nunca_escribe(db):
    # Regresión: "novillas total" es inventario, nunca un registro.
    res = chat_pwa.procesar_mensaje(db, "novillas total", user_id=1)
    assert res["tipo"] == "consulta"
    assert res["token"] is None and res["confirmar"] == []
    assert res["respuesta"]
    fila = db.query_one("SELECT tipo, estado FROM chat_log")
    assert (fila["tipo"], fila["estado"]) == ("consulta", "RESPONDIDA")


def test_registro_no_escribe_hasta_confirmar(db):
    antes = _pesajes(db)
    res = chat_pwa.procesar_mensaje(db, "la 47 peso 450 kg", user_id=1)
    assert res["tipo"] == "registro" and res["token"]
    assert res["confirmar"] == ["Pesaje de la 47: 450.0 kg."]
    assert _pesajes(db) == antes

    ok = chat_pwa.confirmar(db, res["token"], user_id=1)
    assert ok["ok"] and "Registrado pesaje de la 47" in ok["respuesta"]
    assert _pesajes(db) == antes + 1
    assert db.query_one("SELECT estado FROM chat_log")["estado"] == "CONFIRMADA"

    # Doble toque: el token es de un solo uso.
    assert not chat_pwa.confirmar(db, res["token"], user_id=1)["ok"]
    assert _pesajes(db) == antes + 1


def test_corregir_descarta_sin_escribir(db):
    antes = _pesajes(db)
    res = chat_pwa.procesar_mensaje(db, "la 47 peso 450 kg", user_id=1)
    out = chat_pwa.confirmar(db, res["token"], user_id=1, aceptar=False)
    assert out["ok"] and "No registré nada" in out["respuesta"]
    assert _pesajes(db) == antes
    assert db.query_one("SELECT estado FROM chat_log")["estado"] == "CORREGIDA"


def test_token_de_otro_usuario_se_rechaza(db):
    res = chat_pwa.procesar_mensaje(db, "la 47 peso 450 kg", user_id=1)
    assert not chat_pwa.confirmar(db, res["token"], user_id=2)["ok"]
    assert db.query_one("SELECT estado FROM chat_log")["estado"] == "PENDIENTE"


def test_token_vencido_no_escribe(db, monkeypatch):
    antes = _pesajes(db)
    res = chat_pwa.procesar_mensaje(db, "la 47 peso 450 kg", user_id=1)
    tarde = datetime.now() + timedelta(minutes=chat_pwa.VIGENCIA_MIN + 1)
    monkeypatch.setattr(chat_pwa, "_ahora", lambda: tarde)
    out = chat_pwa.confirmar(db, res["token"], user_id=1)
    assert not out["ok"] and "minutos" in out["error"]
    assert _pesajes(db) == antes
    assert db.query_one("SELECT estado FROM chat_log")["estado"] == "VENCIDA"


def test_error_al_registrar_no_deja_nada_a_medias(db, monkeypatch):
    res = chat_pwa.procesar_mensaje(db, "la 47 peso 450 kg", user_id=1)

    def _falla(*a, **k):
        raise ValueError("animal bloqueado")

    monkeypatch.setattr(Bot, "_registrar", _falla)
    out = chat_pwa.confirmar(db, res["token"], user_id=1)
    assert not out["ok"] and "animal bloqueado" in out["error"]
    assert db.query_one("SELECT estado FROM chat_log")["estado"] == "ERROR"


def test_telegram_sigue_registrando_de_una_vez(db):
    antes = _pesajes(db)
    assert "Registrado pesaje" in Bot(db).procesar_texto("la 47 peso 450 kg", user_id=1)
    assert _pesajes(db) == antes + 1


# --- API ------------------------------------------------------------------ #

@pytest.fixture
def client(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave-de-prueba"})
    return c


def test_api_chat_mensaje_y_confirmar(client, db_file):
    r = client.post("/api/chat/mensaje", json={"texto": "la 47 peso 450 kg"})
    d = r.get_json()
    assert r.status_code == 200 and d["tipo"] == "registro" and d["token"]
    d2 = client.post("/api/chat/confirmar", json={"token": d["token"]}).get_json()
    assert d2["ok"]
    otra = client.post("/api/chat/confirmar", json={"token": d["token"]})
    assert otra.status_code == 409
    db = Database(db_file)
    try:
        assert db.count("pesajes") == 1
    finally:
        db.close()


def test_api_chat_mensaje_vacio_400(client):
    assert client.post("/api/chat/mensaje", json={"texto": "  "}).status_code == 400


def test_api_voz_tambien_pide_confirmacion(client, db_file, monkeypatch):
    monkeypatch.setattr("src.parsers.media_handler.transcribe_audio",
                        lambda ruta: SimpleNamespace(texto="la 47 peso 450 kg"))
    import io
    r = client.post("/api/voz", data={"audio": (io.BytesIO(b"x"), "nota.webm")},
                    content_type="multipart/form-data")
    d = r.get_json()
    assert d["ok"] and d["transcripcion"] == "la 47 peso 450 kg"
    assert d["token"] and d["confirmar"]
    db = Database(db_file)
    try:
        assert db.count("pesajes") == 0
        assert db.query_one("SELECT canal FROM chat_log")["canal"] == "voz"
    finally:
        db.close()
