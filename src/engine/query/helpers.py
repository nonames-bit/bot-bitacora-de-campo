"""Funciones auxiliares de módulo compartidas por el motor de consultas: fotos,
edad zootécnica, formato numérico es-CO, brackets de inventario SG y matching
flexible de nombres de potrero (romano <-> arábigo)."""
from __future__ import annotations

import html
import os
import re
from datetime import date
from typing import Optional

from ...db.database import Database
from ...utils import normalizar, to_date

REPOSO_LISTO_DIAS = 21


def buscar_foto_animal(db: Database, tag_or_name: str | int, media_dir: str = "media") -> str | None:
    """Busca la ruta local de la foto de un animal en la tabla fotos y en el directorio media/."""
    if not tag_or_name:
        return None
    aid = db.resolve_animal(tag_or_name)
    tags_probar = [str(tag_or_name).strip()]
    if aid is not None:
        fotos = db.fotos_de(aid, limit=1)
        if fotos and fotos[0]["ruta"] and os.path.exists(fotos[0]["ruta"]):
            return fotos[0]["ruta"]
        animal = db.get_animal(aid)
        if animal:
            if animal["tag"]:
                tags_probar.append(str(animal["tag"]).strip())
            if animal["nombre"]:
                tags_probar.append(str(animal["nombre"]).strip())

    if not os.path.exists(media_dir):
        return None

    # Probar candidatos en disco
    for cand in tags_probar:
        if not cand:
            continue
        c_clean = cand.lower().strip()
        for ext in (".jpg", ".jpeg", ".png"):
            p = os.path.join(media_dir, c_clean + ext)
            if os.path.exists(p):
                return p
            p_upper = os.path.join(media_dir, cand.upper().strip() + ext)
            if os.path.exists(p_upper):
                return p_upper
        # Si es número puro (ej. 9 o 47), probar variantes prefijadas habituales en SG (a009, v047, n069, ja26)
        if c_clean.isdigit():
            for pref in ("a", "n", "v", "ja"):
                for pad in (3, 2, 0):
                    padded = pref + (c_clean.zfill(pad) if pad else c_clean)
                    for ext in (".jpg", ".jpeg"):
                        p = os.path.join(media_dir, padded + ext)
                        if os.path.exists(p):
                            return p
    return None


def formatear_edad_zootecnica(f_nac: date, hoy: date) -> str:
    """Calcula y formatea la edad zootécnica legible con días totales entre paréntesis.

    Formato:
    - >= 365 días: X años Y meses (Z días) o X años (Z días) si meses == 0
    - 30 a 364 días: M meses D días (Z días) o M meses (Z días) si días == 0
    - < 30 días: D días
    """
    dias_totales = (hoy - f_nac).days
    if dias_totales < 0:
        return "0 días"

    dias_totales_str = f"{dias_totales:,}".replace(",", ".")

    if dias_totales < 30:
        return f"{dias_totales} día{'s' if dias_totales != 1 else ''}"

    # Cálculo exacto por calendario
    años = hoy.year - f_nac.year
    meses = hoy.month - f_nac.month
    dias = hoy.day - f_nac.day
    if dias < 0:
        meses -= 1
        año_prev = hoy.year if hoy.month > 1 else hoy.year - 1
        mes_prev = hoy.month - 1 if hoy.month > 1 else 12
        import calendar
        _, num_dias_prev = calendar.monthrange(año_prev, mes_prev)
        dias += num_dias_prev
    if meses < 0:
        años -= 1
        meses += 12

    if dias_totales >= 365:
        año_str = f"{años} año{'s' if años != 1 else ''}"
        if meses > 0:
            mes_str = f"{meses} mes{'es' if meses != 1 else ''}"
            texto_edad = f"{año_str} {mes_str}"
        else:
            texto_edad = año_str
        return f"{texto_edad} ({dias_totales_str} días)"
    else:
        # 30 a 364 días
        mes_str = f"{meses} mes{'es' if meses != 1 else ''}"
        if dias > 0:
            dia_str = f"{dias} día{'s' if dias != 1 else ''}"
            texto_edad = f"{mes_str} {dia_str}"
        else:
            texto_edad = mes_str
        return f"{texto_edad} ({dias_totales_str} días)"


