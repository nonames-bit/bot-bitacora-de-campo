"""Crías huérfanas (madre muerta) y fichas de animales dados de baja."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.dashboard_data import datos_ficha_animal
from src.engine.tareas import datos_tareas, invalidar_cache

HOY = date.today()


def _d(dias: int) -> str:
    return (HOY + timedelta(days=dias)).isoformat()


@pytest.fixture
def db(tmp_path):
    invalidar_cache()
    d = Database(str(tmp_path / "t.db")).create_tables()
    d.registrar_animal("V082", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-2500))
    d.registrar_animal("V082-6", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-17), madre_tag="V082")
    d.registrar_parto("V082", fecha=_d(-17), id_cria_tag="V082-6", sexo_cria="MACHO")
    yield d
    d.close()


def test_cria_con_madre_viva_no_es_huerfana(db):
    assert datos_ficha_animal(db, "V082-6")["huerfana"] is None
    assert datos_tareas(db, HOY, usar_cache=False)["huerfanas"] == []


def test_madre_muerta_marca_cria_huerfana(db):
    db.registrar_muerte("V082", fecha=_d(-8))
    f = datos_ficha_animal(db, "V082-6")
    assert f["huerfana"] == {"madre": "V082", "fecha_muerte": _d(-8)}
    assert "Huérfana" in f["estado_fisiologico"]["detalle"]
    t = datos_tareas(db, HOY, usar_cache=False)
    assert [h["tag"] for h in t["huerfanas"]] == ["V082-6"]
    assert t["huerfanas"][0]["muerte_madre"] == _d(-8)
    assert t["conteos"]["huerfanas"] == 1


def test_cria_destetada_o_muerta_no_es_huerfana(db):
    db.registrar_muerte("V082", fecha=_d(-8))
    db.registrar_destete("V082-6", fecha=_d(-1), peso_kg=60)
    assert datos_ficha_animal(db, "V082-6")["huerfana"] is None
    assert datos_tareas(db, HOY, usar_cache=False)["huerfanas"] == []


def test_vaca_muerta_sin_estado_de_ordeno_ni_reproductivo(db):
    db.registrar_muerte("V082", fecha=_d(-8))
    f = datos_ficha_animal(db, "V082")
    assert f["estado_fisiologico"]["codigo"] == "BAJA"
    assert f["estado_fisiologico"]["badge"] == ""
    assert f["estado_reproductivo"]["codigo"] == "BAJA"
    assert f["estado_reproductivo"]["badge"] == ""
    assert _d(-8) in f["estado_fisiologico"]["detalle"]
