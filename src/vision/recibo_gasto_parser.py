"""Parser multimodal con IA (Gemini Vision / NVIDIA NIM) para facturas y
recibos generales de gastos/ingresos de la finca (insumos, veterinario,
combustible, nómina, etc.) -- mismo patrón que ``recibo_leche_parser.py``
pero para cualquier factura, no solo recibos de leche.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import date
from typing import Any, Optional, Union

from ..llm.gemini_client import GeminiClient
from .recibo_leche_parser import _extraer_bytes_e_imagen

logger = logging.getLogger("bitacora.vision.recibo_gasto")

CATEGORIAS_VALIDAS = (
    "VENTA_LECHE", "OTRO_INGRESO",
    "NOMINA", "INSUMO", "VETERINARIO", "INFRAESTRUCTURA", "COMBUSTIBLE", "OTRO_EGRESO",
)

SYSTEM_PROMPT = """Eres un asistente contable experto en digitalizar facturas y recibos de gastos e ingresos de fincas ganaderas en Colombia.
Examinas fotografías de facturas de compra (insumos, medicamentos, combustible, mantenimiento), recibos de pago a trabajadores, o comprobantes de ingresos varios.

INSTRUCCIONES:
- Identifica si la imagen es realmente una factura/recibo/comprobante (es_factura: true/false).
- tipo: "EGRESO" si es una compra/gasto/pago que hizo la finca, "INGRESO" si es un comprobante de algo que la finca recibió (no ventas de leche ni de animales, esas ya se registran aparte).
- fecha: fecha del documento en formato 'YYYY-MM-DD'. Si no es visible, usa como referencia: {fecha_ref}.
- proveedor: nombre del negocio, persona o entidad que emite o recibe el documento (ej. "Agrotienda El Ganadero", "Dr. Pérez Veterinario").
- concepto: descripción breve de qué se compró o pagó (ej. "Sal mineralizada 3 bultos x 40kg", "Vacuna aftosa + desparasitante").
- categoria_sugerida: la que mejor aplique de esta lista exacta: VENTA_LECHE, OTRO_INGRESO, NOMINA, INSUMO, VETERINARIO, INFRAESTRUCTURA, COMBUSTIBLE, OTRO_EGRESO.
- monto_total: el valor total del documento, como número (ej: 450000.0). Sin símbolo de moneda ni separadores de miles.
- observaciones: cualquier detalle adicional relevante (número de factura, forma de pago, etc.).

Debes responder ÚNICAMENTE un objeto JSON válido con esta estructura exacta:
{{
  "es_factura": true,
  "tipo": "EGRESO",
  "fecha": "2026-09-01",
  "proveedor": "Agrotienda El Ganadero",
  "concepto": "Sal mineralizada 3 bultos x 40kg",
  "categoria_sugerida": "INSUMO",
  "monto_total": 450000.0,
  "observaciones": "",
  "confianza": "alta"
}}
"""


def _analizar_con_nvidia_vision(image_bytes: bytes, mime_type: str, fecha_ref: str) -> Optional[dict]:
    """Fallback a NVIDIA NIM Vision (meta/llama-3.2-90b-vision-instruct)."""
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not api_key or api_key.startswith("pegar_"):
        return None

    model = os.getenv("NVIDIA_VISION_MODEL") or os.getenv("NVIDIA_MODEL") or "meta/llama-3.2-90b-vision-instruct"
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    b64_str = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64_str}"

    prompt_sistema = SYSTEM_PROMPT.format(fecha_ref=fecha_ref)
    prompt_usuario = "Analiza esta factura o recibo. Devuelve únicamente el JSON solicitado."

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_usuario},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 800,
    }

    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=40.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if not choices:
                return None
            txt = choices[0].get("message", {}).get("content", "").strip()
            if txt.startswith("```"):
                txt = re.sub(r"^```(?:json)?\s*", "", txt)
                txt = re.sub(r"\s*```$", "", txt).strip()
            return json.loads(txt)
    except Exception as err:
        logger.warning("Fallo en vision NVIDIA NIM: %s", err)
        return None


def analizar_factura_gasto(imagen: Union[bytes, str], fecha_referencia: Optional[str] = None) -> dict[str, Any]:
    """Analiza una foto de factura/recibo de gasto o ingreso usando Gemini
    Vision o NVIDIA NIM. Devuelve los campos listos para pre-llenar la
    captura de Finanzas (fecha, proveedor, concepto, categoría, monto)."""
    fecha_ref = fecha_referencia or date.today().isoformat()
    try:
        raw_bytes, mime = _extraer_bytes_e_imagen(imagen)
    except Exception as err:
        return {"ok": False, "error": f"No se pudo procesar la imagen adjunta: {err}", "es_factura": False}

    datos_json: Optional[dict] = None

    gemini = GeminiClient()
    if gemini.is_available():
        sys_inst = SYSTEM_PROMPT.format(fecha_ref=fecha_ref)
        try:
            datos_json = gemini.generate_vision_structured(
                system_instruction=sys_inst,
                prompt="Analiza esta factura o recibo. Devuelve el JSON estructurado.",
                image_bytes=raw_bytes,
                mime_type=mime,
                temperature=0.1,
                max_output_tokens=800,
            )
        except Exception as e:
            logger.warning("Error en llamada a Gemini Vision: %s", e)
            datos_json = None

    if not datos_json:
        datos_json = _analizar_con_nvidia_vision(raw_bytes, mime, fecha_ref)

    if not datos_json or not isinstance(datos_json, dict):
        tiene_keys = gemini.is_available() or bool(os.getenv("NVIDIA_API_KEY"))
        msg_err = (
            "No se pudo interpretar la factura con la IA de visión."
            if tiene_keys else
            "Para leer facturas con IA, configure GEMINI_API_KEY o NVIDIA_API_KEY en las variables de entorno."
        )
        return {"ok": False, "error": msg_err, "es_factura": False}

    def _num_o_none(valor):
        try:
            return round(float(valor), 2) if valor is not None else None
        except (TypeError, ValueError):
            return None

    tipo = str(datos_json.get("tipo") or "EGRESO").strip().upper()
    if tipo not in ("INGRESO", "EGRESO"):
        tipo = "EGRESO"
    categoria = str(datos_json.get("categoria_sugerida") or "").strip().upper()
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = "OTRO_INGRESO" if tipo == "INGRESO" else "OTRO_EGRESO"

    fecha = str(datos_json.get("fecha") or fecha_ref).strip()
    try:
        date.fromisoformat(fecha)
    except ValueError:
        fecha = fecha_ref

    return {
        "ok": True,
        "es_factura": bool(datos_json.get("es_factura", True)),
        "tipo": tipo,
        "fecha": fecha,
        "proveedor": str(datos_json.get("proveedor") or "").strip(),
        "concepto": str(datos_json.get("concepto") or "").strip(),
        "categoria_sugerida": categoria,
        "monto_total": _num_o_none(datos_json.get("monto_total")),
        "observaciones": str(datos_json.get("observaciones") or "").strip(),
        "confianza": datos_json.get("confianza") or "media",
    }
