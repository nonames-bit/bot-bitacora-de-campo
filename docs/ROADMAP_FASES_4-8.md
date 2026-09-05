# 🗺️ Hoja de Ruta (Roadmap) — Fases 4 a 8

> **Proyecto:** Bot de Bitácora de Campo Ganadero  
> **Dominio:** [FINCA] Gestión Agropecuaria Integral  
> **Referencia:** Plan de Expansión Zootécnica, Operativa y Multimodal  

---

## 📌 Visión General

Este documento formaliza la hoja de ruta estratégica para las **Fases 4 a 8** del Bot de Bitácora de Campo Ganadero, expandiendo las capacidades actuales (captura NLU, OCR, voz Whisper, consultas zootécnicas y sincronización con Software Ganadero SG) hacia automatización matutina proactiva, control reproductivo y de nitrógeno criogénico, balance bioeconómico forrajero, operación híbrida offline y visión computacional multimodal avanzada.

---

## 🚀 Desglose Detallado por Fase

### 🌅 FASE 4: El Despacho Matutino — ✅ IMPLEMENTADA
> ✅ **Estado:** Implementada en producción. Despacho matutino 05:30 AM (`src/server/telegram_bot.py` + `scripts/enviar_despacho.py`), tabla `recordatorios_programados`, comandos `/programar` y `/leche`, inseminaciones AM-PM por regla AM→tarde / PM→mañana, Voisin día 3 y reposo ≥30d, palpación/eco día 35/60 y alertas de celo perdido integradas en el Despacho.

Automatización proactiva de rutinas operativas diarias enviadas a primera hora para orientar el trabajo en potrero y establo.
- **Briefing 5:30 AM programado:** Generación y despacho automático de resumen de prioridades del día al personal y administración.
- **Inseminaciones AM-PM:** Notificación estricta de vacas con celo detectado (celo en la mañana $\rightarrow$ servicio en la tarde; celo en la tarde $\rightarrow$ servicio en la mañana siguiente).
- **Control de Pastoreo Voisin:** Identificación de potreros en día 3 de ocupación (alerta de cambio inmediato) y potreros en reposo listos para pastoreo ($\ge 30$ días).
- **Programación Reproductiva Clave:** Lista de vacas para palpación o ecografía (día 35 y día 60 post-servicio) y secados proyectados.
- **Alertas de Celos Perdidos y Push:** Detección de vacas con celo perdido ($>50$ días abiertas sin servicio) y alertas push proactivas para animales con $\ge 4$ días de atraso.

---

### 🧬 FASE 5: Reproducción Completa + Termo de Inseminación
Control reproductivo de precisión, gestión del tanque criogénico y genética asistida.
- **[EN PROGRESO] Fase 5.1 — Evento Palpación Directo & Termo Criogénico:**
  - Parser NLU para diagnósticos gestacionales directos (Preñada / Vacía con días de gestación).
  - Tabla `diagnosticos_gestacion` con historial y cálculo dinámico de Tasa de Concepción (%) y Servicios por Concepción (S/C) por reproductor.
  - Gestión completa del Termo Criogénico: tablas `pajuelas_inventario` y `termo_nitrogeno`, descuento automático de pajuelas al registrar servicio IA, alertas de stock crítico y control de recargas periódicas de $N_2$ (21–30 días).
  - Comandos Telegram `/pajuela_add`, `/pajuela_stock`, `/termo`, `/recarga_n2`, `/diagnosticos`, `/kpi_reprod` y teclado dedicado de Reproducción.
- **[PENDIENTE] Fase 5.2 — Consanguinidad 3G & Fertilidad Avanzada:**
  - Simulador de Cruzamiento en 1-Toque: Análisis instantáneo de consanguinidad en 3 generaciones (3G) antes de aplicar el servicio para evitar endogamia.
  - Eventos Reproductivos Críticos: Registro formal de abortos y partos distócicos/difíciles como eventos zootécnicos propios con métricas de impacto.
  - Ranking de Fertilidad por Toro y lectura/OCR de facturas de pajuelas/$N_2$ vía `easyocr`.

---

