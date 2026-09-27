"""Login con huella / Face ID (WebAuthn) para la PWA.

Encapsula el uso de ``py_webauthn`` con **import perezoso**: si la librería no
está instalada en producción, ``disponible()`` devuelve False y los endpoints
responden 503 "Biometría no disponible", sin tumbar el resto de la PWA.

El servidor nunca ve la huella: solo guarda la clave pública del dispositivo
(``webauthn_credenciales``) y verifica la firma de cada autenticación.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import secrets
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:  # import perezoso-tolerante: la PWA debe seguir viva sin esta lib
    from webauthn import (
        generate_authentication_options,
        generate_registration_options,
        options_to_json,
        verify_authentication_response,
        verify_registration_response,
    )
    from webauthn.helpers.structs import (
        AttestationConveyancePreference,
        AuthenticatorAttachment,
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        PublicKeyCredentialType,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    WEBAUTHN_OK = True
    WEBAUTHN_ERROR = ""
except Exception as _e:  # pragma: no cover - depende del entorno
    WEBAUTHN_OK = False
    WEBAUTHN_ERROR = str(_e)
    logger.info("py_webauthn no disponible: %s", _e)

TIMEOUT_MS = 60_000
CHALLENGE_MAX_EDAD_SEG = 300
MAX_CREDENCIALES_POR_USUARIO = 10


def disponible() -> bool:
    """True si la librería WebAuthn está instalada y usable."""
    return WEBAUTHN_OK


# --------------------------------------------------------------------------- #
# base64url (WebAuthn transporta binario como base64url sin padding)
# --------------------------------------------------------------------------- #
def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(bytes(data)).rstrip(b"=").decode("ascii")


def b64url_decode(texto: str) -> bytes:
    s = str(texto or "").strip()
    if not s:
        return b""
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def nuevo_challenge() -> bytes:
    """32 bytes aleatorios (CSPRNG) como challenge."""
    return secrets.token_bytes(32)


# --------------------------------------------------------------------------- #
# Configuración RP (con override por entorno para producción)
# --------------------------------------------------------------------------- #
def rp_config(host: str, scheme: str = "https") -> tuple[str, str, str]:
    """Devuelve ``(rp_id, rp_name, origin)``.

    Por defecto se deriva del host de la request (funciona en producción y en
    ``http://localhost``, que WebAuthn acepta como contexto seguro). Se puede
    forzar con ``WEBAUTHN_RP_ID``, ``WEBAUTHN_RP_NAME`` y ``WEBAUTHN_ORIGIN``.
    """
    host_limpio = (host or "").split(",")[0].strip()
    host_sin_puerto = host_limpio.split(":")[0]
    rp_id = (os.getenv("WEBAUTHN_RP_ID") or host_sin_puerto).strip()
    rp_name = (os.getenv("WEBAUTHN_RP_NAME") or "Bitácora Ganadería JA").strip()
    origin = (os.getenv("WEBAUTHN_ORIGIN") or "").strip() or f"{scheme}://{host_limpio}"
    return rp_id, rp_name, origin


# --------------------------------------------------------------------------- #
# Opciones (lo que se le manda al navegador)
# --------------------------------------------------------------------------- #
def opciones_registro(*, rp_id: str, rp_name: str, user_id: str, user_name: str,
                      user_display_name: str, challenge: bytes,
                      excluir_ids: Optional[list[str]] = None) -> dict[str, Any]:
    """Opciones de ``navigator.credentials.create`` (alta de huella)."""
    seleccion = AuthenticatorSelectionCriteria(
        authenticator_attachment=AuthenticatorAttachment.PLATFORM,
        resident_key=ResidentKeyRequirement.PREFERRED,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    excluir = [
        PublicKeyCredentialDescriptor(
            id=b64url_decode(cid), type=PublicKeyCredentialType.PUBLIC_KEY
        )
        for cid in (excluir_ids or []) if cid
    ]
    opciones = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=str(user_id).encode("utf-8"),
        user_name=user_name or str(user_id),
        user_display_name=user_display_name or user_name or str(user_id),
        challenge=challenge,
        timeout=TIMEOUT_MS,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=seleccion,
        exclude_credentials=excluir or None,
    )
    return json.loads(options_to_json(opciones))


def opciones_login(*, rp_id: str, challenge: bytes) -> dict[str, Any]:
    """Opciones de ``navigator.credentials.get`` (login con huella).

    Credenciales *descubribles* (``allow_credentials`` vacío): el dispositivo
    elige la credencial y el servidor la identifica por su id.
    """
    opciones = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge,
        timeout=TIMEOUT_MS,
        user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=[],
    )
    return json.loads(options_to_json(opciones))


# --------------------------------------------------------------------------- #
# Verificación (lo que devuelve el navegador)
# --------------------------------------------------------------------------- #
def verificar_registro(*, credencial: dict, challenge: bytes, rp_id: str,
                       origin: str) -> Any:
    return verify_registration_response(
        credential=credencial,
        expected_challenge=challenge,
        expected_rp_id=rp_id,
        expected_origin=origin,
        require_user_verification=True,
    )


def verificar_login(*, credencial: dict, challenge: bytes, rp_id: str, origin: str,
                    clave_publica: bytes, sign_count: int) -> Any:
    return verify_authentication_response(
        credential=credencial,
        expected_challenge=challenge,
        expected_rp_id=rp_id,
        expected_origin=origin,
        credential_public_key=clave_publica,
        credential_current_sign_count=int(sign_count or 0),
        require_user_verification=True,
    )
