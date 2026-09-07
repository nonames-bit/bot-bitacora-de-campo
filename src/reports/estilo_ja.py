"""Estilo compartido GANADERÍA JA para todos los PDFs del sistema.

Línea visual unificada tomada de la ficha individual (``qr_fichas.py`` ::
``generar_ficha_qr_individual``, A4 apaisado): franja verde sólida,
bandas de sección claras, tablas con header verde y zebra, pie con línea.

Usado por ``pdf_report.py`` (reporte general) y ``qr_fichas.py``
(ficha individual + tarjetas de lote 6/hoja).
"""
from __future__ import annotations

import os
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Image, Paragraph, Table, TableStyle

# --------------------------------------------------------------------------- #
# Constantes de color (Identidad visual unificada Ganadería JA)
# --------------------------------------------------------------------------- #
COLOR_MARCA = "#1B4D3E"            # Verde bosque institucional profundo
COLOR_MARCA_OSCURO = "#12352B"     # Fondo verde noche para contrastes
COLOR_MARCA_CLARA = "#E8F0EC"      # Banda de sección suave / tint sage
COLOR_MARCA_ZEBRA = "#F7FAF8"      # Zebra stripe en tablas (muy sutil)
COLOR_MARCA_HEADER = "#A3D9A5"     # Texto secundario en header oscuro
COLOR_BORDE_SUAVE = "#D5E2D7"      # Borde sutil para tarjetas y tablas
COLOR_TIERRA = "#8D6E63"           # Tono tierra zootécnico
COLOR_GRIS = "#64748B"             # Gris pizarra medio
COLOR_GRIS_CLARO = "#F1F5F9"       # Fondo neutro claro
COLOR_VERDE = "#15803D"            # Verde éxito / ACTIVO
COLOR_VERDE_OK = "#15803D"
COLOR_VERDE_OK_BG = "#DCFCE7"      # Fondo verde estado óptimo
COLOR_AMBAR = "#D97706"            # Ámbar / Hierro / Advertencia
COLOR_AMBAR_BG = "#FEF3C7"         # Fondo chip ámbar
COLOR_AMBAR_TXT = "#92400E"        # Texto chip ámbar
COLOR_ROJO = "#B91C1C"             # Rojo alerta / muerte
COLOR_ROJO_ALERTA = "#B91C1C"
COLOR_ALERTA_BG = "#FEE2E2"        # Fondo alerta retiro sanitario
COLOR_ALERTA_TXT = "#991B1B"       # Texto alerta retiro
COLOR_PIE = "#64748B"              # Texto pie de página
COLOR_LINEA = "#E2E8F0"            # Línea divisoria muy limpia
COLOR_FONDO_TARJETA = "#F8FAF9"    # Fondo tarjeta izquierda ficha
COLOR_BORDE_TARJETA = "#B7CEBB"    # Borde tarjeta izquierda
COLOR_NEGRO = "#1E293B"            # Texto cuerpo de alto contraste
COLOR_QR_FONDO = "#F8FAFC"         # Placeholder QR
COLOR_QR_URL = "#0369A1"           # URL en ficha
COLOR_FOTO_PLACEHOLDER = "#F1F5F9"
COLOR_FOTO_BORDE = "#CBD5E1"
COLOR_FOTO_TEXTO = "#64748B"
COLOR_VENDIDO = "#D97706"
COLOR_MUERTO = "#DC2626"
COLOR_DESCARTADO = "#B45309"
COLOR_TOTALES_BG = "#DCEBE0"       # Fila de totales
COLOR_QR_BORDE = "#CBD5E1"         # Borde sutil contenedor QR
COLOR_MEDALLA_BORDE = "#D4AF37"    # Borde dorado sutil medalla logo

