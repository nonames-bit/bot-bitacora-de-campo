"""Punto de entrada del bot de bitácora de campo zootécnico."""
from __future__ import annotations

import argparse
import sys

from src.bot.bot_interface import Bot
from src.db.database import Database
from src.exporters.dbf_exporter import export_zip
from src.importers.dbf_importer import import_zip


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Bot de bitácora de campo zootécnico (texto, audio, imagen)."
    )
    parser.add_argument("--db", default=None, help="Ruta de la base SQLite")
    parser.add_argument("--server", action="store_true", help="Inicia el bot de Telegram en modo servidor")
    parser.add_argument("--importar", help="Ruta al Zip de datos DBF (Software Ganadero)")
    parser.add_argument("--exportar", nargs="?", const="AUTO", help="Exporta la base SQLite a un paquete Zip compatible con Software Ganadero")
    parser.add_argument("--texto", help="Procesa un mensaje de texto y termina")
    parser.add_argument("--audio", help="Procesa un archivo de audio")
    parser.add_argument("--imagen", help="Procesa un archivo de imagen")
    parser.add_argument("--despacho", action="store_true", help="Genera y muestra el Despacho Matutino")
    args = parser.parse_args(argv)

    if args.server:
        from src.server.telegram_bot import correr
        correr(db_path=args.db)
        return 0

    db = Database(args.db or "bitacora.db")
    db.create_tables()

    if args.despacho:
        from src.server.formatters import formatear_despacho_matutino
        print(formatear_despacho_matutino(db))
        db.close()
        return 0

    if args.importar:
        conteos = import_zip(db, args.importar)
        print("Importación completada:", conteos)

    if args.exportar:
        out_path = None if args.exportar == "AUTO" else args.exportar
        zip_generado = export_zip(db, out_path)
        print(f"Exportación completada exitosamente: {zip_generado}")

    bot = Bot(db)

    # --importar y/o --exportar son modos de lote (CLI, cron, watcher remoto
    # por SSH): deben terminar solos apenas hacen su trabajo. Sin este
    # chequeo (antes solo miraba --exportar, nunca --importar), un
    # `--importar archivo.zip` sin --texto/--audio/--imagen caía al modo
    # interactivo de abajo y se quedaba bloqueado en input() esperando una
    # línea que nunca llega cuando se invoca por SSH no interactivo -- el
    # import ya había terminado, pero el proceso nunca salía.
    if (args.importar or args.exportar) and not (args.texto or args.audio or args.imagen):
        db.close()
        return 0

    if args.texto:
        print(bot.procesar_texto(args.texto))
    elif args.audio:
        print(bot.procesar_audio(args.audio))
    elif args.imagen:
        print(bot.procesar_imagen(args.imagen))
    else:
        print("Modo interactivo. Escriba una nota o una pregunta (Ctrl+C para salir).")
        try:
            while True:
                entrada = input("> ").strip()
                if entrada.lower() in ("salir", "exit", "q"):
                    break
                if entrada:
                    print(bot.procesar_texto(entrada))
        except (KeyboardInterrupt, EOFError):
            print()

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
