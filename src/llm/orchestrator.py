"""Orquestador de la Capa 2 multi-agente: router -> extractor(es) de dominio,
con el Agente Clasificador como respaldo si el router no detecta nada.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Optional, Union

from ..parsers.event_parser import ParsedEvent
from . import clasificador, manejo, reproduccion, sanidad
from .gemini_client import GeminiClient
from .router import dominios_detectados

_AGENTES = {"reproduccion": reproduccion, "sanidad": sanidad, "manejo": manejo}


def _ejecutar_dominios(
    dominios: list[str], texto: str, hoy: Optional[date], client: GeminiClient
) -> list[ParsedEvent]:
    """Ejecuta 1 o varios agentes de dominio.

    Con >=2 dominios corre en paralelo (I/O-bound esperando HTTP). El orden de
    salida sigue el orden de ``dominios``, no el de llegada de red, para que
    el resultado sea determinista. Un fallo en un dominio no descarta los demás.
    """
    if len(dominios) == 1:
        mod = _AGENTES[dominios[0]]
        res = mod.parse(texto, hoy=hoy, client=client)
        return res or []

    resultados: list[ParsedEvent] = []
    with ThreadPoolExecutor(max_workers=len(dominios)) as ex:
        futures = [(d, ex.submit(_AGENTES[d].parse, texto, hoy, client)) for d in dominios]
        for _dominio, fut in futures:
            try:
                res = fut.result()
            except Exception:
                res = None
            if res:
                resultados.extend(res)
    return resultados


def try_multiagent_parse(
    texto: str,
    hoy: Optional[date] = None,
    timeout: float = 30.0,
) -> Optional[Union[ParsedEvent, list[ParsedEvent]]]:
    """Punto de entrada público de la Capa 2 multi-agente.

    Devuelve ``ParsedEvent`` si hay exactamente 1 evento, ``list[ParsedEvent]``
    si hay >=2, o ``None`` si el LLM no está disponible o no pudo interpretar
    nada (en cuyo caso el llamador debe caer a la Capa 1 de regex).
    """
    client = GeminiClient(timeout=timeout)
    if not client.is_available():
        return None

    dominios = sorted(dominios_detectados(texto))

    if not dominios:
        dominios = clasificador.clasificar_dominios(texto, client=client)
        if not dominios:
            return None

    eventos = _ejecutar_dominios(dominios, texto, hoy, client)
    if not eventos:
        return None
    if len(eventos) == 1:
        return eventos[0]
    return eventos
