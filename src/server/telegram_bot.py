"""Bot de Telegram multiusuario con control de acceso basado en roles (RBAC)."""
from __future__ import annotations

import logging
import os
import sys
import time
import zipfile
from typing import Optional

from ..bot.bot_interface import Bot
from ..db.database import Database
from ..engine.query_engine import QueryEngine
from ..importers.dbf_importer import import_zip
from .auth import Auth

logger = logging.getLogger("bitacora.bot")


# ---------------------------------------------------------------------- #
# Lógica pura / formateadores independientes del SDK
# ---------------------------------------------------------------------- #
def formatear_alertas(db: Database, limite: int = 20) -> str:
    """Devuelve las alertas PENDIENTES ordenadas por fecha_programada."""
    filas = db.query(
        """
        SELECT a.id, a.tipo_alerta, a.fecha_programada, a.descripcion, an.tag
        FROM alertas a
        LEFT JOIN animales an ON an.id_animal = a.animal_id
        WHERE a.estado = 'PENDIENTE'
        ORDER BY a.fecha_programada ASC
        LIMIT ?
        """,
        (limite,),
    )
    if not filas:
        return "No hay alertas pendientes."

    lineas = [f"🔔 Alertas pendientes ({len(filas)}):"]
    for r in filas:
        tag = r["tag"] or "?"
        fec = r["fecha_programada"] or "sin fecha"
        tipo = r["tipo_alerta"] or "ALERTA"
        desc = f" ({r['descripcion']})" if r["descripcion"] else ""
        lineas.append(f"• [{fec}] Tag {tag} - {tipo}{desc}")
    return "\n".join(lineas)


def formatear_historial(db: Database, tag: str, hoy=None) -> str:
    """Devuelve el historial del animal delegando en el motor de consultas."""
    tag_limpio = tag.strip()
    if not tag_limpio:
        return "¿De cuál animal desea el historial? (ej. /historial 47)"
    qe = QueryEngine(db, hoy=hoy)
    return qe.responder(f"¿cuál es el historial de la {tag_limpio}?")


def formatear_potreros(db: Database, hoy=None) -> str:
    """Devuelve el estado de los potreros listos delegando en el motor de consultas."""
    qe = QueryEngine(db, hoy=hoy)
    return qe.responder("¿qué potreros están listos para pastoreo?")


def formatear_animales(db: Database) -> str:
    """Genera un resumen del inventario de animales por sexo y estado."""
    total = db.count("animales")
    if total == 0:
        return "📊 Inventario de animales: 0 registrados."

    filas_sexo = db.query("SELECT sexo, COUNT(*) as c FROM animales GROUP BY sexo")
    sexos: dict[str, int] = {}
    for r in filas_sexo:
        s = (r["sexo"] or "Sin especificar").strip()
        sexos[s] = sexos.get(s, 0) + int(r["c"])

    filas_estado = db.query(
        "SELECT estado, COUNT(*) as c FROM animales WHERE estado IS NOT NULL AND estado != '' GROUP BY estado"
    )
    estados_str = (
        ", ".join(f"{r['estado']}: {r['c']}" for r in filas_estado)
        if filas_estado
        else "Sin estados registrados"
    )

    partes_sexo = [f"{k}: {v}" for k, v in sorted(sexos.items())]
    lineas = [
        "📊 Inventario de Animales:",
        f"• Total: {total}",
        f"• Sexo: {', '.join(partes_sexo)}",
        f"• Estados: {estados_str}",
    ]
    return "\n".join(lineas)


def formatear_status(db: Database, db_path: Optional[str] = None) -> str:
    """Genera un reporte del estado del sistema, conteos y tamaño de base de datos."""
    n_animales = db.count("animales")
    tablas_eventos = [
        "partos", "servicios", "celos", "tratamientos",
        "pesajes", "traslados", "muertes", "movimientos",
    ]
    total_eventos = sum(db.count(t) for t in tablas_eventos)

    row_alertas = db.query_one("SELECT COUNT(*) as n FROM alertas WHERE estado = 'PENDIENTE'")
    n_alertas = int(row_alertas["n"]) if row_alertas else 0

    size_str = "en memoria"
    if db_path and db_path != ":memory:" and os.path.exists(db_path):
        bytes_size = os.path.getsize(db_path)
        mb_size = bytes_size / (1024 * 1024)
        size_str = f"{mb_size:.2f} MB"

    lineas = [
        "🖥️ Estado del Sistema:",
        f"• Animales registrados: {n_animales}",
        f"• Total de eventos zootécnicos: {total_eventos}",
        f"• Alertas pendientes: {n_alertas}",
        f"• Tamaño de base de datos: {size_str}",
    ]
    return "\n".join(lineas)


