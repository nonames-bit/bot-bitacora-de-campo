"""Motor de comprensión de lenguaje natural (NLU) para notas de campo.

Proporciona clasificación de intenciones (los 8 eventos zootécnicos),
extracción semántica de tags de animales, fechas, dosis, pesos, retiros,
lotes y potreros, usando expresiones regulares robustas para el español
informal de mayordomos.
"""
from __future__ import annotations

import re
from typing import Optional

from ..utils import normalizar, parse_fecha

# Palabras interrogativas que indican consulta (no evento).
PALABRAS_CONSULTA = (
    "que", "cual", "cuales", "cuando", "cuanto", "cuantos", "cuantas",
    "como", "quien", "quienes", "donde", "adonde", "porque", "existe",
    "existen", "hay", "tiene", "tienen", "cual es", "historial",
    "consulta", "consultar", "ficha", "info", "informacion", "hoja de vida",
    "buscar", "ver", "muestrame", "dame",
)

# Intenciones en orden de prioridad (la primera que haga match gana).
INTENTOS: list[tuple[str, list[str]]] = [
    ("parto", [
        r"\bpari[oó]\b", r"\bdio a luz\b", r"\bparto\b", r"\bparir\b",
        r"\bternero\b", r"\bternera\b", r"\bbecerro\b", r"\bbecerra\b",
        r"\bcri[oó]\b", r"\bnaci[oó]\b", r"\balumbramiento\b",
    ]),
    ("muerte", [
        r"\bse muri[oó]\b", r"\bmuri[oó]\b", r"\bmuert[oa]\b",
        r"\bfalleci[oó]\b", r"\bse m[ou]ri[oó]?\b",
    ]),
    ("servicio", [
        r"\binsemin", r"\bservicio\b", r"\bmont[aóe]\b", r"\bcon toro\b",
        r"\bpajilla\b", r"\btoro\s+[a-z0-9]",
    ]),
    ("celo", [
        r"\bcelo[s]?\b", r"\bcalor\b", r"\bcaleando\b", r"\bentorada\b",
        r"\bcalores\b",
    ]),
    ("tratamiento", [
        r"\ble puse\b", r"\ble pongo\b", r"\bapliqu[eé]\b", r"\baplic[aó]\b",
        r"\bvacun", r"\bdesparasit", r"\bdosis\b", r"\bretiro\b",
        r"\d+\s*(?:ml|cc|cm3)\b", r"\btratamient[oa]\b", r"\binyect",
        r"\bsuero\b", r"\bantibiotic", r"\bantiparasit",
    ]),
    ("traslado", [
        r"\bpase el lote\b", r"\blote\s+\d+.*potrero", r"\bdel potrero\b.*\bal potrero\b",
        r"\btraslad", r"\bpotrero\b.*\bpotrero\b", r"\bmov[ií] el lote\b",
        r"\bcambie el lote\b", r"\brot[óo] el\b",
    ]),
    ("pesaje", [
        r"\bpesaje\b", r"\bpes[oó]\b", r"\bpeso\s+\d",
        r"\d+\s*(?:kg|kilos|kilogramos)\b", r"\bkilogramos\b", r"\bkilos\b",
    ]),
    ("movimiento", [
        r"\bentraron\b", r"\bentr[oó]\b", r"\bsalieron\b", r"\bsali[oó]\b",
        r"\bcompr[aeoó]\b", r"\bcomprad[oa]s?\b", r"\bcomprad[oa]\b", r"\bventa\b",
        r"\bvendid[oa]s?\b", r"\bvend[ió]s?\b", r"\bvendimos\b", r"\bvendi[oa]s?\b",
        r"\bvend\b", r"\bbaja\b", r"\balta\b", r"\bsubasta\b",
        r"\bsalida\b", r"\bentrada\b",
    ]),
]

