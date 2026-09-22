"""Pruebas unitarias para la emancipación de Software Ganadero:
- Métodos de Condición Corporal
- Métodos de Inventario de Pajuelas/Semen
- Extractor Histórico SG
- Script de Comparación SG vs Bitácora JA
"""
from __future__ import annotations

import os
import pytest

from src.db.database import Database
from src.importers.extractor_historico_sg import extraer_datos_historicos_sg
from scripts.comparar_backup_sg import comparar_sistemas


def test_condicion_corporal_crud():
    db = Database(":memory:")
    db.create_tables()

    db.registrar_animal(tag="VACA01", sexo="Hembra", estado="ACTIVO")
    
    # Registrar CC
    id1 = db.registrar_condicion_corporal(animal_tag="VACA01", fecha="2026-05-10", valor=3.5, notas="Buena CC")
    assert id1 > 0

    # Idempotencia: no duplica el mismo valor en la misma fecha
    id2 = db.registrar_condicion_corporal(animal_tag="VACA01", fecha="2026-05-10", valor=3.5)
    assert id1 == id2

    # Segunda medición posterior
    id3 = db.registrar_condicion_corporal(animal_tag="VACA01", fecha="2026-08-20", valor=3.75)
    assert id3 != id1

    # Última condición corporal
    ult = db.ultima_condicion_corporal("VACA01")
    assert ult is not None
    assert ult["valor"] == 3.75
    assert ult["fecha"] == "2026-08-20"

    # Historial completo
    hist = db.historial_condicion_corporal("VACA01")
    assert len(hist) == 2
    assert hist[0]["valor"] == 3.5
    assert hist[1]["valor"] == 3.75


def test_pajuelas_inventario_crud():
    db = Database(":memory:")
    db.create_tables()

    # Registrar pajuela nueva
    pid1 = db.registrar_pajuela_inventario(
        codigo_toro="TORO-GYR-01",
        raza="GYR",
        procedencia="CRIADERO LA FE",
        canastilla="CAN-01",
        cantidad=15,
        costo=45000.0,
        fecha_ingreso="2026-01-15",
    )
    assert pid1 > 0

    # Actualizar saldo existente (mismo código)
    pid2 = db.registrar_pajuela_inventario(
        codigo_toro="TORO-GYR-01",
        cantidad=12,
        costo=45000.0,
    )
    assert pid1 == pid2

    # Registrar otra con saldo 0
    db.registrar_pajuela_inventario(
        codigo_toro="TORO-HOLSTEIN-02",
        raza="HOLSTEIN",
        cantidad=0,
        costo=35000.0,
    )

    # Listar todas
    todas = db.listar_pajuelas_inventario(solo_con_saldo=False)
    assert len(todas) == 2

    # Listar solo con saldo
    con_saldo = db.listar_pajuelas_inventario(solo_con_saldo=True)
    assert len(con_saldo) == 1
    assert con_saldo[0]["codigo_toro"] == "TORO-GYR-01"
    assert con_saldo[0]["cantidad"] == 12


def test_extractor_historico_y_comparacion_real():
    zip_path = "docs/Datos20260823.Zip"
    if not os.path.isfile(zip_path):
        pytest.skip("No se encontró el backup real docs/Datos20260823.Zip")

    db = Database(":memory:")
    db.create_tables()

    # Extraer histórico sobre base en memoria
    stats = extraer_datos_historicos_sg(db, zip_path)
    assert "condicion_corporal" in stats
    assert stats["condicion_corporal"]["nuevos"] > 500
    assert "produccion_leche" in stats
    assert stats["produccion_leche"]["nuevos"] > 5000
    assert "diagnosticos_gestacion" in stats
    assert stats["diagnosticos_gestacion"]["nuevos"] > 500
    assert "pajuelas_inventario" in stats
    assert stats["pajuelas_inventario"]["nuevos"] > 50

    # Probar comparación
    rep = comparar_sistemas(db, zip_path)
    assert rep["total_activos_sg"] > 0
    assert rep["total_activos_bitacora"] >= 0
    assert "desglose_sexo" in rep
    assert "diferencias_potrero" in rep
