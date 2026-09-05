#!/usr/bin/env bash
# Despliega la última versión de main del repo GitHub en el VPS y reinicia el bot.
# Ejecutar EN el VPS: ssh root@206.189.188.183 'bash /root/bitacora/scripts/desplegar.sh'
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== Estado antes del despliegue =="
git log -1 --oneline

echo "== Descargando cambios de origin/main =="
git fetch origin main
git reset --hard origin/main

echo "== Instalando dependencias (por si cambiaron) =="
.venv/bin/pip install -q -r requirements.txt

echo "== Corriendo suite de pruebas antes de reiniciar =="
.venv/bin/python -m pytest -q

echo "== Reiniciando servicios (Bot Telegram + Dashboard PWA) =="
systemctl restart bitacora-bot bitacora-pwa
sleep 2
systemctl is-active bitacora-bot
systemctl is-active bitacora-pwa

echo "== Desplegado =="
git log -1 --oneline
