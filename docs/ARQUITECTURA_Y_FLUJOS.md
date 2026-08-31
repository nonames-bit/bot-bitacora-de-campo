# 📐 Arquitectura del Sistema y Flujos de Datos

Este documento describe la arquitectura modular, el modelo de datos, los flujos de eventos zootécnicos y el ciclo de sincronización bidireccional entre el **Bot de Bitácora de Campo Ganadero** y el **Software Ganadero (SG/TP)**.

---

## 🏛️ 1. Arquitectura General del Sistema

```text
                                  ┌───────────────────────────────┐
                                  │      USUARIOS EN CAMPO        │
                                  │  (Dueño, Admin, Trabajadores) │
                                  └───────────────┬───────────────┘
                                                  │
                                   Telegram / CLI interactivo
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CAPA DE ENTRADA Y SEGURIDAD                                     │
│  ┌─────────────────────────────┐                         ┌───────────────────────────────────┐  │
│  │   Auth / RBAC (users.json)  │                         │       Telegram Application        │  │
│  │  OWNER · ADMIN · TRABAJADOR │                         │  Comandos / Handlers de Mensajes  │  │
│  └──────────────┬──────────────┘                         └─────────────────┬─────────────────┘  │
└─────────────────┼──────────────────────────────────────────────────────────┼────────────────────┘
                  │                                                          │
                  ▼                                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                CAPA DE PARSERS Y MULTIMODAL                                     │
│  ┌───────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────┐  │
│  │  NLU / EventParser        │   │  MediaHandler             │   │  QueryEngine              │  │
│  │  (8 eventos zootécnicos,  │   │  (Voz, fotos, tags OCR,   │   │  (Q&A lenguaje natural,   │  │
│  │   normalización, fechas)  │   │   captions de aretes)     │   │   consultas reproductivas)│  │
│  └─────────────┬─────────────┘   └─────────────┬─────────────┘   └─────────────┬─────────────┘  │
└────────────────┼───────────────────────────────┼───────────────────────────────┼────────────────┘
                 │                               │                               │
                 ▼                               ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CAPA DE MOTORES ZOOTÉCNICOS                                     │
│  ┌───────────────────────────────┐                       ┌───────────────────────────────────┐  │
│  │  ReproductiveEngine           │                       │  HealthEngine                     │  │
│  │  • Regla AM-PM celos          │                       │  • Retiro en carne y leche        │  │
│  │  • FEP (+283d), Eco (+35d),   │                       │  • Bloqueo sanitario              │  │
│  │    Palpación (+60d), Secado   │                       │                                   │  │
│  ├───────────────────────────────┤                       ├───────────────────────────────────┤  │
│  │  PastureEngine (Voisin)       │                       │  GrowthEngine                     │  │
│  │  • Leyes de reposo/ocupación  │                       │  • Ganancia Media Diaria (GMD)    │  │
│  │  • Aforo kg/m², carga UGG     │                       │  • Peso ajustado a 205 días       │  │
│  └──────────────┬────────────────┘                       └─────────────────┬─────────────────┘  │
└─────────────────┼──────────────────────────────────────────────────────────┼────────────────────┘
                  │                                                          │
                  ▼                                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                CAPA DE DATOS Y PERSISTENCIA                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                 Database (SQLite — WAL Mode)                              │  │
│  │  Tablas: animales · partos · celos · servicios · tratamientos · pesajes · traslados       │  │
│  │          muertes · movimientos · potreros · alertas · fotos · produccion_leche            │  │
│  │          recordatorios_programados · import_sg_historial · consultas_animal               │  │
│  └──────────────────────────────┬──────────────────────────────────────────┬─────────────────┘  │
└─────────────────────────────────┼──────────────────────────────────────────┼────────────────────┘
                                  │                                          │
                                  ▼                                          ▼
┌──────────────────────────────────────────────────┐       ┌──────────────────────────────────────┐
│           CAPA DE IMPORTACIÓN HISTÓRICA          │       │      CAPA DE REPORTES Y EXPORTACIÓN  │
│  ┌────────────────────────────────────────────┐  │       │  ┌────────────────────────────────┐  │
│  │  DBFReader / Importer (TP/SG)              │  │       │  │  PDF Reports (/reporte)        │  │
│  │  • 8 tablas DBF (hoja, partos, celos, etc.)│  │       │  │  • Resumen semanal / diario    │  │
│  │  • Deduplicación por llave natural         │  │       │  ├────────────────────────────────┤  │
│  │  • Sincronización idempotente              │  │       │  │  DataExporter (/exportar)      │  │
│  └────────────────────────────────────────────┘  │       │  │  • DBF (Software Ganadero ZIP) │  │
│                                                  │       │  │  • CSV (todas las tablas)      │  │
│                                                  │       │  │  • JSON (volcado estructurado) │  │
│                                                  │       │  └────────────────────────────────┘  │
└──────────────────────────────────────────────────┘       └──────────────────────────────────────┘
```

