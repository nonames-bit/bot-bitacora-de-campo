"""Pruebas unitarias para Fase 6.2:
- Integración Pluviométrica & Clima IDEAM.
- Capacidad de Carga Dinámica ajustada por Lluvia y Rotación Voisin.
- Balance Forrajero de Materia Seca (MS) Oferta vs Demanda (2.8% PV).
- Registro de lluvias y aforos históricos en base de datos.
- Enrutamiento NLU de consultas y comandos Telegram (/clima, /lluvia, /balance_forrajero).
"""
from datetime import date

import pytest

from src.bot.bot_interface import Bot
from src.db.database import Database
from src.engine.pasture_engine import (
    CONSUMO_MS_UGG,
    PCT_CONSUMO_PV,
    PastureEngine,
    balance_forrajero_calculo,
    capacidad_carga_dinamica_ha,
    consumo_diario_ms,
    factor_ajuste_clima,
    kg_ms_disponibles,
    ugg_de_peso,
)
from src.engine.query_engine import QueryEngine
from src.integrations.ideam_clima import ClimaIDEAM
from src.parsers.event_parser import EventParser
from src.server.formatters import (
    formatear_balance_forrajero_panel,
    formatear_clima_panel,
)
from src.server.keyboards import crear_teclado_clima, crear_teclado_clima_detalle


def test_pasture_engine_formulas_fase6():
    """Valida los cálculos biofísicos de pasturas y factores climáticos."""
    # 1. Consumo por peso vivo (2.8%)
    assert consumo_diario_ms(450.0) == pytest.approx(12.6, 0.01)
    assert consumo_diario_ms(500.0) == pytest.approx(14.0, 0.01)
    assert ugg_de_peso(450.0) == 1.0
    assert ugg_de_peso(225.0) == 0.5

    # 2. Factores de ajuste por lluvia (30 días)
    # Lluvias (>150 mm)
    f_invierno = factor_ajuste_clima(200.0)
    assert f_invierno >= 1.0 and f_invierno <= 1.30
    assert factor_ajuste_clima(150.0) == 1.0

    # Transición (50 - 150 mm)
    f_trans = factor_ajuste_clima(100.0)
    assert f_trans >= 0.65 and f_trans <= 1.0

    # Verano (< 50 mm)
    f_verano = factor_ajuste_clima(20.0)
    assert f_verano >= 0.35 and f_verano < 0.65

    # 3. Capacidad de carga dinámica (UGG/ha)
    # Con aforo 1.5 kg/m2, 33 días rotación, 180 mm lluvia
    carga_lluvia = capacidad_carga_dinamica_ha(1.5, dias_rotacion=33, mm_lluvia_30d=180.0)
    carga_seca = capacidad_carga_dinamica_ha(1.5, dias_rotacion=33, mm_lluvia_30d=20.0)
    assert carga_lluvia > carga_seca
    assert carga_lluvia > 0.0

    # 4. Balance forrajero
    bal_superavit = balance_forrajero_calculo(oferta_neta_ms_total=50000.0, demanda_ms_diaria=500.0, dias_rotacion=33)
    assert bal_superavit["estado"] == "SUPERÁVIT FORRAJERO"
    assert bal_superavit["icono"] == "🟢"
    assert bal_superavit["indice_suficiencia_pct"] > 110.0

    bal_deficit = balance_forrajero_calculo(oferta_neta_ms_total=10000.0, demanda_ms_diaria=800.0, dias_rotacion=33)
    assert bal_deficit["estado"] == "DÉFICIT FORRAJERO"
    assert bal_deficit["icono"] == "🔴"
    assert bal_deficit["indice_suficiencia_pct"] < 90.0


def test_clima_ideam_integracion():
    """Valida la clasificación agroclimática del módulo IDEAM."""
    info_lluvias = ClimaIDEAM.clasificar_estacionalidad(220.0)
    assert "LLUVIAS" in info_lluvias["estacion"]
    assert info_lluvias["dias_reposo_sugeridos"] == 28

    info_seca = ClimaIDEAM.clasificar_estacionalidad(15.0)
    assert "SECA" in info_seca["estacion"]
    assert info_seca["dias_reposo_sugeridos"] == 55

    # Balance agroclimático integral
    bal_agro = ClimaIDEAM.balance_agroclimatico(
        aforo_kg_m2=1.4,
        area_has=40.0,
        num_ugg=35.0,
        mm_30d=160.0,
        dias_rotacion=30,
    )
    assert bal_agro["mm_lluvia_30d"] == 160.0
    assert bal_agro["num_ugg"] == 35.0
    assert bal_agro["demanda_diaria_kg_ms"] == pytest.approx(35.0 * CONSUMO_MS_UGG, 0.1)
    assert bal_agro["carga_sostenible_ugg_ha"] > 0