def _fmt_es_co(num: int | float) -> str:
    """Formatea enteros o flotantes con separador de miles '.' (estilo es-CO)."""
    if isinstance(num, int):
        return f"{num:,}".replace(",", ".")
    return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def calcular_brackets_inventario_sg(db: Database, hoy: date | None = None) -> dict:
    """Calcula la distribución de inventario activo por brackets de edad exactos de Software Ganadero (SG).

    Brackets SG:
    - Hembras:
      * <1 año: 0-364 días (<365 días)
      * 1-2 años: 365-729 días (<730 días)
      * 2-4 años: 730-1459 días (<1460 días)
      * 4-8 años: 1460-2921 días (<=2921 días)
      * 8-10 años: 2922-3651 días (<=3651 días)
      * >10 años: >3651 días (>3651 días)
    - Machos:
      * <1 año: 0-364 días (<365 días)
      * 1-2 años: 365-729 días (<730 días)
      * >2 años: 730+ días pero no reproductor (730 a 912 días)
      * Reproductor: machos con flag reproductor (marcado TORO o edad >= 913 días / >30 meses)
    - Sin clasificar / Sin narr (sexo indefinido o no especificado)
    """
    if hoy is None:
        hoy = date.today()

    total_historico = db.count("animales")
    animales = db.query(
        "SELECT id_animal, tag, nombre, sexo, raza, fecha_nacimiento, madre_id, notas "
        "FROM animales WHERE estado = 'ACTIVO'"
    )
    n_total = len(animales)

    # Brackets contadores
    h_brackets = {
        "menor_1": 0,
        "1_2": 0,
        "2_4": 0,
        "4_8": 0,
        "8_10": 0,
        "mayor_10": 0,
    }
    m_brackets = {
        "menor_1": 0,
        "1_2": 0,
        "mayor_2": 0,
        "reproductor": 0,
    }
    sin_narr_count = 0
    terneros_menor_12m = 0

    for a in animales:
        aid = a["id_animal"]

        # Resolver fecha de nacimiento (o fallback desde partos de cría / madre)
        fn = to_date(a["fecha_nacimiento"])
        if not fn:
            p = db.query_one(
                "SELECT fecha FROM partos WHERE id_cria = ? AND (vaca_id IS NULL OR vaca_id != ?) ORDER BY fecha DESC LIMIT 1",
                (aid, aid),
            )
            if p and p["fecha"]:
                fn = to_date(p["fecha"])
            elif a["madre_id"] and a["madre_id"] != aid:
                p_m = db.query_one(
                    "SELECT fecha FROM partos WHERE vaca_id = ? AND fecha IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                    (a["madre_id"],),
                )
                if p_m and p_m["fecha"]:
                    d_m = to_date(p_m["fecha"])
                    if d_m and (hoy - d_m).days <= 450:
                        fn = d_m

        edad_dias = max(0, (hoy - fn).days) if fn else None
        if edad_dias is not None and edad_dias < 365:
            terneros_menor_12m += 1

        # Resolver sexo
        s_raw = (a["sexo"] or "").strip().lower()
        if not s_raw or s_raw in ("i", "indefinido", "indeterminado", "desconocido", "?"):
            p_cria = db.query_one(
                "SELECT sexo_cria FROM partos WHERE id_cria = ? AND sexo_cria IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                (aid,),
            )
            if p_cria and p_cria["sexo_cria"]:
                s_raw = p_cria["sexo_cria"].strip().lower()

        es_macho = bool(s_raw.startswith("m") or s_raw in ("macho", "toro", "ternero", "novillo", "buey"))
        es_hembra = bool(s_raw.startswith("h") or s_raw in ("hembra", "vaca", "novilla", "ternera"))

        if es_hembra:
            if edad_dias is not None:
                if edad_dias < 365:
                    h_brackets["menor_1"] += 1
                elif edad_dias < 730:
                    h_brackets["1_2"] += 1
                elif edad_dias < 1460:
                    h_brackets["2_4"] += 1
                elif edad_dias <= 2921:
                    h_brackets["4_8"] += 1
                elif edad_dias <= 3651:
                    h_brackets["8_10"] += 1
                else:
                    h_brackets["mayor_10"] += 1
            else:
                # Sin fecha de nacimiento conocida: inferir por partos/madre
                has_parto = db.query_one(
                    "SELECT 1 FROM partos WHERE vaca_id = ? AND (id_cria IS NULL OR id_cria != ?) LIMIT 1",
                    (aid, aid),
                )
                if has_parto:
                    h_brackets["4_8"] += 1
                elif a["madre_id"]:
                    h_brackets["menor_1"] += 1
                else:
                    h_brackets["2_4"] += 1

        elif es_macho:
            txt_info = f"{a['nombre'] or ''} {a['notas'] or ''} {a['tag'] or ''}".upper()
            es_reproductor_flag = bool(re.search(r"\b(?:TORO|REPRODUCTOR|PADRON|SEMEN|PAJILLA)\b", txt_info))

            if es_reproductor_flag or (edad_dias is not None and edad_dias >= 913):
                m_brackets["reproductor"] += 1
            elif edad_dias is not None:
                if edad_dias < 365:
                    m_brackets["menor_1"] += 1
                elif edad_dias < 730:
                    m_brackets["1_2"] += 1
                else:
                    m_brackets["mayor_2"] += 1
            else:
                # Macho con edad desconocida
                if a["madre_id"]:
                    m_brackets["menor_1"] += 1
                else:
                    m_brackets["mayor_2"] += 1

        else:
            sin_narr_count += 1

    total_hembras = sum(h_brackets.values())
    total_machos = sum(m_brackets.values())

    filas_definicion = [
        ("Hembras <1 año", h_brackets["menor_1"]),
        ("Hembras 1-2 años", h_brackets["1_2"]),
        ("Hembras 2-4 años", h_brackets["2_4"]),
        ("Hembras 4-8 años", h_brackets["4_8"]),
        ("Hembras 8-10 años", h_brackets["8_10"]),
        ("Hembras >10 años", h_brackets["mayor_10"]),
        ("Machos <1 año", m_brackets["menor_1"]),
        ("Machos 1-2 años", m_brackets["1_2"]),
        ("Machos >2 años", m_brackets["mayor_2"]),
        ("Reproductor", m_brackets["reproductor"]),
    ]
    if sin_narr_count > 0:
        filas_definicion.append(("Sin clasificar", sin_narr_count))

    filas = []
    acum_pct = 0.0
    for label, count in filas_definicion:
        pct = (count / n_total * 100.0) if n_total > 0 else 0.0
        acum_pct += pct
        if acum_pct > 100.0:
            acum_pct = 100.0
        filas.append((label, count, pct, acum_pct))

    return {
        "total_activos": n_total,
        "total_historico": total_historico,
        "total_hembras": total_hembras,
        "total_machos": total_machos,
        "total_sin_sexo": sin_narr_count,
        "terneros_menor_12m": terneros_menor_12m,
        "h_brackets": h_brackets,
        "m_brackets": m_brackets,
        "filas": filas,
    }


