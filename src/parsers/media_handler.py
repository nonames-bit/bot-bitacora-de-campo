"""Manejador de medios: transcripción de audio (simulación Whisper) e imágenes.

El procesamiento real de audio (Whisper) y de OCR no está disponible en este
entorno; se simula mediante archivos ``.txt`` acompañantes (``<archivo>.txt``)
o callables inyectables, de modo que la lógica del bot sea verificable sin
dependencias externas.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger("bitacora.media")

AUDIO_EXT = (".wav", ".ogg", ".mp3", ".m4a", ".opus", ".webm", ".oga")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")

# Singleton de modelo Whisper en memoria para reutilización eficiente
_WHISPER_MODEL = None
_WHISPER_BACKEND = None


class MediaError(Exception):
    """Error al procesar un medio (audio/imagen)."""


@dataclass
class AudioTranscript:
    texto: str
    origen: str = ""
    confianza: float = 1.0


@dataclass
class ImageInfo:
    tags: list[str] = field(default_factory=list)
    texto_detectado: str = ""
    frascos: list[str] = field(default_factory=list)
    medicamento: Optional[dict] = None
    ocr_text: str = ""
    factura_pajuelas: Optional[object] = None


def _read_sidecar(path: str) -> Optional[str]:
    """Lee un archivo ``.txt`` acompañante con la transcripción/OCR simulada."""
    if os.path.isdir(path):
        return None
    candidates = [f"{path}.txt"]
    base, _ = os.path.splitext(path)
    candidates.append(f"{base}.txt")
    for c in candidates:
        if os.path.isfile(c):
            with open(c, encoding="utf-8") as f:
                return f.read().strip()
    return None


def _get_whisper_model():
    """Carga y cachea el modelo Whisper disponible (faster-whisper o openai-whisper)."""
    global _WHISPER_MODEL, _WHISPER_BACKEND
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL, _WHISPER_BACKEND

    model_size = os.getenv("WHISPER_MODEL", "base")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    # 1. Intentar faster-whisper (más rápido y ligero en CPU)
    try:
        from faster_whisper import WhisperModel
        logger.info("Cargando modelo faster-whisper ('%s', device='%s', compute_type='%s')...",
                    model_size, device, compute_type)
        _WHISPER_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
        _WHISPER_BACKEND = "faster-whisper"
        return _WHISPER_MODEL, _WHISPER_BACKEND
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Fallo al inicializar faster-whisper: %s", e)

    # 2. Intentar openai-whisper
    try:
        import whisper
        logger.info("Cargando modelo openai-whisper ('%s')...", model_size)
        _WHISPER_MODEL = whisper.load_model(model_size)
        _WHISPER_BACKEND = "openai-whisper"
        return _WHISPER_MODEL, _WHISPER_BACKEND
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Fallo al inicializar openai-whisper: %s", e)

    return None, None


def _transcribe_with_local_whisper(audio_path: str) -> Optional[AudioTranscript]:
    """Ejecuta transcripción con el modelo Whisper local si está disponible."""
    model, backend = _get_whisper_model()
    if model is None:
        return None

    try:
        if backend == "faster-whisper":
            segments, info = model.transcribe(audio_path, language="es", beam_size=5)
            texto = " ".join(seg.text.strip() for seg in segments).strip()
            conf = getattr(info, "avg_logprob", 1.0)
            return AudioTranscript(texto=texto, origen=f"faster-whisper ({getattr(info, 'language', 'es')})", confianza=float(conf))
        elif backend == "openai-whisper":
            result = model.transcribe(audio_path, language="es")
            texto = result.get("text", "").strip()
            return AudioTranscript(texto=texto, origen="openai-whisper (es)")
    except Exception as e:
        logger.error("Error transcribiendo audio con %s: %s", backend, e)
        raise MediaError(f"Error en transcripción Whisper: {e}") from e

    return None


def transcribe_audio(audio_path: str,
                     transcriber: Optional[Callable[[str], str]] = None) -> AudioTranscript:
    """Transcribe un audio a texto.

    Prioridad:
    1. Transcriber inyectado explícitamente (callback/stub).
    2. Archivo sidecar ``.txt`` acompañante (si existe).
    3. Whisper local (faster-whisper / openai-whisper).
    """
    if audio_path.endswith(".txt"):
        with open(audio_path, encoding="utf-8") as f:
            return AudioTranscript(f.read().strip(), origen="sidecar-txt")

    if transcriber is not None:
        return AudioTranscript(transcriber(audio_path), origen="transcriber")

    sidecar = _read_sidecar(audio_path)
    if sidecar is not None:
        return AudioTranscript(sidecar, origen="sidecar")

    # Intentar Whisper real local
    res = _transcribe_with_local_whisper(audio_path)
    if res is not None:
        return res

    # Intentar transcripción con Gemini Audio Multimodal (IA en la nube)
    try:
        from ..llm.gemini_client import GeminiClient
        client = GeminiClient()
        if client.is_available():
            txt_gemini = client.transcribe_audio(audio_path)
            if txt_gemini:
                return AudioTranscript(txt_gemini, origen="gemini-audio")
    except Exception as eg:
        logger.debug("Fallo al transcribir con Gemini: %s", eg)

    raise MediaError(
        f"No se pudo transcribir el audio '{audio_path}'. "
        f"Verifica la API key de Gemini (GEMINI_API_KEY) o instala faster-whisper ('pip install faster-whisper')."
    )


def extract_image_info(image_path: str,
                       ocr: Optional[Callable[[str], ImageInfo]] = None) -> ImageInfo:
    """Extrae información de una foto (tags, frascos de fármacos).

    Prioridad:
    1. OCR inyectado explícitamente (callback/stub).
    2. Archivo sidecar ``.txt`` acompañante (si existe).
    3. OCR local real (OCREngine: pytesseract / easyocr).
    """
    if ocr is not None:
        result = ocr(image_path)
        return result if isinstance(result, ImageInfo) else ImageInfo()

    sidecar = _read_sidecar(image_path)
    if sidecar is not None:
        info = ImageInfo(ocr_text=sidecar)
        from ..ocr.factura_parser import parse_factura_pajuelas
        from ..ocr.ocr_engine import detect_medicamento, detect_tags
        for line in sidecar.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            if line_s.startswith("tag:"):
                info.tags.append(line_s.split(":", 1)[1].strip())
            elif line_s.startswith("frasco:"):
                info.frascos.append(line_s.split(":", 1)[1].strip())
            else:
                info.texto_detectado = (info.texto_detectado + " " + line_s).strip()

        # Enriquecer con detección automática si faltan tags o frascos explícitos
        if not info.tags:
            info.tags = detect_tags(sidecar)
        med = detect_medicamento(sidecar)
        if med and med.get("producto"):
            info.medicamento = med
            if med["producto"] not in info.frascos:
                info.frascos.append(med["producto"])
        fac = parse_factura_pajuelas(sidecar)
        if fac and (fac.es_factura or fac.propuesta_mensaje):
            info.factura_pajuelas = fac
        return info

    # Intentar OCR local con OCREngine y visión avanzada de aretes
    from ..ocr.factura_parser import parse_factura_pajuelas
    from ..ocr.ocr_engine import OCREngine
    from ..vision.arete_detector import detectar_arete_avanzado
    engine = OCREngine()
    if engine.is_available():
        texto_ocr = engine.extract_text(image_path)
        tags_encontrados = engine.detect_tags(texto_ocr) if texto_ocr else []

        # Si no se encontraron tags o la imagen es un arete difícil, usar visión avanzada
        if not tags_encontrados and os.path.isfile(image_path):
            vis_res = detectar_arete_avanzado(image_path)
            if vis_res.get("tag"):
                tags_encontrados = [vis_res["tag"]]
                if not texto_ocr:
                    texto_ocr = vis_res.get("texto_bruto", "")

        if texto_ocr or tags_encontrados:
            info = ImageInfo(
                ocr_text=texto_ocr,
                texto_detectado=texto_ocr,
                tags=tags_encontrados,
            )
            med = engine.detect_medicamento(texto_ocr)
            if med and med.get("producto"):
                info.medicamento = med
                info.frascos.append(med["producto"])
            fac = parse_factura_pajuelas(texto_ocr)
            if fac and (fac.es_factura or fac.propuesta_mensaje):
                info.factura_pajuelas = fac
            return info
        return ImageInfo()

    raise MediaError(
        f"OCR no disponible y no hay descripción para '{image_path}'. "
        f"Instala pytesseract ('pip install pytesseract Pillow') o proporciona {image_path}.txt."
    )


def es_audio(path: str) -> bool:
    return path.lower().endswith(AUDIO_EXT) or path.lower().endswith(".txt")


def es_imagen(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXT)
