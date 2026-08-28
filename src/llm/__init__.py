"""Módulo de integración con modelos de lenguaje grande (LLM).

Soporta dos proveedores en paralelo:
- Gemini (Google AI Studio) — multi-agente con router determinista por dominio
- NVIDIA NIM (build.nvidia.com) — cliente simple con fallback

El orquestador híbrido intenta Gemini primero (más preciso con JSON), y si no está
disponible o falla, cae a NVIDIA, y finalmente a regex local.
"""
from .gemini_client import GeminiClient
from .nvidia_client import NvidiaClient, try_llm_parse as try_nvidia_parse
from .orchestrator import try_multiagent_parse as try_gemini_parse

try:
    from .nvidia_client import try_llm_parse  # alias legacy
except Exception:
    try_llm_parse = None  # type: ignore

__all__ = ["GeminiClient", "NvidiaClient", "try_gemini_parse", "try_nvidia_parse", "try_llm_parse"]


def try_hybrid_parse(texto, hoy=None, timeout=30.0):
    """Intenta Gemini primero, luego NVIDIA, devuelve ParsedEvent o lista o None."""
    # 1. Gemini (import dinámico para que los mocks de tests funcionen)
    try:
        from .orchestrator import try_multiagent_parse as _gemini
        res = _gemini(texto, hoy=hoy, timeout=timeout)
        if res is not None:
            return res
    except Exception:
        pass
    # 2. NVIDIA
    try:
        from .nvidia_client import try_llm_parse as _nvidia
        res = _nvidia(texto, hoy=hoy, timeout=timeout)
        if res is not None:
            return res
    except Exception:
        pass
    return None
