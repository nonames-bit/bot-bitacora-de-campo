"""Chat de la PWA: consultas y registros con confirmación antes de escribir.

Usa el mismo cerebro que Telegram (``Bot.interpretar_texto``: regex primero y
LLM solo de respaldo), pero en dos pasos:

1. ``procesar_mensaje``: las consultas se responden de una vez; los registros
   NO se escriben, quedan pendientes en ``chat_log`` con un token y la PWA
   muestra la tarjeta "¿Registro esto?".
2. ``confirmar``: con el token (del mismo usuario y vigente) se escriben en una
   sola transacción, o se descartan si el usuario toca "Corregir".

``chat_log`` guarda además cada mensaje (tipo detectado, latencia y si se
confirmó o corrigió): con esos datos se decide más adelante si hace falta un
clasificador mejor.
"""
from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any, Optional

try:
    from ..bot.bot_interface import MSG_NO_ENTENDI, Bot
    from ..parsers.event_parser import ParsedEvent
except ImportError:  # ejecución directa
    from src.bot.bot_interface import MSG_NO_ENTENDI, Bot  # type: ignore
    from src.parsers.event_parser import ParsedEvent  # type: ignore

logger = logging.getLogger(__name__)

VIGENCIA_MIN = 10


def _ahora() -> datetime:
    return datetime.now()


def procesar_mensaje(db, texto: str, user_id=None, canal: str = "texto",
                     hoy: Optional[date] = None) -> dict[str, Any]:
    """Responde consultas y deja los registros pendientes de confirmación."""
    t0 = time.monotonic()
    bot = Bot(db, hoy=hoy)
    respuestas, pendientes = bot.interpretar_texto(texto)
    if pendientes:
        tipo = "registro"
    elif respuestas == [MSG_NO_ENTENDI]:
        tipo = "desconocido"
    else:
        tipo = "consulta"
    token = secrets.token_urlsafe(16) if pendientes else None
    db.execute(
        "INSERT INTO chat_log (token, user_id, canal, texto, tipo, eventos_json, estado, latencia_ms, creado_en) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (token, None if user_id is None else str(user_id), canal, texto, tipo,
         json.dumps([asdict(e) for e in pendientes], ensure_ascii=False) if pendientes else None,
         "PENDIENTE" if pendientes else "RESPONDIDA",
         int((time.monotonic() - t0) * 1000), _ahora().isoformat(timespec="seconds")))
    return {
        "tipo": tipo,
        "respuesta": "\n".join(respuestas) or None,
        "confirmar": [bot.resumen_evento(e) for e in pendientes],
        "token": token,
    }


def confirmar(db, token: str, user_id=None, aceptar: bool = True,
              hoy: Optional[date] = None) -> dict[str, Any]:
    """Escribe (o descarta) los eventos pendientes de ``token``."""
    fila = db.query_one("SELECT * FROM chat_log WHERE token = ? AND estado = 'PENDIENTE'", (token or "",))
    if not fila or str(fila["user_id"]) != str(user_id):
        return {"ok": False, "error": "Esa nota ya no está pendiente. Envíela otra vez."}
    ahora = _ahora()
    if datetime.fromisoformat(fila["creado_en"]) + timedelta(minutes=VIGENCIA_MIN) < ahora:
        _cerrar(db, token, "VENCIDA", ahora)
        return {"ok": False, "error": f"Pasaron más de {VIGENCIA_MIN} minutos sin confirmar. "
                                      "Envíe la nota otra vez."}
    if not aceptar:
        _cerrar(db, token, "CORREGIDA", ahora)
        return {"ok": True, "respuesta": "No registré nada. Escriba la nota corregida."}
    # Reclamar el token antes de escribir: un doble toque no registra dos veces.
    if db.execute("UPDATE chat_log SET estado = 'CONFIRMANDO' WHERE token = ? AND estado = 'PENDIENTE'",
                  (token,)).rowcount != 1:
        return {"ok": False, "error": "Esa nota ya se está registrando."}
    eventos = [ParsedEvent(**d) for d in json.loads(fila["eventos_json"] or "[]")]
    try:
        with db.transaccion():
            respuestas = Bot(db, hoy=hoy).registrar_eventos(eventos, user_id)
    except ValueError as e:
        _cerrar(db, token, "ERROR", ahora)
        return {"ok": False, "error": f"No se registró nada: {e}"}
    except Exception:
        logger.exception("Error al registrar nota confirmada del chat")
        _cerrar(db, token, "ERROR", ahora)
        return {"ok": False, "error": "No se registró nada por un error interno. Intente de nuevo."}
    _cerrar(db, token, "CONFIRMADA", ahora)
    return {"ok": True, "respuesta": "\n".join(respuestas)}


def _cerrar(db, token: str, estado: str, ahora: datetime) -> None:
    db.execute("UPDATE chat_log SET estado = ?, resuelto_en = ? WHERE token = ?",
               (estado, ahora.isoformat(timespec="seconds"), token))
