"""Cliente HTTP genérico para proveedores compatibles con la API de OpenAI
(chat/completions): OpenRouter, CheaperInference, OpenCode Go, etc.

Reutiliza el prompt de sistema y el extractor de JSON de ``nvidia_client``
(NVIDIA NIM ya expone el mismo formato OpenAI-compatible), variando solo
el prefijo de variables de entorno (API key, modelo y base URL) por
proveedor. Así se evita duplicar la lógica de parseo de eventos.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Optional, Union

from ..parsers.event_parser import ParsedEvent
from .nvidia_client import NvidiaClient

logger = logging.getLogger("bitacora.llm")


class GenericOpenAIClient(NvidiaClient):
    """Cliente para un proveedor OpenAI-compatible identificado por ``env_prefix``.

    Lee ``{env_prefix}_API_KEY``, ``{env_prefix}_MODEL`` y
    ``{env_prefix}_BASE_URL`` del entorno. No requiere modelo/URL por
    defecto: si no están configurados, el cliente queda no disponible
    (``is_available() -> False``) en vez de asumir un valor adivinado.
    """

    def __init__(self, provider: str, env_prefix: str, timeout: float = 30.0):
        self.provider = provider
        self.env_prefix = env_prefix
        raw_key = os.getenv(f"{env_prefix}_API_KEY", "").strip()
        self.api_key: Optional[str] = raw_key if raw_key and not raw_key.startswith("pegar_aqui") else None
        raw_model = os.getenv(f"{env_prefix}_MODEL", "").strip()
        self.model: Optional[str] = raw_model or None
        raw_url = os.getenv(f"{env_prefix}_BASE_URL", "").strip()
        self.api_url: Optional[str] = raw_url or None
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5 and self.model and self.api_url)


def try_generic_parse(
    client: GenericOpenAIClient,
    texto: str,
    hoy: Optional[date] = None,
) -> Optional[Union[ParsedEvent, list[ParsedEvent]]]:
    """Intenta parsear ``texto`` con un ``GenericOpenAIClient`` ya construido.

    Devuelve ``None`` de inmediato si el cliente no tiene key/modelo/URL
    configurados (sin hacer ninguna llamada de red).
    """
    if not client.is_available() or not texto or not texto.strip():
        return None

    eventos = client.parse_text(texto, hoy=hoy)
    if not eventos:
        return None
    if len(eventos) == 1:
        return eventos[0]
    return eventos
