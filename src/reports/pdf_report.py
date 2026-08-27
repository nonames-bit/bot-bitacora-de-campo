"""Generación de reportes PDF de la bitácora de campo zootécnico.

Contiene la lógica pura de recolección de datos (``recolectar_datos``) y la
construcción del documento PDF (``generar_pdf``) mediante reportlab.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Configuración de tablas de eventos (clave, tabla SQL, columna animal, resumen)
# --------------------------------------------------------------------------- #
def _resumen_parto(row: Any, _potreros: dict[int, str]) -> str:
    """Resumen de parto: 'cría <sexo>, <estado>, <peso> kg'."""
    partes = ["cría"]
    if row["sexo_cria"]:
        partes.append(str(row["sexo_cria"]))
    if row["estado_cria"]:
        partes.append(str(row["estado_cria"]))
    if row["peso_nacimiento"] is not None:
        partes.append(f"{row['peso_nacimiento']} kg")
    return ", ".join(partes)


def _resumen_celo(row: Any, _potreros: dict[int, str]) -> str:
    """Resumen de celo: turno AM/PM y notas."""
    partes = []
    if row["am_pm"]:
        partes.append(str(row["am_pm"]))
    if row["notas"]:
        partes.append(str(row["notas"]))
    return ", ".join(partes)


def _resumen_servicio(row: Any, _potreros: dict[int, str]) -> str:
    """Resumen de servicio: '<tipo> · toro/pajilla <X>'."""
    partes = []
    if row["tipo_servicio"]:
        partes.append(str(row["tipo_servicio"]))
    if row["toro_pajilla"]:
        partes.append(f"toro/pajilla {row['toro_pajilla']}")
    return " · ".join(partes)


def _resumen_tratamiento(row: Any, _potreros: dict[int, str]) -> str:
    """Resumen de tratamiento: producto, dosis, vía y retiro de carne."""
    partes = []
    if row["producto"]:
        partes.append(str(row["producto"]))
    if row["dosis"]:
        partes.append(str(row["dosis"]))
    if row["via"]:
        partes.append(str(row["via"]))
    if row["dias_retiro_carne"]:
        partes.append(f"retiro carne {row['dias_retiro_carne']} días")
    return ", ".join(partes)


def _resumen_pesaje(row: Any, _potreros: dict[int, str]) -> str:
    """Resumen de pesaje: '<peso> kg (GMD <x>)'."""
    if row["peso_kg"] is not None:
        texto = f"{row['peso_kg']} kg"
        if row["gmd_calculada"] is not None:
            texto += f" (GMD {row['gmd_calculada']})"
        return texto
    return ""


def _resumen_muerte(row: Any, _potreros: dict[int, str]) -> str:
    """Resumen de muerte: causa presunta o notas."""
    return str(row["causa_presunta"] or row["notas"] or "")


def _resumen_traslado(row: Any, potreros: dict[int, str]) -> str:
    """Resumen de traslado: 'origen -> destino' resolviendo potreros por id."""
    origen = potreros.get(int(row["potrero_origen"])) if row["potrero_origen"] is not None else None
    destino = potreros.get(int(row["potrero_destino"])) if row["potrero_destino"] is not None else None
    return f"{origen or 'sin definir'} -> {destino or 'sin definir'}"


def _resumen_movimiento(row: Any, _potreros: dict[int, str]) -> str:
    """Resumen de movimiento: tipo y procedencia/destino."""
    partes = []
    if row["tipo_movimiento"]:
        partes.append(str(row["tipo_movimiento"]))
    if row["procedencia_destino"]:
        partes.append(str(row["procedencia_destino"]))
    return " - ".join(partes)


# Orden canónico de aparición de los eventos en el reporte.
_TABLAS_EVENTOS: list[tuple[str, str, str, Any]] = [
    ("partos", "partos", "vaca_id", _resumen_parto),
    ("celos", "celos", "vaca_id", _resumen_celo),
    ("servicios", "servicios", "vaca_id", _resumen_servicio),
    ("tratamientos", "tratamientos", "animal_id", _resumen_tratamiento),
    ("traslados", "traslados", "animal_id", _resumen_traslado),
    ("pesajes", "pesajes", "animal_id", _resumen_pesaje),
    ("muertes", "muertes", "animal_id", _resumen_muerte),
    ("movimientos", "movimientos", "animal_id", _resumen_movimiento),
]

_ETIQUETAS_EVENTOS = {
    "partos": "Partos",
    "celos": "Celos",
    "servicios": "Servicios",
    "tratamientos": "Tratamientos",
    "traslados": "Traslados",
    "pesajes": "Pesajes",
    "muertes": "Muertes",
    "movimientos": "Movimientos",
}


# --------------------------------------------------------------------------- #
# Recolección de datos (lógica pura, testeable)
# --------------------------------------------------------------------------- #
def _potreros_por_id(db) -> dict[int, str]:
    """Devuelve un mapa id -> etiqueta legible (nombre o código) de potreros."""
    mapa: dict[int, str] = {}
    for r in db.query("SELECT id, codigo, nombre FROM potreros"):
        mapa[int(r["id"])] = r["nombre"] or r["codigo"] or str(r["id"])
    return mapa


def _recolectar_tabla(
    db, tabla: str, col_animal: str, resumen_fn, potreros: dict[int, str],
    desde_iso: str, hasta_iso: str,
) -> list[dict[str, str]]:
    """Recolecta filas (fecha, tag, resumen) de una tabla en el período dado."""
    sql = (
        f"SELECT t.*, a.tag AS tag "
        f"FROM {tabla} t "
        f"LEFT JOIN animales a ON a.id_animal = t.{col_animal} "
        f"WHERE t.fecha >= ? AND t.fecha <= ? "
        f"ORDER BY t.fecha ASC, t.id ASC"
    )
    filas: list[dict[str, str]] = []
    for r in db.query(sql, (desde_iso, hasta_iso)):
        filas.append({
            "fecha": r["fecha"] or "",
            "tag": r["tag"] or "?",
            "resumen": resumen_fn(r, potreros),
        })
    return filas


def recolectar_datos(db, dias: int, hoy: Optional[date] = None) -> dict:
    """Recolecta inventario, eventos del período y alertas próximas.

    Devuelve un diccionario con:
      - "inventario": conteos de activos, hembras, machos e histórico total.
      - "periodo": fechas ISO ``desde`` y ``hasta`` (inclusive).
      - "eventos": por tabla, lista de filas {fecha, tag, resumen}.
      - "alertas": alertas PENDIENTE con fecha_programada <= hoy+7.
    """
    if hoy is None:
        hoy = date.today()
    desde = hoy - timedelta(days=dias - 1)
    desde_iso = desde.isoformat()
    hasta_iso = hoy.isoformat()

    # Inventario.
    row_activos = db.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO'")
    activos = int(row_activos["n"]) if row_activos else 0
    row_hembras = db.query_one(
        "SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO' AND sexo = 'Hembra'"
    )
    hembras = int(row_hembras["n"]) if row_hembras else 0
    row_machos = db.query_one(
        "SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO' AND sexo = 'Macho'"
    )
    machos = int(row_machos["n"]) if row_machos else 0
    historico_total = db.count("animales")

    # Eventos del período (solo tablas con filas).
    potreros = _potreros_por_id(db)
    eventos: dict[str, list[dict[str, str]]] = {}
    for clave, tabla, col_animal, resumen_fn in _TABLAS_EVENTOS:
        filas = _recolectar_tabla(db, tabla, col_animal, resumen_fn, potreros, desde_iso, hasta_iso)
        if filas:
            eventos[clave] = filas

    # Alertas PENDIENTE con fecha_programada <= hoy+7.
    limite_alertas = (hoy + timedelta(days=7)).isoformat()
    filas_alertas = db.query(
        "SELECT a.fecha_programada, a.tipo_alerta, an.tag "
        "FROM alertas a "
        "LEFT JOIN animales an ON an.id_animal = a.animal_id "
        "WHERE a.estado = 'PENDIENTE' AND a.fecha_programada <= ? "
        "ORDER BY a.fecha_programada ASC",
        (limite_alertas,),
    )
    alertas = [
        {
            "tag": r["tag"] or "?",
            "tipo": r["tipo_alerta"] or "ALERTA",
            "fecha": r["fecha_programada"] or "",
        }
        for r in filas_alertas
    ]

    return {
        "inventario": {
            "activos": activos,
            "hembras": hembras,
            "machos": machos,
            "historico_total": historico_total,
        },
        "periodo": {"desde": desde_iso, "hasta": hasta_iso},
        "eventos": eventos,
        "alertas": alertas,
    }


# --------------------------------------------------------------------------- #
# Generación del PDF (reportlab)
# --------------------------------------------------------------------------- #
def generar_pdf(db, dias: int, ruta_salida: str, hoy: Optional[date] = None) -> str:
    """Genera un PDF con el reporte de campo y devuelve su ruta.

    Usa tipografías base (Helvetica) y texto plano sin emojis. Crea el
    directorio padre de ``ruta_salida`` si no existe.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    datos = recolectar_datos(db, dias, hoy)
    fecha_hoy = hoy if hoy is not None else date.today()

    dir_padre = os.path.dirname(os.path.abspath(ruta_salida))
    if dir_padre:
        os.makedirs(dir_padre, exist_ok=True)

    doc = SimpleDocTemplate(
        ruta_salida,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Reporte de campo",
    )

    base = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloReporte", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=16, textColor=colors.HexColor("#333333"), spaceAfter=2,
    )
    estilo_subtitulo = ParagraphStyle(
        "SubtituloReporte", parent=base["Normal"], fontName="Helvetica",
        fontSize=10, textColor=colors.HexColor("#666666"), spaceAfter=12,
    )
    estilo_seccion = ParagraphStyle(
        "SeccionReporte", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, textColor=colors.HexColor("#333333"),
        spaceBefore=12, spaceAfter=6,
    )
    estilo_normal = ParagraphStyle(
        "NormalReporte", parent=base["Normal"], fontName="Helvetica",
        fontSize=10, textColor=colors.HexColor("#333333"),
    )
    estilo_pie = ParagraphStyle(
        "PieReporte", parent=base["Normal"], fontName="Helvetica-Oblique",
        fontSize=8, textColor=colors.HexColor("#999999"), spaceBefore=16,
    )

    # Encabezado.
    story = [Paragraph("Reporte de campo — Finca", estilo_titulo)]
    story.append(Paragraph(
        f"Período: {datos['periodo']['desde']} al {datos['periodo']['hasta']} · Generado: {fecha_hoy.isoformat()}",
        estilo_subtitulo,
    ))

    # Inventario.
    inv = datos["inventario"]
    story.append(Paragraph("Inventario de animales", estilo_seccion))
    story.append(Paragraph(
        f"Activos: {inv['activos']} (Hembras: {inv['hembras']} · Machos: {inv['machos']}) · "
        f"Histórico total: {inv['historico_total']}",
        estilo_normal,
    ))

    # Tablas por evento.
    for clave, _tabla, _col, _fn in _TABLAS_EVENTOS:
        filas = datos["eventos"].get(clave)
        if not filas:
            continue
        story.append(Paragraph(_ETIQUETAS_EVENTOS[clave], estilo_seccion))
        tabla_datos = [["Fecha", "Animal", "Detalle"]]
        for f in filas:
            tabla_datos.append([f["fecha"], f["tag"], f["resumen"]])
        tabla = Table(tabla_datos, colWidths=[30 * mm, 24 * mm, 116 * mm])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tabla)

    # Alertas próximas 7 días.
    story.append(Paragraph("Alertas próximas 7 días", estilo_seccion))
    alertas = datos["alertas"]
    if alertas:
        tabla_datos = [["Fecha", "Animal", "Tipo"]]
        for a in alertas:
            tabla_datos.append([a["fecha"], a["tag"], a["tipo"]])
        tabla = Table(tabla_datos, colWidths=[30 * mm, 24 * mm, 116 * mm])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tabla)
    else:
        story.append(Paragraph("Sin alertas programadas.", estilo_normal))

    # Pie.
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Generado por el bot de bitácora — para registro manual en Software Ganadero",
        estilo_pie,
    ))

    doc.build(story)
    return ruta_salida