def generar_resumen_inventario_sg(db: Database, hoy: date | None = None) -> str:
    """Genera la tabla formateada en HTML <pre> del Resumen General de Inventario (SG)."""
    if hoy is None:
        hoy = date.today()
    datos = calcular_brackets_inventario_sg(db, hoy)
    total_activos = datos["total_activos"]
    if total_activos == 0:
        return "📊 Inventario: 0 animales activos en la finca."

    pre_lines = [
        f"{'Categoría'.ljust(18)} {'Nro'.rjust(4)} {'Distrib.'.rjust(8)} {'Acum'.rjust(8)}",
    ]
    for cat, n, pct, acum in datos["filas"]:
        cat_str = cat.ljust(18)
        n_str = _fmt_es_co(n).rjust(4)
        pct_str = f"{pct:6.2f}%"
        acum_str = f"{acum:6.2f}%"
        pre_lines.append(f"{cat_str} {n_str} {pct_str} {acum_str}")

    pre_lines.append("─" * 42)
    pie_partes = [
        f"Hembras {_fmt_es_co(datos['total_hembras'])}",
        f"Machos {_fmt_es_co(datos['total_machos'])}",
    ]
    if datos["total_sin_sexo"] > 0:
        pie_partes.append(f"Sin clasificar {_fmt_es_co(datos['total_sin_sexo'])}")
    pie_partes.append(f"Total {_fmt_es_co(datos['total_activos'])}")
    pre_lines.append(" | ".join(pie_partes))

    cuerpo = "\n".join(pre_lines)
    cuerpo_escapado = html.escape(cuerpo)
    return (
        "📊 <b>Resumen General de Inventario</b>\n"
        f"<pre>\n{cuerpo_escapado}\n</pre>"
    )


