"""Generación de reportes PDF de la bitácora de campo zootécnico.

Contiene la lógica pura de recolección de datos (``recolectar_datos``) y la
construcción del documento PDF (``generar_pdf``) mediante reportlab.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Optional

# Paleta institucional GANADERÍA JA (verde pasto oscuro + acentos armónicos).
_COLOR_MARCA = "#2F5233"
_COLOR_MARCA_CLARA = "#E7EFE8"
_COLOR_MARCA_ZEBRA = "#F3F7F3"
_COLOR_TIERRA = "#8D6E63"
_COLOR_GRIS = "#78909C"
_COLOR_VERDE = "#2e7d32"
_COLOR_ROJO = "#c62828"


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

    from ..engine.query_engine import calcular_existencias_potreros_sg
    potreros_sg = calcular_existencias_potreros_sg(db, hoy)

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
        "potreros_sg": potreros_sg,
    }


# --------------------------------------------------------------------------- #
# Generación del PDF (reportlab)
# --------------------------------------------------------------------------- #
def generar_pdf(db, dias: int, ruta_salida: str, hoy: Optional[date] = None) -> str:
    """Genera un PDF con el reporte de campo y devuelve su ruta.

    Usa tipografías base (Helvetica) y texto plano sin emojis. Crea el
    directorio padre de ``ruta_salida`` si no existe.
    """
    import shutil
    import tempfile

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    from ..engine.charts import (
        generar_grafico_categorias,
        generar_grafico_estado_reproductivo_hato,
        generar_grafico_evolucion_rebano,
        generar_grafico_ocupacion_potreros,
        graficos_disponibles,
    )

    def _imagen_ajustada(ruta: str, ancho_mm: float) -> Image:
        """Flowable Image escalada a ``ancho_mm`` preservando la proporción
        real del PNG (evita estirar/achatar los gráficos de matplotlib)."""
        iw, ih = ImageReader(ruta).getSize()
        alto_mm = ancho_mm * (ih / iw)
        return Image(ruta, width=ancho_mm * mm, height=alto_mm * mm)

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
        fontSize=15, textColor=colors.HexColor(_COLOR_MARCA), spaceAfter=2,
    )
    estilo_subtitulo = ParagraphStyle(
        "SubtituloReporte", parent=base["Normal"], fontName="Helvetica",
        fontSize=9, textColor=colors.HexColor("#555555"), spaceAfter=6,
    )
    estilo_seccion = ParagraphStyle(
        "SeccionReporte", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, textColor=colors.HexColor(_COLOR_MARCA),
        spaceBefore=10, spaceAfter=4,
    )
    estilo_subseccion_grafico = ParagraphStyle(
        "SubseccionGrafico", parent=base["Normal"], fontName="Helvetica-Bold",
        fontSize=8.5, textColor=colors.HexColor(_COLOR_MARCA), spaceAfter=2,
    )
    estilo_normal = ParagraphStyle(
        "NormalReporte", parent=base["Normal"], fontName="Helvetica",
        fontSize=9, textColor=colors.HexColor("#333333"),
    )
    estilo_pie = ParagraphStyle(
        "PieReporte", parent=base["Normal"], fontName="Helvetica-Oblique",
        fontSize=8, textColor=colors.HexColor("#888888"), spaceBefore=14,
    )

    # Buscar logo si existe
    logo_path = None
    candidatos_logo = [
        "docs/GanaderiaJA_Logo.jpg",
        "media/GanaderiaJA_Logo.jpg",
        os.path.join(os.path.dirname(__file__), "../../docs/GanaderiaJA_Logo.jpg"),
    ]
    for cand in candidatos_logo:
        if os.path.exists(cand):
            logo_path = cand
            break

    # Encabezado con logo
    if logo_path:
        img = Image(logo_path, width=20 * mm, height=20 * mm)
        texto_enc = [
            Paragraph("GANADERÍA JA", estilo_titulo),
            Paragraph(f"Bitácora de Campo Zootécnico & Software Ganadero (SG) · Generado: {fecha_hoy.isoformat()}", estilo_subtitulo),
            Paragraph(f"Período: {datos['periodo']['desde']} al {datos['periodo']['hasta']}", estilo_normal),
        ]
        enc_table = Table([[img, texto_enc]], colWidths=[24 * mm, 146 * mm])
        enc_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story = [enc_table]
    else:
        story = [Paragraph("Reporte de campo — Ganadería JA", estilo_titulo)]
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

    # Existencias por potrero (Software Ganadero SG)
    potreros_sg = datos.get("potreros_sg", [])
    if potreros_sg:
        story.append(Paragraph("Existencias por potrero (Software Ganadero)", estilo_seccion))
        tabla_pot_datos = [["Potrero", "CH", "HL", "NV", "VP", "VS", "CM", "ML", "MC", "Rep", "Total"]]
        for p in potreros_sg:
            def v(n: int) -> str: return str(n) if n > 0 else "-"
            tabla_pot_datos.append([
                p["display"][:18],
                v(p["ch"]), v(p["hl"]), v(p["nv"]), v(p["vp"]), v(p["vs"]),
                v(p["cm"]), v(p["ml"]), v(p["mc"]), v(p["rep"]),
                str(p["total"]),
            ])
        tot_ch = sum(p["ch"] for p in potreros_sg)
        tot_hl = sum(p["hl"] for p in potreros_sg)
        tot_nv = sum(p["nv"] for p in potreros_sg)
        tot_vp = sum(p["vp"] for p in potreros_sg)
        tot_vs = sum(p["vs"] for p in potreros_sg)
        tot_cm = sum(p["cm"] for p in potreros_sg)
        tot_ml = sum(p["ml"] for p in potreros_sg)
        tot_mc = sum(p["mc"] for p in potreros_sg)
        tot_rep = sum(p["rep"] for p in potreros_sg)
        tot_gen = sum(p["total"] for p in potreros_sg)
        def vt(n: int) -> str: return str(n) if n > 0 else "-"
        tabla_pot_datos.append([
            "Totales...",
            vt(tot_ch), vt(tot_hl), vt(tot_nv), vt(tot_vp), vt(tot_vs),
            vt(tot_cm), vt(tot_ml), vt(tot_mc), vt(tot_rep),
            str(tot_gen),
        ])

        tabla_p = Table(
            tabla_pot_datos,
            colWidths=[40 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm]
        )
        tabla_p.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_COLOR_MARCA_CLARA)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_COLOR_MARCA)),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D7E5D9")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor(_COLOR_MARCA_ZEBRA)]),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(tabla_p)

    # Gráficos (opcionales: si matplotlib no está disponible en el servidor,
    # el reporte se genera igual, solo sin esta sección).
    tmp_charts_dir = None
    if graficos_disponibles():
        tmp_charts_dir = tempfile.mkdtemp(prefix="bitacora_reporte_charts_")
        candidatos = [
            ("Distribución del Hato", lambda: generar_grafico_categorias(db, output_dir=tmp_charts_dir, hoy=fecha_hoy, dpi=130)),
            ("Evolución del Rebaño (6m)", lambda: generar_grafico_evolucion_rebano(db, meses=6, output_dir=tmp_charts_dir, hoy=fecha_hoy, dpi=130)),
            ("Ocupación de Potreros (Voisin)", lambda: generar_grafico_ocupacion_potreros(db, output_dir=tmp_charts_dir, hoy=fecha_hoy, dpi=130)),
            ("Estado Reproductivo", lambda: generar_grafico_estado_reproductivo_hato(db, output_dir=tmp_charts_dir, hoy=fecha_hoy, dpi=130)),
        ]
        graficos_embebidos = []
        for tit_cand, fn_cand in candidatos:
            if len(graficos_embebidos) >= 4:
                break
            try:
                ruta_cand = fn_cand()
                if ruta_cand and os.path.exists(ruta_cand):
                    graficos_embebidos.append((tit_cand, ruta_cand))
            except Exception:
                pass

        if graficos_embebidos:
            story.append(Paragraph("Gráficos de gestión", estilo_seccion))
            if len(graficos_embebidos) == 1:
                story.append(Paragraph(graficos_embebidos[0][0], estilo_subseccion_grafico))
                story.append(_imagen_ajustada(graficos_embebidos[0][1], 165))
                story.append(Spacer(1, 4))
            else:
                filas_tabla_graficos = []
                for i in range(0, len(graficos_embebidos), 2):
                    par = graficos_embebidos[i : i + 2]
                    celda_izq = [
                        Paragraph(par[0][0], estilo_subseccion_grafico),
                        _imagen_ajustada(par[0][1], 80),
                    ]
                    if len(par) > 1:
                        celda_der = [
                            Paragraph(par[1][0], estilo_subseccion_grafico),
                            _imagen_ajustada(par[1][1], 80),
                        ]
                    else:
                        celda_der = ""
                    filas_tabla_graficos.append([celda_izq, celda_der])

                tabla_g = Table(filas_tabla_graficos, colWidths=[85 * mm, 85 * mm])
                tabla_g.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(tabla_g)
                story.append(Spacer(1, 4))

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
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_COLOR_MARCA_CLARA)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_COLOR_MARCA)),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(_COLOR_MARCA_ZEBRA)]),
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
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_COLOR_MARCA_CLARA)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_COLOR_MARCA)),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(_COLOR_MARCA_ZEBRA)]),
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
    if tmp_charts_dir:
        shutil.rmtree(tmp_charts_dir, ignore_errors=True)
    return ruta_salida
