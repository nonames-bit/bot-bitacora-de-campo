"""Más → Indicadores (engine/indicadores.py + /api/indicadores): cada
indicador con su valor, meta y color sobre los últimos 12 meses."""
import json
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.indicadores import color, indicadores_hato
from src.pwa.app import crear_app

HOY = date.today()


def d(n: int) -> str:
    return (HOY - timedelta(days=n)).isoformat()


def _items(res) -> dict:
    return {i["k"]: i for g in res["grupos"] for i in g["items"]}


@pytest.fixture
def db(tmp_path):
    base = Database(str(tmp_path / "ind.db"))
    base.create_tables()
    yield base
    base.close()


def test_color_segun_meta():
    assert color("iep", 390) == "verde"
    assert color("iep", 430) == "ambar"
    assert color("iep", 500) == "rojo"
    assert color("natalidad", 80) == "verde"
    assert color("natalidad", 50) == "rojo"
    assert color("periodo_seco", 60) == "verde"
    assert color("periodo_seco", 85) == "ambar"
    assert color("periodo_seco", 20) == "rojo"
    assert color("iep", None) == "gris"
    assert color("no_existe", 5) == "gris"


def test_hato_vacio_no_falla(db):
    res = indicadores_hato(db)
    assert not res.get("errores")
    assert {g["k"] for g in res["grupos"]} == {"reproduccion", "leche", "carne", "sanidad", "pasturas"}
    assert all(i["color"] == "gris" for g in res["grupos"] for i in g["items"])


def test_reproduccion(db):
    # V1: parto hace 400 d, servida a los 70 d (vacía), repite a los 91 d, preñada, pare.
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V1", fecha=d(800), sexo_cria="Macho")
    db.registrar_parto("V1", fecha=d(400), sexo_cria="Macho")
    db.registrar_servicio("V1", fecha=d(330))
    db.registrar_servicio("V1", fecha=d(309))
    db.registrar_parto("V1", fecha=d(26), sexo_cria="Hembra")  # 283 d después del 2.º
    # V2: parida hace 200 d y sin servir -> vaca problema.
    db.registrar_animal("V2", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V2", fecha=d(600), sexo_cria="Macho")
    db.registrar_parto("V2", fecha=d(200), sexo_cria="Macho")
    # N1: novilla, primer parto hace 100 d con 31 meses.
    db.registrar_animal("N1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(100 + int(31 * 30.44)))
    db.registrar_parto("N1", fecha=d(100), sexo_cria="Macho")
    res = indicadores_hato(db)
    it = _items(res)
    assert it["iep"]["valor"] == 387 and it["iep"]["color"] == "verde"
    assert it["dias_primer_servicio"]["valor"] == 70
    assert it["concepcion_primer_servicio"]["valor"] == 0.0
    assert it["servicios_concepcion"]["valor"] == 2.0
    assert it["dias_abiertos"]["valor"] == 91
    assert it["prenadas_150"]["valor"] == 0.0 or it["prenadas_150"]["n"] >= 1
    assert it["natalidad"]["valor"] == 100.0  # 3 de 3 vientres parieron
    assert 30.5 <= it["edad_primer_parto"]["valor"] <= 31.5
    tags = [v["tag"] for v in res["vacas_problema"]]
    assert tags == ["V2"]


def test_leche_y_lactancia(db):
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V1", fecha=d(660), sexo_cria="Macho")
    db.registrar_secado("V1", fecha=d(380))           # lactancia de 280 d (antes de la ventana)
    db.registrar_parto("V1", fecha=d(320), sexo_cria="Macho")  # 60 d seca
    db.registrar_secado("V1", fecha=d(40))            # lactancia de 280 d
    for dd, lt in ((30, 10), (60, 12), (90, 11), (180, 9), (240, 7)):
        db.registrar_control_leche("V1", fecha=d(320 - dd), litros_am=lt / 2, litros_pm=lt / 2)
    db.registrar_animal("V2", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V2", fecha=d(320), sexo_cria="Macho")  # >305 DEL, vacía
    for k in range(1, 11):
        db.registrar_produccion_leche(fecha=d(k), litros=20)
    res = indicadores_hato(db)
    it = _items(res)
    assert it["periodo_seco"]["valor"] == 60 and it["periodo_seco"]["color"] == "verde"
    assert it["duracion_lactancia"]["valor"] == 280
    assert it["dias_al_pico"]["valor"] == 60
    assert it["persistencia"]["valor"] == 75.0  # 9 / 12
    assert it["litros_lactancia"]["n"] == 1 and it["litros_lactancia"]["valor"] > 2000
    assert it["litros_vaca_hato"]["valor"] == 10.0  # 20 L entre 2 vacas paridas
    assert [x["tag"] for x in res["lactancias_largas"]] in ([], ["V2"])


def test_carne_y_mortalidad(db):
    db.registrar_animal("M1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("M1", fecha=d(300), sexo_cria="Macho", id_cria_tag="C1", peso_nacimiento=30)
    db.registrar_destete("C1", fecha=d(95), peso_kg=180, peso_madre_kg=420)
    db.registrar_animal("C2", sexo="Macho", estado="ACTIVO", fecha_nacimiento=d(150))
    db.registrar_muerte("C2", fecha=d(10))
    res = indicadores_hato(db)
    it = _items(res)
    assert it["kg_destetados_vaca"]["valor"] == 180
    assert it["destete_pct_madre"]["valor"] == round(180 * 100 / 420, 1)
    assert it["peso_destete_205"]["valor"] == 180  # destetado justo a 205 días
    assert it["mortalidad_crias"]["valor"] == 100.0  # 1 muerta / 1 nacida en el año


def test_api_solo_owner_y_admin(tmp_path):
    db_path = str(tmp_path / "api.db")
    users = tmp_path / "users.json"
    users.write_text(json.dumps([{"user_id": 1, "username": "o", "rol": "OWNER"},
                                 {"user_id": 2, "username": "t", "rol": "TRABAJADOR"}]), encoding="utf-8")
    base = Database(db_path)
    base.create_tables()
    base.close()
    client = crear_app(db_path=db_path, users_file=str(users)).test_client()
    with client.session_transaction() as s:
        s.update(autenticado=True, user_id=2, rol="TRABAJADOR")
    assert client.get("/api/indicadores").status_code == 403
    with client.session_transaction() as s:
        s.update(autenticado=True, user_id=1, rol="OWNER")
    r = client.get("/api/indicadores")
    assert r.status_code == 200 and r.get_json()["grupos"]