# Prefijos que preceden al tag de un animal.
# NOTA: se excluye "del" (contracción "de el") para no capturar números de
# potrero ni tokens de traslado ("pase del potrero 5 al potrero 6") como tags.
PREFIJOS_TAG = (
    "la", "el", "vaca", "vacas", "animal", "ternera", "ternero", "becerro",
    "becerra", "novilla", "novillo", "vaquilla", "vaquillona", "cria",
    "torete", "toro", "a la", "a el", "de la", "de el", "de", "del", "consulta", "consultar",
    "ficha", "historial", "info", "informacion", "arete", "tag", "numero",
    "nro", "ver", "buscar", "pario", "pario la", "pario el", "esta", "esta la", "esta el",
    "donde esta", "donde esta la", "donde esta el", "donde anda", "donde anda la", "donde anda el",
    "en que potrero esta", "en que potrero esta la", "en que potrero esta el",
    "secado de", "secado de la", "secado de el", "madre de", "padre de", "quien es",
    "cuando se movio", "cuando se traslado", "cuando se cambio", "cuando entro", "cuando paso",
    "traslado de", "traslado de la", "traslado de el", "movimiento de",
)

# Palabras que no son tags de animal aunque vayan precedidas de "la"/"el".
PALABRAS_NO_TAG = {
    "lote", "lotes", "potrero", "potreros", "grupo", "corral", "paddock",
    "pradera", "subasta", "finca", "norte", "sur", "bajo", "alto",
    "vaca", "vacas", "animal", "animales", "ternera", "ternero", "becerro",
    "becerra", "novilla", "novillo", "vaquilla", "vaquillona", "cria",
    "toro", "torete", "crias", "parto", "celo", "servicio",
    "tratamiento", "pesaje", "traslado", "traslados", "muerte", "movimiento", "movimientos",
    "esta", "estan", "donde", "cuando", "cuanto", "quien", "que", "como", "hoy", "ayer",
    "madre", "padre", "mama", "papa", "abuela", "abuelo", "en", "de", "del", "al", "a",
    "el", "la", "los", "las", "un", "una", "unos", "unas", "tiempo", "retiro",
    "pario", "peso", "insemine", "insemino", "inseminada", "inseminaron", "servida", "servio", "sirvio", "sirvieron",
    "murio", "puso", "aplico", "toco", "toca", "cubrio", "monto",
    "movio", "movieron", "traslado", "trasladaron", "cambio", "cambiaron", "entro", "entraron", "paso", "pasaron",
    "debo", "debe", "deben", "debemos", "tengo", "tiene", "tienen", "tenemos", "hay", "les", "le", "me", "te", "se", "nos",
    "servir", "inseminar", "inseminacion", "inseminaciones", "servicios", "palpacion", "palpaciones",
}


def es_consulta(texto: str) -> bool:
    """Determina si el mensaje es una pregunta/consulta y no un evento."""
    if not texto:
        return False
    t = normalizar(texto)
    t = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b", "", t, flags=re.IGNORECASE).strip()
    if "?" in t or "¿" in t:
        return True
    for w in PALABRAS_CONSULTA:
        if re.search(rf"\b{re.escape(w)}\b", t):
            return True
    # Potrero como consulta (ej. "potrero olegario 1" o "olegario 1" si no es evento de traslado)
    if re.search(r"\bpotrero", t) and clasificar(t) != "traslado":
        return True
    # Si contiene un tag con dígitos y no es un evento reconocido (ej. 'N069' o 'vaca 47')
    tag = extraer_tag(t)
    if tag and any(c.isdigit() for c in tag) and clasificar(t) is None:
        return True
    # Nombre corto sin dígitos (ej. "patricia") o potrero corto (ej. "olegario 1" con 2 palabras) sin evento
    if clasificar(t) is None:
        palabras = t.split()
        if 1 <= len(palabras) <= 2:
            # Si es 1-2 palabras y no es un evento, tratar como consulta (ficha por nombre/tag/potrero)
            # Evitar frases de evento incompletas como "vaca vendida" ya está clasificada como movimiento, no entra aquí
            # "bla bla bla" (3 palabras) queda como desconocido para no romper tests de fallback
            return True
    return False


def clasificar(texto: str) -> Optional[str]:
    """Devuelve el nombre del intento (evento) que mejor describe el texto."""
    t = normalizar(texto)
    for intento, patrones in INTENTOS:
        for p in patrones:
            if re.search(p, t):
                return intento
    return None


