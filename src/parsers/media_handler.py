"""Manejador de medios: transcripción de audio (simulación Whisper) e imágenes.

El procesamiento real de audio (Whisper) y de OCR no está disponible en este
entorno; se simula mediante archivos ``.txt`` acompañantes (``<archivo>.txt``)
o callables inyectables, de modo que la lógica del bot sea verificable sin
dependencias externas.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

AUDIO_EXT = (".wav", ".ogg", ".mp3", ".m4a", ".opus", ".webm", ".oga")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")


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


def transcribe_audio(audio_path: str,
                     transcriber: Optional[Callable[[str], str]] = None) -> AudioTranscript:
    """Transcribe un audio a texto.

    Si se inyecta ``transcriber`` (por ejemplo un stub de Whisper) se usa este;
    en su defecto se busca un ``.txt`` acompañante con la transcripción.
    """
    if audio_path.endswith(".txt"):
        with open(audio_path, encoding="utf-8") as f:
            return AudioTranscript(f.read().strip(), origen="sidecar-txt")
    sidecar = _read_sidecar(audio_path)
    if transcriber is not None:
        return AudioTranscript(transcriber(audio_path), origen="transcriber")
    if sidecar is not None:
        return AudioTranscript(sidecar, origen="sidecar")
    raise MediaError(
        f"Whisper no disponible y no hay transcripción para '{audio_path}'. "
        f"Proporcione un archivo {audio_path}.txt o un transcriber."
    )


def extract_image_info(image_path: str,
                       ocr: Optional[Callable[[str], ImageInfo]] = None) -> ImageInfo:
    """Extrae información de una foto (tags, frascos de fármacos).

    Si se inyecta ``ocr`` se usa; en su defecto se lee un ``.txt`` acompañante
    donde cada línea puede ser ``tag:47``, ``frase:...`` o ``frasco:...``.
    """
    if ocr is not None:
        result = ocr(image_path)
        return result if isinstance(result, ImageInfo) else ImageInfo()
    sidecar = _read_sidecar(image_path)
    if sidecar is None:
        raise MediaError(
            f"OCR no disponible y no hay descripción para '{image_path}'."
        )
    info = ImageInfo()
    for line in sidecar.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("tag:"):
            info.tags.append(line.split(":", 1)[1].strip())
        elif line.startswith("frasco:"):
            info.frascos.append(line.split(":", 1)[1].strip())
        else:
            info.texto_detectado = (info.texto_detectado + " " + line).strip()
    return info


def es_audio(path: str) -> bool:
    return path.lower().endswith(AUDIO_EXT) or path.lower().endswith(".txt")


def es_imagen(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXT)
