"""Pruebas del parser nativo de DBF y del importador a SQLite."""
import os
import struct

import pytest

from src.importers.dbf_importer import (
    DBFReader, import_animales, import_causas, import_celos, import_dbfs,
    import_fotos, import_partos, import_pesajes, import_potreros, import_servicios,
    import_traslados, import_zip,
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
                # Datos en latin-1 (convención DBF), igual que decodifica DBFReader.
                out += str(val).encode("latin-1").rjust(flen, b" ")
            elif ftype == "T":
                # Campo DateTime (8 bytes): día juliano + milisegundos.
                if isinstance(val, tuple):
                    out += struct.pack("<II", val[0], val[1])
                else:
                    out += val
            else:
                out += str(val).encode("latin-1").ljust(flen, b" ")
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
    res = import_potreros(db, [{"CODPOT": "01", "NOMPOT": "Norte", "HAS": 10.0,
                                "KGHA": 5000.0, "PASTO1": "", "TIPO": "L",
                                "FEC_ENT": "2026-01-01", "FEC_SAL": None, "DIA_OCU": 30}])
    assert res == {"nuevos": 1, "duplicados": 0}
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
    assert conteos["animales"] == {"nuevos": 1, "duplicados": 0}
    assert conteos["muertes"] == {"nuevos": 1, "duplicados": 0}
    animal = db.get_animal("47")
    assert animal["sexo"] == "Hembra"
    muerte = db.query_one("SELECT * FROM muertes")
    assert muerte["causa_presunta"] == "ACCIDENTE"


def test_import_animales_estado_desde_tipo(db):
    """El campo TIPO de SG determina el estado del animal (no ESTADO)."""
    base = {"NOMANI": "", "SEXO": "H", "TIPORAZA": "T", "FECNACE": "20200101",
            "CODPOT": "", "ESTADO": "", "OBS": "", "MADRE": "", "PADRE": "",
            "FECMUERTE": "", "CAU": "", "MOTIVO": ""}
    registros = [
        {**base, "CODANI": "1", "TIPO": "V"},
        {**base, "CODANI": "2", "TIPO": "M"},
        {**base, "CODANI": "3", "TIPO": "T"},
        {**base, "CODANI": "4", "TIPO": "O"},
        {**base, "CODANI": "5", "TIPO": ""},
        {**base, "CODANI": "6", "TIPO": "x"},  # desconocido -> ACTIVO
    ]
    import_animales(db, registros, {})
    esperados = {"1": "VENDIDO", "2": "MUERTO", "3": "TRASLADADO",
                 "4": "OTRO", "5": "ACTIVO", "6": "ACTIVO"}
    for tag, estado in esperados.items():
        assert db.get_animal(tag)["estado"] == estado, f"tag {tag}"


def test_import_partos(db):
    res = import_partos(db, [{"CODANI": "47", "FECHA": "2026-05-01", "CRIA": "M",
                              "ABORTO": "", "PESNAC": 35.0, "HIJO": "480", "DETALLE": ""}])
    assert res == {"nuevos": 1, "duplicados": 0}
    parto = db.query_one("SELECT * FROM partos")
    assert parto["sexo_cria"] == "Macho"
    assert parto["estado_cria"] == "VIVO"
    assert db.get_animal("480") is not None


def test_import_partos_ignora_autorreferencia_corrupta(db):
    # Caso donde el DBF corrupto tiene CODANI == HIJO (vaca_tag == cria_tag)
    res = import_partos(db, [{"CODANI": "V009", "FECHA": "2026-03-02", "CRIA": "M",
                              "ABORTO": "", "PESNAC": 33.0, "HIJO": "V009", "DETALLE": "corrupto"}])
    assert res == {"nuevos": 0, "duplicados": 0}
    assert db.count("partos") == 0


def test_import_partos_mismo_dia_con_y_sin_cria_no_colisionan(db):
    # 1. Parto con cría
    r1 = [{"CODANI": "47", "FECHA": "2026-05-01", "CRIA": "M",
           "ABORTO": "", "PESNAC": 35.0, "HIJO": "480", "DETALLE": "con cria"}]
    res1 = import_partos(db, r1)
    assert res1 == {"nuevos": 1, "duplicados": 0}

    # 2. Parto mismo día sin cría (no debe colisionar con el anterior)
    r2 = [{"CODANI": "47", "FECHA": "2026-05-01", "CRIA": "",
           "ABORTO": "S", "PESNAC": 0, "HIJO": "", "DETALLE": "sin cria"}]
    res2 = import_partos(db, r2)
    assert res2 == {"nuevos": 1, "duplicados": 0}

    assert db.count("partos") == 2

    # 3. Re-importar ambos debe dar 0 nuevos y 2 duplicados
    res3 = import_partos(db, r1 + r2)
    assert res3 == {"nuevos": 0, "duplicados": 2}


def test_import_animales_preserva_madre_padre_existentes(db):
    db.registrar_animal(tag="100", sexo="Hembra")
    db.registrar_animal(tag="200", sexo="Macho")
    db.registrar_animal(tag="101", sexo="Hembra")
    db.registrar_animal(tag="201", sexo="Macho")
    db.registrar_animal(tag="50", sexo="Hembra")

    id_50 = db.animal_id("50")
    id_100 = db.animal_id("100")
    id_200 = db.animal_id("200")
    db.execute("UPDATE animales SET madre_id = ?, padre_id = ? WHERE id_animal = ?", (id_100, id_200, id_50))

    import_animales(db, [
        {"CODANI": "50", "NOMANI": "Vaca 50", "SEXO": "H", "TIPORAZA": "T",
         "FECNACE": "20200101", "CODPOT": "01", "ESTADO": "1", "OBS": "",
         "MADRE": "101", "PADRE": "201", "TIPO": "", "FECMUERTE": "",
         "CAU": "", "MOTIVO": ""},
    ], {})

    ani = db.query_one("SELECT madre_id, padre_id FROM animales WHERE tag = '50'")
    assert ani["madre_id"] == id_100
    assert ani["padre_id"] == id_200


def test_import_servicios(db):
    res = import_servicios(db, [{"CODANI": "47", "FECHA": "2026-08-15", "TIPO": "IA",
                                 "TORO": "502", "INSEMINA": "01", "EST": ""}])
    assert res == {"nuevos": 1, "duplicados": 0}
    s = db.query_one("SELECT * FROM servicios")
    assert s["tipo_servicio"] == "IA"
    assert s["toro_pajilla"] == "502"
    assert s["fep_calculada"] == "2027-05-25"


def test_import_pesajes_con_gmd(db):
    res = import_pesajes(db, [
        {"CODANI": "12", "FECHA": "2026-01-01", "PESO": 350.0, "EVENTO": "Control"},
        {"CODANI": "12", "FECHA": "2026-03-11", "PESO": 420.0, "EVENTO": "Control"},
    ])
    assert res == {"nuevos": 2, "duplicados": 0}
    pesajes = db.query("SELECT * FROM pesajes ORDER BY fecha")
    assert len(pesajes) == 2
    assert pesajes[1]["gmd_calculada"] == pytest.approx(70.0 / 69.0, rel=1e-3)


def test_import_celos(db):
    res = import_celos(db, [{"CODANI": "47", "FECHA": "2026-03-01",
                             "HORA": "09:00:00 AM", "DETALLE": ""}])
    assert res == {"nuevos": 1, "duplicados": 0}
    celo = db.query_one("SELECT * FROM celos")
    assert celo["am_pm"] == "AM"


def test_import_traslados(db):
    res = import_traslados(db, [{"CODANI": "47", "FECHA": "2026-06-01", "TIPMOV": "S",
                                 "CODPOT": "01", "LOTE": "2", "REGISTROTR": ""}])
    assert res == {"nuevos": 1, "duplicados": 0}
    tr = db.query_one("SELECT * FROM traslados")
    assert tr["lote"] == "2"


def test_import_doble_deduplicacion_completa(db):
    """Importar dos veces el mismo set de DBFs debe dar en la 2da pasada 0 nuevos y todo duplicados."""
    causas_dbf = build_dbf(
        [("CODIGO", "C", 5, 0), ("DESC", "C", 30, 0)],
        [("19", "ACCIDENTE")],
    )
    potrero_dbf = build_dbf(
        [("CODPOT", "C", 5, 0), ("NOMPOT", "C", 20, 0), ("HAS", "N", 6, 2), ("KGHA", "N", 8, 2),
         ("PASTO1", "C", 10, 0), ("TIPO", "C", 5, 0), ("FEC_ENT", "D", 8, 0), ("FEC_SAL", "D", 8, 0), ("DIA_OCU", "N", 4, 0)],
        [("01", "Norte", 10.0, 5000.0, "Brachiaria", "L", "20260101", "", 30)],
    )
    hoja_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("NOMANI", "C", 20, 0), ("SEXO", "C", 1, 0), ("TIPORAZA", "C", 10, 0),
         ("FECNACE", "D", 8, 0), ("CODPOT", "C", 5, 0), ("ESTADO", "C", 5, 0), ("OBS", "C", 30, 0),
         ("MADRE", "C", 10, 0), ("PADRE", "C", 10, 0), ("TIPO", "C", 1, 0), ("FECMUERTE", "D", 8, 0),
         ("CAU", "C", 5, 0), ("MOTIVO", "C", 30, 0)],
        [("47", "Mariposa", "H", "Cebú", "20200101", "01", "1", "", "", "", "M", "20260507", "19", "accidente")],
    )
    partos_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("CRIA", "C", 1, 0),
         ("ABORTO", "C", 1, 0), ("PESNAC", "N", 6, 2), ("HIJO", "C", 10, 0), ("DETALLE", "C", 30, 0)],
        [("47", "20260501", "M", "", 35.0, "480", "parto normal")],
    )
    celos_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("HORA", "C", 15, 0), ("DETALLE", "C", 30, 0)],
        [("47", "20260301", "09:00:00 AM", "celo detectado")],
    )
    iamn_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("TIPO", "C", 2, 0),
         ("TORO", "C", 10, 0), ("INSEMINA", "C", 10, 0), ("EST", "C", 5, 0)],
        [("47", "20260815", "IA", "502", "01", "")],
    )
    pesos_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("PESO", "N", 6, 2), ("EVENTO", "C", 20, 0)],
        [("47", "20260101", 350.0, "Control"), ("47", "20260311", 420.0, "Control")],
    )
    traslado_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("FECHA", "D", 8, 0), ("TIPMOV", "C", 1, 0),
         ("CODPOT", "C", 5, 0), ("LOTE", "C", 5, 0), ("REGISTROTR", "C", 30, 0)],
        [("47", "20260601", "S", "01", "2", "rotacion")],
    )

    dbf_data = {
        "causas.dbf": causas_dbf,
        "potrero.dbf": potrero_dbf,
        "hoja.dbf": hoja_dbf,
        "partos.dbf": partos_dbf,
        "celos.dbf": celos_dbf,
        "iamn.dbf": iamn_dbf,
        "pesos.dbf": pesos_dbf,
        "traslado.dbf": traslado_dbf,
    }

    # Primera pasada: todo nuevo
    p1 = import_dbfs(db, dbf_data)
    for tabla, res in p1.items():
        assert res["nuevos"] > 0, f"Tabla {tabla} no insertó registros nuevos en pasada 1"
        assert res["duplicados"] == 0, f"Tabla {tabla} reportó duplicados en pasada 1"

    conteo_animales_p1 = db.count("animales")
    conteo_partos_p1 = db.count("partos")
    conteo_celos_p1 = db.count("celos")
    conteo_servicios_p1 = db.count("servicios")
    conteo_pesajes_p1 = db.count("pesajes")
    conteo_traslados_p1 = db.count("traslados")
    conteo_muertes_p1 = db.count("muertes")
    conteo_potreros_p1 = db.count("potreros")

    # Segunda pasada: todo duplicado, cero filas nuevas
    p2 = import_dbfs(db, dbf_data)
    for tabla, res in p2.items():
        assert res["nuevos"] == 0, f"Tabla {tabla} insertó filas nuevas en pasada 2"
        assert res["duplicados"] > 0, f"Tabla {tabla} no contó duplicados en pasada 2"

    # Los conteos en base de datos deben ser exactamente iguales
    assert db.count("animales") == conteo_animales_p1
    assert db.count("partos") == conteo_partos_p1
    assert db.count("celos") == conteo_celos_p1
    assert db.count("servicios") == conteo_servicios_p1
    assert db.count("pesajes") == conteo_pesajes_p1
    assert db.count("traslados") == conteo_traslados_p1
    assert db.count("muertes") == conteo_muertes_p1
    assert db.count("potreros") == conteo_potreros_p1


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
    assert conteos["animales"]["nuevos"] > 0

    # Segunda pasada sobre el mismo archivo zip: cero nuevos
    conteos2 = import_zip(db, zip_path)
    assert conteos2["animales"]["nuevos"] == 0
    assert conteos2["animales"]["duplicados"] > 0


