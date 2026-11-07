"""Indicadores del hato con meta y semáforo (Más → Indicadores).

Un solo lugar para los indicadores de reproducción, leche, carne, sanidad y
pasturas de una finca doble propósito del trópico bajo colombiano, cada uno
con su meta de referencia y color:

- verde: cumple la meta; ámbar: cerca; rojo: lejos; gris: sin datos o sin meta.

Todos se calculan sobre los últimos ``VENTANA_DIAS`` (12 meses) salvo donde
se dice otra cosa (lo de "hoy" es el hato presente y sigue la Regla
Fundamental de Inventario: solo ``estado = 'ACTIVO'``). La historia (partos,
servicios, pesajes) sí incluye animales ya vendidos o muertos, porque es
producción pasada.

Las metas son de referencia general para doble propósito; cada finca puede
tener las suyas. Se escriben una sola vez en ``METAS`` para cambiarlas fácil.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any, Callable, Optional

try:
    from ..db.database import SQL_PARTO_REAL, SQL_POTRERO_REAL
    from ..utils import to_date
    from .growth_engine import peso_ajustado_destete
    from .lactancia import estados_lactancia
except ImportError:  # ejecución directa
    from src.db.database import SQL_PARTO_REAL, SQL_POTRERO_REAL  # type: ignore
    from src.engine.growth_engine import peso_ajustado_destete  # type: ignore
    from src.engine.lactancia import estados_lactancia  # type: ignore
    from src.utils import to_date  # type: ignore

logger = logging.getLogger(__name__)

VENTANA_DIAS = 365
DIAS_MES = 30.44
DIAS_LITROS_RECIENTES = 15

# Metas: (tipo, verde, ámbar[, ...]).
#   "menor": verde si valor <= v, ámbar si <= a.
#   "mayor": verde si valor >= v, ámbar si >= a.
#   "rango": verde si v[0] <= valor <= v[1], ámbar si a[0] <= valor <= a[1].
METAS: dict[str, tuple] = {
    "iep": ("menor", 400, 450),
    "dias_abiertos": ("menor", 120, 150),
    "servicios_concepcion": ("menor", 2.0, 2.5),
    "tasa_concepcion": ("mayor", 50, 40),
    "concepcion_primer_servicio": ("mayor", 50, 40),
    "dias_primer_servicio": ("menor", 80, 100),
    "prenadas_150": ("mayor", 60, 45),
    "natalidad": ("mayor", 75, 65),
    "perdidas": ("menor", 5, 8),
    "edad_primer_parto": ("menor", 32, 36),
    "novillas_edad_servicio": ("menor", 26, 30),
    "novillas_peso_servicio": ("mayor", 300, 270),
    "cc_parto": ("rango", (3.0, 3.5), (2.75, 3.75)),
    "cc_servicio": ("mayor", 2.75, 2.5),
    "litros_vaca_hato": ("mayor", 4, 3),
    "litros_vaca_ordeno": ("mayor", 6, 5),
    "pct_ordeno": ("mayor", 65, 55),
    "del_promedio": ("rango", (150, 180), (120, 210)),
    "periodo_seco": ("rango", (50, 70), (40, 90)),
    "duracion_lactancia": ("rango", (240, 305), (200, 340)),
    "litros_lactancia": ("mayor", 1500, 1000),
    "dias_al_pico": ("rango", (30, 70), (20, 90)),
    "persistencia": ("mayor", 70, 55),
    "kg_destetados_vaca": ("mayor", 130, 100),
    "peso_destete_205": ("mayor", 160, 140),
    "destete_pct_madre": ("mayor", 40, 35),
    "gmd_levante": ("mayor", 450, 350),
    "gmd_ceba": ("mayor", 550, 450),
    "mortalidad_crias": ("menor", 5, 8),
    "mortalidad_levante": ("menor", 2, 3),
    "mortalidad_adultos": ("menor", 2, 3),
    "mastitis": ("menor", 25, 35),
    "cojeras": ("menor", 10, 15),
    "diarreas_crias": ("menor", 15, 25),
    "ugg_ha": ("rango", (1.5, 2.5), (1.0, 3.5)),
    "descanso_real": ("rango", (30, 45), (25, 60)),
    "ocupacion_real": ("menor", 3, 6),
}

_RE_MASTITIS = re.compile(r"MASTIT|CMT|UBRE|CUARTO", re.IGNORECASE)
_RE_COJERA = re.compile(r"COJ|PEZU|CASCO|PODO|PANADIZO|RENG", re.IGNORECASE)
_RE_DIARREA = re.compile(r"DIARR|ENTERI|SOLTURA|COLIBAC", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _f(v) -> Optional[date]:
    try:
        return to_date(v) if v else None
    except Exception:
        return None


def _prom(valores: list[float]) -> Optional[float]:
    return sum(valores) / len(valores) if valores else None


def color(clave: str, valor: Optional[float]) -> str:
    """'verde' / 'ambar' / 'rojo' según METAS; 'gris' sin dato o sin meta."""
    meta = METAS.get(clave)
    if valor is None or meta is None:
        return "gris"
    tipo, v, a = meta
    if tipo == "menor":
        return "verde" if valor <= v else ("ambar" if valor <= a else "rojo")
    if tipo == "mayor":
        return "verde" if valor >= v else ("ambar" if valor >= a else "rojo")
    return "verde" if v[0] <= valor <= v[1] else ("ambar" if a[0] <= valor <= a[1] else "rojo")


def texto_meta(clave: str, unidad: str = "") -> str:
    meta = METAS.get(clave)
    if not meta:
        return ""
    tipo, v, _a = meta
    u = ((" " if not unidad.startswith("/") else "") + unidad) if unidad else ""
    if tipo == "menor":
        return f"Meta: {_num(v)}{u} o menos"
    if tipo == "mayor":
        return f"Meta: {_num(v)}{u} o más"
    return f"Meta: {_num(v[0])} a {_num(v[1])}{u}"


def _num(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(round(v)):,}".replace(",", ".")


def _texto_valor(valor, unidad: str) -> str:
    if valor is None:
        return "Sin datos"
    if unidad.startswith("$"):
        resto = unidad[1:].replace("/año", " al año").replace("/mes", " al mes")
        return "$" + _num(valor) + resto
    return _num(valor) + (((" " if not unidad.startswith("/") else "") + unidad) if unidad else "")


def _item(clave: str, nombre: str, valor: Optional[float], unidad: str, n: int,
          ayuda: str, decimales: int = 0, con_meta: bool = True) -> dict:
    if valor is not None:
        valor = round(float(valor), decimales) if decimales else int(round(float(valor)))
    return {
        "k": clave, "nombre": nombre, "valor": valor, "unidad": unidad,
        "texto": _texto_valor(valor, unidad),
        "meta": texto_meta(clave, unidad) if con_meta else "",
        "color": color(clave, valor) if con_meta else "gris",
        "n": n, "ayuda": ayuda,
    }


def _seguro(nombre: str, fn: Callable[[], Any], errores: dict, defecto: Any) -> Any:
    try:
        return fn()
    except Exception as e:  # una sección rota no tumba la pantalla
        logger.error("indicadores: seccion %s fallo", nombre, exc_info=True)
        errores[nombre] = str(e)
        return defecto


# --------------------------------------------------------------------------- #
# Base común
# --------------------------------------------------------------------------- #
class _Base:
    """Datos que comparten varias secciones, leídos una sola vez."""

    def __init__(self, db, hoy: date):
        self.db = db
        self.hoy = hoy
        self.desde = hoy - timedelta(days=VENTANA_DIAS)
        self.desde_iso = self.desde.isoformat()
        self.hoy_iso = hoy.isoformat()
        self.animales = {r["id_animal"]: dict(r) for r in db.query(
            "SELECT id_animal, tag, nombre, sexo, fecha_nacimiento, estado FROM animales")}
        self.partos: dict[int, list[date]] = {}
        for r in db.query(
            "SELECT vaca_id, fecha FROM partos WHERE vaca_id IS NOT NULL AND fecha IS NOT NULL "
            f"AND (id_cria IS NULL OR id_cria != vaca_id) AND {SQL_PARTO_REAL} ORDER BY fecha"
        ):
            d = _f(r["fecha"])
            if d and d not in self.partos.setdefault(r["vaca_id"], []):
                self.partos[r["vaca_id"]].append(d)
        self.servicios: dict[int, list[dict]] = {}
        for s in db.resultados_servicios():
            self.servicios.setdefault(s["vaca_id"], []).append(s)
        self.diags: dict[int, list[tuple[date, bool]]] = {}
        for r in db.query("SELECT vaca_id, fecha, resultado FROM diagnosticos_gestacion "
                          "WHERE vaca_id IS NOT NULL AND fecha IS NOT NULL ORDER BY fecha, id"):
            d = _f(r["fecha"])
            if d:
                res = str(r["resultado"] or "").upper()
                self.diags.setdefault(r["vaca_id"], []).append(
                    (d, "PREÑADA" in res or "PRENADA" in res or "POSITIV" in res or "CONFIRMADA" in res))
        self._estados: Optional[dict] = None

    def es_hembra(self, aid) -> bool:
        s = str((self.animales.get(aid) or {}).get("sexo") or "").strip().lower()
        return s.startswith("h") or s.startswith("f")

    def activo(self, aid) -> bool:
        return (self.animales.get(aid) or {}).get("estado") == "ACTIVO"

    def nacimiento(self, aid) -> Optional[date]:
        return _f((self.animales.get(aid) or {}).get("fecha_nacimiento"))

    def tag(self, aid) -> str:
        return str((self.animales.get(aid) or {}).get("tag") or aid)

    @property
    def estados(self) -> dict:
        if self._estados is None:
            self._estados = estados_lactancia(self.db, self.hoy)
        return self._estados

    def ultimo_parto(self, aid, antes: Optional[date] = None) -> Optional[date]:
        lim = antes or self.hoy
        previos = [p for p in self.partos.get(aid, []) if p <= lim]
        return max(previos) if previos else None

    def prenada_hoy(self, aid) -> bool:
        """Preñada vigente: lo último que se sabe después del último parto."""
        up = self.ultimo_parto(aid)
        servs = [s for s in self.servicios.get(aid, []) if not up or s["fecha_d"] > up]
        diags = [d for d in self.diags.get(aid, []) if not up or d[0] > up]
        ult_serv = servs[-1] if servs else None
        ult_diag = diags[-1] if diags else None
        if ult_diag and (not ult_serv or ult_diag[0] >= ult_serv["fecha_d"]):
            return ult_diag[1]
        return bool(ult_serv and ult_serv["resultado"] == "PRENADA")

    def vacas_activas(self) -> list[int]:
        """Hembras ACTIVAS con al menos un parto real."""
        return [aid for aid in self.partos if self.activo(aid) and self.es_hembra(aid)]

    def vientres_inicio_ventana(self) -> list[int]:
        """Hembras ACTIVAS que al empezar la ventana ya habían parido o tenían
        24 meses o más: las que podían parir en estos 12 meses."""
        out = []
        for aid, a in self.animales.items():
            if a.get("estado") != "ACTIVO" or not self.es_hembra(aid):
                continue
            ya_pario = any(p < self.desde for p in self.partos.get(aid, []))
            fn = self.nacimiento(aid)
            edad_ok = bool(fn and (self.desde - fn).days >= 730)
            if ya_pario or edad_ok:
                out.append(aid)
        return out


# --------------------------------------------------------------------------- #
# Reproducción
# --------------------------------------------------------------------------- #
def _reproduccion(b: _Base) -> tuple[list[dict], list[dict]]:
    db = b.db
    items: list[dict] = []

    # IEP: intervalos cuyo segundo parto cayó en la ventana.
    ieps = []
    for fechas in b.partos.values():
        for i in range(1, len(fechas)):
            # Menos de 300 días es imposible (gestación de 283): error de registro.
            if fechas[i] >= b.desde and 300 <= (fechas[i] - fechas[i - 1]).days <= 730:
                ieps.append((fechas[i] - fechas[i - 1]).days)
    items.append(_item("iep", "Intervalo entre partos", _prom(ieps), "días", len(ieps),
                       "Días entre un parto y el siguiente de la misma vaca (partos de los últimos 12 meses; los abortos no cuentan)."))

    da = db.dias_abiertos_concepcion(desde=b.desde_iso)
    items.append(_item("dias_abiertos", "Días abiertos", da["dias_abiertos_promedio"] if da else None, "días",
                       da["n"] if da else 0, "Del parto al servicio que la dejó preñada (preñeces de los últimos 12 meses)."))

    k = db.kpis_reproductivos_concepcion(desde=b.desde_iso)
    items.append(_item("servicios_concepcion", "Servicios por preñez", k["servicios_por_concepcion"], "", k["total_evaluados"],
                       "Cuántos servicios (IA o monta) se necesitan para una preñez. Doble IA en el mismo celo cuenta como uno.", 2))
    items.append(_item("tasa_concepcion", "Tasa de concepción", k["tasa_concepcion"] if k["total_evaluados"] else None, "%",
                       k["total_evaluados"], "De cada 100 servicios con resultado, cuántos preñaron.", 1))

    # Primer servicio después del parto.
    primeros_res, dias_ps = [], []
    for aid, servs in b.servicios.items():
        partos = b.partos.get(aid, [])
        for p in partos:
            post = [s for s in servs if s["fecha_d"] > p and not any(p < p2 < s["fecha_d"] for p2 in partos)]
            if not post:
                continue
            s1 = post[0]
            if s1["fecha_d"] < b.desde:
                continue
            dias_ps.append((s1["fecha_d"] - p).days)
            if s1["resultado"] in ("PRENADA", "VACIA"):
                primeros_res.append(s1["resultado"] == "PRENADA")
    items.append(_item("concepcion_primer_servicio", "Preñez al primer servicio",
                       (sum(primeros_res) * 100 / len(primeros_res)) if primeros_res else None, "%", len(primeros_res),
                       "De las vacas servidas por primera vez después de parir, cuántas quedaron preñadas con ese servicio.", 1))
    items.append(_item("dias_primer_servicio", "Días a primer servicio", _prom(dias_ps), "días", len(dias_ps),
                       "Días entre el parto y el primer servicio (meta: 60 a 80)."))

    # % preñadas antes de 150 días: partos entre hace 515 y 150 días (ya pasaron sus 150).
    ini = b.hoy - timedelta(days=VENTANA_DIAS + 150)
    fin = b.hoy - timedelta(days=150)
    casos, ok = 0, 0
    for aid, partos in b.partos.items():
        for p in partos:
            if not (ini <= p <= fin):
                continue
            casos += 1
            if any(s["resultado"] == "PRENADA" and 0 < (s["fecha_d"] - p).days <= 150 for s in b.servicios.get(aid, [])):
                ok += 1
    items.append(_item("prenadas_150", "Preñadas antes de 150 días de paridas", (ok * 100 / casos) if casos else None, "%",
                       casos, "De las vacas que parieron hace entre 5 y 17 meses, cuántas quedaron preñadas antes de cumplir 150 días de paridas.", 1))

    vientres = b.vientres_inicio_ventana()
    paridas = [aid for aid in vientres if any(b.desde <= p <= b.hoy for p in b.partos.get(aid, []))]
    items.append(_item("natalidad", "Natalidad", (len(paridas) * 100 / len(vientres)) if vientres else None, "%",
                       len(vientres), "De las vacas y novillas de 2 años o más que hay en el hato, cuántas parieron en los últimos 12 meses.", 1))

    perd = db.query_one(
        "SELECT SUM(CASE WHEN " + SQL_PARTO_REAL + " THEN 0 ELSE 1 END) AS perdidas, COUNT(*) AS total "
        "FROM (SELECT DISTINCT vaca_id, fecha, tipo_evento FROM partos WHERE vaca_id IS NOT NULL AND fecha >= ? AND fecha <= ?)",
        (b.desde_iso, b.hoy_iso))
    tot = int(perd["total"] or 0) if perd else 0
    items.append(_item("perdidas", "Abortos y pérdidas", (int(perd["perdidas"] or 0) * 100 / tot) if tot else None, "%", tot,
                       "Abortos, reabsorciones y muertes del feto sobre el total de partos y pérdidas del año.", 1))

    # Edad al primer parto: hembras nacidas con fecha y primer parto en la ventana,
    # sin compra registrada (una vaca comprada parida no tuvo aquí su primer parto).
    compradas = {r["animal_id"] for r in db.query(
        "SELECT DISTINCT animal_id FROM movimientos WHERE UPPER(tipo_movimiento) = 'COMPRA' AND animal_id IS NOT NULL")}
    edades = []
    for aid, partos in b.partos.items():
        fn = b.nacimiento(aid)
        if not fn or aid in compradas or not partos:
            continue
        if b.desde <= partos[0] <= b.hoy:
            dias = (partos[0] - fn).days
            # Más de 5 años al "primer" parto casi siempre es historia sin
            # anotar (partos anteriores no registrados), no un primer parto.
            if 450 <= dias <= 1826:
                edades.append(dias / DIAS_MES)
    items.append(_item("edad_primer_parto", "Edad al primer parto", _prom(edades), "meses", len(edades),
                       "Edad de las novillas que parieron por primera vez en los últimos 12 meses.", 1))

    # Novillas: edad y peso al primer servicio de la vida (en la ventana).
    ed_serv, peso_serv = [], []
    pesajes: dict[int, list[tuple[date, float]]] = {}
    for r in db.query("SELECT animal_id, fecha, peso_kg FROM pesajes WHERE peso_kg IS NOT NULL AND fecha IS NOT NULL"):
        d = _f(r["fecha"])
        if d:
            pesajes.setdefault(r["animal_id"], []).append((d, float(r["peso_kg"])))
    for aid, servs in b.servicios.items():
        s1 = servs[0]
        if s1["fecha_d"] < b.desde or any(p < s1["fecha_d"] for p in b.partos.get(aid, [])):
            continue
        fn = b.nacimiento(aid)
        if fn and 300 <= (s1["fecha_d"] - fn).days <= 2500:
            ed_serv.append((s1["fecha_d"] - fn).days / DIAS_MES)
        cerca = [w for d, w in pesajes.get(aid, []) if abs((s1["fecha_d"] - d).days) <= 60]
        if cerca:
            peso_serv.append(cerca[-1])
    items.append(_item("novillas_edad_servicio", "Novillas: edad al primer servicio", _prom(ed_serv), "meses", len(ed_serv),
                       "Edad de las novillas cuando se sirvieron por primera vez.", 1))
    items.append(_item("novillas_peso_servicio", "Novillas: peso al primer servicio", _prom(peso_serv), "kg", len(peso_serv),
                       "Peso de la novilla (pesaje de 2 meses antes o después) en su primer servicio."))

    # Condición corporal cerca del parto y del servicio.
    cc: dict[int, list[tuple[date, float]]] = {}
    for r in db.query("SELECT animal_id, fecha, valor FROM condicion_corporal WHERE valor IS NOT NULL AND fecha IS NOT NULL"):
        d = _f(r["fecha"])
        if d:
            cc.setdefault(r["animal_id"], []).append((d, float(r["valor"])))

    def _cc_cerca(aid, ref: date) -> Optional[float]:
        cand = sorted(((abs((ref - d).days), v) for d, v in cc.get(aid, []) if abs((ref - d).days) <= 30))
        return cand[0][1] if cand else None

    cc_parto = [v for aid, ps in b.partos.items() for p in ps if p >= b.desde
                for v in [_cc_cerca(aid, p)] if v is not None]
    cc_serv = [v for aid, ss in b.servicios.items() for s in ss if s["fecha_d"] >= b.desde
               for v in [_cc_cerca(aid, s["fecha_d"])] if v is not None]
    items.append(_item("cc_parto", "Condición corporal al parto", _prom(cc_parto), "", len(cc_parto),
                       "Condición corporal (escala 1 a 5) anotada un mes antes o después del parto.", 2))
    items.append(_item("cc_servicio", "Condición corporal al servicio", _prom(cc_serv), "", len(cc_serv),
                       "Condición corporal (escala 1 a 5) anotada un mes antes o después del servicio.", 2))

    # Vacas problema (hoy).
    problema = []
    for aid in b.vacas_activas():
        up = b.ultimo_parto(aid)
        if not up or b.prenada_hoy(aid):
            continue
        dias = (b.hoy - up).days
        n_serv = len([s for s in b.servicios.get(aid, []) if s["fecha_d"] > up])
        motivos = []
        if dias > 150:
            motivos.append(f"{dias} días de parida y vacía")
        if n_serv >= 3:
            motivos.append(f"{n_serv} servicios sin quedar preñada")
        if motivos:
            problema.append({"tag": b.tag(aid), "nombre": (b.animales.get(aid) or {}).get("nombre"),
                             "dias_parida": dias, "servicios": n_serv, "motivo": " · ".join(motivos)})
    problema.sort(key=lambda x: (-x["servicios"], -x["dias_parida"]))
    return items, problema


# --------------------------------------------------------------------------- #
# Leche
# --------------------------------------------------------------------------- #
def _lactancias_con_control(b: _Base) -> list[dict]:
    """Cada lactancia con 3 o más controles individuales: pico, días al pico,
    persistencia y litros estimados (método de intervalos entre controles,
    hasta el secado o 305 días)."""
    ctrl: dict[int, list[tuple[date, float]]] = {}
    for r in b.db.query("SELECT animal_id, fecha, SUM(litros) AS litros FROM produccion_leche "
                        "WHERE animal_id IS NOT NULL AND litros IS NOT NULL AND litros > 0 GROUP BY animal_id, fecha"):
        d = _f(r["fecha"])
        if d:
            ctrl.setdefault(r["animal_id"], []).append((d, float(r["litros"])))
    secados: dict[int, list[date]] = {}
    for r in b.db.query("SELECT animal_id, fecha FROM secados WHERE fecha IS NOT NULL"):
        d = _f(r["fecha"])
        if d:
            secados.setdefault(r["animal_id"], []).append(d)
    out = []
    for aid, lista in ctrl.items():
        partos = b.partos.get(aid, [])
        por_parto: dict[date, list[tuple[int, float]]] = {}
        for d, lt in lista:
            p = max((x for x in partos if x <= d), default=None)
            if p and 0 <= (d - p).days <= 600:
                por_parto.setdefault(p, []).append(((d - p).days, lt))
        for p, cs in por_parto.items():
            cs.sort()
            if len(cs) < 3 or (cs[-1][0] + p.toordinal()) < b.desde.toordinal():
                continue
            sig_parto = min((x for x in partos if x > p), default=None)
            sec = min((s for s in secados.get(aid, []) if s > p and (not sig_parto or s < sig_parto)), default=None)
            fin = min(305, (sec - p).days if sec else cs[-1][0] + 15)
            # Litros: primer control constante desde el parto, luego trapecios.
            total = 0.0
            prev_d, prev_l = 0, cs[0][1]
            for dd, lt in cs:
                if dd > fin:
                    break
                total += (dd - prev_d) * (prev_l + lt) / 2
                prev_d, prev_l = dd, lt
            total += max(0, fin - prev_d) * prev_l
            tempranos = [(lt, dd) for dd, lt in cs if dd <= 150]
            pico_l, pico_d = max(tempranos) if tempranos else (None, None)
            tardios = [lt for dd, lt in cs if 150 <= dd <= 210]
            out.append({
                "vaca": b.tag(aid), "parto": p.isoformat(), "controles": len(cs),
                "litros": round(total), "cerrada": bool(sec) or (b.hoy - p).days > 305,
                "pico_litros": pico_l, "dias_al_pico": pico_d,
                "persistencia": round(tardios[0] * 100 / pico_l, 1) if (tardios and pico_l) else None,
            })
    return out


def _leche(b: _Base) -> tuple[list[dict], list[dict], dict]:
    db = b.db
    items: list[dict] = []
    estados = b.estados
    total_paridas = len(estados)
    en_ordeno = [aid for aid, e in estados.items() if e.get("estado") in ("EN_ORDENO", "PAUSADA")]
    ordenandose = [aid for aid, e in estados.items() if e.get("estado") == "EN_ORDENO"]

    serie = db.query("SELECT fecha, SUM(litros) AS litros FROM produccion_leche WHERE animal_id IS NULL "
                     "AND litros > 0 AND fecha IS NOT NULL GROUP BY fecha ORDER BY fecha DESC LIMIT ?",
                     (DIAS_LITROS_RECIENTES,))
    ult = _f(serie[0]["fecha"]) if serie else None
    recientes = [float(r["litros"]) for r in serie
                 if ult and (ult - _f(r["fecha"])).days < DIAS_LITROS_RECIENTES] if serie else []
    prom = _prom(recientes)
    items.append(_item("litros_vaca_hato", "Litros por vaca del hato", (prom / total_paridas) if (prom and total_paridas) else None,
                       "L/día", total_paridas, "Litros del tanque (últimos 15 días registrados) entre todas las vacas paridas, también las secas.", 1))
    items.append(_item("litros_vaca_ordeno", "Litros por vaca en ordeño", (prom / len(ordenandose)) if (prom and ordenandose) else None,
                       "L/día", len(ordenandose), "Litros del tanque (últimos 15 días registrados) entre las vacas que se están ordeñando.", 1))
    items.append(_item("pct_ordeno", "Vacas en ordeño", (len(en_ordeno) * 100 / total_paridas) if total_paridas else None, "%",
                       total_paridas, "De todas las vacas paridas del hato, cuántas están en ordeño hoy.", 1))
    dels = [e["del_dias"] for aid, e in estados.items() if aid in en_ordeno and e.get("del_dias") is not None]
    items.append(_item("del_promedio", "Días en leche promedio", _prom(dels), "días", len(dels),
                       "Días desde el parto de las vacas que se ordeñan hoy."))

    secos, durac = [], []
    for r in db.query("SELECT animal_id, fecha FROM secados WHERE fecha IS NOT NULL"):
        s = _f(r["fecha"])
        if not s:
            continue
        partos = b.partos.get(r["animal_id"], [])
        prev = max((p for p in partos if p < s), default=None)
        sig = min((p for p in partos if p > s), default=None)
        if prev and s >= b.desde and 30 <= (s - prev).days <= 700:
            durac.append((s - prev).days)
        if sig and sig >= b.desde and 0 < (sig - s).days <= 200:
            secos.append((sig - s).days)
    items.append(_item("periodo_seco", "Período seco", _prom(secos), "días", len(secos),
                       "Días que pasó seca la vaca antes de parir (secados anotados)."))
    items.append(_item("duracion_lactancia", "Duración de la lactancia", _prom(durac), "días", len(durac),
                       "Días del parto al secado, de las vacas secadas en los últimos 12 meses."))

    lac = _lactancias_con_control(b)
    cerradas = [x["litros"] for x in lac if x["cerrada"]]
    items.append(_item("litros_lactancia", "Litros por lactancia (hasta 305 días)", _prom(cerradas), "L", len(cerradas),
                       "Estimado con el control lechero mensual de cada vaca (3 o más controles por lactancia)."))
    picos = [x for x in lac if x["pico_litros"] is not None]
    items.append(_item("pico_litros", "Pico de lactancia", _prom([x["pico_litros"] for x in picos]), "L/día", len(picos),
                       "El control más alto de los primeros 150 días de cada lactancia.", 1, con_meta=False))
    items.append(_item("dias_al_pico", "Días al pico", _prom([x["dias_al_pico"] for x in picos]), "días", len(picos),
                       "A los cuántos días de parida dio su mejor control."))
    pers = [x["persistencia"] for x in lac if x["persistencia"] is not None]
    items.append(_item("persistencia", "Persistencia", _prom(pers), "%", len(pers),
                       "Leche entre los días 150 y 210 comparada con el pico: qué tanto se sostiene.", 1))

    largas = []
    for aid in en_ordeno:
        e = estados[aid]
        if (e.get("del_dias") or 0) > 305 and not b.prenada_hoy(aid):
            largas.append({"tag": b.tag(aid), "nombre": (b.animales.get(aid) or {}).get("nombre"),
                           "del_dias": e["del_dias"], "motivo": f"{e['del_dias']} días en leche y vacía"})
    largas.sort(key=lambda x: -x["del_dias"])
    extra = {"promedio_tanque": prom, "en_ordeno": len(en_ordeno), "total_paridas": total_paridas}
    return items, largas, extra


# --------------------------------------------------------------------------- #
# Carne y crías
# --------------------------------------------------------------------------- #
def _carne(b: _Base) -> list[dict]:
    db = b.db
    items: list[dict] = []
    filas = db.query(
        "SELECT d.animal_id, d.madre_id, d.fecha, d.peso_kg, d.peso_madre_kg, c.fecha_nacimiento, "
        "(SELECT p.peso_nacimiento FROM partos p WHERE p.id_cria = d.animal_id ORDER BY p.fecha DESC LIMIT 1) AS pn "
        "FROM destetes d LEFT JOIN animales c ON c.id_animal = d.animal_id "
        "WHERE d.fecha >= ? AND d.fecha <= ? AND d.peso_kg IS NOT NULL AND d.peso_kg > 0",
        (b.desde_iso, b.hoy_iso))
    kg = sum(float(r["peso_kg"]) for r in filas)
    vientres = b.vientres_inicio_ventana()
    items.append(_item("kg_destetados_vaca", "Kilos destetados por vaca", (kg / len(vientres)) if vientres else None, "kg",
                       len(vientres), "Kilos de todos los terneros destetados en el año, divididos entre las vacas del hato. Junta qué tan seguido pare la vaca y cuánto pesa su cría."))
    ajust = []
    pct_madre = []
    for r in filas:
        fd, fn = _f(r["fecha"]), _f(r["fecha_nacimiento"])
        if fd and fn and r["pn"] and 120 <= (fd - fn).days <= 400:
            ajust.append(peso_ajustado_destete(float(r["peso_kg"]), float(r["pn"]), (fd - fn).days))
        pm = r["peso_madre_kg"]
        if not pm and r["madre_id"]:
            q = db.query_one("SELECT peso_kg FROM pesajes WHERE animal_id = ? AND peso_kg > 0 "
                             "AND ABS(julianday(fecha) - julianday(?)) <= 60 ORDER BY ABS(julianday(fecha) - julianday(?)) LIMIT 1",
                             (r["madre_id"], r["fecha"], r["fecha"]))
            pm = q["peso_kg"] if q else None
        if pm and float(pm) > 0:
            pct_madre.append(float(r["peso_kg"]) * 100 / float(pm))
    items.append(_item("peso_destete_205", "Peso al destete (ajustado a 205 días)", _prom(ajust), "kg", len(ajust),
                       "Peso del ternero al destete llevado a 205 días de edad, para comparar terneros destetados a distinta edad."))
    items.append(_item("destete_pct_madre", "Peso del destete frente al de la madre", _prom(pct_madre), "%", len(pct_madre),
                       "Peso del ternero al destete como parte del peso de la madre.", 1))

    # Ganancia diaria por categoría (pesajes consecutivos en la ventana).
    acum = {"levante": [0.0, 0], "ceba": [0.0, 0]}
    n_anim = {"levante": set(), "ceba": set()}
    pes: dict[int, list[tuple[date, float]]] = {}
    for r in db.query("SELECT animal_id, fecha, peso_kg FROM pesajes WHERE peso_kg > 0 AND fecha >= ? AND fecha <= ? ORDER BY fecha",
                      (b.desde_iso, b.hoy_iso)):
        d = _f(r["fecha"])
        if d:
            pes.setdefault(r["animal_id"], []).append((d, float(r["peso_kg"])))
    for aid, lista in pes.items():
        fn = b.nacimiento(aid)
        if not fn:
            continue
        macho = str((b.animales.get(aid) or {}).get("sexo") or "").lower().startswith("m")
        for (d1, w1), (d2, w2) in zip(lista, lista[1:], strict=False):
            dt = (d2 - d1).days
            if dt < 20 or dt > 200:
                continue
            edad = ((d1 - fn).days + (d2 - fn).days) / 2
            cat = "levante" if 240 <= edad <= 540 else ("ceba" if (edad > 540 and macho) else None)
            if cat:
                acum[cat][0] += (w2 - w1)
                acum[cat][1] += dt
                n_anim[cat].add(aid)
    for cat, nombre, ayuda in (
        ("levante", "Ganancia diaria en levante", "Gramos por día ganados entre pesajes, de animales de 8 a 18 meses."),
        ("ceba", "Ganancia diaria en ceba", "Gramos por día ganados entre pesajes, de machos de más de 18 meses."),
    ):
        kg_c, dias_c = acum[cat]
        items.append(_item("gmd_" + cat, nombre, (kg_c * 1000 / dias_c) if dias_c else None, "g/día", len(n_anim[cat]), ayuda))

    # Mortalidad por edad.
    muertes = db.query("SELECT m.animal_id, m.fecha, a.fecha_nacimiento FROM muertes m "
                       "LEFT JOIN animales a ON a.id_animal = m.animal_id WHERE m.fecha >= ? AND m.fecha <= ?",
                       (b.desde_iso, b.hoy_iso))
    cuenta = {"crias": 0, "levante": 0, "adultos": 0}
    for r in muertes:
        fm, fn = _f(r["fecha"]), _f(r["fecha_nacimiento"])
        edad = (fm - fn).days if (fm and fn) else None
        if edad is not None and edad < 365:
            cuenta["crias"] += 1
        elif edad is not None and edad < 730:
            cuenta["levante"] += 1
        else:
            cuenta["adultos"] += 1
    nac = db.query_one(
        "SELECT COUNT(*) AS n, SUM(CASE WHEN UPPER(COALESCE(estado_cria, '')) = 'MUERTO' THEN 1 ELSE 0 END) AS muertos "
        f"FROM partos WHERE fecha >= ? AND fecha <= ? AND {SQL_PARTO_REAL}", (b.desde_iso, b.hoy_iso))
    nacidos = int(nac["n"] or 0) if nac else 0
    nacidos_muertos = int(nac["muertos"] or 0) if nac else 0
    items.append(_item("mortalidad_crias", "Mortalidad de crías", ((cuenta["crias"] + nacidos_muertos) * 100 / nacidos) if nacidos else None,
                       "%", nacidos, "Crías que murieron antes del año (más las nacidas muertas) sobre las nacidas en el año.", 1))
    poblacion = {"levante": 0, "adultos": 0}
    for aid, a in b.animales.items():
        if a.get("estado") != "ACTIVO":
            continue
        fn = b.nacimiento(aid)
        edad = (b.hoy - fn).days if fn else None
        if edad is not None and 365 <= edad < 730:
            poblacion["levante"] += 1
        elif edad is None or edad >= 730:
            poblacion["adultos"] += 1
    for cat, nombre in (("levante", "Mortalidad de levante (1 a 2 años)"), ("adultos", "Mortalidad de adultos")):
        base = poblacion[cat] + cuenta[cat]
        items.append(_item("mortalidad_" + cat, nombre, (cuenta[cat] * 100 / base) if base else None, "%", base,
                           "Muertos en el año sobre los animales de esa edad (los de hoy más los muertos).", 1))
    return items


# --------------------------------------------------------------------------- #
# Sanidad y costos
# --------------------------------------------------------------------------- #
def _sanidad(b: _Base, litros_vaca_ordeno: Optional[float], n_vacas_ordeno: int) -> list[dict]:
    db = b.db
    items: list[dict] = []
    trat = db.query("SELECT animal_id, fecha, diagnostico, producto, fecha_fin_retiro_leche FROM tratamientos "
                    "WHERE fecha >= ? AND fecha <= ?", (b.desde_iso, b.hoy_iso))
    episodios: dict[str, set] = {"mastitis": set(), "cojeras": set(), "diarreas_crias": set()}
    for r in trat:
        txt = f"{r['diagnostico'] or ''} {r['producto'] or ''}"
        d = _f(r["fecha"])
        if not d:
            continue
        clave = (r["animal_id"], d.year, d.month)  # un caso por animal y mes
        if _RE_MASTITIS.search(txt):
            episodios["mastitis"].add(clave)
        if _RE_COJERA.search(txt):
            episodios["cojeras"].add(clave)
        if _RE_DIARREA.search(txt):
            fn = b.nacimiento(r["animal_id"])
            if fn and (d - fn).days < 365:
                episodios["diarreas_crias"].add(clave)
    vacas = len(b.vientres_inicio_ventana()) or len(b.vacas_activas())
    nac = b.db.query_one(f"SELECT COUNT(*) AS n FROM partos WHERE fecha >= ? AND fecha <= ? AND {SQL_PARTO_REAL}",
                         (b.desde_iso, b.hoy_iso))
    nacidos = int(nac["n"] or 0) if nac else 0
    items.append(_item("mastitis", "Casos de mastitis", (len(episodios["mastitis"]) * 100 / vacas) if vacas else None,
                       "/100 vacas", vacas, "Tratamientos de mastitis del año por cada 100 vacas (un caso por vaca y mes)."))
    items.append(_item("cojeras", "Casos de cojera", (len(episodios["cojeras"]) * 100 / vacas) if vacas else None,
                       "/100 vacas", vacas, "Tratamientos de cojera o patas del año por cada 100 vacas."))
    items.append(_item("diarreas_crias", "Diarreas en crías", (len(episodios["diarreas_crias"]) * 100 / nacidos) if nacidos else None,
                       "/100 nacidos", nacidos, "Tratamientos de diarrea en crías de menos de un año por cada 100 nacidas."))

    gasto = db.query_one("SELECT SUM(monto) AS t FROM finanzas WHERE UPPER(tipo) = 'EGRESO' "
                         "AND UPPER(categoria) IN ('MEDICAMENTOS', 'VETERINARIO') AND fecha >= ? AND fecha <= ?",
                         (b.desde_iso, b.hoy_iso))
    g = float(gasto["t"] or 0) if gasto else 0.0
    items.append(_item("costo_sanidad_vaca", "Gasto en sanidad por vaca", (g / vacas) if (g and vacas) else None, "$/año", vacas,
                       "Drogas y veterinario del año (Finanzas) entre las vacas del hato.", con_meta=False))

    # Litros botados por retiro: días de retiro de leche de vacas en ordeño × L/vaca.
    dias_retiro = 0
    for r in trat:
        ini, fin = _f(r["fecha"]), _f(r["fecha_fin_retiro_leche"])
        if ini and fin and fin > ini:
            dias_retiro += (min(fin, b.hoy) - max(ini, b.desde)).days
    litros_botados = dias_retiro * litros_vaca_ordeno if (litros_vaca_ordeno and dias_retiro > 0) else (0 if dias_retiro == 0 and trat else None)
    precio = db.query_one("SELECT SUM(monto) AS m, SUM(litros) AS l FROM finanzas WHERE UPPER(categoria) = 'VENTA_LECHE' "
                          "AND fecha >= ? AND fecha <= ? AND litros > 0", (b.desde_iso, b.hoy_iso))
    precio_l = (float(precio["m"]) / float(precio["l"])) if (precio and precio["l"]) else None
    it = _item("litros_retiro", "Leche botada por retiro (estimado)", litros_botados, "L", dias_retiro,
               "Días de retiro de leche por tratamientos, por los litros que da una vaca en ordeño.", con_meta=False)
    if litros_botados and precio_l:
        it["detalle"] = f"≈ ${_num(round(litros_botados * precio_l))} al precio promedio del litro"
    items.append(it)

    # Ingreso de leche menos su parte de los gastos, por vaca en ordeño al mes.
    try:
        k = db.kpis_financieros(b.desde_iso, b.hoy_iso)
        margen = None
        if k.get("ingresos_leche") and not k.get("sin_gastos") and n_vacas_ordeno:
            margen = (float(k["ingresos_leche"]) - float(k.get("costo_leche_total") or 0)) / n_vacas_ordeno / 12
        items.append(_item("margen_vaca_ordeno", "Ingreso menos gasto por vaca en ordeño", margen, "$/mes", n_vacas_ordeno,
                           "Venta de leche del año menos la parte de los gastos que le toca a la leche, por vaca en ordeño y por mes.",
                           con_meta=False))
    except Exception:
        logger.error("indicadores: margen por vaca fallo", exc_info=True)
    return items


# --------------------------------------------------------------------------- #
# Pasturas
# --------------------------------------------------------------------------- #
def _pasturas(b: _Base) -> list[dict]:
    db = b.db
    items: list[dict] = []
    pots = {r["id"]: r for r in db.query(f"SELECT id, area_has FROM potreros WHERE {SQL_POTRERO_REAL}")}
    area = sum(float(p["area_has"] or 0) for p in pots.values())
    ult_peso = {r["animal_id"]: float(r["peso_kg"]) for r in db.query(
        "SELECT p.animal_id, p.peso_kg FROM pesajes p JOIN (SELECT animal_id, MAX(fecha) f FROM pesajes "
        "WHERE peso_kg > 0 GROUP BY animal_id) u ON u.animal_id = p.animal_id AND u.f = p.fecha WHERE p.peso_kg > 0")}
    ugg = 0.0
    n = 0
    for aid, a in b.animales.items():
        if a.get("estado") != "ACTIVO":
            continue
        n += 1
        if aid in ult_peso:
            ugg += ult_peso[aid] / 450.0
            continue
        fn = b.nacimiento(aid)
        edad = (b.hoy - fn).days if fn else None
        ugg += 0.3 if (edad is not None and edad < 365) else (0.6 if (edad is not None and edad < 730) else 1.0)
    items.append(_item("ugg_ha", "Animales por hectárea", (ugg / area) if area else None, "UGG/ha", n,
                       "Unidades de gran ganado (450 kg) del hato de hoy sobre las hectáreas de los potreros.", 2))

    # Descanso y ocupación reales, con los traslados del año.
    entradas: dict[int, set] = {}
    salidas: dict[int, set] = {}
    for r in db.query("SELECT fecha, potrero_origen, potrero_destino FROM traslados WHERE fecha >= ? AND fecha <= ?",
                      ((b.desde - timedelta(days=120)).isoformat(), b.hoy_iso)):
        d = _f(r["fecha"])
        if not d:
            continue
        if r["potrero_destino"] in pots:
            entradas.setdefault(r["potrero_destino"], set()).add(d)
        if r["potrero_origen"] in pots:
            salidas.setdefault(r["potrero_origen"], set()).add(d)
    descansos, ocupaciones = [], []
    for pid in pots:
        es = sorted(entradas.get(pid, set()))
        ss = sorted(salidas.get(pid, set()))
        for e in es:
            if e < b.desde:
                continue
            prev_s = max((s for s in ss if s < e), default=None)
            if prev_s and not any(prev_s < e2 < e for e2 in es):
                dias = (e - prev_s).days
                if 1 <= dias <= 365:
                    descansos.append(dias)
            sig_s = min((s for s in ss if s > e), default=None)
            if sig_s and not any(e < e2 < sig_s for e2 in es):
                dias = (sig_s - e).days
                if 1 <= dias <= 120:
                    ocupaciones.append(dias)
    items.append(_item("descanso_real", "Descanso real de los potreros", _prom(descansos), "días", len(descansos),
                       "Días entre la salida del ganado de un potrero y la siguiente entrada (traslados del año). Meta: 30 días en lluvias, 45 en seca."))
    items.append(_item("ocupacion_real", "Ocupación real de los potreros", _prom(ocupaciones), "días", len(ocupaciones),
                       "Días que el ganado se quedó en un potrero en cada entrada (traslados del año).", 1))
    return items


# --------------------------------------------------------------------------- #
# Entrada pública
# --------------------------------------------------------------------------- #
def indicadores_hato(db, hoy: Optional[date] = None) -> dict:
    """Todos los indicadores agrupados, más las listas para actuar."""
    hoy = hoy or date.today()
    errores: dict[str, str] = {}
    b = _Base(db, hoy)
    repro, problema = _seguro("reproduccion", lambda: _reproduccion(b), errores, ([], []))
    leche, largas, extra = _seguro("leche", lambda: _leche(b), errores, ([], [], {}))
    l_ordeno = next((i["valor"] for i in leche if i["k"] == "litros_vaca_ordeno"), None)
    carne = _seguro("carne", lambda: _carne(b), errores, [])
    sanidad = _seguro("sanidad", lambda: _sanidad(b, l_ordeno, extra.get("en_ordeno") or 0), errores, [])
    pasturas = _seguro("pasturas", lambda: _pasturas(b), errores, [])
    grupos = [
        {"k": "reproduccion", "titulo": "Reproducción", "items": repro},
        {"k": "leche", "titulo": "Leche", "items": leche},
        {"k": "carne", "titulo": "Carne y crías", "items": carne},
        {"k": "sanidad", "titulo": "Sanidad y plata", "items": sanidad},
        {"k": "pasturas", "titulo": "Pasturas", "items": pasturas},
    ]
    todos = [i for g in grupos for i in g["items"]]
    resumen = {c: sum(1 for i in todos if i["color"] == c) for c in ("verde", "ambar", "rojo", "gris")}
    out: dict[str, Any] = {
        "desde": b.desde_iso, "hasta": b.hoy_iso, "grupos": grupos, "resumen": resumen,
        "vacas_problema": problema, "lactancias_largas": largas,
    }
    if errores:
        out["errores"] = errores
    return out
