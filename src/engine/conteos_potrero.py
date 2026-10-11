"""Conteos de potrero: registro de auditoría de la pantalla "Contar por
potrero" de la PWA (Jaime, 2026-10-10: "cuando se revisan todos los animales
que quede a una fecha un registro"). Cada conteo guarda quién contó, cuándo,
cuántos animales había en la lista, cuántos vio y qué aretes faltaron.

Llega por /api/sync (tipo ``conteo_potrero``) porque se hace en el potrero,
casi siempre sin señal, y viaja en la cola offline como los demás eventos.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

_MAX_TAGS = 2000


def _lista_tags(valor: Any) -> list[str]:
    if not isinstance(valor, list):
        return []
    tags = []
    for t in valor[:_MAX_TAGS]:
        t = str(t or "").strip()[:40]
        if t:
            tags.append(t)
    return tags


def registrar_conteo(db, payload: dict, fecha: str, registrado_por: Optional[int],
                     registrado_por_nombre: Optional[str]) -> int:
    """Guarda un conteo. Lanza ValueError si los datos no sirven."""
    vistos = _lista_tags(payload.get("vistos"))
    faltantes = _lista_tags(payload.get("faltantes"))
    total = len(vistos) + len(faltantes)
    if total == 0:
        raise ValueError("el conteo no trae animales")
    try:
        potrero_id = int(payload.get("potrero_id"))
    except (TypeError, ValueError):
        potrero_id = None
    nombre = str(payload.get("potrero_nombre") or "").strip()[:120] or None
    hora = str(payload.get("hora") or "").strip()[:5] or None
    notas = str(payload.get("notas") or "").strip()[:500] or None
    return db.execute(
        "INSERT INTO conteos_potrero (fecha, hora, potrero_id, potrero_nombre, total, vistos, faltantes, "
        "vistos_tags, notas, registrado_por, registrado_por_nombre, creado_en) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (fecha, hora, potrero_id, nombre, total, len(vistos), json.dumps(faltantes, ensure_ascii=False),
         json.dumps(vistos, ensure_ascii=False), notas, registrado_por,
         (registrado_por_nombre or "").strip()[:80] or None, datetime.now().isoformat(timespec="seconds")),
    ).lastrowid


def listar_conteos(db, potrero_id: Optional[int] = None, limite: int = 20) -> list[dict]:
    """Últimos conteos, del más reciente al más viejo."""
    limite = max(1, min(int(limite or 20), 200))
    sql = ("SELECT id, fecha, hora, potrero_id, potrero_nombre, total, vistos, faltantes, notas, "
           "registrado_por_nombre FROM conteos_potrero")
    params: tuple = ()
    if potrero_id is not None:
        sql += " WHERE potrero_id = ?"
        params = (potrero_id,)
    sql += " ORDER BY fecha DESC, hora DESC, id DESC LIMIT ?"
    out = []
    for f in db.query(sql, params + (limite,)):
        try:
            faltan = json.loads(f["faltantes"] or "[]")
        except (TypeError, ValueError):
            faltan = []
        out.append({
            "id": f["id"], "fecha": f["fecha"], "hora": f["hora"], "potrero_id": f["potrero_id"],
            "potrero": f["potrero_nombre"], "total": f["total"], "vistos": f["vistos"],
            "faltantes": faltan, "notas": f["notas"], "por": f["registrado_por_nombre"],
        })
    return out
