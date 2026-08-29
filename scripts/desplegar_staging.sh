#!/usr/bin/env bash
# Despliega una rama (por defecto main) en el bot de STAGING (@pruebasgan_bot,
# /root/bitacora-staging) sin tocar producción. Útil para probar cambios con
# datos reales-pero-desechables antes de mergear a main y correr
# scripts/desplegar.sh en producción.
#
# Uso: bash scripts/desplegar_staging.sh [rama]
set -euo pipefail

RAMA="${1:-main}"
cd "$(dirname "$0")/.."

echo "== Desplegando rama '$RAMA' en STAGING (/root/bitacora-staging) =="
git fetch origin "$RAMA"
git checkout "$RAMA"
git reset --hard "origin/$RAMA"

echo "== Instalando dependencias =="
.venv/bin/pip install -q -r requirements.txt

echo "== Corriendo suite de pruebas =="
.venv/bin/python -m pytest -q

echo "== Reiniciando bitacora-bot-staging =="
systemctl restart bitacora-bot-staging
sleep 2
systemctl is-active bitacora-bot-staging

echo "== Desplegado en staging =="
git log -1 --oneline
echo "Prueba en Telegram: @pruebasgan_bot"
