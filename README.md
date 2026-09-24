# 🚀 Bot de Bitácora de Campo Ganadero

> **Dominio:** [FINCA] Finca y Gestión Agropecuaria > Gestión Integral (todos los módulos de Finca)  
> **Fecha de Creación:** 2026-08-24  
> **Ubicación:** `C:\Users\Owner\Documents\projects\finca\2026-08-24-bot-bitacora-de-campo`

---

## 🎯 Objetivo del Proyecto

Bot de bitácora de campo que recibe **notas de voz, fotos y texto** del mayordomo o
personal de campo para registrar **8 eventos zootécnicos** y responder consultas en
lenguaje natural desde la base de datos. Integra automatizaciones de **calendario
reproductivo**, **sanidad**, **pasturas** y **trazabilidad** genética y de pesos.

El mayordomo envía una nota simple ("parió la 47, ternero macho") y el bot la
interpreta, la persiste en SQLite y dispara automáticamente las alertas y
programaciones derivadas (FEP, ecografías, palpaciones, secado, retiros, rotación).

---

## 🐄 Eventos Zootécnicos Soportados (8)

| # | Evento | Campos | Automatización disparada |
|---|--------|--------|---------------------------|
| 1 | **Parto** | vaca, sexo de la cría, vivo/muerto, peso al nacer | Días abiertos, FEP, ecografía (día 35), palpación (día 60), secado |
| 2 | **Muerte** | animal, causa presunta | Baja del animal y registro del evento |
| 3 | **Servicio / Inseminación Artificial** | vaca, toro/pajuela, fecha, inseminador | FEP (+283 días), ecografía (+35 días), palpación (+60 días), secado (FEP − 60 días) |
| 4 | **Celo observado** | vaca, regla AM-PM | Alerta de Inseminación Programada (AM→tarde, PM→mañana siguiente) |
| 5 | **Tratamiento** | animal, producto, dosis, vía | Cálculo del tiempo de retiro en leche y carne |
| 6 | **Traslado de potrero** | lote/animal, origen, destino | Rotación Voisin (ocupación / reposo) |
| 7 | **Pesaje** | animal, kg | Ganancia Media Diaria (GMD) y peso ajustado a 205 días |
| 8 | **Entrada / Salida** | compra, venta, traslado | Alta/baja del animal en el inventario |

---

## 💬 Motor de Consultas (Q&A)

El bot responde preguntas en lenguaje natural consultando la base de datos, entre ellas:

- «¿cuándo parió la 47?»
- «¿qué vacas debo inseminar?»
- «¿qué animales están en retiro?»
- «¿qué vacas tienen palpación pendiente?»
- «¿qué potreros están listos?»
- «¿qué vacas están en el potrero olegario 1?» (búsqueda de animales por potrero, soporta `olegario 1 = OLEGARIO I` y `patricia → JA26`)
- «¿cuál es el historial de la vaca 47?» (historial de animales, también por nombre `patricia`)
- «¿cuánto pesó la 12 y cuál fue su ganancia diaria?»
- «¿cuándo le toca el secado a la 47?»
- «¿cuánto ganado hay en la finca?» / «total ganado» / «inventario total» (conteo activo con desglose vacas/toros/terneros, tolera typo `gaando`)
- «¿cuántas vacas/terneros/novillas hay?» (conteos por categoría)
- «¿inventario por potrero?» (lista cada potrero con su total)

---

## 📦 Importador de Backup Histórico

Soporte nativo para importar backups de **Software Ganadero TP/SG** ubicados en
`docs/Datos20260823.Zip` (zip externo con `Dbf.zip` interno). El parser lee las
tablas DBF sin dependencias externas:

`hoja`, `partos`, `celos`, `iamn`, `pesos`, `potrero`, `traslado`, `causas`

Cada tabla siembra su correspondiente dominio en SQLite (animales, muertes, partos,
celos, servicios/IA, pesajes con GMD, potreros con leyes de Voisin, traslados y
causas de baja).

---

## 📡 Fase 1 — Bot de Telegram (NUEVA)

### ¿Qué es?

Los trabajadores envían **notas de campo por Telegram** (texto, voz o foto) y el
dueño consulta el estado de la finca **desde el celular**, sin estar en el campo.
El bot autentica a cada usuario por su `user_id` de Telegram y aplica permisos
según su rol (RBAC). Todo lo que no esté expresamente listado aquí **no** está
implementado todavía.

### Roles y comandos permitidos

| Comando / Acción | 👑 OWNER | 🛠️ ADMIN | 📋 TRABAJADOR |
|------------------|:--------:|:---------:|:--------------:|
| `/menu` / `/start` (Panel táctil limpio) | ✅ | ✅ | ✅ |
| `/despacho` / `/matutino` / `/hoy` | ✅ | ✅ | ✅ |
| `/leche <litros>` (total hato en tanque) | ✅ | ✅ | ✅ |
| `/programar <fecha> <hora> <msg>` | ✅ | ✅ | ✅ |
| `/ayuda` / `/help` / `/comandos` | ✅ | ✅ | ✅ |
| Texto libre (8 eventos) | ✅ | ✅ | ✅ |
| Nota de voz (Whisper) | ✅ | ✅ | ✅ |
| Foto (OCR arete y medicamentos) | ✅ | ✅ | ✅ |
| `/historial <tag>` / `/consulta <tag>` | ✅ | ✅ | ✅ |
| `/fotos` / `/foto <tag>` | ✅ | ✅ | ✅ |
| `/aqui` / botón 📍 (GPS: detecta el potrero donde estás) | ✅ | ✅ | ✅ |
| `/graficos` (4 categorías zootécnicas) | ✅ | ✅ | — |
| `/potreros` / `/potreros sg` | ✅ | ✅ | — |
| `/ocupacion` / `/rotacion` (Voisin) | ✅ | ✅ | — |
| `/alertas` | ✅ | ✅ | — |
| `/animales` | ✅ | ✅ | — |
| `/status` | ✅ | ✅ | — |
| `/duplicados` | ✅ | ✅ | — |
| `/usuarios` | ✅ | ✅ | — |
| `/reporte` [diario\|semanal\|N] | ✅ | ✅ | — |
| `/exportar` (solo OWNER: entrega la base completa y avisa a los demás OWNER) | ✅ | — | — |
| `/importar` (guía) | ✅ | ✅ | — |
| Enviar archivo `.zip` como documento | ✅ | ✅ | — |
| `/confirmar_importar` | ✅ | ✅ | — |
| `/descartar_backup` | ✅ | ✅ | — |
| `/agregar_usuario` | ✅ | — | — |
| `/quitar_usuario` | ✅ | — | — |
| `/renombrar_animal` [tag_viejo] [tag_nuevo] [--fusionar] | ✅ | — | — |
| `/logs` | ✅ | — | — |

### Comandos principales

- **Todos los roles:** `/menu` y `/start` (tablero visual corto y táctil diferenciado por rol), `/despacho` / `/matutino` / `/hoy` (resumen matutino de 05:30 AM con alertas de ordeño, celos AM-PM, recordatorios y repro), `/leche <litros>` (registro rápido de producción total de leche del hato en tanque), `/programar <fecha> <hora> <msg>` (agenda recordatorios para el despacho), `/ayuda` (listado exhaustivo de comandos), **texto libre**
  con los 8 eventos zootécnicos, **nota de voz** (transcripción automática con Whisper
  y ejecución del evento o consulta), `/consulta <tag>` / `/historial <tag>` (ficha zootécnica
  completa del animal con entrega automática de fotografía y curva láctea/peso), **foto** (con detección OCR de tag y medicamento en frasco;
  se guardan en `media/` y en la base SQLite) y `/fotos [tag]` para
  consultar imágenes de los animales, y `/aqui` / botón `📍 GPS` (comparte tu ubicación y el bot detecta en qué potrero estás y guarda la ronda, visible en la auditoría del dueño).
- **OWNER y ADMIN:** `/graficos` (panel interactivo de gráficos en 4 categorías: Hato, Reproducción, Pasturas y Leche con vista detalle simplificada), `/potreros` y `/potreros sg` (matriz exacta de existencias por potrero de Software Ganadero),
  `/ocupacion` / `/rotacion` (días de pastoreo y descanso Voisin con semáforo), `/alertas`,
  `/animales`, `/status`, `/usuarios`, `/reporte [diario|semanal|N]` (genera y envía el reporte PDF institucional con logo `GANADERÍA JA`),
  `/importar` (guía de importación), enviar el `.zip` del backup directamente como
  documento por el chat, `/confirmar_importar` (procesa el backup pendiente) y
  `/descartar_backup` (elimina el backup pendiente sin procesar).
  Límite de Telegram: **20 MB**; archivos más pesados se suben por SSH y se importan
  con `scripts/importar_backup.sh` (ver [`docs/DESPLIEGUE_DIGITALOCEAN.md`](docs/DESPLIEGUE_DIGITALOCEAN.md)).
- **Solo OWNER:** `/exportar` (genera y envía el archivo ZIP con las 8 tablas DBF para Software Ganadero; cada exportación avisa a los demás OWNER), `/agregar_usuario <user_id> <ROL> [nombre]`,
  `/quitar_usuario <user_id>`, `/renombrar_animal <tag_viejo> <tag_nuevo> [--fusionar]` (rectificación de chapetas mal leídas con fusión atómica de eventos) y `/logs`.

### Setup rápido (local)

```bash
# 1. Crear el archivo de entorno y pegar el token de @BotFather
cp .env.example .env        # editar TELEGRAM_TOKEN

# 2. Sembrar los usuarios autorizados (editar el user_id del OWNER; luego se pueden agregar trabajadores vía Telegram con /agregar_usuario, ver docs/TELEGRAM_GUIA_USUARIO.md)
cp src/server/users.example.json src/server/users.json

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Arrancar el bot en modo servidor
python -m src.main --server
```

> 📖 Guías detalladas: [`docs/DESPLIEGUE_DIGITALOCEAN.md`](docs/DESPLIEGUE_DIGITALOCEAN.md)
> (despliegue paso a paso en VPS), [`docs/TELEGRAM_GUIA_USUARIO.md`](docs/TELEGRAM_GUIA_USUARIO.md)
> (manual para el personal de campo) y
> [`docs/GUIA_EXPLICATIVA_PARA_EL_DUENO.md`](docs/GUIA_EXPLICATIVA_PARA_EL_DUENO.md)
> (explicación en lenguaje sencillo de todo el sistema: PWA, NDVI, SQLite, arquitectura y despliegue).

---

## 🔄 Fase 1.1 — Sincronización de backups

Ciclo recurrente de sincronización entre el campo y el Software Ganadero SG:

1. Los **trabajadores** envían notas de campo al bot (texto, voz o foto).
2. Las notas quedan en la **nube** (SQLite del VPS) y el dueño las consulta como **reporte**.
3. El dueño hace la **carga manual al SG** de los eventos nuevos.
4. El SG genera un **backup nuevo** (zip con las tablas DBF).
5. El backup se **sube al bot** por Telegram (o SSH si pesa más de 20 MB).
6. El importador hace la **deduplicación automática** y responde con el reporte
   de registros nuevos y duplicados.

La importación es idempotente: la deduplicación usa **llaves naturales por
tabla** (animal + fecha + tipo según el caso, ej. `vaca_id + fecha + tipo_servicio`
en servicios, `animal_id + fecha + peso_kg` en pesajes), por lo que re-importar
el mismo backup varias veces no crea registros repetidos. **Nunca borra las
notas capturadas por el bot**: solo agrega lo que falta.

Flujo por Telegram (OWNER/ADMIN):

| Paso | Acción | Respuesta del bot |
|------|--------|-------------------|
| 1 | Enviar el `.zip` como documento por el chat (máx. 20 MB) | `📦 Backup recibido (X MB). Responde /confirmar_importar...` |
| 2a | `/confirmar_importar` | Reporte con nuevos/duplicados por tabla |
| 2b | `/descartar_backup` | `🗑️ Backup descartado y archivo eliminado.` |

> ⚠️ Si el zip supera los **20 MB** (límite de Telegram), el bot lo rechaza con
> instrucciones para subirlo por SSH e importarlo con `scripts/importar_backup.sh`
> (ver [`docs/DESPLIEGUE_DIGITALOCEAN.md`](docs/DESPLIEGUE_DIGITALOCEAN.md)).

### 📂 Sincronización automática por carpeta COPIAS (Backups de 70 MB)

Cuando los backups de Software Ganadero (SG) superan el límite de 20 MB de Telegram (frecuente por la inclusión de fotografías y tablas históricas pesadas de 70+ MB), la sincronización se realiza **100% en segundo plano** mediante observadores automáticos:

1. **Opción VPS (`src/watchers/copias_watcher.py` y `scripts/vigilar_copias.sh`):**
   - Monitorea la carpeta `COPIAS_DIR` (por defecto `/root/bitacora/data/copias` o `data/copias`).
   - Usa la biblioteca `watchdog` si está disponible, o realiza sondeos (polling cada 60s o tarea cron cada 5 min).
   - Detecta archivos `.Zip` ordenados por fecha de modificación (`mtime`), verifica integridad y calcula firma MD5.
   - Compara con el registro persistente `data/copias/.ultimo_importado` para evitar reprocesar archivos ya conocidos.
   - Ejecuta `import_zip` de forma idempotente, registra la actividad en `data/copias_import.log` y notifica al `OWNER` por Telegram vía Bot API.

2. **Opción PC Windows SG (`scripts/vigilar_copias_windows.ps1`):**
   - Monitorea la carpeta local de backups de SG (por defecto `C:\Copias`).
   - Al detectar un nuevo `.Zip` generado por fecha, lo transfiere automáticamente por `scp` al droplet VPS (`206.189.188.183:/tmp/`).
   - Dispara la ejecución remota de `bash scripts/importar_backup.sh` vía SSH sin intervención manual.

```bash
# Iniciar vigilante en VPS (modo demonio continuo o polling):
./scripts/vigilar_copias.sh

# Ejecutar una sola pasada (ej. para cron cada 5 minutos):
./scripts/vigilar_copias.sh --once

# En Windows PowerShell (PC con Software Ganadero):
powershell -ExecutionPolicy Bypass -File .\scripts\vigilar_copias_windows.ps1 -CopiasDir "C:\Copias"
```

---

## 🛠️ Stack Tecnológico y Skills Integradas

- **Lenguaje / Runtime:** Python 3.10+
- **Base de Datos:** SQLite
- **Pruebas:** suite de Pytest en verde — el conteo exacto lo publica el CI (no se hardcodea aquí)
- **Skills integradas:**
  - `@inseminacion-calc` — cálculos reproductivos (FEP, días abiertos, IEP)
  - `@plan-sanitario` — calendarios de vacunación, tratamientos y tiempos de retiro
  - `@trazabilidad-ganadera` — árboles genealógicos, consanguinidad, pesajes y GMD
  - `@aforo-pasturas` — aforo, capacidad de carga y rotación Voisin

---

## 🚀 Modo de Uso y Comandos

```bash
# 1. CLI interactivo del bot (notas de voz, fotos y texto)
python src/main.py

# 2. Bot de Telegram en modo servidor (Fase 1)
python -m src.main --server

# 3. Importación del backup histórico (Software Ganadero TP/SG)
python -m src.importers.dbf_importer
#    Equivalente con la ruta explícita del Zip:
python src/main.py --importar docs/Datos20260823.Zip

# 4. Exportación de SQLite a paquete ZIP para Software Ganadero (Fase 2)
python src/main.py --exportar
#    O con ruta personalizada:
python src/main.py --exportar data/exports/MiBackup.Zip

# 5. Ejecución de la suite de pruebas
pytest
```

El CLI también admite flags de una sola ejecución: `--texto "..."`, `--audio ruta.mp3`
y `--imagen ruta.jpg`, además de `--db` para elegir la base SQLite destino.

---

## 📍 Estado Actual

### ✅ Completado
- [x] Modelos y base SQLite (`src/db/`): animales, partos, celos, servicios, tratamientos, pesajes, potreros, traslados, alertas y fotos
- [x] Motores (`src/engine/`): reproductivo, sanitario, pasturas, crecimiento y consultas (Q&A con soporte de fotos)
- [x] Parser NLU de 8 eventos + manejador multimodal de voz/foto/texto (`src/parsers/`)
- [x] Importador DBF nativo de backups TP/SG (`src/importers/`)
- [x] Interfaz del bot (CLI interactivo y flags) (`src/bot/`)
- [x] **Fase 1 — Bot de Telegram multiusuario** (`src/server/`): RBAC (OWNER/ADMIN/TRABAJADOR), scripts de despliegue VPS (`scripts/`) y backup diario automático
- [x] **Fase 1.1 — Sincronización de backups**: importador DBF deduplicado (llaves naturales animal+fecha+tipo) y flujo `/importar` por Telegram en dos pasos (`/confirmar_importar` / `/descartar_backup`)
- [x] **Fase 2 — Reportes PDF, Fotos y Exportador DBF**:
  - [x] Reportes en PDF (`src/reports/`): comando `/reporte` con resúmenes diarios, semanales o personalizados, tablas zootécnicas y alertas
  - [x] Gestión de fotos vinculadas a animales: almacenamiento en `media/`, registro en SQLite, detección en captions y comando `/fotos [tag]`
  - [x] Extracción e importación idempotente de `Fotos.Zip` desde backups de Software Ganadero (`src/importers/dbf_importer.py`)
  - [x] Exportador DBF nativo (`src/exporters/`): serializador `DBFWriter` para las 8 tablas y exportación de paquetes ZIP vía `/exportar` y CLI `--exportar`
  - [x] Exportadores adicionales CSV y JSON vía `/exportar csv` y `/exportar json`
- [x] **Optimización UI Móvil y Motor de Consultas**:
  - [x] Ficha zootécnica (`_historial`) reformateada para lectura rápida en móvil con etiquetas HTML `<b>`, saltos dobles y estructura por dominios.
  - [x] Inventario por potrero deduplicado y agrupado por nombre normalizado, vista compacta de potreros ocupados en bloque `<pre>` con números alineados en formato `es-CO` y filtro para vacíos.
