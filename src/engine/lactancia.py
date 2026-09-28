"""Estado de lactancia de cada vaca: una sola regla para toda la app.

Antes cada pantalla adivinaba por días en leche (DEL) con umbrales distintos
(ficha: >= 300 "Seca"; lista Secar: 305-600 "secar"; recibo: < 300 "en
ordeño"), así que una misma vaca salía seca en su ficha y para secar en la
lista. Como casi no se registran secados, la señal más fiable es el lote:
en la finca solo se ordeña en los potreros donde está el lote de ordeño, y
ese lote rota de potrero.

Regla (vaca ACTIVA con parto):
1. Secado registrado después del último parto -> SECA (confirmada).
2. En un potrero de ordeño -> EN_ORDENO, o PAUSADA si tiene pausa abierta.
3. Fuera de los potreros de ordeño -> SECA (estimada: "fuera del lote").
Si no se conoce ningún potrero de ordeño, se usa la regla vieja por DEL.

Potrero de ordeño = marcado a mano en la PWA (potreros.ordeno 1/0) o, si no
está marcado, su nombre dice ORDEÑO/ORDENO o hoy tiene al menos
MIN_RECIEN_PARIDAS vacas recién paridas (<= DEL_RECIEN_PARIDA días, sin
secado): donde están las recién paridas es donde está el lote de ordeño,
aunque rote.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

try:
    from ..db.database import POTRERO_ACTUAL_EXPR, ULT_TRASLADO_CTE
    from ..utils import to_date
except ImportError:  # ejecución directa
    from src.db.database import POTRERO_ACTUAL_EXPR, ULT_TRASLADO_CTE  # type: ignore
    from src.utils import to_date  # type: ignore

# Un parto con la vaca de menos de 15 meses es un error de registro (lo más
# común: el parto de la madre anotado en la cría). Se ignora y se avisa.
EDAD_MIN_PARTO_DIAS = 450
DEL_RECIEN_PARIDA = 150
MIN_RECIEN_PARIDAS = 2
DEL_FIN_LACTANCIA = 300  # solo para la regla vieja (sin potreros de ordeño conocidos)
_RE_NOMBRE_ORDENO = re.compile(r"ORDE[NÑ]O", re.IGNORECASE)
_RE_NO_AUTO = re.compile(r"PARITORIO|PREPARTO|MATERNIDAD", re.IGNORECASE)

_SQL_VACAS = f"""
    WITH {ULT_TRASLADO_CTE}
    SELECT a.id_animal, a.tag, a.fecha_nacimiento, {POTRERO_ACTUAL_EXPR} AS pid,
           (SELECT MAX(p.fecha) FROM partos p WHERE p.vaca_id = a.id_animal
              AND (p.tipo_evento IS NULL OR p.tipo_evento NOT IN ('ABORTO', 'REABSORCION'))) AS ult_parto,
           (SELECT MAX(s.fecha) FROM secados s WHERE s.animal_id = a.id_animal) AS ult_secado,
           (SELECT po.fecha_inicio FROM pausas_ordeno po WHERE po.animal_id = a.id_animal
              AND po.fecha_fin IS NULL ORDER BY po.fecha_inicio DESC, po.id DESC LIMIT 1) AS pausa_desde
    FROM animales a
    LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1
    WHERE a.estado = 'ACTIVO' AND (LOWER(a.sexo) LIKE 'h%' OR LOWER(a.sexo) LIKE 'f%')
