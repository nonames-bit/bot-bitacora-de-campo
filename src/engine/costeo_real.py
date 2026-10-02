"""Costos reales a partir de los gastos registrados en Finanzas (Fase 6).

Antes la ficha de cada animal usaba costos fijos de referencia ($18.000 por
tratamiento, $28.000 de sostenimiento por mes) y los indicadores del hato
dividían TODOS los gastos entre los litros y TODOS otra vez entre los kg
vendidos, así que cada peso se contaba dos veces.

Ahora:
- Hato (``reparto_leche_carne``): los gastos del periodo se reparten entre
  leche y carne. La compra de animales va completa a carne; el resto se
  reparte según la parte del hato que son vacas en ordeño (si no se sabe,
  según lo que aporta cada línea a los ingresos).
- Animal (``tarifas_reales`` + ``gastos_del_animal``): el sostenimiento por
  cabeza al mes y el costo promedio por tratamiento salen de los gastos de
  los últimos 12 meses; los gastos anotados a nombre del animal y su precio
  de compra se suman directo. Los costos de referencia quedan solo como
  respaldo cuando no hay gastos registrados, y se marca en pantalla.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

# Costos de referencia: solo se usan si la finca no tiene gastos registrados.
REF_SOSTENIMIENTO_MES = 28000.0
REF_TRATAMIENTO = 18000.0
REF_PAJUELA = 45000.0
REF_SERVICIO_MONTA = 35000.0

# Estas categorías se cobran por evento (tratamiento, inseminación) y no
# entran en el sostenimiento mensual, para no contarlas dos veces.
CATEGORIAS_SANIDAD = ("MEDICAMENTOS", "VETERINARIO")
CATEGORIAS_REPRODUCCION = ("REPRODUCCION",)

VENTANA_DIAS = 365
DIAS_MES = VENTANA_DIAS / 12


def reparto_leche_carne(
    gastos_operativos: float,
    compras_animales: float,
    vacas_ordeno: int,
    total_activos: int,
    ingresos_leche: float,
    ingresos_carne: float,
    litros: float,
) -> dict[str, Any]:
    """Qué parte de los gastos le toca a la leche y cuál a la carne.

    Devuelve ``fraccion_leche`` (0..1), ``metodo`` y los totales por línea."""
    if vacas_ordeno > 0 and total_activos > 0:
        fraccion = min(1.0, vacas_ordeno / total_activos)
        metodo = "vacas_ordeno"
    elif ingresos_leche + ingresos_carne > 0:
        fraccion = ingresos_leche / (ingresos_leche + ingresos_carne)
        metodo = "ingresos"
    elif litros > 0:
        fraccion = 1.0
        metodo = "solo_leche"
    else:
        fraccion = 0.0
        metodo = "solo_carne"
    costo_leche = gastos_operativos * fraccion
    costo_carne = gastos_operativos * (1 - fraccion) + compras_animales
    return {
        "fraccion_leche": fraccion,
        "metodo": metodo,
        "costo_leche": round(costo_leche, 2),
        "costo_carne": round(costo_carne, 2),
    }


def desglose_por_unidad(
    gastos_por_categoria: dict[str, float],
    fraccion: float,
    unidades: float,
    extra: Optional[dict[str, float]] = None,
) -> list[dict[str, Any]]:
    """De cada litro (o kg), cuánto se va en cada categoría de gasto."""
    if unidades <= 0:
        return []
    filas = []
    for cat, total in gastos_por_categoria.items():
        valor = total * fraccion / unidades
        if valor > 0:
            filas.append({"categoria": cat, "por_unidad": round(valor, 2)})
    for cat, total in (extra or {}).items():
        if total > 0:
            filas.append({"categoria": cat, "por_unidad": round(total / unidades, 2)})
    filas.sort(key=lambda f: f["por_unidad"], reverse=True)
    return filas


def tarifas_reales(db, hoy: Optional[date] = None) -> dict[str, Any]:
    """Sostenimiento por cabeza al mes y costo por tratamiento, con los
    gastos de los últimos 12 meses. Si no hay gastos, los de referencia."""
    hoy = hoy or date.today()
    desde = (hoy - timedelta(days=VENTANA_DIAS)).isoformat()
    hasta = hoy.isoformat()

    filas = db.query(
        "SELECT UPPER(categoria) AS categoria, SUM(monto) AS total, MIN(fecha) AS primera "
        "FROM finanzas WHERE UPPER(tipo) = 'EGRESO' AND fecha >= ? AND fecha <= ? "
        "AND animal_id IS NULL GROUP BY UPPER(categoria)",
        (desde, hasta),
    )
    sanidad = sum(float(f["total"] or 0) for f in filas if f["categoria"] in CATEGORIAS_SANIDAD)
    general = sum(
        float(f["total"] or 0) for f in filas
        if f["categoria"] not in CATEGORIAS_SANIDAD + CATEGORIAS_REPRODUCCION
    )
    primeras = [str(f["primera"])[:10] for f in filas if f["primera"]]
    meses = VENTANA_DIAS / DIAS_MES
    if primeras:
        try:
            dias = (hoy - date.fromisoformat(min(primeras))).days + 1
            meses = min(meses, max(1.0, dias / DIAS_MES))
        except ValueError:
            pass

    activos = db.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO'")["n"] or 0
    n_trat = db.query_one(
        "SELECT COUNT(*) AS n FROM tratamientos WHERE fecha >= ? AND fecha <= ?", (desde, hasta)
    )["n"] or 0

    if general > 0 and activos > 0:
        sost = round(general / activos / meses, 0)
        sost_real = True
    else:
        sost = REF_SOSTENIMIENTO_MES
        sost_real = False
    if sanidad > 0 and n_trat > 0:
        trat = round(sanidad / n_trat, 0)
        trat_real = True
    else:
        trat = REF_TRATAMIENTO
        trat_real = False

    return {
        "sostenimiento_mes": sost,
        "sostenimiento_real": sost_real,
        "tratamiento": trat,
        "tratamiento_real": trat_real,
        "meses_datos": round(meses, 1),
        "activos": activos,
    }


def gastos_del_animal(db, animal_id: int) -> dict[str, Any]:
    """Gastos anotados a nombre del animal, su precio de compra y la fecha
    de la última compra (el sostenimiento cuenta desde ahí: lo de antes ya
    viene dentro del precio)."""
    fila = db.query_one(
        "SELECT SUM(monto) AS total FROM finanzas WHERE animal_id = ? AND UPPER(tipo) = 'EGRESO'",
        (animal_id,),
    )
    compra = db.query_one(
        "SELECT SUM(precio) AS total, MAX(fecha) AS fecha FROM movimientos WHERE animal_id = ? "
        "AND UPPER(tipo_movimiento) = 'COMPRA' AND precio > 0",
        (animal_id,),
    )
    return {
        "gastos_propios": float(fila["total"] or 0.0) if fila else 0.0,
        "compra": float(compra["total"] or 0.0) if compra else 0.0,
        "fecha_compra": str(compra["fecha"])[:10] if (compra and compra["fecha"]) else None,
    }