- [x] **Fase 3 (Parte 1) — Notas de Voz con Whisper**:
  - [x] Integración de Whisper local (`faster-whisper` / `openai-whisper`) para transcripción de audio en español (`es`)
  - [x] Procesamiento automático en tiempo real de notas de voz en Telegram y CLI con ejecución de eventos y respuestas
  - [x] Resolución flexible de tags alfanuméricos (`N069`, `N-069`, `N 069`) y permisos ampliados para `/consulta`
- [x] **Fase 3 (Parte 2) — OCR para Fotos**:
  - [x] Motor extensible `OCREngine` (`src/ocr/`) con backend liviano `pytesseract` / `Pillow` y fallback graceful (no-op / sidecars)
  - [x] Detección robusta de aretes/tags alfanuméricos (`N069`, `N-069`, `JA26`, `O-123`, `47`, `patricia`)
  - [x] Detección de frascos y fármacos veterinarios (oxitetraciclina, ivermectina, penicilina, dosis `ml/kg`, vías `IM/SC/IV`, lote y tiempos de retiro)
  - [x] Integración en el flujo de Telegram y Bot con concatenación NLU y feedback contextual (`🔍 OCR detectó tag`, `💊 OCR detectó medicamento`)
  - [x] Persistencia de `ocr_text` en SQLite tabla `fotos` con migración idempotente
- [x] **Fase 3 (Parte 3) — UI Interactiva, Consultas Naturales Específicas y Fotos Automáticas**:
  - [x] Motor de consultas ampliadas por tag o nombre propio (`patricia`, `JA26`, `47`):
    - *Ubicación*: `¿en qué potrero está patricia?`, `¿dónde está la vaca 47?` (retorna potrero actual, lote, fecha de ingreso y estado).
    - *Parto puntual*: `¿cuándo parió patricia?` (retorna fecha exacta, cría, sexo, peso al nacer y días abiertos).
    - *Servicio / IA*: `¿cuándo se inseminó patricia?` (retorna toro/pajuela, tipo de servicio, días de gestación y FEP).
    - *Sanidad y Retiro*: `¿patricia está en retiro?` (retorna productos aplicados, vías, fechas de fin y días restantes de carencia).
    - *Genealogía*: `¿quién es la madre de patricia?`, `¿qué crías tiene?` (retorna madre, padre y lista de partos).
  - [x] Despliegue automático de fotos de animales: resolución automática en disco `media/` y SQLite de imágenes del backup (`a009.jpg`, `ja26.jpg`, `v047.jpg`, etc.) adjuntando la fotografía directamente con la ficha zootécnica.
  - [x] Teclados interactivos de Telegram (`InlineKeyboardMarkup`):
    - Menú interactivo en `/start` y `/help` con botones de acceso rápido (`📊 Inventario`, `⚠️ Alertas`, `🌿 Potreros`, `📋 Reporte PDF`, `📷 Fotos`, `💡 Ejemplos`, `⚙️ Estado`).
    - Submenú interactivo de ejemplos de notas de campo para trabajadores (Parto, Celo AM/PM, Servicio, Tratamiento, Pesaje, Traslado, etc.).
    - Botones táctiles contextuales al pie de cada animal (`⚖️ Pesajes`, `🧬 Reproducción`, `🌱 Potrero`, `💊 Retiro`, `📷 Ver Foto`, `📋 Ficha Completa`).
  - [x] Ejecución en paralelo (`ThreadPoolExecutor`) de los extractores cuando una nota toca varios dominios a la vez; agente clasificador LLM como respaldo cuando el router no reconoce ningún dominio.
  - [x] Configuración de variables de entorno `GEMINI_API_KEY` y `GEMINI_MODEL` en `.env`.
- [x] Documentación y diagramas en `docs/`: arquitectura general, flujo de sincronización SG y matriz de permisos (`docs/ARQUITECTURA_Y_FLUJOS.md`)
- [x] Corrección zootécnica de fichas (`_historial` y `database.py`): categorías etarias SG fieles (`CRÍA MACHO <8m`, `LEVANTE 8-18m`, `TORETE 18-30m`, `TORO >30m` / `CRÍA HEMBRA`, `NOVILLA LEVANTE 12-18m`, `NOVILLA VIENTRE ≥18m`, `VACA PARIDA ≤305d` vs `VACA SECA/ESCOTERA >305d`), aislamiento de partos/días abiertos exclusivamente para hembras, bloqueo de partos autorreferenciados (`vaca_id != id_cria`), inferencia de `madre_id`/`sexo_cria` y soporte de tags con `_`.
- [x] **Ficha con edad humana** (`formatear_edad_zootecnica`): `🎂 Edad: 7 años 3 meses (2.667 días)` / `8 meses (243 días)` / `12 días`, inferida desde `fecha_nacimiento` o `parto madre` (<450d), mostrada en header.
- [x] **`/status` depurado para GANADERIA-JA 01-JA**: solo `Activos: 338 (GANADERIA-JA 01-JA)` sin `Histórico`, `Potrero + reposo` filtra reposos absurdos `>365d` (JARA 3.232d → `Ninguno`), `Potrero + animales` usa último traslado + `estado='ACTIVO'`, `Actualizado` usa mtime del `data/bitacora.db` (fecha del último backup SG) con fallback a `MAX(partos.fecha)`.
- [x] **Resumen SG inventario por brackets** (replica foto SG 339): tabla `Hembras <1, 1-2, 2-4, 4-8, 8-10, >10` y `Machos <1, 1-2, >2, Reproductor` con `Nro` y `Distrib.%` + `Total 339`, solo `estado='ACTIVO'` (GANADERIA-JA 01-JA), potreros ocupados con `% del total`; igual que `/animales` y `/status`.
- [x] **Menús diferenciados y UX interactiva optimizada**:
  - Panel corto y táctil para `/start` y `/menu` (`crear_teclado_trabajador` y `crear_teclado_admin`), con submenú compacto de administración (`crear_teclado_sistema_menu`) y submenú unificado de ayuda y guías de campo (`crear_teclado_ayuda_menu`), eliminando redundancia en el menú principal.
  - Menú de campo 100% didáctico para trabajadores (`[ 📝 Cómo Anotar Reportes ]`, `[ 🔍 Cómo Hacer Preguntas ]`, `[ 📷 Fotos Aretes y Remedios ]`, `[ 🐮 Consultar un Animal ]`, `[ 🎤 Cómo Mandar Audios ]`).
  - Listado completo de comandos reservado para `/ayuda` y `/help`.
- [x] **Existencias por potrero fieles a Software Ganadero (SG)**:
  - Matriz zootécnica de 9 columnas (`CH`, `HL`, `NV`, `VP`, `VS`, `CM`, `ML`, `MC`, `RP`, `Tot`) réplica de `potreros.jpg`.
  - Integrada en el motor de consultas (`_inventario_potreros_sg`), comandos de Telegram y reportes en PDF.
- [x] **Días de ocupación y rotación Voisin**:
  - Cálculo de días de pastoreo activo y semáforo de pradera (1-3d óptimo, 4-6d rotación, ≥7d sobreocupación).
  - Estado de descanso de potreros en reposo con punto óptimo de recuperación forrajera (≥30 días).
  - Comando `/ocupacion` / `/rotacion` y consultas de tiempo de ocupación.
- [x] **Doble Tablero de Control Inteligente (Finca vs Sistema)**:
  - **Tablero Zootécnico de la Finca** (`/status`, `/finca`, `/tablero`, `/resumen` o botón `[ 🐮 Tablero de la Finca ]`):
    - Hato activo desglosado por sexo y categorías.
    - Novedades de la semana (últimos 7 días): partos (conteo por sexo), celos, inseminaciones, tratamientos médicos (y retiros activos), pesajes con GMD promedio, traslados y muertes.
    - Alertas zootécnicas próximas (7 días): ecografías (día 35), palpaciones (día 60), secados y retiros activos de leche/carne.
    - Pasturas y Voisin: potreros en pastoreo, listos para rotar (≥30d de reposo) y alertas de sobreocupación (>3d).
  - **Tablero Técnico del Servidor & Sistema** (`/sistema`, `/servidor`, `/vps` o botón `[ ⚙️ Servidor & Sistema ]`):
    - Métricas de infraestructura VPS (SO, RAM servidor, RAM proceso bot, espacio en disco SSD, versión Python, servicio systemd).
    - Base de datos SQLite (ruta, tamaño en MB, total de animales y eventos históricos, fecha de última sincronización).
    - Usuarios autorizados y distribución de roles (OWNER, ADMIN, TRABAJADOR).
    - Estado de IA y APIs integradas (Gemini 2.5 Flash, transcriptor Whisper, OCR Pytesseract).
- [x] **Gestión Integral de Fotografías & Auto-Vinculación**:
  - [x] Auto-vinculación de fotos históricas huérfanas mediante análisis de `caption`, `ocr_text` y nombre de archivo.
  - [x] Búsqueda extendida en `fotos_de` por `animal_id`, `tag` exacto/normalizado, mención en comentario, texto OCR y archivos locales.
  - [x] Envío interactivo de imágenes en Telegram tanto por comando `/fotos <tag>` como por botón de galería `[ 📷 Galería Fotos ]`.
- [x] **Paneles Táctiles Interactivos de Búsqueda Rápida, Medicamentos y Preguntas**:
  - [x] **Buscador Táctil Didáctico** (`[ 🔍 Buscar Animal / Ficha ]` o `/buscar`): botones dinámicos con los animales de actividad más reciente y filtros por categorías (`[ 🥛 Vacas Paridas ]`, `[ 🤰 Inseminadas ]`, `[ 🐂 Toros ]`, `[ 🍼 Crías ]`, `[ ⚖️ Pesajes ]`), con apertura de ficha y fotografía en 1 toque.
  - [x] **Panel Sanitario de Medicamentos & Retiros** (`[ 💊 Medicamentos & Retiro ]`, `/medicamentos`, `/retiros`): monitoreo en tiempo real de animales en retiro de leche y carne según días de carencia, lista de últimos tratamientos aplicados y accesos directos.
  - [x] **Consultas Rápidas de Campo en 1-Toque** (`[ ❓ Preguntas Rápidas ]`, `/preguntas`, `/faq`): respuestas instantáneas a preguntas recurrentes sobre ordeño/retiro, potreros listos y días abiertos.
- [x] **Rediseño Zootécnico Integral inspirado en GANADERO SG App**:
  - [x] **Fichas de Animales Interactivas con Pestañas Táctiles**:
    - `[ ⚖️ Pesajes & GMD ]`: Historial ponderal completo, Ganancia Media Diaria (GMD en g/día) y Ganancia de Vida (g/d/vida).
    - `[ 🍼 Partos & Crías ]`: Perfil reproductivo para hembras (partos, servicios, celos AM/PM, días abiertos, IEP, FEP) y toros (hijos nacidos, servicios).
    - `[ 🥛 Control Leche ]`: Estado de lactancia (en ordeño vs seca), DEL actuales, proyección de secado ($FEP - 60d$) y alertas a $\ge 200$ DEL.
    - `[ 💉 Sanidad & Retiro ]`: Semáforo con conteo regresivo de retiro de leche y carne + historial clínico de fármacos, dosis y vías.
    - `[ 🌳 Genealogía (3G) ]`: Árbol genealógico en 3 generaciones (padre, abuelos paternos, madre, abuelos maternos) y lista de crías descendientes.
    - `[ 📷 Ver Foto ]` y `[ 📋 Ficha Resumen ]`: Visualización rápida con navegación táctil fluida.
  - [x] **Centro de Alertas Semafórico de Campo** (`/alertas`):
    - 🔴 *Partos próximos* ($\le 30$ días) con fecha y conteo regresivo.
    - 🟡 *Vacas candidatas para secado* ($\ge 200$ DEL o $FEP \le 60$ días).
    - 🟢 *Crías en edad de destete* ($\ge 200$ días de edad).
    - ⚠️ *Pérdidas de peso en último control* (GMD $< 0$ g/día).
    - ⛔ *Retiros sanitarios activos* (bloqueo preventivo de leche y carne).
  - [x] **Tablero Poblacional & Pirámide de Edades SG** (`/poblacion`, `/piramide`):
    - Brackets etarios exactos de Software Ganadero para hembras y machos, edad promedio del hato e indicadores zootécnicos.
  - [x] **Composición Genética y Razas** (`/genetica`):
    - Distribución racial y cruces del hato (Holstein, Gyr, Cebú, Pardo Suizo, Ayrshire, etc.).
  - [x] **Estructuración Didáctica de Ayuda & Menús**:
    - Menús divididos en 3 bloques claros (Operación en Campo, Zootecnia & Informes SG, Sistema y Administración).
    - **Centro de Guía de Consultas & Chat** (`/guia`, `/preguntar`): Hub categorizado con ejemplos de preguntas sobre animales, potreros, leche/reproducción, sanidad y dictado por voz/fotos.
    - Guía de ayuda enriquecida con ejemplos de dictado por voz y notas de campo.
  - [x] **Despacho Matutino (05:30 AM), Control Lechero y Recordatorios**:
    - Generador del Despacho Matutino (`formatear_despacho_matutino`): reporte matutino con retiros sanitarios activos de ordeño, inseminaciones AM por regla AM-PM, recordatorios del día y calendario reproductivo (eco d35, palpación d60, partos 7d) con botones de acción rápida.
    - Registro de producción total del hato vía `/leche <litros>` (tabla `produccion_leche` con `animal_id` NULL) y control lechero individual.
    - Programación de recordatorios de campo vía `/programar YYYY-MM-DD HH:MM mensaje` y persistencia en tabla `recordatorios_programados`.
    - Gráficos zootécnicos organizados en 4 categorías (`/graficos`: Hato, Reproducción, Pasturas, Leche) y vista de detalle compacta con solo 2 botones de navegación.
    - Menú principal interactivo compactado con submenús unificados `[ 📦 Sistema & Reportes ]` y `[ ❓ Ayuda & Guías ]`.
  - [x] **Manual Integral de Uso y Operación** ([`docs/MANUAL_DE_USO.md`](docs/MANUAL_DE_USO.md)): Guía completa de extremo a extremo para el dueño, administradores y personal de corral.
- [x] **Auditoría Técnica y Hardening de Concurrencia & Robustez**:
  - [x] Modo WAL en SQLite (`PRAGMA journal_mode=WAL`), `PRAGMA busy_timeout=10000`, `foreign_keys=ON` y `check_same_thread=False` para evitar bloqueos por concurrencia entre Telegram, el vigilante de copias y respaldos.
  - [x] Creación de índices en `SCHEMA_SQL` (incluyendo `idx_recordatorios_fecha_estado`) para acelerar consultas de inventario, partos, servicios, pesajes y traslados.
  - [x] Escapado seguro de entidades HTML (`_esc`) y chunking automático de mensajes extensos (`_enviar_texto_seguro` en Telegram).
  - [x] Inclusión de `ffmpeg`, `sqlite3`, `tesseract-ocr` en `setup_vps.sh` y activación de `Pillow>=10.0.0` en `requirements.txt`.
  - [x] **Seguimiento auditoría 2026-08-30 (H-10..H-12 y recomendaciones)**: file-lock atómico (`threading.Lock` + `tempfile` + `os.replace`) en `auth.py`; backoff adaptativo por longitud de nota en la cascada LLM (`try_multiagent_parse` con `timeout=None`); validación Zip Slip + zip-bomb (`_validar_zip_seguro`, límite 1 GB total / 512 MB por entrada) en `dbf_importer.py`; `watchdog` documentado como extra opcional; test de concurrencia WAL (`tests/test_concurrencia_wal.py`); y lista blanca canónica de `tipo_evento` para la salida de la Capa 2 LLM con log de rechazos (`TIPOS_EVENTO_LLM_VALIDOS`).
  - [x] **Hardening WS-1 — 4 bugs críticos corregidos** (`tests/test_bugs_criticos.py`): `registrar_servicio` en `src/db/database.py` ya no traga fallo de `descontar_pajuela` (warning con detalle); `create_tables` con try/except individual + traceback (`vincular_fotos_huerfanas`, `marcar_historicos_sg`, autorreferencias); `import_fotos` en `src/importers/dbf_importer.py` retorna `{"error": ...}` en Zip corrupto/inseguro y no inserta fila fantasma; `copias_watcher.py` solo persiste estado sin errores y distingue "con errores" de "Exitoso"; `formatear_reporte_importacion` en `src/server/formatters.py` muestra errores por tabla.
- [x] Suite de pruebas con pytest en verde (conteo vigente en el CI)
- [x] **Árbol Genealógico & Trazabilidad 3G Completo en PWA y Bot (2026-09-06)**:
  - **PWA Ficha Técnica**: Incorporada la pestaña interactiva `[ 🌳 Genealogía (3G) ]` en la ficha de cada animal con diagrama de pedigree estructurado (padres, abuelos paternos y maternos, bisabuelos), semáforo zootécnico de consanguinidad parental en 3G, lista interactiva de crías/descendientes con navegación táctil fluida entre fichas y bloque de texto compartible para WhatsApp/Telegram. En la pestaña `General`, se integraron abuelos y crías directas con botón de salto al pedigree.
  - **Bot de Telegram**: Nuevos comandos `/arbol <tag>`, `/genealogia <tag>`, `/pedigree` y `/trazabilidad` con vista zootécnica completa (G1, G2, G3 bisabuelos, verificación de consanguinidad y crías registradas tanto para hembras como machos) y menú interactivo de selección rápida cuando no se indica tag.
  - **Motor de Consultas (QueryEngine)**: Reconocimiento del intent de árbol genealógico tanto con tag (*"árbol de A007"*, *"genealogía de JA238"*) como sin él (*"🌳 ÁRBOL GENEALÓGICO & TRAZABILIDAD (3G)"*, *"pedigree"*), respondiendo con la ficha genealógica detallada.
