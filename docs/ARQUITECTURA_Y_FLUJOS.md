# 📐 Arquitectura, Flujos de Trabajo, Estados y Secuencias
## Sistema Bitácora de Campo Ganadera JA (PWA, Bot Telegram & Monitoreo Satelital)

Este documento presenta la especificación visual y técnica completa del sistema ganadero, integrando la arquitectura modular, los flujos operativos en campo, las máquinas de estado biológicas/operativas y los diagramas de secuencia de sincronización e inteligencia artificial.

---

## 🏛️ 1. Diagrama de Arquitectura Global del Sistema

El sistema opera bajo un modelo híbrido **Offline-First en el Edge** (PWA móvil para corral/manga) y **Cloud/VPS Central** (`206.189.188.183`), comunicando servicios zootécnicos, satelitales e inteligencia artificial con una base de datos SQLite en modo WAL (*Write-Ahead Logging*).

```mermaid
flowchart TB
    subgraph CLIENTES["📱 CAPA DE CLIENTES & ACCESO"]
        direction TB
        PWA["📲 PWA Móvil & Escritorio<br/>(Service Worker v62 · IndexedDB Cache<br/>Bottom Nav · Lightbox Pan & Zoom)"]
        TBOT["🤖 Bot de Telegram<br/>(Comandos · Notas de Voz · Fotos<br/>Teclados Inline · Consultas NLP)"]
        ADMIN["💻 Panel Administrativo PWA<br/>(Gestión RBAC · Usuarios · Reportes PDF)"]
    end

    subgraph INGRESS["🛡️ CAPA DE ENTRADA, SEGURIDAD & SESIÓN"]
        direction TB
        WSGI["🌐 Servidor WSGI Waitress<br/>(Puerto 8080 · Multi-hilo)"]
        RBAC["🔐 Control de Acceso RBAC<br/>(users.json · Niveles 1, 2, 3<br/>OWNER · ADMIN · TRABAJADOR)"]
        BOT_APP["⚡ Telegram Application<br/>(Polling Asíncrono PTB)"]
    end

    subgraph ENGINES["⚙️ CAPA DE MOTORES ZOOTÉCNICOS & DE DOMINIO"]
        direction TB
        REPRO["🧬 ReproductiveEngine<br/>• Regla AM-PM Celos<br/>• FEP (+283d) · Eco (+35d) · Palp (+60d)<br/>• Control de Consanguinidad 3G"]
        HEALTH["💉 HealthEngine<br/>• Tiempos de Retiro Carne/Leche<br/>• Alertas de Bloqueo Sanitario<br/>• Control de Tratamientos y Dosis"]
        PASTURE["🌿 PastureEngine<br/>• Leyes de André Voisin (Reposo/Ocupación)<br/>• Balance Forrajero · Aforo kg/m²<br/>• Capacidad de Carga UGG"]
        GROWTH["⚖️ GrowthEngine<br/>• Ganancia Media Diaria (GMD)<br/>• Curvas de Crecimiento · Ajuste 205d"]
        FINANZAS["💰 FinancialEngine<br/>• Libro Ingresos / Egresos / Margen<br/>• Costos Unitarios (L leche / kg carne)"]
        REPORTS["📊 Report & Chart Engine<br/>• ReportLab (PDF A4 · Tarjetas QR)<br/>• Matplotlib (Mapas NDVI · Cajas IEP)"]
    end

    subgraph IA_SATELLITE["🛰️ CAPA DE SERVICIOS EXTERNOS & IA"]
        direction TB
        GEE_SAR["📡 Google Earth Engine: Sentinel-1 SAR<br/>(Radar C-band 10m · Penetra Nubes<br/>Dual-Pol VV/VH · RVI · Humedad Suelo)"]
        GEE_OPT["🛰️ Google Earth Engine: Sentinel-2 L2A<br/>(Óptico Multiespectral 10m · NDVI<br/>Máscara QA60 Nubosidad)"]
        CHIRPS["🌧️ GEE: CHIRPS Rainfall<br/>(Climatología 30 años · Índice Sequía SPI)"]
        GEMINI["🧠 Google Gemini Vision 2.5<br/>(OCR Multimodal · Facturas · Recibos Leche)"]
        OPEN_METEO["🌤️ Open-Meteo API<br/>(Pronóstico 7 días · Recomendaciones)"]
    end

    subgraph PERSISTENCIA["💾 CAPA DE PERSISTENCIA & STORAGE"]
        direction TB
        SQLITE[("🗄️ SQLite 3 — Modo WAL<br/>data/bitacora.db<br/>(Concurrencia PWA + Bot sin bloqueos)")]
        MEDIA["📁 Almacenamiento Local media/<br/>(Fotos de Ganado · Recibos · Evidencias)"]
        SG_BRIDGE["🔄 DBF Bridge (Software Ganadero)<br/>(Importación / Exportación Idempotente ZIP)"]
    end

    %% Conexiones Clientes -> Entrada
    PWA -->|HTTPS / REST API / Sync Offline| WSGI
    ADMIN -->|HTTPS / Cookies de Sesión| WSGI
    TBOT -->|Telegram MTProto| BOT_APP

    %% Entrada -> Seguridad & Motores
    WSGI --> RBAC
    RBAC --> ENGINES
    BOT_APP --> ENGINES

    %% Motores -> IA & Satélites
    ENGINES --> GEE_SAR
    ENGINES --> GEE_OPT
    ENGINES --> CHIRPS
    ENGINES --> GEMINI
    ENGINES --> OPEN_METEO

    %% Motores -> Persistencia
    ENGINES --> SQLITE
    ENGINES --> MEDIA
    ENGINES --> SG_BRIDGE
```

