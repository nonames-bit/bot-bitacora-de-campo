"""Motor genético zootécnico: fracciones estándar, herencia mendeliana y cruces absorbentes.

Dominio: Finca > Genética, Trazabilidad & Registros (skill @trazabilidad-ganadera).

Reglas zootécnicas de fracciones y cruzamientos:
- 100.0% -> Puro
- >= 96.875% (o ~96.87%) -> Puro por Cruce (PC) [31/32]
- 93.75% -> 15/16
- 87.5%  -> 7/8
- 81.25% -> 13/16
- 75.0%  -> 3/4
- 68.75% -> 11/16
- 62.5%  -> 5/8
- 56.25% -> 9/16
- 50.0%  -> 1/2 (o F1 si es cruce de 2 razas puras)
- 43.75% -> 7/16
- 37.5%  -> 3/8
- 31.25% -> 5/16
- 25.0%  -> 1/4
- 18.75% -> 3/16
- 12.5%  -> 1/8
- 6.25%  -> 1/16
- 3.125% -> 1/32
- 33.33% -> 1/3
- 66.67% -> 2/3

Herencia de cruces absorbentes (upgrading / grading up):
Cría[raza] = 0.5 * Madre[raza] + 0.5 * Padre[raza]
"""
from __future__ import annotations

import re
from typing import Optional

# Catálogo canónico de razas bovinas comunes en el trópico y software ganadero
CATALOGO_RAZAS_PREDEFINIDAS = [
    "Brahman",
    "Romosinuano",
    "Gyr",
    "Guzerá",
    "Nelore",
    "Holstein",
    "Jersey",
    "Pardo Suizo",
    "Simmental",
    "Simbrah",
    "Senepol",
    "Blanco Orejinegro (BON)",
    "Costeño con Cuernos (CCC)",
    "Sanmartinero",
    "Hartón del Valle",
    "Brangus",
    "Angus",
    "Charolais",
    "Girolando",
    "Cebú Comercial",
    "Mestizo",
    "Criollo",
]

# Tabla de fracciones zootécnicas estándar ordenadas por porcentaje
# (porcentaje_nominal, etiqueta_fraccion, es_puro_por_cruce)
FRACCIONES_ESTANDAR: list[tuple[float, str, bool]] = [
    (100.0, "Puro", False),
    (96.875, "Puro por Cruce (PC)", True),
    (93.75, "15/16", False),
    (87.5, "7/8", False),
    (81.25, "13/16", False),
    (75.0, "3/4", False),
    (68.75, "11/16", False),
    (66.667, "2/3", False),
    (62.5, "5/8", False),
    (56.25, "9/16", False),
    (50.0, "1/2", False),
    (43.75, "7/16", False),
    (37.5, "3/8", False),
    (33.333, "1/3", False),
    (31.25, "5/16", False),
    (25.0, "1/4", False),
    (18.75, "3/16", False),
    (12.5, "1/8", False),
    (6.25, "1/16", False),
    (3.125, "1/32", False),
]


def porcentaje_a_fraccion(porcentaje: float, tolerancia: float = 0.6) -> str:
    """Traduce un porcentaje decimal a la fracción o nomenclatura estándar zootécnica.

    Ejemplos:
        50.0   -> "1/2"
        75.0   -> "3/4"
        87.5   -> "7/8"
        93.75  -> "15/16"
        96.87  -> "Puro por Cruce (PC)"
        100.0  -> "Puro"
        62.5   -> "5/8"
        37.5   -> "3/8"
        12.5   -> "1/8"
        40.0   -> "40%"
    """
    if porcentaje is None:
        return "S/D"

    try:
        pct = float(porcentaje)
    except (ValueError, TypeError):
        return "S/D"

    if pct <= 0.0:
        return "0%"
    if pct >= 99.5:
        return "Puro"
    if pct >= 96.5:
        return "Puro por Cruce (PC)"

    for nom, frac, _ in FRACCIONES_ESTANDAR:
        if abs(pct - nom) <= tolerancia:
            return frac

    # Si no encaja en una fracción estándar con tolerancia, mostrar el porcentaje formateado
    if abs(pct - round(pct)) < 0.05:
        return f"{int(round(pct))}%"
    return f"{round(pct, 1)}%"


def formatear_raza_etiqueta(raza: str, porcentaje: float, es_f1: bool = False) -> str:
    """Retorna una etiqueta enriquecida para una raza individual con su fracción y porcentaje.

    Ej: 'Brahman 1/2 (50%)' o 'Gyr 3/4 (75%)' o 'Brahman Puro (100%)' o 'Brahman F1 (50%)'
    """
    frac = porcentaje_a_fraccion(porcentaje)
    if frac == "1/2" and es_f1:
        frac = "1/2 (F1)"
    pct_str = f"{int(round(porcentaje))}%" if abs(porcentaje - round(porcentaje)) < 0.05 else f"{round(porcentaje, 1)}%"
    if frac == "Puro":
        return f"{raza} Puro"
    return f"{frac} {raza} ({pct_str})"


