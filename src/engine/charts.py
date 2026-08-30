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
from .query.helpers import calcular_existencias_potreros_sg

try:
    import matplotlib
    matplotlib.use("Agg")  # backend sin pantalla: obligatorio en servidor/VPS
    import matplotlib.pyplot as plt
    import seaborn as sns
    _MATPLOTLIB_OK = True
    # Tema base (seaborn) + ajustes de marca encima. sns.set_theme configura
    # rcParams globalmente (grilla clara, tipografía, tamaños) -- una mejora
    # de calidad visual "gratis" en los ~20 gráficos del bot sin tener que
    # afinar cada uno a mano. Los ajustes de marca (color de título, etc.) se
    # aplican después para que no se pierdan.
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    plt.rcParams.update({
        "font.size": 10.5,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 10.5,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "legend.frameon": True,
        "legend.framealpha": 0.9,
    })
except Exception:
    _MATPLOTLIB_OK = False

# Paleta viva, inspirada en la app móvil de Software Ganadero (colores
# saturados y distinguibles entre sí incluso con 8-9 categorías).
_PALETA = [
    "#2196F3", "#3F51B5", "#00C853", "#FF7043", "#78909C",
    "#E040FB", "#26C6DA", "#EF5350", "#FFC107", "#66BB6A",
]
_COLOR_LINEA = "#2e7d32"
_COLOR_PROMEDIO = "#9e9e9e"
# Verde institucional de Ganadería JA (el mismo de los reportes PDF), usado
# como acento de marca en títulos y notas al pie de cada gráfico.
_COLOR_MARCA = "#2F5233"
_MESES_ES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def graficos_disponibles() -> bool:
    """True si matplotlib está instalado y listo para generar imágenes."""
    return _MATPLOTLIB_OK


def _estilo_ejes(ax) -> None:
    """Aplica un estilo limpio consistente a todos los gráficos del bot."""
    ax.grid(True, alpha=0.35, linewidth=0.6)
    sns.despine(ax=ax)
    ax.spines["left"].set_color("#666666")
    ax.spines["bottom"].set_color("#666666")
    ax.set_axisbelow(True)


def _titulo_y_subtitulo(fig, ax, titulo: str, subtitulo: str = "") -> None:
    """Título de marca (verde, negrita, arriba de la figura) + subtítulo de
    contexto (gris, chico, pegado al gráfico): cuántos animales/registros
    entran, qué período se analizó y qué significa el indicador. Sin esto,
    un gráfico bien hecho pero sin contexto es fácil de leer mal."""
    fig.suptitle(titulo, fontsize=13, fontweight="bold", color=_COLOR_MARCA, y=0.98)
    if subtitulo:
        ax.set_title(subtitulo, fontsize=8.5, color="#707070", style="italic", pad=8)


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


