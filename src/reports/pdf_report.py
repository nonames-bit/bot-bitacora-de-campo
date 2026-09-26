"""Generación de reportes PDF de la bitácora de campo zootécnico.

Contiene la lógica pura de recolección de datos (``recolectar_datos``) y la
construcción del documento PDF (``generar_pdf``) mediante reportlab.

Línea visual unificada con la ficha individual (ver ``estilo_ja.py``):
franja verde sólida, bandas de sección, tablas header verde / zebra y
pie con línea.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta
from typing import Any, Optional

from .pdf_secciones import (
    SECCIONES,
    ContextoReporte,
    graficos_clave,
    seccion_finanzas,
    seccion_inventario,
    seccion_leche,
    seccion_pasturas,
    seccion_reproduccion,
    seccion_sanidad,
    tablero_ejecutivo,
)
from .estilo_ja import (
    COLOR_GRIS,
    COLOR_LINEA,
    COLOR_MARCA,
    COLOR_MARCA_ZEBRA,
    COLOR_TOTALES_BG,
    buscar_logo_path,
    crear_bloque_kpis,
    dibujar_fondo_pagina,
    dibujar_running_footer,
    dibujar_running_header,
    estilo_normal,
    SeccionFlowable,
    tabla_encabezado_franja,
    tabla_pie,
    tabla_style_alertas,
    tabla_style_moderna,
    tabla_style_potreros,
)


logger = logging.getLogger(__name__)


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
        "AND (a.animal_id IS NULL OR an.estado = 'ACTIVO') "
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

    # Finanzas del período del reporte (mismo rango que "eventos", no el año
    # completo): utilidad/margen semanal, no el acumulado anual de la PWA.
    try:
        resumen_finanzas = db.resumen_finanzas(desde_iso, hasta_iso)
        kpis_finanzas = db.kpis_financieros(desde_iso, hasta_iso)
    except Exception:
        resumen_finanzas = None
        kpis_finanzas = None

    # Clima: mismo pronóstico Open-Meteo del Despacho Matutino/PWA (Pasturas)
    # y misma alerta SPI de sequía -- no se recalculan aparte para el PDF.
    try:
        from ..engine.pronostico import obtener_pronostico_para_despacho, interpretar_pronostico
        _pron = obtener_pronostico_para_despacho(db)
        recomendaciones_clima = interpretar_pronostico(_pron) if _pron else []
    except Exception:
        recomendaciones_clima = []
    try:
        spi_sequia = [dict(r) for r in db.ultimos_spi_sequia()]
    except Exception:
        spi_sequia = []

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
        "finanzas": {"resumen": resumen_finanzas, "kpis": kpis_finanzas},
        "clima": {"recomendaciones": recomendaciones_clima},
        "spi_sequia": spi_sequia,
    }


# --------------------------------------------------------------------------- #
# Generación del PDF (reportlab, línea visual ficha JA)
# --------------------------------------------------------------------------- #
def generar_pdf(
    db,
    dias: int = 7,
    ruta_salida: Optional[str] = None,
    hoy: Optional[date] = None,
    periodo: Optional[str] = None,
    seccion: Optional[str] = None,
) -> str:
    """Genera un PDF con el reporte de campo y devuelve su ruta.

    Usa tipografías base (Helvetica) y texto plano sin emojis. Crea el
    directorio padre de ``ruta_salida`` si no existe.
    """
    import shutil
    import tempfile
    import time

    if periodo:
        p_lower = str(periodo).lower().strip()
        if p_lower in ("semanal", "semana", "7d"):
            dias = 7
        elif p_lower in ("quincenal", "quincena", "15d"):
            dias = 15
        elif p_lower in ("mensual", "mes", "30d"):
            dias = 30
        else:
            try:
                num = int(re.sub(r"\D", "", p_lower))
                if num > 0:
                    dias = num
            except Exception:
                pass

    if not ruta_salida:
        os.makedirs(os.path.join("data", "reportes"), exist_ok=True)
        hoy_str = (hoy or date.today()).isoformat()
        ruta_salida = os.path.join("data", "reportes", f"reporte_finca_{dias}d_{hoy_str}_{int(time.time())}.pdf")

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    from ..engine.charts import graficos_disponibles

    datos = recolectar_datos(db, dias, hoy)
    fecha_hoy = hoy if hoy is not None else date.today()

    dir_padre = os.path.dirname(os.path.abspath(ruta_salida))
    if dir_padre:
        os.makedirs(dir_padre, exist_ok=True)

    ANCHO_UTIL = 174 * mm

    def _primera_pagina_canvas(c, doc) -> None:
        """En la primera página el encabezado ya está en el flujo Platypus (tabla_encabezado_franja).
        Dibujamos el fondo de hoja ejecutivo, marco con esquineros, marca de agua y pie."""
        dibujar_fondo_pagina(c, doc.pagesize[0], doc.pagesize[1], incluir_marco=True, incluir_marca_agua=True)
        dibujar_running_footer(c, doc, "Ganadería JA · Bitácora Zootécnica Oficial · Documento Certificado")

    def _paginas_posteriores_canvas(c, doc) -> None:
        """En páginas 2+, dibuja fondo de hoja ejecutivo, cabecera compacta y pie institucional."""
        dibujar_fondo_pagina(c, doc.pagesize[0], doc.pagesize[1], incluir_marco=True, incluir_marca_agua=True)
        p_str = f"Período: {datos['periodo']['desde']} al {datos['periodo']['hasta']}  ·  Emisión: {fecha_hoy.isoformat()}"
        dibujar_running_header(c, doc, titulo_doc.upper(), p_str)
        dibujar_running_footer(c, doc, "Ganadería JA · Bitácora Zootécnica Oficial · Documento Certificado")

    doc = SimpleDocTemplate(
        ruta_salida,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=26 * mm,
        bottomMargin=18 * mm,
        title="Reporte de campo — Ganadería JA",
    )

    est_normal = estilo_normal()

    logo_path = buscar_logo_path()

    sec_clean = str(seccion or "").strip().lower()
    if sec_clean in ("leche", "produccion"):
        titulo_doc = "GANADERÍA JA · Informe de Producción Lechera"
        sub1_doc = f"MÓDULO DE LECHE  |  SISTEMA OFICIAL GANADERÍA JA · Generado: {fecha_hoy.isoformat()}"
        sub2_doc = f"TANQUE DIARIO  |  Período evaluado: {datos['periodo']['desde']} al {datos['periodo']['hasta']}"
    elif sec_clean in ("finanzas", "caja"):
        titulo_doc = "GANADERÍA JA · Informe Financiero y Flujo de Caja"
        sub1_doc = f"MÓDULO FINANCIERO  |  SISTEMA OFICIAL GANADERÍA JA · Generado: {fecha_hoy.isoformat()}"
        sub2_doc = f"INGRESOS Y EGRESOS  |  Período evaluado: {datos['periodo']['desde']} al {datos['periodo']['hasta']}"
    elif sec_clean in ("pasturas", "potreros"):
        titulo_doc = "GANADERÍA JA · Informe de Potreros y Pasturas (Voisin)"
        sub1_doc = f"PASTURAS Y ROTACIÓN  |  SISTEMA OFICIAL GANADERÍA JA · Generado: {fecha_hoy.isoformat()}"
        sub2_doc = f"OCUPACIÓN Y REPOSO  |  Período evaluado: {datos['periodo']['desde']} al {datos['periodo']['hasta']}"
    elif sec_clean in ("sanidad", "tratamientos"):
        titulo_doc = "GANADERÍA JA · Informe Sanitario y Tratamientos"
        sub1_doc = f"CONTROL VETERINARIO  |  SISTEMA OFICIAL GANADERÍA JA · Generado: {fecha_hoy.isoformat()}"
        sub2_doc = f"HISTORIAL CLÍNICO Y RETIROS  |  Período evaluado: {datos['periodo']['desde']} al {datos['periodo']['hasta']}"
    elif sec_clean in ("repro", "reproduccion"):
        titulo_doc = "GANADERÍA JA · Informe Reproductivo del Hato"
        sub1_doc = f"REPRODUCCIÓN Y GENÉTICA  |  SISTEMA OFICIAL GANADERÍA JA · Generado: {fecha_hoy.isoformat()}"
        sub2_doc = f"SERVICIOS, TACTOS Y PAJUELAS  |  Período evaluado: {datos['periodo']['desde']} al {datos['periodo']['hasta']}"
    elif sec_clean in ("inventario", "hato"):
        titulo_doc = "GANADERÍA JA · Informe de Inventario de Ganado"
        sub1_doc = f"CENSO GANADERO  |  SISTEMA OFICIAL GANADERÍA JA · Generado: {fecha_hoy.isoformat()}"
        sub2_doc = f"HATO ACTIVO  |  Corte a la fecha: {fecha_hoy.isoformat()}"
    else:
        titulo_doc = "GANADERÍA JA · Informe Zootécnico de Campo"
        sub1_doc = f"BITÁCORA DE CAMPO  |  SISTEMA OFICIAL GANADERÍA JA · Generado: {fecha_hoy.isoformat()}"
        sub2_doc = f"HATO ACTIVO  |  Período evaluado: {datos['periodo']['desde']} al {datos['periodo']['hasta']}"

    # Encabezado ejecutivo: franja verde sólida en flujo principal de página 1.
    story = [
        tabla_encabezado_franja(
            titulo_doc,
            sub1_doc,
            sub2_doc,
            ancho_total=ANCHO_UTIL,
            logo_path=logo_path,
        ),
        Spacer(1, 6),
    ]

    def _tabla_evento(filas_datos, anchos):
        """Tabla de evento con estilo moderno y legibilidad superior."""
        tabla = Table(filas_datos, colWidths=anchos, repeatRows=1)
        tabla.setStyle(tabla_style_moderna())
        return tabla

    def _bloque_inventario() -> None:
        # Resumen Ejecutivo e Inventario (Tarjetas KPI)
        inv = datos["inventario"]
        activos = inv.get("activos", 0)
        hembras = inv.get("hembras", 0)
        machos = inv.get("machos", 0)
        pct_h = f"{(hembras / activos * 100):.1f}% del hato" if activos > 0 else ""
        pct_m = f"{(machos / activos * 100):.1f}% del hato" if activos > 0 else ""

        # Solo datos actuales del hato activo -- el acumulado histórico (todos
        # los registros desde que se empezó a importar Software Ganadero, sin
        # importar si siguen activos) confundía al usuario haciéndole pensar que
        # había 1.141 animales en la finca hoy, en vez de los 328 reales.
        kpis_bloque = [
            (str(activos), "Hato Activo", "Cabezas en finca", COLOR_MARCA),
            (str(hembras), "Hembras", pct_h or "Vacas / Novillas", "#047857"),
            (str(machos), "Machos", pct_m or "Toros / Levante", "#1D4ED8"),
        ]
        story.append(SeccionFlowable("RESUMEN EJECUTIVO & INVENTARIO (HATO ACTIVO)", width=ANCHO_UTIL))
        story.append(Spacer(1, 3))
        story.append(crear_bloque_kpis(kpis_bloque, ancho_total=ANCHO_UTIL))
        story.append(Spacer(1, 6))

        # Existencias por potrero
        potreros_sg = datos.get("potreros_sg", [])
        if potreros_sg:
            story.append(SeccionFlowable("EXISTENCIAS POR POTRERO (DISTRIBUCIÓN ZOOTÉCNICA)", width=ANCHO_UTIL))
            story.append(Spacer(1, 3))
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
                "Totales Generales",
                vt(tot_ch), vt(tot_hl), vt(tot_nv), vt(tot_vp), vt(tot_vs),
                vt(tot_cm), vt(tot_ml), vt(tot_mc), vt(tot_rep),
                str(tot_gen),
            ])

            tabla_p = Table(
                tabla_pot_datos,
                colWidths=[44 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm],
                repeatRows=1,
            )
            tabla_p.setStyle(tabla_style_potreros())
            tabla_p.setStyle(TableStyle([
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(COLOR_TOTALES_BG)),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor(COLOR_MARCA)),
                ("LINEABOVE", (0, -1), (-1, -1), 1.0, colors.HexColor(COLOR_MARCA)),
            ]))
            story.append(tabla_p)

            # Glosario técnico explicativo de categorías
            est_glosario = ParagraphStyle(
                "JA_Glosario", parent=getSampleStyleSheet()["Normal"], fontName="Helvetica",
                fontSize=6.8, leading=8.5, textColor=colors.HexColor(COLOR_GRIS), alignment=1
            )
            txt_glosario = (
                "<b>Glosario SG:</b> "
                "<b>CH:</b> Cría Hembra · <b>HL:</b> Hembra Levante · <b>NV:</b> Novilla Vientre · "
                "<b>VP:</b> Vaca Parida · <b>VS:</b> Vaca Seca · <b>CM:</b> Cría Macho · "
                "<b>ML:</b> Macho Levante · <b>MC:</b> Macho Ceba · <b>Rep:</b> Reproductor"
            )
            story.append(Spacer(1, 2))
            story.append(Table([[Paragraph(txt_glosario, est_glosario)]], colWidths=[ANCHO_UTIL],
                               style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(COLOR_MARCA_ZEBRA)),
                                      ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(COLOR_LINEA)),
                                      ("TOPPADDING", (0, 0), (-1, -1), 3),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            story.append(Spacer(1, 5))


    def _bloque_clima() -> None:
        # Clima: pronóstico Open-Meteo (recomendaciones prácticas) + Alerta
        # Temprana de Sequía (SPI 30/60/90d vs climatología histórica CHIRPS).
        clima = datos.get("clima") or {}
        recs_clima = clima.get("recomendaciones") or []
        spi_rows = datos.get("spi_sequia") or []
        if recs_clima or spi_rows:
            story.append(SeccionFlowable("CLIMA & ALERTA TEMPRANA DE SEQUÍA", width=ANCHO_UTIL))
            story.append(Spacer(1, 3))
            if recs_clima:
                for r in recs_clima:
                    r_clean = re.sub(r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\ufe0f\u25a0\u25aa\u25b6]", "", str(r)).strip()
                    story.append(Paragraph(f"• {r_clean}", est_normal))
                story.append(Spacer(1, 3))
            if spi_rows:
                tabla_spi_datos = [["Ventana", "SPI", "Clasificación", "Lluvia acumulada"]]
                for s in spi_rows:
                    spi_v = s.get("spi_valor")
                    tabla_spi_datos.append([
                        f"{s.get('dias_ventana')} días",
                        f"{spi_v:.2f}" if spi_v is not None else "—",
                        s.get("clasificacion") or "Sin datos",
                        f"{s.get('mm_actual')} mm" if s.get("mm_actual") is not None else "—",
                    ])
                story.append(_tabla_evento(tabla_spi_datos, [28 * mm, 22 * mm, 60 * mm, 40 * mm]))
            story.append(Spacer(1, 5))


    def _bloque_eventos(claves: Optional[set] = None) -> None:
        # Tablas por evento (cada una con su banda de sección).
        for clave, _tabla, _col, _fn in _TABLAS_EVENTOS:
            filas = datos["eventos"].get(clave)
            if not filas or (claves is not None and clave not in claves):
                continue
            story.append(SeccionFlowable(f"REGISTRO DE {_ETIQUETAS_EVENTOS[clave].upper()} EN EL PERÍODO", width=ANCHO_UTIL))
            story.append(Spacer(1, 2))
            tabla_datos = [["Fecha", "Animal", "Detalle"]]
            for f in filas:
                tabla_datos.append([
                    f["fecha"],
                    Paragraph(f"<b>{f['tag']}</b>", est_normal),
                    Paragraph(str(f["resumen"] or ""), est_normal),
                ])
            story.append(_tabla_evento(tabla_datos, [28 * mm, 26 * mm, 120 * mm]))
            story.append(Spacer(1, 3))


    def _bloque_alertas(tipos: Optional[tuple] = None) -> None:
        # Alertas próximas 7 días (tratamiento ficha: header de alerta).
        story.append(SeccionFlowable("ALERTAS Y COMPROMISOS PRÓXIMOS 7 DÍAS", alerta=True, width=ANCHO_UTIL))
        story.append(Spacer(1, 3))
        alertas = [a for a in datos["alertas"]
                   if tipos is None or any(t in str(a["tipo"]).upper() for t in tipos)]
        if alertas:
            tabla_datos = [["Fecha", "Animal", "Tipo"]]
            for a in alertas:
                tabla_datos.append([
                    a["fecha"],
                    Paragraph(f"<b>{a['tag']}</b>", est_normal),
                    Paragraph(str(a["tipo"] or ""), est_normal),
                ])
            tabla = Table(tabla_datos, colWidths=[28 * mm, 26 * mm, 120 * mm], repeatRows=1)
            tabla.setStyle(tabla_style_alertas())
            story.append(tabla)
        else:
            est_alerta_ok = ParagraphStyle(
                "JA_AlertOk", parent=est_normal, fontName="Helvetica-Bold",
                fontSize=8.5, leading=11, textColor=colors.HexColor("#065F46")
            )
            callout_ok = Table([[
                Paragraph("✓ SIN ALERTAS PENDIENTES: no hay compromisos programados para los próximos 7 días.", est_alerta_ok)
            ]], colWidths=[ANCHO_UTIL])
            callout_ok.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ECFDF5")),
                ("LINEBEFORE", (0, 0), (0, -1), 3.5, colors.HexColor("#10B981")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#A7F3D0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(callout_ok)


    # Directorio temporal para los gráficos (se borra al terminar el PDF).
    tmp_charts_dir = tempfile.mkdtemp(prefix="bitacora_reporte_charts_") if graficos_disponibles() else None
    ctx = ContextoReporte(
        db=db, hoy=fecha_hoy, desde=date.fromisoformat(datos["periodo"]["desde"]),
        hasta=date.fromisoformat(datos["periodo"]["hasta"]), dias=dias, tmp_dir=tmp_charts_dir, ancho=ANCHO_UTIL,
    )

    def _seguro(fn, *args, **kw) -> list:
        """Una sección que falla no tumba el informe: se omite y queda en el log."""
        try:
            return fn(*args, **kw)
        except Exception:
            logger.exception("Sección del PDF omitida por error: %s", getattr(fn, "__name__", fn))
            return []

    constructor = SECCIONES.get(sec_clean)
    if constructor is not None:
        # Informe de una sección: su contenido específico completo.
        if constructor is seccion_inventario:
            _bloque_inventario()
        story.extend(_seguro(constructor, ctx))
        eventos_por_seccion = {
            seccion_leche: set(),
            seccion_reproduccion: {"partos", "celos", "servicios"},
            seccion_sanidad: {"tratamientos", "muertes"},
            seccion_pasturas: {"traslados"},
            seccion_inventario: {"partos", "muertes", "movimientos", "pesajes"},
            seccion_finanzas: set(),
        }
        alertas_por_seccion = {
            seccion_leche: ("SECADO", "RETIRO_LECHE"),
            seccion_reproduccion: ("ECOGRAFIA", "PALPACION", "INSEMINACION", "PARTO", "SECADO"),
            seccion_sanidad: ("RETIRO", "VACUNA", "TRATAMIENTO"),
        }
        if constructor is seccion_pasturas:
            _bloque_clima()
        _bloque_eventos(eventos_por_seccion.get(constructor, set()))
        if constructor in alertas_por_seccion:
            _bloque_alertas(alertas_por_seccion[constructor])
    else:
        # Informe general: tablero ejecutivo + resumen de cada área + detalle.
        _bloque_inventario()
        story.extend(_seguro(tablero_ejecutivo, ctx))
        for fn in (seccion_leche, seccion_reproduccion, seccion_sanidad, seccion_pasturas, seccion_finanzas):
            story.extend(_seguro(fn, ctx, compacto=True))
        story.extend(_seguro(graficos_clave, ctx))
        _bloque_clima()
        _bloque_eventos()
        _bloque_alertas()

    # Pie institucional de cierre
    story.append(Spacer(1, 8))
    story.append(tabla_pie(
        "Bitácora de Campo Ganadería JA — Generado automáticamente para control zootécnico y conciliación contable/SG",
        ancho=ANCHO_UTIL,
    ))

    doc.build(story, onFirstPage=_primera_pagina_canvas, onLaterPages=_paginas_posteriores_canvas)
    if tmp_charts_dir:
        shutil.rmtree(tmp_charts_dir, ignore_errors=True)
    return ruta_salida
