"""Pruebas del motor de consultas en lenguaje natural."""
from datetime import date

import pytest

from src.engine.query_engine import QueryEngine

HOY = date(2026, 9, 1)


@pytest.fixture
def qe(db):
    db.registrar_parto(vaca_tag="47", fecha="2026-05-01")
    db.registrar_servicio(vaca_tag="47", fecha="2026-08-15",
                          fep_calculada="2027-05-25")
    db.registrar_tratamiento(animal_tag="20", fecha="2026-08-20",
                             dias_retiro_carne=14,
                             fecha_fin_retiro_carne="2026-09-03")
    db.registrar_pesaje(animal_tag="12", fecha="2026-01-01", peso_kg=350.0)
    db.registrar_pesaje(animal_tag="12", fecha="2026-03-11", peso_kg=420.0)
    db.registrar_potrero(nombre="Norte", dias_reposo=30, aforo_kg_m2=0.5)
    db.registrar_potrero(nombre="Bajo", dias_reposo=5)
    return QueryEngine(db, hoy=HOY)


def test_ultimo_parto(qe):
    assert "2026-05-01" in qe.responder("¿cuándo parió la 47?")


def test_palpacion_pendiente(qe):
    resp = qe.responder("¿qué vacas tienen palpación pendiente?")
    assert "47" in resp
    assert "2026-10-14" in resp


def test_secado(qe):
    resp = qe.responder("¿cuándo le toca el secado a la 47?")
    assert "2027-03-26" in resp


def test_en_retiro(qe):
    resp = qe.responder("¿qué animales están en tiempo de retiro?")
    assert "20" in resp


def test_historial(qe):
    resp = qe.responder("¿cuál es el historial de la vaca 47?")
    assert "FICHA ZOOTÉCNICA" in resp
    assert "partos: 1" in resp
    assert "servicios: 1" in resp
    assert "Días Abiertos" in resp


def test_pesaje_y_ganancia(qe):
    resp = qe.responder("¿cuánto pesó la 12 y cuál fue su ganancia diaria?")
    assert "420" in resp
    assert "ganancia" in resp


def test_potreros_listos(qe):
    resp = qe.responder("¿qué potreros están listos para pastoreo?")
    assert "Norte" in resp
    assert "Bajo" not in resp


def test_inseminacion_programada(db):
    db.registrar_celo(vaca_tag="47", fecha="2026-08-15", am_pm="PM")
    db.registrar_alerta("47", "INSEMINACION_PROGRAMADA", "2026-08-16",
                        descripcion="Inseminación programada (regla AM-PM) en la mañana")
    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("¿qué vacas debo inseminar?")
    assert "47" in resp
    assert "2026-08-16" in resp
    assert "mañana" in resp


def test_inseminacion_sin_pendientes(db):
    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("¿a qué vacas les toca servicio?")
    assert "No hay vacas pendientes de inseminación" in resp


def test_sin_datos(db):
    qe = QueryEngine(db, hoy=HOY)
    assert "No hay registro de parto" in qe.responder("¿cuándo parió la 47?")


def test_consulta_fotos(db):
    db.registrar_animal("47")
    db.registrar_foto("media/f1.jpg", animal_tag="47", caption="Arete visible")
    qe = QueryEngine(db, hoy=HOY)

    resp_vaca = qe.responder("¿hay fotos de la 47?")
    assert "1 foto(s) de la 47" in resp_vaca

    resp_gen = qe.responder("muéstrame las fotos registradas")
    assert "Hay 1 fotos recientes" in resp_gen

    resp_nadie = qe.responder("fotos de la 999")
    assert "No hay fotos registradas para la 999" in resp_nadie


def test_consulta_animal_alfanumerico(db):
    db.registrar_animal("N069", nombre="Paloma", sexo="Hembra", raza="Brahman")
    db.registrar_parto("N069", fecha="2026-05-10", sexo_cria="Macho", peso_nacimiento=34.0)
    qe = QueryEngine(db, hoy=HOY)

    resp1 = qe.responder("consulta N069")
    assert "FICHA ZOOTÉCNICA" in resp1
    assert "N069" in resp1
    assert "Paloma" in resp1
    assert "Días Abiertos" in resp1

    resp2 = qe.responder("/consulta N06910:13 PM")
    assert "FICHA ZOOTÉCNICA" in resp2
    assert "N069" in resp2

    resp3 = qe.responder("N069")
    assert "FICHA ZOOTÉCNICA" in resp3
    assert "N069" in resp3


