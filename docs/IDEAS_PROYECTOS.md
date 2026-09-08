# 💡 Ideas de Proyectos — Bitácora de Campo Ganadería JA

> **Propósito:** Banco de ideas para futuros proyectos, mejoras y módulos del sistema.
> Cada idea incluye descripción, valor para la finca, esfuerzo estimado y dependencias.
> Este documento es vivo: se agregan ideas, se marcan las aprobadas y se archivan las completadas.
>
> **Creado:** 2026-09-07
> **Última actualización:** 2026-09-07

---

## 📋 Leyenda

| Campo | Valores |
|---|---|
| **Estado** | 💭 Idea · ✅ Aprobada · 🚧 En progreso · ✔️ Completada · ❌ Descartada |
| **Impacto** | 🟢 Alto / 🟡 Medio / 🔵 Complementario |
| **Costo** | 💲 Solo software (tiempo de desarrollo) · 💲💲 Hardware moderado · 💲💲💲 Hardware/servicio mayor |
| **Esfuerzo** | S (1-3 días) · M (1-2 semanas) · L (1+ mes) |

---

## 🌿 Monitoreo de Potreros & Clima

### 1. Pronóstico del clima integrado al Despacho Matutino
- **Estado:** ✔️ Completada (2026-09-07) — bot y PWA
- **Impacto:** 🟢 Alto — decisiones diarias informadas (fumigar, hacer heno, mover ganado)
- **Costo:** 💲 (API gratuita)
- **Esfuerzo:** S
- **Descripción:** Integrar una API gratuita de pronóstico (Open-Meteo o NASA POWER, sin costo ni clave compleja) con lluvia, temperatura y humedad a 7 días. El despacho de las 5:30 AM incluiría recomendaciones prácticas: *"🌧️ Lluvia probable mañana → no fumigar hoy"* o *"☀️ 4 días secos seguidos → ventana buena para heno"*.
- **Dependencias:** Ninguna. APIs: [Open-Meteo](https://open-meteo.com/) (gratis, sin API key), NASA POWER.
- **Notas:** Implementado en `src/engine/pronostico.py` (Open-Meteo, caché 6h) e integrado al Despacho Matutino del bot. Agregado también a la vista Pasturas de la PWA (tarjetas de 7 días + recomendaciones), que no lo tenía.

### 2. Alerta temprana de sequía (SPI)
- **Estado:** ✔️ Completada (2026-09-07) — solo PWA (a pedido del usuario, sin alerta por Telegram)
- **Impacto:** 🟢 Alto — anticipar crisis forrajera antes de que el potrero colapse
- **Costo:** 💲 (reusa datos CHIRPS ya disponibles)
- **Esfuerzo:** S-M
- **Descripción:** Calcular el Índice de Precipitación Estandarizada (SPI) a 30/60/90 días con los datos CHIRPS que ya se descargan semanalmente. Si entra en rango de sequía, alerta automática para ajustar carga animal preventivamente.
- **Dependencias:** `scripts/actualizar_lluvia_satelital.py` ya corriendo (CHIRPS semanal).
- **Notas:** SPI real (McKee et al. 1993), no un proxy simplificado: `src/gis/earth_engine_lluvia.climatologia_historica_chirps` descarga ~30 años de CHIRPS por ventana (cacheados en `climatologia_lluvia_chirps`, refresco anual) y `src/engine/spi.calcular_spi` ajusta una distribución gamma para ubicar la lluvia actual contra ese histórico. El job semanal guarda el resultado en `monitoreo_spi_sequia`; se muestra en Pasturas (PWA) con semáforo por severidad, sin notificación al bot.

### 3. Balance forrajero predictivo a 30 días
- **Estado:** 💭 Idea
- **Impacto:** 🟢 Alto — responde la pregunta clave: *"¿me alcanza el pasto para el mes?"*
- **Costo:** 💲
- **Esfuerzo:** M
- **Descripción:** Combinar NDVI actual + lluvia acumulada últimos 30 días + pronóstico climático para proyectar kg MS/ha disponibles a 30 días. Integra con el balance forrajero estacional existente (Fase 6.2).
- **Dependencias:** NDVI (ya activo cada 3 días), CHIRPS lluvia (ya activo), idea #1 (pronóstico).

### 4. Recomendación automática de rotación de potreros
- **Estado:** 💭 Idea
- **Impacto:** 🟢 Alto — convierte datos en decisiones accionables
- **Costo:** 💲
- **Esfuerzo:** M
- **Descripción:** Hoy `/ocupacion` muestra qué potreros están listos; el siguiente nivel es que el bot **proponga activamente**: *"Mover lote LECHERAS → COQUERA (biomasa 2.926 kg/ha, 28 días de reposo)"*, cruzando biomasa NDVI + días de reposo Voisin + tamaño/demanda del lote.
- **Dependencias:** NDVI cada 3 días, tabla de traslados, rotación Voisin (todo existente).

### 5. Estación meteorológica propia en la finca
- **Estado:** 💭 Idea
- **Impacto:** 🟢 Alto — clima **real** de la finca, no del satélite (CHIRPS tiene resolución de 5.5 km y no distingue el microclima local)
- **Costo:** 💲💲 (~$200-500 USD)
- **Esfuerzo:** M (compra, instalación, integración API)
- **Descripción:** Estación tipo Ecowitt o Davis con panel solar: lluvia real, temperatura, humedad, viento. Datos cada 5 minutos, histórico propio multi-año. Se integra al bot para reemplazar/complementar el registro manual de `/lluvia`.
- **Hardware sugerido:** Ecowitt GW2000 + pluviómetro WH40, o Davis Vantage Vue.
- **Notas:** La mejor inversión física de la lista. El pluviómetro manual sigue siendo respaldo.

### 6. Sentinel-1 (radar SAR) — monitoreo que funciona con nubes
- **Estado:** 💭 Idea
- **Impacto:** 🟢 Alto — resuelve de raíz el problema real: en época de lluvias el NDVI óptico se queda semanas sin imagen despejada
- **Costo:** 💲 (gratis vía Google Earth Engine, que ya se usa)
- **Esfuerzo:** M
- **Descripción:** El radar SAR de Sentinel-1 penetra las nubes → biomasa/humedad de suelo estimada **sin importar el cielo**. Complementa Sentinel-2: cuando no hay imagen óptica, el radar da continuidad temporal.
- **Dependencias:** Misma infraestructura Earth Engine actual (`src/gis/earth_engine_ndvi.py`).

### 7. Sensores de humedad de suelo
- **Estado:** 💭 Idea
- **Impacto:** 🟡 Medio — precisión sobre el momento real de recuperación del suelo
- **Costo:** 💲💲 (~$30-80 USD por sensor, 3-4 sensores en potreros clave)
- **Esfuerzo:** M
- **Descripción:** Sensores capacitivos en potreros clave para saber cuándo el suelo está listo para recuperación forrajera — más preciso que solo contar días de reposo.

### 8. Comparación histórica NDVI interanual
- **Estado:** 💭 Idea
- **Impacto:** 🟡 Medio — contexto para decisiones de suplementación
- **Costo:** 💲
- **Esfuerzo:** S-M
- **Descripción:** *"Este septiembre vs. septiembre de años anteriores"* → detecta si la finca va mejor o peor que el promedio climático. Gráfico de bandas percentiles (mínimo-promedio-máximo histórico) con el año actual superpuesto.
- **Dependencias:** Acumular histórico NDVI (el job cada 3 días lo construye con el tiempo).

### 9. Foto fija del potrero analizada por IA (índice ExG)
- **Estado:** 💭 Idea
- **Impacto:** 🟡 Medio — verdor diario sin satélite
- **Costo:** 💲💲 (cámara barata en poste, o el celular del mayordomo)
- **Esfuerzo:** M
- **Descripción:** Cámara fija tomando fotos diarias del potrero → análisis de índice de verdor (ExG — Excess Green Index) procesado localmente o con Gemini Vision. Complementa el NDVI con frecuencia diaria. Bonus: el mismo setup sirve para la Fase 8.1 (condición corporal automática BCS).

### 10. Monitores de voltaje en cercas eléctricas
- **Estado:** 💭 Idea
- **Impacto:** 🟡 Medio — evita fugas de ganado
- **Costo:** 💲💲 (~$50 USD por monitor)
- **Esfuerzo:** S-M
- **Descripción:** Monitor de voltaje en la cerca → alerta al Telegram si el voltaje cae (cerca rota, vegetación descargando, etc.).

### 11. Sensores de nivel en bebederos/tanques
- **Estado:** 💭 Idea
- **Impacto:** 🟡 Medio — nunca más un bebedero seco sin enterarse
- **Costo:** 💲💲 (~$20 USD por sensor ultrasónico)
- **Esfuerzo:** S-M
- **Descripción:** Sensor ultrasónico sobre el espejo de agua → alerta *"bebedero de OLEGARIO I sin agua"* al Telegram.

### 12. Collares GPS para el ganado
- **Estado:** 💭 Idea
- **Impacto:** 🟡 Medio — valida la rotación con datos reales de pastoreo
- **Costo:** 💲💲💲 (~$30-100 USD por animal)
- **Esfuerzo:** L
- **Descripción:** Collares GPS en vacas líderes → mapa real de dónde pastorean, tiempo por zona del potrero, detección de celo por actividad. Valida si la rotación planeada se cumple en la práctica.

### 13. Dron mensual para mapas de biomasa
- **Estado:** 💭 Idea
- **Impacto:** 🟡 Medio — resolución de centímetros vs. 10 m del satélite
- **Costo:** 💲💲💲 (dron con cámara multiespectral o RGB + piloto)
- **Esfuerzo:** L
- **Descripción:** Vuelos mensuales → mapas de biomasa detallados, conteo de animales, inspección de cercas y bebederos.

### 14. Planet Labs (imágenes diarias de 3 m)
- **Estado:** 💭 Idea
- **Impacto:** 🟡 Medio — solo si el NDVI cada 3 días queda corto
- **Costo:** 💲💲💲 (suscripción paga)
- **Esfuerzo:** S (mismo pipeline Earth Engine, otra colección)
- **Descripción:** Imágenes satelitales **diarias** a 3 m de resolución. Evaluar solo si la frecuencia actual de Sentinel-2 resulta insuficiente.

---

## 🗂️ Prioridad sugerida (orden de ejecución recomendado)

| Orden | Idea | Por qué primero |
|---|---|---|
| 1️⃣ | #1 Pronóstico al despacho | Rápido, gratis, valor diario inmediato |
| 2️⃣ | #2 Alerta de sequía SPI | Reusa datos CHIRPS que ya se descargan |
| 3️⃣ | #4 Rotación automática recomendada | Convierte datos existentes en decisiones |
| 4️⃣ | #5 Estación meteorológica | Mejor inversión física: clima real de la finca |
| 5️⃣ | #6 Sentinel-1 radar | Resuelve el problema de las nubes, gratis |
| 6️⃣ | #3 Balance forrajero predictivo | Depende de #1; cierra el círculo forrajero |

---

## 📝 Bitácora de decisiones

| Fecha | Decisión |
|---|---|
| 2026-09-07 | Documento creado. Ideas de monitoreo potreros/clima capturadas. NDVI cambiado a job cada 3 días (commit `1375fe4`). |

---

## ➕ Plantilla para nuevas ideas

```markdown
### N. Nombre de la idea
- **Estado:** 💭 Idea
- **Impacto:** 🟢/🟡/🔵
- **Costo:** 💲/💲💲/💲💲💲
- **Esfuerzo:** S/M/L
- **Descripción:** ...
- **Dependencias:** ...
- **Notas:** ...
```