### 💰 FASE 6: Economía + Balance Forrajero
Integración bioeconómica entre productividad animal, praderas y costos operativos.
- **Costeo de Tratamientos y Suplementación:** Imputación directa de costos de insumos veterinarios, sal mineralizada y suplementos $\rightarrow$ Cálculo dinámico de Costo/kg de carne y Margen $/L$ de leche.
- **Balance Forrajero de Materia Seca (MS):** Estimación en tiempo real de oferta forrajera vs. demanda nutricional ($2.8\%$ del Peso Vivo $\times$ UGG del lote).
- **Capacidad de Carga Dinámica:** Ajuste de UGG/ha correlacionado con datos pluviométricos y pronósticos climáticos (IDEAM / estaciones locales).

---

### 📱 FASE 7: PWA Oficina + Corral Offline
> **Estado 2026-09-05:** A (QR) + D (dashboard 10 vistas) + B-lite (SW offline lectura) ✅ implementadas; pendiente B completa (cola + sync + SOS) y C (RFID/OCR corral). Ver `docs/PLAN_FASE7_PWA.md`.
Herramientas visuales ejecutivas y resiliencia de captura para condiciones de nula conectividad en manga/corral.
- **Dashboard Web Ejecutivo (PWA):** Panel gerencial web responsivo para consulta consolidada, filtros avanzados y visualización de KPIs zootécnicos.
- **Fichas QR en PDF por Lote:** Generación masiva de fichas técnicas en PDF con códigos QR por animal o lote para impresión y lectura rápida.
- **Identificación Rápida en Corral:** Identificación de animales mediante fotografía de arete o lectura de bastón RFID en condiciones de barro y trabajo pesado.
- **Modo Offline Lite:** Cola local de eventos en dispositivo (IndexedDB / SQLite local) con sincronización automática al recuperar cobertura y comando SOS de contingencia.

---

### 👁️ FASE 8: Visión Multimodal Avanzada
Inteligencia artificial visual de última generación y monitoreo satelital de pasturas.
- **Estimación de Condición Corporal (BCS):** Clasificación automática de condición corporal (escala 1.0 a 5.0) a partir de fotografía dorsal/isquion procesada con Gemini Vision.
- **OCR Arete Avanzado:** Algoritmos especializados para lectura de aretes sucios, borrosos, dañados o aretes tipo botón en condiciones difíciles de luz.
- **Monitoreo Satelital de Pasturas (NDVI):** Integración con imágenes Sentinel-2 vía `qgis-mcp` para cálculo de biomasa, índice verde y ajuste dinámico de carga animal.

---

## 📊 Matriz de Esfuerzo vs. Impacto

| Fase / Módulo | Componente Clave | Esfuerzo | Impacto | Justificación Técnica |
|---|---|:---:|:---:|---|
| **Fase 4** | Despacho Matutino 5:30 AM | 🟢 Bajo | 🔴 Alto | Automatiza rutinas de Telegram existentes con cron/scheduler y consultas ya construidas. |
| **Fase 5.1** | Evento Palpación + Termo Pajuelas | 🟡 Medio | 🔴 Alto | Reduce pérdidas por pajuelas extraviadas y previene celos repetidos no atendidos. |
| **Fase 5.2** | Consanguinidad 3G + Ranking Toro | 🟡 Medio | 🟡 Medio | Aprovecha árboles genealógicos ya implementados para evitar depresión consanguínea. |
| **Fase 6.1** | Balance MS (2.8% PV) + Costos/Margen | 🟡 Medio | 🔴 Alto | Brinda visibilidad financiera inmediata por litro/kg y optimiza rotación forrajera. |
| **Fase 6.2** | Integración Pluviométrica IDEAM | 🟡 Medio | 🟡 Medio | Modela estacionalidad de aforos y disponibilidad de pastura en época seca/lluvias. |
| **Fase 7.1** | Fichas QR PDF + Exportación Lotes | 🟢 Bajo | 🟡 Medio | Facilita pesajes y chequeos en corral mediante identificación física inmediata. |
| **Fase 7.3** | Modo Offline Lite (Cola + Sync) | 🔴 Alto | 🔴 Alto | Garantiza continuidad operativa en potreros profundos sin señal celular. |
| **Fase 7.2** | PWA Dashboard Oficina | 🔴 Alto | 🟡 Medio | Centraliza analítica web para propietarios y administradores fuera de Telegram. |
| **Fase 8.1** | BCS Corporal con Gemini Vision | 🟡 Medio | 🟡 Medio | Monitoreo nutricional continuo no invasivo a través de fotos tomadas en el corral. |
| **Fase 8.2** | OCR Arete Sucio/Botón + NDVI Sentinel-2 | 🔴 Alto | 🔴 Alto | Lectura robusta en campo adverso y teledetección satelital de oferta forrajera. |

