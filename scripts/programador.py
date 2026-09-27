"""Tareas programadas de la Bitácora dentro de Docker (reemplaza el cron del VPS).

Corre en el servicio ``tareas`` de docker-compose.yml. Cada tarea es un
comando con su horario (hora de la finca, TZ del contenedor):

- 03:00 todos los días   respaldo local de la base (30 días de rotación)
- 06:00 todos los días   precios de mercado
- 06:00 cada 3 días      NDVI satelital
- 06:05 los lunes        lluvia satelital (CHIRPS)
- cada 15 min            alerta de salud por Telegram a los OWNER (reemplaza
                         scripts/healthcheck_vps.sh, que dependía de systemd)

Sin dependencias nuevas: un bucle que revisa el reloj cada 30 s y ejecuta
cada tarea como máximo una vez por día programado.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib import parse, request

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


# ---------------------------------------------------------------------------
# Alerta de salud
# ---------------------------------------------------------------------------
SALUD_MINUTOS = int(os.getenv("SALUD_MINUTOS", "15"))
URL_APP = os.getenv("SALUD_URL_APP", "http://app:8080/login")
LATIDO_BOT = Path(os.getenv("BOT_LATIDO", DB.parent / ".latido_bot"))
USERS_FILE = Path(os.getenv("USERS_FILE", RAIZ / "data" / "users.json"))


def _responde(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=10) as r:  # noqa: S310 - URL de configuración propia
            return r.status == 200
    except Exception:
        return False


def _horas_desde(*rutas: Path) -> float | None:
    mtimes = [r.stat().st_mtime for r in rutas if r.exists()]
    return (time.time() - max(mtimes)) / 3600 if mtimes else None


def revisar_salud() -> dict[str, str]:
    """Problemas actuales: {clave: mensaje}. Vacío si todo está bien."""
    problemas: dict[str, str] = {}
    if not _responde(URL_APP):
        problemas["app"] = "🔴 La aplicación (PWA) no responde dentro del servidor."
    dominio = os.getenv("DOMINIO", "").strip()
    if dominio and not _responde(f"https://{dominio}/login"):
        problemas["https"] = f"🔴 La PWA no responde desde internet (https://{dominio})."
    if os.getenv("TELEGRAM_TOKEN"):
        h = _horas_desde(LATIDO_BOT)
        if h is None or h > 0.25:
            problemas["bot"] = "🔴 El bot de Telegram no da señales de vida hace más de 15 min."
    try:
        uso = shutil.disk_usage(DB.parent)
        pct = round(uso.used * 100 / uso.total)
        if pct >= 90:
            problemas["disco"] = f"⚠️ Disco del servidor al {pct}%."
    except OSError:
        pass
    h = _horas_desde(DB, Path(f"{DB}-wal"))
    if h is not None and h >= 72:
        problemas["base"] = f"🟡 La base de datos no se actualiza hace {int(h)} h."
    h = _horas_desde(*BACKUPS.glob("*.db")) if BACKUPS.exists() else None
    if DB.exists() and (h is None or h >= 26):
        problemas["respaldo"] = "🟡 No hay respaldo local de la base de las últimas 26 h."
    return problemas


def _owners() -> list[str]:
    try:
        usuarios = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(u["user_id"]) for u in usuarios
            if isinstance(u, dict) and str(u.get("rol", "")).strip().upper() == "OWNER" and u.get("user_id")]


def avisar(texto: str) -> None:
    """Envía el texto por Telegram a los OWNER (y siempre lo deja en el log)."""
    log.warning("SALUD: %s", texto)
    token = os.getenv("TELEGRAM_TOKEN", "")
    if not token:
        return
    for chat_id in _owners():
        datos = parse.urlencode({"chat_id": chat_id, "text": texto}).encode()
        try:
            request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=datos, timeout=15)  # noqa: S310
        except Exception as e:
            log.warning("No se pudo avisar a %s: %s", chat_id, type(e).__name__)


def ciclo_salud(avisados: dict[str, str]) -> None:
    """Avisa cada problema nuevo una sola vez y avisa cuando se resuelve."""
    actuales = revisar_salud()
    nuevos = {k: v for k, v in actuales.items() if k not in avisados}
    resueltos = [avisados[k] for k in list(avisados) if k not in actuales]
    if nuevos:
        avisar("Bitácora: alerta de salud\n" + "\n".join(nuevos.values()))
    if resueltos:
        avisar("✅ Bitácora: resuelto\n" + "\n".join(resueltos))
    avisados.clear()
    avisados.update(actuales)


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
    avisados: dict[str, str] = {}
    # Primera revisión 5 min después de arrancar (deja subir app y bot).
    proxima_salud = time.monotonic() + 300
    while True:
        if SALUD_MINUTOS > 0 and time.monotonic() >= proxima_salud:
            proxima_salud = time.monotonic() + SALUD_MINUTOS * 60
            try:
                ciclo_salud(avisados)
            except Exception:
                log.exception("La alerta de salud falló")
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
