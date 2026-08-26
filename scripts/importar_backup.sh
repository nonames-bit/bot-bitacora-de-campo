#!/usr/bin/env bash
# ==============================================================================
# Script para importar backups históricos DBF (Software Ganadero) a SQLite
# ==============================================================================
set -e

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

if [ -z "$1" ]; then
    echo "❌ Error: Debe especificar la ruta del archivo Zip con las tablas DBF."
    echo "   Uso: ./scripts/importar_backup.sh <ruta/al/archivo.Zip>"
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "❌ Error: El archivo '$1' no existe o no es accesible."
    exit 1
fi

mkdir -p data

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "📦 Importando backup histórico desde '$1' a 'data/bitacora.db'..."
python -m src.main --db data/bitacora.db --importar "$1"

echo "✅ Importación completada con éxito."
