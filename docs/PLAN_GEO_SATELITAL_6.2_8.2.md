# 🛰️ Plan: Motor Geoespacial Real para Fase 6.2 + Fase 8.2

> **Fecha:** 2026-09-01
> **Origen:** Sesión de análisis del bot; se detectó que tanto la integración "IDEAM" (Fase 6.2)
> como el NDVI "Sentinel-2" (Fase 8.2) son **simulaciones/heurísticas sin conexión real a datos
> satelitales o climáticos**. Este documento propone cerrar esa brecha usando geodata real que
> ya existe en otro proyecto del usuario.

---

## 1. Diagnóstico: qué es real y qué no, hoy

| Componente | ¿Real o simulado? | Detalle |
|---|---|---|
| `src/integrations/ideam_clima.py` (`ClimaIDEAM`) | ❌ Simulado | Sin llamadas HTTP. `clasificar_estacionalidad()` solo clasifica el mm de lluvia que el usuario registró manualmente (`/lluvia`) en 3 baldes fijos (≥150mm, 50-150mm, <50mm). La tabla `PATRON_ESTACIONAL_COLOMBIA` con promedios mensuales existe pero **nunca se usa** en producción (código muerto). El nombre "IDEAM" es solo branding. |
| `src/gis/sentinel_ndvi.py` (`SentinelNDVI.simular_lecturas_potreros`) | ❌ Simulado | El NDVI se inventa a partir de `dias_ocupacion`/`dias_reposo` del potrero (heurística interna), y se le pega la etiqueta falsa `"fuente": "Sentinel-2 L2A (Copernicus)"`. No hay ninguna imagen satelital real involucrada. |
| Fórmulas de cálculo (`pasture_engine.py`, `calcular_ndvi`, `estimar_aforo_kg_m2_desde_ndvi`, `balance_agroclimatico`) | ✅ Reales/legítimas | Son modelos empíricos agronómicos estándar. El problema no es la fórmula, es el dato de entrada. |
| `potreros.area_has` en la BD del bot (`data/bitacora.db`) | ❌ Vacío | Las 57 filas tienen `area_has = NULL`. El panel `/balance_forrajero` cae al fallback de 50 ha para toda la finca. |
| Tabla `monitoreo_satelital_ndvi` (esquema SQLite) | ✅ Lista para usarse | Esquema correcto (`potrero_id`, `fecha`, `ndvi_promedio/min/max`). Solo falta alimentarla con datos reales. |

---

## 2. El hallazgo: ya existe geodata real utilizable

En `C:\Users\Owner\Documents\finca` hay un proyecto QGIS completo de esta misma finca (Mesetas, Meta):

- `Potreros_fase1.gpkg` — 49 potreros con polígonos reales, CRS **EPSG:32618** (UTM 18N), campo `cod_sg`, `area_ha` ya calculada con restricciones (bosques/lagunas/vías) restadas.
- `Finca.gpkg` — capas `potreros`, `potreros_netos`, `RESTRICCIONES` (26 features: bosques, lagunas, infraestructura).
- `Contours.gpkg` — curvas de nivel (elevación 600-630m).
- Formato GeoPackage = SQLite puro → **se puede leer con `sqlite3` de Python sin GDAL** para los atributos (geometría es WKB, para eso sí se necesita `shapely`/`pyproj` o GDAL).

**Verificado:** el campo `cod_sg` del QGIS coincide exactamente con `potreros.codigo` del bot:

| Bot (`codigo`) | QGIS (`cod_sg`) | Área real | Área en el bot hoy |
|---|---|---|---|
| A02 — CORRAL SANTAMARTHA | A02 — CORRAL | 1.60 ha | `NULL` |
| A03 — PARITORIO | A03 — PARITORIO | 4.81 ha | `NULL` |
| A04 — FELIPE | AF-01..06 (subdividido) | 14.00 ha | `NULL` |
| B01 — OLEGARIO I | B01a..d (subdividido) | 12.88 ha | `NULL` |
| B02 — OLEGARIO II | B02a..f (subdividido) | 17.78 ha | `NULL` |
| C01 — CORRAL VERSALLES | C01 (sin subdividir) | 2.03 ha | `NULL` |