def formatear_usuarios(auth: Auth) -> str:
    """Genera la lista de usuarios registrados con sus roles."""
    usuarios = auth.listar_usuarios()
    if not usuarios:
        return "No hay usuarios registrados en el sistema."

    lineas = [f"👥 Usuarios registrados ({len(usuarios)}):"]
    for u in usuarios:
        lineas.append(f"• ID: {u.get('user_id')} | {u.get('nombre', 'Sin nombre')} | Rol: {u.get('rol')}")
    return "\n".join(lineas)


def formatear_ayuda(rol: Optional[str]) -> str:
    """Devuelve el texto del comando /start o /help adaptado al rol del usuario."""
    if rol == "OWNER":
        return (
            "👑 Comandos disponibles (Propietario / OWNER):\n\n"
            "📝 Bitácora & Consultas:\n"
            "• Envía cualquier nota de texto (ej. 'pario la 47 ternero macho')\n"
            "• Envía preguntas (ej. '¿cuándo parió la 47?')\n"
            "• Envía notas de voz o fotos de aretes/frascos\n\n"
            "📊 Administración:\n"
            "• /alertas - Ver alertas pendientes\n"
            "• /historial <tag> - Historial de un animal\n"
            "• /potreros - Potreros listos para pastoreo\n"
            "• /animales - Resumen de inventario\n"
            "• /status - Estado del sistema y base de datos\n"
            "• /usuarios - Lista de usuarios y roles\n"
            "• /reporte - Generar reporte (Fase 2)\n"
            "• /exportar - Exportar datos (Fase 2)\n"
            "• /importar - Instrucciones para importar backup DBF\n"
            "• /confirmar_importar - Procesar backup subido\n"
            "• /descartar_backup - Eliminar backup pendiente\n\n"
            "⚙️ Gestión de Usuarios & Sistema:\n"
            "• /agregar_usuario <user_id> <ROL> [nombre] - Registrar o actualizar usuario\n"
            "• /quitar_usuario <user_id> - Eliminar usuario\n"
            "• /logs - Ver últimas líneas del registro del bot"
        )
    if rol == "ADMIN":
        return (
            "🛠️ Comandos disponibles (Administrador):\n\n"
            "📝 Bitácora & Consultas:\n"
            "• Envía cualquier nota de texto (ej. 'pario la 47 ternero macho')\n"
            "• Envía preguntas (ej. '¿cuándo parió la 47?')\n"
            "• Envía notas de voz o fotos de aretes/frascos\n\n"
            "📊 Administración:\n"
            "• /alertas - Ver alertas pendientes\n"
            "• /historial <tag> - Historial de un animal\n"
            "• /potreros - Potreros listos para pastoreo\n"
            "• /animales - Resumen de inventario\n"
            "• /status - Estado del sistema y base de datos\n"
            "• /usuarios - Lista de usuarios y roles\n"
            "• /reporte - Generar reporte (Fase 2)\n"
            "• /exportar - Exportar datos (Fase 2)\n"
            "• /importar - Instrucciones para importar backup DBF\n"
            "• /confirmar_importar - Procesar backup subido\n"
            "• /descartar_backup - Eliminar backup pendiente"
        )
    if rol == "TRABAJADOR":
        return (
            "📋 Comandos disponibles (Trabajador / Campo):\n\n"
            "📝 Bitácora & Consultas:\n"
            "• Envía notas de texto de eventos (partos, celos, servicios, tratamientos, pesajes, etc.)\n"
            "• Haz preguntas en lenguaje natural (ej. '¿cuándo parió la 47?')\n"
            "• Envía notas de voz con reportes de campo\n"
            "• Envía fotos de aretes o tratamientos\n"
            "• /start o /help - Mostrar esta ayuda"
        )
    return "⛔ No autorizado."


def obtener_ultimos_logs(log_file: str, lineas: int = 20) -> str:
    """Lee y devuelve las últimas líneas del archivo de registro."""
    if not os.path.exists(log_file):
        return f"El archivo de logs '{log_file}' aún no existe."
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            todas = f.readlines()
        ultimas = todas[-lineas:] if len(todas) > lineas else todas
        if not ultimas:
            return "El archivo de logs está vacío."
        return "📄 Últimos logs:\n" + "".join(ultimas)
    except Exception as e:
        return f"Error al leer logs: {e}"


