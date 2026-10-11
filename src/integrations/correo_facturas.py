"""Correo de facturas de la finca: lee las facturas que llegan por email.

El dueño reenvía (o pide a los proveedores que envíen) las facturas
electrónicas a un correo propio de la finca. Cada cierto tiempo
``scripts/programador.py`` llama a ``revisar_correo``: por cada correo nuevo
toma el PDF (suelto o dentro del .zip de la factura electrónica DIAN) o la
foto adjunta, la lee con la misma IA de "Leer Factura con IA" y deja el gasto
en la bandeja "Por revisar" para que un OWNER/ADMIN lo apruebe con un toque.
Nada entra a Finanzas sin esa aprobación: cualquiera puede escribirle a ese
correo.

Configuración: el dueño pega el correo y la contraseña de aplicación en la
PWA (Sistema → Correo, solo OWNER) y quedan en ``data/correo_facturas.json``
junto a la base (permiso 600; no va a la nube con las copias). Si ese archivo
no existe se usan las variables del .env del servidor:

- FACTURAS_IMAP_USUARIO   correo de la finca (ej. facturas.finca@gmail.com)
- FACTURAS_IMAP_CLAVE     clave de aplicación del correo (no la normal)
- FACTURAS_IMAP_HOST      servidor IMAP (por defecto imap.gmail.com)
- FACTURAS_IMAP_CARPETA   carpeta a revisar (por defecto INBOX)

Cada revisión deja su resultado en ``data/correo_facturas_estado.json`` para
que la PWA muestre cuándo se revisó por última vez y si hubo error.
"""
from __future__ import annotations

import email
import imaplib
import io
import json
import logging
import os
import re
import time
import uuid
import zipfile
from datetime import date, datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr
from typing import Any, Callable, Optional

logger = logging.getLogger("bitacora.correo_facturas")

NOMBRE_REMITENTE = "Correo de facturas"
MAX_CORREOS_POR_VUELTA = 10
MAX_ADJUNTO_BYTES = 10 * 1024 * 1024
_EXT_IMAGEN = (".jpg", ".jpeg", ".png", ".webp")


def _carpeta_datos() -> str:
    """La carpeta de la base (data/ en Docker), compartida por app y tareas."""
    db = os.getenv("BITACORA_DB", "").strip() or os.path.join("data", "bitacora.db")
    return os.path.dirname(os.path.abspath(db))


def ruta_ajustes() -> str:
    return os.getenv("FACTURAS_CONFIG_FILE", "").strip() or os.path.join(_carpeta_datos(), "correo_facturas.json")


def ruta_estado() -> str:
    return os.path.join(os.path.dirname(ruta_ajustes()), "correo_facturas_estado.json")


def _leer_json(ruta: str) -> dict:
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _escribir_json(ruta: str, datos: dict, privado: bool = False) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = f"{ruta}.{uuid.uuid4().hex[:6]}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if privado else 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def _es_real(valor: str) -> bool:
    return bool(valor) and not re.match(r"^(pegar|cambie)_", valor)


def limpiar_clave(clave: str) -> str:
    """Google muestra la contraseña de aplicación en grupos ("abcd efgh ...")."""
    return re.sub(r"\s+", "", clave or "")


def credenciales() -> Optional[dict]:
    """{usuario, clave, host, origen} con lo guardado en la app o, si no hay,
    con el .env. None si falta el usuario o la clave."""
    guardado = _leer_json(ruta_ajustes())
    usuario = str(guardado.get("usuario") or "").strip()
    clave = limpiar_clave(str(guardado.get("clave") or ""))
    if usuario and clave:
        host = str(guardado.get("host") or "").strip()
        origen = "app"
    else:
        usuario = os.getenv("FACTURAS_IMAP_USUARIO", "").strip()
        clave = limpiar_clave(os.getenv("FACTURAS_IMAP_CLAVE", ""))
        host = os.getenv("FACTURAS_IMAP_HOST", "").strip()
        origen = "servidor"
    if not (_es_real(usuario) and _es_real(clave)):
        return None
    return {"usuario": usuario, "clave": clave, "host": host or "imap.gmail.com", "origen": origen}


def configurado() -> bool:
    """True si hay usuario y clave reales (de la app o del .env)."""
    return credenciales() is not None


def guardar_ajustes(usuario: str, clave: str) -> None:
    _escribir_json(ruta_ajustes(), {"usuario": usuario.strip(), "clave": limpiar_clave(clave),
                                    "guardado_en": datetime.now().isoformat(timespec="seconds")},
                   privado=True)