"""


def _fecha(v) -> Optional[date]:
    try:
        return to_date(v) if v else None
    except Exception:
        return None


def parto_imposible(fecha_nacimiento, fecha_parto) -> bool:
    """True si la vaca tenía menos de EDAD_MIN_PARTO_DIAS al parir."""
    fn, fp = _fecha(fecha_nacimiento), _fecha(fecha_parto)
    return bool(fn and fp and (fp - fn).days < EDAD_MIN_PARTO_DIAS)


def _vacas(db) -> list[dict[str, Any]]:
    out = []
    for r in db.query(_SQL_VACAS):
        parto = _fecha(r["ult_parto"])
        if parto_imposible(r["fecha_nacimiento"], parto):
            parto = None
        secado = _fecha(r["ult_secado"])
        out.append({
            "id": r["id_animal"], "tag": r["tag"], "pid": r["pid"], "parto": parto,
            "secado": secado if (secado and parto and secado >= parto) else None,
            "pausa_desde": r["pausa_desde"],
        })
    return out


def potreros_ordeno(db, hoy: Optional[date] = None, vacas: Optional[list] = None) -> dict[int, dict]:
    """Todos los potreros con su estado de ordeño:
    {pid: {"nombre", "ordeno": bool, "modo": "manual"|"nombre"|"auto"|"no", "recien_paridas": n}}."""
    hoy = hoy or date.today()
    vacas = vacas if vacas is not None else _vacas(db)
    recien: dict[int, int] = {}
    for v in vacas:
        if v["pid"] is not None and v["parto"] and not v["secado"] \
                and 0 <= (hoy - v["parto"]).days <= DEL_RECIEN_PARIDA:
            recien[v["pid"]] = recien.get(v["pid"], 0) + 1
    out: dict[int, dict] = {}
    try:
        rows = db.query("SELECT id, COALESCE(nombre, codigo) nombre, ordeno FROM potreros")
    except Exception:
        rows = db.query("SELECT id, COALESCE(nombre, codigo) nombre, NULL AS ordeno FROM potreros")
    for p in rows:
        nombre = str(p["nombre"] or "")
        n = recien.get(p["id"], 0)
        if p["ordeno"] is not None:
            ordeno, modo = bool(p["ordeno"]), "manual"
        elif _RE_NOMBRE_ORDENO.search(nombre):
            ordeno, modo = True, "nombre"
        elif n >= MIN_RECIEN_PARIDAS and not _RE_NO_AUTO.search(nombre):
            ordeno, modo = True, "auto"
        else:
            ordeno, modo = False, "no"
        out[p["id"]] = {"nombre": nombre, "ordeno": ordeno, "modo": modo, "recien_paridas": n}
    return out


def estados_lactancia(db, hoy: Optional[date] = None) -> dict[int, dict]:
    """{id_animal: {"estado": EN_ORDENO|PAUSADA|SECA, "confirmado": bool,
    "del_dias", "fecha_parto", "fecha_secado", "pausa_desde", "motivo"}}
    para cada vaca ACTIVA con parto registrado."""
    hoy = hoy or date.today()
    vacas = _vacas(db)
    pots = potreros_ordeno(db, hoy, vacas)
    hay_lote = any(p["ordeno"] for p in pots.values())
    out: dict[int, dict] = {}
    for v in vacas:
        if not v["parto"]:
            continue
        del_d = max(0, (hoy - v["parto"]).days)
        e: dict[str, Any] = {"del_dias": del_d, "fecha_parto": v["parto"].isoformat(), "fecha_secado": None,
                             "pausa_desde": None, "confirmado": False}
        if v["secado"]:
            e.update(estado="SECA", confirmado=True, fecha_secado=v["secado"].isoformat(),
                     motivo=f"Secada el {v['secado'].isoformat()}")
        else:
            if hay_lote:
                p = pots.get(v["pid"])
                ordena = bool(p and p["ordeno"])
                motivo = f"En lote de ordeño ({p['nombre']})" if ordena else "Fuera del lote de ordeño"
            else:
                ordena = del_d < DEL_FIN_LACTANCIA
                motivo = f"Estimado por {del_d} días en leche"
            if ordena and v["pausa_desde"]:
                e.update(estado="PAUSADA", pausa_desde=v["pausa_desde"], motivo=motivo)
            else:
                e.update(estado="EN_ORDENO" if ordena else "SECA", motivo=motivo)
        out[v["id"]] = e
    return out


def es_seca(estados: dict[int, dict], animal_id: int, del_dias: int) -> bool:
    """¿Vaca seca? Con el estado de ``estados_lactancia`` si lo hay (vaca
    ACTIVA con parto válido); si no, la regla SG de más de 305 días."""
    e = estados.get(animal_id)
    return e["estado"] == "SECA" if e else del_dias > 305


def marcar_potrero_ordeno(db, potrero_id: int, valor: Optional[bool]) -> None:
    """True/False fija el potrero como de ordeño o no; None vuelve a automático."""
    db.execute("UPDATE potreros SET ordeno = ? WHERE id = ?",
               (None if valor is None else int(bool(valor)), int(potrero_id)))
