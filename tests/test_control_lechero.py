"""Control lechero por vaca (engine/control_lechero.py): registro idempotente,
sync offline y listas de baja producción, caída y sin control."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.control_lechero import resumen_control, vacas_para_control
from src.engine.tareas import datos_tareas
from src.pwa.app import crear_app

HOY = date.today()


def _d(n):
    return (HOY + timedelta(days=n)).isoformat()


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "c.db")).create_tables()
    d.registrar_potrero(nombre="ORDENO SANTA MARTHA", codigo="P1")
    d.registrar_potrero(nombre="OLEGARIO II", codigo="P2")
    yield d
    d.close()


def _vaca(db, tag, parto, potrero="ORDENO SANTA MARTHA"):
    db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-2000), potrero=potrero)
    db.registrar_parto(tag, fecha=_d(-parto), sexo_cria="Macho")


def test_registro_idempotente_y_no_toca_el_tanque(db):
    _vaca(db, "V1", 60)
    db.registrar_produccion_leche(fecha=_d(0), litros=300)  # tanque
    db.registrar_control_leche("V1", fecha=_d(0), litros_am=8, litros_pm="6,5")
    db.registrar_control_leche("V1", fecha=_d(0), litros_am=9, litros_pm=6)  # corrige
    filas = db.query("SELECT animal_id, litros, notas FROM produccion_leche ORDER BY id")
    assert [(r["litros"]) for r in filas if r["animal_id"] is None] == [300]
    vaca = [r for r in filas if r["animal_id"] is not None]
    assert len(vaca) == 1 and vaca[0]["litros"] == 15 and "AM 9" in vaca[0]["notas"]
    assert db.registrar_control_leche("V1", fecha=_d(0)) is None
    with pytest.raises(ValueError):
        db.registrar_control_leche("NOEXISTE", fecha=_d(0), litros_am=5)


def test_vacas_para_control_solo_en_ordeno(db):
    _vaca(db, "ORD", 60)
    _vaca(db, "SECA", 400, potrero="OLEGARIO II")
    tags = {v["tag"] for v in vacas_para_control(db, HOY)}
    assert tags == {"ORD"}


def test_resumen_baja_caida_sin_control_y_tanque(db):
    for i in range(4):
        _vaca(db, f"N{i}", 50)
        db.registrar_control_leche(f"N{i}", fecha=_d(-2), litros_am=10, litros_pm=10)  # 20 L
    _vaca(db, "BAJA", 50)
    db.registrar_control_leche("BAJA", fecha=_d(-2), litros_am=4, litros_pm=4)  # 8 L < 60 %
    _vaca(db, "CAE", 50)
    db.registrar_control_leche("CAE", fecha=_d(-32), litros_am=12, litros_pm=12)  # 24 → 16 L
    db.registrar_control_leche("CAE", fecha=_d(-2), litros_am=8, litros_pm=8)
    _vaca(db, "NUNCA", 50)
    db.registrar_produccion_leche(fecha=_d(-2), litros=120)
    r = resumen_control(db, HOY)
    u = r["ultimo"]
    assert u["vacas"] == 6 and u["total_litros"] == 104 and u["tanque_litros"] == 120 and u["cobertura_pct"] == 87
    assert r["top"][0]["litros"] == 20
    assert {x["tag"] for x in r["baja_produccion"]} == {"BAJA"}
    assert {x["tag"] for x in r["caida"]} == {"CAE"} and r["caida"][0]["caida_pct"] == 33
    assert {x["tag"] for x in r["sin_control"]} == {"NUNCA"}
    assert {x["tag"] for x in datos_tareas(db, HOY)["control_leche"]} == {"NUNCA"}


def test_sync_control_leche(tmp_path):
    ruta = str(tmp_path / "s.db")
    d = Database(ruta).create_tables()
    d.registrar_animal("V9", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-2000))
    d.close()
    app = crear_app(ruta, password="x")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "x"})
    ev = {"tipo": "control_leche", "fecha": _d(0), "id_local": "cl1",
          "payload": {"registros": [{"tag": "V9", "am": 7, "pm": 5}, {"tag": "FALTA", "am": 3}]}}
    r = c.post("/api/sync", json={"eventos": [ev]}).get_json()
    assert r["procesados"] == 1 and "cl1" in r["ids_ok"] and any("FALTA" in e for e in r["errores"])
    r2 = c.post("/api/sync", json={"eventos": [ev]}).get_json()  # reintento de la cola: no duplica
    assert "cl1" in r2["ids_ok"]
    d = Database(ruta)
    assert d.query_one("SELECT COUNT(*) n, SUM(litros) l FROM produccion_leche WHERE animal_id IS NOT NULL")["l"] == 12
    d.close()
