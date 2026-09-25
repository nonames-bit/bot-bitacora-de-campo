"""Pruebas para el sistema de composición genética y cruces absorbentes.

Dominio: Finca > Reproducción & Inseminación, Genética y Trazabilidad.
Reglas:
- Fracciones zootécnicas: 50% -> 1/2, 75% -> 3/4, 87.5% -> 7/8, 93.75% -> 15/16, 96.87% -> PC, 100% -> Puro
- Cruces absorbentes: herencia 50% madre + 50% padre.
  Ej: Vaca 3/4 Gyr + 1/4 Holstein cruzada con Toro Brahman Puro
      -> Cría: 50% Brahman + 37.5% Gyr + 12.5% Holstein.
"""
from __future__ import annotations

import pytest
from src.db.database import Database
from src.engine.genetic_engine import (
    calcular_cruce_absorbente,
    formatear_raza_etiqueta,
    generar_resumen_zootecnico,
    normalizar_nombre_raza,
    parsear_texto_raza,
    porcentaje_a_fraccion,
)
from src.pwa.app import crear_app


def test_traduccion_fracciones_zootecnicas():
    """Valida los decimales estándar de la industria ganadera solicitados por el usuario."""
    assert porcentaje_a_fraccion(50.0) == "1/2"
    assert porcentaje_a_fraccion(75.0) == "3/4"
    assert porcentaje_a_fraccion(87.5) == "7/8"
    assert porcentaje_a_fraccion(93.75) == "15/16"
    assert porcentaje_a_fraccion(96.87) == "Puro por Cruce (PC)"
    assert porcentaje_a_fraccion(96.875) == "Puro por Cruce (PC)"
    assert porcentaje_a_fraccion(100.0) == "Puro"
    assert porcentaje_a_fraccion(62.5) == "5/8"
    assert porcentaje_a_fraccion(37.5) == "3/8"
    assert porcentaje_a_fraccion(25.0) == "1/4"
    assert porcentaje_a_fraccion(12.5) == "1/8"
    assert porcentaje_a_fraccion(6.25) == "1/16"
    assert porcentaje_a_fraccion(3.125) == "1/32"
    assert porcentaje_a_fraccion(40.0) == "40%"


def test_cruce_absorbente_ejemplo_usuario():
    """Valida el ejemplo zootécnico exacto provisto por el usuario:
    Vaca 3/4 Gyr (75%) + 1/4 Holstein (25%) cruzada con Toro Brahman puro (100%).
    Resultado esperado: 50% Brahman, 37.5% Gyr, 12.5% Holstein.
    """
    vaca = [
        {"raza": "Gyr", "porcentaje": 75.0},
        {"raza": "Holstein", "porcentaje": 25.0},
    ]
    toro = [
        {"raza": "Brahman", "porcentaje": 100.0},
    ]

    cria = calcular_cruce_absorbente(vaca, toro)
    resumen = generar_resumen_zootecnico(cria)

    # 3 registros en el resultado
    assert len(cria) == 3

    # Ordenados descendentemente por porcentaje
    assert cria[0]["raza"] == "Brahman"
    assert cria[0]["porcentaje"] == 50.0
    assert cria[0]["fraccion"] == "1/2"

    assert cria[1]["raza"] == "Gyr"
    assert cria[1]["porcentaje"] == 37.5
    assert cria[1]["fraccion"] == "3/8"

    assert cria[2]["raza"] == "Holstein"
    assert cria[2]["porcentaje"] == 12.5
    assert cria[2]["fraccion"] == "1/8"

    # Suma exacta 100%
    assert sum(c["porcentaje"] for c in cria) == 100.0
    assert resumen == "1/2 Brahman + 3/8 Gyr + 1/8 Holstein"


def test_cruce_f1_dos_razas_puras():
    """Valida el cruce entre dos razas puras (F1)."""
    madre = [{"raza": "Brahman", "porcentaje": 100.0}]
    padre = [{"raza": "Romosinuano", "porcentaje": 100.0}]

    cria = calcular_cruce_absorbente(madre, padre)
    assert len(cria) == 2
    razas = {c["raza"]: c["porcentaje"] for c in cria}
    assert razas["Brahman"] == 50.0
    assert razas["Romosinuano"] == 50.0
    assert any("F1" in c["fraccion"] or c["fraccion"] == "1/2" for c in cria)


def test_parsear_texto_raza():
    """Valida el parser de cadenas compuestas."""
    p1 = parsear_texto_raza("3/4 Gyr + 1/4 Holstein")
    assert len(p1) == 2
    assert p1[0]["raza"] == "Gyr"
    assert p1[0]["porcentaje"] == 75.0
    assert p1[1]["raza"] == "Holstein"
    assert p1[1]["porcentaje"] == 25.0

    p2 = parsear_texto_raza("50% Brahman y 50% Romosinuano")
    assert len(p2) == 2
    assert p2[0]["porcentaje"] == 50.0
    assert p2[1]["porcentaje"] == 50.0

    p3 = parsear_texto_raza("Brahman")
    assert len(p3) == 1
    assert p3[0]["raza"] == "Brahman"
    assert p3[0]["porcentaje"] == 100.0


