"""Regresiones de genética y composición racial (revisión integral)."""
import pytest

from src.db.database import Database
from src.engine.genetic_engine import (
    calcular_cruce_absorbente,
    clasificar_animal_zootecnico,
    parsear_texto_raza,
)
from src.exporters.dbf_exporter import export_hoja_dbf
from src.importers.dbf_importer import DBFReader


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "b.db")).create_tables()
    yield d
    d.close()


def _pcts(comp):
    return {c["raza"]: c["porcentaje"] for c in comp}


def test_padre_desconocido_no_copia_a_la_madre():
    res = calcular_cruce_absorbente([{"raza": "Brahman", "porcentaje": 100}], [])
    assert _pcts(res) == {"Brahman": 50.0, "Desconocida": 50.0}
    assert all("F1" not in c["fraccion"] for c in res)


@pytest.mark.parametrize("pct, codigo", [
    (93.75, "15_16"), (81.25, "13_16"), (68.75, "11_16"), (56.25, "9_16"),
    (75.0, "3_4"), (87.5, "7_8"), (62.5, "5_8"),
])
def test_grados_absorbentes(pct, codigo):
    comp = [{"raza": "Gyr", "porcentaje": pct}, {"raza": "Holstein", "porcentaje": 100 - pct}]
    assert clasificar_animal_zootecnico(comp)["grado_codigo"] == codigo


def test_variedades_de_color_son_la_misma_raza():
    res = calcular_cruce_absorbente([{"raza": "Holstein", "porcentaje": 100}],
                                    [{"raza": "Holstein Negro", "porcentaje": 100}])
    assert _pcts(res) == {"Holstein": 100.0}
    assert clasificar_animal_zootecnico([{"raza": "Criolla", "porcentaje": 50},
                                         {"raza": "Criollo", "porcentaje": 50}])["grado_codigo"] == "PURO"


def test_mestizo_no_es_puro_y_texto_sin_composicion_se_clasifica():
    assert clasificar_animal_zootecnico([{"raza": "Mestizo", "porcentaje": 100}])["grado_codigo"] == "MULTI"
    assert clasificar_animal_zootecnico([], "Brahman")["grado_codigo"] == "PURO"
    assert clasificar_animal_zootecnico([], "C")["grado_codigo"] == "CEBU"


def test_parte_sin_fraccion_recibe_el_resto():
    assert _pcts(parsear_texto_raza("3/4 Gyr + Holstein")) == {"Gyr": 75.0, "Holstein": 25.0}


def test_guardar_composicion_suma_baja_completa_desconocida(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    assert db.guardar_composicion_racial("47", [{"raza": "Gyr", "porcentaje": 50},
                                                {"raza": "Holstein", "porcentaje": 25}])
    assert _pcts(db.obtener_composicion_racial("47")) == {"Gyr": 50.0, "Holstein": 25.0, "Desconocida": 25.0}
    assert db.guardar_composicion_racial("47", [{"raza": "Gyr", "porcentaje": 150}]) is False


def test_parto_con_pajuela_no_crea_toro_y_usa_su_raza(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.guardar_composicion_racial("47", [{"raza": "Gyr", "porcentaje": 100}])
    db.registrar_pajuela(codigo_toro="HOL502", cantidad=5, raza="Holstein")
    db.registrar_parto("47", fecha="2026-09-20", sexo_cria="Hembra", id_cria_tag="C1", padre_tag="HOL502")
    assert db.animal_id("HOL502") is None
    assert _pcts(db.obtener_composicion_racial("C1")) == {"Gyr": 50.0, "Holstein": 50.0}


def test_parto_sin_padre_no_inventa_composicion(db):
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO")
    db.guardar_composicion_racial("48", [{"raza": "Brahman", "porcentaje": 100}])
    db.registrar_parto("48", fecha="2026-09-20", sexo_cria="Macho", id_cria_tag="C2")
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM composicion_racial WHERE animal_id = ?", (db.animal_id("C2"),)
    )["n"] == 0


def test_exportar_hoja_dbf_conserva_composicion(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.guardar_composicion_racial("47", [{"raza": "Gyr", "porcentaje": 75},
                                         {"raza": "Holstein", "porcentaje": 25}])
    fila = next(r for r in DBFReader(export_hoja_dbf(db)).records() if str(r["CODANI"]).strip() == "47")
    assert (str(fila["CODGR1"]).strip(), float(fila["PORGR1"])) == ("04", 75.0)
    assert (str(fila["CODGR2"]).strip(), float(fila["PORGR2"])) == ("03", 25.0)
