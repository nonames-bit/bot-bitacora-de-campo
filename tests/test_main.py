"""Pruebas del punto de entrada CLI (src/main.py)."""
import builtins
import zipfile

import pytest

from src.main import main


def _input_no_deberia_llamarse(*args, **kwargs):
    pytest.fail(
        "main() entró al modo interactivo (input()) en vez de terminar solo. "
        "Esto cuelga para siempre cuando se invoca por SSH no interactivo "
        "(ej. el vigilante de copias de Software Ganadero)."
    )


def test_importar_solo_termina_sin_entrar_a_modo_interactivo(tmp_path, monkeypatch):
    # Regresión real: `python -m src.main --db ... --importar archivo.zip`
    # (el modo exacto que usa scripts/importar_backup.sh, invocado por SSH
    # desde el vigilante de copias en Windows) hacía la importación
    # correctamente pero después caía al modo interactivo de abajo y se
    # quedaba bloqueado en input() para siempre -- el import ya había
    # terminado, pero el proceso remoto nunca salía, dejando colgado tanto
    # el script de Windows como el proceso en el VPS.
    monkeypatch.setattr(builtins, "input", _input_no_deberia_llamarse)

    zip_path = tmp_path / "vacio.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("nada.txt", "sin tablas dbf reconocibles")

    db_path = tmp_path / "test.db"
    resultado = main(["--db", str(db_path), "--importar", str(zip_path)])
    assert resultado == 0


def test_exportar_solo_termina_sin_entrar_a_modo_interactivo(tmp_path, monkeypatch):
    monkeypatch.setattr(builtins, "input", _input_no_deberia_llamarse)

    db_path = tmp_path / "test.db"
    out_path = tmp_path / "export.zip"
    resultado = main(["--db", str(db_path), "--exportar", str(out_path)])
    assert resultado == 0


def test_importar_y_texto_juntos_procesa_texto_no_modo_interactivo(tmp_path, monkeypatch):
    monkeypatch.setattr(builtins, "input", _input_no_deberia_llamarse)

    zip_path = tmp_path / "vacio.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("nada.txt", "sin tablas dbf reconocibles")

    db_path = tmp_path / "test.db"
    resultado = main(["--db", str(db_path), "--importar", str(zip_path), "--texto", "N069"])
    assert resultado == 0
