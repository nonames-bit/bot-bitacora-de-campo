#!/usr/bin/env bash
# ==============================================================================
# Script de inicio del bot de Telegram en modo servidor
# ==============================================================================
set -e

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

if [ -f ".venv/bin/activate" ]; then
    echo "ℹ️ Activando entorno virtual (.venv)..."
    source .venv/bin/activate
fi

echo "🚀 Iniciando Bot de Bitácora de Campo Ganadero..."
exec python3 -m src.main --server