def normalizar_nombre_raza(nombre_raza: str) -> str:
    """Normaliza nombres y alias comunes de razas bovinas para unificación."""
    if not nombre_raza:
        return ""
    r = str(nombre_raza).strip()
    r_up = r.upper()

    # Mapeo de códigos SG y sinónimos comunes
    mapeo = {
        "BRAHMAN": "Brahman",
        "BRA": "Brahman",
        "CEBU": "Cebú Comercial",
        "CEBÚ": "Cebú Comercial",
        "GYR": "Gyr",
        "GIR": "Gyr",
        "GUZERA": "Guzerá",
        "GUZERÁ": "Guzerá",
        "GUZ": "Guzerá",
        "NELORE": "Nelore",
        "NEL": "Nelore",
        "ROMOSINUANO": "Romosinuano",
        "ROMO": "Romosinuano",
        "RS": "Romosinuano",
        "HOLSTEIN": "Holstein",
        "HOL": "Holstein",
        "JERSEY": "Jersey",
        "JER": "Jersey",
        "PARDO SUIZO": "Pardo Suizo",
        "PARDO": "Pardo Suizo",
        "SWISS": "Pardo Suizo",
        "SIMMENTAL": "Simmental",
        "SIM": "Simmental",
        "SIMBRAH": "Simbrah",
        "SENEPOL": "Senepol",
        "BON": "Blanco Orejinegro (BON)",
        "BLANCO OREJINEGRO": "Blanco Orejinegro (BON)",
        "CCC": "Costeño con Cuernos (CCC)",
        "COSTENO CON CUERNOS": "Costeño con Cuernos (CCC)",
        "COSTEÑO CON CUERNOS": "Costeño con Cuernos (CCC)",
        "SANMARTINERO": "Sanmartinero",
        "HARTON DEL VALLE": "Hartón del Valle",
        "HARTÓN DEL VALLE": "Hartón del Valle",
        "BRANGUS": "Brangus",
        "ANGUS": "Angus",
        "CHAROLAIS": "Charolais",
        "CHAR": "Charolais",
        "GIROLANDO": "Girolando",
        "MESTIZO": "Mestizo",
        "CRIOLLO": "Criollo",
        # Códigos de 1 letra de SG
        "C": "Cebú Comercial",
        "I": "Holstein",
        "M": "Mestizo",
        "T": "Tricross Cebú",
    }
    return mapeo.get(r_up, r)


def calcular_cruce_absorbente(
    comp_madre: list[dict],
    comp_padre: list[dict],
) -> list[dict]:
    """Calcula la composición genética de la cría a partir de madre y padre.

    Cada progenitor aporta el 50% de sus componentes raciales:
        pct_cria[raza] = 0.5 * pct_madre[raza] + 0.5 * pct_padre[raza]

    Args:
        comp_madre: lista de dicts con 'raza' y 'porcentaje'.
        comp_padre: lista de dicts con 'raza' y 'porcentaje'.

    Returns:
        Lista ordenada descendentemente por porcentaje con:
        [
            {
                "raza": "Brahman",
                "porcentaje": 50.0,
                "fraccion": "1/2",
                "etiqueta": "1/2 Brahman (50%)",
            },
            ...
        ]
    """
    aportes: dict[str, float] = {}

    def _procesar_padre(comp: list[dict], factor: float):
        if not comp:
            return
        total_p = sum(float(c.get("porcentaje") or 0.0) for c in comp)
        if total_p <= 0.0:
            return
        for c in comp:
            raza = normalizar_nombre_raza(c.get("raza") or "Sin Raza")
            pct_raw = float(c.get("porcentaje") or 0.0)
            # Normalizar al factor (si el total no es exactamente 100, se escala proporcionalmente)
            pct_normalizado = (pct_raw / total_p) * 100.0
            aportes[raza] = aportes.get(raza, 0.0) + (pct_normalizado * factor)

    _procesar_padre(comp_madre, 0.5)
    _procesar_padre(comp_padre, 0.5)

    if not aportes:
        return []

    # Ajustar para asegurar que la suma dé 100.0 si ambos progenitores aportaron
    suma_total = sum(aportes.values())
    if abs(suma_total - 100.0) > 0.01 and suma_total > 0:
        factor_ajuste = 100.0 / suma_total
        aportes = {r: p * factor_ajuste for r, p in aportes.items()}

    # Verificar si es un F1 verdadero (exactamente 2 razas al 50% cada una)
    es_f1 = (len(aportes) == 2 and all(abs(p - 50.0) <= 0.5 for p in aportes.values()))

    # Convertir a lista y ordenar de mayor a menor porcentaje
    resultado = []
    for raza, pct in sorted(aportes.items(), key=lambda x: x[1], reverse=True):
        pct_red = round(pct, 2)
        frac = porcentaje_a_fraccion(pct_red)
        if frac == "1/2" and es_f1:
            frac = "1/2 o F1"
        resultado.append({
            "raza": raza,
            "porcentaje": pct_red,
            "fraccion": frac,
            "etiqueta": formatear_raza_etiqueta(raza, pct_red, es_f1=es_f1),
        })

    return resultado


