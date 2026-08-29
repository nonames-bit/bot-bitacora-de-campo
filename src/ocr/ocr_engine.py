"""Motor OCR y extracción de entidades visuales (aretes/tags y medicamentos).

Proporciona soporte multi-backend (pytesseract como backend principal liviano,
easyocr como secundario, y fallback graceful a sidecars .txt o no-op cuando
las librerías externas no están instaladas).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger("bitacora.ocr")

# Mapeo de normalización de vías de administración
VIA_NORM = {
    "sc": "SC",
    "subcutanea": "SC",
    "subcutánea": "SC",
    "im": "IM",
    "intramuscular": "IM",
    "iv": "IV",
    "intravenosa": "IV",
    "oral": "Oral",
    "intramamaria": "Intramamaria",
    "topica": "Tópica",
    "tópica": "Tópica",
}

# Principios activos y productos veterinarios frecuentes en ganadería
MEDICAMENTOS_PATTERNS: list[tuple[str, str]] = [
    ("Oxitetraciclina", r"\b(?:oxitetraciclina(?:\s+l\.?a\.?)?|terramicina|oxitetra)\b"),
    ("Ivermectina", r"\b(?:ivermectina(?:\s+ad3e)?|ivomec)\b"),
    ("Penicilina", r"\b(?:penicilina(?:\s+g|\s+procainica|\s+benzatinica)?|penstrep)\b"),
    ("Estreptomicina", r"\b(?:estreptomicina|dihidroestreptomicina)\b"),
    ("Fenbendazol", r"\b(?:fenbendazol|panacur)\b"),
    ("Albendazol", r"\b(?:albendazol|valbazen)\b"),
    ("Tilosina", r"\b(?:tylosina|tilosina|tylan)\b"),
    ("Dexametasona", r"\b(?:dexametasona|azium)\b"),
    ("Enrofloxacina", r"\b(?:enrofloxacina|enrofloxacino|baytril)\b"),
    ("Amoxicilina", r"\b(?:amoxicilina(?:\s*\+\s*acido\s+clavulanico)?)\b"),
    ("Complejo B", r"\b(?:complejo\s*b|vitamina\s*b|catosal)\b"),
    ("Doramectina", r"\b(?:doramectina|dectomax)\b"),
    ("Ceftiofur", r"\b(?:ceftiofur|excenel|naxcel)\b"),
    ("Flunixin Meglumina", r"\b(?:flunixin(?:\s+meglumina)?|finadyne)\b"),
    ("Sulfametazina", r"\b(?:sulfametazina|sulfas?|gorban|trimetoprim)\b"),
    ("Vitamina AD3E", r"\b(?:vitamina\s*ad3e|vitaminas?\s*ade|ad3e)\b"),
    ("Closantel", r"\b(?:closantel)\b"),
    ("Fipronil", r"\b(?:fipronil)\b"),
    ("Levamisol", r"\b(?:levamisol|ripercol)\b"),
    ("Dipirona", r"\b(?:dipirona|novalgina)\b"),
    ("Gentamicina", r"\b(?:gentamicina)\b"),
    ("Ciprofloxacina", r"\b(?:ciprofloxacina)\b"),
    ("Oxitocina", r"\b(?:oxitocina)\b"),
    ("Calcio", r"\b(?:borogluconato\s+de\s+calcio|calfon|calcio\s+coloidal)\b"),
    ("Hierro Dextrano", r"\b(?:hierro\s+dextrano|ferrodex)\b"),
    ("Vacuna Aftosa", r"\b(?:vacuna\s+aftosa|aftosa)\b"),
    ("Vacuna Brucelosis", r"\b(?:vacuna\s+brucelosis|cepa\s*19|rb51)\b"),
    ("Vacuna Rabia", r"\b(?:vacuna\s+rabia|rabia\s+paresiante)\b"),
    ("Vacuna Triple", r"\b(?:vacuna\s+triple|triple\s+bovina|carbunco)\b"),
]

# Palabras que no deben ser interpretadas como tags de animales
STOP_WORDS_TAG = {
    "lote", "potrero", "fecha", "peso", "dosis", "exp", "lot", "batch",
    "vence", "ml", "kg", "im", "iv", "sc", "oral", "mg", "cc", "cm3",
    "vaca", "animal", "toro", "ternero", "ternera", "novilla", "novillo",
    "foto", "campo", "arete", "tag", "chapa", "caravana", "via", "retiro",
    "leche", "carne", "dias", "hora", "min", "sec", "dia", "ano", "mes",
    # Artículos y preposiciones frecuentes en español que no son prefijos de arete
    "la", "el", "le", "les", "lo", "los", "las", "a", "al", "de", "del",
    "en", "con", "por", "para", "y", "o", "que", "un", "una", "unos", "unas",
    "se", "su", "sus", "es", "son", "fue", "era", "esta", "este", "esta",
}


def detect_medicamento(text: str) -> dict:
    """Extrae información farmacológica y de frascos a partir de texto OCR o notas.

    Retorna un diccionario con los campos detectados:
    ``producto``, ``principio_activo``, ``dosis``, ``via``, ``lote``,
    ``vencimiento``, ``dias_retiro``, ``dias_retiro_leche``, ``dias_retiro_carne``.
    """
    if not text:
        return {}
    t_lower = text.lower()

    # 1. Producto y principio activo
    prod = None
    principio = None
    for nom, pat in MEDICAMENTOS_PATTERNS:
        if re.search(pat, t_lower, re.IGNORECASE):
            prod = nom
            principio = nom
            break

    # Respaldo: verbos de aplicación seguidos de nombre o "frasco: ..."
    if not prod:
        m_app = re.search(
            r"\b(?:aplique|puse|le puse|inyecte|frasco\s*:?)\s+([a-z0-9\-]{3,25})\b",
            t_lower,
        )
        if m_app:
            val = m_app.group(1).strip()
            if val not in STOP_WORDS_TAG:
                prod = val.capitalize()
                principio = prod

    if not prod:
        return {}

    res: dict = {
        "producto": prod,
        "principio_activo": principio,
    }

    # 2. Dosis (ej. 20ml, 1ml/10kg, 10 cc, 500 mg) — priorizar etiqueta "Dosis:"
    m_dos_label = re.search(
        r"Dosis\s*:\s*(\d+(?:[.,]\d+)?\s*(?:ml/10kg|ml/50kg|ml/100kg|ml/kg|mg/kg|ml|cc|cm3|mg|g|ui|u\.i\.|mcg))\b",
        text,
        re.IGNORECASE,
    )
    if m_dos_label:
        res["dosis"] = m_dos_label.group(1).replace(" ", "")
    else:
        m_dos = re.search(
            r"\b(\d+(?:[.,]\d+)?\s*(?:ml/10kg|ml/50kg|ml/100kg|ml/kg|mg/kg|ml|cc|cm3|mg|g|ui|u\.i\.|mcg))\b",
            text,
            re.IGNORECASE,
        )
        if m_dos:
            res["dosis"] = m_dos.group(1).replace(" ", "")

    # 3. Vía de administración (SC, IM, IV, Oral...)
    m_via = re.search(
        r"\b(?:v[ií]a\s+)?(sc|im|iv|oral|intramuscular|subcut[aá]nea|intravenosa|intramamaria|t[oó]pica|subcutanea|topica)\b",
        text,
        re.IGNORECASE,
    )
    if m_via:
        v_raw = m_via.group(1).lower()
        res["via"] = VIA_NORM.get(v_raw, v_raw.upper())

    # 4. Lote de fabricación
    m_lot = re.search(
        r"\b(?:lote|lot|batch|no\.?\s*lote|nro\.?\s*lote|lote\s*no\.?)\s*[:#\-]?\s*([A-Za-z0-9\-]+)\b",
        text,
        re.IGNORECASE,
    )
    if m_lot:
        res["lote"] = m_lot.group(1).strip()

    # 5. Fecha de vencimiento / Expiración
    m_venc = re.search(
        r"\b(?:vence|vencimiento|exp|validez|fecha\s+venc|caducidad|caduca)\s*[:#\-]?\s*([0-9]{1,4}[-/.][0-9]{1,4}(?:[-/.][0-9]{1,4})?|[A-Za-z]{3,}\s*\d{2,4})\b",
        text,
        re.IGNORECASE,
    )
    if m_venc:
        res["vencimiento"] = m_venc.group(1).strip()

    # 6. Días de retiro (soporta "14 dias de retiro en carne" y "Retiro: 14 dias carne")
    m_ret = re.search(
        r"\b(\d+)\s*d[ií]as\s*(?:de\s+)?retiro(?:\s+(?:en\s+)?(leche|carne))?\b",
        text,
        re.IGNORECASE,
    )
    if not m_ret:
        m_ret = re.search(
            r"\bRetiro\s*[:\-]?\s*(\d+)\s*d[ií]as(?:\s+(?:en\s+)?(leche|carne))?\b",
            text,
            re.IGNORECASE,
        )
        if m_ret:
            # Grupos desplazados: grupo1=dias, grupo2=tipo
            dias = int(m_ret.group(1))
            tipo_ret = m_ret.group(2).lower() if m_ret.group(2) else None
            res["dias_retiro"] = dias
            if tipo_ret == "leche":
                res["dias_retiro_leche"] = dias
                res["dias_retiro_carne"] = None
            elif tipo_ret == "carne":
                res["dias_retiro_leche"] = None
                res["dias_retiro_carne"] = dias
            else:
                res["dias_retiro_carne"] = dias
            return res
    if m_ret:
        dias = int(m_ret.group(1))
        tipo_ret = m_ret.group(2).lower() if m_ret.group(2) else None
        res["dias_retiro"] = dias
        if tipo_ret == "leche":
            res["dias_retiro_leche"] = dias
            res["dias_retiro_carne"] = None
        elif tipo_ret == "carne":
            res["dias_retiro_leche"] = None
            res["dias_retiro_carne"] = dias
        else:
            res["dias_retiro_carne"] = dias

    return res


def detect_tags(text_or_image: str) -> list[str]:
    """Extrae identificadores de aretes/tags de un texto o ruta de imagen.

    Reconoce identificadores alfanuméricos (N069, N-069, JA26, O-123),
    numéricos simples (47, 105) y nombres propios identificadores (patricia).
    """
    if not text_or_image:
        return []

    # Si es ruta a archivo existente, extraer texto con OCREngine
    texto = text_or_image
    if os.path.isfile(text_or_image):
        engine = OCREngine()
        texto = engine.extract_text(text_or_image)
        if not texto:
            return []

    tags: list[str] = []

    # 1. Tags explícitos con etiqueta (ej. "tag: 47", "arete: N069", "caravana #JA26", "vaca: patricia")
    pat_explicit = (
        r"\b(?:tag|arete|chapa|caravana|identificador|vaca|animal|nombre)\s*[:#\-]?\s*([a-zA-Z0-9\-]+)\b"
    )
    for m in re.finditer(pat_explicit, texto, re.IGNORECASE):
        val = m.group(1).strip()
        if val.lower() not in STOP_WORDS_TAG and val:
            norm_val = val.upper() if any(c.isdigit() for c in val) else val.lower()
            if norm_val not in tags:
                tags.append(norm_val)

    # 2. Alfanuméricos con letras y dígitos (ej. N069, N-069, N 069, JA26, JA-26, O-123, A301, H12)
    pat_alfanumeric = r"\b([A-Za-z]{1,4})\s*[-_.]?\s*(\d{1,6})\b"
    for m in re.finditer(pat_alfanumeric, texto):
        prefix, digits = m.group(1), m.group(2)
        if prefix.lower() in STOP_WORDS_TAG:
            continue
        full_match = m.group(0).strip()
        if "-" in full_match:
            formatted = f"{prefix.upper()}-{digits}"
        else:
            formatted = f"{prefix.upper()}{digits}"
        if formatted not in tags:
            tags.append(formatted)

    # 3. Números aislados (ej. "47", "105") con descarte de fechas, dosis y lotes
    pat_numeros = r"\b(\d{1,6})\b"
    for m in re.finditer(pat_numeros, texto):
        start, end = m.span()
        num_str = m.group(1)
        # Ignorar años recientes (2020..2035)
        if len(num_str) == 4 and num_str.startswith("20"):
            continue
        # Ignorar si va seguido de unidades
        suffix = texto[end:end + 12].lower().strip()
        if re.match(r"^(?:ml|cc|cm3|mg|g|kg|kilos|dias|días|ui|%|horas|meses)\b", suffix):
            continue
        # Ignorar si va precedido de lote, potrero, dosis, etc.
        prefix_ctx = texto[max(0, start - 15):start].lower().strip()
        if re.search(r"\b(?:lote|potrero|dosis|retiro|año|ano|mes|dia|día)\s*[:#]?$", prefix_ctx):
            continue
        if num_str not in tags:
            tags.append(num_str)

    # 4. Complemento con el extractor NLU del proyecto si no hay tags
    from ..parsers.nlp_engine import extraer_tags as nlu_extraer_tags
    for t in nlu_extraer_tags(texto):
        t_norm = t.upper() if any(c.isdigit() for c in t) else t
        if t_norm not in tags and t.lower() not in STOP_WORDS_TAG:
            tags.append(t_norm)

    return tags


class OCREngine:
    """Motor de OCR para reconocimiento visual en fotos de campo ganaderas."""

    def __init__(self):
        pass

    def is_available(self) -> bool:
        """Indica si hay un motor de OCR instalado y disponible."""
        return self.get_backend() is not None

    def get_backend(self) -> Optional[str]:
        """Detecta y retorna el nombre del backend OCR disponible o None."""
        # 1. Pytesseract + Pillow
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
            return "pytesseract"
        except ImportError:
            pass

        # 2. EasyOCR
        try:
            import easyocr  # noqa: F401
            return "easyocr"
        except ImportError:
            pass

        return None

    def extract_text(self, image_path: str) -> str:
        """Extrae el texto presente en una imagen usando el backend disponible.

        Si se le pasa un archivo .txt directamente o existe un sidecar acompañante,
        lo utiliza como respaldo para pruebas o entornos sin dependencias pesadas.
        """
        if not image_path:
            return ""

        # Si el archivo es directamente un archivo de texto
        if image_path.lower().endswith(".txt"):
            if os.path.isfile(image_path):
                try:
                    with open(image_path, "r", encoding="utf-8") as f:
                        return f.read().strip()
                except Exception as e:
                    logger.warning("Error al leer archivo de texto %s: %s", image_path, e)
            return ""

        # 1. Backend Pytesseract
        try:
            import pytesseract
            from PIL import Image
            if os.path.isfile(image_path):
                img = Image.open(image_path)
                try:
                    text = pytesseract.image_to_string(img, lang="spa")
                except Exception:
                    text = pytesseract.image_to_string(img)
                if text and text.strip():
                    return text.strip()
        except ImportError:
            pass
        except Exception as e:
            logger.warning("Fallo en extracción OCR con pytesseract: %s", e)

        # 2. Backend EasyOCR
        try:
            import easyocr
            if os.path.isfile(image_path):
                reader = easyocr.Reader(["es", "en"], gpu=False)
                results = reader.readtext(image_path, detail=0)
                text = " ".join(results).strip()
                if text:
                    return text
        except ImportError:
            pass
        except Exception as e:
            logger.warning("Fallo en extracción OCR con easyocr: %s", e)

        # 3. Fallback a sidecar (.txt acompañante)
        candidates = [f"{image_path}.txt", f"{os.path.splitext(image_path)[0]}.txt"]
        for sc in candidates:
            if os.path.isfile(sc):
                try:
                    with open(sc, "r", encoding="utf-8") as f:
                        return f.read().strip()
                except Exception:
                    pass

        return ""

    def detect_tags(self, text_or_image: str) -> list[str]:
        """Detecta tags de animales en texto o imagen."""
        return detect_tags(text_or_image)

    def detect_medicamento(self, text: str) -> dict:
        """Detecta medicamentos y principios activos en texto."""
        return detect_medicamento(text)
