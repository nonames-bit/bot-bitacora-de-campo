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
    COLOR_AMBAR,
    COLOR_AMBAR_BG,
    COLOR_AMBAR_TXT,
    COLOR_BORDE_SUAVE,
    COLOR_DESCARTADO,
    COLOR_FOTO_BORDE,
    COLOR_GRIS,
    COLOR_GRIS_CLARO,
    COLOR_LINEA,
    COLOR_MARCA,
    COLOR_MARCA_CLARA,
    COLOR_MARCA_HEADER,
    COLOR_MARCA_ZEBRA,
    COLOR_NEGRO,
    COLOR_PIE,
    COLOR_QR_FONDO,
    COLOR_QR_URL,
    COLOR_ROJO_ALERTA,
    COLOR_VERDE_OK,
    COLOR_VERDE_OK_BG,
    dibujar_encabezado,
    dibujar_fondo_pagina,
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
                bits.append(f"retiro leche hasta {r['fecha_fin_retiro_leche']}")
            if r["fecha_fin_retiro_carne"] and r["fecha_fin_retiro_carne"] >= hoy_iso:
                bits.append(f"retiro carne hasta {r['fecha_fin_retiro_carne']}")
            partes.append("ALERTA RETIRO: " + " · ".join(bits) if bits else "Retiro sanitario activo")
        else:
            partes.append("Sin retiro sanitario")
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
    """Genera el PDF A4 (6 tarjetas por hoja) del lote/potrero y devuelve su ruta.
    
    Cada tarjeta incluye franja de marca, tag grande, código QR vectorial nativo,
    identificador de hierro, potrero, edad, perfil zootécnico y estado sanitario.
    Incluye líneas guía de corte para guillotina o tijeras.
    """
    from reportlab.lib import colors as _colors_lote
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        _TIENE_QR_VEC = True
    except Exception:
        _TIENE_QR_VEC = False

    hoy = hoy or date.today()
    hoy_iso = hoy.isoformat()
    animales = listar_animales_lote(db, filtro)
    if not animales:
        raise ValueError(f"Sin animales ACTIVOS para '{filtro}' (potrero o lote).")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(filtro).strip()) or "lote"
    ruta = salida or os.path.join("data", "reportes", f"fichas_qr_{safe}_{hoy_iso}.pdf")
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)

    W, H = A4
    margen, gap = 30, 10
    cw = (W - 2 * margen - gap) / 2.0
    ch = (H - 2 * margen - 2 * gap) / 3.0

    c = canvas.Canvas(ruta, pagesize=A4)

    def _dibujar_fondo_lote():
        dibujar_fondo_pagina(c, W, H, incluir_marco=True, incluir_marca_agua=False, margen_marco=6 * mm)

    _dibujar_fondo_lote()

    def _dibujar_guias_corte():
        """Líneas punteadas sutiles que facilitan el corte de las 6 tarjetas."""
        c.saveState()
        c.setStrokeColor(_colors_lote.HexColor("#CBD5E1"))
        c.setLineWidth(0.4)
        c.setDash([2, 3])
        # Corte vertical
        x_corte = margen + cw + gap / 2.0
        c.line(x_corte, margen - 4, x_corte, H - margen + 4)
        # Cortes horizontales
        y_corte1 = H - margen - ch - gap / 2.0
        y_corte2 = H - margen - 2 * ch - 1.5 * gap
        c.line(margen - 4, y_corte1, W - margen + 4, y_corte1)
        c.line(margen - 4, y_corte2, W - margen + 4, y_corte2)
        c.restoreState()

    for idx, animal in enumerate(animales):
        pos = idx % 6
        if idx and pos == 0:
            _dibujar_guias_corte()
            c.showPage()
            _dibujar_fondo_lote()
        col, row = pos % 2, pos // 2
        x0 = margen + col * (cw + gap)
        y0 = H - margen - (row + 1) * ch - row * gap
        tag = str(animal["tag"] or animal["id_animal"])
        payload, url = qr_payload(tag)
        potrero = _potrero_display(db, animal)
        edad = _edad_str(animal, hoy)
        estado = _estado_repro_retiro(db, int(animal["id_animal"]), hoy_iso)
        an_keys = animal.keys() if hasattr(animal, "keys") else ()
        hierro = str(animal["hierro"] or "").strip() if "hierro" in an_keys and animal["hierro"] else ""
        raza = str(animal["raza"] or "").strip() if "raza" in an_keys and animal["raza"] else ""
        sexo = str(animal["sexo"] or "").strip() if "sexo" in an_keys and animal["sexo"] else ""

        # Contenedor de tarjeta
        c.setFillColor(_colors_lote.HexColor("#FFFFFF"))
        c.setStrokeColor(_colors_lote.HexColor(COLOR_BORDE_SUAVE))
        c.setLineWidth(0.9)
        c.roundRect(x0, y0, cw, ch, 5, stroke=1, fill=1)

        # Franja institucional
        c.setFillColor(_colors_lote.HexColor(COLOR_MARCA))
        c.roundRect(x0 + 0.5, y0 + ch - 22, cw - 1, 21.5, 4, stroke=0, fill=1)
        c.setFillColor("white")
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x0 + 8, y0 + ch - 14, "GANADERÍA JA")
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(_colors_lote.HexColor(COLOR_MARCA_HEADER))
        c.drawRightString(x0 + cw - 8, y0 + ch - 14, potrero[:24].upper())

        # Tag animal
        c.setFillColor(_colors_lote.HexColor(COLOR_MARCA))
        c.setFont("Helvetica-Bold", 19)
        c.drawString(x0 + 8, y0 + ch - 43, tag[:16])

        # Hierro si existe
        if hierro:
            c.setFillColor(_colors_lote.HexColor(COLOR_AMBAR_BG))
            c.setStrokeColor(_colors_lote.HexColor(COLOR_AMBAR))
            c.roundRect(x0 + 8, y0 + ch - 58, 76, 11, 2, stroke=1, fill=1)
            c.setFillColor(_colors_lote.HexColor(COLOR_AMBAR_TXT))
            c.setFont("Helvetica-Bold", 6.8)
            c.drawCentredString(x0 + 46, y0 + ch - 55, f"HIERRO: {hierro[:12]}")

        # QR Vectorial en alta resolución (86x86 pt)
        qx, qy, qs = x0 + 8, y0 + 10, 86
        c.setFillColor(_colors_lote.HexColor("#FFFFFF"))
        c.setStrokeColor(_colors_lote.HexColor(COLOR_BORDE_SUAVE))
        c.setLineWidth(0.8)
        c.roundRect(qx - 2, qy - 2, qs + 4, qs + 4, 3, fill=1, stroke=1)

        target_qr = f"{base_url.rstrip('/')}{url}" if base_url else (f"{payload}\n{url}")
        qr_ok = False
        if _TIENE_QR_VEC:
            try:
                qr_w = QrCodeWidget(target_qr)
                b = qr_w.getBounds()
                bw = b[2] - b[0]
                bh = b[3] - b[1]
                d = Drawing(qs, qs, transform=[qs / bw, 0, 0, qs / bh, 0, 0])
                d.add(qr_w)
                renderPDF.draw(d, c, qx, qy)
                qr_ok = True
            except Exception:
                pass

        if not qr_ok:
            qr_png = _qr_png_path(tag, cache_dir)
            if qr_png and os.path.exists(qr_png):
                try:
                    c.drawImage(ImageReader(qr_png), qx, qy, width=qs, height=qs)
                    qr_ok = True
                except Exception:
                    pass

        if not qr_ok:
            c.setFillColor(_colors_lote.HexColor(COLOR_QR_FONDO))
            c.roundRect(qx, qy, qs, qs, 3, fill=1, stroke=0)
            c.setFillColor(_colors_lote.HexColor(COLOR_NEGRO))
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(qx + qs / 2, qy + qs / 2, f"QR: {tag}")

        # Foto mini si existe en media/
        try:
            foto = buscar_foto_animal(db, tag, media_dir=media_dir) if buscar_foto_animal else None
            if foto and os.path.exists(foto):
                fw, fh = 64, 46
                fx, fy = x0 + cw - fw - 8, y0 + ch - 48 - fh
                c.saveState()
                _clip = c.beginPath()
                _clip.roundRect(fx, fy, fw, fh, 4)
                c.clipPath(_clip, stroke=0, fill=0)
                c.drawImage(ImageReader(foto), fx, fy, width=fw, height=fh, preserveAspectRatio=True)
                c.restoreState()
                c.setStrokeColor(_colors_lote.HexColor(COLOR_FOTO_BORDE))
                c.setLineWidth(0.6)
                c.roundRect(fx, fy, fw, fh, 4, stroke=1, fill=0)
        except Exception:
            pass

        # Columna de datos zootécnicos estructurada
        tx = qx + qs + 10
        c.setFillColor(_colors_lote.HexColor(COLOR_NEGRO))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(tx, y0 + 84, "Potrero:")
        c.setFont("Helvetica", 8)
        c.drawString(tx + 40, y0 + 84, potrero[:22])

        c.setFont("Helvetica-Bold", 8)
        c.drawString(tx, y0 + 70, "Edad:")
        c.setFont("Helvetica", 8)
        c.drawString(tx + 40, y0 + 70, edad[:24])

        if raza or sexo:
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(tx, y0 + 56, "Perfil:")
            c.setFont("Helvetica", 7.5)
            perfil_str = f"{sexo} · {raza}".strip(" ·")
            c.drawString(tx + 40, y0 + 56, perfil_str[:24])

        # Estado reproductivo / sanitario en 2 líneas
        c.setFont("Helvetica", 7.2)
        c.setFillColor(_colors_lote.HexColor("#475569"))
        lineas_est = [estado[i:i + 38] for i in range(0, len(estado), 38)][:2]
        for i, linea in enumerate(lineas_est):
            c.drawString(tx, y0 + 42 - i * 10, linea[:38])

        # Enlace PWA
        full_url = f"{base_url.rstrip('/')}{url}" if base_url else url
        c.setFillColor(_colors_lote.HexColor(COLOR_QR_URL))
        c.setFont("Helvetica-Oblique", 6.2)
        c.drawString(tx, y0 + 16, f"Escanee QR  |  {full_url[:36]}")

    # Guías de corte en la última página
    _dibujar_guias_corte()

    # Pie de página institucional
    c.setStrokeColor(_colors_lote.HexColor(COLOR_LINEA))
    c.setLineWidth(0.5)
    c.line(margen, margen - 6, W - margen, margen - 6)
    c.setFillColor(_colors_lote.HexColor(COLOR_PIE))
    c.setFont("Helvetica", 7.5)
    c.drawString(margen, margen - 16, f"Ganadería JA · Fichas Técnicas Plastificables · {filtro} ({len(animales)} animales ACTIVOS)")
    c.drawRightString(W - margen, margen - 16, f"Emisión: {hoy_iso} · Documento Oficial de Campo")
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
    (formato apaisado A4, diseño ejecutivo de pasaporte zootécnico) para exportar
    la ficha de UN animal desde la PWA (botón 'Descargar tarjeta QR').

    Incluye medalla oficial circular con aro dorado, tarjeta pasaporte izquierda
    con Hierro y QR vectorial, grilla estructurada de 4 columnas, tarjetas de
    genealogía con abuelos, bloques KPI de pesos y GMD, condición reproductiva
    y bloque sanitario de tiempos de retiro sin caracteres rotos.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
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
    aid = db.resolve_animal(tag_clean)
    if aid is None:
        raise ValueError(f"No se encontró ningún animal con el identificador '{tag_clean}'.")
    animal = db.get_animal(aid)
    if animal is None:
        raise ValueError(f"No se encontró ningún animal con el identificador '{tag_clean}'.")
    an_tag = str(animal["tag"] or tag_clean)
    estado_animal = str(animal["estado"] or "ACTIVO").upper()

    ficha = datos_ficha_animal(db, an_tag)
    payload, url = qr_payload(an_tag)
    full_url = f"{base_url.rstrip('/')}{url}" if base_url else url

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", an_tag) or "animal"
    ruta = salida or os.path.join("data", "reportes", f"ficha_qr_{safe}_{hoy_iso}.pdf")
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)

    W, H = landscape(A4)
    c = canvas.Canvas(ruta, pagesize=landscape(A4))
    m = 20
    cw = W - 2 * m
    ch = H - 2 * m
    x0 = m
    y0 = m

    # 1. Fondo de hoja ejecutivo suave, marca de agua y marco con esquineros
    col_izq_w = 210
    dibujar_fondo_pagina(
        c, W, H, incluir_marco=True, incluir_marca_agua=True,
        margen_marco=6 * mm,
        cx=x0 + col_izq_w + (cw - col_izq_w) / 2.0,
        cy=y0 + ch / 2.0,
        watermark_diam=110 * mm,
        watermark_opacity=0.038,
    )

    # Contenedor perimetral de contenido
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.setLineWidth(1.1)
    c.roundRect(x0, y0, cw, ch, 6, stroke=1, fill=0)

    # 2. Encabezado corporativo institucional (con medalla circular y aro dorado)
    h_hdr = 42
    y_hdr = y0 + ch - h_hdr
    pot_nom = str(ficha.get("potrero") or "Sin potrero asignado")
    dibujar_encabezado(
        c, x0, y_hdr, cw, h_hdr=h_hdr,
        potrero=pot_nom, fecha=hoy_iso,
        subtitulo="FICHA TÉCNICA ZOOTÉCNICA Y TRAZABILIDAD INDIVIDUAL",
        estado=estado_animal
    )

    # 3. Pie de página institucional
    c.setStrokeColor(colors.HexColor(COLOR_LINEA))
    c.setLineWidth(0.5)
    c.line(x0 + 10, y0 + 20, x0 + cw - 10, y0 + 20)
    c.setFillColor(colors.HexColor(COLOR_PIE))
    c.setFont("Helvetica", 7.5)
    c.drawString(x0 + 12, y0 + 7, "Ganadería JA · Control Zootécnico Integral · Datos sincronizados del hato ganadero")
    c.drawRightString(x0 + cw - 12, y0 + 7, f"ID Sistema: #{aid} · Tag: {an_tag} · Documento Oficial de Campo")

    # 4. Columna Izquierda: Tarjeta Pasaporte (Identificación, Hierro, QR y Foto)
    col_izq_w = 210
    col_izq_x = x0 + 10
    col_izq_y = y0 + 28
    col_izq_h = y_hdr - col_izq_y - 8

    c.setFillColor(colors.HexColor("#FFFFFF"))
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.setLineWidth(1)
    c.roundRect(col_izq_x, col_izq_y, col_izq_w, col_izq_h, 6, fill=1, stroke=1)

    # Franja superior de tarjeta pasaporte
    c.setFillColor(colors.HexColor(COLOR_MARCA_CLARA))
    c.roundRect(col_izq_x + 0.5, col_izq_y + col_izq_h - 48, col_izq_w - 1, 47.5, 5, stroke=0, fill=1)

    # Tag y Nombre
    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(col_izq_x + 10, col_izq_y + col_izq_h - 26, f"{an_tag[:14]}")

    nom_txt = str(ficha.get("nombre") or "").strip()
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.drawString(col_izq_x + 10, col_izq_y + col_izq_h - 41, f"{nom_txt[:24]}" if nom_txt else "Sin nombre registrado")

    # Pastilla de Hierro
    hierro_val = str(ficha.get("hierro") or "").strip()
    hy = col_izq_y + col_izq_h - 70
    if hierro_val:
        c.setFillColor(colors.HexColor(COLOR_AMBAR_BG))
        c.setStrokeColor(colors.HexColor(COLOR_AMBAR))
        c.roundRect(col_izq_x + 10, hy, col_izq_w - 20, 16, 3, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(COLOR_AMBAR_TXT))
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(col_izq_x + col_izq_w / 2, hy + 4.5, f"HIERRO: {hierro_val[:20]}")
    else:
        c.setFillColor(colors.HexColor(COLOR_GRIS_CLARO))
        c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
        c.roundRect(col_izq_x + 10, hy, col_izq_w - 20, 16, 3, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(COLOR_GRIS))
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(col_izq_x + col_izq_w / 2, hy + 4.5, "HIERRO: S/D")

    # Contenedor QR
    qr_size = 132
    qr_x = col_izq_x + (col_izq_w - qr_size) / 2
    qr_y = hy - 14 - qr_size

    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.setLineWidth(0.8)
    c.roundRect(qr_x - 3, qr_y - 3, qr_size + 6, qr_size + 6, 4, fill=1, stroke=1)

    qr_dibujado = False
    target_qr = full_url if full_url.startswith("http") else (f"{base_url.rstrip('/')}/ficha/{an_tag}" if base_url else f"{payload}\n{url}")
    if _TIENE_QR_NATIVO:
        try:
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
        c.setFillColor(colors.HexColor(COLOR_QR_FONDO))
        c.roundRect(qr_x, qr_y, qr_size, qr_size, 4, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(COLOR_NEGRO))
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(qr_x + qr_size / 2, qr_y + qr_size / 2, f"QR: {an_tag}")

    # Instrucciones QR
    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.setFont("Helvetica-Bold", 7.8)
    c.drawCentredString(col_izq_x + col_izq_w / 2, qr_y - 12, "Escanee con la cámara del celular")
    c.setFont("Helvetica", 6.8)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawCentredString(col_izq_x + col_izq_w / 2, qr_y - 21, "Abre la ficha interactiva en la PWA")
    c.setFont("Helvetica-Oblique", 6.2)
    c.setFillColor(colors.HexColor(COLOR_QR_URL))
    c.drawCentredString(col_izq_x + col_izq_w / 2, qr_y - 30, full_url[:40])

    # Foto del animal o contenedor ilustrado
    foto_y = col_izq_y + 10
    foto_h = qr_y - 38 - foto_y
    foto_w = col_izq_w - 20
    foto_x = col_izq_x + 10
    foto_path = buscar_foto_animal(db, an_tag, media_dir=media_dir) if buscar_foto_animal else None
    if foto_path and os.path.exists(foto_path):
        try:
            c.saveState()
            _clip = c.beginPath()
            _clip.roundRect(foto_x, foto_y, foto_w, foto_h, 4)
            c.clipPath(_clip, stroke=0, fill=0)
            c.drawImage(ImageReader(foto_path), foto_x, foto_y, width=foto_w, height=foto_h, preserveAspectRatio=True)
            c.restoreState()
            c.setStrokeColor(colors.HexColor(COLOR_FOTO_BORDE))
            c.setLineWidth(0.6)
            c.roundRect(foto_x, foto_y, foto_w, foto_h, 4, stroke=1, fill=0)
        except Exception:
            foto_path = None
    if not foto_path:
        c.setFillColor(colors.HexColor("#F8FAF9"))
        c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
        c.roundRect(foto_x, foto_y, foto_w, foto_h, 4, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#94A3B8"))
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(foto_x + foto_w / 2, foto_y + foto_h / 2 + 5, "REGISTRO FOTOGRÁFICO")
        c.setFont("Helvetica", 7)
        c.drawString(foto_x + 10, foto_y + 8, f"Cat: {str(ficha.get('categoria_sg') or 'Bovino')[:20]}")

    # 5. Columna Derecha: 5 Secciones Técnicas Estructuradas
    col_der_x = col_izq_x + col_izq_w + 14
    col_der_w = x0 + cw - 10 - col_der_x
    y_pos = y_hdr - 6
    y_min = y0 + 28

    def _trunc(txt: str, n: int) -> str:
        t = str(txt or "").strip()
        return t if len(t) <= n else t[: max(0, n - 1)].rstrip() + "..."

    def _hay_espacio(necesario: float = 16) -> bool:
        return (y_pos - necesario) >= y_min

    def _dibujar_seccion(titulo, bg_color=COLOR_MARCA_CLARA, txt_color=COLOR_MARCA):
        nonlocal y_pos
        if not _hay_espacio(22):
            return
        dibujar_seccion_hdr(c, col_der_x, y_pos - 16, col_der_w, titulo,
                            bg_color=bg_color, txt_color=txt_color)
        y_pos -= 20

    # --- SECCIÓN 1: IDENTIFICACIÓN Y CATEGORIZACIÓN ZOOTÉCNICA ---
    _dibujar_seccion("1. IDENTIFICACIÓN Y CATEGORIZACIÓN ZOOTÉCNICA")
    h_sec1 = 44
    c.setFillColor(colors.HexColor("#FFFFFF"))
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.setLineWidth(0.8)
    c.roundRect(col_der_x, y_pos - h_sec1, col_der_w, h_sec1, 4, fill=1, stroke=1)

    cw4 = col_der_w / 4.0

    # Fila 1
    # Col 1: Sexo
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + 8, y_pos - 14, "SEXO:")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(col_der_x + 40, y_pos - 14, str(ficha.get("sexo") or "S/D"))

    # Col 2: Raza
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + cw4 + 8, y_pos - 14, "RAZA:")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(col_der_x + cw4 + 42, y_pos - 14, _trunc(str(ficha.get("raza") or "S/D"), 18))

    # Col 3: Categoría SG
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + 2 * cw4 + 8, y_pos - 14, "CATEGORÍA:")
    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(col_der_x + 2 * cw4 + 64, y_pos - 14, _trunc(str(ficha.get("categoria_sg") or "S/D"), 18))

    # Col 4: Potrero Actual
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + 3 * cw4 + 8, y_pos - 14, "POTRERO:")
    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(col_der_x + 3 * cw4 + 56, y_pos - 14, _trunc(pot_nom, 18))

    # Fila 2
    # Col 1: Fecha Nac.
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + 8, y_pos - 34, "FECHA NAC:")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica", 8)
    f_nac_str = str(ficha.get("fecha_nacimiento") or "")[:10] or "S/D"
    c.drawString(col_der_x + 60, y_pos - 34, f_nac_str)

    # Col 2: Edad Zootécnica
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + cw4 + 8, y_pos - 34, "EDAD:")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica", 8)
    c.drawString(col_der_x + cw4 + 38, y_pos - 34, _trunc(str(ficha.get("edad_str") or "S/D"), 20))

    # Col 3: Estado Hato (con chip de color)
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + 2 * cw4 + 8, y_pos - 34, "ESTADO:")
    st_an = str(ficha.get("estado") or "ACTIVO").upper()
    pill_x = col_der_x + 2 * cw4 + 54
    if st_an == "VENDIDO":
        v_fec = ficha.get("venta", {}).get("fecha") if ficha.get("venta") else None
        st_lbl = f"VENDIDO ({str(v_fec)[:10]})" if v_fec else "VENDIDO"
        c.setFillColor(colors.HexColor(COLOR_AMBAR_BG))
        c.setStrokeColor(colors.HexColor(COLOR_AMBAR))
        c.roundRect(pill_x, y_pos - 38, 80, 12, 2, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(COLOR_AMBAR_TXT))
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(pill_x + 40, y_pos - 35, st_lbl[:18])
    elif st_an == "MUERTO":
        m_fec = ficha.get("muerte", {}).get("fecha") if ficha.get("muerte") else None
        st_lbl = f"MUERTO ({str(m_fec)[:10]})" if m_fec else "MUERTO"
        c.setFillColor(colors.HexColor(COLOR_ALERTA_BG))
        c.setStrokeColor(colors.HexColor(COLOR_ROJO_ALERTA))
        c.roundRect(pill_x, y_pos - 38, 80, 12, 2, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(COLOR_ALERTA_TXT))
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(pill_x + 40, y_pos - 35, st_lbl[:18])
    elif st_an == "DESCARTADO":
        c.setFillColor(colors.HexColor(COLOR_AMBAR_BG))
        c.setStrokeColor(colors.HexColor(COLOR_DESCARTADO))
        c.roundRect(pill_x, y_pos - 38, 70, 12, 2, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(COLOR_DESCARTADO))
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(pill_x + 35, y_pos - 35, "DESCARTADO")
    else:
        c.setFillColor(colors.HexColor(COLOR_VERDE_OK_BG))
        c.setStrokeColor(colors.HexColor(COLOR_VERDE_OK))
        c.roundRect(pill_x, y_pos - 38, 54, 12, 2, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(COLOR_VERDE_OK))
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(pill_x + 27, y_pos - 35, "ACTIVO")

    # Col 4: Color / Chip
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + 3 * cw4 + 8, y_pos - 34, "SEÑAS:")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica", 7.5)
    señas_txt = str(ficha.get("color") or ficha.get("chip") or "Sin señas registradas")
    c.drawString(col_der_x + 3 * cw4 + 46, y_pos - 34, _trunc(señas_txt, 22))

    y_pos -= (h_sec1 + 8)

    # --- SECCIÓN 2: GENEALOGÍA Y TRAZABILIDAD (3 GENERACIONES) ---
    _dibujar_seccion("2. GENEALOGÍA Y TRAZABILIDAD (3 GENERACIONES)")
    h_sec2 = 44
    w_ped = (col_der_w - 10) / 2.0
    madre = ficha.get("madre") or {}
    padre = ficha.get("padre") or {}
    abuelo_mat = ficha.get("abuelo_mat") or {}
    abuela_mat = ficha.get("abuela_mat") or {}
    abuelo_pat = ficha.get("abuelo_pat") or {}
    abuela_pat = ficha.get("abuela_pat") or {}

    # Tarjeta Madre (Línea Materna)
    c.setFillColor(colors.HexColor("#F8FAF9"))
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.setLineWidth(0.8)
    c.roundRect(col_der_x, y_pos - h_sec2, w_ped, h_sec2, 4, fill=1, stroke=1)
    # Barra lateral verde
    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.roundRect(col_der_x, y_pos - h_sec2, 3, h_sec2, 1, fill=1, stroke=0)

    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.setFont("Helvetica-Bold", 8)
    m_tag_txt = f"MADRE: {madre.get('tag') or 'S/D'} {('· ' + madre.get('nombre')) if madre.get('nombre') else ''}"
    c.drawString(col_der_x + 8, y_pos - 13, _trunc(m_tag_txt, 38))
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica", 7.2)
    c.drawString(col_der_x + 8, y_pos - 25, f"Raza: {madre.get('raza') or 'S/D'}")
    ab_mat_txt = f"Abuelo: {abuelo_mat.get('tag') or 'S/D'}  |  Abuela: {abuela_mat.get('tag') or 'S/D'}"
    c.drawString(col_der_x + 8, y_pos - 37, _trunc(ab_mat_txt, 44))

    # Tarjeta Padre (Línea Paterna)
    px = col_der_x + w_ped + 10
    c.setFillColor(colors.HexColor("#F8FAF9"))
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.setLineWidth(0.8)
    c.roundRect(px, y_pos - h_sec2, w_ped, h_sec2, 4, fill=1, stroke=1)
    # Barra lateral azul institucional
    c.setFillColor(colors.HexColor("#1E3A8A"))
    c.roundRect(px, y_pos - h_sec2, 3, h_sec2, 1, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#1E3A8A"))
    c.setFont("Helvetica-Bold", 8)
    p_tag_txt = f"PADRE: {padre.get('tag') or 'S/D'} {('· ' + padre.get('nombre')) if padre.get('nombre') else ''}"
    c.drawString(px + 8, y_pos - 13, _trunc(p_tag_txt, 38))
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica", 7.2)
    c.drawString(px + 8, y_pos - 25, f"Raza: {padre.get('raza') or 'S/D'}")
    ab_pat_txt = f"Abuelo: {abuelo_pat.get('tag') or 'S/D'}  |  Abuela: {abuela_pat.get('tag') or 'S/D'}"
    c.drawString(px + 8, y_pos - 37, _trunc(ab_pat_txt, 44))

    y_pos -= (h_sec2 + 8)

    # --- SECCIÓN 3: DESEMPEÑO PONDERAL Y CONTROL DE PESOS ---
    _dibujar_seccion("3. DESEMPEÑO PONDERAL Y CONTROL DE PESOS")
    ult_p = ficha.get("ultimo_peso") or {}
    peso_nac_v = ficha.get("peso_nacimiento")
    peso_nac_txt = f"{peso_nac_v:.1f} kg" if peso_nac_v is not None else "S/D"
    ult_p_kg = f"{ult_p.get('peso_kg')} kg" if ult_p.get("peso_kg") else "Sin pesajes"
    ult_p_fec = str(ult_p.get("fecha"))[:10] if ult_p.get("fecha") else "S/D"
    gmd_v = ult_p.get("gmd")
    gmd_txt = f"+{float(gmd_v) * 1000:.0f} g/día" if gmd_v is not None else "—"

    w_tile = (col_der_w - 16) / 3.0
    h_tile = 32

    # Tile 1: Peso Nacimiento
    c.setFillColor(colors.HexColor("#FFFFFF"))
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.roundRect(col_der_x, y_pos - h_tile, w_tile, h_tile, 3, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#15803D"))
    c.roundRect(col_der_x, y_pos - h_tile, 3, h_tile, 1, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(col_der_x + 8, y_pos - 10, "PESO AL NACER")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(col_der_x + 8, y_pos - 24, peso_nac_txt)
    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.drawString(col_der_x + 8, y_pos - 31, "Registro inicial")

    # Tile 2: Último Peso
    t2_x = col_der_x + w_tile + 8
    c.setFillColor(colors.HexColor("#FFFFFF"))
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.roundRect(t2_x, y_pos - h_tile, w_tile, h_tile, 3, fill=1, stroke=1)
    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.roundRect(t2_x, y_pos - h_tile, 3, h_tile, 1, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(t2_x + 8, y_pos - 10, "ÚLTIMO PESO REGISTRADO")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(t2_x + 8, y_pos - 24, ult_p_kg)
    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.drawString(t2_x + 8, y_pos - 31, f"Fecha: {ult_p_fec}")

    # Tile 3: GMD
    t3_x = t2_x + w_tile + 8
    c.setFillColor(colors.HexColor("#FFFFFF"))
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.roundRect(t3_x, y_pos - h_tile, w_tile, h_tile, 3, fill=1, stroke=1)
    c.setFillColor(colors.HexColor(COLOR_AMBAR))
    c.roundRect(t3_x, y_pos - h_tile, 3, h_tile, 1, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 6.8)
    c.drawString(t3_x + 8, y_pos - 10, "GANANCIA MEDIA DIARIA")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(t3_x + 8, y_pos - 24, gmd_txt)
    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.drawString(t3_x + 8, y_pos - 31, "Desempeño ponderal")

    # Tabla previa de pesajes si existen
    pesajes_list = ficha.get("pesajes") or []
    if pesajes_list and len(pesajes_list) > 1:
        y_pos -= (h_tile + 6)
        c.setFillColor(colors.HexColor(COLOR_MARCA_ZEBRA))
        c.roundRect(col_der_x, y_pos - 12, col_der_w, 12, 2, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(COLOR_MARCA))
        c.setFont("Helvetica-Bold", 6.8)
        c.drawString(col_der_x + 8, y_pos - 8.5, "HISTORIAL RECIENTE:")
        c.drawString(col_der_x + 130, y_pos - 8.5, "FECHA")
        c.drawString(col_der_x + 240, y_pos - 8.5, "PESO")
        c.drawString(col_der_x + 350, y_pos - 8.5, "GMD CALCULADA")
        y_pos -= 20
        for pes in pesajes_list[1:3]:
            c.setFillColor(colors.HexColor(COLOR_NEGRO))
            c.setFont("Helvetica", 7.2)
            c.drawString(col_der_x + 130, y_pos, str(pes.get("fecha") or "")[:10])
            c.drawString(col_der_x + 240, y_pos, f"{pes.get('peso_kg')} kg")
            g_item = pes.get("gmd_calculada")
            g_txt = f"{float(g_item)*1000:.0f} g/d" if g_item is not None else "—"
            c.drawString(col_der_x + 350, y_pos, g_txt)
            y_pos -= 11
        y_pos -= 4
    else:
        y_pos -= (h_tile + 8)

    # --- SECCIÓN 4: ESTADO REPRODUCTIVO Y PARTOS ---
    _dibujar_seccion("4. ESTADO REPRODUCTIVO Y PARTOS")
    h_sec4 = 42
    c.setFillColor(colors.HexColor("#FFFFFF"))
    c.setStrokeColor(colors.HexColor(COLOR_BORDE_SUAVE))
    c.setLineWidth(0.8)
    c.roundRect(col_der_x, y_pos - h_sec4, col_der_w, h_sec4, 4, fill=1, stroke=1)

    est_rep = str(ficha.get("estado_repro") or "Sin datos").replace("🟢", "").replace("🟡", "").replace("⚪", "").strip()
    dias_ab = ficha.get("dias_abiertos")
    dias_ab_txt = f"{dias_ab} días" if dias_ab is not None else "N/A"

    # Columna izquierda: Condición y días abiertos
    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + 8, y_pos - 14, "CONDICIÓN REPRODUCTIVA:")
    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(col_der_x + 130, y_pos - 14, _trunc(est_rep, 24))

    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_der_x + 8, y_pos - 32, "DÍAS ABIERTOS:")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(col_der_x + 80, y_pos - 32, dias_ab_txt)

    # Columna derecha: Último Parto y Último Servicio
    sep_x = col_der_x + col_der_w * 0.48
    ult_par = ficha.get("ultimo_parto") or {}
    ult_ser = ficha.get("ultimo_servicio") or {}

    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(sep_x, y_pos - 14, "ÚLTIMO PARTO:")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica", 7.8)
    if ult_par and ult_par.get("fecha"):
        par_txt = f"{str(ult_par.get('fecha'))[:10]} · Cría: {ult_par.get('sexo_cria') or 'S/D'} ({ult_par.get('estado_cria') or 'Vivo'})"
    else:
        par_txt = "Sin partos registrados"
    c.drawString(sep_x + 76, y_pos - 14, _trunc(par_txt, 34))

    c.setFillColor(colors.HexColor(COLOR_GRIS))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(sep_x, y_pos - 32, "ÚLTIMO SERVICIO:")
    c.setFillColor(colors.HexColor(COLOR_NEGRO))
    c.setFont("Helvetica", 7.8)
    if ult_ser and ult_ser.get("fecha"):
        fep_t = f" · FEP: {str(ult_ser.get('fep_calculada'))[:10]}" if ult_ser.get("fep_calculada") else ""
        ser_txt = f"{str(ult_ser.get('fecha'))[:10]} ({ult_ser.get('tipo_servicio') or 'IA'} {ult_ser.get('toro_pajilla') or ''}){fep_t}"
    else:
        ser_txt = "Sin servicios registrados"
    c.drawString(sep_x + 86, y_pos - 32, _trunc(ser_txt, 34))

    y_pos -= (h_sec4 + 8)

    # --- SECCIÓN 5: CONTROL SANITARIO Y TIEMPOS DE RETIRO ---
    en_ret = bool(ficha.get("en_retiro"))
    bg_san = COLOR_ALERTA_BG if en_ret else COLOR_VERDE_OK_BG
    txt_san = COLOR_ROJO_ALERTA if en_ret else COLOR_VERDE_OK
    titulo_san = "5. CONTROL SANITARIO — ALERTA: ANIMAL EN TIEMPO DE RETIRO" if en_ret else "5. CONTROL SANITARIO — LIBRE DE RETIRO SANITARIO (APTO CONSUMO)"
    _dibujar_seccion(titulo_san, bg_color=bg_san, txt_color=txt_san)

    ret_act = ficha.get("retiros_activos") or []
    h_sec5 = 32
    if en_ret and ret_act:
        c.setFillColor(colors.HexColor("#FFF5F5"))
        c.setStrokeColor(colors.HexColor("#FCA5A5"))
        c.roundRect(col_der_x, y_pos - h_sec5, col_der_w, h_sec5, 3, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(COLOR_ROJO_ALERTA))
        c.roundRect(col_der_x, y_pos - h_sec5, 3, h_sec5, 1, fill=1, stroke=0)

        ordenados = sorted(ret_act, key=lambda r: str(r.get("fecha_fin_retiro_carne") or r.get("fecha_fin_retiro_leche") or ""))
        for idx, r_item in enumerate(ordenados[:2]):
            prod = _trunc(r_item.get("producto") or "Tratamiento", 24)
            leche_fin = f"Retiro Leche: {r_item.get('fecha_fin_retiro_leche')}" if r_item.get("fecha_fin_retiro_leche") else "Sin retiro leche"
            carne_fin = f"Retiro Carne: {r_item.get('fecha_fin_retiro_carne')}" if r_item.get("fecha_fin_retiro_carne") else "Sin retiro carne"
            c.setFillColor(colors.HexColor(COLOR_ROJO_ALERTA))
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(col_der_x + 8, y_pos - 12 - idx * 12, _trunc(f"• {prod}: {leche_fin}  |  {carne_fin}", 85))
    else:
        c.setFillColor(colors.HexColor("#F0FDF4"))
        c.setStrokeColor(colors.HexColor("#BBF7D0"))
        c.roundRect(col_der_x, y_pos - h_sec5, col_der_w, h_sec5, 3, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(COLOR_VERDE_OK))
        c.roundRect(col_der_x, y_pos - h_sec5, 3, h_sec5, 1, fill=1, stroke=0)

        c.setFillColor(colors.HexColor(COLOR_VERDE_OK))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(col_der_x + 8, y_pos - 12, "Este animal NO registra periodos de carencia activos en leche ni carne.")
        c.setFont("Helvetica", 7.2)
        c.setFillColor(colors.HexColor("#166534"))
        c.drawString(col_der_x + 8, y_pos - 24, "Certificado sanitario al día: Apto para producción lechera comercial y faenamiento.")

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
