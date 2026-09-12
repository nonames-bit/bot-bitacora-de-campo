"""Pruebas del parser de eventos y del motor NLU."""
import pytest

from src.parsers.event_parser import EventParser
from src.parsers import nlp_engine as nlu


@pytest.fixture
def parser():
    return EventParser()


# ---------------------------------------------------------------------------
# Clasificación de intenciones
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("texto, esperado", [
    ("pario la 47, ternero macho", "parto"),
    ("se murio el 105 mordedura de culebra", "muerte"),
    ("insemine la 47 con toro brahman 502", "servicio"),
    ("la 47 esta en celo", "celo"),
    ("le puse oxitetraciclina 20ml a la 47", "tratamiento"),
    ("pesaje de la 12 peso 420 kg", "pesaje"),
    ("pase el lote 2 del potrero bajo al potrero norte", "traslado"),
    ("entraron 15 novillas compradas en subasta", "movimiento"),
])
def test_clasificar(texto, esperado):
    assert nlu.clasificar(texto) == esperado


def test_consulta_detectada(parser):
    ev = parser.parse("¿cuándo parió la 47?")
    assert ev.tipo == "consulta"


# ---------------------------------------------------------------------------
# Extracción por evento
# ---------------------------------------------------------------------------
def test_parse_parto(parser):
    ev = parser.parse("pario la 47, ternero macho")
    assert ev.tipo == "parto"
    assert ev.animal_tag == "47"
    assert ev.datos["sexo_cria"] == "Macho"
    assert ev.datos["estado_cria"] == "VIVO"


def test_parse_parto_hembra_muerto(parser):
    ev = parser.parse("la 47 pario una ternera muerta")
    assert ev.tipo == "parto"
    assert ev.datos["sexo_cria"] == "Hembra"
    assert ev.datos["estado_cria"] == "MUERTO"


def test_parse_muerte(parser):
    ev = parser.parse("se murio el 105 mordedura de culebra")
    assert ev.tipo == "muerte"
    assert ev.animal_tag == "105"
    assert "mordedura" in ev.datos["causa_presunta"]


def test_parse_servicio(parser):
    ev = parser.parse("insemine la 47 con toro brahman 502")
    assert ev.tipo == "servicio"
    assert ev.animal_tag == "47"
    assert ev.datos["tipo_servicio"] == "IA"
    assert ev.datos["toro_pajilla"] == "502"
    assert ev.datos["raza_toro"] == "brahman"


def test_parse_servicio_monta(parser):
    ev = parser.parse("monte la 12 con el toro 33")
    assert ev.tipo == "servicio"
    assert ev.datos["tipo_servicio"] == "MONTA"


def test_parse_celo(parser):
    ev = parser.parse("la 47 esta en celo en la tarde")
    assert ev.tipo == "celo"
    assert ev.animal_tag == "47"
    assert ev.datos["am_pm"] == "PM"


def test_parse_secado(parser):
    ev = parser.parse("se seco la 47 por mastitis")
    assert ev.tipo == "secado"
    assert ev.animal_tag == "47"
    assert ev.datos["motivo"] == "Mastitis"


def test_parse_secado_no_confunde_potrero_seco_con_evento(parser):
    ev = parser.parse("el potrero esta muy seco por la sequia")
    assert ev.tipo != "secado"


def test_parse_tratamiento(parser):
    ev = parser.parse("le puse oxitetraciclina 20ml a la 47 con 14 dias de retiro")
    assert ev.tipo == "tratamiento"
    assert ev.animal_tag == "47"
    assert ev.datos["producto"] == "oxitetraciclina"
    assert ev.datos["dosis"] == "20ml"
    assert ev.datos["dias_retiro"] == 14


def test_parse_tratamiento_retiro_carne_por_defecto(parser):
    ev = parser.parse("le puse oxitetraciclina 20ml a la 47 con 14 dias de retiro")
    assert ev.datos["dias_retiro_leche"] is None
    assert ev.datos["dias_retiro_carne"] == 14


def test_parse_tratamiento_retiro_leche(parser):
    ev = parser.parse("le puse oxitetraciclina a la 47 con 14 dias de retiro en leche")
    assert ev.datos["dias_retiro_leche"] == 14
    assert ev.datos["dias_retiro_carne"] is None


