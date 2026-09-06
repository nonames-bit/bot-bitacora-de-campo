# 📖 Guía Explicativa del Sistema de Bitácora Ganadera — Para el Dueño

**Fecha:** 2026-09-06

Esta guía explica, en palabras sencillas y sin tecnicismos, cómo funciona todo el sistema de la finca: el bot de Telegram, la aplicación web (PWA), el satélite, la base de datos y cómo se actualiza. Está pensada para el dueño de la finca que quiere entender y tomar decisiones, no para programadores.

---

## 1. 📱 ¿Qué es una PWA?

**PWA significa "aplicación web instalable".** Piense en ella como una página de internet que se comporta como una aplicación de celular: se abre en el navegador, pero usted puede ponerle un icono en el inicio del teléfono y usarla como si fuera una app normal, sin ir a la tienda de aplicaciones.

En este proyecto, la PWA es el **tablero web de la finca** (el código vive en `src/pwa/`). Se entra desde:

- `https://ganaderiaja.duckdns.org`

¿Qué encuentra ahí? **10 vistas** (10 pantallas):

| # | Vista | ¿Para qué sirve? (en palabras simples) |
|---|-------|----------------------------------------|
| 1 | Tablero | Resumen general de la finca del día |
| 2 | Agenda | Recordatorios y tareas programadas |
| 3 | Inventario SG | Cuántos animales hay, igual que en Software Ganadero |
| 4 | Población | Pirámide de edades del hato |
| 5 | Genética | Razas y cruces del hato |
| 6 | Reproducción | Preñeces, partos próximos, ecografías, palpaciones |
| 7 | Sanidad | Tratamientos y animales en retiro de leche/carne |
| 8 | Pasturas | Estado de cada potrero (ocupado, en descanso, listo) |
| 9 | Leche | Producción del tanque y por vaca |
| 10 | Ficha QR | Ficha de cada animal con su código QR (`/ficha/<tag>`) |

Analogía: si Telegram es el **radio del mayordomo** (mensajes rápidos desde el potrero), la PWA es el **escritorio del dueño** (todo ordenado en pantalla grande para analizar y decidir).

Tres cosas especiales de esta PWA:

- **Funciona sin internet en el campo.** Gracias a dos piezas llamadas Service Worker + IndexedDB (ver glosario), guarda una copia de lectura y una cola de escritura: usted anota aunque no haya señal y todo se sincroniza cuando vuelve la señal (`POST /api/sync`).
- **Modo "Manga de Corral".** Pantalla pensada para el corral: pesaje continuo animal tras animal con la ganancia diaria (GMD) calculada al instante, tratamientos en lote por potrero, y conexión por Bluetooth a básculas y bastones de lectura (RFID).
- **GPS para rondas y auditoría.** Detecta en qué potrero está usted parado (usa los mapas reales de la finca), registra visitas a saladeros, bebederos y cercas, y permite exportar el recorrido a CSV. Hay un modo silencioso de telemetría (solo visible para el OWNER) que guarda la ruta de trabajo.
- **Entrada con PIN y roles.** Cada persona entra con su PIN de 4 dígitos. Según su rol ve más o menos (ver sección 4). Además tiene el tema **"Sol de Campo"**: blanco y negro de alto contraste para leer bajo el sol fuerte del potrero.

---

## 2. 🛰️ ¿Qué es el NDVI?

**NDVI = qué tan verde y forrajera está la pastura, visto desde el satélite.** Es como un "termómetro del pasto": un número entre **-1 y +1**. Cerca de +1 = pasto verde y abundante. Cerca de 0 o negativo = suelo pelado, agua o pasto seco.

| Valor NDVI | Lectura para el dueño |
|---|---|
| 0.6 a 0.9 | Potrero verde, con buena biomasa |
| 0.3 a 0.6 | Potrero regular, vigilar rotación |
| Menos de 0.3 | Potrero pobre o en descanso necesario |
| Negativo | Agua, nube o suelo sin pasto |

¿Cómo lo obtiene la finca?

- Fuente real: satélite **Sentinel-2** consultado por **Google Earth Engine**. El código está en `src/gis/earth_engine_ndvi.py`.
- Se calcula **sobre el mapa real de cada potrero** (el campo `potreros.geom_wkt_4326`: el dibujo exacto del potrero en coordenadas GPS, cargado desde el proyecto QGIS de la finca con los 20 potreros).
- El sistema filtra las nubes píxel por píxel sobre cada potrero (más confiable que el dato general de nubosidad, porque en el trópico un potrero pequeño puede estar despejado aunque el resto de la imagen esté nublada).