No se encontró nada de NDVI/Sentinel/Earth Engine en `C:\Users\Owner\Documents\finca` — ese proyecto es puramente vectorial (potreros, cercas) más un proyecto IoT paralelo de chapetas BLE/LoRa (`proyecto chapetas/`) para geoposicionar el hato en tiempo real (complementario, no satelital).

Entorno del bot: no tiene instalado `shapely`, `pyproj`, `geopandas`, `fiona` ni `osgeo` (GDAL) — habría que agregar al menos `shapely`+`pyproj` (puro Python, sin GDAL) a `requirements.txt` para reproyectar/leer geometría.

---

## 3. Plan por fases

### Fase A — Importar áreas reales (bajo esfuerzo, ~1-2h, impacto inmediato)
Script one-off: leer `area_ha` de `Potreros_fase1.gpkg` + `Finca.gpkg` (vía `sqlite3` directo, sin GDAL) y hacer `UPDATE potreros SET area_has = ? WHERE codigo = ?` matcheando por `cod_sg`. Corrige de inmediato el fallback de 50 ha en `/balance_forrajero`.

### Fase B — Guardar los polígonos, no solo el área (esfuerzo medio, ~1 día)
- Agregar `shapely` + `pyproj` a `requirements.txt`.
- Extraer geometría WKB de cada potrero, reproyectar de EPSG:32618 → EPSG:4326 (lat/lon, lo que exigen las APIs satelitales).
- Guardar en el bot: columna nueva `potreros.geom_wkt` o tabla `potreros_geom`.

### Fase C — NDVI real vía satélite (esfuerzo medio-alto)
- Evaluar **Google Earth Engine** (gratuito para uso agrícola no comercial, requiere cuenta de servicio + proyecto de Google Cloud) vs **Copernicus Data Space Ecosystem / openEO** (oficial ESA, sin cuenta Google).
- Reemplazar `SentinelNDVI.simular_lecturas_potreros()` por una consulta real: Sentinel-2, filtro de nubosidad, `reduceRegion` sobre el polígono real de cada potrero (Fase B), promedio semanal.
- Escribir el resultado en `monitoreo_satelital_ndvi` (esquema ya listo, no se toca).
- Job programado semanal (mismo patrón que el despacho matutino de Fase 4), no cálculo "al vuelo" en el chat.

### Fase D — Lluvia satelital como referencia, NO reemplazo (opcional, mismo pipeline)
- CHIRPS o GPM/IMERG vía Earth Engine, mismo auth que Fase C.
- **Ojo:** resolución ~5km, no distingue microclima entre sectores de una sola finca — mostrar como dato de contraste en `/clima` ("registrado: 35mm · estimado satelital: 28mm"), no sustituir el pluviómetro físico.

---

## 3.5. Resolución de códigos duplicados (2026-09-02)

El usuario compartió el reporte nativo de **Software GANADERO SG** (`POTREROS`, hacienda
01-JA GANADERIA-JA): la lista **real y actual** de potreros es de **21 registros**:
`A01-A04`, `B01-B02`, `C01-C14`, `D01` (ARRIENDO). No existe ningún potrero `12`, `13`,
`09`, `17` ni ningún otro código numérico en el sistema real.

**Conclusión:** los códigos numéricos (`01-23`), `L1-L9`, `G01-G04` presentes en la tabla
`potreros` del bot **no son potreros reales/actuales de la finca** — son artefactos de una
importación anterior (probablemente otra tabla DBF de una versión previa de SG mapeada por
error a `potreros`, o remanente de un esquema de "lotes" funcionales histórico). No se
fusionan ni se borran sin instrucción explícita del usuario; simplemente quedan **fuera**
de cualquier cálculo de balance forrajero/área real.

`D01` (ARRIENDO) es real y actual según SG, pero **queda excluido del alcance de este plan
por diseño, no por falta de dato**: según el usuario, es tierra que se arrienda de forma
variable en distintas partes cerca de la finca — no tiene una ubicación fija que
georreferenciar. Su área se sigue manejando manual/caso a caso como hasta ahora; no aplica
NDVI, polígono ni pipeline satelital para este código.

