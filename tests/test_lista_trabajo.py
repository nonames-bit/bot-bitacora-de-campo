"""Lista de trabajo reproductiva y chequeo general del hato (PWA)."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.dashboard_data import datos_badges, datos_lista_trabajo

HOY = date.today()


def _d(dias: int) -> str:
    return (HOY + timedelta(days=dias)).isoformat()


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "lt.db")).create_tables()
    yield d
    d.close()


def _vaca(db, tag, **kw):
    db.registrar_animal(tag, sexo="Hembra", estado=kw.pop("estado", "ACTIVO"),
                        fecha_nacimiento=kw.pop("nac", _d(-2000)), **kw)


def _tags(lt, clave):
    return {f["tag"] for f in lt[clave]}


def test_dato_viejo_va_a_chequeo_y_no_a_otras_listas(db):
    _vaca(db, "VIEJA")
    db.registrar_servicio("VIEJA", fecha="2017-03-01")
    db.registrar_diagnostico("VIEJA", fecha="2017-05-01", resultado="VACIA")
    _vaca(db, "SIN_NADA")
    lt = datos_lista_trabajo(db, HOY)
    assert {"VIEJA", "SIN_NADA"} <= _tags(lt, "chequeo")
    for k in ("palpar", "secar", "servir"):
        assert not ({"VIEJA", "SIN_NADA"} & _tags(lt, k))


def test_palpar_desde_dia_35(db):
    _vaca(db, "S40")
    db.registrar_servicio("S40", fecha=_d(-40))
    _vaca(db, "S20")
    db.registrar_servicio("S20", fecha=_d(-20))
    lt = datos_lista_trabajo(db, HOY)
    assert "S40" in _tags(lt, "palpar")
    assert "S20" not in _tags(lt, "palpar") and "S20" not in _tags(lt, "chequeo")


def test_secar_por_gestacion_estimada_y_no_si_ya_seca(db):
    _vaca(db, "P230")
    db.registrar_diagnostico("P230", fecha=_d(-80), resultado="PREÑADA", dias_gestacion=150)
    _vaca(db, "P230S")
    db.registrar_diagnostico("P230S", fecha=_d(-80), resultado="PREÑADA", dias_gestacion=150)
    db.registrar_secado("P230S", fecha=_d(-5))
    _vaca(db, "P100")
    db.registrar_diagnostico("P100", fecha=_d(-10), resultado="PREÑADA", dias_gestacion=90)  # 100 d
    lt = datos_lista_trabajo(db, HOY)
    secar = {f["tag"]: f for f in lt["secar"]}
    assert "P230" in secar and secar["P230"]["dias_gestacion"] == 230
    assert "P230S" not in secar and "P100" not in secar


def test_servir_vacia_posparto_sin_ia_programada(db):
    _vaca(db, "V1")
    db.registrar_parto("V1", fecha=_d(-90), sexo_cria="Macho")
    db.registrar_diagnostico("V1", fecha=_d(-30), resultado="VACIA")
    _vaca(db, "V2")
    db.registrar_parto("V2", fecha=_d(-90), sexo_cria="Macho")
    db.registrar_diagnostico("V2", fecha=_d(-30), resultado="VACIA")
    db.registrar_alerta("V2", "INSEMINACION_PROGRAMADA", fecha_programada=_d(2))
    _vaca(db, "RECIEN")
    db.registrar_parto("RECIEN", fecha=_d(-20), sexo_cria="Hembra")
    lt = datos_lista_trabajo(db, HOY)
    assert "V1" in _tags(lt, "servir")
    assert "V2" not in _tags(lt, "servir") and "RECIEN" not in _tags(lt, "servir")


def test_destetar_crias_de_8_a_12_meses_sin_destete(db):
    _vaca(db, "MADRE")
    db.registrar_animal("C250", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-250), madre_tag="MADRE")
    db.registrar_animal("C250D", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-250), madre_tag="MADRE")
    db.registrar_destete("C250D", fecha=_d(-3))
    db.registrar_animal("C100", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-100), madre_tag="MADRE")
    db.registrar_animal("ADULTA", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-900), madre_tag="MADRE")
    lt = datos_lista_trabajo(db, HOY)
    assert _tags(lt, "destetar") == {"C250"}


def test_vendidos_nunca_aparecen(db):
    _vaca(db, "VENDIDA", estado="VENDIDO")
    db.registrar_servicio("VENDIDA", fecha=_d(-40))
    lt = datos_lista_trabajo(db, HOY)
    for k in ("chequeo", "palpar", "secar", "servir", "destetar"):
        assert "VENDIDA" not in _tags(lt, k)


def test_diagnostico_del_chequeo_saca_a_la_vaca_del_chequeo(db):
    _vaca(db, "CHK")
    assert "CHK" in _tags(datos_lista_trabajo(db, HOY), "chequeo")
    db.registrar_diagnostico("CHK", fecha=HOY.isoformat(), resultado="PREÑADA", dias_gestacion=150,
                             metodo="TACTO", detalle="Chequeo del hato")
    lt = datos_lista_trabajo(db, HOY)
    assert "CHK" not in _tags(lt, "chequeo")


def test_badge_repro_incluye_lista_de_trabajo(db):
    _vaca(db, "S40")
    db.registrar_servicio("S40", fecha=_d(-40))
    assert datos_badges(db)["repro"] >= 1
