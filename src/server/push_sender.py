"""Envío de Web Push real (VAPID) a los navegadores suscritos en
``push_suscripciones``.

Antes de este módulo no existía ningún envío real: el frontend nunca
llamaba a ``pushManager.subscribe()`` (no había llave VAPID con qué), así
que la tabla solo guardaba endpoints de relleno (``pwa-local://...``) y
las "notificaciones" solo se mostraban localmente mientras la pestaña
seguía abierta. Con ``VAPID_PUBLIC_KEY``/``VAPID_PRIVATE_KEY`` configuradas
y el frontend suscribiéndose de verdad, este módulo entrega la notificación
aunque el navegador esté cerrado (Web Push estándar).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("bitacora.push_sender")

try:
    from pywebpush import WebPushException, webpush
except ImportError:  # pywebpush es una dependencia opcional en dev sin .venv actualizado
    webpush = None  # type: ignore[assignment]

    class WebPushException(Exception):  # type: ignore[no-redef]
        response = None


def vapid_configurado() -> bool:
    """True si hay llaves VAPID y pywebpush disponible para enviar de verdad."""
    return bool(webpush is not None and os.getenv("VAPID_PRIVATE_KEY") and os.getenv("VAPID_CLAIMS_EMAIL"))


def enviar_push(
    db,
    titulo: str,
    cuerpo: str,
    url: str = "/",
    tag: str = "bitacora-push",
    icono: str = "/static/icon-192.png",
    excluir_user_id: Optional[Any] = None,
) -> dict[str, int]:
    """Envía una notificación Web Push a todos los suscriptores guardados.

    ``excluir_user_id``: no notificar al propio autor del evento (ej. quien
    escribió el mensaje de chat no necesita que le avisen de su propio
    mensaje). Nunca lanza -- si pywebpush no está instalado o faltan las
    llaves VAPID, registra el aviso en el log y devuelve un resumen en
    ceros, para que el llamador (ej. el endpoint de chat) no falle por
    esto. Limpia automáticamente las suscripciones que el push service
    reporta como vencidas (404/410 Gone), para no reintentar sobre
    endpoints muertos en cada mensaje nuevo.
    """
    resumen = {"enviados": 0, "fallidos": 0, "vencidas_limpiadas": 0}

    if not vapid_configurado():
        logger.debug("enviar_push: pywebpush no instalado o VAPID sin configurar; se omite el envío.")
        return resumen

    priv = os.getenv("VAPID_PRIVATE_KEY", "")
    email = os.getenv("VAPID_CLAIMS_EMAIL", "")
    payload = json.dumps({"titulo": titulo, "cuerpo": cuerpo, "url": url, "tag": tag, "icono": icono})

    try:
        suscripciones = db.listar_push_suscripciones(excluir_user_id=excluir_user_id)
    except Exception:
        logger.exception("enviar_push: no se pudo leer push_suscripciones")
        return resumen

    for fila in suscripciones:
        endpoint = fila.get("endpoint") or ""
        p256dh = fila.get("p256dh")
        auth = fila.get("auth")
        if not endpoint.startswith("http") or not p256dh or not auth:
            # Endpoints de relleno (pwa-local://...) de antes de que existiera
            # una suscripción real, o filas incompletas: no hay a dónde enviar.
            continue
        sub_info = {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
        try:
            webpush(
                subscription_info=sub_info,
                data=payload,
                vapid_private_key=priv,
                vapid_claims={"sub": f"mailto:{email}"},
            )
            resumen["enviados"] += 1
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                try:
                    db.eliminar_push_suscripcion(endpoint)
                    resumen["vencidas_limpiadas"] += 1
                except Exception:
                    logger.exception("enviar_push: no se pudo limpiar suscripción vencida")
            else:
                resumen["fallidos"] += 1
                logger.warning("enviar_push: fallo enviando a %s...: %s", endpoint[:40], e)
        except Exception as e:
            resumen["fallidos"] += 1
            logger.warning("enviar_push: error inesperado: %s", e)

    return resumen
