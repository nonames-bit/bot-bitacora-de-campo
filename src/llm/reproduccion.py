"""Agente extractor Gemini para el dominio REPRODUCCIÓN (parto, servicio, celo)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ..db.models import TIPOS_EVENTO_PARTO, TIPOS_EVENTO_SIN_CRIA
from ..parsers.event_parser import ParsedEvent, es_tipo_evento_llm_valido
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
     - tipo_evento: uno de 'PARTO', 'GEMELAR', 'ABORTO', 'REABSORCION',
       'MOMIFICACION', 'MACERACION', 'MUERTE_FETAL' (por defecto 'PARTO').
       Usa 'GEMELAR' si se mencionan dos crías del mismo parto ("parió
       mellizos/gemelos"). Usa 'ABORTO' para pérdida gestacional genérica sin
       más detalle. Usa 'REABSORCION' si se dice "reabsorbió" o "se resorbió"
       (pérdida temprana, sin signos visibles). Usa 'MOMIFICACION' si se dice
       "se momificó" el feto (feto seco/deshidratado retenido). Usa
       'MACERACION' si se dice "se maceró" (feto descompuesto con
       infección). Usa 'MUERTE_FETAL' si se dice "murió el feto"/"muerte
       fetal" sin especificar más.
     - sexo_cria: 'Macho' o 'Hembra' (o null; no aplica si tipo_evento no es
       'PARTO' ni 'GEMELAR')
     - estado_cria: 'VIVO' o 'MUERTO' (por defecto 'VIVO'; 'MUERTO' si nació
       muerto o si tipo_evento no es 'PARTO'/'GEMELAR')
     - peso_nacimiento: float en kg (o null)
     - id_cria: tag de la cría si se menciona (o null; no aplica salvo en
       'PARTO'/'GEMELAR')

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

4. 'diagnostico_gestacion' / 'palpacion':
   - animal_tag: tag de la vaca
   - datos:
     - resultado: 'PREÑADA' o 'VACIA' (por defecto 'PREÑADA')
     - dias_gestacion: int con días de gestación estimados (o null)
     - responsable: nombre del veterinario/palpador (o null)

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
        # Defensa anti prompt-injection (P6): un tipo fuera de la lista blanca
        # central se descarta (el helper registra el warning de rechazo) y el
        # agente solo acepta los tipos de su propio dominio.
        if not es_tipo_evento_llm_valido(tipo) or tipo not in ("parto", "servicio", "celo", "diagnostico_gestacion"):
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
        tipo_evento = str(datos.get("tipo_evento") or "PARTO").strip().upper()
        if tipo_evento not in TIPOS_EVENTO_PARTO:
            tipo_evento = "PARTO"
        datos["tipo_evento"] = tipo_evento

        sexo = datos.get("sexo_cria")
        if sexo:
            s_str = str(sexo).strip().capitalize()
            if s_str.startswith("M"):
                datos["sexo_cria"] = "Macho"
            elif s_str.startswith("H"):
                datos["sexo_cria"] = "Hembra"
        estado = datos.get("estado_cria")
        if tipo_evento in TIPOS_EVENTO_SIN_CRIA:
            datos["estado_cria"] = "MUERTO"
            datos["id_cria"] = None
        elif estado and "muert" in str(estado).lower():
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

    elif tipo == "diagnostico_gestacion":
        res = str(datos.get("resultado", "PREÑADA")).upper()
        if "VAC" in res or "NEG" in res or "ABIER" in res:
            datos["resultado"] = "VACIA"
        else:
            datos["resultado"] = "PREÑADA"
        if "dias_gestacion" in datos and datos["dias_gestacion"] is not None:
            try:
                datos["dias_gestacion"] = int(datos["dias_gestacion"])
            except (ValueError, TypeError):
                datos["dias_gestacion"] = None

    return datos