def generar_resumen_zootecnico(composicion: list[dict]) -> str:
    """Genera la cadena zootécnica estándar para almacenar o mostrar en cabeceras.

    Ejemplos:
        [{"raza": "Brahman", "porcentaje": 100.0}] -> "Brahman Puro"
        [{"raza": "Brahman", "porcentaje": 50.0}, {"raza": "Romosinuano", "porcentaje": 50.0}]
            -> "1/2 Brahman + 1/2 Romosinuano"
        [{"raza": "Brahman", "porcentaje": 50.0}, {"raza": "Gyr", "porcentaje": 37.5}, {"raza": "Holstein", "porcentaje": 12.5}]
            -> "1/2 Brahman + 3/8 Gyr + 1/8 Holstein"
    """
    if not composicion:
        return "Sin Raza"

    if len(composicion) == 1:
        c = composicion[0]
        pct = float(c.get("porcentaje") or 0.0)
        raza = c.get("raza") or "Sin Raza"
        if pct >= 99.0:
            return f"{raza} Puro"
        frac = porcentaje_a_fraccion(pct)
        return f"{frac} {raza}"

    partes = []
    for c in composicion:
        raza = c.get("raza") or "Sin Raza"
        pct = float(c.get("porcentaje") or 0.0)
        frac = c.get("fraccion") or porcentaje_a_fraccion(pct)
        # Si la fracción contiene "o F1", dejamos solo "1/2" en el resumen compacto
        if "1/2" in frac:
            frac = "1/2"
        elif "PC" in frac or "Puro por Cruce" in frac:
            frac = "PC"
        partes.append(f"{frac} {raza}")

    return " + ".join(partes)


def parsear_texto_raza(texto: Optional[str]) -> list[dict]:
    """Interpreta un string de raza existente y extrae las componentes y porcentajes.

    Soporta:
        - "3/4 Gyr + 1/4 Holstein"
        - "50% Brahman y 50% Romosinuano"
        - "1/2 Brahman + 3/8 Gyr + 1/8 Holstein"
        - "Brahman" / "Gyr Puro"
    """
    if not texto or not str(texto).strip():
        return []

    t = str(texto).strip()

    # Si es una sola raza pura o simple
    if "+" not in t and "," not in t and " y " not in t and "/" not in t and "%" not in t:
        r_limpia = re.sub(r"\b(puro|pura|pc)\b", "", t, flags=re.IGNORECASE).strip()
        norm = normalizar_nombre_raza(r_limpia or t)
        return [{
            "raza": norm,
            "porcentaje": 100.0,
            "fraccion": "Puro",
            "etiqueta": f"{norm} Puro",
        }]

    # Si contiene porcentajes explícitos ej: "50% Brahman, 50% Romosinuano" o "50% Brahman + 50% Romo"
    tokens = re.split(r"[+,;\n]| y ", t)
    resultado = []
    total_pct = 0.0

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue

        # Caso: "50% Brahman" o "Brahman 50%"
        m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", tok)
        # Caso: "3/4 Gyr" o "1/2 Brahman"
        m_frac = re.search(r"(\d+)\s*/\s*(\d+)", tok)

        raza_str = re.sub(r"(\d+(?:\.\d+)?\s*%|\d+\s*/\s*\d+|puro|pc)", "", tok, flags=re.IGNORECASE).strip()
        norm_raza = normalizar_nombre_raza(raza_str) or "Mestizo"

        pct_val = None
        if m_pct:
            try:
                pct_val = float(m_pct.group(1))
            except ValueError:
                pass
        elif m_frac:
            try:
                num = float(m_frac.group(1))
                den = float(m_frac.group(2))
                if den > 0:
                    pct_val = (num / den) * 100.0
            except ValueError:
                pass

        if pct_val is not None:
            pct_red = round(pct_val, 2)
            resultado.append({
                "raza": norm_raza,
                "porcentaje": pct_red,
                "fraccion": porcentaje_a_fraccion(pct_red),
                "etiqueta": formatear_raza_etiqueta(norm_raza, pct_red),
            })
            total_pct += pct_val

    if resultado:
        # Si la suma de los porcentajes no da 100 y faltan razas o hay desajuste
        return sorted(resultado, key=lambda x: x["porcentaje"], reverse=True)

    # Fallback si no pudo parsear fracciones ni %
    norm = normalizar_nombre_raza(t)
    return [{
        "raza": norm,
        "porcentaje": 100.0,
        "fraccion": "Puro",
        "etiqueta": f"{norm} Puro",
    }]