def formatear_reporte_importacion(conteos: dict) -> str:
    """Formatea el reporte de importación de DBF indicando filas nuevas y duplicadas."""
    if not conteos:
        return "📦 No se procesaron registros del backup."

    total_nuevos = 0
    total_duplicados = 0
    lineas_tablas = []

    for tabla, res in sorted(conteos.items()):
        if isinstance(res, dict):
            n = res.get("nuevos", 0)
            d = res.get("duplicados", 0)
            total_nuevos += n
            total_duplicados += d
            lineas_tablas.append(f"• {tabla}: {n} nuevos, {d} duplicados")

    lineas = [
        "📦 Reporte de Importación de Backup:",
        f"• Total consolidado: {total_nuevos} nuevos, {total_duplicados} duplicados",
        "",
        "📋 Detalle por tabla:",
    ] + lineas_tablas
    return "\n".join(lineas)


def formatear_instrucciones_importar() -> str:
    """Devuelve las instrucciones para subir un backup mediante Telegram o SSH."""
    return (
        "📦 Para importar un backup de Software Ganadero:\n\n"
        "1. Envíame el archivo .zip directamente por este chat como documento.\n"
        "2. Te confirmaré la recepción y responderás /confirmar_importar para procesarlo.\n"
        "3. Si deseas cancelarlo antes de procesar, usa /descartar_backup.\n\n"
        "⚠️ Límite de Telegram: 20MB. Para archivos más pesados, súbelo por SSH y usa:\n"
        "./scripts/importar_backup.sh <ruta_archivo.zip>"
    )


def guardar_backup_pendiente(ruta_zip: str, uploads_dir: str = "data/uploads") -> str:
    """Registra la ruta del archivo zip pendiente en pendiente.txt."""
    os.makedirs(uploads_dir, exist_ok=True)
    pendiente_file = os.path.join(uploads_dir, "pendiente.txt")
    with open(pendiente_file, "w", encoding="utf-8") as f:
        f.write(os.path.abspath(ruta_zip))
    return pendiente_file


def obtener_backup_pendiente(uploads_dir: str = "data/uploads") -> Optional[str]:
    """Obtiene la ruta absoluta del backup pendiente si el archivo existe en disco."""
    pendiente_file = os.path.join(uploads_dir, "pendiente.txt")
    if not os.path.exists(pendiente_file):
        return None
    try:
        with open(pendiente_file, "r", encoding="utf-8") as f:
            ruta = f.read().strip()
        if ruta and os.path.exists(ruta):
            return ruta
        return None
    except Exception:
        return None


def descartar_backup_pendiente(uploads_dir: str = "data/uploads") -> bool:
    """Elimina el archivo .zip pendiente y el archivo pendiente.txt."""
    pendiente_file = os.path.join(uploads_dir, "pendiente.txt")
    eliminado = False
    if os.path.exists(pendiente_file):
        try:
            with open(pendiente_file, "r", encoding="utf-8") as f:
                ruta = f.read().strip()
            if ruta and os.path.exists(ruta):
                try:
                    os.remove(ruta)
                    eliminado = True
                except OSError:
                    pass
            os.remove(pendiente_file)
        except Exception:
            pass
    return eliminado


