"""Bot de Telegram multiusuario con control de acceso basado en roles (RBAC)."""
from __future__ import annotations

import logging
import os
import re
import sys
import time
import zipfile
from datetime import date
from typing import Optional

from ..bot.bot_interface import Bot
from ..db.database import Database
from ..engine.query_engine import QueryEngine
from ..importers.dbf_importer import import_zip
from ..parsers import nlp_engine as nlu
from ..parsers.media_handler import MediaError, transcribe_audio
from ..utils import add_days, iso
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


def formatear_potreros(db: Database, potrero: Optional[str | date] = None, hoy=None) -> str:
    """Devuelve el estado de los potreros listos, vacíos o los animales en un potrero específico delegando en el motor de consultas."""
    if isinstance(potrero, date):
        hoy = potrero
        potrero = None
    qe = QueryEngine(db, hoy=hoy)
    if potrero and str(potrero).strip():
        p_str = str(potrero).strip()
        if p_str.lower() in ("vacios", "vacio", "vacíos", "vacío"):
            return qe.responder("potreros vacios")
        if p_str.lower() in ("inventario", "todos", "ocupados"):
            return qe.responder("inventario potreros")
        if not re.search(r"\bpotrero", p_str, re.IGNORECASE):
            p_str = f"potrero {p_str}"
        return qe.responder(f"animales en {p_str}")
    return qe.responder("¿qué potreros están listos para pastoreo?")


def _contar_activos(db: Database) -> int:
    """Cuenta los animales con estado ACTIVO (inventario vivo actual)."""
    row = db.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO'")
    return int(row["n"]) if row else 0


def formatear_animales(db: Database) -> str:
    """Genera un resumen del inventario de animales activos y del histórico."""
    total = db.count("animales")
    if total == 0:
        return "📊 Inventario de animales: 0 registrados."

    activos = _contar_activos(db)
    filas_sexo = db.query(
        "SELECT sexo, COUNT(*) as c FROM animales WHERE estado = 'ACTIVO' GROUP BY sexo"
    )
    hembras = 0
    machos = 0
    for r in filas_sexo:
        s = (r["sexo"] or "Sin especificar").strip()
        if s == "Hembra":
            hembras = int(r["c"])
        elif s == "Macho":
            machos = int(r["c"])

    lineas = [
        "📊 Inventario de Animales:",
        f"🐄 Activos: {activos} (♀ {hembras} · ♂ {machos}) · Histórico total: {total}",
    ]
    return "\n".join(lineas)


def formatear_fotos(db: Database, tag: Optional[str] = None, limite: int = 5) -> str:
    """Genera un reporte en texto de las fotos registradas en la bitácora."""
    if tag:
        tag_str = tag.strip()
        filas = db.fotos_de(tag_str, limit=limite)
        if not filas:
            return f"No hay fotos registradas para el animal {tag_str}."
        lineas = [f"📷 Fotos de la {tag_str} ({len(filas)}):"]
        for r in filas:
            fec = r["fecha"] or "sin fecha"
            nom = os.path.basename(r["ruta"]) if r["ruta"] else "foto"
            cap = f" - {r['caption']}" if r["caption"] else ""
            lineas.append(f"• [{fec}] {nom}{cap}")
        return "\n".join(lineas)

    filas = db.ultimas_fotos(limit=limite)
    if not filas:
        return "No hay fotos registradas en la bitácora."
    lineas = [f"📷 Últimas fotos registradas ({len(filas)}):"]
    for r in filas:
        t = r["tag"] or "Sin tag"
        fec = r["fecha"] or "sin fecha"
        nom = os.path.basename(r["ruta"]) if r["ruta"] else "foto"
        cap = f" - {r['caption']}" if r["caption"] else ""
        lineas.append(f"• [{fec}] Tag {t}: {nom}{cap}")
    return "\n".join(lineas)


