#!/usr/bin/env python3
"""Job semanal: consulta CHIRPS vía Google Earth Engine y guarda la lluvia
estimada de la finca como referencia satelital.

Fase D del plan geoespacial (ver docs/PLAN_GEO_SATELITAL_6.2_8.2.md): un dato
de contraste junto al registro manual de `/lluvia`, no un reemplazo. Escribe
en `monitoreo_satelital_lluvia`. Pensado para correr por cron una vez por
semana, igual que scripts/actualizar_ndvi_satelital.py.

Uso:
    python scripts/actualizar_lluvia_satelital.py [--db data/bitacora.db]

Requiere en el entorno (.env) las mismas credenciales que el job de NDVI:
GEE_SERVICE_ACCOUNT_EMAIL, GEE_SERVICE_ACCOUNT_KEY_PATH y opcionalmente
GEE_PROJECT_ID.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.db.database import Database
from src.gis.earth_engine_lluvia import estimar_lluvia_finca
from src.gis.earth_engine_ndvi import inicializar_ee


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualiza la lluvia estimada de la finca vía CHIRPS/Earth Engine")
    parser.add_argument("--db", default=os.getenv("BITACORA_DB", "data/bitacora.db"), help="Ruta SQLite")
    args = parser.parse_args()

    try:
        inicializar_ee()
    except Exception as e:
        print(f"❌ No se pudo inicializar Earth Engine: {e}", file=sys.stderr)
        return 1

    db = Database(args.db)
    centroide = db.query_one(
        "SELECT AVG(centroide_lat) AS lat, AVG(centroide_lon) AS lon "
        "FROM potreros WHERE geom_wkt_4326 IS NOT NULL"
    )
    if not centroide or centroide["lat"] is None or centroide["lon"] is None:
        print("⚠️ Ningún potrero tiene geom_wkt_4326 (Fase B del plan geoespacial). Nada que estimar.")
        db.close()
        return 0

    print(f"🛰️ Consultando CHIRPS vía Earth Engine para el centroide de la finca ({centroide['lat']:.5f}, {centroide['lon']:.5f})...")
    resultado = estimar_lluvia_finca(centroide["lat"], centroide["lon"])

    if not resultado:
        print("⚠️ Sin cobertura CHIRPS reciente para la ventana solicitada; nada que guardar esta semana.")
        db.close()
        return 0

    db.registrar_lectura_lluvia_satelital(
        resultado["mm_estimado"],
        fecha=resultado["fecha_fin"],
        dias_acumulados=resultado["dias_acumulados"],
        fuente=resultado["fuente"],
    )
    db.close()
    print(
        f"✅ Lluvia estimada guardada: {resultado['mm_estimado']} mm en los últimos "
        f"{resultado['dias_acumulados']} días (referencia {resultado['fecha_fin']})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
