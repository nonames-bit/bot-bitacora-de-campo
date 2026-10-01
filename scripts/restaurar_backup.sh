#!/usr/bin/env bash
# ==============================================================================
# Restaura data/bitacora.db a partir de un respaldo (backups/AAAA-MM-DD.db,
# o una copia manual_… / antes_de_restaurar_…).
# Uso EN el servidor, desde la carpeta del proyecto:
#   bash scripts/restaurar_backup.sh --listar      (fechas disponibles)
#   bash scripts/restaurar_backup.sh 2026-08-29
#
# Lo mismo se puede hacer desde la app: Sistema → Copias (solo el propietario).
#
# Este script es para el caso "se dañó algo grande y hay que volver a como
# estaba ayer/anteayer" (ej. un trabajador borró o modificó por accidente
# muchos registros). Para corregir UN solo registro puntual use "Deshacer"
# en la app o /deshacer en Telegram: es más preciso y no pierde el resto del día.
#
# Es destructivo: reemplaza la base completa por la copia elegida y se pierde
# todo lo registrado DESPUÉS de esa copia. Por eso pide confirmación escrita y
# siempre guarda la base actual como backups/antes_de_restaurar_<fecha>.db.
#
# Funciona con Docker (docker compose, servicio "app") y sin Docker. Usa la
# API de backup de SQLite (src/engine/respaldos.py), así que no hay que
# detener la app ni el bot.
# ==============================================================================
set -euo pipefail

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

# Con Docker la base está dentro del contenedor "app"; sin Docker, aquí mismo.
if command -v docker >/dev/null 2>&1 && [ -f docker-compose.yml ] \
    && [ -n "$(docker compose ps -q app 2>/dev/null)" ]; then
    RESPALDOS=(docker compose exec -T app python -m src.engine.respaldos)
else
    PY="python3"
    [ -x .venv/bin/python ] && PY=".venv/bin/python"
    RESPALDOS=("$PY" -m src.engine.respaldos)
fi

if [ "${1:-}" = "--listar" ] || [ -z "${1:-}" ]; then
    echo "Copias disponibles en backups/:"
    "${RESPALDOS[@]}" listar
    echo ""
    echo "Uso: bash scripts/restaurar_backup.sh <AAAA-MM-DD | nombre.db>"
    exit 0
fi

COPIA="$1"
echo "ATENCIÓN: vas a REEMPLAZAR la base con la copia ${COPIA}."
echo "Se perderá todo lo registrado después de esa copia."
echo ""
read -r -p "Escribe SI en mayúsculas para confirmar: " CONFIRMACION
if [ "$CONFIRMACION" != "SI" ]; then
    echo "Cancelado. No se modificó nada."
    exit 0
fi

"${RESPALDOS[@]}" restaurar "$COPIA"
