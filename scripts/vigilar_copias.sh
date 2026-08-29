#!/usr/bin/env bash
# ==============================================================================
# Script para vigilar e importar automáticamente copias (.Zip) de Software Ganadero
# ==============================================================================
set -e

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Cargar variables de entorno si existe .env
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

COPIAS_DIR="${COPIAS_DIR:-data/copias}"
mkdir -p "$COPIAS_DIR"
mkdir -p data

echo "👀 Vigilante de copias SG (Auto-Import) activo en: $COPIAS_DIR"

if [ "$1" = "--once" ] || [ "$1" = "--cron" ]; then
    exec python3 -m src.watchers.copias_watcher --once "$@"
else
    exec python3 -m src.watchers.copias_watcher "$@"
fi
