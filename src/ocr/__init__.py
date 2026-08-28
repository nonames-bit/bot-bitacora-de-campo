"""Módulo OCR para reconocimiento visual de aretes/tags y medicamentos."""
from .ocr_engine import OCREngine, detect_medicamento, detect_tags

__all__ = ["OCREngine", "detect_tags", "detect_medicamento"]