def test_animales_en_potrero(db):
    db.registrar_potrero(nombre="Olegario 1", codigo="01")
    db.registrar_potrero(nombre="Bajo", codigo="02")
    db.registrar_animal("JA400", potrero="01", estado="ACTIVO")
    db.registrar_animal("N067", potrero="01", estado="ACTIVO")
    db.registrar_animal("47", potrero="01", estado="ACTIVO")
    db.registrar_animal("99", potrero="02", estado="ACTIVO")

    qe = QueryEngine(db, hoy=HOY)

    # Consulta en lenguaje natural
    resp1 = qe.responder("que vacas hay en el potrero olegario 1")
    assert "Olegario 1" in resp1
    assert "3 animales" in resp1
    assert "JA400" in resp1
    assert "N067" in resp1
    assert "47" in resp1
    assert "99" not in resp1

    # Otra variante zootécnica
    resp2 = qe.responder("¿qué vaca está en el potrero olegario 1?")
    assert "3 animales" in resp2
    assert "JA400" in resp2

    # Directo comando o texto
    resp3 = qe.responder("potrero olegario 1")
    assert "3 animales" in resp3
    assert "JA400" in resp3


def test_animales_en_potrero_con_traslado(db):
    db.registrar_potrero(nombre="Olegario 1", codigo="01")
    db.registrar_potrero(nombre="Santa Martha", codigo="02")
    db.registrar_animal("JA400", potrero="01", estado="ACTIVO")
    db.registrar_animal("N067", potrero="01", estado="ACTIVO")

    # Trasladar JA400 de Olegario 1 a Santa Martha
    db.registrar_traslado("JA400", fecha="2026-08-25", potrero_origen="01", potrero_destino="02")

    qe = QueryEngine(db, hoy=HOY)

    resp_orig = qe.responder("que vacas hay en el potrero olegario 1")
    assert "1 animal" in resp_orig
    assert "N067" in resp_orig
    assert "JA400" not in resp_orig

    resp_dest = qe.responder("que vacas estan en potrero santa martha")
    assert "1 animal" in resp_dest
    assert "JA400" in resp_dest


def test_animales_en_potrero_inexistente_o_vacio(db):
    db.registrar_potrero(nombre="Olegario 1", codigo="01")
    db.registrar_potrero(nombre="Bajo", codigo="02")
    qe = QueryEngine(db, hoy=HOY)

    # Inexistente
    resp_inex = qe.responder("que vacas hay en el potrero fantasma")
    assert "fantasma" in resp_inex
    assert "no existe" in resp_inex
    assert "Potreros disponibles" in resp_inex
    assert "Olegario 1" in resp_inex

    # Existente pero vacío
    resp_vacio = qe.responder("que vacas hay en el potrero bajo")
    assert "No hay animales en el potrero" in resp_vacio
    assert "Bajo" in resp_vacio


def test_animales_en_potrero_mas_de_diez(db):
    db.registrar_potrero(nombre="Olegario 1", codigo="01")
    for i in range(1, 16):
        db.registrar_animal(f"TAG{i:02d}", potrero="01", estado="ACTIVO")

    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("cuantas vacas hay en el potrero olegario 1")
    assert "15 animales" in resp
    assert "TAG01" in resp
    assert "TAG10" in resp
    assert "y 5 más" in resp


def test_extraer_nombre_potrero_helper():
    from src.engine.query_engine import extraer_nombre_potrero

    assert extraer_nombre_potrero("que vaca está en el potrero olegario 1") == "olegario 1"
    assert extraer_nombre_potrero("¿qué vacas hay en el potrero santa martha?") == "santa martha"
    assert extraer_nombre_potrero("animales en potrero norte") == "norte"
    assert extraer_nombre_potrero("potrero olegario-1") == "olegario-1"
    assert extraer_nombre_potrero("¿cuándo parió la 47?") is None


def test_fallback_ayuda_y_sugerencias(qe):
    resp = qe.responder("asdf qwerty zxcv lorem ipsum dolor sit")
    assert "No entendí" in resp
    assert "asdf qwerty" in resp

    sugerencias = qe.sugerencias_fallback("algo")
    assert len(sugerencias) == 3
    assert sugerencias[0][1] == "cmd:inventario"
    assert sugerencias[1][1] == "cmd:historial"
    assert sugerencias[2][1] == "cmd:ayuda"