def borrar_ajustes() -> None:
    for ruta in (ruta_ajustes(), ruta_estado()):
        try:
            os.remove(ruta)
        except FileNotFoundError:
            pass


def leer_estado() -> dict:
    return _leer_json(ruta_estado())


def anotar_estado(ok: bool, *, facturas: int = 0, error: str = "", correos: Optional[list] = None) -> None:
    """Guarda el resultado de una revisión. Los últimos correos leídos se
    conservan aunque en esta vuelta no haya llegado nada nuevo."""
    anteriores = leer_estado().get("correos") or []
    try:
        _escribir_json(ruta_estado(), {"revisado_en": datetime.now().isoformat(timespec="seconds"),
                                       "ok": ok, "facturas": facturas, "error": error,
                                       "correos": ((correos or []) + anteriores)[:5]})
    except OSError:
        logger.warning("No se pudo guardar el estado del correo de facturas")


def explicar_error(exc: BaseException) -> str:
    """El error de IMAP en palabras para el dueño."""
    texto = str(exc)
    if isinstance(exc, imaplib.IMAP4.error) and re.search(r"AUTHENTICATIONFAILED|Invalid credentials|LOGIN failed",
                                                         texto, re.IGNORECASE):
        return ("Gmail no aceptó el correo o la clave. Usa la contraseña de aplicación de 16 letras "
                "(no la clave normal) y revisa que la verificación en 2 pasos esté activa.")
    if isinstance(exc, imaplib.IMAP4.error) and "IMAP" in texto.upper() and "disabled" in texto.lower():
        return "El correo tiene apagado el acceso IMAP. Actívalo en Gmail → Configuración → Reenvío y POP/IMAP."
    if isinstance(exc, (OSError, TimeoutError)):
        return "No hubo conexión con el servidor del correo. Intenta de nuevo en un rato."
    return f"El correo respondió con un error: {texto[:200]}"


def _conectar_imap(cred: Optional[dict] = None) -> imaplib.IMAP4:
    cred = cred or credenciales()
    if not cred:
        raise RuntimeError("El correo de facturas no está configurado.")
    imap = imaplib.IMAP4_SSL(cred["host"], timeout=60)
    imap.login(cred["usuario"], cred["clave"])
    return imap


def probar_conexion(usuario: str, clave: str, host: str = "imap.gmail.com",
                    conectar: Optional[Callable[[dict], Any]] = None) -> dict:
    """Entra al buzón y cuenta los correos sin leer. {ok, sin_leer} o {ok: False, error}."""
    cred = {"usuario": usuario.strip(), "clave": limpiar_clave(clave), "host": host or "imap.gmail.com"}
    try:
        imap = (conectar or _conectar_imap)(cred)
    except Exception as e:  # noqa: BLE001 - se le explica al dueño
        return {"ok": False, "error": explicar_error(e)}
    try:
        carpeta = os.getenv("FACTURAS_IMAP_CARPETA", "").strip() or "INBOX"
        estado, _ = imap.select(carpeta, readonly=True)
        if estado != "OK":
            return {"ok": False, "error": f"No se encontró la carpeta {carpeta} en el correo."}
        estado, datos = imap.search(None, "UNSEEN")
        sin_leer = len((datos[0] or b"").split()) if estado == "OK" and datos else 0
        return {"ok": True, "sin_leer": sin_leer}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": explicar_error(e)}
    finally:
        try:
            imap.logout()
        except Exception:
            pass


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
                     users_file: Optional[str] = None) -> dict:
    """Lee las facturas de un correo y las deja por revisar.

    Devuelve {asunto, puestas, marcar, resultado, nota}. ``marcar`` dice si el
    correo se puede marcar leído; si la IA falló (sin red o sin llaves) queda
    sin leer para reintentar. ``resultado`` es "por_revisar", "ya_estaba",
    "sin_adjunto", "no_factura" o "error" y ``nota`` lo explica en palabras
    para la pantalla Sistema → Correo.

    Todo lo que llega a este buzón es una compra de la finca, así que una
    "factura de venta" del proveedor (que la IA a veces marca como INGRESO)
    se toma como gasto; igual pasa por la bandeja antes de entrar a Finanzas.
    """
    from ..engine.revision import poner_en_revision

    correo_id = (msg.get("Message-ID") or "").strip()
    asunto = _texto_cabecera(msg.get("Subject"))[:150]
    salida = {"asunto": asunto or "(sin asunto)", "puestas": 0, "marcar": True, "resultado": "", "nota": ""}
    if _ya_procesado(db, correo_id):
        salida.update(resultado="ya_estaba", nota="Ya estaba en Por revisar.")
        return salida
    remitente = parseaddr(_texto_cabecera(msg.get("From")))[1]
    documentos = documentos_de_correo(msg)
    if not documentos:
        salida.update(resultado="sin_adjunto", nota="No trae PDF, .zip ni foto de factura.")
        return salida
    descartes = []
    for i, (_nombre, raw) in enumerate(documentos):
        res = analizar(raw, date.today().isoformat())
        if not res.get("ok"):
            logger.warning("No se pudo leer una factura del correo (%s): %s", asunto, res.get("error"))
            salida.update(marcar=False, resultado="error",
                          nota=f"La IA no pudo leer la factura: {res.get('error') or 'sin detalle'}. "
                               "Se vuelve a intentar en la próxima revisión.")
            return salida
        if not res.get("es_factura"):
            descartes.append("la IA dice que no es una factura")
            continue
        if not res.get("monto_total"):
            descartes.append("no se le encontró el total")
            continue
        res = dict(res, tipo="EGRESO")
        fecha = res.get("fecha") or date.today().isoformat()
        foto_ruta = _guardar_documento(db, raw, media_dir, res.get("concepto") or "", fecha)
        datos = payload_gasto(res, foto_ruta=foto_ruta, remitente=remitente, asunto=asunto,
                              correo_id=f"{correo_id}#{i}" if i else correo_id)
        poner_en_revision(db, origen="app", tipo="gasto", datos=datos, fecha=fecha,
                          registrado_por=None, registrado_por_nombre=NOMBRE_REMITENTE,
                          canal="correo", users_file=users_file)
        salida["puestas"] += 1
    if salida["puestas"]:
        salida.update(resultado="por_revisar", nota="Quedó en Gestión → Por revisar.")
    else:
        salida.update(resultado="no_factura", nota="No se anotó: " + "; ".join(dict.fromkeys(descartes)) + ".")
    return salida


