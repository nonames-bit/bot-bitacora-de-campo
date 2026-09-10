#!/usr/bin/env bash
# ==============================================================================
# Script de configuración y despliegue para Ubuntu 22.04 LTS (VPS)
# ==============================================================================
set -e

echo "=== [1/7] Actualizando repositorios del sistema ==="
sudo apt-get update -y

echo "=== [2/7] Instalando paquetes base de Python, audio, OCR y utilidades ==="
sudo apt-get install -y python3 python3-venv python3-pip ufw ffmpeg sqlite3 tesseract-ocr tesseract-ocr-spa


echo "=== [3/7] Configurando cortafuegos (UFW) para permitir OpenSSH ==="
sudo ufw allow OpenSSH || true

echo "=== [4/7] Creando directorios del proyecto ==="
mkdir -p data media backups

echo "=== [5/7] Configurando entorno virtual e instalando dependencias ==="
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "=== [6/7] Configurando variables de entorno (.env) ==="
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️ Se ha creado el archivo .env desde .env.example."
    echo "   Recuerda editar .env con tu TELEGRAM_TOKEN antes de iniciar el bot."
else
    echo "ℹ️ El archivo .env ya existe."
fi

echo "=== [7/7] Configurando tarea programada en cron (backup diario 3:00 AM) ==="
PROYECTO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_SCRIPT="$PROYECTO_DIR/scripts/backup_diario.sh"
chmod +x "$BACKUP_SCRIPT" "$PROYECTO_DIR/scripts/iniciar_bot.sh" "$PROYECTO_DIR/scripts/importar_backup.sh" || true

CRON_CMD="0 3 * * * $BACKUP_SCRIPT >> $PROYECTO_DIR/bot.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "$BACKUP_SCRIPT" ; echo "$CRON_CMD") | crontab -

MERCADO_SCRIPT="$PROYECTO_DIR/scripts/actualizar_precios_mercado.py"
chmod +x "$MERCADO_SCRIPT" || true
CRON_MERCADO="0 6 * * * $PROYECTO_DIR/.venv/bin/python $MERCADO_SCRIPT >> $PROYECTO_DIR/mercado.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "$MERCADO_SCRIPT" ; echo "$CRON_MERCADO") | crontab -

echo "✅ Configuración del VPS completada con éxito."
echo "   Para iniciar el bot ejecuta: ./scripts/iniciar_bot.sh"
