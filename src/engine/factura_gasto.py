"""Anotar en Finanzas una factura de gasto leída con IA desde Telegram.

La PWA hace lo mismo desde Registrar → Ingreso / Gasto (ver
``src/pwa/rutas/sync.py``); aquí vive la parte que no depende de Telegram
para poder probarla sin el bot.
"""
from __future__ import annotations

import html
import re
from typing import Any, Optional

from .finanzas_categorias import ETIQUETAS

# Palabras en el pie de foto que piden leer la foto como factura de gasto.
_PALABRAS_FACTURA = re.compile(
    r"\b(factura|recibo|gasto|compra|compr[eé]|cuenta\s+de\s+cobro|remisi[oó]n|tiquete)\b",
    re.IGNORECASE,
)


def pide_leer_factura(caption: str, ocr_text: str) -> bool:
    """True si el pie de foto habla de una factura o si el OCR ve plata
    (números junto a $, NIT o COP), igual que el aviso viejo de pajillas."""
    if caption and _PALABRAS_FACTURA.search(caption):
        return True
    texto = ocr_text or ""
    return bool(re.search(r"\d", texto) and re.search(r"(\$|\bnit\b|\bcop\b)", texto, re.IGNORECASE))


def _pesos(valor: Any) -> str:
    try:
        return "$" + f"{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def partes_factura(res: dict) -> list[dict]:
    """Los movimientos a anotar: uno por categoría si la factura trae
    varias, si no uno solo con el total."""
    desglose = [g for g in (res.get("desglose") or []) if (g.get("monto") or 0) > 0]
    if len(desglose) > 1:
        return desglose
    return [{"categoria": res.get("categoria_sugerida") or "OTRO_EGRESO",
             "concepto": res.get("concepto") or "", "monto": res.get("monto_total")}]


def texto_propuesta(res: dict) -> str:
    """Mensaje HTML con lo que se leyó, para confirmar con un botón."""
    lineas = ["🧾 <b>Factura leída</b>"]
    if res.get("proveedor"):
        lineas.append(f"Proveedor: {html.escape(res['proveedor'])}")
    lineas.append(f"Fecha: {html.escape(str(res.get('fecha') or ''))}")
    partes = partes_factura(res)
    if len(partes) > 1:
        lineas.append("")
        for p in partes:
            lineas.append(f"• <b>{html.escape(ETIQUETAS.get(p['categoria'], p['categoria']))}</b>: {_pesos(p['monto'])}")
            if p.get("concepto"):
                lineas.append(f"   <i>{html.escape(p['concepto'])}</i>")
        lineas.append(f"\nTotal: <b>{_pesos(res.get('monto_total'))}</b>")
    else:
        p = partes[0]
        lineas.append(f"Categoría: <b>{html.escape(ETIQUETAS.get(p['categoria'], p['categoria']))}</b>")
        if p.get("concepto"):
            lineas.append(f"Concepto: {html.escape(p['concepto'])}")
        lineas.append(f"Total: <b>{_pesos(p['monto'])}</b>")
    lineas.append("\n¿La anoto como gasto en Finanzas?")
    return "\n".join(lineas)


def anotar_factura(db, res: dict, *, foto_ruta: Optional[str], user_id: Optional[int]) -> list[int]:
    """Registra la factura como egreso(s) en ``finanzas``. Devuelve los ids."""
    partes = partes_factura(res)
    if any(not p.get("monto") or float(p["monto"]) <= 0 for p in partes):
        raise ValueError("La factura no tiene un total válido.")
    nota = "Leída con IA desde Telegram."
    if len(partes) > 1:
        nota += f" Factura repartida en {len(partes)} categorías."
    return [
        db.registrar_finanza(
            fecha=res.get("fecha"), tipo="EGRESO", categoria=p["categoria"],
            concepto=p.get("concepto") or None, monto=p["monto"],
            contraparte=res.get("proveedor") or None, foto_ruta=foto_ruta,
            notas=nota, registrado_por=user_id,
        )
        for p in partes
    ]
