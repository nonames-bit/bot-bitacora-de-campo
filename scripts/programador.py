"""Tareas programadas de la Bitácora dentro de Docker (reemplaza el cron del VPS).

Corre en el servicio ``tareas`` de docker-compose.yml. Cada tarea es un
comando con su horario (hora de la finca, TZ del contenedor):

- 03:00 todos los días   respaldo local de la base (30 días de rotación)
- 06:00 todos los días   precios de mercado
- 06:00 cada 3 días      NDVI satelital
- 06:05 los lunes        lluvia satelital (CHIRPS)
- cada 15 min            alerta de salud por Telegram (y push) a los OWNER
                         (reemplaza scripts/healthcheck_vps.sh, que dependía de systemd)
- 06:30 todos los días   push "Tareas de hoy" (resumen de las listas de trabajo)
- cada 30 min            push de avisos urgentes nuevos (parto atrasado o para
                         hoy/mañana, retiro que termina hoy), sin repetir
- cada 15 min            correo de facturas de la finca: las facturas que llegan
                         quedan "Por revisar" (solo si FACTURAS_IMAP_* está en .env)

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


# ---------------------------------------------------------------------------
# Notificaciones push al celular (llegan con la app cerrada)
# ---------------------------------------------------------------------------
ROLES_AVISOS = {"OWNER", "ADMIN", "MAYORDOMO"}
URGENTES_MINUTOS = int(os.getenv("PUSH_URGENTES_MINUTOS", "30"))
# (clave de la lista de trabajo, texto para el resumen de la mañana)
RESUMEN_LISTAS = [
    ("partos", "parto(s) próximos o atrasados"), ("palpar", "para palpar"), ("secar", "para secar"),
    ("servir", "para servir"), ("celos", "celo(s) esperados"), ("tratamientos", "tratamiento(s)/retiros"),
    ("vac_brucelosis", "vacuna brucelosis"), ("vac_aftosa", "vacuna aftosa"), ("destetar", "para destetar"),
    ("control_leche", "sin control lechero"),
]


def _destinatarios_push() -> list:
    """OWNER/ADMIN/MAYORDOMO de users.json + las suscripciones sin usuario
    (quien entra con la contraseña maestra, que es el dueño)."""
    ids: list = [None]
    try:
        usuarios = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        usuarios = []
    for u in usuarios:
        if isinstance(u, dict) and str(u.get("rol", "")).strip().upper() in ROLES_AVISOS and u.get("user_id"):
            ids.append(u["user_id"])
    return ids


def _db():
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    from src.db.database import Database
    return Database(str(DB))


def push(titulo: str, cuerpo: str, url: str = "/", tag: str = "bitacora-aviso", urgente: bool = False) -> dict:
    """Push a los destinatarios de avisos. Nunca lanza (sin llaves VAPID no envía)."""
    if not DB.exists():  # sin base no hay suscripciones (y no se crea una vacía)
        return {"enviados": 0, "fallidos": 0, "vencidas_limpiadas": 0}
    try:
        from src.server.push_sender import enviar_push
        db = _db()
        try:
            r = enviar_push(db, titulo, cuerpo, url=url, tag=tag, user_ids=_destinatarios_push(), urgente=urgente)
        finally:
            db.close()
        log.info("push '%s': %s", titulo, r)
        return r
    except Exception:
        log.exception("push '%s' falló", titulo)
        return {"enviados": 0, "fallidos": 0, "vencidas_limpiadas": 0}


def push_resumen_diario() -> None:
    """06:30: cuántas tareas hay hoy por lista. No envía nada si no hay tareas."""
    from src.engine.tareas import datos_tareas
    db = _db()
    try:
        conteos = datos_tareas(db, date.today()).get("conteos") or {}
    finally:
        db.close()
    partes = [f"{conteos[k]} {txt}" for k, txt in RESUMEN_LISTAS if conteos.get(k)]
    if partes:
        push("🐄 Tareas de hoy", " · ".join(partes), url="/", tag="resumen-diario")


def avisos_urgentes(hoy: date | None = None) -> list[tuple[str, str]]:
    """[(clave única, texto)] de lo que no puede esperar: parto atrasado, parto
    esperado hoy o mañana y retiro de leche/carne que termina hoy."""
    from src.engine.tareas import datos_tareas
    hoy = hoy or date.today()
    db = _db()
    try:
        t = datos_tareas(db, hoy)
        filas_ret = db.query(
            "SELECT a.tag, t.producto, t.fecha_fin_retiro_leche fl, t.fecha_fin_retiro_carne fc "
            "FROM tratamientos t JOIN animales a ON a.id_animal = t.animal_id "
            "WHERE a.estado = 'ACTIVO' AND (t.fecha_fin_retiro_leche = ? OR t.fecha_fin_retiro_carne = ?)",
            (hoy.isoformat(), hoy.isoformat()))
    finally:
        db.close()
    out = []
    for p in t.get("partos", []):
        if p.get("estado") == "ATRASADO":
            out.append((f"parto_atrasado:{p['tag']}:{p['fep']}",
                        f"🐄 {p['tag']}: parto atrasado ({-int(p['en_dias'])} d, esperado {p['fep']})"))
        elif p.get("en_dias") is not None and int(p["en_dias"]) <= 1:
            cuando = "hoy" if int(p["en_dias"]) == 0 else "mañana"
            out.append((f"parto_proximo:{p['tag']}:{p['fep']}", f"🐣 {p['tag']}: parto esperado {cuando}"))
    for r in filas_ret:
        for campo, nombre in (("fl", "leche"), ("fc", "carne")):
            if r[campo] == hoy.isoformat():
                out.append((f"retiro_fin:{r['tag']}:{nombre}:{hoy.isoformat()}",
                            f"💉 {r['tag']}: hoy termina el retiro de {nombre} ({r['producto'] or 'tratamiento'})"))
    return out


def push_urgentes(hoy: date | None = None) -> int:
    """Envía los avisos urgentes que aún no se enviaron. Si son más de 3, van en
    un solo push para no llenar el celular. Devuelve cuántos avisos nuevos hubo."""
    avisos = avisos_urgentes(hoy)
    db = _db()
    try:
        nuevos = [(k, txt) for k, txt in avisos if not db.push_ya_enviado(k)]
        if not nuevos:
            return 0
        if len(nuevos) <= 3:
            for _k, txt in nuevos:
                push("⚠️ Aviso de la finca", txt, url="/?v=repro", tag=_k.split(":")[0], urgente=True)
        else:
            cuerpo = "\n".join(txt for _k, txt in nuevos[:3]) + f"\n… y {len(nuevos) - 3} más"
            push(f"⚠️ {len(nuevos)} avisos de la finca", cuerpo, url="/?v=repro", tag="avisos-urgentes",
                 urgente=True)
        for k, _txt in nuevos:
            db.marcar_push_enviado(k)
        return len(nuevos)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Correo de facturas (src/integrations/correo_facturas.py)
# ---------------------------------------------------------------------------
CORREO_FACTURAS_MINUTOS = int(os.getenv("FACTURAS_CORREO_MINUTOS", "15"))
MEDIA = Path(os.getenv("MEDIA_DIR", "media"))


def revisar_correo_facturas() -> int:
    """Lee las facturas nuevas del correo de la finca y las deja por revisar."""
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    from src.integrations import correo_facturas
    if not correo_facturas.configurado():
        return 0
    media = MEDIA if MEDIA.is_absolute() else RAIZ / MEDIA
    db = _db()
    try:
        n = correo_facturas.revisar_correo(db, media_dir=str(media), users_file=str(USERS_FILE))
    finally:
        db.close()
    if n:
        log.info("Correo de facturas: %d factura(s) por revisar", n)
    return n


def avisar(texto: str) -> None:
    """Envía el texto por Telegram y push a los OWNER (y siempre lo deja en el log)."""
    log.warning("SALUD: %s", texto)
    lineas = texto.split("\n")
    push(lineas[0], "\n".join(lineas[1:]) or lineas[0], url="/", tag="salud", urgente=True)
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
    ("push_resumen_diario", 6, 30, lambda d: True, push_resumen_diario),
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
    proxima_urgentes = time.monotonic() + 120
    proxima_correo = time.monotonic() + 180
    while True:
        if CORREO_FACTURAS_MINUTOS > 0 and time.monotonic() >= proxima_correo:
            proxima_correo = time.monotonic() + CORREO_FACTURAS_MINUTOS * 60
            try:
                revisar_correo_facturas()
            except Exception:
                log.exception("El correo de facturas falló")
        if URGENTES_MINUTOS > 0 and time.monotonic() >= proxima_urgentes:
            proxima_urgentes = time.monotonic() + URGENTES_MINUTOS * 60
            try:
                push_urgentes()
            except Exception:
                log.exception("Los avisos urgentes fallaron")
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
