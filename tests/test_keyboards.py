"""Pruebas de construcción de teclados táctiles (InlineKeyboardMarkup)."""
from src.server.keyboards import (
    crear_teclado_alertas_detalle,
    crear_teclado_animal_detalle,
    crear_teclado_buscar_animal,
    crear_teclado_grafico_detalle,
    crear_teclado_graficos,
    crear_teclado_poblacion_detalle,
)


def _tags_botones(teclado):
    return [
        btn.text.split(" ", 1)[-1]
        for fila in teclado.inline_keyboard
        for btn in fila
        if btn.callback_data and btn.callback_data.startswith("ficha:")
    ]


def test_teclado_buscar_animal_sin_consultas_no_muestra_fila_recientes(db):
    teclado = crear_teclado_buscar_animal(db)
    assert _tags_botones(teclado) == []


def test_teclado_buscar_animal_muestra_ultimas_4_consultas_en_orden(db):
    db.registrar_animal("A048", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("A088", sexo="Hembra", estado="ACTIVO")
    db.registrar_consulta_animal("A048", hoy="2026-08-01")
    db.registrar_consulta_animal("A088", hoy="2026-08-02")

    teclado = crear_teclado_buscar_animal(db)
    assert _tags_botones(teclado) == ["A088", "A048"]


def test_teclado_buscar_animal_se_actualiza_al_reconsultar(db):
    db.registrar_animal("A048", sexo="Hembra", estado="ACTIVO")
    db.registrar_animal("A088", sexo="Hembra", estado="ACTIVO")
    db.registrar_consulta_animal("A048", hoy="2026-08-01")
    db.registrar_consulta_animal("A088", hoy="2026-08-02")

    # Se vuelve a consultar A048 más tarde: el panel debe reordenarse.
    db.registrar_consulta_animal("A048", hoy="2026-08-03")
    teclado = crear_teclado_buscar_animal(db)
    assert _tags_botones(teclado) == ["A048", "A088"]


def test_teclado_grafico_detalle_tiene_solo_dos_botones():
    teclado = crear_teclado_grafico_detalle()
    botones = [btn for fila in teclado.inline_keyboard for btn in fila]
    assert len(botones) == 2
    assert botones[0].text == "◀ Volver a Gráficos"
    assert botones[0].callback_data == "cmd:graficos"
    assert botones[1].text == "🏠 Menú Principal"
    assert botones[1].callback_data == "menu:principal"


def test_teclado_animal_detalle_tiene_dos_botones():
    teclado = crear_teclado_animal_detalle("47")
    botones = [btn for fila in teclado.inline_keyboard for btn in fila]
    assert len(botones) == 2
    assert botones[0].text == "◀ Volver a Ficha (47)"
    assert botones[0].callback_data == "ficha:47"
    assert botones[1].text == "🏠 Menú Principal"
    assert botones[1].callback_data == "menu:principal"


def test_teclado_alertas_detalle_tiene_dos_botones():
    teclado = crear_teclado_alertas_detalle()
    botones = [btn for fila in teclado.inline_keyboard for btn in fila]
    assert len(botones) == 2
    assert botones[0].text == "⚠️ Volver a Alertas"
    assert botones[0].callback_data == "cmd:alertas"
    assert botones[1].text == "🏠 Menú Principal"
    assert botones[1].callback_data == "menu:principal"


def test_teclado_poblacion_detalle_tiene_dos_botones():
    teclado = crear_teclado_poblacion_detalle()
    botones = [btn for fila in teclado.inline_keyboard for btn in fila]
    assert len(botones) == 2
    assert botones[0].text == "📊 Volver a Población"
    assert botones[0].callback_data == "cmd:poblacion"
    assert botones[1].text == "🏠 Menú Principal"
    assert botones[1].callback_data == "menu:principal"


def test_teclado_graficos_mantiene_menu_completo():
    teclado = crear_teclado_graficos()
    botones = [btn for fila in teclado.inline_keyboard for btn in fila]
    assert len(botones) > 10
    callbacks = [btn.callback_data for btn in botones]
    assert "panel_grafico:evolucion" in callbacks
    assert "menu:principal" in callbacks


def test_teclado_graficos_organizado_por_4_categorias():
    teclado = crear_teclado_graficos()
    filas = teclado.inline_keyboard
    callbacks = [btn.callback_data for fila in filas for btn in fila]

    # Verifica separadores de encabezado
    assert "noop:hato" in callbacks
    assert "noop:reprod" in callbacks
    assert "noop:pasturas" in callbacks
    assert "noop:leche" in callbacks

    # 1. HATO
    assert "panel_grafico:evolucion" in callbacks
    assert "panel_grafico:waterfall" in callbacks
    assert "panel_grafico:categorias" in callbacks

    # 2. REPRODUCCIÓN
    assert "panel_grafico:gmd" in callbacks
    assert "panel_grafico:iep" in callbacks
    assert "panel_grafico:iep_completo" in callbacks
    assert "panel_grafico:destete_raza" in callbacks
    assert "panel_grafico:padre" in callbacks
    assert "panel_grafico:prenadas" in callbacks
    assert "panel_grafico:dias_abiertos_km" in callbacks
    assert "panel_grafico:reproductivo_hato" in callbacks

    # 3. PASTURAS
    assert "panel_grafico:aforo" in callbacks
    assert "panel_grafico:ocupacion" in callbacks
    assert "panel_grafico:carga_animal" in callbacks

    # 4. LECHE
    assert "panel_grafico:leche_total" in callbacks
    assert "panel_grafico:eficiencia_lechera" in callbacks
    assert "panel_grafico:ranking_leche" in callbacks

    # 5. MENÚ PRINCIPAL
    assert "menu:principal" in callbacks
