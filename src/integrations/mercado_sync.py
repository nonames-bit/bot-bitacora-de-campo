"""Sincronización automática de indicadores de mercado.

Lo único que se consulta de verdad en internet es:
1. Dólar TRM oficial: API de Datos Abiertos de Colombia (Superintendencia Financiera)
   con DolarAPI como respaldo.
2. Titulares de noticias ganaderas (RSS de Google Noticias).

Los precios de subastas, leche e insumos NO tienen fuente automática: se muestran
los valores de referencia de la semilla (``mercado_semilla.py``) hasta que el
usuario anote precios reales con "Actualizar Precios" (fuente ``MANUAL``).
Antes este módulo re-guardaba cada día una tabla fija de precios con la fecha
del día y fuente "AUTOMATICO", lo que los hacía parecer cotizaciones reales
(siempre con variación 0%); ``limpiar_precios_fijos_automaticos`` borra esas filas.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

SOCRATA_TRM_URL = "https://www.datos.gov.co/resource/mcec-87by.json?$limit=1&$order=vigenciadesde%20DESC"
DOLARAPI_TRM_URL = "https://co.dolarapi.com/v1/trm"
GOOGLE_NEWS_GANADO_URL = (
    "https://news.google.com/rss/search?q=precio+ganado+subasta+fedegan+colombia&hl=es-419&gl=CO&ceid=CO:es-419"
)

def consultar_trm_oficial() -> dict[str, Any]:
    """Consulta la TRM oficial del día en tiempo real.
    
    1. Intenta la API Socrata de Datos Abiertos Colombia (Superfinanciera / Banco de la República).
    2. En caso de fallo o timeout, consulta DolarAPI Colombia.
    3. Retorna diccionario con valor, fecha y fuente oficial.
    """
    # 1. Datos Abiertos Colombia (Socrata)
    try:
        req = urllib.request.Request(
            SOCRATA_TRM_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BitacoraCampo/1.0"}
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0 and "valor" in data[0]:
                val = float(data[0]["valor"])
                fec_str = (data[0].get("vigenciadesde") or "")[:10] or date.today().isoformat()
                return {
                    "valor": round(val, 2),
                    "fecha": fec_str,
                    "fuente": "AUTOMATICO: Datos Abiertos (Superintendencia Financiera de Colombia)",
                    "ok": True,
                }
    except Exception as e:
        logger.warning("Fallo al consultar TRM en datos.gov.co: %s", e)

    # 2. Fallback DolarAPI Colombia
    try:
        req = urllib.request.Request(
            DOLARAPI_TRM_URL,
            headers={"User-Agent": "Mozilla/5.0 BitacoraCampo/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and "valor" in data:
                val = float(data["valor"])
                fec_str = (data.get("fechaActualizacion") or "")[:10] or date.today().isoformat()
                return {
                    "valor": round(val, 2),
                    "fecha": fec_str,
                    "fuente": "AUTOMATICO: DolarAPI (Banco de la República)",
                    "ok": True,
                }
    except Exception as e:
        logger.warning("Fallo al consultar TRM en dolarapi.com: %s", e)

    # 3. Fallback referencial
    return {
        "valor": 4085.0,
        "fecha": date.today().isoformat(),
        "fuente": "AUTOMATICO: Banco de la República (Referencia Base)",
        "ok": False,
    }


_CACHE_TITULARES: dict[str, Any] = {"fecha": None, "items": []}


def consultar_titulares_mercado() -> list[dict[str, str]]:
    """Consulta los titulares de noticias ganaderas y subastas más recientes vía RSS (cacheados por día)."""
    hoy = date.today().isoformat()
    if _CACHE_TITULARES["fecha"] == hoy and _CACHE_TITULARES["items"]:
        return _CACHE_TITULARES["items"]

    try:
        req = urllib.request.Request(
            GOOGLE_NEWS_GANADO_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BitacoraCampo/1.0"}
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            xml = resp.read().decode("utf-8", errors="ignore")

        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
        noticias: list[dict[str, str]] = []
        for item in items[:6]:
            t_match = re.search(r"<title>(.*?)</title>", item)
            l_match = re.search(r"<link>(.*?)</link>", item)
            d_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
            if t_match and l_match:
                tit = t_match.group(1).replace("<![CDATA[", "").replace("]]>", "").strip()
                link = l_match.group(1).strip()
                fec = d_match.group(1).strip() if d_match else ""
                noticias.append({"titulo": tit, "enlace": link, "fecha": fec})

        _CACHE_TITULARES["fecha"] = hoy
        _CACHE_TITULARES["items"] = noticias
        return noticias
    except Exception as e:
        logger.warning("No se pudieron consultar titulares de noticias ganaderas: %s", e)
        return _CACHE_TITULARES.get("items") or []


def limpiar_precios_fijos_automaticos(db: Any) -> int:
    """Borra las filas "AUTOMATICO" que no son la TRM real.

    Eran copias diarias de una tabla fija (subastas, leche, insumos) y la TRM
    de respaldo (4.085) guardada cuando no había internet. Los precios MANUAL
    y la semilla de referencia no se tocan.
    """
    cur = db.execute(
        "DELETE FROM precios_mercado WHERE fuente LIKE 'AUTOMATICO%' "
        "AND (producto <> 'DOLAR_TRM' OR fuente LIKE '%Referencia Base%')"
    )
    return max(cur.rowcount, 0)


def sincronizar_precios_mercado(db: Any, forzar: bool = False) -> dict[str, Any]:
    """Actualiza la TRM oficial del día (único indicador con fuente automática).

    Args:
        db: Instancia de Database (SQLite).
        forzar: Si es True, consulta aunque ya exista la TRM de hoy.
    """
    hoy_iso = date.today().isoformat()
    # Con la tabla vacía se siembra primero la referencia: si la TRM entrara
    # antes, la tabla ya no estaría vacía y las subastas quedarían sin datos.
    db.sembrar_precios_mercado_iniciales()
    try:
        limpiar_precios_fijos_automaticos(db)
    except Exception as e:
        logger.warning("No se pudieron limpiar precios fijos automáticos: %s", e)

    if not forzar:
        row_hoy = db.query_one(
            "SELECT id FROM precios_mercado WHERE fecha = ? AND producto = 'DOLAR_TRM' "
            "AND fuente LIKE 'AUTOMATICO%' LIMIT 1",
            (hoy_iso,)
        )
        if row_hoy:
            return {
                "ok": True,
                "actualizado": False,
                "mensaje": f"La TRM de hoy ({hoy_iso}) ya está guardada.",
                "fecha": hoy_iso,
            }

    trm_info = consultar_trm_oficial()
    noticias = consultar_titulares_mercado()
    if not trm_info.get("ok"):
        # Sin internet: no guardar el valor de respaldo como si fuera la TRM del día.
        return {
            "ok": True,
            "actualizado": False,
            "fecha": hoy_iso,
            "mensaje": "No se pudo consultar la TRM oficial (sin conexión). Se mantiene el último dato.",
            "noticias": noticias,
        }

    trm_val = trm_info["valor"]
    trm_fuente = trm_info["fuente"]
    trm_fecha = trm_info.get("fecha") or hoy_iso
    db.execute(
        "DELETE FROM precios_mercado WHERE fecha = ? AND producto = 'DOLAR_TRM' AND fuente LIKE 'AUTOMATICO%'",
        (hoy_iso,),
    )
    db.registrar_precio_mercado(
        plaza="COLOMBIA",
        producto="DOLAR_TRM",
        precio_promedio=trm_val,
        precio_maximo=None,
        precio_minimo=None,
        unidad="COP/USD",
        fuente=trm_fuente,
        fecha=hoy_iso,
        notas=f"Tasa Representativa del Mercado oficial (vigente {trm_fecha})",
    )

    return {
        "ok": True,
        "actualizado": True,
        "fecha": hoy_iso,
        "trm": trm_val,
        "trm_fuente": trm_fuente,
        "filas_actualizadas": 1,
        "mensaje": f"TRM oficial actualizada: ${trm_val:,.2f} COP. Los precios de subastas se anotan con 'Actualizar Precios'.",
        "noticias": noticias,
    }