def _guardar(fig, output_dir: str, nombre_archivo: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    ruta = os.path.join(output_dir, nombre_archivo)
    # Marca de agua sutil, igual en todos los gráficos (identidad visual
    # Ganadería JA, consistente con el reporte PDF).
    fig.text(0.99, 0.01, "Ganadería JA", ha="right", va="bottom",
              fontsize=7.5, color="#aaaaaa", style="italic")
    fig.tight_layout()
    # bbox_inches="tight" evita que títulos/leyendas largos (ej. la nota de
    # intervalos excluidos del IEP) queden cortados en el borde del canvas.
    fig.savefig(ruta, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return ruta


# --------------------------------------------------------------------- #
# Ficha de un animal
# --------------------------------------------------------------------- #
def generar_grafico_peso(db, tag, output_dir: str = "data/reportes",
                         hoy: Optional[date] = None) -> Optional[str]:
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

    if len(ys) < 2:
        return None

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=130)
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

    tag_str = animal["tag"] or str(tag)
    nombre = f" ({animal['nombre']})" if animal["nombre"] else ""
    rango = f"{fechas[0].isoformat()} a {fechas[-1].isoformat()}"
    _titulo_y_subtitulo(fig, ax, f"Curva de Crecimiento — {tag_str}{nombre}",
                        f"{len(ys)} pesajes · {rango}")
    _estilo_ejes(ax)
    ax.legend(loc="upper left", fontsize=8)

    fecha_hoy = (hoy or date.today()).isoformat()
    return _guardar(fig, output_dir, f"grafico_peso_{tag_str}_{fecha_hoy}.png")


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
                              hoy: Optional[date] = None) -> Optional[str]:
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

    controles = db.historial_leche(aid)
    ultimo_parto = db.ultimo_parto(aid)
    if ultimo_parto is None or not ultimo_parto["fecha"]:
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
        return None

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=130)
    ax.plot(xs, ys, marker="o", color=_COLOR_LINEA, linewidth=2.2, markersize=6, label="Litros/día (individual)")
    _marcar_ultimo_valor(ax, xs[-1], ys[-1], texto=f"{ys[-1]:.1f} L")

    prom = _promedio_leche_hato_por_del(db, aid)
    if prom:
        xs_prom, ys_prom = zip(*prom)
        ax.plot(xs_prom, ys_prom, color=_COLOR_PROMEDIO, linewidth=1.6, linestyle="--",
                label="Promedio del hato")

    ax.set_xlabel("Días en leche (DEL)")
    ax.set_ylabel("Litros/día")
    tag_str = animal["tag"] or str(tag)
    nombre = f" ({animal['nombre']})" if animal["nombre"] else ""
    _titulo_y_subtitulo(fig, ax, f"Curva de Lactancia — {tag_str}{nombre}",
                        f"{len(xs)} controles de leche · último: día {xs[-1]} de lactancia")
    _estilo_ejes(ax)
    ax.legend(loc="upper right", fontsize=8)

    fecha_hoy = (hoy or date.today()).isoformat()
    return _guardar(fig, output_dir, f"grafico_lactancia_{tag_str}_{fecha_hoy}.png")


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
                                     hoy: Optional[date] = None) -> Optional[str]:
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
        return None
    etiquetas, nacimientos, muertes_m, compras, ventas, niveles = datos

    x = range(len(etiquetas))
    fig, ax = plt.subplots(figsize=(9, 5), dpi=130)
    ancho = 0.2
    ax.bar([i - 1.5 * ancho for i in x], nacimientos, ancho, label="Nacimientos", color=_PALETA[2])
    ax.bar([i - 0.5 * ancho for i in x], compras, ancho, label="Compras/Entradas", color=_PALETA[0])
    ax.bar([i + 0.5 * ancho for i in x], ventas, ancho, label="Ventas/Salidas", color=_PALETA[3])
    ax.bar([i + 1.5 * ancho for i in x], muertes_m, ancho, label="Muertes", color=_PALETA[7])
    ax.set_xticks(list(x))
    ax.set_xticklabels(etiquetas, fontsize=8)
    ax.set_ylabel("Animales por mes")
    _estilo_ejes(ax)

    ax2 = ax.twinx()
    ax2.plot(list(x), niveles, color="#b71c1c", linewidth=2.2, marker="o", markersize=4,
             label="Inventario estimado")
    ax2.set_ylabel("Inventario estimado (total activos)")
    ax2.spines["top"].set_visible(False)
    ax2.grid(False)

    lineas1, etiquetas1 = ax.get_legend_handles_labels()
    lineas2, etiquetas2 = ax2.get_legend_handles_labels()
    ax.legend(lineas1 + lineas2, etiquetas1 + etiquetas2, loc="upper left", fontsize=8, ncol=2)
    _titulo_y_subtitulo(fig, ax, "Evolución del Rebaño",
                        f"{len(etiquetas)} meses · inventario final estimado: {niveles[-1]}")

    return _guardar(fig, output_dir, f"grafico_evolucion_rebano_{hoy.isoformat()}.png")