---

## 🔄 2. Ciclo de Sincronización con Software Ganadero (SG)

El sistema mantiene una coexistencia armoniosa con el software de escritorio del cliente mediante un ciclo continuo:

```text
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 1. CAMPO: Mayordomo o vaquero registra notas (texto/voz/foto) en bot   │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 2. NUBE: SQLite procesa eventos y genera alertas automáticas           │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 3. DUEÑO: Consulta /reporte en PDF o /exportar csv/dbf                 │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 4. ESCRITORIO: Carga manual o validación en Software Ganadero SG       │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 5. BACKUP: SG genera nuevo backup (DatosYYYYMMDD.Zip con Dbf.zip)      │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 6. SYNC: Se envía el .zip al bot -> /confirmar_importar                │
  │    (Deduplicación automática por llave natural, sin duplicar notas)    │
  └────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ 3. Flujo de Procesamiento de Eventos y Alertas

```text
Entrada de Texto / Foto
        │
        ▼
   EventParser
        │
   ┌────┴──────────────────────────┐
   │ Clasificación de Evento       │
   └────┬──────────────────────────┘
        │
        ├─► Parto ────────► Registra parto + cría ──► Alerta secado, IEP, genealogía
        ├─► Celo ─────────► Registra celo ──────────► Alerta INSEMINACION_PROGRAMADA (AM-PM)
        ├─► Servicio ─────► Registra IA/MN ─────────► Alertas: ECOGRAFIA (+35d), PALPACION (+60d),
        │                                                     SECADO (FEP - 60d), PARTO_ESPERADO (+283d)
        ├─► Tratamiento ──► Registra fármaco ───────► Alertas: RETIRO_LECHE / RETIRO_CARNE
        ├─► Pesaje ───────► Registra peso ──────────► Calcula GMD y peso ajustado 205 días
        ├─► Traslado ─────► Registra movimiento ────► Actualiza ocupación/reposo potrero (Voisin)
        ├─► Muerte ───────► Registra baja ──────────► Estado = MUERTO (excluido de inventario activo)
        ├─► Movimiento ───► Compra/Venta/Entrada ───► Alta/Baja en inventario
        ├─► Leche Hato ───► /leche <litros> ────────► Guarda en produccion_leche (animal_id = NULL)
        └─► Programar ────► /programar <fecha> ─────► Guarda en recordatorios_programados (estado PENDIENTE)
```

### 3.1 Flujo del Despacho Matutino (05:30 AM)

El Despacho Matutino (`formatear_despacho_matutino`) se ejecuta automáticamente cada mañana a las 05:30 AM (vía `scripts/enviar_despacho.py` en cron/systemd) o bajo demanda con `/despacho`. Consolida 4 consultas prioritarias para la operación del día:

```text
 Cron 05:30 AM / /despacho
            │
            ▼
┌────────────────────────────────────────────────────────┐
│             formatear_despacho_matutino()              │
└───────────┬──────────────┬──────────────┬──────────────┘
            │              │              │              │
            ▼              ▼              ▼              ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐
