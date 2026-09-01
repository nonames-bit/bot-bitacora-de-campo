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
PCT_CONSUMO_PV = 2.8  # Consumo estándar 2.8% del Peso Vivo
CONSUMO_MS_UGG = 12.0  # valor histórico para compatibilidad (tests usan 12)
CONSUMO_MS_UGG_28 = 12.6  # 450 kg * 2.8% = 12.6 kg MS / UGG / día (para cálculo dinámico)
PCT_MS_TROPICAL = 22.0  # pasto tropical ~22% de materia seca (%MS)
FACTOR_APROVECHAMIENTO_DEFAULT = 0.75  # 75% aprovechamiento real (25% pérdidas pisoteo/bostas)


def kg_mv_ha(aforo_kg_m2: float) -> float:
    """Producción de materia verde por hectárea (kg MV/ha)."""
    return float(aforo_kg_m2) * M2_POR_HA


def kg_ms_ha(kg_mv_ha_valor: float, pct_ms: float = PCT_MS_TROPICAL) -> float:
    """Producción de materia seca por hectárea (kg MS/ha)."""
    return float(kg_mv_ha_valor) * (float(pct_ms) / 100.0)


def kg_ms_disponibles(aforo_kg_m2: float, area_has: float,
                      pct_ms: float = PCT_MS_TROPICAL,
                      factor_aprov: float = 1.0) -> float:
    """Materia seca neta disponible para pastoreo en un potrero (kg MS).

    factor_aprov=1.0 mantiene compatibilidad con cálculo bruto (sin pérdidas);
    use FACTOR_APROVECHAMIENTO_DEFAULT (0.75) para oferta neta real.
    """
    return kg_ms_ha(kg_mv_ha(aforo_kg_m2), pct_ms) * float(area_has) * float(factor_aprov)


def factor_ajuste_clima(mm_lluvia_30d: float) -> float:
    """Calcula el factor de ajuste de crecimiento forrajero según precipitación en los últimos 30 días.

    - >= 150 mm (Época de lluvias): Factor 1.0 - 1.30 (crecimiento vigoroso).
    - 50 - 150 mm (Transición): Factor 0.65 - 1.0.
    - < 50 mm (Época seca / verano): Factor 0.35 - 0.65 (crecimiento reducido).
    """
    mm = max(0.0, float(mm_lluvia_30d))
    if mm >= 150.0:
        return min(1.30, 1.0 + (mm - 150.0) / 500.0)
    elif mm >= 50.0:
        return 0.65 + 0.35 * ((mm - 50.0) / 100.0)
    else:
        return max(0.35, 0.35 + 0.30 * (mm / 50.0))


def capacidad_carga_ugg(kg_ms_disponibles_valor: float,
                        consumo_ms_ugg: float = CONSUMO_MS_UGG) -> float:
    """Capacidad de carga: número de UGG que soporta la oferta un día."""
    if consumo_ms_ugg <= 0:
        return 0.0
    return float(kg_ms_disponibles_valor) / float(consumo_ms_ugg)


def capacidad_carga_dinamica_ha(aforo_kg_m2: float, dias_rotacion: int = 33,
                                mm_lluvia_30d: float = 100.0,
                                pct_ms: float = PCT_MS_TROPICAL,
                                factor_aprov: float = FACTOR_APROVECHAMIENTO_DEFAULT) -> float:
    """Calcula la carga animal sostenible por hectárea (UGG/ha) ajustada por lluvia y rotación.

    Fórmula:
    - Oferta neta MS/ha = (aforo * 10000 * %MS/100 * factor_aprov * factor_clima)
    - Demanda ciclo/UGG = (dias_rotacion * 12.6 kg MS/día)
    - Carga sostenible = Oferta neta / Demanda ciclo
    """
    if dias_rotacion <= 0:
        return 0.0
    f_clima = factor_ajuste_clima(mm_lluvia_30d)
    ms_neta_ha = kg_ms_ha(kg_mv_ha(aforo_kg_m2), pct_ms) * factor_aprov * f_clima
    demanda_ciclo_ugg = float(dias_rotacion) * CONSUMO_MS_UGG_28
    return round(ms_neta_ha / demanda_ciclo_ugg, 2)


def dias_ocupacion(kg_ms_disponibles_valor: float, num_animales: int,
                   consumo_ms_animal_dia: float = CONSUMO_MS_UGG) -> float:
    """Días de ocupación Voisin para un número dado de animales."""
    if num_animales <= 0 or consumo_ms_animal_dia <= 0:
        return 0.0
    return float(kg_ms_disponibles_valor) / (float(num_animales) * float(consumo_ms_animal_dia))


def consumo_diario_ms(peso_vivo_kg: float, pct_pv: float = PCT_CONSUMO_PV) -> float:
    """Consumo diario de Materia Seca estimado a partir del Peso Vivo (2.8% PV)."""
    return float(peso_vivo_kg) * (float(pct_pv) / 100.0)