---

## 🔄 2. Flujos de Trabajo en Campo (Workflows)

### 2.1 Flujo de Pesaje y Manejo en Corral ("Modo Manga Offline")
Permite registrar pesajes individuales o por lotes directamente en el corral de manejo, calculando la Ganancia Media Diaria (GMD) en tiempo real sin requerir conectividad a Internet.

```mermaid
flowchart TD
    A["🐮 Vaquero en Manga con Celular/Tablet"] --> B{"¿Hay Conectividad 4G/Wi-Fi en el Corral?"}
    B -- "NO (Común en potrero)" --> C["📱 Modo Manga Offline (PWA)<br/>Lectura de arete visual o RFID"]
    B -- "SÍ" --> D["🌐 Conexión en Línea Directa"]

    C --> E["Ingreso de Arete (Tag) + Peso (kg) + Condición Corporal"]
    D --> E

    E --> F["⚡ Motor Local de Pesaje (app.js)"]
    F --> G["Cálculo instantáneo GMD contra pesaje previo en caché local"]
    G --> H{"¿Guardado Offline o Online?"}

    H -- "Offline" --> I["💾 Almacena en IndexedDB (cola: eventos_pendientes)<br/>Chip visual: '💾 Guardado Offline'"]
    H -- "Online" --> J["🚀 Envío directo POST /api/manga/pesaje"]

    I --> K["Vaquero termina sesión de manga"]
    K --> L["Al llegar a casa de campo o detectar Wi-Fi"]
    L --> M["🔄 Sincronizador Automático (sw.js / app.js)"]
    M --> N["POST /api/sync con lote de eventos"]
    N --> O["🗄️ Database.registrar_pesaje() en SQLite WAL"]
    J --> O
    O --> P["✅ Actualiza historial animal, GMD y peso ajustado 205 días"]
```

---

### 2.2 Flujo de Digitalización de Recibos y Gastos con IA Multimodal
Transforma recibos manuales de leche y facturas de insumos en registros contables automáticos, asociando la imagen como respaldo auditable.