def _fmt_es_co(num: int | float) -> str:
    """Formatea enteros o flotantes con separador de miles '.' (estilo es-CO)."""
    if isinstance(num, int):
        return f"{num:,}".replace(",", ".")
    return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatear_status(
    db: Database, db_path: Optional[str] = None, hoy: Optional[date] = None
) -> str:
    """Genera un reporte del estado del sistema, conteos zootécnicos y tamaño de base de datos."""
    if hoy is None:
        hoy = date.today()

    n_activos = _contar_activos(db)
    n_total_animales = db.count("animales")

    fecha_30d = iso(add_days(hoy, -30))
    row_partos = db.query_one("SELECT COUNT(*) as n FROM partos WHERE fecha >= ?", (fecha_30d,))
    n_partos_30d = int(row_partos["n"]) if row_partos else 0

    row_destetes = db.query_one(
        "SELECT COUNT(*) as n FROM pesajes WHERE UPPER(evento) = 'DESTETE' AND fecha >= ?",
        (fecha_30d,),
    )
    n_destetes_30d = int(row_destetes["n"]) if row_destetes else 0

    # Potrero con más animales (conteo por potrero_id o último traslado)
    animales = db.query(
        "SELECT id_animal, potrero_id FROM animales WHERE COALESCE(estado, 'ACTIVO') = 'ACTIVO'"
    )
    conteo_potreros: dict[int, int] = {}
    for a in animales:
        aid = a["id_animal"]
        ult = db.query_one(
            "SELECT potrero_destino FROM traslados WHERE animal_id = ? ORDER BY fecha DESC, id DESC LIMIT 1",
            (aid,),
        )
        pid = ult["potrero_destino"] if ult and ult["potrero_destino"] is not None else a["potrero_id"]
        if pid is not None:
            conteo_potreros[pid] = conteo_potreros.get(pid, 0) + 1

    pot_mas_animales_str = "Ninguno"
    if conteo_potreros:
        max_pid, max_cnt = max(conteo_potreros.items(), key=lambda item: item[1])
        prow = db.query_one("SELECT nombre, codigo FROM potreros WHERE id = ?", (max_pid,))
        if prow:
            p_nom = prow["nombre"] or prow["codigo"] or f"ID {max_pid}"
            pot_mas_animales_str = f"{p_nom} ({_fmt_es_co(max_cnt)})"

    # Potrero con más reposo (MAX dias_reposo)
    p_reposo = db.query_one(
        "SELECT nombre, codigo, dias_reposo FROM potreros WHERE dias_reposo IS NOT NULL ORDER BY dias_reposo DESC LIMIT 1"
    )
    if p_reposo and p_reposo["dias_reposo"] is not None:
        p_rep_nom = p_reposo["nombre"] or p_reposo["codigo"] or "Potrero"
        pot_mas_reposo_str = f"{p_rep_nom} ({_fmt_es_co(p_reposo['dias_reposo'])}d)"
    else:
        pot_mas_reposo_str = "Ninguno"

    row_alertas = db.query_one("SELECT COUNT(*) as n FROM alertas WHERE estado = 'PENDIENTE'")
    n_alertas = int(row_alertas["n"]) if row_alertas else 0

    size_str = "en memoria"
    if db_path and db_path != ":memory:" and os.path.exists(db_path):
        bytes_size = os.path.getsize(db_path)
        mb_size = bytes_size / (1024 * 1024)
        size_str = f"{mb_size:.2f} MB"

    mem_str = "0 MB"
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        rss_mb = proc.memory_info().rss / (1024 * 1024)
        mem_str = f"{rss_mb:.1f} MB"
    except Exception:
        mem_str = "0 MB"

    from datetime import datetime
    ts_str = datetime.now().strftime("%d/%m %H:%M")

    lineas_pre = [
        f"Activos:              {_fmt_es_co(n_activos)}",
        f"Histórico:            {_fmt_es_co(n_total_animales)}",
        f"Partos últimos 30d:   {_fmt_es_co(n_partos_30d)}",
        f"Destetes últimos 30d: {_fmt_es_co(n_destetes_30d)}",
        f"Potrero + animales:   {pot_mas_animales_str}",
        f"Potrero + reposo:     {pot_mas_reposo_str}",
        f"Alertas pendientes:   {_fmt_es_co(n_alertas)}",
        f"Tamaño DB:            {size_str}",
        f"Memoria:              {mem_str}",
    ]
    cuerpo = "\n".join(lineas_pre)
    return (
        f"🖥️ <b>Estado del Sistema</b>\n"
        f"<pre>\n{cuerpo}\n</pre>\n"
        f"<i>Actualizado: {ts_str}</i>"
    )


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
            "• /fotos [tag] - Ver fotos registradas (o /foto <tag>)\n"
            "• /status - Estado del sistema y base de datos\n"
            "• /usuarios - Lista de usuarios y roles\n"
            "• /reporte [diario|semanal|N] - Generar reporte en PDF\n"
            "• /exportar - Descargar backup ZIP para Software Ganadero\n"
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
            "• /fotos [tag] - Ver fotos registradas (o /foto <tag>)\n"
            "• /status - Estado del sistema y base de datos\n"
            "• /usuarios - Lista de usuarios y roles\n"
            "• /reporte [diario|semanal|N] - Generar reporte en PDF\n"
            "• /exportar - Descargar backup ZIP para Software Ganadero\n"
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
            "• Envía notas de voz con reportes de campo (transcripción automática)\n"
            "• Envía fotos de aretes o tratamientos\n"
            "• /consulta <tag> o /historial <tag> - Consultar ficha zootécnica de un animal\n"
            "• /fotos [tag] - Ver fotos registradas (o /foto <tag>)\n"
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