def _criterio_busqueda(dias_atras: Optional[int]) -> str:
    """UNSEEN en la revisión automática. A mano se miran los últimos días
    aunque ya estén leídos (por si el correo se abrió en el celular)."""
    if not dias_atras:
        return "UNSEEN"
    desde = date.fromordinal(date.today().toordinal() - dias_atras)
    meses = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"SINCE {desde.day:02d}-{meses[desde.month - 1]}-{desde.year}"


def revisar_correo_detalle(db, *, media_dir: str = "media", users_file: Optional[str] = None,
                           conectar: Callable[[], Any] = _conectar_imap,
                           analizar: Optional[Callable[..., dict]] = None,
                           dias_atras: Optional[int] = None) -> dict:
    """Revisa el buzón y deja sus facturas por revisar.
    Devuelve {facturas, correos: [lo que pasó con cada correo]}."""
    if analizar is None:
        from ..vision.recibo_gasto_parser import analizar_factura_gasto as analizar
    carpeta = os.getenv("FACTURAS_IMAP_CARPETA", "").strip() or "INBOX"
    imap = conectar()
    total, correos = 0, []
    try:
        imap.select(carpeta)
        estado, datos = imap.search(None, _criterio_busqueda(dias_atras))
        if estado != "OK":
            return {"facturas": 0, "correos": []}
        # Los más nuevos primero cuando se revisa a mano.
        ids = (datos[0] or b"").split()
        ids = (ids[::-1] if dias_atras else ids)[:MAX_CORREOS_POR_VUELTA]
        for num in ids:
            # BODY.PEEK no marca el correo como leído hasta que se procese bien.
            estado, partes = imap.fetch(num, "(BODY.PEEK[])")
            crudo = next((p[1] for p in partes or [] if isinstance(p, tuple)), None)
            if estado != "OK" or not crudo:
                continue
            try:
                r = procesar_mensaje(db, email.message_from_bytes(crudo), media_dir=media_dir,
                                     analizar=analizar, users_file=users_file)
            except Exception as e:  # noqa: BLE001 - se anota y se reintenta
                logger.exception("Falló un correo de facturas; se reintenta en la próxima vuelta")
                r = {"asunto": "(correo)", "puestas": 0, "marcar": False, "resultado": "error",
                     "nota": f"Falló al leerlo ({type(e).__name__}: {str(e)[:120]}). Se reintenta."}
            total += r["puestas"]
            correos.append({k: r[k] for k in ("asunto", "resultado", "nota")})
            if r["marcar"]:
                imap.store(num, "+FLAGS", "\\Seen")
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return {"facturas": total, "correos": correos}


def revisar_correo(db, **kw) -> int:
    """Igual que ``revisar_correo_detalle`` pero solo devuelve cuántas
    facturas quedaron en la bandeja."""
    return revisar_correo_detalle(db, **kw)["facturas"]
