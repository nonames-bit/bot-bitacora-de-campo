"""Generación de gráficos (matplotlib + seaborn) para la ficha del animal y
paneles generales de la finca.

Opcional por diseño: si matplotlib no está instalado en el entorno, las
funciones devuelven ``None`` en vez de fallar, para que el resto del bot
(consultas de texto, registro de eventos, etc.) siga funcionando sin esta
dependencia. El llamador (telegram_bot.py) debe manejar el ``None`` mostrando
un mensaje de "gráfico no disponible" en vez de un error.

Varias de estas funciones son ESTIMACIONES a partir de los datos que el bot
sí captura (servicios + partos), no diagnósticos veterinarios reales (no
existe todavía un evento de "palpación/confirmación de preñez" ni de "costo
de tratamiento"). Se etiquetan explícitamente como "(estimado)" en el
gráfico para no hacerlas pasar por datos que no son.

Convenciones de diseño (todas las funciones las siguen):
- Título de marca (verde, negrita) + SUBTÍTULO de contexto (gris, chico) con
  cuántos animales/registros entran en el cálculo, el período analizado y
  qué significa el indicador -- un gráfico bonito sin esto es fácil de
  malinterpretar.
- Solo se etiquetan los puntos que importan para la lectura (mediana, último
  valor, meta, casos que requieren atención), nunca cada dato individual.
"""
from __future__ import annotations

import os
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from ..utils import to_date
from ..db.database import POTRERO_ACTUAL_EXPR, ULT_TRASLADO_CTE
from .query.helpers import calcular_existencias_potreros_sg

try:
    import matplotlib
    matplotlib.use("Agg")  # backend sin pantalla: obligatorio en servidor/VPS
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import fontManager
    import seaborn as sns
    _MATPLOTLIB_OK = True

    # Tipografía institucional: 'Inter' con fallback limpio a 'DejaVu Sans'
    _disponibles_fuentes = {f.name for f in fontManager.ttflist}
    _FUENTE_BASE = "Inter" if "Inter" in _disponibles_fuentes else "DejaVu Sans"

    # Tema base (seaborn) + ajustes de marca Ganadería JA
    sns.set_theme(style="whitegrid", font=_FUENTE_BASE)
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [_FUENTE_BASE, "DejaVu Sans", "Helvetica", "Arial", "sans-serif"],
        "font.size": 11.0,
        "axes.titlesize": 13.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 11.0,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "legend.frameon": True,
        "legend.framealpha": 0.9,
    })
except Exception:
    _MATPLOTLIB_OK = False

# Paleta refinada Ganadería JA: verdes, tierra, pizarra neutro y acentos armónicos
_COLOR_MARCA = "#2F5233"         # Verde institucional Ganadería JA
_COLOR_MARCA_CLARO = "#66BB6A"   # Verde acento / pasto
_COLOR_TIERRA = "#8D6E63"        # Tono tierra ganadero
_COLOR_GRIS = "#78909C"          # Gris pizarra neutro
_COLOR_ALERTA = "#EF5350"        # Rojo alerta suave
_COLOR_ACENTO = "#D4A373"        # Cuero / arena cálido

# 6 colores coherentes de la paleta JA
_PALETA = [
    "#2F5233",  # Verde oscuro institucional
    "#66BB6A",  # Verde claro
    "#8D6E63",  # Tierra
    "#78909C",  # Gris pizarra
    "#EF5350",  # Rojo alerta
    "#D4A373",  # Arena cálido
]

# Semáforo unificado consistente (Voisin, GMD, rankings y carga animal)
_COLOR_VERDE = "#2e7d32"
_COLOR_AMARILLO = "#f9a825"
_COLOR_NARANJA = "#ef6c00"
_COLOR_ROJO = "#c62828"

# Colores por categoría NDVI (mapa de potreros), ver src/gis/sentinel_ndvi.py::clasificar_ndvi
_COLOR_POR_CATEGORIA_NDVI = {
    "EXCELENTE": _COLOR_VERDE,
    "ÓPTIMO / REPOSO": _COLOR_AMARILLO,
    "ESTRÉS / BAJA BIOMASA": _COLOR_NARANJA,
    "CRÍTICO / SUELO DESNUDO": _COLOR_ROJO,
}

_COLOR_LINEA = "#2F5233"
_COLOR_PROMEDIO = "#9e9e9e"
_MESES_ES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def graficos_disponibles() -> bool:
    """True si matplotlib está instalado y listo para generar imágenes."""
    return _MATPLOTLIB_OK


def _estilo_ejes(ax, margin_x: float = 0.02, margin_y: Optional[float] = None) -> None:
    """Aplica un estilo limpio consistente a todos los gráficos del bot."""
    ax.grid(True, alpha=0.35, linewidth=0.6)
    sns.despine(ax=ax)
    ax.spines["left"].set_color("#666666")
    ax.spines["bottom"].set_color("#666666")
    ax.set_axisbelow(True)
    if margin_y is not None:
        ax.margins(x=margin_x, y=margin_y)
    else:
        ax.margins(x=margin_x)


def _titulo_y_subtitulo(fig, ax, titulo: str, subtitulo: str = "") -> None:
    """Título de marca (verde, negrita, arriba de la figura) + subtítulo de
    contexto (gris, chico, pegado al gráfico): cuántos animales/registros
    entran, qué período se analizó y qué significa el indicador. Sin esto,
    un gráfico bien hecho pero sin contexto es fácil de leer mal."""
    fig.suptitle(titulo, fontsize=13.5, fontweight="bold", color=_COLOR_MARCA, y=0.98)
    if subtitulo:
        ax.set_title(subtitulo, fontsize=9.0, color="#707070", style="italic", pad=8)


def _marcar_ultimo_valor(ax, x_ultimo, y_ultimo, texto: Optional[str] = None, color: Optional[str] = None) -> None:
    """Resalta el último punto de una serie temporal con un marcador y una
    etiqueta de texto. El "último valor" es uno de los pocos puntos que
    siempre vale la pena etiquetar (es el estado actual), a diferencia de
    etiquetar cada dato de la serie."""
    color = color or _COLOR_MARCA
    txt = texto if texto is not None else f"{y_ultimo:.1f}"
    ax.scatter([x_ultimo], [y_ultimo], color=color, s=90, zorder=5, edgecolor="white", linewidth=1.3)
    ax.annotate(f" {txt}", (x_ultimo, y_ultimo), textcoords="offset points", xytext=(6, 8),
                fontsize=9, fontweight="bold", color=color)


def _marcar_mediana_vertical(ax, valores: list, etiqueta_prefijo: str = "Mediana") -> Optional[float]:
    """Dibuja una línea vertical punteada en la mediana de `valores` (para
    gráficos de barras horizontales, ej. rankings) y la devuelve."""
    if not valores:
        return None
    mediana = statistics.median(valores)
    ax.axvline(mediana, color="#616161", linewidth=1.2, linestyle="--", alpha=0.8,
               label=f"{etiqueta_prefijo}: {mediana:.1f}")
    return mediana


def _guardar(fig, output_dir: str, nombre_archivo: str, dpi: int = 130,
             hoy: Optional[date] = None) -> str:
    """Guarda la figura con marca de agua institucional Ganadería JA."""
    os.makedirs(output_dir, exist_ok=True)
    ruta = os.path.join(output_dir, nombre_archivo)
    fecha_str = (hoy or date.today()).isoformat()
    # Marca de agua sutil, igual en todos los gráficos (identidad visual Ganadería JA)
    fig.text(0.99, 0.01, f"Ganadería JA · {fecha_str}", ha="right", va="bottom",
             fontsize=8, color="#999999", style="italic")
    fig.tight_layout(pad=1.2)
    # bbox_inches="tight" evita que títulos/leyendas largos queden cortados
    fig.savefig(ruta, facecolor="white", bbox_inches="tight", dpi=dpi)
    plt.close(fig)
    return ruta


def generar_grafico_placeholder(titulo: str = "Sin datos suficientes",
                                subtitulo: str = "Se requieren más registros para calcular este indicador",
                                output_dir: str = "data/reportes",
                                nombre_archivo: str = "grafico_sin_datos.png",
                                hoy: Optional[date] = None,
                                dpi: int = 130) -> Optional[str]:
    """Genera una figura placeholder elegante cuando no hay datos suficientes."""
    if not _MATPLOTLIB_OK:
        return None
    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=dpi)
    ax.axis("off")
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")
    rect = plt.Rectangle((0.02, 0.04), 0.96, 0.92, fill=False, edgecolor="#D7E5D9",
                         linewidth=1.5, linestyle="--", transform=ax.transAxes)
    ax.add_patch(rect)
    ax.text(0.5, 0.60, "Sin datos suficientes — Ganadería JA",
            ha="center", va="center", fontsize=13, fontweight="bold",
            color=_COLOR_MARCA, transform=ax.transAxes)
    ax.text(0.5, 0.40, f"{titulo}\n{subtitulo}",
            ha="center", va="center", fontsize=9.5, color="#707070",
            style="italic", transform=ax.transAxes)
    return _guardar(fig, output_dir, nombre_archivo, dpi=dpi, hoy=hoy)