¿Para qué le sirve a usted?

- **Estimar comida disponible:** convierte el NDVI en biomasa (kg de pasto verde por m² y kg de materia seca por hectárea).
- **Ajustar cuántos animales mete por potrero:** capacidad de carga animal (cuántas UGG aguanta el potrero).
- **Verlo en el celular:** comandos `/ndvi`, `/satelite`, `/indice_verde` y botón `[ 🛰️ Satélite NDVI ]`.

Dos aclaraciones honestas:

- Si un potrero **no tiene imagen despejada reciente** (muchas nubes o sin mapa cargado), el sistema no inventa: usa una **estimación de respaldo** por días de ocupación y descanso (leyes de Voisin) hasta que llegue la próxima imagen real.
- También existe **lluvia satelital CHIRPS** (`src/gis/earth_engine_lluvia.py`) como **referencia** a nivel de toda la finca. No reemplaza su pluviómetro físico: la resolución del satélite (~5.5 km) no distingue el microclima de cada sector.

El NDVI real se actualiza con el job semanal `scripts/actualizar_ndvi_satelital.py` (lunes 6:00 AM por cron). La lluvia satelital con `scripts/actualizar_lluvia_satelital.py` (lunes 6:05 AM).

---

## 3. 🗄️ ¿SQLite es suficiente o hace falta otra base de datos?

**Respuesta corta: sí, SQLite es suficiente y es lo correcto para esta finca.**

Piense en SQLite como un **cuaderno grueso y ordenado en un solo archivo** (`data/bitacora.db`). No necesita un servidor aparte de base de datos: todo vive en ese archivo dentro del VPS.

| Punto que se evaluó | Situación de este proyecto | Conclusión |
|---|---|---|
| Volumen | ~338 animales activos, miles de eventos históricos | Muy liviano para SQLite |
| Escritores al tiempo | 1 escritor principal (el bot) + pocos usuarios consultando | Sin problema |
| Concurrencia | Resuelta con modo WAL + `busy_timeout` + locks (permite leer mientras se escribe) | No se bloquea |
| Hosting | Un solo VPS (`206.189.188.183`) | No se necesita base distribuida |
| Portabilidad y respaldo | Un solo archivo `.db` que se copia entero cada día a `backups/` (retención 30 días) | Respaldo simple y confiable |
| Costo y mantenimiento | Cero licencias, cero servidor extra | Ideal para una finca |

¿Cuándo **sí** habría que cambiar a PostgreSQL (una base grande de servidor)?

- Si fueran **muchas fincas al tiempo** en el mismo sistema.
- Si hubiera **muchos escritores escribiendo a la vez** (decenas de personas guardando al mismo segundo).
- Si se necesitara **mapas avanzados tipo PostGIS** (análisis geoespacial pesado).

Nada de eso aplica hoy. Para una sola finca, SQLite es más barato, más simple y más fácil de respaldar.

---

## 4. 📷 ¿Cómo se guardan las fotos y los usuarios?

### Las fotos: el archivo en disco + la ficha en la base

Analogía: la foto es como un **toro en el corral** (pesa y ocupa espacio) y la base de datos es la **tarjeta del toro** (papelito con sus datos y dónde está). No se mete el toro dentro del papelito.

- **Archivo real:** carpeta `media/` (fotos `a001.jpg`, `v047.jpg`, `ja26.jpg`, etc.).
- **Ficha en SQLite, tabla `fotos`:** `animal_id`, `tag`, `fecha`, `ruta` (dónde está el archivo), `caption`, `user_id`, `notas`, `ocr_text` (lo que leyó el lector de aretes).
- **El binario NO va dentro de la base.** La base solo guarda la referencia (la ruta).

Flujo real:

1. El trabajador manda la foto por Telegram.
2. El bot la descarga a `media/`.
3. El lector OCR lee el número del arete en la foto.
4. La foto queda vinculada al animal y aparece en su ficha y galería (`/fotos <tag>`).

### Los usuarios: un archivo JSON con roles

Viven en `src/server/users.json` (este archivo **no** se sube a GitHub, solo existe en cada máquina). Cada persona tiene:

- `user_id` (número de Telegram), `telegram_id`, `nombre`, `rol`, `pin`, `avatar`.

| Rol | Nivel | ¿Qué puede hacer? |
|---|---|---|
| OWNER | Nivel 1 (dueño) | Todo, incluyendo agregar/quitar usuarios y ver el servidor |
| ADMIN | Nivel 2 (administrador) | Gestión zootécnica, reportes, potreros, alertas |
| TRABAJADOR | Nivel 3 (campo) | Anotar eventos, mandar voz/foto, consultar fichas |

¿Cómo entra cada uno?

- **Telegram:** el sistema reconoce el `user_id` de Telegram automáticamente y aplica el rol (RBAC = permisos por rol).
- **PWA web:** se entra con el **PIN de 4 dígitos** personal.

---

## 5. 🤖 ¿El bot de la PWA es el mismo de Telegram?

**No. Son dos procesos independientes que comparten la misma base de datos.** Como dos llaves que abren la misma bodega: cada una entra por su puerta, pero lo que guardan queda en el mismo lugar (SQLite en modo WAL, que permite leer y escribir al tiempo sin dañarse).

```
                 ┌──────────────────────────┐
                 │   SQLite data/bitacora.db │
                 │   (modo WAL, compartida)  │
                 └────────────┬─────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
 ┌────────────▼───────────┐      ┌────────────▼───────────┐
 │ TELEGRAM               │      │ PWA WEB                │
 │ python -m src.main     │      │ python -m src.pwa.app  │
 │   --server             │      │ Flask + waitress :8080 │
 │ long-polling, sin      │      │ nginx 443 → 127.0.0.1  │
 │ puerto abierto         │      │ https://ganaderiaja.   │
 │                        │      │   duckdns.org          │
 └────────────────────────┘      └────────────────────────┘
   Mismo users.json                Mismo users.json
   Misma Database                  Misma Database
   (src/db/database.py)            (src/db/database.py)
   Mismas funciones de             Mismas funciones de
   src/engine/dashboard_data.py    src/engine/dashboard_data.py
   (fuente única de datos)         (fuente única de datos)
```

| Capacidad | Solo Telegram | Solo PWA | Ambos |
|---|---|---|---|
| Notas de texto / voz / foto | | | ✅ |
| Preguntas en lenguaje natural (Q&A) | | | ✅ |
| Lector OCR de aretes y remedios | | | ✅ |
| Gráficos y reportes PDF | | | ✅ |
| Despacho matutino automático 5:30 AM | ✅ | | |
| Importar / exportar backups de SG | ✅ | | |
| Comandos `/reporte`, `/ndvi`, `/clima`, gestión de usuarios por comando | ✅ | | |
| Tablero visual con 10 vistas | | ✅ | |
| Funciona sin internet (offline real) | | ✅ | |
| Manga de corral (pesaje continuo + Bluetooth) | | ✅ | |
| GPS / geolocalización de rondas | | ✅ | |
| Gestión de usuarios por pantalla visual, ficha QR, autocompletar | | ✅ | |

En resumen: **Telegram es para el campo rápido, la PWA es para la oficina y el análisis.** Los dos leen y escriben en el mismo cuaderno.

---

## 6. 🏗️ Arquitectura completa del sistema

Piense en el sistema como una **finca con portería, bodega, oficinas y caminos**. Cada nivel tiene su trabajo.

**(a) Entradas (las porterías).** Por aquí llega todo: Telegram, PWA web, comandos de consola (CLI), el vigilante automático de copias SG (`src/watchers/copias_watcher.py`), y los trabajos programados (despacho 5:30 AM, backups, NDVI semanal).

**(b) Base de datos SQLite (la bodega central).** Un solo archivo con 28 tablas, en modo WAL. Grupos:

- Animales e inventario; eventos reproductivos (partos, celos, servicios/IA, diagnósticos de gestación); sanidad (tratamientos, retiros); manejo (traslados, entradas/salidas, muertes); pasturas (potreros, ocupación/reposo, aforos); leche (producción total e individual); criogenia (pajuelas, termo de nitrógeno); clima y satélite (pluviometría, NDVI, lluvia satelital); fotos; alertas y recordatorios; GPS y presencia; auditoría e importaciones.

