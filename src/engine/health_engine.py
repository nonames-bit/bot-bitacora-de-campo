"""Motor sanitario: periodos de retiro y bloqueos de ordeño/carne.

Regla (skill ``@plan-sanitario``):
- Fecha Fin Retiro = Fecha Última Dosis + Días de Retiro del Fármaco.
- Alerta estricta si un animal tratado está en ordeño o programado para
  venta/sacrificio durante su periodo de carencia.
"""
from __future__ import annotations

from datetime import date

from ..utils import add_days, iso, to_date


def fecha_fin_retiro(fecha_ultima_dosis, dias_retiro) -> date | None:
    """Fecha en que termina el retiro = última dosis + días de retiro."""
    if dias_retiro is None:
        return None
    return add_days(fecha_ultima_dosis, int(dias_retiro))


def en_retiro(fecha_ultima_dosis, dias_retiro, fecha_consulta=None) -> bool:
    """True si la fecha de consulta cae dentro del periodo de retiro."""
    if dias_retiro is None or int(dias_retiro) <= 0:
        return False
    fin = fecha_fin_retiro(fecha_ultima_dosis, dias_retiro)
    if fin is None:
        return False
    consulta = to_date(fecha_consulta) if fecha_consulta else date.today()
    inicio = to_date(fecha_ultima_dosis)
    if inicio is None:
        return False
    return inicio <= consulta <= fin


def bloqueo_ordenio(fecha_ultima_dosis, dias_retiro_leche, fecha_consulta=None) -> bool:
    """Bloqueo de leche: True si está en retiro de leche."""
    return en_retiro(fecha_ultima_dosis, dias_retiro_leche, fecha_consulta)


def bloqueo_carne(fecha_ultima_dosis, dias_retiro_carne, fecha_consulta=None) -> bool:
    """Bloqueo de carne: True si está en retiro de carne."""
    return en_retiro(fecha_ultima_dosis, dias_retiro_carne, fecha_consulta)


class HealthEngine:
    """Contenedor de cálculos sanitarios (métodos estáticos)."""

    @staticmethod
    def fecha_fin_retiro(fecha_ultima_dosis, dias_retiro):
        return fecha_fin_retiro(fecha_ultima_dosis, dias_retiro)

    @staticmethod
    def en_retiro(fecha_ultima_dosis, dias_retiro, fecha_consulta=None):
        return en_retiro(fecha_ultima_dosis, dias_retiro, fecha_consulta)

    @staticmethod
    def bloqueo_ordenio(fecha_ultima_dosis, dias_retiro_leche, fecha_consulta=None):
        return bloqueo_ordenio(fecha_ultima_dosis, dias_retiro_leche, fecha_consulta)

    @staticmethod
    def bloqueo_carne(fecha_ultima_dosis, dias_retiro_carne, fecha_consulta=None):
        return bloqueo_carne(fecha_ultima_dosis, dias_retiro_carne, fecha_consulta)

    @staticmethod
    def calcular_fin_retiros(fecha_dosis, dias_leche, dias_carne) -> dict:
        return {
            "fecha_fin_retiro_leche": iso(fecha_fin_retiro(fecha_dosis, dias_leche)),
            "fecha_fin_retiro_carne": iso(fecha_fin_retiro(fecha_dosis, dias_carne)),
        }
