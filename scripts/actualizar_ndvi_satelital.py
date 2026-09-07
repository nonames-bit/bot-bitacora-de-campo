#!/usr/bin/env python3
"""Job periódico (cada 3 días): consulta Google Earth Engine y actualiza el
NDVI real de los potreros.

Reemplaza la simulación de sentinel_ndvi.SentinelNDVI.simular_lecturas_potreros
escribiendo lecturas reales en monitoreo_satelital_ndvi (Fase C del plan
geoespacial, ver docs/PLAN_GEO_SATELITAL_6.2_8.2.md). Pensado para correr por
cron cada 3 días (``0 6 */3 * *``): la revisita de Sentinel-2 es cada ~5 días,
así que correr cada 3 días maximiza la probabilidad de capturar la imagen
despejada nueva apenas se publica.

Uso:
    python scripts/actualizar_ndvi_satelital.py [--db data/bitacora.db]

Requiere en el entorno (.env): GEE_SERVICE_ACCOUNT_EMAIL, GEE_SERVICE_ACCOUNT_KEY_PATH
y opcionalmente GEE_PROJECT_ID.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.db.database import Database
from src.gis.earth_engine_ndvi import actualizar_lecturas_reales, inicializar_ee


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualiza NDVI real de potreros vía Google Earth Engine")
    parser.add_argument("--db", default=os.getenv("BITACORA_DB", "data/bitacora.db"), help="Ruta SQLite")
    args = parser.parse_args()

    try:
        inicializar_ee()
    except Exception as e:
        print(f"❌ No se pudo inicializar Earth Engine: {e}", file=sys.stderr)
        return 1

    db = Database(args.db)
    filas = db.query(
        "SELECT id, nombre, area_has, geom_wkt_4326 FROM potreros WHERE geom_wkt_4326 IS NOT NULL"
    )
    potreros = [dict(f) for f in filas]

    if not potreros:
        print("⚠️ Ningún potrero tiene geom_wkt_4326 (Fase B del plan geoespacial). Nada que actualizar.")
        db.close()
        return 0

    print(f"🛰️ Consultando Sentinel-2 vía Earth Engine para {len(potreros)} potreros...")
    lecturas = actualizar_lecturas_reales(potreros)

    for l in lecturas:
        db.registrar_lectura_ndvi(
            l["potrero_id"],
            l["ndvi_promedio"],
            fecha=l["fecha"],
            ndvi_min=l["ndvi_min"],
            ndvi_max=l["ndvi_max"],
            biomasa_estimada_kg_ha=l["biomasa_estimada_kg_ha"],
            aforo_estimado_kg_m2=l["aforo_estimado_kg_m2"],
            cobertura_nubes_pct=l["cobertura_nubes_pct"] or 0.0,
            fuente=l["fuente"],
        )
        print(f"  ✅ {l['potrero_nombre']}: NDVI {l['ndvi_promedio']} ({l['categoria']}, imagen del {l['fecha']})")

    sin_dato = len(potreros) - len(lecturas)
    if sin_dato:
        print(
            f"  ⚠️ {sin_dato} potreros sin imagen Sentinel-2 reciente (nubes/revisita); "
            "conservan el último dato real o caen a la estimación de respaldo en /ndvi."
        )

    db.close()
    print(f"\n✅ {len(lecturas)} lecturas NDVI reales guardadas en monitoreo_satelital_ndvi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
