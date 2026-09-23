"""Pruebas del motor de datos del Mapa Satelital Interactivo (GeoJSON de
potreros + vigor NDVI/SAR + operarios en vivo)."""
from src.engine.mapa_data import COLORES_NDVI, datos_mapa_finca
from src.gis.sentinel_ndvi import clasificar_ndvi

_WKT_TEST = "POLYGON((-74.07 3.39, -74.06 3.39, -74.06 3.40, -74.07 3.40, -74.07 3.39))"


def _crear_potrero_real(db, nombre: str) -> int:
    pot_id = db.registrar_potrero(nombre=nombre, area_has=10.0)
    db.execute(
        "UPDATE potreros SET geom_wkt_4326 = ?, centroide_lat = 3.395, centroide_lon = -74.065 "
        "WHERE id = ?",
        (_WKT_TEST, pot_id),
    )
    return pot_id


def test_colores_ndvi_calzan_con_las_categorias_reales_de_clasificar_ndvi():
    """Regresión: COLORES_NDVI tenía claves inventadas ("EXCELENTE / DENSO",
    "BUENO / EN CRECIMIENTO", etc.) que no calzaban con ninguna categoría real
    de clasificar_ndvi() -- el mapa caía siempre al color por defecto (verde)
    sin importar el vigor real del potrero. Cada categoría posible debe tener
    su propio color en el diccionario."""
    categorias_posibles = {clasificar_ndvi(v)["categoria"] for v in (0.85, 0.60, 0.40, 0.10)}
    assert categorias_posibles == {"EXCELENTE", "ÓPTIMO / REPOSO", "ESTRÉS / BAJA BIOMASA", "CRÍTICO / SUELO DESNUDO"}
    for cat in categorias_posibles:
        assert cat in COLORES_NDVI, f"Falta color para la categoría real '{cat}'"
    # Las 4 categorías deben tener colores distintos entre sí (si no, el mapa
    # vuelve a verse "todo igual" aunque las claves ya calcen).
    assert len(set(COLORES_NDVI[c] for c in categorias_posibles)) == 4


def test_datos_mapa_finca_diferencia_potreros_por_categoria_ndvi(db):
    p_excelente = _crear_potrero_real(db, "Potrero Excelente")
    p_critico = _crear_potrero_real(db, "Potrero Critico")
    db.registrar_lectura_ndvi(p_excelente, ndvi_promedio=0.85, fuente="Sentinel-2 L2A")
    db.registrar_lectura_ndvi(p_critico, ndvi_promedio=0.10, fuente="Sentinel-2 L2A")

    res = datos_mapa_finca(db)
    props = {f["properties"]["nombre"]: f["properties"] for f in res["potreros_geojson"]["features"]}

    assert props["Potrero Excelente"]["categoria_ndvi"] == "EXCELENTE"
    assert props["Potrero Critico"]["categoria_ndvi"] == "CRÍTICO / SUELO DESNUDO"
    # El punto central del bug: dos potreros con vigor muy distinto deben
    # pintarse con colores distintos, no ambos en el mismo verde por defecto.
    assert props["Potrero Excelente"]["color_ndvi"] != props["Potrero Critico"]["color_ndvi"]


def test_mapa_cuenta_activos_por_potrero_vigente(db):
    """El mapa usa la misma regla que Inventario: potrero_id manda;
    el último traslado solo cubre NULL. Históricos no inflan el conteo."""
    pot_a = _crear_potrero_real(db, "Potrero A")
    pot_b = _crear_potrero_real(db, "Potrero B")

    db.registrar_animal("SIN-FICHA", sexo="Hembra", estado="ACTIVO")
    aid = db.animal_id("SIN-FICHA")
    db.execute(
        "INSERT INTO traslados (animal_id, fecha, potrero_destino) VALUES (?, ?, ?)",
        (aid, "2026-09-01", pot_a),
    )

    db.registrar_animal("EN-B", sexo="Hembra", estado="ACTIVO", potrero=pot_b)
    bid = db.animal_id("EN-B")
    db.execute(
        "INSERT INTO traslados (animal_id, fecha, potrero_destino) VALUES (?, ?, ?)",
        (bid, "2026-01-01", pot_a),
    )

    db.registrar_animal("MUERTO-A", sexo="Hembra", estado="MUERTO", potrero=pot_a)

    res = datos_mapa_finca(db)
    props = {f["properties"]["nombre"]: f["properties"] for f in res["potreros_geojson"]["features"]}
    assert props["Potrero A"]["animales_count"] == 1
    assert props["Potrero A"]["animales_tags"] == ["SIN-FICHA"]
    assert props["Potrero B"]["animales_count"] == 1
    assert props["Potrero B"]["animales_tags"] == ["EN-B"]


def test_datos_mapa_finca_sin_potreros(db):
    res = datos_mapa_finca(db)
    assert res["ok"] is True
    assert res["finca"]["total_potreros"] == 0
    assert res["potreros_geojson"]["features"] == []
