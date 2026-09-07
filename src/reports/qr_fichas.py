"""Fichas QR por lote/potrero — Fase 7 Etapa A (PLAN_FASE7_PWA.md §3A, tareas A1/A2).

Genera un PDF A4 con 6 tarjetas plastificables por hoja. Cada tarjeta trae:
tag grande, QR (payload ``JA://animal/<tag>`` + URL ``/ficha/<tag>``),
potrero, edad zootécnica, estado repro/retiro y foto mini si existe.

Regla de inventario: toda consulta filtra estrictamente ``estado='ACTIVO'``.
"""
from __future__ import annotations

import os
import re
from datetime import date
from typing import Optional

try:
    from ..db.database import Database
except ImportError:  # ejecución como script: python src/reports/qr_fichas.py
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.db.database import Database  # type: ignore

try:
    from ..engine.query_engine import formatear_edad_zootecnica
except Exception:  # pragma: no cover - fallback sin romper
    formatear_edad_zootecnica = None  # type: ignore

try:
    from ..engine.query_engine import buscar_foto_animal
except Exception:  # pragma: no cover - fallback sin romper
    buscar_foto_animal = None  # type: ignore

try:
    from ..utils import to_date
except Exception:  # pragma: no cover

    def to_date(v):  # type: ignore
        from datetime import datetime as _dt

        if v is None:
            return None
        if isinstance(v, date):
            return v
        try:
            return _dt.fromisoformat(str(v)[:10]).date()
        except Exception:
            return None


from .estilo_ja import (
    COLOR_ALERTA_BG,
    COLOR_ALERTA_TXT,
    COLOR_BORDE_TARJETA,
    COLOR_DESCARTADO,
    COLOR_FONDO_TARJETA,
    COLOR_FOTO_BORDE,
    COLOR_FOTO_PLACEHOLDER,
    COLOR_FOTO_TEXTO,
    COLOR_LINEA,
    COLOR_MARCA,
    COLOR_MARCA_CLARA,
    COLOR_MARCA_HEADER,
    COLOR_MUERTO,
    COLOR_NEGRO,
    COLOR_PIE,
    COLOR_QR_BORDE,
    COLOR_QR_FONDO,
    COLOR_QR_URL,
    COLOR_VENDIDO,
    COLOR_VERDE,
    dibujar_pie,
    dibujar_seccion_hdr,
)

# Alias locales (compatibilidad con código existente de este módulo).
_COLOR_MARCA = COLOR_MARCA
_COLOR_MARCA_CLARA = COLOR_MARCA_CLARA

QR_CACHE_DIR = os.path.join("data", "qr_cache")


def qr_payload(tag: str) -> tuple[str, str]:
    """Devuelve (payload_crudo, url_ficha) para un tag."""
    t = str(tag).strip()
    return f"JA://animal/{t}", f"/ficha/{t}"