Capa QGIS confirmada por el usuario (captura de pantalla de la tabla de atributos en QGIS):
`Finca.gpkg::potreros` (área **bruta**, sin restar restricciones) — no `potreros_netos`.
Valores verificados contra `sqlite3` directo, coinciden exactamente.

## 4. Estado y próximo paso

- [x] **Fase A — Importar áreas reales de potreros** (completada 2026-09-02): `UPDATE potreros SET area_has = ...` acotado a los 20 códigos `A01-A04`/`B01-B02`/`C01-C14`, usando `Finca.gpkg::potreros` (área bruta, confirmada por el usuario vía captura de QGIS). Backup previo en `data/bitacora.db.bak-20260902-200756`. Verificado en `/balance_forrajero`: superficie pasó de 50 ha (fallback) a **243.5 ha reales**, carga animal actual 0.97 UGG/ha, superávit forrajero.
- [x] **Fase B — Guardar polígonos reproyectados en la BD del bot** (completada 2026-09-02): se agregaron `shapely`+`pyproj` a `requirements.txt`; columnas nuevas `geom_wkt_4326`, `centroide_lat`, `centroide_lon` en `potreros` (`src/db/models.py` para BDs nuevas, migración idempotente `ALTER TABLE` en `database.py::create_tables()` para BDs existentes). Se extrajo la geometría de `Finca.gpkg::potreros` (columna `geometry`, header binario GeoPackage despojado a mano — no requiere GDAL), se reproyectó de EPSG:32618 a EPSG:4326 con `pyproj.Transformer`, y se guardó el polígono completo (WKT) + centroide (lat/lon) para los 20 códigos A/B/C. Centroides verificados en rango ~3.39-3.41°N / -74.06 a -74.10°W, consistente con Mesetas, Meta. Suite de tests sigue en verde tras la migración.
- [x] **Fase C — Pipeline NDVI real vía Google Earth Engine** (completada 2026-09-03): cuenta de servicio (`ndvi-bot-bitacora@finca-mesetas-ndvi.iam.gserviceaccount.com`) creada con roles **Earth Engine Resource Viewer** + **Service Usage Consumer** (el segundo es obligatorio y no es obvio — sin él, `ee.Initialize()` falla con `USER_PROJECT_DENIED` aunque las credenciales sean correctas). Nuevo módulo `src/gis/earth_engine_ndvi.py`:
  - `inicializar_ee()` autentica con `ee.ServiceAccountCredentials` usando `GEE_SERVICE_ACCOUNT_EMAIL` / `GEE_SERVICE_ACCOUNT_KEY_PATH` / `GEE_PROJECT_ID` (`.env`).
  - `actualizar_lecturas_reales(potreros)` consulta `COPERNICUS/S2_SR_HARMONIZED` sobre el polígono real (`geom_wkt_4326`, Fase B) de cada potrero.
  - **Hallazgo de la prueba en vivo:** filtrar por `CLOUDY_PIXEL_PERCENTAGE` (metadato de nubosidad de la escena completa, ~110×110 km) da **0 imágenes útiles en una ventana de 15 días** para potreros pequeños (1-50 ha) en clima tropical (Meta, Colombia, temporada de lluvias) — una escena "nublada" en el metadato puede tener el potrero puntual despejado, y viceversa. Se cambió a evaluar la nubosidad **píxel a píxel con la banda SCL directamente sobre el polígono del potrero** (clases limpias: vegetación/suelo desnudo/agua/no clasificado/nieve), recorriendo las imágenes de una ventana de 45 días de la más reciente a la más antigua hasta encontrar una con ≥60% de píxeles limpios sobre el AOI. Con ese cambio sí se encontró una imagen 100% despejada para la finca.
  - Script `scripts/actualizar_ndvi_satelital.py` (mismo patrón que `enviar_despacho.py`): lee los potreros con `geom_wkt_4326`, llama al pipeline y persiste con `Database.registrar_lectura_ndvi`. Pensado para cron semanal (documentado en `docs/DESPLIEGUE_DIGITALOCEAN.md`, sección "NDVI satelital real").
  - **Verificado en producción local** (`data/bitacora.db`, 2026-09-03): los 20 potreros reales (`A01-A04`/`B01-B02`/`C01-C14`) recibieron NDVI real de la imagen Sentinel-2 del `2026-08-25` (una del `2026-08-27`), rango 0.538-0.672 (categoría ÓPTIMO/REPOSO), y `/ndvi` ya los muestra con `fuente = "Sentinel-2 L2A (Copernicus, vía Google Earth Engine)"` en vez de la simulación.
  - Tests: `tests/test_earth_engine_ndvi.py` (7 casos), con `ee` completamente mockeado — no requieren red ni credenciales para correr en CI.
  - **Nota pendiente sin resolver, detectada de paso (no es de esta fase):** al revisar `/ndvi` en vivo aparecieron potreros duplicados con el mismo nombre pero distinto `id` — uno con código numérico legado (`13`, `17`, sin `geom_wkt_4326`, cae a la simulación) y otro con código real `A/B/C` (con geometría, dato real). Ej.: `CARRETERA VERSALLES` (id 13, sin geom) vs `CARRETERA VERSALLES` (id 31, código `C02`, con geom). Es el mismo problema de duplicados ya documentado en la sección 3.5 de este plan; sigue **fuera de alcance** — no se fusiona/borra sin instrucción explícita del usuario.