def generar_grafico_categorias(db, output_dir: str = "data/reportes",
                               hoy: Optional[date] = None) -> Optional[str]:
    """Torta de distribución del hato activo por las categorías de Software
    Ganadero (cría hembra/macho, levante, novilla vientre, vaca parida/seca,
    ceba, reproductor), sumando todos los potreros más los animales sin
    potrero asignado."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    grupos = calcular_existencias_potreros_sg(db, hoy)
    if not grupos:
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
        return None

    fig, ax = plt.subplots(figsize=(7, 6), dpi=130)
    ax.pie(
        valores, labels=None, autopct=lambda p: f"{p:.0f}%" if p >= 4 else "",
        colors=_PALETA[: len(valores)], startangle=90,
        wedgeprops={"linewidth": 1.5, "edgecolor": "white"}, textprops={"fontsize": 9},
    )
    ax.legend(etiquetas, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9)
    _titulo_y_subtitulo(fig, ax, "Distribución del Hato por Categorías",
                        f"{total_activos} animales activos al {hoy.isoformat()}")
    ax.axis("equal")

    return _guardar(fig, output_dir, f"grafico_categorias_{hoy.isoformat()}.png")


def generar_grafico_gmd_hato(db, output_dir: str = "data/reportes",
                             hoy: Optional[date] = None) -> Optional[str]:
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
        return None

    todos_gmd = ys_h + ys_m
    n_negativos = sum(1 for v in todos_gmd if v < 0)
    mediana_gmd = statistics.median(todos_gmd)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
    if xs_h:
        ax.scatter(xs_h, ys_h, color=_PALETA[0], label="Hembras", alpha=0.75, s=45)
    if xs_m:
        ax.scatter(xs_m, ys_m, color=_PALETA[3], label="Machos", alpha=0.75, s=45)
    ax.axhline(0, color="#616161", linewidth=1, linestyle=":")
    ax.axhline(mediana_gmd, color=_COLOR_MARCA, linewidth=1.2, linestyle="--", alpha=0.8,
               label=f"Mediana: {mediana_gmd:.2f} kg/día")
    ax.set_xlabel("Edad al último pesaje (días)")
    ax.set_ylabel("GMD (kg/día)")
    subtitulo = f"{len(todos_gmd)} animales con 2+ pesajes"
    if n_negativos:
        subtitulo += f" · ⚠️ {n_negativos} con GMD negativa (requieren atención)"
    _titulo_y_subtitulo(fig, ax, "Ganancia Media Diaria del Hato", subtitulo)
    _estilo_ejes(ax)
    ax.legend(loc="upper right", fontsize=9)

    return _guardar(fig, output_dir, f"grafico_gmd_hato_{hoy.isoformat()}.png")


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
                                umbral_max_dias: Optional[int] = 730) -> Optional[str]:
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
        return None

    mediana = statistics.median(ieps)

    fig, ax = plt.subplots(figsize=(6, 5.5), dpi=130)
    sns.boxplot(y=ieps, ax=ax, color=_PALETA[0], width=0.35, showfliers=False)
    sns.stripplot(y=ieps, ax=ax, color=_PALETA[7], alpha=0.6, size=5, jitter=0.12)
    ax.axhline(365, color=_PALETA[2], linewidth=1.4, linestyle="--", label="Meta: 365 días (1 parto/año)")
    ax.annotate(f"Mediana: {mediana:.0f}d", (0.18, mediana), fontsize=8.5, color=_COLOR_MARCA,
                fontweight="bold", va="center")
    ax.set_ylabel("Intervalo entre partos (días)")
    ax.set_xticks([])

    subtitulo = f"{len(ieps)} intervalo(s) · vacas con 2+ partos"
    if n_excluidos > 0:
        subtitulo += f" · {n_excluidos} excluido(s) >{umbral_max_dias}d (probable hueco de registro)"
    _titulo_y_subtitulo(fig, ax, "Intervalo Entre Partos (IEP)", subtitulo)
    _estilo_ejes(ax)
    ax.legend(loc="upper right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_iep_{hoy.isoformat()}.png")


def generar_grafico_iep_boxplot_completo(db, output_dir: str = "data/reportes",
                                         hoy: Optional[date] = None) -> Optional[str]:
    """Versión del boxplot de IEP sin filtrar outliers (histórico completo),
    para cuando se quiere auditar los huecos de registro en vez de
    esconderlos."""
    return generar_grafico_iep_boxplot(db, output_dir=output_dir, hoy=hoy, umbral_max_dias=None)


def generar_grafico_peso_destete_por_raza(db, output_dir: str = "data/reportes",
                                          hoy: Optional[date] = None) -> Optional[str]:
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
        return None

    razas = sorted(por_raza, key=lambda r: -sum(por_raza[r]) / len(por_raza[r]))
    promedios = [sum(por_raza[r]) / len(por_raza[r]) for r in razas]
    conteos = [len(por_raza[r]) for r in razas]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
    barras = ax.bar(razas, promedios, color=_PALETA[: len(razas)])
    for barra, n in zip(barras, conteos):
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height(), f" n={n}",
               ha="center", va="bottom", fontsize=8, rotation=0)
    ax.set_ylabel("Peso promedio al destete (kg)")
    ax.tick_params(axis="x", rotation=20, labelsize=9)
    _titulo_y_subtitulo(fig, ax, "Peso al Destete por Raza",
                        f"{sum(conteos)} destetes registrados · {len(razas)} raza(s)")
    _estilo_ejes(ax)

    return _guardar(fig, output_dir, f"grafico_destete_raza_{hoy.isoformat()}.png")


def generar_grafico_rendimiento_padre(db, output_dir: str = "data/reportes",
                                      hoy: Optional[date] = None) -> Optional[str]:
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
        return None

    padres = sorted(por_padre, key=lambda k: -sum(por_padre[k]) / len(por_padre[k]))
    promedios = [sum(por_padre[k]) / len(por_padre[k]) for k in padres]
    conteos = [len(por_padre[k]) for k in padres]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
    barras = ax.barh(padres, promedios, color=_PALETA[: len(padres)])
    for barra, n in zip(barras, conteos):
        ax.text(barra.get_width(), barra.get_y() + barra.get_height() / 2, f" n={n}",
               ha="left", va="center", fontsize=8)
    ax.set_xlabel("Peso promedio al nacer de sus crías (kg)")
    _titulo_y_subtitulo(fig, ax, "Rendimiento por Padre/Reproductor",
                        f"{sum(conteos)} crías con peso al nacer · {len(padres)} padre(s) con 2+ crías")
    _estilo_ejes(ax)

    return _guardar(fig, output_dir, f"grafico_rendimiento_padre_{hoy.isoformat()}.png")


def generar_grafico_aforo_potreros(db, output_dir: str = "data/reportes",
                                   hoy: Optional[date] = None) -> Optional[str]:
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
        return None

    nombres = [(p["nombre"] or p["codigo"] or "?") for p in potreros]
    valores = [float(p["aforo_kg_m2"]) for p in potreros]
    pastos = [(p["tipo_pasto"] or "Sin dato") for p in potreros]
    pastos_unicos = sorted(set(pastos))
    color_de_pasto = {p: _PALETA[i % len(_PALETA)] for i, p in enumerate(pastos_unicos)}
    colores = [color_de_pasto[p] for p in pastos]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
    ax.bar(nombres, valores, color=colores)
    ax.set_ylabel("Aforo (kg/m²)")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    _titulo_y_subtitulo(fig, ax, "Aforo de Forraje por Potrero",
                        f"{len(nombres)} potrero(s) · última medición cargada (no es serie histórica)")
    _estilo_ejes(ax)

    parches = [plt.Rectangle((0, 0), 1, 1, color=color_de_pasto[p]) for p in pastos_unicos]
    ax.legend(parches, pastos_unicos, loc="upper right", fontsize=8, title="Tipo de pasto")

    return _guardar(fig, output_dir, f"grafico_aforo_potreros_{hoy.isoformat()}.png")


def generar_grafico_ocupacion_potreros(db, output_dir: str = "data/reportes",
                                       hoy: Optional[date] = None) -> Optional[str]:
    """Barras horizontales de días de ocupación actual por potrero
    (semáforo Voisin: verde ≤3d, amarillo ≤6d, rojo >6d)."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()
    grupos = calcular_existencias_potreros_sg(db, hoy)
    if not grupos:
        return None

    nombres, dias_ocup, colores = [], [], []
    for g in grupos:
        f_ingreso = g.get("fecha_ingreso_reciente")
        d = (hoy - to_date(f_ingreso)).days if f_ingreso and to_date(f_ingreso) else None
        if d is None:
            continue
        nombres.append(g["display"])
        dias_ocup.append(d)
        colores.append("#2e7d32" if d <= 3 else ("#f9a825" if d <= 6 else "#c62828"))

    if not nombres:
        return None

    orden = sorted(range(len(nombres)), key=lambda i: -dias_ocup[i])
    nombres = [nombres[i] for i in orden]
    dias_ocup = [dias_ocup[i] for i in orden]
    colores = [colores[i] for i in orden]

    fig, ax = plt.subplots(figsize=(7, max(3.5, 0.4 * len(nombres))), dpi=130)
    ax.barh(nombres, dias_ocup, color=colores)
    ax.axvline(3, color="#616161", linewidth=1, linestyle=":", label="Meta Voisin: ≤3 días")
    ax.set_xlabel("Días de ocupación actual")
    _titulo_y_subtitulo(fig, ax, "Ocupación de Potreros (Rotación Voisin)",
                        f"{len(nombres)} potrero(s) ocupado(s) al {hoy.isoformat()}")
    _estilo_ejes(ax)
    ax.legend(loc="lower right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_ocupacion_potreros_{hoy.isoformat()}.png")