- [x] **Fase 7 PWA Etapa D enriquecida (5 workstreams, 2026-09-05)** — dashboard con 10 vistas (Tablero, Agenda, Inventario SG, Población, Genética, Reproducción, Sanidad, Pasturas, Leche, Ficha QR `/ficha/<tag>`); offline lite solo lectura (Service Worker `src/pwa/static/sw.js` + `/offline.html` + `/sw.js` + `manifest.json`); dark mode + KPIs/chips + ficha con 4 pestañas (General/Repro/Tratamientos/Pesos) + polling 60 s; fuente única de datos compartida con Telegram vía `src/engine/dashboard_data.py` (WS-2, sin duplicar SQL; ruff E9/F limpio; smoke PWA OK: login + 11 APIs + ficha + estáticos + logout). Ver `docs/PLAN_FASE7_PWA.md`.
- [x] **PWA X2 — Identificación por foto del arete y RFID**: `POST /api/identificar` (solo lectura; nunca escribe BD/media) acepta `texto` (arete/RFID/lector de corral) o `foto` (multipart) y reutiliza `src/vision/arete_detector.py` (+ OCR con degradación elegante si falta tesseract/easyocr); resolución exacto/normalizado, variantes con prefijos (A/N/V/JA + relleno de ceros, p. ej. RFID `...00047` → `A047`) y sugerencias difusas si no hay match; panel "Identificar / Ficha" carga ficha por foto del arete y muestra sugerencias táctiles
- [x] **PWA X4 — Leche por vaca y curvas en la ficha**: `/api/leche` devuelve `ranking_vacas` (top por litros acumulados, KPI "Mejor vaca" en vista Leche); ficha animal con secciones enriquecidas (partos, servicios, diagnosticos, lactancia con DEL y estado, controles de leche), pestaña nueva "🥛 Leche" y gráficos por animal vía `/api/ficha/<tag>/grafico/peso|lactancia` (whitelist + caché por animal, mismo patrón que `/api/grafico`)
- [x] **PWA X5 — Autocompletar y deep-link de potrero**: `GET /api/buscar?q=` (animales ACTIVOS y potreros) alimenta datalist en campos Tag/Potrero (debounce 250 ms); distribución por potrero del Tablero enlaza a `/?v=tablero&potrero=X` y la app respeta parámetros URL (`?v=`, `?potrero=`, `?tag=`) al cargar
- [x] **PWA X3 — Producción PWA**: arranque (`python -m src.pwa.app`) usa waitress (WSGI multi-hilo) si está instalado y solo cae al dev server de Flask con aviso si no; plantillas `scripts/bitacora-pwa.service` (systemd, PWA en 127.0.0.1:8080) y `scripts/nginx-bitacora.conf` (proxy reverso + TLS + `client_max_body_size 25m` + caché de estáticos con excepción para sw.js/manifest/offline); `requirements.txt` añade waitress; despliegue VPS en `docs/DESPLIEGUE_DIGITALOCEAN.md` (sección "Plantillas del repositorio")
- [x] **Catálogo de tipo de evento reproductivo (Parto/Gemelar/Aborto/Reabsorción/Momificación/Maceración/Muerte fetal), 2026-09-10** — columna `tipo_evento`/`grupo_parto_id` en `partos` (equivalente al combo "Tipo" de Software Ganadero): `registrar_parto()` acepta el nuevo tipo y agrupa gemelares por `grupo_parto_id`; import/export DBF hace round-trip vía prefijo `[TIPO]` en `DETALLE` (SG solo tiene el booleano `ABORTO`); selector de tipo + campos de "Cría 2" en el formulario de Captura Rápida de la PWA; prompt/schema del extractor Gemini y capa regex (`event_parser.py`) reconocen los 7 tipos por lenguaje natural; detección de mellizos en `detectar_duplicados_geneticos` migrada de regex sobre notas a `tipo_evento='GEMELAR'` estructurado.
- [x] **Incidente de producción y hardening de CI (noche del 2026-09-10)** — otra sesión de IA operando en paralelo sobre el mismo repo local pusheó directo a `main` (sin CI en verde, sin pre-push hook) una función `renderMercado()` pegada dos veces en `app.js` con la primera copia cortada a mitad de línea: sintaxis inválida en todo el archivo, la PWA quedó en blanco ("Cargando..." infinito) para todos los usuarios. Diagnosticado por SSH (logs de `bitacora-pwa`, `node --check`) y corregido. A raíz de esto:
  - CI (`.github/workflows/tests.yml`) llevaba **20 pushes seguidos en rojo** solo por deuda de lint de `ruff` (nunca llegaba a correr pytest) — se limpiaron los 48 errores, incluyendo 2 bugs reales (no solo estilo): `GeminiClient.transcribe_audio()` extraía el texto pero nunca lo retornaba (transcripción de voz rota en silencio) y `crear_bloque_kpis()` usaba `Sequence` sin importar.
  - Se agregó chequeo de sintaxis JS (`node --check` sobre `src/pwa/static/*.js`) al CI — la pieza que habría atajado el incidente.
  - Hook local `.githooks/pre-push` (activar una vez por clon con `git config core.hooksPath .githooks`): corta sintaxis JS/Python inválida antes de dejar pushear.
  - Branch protection real en `main` (bloquear push directo sin PR+CI verde) evaluado pero no disponible: GitHub lo requiere plan Pro en repos privados; queda pendiente si se actualiza el plan.
  - Droplet de producción redimensionado de 1 GB a 2 GB de RAM (quedaba con ~130 MB libres bajo carga normal).

### ⏳ En Progreso / Calibración Continua
- [x] **Header Móvil Compacto, Menú Desplegable al tocar el Logo y Auto-Ocultado de la Barra Inferior (2026-09-17)**:
  - **Ahorro de ~60px verticales en pantalla móvil**: El encabezado pasa de 2 filas a 1 sola fila fija de 48px sin desbordes ni wraps, dejando visibles inmediatamente los KPIs del hato (336 activos, 268 hembras, 64 machos, partos, etc.) y los botones de acción sin necesidad de scroll.
  - **Disparador táctil en el logo / marca (`#marca-header-btn`)**: Logo con micro-indicador de avisos pendientes (`#header-menu-dot` animado con pulso sutil si hay eventos offline en cola o alertas de agenda), nombre GANADERÍA JA, hora compacta y flecha indicadora accesible con tap y teclado.
  - **Menú Flotante / Bottom Sheet Glassmorphism (`#modal-menu-usuario`)**:
    - Perfil con avatar de usuario, nombre y badge de nivel de acceso (ej. `L1 · OWNER`).
    - Tarjeta interactiva de **Sincronización de Campo** (estado "Al día con el servidor" o "X pendientes" y botón para forzar sincronización de cola offline).
    - Botones de acceso rápido: **Avisos** (campana con contador), **Ayuda** (manuales y guías) e **Instalar App** (PWA).
    - **Selector Visual de Temas**: 4 opciones con previsualización táctil y cambio reactivo en tiempo real (*Verde Campestre*, *Sol de Campo*, *Claro Editorial*, *Modo Oscuro*).
    - Botón de **Cerrar Sesión** con limpieza de caché del Service Worker.
  - **Barra de Navegación Inferior con Auto-Ocultado Inteligente**: Al hacer scroll hacia abajo, la barra `#nav-principal` se desliza automáticamente fuera de pantalla y la burbuja de chat baja al borde inferior, maximizando el espacio de lectura. Al deslizar hacia arriba, al llegar al fondo o al tocar cerca de la base, la barra reaparece al instante con animaciones suaves.
  - **Eliminación de Redundancia del Botón Flotante (+)**: Ocultamiento de la torre flotante `.fab-stack-global` en móvil, eliminando la duplicidad con el botón Captura. En la barra inferior se resalta como `+ Captura` para registro rápido a un solo toque, y se integra búsqueda directa de aretes en el menú rápido del logo y en el Tablero.
  - **Verificación visual móvil (390×844 DPR=2)**: Probado y validado en navegador autónomo, cumpliendo con la regla de calidad de AGENTS.md y chequeo estricto de sintaxis `node --check` para JS.
- [x] **Mejoras UX PWA — Fecha en cabecera, hora en chat y listado interactivo de animales por potrero (2026-09-12)**:
  - **Fecha compacta en cabecera**: Indicador tipo pill con día de la semana, fecha y hora (`Sáb, 12 de sept · 11:55 p. m.`) en `#reloj-hora` para dashboard y ficha técnica, adaptado a viewport móvil sin desbordes.
  - **Hora en mensajes de chat (Asistente IA y Equipo)**: Inclusión de marca de tiempo (`chat-msg-hora`) en cada burbuja de mensaje (usuario, bot, notas de voz y chat de equipo).
  - **Listado interactivo de animales por potrero (Pasturas / Voisin)**:
    - Endpoint `@app.get("/api/potrero/<potrero_ref>/animales")` y función `animales_de_potrero()` con filtrado estricto `estado = 'ACTIVO'` (Regla Fundamental de Inventario).
    - Enlace táctil en nombres de potreros y botón `👥 Listar` en la tabla de rotación y ocupación.
    - Modal móvil optimizado (390×844 DPR=2) con resumen de categorías SG (`NV`, `VS`, `VP`, `CH`, `CM`, `HL`, `ML`, `MC`, `TR`), buscador en tiempo real y tabla con columnas: Número (con salto a ficha técnica), Nombre, Edad, Estado y Días en el potrero.
    - Formateo de hectáreas a 1 decimal (`10.0 ha`) y pruebas unitarias de API en verde.
- [x] **Fase 5.1 — Reproducción Completa & Termo Criogénico**: Evento palpación directo (Preñada/Vacía con días de gestación), tablas `diagnosticos_gestacion`, `pajuelas_inventario`, `termo_nitrogeno`, KPIs tasa de concepción y S/C, sincronización con ficha zootécnica (estado reproductivo y sección diagnósticos), limpieza de FEP en diagnósticos VACIA, descuento automático de pajuelas al inseminar, comandos `/pajuela_stock`, `/pajuela_add`, `/termo`, `/recarga_n2`, alerta automática de recarga N₂ (<=3d) integrada en Despacho Matutino y OCR de facturas de pajuelas (`src/ocr/factura_parser.py`) con propuesta y confirmación táctil de stock.
- [x] **Fase 6.2 — Capacidad de Carga Dinámica e Integración Pluviométrica & Balance Forrajero Estacional**:
  - Modelado zootécnico de Materia Seca (MS): demanda diaria al $2.8\%$ del Peso Vivo ($12.6\text{ kg MS/UGG/día}$).
  - Integración agroclimática IDEAM (referencia histórica mensual) y pluviometría de campo con factor de crecimiento $F_{\text{clima}}$ (30 días).
  - Lluvia satelital real de contraste (CHIRPS vía Google Earth Engine, Fase D del plan geoespacial) junto al registro manual en `/clima` — no reemplaza el pluviómetro físico.
  - Tablas SQLite `pluviometria`, `aforos_historico` y `monitoreo_satelital_lluvia` con auditoría y comando `/deshacer`.
  - Consultas en lenguaje natural de lluvias y balance forrajero; comandos `/clima`, `/lluvia <mm> [sector]` y `/balance_forrajero`.
- [x] **Fase 8.2 — OCR Arete Sucio/Botón & Monitoreo Satelital NDVI Sentinel-2 (real)**:
  - Visión artificial avanzada (`src/vision/arete_detector.py`): CLAHE, filtros bilaterales, clasificación (Paleta vs Botón) y corrección de ambigüedades OCR (`O`$\leftrightarrow$`0`, `I`$\leftrightarrow$`1`, `G`$\leftrightarrow$`6`, `S`$\leftrightarrow$`5`, `B`$\leftrightarrow$`8`).
  - Fórmulas NDVI, aforo satelital (kg MV/m²), biomasa (kg MS/ha) y ajuste dinámico de carga animal (`src/gis/sentinel_ndvi.py`).
  - **NDVI real vía Google Earth Engine** (`src/gis/earth_engine_ndvi.py`): consulta Sentinel-2 L2A (`COPERNICUS/S2_SR_HARMONIZED`) sobre el polígono real de cada potrero (`potreros.geom_wkt_4326`), con filtrado de nubes píxel a píxel (banda SCL) sobre el propio potrero — más confiable que el metadato de nubosidad de la escena completa para potreros pequeños en clima tropical. Job semanal `scripts/actualizar_ndvi_satelital.py` (ver `docs/DESPLIEGUE_DIGITALOCEAN.md`). Cuando un potrero aún no tiene lectura real (sin `geom_wkt_4326` o sin imagen despejada reciente), `/ndvi` cae a una estimación heurística de respaldo basada en días de ocupación/reposo — ver detalle en `docs/PLAN_GEO_SATELITAL_6.2_8.2.md`.
  - Tabla SQLite `monitoreo_satelital_ndvi`, comandos `/ndvi`, `/satelite`, `/indice_verde` y botón táctil `[ 🛰️ Satélite NDVI ]`.
