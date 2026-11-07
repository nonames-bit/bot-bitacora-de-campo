"""Correcciones de indicadores reproductivos y de leche (revisión 2026-11):
IEP sin abortos, S/C y tasa de concepción por servicio, índice de fertilidad
con partos posteriores, días abiertos reales y DEL solo de vacas en ordeño."""
from datetime import date, timedelta

import pytest

from src.db.database import Database
from src.engine.dashboard_data import datos_leche, datos_reproduccion

HOY = date.today()


def d(n: int) -> str:
    return (HOY - timedelta(days=n)).isoformat()


@pytest.fixture
def db(tmp_path):
    base = Database(str(tmp_path / "ind.db"))
    base.create_tables()
    yield base
    base.close()


def test_iep_no_cuenta_aborto_como_parto(db):
    db.registrar_animal("V2", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V2", fecha=d(600), sexo_cria="Macho")
    db.registrar_parto("V2", fecha=d(400), tipo_evento="ABORTO")
    db.registrar_parto("V2", fecha=d(100), sexo_cria="Macho")
    assert db.intervalos_entre_partos() == [500]
    assert db.iep_promedio_hato()["iep_promedio_dias"] == 500
    dist = {t["tramo"]: t["cantidad"] for t in datos_reproduccion(db)["distribucion_iep"]}
    assert dist[">485"] == 1


def test_sc_y_concepcion_cuentan_cada_servicio_una_vez(db):
    # V1: 1 servicio, preñada (eco + palpación = 2 diagnósticos positivos).
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2000))
    db.registrar_servicio("V1", fecha=d(120))
    db.registrar_diagnostico("V1", fecha=d(85), resultado="PREÑADA", dias_gestacion=35)
    db.registrar_diagnostico("V1", fecha=d(60), resultado="PREÑADA", dias_gestacion=60)
    # V3: repitió (2 servicios, sin palpar el primero), preñada del segundo.
    db.registrar_animal("V3", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2000))
    db.registrar_servicio("V3", fecha=d(140))
    db.registrar_servicio("V3", fecha=d(119))
    db.registrar_diagnostico("V3", fecha=d(60), resultado="PREÑADA", dias_gestacion=59)
    k = db.kpis_reproductivos_concepcion()
    assert k["total_prenadas"] == 2
    assert k["total_vacias"] == 1
    assert k["servicios_por_concepcion"] == 1.5
    assert k["tasa_concepcion"] == 66.7


def test_doble_ia_mismo_celo_es_un_servicio(db):
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2000))
    db.registrar_servicio("V1", fecha=d(121))
    db.registrar_servicio("V1", fecha=d(120))
    db.registrar_diagnostico("V1", fecha=d(60), resultado="PREÑADA", dias_gestacion=60)
    k = db.kpis_reproductivos_concepcion()
    assert k["total_servicios"] == 1 and k["servicios_por_concepcion"] == 1.0


def test_servicio_confirmado_por_parto_sin_palpar(db):
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_servicio("V1", fecha=d(400))
    db.registrar_parto("V1", fecha=d(117), sexo_cria="Hembra")
    k = db.kpis_reproductivos_concepcion()
    assert k["total_prenadas"] == 1 and k["tasa_concepcion"] == 100.0


def test_servicio_reciente_sin_resultado_no_cuenta(db):
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2000))
    db.registrar_servicio("V1", fecha=d(10))
    k = db.kpis_reproductivos_concepcion()
    assert k["total_servicios"] == 1 and k["total_evaluados"] == 0
    assert k["servicios_por_concepcion"] is None


def test_indice_fertilidad_no_cuenta_preñez_que_ya_parió(db):
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V1", fecha=d(700), sexo_cria="Macho")
    db.registrar_servicio("V1", fecha=d(430))
    db.registrar_diagnostico("V1", fecha=d(370), resultado="PREÑADA", dias_gestacion=60)
    db.registrar_parto("V1", fecha=d(150), sexo_cria="Hembra")
    ind = datos_reproduccion(db)["indice_fertilidad"]
    assert ind["prenadas"] == 0
    assert ind["en_descanso"] == 0  # 150 días: ni preñada ni en descanso
    assert ind["indice_pct"] == 0.0


def test_dias_abiertos_reales_parto_a_preñez(db):
    db.registrar_animal("V3", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V3", fecha=d(200), sexo_cria="Macho")
    db.registrar_servicio("V3", fecha=d(140))
    db.registrar_servicio("V3", fecha=d(119))
    db.registrar_diagnostico("V3", fecha=d(60), resultado="PREÑADA", dias_gestacion=59)
    db.registrar_animal("V4", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V4", fecha=d(90), sexo_cria="Macho")  # sin servir
    k = datos_reproduccion(db)["kpis"]
    assert k["dias_abiertos_promedio"] == 81 and k["dias_abiertos_n"] == 1
    assert k["dias_vacias_hoy_promedio"] == 90 and k["dias_vacias_hoy_n"] == 1


def test_del_solo_vacas_en_ordeno(db):
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V1", fecha=d(100), sexo_cria="Macho")
    db.registrar_animal("V2", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_parto("V2", fecha=d(400), sexo_cria="Macho")  # >300 DEL: seca por regla vieja
    info = datos_leche(db)["analisis_del"]
    assert info["total_vacas"] == 1 and info["promedio_del"] == 100


def test_litros_vaca_dia_usa_solo_ultimos_dias(db):
    db.execute("INSERT INTO produccion_leche (fecha, litros) VALUES (?, ?)", (d(300), 1000))
    db.execute("INSERT INTO produccion_leche (fecha, litros) VALUES (?, ?)", (d(40), 100))
    res = datos_leche(db)["resumen"]
    assert res["promedio_diario_reciente"] == 100


def test_parto_se_atribuye_al_ultimo_servicio(db):
    # Servida, repitió a los 21 días y parió 283 días después del segundo:
    # el primero falló aunque el parto caiga a 304 días de él.
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=d(2500))
    db.registrar_servicio("V1", fecha=d(420))
    db.registrar_servicio("V1", fecha=d(399))
    db.registrar_parto("V1", fecha=d(116), sexo_cria="Hembra")
    k = db.kpis_reproductivos_concepcion()
    assert k["total_prenadas"] == 1 and k["total_vacias"] == 1
    assert k["servicios_por_concepcion"] == 2.0