__all__ = [
    "COLOR_MARCA", "COLOR_MARCA_OSCURO", "COLOR_MARCA_CLARA", "COLOR_MARCA_ZEBRA",
    "COLOR_MARCA_HEADER", "COLOR_BORDE_SUAVE", "COLOR_TIERRA", "COLOR_GRIS",
    "COLOR_GRIS_CLARO", "COLOR_VERDE", "COLOR_VERDE_OK", "COLOR_VERDE_OK_BG",
    "COLOR_AMBAR", "COLOR_AMBAR_BG", "COLOR_AMBAR_TXT", "COLOR_ROJO",
    "COLOR_ROJO_ALERTA", "COLOR_ALERTA_BG", "COLOR_ALERTA_TXT", "COLOR_PIE",
    "COLOR_LINEA", "COLOR_FONDO_TARJETA", "COLOR_BORDE_TARJETA",
    "COLOR_NEGRO", "COLOR_QR_FONDO", "COLOR_QR_URL",
    "COLOR_FOTO_PLACEHOLDER", "COLOR_FOTO_BORDE", "COLOR_FOTO_TEXTO",
    "COLOR_VENDIDO", "COLOR_MUERTO", "COLOR_DESCARTADO",
    "COLOR_TOTALES_BG", "COLOR_QR_BORDE", "COLOR_MEDALLA_BORDE",
    "estilo_titulo", "estilo_subtitulo", "estilo_seccion",
    "estilo_subseccion_grafico", "estilo_normal", "estilo_pie",
    "estilo_encabezado_titulo", "estilo_encabezado_sub",
    "tabla_style_base", "tabla_style_alertas", "tabla_style_potreros",
    "tabla_style_header_verde", "tabla_style_moderna",
    "dibujar_encabezado", "dibujar_pie", "dibujar_seccion_hdr",
    "dibujar_logo_circular", "dibujar_running_header", "dibujar_running_footer",
    "buscar_logo_path", "logo_image",
    "banda_seccion", "tabla_encabezado_franja", "tabla_pie",
    "crear_bloque_kpis",
    "EncabezadoFlowable", "SeccionFlowable", "PieFlowable",
]


def _base():
    return getSampleStyleSheet()


# --------------------------------------------------------------------------- #
# Estilos de párrafo
# --------------------------------------------------------------------------- #
def estilo_titulo() -> ParagraphStyle:
    """Helvetica-Bold 15, color marca."""
    return ParagraphStyle(
        "JA_Titulo", parent=_base()["Title"], fontName="Helvetica-Bold",
        fontSize=15, textColor=colors.HexColor(COLOR_MARCA), spaceAfter=2,
    )


def estilo_subtitulo() -> ParagraphStyle:
    """Helvetica 9, gris."""
    return ParagraphStyle(
        "JA_Subtitulo", parent=_base()["Normal"], fontName="Helvetica",
        fontSize=9, textColor=colors.HexColor("#555555"), spaceAfter=6,
    )