def calcular_existencias_potreros_sg(db: Database, hoy: Optional[date] = None) -> list[dict]:
    """Calcula las existencias por potrero desglosadas por las 9 categorías zootécnicas de Software Ganadero (SG).

    Inventario presente: solo potreros reales (geom WGS84, excluye legacy
    DBF); solo animales ACTIVOS por potrero vigente (último traslado)."""
    hoy = hoy or date.today()
    potreros = db.query("SELECT * FROM potreros WHERE geom_wkt_4326 IS NOT NULL")
    if not potreros:
        return []

    potreros_by_id = {p["id"]: p for p in potreros}
    grupos: dict[str, dict] = {}
    for p in potreros:
        if p["dias_reposo"] is not None and p["dias_reposo"] > 365:
            continue
        raw_nom = (p["nombre"] or p["codigo"] or str(p["id"])).strip()
        norm = normalizar(raw_nom).strip().upper()
        if not norm:
            norm = f"POTRERO {p['id']}"
        if norm not in grupos:
            grupos[norm] = {
                "display": raw_nom.upper(),
                "ids": set(),
                "animales": [],
                "ch": 0, "hl": 0, "nv": 0, "vp": 0, "vs": 0,
                "cm": 0, "ml": 0, "mc": 0, "rep": 0,
                "total": 0,
                "dias_reposo": p["dias_reposo"],
                "fecha_ingreso_reciente": None,
            }
        grupos[norm]["ids"].add(p["id"])

    animales = db.query(
        "SELECT id_animal, tag, potrero_id, estado, sexo, fecha_nacimiento, nombre, notas, madre_id FROM animales WHERE estado = 'ACTIVO'"
    )
    for a in animales:
        aid = a["id_animal"]
        ult = db.query_one(
            "SELECT potrero_destino, fecha, lote FROM traslados WHERE animal_id=? ORDER BY fecha DESC, id DESC LIMIT 1",
            (aid,),
        )
        pid = ult["potrero_destino"] if (ult and ult["potrero_destino"] is not None) else a["potrero_id"]
        fecha_ingreso = ult["fecha"] if ult else None

        if pid is not None and pid in potreros_by_id:
            p_row = potreros_by_id[pid]
            raw_nom = (p_row["nombre"] or p_row["codigo"] or str(pid)).strip()
            norm = normalizar(raw_nom).strip().upper()
            if norm not in grupos:
                grupos[norm] = {
                    "display": raw_nom.upper(),
                    "ids": {pid},
                    "animales": [],
                    "ch": 0, "hl": 0, "nv": 0, "vp": 0, "vs": 0,
                    "cm": 0, "ml": 0, "mc": 0, "rep": 0,
                    "total": 0,
                    "dias_reposo": None,
                    "fecha_ingreso_reciente": None,
                }
            g = grupos[norm]
            g["animales"].append(a)
            g["total"] += 1
            if fecha_ingreso:
                if not g["fecha_ingreso_reciente"] or str(fecha_ingreso) > str(g["fecha_ingreso_reciente"]):
                    g["fecha_ingreso_reciente"] = str(fecha_ingreso)

            # Categorizar según SG (potreros.jpg)
            sexo = (a["sexo"] or "").strip().lower()
            fnac = to_date(a["fecha_nacimiento"])
            edad_d = (hoy - fnac).days if fnac else None
            es_h = bool(sexo.startswith("h") or sexo.startswith("f") or sexo in ("vaca", "novilla", "ternera"))

            if es_h:
                if edad_d is not None and edad_d < 365:
                    g["ch"] += 1
                elif edad_d is not None and edad_d < 730:
                    g["hl"] += 1
                else:
                    p_ult = db.ultimo_parto(aid)
                    if p_ult and p_ult["fecha"] and to_date(p_ult["fecha"]):
                        dp = (hoy - to_date(p_ult["fecha"])).days
                        if dp <= 305:
                            g["vp"] += 1
                        else:
                            g["vs"] += 1
                    else:
                        g["nv"] += 1
            else:
                nom_m = f"{a['nombre'] or ''} {a['notas'] or ''} {a['tag'] or ''}".upper()
                if "REPRODUCTOR" in nom_m or "PADRON" in nom_m or "TORO" in nom_m or (edad_d is not None and edad_d >= 1095):
                    g["rep"] += 1
                elif edad_d is not None and edad_d < 365:
                    g["cm"] += 1
                elif edad_d is not None and edad_d < 730:
                    g["ml"] += 1
                else:
                    g["mc"] += 1

    ocupados = [g for g in grupos.values() if g["total"] > 0]
    ocupados.sort(key=lambda x: (-x["total"], x["display"]))
    return ocupados


