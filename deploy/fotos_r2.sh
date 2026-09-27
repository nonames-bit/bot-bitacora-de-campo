#!/bin/sh
# Copia las fotos (media/) y users.json al mismo bucket S3/R2 de Litestream.
# Corre en el servicio "fotos" de docker-compose.yml (perfil "replica").
#
# - Usa las mismas llaves del .env: LITESTREAM_ACCESS_KEY_ID,
#   LITESTREAM_SECRET_ACCESS_KEY, LITESTREAM_ENDPOINT.
# - Destino: <bucket de LITESTREAM_REPLICA_URL>/fotos (o FOTOS_DESTINO).
# - "copy", no "sync": una foto borrada en el servidor se conserva en la nube.
# - Solo sube lo nuevo o cambiado. Repite cada FOTOS_INTERVALO segundos (6 h).
set -u

BUCKET="${LITESTREAM_REPLICA_URL#s3://}"
BUCKET="${BUCKET%%/*}"
DESTINO="${FOTOS_DESTINO:-$BUCKET/fotos}"
INTERVALO="${FOTOS_INTERVALO:-21600}"
MARCA=/tmp/ultima-copia-ok

export HOME=/tmp
export RCLONE_CONFIG=/dev/null   # todo sale de las variables RCLONE_CONFIG_R2_*
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER="${FOTOS_PROVEEDOR:-Cloudflare}"
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="${LITESTREAM_ACCESS_KEY_ID:-}"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="${LITESTREAM_SECRET_ACCESS_KEY:-}"
export RCLONE_CONFIG_R2_ENDPOINT="${LITESTREAM_ENDPOINT:-}"
# El token de R2 solo tiene permiso sobre el bucket: no intentar crearlo.
export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true

# FOTOS_SOLO_CONFIG=1 y ". fotos_r2.sh": deja el remoto r2 y $DESTINO listos
# sin copiar nada (para restaurar, ver docs/DESPLIEGUE_DOCKER.md).
if [ "${FOTOS_SOLO_CONFIG:-}" = 1 ]; then
    return 0 2>/dev/null || exit 0
fi

if [ -z "$BUCKET" ] || [ -z "$RCLONE_CONFIG_R2_ACCESS_KEY_ID" ]; then
    echo "[fotos] Falta LITESTREAM_REPLICA_URL o LITESTREAM_ACCESS_KEY_ID en .env; no se copia nada."
    sleep 3600
    exit 1
fi

echo "[fotos] Copiando media/ y users.json a r2:$DESTINO cada $INTERVALO s"
while true; do
    ok=1
    rclone copy /origen/media "r2:$DESTINO/media" --transfers 4 --stats-one-line --stats 0 -v || ok=0
    if [ -f /origen/data/users.json ]; then
        rclone copyto /origen/data/users.json "r2:$DESTINO/users.json" -v || ok=0
    fi
    if [ "$ok" = 1 ]; then
        date > "$MARCA"
        echo "[fotos] Copia completa $(date '+%F %T')"
    else
        rm -f "$MARCA"
        echo "[fotos] La copia falló; se reintenta en $INTERVALO s"
    fi
    sleep "$INTERVALO"
done
