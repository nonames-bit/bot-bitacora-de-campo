"""Router determinista: decide qué dominio(s) zootécnico(s) toca una nota.

No hace ninguna llamada LLM — reutiliza los mismos patrones regex de
``nlp_engine.INTENTOS`` que ya usa la Capa 1, agrupados en 3 dominios.
"""
from __future__ import annotations

import re

from ..parsers import nlp_engine as nlu
from ..utils import normalizar

TIPO_A_DOMINIO: dict[str, str] = {
    "parto": "reproduccion", "servicio": "reproduccion", "celo": "reproduccion",
    "tratamiento": "sanidad", "muerte": "sanidad",
    "pesaje": "manejo", "traslado": "manejo", "movimiento": "manejo",
}

DOMINIOS = ("reproduccion", "sanidad", "manejo")


def tipos_coincidentes(texto: str) -> set[str]:
    """Tipos de ``nlu.INTENTOS`` cuyo patrón matchea en el texto (0, 1 o varios)."""
    t = normalizar(texto)
    return {tipo for tipo, patrones in nlu.INTENTOS if any(re.search(p, t) for p in patrones)}


def dominios_detectados(texto: str) -> set[str]:
    """Dominios (subset de reproduccion/sanidad/manejo) que toca el texto."""
    tipos = tipos_coincidentes(texto)
    return {TIPO_A_DOMINIO[t] for t in tipos if t in TIPO_A_DOMINIO}
