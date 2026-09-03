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
- [ ] **Fase C — Pipeline NDVI real vía Google Earth Engine** (decidido 2026-09-02, sobre openEO/Copernicus: mejor tooling Python, unifica NDVI + lluvia CHIRPS en una sola cuenta). **Bloqueado en el usuario**: falta que complete el registro (proyecto Google Cloud + tier no-comercial + cuenta de servicio con JSON key). Pasos entregados al usuario:
  1. https://console.cloud.google.com/earth-engine — crear/elegir proyecto Cloud.
  2. Activar Earth Engine API: https://console.cloud.google.com/apis/library/earthengine.googleapis.com
  3. Verificación no-comercial (tier Community, 150 EECU-hora/mes): https://console.cloud.google.com/earth-engine/configuration
  4. Cuenta de servicio + JSON key: https://console.cloud.google.com/apis/credentials
  5. Entregar la ruta del `.json` descargado (no el contenido en texto plano) para continuar con el script de la Fase C.
- [ ] Fase D — Lluvia satelital de referencia (opcional, mismo pipeline de Earth Engine vía CHIRPS/GPM una vez esté la Fase C andando).

**Nota honesta pendiente aparte:** el `README.md` (líneas ~375-378) describe la Fase 8.2 como si el NDVI ya fuera real ("Monitoreo satelital multiespectral Sentinel-2 L2A"), lo cual es engañoso dado que hoy es simulado. Vale la pena corregir esa redacción cuando se implemente la Fase C, o antes si se quiere ser preciso de inmediato.
