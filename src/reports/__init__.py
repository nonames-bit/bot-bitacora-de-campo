"""Paquete de reportes PDF de la bitácora de campo zootécnico.

Expone la API pública de generación de documentos. Los estilos compartidos
viven en ``src.reports.estilo_ja`` y se importan directamente desde ahí por
los consumidores que los necesiten; aquí solo se re-exporta la API funcional.
"""
from .pdf_report import generar_pdf, recolectar_datos
from .qr_fichas import (
    generar_ficha_qr_individual,
    generar_fichas_lote,
    listar_animales_lote,
    qr_payload,
)
from .estilo_ja import (  # noqa: F401  (reexportado para compatibilidad)
    COLOR_MARCA,
    COLOR_MARCA_CLARA,
    COLOR_MARCA_ZEBRA,
    dibujar_encabezado,
    dibujar_pie,
    dibujar_seccion_hdr,
    estilo_normal,
    estilo_pie,
    estilo_seccion,
    estilo_subtitulo,
    estilo_titulo,
    tabla_style_alertas,
    tabla_style_base,
    tabla_style_header_verde,
    tabla_style_potreros,
)

__all__ = [
    "recolectar_datos",
    "generar_pdf",
    "generar_fichas_lote",
    "generar_ficha_qr_individual",
    "listar_animales_lote",
    "qr_payload",
    # Constantes/helpers de estilo reexportados (compatibilidad):
    "COLOR_MARCA",
    "COLOR_MARCA_CLARA",
    "COLOR_MARCA_ZEBRA",
    "dibujar_encabezado",
    "dibujar_pie",
    "dibujar_seccion_hdr",
    "estilo_normal",
    "estilo_pie",
    "estilo_seccion",
    "estilo_subtitulo",
    "estilo_titulo",
    "tabla_style_alertas",
    "tabla_style_base",
    "tabla_style_header_verde",
    "tabla_style_potreros",
]
