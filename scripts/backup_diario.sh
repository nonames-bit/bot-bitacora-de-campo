#!/usr/bin/env bash
# ==============================================================================
# Script de respaldo diario de la base de datos SQLite y rotación a 30 días
# ==============================================================================
set -e

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

mkdir -p backups

ORIGEN="data/bitacora.db"
FECHA=$(date +%F)
DESTINO="backups/${FECHA}.db"

if [ ! -f "$ORIGEN" ]; then
    echo "⚠️ Base de datos no encontrada en $ORIGEN. Respaldo omitido."
    exit 0
fi

echo "📦 Creando respaldo diario: $DESTINO..."
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$ORIGEN" ".backup '$DESTINO'"
else
    cp "$ORIGEN" "$DESTINO"
fi

echo "🧹 Eliminando respaldos con más de 30 días de antigüedad..."
find backups/ -maxdepth 1 -name "*.db" -type f -mtime +30 -exec rm -f {} +

echo "✅ Respaldo diario completado exitosamente: $DESTINO"
