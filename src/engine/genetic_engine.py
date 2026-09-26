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
    "Ayrshire",
    "Brahman",
    "Romosinuano",
    "Gyr",
    "Guzerá",
    "Nelore",
    "Holstein",
    "Holstein Rojo",
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


# Tipos de raza de SG que no identifican una raza concreta.
_NO_RAZAS = {"Mestizo", "Taurino", "Cebuino", "Indeterminado", "Desconocida", "Sin Raza"}
_TIPOS_SG_SIN_RAZA = {"I", "C", "T", "INDETERMINADO", "CEBUINO", "CEBU", "TAURINO"}

# (porcentaje nominal, código, fracción, color, tolerancia): grados del cruce
# absorbente que no cubren las bandas 1/2, 5/8, 3/4, 7/8 y Puro.
_GRADOS_DIECISEISAVOS = [
    (93.75, "15_16", "15/16", "morado", 2.0),
    (81.25, "13_16", "13/16", "azul", 1.0),
    (68.75, "11_16", "11/16", "ambar", 1.0),
    (56.25, "9_16", "9/16", "lima", 1.0),
]
_NOMBRES_DIECISEISAVOS = {
    "15_16": "Quince Dieciseisavos",
    "13_16": "Trece Dieciseisavos",
    "11_16": "Once Dieciseisavos",
    "9_16": "Nueve Dieciseisavos",
}


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
        "CEBUINO": "Cebú Comercial",
        "CEBUINA": "Cebú Comercial",
        "CEBÚ COMERC": "Cebú Comercial",
        "CEBU COMERC": "Cebú Comercial",
        "CEBÚ COMERCIAL": "Cebú Comercial",
        "CEBU COMERCIAL": "Cebú Comercial",
        "CEBÚ ROJO": "Cebú Comercial",
        "CEBU ROJO": "Cebú Comercial",
        "CEBÚ ROJO PURO": "Cebú Comercial",
        "CEBU ROJO PURO": "Cebú Comercial",
        "CEBÚ COMERCIAL PURO": "Cebú Comercial",
        "GYR": "Gyr",
        "GIR": "Gyr",
        "GUZERA": "Guzerá",
        "GUZERÁ": "Guzerá",
        "GUZ": "Guzerá",
        "GUZERAT": "Guzerá",
        "NELORE": "Nelore",
        "NEL": "Nelore",
        "ROMOSINUANO": "Romosinuano",
        "ROMO": "Romosinuano",
        "RS": "Romosinuano",
        "HOLSTEIN": "Holstein",
        "HOL": "Holstein",
        "HOLSTEIN NEG": "Holstein",
        "HOLSTEIN NEGRO": "Holstein",
        "HOLSTEIN ROJO": "Holstein Rojo",
        "HOLSTEIN R.": "Holstein Rojo",
        "HOLSTEÍN R.": "Holstein Rojo",
        "HOLSTEIN COLORADO": "Holstein Rojo",
        "JERSEY": "Jersey",
        "JER": "Jersey",
        "PARDO SUIZO": "Pardo Suizo",
        "PARDO": "Pardo Suizo",
        "SWISS": "Pardo Suizo",
        "PARDO COL": "Pardo Suizo",
        "PARDO COLOMBIANO": "Pardo Suizo",
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
        "HARTON": "Hartón del Valle",
        "HARTÓN": "Hartón del Valle",
        "BRANGUS": "Brangus",
        "ANGUS": "Angus",
        "ANGUS N.": "Angus",
        "ANGUS NEGRO": "Angus",
        "ANGUS ROJO": "Angus",
        "BRAHMAN ROJO": "Brahman",
        "BRAHMAN GRIS": "Brahman",
        "BRAHMAN BLANCO": "Brahman",
        "BRANGUS ROJO": "Brangus",
        "BRANGUS NEGRO": "Brangus",
        "CHAROLAIS": "Charolais",
        "CHAR": "Charolais",
        "GIROLANDO": "Girolando",
        "GYROLANDO": "Girolando",
        "MESTIZO": "Mestizo",
        "7 COLORES": "Mestizo",
        "CRIOLLO": "Criollo",
        "CRIOLLA": "Criollo",
        "AYRSHIRE": "Ayrshire",
        "AYR": "Ayrshire",
        "SHORTON": "Shorthorn",
        "SHORTHORN": "Shorthorn",
        "HEREFORD": "Hereford",
        "NORMANDO": "Normando",
        "VELASQUEZ": "Velásquez",
        "VELÁSQUEZ": "Velásquez",
        "MONTBELIARDE": "Montbéliarde",
        # Códigos de tipo de raza de Software Ganadero (SG)
        "T": "Taurino",
        "C": "Cebuino",
        "I": "Indeterminado",
        "M": "Mestizo",
    }
    return mapeo.get(r_up, r)


