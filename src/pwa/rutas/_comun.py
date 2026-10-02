"""Funciones compartidas por varios módulos de rutas.

``construir(ctx, h)`` las define con el estado de ``crear_app`` y las
agrega a ``h`` antes de registrar las rutas (ver rutas/__init__.py).
"""
from __future__ import annotations

import os
import re
import time
import logging
from typing import Optional
from .. import app as _base
from ..app import (  # helpers de módulo compartidos (ver src/pwa/app.py)
    _es_imagen_valida,
)
from ...vision.recibo_gasto_parser import es_pdf_valido as _pdf_valido

# Mismo logger que src/pwa/app.py: los mensajes salen igual que antes.
logger = logging.getLogger("src.pwa.app")


def construir(ctx, h) -> None:
    pass

    def _guardar_foto_evento(db_inst, payload: dict, tipo: str, fecha: str, uid_user: Optional[int]) -> Optional[int]:
        """Procesa y almacena una foto adjunta (opcional) enviada en base64 desde la captura rápida."""
        foto_b64 = payload.get("foto_base64")
        if not foto_b64 or not isinstance(foto_b64, str):
            return None
        try:
            import base64
            import uuid

            if "," in foto_b64:
                foto_b64 = foto_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(foto_b64)
            # Un gasto puede traer el PDF de la factura electrónica en vez de foto.
            es_pdf = tipo == "gasto" and _pdf_valido(raw_bytes)
            if not raw_bytes or not (es_pdf or _es_imagen_valida(raw_bytes)):
                return None

            media_dir_abs = os.path.join(_base.RAIZ_PROYECTO, _base.MEDIA_DIR_DEFAULT) if not os.path.isabs(_base.MEDIA_DIR_DEFAULT) else _base.MEDIA_DIR_DEFAULT
            os.makedirs(media_dir_abs, exist_ok=True)

            # Determinar el tag del animal involucrado
            tag_asoc = None
            if tipo == "parto":
                tag_asoc = payload.get("id_cria_tag") or payload.get("vaca_tag") or payload.get("tag")
            elif tipo == "destete":
                tag_asoc = payload.get("cria_tag") or payload.get("animal_tag") or payload.get("tag")
            elif tipo in ("tratamiento", "muerte", "pesaje", "traslado"):
                tag_asoc = payload.get("animal_tag") or payload.get("tag")
            elif tipo in ("celo", "servicio"):
                tag_asoc = payload.get("vaca_tag") or payload.get("tag")
            else:
                tag_asoc = payload.get("animal_tag") or payload.get("vaca_tag") or payload.get("tag")

            tag_clean = re.sub(r"[^A-Za-z0-9_-]+", "_", str(tag_asoc or "campo"))
            ts = int(time.time())
            rnd = uuid.uuid4().hex[:6]
            # Prefijo gasto_ en facturas: en /media solo las ven OWNER/ADMIN.
            fname = (f"gasto_{tag_clean}_{ts}_{rnd}.pdf" if es_pdf
                     else f"cap_{tipo}_{tag_clean}_{ts}_{rnd}.jpg")
            dest_file = os.path.join(media_dir_abs, fname)
            with open(dest_file, "wb") as f:
                f.write(raw_bytes)

            ruta_rel = os.path.join("media", fname).replace("\\", "/")
            caption_txt = f"Captura {tipo.capitalize()} · {tag_asoc or ''}".strip()
            if tipo == "parto":
                caption_txt = f"Parto: cría {payload.get('id_cria_tag') or 'S/D'} (madre {payload.get('vaca_tag') or 'S/D'})".strip()
            elif tipo == "tratamiento":
                caption_txt = f"Tratamiento: {payload.get('producto') or ''} ({tag_asoc or ''})".strip()
            elif tipo == "muerte":
                caption_txt = f"Muerte: {payload.get('causa_presunta') or ''} ({tag_asoc or ''})".strip()
            elif tipo == "destete":
                caption_txt = f"Destete: cría {tag_asoc or 'S/D'}".strip()
            elif tipo == "secado":
                caption_txt = f"Secado: {tag_asoc or 'S/D'}".strip()
            elif tipo == "leche":
                litros_str = f"{payload.get('litros')} L" if payload.get("litros") is not None else ""
                caption_txt = f"Recibo/Planilla de Leche: {litros_str} · {fecha}".strip()
            elif tipo == "gasto":
                caption_txt = f"Factura/Recibo: {payload.get('categoria') or ''} · {payload.get('concepto') or ''}".strip(" ·")

            fid = db_inst.registrar_foto(
                ruta=ruta_rel,
                animal_tag=tag_asoc,
                fecha=fecha,
                caption=caption_txt,
                user_id=uid_user,
                notas=f"Captura rápida en campo ({tipo}): {payload.get('notas') or payload.get('diagnostico') or ''}".strip(),
            )

            # Para parto, si se especificaron cría y madre, vincular también a la madre
            if tipo == "parto" and payload.get("id_cria_tag") and payload.get("vaca_tag") and str(payload.get("id_cria_tag")) != str(payload.get("vaca_tag")):
                try:
                    db_inst.registrar_foto(
                        ruta=ruta_rel,
                        animal_tag=payload.get("vaca_tag"),
                        fecha=fecha,
                        caption=caption_txt,
                        user_id=uid_user,
                        notas=f"Parto madre {payload.get('vaca_tag')} de la cría {payload.get('id_cria_tag')}",
                    )
                except Exception:
                    pass

            return fid
        except Exception as err:
            logger.exception("Error al guardar foto adjunta de captura: %s", err)
            return None

    h._guardar_foto_evento = _guardar_foto_evento
