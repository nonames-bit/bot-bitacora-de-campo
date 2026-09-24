"""Regresión P2.12: el gráfico NDVI debe contar animales por potrero VIGENTE.

Antes `generar_mapa_potreros` agrupaba solo por `animales.potrero_id`, así que un
animal trasladado con `potrero_id` NULL quedaba fuera del gráfico y este
contradecía a Inventario/Mapa/Pasturas (que usan la expresión canónica
`POTRERO_ACTUAL_EXPR`: potrero_id → último traslado si es NULL).
"""
from src.engine.charts import _animales_activos_por_potrero_vigente


def test_conteo_por_potrero_vigente(db):
    pot_a = db.registrar_potrero(nombre="Potrero A", codigo="A")
    pot_b = db.registrar_potrero(nombre="Potrero B", codigo="B")

    # Sin potrero_id (ficha) pero con traslado: debe contar en el destino.
    db.registrar_animal("SIN-FICHA", sexo="Hembra", estado="ACTIVO")
    aid = db.animal_id("SIN-FICHA")
    db.execute(
        "INSERT INTO traslados (animal_id, fecha, potrero_destino) VALUES (?, ?, ?)",
        (aid, "2026-09-01", pot_a),
    )

    # Con potrero_id: manda el estático aunque tenga un traslado viejo a otro.
    db.registrar_animal("EN-B", sexo="Hembra", estado="ACTIVO", potrero=pot_b)
    bid = db.animal_id("EN-B")
    db.execute(
        "INSERT INTO traslados (animal_id, fecha, potrero_destino) VALUES (?, ?, ?)",
        (bid, "2026-01-01", pot_a),
    )

    # Histórico (no ACTIVO): fuera del inventario presente.
    db.registrar_animal("MUERTO-A", sexo="Hembra", estado="MUERTO", potrero=pot_a)

    conteo = _animales_activos_por_potrero_vigente(db)
    assert conteo.get(pot_a) == 1
    assert conteo.get(pot_b) == 1
