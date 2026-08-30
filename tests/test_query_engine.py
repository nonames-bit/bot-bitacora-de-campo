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


def test_historial_animal_historico_explica_por_que(db):
    # Reportado directamente: la ficha mostraba "Estado: HISTORICO" sin
    # ninguna explicación, y el usuario no entendía qué significaba ni por
    # qué ese animal ya no aparecía en su inventario activo.
    db.registrar_animal("JA146", nombre="TANGUITA", sexo="Hembra", estado="HISTORICO")
    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("ja146")
    assert "HISTORICO" in resp
    assert "no hace parte del hato activo" in resp


def test_historial_animal_activo_no_muestra_nota_historico(db):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    qe = QueryEngine(db, hoy=HOY)
    resp = qe.responder("47")
    assert "no hace parte del hato activo" not in resp


def test_historial_cria_numerada_como_madre_guion_n_no_abre_ficha_madre(db):
    # Regresión real: convención de la finca de numerar crías como
    # "arete_madre-n" (ej. JA26-6). Antes del fix, "consulta ja26-6" abría
    # la ficha de la MADRE (JA26) porque extraer_tag truncaba el tag.
    db.registrar_animal("JA26", nombre="PATRICIA", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="JA26", id_cria_tag="JA26-6", fecha="2026-08-27", sexo_cria="Macho")
    qe = QueryEngine(db, hoy=HOY)

    resp = qe.responder("ja26-6")
    assert "PATRICIA" not in resp
    assert "JA26-6" in resp or "ja26-6" in resp.lower()


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


def test_ficha_vaca_parida_y_cria_ternero(db):
    # Caso reportado por Jaime: JA400 (Madre) y V008 (Cría macho nacida el 2026-01-08)
    db.registrar_potrero(nombre="ORDENO SANTA MARTHA", codigo="01")
    db.registrar_potrero(nombre="CORRAL SANTAMARTHA", codigo="02")

    db.registrar_animal(
        "JA400",
        nombre="PACHITA HIJA JANGO 3/4 GIRO",
        sexo="Hembra",
        raza="Gyr",
        potrero="01",
        estado="ACTIVO",
    )
    # Partos anteriores
    db.registrar_parto("JA400", fecha="2024-01-10", sexo_cria="Hembra")
    db.registrar_parto("JA400", fecha="2025-01-05", sexo_cria="Hembra")
    # Último parto con cría macho V008 el 2026-01-08
    db.registrar_parto(
        "JA400",
        fecha="2026-01-08",
        sexo_cria="Macho",
        peso_nacimiento=34.0,
        id_cria_tag="V008",
    )
    db.registrar_animal("V008", sexo="Macho", potrero="02", estado="ACTIVO")

    # Fecha de consulta: 2026-08-28 (232 días desde el parto)
    qe = QueryEngine(db, hoy=date(2026, 8, 28))

    # Ficha de la vaca madre JA400
    resp_ja400 = qe.responder("ficha JA400")
    assert "FICHA ZOOTÉCNICA" in resp_ja400
    assert "Vaca JA400" in resp_ja400
    assert "PACHITA HIJA JANGO 3/4 GIRO" in resp_ja400
    assert "PARIDA SIN PALPAR" in resp_ja400
    assert "partos: 3 registro(s)" in resp_ja400
    assert "Último Parto: 2026-01-08 (Cría macho, 34.0 kg, Arete V008)" in resp_ja400
    assert "Días Abiertos: 232 días" in resp_ja400

    # Ficha de la cría macho V008
    resp_v008 = qe.responder("ficha V008")
    assert "FICHA ZOOTÉCNICA" in resp_v008
    assert "Ternero V008" in resp_v008
    assert "Toro V008" not in resp_v008
    assert "MACHO REPRODUCTOR" not in resp_v008
    assert "CRÍA MACHO" in resp_v008
    assert "Edad:" in resp_v008
    assert "partos: 0 registro(s)" in resp_v008
    assert "Días Abiertos" not in resp_v008
    assert "Último Parto" not in resp_v008
    assert "Madre: JA400" in resp_v008


def test_ficha_macho_clasificacion_etaria(db):
    # Ternero (<8 meses), Novillo (8-18 meses), Torete (18-30 meses), Toro (>=30 meses)
    db.registrar_animal("T01", sexo="Macho", fecha_nacimiento="2026-03-01")  # ~6 meses -> Ternero / CRÍA MACHO
    db.registrar_animal("N01", sexo="Macho", fecha_nacimiento="2025-01-01")  # ~20 meses -> Torete / TORETE
    db.registrar_animal("TORO1", sexo="Macho", fecha_nacimiento="2023-01-01")  # ~3.6 años -> Toro / TORO

    qe = QueryEngine(db, hoy=date(2026, 9, 1))

    resp_t01 = qe.responder("ficha T01")
    assert "Ternero T01" in resp_t01
    assert "CRÍA MACHO" in resp_t01
    assert "partos: 0" in resp_t01
    assert "Días Abiertos" not in resp_t01

    resp_n01 = qe.responder("ficha N01")
    assert "Torete N01" in resp_n01
    assert "TORETE" in resp_n01
    assert "partos: 0" in resp_n01

    resp_toro = qe.responder("ficha TORO1")
    assert "Toro TORO1" in resp_toro
    assert "TORO" in resp_toro
    assert "partos: 0" in resp_toro


