"""Pruebas de la Fase 5.1: Reproducción Completa, Diagnóstico Gestacional y Termo Criogénico."""
from datetime import date

from src.bot.bot_interface import Bot
from src.db.database import Database
from src.db.models import TABLAS, DiagnosticoGestacion, PajuelaInventario, TermoNitrogeno
from src.engine.query_engine import QueryEngine
from src.parsers.event_parser import EventParser
from src.server.formatters import (
    formatear_diagnosticos_recientes,
    formatear_estado_termo,
    formatear_kpis_reproduccion,
    formatear_panel_reproduccion,
    formatear_stock_pajuelas,
)
from src.server.keyboards import (
    crear_teclado_reproduccion,
    crear_teclado_reproduccion_detalle,
)


def test_schema_modelos_palpacion_termo(db: Database):
    """Verifica la existencia de las nuevas tablas y modelos de datos."""
    for t in ("diagnosticos_gestacion", "pajuelas_inventario", "termo_nitrogeno"):
        assert t in TABLAS
        assert db.query_one(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'") is not None

    assert "diagnosticos_gestacion" in db.TABLAS_EVENTOS

    d = DiagnosticoGestacion(vaca_id=1, resultado="PREÑADA", dias_gestacion=60)
    assert d.resultado == "PREÑADA"
    assert d.dias_gestacion == 60

    p = PajuelaInventario(codigo_toro="502", cantidad=10, canastilla="C1")
    assert p.codigo_toro == "502"
    assert p.cantidad == 10

    t = TermoNitrogeno(fecha_recarga="2026-08-31", dias_intervalo=21)
    assert t.dias_intervalo == 21


def test_parser_palpacion_prenada():
    """Verifica la extracción NLU de un diagnóstico positivo con días de gestación."""
    parser = EventParser(hoy=date(2026, 8, 31))
    ev = parser.parse("palpé la 47 confirmada preñada 60 días")

    assert ev.tipo == "diagnostico_gestacion"
    assert ev.animal_tag == "47"
    assert ev.datos["resultado"] == "PREÑADA"
    assert ev.datos["dias_gestacion"] == 60


def test_parser_palpacion_vacia():
    """Verifica la extracción NLU de un diagnóstico negativo (vacía)."""
    parser = EventParser(hoy=date(2026, 8, 31))
    ev = parser.parse("la 12 vacía")

    assert ev.tipo == "diagnostico_gestacion"
    assert ev.animal_tag == "12"
    assert ev.datos["resultado"] == "VACIA"


def test_parser_palpacion_variantes_texto():
    """Verifica diversas formas verbales de mayordomo para registrar palpaciones."""
    parser = EventParser(hoy=date(2026, 8, 31))

    ev1 = parser.parse("palpe la vaca 105 preñada")
    assert ev1.tipo == "diagnostico_gestacion"
    assert ev1.animal_tag == "105"
    assert ev1.datos["resultado"] == "PREÑADA"

    ev2 = parser.parse("palpacion de la 47 salio vacia")
    assert ev2.tipo == "diagnostico_gestacion"
    assert ev2.animal_tag == "47"
    assert ev2.datos["resultado"] == "VACIA"

    ev3 = parser.parse("diagnostico de gestacion 47 prenada 90 dias")
    assert ev3.tipo == "diagnostico_gestacion"
    assert ev3.animal_tag == "47"
    assert ev3.datos["resultado"] == "PREÑADA"
    assert ev3.datos["dias_gestacion"] == 90


def test_db_registrar_diagnostico_y_listar(db: Database):
    """Prueba el registro en BD de diagnósticos gestacionales y su idempotencia."""
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_servicio(vaca_tag="47", fecha="2026-06-30", tipo_servicio="IA", toro_pajilla="502")

    diag_id = db.registrar_diagnostico(
        vaca_tag="47",
        fecha="2026-08-31",
        resultado="PREÑADA",
        dias_gestacion=62,
        responsable="Dr. Martínez",
    )
    assert isinstance(diag_id, int)

    # Idempotencia
    diag_id2 = db.registrar_diagnostico(
        vaca_tag="47",
        fecha="2026-08-31",
        resultado="PREÑADA",
        dias_gestacion=62,
    )
    assert diag_id == diag_id2

    # Consulta y listado
    diags = db.listar_diagnosticos(vaca_tag_or_id="47")
    assert len(diags) == 1
    assert diags[0]["resultado"] == "PREÑADA"
    assert diags[0]["dias_gestacion"] == 62
    assert diags[0]["responsable"] == "Dr. Martínez"

    # Verificar que el servicio anterior quedó marcado como CONFIRMADA
    serv = db.ultimo_servicio("47")
    assert serv["estado"] == "CONFIRMADA"


def test_kpis_reproductivos_tasa_concepcion_y_sc(db: Database):
    """Calcula Tasa de Concepción (%) y Servicios por Concepción (S/C) por toro."""
    db.registrar_animal("V01", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("V02", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("V03", sexo="Hembra", estado="ACTIVO")

    # V01: 1 servicio con Toro 502 -> Preñada
    db.registrar_servicio("V01", fecha="2026-06-01", tipo_servicio="IA", toro_pajilla="502")
    db.registrar_diagnostico("V01", fecha="2026-08-01", resultado="PREÑADA")

    # V02: 1 servicio con Toro 502 -> Vacía, luego 2do servicio con Toro 502 -> Preñada
    db.registrar_servicio("V02", fecha="2026-05-01", tipo_servicio="IA", toro_pajilla="502")
    db.registrar_diagnostico("V02", fecha="2026-07-01", resultado="VACIA")
    db.registrar_servicio("V02", fecha="2026-07-05", tipo_servicio="IA", toro_pajilla="502")
    db.registrar_diagnostico("V02", fecha="2026-08-31", resultado="PREÑADA")

    # V03: 1 servicio con Toro 999 -> Vacía
    db.registrar_servicio("V03", fecha="2026-06-15", tipo_servicio="IA", toro_pajilla="999")
    db.registrar_diagnostico("V03", fecha="2026-08-15", resultado="VACIA")

    kpis = db.kpis_reproductivos_concepcion()
    assert kpis["total_servicios"] == 4
    assert kpis["total_prenadas"] == 2
    assert kpis["total_vacias"] == 2
    assert kpis["total_evaluados"] == 4
    assert kpis["tasa_concepcion"] == 50.0  # 2 / 4 = 50%
    assert kpis["servicios_por_concepcion"] == 2.0  # 4 / 2 = 2.0 S/C

    # KPI específico para Toro 502: 3 servicios, 2 preñadas, 1 vacía -> 66.7% concepción, S/C = 1.5
    kpi_502 = db.kpis_reproductivos_concepcion(toro_pajilla="502")
    assert kpi_502["total_servicios"] == 3
    assert kpi_502["total_prenadas"] == 2
    assert kpi_502["tasa_concepcion"] == 66.7
    assert kpi_502["servicios_por_concepcion"] == 1.5


def test_inventario_pajuelas_add_y_stock(db: Database):
    """Verifica el ingreso de pajuelas al termo, acumulación de stock y alertas críticas."""
    # Registro de pajuelas
    pid = db.registrar_pajuela(
        codigo_toro="502",
        raza="Brahman Rojo",
        procedencia="Crebis Genetic",
        canastilla="C1",
        cantidad=10,
        costo=35000.0,
    )
    assert isinstance(pid, int)

    # Añadir más pajuelas al mismo toro y canastilla
    pid2 = db.registrar_pajuela(
        codigo_toro="502",
        canastilla="C1",
        cantidad=5,
    )
    assert pid == pid2

    paj = db.obtener_pajuela("502")
    assert paj is not None
    assert paj["cantidad"] == 15
    assert paj["raza"] == "Brahman Rojo"

    # Registrar toro con bajo stock
    db.registrar_pajuela(codigo_toro="TORO_ESCASO", cantidad=2, canastilla="C2")
    criticas = db.alertas_stock_pajuelas(umbral_critico=2)
    assert len(criticas) == 1
    assert criticas[0]["codigo_toro"] == "TORO_ESCASO"


def test_descontar_pajuela_en_servicio_ia(db: Database):
    """Verifica que al registrar un servicio de tipo IA se descuente automáticamente 1 pajuela."""
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_pajuela(codigo_toro="502", cantidad=5, canastilla="C1")

    # Descuento directo
    ok = db.descontar_pajuela("502", cantidad=1)
    assert ok is True
    paj = db.obtener_pajuela("502")
    assert paj["cantidad"] == 4

    # Registro de servicio IA con el toro 502 -> debe descontar automáticamente a 3
    db.registrar_servicio(
        vaca_tag="47",
        fecha="2026-08-31",
        tipo_servicio="IA",
        toro_pajilla="502",
    )
    paj_post = db.obtener_pajuela("502")
    assert paj_post["cantidad"] == 3


def test_termo_nitrogeno_recarga_y_alertas(db: Database):
    """Verifica el registro de recargas de N2, cálculo de próxima recarga y alertas."""
    rec_id = db.registrar_recarga_nitrogeno(
        fecha_recarga="2026-08-10",
        dias_intervalo=21,
    )
    assert isinstance(rec_id, int)

    termo = db.ultimo_estado_termo(hoy=date(2026, 8, 25))
    assert termo is not None
    assert termo["fecha_recarga"] == "2026-08-10"
    assert termo["proxima_recarga"] == "2026-08-31"
    assert termo["dias_desde_recarga"] == 15
    assert termo["dias_restantes"] == 6
    assert termo["alerta_critica"] is False

    # A fecha 2026-08-28 (a 3 días de la recarga) debe marcar alerta crítica
    termo_urgente = db.ultimo_estado_termo(hoy=date(2026, 8, 28))
    assert termo_urgente["dias_restantes"] == 3
    assert termo_urgente["alerta_critica"] is True

    # Alerta en tabla alertas
    alerta = db.query_one("SELECT * FROM alertas WHERE tipo_alerta = 'RECARGA_NITROGENO' AND estado = 'PENDIENTE'")
    assert alerta is not None
    assert alerta["fecha_programada"] == "2026-08-31"


def test_bot_procesar_texto_palpacion(db: Database):
    """Verifica el flujo completo de Bot.procesar_texto para una palpación confirmada."""
    bot = Bot(db, hoy=date(2026, 8, 31))
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")

    resp = bot.procesar_texto("palpé la 47 confirmada preñada 60 días")
    assert "Registrado diagnóstico de gestación de la 47" in resp
    assert "PREÑADA" in resp
    assert "60 días" in resp

    # Verificar que generó alerta de parto esperado calculada con los días de gestación
    alerta_parto = db.query_one("SELECT * FROM alertas WHERE animal_id = ? AND tipo_alerta = 'PARTO_ESPERADO'", (db.animal_id("47"),))
    assert alerta_parto is not None
    # 283 - 60 = 223 días restantes desde 2026-08-31 -> 2027-04-11
    assert alerta_parto["fecha_programada"] == "2027-04-11"


def test_formatters_reproduccion_y_termo(db: Database):
    """Verifica que los formatters de Telegram generen contenido HTML válido."""
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_pajuela(codigo_toro="502", cantidad=10, raza="Brahman")
    db.registrar_recarga_nitrogeno("2026-08-31", dias_intervalo=21)
    db.registrar_diagnostico("47", fecha="2026-08-31", resultado="PREÑADA", dias_gestacion=60)

    txt_panel = formatear_panel_reproduccion(db, hoy=date(2026, 8, 31))
    assert "MÓDULO DE REPRODUCCIÓN" in txt_panel
    assert "Termo N₂" in txt_panel
    assert "10" in txt_panel

    txt_stock = formatear_stock_pajuelas(db)
    assert "INVENTARIO DE PAJUELAS" in txt_stock
    assert "502" in txt_stock

    txt_termo = formatear_estado_termo(db, hoy=date(2026, 8, 31))
    assert "ESTADO DEL TERMO CRIOGÉNICO" in txt_termo
    assert "2026-08-31" in txt_termo

    txt_kpis = formatear_kpis_reproduccion(db)
    assert "KPIs REPRODUCTIVOS" in txt_kpis

    txt_diags = formatear_diagnosticos_recientes(db)
    assert "DIAGNÓSTICOS DE GESTACIÓN" in txt_diags
    assert "47" in txt_diags


def test_query_engine_consultas_termo_y_pajuelas(db: Database):
    """Verifica que QueryEngine responda preguntas en lenguaje natural sobre pajuelas y termo."""
    engine = QueryEngine(db, hoy=date(2026, 8, 31))
    db.registrar_pajuela(codigo_toro="502", cantidad=12, raza="Brahman")
    db.registrar_recarga_nitrogeno("2026-08-31", dias_intervalo=21)

    res_paj = engine.responder("¿cuántas pajuelas disponibles hay?")
    assert "502" in res_paj
    assert "12" in res_paj

    res_termo = engine.responder("¿cuál es el estado del termo de nitrógeno?")
    assert "Termo Criogénico" in res_termo
    assert "2026-08-31" in res_termo


def test_teclados_reproduccion():
    """Verifica la correcta construcción de teclados del módulo de reproducción."""
    t_rep = crear_teclado_reproduccion()
    callbacks = [btn.callback_data for fila in t_rep.inline_keyboard for btn in fila]
    assert "cmd:pajuelas" in callbacks
    assert "cmd:termo" in callbacks
    assert "cmd:diagnosticos" in callbacks
    assert "cmd:kpi_reprod" in callbacks
    assert "menu:principal" in callbacks

    t_det = crear_teclado_reproduccion_detalle()
    callbacks_det = [btn.callback_data for fila in t_det.inline_keyboard for btn in fila]
    assert "cmd:reprod_menu" in callbacks_det
    assert "menu:principal" in callbacks_det