```mermaid
flowchart TD
    A["📸 Foto tomada en campo / recibo en papel"] --> B["Carga en PWA: Captura Leche o Finanzas"]
    B --> C["Pre-compresión de imagen en cliente (Canvas WebP/JPEG)"]
    C --> D["POST /api/leche/analizar-recibo o /api/finanzas/analizar-factura"]
    
    D --> E["🧠 Motor Gemini Vision (Prompt Zootécnico Especializado)"]
    E --> F{"¿Tipo de Documento Detectado?"}

    F -- "Planilla / Recibo de Leche" --> G["Extrae: Quincena, Litros día a día,<br/>Total Litros, Precio/Litro, Bonificaciones y Neto"]
    F -- "Factura / Recibo de Gasto" --> H["Extrae: Categoría (Insumo, Sanidad, Flete),<br/>Proveedor, Monto Total, Concepto y Fecha"]

    G --> I["Pre-llenado interactivo en formulario PWA"]
    H --> I

    I --> J["👁️ Verificación visual del usuario<br/>(Ajusta o confirma con 1 clic)"]
    J --> K["Botón: 'Guardar Quincena' o 'Registrar Gasto'"]

    K --> L["💾 Almacenamiento en SQLite: produccion_leche + finanzas_movimientos"]
    K --> M["📁 Guarda foto física en media/fotos/ como evidencia vinculada"]
    L --> N["📊 Actualiza KPI financiero: margen de utilidad y costo/litro"]
```

---

### 2.3 Flujo de Monitoreo Satelital Todo-Clima (Multi-Sensor SAR + Óptico)
Garantiza la supervisión continua del forraje los 365 días del año, superando la limitación de nubosidad tropical mediante microondas de radar.

```mermaid
flowchart TD
    A["🛰️ Solicitud de Monitoreo Satelital<br/>(Automático Semanal o Botón PWA)"] --> B["Carga polígonos potreros (geom_wkt_4326)"]
    B --> C{"Modo de Consulta"}

    C -- "Modo 'auto' (Por Defecto)" --> D["Consulta Sentinel-2 L2A en Earth Engine"]
    C -- "Modo 'radar' / 's1'" --> E["Consulta Directa Sentinel-1 SAR GRD"]

    D --> F{"¿Cielo Despejado?<br/>(Nubosidad < 40% en potreros)"}
    
    F -- "SÍ (Verano / Despejado)" --> G["Calcula NDVI Óptico Multiespectral (B8-B4)/(B8+B4)"]
    G --> H["Fuente: Sentinel-2 L2A (Óptico)"]

    F -- "NO (Invierno / Nublado)" --> I["🚨 Detección de nubes: Conmutación a Radar SAR"]
    I --> E

    E --> J["Radar Microondas C-band (10m) atraviesa nubes y lluvia"]
    J --> K["Cálculo Backscatter Dual-Pol (VV / VH en dB y lineal)"]
    K --> L["Índice Dual RVI = 4*VH / (VV + VH)<br/>Proxy NDVI_radar = clip(0.20 + 0.65*RVI)<br/>Humedad Suelo/Canopy desde respuesta dieléctrica VV"]
    L --> M["Fuente: Sentinel-1 SAR GRD (Radar Todo Clima)"]

    H --> N["Estimación Zootécnica de Rendimiento:<br/>• Aforo (kg MV/m²)<br/>• Biomasa (kg MS/ha)"]
    M --> N

    N --> O["💾 Database.registrar_lectura_ndvi()"]
    O --> P["Purga caché de mapas: _pwa_cache_mapa_potreros.png"]
    P --> Q["Refresco automático en PWA: Mapa coloreado por vigor forrajero"]
```

---

## 🚦 3. Máquinas de Estados (State Machines)

### 3.1 Ciclo de Vida del Animal en el Hato
Control estricto de inventario según la regla fundamental: **toda consulta de hato activo debe filtrar estrictamente por `estado = 'ACTIVO'`**.

