#!/usr/bin/env python3
"""Job de Sincronización Automática Diaria: Precios de Subastas Ganaderas, TRM e Insumos.

Actualiza automáticamente en SQLite (`data/bitacora.db`):
- Dólar TRM Oficial (Superintendencia Financiera / Banco de la República).
- Precios de subastas regionales (Granada, Guamal, San Martín, Puerto López, Catama, Yopal, Bogotá, Nacional).
- Insumos agropecuarios críticos del Ariari (urea, sal mineralizada 8% y 10%, alambre de púas).
- Precios de referencia de leche (Queseras locales, Industria, MinAgricultura USP).

Uso:
    python scripts/actualizar_precios_mercado.py [--db data/bitacora.db] [--forzar]

Configuración en cron (diario 06:00 AM COT):
    0 6 * * * /root/bitacora/.venv/bin/python /root/bitacora/scripts/actualizar_precios_mercado.py >> /var/log/bitacora-mercado.log 2>&1
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.db.database import Database
from src.integrations.mercado_sync import sincronizar_precios_mercado

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualización automática de precios de mercado ganadero")
    parser.add_argument(
        "--db",
        default=os.getenv("BITACORA_DB", "data/bitacora.db"),
        help="Ruta a la base de datos SQLite (por defecto: data/bitacora.db)",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Fuerza la actualización incluso si ya se ejecutó hoy",
    )
    args = parser.parse_args()

    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ahora}] 📡 Iniciando sincronización automática de precios de mercado...")
    print(f"  Base de datos: {args.db}")

    try:
        db = Database(args.db)
        res = sincronizar_precios_mercado(db, forzar=args.forzar)
        db.close()

        if res.get("actualizado"):
            print(f"[{ahora}] ✅ {res.get('mensaje')}")
            print(f"  TRM Oficial: ${res.get('trm', 0):,.2f} COP ({res.get('trm_fuente')})")
            print(f"  Filas registradas: {res.get('filas_actualizadas')}")
            noticias = res.get("noticias") or []
            if noticias:
                print(f"  Noticias / Boletines recientes ({len(noticias)}):")
                for n in noticias[:3]:
                    print(f"    - {n.get('titulo')}")
        else:
            print(f"[{ahora}] ℹ️ {res.get('mensaje')}")

        return 0
    except Exception as e:
        print(f"[{ahora}] ❌ Error durante la sincronización de precios de mercado: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
