#!/usr/bin/env bash
# ==============================================================================
# Restaura data/bitacora.db + media/ (fotos) a partir de un respaldo subido a
# Google Drive por scripts/respaldo_drive.sh.
#
# Uso EN el VPS:
#   bash /root/bitacora/scripts/restaurar_drive.sh --listar
#   bash /root/bitacora/scripts/restaurar_drive.sh 2026-09-08
#
# Este es el script para el caso "el servidor murió/hay que reinstalarlo de
# cero" (o "se borró/dañó la carpeta media/"), a diferencia de
# restaurar_backup.sh que solo restaura la base de datos desde una copia
# LOCAL (que no sirve si el droplet entero se destruyó, porque esa copia
# vivía en el mismo disco).
#
# En un servidor nuevo, antes de correr esto: clonar el repo, instalar
# dependencias (bash scripts/setup_vps.sh) y configurar rclone (ver
# docs/DESPLIEGUE_DIGITALOCEAN.md, sección "Backup diario a Google Drive").
#
# Es destructivo: reemplaza data/bitacora.db y media/ completos por los del
# respaldo elegido. Por eso pide confirmación escrita y guarda una copia de
# seguridad de "antes de restaurar" para poder deshacerlo si fue un error.
# ==============================================================================
set -euo pipefail

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

REMOTO="gdrive:Bitacora_Backups_JA"

if ! command -v rclone >/dev/null 2>&1; then
    echo "❌ rclone no está instalado. Instálelo con: apt-get install -y rclone"
    exit 1
fi

if [ "${1:-}" = "--listar" ] || [ -z "${1:-}" ]; then
    echo "📅 Respaldos disponibles en Google Drive ($REMOTO):"
    rclone lsl "$REMOTO" | awk '{print $4}' | sed 's/respaldo_completo_//; s/\.tar\.gz$//' | sort
    echo ""
    echo "Uso: bash scripts/restaurar_drive.sh <AAAA-MM-DD>"
    exit 0
fi

FECHA="$1"
ARCHIVO="respaldo_completo_${FECHA}.tar.gz"
TMP_DIR=$(mktemp -d)

echo "☁️  Buscando $ARCHIVO en Google Drive..."
if ! rclone copy "$REMOTO/$ARCHIVO" "$TMP_DIR/" --quiet; then
    echo "❌ No se pudo descargar $ARCHIVO. Ejecuta '--listar' para ver las fechas disponibles."
    rm -rf "$TMP_DIR"
    exit 1
fi
if [ ! -f "$TMP_DIR/$ARCHIVO" ]; then
    echo "❌ No existe $ARCHIVO en Drive. Ejecuta '--listar' para ver las fechas disponibles."
    rm -rf "$TMP_DIR"
    exit 1
fi

echo "⚠️  Vas a REEMPLAZAR data/bitacora.db y media/ completos con el respaldo de $FECHA."
echo "⚠️  Se perderá todo lo registrado (y todas las fotos subidas) después de ese respaldo."
echo ""
read -r -p "Escribe SI en mayúsculas para confirmar: " CONFIRMACION
if [ "$CONFIRMACION" != "SI" ]; then
    echo "Cancelado. No se modificó nada."
    rm -rf "$TMP_DIR"
    exit 0
fi

echo "🗜️  Extrayendo $ARCHIVO..."
mkdir -p "$TMP_DIR/extraido"
tar -xzf "$TMP_DIR/$ARCHIVO" -C "$TMP_DIR/extraido"

TS=$(date +%Y%m%d_%H%M%S)
mkdir -p "backups/antes_de_restaurar_drive_${TS}"
if [ -f data/bitacora.db ]; then
    echo "📦 Guardando la base de datos actual por si hay que deshacer esta restauración..."
    cp data/bitacora.db "backups/antes_de_restaurar_drive_${TS}/bitacora.db"
fi
if [ -d media ]; then
    echo "📦 Guardando la carpeta media/ actual..."
    mv media "backups/antes_de_restaurar_drive_${TS}/media"
fi

echo "🛑 Deteniendo los servicios..."
systemctl stop bitacora-bot 2>/dev/null || true
systemctl stop bitacora-pwa 2>/dev/null || true

echo "♻️  Restaurando base de datos y fotos..."
mkdir -p data
cp "$TMP_DIR/extraido/bitacora.db" data/bitacora.db
if [ -d "$TMP_DIR/extraido/media" ]; then
    cp -r "$TMP_DIR/extraido/media" media
fi

echo "▶️  Reiniciando los servicios..."
systemctl start bitacora-bot 2>/dev/null || true
systemctl start bitacora-pwa 2>/dev/null || true
sleep 2
systemctl is-active bitacora-bot 2>/dev/null || true
systemctl is-active bitacora-pwa 2>/dev/null || true

rm -rf "$TMP_DIR"

echo "✅ Restaurado a la versión de ${FECHA} (base de datos + fotos)."
echo "   Copia de seguridad de lo que había antes: backups/antes_de_restaurar_drive_${TS}/"
