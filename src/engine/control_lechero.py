"""Control lechero por vaca (ordeño AM + PM, una vez al mes).

Los controles viven en ``produccion_leche`` con ``animal_id`` (las filas del
tanque tienen ``animal_id`` NULL). Qué vacas se controlan sale de la misma
regla de lactancia de toda la app (engine/lactancia.py): las que están en
ordeño o en pausa.

Resumen del último control: promedio por vaca, total contra el tanque del
mismo día, mejores vacas y tres listas para actuar:
- baja producción: menos del 60 % del promedio de su tramo de días en leche;
- caída fuerte: bajó más de 25 % frente a su control anterior (mastitis,
  cojera, celo, falta de comida...);
- sin control: en ordeño y sin control hace más de 35 días.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

try:
    from ..db.database import POTRERO_ACTUAL_EXPR, ULT_TRASLADO_CTE
    from ..utils import to_date
    from .lactancia import estados_lactancia
except ImportError:  # ejecución directa
    from src.db.database import POTRERO_ACTUAL_EXPR, ULT_TRASLADO_CTE  # type: ignore
    from src.engine.lactancia import estados_lactancia  # type: ignore
    from src.utils import to_date  # type: ignore

DIAS_SIN_CONTROL = 35
DIAS_CONTROL_VIGENTE = 60   # un control más viejo no cuenta como "último" para el resumen
UMBRAL_BAJA = 0.60
UMBRAL_CAIDA = 0.25
MIN_VACAS_TRAMO = 3         # con menos vacas en el tramo se compara contra el promedio del hato
TRAMOS_DEL = ((0, 100, "0-100 DEL"), (101, 200, "101-200 DEL"), (201, 305, "201-305 DEL"), (306, 10 ** 6, "> 305 DEL"))


def _tramo(del_dias: Optional[int]) -> Optional[str]:
    if del_dias is None:
        return None
    for a, b, nombre in TRAMOS_DEL:
        if a <= del_dias <= b:
            return nombre
    return None


def _fecha(v) -> Optional[date]:
    try:
        return to_date(v) if v else None
    except Exception:
        return None


def _controles(db) -> dict[int, list[tuple[date, float]]]:
    """{animal_id: [(fecha, litros), ...]} del más reciente al más viejo."""
    out: dict[int, list[tuple[date, float]]] = {}
    for r in db.query("SELECT animal_id, fecha, litros FROM produccion_leche "
                      "WHERE animal_id IS NOT NULL AND litros IS NOT NULL AND fecha IS NOT NULL "
                      "ORDER BY fecha DESC, id DESC"):
        f = _fecha(r["fecha"])
        if f:
            out.setdefault(r["animal_id"], []).append((f, float(r["litros"])))
    return out


def vacas_para_control(db, hoy: Optional[date] = None, estados: Optional[dict] = None) -> list[dict[str, Any]]:
    """Vacas en ordeño o en pausa (hato ACTIVO), con potrero, DEL y último control."""
    hoy = hoy or date.today()
    estados = estados if estados is not None else estados_lactancia(db, hoy)
    ids = [aid for aid, e in estados.items() if e["estado"] in ("EN_ORDENO", "PAUSADA")]
    if not ids:
        return []
    ctrl = _controles(db)
    marcas = ",".join("?" * len(ids))
    filas = db.query(f"""
        WITH {ULT_TRASLADO_CTE}
        SELECT a.id_animal, a.tag, a.nombre, pt.nombre AS potrero
        FROM animales a
        LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1
        LEFT JOIN potreros pt ON pt.id = {POTRERO_ACTUAL_EXPR}
        WHERE a.estado = 'ACTIVO' AND a.id_animal IN ({marcas})""", tuple(ids))
    out = []
    for r in filas:
        e = estados[r["id_animal"]]
        ult = (ctrl.get(r["id_animal"]) or [None])[0]
        out.append({
            "tag": r["tag"], "nombre": r["nombre"], "potrero": r["potrero"] or "Sin potrero",
            "del_dias": e["del_dias"], "pausada": e["estado"] == "PAUSADA",
            "ultimo_control": ult[0].isoformat() if ult else None,
            "ultimo_litros": ult[1] if ult else None,
            "dias_sin_control": (hoy - ult[0]).days if ult else None,
        })
    out.sort(key=lambda x: (x["potrero"], str(x["tag"])))
    return out


def sin_control(db, hoy: Optional[date] = None, estados: Optional[dict] = None,
                vacas: Optional[list] = None) -> list[dict[str, Any]]:
    """Vacas en ordeño (no pausadas) sin control o con el último hace más de 35 días."""
    vacas = vacas if vacas is not None else vacas_para_control(db, hoy, estados)
    return [{**v, "motivo": "Nunca controlada" if v["dias_sin_control"] is None
             else f"Último control hace {v['dias_sin_control']} d ({v['ultimo_litros']:g} L)"}
            for v in vacas if not v["pausada"]
            and (v["dias_sin_control"] is None or v["dias_sin_control"] > DIAS_SIN_CONTROL)]


def resumen_control(db, hoy: Optional[date] = None) -> dict[str, Any]:
    """Resumen del último control y listas para actuar (ver docstring del módulo)."""
    hoy = hoy or date.today()
    estados = estados_lactancia(db, hoy)
    vacas = vacas_para_control(db, hoy, estados)
    por_tag = {v["tag"]: v for v in vacas}
    ctrl = _controles(db)
    tags = {r["id_animal"]: r["tag"] for r in db.query("SELECT id_animal, tag FROM animales")}
    out: dict[str, Any] = {"vacas_en_ordeno": len(vacas), "ultimo": None, "top": [], "baja_produccion": [],
                           "caida": [], "sin_control": sin_control(db, hoy, estados, vacas)}

    # Último control vigente de cada vaca en ordeño (con su DEL ese día).
    ultimos = []
    for aid, lista in ctrl.items():
        tag = tags.get(aid)
        if tag not in por_tag or not lista:
            continue
        f, litros = lista[0]
        if (hoy - f).days > DIAS_CONTROL_VIGENTE:
            continue
        e = estados.get(aid) or {}
        parto = _fecha(e.get("fecha_parto"))
        del_ctrl = (f - parto).days if parto else None
        prev = next(((f2, l2) for f2, l2 in lista[1:] if 0 < (f - f2).days <= 90), None)
        ultimos.append({"tag": tag, "nombre": por_tag[tag]["nombre"], "potrero": por_tag[tag]["potrero"],
                        "fecha": f.isoformat(), "litros": litros, "del_dias": del_ctrl,
                        "tramo": _tramo(del_ctrl), "previo": prev})
    if not ultimos:
        return out

    fecha_ult = max(u["fecha"] for u in ultimos)
    del_dia = [u for u in ultimos if u["fecha"] == fecha_ult]
    total = round(sum(u["litros"] for u in del_dia), 1)
    tanque = db.query_one("SELECT SUM(litros) t FROM produccion_leche WHERE animal_id IS NULL AND fecha = ?",
                          (fecha_ult,))
    tanque_l = float(tanque["t"]) if tanque and tanque["t"] else None
    out["ultimo"] = {
        "fecha": fecha_ult, "vacas": len(del_dia), "total_litros": total,
        "promedio": round(total / len(del_dia), 1),
        "tanque_litros": tanque_l,
        "cobertura_pct": round(total * 100 / tanque_l) if tanque_l else None,
    }
    out["top"] = [{k: u[k] for k in ("tag", "nombre", "potrero", "litros", "del_dias")}
                  for u in sorted(del_dia, key=lambda x: -x["litros"])[:5]]

    # Promedios por tramo de DEL (o del hato si el tramo tiene pocas vacas).
    prom_hato = sum(u["litros"] for u in ultimos) / len(ultimos)
    por_tramo: dict[str, list[float]] = {}
    for u in ultimos:
        if u["tramo"]:
            por_tramo.setdefault(u["tramo"], []).append(u["litros"])
    for u in ultimos:
        base = por_tramo.get(u["tramo"] or "", [])
        ref = sum(base) / len(base) if len(base) >= MIN_VACAS_TRAMO else prom_hato
        fila = {k: u[k] for k in ("tag", "nombre", "potrero", "litros", "del_dias", "fecha")}
        if ref > 0 and u["litros"] < UMBRAL_BAJA * ref:
            out["baja_produccion"].append({**fila, "referencia": round(ref, 1),
                                           "motivo": f"{u['litros']:g} L vs {ref:.1f} L de promedio"
                                           + (f" ({u['tramo']})" if len(base) >= MIN_VACAS_TRAMO else " del hato")})
        if u["previo"] and u["previo"][1] > 0:
            caida = 1 - u["litros"] / u["previo"][1]
            if caida > UMBRAL_CAIDA:
                out["caida"].append({**fila, "previo_litros": u["previo"][1], "caida_pct": round(caida * 100),
                                     "motivo": f"Bajó {round(caida * 100)} %: {u['previo'][1]:g} → {u['litros']:g} L"})
    out["baja_produccion"].sort(key=lambda x: x["litros"])
    out["caida"].sort(key=lambda x: -x["caida_pct"])
    return out
