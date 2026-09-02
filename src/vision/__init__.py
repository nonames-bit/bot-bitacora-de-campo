"""Módulo de Visión Multimodal y OCR Avanzado."""
from .arete_detector import (
    AreteDetector,
    corregir_caracteres_confusos,
    detectar_arete_avanzado,
    mejorar_imagen_para_ocr,
)

__all__ = [
    "AreteDetector",
    "detectar_arete_avanzado",
    "corregir_caracteres_confusos",
    "mejorar_imagen_para_ocr",
]