# ---------------------------------------------------------------------- #
# Construcción del Bot de Telegram (SDK python-telegram-bot)
# ---------------------------------------------------------------------- #
def construir_application(
    token: str,
    db: Database,
    auth: Auth,
    media_dir: str = "media",
    log_file: str = "bot.log",
    uploads_dir: str = "data/uploads",
):
    """Construye y configura la Application de Telegram con todos los handlers."""
    try:
        from telegram import Update
        from telegram.ext import (ApplicationBuilder, CommandHandler,
                                  ContextTypes, MessageHandler, filters)
    except ImportError as e:
        raise ImportError(
            "python-telegram-bot no está instalado. Instálalo con 'pip install python-telegram-bot>=21.0'"
        ) from e

    async def cmd_start_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            rol = auth.rol_de(user_id)
            await update.message.reply_text(formatear_ayuda(rol))
        except Exception as e:
            logger.error("Error en cmd_start_help: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message or not update.message.text:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            bot_engine = Bot(db)
            respuesta = bot_engine.procesar_texto(update.message.text)
            await update.message.reply_text(respuesta)
        except Exception as e:
            logger.error("Error en handle_texto: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            voice = update.message.voice or update.message.audio
            if not voice:
                return
            os.makedirs(media_dir, exist_ok=True)
            ts = int(time.time())
            dest_path = os.path.join(media_dir, f"voz_{user_id}_{ts}.ogg")
            archivo = await context.bot.get_file(voice.file_id)
            await archivo.download_to_drive(dest_path)
            await update.message.reply_text(
                "🎤 Audio recibido y guardado. La transcripción automática llega en Fase 3."
            )
        except Exception as e:
            logger.error("Error en handle_voice: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            photos = update.message.photo
            if not photos:
                return
            foto = photos[-1]
            os.makedirs(media_dir, exist_ok=True)
            ts = int(time.time())
            dest_path = os.path.join(media_dir, f"foto_{user_id}_{ts}.jpg")
            archivo = await context.bot.get_file(foto.file_id)
            await archivo.download_to_drive(dest_path)
            await update.message.reply_text("📷 Foto recibida y guardada.")
        except Exception as e:
            logger.error("Error en handle_photo: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message or not update.message.document:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            doc = update.message.document
            file_name = doc.file_name or ""
            if not file_name.lower().endswith(".zip"):
                await update.message.reply_text("⚠️ Por favor envía un archivo .zip con el backup de Software Ganadero.")
                return

            file_size = doc.file_size or 0
            if file_size > 20 * 1024 * 1024:
                await update.message.reply_text(
                    "❌ El archivo supera el límite de Telegram (20MB). Súbelo por SSH y usa scripts/importar_backup.sh"
                )
                return

            os.makedirs(uploads_dir, exist_ok=True)
            ts = int(time.time())
            dest_path = os.path.join(uploads_dir, f"backup_{ts}.zip")

            try:
                archivo = await context.bot.get_file(doc.file_id)
                await archivo.download_to_drive(dest_path)
            except Exception as e:
                logger.error("Error al descargar archivo desde Telegram: %s", e)
                await update.message.reply_text(
                    "❌ El archivo supera el límite de Telegram (20MB). Súbelo por SSH y usa scripts/importar_backup.sh"
                )
                return

            if not zipfile.is_zipfile(dest_path):
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                await update.message.reply_text("❌ El archivo no es un ZIP válido.")
                return

            guardar_backup_pendiente(dest_path, uploads_dir=uploads_dir)
            tam_mb = os.path.getsize(dest_path) / (1024 * 1024)
            await update.message.reply_text(
                f"📦 Backup recibido ({tam_mb:.2f} MB). Responde /confirmar_importar para procesarlo o /descartar_backup para eliminarlo."
            )
        except Exception as e:
            logger.error("Error en handle_document: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_alertas(db)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_alertas: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            if not context.args or len(context.args) != 1:
                await update.message.reply_text("Uso: /historial <tag>")
                return
            tag = context.args[0]
            msg = formatear_historial(db, tag)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_historial: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_potreros(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_potreros(db)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_potreros: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_animales(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_animales(db)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_animales: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_status(db, db.path if hasattr(db, "path") else None)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_status: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_usuarios(auth)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_usuarios: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_fase2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            await update.message.reply_text("⏳ Disponible en Fase 2.")
        except Exception as e:
            logger.error("Error en cmd_fase2: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_importar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            await update.message.reply_text(formatear_instrucciones_importar())
        except Exception as e:
            logger.error("Error en cmd_importar: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_confirmar_importar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            ruta_zip = obtener_backup_pendiente(uploads_dir=uploads_dir)
            if not ruta_zip:
                await update.message.reply_text("⚠️ No hay ningún backup pendiente de importación.")
                return

            conteos = import_zip(db, ruta_zip)
            descartar_backup_pendiente(uploads_dir=uploads_dir)
            msg = formatear_reporte_importacion(conteos)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_confirmar_importar: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al importar backup: {e}")

    async def cmd_descartar_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            ruta_zip = obtener_backup_pendiente(uploads_dir=uploads_dir)
            if not ruta_zip:
                await update.message.reply_text("⚠️ No hay ningún backup pendiente para descartar.")
                return

            descartar_backup_pendiente(uploads_dir=uploads_dir)
            await update.message.reply_text("🗑️ Backup descartado y archivo eliminado.")
        except Exception as e:
            logger.error("Error en cmd_descartar_backup: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_agregar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_gestionar_usuarios(user_id):
                await update.message.reply_text("⛔ No autorizado. Solo OWNER puede gestionar usuarios.")
                return
            if not context.args or len(context.args) < 2:
                await update.message.reply_text("Uso: /agregar_usuario <user_id> <ROL> [nombre]")
                return
            try:
                nuevo_uid = int(context.args[0])
            except ValueError:
                await update.message.reply_text("❌ El user_id debe ser un número entero.")
                return
            nuevo_rol = context.args[1].upper()
            nuevo_nombre = " ".join(context.args[2:]) if len(context.args) > 2 else f"Usuario_{nuevo_uid}"

            auth.agregar_usuario(nuevo_uid, nuevo_nombre, nuevo_rol)
            await update.message.reply_text(
                f"✅ Usuario {nuevo_uid} ({nuevo_nombre}) registrado correctamente con rol {nuevo_rol}."
            )
        except ValueError as ve:
            if update.message:
                await update.message.reply_text(f"❌ Error: {ve}")
        except Exception as e:
            logger.error("Error en cmd_agregar_usuario: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_quitar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_gestionar_usuarios(user_id):
                await update.message.reply_text("⛔ No autorizado. Solo OWNER puede gestionar usuarios.")
                return
            if not context.args:
                await update.message.reply_text("Uso: /quitar_usuario <user_id>")
                return
            try:
                eliminar_uid = int(context.args[0])
            except ValueError:
                await update.message.reply_text("❌ El user_id debe ser un número entero.")
                return
            auth.quitar_usuario(eliminar_uid)
            await update.message.reply_text(f"✅ Usuario {eliminar_uid} eliminado correctamente.")
        except ValueError as ve:
            if update.message:
                await update.message.reply_text(f"❌ Error: {ve}")
        except Exception as e:
            logger.error("Error en cmd_quitar_usuario: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_gestionar_usuarios(user_id):
                await update.message.reply_text("⛔ No autorizado. Solo OWNER puede ver los logs.")
                return
            msg = obtener_ultimos_logs(log_file)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_logs: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    app = ApplicationBuilder().token(token).build()

    # Handlers de comandos
    app.add_handler(CommandHandler(["start", "help"], cmd_start_help))
    app.add_handler(CommandHandler("alertas", cmd_alertas))
    app.add_handler(CommandHandler("historial", cmd_historial))
    app.add_handler(CommandHandler("potreros", cmd_potreros))
    app.add_handler(CommandHandler("animales", cmd_animales))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("usuarios", cmd_usuarios))
    app.add_handler(CommandHandler(["reporte", "exportar"], cmd_fase2))
    app.add_handler(CommandHandler("importar", cmd_importar))
    app.add_handler(CommandHandler("confirmar_importar", cmd_confirmar_importar))
    app.add_handler(CommandHandler("descartar_backup", cmd_descartar_backup))
    app.add_handler(CommandHandler("agregar_usuario", cmd_agregar_usuario))
    app.add_handler(CommandHandler("quitar_usuario", cmd_quitar_usuario))
    app.add_handler(CommandHandler("logs", cmd_logs))

    # Handlers de mensajes
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))

    return app


# ---------------------------------------------------------------------- #
# Función principal de arranque
# ---------------------------------------------------------------------- #
def correr(
    token: Optional[str] = None,
    db_path: Optional[str] = None,
    users_file: Optional[str] = None,
    media_dir: Optional[str] = None,
    log_file: Optional[str] = None,
    uploads_dir: Optional[str] = None,
) -> None:
    """Inicia el bot de Telegram en modo polling con la configuración provista."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = token or os.getenv("TELEGRAM_TOKEN")
    if not token or token == "pegar_aqui_el_token_del_botfather":
        raise ValueError(
            "TELEGRAM_TOKEN no configurado. Define la variable de entorno o en el archivo .env."
        )

    db_path = db_path or os.getenv("BITACORA_DB", "data/bitacora.db")
    users_file = users_file or os.getenv("USERS_FILE", "src/server/users.json")
    media_dir = media_dir or os.getenv("MEDIA_DIR", "media")
    log_file = log_file or os.getenv("LOG_FILE", "bot.log")
    uploads_dir = uploads_dir or os.getenv("UPLOADS_DIR", "data/uploads")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    db = Database(db_path)
    db.create_tables()

    auth = Auth(users_file)

    app = construir_application(
        token=token,
        db=db,
        auth=auth,
        media_dir=media_dir,
        log_file=log_file,
        uploads_dir=uploads_dir,
    )
    logger.info("Bot de Telegram iniciado correctamente con polling...")
    app.run_polling(drop_pending_updates=True)
