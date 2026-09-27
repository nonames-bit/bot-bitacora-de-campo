"""Estado de lactancia único (engine/lactancia.py): lote de ordeño, secados,
pausas y partos imposibles; y que ficha, lista Secar y recibo coincidan."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.dashboard_data import _calcular_novillas_entoradas, datos_ficha_animal
from src.engine.lactancia import estados_lactancia, marcar_potrero_ordeno, potreros_ordeno
from src.engine.tareas import datos_tareas
from src.pwa.app import crear_app

HOY = date.today()


def _d(dias: int) -> str:
    return (HOY + timedelta(days=dias)).isoformat()


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "l.db")).create_tables()
    yield d
    d.close()


def _vaca(db, tag, potrero=None, parto=None, edad=2000):
    db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-edad), potrero=potrero)
    if parto is not None:
        db.registrar_parto(tag, fecha=_d(-parto), sexo_cria="Macho")


def _pid(db, nombre):
    return db.query_one("SELECT id FROM potreros WHERE nombre = ?", (nombre,))["id"]


def _estado(db, tag):
    aid = db.query_one("SELECT id_animal FROM animales WHERE tag = ?", (tag,))["id_animal"]
    return estados_lactancia(db, HOY).get(aid)


def test_lote_por_nombre_y_fuera_del_lote_es_seca(db):
    db.registrar_potrero(nombre="ORDENO SANTA MARTHA", codigo="P1")
    db.registrar_potrero(nombre="OLEGARIO II", codigo="P2")
    _vaca(db, "LARGA", "ORDENO SANTA MARTHA", parto=400)
    _vaca(db, "A015", "OLEGARIO II", parto=513)
    _vaca(db, "FRESCA_FUERA", "OLEGARIO II", parto=40)
    assert _estado(db, "LARGA")["estado"] == "EN_ORDENO"
    assert _estado(db, "A015")["estado"] == "SECA" and not _estado(db, "A015")["confirmado"]
    assert _estado(db, "FRESCA_FUERA")["estado"] == "SECA"
    t = datos_tareas(db, HOY)
    secar = {f["tag"] for f in t["secar"]}
    assert "LARGA" in secar and "A015" not in secar


def test_lote_automatico_donde_estan_las_recien_paridas_y_manual(db):
    db.registrar_potrero(nombre="LA LOMA", codigo="P1")
    db.registrar_potrero(nombre="EL BAJO", codigo="P2")
    for i in range(2):
        _vaca(db, f"F{i}", "LA LOMA", parto=30)
    _vaca(db, "VIEJA", "LA LOMA", parto=350)
    _vaca(db, "OTRA", "EL BAJO", parto=350)
    pots = potreros_ordeno(db, HOY)
    assert pots[_pid(db, "LA LOMA")]["modo"] == "auto" and pots[_pid(db, "LA LOMA")]["ordeno"]
    assert not pots[_pid(db, "EL BAJO")]["ordeno"]
    assert _estado(db, "VIEJA")["estado"] == "EN_ORDENO" and _estado(db, "OTRA")["estado"] == "SECA"
    marcar_potrero_ordeno(db, _pid(db, "EL BAJO"), True)
    assert _estado(db, "OTRA")["estado"] == "EN_ORDENO"
    marcar_potrero_ordeno(db, _pid(db, "LA LOMA"), False)
    assert _estado(db, "F0")["estado"] == "SECA"
    marcar_potrero_ordeno(db, _pid(db, "LA LOMA"), None)
    assert _estado(db, "F0")["estado"] == "EN_ORDENO"


def test_secado_confirmado_pausa_y_regla_vieja_sin_lote(db):
    _vaca(db, "S", parto=100)
    db.registrar_secado("S", fecha=_d(-3))
    _vaca(db, "J", parto=100)
    _vaca(db, "V", parto=400)
    _vaca(db, "P", parto=60)
    db.registrar_pausa_ordeno("P", fecha_inicio=_d(-2))
    assert _estado(db, "S")["estado"] == "SECA" and _estado(db, "S")["confirmado"]
    assert _estado(db, "J")["estado"] == "EN_ORDENO"  # sin lote conocido: < 300 DEL
    assert _estado(db, "V")["estado"] == "SECA"
    assert _estado(db, "P")["estado"] == "PAUSADA"
    assert db.resumen_ordeno() == {"en_ordeno": 2, "en_pausa": 1, "ordenandose": 1}


def test_ficha_usa_la_misma_regla(db):
    db.registrar_potrero(nombre="ORDENO", codigo="P1")
    db.registrar_potrero(nombre="OLEGARIO II", codigo="P2")
    _vaca(db, "A015", "OLEGARIO II", parto=513)
    _vaca(db, "EN", "ORDENO", parto=320)
    f = datos_ficha_animal(db, "A015")
    assert f["lactancia"]["estado"] == "Seca" and "Fuera del lote" in f["lactancia"]["motivo"]
    assert datos_ficha_animal(db, "EN")["lactancia"]["estado"] == "En ordeño"


def test_parto_imposible_en_ternera_se_ignora_y_avisa(db):
    _vaca(db, "A033", parto=None)
    db.registrar_animal("A048", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-240), madre_tag="A033")
    db.registrar_parto("A048", fecha=_d(-30), sexo_cria="Macho")
    assert _estado(db, "A048") is None
    f = datos_ficha_animal(db, "A048")
    assert f["ultimo_parto"] is None and "A033" in f["aviso_datos"]
    assert "Vaca" not in f["estado_fisiologico"]["titulo"]
    t = datos_tareas(db, HOY)
    assert "A048" not in {x["tag"] for x in t["servir"]}


def test_sync_no_guarda_parto_de_ternera(tmp_path):
    ruta = str(tmp_path / "s.db")
    d = Database(ruta).create_tables()
    d.registrar_animal("T7", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-210))
    d.close()
    app = crear_app(ruta, password="clave")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave"})
    r = c.post("/api/sync", json={"eventos": [{"tipo": "parto", "fecha": HOY.isoformat(), "id_local": "x1",
                                              "payload": {"vaca_tag": "T7", "sexo_cria": "Macho"}}]}).get_json()
    assert r["procesados"] == 0 and "x1" in r["ids_ok"] and "T7" in r["errores"][0]
    d = Database(ruta)
    assert d.query_one("SELECT COUNT(*) n FROM partos")["n"] == 0
    d.close()


def test_api_marcar_potrero_ordeno(tmp_path):
    ruta = str(tmp_path / "p.db")
    d = Database(ruta).create_tables()
    d.registrar_potrero(nombre="LA LOMA", codigo="P1")
    pid = d.query_one("SELECT id FROM potreros")["id"]
    d.close()
    app = crear_app(ruta, password="clave")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave"})
    assert c.post(f"/api/potrero/{pid}/ordeno", json={"valor": True}).get_json()["ok"]
    assert c.post(f"/api/potrero/{pid}/ordeno", json={"valor": "x"}).status_code == 400
    d = Database(ruta)
    assert d.query_one("SELECT ordeno FROM potreros")["ordeno"] == 1
    d.close()


def test_novillas_entoradas_solo_edad_real_de_primer_parto():
    filas = []
    for tag, meses_nac, parto_hace in (("PRIMERIZA", 30, 20), ("VIEJA_SIN_HISTORIA", 81, 3), ("TERNERA", 8, 30)):
        filas.append({"tag": tag, "nombre": "", "fecha_nacimiento": _d(-int(meses_nac * 30.44) - parto_hace),
                      "primer_parto": _d(-parto_hace), "ult_parto": _d(-parto_hace), "n_partos": 1,
                      "ult_diag_res": None, "ult_diag_fecha": None, "dias_gestacion": None,
                      "ult_serv_fecha": None, "tiene_prog_ia": 0})
    tags = {x["tag"] for x in _calcular_novillas_entoradas(filas, HOY)}
    assert tags == {"PRIMERIZA"}
