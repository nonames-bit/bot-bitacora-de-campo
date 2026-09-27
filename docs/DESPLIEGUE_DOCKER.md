# 🐳 Despliegue con Docker

Guía para correr la Bitácora en Docker en cualquier servidor (DigitalOcean,
AWS, GCP, etc.) y para **migrar el servidor actual** (systemd + nginx en
`/root/bitacora`) sin perder datos.

## Qué incluye

| Pieza | Qué hace |
|---|---|
| `Dockerfile` | Imagen con la app, ffmpeg (voz), tesseract (OCR) y sqlite3. Corre con un usuario **sin privilegios** (uid 1000). |
| `docker-compose.yml` | Servicios `app` (PWA), `bot` (Telegram), `tareas` (respaldos, mercado, satélite), `caddy` (HTTPS) y `litestream` (réplica). |
| `deploy/Caddyfile` | HTTPS automático con Let's Encrypt y las mismas cabeceras de seguridad que tenía nginx. |
| `deploy/litestream.yml` | Copia la base en tiempo real a un almacenamiento S3 fuera del servidor. |
| `scripts/programador.py` | Reemplaza el cron: respaldo 03:00, mercado 06:00, NDVI cada 3 días, lluvia los lunes. |
| `scripts/endurecer_vps.sh` | Firewall, SSH solo con llave, fail2ban, actualizaciones automáticas e instalación de Docker. |
| `.github/workflows/docker.yml` | Cuando los tests pasan en `main`: verifica que la imagen se construye y (opcional) le pide al servidor que se actualice; el servidor arma la imagen (sin registro de paquetes, costo $0). |

Los datos viven **fuera del contenedor**, en carpetas del servidor:

```
/opt/bitacora/
├── data/      base de datos (bitacora.db), users.json, reportes, llaves de sesión
├── media/     fotos
├── backups/   respaldos diarios (30 días)
└── .env       claves y configuración (nunca va a GitHub)
```

---

## A. Migrar el servidor actual (paso a paso)

> Tiempo estimado: 30–45 min. La app queda fuera de línea solo unos minutos
> (del paso 4 al 6). Si algo falla, el paso **"Volver atrás"** deja todo como estaba.

### 0. Respaldo antes de empezar

```bash
ssh root@IP_DEL_SERVIDOR
cd /root/bitacora
sqlite3 data/bitacora.db ".backup '/root/antes-de-docker.db'"
tar czf /root/media-antes-de-docker.tgz media
```

### 1. Endurecer el servidor e instalar Docker

Confirme primero que entra por SSH **con su llave** (no con contraseña):

```bash
cd /root/bitacora && git pull
bash scripts/endurecer_vps.sh
```

### 2. Clonar el proyecto en `/opt/bitacora`

```bash
git clone https://github.com/nonames-bit/bot-bitacora-de-campo.git /opt/bitacora
cd /opt/bitacora
cp /root/bitacora/.env .env
```

Agregue al final de `/opt/bitacora/.env`:

```
DOMINIO=ganaderiaja.duckdns.org
```

### 3. Detener los servicios viejos

```bash
systemctl stop bitacora-pwa bitacora-bot nginx
systemctl disable bitacora-pwa bitacora-bot nginx
crontab -l > /root/crontab-antes-de-docker.txt   # guardar por si acaso
crontab -r                                       # las tareas ahora las corre Docker
```

### 4. Pasar los datos

```bash
cd /opt/bitacora
mkdir -p data media backups
cp -a /root/bitacora/data/. data/
cp -a /root/bitacora/media/. media/
cp /root/bitacora/src/server/users.json data/users.json
chown -R 1000:1000 data media backups
```

### 5. Arrancar

```bash
docker compose up -d --build
docker compose ps          # app debe quedar "healthy" en ~1 minuto
docker compose logs -f app # Ctrl+C para salir
```

Caddy saca el certificado HTTPS solo la primera vez (unos segundos).

### 6. Comprobar

- Abra `https://ganaderiaja.duckdns.org` y entre con su PIN.
- Revise que están sus animales, fotos y usuarios.
- `docker compose logs bot --tail 20` → el bot de Telegram responde.

### Volver atrás (si algo falla)

```bash
cd /opt/bitacora && docker compose down
systemctl enable --now nginx bitacora-pwa bitacora-bot
crontab /root/crontab-antes-de-docker.txt
```

Los datos originales en `/root/bitacora` no se tocaron.

---

## B. Réplica de la base en la nube (Litestream)

Guarda cada cambio de la base, cada 10 segundos, en un almacenamiento fuera
del servidor. Si el servidor se daña, se recupera todo con 30 días de historial.

