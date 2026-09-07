"""Parser multimodal con IA (Gemini Vision / NVIDIA NIM) para recibos y planillas de leche.

Digitaliza hojas de anotación diaria, planillas manuscritas y recibos de pago
quincenal de leche emitidos por empresas o acopiadores (Colanta, Alquería, queseras),
extrayendo los litros producidos día por día para su siembra directa en SQLite.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from typing import Any, Optional, Union

from ..llm.gemini_client import GeminiClient

logger = logging.getLogger("bitacora.vision.recibo_leche")

SYSTEM_PROMPT = """Eres un asistente zootécnico y contable experto en digitalización de planillas y recibos de producción lechera en fincas ganaderas de Colombia y Latinoamérica.
Tu objetivo es examinar con extrema precisión fotografías de:
1. Recibos o colillas de pago quincenal emitidos por acopiadores, cooperativas o empresas lecheras (ej. Colanta, Alquería, Alpina, queseras locales).
2. Hojas de cuaderno o planillas impresas de control lechero donde el mayordomo anota manualmente con lapicero los litros entregados o medidos cada día del mes (días 1 al 15, 16 al 30/31, etc.).

INSTRUCCIONES DE LECTURA:
- Identifica si la imagen corresponde a un recibo, colilla o planilla de leche (es_recibo_leche: true/false).
- Identifica el periodo, quincena, mes y año. Si el año o mes no están explícitos en el papel, utiliza como año y mes de referencia: {fecha_ref}.
- Extrae cada fila, casilla o renglón diario donde aparezca el día y sus litros:
  * dia: número entero del día del mes (1..31).
  * fecha: fecha en formato exacto 'YYYY-MM-DD'.
  * litros: número flotante con los litros de ese día (ej: 185.0). Si hay desglose de mañana (AM) y tarde (PM), suma ambos para el total del día y coloca el desglose en 'notas'.
  * notas: notas breves del día si las hay (ej: 'AM: 110, PM: 75').
- Identifica el total de litros declarado o impreso al final del recibo (total_litros_declarado) si está visible.
- Extrae observaciones generales (acopiador/empresa, grasa %, proteína %, precio por litro, retenciones, etc.).

