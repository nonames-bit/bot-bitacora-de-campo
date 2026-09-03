"""Agente extractor Gemini para el dominio SANIDAD (tratamiento, muerte)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ..parsers import nlp_engine as nlu
from ..parsers.event_parser import ParsedEvent, es_tipo_evento_llm_valido
from ..utils import iso, parse_fecha, to_date
from .gemini_client import GeminiClient
from .normalizacion import normalizar_tag
from .schemas import SCHEMA_SANIDAD

SYSTEM_PROMPT = """Eres un agente extractor especializado en eventos de SANIDAD
animal para una bitácora de campo ganadero. Extrae eventos estructurados en
JSON a partir de notas de voz o texto en español enviadas por mayordomos.

Los tipos de evento posibles en este dominio son:

1. 'tratamiento':
   - animal_tag: tag/arete del animal (ej: '47', 'n069')
   - datos:
     - producto: nombre del medicamento/vacuna (o null)
     - dosis: dosis con unidad (ej: '20ml', '10 cc') (o null)
     - via: 'SC', 'IM', 'IV', 'Oral' (o null)
     - dias_retiro: int días totales de retiro (o null)

2. 'muerte':
   - animal_tag: tag del animal fallecido
   - datos:
     - causa_presunta: string con la causa sospechada (o null)

Si la nota contiene MÚLTIPLES eventos de este dominio, extrae TODOS en la
lista 'eventos'. Responde ÚNICAMENTE JSON con la estructura
{"eventos": [{"tipo": "tratamiento", "animal_tag": "47", "fecha": null, "datos": {...}}]}.
"""


def parse(
    texto: str,
    hoy: Optional[date] = None,
    client: Optional[GeminiClient] = None,
) -> Optional[list[ParsedEvent]]:
    """Extrae eventos de sanidad vía Gemini. None si no disponible/falló/vacío."""
    cli = client or GeminiClient()
    if not cli.is_available() or not texto or not texto.strip():
        return None

    fecha_base = hoy or date.today()
    user_text = f"Nota de campo: «{texto}»\nFecha actual de referencia: {iso(fecha_base)}"

    resultado = cli.generate_structured(SYSTEM_PROMPT, user_text, SCHEMA_SANIDAD)
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
        if not es_tipo_evento_llm_valido(tipo) or tipo not in ("tratamiento", "muerte"):
            continue

        tag = normalizar_tag(item.get("animal_tag"))

        fecha_raw = item.get("fecha")
        if fecha_raw:
            f_obj = parse_fecha(str(fecha_raw), fecha_base) or to_date(fecha_raw)
            fecha = iso(f_obj or fecha_base)
        else:
            fecha = iso(parse_fecha(texto, fecha_base) or fecha_base)

        datos = _limpiar_datos(tipo, dict(item.get("datos") or {}), texto)
        eventos.append(ParsedEvent(tipo=tipo, texto=texto, animal_tag=tag, fecha=fecha, datos=datos))

    return eventos or None


def _limpiar_datos(tipo: str, datos: dict, texto_completo: str) -> dict:
    if tipo == "tratamiento":
        if "dias_retiro" in datos and datos["dias_retiro"] is not None:
            try:
                datos["dias_retiro"] = int(datos["dias_retiro"])
            except (ValueError, TypeError):
                pass
        dias = datos.get("dias_retiro")
        if dias:
            retiro = nlu.retiro_leche_carne(texto_completo, dias)
            if datos.get("dias_retiro_leche") is None:
                datos["dias_retiro_leche"] = retiro["dias_retiro_leche"]
            if datos.get("dias_retiro_carne") is None:
                datos["dias_retiro_carne"] = retiro["dias_retiro_carne"]

    return datos