- [x] **Fase 7 — PWA Oficina + Corral Offline (Completa 2026-09-05)**:
  - **Módulo de Indicadores Económicos, Subastas Ganaderas & Calculadora de Flete desde Mesetas (2026-09-09)**:
    - **Sección Especializada en PWA (`v=mercado`)**: Módulo de precios y subastas para toma de decisiones comerciales, con cotizaciones semanales de novillo gordo, levante, terneros destetos, hembras y vacas descarte en 8 plazas: Sugameta Granada (Ariari), Sugameta Guamal, Sugameta San Martín, Subagaucho Catama (Villavicencio), Suballanos (Puerto López), Subacasanare (Yopal), Frigorífico Guadalupe (Bogotá) y Promedio Nacional FEDEGÁN.
    - **Calculadora Interactiva de Rendimiento Neto & Fletes**: Simulación en tiempo real desde Mesetas, Meta que calcula mermas por transporte (desbaste según distancia y horas de viaje), flete por cabeza, comisión de subasta (2.5%), ingreso neto final en el bolsillo y precio neto por kg equivalente en la báscula de la finca, destacando automáticamente la plaza con mayor rentabilidad neta.
    - **Monitoreo del Litro de Leche & Poder Adquisitivo de Insumos**: Comparativa entre la liquidación real en la finca (extraída de Finanzas), quesera artesanal local, industria formal y precio mínimo de sustentación MinAgricultura (USP Región 2 Meta). Indicador de intercambio de insumos críticos en el Ariari (sal mineralizada 8% y 10%, bulto de urea, alambre de púas, TRM dólar) midiendo cuántos kilos de novillo en pie se necesitan para adquirir cada insumo.
    - **Fuentes Oficiales & Flexibilidad de Actualización**: Transparencia metodológica documentando las fuentes (FEDEGÁN, DANE SIPSA, Sugameta, MinAgricultura USP, Banco de la República), con modal de actualización de precios protegido para roles `ADMIN` y `OWNER` (oculto a `TRABAJADOR`).
    - **Aislamiento Estricto PWA**: Implementado exclusivamente en la aplicación web sin alterar comandos ni menús del bot de Telegram.
  - **Cola de Escritura Offline Real** con `IndexedDB` (`POST /api/sync`) y sincronización automática/manual.
  - **Modo "Manga de Corral"**: Pesaje continuo de animales con cálculo instantáneo de GMD (g/día) en pantalla, historial en vivo de pesajes, tratamientos masivos en lote por potrero, y conector Web Bluetooth (`navigator.bluetooth`) para básculas y bastones RFID BLE.
  - **Geolocalización GPS & Auditoría de Rondas**: Detección automática del potrero actual sobre polígonos WGS84 de la finca (`potreros.geom_wkt_4326`), registro georreferenciado de visitas a saladeros, bebederos, cercas y recorridos de inspección con exportación directa a CSV.
  - **Telemetría GPS Silenciosa en Segundo Plano & Auditoría de Rutas (Solo OWNER)**: Motor en segundo plano que registra coordenadas satelitales transparentemente sin alertar al operario (al abrir app, cambiar pestañas, guardar pesajes/capturas o por latido de 3 min), geocercado por potreros, soporte offline y panel exclusivo para OWNER con cronología de visitas, enlaces a Google Maps y exportación a CSV.
  - **Gestión Interactiva de Usuarios, Niveles (Level 1, 2, 3) & Avatares**: Módulo administrativo en PWA para ADMIN y OWNER (`/api/usuarios`) con jerarquía estricta por niveles (Level 1 OWNER, Level 2 ADMIN, Level 3 TRABAJADOR), IDs locales y de Telegram enlazados, selector de foto/avatar temático con estilo Ganadería JA, campo de nombre espacioso y PIN de 4 dígitos con validación de colisiones.
  - **Mejoras Visuales & UX Editorial**: Iconografía vectorial SVG Lucide (manga corral, celo, muerte, pajuelas francesas), logotipo oficial de Ganadería JA y soporte de `safe-area-inset-top` para pantallas móviles con notch.
  - **Autenticación por PIN & 3 Roles RBAC**: Login por PIN de 4 dígitos individual con permisos estrictos (`TRABAJADOR` para captura en campo, `ADMIN` para gestión zootécnica y reportes PDF/Excel, y `OWNER` con acceso exclusivo a panel de métricas VPS, SQLite WAL y visor de logs en vivo).
  - **Identidad Visual Oficial Ganadería JA & Desvinculación de SG**: Incorporación del medallón oficial de marca (`docs/GanaderiaJA_Logo.jpg`) en alta resolución en barra de navegación, pantalla de login, favicon y manifest PWA, con desvinculación total de referencias visibles a marcas comerciales externas ("Software Ganadero / SG") en el bot de Telegram, reportes PDF y fichas técnicas zootécnicas, preservando la compatibilidad técnica DBF de fondo.
  - **Monitor de Usuarios en Línea en Tiempo Real (Exclusivo OWNER)**: Sistema confidencial de presencia de usuarios (`usuarios_presencia`) con latido periódico cada 60s, detección de canales (PWA Web y Telegram Bot), indicación de última actividad y dirección IP, expuesto única y exclusivamente al rol OWNER con protección HTTP 403 a nivel de API.
  - **Inteligencia, Voz & Tablas de Inventario**: Asistente zootécnico en lenguaje natural (`QueryEngine`) integrado en la PWA con formateo enriquecido seguro, tablas de inventario en bloques monoespaciados (`<pre>`) con scroll táctil horizontal y botón de copiado al portapapeles (`📋 Copiar`), y dictado por voz directo (`MediaRecorder` + Whisper) para notas sin teclear.
  - **Tema "☀️ Sol de Campo"**: Modo de alto contraste en blanco y negro puro para legibilidad bajo sol directo en potrero.
  - **Ficha Zootécnica Ejecutiva & Tarjeta QR Completa A4**:
    - **Endpoint `/api/reporte.pdf` reparado**: integración completa de períodos (`semanal` -> 7d, `quincenal` -> 15d, `mensual` -> 30d) con generación robusta y descarga directa.
    - **Dashboard de Ficha Animal en PWA enriquecido**: 4 tarjetas KPI (Potrero Actual, Edad Zootécnica exacta, Último Peso/GMD, Estado de Retiro Sanitario), Identificación completa, Genealogía con enlaces interactivos a madre y padre, Estado reproductivo vivo (condición, FEP, días abiertos post-parto), alerta roja destacada de retiro sanitario con desglose de fármacos, y registro de movimientos recientes entre potreros.
    - **Ficha Técnica Zootécnica QR en PDF (A4 Landscape)**: Formato apaisado de alta densidad de datos generado con código QR vectorial ReportLab que enlaza directamente a la ficha web interactiva en vivo, incluyendo fotografía/placeholder oficial, cuadro genealógico, tabla de pesajes/GMD, historial reproductivo/partos y semáforo sanitario de inocuidad.
  - **Captura Fotográfica Opcional de Campo en Captura Rápida PWA**:
    - Botón de cámara táctil integrado en Captura Rápida (selector nativo de archivos, con opción de cámara **o** galería/archivos) con vista previa instantánea, miniatura, botón de descarte y textos contextuales según el evento.
    - **Estrictamente opcional**: los registros de partos (crías), aplicaciones de medicamentos/drogas, muertes/necropsia, traslados o pesajes se guardan normalmente con o sin foto adjunta.
    - **Compresión client-side con `<canvas>`**: reducción inteligente a máximo 1200px y calidad JPEG 0.82 (~140-200 KB) garantizando compatibilidad con la cola offline `outbox` en `IndexedDB` y subida ultrarrápida.
    - **Sincronización y persistencia dual**: procesamiento automático en `POST /api/sync`, guardado físico en `media/` y registro en tabla SQLite `fotos` con auto-vinculación cruzada en partos (tanto a la cría como a la madre) para consulta inmediata en la ficha del animal.
  - **Instalación Directa como App en Celular y PC (PWA Standalone) sobre HTTPS (`ganaderiaja.duckdns.org`)**:
    - **Instalación en 1 toque**: botón táctil `[ 📲 Instalar App ]` integrado en el encabezado y en la pantalla de inicio de sesión (`/login`), permitiendo agregar la app directamente a la pantalla de inicio del teléfono con el logo oficial de Ganadería JA.
    - **Experiencia Nativa Standalone**: apertura a pantalla completa sin barra de URL ni pestañas del navegador, persistencia de sesión y soporte offline integral con `ServiceWorker` (`pwa-ja-v34`).
    - **Diferenciación inteligente por plataforma**: disparo de diálogo oficial en Android (`beforeinstallprompt`) y PC Chrome/Edge; despliegue de guía modal ilustrada paso a paso en iPhone/iPad (Safari iOS: *Compartir ⎋* $\rightarrow$ *"Agregar a la pantalla de inicio ➕"*); y ocultación automática cuando la app ya corre instalada.
    - **Manifest PWA enriquecido**: `id`, `start_url` con tracking `?source=pwa`, orientación `portrait-primary`, colores institucionales e iconos adaptativos maskable.
  - **Centro de Ayuda PWA, Asistencia IA de Sistema y Nuevos SVGs Zootécnicos**:
    - **Pestaña de Ayuda (`<button data-v="ayuda">`)**: Centro de guías operativas en la navegación principal con tarjetas ilustradas sobre: 1) Cómo instalar la app (pestañas Android, iPhone/iPad y PC con botón de instalación directo), 2) Funcionamiento en potrero sin internet (cola local `IndexedDB` y sincronización automática), 3) Trabajo en manga y pesaje continuo (GMD en vivo, cursor ágil y tratamientos en lote), 4) Captura rápida con fotos ligeras, 5) Dictado por voz con Whisper, y 6) Asistente IA con preguntas frecuentes.
    - **Asistente IA con Soporte de la App**: `QueryEngine` entrenado para responder en lenguaje natural preguntas sobre el funcionamiento del sistema (`_ayuda_instalar_app`, `_ayuda_modo_offline`, `_ayuda_manga_pesaje`, `_ayuda_general_sistema`) con chips de sugerencias rápidas en el modal de chat.
  - **PWA OWNER — Panel de Sincronización SG & Bitácora de Actividad de Usuarios**:
    - **Monitoreo de Sincronización de Backups SG**: Tarjeta ejecutiva con el último archivo procesado (`Datos20260831.Zip`), fecha y tiempo relativo ("hace X días"), desglose de registros nuevos incorporados vs existentes verificados (idempotencia), semáforo de salud de sincronización e historial de backups anteriores (`import_sg_historial`).
    - **Bitácora de Auditoría de Actividad de Campo**: Registro cronológico de eventos ingresados por mayordomos, administradores y personal de corral (partos, pesajes con GMD, tratamientos sanitarios con retiros, traslados, celos, servicios), con avatar temático del responsable, canal de origen (PWA, Telegram o SG), fecha/hora exacta, enlace directo a ficha animal y filtros táctiles por grupo (`[ Todos ]`, `[ 🤠 Trabajadores ]`, `[ 🛡️ Administradores ]`, `[ 📁 Software Ganadero ]`).
    - **Preservación Robusta de Identidad**: Corrección en `auth.py` y `api_guardar_usuario` para evitar que la edición de perfiles o PINs en la PWA desvincule el `telegram_id` del bot.
  - **Feed de Eventos en Tablero Principal, Iconografía SVG y Navegación Táctil (2026-09-06)**:
    - **Registro Cronológico en Vivo**: Panel de últimos 25 eventos del hato (partos, muertes, ventas, traslados, pesajes con GMD, tratamientos y servicios/IA) en el Tablero principal.
    - **Navegación Táctica Inmediata**: Clic directo en cualquier arete o cría para saltar al instante a la ficha técnica del animal con scroll superior automático y delegación de eventos compatible con CSP.
    - **Iconografía Unificada SVG**: Reemplazo de emojis y dibujos antiguos por iconos vectoriales derivados 100% de la vaquita canónica (`COW_HEAD`): `CALF_HEAD` con frente redondeada tierna sin cuernos para crías y `PARTO_HEADS` con Vaca Madre + Cría juntas compartiendo el mismo diseño exacto.
    - **Botón de Ayuda en Encabezado**: Reubicación del centro de ayuda como icono `?` en el encabezado superior junto al asistente de chat, liberando espacio en la barra de navegación principal.
    - **Retiro de Columna Redundante**: Supresión de la columna "Acción" en la tabla de eventos para una visualización más limpia y espaciosa en teléfonos móviles.
  - **Ficha Animal Standalone (`/ficha/<tag>`) Unificada (2026-09-06)**:
    - **Selector de Temas Visuales Activo**: Dropdown con los 4 temas visuales (`Verde Campestre`, `Sol de Campo`, `Claro Editorial`, `Modo Oscuro`) sincronizado con `localStorage`.
    - **Iconografía SVG Canónica**: Sustitución del emoji residual `🐮` por el icono SVG Lucide de vaca (`COW_HEAD`) en la ruta de navegación.
    - **Herramientas de Encabezado**: Integración de Asistente IA (modal de chat zootécnico interactivo con sugerencias contextuales para el animal consultado) y botón de Ayuda con redirección a `/?v=ayuda`.
    - **Caché y Service Worker `v43`**: Actualización de versión para forzar la recarga limpia de assets en navegadores móviles y escritorio.
  - **Módulo de Leche: Recibos Quincenales & Planillas Manuales de Campo (2026-09-06)**:
    - **Captura Rápida Adaptada a la Realidad de Finca**: Ajuste del formulario de leche para recibir la foto del recibo de quincena o planilla manual en papel donde anotan los litros diarios, con título contextual `Foto del Recibo / Planilla de Leche`, botón `Tomar o Subir Recibo / Hoja`, y campo de litros adaptado a ordeño o consolidado de quincena.
    - **Galería de Recibos en Vista Leche con Zoom Lightbox**: Incorporación de sección visual con miniaturas de recibos y planillas subidas, permitiendo abrir cualquier hoja en pantalla completa con zoom táctil (1.5x) para verificar números y notas de campo.
    - **Caché y Service Worker `v44`**: Bump de versión para refresco inmediato de estilos y componentes.
  - **Digitalización Inteligente de Recibos y Planillas de Leche con IA Multimodal (2026-09-06)**:
    - **Parser Multimodal Especializado (`src/vision/recibo_leche_parser.py`)**: Motor de visión artificial que procesa fotos de recibos quincenales impresos o planillas manuscritas de campo usando Gemini Vision (`gemini-2.5-flash`) con fallback automático a NVIDIA NIM (`meta/llama-3.2-90b-vision-instruct`).
    - **Extracción de Tablas y Verificación de Sumas**: Detección inteligente del período, asignación de fechas ISO a cada renglón/día (1 al 15 o 16 al 31), litros diarios y detección de discrepancias entre la suma de las filas y el total liquidado en el papel.
    - **Endpoints PWA (`/api/leche/analizar-recibo` y `/api/leche/guardar-quincena`)**: Rutas REST para análisis multimodal, upsert masivo idempotente en `produccion_leche` y archivo de la foto del recibo en `media/` y la tabla `fotos`.
    - **Desglose Diario Interactivo en Captura Rápida**: Al subir una foto de recibo, aparece el botón `[ Leer Recibo con IA ]`, mostrando el progreso en vivo y una tabla interactiva donde el usuario puede verificar, editar o agregar días con suma recalculada en tiempo real antes de guardar todo en un solo clic.
    - **Atajo en Vista de Leche**: Botón `[ Digitalizar Recibo con IA ]` en la cabecera de Producción de Leche para iniciar de inmediato la captura y digitalización.
    - **Caché y Service Worker `v45`**: Actualización de versión para distribución instantánea en celulares y computadores.
  - **Visualización de Ventas y Vínculos Madre ⇄ Cría en Tablero (2026-09-07)**:
    - **Idempotencia y Backfill en Importador DBF (`src/importers/dbf_importer.py`)**: Eliminada la condición excluyente `estado_previo != "VENDIDO"`, verificando directamente contra `movimientos` para permitir que reimportaciones de backups históricos o archivos zip completen las ventas fechadas (`FECMUERTE`) en `movimientos` sin crear duplicados.
    - **Alimentador Cronológico de Eventos (`src/engine/dashboard_data.py`)**: Enriquecimiento de `query_eventos` en tablero para vincular bidireccionalmente ventas de vacas y sus crías vendidas en la misma fecha (ej. `V089` ⇄ `V089-6`, `A090` ⇄ `A090-6`, `A096` ⇄ `A096-6`), etiquetando `detalle_label` (`Madre`/`Cría`), generando descripciones zootécnicas claras (`Venta con cría`, `Venta (cría de ...)`) y ampliando el límite a 35 eventos recientes.
  - **Barra de Navegación Móvil Ergonómica & Menú "Más Módulos" Categorizado (2026-09-07)**:
    - **Fin del Scroll Horizontal Infinito**: Reorganización completa de la barra de navegación inferior fija en móviles (pantallas ≤ 640px) pasando de una fila de más de 13 botones desbordados a una cuadrícula simétrica fija de 5 botones: 4 accesos directos principales (`Tablero`, `Captura`, `Inventario`, `Finanzas`) + 1 botón táctil `[ ☰ Más ]`.
    - **Bottom Sheet Nativo Categorizado (`#modal-mas-modulos`)**: Al pulsar "Más", se despliega suavemente desde abajo una hoja modal nativa con todos los módulos de la finca ordenados por área zootécnica: 1) *Trabajo de Campo & Manga* (`Manga & Pesaje`, `Captura Rápida`, `Agenda & Avisos`, `GPS Rutas`), 2) *Zootecnia & Producción* (`Inventario Hato`, `Ficha Animal`, `Reproducción`, `Producción Leche`, `Sanidad Animal`, `Pasturas & Voisin`, `Genética & Pedigree`), y 3) *Gestión & Administración* (`Finanzas Finca`, `Usuarios & PIN`, `Servidor & Sistema`).
    - **Sincronización Bidireccional & Estado Activo Dinámico**: Al elegir un módulo secundario (ej. `Producción Leche`), el botón "Más" se resalta con el nombre de la vista activa (`Leche`), dando retroalimentación visual clara sin alterar el diseño compacto.
    - **Cumplimiento RBAC Estricto**: La visibilidad de módulos en la barra inferior y en la hoja "Más" se sincroniza rigurosamente con los permisos del usuario logueado (`TRABAJADOR` solo ve herramientas operativas autorizadas y sus categorías vacías se ocultan automáticamente; `ADMIN` y `OWNER` acceden a sus paneles respectivos).
    - **Badges y Alertas Integradas**: El botón "Más" muestra un indicador con el conteo acumulado si hay tareas o alertas pendientes en los módulos secundarios (Agenda, Reproducción o Sanidad).
    - **Caché y Service Worker `v51/v52`**: Actualización de versión de caché para entrega inmediata sin fricción en todos los navegadores móviles y desktop.
    - **Aislamiento Estricto de Navegación & Ficha Animal (v52)**: Corrección de solapamiento donde los estilos de la barra fija móvil afectaban a las pestañas internas de la ficha animal (`#ficha-tabs`) al usar el selector genérico `nav`. Se encapsuló la barra principal bajo `#nav-principal` y las pestañas de la ficha bajo `#ficha-tabs .mini`, restaurando la operatividad total de los botones inferiores (Tablero, Captura, Inventario, Finanzas, Más) al consultar cualquier ficha.
  - **Corrección Crítica: CSP Bloqueaba Silenciosamente los Clics Dinámicos de Toda la App (2026-09-06)**:
    - El CSP de producción (`script-src 'self'`, sin `unsafe-inline`) impedía que el navegador ejecutara **cualquier** atributo `onclick`/`onerror` inyectado dinámicamente vía `innerHTML` (árbol genealógico, crías, feed de eventos, exportar CSV, imágenes rotas), sin lanzar error visible — parecían simplemente "no hacer nada" al tocarlos.
    - Migrados los 14 sitios `onclick` y 4 `onerror` a un único listener delegado en `document` con atributos `data-ir-ficha` / `data-ir-tab` / `data-accion` / `data-onerror-hide`, el mismo patrón ya usado por los botones del menú principal (que sí funcionaban).
    - Corregido además un bug independiente en la página standalone `/ficha/<tag>`: el clic en una cría/animal traía los datos pero nunca los pintaba, porque apuntaba al contenedor `#vista` (solo existe en el dashboard SPA) en vez de `#ficha` (el real en esa página).
    - Quitados los 3 accesos redundantes al mismo pedigree en la tarjeta "Identificación & Genealogía" (botón chico "Ver Pedigree 3G" + botón grande "Abrir Árbol Genealógico"); la pestaña "Genealogía (3G)" ya visible arriba queda como único acceso.
    - El panel "Formato de Texto Compartible (Telegram/WhatsApp)" del árbol genealógico mostraba las etiquetas `<b>`/`<i>` (formato HTML que solo el Bot de Telegram interpreta vía `parse_mode="HTML"`) de forma literal al copiar y pegar a mano; ahora se convierten a `*negrita*`/`_cursiva_` estilo WhatsApp para ese panel específico.
  - **Importador DBF: Fecha Real de Ventas desde Software Ganadero (2026-09-06/07)**:
    - Descubierto que `FECMUERTE` en `hoja.dbf` es, pese al nombre, el campo genérico de "fecha de baja" que SG llena tanto para `TIPO='M'` (muerte) como `TIPO='V'` (venta) — confirmado contra un respaldo real cuyo informe de indicadores de ventas agrupa exactamente por esa fecha. El importador solo la leía para muertes, así que toda venta caía sin ningún evento fechado en `movimientos` (invisible para "Últimos Eventos" y reportes por periodo), aunque `animales.estado` sí quedara en `VENDIDO`.
    - Ahora usa esa fecha real (más `VALOR` como precio y `VENDIDOA` como destino) cuando SG la trae; si genuinamente no hay fecha, aproxima con la fecha de la importación y lo deja anotado como tal (mismo tratamiento para muertes sin `FECMUERTE`).
    - Eliminada la condición excluyente `estado_previo != "VENDIDO"` para que reimportar un backup ya procesado siga completando ventas que quedaron sin fecha antes del fix, sin duplicar.
  - **Módulo de Finanzas — Ingresos, Egresos y Utilidad (Fase 1, 2026-09-07)**:
    - Nueva pestaña **Finanzas** con libro unificado de ingresos/egresos (tabla `finanzas`: fecha, tipo, categoría, concepto, monto, litros, animal/potrero opcionales, foto de factura, notas) y categorías `VENTA_LECHE`, `NOMINA`, `INSUMO`, `VETERINARIO`, `INFRAESTRUCTURA`, `COMBUSTIBLE`, `OTRO_INGRESO`/`OTRO_EGRESO`.
    - La venta/compra de animales **no se duplica**: ya vive en `movimientos` con su `precio` y el resumen de utilidad la suma directamente desde ahí.
    - Resumen por año (selector) con KPIs de Ingresos/Egresos/Utilidad, desglose por categoría y tabla de movimientos recientes; captura de gasto/ingreso integrada al flujo offline-first de Captura Rápida (con foto de factura opcional, reutilizando la cola `IndexedDB` y compresión client-side existentes).
    - Cada movimiento tiene un botón "Ver" que abre un modal de detalle con toda la información y la foto adjunta (zoom táctil); el animal vinculado es clicable (icono SVG vaca, sin emoji) y navega a su ficha, cerrando el modal automáticamente.
  - **Corrección: Fotos Cruzadas entre Animales en la Ficha (2026-09-07)**: `fotos_de()` hacía un match difuso (`LIKE '%tag%'` sobre caption/OCR/nombre de archivo) incluso para fotos ya vinculadas a otro animal_id, así que la ficha de un padre/madre también mostraba la foto de su propia cría numerada (`JA14` calzaba como substring de `JA14-7`, mismo riesgo con `V089`/`V089-6`, `N069`/`N069-6`, etc.). El match difuso ahora solo aplica a fotos huérfanas (`animal_id IS NULL`), que es justamente el caso que ya cubre `vincular_fotos_huerfanas()`.
  - **Hardening de Seguridad — PIN, Cookies de Sesión e IP Falsificable (2026-09-07)**: siguiendo una revisión de seguridad, se corrigieron los 3 hallazgos críticos/altos: comparación del PIN con `hmac.compare_digest` en vez de `==` (evita ataque de temporización); cookie de sesión con `SESSION_COOKIE_SECURE=True` (solo HTTPS, con `PWA_COOKIE_SECURE=0` como escape hatch para dev local), `HTTPONLY` explícito y `SAMESITE=Lax`; y `ProxyFix` de Werkzeug (`x_for=1`) reemplazando la lectura manual de `X-Forwarded-For`, que confiaba en el primer valor del header (falsificable por el cliente) en vez del último salto real que agrega Nginx — eso permitía eludir el rate-limit de `/login` rotando un prefijo falso en cada intento.
  - **Selector de Fotos: Cámara o Galería (2026-09-07)**: quitado `capture="environment"` de los inputs de foto (factura/recibo y arete), que en Android forzaba la cámara directamente sin dar opción de elegir una imagen ya existente (ej. una foto recibida por WhatsApp).
  - **Información Explícita de Bajas por Venta y Muerte en Ficha Animal (2026-09-07)**:
    - **Header y Chip de Estado Fechado**: Si un animal está `VENDIDO` o `MUERTO`, el chip superior de estado ahora muestra la fecha exacta del evento (`VENDIDO · 05/09/2026`, `MUERTO · 07/05/2016`) junto a su icono SVG respectivo (`receipt`, `cowSkull`).
    - **Banners Destacados en Pestaña General**: Al inspeccionar un animal que causó baja, se despliega un banner de alto contraste al inicio de la ficha:
      - *Ventas*: Tarjeta ámbar con fecha de venta, comprador/destino, precio liquidado, observaciones y vínculos automáticos de venta conjunta (cría vendida al pie de su madre o madre vendida junto a sus crías en la misma fecha).
      - *Muertes*: Tarjeta roja con fecha del deceso, causa presunta, notas de necropsia y observaciones clínicas.
      - *Descartes*: Tarjeta descriptiva con motivo de baja.
    - **Historial Consolidado de Bajas y Movimientos**: Tabla estructurada que consolida todas las bajas (ventas, muertes, compras, traslados) con fecha, tipo, destino/causa, precio y observaciones.
    - **Ficha Técnica PDF (`/api/ficha/<tag>/qr.pdf`)**: El estado del hato en la ficha imprimible A4 refleja dinámicamente el estado real y fecha de baja (`VENDIDO (2026-09-05)`, `MUERTO (2016-05-07)`) en vez de asumir estáticamente "ACTIVO".
    - **Caché y Service Worker `v55`**: Incremento de versión para refresco instantáneo en celulares y navegadores.
  - **Rediseño Estético Unificado del Sistema PDF (2026-09-07)**:
    - **Nuevo módulo `src/reports/estilo_ja.py`**: fuente única de identidad visual JA (constantes de color institucional, estilos de párrafo, `TableStyle` base/alertas/potreros/header-verde, helpers de canvas `dibujar_encabezado`/`dibujar_pie`/`dibujar_seccion_hdr`, y flowables platypus `EncabezadoFlowable`/`SeccionFlowable`/`PieFlowable`), eliminando la duplicación de `_COLOR_MARCA` que había en `pdf_report.py` y `qr_fichas.py`.
    - **Reporte general de la finca (`/reporte`, `/api/reporte.pdf`) alineado con la ficha**: encabezado con franja verde sólida `#2F5233` + logo, secciones con banda `#E7EFE8`, tablas con header verde y texto blanco + zebra, alertas destacadas con fondo/acento de retiro (rojo suave) y pie de página con línea separadora corporativa. Se conservan las firmas públicas (`generar_pdf`, `recolectar_datos`).
    - **Tarjetas QR en lote (6/hoja) refinadas**: marcos `roundRect` con radio, QR con contenedor blanco/borde sutil y truncado elegante de textos, mismos constantes que la ficha individual.
  - **Rediseño Estético y Ejecutivo de Reportes PDF y Tarjetas QR (2026-09-07)**:
    - **Sistema de Diseño Unificado (`src/reports/estilo_ja.py`)**: Tokens de color premium institucional (`#1B4D3E`, `#12352B`, `#D5E2D7`, `#D4AF37`), medalla circular con aro dorado decorativo (`dibujar_logo_circular`), bloques KPI ejecutivos (`crear_bloque_kpis`), tablas modernas con franja de acento y zebra (`tabla_style_moderna`), y cabeceras/pies de página limpios.
    - **Reporte General de Campo (`src/reports/pdf_report.py`)**:
      - Corrección de doble cabecera en página 1 y eliminación total de solapamientos en páginas 2+ (`topMargin = 26 mm`).
      - Bloque ejecutivo de 4 tarjetas KPI para resumen de inventario (Hato Activo, Hembras %, Machos %, Histórico total).
      - Tabla de existencias por potrero enriquecida con fila de totales generales y recuadro explicativo de glosario de categorías SG.
      - Tablas de eventos (partos, muertes) con tags en negrita y padding profesional; tarjeta de estado óptimo en alertas.
    - **Ficha Zootécnica Individual A4 Apaisada (`src/reports/qr_fichas.py`)**:
      - Encabezado con medalla circular oficial y aro dorado que refleja dinámicamente el estado (`HATO ACTIVO` o `REGISTRO HISTÓRICO (VENDIDO/MUERTO)`).
      - Soporte universal para animales activos e históricos (`VENDIDO`, `MUERTO`, `DESCARTADO`): descarga sin errores 404 ni restricciones de inventario activo.
      - Tarjeta pasaporte izquierda con tag en 22pt, nombre, pastilla ámbar para el Hierro del animal (`HIERRO: <valor>`), QR vectorial nativo de alta resolución e imagen/placeholder.
      - Grilla estructurada de 4 columnas en Identificación y Categoría con chip de estado (`ACTIVO` verde, `VENDIDO` ámbar, `MUERTO` rojo).
      - Tarjetas de genealogía (Línea Materna y Paterna) con padres y abuelos, más chequeo de consanguinidad en 3G.
      - 3 tarjetas KPI métricas de peso (Peso al Nacer, Último Peso, GMD) e historial con zebra.
      - Condición reproductiva y partos limpios; bloque sanitario sin caracteres rotos `■` ni emojis no soportados por WinAnsi.
    - **Tarjetas QR Plastificables por Lote (6 por hoja, `generar_fichas_lote`)**:
      - Código QR vectorial directo con `QrCodeWidget` en cada una de las 6 tarjetas (100% nítidos, scannables e independientes de cache local en disco).
      - Líneas guía de corte punteadas (`c.setDash([2, 3])`) entre filas y columnas para guillotina o tijeras.
      - Franja institucional verde, tag prominente, chip de hierro, edad, perfil zootécnico y estado sanitario sin caracteres rotos.
  - **Pronóstico Meteorológico 7 Días Open-Meteo (`src/engine/pronostico.py`, `src/server/telegram_bot.py`)**:
    - Integración sin clave con Open-Meteo para coordenadas de la finca con caché de 3 horas.
    - Despacho matutino enriquecido con clima del día (temperatura, probabilidad de precipitación, índice UV, viento y alertas de campo).
    - Comando `/pronostico` en Telegram con tabla extendida a 7 días y botones interactivos.
  - **Monitoreo Satelital Radar SAR Todo Clima (Sentinel-1 C-band, `src/gis/earth_engine_sar.py`)**:
    - Radar de microondas de apertura sintética (SAR) vía Google Earth Engine (`COPERNICUS/S1_GRD`, polarizaciones duales VV/VH, 10m).
    - **Penetración 100% de nubes, lluvia y neblina**: resuelve el apagón del NDVI óptico en temporada de lluvias en los Llanos Orientales.
    - Dual-Pol Radar Vegetation Index ($RVI$, Mandal et al. 2020), proxy SAR-NDVI y estimador dieléctrico de humedad superficial de pastura/suelo.
    - Fusión multisensor automática en `actualizar_lecturas_reales(modo='auto')`: si Sentinel-2 está nublado, conmuta de inmediato a Sentinel-1 SAR.
  - **Depuración de UI: Asistente IA Limpio en PWA (v68)**: Remoción completa de los botones/chips inferiores de sugerencias del modal de chat en el Tablero principal y en la Ficha Animal, brindando un área despejada y enfocada exclusivamente en el historial de conversación y entrada de texto.
  - **Optimización de Interfaz Móvil y Mapa Satelital de Precisión (Leaflet PWA v71)**:
    - **Barra de Navegación Móvil Compacta**: Menú inferior preservado estrictamente en 1 sola fila con 5 botones primarios (`Tablero`, `Captura`, `Inventario`, `Finanzas`, `Más`). Acceso al Mapa Satelital delegado a navegación secundaria ("Más" / Trabajo de Campo) para no desbordar el alto en smartphones.
    - **Control de Acceso RBAC para Mapa**: Restricción estricta a roles directivos (`OWNER` y `ADMIN`); redirección automática y respuesta HTTP 403 para usuarios de rol `TRABAJADOR`.
    - **Autolocalización GPS en Tiempo Real**: Al abrir el mapa, la app detecta automáticamente la posición del usuario (`watchPosition`), dibuja el punto pulsante azul (`.self-pulse-dot`) y su halo de precisión en metros, y sincroniza la telemetría con el servidor.
    - **Visualización Satelital Realzada & Tooltips Permanentes**: El modo Satelital resalta los linderos de potrero en tono dorado vibrante (`#f1c40f`) con tenue velo esmeralda translúcido, manteniendo visibles los nombres de cada potrero y conteos de animales (`.mapa-tooltip-potrero`) directamente sobre la foto satelital.
    - **Ampliación de Perímetro para Instalaciones y Filtrado de Telemetría**: El motor geoespacial reconoce corrales, vaquera y casa de la finca hasta 650 m de los potreros, descartando puntos de prueba remotos fuera del área ganadera.
  - **Unificación de Módulos Mapa & GPS (PWA v77)**:
    - Fusión de las vistas antes separadas de Mapa Satelital y Auditoría GPS en una sola experiencia consolidada (`Mapa & GPS`).
    - Visible exclusivamente para roles directivos (`OWNER` y `ADMIN`); completamente oculto y bloqueado (HTTP 403) para `TRABAJADOR`.
    - Integración de auditoría de desplazamientos, cronología por operario, tabla de coordenadas, rondas de campo manuales y botón directo `"🗺️ Ver rastro en mapa"` que traza la polilínea del recorrido sobre la foto satelital con centrado automático.
  - **Dock de Chat Expandible con Dictado de Voz Estilo WhatsApp (PWA v77)**:
    - Sustitución del modal emergente centrado por una barra/dock acoplada en la parte inferior, siempre disponible para escribir o expandirse suavemente hacia arriba.
    - Grabación de notas de voz estilo WhatsApp con cronómetro en vivo, indicador rojo pulsante, descarte (`✕`) y envío inmediato (`✓`) hacia el motor Whisper con inclusión automática de la transcripción y respuesta en el hilo.
  - **Depuración Integral de Terminología**:
  - **Vaquita Animada en GIF desde Video Real (`vaca.mp4`, PWA v86)**:
    - Conversión cuadro a cuadro desde video MP4 (`vaca.mp4`) a GIF animado transparente (`src/pwa/static/vaca_comiendo.gif`, 120 fotogramas, 10s de ciclo continuo de 83 ms/cuadro) con remoción de fondo blanco y aislamiento inteligente de bolsas de aire (bajo vientre, entre patas y base de pasto).
    - **Depuración visual completa**: Remoción del destello blanco atrapado entre cola y pata trasera al colear, eliminación de la mancha blanca oclusa bajo el hocico/cuello al agacharse a pastar, y corrección de la oreja derecha para mantener orejas caídas naturales de vaca mocha/descornada sin falsos cuernos al levantar la cabeza a rumiar.
    - Técnica anti-halo de sangrado negro en bordes para garantizar integración limpia sin rebordes blancos sobre temas oscuro, campestre, claro y sol de campo.
    - Animación 100% natural y orgánica: la vaca come pasto en el suelo, levanta la cabeza, mastica rumiando, mueve las orejas y colea, para luego volver a bajar la cabeza a pastar.
    - Integrada en cabecera de `index.html` y `ficha.html`, precargada en Service Worker (`pwa-ja-v86`), con fallback PNG estático optimizado.
  - **Animaciones Contextuales en Cabecera & Easter Egg Interactivo (PWA v86)**:
    - **Modo Nocturno / Descanso (`vaca_echada.gif`)**: Vaca rumiando plácidamente echada en el suelo; se activa automáticamente de noche (18:30 a 05:30 hora Colombia) o al encender el tema oscuro.
    - **Modo Maternidad / Cría (`vaca_con_cria.gif`)**: Vaca mocha amamantando y cuidando a su ternero; se activa dinámicamente en la cabecera al consultar la ficha de un animal en estado `PARIDA` o con cría al pie. Descornado quirúrgico cuadro a cuadro para mantener pureza de hato mocho sin cuernos.
    - **Modo Toro Reproductor / Padrote (`toro_reproductor.gif`)**: Toro cebuino con cornamenta, giba y gran estampa pastando y marchando con vigor; procesado cuadro a cuadro desde video MP4 (`gemini_generated_video_8d78d637.mp4` / `toro.mp4`) a 120 fotogramas transparentes con anti-halo de borde y optimización para cabecera y miniatura de ficha cuando se consulta un toro reproductor, macho activo o padrote.
    - **Modo Ternero / Cría Juguetona (`ternero.gif`, PWA v87)**: Ternero blanco y negro retozando y pateando alegremente en el pasto; procesado cuadro a cuadro desde video MP4 (`gemini_generated_video_b29b450f.mp4` / `ternero.mp4`) a 120 fotogramas transparentes con remoción de fondo conectada a bordes y bolsas de aire (bajo vientre y cola alzada al patear). Se activa dinámicamente en la cabecera (`header-vaca-img`) y como miniatura/placeholder en la ficha de cualquier cría o ternero (`CRIA_MACHO`, `CRIA_HEMBRA`, categorías `CH`, `CM`, `CRIA`, `TERNER*` o edad < 365 días) cuando no cuenta con foto cargada. Incluye frases personalizadas en el Easter Egg táctil sobre vitalidad, lactancia y vigor de crecimiento en Ganadería JA.
    - **Easter Egg Táctil**: Al tocar la vaquita en la cabecera, reacciona con un brinco elástico, vibración háptica hábil en el dispositivo (`navigator.vibrate`) y un globo de diálogo flotante con estadísticas vivas (conteo de hato activo, potreros y potrero con mayor descanso Voisin) y frases zootécnicas de Ganadería JA (incluyendo reconocimiento al vigor genético del toro reproductor y la vitalidad del ternero).
    - **Lluvia Dinámica en Cabecera**: Líneas diagonales translúcidas animadas sobre el pasto del header cuando el pronóstico del día detecta lluvia (≥1.5 mm o prob ≥65%).
    - **Semáforo Biológico Voisin en Pasturas**: Íconos de estadio forrajero (`🌱` rebrote tierno, `🌿` en crecimiento, `🌾` punto óptimo Voisin, `🍂` pasado/lignificado) en la columna de Días de Reposo de la tabla de potreros.
  - **Módulo de Mercado, Subastas Ganaderas & TRM 100% Automatizado ("Nada Manual", PWA v79)**:
    - **Sincronización Automática Diaria**: Robot en background (`src/integrations/mercado_sync.py`) y script cron (`scripts/actualizar_precios_mercado.py`, programado diario a las 06:00 AM COT) que actualiza cotizaciones oficiales sin requerir digitación ni intervención manual.
    - **Dólar TRM Oficial en Tiempo Real**: Consumo directo de la API de Datos Abiertos de Colombia (Superintendencia Financiera / Banco de la República con fallback automático a DolarAPI).
    - **8 Plazas Ganaderas Estratégicas para Mesetas, Meta**: Cotizaciones por categoría (macho gordo, levante, ternero desteto, hembra levante, vaca descarte) en Granada (Sugameta/SubaGranada), Guamal, San Martín, Puerto López, Catama (Villavicencio), Yopal (Casanare), Bogotá (Frigorífico Guadalupe) y Promedio Nacional FEDEGÁN.
    - **Calculadora Interactiva de Flete, Merma & Utilidad Neta**: Simulación instantánea para lotes de venta desde Mesetas calculando merma por desbaste de viaje, flete por camión y comisión de subasta (2.5%).
    - **Poder Adquisitivo de Insumos del Ariari**: Relación de intercambio kg de novillo vs. insumos críticos (urea 46%, sal mineralizada 8% y 10%, alambre de púas) indexados a TRM, y precio real liquidado de leche finca desde el módulo de Finanzas.
    - **Monitoreo de Titulares y Boletines**: Ticker informativo de boletines semanales de FEDEGÁN y CONtexto Ganadero vía RSS oficial.
  - **Tablero Visual Interactivo de Subastas & Tendencias Semanales (PWA v82)**:
    - **Gráficas Comparativas de Barras Horizontales**: Ranking visual de las 8 plazas ordenadas por precio según la categoría seleccionada (`Macho Gordo`, `Macho Levante`, `Ternero Desteto`, `Hembra Levante`, `Vaca Gorda`), destacando la plaza local (Granada / Ariari) y la plaza líder (Catama / Bogotá) con diferencial explícito en $/kg y respecto a la media nacional.
    - **Curvas de Tendencia Temporal Semanal (7 semanas)**: Evolución multi-plaza en SVG y PNG alta definición (`src/engine/charts.py`) mostrando con claridad si el mercado viene subiendo, bajando o estable, con marcadores interactivos en Granada, Catama, Bogotá y Promedio Nacional.
    - **Badges y Chips de Tendencia Zootécnica**: Indicadores visuales en cada plaza y producto (`▲ +X.X%`, `▼ -X.X%`, `▬ 0.0%`) calculados con funciones de ventana SQL (`LAG` / `ROW_NUMBER`).
    - **KPIs y Diagnóstico Ejecutivo de Comercialización**: Resumen con semáforo alcista/bajista, cotización de Granada, líder regional, líder terminal y recomendación estratégica para venta de lotes desde Mesetas.
    - **Endpoints de Gráficos de Servidor**: `/api/grafico/subastas_comparativa` y `/api/grafico/subastas_tendencia` para reportes PNG y visualización de alta resolución.
  - [x] **Hardening idempotencia de partos y mercado (2026-09-10)**: `registrar_parto` idempotente en `src/db/database.py` — deduplica por `(vaca_id, fecha, id_cria)` y por `(vaca_id, fecha, tipo_evento, id_cria)` cuando `id_cria` es NULL (evita duplicar partos/gemelos en reintentos de `/api/sync`); propaga `grupo_parto_id` al gemelo existente si estaba NULL; `sembrar_precios_mercado_iniciales(forzar=True)` preserva precios manuales (`DELETE ... WHERE COALESCE(fuente,'') NOT LIKE 'MANUAL%'`); doble capa documentada en `src/importers/dbf_importer.py`; 3 tests nuevos en `tests/test_db.py` (gemelo conserva `grupo_parto_id`, misma cría con distinto `tipo_evento` no duplica, ABORTO vs REABSORCIÓN sin cría no colisionan).
  - [x] **Checklist de Ronda Voisin en Pasturas D2 (2026-09-12)**: tabla `aforos_ronda` + `registrar/listar_rondas_voisin` (`src/db/`), `evaluar_ronda_voisin` con 30% MS y semáforo VERDE/AMARILLO/ROJO (`src/engine/pasture_engine.py`, wrapper `PastureEngine`), `formatear_ronda_voisin` (`src/server/formatters.py`), endpoints PWA `POST /api/pasturas/ronda` y `GET /api/pasturas/rondas` (cualquier rol autenticado incl. TRABAJADOR), y modal de 3 pasos en vista Pasturas (`+ Nueva Ronda Voisin`, conversión auto g→kg, chip de semáforo e historial).
