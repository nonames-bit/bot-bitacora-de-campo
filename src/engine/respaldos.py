"""Copias de seguridad de la base (carpeta backups/, la misma que llena
scripts/programador.py a las 03:00).

Se usa desde la PWA (Sistema → Copias, solo OWNER) y desde
scripts/restaurar_backup.sh. Todo pasa por la API de backup de SQLite, que
copia de forma consistente con la app y el bot en marcha: no hace falta
detener nada (con Docker no hay systemctl).

Restaurar reemplaza la base completa por la copia elegida. Antes guarda la
base actual como ``antes_de_restaurar_<fecha_hora>.db`` para poder deshacerlo.

Uso por consola (dentro del contenedor o en el servidor):
    python -m src.engine.respaldos listar
    python -m src.engine.respaldos copiar
    python -m src.engine.respaldos restaurar 2026-09-30
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent

# Nombres que se aceptan: diario (AAAA-MM-DD.db), manual_… y antes_de_restaurar_….
_NOMBRE_VALIDO = re.compile(r"(\d{4}-\d{2}-\d{2}|manual_\d{8}_\d{6}|antes_de_restaurar_\d{8}_\d{6})\.db")


def carpeta() -> Path:
    return Path(os.getenv("BACKUPS_DIR") or RAIZ / "backups")


def ruta_db() -> Path:
    return Path(os.getenv("BITACORA_DB") or RAIZ / "data" / "bitacora.db")


def _tipo(nombre: str) -> str:
    if nombre.startswith("manual_"):
        return "manual"
    if nombre.startswith("antes_de_restaurar_"):
        return "antes_de_restaurar"
    return "diaria"


def listar(dir_backups: Path | None = None) -> list[dict]:
    """Copias guardadas, de la más nueva a la más vieja."""
    d = Path(dir_backups or carpeta())
    try:
        nombres = [n for n in os.listdir(d) if _NOMBRE_VALIDO.fullmatch(n)]
    except OSError:
        return []
    out = []
    for n in nombres:
        try:
            st = (d / n).stat()
        except OSError:
            continue
        out.append({
            "nombre": n,
            "tipo": _tipo(n),
            "fecha": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"),
            "tam_mb": round(st.st_size / (1024 * 1024), 2),
        })
    out.sort(key=lambda x: x["fecha"], reverse=True)
    return out


def ruta_copia(nombre: str, dir_backups: Path | None = None) -> Path:
    """Ruta de una copia por su nombre; ValueError si el nombre no es una
    copia válida o no existe (evita leer archivos fuera de backups/)."""
    if not _NOMBRE_VALIDO.fullmatch(str(nombre or "")):
        raise ValueError("Ese nombre de copia no es válido.")
    ruta = Path(dir_backups or carpeta()) / nombre
    if not ruta.is_file():
        raise ValueError("Esa copia ya no existe en el servidor.")
    return ruta


def _copiar(origen: Path, destino: Path) -> None:
    with sqlite3.connect(origen) as o, sqlite3.connect(destino) as d:
        o.backup(d)


def crear_copia(db_path: Path | str | None = None, dir_backups: Path | None = None,
                prefijo: str = "manual") -> str:
    """Copia la base ahora mismo. Devuelve el nombre del archivo."""
    db = Path(db_path or ruta_db())
    if not db.is_file():
        raise ValueError("No se encontró la base de datos.")
    d = Path(dir_backups or carpeta())
    d.mkdir(parents=True, exist_ok=True)
    # Nunca pisa una copia que ya existe (dos copias en el mismo segundo, o
    # restaurar una "antes_de_restaurar" recién hecha).
    momento = datetime.now()
    nombre = f"{prefijo}_{momento.strftime('%Y%m%d_%H%M%S')}.db"
    while (d / nombre).exists():
        momento += timedelta(seconds=1)
        nombre = f"{prefijo}_{momento.strftime('%Y%m%d_%H%M%S')}.db"
    _copiar(db, d / nombre)
    return nombre


def _es_base_valida(ruta: Path) -> bool:
    try:
        con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        try:
            ok = con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            tiene = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='animales'").fetchone()
            return ok and bool(tiene)
        finally:
            con.close()
    except sqlite3.Error:
        return False


def restaurar(nombre: str, db_path: Path | str | None = None,
              dir_backups: Path | None = None) -> str:
    """Reemplaza la base por la copia ``nombre``. Devuelve el nombre de la
    copia de seguridad de lo que había antes."""
    origen = ruta_copia(nombre, dir_backups)
    if not _es_base_valida(origen):
        raise ValueError("Esa copia está dañada o no es una base de la bitácora; no se restauró.")
    db = Path(db_path or ruta_db())
    seguridad = crear_copia(db, dir_backups, prefijo="antes_de_restaurar")
    _copiar(origen, db)
    # Una copia vieja puede venir sin las tablas o columnas nuevas.
    try:
        from ..db.database import Database
    except ImportError:  # ejecutado como script suelto
        from src.db.database import Database  # type: ignore
    Database(str(db)).create_tables().close()
    return seguridad


def _main(argv: list[str]) -> int:
    orden = argv[1] if len(argv) > 1 else "listar"
    if orden == "listar":
        for c in listar():
            print(f"{c['nombre']:<40} {c['tam_mb']:>8.2f} MB  {c['fecha']}")
        return 0
    if orden == "copiar":
        print(crear_copia())
        return 0
    if orden == "restaurar" and len(argv) > 2:
        nombre = argv[2] if argv[2].endswith(".db") else f"{argv[2]}.db"
        try:
            seguridad = restaurar(nombre)
        except ValueError as e:
            print(f"No se restauró: {e}")
            return 1
        print(f"Restaurado a {nombre}. Lo que había antes quedó en backups/{seguridad}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
