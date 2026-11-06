"""Datos a revisar: registros imposibles o sospechosos del hato ACTIVO.

La historia viene en buena parte de Software Ganadero y trae errores que
descuadran listas y fichas (ej. el parto de una madre anotado en su cría
de 7 meses, que la volvía "vaca en ordeño"). Cada revisión es una consulta;
solo se miran animales ACTIVOS (los vendidos/muertos ya no se corrigen).
La corrección se hace desde la ficha del animal (pestaña Reproducción,
Pesos, Editar...), que ya tiene esas acciones.
"""
from __future__ import annotations

from datetime import date, timedelta
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
    "gestacion_corta": ("Gestación muy corta", "media"),
    "gestacion_larga": ("Gestación muy larga", "media"),
    "celo_en_prenada": ("Celo o servicio estando preñada", "media"),
    "palpacion_no_cuadra": ("Palpación que no cuadra", "media"),
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

    # Reproducción: gestación vs. servicio, celo/servicio en preñada y
    # palpaciones con días que no cuadran (ver _revisar_repro).
    for r in db.query(cte + f"SELECT act.* FROM act WHERE NOT {_MACHO.format(a='act')}{solo}", p_solo):
        ev = _eventos_repro(db, r["id_animal"])
        if not (ev["partos"] or ev["servicios"] or ev["celos"] or ev["diags"]):
            continue
        for tipo, detalle, fecha in _revisar_repro(ev):
            agregar(tipo, r, detalle, fecha)

    orden = {"alta": 0, "media": 1, "baja": 2}
    out.sort(key=lambda x: (orden[x["gravedad"]], x["tipo"], str(x["tag"])))
    return out


# ── Reproducción ──────────────────────────────────────────────────────
# Gestación bovina ~283 días; lo normal va de ~270 a ~295. Fuera de este
# rango (con servicio registrado) casi siempre falta o sobra un registro.
GESTACION_MIN_DIAS = 260
GESTACION_MAX_DIAS = 300
# Más allá de esto no se compara: falta el servicio real (monta natural).
GESTACION_SIN_DATO_DIAS = 365
# Margen entre los días de gestación de la palpación y los del servicio.
PALPACION_MARGEN_DIAS = 30
PERDIDAS = ("ABORTO", "REABSORCION", "MOMIFICACION", "MACERACION", "MUERTE_FETAL")


def _f(valor) -> Optional[date]:
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except ValueError:
        return None


def _fc(d: date) -> str:
    """Fecha corta legible: 12/08/2026."""
    return d.strftime("%d/%m/%Y")


def _eventos_repro(db, vaca_id: int) -> dict:
    """Partos, servicios, celos y palpaciones de la vaca, con fechas date."""
    partos = [(f, (r["tipo_evento"] or "PARTO").upper()) for r in db.query(
        "SELECT fecha, tipo_evento FROM partos WHERE vaca_id = ?", (vaca_id,)) if (f := _f(r["fecha"]))]
    servicios = [f for r in db.query("SELECT fecha FROM servicios WHERE vaca_id = ?", (vaca_id,))
                 if (f := _f(r["fecha"]))]
    celos = [f for r in db.query("SELECT fecha FROM celos WHERE vaca_id = ?", (vaca_id,)) if (f := _f(r["fecha"]))]
    diags = [(f, (r["resultado"] or "").upper(), r["dias_gestacion"]) for r in db.query(
        "SELECT fecha, resultado, dias_gestacion FROM diagnosticos_gestacion WHERE vaca_id = ?", (vaca_id,))
        if (f := _f(r["fecha"]))]
    return {"partos": sorted(partos), "servicios": sorted(servicios), "celos": sorted(celos), "diags": sorted(diags)}


def _fin_gestacion_previa(ev: dict, antes_de: date) -> Optional[date]:
    """Último parto o pérdida antes de la fecha (cierra la gestación anterior)."""
    previos = [f for f, _t in ev["partos"] if f < antes_de]
    return max(previos) if previos else None


def _servicio_de(ev: dict, antes_de: date) -> Optional[date]:
    """Último servicio antes de la fecha y después del parto/pérdida anterior."""
    desde = _fin_gestacion_previa(ev, antes_de)
    cands = [s for s in ev["servicios"] if s < antes_de and (desde is None or s > desde)]
    return max(cands) if cands else None