- [x] **Bloque 1 Quick Wins Visuales PWA (2026-09-10)** (`src/pwa/`, SW `pwa-ja-v83` → `v84`):
    - Chips `chip amarillo` → `chip ambar` (4 sitios `app.js`); 2 gradientes inline → `.btn-satelite-sar` / `.card-banner` con override tema Sol.
    - Táctil `min-height:44px` en móvil (header, captura/manga, reintento offline); feed Tablero como cards en `≤640px` (`data-label`), tabla en escritorio.
    - CSP `offline.html` sin `onclick` inline (enlace sin JS); bump caché `?v=84` en `index/ficha/login/offline.html`.
- [x] **Rediseño y Optimización UX/UI Móvil PWA (2026-09-12)**:
    - **Bocadillo Vaquita Móvil**: Despliegue como toast flotante centrado con z-index alto bajo el header, sin colisionar con botones ni salirse de pantalla.
    - **Despeje de Botón Flotante Chat vs Siguiente**: Contenedor `main` con padding inferior ampliado a 125px + safe-area, previniendo toques accidentales sobre el FAB.
    - **Inventario y Finanzas Responsivos**: Eliminación de floats desalineados en cabeceras; cuadrícula de KPIs simétrica 2x2 en móviles llenando el 100% del ancho.
    - **Tablero Despejado con Búsqueda Inteligente**: Barra de filtros oculta por defecto en móviles al entrar al Tablero, accesible mediante botón rápido `[🔍 Buscar]`.
    - **Ficha Animal Limpia**: Botones de acción en fila inferior en pantallas pequeñas, previniendo quiebres de texto vertical en edad y hierro, y corrección de desborde en input de foto de arete.
