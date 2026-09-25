"""Contenido específico de cada informe PDF por sección (leche, reproducción,
sanidad, pasturas, finanzas, inventario) y el tablero ejecutivo del informe
general.

Cada ``seccion_*`` devuelve una lista de flowables de reportlab lista para
agregarse al ``story`` de :func:`src.reports.pdf_report.generar_pdf`. Los datos
salen de las mismas funciones que usa la PWA (``dashboard_data``, KPIs de
``Database`` y gráficos de ``engine.charts``) para que el PDF y la pantalla
nunca muestren cifras distintas. Todo lo "presente" filtra el hato ACTIVO.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import CondPageBreak, Image, Paragraph, Spacer, Table, TableStyle

from .estilo_ja import (
    COLOR_AMBAR,
    COLOR_AMBAR_BG,
    COLOR_AMBAR_TXT,
    COLOR_BORDE_SUAVE,
    COLOR_GRIS,
    COLOR_MARCA,
    COLOR_ROJO_ALERTA,
    COLOR_ALERTA_BG,
    COLOR_ALERTA_TXT,
    COLOR_VERDE_OK,
    COLOR_VERDE_OK_BG,
    SeccionFlowable,
    crear_bloque_kpis,
    estilo_normal,
    estilo_subseccion_grafico,
    tabla_style_moderna,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Contexto y utilidades comunes
# --------------------------------------------------------------------------- #
@dataclass
class ContextoReporte:
    """Datos compartidos por todas las secciones de un informe."""
    db: Any
    hoy: date
    desde: date
    hasta: date
    dias: int
    tmp_dir: Optional[str]
    ancho: float

    @property
    def desde_iso(self) -> str:
        return self.desde.isoformat()

    @property
    def hasta_iso(self) -> str:
        return self.hasta.isoformat()

    @property
    def anterior(self) -> tuple[str, str]:
        """Período anterior de la misma duración (para comparar tendencias)."""
        fin = self.desde - timedelta(days=1)
        ini = fin - timedelta(days=self.dias - 1)
        return ini.isoformat(), fin.isoformat()


def num(n: Any, dec: int = 0) -> str:
    """Número con formato es-CO (miles con punto, decimales con coma)."""
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "—"
    txt = f"{v:,.{dec}f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def moneda(n: Any) -> str:
    try:
        return "$" + num(round(float(n)))
    except (TypeError, ValueError):
        return "—"


def variacion(actual: Any, anterior: Any) -> str:
    """Texto de variación porcentual contra el período anterior."""
    try:
        a, b = float(actual), float(anterior)
    except (TypeError, ValueError):
        return ""
    if b == 0:
        return ""
    pct = (a - b) / b * 100
    signo = "+" if pct >= 0 else ""
    return f"{signo}{num(pct, 1)}% vs período anterior"


def _estilo(nombre: str, **kw) -> ParagraphStyle:
    return ParagraphStyle(nombre, parent=estilo_normal(), **kw)


def _p(txt: Any, estilo: Optional[ParagraphStyle] = None) -> Paragraph:
    return Paragraph(str(txt if txt is not None else ""), estilo or estilo_normal())


def tabla(encabezados: Sequence[str], filas: Sequence[Sequence[Any]], anchos_mm: Sequence[float],
          alinear_derecha: Sequence[int] = ()) -> Table:
    """Tabla con el estilo moderno JA; celdas de texto largo como Paragraph."""
    datos = [list(encabezados)]
    for f in filas:
        datos.append([c if not isinstance(c, str) or len(c) < 38 else _p(c) for c in f])
    t = Table(datos, colWidths=[a * mm for a in anchos_mm], repeatRows=1)
    t.setStyle(tabla_style_moderna())
    if alinear_derecha:
        t.setStyle(TableStyle([("ALIGN", (c, 1), (c, -1), "RIGHT") for c in alinear_derecha]))
    return t


def subtitulo(txt: str) -> Paragraph:
    # keepWithNext: el subtítulo nunca queda solo al final de una página.
    return Paragraph(txt, ParagraphStyle("JA_SubKeep", parent=estilo_subseccion_grafico(), keepWithNext=1))


def nota(txt: str) -> Paragraph:
    return Paragraph(txt, _estilo("JA_Nota", fontSize=7, leading=9, textColor=colors.HexColor(COLOR_GRIS)))


_NIVELES = {
    "ok": (COLOR_VERDE_OK_BG, COLOR_VERDE_OK, "#065F46", "BIEN"),
    "atencion": (COLOR_AMBAR_BG, COLOR_AMBAR, COLOR_AMBAR_TXT, "ATENCIÓN"),
    "critico": (COLOR_ALERTA_BG, COLOR_ROJO_ALERTA, COLOR_ALERTA_TXT, "CRÍTICO"),
}


def hallazgos(items: Sequence[tuple[str, str]], ancho: float) -> list:
    """Caja de hallazgos y recomendaciones con semáforo por fila.

    ``items``: lista de (nivel, texto) con nivel 'ok' | 'atencion' | 'critico'.
    """
    if not items:
        return []
    filas, estilos = [], []
    for i, (nivel, texto) in enumerate(items):
        bg, barra, txt_col, etiqueta = _NIVELES.get(nivel, _NIVELES["atencion"])
        est = _estilo(f"JA_Hall_{i}", fontSize=8, leading=10.5, textColor=colors.HexColor(txt_col))
        filas.append([_p(f"<b>{etiqueta}</b>", est), _p(texto, est)])
        estilos += [
            ("BACKGROUND", (0, i), (-1, i), colors.HexColor(bg)),
            ("LINEBEFORE", (0, i), (0, i), 3.5, colors.HexColor(barra)),
        ]
    t = Table(filas, colWidths=[22 * mm, ancho - 22 * mm])
    t.setStyle(TableStyle(estilos + [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.6, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [subtitulo("Hallazgos y recomendaciones"), t, Spacer(1, 6)]


def _imagen(ruta: str, ancho_mm: float) -> Image:
    iw, ih = ImageReader(ruta).getSize()
    return Image(ruta, width=ancho_mm * mm, height=ancho_mm * (ih / iw) * mm)


def grafico(ctx: ContextoReporte, titulo: str, fn: Callable[..., Optional[str]], **kw) -> Optional[tuple[str, str]]:
    """Genera un gráfico de engine.charts en el directorio temporal del informe.
    Si falla o no hay datos, devuelve None y deja constancia en el log."""
    if not ctx.tmp_dir:
        return None
    try:
        ruta = fn(ctx.db, output_dir=ctx.tmp_dir, hoy=ctx.hoy, dpi=130, **kw)
    except Exception:
        logger.warning("Gráfico '%s' no se pudo generar para el PDF", titulo, exc_info=True)
        return None
    if ruta and os.path.exists(ruta):
        return titulo, ruta
    return None


def grilla_graficos(graficos: Sequence[Optional[tuple[str, str]]], ancho: float) -> list:
    """Gráficos en grilla de 2 columnas (o a ancho completo si es uno solo)."""
    g = [x for x in graficos if x]
    if not g:
        return []
    ancho_mm = ancho / mm
    if len(g) == 1:
        # Un gráfico "cuadrado" a todo el ancho ocupa media hoja: solo los
        # panorámicos (series de tiempo) van a ancho completo.
        iw, ih = ImageReader(g[0][1]).getSize()
        w = ancho_mm - 6 if iw / ih >= 1.8 else min(ancho_mm - 6, 110)
        img = _imagen(g[0][1], w)
        img.hAlign = "CENTER"
        return [subtitulo(g[0][0]), img, Spacer(1, 5)]
    col = (ancho_mm - 6) / 2
    filas = []
    for i in range(0, len(g), 2):
        par = g[i:i + 2]
        celdas = [[subtitulo(t), _imagen(r, col - 4)] for t, r in par]
        if len(celdas) == 1:
            celdas.append("")
        filas.append(celdas)
    t = Table(filas, colWidths=[col * mm, col * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(COLOR_BORDE_SUAVE)),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COLOR_BORDE_SUAVE)),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [t, Spacer(1, 6)]


def _encabezado(titulo: str, ancho: float) -> list:
    # Si quedan menos de 50 mm en la hoja, la sección arranca en la siguiente
    # (evita la banda de título sola al pie de página).
    return [CondPageBreak(50 * mm), SeccionFlowable(titulo, width=ancho), Spacer(1, 3)]


def _dos_columnas(izq: list, der: list, ancho: float) -> Table:
    """Dos bloques de flowables lado a lado (tablas pequeñas complementarias)."""
    t = Table([[izq, der]], colWidths=[ancho / 2, ancho / 2])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 4),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
    ]))
    return t


def _grafico_serie_diaria(ctx: ContextoReporte, serie: list[dict], titulo: str,
                          etiqueta_y: str = "Litros / día") -> Optional[tuple[str, str]]:
    """Serie diaria del período con media móvil de 7 días y línea de promedio."""
    if not ctx.tmp_dir or len(serie) < 2:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception:
        return None
    try:
        fechas = [date.fromisoformat(str(r["fecha"])[:10]) for r in serie]
        valores = [float(r["litros"]) for r in serie]
        prom = sum(valores) / len(valores)
        movil = []
        for i in range(len(valores)):
            ventana = valores[max(0, i - 6):i + 1]
            movil.append(sum(ventana) / len(ventana))
        fig, ax = plt.subplots(figsize=(8.6, 3.2), dpi=130)
        ax.bar(fechas, valores, color="#A3C9A8", width=0.8, label="Litros del día")
        ax.plot(fechas, movil, color=COLOR_MARCA, linewidth=2.2, label="Media móvil 7 días")
        ax.axhline(prom, color=COLOR_AMBAR, linestyle="--", linewidth=1.2, label=f"Promedio {num(prom, 0)} L")
        ax.set_ylabel(etiqueta_y, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(fontsize=7, loc="lower left", frameon=False, ncol=3)
        fig.tight_layout()
        ruta = os.path.join(ctx.tmp_dir, f"serie_diaria_{abs(hash(titulo))}.png")
        fig.savefig(ruta)
        plt.close(fig)
        return titulo, ruta
    except Exception:
        logger.warning("No se pudo dibujar la serie diaria '%s'", titulo, exc_info=True)
        return None


def _fecha_corta(iso: Any) -> str:
    s = str(iso or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[0:4]}" if len(s) == 10 else s


# --------------------------------------------------------------------------- #
# LECHE
# --------------------------------------------------------------------------- #
def _serie_leche(db, desde: str, hasta: str) -> list[dict]:
    """Litros por día del período. Si hay registros de tanque (sin animal)
    se usan solo esos para no sumar dos veces los controles individuales."""
    hay_tanque = db.query_one(
        "SELECT 1 FROM produccion_leche WHERE animal_id IS NULL AND fecha BETWEEN ? AND ? LIMIT 1",
        (desde, hasta),
    )
    filtro = "AND animal_id IS NULL" if hay_tanque else ""
    filas = db.query(
        f"SELECT fecha, SUM(litros) AS litros FROM produccion_leche "
        f"WHERE litros > 0 AND fecha BETWEEN ? AND ? {filtro} GROUP BY fecha ORDER BY fecha",
        (desde, hasta),
    )
    return [{"fecha": r["fecha"], "litros": round(float(r["litros"]), 1)} for r in filas]


def datos_leche_periodo(ctx: ContextoReporte) -> dict:
    db = ctx.db
    serie = _serie_leche(db, ctx.desde_iso, ctx.hasta_iso)
    serie_ant = _serie_leche(db, *ctx.anterior)
    total = sum(r["litros"] for r in serie)
    total_ant = sum(r["litros"] for r in serie_ant)
    prom = total / len(serie) if serie else 0.0
    prom_ant = total_ant / len(serie_ant) if serie_ant else 0.0
    try:
        ordeno = db.resumen_ordeno()
    except Exception:
        ordeno = {"en_ordeno": 0, "en_pausa": 0, "ordenandose": 0}
    ordenandose = ordeno.get("ordenandose") or 0
    # Precio promedio pagado por litro (ingresos por leche con litros del recibo)
    fila_precio = db.query_one(
        "SELECT SUM(monto) AS monto, SUM(litros) AS litros FROM finanzas "
        "WHERE UPPER(tipo) = 'INGRESO' AND UPPER(categoria) LIKE 'LECHE%' AND fecha BETWEEN ? AND ?",
        (ctx.desde_iso, ctx.hasta_iso),
    )
    precio = None
    if fila_precio and fila_precio["litros"]:
        precio = float(fila_precio["monto"] or 0) / float(fila_precio["litros"])
    try:
        kpis_fin = db.kpis_financieros(ctx.desde_iso, ctx.hasta_iso) or {}
    except Exception:
        kpis_fin = {}
    retiros = db.query(
        "SELECT a.tag, t.producto, t.fecha_fin_retiro_leche FROM tratamientos t "
        "JOIN animales a ON a.id_animal = t.animal_id "
        "WHERE a.estado = 'ACTIVO' AND t.fecha <= ? AND t.fecha_fin_retiro_leche >= ? "
        "ORDER BY t.fecha_fin_retiro_leche",
        (ctx.hasta_iso, ctx.hasta_iso),
    )
    pausas = db.query(
        "SELECT a.tag, p.fecha_inicio, p.motivo FROM pausas_ordeno p "
        "JOIN animales a ON a.id_animal = p.animal_id "
        "WHERE a.estado = 'ACTIVO' AND p.fecha_fin IS NULL ORDER BY p.fecha_inicio",
    )
    from ..engine.dashboard_data import datos_leche
    base = datos_leche(db)
    dias_periodo = ctx.dias
    return {
        "serie": serie, "total": total, "total_ant": total_ant, "promedio": prom, "promedio_ant": prom_ant,
        "pico": max(serie, key=lambda r: r["litros"]) if serie else None,
        "piso": min(serie, key=lambda r: r["litros"]) if serie else None,
        "dias_con_registro": len(serie), "dias_periodo": dias_periodo,
        "ordeno": ordeno,
        "litros_vaca_dia": (prom / ordenandose) if ordenandose else None,
        "precio_litro": precio, "costo_litro": kpis_fin.get("costo_por_litro_leche"),
        "retiros": [dict(r) for r in retiros], "pausas": [dict(r) for r in pausas],
        "ranking": base.get("ranking_vacas") or [], "del": base.get("analisis_del") or {},
    }


def seccion_leche(ctx: ContextoReporte, compacto: bool = False) -> list:
    d = datos_leche_periodo(ctx)
    if not d["serie"] and compacto:
        return []  # el informe general omite áreas sin datos
    out = _encabezado("PRODUCCIÓN LECHERA DEL PERÍODO", ctx.ancho)
    if not d["serie"]:
        out.append(nota("No hay registros de producción de leche en el período evaluado."))
        return out + [Spacer(1, 6)]
    o = d["ordeno"]
    out.append(crear_bloque_kpis([
        (f"{num(d['total'])} L", "Total del período", variacion(d["total"], d["total_ant"]) or f"{d['dias_con_registro']} días con registro", COLOR_MARCA),
        (f"{num(d['promedio'], 1)} L", "Promedio diario", variacion(d["promedio"], d["promedio_ant"]), "#047857"),
        (f"{num(d['litros_vaca_dia'], 1)} L" if d["litros_vaca_dia"] else "—", "Litros / vaca / día", f"{o.get('ordenandose', 0)} vacas ordeñándose", "#1D4ED8"),
        (str(o.get("en_ordeno", 0)), "Vacas en ordeño", f"{o.get('en_pausa', 0)} en pausa temporal", COLOR_GRIS),
    ], ancho_total=ctx.ancho))
    if not compacto:
        margen = None
        if d["precio_litro"] and d["costo_litro"] is not None:
            margen = d["precio_litro"] - float(d["costo_litro"])
        out += [Spacer(1, 3), crear_bloque_kpis([
            (f"{num(d['pico']['litros'])} L", "Pico del período", _fecha_corta(d["pico"]["fecha"]), COLOR_VERDE_OK),
            (f"{num(d['piso']['litros'])} L", "Día más bajo", _fecha_corta(d["piso"]["fecha"]), COLOR_AMBAR),
            (moneda(d["precio_litro"]) if d["precio_litro"] else "—", "Precio por litro", "Según recibos del período", COLOR_MARCA),
            (moneda(margen) if margen is not None else "—", "Margen por litro",
             f"Costo {moneda(d['costo_litro'])}/L" if d["costo_litro"] is not None else "Sin costo registrado",
             COLOR_VERDE_OK if (margen or 0) >= 0 else COLOR_ROJO_ALERTA),
        ], ancho_total=ctx.ancho)]
    out.append(Spacer(1, 5))

    from ..engine import charts
    if not compacto:
        out += grilla_graficos([_grafico_serie_diaria(ctx, d["serie"], "Producción diaria del período")], ctx.ancho)
        out += grilla_graficos([
            grafico(ctx, "Tendencia semanal (12 semanas)", charts.generar_grafico_leche_total_hato),
            grafico(ctx, "Eficiencia: litros por vaca en ordeño", charts.generar_grafico_eficiencia_lechera),
            grafico(ctx, "Ranking de vacas por producción", charts.generar_grafico_ranking_vacas_leche),
        ], ctx.ancho)

    # Hallazgos
    items: list[tuple[str, str]] = []
    if d["total_ant"]:
        pct = (d["total"] - d["total_ant"]) / d["total_ant"] * 100
        if pct <= -5:
            items.append(("critico" if pct <= -10 else "atencion",
                          f"La producción bajó {num(abs(pct), 1)}% frente al período anterior. Revise alimentación, sanidad de ubre y vacas que pasaron a secado."))
        elif pct >= 5:
            items.append(("ok", f"La producción subió {num(pct, 1)}% frente al período anterior."))
        else:
            items.append(("ok", f"Producción estable frente al período anterior ({variacion(d['total'], d['total_ant'])})."))
    faltan = d["dias_periodo"] - d["dias_con_registro"]
    if faltan > 0:
        items.append(("atencion", f"Hay {faltan} día(s) del período sin registro de leche: complete los recibos para que los promedios sean reales."))
    lvd = d["litros_vaca_dia"]
    if lvd is not None:
        if lvd < 6:
            items.append(("critico", f"Promedio de {num(lvd, 1)} L/vaca/día: muy bajo para el hato en ordeño."))
        elif lvd < 9:
            items.append(("atencion", f"Promedio de {num(lvd, 1)} L/vaca/día: hay margen de mejora (suplementación, confort, descarte de vacas de baja producción)."))
    etapas = {e["etapa"]: e["cantidad"] for e in (d["del"].get("etapas") or [])}
    prolong = etapas.get(">340 (Prolongada)", 0)
    if prolong:
        items.append(("atencion", f"{prolong} vaca(s) con más de 340 días en leche: evalúe secarlas y revisar su estado reproductivo."))
    if d["retiros"]:
        items.append(("critico", f"{len(d['retiros'])} vaca(s) con leche bloqueada por retiro sanitario: su leche NO debe ir al tanque (ver tabla)."))
    out += hallazgos(items, ctx.ancho)
    if compacto:
        return out

    # Tablas de detalle
    del_d = d["del"]
    if del_d.get("etapas"):
        izq = [subtitulo(f"Etapas de lactancia (DEL promedio: {num(del_d.get('promedio_del'), 0)} días)"),
               tabla(["Etapa", "Vacas", "%"], [[e["etapa"], e["cantidad"], f"{num(e['pct'], 1)}%"] for e in del_d["etapas"]],
                     [40, 20, 22], alinear_derecha=(1, 2))]
    else:
        izq = [nota("Sin datos de días en leche.")]
    if d["ranking"]:
        der = [subtitulo("Mejores vacas (controles individuales)"),
               tabla(["Vaca", "Controles", "Litros"], [[r["tag"], r["controles"], num(r["total_litros"], 1)] for r in d["ranking"]],
                     [26, 26, 30], alinear_derecha=(1, 2))]
    else:
        der = [nota("Sin controles individuales de leche.")]
    out += [_dos_columnas(izq, der, ctx.ancho), Spacer(1, 5)]

    if d["retiros"] or d["pausas"]:
        izq = [subtitulo("Leche bloqueada por retiro sanitario"),
               tabla(["Vaca", "Producto", "Hasta"], [[r["tag"], r["producto"] or "—", _fecha_corta(r["fecha_fin_retiro_leche"])] for r in d["retiros"]],
                     [20, 38, 24])] if d["retiros"] else [nota("Ninguna vaca con retiro de leche vigente.")]
        der = [subtitulo("Pausas temporales de ordeño"),
               tabla(["Vaca", "Desde", "Motivo"], [[r["tag"], _fecha_corta(r["fecha_inicio"]), r["motivo"] or "—"] for r in d["pausas"]],
                     [20, 24, 38])] if d["pausas"] else [nota("Sin pausas de ordeño abiertas.")]
        out += [_dos_columnas(izq, der, ctx.ancho), Spacer(1, 5)]

    prom = d["promedio"]
    filas = []
    for r in d["serie"][-31:]:
        dif = r["litros"] - prom
        filas.append([_fecha_corta(r["fecha"]), num(r["litros"], 1), ("+" if dif >= 0 else "") + num(dif, 1),
                      ("+" if dif >= 0 else "") + num(dif / prom * 100 if prom else 0, 1) + "%"])
    out += [subtitulo("Detalle diario del tanque"),
            tabla(["Fecha", "Litros", "Dif. vs promedio", "%"], filas, [40, 40, 46, 40], alinear_derecha=(1, 2, 3)),
            Spacer(1, 6)]
    return out


# --------------------------------------------------------------------------- #
# REPRODUCCIÓN
# --------------------------------------------------------------------------- #
# Metas zootécnicas de referencia para trópico (doble propósito / lechería).
META_IEP = 400
META_DIAS_ABIERTOS = 120
META_SERV_CONCEPCION = 2.0
META_TASA_CONCEPCION = 50.0
META_EDAD_1P_MESES = 30.0


def _semaforo_menor(valor, meta, tolerancia) -> str:
    if valor is None:
        return COLOR_GRIS
    return COLOR_VERDE_OK if valor <= meta else (COLOR_AMBAR if valor <= meta + tolerancia else COLOR_ROJO_ALERTA)


def datos_reproduccion_periodo(ctx: ContextoReporte) -> dict:
    from ..engine.dashboard_data import datos_reproduccion
    db = ctx.db
    base = datos_reproduccion(db)
    rng = (ctx.desde_iso, ctx.hasta_iso)

    def _cnt(sql: str) -> int:
        r = db.query_one(sql, rng)
        return int(r["n"]) if r else 0

    partos = db.query(
        "SELECT COALESCE(p.tipo_evento, 'PARTO') AS tipo, COUNT(*) AS n FROM partos p "
        "JOIN animales a ON a.id_animal = p.vaca_id WHERE p.fecha BETWEEN ? AND ? GROUP BY 1", rng)
    diags = db.query(
        "SELECT d.fecha, a.tag, d.resultado, d.dias_gestacion FROM diagnosticos_gestacion d "
        "JOIN animales a ON a.id_animal = d.vaca_id WHERE a.estado = 'ACTIVO' AND d.fecha BETWEEN ? AND ? "
        "ORDER BY d.fecha", rng)
    celos = db.query(
        "SELECT c.fecha, a.tag, c.am_pm FROM celos c JOIN animales a ON a.id_animal = c.vaca_id "
        "WHERE a.estado = 'ACTIVO' AND c.fecha BETWEEN ? AND ? ORDER BY c.fecha", rng)
    toros = db.query(
        "SELECT UPPER(TRIM(s.toro_pajilla)) AS toro, COUNT(*) AS servicios, "
        "SUM(CASE WHEN UPPER(COALESCE(s.estado,'')) = 'CONFIRMADA' THEN 1 ELSE 0 END) AS confirmados, "
        "SUM(CASE WHEN UPPER(COALESCE(s.estado,'')) = 'FALLIDO' THEN 1 ELSE 0 END) AS fallidos "
        "FROM servicios s JOIN animales a ON a.id_animal = s.vaca_id "
        "WHERE s.toro_pajilla IS NOT NULL AND TRIM(s.toro_pajilla) != '' AND s.fecha >= ? "
        "GROUP BY 1 HAVING COUNT(*) >= 2 ORDER BY servicios DESC LIMIT 8",
        ((ctx.hoy - timedelta(days=730)).isoformat(),))
    from ..engine.query_engine import QueryEngine
    qe = QueryEngine(db, hoy=ctx.hoy)
    try:
        proximos = qe._ultimos_servicios_activos()
        limite = (ctx.hoy + timedelta(days=45)).isoformat()
        proximos = [s for s in proximos if ctx.hoy.isoformat() <= s["fep_calculada"] <= limite and qe._servicio_vigente(s)]
        proximos.sort(key=lambda s: s["fep_calculada"])
    except Exception:
        logger.warning("No se pudieron calcular los partos próximos para el PDF", exc_info=True)
        proximos = []
    return {
        "kpis": base.get("kpis") or {},
        "indice_fertilidad": base.get("indice_fertilidad") or {},
        "dist_da": base.get("distribucion_dias_abiertos") or [],
        "dist_iep": base.get("distribucion_iep") or [],
        "perdidas": base.get("perdidas") or {},
        "pajuelas": base.get("pajuelas") or [],
        "termo": base.get("termo"),
        "partos": {r["tipo"]: int(r["n"]) for r in partos},
        "servicios_periodo": _cnt("SELECT COUNT(*) AS n FROM servicios s JOIN animales a ON a.id_animal = s.vaca_id "
                                  "WHERE s.fecha BETWEEN ? AND ?"),
        "diagnosticos": [dict(r) for r in diags],
        "celos": [dict(r) for r in celos],
        "toros": [dict(r) for r in toros],
        "proximos_partos": [dict(s) for s in proximos],
        "palpaciones": qe._palpaciones_pendientes_lista(),
    }


def seccion_reproduccion(ctx: ContextoReporte, compacto: bool = False) -> list:
    from ..engine.reproductive_engine import programar_inseminacion
    d = datos_reproduccion_periodo(ctx)
    k = d["kpis"]
    if compacto and not any(v for v in k.values()) and not d["diagnosticos"] and not d["partos"]:
        return []
    out = _encabezado("INDICADORES REPRODUCTIVOS DEL HATO", ctx.ancho)
    iep, da = k.get("iep_promedio_dias"), k.get("dias_abiertos_promedio")
    spc, tc = k.get("servicios_por_concepcion"), k.get("tasa_concepcion")
    e1p, ifert = k.get("edad_primer_parto_meses"), k.get("indice_fertilidad_pct")
    out.append(crear_bloque_kpis([
        (f"{num(iep)} d" if iep else "—", "Intervalo entre partos", f"Meta: máx. {META_IEP} días", _semaforo_menor(iep, META_IEP, 50)),
        (f"{num(da)} d" if da else "—", "Días abiertos", f"Meta: máx. {META_DIAS_ABIERTOS} días", _semaforo_menor(da, META_DIAS_ABIERTOS, 40)),
        (num(spc, 2) if spc else "—", "Servicios por concepción", f"Meta: máx. {num(META_SERV_CONCEPCION, 1)}", _semaforo_menor(spc, META_SERV_CONCEPCION, 0.5)),
        (f"{num(tc, 1)}%" if tc is not None else "—", "Tasa de concepción", f"Meta: mín. {num(META_TASA_CONCEPCION)}%",
         COLOR_GRIS if tc is None else (COLOR_VERDE_OK if tc >= META_TASA_CONCEPCION else COLOR_AMBAR)),
    ], ancho_total=ctx.ancho))
    partos_total = sum(d["partos"].values())
    perdidas_periodo = sum(v for t, v in d["partos"].items() if t not in ("PARTO", "GEMELAR"))
    diags = d["diagnosticos"]
    pren = sum(1 for x in diags if str(x["resultado"]).upper().startswith("PRE"))
    out += [Spacer(1, 3), crear_bloque_kpis([
        (f"{num(e1p, 1)} m" if e1p else "—", "Edad al primer parto", f"Meta: máx. {num(META_EDAD_1P_MESES)} meses", _semaforo_menor(e1p, META_EDAD_1P_MESES, 4)),
        (f"{num(ifert, 1)}%" if ifert is not None else "—", "Índice de fertilidad", "Vientres preñados o en descanso", COLOR_MARCA),
        (str(partos_total), "Partos del período", f"{perdidas_periodo} pérdida(s)" if perdidas_periodo else "Sin pérdidas", COLOR_MARCA),
        (f"{pren}/{len(diags)}", "Diagnósticos preñados", f"{d['servicios_periodo']} servicios en el período", "#1D4ED8"),
    ], ancho_total=ctx.ancho), Spacer(1, 5)]

    from ..engine import charts
    if not compacto:
        out += grilla_graficos([
            grafico(ctx, "Estado reproductivo del hato", charts.generar_grafico_estado_reproductivo_hato),
            grafico(ctx, "Intervalo entre partos (IEP)", charts.generar_grafico_iep_boxplot),
            grafico(ctx, "Días abiertos (curva de preñez)", charts.generar_grafico_dias_abiertos_km),
            grafico(ctx, "Preñadas vs vacías por potrero", charts.generar_grafico_prenadas_vacias_potrero),
        ], ctx.ancho)

    items: list[tuple[str, str]] = []
    if iep:
        items.append(("ok", f"IEP de {num(iep)} días dentro de la meta.") if iep <= META_IEP else
                     (("atencion" if iep <= META_IEP + 50 else "critico"),
                      f"IEP de {num(iep)} días ({num(iep - META_IEP)} sobre la meta): cada mes extra entre partos es leche y un ternero menos al año."))
    if da and da > META_DIAS_ABIERTOS:
        items.append(("critico" if da > META_DIAS_ABIERTOS + 60 else "atencion",
                      f"{num(da)} días abiertos promedio: refuerce detección de celos (regla AM-PM) y revise vacas vacías con más de 120 días posparto."))
    if spc and spc > META_SERV_CONCEPCION:
        items.append(("atencion", f"{num(spc, 2)} servicios por concepción: revise técnica de inseminación, manejo del termo y calidad de pajuelas."))
    fert = d["indice_fertilidad"]
    if fert.get("diagnostico"):
        nivel = "critico" if "Alerta" in fert["diagnostico"] else "ok"
        items.append((nivel, f"Índice de fertilidad {num(fert.get('indice_pct'), 1)}%: {fert['diagnostico']} ({fert.get('prenadas', 0)} preñadas de {fert.get('total_vientres', 0)} vientres)."))
    atrasadas = [p for p in d["palpaciones"] if p["atraso"] > 0]
    if atrasadas:
        items.append(("atencion", f"{len(atrasadas)} palpación(es) de confirmación (día 60) atrasada(s): prográmelas esta semana."))
    if perdidas_periodo:
        items.append(("critico", f"{perdidas_periodo} pérdida(s) reproductiva(s) en el período (abortos o similares): revise sanidad (brucelosis, leptospira, IBR/DVB)."))
    out += hallazgos(items, ctx.ancho)
    if compacto:
        return out

    izq = [subtitulo("Distribución de días abiertos"),
           tabla(["Tramo (días)", "Vacas", "%"], [[x["tramo"], x["cantidad"], f"{num(x['pct'], 1)}%"] for x in d["dist_da"]],
                 [34, 22, 24], alinear_derecha=(1, 2))] if d["dist_da"] else [nota("Sin datos de días abiertos.")]
    der = [subtitulo("Distribución del intervalo entre partos"),
           tabla(["Tramo (días)", "Vacas", "%"], [[x["tramo"], x["cantidad"], f"{num(x['pct'], 1)}%"] for x in d["dist_iep"]],
                 [34, 22, 24], alinear_derecha=(1, 2))] if d["dist_iep"] else [nota("Sin datos de IEP.")]
    out += [_dos_columnas(izq, der, ctx.ancho), Spacer(1, 5)]

    if d["palpaciones"]:
        out += [subtitulo("Palpaciones pendientes (confirmación del día 60)"),
                tabla(["Vaca", "Servicio", "Palpar el", "Estado"],
                      [[p["tag"], _fecha_corta(p["servicio"]), _fecha_corta(p["fecha"]),
                        f"Atrasada {p['atraso']} d" if p["atraso"] > 0 else f"En {-p['atraso']} d"]
                       for p in d["palpaciones"][:30]], [30, 40, 40, 50]), Spacer(1, 5)]

    if d["proximos_partos"]:
        filas = []
        for s in d["proximos_partos"][:25]:
            faltan = (date.fromisoformat(s["fep_calculada"][:10]) - ctx.hoy).days
            filas.append([s["tag"], _fecha_corta(s["fecha"]), s.get("toro_pajilla") or "—", _fecha_corta(s["fep_calculada"]), f"{faltan} d"])
        out += [subtitulo("Partos esperados en los próximos 45 días (preparar maternidad)"),
                tabla(["Vaca", "Servicio", "Toro / pajuela", "Fecha probable", "Faltan"], filas, [26, 30, 46, 34, 24], alinear_derecha=(4,)),
                Spacer(1, 5)]

    if d["celos"]:
        filas = []
        for c in d["celos"][-25:]:
            prog = programar_inseminacion(c["fecha"], c["am_pm"])
            filas.append([_fecha_corta(c["fecha"]), c["tag"], c["am_pm"] or "—",
                          f"{_fecha_corta(prog['fecha'])} ({prog['franja']})" if prog.get("fecha") else "—"])
        out += [subtitulo("Celos del período y momento de inseminación (regla AM-PM)"),
                tabla(["Fecha celo", "Vaca", "Franja", "Inseminar"], filas, [34, 30, 24, 72]), Spacer(1, 5)]

    if diags:
        out += [subtitulo("Diagnósticos de gestación del período"),
                tabla(["Fecha", "Vaca", "Resultado", "Días gestación"],
                      [[_fecha_corta(x["fecha"]), x["tag"], x["resultado"], x["dias_gestacion"] or "—"] for x in diags[-30:]],
                      [34, 30, 50, 46], alinear_derecha=(3,)), Spacer(1, 5)]

    if d["toros"]:
        filas = []
        for t in d["toros"]:
            cerrados = (t["confirmados"] or 0) + (t["fallidos"] or 0)
            pct = f"{num((t['confirmados'] or 0) / cerrados * 100, 1)}%" if cerrados else "—"
            filas.append([t["toro"], t["servicios"], t["confirmados"] or 0, t["fallidos"] or 0, pct])
        out += [subtitulo("Desempeño por toro / pajuela (últimos 24 meses)"),
                tabla(["Toro / pajuela", "Servicios", "Preñeces", "Fallidos", "Concepción"], filas, [46, 28, 28, 28, 30],
                      alinear_derecha=(1, 2, 3, 4)),
                nota("Concepción = preñeces / (preñeces + fallidos), solo servicios ya diagnosticados."), Spacer(1, 5)]

    if d["pajuelas"]:
        out += [subtitulo("Inventario de pajuelas en termo"),
                tabla(["Toro", "Raza", "Canastilla", "Disponibles"],
                      [[p.get("codigo_toro"), p.get("raza") or "—", p.get("canastilla") or "—", p.get("cantidad", 0)] for p in d["pajuelas"][:20]],
                      [40, 50, 34, 36], alinear_derecha=(3,)), Spacer(1, 5)]
    return out


# --------------------------------------------------------------------------- #
# SANIDAD
# --------------------------------------------------------------------------- #
def seccion_sanidad(ctx: ContextoReporte, compacto: bool = False) -> list:
    db = ctx.db
    rng = (ctx.desde_iso, ctx.hasta_iso)
    hoy_iso = ctx.hasta_iso
    trat = db.query(
        "SELECT t.fecha, a.tag, t.producto, t.principio_activo, t.dosis, t.via, t.diagnostico, "
        "t.fecha_fin_retiro_leche, t.fecha_fin_retiro_carne FROM tratamientos t "
        "JOIN animales a ON a.id_animal = t.animal_id WHERE t.fecha BETWEEN ? AND ? ORDER BY t.fecha", rng)
    retiros = db.query(
        "SELECT a.tag, t.producto, t.fecha, t.fecha_fin_retiro_leche, t.fecha_fin_retiro_carne FROM tratamientos t "
        "JOIN animales a ON a.id_animal = t.animal_id WHERE a.estado = 'ACTIVO' AND t.fecha <= ? "
        "AND (t.fecha_fin_retiro_leche >= ? OR t.fecha_fin_retiro_carne >= ?) ORDER BY a.tag",
        (hoy_iso, hoy_iso, hoy_iso))
    en_leche = {r["tag"] for r in retiros if (r["fecha_fin_retiro_leche"] or "") >= hoy_iso}
    en_carne = {r["tag"] for r in retiros if (r["fecha_fin_retiro_carne"] or "") >= hoy_iso}
    productos: dict[str, int] = {}
    for t in trat:
        clave = (t["producto"] or "Sin nombre").strip().title()
        productos[clave] = productos.get(clave, 0) + 1
    muertes = db.query(
        "SELECT m.fecha, a.tag, m.causa_presunta FROM muertes m LEFT JOIN animales a ON a.id_animal = m.animal_id "
        "WHERE m.fecha BETWEEN ? AND ? ORDER BY m.fecha", rng)
    activos = db.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO'")
    n_act = int(activos["n"]) if activos else 0
    cc_baja = db.query(
        "SELECT a.tag, c.valor, c.fecha FROM condicion_corporal c JOIN animales a ON a.id_animal = c.animal_id "
        "WHERE a.estado = 'ACTIVO' AND c.valor < 2.5 AND c.fecha = (SELECT MAX(c2.fecha) FROM condicion_corporal c2 "
        "WHERE c2.animal_id = c.animal_id) ORDER BY c.valor LIMIT 20")

    if compacto and not (trat or retiros or muertes):
        return []
    out = _encabezado("SANIDAD ANIMAL Y CONTROL VETERINARIO", ctx.ancho)
    mort = (len(muertes) / n_act * 100) if n_act else 0
    out.append(crear_bloque_kpis([
        (str(len(trat)), "Tratamientos del período", f"{len({t['tag'] for t in trat})} animales tratados", COLOR_MARCA),
        (str(len(en_leche)), "Leche bloqueada", "Animales en retiro de leche", COLOR_ROJO_ALERTA if en_leche else COLOR_VERDE_OK),
        (str(len(en_carne)), "Carne bloqueada", "No enviar a sacrificio", COLOR_ROJO_ALERTA if en_carne else COLOR_VERDE_OK),
        (str(len(muertes)), "Muertes del período", f"Mortalidad {num(mort, 2)}% del hato", COLOR_ROJO_ALERTA if muertes else COLOR_VERDE_OK),
    ], ancho_total=ctx.ancho))
    out.append(Spacer(1, 5))

    items: list[tuple[str, str]] = []
    if en_leche or en_carne:
        items.append(("critico", f"{len(en_leche | en_carne)} animal(es) en periodo de retiro: separe su leche y no los venda para carne hasta la fecha indicada."))
    else:
        items.append(("ok", "Ningún animal activo en periodo de retiro."))
    if muertes:
        causas: dict[str, int] = {}
        for m in muertes:
            c = (m["causa_presunta"] or "Sin causa").strip().capitalize()
            causas[c] = causas.get(c, 0) + 1
        principal = max(causas.items(), key=lambda x: x[1])
        items.append(("atencion" if mort < 1 else "critico",
                      f"{len(muertes)} muerte(s); causa más frecuente: {principal[0]} ({principal[1]}). Registre necropsia cuando sea posible."))
    if cc_baja:
        items.append(("atencion", f"{len(cc_baja)} animal(es) con condición corporal menor a 2,5: revise nutrición y parásitos."))
    out += hallazgos(items, ctx.ancho)
    if compacto:
        return out

    if retiros:
        out += [subtitulo("Animales en periodo de retiro (vigentes hoy)"),
                tabla(["Animal", "Producto", "Aplicado", "Leche hasta", "Carne hasta"],
                      [[r["tag"], r["producto"] or "—", _fecha_corta(r["fecha"]),
                        _fecha_corta(r["fecha_fin_retiro_leche"]) if (r["fecha_fin_retiro_leche"] or "") >= hoy_iso else "Libre",
                        _fecha_corta(r["fecha_fin_retiro_carne"]) if (r["fecha_fin_retiro_carne"] or "") >= hoy_iso else "Libre"]
                       for r in retiros], [24, 52, 28, 28, 28]), Spacer(1, 5)]
    if productos:
        izq = [subtitulo("Productos más usados"),
               tabla(["Producto", "Aplicaciones"], sorted(([k, v] for k, v in productos.items()), key=lambda x: -x[1])[:10],
                     [52, 28], alinear_derecha=(1,))]
    else:
        izq = [nota("Sin tratamientos en el período.")]
    der = [subtitulo("Condición corporal crítica (< 2,5)"),
           tabla(["Animal", "CC", "Fecha"], [[r["tag"], num(r["valor"], 1), _fecha_corta(r["fecha"])] for r in cc_baja],
                 [26, 20, 34], alinear_derecha=(1,))] if cc_baja else [nota("Sin animales con condición corporal crítica.")]
    out += [_dos_columnas(izq, der, ctx.ancho), Spacer(1, 5)]
    if trat:
        out += [subtitulo("Tratamientos aplicados en el período"),
                tabla(["Fecha", "Animal", "Producto", "Dosis / vía", "Diagnóstico"],
                      [[_fecha_corta(t["fecha"]), t["tag"], t["producto"] or "—",
                        " ".join(x for x in (t["dosis"], t["via"]) if x) or "—", t["diagnostico"] or "—"] for t in trat[-40:]],
                      [24, 22, 40, 34, 40]), Spacer(1, 5)]
    if muertes:
        out += [subtitulo("Muertes del período"),
                tabla(["Fecha", "Animal", "Causa presunta"],
                      [[_fecha_corta(m["fecha"]), m["tag"] or "—", m["causa_presunta"] or "—"] for m in muertes],
                      [30, 30, 100]), Spacer(1, 5)]
    return out


# --------------------------------------------------------------------------- #
# PASTURAS
# --------------------------------------------------------------------------- #
def seccion_pasturas(ctx: ContextoReporte, compacto: bool = False) -> list:
    from ..engine import charts
    from ..engine.dashboard_data import datos_pasturas
    base = datos_pasturas(ctx.db)
    pots = base.get("potreros") or []
    if not pots and compacto:
        return []
    out = _encabezado("POTREROS, PASTURAS Y ROTACIÓN (VOISIN)", ctx.ancho)
    if not pots:
        return out + [nota("No hay potreros registrados."), Spacer(1, 6)]
    ocupados = [p for p in pots if (p.get("total_animales") or 0) > 0]
    area = sum(float(p.get("area_has") or 0) for p in pots)
    animales = sum(int(p.get("total_animales") or 0) for p in pots)
    sobre = [p for p in ocupados if (p.get("dias_ocupacion") or 0) > 3]
    listos = [p for p in pots if not (p.get("total_animales") or 0) and (p.get("dias_reposo") or 0) >= 30]
    out.append(crear_bloque_kpis([
        (str(len(pots)), "Potreros", f"{num(area, 1)} ha en total", COLOR_MARCA),
        (f"{len(ocupados)}", "Ocupados hoy", f"{animales} animales en pastoreo", "#1D4ED8"),
        (num(animales / area, 2) if area else "—", "Animales por hectárea", "Carga instantánea global", COLOR_GRIS),
        (str(len(sobre)), "Sobreocupados", "Más de 3 días (ley de ocupación)", COLOR_ROJO_ALERTA if sobre else COLOR_VERDE_OK),
    ], ancho_total=ctx.ancho))
    out.append(Spacer(1, 5))
    if not compacto:
        out += grilla_graficos([
            grafico(ctx, "Ocupación y reposo por potrero", charts.generar_grafico_ocupacion_potreros),
            grafico(ctx, "Aforo (oferta de forraje)", charts.generar_grafico_aforo_potreros),
            grafico(ctx, "Carga animal por potrero", charts.generar_grafico_carga_animal_potrero),
        ], ctx.ancho)

    items: list[tuple[str, str]] = []
    for p in sobre:
        items.append(("critico" if (p.get("dias_ocupacion") or 0) > 6 else "atencion",
                      f"{p.get('nombre') or p.get('codigo')}: {p.get('dias_ocupacion')} días ocupado con {p.get('total_animales')} animales. Rote el lote."))
    if listos:
        items.append(("ok", "Listos para entrar (reposo de 30 días o más): " + ", ".join(str(p.get("nombre") or p.get("codigo")) for p in listos[:8]) + "."))
    spi = base.get("spi_sequia") or []
    secos = [s for s in spi if (s.get("spi_valor") or 0) <= -1]
    if secos:
        items.append(("critico", "Alerta de sequía (SPI de -1 o menos): planifique suplementación y reserva de forraje."))
    out += hallazgos(items, ctx.ancho)
    if compacto:
        return out
    filas = []
    for p in sorted(pots, key=lambda x: str(x.get("nombre") or x.get("codigo") or "")):
        estado = str(p.get("estado_rotacion") or "—")
        filas.append([p.get("nombre") or p.get("codigo") or "—", num(p.get("area_has"), 1),
                      p.get("total_animales") or 0,
                      p.get("dias_ocupacion") if p.get("dias_ocupacion") is not None else "—",
                      p.get("dias_reposo") if p.get("dias_reposo") is not None else "—",
                      num(p.get("aforo_kg_m2"), 2) if p.get("aforo_kg_m2") is not None else "—", estado])
    out += [subtitulo("Estado de cada potrero"),
            tabla(["Potrero", "Ha", "Animales", "Días ocup.", "Días reposo", "Aforo kg/m²", "Estado"], filas,
                  [34, 14, 20, 20, 22, 22, 42], alinear_derecha=(1, 2, 3, 4, 5)),
            nota("Voisin: ocupación máxima 1-3 días y reposo suficiente (30+ días en lluvias, más en época seca)."),
            Spacer(1, 5)]
    return out


# --------------------------------------------------------------------------- #
# FINANZAS
# --------------------------------------------------------------------------- #
def seccion_finanzas(ctx: ContextoReporte, compacto: bool = False) -> list:
    from ..engine import charts
    db = ctx.db
    try:
        res = db.resumen_finanzas(ctx.desde_iso, ctx.hasta_iso) or {}
        res_ant = db.resumen_finanzas(*ctx.anterior) or {}
        kpis = db.kpis_financieros(ctx.desde_iso, ctx.hasta_iso) or {}
    except Exception:
        logger.warning("No se pudieron calcular las finanzas del PDF", exc_info=True)
        res, res_ant, kpis = {}, {}, {}
    if not (res.get("total_ingresos") or res.get("total_egresos")) and compacto:
        return []
    out = _encabezado("FINANZAS: INGRESOS, EGRESOS Y RENTABILIDAD", ctx.ancho)
    if not (res.get("total_ingresos") or res.get("total_egresos")):
        return out + [nota("No hay movimientos financieros registrados en el período."), Spacer(1, 6)]
    util = res.get("utilidad", 0) or 0
    out.append(crear_bloque_kpis([
        (moneda(res.get("total_ingresos")), "Ingresos", variacion(res.get("total_ingresos"), res_ant.get("total_ingresos")), COLOR_MARCA),
        (moneda(res.get("total_egresos")), "Egresos", variacion(res.get("total_egresos"), res_ant.get("total_egresos")), "#B45309"),
        (moneda(util), "Utilidad", f"Margen {num(kpis.get('margen_utilidad_pct'), 1)}%" if kpis.get("margen_utilidad_pct") is not None else "",
         COLOR_VERDE_OK if util >= 0 else COLOR_ROJO_ALERTA),
        (moneda(kpis.get("costo_por_litro_leche")) if kpis.get("costo_por_litro_leche") is not None else "—",
         "Costo por litro", "Egresos / litros producidos", COLOR_GRIS),
    ], ancho_total=ctx.ancho))
    out.append(Spacer(1, 5))
    if not compacto:
        out += grilla_graficos([grafico(ctx, "Flujo de caja", charts.generar_grafico_flujo_caja,
                                        desde=ctx.desde_iso, hasta=ctx.hasta_iso)], ctx.ancho)
    items: list[tuple[str, str]] = []
    items.append(("ok" if util >= 0 else "critico",
                  f"El período cerró con {'utilidad' if util >= 0 else 'pérdida'} de {moneda(abs(util))}."))
    cats = [c for c in (res.get("categorias") or []) if str(c.get("tipo")).upper() == "EGRESO"]
    if cats and res.get("total_egresos"):
        mayor = max(cats, key=lambda c: c.get("total") or 0)
        pct = (mayor.get("total") or 0) / res["total_egresos"] * 100
        items.append(("atencion" if pct >= 40 else "ok",
                      f"Mayor gasto: {str(mayor.get('categoria')).title()} ({num(pct, 1)}% de los egresos)."))
    out += hallazgos(items, ctx.ancho)
    if compacto:
        return out
    categorias = res.get("categorias") or []
    if categorias:
        filas = [[str(c.get("tipo")).title(), str(c.get("categoria")).replace("_", " ").title(), c.get("n", 0), moneda(c.get("total"))]
                 for c in sorted(categorias, key=lambda c: (str(c.get("tipo")), -(c.get("total") or 0)))]
        out += [subtitulo("Movimientos por categoría"),
                tabla(["Tipo", "Categoría", "Registros", "Total"], filas, [30, 60, 26, 44], alinear_derecha=(2, 3)),
                Spacer(1, 5)]
    return out


# --------------------------------------------------------------------------- #
# INVENTARIO
# --------------------------------------------------------------------------- #
def seccion_inventario(ctx: ContextoReporte, compacto: bool = False) -> list:
    from ..engine import charts
    db = ctx.db
    rng = (ctx.desde_iso, ctx.hasta_iso)

    def _n(sql: str, params: tuple = ()) -> int:
        r = db.query_one(sql, params)
        return int(r["n"]) if r else 0

    nacimientos = _n("SELECT COUNT(*) AS n FROM partos WHERE id_cria IS NOT NULL AND fecha BETWEEN ? AND ?", rng)
    muertes = _n("SELECT COUNT(*) AS n FROM muertes WHERE fecha BETWEEN ? AND ?", rng)
    mov = db.query("SELECT UPPER(COALESCE(tipo_movimiento, '')) AS t, COUNT(*) AS n FROM movimientos "
                   "WHERE fecha BETWEEN ? AND ? GROUP BY 1", rng)
    movs = {r["t"]: int(r["n"]) for r in mov}
    entradas = sum(v for t, v in movs.items() if "COMPRA" in t or "ENTRADA" in t or "INGRESO" in t)
    salidas = sum(v for t, v in movs.items() if "VENTA" in t or "SALIDA" in t or "DESCARTE" in t)
    out = _encabezado("INVENTARIO Y DINÁMICA DEL HATO", ctx.ancho)
    out.append(crear_bloque_kpis([
        (str(nacimientos), "Nacimientos", "Crías registradas en el período", COLOR_VERDE_OK),
        (str(entradas), "Entradas", "Compras / ingresos", "#1D4ED8"),
        (str(salidas), "Salidas", "Ventas / descartes", COLOR_AMBAR),
        (str(muertes), "Muertes", "Bajas por muerte", COLOR_ROJO_ALERTA if muertes else COLOR_VERDE_OK),
    ], ancho_total=ctx.ancho))
    out.append(Spacer(1, 5))
    if not compacto:
        out += grilla_graficos([
            grafico(ctx, "Distribución del hato por categoría", charts.generar_grafico_categorias),
            grafico(ctx, "Evolución del rebaño (6 meses)", charts.generar_grafico_evolucion_rebano, meses=6),
            grafico(ctx, "Entradas y salidas (12 meses)", charts.generar_grafico_waterfall_inventario),
            grafico(ctx, "Composición racial del hato", charts.generar_grafico_composicion_racial),
            grafico(ctx, "Ganancia diaria de peso (GMD)", charts.generar_grafico_gmd_hato),
        ], ctx.ancho)
    return out


def graficos_clave(ctx: ContextoReporte) -> list:
    """Grilla de gráficos del informe general: un gráfico por área."""
    from ..engine import charts
    serie = []
    try:
        serie = _serie_leche(ctx.db, ctx.desde_iso, ctx.hasta_iso)
    except Exception:
        logger.warning("Gráficos clave: serie de leche", exc_info=True)
    g = grilla_graficos([_grafico_serie_diaria(ctx, serie, "Producción diaria de leche")], ctx.ancho)
    g += grilla_graficos([
        grafico(ctx, "Estado reproductivo del hato", charts.generar_grafico_estado_reproductivo_hato),
        grafico(ctx, "Distribución del hato por categoría", charts.generar_grafico_categorias),
        grafico(ctx, "Ocupación y reposo por potrero", charts.generar_grafico_ocupacion_potreros),
        grafico(ctx, "Evolución del rebaño (6 meses)", charts.generar_grafico_evolucion_rebano, meses=6),
        grafico(ctx, "Flujo de caja del período", charts.generar_grafico_flujo_caja, desde=ctx.desde_iso, hasta=ctx.hasta_iso),
        grafico(ctx, "Intervalo entre partos (IEP)", charts.generar_grafico_iep_boxplot),
    ], ctx.ancho)
    return (_encabezado("GRÁFICOS CLAVE DE LA FINCA", ctx.ancho) + g) if g else []


# --------------------------------------------------------------------------- #
# TABLERO EJECUTIVO (informe general)
# --------------------------------------------------------------------------- #
def tablero_ejecutivo(ctx: ContextoReporte) -> list:
    """Una línea por área con su indicador principal y semáforo: la primera
    página del informe general resume toda la finca de un vistazo."""
    filas = []
    estilos = []

    def fila(area: str, indicador: str, valor: str, estado: str, lectura: str) -> None:
        colores = {"ok": COLOR_VERDE_OK, "atencion": COLOR_AMBAR, "critico": COLOR_ROJO_ALERTA, "": COLOR_GRIS}
        etiquetas = {"ok": "BIEN", "atencion": "ATENCIÓN", "critico": "CRÍTICO", "": "—"}
        i = len(filas) + 1
        filas.append([area, indicador, valor, etiquetas[estado], _p(lectura, _estilo(f"JA_Tab_{i}", fontSize=7.5, leading=9.5))])
        estilos.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor(colores[estado])))

    try:
        dl = datos_leche_periodo(ctx)
        if dl["serie"]:
            pct = ((dl["total"] - dl["total_ant"]) / dl["total_ant"] * 100) if dl["total_ant"] else 0
            fila("Leche", "Promedio diario", f"{num(dl['promedio'], 1)} L",
                 "critico" if pct <= -10 else ("atencion" if pct <= -5 else "ok"),
                 variacion(dl["total"], dl["total_ant"]) or f"{num(dl['total'])} L en el período")
    except Exception:
        logger.warning("Tablero: leche", exc_info=True)
    try:
        dr = datos_reproduccion_periodo(ctx)
        iep = dr["kpis"].get("iep_promedio_dias")
        da = dr["kpis"].get("dias_abiertos_promedio")
        if iep:
            fila("Reproducción", "Intervalo entre partos", f"{num(iep)} días",
                 "ok" if iep <= META_IEP else ("atencion" if iep <= META_IEP + 50 else "critico"),
                 f"Meta máx. {META_IEP} días. Días abiertos: {num(da)}" if da else f"Meta máx. {META_IEP} días")
        fert = dr["indice_fertilidad"]
        if fert.get("indice_pct") is not None:
            fila("Reproducción", "Índice de fertilidad", f"{num(fert['indice_pct'], 1)}%",
                 "critico" if "Alerta" in str(fert.get("diagnostico")) else "ok", str(fert.get("diagnostico") or ""))
    except Exception:
        logger.warning("Tablero: reproducción", exc_info=True)
    try:
        hoy_iso = ctx.hasta_iso
        r = ctx.db.query_one(
            "SELECT COUNT(DISTINCT t.animal_id) AS n FROM tratamientos t JOIN animales a ON a.id_animal = t.animal_id "
            "WHERE a.estado = 'ACTIVO' AND t.fecha <= ? AND (t.fecha_fin_retiro_leche >= ? OR t.fecha_fin_retiro_carne >= ?)",
            (hoy_iso, hoy_iso, hoy_iso))
        n_ret = int(r["n"]) if r else 0
        fila("Sanidad", "Animales en retiro", str(n_ret), "critico" if n_ret else "ok",
             "Separar leche / no vender para carne" if n_ret else "Sin retiros vigentes")
    except Exception:
        logger.warning("Tablero: sanidad", exc_info=True)
    try:
        from ..engine.dashboard_data import datos_pasturas
        pots = datos_pasturas(ctx.db).get("potreros") or []
        sobre = [p for p in pots if (p.get("total_animales") or 0) > 0 and (p.get("dias_ocupacion") or 0) > 3]
        if pots:
            fila("Pasturas", "Potreros sobreocupados", str(len(sobre)), "atencion" if sobre else "ok",
                 ", ".join(str(p.get("nombre") or p.get("codigo")) for p in sobre[:4]) or "Rotación al día")
    except Exception:
        logger.warning("Tablero: pasturas", exc_info=True)
    try:
        res = ctx.db.resumen_finanzas(ctx.desde_iso, ctx.hasta_iso) or {}
        if res.get("total_ingresos") or res.get("total_egresos"):
            util = res.get("utilidad", 0) or 0
            fila("Finanzas", "Utilidad del período", moneda(util), "ok" if util >= 0 else "critico",
                 f"Ingresos {moneda(res.get('total_ingresos'))} / egresos {moneda(res.get('total_egresos'))}")
    except Exception:
        logger.warning("Tablero: finanzas", exc_info=True)

    if not filas:
        return []
    datos = [["Área", "Indicador", "Valor", "Estado", "Lectura"]] + filas
    t = Table(datos, colWidths=[24 * mm, 38 * mm, 26 * mm, 20 * mm, ctx.ancho - 108 * mm], repeatRows=1)
    t.setStyle(tabla_style_moderna())
    t.setStyle(TableStyle(estilos + [("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold")]))
    return _encabezado("TABLERO EJECUTIVO DE LA FINCA", ctx.ancho) + [t, Spacer(1, 6)]


SECCIONES: dict[str, Callable[..., list]] = {
    "leche": seccion_leche,
    "produccion": seccion_leche,
    "repro": seccion_reproduccion,
    "reproduccion": seccion_reproduccion,
    "sanidad": seccion_sanidad,
    "tratamientos": seccion_sanidad,
    "pasturas": seccion_pasturas,
    "potreros": seccion_pasturas,
    "finanzas": seccion_finanzas,
    "caja": seccion_finanzas,
    "inventario": seccion_inventario,
    "hato": seccion_inventario,
}
