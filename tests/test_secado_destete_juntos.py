"""Casillas opcionales que unen Secado y Destete en Registrar.

- Secado con "Destetar también la cría" (payload.destetar_cria): además
  del secado se guarda el destete de la cría activa sin destetar.
- Destete con "Secar también la madre" (payload.secar_madre): además del
  destete se guarda el secado de la madre.
Cada uno queda como su propio evento y no se duplica.
"""
import pytest

flask = pytest.importorskip("flask", reason="Flask no instalado")

from src.db.database import Database
from src.pwa.app import crear_app


@pytest.fixture
def db_file(tmp_path):
    ruta = str(tmp_path / "bitacora_juntos.db")
    d = Database(ruta)
    d.create_tables()
    d.registrar_potrero(nombre="Vacas Secas", codigo="VS")
    d.registrar_animal("V50", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2020-01-01")
    d.registrar_parto(vaca_tag="V50", fecha="2026-02-01", sexo_cria="MACHO", id_cria_tag="V50M")
    d.registrar_animal("V60", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2020-01-01")
    d.close()
    return ruta


@pytest.fixture
def client(db_file):
    app = crear_app(db_file, password="clave-de-prueba")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave-de-prueba"})
    return c


def _conteo(db_file, tabla, tag):
    d = Database(db_file)
    try:
        aid = d.resolve_animal(tag)
        return d.query_one(f"SELECT COUNT(*) AS n FROM {tabla} WHERE animal_id = ?", (aid,))["n"]
    finally:
        d.close()


def _sync(client, tipo, payload, id_local, fecha="2026-11-05"):
    r = client.post("/api/sync", json={"eventos": [
        {"tipo": tipo, "id_local": id_local, "fecha": fecha, "payload": payload}]})
    assert r.status_code == 200
    assert r.get_json()["errores"] == []


def test_secado_con_destetar_cria(client, db_file):
    _sync(client, "secado", {"animal_tag": "V50", "motivo": "Fin de lactancia", "destetar_cria": True}, "s1")
    assert _conteo(db_file, "secados", "V50") == 1
    assert _conteo(db_file, "destetes", "V50M") == 1
    # Otro secado con la casilla no vuelve a destetar la misma cría.
    _sync(client, "secado", {"animal_tag": "V50", "destetar_cria": True}, "s2", fecha="2026-11-06")
    assert _conteo(db_file, "destetes", "V50M") == 1


def test_secado_sin_casilla_no_desteta(client, db_file):
    _sync(client, "secado", {"animal_tag": "V50"}, "s3")
    assert _conteo(db_file, "secados", "V50") == 1
    assert _conteo(db_file, "destetes", "V50M") == 0


def test_secado_con_casilla_sin_cria_solo_seca(client, db_file):
    _sync(client, "secado", {"animal_tag": "V60", "destetar_cria": True}, "s4")
    assert _conteo(db_file, "secados", "V60") == 1


def test_destete_con_secar_madre(client, db_file):
    _sync(client, "destete", {"cria_tag": "V50M", "vaca_tag": "V50", "secar_madre": True,
                              "potrero_madre": "Vacas Secas", "cond_corporal_madre": 3.0}, "d1")
    assert _conteo(db_file, "destetes", "V50M") == 1
    assert _conteo(db_file, "secados", "V50") == 1
    d = Database(db_file)
    try:
        s = d.query_one("SELECT * FROM secados WHERE animal_id = ?", (d.resolve_animal("V50"),))
        assert s["motivo"] == "Destete de la cría"
        assert s["potrero_destino"] is not None
        # Un solo traslado de la madre aunque destete y secado lo pidan.
        assert d.query_one("SELECT COUNT(*) AS n FROM traslados WHERE animal_id = ?",
                           (d.resolve_animal("V50"),))["n"] == 1
    finally:
        d.close()


def test_destete_secar_madre_ya_secada_no_duplica(client, db_file):
    _sync(client, "secado", {"animal_tag": "V50"}, "s5", fecha="2026-11-01")
    _sync(client, "destete", {"cria_tag": "V50M", "vaca_tag": "V50", "secar_madre": True}, "d2")
    assert _conteo(db_file, "secados", "V50") == 1
    assert _conteo(db_file, "destetes", "V50M") == 1


def test_destete_sin_casilla_no_seca(client, db_file):
    _sync(client, "destete", {"cria_tag": "V50M", "vaca_tag": "V50"}, "d3")
    assert _conteo(db_file, "secados", "V50") == 0
