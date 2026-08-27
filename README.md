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
- «¿qué vacas están en el potrero olegario 1?» (búsqueda de animales por potrero)
- «¿cuál es el historial de la vaca 47?» (historial de animales)
- «¿cuánto pesó la 12 y cuál fue su ganancia diaria?»
- «¿cuándo le toca el secado a la 47?»

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
| `/start`, `/help` | ✅ | ✅ | ✅ |
| Texto libre (8 eventos) | ✅ | ✅ | ✅ |
| Nota de voz (Whisper) | ✅ | ✅ | ✅ |
| Foto | ✅ | ✅ | ✅ |
| `/historial <tag>` / `/consulta <tag>` | ✅ | ✅ | ✅ |
| `/fotos` / `/foto <tag>` | ✅ | ✅ | ✅ |
| `/alertas` | ✅ | ✅ | — |
| `/potreros` / `/potreros <nombre>` | ✅ | ✅ | — |
| `/animales` | ✅ | ✅ | — |
| `/status` | ✅ | ✅ | — |
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

- **Todos los roles:** `/start` y `/help` (ayuda adaptada al rol), **texto libre**
  con los 8 eventos zootécnicos, **nota de voz** (transcripción automática con Whisper
  y ejecución del evento o consulta), `/consulta <tag>` / `/historial <tag>` (ficha zootécnica
  completa del animal), **foto** (con detección de tag y eventos
  en el pie de foto; se guardan en `media/` y en la base SQLite) y `/fotos [tag]` para
  consultar imágenes de los animales.
- **OWNER y ADMIN:** `/alertas`, `/historial <tag>`, `/potreros`, `/animales`,
  `/status`, `/usuarios`, `/reporte [diario|semanal|N]` (genera y envía el reporte PDF),
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

# 2. Sembrar los usuarios autorizados (editar el user_id del OWNER)
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

---

## 🛠️ Stack Tecnológico y Skills Integradas

- **Lenguaje / Runtime:** Python 3.10+
- **Base de Datos:** SQLite
- **Pruebas:** Pytest — **171 pruebas en verde**
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
  - [x] Exportador DBF nativo (`src/exporters/`): serializador `DBFWriter` para las 8 tablas y exportación de paquetes ZIP vía `/exportar` y CLI `--exportar`
  - [x] Exportadores adicionales CSV y JSON vía `/exportar csv` y `/exportar json`
- [x] **Fase 3 (Parte 1) — Notas de Voz con Whisper**:
  - [x] Integración de Whisper local (`faster-whisper` / `openai-whisper`) para transcripción de audio en español (`es`)
  - [x] Procesamiento automático en tiempo real de notas de voz en Telegram y CLI con ejecución de eventos y respuestas
  - [x] Resolución flexible de tags alfanuméricos (`N069`, `N-069`, `N 069`) y permisos ampliados para `/consulta`
- [x] **Integración LLM con NVIDIA NIM (build.nvidia.com)**:
  - [x] Conector HTTP para modelos en la nube de NVIDIA (ej. `meta/llama-3.3-70b-instruct`, `mistralai/mistral-nemo-12b-instruct`) con fallback automático y sin dependencias pesadas (`src/llm/`).
  - [x] Arquitectura NLU híbrida: Capa 1 local rápida (regex) + Capa 2 LLM NVIDIA para jerga compleja, notas con múltiples eventos zootécnicos y extracción JSON estructurada.
  - [x] Soporte para notas compuestas con múltiples eventos en un solo mensaje y persistencia automática en SQLite.
  - [x] Configuración de variables de entorno `NVIDIA_API_KEY` y `NVIDIA_MODEL` en `.env`.
- [x] Documentación y diagramas en `docs/`: arquitectura general, flujo de sincronización SG y matriz de permisos (`docs/ARQUITECTURA_Y_FLUJOS.md`)
- [x] Suite de pruebas con pytest: **171 pruebas pasando en verde**

### ⏳ En Progreso / Planificado para la Próxima Sesión
- [ ] **Fase 3 (Parte 2) — OCR para Fotos:**
  - Reconocimiento de aretes/tags y frascos de medicamentos en fotos de campo.

### 📋 Hoja de Ruta Pendiente
- [ ] OCR visual en imágenes de campo.

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
│   ├── db/              # Modelos y base de datos SQLite (incluye tabla fotos)
│   ├── engine/          # Motores reproductivo, sanitario, pasturas, crecimiento, consultas
│   ├── parsers/         # Parser NLU de eventos + manejador multimodal
│   ├── llm/               # Cliente NVIDIA NIM + arquitectura NLU híbrida (Capa 1 regex + Capa 2 LLM)
│   ├── importers/       # Importador DBF nativo (TP/SG)
│   ├── exporters/       # Exportador DBF nativo y empaquetador ZIP (Fase 2)
│   ├── reports/         # Generador de reportes en PDF con reportlab (Fase 2)
│   ├── bot/             # Interfaz del bot (CLI)
│   └── server/          # Bot de Telegram + autenticación RBAC (Fases 1, 1.1, 2)
├── docs/                # Documentación, diagramas y guías
├── tests/               # Pruebas y validación (pytest — 151 pruebas)
└── scripts/             # Automatizaciones VPS y utilidades
    ├── setup_vps.sh         # Configuración inicial del droplet (Ubuntu 22.04 / 24.04)
    ├── iniciar_bot.sh       # Arranque del bot en modo servidor
    ├── backup_diario.sh     # Respaldo diario de SQLite (retención 30 días)
    └── importar_backup.sh   # Importación de backups DBF (Software Ganadero)
```