UGG_FACTOR_SG = {
    "ch": 0.30, "cm": 0.30,   # crías (macho/hembra) < 1 año
    "hl": 0.60, "ml": 0.60,   # levante (macho/hembra) 1-2 años
    "nv": 0.80,               # novilla de vientre
    "vp": 1.00, "vs": 0.90,   # vaca parida / vaca seca
    "mc": 0.90,               # macho >2 años no reproductor (ceba/levante adulto)
    "rep": 1.30,              # reproductor
}
ETIQUETAS_SG = {
    "cm": "Cría macho", "ch": "Cría hembra",
    "ml": "Levante macho", "hl": "Levante hembra",
    "nv": "Novilla de vientre", "vp": "Vaca parida", "vs": "Vaca seca",
    "mc": "Macho de ceba/levante adulto", "rep": "Reproductor",
}


def calcular_estructura_hato_sg(db: Database, hoy: Optional[date] = None) -> dict:
    """Estructura del hato con las mismas 9 categorías SG que
    ``calcular_existencias_potreros_sg`` (CH/HL/NV/VP/VS/CM/ML/MC/REP), pero
    a nivel de finca completa en vez de por potrero -- incluye también los
    animales sin potrero resoluble, que esa tabla deja fuera por diseño (ver
    ``contar_animales_sin_potrero``). El UGG (Unidad Gran Ganado) es una
    equivalencia estándar por categoría, no un cálculo a partir del peso real
    de cada animal (no hay cobertura de pesajes para todo el hato)."""
    hoy = hoy or date.today()
    cont = {k: 0 for k in UGG_FACTOR_SG}
    animales = db.query(
        "SELECT id_animal, tag, sexo, fecha_nacimiento, nombre, notas FROM animales WHERE estado = 'ACTIVO'"
    )
    for a in animales:
        aid = a["id_animal"]
        sexo = (a["sexo"] or "").strip().lower()
        fnac = to_date(a["fecha_nacimiento"])
        edad_d = (hoy - fnac).days if fnac else None
        es_h = bool(sexo.startswith("h") or sexo.startswith("f") or sexo in ("vaca", "novilla", "ternera"))
        if es_h:
            if edad_d is not None and edad_d < 365:
                cont["ch"] += 1
            elif edad_d is not None and edad_d < 730:
                cont["hl"] += 1
            else:
                p_ult = db.ultimo_parto(aid)
                if p_ult and p_ult["fecha"] and to_date(p_ult["fecha"]):
                    dp = (hoy - to_date(p_ult["fecha"])).days
                    cont["vp" if dp <= 305 else "vs"] += 1
                else:
                    cont["nv"] += 1
        else:
            nom_m = f"{a['nombre'] or ''} {a['notas'] or ''} {a['tag'] or ''}".upper()
            if "REPRODUCTOR" in nom_m or "PADRON" in nom_m or "TORO" in nom_m or (edad_d is not None and edad_d >= 1095):
                cont["rep"] += 1
            elif edad_d is not None and edad_d < 365:
                cont["cm"] += 1
            elif edad_d is not None and edad_d < 730:
                cont["ml"] += 1
            else:
                cont["mc"] += 1

    total = sum(cont.values())
    filas = []
    total_ugg = 0.0
    for k in ("cm", "ch", "ml", "hl", "nv", "vp", "vs", "mc", "rep"):
        n = cont[k]
        if n == 0:
            continue
        ugg = round(n * UGG_FACTOR_SG[k], 2)
        total_ugg += ugg
        filas.append({
            "categoria": ETIQUETAS_SG[k], "n": n,
            "pct": round(n / total * 100, 2) if total else 0.0,
            "ugg": ugg,
        })
    return {
        "filas": filas,
        "total": total,
        "total_ugg": round(total_ugg, 2),
        "total_hembras": cont["ch"] + cont["hl"] + cont["nv"] + cont["vp"] + cont["vs"],
        "total_machos": cont["cm"] + cont["ml"] + cont["mc"] + cont["rep"],
    }