def test_ficha_ternero_v009_madre_ja400(db):
    # Caso reportado por Jaime: JA400 (Madre) y V009 (Cría macho nacida el 2026-03-02)
    db.registrar_potrero(nombre="ORDENO SANTA MARTHA", codigo="01")
    db.registrar_potrero(nombre="CORRAL SANTAMARTHA", codigo="02")

    db.registrar_animal(
        "JA400",
        nombre="PACHITA HIJA JANGO 3/4 GIRO",
        sexo="Hembra",
        raza="Gyr",
        potrero="01",
        estado="ACTIVO",
    )
    # Parto de la madre JA400 con cría macho V009 el 2026-03-02
    db.registrar_parto(
        "JA400",
        fecha="2026-03-02",
        sexo_cria="Macho",
        peso_nacimiento=33.0,
        id_cria_tag="V009",
    )
    db.registrar_animal("V009", sexo="Macho", potrero="02", estado="ACTIVO")

    # Fecha de consulta: 2026-08-28 (179 días desde el parto)
    qe = QueryEngine(db, hoy=date(2026, 8, 28))

    resp_v009 = qe.responder("ficha V009")
    assert "FICHA ZOOTÉCNICA" in resp_v009
    assert "Ternero V009" in resp_v009
    assert "Toro V009" not in resp_v009
    assert "TORETE" not in resp_v009
    assert "CRÍA MACHO" in resp_v009
    assert "5 meses 26 días (179 días)" in resp_v009
    assert "partos: 0 registro(s)" in resp_v009
    assert "servicios: 0 registro(s)" in resp_v009
    assert "Días Abiertos" not in resp_v009
    assert "Último Parto" not in resp_v009
    assert "Madre: JA400" in resp_v009
    assert "Fecha: 2026-03-02" in resp_v009


def test_ficha_v009_con_parto_autorreferenciado_corrupto(db):
    # Simula caso corrupto donde V009 existía como registro de parto autorreferenciado
    v009_id = db.registrar_animal("V009", sexo="Macho", fecha_nacimiento="2026-03-02", estado="ACTIVO")
    ja400_id = db.registrar_animal("JA400", sexo="Hembra", estado="ACTIVO")
    db.execute("UPDATE animales SET madre_id = ? WHERE id_animal = ?", (ja400_id, v009_id))

    # Insertar manualmente un parto corrupto autorreferenciado (vaca_id = V009, id_cria = V009)
    db.execute(
        "INSERT INTO partos (vaca_id, id_cria, fecha, sexo_cria, peso_nacimiento) VALUES (?, ?, '2026-03-02', 'Macho', 33.0)",
        (v009_id, v009_id),
    )

    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp = qe.responder("ficha V009")

    assert "Ternero V009" in resp
    assert "Toro V009" not in resp
    assert "TORETE" not in resp
    assert "CRÍA MACHO" in resp
    assert "partos: 0 registro(s)" in resp
    assert "Días Abiertos" not in resp
    assert "Último Parto" not in resp
    assert "Madre: JA400" in resp


def test_ficha_v009_sin_fecha_nacimiento_infiere_parto_madre(db):
    # V009 sin fecha_nacimiento en tabla animales, pero con madre JA400 con parto el 2026-03-02
    ja400_id = db.registrar_animal("JA400", sexo="Hembra", estado="ACTIVO")
    v009_id = db.registrar_animal("V009", sexo="Macho", madre_tag="JA400", estado="ACTIVO")
    db.execute(
        "INSERT INTO partos (vaca_id, id_cria, fecha, sexo_cria, peso_nacimiento) VALUES (?, ?, '2026-03-02', 'Macho', 33.0)",
        (ja400_id, v009_id),
    )

    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp = qe.responder("ficha V009")

    assert "Ternero V009" in resp
    assert "CRÍA MACHO" in resp
    assert "Madre: JA400" in resp
    assert "Fecha: 2026-03-02" in resp


def test_ficha_macho_edad_desconocida_sin_madre(db):
    # Macho sin fecha de nacimiento ni madre registrada -> no debe clasificarse como Toro reproductor
    db.registrar_animal("M_DESCONOCIDO", sexo="Macho", estado="ACTIVO")
    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp = qe.responder("ficha M_DESCONOCIDO")

    assert "Macho joven M_DESCONOCIDO" in resp
    assert "Toro M_DESCONOCIDO" not in resp
    assert "MACHO REPRODUCTOR" not in resp
    assert "LEVANTE / EDAD POR CONFIRMAR" in resp
    assert "partos: 0 registro(s)" in resp


def test_ficha_macho_sexo_indefinido_infiere_macho_desde_parto(db):
    # Animal con sexo 'I' en la tabla pero con registro de parto que indica sexo_cria 'Macho'
    ja400_id = db.registrar_animal("JA400", sexo="Hembra", estado="ACTIVO")
    cria_id = db.registrar_animal("CRIA_01", sexo="I", madre_tag="JA400", estado="ACTIVO")
    db.execute(
        "INSERT INTO partos (vaca_id, id_cria, fecha, sexo_cria, peso_nacimiento) VALUES (?, ?, '2026-03-02', 'Macho', 33.0)",
        (ja400_id, cria_id),
    )

    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp = qe.responder("ficha CRIA_01")

    assert "Ternero CRIA_01" in resp
    assert "Vaca CRIA_01" not in resp
    assert "partos: 0 registro(s)" in resp
    assert "Días Abiertos" not in resp


