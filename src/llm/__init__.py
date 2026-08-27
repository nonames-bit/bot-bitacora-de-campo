"""Módulo de integración con modelos de lenguaje grande (LLM).

Soporta NVIDIA NIM (build.nvidia.com) para extracción estructurada de
eventos zootécnicos, procesamiento de lenguaje complejo y múltiples
eventos por nota.
"""
from .nvidia_client import NvidiaClient, try_llm_parse

__all__ = ["NvidiaClient", "try_llm_parse"]