- [x] **Corrección del Monitor de Conexiones en Vivo (Exclusivo OWNER, 2026-09-12)**:
    - **Causa raíz eliminada en SQLite**: Corrección de `self.query_all` por `self.query` en `obtener_usuarios_presencia` (`src/db/database.py`), eliminando la excepción silenciada que devolvía un diccionario de presencias vacío `{}`.
    - **Cálculo de presencia UTC de precisión**: Diferencia temporal con objetos `datetime` timezone-aware en UTC, evitando desincronizaciones horarias y alertas deprecadas.
    - **Resolución multi-canal de presencia**: Helper `_resolver_presencia_usuario` en `src/pwa/app.py` que enlaza la actividad por `user_id` local, `telegram_id` del bot o sesión `"Propietario"` de la PWA, priorizando el canal activo más reciente.
    - **Latido instantáneo y visualización en vivo**: Disparo inmediato de `POST /api/heartbeat` al abrir la PWA, al ingresar a la vista de personal y al presionar "Actualizar Estados"; enriquecimiento de la tarjeta de monitoreo mostrando el contador vivo y los nombres y canales (`Jaime (PWA)`, `Sebastian (Telegram)`) de los operarios conectados.
    - **Test unitario automatizado**: `test_usuarios_presencia_y_monitor_en_linea` en `tests/test_pwa_api.py`.
- [x] **Optimización Compacta del Header Móvil PWA (2026-09-13)**:
    - **Reubicación de Fecha/Hora**: Integración de la fecha y hora pequeña (`reloj-hora`) dentro de `.marca-textos` apilada directamente bajo el título `GANADERÍA JA`, eliminando la sobrecarga horizontal en `.acciones`.
    - **Eliminación de la 3ª Fila en Móvil**: La barra `.acciones` ahora se mantiene estrictamente en 1 sola fila sin desbordes (`flex-wrap: nowrap`), manteniendo los botones de Temas y Salir junto a los íconos (Sync, Ayuda, Notif).
    - **Recuperación de Espacio Vertical**: Reducción de la altura del header móvil de ~150px a ~80px (ahorro de más de 60px verticales), proporcionando mayor espacio libre en pantalla para el Tablero y modales.
- [x] **Proceso Especial de Rectificación de Chapeta / Tag (Exclusivo OWNER, 2026-09-13)**:
    - **Manejo de Errores de Lectura en Campo**: Permite al OWNER corregir números de arete leídos o digitados por error (ej: `JA83` por `JA88`) preservando el historial zootécnico.
    - **Detección Automática de Conflictos y Fusión Atómica**: Si el nuevo tag no existe en la base, renombra limpiamente el animal (`animales` y `fotos`) manteniendo su ID e historial. Si el tag destino ya existe (la vaca real ya estaba registrada y se le cargaron eventos a la chapeta errónea), detecta la colisión, devuelve diagnóstico detallado (HTTP 409) y, bajo confirmación explícita del OWNER (`fusionar_si_existe=True`), transfiere atómicamente todos los eventos (partos, pesajes, tratamientos, palpaciones, celos, servicios, fotos, etc.) al animal destino y elimina el registro erróneo sin violar integridad referencial.
    - **Seguridad RBAC Estricta**: Bloqueo con HTTP 403 para roles `ADMIN` y `TRABAJADOR`; habilitado única y exclusivamente para el rol `OWNER` tanto en PWA como en Telegram.
    - **Integración UI PWA & Telegram**: Botón `🏷️ Rectificar Chapeta` en la Ficha del Animal (y acceso rápido desde "Editar Animal") con modal interactivo de confirmación y advertencia en caso de fusión. Comando `/renombrar_animal <tag_viejo> <tag_nuevo> [--fusionar]` en Telegram bot.
- [x] **Manga Corral en Captura, Asignación de Tareas con Acknowledge, Botón Flotante Global (+) y Precio Bogotá Guadalupe (2026-09-13)**:
    - **Botón Manga Corral en Captura**: Acceso directo y destacado a la Manga de Corral (trabajo en lote) desde el módulo de Captura Rápida de Campo.
    - **Gestión de Tareas con Asignación y Cumplimiento (Acknowledge)**: Permite programar tareas dirigidas a animales (`JA457`) o potreros (`OLEGARIO I`), adjudicadas al Encargado, Administrador o integrantes del equipo. Soporta confirmación de tarea realizada con notas del trabajo ejecutado, ejecutor y foto de comprobante opcional, registrándose en la bitácora histórica y canal de equipo.
    - **Botón Flotante Global (FAB +)**: Acceso rápido flotante a Captura en todos los módulos clave (Tablero, Inventario, Pasturas, Ficha, Agenda, etc.), con prellenado automático de animal y apilado responsivo perfecto sobre la burbuja de chat en móvil (390×844).
    - **Precio Bogotá Frigorífico Guadalupe**: Visualización priorizada en el Tablero del precio de referencia de Macho Gordo para la plaza de Bogotá (Frig. Guadalupe).
- [x] **Genealogía JA218, Sugerencia Arete Cría en Parto (SG) y Eliminación de Eventos para OWNER (2026-09-13)**:
    - **Corrección Árbol Genealógico en PWA (`JA218`)**: Solucionado `ReferenceError: click is not defined` en `app.js` al renderizar enlaces a fichas de padres/abuelos; ahora navega fluidamente usando atributos `data-ir-ficha`.
    - **Sugerencia Automática de Arete de Cría (Regla Software Ganadero)**: Al registrar partos, el sistema sugiere automáticamente el arete de la cría como `<TagMadre>-<DígitoAño>` (ej. `JA457` en 2026 -> `JA457-6`, `n088` -> `n088-6`). Es 100% editable y opcional, cuenta con chip clickeable de sugerencia y previene envíos prematuros con la tecla Enter antes del paso 3.
    - **Eliminación y Reversión de Eventos (Exclusivo OWNER)**: Endpoint seguro `POST /api/eventos/eliminar` y botones de papelera `[🗑️]` en PWA (Fichas técnicas de animal y Tablero de últimos eventos). Revierte atómicamente el estado del hato (restaura potrero en traslados erróneos, devuelve animales a `ACTIVO` si se elimina muerte/venta, limpia crías fantasma si se descarta un parto accidental, y anula alertas derivadas).
- [x] **Auditoría de Inventario y Comparación 100% Exacta con Software Ganadero (2026-09-13)**:
    - **Cotejo con Respaldo Real (`Datos20260913.Zip`)**: Verificación automatizada con `scripts/comparar_backup_sg.py`. Total activos en SG: **328**, Total activos en Bitácora: **328**. Coincidencia total del 100% (0 diferencias de inventario, 0 animales faltantes, 0 discrepancias de potrero en animales activos).
    - **Resolución Priorizada de Potreros Vigentes**: Corrección en `src/db/database.py` (`potrero_id` y migración de auto-reparación en `create_tables`) para priorizar potreros georreferenciados y con prefijo de letra sobre códigos históricos numéricos obsoletos de SG (01..23), garantizando que animales como `JA457` mantengan su potrero activo `B02 - OLEGARIO II` (`id=29`) y no queden catalogados como `HISTORICO`.
    - **Depuración de Eventos Fantasma**: Eliminación del traslado automático de `JA457` (id 166) originado durante la importación comparativa, restableciendo la cronología real de eventos en el Tablero de la PWA.
    - **Captura de Parto con Toro/Padre y Revisión Completa de Cría**:
      - Selector opcional de Toro / Padre (`GET /api/toros`) con reproductores activos (`T01` BRUNO, `T02` PERLA OHIO, etc.), machos activos del hato y opción para toro externo o pajuela; enlazado automáticamente al árbol genealógico del ternero (`padre_id`).
      - Autocompletado completo e instantáneo de animales activos (`#dl-tags`) y potreros (`#dl-potreros`) tanto en tecleo como al enfocar cualquier campo de captura.
      - Visualización destacada en el paso 3 ("Revise y guarde") mostrando número de cría sugerido/asignado, sexo, estado, peso y toro/padre.
- [x] **Reorganización y Claridad de Estados Fisiológicos & Reproductivos en Ficha Animal (2026-09-14)**:
    - **Cálculo Riguroso del Ciclo Actual (`src/engine/dashboard_data.py`)**: Aislamiento temporal de servicios y diagnósticos posteriores al último parto (`fecha >= ultimo_parto.fecha`), evitando que inseminaciones históricas de ciclos pasados (ej. 2017) declaren falsamente como preñada a una vaca parida recientemente.
    - **Categorización Fisiológica & Reproductiva Inmediata**: Distinción clara en chips de cabecera (`.ficha-head`) para: Cría (Ternero/Ternera con días de nacido), Novilla de levante, Novilla de vientre, Vaca en ordeño (con DEL), Vaca seca y Toro reproductor; junto con el estado del ciclo actual: Preñada/Gestante (FEP y días de gestación), Servida / Sin palpar (días post-servicio), Vacía / Sin palpar (días abiertos y semáforo zootécnico) o Vacía palpada.
    - **Tarjeta #1 en Pestaña General**: Ubicación prioritaria de la tarjeta **Estado Fisiológico & Reproductivo** en la primera posición de la ficha técnica con desglose en 2 columnas (Producción/Lactancia y Reproducción Actual), semáforo zootécnico de días abiertos (verde ≤90d, amarillo 91-150d, rojo >150d) y alertas veterinarias contextuales.
    - **KPIs Dinámicos por Sexo/Rol**: Indicadores superiores adaptativos según se consulte una vaca, novilla, cría o toro reproductor.
    - **Pruebas y Verificación Visual**: Suite automatizada `tests/test_ficha_estados_zootecnicos.py` (100% pasando) y capturas móviles verificadas en viewport 390×844 DPR=2.
- [x] **Producción Total Diaria de Leche por Recibos & Curva Diaria (`v=leche`, 2026-09-14)**:
    - **Alineación con el Flujo Real de Finca (Recibos / Tanque)**: La producción se carga a partir de las fotos y digitalización con IA de los recibos de quincena, registrando el total diario entregado por la finca (~300-350 L/día).
    - **Aislamiento de Históricos de Software Ganadero (2016-2018)**: Filtro estricto en `datos_leche()` y `charts.py` para la era activa (`>= 2024`), evitando que 456 registros viejos de pesajes individuales por vaca distorsionen la serie diaria ni los totales actuales.
    - **Depuración de Duplicados & Corrección de Captura**: Eliminación del registro accidental de suma acumulada (fila 473 de 5,092 L) y protección en `app.js` (`bindTablaReciboIa`) para no volcar la suma quincenal en el campo de un solo día.
    - **Gráfico Interactivo de Producción Diaria (SVG responsivo)**: Curva de barras con litros por día, línea de promedio diario destacada (318.2 L/d), picos y pisos identificados, y tooltips vectoriales adaptados a móvil (390×844) y escritorio.
    - **KPIs Ejecutivos & Tabla Detallada**: Total período (5,092 L en 16 días), promedio diario (318.2 L/d), pico más alto (368 L el 24-Ago), piso más bajo (276 L el 26-Ago) y desglose día a día con variación vs promedio (+/- L) y foto de respaldo.
- [x] **Leche: promedio litros/vaca/día y pausas temporales de ordeño (2026-09-19)**:
    - **Vacas en ordeño vs ordeñándose**: `Database.resumen_ordeno()` cruza las vacas ACTIVO en etapa de ordeño (paridas hace <300 días y sin secado confirmado, mismo criterio que la ficha individual) contra las que tienen una pausa abierta en la tabla nueva `pausas_ordeno`, para saber cuántas se ordeñan de verdad.
    - **KPI `litros/vaca/día` en la vista Leche**: litros del recibo de quincena ÷ vacas ordeñándose (es un promedio de hato: el recibo solo captura el total de la finca, no pesaje individual), más la tarjeta "En ordeño / Ordeñándose / N en pausa".
    - **Pausa temporal sin secar la vaca**: `POST /api/animal/<tag>/pausa-ordeno` y `/reanudar-ordeno` con botones **Pausar / Reanudar ordeño** en la pestaña Leche de la ficha (caso de campo: se suelta el ternero con la vaca porque nació flaco). NO toca `secados` (el fin real de la lactancia), es idempotente (una pausa abierta no se duplica) y conserva el histórico al reanudar.
    - **Fix de UX al pausar/reanudar**: la ficha se reabre en la pestaña **Leche** (antes el re-render volvía a "General" y el botón de reanudar quedaba inalcanzable, dejando la pausa imposible de deshacer desde la interfaz). Los chips de variación ahora usan `chip ambar` (la clase `chip naranja` no existía en el CSS).
    - **Pruebas**: 5 tests nuevos en `tests/test_pausas_ordeno.py` (idempotencia de la pausa, reanudación, criterio de "en etapa de ordeño", pausa de una vaca secada que no infla el conteo, tags inexistentes y el KPI `litros_por_vaca_dia` en `datos_leche`).
- [x] **Ocupación Dinámica de Potreros & Listado Interactivo de Animales en Inventario (`v=pasturas`, `v=inventario`, 2026-09-14)**:
    - **Ocupación Dinámica Real Voisin (`datos_pasturas`)**: Corrección de ocupaciones estáticas en 0 d. Ahora calcula en tiempo real los días de ocupación basados en la fecha del último traslado o entrada (`traslados.fecha` / `potreros.fecha_entrada`) para potreros con animales activos (`estado = 'ACTIVO'`), y días de reposo con estadios de pastura (🌱 Rebrote, 🌿 Desarrollo, 🌾 Óptimo, 🍂 Pasado) para potreros en descanso.
    - **Columna Total Animales en Tabla de Pasturas**: Despliegue de cabezas activas por potrero (ej. `🐄 53 cab.`, `🐄 100 cab.`, o `0 (Vacío)`) con botón de acción directa "Listar" para consultar los animales presentes sin salir de la vista.
    - **Exploración Interactiva de Inventario Completo (`/api/inventario/animales`)**:
      - **Estructura del Hato (Categorías SG)**: Clic en cualquier categoría (Cría macho/hembra, Novillas, Vacas paridas/secas, Machos ceba, Reproductores), barra apilada o botón "Listar" abre un modal interactivo con el censo de animales activos.
      - **Categorías de Edad (Brackets)**: Exploración interactiva por grupos etarios (<1a H, 1-2a H, 2-4a H, 4-8a H, 8-10a H, >10a H, <1a M, 1-2a M, Reproductores).
      - **Distribución por Potrero**: Tarjetas y barras de ocupación con acceso inmediato a los animales de cada potrero y del grupo "Sin potrero".
      - **Pirámide de Edades**: Clic directo en las barras o leyendas (ej. `47 H · 53 M`) para listar los animales de cada género y grupo etario.
    - **Filtro Estricto de Hato Activo**: Conforme a la directriz de `AGENTS.md`, todas las consultas filtran rigurosamente por `estado = 'ACTIVO'` (336 animales en total), evitando inflar el inventario con registros históricos.
    - **Verificación Visual Móvil**: Pruebas automáticas CDP en viewport móvil (390×844 DPR=2) y validación de sintaxis con hooks locales.
