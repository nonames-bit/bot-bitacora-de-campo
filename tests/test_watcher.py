"""Pruebas unitarias para el vigilante automático de copias (CopiasWatcher)."""
from __future__ import annotations

import io
import json
import os
import struct
import time
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from src.db.database import Database
from src.watchers.copias_watcher import (
    CopiasWatcher,
    calcular_hash_archivo,
    formatear_reporte_copias,
)


def _build_dbf_bytes(fields: list[tuple], records: list[list]) -> bytes:
    """Construye un archivo DBF III mínimo en memoria para pruebas."""
    nf = len(fields)
    header_len = 32 + 32 * nf + 1
    record_len = 1 + sum(f[2] for f in fields)
    out = bytearray()
    out += bytes([0x03, 0x52, 0x08, 0x18])
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
        out += b"\x20"
        for (name, ftype, flen, fdec), val in zip(fields, rec):
            if ftype == "N":
                out += str(val).encode("latin-1").rjust(flen, b" ")
            else:
                out += str(val).encode("latin-1").ljust(flen, b" ")
    return bytes(out)


def _crear_zip_sg_prueba(ruta_zip: str, tag_animal: str, nom_animal: str) -> None:
    """Genera un archivo Zip de respaldo SG válido con hoja.dbf y causas.dbf."""
    causas_dbf = _build_dbf_bytes(
        [("CODIGO", "C", 5, 0), ("DESC", "C", 30, 0)],
        [("01", "VEJEZ")],
    )
    hoja_dbf = _build_dbf_bytes(
        [
            ("CODANI", "C", 10, 0),
            ("NOMANI", "C", 20, 0),
            ("SEXO", "C", 1, 0),
            ("TIPORAZA", "C", 10, 0),
            ("FECNACE", "D", 8, 0),
            ("CODPOT", "C", 5, 0),
            ("ESTADO", "C", 5, 0),
            ("OBS", "C", 30, 0),
            ("MADRE", "C", 10, 0),
            ("PADRE", "C", 10, 0),
            ("TIPO", "C", 1, 0),
            ("FECMUERTE", "D", 8, 0),
            ("CAU", "C", 5, 0),
            ("MOTIVO", "C", 30, 0),
        ],
        [
            (tag_animal, nom_animal, "H", "Brahman", "20210101", "01", "1", "", "", "", "", "", "", ""),
        ],
    )

    buf_dbf = io.BytesIO()
    with zipfile.ZipFile(buf_dbf, "w") as z_dbf:
        z_dbf.writestr("causas.dbf", causas_dbf)
        z_dbf.writestr("hoja.dbf", hoja_dbf)

    with zipfile.ZipFile(ruta_zip, "w") as z_outer:
        z_outer.writestr("Dbf.zip", buf_dbf.getvalue())