1. Cree un bucket privado (DigitalOcean Spaces, AWS S3, Backblaze B2 o
   Cloudflare R2) y una llave de acceso solo para ese bucket.
2. En `.env`:
   ```
   LITESTREAM_ACCESS_KEY_ID=...
   LITESTREAM_SECRET_ACCESS_KEY=...
   LITESTREAM_REPLICA_URL=s3://nombre-del-bucket/bitacora
   LITESTREAM_ENDPOINT=https://nyc3.digitaloceanspaces.com   # vacío si es AWS
   ```
3. Arrancar: `docker compose --profile replica up -d`
4. Probar que se puede restaurar (sin tocar la base real):
   ```bash
   docker compose --profile replica run --rm litestream \
     restore -o /app/data/prueba-restaurada.db /app/data/bitacora.db
   ```

**Restaurar de verdad** (servidor nuevo o base dañada):

```bash
docker compose stop app bot tareas
docker compose --profile replica run --rm litestream \
  restore -o /app/data/bitacora.db /app/data/bitacora.db
docker compose up -d
```

Las fotos (`media/`) no las copia Litestream. Para ellas se puede seguir
usando `scripts/respaldo_drive.sh` (rclone) desde el cron del servidor sobre
`/opt/bitacora/media` y `/opt/bitacora/backups`.

---

## C. Despliegue automático desde GitHub

Cuando se fusiona un PR y los tests pasan, GitHub comprueba que la imagen se
construye y le avisa al servidor, que descarga el código nuevo y **arma la
imagen él mismo**. No se usa almacenamiento de paquetes de GitHub (costo $0).

1. **Llave de despliegue**: en el servidor,
   ```bash
   ssh-keygen -t ed25519 -f /root/.ssh/despliegue -N ""
   cat /root/.ssh/despliegue.pub >> /root/.ssh/authorized_keys
   cat /root/.ssh/despliegue      # copiar TODO, de -----BEGIN a END-----
   ```
2. **En GitHub** → Settings → Secrets and variables → Actions → *New repository secret*:
   - `VPS_HOST` = IP del servidor
   - `VPS_USUARIO` = `root`
   - `VPS_SSH_KEY` = la llave privada que copió
   - (variable opcional) `VPS_DIR` = `/opt/bitacora`
3. Si el repositorio es **privado**, el servidor necesita poder hacer
   `git pull`: agregue `/root/.ssh/despliegue.pub` (u otra llave del servidor)
   como *Deploy key* de solo lectura en GitHub → Settings → Deploy keys, y
   clone con `git@github.com:nonames-bit/bot-bitacora-de-campo.git`.

Sin los secrets, el workflow solo verifica que la imagen se construye; no toca el servidor.
El avance se ve en la pestaña **Actions**, flujo **docker**.

**Actualizar a mano** (sin GitHub Actions):

```bash
cd /opt/bitacora && git pull && docker compose up -d --build
```

**Volver a una versión anterior**:

```bash
cd /opt/bitacora && git log --oneline -5      # elegir el commit bueno
git checkout <commit> && docker compose up -d --build
# para volver a la última versión: git checkout main && git pull
```

---

## D. Una finca nueva desde cero

```bash
git clone https://github.com/nonames-bit/bot-bitacora-de-campo.git /opt/finca-x
cd /opt/finca-x && cp .env.example .env     # completar DOMINIO, PWA_PASSWORD, etc.
mkdir -p data media backups && chown -R 1000:1000 data media backups
docker compose build
docker compose run --rm --no-deps app python -c \
  "from src.db.database import Database; Database('/app/data/bitacora.db').create_tables()"
cp src/server/users.example.json data/users.json   # editar el OWNER
docker compose up -d
```

---

## Operación diaria

| Tarea | Comando |
|---|---|
| Estado | `docker compose ps` |
| Ver errores de la app | `docker compose logs app --tail 100` |
| Reiniciar | `docker compose restart app` |
| Respaldo manual ahora | `docker compose exec tareas python -c "from scripts import programador; programador.respaldo_local()"` |
| Entrar a la base | `sqlite3 /opt/bitacora/data/bitacora.db` |
| Espacio en disco | `docker system df` · limpiar imágenes viejas: `docker image prune -f` |

**Seguridad aplicada:** la app corre sin root y sin capacidades extra
(`cap_drop: ALL`, `no-new-privileges`). Solo Caddy expone los puertos 80 y
443. Las claves viven en `.env` (fuera de GitHub y de la imagen). HTTPS usa
HSTS y CSP. El firewall solo deja pasar 22, 80 y 443, y SSH solo acepta llave.
