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
  consultar imágenes de los animales, y `/aqui` / botón `📍 GPS` (comparte tu ubicación y el bot detecta en qué potrero estás y guarda la ronda, visible en la auditoría del dueño).
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
- **Pruebas:** Pytest — **761 pruebas en verde** (100% pasando)
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
- [x] Suite de pruebas con pytest: **761 pruebas en verde** (100% pasando)
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
- [x] Suite de pruebas con pytest: **761 pruebas en verde** (100% pasando).

### 📋 Hoja de Ruta Pendiente ([Ver Detalle Completo en docs/ROADMAP_FASES_4-8.md](docs/ROADMAP_FASES_4-8.md))
> ✅ La **Fase 4 (El Despacho Matutino)** ya está implementada: briefing 05:30 AM, inseminaciones AM-PM, Voisin día 3 y reposo ≥30d, palpación/eco día 35/60, recordatorios programados (`/programar`), registro de leche (`/leche`) y alertas de celo perdido.
- [ ] **Fase 5.2 — Consanguinidad 3G & Fertilidad Avanzada**: Simulador cruzamiento 1-toque consanguinidad 3G, ranking fertilidad toro, partos distócicos y abortos.
- [x] **Fase 6.1 — Economía & Costeo**: Costeo unitario dinámico (Costo/kg carne, Precio venta/kg, Margen/kg y Margen $/L leche) en módulo Finanzas.
 - [ ] **Fase 8.1 — Estimación de Condición Corporal (BCS)**: Clasificación automática 1.0-5.0 con Gemini Vision.
 - [ ] **B) Verificar CSP en producción (`scripts/nginx-bitacora.conf`)**: ejecutar en el VPS: `curl -I https://ganaderiaja.duckdns.org/login | grep script-src`. Si `script-src 'self'` sin `unsafe-inline`, el botón "Instalar App" en login NO funciona. El fix ya existe en `/static/login.js?v=85` (extraído en Bloque 2); solo requiere deploy y verificación.
- [x] **Motor Geoespacial Real para Fase 6.2 + 8.2** ([Ver Plan en docs/PLAN_GEO_SATELITAL_6.2_8.2.md](docs/PLAN_GEO_SATELITAL_6.2_8.2.md)): área real + polígonos georreferenciados (WGS84) de los 20 potreros desde QGIS (Fases A+B), **NDVI real vía Google Earth Engine** (Fase C), **lluvia satelital CHIRPS** (Fase D), y **radar SAR Sentinel-1 todo clima** (Fase E). Fusión multisensor automatizada en cron cada 3 días.
- [x] **Mapa Satelital Interactivo & Web Push en PWA**: Visualización interactiva Leaflet con operarios en vivo, GeoJSON de potreros y notificaciones push nativas de alertas sanitarias/reproductivas.

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
