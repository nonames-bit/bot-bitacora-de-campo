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

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from src.db.database import Database
from src.gis.earth_engine_ndvi import actualizar_lecturas_reales, inicializar_ee


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualiza NDVI real de potreros vía Google Earth Engine (Sentinel-2 y Sentinel-1 SAR)")
    parser.add_argument("--db", default=os.getenv("BITACORA_DB", "data/bitacora.db"), help="Ruta SQLite")
    parser.add_argument(
        "--modo",
        choices=["auto", "s2", "s1", "radar"],
        default="auto",
        help="Modo satelital: 'auto' (óptico con respaldo radar SAR si hay nubes), 's2' (solo óptico), 's1'/'radar' (solo radar SAR)",
    )
    parser.add_argument("--radar", "--sar", action="store_true", help="Atajo para forzar modo='s1' (radar SAR todo clima)")
    args = parser.parse_args()

    modo = "s1" if args.radar else args.modo

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

    modo_desc = (
        "Sentinel-2 óptico + respaldo Sentinel-1 SAR radar" if modo == "auto"
        else ("Sentinel-1 SAR Radar (todo clima)" if modo in ("s1", "radar") else "Sentinel-2 óptico")
    )
    print(f"🛰️ Consultando satélites ({modo_desc}) vía Earth Engine para {len(potreros)} potreros...")
    lecturas = actualizar_lecturas_reales(potreros, modo=modo)

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
        if "Sentinel-1" in str(l.get("fuente")):
            hum_txt = f" · Humedad: {l.get('humedad_pct')}%" if l.get("humedad_pct") is not None else ""
            print(f"  📡 {l['potrero_nombre']}: NDVI {l['ndvi_promedio']} ({l['categoria']}, Radar SAR Sentinel-1{hum_txt}, imagen del {l['fecha']})")
        else:
            print(f"  🛰️ {l['potrero_nombre']}: NDVI {l['ndvi_promedio']} ({l['categoria']}, Óptico Sentinel-2, imagen del {l['fecha']})")

    sin_dato = len(potreros) - len(lecturas)
    if sin_dato:
        print(
            f"  ⚠️ {sin_dato} potreros sin adquisición reciente; "
            "conservan el último dato real o caen a la estimación de respaldo en /ndvi."
        )

    db.close()
    print(f"\n✅ {len(lecturas)} lecturas satelitales guardadas en monitoreo_satelital_ndvi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