def test_database_pluviometria_y_aforos(db: Database):
    """Valida la persistencia SQLite de mediciones pluviométricas y aforos históricos."""
    # 1. Registrar lluvias
    id1 = db.registrar_pluviometria(mm_lluvia=25.0, fecha="2026-08-20", estacion_o_sector="Sector Alto")
    id2 = db.registrar_pluviometria(mm_lluvia=40.5, fecha="2026-08-25", estacion_o_sector="Sector Bajo")
    id3 = db.registrar_pluviometria(mm_lluvia=15.0, fecha="2026-08-31", estacion_o_sector="Casa Principal")

    assert id1 > 0 and id2 > 0 and id3 > 0

    # 2. Consultar acumulados
    acum_total = db.acumulado_lluvia(desde="2026-08-01", hasta="2026-08-31")
    assert acum_total == pytest.approx(80.5, 0.01)

    resumen = db.resumen_pluviometrico(hoy=date(2026, 8, 31))
    assert resumen["hoy_mm"] == 15.0
    assert resumen["ultimos_7d_mm"] == pytest.approx(55.5, 0.01)
    assert resumen["ultimos_30d_mm"] == pytest.approx(80.5, 0.01)
    assert "TRANSICIÓN" in resumen["estacion"]

    # 3. Detalle para /deshacer
    det = db.detalle_registro("pluviometria", id1)
    assert det is not None
    assert "Pluviometría: 25.0mm (Sector Alto)" in det["resumen"]

    # 4. Registrar y consultar aforos históricos
    pot_id = db.registrar_potrero(nombre="Potrero La Vega", area_has=8.5)
    af_id = db.registrar_aforo(potrero_id_o_nom=pot_id, aforo_kg_m2=1.65, fecha="2026-08-28")
    assert af_id > 0

    # Potrero debe tener el aforo actualizado
    p_row = db.get_potrero(pot_id)
    assert p_row["aforo_kg_m2"] == pytest.approx(1.65, 0.01)

    hist_af = db.obtener_aforos(potrero_id=pot_id)
    assert len(hist_af) == 1
    assert hist_af[0]["aforo_kg_m2"] == pytest.approx(1.65, 0.01)


def test_nlu_parsing_pluviometria_y_aforo(db: Database):
    """Valida el parsing de eventos pluviométricos y aforos en lenguaje natural."""
    parser = EventParser(hoy=date(2026, 8, 31), use_llm=False)

    # Evento de lluvia
    ev_lluvia = parser.parse("llovió 35 mm hoy en sector bajo")
    assert ev_lluvia.tipo == "pluviometria"
    assert ev_lluvia.datos["mm_lluvia"] == 35.0
    assert ev_lluvia.datos["estacion_o_sector"] == "BAJO"

    ev_lluvia_ayer = parser.parse("pluviometro marco 42.5 mm ayer")
    assert ev_lluvia_ayer.tipo == "pluviometria"
    assert ev_lluvia_ayer.datos["mm_lluvia"] == 42.5
    assert ev_lluvia_ayer.fecha == "2026-08-30"

    # Evento de aforo
    ev_aforo = parser.parse("el aforo del potrero 3 dio 1.45 kg/m2")
    assert ev_aforo.tipo == "aforo"
    assert ev_aforo.datos["aforo_kg_m2"] == 1.45
    assert "3" in str(ev_aforo.datos["potrero"])

    # Preguntas (sin números extraíbles) deben ir a consulta
    ev_preg = parser.parse("¿cuánta lluvia ha caído?")
    assert ev_preg.tipo == "consulta"

    # Procesar con Bot interface
    bot = Bot(db, hoy=date(2026, 8, 31))
    resp_lluvia = bot.procesar_mensaje("llovió 28 mm hoy")
    assert "Registrada lluvia: 28.0 mm" in resp_lluvia

    resp_aforo = bot.procesar_mensaje("aforo potrero bajo dio 1.5 kg/m2")
    assert "Registrado aforo de pasto: 1.5 kg/m²" in resp_aforo


def test_query_engine_consultas_clima_y_balance(db: Database):
    """Valida las respuestas en lenguaje natural de QueryEngine para clima y balance forrajero."""
    # Preparar datos
    db.registrar_pluviometria(mm_lluvia=65.0, fecha="2026-08-25")
    db.registrar_pluviometria(mm_lluvia=45.0, fecha="2026-08-31")

    db.registrar_animal(tag="101", sexo="H", estado="ACTIVO", fecha_nacimiento="2022-01-01")
    db.registrar_pesaje(animal_tag="101", fecha="2026-08-01", peso_kg=480.0)

    db.registrar_potrero(nombre="Potrero 1", area_has=10.0, aforo_kg_m2=1.3)

    qe = QueryEngine(db, hoy=date(2026, 8, 31))

    # Consulta de lluvias
    res_lluvia = qe.responder("¿cuánta lluvia ha caído este mes?")
    assert "REPORTE PLUVIOMÉTRICO" in res_lluvia
    assert "110.0 mm" in res_lluvia or "45.0 mm" in res_lluvia
    assert "Factor Crecimiento Forrajero" in res_lluvia

    # Consulta de balance forrajero
    res_balance = qe.responder("¿cómo está el balance forrajero?")
    assert "BALANCE FORRAJERO" in res_balance
    assert "MATERIA SECA" in res_balance
    assert "Hato Activo" in res_balance
    assert "Índice de Suficiencia" in res_balance


def test_formatters_y_teclados_clima(db: Database):
    """Valida la generación de paneles HTML y teclados interactivos."""
    db.registrar_pluviometria(mm_lluvia=50.0, fecha="2026-08-20")
    db.registrar_animal(tag="201", sexo="H", estado="ACTIVO")
    db.registrar_potrero(nombre="Potrero Norte", area_has=12.0, aforo_kg_m2=1.4)

    # Formatear panel de clima
    panel_clima = formatear_clima_panel(db, hoy=date(2026, 8, 31))
    assert "PLUVIOMETRÍA & CLIMA AGROPECUARIO" in panel_clima
    assert "Acumulado Anual" in panel_clima

    # Formatear balance forrajero
    panel_balance = formatear_balance_forrajero_panel(db, hoy=date(2026, 8, 31))
    assert "BALANCE FORRAJERO" in panel_balance
    assert "Superficie Pasturas" in panel_balance

    # Teclados
    teclado_c = crear_teclado_clima()
    assert len(teclado_c.inline_keyboard) >= 3

    teclado_d = crear_teclado_clima_detalle()
    assert len(teclado_d.inline_keyboard) == 1