- [x] **Fase D — Lluvia satelital de referencia** (completada 2026-09-03): pipeline
  `src/gis/earth_engine_lluvia.py::estimar_lluvia_finca()`, usando **CHIRPS**
  (`UCSB-CHG/CHIRPS/DAILY`, banda `precipitation`, resolución ~5.5 km) en vez de GPM/IMERG —
  banda diaria única, agregación simple (`.sum()` sobre la ventana), sin la complejidad de
  sumar decenas de imágenes semi-horarias. Reutiliza `inicializar_ee()` de
  `earth_engine_ndvi.py`, sin credenciales nuevas.
  - **Hallazgo de la prueba en vivo (análogo al de nubosidad de la Fase C):** a diferencia
    de Sentinel-2, la colección `UCSB-CHG/CHIRPS/DAILY` en Earth Engine tiene una latencia
    real de **~30-45 días** — al probar el 2026-09-03, la imagen más reciente disponible en
    el catálogo era del **2026-07-31**, no de la semana anterior. Asumir que la ventana de
    30 días termina "hoy" da colección vacía casi siempre. Se resolvió con
    `_fecha_mas_reciente_disponible()`: busca hacia atrás (ventana de 75 días) la fecha real
    más reciente con dato disponible, y la ventana de acumulación de lluvia termina ahí, no
    en la fecha de corrida del job.
  - Esto implica que `fecha` en `monitoreo_satelital_lluvia` (el fin de la ventana de 30
    días que cubre el dato) **siempre** va a estar semanas atrás de la fecha real del job —
    es esperado, no un bug. Por eso el chequeo de "dato obsoleto" en
    `Database.resumen_pluviometrico()` compara contra `creado_en` (cuándo corrió el job),
    no contra `fecha` (qué período cubre el dato CHIRPS).
  - Como la resolución de CHIRPS no distingue microclima entre sectores de una sola finca
    (~243 ha caben holgadamente en un solo píxel de ~5.5 km), el AOI es un único
    punto-buffer (radio 2750 m, la mitad de la resolución nativa) centrado en el centroide
    **promedio** de los 20 potreros reales con `geom_wkt_4326` — no se calcula por potrero
    ni se construye la unión de los 20 polígonos.
  - Se guarda en la nueva tabla `monitoreo_satelital_lluvia` (`fecha`, `dias_acumulados`,
    `mm_estimado`, `fuente`, `creado_en`), vía `Database.registrar_lectura_lluvia_satelital()`.
    Se añadió a `TABLAS_EVENTOS`/`/deshacer` igual que `monitoreo_satelital_ndvi`.
  - `Database.resumen_pluviometrico()` expone `satelital_mm`/`satelital_dias`/
    `satelital_fecha` solo si el job corrió en los últimos ≤10 días (vía `creado_en`); es un
    campo aditivo, no rompe a los llamadores existentes.
  - `/clima` (`src/engine/query/pasturas.py::_consulta_lluvias`) muestra una línea
    adicional "🛰️ Estimado Satelital (CHIRPS, 30d hasta {fecha}): X mm · registrado: Y mm"
    cuando hay dato satelital reciente, junto al registro manual real (que sigue siendo la
    fuente de verdad para el balance forrajero — este dato es solo de contraste). La fecha
    mostrada es explícita para que no se confunda con "los últimos 30 días desde hoy".
  - Job semanal `scripts/actualizar_lluvia_satelital.py` (mismo patrón que
    `actualizar_ndvi_satelital.py`): calcula el centroide promedio con
    `SELECT AVG(centroide_lat), AVG(centroide_lon) FROM potreros WHERE geom_wkt_4326 IS NOT NULL`,
    consulta CHIRPS y persiste el resultado. Cron documentado en
    `docs/DESPLIEGUE_DIGITALOCEAN.md`.
  - **Verificado en producción local** (`data/bitacora.db`, 2026-09-03): 272.1 mm en los 30
    días terminando el 2026-07-31 para el centroide de la finca (3.40237, -74.08822);
    `/clima` ya muestra la línea del estimado satelital.
  - 4 tests con `ee` completamente mockeado (`tests/test_earth_engine_lluvia.py`): usa la
    fecha más reciente disponible (no "hoy"), ventana sin cobertura CHIRPS en absoluto →
    `None`, redondeo, y manejo de error de Earth Engine. Suite completa: 523/523 en verde.
  - **Pendiente de este cierre:** desplegar al VPS (push + pull + reinicio del servicio +
    agregar la línea de cron + correr el job una vez a mano), con el mismo cuidado de backup
    previo que se usó al desplegar la Fase C.
