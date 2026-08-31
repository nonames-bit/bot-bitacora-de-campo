#!/usr/bin/env python3
"""Script CLI / Cron para generar y enviar el Despacho Matutino (Morning Briefing).

Uso:
    python scripts/enviar_despacho.py [--enviar-telegram] [--db data/bitacora.db]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

# Asegurar path del proyecto
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.db.database import Database
from src.server.auth import Auth
from src.server.formatters import formatear_despacho_matutino
from src.server.keyboards import crear_teclado_despacho_matutino


async def _enviar_por_telegram(token: str, users_file: str, mensaje: str) -> None:
    try:
        from telegram import Bot
        from telegram.constants import ParseMode
    except ImportError:
        print("❌ Error: python-telegram-bot no está instalado.", file=sys.stderr)
        return

    auth = Auth(users_file)
    bot = Bot(token=token)
    teclado = crear_teclado_despacho_matutino()

    usuarios = [
        u for u in auth.listar_usuarios()
        if u.get("user_id") and u.get("rol") in ("OWNER", "ADMIN", "TRABAJADOR")
    ]

    if not usuarios:
        print("⚠️ No hay usuarios autorizados configurados en users.json")
        return

    for u in usuarios:
        uid = u["user_id"]
        nombre = u.get("nombre", f"ID {uid}")
        try:
            await bot.send_message(
                chat_id=uid,
                text=mensaje,
                parse_mode=ParseMode.HTML,
                reply_markup=teclado,
            )
            print(f"✅ Despacho enviado exitosamente a {nombre} ({uid})")
        except Exception as e:
            print(f"❌ Falló envío a {nombre} ({uid}): {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Despacho Matutino Ganadero")
    parser.add_argument("--db", default=os.getenv("BITACORA_DB", "data/bitacora.db"), help="Ruta SQLite")
    parser.add_argument("--users", default=os.getenv("USERS_FILE", "src/server/users.json"), help="Ruta users.json")
    parser.add_argument("--enviar-telegram", action="store_true", help="Envía el mensaje por Telegram a los usuarios")
    parser.add_argument("--fecha", default=None, help="Simular fecha YYYY-MM-DD")
    args = parser.parse_args()

    db = Database(args.db)
    sim_fecha = date.fromisoformat(args.fecha) if args.fecha else None
    texto_despacho = formatear_despacho_matutino(db, hoy=sim_fecha)

    try:
        print(texto_despacho)
    except UnicodeEncodeError:
        print(texto_despacho.encode("utf-8", errors="replace").decode("utf-8"))
    print("\n" + "=" * 45 + "\n")

    if args.enviar_telegram:
        token = os.getenv("TELEGRAM_TOKEN")
        if not token or token == "pegar_aqui_el_token_del_botfather":
            print("❌ Error: TELEGRAM_TOKEN no configurado en variables de entorno.", file=sys.stderr)
            return 1
        asyncio.run(_enviar_por_telegram(token, args.users, texto_despacho))

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