```mermaid
stateDiagram-v2
    [*] --> ACTIVO: Nacimiento registrado en parto / Compra ingresada
    
    state ACTIVO {
        [*] --> EnPotrero: Asignado a potrero con geometría
        EnPotrero --> EnTraslado: Orden de traslado
        EnTraslado --> EnPotrero: Entrada al nuevo potrero
        --
        [*] --> Sano: Estado sanitario normal
        Sano --> EnTratamiento: Aplicación de fármaco
        EnTratamiento --> EnRetiro: Periodo de carencia leche/carne
        EnRetiro --> Sano: Vencimiento de periodo de retiro
    }

    ACTIVO --> VENDIDO: Registro de Venta (Fecha, Comprador, Monto)
    ACTIVO --> MUERTO: Registro de Muerte (Fecha, Causa, Diagnóstico)
    ACTIVO --> DESCARTADO: Descarte zootécnico / Salida administrativa

    VENDIDO --> [*]: Conserva historial genealógico / Sale de inventario activo
    MUERTO --> [*]: Conserva historial genealógico / Sale de inventario activo
    DESCARTADO --> [*]: Sale de inventario activo
```

---

### 3.2 Ciclo Reproductivo de la Hembra Bovina
Gobierna la fertilidad del rebaño mediante la regla zootécnica AM-PM y el cronograma veterinario de confirmación de preñez.

```mermaid
stateDiagram-v2
    [*] --> VACIA: Hembra apta para reproducción / Post-parto voluntario

    VACIA --> EN_CELO: Detección visual de celo (mañana o tarde)
    
    note right of EN_CELO
        Regla AM-PM:
        • Celo AM -> Inseminar PM
        • Celo PM -> Inseminar AM siguiente
    end note

    EN_CELO --> SERVIDA: Inseminación Artificial (IA) o Monta Natural (MN)
    
    SERVIDA --> ECOGRAFIA_PENDIENTE: Día +35 post-servicio
    
    ECOGRAFIA_PENDIENTE --> SERVIDA: Reconfirma evolución
    ECOGRAFIA_PENDIENTE --> VACIA: Diagnóstico NEGATIVO (Vuelve al ciclo)
    ECOGRAFIA_PENDIENTE --> GESTANTE: Diagnóstico POSITIVO en ecografía

    SERVIDA --> PALPACION_PENDIENTE: Día +60 post-servicio (Confirmación física)
    PALPACION_PENDIENTE --> GESTANTE: Confirmación positiva
    PALPACION_PENDIENTE --> VACIA: Diagnóstico NEGATIVO

    GESTANTE --> SECA_PRENADA: Día +223 (FEP - 60 días: Secado obligatorio)
    
    note right of SECA_PRENADA
        Descanso mamario y preparación
        nutricional para el parto (+283d)
    end note

    SECA_PRENADA --> PARTO_PARIDA: Día +283 (Parto de cría macho/hembra)
    
    PARTO_PARIDA --> LACTANDO: Producción láctea + amamantamiento
    LACTANDO --> VACIA: Cumplimiento de Periodo de Espera Voluntario (PEV)
```

---

### 3.3 Semáforo de Ocupación y Rotación Voisin de Potreros
Implementa las leyes universales del pastoreo racional de André Voisin (ley del reposo y ley de la ocupación).

```mermaid
stateDiagram-v2
    [*] --> EN_REPOSO: Ganado retirado / Potrero vacío

    state EN_REPOSO {
        [*] --> Recuperando: Días 1 a 20
        Recuperando --> PuntoOptimoCorte: Días 21 a 35 (Llamarada de crecimiento Voisin)
        PuntoOptimoCorte --> PastoPasado: Días 36+ (Lignificación / Pérdida de proteína)
    }

    EN_REPOSO --> OCUPADO_OPTIMO: Entrada de lote de animales (Día 1 a 3)
    
    note left of OCUPADO_OPTIMO
        Semáforo: 🟢 Verde
        Ocupación ideal: 1 a 3 días máx.
        Sin comer rebrote tierno.
    end note

    OCUPADO_OPTIMO --> ROTAR_PRONTO: Días 4 a 6 en el potrero
    
    note right of ROTAR_PRONTO
        Semáforo: 🟡 Amarillo
        Alerta: El ganado empieza a dañar
        el rebrote nuevo.
    end note

    ROTAR_PRONTO --> SOBREOCUPADO: Días 7 o más sin rotación
    
    note right of SOBREOCUPADO
        Semáforo: 🔴 Rojo
        Peligro: Pérdida de biomasa,
        compactación y degradación.
    end note

    OCUPADO_OPTIMO --> EN_REPOSO: Salida de animales (Registro fecha_salida)
    ROTAR_PRONTO --> EN_REPOSO: Salida de animales (Registro fecha_salida)
    SOBREOCUPADO --> EN_REPOSO: Salida urgente de animales
```

