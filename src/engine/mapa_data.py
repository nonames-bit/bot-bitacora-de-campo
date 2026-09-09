"""src/engine/mapa_data.py
Motor de datos geoespaciales para el Mapa Satelital Interactivo de la PWA.
Procesa polígonos WGS84 de los potreros (GeoJSON), lecturas de vigor NDVI/SAR,
ocupación de ganado en vivo y posiciones satelitales GPS recientes de operarios.
"""

from datetime import date, datetime, timedelta
import json
import logging
from typing import Any, Optional

from shapely import wkt as shapely_wkt
from shapely.geometry import mapping as shapely_mapping

from ..db.database import Database

logger = logging.getLogger(__name__)

# Paleta de colores para Vigor Forrajero (NDVI / SAR) -- mismas 4 categorías y
# colores que clasificar_ndvi() (src/gis/sentinel_ndvi.py) y el mapa de
# potreros en matplotlib (src/engine/charts.py::_COLOR_POR_CATEGORIA_NDVI).
# Las claves deben calzar EXACTO con lo que devuelve clasificar_ndvi(): antes
# tenían nombres distintos ("EXCELENTE / DENSO", "BUENO / EN CRECIMIENTO",
# etc.) que nunca hacían match, así que todo potrero cadía al color por
# defecto (verde) sin importar su vigor real.
COLORES_NDVI = {
    "EXCELENTE": "#2e7d32",  # Verde
    "ÓPTIMO / REPOSO": "#f9a825",  # Amarillo
    "ESTRÉS / BAJA BIOMASA": "#ef6c00",  # Naranja
    "CRÍTICO / SUELO DESNUDO": "#c62828",  # Rojo
}

def color_voisin(n_animales: int, dias_ocupacion: Optional[int], dias_reposo: Optional[int]) -> tuple[str, str]:
    """Retorna (color_hex, estado_texto) según las Leyes de André Voisin."""
    if n_animales > 0:
        dias_o = dias_ocupacion if dias_ocupacion is not None else 1
        if dias_o <= 3:
            return "#2e7d32", f"Ocupado ({dias_o}d de ocupación — En norma)"
        else:
            return "#c62828", f"Alerta Voisin ({dias_o}d de ocupación — Sobrepastoreo >3d)"
    else:
        dias_r = dias_reposo if dias_reposo is not None else 0
        if dias_r >= 30:
            return "#1565c0", f"Listo para pastoreo ({dias_r}d de reposo)"
        elif dias_r >= 20:
            return "#00838f", f"En recuperación ({dias_r}d de reposo)"
        else:
            return "#ef6c00", f"Recién desocupado ({dias_r}d de reposo)"