---

## 📦 Entregables por Fase

```text
FASE 4: El Despacho Matutino
├── src/engine/scheduler.py          # Demonio cron para despacho 5:30 AM
├── src/engine/morning_briefing.py   # Generador del reporte matutino consolidado
└── src/server/bot_alerts.py         # Rutinas de push notifications (celo >50d, atrasos ≥4d)

FASE 5: Reproducción Completa + Termo
├── src/db/migrations/termo_schema.sql  # Tablas para inventario de pajuelas, termo y canastillas
├── src/engine/reproduccion_avanzada.py # Diagnóstico palpación (S/C), tasa concepción y ranking toro
├── src/engine/consanguinidad.py        # Simulador de cruzamiento 3G con alerta de endogamia
└── src/ocr/facturas_termo.py           # Parser OCR de facturas de pajuelas/N2 vía easyocr

FASE 6: Economía + Balance Forrajero
├── src/engine/costos.py             # Motor de costeo $/kg carne y margen $/L leche
├── src/engine/balance_forrajero.py  # Balance MS oferta vs demanda (2.8% PV x UGG)
└── src/integrations/ideam_clima.py  # Conexión y correlación con datos pluviométricos

FASE 7: PWA Oficina + Corral Offline
├── src/pwa/                         # Frontend liviano PWA para oficina y corral
├── src/reports/qr_fichas.py         # Generador de PDFs con códigos QR por animal/lote
├── src/offline/sync_queue.py        # Cola de sincronización local con persistencia SOS
└── src/rfid/reader.py               # Módulo de integración RFID/bastón de lectura

FASE 8: Visión Multimodal
├── src/vision/bcs_analyzer.py       # Clasificador de Condición Corporal (1.0-5.0) con Gemini Vision
├── src/vision/arete_detector.py     # OCR especializado para aretes sucios y tipo botón
└── src/gis/sentinel_ndvi.py         # Integrador NDVI satelital vía qgis-mcp y carga dinámica
```

---

## 🧭 Orden Recomendado de Implementación

Para maximizar el retorno de valor en campo con el menor esfuerzo inicial, la secuencia de desarrollo prioritario es:

$$\mathbf{4 \longrightarrow 5.1 + 5.2 \longrightarrow 6.1 \longrightarrow 7.3 \longrightarrow 8.2}$$

1. **Paso 1 — Fase 4 (Despacho Matutino 5:30 AM):** Despliegue inmediato de las alertas proactivas usando las bases zootécnicas y el bot de Telegram ya existentes.
2. **Paso 2 — Fases 5.1 & 5.2 (Reproducción Completa + Termo + Consanguinidad 3G):** Control de nitrógeno, canastillas de pajuelas, eventos de palpación directa y simulación de cruces.
3. **Paso 3 — Fase 6.1 (Costeo $/kg, Margen $/L y Balance MS 2.8% PV):** Cierre de la brecha bioeconómica para cuantificar la rentabilidad del hato y oferta de pasto.
4. **Paso 4 — Fase 7.3 (Modo Offline Lite con Cola Local + SOS):** Blindaje de la captura de datos en zonas rurales sin cobertura móvil.
5. **Paso 5 — Fase 8.2 (OCR Avanzado en Arete Sucio/Botón + NDVI Sentinel-2):** Incorporación de visión artificial de alta precisión y monitoreo satelital de potreros.