def revisar_parto(ev: dict, fecha: date) -> list[tuple[str, str]]:
    """Gestación fuera de rango según el último servicio: [(tipo, detalle)]."""
    s = _servicio_de(ev, fecha)
    if s is None:
        return []
    d = (fecha - s).days
    if d < GESTACION_MIN_DIAS:
        return [("gestacion_corta", f"Parto el {_fc(fecha)}, solo {d} días después del servicio del {_fc(s)} "
                 f"(una gestación dura ~283). Si se perdió la cría, regístrelo como Aborto; si no, "
                 f"revise la fecha del parto o del servicio.")]
    if GESTACION_MAX_DIAS < d <= GESTACION_SIN_DATO_DIAS:
        return [("gestacion_larga", f"Parto el {_fc(fecha)}, {d} días después del servicio del {_fc(s)} "
                 f"(una gestación dura ~283). Seguramente falta un servicio más reciente o la fecha está mal.")]
    return []


def revisar_celo_servicio(ev: dict, fecha: date, legible: str) -> list[tuple[str, str]]:
    """Celo o servicio con la vaca confirmada preñada (sin parto ni pérdida
    ni palpación vacía después de la palpación positiva)."""
    positivas = [(f, dias) for f, res, dias in ev["diags"] if res == "PREÑADA" and f < fecha]
    if not positivas:
        return []
    f_diag, dias = max(positivas)
    if any(f_diag <= p < fecha for p, _t in ev["partos"]):
        return []
    if any(f_diag < f < fecha and res == "VACIA" for f, res, _d in ev["diags"]):
        return []
    concepcion = (f_diag - timedelta(days=int(dias))) if dias else (_servicio_de(ev, f_diag) or f_diag - timedelta(days=60))
    gest = (fecha - concepcion).days
    if gest > GESTACION_MAX_DIAS - 5:
        return []  # ya debió parir: falta el parto, no es este registro
    return [("celo_en_prenada", f"{legible} el {_fc(fecha)}, pero fue palpada preñada el {_fc(f_diag)} "
             f"(tendría unos {gest} días de gestación). Si abortó, registre el aborto o una palpación vacía; "
             f"si no, revise la vaca o la fecha.")]


def revisar_palpacion(ev: dict, fecha: date, resultado: str, dias: Optional[int]) -> list[tuple[str, str]]:
    """Días de preñez de la palpación contra el servicio y el último parto."""
    if (resultado or "").upper() != "PREÑADA" or not dias:
        return []
    dias = int(dias)
    if dias > GESTACION_MAX_DIAS:
        return [("palpacion_no_cuadra", f"Palpación del {_fc(fecha)} con {dias} días de preñez: "
                 f"una gestación no pasa de ~295.")]
    previo = _fin_gestacion_previa(ev, fecha)
    if previo is not None and (fecha - previo).days + 15 < dias:
        return [("palpacion_no_cuadra", f"Palpación del {_fc(fecha)} con {dias} días de preñez, pero parió o "
                 f"abortó el {_fc(previo)} (hace {(fecha - previo).days} días). No alcanza: revise los días o la fecha.")]
    s = _servicio_de(ev, fecha)
    if s is not None:
        segun = (fecha - s).days
        if abs(segun - dias) > PALPACION_MARGEN_DIAS:
            return [("palpacion_no_cuadra", f"Palpación del {_fc(fecha)} con {dias} días de preñez, pero el "
                     f"último servicio fue el {_fc(s)} ({segun} días). Falta un servicio o los días están mal.")]
    return []


def _revisar_repro(ev: dict) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for f, tipo in ev["partos"]:
        if tipo not in PERDIDAS:
            out += [(t, d, f.isoformat()) for t, d in revisar_parto(ev, f)]
    for f in ev["servicios"]:
        out += [(t, d, f.isoformat()) for t, d in revisar_celo_servicio(ev, f, "Servicio")]
    for f in ev["celos"]:
        out += [(t, d, f.isoformat()) for t, d in revisar_celo_servicio(ev, f, "Celo")]
    for f, res, dias in ev["diags"]:
        out += [(t, d, f.isoformat()) for t, d in revisar_palpacion(ev, f, res, dias)]
    return out