def test_prefijo_del_no_captura_tag(parser):
    ev = parser.parse("pase del potrero 5 al potrero 6")
    assert ev.tipo == "traslado"
    assert ev.animal_tag is None


def test_parse_pesaje(parser):
    ev = parser.parse("pesaje de la 12 peso 420 kg")
    assert ev.tipo == "pesaje"
    assert ev.animal_tag == "12"
    assert ev.datos["peso_kg"] == 420.0


def test_parse_traslado(parser):
    ev = parser.parse("pase el lote 2 del potrero bajo al potrero norte")
    assert ev.tipo == "traslado"
    assert ev.datos["lote"] == "2"
    assert ev.datos["potrero_origen"] == "bajo"
    assert ev.datos["potrero_destino"] == "norte"


def test_parse_movimiento_compra(parser):
    ev = parser.parse("entraron 15 novillas compradas en subasta")
    assert ev.tipo == "movimiento"
    assert ev.datos["tipo_movimiento"] == "COMPRA"
    assert ev.datos["cantidad"] == 15


def test_parse_desconocido(parser):
    ev = parser.parse("bla bla bla")
    assert ev.tipo == "desconocido"


def test_parse_fecha_hoy(parser):
    ev = parser.parse("pario la 47 hoy")
    assert ev.fecha is not None
    assert ev.fecha == parser.hoy.isoformat()


def test_extraer_tag_alfanumerico_y_limpieza_timestamp(parser):
    assert nlu.extraer_tag("consulta N069") == "n069"
    assert nlu.extraer_tag("/consulta N06910:13 PM") == "n069"
    assert nlu.extraer_tag("N069") == "n069"
    assert nlu.extraer_tag("ficha de la N069 10:13 PM") == "n069"

    ev = parser.parse("consulta N069")
    assert ev.tipo == "consulta"

    ev_directo = parser.parse("N069")
    assert ev_directo.tipo == "consulta"


# Regresión real: al consultar "JA26-6" (arete de una cría numerada como
# "madre-n", convención habitual de la finca) el bot abría la ficha de la
# MADRE (JA26) porque el regex de extraer_tags no incluía el guion antes del
# sufijo numérico y truncaba "ja26-6" a "ja26".
@pytest.mark.parametrize("texto, esperado", [
    ("JA26-6", "ja26-6"),
    ("consulta JA26-6", "ja26-6"),
    ("N065-1", "n065-1"),
    ("ficha de la JA26-6", "ja26-6"),
])
def test_extraer_tag_con_sufijo_de_cria_numerada(texto, esperado):
    assert nlu.extraer_tag(texto) == esperado


def test_transcribe_audio_sidecar(tmp_path):
    from src.parsers.media_handler import transcribe_audio
    audio = tmp_path / "nota_voz.ogg"
    audio.write_bytes(b"dummy audio")
    sidecar = tmp_path / "nota_voz.ogg.txt"
    sidecar.write_text("pario la 47 ternero macho", encoding="utf-8")

    res = transcribe_audio(str(audio))
    assert res.texto == "pario la 47 ternero macho"
    assert res.origen == "sidecar"


def test_transcribe_audio_transcriber_callback():
    from src.parsers.media_handler import transcribe_audio
    dummy_audio = "fake_audio.ogg"
    res = transcribe_audio(dummy_audio, transcriber=lambda p: "se murio el 105")
    assert res.texto == "se murio el 105"
    assert res.origen == "transcriber"


# ---------------------------------------------------------------------------
# es_consulta: distinguir preguntas agregadas de eventos sobre un animal puntual.
# Regresión real: "animales muertos este mes" se clasificaba como evento (no
# consulta) porque no traía ninguna palabra interrogativa explícita, y el bot
# llegó a responder "Registrada muerte del animal lote" sin que existiera tal
# animal -- una confirmación falsa. "vacas vendidas esta semana" tenía un
# segundo problema encadenado: extraer_tag tomaba la palabra "vendidas" como
# si fuera un arete real.
@pytest.mark.parametrize("texto, esperado", [
    ("animales muertos este mes", True),
    ("vacas vendidas esta semana", True),
    ("cuantos animales vendieron el mes pasado", True),
    ("animales vendidos este año", True),
    ("terneros nacidos ultimos 15 dias", True),
    ("murio la 47", False),
    ("se murio la vaca de la mancha", False),
    ("vendi la 47", False),
    ("pario la 47 ternero macho", False),
])
def test_es_consulta_plural_con_periodo_no_arete(texto, esperado):
    assert nlu.es_consulta(texto) is esperado


