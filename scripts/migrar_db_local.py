"""Aplica la migración idempotente del proyecto a la DB local desactualizada.

Diagnóstico
-----------
La DB local ``data/bitacora.db`` fue creada con el código de fases anteriores
y contiene las tablas base (animales, partos, servicios, celos, pesajes,
fotos, potreros, traslados, etc.), pero NO contiene las tablas añadidas en
las fases 5.1/6.2/8.2:

    diagnosticos_gestacion, pajuelas_inventario, termo_nitrogeno,
    recordatorios_programados, pluviometria, aforos_historico,
    monitoreo_satelital_ndvi

Estas tablas están definidas en ``src/db/models.py`` dentro de ``SCHEMA_SQL``
con ``CREATE TABLE IF NOT EXISTS`` y solo se materializan cuando el bot
ejecuta ``Database.create_tables()`` en el arranque (``src/main.py``,
``src/server/telegram_bot.py``, ``src/watchers/copias_watcher.py``). Como la
DB local no se ha vuelto a abrir con el código actual, las tablas nuevas
nunca se crearon.

Solución (sin tocar el código fuente)
-------------------------------------
Este script ejecuta EXACTAMENTE el esquema y las migraciones definidas en el
código del proyecto (``SCHEMA_SQL`` de ``models.py`` + los ``ALTER TABLE``
idempotentes de columnas que ``create_tables()`` aplica), sobre
``data/bitacora.db``. NO se usa el saneamiento de datos de ``create_tables()``
(borrado de partos autorreferenciados / marcado de históricos SG) porque esa
DB ya está saneada y el requisito es no alterar ningún dato existente.

La operación es estrictamente ADITIVA e idempotente:
- ``CREATE TABLE IF NOT EXISTS`` (tablas nuevas) y ``CREATE INDEX IF NOT
  EXISTS`` no tocan ninguna fila existente.
- ``ALTER TABLE ... ADD COLUMN`` solo agrega columnas si no existen.
Por lo tanto los conteos de las tablas existentes y los 344 ACTIVO se
mantienen intactos.

Verificación
------------
Al terminar imprime:
  1. Presencia de las 7 tablas nuevas.
  2. Conteos de las tablas existentes ANTES vs DESPUÉS (deben coincidir:
     animales 1123, partos 611, servicios 837, pesajes 1360, fotos 347,
     potreros 57, traslados 208, celos 856, produccion_leche 0).
  3. Animales con estado='ACTIVO' (deben seguir siendo 344).
  4. Resultado de ``PRAGMA integrity_check``.

Uso
---
    python scripts/migrar_db_local.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Ejecución directa desde scripts/: python scripts/migrar_db_local.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "bitacora.db"

# Tablas nuevas esperadas tras la migración (definidas en models.py).
TABLAS_NUEVAS = [
    "diagnosticos_gestacion",
    "pajuelas_inventario",
    "termo_nitrogeno",
    "recordatorios_programados",
    "pluviometria",
    "aforos_historico",
    "monitoreo_satelital_ndvi",
]

# Tablas de eventos que reciben las columnas de auditoría (migración
# idempotente de create_tables() en database.py).
TABLAS_EVENTOS = (
    "partos", "muertes", "servicios", "celos", "tratamientos",
    "traslados", "pesajes", "movimientos", "condicion_corporal",
    "produccion_leche", "diagnosticos_gestacion", "pluviometria",
    "aforos_historico", "monitoreo_satelital_ndvi",
)

# Conteos de referencia de la DB local antes de migrar (no deben cambiar).
CONTEOS_REFERENCIA = {
    "animales": 1123,
    "partos": 611,
    "servicios": 837,
    "pesajes": 1360,
    "fotos": 347,
    "potreros": 57,
    "traslados": 208,
    "celos": 856,
    "produccion_leche": 0,
}

ACTIVOS_REFERENCIA = 344


def _conteos(conn: sqlite3.Connection) -> dict[str, int]:
    """Snapshot de conteos de las tablas de referencia."""
    return {
        tabla: conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        for tabla in CONTEOS_REFERENCIA
    }


def _tablas(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def aplicar_migracion(conn: sqlite3.Connection) -> None:
    """Aplica el esquema y migraciones del proyecto, solo parte aditiva.

    Usa el SCHEMA_SQL real de ``src/db/models.py`` (no inventa esquemas) y
    las mismas migraciones idempotentes de columnas que ejecuta
    ``Database.create_tables()`` en database.py.
    """
    from src.db.models import SCHEMA_SQL  # import diferido (depende del root)

    # 1) Esquema completo del proyecto: CREATE TABLE IF NOT EXISTS + índices.
    conn.executescript(SCHEMA_SQL)

    # 2) Migración idempotente de columnas (igual que create_tables()):
    #    columna ocr_text en fotos.
    cols_fotos = [r[1] for r in conn.execute("PRAGMA table_info(fotos)").fetchall()]
    if "ocr_text" not in cols_fotos:
        conn.execute("ALTER TABLE fotos ADD COLUMN ocr_text TEXT")

    # 3) Columnas de auditoría en las tablas de eventos.
    for tabla in TABLAS_EVENTOS:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tabla})").fetchall()]
        if "creado_en" not in cols:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN creado_en TEXT")
        if "registrado_por" not in cols:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN registrado_por INTEGER")

    conn.commit()


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] No existe la DB local: {DB_PATH}")
        return 1

    # --- 1. Estado previo -------------------------------------------------- #
    conn = sqlite3.connect(DB_PATH)
    tablas_antes = _tablas(conn)
    conteos_antes = _conteos(conn)
    activos_antes = conn.execute(
        "SELECT COUNT(*) FROM animales WHERE estado = 'ACTIVO'"
    ).fetchone()[0]
    conn.close()

    faltaban = [t for t in TABLAS_NUEVAS if t not in tablas_antes]
    print(f"[1/4] Tablas nuevas faltantes antes de migrar: {len(faltaban)}")
    for t in faltaban:
        print(f"      - {t}")

    # --- 2. Migración aditiva (esquema + columnas del propio proyecto) ---- #
    conn = sqlite3.connect(DB_PATH)
    try:
        aplicar_migracion(conn)
        conn.close()
    except Exception as exc:  # pragma: no cover - defensivo
        print(f"[ERROR] Falló la migración: {exc}")
        try:
            conn.close()
        except Exception:
            pass
        return 1
    print("[2/4] Migración aplicada: SCHEMA_SQL (models.py) + ALTERs idempotentes")

    # --- 3. Verificación posterior ----------------------------------------- #
    conn = sqlite3.connect(DB_PATH)
    tablas_despues = _tablas(conn)
    conteos_despues = _conteos(conn)
    activos_despues = conn.execute(
        "SELECT COUNT(*) FROM animales WHERE estado = 'ACTIVO'"
    ).fetchone()[0]

    faltan_tras = [t for t in TABLAS_NUEVAS if t not in tablas_despues]
    integridad = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()

    print("[3/4] Verificación de tablas nuevas:")
    for t in TABLAS_NUEVAS:
        presente = "OK " if t in tablas_despues else "FALTA"
        print(f"      [{presente}] {t}")
    if faltan_tras:
        print(f"[ERROR] Siguen faltando tablas: {faltan_tras}")

    print("[4/4] Conteos de tablas existentes (antes -> después):")
    conteos_ok = True
    for tabla, antes in conteos_antes.items():
        despues = conteos_despues[tabla]
        ok = antes == despues
        conteos_ok = conteos_ok and ok
        if ok:
            print(f"      [OK ] {tabla}: {antes} -> {despues}")
        else:
            print(f"      [CAMBIÓ] {tabla}: {antes} -> {despues}")
            conteos_ok = False

    activos_ok = activos_antes == activos_despues == ACTIVOS_REFERENCIA
    print(f"      [{'OK ' if activos_ok else 'CAMBIÓ'}] animales ACTIVO: "
          f"{activos_antes} -> {activos_despues} (referencia {ACTIVOS_REFERENCIA})")

    integridad_ok = integridad == "ok"
    print(f"[INTEGRIDAD] PRAGMA integrity_check: {integridad}")

    exito = (not faltan_tras) and conteos_ok and activos_ok and integridad_ok
    print(f"\nRESULTADO: {'MIGRACION CORRECTA' if exito else 'REVISAR'}")
    return 0 if exito else 2


if __name__ == "__main__":
    sys.exit(main())
