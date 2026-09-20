"""Pronóstico del clima para el Despacho Matutino (Open-Meteo, sin API key).

Fuente gratuita: https://open-meteo.com/ (sin clave, sin registro).
Todo el módulo es defensivo: ninguna función lanza por fallos de red,
de disco o de datos — devuelven ``None`` / listas vacías según el caso.
"""
from __future__ import annotations

import html
import json
import logging
import os
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bitacora.pronostico")

# URL base de Open-Meteo (sin API key, incluye telemetría en tiempo real y diaria).
OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=temperature_2m,relative_humidity_2m,precipitation,rain,showers,weather_code"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"
    "&timezone=auto&forecast_days={dias}"
)

# TTL por defecto del cache en disco (horas).
CACHE_TTL_HORAS = 6.0


def _ruta_cache() -> Path:
    """Ruta del cache en disco (permite override vía env para tests)."""
    override = os.getenv("PRONOSTICO_CACHE")
    if override:
        return Path(override)
    # src/engine/pronostico.py -> raíz del proyecto (3 niveles arriba).
    raiz = Path(__file__).resolve().parent.parent.parent
    return raiz / "data" / "pronostico_cache.json"


def _a_float(valor: object, default: float = 0.0) -> float:
    """Convierte un valor a float de forma tolerante (None/inválido -> default)."""
    try:
        if valor is None:
            return default
        return float(valor)
    except (TypeError, ValueError):
        return default


def _fecha_de(valor: object) -> Optional[date]:
    """Normaliza fecha (date o ISO str) a date; None si no se puede."""
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor.strip()[:10])
        except ValueError:
            return None
    return None


def _dd_mm(fecha: object) -> str:
    """Formato corto DD-MM para mensajes de campo."""
    d = _fecha_de(fecha)
    if d is None:
        return str(fecha)
    return f"{d.day:02d}-{d.month:02d}"