# ---------------------------------------------------------------------------
# Condición corporal (BCS): nueva capacidad, calca el patrón de pesaje pero
# con una salvedad -- sin valor numérico es una PREGUNTA, no un registro.
@pytest.mark.parametrize("texto, esperado", [
    ("condición corporal de la 47 es 3.5", "3.5"),
    ("la 12 tiene condición corporal 3", "3"),
    ("puntaje corporal 4.0 de la 105", "4.0"),
])
def test_extraer_condicion_corporal(texto, esperado):
    tag = nlu.extraer_tag(texto)
    valor = nlu.extraer_condicion_corporal(texto, tag_excluir=tag)
    assert valor == float(esperado)


def test_clasificar_condicion_corporal():
    assert nlu.clasificar("condición corporal de la 47 es 3.5") == "condicion_corporal"


def test_parse_condicion_corporal(parser):
    ev = parser.parse("condición corporal de la 47 es 3.5")
    assert ev.tipo == "condicion_corporal"
    assert ev.animal_tag == "47"
    assert ev.datos["valor"] == 3.5


def test_parse_condicion_corporal_sin_valor_es_consulta(parser):
    # Regresión: "condición corporal de la 47" sin número es una pregunta
    # implícita ("¿cuál es...?"), no un registro con valor=None. Mismo tipo
    # de bug que causó el falso "Registrada muerte del animal lote".
    ev = parser.parse("condición corporal de la 47")
    assert ev.tipo == "consulta"


# ---------------------------------------------------------------------------
# Producción de leche: mismo patrón que condición corporal (calca pesaje,
# pero sin número extraíble es una PREGUNTA, no un registro).
@pytest.mark.parametrize("texto, esperado", [
    ("la 47 dio 12 litros de leche", "12"),
    ("ordeñé 8.5 litros a la 12", "8.5"),
    ("12 litros de leche de la 47", "12"),
])
def test_extraer_litros_leche(texto, esperado):
    assert nlu.extraer_litros_leche(texto) == float(esperado)


def test_clasificar_leche():
    assert nlu.clasificar("la 47 dio 12 litros de leche") == "leche"


def test_parse_leche(parser):
    ev = parser.parse("la 47 dio 12 litros de leche")
    assert ev.tipo == "leche"
    assert ev.animal_tag == "47"
    assert ev.datos["litros"] == 12.0


def test_parse_leche_sin_valor_es_consulta(parser):
    # Regresión (mismo tipo que condición corporal): "cuánta leche dio la 47"
    # sin número extraíble es una pregunta, no un registro con litros=None.
    ev = parser.parse("cuánta leche dio la 47")
    assert ev.tipo == "consulta"


def test_transcribe_audio_sin_transcripcion_error(tmp_path):
    from src.parsers.media_handler import transcribe_audio, MediaError
    import pytest
    audio_inexistente = str(tmp_path / "sin_texto.ogg")
    with pytest.raises(MediaError):
        transcribe_audio(audio_inexistente)


# ---------------------------------------------------------------------------
# Diagnóstico de gestación: extracción de días, semanas y meses de gestación.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("texto, esperado", [
    ("palpe a023 esta prenada 3 meses", 90),
    ("palpe la 47 confirmada preñada 60 días", 60),
    ("palpe la 47 prenada 2 meses 15 dias", 75),
    ("palpe la 47 prenada 2 meses y 15 dias", 75),
    ("palpe la 105 prenada 2 meses y medio", 75),
    ("palpe la 47 prenada 8 semanas", 56),
    ("palpe la 47 prenada 3 semanas y 2 dias", 23),
    ("vaca 12 prenada 1 mes", 30),
    ("prenada medio mes", 15),
    ("palpe la 47 prenada 2.5 meses", 75),
    ("palpe la 47 prenada 60", 60),
])
def test_extraer_dias_gestacion(texto, esperado):
    assert nlu.extraer_dias_gestacion(texto) == esperado


def test_parse_diagnostico_gestacion_3_meses(parser):
    ev = parser.parse("palpe a023 esta prenada 3 meses")
    assert ev.tipo == "diagnostico_gestacion"
    assert ev.animal_tag == "a023"
    assert ev.datos["resultado"] == "PREÑADA"
    assert ev.datos["dias_gestacion"] == 90


