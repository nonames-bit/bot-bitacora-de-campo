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

    @staticmethod
    def indice_fertilidad(total_prenadas: int, vacas_descanso: int, total_vientres: int) -> dict:
        return calcular_indice_fertilidad(total_prenadas, vacas_descanso, total_vientres)

    @staticmethod
    def categorizar_dias_abiertos(da: int | None) -> str:
        return tramo_dias_abiertos(da)

    @staticmethod
    def categorizar_iep(iep: int | None) -> str:
        return tramo_iep(iep)

    @staticmethod
    def categorizar_del(del_dias: int | None) -> str:
        return tramo_del(del_dias)


def calcular_indice_fertilidad(
    total_prenadas: int,
    vacas_descanso_postparto: int,
    total_vientres_aptos: int,
) -> dict:
    """Calcula el Índice de Fertilidad (I.F.) oficial según la metodología de Software Ganadero:
    I.F. = ((Hembras Preñadas + Vacas <= 120 días postparto) / Vientres Aptos) * 100
    """
    p = max(0, int(total_prenadas or 0))
    d = max(0, int(vacas_descanso_postparto or 0))
    v = max(0, int(total_vientres_aptos or 0))
    numerador = p + d
    pct = round((numerador / v) * 100, 2) if v > 0 else 0.0
    # Evaluación semafórica zootécnica
    if pct >= 75.0:
        semaforo = "🟢"
        diagnostico = "Excelente eficiencia reproductiva"
    elif pct >= 60.0:
        semaforo = "🟡"
        diagnostico = "Eficiencia aceptable / seguimiento"
    else:
        semaforo = "🔴"
        diagnostico = "Alerta reproductiva (bajo porcentaje preñado/descanso)"

    return {
        "indice_pct": pct,
        "prenadas": p,
        "en_descanso": d,
        "numerador_util": numerador,
        "total_vientres": v,
        "semaforo": semaforo,
        "diagnostico": diagnostico,
    }


def tramo_dias_abiertos(da: int | None) -> str:
    """Clasifica los Días Abiertos según los brackets de Software Ganadero."""
    if da is None:
        return "Sin dato"
    d = int(da)
    if d <= 90:
        return "0-90"
    elif d <= 120:
        return "91-120"
    elif d <= 150:
        return "121-150"
    elif d <= 180:
        return "151-180"
    elif d <= 210:
        return "181-210"
    elif d <= 240:
        return "211-240"
    elif d <= 270:
        return "241-270"
    elif d <= 300:
        return "271-300"
    else:
        return ">300"


def tramo_iep(iep: int | None) -> str:
    """Clasifica el Intervalo Entre Partos según los brackets de Software Ganadero."""
    if iep is None:
        return "Sin dato"
    i = int(iep)
    if i < 365:
        return "<365"
    elif i <= 395:
        return "365-395"
    elif i <= 425:
        return "396-425"
    elif i <= 455:
        return "426-455"
    elif i <= 485:
        return "456-485"
    else:
        return ">485"


def tramo_del(del_dias: int | None) -> str:
    """Clasifica los Días En Leche (DEL) según las etapas de la curva de lactancia de Software Ganadero."""
    if del_dias is None:
        return "Sin dato"
    d = int(del_dias)
    if d <= 100:
        return "0-100 (Pico)"
    elif d <= 200:
        return "101-200 (Meseta)"
    elif d <= 340:
        return "201-340 (Descenso)"
    else:
        return ">340 (Prolongada)"