---

## ⏱️ 4. Diagramas de Secuencia (Sequence Diagrams)

### 4.1 Secuencia de Sincronización Offline Bidireccional (PWA ⇄ VPS)
Muestra cómo los datos capturados en mangas sin señal viajan con seguridad hasta la base de datos central sin pérdida de información.

```mermaid
sequenceDiagram
    autonumber
    actor Vaquero as 🤠 Vaquero en Corral
    participant UI as 📱 PWA UI (Manga)
    participant IDB as 🗃️ IndexedDB (Local)
    participant SW as ⚙️ Service Worker (v62)
    participant API as 🌐 Waitress / Flask (/api/sync)
    participant DB as 🗄️ SQLite 3 (WAL)

    Vaquero->>UI: Registra pesaje: Tag V097, 460 kg
    UI->>UI: Verifica navigator.onLine (False)
    UI->>IDB: encolarOffline("pesaje", {tag: "V097", peso: 460})
    IDB-->>UI: Guardado en cola local (ID: evt_101)
    UI-->>Vaquero: Feedback visual: "💾 Guardado Offline (en cola)"

    Note over Vaquero,UI: El vaquero termina la jornada y se conecta a Wi-Fi

    SW->>SW: Detecta evento "online" / reconexión de red
    SW->>UI: Notifica canal de sincronización listo
    UI->>IDB: obtenerEventosPendientes()
    IDB-->>UI: Retorna [evt_101, evt_102, ...]
    
    UI->>API: POST /api/sync {eventos: [...], token_sesion}
    API->>API: Valida permisos RBAC y firma HMAC
    
    loop Por cada evento en lote
        API->>DB: Database.registrar_pesaje(tag="V097", peso=460)
        DB-->>API: Retorna id_pesaje y cálculo GMD
    end
    
    API-->>UI: HTTP 200 {ok: true, sincronizados: 2, errores: []}
    UI->>IDB: eliminarEventosConfirmados(["evt_101", "evt_102"])
    UI-->>Vaquero: Notificación en pantalla: "✅ 2 eventos sincronizados con éxito"
```

---

### 4.2 Secuencia de Digitalización de Facturas / Recibos con Gemini Vision
Flujo paso a paso para la extracción multimodal asistida por inteligencia artificial con supervisión humana.

```mermaid
sequenceDiagram
    autonumber
    actor Usuario as 👤 Administrador / Dueño
    participant PWA as 📱 Interfaz PWA (Finanzas)
    participant App as 🌐 Backend Flask (/api/finanzas/analizar-factura)
    participant Gemini as 🧠 Google Gemini 2.5 Vision API
    participant Storage as 📁 Disco VPS (media/fotos/)
    participant DB as 🗄️ SQLite (finanzas_movimientos)

    Usuario->>PWA: Toca botón "Digitalizar Factura / Recibo con IA"
    Usuario->>PWA: Selecciona foto o captura con la cámara del celular
    PWA->>PWA: Comprime imagen a WebP (máx 1600px, calidad 0.85)
    
    PWA->>App: POST /api/finanzas/analizar-factura {foto_base64: "..."}
    App->>Storage: Guarda copia física temporal en media/fotos/recibos/
    
    App->>Gemini: Solicitud multimodal (System Prompt Contable + Imagen Bytes)
    Note over App,Gemini: Analiza tabla de items, proveedor, IVA, total y fecha
    Gemini-->>App: JSON Estructurado {categoria: "INSUMO", monto: 450000, proveedor: "Agrovida", fecha: "2026-09-08"}
    
    App-->>PWA: Retorna datos extraídos + ruta de foto guardada
    PWA-->>Usuario: Despliega modal con campos autocompletados y foto en pantalla
    
    Usuario->>PWA: Revisa y presiona "Confirmar Gasto"
    PWA->>App: POST /api/finanzas {tipo: "EGRESO", monto: 450000, categoria: "INSUMO", ...}
    App->>DB: Database.registrar_movimiento_financiero(...)
    DB-->>App: Confirmado ID #84
    App-->>PWA: HTTP 200 {ok: true}
    PWA-->>Usuario: Muestra en libro contable y actualiza KPI de utilidad
```

