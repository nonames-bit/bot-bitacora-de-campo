"""Genera el par de llaves VAPID para las notificaciones push, listas para .env.

Uso (una sola vez, en el servidor):
    docker compose run --rm --no-deps app python scripts/generar_vapid.py

Imprime VAPID_PUBLIC_KEY y VAPID_PRIVATE_KEY en base64url (el formato que
esperan el navegador y pywebpush). Cópielas al .env y reinicie:
    docker compose up -d
NO las regenere sin motivo: invalida las suscripciones de todos los celulares
(cada uno tendría que tocar "Activar" otra vez).
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid01


def _b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def generar() -> tuple[str, str]:
    v = Vapid01()
    v.generate_keys()
    publica = _b64url(v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
    privada = _b64url(v.private_key.private_numbers().private_value.to_bytes(32, "big"))
    return publica, privada


if __name__ == "__main__":
    pub, priv = generar()
    print(f"VAPID_PUBLIC_KEY={pub}")
    print(f"VAPID_PRIVATE_KEY={priv}")
    print("VAPID_CLAIMS_EMAIL=su_correo@ejemplo.com")