# --------------------------------------------------------------------- #
# Ficha de un animal
# --------------------------------------------------------------------- #
def generar_grafico_peso(db, tag, output_dir: str = "data/reportes",
                         hoy: Optional[date] = None, dpi: int = 130,
                         placeholder_si_vacio: bool = False) -> Optional[str]:
    """Genera un PNG con la curva de crecimiento (peso_kg) del animal.

    Si se conoce la fecha de nacimiento, el eje X es la edad en días
    (comparable entre animales); si no, es la fecha del pesaje.
    Devuelve la ruta del archivo generado, o None si matplotlib no está
    disponible, el animal no existe, o tiene menos de 2 pesajes con peso.
    """
    if not _MATPLOTLIB_OK:
        return None
    aid = db.resolve_animal(tag)
    if aid is None:
        return None
    animal = db.get_animal(aid)
    if animal is None:
        return None

    pesajes = db.query(
        "SELECT fecha, peso_kg FROM pesajes WHERE animal_id = ? AND peso_kg IS NOT NULL "
        "AND fecha IS NOT NULL ORDER BY fecha",
        (aid,),
    )
    fnac = to_date(animal["fecha_nacimiento"]) if animal["fecha_nacimiento"] else None
    usar_edad = fnac is not None

    fechas: list = []
    xs: list = []
    ys: list[float] = []
    for p in pesajes:
        f = to_date(p["fecha"])
        if f is None:
            continue
        fechas.append(f)
        ys.append(float(p["peso_kg"]))
        xs.append((f - fnac).days if usar_edad else f)

    tag_str = animal["tag"] or str(tag)
    fecha_hoy = (hoy or date.today()).isoformat()

    if len(ys) < 2:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo=f"Curva de Crecimiento — {tag_str}",
                subtitulo="Se requieren al menos 2 pesajes registrados.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_peso_{tag_str}_{fecha_hoy}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=dpi)
    eje_x = xs if usar_edad else fechas
    ax.plot(eje_x, ys, marker="o", color=_COLOR_LINEA, linewidth=2.2, markersize=6, label="Peso del animal")
    _marcar_ultimo_valor(ax, eje_x[-1], ys[-1], texto=f"{ys[-1]:.0f} kg")

    # Comparación contra el promedio del hato (mismo sexo, edad similar):
    # solo si hay fecha de nacimiento (eje de edad) y suficientes animales
    # de referencia en la finca.
    if usar_edad and animal["sexo"]:
        prom = _promedio_peso_hato_por_edad(db, animal["sexo"], aid)
        if prom:
            xs_prom, ys_prom = zip(*prom)
            ax.plot(xs_prom, ys_prom, color=_COLOR_PROMEDIO, linewidth=1.6, linestyle="--",
                   label="Promedio del hato (mismo sexo)")

    if usar_edad:
        ax.set_xlabel("Edad (días)")
    else:
        ax.set_xlabel("Fecha")
        fig.autofmt_xdate()
    ax.set_ylabel("Peso (kg)")

    nombre = f" ({animal['nombre']})" if animal["nombre"] else ""
    rango = f"{fechas[0].isoformat()} a {fechas[-1].isoformat()}"
    _titulo_y_subtitulo(fig, ax, f"Curva de Crecimiento — {tag_str}{nombre}",
                        f"{len(ys)} pesajes · {rango}")
    _estilo_ejes(ax, margin_x=0.03, margin_y=0.05)
    ax.legend(loc="upper left", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_peso_{tag_str}_{fecha_hoy}.png", dpi=dpi, hoy=hoy)


def _promedio_peso_hato_por_edad(db, sexo: str, excluir_id: int, bucket_dias: int = 30) -> list[tuple[int, float]]:
    """Promedio de peso por bucket de edad (días, agrupado de a 30) entre
    los demás animales activos del mismo sexo con fecha de nacimiento
    conocida. Sirve de referencia visual, no es un cálculo estadístico
    formal (sin ajuste por raza, época, etc.)."""
    sexo_prefijo = (sexo or "").strip().lower()[:1]
    if not sexo_prefijo:
        return []
    filas = db.query(
        """
        SELECT p.fecha AS fecha_pesaje, p.peso_kg AS peso_kg, a.fecha_nacimiento AS fnac
        FROM pesajes p
        JOIN animales a ON a.id_animal = p.animal_id
        WHERE a.estado = 'ACTIVO' AND a.id_animal != ? AND p.peso_kg IS NOT NULL
          AND a.fecha_nacimiento IS NOT NULL AND LOWER(SUBSTR(a.sexo, 1, 1)) = ?
        """,
        (excluir_id, sexo_prefijo),
    )
    buckets: dict[int, list[float]] = {}
    for f in filas:
        fnac = to_date(f["fnac"])
        fp = to_date(f["fecha_pesaje"])
        if not fnac or not fp:
            continue
        edad = (fp - fnac).days
        if edad < 0:
            continue
        bucket = (edad // bucket_dias) * bucket_dias
        buckets.setdefault(bucket, []).append(float(f["peso_kg"]))
    if len(buckets) < 2:
        return []
    return sorted((b, sum(vals) / len(vals)) for b, vals in buckets.items())


def _promedio_leche_hato_por_del(db, excluir_id: int, bucket_dias: int = 15) -> list[tuple[int, float]]:
    """Promedio de litros/día por bucket de días en leche (DEL, agrupado de
    a 15 días) entre los demás animales activos, usando el último parto de
    cada uno para calcular el DEL de cada control. Referencia visual, mismo
    criterio que _promedio_peso_hato_por_edad."""
    filas = db.query(
        """
        SELECT pl.animal_id AS animal_id, pl.fecha AS fecha_control, pl.litros AS litros
        FROM produccion_leche pl
        JOIN animales a ON a.id_animal = pl.animal_id
        WHERE a.estado = 'ACTIVO' AND a.id_animal != ? AND pl.litros IS NOT NULL
        """,
        (excluir_id,),
    )
    if not filas:
        return []
    partos_cache: dict = {}
    buckets: dict[int, list[float]] = {}
    for f in filas:
        aid = f["animal_id"]
        if aid not in partos_cache:
            partos_cache[aid] = db.ultimo_parto(aid)
        parto = partos_cache[aid]
        if not parto or not parto["fecha"]:
            continue
        f_parto = to_date(parto["fecha"])
        f_control = to_date(f["fecha_control"])
        if not f_parto or not f_control:
            continue
        del_dias = (f_control - f_parto).days
        if del_dias < 0:
            continue
        bucket = (del_dias // bucket_dias) * bucket_dias
        buckets.setdefault(bucket, []).append(float(f["litros"]))
    if len(buckets) < 2:
        return []
    return sorted((b, sum(vals) / len(vals)) for b, vals in buckets.items())


def generar_grafico_lactancia(db, tag, output_dir: str = "data/reportes",
                              hoy: Optional[date] = None, dpi: int = 130,
                              placeholder_si_vacio: bool = False) -> Optional[str]:
    """Curva de lactancia individual (litros/día vs días en leche) sobre la
    curva promedio del hato, mismo estilo que generar_grafico_peso. Muestra
    de un vistazo el pico, la persistencia y si la vaca está cayendo antes
    de tiempo comparada con sus compañeras.

    Requiere al menos 2 controles de leche del animal y conocer la fecha de
    su último parto (para calcular días en leche); devuelve None si no hay
    suficientes datos todavía."""
    if not _MATPLOTLIB_OK:
        return None
    aid = db.resolve_animal(tag)
    if aid is None:
        return None
    animal = db.get_animal(aid)
    if animal is None:
        return None

    tag_str = animal["tag"] or str(tag)
    fecha_hoy = (hoy or date.today()).isoformat()

    controles = db.historial_leche(aid)
    ultimo_parto = db.ultimo_parto(aid)
    if ultimo_parto is None or not ultimo_parto["fecha"]:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo=f"Curva de Lactancia — {tag_str}",
                subtitulo="No se encontró fecha de último parto para calcular DEL.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_lactancia_{tag_str}_{fecha_hoy}.png",
                hoy=hoy, dpi=dpi,
            )
        return None
    f_parto = to_date(ultimo_parto["fecha"])
    if not f_parto:
        return None

    xs: list[int] = []
    ys: list[float] = []
    for c in controles:
        if c["litros"] is None:
            continue
        f_c = to_date(c["fecha"])
        if not f_c:
            continue
        dias_leche = (f_c - f_parto).days
        if dias_leche < 0:
            continue  # control de una lactancia anterior, no de esta
        xs.append(dias_leche)
        ys.append(float(c["litros"]))

    if len(xs) < 2:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo=f"Curva de Lactancia — {tag_str}",
                subtitulo="Se requieren al menos 2 controles de leche en la lactancia actual.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_lactancia_{tag_str}_{fecha_hoy}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=dpi)
    ax.plot(xs, ys, marker="o", color=_COLOR_LINEA, linewidth=2.2, markersize=6, label="Litros/día (individual)")
    _marcar_ultimo_valor(ax, xs[-1], ys[-1], texto=f"{ys[-1]:.1f} L")

    prom = _promedio_leche_hato_por_del(db, aid)
    if prom:
        xs_prom, ys_prom = zip(*prom)
        ax.plot(xs_prom, ys_prom, color=_COLOR_PROMEDIO, linewidth=1.6, linestyle="--",
                label="Promedio del hato")

    ax.set_xlabel("Días en leche (DEL)")
    ax.set_ylabel("Litros/día")
    nombre = f" ({animal['nombre']})" if animal["nombre"] else ""
    _titulo_y_subtitulo(fig, ax, f"Curva de Lactancia — {tag_str}{nombre}",
                        f"{len(xs)} controles de leche · último: día {xs[-1]} de lactancia")
    _estilo_ejes(ax, margin_x=0.03, margin_y=0.05)
    ax.legend(loc="upper right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_lactancia_{tag_str}_{fecha_hoy}.png", dpi=dpi, hoy=hoy)


# --------------------------------------------------------------------- #
# Panel general de la finca
# --------------------------------------------------------------------- #
def _movimientos_mensuales(db, meses: int, hoy: date):
    """Nacimientos/muertes/compras/ventas por mes de los últimos `meses`
    meses, más el inventario estimado al final de cada mes (retrocediendo
    desde el total activo de hoy). Compartido por generar_grafico_evolucion_rebano
    y generar_grafico_waterfall_inventario para no duplicar la lógica.
    Devuelve None si no hay ningún movimiento en la ventana."""
    periodos = []
    y, m = hoy.year, hoy.month
    for _ in range(meses):
        periodos.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    periodos.reverse()

    nacimientos, muertes_m, compras, ventas, etiquetas = [], [], [], [], []
    for (yy, mm) in periodos:
        desde = date(yy, mm, 1).isoformat()
        hasta = (date(yy + 1, 1, 1) if mm == 12 else date(yy, mm + 1, 1)).isoformat()
        n_nac = db.query_one(
            "SELECT COUNT(*) AS n FROM partos WHERE fecha >= ? AND fecha < ? "
            "AND (id_cria IS NULL OR id_cria != vaca_id)", (desde, hasta),
        )["n"]
        n_mue = db.query_one(
            "SELECT COUNT(*) AS n FROM muertes WHERE fecha >= ? AND fecha < ?", (desde, hasta)
        )["n"]
        n_compra = db.query_one(
            "SELECT COUNT(*) AS n FROM movimientos WHERE fecha >= ? AND fecha < ? "
            "AND UPPER(tipo_movimiento) IN ('COMPRA', 'ENTRADA')", (desde, hasta),
        )["n"]
        n_venta = db.query_one(
            "SELECT COUNT(*) AS n FROM movimientos WHERE fecha >= ? AND fecha < ? "
            "AND UPPER(tipo_movimiento) IN ('VENTA', 'SALIDA')", (desde, hasta),
        )["n"]
        nacimientos.append(n_nac)
        muertes_m.append(n_mue)
        compras.append(n_compra)
        ventas.append(n_venta)
        etiquetas.append(f"{_MESES_ES[mm]}\n{yy}")

    if sum(nacimientos) + sum(muertes_m) + sum(compras) + sum(ventas) == 0:
        return None

    activos_hoy = db.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado='ACTIVO'")["n"]
    niveles = [0] * len(periodos)
    niveles[-1] = activos_hoy
    for i in range(len(periodos) - 2, -1, -1):
        delta_sig = nacimientos[i + 1] + compras[i + 1] - muertes_m[i + 1] - ventas[i + 1]
        niveles[i] = niveles[i + 1] - delta_sig

    return etiquetas, nacimientos, muertes_m, compras, ventas, niveles


def generar_grafico_evolucion_rebano(db, meses: int = 12, output_dir: str = "data/reportes",
                                     hoy: Optional[date] = None, dpi: int = 130,
                                     placeholder_si_vacio: bool = False) -> Optional[str]:
    """Evolución mensual del hato: barras de nacimientos/muertes/compras/
    ventas y una línea de inventario estimado (eje secundario), igual al
    estilo del reporte "Tendencias de la población" de Software Ganadero.

    El inventario es una ESTIMACIÓN: parte del total de animales activos
    hoy y retrocede mes a mes restando/sumando los movimientos registrados
    en el bot. Si un animal fue importado sin su evento de nacimiento o
    compra en el bot, el nivel de meses muy anteriores puede no cuadrar
    exactamente con lo que había en Software Ganadero ese día.
    """
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    datos = _movimientos_mensuales(db, meses, hoy)
    if datos is None:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Evolución del Rebaño",
                subtitulo=f"Sin movimientos registrados en los últimos {meses} meses.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_evolucion_rebano_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None
    etiquetas, nacimientos, muertes_m, compras, ventas, niveles = datos

    x = range(len(etiquetas))
    fig, ax = plt.subplots(figsize=(9, 5), dpi=dpi)
    ancho = 0.2
    ax.bar([i - 1.5 * ancho for i in x], nacimientos, ancho, label="Nacimientos (crías)", color=_COLOR_VERDE)
    ax.bar([i - 0.5 * ancho for i in x], compras, ancho, label="Compras/Entradas", color=_COLOR_MARCA)
    ax.bar([i + 0.5 * ancho for i in x], ventas, ancho, label="Ventas/Salidas", color=_COLOR_TIERRA)
    ax.bar([i + 1.5 * ancho for i in x], muertes_m, ancho, label="Muertes", color=_COLOR_ROJO)
    ax.set_xticks(list(x))
    ax.set_xticklabels(etiquetas, fontsize=7.5)
    ax.set_ylabel("Animales por mes")
    _estilo_ejes(ax, margin_x=0.02)

    ax2 = ax.twinx()
    ax2.plot(list(x), niveles, color=_COLOR_ROJO, linewidth=2.2, marker="o", markersize=4,
             label="Inventario estimado")
    ax2.set_ylabel("Inventario estimado (total activos)")
    ax2.spines["top"].set_visible(False)
    ax2.grid(False)

    lineas1, etiquetas1 = ax.get_legend_handles_labels()
    lineas2, etiquetas2 = ax2.get_legend_handles_labels()
    ax.legend(lineas1 + lineas2, etiquetas1 + etiquetas2, loc="upper left", fontsize=8, ncol=2)
    _titulo_y_subtitulo(fig, ax, "Evolución del Rebaño",
                        f"{len(etiquetas)} meses · inventario final estimado: {niveles[-1]}")

    return _guardar(fig, output_dir, f"grafico_evolucion_rebano_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_categorias(db, output_dir: str = "data/reportes",
                               hoy: Optional[date] = None, dpi: int = 130,
                               placeholder_si_vacio: bool = False) -> Optional[str]:
    """Torta de distribución del hato activo por las categorías de Software
    Ganadero (cría hembra/macho, levante, novilla vientre, vaca parida/seca,
    ceba, reproductor), sumando todos los potreros más los animales sin
    potrero asignado."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    grupos = calcular_existencias_potreros_sg(db, hoy)
    if not grupos:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Distribución del Hato por Categorías",
                subtitulo="No hay animales activos registrados.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_categorias_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    totales = {"ch": 0, "hl": 0, "nv": 0, "vp": 0, "vs": 0, "cm": 0, "ml": 0, "mc": 0, "rep": 0}
    for g in grupos:
        for k in totales:
            totales[k] += g.get(k, 0)

    total_activos = db.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado='ACTIVO'")["n"]
    residual = total_activos - sum(totales.values())

    etiquetas_map = {
        "vp": "Vacas Paridas", "vs": "Vacas Secas", "nv": "Novillas Vientre",
        "hl": "Hembras Levante", "ch": "Crías Hembra", "cm": "Crías Macho",
        "ml": "Machos Levante", "mc": "Machos Ceba", "rep": "Reproductores",
    }
    etiquetas, valores = [], []
    for k, v in totales.items():
        if v > 0:
            etiquetas.append(etiquetas_map[k])
            valores.append(v)
    if residual > 0:
        etiquetas.append("Sin potrero asignado")
        valores.append(residual)
    if not valores:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Distribución del Hato por Categorías",
                subtitulo="No se registraron animales en categorías activas.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_categorias_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    fig, ax = plt.subplots(figsize=(7, 6), dpi=dpi)
    colores_pie = [_PALETA[i % len(_PALETA)] for i in range(len(valores))]
    ax.pie(
        valores, labels=None, autopct=lambda p: f"{p:.0f}%" if p >= 4 else "",
        colors=colores_pie, startangle=90,
        wedgeprops={"linewidth": 1.5, "edgecolor": "white"}, textprops={"fontsize": 9},
    )
    ax.legend(etiquetas, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9)
    _titulo_y_subtitulo(fig, ax, "Distribución del Hato por Categorías",
                        f"{total_activos} animales activos al {hoy.isoformat()}")
    ax.axis("equal")

    return _guardar(fig, output_dir, f"grafico_categorias_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_composicion_racial(db, output_dir: str = "data/reportes",
                                       hoy: Optional[date] = None, dpi: int = 130,
                                       placeholder_si_vacio: bool = False) -> Optional[str]:
    """Donut de pool genético y composición racial del hato activo.
    Grafica la proporción de sangre real de cada raza en el pool genético del hato.
    """
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    rows_comp = db.query(
        """SELECT cr.raza, SUM(cr.porcentaje) as pts, COUNT(DISTINCT cr.animal_id) as n
           FROM composicion_racial cr
           JOIN animales a ON a.id_animal = cr.animal_id
           WHERE a.estado = 'ACTIVO'
           GROUP BY cr.raza
           ORDER BY pts DESC"""
    )
    total_tipificados = db.query_one(
        "SELECT COUNT(DISTINCT animal_id) as n FROM composicion_racial cr JOIN animales a ON a.id_animal=cr.animal_id WHERE a.estado='ACTIVO'"
    )
    n_tipificados = int(total_tipificados["n"]) if total_tipificados else 0

    if not rows_comp or n_tipificados == 0:
        # Fallback a conteo de razas simples si no hay composición detallada
        rows = db.query(
            "SELECT COALESCE(NULLIF(TRIM(raza), ''), 'SIN RAZA') raza, COUNT(*) n "
            "FROM animales WHERE estado = 'ACTIVO' GROUP BY raza ORDER BY n DESC LIMIT 8"
        )
        total = sum(int(r["n"]) for r in rows)
        if not rows or total == 0:
            if placeholder_si_vacio:
                return generar_grafico_placeholder(
                    titulo="Composición Genética (Razas)",
                    subtitulo="No hay animales activos con raza registrada.",
                    output_dir=output_dir,
                    nombre_archivo=f"grafico_composicion_racial_{hoy.isoformat()}.png",
                    hoy=hoy, dpi=dpi,
                )
            return None
        etiquetas = [r["raza"] for r in rows]
        valores = [int(r["n"]) for r in rows]
        total_centro = total
        subtitulo_centro = "animales"
    else:
        # Agrupar Top 5 razas y colapsar las restantes en 'Otras razas'
        from .genetic_engine import normalizar_nombre_raza
        total_puntos = sum(float(r["pts"]) for r in rows_comp)
        top_rows = rows_comp[:5]
        resto_rows = rows_comp[5:]

        etiquetas = []
        valores = []
        for r in top_rows:
            nom = normalizar_nombre_raza(r["raza"])
            pts = float(r["pts"])
            pct = (pts / total_puntos * 100.0) if total_puntos else 0.0
            n_ani = int(r["n"])
            etiquetas.append(f"{nom}: {pct:.1f}% ({n_ani} cab)")
            valores.append(pts)

        if resto_rows:
            pts_resto = sum(float(r["pts"]) for r in resto_rows)
            pct_resto = (pts_resto / total_puntos * 100.0) if total_puntos else 0.0
            etiquetas.append(f"Otras razas: {pct_resto:.1f}%")
            valores.append(pts_resto)

        total_centro = n_tipificados
        subtitulo_centro = "tipificados"

    colores = [_PALETA[i % len(_PALETA)] for i in range(len(valores))]

    fig, ax = plt.subplots(figsize=(7, 6), dpi=dpi)
    ax.pie(
        valores, labels=None, autopct=lambda p: f"{p:.1f}%" if p >= 4 else "",
        colors=colores, startangle=90, pctdistance=0.82,
        wedgeprops={"width": 0.42, "linewidth": 1.5, "edgecolor": "white"},
        textprops={"fontsize": 9, "color": "white", "fontweight": "bold"},
    )
    ax.text(0, 0, str(total_centro), ha="center", va="center", fontsize=22, fontweight="bold", color=_COLOR_MARCA)
    ax.text(0, -0.18, subtitulo_centro, ha="center", va="center", fontsize=9, color=_COLOR_GRIS)
    ax.legend(etiquetas, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9)
    _titulo_y_subtitulo(fig, ax, "Pool Genético del Hato (% Sangre)",
                        f"{total_centro} animales tipificados al {hoy.isoformat()}")
    ax.axis("equal")

    return _guardar(fig, output_dir, f"grafico_composicion_racial_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_gmd_hato(db, output_dir: str = "data/reportes",
                             hoy: Optional[date] = None, dpi: int = 130,
                             placeholder_si_vacio: bool = False) -> Optional[str]:
    """Dispersión de la Ganancia Media Diaria (GMD) de todos los animales
    activos con al menos 2 pesajes, contra su edad al último pesaje."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    animales = db.query(
        "SELECT id_animal, tag, sexo, fecha_nacimiento FROM animales WHERE estado='ACTIVO'"
    )
    xs_h, ys_h, xs_m, ys_m = [], [], [], []
    for a in animales:
        pesajes = db.query(
            "SELECT fecha, peso_kg FROM pesajes WHERE animal_id = ? AND peso_kg IS NOT NULL "
            "ORDER BY fecha DESC LIMIT 2", (a["id_animal"],),
        )
        if len(pesajes) < 2:
            continue
        ultimo, anterior = pesajes[0], pesajes[1]
        f1, f2 = to_date(anterior["fecha"]), to_date(ultimo["fecha"])
        fnac = to_date(a["fecha_nacimiento"])
        if not f1 or not f2 or (f2 - f1).days <= 0 or not fnac:
            continue
        gmd = (float(ultimo["peso_kg"]) - float(anterior["peso_kg"])) / (f2 - f1).days
        edad = (f2 - fnac).days
        sexo = (a["sexo"] or "").strip().lower()
        if sexo.startswith("h"):
            xs_h.append(edad); ys_h.append(gmd)
        elif sexo.startswith("m"):
            xs_m.append(edad); ys_m.append(gmd)

    if len(xs_h) + len(xs_m) < 2:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Ganancia Media Diaria del Hato",
                subtitulo="Se requieren al menos 2 animales con fecha de nacimiento y 2+ pesajes.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_gmd_hato_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    todos_gmd = ys_h + ys_m
    n_negativos = sum(1 for v in todos_gmd if v < 0)
    mediana_gmd = statistics.median(todos_gmd)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)
    if xs_h:
        ax.scatter(xs_h, ys_h, color=_COLOR_MARCA, label="Hembras", alpha=0.75, s=45)
    if xs_m:
        ax.scatter(xs_m, ys_m, color=_COLOR_TIERRA, label="Machos", alpha=0.75, s=45)
    ax.axhline(0, color="#616161", linewidth=1, linestyle=":")
    ax.axhline(mediana_gmd, color=_COLOR_MARCA, linewidth=1.2, linestyle="--", alpha=0.8,
               label=f"Mediana: {mediana_gmd:.2f} kg/día")
    ax.set_xlabel("Edad al último pesaje (días)")
    ax.set_ylabel("GMD (kg/día)")
    subtitulo = f"{len(todos_gmd)} animales con 2+ pesajes"
    if n_negativos:
        subtitulo += f" · ⚠️ {n_negativos} con GMD negativa (requieren atención)"
    _titulo_y_subtitulo(fig, ax, "Ganancia Media Diaria del Hato", subtitulo)
    _estilo_ejes(ax, margin_x=0.03, margin_y=0.05)
    ax.legend(loc="upper right", fontsize=9)

    return _guardar(fig, output_dir, f"grafico_gmd_hato_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def _calcular_ieps(db) -> list[int]:
    """Intervalos (en días) entre partos consecutivos de cada vaca."""
    vacas = db.query(
        "SELECT DISTINCT vaca_id FROM partos WHERE vaca_id IS NOT NULL AND (id_cria IS NULL OR id_cria != vaca_id)"
    )
    ieps: list[int] = []
    for v in vacas:
        partos = db.query(
            "SELECT fecha FROM partos WHERE vaca_id = ? AND fecha IS NOT NULL "
            "AND (id_cria IS NULL OR id_cria != vaca_id) ORDER BY fecha", (v["vaca_id"],),
        )
        fechas = [to_date(p["fecha"]) for p in partos if to_date(p["fecha"])]
        for i in range(1, len(fechas)):
            dias = (fechas[i] - fechas[i - 1]).days
            if dias > 0:
                ieps.append(dias)
    return ieps


def generar_grafico_iep_boxplot(db, output_dir: str = "data/reportes",
                                hoy: Optional[date] = None,
                                umbral_max_dias: Optional[int] = 730,
                                dpi: int = 130,
                                placeholder_si_vacio: bool = False) -> Optional[str]:
    """Boxplot (con los puntos individuales superpuestos) del intervalo
    entre partos (IEP, en días) de todas las vacas con 2 o más partos, para
    detectar vacas atípicas (outliers).

    Por defecto excluye intervalos mayores a ``umbral_max_dias`` (2 años):
    en la práctica, un hato con historial importado de años atrás y con
    huecos de registro (no se cargó todo parto real en el sistema) produce
    intervalos "fantasma" de varios años entre dos partos reales de la
    misma vaca que en realidad tuvo partos intermedios sin registrar. Un
    intervalo real de más de 2 años sin que la vaca haya sido descartada es
    prácticamente imposible en manejo normal, así que es mucho más probable
    que sea un hueco de datos que un caso real. Pase
    ``umbral_max_dias=None`` para ver el histórico completo sin filtrar
    (útil para auditar esos huecos)."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    ieps_todos = _calcular_ieps(db)
    if umbral_max_dias is not None:
        ieps = [d for d in ieps_todos if d <= umbral_max_dias]
        n_excluidos = len(ieps_todos) - len(ieps)
    else:
        ieps = ieps_todos
        n_excluidos = 0

    if len(ieps) < 3:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Intervalo Entre Partos (IEP)",
                subtitulo="Se requieren al menos 3 intervalos entre partos calculables.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_iep_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    mediana = statistics.median(ieps)

    fig, ax = plt.subplots(figsize=(6, 5.5), dpi=dpi)
    sns.boxplot(y=ieps, ax=ax, color=_COLOR_MARCA_CLARO, width=0.35, showfliers=False)
    sns.stripplot(y=ieps, ax=ax, color=_COLOR_TIERRA, alpha=0.65, size=5, jitter=0.12)
    ax.axhline(365, color=_COLOR_VERDE, linewidth=1.4, linestyle="--", label="Meta: 365 días (1 parto/año)")
    ax.annotate(f"Mediana: {mediana:.0f}d", (0.18, mediana), fontsize=8.5, color=_COLOR_MARCA,
                fontweight="bold", va="center")
    ax.set_ylabel("Intervalo entre partos (días)")
    ax.set_xticks([])

    subtitulo = f"{len(ieps)} intervalo(s) · vacas con 2+ partos"
    if n_excluidos > 0:
        subtitulo += f" · {n_excluidos} excluido(s) >{umbral_max_dias}d (probable hueco de registro)"
    _titulo_y_subtitulo(fig, ax, "Intervalo Entre Partos (IEP)", subtitulo)
    _estilo_ejes(ax, margin_x=0.05)
    ax.legend(loc="upper right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_iep_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_iep_boxplot_completo(db, output_dir: str = "data/reportes",
                                         hoy: Optional[date] = None, dpi: int = 130,
                                         placeholder_si_vacio: bool = False) -> Optional[str]:
    """Versión del boxplot de IEP sin filtrar outliers (histórico completo),
    para cuando se quiere auditar los huecos de registro en vez de
    esconderlos."""
    return generar_grafico_iep_boxplot(db, output_dir=output_dir, hoy=hoy, umbral_max_dias=None,
                                       dpi=dpi, placeholder_si_vacio=placeholder_si_vacio)


def generar_grafico_peso_destete_por_raza(db, output_dir: str = "data/reportes",
                                          hoy: Optional[date] = None, dpi: int = 130,
                                          placeholder_si_vacio: bool = False) -> Optional[str]:
    """Barras del peso promedio al destete (pesajes.evento='DESTETE'),
    agrupado por raza del animal."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    filas = db.query(
        "SELECT a.raza AS raza, p.peso_kg AS peso_kg FROM pesajes p "
        "JOIN animales a ON a.id_animal = p.animal_id "
        "WHERE UPPER(p.evento) = 'DESTETE' AND p.peso_kg IS NOT NULL AND a.raza IS NOT NULL"
    )
    por_raza: dict[str, list[float]] = {}
    for f in filas:
        raza = (f["raza"] or "").strip() or "Sin raza"
        por_raza.setdefault(raza, []).append(float(f["peso_kg"]))
    if not por_raza:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Peso al Destete por Raza",
                subtitulo="No hay pesajes de destete registrados con raza asignada.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_destete_raza_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    razas = sorted(por_raza, key=lambda r: -sum(por_raza[r]) / len(por_raza[r]))
    promedios = [sum(por_raza[r]) / len(por_raza[r]) for r in razas]
    conteos = [len(por_raza[r]) for r in razas]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)
    colores_barras = [_PALETA[i % len(_PALETA)] for i in range(len(razas))]
    barras = ax.bar(razas, promedios, color=colores_barras)
    for barra, n in zip(barras, conteos):
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height(), f" n={n}",
               ha="center", va="bottom", fontsize=8, rotation=0)
    ax.set_ylabel("Peso promedio al destete (kg)")
    ax.tick_params(axis="x", rotation=20, labelsize=9)
    _titulo_y_subtitulo(fig, ax, "Peso al Destete por Raza",
                        f"{sum(conteos)} destetes registrados · {len(razas)} raza(s)")
    _estilo_ejes(ax, margin_x=0.03, margin_y=0.08)

    return _guardar(fig, output_dir, f"grafico_destete_raza_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_rendimiento_padre(db, output_dir: str = "data/reportes",
                                      hoy: Optional[date] = None, dpi: int = 130,
                                      placeholder_si_vacio: bool = False) -> Optional[str]:
    """Barras del peso promedio al nacer de las crías, agrupado por padre
    (solo padres registrados como animal local vía genealogía -- no cubre
    pajuelas de IA sin un animal correspondiente en el sistema)."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    filas = db.query(
        """
        SELECT padre.tag AS padre_tag, padre.nombre AS padre_nombre, p.peso_nacimiento AS peso
        FROM partos p
        JOIN animales cria ON cria.id_animal = p.id_cria
        JOIN animales padre ON padre.id_animal = cria.padre_id
        WHERE p.peso_nacimiento IS NOT NULL AND cria.padre_id IS NOT NULL
        """
    )
    por_padre: dict[str, list[float]] = {}
    for f in filas:
        etiqueta = f["padre_tag"] or "?"
        if f["padre_nombre"]:
            etiqueta += f" ({f['padre_nombre']})"
        por_padre.setdefault(etiqueta, []).append(float(f["peso"]))
    # Solo padres con al menos 2 crías pesadas (evitar comparar con n=1)
    por_padre = {k: v for k, v in por_padre.items() if len(v) >= 2}
    if not por_padre:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Rendimiento por Padre/Reproductor",
                subtitulo="Se requieren al menos 2 crías pesadas al nacer por padre.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_rendimiento_padre_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    padres = sorted(por_padre, key=lambda k: -sum(por_padre[k]) / len(por_padre[k]))
    promedios = [sum(por_padre[k]) / len(por_padre[k]) for k in padres]
    conteos = [len(por_padre[k]) for k in padres]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)
    colores_padres = [_PALETA[i % len(_PALETA)] for i in range(len(padres))]
    barras = ax.barh(padres, promedios, color=colores_padres)
    for barra, n in zip(barras, conteos):
        ax.text(barra.get_width(), barra.get_y() + barra.get_height() / 2, f" n={n}",
               ha="left", va="center", fontsize=8)
    ax.set_xlabel("Peso promedio al nacer de sus crías (kg)")
    _titulo_y_subtitulo(fig, ax, "Rendimiento por Padre/Reproductor",
                        f"{sum(conteos)} crías con peso al nacer · {len(padres)} padre(s) con 2+ crías")
    _estilo_ejes(ax, margin_x=0.08, margin_y=0.03)

    return _guardar(fig, output_dir, f"grafico_rendimiento_padre_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_aforo_potreros(db, output_dir: str = "data/reportes",
                                   hoy: Optional[date] = None, dpi: int = 130,
                                   placeholder_si_vacio: bool = False) -> Optional[str]:
    """Barras del aforo (kg/m²) registrado por potrero, coloreado por tipo
    de pasto. Es una foto del último aforo cargado por potrero, no una
    serie histórica (el bot no guarda un historial de aforos repetidos)."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    potreros = db.query(
        "SELECT nombre, codigo, tipo_pasto, aforo_kg_m2 FROM potreros "
        "WHERE aforo_kg_m2 IS NOT NULL ORDER BY aforo_kg_m2 DESC"
    )
    if not potreros:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Aforo de Forraje por Potrero",
                subtitulo="No hay aforos registrados en los potreros.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_aforo_potreros_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    nombres = [(p["nombre"] or p["codigo"] or "?") for p in potreros]
    valores = [float(p["aforo_kg_m2"]) for p in potreros]
    pastos = [(p["tipo_pasto"] or "Sin dato") for p in potreros]
    pastos_unicos = sorted(set(pastos))
    color_de_pasto = {p: _PALETA[i % len(_PALETA)] for i, p in enumerate(pastos_unicos)}
    colores = [color_de_pasto[p] for p in pastos]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)
    ax.bar(nombres, valores, color=colores)
    ax.set_ylabel("Aforo (kg/m²)")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    _titulo_y_subtitulo(fig, ax, "Aforo de Forraje por Potrero",
                        f"{len(nombres)} potrero(s) · última medición cargada (no es serie histórica)")
    _estilo_ejes(ax, margin_x=0.03, margin_y=0.06)

    parches = [plt.Rectangle((0, 0), 1, 1, color=color_de_pasto[p]) for p in pastos_unicos]
    ax.legend(parches, pastos_unicos, loc="upper right", fontsize=8, title="Tipo de pasto")

    return _guardar(fig, output_dir, f"grafico_aforo_potreros_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_ocupacion_potreros(db, output_dir: str = "data/reportes",
                                       hoy: Optional[date] = None, dpi: int = 130,
                                       placeholder_si_vacio: bool = False) -> Optional[str]:
    """Barras horizontales de días de ocupación actual por potrero
    (semáforo Voisin: verde ≤3d, amarillo ≤6d, rojo >6d)."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    grupos = calcular_existencias_potreros_sg(db, hoy)
    if not grupos:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Ocupación de Potreros (Rotación Voisin)",
                subtitulo="No hay ocupación de potreros registrada actualmente.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_ocupacion_potreros_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    nombres, dias_ocup, colores = [], [], []
    for g in grupos:
        f_ingreso = g.get("fecha_ingreso_reciente")
        d = (hoy - to_date(f_ingreso)).days if f_ingreso and to_date(f_ingreso) else None
        if d is None:
            continue
        nombres.append(g["display"])
        dias_ocup.append(d)
        colores.append(_COLOR_VERDE if d <= 3 else (_COLOR_AMARILLO if d <= 6 else _COLOR_ROJO))

    if not nombres:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Ocupación de Potreros (Rotación Voisin)",
                subtitulo="Sin traslados recientes para calcular días de ocupación.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_ocupacion_potreros_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    orden = sorted(range(len(nombres)), key=lambda i: -dias_ocup[i])
    nombres = [nombres[i] for i in orden]
    dias_ocup = [dias_ocup[i] for i in orden]
    colores = [colores[i] for i in orden]

    fig, ax = plt.subplots(figsize=(7, max(3.5, 0.4 * len(nombres))), dpi=dpi)
    ax.barh(nombres, dias_ocup, color=colores)
    ax.axvline(3, color="#616161", linewidth=1, linestyle=":", label="Meta Voisin: ≤3 días")
    ax.set_xlabel("Días de ocupación actual")
    _titulo_y_subtitulo(fig, ax, "Ocupación de Potreros (Rotación Voisin)",
                        f"{len(nombres)} potrero(s) ocupado(s) al {hoy.isoformat()}")
    _estilo_ejes(ax, margin_x=0.05, margin_y=0.02)
    ax.legend(loc="lower right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_ocupacion_potreros_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def _animales_activos_por_potrero_vigente(db) -> dict:
    """Conteo de animales ACTIVO por potrero VIGENTE (auditoría P2.12).

    Usa la expresión canónica (`POTRERO_ACTUAL_EXPR` = potrero_id → último
    traslado si es NULL) que ya usan Inventario/Mapa/Pasturas. Antes el gráfico
    NDVI agrupaba solo por `animales.potrero_id`, así que un animal trasladado
    con `potrero_id` NULL quedaba fuera y el gráfico contradecía a esas vistas.
    """
    conteo: dict = {}
    for r in db.query(
        f"WITH {ULT_TRASLADO_CTE} "
        f"SELECT {POTRERO_ACTUAL_EXPR} AS potrero_id, COUNT(*) AS n "
        "FROM animales a "
        "LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1 "
        "WHERE a.estado = 'ACTIVO' "
        f"GROUP BY {POTRERO_ACTUAL_EXPR}"
    ):
        if r["potrero_id"] is not None:
            conteo[r["potrero_id"]] = r["n"]
    return conteo


def generar_mapa_potreros(db, output_dir: str = "data/reportes",
                          hoy: Optional[date] = None, dpi: int = 130) -> Optional[str]:
    """Mapa de los potreros reales (Fase B del plan geoespacial: los que
    tienen `geom_wkt_4326`), coloreados por categoría NDVI satelital
    (verde/amarillo/naranja/rojo) y etiquetados con el número de animales
    activos y los días de ocupación (o de reposo si está vacío).

    No incluye los códigos legacy sin geometría real (ver
    docs/PLAN_GEO_SATELITAL_6.2_8.2.md sección 3.5) por la misma razón que
    ya se excluyen de `Database.resumen_ndvi_finca()`: no tienen una
    ubicación fija que dibujar."""
    if not _MATPLOTLIB_OK:
        return None
    import math
    from matplotlib.patches import Polygon
    from shapely import wkt as shapely_wkt

    hoy = hoy or date.today()
    potreros = db.query(
        "SELECT id, nombre, area_has, geom_wkt_4326, centroide_lat, centroide_lon, "
        "dias_ocupacion, dias_reposo FROM potreros WHERE geom_wkt_4326 IS NOT NULL"
    )
    if not potreros:
        return None

    ndvi_por_potrero = {p["potrero_id"]: p for p in db.resumen_ndvi_finca().get("potreros", [])}
    animales_por_potrero = _animales_activos_por_potrero_vigente(db)

    lats = [float(p["centroide_lat"]) for p in potreros if p["centroide_lat"] is not None]
    lat_promedio = sum(lats) / len(lats) if lats else 0.0

    fig, ax = plt.subplots(figsize=(9, 8), dpi=dpi)
    categorias_presentes: set[str] = set()

    for p in potreros:
        try:
            poligono = shapely_wkt.loads(p["geom_wkt_4326"])
            coords = list(poligono.exterior.coords)
        except Exception:
            continue

        ndvi_info = ndvi_por_potrero.get(p["id"])
        categoria = ndvi_info["categoria"] if ndvi_info else "ÓPTIMO / REPOSO"
        categorias_presentes.add(categoria)
        color = _COLOR_POR_CATEGORIA_NDVI.get(categoria, _COLOR_GRIS)

        ax.add_patch(Polygon(coords, closed=True, facecolor=color, edgecolor="white",
                             linewidth=1.0, alpha=0.85))

        n_animales = animales_por_potrero.get(p["id"], 0)
        if n_animales > 0:
            dias_txt = f"{p['dias_ocupacion']}d" if p["dias_ocupacion"] is not None else "ocupado"
        else:
            dias_txt = f"{p['dias_reposo']}d" if p["dias_reposo"] is not None else "vacío"

        lat = p["centroide_lat"]
        lon = p["centroide_lon"]
        if lat is not None and lon is not None:
            etiqueta = f"{p['nombre']}\n{n_animales}u · {dias_txt}"
            ax.annotate(etiqueta, (lon, lat), ha="center", va="center", fontsize=5.3,
                       fontweight="bold", color="#1a1a1a", linespacing=1.15, zorder=6,
                       bbox=dict(boxstyle="round,pad=0.15", facecolor="white", alpha=0.65, linewidth=0))

    # Corrección de aspecto: a esta latitud, 1° de longitud recorre menos
    # distancia real que 1° de latitud (factor cos(lat)) -- sin esto el mapa
    # se ve visualmente achatado/estirado.
    if lat_promedio:
        ax.set_aspect(1.0 / math.cos(math.radians(lat_promedio)))
    ax.autoscale_view()
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    _titulo_y_subtitulo(fig, ax, "Mapa de Potreros (NDVI + Ocupación)",
                        f"{len(potreros)} potrero(s) con ubicación real · vigor forrajero satelital")
    ax.grid(True, alpha=0.25, linewidth=0.5)

    orden_categorias = ["EXCELENTE", "ÓPTIMO / REPOSO", "ESTRÉS / BAJA BIOMASA", "CRÍTICO / SUELO DESNUDO"]
    presentes_ordenadas = [c for c in orden_categorias if c in categorias_presentes]
    parches = [plt.Rectangle((0, 0), 1, 1, color=_COLOR_POR_CATEGORIA_NDVI[c]) for c in presentes_ordenadas]
    ax.legend(parches, presentes_ordenadas, loc="upper right", fontsize=7.5, title="Vigor NDVI", title_fontsize=8)

    return _guardar(fig, output_dir, f"mapa_potreros_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def _hembra_prenada_estimado(db, aid: int) -> bool:
    """Estimación: True si el último servicio o diagnóstico de la hembra
    indica preñez activa y no tiene un parto registrado después de esa fecha."""
    ult_diag = db.ultimo_diagnostico(aid)
    ult = db.ultimo_servicio(aid)
    if ult_diag and ult_diag["fecha"]:
        f_diag = to_date(ult_diag["fecha"])
        f_serv = to_date(ult["fecha"]) if ult and ult["fecha"] else None
        if not f_serv or not f_diag or f_diag >= f_serv:
            res = (ult_diag["resultado"] or "").upper()
            parto = db.query_one(
                "SELECT id FROM partos WHERE vaca_id = ? AND fecha >= ? LIMIT 1", (aid, ult_diag["fecha"])
            )
            return bool(res in ("PREÑADA", "PRENADA", "CONFIRMADA", "POSITIVA") and parto is None)

    if ult is None or not ult["fecha"]:
        return False
    estado_ult = ult["estado"] if "estado" in ult.keys() else None
    if (estado_ult or "").upper() in ("FALLIDO", "VACIA", "VACÍA"):
        return False
    parto = db.query_one(
        "SELECT id FROM partos WHERE vaca_id = ? AND fecha >= ? LIMIT 1", (aid, ult["fecha"])
    )
    return parto is None


def generar_grafico_prenadas_vacias_potrero(db, output_dir: str = "data/reportes",
                                            hoy: Optional[date] = None, dpi: int = 130,
                                            placeholder_si_vacio: bool = False) -> Optional[str]:
    """Barras apiladas por potrero: hembras en edad reproductiva (≥1 año)
    preñadas (estimado) vs vacías, más el total de animales del potrero
    como referencia. "Preñada" aquí es una ESTIMACIÓN por servicio sin
    parto posterior -- el bot no registra diagnóstico de preñez (palpación/
    ecografía) como evento propio todavía."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    grupos = calcular_existencias_potreros_sg(db, hoy)
    if not grupos:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Preñadas vs Vacías por Potrero",
                subtitulo="No hay registros de potreros activos.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_prenadas_potrero_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    nombres, totales, prenadas, vacias = [], [], [], []
    for g in grupos:
        n_prenadas = 0
        n_vacias = 0
        for a in g.get("animales", []):
            sexo = (a["sexo"] or "").strip().lower()
            if not sexo.startswith("h"):
                continue
            fnac = to_date(a["fecha_nacimiento"])
            if fnac and (hoy - fnac).days < 365:
                continue  # cría, no aplica
            if _hembra_prenada_estimado(db, a["id_animal"]):
                n_prenadas += 1
            else:
                n_vacias += 1
        if n_prenadas + n_vacias == 0:
            continue
        nombres.append(g["display"])
        totales.append(g["total"])
        prenadas.append(n_prenadas)
        vacias.append(n_vacias)

    if not nombres:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Preñadas vs Vacías por Potrero",
                subtitulo="No se encontraron hembras adultas (≥1 año) con estado reproductivo.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_prenadas_potrero_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.5 * len(nombres))), dpi=dpi)
    ax.barh(nombres, prenadas, color=_COLOR_VERDE, label="Preñadas (estimado)")
    ax.barh(nombres, vacias, left=prenadas, color=_COLOR_TIERRA, label="Vacías")
    for i, tot in enumerate(totales):
        ax.text(prenadas[i] + vacias[i], i, f"  potrero: {tot} animales en total", va="center", fontsize=8)
    ax.set_xlabel("Hembras en edad reproductiva")
    _titulo_y_subtitulo(fig, ax, "Preñadas vs Vacías por Potrero",
                        f"al {hoy.isoformat()} · estimado por servicio sin parto posterior")
    _estilo_ejes(ax, margin_x=0.08, margin_y=0.02)
    ax.legend(loc="lower right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_prenadas_potrero_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_waterfall_inventario(db, meses: int = 12, output_dir: str = "data/reportes",
                                         hoy: Optional[date] = None, dpi: int = 130,
                                         placeholder_si_vacio: bool = False) -> Optional[str]:
    """Waterfall (cascada) del inventario mensual: una barra de inicio, un
    escalón por mes (verde si el neto del mes fue positivo, rojo si fue
    negativo) y una barra final, para ver de un vistazo cómo se llegó del
    inventario de hace `meses` meses al de hoy sin tener que leer una tabla.

    Usa el mismo inventario ESTIMADO que generar_grafico_evolucion_rebano
    (ver su docstring para la limitación de animales importados sin evento
    de nacimiento/compra propio en el bot)."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    datos = _movimientos_mensuales(db, meses, hoy)
    if datos is None:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Waterfall de Inventario Mensual",
                subtitulo=f"Sin movimientos registrados en los últimos {meses} meses.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_waterfall_inventario_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None
    etiquetas, nacimientos, muertes_m, compras, ventas, niveles = datos

    deltas = [nacimientos[i] + compras[i] - muertes_m[i] - ventas[i] for i in range(len(etiquetas))]
    inicio = niveles[0] - deltas[0]
    niveles_completos = [inicio] + list(niveles)  # longitud = len(etiquetas) + 1

    categorias = ["Inicio"] + etiquetas + ["Actual"]
    n = len(categorias)

    color_inicio_fin = _COLOR_GRIS
    color_sube = _COLOR_VERDE
    color_baja = _COLOR_ROJO

    fig, ax = plt.subplots(figsize=(max(9, 0.9 * n), 5.5), dpi=dpi)

    # Barras de inicio y final: representan el total (van desde 0), no un cambio.
    ax.bar(0, inicio, color=color_inicio_fin, width=0.6)
    ax.text(0, inicio, f" {int(round(inicio))}", ha="center", va="bottom", fontsize=8)
    ax.bar(n - 1, niveles_completos[-1], color=color_inicio_fin, width=0.6)
    ax.text(n - 1, niveles_completos[-1], f" {int(round(niveles_completos[-1]))}", ha="center", va="bottom", fontsize=8)

    # Escalones mensuales: barras flotantes entre el nivel anterior y el nuevo.
    for i, d in enumerate(deltas):
        base = min(niveles_completos[i], niveles_completos[i + 1])
        alto = abs(d)
        color = color_sube if d >= 0 else color_baja
        ax.bar(i + 1, alto, bottom=base, color=color, width=0.6)
        signo = "+" if d > 0 else ""
        ax.text(i + 1, max(niveles_completos[i], niveles_completos[i + 1]),
                f" {signo}{d}", ha="center", va="bottom", fontsize=8)

    # Líneas conectoras punteadas entre el borde de cada barra y la siguiente.
    for k in range(len(niveles_completos)):
        ax.plot([k + 0.3, k + 1 - 0.3], [niveles_completos[k], niveles_completos[k]],
                color="#bbbbbb", linewidth=1, linestyle=":")

    ax.set_xticks(range(n))
    ax.set_xticklabels(categorias, fontsize=8)
    ax.set_ylabel("Inventario estimado (total activos)")
    _titulo_y_subtitulo(fig, ax, "Waterfall de Inventario Mensual",
                        f"{len(etiquetas)} meses · nacimientos + compras − muertes − ventas (estimado)")
    _estilo_ejes(ax, margin_x=0.02)

    return _guardar(fig, output_dir, f"grafico_waterfall_inventario_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def _kaplan_meier(observaciones: list) -> tuple:
    """Estimador de Kaplan-Meier clásico. ``observaciones`` es una lista de
    (tiempo_dias, evento) donde evento=True significa que el evento
    (siguiente servicio) ocurrió en ese tiempo, y evento=False significa
    censurado (todavía sin servicio a la fecha de corte -- no es que "no
    haya pasado nada", es que no se sabe todavía). Devuelve
    (tiempos, supervivencia) para graficar como función escalonada."""
    datos = sorted(observaciones, key=lambda x: x[0])
    tiempos = [0]
    supervivencia = [1.0]
    s = 1.0
    en_riesgo = len(datos)
    i = 0
    while i < len(datos):
        t = datos[i][0]
        eventos_en_t = 0
        n_en_t = 0
        while i < len(datos) and datos[i][0] == t:
            if datos[i][1]:
                eventos_en_t += 1
            n_en_t += 1
            i += 1
        if eventos_en_t > 0 and en_riesgo > 0:
            s *= (1 - eventos_en_t / en_riesgo)
            tiempos.append(t)
            supervivencia.append(s)
        en_riesgo -= n_en_t
    return tiempos, supervivencia


def generar_grafico_flujo_caja(db, output_dir: str = "data/reportes",
                               desde: Optional[str] = None, hasta: Optional[str] = None,
                               hoy: Optional[date] = None, dpi: int = 130,
                               placeholder_si_vacio: bool = False) -> Optional[str]:
    """Barras agrupadas de ingresos/egresos por mes + línea de utilidad, para
    ver estacionalidad del flujo de caja (no solo el acumulado del año)."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    desde = desde or date(hoy.year, 1, 1).isoformat()
    hasta = hasta or date(hoy.year, 12, 31).isoformat()
    filas = db.flujo_caja_mensual(desde, hasta)
    if not filas:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Flujo de Caja Mensual",
                subtitulo="Sin movimientos financieros en el periodo.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_flujo_caja_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    meses = [f["mes"] for f in filas]
    ingresos = [f["ingresos"] for f in filas]
    egresos = [f["egresos"] for f in filas]
    utilidad = [f["utilidad"] for f in filas]

    x = list(range(len(meses)))
    ancho = 0.38
    fig, ax = plt.subplots(figsize=(9, 5), dpi=dpi)
    ax.bar([i - ancho / 2 for i in x], ingresos, width=ancho, label="Ingresos", color=_COLOR_VERDE)
    ax.bar([i + ancho / 2 for i in x], egresos, width=ancho, label="Egresos", color=_COLOR_ROJO)
    ax.plot(x, utilidad, color=_COLOR_MARCA, marker="o", linewidth=2, label="Utilidad")
    ax.axhline(0, color="#616161", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(meses, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Pesos ($)")
    total_util = sum(utilidad)
    _titulo_y_subtitulo(fig, ax, "Flujo de Caja Mensual",
                        f"{len(meses)} mes(es) · utilidad del periodo: ${total_util:,.0f}".replace(",", "."))
    _estilo_ejes(ax, margin_x=0.03)
    ax.legend(loc="upper left", fontsize=8, ncol=3)

    return _guardar(fig, output_dir, f"grafico_flujo_caja_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_dias_abiertos_km(db, output_dir: str = "data/reportes",
                                     hoy: Optional[date] = None, dpi: int = 130,
                                     placeholder_si_vacio: bool = False) -> Optional[str]:
    """Curva de Kaplan-Meier de días abiertos: eje X = días desde el parto,
    eje Y = % de vacas que seguían sin un servicio posterior a esa altura.
    A diferencia de un promedio simple de días abiertos (que excluye a las
    vacas que todavía no han sido servidas), esto SÍ las incluye como
    "censuradas" -- por eso no da un número artificialmente bueno.

    "Servicio posterior" es la señal disponible más cercana a "dejó de
    estar vacía" -- el bot no tiene todavía un evento propio de confirmación
    de preñez (palpación/ecografía), igual que en el resto de las consultas
    de reproducción de este bot."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    partos = db.query(
        "SELECT vaca_id, fecha FROM partos WHERE vaca_id IS NOT NULL AND fecha IS NOT NULL "
        "AND (id_cria IS NULL OR id_cria != vaca_id) ORDER BY vaca_id, fecha"
    )
    observaciones = []
    for p in partos:
        f_parto = to_date(p["fecha"])
        if not f_parto:
            continue
        siguiente_servicio = db.query_one(
            "SELECT fecha FROM servicios WHERE vaca_id = ? AND fecha >= ? "
            "ORDER BY fecha ASC LIMIT 1", (p["vaca_id"], p["fecha"]),
        )
        if siguiente_servicio and siguiente_servicio["fecha"]:
            f_serv = to_date(siguiente_servicio["fecha"])
            if f_serv and (f_serv - f_parto).days >= 0:
                observaciones.append(((f_serv - f_parto).days, True))
                continue
        dias_censura = (hoy - f_parto).days
        if dias_censura >= 0:
            observaciones.append((dias_censura, False))

    if len(observaciones) < 5:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Días Abiertos (Kaplan-Meier)",
                subtitulo="Se requieren al menos 5 observaciones posparto.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_dias_abiertos_km_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    tiempos, supervivencia = _kaplan_meier(observaciones)
    porcentajes = [s * 100 for s in supervivencia]

    # Días donde la curva cruza el 50% (mediana de días abiertos "vencidos"):
    # el primer tiempo en el que menos de la mitad del hato sigue abierta.
    mediana_dias = None
    for t, p in zip(tiempos, porcentajes):
        if p <= 50:
            mediana_dias = t
            break

    fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)
    ax.step(tiempos, porcentajes, where="post", color=_COLOR_MARCA, linewidth=2.3)
    ax.fill_between(tiempos, porcentajes, step="post", color=_COLOR_MARCA, alpha=0.12)
    ax.axhline(50, color="#9e9e9e", linewidth=1, linestyle=":")
    if mediana_dias is not None:
        ax.axvline(mediana_dias, color=_COLOR_MARCA, linewidth=1.2, linestyle="--")
        ax.annotate(f"Mediana: {mediana_dias}d", (mediana_dias, 52), fontsize=8.5,
                    color=_COLOR_MARCA, fontweight="bold")
    ax.set_xlabel("Días posparto")
    ax.set_ylabel("% de vacas aún sin servicio posterior")
    ax.set_ylim(0, 105)
    _titulo_y_subtitulo(fig, ax, "Días Abiertos — Curva de Kaplan-Meier",
                        f"n={len(observaciones)} intervalo(s) posparto · evento = siguiente servicio registrado")
    _estilo_ejes(ax, margin_x=0.02)

    return _guardar(fig, output_dir, f"grafico_dias_abiertos_km_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


# --------------------------------------------------------------------- #
# Producción de leche del hato (agregada, no individual)
# --------------------------------------------------------------------- #
def _controles_leche_por_semana(db) -> dict:
    """Agrupa todos los controles de leche por semana (lunes de esa semana):
    {lunes: {"litros": total, "vacas": {ids}}}. Se agrupa por semana y no
    por día porque el control es semanal, no diario -- un total "por día"
    tendría casi todos los días en cero."""
    controles = db.query(
        "SELECT animal_id, fecha, litros FROM produccion_leche WHERE litros IS NOT NULL AND fecha IS NOT NULL"
    )
    por_semana: dict = defaultdict(lambda: {"litros": 0.0, "vacas": set()})
    for c in controles:
        f = to_date(c["fecha"])
        if not f:
            continue
        lunes = f - timedelta(days=f.weekday())
        por_semana[lunes]["litros"] += float(c["litros"])
        por_semana[lunes]["vacas"].add(c["animal_id"])
    return por_semana


def generar_grafico_leche_total_hato(db, semanas: int = 12, output_dir: str = "data/reportes",
                                     hoy: Optional[date] = None, dpi: int = 130,
                                     placeholder_si_vacio: bool = False, dias_max: int = 31) -> Optional[str]:
    """Producción total diaria de leche del hato (tanque / recibos diarios de la finca),
    mostrando el volumen entregado por día, el promedio del período y la tendencia.

    Prioriza la era moderna (>= 2024) para graficar los litros diarios cargados por
    recibos de leche, sin mezclar datos históricos desactualizados de 2016-2018.
    """
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    # 1. Verificamos si existen registros de la era moderna (>= 2024)
    hay_modernos = db.query_one(
        "SELECT 1 FROM produccion_leche WHERE fecha >= '2024-01-01' LIMIT 1"
    )
    filtro = "fecha >= '2024-01-01'" if hay_modernos else "1=1"

    filas = db.query(f"""
        SELECT fecha, SUM(litros) AS litros
        FROM produccion_leche
        WHERE litros IS NOT NULL AND litros > 0 AND {filtro}
        GROUP BY fecha
        ORDER BY fecha ASC
    """)

    if not filas or len(filas) < 1:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Producción Total Diaria de Leche",
                subtitulo="Se requieren registros diarios de leche en la bitácora.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_leche_total_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    # Tomamos los últimos dias_max días cronológicamente
    filas_recientes = filas[-dias_max:]
    fechas_dt = [to_date(f["fecha"]) for f in filas_recientes]
    etiquetas = [d.strftime("%d-%b") if d else f["fecha"] for d, f in zip(fechas_dt, filas_recientes)]
    litros = [float(f["litros"]) for f in filas_recientes]

    total_litros = sum(litros)
    promedio = total_litros / len(litros)
    pico = max(litros)

    fig, ax = plt.subplots(figsize=(10, 5), dpi=dpi)
    x = range(len(etiquetas))
    barras = ax.bar(x, litros, color=_COLOR_MARCA, width=0.62, edgecolor="#1B301E", linewidth=0.8, alpha=0.92, label="Litros entregados")
    
    # Línea de promedio diario
    ax.axhline(promedio, color="#D97706", linestyle="--", linewidth=1.8, label=f"Promedio: {promedio:.1f} L/día")

    # Etiquetas de valor encima de las barras
    for i, (b, val) in enumerate(zip(barras, litros)):
        es_pico = (val == pico)
        txt_color = "#15803D" if es_pico else "#1F2937"
        peso = "bold" if es_pico else "normal"
        ax.text(i, val + (max(litros) * 0.015), f"{val:.0f}", ha="center", va="bottom",
                fontsize=8, fontweight=peso, color=txt_color)

    ax.set_ylabel("Litros diarios (L)", fontsize=9, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(etiquetas, rotation=45, ha="right", fontsize=8)
    ax.legend(loc="upper right", frameon=True, fontsize=8.5)

    subtitulo = f"{len(litros)} días registrados · Total: {total_litros:,.0f} L · Promedio: {promedio:.1f} L/día · Pico: {pico:.0f} L"
    _titulo_y_subtitulo(fig, ax, "Producción Total Diaria de Leche (Tanque / Recibos)", subtitulo)
    _estilo_ejes(ax, margin_x=0.03, margin_y=0.10)

    return _guardar(fig, output_dir, f"grafico_leche_total_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_eficiencia_lechera(db, semanas: int = 12, output_dir: str = "data/reportes",
                                       hoy: Optional[date] = None, dpi: int = 130,
                                       placeholder_si_vacio: bool = False) -> Optional[str]:
    """Litros por vaca en ordeño por día, por semana: total de litros de esa
    semana dividido entre las vacas con control esa semana y entre 7 días.
    Es el indicador de eficiencia, no solo de volumen -- una finca puede
    producir más litros totales solo por tener más vacas, sin ser más
    eficiente por vaca."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    por_semana = _controles_leche_por_semana(db)
    if len(por_semana) < 2:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Eficiencia Lechera del Hato",
                subtitulo="Se requieren al menos 2 semanas de controles de leche.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_eficiencia_lechera_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    semanas_ordenadas = sorted(por_semana.keys())[-semanas:]
    etiquetas = [s.strftime("%d-%b") for s in semanas_ordenadas]
    eficiencia = [
        por_semana[s]["litros"] / len(por_semana[s]["vacas"]) / 7
        for s in semanas_ordenadas if por_semana[s]["vacas"]
    ]
    if len(eficiencia) < 2:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Eficiencia Lechera del Hato",
                subtitulo="Se requieren al menos 2 semanas con datos válidos de eficiencia.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_eficiencia_lechera_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    fig, ax = plt.subplots(figsize=(9, 5), dpi=dpi)
    ax.plot(etiquetas, eficiencia, marker="o", color=_COLOR_VERDE, linewidth=2.2, markersize=6)
    _marcar_ultimo_valor(ax, len(etiquetas) - 1, eficiencia[-1], texto=f"{eficiencia[-1]:.1f} L/vaca/día")
    ax.set_ylabel("Litros / vaca en ordeño / día")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    _titulo_y_subtitulo(fig, ax, "Eficiencia Lechera del Hato",
                        f"{len(eficiencia)} semanas · litros totales ÷ vacas con control ÷ 7 días")
    _estilo_ejes(ax, margin_x=0.03, margin_y=0.06)

    return _guardar(fig, output_dir, f"grafico_eficiencia_lechera_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_ranking_vacas_leche(db, output_dir: str = "data/reportes",
                                        hoy: Optional[date] = None, dpi: int = 130,
                                        placeholder_si_vacio: bool = False) -> Optional[str]:
    """Ranking de vacas activas por promedio de litros/control, para
    identificar las mejores productoras y las candidatas a revisar/
    descartar de un vistazo. Verde = tercio superior, rojo = tercio
    inferior (candidatas a revisión), gris = medio."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    filas = db.query(
        """
        SELECT pl.animal_id AS animal_id, a.tag AS tag, a.nombre AS nombre,
               AVG(pl.litros) AS promedio, COUNT(*) AS n
        FROM produccion_leche pl
        JOIN animales a ON a.id_animal = pl.animal_id
        WHERE pl.litros IS NOT NULL AND a.estado = 'ACTIVO'
        GROUP BY pl.animal_id
        """
    )
    if len(filas) < 3:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Ranking de Vacas por Producción de Leche",
                subtitulo="Se requieren al menos 3 vacas activas con controles de leche.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_ranking_leche_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    filas_ordenadas = sorted(filas, key=lambda f: -f["promedio"])
    etiquetas = []
    valores = []
    for f in filas_ordenadas:
        nom = f"{f['tag']} ({f['nombre']})" if f["nombre"] else f["tag"]
        etiquetas.append(nom)
        valores.append(f["promedio"])

    n = len(valores)
    tercio = max(1, n // 3)
    colores = []
    for i in range(n):
        if i < tercio:
            colores.append(_COLOR_VERDE)
        elif i >= n - tercio:
            colores.append(_COLOR_ROJO)
        else:
            colores.append(_COLOR_GRIS)

    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.35 * n)), dpi=dpi)
    ax.barh(list(reversed(etiquetas)), list(reversed(valores)), color=list(reversed(colores)))
    _marcar_mediana_vertical(ax, valores)
    ax.set_xlabel("Promedio de litros por control")
    _titulo_y_subtitulo(fig, ax, "Ranking de Vacas por Producción de Leche",
                        f"{n} vaca(s) con controles registrados · verde = mejor tercio, rojo = revisar/descartar")
    _estilo_ejes(ax, margin_x=0.06, margin_y=0.02)
    ax.legend(loc="lower right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_ranking_leche_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


# --------------------------------------------------------------------- #
# Estado reproductivo agregado del hato
# --------------------------------------------------------------------- #
def generar_grafico_estado_reproductivo_hato(db, output_dir: str = "data/reportes",
                                             hoy: Optional[date] = None, dpi: int = 130,
                                             placeholder_si_vacio: bool = False) -> Optional[str]:
    """Estado reproductivo de todo el hato (no por potrero): hembras nunca
    servidas, vacías servidas y preñadas (estimado), más la tasa de preñez
    sobre las hembras expuestas (servidas). Misma limitación que el resto
    de las estimaciones reproductivas de este archivo: "preñada" es un
    servicio abierto sin parto posterior, no un diagnóstico real."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    hembras = db.query(
        "SELECT id_animal, fecha_nacimiento FROM animales "
        "WHERE estado = 'ACTIVO' AND LOWER(SUBSTR(sexo, 1, 1)) = 'h'"
    )
    n_prenadas = 0
    n_vacias_servidas = 0
    n_nunca_servidas = 0
    for h in hembras:
        fnac = to_date(h["fecha_nacimiento"])
        if fnac and (hoy - fnac).days < 365:
            continue  # cría, no aplica
        ult_serv = db.ultimo_servicio(h["id_animal"])
        if ult_serv is None:
            n_nunca_servidas += 1
            continue
        if _hembra_prenada_estimado(db, h["id_animal"]):
            n_prenadas += 1
        else:
            n_vacias_servidas += 1

    expuestas = n_prenadas + n_vacias_servidas
    if expuestas == 0:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Estado Reproductivo del Hato",
                subtitulo="No hay hembras activas expuestas a reproducción.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_estado_reproductivo_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None
    tasa = n_prenadas / expuestas * 100
    total_hembras = expuestas + n_nunca_servidas

    categorias = ["Preñadas\n(estimado)", "Vacías\n(servidas)", "Nunca\nservidas"]
    valores = [n_prenadas, n_vacias_servidas, n_nunca_servidas]
    colores = [_COLOR_VERDE, _COLOR_AMARILLO, _COLOR_GRIS]

    fig, ax = plt.subplots(figsize=(7, 5.5), dpi=dpi)
    barras = ax.bar(categorias, valores, color=colores)
    ax.set_ylim(0, max(valores) * 1.22)
    for barra, v in zip(barras, valores):
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height(), f" {v}",
                ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("Hembras en edad reproductiva")
    _titulo_y_subtitulo(fig, ax, "Estado Reproductivo del Hato",
                        f"{total_hembras} hembras activas ≥1 año al {hoy.isoformat()}")
    _estilo_ejes(ax, margin_x=0.04, margin_y=0.06)
    ax.text(0.98, 0.95, f"Tasa de preñez (sobre expuestas): {tasa:.0f}%",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            color=_COLOR_MARCA, fontweight="bold")

    return _guardar(fig, output_dir, f"grafico_estado_reproductivo_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


# --------------------------------------------------------------------- #
# Carga animal por hectárea (UGG/ha)
# --------------------------------------------------------------------- #
def _ugg_de_animal(db, animal_id: int, fecha_nacimiento, hoy: date) -> float:
    """Estima las Unidades Gran Ganado (UGG, 1 UGG = 450 kg de peso vivo) de
    un animal. Usa su último pesaje real si existe; si no, un estimado por
    categoría de edad (cría/levante/adulto) -- menos preciso, pero evita
    dejar fuera del cálculo a los animales sin pesaje registrado."""
    ultimo_peso = db.query_one(
        "SELECT peso_kg FROM pesajes WHERE animal_id = ? AND peso_kg IS NOT NULL ORDER BY fecha DESC LIMIT 1",
        (animal_id,),
    )
    if ultimo_peso and ultimo_peso["peso_kg"]:
        return float(ultimo_peso["peso_kg"]) / 450.0
    fnac = to_date(fecha_nacimiento)
    edad = (hoy - fnac).days if fnac else None
    if edad is not None and edad < 365:
        return 0.3
    if edad is not None and edad < 730:
        return 0.6
    return 1.0


def generar_grafico_carga_animal_potrero(db, output_dir: str = "data/reportes",
                                         hoy: Optional[date] = None, dpi: int = 130,
                                         placeholder_si_vacio: bool = False) -> Optional[str]:
    """UGG/ha por potrero, usando el último peso conocido de cada animal (o
    un estimado por categoría cuando no hay pesaje) sobre el área real de
    cada potrero. Útil para detectar sobrecarga antes de que se note en el
    pasto."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    grupos = calcular_existencias_potreros_sg(db, hoy)
    if not grupos:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Carga Animal por Potrero",
                subtitulo="No hay existencias de potreros activas.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_carga_animal_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    potreros_area = {p["id"]: p["area_has"] for p in db.query("SELECT id, area_has FROM potreros")}

    nombres = []
    cargas = []
    for g in grupos:
        area_total = sum(potreros_area.get(pid) or 0 for pid in g.get("ids", set()))
        if not area_total:
            continue
        ugg_total = sum(
            _ugg_de_animal(db, a["id_animal"], a["fecha_nacimiento"], hoy)
            for a in g.get("animales", [])
        )
        nombres.append(g["display"])
        cargas.append(ugg_total / area_total)

    if not nombres:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Carga Animal por Potrero",
                subtitulo="No hay potreros con área (has) asignada para calcular UGG/ha.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_carga_animal_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    orden = sorted(range(len(nombres)), key=lambda i: -cargas[i])
    nombres = [nombres[i] for i in orden]
    cargas = [cargas[i] for i in orden]
    colores = [_COLOR_ROJO if c > 3 else (_COLOR_AMARILLO if c > 2 else _COLOR_VERDE) for c in cargas]

    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.4 * len(nombres))), dpi=dpi)
    ax.barh(nombres, cargas, color=colores)
    ax.set_xlabel("Carga animal (UGG/ha, estimado)")
    _titulo_y_subtitulo(fig, ax, "Carga Animal por Potrero",
                        f"{len(nombres)} potrero(s) · UGG = peso vivo/450kg (o estimado por edad)")
    _estilo_ejes(ax, margin_x=0.06, margin_y=0.02)

    return _guardar(fig, output_dir, f"grafico_carga_animal_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_subastas_comparativa(db, output_dir: str = "data/reportes",
                                        hoy: Optional[date] = None, dpi: int = 130,
                                        placeholder_si_vacio: bool = False,
                                        producto: str = "MACHO_GORDO",
                                        categoria: Optional[str] = None) -> Optional[str]:
    """Barras horizontales comparativas de precios de subastas ganaderas ($/kg en pie)
    en 8 plazas comerciales relevantes para la finca."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    producto = categoria or producto
    datos = db.obtener_datos_mercado_completos()
    comp = datos.get("comparativa_por_categoria", {}).get(producto, [])
    if not comp:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Subastas Ganaderas · Comparativa de Precios",
                subtitulo=f"Sin cotizaciones registradas para {producto}.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_subastas_comparativa_{producto.lower()}_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    # Ordenar de menor a mayor precio para barh (los más altos quedan arriba)
    comp_sorted = sorted(comp, key=lambda x: x["precio_promedio"])
    nombres = []
    precios = []
    colores = []
    textos_valores = []

    # Encontrar el promedio nacional para la línea de referencia
    prom_nal = next((x["precio_promedio"] for x in comp if x["plaza_key"] == "PROMEDIO_NACIONAL"), None)

    for item in comp_sorted:
        pz_key = item["plaza_key"]
        dist = f"{item['distancia_km']}km" if item.get("distancia_km") else "Nacional"
        nombre_label = f"{item['nombre']} ({dist})"
        nombres.append(nombre_label)
        p = item["precio_promedio"]
        precios.append(p)

        # Colorear según relevancia: Granada (local) verde oscuro, Mejor precio verde brillante, Promedio gris, resto tierra/pizarra
        if pz_key == "GRANADA":
            colores.append(_COLOR_MARCA)  # Verde institucional
        elif item.get("es_mejor_precio"):
            colores.append(_COLOR_VERDE)  # Verde acento mejor precio
        elif pz_key == "PROMEDIO_NACIONAL":
            colores.append(_COLOR_GRIS)
        else:
            colores.append("#52796F")

        # Texto del valor con indicador de tendencia
        tend = item.get("tendencia", "ESTABLE")
        flecha = "▲" if tend == "SUBIENDO" else ("▼" if tend == "BAJANDO" else "▬")
        var_txt = f"{flecha}{'+' if item.get('variacion_pct', 0) > 0 else ''}{item.get('variacion_pct', 0):.1f}%"
        textos_valores.append(f" ${p:,.0f} ({var_txt})")

    fig, ax = plt.subplots(figsize=(8.5, max(4.0, 0.45 * len(nombres))), dpi=dpi)
    bars = ax.barh(nombres, precios, color=colores, height=0.62)

    # Anotar valores al final de cada barra
    max_p = max(precios)
    min_p = min(precios)
    rango = max_p - min_p if max_p > min_p else 1000
    ax.set_xlim(left=max(0, min_p - rango * 0.4), right=max_p + rango * 0.35)

    for bar, txt, p in zip(bars, textos_valores, precios):
        ax.text(p + rango * 0.02, bar.get_y() + bar.get_height() / 2, txt,
                va="center", ha="left", fontsize=9.5, fontweight="bold", color="#333333")

    if prom_nal:
        ax.axvline(prom_nal, color=_COLOR_GRIS, linestyle="--", linewidth=1.2,
                   label=f"Promedio Nacional: ${prom_nal:,.0f}/kg")
        ax.legend(loc="lower right", fontsize=9.0)

    cat_labels = {
        "MACHO_GORDO": "Macho Gordo (400+ kg)",
        "MACHO_LEVANTE": "Macho 1 ½ años (Levante)",
        "TERNERO_DESTETO": "Ternero(a) Desteto",
        "HEMBRA_LEVANTE": "Hembra Levante",
        "VACA_GORDA": "Vaca Descarte / Gorda",
    }
    cat_nom = cat_labels.get(producto, producto)
    _titulo_y_subtitulo(fig, ax, f"Subastas Ganaderas · {cat_nom}",
                        "Cotizaciones oficiales semanales ($/kg en pie) · Referencia desde Mesetas, Meta")
    ax.set_xlabel("Precio en pie ($/kg)")
    _estilo_ejes(ax, margin_x=0.08, margin_y=0.03)

    return _guardar(fig, output_dir, f"grafico_subastas_comparativa_{producto.lower()}_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)


def generar_grafico_subastas_tendencia(db, output_dir: str = "data/reportes",
                                       hoy: Optional[date] = None, dpi: int = 130,
                                       placeholder_si_vacio: bool = False,
                                       producto: str = "MACHO_GORDO",
                                       categoria: Optional[str] = None) -> Optional[str]:
    """Líneas de tendencia histórica semanal de precios de subastas ($/kg) en mercados clave."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    producto = categoria or producto
    datos = db.obtener_datos_mercado_completos()
    subastas = datos.get("subastas", [])

    # Plazas clave para la comparativa temporal
    PLAZAS_CLAVE = [
        ("GRANADA", "Granada (Ariari - Local)", _COLOR_MARCA, "o", "-"),
        ("CATAMA", "Catama (Villavicencio)", _COLOR_VERDE, "s", "-"),
        ("BOGOTA", "Bogotá (Guadalupe)", "#1E88E5", "^", "-"),
        ("PROMEDIO_NACIONAL", "Promedio Nacional FEDEGÁN", _COLOR_GRIS, "D", "--"),
    ]

    series_a_graficar = []
    todas_fechas = set()

    for pz_key, pz_nombre, col, marker, lstyle in PLAZAS_CLAVE:
        pz_obj = next((s for s in subastas if s["plaza_key"] == pz_key), None)
        if not pz_obj:
            continue
        p_obj = pz_obj.get("productos", {}).get(producto)
        if not p_obj:
            continue
        hist = p_obj.get("historico_semanal", [])
        if not hist:
            continue
        fechas = [h["fecha"] for h in hist]
        precios = [h["precio"] for h in hist]
        todas_fechas.update(fechas)
        series_a_graficar.append({
            "key": pz_key,
            "nombre": pz_nombre,
            "color": col,
            "marker": marker,
            "linestyle": lstyle,
            "fechas": fechas,
            "precios": precios,
        })

    if not series_a_graficar or len(todas_fechas) < 2:
        if placeholder_si_vacio:
            return generar_grafico_placeholder(
                titulo="Tendencia Histórica de Precios de Subasta",
                subtitulo=f"Se requieren al menos 2 semanas de cotizaciones para {producto}.",
                output_dir=output_dir,
                nombre_archivo=f"grafico_subastas_tendencia_{producto.lower()}_{hoy.isoformat()}.png",
                hoy=hoy, dpi=dpi,
            )
        return None

    fechas_ordenadas = sorted(list(todas_fechas))
    fechas_etiquetas = []
    for f in fechas_ordenadas:
        try:
            d_obj = to_date(f)
            fechas_etiquetas.append(f"{d_obj.day:02d} {_MESES_ES[d_obj.month]}")
        except Exception:
            fechas_etiquetas.append(f)

    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=dpi)

    for s in series_a_graficar:
        x_pts = []
        y_pts = []
        for i, f in enumerate(fechas_ordenadas):
            if f in s["fechas"]:
                idx_h = s["fechas"].index(f)
                x_pts.append(i)
                y_pts.append(s["precios"][idx_h])

        if not x_pts:
            continue

        ax.plot(x_pts, y_pts, label=s["nombre"], color=s["color"],
                marker=s["marker"], linestyle=s["linestyle"], linewidth=2.2, markersize=6.5)

        if x_pts:
            ult_x = x_pts[-1]
            ult_y = y_pts[-1]
            _marcar_ultimo_valor(ax, ult_x, ult_y, f"${ult_y:,.0f}", color=s["color"])

    ax.set_xticks(range(len(fechas_ordenadas)))
    ax.set_xticklabels(fechas_etiquetas, fontsize=9.5)
    ax.set_ylabel("Precio en pie ($/kg)", fontsize=10.5)

    cat_labels = {
        "MACHO_GORDO": "Macho Gordo (400+ kg)",
        "MACHO_LEVANTE": "Macho 1 ½ años (Levante)",
        "TERNERO_DESTETO": "Ternero(a) Desteto",
        "HEMBRA_LEVANTE": "Hembra Levante",
        "VACA_GORDA": "Vaca Descarte / Gorda",
    }
    cat_nom = cat_labels.get(producto, producto)
    _titulo_y_subtitulo(fig, ax, f"Tendencia de Precios en Subasta · {cat_nom}",
                        "Evolución semanal ($/kg en pie) · Plazas clave para Ganadería JA (Mesetas)")

    ax.legend(loc="upper left", fontsize=9.0, framealpha=0.92)
    _estilo_ejes(ax, margin_x=0.06, margin_y=0.12)

    return _guardar(fig, output_dir, f"grafico_subastas_tendencia_{producto.lower()}_{hoy.isoformat()}.png", dpi=dpi, hoy=hoy)

