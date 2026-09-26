"""Pruebas del módulo Carne y de los gaps de Reproducción (PWA, solo lectura).

Cubre `dashboard_data.datos_carne` (Animales sin pesar, a pesar por edad,
destete/índice productivo, proyección de destetes, prueba de comportamiento)
y las 6 claves nuevas de `dashboard_data.datos_reproduccion`.
"""
from datetime import date, timedelta

from src.engine.dashboard_data import datos_carne, datos_reproduccion


def _d(dias: int) -> str:
    return (date.today() + timedelta(days=dias)).isoformat()


def _tags(filas, campo="tag"):
    return {f[campo] for f in filas}


# --------------------------------------------------------------------------- #
# 1 y 2) Sin pesar / a pesar por edad
# --------------------------------------------------------------------------- #
def test_sin_pesar_separa_nunca_de_vencido_y_filtra_activos(db):
    db.registrar_animal("C1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-1000))
    db.registrar_animal("C2", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-1000))
    db.registrar_animal("C3", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-1000))
    db.registrar_animal("MUERTO1", sexo="Hembra", estado="VENDIDO", fecha_nacimiento=_d(-1000))
    db.registrar_pesaje("C2", fecha=_d(-90), peso_kg=300)
    db.registrar_pesaje("C3", fecha=_d(-10), peso_kg=310)
    db.registrar_pesaje("MUERTO1", fecha=_d(-200), peso_kg=200)

    out = datos_carne(db)
    nunca = _tags(out["sin_pesar"]["nunca"])
    vencidos = _tags(out["sin_pesar"]["vencidos"])
    assert "C1" in nunca
    assert "C3" not in nunca and "C3" not in vencidos
    assert "C2" in vencidos
    assert "MUERTO1" not in nunca and "MUERTO1" not in vencidos
    assert out["kpis"]["sin_pesar_nunca"] == len(out["sin_pesar"]["nunca"])


def test_a_pesar_por_edad_frecuencia_por_categoria(db):
    db.registrar_animal("CRIA", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-100))
    db.registrar_animal("LEVANTE", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-300))
    db.registrar_animal("ADULTO_VENCIDO", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-1200))
    db.registrar_animal("ADULTO_OK", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-1200))
    db.registrar_animal("SIN_FECHA", sexo="Hembra", estado="ACTIVO")
    db.registrar_pesaje("ADULTO_VENCIDO", fecha=_d(-100), peso_kg=400)
    db.registrar_pesaje("ADULTO_OK", fecha=_d(-50), peso_kg=400)

    out = datos_carne(db)
    por_tag = {f["tag"]: f for f in out["a_pesar_edad"]}
    assert por_tag["CRIA"]["frecuencia_dias"] == 30
    assert por_tag["LEVANTE"]["frecuencia_dias"] == 60
    assert por_tag["ADULTO_VENCIDO"]["frecuencia_dias"] == 90
    assert "ADULTO_OK" not in por_tag
    assert out["sin_fecha_nacimiento_n"] == 1


# --------------------------------------------------------------------------- #
# 3) Destete / Índice productivo
# --------------------------------------------------------------------------- #
def test_destete_calcula_peso_ajustado_e_indice(db):
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-2000))
    db.registrar_animal("X1", sexo="Hembra", estado="ACTIVO",
                        fecha_nacimiento=_d(-210), madre_tag="V1")
    db.registrar_parto("V1", fecha=_d(-210), id_cria_tag="X1", peso_nacimiento=35)
    db.registrar_destete("X1", fecha=_d(-5), peso_kg=190)

    out = datos_carne(db)
    dest = {d["tag"]: d for d in out["destetes"]}
    assert "X1" in dest
    assert dest["X1"]["edad_destete_dias"] == 205
    assert dest["X1"]["peso_ajustado_205"] is not None
    assert abs(dest["X1"]["peso_ajustado_205"] - 190.0) < 0.1
    assert dest["X1"]["gmd_predestete_g_dia"] is not None

    indice = {i["madre"]: i for i in out["indice_productivo"]}
    assert "V1" in indice
    assert indice["V1"]["n_crias"] == 1
    # Con una sola madre, su índice es el 100% del promedio del hato.
    assert indice["V1"]["indice_pct"] == 100.0


