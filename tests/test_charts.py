"""Pruebas de generación de gráficos (curva de crecimiento) en la ficha del animal
y de los paneles generales de la finca."""
import os
from datetime import date

import pytest

from src.engine.charts import (
    _calcular_ieps,
    _kaplan_meier,
    generar_grafico_aforo_potreros,
    generar_grafico_carga_animal_potrero,
    generar_grafico_categorias,
    generar_grafico_dias_abiertos_km,
    generar_grafico_eficiencia_lechera,
    generar_grafico_estado_reproductivo_hato,
    generar_grafico_evolucion_rebano,
    generar_grafico_gmd_hato,
    generar_grafico_iep_boxplot,
    generar_grafico_iep_boxplot_completo,
    generar_grafico_lactancia,
    generar_grafico_leche_total_hato,
    generar_grafico_ocupacion_potreros,
    generar_grafico_peso,
    generar_grafico_peso_destete_por_raza,
    generar_grafico_prenadas_vacias_potrero,
    generar_grafico_ranking_vacas_leche,
    generar_grafico_rendimiento_padre,
    generar_grafico_waterfall_inventario,
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


def _sembrar_ieps_con_hueco_de_registro(db):
    """3 vacas con intervalo normal (~370-390 días) + 1 vaca con un hueco de
    registro real: se importó del Software Ganadero un historial con años sin
    cargar partos intermedios, así que entre dos partos reales de la misma
    vaca queda un intervalo "fantasma" de varios años. Reproduce el reporte
    real del usuario (boxplot con outliers de miles de días)."""
    for i, tag in enumerate(["47", "48", "49"]):
        db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO")
        db.registrar_parto(vaca_tag=tag, fecha=f"2024-0{i + 1}-01")
        db.registrar_parto(vaca_tag=tag, fecha=f"2025-0{i + 1}-10")
    db.registrar_animal("HUECO", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="HUECO", fecha="2017-01-01")
    db.registrar_parto(vaca_tag="HUECO", fecha="2025-06-01")  # ~3070 días de hueco, no un IEP real


def test_calcular_ieps_incluye_todos_los_intervalos_sin_filtrar(db):
    _sembrar_ieps_con_hueco_de_registro(db)
    ieps = _calcular_ieps(db)
    assert len(ieps) == 4
    assert max(ieps) > 3000


def test_generar_grafico_iep_boxplot_excluye_huecos_de_registro_por_defecto(db, tmp_path):
    # Regresión real: el usuario reportó que el boxplot de IEP salía
    # dominado por outliers de miles de días porque no se llevaban
    # registros completos años atrás y se retomó este año. Por defecto,
    # intervalos de más de 2 años (730 días) se excluyen del boxplot por
    # ser casi con certeza huecos de registro, no vacas realmente atípicas.
    _sembrar_ieps_con_hueco_de_registro(db)
    ruta = generar_grafico_iep_boxplot(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_iep_boxplot_umbral_none_no_filtra(db, tmp_path):
    _sembrar_ieps_con_hueco_de_registro(db)
    ruta = generar_grafico_iep_boxplot(
        db, output_dir=str(tmp_path), hoy=date(2026, 8, 30), umbral_max_dias=None
    )
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_iep_boxplot_completo_equivale_a_umbral_none(db, tmp_path):
    _sembrar_ieps_con_hueco_de_registro(db)
    ruta = generar_grafico_iep_boxplot_completo(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


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


# ---------------------------------------------------------------------------
# Waterfall de inventario mensual
# ---------------------------------------------------------------------------
def test_generar_grafico_waterfall_inventario(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-03-01", sexo_cria="Macho")
    db.registrar_animal("48", sexo="Macho", estado="ACTIVO")
    db.registrar_muerte("48", fecha="2026-06-01")
    ruta = generar_grafico_waterfall_inventario(db, meses=8, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_waterfall_inventario_sin_datos_devuelve_none(db, tmp_path):
    assert generar_grafico_waterfall_inventario(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None


# ---------------------------------------------------------------------------
# Días abiertos: curva de Kaplan-Meier
# ---------------------------------------------------------------------------
def test_kaplan_meier_todo_eventos_llega_a_cero():
    # 4 vacas, todas servidas (evento) en distintos tiempos: la supervivencia
    # debe llegar exactamente a 0 al final (todas "salieron" de abiertas).
    obs = [(30, True), (60, True), (90, True), (120, True)]
    tiempos, supervivencia = _kaplan_meier(obs)
    assert tiempos[0] == 0 and supervivencia[0] == 1.0
    assert supervivencia[-1] == pytest.approx(0.0, abs=1e-9)
    assert tiempos == sorted(tiempos)
    assert all(0.0 <= s <= 1.0 for s in supervivencia)


def test_kaplan_meier_con_censura_no_llega_a_cero():
    # Una vaca censurada (todavía abierta) nunca "sale" del riesgo como
    # evento, así que la supervivencia no debe caer a 0 solo por ella.
    obs = [(30, True), (60, True), (200, False)]
    _tiempos, supervivencia = _kaplan_meier(obs)
    assert supervivencia[-1] > 0.0


def test_generar_grafico_dias_abiertos_km(db, tmp_path):
    for i in range(6):
        tag = f"V{i}"
        db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO")
        db.registrar_parto(vaca_tag=tag, fecha=f"2026-0{(i % 6) + 1}-01")
        if i % 2 == 0:
            db.registrar_servicio(vaca_tag=tag, fecha=f"2026-0{(i % 6) + 1}-20")
    ruta = generar_grafico_dias_abiertos_km(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_dias_abiertos_km_pocos_datos_devuelve_none(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01")
    assert generar_grafico_dias_abiertos_km(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None


# ---------------------------------------------------------------------------
# Curva de lactancia individual (litros/día vs días en leche)
# ---------------------------------------------------------------------------
def test_generar_grafico_lactancia(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01")
    db.registrar_leche("47", fecha="2026-06-08", litros=10.0)
    db.registrar_leche("47", fecha="2026-06-15", litros=12.0)
    ruta = generar_grafico_lactancia(db, "47", output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_lactancia_con_promedio_del_hato(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01")
    db.registrar_leche("47", fecha="2026-06-08", litros=10.0)
    db.registrar_leche("47", fecha="2026-06-15", litros=12.0)
    for i in range(3):
        tag = f"V{i}"
        db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO")
        db.registrar_parto(vaca_tag=tag, fecha="2026-05-01")
        db.registrar_leche(tag, fecha="2026-05-08", litros=9.0 + i)
        db.registrar_leche(tag, fecha="2026-05-15", litros=11.0 + i)
    ruta = generar_grafico_lactancia(db, "47", output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_lactancia_menos_de_dos_controles_devuelve_none(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_parto(vaca_tag="47", fecha="2026-06-01")
    db.registrar_leche("47", fecha="2026-06-08", litros=10.0)
    assert generar_grafico_lactancia(db, "47", output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None


def test_generar_grafico_lactancia_sin_parto_devuelve_none(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_leche("47", fecha="2026-06-08", litros=10.0)
    db.registrar_leche("47", fecha="2026-06-15", litros=12.0)
    assert generar_grafico_lactancia(db, "47", output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None


def test_generar_grafico_lactancia_animal_inexistente_devuelve_none(db, tmp_path):
    assert generar_grafico_lactancia(db, "no-existe-999", output_dir=str(tmp_path)) is None


# ---------------------------------------------------------------------------
# Producción de leche del hato (agregada): total, eficiencia, ranking
# ---------------------------------------------------------------------------
def _sembrar_leche_semanal(db, semanas=3, vacas=3):
    from datetime import timedelta
    for i in range(vacas):
        tag = f"V{i}"
        db.registrar_animal(tag, sexo="Hembra", estado="ACTIVO")
        for s in range(semanas):
            f = date(2026, 6, 1) + timedelta(weeks=s)
            db.registrar_leche(tag, fecha=f.isoformat(), litros=10.0 + i + s)


def test_generar_grafico_leche_total_hato(db, tmp_path):
    _sembrar_leche_semanal(db)
    ruta = generar_grafico_leche_total_hato(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_leche_total_hato_sin_datos_devuelve_none(db, tmp_path):
    assert generar_grafico_leche_total_hato(db, output_dir=str(tmp_path)) is None


def test_generar_grafico_eficiencia_lechera(db, tmp_path):
    _sembrar_leche_semanal(db)
    ruta = generar_grafico_eficiencia_lechera(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_ranking_vacas_leche(db, tmp_path):
    _sembrar_leche_semanal(db)
    ruta = generar_grafico_ranking_vacas_leche(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_ranking_vacas_leche_pocas_vacas_devuelve_none(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO")
    db.registrar_leche("47", fecha="2026-06-01", litros=10.0)
    assert generar_grafico_ranking_vacas_leche(db, output_dir=str(tmp_path)) is None


# ---------------------------------------------------------------------------
# Estado reproductivo agregado del hato
# ---------------------------------------------------------------------------
def test_generar_grafico_estado_reproductivo_hato(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2022-01-01")
    db.registrar_servicio(vaca_tag="47", fecha="2026-01-01", fep_calculada="2026-10-08")
    db.registrar_animal("48", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2022-01-01")
    ruta = generar_grafico_estado_reproductivo_hato(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_estado_reproductivo_hato_sin_expuestas_devuelve_none(db, tmp_path):
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", fecha_nacimiento="2022-01-01")
    assert generar_grafico_estado_reproductivo_hato(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None


# ---------------------------------------------------------------------------
# Carga animal por hectárea (UGG/ha)
# ---------------------------------------------------------------------------
def test_generar_grafico_carga_animal_potrero(db, tmp_path):
    p1 = db.registrar_potrero("Norte", area_has=5.0)
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2022-01-01")
    db.registrar_pesaje(animal_tag="47", fecha="2026-08-01", peso_kg=450)
    ruta = generar_grafico_carga_animal_potrero(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30))
    assert ruta is not None
    assert os.path.exists(ruta)


def test_generar_grafico_carga_animal_potrero_sin_area_devuelve_none(db, tmp_path):
    p1 = db.registrar_potrero("Norte")  # sin area_has
    db.registrar_animal("47", sexo="Hembra", estado="ACTIVO", potrero=p1, fecha_nacimiento="2022-01-01")
    assert generar_grafico_carga_animal_potrero(db, output_dir=str(tmp_path), hoy=date(2026, 8, 30)) is None
