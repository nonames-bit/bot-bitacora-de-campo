"""Paquete de reportes PDF de la bitácora de campo zootécnico."""
from .pdf_report import generar_pdf, recolectar_datos
from .qr_fichas import generar_fichas_lote, listar_animales_lote, qr_payload

__all__ = ["recolectar_datos", "generar_pdf", "generar_fichas_lote", "listar_animales_lote", "qr_payload"]