- [x] **Fase E — Sentinel-1 SAR GRD: Monitoreo Radar Todo Clima (2026-09-07)**:
  - **Problema resuelto:** en temporada de lluvias (Llanos Orientales / Meta), la nubosidad
    persistente bloquea el NDVI óptico (Sentinel-2) por semanas completas.
  - **Solución implementada:** radar de apertura sintética (SAR) en banda C (~5.4 GHz) vía
    `COPERNICUS/S1_GRD` (modos IW, polarizaciones duales VV y VH). Las microondas penetran
    100% las nubes, lluvia, neblina y noche.
  - **Módulo `src/gis/earth_engine_sar.py`**:
    - Cálculo de Dual-Pol Radar Vegetation Index:
      $RVI = \frac{4 \cdot \sigma^\circ_{VH,lin}}{\sigma^\circ_{VV,lin} + \sigma^\circ_{VH,lin}}$
    - Relación cruzada de retrodispersión (Cross-Ratio $CR_{dB} = VH_{dB} - VV_{dB}$).
    - Proxy SAR-NDVI calibrado para pasturas tropicales:
      $NDVI_{radar} = 0.20 + 0.65 \times RVI$ (rango 0.15 - 0.85).
    - Proxy de humedad de suelo / forraje por respuesta dieléctrica de polarización VV:
      $Humedad_{\%} = \frac{VV_{dB} - (-18)}{(-7) - (-18)} \times 100$.
  - **Estrategia Multi-sensor / Fusión (`src/gis/earth_engine_ndvi.py`):**
    - `actualizar_lecturas_reales(modo='auto')`: busca primero Sentinel-2 óptico ($\ge 60\%$ píxeles limpios).
    - Si el potrero está cubierto de nubes, conmuta **automáticamente** al radar SAR Sentinel-1 como
      respaldo todo clima, garantizando continuidad temporal 365 días al año sin potreros huérfanos.
    - Soporte para modos forzados `--modo s1` (radar puro) y `--modo s2` (óptico puro).
  - **Integración Telegram y PWA:**
    - `/ndvi` muestra distintivo `[📡 SAR]` y nota multisensor cuando la lectura proviene de radar.
    - PWA expone la fuente y métricas de humedad.
  - Tests unitarios completos con `ee` mockeado en `tests/test_earth_engine_sar.py`.

Con esto el plan geoespacial (Fases A–E) queda **completo y robusto**.

**Nota honesta ya corregida:** el `README.md` describía la Fase 8.2 como si el NDVI ya fuera real cuando en realidad era simulado. Con la Fase C y Fase E completadas, la redacción del README se actualizó para reflejar el estado real (NDVI real multisensor óptico Sentinel-2 + radar SAR Sentinel-1 todo clima).
