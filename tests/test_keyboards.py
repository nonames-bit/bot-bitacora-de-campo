"""Pruebas de construcción de teclados táctiles (InlineKeyboardMarkup)."""
from src.server.keyboards import crear_teclado_buscar_animal


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
