"""Motor de pasturas: aforo, materia seca, carga animal y rotación Voisin.

Fórmulas (skill ``@aforo-pasturas``):
- kg MV/ha = aforo (kg/m²) × 10 000 m².
- kg MS/ha = kg MV/ha × (%MS / 100).
- 1 UGG = 450 kg peso vivo; consumo ≈ 12 kg MS/día.
- Días de Ocupación = kg MS disponibles / (nº animales × consumo MS/animal/día).
"""
from __future__ import annotations

M2_POR_HA = 10_000.0
UGG_KG = 450.0
CONSUMO_MS_UGG = 12.0  # kg MS / UGG / día
PCT_MS_TROPICAL = 22.0  # pasto tropical ~22% de materia seca (%MS)


def kg_mv_ha(aforo_kg_m2: float) -> float:
    """Producción de materia verde por hectárea (kg MV/ha)."""
    return float(aforo_kg_m2) * M2_POR_HA


def kg_ms_ha(kg_mv_ha_valor: float, pct_ms: float = PCT_MS_TROPICAL) -> float:
    """Producción de materia seca por hectárea (kg MS/ha)."""
    return float(kg_mv_ha_valor) * (float(pct_ms) / 100.0)


def kg_ms_disponibles(aforo_kg_m2: float, area_has: float,
                      pct_ms: float = PCT_MS_TROPICAL) -> float:
    """Materia seca total disponible en un potrero (kg MS)."""
    return kg_ms_ha(kg_mv_ha(aforo_kg_m2), pct_ms) * float(area_has)


def capacidad_carga_ugg(kg_ms_disponibles_valor: float,
                        consumo_ms_ugg: float = CONSUMO_MS_UGG) -> float:
    """Capacidad de carga: número de UGG que soporta la oferta un día."""
    if consumo_ms_ugg <= 0:
        return 0.0
    return float(kg_ms_disponibles_valor) / float(consumo_ms_ugg)


def dias_ocupacion(kg_ms_disponibles_valor: float, num_animales: int,
                   consumo_ms_animal_dia: float = CONSUMO_MS_UGG) -> float:
    """Días de ocupación Voisin para un número dado de animales."""
    if num_animales <= 0 or consumo_ms_animal_dia <= 0:
        return 0.0
    return float(kg_ms_disponibles_valor) / (float(num_animales) * float(consumo_ms_animal_dia))


def ugg_de_peso(peso_vivo_kg: float) -> float:
    """Convierte peso vivo a Unidades Gran Ganado (UGG)."""
    return float(peso_vivo_kg) / UGG_KG


class PastureEngine:
    """Contenedor de cálculos de pasturas (métodos estáticos)."""

    @staticmethod
    def kg_mv_ha(aforo_kg_m2):
        return kg_mv_ha(aforo_kg_m2)

    @staticmethod
    def kg_ms_ha(kg_mv_ha_valor, pct_ms=PCT_MS_TROPICAL):
        return kg_ms_ha(kg_mv_ha_valor, pct_ms)

    @staticmethod
    def kg_ms_disponibles(aforo_kg_m2, area_has, pct_ms=PCT_MS_TROPICAL):
        return kg_ms_disponibles(aforo_kg_m2, area_has, pct_ms)

    @staticmethod
    def capacidad_carga_ugg(kg_ms_disponibles_valor, consumo_ms_ugg=CONSUMO_MS_UGG):
        return capacidad_carga_ugg(kg_ms_disponibles_valor, consumo_ms_ugg)

    @staticmethod
    def dias_ocupacion(kg_ms_disponibles_valor, num_animales,
                       consumo_ms_animal_dia=CONSUMO_MS_UGG):
        return dias_ocupacion(kg_ms_disponibles_valor, num_animales, consumo_ms_animal_dia)

    @staticmethod
    def ugg_de_peso(peso_vivo_kg):
        return ugg_de_peso(peso_vivo_kg)
