"""Agente extractor Gemini para el dominio REPRODUCCIÓN (parto, servicio, celo)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ..parsers.event_parser import ParsedEvent
from ..utils import a_float, iso, parse_fecha, to_date
from .gemini_client import GeminiClient
from .normalizacion import normalizar_tag
from .schemas import SCHEMA_REPRODUCCION

SYSTEM_PROMPT = """Eres un agente extractor especializado en eventos de
REPRODUCCIÓN bovina para una bitácora de campo ganadero. Extrae eventos
estructurados en JSON a partir de notas de voz o texto en español enviadas
por mayordomos.

Los tipos de evento posibles en este dominio son:

1. 'parto':
   - animal_tag: tag/arete de la vaca madre (ej: '47', 'n069')
   - datos:
     - sexo_cria: 'Macho' o 'Hembra' (o null)
     - estado_cria: 'VIVO' o 'MUERTO' (por defecto 'VIVO', 'MUERTO' si fue aborto o nació muerto)
     - peso_nacimiento: float en kg (o null)
     - id_cria: tag de la cría si se menciona (o null)

2. 'servicio':
   - animal_tag: tag de la vaca
   - datos:
     - tipo_servicio: 'IA' (inseminación artificial / pajilla) o 'MONTA' (monta directa/toro)
     - toro_pajilla: código o nombre del toro/pajuela (o null)
     - raza_toro: raza del toro si se indica (o null)

3. 'celo':
   - animal_tag: tag de la vaca
   - datos:
     - am_pm: 'AM' (mañana/madrugada) o 'PM' (tarde/noche) (o null)

Si la nota contiene MÚLTIPLES eventos de este dominio, extrae TODOS en la
lista 'eventos'. Responde ÚNICAMENTE JSON con la estructura
{"eventos": [{"tipo": "parto", "animal_tag": "47", "fecha": null, "datos": {...}}]}.
"""


def parse(
    texto: str,
    hoy: Optional[date] = None,
    client: Optional[GeminiClient] = None,
) -> Optional[list[ParsedEvent]]:
    """Extrae eventos de reproducción vía Gemini. None si no disponible/falló/vacío."""
    cli = client or GeminiClient()
    if not cli.is_available() or not texto or not texto.strip():
        return None

    fecha_base = hoy or date.today()
    user_text = f"Nota de campo: «{texto}»\nFecha actual de referencia: {iso(fecha_base)}"

    resultado = cli.generate_structured(SYSTEM_PROMPT, user_text, SCHEMA_REPRODUCCION)
    if not resultado or "eventos" not in resultado:
        return None
    eventos_raw = resultado["eventos"]
    if not eventos_raw:
        return None

    eventos: list[ParsedEvent] = []
    for item in eventos_raw:
        tipo = item.get("tipo")
        if tipo not in ("parto", "servicio", "celo"):
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
    if tipo == "parto":
        sexo = datos.get("sexo_cria")
        if sexo:
            s_str = str(sexo).strip().capitalize()
            if s_str.startswith("M"):
                datos["sexo_cria"] = "Macho"
            elif s_str.startswith("H"):
                datos["sexo_cria"] = "Hembra"
        estado = datos.get("estado_cria")
        if estado and "muert" in str(estado).lower():
            datos["estado_cria"] = "MUERTO"
        else:
            datos["estado_cria"] = "VIVO"
        if "peso_nacimiento" in datos:
            datos["peso_nacimiento"] = a_float(datos["peso_nacimiento"])
        if datos.get("id_cria"):
            datos["id_cria"] = normalizar_tag(str(datos["id_cria"]))

    elif tipo == "servicio":
        t_serv = str(datos.get("tipo_servicio", "IA")).upper()
        datos["tipo_servicio"] = "MONTA" if "MONT" in t_serv else "IA"

    elif tipo == "celo":
        am_pm = datos.get("am_pm")
        if am_pm:
            am_pm_str = str(am_pm).upper()
            datos["am_pm"] = "AM" if "AM" in am_pm_str else ("PM" if "PM" in am_pm_str else None)

    return datos