def contar_animales_sin_potrero(db: Database) -> int:
    """Cuenta animales ACTIVOS sin potrero vigente resoluble a un potrero
    real (ni traslado ni potrero_id apuntan a un potrero con geom WGS84).
    Explica por qué el total de la tabla de 'Existencias por Potrero' puede
    ser menor que el total general de activos: esos animales sí cuentan en
    el inventario, pero no aparecen en ninguna fila de la tabla porque no
    tienen potrero asignado (los legacy nunca se listan como presente)."""
    potreros_validos = {p["id"] for p in db.query("SELECT id FROM potreros WHERE geom_wkt_4326 IS NOT NULL")}
    animales = db.query("SELECT id_animal, potrero_id FROM animales WHERE estado = 'ACTIVO'")
    n = 0
    for a in animales:
        aid = a["id_animal"]
        ult = db.query_one(
            "SELECT potrero_destino FROM traslados WHERE animal_id=? ORDER BY fecha DESC, id DESC LIMIT 1",
            (aid,),
        )
        pid = ult["potrero_destino"] if (ult and ult["potrero_destino"] is not None) else a["potrero_id"]
        if pid is None or pid not in potreros_validos:
            n += 1
    return n


def formatear_tabla_potreros_sg(filas_potreros: list[dict], sin_potrero: int = 0) -> str:
    """Formatea la tabla de inventario por potreros exacta a la de la finca."""
    if not filas_potreros:
        return "📍 <b>[01-JA] GANADERIA-JA · Existencias por Potreros</b>\n\nNo hay potreros con animales activos actualmente."

    tot_ch = sum(p["ch"] for p in filas_potreros)
    tot_hl = sum(p["hl"] for p in filas_potreros)
    tot_nv = sum(p["nv"] for p in filas_potreros)
    tot_vp = sum(p["vp"] for p in filas_potreros)
    tot_vs = sum(p["vs"] for p in filas_potreros)
    tot_cm = sum(p["cm"] for p in filas_potreros)
    tot_ml = sum(p["ml"] for p in filas_potreros)
    tot_mc = sum(p["mc"] for p in filas_potreros)
    tot_rep = sum(p["rep"] for p in filas_potreros)
    tot_general = sum(p["total"] for p in filas_potreros)

    def v(n: int) -> str:
        return str(n) if n > 0 else "."

    max_nom = max(len(p["display"]) for p in filas_potreros)
    col_w = min(max(max_nom, 14), 16)

    header = f"{'Potrero'.ljust(col_w)} CH HL NV VP VS CM ML MC RP  Tot"
    sep = "─" * len(header)
    lines = [header, sep]

    for p in filas_potreros:
        nom = p["display"][:col_w].ljust(col_w)
        ch = v(p["ch"]).rjust(2)
        hl = v(p["hl"]).rjust(2)
        nv = v(p["nv"]).rjust(2)
        vp = v(p["vp"]).rjust(2)
        vs = v(p["vs"]).rjust(2)
        cm = v(p["cm"]).rjust(2)
        ml = v(p["ml"]).rjust(2)
        mc = v(p["mc"]).rjust(2)
        rep = v(p["rep"]).rjust(2)
        tot = str(p["total"]).rjust(4)
        lines.append(f"{nom} {ch} {hl} {nv} {vp} {vs} {cm} {ml} {mc} {rep} {tot}")

    lines.append(sep)
    tot_nom = "Totales...".ljust(col_w)
    lines.append(
        f"{tot_nom} {v(tot_ch).rjust(2)} {v(tot_hl).rjust(2)} {v(tot_nv).rjust(2)} {v(tot_vp).rjust(2)} "
        f"{v(tot_vs).rjust(2)} {v(tot_cm).rjust(2)} {v(tot_ml).rjust(2)} {v(tot_mc).rjust(2)} "
        f"{v(tot_rep).rjust(2)} {str(tot_general).rjust(4)}"
    )

    cuerpo_escapado = html.escape("\n".join(lines))
    msg = [
        "🌿 <b>[01-JA] GANADERIA-JA · Existencias por Potreros</b>",
        f"<pre>\n{cuerpo_escapado}\n</pre>",
        "<i>Leyenda: CH: Cría hembra | HL: Hemb. levante | NV: Nov. vientre | VP: Vaca parida | VS: Vaca seca | CM: Cría macho | ML: Mac. levante | MC: Macho ceba | RP: Reproductor | Tot: Total activos</i>",
    ]
    if sin_potrero > 0:
        palabra = "animal" if sin_potrero == 1 else "animales"
        msg.append(
            f"⚠️ <i>{sin_potrero} {palabra} activo(s) sin potrero asignado (no aparece(n) en esta tabla, "
            f"por eso el total general puede ser {sin_potrero} más que la suma de arriba).</i>"
        )
    return "\n".join(msg)


