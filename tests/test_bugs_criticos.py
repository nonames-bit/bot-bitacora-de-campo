"""Pruebas de regresión para 4 bugs críticos de auditoría."""
import builtins
import io
import logging
import os
import zipfile

from src.importers.dbf_importer import import_fotos, import_zip


def test_bug1_segundo_servicio_ia_sin_stock_no_lanza_y_loguea(db, caplog):
    db.registrar_pajuela(codigo_toro="BUG1TORO", cantidad=1)
    with caplog.at_level(logging.WARNING, logger="src.db.database"):
        s1 = db.registrar_servicio(vaca_tag="V-BUG1A", fecha="2026-08-01",
                                   tipo_servicio="IA", toro_pajilla="BUG1TORO")
        assert isinstance(s1, int)
        assert db.obtener_pajuela("BUG1TORO")["cantidad"] == 0
        caplog.clear()
        s2 = db.registrar_servicio(vaca_tag="V-BUG1B", fecha="2026-08-01",
                                   tipo_servicio="IA", toro_pajilla="BUG1TORO")
        assert isinstance(s2, int)
    assert db.obtener_pajuela("BUG1TORO")["cantidad"] == 0
    textos = " ".join(r.getMessage() for r in caplog.records).lower()
    assert "pajuela" in textos


def test_bug2_create_tables_tolera_fallo_marcar_historicos(db, caplog, monkeypatch):
    def _romper():
        raise RuntimeError("fallo simulado historicos")

    monkeypatch.setattr(db, "marcar_historicos_sg", _romper)
    with caplog.at_level(logging.ERROR, logger="src.db.database"):
        db.create_tables()  # no debe propagar
    textos = " ".join(r.getMessage() for r in caplog.records)
    assert "marcar_historicos_sg" in textos


def test_bug3_fotos_corruptas_reportan_error(db, tmp_path):
    res = import_fotos(db, b"esto no es un zip", media_dir=str(tmp_path / "m1"))
    assert res.get("error"), "bytes corruptos deben reportar 'error'"
    assert res.get("nuevos", 0) == 0
    assert db.count("fotos") == 0


def test_bug3_import_zip_con_fotos_zip_corrupta(db, tmp_path):
    import struct

    def _dbf(fields, records):
        nf = len(fields)
        hl = 32 + 32 * nf + 1
        rl = 1 + sum(f[2] for f in fields)
        out = bytearray()
        out += bytes([0x03, 0x52, 0x08, 0x18])
        out += struct.pack("<I", len(records))
        out += struct.pack("<H", hl)
        out += struct.pack("<H", rl)
        out += b"\x00" * 20
        for (name, ftype, flen, fdec) in fields:
            out += name.encode("ascii").ljust(11, b"\x00")
            out += ftype.encode("ascii")
            out += b"\x00" * 4
            out += bytes([flen, fdec])
            out += b"\x00" * 14
        out += b"\x0d"
        for rec in records:
            out += b"\x20"
            for (name, ftype, flen, fdec), val in zip(fields, rec, strict=False):
                out += str(val).encode("latin-1").ljust(flen, b" ")
        return bytes(out)

    hoja = _dbf(
        [("CODANI", "C", 10, 0), ("NOMANI", "C", 20, 0), ("SEXO", "C", 1, 0),
         ("TIPORAZA", "C", 10, 0), ("FECNACE", "D", 8, 0), ("CODPOT", "C", 5, 0),
         ("ESTADO", "C", 5, 0), ("OBS", "C", 30, 0), ("MADRE", "C", 10, 0),
         ("PADRE", "C", 10, 0), ("TIPO", "C", 1, 0), ("FECMUERTE", "D", 8, 0),
         ("CAU", "C", 5, 0), ("MOTIVO", "C", 30, 0)],
        [("ZX01", "Vaca ZX", "H", "Brahman", "20200101", "", "1", "", "", "", "", "", "", "")],
    )
    buf_dbf = io.BytesIO()
    with zipfile.ZipFile(buf_dbf, "w") as z:
        z.writestr("hoja.dbf", hoja)
    outer = str(tmp_path / "BackupBug3.Zip")
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("Dbf.zip", buf_dbf.getvalue())
        z.writestr("Fotos.Zip", b"bytes corruptos que no son zip")
    conteos = import_zip(db, outer, media_dir=str(tmp_path / "media_bug3"))
    assert conteos["animales"]["nuevos"] == 1
    assert "fotos" in conteos
    assert conteos["fotos"].get("error"), "Fotos.Zip corrupta debe reportar 'error'"


def test_bug4_escritura_foto_fallida_no_deja_fantasma(db, tmp_path, monkeypatch):
    media_dir = str(tmp_path / "media_bug4")
    os.makedirs(media_dir, exist_ok=True)
    real_open = builtins.open

    def _open_falla(file, mode="r", *a, **k):
        if isinstance(file, (str, os.PathLike)) and "wb" in str(mode):
            raise OSError("disco lleno simulado")
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", _open_falla)
    res = import_fotos(db, {"VFANTASMA.jpg": b"datos-fake"}, media_dir=media_dir)
    assert (res.get("errores", 0) > 0) or res.get("error")
    assert db.query_one("SELECT * FROM fotos WHERE tag = 'VFANTASMA'") is None
    assert db.count("fotos") == 0
