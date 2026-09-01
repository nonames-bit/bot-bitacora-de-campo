"""Motor reproductivo: FEP, ecografía, palpación, secado, días abiertos, IEP.

Constantes y fórmulas zootécnicas (skill ``@inseminacion-calc``):
- Gestación bovina promedio: 283 días.
- FEP = Fecha_IA + 283 días.
- Ecografía: Fecha_IA + 35 días. Palpación rectal: Fecha_IA + 60 días.
- Secado: FEP - 60 días (equivalente al día 223 de gestación).
- Días Abiertos = Fecha_Concepción - Fecha_Último_Parto.
- IEP proyectado = Días Abiertos + 283 días.
"""
from __future__ import annotations

from datetime import date

from ..utils import add_days, iso, to_date

GESTACION_DIAS = 283
ECOGRAFIA_DIAS = 35
PALPACION_DIAS = 60
SECADO_ANTES_PART = 60
DIAS_ABIERTOS_META = 110
IEP_META_DIAS = 400
INTERVALO_RECARGA_N2_DIAS = 21


def fecha_estimada_parto(fecha_servicio) -> date | None:
    """Fecha Estimada de Parto: fecha de servicio + 283 días."""
    return add_days(fecha_servicio, GESTACION_DIAS)


def fecha_ecografia(fecha_servicio) -> date | None:
    """Fecha programada de ecografía: servicio + 35 días."""
    return add_days(fecha_servicio, ECOGRAFIA_DIAS)


def fecha_palpacion(fecha_servicio) -> date | None:
    """Fecha programada de palpación rectal: servicio + 60 días."""
    return add_days(fecha_servicio, PALPACION_DIAS)


def fecha_secado(fep) -> date | None:
    """Fecha de secado de la vaca lechera: FEP - 60 días."""
    return add_days(fep, -SECADO_ANTES_PART)


def dias_abiertos(fecha_concepcion, fecha_ultimo_parto) -> int | None:
    """Días abiertos entre concepción/servicio y el último parto."""
    c = to_date(fecha_concepcion)
    p = to_date(fecha_ultimo_parto)
    if c is None or p is None:
        return None
    return (c - p).days


def iep_proyectado(dias_abiertos_valor: int) -> int:
    """Intervalo Entre Partos proyectado = días abiertos + 283."""
    return int(dias_abiertos_valor) + GESTACION_DIAS


def programar_inseminacion(fecha_celo, am_pm=None) -> dict:
    """Regla AM-PM para la inseminación programada.

    - Celo detectado en la mañana (AM) → inseminar en la tarde del mismo día.
    - Celo detectado en la tarde/noche (PM) → inseminar en la mañana siguiente.
    Devuelve ``{"fecha": date|None, "franja": "tarde"|"mañana"}``.
    """
    if (am_pm or "").upper() == "PM":
        return {"fecha": add_days(fecha_celo, 1), "franja": "mañana"}
    return {"fecha": to_date(fecha_celo), "franja": "tarde"}


def calcular_proxima_recarga_n2(fecha_ultima_recarga, intervalo_dias: int = INTERVALO_RECARGA_N2_DIAS) -> date | None:
    """Calcula la fecha de la próxima recarga de nitrógeno líquido para el termo criogénico."""
    return add_days(fecha_ultima_recarga, int(intervalo_dias))


def calcular_alerta_nitrogeno(
    fecha_ultima_recarga,
    intervalo_dias: int = INTERVALO_RECARGA_N2_DIAS,
    hoy: date | None = None,
    umbral_alerta: int = 3,
) -> dict:
    """Evalúa el estado de evaporación del nitrógeno líquido en el termo.

    Avisa si faltan <= umbral_alerta días (default 3 días) para vencer los 21-30 días
    desde la última recarga registrada.
    """
    f_rec = to_date(fecha_ultima_recarga)
    if not f_rec:
        return {
            "fecha_recarga": None,
            "proxima_recarga": None,
            "dias_intervalo": intervalo_dias,
            "dias_desde_recarga": 0,
            "dias_restantes": 0,
            "alerta": False,
            "vencido": False,
            "mensaje": "Sin registro de recarga de nitrógeno",
        }

    fecha_ref = to_date(hoy) or date.today()
    prox = add_days(f_rec, int(intervalo_dias))
    dias_desde = (fecha_ref - f_rec).days
    dias_restantes = (prox - fecha_ref).days if prox else 0
    alerta = dias_restantes <= umbral_alerta
    vencido = dias_restantes < 0

    if vencido:
        msg = f"Nitrógeno VENCIDO hace {abs(dias_restantes)} días"
    elif dias_restantes == 0:
        msg = "Nitrógeno recargar HOY"
    elif dias_restantes == 1:
        msg = "Nitrógeno recargar en 1 día"
    else:
        msg = f"Nitrógeno recargar en {dias_restantes} días"

    return {
        "fecha_recarga": iso(f_rec),
        "proxima_recarga": iso(prox),
        "dias_intervalo": int(intervalo_dias),
        "dias_desde_recarga": dias_desde,
        "dias_restantes": dias_restantes,
        "alerta": alerta,
        "vencido": vencido,
        "mensaje": msg,
    }


class ReproductiveEngine:
    """Contenedor de los cálculos reproductivos (métodos estáticos)."""

    @staticmethod
    def fep(fecha_servicio):
        return fecha_estimada_parto(fecha_servicio)

    @staticmethod
    def ecografia(fecha_servicio):
        return fecha_ecografia(fecha_servicio)

    @staticmethod
    def palpacion(fecha_servicio):
        return fecha_palpacion(fecha_servicio)

    @staticmethod
    def secado(fep):
        return fecha_secado(fep)

    @staticmethod
    def dias_abiertos(fecha_concepcion, fecha_ultimo_parto):
        return dias_abiertos(fecha_concepcion, fecha_ultimo_parto)

    @staticmethod
    def iep_proyectado(dias_abiertos_valor):
        return iep_proyectado(dias_abiertos_valor)

    @staticmethod
    def proxima_recarga_n2(fecha_ultima_recarga, intervalo_dias: int = INTERVALO_RECARGA_N2_DIAS):
        return calcular_proxima_recarga_n2(fecha_ultima_recarga, intervalo_dias)

    @staticmethod
    def alerta_nitrogeno(fecha_ultima_recarga, intervalo_dias: int = INTERVALO_RECARGA_N2_DIAS, hoy: date | None = None, umbral_alerta: int = 3):
        return calcular_alerta_nitrogeno(fecha_ultima_recarga, intervalo_dias, hoy, umbral_alerta)

    @staticmethod
    def programar(fecha_servicio) -> dict:
        """Devuelve el calendario completo de chequeos de un servicio."""
        return {
            "fep": iso(fecha_estimada_parto(fecha_servicio)),
            "ecografia": iso(fecha_ecografia(fecha_servicio)),
            "palpacion": iso(fecha_palpacion(fecha_servicio)),
            "secado": iso(fecha_secado(fecha_estimada_parto(fecha_servicio))),
        }

    @staticmethod
    def programar_inseminacion(fecha_celo, am_pm=None) -> dict:
        return programar_inseminacion(fecha_celo, am_pm)
