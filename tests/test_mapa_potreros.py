"""Pruebas del mapa visual de potreros (NDVI + animales + días de ocupación).

Solo valida el contrato de la función (devuelve una imagen cuando hay
potreros con geometría real, `None` cuando no hay ninguno) — el contenido
visual exacto (colores, posición de etiquetas) se revisa a ojo con datos
reales, no con aserciones automáticas."""
import os

import pytest

from src.engine.charts import generar_mapa_potreros, graficos_disponibles

pytestmark = pytest.mark.skipif(
    not graficos_disponibles(), reason="matplotlib no está instalado en este entorno"
)

_WKT_TEST = "POLYGON((-74.07 3.39, -74.06 3.39, -74.06 3.40, -74.07 3.40, -74.07 3.39))"


def _crear_potrero_real(db, nombre: str, dias_ocupacion=None, dias_reposo=None) -> int:
    pot_id = db.registrar_potrero(nombre=nombre, area_has=10.0,
                                  dias_ocupacion=dias_ocupacion, dias_reposo=dias_reposo)
    db.execute(
        "UPDATE potreros SET geom_wkt_4326 = ?, centroide_lat = 3.395, centroide_lon = -74.065 "
        "WHERE id = ?",
        (_WKT_TEST, pot_id),
    )
    return pot_id


def test_mapa_potreros_sin_geometria_devuelve_none(db, tmp_path):
    db.registrar_potrero(nombre="Potrero Sin Mapear", area_has=5.0)
    ruta = generar_mapa_potreros(db, output_dir=str(tmp_path))
    assert ruta is None


def test_mapa_potreros_con_datos_genera_imagen(db, tmp_path):
    pot_ocupado = _crear_potrero_real(db, "Potrero Ocupado", dias_ocupacion=2)
    pot_vacio = _crear_potrero_real(db, "Potrero En Reposo", dias_reposo=20)

    db.registrar_lectura_ndvi(potrero_id_o_nom=pot_ocupado, ndvi_promedio=0.74, fecha="2026-08-31")
    db.registrar_lectura_ndvi(potrero_id_o_nom=pot_vacio, ndvi_promedio=0.31, fecha="2026-08-31")

    db.registrar_animal("47", sexo="Macho", estado="ACTIVO", potrero=pot_ocupado)

    ruta = generar_mapa_potreros(db, output_dir=str(tmp_path))
    assert ruta is not None
    assert os.path.exists(ruta)
    assert ruta.endswith(".png")