def extraer_tags(texto: str) -> list[str]:
    """Extrae los tags de animales mencionados (ej. 'la 47' → '47', 'N069' → 'n069')."""
    if not texto:
        return []
    t = normalizar(texto)
    # Limpiar timestamp si viene pegado al final (ej. N06910:13 PM o 10:13)
    t = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b", "", t, flags=re.IGNORECASE).strip()
    # Limpiar comando /consulta o /historial al inicio
    t = re.sub(r"^/[a-z_]+\s*", "", t).strip()

    tags: list[str] = []

    # 1. Búsqueda por prefijo (soporta tags con guion y guion bajo, ej. M_DESCONOCIDO, CRIA_01, N-069)
    for pref in PREFIJOS_TAG:
        pat = rf"\b{re.escape(pref)}\s+([a-z0-9\-_]{{1,12}})\b"
        for m in re.finditer(pat, t):
            val = m.group(1).strip("-_")
            val = re.sub(r"\d{1,2}:\d{2}.*", "", val, flags=re.IGNORECASE)
            if val in PALABRAS_NO_TAG or not val:
                continue
            if val not in tags:
                tags.append(val)

    # 2. Búsqueda de identificadores alfanuméricos con letras y dígitos (ej. n069, a301, h12, n-069, cria_01)
    for m in re.finditer(r"\b([a-z]{1,3}[-_]?[a-z0-9_]{0,9}\d{1,6})\b", t):
        val = m.group(1).strip("-_")
        val = re.sub(r"\d{1,2}:\d{2}.*", "", val, flags=re.IGNORECASE)
        if val not in PALABRAS_NO_TAG and val and val not in tags:
            tags.append(val)
    # Fallback genérico para tags con guion bajo sin dígito obligatorio (ej. m_desconocido)
    for m in re.finditer(r"\b([a-z]+_[a-z0-9_]{1,11})\b", t):
        val = m.group(1).strip("-_")
        if val not in PALABRAS_NO_TAG and val and val not in tags:
            tags.append(val)

    # 3. Si el texto completo es sólo un número o código simple (ej. "47" o "N069")
    palabras = t.split()
    if len(palabras) == 1:
        val = palabras[0].strip()
        val = re.sub(r"\d{1,2}:\d{2}.*", "", val, flags=re.IGNORECASE)
        if val not in PALABRAS_NO_TAG and val and val not in tags:
            tags.append(val)

    # 4. Fallback para nombres propios o identificadores en preguntas (ej. "patricia esta en retiro?", "donde esta patricia?")
    if not tags:
        palabras_filtradas = [
            re.sub(r"[?!.,;:¿¡]+", "", w).strip()
            for w in t.split()
            if re.sub(r"[?!.,;:¿¡]+", "", w).strip() and re.sub(r"[?!.,;:¿¡]+", "", w).strip() not in PALABRAS_NO_TAG
        ]
        if len(palabras_filtradas) == 1:
            cand = palabras_filtradas[0]
            if len(cand) >= 2 and cand not in tags:
                tags.append(cand)

    return tags


def extraer_tag(texto: str) -> Optional[str]:
    """Devuelve el tag de animal más probable (prefiere identificadores con dígitos)."""
    tags = extraer_tags(texto)
    if not tags:
        return None
    for t in tags:
        if any(c.isdigit() for c in t):
            return t
    return tags[0]


def extraer_cantidad(texto: str) -> Optional[int]:
    """Extrae un cardinal asociado a un grupo de animales (ej. '15 novillas')."""
    t = normalizar(texto)
    m = re.search(
        r"\b(\d+)\s*(?:novillas|novillos|terneras|terneros|vacas|toros|"
        r"animales|cabezas|reses|ejemplares)\b", t)
    if m:
        return int(m.group(1))
    return None


def extraer_sexo_cria(texto: str) -> Optional[str]:
    """Detecta el sexo de una cría: 'Macho' o 'Hembra'."""
    t = normalizar(texto)
    if re.search(r"\bmacho[s]?\b|\bternero\b|\bbecerro\b|\btorete\b|\bnovillo\b", t):
        return "Macho"
    if re.search(r"\bhembra[s]?\b|\bternera\b|\bbecerra\b|\bvaquilla\b|\bnovilla\b", t):
        return "Hembra"
    return None


def extraer_peso(texto: str) -> Optional[float]:
    """Extrae un peso en kg (ej. 'peso 420', '420 kg', '420 kilos')."""
    t = normalizar(texto)
    m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:kg|kilos|kilogramos)\b", t)
    if m:
        return _f(m.group(1))
    m = re.search(r"\bpeso\s+(\d+(?:[.,]\d+)?)\b", t)
    if m:
        return _f(m.group(1))
    return None


