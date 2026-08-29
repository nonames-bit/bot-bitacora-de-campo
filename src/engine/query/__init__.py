"""Paquete del motor de consultas, dividido por dominio zootécnico.

Importar siempre desde ``src.engine.query_engine`` (mantiene la API pública
estable); este paquete es el detalle de implementación interno.
"""
from .engine import QueryEngine
from .helpers import (
    REPOSO_LISTO_DIAS,
    buscar_foto_animal,
    calcular_brackets_inventario_sg,
    calcular_existencias_potreros_sg,
    extraer_nombre_potrero,
    formatear_edad_zootecnica,
    formatear_ocupacion_potreros,
    formatear_tabla_potreros_sg,
    generar_resumen_inventario_sg,
)

__all__ = [
    "QueryEngine",
    "REPOSO_LISTO_DIAS",
    "buscar_foto_animal",
    "calcular_brackets_inventario_sg",
    "calcular_existencias_potreros_sg",
    "extraer_nombre_potrero",
    "formatear_edad_zootecnica",
    "formatear_ocupacion_potreros",
    "formatear_tabla_potreros_sg",
    "generar_resumen_inventario_sg",
]
