#!/usr/bin/env bash
# Verifica la salud del bot en el VPS (servicio, disco, frescura de la base de
# datos) y notifica por Telegram a los usuarios OWNER si algo falla.
# Pensado para correr por cron cada 10-15 min:
#   */15 * * * * /root/bitacora/scripts/healthcheck_vps.sh >> /root/bitacora/backups/healthcheck.log 2>&1
set -uo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

ESTADO_FILE="/tmp/.bitacora_healthcheck_estado"
touch "$ESTADO_FILE"

ya_avisado() {
    grep -qx "$1" "$ESTADO_FILE" 2>/dev/null
}

enviar_alerta() {
    local mensaje="$1"
    local clave="$2"
    if ya_avisado "$clave"; then
        return 0
    fi
    if [ -z "${TELEGRAM_TOKEN:-}" ]; then
        echo "$(date -Is) [WARN] TELEGRAM_TOKEN vacío, no se puede notificar: $mensaje"
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
    echo "$clave" >> "$ESTADO_FILE"
    echo "$(date -Is) [ALERTA] $clave -> $mensaje"
}

limpiar_alerta() {
    sed -i "/^${1}\$/d" "$ESTADO_FILE" 2>/dev/null || true
}

# 1. Servicio del bot activo
if systemctl is-active --quiet bitacora-bot; then
    limpiar_alerta "bot_caido"
else
    enviar_alerta "🔴 <b>ALERTA: bitacora-bot NO está activo</b> en el VPS.
Revisar con: <code>systemctl status bitacora-bot</code>" "bot_caido"
fi

# 2. Espacio en disco
USO_DISCO=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "${USO_DISCO:-0}" -ge 90 ] 2>/dev/null; then
    enviar_alerta "⚠️ <b>Disco del VPS al ${USO_DISCO}%.</b> Revisar espacio disponible." "disco_lleno"
else
    limpiar_alerta "disco_lleno"
fi

# 3. Frescura de la base de datos (señal de bot inactivo o sincronización detenida)
if [ -f data/bitacora.db ]; then
    EDAD_HORAS=$(( ($(date +%s) - $(stat -c %Y data/bitacora.db)) / 3600 ))
    if [ "$EDAD_HORAS" -ge 72 ]; then
        enviar_alerta "🟡 <b>La base de datos no se actualiza hace ${EDAD_HORAS}h.</b>
Verificar si hay notas de campo llegando y si la sincronización de backups SG sigue activa." "db_desactualizada"
    else
        limpiar_alerta "db_desactualizada"
    fi
fi