def test_db_guardar_y_obtener_composicion(tmp_path):
    """Valida el almacenamiento estructurado en la tabla composicion_racial y retrocompatibilidad de animales.raza."""
    db_file = tmp_path / "test_genetica.db"
    db = Database(str(db_file)).create_tables()

    aid = db.registrar_animal("VACA-10", sexo="Hembra")
    composicion = [
        {"raza": "Brahman", "porcentaje": 50.0},
        {"raza": "Romosinuano", "porcentaje": 50.0},
    ]

    ok = db.guardar_composicion_racial(aid, composicion)
    assert ok is True

    # Verificar lectura estructurada
    comp_db = db.obtener_composicion_racial(aid)
    assert len(comp_db) == 2
    assert comp_db[0]["raza"] in ("Brahman", "Romosinuano")
    assert comp_db[0]["porcentaje"] == 50.0
    assert comp_db[1]["porcentaje"] == 50.0

    # Verificar que animales.raza se actualizó con la cadena resumen
    an = db.get_animal(aid)
    assert "1/2" in an["raza"]
    assert "Brahman" in an["raza"]
    assert "Romosinuano" in an["raza"]


def test_db_parto_herencia_cruce_absorbente(tmp_path):
    """Valida que al registrar un parto, la cría herede la composición de madre y padre automáticamente."""
    db_file = tmp_path / "test_parto_genetica.db"
    db = Database(str(db_file)).create_tables()

    # Madre: 3/4 Gyr + 1/4 Holstein
    vaca_id = db.registrar_animal("VACA-GYR", sexo="Hembra")
    db.guardar_composicion_racial(vaca_id, [
        {"raza": "Gyr", "porcentaje": 75.0},
        {"raza": "Holstein", "porcentaje": 25.0},
    ])

    # Padre: Toro Brahman puro (100%)
    toro_id = db.registrar_animal("TORO-BRA", sexo="Macho", raza="Brahman")
    db.guardar_composicion_racial(toro_id, [
        {"raza": "Brahman", "porcentaje": 100.0},
    ])

    # Registrar parto de la vaca con ese toro
    parto_id = db.registrar_parto(
        vaca_tag="VACA-GYR",
        fecha="2026-05-10",
        sexo_cria="Hembra",
        id_cria_tag="CRIA-01",
        padre_tag="TORO-BRA",
    )
    assert parto_id is not None

    # Verificar que la cría fue creada y tiene la composición calculada
    cria_row = db.get_animal("CRIA-01")
    assert cria_row is not None

    comp_cria = db.obtener_composicion_racial("CRIA-01")
    assert len(comp_cria) == 3
    dict_comp = {c["raza"]: c["porcentaje"] for c in comp_cria}
    assert dict_comp["Brahman"] == 50.0
    assert dict_comp["Gyr"] == 37.5
    assert dict_comp["Holstein"] == 12.5

    # animales.raza de la cría
    assert cria_row["raza"] == "1/2 Brahman + 3/8 Gyr + 1/8 Holstein"


def test_api_rest_genetica(tmp_path):
    """Valida los endpoints REST de composición y simulación."""
    db_file = tmp_path / "test_api_genetica.db"
    db = Database(str(db_file)).create_tables()

    vaca_id = db.registrar_animal("V01", sexo="Hembra")
    toro_id = db.registrar_animal("T01", sexo="Macho", raza="Brahman")

    app = crear_app(str(db_file), password="clave-de-prueba")
    app.config.update({"TESTING": True})
    client = app.test_client()
    client.post("/login", data={"password": "clave-de-prueba"})

    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["rol"] = "OWNER"

    # 1. Guardar composición manual vía POST
    resp_post = client.post("/api/animal/V01/composicion", json={
        "composicion": [
            {"raza": "Brahman", "porcentaje": 50.0},
            {"raza": "Romosinuano", "porcentaje": 50.0},
        ]
    })
    assert resp_post.status_code == 200
    data_post = resp_post.get_json()
    assert data_post["ok"] is True
    assert len(data_post["composicion"]) == 2

    # 2. Consultar composición vía GET
    resp_get = client.get("/api/animal/V01/composicion")
    assert resp_get.status_code == 200
    data_get = resp_get.get_json()
    assert data_get["ok"] is True
    assert len(data_get["composicion"]) == 2

    # 3. Simular cruce
    resp_sim = client.get("/api/genetica/simular-cruce?madre=V01&padre=T01")
    assert resp_sim.status_code == 200
    data_sim = resp_sim.get_json()
    assert data_sim["ok"] is True
    assert data_sim["cria_resumen"] != ""

    # 4. Catálogo de razas
    resp_cat = client.get("/api/genetica/catalogo-razas")
    assert resp_cat.status_code == 200
    data_cat = resp_cat.get_json()
    assert "Brahman" in data_cat["razas"]
    assert "Romosinuano" in data_cat["razas"]
