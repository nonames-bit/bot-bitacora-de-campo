#!/usr/bin/env bash
# ==============================================================================
# Restore drill semanal (auditoría P1.6, 2026-09-23)
#
# Un backup que NUNCA se restaura no es un backup: puede estar corrupto o
# incompleto y nadie lo sabe hasta la emergencia. Este script toma el backup
# local más reciente de backups/, lo restaura en un directorio temporal y corre
# `PRAGMA integrity_check` + un conteo básico. Si falla, notifica a los OWNER
# por Telegram (mismo mecanismo que healthcheck_vps.sh).
#
# Se agenda semanal en setup_vps.sh:
#   0 4 * * 0  <proyecto>/scripts/restore_drill.sh >> <proyecto>/backups/restore_drill.log 2>&1
# ==============================================================================
set -uo pipefail

DIR_RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR_RAIZ"

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

notificar_owner() {
    local mensaje="$1"
    if [ -z "${TELEGRAM_TOKEN:-}" ]; then
        return 0
    fi
    local destinatarios
    destinatarios=$(python3 -c "
import json
try:
    u = json.load(open('src/server/users.json'))
    print('\n'.join(str(x['user_id']) for x in u if str(x.get('rol', '')).strip().upper() == 'OWNER'))
except Exception:
    pass
" 2>/dev/null)
    for chat_id in $destinatarios; do
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            -d chat_id="$chat_id" -d parse_mode=HTML -d text="$mensaje" >/dev/null 2>&1
    done
}

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "$(date -Is) [WARN] sqlite3 no instalado; drill omitido."
    exit 0
fi

BACKUP="$(ls -1t backups/*.db 2>/dev/null | head -1 || true)"
if [ -z "$BACKUP" ]; then
    echo "$(date -Is) [WARN] No hay backups locales en backups/; drill omitido."
    exit 0
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "$(date -Is) [drill] Restaurando $BACKUP ..."
if ! cp "$BACKUP" "$TMP_DIR/drill.db"; then
    echo "$(date -Is) [ERROR] No se pudo copiar $BACKUP."
    notificar_owner "🔴 <b>Drill de restauración FALLÓ</b>: no se pudo leer $(basename "$BACKUP")."
    exit 1
fi

RESULTADO="$(sqlite3 "$TMP_DIR/drill.db" 'PRAGMA integrity_check;' 2>&1)"
if [ "$RESULTADO" != "ok" ]; then
    echo "$(date -Is) [ERROR] integrity_check='$RESULTADO' sobre $(basename "$BACKUP")."
    notificar_owner "🔴 <b>Drill de restauración FALLÓ</b>: <code>integrity_check</code> devolvió '$RESULTADO' sobre $(basename "$BACKUP"). El backup podría estar corrupto."
    exit 1
fi

N_ANIMALES="$(sqlite3 "$TMP_DIR/drill.db" 'SELECT COUNT(*) FROM animales;' 2>/dev/null || echo '?')"
echo "$(date -Is) [drill] OK: $(basename "$BACKUP") íntegro (animales=$N_ANIMALES)."
exit 0