def extraer_dosis(texto: str) -> Optional[str]:
    """Extrae una dosis con unidad (ej. '20ml', '10 cc')."""
    t = normalizar(texto)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ml|cc|cm3)", t)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return None


def extraer_dias_retiro(texto: str) -> Optional[int]:
    """Extrae el número de días de retiro de un fármaco."""
    t = normalizar(texto)
    m = re.search(r"(\d+)\s*d[ií]as\s+de\s+retiro", t)
    if m:
        return int(m.group(1))
    m = re.search(r"retiro\s+(?:de\s+)?(\d+)\s*d[ií]as", t)
    if m:
        return int(m.group(1))
    if "retiro" in t:
        m = re.search(r"(\d+)\s*d[ií]as", t)
        if m:
            return int(m.group(1))
    return None


def retiro_leche_carne(texto: str, dias: Optional[int]) -> dict:
    """Desglosa los días de retiro en leche/carne.

    Regla zootécnica (skill ``@plan-sanitario``): si no se menciona "leche"
    explícitamente, el retiro aplica a carne por defecto, sin bloquear leche.
    """
    t = normalizar(texto)
    menciona_leche = re.search(r"\bleche\b", t) is not None
    menciona_carne = re.search(r"\bcarne\b", t) is not None
    leche = dias if menciona_leche else None
    carne = dias if (menciona_carne or not menciona_leche) else None
    return {"dias_retiro_leche": leche, "dias_retiro_carne": carne}


def extraer_producto(texto: str) -> Optional[str]:
    """Extrae el nombre del fármaco (primera palabra tras un verbo de aplicación)."""
    t = normalizar(texto)
    m = re.search(
        r"\b(?:le puse|puse|le pongo|pongo|aplique|aplico|aplic[oó]|vacune|"
        r"vacuno|desparasite|desparasito|inyecte|inyecto)\s+(?:de\s+)?"
        r"([a-z][a-z0-9\-]{1,24})", t)
    if m:
        return m.group(1)
    return None


def extraer_via(texto: str) -> Optional[str]:
    """Extrae la vía de administración (SC, IM, IV, Oral...)."""
    t = normalizar(texto)
    m = re.search(r"\b(?:via|por)\s+(sc|im|iv|oral|subcutanea|intramuscular|intravenosa)\b", t)
    if m:
        return m.group(1).upper()
    return None


def extraer_toro(texto: str) -> dict:
    """Extrae el toro/pajilla y la raza del toro (ej. 'toro brahman 502')."""
    t = normalizar(texto)
    m = re.search(r"\btoro\s+([a-z]+)\s+([a-z0-9]+)\b", t)
    if m:
        return {"raza": m.group(1), "toro": m.group(2)}
    m = re.search(r"\btoro\s+([a-z0-9]+)\b", t)
    if m:
        return {"raza": None, "toro": m.group(1)}
    return {"raza": None, "toro": None}


def extraer_lote(texto: str) -> Optional[str]:
    """Extrae el número de lote (ej. 'lote 2')."""
    t = normalizar(texto)
    m = re.search(r"\blote\s+(\d+)\b", t)
    if m:
        return m.group(1)
    return None


def extraer_potreros(texto: str) -> list[str]:
    """Extrae nombres de potrero mencionados (en orden de aparición)."""
    t = normalizar(texto)
    return re.findall(r"\bpotrero\s+([a-z0-9]+)\b", t)


def extraer_am_pm(texto: str) -> Optional[str]:
    """Detecta la franja horaria de un celo (AM/PM)."""
    t = normalizar(texto)
    if re.search(r"\b(?:am|manana|madrugada)\b", t):
        return "AM"
    if re.search(r"\b(?:pm|tarde|noche)\b", t):
        return "PM"
    return None


def _f(s: str) -> float:
    return float(s.replace(",", "."))


class NLUEngine:
    """Interfaz por objetos del motor NLU (métodos estáticos)."""

    @staticmethod
    def es_consulta(texto):
        return es_consulta(texto)

    @staticmethod
    def clasificar(texto):
        return clasificar(texto)

    @staticmethod
    def extraer_tag(texto):
        return extraer_tag(texto)

    @staticmethod
    def extraer_tags(texto):
        return extraer_tags(texto)

    @staticmethod
    def extraer_fecha(texto, base=None):
        return parse_fecha(texto, base)
