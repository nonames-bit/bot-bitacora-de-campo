"""Datos a revisar (engine/calidad_datos.py): un caso por revisión y sus negativos."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.calidad_datos import problemas_de_animal, revisar_datos
from src.engine.dashboard_data import datos_ficha_animal, datos_inventario

HOY = date.today()


def _d(dias: int) -> str:
    return (HOY + timedelta(days=dias)).isoformat()


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "c.db")).create_tables()
    yield d
    d.close()


def _a(db, tag, sexo="Hembra", edad=2000, **kw):
    db.registrar_animal(tag, sexo=sexo, estado=kw.pop("estado", "ACTIVO"),
                        fecha_nacimiento=_d(-edad) if edad is not None else None, **kw)


def _por_tipo(db):
    out: dict[str, set] = {}
    for p in revisar_datos(db, HOY):
        out.setdefault(p["tipo"], set()).add(p["tag"])
    return out


def test_cada_revision_detecta_su_caso(db):
    _a(db, "MADRE")
    _a(db, "TERNERA", edad=240, madre_tag="MADRE")
    db.registrar_parto("TERNERA", fecha=_d(-30), sexo_cria="Macho")
    _a(db, "TORO9", sexo="Macho")
    db.registrar_servicio("TORO9", fecha=_d(-50))
    _a(db, "FUTURA")
    db.registrar_pesaje("FUTURA", fecha=_d(40), peso_kg=400)
    _a(db, "ANTES", edad=100)
    db.registrar_pesaje("ANTES", fecha=_d(-300), peso_kg=30)
    _a(db, "SEGUIDOS")
    db.registrar_parto("SEGUIDOS", fecha=_d(-300), sexo_cria="Macho")
    db.registrar_parto("SEGUIDOS", fecha=_d(-150), sexo_cria="Hembra")
    _a(db, "PAPA", sexo="Macho")
    _a(db, "HIJO", edad=300, madre_tag="PAPA")
    _a(db, "GORDO", sexo="Macho")
    db.registrar_pesaje("GORDO", fecha=_d(-5), peso_kg=4500)
    _a(db, "MATUSALEN", edad=30 * 366)
    _a(db, "SINSEXO", sexo=None)
    t = _por_tipo(db)
    assert t["parto_en_ternera"] == {"TERNERA"}
    assert t["macho_con_partos"] == {"TORO9"}
    assert t["fecha_futura"] == {"FUTURA"}
    assert t["evento_antes_de_nacer"] == {"ANTES"}
    assert t["partos_muy_seguidos"] == {"SEGUIDOS"}
    assert "HIJO" in t["madre_imposible"]
    assert t["peso_absurdo"] == {"GORDO"}
    assert t["edad_absurda"] == {"MATUSALEN"}
    assert t["sin_sexo"] == {"SINSEXO"}
    detalle = next(p for p in revisar_datos(db, HOY) if p["tipo"] == "parto_en_ternera")["detalle"]
    assert "MADRE" in detalle


def test_negativos_gemelos_primeriza_y_vendidos(db):
    _a(db, "GEM")
    pid = db.registrar_parto("GEM", fecha=_d(-100), sexo_cria="Macho", tipo_evento="GEMELAR")
    db.registrar_parto("GEM", fecha=_d(-100), sexo_cria="Hembra", tipo_evento="GEMELAR", grupo_parto_id=pid)
    _a(db, "PRIMERIZA", edad=900)
    db.registrar_parto("PRIMERIZA", fecha=_d(-20), sexo_cria="Macho")
    _a(db, "NORMAL")
    db.registrar_parto("NORMAL", fecha=_d(-800), sexo_cria="Macho")
    db.registrar_parto("NORMAL", fecha=_d(-400), sexo_cria="Macho")
    db.registrar_pesaje("NORMAL", fecha=_d(-3), peso_kg=520)
    _a(db, "VIEJA_VENDIDA", edad=30 * 366, estado="VENDIDO")
    _a(db, "SIN_SEXO_MUERTO", sexo=None, estado="MUERTO")
    assert revisar_datos(db, HOY) == []


def test_ficha_e_inventario_muestran_los_problemas(db):
    _a(db, "GORDO", sexo="Macho")
    db.registrar_pesaje("GORDO", fecha=_d(-5), peso_kg=4500)
    aid = db.query_one("SELECT id_animal FROM animales WHERE tag='GORDO'")["id_animal"]
    assert [p["tipo"] for p in problemas_de_animal(db, aid, HOY)] == ["peso_absurdo"]
    f = datos_ficha_animal(db, "GORDO")
    assert any("4500" in a for a in f["avisos_datos"])
    inv = datos_inventario(db)
    assert [p["tag"] for p in inv["datos_revisar"]] == ["GORDO"]
