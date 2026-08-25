"""Utilidades compartidas: normalización de texto y manejo de fechas."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta


def normalizar(texto: str | None) -> str:
    """Devuelve el texto en minúsculas, sin tildes y con espacios colapsados.

    Se usa para que las expresiones regulares del parser sean insensibles a
    acentos, mayúsculas y espacios redundantes de las notas de campo.
    """
    if texto is None:
        return ""
    s = str(texto).lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def to_date(valor) -> date | None:
    """Convierte una fecha en distintos formatos a ``datetime.date`` (o None)."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1]))
    return None


def iso(valor) -> str | None:
    """Devuelve la fecha en formato ISO ``YYYY-MM-DD`` (o None)."""
    d = to_date(valor)
    return d.isoformat() if d else None


def add_days(valor, dias: int) -> date | None:
    """Suma ``dias`` días a una fecha (acepta varios formatos)."""
    d = to_date(valor)
    return d + timedelta(days=dias) if d else None


def hoy() -> date:
    """Fecha de hoy."""
    return date.today()


def parse_fecha(texto: str, base: date | None = None) -> date | None:
    """Extrae una fecha de lenguaje natural (hoy, ayer, ISO, DD/MM/YYYY...)."""
    if base is None:
        base = date.today()
    s = normalizar(texto)
    if s == "" or re.search(r"\bhoy\b", s):
        return base
    if re.search(r"\bayer\b", s):
        return base - timedelta(days=1)
    if re.search(r"\banteayer\b", s):
        return base - timedelta(days=2)
    if re.search(r"\bmanana\b", s):
        return base + timedelta(days=1)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        dia, mes, anio = int(m[1]), int(m[2]), int(m[3])
        if anio < 100:
            anio += 2000
        return date(anio, mes, dia)
    return None


def a_float(valor, default: float | None = None) -> float | None:
    """Convierte un valor a float reemplazando coma decimal, o devuelve default."""
    if valor is None or valor == "":
        return default
    try:
        return float(str(valor).replace(",", "."))
    except (ValueError, TypeError):
        return default