**(c) Capa de acceso `Database` (`src/db/database.py`).** Es la **única puerta** para guardar. Métodos `registrar_*` idempotentes (si llega dos veces la misma nota, no duplica), y `resolve_animal` que entiende que "47", "N-069", "JA26" o "patricia" pueden ser el mismo animal (búsqueda flexible/fuzzy).

**(d) Motores (`src/engine/`).** Las **oficinas técnicas**: consultas en lenguaje natural (`query_engine`), reproducción (FEP = fecha estimada de parto +283 días, eco día 35, palpación día 60, secado FEP − 60 días), sanidad (tiempos de retiro), pasturas (rotación Voisin y capacidad de carga), crecimiento (GMD = ganancia diaria de peso), gráficos (`charts`), y `dashboard_data.py` como **fuente única** que usan igual Telegram y PWA (para que los dos muestren lo mismo).

**(e) Entendimiento de lenguaje (NLU híbrido, `src/parsers/` + `src/llm/`).** Dos capas: **Capa 1** rápida con reglas (regex, menos de 1 milisegundo) para lo común ("parió la 47"); **Capa 2** con inteligencia artificial (Gemini) multi-agente en paralelo cuando la nota es compleja o toca varios temas. Tiene un clasificador (router) de 3 dominios (reproducción / sanidad / manejo) y una lista blanca que rechaza eventos inventados (protección anti prompt injection).

**(f) Modelos de IA (`src/llm/`).** Conectores: `gemini_client` (HTTP puro), `nvidia_client` y `generic_client` (compatible OpenAI). El dueño solo necesita saber: si hay internet y clave válida, el bot entiende notas difíciles; si no, sigue funcionando con las reglas locales.

**(g) Lectura de fotos y documentos (`src/ocr/` + `src/vision/`).** `OCREngine` con varios motores (pytesseract/easyocr), `arete_detector` que limpia la foto (CLAHE) y corrige confusiones típicas (`O`↔`0`, `I`↔`1`, `G`↔`6`, `S`↔`5`, `B`↔`8`), y `factura_parser` que lee facturas de pajuelas para proponer cargar stock.

**(h) Importadores/exportadores DBF (puente con Software Ganadero).** Leen los backups `.Zip` de SG sin programas externos, deduplican por llaves naturales (animal + fecha + tipo) y protegen contra archivos trampa (Zip Slip / zip-bomb). Exportan de vuelta a DBF/CSV/JSON.

**(i) Servidor Telegram (`src/server/`).** `telegram_bot.py` (más de 40 comandos y botones), `auth.py` (permisos por rol), `formatters.py` (textos bonitos para celular), `keyboards.py` (botones táctiles).

**(j) PWA (`src/pwa/`).** Plantillas (`templates/`: `index.html`, `login.html`, `ficha.html`) y estáticos (`static/`: `app.js`, `sw.js`, `offline.html`, `manifest.json`). Instalable, offline y con PIN.

**(k) Satélite (`src/gis/`).** `earth_engine_ndvi` (NDVI real), `earth_engine_lluvia` (CHIRPS), `sentinel_ndvi` (fórmulas de biomasa y respaldo heurístico).

**(l) Reportes (`src/reports/`).** `pdf_report.py` (reporte institucional GANADERÍA JA) y `qr_fichas.py` (ficha A4 con QR a la ficha web).

**(m) Despliegue.** Servicios systemd `bitacora-bot` y `bitacora-pwa`, nginx como portero con TLS, y tareas cron (backup, healthcheck, NDVI, despacho).

Flujo de un mensaje, paso a paso:

```
Usted / mayordomo escribe o habla
        │
        ▼
Parser entiende (Capa 1 reglas → Capa 2 IA si hace falta)
        │
        ├─→ ¿Es REGISTRO? (parto, celo, tratamiento…)
        │       → Database.registrar_* → dispara alertas
        │         (FEP, eco, palpación, secado, retiro, Voisin)
        │
        └─→ ¿Es CONSULTA? (¿cuándo parió la 47?)
                → query_engine consulta SQLite → respuesta en español
                        │
                        ▼
                Telegram o PWA le responde
```

Tres reglas de oro del sistema:

- **Idempotencia:** repetir lo mismo no duplica (importar dos veces el mismo backup no crea gemelos).
- **Degradación elegante:** si falta algo (sin internet, sin OCR, sin imagen satelital), el sistema sigue con lo local y avisa, no se cae.
- **Inventario siempre filtra `estado = 'ACTIVO'`:** los conteos del hato actual nunca mezclan animales muertos, vendidos o históricos. Lo histórico solo se mira en fichas puntuales (genealogía, partos pasados).