def datos_mapa_finca(db: Database) -> dict[str, Any]:
    """Genera el GeoJSON completo de la finca, potreros, ganado y usuarios activos."""
    hoy_iso = date.today().isoformat()
    hace_24h_iso = (date.today() - timedelta(days=1)).isoformat()

    # 1. Potreros con geometría real WGS84
    potreros_raw = db.query(
        """SELECT id, nombre, codigo, area_has, geom_wkt_4326, centroide_lat, centroide_lon,
                  dias_ocupacion, dias_reposo
           FROM potreros WHERE geom_wkt_4326 IS NOT NULL ORDER BY nombre"""
    )

    # 2. Conteo de animales activos por potrero
    animales_filas = db.query(
        """SELECT potrero_id, COUNT(*) AS n
           FROM animales
           WHERE estado = 'ACTIVO' AND potrero_id IS NOT NULL
           GROUP BY potrero_id"""
    )
    animales_por_potrero = {r["potrero_id"]: r["n"] for r in animales_filas}

    # Muestra de tags por potrero (hasta 8 animales para tooltip)
    tags_filas = db.query(
        """SELECT potrero_id, tag
           FROM animales
           WHERE estado = 'ACTIVO' AND potrero_id IS NOT NULL
           ORDER BY tag ASC"""
    )
    tags_por_potrero: dict[int, list[str]] = {}
    for r in tags_filas:
        p_id = r["potrero_id"]
        tags_por_potrero.setdefault(p_id, [])
        if len(tags_por_potrero[p_id]) < 8:
            tags_por_potrero[p_id].append(r["tag"])

    # 3. Última lectura NDVI / SAR satelital por potrero
    resumen_ndvi = db.resumen_ndvi_finca()
    ndvi_por_potrero = {p["potrero_id"]: p for p in resumen_ndvi.get("potreros", [])}

    potreros_geojson = []
    lats, lons = [], []

    for p in potreros_raw:
        p_id = p["id"]
        wkt_str = p["geom_wkt_4326"]
        try:
            geom = shapely_wkt.loads(wkt_str)
            geojson_geom = shapely_mapping(geom)
        except Exception as e:
            logger.warning("Error parseando WKT para potrero %s: %s", p["nombre"], e)
            continue

        c_lat = float(p["centroide_lat"]) if p["centroide_lat"] is not None else None
        c_lon = float(p["centroide_lon"]) if p["centroide_lon"] is not None else None
        if c_lat and c_lon:
            lats.append(c_lat)
            lons.append(c_lon)

        n_anim = animales_por_potrero.get(p_id, 0)
        tags_preview = tags_por_potrero.get(p_id, [])

        ndvi_info = ndvi_por_potrero.get(p_id) or {}
        categoria_ndvi = ndvi_info.get("categoria") or "ÓPTIMO / REPOSO"
        color_n = COLORES_NDVI.get(categoria_ndvi, "#2e7d32")

        c_voisin, estado_v = color_voisin(n_anim, p["dias_ocupacion"], p["dias_reposo"])

        potreros_geojson.append({
            "type": "Feature",
            "id": p_id,
            "geometry": geojson_geom,
            "properties": {
                "id": p_id,
                "nombre": p["nombre"],
                "codigo": p["codigo"] or p["nombre"],
                "area_has": round(float(p["area_has"] or 0), 2),
                "centroide": [c_lat, c_lon] if (c_lat and c_lon) else None,
                "animales_count": n_anim,
                "animales_tags": tags_preview,
                "dias_ocupacion": p["dias_ocupacion"],
                "dias_reposo": p["dias_reposo"],
                "estado_voisin": estado_v,
                "color_voisin": c_voisin,
                "ndvi_valor": ndvi_info.get("ndvi"),
                "biomasa_kg_ha": ndvi_info.get("biomasa_kg_ha"),
                "categoria_ndvi": categoria_ndvi,
                "color_ndvi": color_n,
                "fecha_ndvi": ndvi_info.get("fecha"),
                "fuente_ndvi": ndvi_info.get("fuente", "Satelital"),
            }
        })

    # Bounding box de la finca
    bbox = None
    centroide_finca = [3.40, -74.06]
    if lats and lons:
        bbox = [[min(lats) - 0.003, min(lons) - 0.003], [max(lats) + 0.003, max(lons) + 0.003]]
        centroide_finca = [sum(lats) / len(lats), sum(lons) / len(lons)]

    # 4. Usuarios con telemetría GPS (prioriza últimas 24h, o última conocida)
    filas_usuarios_pts = db.query(
        """SELECT t.id, t.user_id, t.usuario_nombre, t.rol, t.fecha, t.hora,
                  t.lat, t.lon, t.precision_m, t.potrero_nombre, t.evento_origen, t.creado_en
           FROM telemetria_gps t
           INNER JOIN (
               SELECT user_id, MAX(id) AS max_id
               FROM telemetria_gps
               WHERE fecha >= ?
               GROUP BY user_id
           ) ult ON t.id = ult.max_id
           ORDER BY t.hora DESC""",
        (hace_24h_iso,)
    )
    if not filas_usuarios_pts:
        filas_usuarios_pts = db.query(
            """SELECT t.id, t.user_id, t.usuario_nombre, t.rol, t.fecha, t.hora,
                      t.lat, t.lon, t.precision_m, t.potrero_nombre, t.evento_origen, t.creado_en
               FROM telemetria_gps t
               INNER JOIN (
                   SELECT user_id, MAX(id) AS max_id
                   FROM telemetria_gps
                   GROUP BY user_id
               ) ult ON t.id = ult.max_id
               ORDER BY t.fecha DESC, t.hora DESC"""
        )

    presencias = {str(r["user_id"]): dict(r) for r in db.query("SELECT * FROM usuarios_presencia")}
    try:
        from ..server.auth import Auth
        usuarios_meta = {str(u.get("user_id")): u for u in Auth().usuarios}
    except Exception:
        usuarios_meta = {}

    ahora_dt = datetime.now()
    usuarios_activos = []

    for pt in filas_usuarios_pts:
        uid_str = str(pt["user_id"])
        meta = usuarios_meta.get(uid_str) or {}
        pres = presencias.get(uid_str) or {}

        # Determinar si está en línea (presencia en últimos 30 min)
        en_linea = False
        minutos_hace = None
        if pt["fecha"] == hoy_iso and pt["hora"]:
            try:
                hora_pt_dt = datetime.strptime(f"{pt['fecha']} {pt['hora'][:8]}", "%Y-%m-%d %H:%M:%S")
                diff = (ahora_dt - hora_pt_dt).total_seconds() / 60.0
                minutos_hace = max(0, int(diff))
                en_linea = minutos_hace <= 30
            except Exception:
                minutos_hace = None

        # Historial de puntos de hoy para trazar rastro/camino
        pts_hoy = db.query(
            """SELECT lat, lon, hora, potrero_nombre
               FROM telemetria_gps
               WHERE user_id = ? AND fecha = ?
               ORDER BY hora ASC, id ASC LIMIT 50""",
            (pt["user_id"], hoy_iso)
        )

        lat_u = float(pt["lat"])
        lon_u = float(pt["lon"])
        dist_finca_km = (((lat_u - centroide_finca[0]) ** 2 + (lon_u - centroide_finca[1]) ** 2) ** 0.5) * 111.0
        en_finca = dist_finca_km <= 15.0

        usuarios_activos.append({
            "user_id": pt["user_id"],
            "nombre": meta.get("nombre") or pt["usuario_nombre"] or f"Usuario {pt['user_id']}",
            "rol": meta.get("rol") or pt["rol"] or "TRABAJADOR",
            "avatar": meta.get("avatar") or "vaquero_clasico",
            "lat": lat_u,
            "lon": lon_u,
            "precision_m": round(float(pt["precision_m"] or 0), 1),
            "potrero_actual": pt["potrero_nombre"] or ("Área de la Finca" if en_finca else "Fuera de la Finca"),
            "en_finca": en_finca,
            "dist_finca_km": round(dist_finca_km, 1),
            "fecha": pt["fecha"],
            "hora": pt["hora"],
            "minutos_hace": minutos_hace,
            "en_linea": en_linea,
            "rastro_hoy": [[float(p["lat"]), float(p["lon"]), p["hora"], p["potrero_nombre"] or ""] for p in pts_hoy]
        })

    return {
        "ok": True,
        "finca": {
            "centroide": centroide_finca,
            "bbox": bbox,
            "total_potreros": len(potreros_geojson),
        },
        "potreros_geojson": {
            "type": "FeatureCollection",
            "features": potreros_geojson,
        },
        "usuarios_activos": usuarios_activos,
        "fecha": hoy_iso,
    }
