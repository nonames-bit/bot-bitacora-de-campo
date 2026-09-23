"""Distocias y pérdidas gestacionales (cierre Fase 5.2): parser, registro,
métricas, confirmación del bot y sección en datos_reproduccion."""
import pytest

from src.bot.bot_interface import Bot
from src.db.database import Database
from src.engine.dashboard_data import datos_reproduccion
from src.parsers.event_parser import EventParser, ParsedEvent
from src.server.formatters import formatear_kpis_reproduccion


@pytest.fixture
def parser():
    return EventParser()


@pytest.fixture
def db(tmp_path):
    ruta = str(tmp_path / "distocia.db")
    d = Database(ruta)
    d.create_tables()
    for tag, sexo in [("V1", "Hembra"), ("V2", "Hembra"), ("V3", "Hembra"), ("T1", "Macho")]:
        d.registrar_animal(tag, sexo=sexo, estado="ACTIVO")
    yield d
    d.close()


# ---------------------------------------------------------------------------
# Parser: lenguaje de campo para parto difícil
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("texto", [
    "pario la V1 y hubo que sacarle el ternero",
    "la V1 pario con parto distocico, ternero macho",
    "la V1 pario dificil, tuvimos que ayudar",
    "toco meter mano, pario la V1",
])
def test_parser_marca_distocia(parser, texto):
    ev = parser.parse(texto)
    assert ev.tipo == "parto"
    assert ev.datos.get("distocia") is True


@pytest.mark.parametrize("texto", [
    "pario la V1, ternero macho",
    "la V1 aborto",
    "la V1 pario una ternera muerta",
])
def test_parser_sin_distocia(parser, texto):
    ev = parser.parse(texto)
    assert ev.tipo == "parto"
    assert ev.datos.get("distocia") is not True


# ---------------------------------------------------------------------------
# NLU: "que" relativo no vuelve consulta una nota de campo, y el sexo de
# la cría no se extrae como tag (fantasma "macho"/"hembra" en inventario)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("texto", [
    "pario la 47 que estaba gorda",
    "insemine la 12 que entro en celo",
    "se murio el 105 que estaba enfermo",
])
def test_que_relativo_sigue_siendo_evento(texto):
    from src.parsers import nlp_engine as nlu
    assert nlu.es_consulta(texto) is False


@pytest.mark.parametrize("texto", [
    "que vacas debo inseminar",
    "que toro sirvio a la 47",
    "que le paso a la 12",
])
def test_que_interrogativo_sigue_siendo_consulta(texto):
    from src.parsers import nlp_engine as nlu
    assert nlu.es_consulta(texto) is True


def test_sexo_cria_no_es_tag(parser):
    from src.parsers import nlp_engine as nlu
    assert "macho" not in nlu.extraer_tags("pario la 47, ternero macho")
    assert "hembra" not in nlu.extraer_tags("pario la 47, ternera hembra")
    ev = parser.parse("pario la 47, ternero macho")
    assert ev.tipo == "parto"
    assert ev.datos.get("id_cria") != "macho"


def test_nota_con_que_se_registra_como_parto(db):
    from src.bot.bot_interface import Bot as BotLocal
    bot = BotLocal(db)
    resp = bot.procesar_texto("pario la V1 y hubo que sacarle el ternero")
    assert "Registrado parto" in resp
    fila = db.query_one(
        "SELECT distocia FROM partos WHERE vaca_id = ?", (db.animal_id("V1"),)
    )
    assert fila is not None and (fila["distocia"] or 0) == 1
    assert db.animal_id("macho") is None


# ---------------------------------------------------------------------------
# Registro: columna distocia, idempotencia y pérdidas en 0 aunque se pida
# ---------------------------------------------------------------------------
def test_registrar_parto_distocia(db):
    pid = db.registrar_parto("V1", fecha="2026-09-01", sexo_cria="Macho",
                             id_cria_tag="C1", distocia=True)
    assert pid is not None
    fila = db.query_one("SELECT distocia, tipo_evento FROM partos WHERE id = ?", (pid,))
    assert (fila["distocia"] or 0) == 1
    assert fila["tipo_evento"] == "PARTO"


def test_distocia_se_ignora_en_perdidas(db):
    pid = db.registrar_parto("V1", fecha="2026-09-02", tipo_evento="ABORTO", distocia=True)
    assert pid is not None
    fila = db.query_one("SELECT distocia FROM partos WHERE id = ?", (pid,))
    assert (fila["distocia"] or 0) == 0


