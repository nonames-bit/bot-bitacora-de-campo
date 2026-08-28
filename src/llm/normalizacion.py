"""Normalización de tags de animales compartida por los agentes de dominio."""
from __future__ import annotations

import re
from typing import Optional

from ..utils import normalizar


def normalizar_tag(tag_raw: Optional[str]) -> Optional[str]:
    """Normaliza un tag de animal devuelto por el LLM (ej. 'la 47' -> '47')."""
    if not tag_raw:
        return None
    t = str(tag_raw).strip()
    if t.lower() in ("null", "none", "", "no aplica", "n/a"):
        return None
    t = re.sub(r"^(?:la|el|vaca|animal|arete|tag|nro|numero)\s+", "", t, flags=re.IGNORECASE).strip()
    t = normalizar(t)
    return t or None
