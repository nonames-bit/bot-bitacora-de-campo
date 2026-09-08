#!/usr/bin/env bash
# ==============================================================================
# Respaldo fuera del servidor: base de datos + fotos (media/) comprimidas y
# subidas a Google Drive vía rclone (remoto "gdrive", configurado una sola
# vez con `rclone authorize "drive"` -- ver docs/DESPLIEGUE_DIGITALOCEAN.md).
#
# Motivo: backup_diario.sh respalda solo data/bitacora.db y lo guarda EN EL
# MISMO SERVIDOR -- si el droplet se destruye, se pierden la base de datos,
# sus copias locales Y todas las fotos (media/) juntas. Este script agrega
# una copia fuera del VPS con ambas cosas.
# ==============================================================================
set -e

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

REMOTO="gdrive:Bitacora_Backups_JA"
FECHA=$(date +%F)
TMP_DIR=$(mktemp -d)
ARCHIVO="respaldo_completo_${FECHA}.tar.gz"

if ! command -v rclone >/dev/null 2>&1; then
    echo "⚠️ rclone no está instalado. Respaldo a Drive omitido."
    exit 0
fi

DB_ORIGEN="data/bitacora.db"
if [ ! -f "$DB_ORIGEN" ]; then
    echo "⚠️ Base de datos no encontrada en $DB_ORIGEN. Respaldo a Drive omitido."
    exit 0
fi

echo "📦 Generando copia consistente de la base de datos..."
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB_ORIGEN" ".backup '$TMP_DIR/bitacora.db'"
else
    cp "$DB_ORIGEN" "$TMP_DIR/bitacora.db"
fi

if [ -d media ]; then
    echo "📦 Copiando fotos (media/)..."
    cp -r media "$TMP_DIR/media"
fi

echo "🗜️ Comprimiendo en $ARCHIVO..."
tar -czf "$TMP_DIR/$ARCHIVO" -C "$TMP_DIR" bitacora.db $( [ -d "$TMP_DIR/media" ] && echo media )

echo "☁️ Subiendo a Google Drive ($REMOTO)..."
rclone copy "$TMP_DIR/$ARCHIVO" "$REMOTO/" --quiet

rm -rf "$TMP_DIR"

echo "🧹 Eliminando respaldos de Drive con más de 90 días de antigüedad..."
rclone delete "$REMOTO/" --min-age 90d --quiet

echo "✅ Respaldo a Google Drive completado: $ARCHIVO"