def test_distocia_se_propaga_en_reintento(db):
    pid1 = db.registrar_parto("V1", fecha="2026-09-03", sexo_cria="Hembra", id_cria_tag="C2")
    pid2 = db.registrar_parto("V1", fecha="2026-09-03", sexo_cria="Hembra",
                              id_cria_tag="C2", distocia=True)
    assert pid1 == pid2
    fila = db.query_one("SELECT distocia FROM partos WHERE id = ?", (pid1,))
    assert (fila["distocia"] or 0) == 1


# ---------------------------------------------------------------------------
# Métricas: tasas, desglose, reincidentes y recientes
# ---------------------------------------------------------------------------
@pytest.fixture
def db_metricas(tmp_path):
    ruta = str(tmp_path / "metricas.db")
    d = Database(ruta)
    d.create_tables()
    for tag, sexo in [("A", "Hembra"), ("B", "Hembra"), ("C", "Hembra"), ("T1", "Macho")]:
        d.registrar_animal(tag, sexo=sexo, estado="ACTIVO")
    # 2 partos normales + 1 distócico + 1 gemelar (2 filas, 1 evento)
    d.registrar_parto("A", fecha="2026-01-10", sexo_cria="Macho", id_cria_tag="CA1")
    d.registrar_parto("B", fecha="2026-02-10", sexo_cria="Hembra", id_cria_tag="CB1", distocia=True)
    d.registrar_parto("C", fecha="2026-03-10", sexo_cria="Macho", id_cria_tag="CC1",
                      tipo_evento="GEMELAR", grupo_parto_id=999)
    d.registrar_parto("C", fecha="2026-03-10", sexo_cria="Hembra", id_cria_tag="CC2",
                      tipo_evento="GEMELAR", grupo_parto_id=999)
    # 2 abortos de A (reincidente) + 1 momificación de B
    d.registrar_parto("A", fecha="2026-05-01", tipo_evento="ABORTO")
    d.registrar_parto("A", fecha="2026-08-01", tipo_evento="ABORTO")
    d.registrar_parto("B", fecha="2026-06-01", tipo_evento="MOMIFICACION")
    yield d
    d.close()


def test_metricas_perdidas(db_metricas):
    m = db_metricas.metricas_perdidas_reproductivas()
    assert m["partos"] == 3  # gemelar cuenta como 1 evento
    assert m["perdidas"] == 3
    assert m["tasa_perdida_pct"] == 50.0
    assert m["por_tipo"] == {"ABORTO": 2, "MOMIFICACION": 1}
    assert m["distocias"] == 1
    assert m["tasa_distocia_pct"] == round(1 / 3 * 100, 1)
    assert m["reincidentes"] == [{"vaca": "A", "perdidas": 2}]
    assert m["recientes"][0]["vaca"] == "A"
    assert m["recientes"][0]["tipo_evento"] == "ABORTO"


def test_metricas_sin_datos_no_rompen(db):
    m = db.metricas_perdidas_reproductivas()
    assert m["partos"] == 0 and m["perdidas"] == 0
    assert m["tasa_perdida_pct"] == 0.0 and m["tasa_distocia_pct"] == 0.0
    assert m["recientes"] == [] and m["reincidentes"] == []


def test_dashboard_incluye_perdidas(db_metricas):
    d = datos_reproduccion(db_metricas)
    assert "perdidas" in d
    assert d["perdidas"]["perdidas"] == 3
    assert d["perdidas"]["distocias"] == 1


def test_kpi_reprod_incluye_perdidas(db_metricas):
    txt = formatear_kpis_reproduccion(db_metricas)
    assert "PÉRDIDAS GESTACIONALES" in txt
    assert "×2" in txt or "A" in txt


# ---------------------------------------------------------------------------
# Bot: confirmación de parto difícil
# ---------------------------------------------------------------------------
def test_confirmacion_parto_distocia(db):
    bot = Bot(db)
    ev = ParsedEvent(tipo="parto", texto="x", animal_tag="V1",
                     fecha="2026-09-20",
                     datos={"tipo_evento": "PARTO", "sexo_cria": "Macho", "distocia": True})
    assert "difícil" in bot._confirmacion(ev)
    ev2 = ParsedEvent(tipo="parto", texto="x", animal_tag="V1",
                      fecha="2026-09-20",
                      datos={"tipo_evento": "PARTO", "sexo_cria": "Macho"})
    assert "difícil" not in bot._confirmacion(ev2)