def test_import_zip_registra_en_import_sg_historial(db):
    # Regresión real: no había forma de saber si el bot estaba usando el
    # backup de hoy sin adivinar por la fecha de modificación del archivo
    # .db. import_zip() debe dejar un registro consultable por /sistema
    # cada vez que se importa un backup (manual o por el vigilante).
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(root, "docs", "Datos20260823.Zip")
    if not os.path.exists(zip_path):
        pytest.skip("Archivo de datos DBF no disponible")

    assert db.ultimo_import_sg() is None
    import_zip(db, zip_path)
    ultimo = db.ultimo_import_sg()
    assert ultimo is not None
    assert ultimo["archivo"] == "Datos20260823.Zip"
    assert ultimo["nuevos"] > 0
    assert ultimo["fecha_iso"] is not None


def test_import_fotos_directo_e_idempotente(db, tmp_path):
    import io
    import zipfile

    # Crear ZIP en memoria con fotos simuladas
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a001.jpg", b"fake_jpg_content_1")
        zf.writestr("4145-8.jpg", b"fake_jpg_content_2")
        zf.writestr("subfolder/c99.png", b"fake_png_content_3")
        zf.writestr("ignore.txt", b"not_an_image")
    fotos_zip_bytes = buf.getvalue()

    media_dir = str(tmp_path / "media_test")

    # Primera pasada: 3 fotos nuevas (a001, 4145-8, c99)
    res1 = import_fotos(db, fotos_zip_bytes, media_dir=media_dir)
    assert res1["nuevos"] == 3
    assert res1["duplicados"] == 0
    assert db.count("fotos") == 3

    # Verificar que los archivos existen en disco
    assert os.path.exists(os.path.join(media_dir, "a001.jpg"))
    assert os.path.exists(os.path.join(media_dir, "4145-8.jpg"))
    assert os.path.exists(os.path.join(media_dir, "c99.png"))

    # Verificar tags derivados
    f_a001 = db.query_one("SELECT * FROM fotos WHERE tag = 'a001'")
    assert f_a001 is not None
    assert "a001.jpg" in f_a001["ruta"]

    f_4145 = db.query_one("SELECT * FROM fotos WHERE tag = '4145-8'")
    assert f_4145 is not None
    assert "4145-8.jpg" in f_4145["ruta"]

    # Segunda pasada: 0 nuevos, 3 duplicados
    res2 = import_fotos(db, fotos_zip_bytes, media_dir=media_dir)
    assert res2["nuevos"] == 0
    assert res2["duplicados"] == 3
    assert db.count("fotos") == 3


