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
│  │                                 Database (SQLite)                                         │  │
│  │  Tablas: animales · partos · celos · servicios · tratamientos · pesajes · traslados       │  │
│  │          muertes · movimientos · potreros · alertas · fotos                               │  │
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
        └─► Movimiento ───► Compra/Venta/Entrada ───► Alta/Baja en inventario
```

---

## 📷 4. Flujo de Gestión de Fotos de Campo

1. **Recepción:** El usuario envía una foto (con o sin caption).
2. **Identificación:** Si el caption incluye el arete (ej. `vaca 47 ubre inflamada`), se asocia automáticamente a la `47`. Si contiene un evento zootécnico, también se dispara el parser del evento.
3. **Persistencia:** La foto se almacena en `media/` y su metadata en la tabla `fotos` de SQLite.
4. **Consulta:** 
   - Vía Telegram: `/fotos 47` o `/fotos` envía directamente las imágenes con sus captions y fechas.
   - Vía Lenguaje Natural: `¿hay fotos de la 47?` responde con la cantidad y disponibilidad de fotos registradas.
   - Vía Historial: `/historial 47` incluye el conteo de fotos en la ficha del animal.

---

## 🛡️ 5. Matriz de Roles y Permisos (RBAC)

| Comando / Recurso | 👑 OWNER | 🛠️ ADMIN | 📋 TRABAJADOR |
|---|:---:|:---:|:---:|
| `/start`, `/help` | ✅ | ✅ | ✅ |
| Registro de 8 eventos (texto) | ✅ | ✅ | ✅ |
| Notas de voz / Fotos de campo | ✅ | ✅ | ✅ |
| Consultas lenguaje natural | ✅ | ✅ | ✅ |
| `/fotos [tag]` | ✅ | ✅ | ✅ |
| `/alertas` | ✅ | ✅ | ❌ |
| `/historial <tag>` | ✅ | ✅ | ❌ |
| `/potreros` | ✅ | ✅ | ❌ |
| `/animales` | ✅ | ✅ | ❌ |
| `/status` | ✅ | ✅ | ❌ |
| `/usuarios` | ✅ | ✅ | ❌ |
| `/reporte [diario\|semanal\|N]` | ✅ | ✅ | ❌ |
| `/exportar [dbf\|csv\|json]` | ✅ | ✅ | ❌ |
| `/importar`, `/confirmar_importar` | ✅ | ✅ | ❌ |
| `/agregar_usuario`, `/quitar_usuario` | ✅ | ❌ | ❌ |
| `/logs` | ✅ | ❌ | ❌ |
