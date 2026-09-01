"""Módulo OCR para reconocimiento visual de aretes/tags, medicamentos y facturas."""
from .factura_parser import (
    FacturaPajuelasInfo,
    detect_cantidad,
    detect_nit,
    detect_toro,
    detect_total,
    parse_factura_pajuelas,
)
from .ocr_engine import OCREngine, detect_medicamento, detect_tags

__all__ = [
    "OCREngine",
    "detect_tags",
    "detect_medicamento",
    "FacturaPajuelasInfo",
    "detect_nit",
    "detect_total",
    "detect_cantidad",
    "detect_toro",
    "parse_factura_pajuelas",
]
