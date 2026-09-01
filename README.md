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
| `/graficos` (4 categorías zootécnicas) | ✅ | ✅ | — |
| `/potreros` / `/potreros sg` | ✅ | ✅ | — |
| `/ocupacion` / `/rotacion` (Voisin) | ✅ | ✅ | — |
| `/alertas` | ✅ | ✅ | — |
| `/animales` | ✅ | ✅ | — |
| `/status` | ✅ | ✅ | — |
| `/duplicados` | ✅ | ✅ | — |
| `/usuarios` | ✅ | ✅ | — |
| `/reporte` [diario\|semanal\|N] | ✅ | ✅ | — |
| `/exportar` | ✅ | ✅ | — |
| `/importar` (guía) | ✅ | ✅ | — |
| Enviar archivo `.zip` como documento | ✅ | ✅ | — |
| `/confirmar_importar` | ✅ | ✅ | — |
| `/descartar_backup` | ✅ | ✅ | — |
| `/agregar_usuario` | ✅ | — | — |
| `/quitar_usuario` | ✅ | — | — |
| `/logs` | ✅ | — | — |

### Comandos principales

- **Todos los roles:** `/menu` y `/start` (tablero visual corto y táctil diferenciado por rol), `/despacho` / `/matutino` / `/hoy` (resumen matutino de 05:30 AM con alertas de ordeño, celos AM-PM, recordatorios y repro), `/leche <litros>` (registro rápido de producción total de leche del hato en tanque), `/programar <fecha> <hora> <msg>` (agenda recordatorios para el despacho), `/ayuda` (listado exhaustivo de comandos), **texto libre**
  con los 8 eventos zootécnicos, **nota de voz** (transcripción automática con Whisper
  y ejecución del evento o consulta), `/consulta <tag>` / `/historial <tag>` (ficha zootécnica
  completa del animal con entrega automática de fotografía y curva láctea/peso), **foto** (con detección OCR de tag y medicamento en frasco;
  se guardan en `media/` y en la base SQLite) y `/fotos [tag]` para
  consultar imágenes de los animales.
- **OWNER y ADMIN:** `/graficos` (panel interactivo de gráficos en 4 categorías: Hato, Reproducción, Pasturas y Leche con vista detalle simplificada), `/potreros` y `/potreros sg` (matriz exacta de existencias por potrero de Software Ganadero),
  `/ocupacion` / `/rotacion` (días de pastoreo y descanso Voisin con semáforo), `/alertas`,
  `/animales`, `/status`, `/usuarios`, `/reporte [diario|semanal|N]` (genera y envía el reporte PDF institucional con logo `GANADERÍA JA`),
  `/exportar` (genera y envía el archivo ZIP con las 8 tablas DBF para Software Ganadero),
  `/importar` (guía de importación), enviar el `.zip` del backup directamente como
  documento por el chat, `/confirmar_importar` (procesa el backup pendiente) y
  `/descartar_backup` (elimina el backup pendiente sin procesar).
  Límite de Telegram: **20 MB**; archivos más pesados se suben por SSH y se importan
  con `scripts/importar_backup.sh` (ver [`docs/DESPLIEGUE_DIGITALOCEAN.md`](docs/DESPLIEGUE_DIGITALOCEAN.md)).
- **Solo OWNER:** `/agregar_usuario <user_id> <ROL> [nombre]`,
  `/quitar_usuario <user_id>` y `/logs`.

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
> (despliegue paso a paso en VPS) y [`docs/TELEGRAM_GUIA_USUARIO.md`](docs/TELEGRAM_GUIA_USUARIO.md)
> (manual para el personal de campo).

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
- **Pruebas:** Pytest — **402 pruebas en verde** (100% pasando)
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
- [x] Suite de pruebas con pytest: **402 pruebas en verde** (100% pasando)

### ⏳ En Progreso / Calibración Continua
- [x] **Fase 5.1 — Reproducción Completa & Termo Criogénico**: Evento palpación directo (Preñada/Vacía con días de gestación), tablas `diagnosticos_gestacion`, `pajuelas_inventario`, `termo_nitrogeno`, KPIs tasa de concepción y S/C, sincronización con ficha zootécnica (estado reproductivo y sección diagnósticos), limpieza de FEP en diagnósticos VACIA, descuento automático de pajuelas al inseminar, comandos `/pajuela_stock`, `/pajuela_add`, `/termo`, `/recarga_n2`, alerta automática de recarga N₂ (<=3d) integrada en Despacho Matutino y OCR de facturas de pajuelas (`src/ocr/factura_parser.py`) con propuesta y confirmación táctil de stock.
- [ ] Calibración de parámetros y retroalimentación de uso en campo.

### 📋 Hoja de Ruta Pendiente ([Ver Detalle Completo en docs/ROADMAP_FASES_4-8.md](docs/ROADMAP_FASES_4-8.md))
- [ ] **Fase 4 — El Despacho Matutino**: Briefing 5:30 AM con inseminaciones AM-PM, Voisin día 3 y listo ≥30d, palpación/eco día 35/60, celo perdido >50d y alertas push ≥4d.
- [ ] **Fase 5.2 — Consanguinidad 3G & Fertilidad Avanzada**: Simulador cruzamiento 1-toque consanguinidad 3G, ranking fertilidad toro, partos distócicos y abortos.
- [ ] **Fase 6 — Economía + Balance Forrajero**: Costeo tratamiento/suplemento (Costo/kg y Margen $/L), balance MS oferta vs demanda (2.8% PV x UGG) y ajuste UGG/ha por lluvia IDEAM.
- [ ] **Fase 7 — PWA Oficina + Corral Offline**: Dashboard web ejecutivo, fichas QR en PDF por lote, identificación arete foto/RFID barro y modo offline lite con cola + SOS.
- [ ] **Fase 8 — Visión Multimodal**: Estimación BCS foto 1.0-5.0 con Gemini Vision, OCR arete avanzado (sucio/botón) y NDVI Sentinel-2 via qgis-mcp con carga dinámica.

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