---

### 4.3 Secuencia del Monitoreo Satelital Radar SAR Sentinel-1
Detalla la invocación a Google Earth Engine desde el botón de la PWA para penetrar nubes y actualizar el mapa de potreros.

```mermaid
sequenceDiagram
    autonumber
    actor Usuario as 👤 Usuario en PWA (Pasturas)
    participant PWA as 📱 PWA UI (Botón Radar SAR)
    participant App as 🌐 Backend Flask (/api/satelite/actualizar)
    participant GIS as 🛰️ Módulo GIS (earth_engine_ndvi.py / earth_engine_sar.py)
    participant GEE as ☁️ Google Earth Engine (COPERNICUS/S1_GRD)
    participant DB as 🗄️ SQLite 3 (monitoreo_satelital_ndvi)
    participant Cache as 🖼️ Caché de Gráficos (_pwa_cache_*)

    Usuario->>PWA: Clic en botón "📡 Radar SAR (Todo Clima)"
    PWA->>PWA: Muestra recuadro de estado con animación de satélite
    PWA->>App: POST /api/satelite/actualizar {modo: "radar"}
    
    App->>DB: Obtiene 20 potreros con geometría WKT (geom_wkt_4326)
    DB-->>App: Retorna lista de polígonos
    
    App->>GIS: actualizar_lecturas_reales(potreros, modo="radar")
    GIS->>GEE: Autentica con Service Account (GEE_SERVICE_ACCOUNT_EMAIL)
    GIS->>GEE: Colección S1_GRD: Polarización dual VV/VH, modo IW, órbita descendente
    
    loop Por cada uno de los 20 potreros
        GEE-->>GIS: Retorna backscatter medio VV_dB y VH_dB
        GIS->>GIS: Convierte a lineal: σ° = 10^(dB/10)
        GIS->>GIS: Dual-Pol RVI = 4*VH / (VV + VH)
        GIS->>GIS: Proxy NDVI = clip(0.20 + 0.65*RVI, 0.15, 0.85)
        GIS->>GIS: Humedad % = clip((VV_dB - (-18)) / ((-7) - (-18)) * 100)
    end
    
    GIS-->>App: 20 lecturas consolidadas (NDVI, biomasa, aforo, humedad)
    
    loop Por cada potrero procesado
        App->>DB: Database.registrar_lectura_ndvi(fuente="Sentinel-1 SAR GRD...")
    end
    
    App->>Cache: Elimina archivos _pwa_cache_mapa_potreros.png
    App-->>PWA: HTTP 200 {ok: true, actualizados: 20, sar: 20, modo: "radar"}
    
    PWA->>PWA: Oculta spinner y muestra "✅ 20 potreros actualizados vía Radar SAR"
    PWA->>App: Solicita /api/grafico/mapa_potreros
    App->>App: Regenera mapa en alta resolución con nuevos valores de vigor
    App-->>PWA: Renderiza nuevo mapa coloreado y actualiza tabla satelital
```

---

### 4.4 Secuencia del Despacho Matutino Diario (05:30 AM)
Orquesta el envío proactivo del informe diario matutino al canal de Telegram del propietario y personal de campo.

