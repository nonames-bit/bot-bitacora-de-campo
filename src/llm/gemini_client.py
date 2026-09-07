"""Cliente HTTP puro para Gemini (Google AI Studio, generativelanguage.googleapis.com).

Sin SDK, solo urllib.request + json, siguiendo la convención del proyecto de
no depender de librerías pesadas para la integración LLM.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional, Union

logger = logging.getLogger("bitacora.llm")

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiClient:
    """Cliente para la API de Gemini (Google AI Studio)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        if api_key is None:
            raw_key = os.getenv("GEMINI_API_KEY", "")
        else:
            raw_key = api_key
        # Deshabilitado si es placeholder o vacía
        if raw_key in ("pegar_aqui_tu_clave_de_gemini", "") or not raw_key.strip():
            self.api_key: Optional[str] = None
        else:
            self.api_key = raw_key.strip()

        self.model = model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    def is_available(self) -> bool:
        """Indica si el cliente cuenta con una API key configurada."""
        return bool(self.api_key and len(self.api_key) > 5)

    def generate_structured(
        self,
        system_instruction: str,
        user_text: str,
        response_schema: dict,
        temperature: float = 0.1,
        max_output_tokens: int = 1024,
    ) -> Optional[Union[dict, list]]:
        """Llama a generateContent pidiendo JSON conforme a ``response_schema``.

        Devuelve el JSON ya parseado (dict o list) o ``None`` ante cualquier
        fallo (sin API key, error de red/HTTP, timeout o respuesta malformada).
        Nunca lanza excepción hacia arriba.
        """
        if not self.is_available():
            return None
        if not user_text or not user_text.strip():
            return None

        url = DEFAULT_API_URL.format(model=self.model)
        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            },
        }

        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "BitacoraCampo-Gemini/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.warning("Respuesta Gemini sin candidates")
                    return None
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    logger.warning("Respuesta Gemini sin parts")
                    return None
                text = parts[0].get("text", "")
                if not text:
                    return None
                return json.loads(text)
        except urllib.error.HTTPError as he:
            logger.warning("Error HTTP en Gemini (%s): %s", he.code, he.reason)
            return None
        except urllib.error.URLError as ue:
            logger.warning("Error de red al conectar con Gemini: %s", ue.reason)
            return None
        except TimeoutError:
            logger.warning("Timeout al conectar con Gemini (>%ss)", self.timeout)
            return None
        except (json.JSONDecodeError, KeyError, IndexError) as pe:
            logger.warning("Respuesta Gemini malformada: %s", pe)
            return None
        except Exception as e:
            logger.warning("Excepción inesperada en Gemini: %s", e)
            return None

    def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """Transcribe un archivo de audio (ogg, mp3, wav, m4a) usando Gemini Multimodal."""
        if not self.is_available() or not os.path.exists(audio_path) or os.path.getsize(audio_path) < 200:
            return None
        import base64
        ext = os.path.splitext(audio_path)[1].lower().lstrip(".")
        mime_map = {
            "ogg": "audio/ogg",
            "oga": "audio/ogg",
            "mp3": "audio/mp3",
            "wav": "audio/wav",
            "m4a": "audio/mp4",
            "aac": "audio/aac",
            "flac": "audio/flac",
        }
        mime_type = mime_map.get(ext, "audio/ogg")
        try:
            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning("No se pudo leer audio %s: %s", audio_path, e)
            return None

        url = DEFAULT_API_URL.format(model=self.model)
        prompt = (
            "Eres un transcriptor experto en notas de campo ganadero y zootécnico en español. "
            "Transcribe textualmente y con exactitud lo que dice el audio (nombres de animales, números de arete, potreros, kilos, medicamentos). "
            "Devuelve ÚNICAMENTE el texto transcrito directo, sin comillas ni explicaciones adicionales."
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": audio_b64,
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 1024,
            },
        }
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "BitacoraCampo-Gemini/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                candidates = data.get("candidates", [])
                if not candidates:
                    return None
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    return None
                text = parts[0].get("text", "").strip()
        except Exception as e:
            logger.warning("Error en transcripción Gemini Audio: %s", e)
            return None

    def generate_vision_structured(
        self,
        system_instruction: str,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        response_schema: Optional[dict] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 3072,
    ) -> Optional[Union[dict, list]]:
        """Analiza una imagen con Gemini Multimodal y devuelve JSON estructurado."""
        if not self.is_available() or not image_bytes:
            return None
        import base64
        try:
            img_b64 = base64.b64encode(image_bytes).decode("utf-8")
        except Exception as e:
            logger.warning("No se pudo codificar imagen para Gemini Vision: %s", e)
            return None

        url = DEFAULT_API_URL.format(model=self.model)
        gen_config: dict = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "responseMimeType": "application/json",
        }
        if response_schema:
            gen_config["responseSchema"] = response_schema

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": img_b64,
                            }
                        },
                    ],
                }
            ],
            "generationConfig": gen_config,
        }
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "BitacoraCampo-Gemini/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                candidates = data.get("candidates", [])
                if not candidates:
                    return None
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    return None
                text = parts[0].get("text", "").strip()
                if not text:
                    return None
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text).strip()
                return json.loads(text)
        except Exception as e:
            logger.warning("Fallo en generate_vision_structured de Gemini: %s", e)
            return None