def _hembra_prenada_estimado(db, aid: int) -> bool:
    """Estimación: True si el último servicio de la hembra no tiene un
    parto registrado después de esa fecha (no hay diagnóstico de preñez
    real en el sistema -- ver nota del módulo)."""
    ult = db.ultimo_servicio(aid)
    if ult is None or not ult["fecha"]:
        return False
    parto = db.query_one(
        "SELECT id FROM partos WHERE vaca_id = ? AND fecha >= ? LIMIT 1", (aid, ult["fecha"])
    )
    return parto is None


def generar_grafico_prenadas_vacias_potrero(db, output_dir: str = "data/reportes",
                                            hoy: Optional[date] = None) -> Optional[str]:
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
        return None

    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.5 * len(nombres))), dpi=130)
    ax.barh(nombres, prenadas, color=_PALETA[2], label="Preñadas (estimado)")
    ax.barh(nombres, vacias, left=prenadas, color=_PALETA[0], label="Vacías")
    for i, tot in enumerate(totales):
        ax.text(prenadas[i] + vacias[i], i, f"  potrero: {tot} animales en total", va="center", fontsize=8)
    ax.set_xlabel("Hembras en edad reproductiva")
    _titulo_y_subtitulo(fig, ax, "Preñadas vs Vacías por Potrero",
                        f"al {hoy.isoformat()} · estimado por servicio sin parto posterior")
    _estilo_ejes(ax)
    ax.legend(loc="lower right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_prenadas_potrero_{hoy.isoformat()}.png")