```mermaid
sequenceDiagram
    autonumber
    participant Cron as ⏰ Systemd Timer (05:30 AM)
    participant Script as 📜 scripts/enviar_despacho.py
    participant Engine as ⚙️ Orchestrator / Despacho
    participant DB as 🗄️ SQLite 3 (Database)
    participant Meteo as 🌤️ Open-Meteo API
    participant Bot as 🤖 Telegram Bot API
    actor Personal as 📱 Mayordomo & Dueño (Telegram)

    Cron->>Script: Disparo automático programado
    Script->>Engine: formatear_despacho_matutino(db)
    
    Engine->>DB: Consulta 1: Partos próximos (FEP en ventana 7 días)
    Engine->>DB: Consulta 2: Vacas en periodo de retiro (leche y carne bloqueadas)
    Engine->>DB: Consulta 3: Potreros en sobreocupación (Voisin: ocupación > 6 días)
    Engine->>DB: Consulta 4: Nivel del termo de nitrógeno y recargas próximas
    
    Engine->>Meteo: Pronóstico del día (T° máx/mín, probabilidad lluvia mm)
    Meteo-->>Engine: Retorna pronóstico meteorológico
    
    Engine->>Engine: Compone mensaje con formato Markdown enriquecido y semáforos
    Engine-->>Script: Texto consolidado del Despacho Matutino
    
    Script->>Bot: send_message(chat_id=OWNER_CHAT_ID, text=despacho)
    Script->>Bot: send_message(chat_id=GRUPO_FINCA, text=despacho)
    Bot-->>Personal: Entrega mensaje al amanecer antes del inicio de labores
```

---

## 📋 Resumen de Componentes Clave

| Componente | Archivo / Ubicación | Responsabilidad Principal |
| :--- | :--- | :--- |
| **PWA Web App** | [`src/pwa/app.py`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/pwa/app.py) | Servidor WSGI Flask, API REST, autenticación RBAC y renderizado. |
| **PWA Client JS** | [`src/pwa/static/app.js`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/pwa/static/app.js) | Lógica de vistas, IndexedDB offline, visor Pan/Zoom y sincro de eventos. |
| **Service Worker** | [`src/pwa/static/sw.js`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/pwa/static/sw.js) | Caché de activos estáticos, interceptor offline e instalación en móviles. |
| **Telegram Bot** | [`src/server/telegram_bot.py`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/server/telegram_bot.py) | Interfaz de mensajería, comandos de audio, fotos y despacho diario. |
| **Base de Datos** | [`src/db/database.py`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/db/database.py) | Capa de persistencia SQLite 3 en modo WAL, reglas de hato activo. |
| **Sentinel-1 SAR** | [`src/gis/earth_engine_sar.py`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/gis/earth_engine_sar.py) | Monitoreo radar microondas C-band todo clima, biomasa RVI y humedad. |
| **Sentinel-2 NDVI** | [`src/gis/earth_engine_ndvi.py`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/gis/earth_engine_ndvi.py) | Monitoreo multiespectral óptico y fallback automático a SAR en nubes. |
| **IA Multimodal** | [`src/vision/recibo_leche_parser.py`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/vision/recibo_leche_parser.py) | Digitalización inteligente con Google Gemini Vision para recibos y facturas. |
| **Generador Mapas** | [`src/engine/charts.py`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/engine/charts.py) | Cartografía vectorial de potreros reales con proyección esférica corregida. |
| **Reportes PDF** | [`src/reports/pdf_report.py`](file:///C:/Users/Owner/Documents/projects/finca/2026-08-24-bot-bitacora-de-campo/src/reports/pdf_report.py) | Generación ejecutiva ReportLab de fichas técnicas y reportes generales. |


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
| `/exportar [dbf\|csv\|json]` (solo OWNER, avisa a los demás OWNER) | ✅ | ❌ | ❌ |
| `/importar`, `/confirmar_importar` | ✅ | ✅ | ❌ |
| `/agregar_usuario`, `/quitar_usuario` | ✅ | ❌ | ❌ |
| `/logs` | ✅ | ❌ | ❌ |
