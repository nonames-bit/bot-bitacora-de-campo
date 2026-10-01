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

from ..engine.finanzas_categorias import CATEGORIAS_EGRESO, CATEGORIAS_INGRESO, normalizar_categoria
from ..llm.gemini_client import GeminiClient
from .recibo_leche_parser import _extraer_bytes_e_imagen

logger = logging.getLogger("bitacora.vision.recibo_gasto")

CATEGORIAS_VALIDAS = CATEGORIAS_INGRESO + CATEGORIAS_EGRESO

# Máximo de renglones que se leen de una factura (y de movimientos en que se
# reparte): una factura de agrotienda rara vez trae más.
MAX_ITEMS = 30

SYSTEM_PROMPT = """Eres un asistente contable experto en digitalizar facturas y recibos de gastos e ingresos de fincas ganaderas en Colombia.
Examinas fotografías de facturas de compra (agrotienda, droguería veterinaria, combustible, ferretería), recibos de pago a trabajadores, o comprobantes de ingresos varios.

CATEGORÍAS DE GASTO (usa el código exacto):
- SAL_MINERALES: sal blanca, sal mineralizada, premezclas minerales, bloques multinutricionales.
- MEDICAMENTOS: drogas veterinarias: vacunas, antibióticos, desparasitantes, ivermectina, garrapaticidas, vitaminas, hormonas, jeringas y agujas.
- ALIMENTO: concentrado, melaza, silo, heno, semilla de algodón, suplementos alimenticios.
- FERTILIZANTES: abonos, urea, cal, semillas de pasto, herbicidas y venenos para potreros.
- REPRODUCCION: pajillas de semen, nitrógeno líquido, guantes y catéteres de inseminación.
- INSUMO: otros insumos de la finca: alambre, grapas, herramienta, sogas, baldes, repuestos.
- NOMINA: pagos a trabajadores, jornales.
- VETERINARIO: honorarios o visita del veterinario (el servicio, no las drogas).
- INFRAESTRUCTURA: materiales y mano de obra de construcción o reparación de corrales, cercas, bebederos.
- COMBUSTIBLE: gasolina, ACPM, aceite de motor.
- OTRO_EGRESO: cualquier otro gasto.
CATEGORÍAS DE INGRESO: VENTA_LECHE, OTRO_INGRESO.

INSTRUCCIONES:
- Identifica si la imagen es realmente una factura/recibo/comprobante (es_factura: true/false).
- tipo: "EGRESO" si es una compra/gasto/pago que hizo la finca, "INGRESO" si es un comprobante de algo que la finca recibió (no ventas de leche ni de animales, esas ya se registran aparte).
- fecha: fecha del documento en formato 'YYYY-MM-DD'. Si no es visible, usa como referencia: {fecha_ref}.
- proveedor: nombre del negocio, persona o entidad que emite o recibe el documento (ej. "Agrotienda El Ganadero", "Dr. Pérez Veterinario").
- items: cada renglón de la factura con su descripción, su valor total del renglón (número, sin símbolos ni separadores de miles) y su categoría de la lista de arriba. Si no se ven renglones, deja la lista vacía.
- concepto: descripción breve de qué se compró o pagó (ej. "Sal mineralizada 3 bultos x 40kg, Ivermectina 500 ml").
- categoria_sugerida: la categoría que más plata se lleva en la factura.
- monto_total: el valor total a pagar del documento (con IVA), como número (ej: 450000.0).
- observaciones: cualquier detalle adicional relevante (número de factura, forma de pago, etc.).

Debes responder ÚNICAMENTE un objeto JSON válido con esta estructura exacta:
{{
  "es_factura": true,
  "tipo": "EGRESO",
  "fecha": "2026-09-01",
  "proveedor": "Agrotienda El Ganadero",
  "items": [
    {{"descripcion": "Sal mineralizada 8% bulto 40kg x3", "valor": 330000.0, "categoria": "SAL_MINERALES"}},
    {{"descripcion": "Ivermectina 1% x 500 ml", "valor": 120000.0, "categoria": "MEDICAMENTOS"}}
  ],
  "concepto": "Sal mineralizada 3 bultos, Ivermectina 500 ml",
  "categoria_sugerida": "SAL_MINERALES",
  "monto_total": 450000.0,
  "observaciones": "Factura FE-1234, contado",
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
        "max_tokens": 1500,
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
                max_output_tokens=1500,
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

    tipo = str(datos_json.get("tipo") or "EGRESO").strip().upper()
    if tipo not in ("INGRESO", "EGRESO"):
        tipo = "EGRESO"
    categoria = normalizar_categoria(datos_json.get("categoria_sugerida"), tipo)

    fecha = str(datos_json.get("fecha") or fecha_ref).strip()
    try:
        date.fromisoformat(fecha)
    except ValueError:
        fecha = fecha_ref

    monto_total = _num_o_none(datos_json.get("monto_total"))
    items = _normalizar_items(datos_json.get("items"), tipo)
    if monto_total is None and items:
        monto_total = round(sum(i["valor"] for i in items), 2)
    concepto = str(datos_json.get("concepto") or "").strip()
    desglose = desglosar_por_categoria(items, monto_total, tipo, categoria, concepto)
    if len(desglose) > 1:
        # La sugerida es la que más plata se lleva, aunque la IA diga otra.
        categoria = max(desglose, key=lambda g: g["monto"])["categoria"]

    return {
        "ok": True,
        "es_factura": bool(datos_json.get("es_factura", True)),
        "tipo": tipo,
        "fecha": fecha,
        "proveedor": str(datos_json.get("proveedor") or "").strip(),
        "concepto": concepto,
        "categoria_sugerida": categoria,
        "monto_total": monto_total,
        "items": items,
        "desglose": desglose,
        "observaciones": str(datos_json.get("observaciones") or "").strip(),
        "confianza": datos_json.get("confianza") or "media",
    }


def _num_o_none(valor):
    try:
        return round(float(valor), 2) if valor is not None else None
    except (TypeError, ValueError):
        return None


def _normalizar_items(crudos: Any, tipo: str) -> list[dict]:
    """Renglones de la factura con valor > 0 y categoría conocida."""
    if not isinstance(crudos, list):
        return []
    items = []
    for it in crudos[:MAX_ITEMS]:
        if not isinstance(it, dict):
            continue
        valor = _num_o_none(it.get("valor"))
        if not valor or valor <= 0:
            continue
        items.append({
            "descripcion": str(it.get("descripcion") or "").strip()[:120],
            "valor": valor,
            "categoria": normalizar_categoria(it.get("categoria"), tipo),
        })
    return items


def desglosar_por_categoria(items: list[dict], monto_total: Optional[float], tipo: str,
                            categoria: str, concepto: str) -> list[dict]:
    """Agrupa los renglones por categoría: un movimiento de Finanzas por cada
    una. Los renglones suelen venir sin IVA o con descuentos, así que cada
    grupo se escala para que la suma dé el total a pagar de la factura (el
    último grupo absorbe el redondeo). Sin renglones, o si todos son de la
    misma categoría, devuelve un solo grupo con el total."""
    unico = [{"categoria": categoria, "concepto": concepto, "monto": monto_total}]
    if not items:
        return unico
    grupos: dict[str, dict] = {}
    for it in items:
        g = grupos.setdefault(it["categoria"], {"categoria": it["categoria"], "descripciones": [], "valor": 0.0})
        g["valor"] += it["valor"]
        if it["descripcion"]:
            g["descripciones"].append(it["descripcion"])
    if len(grupos) == 1:
        unica = next(iter(grupos.values()))
        return [{"categoria": unica["categoria"], "concepto": concepto or ", ".join(unica["descripciones"])[:200],
                 "monto": monto_total}]
    suma = sum(g["valor"] for g in grupos.values())
    objetivo = monto_total if monto_total and monto_total > 0 else suma
    orden = sorted(grupos.values(), key=lambda g: -g["valor"])
    salida = []
    acumulado = 0.0
    for i, g in enumerate(orden):
        if i == len(orden) - 1:
            monto = round(objetivo - acumulado, 2)
        else:
            monto = round(g["valor"] * objetivo / suma, 0)
            acumulado += monto
        salida.append({"categoria": g["categoria"], "concepto": ", ".join(g["descripciones"])[:200], "monto": monto})
    return salida
