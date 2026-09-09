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
- **Estado:** ✔️ Completada (2026-09-08) — bot y PWA
- **Impacto:** 🟢 Alto — resuelve de raíz el problema real: en época de lluvias el NDVI óptico se queda semanas sin imagen despejada
- **Costo:** 💲 (gratis vía Google Earth Engine, que ya se usa)
- **Esfuerzo:** M
- **Descripción:** El radar SAR de Sentinel-1 penetra las nubes → biomasa/humedad de suelo estimada **sin importar el cielo**. Complementa Sentinel-2: cuando no hay imagen óptica, el radar da continuidad temporal.
- **Dependencias:** Misma infraestructura Earth Engine actual (`src/gis/earth_engine_ndvi.py` y `src/gis/earth_engine_sar.py`).
- **Notas:** Implementado en `src/gis/earth_engine_sar.py` con índice RVI dual-pol y estimación de humedad dieléctrica. Fusión multisensor automatizada en modo auto.

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

## 🧬 Zootecnia, Genética & Gestión Comercial

### 15. Simulador de Cruzamiento y Consanguinidad 3G en PWA (Fase 5.2)
- **Estado:** 💭 Pendiente
- **Impacto:** 🟢 Alto — previene depresión por endogamia antes de aplicar la pajuela en campo
- **Costo:** 💲 Solo software
- **Esfuerzo:** S-M
- **Descripción:** Selector táctil en PWA donde el usuario elige la vaca receptora y el toro/pajuela del termo. El sistema calcula al vuelo el coeficiente de parentesco/consanguinidad de Wright ($F$) en 3 generaciones (3G) y muestra un semáforo (Verde < 3.12%, Amarillo 3.12-6.25%, Rojo > 6.25% con ancestros comunes destacados).
- **Dependencias:** Tablas `genealogia`, `animales`, `pajuelas_inventario` existentes.

### 16. Estimación de Condición Corporal (BCS) asistida por Visión IA (Fase 8.1)
- **Estado:** 💭 Pendiente
- **Impacto:** 🟡 Medio-Alto — monitoreo nutricional no invasivo y balance energético de vacas
- **Costo:** 💲 Software (Gemini Vision API)
- **Esfuerzo:** M
- **Descripción:** Capturar o subir fotografía dorsal/isquion de la vaca en la PWA. Gemini Vision evalúa la prominencia ósea de espina dorsal, costillas, ganchos e isquiones para estimar la condición corporal en escala zootécnica 1.0 a 5.0 (con precisión de 0.25).
- **Dependencias:** Gemini Vision / OpenAI vision, tabla `condicion_corporal`.

### 17. Catálogo Digital de Venta de Ganado (Modo Feria / WhatsApp)
- **Estado:** 💭 Pendiente
- **Impacto:** 🟢 Alto — herramienta comercial inmediata para negociar lotes o reproductores
- **Costo:** 💲 Solo software
- **Esfuerzo:** S
- **Descripción:** Selección de animales para la venta en la PWA con generación en 1 clic de ficha publicitaria web o PDF de presentación para compradores: fotos, hierro/fierro, peso actual, GMD, árbol genealógico de padres/abuelos y estado reproductivo.
- **Dependencias:** Fichas zootécnicas existentes, fotos y reportes PDF.

---

## 🗂️ Prioridad sugerida (orden de ejecución recomendado)

| Orden | Idea | Por qué primero |
|---|---|---|
| 1️⃣ | #1 Pronóstico al despacho | ✔️ Completada: rápido, gratis, valor diario inmediato |
| 2️⃣ | #2 Alerta de sequía SPI | ✔️ Completada: reusa datos CHIRPS que ya se descargan |
| 3️⃣ | #6 Sentinel-1 radar SAR | ✔️ Completada: resuelve monitoreo con cielo nublado |
| 4️⃣ | **Mapa Satelital con usuarios en vivo** | 🚧 En progreso: visualización espacial táctil de los 20 potreros y operarios |
| 5️⃣ | **Costo/kg Carne y Margen/L Leche** | 🚧 En progreso: control económico dinámico en Finanzas |
| 6️⃣ | **Notificaciones Web Push PWA** | 🚧 En progreso: alertas nativas en celulares de campo |
| 7️⃣ | #15 Simulador Cruzamiento 3G | 💭 Pendiente: seguridad genética al inseminar |
| 8️⃣ | #17 Catálogo Venta Ganado | 💭 Pendiente: valor comercial directo |
| 9️⃣ | #16 BCS Corporal con IA | 💭 Pendiente: monitoreo nutricional |

---

## 📝 Bitácora de decisiones

| Fecha | Decisión |
|---|---|
| 2026-09-07 | Documento creado. Ideas de monitoreo potreros/clima capturadas. NDVI cambiado a job cada 3 días. |
| 2026-09-08 | Sentinel-1 SAR implementado y en producción (Fusión multisensor S1+S2). |
| 2026-09-08 | Aprobadas para desarrollo inmediato: 1) Mapa Satelital Interactivo con usuarios en vivo en PWA, 2) Indicadores económicos dinámicos (Costo/kg y Margen/L), 3) Notificaciones Web Push en PWA. Las ideas de Simulador 3G (#15), BCS corporal (#16) y Catálogo de venta (#17) quedan registradas como pendientes. |

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
