"""Pruebas de generación de gráficos (curva de crecimiento) en la ficha del animal."""
import os

import pytest

from src.engine.charts import generar_grafico_peso, graficos_disponibles


@pytest.mark.skipif(not graficos_disponibles(), reason="matplotlib no está instalado en este entorno")
def test_generar_grafico_peso_con_datos_suficientes(db, tmp_path):
    db.registrar_animal("47", sexo="Macho", estado="ACTIVO", fecha_nacimiento="2025-01-01")
    db.registrar_pesaje(animal_tag="47", fecha="2025-06-01", peso_kg=150)
    db.registrar_pesaje(animal_tag="47", fecha="2025-09-01", peso_kg=220)

    ruta = generar_grafico_peso(db, "47", output_dir=str(tmp_path))
    assert ruta is not None
    assert os.path.exists(ruta)
    assert ruta.endswith(".png")
    assert os.path.getsize(ruta) > 0


@pytest.mark.skipif(not graficos_disponibles(), reason="matplotlib no está instalado en este entorno")
def test_generar_grafico_peso_sin_fecha_nacimiento_usa_fechas(db, tmp_path):
    # Sin fecha_nacimiento, el gráfico debe usar la fecha del pesaje en vez
    # de la edad en días, y seguir generando el archivo con normalidad.
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO")
    db.registrar_pesaje(animal_tag="48", fecha="2025-06-01", peso_kg=180)
    db.registrar_pesaje(animal_tag="48", fecha="2025-09-01", peso_kg=230)

    ruta = generar_grafico_peso(db, "48", output_dir=str(tmp_path))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_peso_menos_de_dos_pesajes_devuelve_none(db, tmp_path):
    db.registrar_animal("49", sexo="Macho", estado="ACTIVO")
    db.registrar_pesaje(animal_tag="49", fecha="2025-06-01", peso_kg=150)
    assert generar_grafico_peso(db, "49", output_dir=str(tmp_path)) is None


def test_generar_grafico_peso_animal_inexistente_devuelve_none(db, tmp_path):
    assert generar_grafico_peso(db, "no-existe-999", output_dir=str(tmp_path)) is None
