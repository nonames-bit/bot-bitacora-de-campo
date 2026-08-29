"""Watcher automático para la carpeta de copias de Software Ganadero (SG).

Monitorea la carpeta de copias (configurable vía ``COPIAS_DIR`` o argumento CLI),
detecta nuevos archivos de respaldo (.Zip), evita re-importar archivos ya procesados
usando mtime, tamaño y hash MD5 (guardado en ``.ultimo_importado``), ejecuta la
importación idempotente con ``import_zip``, registra el resultado en ``data/copias_import.log``
y envía un reporte a los usuarios OWNER mediante la API de Telegram.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ..db.database import Database
from ..importers.dbf_importer import import_zip

logger = logging.getLogger("bitacora.copias_watcher")


def calcular_hash_archivo(ruta: str, chunk_size: int = 65536) -> str:
    """Calcula el hash MD5 de un archivo de manera eficiente en memoria."""
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def formatear_reporte_copias(
    conteos: dict,
    nombre_archivo: str,
    duracion_s: float = 0.0,
    modo_html: bool = False,
) -> str:
    """Formatea el reporte de importación para logs y notificación Telegram."""
    if not conteos:
        if modo_html:
            return (
                f"📦 <b>Auto-Import SG:</b> <code>{nombre_archivo}</code>\n"
                "⚠️ No se procesaron registros del backup."
            )
        return (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Auto-Import SG: {nombre_archivo}\nNo se procesaron registros.\n"
        )

    total_nuevos = 0
    total_duplicados = 0
    lineas_tablas = []

    for tabla, res in sorted(conteos.items()):
        if isinstance(res, dict):
            n = res.get("nuevos", 0)
            d = res.get("duplicados", 0)
            total_nuevos += n
            total_duplicados += d
            if modo_html:
                lineas_tablas.append(f"• <b>{tabla}</b>: {n} nuevos, {d} duplicados")
            else:
                lineas_tablas.append(f"• {tabla}: {n} nuevos, {d} duplicados")

    dur_str = f" ({duracion_s:.1f}s)" if duracion_s > 0 else ""

    if modo_html:
        lineas = [
            "📦 <b>Software Ganadero — Auto-Import Exitoso</b>",
            f"📁 Archivo: <code>{nombre_archivo}</code>{dur_str}",
            f"📊 Consolidado: <b>{total_nuevos} nuevos</b>, {total_duplicados} duplicados",
            "",
            "📋 <b>Detalle por tabla:</b>",
        ] + lineas_tablas
        return "\n".join(lineas)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lineas = [
        f"[{timestamp}] IMPORTACIÓN AUTOMÁTICA: {nombre_archivo}{dur_str}",
        f"Total consolidado: {total_nuevos} nuevos, {total_duplicados} duplicados",
        "Detalle por tabla:",
    ] + lineas_tablas + ["-" * 60]
    return "\n".join(lineas)


class CopiasWatcher:
    """Monitorea un directorio en busca de nuevos .Zip y ejecuta import_zip."""

    def __init__(
        self,
        copias_dir: Optional[str] = None,
        db_path: Optional[str] = None,
        state_file: Optional[str] = None,
        log_file: Optional[str] = None,
        media_dir: Optional[str] = None,
        users_file: Optional[str] = None,
        telegram_token: Optional[str] = None,
        notify_telegram: bool = True,
    ):
        self.copias_dir = copias_dir or os.getenv("COPIAS_DIR", "data/copias")
        self.db_path = db_path or os.getenv("BITACORA_DB", "data/bitacora.db")
        self.state_file = state_file or os.path.join(self.copias_dir, ".ultimo_importado")
        self.log_file = log_file or os.getenv("COPIAS_LOG", "data/copias_import.log")
        self.media_dir = media_dir or os.getenv("MEDIA_DIR", "media")
        self.users_file = users_file or os.getenv("USERS_FILE", "src/server/users.json")
        self.telegram_token = telegram_token or os.getenv("TELEGRAM_TOKEN")
        self.notify_telegram = notify_telegram
        self._running = False

    def leer_estado(self) -> dict[str, Any]:
        """Lee el archivo de estado .ultimo_importado. Retorna estructura dict."""
        if not os.path.exists(self.state_file):
            return {"procesados": {}}

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
                if not contenido:
                    return {"procesados": {}}
                try:
                    data = json.loads(contenido)
                    if isinstance(data, dict):
                        if "procesados" not in data:
                            data["procesados"] = {}
                        return data
                except json.JSONDecodeError:
                    # Compatibilidad con formato de texto plano (solo hash o nombre)
                    return {
                        "ultimo_archivo": contenido,
                        "ultimo_hash": contenido,
                        "procesados": {contenido: {"hash": contenido}},
                    }
        except Exception as e:
            logger.warning("Error al leer archivo de estado %s: %s", self.state_file, e)

        return {"procesados": {}}

    def guardar_estado(
        self,
        nombre: str,
        mtime: float,
        size: int,
        hash_val: str,
    ) -> None:
        """Guarda la información del archivo importado en .ultimo_importado."""
        estado = self.leer_estado()
        if "procesados" not in estado:
            estado["procesados"] = {}

        now_iso = datetime.now().isoformat()
        estado["ultimo_archivo"] = nombre
        estado["ultimo_mtime"] = mtime
        estado["ultimo_size"] = size
        estado["ultimo_hash"] = hash_val
        estado["fecha_actualizacion"] = now_iso

        estado["procesados"][nombre] = {
            "mtime": mtime,
            "size": size,
            "hash": hash_val,
            "fecha": now_iso,
        }

        dir_state = os.path.dirname(os.path.abspath(self.state_file))
        if dir_state and not os.path.exists(dir_state):
            os.makedirs(dir_state, exist_ok=True)

        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(estado, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Error al escribir archivo de estado %s: %s", self.state_file, e)

    def calcular_hash(self, ruta: str) -> str:
        """Calcula el hash del archivo usando la función auxiliar."""
        return calcular_hash_archivo(ruta)

    def es_archivo_nuevo(self, ruta: str) -> bool:
        """Determina si un archivo zip es nuevo o si su contenido/mtime ha cambiado."""
        if not os.path.isfile(ruta):
            return False

        nombre = os.path.basename(ruta)
        if nombre.startswith("."):
            return False

        try:
            st = os.stat(ruta)
        except OSError:
            return False

        mtime = st.st_mtime
        size = st.st_size

        estado = self.leer_estado()
        procesados = estado.get("procesados", {})

        if nombre in procesados:
            reg = procesados[nombre]
            # Si coincide en mtime exacto y tamaño, ya fue procesado
            if abs(reg.get("mtime", 0.0) - mtime) < 0.001 and reg.get("size") == size:
                return False

        # Si no coincide o no existe en procesados, calculamos hash MD5
        try:
            h = self.calcular_hash(ruta)
        except Exception as e:
            logger.warning("No se pudo calcular hash de %s: %s", ruta, e)
            return False

        if nombre in procesados:
            if procesados[nombre].get("hash") == h:
                return False

        if estado.get("ultimo_hash") == h and estado.get("ultimo_size") == size:
            return False

        return True

    def archivo_listo(self, ruta: str) -> bool:
        """Comprueba que el archivo no esté bloqueado o a medio escribir."""
        if not os.path.isfile(ruta):
            return False
        try:
            size = os.path.getsize(ruta)
            if size == 0:
                return False
            # Validar que sea un zip legible
            with zipfile.ZipFile(ruta, "r") as zf:
                _ = zf.namelist()
            return True
        except (zipfile.BadZipFile, OSError, PermissionError):
            return False

    def escribir_log(self, mensaje_texto: str) -> None:
        """Escribe una entrada en el log histórico data/copias_import.log."""
        dir_log = os.path.dirname(os.path.abspath(self.log_file))
        if dir_log and not os.path.exists(dir_log):
            os.makedirs(dir_log, exist_ok=True)

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(mensaje_texto + "\n")
        except Exception as e:
            logger.error("Error al escribir log en %s: %s", self.log_file, e)

    def obtener_destinatarios(self, users_path: Optional[str] = None) -> list[int]:
        """Obtiene la lista de chat_ids de usuarios con rol OWNER (y ADMIN)."""
        ruta = users_path or self.users_file
        if not os.path.exists(ruta):
            return []

        try:
            with open(ruta, "r", encoding="utf-8") as f:
                usuarios = json.load(f)
            if not isinstance(usuarios, list):
                return []
            owners = []
            for u in usuarios:
                if isinstance(u, dict) and str(u.get("rol", "")).strip().upper() == "OWNER":
                    uid = u.get("user_id")
                    if uid:
                        owners.append(int(uid))
            return owners
        except Exception as e:
            logger.warning("Error al leer destinatarios desde %s: %s", ruta, e)
            return []

    def enviar_notificacion_telegram(self, texto_html: str) -> int:
        """Envía el reporte formateado a los administradores/propietarios vía Telegram."""
        if not self.notify_telegram or not self.telegram_token:
            return 0

        destinatarios = self.obtener_destinatarios()
        if not destinatarios:
            logger.info("No se encontraron usuarios OWNER para notificar por Telegram.")
            return 0

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        enviados = 0

        for chat_id in destinatarios:
            payload = json.dumps({
                "chat_id": chat_id,
                "text": texto_html,
                "parse_mode": "HTML",
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    st_code = getattr(resp, "status", None)
                    if st_code is None and hasattr(resp, "getcode"):
                        st_code = resp.getcode()
                    if st_code == 200 or st_code is None:
                        enviados += 1
                        logger.info("Notificación Telegram enviada a user_id=%s", chat_id)
            except Exception as e:
                logger.error("Error al enviar notificación Telegram a %s: %s", chat_id, e)

        return enviados

    def procesar_archivo(self, zip_path: str) -> dict[str, Any]:
        """Importa un archivo .Zip específico, actualiza estado, loguea y notifica."""
        nombre = os.path.basename(zip_path)
        st = os.stat(zip_path)
        mtime = st.st_mtime
        size = st.st_size
        hash_val = self.calcular_hash(zip_path)

        t_inicio = time.time()
        db = Database(self.db_path)
        db.create_tables()

        try:
            conteos = import_zip(db, zip_path, media_dir=self.media_dir)
            duracion = time.time() - t_inicio

            # Log en archivo plano
            reporte_txt = formatear_reporte_copias(conteos, nombre, duracion_s=duracion, modo_html=False)
            self.escribir_log(reporte_txt)

            # Notificación Telegram en HTML
            reporte_html = formatear_reporte_copias(conteos, nombre, duracion_s=duracion, modo_html=True)
            self.enviar_notificacion_telegram(reporte_html)

            # Actualizar estado para evitar re-importación
            self.guardar_estado(nombre, mtime, size, hash_val)

            logger.info("Importación completada para %s en %.2fs: %s", nombre, duracion, conteos)
            return {
                "archivo": zip_path,
                "nombre": nombre,
                "conteos": conteos,
                "duracion_s": duracion,
                "exito": True,
            }
        except Exception as e:
            duracion = time.time() - t_inicio
            err_msg = f"Error al importar backup '{nombre}': {e}"
            logger.error(err_msg, exc_info=True)
            self.escribir_log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR al importar {nombre}: {e}\n" + "-" * 60)
            if self.notify_telegram and self.telegram_token:
                self.enviar_notificacion_telegram(
                    f"⚠️ <b>Error en Auto-Import SG:</b>\n"
                    f"📁 Archivo: <code>{nombre}</code>\n"
                    f"❌ Detalle: <code>{e}</code>"
                )
            return {
                "archivo": zip_path,
                "nombre": nombre,
                "error": str(e),
                "duracion_s": duracion,
                "exito": False,
            }
        finally:
            try:
                db.close()
            except Exception:
                pass

    def listar_candidatos(self) -> list[str]:
        """Lista todos los archivos .zip en copias_dir ordenados por mtime ascendente."""
        if not os.path.exists(self.copias_dir):
            return []

        candidatos = []
        try:
            for entry in os.scandir(self.copias_dir):
                if entry.is_file() and entry.name.lower().endswith(".zip") and not entry.name.startswith("."):
                    candidatos.append(entry.path)
        except OSError as e:
            logger.error("Error al escanear directorio %s: %s", self.copias_dir, e)
            return []

        # Ordenar por fecha de modificación (los más antiguos primero para orden cronológico)
        candidatos.sort(key=lambda p: os.path.getmtime(p))
        return candidatos

    def verificar_y_procesar(self) -> list[dict[str, Any]]:
        """Escanea la carpeta, detecta nuevos .Zip y los procesa."""
        if not os.path.exists(self.copias_dir):
            os.makedirs(self.copias_dir, exist_ok=True)

        candidatos = self.listar_candidatos()
        resultados = []

        for ruta in candidatos:
            if self.es_archivo_nuevo(ruta):
                if not self.archivo_listo(ruta):
                    logger.warning("Archivo %s aún no está listo o está corrupto; se omite temporalmente.", ruta)
                    continue

                logger.info("Nuevo archivo de backup detectado: %s", ruta)
                res = self.procesar_archivo(ruta)
                resultados.append(res)

        return resultados

    def detener(self, *args) -> None:
        """Detiene el bucle de ejecución."""
        self._running = False

    def iniciar(self, polling_interval: int = 60, once: bool = False) -> None:
        """Inicia el servicio de vigilancia en tiempo real o sondeo periódico."""
        if once:
            logger.info("Ejecutando verificación única de copias en: %s", self.copias_dir)
            self.verificar_y_procesar()
            return

        logger.info(
            "Iniciando vigilante de copias SG en: %s (intervalo: %ds, db: %s)",
            self.copias_dir,
            polling_interval,
            self.db_path,
        )
        self._running = True

        try:
            signal.signal(signal.SIGINT, lambda s, f: self.detener())
            signal.signal(signal.SIGTERM, lambda s, f: self.detener())
        except Exception:
            pass

        # Primera verificación inmediata
        self.verificar_y_procesar()

        # Intentar watchdog si está disponible
        usar_watchdog = False
        try:
            from watchdog.observers import Observer
            from watchdog.events import PatternMatchingEventHandler

            watcher_ref = self

            class CopiasHandler(PatternMatchingEventHandler):
                patterns = ["*.zip", "*.Zip", "*.ZIP"]

                def on_created(self, event):
                    if not event.is_directory:
                        time.sleep(1.0)
                        watcher_ref.verificar_y_procesar()

                def on_modified(self, event):
                    if not event.is_directory:
                        time.sleep(1.0)
                        watcher_ref.verificar_y_procesar()

                def on_moved(self, event):
                    if not event.is_directory:
                        time.sleep(1.0)
                        watcher_ref.verificar_y_procesar()

            handler = CopiasHandler()
            observer = Observer()
            observer.schedule(handler, self.copias_dir, recursive=False)
            observer.start()
            usar_watchdog = True
            logger.info("Observador de sistema de archivos (watchdog) activo en %s", self.copias_dir)

            try:
                while self._running:
                    time.sleep(polling_interval)
                    self.verificar_y_procesar()
            finally:
                observer.stop()
                observer.join()

        except (ImportError, Exception) as e:
            if not usar_watchdog:
                logger.info(
                    "Watchdog no disponible o no compatible (%s). Usando sondeo (polling cada %ds).",
                    e,
                    polling_interval,
                )
            while self._running:
                try:
                    time.sleep(polling_interval)
                    self.verificar_y_procesar()
                except KeyboardInterrupt:
                    break


def main(argv=None) -> int:
    """Punto de entrada CLI para el vigilante de copias."""
    parser = argparse.ArgumentParser(
        description="Vigilante de carpeta de copias Software Ganadero (Auto-Importador)."
    )
    parser.add_argument("--dir", default=None, help="Directorio a vigilar (default: data/copias o COPIAS_DIR)")
    parser.add_argument("--db", default=None, help="Ruta de la base de datos (default: data/bitacora.db)")
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola verificación y salir")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo de polling en segundos (default: 60)")
    parser.add_argument("--no-telegram", action="store_true", help="Desactivar notificaciones de Telegram")
    parser.add_argument("--state-file", default=None, help="Ruta del archivo de estado .ultimo_importado")
    parser.add_argument("--log-file", default=None, help="Ruta del log data/copias_import.log")
    parser.add_argument("--media", default=None, help="Directorio para extraer fotos")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    watcher = CopiasWatcher(
        copias_dir=args.dir,
        db_path=args.db,
        state_file=args.state_file,
        log_file=args.log_file,
        media_dir=args.media,
        notify_telegram=not args.no_telegram,
    )
    watcher.iniciar(polling_interval=args.interval, once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
