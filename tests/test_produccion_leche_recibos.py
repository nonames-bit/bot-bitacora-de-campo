"""Pruebas unitarias para el módulo de Producción Total Diaria de Leche (recibos y tanque).

Verifica:
1. Aislamiento de datos históricos de SG (2016-2018) para no alterar la producción actual.
2. Cálculo correcto de métricas ejecutivas: total quincena/mes, promedio diario, pico y piso.
3. Generación exitosa del gráfico de producción diaria del hato con línea de promedio.
"""
import os
import sys
from datetime import date
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.db.database import Database
from src.engine.dashboard_data import datos_leche
from src.engine.charts import generar_grafico_leche_total_hato


def test_datos_leche_produccion_diaria_y_aislamiento(tmp_path):
    db_path = str(tmp_path / "test_leche.db")
    db = Database(db_path)
    db.create_tables()

    # 1. Sembrar registros históricos viejos de Software Ganadero (2017)
    db.execute("""
        INSERT INTO produccion_leche (animal_id, fecha, litros, notas) VALUES
        (101, '2017-05-10', 8.5, NULL),
        (102, '2017-05-10', 9.0, NULL),
        (103, '2017-05-10', 7.5, NULL)
    """)

    # 2. Sembrar registros de un recibo de leche moderno (2026) con total diario del hato
    dias_recibo = [
        ('2026-08-16', 350.0),
        ('2026-08-17', 321.0),
        ('2026-08-18', 321.0),
        ('2026-08-19', 288.0),
        ('2026-08-20', 336.0),
        ('2026-08-21', 290.0),
        ('2026-08-22', 321.0),
        ('2026-08-23', 330.0),
        ('2026-08-24', 368.0),  # Pico máximo
        ('2026-08-25', 310.0),
        ('2026-08-26', 276.0),  # Piso mínimo
        ('2026-08-27', 337.0),
        ('2026-08-28', 316.0),
        ('2026-08-29', 350.0),
        ('2026-08-30', 280.0),
        ('2026-08-31', 298.0),
    ]
    for f, l in dias_recibo:
        db.execute(
            "INSERT INTO produccion_leche (animal_id, fecha, litros, notas) VALUES (NULL, ?, ?, ?)",
            (f, l, "Recibo 16 al 31 de Agosto 2026 (16 días)")
        )

    res = datos_leche(db)

    # Verificaciones de serie activa
    serie = res["serie_tanque"]
    assert len(serie) == 16, f"Se esperaban 16 días, se obtuvieron {len(serie)}"
    assert serie[0]["fecha"] == "2026-08-16"
    assert serie[-1]["fecha"] == "2026-08-31"

    # Verificaciones del resumen
    kpis = res["resumen"]
    assert kpis["total_litros"] == 5092.0
    assert kpis["dias"] == 16
    assert kpis["promedio_diario"] == 318.2
    assert kpis["pico_max"]["litros"] == 368.0
    assert kpis["pico_max"]["fecha"] == "2026-08-24"
    assert kpis["piso_min"]["litros"] == 276.0
    assert kpis["piso_min"]["fecha"] == "2026-08-26"

    # Verificación de aislamiento histórico
    assert res["total_historico_sg"] == 3

    # Verificación de gráfico
    ruta_grafico = generar_grafico_leche_total_hato(db, output_dir=str(tmp_path), hoy=date(2026, 9, 1))
    assert ruta_grafico is not None
    assert os.path.exists(ruta_grafico)


if __name__ == "__main__":
    import pytest
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
