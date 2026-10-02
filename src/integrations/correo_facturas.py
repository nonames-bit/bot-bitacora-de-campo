"""Correo de facturas de la finca: lee las facturas que llegan por email.

El dueño reenvía (o pide a los proveedores que envíen) las facturas
electrónicas a un correo propio de la finca. Cada cierto tiempo
``scripts/programador.py`` llama a ``revisar_correo``: por cada correo nuevo
toma el PDF (suelto o dentro del .zip de la factura electrónica DIAN) o la
foto adjunta, la lee con la misma IA de "Leer Factura con IA" y deja el gasto
en la bandeja "Por revisar" para que un OWNER/ADMIN lo apruebe con un toque.
Nada entra a Finanzas sin esa aprobación: cualquiera puede escribirle a ese
correo.

Configuración (.env del servidor; sin usuario y clave no hace nada):

- FACTURAS_IMAP_USUARIO   correo de la finca (ej. facturas.finca@gmail.com)
- FACTURAS_IMAP_CLAVE     clave de aplicación del correo (no la normal)
- FACTURAS_IMAP_HOST      servidor IMAP (por defecto imap.gmail.com)
- FACTURAS_IMAP_CARPETA   carpeta a revisar (por defecto INBOX)
"""
from __future__ import annotations

import email
import imaplib
import io
import logging
import os
import re
import time
import uuid
import zipfile
from datetime import date
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr
from typing import Any, Callable, Optional

logger = logging.getLogger("bitacora.correo_facturas")

NOMBRE_REMITENTE = "Correo de facturas"
MAX_CORREOS_POR_VUELTA = 10
MAX_ADJUNTO_BYTES = 10 * 1024 * 1024
_EXT_IMAGEN = (".jpg", ".jpeg", ".png", ".webp")


def configurado() -> bool:
    """True si el .env trae usuario y clave reales (no los de ejemplo)."""
    valores = [os.getenv(k, "").strip() for k in ("FACTURAS_IMAP_USUARIO", "FACTURAS_IMAP_CLAVE")]
    return all(v and not re.match(r"^(pegar|cambie)_", v) for v in valores)


def _conectar_imap() -> imaplib.IMAP4:
    host = os.getenv("FACTURAS_IMAP_HOST", "").strip() or "imap.gmail.com"
    imap = imaplib.IMAP4_SSL(host, timeout=60)
    imap.login(os.environ["FACTURAS_IMAP_USUARIO"].strip(), os.environ["FACTURAS_IMAP_CLAVE"].strip())
    return imap


def _texto_cabecera(valor: Optional[str]) -> str:
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor))).strip()
    except Exception:
        return str(valor).strip()


def documentos_de_correo(msg: Message) -> list[tuple[str, bytes]]:
    """[(nombre, bytes)] de las facturas adjuntas: cada PDF (también los que
    vienen dentro de un .zip) y, si no hay ningún PDF, las fotos."""
    pdfs: list[tuple[str, bytes]] = []
    fotos: list[tuple[str, bytes]] = []
    for parte in msg.walk():
        if parte.is_multipart():
            continue
        nombre = _texto_cabecera(parte.get_filename()) or ""
        tipo = (parte.get_content_type() or "").lower()
        datos = parte.get_payload(decode=True) or b""
        if not datos or len(datos) > MAX_ADJUNTO_BYTES:
            continue
        nombre_min = nombre.lower()
        if tipo == "application/pdf" or nombre_min.endswith(".pdf"):
            pdfs.append((nombre or "factura.pdf", datos))
        elif tipo in ("application/zip", "application/x-zip-compressed") or nombre_min.endswith(".zip"):
            pdfs.extend(_pdfs_de_zip(datos))
        elif tipo.startswith("image/") and (nombre_min.endswith(_EXT_IMAGEN) or not nombre):
            fotos.append((nombre or "factura.jpg", datos))
    return pdfs or fotos


def _pdfs_de_zip(datos: bytes) -> list[tuple[str, bytes]]:
    """La factura electrónica DIAN llega como .zip con el PDF y el XML."""
    salida = []
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as zf:
            for info in zf.infolist()[:20]:
                if info.filename.lower().endswith(".pdf") and 0 < info.file_size <= MAX_ADJUNTO_BYTES:
                    salida.append((os.path.basename(info.filename), zf.read(info)))
    except (zipfile.BadZipFile, OSError, RuntimeError):
        logger.warning("Adjunto .zip ilegible en el correo de facturas")
    return salida


def _ya_procesado(db, message_id: str) -> bool:
    if not message_id:
        return False
    fila = db.query_one(
        "SELECT 1 AS ok FROM registros_pendientes WHERE canal = 'correo' AND datos_json LIKE ? LIMIT 1",
        (f'%"correo_id": {_json_str(message_id)}%',),
    )
    return bool(fila)


def _json_str(valor: str) -> str:
    import json
    return json.dumps(valor, ensure_ascii=False)


