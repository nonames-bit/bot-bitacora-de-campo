"""Tareas asignadas al equipo: quién las asigna, de quién son y a quién avisar.

Jaime (2026-10-10): el dueño (OWNER) y el administrador (ADMIN) asignan
tareas; el operario (TRABAJADOR) no asigna, solo completa las suyas y manda
la foto como evidencia. La tabla es ``recordatorios_programados`` (la misma de
/programar en Telegram y del Despacho Matutino).
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

logger = logging.getLogger("src.pwa.app")

ROLES_ASIGNAN = ("OWNER", "ADMIN")

# Tareas viejas guardadas solo con un nombre genérico (antes "Asignar a" era
# texto libre y el valor por defecto era "Encargado"): son del equipo de
# campo, así que las ve cualquier operario.
_NOMBRES_GENERICOS_CAMPO = {
    "", "equipo", "todos", "todo el equipo", "trabajador", "trabajadores",
    "operario", "operarios", "mayordomo", "encargado",
}


def puede_asignar(rol: Optional[str]) -> bool:
    return str(rol or "").upper() in ROLES_ASIGNAN


def nombre_usuario(u: dict) -> str:
    return str(u.get("nombre") or u.get("username") or "").strip()


def resolver_asignado(usuarios: Iterable[dict], asignado_a: Any,
                      asignado_a_id: Any) -> tuple[Optional[str], Optional[int]]:
    """Devuelve (nombre, user_id) del responsable.

    Prefiere el id que manda la lista de la PWA; si solo llega un nombre
    (Telegram, cola offline vieja) lo busca entre los usuarios. Si no es
    nadie del equipo, guarda el nombre tal cual y sin id."""
    usuarios = list(usuarios or [])
    try:
        uid = int(asignado_a_id) if asignado_a_id not in (None, "") else None
    except (TypeError, ValueError):
        uid = None
    if uid is not None:
        for u in usuarios:
            if u.get("user_id") == uid:
                return nombre_usuario(u) or str(asignado_a or "").strip() or None, uid
    nombre = str(asignado_a or "").strip()
    if nombre:
        for u in usuarios:
            if nombre_usuario(u).lower() == nombre.lower():
                return nombre_usuario(u), u.get("user_id")
    return nombre or None, None


def es_tarea_de(tarea: dict, uid: Any, nombre: Any) -> bool:
    """¿Esta tarea le toca a esta persona?"""
    asig_id = tarea.get("asignado_a_id")
    if asig_id not in (None, ""):
        try:
            return int(asig_id) == int(uid)
        except (TypeError, ValueError):
            return False
    asig = str(tarea.get("asignado_a") or "").strip().lower()
    if asig in _NOMBRES_GENERICOS_CAMPO:
        return True
    return bool(nombre) and asig == str(nombre).strip().lower()


def avisar(db, titulo: str, cuerpo: str, user_ids: list, url: str = "/?v=captura") -> None:
    """Notificación al celular de esas personas. Nunca falla: sin llaves
    VAPID o sin suscripción simplemente no llega."""
    ids = [i for i in (user_ids or []) if i is not None]
    if not ids:
        return
    try:
        try:
            from ..server.push_sender import enviar_push
        except (ImportError, ValueError):
            from src.server.push_sender import enviar_push  # type: ignore
        enviar_push(db, titulo=titulo, cuerpo=cuerpo[:160], url=url,
                    tag="tarea-asignada", user_ids=ids)
    except Exception:
        logger.exception("No se pudo enviar el aviso de la tarea")