def test_ficha_edad_legible_7_anos_3_meses(db):
    # Vaca con 7 años y 3 meses (nacida el 2019-05-10, consulta el 2026-08-28 -> 2.667 días)
    db.registrar_animal(
        "V_ADULTA",
        nombre="PALOMA",
        sexo="Hembra",
        fecha_nacimiento="2019-05-10",
        estado="ACTIVO",
    )
    db.registrar_parto("V_ADULTA", fecha="2026-02-15", sexo_cria="Hembra")

    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp = qe.responder("ficha V_ADULTA")

    assert "FICHA ZOOTÉCNICA" in resp
    assert "🎂 <b>Edad:</b> 7 años 3 meses (2.667 días)" in resp
    assert "VACA PARIDA" in resp


def test_ficha_edad_cria_8_meses(db):
    # Cría macho de 8 meses exactos (nacido el 2025-12-28, hoy 2026-08-28 -> 243 días)
    db.registrar_animal(
        "CRIA_8M",
        sexo="Macho",
        fecha_nacimiento="2025-12-28",
        estado="ACTIVO",
    )
    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp = qe.responder("ficha CRIA_8M")

    assert "FICHA ZOOTÉCNICA" in resp
    assert "🎂 <b>Edad:</b> 8 meses (243 días)" in resp
    assert "Novillo CRIA_8M" in resp or "Ternero CRIA_8M" in resp
    assert "Toro CRIA_8M" not in resp
    assert "TORETE" not in resp


def test_ficha_edad_menos_30_dias(db):
    # Ternero recién nacido de 12 días
    db.registrar_animal(
        "CRIA_12D",
        sexo="Macho",
        fecha_nacimiento="2026-08-16",
        estado="ACTIVO",
    )
    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp = qe.responder("ficha CRIA_12D")

    assert "FICHA ZOOTÉCNICA" in resp
    assert "🎂 <b>Edad:</b> 12 días" in resp
    assert "Ternero CRIA_12D" in resp
    assert "CRÍA MACHO" in resp