def _guardar_documento(db, raw: bytes, media_dir: str, concepto: str, fecha: str) -> str:
    """Guarda el PDF/foto en media/ con prefijo factura_ (solo OWNER/ADMIN lo
    ven en la PWA) y lo registra en fotos. Devuelve la ruta relativa."""
    ext = "pdf" if raw.startswith(b"%PDF") else "jpg"
    os.makedirs(media_dir, exist_ok=True)
    fname = f"factura_correo_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
    with open(os.path.join(media_dir, fname), "wb") as f:
        f.write(raw)
    ruta_rel = f"media/{fname}"
    db.registrar_foto(ruta=ruta_rel, animal_tag=None, fecha=fecha,
                      caption=f"Factura/Recibo: {concepto}".strip(),
                      notas="Llegó al correo de facturas de la finca.")
    return ruta_rel


def payload_gasto(res: dict, *, foto_ruta: str, remitente: str, asunto: str, correo_id: str) -> dict:
    """Evento "gasto" de /api/sync con lo leído, listo para la bandeja."""
    desglose = [g for g in (res.get("desglose") or []) if (g.get("monto") or 0) > 0]
    datos: dict[str, Any] = {
        "tipo_finanza": "EGRESO",
        "categoria": res.get("categoria_sugerida") or "OTRO_EGRESO",
        "concepto": res.get("concepto") or None,
        "monto": res.get("monto_total"),
        "contraparte": res.get("proveedor") or None,
        "notas": f"Llegó al correo de facturas: {asunto or 'sin asunto'} ({remitente or 'remitente desconocido'}).",
        "foto_ruta": foto_ruta,
        "correo_id": correo_id,
    }
    if len(desglose) > 1:
        datos["desglose"] = desglose
    return datos


def procesar_mensaje(db, msg: Message, *, media_dir: str, analizar: Callable[..., dict],
                     users_file: Optional[str] = None) -> tuple[int, bool]:
    """Lee las facturas de un correo y las deja por revisar.
    Devuelve (facturas puestas en revisión, se_puede_marcar_leido). Si la IA
    falló (sin red o sin llaves) el correo queda sin leer para reintentar."""
    from ..engine.revision import poner_en_revision

    correo_id = (msg.get("Message-ID") or "").strip()
    if _ya_procesado(db, correo_id):
        return 0, True
    remitente = parseaddr(_texto_cabecera(msg.get("From")))[1]
    asunto = _texto_cabecera(msg.get("Subject"))[:150]
    puestas = 0
    for i, (_nombre, raw) in enumerate(documentos_de_correo(msg)):
        res = analizar(raw, date.today().isoformat())
        if not res.get("ok"):
            logger.warning("No se pudo leer una factura del correo (%s): %s", asunto, res.get("error"))
            return puestas, False
        if not res.get("es_factura") or res.get("tipo") != "EGRESO" or not res.get("monto_total"):
            continue
        fecha = res.get("fecha") or date.today().isoformat()
        foto_ruta = _guardar_documento(db, raw, media_dir, res.get("concepto") or "", fecha)
        datos = payload_gasto(res, foto_ruta=foto_ruta, remitente=remitente, asunto=asunto,
                              correo_id=f"{correo_id}#{i}" if i else correo_id)
        poner_en_revision(db, origen="app", tipo="gasto", datos=datos, fecha=fecha,
                          registrado_por=None, registrado_por_nombre=NOMBRE_REMITENTE,
                          canal="correo", users_file=users_file)
        puestas += 1
    return puestas, True


def revisar_correo(db, *, media_dir: str = "media", users_file: Optional[str] = None,
                   conectar: Callable[[], Any] = _conectar_imap,
                   analizar: Optional[Callable[..., dict]] = None) -> int:
    """Revisa los correos no leídos y deja sus facturas por revisar.
    Devuelve cuántas facturas quedaron en la bandeja."""
    if analizar is None:
        from ..vision.recibo_gasto_parser import analizar_factura_gasto as analizar
    carpeta = os.getenv("FACTURAS_IMAP_CARPETA", "").strip() or "INBOX"
    imap = conectar()
    total = 0
    try:
        imap.select(carpeta)
        estado, datos = imap.search(None, "UNSEEN")
        if estado != "OK":
            return 0
        ids = (datos[0] or b"").split()[:MAX_CORREOS_POR_VUELTA]
        for num in ids:
            # BODY.PEEK no marca el correo como leído hasta que se procese bien.
            estado, partes = imap.fetch(num, "(BODY.PEEK[])")
            crudo = next((p[1] for p in partes or [] if isinstance(p, tuple)), None)
            if estado != "OK" or not crudo:
                continue
            try:
                puestas, marcar = procesar_mensaje(db, email.message_from_bytes(crudo), media_dir=media_dir,
                                                   analizar=analizar, users_file=users_file)
            except Exception:
                logger.exception("Falló un correo de facturas; se reintenta en la próxima vuelta")
                continue
            total += puestas
            if marcar:
                imap.store(num, "+FLAGS", "\\Seen")
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return total

