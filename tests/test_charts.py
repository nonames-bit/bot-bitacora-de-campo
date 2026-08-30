"""Pruebas de generación de gráficos (curva de crecimiento) en la ficha del animal
y de los paneles generales de la finca."""
import os
from datetime import date

import pytest

from src.engine.charts import (
    generar_grafico_aforo_potreros,
    generar_grafico_categorias,
    generar_grafico_evolucion_rebano,
    generar_grafico_gmd_hato,
    generar_grafico_iep_boxplot,
    generar_grafico_ocupacion_potreros,
    generar_grafico_peso,
    generar_grafico_peso_destete_por_raza,
    generar_grafico_prenadas_vacias_potrero,
    generar_grafico_rendimiento_padre,
    graficos_disponibles,
)

pytestmark = pytest.mark.skipif(
    not graficos_disponibles(), reason="matplotlib no está instalado en este entorno"
)


def test_generar_grafico_peso_con_datos_suficientes(db, tmp_path):
    db.registrar_animal("47", sexo="Macho", estado="ACTIVO", fecha_nacimiento="2025-01-01")
    db.registrar_pesaje(animal_tag="47", fecha="2025-06-01", peso_kg=150)
    db.registrar_pesaje(animal_tag="47", fecha="2025-09-01", peso_kg=220)

    ruta = generar_grafico_peso(db, "47", output_dir=str(tmp_path))
    assert ruta is not None
    assert os.path.exists(ruta)
    assert ruta.endswith(".png")
    assert os.path.getsize(ruta) > 0


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


# ---------------------------------------------------------------------------
# Gráficos generales de la finca (panel /graficos)
# ---------------------------------------------------------------------------
def _sembrar_hato_basico(db):
    db.registrar_potrero("Norte", tipo_pasto="Brachiaria decumbens", aforo_kg_m2=2.5)
    db.registrar_potrero("Sur", tipo_pasto="Toledo", aforo_kg_m2=3.1)
    db.registrar_animal("T1", sexo="Macho", estado="ACTIVO", nombre="TORO PADRON", fecha_nacimiento="2018-01-01")
    for i in range(6):
        tag = f"V{i}"
        sexo = "Hembra" if i % 2 == 0 else "Macho"
        db.registrar_animal(
            tag, sexo=sexo, estado="ACTIVO", raza="Brahman" if i % 2 == 0 else "Gyr",
            fecha_nacimiento="2024-01-01", potrero="Norte" if i % 2 == 0 else "Sur",
        )
        db.registrar_pesaje(animal_tag=tag, fecha="2025-01-01", peso_kg=150 + i)
        db.registrar_pesaje(animal_tag=tag, fecha="2025-06-01", peso_kg=200 + i, evento="DESTETE")


def test_generar_grafico_evolucion_rebano(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01", sexo_cria="Macho")
    db.registrar_muerte("47", fecha="2026-07-01")
    ruta = generar_grafico_evolucion_rebano(db, meses=6, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_evolucion_rebano_sin_datos_devuelve_none(db, tmp_path):
    assert generar_grafico_evolucion_rebano(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None


def test_generar_grafico_categorias(db, tmp_path):
    _sembrar_hato_basico(db)
    ruta = generar_grafico_categorias(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_categorias_sin_animales_devuelve_none(db, tmp_path):
    assert generar_grafico_categorias(db, output_dir=str(tmp_path)) is None


def test_generar_grafico_gmd_hato(db, tmp_path):
    _sembrar_hato_basico(db)
    ruta = generar_grafico_gmd_hato(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_iep_boxplot_con_suficientes_intervalos(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2024-01-01")
    db.registrar_parto(vaca_tag="47", fecha="2025-01-05")
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="48", fecha="2024-02-01")
    db.registrar_parto(vaca_tag="48", fecha="2025-02-20")
    db.registrar_animal("49", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="49", fecha="2024-03-01")
    db.registrar_parto(vaca_tag="49", fecha="2025-03-15")
    ruta = generar_grafico_iep_boxplot(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_iep_boxplot_sin_suficientes_intervalos_devuelve_none(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2025-01-01")  # un solo parto, sin intervalo
    assert generar_grafico_iep_boxplot(db, output_dir=str(tmp_path)) is None


def test_generar_grafico_peso_destete_por_raza(db, tmp_path):
    _sembrar_hato_basico(db)
    ruta = generar_grafico_peso_destete_por_raza(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_peso_destete_por_raza_sin_destetes_devuelve_none(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", raza="Brahman")
    db.registrar_pesaje(animal_tag="47", fecha="2025-01-01", peso_kg=150, evento="Control")
    assert generar_grafico_peso_destete_por_raza(db, output_dir=str(tmp_path)) is None


def test_generar_grafico_rendimiento_padre(db, tmp_path):
    db.registrar_animal("T1", sexo="Macho", estado="ACTIVO", nombre="Padron")
    db.registrar_animal("C1", sexo="Hembra", estado="ACTIVO", padre_tag="T1")
    db.registrar_animal("C2", sexo="Hembra", estado="ACTIVO", padre_tag="T1")
    db.registrar_parto(vaca_tag="C1", id_cria_tag="C1B", fecha="2025-01-01", peso_nacimiento=30)
    db.registrar_animal("C1B", padre_tag="T1")
    db.registrar_parto(vaca_tag="C2", id_cria_tag="C2B", fecha="2025-02-01", peso_nacimiento=34)
    db.registrar_animal("C2B", padre_tag="T1")
    ruta = generar_grafico_rendimiento_padre(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_rendimiento_padre_sin_datos_devuelve_none(db, tmp_path):
    assert generar_grafico_rendimiento_padre(db, output_dir=str(tmp_path)) is None


def test_generar_grafico_aforo_potreros(db, tmp_path):
    db.registrar_potrero("Norte", tipo_pasto="Brachiaria decumbens", aforo_kg_m2=2.5)
    db.registrar_potrero("Sur", tipo_pasto="Toledo", aforo_kg_m2=3.1)
    ruta = generar_grafico_aforo_potreros(db, output_dir=str(tmp_path))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_aforo_potreros_sin_aforo_devuelve_none(db, tmp_path):
    db.registrar_potrero("Norte")
    assert generar_grafico_aforo_potreros(db, output_dir=str(tmp_path)) is None


def test_generar_grafico_ocupacion_potreros(db, tmp_path):
    p1 = db.registrar_potrero("Norte")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1)
    db.registrar_traslado(animal_tag="47", fecha="2026-08-28", potrero_destino="Norte")
    ruta = generar_grafico_ocupacion_potreros(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_ocupacion_potreros_sin_traslados_devuelve_none(db, tmp_path):
    p1 = db.registrar_potrero("Norte")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1)
    assert generar_grafico_ocupacion_potreros(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None


def test_generar_grafico_prenadas_vacias_potrero(db, tmp_path):
    p1 = db.registrar_potrero("Norte")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2022-01-01")
    db.registrar_servicio(vaca_tag="47", fecha="2026-01-01", fep_calculada="2026-10-08")
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2022-01-01")
    ruta = generar_grafico_prenadas_vacias_potrero(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_prenadas_vacias_potrero_sin_hembras_adultas_devuelve_none(db, tmp_path):
    p1 = db.registrar_potrero("Norte")
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2026-06-01")  # cría
    assert generar_grafico_prenadas_vacias_potrero(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None