def _parsear_respuesta_open_meteo(payload: dict, lat: float = 0.0, lon: float = 0.0) -> dict:
    """Normaliza la respuesta cruda de Open-Meteo a dict interno.

    Estructura real de Open-Meteo: ``daily.time[]``, ``daily.temperature_2m_max[]``,
    ``daily.temperature_2m_min[]``, ``daily.precipitation_sum[]``,
    ``daily.precipitation_probability_max[]`` (esta última puede venir null),
    y ``current`` con condiciones meteorológicas en tiempo real.
    """
    daily = payload.get("daily") if isinstance(payload, dict) else None
    if not isinstance(daily, dict):
        return {"lat": lat, "lon": lon, "dias": [], "current": None}
    times = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    lluv = daily.get("precipitation_sum") or []
    prob = daily.get("precipitation_probability_max")
    if not isinstance(prob, list):
        prob = [None] * len(times)
    dias = []
    for i, f in enumerate(times):
        fecha = _fecha_de(f)
        if fecha is None:
            continue
        p = prob[i] if i < len(prob) else None
        try:
            p = None if p is None else float(p)
        except (TypeError, ValueError):
            p = None
        dias.append(
            {
                "fecha": fecha,
                "temp_max_c": _a_float(tmax[i] if i < len(tmax) else None),
                "temp_min_c": _a_float(tmin[i] if i < len(tmin) else None),
                "lluvia_mm": _a_float(lluv[i] if i < len(lluv) else None),
                "prob_lluvia_pct": p,
            }
        )

    current_raw = payload.get("current") if isinstance(payload, dict) else None
    current = None
    if isinstance(current_raw, dict):
        wcode = current_raw.get("weather_code")
        precip = _a_float(current_raw.get("precipitation"))
        rain = _a_float(current_raw.get("rain"))
        showers = _a_float(current_raw.get("showers"))
        # Códigos WMO de precipitación activa:
        # 51,53,55: llovizna; 61,63,65: lluvia; 66,67: lluvia helada; 80,81,82: chubascos; 95,96,99: tormenta
        wmo_lluvia = wcode in {51, 53, 55, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
        esta_lloviendo = bool((precip > 0.1 or rain > 0.1 or showers > 0.1) or wmo_lluvia)
        current = {
            "time": current_raw.get("time"),
            "temp_c": _a_float(current_raw.get("temperature_2m")),
            "humedad_pct": current_raw.get("relative_humidity_2m"),
            "lluvia_mm": precip,
            "weather_code": wcode,
            "esta_lloviendo": esta_lloviendo,
        }

    return {"lat": lat, "lon": lon, "dias": dias, "current": current}


def coordenadas_finca(db) -> Optional[tuple[float, float]]:
    """Promedio de centroides de potreros con geometría; fallback a env.

    Promedia ``centroide_lat/lon`` de potreros con ``geom_wkt_4326`` no nulo.
    Si no hay potreros georreferenciados, usa ``FINCA_LAT`` / ``FINCA_LON``.
    Devuelve None si no hay nada. Nunca lanza.
    """
    try:
        filas = db.query(
            "SELECT centroide_lat, centroide_lon FROM potreros "
            "WHERE geom_wkt_4326 IS NOT NULL "
            "AND centroide_lat IS NOT NULL AND centroide_lon IS NOT NULL"
        )
        lats = [float(r["centroide_lat"]) for r in filas if r["centroide_lat"] is not None]
        lons = [float(r["centroide_lon"]) for r in filas if r["centroide_lon"] is not None]
        if lats and lons and len(lats) == len(lons):
            return (sum(lats) / len(lats), sum(lons) / len(lons))
    except Exception as e:  # noqa: BLE001 - función defensiva, nunca lanzar
        logger.debug("coordenadas_finca (DB) falló: %s", e)
    # Fallback: variables de entorno.
    try:
        lat_s = os.getenv("FINCA_LAT")
        lon_s = os.getenv("FINCA_LON")
        if lat_s and lon_s:
            return (float(lat_s), float(lon_s))
    except (TypeError, ValueError):
        pass
    return None


def obtener_pronostico(lat: float, lon: float, dias: int = 7, timeout: float = 8.0) -> Optional[dict]:
    """Consulta Open-Meteo (sin API key) y devuelve dict normalizado o None.

    Usa ``urllib.request`` (sin dependencias nuevas). Nunca lanza.
    """
    try:
        url = OPEN_METEO_URL.format(lat=lat, lon=lon, dias=int(dias))
        req = urllib.request.Request(url, headers={"User-Agent": "bitacora-ganadera/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            crudo = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(crudo)
        pron = _parsear_respuesta_open_meteo(payload, lat=lat, lon=lon)
        if not pron.get("dias"):
            return None
        return pron
    except Exception as e:  # noqa: BLE001 - red/JSON: degradar a None
        logger.debug("obtener_pronostico falló: %s", e)
        return None


def _serializar_pron(pron: dict) -> dict:
    """Convierte fechas date -> ISO str para guardar el cache JSON."""
    dias = []
    for d in pron.get("dias", []):
        f = d.get("fecha")
        dias.append({**d, "fecha": f.isoformat() if isinstance(f, (date, datetime)) else str(f)})
    return {**pron, "dias": dias}


def _deserializar_pron(pron: dict) -> dict:
    """Convierte fechas ISO str -> date al leer el cache JSON."""
    dias = []
    for d in pron.get("dias", []):
        f = _fecha_de(d.get("fecha"))
        dias.append({**d, "fecha": f if f is not None else d.get("fecha")})
    return {**pron, "dias": dias}


def obtener_pronostico_para_despacho(db, cache_ttl_horas: float = CACHE_TTL_HORAS) -> Optional[dict]:
    """Coordenadas -> cache en disco (TTL) -> API. Nunca lanza.

    Si el cache está vigente (TTL) se devuelve directo. Si la API falla y hay
    cache viejo, se devuelve el viejo marcando ``desactualizado_horas`` para
    que el formateo avise. Si nada disponible, None.
    """
    try:
        coords = coordenadas_finca(db)
        if coords is None:
            return None
        lat, lon = coords
        ruta = _ruta_cache()
        cache: Optional[dict] = None
        if ruta.exists():
            try:
                cache = json.loads(ruta.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001 - cache corrupto: ignorar
                logger.debug("Cache de pronóstico ilegible: %s", e)
                cache = None
        ahora = datetime.now()
        if cache and isinstance(cache, dict) and cache.get("pron"):
            try:
                guardado = datetime.fromisoformat(str(cache["guardado_en"]))
                edad_h = (ahora - guardado).total_seconds() / 3600.0
            except (ValueError, TypeError, KeyError):
                edad_h = float("inf")
            # Cache vigente y coordenadas cercanas: devolver directo.
            try:
                misma_zona = abs(float(cache.get("lat", lat)) - lat) < 0.5 and abs(
                    float(cache.get("lon", lon)) - lon
                ) < 0.5
            except (TypeError, ValueError):
                misma_zona = True
            if edad_h <= cache_ttl_horas and misma_zona:
                return _deserializar_pron(cache["pron"])
        # Ir a la API.
        pron = obtener_pronostico(lat, lon)
        if pron is not None:
            try:
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(
                    json.dumps(
                        {"guardado_en": ahora.isoformat(), "lat": lat, "lon": lon, "pron": _serializar_pron(pron)},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception as e:  # noqa: BLE001 - no poder guardar no es fatal
                logger.debug("No se pudo guardar cache de pronóstico: %s", e)
            return pron
        # API falló: usar cache viejo si existe, marcando antigüedad.
        if cache and isinstance(cache, dict) and cache.get("pron"):
            try:
                guardado = datetime.fromisoformat(str(cache["guardado_en"]))
                edad_h = (ahora - guardado).total_seconds() / 3600.0
            except (ValueError, TypeError, KeyError):
                edad_h = 99.0
            viejo = _deserializar_pron(cache["pron"])
            viejo["desactualizado_horas"] = round(edad_h, 1)
            return viejo
        return None
    except Exception as e:  # noqa: BLE001 - garantía total: nunca romper el despacho
        logger.debug("obtener_pronostico_para_despacho falló: %s", e)
        return None


def interpretar_pronostico(pron: dict) -> list[str]:
    """Reglas deterministas (sin LLM) -> recomendaciones prácticas de campo."""
    dias = pron.get("dias", []) if isinstance(pron, dict) else []
    if not dias:
        return []
    recs: list[str] = []

    # 1. Lluvia hoy o mañana: no fumigar ni tópicos.
    for d in dias[:2]:
        mm = _a_float(d.get("lluvia_mm"))
        prob = d.get("prob_lluvia_pct")
        try:
            prob_f = None if prob is None else float(prob)
        except (TypeError, ValueError):
            prob_f = None
        if mm > 5 or (prob_f is not None and prob_f >= 70):
            prob_txt = f"{prob_f:.0f}" if prob_f is not None else "N/D"
            recs.append(
                f"🌧️ Lluvia probable ({mm:.1f} mm / {prob_txt}%): "
                "NO fumigar ni aplicar medicamentos tópicos hoy/mañana "
                "— la lluvia lava el producto."
            )
            break

    # 2. Ventana seca: 3+ días consecutivos con lluvia < 2 mm.
    mejor_n = 0
    mejor_ini: Optional[object] = None
    racha = 0
    ini: Optional[object] = None
    for d in dias:
        if _a_float(d.get("lluvia_mm")) < 2:
            if racha == 0:
                ini = d.get("fecha")
            racha += 1
            if racha > mejor_n:
                mejor_n = racha
                mejor_ini = ini
        else:
            racha = 0
            ini = None
    if mejor_n >= 3:
        recs.append(
            f"☀️ Ventana seca de {mejor_n} días (desde {_dd_mm(mejor_ini)}): "
            "buena para heno, ensilaje o trabajos de cerca."
        )

    # 3 y 4. Acumulada 7 días.
    total = sum(_a_float(d.get("lluvia_mm")) for d in dias[:7])
    if total >= 60:
        recs.append(
            f"💧 Lluvia fuerte acumulada ({total:.1f} mm en 7 días): "
            "el pasto crecerá rápido; revisa rotación y caminos."
        )
    elif total < 5:
        recs.append(
            f"🏜️ Semana muy seca ({total:.1f} mm): "
            "vigila agua en bebederos y ajusta la carga del potrero."
        )

    # 5. Estrés térmico: máx >= 32 °C.
    calientes = [d for d in dias if _a_float(d.get("temp_max_c")) >= 32]
    if calientes:
        pico = max(calientes, key=lambda d: _a_float(d.get("temp_max_c")))
        recs.append(
            f"🥵 Días calurosos (máx {_a_float(pico.get('temp_max_c')):.0f}°C el {_dd_mm(pico.get('fecha'))}): "
            "garantiza sombra y agua; adelanta el ordeño."
        )

    # 6. Frío para crías: mín <= 8 °C.
    frias = [d for d in dias if _a_float(d.get("temp_min_c")) <= 8]
    if frias:
        pico_f = min(frias, key=lambda d: _a_float(d.get("temp_min_c")))
        recs.append(
            f"🥶 Noches frías (mín {_a_float(pico_f.get('temp_min_c')):.0f}°C): "
            "revisa terneros recién nacidos."
        )

    # 7. Semana estable.
    if not recs:
        recs.append("🌤️ Semana estable: sin alertas climáticas para la operación.")
    return recs


def formatear_pronostico_despacho(pron: Optional[dict]) -> str:
    """Bloque HTML del despacho con pronóstico 7 días; "" si no hay datos."""
    if not isinstance(pron, dict) or not pron.get("dias"):
        return ""
    dias = pron["dias"]
    try:
        tmax = max(_a_float(d.get("temp_max_c")) for d in dias)
        total = sum(_a_float(d.get("lluvia_mm")) for d in dias[:7])
        mojado = max(dias[:7], key=lambda d: _a_float(d.get("lluvia_mm")))
        mojado_mm = _a_float(mojado.get("lluvia_mm"))
        lineas = [
            "⛅ <b>CLIMA & PRONÓSTICO (7 DÍAS):</b>",
            f"☀️ Máx {tmax:.0f}°C · 🌧️ Lluvia estimada: {total:.1f} mm "
            f"· 💧 Día más lluvioso: {_dd_mm(mojado.get('fecha'))} ({mojado_mm:.1f} mm)",
        ]
        for r in interpretar_pronostico(pron):
            # Las recomendaciones son texto propio (sin input de usuario);
            # se escapa por seguridad HTML de Telegram.
            lineas.append(f"• {html.escape(r)}")
        if pron.get("desactualizado_horas") is not None:
            try:
                h = float(pron["desactualizado_horas"])
                lineas.append(f"⚠️ <i>Datos del pronóstico de hace {h:.0f} h.</i>")
            except (TypeError, ValueError):
                pass
        return "\n".join(lineas)
    except Exception as e:  # noqa: BLE001 - nunca romper el despacho por clima
        logger.debug("formatear_pronostico_despacho falló: %s", e)
        return ""


def formatear_tabla_pronostico(pron: Optional[dict]) -> str:
    """Mini tabla diaria (día, máx/mín, mm, % prob) para /pronostico y /clima."""
    if not isinstance(pron, dict) or not pron.get("dias"):
        return ""
    lineas = ["📅 <b>Detalle diario:</b>"]
    for d in pron["dias"][:7]:
        prob = d.get("prob_lluvia_pct")
        try:
            prob_txt = f"{float(prob):.0f}%" if prob is not None else "—"
        except (TypeError, ValueError):
            prob_txt = "—"
        lineas.append(
            f"• <b>{_dd_mm(d.get('fecha'))}</b> 🌡️ {_a_float(d.get('temp_max_c')):.0f}/{_a_float(d.get('temp_min_c')):.0f}°C "
            f"🌧️ {_a_float(d.get('lluvia_mm')):.1f} mm ({prob_txt})"
        )
    return "\n".join(lineas)