def clasificar_animal_zootecnico(
    comp: list[dict],
    raza_str: Optional[str] = None,
) -> dict:
    """Clasifica un animal en una categoría zootécnica estándar según su composición racial o tipo.

    Categorías:
        - PURO: >= 96.0% de una sola raza (o puro por cruce)
        - F1_1_2: Cruce de 2 razas al ~50% cada una (ej. F1 Girolando 1/2 Gyr + 1/2 Holstein)
        - 3_4: Raza predominante ~75% (entre 70% y 80%)
        - 5_8: Raza predominante ~62.5% (entre 58% y 67%)
        - 7_8: Raza predominante ~87.5% (entre 84% y 92%)
        - 1_2: Media sangre con componentes multirraciales (ej. 1/2 Gyr + 1/4 Holstein + 1/4 Ayrshire)
        - MULTI: Sintéticos, multirraciales o trihíbridos
        - INDET: Sin desglose específico de razas en Software Ganadero
        - CEBU: Cebuino base sin porcentaje
        - TAURINO: Taurino base sin porcentaje
        - SIN_CLASIFICAR: Sin raza registrada
    """
    rz_str = str(raza_str or "").strip()
    if not comp and rz_str and rz_str.upper() not in _TIPOS_SG_SIN_RAZA:
        # Animal sin filas en composicion_racial pero con raza en texto
        # ("Brahman", "3/4 Gyr + 1/4 Holstein"): mismo fallback que
        # obtener_composicion_racial, en vez de "Sin Clasificar".
        comp = [c for c in parsear_texto_raza(rz_str) if c.get("raza")]
    if not comp:
        rz_up = rz_str.upper()
        if rz_up in ("INDETERMINADO", "I"):
            return {
                "grado_codigo": "INDET",
                "grado_nombre": "Indeterminados (Base SG)",
                "fraccion": "Indeterminado",
                "chip_color": "gris",
                "patron_formula": "Indeterminado / Base SG",
                "es_tipificado": False,
            }
        if rz_up in ("C", "CEBUINO", "CEBU"):
            return {
                "grado_codigo": "CEBU",
                "grado_nombre": "Cebuino Base",
                "fraccion": "Cebuino",
                "chip_color": "ambar",
                "patron_formula": "Cebuino Comercial (Base SG)",
                "es_tipificado": False,
            }
        if rz_up in ("T", "TAURINO"):
            return {
                "grado_codigo": "TAURINO",
                "grado_nombre": "Taurino Base",
                "fraccion": "Taurino",
                "chip_color": "azul",
                "patron_formula": "Taurino (Base SG)",
                "es_tipificado": False,
            }
        return {
            "grado_codigo": "SIN_CLASIFICAR",
            "grado_nombre": "Sin Clasificar",
            "fraccion": "S/C",
            "chip_color": "gris",
            "patron_formula": "Sin Clasificar",
            "es_tipificado": False,
        }

    # Normalizar componentes al 100%
    suma = sum(float(c.get("porcentaje") or 0.0) for c in comp)
    factor = 100.0 / suma if suma > 0 else 1.0
    agregados: dict[str, float] = {}
    for c in comp:
        rz = normalizar_nombre_raza(c.get("raza") or "Sin Raza")
        agregados[rz] = agregados.get(rz, 0.0) + float(c.get("porcentaje") or 0.0) * factor
    c_norm = [{"raza": rz, "porcentaje": round(p, 2)} for rz, p in agregados.items() if round(p, 2) > 0]
    c_norm.sort(key=lambda x: x["porcentaje"], reverse=True)

    if not c_norm:
        return {
            "grado_codigo": "SIN_CLASIFICAR",
            "grado_nombre": "Sin Clasificar",
            "fraccion": "S/C",
            "chip_color": "gris",
            "patron_formula": "Sin Clasificar",
            "es_tipificado": False,
        }

    max_c = c_norm[0]
    max_p = max_c["porcentaje"]
    r1 = max_c["raza"]

    # Tipos genéricos de SG que no son razas: un 100% "Mestizo" no es puro.
    if max_p >= 96.0 and r1 in _NO_RAZAS:
        base = {"Cebuino": "C", "Taurino": "T", "Indeterminado": "I"}.get(r1)
        if base:
            return clasificar_animal_zootecnico([], base)
        return {
            "grado_codigo": "MULTI",
            "grado_nombre": "Multirracial / Compuesto",
            "fraccion": "Compuesto",
            "chip_color": "naranja",
            "patron_formula": r1,
            "es_tipificado": False,
        }

    # 1. Puros o Puro por Cruce (>= 96.0%)
    if len(c_norm) == 1 or max_p >= 96.0:
        return {
            "grado_codigo": "PURO",
            "grado_nombre": "Puros & PC",
            "fraccion": "Puro",
            "chip_color": "morado",
            "patron_formula": f"{r1} Puro",
            "es_tipificado": True,
        }

    # 2. F1 verdadero (2 razas puras entre 44% y 56% cada una)
    if (len(c_norm) == 2 and abs(c_norm[0]["porcentaje"] - 50.0) <= 6.0 and abs(c_norm[1]["porcentaje"] - 50.0) <= 6.0
            and not any(c["raza"] in _NO_RAZAS for c in c_norm)):
        r2 = c_norm[1]["raza"]
        nombre_cruce = f"1/2 {r1} + 1/2 {r2}"
        if ("Gyr" in (r1, r2) and ("Holstein" in r1 or "Holstein" in r2)) or ("Girolando" in (r1, r2)):
            nombre_cruce = "F1 Girolando (1/2 Gyr + 1/2 Holstein)"
        return {
            "grado_codigo": "F1_1_2",
            "grado_nombre": "F1 / Media Sangre (1/2)",
            "fraccion": "F1 1/2",
            "chip_color": "verde",
            "patron_formula": nombre_cruce,
            "es_tipificado": True,
        }

    # 2b. Grados intermedios del cruce absorbente (x/16): 15/16 es el paso
    # previo al Puro por Cruce. Antes caían en los huecos entre bandas y se
    # clasificaban como "Multirracial / Trihíbrido".
    for nominal, codigo, frac_txt, color, tol in _GRADOS_DIECISEISAVOS:
        if abs(max_p - nominal) <= tol:
            r2 = c_norm[1]["raza"] if len(c_norm) > 1 else "Otro"
            num = frac_txt.split("/")[0]
            return {
                "grado_codigo": codigo,
                "grado_nombre": f"{_NOMBRES_DIECISEISAVOS[codigo]} ({frac_txt})",
                "fraccion": frac_txt,
                "chip_color": color,
                "patron_formula": f"{frac_txt} {r1} + {16 - int(num)}/16 {r2}",
                "es_tipificado": True,
            }

    # 3. Tres Cuartos (3/4) ~75% (entre 69.5% y 80.5%)
    if abs(max_p - 75.0) <= 5.5:
        r2 = c_norm[1]["raza"] if len(c_norm) > 1 else "Otro"
        return {
            "grado_codigo": "3_4",
            "grado_nombre": "Tres Cuartos (3/4)",
            "fraccion": "3/4",
            "chip_color": "azul",
            "patron_formula": f"3/4 {r1} + 1/4 {r2}",
            "es_tipificado": True,
        }

    # 4. Cinco Octavos (5/8) ~62.5% (entre 58.0% y 67.5%)
    if abs(max_p - 62.5) <= 5.0:
        r2 = c_norm[1]["raza"] if len(c_norm) > 1 else "Otro"
        return {
            "grado_codigo": "5_8",
            "grado_nombre": "Cinco Octavos (5/8)",
            "fraccion": "5/8",
            "chip_color": "ambar",
            "patron_formula": f"5/8 {r1} + 3/8 {r2}",
            "es_tipificado": True,
        }

    # 5. Siete Octavos (7/8) ~87.5% (entre 83.5% y 92.5%)
    if abs(max_p - 87.5) <= 5.0:
        r2 = c_norm[1]["raza"] if len(c_norm) > 1 else "Otro"
        return {
            "grado_codigo": "7_8",
            "grado_nombre": "Siete Octavos (7/8)",
            "fraccion": "7/8",
            "chip_color": "cyan",
            "patron_formula": f"7/8 {r1} + 1/8 {r2}",
            "es_tipificado": True,
        }

    # 6. Media Sangre multirracial (~50% de la raza dominante)
    if abs(max_p - 50.0) <= 6.0:
        r2 = c_norm[1]["raza"] if len(c_norm) > 1 else "Otro"
        return {
            "grado_codigo": "1_2",
            "grado_nombre": "Media Sangre (1/2)",
            "fraccion": "1/2",
            "chip_color": "lima",
            "patron_formula": f"1/2 {r1} + 1/2 Cruce ({r2})",
            "es_tipificado": True,
        }

    # 7. Multirracial / Compuesto / Trihíbrido
    formula_res = generar_resumen_zootecnico(c_norm)
    return {
        "grado_codigo": "MULTI",
        "grado_nombre": "Multirracial / Trihíbrido",
        "fraccion": "Compuesto",
        "chip_color": "naranja",
        "patron_formula": formula_res,
        "es_tipificado": True,
    }


