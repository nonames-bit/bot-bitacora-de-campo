"""Parser OCR para facturas de compra de pajuelas de semen bovino y nitrógeno.

Extrae campos clave: NIT, total facturado, código/nombre del reproductor (toro)
y cantidad de pajuelas, generando propuestas interactivas para actualización
del inventario en el termo criogénico.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("bitacora.ocr.factura")

STOP_WORDS_TORO = {
    "semen", "bovino", "pajuela", "pajuelas", "pajilla", "pajillas",
    "dosis", "genetica", "genética", "raza", "precio", "unitario",
    "valor", "total", "cantidad", "cant", "factura", "nit", "iva",
    "subtotal", "compra", "venta", "cliente", "producto", "item",
    "descripcion", "descripción", "detalle",
}


@dataclass
class FacturaPajuelasInfo:
    """Contenedor de datos extraídos de una factura de pajuelas."""
    es_factura: bool = False
    toro: Optional[str] = None
    cantidad: Optional[int] = None
    nit: Optional[str] = None
    total: Optional[float] = None
    total_raw: Optional[str] = None
    proveedor: Optional[str] = None
    texto_extraido: str = ""
    propuesta_mensaje: str = ""


def _parse_monto(val_str: str) -> Optional[float]:
    """Convierte cadenas de moneda (ej. '$900.000', '1,250,000 COP', '450000') a float."""
    if not val_str:
        return None
    s = val_str.strip().replace("$", "").replace("COP", "").replace("COL", "").strip()
    if re.search(r"[,.]00$", s):
        s = s[:-3]
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "." in s:
        partes = s.split(".")
        if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
            s = "".join(partes)
    elif "," in s:
        partes = s.split(",")
        if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
            s = "".join(partes)
        else:
            s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def detect_nit(text: str) -> Optional[str]:
    """Extrae el NIT o RUT de la entidad emisora de la factura."""
    if not text:
        return None
    m = re.search(
        r"\b(?:NIT|N\.I\.T\.|RUT)\s*[:#.]?\s*([0-9]{1,3}(?:[.\s]?[0-9]{3}){2}(?:-[0-9kK])?|[0-9]{8,11}(?:-[0-9kK])?|[0-9.\-]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        nit_raw = m.group(1).strip().rstrip(".,:;")
        digitos = re.sub(r"\D", "", nit_raw)
        if len(digitos) >= 6:
            return nit_raw
    return None


def detect_total(text: str) -> tuple[Optional[float], Optional[str]]:
    """Extrae el valor total a pagar de la factura (float y representación textual)."""
    if not text:
        return None, None
    m = re.search(
        r"\b(?:valor\s+total|total\s+a\s+pagar|total\s+factura|total\s+general|total|neto\s+a\s+pagar|vr\.?\s*total)\s*[:$]?\s*(?:COP|COL|\$)?\s*([0-9.,]+)\b",
        text,
        re.IGNORECASE,
    )
    if m:
        raw_val = m.group(1).strip()
        num_val = _parse_monto(raw_val)
        return num_val, raw_val
    return None, None


def detect_cantidad(text: str) -> Optional[int]:
    """Extrae la cantidad de pajuelas o dosis facturadas."""
    if not text:
        return None
    # 1. 'Cantidad: 20' / 'Cant: 15' / 'Unidades: 10' / 'Qty: 50'
    m1 = re.search(
        r"\b(?:cantidad|cant|cant\.|unidades|uds|qty)\s*[:#.]?\s*(\d{1,5})\b",
        text,
        re.IGNORECASE,
    )
    if m1:
        return int(m1.group(1))

    # 2. '20 pajuelas' / '15 pajillas' / '50 dosis'
    m2 = re.search(
        r"\b(\d{1,5})\s*(?:pajuelas?|pajillas?|dosis|unidades)\b",
        text,
        re.IGNORECASE,
    )
    if m2:
        return int(m2.group(1))

    # 3. 'pajuelas: 20'
    m3 = re.search(
        r"\b(?:pajuelas?|pajillas?)\s*[:#.]?\s*(\d{1,5})\b",
        text,
        re.IGNORECASE,
    )
    if m3:
        return int(m3.group(1))

    # 4. 'compra de 10 pajuelas' / 'ingreso 10 pajuelas'
    m4 = re.search(
        r"\b(?:compra|adquisici[oó]n|ingreso)\s+(?:de\s+)?(\d{1,5})\b",
        text,
        re.IGNORECASE,
    )
    if m4:
        return int(m4.group(1))

    return None


def _limpiar_nombre_toro(cand: str) -> str:
    """Normaliza y limpia el identificador/nombre del reproductor."""
    if not cand:
        return ""
    s = re.sub(
        r"^(?:de\s+toro\s+|del\s+toro\s+|toro\s+|de\s+|del\s+|el\s+|la\s+)",
        "",
        cand.strip(),
        flags=re.IGNORECASE,
    )
    s = s.strip(" \t\r\n:;,-.")
    return s


def detect_toro(text: str) -> Optional[str]:
    """Extrae el código o nombre del toro reproductor de la factura."""
    if not text:
        return None

    # 1. 'toro: GYR-DON-JUAN' / 'código toro: 502' / 'reproductor: Kingboy'
    pat1 = (
        r"\b(?:c[oó]digo\s+)?(?:toro|reproductor|macho|padrote|donante)\s*[:#.]?\s*"
        r"([A-Za-z0-9\-_./ ]{1,35}?)(?=\s*(?:cantidad|cant|precio|vr|valor|total|nit|iva|subtotal|\$|\n|$))"
    )
    m1 = re.search(pat1, text, re.IGNORECASE)
    if m1:
        cand = _limpiar_nombre_toro(m1.group(1))
        if cand and cand.lower() not in STOP_WORDS_TORO:
            return cand

    # 2. 'pajuelas de toro GYR 502' / '10 pajuelas toro Kingboy' / 'pajuela toro Holstein Kingboy'
    pat2 = (
        r"\b(?:pajuelas?|pajillas?|semen|dosis)(?:\s+de|\s+del)?\s+(?:toro\s+)?"
        r"([A-Za-z0-9\-_./ ]{1,35}?)(?=\s*(?:cantidad|cant|precio|vr|valor|total|nit|iva|subtotal|\$|\n|$))"
    )
    m2 = re.search(pat2, text, re.IGNORECASE)
    if m2:
        cand = _limpiar_nombre_toro(m2.group(1))
        if cand and cand.lower() not in STOP_WORDS_TORO:
            return cand

    # 3. 'pajuelas <codigo>'
    pat3 = r"\b(?:pajuelas?|pajillas?)\s+(?:de\s+)?([A-Za-z0-9\-_]{2,20})\b"
    m3 = re.search(pat3, text, re.IGNORECASE)
    if m3:
        cand = _limpiar_nombre_toro(m3.group(1))
        if cand and cand.lower() not in STOP_WORDS_TORO:
            return cand

    return None


def detect_proveedor(text: str) -> Optional[str]:
    """Intenta detectar el nombre de la empresa distribuidora o centro genético."""
    if not text:
        return None
    for linea in text.splitlines():
        linea_s = linea.strip()
        if not linea_s:
            continue
        if re.search(r"\b(?:distribuidora|gen[eé]tica|inseminaci[oó]n|centro|cia|s\.?a\.?s?|semex|abs|altagenetics)\b", linea_s, re.IGNORECASE):
            return linea_s
    return None


def parse_factura_pajuelas(text_or_image: str) -> FacturaPajuelasInfo:
    """Extrae datos de compra de pajuelas a partir de texto o ruta de imagen.

    Busca NIT, total, código del toro, cantidad de pajuelas y genera una
    propuesta interactiva para cargar inventario con fallback graceful si no hay OCR.
    """
    if not text_or_image:
        return FacturaPajuelasInfo()

    texto = text_or_image
    if os.path.isfile(text_or_image):
        from .ocr_engine import OCREngine
        engine = OCREngine()
        texto = engine.extract_text(text_or_image)
        if not texto:
            return FacturaPajuelasInfo(texto_extraido="")

    t_lower = texto.lower()
    indicios_factura = bool(
        re.search(
            r"\b(?:factura|recibo|comprobante|cuenta\s+de\s+cobro|remisi[oó]n|compra|venta|nit|total|precio|valor|adquisici[oó]n)\b",
            t_lower,
        )
    )
    indicios_pajuelas = bool(
        re.search(
            r"\b(?:pajuelas?|pajillas?|semen|dosis|inseminaci[oó]n|gen[eé]tica|toro)\b",
            t_lower,
        )
    )

    nit = detect_nit(texto)
    total_val, total_raw = detect_total(texto)
    cantidad = detect_cantidad(texto)
    toro = detect_toro(texto)
    proveedor = detect_proveedor(texto)

    # Es factura de pajuelas si menciona pajuelas/semen/toro y tiene indicios de factura o datos clave
    es_factura = indicios_pajuelas and (
        indicios_factura or nit is not None or (toro is not None and cantidad is not None)
    )

    propuesta = ""
    if toro and cantidad:
        propuesta = f"Detecté compra de {cantidad} pajuelas toro {toro}, ¿confirmar?"
    elif cantidad:
        propuesta = f"Detecté compra de {cantidad} pajuelas, ¿confirmar?"
    elif toro:
        propuesta = f"Detecté compra de pajuelas toro {toro}, ¿confirmar?"

    return FacturaPajuelasInfo(
        es_factura=es_factura,
        toro=toro,
        cantidad=cantidad,
        nit=nit,
        total=total_val,
        total_raw=total_raw,
        proveedor=proveedor,
        texto_extraido=texto,
        propuesta_mensaje=propuesta,
    )