- [x] **Gráficos Vectoriales SVG Nativos Adaptados a Temas & Modo Dual en la PWA (2026-09-15)**:
    - **Reemplazo de Imágenes Fijas por Gráficos Vectoriales Nativos**: En lugar de depender exclusivamente de imágenes estáticas PNG renderizadas por Matplotlib en el servidor, se implementó el endpoint REST `/api/grafico-datos/<tipo>` en `src/pwa/app.py` y `src/engine/dashboard_data.py`, entregando datos estructurados JSON para que el navegador dibuje vectores SVG crisp, interactivos y ultralivianos.
    - **Soporte Completo para los 11 Gráficos de la PWA**: `evolucion` (serie 12 meses), `reproductivo_hato` (gauges de preñez y días abiertos), `ocupacion` (permanencia y semáforo Voisin), `aforo` (kg MV/m² y promedio), `flujo_caja` (ingresos/egresos/utilidad), `waterfall_inventario` (balance paso a paso), `gmd_hato` (dispersión GMD vs edad), `composicion_racial` (distribución I/C/T/M), `subastas_comparativa` & `subastas_tendencia` (precios $/kg por plaza), `mapa_potreros` y `carga_animal`.
    - **Adaptación Instantánea a los 4 Temas**: El renderizado vectorial en `src/pwa/static/ja-core.js` consume directamente los tokens CSS del sistema (`--superficie`, `--texto`, `--borde`, `--verde-marca`, `--acento`, etc.), adaptándose con elegancia y contraste tanto en Modo Oscuro como en Verde Campestre, Sol de Campo y Claro Editorial.
    - **Modo Dual con Acordeón Desplegable (Matplotlib PNG)**: Cada gráfico incluye un acordeón colapsable `<details>` ("Ver gráfico original del servidor (Matplotlib PNG)") que permite alternar, auditar o descargar la imagen generada por Matplotlib sin saturar la vista.
    - **Aislamiento de Alcance**: La generación de gráficos para reportes PDF y Telegram permanece intacta.
    - **Pruebas y Verificación Visual**: Suite `tests/test_grafico_datos.py` (100% pasando), chequeos de sintaxis con Node y validación visual automatizada mediante CDP en viewport móvil (390×844 DPR=2).
- [x] **Optimización Móvil de Inventario, Gráficos y Búsqueda Rápida**:
    - **Fechas Rotadas y Leyendas en Evolución**: Fechas inclinadas a -45° con año corto (ej. `Sep '25`) en el gráfico de evolución para eliminar definitivamente solapamientos y colisiones en pantallas estrechas; leyenda explícita "Nacimientos (crías)" (aclarando qué es "Nac").
    - **Tablas de Inventario 100% Responsivas**: En pantallas móviles (≤640px) se oculta la columna redundante *Acción* (el nombre y conteo ya abren la lista con un toque), logrando que las 4 columnas ocupen el 100% exacto del viewport sin desborde ni barra horizontal.
    - **Stack FAB Flotante con Búsqueda Inmediata**: Botón (+) más discreto y compacto (38px desktop / 36px móvil) junto a botón de lupa (🔍) para buscar y abrir al instante la ficha técnica de cualquier animal por tag o nombre, habilitado tanto en el tablero como en la ficha técnica.
- [x] **Auditoría Integral y Optimización UX/UI de la PWA (Móvil, Tablet y Computador, 2026-09-19)**:
    - **Ficha Animal Priorizada**: Reubicación de la cabecera zootécnica al tope absoluto de la ficha. El módulo de identificación por foto de arete y OCR ahora se presenta como un acordeón colapsable `<details>` ("📷 Identificar otro animal por foto o QR") posicionado debajo de la cabecera, eliminando el scroll vertical forzado en móvil.
    - **Liberación de Espacio Vertical (`#barra-filtros`)**: Ocultamiento automático de la barra secundaria `Potrero / Tag / Cargar` en todas las vistas de datos (Inventario, Pasturas, Ficha, Genética, Reproducción, Manga, Sanidad, Leche, etc.), reservándola exclusivamente para el Tablero cuando sea necesario. Ahorro de 70px a 90px de espacio útil.
    - **Captura Rápida en Grilla Simétrica (2x6 Móvil / 3x4 Tablet / 4x3 Desktop)**: Organización de los 12 botones de tipo de evento zootécnico en una cuadrícula CSS Grid equilibrada (`.cap-tipos-grid`), con síntesis del aviso introductorio superior.
    - **Header Robusto en 1 Sola Fila (56px) para Tablet y Laptops (641px–1150px)**: Prevención de que el header se parta en dos filas (evitando el salto de 110px de alto); reubicación de selectores secundarios y botón de instalación en el menú desplegable del logo.
    - **Tablet Portrait Compacto (641px–880px)**: Sidebar optimizada a 180px para entregar +62px de ancho adicional a las tablas zootécnicas y gráficos.
    - **Despeje Total de Botones Flotantes en Desktop y Tablet**: Ocultamiento de botones flotantes redundantes `(+)` y `(🔍)` en pantallas ≥641px (donde la barra lateral ya ofrece accesos directos), manteniendo despejada la esquina inferior de tablas y gráficos. En móvil (≤640px) se conserva únicamente el botón compacto de búsqueda `(🔍)` apilado sobre la burbuja del chat.
    - **Curva de Leche y Gráficos SVG**: Ajuste de márgenes vectoriales para evitar que la etiqueta del promedio diario colisione con las barras de producción.
    - **Lupita de Búsqueda al 60% y Etiqueta "Captura" sin `+` redundante (2026-09-19)**: La lupita flotante se redujo a 26px de diámetro (60% de sus 44px) con icono de 12px y `min-width/min-height: 0` para vencer el `min-height: 36px` global de `button` que la deformaba en óvalo; `right: 27px` la mantiene centrada con la burbuja del chat conservando el hueco de 10px en ambos estados (barra inferior visible y auto-oculta). También se quitó el prefijo `+` de la etiqueta del botón Captura de `#nav-principal` (el affordance `+` queda solo en su icono circular), evitando el doble signo junto a las letras.
    - **Corrección de Cortina de Lluvia y Clima en Tiempo Real en Cabecera PWA (2026-09-19)** 🌧️☀️:
      - **Causa Raíz**: Open-Meteo solo consultaba el acumulado diario (`precipitation_sum`, `precipitation_probability_max`). En el trópico húmedo de Mesetas (Meta), casi cualquier día tiene pronóstico acumulado $\ge 1.5$ mm en 24h, lo que hacía que `hayLluvia = (lluviaMm >= 1.5 || probLluvia >= 65)` fuera `true` las 24 horas continuas, simulando lluvia permanente sobre las vacas.
      - **Telemetría en tiempo real**: Se incorporó el bloque `&current=temperature_2m,relative_humidity_2m,precipitation,rain,showers,weather_code` en `src/engine/pronostico.py`, determinando `esta_lloviendo` por precipitación activa instantánea o códigos WMO (51-67, 80-82, 95-99). Se expuso en `clima_hoy` (`datos_tablero`) y `datos_pasturas` con TTL de 30 min para mantener frescos los datos en la PWA.
      - **Cabecera PWA**: `actualizarClimaHeader` en `src/pwa/static/app.js` ahora activa la cortina animada `#header-lluvia` estrictamente cuando `esta_lloviendo` es `true`. En ausencia de lluvia muestra sol radiante (`☀️`), nublado (`⛅`) o reposo nocturno (`🌙 ✨`).
      - **Validación**: 19 pruebas en `tests/test_pronostico.py` en verde (100% pasando), `node --check` y `python -m compileall` sin errores.
- [x] Suite de pruebas con pytest en verde (conteo vigente en el CI).
- [x] **PWA móvil: burbuja, KPIs, foto y mapa alineado (2026-09-23)**:
  - La burbuja del chat y la lupita viven dentro de la barra inferior en celular (≤640px), no encima de precios, edad ni mapa.
  - La última tarjeta KPI impar ocupa la fila completa (sin hueco). Etiqueta "Activos" sin glifos ♀♂ que se veían rotos.
  - Identificar por foto usa botón "Tomar foto o elegir" en español, no el input nativo "Choose File".
  - Abrir una ficha ya no vuelve a mostrar la barra Potrero/Tag. El clima dice "prob. del día" y solo marca "Lloviendo ahora" si hay lluvia en el momento.
  - El mapa satelital cuenta activos con el mismo potrero vigente que Inventario (`COALESCE(potrero_id, último traslado)`), no solo `potrero_id`.
  - Verificado en móvil 390×844 (Edge headless + copia de la base, `scratch/verif_cambios_movil.py`): 9/9 checks en verde y `node --check`, `ruff`, `compileall`, `test_mapa_data.py` (4) y `test_potreros_reales_inventario.py` (9) pasando.
- [x] **Endurecimiento de sesión PWA (2026-09-23)**:
  - Cada login exitoso (PIN o maestra) parte de sesión limpia (`session.clear()`): no se arrastra `telegram_id` ni identidad previa en equipos compartidos.
  - La clave maestra ya no adopta un `user_id` arbitrario del formulario (el `login.html` ni lo pide): solo se acepta si existe en `users.json`; si no, sesión OWNER sin `user_id`.
  - El alta de usuario (`POST /api/usuarios`) no devuelve el PIN y los errores de colisión son genéricos (sin valor ni dueño del PIN). El listado ya lo enmascaraba como `····`.
  - Pruebas: colisión genérica actualizada + 2 tests nuevos (sesión maestra y no-devolución de PIN); `test_pwa_api.py` (14 login/usuarios) y `test_pwa_agenda.py` (6) en verde.
- [x] **Simulador de cruzamiento en 1 toque, Fase 5.2 parcial (2026-09-23)**:
  - `Database.simular_cruzamiento(vaca, toro)` (solo lectura, sin crear fantasmas): veredicto APTO / NO RECOMENDADO / NO EVALUABLE con ancestros comunes (padre/abuelo/bisabuelo por rama), relación directa y aviso de pedigrí parcial. Mismo criterio 3G de `verificar_consanguinidad`.
  - PWA: `GET /api/simular-cruzamiento` (todos los roles) + veredicto automático en el paso 3 de Captura Servicio/IA (avisa, no bloquea). Telegram: la confirmación de servicio anexa el veredicto 🧬 cuando el toro es del hato.
  - Pruebas: `tests/test_simular_cruzamiento.py` (11 en verde: medios hermanos, abuelo en 2G, padre-hija, toro externo, typo sin fantasma, endpoint 401/400 y confirmación del bot); verificado en móvil con JA457 × T01 (APTO con aviso de pedigrí parcial).
- [x] **Distocias y pérdidas gestacionales, Fase 5.2 completa (2026-09-23)**:
  - Columna `distocia` en `partos` (migración idempotente + backfill por notas), `registrar_parto(distocia=)` (forzado a 0 en pérdidas, propagación en reintentos) y `Database.metricas_perdidas_reproductivas()` (tasa de pérdida, desglose por tipo, tasa de distocia, crías muertas, reincidentes y recientes; gemelar = 1 evento).
  - Parser: `DISTOCIA_RE` ("hubo que sacarle el ternero", "parto distócico/difícil", "meter mano"); PWA con selector Sí/No en captura de parto + aviso en paso 3; sync y bot lo guardan y la confirmación de Telegram avisa "Parto difícil ⚠️".
  - Vista Reproducción con KPIs de pérdidas/distocias + tarjeta de reincidentes y últimas pérdidas; `/kpi_reprod` con la misma sección (visible aun sin datos de concepción).
  - Dos bugs del NLU hallados al paso y corregidos: `es_consulta` trataba cualquier "que" como pregunta (notas como "parió la 47 que estaba gorda" nunca se registraban; ahora solo cuenta si empieza con "que" o no hay evento+arete) y `extraer_tags` devolvía "macho"/"hembra" (cada "parió la 47, ternero macho" creaba un animal fantasma ACTIVO; verificado que ya no).
  - Pruebas: `tests/test_distocia_perdidas.py` (23 en verde) + regresión NLU/bot (136 + 91 + 57 + 25) y 13/13 checks visuales en móvil.
- [x] **Seguridad: backoff de login, cuotas en API y exportación solo OWNER (2026-09-24)**:
  - Login con backoff progresivo (`CastigoStore` en `data/login_castigos.json`): cada ventana de 8 intentos / 5 min agotada duplica el bloqueo (60s → 1h); un éxito limpia ventana y castigo. El PIN de 4 dígitos ya no se barre en días.
  - Cuotas por usuario+IP en endpoints costosos (429 + `Retry-After`): voz 12/min, identificar 30/min, satélite 6/5min, gráficos 40/min, sync 40/min, mensajes 90/min. Sin esto, una sesión saturaba waitress y tumbaba la PWA.
  - `/exportar` (comando y botón) solo OWNER + aviso a los demás OWNER por Telegram; botón oculto para ADMIN y manual actualizado.
  - Pruebas: `tests/test_seguridad_rate_limit.py` (5 en verde: progresión/tope/persistencia del castigo, escalado y limpieza en login, 429 en API) + regresión (37 + 14 + 60).
- [x] **Modo Campo del mayordomo (2026-09-24)**:
  - Vista `campo` (`?v=campo`): saludo con fecha, 4 mosaicos grandes (Registrar, Hoy, Ficha, GPS) y resumen "Hoy en la finca" (vencidos + hoy, retiros, enlace a agenda). Botón Campo en la barra solo para TRABAJADOR y mosaico "Modo Campo" en el sheet para todos.
  - El TRABAJADOR cae en campo al entrar (antes caía en captura); puede abrir agenda y ficha; el GPS localiza y guarda la ronda sin mapa (el satelital sigue solo oficina, 403 intacto).
  - Pruebas: `tests/test_modo_campo.py` (3 en verde) + 10/10 checks visuales con login PIN real de trabajador (cae en campo, GPS detecta ORDENIO SANTA MARTHA con 62 animales y la ronda queda persistida).
- [x] **Buscador unificado y cielo detrás de la vaquita (2026-09-24)**:
  - Se quitó el botón "Buscar" del Tablero (duplicaba la lupita 🔍): la lupita ahora trae campo de arete/tag Y de potrero, con botones "Abrir Ficha" y "Ver en Tablero" (aplica el filtro y muestra la barra con contexto). Enter sin arete filtra el Tablero.
  - La vaquita de la cabecera quedó delante del cielo (z-index sobre sol/luna/nubes); la lluvia sigue cayendo encima, como debe ser.
  - Verificado en móvil 390×844 (`scratch/verif_buscar_cielo.py`): 9/9 checks en verde.
- [x] **Catálogo y Evaluación de Inseminadores + Módulo de Sincronizaciones IATF (2026-09-24)** 🧬💉🏆:
  - **Catálogo y Evaluación de Inseminadores**: Registro centralizado de técnicos (`inseminadores`) con cálculo de IAs realizadas, diagnosticadas, preñadas, vacías, Tasa de Concepción (%) y Servicios por Concepción (S/C) con semáforo zootécnico (🟢 ≥55%, 🟡 45-54%, 🔴 <45%). Selector inteligente en Captura Rápida de Servicio/IA con autocompletado y preselección del usuario en sesión.
  - **Biblioteca de Protocolos Hormonales IATF**: Protocolos precargados con dosis, vías y marcas comerciales de la industria (Convencional 8 días con eCG para carne/doble propósito, Convencional Lechería y J-Synch 6 días para novillas de vientre).
  - **Lotes IATF y Cronograma Automatizado**: Programación automática de alertas de manejo y medicación en `recordatorios_programados` (Día 0 dispositivo+estrógeno, Día 8 retiro+luteolítico+eCG, Día 10 IATF y Día 40 ecografía).
  - **Inseminación a 1-Toque del Lote**: Registro masivo de servicios, asignación de toro/inseminador y descuento automático en el inventario de pajuelas (`pajuelas_inventario`).
  - **Validación**: Pruebas unitarias en `tests/test_inseminadores_iatf.py` (4/4 en verde), 110 pruebas de API en verde y verificación visual interactiva móvil (390×844) y escritorio (1280×800) sin desbordes.
- [x] **Tablero Integral de Potreros, Descargas por Sección (Excel/PDF), Banco de Semen y Tactos SG en PWA (2026-09-23)** 🌿📊❄️🖐️:
  - **Tablero Integral de Potreros**: Eliminada la redundancia de 3 gráficos apilados y tablas repetidas. Sustituido por selector interactivo de gráficos (`🗺️ Mapa Potreros (Voisin)`, `📊 Ocupación y Carga`, `🌾 Aforos y Forraje`) y un **Tablero Integral de Potreros** que reúne en una sola fila por potrero: área (ha), días de ocupación/reposo, semáforo Voisin, cabezas activas, último aforo manual (kg MV/m² y kg MS/ha) y biomasa satelital MS/ha, con atajos directos a listar aretes y registrar aforo.
  - **Descargas de Informes Especializados en PDF y Excel (`.xlsx`)**: Añadida barra de exportación en las cabeceras de Leche, Finanzas, Potreros/Pasturas, Sanidad, Inventario y Reproducción. Motor nativo `src/reports/excel_report.py` con `openpyxl` y endpoints parametrizados `GET /api/reporte.pdf?seccion=...` y `GET /api/reporte.xlsx?seccion=...`.
  - **Banco de Semen & Termo Criogénico**: Módulo en Reproducción con KPIs de días restantes de nitrógeno líquido, stock total de pajuelas, toros disponibles y alertas de stock bajo (≤ 3 pajuelas), tabla de canastillas e inventario detallado de pajuelas, con modales de recarga y entrada rápida.
  - **Tactos / Palpaciones al Estilo Software Ganadero**: Formulario en Captura Rápida y botón en Ficha del Animal con método de diagnóstico (Manual vs Ecógrafo), resultado (Preñada/Vacía/Dudosa), días de gestación con cálculo reactivo de FEP (`FEP = Fecha + 283 - Días`), reproductor, hallazgo ovárico/zootécnico, Condición Corporal (1-5), peso (kg), profesional y notas.