# --------------------------------------------------------------------------- #
# 4) Proyección de destetes
# --------------------------------------------------------------------------- #
def test_proyeccion_destetes_usa_fep_mas_205(db):
    db.registrar_animal("P1", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio("P1", fecha=_d(-100), tipo_servicio="IA", fep_calculada=_d(183))

    out = datos_carne(db)
    proy = {p["tag"]: p for p in out["proyeccion_destetes"]}
    assert "P1" in proy
    assert proy["P1"]["base"] == "Servicio"
    assert proy["P1"]["destete_estimado"] == _d(388)
    assert out["proyeccion_destetes_mes"][0]["n"] >= 1


def test_proyeccion_destetes_excluye_fep_vencida(db):
    db.registrar_animal("P2", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio("P2", fecha=_d(-400), tipo_servicio="IA", fep_calculada=_d(-117))

    out = datos_carne(db)
    assert "P2" not in _tags(out["proyeccion_destetes"])


# --------------------------------------------------------------------------- #
# 5) Prueba de comportamiento
# --------------------------------------------------------------------------- #
def test_prueba_comportamiento_ranking_gmd(db):
    db.registrar_animal("M2", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-500))
    db.registrar_animal("M3", sexo="Macho", estado="ACTIVO", fecha_nacimiento=_d(-500))
    db.registrar_pesaje("M2", fecha=_d(-60), peso_kg=200)
    db.registrar_pesaje("M2", fecha=_d(-1), peso_kg=260)
    db.registrar_pesaje("M3", fecha=_d(-30), peso_kg=300)  # un solo pesaje

    out = datos_carne(db)
    pc = out["prueba_comportamiento"]
    por_tag = {a["tag"]: a for a in pc["animales"]}
    assert "M2" in por_tag
    assert "M3" not in por_tag
    assert por_tag["M2"]["gmd_g_dia"] > 0
    assert por_tag["M2"]["dias_prueba"] == 59
    assert pc["n"] == 1


# --------------------------------------------------------------------------- #
# Gaps de Reproducción
# --------------------------------------------------------------------------- #
def test_debieron_parir_y_sin_programar(db):
    db.registrar_animal("D1", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio("D1", fecha=_d(-300), tipo_servicio="IA", fep_calculada=_d(-17))
    db.registrar_animal("D2", sexo="Hembra", estado="VENDIDO")
    db.registrar_servicio("D2", fecha=_d(-300), tipo_servicio="IA", fep_calculada=_d(-17))

    db.registrar_animal("S1", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("S1", fecha=_d(-200), sexo_cria="Macho")

    out = datos_reproduccion(db)
    assert "D1" in _tags(out["debieron_parir"])
    assert "D2" not in _tags(out["debieron_parir"])
    assert out["debieron_parir"][0]["dias_atraso"] == 17
    assert "S1" in _tags(out["sin_programar"])
    assert out["sin_programar"][0]["dias_abiertos"] == 200


def test_proyeccion_celos_y_gemelos(db):
    db.registrar_animal("E1", sexo="Hembra", estado="ACTIVO")
    db.registrar_celo("E1", fecha=_d(-20), am_pm="AM")

    out = datos_reproduccion(db)
    proy = {p["tag"]: p for p in out["proyeccion_celos"]}
    assert "E1" in proy
    assert proy["E1"]["proximo_celo"] == _d(1)


def test_servicios_realizados_ventana_y_resultado(db):
    db.registrar_animal("R1", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio("R1", fecha=_d(-10), tipo_servicio="IA", toro_pajilla="T99")
    db.execute(
        "INSERT INTO diagnosticos_gestacion (vaca_id, fecha, resultado) "
        "VALUES ((SELECT id_animal FROM animales WHERE tag='R1'), ?, 'PRENADA')",
        (_d(-2),),
    )
    db.registrar_servicio("R1", fecha=_d(-100), tipo_servicio="IA", toro_pajilla="T98")

    out = datos_reproduccion(db)  # ventana default: últimos 30 días
    rows = {s["fecha"]: s for s in out["servicios_realizados"]}
    assert _d(-10) in rows
    assert rows[_d(-10)]["resultado_diag"] == "PRENADA"
    assert _d(-100) not in rows
    assert out["servicios_rango"]["hasta"] == date.today().isoformat()


def test_novillas_entoradas_y_reproductores(db):
    db.registrar_animal("N1", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-900))
    db.registrar_parto("N1", fecha=_d(-100), sexo_cria="Hembra")
    db.registrar_animal("N2", sexo="Hembra", estado="ACTIVO", fecha_nacimiento=_d(-2000))
    db.registrar_parto("N2", fecha=_d(-100), sexo_cria="Hembra")
    db.registrar_parto("N2", fecha=_d(-800), sexo_cria="Hembra")  # primer parto viejo

    db.registrar_animal("T01", sexo="Macho", estado="ACTIVO", notas="[REPRODUCTOR]")
    db.registrar_animal("T02", sexo="Macho", estado="ACTIVO", notas="[REPRODUCTOR]")
    db.registrar_servicio("N1", fecha=_d(-10), tipo_servicio="MONTA", toro_pajilla="T01")

    out = datos_reproduccion(db)
    entoradas = {e["tag"]: e for e in out["novillas_entoradas"]}
    assert "N1" in entoradas
    assert "N2" not in entoradas  # su primer parto fue hace >12 meses
    assert entoradas["N1"]["edad_primer_parto_meses"] is not None

    toros = {t["tag"]: t for t in out["reproductores_estado"]}
    assert toros["T01"]["estado"] == "EN_SERVICIO"
    assert toros["T02"]["estado"] == "EN_DESCANSO"
