"""Categorías del libro de Finanzas (ingresos/egresos), en un solo lugar.

Las usan la vista de Finanzas, la lectura de facturas con IA (PWA y
Telegram) y /api/sync. La venta/compra de animales no está aquí: vive en
``movimientos`` con su precio (ver ``Database.resumen_finanzas``).

Sal, drogas, alimento, abonos y pajillas van aparte de "Insumos" y
"Veterinario" para que el dueño vea en qué se va la plata (2026-10-01).
Los registros viejos conservan su categoría: INSUMO y VETERINARIO siguen
siendo válidas.
"""
from __future__ import annotations

CATEGORIAS_INGRESO = ("VENTA_LECHE", "OTRO_INGRESO")

CATEGORIAS_EGRESO = (
    "SAL_MINERALES", "MEDICAMENTOS", "ALIMENTO", "FERTILIZANTES", "REPRODUCCION",
    "INSUMO", "NOMINA", "VETERINARIO", "INFRAESTRUCTURA", "COMBUSTIBLE", "OTRO_EGRESO",
)

ETIQUETAS = {
    "VENTA_LECHE": "Venta de leche",
    "OTRO_INGRESO": "Otro ingreso",
    "SAL_MINERALES": "Sal y minerales",
    "MEDICAMENTOS": "Drogas / medicamentos",
    "ALIMENTO": "Concentrado / alimento",
    "FERTILIZANTES": "Abonos, semillas y venenos de potrero",
    "REPRODUCCION": "Pajillas / nitrógeno",
    "INSUMO": "Otros insumos (alambre, herramienta, etc.)",
    "NOMINA": "Nómina / jornales",
    "VETERINARIO": "Veterinario (visita / servicio)",
    "INFRAESTRUCTURA": "Infraestructura / mantenimiento",
    "COMBUSTIBLE": "Combustible",
    "OTRO_EGRESO": "Otro gasto",
}


def tipo_de_categoria(categoria: str) -> str:
    return "INGRESO" if str(categoria or "").upper() in CATEGORIAS_INGRESO else "EGRESO"


def normalizar_categoria(categoria: str, tipo: str = "EGRESO") -> str:
    """La categoría en mayúsculas si es conocida; si no, "otro" del tipo."""
    cat = str(categoria or "").strip().upper()
    validas = CATEGORIAS_INGRESO if str(tipo).upper() == "INGRESO" else CATEGORIAS_EGRESO
    if cat in validas:
        return cat
    return "OTRO_INGRESO" if str(tipo).upper() == "INGRESO" else "OTRO_EGRESO"