def formatear_ocupacion_potreros(db: Database, hoy: Optional[date] = None) -> str:
    """Calcula y formatea los días de ocupación y rotación Voisin para todos los potreros (solo reales)."""
    hoy = hoy or date.today()
    potreros = db.query("SELECT * FROM potreros WHERE geom_wkt_4326 IS NOT NULL")
    if not potreros:
        return "No hay potreros registrados en la bitácora."

    filas_ocupados = calcular_existencias_potreros_sg(db, hoy)
    nombres_ocupados = {p["display"] for p in filas_ocupados}

    # Potreros ocupados
    lineas_ocupados = []
    for p in filas_ocupados:
        f_ingreso = p.get("fecha_ingreso_reciente")
        dias_ocup = (hoy - to_date(f_ingreso)).days if f_ingreso and to_date(f_ingreso) else None

        if dias_ocup is not None:
            if dias_ocup <= 3:
                estado_v = f"🟢 {dias_ocup}d ocupación (Óptimo Voisin)"
            elif dias_ocup <= 6:
                estado_v = f"🟡 {dias_ocup}d ocupación (Rotación recomendada)"
            else:
                estado_v = f"🔴 {dias_ocup}d ocupación (⚠️ Sobreocupación)"
        else:
            estado_v = "🟢 En pastoreo activo"

        lineas_ocupados.append(
            f"• <b>{p['display']}:</b> {p['total']} animales · {estado_v}"
        )

    # Potreros vacíos / en reposo
    lineas_reposo = []
    for p in potreros:
        raw_nom = (p["nombre"] or p["codigo"] or str(p["id"])).strip().upper()
        if raw_nom in nombres_ocupados:
            continue
        d_reposo = p["dias_reposo"]
        if d_reposo is not None and d_reposo > 365:
            continue

        if d_reposo is not None:
            if d_reposo >= 30:
                est_r = f"🟢 {d_reposo}d reposo (✅ Listo para pastoreo)"
            else:
                est_r = f"⏳ {d_reposo}d reposo (recuperando forraje)"
        else:
            est_r = "⏳ En reposo"
        lineas_reposo.append(f"• <b>{raw_nom}:</b> {est_r}")

    salida = [
        "🌿 <b>Días de Ocupación y Rotación Voisin — Ganadería JA</b>",
        "",
        f"📍 <b>Potreros Ocupados ({len(lineas_ocupados)}):</b>",
    ]
    if lineas_ocupados:
        salida.extend(lineas_ocupados)
    else:
        salida.append("<i>No hay potreros con ganado actualmente.</i>")

    salida.append("")
    salida.append(f"🌱 <b>Potreros en Reposo / Recuperación ({len(lineas_reposo)}):</b>")
    if lineas_reposo:
        salida.extend(lineas_reposo[:15])
        if len(lineas_reposo) > 15:
            salida.append(f"<i>... y {len(lineas_reposo)-15} potreros más en descanso.</i>")
    else:
        salida.append("<i>Todos los potreros están actualmente ocupados.</i>")

    salida.append("")
    salida.append("💡 <i>Regla Voisin: Ocupación máxima 1 a 3 días por potrero para garantizar el rebrote del pasto.</i>")
    return "\n".join(salida)