---

## 7. 💻 Commit, push a GitHub y despliegue local → VPS

Analogía: su PC es la **mesa de trabajo**, GitHub es la **bodega central de planos**, y el VPS es la **finca en producción**. Usted dibuja en la mesa, guarda el plano en la bodega, y luego la finca descarga el plano nuevo.

Datos reales (verificados en el repo):

- Remoto: `https://github.com/nonames-bit/bot-bitacora-de-campo.git`, rama `main`.
- VPS: `206.189.188.183`, proyecto en `/root/bitacora`, staging en `/root/bitacora-staging`.

### Paso 1 — Guardar y subir desde su PC (Windows)

```bash
git add .
git commit -m "describe el cambio en presente: add ..., fix ..."
git push origin main
```

### Paso 2 — Llevarlo al VPS (dos opciones)

Opción A — manual (paso por paso):

```bash
ssh root@206.189.188.183
cd /root/bitacora
git pull origin main
systemctl restart bitacora-bot bitacora-pwa
```

Opción B — con script (recomendada, hace todo solo: descarga, instala, prueba y reinicia):

```bash
ssh root@206.189.188.183 'bash /root/bitacora/scripts/desplegar.sh'
```

Lo que hace `scripts/desplegar.sh`: `fetch + reset --hard origin/main` + `pip install -r requirements.txt` + `pytest` + `restart bitacora-bot bitacora-pwa`.

### Por qué la llave del VPS es de solo lectura

El VPS usa una **deploy key de SOLO LECTURA**: puede descargar (`git pull`) pero **nunca** subir (`git push`). Es por seguridad (principio de menor privilegio): si alguien entrara al servidor, no podría borrar ni alterar los planos en GitHub.

### Staging: la finca de pruebas

Existe una copia completa para ensayar sin tocar lo real: `/root/bitacora-staging` con el bot `@pruebasgan_bot` y el servicio `bitacora-bot-staging`.

```bash
ssh root@206.189.188.183 'bash /root/bitacora-staging/scripts/desplegar_staging.sh'
ssh root@206.189.188.183 'bash /root/bitacora-staging/scripts/desplegar_staging.sh mi-rama-de-prueba'
```

### Secretos: lo que NUNCA se sube a GitHub

`.env` (tokens), `src/server/users.json` (personas y PINes) y `data/` (la base real) están en `.gitignore`. Los secretos solo viven en el `.env` del VPS. La clave de Earth Engine tampoco va a git: se sube por `scp` a `/root/secrets/ndvi-key.json`.

El ciclo completo:

```
┌──────────┐   push    ┌──────────┐   pull    ┌───────────┐
│  SU PC   │ ────────▶ │  GitHub  │ ────────▶ │ VPS       │
│ edita,   │  origin   │ main     │ fetch +   │ /root/    │
│ commit   │  main     │ bodega   │ reset     │ bitacora  │
└──────────┘           └──────────┘           │ restart   │
                                              └───────────┘
```

### Operación diaria y semanal (mantenimiento)

| Tarea | Cuándo | ¿Qué hace? | Comando / lugar |
|---|---|---|---|
| Respaldo diario | Cron 3:00 AM | Copia `data/bitacora.db` a `backups/AAAA-MM-DD.db`, borra mayores de 30 días | `scripts/backup_diario.sh` |
| Vigilante de salud | Cron cada 15 min | Revisa servicio, disco y frescura de la base; avisa al OWNER por Telegram | `scripts/healthcheck_vps.sh` |
| Despacho matutino | 5:30 AM | Envía resumen del día (ordeño, celos AM-PM, eco/palpación, recordatorios) | `scripts/enviar_despacho.py` |
| NDVI satelital | Lunes 6:00 AM | Actualiza verdor real por potrero (Sentinel-2) | `scripts/actualizar_ndvi_satelital.py` |
| Lluvia satelital | Lunes 6:05 AM | Actualiza lluvia de referencia CHIRPS | `scripts/actualizar_lluvia_satelital.py` |
| Importar backup SG grande | Cuando SG genera copia | Importa `.Zip` de 70 MB+ sin pasar por Telegram | `bash scripts/importar_backup.sh /tmp/archivo.Zip` |
| Vigilar carpeta COPIAS | Cada 5 min o continuo | Detecta copias nuevas en `data/copias` e importa solo | `scripts/vigilar_copias.sh --once` |
| Instalación inicial VPS | Una vez | Prepara Ubuntu, Python, carpetas, `.env`, cron | `scripts/setup_vps.sh` |