def generar_grafico_waterfall_inventario(db, meses: int = 12, output_dir: str = "data/reportes",
                                         hoy: Optional[date] = None) -> Optional[str]:
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
        return None
    etiquetas, nacimientos, muertes_m, compras, ventas, niveles = datos

    deltas = [nacimientos[i] + compras[i] - muertes_m[i] - ventas[i] for i in range(len(etiquetas))]
    inicio = niveles[0] - deltas[0]
    niveles_completos = [inicio] + list(niveles)  # longitud = len(etiquetas) + 1

    categorias = ["Inicio"] + etiquetas + ["Actual"]
    n = len(categorias)

    color_inicio_fin = "#607D8B"
    color_sube = "#00C853"
    color_baja = "#EF5350"

    fig, ax = plt.subplots(figsize=(max(9, 0.9 * n), 5.5), dpi=130)

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
    _estilo_ejes(ax)

    return _guardar(fig, output_dir, f"grafico_waterfall_inventario_{hoy.isoformat()}.png")


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


def generar_grafico_dias_abiertos_km(db, output_dir: str = "data/reportes",
                                     hoy: Optional[date] = None) -> Optional[str]:
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

    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
    ax.step(tiempos, porcentajes, where="post", color=_PALETA[3], linewidth=2.3)
    ax.fill_between(tiempos, porcentajes, step="post", color=_PALETA[3], alpha=0.12)
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
    _estilo_ejes(ax)

    return _guardar(fig, output_dir, f"grafico_dias_abiertos_km_{hoy.isoformat()}.png")


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
                                     hoy: Optional[date] = None) -> Optional[str]:
    """Litros totales del hato por semana (suma de todos los controles
    registrados esa semana), para ver la tendencia de producción total de
    la finca en el tiempo."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    por_semana = _controles_leche_por_semana(db)
    if len(por_semana) < 2:
        return None

    semanas_ordenadas = sorted(por_semana.keys())[-semanas:]
    etiquetas = [s.strftime("%d-%b") for s in semanas_ordenadas]
    litros = [por_semana[s]["litros"] for s in semanas_ordenadas]

    fig, ax = plt.subplots(figsize=(9, 5), dpi=130)
    ax.bar(etiquetas, litros, color=_PALETA[0])
    ax.text(len(etiquetas) - 1, litros[-1], f" {litros[-1]:.0f} L", ha="left", va="bottom",
            fontsize=9, fontweight="bold", color=_COLOR_MARCA)
    ax.set_ylabel("Litros totales por semana")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    n_vacas_total = len({v for s in por_semana.values() for v in s["vacas"]})
    _titulo_y_subtitulo(fig, ax, "Producción Total de Leche del Hato",
                        f"{len(semanas_ordenadas)} semanas · {n_vacas_total} vaca(s) con controles")
    _estilo_ejes(ax)

    return _guardar(fig, output_dir, f"grafico_leche_total_{hoy.isoformat()}.png")


def generar_grafico_eficiencia_lechera(db, semanas: int = 12, output_dir: str = "data/reportes",
                                       hoy: Optional[date] = None) -> Optional[str]:
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
        return None

    semanas_ordenadas = sorted(por_semana.keys())[-semanas:]
    etiquetas = [s.strftime("%d-%b") for s in semanas_ordenadas]
    eficiencia = [
        por_semana[s]["litros"] / len(por_semana[s]["vacas"]) / 7
        for s in semanas_ordenadas if por_semana[s]["vacas"]
    ]
    if len(eficiencia) < 2:
        return None

    fig, ax = plt.subplots(figsize=(9, 5), dpi=130)
    ax.plot(etiquetas, eficiencia, marker="o", color=_PALETA[2], linewidth=2.2, markersize=6)
    _marcar_ultimo_valor(ax, len(etiquetas) - 1, eficiencia[-1], texto=f"{eficiencia[-1]:.1f} L/vaca/día")
    ax.set_ylabel("Litros / vaca en ordeño / día")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    _titulo_y_subtitulo(fig, ax, "Eficiencia Lechera del Hato",
                        f"{len(eficiencia)} semanas · litros totales ÷ vacas con control ÷ 7 días")
    _estilo_ejes(ax)

    return _guardar(fig, output_dir, f"grafico_eficiencia_lechera_{hoy.isoformat()}.png")


def generar_grafico_ranking_vacas_leche(db, output_dir: str = "data/reportes",
                                        hoy: Optional[date] = None) -> Optional[str]:
    """Ranking de vacas activas por promedio de litros/control, para
    identificar las mejores productoras y las candidatas a revisar/
    descartar de un vistazo. Verde = tercio superior, rojo = tercio
    inferior (candidatas a revisión), azul = medio."""
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
            colores.append("#00C853")
        elif i >= n - tercio:
            colores.append("#EF5350")
        else:
            colores.append(_PALETA[0])

    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.35 * n)), dpi=130)
    ax.barh(list(reversed(etiquetas)), list(reversed(valores)), color=list(reversed(colores)))
    _marcar_mediana_vertical(ax, valores)
    ax.set_xlabel("Promedio de litros por control")
    _titulo_y_subtitulo(fig, ax, "Ranking de Vacas por Producción de Leche",
                        f"{n} vaca(s) con controles registrados · verde = mejor tercio, rojo = revisar/descartar")
    _estilo_ejes(ax)
    ax.legend(loc="lower right", fontsize=8)

    return _guardar(fig, output_dir, f"grafico_ranking_leche_{hoy.isoformat()}.png")


# --------------------------------------------------------------------- #
# Estado reproductivo agregado del hato
# --------------------------------------------------------------------- #
def generar_grafico_estado_reproductivo_hato(db, output_dir: str = "data/reportes",
                                             hoy: Optional[date] = None) -> Optional[str]:
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
        return None
    tasa = n_prenadas / expuestas * 100
    total_hembras = expuestas + n_nunca_servidas

    categorias = ["Preñadas\n(estimado)", "Vacías\n(servidas)", "Nunca\nservidas"]
    valores = [n_prenadas, n_vacias_servidas, n_nunca_servidas]
    colores = [_PALETA[2], _PALETA[3], _PALETA[4]]

    fig, ax = plt.subplots(figsize=(7, 5.5), dpi=130)
    barras = ax.bar(categorias, valores, color=colores)
    ax.set_ylim(0, max(valores) * 1.22)
    for barra, v in zip(barras, valores):
        ax.text(barra.get_x() + barra.get_width() / 2, barra.get_height(), f" {v}",
                ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("Hembras en edad reproductiva")
    _titulo_y_subtitulo(fig, ax, "Estado Reproductivo del Hato",
                        f"{total_hembras} hembras activas ≥1 año al {hoy.isoformat()}")
    _estilo_ejes(ax)
    ax.text(0.98, 0.95, f"Tasa de preñez (sobre expuestas): {tasa:.0f}%",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            color=_COLOR_MARCA, fontweight="bold")

    return _guardar(fig, output_dir, f"grafico_estado_reproductivo_{hoy.isoformat()}.png")


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
                                         hoy: Optional[date] = None) -> Optional[str]:
    """UGG/ha por potrero, usando el último peso conocido de cada animal (o
    un estimado por categoría cuando no hay pesaje) sobre el área real de
    cada potrero. Útil para detectar sobrecarga antes de que se note en el
    pasto."""
    if not _MATPLOTLIB_OK:
        return None
    hoy = hoy or date.today()

    grupos = calcular_existencias_potreros_sg(db, hoy)
    if not grupos:
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
        return None

    orden = sorted(range(len(nombres)), key=lambda i: -cargas[i])
    nombres = [nombres[i] for i in orden]
    cargas = [cargas[i] for i in orden]
    colores = ["#EF5350" if c > 3 else ("#FFC107" if c > 2 else "#00C853") for c in cargas]

    fig, ax = plt.subplots(figsize=(8, max(3.5, 0.4 * len(nombres))), dpi=130)
    ax.barh(nombres, cargas, color=colores)
    ax.set_xlabel("Carga animal (UGG/ha, estimado)")
    _titulo_y_subtitulo(fig, ax, "Carga Animal por Potrero",
                        f"{len(nombres)} potrero(s) · UGG = peso vivo/450kg (o estimado por edad)")
    _estilo_ejes(ax)

    return _guardar(fig, output_dir, f"grafico_carga_animal_{hoy.isoformat()}.png")