ROMANO_A_ARABIGO = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10"}
ARABIGO_A_ROMANO = {v: k for k, v in ROMANO_A_ARABIGO.items()}


def _normalizar_potrero_key(s: str) -> str:
    """Normaliza clave de potrero para matching flexible (I <-> 1)."""
    if not s:
        return ""
    t = normalizar(s).strip()
    # Convierte sufijo romano a arábigo y viceversa para matching
    # Ej: "olegario i" -> "olegario 1" y "olegario 1" -> "olegario i" ambos se consideran equivalentes en _buscar_potrero
    return t


def _potrero_variantes(nombre: str) -> set[str]:
    """Genera variantes de un nombre de potrero para matching (I<->1)."""
    base = normalizar(nombre).strip()
    variantes = {base}
    # si termina en romano, agrega variante arábiga
    m = re.search(r"\s([ivx]+)$", base)
    if m:
        romano = m.group(1)
        if romano in ROMANO_A_ARABIGO:
            variantes.add(re.sub(r"\s[ivx]+$", f" {ROMANO_A_ARABIGO[romano]}", base))
    # si termina en arábigo, agrega variante romana
    m2 = re.search(r"\s(\d+)$", base)
    if m2:
        arab = m2.group(1)
        if arab in ARABIGO_A_ROMANO:
            variantes.add(re.sub(r"\s\d+$", f" {ARABIGO_A_ROMANO[arab]}", base))
    return variantes


def extraer_nombre_potrero(texto: str) -> str | None:
    """Extrae el nombre o código del potrero de una consulta en lenguaje natural."""
    if not texto:
        return None
    t = normalizar(texto)
    m = re.search(r"\bpotreros?\s+([a-z0-9\s\-]+)", t)
    if not m:
        return None
    nombre = m.group(1).strip()
    nombre = re.split(r"[?!.,;:¿¡]", nombre)[0].strip()
    nombre = re.sub(r"\s+(?:por\s+favor|gracias|hoy|ahora|actualmente)$", "", nombre).strip()
    return nombre if nombre else None
