"""Pruebas del exportador DBF y generación de paquetes compatibles con Software Ganadero."""
import io
import os
import zipfile
import pytest

from src.db.database import Database
from src.exporters.dbf_exporter import (
    DBFWriter,
    export_all_dbfs,
    export_hoja_dbf,
    export_partos_dbf,
    export_celos_dbf,
    export_iamn_dbf,
    export_pesos_dbf,
    export_potrero_dbf,
    export_traslado_dbf,
    export_causas_dbf,
    export_zip,
)
from src.importers.dbf_importer import DBFReader


def test_dbf_writer_basico():
    fields = [
        ("CODANI", "C", 10, 0),
        ("FECHA", "D", 8, 0),
        ("PESO", "N", 6, 2),
    ]
    w = DBFWriter(fields)
    w.add_record(["47", "2026-08-26", 420.5])
    w.add_record(["12", "2026-08-25", 350.0])
    raw = w.write_bytes()

    assert raw.startswith(b"\x03")
    reader = DBFReader(raw)
    assert reader.num_records == 2
    records = list(reader.records())
    assert len(records) == 2
    assert records[0]["CODANI"] == "47"
    assert records[0]["FECHA"] == "2026-08-26"
    assert records[0]["PESO"] == 420.5


def test_export_roundtrip_con_datos_reales(db, tmp_path):
    # Sembrar datos completos en la base SQLite
    db.registrar_potrero("Norte", codigo="01", area_has=10.0, aforo_kg_m2=0.5, dias_ocupacion=3)
    db.registrar_animal("47", nombre="Mariposa", sexo="Hembra", raza="Cebú", potrero="01", estado="ACTIVO")
    db.registrar_animal("101", nombre="Toro Bravo", sexo="Macho", estado="ACTIVO")
    db.registrar_parto("47", fecha="2026-08-20", sexo_cria="Macho", peso_nacimiento=35.0, id_cria_tag="47-1")
    db.registrar_celo("47", fecha="2026-08-22", am_pm="AM")
    db.registrar_servicio("47", fecha="2026-08-23", tipo_servicio="IA", toro_pajilla="BRAHMAN502")
    db.registrar_pesaje("47", fecha="2026-08-24", peso_kg=420.0, evento="Control")
    db.registrar_traslado("47", fecha="2026-08-25", potrero_origen="01", potrero_destino="01", motivo="Rotación")
    db.registrar_muerte("101", fecha="2026-08-26", causa_presunta="ACCIDENTE")

    # 1. Probar exportación individual de cada tabla
    dbf_files = export_all_dbfs(db)
    assert len(dbf_files) == 8

    # Verificar hoja.dbf con DBFReader
    r_hoja = DBFReader(dbf_files["hoja.dbf"])
    recs_hoja = list(r_hoja.records())
    tags = [r["CODANI"] for r in recs_hoja]
    assert "47" in tags
    assert "101" in tags
    # 101 debe tener TIPO='M' y fecha de muerte
    rec_101 = next(r for r in recs_hoja if r["CODANI"] == "101")
    assert rec_101["TIPO"] == "M"
    assert rec_101["FECMUERTE"] == "2026-08-26"

    # Verificar partos.dbf
    r_partos = DBFReader(dbf_files["partos.dbf"])
    recs_partos = list(r_partos.records())
    assert len(recs_partos) == 1
    assert recs_partos[0]["CODANI"] == "47"
    assert recs_partos[0]["CRIA"] == "M"

    # Verificar iamn.dbf
    r_iamn = DBFReader(dbf_files["iamn.dbf"])
    recs_iamn = list(r_iamn.records())
    assert len(recs_iamn) == 1
    assert recs_iamn[0]["TORO"] == "BRAHMAN502"

    # 2. Probar export_zip completo
    out_zip = str(tmp_path / "Datos_Export_Test.Zip")
    zip_path = export_zip(db, out_zip)
    assert os.path.exists(zip_path)
    assert os.path.getsize(zip_path) > 500

    # Verificar estructura interna: ZIP externo -> Dbf.zip interno -> 8 tablas .dbf
    with zipfile.ZipFile(zip_path, "r") as outer:
        assert "Dbf.zip" in outer.namelist()
        inner_data = outer.read("Dbf.zip")
        with zipfile.ZipFile(io.BytesIO(inner_data), "r") as inner:
            inner_names = inner.namelist()
            for expected in ["hoja.dbf", "partos.dbf", "celos.dbf", "iamn.dbf", "pesos.dbf", "potrero.dbf", "traslado.dbf", "causas.dbf"]:
                assert expected in inner_names
                content = inner.read(expected)
                assert len(content) > 32
