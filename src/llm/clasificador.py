"""Agente clasificador Gemini: respaldo cuando el router determinista no
detecta ningún dominio en el texto (regex de nlp_engine no reconoce nada)."""
from __future__ import annotations

from typing import Optional

from .gemini_client import GeminiClient
from .schemas import SCHEMA_CLASIFICADOR

SYSTEM_PROMPT = """Clasifica la siguiente nota de campo ganadera en uno o más
de estos dominios:
- 'reproduccion': parto, servicio/inseminación artificial, celo.
- 'sanidad': tratamiento, vacuna, medicación, muerte de un animal.
- 'manejo': pesaje, traslado de potrero, compra/venta/entrada/salida de animales.

Responde con TODOS los dominios que apliquen si el texto menciona varios
eventos. Si no reconoces ningún evento zootécnico, responde con una lista
vacía."""


def clasificar_dominios(texto: str, client: Optional[GeminiClient] = None) -> list[str]:
    """Dominios (subset de reproduccion/sanidad/manejo) según el LLM.

    Lista vacía si el cliente no está disponible, falló o no reconoce nada.
    """
    cli = client or GeminiClient()
    if not cli.is_available() or not texto or not texto.strip():
        return []

    resultado = cli.generate_structured(SYSTEM_PROMPT, texto, SCHEMA_CLASIFICADOR)
    if not resultado or "dominios" not in resultado:
        return []

    validos = {"reproduccion", "sanidad", "manejo"}
    return [d for d in resultado["dominios"] if d in validos]