def parsear_args_reporte(args) -> Optional[tuple[int, str]]:
    """Interpreta los argumentos de /reporte -> (días, etiqueta) o None si inválido.

    - Sin argumentos: semanal (7 días).
    - "diario": 1 día.
    - N numérico: N días.
    - Cualquier otro caso: None.
    """
    if not args:
        return (7, "semanal")
    if len(args) > 1:
        return None
    arg = args[0]
    if arg == "diario":
        return (1, "diario")
    try:
        dias = int(arg)
    except (ValueError, TypeError):
        return None
    if dias < 1:
        return None
    return (dias, f"{dias}d")


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
    reportes_dir: str = "data/reportes",
):
    """Construye y configura la Application de Telegram con todos los handlers."""
    try:
        from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                              Update)
        from telegram.ext import (ApplicationBuilder, CallbackQueryHandler,
                                  CommandHandler, ContextTypes, MessageHandler,
                                  filters)
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
            raw_text = update.message.text
            respuesta = bot_engine.procesar_texto(raw_text)

            # Fallback inteligente con botones interactivos
            if (
                "No entendí" in respuesta
                or "Puedo responder consultas como" in respuesta
                or "¿Querías alguna de estas" in respuesta
                or "No pude interpretar ese mensaje" in respuesta
            ):
                qe = QueryEngine(db)
                sugerencias = qe.sugerencias_fallback(raw_text)
                keyboard = [
                    [
                        InlineKeyboardButton(texto_btn, callback_data=cb_data)
                        for texto_btn, cb_data in sugerencias
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(respuesta, reply_markup=reply_markup)
                return

            if "<pre>" in respuesta or "<b>" in respuesta or "FICHA ZOOTÉCNICA" in respuesta:
                try:
                    await update.message.reply_text(respuesta, parse_mode="HTML")
                except Exception:
                    await update.message.reply_text(respuesta)
            else:
                await update.message.reply_text(respuesta)

            # Botón de fotos si la respuesta es una ficha zootécnica
            if "FICHA ZOOTÉCNICA" in respuesta:
                tag = nlu.extraer_tag(raw_text)
                if tag:
                    fotos = db.fotos_de(tag)
                    if fotos:
                        n_fotos = len(fotos)
                        btn_k = [
                            [
                                InlineKeyboardButton(
                                    f"📷 Ver foto ({n_fotos})",
                                    callback_data=f"foto:{tag}",
                                )
                            ]
                        ]
                        await update.message.reply_text(
                            f"📷 Este animal tiene {n_fotos} foto(s) disponible(s).",
                            reply_markup=InlineKeyboardMarkup(btn_k),
                        )
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

            bot_engine = Bot(db)
            try:
                transcript = transcribe_audio(dest_path)
                texto_audio = transcript.texto.strip()
                if texto_audio:
                    resp_evento = bot_engine.procesar_texto(texto_audio)
                    await update.message.reply_text(
                        f"🎤 Audio transcrito:\n«{texto_audio}»\n\n{resp_evento}"
                    )
                else:
                    await update.message.reply_text(
                        "🎤 Audio recibido, pero no se detectaron palabras legibles en la grabación."
                    )
            except MediaError as me:
                await update.message.reply_text(
                    f"🎤 Audio recibido y guardado ({os.path.basename(dest_path)}).\n⚠️ Nota: {me}"
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
            caption = (update.message.caption or "").strip()
            tag = nlu.extraer_tag(caption) if caption else None

            dest_path = os.path.join(media_dir, f"foto_{tag or user_id}_{ts}.jpg")
            archivo = await context.bot.get_file(foto.file_id)
            await archivo.download_to_drive(dest_path)

            # Registrar en la base de datos
            db.registrar_foto(
                ruta=dest_path,
                animal_tag=tag,
                caption=caption or None,
                user_id=user_id,
                fecha=date.today().isoformat(),
            )

            # Si el caption contiene un evento zootécnico (ej. 'pario la 47 macho'), procesarlo también
            if caption and nlu.clasificar(caption) is not None:
                bot_engine = Bot(db)
                resp_evento = bot_engine.procesar_texto(caption)
                await update.message.reply_text(
                    f"📷 Foto registrada y vinculada a {tag or 'evento'}.\n\n{resp_evento}"
                )
            elif tag:
                await update.message.reply_text(f"📷 Foto guardada y vinculada a la {tag}.")
            else:
                await update.message.reply_text("📷 Foto recibida y guardada en la bitácora.")
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
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            raw_text = update.message.text or ""
            # Limpiar posibles timestamps de copy-paste (ej. 10:13 PM)
            clean_text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b", "", raw_text, flags=re.IGNORECASE).strip()

            tag = None
            if context.args:
                arg0 = context.args[0]
                # Si el timestamp quedó adherido (ej. N06910:13)
                arg_clean = re.sub(r"\d{1,2}:\d{2}.*", "", arg0, flags=re.IGNORECASE).strip()
                tag = arg_clean or arg0
            if not tag:
                tag = nlu.extraer_tag(clean_text)

            if not tag:
                await update.message.reply_text("Uso: /consulta <tag> o /historial <tag> (ej. /consulta N069)")
                return

            msg = formatear_historial(db, tag)
            try:
                await update.message.reply_text(msg, parse_mode="HTML")
            except Exception:
                await update.message.reply_text(msg)

            # Botón para ver fotos si el animal tiene registros fotográficos
            fotos = db.fotos_de(tag)
            if fotos:
                n_fotos = len(fotos)
                keyboard = [
                    [
                        InlineKeyboardButton(
                            f"📷 Ver foto ({n_fotos})",
                            callback_data=f"foto:{tag}",
                        )
                    ]
                ]
                await update.message.reply_text(
                    f"📷 Este animal tiene {n_fotos} foto(s) disponible(s).",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
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
            arg_potrero = " ".join(context.args).strip() if context.args else None
            msg = formatear_potreros(db, potrero=arg_potrero)
            try:
                await update.message.reply_text(msg, parse_mode="HTML")
            except Exception:
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
            await update.message.reply_text(msg, parse_mode="HTML")
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

    async def cmd_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            parsed = parsear_args_reporte(context.args)
            if parsed is None:
                await update.message.reply_text(
                    "Uso: /reporte (semanal por defecto) · /reporte diario · /reporte <N> días"
                )
                return

            dias, etiqueta = parsed
            # Import perezoso para no requerir reportlab salvo que se use /reporte.
            from ..reports import generar_pdf

            fecha_hoy = date.today()
            ruta = os.path.join(reportes_dir, f"reporte_{etiqueta}_{fecha_hoy.isoformat()}.pdf")
            generar_pdf(db, dias, ruta, hoy=fecha_hoy)
            with open(ruta, "rb") as f:
                contenido = f.read()
            await update.message.reply_document(
                document=contenido, filename=os.path.basename(ruta)
            )
        except Exception as e:
            logger.error("Error en cmd_reporte: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al generar el reporte: {e}")

    async def cmd_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            tag = context.args[0].strip() if context.args else None
            if tag:
                filas = db.fotos_de(tag, limit=3)
                if not filas:
                    await update.message.reply_text(f"📷 No hay fotos registradas para el animal {tag}.")
                    return
                for r in filas:
                    ruta = r["ruta"]
                    fec = r["fecha"] or "sin fecha"
                    cap = f" ({r['caption']})" if r["caption"] else ""
                    pie = f"📷 Animal {tag} - {fec}{cap}"
                    if os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            await update.message.reply_photo(photo=f, caption=pie)
                    else:
                        await update.message.reply_text(f"📷 Registro de foto ({fec}), pero el archivo local no está disponible.")
            else:
                # Mostrar últimas fotos registradas
                filas = db.ultimas_fotos(limit=5)
                if not filas:
                    await update.message.reply_text("📷 No hay fotos registradas en la bitácora.")
                    return
                for r in filas:
                    ruta = r["ruta"]
                    tag_foto = r["tag"] or "Sin tag"
                    fec = r["fecha"] or "sin fecha"
                    cap = f" - {r['caption']}" if r["caption"] else ""
                    pie = f"📷 Tag {tag_foto} [{fec}]{cap}"
                    if os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            await update.message.reply_photo(photo=f, caption=pie)
                    else:
                        await update.message.reply_text(f"📷 Foto {tag_foto} [{fec}] (archivo no disponible en servidor).")
        except Exception as e:
            logger.error("Error en cmd_fotos: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al consultar fotos: {e}")

    async def cmd_exportar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            from ..exporters import (
                export_csv_zip,
                export_json_zip,
                export_zip,
                parsear_args_exportar,
            )

            parsed = parsear_args_exportar(context.args)
            if parsed is None:
                await update.message.reply_text(
                    "Uso: /exportar (DBF/Software Ganadero por defecto) · /exportar csv · /exportar json"
                )
                return

            formato, etiqueta = parsed
            exports_dir = os.path.join(os.path.dirname(uploads_dir), "exports")
            os.makedirs(exports_dir, exist_ok=True)
            hoy_str = date.today().strftime("%Y%m%d")

            if formato == "dbf":
                ruta_zip = os.path.join(exports_dir, f"Datos_Export_{hoy_str}.Zip")
                zip_generado = export_zip(db, ruta_zip)
                desc = "📦 Exportación para Software Ganadero SG (8 tablas DBF)."
            elif formato == "csv":
                ruta_zip = os.path.join(exports_dir, f"bitacora_csv_{hoy_str}.zip")
                zip_generado = export_csv_zip(db, ruta_zip)
                desc = "📊 Exportación de bitácora en formato CSV (todas las tablas)."
            elif formato == "json":
                ruta_zip = os.path.join(exports_dir, f"bitacora_json_{hoy_str}.zip")
                zip_generado = export_json_zip(db, ruta_zip)
                desc = "📄 Exportación de bitácora en formato JSON."
            else:
                ruta_zip = os.path.join(exports_dir, f"Datos_Export_{hoy_str}.Zip")
                zip_generado = export_zip(db, ruta_zip)
                desc = "📦 Exportación para Software Ganadero SG."

            with open(zip_generado, "rb") as f:
                contenido = f.read()

            tam_mb = len(contenido) / (1024 * 1024)
            await update.message.reply_document(
                document=contenido,
                filename=os.path.basename(zip_generado),
                caption=f"{desc} ({tam_mb:.2f} MB)",
            )
        except Exception as e:
            logger.error("Error en cmd_exportar: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al exportar: {e}")

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

    async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            query = update.callback_query
            if not query or not query.data:
                return
            user_id = update.effective_user.id if update.effective_user else 0
            if not auth.es_autorizado(user_id):
                await query.answer("⛔ No autorizado.", show_alert=True)
                return

            data = query.data
            if data.startswith("foto:"):
                tag = data.split("foto:", 1)[1].strip()
                await query.answer()
                filas = db.fotos_de(tag, limit=5)
                if not filas:
                    if query.message:
                        await query.message.reply_text(f"📷 No hay fotos registradas para el animal {tag}.")
                    return
                for r in filas:
                    ruta = r["ruta"]
                    fec = r["fecha"] or "sin fecha"
                    cap = f" ({r['caption']})" if r.get("caption") else ""
                    pie = f"📷 Animal {tag} - {fec}{cap}"
                    if ruta and os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            if query.message:
                                await query.message.reply_photo(photo=f, caption=pie)
                    else:
                        if query.message:
                            await query.message.reply_text(
                                f"📷 Foto {tag} [{fec}] (archivo no disponible en servidor)."
                            )

            elif data == "cmd:inventario":
                await query.answer()
                msg = formatear_animales(db)
                if query.message:
                    await query.message.reply_text(msg)

            elif data == "cmd:historial":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "📋 Para consultar la ficha de un animal, escribe:\n/historial <tag> (ej. /historial 47) o directamente el número de arete."
                    )

            elif data == "cmd:ayuda":
                await query.answer()
                rol = auth.rol_de(user_id)
                if query.message:
                    await query.message.reply_text(formatear_ayuda(rol))

        except Exception as e:
            logger.error("Error en handle_callback_query: %s", e, exc_info=True)
            if query and query.message:
                await query.message.reply_text(f"❌ Error: {e}")

    app = ApplicationBuilder().token(token).build()

    # Handlers de comandos
    app.add_handler(CommandHandler(["start", "help"], cmd_start_help))
    app.add_handler(CommandHandler("alertas", cmd_alertas))
    app.add_handler(CommandHandler(["historial", "consulta", "ficha", "info", "vaca", "animal", "buscar"], cmd_historial))
    app.add_handler(CommandHandler("potreros", cmd_potreros))
    app.add_handler(CommandHandler("animales", cmd_animales))
    app.add_handler(CommandHandler(["foto", "fotos"], cmd_fotos))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("usuarios", cmd_usuarios))
    app.add_handler(CommandHandler("reporte", cmd_reporte))
    app.add_handler(CommandHandler("exportar", cmd_exportar))
    app.add_handler(CommandHandler("importar", cmd_importar))
    app.add_handler(CommandHandler("confirmar_importar", cmd_confirmar_importar))
    app.add_handler(CommandHandler("descartar_backup", cmd_descartar_backup))
    app.add_handler(CommandHandler("agregar_usuario", cmd_agregar_usuario))
    app.add_handler(CommandHandler("quitar_usuario", cmd_quitar_usuario))
    app.add_handler(CommandHandler("logs", cmd_logs))

    # Handlers de callbacks y mensajes
    app.add_handler(CallbackQueryHandler(handle_callback_query))
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
    reportes_dir: Optional[str] = None,
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
    reportes_dir = reportes_dir or os.getenv("REPORTES_DIR", "data/reportes")

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
        reportes_dir=reportes_dir,
    )
    logger.info("Bot de Telegram iniciado correctamente con polling...")
    app.run_polling(drop_pending_updates=True)
