"""Listas de trabajo de todas las vistas (engine/tareas.py) y evento Manejo."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.tareas import _ciclo_aftosa, datos_tareas, invalidar_cache
from src.pwa.app import crear_app

HOY = date.today()


def _d(dias: int) -> str:
    return (HOY + timedelta(days=dias)).isoformat()


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "t.db")).create_tables()
    yield d
    d.close()


def _a(db, tag, sexo="Hembra", edad=2000, **kw):
    db.registrar_animal(tag, sexo=sexo, estado=kw.pop("estado", "ACTIVO"), fecha_nacimiento=_d(-edad), **kw)


def _tags(t, k):
    return {f["tag"] for f in t[k]}


def test_novillas_a_entorar(db):
    _a(db, "NOV", edad=500)
    _a(db, "NOV_LIVIANA", edad=500)
    db.registrar_pesaje("NOV_LIVIANA", fecha=_d(-10), peso_kg=250)
    _a(db, "TERNERA", edad=200)
    _a(db, "VACA_SIN_DATOS", edad=2500)
    t = datos_tareas(db, HOY)
    assert _tags(t, "novillas") == {"NOV"}
    assert "VACA_SIN_DATOS" in _tags(t, "chequeo")


def test_partos_proximos_y_atrasados(db):
    _a(db, "PROX")
    db.registrar_diagnostico("PROX", fecha=_d(-60), resultado="PREÑADA", dias_gestacion=210)  # 270 d
    _a(db, "ATRAS")
    db.registrar_diagnostico("ATRAS", fecha=_d(-120), resultado="PREÑADA", dias_gestacion=180)  # 300 d
    _a(db, "PARIO")
    db.registrar_diagnostico("PARIO", fecha=_d(-120), resultado="PREÑADA", dias_gestacion=180)
    db.registrar_parto("PARIO", fecha=_d(-10), sexo_cria="Macho")
    t = datos_tareas(db, HOY)
    partos = {f["tag"]: f for f in t["partos"]}
    assert partos["PROX"]["estado"] == "PROXIMO" and partos["PROX"]["en_dias"] == 13
    assert partos["ATRAS"]["estado"] == "ATRASADO"
    assert "PARIO" not in partos


def test_celos_esperados_y_repetidoras(db):
    _a(db, "CELO")
    db.registrar_parto("CELO", fecha=_d(-80), sexo_cria="Macho")
    db.registrar_celo("CELO", fecha=_d(-20), am_pm="AM")
    _a(db, "REP")
    db.registrar_parto("REP", fecha=_d(-200), sexo_cria="Hembra")
    for dias in (-150, -120, -90):
        db.registrar_servicio("REP", fecha=_d(dias))
    db.registrar_diagnostico("REP", fecha=_d(-50), resultado="VACIA")
    t = datos_tareas(db, HOY)
    assert "CELO" in _tags(t, "celos")
    rep = {f["tag"]: f for f in t["repetidoras"]}
    assert "3 servicios" in rep["REP"]["motivo"]
    assert "REP" in _tags(t, "descarte")


def test_manejo_topizar_castrar_marcar_y_vacunas(db):
    _a(db, "T60", sexo="Macho", edad=60)
    _a(db, "T60H", sexo="Hembra", edad=60)
    db.registrar_manejo("T60H", "TOPIZADO")
    _a(db, "M200", sexo="Macho", edad=200)
    _a(db, "M200E", sexo="Macho", edad=200)
    db.registrar_manejo("M200E", "ENTERO")
    _a(db, "TORO_JOVEN", sexo="Macho", edad=200, nombre="TORO SENATOR")
    _a(db, "H150", sexo="Hembra", edad=150)
    _a(db, "H300", sexo="Hembra", edad=300, hierro="JA")
    t = datos_tareas(db, HOY)
    assert _tags(t, "topizar") == {"T60"}
    assert _tags(t, "castrar") == {"M200"}
    assert "M200" in _tags(t, "marcar") and "H300" not in _tags(t, "marcar")
    assert _tags(t, "vac_brucelosis") == {"H150"}


def test_aftosa_por_ciclo_y_tratamiento_viejo(db):
    ini, _ = _ciclo_aftosa(HOY)
    _a(db, "VAC")
    db.registrar_manejo("VAC", "VACUNA_AFTOSA", fecha=ini.isoformat())
    _a(db, "TRAT")
    db.registrar_tratamiento("TRAT", fecha=HOY.isoformat(), producto="Vacuna Aftosa bivalente")
    _a(db, "VIEJA")
    db.registrar_manejo("VIEJA", "VACUNA_AFTOSA", fecha=(ini - timedelta(days=30)).isoformat())
    t = datos_tareas(db, HOY)
    assert "VIEJA" in _tags(t, "vac_aftosa")
    assert not ({"VAC", "TRAT"} & _tags(t, "vac_aftosa"))


def test_tratamientos_leche_y_carne(db):
    _a(db, "TR")
    db.registrar_tratamiento("TR", fecha=_d(-2), producto="Oxitetraciclina",
                             fecha_fin_retiro_leche=_d(3))
    _a(db, "DEL")
    db.registrar_parto("DEL", fecha=_d(-400), sexo_cria="Macho")
    _a(db, "PAUSA")
    db.registrar_parto("PAUSA", fecha=_d(-60), sexo_cria="Macho")
    db.registrar_pausa_ordeno("PAUSA", fecha_inicio=_d(-3))
    _a(db, "FLACO", sexo="Macho", edad=500)
    db.registrar_pesaje("FLACO", fecha=_d(-60), peso_kg=300)
    db.registrar_pesaje("FLACO", fecha=_d(-5), peso_kg=305)
    _a(db, "GORDO", sexo="Macho", edad=800)
    db.registrar_pesaje("GORDO", fecha=_d(-5), peso_kg=450)
    _a(db, "ABUELA", edad=4000)
    _a(db, "LEV", sexo="Hembra", edad=370)
    t = datos_tareas(db, HOY)
    trat = {f["tag"]: f for f in t["tratamientos"]}
    assert "Retiro de leche" in trat["TR"]["detalle"] and "Oxitetraciclina" in trat["TR"]["detalle"]
    secar = {f["tag"]: f for f in t["secar"]}
    assert "Lactancia larga" in secar["DEL"]["motivo"]
    assert "PAUSA" in _tags(t, "pausas")
    assert "FLACO" in _tags(t, "bajo_peso")
    assert "GORDO" in _tags(t, "venta") and "FLACO" not in _tags(t, "venta")
    assert "ABUELA" in _tags(t, "descarte")
    cat = {f["tag"]: f for f in t["categoria"]}
    assert cat["LEV"]["cambio"] == "Cría → Levante"


def test_vendidos_no_aparecen_en_ninguna_lista(db):
    _a(db, "VEND", sexo="Macho", edad=60, estado="VENDIDO")
    t = datos_tareas(db, HOY)
    assert all("VEND" not in _tags(t, k) for k in t["conteos"])


def test_manejo_por_sync_con_varios_animales_y_cache(tmp_path):
    ruta = str(tmp_path / "s.db")
    d = Database(ruta).create_tables()
    for tag in ("A1", "A2"):
        d.registrar_animal(tag, sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-60))
    d.close()
    invalidar_cache()
    db = Database(ruta)
    assert datos_tareas(db, HOY, usar_cache=True)["conteos"]["topizar"] == 2
    app = crear_app(ruta, password="clave")
    app.config.update({"TESTING": True})
    c = app.test_client()
    c.post("/login", data={"password": "clave"})
    r = c.post("/api/sync", json={"eventos": [{"tipo": "manejo", "fecha": HOY.isoformat(),
                                              "payload": {"animal_tags": ["A1", "A2"], "tipo_manejo": "TOPIZADO"}}]})
    assert r.get_json()["procesados"] == 1
    assert datos_tareas(db, HOY, usar_cache=True)["conteos"]["topizar"] == 0
    db.close()


def test_manejo_tipo_invalido(db):
    _a(db, "X")
    with pytest.raises(ValueError):
        db.registrar_manejo("X", "OTRA_COSA")


def test_secar_preñez_7_meses_y_una_fila_si_cumple_ambas(db):
    _a(db, "P212")
    db.registrar_diagnostico("P212", fecha=_d(-62), resultado="PREÑADA", dias_gestacion=150)
    _a(db, "AMBAS")
    db.registrar_parto("AMBAS", fecha=_d(-400), sexo_cria="Macho")
    db.registrar_diagnostico("AMBAS", fecha=_d(-70), resultado="PREÑADA", dias_gestacion=150)
    t = datos_tareas(db, HOY)
    secar = {f["tag"]: f for f in t["secar"]}
    assert "Preñez" in secar["P212"]["motivo"]
    assert [f["tag"] for f in t["secar"]].count("AMBAS") == 1
    assert "Preñez" in secar["AMBAS"]["motivo"] and "Lactancia larga" in secar["AMBAS"]["motivo"]


def test_estado_toros_manual_potrero_y_solo(db):
    from src.engine.tareas import estado_toros
    db.registrar_potrero(nombre="OLEGARIO", codigo="O1")
    db.registrar_potrero(nombre="SOLO", codigo="S1")
    db.registrar_animal("T01", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-1500), potrero="OLEGARIO")
    db.registrar_animal("T02", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-1500), potrero="OLEGARIO")
    db.registrar_animal("T03", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-1500), potrero="SOLO")
    for i in range(3):
        db.registrar_animal(f"V{i}", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-1500), potrero="OLEGARIO")
    db.registrar_manejo("T02", "TORO_DESCANSO")
    est = {t["tag"]: t for t in estado_toros(db, HOY)}
    assert est["T01"]["estado"] == "EN_SERVICIO" and "3 hembras" in est["T01"]["motivo"]
    assert est["T02"]["estado"] == "EN_DESCANSO" and est["T02"]["fuente"] == "MANUAL"
    assert est["T03"]["estado"] == "EN_DESCANSO"
    db.registrar_manejo("T02", "TORO_SERVICIO")
    assert {t["tag"]: t for t in estado_toros(db, HOY)}["T02"]["estado"] == "EN_SERVICIO"
