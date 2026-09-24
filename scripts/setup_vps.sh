#!/usr/bin/env bash
# ==============================================================================
# Script de configuración y despliegue para Ubuntu 22.04 LTS (VPS)
# ==============================================================================
set -e

echo "=== [1/7] Actualizando repositorios del sistema ==="
sudo apt-get update -y

echo "=== [2/7] Instalando paquetes base de Python, audio, OCR y utilidades ==="
sudo apt-get install -y python3 python3-venv python3-pip ufw ffmpeg sqlite3 tesseract-ocr tesseract-ocr-spa


echo "=== [3/7] Configurando cortafuegos (UFW): SSH + Nginx Full ==="
sudo ufw allow OpenSSH || true
# La PWA se sirve por nginx en 80/443. Sin permitirlos, habilitar UFW dejaba la
# PWA inalcanzable (solo SSH estaba permitido y nunca se hacía `ufw enable`).
# 'Nginx Full' depende del perfil de nginx; si aún no existe, se abren los
# puertos explícitos para no dejar el sitio inaccesible.
if ! sudo ufw allow 'Nginx Full' 2>/dev/null; then
    sudo ufw allow 80/tcp || true
    sudo ufw allow 443/tcp || true
fi
sudo ufw --force enable || true

echo "=== [4/7] Creando directorios del proyecto ==="
mkdir -p data media backups

echo "=== [5/7] Configurando entorno virtual e instalando dependencias ==="
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
# requirements.txt es el lock pinneado (auditoría P1.7). Si el intérprete del
# VPS no puede instalarlo, se cae a requirements.in para no dejar la PWA sin
# dependencias; regenerar el lock EN el VPS si eso ocurre:
#   uv pip compile requirements.in --python-version "$(python3 -V | cut -d' ' -f2)" -o requirements.txt
if ! .venv/bin/pip install -r requirements.txt; then
    echo "⚠️ Lock requirements.txt no instalable en este intérprete; usando requirements.in (sin pin)."
    .venv/bin/pip install -r requirements.in
fi

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

# Respaldo offsite a Google Drive (auditoría P1.6: existía el script pero NUNCA
# se agendaba, así que el respaldo "fuera del servidor" no ocurría).
RESPALDO_DRIVE="$PROYECTO_DIR/scripts/respaldo_drive.sh"
chmod +x "$RESPALDO_DRIVE" || true
CRON_DRIVE="30 3 * * * $RESPALDO_DRIVE >> $PROYECTO_DIR/backups/respaldo_drive.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "$RESPALDO_DRIVE" ; echo "$CRON_DRIVE") | crontab -

# Healthcheck cada 15 min (bot + PWA + nginx + HTTPS + disco + frescura de DB).
HEALTHCHECK_SCRIPT="$PROYECTO_DIR/scripts/healthcheck_vps.sh"
chmod +x "$HEALTHCHECK_SCRIPT" || true
CRON_HEALTH="*/15 * * * * $HEALTHCHECK_SCRIPT >> $PROYECTO_DIR/backups/healthcheck.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "$HEALTHCHECK_SCRIPT" ; echo "$CRON_HEALTH") | crontab -

# Drill de restauración semanal (domingo 4:00): restaura el último backup local
# en un dir temporal y valida PRAGMA integrity_check.
DRILL_SCRIPT="$PROYECTO_DIR/scripts/restore_drill.sh"
chmod +x "$DRILL_SCRIPT" || true
CRON_DRILL="0 4 * * 0 $DRILL_SCRIPT >> $PROYECTO_DIR/backups/restore_drill.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "$DRILL_SCRIPT" ; echo "$CRON_DRILL") | crontab -

echo "✅ Configuración del VPS completada con éxito."
echo "   Para iniciar el bot ejecuta: ./scripts/iniciar_bot.sh"
