"""Agente extractor Gemini para el dominio MANEJO (pesaje, traslado, movimiento)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ..parsers.event_parser import ParsedEvent, es_tipo_evento_llm_valido
from ..utils import a_float, iso, parse_fecha, to_date
from .gemini_client import GeminiClient
from .normalizacion import normalizar_tag
from .schemas import SCHEMA_MANEJO

SYSTEM_PROMPT = """Eres un agente extractor especializado en eventos de MANEJO
de hato para una bitácora de campo ganadero. Extrae eventos estructurados en
JSON a partir de notas de voz o texto en español enviadas por mayordomos.

Los tipos de evento posibles en este dominio son:

1. 'pesaje':
   - animal_tag: tag del animal
   - datos:
     - peso_kg: float (o null)
     - evento: 'Control', 'DESTETE', o 'NACIMIENTO' (por defecto 'Control')

2. 'traslado':
   - animal_tag: tag del animal o null si es por lote
   - datos:
     - lote: identificador del lote si aplica (o null)
     - potrero_origen: nombre/número del potrero de salida (o null)
     - potrero_destino: nombre/número del potrero de llegada (o null)

3. 'movimiento':
   - animal_tag: tag si aplica (o null)
   - datos:
     - tipo_movimiento: 'COMPRA', 'VENTA', 'SALIDA', o 'ENTRADA'
     - cantidad: int de animales si es grupo (o null)
     - procedencia_destino: origen o destino (o null)

Si la nota contiene MÚLTIPLES eventos de este dominio, extrae TODOS en la
lista 'eventos'. Responde ÚNICAMENTE JSON con la estructura
{"eventos": [{"tipo": "pesaje", "animal_tag": "47", "fecha": null, "datos": {...}}]}.
"""


def parse(
    texto: str,
    hoy: Optional[date] = None,
    client: Optional[GeminiClient] = None,
) -> Optional[list[ParsedEvent]]:
    """Extrae eventos de manejo vía Gemini. None si no disponible/falló/vacío."""
    cli = client or GeminiClient()
    if not cli.is_available() or not texto or not texto.strip():
        return None

    fecha_base = hoy or date.today()
    user_text = f"Nota de campo: «{texto}»\nFecha actual de referencia: {iso(fecha_base)}"

    resultado = cli.generate_structured(SYSTEM_PROMPT, user_text, SCHEMA_MANEJO)
    if not resultado or "eventos" not in resultado:
        return None
    eventos_raw = resultado["eventos"]
    if not eventos_raw:
        return None

    eventos: list[ParsedEvent] = []
    for item in eventos_raw:
        tipo = item.get("tipo")
        # Defensa anti prompt-injection (P6): un tipo fuera de la lista blanca
        # central se descarta (el helper registra el warning de rechazo) y el
        # agente solo acepta los tipos de su propio dominio.
        if not es_tipo_evento_llm_valido(tipo) or tipo not in ("pesaje", "traslado", "movimiento"):
            continue

        tag = normalizar_tag(item.get("animal_tag"))

        fecha_raw = item.get("fecha")
        if fecha_raw:
            f_obj = parse_fecha(str(fecha_raw), fecha_base) or to_date(fecha_raw)
            fecha = iso(f_obj or fecha_base)
        else:
            fecha = iso(parse_fecha(texto, fecha_base) or fecha_base)

        datos = _limpiar_datos(tipo, dict(item.get("datos") or {}))
        eventos.append(ParsedEvent(tipo=tipo, texto=texto, animal_tag=tag, fecha=fecha, datos=datos))

    return eventos or None


def _limpiar_datos(tipo: str, datos: dict) -> dict:
    if tipo == "pesaje":
        if "peso_kg" in datos:
            datos["peso_kg"] = a_float(datos["peso_kg"])
        if not datos.get("evento"):
            datos["evento"] = "Control"

    elif tipo == "movimiento":
        if "cantidad" in datos and datos["cantidad"] is not None:
            try:
                datos["cantidad"] = int(datos["cantidad"])
            except (ValueError, TypeError):
                pass

    return datos