│ 1. Ordeño &     │ │ 2. Celos AM  │ │ 3. Tareas    │ │ 4. Calendario   │
│    Retiros      │ │    (AM-PM)   │ │    Agendadas │ │    Reproductivo │
│                 │ │              │ │              │ │                 │
│ • tratamientos  │ │ • celos ayer │ │ • recordato- │ │ • servicios FEP │
│   fin_retiro    │ │   PM/tarde   │ │   rios_pro-  │ │   próximos 7d   │
│   >= hoy        │ │ • alertas IA │ │   gramados   │ │ • ecografía d35 │
│ • Solo alerta   │ │   programada │ │   pendientes │ │ • palpación d60 │
│   si hay casos  │ │   para hoy   │ │   de hoy     │ │                 │
└─────────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬────────┘
          │                │                │                  │
          └────────────────┼────────────────┴──────────────────┘
                           ▼
              Mensaje Telegram Formateado
                           +
          Botonera de Acción Rápida (8 botones)
    [ 🥛 Registrar Leche ]  [ ⏰ Programar Recordatorio ]
    [ 🚨 Alertas Día ]      [ 💊 Medicamentos ]
    [ 🌿 Potreros ]         [ 🐮 Tablero Finca ]
    [ 🔍 Buscar Animal ]    [ 🏠 Menú Principal ]