---

## 8. 📚 Glosario breve

| Término | Qué es (1-2 líneas) |
|---|---|
| SQLite | Base de datos en un solo archivo, sin servidor aparte. Ideal para una finca. |
| WAL | Modo que deja leer y escribir al tiempo sin bloquearse. Como dos puertas en la bodega. |
| PWA | Página web instalable que funciona como app y trabaja sin internet. |
| Service Worker | Ayudante del navegador que guarda copias para usar sin señal. |
| IndexedDB | Cajón del navegador donde la PWA guarda notas pendientes hasta sincronizar. |
| NDVI | Número -1 a +1 que mide qué tan verde está el pasto visto del satélite. |
| Sentinel-2 | Satélites europeos que toman fotos de la tierra cada ~5 días. |
| CHIRPS | Dato satelital de lluvia de referencia (no reemplaza el pluviómetro). |
| VPS | Computador alquilado en la nube, prendido 24 horas. |
| Droplet | Nombre que DigitalOcean le da a cada VPS. |
| SSH | Forma segura de entrar al VPS por comandos desde su PC. |
| Deploy key | Llave del VPS para descargar código de GitHub (aquí: solo lectura). |
| systemd | Encargado en Ubuntu de mantener los servicios prendidos y reiniciarlos (`bitacora-bot`, `bitacora-pwa`). |
| cron | Reloj automático que ejecuta tareas (backup 3 AM, NDVI lunes 6 AM). |
| Polling | El bot preguntando a Telegram "¿hay mensajes nuevos?" cada momento (long-polling). |
| RBAC | Permisos por rol: OWNER / ADMIN / TRABAJADOR ven y hacen distinto. |
| OCR | Lector que saca texto de fotos (lee el número del arete o el frasco del remedio). |
| Whisper | Inteligencia que convierte notas de voz en texto en español. |
| LLM | Modelo grande de IA (Gemini) que entiende lenguaje difícil. |
| NLU | Parte que entiende lo que usted escribe ("parió la 47" → evento de parto). |
| Regex | Reglas rápidas de texto para lo común (menos de 1 milisegundo). |
| DBF | Formato viejo de tablas de Software Ganadero que el sistema sabe leer y escribir. |
| GMD | Ganancia media diaria de peso (gramos por día que engorda el animal). |
| FEP | Fecha estimada de parto (servicio + 283 días). |
| UGG | Unidad de ganado grande (~450 kg): medida para calcular cuántos animales aguanta un potrero. |
| Potrero | Lote de pasto cercado donde pastorea un grupo. |
| geom_wkt_4326 | Dibujo GPS exacto del potrero guardado como texto de coordenadas. |
| waitress | Servidor serio para la PWA en producción (multi-hilo, estable). |
| nginx | Portero del VPS: recibe internet y lo pasa a la PWA interna. |
| Proxy reverso | Eso que hace nginx: usted habla con nginx y él habla con la app escondida. |
| TLS / certbot | Candado HTTPS (certificado gratis de Let's Encrypt que se renueva solo). |
| Staging | Copia de pruebas (`/root/bitacora-staging` + `@pruebasgan_bot`) para ensayar sin riesgo. |

---

## 9. 📝 Historial de actualizaciones de esta guía

Esta guía es un documento vivo que se actualiza conforme el proyecto avanza. Cuando se complete una fase del roadmap, se agregue una función, se cambie una ruta, IP, dominio o comando de despliegue, o el dueño pida aclarar un concepto, esta guía se edita para reflejarlo.

> Nota: la guía vive en `docs/GUIA_EXPLICATIVA_PARA_EL_DUENO.md` y también queda versionada en git (cada edición queda en el historial del repositorio con su commit descriptivo).

| Fecha | Versión | Cambio realizado |
|---|---|---|
| 2026-09-06 | v1.0 | Creación inicial de la guía con 8 secciones (PWA, NDVI, SQLite/fotos/usuarios, Telegram vs PWA, arquitectura completa, despliegue local→GitHub→VPS, glosario). |
