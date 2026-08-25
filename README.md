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

## 🛠️ Stack Tecnológico y Skills Integradas

- **Lenguaje / Runtime:** Python 3.10+
- **Base de Datos:** SQLite
- **Pruebas:** Pytest — **98 pruebas en verde**
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

# 2. Importación del backup histórico (Software Ganadero TP/SG)
python -m src.importers.dbf_importer
#    Equivalente con la ruta explícita del Zip:
python src/main.py --importar docs/Datos20260823.Zip

# 3. Ejecución de la suite de pruebas
pytest
```

El CLI también admite flags de una sola ejecución: `--texto "..."`, `--audio ruta.mp3`
y `--imagen ruta.jpg`, además de `--db` para elegir la base SQLite destino.

---

## 📍 Estado Actual

### ✅ Completado
- [x] Modelos y base SQLite (`src/db/`): animales, partos, celos, servicios, tratamientos, pesajes, potreros, traslados y alertas
- [x] Motores (`src/engine/`): reproductivo, sanitario, pasturas, crecimiento y consultas (Q&A)
- [x] Parser NLU de 8 eventos + manejador multimodal de voz/foto/texto (`src/parsers/`)
- [x] Importador DBF nativo de backups TP/SG (`src/importers/`)
- [x] Interfaz del bot (CLI interactivo y flags) (`src/bot/`)
- [x] Suite de pruebas con pytest: **98 pruebas pasando en verde**

### ⏳ En Progreso
- [ ] Integración con Whisper/OCR reales (actualmente simulados vía archivos `.txt` acompañantes)

### 📋 Tareas Pendientes
- [ ] Documentación y diagramas en `docs/`

---

## 📂 Estructura de Directorios
```text
2026-08-24-bot-bitacora-de-campo/
├── AGENTS.md            # Reglas e instrucciones para IAs
├── CLAUDE.md            # Guía para Claude Code
├── README.md            # Estado y especificaciones del proyecto
├── src/                 # Código fuente principal
│   ├── main.py          # Punto de entrada (CLI)
│   ├── db/              # Modelos y base de datos SQLite
│   ├── engine/          # Motores reproductivo, sanitario, pasturas, crecimiento, consultas
│   ├── parsers/         # Parser NLU de eventos + manejador multimodal
│   ├── importers/       # Importador DBF nativo (TP/SG)
│   └── bot/             # Interfaz del bot
├── docs/                # Documentación y backups (Datos20260823.Zip)
├── tests/               # Pruebas y validación (pytest)
└── scripts/             # Automatizaciones y utilidades
```
