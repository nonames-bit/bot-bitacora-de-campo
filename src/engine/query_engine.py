"""Motor de consultas: respuestas zootécnicas a preguntas en lenguaje natural.

Implementación dividida por dominio en ``src/engine/query/`` (reproducción,
sanidad, pasturas, inventario, historial). Este módulo se mantiene como punto
de importación público estable — no mover ni duplicar lógica aquí.
"""
from __future__ import annotations

from .query import (
    REPOSO_LISTO_DIAS,
    QueryEngine,
    buscar_foto_animal,
    calcular_brackets_inventario_sg,
    calcular_existencias_potreros_sg,
    contar_animales_sin_potrero,
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
    "contar_animales_sin_potrero",
    "extraer_nombre_potrero",
    "formatear_edad_zootecnica",
    "formatear_ocupacion_potreros",
    "formatear_tabla_potreros_sg",
    "generar_resumen_inventario_sg",
]