```

---

## 📷 4. Flujo de Gestión de Fotos de Campo + OCR (Fase 3.2)

1. **Recepción:** El usuario envía una foto (con o sin caption) por Telegram o CLI `--imagen`.
2. **OCR (`src/ocr/ocr_engine.py`):** `OCREngine` intenta extraer texto de la imagen con backend `pytesseract` + `Pillow` (o `easyocr` secundario). Si no hay dependencias, usa fallback `sidecar .txt` (útil en tests) y degradación graceful sin tumbar el bot. `detect_tags()` reconoce `N069`, `N-069`, `JA26`, `O-123`, `47`, `patricia`; `detect_medicamento()` extrae producto, dosis (`ml/kg`), vía (`IM/SC/IV/Oral`), lote y `dias_retiro`.
3. **Identificación:** Si el caption **o** el texto OCR incluye el arete (ej. `vaca 47 ubre inflamada` o arete visible en foto), se asocia automáticamente a la `47`. Si el OCR detecta frasco/medicamento, se dispara también el parser de tratamiento. Feedback contextual: `🔍 OCR detectó tag N069` / `💊 OCR detectó medicamento: Oxitetraciclina`.
4. **Persistencia:** La foto se almacena en `media/` y su metadata (`ruta`, `tag`, `caption`, `ocr_text`, `user_id`, `fecha`) en la tabla `fotos` de SQLite (migración idempotente `ocr_text TEXT` vía `ALTER TABLE`).
5. **Consulta:** 
   - Vía Telegram: `/fotos 47` o `/fotos` envía directamente las imágenes con sus captions, ocr_text y fechas.
   - Vía Lenguaje Natural: `¿hay fotos de la 47?` responde con la cantidad y disponibilidad de fotos registradas.
   - Vía Historial: `/historial 47` incluye el conteo de fotos en la ficha del animal.

### 4.1 Ficha Zootécnica y `/status` (GANADERIA-JA 01-JA)

- **Edad humana** (`formatear_edad_zootecnica` en `src/engine/query_engine.py`): `🎂 Edad: 7 años 3 meses (2.667 días)` / `8 meses (243 días)` / `12 días`, inferida desde `animales.fecha_nacimiento` o `partos.fecha` de la madre (<450d). Visible en header de `/historial`.
- **Estados SG fieles**: `CRÍA MACHO (<8m)`, `LEVANTE (8-18m)`, `TORETE (18-30m)`, `TORO (>30m)` / `CRÍA HEMBRA`, `NOVILLA LEVANTE (12-18m)`, `NOVILLA VIENTRE (≥18m)`, `VACA PARIDA (≤305d)` vs `VACA SECA/ESCOTERA (>305d)`. Partos/días abiertos solo para hembras; partos autorreferenciados (`vaca_id == id_cria`) se excluyen y se bloquean para machos.
- **`/status` filtrado por finca**: `Activos: 338 (GANADERIA-JA 01-JA)` sin `Histórico`; `Potrero + reposo` ignora reposos absurdos `>365d` (ej. JARA 3.232d histórico) y `Potrero + animales` cuenta solo `estado='ACTIVO'` por último traslado; `Actualizado` usa `mtime` de `data/bitacora.db` (fecha del último backup SG) con fallback a `MAX(partos.fecha)`.

### 4.2 Modelo de Datos Extendido & Hardening Concurrente (WAL)

La base de datos SQLite opera con parámetros de concurrencia y confiabilidad para alta carga:
- **Modo WAL (`PRAGMA journal_mode=WAL`):** Permite lecturas y escrituras simultáneas sin bloqueos mutuos entre los procesos del Bot de Telegram, los observadores de backups y las tareas programadas.
- **Tolerancia a Bloqueos (`PRAGMA busy_timeout=10000`):** Espera hasta 10 segundos antes de fallar por contención de base de datos.
- **Integridad Referencial (`PRAGMA foreign_keys=ON`):** Asegura consistencia relacional.

**Tablas Nuevas Integradas:**
- `produccion_leche`: Registra pesajes individuales de leche vinculados a `animal_id`, o registros de producción total diaria del hato en el tanque (`animal_id = NULL`).
- `recordatorios_programados`: Tareas de campo agendadas con `mensaje`, `fecha_programada`, `hora`, `creado_por`, `estado` (`PENDIENTE`/`ENVIADO`) y `creado_en`.

**Índices Compuestos de Rendimiento:**
- `idx_recordatorios_fecha_estado` en `recordatorios_programados(fecha_programada, estado)`
- `idx_animales_tag` en `animales(tag)` y `idx_animales_estado` en `animales(estado)`
- `idx_animales_potrero` en `animales(potrero_id)`
- `idx_partos_vaca_fecha` en `partos(vaca_id, fecha)` e `idx_partos_cria` en `partos(id_cria)`
- `idx_servicios_vaca_fecha` en `servicios(vaca_id, fecha)`
- `idx_celos_vaca_fecha` en `celos(vaca_id, fecha)`
- `idx_tratamientos_animal_fecha` en `tratamientos(animal_id, fecha)`
- `idx_traslados_animal_fecha` en `traslados(animal_id, fecha)`
- `idx_pesajes_animal_fecha` en `pesajes(animal_id, fecha)`
- `idx_movimientos_animal_fecha` en `movimientos(animal_id, fecha)`
- `idx_fotos_animal_tag` en `fotos(animal_id, tag)`

---

## 🤖 5. Arquitectura NLU Híbrida Multi-Agente (Gemini)

El parser implementa dos capas para maximizar velocidad y comprensión de jerga de campo:

| Capa | Motor | Cuándo se activa | Latencia | Dependencias |
|------|:-----:|---|:---:|---|
| **Capa 1** | Regex local (`src/parsers/nlp_engine.py`) | Siempre (intento rápido) | <1 ms | Ninguna |
| **Capa 2** | Multi-agente Gemini (`src/llm/orchestrator.py`) | Texto sin intención conocida, >20 palabras, o múltiples eventos ("y también vacune...") | 800–3000 ms | `GEMINI_API_KEY` configurada |

**Capa 2 — arquitectura multi-agente:**
1. **Router determinista** (`src/llm/router.py`, sin llamada LLM): agrupa los 8 tipos de evento en 3 dominios — `reproduccion` (parto, servicio, celo), `sanidad` (tratamiento, muerte), `manejo` (pesaje, traslado, movimiento) — escaneando los mismos patrones de `nlu.INTENTOS` que usa la Capa 1.
2. Si detecta **1 dominio** → 1 llamada al extractor de ese dominio (`reproduccion.py` / `sanidad.py` / `manejo.py`).
3. Si detecta **≥2 dominios** → llamadas EN PARALELO (`ThreadPoolExecutor`) a cada extractor implicado; resultados combinados preservando el orden de dominios (determinista, no depende de cuál responda primero por red).
4. Si **no detecta ningún dominio** → 1 llamada al **Agente Clasificador** (`src/llm/clasificador.py`), que devuelve los dominios aplicables, y luego se invoca a los extractores correspondientes.
5. Cada extractor de dominio usa `generationConfig.responseSchema` + `responseMimeType: application/json` para garantizar salida JSON conforme al schema (`src/llm/schemas.py`) — ya no hace falta parseo manual de markdown/JSON embebido en texto libre.

- **Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- **Modelo por defecto:** `gemini-2.5-flash` (configurable vía `GEMINI_MODEL`)
- **Variables:** `GEMINI_API_KEY` y `GEMINI_MODEL` en `.env`
- **Validación:** normalización determinista (no LLM) por dominio — sexo_cria/estado_cria/tipo_servicio/am_pm en `reproduccion.py`, retiro leche/carne en `sanidad.py`, peso_kg/cantidad en `manejo.py`.
- **Fallback:** Si no hay API key (o placeholder), timeout, error HTTP/URLError, o fallo de un dominio en la ejecución paralela → retorno silencioso a Capa 1 sin tumbar el bot (en fallo parcial, se conservan los eventos de los dominios que sí respondieron). Logging en `bitacora.llm` sin exponer la key.
- **Integración:** `EventParser.parse()` retorna `ParsedEvent | list[ParsedEvent]`; `Bot.procesar_texto()` itera y persiste cada evento con sus alertas (`src/bot/bot_interface.py`) — sin cambios en este contrato.

```text
Texto "parió la 47 y vacune la 12 con 20ml"
        │
        ▼
  EventParser._should_try_llm()? --sí--> try_multiagent_parse()
        │                                   │
        │                          router.dominios_detectados()
        │                                   │
        │                    {"reproduccion", "sanidad"} (2 dominios)
        │                                   │
        │                     ┌─────────────┴─────────────┐
        │                     ▼ (paralelo)                 ▼ (paralelo)
        │              reproduccion.parse()          sanidad.parse()
        │                  [parto 47]                [tratamiento 12]
        │                     └─────────────┬─────────────┘
        │                                   ▼
        │                        combinar → [parto 47, tratamiento 12]
        │                                   │ fallo/timeout/sin key
        │                                   └──────────► fallback
        ▼
     regex local (capa 1)
