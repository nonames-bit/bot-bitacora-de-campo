"""Generación de gráficos (matplotlib) para la ficha del animal.

Opcional por diseño: si matplotlib no está instalado en el entorno, las
funciones devuelven ``None`` en vez de fallar, para que el resto del bot
(consultas de texto, registro de eventos, etc.) siga funcionando sin esta
dependencia. El llamador (telegram_bot.py) debe manejar el ``None`` mostrando
un mensaje de "gráfico no disponible" en vez de un error.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Optional

from ..utils import to_date

try:
    import matplotlib
    matplotlib.use("Agg")  # backend sin pantalla: obligatorio en servidor/VPS
    import matplotlib.pyplot as plt
    _MATPLOTLIB_OK = True
except Exception:
    _MATPLOTLIB_OK = False

_COLOR_LINEA = "#2e7d32"
_COLOR_PROMEDIO = "#9e9e9e"


def graficos_disponibles() -> bool:
    """True si matplotlib está instalado y listo para generar imágenes."""
    return _MATPLOTLIB_OK


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
    ax.plot(eje_x, ys, marker="o", color=_COLOR_LINEA, linewidth=2, label="Peso registrado")
    if usar_edad:
        ax.set_xlabel("Edad (días)")
    else:
        ax.set_xlabel("Fecha")
        fig.autofmt_xdate()
    ax.set_ylabel("Peso (kg)")

    tag_str = animal["tag"] or str(tag)
    nombre = f" ({animal['nombre']})" if animal["nombre"] else ""
    ax.set_title(f"Curva de crecimiento — {tag_str}{nombre}")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    fecha_hoy = (hoy or date.today()).isoformat()
    ruta = os.path.join(output_dir, f"grafico_peso_{tag_str}_{fecha_hoy}.png")
    fig.savefig(ruta)
    plt.close(fig)
    return ruta
