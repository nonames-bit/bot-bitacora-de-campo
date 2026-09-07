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
# Constantes de color (unificadas de pdf_report.py + qr_fichas.py)
# --------------------------------------------------------------------------- #
COLOR_MARCA = "#2F5233"            # Verde institucional (franja header, texto destacado)
COLOR_MARCA_CLARA = "#E7EFE8"      # Banda de sección, fondo header tabla
COLOR_MARCA_ZEBRA = "#F3F7F3"      # Zebra stripe en tablas
COLOR_MARCA_HEADER = "#C8E6C9"     # Texto claro en header
COLOR_TIERRA = "#8D6E63"           # Tono tierra
COLOR_GRIS = "#78909C"             # Gris pizarra
COLOR_VERDE = "#2E7D32"            # Verde éxito/ACTIVO
COLOR_ROJO = "#C62828"             # Rojo alerta
COLOR_ALERTA_BG = "#FDEBEC"        # Fondo alerta retiro
COLOR_ALERTA_TXT = "#9F2F2D"       # Texto alerta retiro
COLOR_PIE = "#666666"              # Texto pie de página
COLOR_LINEA = "#CCCCCC"            # Línea separatoria
COLOR_FONDO_TARJETA = "#F8FAF8"    # Fondo tarjeta izquierda ficha
COLOR_BORDE_TARJETA = "#A4C1A8"    # Borde tarjeta izquierda
COLOR_NEGRO = "#222222"            # Texto cuerpo
COLOR_QR_FONDO = "#EEEEEE"         # Placeholder QR
COLOR_QR_URL = "#1F6C9F"           # URL en ficha
COLOR_FOTO_PLACEHOLDER = "#F0F3F0"
COLOR_FOTO_BORDE = "#D0DDD1"
COLOR_FOTO_TEXTO = "#7A8B7C"
COLOR_VENDIDO = "#D97706"
COLOR_MUERTO = "#DC2626"
COLOR_DESCARTADO = "#B45309"
COLOR_TOTALES_BG = "#D7E5D9"       # Fila de totales (existencias por potrero)
COLOR_QR_BORDE = "#DDDDDD"         # Borde sutil contenedor QR