```

---

## 🛡️ 6. Matriz de Roles y Permisos (RBAC)

| Comando / Recurso | 👑 OWNER | 🛠️ ADMIN | 📋 TRABAJADOR |
|---|:---:|:---:|:---:|
| `/start`, `/help`, `/menu` | ✅ | ✅ | ✅ |
| `/despacho`, `/matutino`, `/hoy` | ✅ | ✅ | ✅ |
| `/leche <litros>` | ✅ | ✅ | ✅ |
| `/programar <fecha> <hora> <msg>` | ✅ | ✅ | ✅ |
| Registro de 8 eventos (texto) | ✅ | ✅ | ✅ |
| Notas de voz / Fotos de campo | ✅ | ✅ | ✅ |
| Consultas lenguaje natural | ✅ | ✅ | ✅ |
| `/fotos [tag]` | ✅ | ✅ | ✅ |
| `/alertas` | ✅ | ✅ | ❌ |
| `/historial <tag>` | ✅ | ✅ | ❌ |
| `/graficos` | ✅ | ✅ | ❌ |
| `/potreros` | ✅ | ✅ | ❌ |
| `/animales` | ✅ | ✅ | ❌ |
| `/status` | ✅ | ✅ | ❌ |
| `/usuarios` | ✅ | ✅ | ❌ |
| `/reporte [diario\|semanal\|N]` | ✅ | ✅ | ❌ |
| `/exportar [dbf\|csv\|json]` | ✅ | ✅ | ❌ |
| `/importar`, `/confirmar_importar` | ✅ | ✅ | ❌ |
| `/agregar_usuario`, `/quitar_usuario` | ✅ | ❌ | ❌ |
| `/logs` | ✅ | ❌ | ❌ |