def calcular_resumen_genetico_hato(
    animales_activos: list[dict],
    composicion_por_animal: dict[int, list[dict]],
) -> dict:
    """Calcula el pool genético consolidado y la agrupación de cruces del hato activo.

    Args:
        animales_activos: lista de dicts [{'id_animal': int, 'tag': str, 'raza': str, ...}]
        composicion_por_animal: mapa de id_animal -> lista de componentes raciales.

    Returns:
        dict con kpis, pool_racial, grados_resumen, patrones_cruces y filas consolidadas.
    """
    total_activos = len(animales_activos)
    tipificados = 0
    puntos_raciales: dict[str, float] = {}
    animales_por_raza: dict[str, set[str]] = {}

    conteo_grados: dict[str, int] = {}
    patrones_map: dict[tuple[str, str, str, str, str], list[str]] = {}

    info_grados = {
        "PURO": {"nombre": "Puros (100% / PC)", "chip": "Puro", "color": "morado", "orden": 1},
        "F1_1_2": {"nombre": "F1 / Media Sangre (1/2)", "chip": "F1 1/2", "color": "verde", "orden": 2},
        "3_4": {"nombre": "Tres Cuartos (3/4)", "chip": "3/4", "color": "azul", "orden": 3},
        "5_8": {"nombre": "Cinco Octavos (5/8)", "chip": "5/8", "color": "ambar", "orden": 4},
        "7_8": {"nombre": "Siete Octavos (7/8)", "chip": "7/8", "color": "cyan", "orden": 5},
        "15_16": {"nombre": "Quince Dieciseisavos (15/16)", "chip": "15/16", "color": "morado", "orden": 5.1},
        "13_16": {"nombre": "Trece Dieciseisavos (13/16)", "chip": "13/16", "color": "azul", "orden": 5.2},
        "11_16": {"nombre": "Once Dieciseisavos (11/16)", "chip": "11/16", "color": "ambar", "orden": 5.3},
        "9_16": {"nombre": "Nueve Dieciseisavos (9/16)", "chip": "9/16", "color": "lima", "orden": 5.4},
        "1_2": {"nombre": "Medias Sangres Multirracial", "chip": "1/2", "color": "lima", "orden": 6},
        "MULTI": {"nombre": "Compuestos / Trihíbridos", "chip": "Compuesto", "color": "naranja", "orden": 7},
        "CEBU": {"nombre": "Cebuino Base", "chip": "Cebuino", "color": "ambar", "orden": 8},
        "TAURINO": {"nombre": "Taurino Base", "chip": "Taurino", "color": "azul", "orden": 9},
        "INDET": {"nombre": "Indeterminados (Base SG)", "chip": "Indeterminado", "color": "gris", "orden": 10},
        "SIN_CLASIFICAR": {"nombre": "Sin Clasificar", "chip": "S/C", "color": "gris", "orden": 11},
    }

    for a in animales_activos:
        aid = a["id_animal"]
        tag = a["tag"]
        raza_str = a.get("raza") or ""
        comp = composicion_por_animal.get(aid, [])

        clasif = clasificar_animal_zootecnico(comp, raza_str)
        gid = clasif["grado_codigo"]
        gnom = clasif["grado_nombre"]
        frac = clasif["fraccion"]
        col = clasif["chip_color"]
        pat = clasif["patron_formula"]

        conteo_grados[gid] = conteo_grados.get(gid, 0) + 1

        pkey = (gid, gnom, frac, col, pat)
        if pkey not in patrones_map:
            patrones_map[pkey] = []
        patrones_map[pkey].append(tag)

        if clasif["es_tipificado"] and comp:
            tipificados += 1
            # Acumular aporte en el pool genético (normalizado al 100% por animal)
            suma_c = sum(float(c.get("porcentaje") or 0.0) for c in comp)
            f_norm = 100.0 / suma_c if suma_c > 0 else 1.0
            for c in comp:
                nom_r = normalizar_nombre_raza(c.get("raza") or "Sin Raza")
                pct_r = float(c.get("porcentaje") or 0.0) * f_norm
                puntos_raciales[nom_r] = puntos_raciales.get(nom_r, 0.0) + pct_r
                if nom_r not in animales_por_raza:
                    animales_por_raza[nom_r] = set()
                animales_por_raza[nom_r].add(tag)

    # 1. Grados resumen
    grados_resumen = []
    for gid, meta in sorted(info_grados.items(), key=lambda x: x[1]["orden"]):
        n = conteo_grados.get(gid, 0)
        if n > 0:
            grados_resumen.append({
                "codigo": gid,
                "nombre": meta["nombre"],
                "chip": meta["chip"],
                "color": meta["color"],
                "cabezas": n,
                "pct_hato": round(n / total_activos * 100.0, 1) if total_activos else 0.0,
                "pct_tipificados": round(n / tipificados * 100.0, 1) if tipificados and gid not in ("INDET", "SIN_CLASIFICAR", "CEBU", "TAURINO") else 0.0,
            })

    # 2. Pool racial global
    total_puntos = sum(puntos_raciales.values())
    pool_racial = []
    colores_razas = {
        "Gyr": "#2e7d32",
        "Holstein Negro": "#1565c0",
        "Ayrshire": "#c62828",
        "Cebú Comercial": "#ef6c00",
        "Pardo Suizo": "#6d4c41",
        "Guzerá": "#00838f",
        "Shorthorn": "#ad1457",
        "Jersey": "#e65100",
        "Girolando": "#2e7d32",
        "Cebú Rojo": "#d84315",
        "Holstein Rojo": "#0277bd",
        "Hereford": "#b71c1c",
        "Normando": "#4527a0",
        "Hartón del Valle": "#558b2f",
    }
    for rz, pts in sorted(puntos_raciales.items(), key=lambda x: x[1], reverse=True):
        pct_pool = round(pts / total_puntos * 100.0, 1) if total_puntos else 0.0
        n_ani = len(animales_por_raza.get(rz, set()))
        pool_racial.append({
            "raza": rz,
            "puntos": round(pts, 1),
            "pct": pct_pool,
            "cabezas_portadoras": n_ani,
            "color": colores_razas.get(rz, "#546e7a"),
        })

    # 3. Patrones de cruce consolidados
    patrones_cruces = []
    for (gid, gnom, frac, col, pat), tag_list in sorted(patrones_map.items(), key=lambda x: len(x[1]), reverse=True):
        cabs = len(tag_list)
        patrones_cruces.append({
            "grado_codigo": gid,
            "grado_nombre": gnom,
            "fraccion": frac,
            "chip_color": col,
            "nombre": pat,
            "cabezas": cabs,
            "pct_hato": round(cabs / total_activos * 100.0, 1) if total_activos else 0.0,
            "pct_tipificados": round(cabs / tipificados * 100.0, 1) if tipificados and gid not in ("INDET", "SIN_CLASIFICAR", "CEBU", "TAURINO") else 0.0,
            "animales": tag_list,
        })

    # 4. Filas compatibles hacia atrás
    filas_compatibles = []
    for pat in patrones_cruces:
        filas_compatibles.append({
            "raza": pat["fraccion"],
            "raza_nombre": pat["nombre"],
            "n": pat["cabezas"],
            "pct": pat["pct_hato"],
            "grado_codigo": pat["grado_codigo"],
            "chip_color": pat["chip_color"],
            "animales": pat["animales"][:8],
        })

    return {
        "total": total_activos,
        "total_activos": total_activos,
        "tipificados": tipificados,
        "pct_tipificados": round(tipificados / total_activos * 100.0, 1) if total_activos else 0.0,
        "indeterminados": conteo_grados.get("INDET", 0),
        "grados_resumen": grados_resumen,
        "pool_racial": pool_racial,
        "patrones_cruces": patrones_cruces,
        "filas": filas_compatibles,
    }


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

    # Progenitor sin composición conocida: su 50% queda como "Desconocida".
    # Antes se reescalaba al 100% y la cría salía copia del otro progenitor
    # (madre Brahman x padre desconocido = "Brahman Puro").
    suma_total = sum(aportes.values())
    if suma_total < 99.99:
        aportes["Desconocida"] = aportes.get("Desconocida", 0.0) + (100.0 - suma_total)

    # Verificar si es un F1 verdadero (exactamente 2 razas al 50% cada una)
    es_f1 = (len(aportes) == 2 and all(abs(p - 50.0) <= 0.5 for p in aportes.values())
             and "Desconocida" not in aportes)

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
    sin_pct: list[str] = []

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
        elif raza_str:
            sin_pct.append(norm_raza)

    # "3/4 Gyr + Holstein": la parte sin fracción recibe el resto hasta 100
    # (antes se descartaba y quedaba solo Gyr 75%).
    if resultado and sin_pct and total_pct < 99.99:
        resto = round((100.0 - total_pct) / len(sin_pct), 2)
        for rz in sin_pct:
            resultado.append({
                "raza": rz,
                "porcentaje": resto,
                "fraccion": porcentaje_a_fraccion(resto),
                "etiqueta": formatear_raza_etiqueta(rz, resto),
            })

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
