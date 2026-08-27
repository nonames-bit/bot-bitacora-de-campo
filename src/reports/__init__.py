"""Paquete de reportes PDF de la bitácora de campo zootécnico."""
from .pdf_report import generar_pdf, recolectar_datos

__all__ = ["recolectar_datos", "generar_pdf"]