def ugg_de_peso(peso_vivo_kg: float) -> float:
    """Convierte peso vivo a Unidades Gran Ganado (UGG = 450 kg)."""
    return float(peso_vivo_kg) / UGG_KG


def balance_forrajero_calculo(oferta_neta_ms_total: float,
                              demanda_ms_diaria: float,
                              dias_rotacion: int = 33) -> dict:
    """Calcula el balance forrajero de la finca o lote.

    - Oferta Diaria Sostenible = Oferta neta total / días de rotación
    - Balance Diario = Oferta Diaria - Demanda Diaria
    - Índice de Suficiencia = (Oferta Diaria / Demanda Diaria) * 100%
    """
    if dias_rotacion <= 0 or demanda_ms_diaria <= 0:
        return {
            "oferta_diaria_kg_ms": 0.0,
            "demanda_diaria_kg_ms": round(demanda_ms_diaria, 1),
            "balance_diario_kg_ms": 0.0,
            "indice_suficiencia_pct": 0.0,
            "estado": "SIN DATOS",
            "icono": "⚪",
        }

    oferta_diaria = float(oferta_neta_ms_total) / float(dias_rotacion)
    balance = oferta_diaria - float(demanda_ms_diaria)
    suficiencia = (oferta_diaria / float(demanda_ms_diaria)) * 100.0

    if suficiencia >= 110.0:
        estado = "SUPERÁVIT FORRAJERO"
        icono = "🟢"
        recomendacion = "Excelente disponibilidad forrajera. Oportunidad de henificación o incremento de carga."
    elif suficiencia >= 90.0:
        estado = "EQUILIBRIO FORRAJERO"
        icono = "🟡"
        recomendacion = "Oferta ajustada a la demanda. Mantener rotación estricta Voisin."
    else:
        estado = "DÉFICIT FORRAJERO"
        icono = "🔴"
        recomendacion = "Alerta de sobrepastoreo. Requiere suplementación, ensilaje o alivio de carga animal."

    return {
        "oferta_diaria_kg_ms": round(oferta_diaria, 1),
        "demanda_diaria_kg_ms": round(demanda_ms_diaria, 1),
        "balance_diario_kg_ms": round(balance, 1),
        "indice_suficiencia_pct": round(suficiencia, 1),
        "estado": estado,
        "icono": icono,
        "recomendacion": recomendacion,
    }


class PastureEngine:
    """Contenedor de cálculos de pasturas (métodos estáticos)."""

    @staticmethod
    def kg_mv_ha(aforo_kg_m2):
        return kg_mv_ha(aforo_kg_m2)

    @staticmethod
    def kg_ms_ha(kg_mv_ha_valor, pct_ms=PCT_MS_TROPICAL):
        return kg_ms_ha(kg_mv_ha_valor, pct_ms)

    @staticmethod
    def kg_ms_disponibles(aforo_kg_m2, area_has, pct_ms=PCT_MS_TROPICAL, factor_aprov=1.0):
        return kg_ms_disponibles(aforo_kg_m2, area_has, pct_ms, factor_aprov)

    @staticmethod
    def factor_ajuste_clima(mm_lluvia_30d):
        return factor_ajuste_clima(mm_lluvia_30d)

    @staticmethod
    def capacidad_carga_dinamica_ha(aforo_kg_m2, dias_rotacion=33, mm_lluvia_30d=100.0,
                                    pct_ms=PCT_MS_TROPICAL, factor_aprov=FACTOR_APROVECHAMIENTO_DEFAULT):
        return capacidad_carga_dinamica_ha(aforo_kg_m2, dias_rotacion, mm_lluvia_30d, pct_ms, factor_aprov)

    @staticmethod
    def capacidad_carga_ugg(kg_ms_disponibles_valor, consumo_ms_ugg=CONSUMO_MS_UGG):
        return capacidad_carga_ugg(kg_ms_disponibles_valor, consumo_ms_ugg)

    @staticmethod
    def dias_ocupacion(kg_ms_disponibles_valor, num_animales,
                       consumo_ms_animal_dia=CONSUMO_MS_UGG):
        return dias_ocupacion(kg_ms_disponibles_valor, num_animales, consumo_ms_animal_dia)

    @staticmethod
    def consumo_diario_ms(peso_vivo_kg, pct_pv=PCT_CONSUMO_PV):
        return consumo_diario_ms(peso_vivo_kg, pct_pv)

    @staticmethod
    def ugg_de_peso(peso_vivo_kg):
        return ugg_de_peso(peso_vivo_kg)

    @staticmethod
    def balance_forrajero(oferta_neta_ms_total, demanda_ms_diaria, dias_rotacion=33):
        return balance_forrajero_calculo(oferta_neta_ms_total, demanda_ms_diaria, dias_rotacion)