def _qr_png_path(tag: str, cache_dir: str = QR_CACHE_DIR) -> Optional[str]:
    """Genera (o reutiliza de cache) el PNG del QR de un tag.

    Si ``qrcode`` no está instalado hace fallback: devuelve None y la tarjeta
    dibuja un recuadro placeholder con el payload en texto (sin romper).
    """
    t = str(tag).strip()
    os.makedirs(cache_dir, exist_ok=True)
    destino = os.path.join(cache_dir, f"{re.sub(r'[^A-Za-z0-9_-]+', '_', t)}.png")
    if os.path.exists(destino):
        return destino
    try:
        import qrcode  # type: ignore
    except Exception:
        return None  # fallback sin romper: placeholder dibujado en el PDF
    try:
        payload, url = qr_payload(t)
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
        qr.add_data(f"{payload}\n{url}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(destino)
        return destino
    except Exception:
        # PIL faltante, disco lleno, etc.: placeholder dibujado en el PDF.
        try:
            if os.path.exists(destino):
                os.remove(destino)
        except Exception:
            pass
        return None


def _edad_str(animal, hoy: date) -> str:
    """Edad zootécnica reusando formatear_edad_zootecnica si existe."""
    f_nac = to_date(animal["fecha_nacimiento"]) if animal["fecha_nacimiento"] else None
    if f_nac is None:
        return "Edad S/D"
    if formatear_edad_zootecnica is not None:
        try:
            return str(formatear_edad_zootecnica(f_nac, hoy))
        except Exception:
            pass
    dias = (hoy - f_nac).days
    if dias < 0:
        return "0 días"
    return f"{dias} días"


def _estado_repro_retiro(db: Database, aid: int, hoy_iso: str) -> str:
    """Estado reproductivo + retiro sanitario resumido (solo lectura)."""
    partes: list[str] = []
    try:
        diag = db.query(
            "SELECT resultado FROM diagnosticos_gestacion WHERE vaca_id = ? ORDER BY fecha DESC, id DESC LIMIT 1",
            (aid,),
        )
        if diag and diag[0]["resultado"]:
            partes.append(str(diag[0]["resultado"]).upper())
        else:
            serv = db.query(
                "SELECT tipo_servicio, fep_calculada FROM servicios WHERE vaca_id = ? ORDER BY fecha DESC LIMIT 1",
                (aid,),
            )
            if serv:
                fep = f" FEP {serv[0]['fep_calculada']}" if serv[0]["fep_calculada"] else ""
                partes.append(f"{(serv[0]['tipo_servicio'] or 'SERVIDA')}{fep}")
            else:
                partes.append("Sin servicio")
    except Exception:
        partes.append("Repro S/D")
    try:
        rets = db.query(
            """SELECT fecha_fin_retiro_leche, fecha_fin_retiro_carne FROM tratamientos
               WHERE animal_id = ? AND ((fecha_fin_retiro_leche IS NOT NULL AND fecha_fin_retiro_leche >= ?)
               OR (fecha_fin_retiro_carne IS NOT NULL AND fecha_fin_retiro_carne >= ?))
               ORDER BY fecha DESC LIMIT 1""",
            (aid, hoy_iso, hoy_iso),
        )
        if rets:
            r = rets[0]
            bits = []
            if r["fecha_fin_retiro_leche"] and r["fecha_fin_retiro_leche"] >= hoy_iso:
                bits.append(f"retiro leche→{r['fecha_fin_retiro_leche']}")
            if r["fecha_fin_retiro_carne"] and r["fecha_fin_retiro_carne"] >= hoy_iso:
                bits.append(f"retiro carne→{r['fecha_fin_retiro_carne']}")
            partes.append("⛔ " + " · ".join(bits) if bits else "Retiro activo")
        else:
            partes.append("✅ Sin retiro")
    except Exception:
        pass
    return " · ".join(partes)


def _potrero_display(db: Database, animal) -> str:
    """Nombre del potrero del animal (columna directa o último traslado)."""
    try:
        pid = animal["potrero_id"]
        if pid is not None:
            p = db.get_potrero(pid)
            if p and (p["nombre"] or p["codigo"]):
                return str(p["nombre"] or p["codigo"])
        ult = db.query_one(
            "SELECT potrero_destino FROM traslados WHERE animal_id = ? ORDER BY fecha DESC, id DESC LIMIT 1",
            (animal["id_animal"],),
        )
        if ult and ult["potrero_destino"] is not None:
            p = db.get_potrero(ult["potrero_destino"])
            if p and (p["nombre"] or p["codigo"]):
                return str(p["nombre"] or p["codigo"])
    except Exception:
        pass
    return "Sin potrero"


def listar_animales_lote(db: Database, filtro: str) -> list:
    """Animales ACTIVOS de un potrero (nombre/código) o lote de traslados.

    Inventario estricto: siempre ``estado='ACTIVO'`` (nunca COALESCE ni sin filtro).
    """
    f = str(filtro or "").strip()
    if not f:
        return []
    # 1) ¿Es potrero? (exacto por codigo/nombre o coincidencia parcial insensible)
    try:
        potreros = db.query("SELECT id, nombre, codigo FROM potreros")
    except Exception:
        potreros = []
    pids: list[int] = []
    f_up = f.upper()
    for p in potreros:
        nom = str(p["nombre"] or "")
        cod = str(p["codigo"] or "")
        if f_up == nom.upper() or f_up == cod.upper() or f_up in nom.upper():
            pids.append(int(p["id"]))
    if pids:
        marks = ",".join("?" for _ in pids)
        por_potrero = db.query(
            f"SELECT * FROM animales WHERE estado = 'ACTIVO' AND potrero_id IN ({marks}) ORDER BY tag",
            tuple(pids),
        )
        ids_tras = db.query(
            f"SELECT DISTINCT animal_id FROM traslados WHERE potrero_destino IN ({marks})",
            tuple(pids),
        )
        ids_set = {r["animal_id"] for r in ids_tras if r["animal_id"] is not None}
        ya = {a["id_animal"] for a in por_potrero}
        extra = []
        if ids_set:
            marks2 = ",".join("?" for _ in ids_set)
            extra = [
                a for a in db.query(
                    f"SELECT * FROM animales WHERE estado = 'ACTIVO' AND id_animal IN ({marks2}) ORDER BY tag",
                    tuple(ids_set),
                )
                if a["id_animal"] not in ya
            ]
        return list(por_potrero) + extra
    # 2) Tratarlo como lote de traslados (columna traslados.lote).
    try:
        filas = db.query(
            "SELECT DISTINCT animal_id FROM traslados WHERE UPPER(lote) = UPPER(?)", (f,)
        )
    except Exception:
        return []
    ids = [r["animal_id"] for r in filas if r["animal_id"] is not None]
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    return db.query(
        f"SELECT * FROM animales WHERE estado = 'ACTIVO' AND id_animal IN ({marks}) ORDER BY tag",
        tuple(ids),
    )


def generar_fichas_lote(
    db: Database,
    filtro: str,
    salida: Optional[str] = None,
    media_dir: str = "media",
    base_url: str = "",
    hoy: Optional[date] = None,
    cache_dir: str = QR_CACHE_DIR,
) -> str:
    """Genera el PDF A4 (6 tarjetas por hoja) del lote/potrero y devuelve su ruta."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    hoy = hoy or date.today()
    hoy_iso = hoy.isoformat()
    animales = listar_animales_lote(db, filtro)
    if not animales:
        raise ValueError(f"Sin animales ACTIVOS para '{filtro}' (potrero o lote).")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(filtro).strip()) or "lote"
    ruta = salida or os.path.join("data", "reportes", f"fichas_qr_{safe}_{hoy_iso}.pdf")
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)

    W, H = A4
    margen, gap = 36, 12
    cw = (W - 2 * margen - gap) / 2
    ch = (H - 2 * margen - 2 * gap) / 3

    c = canvas.Canvas(ruta, pagesize=A4)
    for idx, animal in enumerate(animales):
        pos = idx % 6
        if idx and pos == 0:
            c.showPage()
        col, row = pos % 2, pos // 2
        x0 = margen + col * (cw + gap)
        y0 = H - margen - (row + 1) * ch - row * gap  # esquina inferior
        tag = str(animal["tag"] or animal["id_animal"])
        payload, url = qr_payload(tag)
        potrero = _potrero_display(db, animal)
        edad = _edad_str(animal, hoy)
        estado = _estado_repro_retiro(db, int(animal["id_animal"]), hoy_iso)

        # Marco + franja marca (roundRect como la ficha individual).
        c.setStrokeColor(_COLOR_MARCA)
        c.setLineWidth(1.2)
        c.roundRect(x0, y0, cw, ch, 6, stroke=1, fill=0)
        c.setFillColor(_COLOR_MARCA)
        c.rect(x0 + 1, y0 + ch - 20, cw - 2, 20, stroke=0, fill=1)
        c.setFillColor("white")
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x0 + 6, y0 + ch - 14, "GANADERÍA JA")
        c.setFont("Helvetica", 8)
        c.drawRightString(x0 + cw - 6, y0 + ch - 14, potrero[:32])

        # Tag grande.
        c.setFillColor("black")
        c.setFont("Helvetica-Bold", 20)
        c.drawString(x0 + 8, y0 + ch - 44, tag[:18])

        # QR (cache) o placeholder — mismo tratamiento ficha individual:
        # fondo blanco + borde sutil #DDDDDD.
        from reportlab.lib import colors as _colors_lote
        qx, qy, qs = x0 + 8, y0 + 10, 92
        c.setFillColor(_colors_lote.HexColor("#FFFFFF"))
        c.setStrokeColor(_colors_lote.HexColor(COLOR_QR_BORDE))
        c.setLineWidth(0.8)
        c.rect(qx - 3, qy - 3, qs + 6, qs + 6, fill=1, stroke=1)
        qr_png = _qr_png_path(tag, cache_dir)
        if qr_png and os.path.exists(qr_png):
            try:
                c.drawImage(ImageReader(qr_png), qx, qy, width=qs, height=qs)
            except Exception:
                c.setFillColor(_colors_lote.HexColor(COLOR_QR_FONDO))
                c.rect(qx, qy, qs, qs, fill=1, stroke=0)
                c.setFillColor("black")
                c.setFont("Helvetica", 6)
                c.drawString(qx + 4, qy + qs / 2, payload[:28])
        else:
            c.setFillColor(_colors_lote.HexColor(COLOR_QR_FONDO))
            c.rect(qx, qy, qs, qs, fill=1, stroke=0)
            c.setFillColor("black")
            c.setFont("Helvetica", 6)
            c.drawString(qx + 4, qy + qs / 2, payload[:28])

        # Columna de datos.
        tx = qx + qs + 8
        c.setFillColor("black")
        c.setFont("Helvetica", 9)
        c.drawString(tx, y0 + 92, f"Potrero: {potrero[:26]}")
        c.drawString(tx, y0 + 78, f"Edad: {edad[:30]}")
        c.setFont("Helvetica", 8)
        for i, linea in enumerate([estado[i:i + 42] for i in range(0, len(estado), 42)][:3]):
            c.drawString(tx, y0 + 64 - i * 11, linea[:42])
        c.setFont("Helvetica", 7)
        full_url = f"{base_url.rstrip('/')}{url}" if base_url else url
        c.drawString(tx, y0 + 24, payload[:44])
        c.drawString(tx, y0 + 13, full_url[:44])

        # Foto mini si existe en media/ (contenedor roundRect como la ficha).
        try:
            foto = buscar_foto_animal(db, tag, media_dir=media_dir) if buscar_foto_animal else None
            if foto and os.path.exists(foto):
                fw, fh = 64, 48
                fx, fy = x0 + cw - fw - 6, y0 + ch - 44 - fh
                c.saveState()
                _clip = c.beginPath()
                _clip.roundRect(fx, fy, fw, fh, 4)
                c.clipPath(_clip, stroke=0, fill=0)
                c.drawImage(ImageReader(foto), fx, fy,
                            width=fw, height=fh, preserveAspectRatio=True)
                c.restoreState()
                c.setStrokeColor(_colors_lote.HexColor(COLOR_FOTO_BORDE))
                c.setLineWidth(0.6)
                c.roundRect(fx, fy, fw, fh, 4, stroke=1, fill=0)
        except Exception:
            pass

    # Pie con línea + texto (mismo formato que la ficha individual).
    from reportlab.lib import colors as _colors_pie
    c.setStrokeColor(_colors_pie.HexColor(COLOR_LINEA))
    c.setLineWidth(0.5)
    c.line(margen, margen - 6, W - margen, margen - 6)
    c.setFillColor(_colors_pie.HexColor(COLOR_PIE))
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(W / 2, margen - 18, f"Fichas QR · {filtro} · {len(animales)} animales ACTIVOS · {hoy_iso}")
    c.save()
    return ruta


def generar_ficha_qr_individual(
    db: Database,
    tag: str,
    salida: Optional[str] = None,
    media_dir: str = "media",
    base_url: str = "",
    hoy: Optional[date] = None,
    cache_dir: str = QR_CACHE_DIR,
) -> str:
    """Genera la Ficha Técnica Zootécnica Oficial con Tarjeta QR individual
    (formato apaisado A4, alta densidad de datos) para exportar la ficha de
    UN animal desde la PWA (botón 'Descargar tarjeta QR').

    Incluye identificación completa, categoría SG, potrero, genealogía,
    pesajes y GMD, historial reproductivo, control sanitario de retiros,
    foto y código QR interactivo de alta resolución.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        _TIENE_QR_NATIVO = True
    except Exception:
        _TIENE_QR_NATIVO = False

    try:
        from ..engine.dashboard_data import datos_ficha_animal
    except (ImportError, ValueError):
        from src.engine.dashboard_data import datos_ficha_animal  # type: ignore

    hoy = hoy or date.today()
    hoy_iso = hoy.isoformat()
    tag_clean = str(tag or "").strip()
    aid = db.animal_id(tag_clean)
    if aid is None:
        raise ValueError(f"Sin animal ACTIVO con tag '{tag_clean}'.")
    animal = db.get_animal(aid)
    if animal is None or str(animal["estado"] or "").upper() != "ACTIVO":
        raise ValueError(f"El animal '{tag_clean}' no está ACTIVO.")
    an_tag = str(animal["tag"] or tag_clean)

    ficha = datos_ficha_animal(db, an_tag)
    payload, url = qr_payload(an_tag)
    full_url = f"{base_url.rstrip('/')}{url}" if base_url else url

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", an_tag) or "animal"
    ruta = salida or os.path.join("data", "reportes", f"ficha_qr_{safe}_{hoy_iso}.pdf")
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)

    W, H = landscape(A4)
    c = canvas.Canvas(ruta, pagesize=landscape(A4))
    m = 22
    cw = W - 2 * m
    ch = H - 2 * m
    x0 = m
    y0 = m

    # 1. Borde perimetral exterior
    c.setStrokeColor(colors.HexColor(_COLOR_MARCA))
    c.setLineWidth(1.4)
    c.rect(x0, y0, cw, ch, stroke=1, fill=0)

    # 2. Encabezado corporativo
    h_hdr = 40
    y_hdr = y0 + ch - h_hdr
    c.setFillColor(colors.HexColor(_COLOR_MARCA))
    c.rect(x0, y_hdr, cw, h_hdr, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x0 + 12, y_hdr + 22, "GANADERÍA JA")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x0 + 130, y_hdr + 22, "·  FICHA TÉCNICA ZOOTÉCNICA Y TRAZABILIDAD INDIVIDUAL")

    c.setFont("Helvetica", 8)
    c.drawString(x0 + 12, y_hdr + 9, "BITÁCORA DE CAMPO  |  SISTEMA OFICIAL GANADERÍA JA")

    c.setFont("Helvetica-Bold", 10)
    pot_nom = str(ficha.get("potrero") or "Sin potrero asignado").upper()
    c.drawRightString(x0 + cw - 12, y_hdr + 22, f"POTRERO: {pot_nom[:32]}")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#C8E6C9"))
    c.drawRightString(x0 + cw - 12, y_hdr + 9, f"HATO ACTIVO  |  Emisión: {hoy_iso}")

    # 3. Pie de página
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.setLineWidth(0.5)
    c.line(x0 + 10, y0 + 20, x0 + cw - 10, y0 + 20)
    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 7.5)
    c.drawString(x0 + 12, y0 + 7, "Ganadería JA · Control Zootécnico Integral · Datos sincronizados del hato ganadero")
    c.drawRightString(x0 + cw - 12, y0 + 7, f"ID Sistema: #{aid} · Tag: {an_tag} · Documento Oficial de Campo")

    # 4. Columna Izquierda: Tarjeta de Identificación, QR y Foto
    col_izq_w = 215
    col_izq_x = x0 + 10
    col_izq_y = y0 + 28
    col_izq_h = y_hdr - col_izq_y - 8

    c.setFillColor(colors.HexColor("#F8FAF8"))
    c.setStrokeColor(colors.HexColor("#A4C1A8"))
    c.setLineWidth(1)
    c.roundRect(col_izq_x, col_izq_y, col_izq_w, col_izq_h, 6, fill=1, stroke=1)

    # Tag y Nombre en caja izquierda
    c.setFillColor(colors.HexColor(_COLOR_MARCA))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(col_izq_x + 10, col_izq_y + col_izq_h - 30, f"{an_tag[:14]}")

    nom_txt = str(ficha.get("nombre") or "").strip()
    c.setFont("Helvetica-Bold", 10.5)
    c.setFillColor(colors.HexColor("#1F2D21"))
    c.drawString(col_izq_x + 10, col_izq_y + col_izq_h - 46, f"{nom_txt[:24]}" if nom_txt else "Sin nombre registrado")

    # Generar QR
    qr_size = 142
    qr_x = col_izq_x + (col_izq_w - qr_size) / 2
    qr_y = col_izq_y + col_izq_h - 204

    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#DDDDDD"))
    c.rect(qr_x - 3, qr_y - 3, qr_size + 6, qr_size + 6, fill=1, stroke=1)

    # Dibujar QR (nativo reportlab vector o PNG de fallback)
    qr_dibujado = False
    if _TIENE_QR_NATIVO:
        try:
            target_qr = full_url if full_url.startswith("http") else (f"{base_url.rstrip('/')}/ficha/{an_tag}" if base_url else f"{payload}\n{url}")
            qr_w = QrCodeWidget(target_qr)
            b = qr_w.getBounds()
            bw = b[2] - b[0]
            bh = b[3] - b[1]
            d = Drawing(qr_size, qr_size, transform=[qr_size / bw, 0, 0, qr_size / bh, 0, 0])
            d.add(qr_w)
            renderPDF.draw(d, c, qr_x, qr_y)
            qr_dibujado = True
        except Exception:
            pass

    if not qr_dibujado:
        qr_png = _qr_png_path(an_tag, cache_dir)
        if qr_png and os.path.exists(qr_png):
            try:
                c.drawImage(ImageReader(qr_png), qr_x, qr_y, width=qr_size, height=qr_size)
                qr_dibujado = True
            except Exception:
                pass

    if not qr_dibujado:
        c.setFillColor(colors.HexColor("#EEEEEE"))
        c.rect(qr_x, qr_y, qr_size, qr_size, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#333333"))
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(qr_x + qr_size / 2, qr_y + qr_size / 2, f"QR: {an_tag}")

    # Instrucciones QR
    c.setFillColor(colors.HexColor(_COLOR_MARCA))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(col_izq_x + col_izq_w / 2, qr_y - 12, "Escanee con la cámara del celular")
    c.setFont("Helvetica", 6.8)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawCentredString(col_izq_x + col_izq_w / 2, qr_y - 22, "Abre la ficha interactiva en la PWA")
    c.setFont("Helvetica-Oblique", 6.2)
    c.setFillColor(colors.HexColor("#1F6C9F"))
    c.drawCentredString(col_izq_x + col_izq_w / 2, qr_y - 32, full_url[:42])

    # Foto del animal (si existe) o recuadro
    foto_y = col_izq_y + 10
    foto_h = qr_y - 40 - foto_y
    foto_w = col_izq_w - 20
    foto_x = col_izq_x + 10
    foto_path = buscar_foto_animal(db, an_tag, media_dir=media_dir) if buscar_foto_animal else None
    if foto_path and os.path.exists(foto_path):
        try:
            c.drawImage(ImageReader(foto_path), foto_x, foto_y, width=foto_w, height=foto_h, preserveAspectRatio=True)
        except Exception:
            foto_path = None
    if not foto_path:
        c.setFillColor(colors.HexColor("#F0F3F0"))
        c.setStrokeColor(colors.HexColor("#D0DDD1"))
        c.roundRect(foto_x, foto_y, foto_w, foto_h, 4, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#7A8B7C"))
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(foto_x + foto_w / 2, foto_y + foto_h / 2 + 6, "REGISTRO FOTOGRÁFICO")
        c.setFont("Helvetica", 7)
        c.drawCentredString(foto_x + foto_w / 2, foto_y + foto_h / 2 - 8, f"Categoría: {str(ficha.get('categoria_sg') or 'Bovino')[:26]}")

    # 5. Columna Derecha: 5 Secciones Técnicas Estructuradas
    col_der_x = col_izq_x + col_izq_w + 12
    col_der_w = x0 + cw - 10 - col_der_x
    y_pos = y_hdr - 6
    y_min = y0 + 28  # no invadir el pie de página

    def _trunc(txt: str, n: int) -> str:
        """Trunca con elegancia (elipsis) para no salirse del rectángulo."""
        t = str(txt or "").strip()
        return t if len(t) <= n else t[: max(0, n - 1)].rstrip() + "…"

    def _hay_espacio(necesario: float = 16) -> bool:
        return (y_pos - necesario) >= y_min

    def _dibujar_seccion_hdr(titulo, bg_color=COLOR_MARCA_CLARA, txt_color=COLOR_MARCA):
        nonlocal y_pos
        # Espaciado vertical: evita amontonar secciones cuando hay muchos datos.
        if not _hay_espacio(22):
            return
        dibujar_seccion_hdr(c, col_der_x, y_pos - 16, col_der_w, titulo,
                            bg_color=bg_color, txt_color=txt_color)
        y_pos -= 20

    # --- SECCIÓN 1: IDENTIFICACIÓN Y CATEGORÍA SG ---
    _dibujar_seccion_hdr("1. IDENTIFICACIÓN Y CATEGORIZACIÓN ZOOTÉCNICA")
    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 8, y_pos - 10, "Sexo:")
    c.setFont("Helvetica", 8)
    c.drawString(col_der_x + 38, y_pos - 10, str(ficha.get("sexo") or "S/D"))

    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 105, y_pos - 10, "Raza:")
    c.setFont("Helvetica", 8)
    c.drawString(col_der_x + 135, y_pos - 10, str(ficha.get("raza") or "S/D"))

    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 205, y_pos - 10, "Hierro:")
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor(_COLOR_MARCA))
    c.drawString(col_der_x + 240, y_pos - 10, str(ficha.get("hierro") or "S/D"))

    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 305, y_pos - 10, "Categoría:")
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor(_COLOR_MARCA))
    c.drawString(col_der_x + 358, y_pos - 10, str(ficha.get("categoria_sg") or "S/D")[:26])

    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 8, y_pos - 24, "Fecha Nac.:")
    c.setFont("Helvetica", 8)
    f_nac_str = str(ficha.get("fecha_nacimiento") or "")[:10] or "Sin fecha registrada"
    c.drawString(col_der_x + 64, y_pos - 24, f_nac_str)

    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 190, y_pos - 24, "Edad Zootécnica:")
    c.setFont("Helvetica", 8)
    c.drawString(col_der_x + 276, y_pos - 24, str(ficha.get("edad_str") or "S/D")[:34])

    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 8, y_pos - 38, "Potrero Actual:")
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor(_COLOR_MARCA))
    c.drawString(col_der_x + 78, y_pos - 38, pot_nom[:36])

    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 310, y_pos - 38, "Estado Hato:")
    c.setFont("Helvetica-Bold", 8)
    st_an = str(ficha.get("estado") or "ACTIVO").upper()
    if st_an == "VENDIDO":
        c.setFillColor(colors.HexColor("#D97706"))
        v_fec = ficha.get("venta", {}).get("fecha") if ficha.get("venta") else None
        c.drawString(col_der_x + 375, y_pos - 38, f"VENDIDO ({str(v_fec)[:10]})" if v_fec else "VENDIDO")
    elif st_an == "MUERTO":
        c.setFillColor(colors.HexColor("#DC2626"))
        m_fec = ficha.get("muerte", {}).get("fecha") if ficha.get("muerte") else None
        c.drawString(col_der_x + 375, y_pos - 38, f"MUERTO ({str(m_fec)[:10]})" if m_fec else "MUERTO")
    elif st_an == "DESCARTADO":
        c.setFillColor(colors.HexColor("#B45309"))
        c.drawString(col_der_x + 375, y_pos - 38, "DESCARTADO")
    else:
        c.setFillColor(colors.HexColor("#2E7D32"))
        c.drawString(col_der_x + 375, y_pos - 38, st_an)

    y_pos -= 46

    # --- SECCIÓN 2: GENEALOGÍA Y TRAZABILIDAD ---
    _dibujar_seccion_hdr("2. GENEALOGÍA Y TRAZABILIDAD")
    madre = ficha.get("madre") or {}
    padre = ficha.get("padre") or {}

    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 8, y_pos - 10, "Madre:")
    c.setFont("Helvetica", 8)
    m_txt = f"{madre.get('tag') or ''} {('· ' + madre.get('nombre')) if madre.get('nombre') else ''} {('(' + madre.get('raza') + ')') if madre.get('raza') else ''}".strip() or "Sin madre registrada"
    c.drawString(col_der_x + 46, y_pos - 10, _trunc(m_txt, 48))

    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 280, y_pos - 10, "Padre:")
    c.setFont("Helvetica", 8)
    p_txt = f"{padre.get('tag') or ''} {('· ' + padre.get('nombre')) if padre.get('nombre') else ''} {('(' + padre.get('raza') + ')') if padre.get('raza') else ''}".strip() or "Sin padre registrado"
    c.drawString(col_der_x + 318, y_pos - 10, _trunc(p_txt, 44))

    y_pos -= 18

    # --- SECCIÓN 3: DESEMPEÑO PONDERAL Y CONTROL DE PESOS ---
    _dibujar_seccion_hdr("3. DESEMPEÑO PONDERAL Y CONTROL DE PESOS")
    ult_p = ficha.get("ultimo_peso") or {}
    peso_nac_v = ficha.get("peso_nacimiento")
    peso_nac_txt = f"{peso_nac_v:.1f} kg" if peso_nac_v is not None else "S/D"

    ult_p_txt = f"{ult_p.get('peso_kg')} kg ({str(ult_p.get('fecha'))[:10]})" if ult_p.get("peso_kg") else "Sin pesajes"
    gmd_v = ult_p.get("gmd")
    gmd_txt = f"{float(gmd_v) * 1000:.0f} g/día" if gmd_v is not None else "—"

    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 8, y_pos - 10, "Peso Nac.:")
    c.setFont("Helvetica", 8)
    c.drawString(col_der_x + 60, y_pos - 10, peso_nac_txt)

    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 130, y_pos - 10, "Último Peso:")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 190, y_pos - 10, ult_p_txt)

    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 350, y_pos - 10, "GMD Reciente:")
    c.setFont("Helvetica", 8)
    c.drawString(col_der_x + 424, y_pos - 10, gmd_txt)

    # Mini tabla pesajes
    pesajes_list = ficha.get("pesajes") or []
    if pesajes_list:
        y_pos -= 22
        c.setFillColor(colors.HexColor("#F2F5F2"))
        c.rect(col_der_x + 8, y_pos - 2, col_der_w - 16, 12, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#2F5233"))
        c.setFont("Helvetica-Bold", 7)
        c.drawString(col_der_x + 14, y_pos + 1, "HISTORIAL PESAJES")
        c.drawString(col_der_x + 160, y_pos + 1, "PESO (KG)")
        c.drawString(col_der_x + 280, y_pos + 1, "GMD (G/D)")
        for idx, pes in enumerate(pesajes_list[:2]):
            y_pos -= 11
            c.setFillColor(colors.HexColor("#333333"))
            c.setFont("Helvetica", 7.2)
            c.drawString(col_der_x + 14, y_pos, str(pes.get("fecha") or "")[:10])
            c.drawString(col_der_x + 160, y_pos, f"{pes.get('peso_kg')} kg")
            gmd_item = pes.get("gmd_calculada")
            gmd_i_txt = f"{float(gmd_item)*1000:.0f} g/d" if gmd_item is not None else "—"
            c.drawString(col_der_x + 280, y_pos, gmd_i_txt)
        y_pos -= 6
    else:
        y_pos -= 16

    # --- SECCIÓN 4: ESTADO REPRODUCTIVO Y PARTOS ---
    _dibujar_seccion_hdr("4. ESTADO REPRODUCTIVO Y PARTOS")
    est_rep = str(ficha.get("estado_repro") or "Sin datos").replace("🟢", "").replace("🟡", "").replace("⚪", "").strip()
    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 8, y_pos - 10, "Condición:")
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor(_COLOR_MARCA))
    c.drawString(col_der_x + 60, y_pos - 10, est_rep[:46])

    dias_ab = ficha.get("dias_abiertos")
    if dias_ab is not None:
        c.setFillColor(colors.HexColor("#222222"))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(col_der_x + 360, y_pos - 10, "Días Abiertos:")
        c.setFont("Helvetica", 8)
        c.drawString(col_der_x + 428, y_pos - 10, f"{dias_ab} días")

    ult_par = ficha.get("ultimo_parto") or {}
    ult_ser = ficha.get("ultimo_servicio") or {}

    c.setFillColor(colors.HexColor("#222222"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 8, y_pos - 24, "Último Parto:")
    c.setFont("Helvetica", 8)
    if ult_par and ult_par.get("fecha"):
        par_txt = f"{str(ult_par.get('fecha'))[:10]} · Cría: {ult_par.get('sexo_cria') or 'S/D'} ({ult_par.get('estado_cria') or 'Vivo'})"
    else:
        par_txt = "Sin partos registrados"
    c.drawString(col_der_x + 68, y_pos - 24, par_txt[:44])

    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 8, y_pos - 38, "Último Servicio:")
    c.setFont("Helvetica", 8)
    if ult_ser and ult_ser.get("fecha"):
        fep_t = f" · FEP: {str(ult_ser.get('fep_calculada'))[:10]}" if ult_ser.get("fep_calculada") else ""
        ser_txt = f"{str(ult_ser.get('fecha'))[:10]} ({ult_ser.get('tipo_servicio') or 'IA'} {ult_ser.get('toro_pajilla') or ''}){fep_t}"
    else:
        ser_txt = "Sin servicios registrados"
    c.drawString(col_der_x + 78, y_pos - 38, ser_txt[:52])

    y_pos -= 46

    # --- SECCIÓN 5: CONTROL SANITARIO Y TIEMPOS DE RETIRO ---
    en_ret = bool(ficha.get("en_retiro"))
    bg_san = "#FDEBEC" if en_ret else _COLOR_MARCA_CLARA
    txt_san = "#9F2F2D" if en_ret else _COLOR_MARCA
    titulo_san = "5. CONTROL SANITARIO — ⚠️ ANIMAL EN TIEMPO DE RETIRO" if en_ret else "5. CONTROL SANITARIO — 🟢 LIBRE DE TIEMPO DE RETIRO"
    _dibujar_seccion_hdr(titulo_san, bg_color=bg_san, txt_color=txt_san)

    ret_act = ficha.get("retiros_activos") or []
    if ret_act:
        # Múltiples retiros: ordenados por fecha y sin solaparse.
        ordenados = sorted(ret_act, key=lambda r: str(r.get("fecha_fin_retiro_carne") or r.get("fecha_fin_retiro_leche") or ""))
        for r_item in ordenados[:3]:
            if not _hay_espacio(12):
                break
            c.setFillColor(colors.HexColor("#B71C1C"))
            c.setFont("Helvetica-Bold", 7.5)
            prod = _trunc(r_item.get("producto") or "Tratamiento", 26)
            leche_fin = f"Retiro Leche: {r_item.get('fecha_fin_retiro_leche')}" if r_item.get("fecha_fin_retiro_leche") else "Sin retiro leche"
            carne_fin = f"Retiro Carne: {r_item.get('fecha_fin_retiro_carne')}" if r_item.get("fecha_fin_retiro_carne") else "Sin retiro carne"
            c.drawString(col_der_x + 8, y_pos - 10, _trunc(f"• {prod}: {leche_fin} | {carne_fin}", 88))
            y_pos -= 12
    else:
        c.setFillColor(colors.HexColor("#2E7D32"))
        c.setFont("Helvetica", 8)
        c.drawString(col_der_x + 8, y_pos - 10, "Este animal NO registra periodos de carencia activos en leche ni carne.")
        y_pos -= 14

    c.save()
    return ruta


if __name__ == "__main__":  # pragma: no cover
    import sys as _s

    _f = _s.argv[1] if len(_s.argv) > 1 else ""
    if not _f:
        print("Uso: python src/reports/qr_fichas.py <potrero|lote>")
        raise SystemExit(2)
    _db = Database(os.getenv("BITACORA_DB", "data/bitacora.db"))
    print(generar_fichas_lote(_db, _f))
