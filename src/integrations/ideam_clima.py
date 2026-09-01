"""Módulo de Integración Agroclimática & IDEAM (Fase 6.2).

Proporciona análisis de estacionalidad pluviométrica, factores de crecimiento
forrajero y modelos de capacidad de carga dinámica para ganadería tropical.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from ..engine.pasture_engine import (
    CONSUMO_MS_UGG,
    PCT_MS_TROPICAL,
    capacidad_carga_dinamica_ha,
    factor_ajuste_clima,
    kg_ms_disponibles,
)


@dataclass
class ReporteClimatico:
    fecha: str
    estacion: str
    factor_clima: float
    icono: str
    dias_reposo_sugeridos: int
    capacidad_carga_sugerida_ha: float
    recomendacion_zootecnica: str


class ClimaIDEAM:
    """Motor de análisis climático y correlación pluviométrica para pasturas."""

    # Calendario bimodal típico colombiano (Llanos Orientales / Magdalena Medio / Caribe)
    PATRON_ESTACIONAL_COLOMBIA = {
        1: {"temporada": "SECA / VERANO", "mm_promedio": 30.0, "reposo_dias": 55},
        2: {"temporada": "SECA / VERANO", "mm_promedio": 40.0, "reposo_dias": 50},
        3: {"temporada": "TRANSICIÓN A LLUVIAS", "mm_promedio": 110.0, "reposo_dias": 40},
        4: {"temporada": "ÉPOCA DE LLUVIAS", "mm_promedio": 280.0, "reposo_dias": 30},
        5: {"temporada": "ÉPOCA DE LLUVIAS", "mm_promedio": 350.0, "reposo_dias": 28},
        6: {"temporada": "ÉPOCA DE LLUVIAS", "mm_promedio": 320.0, "reposo_dias": 28},
        7: {"temporada": "TRANSICIÓN / VERANILLO", "mm_promedio": 180.0, "reposo_dias": 32},
        8: {"temporada": "TRANSICIÓN / VERANILLO", "mm_promedio": 160.0, "reposo_dias": 32},
        9: {"temporada": "ÉPOCA DE LLUVIAS", "mm_promedio": 290.0, "reposo_dias": 28},
        10: {"temporada": "ÉPOCA DE LLUVIAS (Pico)", "mm_promedio": 340.0, "reposo_dias": 28},
        11: {"temporada": "TRANSICIÓN A SECA", "mm_promedio": 130.0, "reposo_dias": 38},
        12: {"temporada": "SECA / VERANO", "mm_promedio": 45.0, "reposo_dias": 50},
    }

    @classmethod
    def clasificar_estacionalidad(cls, mm_lluvia_30d: float) -> dict:
        """Clasifica el estado forrajero y días de reposo óptimos según mm de lluvia en 30 días."""
        mm = float(mm_lluvia_30d)
        f_clima = factor_ajuste_clima(mm)

        if mm >= 150.0:
            estacion = "ÉPOCA DE LLUVIAS (Alta Oferta)"
            icono = "🌧️"
            reposo = 28
            recom = "Excelente tasa de rebrote. Mantener ocupación corta (1-2 días) para evitar sobremaduración y pisoteo."
        elif mm >= 50.0:
            estacion = "TRANSICIÓN (Oferta Moderada)"
            icono = "⛅"
            reposo = 35
            recom = "Crecimiento forrajero regular. Ajustar reposo a 35-40 días y monitorear punto óptimo de cosecha Voisin."
        else:
            estacion = "ÉPOCA SECA / VERANO (Oferta Restringida)"
            icono = "☀️"
            reposo = 55
            recom = "Déficit hídrico. Extender periodos de descanso a 50-60 días, suministrar sal mineralizada proteinada o silo/heno."

        return {
            "estacion": estacion,
            "mm_30d": round(mm, 1),
            "factor_clima": round(f_clima, 2),
            "icono": icono,
            "dias_reposo_sugeridos": reposo,
            "recomendacion": recom,
        }

    @classmethod
    def pronostico_mes(cls, mes: Optional[int] = None) -> dict:
        """Retorna el perfil climático histórico de referencia para el mes."""
        m = mes or date.today().month
        m_val = max(1, min(12, int(m)))
        return cls.PATRON_ESTACIONAL_COLOMBIA.get(m_val, cls.PATRON_ESTACIONAL_COLOMBIA[1])

    @classmethod
    def balance_agroclimatico(cls, aforo_kg_m2: float, area_has: float,
                              num_ugg: float, mm_30d: float,
                              dias_rotacion: int = 33) -> dict:
        """Calcula el balance forrajero integral combinando aforo, área, carga en UGG y lluvia acumulada."""
        f_clima = factor_ajuste_clima(mm_30d)
        ms_neta_disponible = kg_ms_disponibles(aforo_kg_m2, area_has, PCT_MS_TROPICAL) * f_clima
        demanda_diaria_ugg = float(num_ugg) * CONSUMO_MS_UGG
        oferta_diaria_sostenible = ms_neta_disponible / float(dias_rotacion) if dias_rotacion > 0 else 0.0

        balance_diario = oferta_diaria_sostenible - demanda_diaria_ugg
        suficiencia = (oferta_diaria_sostenible / demanda_diaria_ugg * 100.0) if demanda_diaria_ugg > 0 else 100.0
        carga_dinamica = capacidad_carga_dinamica_ha(aforo_kg_m2, dias_rotacion, mm_30d)

        info_clima = cls.clasificar_estacionalidad(mm_30d)

        return {
            "mm_lluvia_30d": round(mm_30d, 1),
            "estacion": info_clima["estacion"],
            "icono": info_clima["icono"],
            "factor_clima": f_clima,
            "aforo_kg_m2": round(aforo_kg_m2, 2),
            "area_has": round(area_has, 1),
            "ms_neta_total_kg": round(ms_neta_disponible, 1),
            "num_ugg": round(num_ugg, 1),
            "demanda_diaria_kg_ms": round(demanda_diaria_ugg, 1),
            "oferta_diaria_kg_ms": round(oferta_diaria_sostenible, 1),
            "balance_diario_kg_ms": round(balance_diario, 1),
            "suficiencia_pct": round(suficiencia, 1),
            "carga_sostenible_ugg_ha": carga_dinamica,
            "dias_reposo_sugeridos": info_clima["dias_reposo_sugeridos"],
            "recomendacion": info_clima["recomendacion"],
        }
