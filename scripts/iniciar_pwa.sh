#!/usr/bin/env bash
# ==============================================================================
# Arranque del Dashboard PWA ejecutivo (Fase 7 Etapa D, solo online, puerto 8080)
# Uso: bash scripts/iniciar_pwa.sh  (corre en proceso aparte, no bloquea el bot)
# ==============================================================================
set -e
DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"
if [ -f ".venv/bin/activate" ]; then
  echo "ℹ️ Activando entorno virtual (.venv)..."
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export BITACORA_DB="${BITACORA_DB:-data/bitacora.db}"
export PWA_PORT="${PWA_PORT:-8080}"
echo "🚀 Iniciando PWA Bitácora JA en puerto ${PWA_PORT} (DB=${BITACORA_DB})..."
exec python src/pwa/app.py
