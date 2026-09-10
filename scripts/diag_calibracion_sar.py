"""Diagnóstico: compara RVI real (Sentinel-1 SAR) contra NDVI óptico real
(Sentinel-2, cuando haya imagen usable) para cada potrero, para reevaluar si
la calibración de calcular_sar_ndvi() en src/gis/earth_engine_sar.py sigue
siendo válida (repetir sobre todo cuando haya muestras de pastura degradada/
RVI bajo, fuera del rango 0.80-1.01 cubierto por la calibración 2026-09-08).

Uso: python scripts/diag_calibracion_sar.py  (requiere GEE_* en .env)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from src.db.database import Database
from src.gis.earth_engine_ndvi import inicializar_ee, _ndvi_region_sentinel2
from src.gis.earth_engine_sar import _sar_region_sentinel1

DIR_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db = Database(os.path.join(DIR_RAIZ, "data", "bitacora.db"))
potreros = db.query(
    "SELECT id, nombre, geom_wkt_4326 FROM potreros WHERE geom_wkt_4326 IS NOT NULL ORDER BY nombre"
)
db.close()

print(f"{len(potreros)} potreros con geometría real.\n")
inicializar_ee()

hoy = date.today()
filas = []
for p in potreros:
    nombre = p["nombre"]
    wkt = p["geom_wkt_4326"]
    try:
        sar = _sar_region_sentinel1(wkt, hoy, dias_ventana=45)
    except Exception as e:
        sar = None
        print(f"  [SAR ERROR] {nombre}: {e}")
    try:
        opt = _ndvi_region_sentinel2(wkt, hoy, dias_ventana=90, fraccion_valida_min=0.6)
    except Exception as e:
        opt = None
        print(f"  [S2 ERROR] {nombre}: {e}")

    rvi = sar["rvi"] if sar else None
    proxy = sar["ndvi_promedio"] if sar else None
    real = opt["ndvi_promedio"] if opt else None
    real_fecha = opt["fecha_imagen"] if opt else None
    filas.append((nombre, rvi, proxy, real, real_fecha))
    print(f"{nombre:25s}  RVI={str(rvi):>7}  proxy_actual={str(proxy):>7}  "
          f"NDVI_real_S2={str(real):>7}  (fecha={real_fecha})")

print("\n--- Resumen ---")
rvis = [f[1] for f in filas if f[1] is not None]
if rvis:
    print(f"RVI: min={min(rvis):.3f} max={max(rvis):.3f} promedio={sum(rvis)/len(rvis):.3f}")
    saturados = sum(1 for r in rvis if r >= 1.0)
    print(f"Potreros con RVI >= 1.0 (satura el proxy en 0.85): {saturados}/{len(rvis)}")

pares = [(f[1], f[3]) for f in filas if f[1] is not None and f[3] is not None]
print(f"\nPares con NDVI óptico real disponible: {len(pares)}/{len(filas)}")
if len(pares) >= 3:
    import statistics
    xs = [p[0] for p in pares]
    ys = [p[1] for p in pares]
    n = len(pares)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in pares)
    varx = sum((x - mx) ** 2 for x in xs)
    if varx > 0:
        b = cov / varx
        a = my - b * mx
        print(f"Ajuste lineal real (mínimos cuadrados): NDVI_real ≈ {a:.4f} + {b:.4f} * RVI")
        print("(fórmula actual en el código: NDVI_proxy = 0.20 + 0.65 * RVI)")
elif pares:
    for x, y in pares:
        print(f"  RVI={x:.3f} -> NDVI_real={y:.3f}")
else:
    print("Sin pares suficientes -- ninguna imagen Sentinel-2 despejada en los últimos 90 días.")
