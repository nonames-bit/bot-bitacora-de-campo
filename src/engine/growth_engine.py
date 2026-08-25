"""Motor de crecimiento: ganancia media diaria (GMD) y peso ajustado a 205 días.

Fórmulas (skill ``@trazabilidad-ganadera``):
- GMD (kg/día) = (Peso Actual - Peso Anterior) / Días Transcurridos.
- Peso 205d = ((Peso Destete - Peso Nacimiento) / Edad en Días) × 205 + Peso Nacimiento.
"""
from __future__ import annotations

DIA_AJUSTE_DESTETE = 205


def gmd(peso_actual: float, peso_anterior: float, dias_transcurridos: int) -> float:
    """Ganancia Media Diaria entre dos pesajes (kg/día)."""
    if dias_transcurridos is None or int(dias_transcurridos) <= 0:
        return 0.0
    return (float(peso_actual) - float(peso_anterior)) / float(dias_transcurridos)


def peso_ajustado_destete(peso_destete: float, peso_nacimiento: float,
                          edad_dias: int, dias_ajuste: int = DIA_AJUSTE_DESTETE) -> float:
    """Peso ajustado a la edad estándar de destete (205 días)."""
    if edad_dias is None or int(edad_dias) <= 0:
        return float(peso_destete)
    base = (float(peso_destete) - float(peso_nacimiento)) / float(edad_dias)
    return base * float(dias_ajuste) + float(peso_nacimiento)


class GrowthEngine:
    """Contenedor de cálculos de crecimiento (métodos estáticos)."""

    @staticmethod
    def gmd(peso_actual, peso_anterior, dias_transcurridos):
        return gmd(peso_actual, peso_anterior, dias_transcurridos)

    @staticmethod
    def peso_ajustado_destete(peso_destete, peso_nacimiento, edad_dias,
                              dias_ajuste=DIA_AJUSTE_DESTETE):
        return peso_ajustado_destete(peso_destete, peso_nacimiento, edad_dias, dias_ajuste)
