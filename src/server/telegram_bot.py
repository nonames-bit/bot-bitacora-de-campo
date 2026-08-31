"""Bot de Telegram multiusuario con control de acceso basado en roles (RBAC)."""
from __future__ import annotations

import html
import logging
import os
import re
import sys
import time
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from ..bot.bot_interface import Bot
from ..db.database import Database
from ..engine.charts import (
    generar_grafico_aforo_potreros,
    generar_grafico_carga_animal_potrero,
    generar_grafico_categorias,
    generar_grafico_dias_abiertos_km,
    generar_grafico_eficiencia_lechera,
    generar_grafico_estado_reproductivo_hato,
    generar_grafico_evolucion_rebano,
    generar_grafico_gmd_hato,
    generar_grafico_iep_boxplot,
    generar_grafico_iep_boxplot_completo,
    generar_grafico_lactancia,
    generar_grafico_leche_total_hato,
    generar_grafico_ocupacion_potreros,
    generar_grafico_peso,
    generar_grafico_peso_destete_por_raza,
    generar_grafico_prenadas_vacias_potrero,
    generar_grafico_ranking_vacas_leche,
    generar_grafico_rendimiento_padre,
    generar_grafico_waterfall_inventario,
    graficos_disponibles,
)
from ..engine.query_engine import (
    QueryEngine,
    buscar_foto_animal,
    calcular_brackets_inventario_sg,
    calcular_existencias_potreros_sg,
    generar_resumen_inventario_sg,
)
from ..importers.dbf_importer import import_zip
from ..parsers import nlp_engine as nlu
from ..parsers.media_handler import (MediaError, extract_image_info,
                                      transcribe_audio)
from ..utils import add_days, iso, to_date
from .auth import Auth

logger = logging.getLogger("bitacora.bot")



from .formatters import (
    _contar_activos,
    _fmt_es_co,
    _obtener_fecha_ultimo_backup,
    descartar_backup_pendiente,
    formatear_alertas,
    formatear_alertas_panel,
    formatear_animales,
    formatear_ayuda,
    formatear_despacho_matutino,
    formatear_duplicados_geneticos,
    formatear_estado_servidor,
    formatear_fotos,
    formatear_genealogia_animal_tab,
    formatear_genetica_panel,
    formatear_historial,
    formatear_instrucciones_importar,
    formatear_leche_animal_tab,
    formatear_panel_buscar_animal_texto,
    formatear_panel_medicamentos,
    formatear_panel_preguntas_rapidas_texto,
    formatear_pesajes_animal_tab,
    formatear_poblacion_panel,
    formatear_potreros,
    formatear_reporte_importacion,
    formatear_reprod_animal_tab,
    formatear_sanidad_animal_tab,
    formatear_status,
    formatear_tablero_finca,
    formatear_ultimos_registros,
    formatear_usuarios,
    guardar_backup_pendiente,
    obtener_backup_pendiente,
    obtener_ultimos_logs,
    parsear_args_reporte,
    texto_ejemplo_evento,
    texto_guia_animal,
    texto_guia_audios,
    texto_guia_chat_hub,
    texto_guia_consultas,
    texto_guia_fotos,
    texto_guia_preguntas_animal,
    texto_guia_preguntas_potreros,
    texto_guia_preguntas_reproduccion,
    texto_guia_preguntas_sanidad,
    texto_guia_voz_fotos,
    texto_menu_principal,
)


