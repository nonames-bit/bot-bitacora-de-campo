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
# requirements.txt es el lock pinneado (auditoría P1.7). Si el intérprete del
# VPS no puede instalarlo (otra versión de Python), se cae a requirements.in
# para no dejar el deploy roto; en ese caso conviene regenerar el lock EN el VPS:
#   uv pip compile requirements.in --python-version "$(python3 -V | cut -d' ' -f2)" -o requirements.txt
if ! .venv/bin/pip install -q -r requirements.txt; then
    echo "⚠️ Lock requirements.txt no instalable en este intérprete; usando requirements.in (sin pin)."
    .venv/bin/pip install -q -r requirements.in
fi
# requirements-dev.txt: pytest/ruff, necesarios para la puerta de pruebas de abajo.
.venv/bin/pip install -q -r requirements-dev.txt

echo "== Corriendo suite de pruebas antes de reiniciar =="
.venv/bin/python -m pytest -q

echo "== Verificando datos históricos zootécnicos profundos =="
if [ -f "docs/Datos20260823.Zip" ]; then
    .venv/bin/python -m src.importers.extractor_historico_sg docs/Datos20260823.Zip data/bitacora.db || true
    .venv/bin/python -m scripts.migrar_composicion_sg data/bitacora.db docs/Datos20260823.Zip || true
fi

echo "== Reiniciando servicios (Bot Telegram + Dashboard PWA) =="
systemctl restart bitacora-bot bitacora-pwa
sleep 2
systemctl is-active bitacora-bot
systemctl is-active bitacora-pwa

echo "== Desplegado =="
git log -1 --oneline