__all__ = [
    "COLOR_MARCA", "COLOR_MARCA_CLARA", "COLOR_MARCA_ZEBRA",
    "COLOR_MARCA_HEADER", "COLOR_TIERRA", "COLOR_GRIS", "COLOR_VERDE",
    "COLOR_ROJO", "COLOR_ALERTA_BG", "COLOR_ALERTA_TXT", "COLOR_PIE",
    "COLOR_LINEA", "COLOR_FONDO_TARJETA", "COLOR_BORDE_TARJETA",
    "COLOR_NEGRO", "COLOR_QR_FONDO", "COLOR_QR_URL",
    "COLOR_FOTO_PLACEHOLDER", "COLOR_FOTO_BORDE", "COLOR_FOTO_TEXTO",
    "COLOR_VENDIDO", "COLOR_MUERTO", "COLOR_DESCARTADO",
    "COLOR_TOTALES_BG", "COLOR_QR_BORDE",
    "estilo_titulo", "estilo_subtitulo", "estilo_seccion",
    "estilo_subseccion_grafico", "estilo_normal", "estilo_pie",
    "estilo_encabezado_titulo", "estilo_encabezado_sub",
    "tabla_style_base", "tabla_style_alertas", "tabla_style_potreros",
    "tabla_style_header_verde",
    "dibujar_encabezado", "dibujar_pie", "dibujar_seccion_hdr",
    "buscar_logo_path", "logo_image",
    "banda_seccion", "tabla_encabezado_franja", "tabla_pie",
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
# TableStyles genéricos
# --------------------------------------------------------------------------- #
def tabla_style_base() -> TableStyle:
    """Header CLARA + texto marca Bold, zebra, GRID, VALIGN TOP."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA_CLARA)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COLOR_LINEA)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor(COLOR_MARCA_ZEBRA)]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])


def tabla_style_alertas() -> TableStyle:
    """Igual que la base pero header de alerta (fondo + texto de retiro)."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_ALERTA_BG)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(COLOR_ALERTA_TXT)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COLOR_LINEA)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor(COLOR_MARCA_ZEBRA)]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])


def tabla_style_potreros() -> TableStyle:
    """Igual que la base pero FONTSIZE 8, padding 2, numérico centrado."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA_CLARA)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COLOR_LINEA)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2),
         [colors.white, colors.HexColor(COLOR_MARCA_ZEBRA)]),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ])


def tabla_style_header_verde(base: Optional[TableStyle] = None) -> TableStyle:
    """Variante ficha: header fondo MARCA con texto blanco Bold.

    Se aplica ENCIMA del estilo base (los comandos posteriores ganan).
    """
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLOR_MARCA)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ])


# --------------------------------------------------------------------------- #
# Helpers de canvas (como en la ficha individual)
# --------------------------------------------------------------------------- #
def dibujar_encabezado(c, x0, y_hdr, cw, h_hdr=40, potrero="", fecha="") -> None:
    """Dibuja la franja sólida verde con textos blancos estilo ficha."""
    c.saveState()
    c.setFillColor(colors.HexColor(COLOR_MARCA))
    c.rect(x0, y_hdr, cw, h_hdr, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x0 + 12, y_hdr + 22, "GANADERÍA JA")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x0 + 130, y_hdr + 22,
                 "·  FICHA TÉCNICA ZOOTÉCNICA Y TRAZABILIDAD INDIVIDUAL")
    c.setFont("Helvetica", 8)
    c.drawString(x0 + 12, y_hdr + 9,
                 "BITÁCORA DE CAMPO  |  SISTEMA OFICIAL GANADERÍA JA")
    if potrero:
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(x0 + cw - 12, y_hdr + 22,
                          f"POTRERO: {str(potrero).upper()[:32]}")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor(COLOR_MARCA_HEADER))
    c.drawRightString(x0 + cw - 12, y_hdr + 9,
                      f"HATO ACTIVO  |  Emisión: {fecha}")
    c.restoreState()


def dibujar_pie(c, x0, y0, cw, texto_izq, texto_der) -> None:
    """Línea 0.5pt + textos 7.5pt gris, como el pie de la ficha."""
    c.saveState()
    c.setStrokeColor(colors.HexColor(COLOR_LINEA))
    c.setLineWidth(0.5)
    c.line(x0 + 10, y0 + 20, x0 + cw - 10, y0 + 20)
    c.setFillColor(colors.HexColor(COLOR_PIE))
    c.setFont("Helvetica", 7.5)
    c.drawString(x0 + 12, y0 + 7, str(texto_izq))
    c.drawRightString(x0 + cw - 12, y0 + 7, str(texto_der))
    c.restoreState()


def dibujar_seccion_hdr(c, x, y, w, titulo,
                        bg_color=COLOR_MARCA_CLARA,
                        txt_color=COLOR_MARCA) -> None:
    """Rectángulo de 16pt con fondo y texto Bold 8.5."""
    c.saveState()
    c.setFillColor(colors.HexColor(bg_color))
    c.rect(x, y, w, 16, fill=1, stroke=0)
    c.setFillColor(colors.HexColor(txt_color))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x + 8, y + 4, str(titulo))
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
# Flowables platypus (franja / banda / pie) para SimpleDocTemplate
# --------------------------------------------------------------------------- #
def banda_seccion(titulo: str, alerta: bool = False,
                  ancho: float = 170 * mm) -> Table:
    """Banda de sección (1 celda) con fondo CLARA o de alerta."""
    bg = COLOR_ALERTA_BG if alerta else COLOR_MARCA_CLARA
    fg = COLOR_ALERTA_TXT if alerta else COLOR_MARCA
    est = ParagraphStyle(
        "JA_Banda", parent=getSampleStyleSheet()["Normal"],
        fontName="Helvetica-Bold", fontSize=11, leading=13,
        textColor=colors.HexColor(fg), spaceBefore=0, spaceAfter=0,
    )
    t = Table([[Paragraph(str(titulo), est)]], colWidths=[ancho])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
    ]))
    return t


def tabla_encabezado_franja(titulo: str, linea2: str, linea3: str = "",
                            ancho_total: float = 170 * mm,
                            logo_path: Optional[str] = None) -> Table:
    """Tabla con fondo verde que simula la franja sólida (logo 20x20mm)."""
    est_t = ParagraphStyle(
        "JA_FranjaT", parent=getSampleStyleSheet()["Normal"],
        fontName="Helvetica-Bold", fontSize=14, leading=16,
        textColor=colors.white, spaceAfter=2,
    )
    est_s = ParagraphStyle(
        "JA_FranjaS", parent=getSampleStyleSheet()["Normal"],
        fontName="Helvetica", fontSize=8, leading=10,
        textColor=colors.HexColor(COLOR_MARCA_HEADER), spaceAfter=1,
    )
    bloques = [Paragraph(titulo, est_t), Paragraph(linea2, est_s)]
    if linea3:
        bloques.append(Paragraph(linea3, est_s))
    if logo_path and os.path.exists(logo_path):
        img = logo_image(logo_path)
        datos = [[img, bloques]]
        anchos = [24 * mm, ancho_total - 24 * mm]
    else:
        datos = [[bloques]]
        anchos = [ancho_total]
    t = Table(datos, colWidths=anchos)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(COLOR_MARCA)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def tabla_pie(texto: str, ancho: float = 170 * mm) -> Table:
    """Pie con línea superior y texto gris oblicuo."""
    est = ParagraphStyle(
        "JA_PieTabla", parent=getSampleStyleSheet()["Normal"],
        fontName="Helvetica-Oblique", fontSize=8, leading=10,
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
    """Banda de sección dibujada en canvas (fondo + título)."""

    def __init__(self, titulo: str, alerta: bool = False,
                 width: float = 170 * mm, height: float = 18):
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
        self.canv.saveState()
        self.canv.setFillColor(colors.HexColor(bg))
        self.canv.roundRect(0, 0, self.width, self.height, 3,
                            fill=1, stroke=0)
        self.canv.setFillColor(colors.HexColor(fg))
        self.canv.setFont("Helvetica-Bold", 11)
        self.canv.drawString(8, 5.5, self.titulo)
        self.canv.restoreState()


class EncabezadoFlowable(Flowable):
    """Franja verde sólida dibujada en el canvas del documento."""

    def __init__(self, titulo: str, linea2: str, linea3: str = "",
                 width: float = 170 * mm, height: float = 44,
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
        from reportlab.lib.utils import ImageReader
        c = self.canv
        c.saveState()
        c.setFillColor(colors.HexColor(COLOR_MARCA))
        c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        x_txt = 34 if self.logo_path and os.path.exists(self.logo_path or "") else 10
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                c.drawImage(ImageReader(self.logo_path), 8, 6, width=22,
                            height=22, preserveAspectRatio=True, mask="auto")
            except Exception:
                x_txt = 10
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x_txt, self.height - 18, self.titulo)
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor(COLOR_MARCA_HEADER))
        c.drawString(x_txt, self.height - 29, self.linea2[:110])
        if self.linea3:
            c.drawString(x_txt, self.height - 39, self.linea3[:110])
        c.restoreState()


class PieFlowable(Flowable):
    """Pie con línea + texto gris."""

    def __init__(self, texto: str, width: float = 170 * mm):
        super().__init__()
        self.texto = texto
        self.width = width
        self.height = 16

    def wrap(self, *args):
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(colors.HexColor(COLOR_LINEA))
        c.setLineWidth(0.5)
        c.line(0, 12, self.width, 12)
        c.setFillColor(colors.HexColor(COLOR_PIE))
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(0, 0, self.texto[:140])
        c.restoreState()
