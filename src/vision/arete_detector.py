"""Detector y OCR avanzado de aretes ganaderos en condiciones adversas de campo.

Diseñado para procesar fotografías de aretes con suciedad (barro, polvo),
contraluz, ángulos inclinados y distinguir entre aretes tipo paleta (rectangulares)
y aretes tipo botón (redondos/pequeños).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional, Tuple

logger = logging.getLogger("bitacora.vision.arete")

# Prefijos reconocidos frecuentes en ganaderías colombianas y el proyecto
PREFIJOS_CONOCIDOS = {"N", "A", "JA", "H", "B", "T", "V", "R", "L", "SG", "G"}

# Palabras no válidas como identificadores de arete
PALABRAS_DESCARTADAS = {
    "lote", "fecha", "vaca", "toro", "arete", "tag", "foto", "caravana", "chapa",
    "ml", "kg", "sc", "im", "iv", "exp", "lot", "retiro", "carne", "leche", "dias",
    "hoy", "ayer", "campo", "raza", "peso", "dia", "mes", "ano",
}


def corregir_caracteres_confusos(texto: str) -> str:
    """Corrige errores típicos de OCR en aretes de ganado.

    Ejemplos:
    - 'NO69' -> 'N069' (la letra 'O' después del prefijo se convierte en '0')
    - 'JA-2G' -> 'JA-26' ('G' confundida con '6')
    - 'A-I05' -> 'A-105' ('I' o 'l' confundida con '1')
    - 'N-O57' -> 'N-057'
    """
    if not texto:
        return ""

    t = texto.strip().upper()

    # 1. Probar primero con prefijos conocidos (ej. 'N', 'JA', 'A', etc.)
    for pref in sorted(PREFIJOS_CONOCIDOS, key=len, reverse=True):
        if t.startswith(pref) and len(t) > len(pref):
            resto = t[len(pref):].lstrip("-_ .")
            resto_corregido = (
                resto.replace("O", "0")
                .replace("Q", "0")
                .replace("D", "0")
                .replace("I", "1")
                .replace("L", "1")
                .replace("Z", "2")
                .replace("S", "5")
                .replace("G", "6")
                .replace("B", "8")
            )
            if resto_corregido.isdigit():
                if "-" in t or "_" in t:
                    return f"{pref}-{resto_corregido}"
                return f"{pref}{resto_corregido}"

    # 2. Corrección en prefijos con guion o espacio: e.g. "JA-2G"
    m_pref = re.match(r"^([A-Z]{1,3})[\s\-_.]+([A-Z0-9]+)$", t)
    if m_pref:
        prefijo = m_pref.group(1)
        cuerpo = m_pref.group(2)
        cuerpo_corregido = (
            cuerpo.replace("O", "0")
            .replace("Q", "0")
            .replace("D", "0")
            .replace("I", "1")
            .replace("L", "1")
            .replace("Z", "2")
            .replace("S", "5")
            .replace("G", "6")
            .replace("B", "8")
        )
        if cuerpo_corregido.isdigit():
            if "-" in t or "_" in t:
                return f"{prefijo}-{cuerpo_corregido}"
            return f"{prefijo}{cuerpo_corregido}"

    # 3. Corrección en números puros con ruido (ej. 'IO5' -> '105', '4O7' -> '407')
    candidato_num = (
        t.replace("O", "0")
        .replace("Q", "0")
        .replace("D", "0")
        .replace("I", "1")
        .replace("L", "1")
        .replace("Z", "2")
        .replace("S", "5")
        .replace("G", "6")
        .replace("B", "8")
    )
    if candidato_num.isdigit():
        return candidato_num

    return t



def clasificar_tipo_arete(ancho: int, alto: int) -> str:
    """Clasifica el tipo de arete según su relación de aspecto geométrica."""
    if ancho <= 0 or alto <= 0:
        return "DESCONOCIDO"
    aspect_ratio = max(ancho, alto) / min(ancho, alto)
    # Arete botón: casi circular o cuadrado (aspect ratio < 1.35)
    # Arete paleta: rectangular alargado (aspect ratio >= 1.35)
    if aspect_ratio < 1.35:
        return "BOTON"
    return "PALETA"


def mejorar_imagen_para_ocr(image_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """Aplica preprocesamiento avanzado a la imagen para resaltar caracteres sucios.

    Utiliza OpenCV si está instalado (CLAHE, Bilateral Filter, Otsu),
    o PIL (Pillow) como fallback con realce de contraste y nitidez.
    """
    if not image_path or not os.path.isfile(image_path):
        return None

    out_file = output_path or f"{os.path.splitext(image_path)[0]}_enhanced.jpg"

    # 1. Intentar OpenCV (alta precisión morfológica)
    try:
        import cv2
        import numpy as np

        img = cv2.imread(image_path)
        if img is not None:
            # Convertir a escala de grises
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Redimensionar si es muy pequeña (mínimo 600px de altura para legibilidad OCR)
            h, w = gray.shape
            if h < 600 or w < 600:
                scale = max(600 / h, 600 / w)
                gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

            # Filtro Bilateral para eliminar ruido y barro preservando bordes de los números
            filtered = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

            # CLAHE: Ecualización de histograma adaptativa para compensar sombras y contraluz
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(filtered)

            cv2.imwrite(out_file, enhanced)
            return out_file
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Fallo en preprocesamiento OpenCV: %s", e)

    # 2. Fallback con PIL (Pillow)
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        with Image.open(image_path) as img:
            # Escala de grises
            gray = ImageOps.grayscale(img)

            # Redimensionar si es pequeña
            w, h = gray.size
            if w < 600 or h < 600:
                scale = max(600 / w, 600 / h)
                gray = gray.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)

            # Aumentar contraste
            enh_contrast = ImageEnhance.Contrast(gray).enhance(2.0)
            # Aumentar nitidez
            enh_sharp = ImageEnhance.Sharpness(enh_contrast).enhance(2.0)

            enh_sharp.save(out_file)
            return out_file
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Fallo en preprocesamiento PIL: %s", e)

    return None


def detectar_arete_avanzado(image_path: str) -> dict:
    """Detecta y extrae el identificador de arete en una imagen con soporte para casos difíciles.

    Retorna un diccionario con:
    - ``tag``: Tag limpio y corregido (ej. 'N069', '47', 'JA-26').
    - ``tipo_arete``: 'PALETA', 'BOTON' o 'DESCONOCIDO'.
    - ``confianza``: Valor entre 0.0 y 1.0.
    - ``texto_bruto``: Texto crudo obtenido por OCR.
    - ``imagen_procesada``: Ruta de la imagen preprocesada (si se generó).
    """
    resultado = {
        "tag": None,
        "tipo_arete": "DESCONOCIDO",
        "confianza": 0.0,
        "texto_bruto": "",
        "imagen_procesada": None,
    }

    if not image_path:
        return resultado

    # 1. Si existe sidecar .txt de prueba o anotación de campo
    sidecar_txt = None
    candidates = [f"{image_path}.txt", f"{os.path.splitext(image_path)[0]}.txt"]
    for sc in candidates:
        if os.path.isfile(sc):
            try:
                with open(sc, "r", encoding="utf-8") as f:
                    sidecar_txt = f.read().strip()
                    break
            except Exception:
                pass

    if sidecar_txt:
        resultado["texto_bruto"] = sidecar_txt
        # Buscar tag explícito en sidecar
        from ..ocr.ocr_engine import detect_tags
        tags_encontrados = detect_tags(sidecar_txt)
        if tags_encontrados:
            raw_tag = tags_encontrados[0]
            resultado["tag"] = corregir_caracteres_confusos(raw_tag)
            resultado["confianza"] = 0.95
            resultado["tipo_arete"] = "BOTON" if len(resultado["tag"]) <= 3 and resultado["tag"].isdigit() else "PALETA"
            return resultado

    # 2. Intentar preprocesamiento y OCR local
    if os.path.isfile(image_path):
        enhanced_path = mejorar_imagen_para_ocr(image_path)
        if enhanced_path:
            resultado["imagen_procesada"] = enhanced_path

        from ..ocr.ocr_engine import OCREngine
        engine = OCREngine()
        texto_ocr = ""

        # Probar primero con la imagen mejorada
        if enhanced_path and os.path.isfile(enhanced_path):
            texto_ocr = engine.extract_text(enhanced_path)

        # Si no arrojó texto, probar con la original
        if not texto_ocr:
            texto_ocr = engine.extract_text(image_path)

        resultado["texto_bruto"] = texto_ocr

        if texto_ocr:
            tags = engine.detect_tags(texto_ocr)
            if tags:
                tag_candidato = corregir_caracteres_confusos(tags[0])
                if tag_candidato.lower() not in PALABRAS_DESCARTADAS:
                    resultado["tag"] = tag_candidato
                    resultado["confianza"] = 0.85
                    resultado["tipo_arete"] = "BOTON" if len(tag_candidato) <= 3 and tag_candidato.isdigit() else "PALETA"

    return resultado


class AreteDetector:
    """Clase envolvente para detección y clasificación de aretes visuales."""

    def __init__(self):
        pass

    def procesar(self, image_path: str) -> dict:
        """Procesa una imagen y retorna los datos del arete identificado."""
        return detectar_arete_avanzado(image_path)

    def corregir_texto(self, texto: str) -> str:
        """Aplica correcciones de OCR específicas de aretes a un texto."""
        return corregir_caracteres_confusos(texto)