Debes responder ÚNICAMENTE un objeto JSON válido con la siguiente estructura exacta:
{{
  "es_recibo_leche": true,
  "periodo": "1 al 15 de Mayo 2026",
  "mes": "Mayo",
  "ano": 2026,
  "acopiador": "Colanta",
  "total_litros_declarado": 2740.0,
  "observaciones": "Grasa: 3.7%, Proteína: 3.1%",
  "dias": [
    {{
      "dia": 1,
      "fecha": "2026-05-01",
      "litros": 185.0,
      "notas": "AM: 110, PM: 75"
    }}
  ],
  "confianza": "alta"
}}
"""


def _extraer_bytes_e_imagen(imagen: Union[bytes, str]) -> tuple[bytes, str]:
    """Normaliza bytes o cadena Base64, devolviendo (raw_bytes, mime_type)."""
    if isinstance(imagen, bytes):
        mime = "image/jpeg"
        if imagen.startswith(b"\x89PNG"):
            mime = "image/png"
        elif imagen.startswith(b"GIF"):
            mime = "image/gif"
        elif imagen.startswith(b"RIFF") and b"WEBP" in imagen[:16]:
            mime = "image/webp"
        return imagen, mime

    s = imagen.strip()
    mime = "image/jpeg"
    if s.startswith("data:"):
        match = re.match(r"^data:(image/[a-zA-Z0-9.-]+);base64,", s)
        if match:
            mime = match.group(1)
            s = s[len(match.group(0)):]

    raw = base64.b64decode(s)
    return raw, mime


def _ajustar_fechas_dias(dias: list[dict], fecha_ref: str, mes_nombre: Optional[str] = None, ano_int: Optional[int] = None) -> list[dict]:
    """Garantiza que cada día tenga una fecha válida YYYY-MM-DD."""
    try:
        ref_dt = datetime.strptime(fecha_ref, "%Y-%m-%d").date()
    except Exception:
        ref_dt = date.today()

    meses_map = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "setiembre": 9, "octubre": 10,
        "noviembre": 11, "diciembre": 12,
    }

    ano = ano_int or ref_dt.year
    mes = ref_dt.month
    if mes_nombre and str(mes_nombre).lower().strip() in meses_map:
        mes = meses_map[str(mes_nombre).lower().strip()]

    resultado = []
    for d in dias:
        if not isinstance(d, dict):
            continue
        dia_num = d.get("dia")
        litros = d.get("litros")
        try:
            litros = round(float(litros), 1)
        except (TypeError, ValueError):
            continue

        if dia_num is None and d.get("fecha"):
            try:
                dia_num = int(str(d["fecha"]).split("-")[-1])
            except Exception:
                pass

        try:
            dia_num = int(dia_num)
        except (TypeError, ValueError):
            dia_num = 1

        dia_num = max(1, min(31, dia_num))
        try:
            fec_str = f"{ano:04d}-{mes:02d}-{dia_num:02d}"
            datetime.strptime(fec_str, "%Y-%m-%d")
        except ValueError:
            fec_str = f"{ano:04d}-{mes:02d}-{min(dia_num, 28):02d}"

        resultado.append({
            "dia": dia_num,
            "fecha": fec_str,
            "litros": litros,
            "notas": str(d.get("notas") or "").strip(),
        })

    resultado.sort(key=lambda x: (x["fecha"], x["dia"]))
    return resultado


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
    prompt_usuario = (
        "Analiza esta imagen de recibo o planilla de leche. Extrae los litros día a día y el total. "
        "Devuelve únicamente el JSON solicitado."
    )

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
        "max_tokens": 2500,
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


def analizar_recibo_leche(imagen: Union[bytes, str], fecha_referencia: Optional[str] = None) -> dict[str, Any]:
    """Analiza una imagen de recibo/planilla de leche usando Gemini Vision o NVIDIA NIM.

    Devuelve un diccionario estructurado con los días leídos, totales y metadatos.
    """
    fecha_ref = fecha_referencia or date.today().isoformat()
    try:
        raw_bytes, mime = _extraer_bytes_e_imagen(imagen)
    except Exception as err:
        return {
            "ok": False,
            "error": f"No se pudo procesar la imagen adjunta: {err}",
            "es_recibo_leche": False,
            "dias": [],
        }

    datos_json: Optional[dict] = None

    # 1. Intentar con Gemini Vision (más rápido y preciso con JSON estructurado)
    gemini = GeminiClient()
    if gemini.is_available():
        sys_inst = SYSTEM_PROMPT.format(fecha_ref=fecha_ref)
        prompt_usr = (
            "Analiza este recibo o planilla de control de leche. "
            "Lee minuciosamente cada casilla de día y litros anotados a mano o impresos. "
            "Devuelve el JSON estructurado."
        )
        try:
            datos_json = gemini.generate_vision_structured(
                system_instruction=sys_inst,
                prompt=prompt_usr,
                image_bytes=raw_bytes,
                mime_type=mime,
                temperature=0.1,
                max_output_tokens=3000,
            )
        except Exception as e:
            logger.warning("Error en llamada a Gemini Vision: %s", e)
            datos_json = None

    # 2. Si Gemini no está disponible o falló, intentar con NVIDIA NIM Vision
    if not datos_json:
        datos_json = _analizar_con_nvidia_vision(raw_bytes, mime, fecha_ref)

    if not datos_json or not isinstance(datos_json, dict):
        tiene_keys = gemini.is_available() or bool(os.getenv("NVIDIA_API_KEY"))
        msg_err = (
            "No se pudo interpretar el recibo de leche con la IA de visión."
            if tiene_keys else
            "Para leer recibos con IA, configure GEMINI_API_KEY o NVIDIA_API_KEY en las variables de entorno."
        )
        return {
            "ok": False,
            "error": msg_err,
            "es_recibo_leche": False,
            "dias": [],
        }

    dias_raw = datos_json.get("dias") or []
    mes = datos_json.get("mes")
    ano = datos_json.get("ano")
    try:
        ano = int(ano) if ano else None
    except Exception:
        ano = None

    dias_procesados = _ajustar_fechas_dias(dias_raw, fecha_ref, mes_nombre=mes, ano_int=ano)
    total_calculado = round(sum(d["litros"] for d in dias_procesados), 1)

    total_declarado = datos_json.get("total_litros_declarado")
    try:
        total_declarado = round(float(total_declarado), 1) if total_declarado is not None else None
    except Exception:
        total_declarado = None

    discrepancia = round(abs(total_calculado - (total_declarado or total_calculado)), 1)

    return {
        "ok": True,
        "es_recibo_leche": bool(datos_json.get("es_recibo_leche", True) and len(dias_procesados) > 0),
        "periodo": str(datos_json.get("periodo") or f"{len(dias_procesados)} días detectados"),
        "mes": mes,
        "ano": ano,
        "acopiador": datos_json.get("acopiador") or "No especificado",
        "total_litros_declarado": total_declarado,
        "total_litros_calculado": total_calculado,
        "discrepancia_litros": discrepancia,
        "observaciones": str(datos_json.get("observaciones") or "").strip(),
        "dias": dias_procesados,
        "confianza": datos_json.get("confianza") or ("alta" if discrepancia < 2.0 else "media"),
    }
