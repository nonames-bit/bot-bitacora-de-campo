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


# Paleta institucional GANADERÍA JA (misma que pdf_report.py).
_COLOR_MARCA = "#2F5233"
_COLOR_MARCA_CLARA = "#E7EFE8"

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

        # Marco + franja marca.
        c.setStrokeColor(_COLOR_MARCA)
        c.setLineWidth(1.2)
        c.rect(x0, y0, cw, ch, stroke=1, fill=0)
        c.setFillColor(_COLOR_MARCA)
        c.rect(x0, y0 + ch - 20, cw, 20, stroke=0, fill=1)
        c.setFillColor("white")
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x0 + 6, y0 + ch - 14, "GANADERÍA JA")
        c.setFont("Helvetica", 8)
        c.drawRightString(x0 + cw - 6, y0 + ch - 14, potrero[:32])

        # Tag grande.
        c.setFillColor("black")
        c.setFont("Helvetica-Bold", 20)
        c.drawString(x0 + 8, y0 + ch - 44, tag[:18])

        # QR (cache) o placeholder si falta librería qrcode.
        qx, qy, qs = x0 + 8, y0 + 10, 92
        qr_png = _qr_png_path(tag, cache_dir)
        if qr_png and os.path.exists(qr_png):
            try:
                c.drawImage(ImageReader(qr_png), qx, qy, width=qs, height=qs)
            except Exception:
                c.rect(qx, qy, qs, qs)
                c.setFont("Helvetica", 6)
                c.drawString(qx + 4, qy + qs / 2, payload[:28])
        else:
            c.rect(qx, qy, qs, qs)
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

        # Foto mini si existe en media/.
        try:
            foto = buscar_foto_animal(db, tag, media_dir=media_dir) if buscar_foto_animal else None
            if foto and os.path.exists(foto):
                fw, fh = 64, 48
                c.drawImage(ImageReader(foto), x0 + cw - fw - 6, y0 + ch - 44 - fh,
                            width=fw, height=fh, preserveAspectRatio=True)
        except Exception:
            pass

    # Pie con conteo en la última página.
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(W / 2, margen - 14, f"Fichas QR · {filtro} · {len(animales)} animales ACTIVOS · {hoy_iso}")
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
    """Genera una tarjeta QR única (una por página, formato apaisado A4)
    para exportar la ficha de UN animal desde la PWA (botón "Descargar QR").

    Devuelve la ruta del PDF. Lanza ValueError si el animal no existe o no
    está ACTIVO.
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

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
    payload, url = qr_payload(an_tag)
    potrero = _potrero_display(db, animal)
    edad = _edad_str(animal, hoy)
    estado = _estado_repro_retiro(db, aid, hoy_iso)

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", an_tag) or "animal"
    ruta = salida or os.path.join("data", "reportes", f"ficha_qr_{safe}_{hoy_iso}.pdf")
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)

    W, H = landscape(A4)
    c = canvas.Canvas(ruta, pagesize=landscape(A4))
    m = 30
    cw, ch = W - 2 * m, H - 2 * m - 22

    # Marco + franja marca.
    c.setStrokeColor(_COLOR_MARCA)
    c.setLineWidth(1.4)
    c.rect(m, m + 20, cw, ch, stroke=1, fill=0)
    c.setFillColor(_COLOR_MARCA)
    c.rect(m, m + ch + 20 - 24, cw, 24, stroke=0, fill=1)
    c.setFillColor("white")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(m + 8, m + ch - 16, "GANADERÍA JA · Ficha QR")
    c.setFont("Helvetica", 9)
    c.drawRightString(m + cw - 8, m + ch - 16, f"{potrero[:44]} · {hoy_iso}")

    # Tag grande.
    c.setFillColor("black")
    c.setFont("Helvetica-Bold", 34)
    c.drawString(m + 12, m + ch - 64, an_tag[:20])

    # QR (o placeholder).
    qx, qy, qs = m + 12, m + 30, 160
    qr_png = _qr_png_path(an_tag, cache_dir)
    if qr_png and os.path.exists(qr_png):
        try:
            c.drawImage(ImageReader(qr_png), qx, qy, width=qs, height=qs)
        except Exception:
            c.rect(qx, qy, qs, qs)
    else:
        c.rect(qx, qy, qs, qs)
        c.setFont("Helvetica", 8)
        c.drawCentredString(qx + qs / 2, qy + qs / 2, payload[:40])

    tx = qx + qs + 18
    c.setFont("Helvetica", 12)
    c.drawString(tx, qy + 150, f"Tag: {an_tag[:18]}")
    c.drawString(tx, qy + 130, f"Edad: {edad[:42]}")
    c.setFont("Helvetica", 10.5)
    for i, linea in enumerate(estado[i:i + 60] for i in range(0, len(estado), 60)):
        if i >= 4:
            break
        c.drawString(tx, qy + 108 - i * 16, linea[:60])

    full_url = f"{base_url.rstrip('/')}{url}" if base_url else url
    c.setFont("Helvetica", 9)
    c.drawString(tx, qy + 40, f"QR: {payload[:60]}")
    c.drawString(tx, qy + 24, f"Web: {full_url[:80]}")

    # Foto mini si existe.
    try:
        foto = buscar_foto_animal(db, an_tag, media_dir=media_dir) if buscar_foto_animal else None
        if foto and os.path.exists(foto):
            c.drawImage(ImageReader(foto), m + cw - 170, qy, width=158, height=118,
                        preserveAspectRatio=True)
    except Exception:
        pass

    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(W / 2, 12, f"Ficha QR individual · {an_tag} · ACTIVO · {hoy_iso}")
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