def test_import_outer_zip_con_fotos_zip(db, tmp_path):
    import io
    import zipfile

    # 1. Crear Dbf.zip interno
    causas_dbf = build_dbf(
        [("CODIGO", "C", 5, 0), ("DESC", "C", 30, 0)],
        [("19", "ACCIDENTE")],
    )
    hoja_dbf = build_dbf(
        [("CODANI", "C", 10, 0), ("NOMANI", "C", 20, 0), ("SEXO", "C", 1, 0), ("TIPORAZA", "C", 10, 0),
         ("FECNACE", "D", 8, 0), ("CODPOT", "C", 5, 0), ("ESTADO", "C", 5, 0), ("OBS", "C", 30, 0),
         ("MADRE", "C", 10, 0), ("PADRE", "C", 10, 0), ("TIPO", "C", 1, 0), ("FECMUERTE", "D", 8, 0),
         ("CAU", "C", 5, 0), ("MOTIVO", "C", 30, 0)],
        [("A001", "Vaca A001", "H", "Brahman", "20200101", "", "1", "", "", "", "", "", "", "")],
    )
    buf_dbf = io.BytesIO()
    with zipfile.ZipFile(buf_dbf, "w") as z_dbf:
        z_dbf.writestr("causas.dbf", causas_dbf)
        z_dbf.writestr("hoja.dbf", hoja_dbf)

    # 2. Crear Fotos.Zip interno
    buf_fotos = io.BytesIO()
    with zipfile.ZipFile(buf_fotos, "w") as z_fotos:
        z_fotos.writestr("a001.jpg", b"jpg_data_a001")
        z_fotos.writestr("4145-8.jpg", b"jpg_data_4145")

    # 3. Crear outer ZIP
    outer_path = str(tmp_path / "BackupCompleto.Zip")
    with zipfile.ZipFile(outer_path, "w") as z_outer:
        z_outer.writestr("Dbf.zip", buf_dbf.getvalue())
        z_outer.writestr("Fotos.Zip", buf_fotos.getvalue())

    media_dir = str(tmp_path / "media_outer")

    # Importar outer zip
    conteos = import_zip(db, outer_path, media_dir=media_dir)
    assert "animales" in conteos
    assert conteos["animales"]["nuevos"] == 1
    assert "fotos" in conteos
    assert conteos["fotos"]["nuevos"] == 2
    assert conteos["fotos"]["duplicados"] == 0

    # Re-importar: todo duplicado
    conteos2 = import_zip(db, outer_path, media_dir=media_dir)
    assert conteos2["animales"]["nuevos"] == 0
    assert conteos2["fotos"]["nuevos"] == 0
    assert conteos2["fotos"]["duplicados"] == 2

