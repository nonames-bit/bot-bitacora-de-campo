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


# ── Reproducción: gestación, celo en preñada, palpación que no cuadra ──
from src.engine.calidad_datos import avisos_al_guardar  # noqa: E402


def test_repro_en_lista(db):
    _a(db, "CORTA")
    db.registrar_servicio("CORTA", fecha=_d(-200), tipo_servicio="IA")
    db.registrar_parto("CORTA", fecha=_d(-80), sexo_cria="Macho")  # 120 días
    _a(db, "LARGA")
    db.registrar_servicio("LARGA", fecha=_d(-340), tipo_servicio="IA")
    db.registrar_parto("LARGA", fecha=_d(-10), sexo_cria="Macho")  # 330 días
    _a(db, "BIEN")
    db.registrar_servicio("BIEN", fecha=_d(-300), tipo_servicio="IA")
    db.registrar_parto("BIEN", fecha=_d(-18), sexo_cria="Macho")  # 282 días
    _a(db, "CELOPRE")
    db.registrar_servicio("CELOPRE", fecha=_d(-120), tipo_servicio="IA")
    db.registrar_diagnostico("CELOPRE", fecha=_d(-80), resultado="PREÑADA", dias_gestacion=40)
    db.registrar_celo("CELOPRE", fecha=_d(-20))
    _a(db, "ABORTO_OK")
    db.registrar_diagnostico("ABORTO_OK", fecha=_d(-80), resultado="PREÑADA", dias_gestacion=40)
    db.registrar_diagnostico("ABORTO_OK", fecha=_d(-40), resultado="VACIA")
    db.registrar_servicio("ABORTO_OK", fecha=_d(-20), tipo_servicio="IA")
    _a(db, "PALP")
    db.registrar_servicio("PALP", fecha=_d(-50), tipo_servicio="IA")
    db.registrar_diagnostico("PALP", fecha=_d(-5), resultado="PREÑADA", dias_gestacion=120)
    t = _por_tipo(db)
    assert t["gestacion_corta"] == {"CORTA"}
    assert t["gestacion_larga"] == {"LARGA"}
    assert t["celo_en_prenada"] == {"CELOPRE"}
    assert t["palpacion_no_cuadra"] == {"PALP"}
    todos = set().union(*t.values())
    assert "BIEN" not in todos and "ABORTO_OK" not in todos


def test_aviso_al_guardar(db):
    _a(db, "V1")
    db.registrar_servicio("V1", fecha=_d(-120), tipo_servicio="IA")
    av = avisos_al_guardar(db, "parto", "V1", _d(0), {"tipo_evento": "PARTO"}, HOY)
    assert any("120 días" in a for a in av)
    # Como aborto no avisa por gestación corta.
    assert avisos_al_guardar(db, "parto", "V1", _d(0), {"tipo_evento": "ABORTO"}, HOY) == []
    # Parto con cría de 5 meses.
    _a(db, "V2")
    db.registrar_parto("V2", fecha=_d(-150), sexo_cria="Macho")
    av = avisos_al_guardar(db, "parto", "V2", _d(0), {}, HOY)
    assert any("150 días" in a for a in av)
    # Celo y servicio en preñada.
    db.registrar_diagnostico("V1", fecha=_d(-60), resultado="PREÑADA", dias_gestacion=60)
    assert avisos_al_guardar(db, "celo", "V1", _d(0), {}, HOY)
    assert avisos_al_guardar(db, "servicio", "V1", _d(0), {}, HOY)
    # Arete inexistente, macho y fecha futura.
    assert any("se va a crear" in a for a in avisos_al_guardar(db, "celo", "NOEXISTE", _d(0), {}, HOY))
    _a(db, "T1", sexo="Macho")
    assert any("macho" in a for a in avisos_al_guardar(db, "servicio", "T1", _d(0), {}, HOY))
    assert any("futuro" in a for a in avisos_al_guardar(db, "celo", "V2", _d(5), {}, HOY))
    assert not any("futuro" in a for a in avisos_al_guardar(db, "celo", "V2", _d(1), {}, HOY))
    # Palpación coherente con el servicio: sin avisos.
    _a(db, "V3")
    db.registrar_servicio("V3", fecha=_d(-45), tipo_servicio="IA")
    assert avisos_al_guardar(db, "palpacion", "V3", _d(0), {"resultado": "PREÑADA", "dias_gestacion": 45}, HOY) == []
    assert avisos_al_guardar(db, "palpacion", "V3", _d(0), {"resultado": "PREÑADA", "dias_gestacion": 150}, HOY)
    # Tipos sin aviso.
    assert avisos_al_guardar(db, "pesaje", "V3", _d(0), {}, HOY) == []


def test_endpoint_verificar_registro(tmp_path):
    from src.pwa.app import crear_app
    ruta = str(tmp_path / "v.db")
    d = Database(ruta).create_tables()
    d.registrar_animal("V9", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-2000))
    d.registrar_servicio("V9", fecha=_d(-120), tipo_servicio="IA")
    d.close()
    app = crear_app(ruta, password="clave")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave"})
    r = c.post("/api/verificar-registro", json={"tipo": "parto", "fecha": HOY.isoformat(),
                                                 "payload": {"vaca_tag": "V9"}}).get_json()
    assert r["ok"] and any("120 días" in a for a in r["avisos"])
    r = c.post("/api/verificar-registro", json={"tipo": "pesaje", "payload": {"animal_tag": "V9"}}).get_json()
    assert r["avisos"] == []
    d = Database(ruta)
    assert d.query_one("SELECT COUNT(*) n FROM partos")["n"] == 0
    d.close()
