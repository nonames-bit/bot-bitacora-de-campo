# 📡 Despliegue en DigitalOcean (VPS) — Fase 1

> Guía paso a paso para subir el **Bot de Bitácora de Campo Ganadero** a un
> servidor en la nube (VPS) de DigitalOcean. Escrita para una persona **no
> experta**: solo hay que copiar, pegar y leer. No se requiere saber programar.

**Qué vamos a lograr:** un servidor pequeño y barato (≈ $6/mes) que corre el bot
de Telegram las 24 horas, guarda la base de datos, hace un respaldo diario
automático y sobrevive a reinicios.

---

## 0. Qué necesita antes de empezar

- Una cuenta en [DigitalOcean](https://www.digitalocean.com) con una tarjeta o
  saldo cargado.
- El código de este proyecto en su computadora (la carpeta
  `2026-08-24-bot-bitacora-de-campo`).
- El archivo de backup histórico `docs/Datos20260823.Zip` (viene dentro del
  proyecto).
- Unos 30–45 minutos con calma. ☕

---

## 1. Crear el droplet (el servidor)

Un **droplet** es el nombre que DigitalOcean le da a cada servidor virtual.

1. Entre a DigitalOcean y haga clic en **Create → Droplets** (Crear Droplets).
2. En **Image** (imagen) elija **Ubuntu 22.04 (LTS) x64**.
3. En **Plan**, elija el **Basic** de **$6/mes** (1 GB de RAM es suficiente para
   este bot).
4. En **Datacenter region**, elija la región **más cercana a usted** (por
   ejemplo "New York" para América o la que le quede más cerca), para que
   responda rápido.
5. En **Authentication**, seleccione **SSH Key** y agregue su llave pública SSH.
   - Si no tiene una llave SSH todavía, en su computadora ejecute
     `ssh-keygen` (acepte todo por defecto) y copie el contenido del archivo
     `~/.ssh/id_rsa.pub` (o `id_ed25519.pub`) al cuadro de DigitalOcean.
6. Deje el resto como está y haga clic en **Create Droplet**.
7. Anote la **dirección IP** del droplet (algo como `143.198.10.20`). La verá en
   el panel.

> 💡 En esta guía usamos `IP_DEL_DROPLET` como marcador. Reemplácela siempre por
> la IP real de su droplet.

---

## 2. Conectarse por SSH y copiar el proyecto

Abra una terminal en su computadora (PowerShell, CMD con WSL, Terminal de macOS
o Linux) y conéctese al droplet:

```bash
ssh root@IP_DEL_DROPLET
```

La primera vez le preguntará si confía en el servidor: escriba `yes` y Enter.
Ya está dentro del droplet (el prompt cambia a algo como `root@nombre:~#`).

Ahora traiga el proyecto. Tiene **dos opciones**:

**Opción A — Clonar con git (si el proyecto está en un repositorio remoto):**

```bash
apt-get install -y git
git clone URL_DEL_REPOSITORIO /root/bitacora
cd /root/bitacora
```

**Opción B — Copiar la carpeta desde su computadora (sin repositorio remoto):**

Salga del droplet (`exit`), y desde su computadora copie la carpeta completa:

```bash
scp -r ruta/local/2026-08-24-bot-bitacora-de-campo root@IP_DEL_DROPLET:/root/bitacora
```

Luego vuelva a entrar y sitúese en la carpeta:

```bash
ssh root@IP_DEL_DROPLET
cd /root/bitacora
```

> 📌 En esta guía asumimos que el proyecto vive en `/root/bitacora`. Si lo puso
> en otra carpeta, ajuste las rutas cuando se indique.

---

## 3. Configurar el servidor (script automático)

Dentro de `/root/bitacora`, ejecute el script de configuración. Este paso:
actualiza el sistema, instala Python y utilidades, abre el puerto SSH en el
cortafuegos, crea las carpetas `data/`, `media/` y `backups/`, crea el entorno
virtual con las dependencias, prepara el `.env` y programa el **respaldo diario**.

```bash
bash scripts/setup_vps.sh
```

Al terminar verá `✅ Configuración del VPS completada con éxito.`

> ℹ️ El script crea `.env` a partir de `.env.example`. **Aún falta poner el
> token del bot** (paso siguiente).

---

## 4. Crear el bot en Telegram y configurar el token

1. En Telegram, busque a **@BotFather** (el "padre" oficial de los bots) y
   ábralo.
2. Envíele el comando `/newbot`.
3. BotFather le pedirá un **nombre** para el bot (ej. `Bitácora Finca`) y un
   **usuario** que debe terminar en `bot` (ej. `bitacora_finca_bot`).
4. BotFather le responderá con un **token** largo, algo como
   `123456789:ABCdefGhIJKlmNoPQRsTUVwxYZ`. **Cópielo.**
5. En el droplet, edite el archivo `.env`:

```bash
nano /root/bitacora/.env
```

Reemplace la línea del token así (pegue su token real):

```env
TELEGRAM_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxYZ
```

Guarde con `Ctrl+O`, Enter, y salga con `Ctrl+X`.

> 🔒 El token es una **clave secreta**: no lo comparta ni lo suba a ningún lado
> público. Por eso vive solo en el `.env` del servidor.

---

## 5. Sembrar los usuarios autorizados (quiénes pueden usar el bot)

El bot solo responde a usuarios registrados en `src/server/users.json`. Para
arrancar, sembramos al **OWNER** (dueño).

### 5.1. Obtener su `user_id` de Telegram

El `user_id` es el número único que Telegram le asigna a cada persona. Tiene dos
formas fiables de averiguarlo:

- **Más fácil — con @userinfobot:** en Telegram busque a **@userinfobot**,
  ábrale el chat y envíele `/start`. Le responderá con su **Id** (un número).
  Ese es su `user_id`.

- **Alternativa — con los registros del bot:** el bot anota cada intento de
  acceso no autorizado en el archivo de logs. Arranque el bot (ver paso 7),
  mándele cualquier mensaje desde su Telegram personal, y luego lea el log:

  ```bash
  grep "no autorizado" /root/bitacora/bot.log
  ```

  Verá una línea como `Intento de acceso no autorizado: user_id=123456789`.
  Ese número es su `user_id`. (Luego detenga el bot con `Ctrl+C` y siga.)

> ⚠️ El bot **no** muestra su `user_id` por chat a desconocidos (por seguridad
> responde `⛔ No autorizado.`). Use una de las dos formas de arriba.

### 5.2. Crear y editar `users.json`

```bash
cp src/server/users.example.json src/server/users.json
nano src/server/users.json
```

Cambie el `user_id` del **OWNER** por el suyo. Puede dejar el del trabajador
para después o poner ya el del mayordomo si lo conoce:

```json
[
  {
    "user_id": 123456789,
    "nombre": "Duenio",
    "rol": "OWNER"
  },
  {
    "user_id": 987654321,
    "nombre": "Mayordomo",
    "rol": "TRABAJADOR"
  }
]
```

Guarde con `Ctrl+O`, Enter, `Ctrl+X`. Los roles válidos son `OWNER`, `ADMIN` y
`TRABAJADOR`.

> 💡 Una vez que el dueño ya está dado de alta como OWNER, puede agregar al
> resto del personal directamente desde Telegram con
> `/agregar_usuario <user_id> <ROL> [nombre]` (solo el OWNER puede hacerlo).

---

## 6. Importar el backup histórico (Software Ganadero SG)

Si tiene el backup de Software Ganadero (`docs/Datos20260823.Zip`), impórtelo
para que el bot arranque con los animales y el historial ya cargados.

> 💡 Si en el paso 2 copió la carpeta completa con `scp -r` (Opción B), el Zip ya
> está en el servidor, en `/root/bitacora/docs/Datos20260823.Zip`, y puede saltar
> la subida e importar directo con esa ruta.

1. Desde **su computadora**, suba el archivo al droplet:

   ```bash
   scp ruta/local/2026-08-24-bot-bitacora-de-campo/docs/Datos20260823.Zip root@IP_DEL_DROPLET:/tmp/
   ```

2. En el **droplet**, ejecute el importador apuntando al archivo subido (o a la
   ruta del proyecto si ya estaba ahí):

   ```bash
   cd /root/bitacora
   bash scripts/importar_backup.sh /tmp/Datos20260823.Zip
   ```

Al terminar verá `✅ Importación completada con éxito.` y los datos quedarán en
`data/bitacora.db`.

---

## 7. Arrancar el bot

Para probarlo de forma inmediata (se detiene si cierra la terminal):

```bash
cd /root/bitacora
bash scripts/iniciar_bot.sh
```

Vaya a Telegram y envíele `/start` al bot con la cuenta del OWNER. Si todo está
bien, le mostrará la ayuda con sus comandos. 🎉

### Autoarranque con systemd (recomendado para producción)

Para que el bot **se reinicie solo** si el servidor se reinicia, créelo como
servicio del sistema:

```bash
nano /etc/systemd/system/bitacora-bot.service
```

Pegue este contenido (ajuste las rutas si el proyecto no está en `/root/bitacora`):

```ini
[Unit]
Description=Bot de Bitacora de Campo Ganadero (Telegram)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/bitacora
ExecStart=/root/bitacora/.venv/bin/python -m src.main --server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Guarde (`Ctrl+O`, Enter, `Ctrl+X`) y active el servicio:

```bash
systemctl daemon-reload
systemctl enable bitacora-bot
systemctl start bitacora-bot
systemctl status bitacora-bot
```

Si el estado dice `active (running)`, el bot está corriendo y arrancará solo con
el servidor. Para ver los logs en vivo: `journalctl -u bitacora-bot -f`.

---

## 8. Respaldos: backup diario automático + snapshots

### Backup diario automático (ya quedó configurado)

El paso 3 (`setup_vps.sh`) ya programó una tarea **cron a las 3:00 AM** que
ejecuta `scripts/backup_diario.sh`. Ese script:

- Copia la base de datos `data/bitacora.db` a `backups/AAAA-MM-DD.db`.
- **Elimina automáticamente los respaldos con más de 30 días** (retención 30
  días), para no llenar el disco.
- Usa `sqlite3` si está instalado; si no, hace una copia simple del archivo
  (igual de válida).

Para comprobar que la tarea quedó agendada:

```bash
crontab -l
```

Debería ver una línea como:
`0 3 * * * /root/bitacora/scripts/backup_diario.sh >> /root/bitacora/bot.log 2>&1`

### Snapshots de DigitalOcean (recomendado, ≈ $1/mes)

Además del backup diario, active **Snapshots** del droplet en DigitalOcean
(Backups/Snapshots en el menú del droplet). Un snapshot guarda una "foto"
completa del servidor (sistema + código + datos) y permite restaurarlo entero si
algo falla. El plan recomendado cuesta alrededor de **$1/mes**.

> ✅ Regla de oro: el backup diario protege la **base de datos**; el snapshot
> protege **el servidor completo**. Con ambos, la finca queda bien respaldada.

---

## 🛰️ NDVI satelital real (Fase C del plan geoespacial)

El comando `/ndvi` lee el índice de vegetación real de cada potrero desde la
tabla `monitoreo_satelital_ndvi`, calculado por Google Earth Engine sobre
Sentinel-2 (ver `docs/PLAN_GEO_SATELITAL_6.2_8.2.md`). Esa tabla no se llena
sola: hay que correr `scripts/actualizar_ndvi_satelital.py` — un job liviano
(no requiere GPU ni procesa imágenes localmente, todo el cálculo ocurre en los
servidores de Earth Engine) que conviene programar **una vez por semana** (el
revisita de Sentinel-2 es cada ~5 días, y en época de lluvias puede tardar más
en aparecer una imagen despejada).

### 1. Subir la clave de la cuenta de servicio al VPS (una sola vez)

La clave `.json` de Earth Engine **nunca se sube al repositorio git**. Se sube
directo al servidor por `scp`, a una ruta fuera del proyecto:

```bash
# Desde su PC (Windows PowerShell), reemplace la ruta local y la IP del droplet:
scp "C:\Users\Owner\Documents\secrets\finca-mesetas-ndvi-XXXXXXXX.json" root@SU_IP_DEL_DROPLET:/root/secrets/ndvi-key.json
```

### 2. Configurar las variables en `.env`

En el servidor, edite `/root/bitacora/.env` y agregue (o descomente) estas
tres líneas con sus valores reales:

```bash
GEE_SERVICE_ACCOUNT_EMAIL=ndvi-bot-bitacora@SU_PROJECT_ID.iam.gserviceaccount.com
GEE_SERVICE_ACCOUNT_KEY_PATH=/root/secrets/ndvi-key.json
GEE_PROJECT_ID=SU_PROJECT_ID
```

### 3. Probar el job manualmente

```bash
cd /root/bitacora
source .venv/bin/activate
set -a; source .env; set +a
python scripts/actualizar_ndvi_satelital.py
```

Debe ver una línea `✅` por cada potrero con `geom_wkt_4326` (los 20 códigos
`A01-A04`/`B01-B02`/`C01-C14` de la Fase B). Si un potrero sale con
`⚠️ sin imagen Sentinel-2 reciente`, no es un error — simplemente no hubo
todavía una imagen suficientemente despejada sobre ese potrero en la ventana
de búsqueda; se resuelve solo en la próxima corrida semanal.

### 4. Programar el job semanal en cron

```bash
crontab -e
```

Agregue esta línea (corre todos los lunes a las 6:00 AM):

```
0 6 * * 1 cd /root/bitacora && /root/bitacora/.venv/bin/python scripts/actualizar_ndvi_satelital.py >> /root/bitacora/bot.log 2>&1
```

> ⚠️ El cron no carga `.env` automáticamente como sí hace `source`. Si el
> script falla solo desde cron (pero funciona a mano), envuelva la línea en un
> script `.sh` que haga `set -a; source /root/bitacora/.env; set +a` antes de
> llamar a `python`, igual que en el paso 3.

---

## 🌧️ Lluvia satelital de referencia (Fase D del plan geoespacial)

El comando `/clima` muestra, junto al registro real de `/lluvia`, un estimado
satelital de contraste calculado con **CHIRPS** (`UCSB-CHG/CHIRPS/DAILY`) vía
el mismo Earth Engine que la Fase C — **no requiere credenciales nuevas**,
reutiliza las variables `GEE_*` ya configuradas arriba. El dato no reemplaza
el pluviómetro físico: la resolución de CHIRPS (~5.5 km) no distingue
microclima entre sectores de una sola finca, así que es un único valor a
nivel de finca completa, no por potrero.

### 1. Probar el job manualmente

```bash
cd /root/bitacora
source .venv/bin/activate
set -a; source .env; set +a
python scripts/actualizar_lluvia_satelital.py
```

Debe ver `✅ Lluvia estimada guardada: X mm en los últimos 30 días (referencia
AAAA-MM-DD)`. **Ojo:** esa fecha de referencia normalmente va a estar
**semanas atrás** de la fecha de hoy — a diferencia de Sentinel-2, CHIRPS
tiene una latencia real de ~30-45 días en el catálogo de Earth Engine, así
que el job siempre busca hacia atrás la fecha más reciente con dato
disponible. No es un error ni un job desactualizado; es el comportamiento
esperado del dataset. Si sale `⚠️ sin cobertura CHIRPS en absoluto`, ahí sí
revise que el centroide de la finca (`potreros.centroide_lat/lon`) esté
dentro del área de cobertura de CHIRPS (50°S-50°N).

### 2. Programar el job semanal en cron

```bash
crontab -e
```

Agregue esta línea (corre todos los lunes a las 6:05 AM, 5 minutos después
del job de NDVI para no chocar cuotas de Earth Engine):

```
5 6 * * 1 cd /root/bitacora && /root/bitacora/.venv/bin/python scripts/actualizar_lluvia_satelital.py >> /root/bitacora/bot.log 2>&1
```

---

## 🔄 Rutina de sincronización semanal/mensual (Fase 1.1)

Cuando usted cargó en el Software Ganadero SG los eventos que reportaron los
trabajadores por Telegram, el SG genera un backup nuevo. Ese backup se vuelve a
subir al bot para que la base de datos de la nube quede sincronizada. El
importador **deduplica automáticamente** por llaves naturales (animal + fecha +
tipo según la tabla), así que puede repetir este paso las veces que quiera sin
crear registros repetidos, y **nunca borra las notas capturadas por el bot**.

### Opción A — Desde el celular (zip de hasta 20 MB)

1. **Exporte el backup** en el SG y tenga el archivo `.zip` en el celular.
2. **Envíe el `.zip` al bot** por Telegram como documento (adjuntar archivo).
   El bot confirma la recepción:
   > 📦 Backup recibido (4.32 MB). Responde `/confirmar_importar` para procesarlo o `/descartar_backup` para eliminarlo.
3. **Confirme** con `/confirmar_importar` (o cancele con `/descartar_backup` si
   se arrepintió).
4. **Lea el reporte**: el bot responde con los registros nuevos y duplicados
   por tabla, por ejemplo:

   ```text
   📦 Reporte de Importación de Backup:
   • Total consolidado: 12 nuevos, 458 duplicados

   📋 Detalle por tabla:
   • animales: 2 nuevos, 310 duplicados
   • celos: 1 nuevos, 40 duplicados
   • partos: 3 nuevos, 55 duplicados
   • pesos: 4 nuevos, 30 duplicados
   • servicios: 2 nuevos, 23 duplicados
   ...
   ```

   Con que los "nuevos" coincidan con lo que usted cargó en el SG, la
   sincronización quedó lista. Los duplicados son los registros que ya estaban
   en la base y se saltaron.

> ⚠️ Telegram tiene un límite de **20 MB** por archivo. Si el zip pesa más, el
> bot lo rechaza y pide usar la Opción B.

### Opción B — Por SCP/SSH (zip mayor a 20 MB)

1. Desde **su computadora**, copie el zip al droplet:

   ```bash
   scp ruta/local/backup_sg.zip root@IP_DEL_DROPLET:/tmp/
   ```

2. En el **droplet**, ejecute el importador:

   ```bash
   cd /root/bitacora
   bash scripts/importar_backup.sh /tmp/backup_sg.zip
   ```

Al terminar verá `✅ Importación completada con éxito.` y la base
`data/bitacora.db` quedará sincronizada (misma deduplicación que por Telegram).

### Opción C — Auto-Import por Carpeta COPIAS (100% Automático)

Para no tener que entrar por SSH cada vez que genere un backup de 70 MB en Software Ganadero:

1. **En el VPS:** Puede activar el vigilante en segundo plano o agendarlo en `cron`:
   ```bash
   # Opción 1: Agendar sondeo en cron cada 5 minutos
   crontab -e
   # Agregar la línea:
   # */5 * * * * /root/bitacora/scripts/vigilar_copias.sh --once >> /root/bitacora/bot.log 2>&1

   # Opción 2: Ejecutar como demonio
   ./scripts/vigilar_copias.sh
   ```
2. **En su PC Windows (donde corre Software Ganadero):**
   Ejecute el script de sincronización automática en PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\vigilar_copias_windows.ps1 -CopiasDir "C:\Copias"
   ```
   Apenas SG genere una copia en `C:\Copias`, el script la transfiere por `scp`, la importa en el VPS y el bot le notifica por Telegram.

---

## 8. Actualizaciones del Código mediante Git (Deploy Key de Solo Lectura)

El droplet de producción está vinculado al repositorio GitHub oficial utilizando una **Deploy Key de solo lectura** (`vps-206.189.188.183-readonly`).

> 🛡️ **Principio de Menor Privilegio:** El VPS tiene permisos exclusivos para descargar (`git pull`), pero no puede escribir ni modificar ramas en GitHub. Si el servidor sufre un incidente, la seguridad del repositorio central permanece intacta.

### ¿Cómo actualizar el bot en el VPS tras un cambio en GitHub?
Para traer los últimos cambios y reiniciar el servicio, ejecute en el VPS:

```bash
cd /root/bitacora
git pull origin main
systemctl restart bitacora-bot
```

Para verificar que el bot arrancó correctamente:
```bash
systemctl status bitacora-bot
journalctl -u bitacora-bot -n 20 --no-pager
```

---

## ✅ Lista final de verificación

| Paso | ¿Listo? |
|------|:-------:|
| Droplet Ubuntu 22.04 creado ($6/mes) | ☐ |
| SSH funciona (`ssh root@IP`) | ☐ |
| Proyecto copiado en `/root/bitacora` | ☐ |
| `bash scripts/setup_vps.sh` terminó en verde | ☐ |
| Bot creado con @BotFather y token en `.env` | ☐ |
| `users.json` sembrado con el OWNER | ☐ |
| Backup SG importado (opcional) | ☐ |
| Bot responde `/start` en Telegram | ☐ |
| Servicio `bitacora-bot` activo y autoarranca | ☐ |
| `crontab -l` muestra el backup diario | ☐ |
| Snapshots activados (recomendado) | ☐ |

---

## 🆘 Problemas frecuentes

| Problema | Causa probable | Solución |
|----------|----------------|----------|
| El bot responde `⛔ No autorizado.` | Su `user_id` no está en `users.json` | Ver paso 5: obtenga su `user_id` y agréguelo como OWNER |
| El bot no responde nada | Token vacío o erróneo en `.env` | Revise `TELEGRAM_TOKEN` en `.env` y reinicie el servicio |
| `TELEGRAM_TOKEN no configurado` | `.env` sin editar | Copió `.env.example` pero no pegó el token (paso 4) |
| No encuentra la base de datos | Aún no se importó/creó | Ejecute una vez el importador (paso 6) o arranque el bot para que cree `data/` |
| El backup no aparece | Cron no agendado o `data/` vacío | Revise `crontab -l` y que exista `data/bitacora.db` |

Para más detalle del día a día del bot, vea
[`TELEGRAM_GUIA_USUARIO.md`](./TELEGRAM_GUIA_USUARIO.md).

---

## 9. Bot de pruebas (staging)

Existe un segundo checkout completo en `/root/bitacora-staging`, corriendo como
el servicio `bitacora-bot-staging`, con su **propio bot de Telegram**
(`@pruebasgan_bot`) y su **propia base de datos** (copia congelada, no la de
producción). Sirve para probar cambios de código con datos realistas antes de
que le lleguen a los trabajadores de verdad.

```bash
# Desplegar la rama main (o la que se indique) en staging:
ssh root@206.189.188.183 'bash /root/bitacora-staging/scripts/desplegar_staging.sh'
ssh root@206.189.188.183 'bash /root/bitacora-staging/scripts/desplegar_staging.sh mi-rama-de-prueba'
```

El bot de producción (`bitacora-bot`, `/root/bitacora`) nunca se toca al
desplegar en staging — son procesos, servicios y bases de datos totalmente
separados.
