"""Pruebas del módulo de exportación (DBF nativo, CSV, JSON y paquete ZIP)."""
import io
import json
import os
import zipfile
from datetime import date

import pytest

from src.exporters import (
    DBFWriter,
    export_all_dbfs,
    export_causas_dbf,
    export_celos_dbf,
    export_csv_zip,
    export_hoja_dbf,
    export_iamn_dbf,
    export_json_zip,
    export_partos_dbf,
    export_pesos_dbf,
    export_potrero_dbf,
    export_traslado_dbf,
    export_zip,
    parsear_args_exportar,
)
from src.importers.dbf_importer import DBFReader


def test_dbf_writer_roundtrip():
    fields = [
        ("TAG", "C", 10, 0),
        ("PESO", "N", 6, 2),
        ("FECHA", "D", 8, 0),
        ("ACTIVO", "L", 1, 0),
    ]
    w = DBFWriter(fields)
    w.add_record(["VACA-01", 450.5, "2026-08-25", True])
    w.add_record(["TORO-99", 780.0, date(2026, 8, 20), False])

    data = w.write_bytes()
    assert len(data) > 32
    assert data[0] == 0x03  # dBASE III flag

    # Lectura con DBFReader
    reader = DBFReader(data)
    recs = list(reader.records())
    assert len(recs) == 2
    assert recs[0]["TAG"] == "VACA-01"
    assert recs[0]["PESO"] == 450.5
    assert recs[0]["FECHA"] == "2026-08-25"
    assert recs[0]["ACTIVO"] is True

    assert recs[1]["TAG"] == "TORO-99"
    assert recs[1]["PESO"] == 780.0
    assert recs[1]["FECHA"] == "2026-08-20"
    assert recs[1]["ACTIVO"] is False


def test_export_all_dbfs_con_datos(db):
    db.registrar_potrero(nombre="Potrero 1", codigo="P01", area_has=5.5)
    db.registrar_animal("47", nombre="Mariposa", sexo="Hembra", raza="Brahman")
    db.registrar_parto("47", fecha="2026-08-20", sexo_cria="Macho", peso_nacimiento=32.0)
    db.registrar_celo("47", fecha="2026-08-21", am_pm="AM")
    db.registrar_servicio("47", fecha="2026-08-22", tipo_servicio="IA", toro_pajilla="502")
    db.registrar_pesaje("47", fecha="2026-08-23", peso_kg=480.0)
    db.registrar_traslado("47", fecha="2026-08-24", potrero_destino=db.potrero_id("P01"))

    dbfs = export_all_dbfs(db)
    assert len(dbfs) == 8
    for name, raw in dbfs.items():
        assert len(raw) > 32
        reader = DBFReader(raw)
        recs = list(reader.records())
        if name == "hoja.dbf":
            assert len(recs) == 1
            assert recs[0]["CODANI"] == "47"
        elif name == "partos.dbf":
            assert len(recs) == 1
            assert recs[0]["CODANI"] == "47"
            assert recs[0]["PESNAC"] == 32.0


def test_export_zip_software_ganadero_format(tmp_path, db):
    db.registrar_animal("47", nombre="Mariposa", sexo="Hembra")
    db.registrar_parto("47", fecha="2026-08-20", sexo_cria="Macho")

    zip_out = tmp_path / "Datos_Export.Zip"
    resultado = export_zip(db, str(zip_out))

    assert resultado == str(zip_out)
    assert zip_out.exists()

    with zipfile.ZipFile(str(zip_out), "r") as outer:
        assert "Dbf.zip" in outer.namelist()
        inner_bytes = outer.read("Dbf.zip")
        with zipfile.ZipFile(io.BytesIO(inner_bytes), "r") as inner:
            assert "hoja.dbf" in inner.namelist()
            assert "partos.dbf" in inner.namelist()


def test_export_csv_zip(tmp_path, db):
    db.registrar_animal("47", nombre="Mariposa", sexo="Hembra")
    db.registrar_parto("47", fecha="2026-08-20", sexo_cria="Macho")

    zip_out = tmp_path / "bitacora_csv.zip"
    resultado = export_csv_zip(db, str(zip_out))

    assert resultado == str(zip_out)
    assert zip_out.exists()

    with zipfile.ZipFile(str(zip_out), "r") as zf:
        nombres = zf.namelist()
        assert "animales.csv" in nombres
        assert "partos.csv" in nombres
        assert "fotos.csv" in nombres

        animales_csv = zf.read("animales.csv").decode("utf-8-sig")
        assert "47" in animales_csv
        assert "Mariposa" in animales_csv


def test_export_json_zip(tmp_path, db):
    db.registrar_animal("47", nombre="Mariposa", sexo="Hembra")
    db.registrar_parto("47", fecha="2026-08-20", sexo_cria="Macho")

    zip_out = tmp_path / "bitacora_json.zip"
    resultado = export_json_zip(db, str(zip_out))

    assert resultado == str(zip_out)
    assert zip_out.exists()

    with zipfile.ZipFile(str(zip_out), "r") as zf:
        assert "bitacora.json" in zf.namelist()
        content = json.loads(zf.read("bitacora.json").decode("utf-8"))
        assert content["version"] == "1.0"
        assert len(content["tablas"]["animales"]) == 1
        assert content["tablas"]["animales"][0]["tag"] == "47"


def test_parsear_args_exportar():
    assert parsear_args_exportar([]) == ("dbf", "dbf")
    assert parsear_args_exportar(["dbf"]) == ("dbf", "dbf")
    assert parsear_args_exportar(["sg"]) == ("dbf", "dbf")
    assert parsear_args_exportar(["csv"]) == ("csv", "csv")
    assert parsear_args_exportar(["json"]) == ("json", "json")
    assert parsear_args_exportar(["invalido"]) is None
    assert parsear_args_exportar(["csv", "extra"]) is None