def test_watcher_simula_dos_zips_con_diferente_mtime(tmp_path):
    """Simula 2 zips generados en momentos distintos y comprueba que solo el nuevo se importa."""
    copias_dir = tmp_path / "copias"
    copias_dir.mkdir()
    db_path = str(tmp_path / "bitacora_test.db")
    state_file = str(copias_dir / ".ultimo_importado")
    log_file = str(tmp_path / "copias_import.log")

    watcher = CopiasWatcher(
        copias_dir=str(copias_dir),
        db_path=db_path,
        state_file=state_file,
        log_file=log_file,
        notify_telegram=False,
    )

    # 1. Crear primer zip (Datos20260823.Zip)
    zip1 = str(copias_dir / "Datos20260823.Zip")
    _crear_zip_sg_prueba(zip1, "A100", "Vaca Primera")
    os.utime(zip1, (1700000000, 1700000000))

    # Primera ejecución: debe importar zip1
    res1 = watcher.verificar_y_procesar()
    assert len(res1) == 1
    assert res1[0]["nombre"] == "Datos20260823.Zip"
    assert res1[0]["exito"] is True
    assert res1[0]["conteos"]["animales"]["nuevos"] == 1

    # Verificar que quedó en base de datos
    db = Database(db_path)
    assert db.count("animales") == 1
    ani1 = db.query_one("SELECT * FROM animales WHERE tag = 'A100'")
    assert ani1 is not None
    assert ani1["nombre"] == "Vaca Primera"
    db.close()

    # Verificar que el log y el estado existen
    assert os.path.exists(log_file)
    assert os.path.exists(state_file)
    estado1 = watcher.leer_estado()
    assert estado1["ultimo_archivo"] == "Datos20260823.Zip"
    assert "Datos20260823.Zip" in estado1["procesados"]

    # 2. Ejecutar sin crear nuevos archivos: no debe re-importar nada
    res_vacio = watcher.verificar_y_procesar()
    assert len(res_vacio) == 0

    # 3. Crear segundo zip con fecha posterior (Datos20260824.Zip)
    zip2 = str(copias_dir / "Datos20260824.Zip")
    _crear_zip_sg_prueba(zip2, "A200", "Vaca Segunda")
    os.utime(zip2, (1700005000, 1700005000))

    # Tercera ejecución: solo debe procesar el nuevo zip2
    res2 = watcher.verificar_y_procesar()
    assert len(res2) == 1
    assert res2[0]["nombre"] == "Datos20260824.Zip"
    assert res2[0]["conteos"]["animales"]["nuevos"] == 1

    # Comprobar que en la base de datos ahora están ambos animales
    db = Database(db_path)
    assert db.count("animales") == 2
    ani2 = db.query_one("SELECT * FROM animales WHERE tag = 'A200'")
    assert ani2 is not None
    assert ani2["nombre"] == "Vaca Segunda"
    db.close()

    # Estado final: contiene ambos zips en el historial
    estado2 = watcher.leer_estado()
    assert estado2["ultimo_archivo"] == "Datos20260824.Zip"
    assert "Datos20260823.Zip" in estado2["procesados"]
    assert "Datos20260824.Zip" in estado2["procesados"]

    # 4. Cuarta ejecución: nada pendiente
    res_final = watcher.verificar_y_procesar()
    assert len(res_final) == 0


def test_watcher_ignora_archivos_incompletos_o_no_zip(tmp_path):
    """Archivos no-zip o archivos temporales incompletos se ignoran sin fallar."""
    copias_dir = tmp_path / "copias"
    copias_dir.mkdir()
    db_path = str(tmp_path / "bitacora_test.db")

    watcher = CopiasWatcher(
        copias_dir=str(copias_dir),
        db_path=db_path,
        notify_telegram=False,
    )

    # Archivo .txt y archivo .zip corrupto/vacío
    (copias_dir / "readme.txt").write_text("no es un zip", encoding="utf-8")
    (copias_dir / "incompleto.zip").write_bytes(b"")

    res = watcher.verificar_y_procesar()
    assert len(res) == 0


def test_watcher_formatear_reportes():
    """Verifica formato de texto plano y HTML del reporte de copias."""
    conteos = {
        "animales": {"nuevos": 2, "duplicados": 10},
        "partos": {"nuevos": 1, "duplicados": 5},
    }
    txt = formatear_reporte_copias(conteos, "Datos20260824.Zip", duracion_s=1.2, modo_html=False)
    assert "IMPORTACIÓN AUTOMÁTICA: Datos20260824.Zip" in txt
    assert "3 nuevos, 15 duplicados" in txt
    assert "• animales: 2 nuevos, 10 duplicados" in txt

    html = formatear_reporte_copias(conteos, "Datos20260824.Zip", duracion_s=1.2, modo_html=True)
    assert "<b>Software Ganadero — Auto-Import Exitoso</b>" in html
    assert "<code>Datos20260824.Zip</code>" in html
    assert "<b>3 nuevos</b>, 15 duplicados" in html


def test_watcher_notificacion_telegram(tmp_path):
    """Verifica la lógica de obtención de destinatarios y envío de mensaje a OWNER."""
    users_file = tmp_path / "users.json"
    users_file.write_text(
        json.dumps([
            {"user_id": 111, "rol": "OWNER", "nombre": "Jaime Dueño"},
            {"user_id": 222, "rol": "TRABAJADOR", "nombre": "Carlos"},
        ]),
        encoding="utf-8",
    )

    watcher = CopiasWatcher(
        copias_dir=str(tmp_path),
        users_file=str(users_file),
        telegram_token="fake_token_123",
        notify_telegram=True,
    )

    owners = watcher.obtener_destinatarios()
    assert owners == [111]

    # Mock urllib.request para verificar envío (soporta context manager)
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        enviados = watcher.enviar_notificacion_telegram("<b>Reporte prueba</b>")
        assert enviados == 1
        assert mock_urlopen.called
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        assert "fake_token_123" in req.full_url