def estilo_seccion() -> ParagraphStyle:
    """Helvetica-Bold 12, color marca (para usar dentro de bandas)."""
    return ParagraphStyle(
        "JA_Seccion", parent=_base()["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, textColor=colors.HexColor(COLOR_MARCA),
        spaceBefore=10, spaceAfter=4,
    )


def estilo_subseccion_grafico() -> ParagraphStyle:
    """Helvetica-Bold 8.5, color marca."""
    return ParagraphStyle(
        "JA_SubseccionGrafico", parent=_base()["Normal"],
        fontName="Helvetica-Bold", fontSize=8.5,
        textColor=colors.HexColor(COLOR_MARCA), spaceAfter=2,
    )


def estilo_normal() -> ParagraphStyle:
    """Helvetica 9, negro cuerpo."""
    return ParagraphStyle(
        "JA_Normal", parent=_base()["Normal"], fontName="Helvetica",
        fontSize=9, textColor=colors.HexColor(COLOR_NEGRO),
    )


def estilo_pie() -> ParagraphStyle:
    """Helvetica-Oblique 8, gris pie."""
    return ParagraphStyle(
        "JA_Pie", parent=_base()["Normal"], fontName="Helvetica-Oblique",
        fontSize=8, textColor=colors.HexColor(COLOR_PIE), spaceBefore=14,
    )


def estilo_encabezado_titulo() -> ParagraphStyle:
    """Título blanco para usar dentro de la franja verde."""
    return ParagraphStyle(
        "JA_EncTitulo", parent=_base()["Normal"], fontName="Helvetica-Bold",
        fontSize=14, leading=16, textColor=colors.white, spaceAfter=2,
    )


def estilo_encabezado_sub() -> ParagraphStyle:
    """Subtítulo blanco tenue para la franja verde."""
    return ParagraphStyle(
        "JA_EncSub", parent=_base()["Normal"], fontName="Helvetica",
        fontSize=8, leading=10, textColor=colors.HexColor(COLOR_MARCA_HEADER),
        spaceAfter=1,
    )


# --------------------------------------------------------------------------- #
# TableStyles modernos
# --------------------------------------------------------------------------- #
def tabla_style_moderna() -> TableStyle:
    """Estilo contemporáneo: cabecera verde sólida con texto blanco,
    filas alternadas tenues, bordes sutiles y padding ergonómico."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(COLOR_NEGRO)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor(COLOR_MARCA_ZEBRA)]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(COLOR_MARCA_OSCURO)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor(COLOR_LINEA)),
        ("LINEAFTER", (0, 0), (-2, -1), 0.3, colors.HexColor(COLOR_LINEA)),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def tabla_style_base() -> TableStyle:
    """Compatibilidad: cabecera clara + zebra."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA_CLARA)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_LINEA)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor(COLOR_MARCA_ZEBRA)]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ])


def tabla_style_header_verde(base: Optional[TableStyle] = None) -> TableStyle:
    """Superpone cabecera verde con texto blanco."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(COLOR_MARCA_OSCURO)),
    ])


def tabla_style_alertas() -> TableStyle:
    """Cabecera de alerta sanitaria destacada."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_ALERTA_BG)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(COLOR_ALERTA_TXT)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_LINEA)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#FFF7F7")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def tabla_style_potreros() -> TableStyle:
    """Tabla técnica de existencias por potrero."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.8),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_LINEA)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2),
         [colors.white, colors.HexColor(COLOR_MARCA_ZEBRA)]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])


# --------------------------------------------------------------------------- #
# Helpers de dibujo en Canvas
# --------------------------------------------------------------------------- #
def dibujar_logo_circular(c, x: float, y: float, diametro: float = 30,
                           logo_path: Optional[str] = None) -> bool:
    """Dibuja el logo de Ganadería JA dentro de una máscara circular elegante
    con un aro decorativo dorado, eliminando el marco cuadrado oscuro."""
    path = logo_path or buscar_logo_path()
    if not path or not os.path.exists(path):
        return False
    from reportlab.lib.utils import ImageReader
    r = diametro / 2.0
    cx = x + r
    cy = y + r
    c.saveState()
    clip = c.beginPath()
    clip.circle(cx, cy, r)
    c.clipPath(clip, stroke=0, fill=0)
    try:
        c.drawImage(ImageReader(path), x, y, width=diametro, height=diametro,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        c.restoreState()
        return False
    c.restoreState()

    c.saveState()
    c.setStrokeColor(colors.HexColor(COLOR_MEDALLA_BORDE))
    c.setLineWidth(0.8)
    c.circle(cx, cy, r, stroke=1, fill=0)
    c.restoreState()
    return True


def dibujar_encabezado(c, x0, y_hdr, cw, h_hdr=40, potrero="", fecha="",
                       subtitulo="FICHA TÉCNICA ZOOTÉCNICA Y TRAZABILIDAD INDIVIDUAL") -> None:
    """Franja institucional verde sólida con medalla circular y tipografía refinada."""
    c.saveState()
    c.setFillColor(colors.HexColor("#0D1D13"))
    c.rect(x0, y_hdr - 1.5, cw, 1.5, stroke=0, fill=1)

    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.rect(x0, y_hdr, cw, h_hdr, stroke=0, fill=1)

    logo_w = h_hdr - 10
    tiene_logo = dibujar_logo_circular(c, x0 + 8, y_hdr + 5, diametro=logo_w)
    txt_x = x0 + logo_w + 16 if tiene_logo else x0 + 12

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13.5)
    c.drawString(txt_x, y_hdr + 22, "GANADERÍA JA")

    c.setFont("Helvetica-Bold", 8.8)
    c.setFillColor(colors.HexColor(COLOR_MARCA_HEADER))
    c.drawString(txt_x + 115, y_hdr + 22, f"·  {subtitulo.upper()[:65]}")

    c.setFont("Helvetica", 7.6)
    c.setFillColor(colors.HexColor("#E2E8F0"))
    c.drawString(txt_x, y_hdr + 9, "BITÁCORA DE CAMPO  |  SISTEMA OFICIAL GANADERÍA JA · HATO ACTIVO")

    if potrero:
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawRightString(x0 + cw - 12, y_hdr + 22, f"POTRERO: {str(potrero).upper()[:30]}")
    c.setFont("Helvetica", 7.8)
    c.setFillColor(colors.HexColor(COLOR_MARCA_HEADER))
    c.drawRightString(x0 + cw - 12, y_hdr + 9, f"Emisión: {fecha}  |  Doc. Certificado")
    c.restoreState()


def dibujar_seccion_hdr(c, x: float, y: float, w: float, titulo: str,
                        bg_color: str = COLOR_MARCA_CLARA,
                        txt_color: str = COLOR_MARCA) -> None:
    """Rectángulo estilizado con acento lateral y texto en negrita."""
    c.saveState()
    c.setFillColor(colors.HexColor(bg_color))
    c.roundRect(x, y, w, 16, 2, fill=1, stroke=0)
    # Acento lateral izquierdo
    c.setFillColor(colors.HexColor(txt_color))
    c.roundRect(x, y, 3, 16, 1, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x + 8, y + 4.5, str(titulo))
    c.restoreState()


def dibujar_running_header(c, doc, titulo: str = "GANADERÍA JA · Reporte de Campo",
                           periodo_str: str = "") -> None:
    """Cabecera compacta para páginas posteriores (evita solapar contenido)."""
    c.saveState()
    cw = doc.pagesize[0] - doc.leftMargin - doc.rightMargin
    x0 = doc.leftMargin
    y_top = doc.pagesize[1] - doc.topMargin + 10 * mm

    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x0, y_top + 2, titulo)

    if periodo_str:
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.HexColor(COLOR_GRIS))
        c.drawRightString(x0 + cw, y_top + 2, periodo_str)

    c.setStrokeColor(colors.HexColor(COLOR_LINEA))
    c.setLineWidth(0.6)
    c.line(x0, y_top - 2, x0 + cw, y_top - 2)
    c.restoreState()


def dibujar_running_footer(c, doc, texto_izq: str = "Ganadería JA · Bitácora Zootécnica Oficial",
                           total_paginas: Optional[int] = None) -> None:
    """Pie de página institucional con línea separatoria y paginador."""
    c.saveState()
    cw = doc.pagesize[0] - doc.leftMargin - doc.rightMargin
    x0 = doc.leftMargin
    y_pie = doc.bottomMargin - 4 * mm

    c.setStrokeColor(colors.HexColor(COLOR_LINEA))
    c.setLineWidth(0.5)
    c.line(x0, y_pie + 10, x0 + cw, y_pie + 10)

    c.setFillColor(colors.HexColor(COLOR_PIE))
    c.setFont("Helvetica", 7.2)
    c.drawString(x0, y_pie + 2, texto_izq)

    pag_txt = f"Página {doc.page} de {total_paginas}" if total_paginas else f"Página {doc.page}"
    c.drawRightString(x0 + cw, y_pie + 2, pag_txt)
    c.restoreState()


def dibujar_pie(c, x0: float, y_pie: float, cw: float, texto_izq: str, texto_der: str = "") -> None:
    """Dibuja un pie de página con línea divisoria fina y dos columnas de texto."""
    c.saveState()
    c.setStrokeColor(colors.HexColor(COLOR_LINEA))
    c.setLineWidth(0.5)
    c.line(x0, y_pie + 12, x0 + cw, y_pie + 12)
    c.setFillColor(colors.HexColor(COLOR_PIE))
    c.setFont("Helvetica", 7.5)
    c.drawString(x0, y_pie + 2, texto_izq)
    if texto_der:
        c.drawRightString(x0 + cw, y_pie + 2, texto_der)
    c.restoreState()


# --------------------------------------------------------------------------- #
# Logo
# --------------------------------------------------------------------------- #
def buscar_logo_path() -> Optional[str]:
    """Busca el logo institucional en ubicaciones conocidas."""
    candidatos = [
        "docs/GanaderiaJA_Logo.jpg",
        "media/GanaderiaJA_Logo.jpg",
        os.path.join(os.path.dirname(__file__), "../../docs/GanaderiaJA_Logo.jpg"),
        os.path.abspath(os.path.join(os.path.dirname(__file__),
                                      "../../docs/GanaderiaJA_Logo.jpg")),
    ]
    for cand in candidatos:
        try:
            if cand and os.path.exists(cand):
                return cand
        except Exception:
            continue
    return None


def logo_image(path, width=20 * mm, height=20 * mm) -> Image:
    """Devuelve un flowable Image listo para usar en el encabezado."""
    return Image(path, width=width, height=height)


# --------------------------------------------------------------------------- #
# Flowables platypus (Tarjetas ejecutivas, bandas y tablas compuestas)
# --------------------------------------------------------------------------- #
def crear_bloque_kpis(kpis: Sequence[tuple[str, str, str, str]], ancho_total: float = 170 * mm) -> Table:
    """Crea una fila de tarjetas KPI ejecutivas para resúmenes de inventario y producción.
    Cada elemento de kpis es: (valor_grande, etiqueta_superior, subtexto_inferior, color_acento)"""
    n = len(kpis)
    if n == 0:
        return Table([[]])
    w_col = ancho_total / float(n)
    col_widths = [w_col] * n

    est_et = ParagraphStyle("KPI_Et", fontName="Helvetica-Bold", fontSize=7.2, leading=9,
                            textColor=colors.HexColor(COLOR_GRIS), alignment=1)
    est_val = ParagraphStyle("KPI_Val", fontName="Helvetica-Bold", fontSize=15, leading=17,
                             textColor=colors.HexColor(COLOR_MARCA), alignment=1)
    est_sub = ParagraphStyle("KPI_Sub", fontName="Helvetica", fontSize=6.8, leading=8.5,
                             textColor=colors.HexColor(COLOR_GRIS), alignment=1)

    celdas = []
    for val, et, sub, col_hex in kpis:
        st_val_custom = ParagraphStyle(f"Val_{col_hex}_{val}", parent=est_val, textColor=colors.HexColor(col_hex))
        p_et = Paragraph(et.upper(), est_et)
        p_val = Paragraph(str(val), st_val_custom)
        p_sub = Paragraph(sub, est_sub) if sub else Paragraph("&nbsp;", est_sub)
        celdas.append([p_et, p_val, p_sub])

    t = Table([celdas], colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAF9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COLOR_BORDE_SUAVE)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def banda_seccion(titulo: str, alerta: bool = False,
                  ancho: float = 170 * mm) -> Table:
    """Banda de sección refinada con barra lateral de acento."""
    bg = COLOR_ALERTA_BG if alerta else COLOR_MARCA_CLARA
    fg = COLOR_ALERTA_TXT if alerta else COLOR_MARCA
    acento = COLOR_ROJO_ALERTA if alerta else COLOR_MARCA
    est = ParagraphStyle(
        "JA_Banda", parent=getSampleStyleSheet()["Normal"],
        fontName="Helvetica-Bold", fontSize=10, leading=12,
        textColor=colors.HexColor(fg), spaceBefore=0, spaceAfter=0,
    )
    t = Table([[Paragraph(str(titulo), est)]], colWidths=[ancho])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
        ("LINEBEFORE", (0, 0), (0, -1), 3.5, colors.HexColor(acento)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def tabla_encabezado_franja(titulo: str, linea2: str, linea3: str = "",
                            ancho_total: float = 170 * mm,
                            logo_path: Optional[str] = None) -> Table:
    """Banner ejecutivo de primera página con fondo verde oscuro, logo y jerarquía nítida."""
    est_t = ParagraphStyle(
        "JA_FranjaT", parent=getSampleStyleSheet()["Normal"],
        fontName="Helvetica-Bold", fontSize=13.5, leading=16,
        textColor=colors.white, spaceAfter=2,
    )
    est_s = ParagraphStyle(
        "JA_FranjaS", parent=getSampleStyleSheet()["Normal"],
        fontName="Helvetica", fontSize=7.8, leading=10,
        textColor=colors.HexColor(COLOR_MARCA_HEADER), spaceAfter=1,
    )
    bloques = [Paragraph(titulo, est_t), Paragraph(linea2, est_s)]
    if linea3:
        bloques.append(Paragraph(linea3, est_s))

    if logo_path and os.path.exists(logo_path):
        img = logo_image(logo_path, width=18 * mm, height=18 * mm)
        datos = [[img, bloques]]
        anchos = [22 * mm, ancho_total - 22 * mm]
    else:
        datos = [[bloques]]
        anchos = [ancho_total]

    t = Table(datos, colWidths=anchos)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(COLOR_MARCA)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def tabla_pie(texto: str, ancho: float = 170 * mm) -> Table:
    """Pie con línea superior y texto gris oblicuo."""
    est = ParagraphStyle(
        "JA_PieTabla", parent=getSampleStyleSheet()["Normal"],
        fontName="Helvetica-Oblique", fontSize=7.5, leading=9.5,
        textColor=colors.HexColor(COLOR_PIE),
    )
    t = Table([[Paragraph(texto, est)]], colWidths=[ancho])
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor(COLOR_LINEA)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


class SeccionFlowable(Flowable):
    """Banda de sección dibujada en canvas con acento lateral y tipografía nítida."""

    def __init__(self, titulo: str, alerta: bool = False,
                 width: float = 170 * mm, height: float = 17):
        super().__init__()
        self.titulo = str(titulo)
        self.alerta = alerta
        self.width = width
        self.height = height

    def wrap(self, *args):
        return (self.width, self.height + 4)

    def draw(self):
        bg = COLOR_ALERTA_BG if self.alerta else COLOR_MARCA_CLARA
        fg = COLOR_ALERTA_TXT if self.alerta else COLOR_MARCA
        acento = COLOR_ROJO_ALERTA if self.alerta else COLOR_MARCA
        self.canv.saveState()
        self.canv.setFillColor(colors.HexColor(bg))
        self.canv.roundRect(0, 0, self.width, self.height, 3, fill=1, stroke=0)
        self.canv.setFillColor(colors.HexColor(acento))
        self.canv.roundRect(0, 0, 3.5, self.height, 1.5, fill=1, stroke=0)
        self.canv.setFillColor(colors.HexColor(fg))
        self.canv.setFont("Helvetica-Bold", 9.5)
        self.canv.drawString(9, 4.5, self.titulo)
        self.canv.restoreState()


class EncabezadoFlowable(Flowable):
    """Banner institucional verde de primera página para flujo Platypus."""

    def __init__(self, titulo: str, linea2: str, linea3: str = "",
                 width: float = 170 * mm, height: float = 42,
                 logo_path: Optional[str] = None):
        super().__init__()
        self.titulo = titulo
        self.linea2 = linea2
        self.linea3 = linea3
        self.width = width
        self.height = height
        self.logo_path = logo_path

    def wrap(self, *args):
        return (self.width, self.height + 4)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(colors.HexColor(COLOR_MARCA))
        c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        tiene_logo = False
        if self.logo_path and os.path.exists(self.logo_path):
            tiene_logo = dibujar_logo_circular(c, 8, (self.height - 30) / 2.0,
                                               diametro=30, logo_path=self.logo_path)
        x_txt = 46 if tiene_logo else 12
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 13.5)
        c.drawString(x_txt, self.height - 15, self.titulo)
        c.setFont("Helvetica", 7.8)
        c.setFillColor(colors.HexColor(COLOR_MARCA_HEADER))
        c.drawString(x_txt, self.height - 26, self.linea2[:110])
        if self.linea3:
            c.drawString(x_txt, self.height - 36, self.linea3[:110])
        c.restoreState()


class PieFlowable(Flowable):
    """Pie con línea separatoria y texto tenue."""

    def __init__(self, texto: str, width: float = 170 * mm):
        super().__init__()
        self.texto = texto
        self.width = width
        self.height = 14

    def wrap(self, *args):
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(colors.HexColor(COLOR_LINEA))
        c.setLineWidth(0.5)
        c.line(0, 10, self.width, 10)
        c.setFillColor(colors.HexColor(COLOR_PIE))
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(0, 0, self.texto[:140])
        c.restoreState()
