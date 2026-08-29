"""Pruebas de los agentes extractores de dominio (reproduccion, sanidad, manejo).

El mock se hace inyectando un GeminiClient falso vía el parámetro ``client=``
en vez de parchear urllib, para no reconstruir el envelope HTTP en cada test.
"""
from unittest.mock import MagicMock


from src.llm import manejo, reproduccion, sanidad


def _fake_client(resultado):
    client = MagicMock()
    client.is_available.return_value = True
    client.generate_structured.return_value = resultado
    return client


def _unavailable_client():
    client = MagicMock()
    client.is_available.return_value = False
    return client


# ---------------------------------------------------------------------------
# reproduccion
# ---------------------------------------------------------------------------
def test_reproduccion_parse_single_event():
    resultado = {
        "eventos": [
            {
                "tipo": "parto",
                "animal_tag": "47",
                "fecha": None,
                "datos": {
                    "sexo_cria": "macho",
                    "estado_cria": None,
                    "peso_nacimiento": "38,5",
                    "id_cria": None,
                },
            }
        ]
    }
    eventos = reproduccion.parse("pario la 47", client=_fake_client(resultado))
    assert eventos is not None
    assert len(eventos) == 1
    ev = eventos[0]
    assert ev.tipo == "parto"
    assert ev.animal_tag == "47"
    assert ev.datos["sexo_cria"] == "Macho"
    assert ev.datos["estado_cria"] == "VIVO"
    assert ev.datos["peso_nacimiento"] == 38.5


def test_reproduccion_parse_multiple_events():
    resultado = {
        "eventos": [
            {"tipo": "parto", "animal_tag": "47", "datos": {"sexo_cria": "Hembra"}},
            {"tipo": "servicio", "animal_tag": "12", "datos": {"tipo_servicio": "monta"}},
        ]
    }
    eventos = reproduccion.parse("pario la 47 y monte la 12", client=_fake_client(resultado))
    assert len(eventos) == 2
    assert eventos[0].tipo == "parto"
    assert eventos[1].tipo == "servicio"
    assert eventos[1].datos["tipo_servicio"] == "MONTA"


def test_reproduccion_parse_celo_am_pm():
    resultado = {"eventos": [{"tipo": "celo", "animal_tag": "9", "datos": {"am_pm": "am"}}]}
    eventos = reproduccion.parse("la 9 esta en celo en la manana", client=_fake_client(resultado))
    assert eventos[0].datos["am_pm"] == "AM"


def test_reproduccion_parse_client_unavailable():
    assert reproduccion.parse("pario la 47", client=_unavailable_client()) is None


def test_reproduccion_parse_client_returns_none():
    assert reproduccion.parse("pario la 47", client=_fake_client(None)) is None


# ---------------------------------------------------------------------------
# sanidad
# ---------------------------------------------------------------------------
def test_sanidad_parse_tratamiento_calcula_retiro():
    resultado = {
        "eventos": [
            {
                "tipo": "tratamiento",
                "animal_tag": "12",
                "datos": {"producto": "oxitetraciclina", "dosis": "20ml", "dias_retiro": "14"},
            }
        ]
    }
    eventos = sanidad.parse(
        "vacune la 12 con oxitetraciclina 20ml, retiro 14 dias",
        client=_fake_client(resultado),
    )
    ev = eventos[0]
    assert ev.tipo == "tratamiento"
    assert ev.datos["dias_retiro"] == 14
    assert "dias_retiro_leche" in ev.datos
    assert "dias_retiro_carne" in ev.datos


def test_sanidad_parse_muerte_causa():
    resultado = {"eventos": [{"tipo": "muerte", "animal_tag": "105", "datos": {"causa_presunta": "culebra"}}]}
    eventos = sanidad.parse("se murio la 105 por culebra", client=_fake_client(resultado))
    assert eventos[0].tipo == "muerte"
    assert eventos[0].datos["causa_presunta"] == "culebra"


def test_sanidad_parse_client_unavailable():
    assert sanidad.parse("vacune la 12", client=_unavailable_client()) is None


def test_sanidad_parse_client_returns_none():
    assert sanidad.parse("vacune la 12", client=_fake_client(None)) is None


# ---------------------------------------------------------------------------
# manejo
# ---------------------------------------------------------------------------
def test_manejo_parse_pesaje_default_evento():
    resultado = {"eventos": [{"tipo": "pesaje", "animal_tag": "8", "datos": {"peso_kg": "205,3"}}]}
    eventos = manejo.parse("pese la 8, dio 205.3 kg", client=_fake_client(resultado))
    ev = eventos[0]
    assert ev.datos["peso_kg"] == 205.3
    assert ev.datos["evento"] == "Control"


def test_manejo_parse_movimiento_cantidad_int():
    resultado = {
        "eventos": [
            {
                "tipo": "movimiento",
                "animal_tag": None,
                "datos": {"tipo_movimiento": "COMPRA", "cantidad": "5"},
            }
        ]
    }
    eventos = manejo.parse("compre 5 novillas", client=_fake_client(resultado))
    assert eventos[0].datos["cantidad"] == 5


def test_manejo_parse_traslado():
    resultado = {
        "eventos": [
            {
                "tipo": "traslado",
                "animal_tag": None,
                "datos": {"lote": "A", "potrero_origen": "3", "potrero_destino": "4"},
            }
        ]
    }
    eventos = manejo.parse("pase el lote A del potrero 3 al 4", client=_fake_client(resultado))
    assert eventos[0].datos["potrero_destino"] == "4"


def test_manejo_parse_client_unavailable():
    assert manejo.parse("pese la 8", client=_unavailable_client()) is None


def test_manejo_parse_client_returns_none():
    assert manejo.parse("pese la 8", client=_fake_client(None)) is None
