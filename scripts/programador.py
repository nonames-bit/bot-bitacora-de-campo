"""Tareas programadas de la Bitácora dentro de Docker (reemplaza el cron del VPS).

Corre en el servicio ``tareas`` de docker-compose.yml. Cada tarea es un
comando con su horario (hora de la finca, TZ del contenedor):

- 03:00 todos los días   respaldo local de la base (30 días de rotación)
- 06:00 todos los días   precios de mercado
- 06:00 cada 3 días      NDVI satelital
- 06:05 los lunes        lluvia satelital (CHIRPS)

Sin dependencias nuevas: un bucle que revisa el reloj cada 30 s y ejecuta
cada tarea como máximo una vez por día programado.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [tareas] %(message)s")
log = logging.getLogger("tareas")

RAIZ = Path(__file__).resolve().parent.parent
DB = Path(os.getenv("BITACORA_DB", RAIZ / "data" / "bitacora.db"))
BACKUPS = Path(os.getenv("BACKUPS_DIR", RAIZ / "backups"))
DIAS_BACKUP = int(os.getenv("BACKUPS_DIAS", "30"))


def respaldo_local() -> None:
    """Copia consistente de SQLite (API de backup) y rotación."""
    if not DB.exists():
        log.warning("Base %s no existe; respaldo omitido", DB)
        return
    BACKUPS.mkdir(parents=True, exist_ok=True)
    destino = BACKUPS / f"{date.today().isoformat()}.db"
    with sqlite3.connect(DB) as origen, sqlite3.connect(destino) as copia:
        origen.backup(copia)
    limite = time.time() - DIAS_BACKUP * 86400
    for f in BACKUPS.glob("*.db"):
        if f.stat().st_mtime < limite:
            f.unlink()
    log.info("Respaldo local listo: %s", destino)


def script(nombre: str):
    def _correr() -> None:
        r = subprocess.run([sys.executable, str(RAIZ / "scripts" / nombre)], cwd=RAIZ,
                           capture_output=True, text=True, timeout=3600)
        salida = (r.stdout or "")[-2000:] + (r.stderr or "")[-2000:]
        log.info("%s terminó con código %s\n%s", nombre, r.returncode, salida.strip())
    return _correr


# (nombre, hora, minuto, condición sobre la fecha, función)
TAREAS = [
    ("respaldo_local", 3, 0, lambda d: True, respaldo_local),
    ("precios_mercado", 6, 0, lambda d: True, script("actualizar_precios_mercado.py")),
    ("ndvi_satelital", 6, 0, lambda d: d.toordinal() % 3 == 0, script("actualizar_ndvi_satelital.py")),
    ("lluvia_satelital", 6, 5, lambda d: d.weekday() == 0, script("actualizar_lluvia_satelital.py")),
]


def pendientes(ahora: datetime, hechas: dict[str, date]) -> list:
    """Tareas cuya hora ya pasó hoy (dentro de 1 h) y que no han corrido hoy."""
    out = []
    for nombre, h, m, cond, fn in TAREAS:
        programada = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
        if (cond(ahora.date()) and hechas.get(nombre) != ahora.date()
                and programada <= ahora < programada + timedelta(hours=1)):
            out.append((nombre, fn))
    return out


def main() -> None:
    log.info("Programador iniciado (%d tareas)", len(TAREAS))
    hechas: dict[str, date] = {}
    while True:
        ahora = datetime.now()
        for nombre, fn in pendientes(ahora, hechas):
            hechas[nombre] = ahora.date()
            try:
                fn()
            except Exception:
                log.exception("La tarea %s falló", nombre)
        time.sleep(30)


if __name__ == "__main__":
    main()
