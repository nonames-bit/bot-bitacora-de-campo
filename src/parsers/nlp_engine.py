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
        # Pérdida gestacional (mismo evento reproductivo que el parto, sin
        # cría -- ver TIPOS_EVENTO_SIN_CRIA) y parto múltiple.
        r"\babort", r"\breabsor", r"\bmomific", r"\bmacer",
        r"\bmuerte\s+fetal\b", r"\bgemel", r"\bmelliz",
    ]),
    ("muerte", [
        r"\bse muri[oó]\b", r"\bmuri[oó]\b", r"\bmuert[oa]\b",
        r"\bfalleci[oó]\b", r"\bse m[ou]ri[oó]?\b",
    ]),
    ("diagnostico_gestacion", [
        r"\bpalp[eé]\b", r"\bpalpaci[oó]n\b", r"\bpalpar\b",
        r"\bdiagn[oó]stic[oa]\s+(?:de\s+)?gestaci[oó]n\b",
        r"\bconfirmad[oa]\s+pre[nñ]ad[oa]\b",
        r"\bconfirmad[oa]\s+vac[ií]a\b",
        r"\bpre[nñ]ad[oa]\b",
        r"\bvac[ií]a\b",
        r"\bgestante\b",
        r"\bchequeo\s+reproductivo\b",
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
    ("secado", [
        # Secado real de una vaca lechera (deja de ordeñarse), evento
        # independiente del destete de su cría -- ver Database.registrar_secado.
        # Patrones específicos para no confundir con "potrero seco"/"época
        # seca" (clima/pastura), que no mencionan a la vaca.
        r"\bse sec[oó]\b", r"\bsec[oó]\s+(?:a\s+)?la\b", r"\bsecad[oa]\s+de\s+la\b",
        r"\bdej[oó]\s+de\s+(?:dar|producir)\s+leche\b", r"\bfin\s+de\s+(?:la\s+)?lactancia\b",
        r"\bya\s+no\s+da\s+leche\b",
    ]),
    ("leche", [
        r"\blitros?\s+de\s+leche\b", r"\bleche\b.*\blitros?\b", r"\blitros?\b.*\bleche\b",
        r"\bordeñ[eoó]", r"\bproducci[oó]n\s+de\s+leche\b", r"\bcontrol\s+lechero\b",
    ]),
    ("aforo", [
        r"\baforo\b", r"\bafor[eé]\b", r"\bkg/m2\b", r"\bkg\s+mv/m2\b",
    ]),
    ("pluviometria", [
        r"\bllovi[oó]\b", r"\blluvia[s]?\b", r"\bpluvi[oó]metr[oa]\b",
        r"\bprecipitaci[oó]n\b", r"\baguacero\b", r"\b\d+\s*mm\b",
    ]),
    ("pesaje", [
        r"\bpesaje\b", r"\bpes[oó]\b", r"\bpeso\s+\d",
        r"\d+\s*(?:kg|kilos|kilogramos)\b", r"\bkilogramos\b", r"\bkilos\b",
    ]),
    ("condicion_corporal", [
        r"\bcondici[oó]n\s+corporal\b", r"\bpuntaje\s+corporal\b",
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
    "palpe", "palpe la", "palpe el", "palpe a la", "palpe a el", "palpacion de", "palpacion de la", "palpacion de el",
    "palpacion", "palpaciones", "palpar", "palpar la", "palpar el",
    "diagnostico de gestacion", "diagnostico de gestacion de", "diagnostico de gestacion de la", "diagnostico de gestacion de el",
    "diagnostico de gestacion la", "diagnostico de gestacion el", "diagnostico gestacional", "diagnostico gestacional de",
    "diagnostico gestacional de la", "diagnostico gestacional la", "diagnostico de", "diagnostico de la", "diagnostico de el",
    "diagnostico", "diagnosticos", "gestacion", "gestacion de", "gestacion de la", "gestacion de el", "gestacion la", "gestacion el",
    "ecografia de", "ecografia de la", "ecografia", "chequeo de", "chequeo de la", "chequeo",
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
    "movio", "movieron", "trasladaron", "cambio", "cambiaron", "entro", "entraron", "paso", "pasaron",
    "debo", "debe", "deben", "debemos", "tengo", "tiene", "tienen", "tenemos", "hay", "les", "le", "me", "te", "se", "nos",
    "servir", "inseminar", "inseminacion", "inseminaciones", "servicios", "palpacion", "palpaciones",
    "palpe", "palpar", "diagnostico", "diagnosticos", "gestacion", "gestaciones", "ecografia", "ecografias",
    "chequeo", "chequeos", "prenada", "prenado", "vacia", "vacio", "gestante", "confirmada",
    "confirmado", "pajuela", "pajuelas", "termo", "nitrogeno", "canastilla", "dias", "dia",
    "mes", "meses", "semana", "semanas", "medio", "media",
    # Sexo de la cría: sin esto, "parió la 47, ternero macho" extraía
    # "macho" como segundo tag y registrar_parto() creaba un animal
    # fantasma ACTIVO llamado "macho"/"hembra" que inflaba el inventario.
    "macho", "machos", "hembra", "hembras",
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
        if w == "que":
            continue  # se evalúa aparte abajo (relativo vs. interrogativo)
        if re.search(rf"\b{re.escape(w)}\b", t):
            return True
    # "que" sin tilde es ambiguo tras normalizar: relativo ("parió la 47
    # que estaba gorda") o interrogativo ("¿qué vacas debo inseminar?").
    # Solo cuenta como pregunta si empieza con "que" o si NO hay un evento
    # concreto sobre un animal puntual (intención + arete con dígitos).
    # Sin esto, cualquier nota con subordinada se volvía consulta y el
    # evento nunca se registraba (pérdida silenciosa de datos de campo).
    if re.search(r"\bque\b", t):
        if re.search(r"^que\b", t):
            return True
        if clasificar(t) is None:
            return True
        tag_q = extraer_tag(t)
        if not tag_q or not any(c.isdigit() for c in tag_q):
            return True
    # Plural + periodo sin arete/nombre puntual: casi siempre es una pregunta
    # agregada (ej. "animales muertos este mes", "vacas vendidas esta semana"),
    # no un evento sobre un animal concreto (esos sí traen un arete/nombre, ej.
    # "murió la 47"). Sin esta regla, el mensaje caía en el registro de evento
    # y el bot llegó a "confirmar" un registro que ni siquiera se guardó.
    if re.search(r"\b(?:animales|vacas|toros|terneros|novillas)\b", t) and re.search(
        r"\beste\s+mes\b|\besta\s+semana\b|\bmes\s+pasado\b|\ba[nñ]o\s+pasado\b|\beste\s+a[nñ]o\b|\bultimos?\s+\d+\s+dias\b",
        t,
    ):
        # Los aretes reales de la finca siempre traen al menos un dígito
        # (N065, A057, 47...); si extraer_tag "encontró" algo sin dígitos
        # (ej. "vendidas" en "vacas vendidas esta semana"), es una palabra
        # suelta mal tomada como arete, no un animal puntual real.
        tag_encontrado = extraer_tag(t)
        if not tag_encontrado or not any(c.isdigit() for c in tag_encontrado):
            return True
    # Potrero como consulta (ej. "potrero olegario 1" o "olegario 1" si no es evento de traslado o aforo)
    if re.search(r"\bpotrero", t) and clasificar(t) not in ("traslado", "aforo"):
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

    # 2. Búsqueda de identificadores alfanuméricos con letras y dígitos (ej. n069,
    # a301, h12, n-069, cria_01). El sufijo final "(?:[-_]\d{1,4})?" cubre la
    # convención de numerar crías como "arete_madre-n" (ej. JA26-6, N065-1):
    # sin él, la parte "-6"/"-1" se perdía y el tag quedaba truncado al de la
    # madre, haciendo que "consulta JA26-6" abriera la ficha de la madre.
    for m in re.finditer(r"\b([a-z]{1,3}[-_]?[a-z0-9_]{0,9}\d{1,6}(?:[-_]\d{1,4})?)\b", t):
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


def extraer_litros_leche(texto: str) -> Optional[float]:
    """Extrae los litros de leche producidos (ej. '12 litros', '8.5 lts de
    leche', 'ordeñó 10 litros')."""
    t = normalizar(texto)
    m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:litros?|lts?)\b", t)
    if m:
        return _f(m.group(1))
    m = re.search(r"\blitros?\s+(?:de\s+leche\s+)?(\d+(?:[.,]\d+)?)\b", t)
    if m:
        return _f(m.group(1))
    return None


def extraer_condicion_corporal(texto: str, tag_excluir: Optional[str] = None) -> Optional[float]:
    """Extrae el valor de condición corporal (escala 1-5 o 1-9 según el
    hato), ej. 'condición corporal de la 47 es 3.5', 'puntaje corporal 3'.
    Busca el primer número después de la frase clave, descartando el
    número que resulte ser el propio arete del animal (ej. 'de la 47') si
    se pasa ``tag_excluir``, para no confundir el arete con el valor."""
    t = normalizar(texto)
    m_frase = re.search(r"condici[oó]n\s+corporal|puntaje\s+corporal", t)
    if not m_frase:
        return None
    resto = t[m_frase.end():]
    tag_norm = str(tag_excluir).strip().lower().lstrip("0") if tag_excluir else None
    for m_num in re.finditer(r"\d+(?:[.,]\d+)?", resto):
        valor = m_num.group(0)
        if tag_norm and valor.lstrip("0") == tag_norm:
            continue
        return _f(valor)
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


def _dias_retiro_por_producto(t: str) -> dict:
    """Asigna cada "N días" del texto normalizado a 'leche' o 'carne'.

    Un número pertenece al producto que lo sigue con preposición ("28 días
    en carne", "3 días de retiro en leche") o, si no, al producto mencionado
    justo antes ("leche 3 días", "leche: 4 días", "leche y carne 10 días"
    asigna 10 a ambos). Devuelve {'leche': int|None, 'carne': int|None}.
    """
    res: dict = {"leche": None, "carne": None}
    for m in re.finditer(r"\b(\d+)\s*d[ií]as?\b", t):
        n = int(m.group(1))
        despues = re.match(
            r"\s+(?:(?:de\s+)?retiro\s+(?:en\s+|de\s+|para\s+)?|(?:en|de|para)\s+)(leche|carne)\b",
            t[m.end():],
        )
        if despues:
            res[despues.group(1)] = res[despues.group(1)] if res[despues.group(1)] is not None else n
            continue
        antes = t[max(0, m.start() - 30):m.start()]
        cercanos = list(re.finditer(r"\b(leche|carne)\b", antes))
        if not cercanos:
            continue
        ultimo = cercanos[-1]
        # "leche y carne 10 días": ambos productos comparten el número.
        duenos = [ultimo.group(1)]
        if len(cercanos) >= 2 and re.fullmatch(r"\s+(?:y|e|o)\s+", antes[cercanos[-2].end():ultimo.start()]):
            duenos.append(cercanos[-2].group(1))
        # Solo conectores cortos entre el producto y el número.
        if len(antes) - ultimo.end() > 20:
            continue
        for d in duenos:
            if res[d] is None:
                res[d] = n
    return res


def retiro_leche_carne(texto: str, dias: Optional[int]) -> dict:
    """Desglosa los días de retiro en leche/carne.

    Si la nota da días distintos a cada producto ("leche 3 días carne 28
    días") se respeta cada valor; antes se aplicaba el primer número a ambos
    y la carne se liberaba semanas antes. Regla zootécnica (skill
    ``@plan-sanitario``): si no se menciona "leche" explícitamente, el
    retiro aplica a carne por defecto, sin bloquear leche.
    """
    t = normalizar(texto)
    menciona_leche = re.search(r"\bleche\b", t) is not None
    menciona_carne = re.search(r"\bcarne\b", t) is not None
    por_producto = _dias_retiro_por_producto(t)
    leche_exp = por_producto["leche"]
    carne_exp = por_producto["carne"]
    leche = leche_exp if leche_exp is not None else (dias if menciona_leche else None)
    carne = carne_exp if carne_exp is not None else (dias if (menciona_carne or not menciona_leche) else None)
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
    if re.search(r"\b(?:pm|tarde|noche|anoche)\b", t):
        return "PM"
    return None


def extraer_resultado_diagnostico(texto: str) -> Optional[str]:
    """Extrae el resultado del diagnóstico: 'PREÑADA', 'VACIA' o None.

    La negación admite hasta dos palabras intermedias ("no quedó preñada",
    "no está preñada"). Sin palabra de resultado devuelve None: registrar
    PREÑADA por defecto daba gestaciones falsas y ocultaba vacías.
    """
    t = normalizar(texto)
    if re.search(r"\b(?:vac[ií]a|abierta|negativa|no\s+(?:\w+\s+){0,2}pre[nñ]ad[oa])\b", t):
        return "VACIA"
    if re.search(r"\b(?:pre[nñ]ad[oa]|gestante|positiva|confirmad[oa]|pre[nñ]ez)\b", t):
        return "PREÑADA"
    return None


_NUMS_TEXTO = {
    "un": 1.0,
    "uno": 1.0,
    "una": 1.0,
    "dos": 2.0,
    "tres": 3.0,
    "cuatro": 4.0,
    "cinco": 5.0,
    "seis": 6.0,
    "siete": 7.0,
    "ocho": 8.0,
    "nueve": 9.0,
    "diez": 10.0,
}

_PAT_NUM = r"(?:\d+(?:[.,]\d+)?|un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)"


def _parse_num_val(s: str) -> Optional[float]:
    s = s.strip().lower()
    if s in _NUMS_TEXTO:
        return _NUMS_TEXTO[s]
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def extraer_dias_gestacion(texto: str) -> Optional[int]:
    """Extrae los días de gestación estimados a partir de días, semanas o meses.

    Conversiones zootécnicas:
      - 'X meses' -> X * 30 días
      - 'X semanas' -> X * 7 días
      - 'X meses Y días' / 'X meses y medio' -> X * 30 + Y días (o + 15 días)
      - 'X semanas Y días' / 'X semanas y media' -> X * 7 + Y días (o + 3.5 días)
    """
    if not texto:
        return None
    t = normalizar(texto)

    # 1. Caso especial: "medio mes"
    if re.search(r"\bmedi[oa]\s+mes\b", t):
        return 15

    # 2. Meses + Días: ej. "2 meses y 15 días", "2 meses 15 días", "2 meses con 10 dias"
    m_mes_dia = re.search(
        rf"\b({_PAT_NUM})\s*mes(?:es)?\s*(?:y|con|\+)?\s*({_PAT_NUM})\s*(?:d[ií]as?|d)\b",
        t,
    )
    if m_mes_dia:
        n_meses = _parse_num_val(m_mes_dia.group(1))
        n_dias = _parse_num_val(m_mes_dia.group(2))
        if n_meses is not None and n_dias is not None:
            return int(round(n_meses * 30 + n_dias))

    # 3. Meses + Medio: ej. "2 meses y medio", "un mes y medio", "1 mes y medio", "2 meses y media"
    m_mes_medio = re.search(
        rf"\b({_PAT_NUM})\s*mes(?:es)?\s*(?:y\s+)?medi[oa]\b",
        t,
    )
    if m_mes_medio:
        n_meses = _parse_num_val(m_mes_medio.group(1))
        if n_meses is not None:
            return int(round(n_meses * 30 + 15))

    # 4. Semanas + Días: ej. "3 semanas y 2 días", "3 semanas 2 dias"
    m_sem_dia = re.search(
        rf"\b({_PAT_NUM})\s*(?:semanas?|sem)\s*(?:y|con|\+)?\s*({_PAT_NUM})\s*(?:d[ií]as?|d)\b",
        t,
    )
    if m_sem_dia:
        n_sem = _parse_num_val(m_sem_dia.group(1))
        n_dias = _parse_num_val(m_sem_dia.group(2))
        if n_sem is not None and n_dias is not None:
            return int(round(n_sem * 7 + n_dias))

    # 5. Semanas + Medio: ej. "2 semanas y media"
    m_sem_medio = re.search(
        rf"\b({_PAT_NUM})\s*(?:semanas?|sem)\s*(?:y\s+)?medi[oa]\b",
        t,
    )
    if m_sem_medio:
        n_sem = _parse_num_val(m_sem_medio.group(1))
        if n_sem is not None:
            return int(round(n_sem * 7 + 3.5))

    # 6. Meses solos: ej. "3 meses", "1 mes", "2.5 meses", "tres meses"
    m_mes = re.search(
        rf"\b({_PAT_NUM})\s*mes(?:es)?\b",
        t,
    )
    if m_mes:
        n_meses = _parse_num_val(m_mes.group(1))
        if n_meses is not None:
            return int(round(n_meses * 30))

    # 7. Semanas solas: ej. "8 semanas", "1 semana", "ocho semanas"
    m_sem = re.search(
        rf"\b({_PAT_NUM})\s*(?:semanas?|sem)\b",
        t,
    )
    if m_sem:
        n_sem = _parse_num_val(m_sem.group(1))
        if n_sem is not None:
            return int(round(n_sem * 7))

    # 8. Días solos: ej. "60 días", "60 dias", "60 d", "60d"
    m_dia = re.search(
        rf"\b({_PAT_NUM})\s*(?:d[ií]as?|d)\b",
        t,
    )
    if m_dia:
        n_dias = _parse_num_val(m_dia.group(1))
        if n_dias is not None:
            return int(round(n_dias))

    # 9. Fallback explícito tras "preñada"/"gestante" sin unidad (ej. "preñada de 60", "preñada 60")
    m_raw = re.search(r"\b(?:pre[nñ]ad[oa]|gestante)\s+(?:de\s+)?(\d{1,3})\b", t)
    if m_raw:
        try:
            return int(m_raw.group(1))
        except ValueError:
            pass

    return None


def extraer_responsable(texto: str) -> Optional[str]:
    """Extrae el nombre del veterinario/palpador si se menciona."""
    t = normalizar(texto)
    m = re.search(r"\b(?:por|veterinario|dr|palpador|resp|responsable)\s+([a-z]+)\b", t)
    if m:
        val = m.group(1).capitalize()
        if val.lower() not in PALABRAS_NO_TAG:
            return val
    return None


def extraer_mm_lluvia(texto: str) -> Optional[float]:
    """Extrae la cantidad de lluvia en milímetros (mm)."""
    t = normalizar(texto)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:mm|mil[ií]metros)\b", t)
    if m:
        return _f(m.group(1))
    m2 = re.search(r"\b(?:llovi[oó]|lluvia|pluvi[oó]metro|marc[oó]|cayeron|registr[oó])\s+(\d+(?:[.,]\d+)?)\b", t)
    if m2:
        return _f(m2.group(1))
    return None


PALABRAS_NO_SECTOR = {
    "hoy", "ayer", "mm", "lluvia", "lluvias", "pluviometro", "milimetros",
    "sector", "estacion", "en", "de", "del", "el", "la", "los", "las", "un", "una",
}


def extraer_sector_lluvia(texto: str) -> Optional[str]:
    """Extrae el sector, lote o estación pluviométrica si se menciona."""
    t = normalizar(texto)
    m = re.search(r"\b(?:en\s+el\s+sector|en\s+sector|en\s+la\s+estacion|en\s+estacion|en\s+el\s+potrero|en\s+potrero|sector|estacion|corral|finca|potrero)\s+([a-z0-9\-_]+)\b", t)
    if m:
        val = m.group(1).upper()
        if val.lower() not in PALABRAS_NO_SECTOR:
            return val
    m2 = re.search(r"\b(?:en)\s+([a-z0-9\-_]+)\b", t)
    if m2:
        val = m2.group(1).upper()
        if val.lower() not in PALABRAS_NO_SECTOR:
            return val
    return None



def extraer_aforo_kg_m2(texto: str) -> Optional[float]:
    """Extrae el aforo de pasto en kg/m² o kg MV/m²."""
    t = normalizar(texto)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kg/m2|kg\s*m2|kg\s*metro|kg/metro|kg\s*mv/m2)\b", t)
    if m:
        return _f(m.group(1))
    m2 = re.search(r"\b(?:aforo|afor[eé]|dio|peso|pesaje\s+pasto)\s+(\d+(?:[.,]\d+)?)\b", t)
    if m2:
        return _f(m2.group(1))
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

    @staticmethod
    def extraer_resultado_diagnostico(texto):
        return extraer_resultado_diagnostico(texto)

    @staticmethod
    def extraer_dias_gestacion(texto):
        return extraer_dias_gestacion(texto)

    @staticmethod
    def extraer_mm_lluvia(texto):
        return extraer_mm_lluvia(texto)

    @staticmethod
    def extraer_aforo_kg_m2(texto):
        return extraer_aforo_kg_m2(texto)