def test_ficha_estados_zootecnicos_sg(db):
    # Hembras en diferentes etapas productivas según Software Ganadero
    # 1. Novilla levante (14 meses)
    db.registrar_animal("NOV_LEV", sexo="Hembra", fecha_nacimiento="2025-06-28", estado="ACTIVO")
    # 2. Novilla vientre (>18m, 22 meses)
    db.registrar_animal("NOV_VIE", sexo="Hembra", fecha_nacimiento="2024-10-28", estado="ACTIVO")
    # 3. Vaca parida (parto hace 120 días)
    db.registrar_animal("VAC_PARIDA", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("VAC_PARIDA", fecha="2026-04-30", sexo_cria="Hembra")
    # 4. Vaca escotera (>1 parto, >305 días sin servicio: parto hace 400 días)
    db.registrar_animal("VAC_ESCOTERA", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("VAC_ESCOTERA", fecha="2024-01-01", sexo_cria="Hembra")
    db.registrar_parto("VAC_ESCOTERA", fecha="2025-07-24", sexo_cria="Hembra")

    qe = QueryEngine(db, hoy=date(2026, 8, 28))

    resp_nl = qe.responder("ficha NOV_LEV")
    assert "NOVILLA LEVANTE" in resp_nl

    resp_nv = qe.responder("ficha NOV_VIE")
    assert "NOVILLA VIENTRE" in resp_nv

    resp_vp = qe.responder("ficha VAC_PARIDA")
    assert "VACA PARIDA SIN PALPAR" in resp_vp

    resp_ve = qe.responder("ficha VAC_ESCOTERA")
    assert "VACA ESCOTERA" in resp_ve


def test_resumen_inventario_sg_brackets_completos(db):
    hoy = date(2026, 9, 1)

    # 1. Hembras en cada uno de los 6 brackets SG
    db.registrar_animal("H_MENOR_1", sexo="Hembra", fecha_nacimiento="2026-03-01", estado="ACTIVO")   # 184d -> <1
    db.registrar_animal("H_1_2", sexo="Hembra", fecha_nacimiento="2025-03-01", estado="ACTIVO")       # 549d -> 1-2
    db.registrar_animal("H_2_4", sexo="Hembra", fecha_nacimiento="2023-09-01", estado="ACTIVO")       # 1096d -> 2-4
    db.registrar_animal("H_4_8", sexo="Hembra", fecha_nacimiento="2020-09-01", estado="ACTIVO")       # 2191d -> 4-8
    db.registrar_animal("H_8_10", sexo="Hembra", fecha_nacimiento="2017-09-01", estado="ACTIVO")      # 3287d -> 8-10
    db.registrar_animal("H_MAYOR_10", sexo="Hembra", fecha_nacimiento="2014-09-01", estado="ACTIVO")  # 4383d -> >10

    # 2. Machos en cada bracket SG
    db.registrar_animal("M_MENOR_1", sexo="Macho", fecha_nacimiento="2026-04-01", estado="ACTIVO")    # 153d -> <1
    db.registrar_animal("M_1_2", sexo="Macho", fecha_nacimiento="2025-04-01", estado="ACTIVO")        # 518d -> 1-2
    db.registrar_animal("M_MAYOR_2", sexo="Macho", fecha_nacimiento="2024-06-23", estado="ACTIVO")    # 800d -> >2
    db.registrar_animal("M_REP_EDAD", sexo="Macho", fecha_nacimiento="2022-01-01", estado="ACTIVO")   # 1704d (>913d) -> Reproductor
    db.registrar_animal("M_REP_TORO", sexo="Macho", nombre="TORO BRAHMAN 01", fecha_nacimiento="2025-01-01", estado="ACTIVO")  # flag TORO -> Reproductor

    # 3. Animales históricos (NO deben contarse en inventario activo)
    db.registrar_animal("H_MUERTO", sexo="Hembra", estado="MUERTO", fecha_nacimiento="2020-01-01")
    db.registrar_animal("M_VENDIDO", sexo="Macho", estado="VENDIDO", fecha_nacimiento="2022-01-01")

    qe = QueryEngine(db, hoy=hoy)

    # Consulta por lenguaje natural
    resp = qe.responder("resumen inventario")

    assert "<pre>" in resp
    assert "</pre>" in resp

    import html
    resp_txt = html.unescape(resp)

    # Verificaciones de brackets hembras
    assert "Hembras <1 año" in resp_txt and "9.09%" in resp_txt
    assert "Hembras 1-2 años" in resp_txt
    assert "Hembras 2-4 años" in resp_txt
    assert "Hembras 4-8 años" in resp_txt
    assert "Hembras 8-10 años" in resp_txt
    assert "Hembras >10 años" in resp_txt

    # Verificaciones de brackets machos
    assert "Machos <1 año" in resp_txt
    assert "Machos 1-2 años" in resp_txt
    assert "Machos >2 años" in resp_txt
    assert "Reproductor" in resp_txt and "18.18%" in resp_txt

    # Pie de tabla SG y resumen
    assert "Hembras 6 | Machos 5 | Total 11" in resp_txt
    assert "Total en finca: 11 animales" in resp_txt
    assert "H_MUERTO" not in resp_txt
    assert "M_VENDIDO" not in resp_txt


def test_inventario_potreros_ocupados_porcentajes_y_filtro_historico(db):
    hoy = date(2026, 9, 1)

    db.registrar_potrero(nombre="POTRERO ALTO", codigo="01")
    db.registrar_potrero(nombre="POTRERO BAJO", codigo="02")
    db.registrar_potrero(nombre="POTRERO VACIO", codigo="03")
    # Potrero histórico con reposo excesivo (no debe aparecer)
    db.registrar_potrero(nombre="JARA", codigo="99", dias_reposo=3232)

    # 15 animales activos en POTRERO ALTO (75.00%)
    for i in range(1, 16):
        db.registrar_animal(f"ALTO_{i:02d}", potrero="01", estado="ACTIVO")

    # 5 animales activos en POTRERO BAJO (25.00%)
    for i in range(1, 6):
        db.registrar_animal(f"BAJO_{i:02d}", potrero="02", estado="ACTIVO")

    # Animales históricos asignados a potrero (NO deben contarse)
    db.registrar_animal("HIST_1", potrero="01", estado="MUERTO")
    db.registrar_animal("HIST_2", potrero="02", estado="VENDIDO")

    qe = QueryEngine(db, hoy=hoy)
    resp = qe.responder("inventario potreros")

    assert "Inventario por potrero — Ocupados (2)" in resp
    assert "<pre>" in resp
    assert "</pre>" in resp

    # Tabla con porcentajes SG-like
    assert "POTRERO ALTO" in resp and "15" in resp and "75.00%" in resp
    assert "POTRERO BAJO" in resp and "5" in resp and "25.00%" in resp
    assert "Total en potreros" in resp and "20" in resp and "100.00%" in resp

    # JARA no debe salir en ocupados
    assert "JARA" not in resp
    assert "Vacíos: 1" in resp


def test_consultas_especificas_nombre_y_tag(db, tmp_path):
    hoy = date(2026, 9, 1)
    db.registrar_potrero(nombre="OLEGARIO I", codigo="01")
    db.registrar_animal(tag="JA26", nombre="PATRICIA", sexo="Hembra", estado="ACTIVO", potrero="01")
    db.registrar_animal(tag="TORO_502", nombre="BRAHMAN 502", sexo="Macho", estado="ACTIVO")
    db.registrar_parto(vaca_tag="JA26", fecha="2025-11-12", sexo_cria="Hembra", estado_cria="VIVO", peso_nacimiento=36.0)
    db.registrar_servicio(vaca_tag="JA26", fecha="2026-06-15", toro_pajilla="TORO_502", tipo_servicio="IA")
    db.registrar_tratamiento(animal_tag="JA26", fecha="2026-08-30", producto="Oxitetraciclina", dias_retiro_carne=14, fecha_fin_retiro_carne="2026-09-13")

    qe = QueryEngine(db, hoy=hoy)

    # 1. Ubicación de animal por nombre y por tag
    resp_ubi1 = qe.responder("¿en qué potrero está patricia?")
    assert "OLEGARIO I" in resp_ubi1
    assert "JA26" in resp_ubi1
    assert "PATRICIA" in resp_ubi1

    resp_ubi2 = qe.responder("dónde está la vaca JA26?")
    assert "OLEGARIO I" in resp_ubi2

    # 2. Parto de animal por nombre propio
    resp_parto = qe.responder("¿cuándo parió patricia?")
    assert "2025-11-12" in resp_parto
    assert "36.0 kg" in resp_parto

    # 3. Servicio de animal
    resp_serv = qe.responder("¿cuándo se inseminó patricia?")
    assert "2026-06-15" in resp_serv
    assert "TORO_502" in resp_serv

    # 4. Retiro de animal individual
    resp_ret = qe.responder("¿patricia está en retiro?")
    assert "Oxitetraciclina" in resp_ret
    assert "2026-09-13" in resp_ret

    # 5. Genealogía de animal
    resp_gen = qe.responder("¿quién es la madre de patricia?")
    assert "Genealogía de JA26" in resp_gen

    # 6. Búsqueda de foto de animal
    from src.engine.query_engine import buscar_foto_animal
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    foto_ja26 = media_dir / "ja26.jpg"
    foto_ja26.write_bytes(b"dummy_image")

    encontrada = buscar_foto_animal(db, "patricia", media_dir=str(media_dir))
    assert encontrada is not None
    assert "ja26.jpg" in encontrada

    # 7. Pregunta de cuándo se movió de potrero
    db.registrar_traslado(
        "JA26", fecha="2026-08-20", potrero_origen="P01", potrero_destino="01", lote="2"
    )
    resp_trasl = qe.responder("¿cuándo se movió patricia de potrero?")
    assert "Último traslado de JA26" in resp_trasl
    assert "OLEGARIO I" in resp_trasl
    assert "2026-08-20" in resp_trasl
    assert "Lote 2" in resp_trasl


def test_existencias_por_potrero_sg(db):
    from src.engine.query_engine import (
        calcular_existencias_potreros_sg,
        formatear_tabla_potreros_sg,
        QueryEngine,
    )
    # Registrar potreros
    p1 = db.registrar_potrero("ORDENO SANTA MARTHA", "01")
    p2 = db.registrar_potrero("OLEGARIO I", "02")

    # Registrar animales en potrero 1
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2020-01-01")
    db.registrar_parto("V1", fecha="2026-06-01")  # Vaca parida (<305d)

    db.registrar_animal("N1", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2023-01-01")  # Novilla vientre (>2a sin parto)
    db.registrar_animal("T1", sexo="Macho", estado="ACTIVO", potrero=p1, nombre="TORO PADRON", fecha_nacimiento="2021-01-01")  # Reproductor

    # Registrar animales en potrero 2
    db.registrar_animal("C1", sexo="Hembra", estado="ACTIVO", potrero=p2, fecha_nacimiento="2026-02-01")  # Cría hembra (<1a)
    db.registrar_animal("CM1", sexo="Macho", estado="ACTIVO", potrero=p2, fecha_nacimiento="2026-03-01")  # Cría macho (<1a)

    filas = calcular_existencias_potreros_sg(db, hoy=date(2026, 8, 28))
    assert len(filas) == 2

    p1_fila = next(f for f in filas if "ORDENO" in f["display"])
    assert p1_fila["vp"] == 1
    assert p1_fila["nv"] == 1
    assert p1_fila["rep"] == 1
    assert p1_fila["total"] == 3

    p2_fila = next(f for f in filas if "OLEGARIO" in f["display"])
    assert p2_fila["ch"] == 1
    assert p2_fila["cm"] == 1
    assert p2_fila["total"] == 2

    tabla_str = formatear_tabla_potreros_sg(filas)
    assert "GANADERIA-JA" in tabla_str
    assert "ORDENO SANTA" in tabla_str
    assert "Totales..." in tabla_str
    assert "5" in tabla_str

    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp_query = qe.responder("existencias por potrero")
    assert "GANADERIA-JA" in resp_query
    assert "Totales..." in resp_query


def test_dias_ocupacion_y_rotacion(db):
    from src.engine.query_engine import (
        formatear_ocupacion_potreros,
        QueryEngine,
    )
    p1 = db.registrar_potrero("ORDENO SANTA MARTHA", "01")
    p2 = db.registrar_potrero("BAJO", "02", dias_reposo=35)

    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", potrero=p1)
    db.registrar_traslado("V1", fecha="2026-08-26", potrero_destino=p1)

    ocup_str = formatear_ocupacion_potreros(db, hoy=date(2026, 8, 28))
    assert "Días de Ocupación y Rotación" in ocup_str
    assert "ORDENO SANTA MARTHA" in ocup_str
    assert "2d ocupación" in ocup_str
    assert "BAJO" in ocup_str
    assert "35d reposo" in ocup_str
    assert "Listo para pastoreo" in ocup_str

    qe = QueryEngine(db, hoy=date(2026, 8, 28))
    resp = qe.responder("dias de ocupacion de potreros")
    assert "Días de Ocupación y Rotación" in resp


# --------------------------------------------------------------------- #
# Consultas de lista ampliadas (días abiertos, partos por periodo, crías
# por sexo, próximas a parir, secado/lactancia larga, tratamientos)
# --------------------------------------------------------------------- #

def test_dias_abiertos_mayor(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-01-01")
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="48", fecha="2026-08-20")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("¿qué vacas tienen más de 90 días abiertas?")
    assert "No entendí" not in resp
    assert "47" in resp
    assert "48" not in resp

    resp_sin = qe.responder("vacas con más de 300 días abiertos")
    assert "No hay vacas" in resp_sin


def test_partos_periodo(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-08-25", sexo_cria="Macho")
    db.registrar_animal("12", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="12", fecha="2026-07-20", sexo_cria="Hembra")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("¿qué partos hubo este mes?")
    assert "No entendí" not in resp
    assert "47" in resp
    assert "12" not in resp

    resp2 = qe.responder("partos de los últimos 45 días")
    assert "47" in resp2
    assert "12" in resp2


def test_crias_por_sexo(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-08-01", sexo_cria="Macho")
    db.registrar_animal("12", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="12", fecha="2026-08-05", sexo_cria="Macho")
    db.registrar_animal("15", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="15", fecha="2026-08-10", sexo_cria="Hembra")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("cuántos terneros machos han nacido")
    assert "No entendí" not in resp
    assert "2" in resp


def test_vacas_proximas_parir(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag="47", fecha="2025-12-01", fep_calculada="2026-09-10")
    db.registrar_animal("12", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag="12", fecha="2025-06-01", fep_calculada="2027-06-10")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("¿qué vacas están próximas a parir?")
    assert "No entendí" not in resp
    assert "47" in resp
    assert "12" not in resp


def test_vacas_lactancia_larga(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-01-01")
    db.registrar_animal("12", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="12", fecha="2026-08-20")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("vacas que debo secar este mes")
    assert "No entendí" not in resp
    assert "47" in resp
    assert "12" not in resp

    resp2 = qe.responder("vacas con más de 200 días de lactancia")
    assert "47" in resp2


def test_partos_atrasados(db):
    from src.engine.query_engine import QueryEngine
    # 47: FEP vencida, sin parto desde ese servicio -> debe salir en la lista.
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag="47", fecha="2025-11-01", fep_calculada="2026-08-11")
    # 12: FEP vencida pero ya parió después del servicio -> no debe salir.
    db.registrar_animal("12", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag="12", fecha="2025-11-01", fep_calculada="2026-08-11")
    db.registrar_parto(vaca_tag="12", fecha="2026-08-15")
    # 33: FEP todavía no vencida -> no debe salir.
    db.registrar_animal("33", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag="33", fecha="2026-08-01", fep_calculada="2027-05-11")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("¿qué vacas debían haber parido?")
    assert "No entendí" not in resp
    assert "47" in resp
    assert "12" not in resp
    assert "33" not in resp

    resp2 = qe.responder("vacas atrasadas de parto")
    assert "47" in resp2


def test_animales_perdiendo_peso(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Macho", estado="ACTIVO")
    db.registrar_pesaje(animal_tag="47", fecha="2026-08-01", peso_kg=300)
    db.registrar_pesaje(animal_tag="47", fecha="2026-08-20", peso_kg=280)  # bajó
    db.registrar_animal("12", sexo="Macho", estado="ACTIVO")
    db.registrar_pesaje(animal_tag="12", fecha="2026-08-01", peso_kg=300)
    db.registrar_pesaje(animal_tag="12", fecha="2026-08-20", peso_kg=320)  # subió

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("¿qué animales están perdiendo peso?")
    assert "No entendí" not in resp
    assert "47" in resp
    assert "12" not in resp


def test_condicion_corporal_consulta(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_condicion_corporal("47", fecha="2026-08-01", valor=2.5)
    db.registrar_condicion_corporal("47", fecha="2026-08-20", valor=3.5)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("condición corporal de la 47")
    assert "No entendí" not in resp
    assert "3.5" in resp
    assert "2026-08-20" in resp

    resp_sin_datos = qe.responder("condición corporal de la 99")
    assert "No hay" in resp_sin_datos


def test_leche_consulta(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_leche("47", fecha="2026-08-01", litros=10.0)
    db.registrar_leche("47", fecha="2026-08-08", litros=12.5)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("litros de leche de la 47")
    assert "No entendí" not in resp
    assert "12.5" in resp
    assert "2026-08-08" in resp

    resp_sin_datos = qe.responder("litros de leche de la 99")
    assert "No hay" in resp_sin_datos


def test_cuantos_partos_tiene_nombre(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", nombre="patricia", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-01-01")
    db.registrar_parto(vaca_tag="47", fecha="2024-01-01")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("cuántos partos tiene patricia")
    assert "No entendí" not in resp
    assert "2 partos" in resp


def test_con_que_toro_se_sirvio(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("A029", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag="A029", fecha="2026-08-01", toro_pajilla="TORO 502")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("¿con qué toro se sirvió la A029?")
    assert "No entendí" not in resp
    assert "TORO 502" in resp


def test_tratamientos_animal_y_ultimos(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_tratamiento(animal_tag="47", fecha="2026-08-01", producto="Ivermectina", dosis="10ml", via="SC")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("cuándo le aplicaron ivermectina a la 47")
    assert "No entendí" not in resp
    assert "Ivermectina" in resp
    assert "2026-08-01" in resp

    resp2 = qe.responder("últimos tratamientos aplicados")
    assert "No entendí" not in resp2
    assert "47" in resp2
    assert "Ivermectina" in resp2


def test_se_puede_ordenar_hoy_usa_retiro(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_tratamiento(
        animal_tag="47", fecha="2026-08-28", producto="Oxitetraciclina",
        dias_retiro_leche=5, fecha_fin_retiro_leche="2026-09-05",
    )

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("¿la vaca 47 se puede ordeñar hoy?")
    assert "No entendí" not in resp
    assert "Retiro de leche" in resp


def test_pesaje_palabra_completa(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("A060", sexo="Macho", estado="ACTIVO")
    db.registrar_pesaje("A060", fecha="2026-08-01", peso_kg=180.0)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("último pesaje del novillo A060")
    assert "No entendí" not in resp
    assert "180" in resp


def test_inventario_por_edad_exacta(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2024-08-15")
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2020-01-01")
    db.registrar_animal("49", sexo="Macho", estado="ACTIVO", fecha_nacimiento="2020-06-01")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("cuantos animales hay de 2 anos")
    assert "No entendí" not in resp
    assert "47" in resp
    assert "48" not in resp

    resp_vacas = qe.responder("cuantas vacas de 6 anos hay")
    assert "48" in resp_vacas
    assert "49" not in resp_vacas  # es macho, no vaca

    resp_sin = qe.responder("cuantos animales hay de 10 anos")
    assert "No hay" in resp_sin


def test_conteo_por_estado_vendidos_muertos(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="VENDIDO")
    db.registrar_animal("48", sexo="Macho", estado="VENDIDO")
    db.registrar_animal("49", sexo="Hembra", estado="MUERTO")
    db.registrar_animal("50", sexo="Hembra", estado="ACTIVO")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp_v = qe.responder("cuantos animales vendidos hay")
    assert "No entendí" not in resp_v
    assert "2" in resp_v

    resp_vv = qe.responder("cuantas vacas se han vendido")
    assert "Vacas vendidas" in resp_vv
    assert "1" in resp_vv

    resp_m = qe.responder("cuantos animales muertos hay")
    assert "1" in resp_m


def test_potrero_mencionado_sin_palabra_potrero(db):
    """Regresión: 'donde olegario' / 'en el corral santa martha' caían en el
    resumen general porque extraer_nombre_potrero exige la palabra 'potrero'
    y el matcher exacto exigía el nombre completo con sufijo (I/1)."""
    from src.engine.query_engine import QueryEngine
    p1 = db.registrar_potrero("OLEGARIO I", "01")
    p2 = db.registrar_potrero("CORRAL SANTAMART", "02")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1)
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO", potrero=p2)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp1 = qe.responder("cuantos animales hay donde olegario")
    assert "47" in resp1 and "Resumen General" not in resp1

    resp2 = qe.responder("cuantos animales hay en el corral santa martha")
    assert "48" in resp2 and "Resumen General" not in resp2

    # Sin mención de potrero, debe seguir cayendo en el resumen general.
    resp3 = qe.responder("total animales")
    assert "Resumen General" in resp3

    # La combinación categoría + potrero sigue teniendo prioridad sobre el
    # match genérico de nombre de potrero (no debe perder el filtro).
    db.registrar_parto("47", fecha="2026-08-01")
    resp4 = qe.responder("vacas paridas que estan en el potrero olegario 1")
    assert "Vacas paridas" in resp4


def test_conteo_vendidos_tolera_typo_y_verbo(db):
    """Regresión: 'cuantoa' (typo de 'cuantos') y 'vendieron' (verbo, no solo
    el adjetivo 'vendidos') no eran reconocidos."""
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="VENDIDO")
    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    for pregunta in ["cuantoa animales vendieron este mes", "cuantos animales vendieron",
                      "cuantoa animales hay de 2 anos"]:
        resp = qe.responder(pregunta)
        assert "No entendí" not in resp


def test_movimientos_venta_periodo(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="VENDIDO")
    db.registrar_movimiento("47", fecha="2026-08-15", tipo_movimiento="VENTA", precio=1500000)
    db.registrar_animal("48", sexo="Hembra", estado="VENDIDO")
    db.registrar_movimiento("48", fecha="2026-01-01", tipo_movimiento="VENTA", precio=1200000)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("cuantos animales vendieron este mes")
    assert "No entendí" not in resp
    assert "47" in resp
    assert "48" not in resp


def test_inventario_por_raza(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", raza="Holstein Neg-T")
    db.registrar_animal("48", sexo="Macho", estado="ACTIVO", raza="Gyr")
    db.registrar_animal("49", sexo="Hembra", estado="ACTIVO", raza="Gyr")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("cuantas vacas holstein hay")
    assert "No entendí" not in resp
    assert "47" in resp

    resp2 = qe.responder("cuantos animales raza gyr hay")
    assert "48" in resp2 and "49" in resp2 and "47" not in resp2


def test_potrero_con_mas_animales(db):
    from src.engine.query_engine import QueryEngine
    p1 = db.registrar_potrero("OLEGARIO I", "01")
    p2 = db.registrar_potrero("VERSALLES", "02")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1)
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO", potrero=p1)
    db.registrar_animal("49", sexo="Hembra", estado="ACTIVO", potrero=p2)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("que potrero tiene mas animales")
    assert "No entendí" not in resp
    assert "OLEGARIO I" in resp


def test_animales_por_umbral_de_peso(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_pesaje("47", fecha="2026-08-01", peso_kg=450)
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO")
    db.registrar_pesaje("48", fecha="2026-08-01", peso_kg=200)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("cuantos animales pesan mas de 400 kilos")
    assert "No entendí" not in resp
    assert "47" in resp and "48" not in resp

    resp2 = qe.responder("cuantos animales pesan menos de 300 kilos")
    assert "48" in resp2 and "47" not in resp2


def test_movimientos_entrada_periodo(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_movimiento("47", fecha="2026-08-20", tipo_movimiento="ENTRADA")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("cuantos animales entraron este mes")
    assert "No entendí" not in resp
    assert "47" in resp


def test_partos_mes_y_anio_pasado(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("47", fecha="2026-08-15")  # mes pasado respecto a hoy=2026-09-01
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto("48", fecha="2025-06-01")  # año pasado

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp_mes = qe.responder("cuantos partos hubo el mes pasado")
    assert "No entendí" not in resp_mes
    assert "47" in resp_mes and "48" not in resp_mes

    resp_anio = qe.responder("cuantos partos hubo el año pasado")
    assert "48" in resp_anio and "47" not in resp_anio

    resp_este_anio = qe.responder("cuantos partos hubo este año")
    assert "47" in resp_este_anio and "48" not in resp_este_anio


def test_muertes_por_periodo(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="MUERTO")
    db.registrar_muerte("47", fecha="2026-08-20", causa_presunta="Picadura de culebra")
    db.registrar_animal("48", sexo="Hembra", estado="MUERTO")
    db.registrar_muerte("48", fecha="2025-01-01", causa_presunta="Vieja")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("animales muertos este mes")
    assert "No entendí" not in resp
    assert "47" in resp and "48" not in resp

    # Regresión: "esta semana" también fallaba porque extraer_tag tomaba la
    # palabra "semana" (sin dígitos) como si fuera un arete real, y la
    # condición `and not tag` de la rama bloqueaba la respuesta agregada.
    resp_semana = qe.responder("animales muertos esta semana")
    assert "No entendí" not in resp_semana


def test_destetes_por_periodo_y_total(db):
    from src.engine.query_engine import QueryEngine
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_pesaje("47", fecha="2026-08-15", peso_kg=180, evento="DESTETE")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp_semana = qe.responder("cuantos destetes hubo esta semana")
    assert "No hay destetes" in resp_semana

    resp_mes = qe.responder("cuantos destetes hubo este mes")
    assert "47" in resp_mes

    resp_total = qe.responder("cuantos destetes hay")
    assert "47" in resp_total


def test_lote_ocupacion(db):
    from src.engine.query_engine import QueryEngine
    p1 = db.registrar_potrero("BAJO", "01")
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO")
    db.registrar_traslado("V1", fecha="2026-08-15", lote="1", potrero_destino=p1)
    db.registrar_animal("V2", sexo="Hembra", estado="ACTIVO")
    db.registrar_traslado("V2", fecha="2026-08-20", lote="2", potrero_destino=p1)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("días de pastoreo del lote 1")
    assert "No entendí" not in resp
    assert "V1" in resp
    assert "V2" not in resp
    assert "17 días" in resp


def test_consulta_combinada_categoria_y_potrero(db):
    from src.engine.query_engine import QueryEngine
    p1 = db.registrar_potrero("OLEGARIO I", "01")
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2020-01-01")
    db.registrar_parto("V1", fecha="2026-08-01")
    db.registrar_animal("V2", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2019-01-01")
    db.registrar_parto("V2", fecha="2025-01-01")
    db.registrar_animal("T1", sexo="Macho", estado="ACTIVO", potrero=p1, nombre="TORO PADRON", fecha_nacimiento="2020-01-01")

    qe = QueryEngine(db, hoy=date(2026, 9, 1))

    resp_paridas = qe.responder("vacas paridas que están en el potrero olegario 1")
    assert "No entendí" not in resp_paridas
    assert "V1" in resp_paridas
    assert "V2" not in resp_paridas
    assert "T1" not in resp_paridas

    resp_toros = qe.responder("toros en el potrero olegario 1")
    assert "T1" in resp_toros
    assert "V1" not in resp_toros

    resp_sin_filtro = qe.responder("animales en el potrero olegario 1")
    assert "V1" in resp_sin_filtro and "V2" in resp_sin_filtro and "T1" in resp_sin_filtro

    resp_vacio = qe.responder("novillas que están en el potrero olegario 1")
    assert "No hay animales" in resp_vacio


def test_potreros_ocupados_y_sobreocupacion(db):
    from src.engine.query_engine import QueryEngine
    p1 = db.registrar_potrero("VERSALLES", "01")
    db.registrar_animal("V1", sexo="Hembra", estado="ACTIVO", potrero=p1)
    db.registrar_traslado("V1", fecha="2026-08-20", potrero_destino=p1)

    qe = QueryEngine(db, hoy=date(2026, 9, 1))
    resp = qe.responder("¿qué potreros están ocupados hoy?")
    assert "No entendí" not in resp
    assert "VERSALLES" in resp

    resp2 = qe.responder("qué potreros tienen sobreocupación")
    assert "VERSALLES" in resp2
    assert "Sobreocupación" in resp2