def test_inventario_potreros_agrupado_y_ordenado(db):
    # Registrar potreros duplicados / variantes de caso
    db.registrar_potrero(nombre="LECHERAS", codigo="01")
    db.registrar_potrero(nombre="lecheras", codigo="02")
    db.registrar_potrero(nombre="OLEGARIO II", codigo="03")
    db.registrar_potrero(nombre="Olegario II", codigo="04")
    db.registrar_potrero(nombre="PLAN VERSALLES", codigo="05")
    db.registrar_potrero(nombre="POTRERO VACIO 1", codigo="06")
    db.registrar_potrero(nombre="POTRERO VACIO 2", codigo="07")

    # Asignar animales:
    # LECHERAS (01): 3 animales, lecheras (02): 2 animales -> Total LECHERAS = 5
    for i in range(1, 4):
        db.registrar_animal(f"LEC_A_{i}", potrero="01", estado="ACTIVO")
    for i in range(1, 3):
        db.registrar_animal(f"LEC_B_{i}", potrero="02", estado="ACTIVO")

    # OLEGARIO II (03): 1 animal, Olegario II (04): 1 animal -> Total OLEGARIO II = 2
    db.registrar_animal("OLEG_1", potrero="03", estado="ACTIVO")
    db.registrar_animal("OLEG_2", potrero="04", estado="ACTIVO")

    # PLAN VERSALLES (05): 10 animales -> Total PLAN VERSALLES = 10
    for i in range(1, 11):
        db.registrar_animal(f"VERS_{i}", potrero="05", estado="ACTIVO")

    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("inventario potreros")

    # Verifica encabezado y bloque pre
    assert "Inventario por potrero — Ocupados (3)" in resp
    assert "<pre>" in resp
    assert "</pre>" in resp

    # Verifica orden descendente: PLAN VERSALLES (10) -> LECHERAS (5) -> OLEGARIO II (2)
    idx_versalles = resp.find("PLAN VERSALLES")
    idx_lecheras = resp.find("LECHERAS")
    idx_olegario = resp.find("OLEGARIO II")
    assert idx_versalles != -1
    assert idx_lecheras != -1
    assert idx_olegario != -1
    assert idx_versalles < idx_lecheras < idx_olegario

    # Verifica conteo de vacíos
    assert "Vacíos: 2" in resp
    assert "/potreros vacios" in resp


def test_inventario_potreros_vacios_y_sin_potreros(db):
    qe = QueryEngine(db, hoy=HOY)
    # Sin potreros registrados
    assert "No hay potreros registrados" in qe.responder("inventario potreros")

    # Registrar potreros sin animales
    db.registrar_potrero(nombre="Norte", codigo="01")
    db.registrar_potrero(nombre="Sur", codigo="02")

    # Consulta inventario normal cuando todos están vacíos
    resp_todos_vacios = qe.responder("inventario potreros")
    assert "Todos los potreros (2) están vacíos" in resp_todos_vacios

    # Consulta explícita de vacíos
    resp_vacios = qe.responder("potreros vacios")
    assert "Inventario por potrero — Vacíos (2)" in resp_vacios
    assert "NORTE" in resp_vacios
    assert "SUR" in resp_vacios


def test_ficha_zootecnica_formato_movil(db):
    db.registrar_animal("JA26", nombre="Patricia", sexo="Hembra", raza="Gyr")
    db.registrar_parto("JA26", fecha="2026-04-10", sexo_cria="Hembra", peso_nacimiento=32.0)
    db.registrar_servicio("JA26", fecha="2026-07-01", tipo_servicio="IA", toro_pajilla="T-99")
    db.registrar_celo("JA26", fecha="2026-06-30", am_pm="AM")
    db.registrar_pesaje("JA26", fecha="2026-01-01", peso_kg=400.0)
    db.registrar_pesaje("JA26", fecha="2026-06-01", peso_kg=460.0)
    db.registrar_tratamiento("JA26", fecha="2026-08-25", producto="Oxitetraciclina", dosis="20ml", dias_retiro_carne=28, fecha_fin_retiro_carne="2026-09-22")
    db.registrar_foto("media/ja26.jpg", animal_tag="JA26", caption="Foto lateral")

    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("ficha JA26")

    # Header
    assert "FICHA ZOOTÉCNICA" in resp
    assert "JA26" in resp
    assert "Patricia" in resp
    assert "Gyr" in resp
    assert "───────────────────" in resp

    # Secciones
    assert "REPRODUCCIÓN & PARTOS" in resp
    assert "partos: 1" in resp
    assert "Días Abiertos" in resp
    assert "servicios: 1" in resp
    assert "FEP (Fecha Estimada Parto)" in resp
    assert "celos: 1" in resp

    assert "PESAJE & CRECIMIENTO" in resp
    assert "pesajes: 2" in resp
    assert "460" in resp
    assert "GMD:" in resp

    assert "SANIDAD & RETIROS" in resp
    assert "Oxitetraciclina" in resp
    assert "Retiro carne hasta 2026-09-22" in resp

    assert "FOTOS" in resp
    assert "1 foto(s) registrada(s)" in resp