# ---------------------------------------------------------------------- #
# Gráficos generales de la finca (menú /graficos): tipo -> (generador, título)
# ---------------------------------------------------------------------- #
GRAFICOS_PANEL = {
    "evolucion": (generar_grafico_evolucion_rebano, "📈 Evolución del Rebaño (últimos 12 meses)"),
    "waterfall": (generar_grafico_waterfall_inventario, "🌊 Waterfall de Inventario Mensual"),
    "categorias": (generar_grafico_categorias, "🥧 Distribución del Hato por Categorías"),
    "gmd": (generar_grafico_gmd_hato, "⚖️ Ganancia Media Diaria del Hato"),
    "iep": (generar_grafico_iep_boxplot, "📦 Intervalo Entre Partos (IEP, últimos 2 años)"),
    "iep_completo": (generar_grafico_iep_boxplot_completo, "📦 Intervalo Entre Partos (IEP, histórico completo sin filtrar)"),
    "destete_raza": (generar_grafico_peso_destete_por_raza, "🐄 Peso al Destete por Raza"),
    "padre": (generar_grafico_rendimiento_padre, "🐂 Rendimiento por Padre/Reproductor"),
    "aforo": (generar_grafico_aforo_potreros, "🌱 Aforo de Forraje por Potrero"),
    "ocupacion": (generar_grafico_ocupacion_potreros, "🔄 Ocupación de Potreros (Voisin)"),
    "prenadas": (generar_grafico_prenadas_vacias_potrero, "🤰 Preñadas vs Vacías por Potrero (estimado)"),
    "dias_abiertos_km": (generar_grafico_dias_abiertos_km, "📉 Días Abiertos (curva de Kaplan-Meier)"),
    "leche_total": (generar_grafico_leche_total_hato, "🥛 Producción Total de Leche del Hato"),
    "eficiencia_lechera": (generar_grafico_eficiencia_lechera, "⚡ Eficiencia Lechera del Hato"),
    "ranking_leche": (generar_grafico_ranking_vacas_leche, "🏆 Ranking de Vacas por Producción"),
    "reproductivo_hato": (generar_grafico_estado_reproductivo_hato, "🧬 Estado Reproductivo del Hato"),
    "carga_animal": (generar_grafico_carga_animal_potrero, "🐄 Carga Animal por Potrero (UGG/ha)"),
}


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

    from .keyboards import (
        crear_teclado_admin,
        crear_teclado_alertas,
        crear_teclado_alertas_detalle,
        crear_teclado_animal,
        crear_teclado_animal_detalle,
        crear_teclado_buscar_animal,
        crear_teclado_despacho_matutino,
        crear_teclado_ejemplos,
        crear_teclado_grafico_detalle,
        crear_teclado_graficos,
        crear_teclado_guia_chat,
        crear_teclado_medicamentos,
        crear_teclado_poblacion,
        crear_teclado_poblacion_detalle,
        crear_teclado_preguntas_rapidas,
        crear_teclado_principal,
        crear_teclado_trabajador,
    )

    async def _enviar_texto_seguro(
        target,
        texto: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        limite: int = 4000,
    ) -> None:
        """Envía un mensaje dividiéndolo limpiamente en bloques <= 4000 caracteres si excede el límite de Telegram."""
        if not texto:
            return
        if len(texto) <= limite:
            try:
                if hasattr(target, "reply_text"):
                    await target.reply_text(texto, parse_mode=parse_mode, reply_markup=reply_markup)
                elif hasattr(target, "message") and target.message:
                    await target.message.reply_text(texto, parse_mode=parse_mode, reply_markup=reply_markup)
                return
            except Exception as exc:
                if parse_mode == "HTML" and "parse" in str(exc).lower():
                    logger.warning("Fallo al enviar mensaje HTML, reintentando como texto plano: %s", exc)
                    if hasattr(target, "reply_text"):
                        await target.reply_text(texto, reply_markup=reply_markup)
                    elif hasattr(target, "message") and target.message:
                        await target.message.reply_text(texto, reply_markup=reply_markup)
                    return
                raise

        partes: list[str] = []
        bloque_actual = []
        longitud_actual = 0
        for linea in texto.split("\n"):
            if longitud_actual + len(linea) + 1 > limite and bloque_actual:
                partes.append("\n".join(bloque_actual))
                bloque_actual = [linea]
                longitud_actual = len(linea)
            else:
                bloque_actual.append(linea)
                longitud_actual += len(linea) + 1
        if bloque_actual:
            partes.append("\n".join(bloque_actual))

        for i, parte in enumerate(partes):
            mk = reply_markup if i == len(partes) - 1 else None
            try:
                if hasattr(target, "reply_text"):
                    await target.reply_text(parte, parse_mode=parse_mode, reply_markup=mk)
                elif hasattr(target, "message") and target.message:
                    await target.message.reply_text(parte, parse_mode=parse_mode, reply_markup=mk)
            except Exception as exc:
                if parse_mode == "HTML" and "parse" in str(exc).lower():
                    if hasattr(target, "reply_text"):
                        await target.reply_text(parte, reply_markup=mk)
                    elif hasattr(target, "message") and target.message:
                        await target.message.reply_text(parte, reply_markup=mk)
                else:
                    raise

    async def cmd_start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            rol = auth.rol_de(user_id)
            texto_menu = texto_menu_principal(rol)
            teclado = crear_teclado_principal(rol)
            await _enviar_texto_seguro(update.message, texto_menu, parse_mode="HTML", reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_start_menu: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_ayuda_completa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            rol = auth.rol_de(user_id)
            texto_ayuda = formatear_ayuda(rol)
            teclado = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Abrir Menú", callback_data="menu:principal")]])
            await _enviar_texto_seguro(update.message, texto_ayuda, parse_mode="HTML", reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_ayuda_completa: %s", e, exc_info=True)
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
            respuesta = bot_engine.procesar_texto(raw_text, user_id=user_id)

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

            if "FICHA ZOOTÉCNICA" in respuesta:
                tag = nlu.extraer_tag(raw_text)
                if not tag:
                    m_tag = re.search(r"(?:🐄|🐮|🐂|🍼)\s*(?:Vaca|Toro|Novilla|Ternero|Ternera|Novillo|Cría|Cria)?\s*([A-Za-z0-9\-_]+)", respuesta)
                    if m_tag:
                        tag = m_tag.group(1).strip()
                if tag:
                    try:
                        db.registrar_consulta_animal(tag)
                    except Exception:
                        pass
                    foto_path = buscar_foto_animal(db, tag, media_dir=media_dir)
                    teclado = crear_teclado_animal(tag)
                    if foto_path and os.path.exists(foto_path):
                        try:
                            with open(foto_path, "rb") as f:
                                if len(respuesta) <= 1024:
                                    await update.message.reply_photo(
                                        photo=f, caption=respuesta, parse_mode="HTML", reply_markup=teclado
                                    )
                                    return
                                else:
                                    await update.message.reply_text(respuesta, parse_mode="HTML")
                                    with open(foto_path, "rb") as f2:
                                        await update.message.reply_photo(
                                            photo=f2, caption=f"📷 Foto del animal {tag}", reply_markup=teclado
                                        )
                                    return
                        except Exception as ef:
                            logger.warning("Error al enviar foto en handle_texto para %s: %s", tag, ef)
                    try:
                        await update.message.reply_text(respuesta, parse_mode="HTML", reply_markup=teclado)
                    except Exception:
                        await update.message.reply_text(respuesta, reply_markup=teclado)
                    return

            if "<pre>" in respuesta or "<b>" in respuesta:
                try:
                    await update.message.reply_text(respuesta, parse_mode="HTML")
                except Exception:
                    await update.message.reply_text(respuesta)
            else:
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

            bot_engine = Bot(db)
            try:
                transcript = transcribe_audio(dest_path)
                texto_audio = transcript.texto.strip()
                if texto_audio:
                    resp_evento = bot_engine.procesar_texto(texto_audio, user_id=user_id)
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

            # Extraer información visual con OCR
            ocr_text = ""
            ocr_tags = []
            ocr_med = None
            try:
                img_info = extract_image_info(dest_path)
                ocr_text = img_info.ocr_text or img_info.texto_detectado or ""
                ocr_tags = img_info.tags
                ocr_med = img_info.medicamento
                if not tag and ocr_tags:
                    tag = ocr_tags[0]
            except Exception:
                pass

            # Registrar en la base de datos
            db.registrar_foto(
                ruta=dest_path,
                animal_tag=tag,
                caption=caption or None,
                user_id=user_id,
                fecha=date.today().isoformat(),
                ocr_text=ocr_text or None,
            )

            # Construir texto consolidado para NLU
            texto_consolidado = f"{caption} {ocr_text}".strip() if caption else ocr_text

            # Mensajes de detección OCR para feedback al usuario
            ocr_feedback = []
            if ocr_tags:
                ocr_feedback.append(f"🔍 OCR detectó tag {', '.join(ocr_tags)}")
            if ocr_med and ocr_med.get("producto"):
                detalles_med = [ocr_med['producto']]
                if ocr_med.get("dosis"):
                    detalles_med.append(f"dosis {ocr_med['dosis']}")
                if ocr_med.get("via"):
                    detalles_med.append(f"vía {ocr_med['via']}")
                if ocr_med.get("lote"):
                    detalles_med.append(f"lote {ocr_med['lote']}")
                ocr_feedback.append(f"💊 OCR detectó medicamento: {', '.join(detalles_med)}")

            str_feedback = ("\n" + "\n".join(ocr_feedback)) if ocr_feedback else ""

            # Si el caption o OCR contiene un evento zootécnico (ej. 'pario la 47 macho'), procesarlo también
            if texto_consolidado and nlu.clasificar(texto_consolidado) is not None:
                bot_engine = Bot(db)
                resp_evento = bot_engine.procesar_texto(texto_consolidado, user_id=user_id)
                await update.message.reply_text(
                    f"📷 Foto registrada y vinculada a {tag or 'evento'}.{str_feedback}\n\n{resp_evento}"
                )
            elif tag:
                await update.message.reply_text(f"📷 Foto guardada y vinculada a la {tag}.{str_feedback}")
            else:
                await update.message.reply_text(f"📷 Foto recibida y guardada en la bitácora.{str_feedback}")
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

    async def cmd_despacho(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_despacho_matutino(db)
            await _enviar_texto_seguro(
                update.message,
                msg,
                parse_mode="HTML",
                reply_markup=crear_teclado_despacho_matutino(),
            )
        except Exception as e:
            logger.error("Error en cmd_despacho: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_leche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            args = context.args or []
            if not args:
                await update.message.reply_text("🥛 Uso: /leche <litros>  ej. /leche 475\nO pulsa 🥛 Registrar Leche Hoy y escribe el total del día.")
                return
            try:
                litros = float(args[0].replace(",", "."))
            except ValueError:
                await update.message.reply_text("❌ Litros inválido. Ej: /leche 475 o /leche 475.5")
                return
            fecha_hoy = date.today().isoformat()
            db.registrar_leche(animal_tag=None, fecha=fecha_hoy, litros=litros, registrado_por=user_id)
            await update.message.reply_text(f"✅ Leche registrada: <b>{litros} L</b> el {fecha_hoy} (total hato)", parse_mode="HTML")
        except Exception as e:
            logger.error("Error en cmd_leche: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_programar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            texto = " ".join(context.args or []).strip()
            if not texto:
                await update.message.reply_text("⏰ Uso: /programar YYYY-MM-DD HH:MM mensaje\nEj: /programar 2026-09-01 08:00 Rotar potrero Bajo a Guayabal\nO usa el botón ⏰ Programar Recordatorio.")
                return
            partes = texto.split(maxsplit=2)
            if len(partes) < 3:
                await update.message.reply_text("❌ Formato incompleto. Ej: /programar 2026-09-01 08:00 Rotar potrero")
                return
            fecha, hora, mensaje = partes[0], partes[1], partes[2]
            # validación básica
            from datetime import datetime as _dt
            try:
                _dt.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            except ValueError:
                await update.message.reply_text("❌ Fecha/hora inválida. Usa YYYY-MM-DD HH:MM")
                return
            rid = db.registrar_recordatorio(mensaje=mensaje, fecha_programada=fecha, hora=hora, creado_por=user_id)
            await update.message.reply_text(f"✅ Recordatorio #{rid} programado para <b>{fecha} {hora}</b>:\n<i>{html.escape(mensaje)}</i>", parse_mode="HTML")
        except Exception as e:
            logger.error("Error en cmd_programar: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_alertas_panel(db)
            await update.message.reply_text(
                msg, parse_mode="HTML", reply_markup=crear_teclado_alertas()
            )
        except Exception as e:
            logger.error("Error en cmd_alertas: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_poblacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_poblacion_panel(db)
            await update.message.reply_text(
                msg, parse_mode="HTML", reply_markup=crear_teclado_poblacion()
            )
        except Exception as e:
            logger.error("Error en cmd_poblacion: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_genetica(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_genetica_panel(db)
            await update.message.reply_text(
                msg, parse_mode="HTML", reply_markup=crear_teclado_poblacion_detalle()
            )
        except Exception as e:
            logger.error("Error en cmd_genetica: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_duplicados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            grupos = db.detectar_duplicados_geneticos()
            msg = formatear_duplicados_geneticos(grupos)
            await _enviar_texto_seguro(update.message, msg, parse_mode="HTML")
        except Exception as e:
            logger.error("Error en cmd_duplicados: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_ultimos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            filas = db.ultimos_registros(15)
            msg = formatear_ultimos_registros(filas, auth=auth)
            await _enviar_texto_seguro(update.message, msg, parse_mode="HTML")
        except Exception as e:
            logger.error("Error en cmd_ultimos: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_deshacer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            if not context.args or len(context.args) < 2:
                await update.message.reply_text(
                    "Uso: /deshacer <tabla> <id> (ver /ultimos para los comandos exactos)."
                )
                return
            tabla, id_txt = context.args[0], context.args[1]
            try:
                id_registro = int(id_txt)
            except ValueError:
                await update.message.reply_text("El id debe ser un número. Revisa /ultimos.")
                return

            detalle = db.detalle_registro(tabla, id_registro)
            if detalle is None:
                await update.message.reply_text(
                    "⚠️ No encontré ese registro (o la tabla no es válida). Revisa /ultimos."
                )
                return

            context.user_data["deshacer_pendiente"] = {"tabla": tabla, "id": id_registro}
            await update.message.reply_text(
                f"⚠️ Vas a borrar definitivamente:\n\n<b>{detalle['resumen']}</b>\n"
                f"Fecha: {detalle['fecha']}\n\n"
                "Esto NO se puede deshacer desde el chat. Responde /confirmar_deshacer para borrarlo "
                "o /cancelar_deshacer para dejarlo como está.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Error en cmd_deshacer: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_confirmar_deshacer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            pendiente = context.user_data.get("deshacer_pendiente")
            if not pendiente:
                await update.message.reply_text("⚠️ No hay ningún /deshacer pendiente de confirmar.")
                return
            ok = db.eliminar_registro(pendiente["tabla"], pendiente["id"])
            context.user_data.pop("deshacer_pendiente", None)
            if ok:
                await update.message.reply_text("🗑️ Registro eliminado.")
            else:
                await update.message.reply_text("⚠️ Ese registro ya no existía (quizás borrado desde otro chat).")
        except Exception as e:
            logger.error("Error en cmd_confirmar_deshacer: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_cancelar_deshacer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            if context.user_data.pop("deshacer_pendiente", None):
                await update.message.reply_text("✅ Cancelado. No se borró nada.")
            else:
                await update.message.reply_text("No había ningún /deshacer pendiente.")
        except Exception as e:
            logger.error("Error en cmd_cancelar_deshacer: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_renombrar_animal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            if len(context.args) != 2:
                await update.message.reply_text(
                    "Uso: /renombrar_animal <tag_viejo> <tag_nuevo>\n"
                    "Ej. /renombrar_animal A090-6 B234\n\n"
                    "Úselo cuando una cría tenía el código temporal que asigna "
                    "Software Ganadero al nacer y ya le pusieron la chapeta "
                    "definitiva: conserva todo el historial ya registrado."
                )
                return
            tag_viejo, tag_nuevo = context.args
            if db.animal_id(tag_viejo) is None:
                await update.message.reply_text(f"⚠️ No existe ningún animal con el tag «{tag_viejo}».")
                return
            if db.animal_id(tag_nuevo) is not None:
                await update.message.reply_text(f"⚠️ Ya existe un animal con el tag «{tag_nuevo}». No se puede renombrar.")
                return
            aid = db.renombrar_animal(tag_viejo, tag_nuevo)
            if aid is None:
                await update.message.reply_text("❌ No se pudo renombrar el animal.")
                return
            await update.message.reply_text(
                f"🏷️ Listo: «{tag_viejo}» ahora es «{tag_nuevo}» (se conservó todo su historial).",
                reply_markup=crear_teclado_animal(tag_nuevo),
            )
        except Exception as e:
            logger.error("Error en cmd_renombrar_animal: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_guia_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = texto_guia_chat_hub()
            await update.message.reply_text(
                msg, parse_mode="HTML", reply_markup=crear_teclado_guia_chat()
            )
        except Exception as e:
            logger.error("Error en cmd_guia_chat: %s", e, exc_info=True)
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

            try:
                db.registrar_consulta_animal(tag)
            except Exception:
                pass

            msg = formatear_historial(db, tag)
            teclado = crear_teclado_animal(tag)
            foto_path = buscar_foto_animal(db, tag, media_dir=media_dir)

            if foto_path and os.path.exists(foto_path):
                try:
                    with open(foto_path, "rb") as f:
                        if len(msg) <= 1024:
                            await update.message.reply_photo(
                                photo=f, caption=msg, parse_mode="HTML", reply_markup=teclado
                            )
                            return
                        else:
                            await update.message.reply_text(msg, parse_mode="HTML")
                            with open(foto_path, "rb") as f2:
                                await update.message.reply_photo(
                                    photo=f2, caption=f"📷 Foto del animal {tag}", reply_markup=teclado
                                )
                            return
                except Exception as efoto:
                    logger.warning("Error al enviar foto para animal %s: %s", tag, efoto)

            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado)
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
            teclado_p = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Existencias SG", callback_data="cmd:potreros_sg"),
                    InlineKeyboardButton("⏳ Días Ocupación", callback_data="cmd:ocupacion"),
                ],
                [
                    InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                    InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                ],
            ])
            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado_p)
        except Exception as e:
            logger.error("Error en cmd_potreros: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            qe = QueryEngine(db)
            msg = qe.responder("dias de ocupacion")
            teclado_p = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Existencias SG", callback_data="cmd:potreros_sg"),
                    InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                ],
                [
                    InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                ],
            ])
            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado_p)
        except Exception as e:
            logger.error("Error en cmd_ocupacion: %s", e, exc_info=True)
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
            try:
                await update.message.reply_text(msg, parse_mode="HTML")
            except Exception:
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
            msg = formatear_tablero_finca(db)
            teclado = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Inventario Hato", callback_data="cmd:inventario"),
                    InlineKeyboardButton("⚠️ Alertas Pendientes", callback_data="cmd:alertas"),
                ],
                [
                    InlineKeyboardButton("🌿 Potreros Voisin", callback_data="cmd:potreros"),
                    InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                ],
                [
                    InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                ],
            ])
            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_status: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_sistema(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_estado_servidor(db, auth, db.path if hasattr(db, "path") else None)
            teclado = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
                    InlineKeyboardButton("👥 Usuarios / Permisos", callback_data="cmd:usuarios"),
                ],
                [
                    InlineKeyboardButton("📜 Ver Últimos Logs", callback_data="cmd:logs"),
                    InlineKeyboardButton("📦 Descargar Backup ZIP", callback_data="cmd:exportar"),
                ],
                [
                    InlineKeyboardButton("🔄 Actualizar", callback_data="cmd:sistema"),
                    InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                ],
            ])
            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_sistema: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_medicamentos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_panel_medicamentos(db)
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_medicamentos())
        except Exception as e:
            logger.error("Error en cmd_medicamentos: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_buscar_animal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_panel_buscar_animal_texto()
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_buscar_animal(db))
        except Exception as e:
            logger.error("Error en cmd_buscar_animal: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_preguntas_rapidas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_panel_preguntas_rapidas_texto()
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_preguntas_rapidas())
        except Exception as e:
            logger.error("Error en cmd_preguntas_rapidas: %s", e, exc_info=True)
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
                filas = db.fotos_de(tag, limit=5)
                foto_disco = buscar_foto_animal(db, tag, media_dir=media_dir)
                if not filas and not foto_disco:
                    await update.message.reply_text(f"📷 No hay fotos registradas para el animal {tag}.")
                    return

                enviadas = 0
                for r in filas:
                    ruta = r["ruta"]
                    fec = r["fecha"] or "sin fecha"
                    cap = f" — {r['caption']}" if r["caption"] else ""
                    pie = f"📷 Animal {tag} [{fec}]{cap}"
                    if ruta and os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            await update.message.reply_photo(photo=f, caption=pie)
                            enviadas += 1

                if foto_disco and os.path.exists(foto_disco) and enviadas == 0:
                    with open(foto_disco, "rb") as f:
                        await update.message.reply_photo(photo=f, caption=f"📷 Foto del animal {tag}")
            else:
                # Mostrar últimas fotos registradas
                filas = db.ultimas_fotos(limit=5)
                if not filas:
                    await update.message.reply_text("📷 No hay fotos registradas en la bitácora.")
                    return
                for r in filas:
                    ruta = r["ruta"]
                    tag_foto = r["tag"] or "Sin arete"
                    fec = r["fecha"] or "sin fecha"
                    cap = f" — {r['caption']}" if r["caption"] else ""
                    pie = f"📷 Tag {tag_foto} [{fec}]{cap}"
                    if ruta and os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            await update.message.reply_photo(photo=f, caption=pie)
                    else:
                        await update.message.reply_text(f"📷 Foto {tag_foto} [{fec}] (archivo no disponible en servidor).")
        except Exception as e:
            logger.error("Error en cmd_fotos: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al consultar fotos: {e}")

    async def cmd_grafico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            tag = context.args[0].strip() if context.args else (nlu.extraer_tag(update.message.text or "") or None)
            if not tag:
                await update.message.reply_text("Uso: /grafico <tag> (ej. /grafico N069)")
                return
            if not graficos_disponibles():
                await update.message.reply_text(
                    "📈 Los gráficos no están disponibles en este servidor (falta matplotlib)."
                )
                return
            ruta_grafico = generar_grafico_peso(db, tag, output_dir=reportes_dir)
            if ruta_grafico and os.path.exists(ruta_grafico):
                with open(ruta_grafico, "rb") as f:
                    await update.message.reply_photo(
                        photo=f, caption=f"📈 Curva de crecimiento — {tag}",
                        reply_markup=crear_teclado_animal_detalle(tag),
                    )
            else:
                await update.message.reply_text(
                    f"📈 No hay suficientes pesajes registrados para graficar a {tag} (se necesitan al menos 2)."
                )
        except Exception as e:
            logger.error("Error en cmd_grafico: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al generar el gráfico: {e}")

    async def cmd_grafico_leche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            tag = context.args[0].strip() if context.args else (nlu.extraer_tag(update.message.text or "") or None)
            if not tag:
                await update.message.reply_text("Uso: /grafico_leche <tag> (ej. /grafico_leche N069)")
                return
            if not graficos_disponibles():
                await update.message.reply_text(
                    "📉 Los gráficos no están disponibles en este servidor (falta matplotlib)."
                )
                return
            ruta_grafico = generar_grafico_lactancia(db, tag, output_dir=reportes_dir)
            if ruta_grafico and os.path.exists(ruta_grafico):
                with open(ruta_grafico, "rb") as f:
                    await update.message.reply_photo(
                        photo=f, caption=f"📉 Curva de lactancia — {tag}",
                        reply_markup=crear_teclado_animal_detalle(tag),
                    )
            else:
                await update.message.reply_text(
                    f"📉 No hay suficientes controles de leche registrados para {tag} "
                    "(se necesitan al menos 2, y conocer su fecha de último parto)."
                )
        except Exception as e:
            logger.error("Error en cmd_grafico_leche: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al generar el gráfico: {e}")

    async def cmd_graficos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            await update.message.reply_text(
                "📊 <b>Gráficos de la Finca</b>\n\nElige un gráfico:",
                parse_mode="HTML", reply_markup=crear_teclado_graficos(),
            )
        except Exception as e:
            logger.error("Error en cmd_graficos: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

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
            await _enviar_texto_seguro(update.message, msg)
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
            if data.startswith("noop") or data.startswith("section:"):
                await query.answer()
                return

            if data == "menu:principal":
                await query.answer()
                rol = auth.rol_de(user_id)
                if query.message:
                    await query.message.reply_text(
                        texto_menu_principal(rol), parse_mode="HTML", reply_markup=crear_teclado_principal(rol)
                    )

            elif data == "menu:campo":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "🤠 <b>Modo Guía de Campo (Personal de Campo):</b>\nSeleccione una opción didáctica de ayuda o consulta:",
                        parse_mode="HTML",
                        reply_markup=crear_teclado_trabajador(),
                    )

            elif data == "guia:consultas":
                await query.answer()
                btn = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        texto_guia_consultas(),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "guia:chat_hub":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        texto_guia_chat_hub(),
                        parse_mode="HTML",
                        reply_markup=crear_teclado_guia_chat(),
                    )

            elif data in (
                "guia:preguntas_animal", "guia:preguntas_potreros",
                "guia:preguntas_reprod", "guia:preguntas_sanidad", "guia:voz_fotos",
            ):
                await query.answer()
                textos_guia_categoria = {
                    "guia:preguntas_animal": texto_guia_preguntas_animal,
                    "guia:preguntas_potreros": texto_guia_preguntas_potreros,
                    "guia:preguntas_reprod": texto_guia_preguntas_reproduccion,
                    "guia:preguntas_sanidad": texto_guia_preguntas_sanidad,
                    "guia:voz_fotos": texto_guia_voz_fotos,
                }
                btn = [
                    [
                        InlineKeyboardButton("⬅️ Volver a Guía de Chat", callback_data="guia:chat_hub"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ]
                if query.message:
                    await query.message.reply_text(
                        textos_guia_categoria[data](),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "guia:fotos":
                await query.answer()
                btn = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        texto_guia_fotos(),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "guia:audios":
                await query.answer()
                btn = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        texto_guia_audios(),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "guia:animal":
                await query.answer()
                btn = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        texto_guia_animal(),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "cmd:ejemplos":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "💡 <b>Ejemplos de Notas de Campo:</b>\nSelecciona el tipo de evento que deseas ver:",
                        parse_mode="HTML",
                        reply_markup=crear_teclado_ejemplos(),
                    )

            elif data.startswith("ejemplo:"):
                tipo = data.split("ejemplo:", 1)[1]
                await query.answer()
                txt = texto_ejemplo_evento(tipo)
                btn_volver = [
                    [
                        InlineKeyboardButton("⬅️ Volver a Ejemplos", callback_data="cmd:ejemplos"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ]
                if query.message:
                    await query.message.reply_text(
                        txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_volver)
                    )

            elif data == "cmd:exportar":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                try:
                    from ..exporters import export_zip
                    os.makedirs("data/exports", exist_ok=True)
                    fecha_hoy = date.today().isoformat()
                    ruta_zip = os.path.join("data/exports", f"Backup_SG_{fecha_hoy}.zip")
                    export_zip(db, ruta_zip)
                    if os.path.exists(ruta_zip):
                        with open(ruta_zip, "rb") as f:
                            contenido = f.read()
                        if query.message:
                            await query.message.reply_document(
                                document=contenido,
                                filename=os.path.basename(ruta_zip),
                                caption="📦 Backup exportado en formato ZIP para Software Ganadero (TP/SG).",
                            )
                except Exception as eexp:
                    logger.error("Error al exportar en callback: %s", eexp)
                    if query.message:
                        await query.message.reply_text(f"❌ Error al exportar backup: {eexp}")

            elif data == "cmd:usuarios":
                await query.answer()
                if not auth.puede_gestionar_usuarios(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ Solo el propietario (OWNER) puede ver la lista de usuarios.")
                    return
                msg = formatear_usuarios(auth)
                teclado_u = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ])
                if query.message:
                    await query.message.reply_text(msg, reply_markup=teclado_u)

            elif data == "cmd:logs":
                await query.answer()
                if not auth.puede_gestionar_usuarios(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ Solo el propietario (OWNER) puede consultar los logs del sistema.")
                    return
                msg = obtener_ultimos_logs(log_file, lineas=25)
                if len(msg) > 3800:
                    msg = msg[-3800:]
                cuerpo_log = html.escape(msg)
                teclado_l = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔄 Refrescar Logs", callback_data="cmd:logs"),
                        InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ])
                if query.message:
                    try:
                        await query.message.reply_text(
                            f"📜 <b>Últimos Registros del Sistema (Logs)</b>\n<pre>\n{cuerpo_log}\n</pre>",
                            parse_mode="HTML",
                            reply_markup=teclado_l,
                        )
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_l)

            elif data == "cmd:inventario":
                await query.answer()
                msg = formatear_animales(db)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML")
                    except Exception:
                        await query.message.reply_text(msg)

            elif data == "cmd:despacho":
                await query.answer()
                if not auth.es_autorizado(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_despacho_matutino(db)
                if query.message:
                    await _enviar_texto_seguro(
                        query.message,
                        msg,
                        parse_mode="HTML",
                        reply_markup=crear_teclado_despacho_matutino(),
                    )

            elif data == "cmd:registrar_leche":
                await query.answer()
                if query.message:
                    await query.message.reply_text("🥛 Envía: /leche <litros>\nEj: /leche 475  (total del hato hoy)")

            elif data == "cmd:programar_recordatorio":
                await query.answer()
                if query.message:
                    await query.message.reply_text("⏰ Envía: /programar YYYY-MM-DD HH:MM mensaje\nEj: /programar 2026-09-01 08:00 Rotar potrero Bajo")

            elif data == "cmd:alertas":
                await query.answer()
                if not auth.es_autorizado(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_alertas_panel(db)
                if query.message:
                    try:
                        await query.message.reply_text(
                            msg, parse_mode="HTML", reply_markup=crear_teclado_alertas()
                        )
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_alertas())

            elif data == "cmd:poblacion":
                await query.answer()
                if not auth.es_autorizado(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_poblacion_panel(db)
                if query.message:
                    try:
                        await query.message.reply_text(
                            msg, parse_mode="HTML", reply_markup=crear_teclado_poblacion()
                        )
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_poblacion())

            elif data == "cmd:genetica":
                await query.answer()
                if not auth.es_autorizado(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_genetica_panel(db)
                if query.message:
                    try:
                        await query.message.reply_text(
                            msg, parse_mode="HTML", reply_markup=crear_teclado_poblacion_detalle()
                        )
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_poblacion_detalle())

            elif data == "alerta:partos":
                await query.answer()
                hoy = date.today()
                limite_30d = hoy + timedelta(days=30)
                filas = db.query(
                    """
                    SELECT a.tag, a.nombre, s.fep_calculada, p.nombre AS potrero
                    FROM servicios s
                    JOIN animales a ON a.id_animal = s.vaca_id
                    LEFT JOIN potreros p ON p.id = a.potrero_id
                    WHERE a.estado = 'ACTIVO' AND s.fep_calculada IS NOT NULL
                      AND s.fep_calculada >= ? AND s.fep_calculada <= ?
                    ORDER BY s.fep_calculada ASC
                    """,
                    (hoy.isoformat(), limite_30d.isoformat()),
                )
                if not filas:
                    txt = "🔴 <b>Próximos Partos (≤30 días):</b>\n\n✅ No hay partos proyectados para los próximos 30 días."
                    btn_a = [[
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]]
                else:
                    total_p = len(filas)
                    filas_m = filas[:15]
                    lineas = [f"🔴 <b>Vacas con Parto Próximo (≤30 días) [{total_p} vaca(s)]:</b>\n"]
                    botones_vacas = []
                    for r in filas_m:
                        tag_v = r["tag"] or "S/T"
                        fep = r["fep_calculada"]
                        dias_faltan = (to_date(fep) - hoy).days if to_date(fep) else 0
                        pot = f" · 📍 {r['potrero']}" if r["potrero"] else ""
                        lineas.append(f"• 🐮 <b>{html.escape(str(tag_v))}</b>: FEP {fep} (en {dias_faltan}d){pot}")
                        botones_vacas.append(InlineKeyboardButton(f"🐮 {tag_v}", callback_data=f"ficha:{tag_v}"))
                    if total_p > 15:
                        lineas.append(f"\n<i>...y {total_p - 15} vaca(s) más.</i>")
                    txt = "\n".join(lineas)
                    btn_a = []
                    for i in range(0, min(len(botones_vacas), 15), 3):
                        btn_a.append(botones_vacas[i:i+3])
                    btn_a.append([
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_a))

            elif data == "alerta:secados":
                await query.answer()
                hoy = date.today()
                filas = db.query(
                    """
                    SELECT a.tag, a.nombre, MAX(p.fecha) as ult_parto, pot.nombre AS potrero
                    FROM partos p
                    JOIN animales a ON a.id_animal = p.vaca_id
                    LEFT JOIN potreros pot ON pot.id = a.potrero_id
                    WHERE a.estado = 'ACTIVO' AND a.sexo LIKE 'H%'
                    GROUP BY a.id_animal
                    HAVING ult_parto <= date(?, '-200 days')
                    ORDER BY ult_parto ASC
                    """,
                    (hoy.isoformat(),),
                )
                if not filas:
                    txt = "🟡 <b>Vacas Candidatas para Secado (≥200 DEL):</b>\n\n✅ No hay vacas en lactancia prolongada pendientes de secado."
                    btn_a = [[
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]]
                else:
                    total_s = len(filas)
                    filas_m = filas[:15]
                    lineas = [f"🟡 <b>Vacas Candidatas para Secado (≥200 Días de Lactancia) [{total_s} vaca(s)]:</b>\n"]
                    botones_vacas = []
                    for r in filas_m:
                        tag_v = r["tag"] or "S/T"
                        dias_l = (hoy - to_date(r["ult_parto"])).days if to_date(r["ult_parto"]) else 0
                        pot = f" · 📍 {r['potrero']}" if r["potrero"] else ""
                        lineas.append(f"• 🐮 <b>{html.escape(str(tag_v))}</b>: {dias_l} DEL (Parto {r['ult_parto']}){pot}")
                        botones_vacas.append(InlineKeyboardButton(f"🐮 {tag_v}", callback_data=f"ficha:{tag_v}"))
                    if total_s > 15:
                        lineas.append(f"\n<i>...y {total_s - 15} vaca(s) más.</i>")
                    txt = "\n".join(lineas)
                    btn_a = []
                    for i in range(0, min(len(botones_vacas), 15), 3):
                        btn_a.append(botones_vacas[i:i+3])
                    btn_a.append([
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_a))

            elif data == "alerta:destetes":
                await query.answer()
                hoy = date.today()
                filas = db.query(
                    """
                    SELECT a.tag, a.nombre, a.fecha_nacimiento, a.sexo, pot.nombre AS potrero
                    FROM animales a
                    LEFT JOIN potreros pot ON pot.id = a.potrero_id
                    WHERE a.estado = 'ACTIVO' AND a.fecha_nacimiento IS NOT NULL
                      AND a.fecha_nacimiento <= date(?, '-200 days')
                      AND a.fecha_nacimiento >= date(?, '-365 days')
                    ORDER BY a.fecha_nacimiento ASC
                    """,
                    (hoy.isoformat(), hoy.isoformat()),
                )
                if not filas:
                    txt = "🟢 <b>Crías en Edad de Destete (≥200 días):</b>\n\n✅ No hay terneros pendientes de destete en este rango."
                    btn_a = [[
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]]
                else:
                    total_c = len(filas)
                    filas_m = filas[:15]
                    lineas = [f"🟢 <b>Crías en Edad de Destete (200 - 365 días) [{total_c} cría(s)]:</b>\n"]
                    botones_crias = []
                    for r in filas_m:
                        tag_c = r["tag"] or "S/T"
                        dias_edad = (hoy - to_date(r["fecha_nacimiento"])).days if to_date(r["fecha_nacimiento"]) else 0
                        sexo_txt = "Macho" if str(r["sexo"]).startswith("M") else "Hembra"
                        pot = f" · 📍 {r['potrero']}" if r["potrero"] else ""
                        lineas.append(f"• 🍼 <b>{html.escape(str(tag_c))}</b> ({sexo_txt}): {dias_edad}d (Nac. {r['fecha_nacimiento']}){pot}")
                        botones_crias.append(InlineKeyboardButton(f"🐮 {tag_c}", callback_data=f"ficha:{tag_c}"))
                    if total_c > 15:
                        lineas.append(f"\n<i>...y {total_c - 15} cría(s) más.</i>")
                    txt = "\n".join(lineas)
                    btn_a = []
                    for i in range(0, min(len(botones_crias), 15), 3):
                        btn_a.append(botones_crias[i:i+3])
                    btn_a.append([
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_a))

            elif data == "alerta:pesos":
                await query.answer()
                filas_gmd = db.query(
                    """
                    SELECT a.tag, a.nombre, p.peso_kg, p.fecha, pot.nombre AS potrero
                    FROM pesajes p
                    JOIN animales a ON a.id_animal = p.animal_id
                    LEFT JOIN potreros pot ON pot.id = a.potrero_id
                    WHERE a.estado = 'ACTIVO'
                    ORDER BY a.id_animal, p.fecha ASC
                    """
                )
                pesos_por_animal = defaultdict(list)
                for r in filas_gmd:
                    pesos_por_animal[r["tag"]].append(r)
                perdidas = []
                for tag_a, p_list in pesos_por_animal.items():
                    if len(p_list) >= 2:
                        ult = p_list[-1]
                        pen = p_list[-2]
                        d_ult = to_date(ult["fecha"])
                        d_pen = to_date(pen["fecha"])
                        if d_ult and d_pen and (d_ult - d_pen).days > 0:
                            dias_diff = (d_ult - d_pen).days
                            kg_diff = ult["peso_kg"] - pen["peso_kg"]
                            if kg_diff < 0:
                                gmd = (kg_diff * 1000.0) / dias_diff
                                perdidas.append((tag_a, gmd, kg_diff, ult["peso_kg"], pen["peso_kg"], ult["potrero"]))
                if not perdidas:
                    txt = "⚠️ <b>Alertas de Pérdida de Peso (GMD &lt; 0):</b>\n\n✅ Ningún animal activo registró pérdida de peso en su último pesaje."
                    btn_a = [[
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]]
                else:
                    total_p = len(perdidas)
                    perdidas_m = sorted(perdidas, key=lambda x: x[1])[:15]
                    lineas = [f"⚠️ <b>Pérdida de Peso en Último Control [{total_p} animal(es)]:</b>\n"]
                    botones_p = []
                    for tag_a, gmd, kg_diff, p_ult, p_pen, pot in perdidas_m:
                        pot_txt = f" · 📍 {pot}" if pot else ""
                        lineas.append(f"• 🐮 <b>{html.escape(str(tag_a))}</b>: <b>{gmd:.0f} g/día</b> ({kg_diff:+.1f} kg: {p_pen:.0f}kg → {p_ult:.0f}kg){pot_txt}")
                        botones_p.append(InlineKeyboardButton(f"🐮 {tag_a}", callback_data=f"animal:pesos:{tag_a}"))
                    if total_p > 15:
                        lineas.append(f"\n<i>...y {total_p - 15} animal(es) más.</i>")
                    txt = "\n".join(lineas)
                    btn_a = []
                    for i in range(0, min(len(botones_p), 15), 3):
                        btn_a.append(botones_p[i:i+3])
                    btn_a.append([
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_a))

            elif data == "cmd:potreros":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_potreros(db, potrero="sg")
                teclado_p = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⏳ Días Ocupación", callback_data="cmd:ocupacion"),
                        InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_p)

            elif data == "cmd:potreros_sg":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_potreros(db, potrero="sg")
                teclado_p = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⏳ Días Ocupación", callback_data="cmd:ocupacion"),
                        InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_p)

            elif data == "cmd:ocupacion":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                qe = QueryEngine(db)
                msg = qe.responder("dias de ocupacion")
                teclado_p = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📊 Existencias SG", callback_data="cmd:potreros_sg"),
                        InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_p)

            elif data == "cmd:potreros_listos":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_potreros(db)
                teclado_p = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📊 Existencias SG", callback_data="cmd:potreros_sg"),
                        InlineKeyboardButton("⏳ Días Ocupación", callback_data="cmd:ocupacion"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_p)

            elif data == "cmd:status":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_tablero_finca(db)
                teclado_st = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📊 Inventario Hato", callback_data="cmd:inventario"),
                        InlineKeyboardButton("⚠️ Alertas Pendientes", callback_data="cmd:alertas"),
                    ],
                    [
                        InlineKeyboardButton("🌿 Potreros Voisin", callback_data="cmd:potreros"),
                        InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_st)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_st)

            elif data == "cmd:sistema":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_estado_servidor(db, auth, db.path if hasattr(db, "path") else None)
                teclado_sis = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
                        InlineKeyboardButton("👥 Usuarios / Permisos", callback_data="cmd:usuarios"),
                    ],
                    [
                        InlineKeyboardButton("📜 Ver Últimos Logs", callback_data="cmd:logs"),
                        InlineKeyboardButton("📦 Descargar Backup ZIP", callback_data="cmd:exportar"),
                    ],
                    [
                        InlineKeyboardButton("🔄 Actualizar", callback_data="cmd:sistema"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_sis)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_sis)

            elif data == "cmd:reporte":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                try:
                    from ..reports import generar_pdf
                    os.makedirs(reportes_dir, exist_ok=True)
                    fecha_hoy = date.today()
                    ruta = os.path.join(reportes_dir, f"reporte_semanal_{fecha_hoy.isoformat()}.pdf")
                    generar_pdf(db, 7, ruta, hoy=fecha_hoy)
                    if os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            contenido = f.read()
                        if query.message:
                            await query.message.reply_document(
                                document=contenido, filename=os.path.basename(ruta)
                            )
                except Exception as erep:
                    logger.error("Error al generar reporte en callback: %s", erep)
                    if query.message:
                        await query.message.reply_text(f"❌ Error al generar reporte: {erep}")

            elif data == "cmd:graficos":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "📊 <b>Gráficos de la Finca</b>\n\nElige un gráfico:",
                        parse_mode="HTML", reply_markup=crear_teclado_graficos(),
                    )

            elif data == "cmd:fotos":
                await query.answer()
                filas = db.ultimas_fotos(limit=5)
                if not filas:
                    if query.message:
                        await query.message.reply_text("📷 No hay fotos registradas en la bitácora.")
                    return

                msg = formatear_fotos(db, limite=5)
                teclado_f = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal")]
                ])
                if query.message:
                    await query.message.reply_text(msg, reply_markup=teclado_f)

                # Enviar las fotografías disponibles en disco
                for r in filas:
                    ruta = r["ruta"]
                    tag_foto = r["tag"] or "Sin arete"
                    fec = r["fecha"] or "sin fecha"
                    cap = f" — {r['caption']}" if r["caption"] else ""
                    pie = f"📷 Animal: {tag_foto} [{fec}]{cap}"
                    if ruta and os.path.exists(ruta):
                        try:
                            with open(ruta, "rb") as f:
                                if query.message:
                                    await query.message.reply_photo(photo=f, caption=pie)
                        except Exception as efoto:
                            logger.error("Error al enviar foto %s: %s", ruta, efoto)

            elif data.startswith("foto:"):
                tag = data.split("foto:", 1)[1].strip()
                await query.answer()
                foto_path = buscar_foto_animal(db, tag, media_dir=media_dir)
                if foto_path and os.path.exists(foto_path):
                    with open(foto_path, "rb") as f:
                        if query.message:
                            await query.message.reply_photo(
                                photo=f, caption=f"📷 Foto del animal {tag}", reply_markup=crear_teclado_animal_detalle(tag)
                            )
                    return

                filas = db.fotos_de(tag, limit=5)
                if not filas:
                    if query.message:
                        await query.message.reply_text(
                            f"📷 No hay fotos registradas para el animal {tag}.",
                            reply_markup=crear_teclado_animal_detalle(tag),
                        )
                    return
                for r in filas:
                    ruta = r["ruta"]
                    fec = r["fecha"] or "sin fecha"
                    cap = f" ({r['caption']})" if r.get("caption") else ""
                    pie = f"📷 Animal {tag} - {fec}{cap}"
                    if ruta and os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            if query.message:
                                await query.message.reply_photo(
                                    photo=f, caption=pie, reply_markup=crear_teclado_animal_detalle(tag)
                                )
                    else:
                        if query.message:
                            await query.message.reply_text(
                                f"📷 Foto {tag} [{fec}] (archivo no disponible en servidor).",
                                reply_markup=crear_teclado_animal_detalle(tag),
                            )

            elif data.startswith("animal:pesos:") or data.startswith("pesos:"):
                tag = data.split(":", 2)[-1].strip()
                await query.answer()
                msg = formatear_pesajes_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal_detalle(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal_detalle(tag))

            elif data.startswith("animal:reprod:") or data.startswith("repro:"):
                tag = data.split(":", 2)[-1].strip()
                await query.answer()
                msg = formatear_reprod_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal_detalle(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal_detalle(tag))

            elif data.startswith("animal:leche:"):
                tag = data.split("animal:leche:", 1)[1].strip()
                await query.answer()
                msg = formatear_leche_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal_detalle(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal_detalle(tag))

            elif data.startswith("animal:sanidad:") or data.startswith("retiro:"):
                tag = data.split(":", 2)[-1].strip()
                await query.answer()
                msg = formatear_sanidad_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal_detalle(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal_detalle(tag))

            elif data.startswith("animal:grafico:"):
                tag = data.split("animal:grafico:", 1)[1].strip()
                await query.answer()
                if not graficos_disponibles():
                    if query.message:
                        await query.message.reply_text(
                            "📈 Los gráficos no están disponibles en este servidor (falta matplotlib)."
                        )
                else:
                    ruta_grafico = generar_grafico_peso(db, tag, output_dir=reportes_dir)
                    if ruta_grafico and os.path.exists(ruta_grafico):
                        with open(ruta_grafico, "rb") as f:
                            if query.message:
                                await query.message.reply_photo(
                                    photo=f, caption=f"📈 Curva de crecimiento — {tag}",
                                    reply_markup=crear_teclado_animal_detalle(tag),
                                )
                    else:
                        if query.message:
                            await query.message.reply_text(
                                f"📈 No hay suficientes pesajes registrados para graficar a {tag} "
                                "(se necesitan al menos 2)."
                            )

            elif data.startswith("animal:grafico_leche:"):
                tag = data.split("animal:grafico_leche:", 1)[1].strip()
                await query.answer()
                if not graficos_disponibles():
                    if query.message:
                        await query.message.reply_text(
                            "📉 Los gráficos no están disponibles en este servidor (falta matplotlib)."
                        )
                else:
                    ruta_grafico = generar_grafico_lactancia(db, tag, output_dir=reportes_dir)
                    if ruta_grafico and os.path.exists(ruta_grafico):
                        with open(ruta_grafico, "rb") as f:
                            if query.message:
                                await query.message.reply_photo(
                                    photo=f, caption=f"📉 Curva de lactancia — {tag}",
                                    reply_markup=crear_teclado_animal_detalle(tag),
                                )
                    else:
                        if query.message:
                            await query.message.reply_text(
                                f"📉 No hay suficientes controles de leche registrados para {tag} "
                                "(se necesitan al menos 2, y conocer su fecha de último parto)."
                            )

            elif data.startswith("panel_grafico:"):
                tipo = data.split("panel_grafico:", 1)[1].strip()
                await query.answer()
                entrada = GRAFICOS_PANEL.get(tipo)
                if not entrada:
                    if query.message:
                        await query.message.reply_text("⚠️ Tipo de gráfico no reconocido.")
                elif not graficos_disponibles():
                    if query.message:
                        await query.message.reply_text(
                            "📈 Los gráficos no están disponibles en este servidor (falta matplotlib)."
                        )
                else:
                    generador, titulo = entrada
                    ruta_grafico = generador(db, output_dir=reportes_dir)
                    if ruta_grafico and os.path.exists(ruta_grafico):
                        with open(ruta_grafico, "rb") as f:
                            if query.message:
                                await query.message.reply_photo(
                                    photo=f, caption=titulo, reply_markup=crear_teclado_grafico_detalle(),
                                )
                    else:
                        if query.message:
                            await query.message.reply_text(
                                f"{titulo}\n\n⚠️ No hay suficientes datos registrados todavía para este gráfico."
                            )

            elif data.startswith("animal:geneal:"):
                tag = data.split("animal:geneal:", 1)[1].strip()
                await query.answer()
                msg = formatear_genealogia_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal_detalle(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal_detalle(tag))

            elif data.startswith("animal:resumen:") or data.startswith("ficha:"):
                tag = data.split(":", 2)[-1].strip()
                await query.answer()
                try:
                    db.registrar_consulta_animal(tag)
                except Exception:
                    pass
                msg = formatear_historial(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal(tag))

            elif data.startswith("ubica:"):
                tag = data.split("ubica:", 1)[1].strip()
                await query.answer()
                qe = QueryEngine(db)
                msg = qe.responder(f"en que potrero esta {tag}")
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal_detalle(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal_detalle(tag))

            elif data == "cmd:historial":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "📋 Para consultar la ficha de un animal, escribe:\n/historial <tag> (ej. /historial 47) o directamente el número de arete."
                    )

            elif data == "cmd:buscar_animal":
                await query.answer()
                msg = formatear_panel_buscar_animal_texto()
                if query.message:
                    await query.message.reply_text(
                        msg, parse_mode="HTML", reply_markup=crear_teclado_buscar_animal(db)
                    )

            elif data == "cmd:medicamentos":
                await query.answer()
                msg = formatear_panel_medicamentos(db)
                if query.message:
                    await query.message.reply_text(
                        msg, parse_mode="HTML", reply_markup=crear_teclado_medicamentos()
                    )

            elif data == "cmd:preguntas_rapidas":
                await query.answer()
                msg = formatear_panel_preguntas_rapidas_texto()
                if query.message:
                    await query.message.reply_text(
                        msg, parse_mode="HTML", reply_markup=crear_teclado_preguntas_rapidas()
                    )

            elif data == "cmd:retiros_activos":
                await query.answer()
                qe = QueryEngine(db)
                msg = qe.responder("quien esta en retiro")
                teclado_ret = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("💉 Ver Medicamentos", callback_data="cmd:medicamentos"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ])
                if query.message:
                    await query.message.reply_text(msg, reply_markup=teclado_ret)

            elif data == "cmd:ultimos_tratamientos":
                await query.answer()
                ultimos = db.query(
                    """
                    SELECT t.*, a.tag, a.nombre, p.nombre AS potrero_nombre
                    FROM tratamientos t
                    LEFT JOIN animales a ON a.id_animal = t.animal_id
                    LEFT JOIN potreros p ON p.id = a.potrero_id
                    ORDER BY t.fecha DESC, t.id DESC LIMIT 10
                    """
                )
                if not ultimos:
                    txt = "💉 No hay tratamientos médicos registrados recientemente en la bitácora."
                    btn_t = [[InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal")]]
                else:
                    lineas = ["💉 <b>Últimos Tratamientos Médicos Registrados:</b>\n"]
                    botones_trat = []
                    for u in ultimos:
                        tag_u = u["tag"] or (f"#{u['animal_id']}" if u["animal_id"] else "S/T")
                        fec = u["fecha"] or "S/F"
                        med = u["producto"] or "Tratamiento"
                        dos = f" ({u['dosis']})" if u["dosis"] else ""
                        pot = f" · 📍 {u['potrero_nombre']}" if u["potrero_nombre"] else ""
                        lineas.append(f"• [{fec}] 🐮 <b>{html.escape(str(tag_u))}</b>: {html.escape(str(med))}{dos}{pot}")
                        if u["tag"] and len(botones_trat) < 6:
                            botones_trat.append(InlineKeyboardButton(f"🐮 {u['tag']}", callback_data=f"ficha:{u['tag']}"))
                    txt = "\n".join(lineas)
                    btn_t = []
                    if botones_trat:
                        for i in range(0, len(botones_trat), 3):
                            btn_t.append(botones_trat[i:i+3])
                    btn_t.append([
                        InlineKeyboardButton("💊 Panel Medicamentos", callback_data="cmd:medicamentos"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_t))

            elif data.startswith("filtro:"):
                cat = data.split("filtro:", 1)[1].strip()
                await query.answer()
                filas = []
                titulo = ""
                if cat == "paridas":
                    titulo = "🥛 <b>Vacas Paridas Recientes (Lactancia):</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre, p.fecha FROM partos p
                        JOIN animales a ON a.id_animal = p.vaca_id
                        WHERE a.estado = 'ACTIVO' AND a.sexo LIKE 'H%'
                        ORDER BY p.fecha DESC LIMIT 9
                        """
                    )
                elif cat == "inseminadas":
                    titulo = "🤰 <b>Vacas Inseminadas / Servidas:</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre, s.fecha FROM servicios s
                        JOIN animales a ON a.id_animal = s.vaca_id
                        WHERE a.estado = 'ACTIVO'
                        ORDER BY s.fecha DESC LIMIT 9
                        """
                    )
                elif cat == "toros":
                    titulo = "🐂 <b>Toros / Reproductores Activos:</b>"
                    # Mismo criterio de "reproductor" que el resto del bot (existencias por
                    # potrero, fichas, etc.): nombre/nota con TORO·REPRODUCTOR·PADRON, o
                    # >=1095 días (~3 años). Sin este filtro, "toros" mostraba cualquier
                    # macho activo por orden de arete (terneros y levante incluidos).
                    machos = db.query(
                        """
                        SELECT a.tag, a.nombre, a.notas, a.fecha_nacimiento FROM animales a
                        WHERE a.estado = 'ACTIVO' AND (a.sexo LIKE 'M%' OR a.sexo = 'Macho')
                        """
                    )
                    reproductores = []
                    for m in machos:
                        nom_m = f"{m['nombre'] or ''} {m['notas'] or ''} {m['tag'] or ''}".upper()
                        fnac = to_date(m["fecha_nacimiento"])
                        edad_d = (date.today() - fnac).days if fnac else None
                        if "REPRODUCTOR" in nom_m or "PADRON" in nom_m or "TORO" in nom_m or (edad_d is not None and edad_d >= 1095):
                            reproductores.append(m)
                    filas = reproductores[:9]
                elif cat == "crias":
                    titulo = "🍼 <b>Crías y Terneros Recientes:</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre, a.fecha_nacimiento AS fecha FROM animales a
                        WHERE a.estado = 'ACTIVO' AND a.fecha_nacimiento IS NOT NULL
                        ORDER BY a.fecha_nacimiento DESC LIMIT 9
                        """
                    )
                elif cat == "pesajes":
                    titulo = "⚖️ <b>Últimos Animales Pesados:</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre, pe.peso_kg, pe.fecha FROM pesajes pe
                        JOIN animales a ON a.id_animal = pe.animal_id
                        WHERE a.estado = 'ACTIVO'
                        ORDER BY pe.fecha DESC LIMIT 9
                        """
                    )

                if not filas:
                    txt = f"{titulo}\n\nNo se encontraron animales activos registrados en esta categoría."
                    btn_f = [[InlineKeyboardButton("🔍 Buscar Otro Grupo", callback_data="cmd:buscar_animal")]]
                else:
                    txt = f"{titulo}\n\nToque cualquier animal para abrir su ficha y fotografía:"
                    botones = [
                        InlineKeyboardButton(f"🐮 {r['tag']}", callback_data=f"ficha:{r['tag']}")
                        for r in filas if r["tag"]
                    ]
                    btn_f = []
                    for i in range(0, len(botones), 3):
                        btn_f.append(botones[i:i+3])
                    btn_f.append([
                        InlineKeyboardButton("🔍 Buscar Otro Grupo", callback_data="cmd:buscar_animal"),
                        InlineKeyboardButton("🏠 Menú", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_f))

            elif data.startswith("faq:"):
                tema = data.split("faq:", 1)[1].strip()
                await query.answer()
                qe = QueryEngine(db)
                if tema == "retiro_leche":
                    msg = qe.responder("quien esta en retiro de leche")
                elif tema == "potreros_listos":
                    msg = qe.responder("que potreros estan listos")
                elif tema == "dias_abiertos":
                    msg = qe.responder("vacas abiertas mas de 90 dias")
                elif tema == "partos_mes":
                    msg = qe.responder("partos del mes")
                elif tema == "pesajes":
                    msg = qe.responder("ultimos pesajes")
                else:
                    msg = "Consulta no reconocida."

                teclado_faq = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("❓ Más Preguntas", callback_data="cmd:preguntas_rapidas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_faq)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_faq)

            elif data == "cmd:ayuda":
                await query.answer()
                rol = auth.rol_de(user_id)
                btn = [[InlineKeyboardButton("🏠 Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        formatear_ayuda(rol), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn)
                    )

        except Exception as e:
            logger.error("Error en handle_callback_query: %s", e, exc_info=True)
            if query and query.message:
                await query.message.reply_text(f"❌ Error: {e}")

    app = ApplicationBuilder().token(token).build()

    # Handlers de comandos
    app.add_handler(CommandHandler(["start", "menu"], cmd_start_menu))
    app.add_handler(CommandHandler(["help", "ayuda", "comandos"], cmd_ayuda_completa))
    app.add_handler(CommandHandler(["guia", "preguntar", "chat", "preguntas_guia"], cmd_guia_chat))
    app.add_handler(CommandHandler(["buscar", "buscar_animal", "buscador"], cmd_buscar_animal))
    app.add_handler(CommandHandler(["medicamentos", "tratamientos", "farmacia", "retiros", "retiro"], cmd_medicamentos))
    app.add_handler(CommandHandler(["preguntas", "faq", "consultas"], cmd_preguntas_rapidas))
    app.add_handler(CommandHandler(["despacho", "matutino", "hoy", "briefing"], cmd_despacho))
    app.add_handler(CommandHandler(["leche", "leche_total", "produccion"], cmd_leche))
    app.add_handler(CommandHandler(["programar", "recordatorio", "programar_recordatorio"], cmd_programar))
    app.add_handler(CommandHandler("alertas", cmd_alertas))
    app.add_handler(CommandHandler(["poblacion", "piramide", "edades"], cmd_poblacion))
    app.add_handler(CommandHandler(["genetica", "razas", "cruces"], cmd_genetica))
    app.add_handler(CommandHandler(["duplicados", "duplicados_geneticos"], cmd_duplicados))
    app.add_handler(CommandHandler(["ultimos", "ultimos_registros"], cmd_ultimos))
    app.add_handler(CommandHandler("deshacer", cmd_deshacer))
    app.add_handler(CommandHandler("confirmar_deshacer", cmd_confirmar_deshacer))
    app.add_handler(CommandHandler("cancelar_deshacer", cmd_cancelar_deshacer))
    app.add_handler(CommandHandler("renombrar_animal", cmd_renombrar_animal))
    app.add_handler(CommandHandler(["historial", "consulta", "ficha", "info", "vaca", "animal"], cmd_historial))
    app.add_handler(CommandHandler("potreros", cmd_potreros))
    app.add_handler(CommandHandler(["ocupacion", "rotacion"], cmd_ocupacion))
    app.add_handler(CommandHandler("animales", cmd_animales))
    app.add_handler(CommandHandler(["foto", "fotos"], cmd_fotos))
    app.add_handler(CommandHandler(["grafico", "grafica", "curva"], cmd_grafico))
    app.add_handler(CommandHandler(["grafico_leche", "curva_lactancia"], cmd_grafico_leche))
    app.add_handler(CommandHandler(["graficos", "graficas", "panel_graficos"], cmd_graficos))
    app.add_handler(CommandHandler(["status", "tablero", "finca", "resumen"], cmd_status))
    app.add_handler(CommandHandler(["sistema", "servidor", "vps"], cmd_sistema))
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

    # Tarea proactiva programada: Despacho Matutino diario (ej. 05:30 AM)
    async def _tarea_despacho_matutino(context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            msg = formatear_despacho_matutino(db)
            teclado = crear_teclado_despacho_matutino()
            for u in auth.listar_usuarios():
                u_id = u.get("user_id")
                u_rol = u.get("rol")
                if u_id and u_rol in ("OWNER", "ADMIN", "TRABAJADOR"):
                    try:
                        await context.bot.send_message(
                            chat_id=u_id,
                            text=msg,
                            parse_mode="HTML",
                            reply_markup=teclado,
                        )
                    except Exception as eu:
                        logger.warning("No se pudo enviar despacho matutino a usuario %s: %s", u_id, eu)
        except Exception as e:
            logger.error("Error ejecutando _tarea_despacho_matutino: %s", e, exc_info=True)

    if app.job_queue:
        import datetime
        hora_env = os.getenv("DESPACHO_HORA", "05:30")
        try:
            h, m = map(int, hora_env.split(":"))
            hora_despacho = datetime.time(hour=h, minute=m)
            app.job_queue.run_daily(_tarea_despacho_matutino, time=hora_despacho)
            logger.info("Tarea de Despacho Matutino programada diariamente a las %02d:%02d", h, m)
        except Exception as ejq:
            logger.warning("No se pudo programar despacho matutino en job_queue: %s", ejq)

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