- [x] **Monta Natural Distintiva y Sugerencia Automática de Padre en Partos (2026-09-24)** 🐂💡🌾:
  - **Diferenciación Visual de Monta Natural vs IA/IATF**: En el feed de eventos recientes del Tablero y en las tablas de la Ficha Animal, los eventos de servicio por monta natural (`MONTA`, `MN`, toro a campo) se distinguen con un chip ámbar de `🐂 Monta Natural` con el ícono vectorial de toro, separándolos visualmente de `Inseminación (IA)` e `IATF` (verde con ícono de espermatozoide).
  - **Detección Zootécnica de Concepción por Potrero Compartido**: Cálculo riguroso de la ventana de gestación bovina ($F_c = F_{\text{parto}} - 283\text{ días}$, margen $\pm 15$ días). Prioridad 1: verifica si hubo un servicio registrado previo. Prioridad 2: averigua en qué potrero estaba la vaca durante la fecha de concepción analizando el historial de traslados y determina qué toro reproductor activo oficial de la finca (`T01..T05`) compartía ese mismo potrero en esa fecha.
  - **Asistente Inteligente en Captura de Partos (`/api/parto/sugerir-padre`)**: Al digitar o seleccionar el tag de la madre en el modal de Parto de la PWA, se consulta reactivamente la sugerencia y se despliega un banner de alto contraste con el toro sugerido, el potrero donde ocurrió la monta y los ~283 días de gestación, preseleccionando automáticamente al reproductor en `#cap-toro-padre` con opción de un toque `[Aplicar]`.
  - **Trazabilidad Genealógica Automática**: `Database.registrar_parto` autocompleta el `padre_id` de la cría si no se especifica de forma manual, garantizando la línea paterna en registros rápidos o desde canales sin UI interactiva.
  - **Validación Automatizada**: 5 pruebas unitarias en `tests/test_sugerir_padre_parto.py` (100% pasando), `node --check` limpio y verificación interactiva móvil (390×844) capturada con la vaca `A004` y el toro `T01 (BRUNO)`.

### 📋 Hoja de Ruta Pendiente ([Ver Detalle Completo en docs/ROADMAP_FASES_4-8.md](docs/ROADMAP_FASES_4-8.md))
> ✅ La **Fase 4 (El Despacho Matutino)** ya está implementada: briefing 05:30 AM, inseminaciones AM-PM, Voisin día 3 y reposo ≥30d, palpación/eco día 35/60, recordatorios programados (`/programar`), registro de leche (`/leche`) y alertas de celo perdido.
- [x] **Fase 5.2 — Consanguinidad 3G & Fertilidad Avanzada (2026-09-24)**: Simulador de cruzamiento 1-toque consanguinidad 3G, ranking fertilidad toro, distocias y pérdidas gestacionales, catálogo y evaluación de técnicos inseminadores, y módulo de sincronizaciones hormonales IATF.
- [x] **Fase 6.1 — Economía & Costeo**: Costeo unitario dinámico (Costo/kg carne, Precio venta/kg, Margen/kg y Margen $/L leche) en módulo Finanzas.
 - [ ] **Fase 8.1 — Estimación de Condición Corporal (BCS)**: Clasificación automática 1.0-5.0 con Gemini Vision.
 - [ ] **B) Verificar CSP en producción (`scripts/nginx-bitacora.conf`)**: ejecutar en el VPS: `curl -I https://ganaderiaja.duckdns.org/login | grep script-src`. Si `script-src 'self'` sin `unsafe-inline`, el botón "Instalar App" en login NO funciona. El fix ya existe en `/static/login.js?v=85` (extraído en Bloque 2); solo requiere deploy y verificación.
- [x] **Motor Geoespacial Real para Fase 6.2 + 8.2** ([Ver Plan en docs/PLAN_GEO_SATELITAL_6.2_8.2.md](docs/PLAN_GEO_SATELITAL_6.2_8.2.md)): área real + polígonos georreferenciados (WGS84) de los 20 potreros desde QGIS (Fases A+B), **NDVI real vía Google Earth Engine** (Fase C), **lluvia satelital CHIRPS** (Fase D), y **radar SAR Sentinel-1 todo clima** (Fase E). Fusión multisensor automatizada en cron cada 3 días.
- [x] **Mapa Satelital Interactivo & Web Push en PWA**: Visualización interactiva Leaflet con operarios en vivo, GeoJSON de potreros y notificaciones push nativas de alertas sanitarias/reproductivas.
- [x] **Inventario y Pasturas unificados: solo 20 potreros reales y alineación canónica con Software Ganadero (2026-09-16)** 🐄🌿:
    - **Alineación con reporte nativo SG (`potreros.jpg`)**: La fuente maestra y canónica del potrero de cada animal es su ficha actual (`animales.potrero_id`), actualizada directamente por el archivo maestro `HOJA.DBF` de Software Ganadero y por los traslados registrados en la PWA.
    - Se corrigió `POTRERO_ACTUAL_EXPR` y `POTRERO_VIGENTE_SUBQUERY` para usar `COALESCE(a.potrero_id, ut.potrero_destino)` en vez de sobreescribir la ficha con traslados históricos obsoletos de `traslado.dbf` (los cuales ubicaban erróneamente 14 animales en Olegario I y 3 en Plan Versalles cuando en SG ambos potreros están en 0).
    - Unificación en `datos_pasturas()`, `_inventario_por_potrero_real()`, `animales_de_potrero()`, `calcular_existencias_potreros_sg()`, Mapa Satelital y bot Telegram.
    - **Conteo verificado**: Ordeno Santa Martha (56), Corral Santamartha (46), Paritorio (2), Olegario II (35), Corral Versalles (3), Carretera Versalles (18), Casa Abajo Versalles (103), Coquera (20), Ramon Casa (23), Ramon Carretera I (27) = **333 activos exactos**, 100% idéntico a Software Ganadero. Tests en verde.
- [x] **Gráfico "Mapa de potreros" corregido: solo potreros reales y tablero de rotación Voisin (2026-09-17)** 🗺️🌿:
    - **Bug**: `datos_grafico("mapa_potreros")` (`src/engine/dashboard_data.py`) consultaba `SELECT id, nombre, codigo, area_has FROM potreros ORDER BY nombre` **sin filtro**, así que pintaba los **57** potreros de la base (20 reales + 37 códigos legacy del DBF sin geometría, todos "En reposo" y duplicando nombres como Coquera, Carretera Versalles, Lecheras u Olegario II). Era el único lugar de la PWA que no aplicaba `SQL_POTRERO_REAL`, contradiciendo a la tabla de Ocupación, el Mapa Satelital y el PNG de Matplotlib, que sí muestran 20.
    - **Fix backend**: ahora filtra con `SQL_POTRERO_REAL`, cuenta animales activos por **potrero vigente (último traslado)** en vez de `animales.potrero_id`, y reutiliza el helper nuevo `_enriquecer_rotacion_potreros()` (extraído de `datos_pasturas()`, misma lógica Voisin) para que ambos reporten idéntico universo y días.
    - **Tarjeta útil**: el gráfico pasó de tarjetas planas a un **tablero de rotación**: semáforo Voisin (🟢 óptimo/listo, 🟡 rotar pronto, 🔴 sobreocupado, 🌱 en reposo), ha, cabezas, días de ocupación/reposo y carga en cab/ha, ordenado por urgencia de rotación (ocupados primero, más días arriba). Subtítulo real: "20 potreros reales · 10 ocupados · 10 en reposo".
    - **Botón muerto arreglado**: "Abrir Mapa Satelital GPS Completo" (`src/pwa/static/ja-core.js`) se emitía con `id='btn-ir-mapa-satelital-desde-past'` pero **no tenía ningún handler**; ahora usa `data-accion="ir-mapa-satelital"` y el listener delegado de `app.js` navega a `v=mapa` con `irAVista("mapa") + cargar()`.
    - **Verificación**: 4 tests nuevos en `tests/test_potreros_reales_inventario.py` (excluye legacy, cuenta por traslado, carga/estado de rotación, orden) + capturas con Edge headless en móvil 390×844 DPR2 y escritorio 1366×900: 20 tarjetas, cero nombres legacy, sin desbordes, y el botón montando Leaflet; `node --check` y `ruff` en verde.
- [x] **Buscador Dedicado en Vista Ficha, Cabecera Global y Atajos de Teclado (`v=ficha`, 2026-09-20)** 🔍🐄:
    - **Solución al bug de navegación en PC/Escritorio**: Al navegar a Ficha Animal en computador, la barra de filtros (`#barra-filtros`) se ocultaba automáticamente y los botones flotantes FAB están deshabilitados en pantallas grandes (`display: none !important`), dejando al usuario sin campo de entrada y provocando error al intentar identificar sin tag.
    - **Tarjeta de Búsqueda Dedicada (`renderFichaBuscador`)**: Al entrar a la vista Ficha sin un animal preseleccionado, se monta una interfaz centralizada con campo de búsqueda interactivo (`#input-tag-ficha-vista`), autocompletado en tiempo real con datalist (`#dl-tags`), chips de acceso rápido (últimos consultados, toros reproductores), y fallback con acordeón de OCR por foto.
    - **Botón Global en Cabecera (`#btn-header-buscar-animal`)**: Añadido en `index.html` y `ficha.html`, permitiendo abrir el modal de búsqueda rápida de cualquier animal desde cualquier vista tanto en móvil como en escritorio.
    - **Atajos de Teclado Globales (`Ctrl+K` y `/`)**: Permiten invocar instantáneamente el modal de búsqueda rápida sin tocar el ratón.
    - **Acción "Buscar otro" en Ficha**: Botón accesible en la cabecera zootécnica de cada animal (`.ficha-head-acciones`) y en la pantalla de "Sin registro", facilitando saltar a otro animal sin recargar ni perder contexto.
    - **Validación Visual Responsiva**: Probado en móvil (390×844 DPR=2) y escritorio (1366×768), asegurando que los botones y campos se adapten al 100% de ancho sin desbordes. Suite de pruebas con 864 tests pasando y sintaxis validada.
- [x] **Emancipación de Software Ganadero (SG) y Consolidación de Históricos Zootécnicos (2026-09-22)** 🚀🐄:
    - **Desinstalación del Vigilante Local en Windows**: Se eliminó y detuvo permanentemente la tarea programada `BitacoraVigilanteCopiasSG` y los procesos residuales de sincronización continua mediante `scripts/desinstalar_tarea_programada.ps1`. `scripts/vigilar_copias_windows.ps1` fue marcado formalmente como deprecado.
    - **Extracción e Importación Histórica Zootécnica Profunda (`src/importers/extractor_historico_sg.py`)**: Se analizaron e importaron de forma idempotente y de alto rendimiento todas las tablas zootécnicas históricas de SG nunca antes aprovechadas:
        - **6,713 pesajes de leche** individuales consolidados en `produccion_leche`.
        - **702 diagnósticos de gestación / tactos** en `diagnosticos_gestacion`.
        - **712 evaluaciones de condición corporal** (escala 1-5) en `condicion_corporal`.
        - **101 registros de inventario de pajuelas y toros** en `pajuelas_inventario`.
        - Registro del termo de nitrógeno líquido en `termo_nitrogeno`.
    - **Herramienta de Auditoría y Comparación Bajo Demanda (`scripts/comparar_backup_sg.py`)**: Permite contrastar en segundos cualquier archivo `.Zip` de Software Ganadero con la base nativa SQLite de Bitácora JA, generando balances de hato activo (`estado = 'ACTIVO'`), discrepancias de ventas/bajas, animales nacidos en campo no registrados en SG, diferencias de potrero y exportación automática a Excel estructurado (`--excel reportes/comparacion_sg_bitacora.xlsx`).
    - **Desacoplamiento de Categorías**: Categorización zootécnica autónoma de primera clase (`base["categoria"]`) en el motor de analítica, garantizando independencia total respecto a SG. Suite de pruebas con 3 tests nuevos en `tests/test_emancipacion_sg.py` en verde.
- [x] **Módulo de Reversión Inteligente (Deshacer) y Métricas Zootécnicas Avanzadas de Software Ganadero en PWA (2026-09-22)** 🔄📊:
    - **Reversión Inteligente en Cascada (`src/db/database.py`)**:
        - `eliminar_evento()` unificado con tolerancia a nombres singulares/plurales y soporte para `condicion_corporal`, `pluviometria`, `aforos_historico`.
        - Restauración inteligente automática: si se borra una muerte/venta/descarte, el animal vuelve a `estado = 'ACTIVO'`; si se borra un traslado, retorna a su `potrero_origen`; si se borra un parto o servicio, limpia alertas y crías asociadas sin eventos posteriores.
        - Delegación total de `eliminar_registro()` a `eliminar_evento()`, dotando también al comando `/deshacer` de Telegram de reversión inteligente.
    - **Control de Acceso y API de Eventos Recientes (`src/pwa/app.py`)**:
        - Endpoint `POST /api/eventos/eliminar` habilitado para roles `OWNER` y `ADMIN`.
        - Endpoint `GET /api/eventos/recientes` que entrega los últimos 35 eventos con metadatos descriptivos y bandera de permisos para deshacer.
    - **Interfaz Visual en PWA (`src/pwa/templates/index.html` y `src/pwa/static/app.js`)**:
        - Modal responsivo `#modal-ultimos-eventos` con diseño táctil, botón rojo de confirmación y advertencia clara de reversión inteligente. Accesible desde el menú de usuario y desde "Más Módulos".
        - Botón de papelera en la Ficha del Animal disponible para `OWNER` y `ADMIN`.
    - **Métricas Zootécnicas Oficiales de Software Ganadero**:
        - **Índice de Fertilidad (I.F.) Oficial SG**: $I.F. = \frac{\text{Preñadas} + \text{Descanso } \le 120\text{d}}{\text{Vientres } \ge 3.0\text{a}} \times 100$ con semáforo zootécnico (🟢 $\ge 75\%$, 🟡 $60-74\%$, 🔴 $< 60\%$) y desglose completo.
        - **Distribución de Días Abiertos (DA)**: 9 intervalos zootécnicos idénticos a SG (`0-90`, `91-120`, ..., `>300`) con barras proporcionales.
        - **Intervalo Entre Partos (IEP)**: 6 tramos de frecuencia (`<365`, `365-395`, ..., `>485`).
        - **Días En Leche (DEL) & Curva de Lactancia**: Promedio DEL del lote y vacas por etapa (Pico, Meseta, Descenso, Prolongada) en la pestaña Leche.
    - **Catálogo & Evaluación de Inseminadores (`src/db/models.py`, `src/db/database.py`, `src/pwa/`)**:
        - Nueva tabla `inseminadores` con auto-siembra inicial de técnicos históricos de `servicios` y usuarios del sistema (`Auth`).
        - Evaluación zootécnica de inseminadores (`evaluar_inseminadores`): IAs realizadas, diagnosticadas, preñadas, vacías, Tasa de Concepción (%) y Servicios por Concepción (S/C).
        - Semáforo zootécnico oficial: 🟢 $\ge 55\%$ (Excelente), 🟡 $45-54\%$ (Aceptable), 🔴 $< 45\%$ (Revisar técnica de inseminación).
        - Selector rápido en Captura de Servicio/IA (`dl-inseminadores`), prellenado automático con el usuario en sesión y modal `[➕]` para alta inmediata de técnicos en campo.
    - **Sincronizaciones IATF & Cronograma de Fármacos (`src/db/models.py`, `src/db/database.py`, `src/pwa/`)**:
        - Tablas zootécnicas `protocolos_iatf`, `lotes_iatf`, `lote_iatf_animales`.
        - Sembrado de protocolos estándar de la industria validados para trópico bajo/medio:
            - *Convencional 8 Días con eCG* (Carne / Doble Propósito en anestro / vacas con cría).
            - *Convencional 8 Días Lechería Especializada* (con GnRH o BE al inicio, retiro PGF2α + ECP).
            - *J-Synch 6 Días* (Novillas de primer servicio / alta ciclicidad con GnRH al retiro).
        - Cronograma automático de alertas de fármacos en `recordatorios_programados` (Día 0, Día 8, Día 10) y recordatorio ecográfico automático (Día 35 post-IATF).
        - Registro de aplicación de fármacos paso a paso con trazabilidad de marca comercial y dosis (DIB, Cronipres, Sincrodiol, Ciclase, Lutalyse, ECP, Novormon, Conceptal).
        - Inseminación Masiva a 1-Toque: genera los servicios en bloque, descuenta existencias de pajuelas en `pajuelas_inventario` y actualiza el lote a `IATF_REALIZADA`.
        - Endpoints REST `/api/inseminadores`, `/api/iatf/protocolos`, `/api/iatf/lotes` y soporte offline en `/api/sync`.
        - Pruebas unitarias completas en `tests/test_inseminadores_iatf.py` y validación visual en viewport móvil (390×844 DPR=2) y escritorio (1280×800).


---

## 📂 Estructura de Directorios
```text
2026-08-24-bot-bitacora-de-campo/
├── AGENTS.md            # Reglas e instrucciones para IAs
├── CLAUDE.md            # Guía para Claude Code
├── README.md            # Estado y especificaciones del proyecto
├── requirements.txt     # Dependencias Python (pytest, python-telegram-bot, python-dotenv, reportlab)
├── .env.example         # Plantilla de variables de entorno (TELEGRAM_TOKEN, etc.)
├── src/                 # Código fuente principal
│   ├── main.py          # Punto de entrada (CLI y flags --server, --importar, --exportar)
│   ├── db/              # Modelos y base de datos SQLite (incluye tabla fotos y columna ocr_text)
│   ├── engine/          # Motores reproductivo, sanitario, pasturas, crecimiento, consultas
│   ├── parsers/         # Parser NLU de eventos + manejador multimodal
│   ├── ocr/             # Motor OCR multi-backend (pytesseract, Pillow, easyocr) y extracción de aretes/fármacos
│   ├── llm/             # Router + agentes Gemini multi-dominio + arquitectura NLU híbrida (Capa 1 regex + Capa 2 LLM)
│   ├── importers/       # Importador DBF nativo (TP/SG)
│   ├── exporters/       # Exportador DBF nativo y empaquetador ZIP (Fase 2)
│   ├── reports/         # Generador de reportes en PDF con reportlab (Fase 2)
│   ├── bot/             # Interfaz del bot (CLI)
│   └── server/          # Bot de Telegram + autenticación RBAC (Fases 1, 1.1, 2)
├── docs/                # Documentación, diagramas y guías
├── tests/               # Pruebas y validación (pytest)
└── scripts/             # Automatizaciones VPS y utilidades
    ├── setup_vps.sh         # Configuración inicial del droplet (Ubuntu 22.04 / 24.04)
    ├── iniciar_bot.sh       # Arranque del bot en modo servidor
    ├── backup_diario.sh     # Respaldo diario de SQLite (retención 30 días)
    └── importar_backup.sh   # Importación de backups DBF (Software Ganadero)
```
