"""Datos a revisar: registros imposibles o sospechosos del hato ACTIVO.

La historia viene en buena parte de Software Ganadero y trae errores que
descuadran listas y fichas (ej. el parto de una madre anotado en su cría
de 7 meses, que la volvía "vaca en ordeño"). Cada revisión es una consulta;
solo se miran animales ACTIVOS (los vendidos/muertos ya no se corrigen).
La corrección se hace desde la ficha del animal (pestaña Reproducción,
Pesos, Editar...), que ya tiene esas acciones.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

try:
    from ..db.database import POTRERO_ACTUAL_EXPR, ULT_TRASLADO_CTE
    from .lactancia import EDAD_MIN_PARTO_DIAS
except ImportError:  # ejecución directa
    from src.db.database import POTRERO_ACTUAL_EXPR, ULT_TRASLADO_CTE  # type: ignore
    from src.engine.lactancia import EDAD_MIN_PARTO_DIAS  # type: ignore

DIAS_MIN_ENTRE_PARTOS = 240
PESO_MAX_KG = 1300
PESO_MIN_KG = 15
EDAD_MAX_ANOS = 25
_PERDIDAS = "('ABORTO', 'REABSORCION', 'MOMIFICACION', 'MACERACION', 'MUERTE_FETAL')"
_MACHO = "LOWER(COALESCE({a}.sexo, '')) LIKE 'm%'"

TIPOS = {
    "parto_en_ternera": ("Parto en animal muy joven", "alta"),
    "macho_con_partos": ("Macho con eventos de hembra", "alta"),
    "fecha_futura": ("Fecha en el futuro", "alta"),
    "evento_antes_de_nacer": ("Evento antes de nacer", "alta"),
    "partos_muy_seguidos": ("Partos muy seguidos", "media"),
    "madre_imposible": ("Madre imposible", "media"),
    "peso_absurdo": ("Peso imposible", "media"),
    "edad_absurda": ("Edad imposible", "baja"),
    "sin_sexo": ("Sin sexo registrado", "baja"),
}

# Eventos con fecha por animal: (tabla, columna del animal, nombre legible).
_EVENTOS = (
    ("partos", "vaca_id", "Parto"),
    ("servicios", "vaca_id", "Servicio"),
    ("diagnosticos_gestacion", "vaca_id", "Palpación"),
    ("pesajes", "animal_id", "Pesaje"),
    ("tratamientos", "animal_id", "Tratamiento"),
    ("secados", "animal_id", "Secado"),
    ("destetes", "animal_id", "Destete"),
)


def _activos_cte() -> str:
    return (f"WITH {ULT_TRASLADO_CTE}, act AS (SELECT a.id_animal, a.tag, a.nombre, a.sexo, "
            f"a.fecha_nacimiento, a.madre_id, pt.nombre AS potrero FROM animales a "
            f"LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1 "
            f"LEFT JOIN potreros pt ON pt.id = {POTRERO_ACTUAL_EXPR} "
            f"WHERE a.estado = 'ACTIVO') ")


def revisar_datos(db, hoy: Optional[date] = None, animal_id: Optional[int] = None) -> list[dict[str, Any]]:
    """Problemas encontrados: [{tipo, titulo, gravedad, tag, nombre, potrero, detalle, fecha}]."""
    hoy_iso = (hoy or date.today()).isoformat()
    cte = _activos_cte()
    solo = " AND act.id_animal = ?" if animal_id is not None else ""
    p_solo: tuple = (animal_id,) if animal_id is not None else ()
    out: list[dict[str, Any]] = []

    def agregar(tipo: str, r, detalle: str, fecha: Optional[str] = None) -> None:
        titulo, gravedad = TIPOS[tipo]
        out.append({"tipo": tipo, "titulo": titulo, "gravedad": gravedad, "tag": r["tag"],
                    "nombre": r["nombre"], "potrero": r["potrero"], "detalle": detalle, "fecha": fecha})

    # Parto con la vaca de < 15 meses (casi siempre el de la madre en la cría).
    for r in db.query(cte + f"""
        SELECT act.*, p.fecha, m.tag AS madre FROM act JOIN partos p ON p.vaca_id = act.id_animal
        LEFT JOIN animales m ON m.id_animal = act.madre_id
        WHERE act.fecha_nacimiento IS NOT NULL AND p.fecha IS NOT NULL
          AND julianday(p.fecha) - julianday(act.fecha_nacimiento) < ?{solo}""",
            (EDAD_MIN_PARTO_DIAS, *p_solo)):
        meses = _meses(db, r["fecha_nacimiento"], r["fecha"])
        sugerencia = f" Seguramente es el parto de la madre ({r['madre']})." if r["madre"] else ""
        agregar("parto_en_ternera", r, f"Parto el {r['fecha']} con {meses} meses de edad.{sugerencia}", r["fecha"])

    # Macho con partos, servicios o palpaciones como vaca.
    for r in db.query(cte + f"""
        SELECT act.*, (SELECT COUNT(*) FROM partos WHERE vaca_id = act.id_animal) np,
               (SELECT COUNT(*) FROM servicios WHERE vaca_id = act.id_animal) ns,
               (SELECT COUNT(*) FROM diagnosticos_gestacion WHERE vaca_id = act.id_animal) nd
        FROM act WHERE {_MACHO.format(a='act')}{solo}""", p_solo):
        if r["np"] or r["ns"] or r["nd"]:
            partes = [f"{n} {t}" for n, t in ((r["np"], "parto(s)"), (r["ns"], "servicio(s)"),
                                               (r["nd"], "palpación(es)")) if n]
            agregar("macho_con_partos", r, "Está registrado como macho pero tiene " + ", ".join(partes)
                    + ". Corrija el sexo o pase los eventos a la vaca correcta.")

    # Fechas en el futuro y eventos antes de nacer.
    for r in db.query(cte + f"SELECT act.* FROM act WHERE act.fecha_nacimiento > ?{solo}", (hoy_iso, *p_solo)):
        agregar("fecha_futura", r, f"Fecha de nacimiento en el futuro: {r['fecha_nacimiento']}.",
                r["fecha_nacimiento"])
    for tabla, col, legible in _EVENTOS:
        for r in db.query(cte + f"""
            SELECT act.*, MIN(e.fecha) fecha, COUNT(*) n FROM act JOIN {tabla} e ON e.{col} = act.id_animal
            WHERE e.fecha > ?{solo} GROUP BY act.id_animal""", (hoy_iso, *p_solo)):
            agregar("fecha_futura", r, f"{legible} con fecha en el futuro ({r['fecha']})"
                    + (f" y {r['n'] - 1} más." if r["n"] > 1 else "."), r["fecha"])
        if tabla in ("partos", "servicios", "diagnosticos_gestacion", "pesajes"):
            for r in db.query(cte + f"""
                SELECT act.*, MIN(e.fecha) fecha FROM act JOIN {tabla} e ON e.{col} = act.id_animal
                WHERE act.fecha_nacimiento IS NOT NULL AND e.fecha IS NOT NULL
                  AND e.fecha < act.fecha_nacimiento{solo} GROUP BY act.id_animal""", p_solo):
                agregar("evento_antes_de_nacer", r, f"{legible} el {r['fecha']}, antes de nacer "
                        f"({r['fecha_nacimiento']}). Revise la fecha de nacimiento o la del evento.", r["fecha"])

    # Dos partos (no gemelos, no pérdidas) con menos de 240 días entre sí.
    for r in db.query(cte + f"""
        SELECT act.*, p1.fecha f1, p2.fecha fecha FROM act
        JOIN partos p1 ON p1.vaca_id = act.id_animal
        JOIN partos p2 ON p2.vaca_id = act.id_animal AND p2.id > p1.id
        WHERE p1.fecha IS NOT NULL AND p2.fecha IS NOT NULL
          AND COALESCE(p1.tipo_evento, 'PARTO') NOT IN {_PERDIDAS}
          AND COALESCE(p2.tipo_evento, 'PARTO') NOT IN {_PERDIDAS}
          AND COALESCE(p1.grupo_parto_id, -1) != COALESCE(p2.grupo_parto_id, -2)
          AND p1.id != COALESCE(p2.grupo_parto_id, -1) AND p2.id != COALESCE(p1.grupo_parto_id, -1)
          AND p1.fecha != p2.fecha
          AND ABS(julianday(p2.fecha) - julianday(p1.fecha)) < ?{solo}""",
            (DIAS_MIN_ENTRE_PARTOS, *p_solo)):
        dias = abs(int(_dias(db, r["f1"], r["fecha"])))
        agregar("partos_muy_seguidos", r, f"Partos el {min(r['f1'], r['fecha'])} y el {max(r['f1'], r['fecha'])}: "
                f"solo {dias} días entre ambos (una gestación dura ~283). Uno sobra o tiene la fecha mal.",
                r["fecha"])

    # Madre imposible: macho, el mismo animal o demasiado joven al parirlo.
    for r in db.query(cte + f"""
        SELECT act.*, m.tag madre, m.sexo msexo, m.fecha_nacimiento mnac FROM act
        JOIN animales m ON m.id_animal = act.madre_id WHERE 1=1{solo}""", p_solo):
        if r["madre_id"] == r["id_animal"]:
            agregar("madre_imposible", r, "Está registrado como su propia madre.")
        elif str(r["msexo"] or "").strip().lower().startswith("m"):
            agregar("madre_imposible", r, f"La madre registrada ({r['madre']}) es un macho.")
        elif r["mnac"] and r["fecha_nacimiento"] and _dias(db, r["mnac"], r["fecha_nacimiento"]) < EDAD_MIN_PARTO_DIAS:
            agregar("madre_imposible", r, f"La madre registrada ({r['madre']}) tenía "
                    f"{_meses(db, r['mnac'], r['fecha_nacimiento'])} meses cuando nació este animal.")

    # Pesos imposibles.
    for r in db.query(cte + f"""
        SELECT act.*, pe.fecha, pe.peso_kg FROM act JOIN pesajes pe ON pe.animal_id = act.id_animal
        WHERE pe.peso_kg IS NOT NULL AND (pe.peso_kg > ? OR (pe.peso_kg < ? AND (act.fecha_nacimiento IS NULL
              OR julianday(pe.fecha) - julianday(act.fecha_nacimiento) > 30))){solo}""",
            (PESO_MAX_KG, PESO_MIN_KG, *p_solo)):
        agregar("peso_absurdo", r, f"Pesaje de {r['peso_kg']:g} kg el {r['fecha']}.", r["fecha"])

    # Edad imposible y sin sexo.
    for r in db.query(cte + f"""
        SELECT act.* FROM act WHERE act.fecha_nacimiento IS NOT NULL
          AND julianday(?) - julianday(act.fecha_nacimiento) > ? * 365.25{solo}""",
            (hoy_iso, EDAD_MAX_ANOS, *p_solo)):
        agregar("edad_absurda", r, f"Nació el {r['fecha_nacimiento']}: más de {EDAD_MAX_ANOS} años.")
    for r in db.query(cte + f"SELECT act.* FROM act WHERE TRIM(COALESCE(act.sexo, '')) = ''{solo}", p_solo):
        agregar("sin_sexo", r, "No tiene sexo registrado: no entra en las listas de hembras ni de machos.")

    orden = {"alta": 0, "media": 1, "baja": 2}
    out.sort(key=lambda x: (orden[x["gravedad"]], x["tipo"], str(x["tag"])))
    return out


def problemas_de_animal(db, animal_id: int, hoy: Optional[date] = None) -> list[dict[str, Any]]:
    """Los mismos problemas, solo para un animal (ficha)."""
    return revisar_datos(db, hoy, animal_id=animal_id)


def _dias(db, desde, hasta) -> float:
    r = db.query_one("SELECT julianday(?) - julianday(?) d", (hasta, desde))
    return float(r["d"] or 0)


def _meses(db, desde, hasta) -> float:
    return round(_dias(db, desde, hasta) / 30.44, 1)
