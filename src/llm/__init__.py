"""Módulo de integración con modelos de lenguaje grande (LLM).

Soporta varios proveedores en cascada, del más barato/gratuito al de pago:
- OpenRouter, CheaperInference, OpenCode Go (`GenericOpenAIClient`) — clientes
  OpenAI-compatible configurables por variables de entorno, sin costo fijo
  o de muy bajo costo según el modelo elegido.
- NVIDIA NIM (build.nvidia.com) — cliente simple, gratuito.
- Gemini (Google AI Studio) — multi-agente con router determinista por dominio;
  el más preciso con JSON estructurado, pero de pago. Se prueba **al final**
  para minimizar el gasto: solo se usa si ningún proveedor gratuito/barato
  resolvió la nota.

El orden se puede ajustar simplemente dejando sin configurar (sin API key)
los proveedores que no se quieran usar: `GenericOpenAIClient.is_available()`
devuelve False de inmediato y no se hace ninguna llamada de red.
"""
from .gemini_client import GeminiClient
from .generic_client import GenericOpenAIClient, try_generic_parse
from .nvidia_client import NvidiaClient, try_llm_parse as try_nvidia_parse
from .orchestrator import try_multiagent_parse as try_gemini_parse

try:
    from .nvidia_client import try_llm_parse  # alias legacy
except Exception:
    try_llm_parse = None  # type: ignore

__all__ = [
    "GeminiClient",
    "GenericOpenAIClient",
    "NvidiaClient",
    "try_gemini_parse",
    "try_generic_parse",
    "try_nvidia_parse",
    "try_llm_parse",
    "try_hybrid_parse",
]

# Proveedores OpenAI-compatible probados en este orden antes que Gemini.
# El prefijo determina las variables de entorno: {PREFIX}_API_KEY,
# {PREFIX}_MODEL y {PREFIX}_BASE_URL (ver .env.example).
_PROVIDERS_BARATOS = [
    ("openrouter", "OPENROUTER"),
    ("cheaperinference", "CHEAPERINFERENCE"),
    ("opencode_go", "OPENCODE"),
]


def try_hybrid_parse(texto, hoy=None, timeout=30.0):
    """Prueba proveedores baratos/gratuitos primero; Gemini y NVIDIA al final.

    Orden: OpenRouter -> CheaperInference -> OpenCode Go -> NVIDIA -> Gemini.
    Cada proveedor sin API key configurada se salta sin llamada de red.
    """
    # 1-3. Proveedores OpenAI-compatible baratos/gratuitos
    for provider, env_prefix in _PROVIDERS_BARATOS:
        try:
            from .generic_client import GenericOpenAIClient as _Client, try_generic_parse as _try
            client = _Client(provider=provider, env_prefix=env_prefix, timeout=timeout)
            res = _try(client, texto, hoy=hoy)
            if res is not None:
                return res
        except Exception:
            pass
    # 4. NVIDIA (gratuito)
    try:
        from .nvidia_client import try_llm_parse as _nvidia
        res = _nvidia(texto, hoy=hoy, timeout=timeout)
        if res is not None:
            return res
    except Exception:
        pass
    # 5. Gemini (de pago) — último recurso
    try:
        from .orchestrator import try_multiagent_parse as _gemini
        res = _gemini(texto, hoy=hoy, timeout=timeout)
        if res is not None:
            return res
    except Exception:
        pass
    return None
