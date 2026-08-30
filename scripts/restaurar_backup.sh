#!/usr/bin/env bash
# ==============================================================================
# Restaura data/bitacora.db a partir de un respaldo diario (backups/AAAA-MM-DD.db).
# Uso EN el VPS:
#   bash /root/bitacora/scripts/restaurar_backup.sh 2026-08-29
#   bash /root/bitacora/scripts/restaurar_backup.sh --listar    (para ver fechas disponibles)
#
# Este script es para el caso "se dañó algo grande y hay que volver a como
# estaba ayer/anteayer" (ej. un trabajador borró o modificó por accidente
# muchos registros, o un backup de Software Ganadero se importó mal).
# Para corregir UN solo registro puntual (una muerte, un parto, etc. mal
# escrito) use /deshacer desde el chat de Telegram en vez de esto: es mucho
# más preciso y no pierde el resto del día.
#
# Es destructivo: reemplaza la base de datos completa por la del día elegido,
# perdiendo todo lo registrado DESPUÉS de ese respaldo. Por eso pide
# confirmación escrita y siempre guarda una copia de seguridad de "antes de
# restaurar" para poder deshacer la restauración misma si fue un error.
# ==============================================================================
set -euo pipefail

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

if [ "${1:-}" = "--listar" ] || [ -z "${1:-}" ]; then
    echo "📅 Respaldos disponibles en backups/:"
    ls -1 backups/*.db 2>/dev/null | sed 's#backups/##; s#\.db$##' | sort
    echo ""
    echo "Uso: bash scripts/restaurar_backup.sh <AAAA-MM-DD>"
    exit 0
fi

FECHA="$1"
ORIGEN="backups/${FECHA}.db"
ACTUAL="data/bitacora.db"

if [ ! -f "$ORIGEN" ]; then
    echo "❌ No existe el respaldo backups/${FECHA}.db"
    echo "Ejecuta 'bash scripts/restaurar_backup.sh --listar' para ver las fechas disponibles."
    exit 1
fi

echo "⚠️  Vas a REEMPLAZAR $ACTUAL con el respaldo de $FECHA."
echo "⚠️  Se perderá todo lo registrado después de ese respaldo (${FECHA})."
echo ""
read -r -p "Escribe SI en mayúsculas para confirmar: " CONFIRMACION
if [ "$CONFIRMACION" != "SI" ]; then
    echo "Cancelado. No se modificó nada."
    exit 0
fi

TS=$(date +%Y%m%d_%H%M%S)
COPIA_SEGURIDAD="backups/antes_de_restaurar_${TS}.db"
echo "📦 Guardando copia de la base actual en $COPIA_SEGURIDAD por si hay que deshacer esta restauración..."
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$ACTUAL" ".backup '$COPIA_SEGURIDAD'"
else
    cp "$ACTUAL" "$COPIA_SEGURIDAD"
fi

echo "🛑 Deteniendo el bot..."
systemctl stop bitacora-bot

echo "♻️  Restaurando $ORIGEN → $ACTUAL..."
cp "$ORIGEN" "$ACTUAL"

echo "▶️  Reiniciando el bot..."
systemctl start bitacora-bot
sleep 2
systemctl is-active bitacora-bot

echo "✅ Restaurado a la versión de ${FECHA}."
echo "   Copia de seguridad de lo que había antes: $COPIA_SEGURIDAD"
