"""Pruebas del parser nativo de DBF y del importador a SQLite."""
import os
import struct

import pytest

from src.importers.dbf_importer import (
    DBFReader, import_animales, import_causas, import_celos, import_partos,
    import_pesajes, import_potreros, import_servicios, import_traslados,
    import_zip,
)


def build_dbf(fields, records):
    """Construye un archivo DBF III mínimo en memoria."""
    nf = len(fields)
    header_len = 32 + 32 * nf + 1
    record_len = 1 + sum(f[2] for f in fields)
    out = bytearray()
    out += bytes([0x03, 0x52, 0x08, 0x18])  # versión + fecha (irrelevante)
    out += struct.pack("<I", len(records))
    out += struct.pack("<H", header_len)
    out += struct.pack("<H", record_len)
    out += b"\x00" * 20
    for (name, ftype, flen, fdec) in fields:
        out += name.encode("ascii").ljust(11, b"\x00")
        out += ftype.encode("ascii")
        out += b"\x00" * 4
        out += bytes([flen, fdec])
        out += b"\x00" * 14
    out += b"\x0d"
    for rec in records:
        out += b"\x20"  # registro activo
        for (name, ftype, flen, fdec), val in zip(fields, rec):
            if ftype == "N":
                out += str(val).encode("ascii").rjust(flen, b" ")
            elif ftype == "T":
                # Campo DateTime (8 bytes): día juliano + milisegundos.
                if isinstance(val, tuple):
                    out += struct.pack("<II", val[0], val[1])
                else:
                    out += val
            else:
                out += str(val).encode("ascii").ljust(flen, b" ")
    return bytes(out)


# ---------------------------------------------------------------------------
# Parser nativo DBF
# ---------------------------------------------------------------------------
def test_dbf_reader_campos_y_registros():
    data = build_dbf(
        [("CODANI", "C", 5, 0), ("FECHA", "D", 8, 0), ("PESO", "N", 6, 2)],
        [("47", "20260815", "420.50"), ("48", "20260816", "350")],
    )
    reader = DBFReader(data)
    assert reader.field_names == ["CODANI", "FECHA", "PESO"]
    recs = list(reader.records())
    assert len(recs) == 2
    assert recs[0]["CODANI"] == "47"
    assert recs[0]["FECHA"] == "2026-08-15"
    assert recs[0]["PESO"] == 420.5
    assert recs[1]["PESO"] == 350.0


def test_dbf_datetime_julian():
    """Campo ``T`` (DateTime VFP): día juliano astronómico a fecha ISO."""
    from datetime import date
    jd = date(2000, 1, 1).toordinal() + 1721425  # 2451545 == 2000-01-01
    assert jd == 2451545
    data = build_dbf(
        [("DTCREA", "T", 8, 0)],
        [((jd, 0),)],
    )
    reader = DBFReader(data)
    recs = list(reader.records())
    assert len(recs) == 1
    assert recs[0]["DTCREA"] == "2000-01-01"


# ---------------------------------------------------------------------------
# Mapeo de tablas (registros sintéticos como dicts)
# ---------------------------------------------------------------------------
def test_import_causas(db):
    causas = import_causas(db, [{"CODIGO": "19", "DESC": "ACCIDENTE", "TIPO": "D"}])
    assert causas == {"19": "ACCIDENTE"}


def test_import_potreros(db):
    import_potreros(db, [{"CODPOT": "01", "NOMPOT": "Norte", "HAS": 10.0,
                          "KGHA": 5000.0, "PASTO1": "", "TIPO": "L",
                          "FEC_ENT": "2026-01-01", "FEC_SAL": None, "DIA_OCU": 30}])
    pot = db.query_one("SELECT * FROM potreros WHERE codigo = '01'")
    assert pot is not None
    assert pot["area_has"] == 10.0
    assert pot["aforo_kg_m2"] == pytest.approx(0.5)
    # 2ª Ley de Voisin: DIA_OCU es ocupación (no reposo).
    assert pot["dias_ocupacion"] == 30
    # 1ª Ley de Voisin: sin fecha de salida no hay reposo acumulado.
    assert pot["dias_reposo"] is None


def test_import_animales_y_muertes(db):
    causas = {"19": "ACCIDENTE"}
    conteos = import_animales(db, [
        {"CODANI": "47", "NOMANI": "Mariposa", "SEXO": "H", "TIPORAZA": "T",
         "FECNACE": "20200101", "CODPOT": "01", "ESTADO": "1", "OBS": "",
         "MADRE": "", "PADRE": "", "TIPO": "M", "FECMUERTE": "20260507",
         "CAU": "19", "MOTIVO": "se rodo"},
    ], causas)
    assert conteos["animales"] == 1
    assert conteos["muertes"] == 1
    animal = db.get_animal("47")
    assert animal["sexo"] == "Hembra"
    muerte = db.query_one("SELECT * FROM muertes")
    assert muerte["causa_presunta"] == "ACCIDENTE"


def test_import_partos(db):
    import_partos(db, [{"CODANI": "47", "FECHA": "2026-05-01", "CRIA": "M",
                        "ABORTO": "", "PESNAC": 35.0, "HIJO": "480", "DETALLE": ""}])
    parto = db.query_one("SELECT * FROM partos")
    assert parto["sexo_cria"] == "Macho"
    assert parto["estado_cria"] == "VIVO"
    assert db.get_animal("480") is not None


def test_import_servicios(db):
    import_servicios(db, [{"CODANI": "47", "FECHA": "2026-08-15", "TIPO": "IA",
                           "TORO": "502", "INSEMINA": "01", "EST": ""}])
    s = db.query_one("SELECT * FROM servicios")
    assert s["tipo_servicio"] == "IA"
    assert s["toro_pajilla"] == "502"
    assert s["fep_calculada"] == "2027-05-25"


def test_import_pesajes_con_gmd(db):
    import_pesajes(db, [
        {"CODANI": "12", "FECHA": "2026-01-01", "PESO": 350.0, "EVENTO": "Control"},
        {"CODANI": "12", "FECHA": "2026-03-11", "PESO": 420.0, "EVENTO": "Control"},
    ])
    pesajes = db.query("SELECT * FROM pesajes ORDER BY fecha")
    assert len(pesajes) == 2
    assert pesajes[1]["gmd_calculada"] == pytest.approx(70.0 / 69.0, rel=1e-3)


def test_import_celos(db):
    import_celos(db, [{"CODANI": "47", "FECHA": "2026-03-01",
                       "HORA": "09:00:00 AM", "DETALLE": ""}])
    celo = db.query_one("SELECT * FROM celos")
    assert celo["am_pm"] == "AM"


def test_import_traslados(db):
    import_traslados(db, [{"CODANI": "47", "FECHA": "2026-06-01", "TIPMOV": "S",
                           "CODPOT": "01", "LOTE": "2", "REGISTROTR": ""}])
    tr = db.query_one("SELECT * FROM traslados")
    assert tr["lote"] == "2"


# ---------------------------------------------------------------------------
# Importación del Zip real (se omite si el archivo no está presente)
# ---------------------------------------------------------------------------
def test_import_zip_real(db):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(root, "docs", "Datos20260823.Zip")
    if not os.path.exists(zip_path):
        pytest.skip("Archivo de datos DBF no disponible")
    conteos = import_zip(db, zip_path)
    assert db.count("animales") > 0
    assert db.count("partos") > 0
    assert "animales" in conteos