# ── Aviso al guardar ──────────────────────────────────────────────────
TIPOS_CON_AVISO = ("parto", "celo", "servicio", "palpacion")


def avisos_al_guardar(db, tipo: str, tag: str, fecha: Optional[str], datos: Optional[dict] = None,
                      hoy: Optional[date] = None) -> list[str]:
    """Avisos para el registro que se está por guardar (no lo guarda ni lo
    bloquea: la persona decide si lo guarda igual)."""
    tipo = (tipo or "").lower()
    datos = datos or {}
    tag = str(tag or "").strip()
    if tipo not in TIPOS_CON_AVISO or not tag:
        return []
    hoy = hoy or date.today()
    f = _f(fecha) or hoy
    avisos: list[str] = []
    # Un día de margen: el formulario puede poner la fecha en UTC y de
    # noche en Colombia ya es "mañana".
    if f > hoy + timedelta(days=1):
        avisos.append(f"La fecha ({_fc(f)}) está en el futuro.")
    aid = db.animal_id(tag)
    a = db.query_one("SELECT id_animal, sexo, estado, fecha_nacimiento FROM animales WHERE id_animal = ?",
                     (aid,)) if aid is not None else None
    if a is None:
        return avisos + [f"No hay ningún animal con el arete {tag}: se va a crear uno nuevo. ¿Está bien escrito?"]
    estado = str(a["estado"] or "").upper()
    if estado and estado != "ACTIVO":
        avisos.append(f"El animal {tag} figura como {estado.lower()}, no está en el hato activo.")
    if str(a["sexo"] or "").strip().lower().startswith("m"):
        avisos.append(f"El animal {tag} está registrado como macho.")
    nac = _f(a["fecha_nacimiento"])
    if nac and f < nac:
        avisos.append(f"La fecha es anterior al nacimiento del animal ({_fc(nac)}).")
    ev = _eventos_repro(db, a["id_animal"])
    if tipo == "parto":
        tipo_ev = str(datos.get("tipo_evento") or "PARTO").upper()
        if nac and tipo_ev not in PERDIDAS and (f - nac).days < EDAD_MIN_PARTO_DIAS:
            avisos.append(f"El animal tiene apenas {round((f - nac).days / 30.44, 1)} meses: muy joven para parir. "
                          f"¿No será el parto de la madre?")
        previos = [(p, t) for p, t in ev["partos"] if p < f and t not in PERDIDAS]
        if previos and tipo_ev not in PERDIDAS:
            p = max(previos)[0]
            if (f - p).days < DIAS_MIN_ENTRE_PARTOS:
                avisos.append(f"Ya tiene un parto el {_fc(p)}, hace solo {(f - p).days} días (su cría tendría "
                              f"{round((f - p).days / 30.44, 1)} meses).")
        if tipo_ev not in PERDIDAS:
            avisos += [d for _t, d in revisar_parto(ev, f)]
    elif tipo in ("celo", "servicio"):
        avisos += [d for _t, d in revisar_celo_servicio(ev, f, "Celo" if tipo == "celo" else "Servicio")]
    elif tipo == "palpacion":
        dias = datos.get("dias_gestacion")
        try:
            dias = int(dias) if dias not in (None, "") else None
        except (TypeError, ValueError):
            dias = None
        res = str(datos.get("resultado") or "PREÑADA").upper().replace("PRENADA", "PREÑADA")
        avisos += [d for _t, d in revisar_palpacion(ev, f, res, dias)]
    return avisos


def problemas_de_animal(db, animal_id: int, hoy: Optional[date] = None) -> list[dict[str, Any]]:
    """Los mismos problemas, solo para un animal (ficha)."""
    return revisar_datos(db, hoy, animal_id=animal_id)


def _dias(db, desde, hasta) -> float:
    r = db.query_one("SELECT julianday(?) - julianday(?) d", (hasta, desde))
    return float(r["d"] or 0)


def _meses(db, desde, hasta) -> float:
    return round(_dias(db, desde, hasta) / 30.44, 1)
