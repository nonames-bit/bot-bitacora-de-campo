"""Motor de consultas: respuestas zootécnicas a preguntas en lenguaje natural."""
from __future__ import annotations

import html
import os
import re
from datetime import date

from ..db.database import Database
from ..parsers import nlp_engine as nlu
from ..utils import add_days, iso, normalizar, to_date
from .growth_engine import gmd
from .reproductive_engine import (
    dias_abiertos,
    fecha_ecografia,
    fecha_estimada_parto,
    fecha_palpacion,
    fecha_secado,
)

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
        "📊 <b>Resumen General de Inventario (SG)</b>\n"
        f"<pre>\n{cuerpo_escapado}\n</pre>"
    )


def calcular_existencias_potreros_sg(db: Database, hoy: Optional[date] = None) -> list[dict]:
    """Calcula las existencias por potrero desglosadas por las 9 categorías zootécnicas de Software Ganadero (SG)."""
    hoy = hoy or date.today()
    potreros = db.query("SELECT * FROM potreros")
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


def formatear_tabla_potreros_sg(filas_potreros: list[dict]) -> str:
    """Formatea la tabla de inventario por potreros exacta a la de Software Ganadero (potreros.jpg)."""
    if not filas_potreros:
        return "📍 <b>[01-JA] GANADERIA-JA · Existencias por Potreros (SG)</b>\n\nNo hay potreros con animales activos actualmente."

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
        "🌿 <b>[01-JA] GANADERIA-JA · Existencias por Potreros (SG)</b>",
        f"<pre>\n{cuerpo_escapado}\n</pre>",
        "<i>Leyenda: CH: Cría hembra | HL: Hemb. levante | NV: Nov. vientre | VP: Vaca parida | VS: Vaca seca | CM: Cría macho | ML: Mac. levante | MC: Macho ceba | RP: Reproductor | Tot: Total activos</i>",
    ]
    return "\n".join(msg)


def formatear_ocupacion_potreros(db: Database, hoy: Optional[date] = None) -> str:
    """Calcula y formatea los días de ocupación y rotación Voisin para todos los potreros."""
    hoy = hoy or date.today()
    potreros = db.query("SELECT * FROM potreros")
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


class QueryEngine:
    """Responde preguntas frecuentes del personal de campo."""

    extraer_nombre_potrero = staticmethod(extraer_nombre_potrero)

    def __init__(self, db: Database, hoy: date | None = None):
        self.db = db
        self.hoy = hoy or date.today()

    def responder(self, texto: str) -> str:
        t = normalizar(texto)
        tag = nlu.extraer_tag(texto)

        # 1. Ubicación y potrero del animal (ej. "¿en qué potrero está patricia?", "¿dónde está la vaca 47?")
        if (
            re.search(r"\b(?:donde\s+esta|donde\s+anda|donde\s+se\s+encuentra|en\s+que\s+potrero|ubicacion)\b", t)
            or (tag and re.search(r"\bpotrero\b", t) and re.search(r"\b(?:esta|anda|se\s+encuentra|quedo)\b", t))
        ):
            return self._ubicacion_animal(tag)

        # 1b. Traslados y movimientos de potrero (ej. "¿cuándo se movió patricia?", "¿cuándo fue el traslado de la 47?")
        if tag and re.search(r"\b(?:cuando\s+se\s+movi[oó]|cuando\s+se\s+traslad[oó]|cuando\s+se\s+cambi[oó]|cuando\s+fue\s+el\s+traslado|cuando\s+entr[oó]|traslados?|movimientos?)\b", t):
            return self._ultimo_traslado(tag)

        # 2. Partos y maternidad
        if re.search(r"\bpari[oó]\b|\bparto\b", t):
            return self._ultimo_parto(tag)

        # 3. Servicios e Inseminación
        if re.search(r"\b(?:que\s+vacas?|cuales\s+vacas?|que\s+animales?|a\s+que\s+vacas?|hay\s+para\s+inseminar)\b", t) or not tag:
            if re.search(r"\binsemin|\bservicio\b|\bpajuela\b|\bmonta\b|\btoca.*servicio\b", t):
                return self._inseminacion_programada()
        if tag and (re.search(r"\binsemin|\bservicio\b|\bpajuela\b|\bmonta\b", t)):
            return self._ultimo_servicio(tag)
        if re.search(r"\bpalpacion", t) and re.search(r"\bpendiente", t):
            return self._palpacion_pendiente()
        if re.search(r"\binsemin", t) or (
            re.search(r"\b(?:toca|tocan|debo|deben|debemos|tengo que|servir)\b", t)
            and re.search(r"\bservicio\b|\bia\b", t)
        ):
            return self._inseminacion_programada()

        # 4. Secado y retiros
        if re.search(r"\bsecado\b", t):
            return self._secado(tag)
        if re.search(r"\bretiro\b|\bmedicamento\b|\bremedio\b", t):
            if tag:
                return self._retiro_animal(tag)
            return self._en_retiro()

        # 5. Genealogía y familia
        if tag and re.search(r"\b(?:madre|padre|mama|papa|genealogia|familia|hijos?|hijas?|crias?)\b", t):
            return self._genealogia(tag)

        # 6. Ficha zootécnica
        if re.search(r"\b(?:historial|ficha|hoja de vida|consulta|info|informacion|datos|buscar|ver)\b", t) and tag:
            return self._historial(tag)
        if re.search(r"\b(?:historial|ficha|consulta)\b", t):
            return self._historial(tag)

        # 7. Pesaje y crecimiento
        if re.search(r"\bpes[oó]\b|\bganancia\b|\bgmd\b|\bkg\b|\bkilos\b", t):
            return self._pesaje(tag)

        # Ocupación y rotación de potreros (Voisin)
        if re.search(r"\b(?:ocupaci[oó]n|dias\s+de\s+ocupaci[oó]n|tiempo\s+de\s+ocupaci[oó]n|rotaci[oó]n|rotacion\s+de\s+potreros|rotacion\s+voisin)\b", t):
            return self._ocupacion_potreros()

        # Existencias por potrero en formato Software Ganadero (SG)
        if re.search(r"\b(?:existencias?\s+por\s+potreros?|tabla\s+de\s+potreros?|potreros?\s+sg|potreros?\s+software\s+ganadero)\b", t) or (
            re.search(r"\bpotrero", t) and re.search(r"\b(?:existencias?|sg|categor[ií]as?)\b", t)
        ):
            return self._inventario_potreros(formato_sg=True)

        # 8. Inventario / conteos (consultas diarias: total ganado, total vacas, novillas, inventario potreros) — incluye typo gaando
        if re.search(r"\b(?:total|totales|inventario|cuantos?|cuantas?|cuanto)\b", t) or re.search(r"\bganad", t) or re.search(r"\bga+ndo\b", t):
            # inventario por potrero tiene prioridad si menciona potrero
            if re.search(r"\bpotrero", t):
                # "inventario potreros" o "total por potrero"
                if re.search(r"\b(?:total|inventario|listar|mostrar|resumen|conteo|distribuci[oó]n)\b", t):
                    mostrar_vacios = bool(re.search(r"\bvac[ií]os?\b", t))
                    return self._inventario_potreros(mostrar_vacios=mostrar_vacios)
            # conteos de ganado por categoría (ganado, gaando typo, animal, inventario)
            if re.search(r"\b(?:ganado|ganad|ga+ndo|animal|inventario)\b", t) or re.search(r"\btotal\b.*\b(?:vaca|toro|terner|novill)", t) or re.search(r"\b(?:vaca|toro|terner|novill).*\btotal\b", t):
                # si menciona categoría específica, delegar con filtro
                if re.search(r"\bterner", t):
                    return self._inventario_categoria("terneros")
                if re.search(r"\bnovill", t):
                    return self._inventario_categoria("novillas")
                if re.search(r"\bvaca", t):
                    return self._inventario_categoria("vacas")
                if re.search(r"\btoro", t):
                    return self._inventario_categoria("toros")
                return self._inventario_general()
            # fallback para "total ganado" con typo gaando / ga+ndo
            if re.search(r"\bga+ndo\b", t) or re.search(r"\bga+n?ado\b", t):
                return self._inventario_general()
        if re.search(r"\bpotrero", t) and re.search(r"\bvac[ií]os?\b", t):
            return self._inventario_potreros(mostrar_vacios=True)
        if re.search(r"\bpotrero", t) and re.search(r"\blisto|pastoreo|pastar", t):
            return self._potreros_listos()
        if re.search(r"\bpotrero", t):
            es_consulta_potrero = bool(
                re.search(
                    r"\b(?:que\s+vacas?|que\s+animales?|cuantas?|cuantos?|listar|mostrar|animales\s+en|vacas?\s+en|hay\s+en|est[aá]n?\s+en)\b",
                    t,
                )
                or re.match(r"^\s*(?:consulta\s+|ver\s+|buscar\s+)?potreros?\s+[a-z0-9\s\-]+$", t)
            )
            nom_pot = extraer_nombre_potrero(texto)
            if (es_consulta_potrero and nom_pot) or (nom_pot and not tag):
                return self._animales_en_potrero(nom_pot)
        # Ficha directa por arete o nombre corto (ej. "N069", "JA26", "patricia", "47")
        if tag and len(t.split()) <= 2 and not re.search(r"\b(?:pari|murio|insemin|celo|peso|retiro|potrero|foto|total|inventario|vacas|toros|terneros|novillas)\b", t):
            return self._historial(tag)

        # Fallback: consulta por nombre de potrero sin la palabra "potrero" (ej. "cuantos hay en olegario 1")
        if re.search(r"\b(?:que\s+vacas?|que\s+animales?|cuantas?|cuantos?|hay|estan?|est[aá]n|listar|mostrar)\b", t):
            potreros = self.db.query("SELECT nombre, codigo FROM potreros")
            for p in potreros:
                for campo in (p["nombre"], p["codigo"]):
                    if not campo:
                        continue
                    for var in _potrero_variantes(normalizar(campo)):
                        # Coincidencia de palabra completa para evitar que código '06' matchee dentro de 'n069'
                        if var and re.search(rf"\b{re.escape(var)}\b", t):
                            return self._animales_en_potrero(campo)

        # Si el mensaje es solo el nombre exacto de un potrero (ej. "olegario 1" o "olegario 1?" )
        if len(t.split()) <= 3:
            t_clean = re.sub(r"[?!.,;:¿¡]+$", "", t.strip())
            potreros = self.db.query("SELECT nombre, codigo FROM potreros")
            for p in potreros:
                for campo in (p["nombre"], p["codigo"]):
                    if not campo:
                        continue
                    for var in _potrero_variantes(normalizar(campo)):
                        if var and var == t_clean:
                            return self._animales_en_potrero(campo)
        if re.search(r"\bfoto[s]?\b|\bimagen(?:es)?\b", t):
            return self._fotos(tag)
        if re.search(r"\bpari[oó]\b|\bparto\b", t):
            return self._ultimo_parto(tag)
        if tag and len(t.split()) <= 3 and not re.search(r"\b(?:pari|murio|insemin|celo|peso|retiro|potrero|foto)\b", t):
            return self._historial(tag)
        return self._ayuda(texto)

    # ------------------------------------------------------------------ #
    def _ubicacion_animal(self, tag) -> str:
        if not tag:
            return "¿De cuál animal desea consultar la ubicación? (ej. '¿en qué potrero está patricia?')"
        aid = self.db.resolve_animal(tag)
        if aid is None:
            return f"No se encontró el animal '{tag}' en los registros."
        animal = self.db.get_animal(aid)
        if not animal:
            return f"No se encontró el animal '{tag}' en los registros."

        tag_str = animal["tag"] or str(tag)
        nombre = f" ({animal['nombre']})" if animal["nombre"] else ""
        estado = animal["estado"] or "ACTIVO"

        potrero_nom = None
        lote_str = ""
        fecha_ingreso = None

        if animal["potrero_id"]:
            prow = self.db.query_one("SELECT nombre, codigo FROM potreros WHERE id = ?", (animal["potrero_id"],))
            if prow:
                potrero_nom = prow["nombre"] or prow["codigo"]

        ult_traslado = self.db.query_one(
            "SELECT * FROM traslados WHERE animal_id = ? ORDER BY fecha DESC LIMIT 1", (aid,)
        )
        if ult_traslado:
            if not potrero_nom and ult_traslado["potrero_destino"]:
                prow = self.db.query_one("SELECT nombre, codigo FROM potreros WHERE id = ?", (ult_traslado["potrero_destino"],))
                if prow:
                    potrero_nom = prow["nombre"] or prow["codigo"]
            if ult_traslado["lote"]:
                lote_str = f" (Lote {ult_traslado['lote']})"
            if ult_traslado["fecha"]:
                fecha_ingreso = ult_traslado["fecha"]

        if not potrero_nom:
            return f"El animal {tag_str}{nombre} (Estado: {estado}) no tiene potrero asignado actualmente."

        dias_en_potrero = ""
        if fecha_ingreso and to_date(fecha_ingreso):
            dias_p = (self.hoy - to_date(fecha_ingreso)).days
            if dias_p >= 0:
                dias_en_potrero = f" (hace {dias_p} días)"
        detalle_fecha = f" desde el {fecha_ingreso}{dias_en_potrero}" if fecha_ingreso else ""
        return f"🌱 El animal {tag_str}{nombre} se encuentra actualmente en el potrero <b>{potrero_nom}</b>{lote_str}{detalle_fecha}. Estado: {estado}."

    def _ultimo_traslado(self, tag) -> str:
        if not tag:
            return "¿De cuál animal desea consultar los traslados? (ej. '¿cuándo se movió patricia?')"
        aid = self.db.resolve_animal(tag)
        if aid is None:
            return f"No se encontró el animal '{tag}' en los registros."
        animal = self.db.get_animal(aid)
        if not animal:
            return f"No se encontró el animal '{tag}' en los registros."

        tag_str = animal["tag"] or str(tag)
        nombre = f" ({animal['nombre']})" if animal["nombre"] else ""

        traslados = self.db.query(
            "SELECT * FROM traslados WHERE animal_id = ? ORDER BY fecha DESC, id DESC LIMIT 5",
            (aid,),
        )
        if not traslados:
            if animal["potrero_id"]:
                prow = self.db.query_one("SELECT nombre, codigo FROM potreros WHERE id = ?", (animal["potrero_id"],))
                pnom = prow["nombre"] or prow["codigo"] if prow else f"Potrero {animal['potrero_id']}"
                return f"🌱 {tag_str}{nombre} se encuentra asignada al potrero <b>{pnom}</b> (no registra fecha de traslado histórica)."
            return f"No hay registros de traslados para {tag_str}{nombre}."

        ult = traslados[0]
        fec = ult["fecha"] or "sin fecha"
        p_dest_nom = "Desconocido"
        if ult["potrero_destino"]:
            prow = self.db.query_one(
                "SELECT nombre, codigo FROM potreros WHERE id = ? OR codigo = ? OR nombre = ?",
                (ult["potrero_destino"], ult["potrero_destino"], ult["potrero_destino"]),
            )
            if not prow:
                p_obj = self._buscar_potrero(str(ult["potrero_destino"]))
                if p_obj:
                    prow = p_obj
            if prow:
                p_dest_nom = prow["nombre"] or prow["codigo"] or str(ult["potrero_destino"])
            else:
                p_dest_nom = str(ult["potrero_destino"])

        p_orig_nom = None
        if ult["potrero_origen"]:
            prow_o = self.db.query_one(
                "SELECT nombre, codigo FROM potreros WHERE id = ? OR codigo = ? OR nombre = ?",
                (ult["potrero_origen"], ult["potrero_origen"], ult["potrero_origen"]),
            )
            if not prow_o:
                p_obj_o = self._buscar_potrero(str(ult["potrero_origen"]))
                if p_obj_o:
                    prow_o = p_obj_o
            if prow_o:
                p_orig_nom = prow_o["nombre"] or prow_o["codigo"] or str(ult["potrero_origen"])
            else:
                p_orig_nom = str(ult["potrero_origen"])

        orig_str = f" desde <b>{p_orig_nom}</b>" if p_orig_nom else ""
        lote_str = f" (Lote {ult['lote']})" if ult["lote"] else ""

        dias_str = ""
        if ult["fecha"] and to_date(ult["fecha"]):
            dias = (self.hoy - to_date(ult["fecha"])).days
            if dias >= 0:
                dias_str = f" · Ocupación actual: <b>{dias} días</b>"

        resp = (
            f"🚚 <b>Último traslado de {tag_str}{nombre}:</b>\n"
            f"• Fecha: <b>{fec}</b>\n"
            f"• Movido a: <b>{p_dest_nom}</b>{orig_str}{lote_str}\n"
            f"• Estado: {animal['estado'] or 'ACTIVO'}{dias_str}"
        )
        return resp

    def _ultimo_parto(self, tag) -> str:
        if not tag:
            return "¿De cuál animal desea saber el parto? (ej. '¿cuándo parió la 47?')"
        aid = self.db.resolve_animal(tag)
        if aid is None:
            return f"No hay registro de parto para la {tag}."
        animal = self.db.get_animal(aid)
        tag_str = animal["tag"] if animal else str(tag)
        nombre = f" ({animal['nombre']})" if animal and animal["nombre"] else ""

        parto = self.db.ultimo_parto(aid)
        if parto is None:
            return f"No hay registro de parto para la {tag_str}{nombre}."
        fec = parto["fecha"]
        cria_info = []
        if parto["sexo_cria"]:
            cria_info.append(f"Cría {parto['sexo_cria']}")
        if parto["estado_cria"]:
            cria_info.append(parto["estado_cria"])
        if parto["peso_nacimiento"]:
            cria_info.append(f"{parto['peso_nacimiento']} kg")
        str_cria = f" ({', '.join(cria_info)})" if cria_info else ""
        return f"La {tag_str}{nombre} parió el {fec}{str_cria}."

    def _ultimo_servicio(self, tag) -> str:
        if not tag:
            return "¿De cuál animal desea consultar el servicio? (ej. '¿cuándo se inseminó la 47?')"
        aid = self.db.resolve_animal(tag)
        if aid is None:
            return f"No hay servicio registrado para '{tag}'."
        animal = self.db.get_animal(aid)
        tag_str = animal["tag"] if animal else str(tag)
        nombre = f" ({animal['nombre']})" if animal and animal["nombre"] else ""

        serv = self.db.ultimo_servicio(aid)
        if serv is None:
            return f"No hay servicio ni inseminación registrada para {tag_str}{nombre}."
        fec = serv["fecha"]
        toro_str = f" con toro/pajuela {serv['toro_pajilla']}" if ("toro_pajilla" in serv.keys() and serv["toro_pajilla"]) else ""
        tipo_str = f" ({serv['tipo_servicio']})" if serv["tipo_servicio"] else ""
        fep = serv["fep_calculada"] or iso(add_days(serv["fecha"], 283))
        dias_gest = (self.hoy - to_date(fec)).days if to_date(fec) else 0

        return (
            f"🐂 {tag_str}{nombre} fue servida el <b>{fec}</b>{toro_str}{tipo_str}.\n"
            f"• Días de gestación calculados: {dias_gest} días\n"
            f"• Fecha Estimada de Parto (FEP): <b>{fep}</b>"
        )

    def _genealogia(self, tag) -> str:
        if not tag:
            return "¿De cuál animal desea consultar la genealogía? (ej. '¿quién es la madre de patricia?')"
        aid = self.db.resolve_animal(tag)
        if aid is None:
            return f"No se encontró el animal '{tag}' en los registros."
        animal = self.db.get_animal(aid)
        if not animal:
            return f"No se encontró el animal '{tag}' en los registros."

        tag_str = animal["tag"] or str(tag)
        nombre = f" ({animal['nombre']})" if animal["nombre"] else ""

        madre_str = "Desconocida"
        if animal["madre_id"]:
            m_row = self.db.get_animal(animal["madre_id"])
            if m_row:
                madre_str = m_row["tag"] + (f" ({m_row['nombre']})" if m_row["nombre"] else "")

        padre_str = "Desconocido"
        if animal["padre_id"]:
            p_row = self.db.get_animal(animal["padre_id"])
            if p_row:
                padre_str = p_row["tag"] + (f" ({p_row['nombre']})" if p_row["nombre"] else "")

        crias = self.db.query(
            "SELECT a.tag, a.nombre, a.sexo, p.fecha FROM partos p "
            "LEFT JOIN animales a ON a.id_animal = p.id_cria "
            "WHERE p.vaca_id = ? AND (p.id_cria IS NULL OR p.id_cria != ?) ORDER BY p.fecha DESC",
            (aid, aid),
        )
        crias_str = f"{len(crias)} partos registrados"
        if crias:
            crias_desc = []
            for c in crias[:3]:
                c_tag = c["tag"] or "Sin arete"
                c_fec = f" ({c['fecha']})" if c["fecha"] else ""
                crias_desc.append(f"{c_tag}{c_fec}")
            crias_str += f" [{', '.join(crias_desc)}]"

        return (
            f"🌳 <b>Genealogía de {tag_str}{nombre}</b>\n"
            f"• Madre: <b>{madre_str}</b>\n"
            f"• Padre: <b>{padre_str}</b>\n"
            f"• Crías: {crias_str}"
        )

    def _retiro_animal(self, tag) -> str:
        if not tag:
            return self._en_retiro()
        aid = self.db.resolve_animal(tag)
        if aid is None:
            return f"No se encontró el animal '{tag}'."
        animal = self.db.get_animal(aid)
        tag_str = animal["tag"] if animal else str(tag)
        nombre = f" ({animal['nombre']})" if animal and animal["nombre"] else ""

        tratamientos = self.db.query(
            "SELECT * FROM tratamientos WHERE animal_id = ? ORDER BY fecha DESC LIMIT 5", (aid,)
        )
        if not tratamientos:
            return f"✅ {tag_str}{nombre} no tiene tratamientos registrados. Está libre de retiro."

        hoy = self.hoy
        bloqueos = []
        for t in tratamientos:
            for tipo, fin in (
                ("leche", t["fecha_fin_retiro_leche"]),
                ("carne", t["fecha_fin_retiro_carne"]),
            ):
                if fin and to_date(fin) and to_date(t["fecha"]) <= hoy <= to_date(fin):
                    dias_rest = (to_date(fin) - hoy).days
                    prod = t["producto"] or "Fármaco"
                    bloqueos.append(f"⚠️ Retiro de {tipo} por {prod} hasta el {fin} (faltan {dias_rest} días)")

        if bloqueos:
            return f"💊 <b>Tratamiento en {tag_str}{nombre}</b>:\n" + "\n".join(bloqueos)
        return f"✅ {tag_str}{nombre} no tiene retiros activos actualmente. Está libre para consumo/ordeño."

    def _palpacion_pendiente(self) -> str:
        hoy = self.hoy
        servicios = self.db.query("SELECT * FROM servicios WHERE fecha IS NOT NULL ORDER BY fecha")
        pendientes = []
        for s in servicios:
            palp = fecha_palpacion(s["fecha"])
            if palp is None or palp < hoy:
                continue
            confirmado = self.db.query_one(
                "SELECT id FROM partos WHERE vaca_id = ? AND fecha >= ? LIMIT 1",
                (s["vaca_id"], s["fecha"]),
            )
            if confirmado:
                continue
            tag = self._tag_de(s["vaca_id"])
            pendientes.append(f"{tag} (palpación el {iso(palp)})")
        if not pendientes:
            return "No hay vacas con palpación pendiente."
        return "Vacas con palpación pendiente: " + "; ".join(pendientes) + "."

    def _inseminacion_programada(self) -> str:
        alertas = self.db.query(
            "SELECT a.fecha_programada, a.descripcion, a.animal_id, an.tag AS tag "
            "FROM alertas a LEFT JOIN animales an ON an.id_animal = a.animal_id "
            "WHERE a.tipo_alerta = 'INSEMINACION_PROGRAMADA' AND a.estado = 'PENDIENTE' "
            "ORDER BY a.fecha_programada"
        )
        pendientes = []
        for a in alertas:
            tag = a["tag"] or (self._tag_de(a["animal_id"]) if a["animal_id"] else "?")
            franja = self._franja_inseminacion(a["descripcion"])
            detalle = f"{tag} (el {a['fecha_programada']}"
            if franja:
                detalle += f", {franja}"
            detalle += ")"
            pendientes.append(detalle)
        if not pendientes:
            return "No hay vacas pendientes de inseminación."
        return "Vacas para inseminar: " + "; ".join(pendientes) + "."

    def _franja_inseminacion(self, descripcion) -> str:
        if not descripcion:
            return ""
        m = re.search(r"en la (tarde|mañana)", descripcion)
        return m.group(1) if m else ""

    def _secado(self, tag) -> str:
        if not tag:
            return "¿De cuál vaca desea saber el secado? (ej. '¿cuándo le toca el secado a la 47?')"
        servicio = self.db.ultimo_servicio(tag)
        if servicio is None:
            return f"No hay servicio registrado para la {tag}."
        fep = servicio["fep_calculada"] or iso(add_days(servicio["fecha"], 283))
        secado = fecha_secado(fep)
        return f"El secado de la {tag} es el {iso(secado)}."

    def _en_retiro(self) -> str:
        hoy = self.hoy
        tratamientos = self.db.query(
            "SELECT * FROM tratamientos WHERE dias_retiro_leche > 0 OR dias_retiro_carne > 0"
        )
        bloqueados = []
        for t in tratamientos:
            for tipo, fin in (
                ("leche", t["fecha_fin_retiro_leche"]),
                ("carne", t["fecha_fin_retiro_carne"]),
            ):
                if fin and to_date(t["fecha"]) and to_date(t["fecha"]) <= hoy <= to_date(fin):
                    tag = self._tag_de(t["animal_id"])
                    bloqueados.append(f"{tag} ({tipo} hasta {fin})")
        if not bloqueados:
            return "No hay animales en tiempo de retiro."
        return "Animales en tiempo de retiro: " + "; ".join(bloqueados) + "."

    def _historial(self, tag) -> str:
        if not tag:
            return "¿De cuál animal desea el historial? (ej. '¿cuál es el historial de la vaca 47?')"
        aid = self.db.resolve_animal(tag)
        if aid is None:
            return f"No hay registros para la {tag}."
        animal = self.db.get_animal(aid)
        if not animal:
            return f"No hay registros para la {tag}."

        tag_str = animal["tag"] or str(tag)
        nombre = f" ({animal['nombre']})" if animal["nombre"] else ""
        raza = animal["raza"] or "Sin especificar"
        sexo_raw = animal["sexo"] or ""
        estado = animal["estado"] or "ACTIVO"

        potrero_nom = "No asignado"
        if animal["potrero_id"]:
            prow = self.db.query_one("SELECT nombre, codigo FROM potreros WHERE id = ?", (animal["potrero_id"],))
            if prow:
                potrero_nom = prow["nombre"] or prow["codigo"] or "No asignado"
        else:
            ult_traslado = self.db.query_one(
                "SELECT potrero_destino FROM traslados WHERE animal_id = ? ORDER BY fecha DESC LIMIT 1", (aid,)
            )
            if ult_traslado and ult_traslado["potrero_destino"]:
                prow = self.db.query_one("SELECT nombre, codigo FROM potreros WHERE id = ?", (ult_traslado["potrero_destino"],))
                if prow:
                    potrero_nom = prow["nombre"] or prow["codigo"] or "No asignado"

        # Registro de nacimiento como cría (excluyendo autorreferencias)
        p_nac = self.db.query_one(
            "SELECT * FROM partos WHERE id_cria = ? AND (vaca_id IS NULL OR vaca_id != ?) ORDER BY fecha DESC LIMIT 1",
            (aid, aid),
        )
        if not p_nac and animal["madre_id"] and animal["madre_id"] != aid:
            p_nac = self.db.query_one(
                "SELECT * FROM partos WHERE vaca_id = ? AND (id_cria = ? OR id_cria IS NULL) ORDER BY fecha DESC LIMIT 1",
                (animal["madre_id"], aid),
            )

        # Normalización e inferencia de sexo
        sexo_norm = sexo_raw.strip().lower()
        if not sexo_norm or sexo_norm in ("i", "indefinido", "indeterminado", "desconocido", "?"):
            if p_nac and p_nac["sexo_cria"]:
                sexo_norm = p_nac["sexo_cria"].strip().lower()

        es_macho = bool(sexo_norm.startswith("m") or sexo_norm in ("macho", "toro", "ternero", "novillo", "buey"))
        es_hembra = not es_macho

        # Historial de eventos (machos no tienen partos dados por ellos ni servicios de hembra)
        h = self.db.historial(tag_str)
        def _row_get(row, key, default=None):
            try:
                return row[key]
            except Exception:
                try:
                    return row.get(key, default)  # type: ignore
                except Exception:
                    return default
        partos = [] if es_macho else [p for p in h.get("partos", []) if p["vaca_id"] != _row_get(p, "id_cria")]
        servicios = [] if es_macho else h.get("servicios", [])
        celos = [] if es_macho else h.get("celos", [])
        tratamientos = h.get("tratamientos", [])
        pesajes = h.get("pesajes", [])
        fotos = h.get("fotos", [])

        # Cálculo de fecha de nacimiento y edad
        f_nac = to_date(animal["fecha_nacimiento"])
        if not f_nac and p_nac and p_nac["fecha"]:
            f_nac = to_date(p_nac["fecha"])

        # Si aún no hay f_nac pero tiene madre_id válida, inferir desde partos recientes de la madre (<15 meses)
        if not f_nac and animal["madre_id"] and animal["madre_id"] != aid:
            ult_p_madre = self.db.query_one(
                "SELECT fecha, peso_nacimiento FROM partos WHERE vaca_id = ? AND fecha IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                (animal["madre_id"],),
            )
            if ult_p_madre and ult_p_madre["fecha"]:
                d_madre = to_date(ult_p_madre["fecha"])
                if d_madre and (self.hoy - d_madre).days <= 450:
                    f_nac = d_madre
                    if not p_nac:
                        p_nac = ult_p_madre

        edad_dias = (self.hoy - f_nac).days if f_nac else None

        # Categoría etaria / zootécnica alineada fielmente a Software Ganadero (SG)
        # Estados típicos SG:
        # - Machos: <8m CRÍA MACHO / Ternero, 8-18m LEVANTE / Novillo, 18-30m TORETE / Torete, >30m TORO / Toro
        # - Hembras con partos:
        #   - da <= 305d: VACA PARIDA (o VACA PARIDA SERVIDA / SIN PALPAR si tiene servicio)
        #   - da > 305d: VACA SECA (o VACA ESCOTERA si tiene >1 parto sin servicio)
        # - Hembras sin partos:
        #   - <12m: CRÍA HEMBRA / Ternera
        #   - 12-18m: NOVILLA LEVANTE / Novilla
        #   - >=18m: NOVILLA VIENTRE / Novilla (o NOVILLA VIENTRE SERVIDA si tiene servicio)
        if es_macho:
            if edad_dias is not None:
                if edad_dias < 243:  # < 8 meses
                    tipo_animal = "Ternero"
                    estado_reprod = "CRÍA MACHO"
                elif edad_dias < 548:  # 8 a 18 meses
                    tipo_animal = "Novillo"
                    estado_reprod = "LEVANTE"
                elif edad_dias < 913:  # 18 a 30 meses
                    tipo_animal = "Torete"
                    estado_reprod = "TORETE"
                else:  # > 30 meses
                    tipo_animal = "Toro"
                    estado_reprod = "TORO"
            else:
                # Edad desconocida: evitar clasificar como Toro reproductor
                if (animal["madre_id"] and animal["madre_id"] != aid) or p_nac:
                    tipo_animal = "Ternero"
                    estado_reprod = "CRÍA MACHO"
                else:
                    tipo_animal = "Macho joven"
                    estado_reprod = "LEVANTE / EDAD POR CONFIRMAR"
        else:
            ult_parto = partos[-1] if partos else None
            ult_servicio = servicios[-1] if servicios else None

            if partos:
                tipo_animal = "Vaca"
                f_up = to_date(ult_parto["fecha"]) if ult_parto else None
                da = (self.hoy - f_up).days if f_up else 0
                f_us = to_date(ult_servicio["fecha"]) if ult_servicio else None
                serv_post_parto = bool(f_us and f_up and f_us >= f_up)

                if da > 305:
                    if len(partos) > 1 and not serv_post_parto:
                        estado_reprod = "VACA ESCOTERA"
                    elif serv_post_parto:
                        estado_reprod = "VACA SECA SERVIDA"
                    else:
                        estado_reprod = "VACA SECA"
                else:
                    # da <= 305 días (vaca parida en lactancia activa)
                    if serv_post_parto:
                        estado_reprod = "VACA PARIDA SERVIDA / SIN PALPAR"
                    else:
                        estado_reprod = "VACA PARIDA SIN PALPAR"
            elif edad_dias is not None:
                if edad_dias < 365:  # < 12 meses
                    tipo_animal = "Ternera"
                    estado_reprod = "CRÍA HEMBRA"
                elif edad_dias < 548:  # 12 a 18 meses
                    tipo_animal = "Novilla"
                    estado_reprod = "NOVILLA LEVANTE"
                else:  # >= 18 meses (edad apta para vientre)
                    tipo_animal = "Novilla"
                    if ult_servicio:
                        estado_reprod = "NOVILLA VIENTRE SERVIDA"
                    else:
                        estado_reprod = "NOVILLA VIENTRE"
            else:
                if (animal["madre_id"] and animal["madre_id"] != aid) or p_nac:
                    tipo_animal = "Ternera"
                    estado_reprod = "CRÍA HEMBRA"
                elif ult_servicio:
                    tipo_animal = "Novilla"
                    estado_reprod = "NOVILLA VIENTRE SERVIDA"
                else:
                    tipo_animal = "Novilla"
                    estado_reprod = "NOVILLA VIENTRE"

        bloques = []

        # Encabezado
        nom_txt = f" ({animal['nombre']})" if animal["nombre"] else ""
        header = [
            "📋 <b>FICHA ZOOTÉCNICA</b>",
            f"🐄 <b>{tipo_animal} {tag_str}{nom_txt}</b>",
            f"🏷️ <b>Raza:</b> {raza}",
            f"📍 <b>Potrero:</b> {potrero_nom}",
        ]
        if f_nac:
            edad_str = formatear_edad_zootecnica(f_nac, self.hoy)
            header.append(f"🎂 <b>Edad:</b> {edad_str}")
        header.extend([
            f"● <b>Estado:</b> {estado}",
            f"🧬 <b>Reproductivo:</b> {estado_reprod}",
            "───────────────────",
        ])
        bloques.append("\n".join(header))

        # Sección Reproducción
        reprod = ["🍼 <b>REPRODUCCIÓN & PARTOS</b>"]
        if es_hembra:
            if partos:
                p = ult_parto
                cria_info = []
                if p["sexo_cria"]:
                    cria_info.append(f"Cría {p['sexo_cria'].lower()}")
                if p["peso_nacimiento"]:
                    cria_info.append(f"{p['peso_nacimiento']} kg")
                if p["id_cria"]:
                    cria_animal = self.db.get_animal(p["id_cria"])
                    if cria_animal:
                        cria_info.append(f"Arete {cria_animal['tag']}")
                cria_str = f" ({', '.join(cria_info)})" if cria_info else ""
                reprod.append(f"• partos: {len(partos)} registro(s)")
                reprod.append(f"  Último Parto: {p['fecha']}{cria_str}")

                f_parto = to_date(p["fecha"])
                if f_parto:
                    da = (self.hoy - f_parto).days
                    reprod.append(f"  Días Abiertos: {da} días (desde el último parto)")
            else:
                reprod.append("• partos: 0 registro(s).")

            if servicios:
                s = ult_servicio
                toro_info = f" (Toro/Pajilla {s['toro_pajilla']})" if s["toro_pajilla"] else ""
                tipo_srv = s["tipo_servicio"] or "IA"
                reprod.append(f"• servicios: {len(servicios)} registro(s)")
                reprod.append(f"  Último Servicio: {s['fecha']} [{tipo_srv}]{toro_info}")

                if s["fecha"]:
                    fep = s["fep_calculada"] or iso(fecha_estimada_parto(s["fecha"]))
                    f_palp = iso(fecha_palpacion(s["fecha"]))
                    f_sec = iso(fecha_secado(fep))
                    reprod.append(f"  Palpación Rectal: PENDIENTE ({f_palp}, día 60)")
                    reprod.append(f"  FEP (Fecha Estimada Parto): {fep} (+283 días)")
                    reprod.append(f"  Secado Programado: {f_sec} (FEP − 60 días)")
            else:
                reprod.append("• servicios: 0 registro(s).")

            if celos:
                c = celos[-1]
                turno = f" [{c['am_pm']}]" if c["am_pm"] else ""
                reprod.append(f"• celos: {len(celos)} registro(s)")
                reprod.append(f"  Último Celo: {c['fecha']}{turno}")
        else:
            reprod.append("• partos: 0 registro(s).")
            reprod.append("• servicios: 0 registro(s).")

        # Datos de origen / nacimiento si el animal nació en la finca o tiene madre registrada
        madre_id = animal["madre_id"] or (p_nac["vaca_id"] if p_nac else None)
        madre_tag = None
        if madre_id and madre_id != aid:
            m_animal = self.db.get_animal(madre_id)
            if m_animal and m_animal["tag"] != tag_str:
                madre_tag = m_animal["tag"]

        if f_nac or madre_tag:
            origen_parts = []
            if f_nac:
                origen_parts.append(f"Fecha: {iso(f_nac)}")
            if madre_tag:
                origen_parts.append(f"Madre: {madre_tag}")
            if p_nac and p_nac["peso_nacimiento"]:
                origen_parts.append(f"Peso al nacer: {p_nac['peso_nacimiento']} kg")
            reprod.append(f"• Origen / Nacimiento: {', '.join(origen_parts)}")

        bloques.append("\n".join(reprod))

        # Sección Pesaje & Crecimiento
        pesaje = ["⚖️ <b>PESAJE & CRECIMIENTO</b>"]
        if pesajes:
            ult_p = pesajes[-1]
            gmd_str = ""
            if len(pesajes) >= 2:
                ant_p = pesajes[-2]
                d1, d2 = to_date(ant_p["fecha"]), to_date(ult_p["fecha"])
                if d1 and d2 and (d2 - d1).days > 0 and ant_p["peso_kg"] is not None:
                    g_val = gmd(ult_p["peso_kg"], ant_p["peso_kg"], (d2 - d1).days)
                    signo = "+" if g_val >= 0 else ""
                    gmd_str = f" (GMD: {signo}{g_val:.3f} kg/día)"
            pesaje.append(f"• pesajes: {len(pesajes)} registro(s)")
            pesaje.append(f"  Último Peso: {ult_p['peso_kg']} kg el {ult_p['fecha']}{gmd_str}")
        else:
            pesaje.append("• pesajes: 0 registro(s).")
        bloques.append("\n".join(pesaje))

        # Sección Sanidad & Retiros
        sanidad = ["💉 <b>SANIDAD & RETIROS</b>"]
        if tratamientos:
            t = tratamientos[-1]
            prod = t["producto"] or "Fármaco"
            dosis = f" {t['dosis']}" if t["dosis"] else ""
            retiro_info = "Sin retiro activo"
            hoy_iso = self.hoy.isoformat()
            if t["fecha_fin_retiro_carne"] and t["fecha_fin_retiro_carne"] >= hoy_iso:
                retiro_info = f"⚠️ Retiro carne hasta {t['fecha_fin_retiro_carne']}"
            elif t["fecha_fin_retiro_leche"] and t["fecha_fin_retiro_leche"] >= hoy_iso:
                retiro_info = f"⚠️ Retiro leche hasta {t['fecha_fin_retiro_leche']}"
            sanidad.append(f"• tratamientos: {len(tratamientos)} registro(s)")
            sanidad.append(f"  Tratamiento: {prod}{dosis} ({retiro_info})")
        else:
            sanidad.append("• tratamientos: 0 registro(s) · (Sin retiro activo).")
        bloques.append("\n".join(sanidad))

        # Sección Fotos
        fotos_sec = ["📷 <b>FOTOS</b>"]
        if fotos:
            fotos_sec.append(f"• {len(fotos)} foto(s) registrada(s) (ver con /foto {tag_str})")
        else:
            fotos_sec.append("• 0 fotos registradas para este animal.")
        bloques.append("\n".join(fotos_sec))

        return "\n\n".join(bloques)

    def _pesaje(self, tag) -> str:
        if not tag:
            return "¿De cuál animal desea el peso? (ej. '¿cuánto pesó la 12?')"
        pesajes = self.db.ultimos_pesajes(tag, 2)
        if not pesajes:
            return f"No hay pesajes registrados para la {tag}."
        ultimo = pesajes[0]
        peso = ultimo["peso_kg"]
        if len(pesajes) >= 2:
            anterior = pesajes[1]
            dias = (to_date(ultimo["fecha"]) - to_date(anterior["fecha"])).days
            ganancia = gmd(peso, anterior["peso_kg"], dias)
            return (f"La {tag} pesó {peso} kg el {ultimo['fecha']} y su ganancia diaria "
                    f"fue {ganancia:.3f} kg/día.")
        return f"La {tag} pesó {peso} kg el {ultimo['fecha']}."

    def _potreros_listos(self) -> str:
        potreros = self.db.query("SELECT * FROM potreros")
        listos = []
        for p in potreros:
            # 1ª Ley de Voisin (reposo): exige reposo suficiente Y oferta forrajera.
            reposo = p["dias_reposo"]
            aforo = p["aforo_kg_m2"]
            if (reposo is not None and reposo >= REPOSO_LISTO_DIAS) and aforo:
                listos.append(p["nombre"] or p["codigo"] or str(p["id"]))
        if not listos:
            return "No hay potreros listos para pastoreo."
        return "Potreros listos para pastoreo: " + ", ".join(listos) + "."

    def _inventario_general(self) -> str:
        total = self.db.query_one("SELECT COUNT(*) as n FROM animales WHERE estado='ACTIVO'")
        n_total = int(total["n"]) if total else 0
        if n_total == 0:
            return "📊 Inventario: 0 animales activos en la finca."

        tabla_sg = generar_resumen_inventario_sg(self.db, self.hoy)
        datos = calcular_brackets_inventario_sg(self.db, self.hoy)
        n_hembras = datos["total_hembras"]
        n_machos = datos["total_machos"]
        terneros = datos["terneros_menor_12m"]

        detalle = f"🐄 Total en finca: {_fmt_es_co(n_total)} animales"
        partes = []
        if n_hembras:
            partes.append(f"{n_hembras} vacas")
        if n_machos:
            partes.append(f"{n_machos} toros")
        if partes:
            detalle += f" ({', '.join(partes)})"
        if terneros:
            detalle += f" — {terneros} terneros <12m incluidos"
        detalle += "."

        return f"{tabla_sg}\n{detalle}"

    def _inventario_categoria(self, categoria: str) -> str:
        cat = categoria.lower()
        if cat in ("vacas", "vaca"):
            row = self.db.query_one("SELECT COUNT(*) as n FROM animales WHERE estado='ACTIVO' AND UPPER(sexo)='HEMBRA'")
            n = int(row["n"]) if row else 0
            return f"🐄 Total vacas (hembras activas): {n}."
        if cat in ("toros", "toro"):
            row = self.db.query_one("SELECT COUNT(*) as n FROM animales WHERE estado='ACTIVO' AND UPPER(sexo)='MACHO'")
            n = int(row["n"]) if row else 0
            return f"🐂 Total toros (machos activos): {n}."
        if cat in ("novillas", "novilla"):
            # Novillas: hembras sin partos
            hembras = self.db.query("SELECT id_animal FROM animales WHERE estado='ACTIVO' AND UPPER(sexo)='HEMBRA'")
            count = 0
            for h in hembras:
                aid = h["id_animal"]
                has_parto = self.db.query_one("SELECT 1 FROM partos WHERE vaca_id=? AND (id_cria IS NULL OR id_cria != ?) LIMIT 1", (aid, aid))
                if not has_parto:
                    count += 1
            return f"🐄 Total novillas (hembras sin parto): {count}."
        if cat in ("terneros", "ternero", "terneras"):
            rows = self.db.query("SELECT id_animal, fecha_nacimiento, madre_id FROM animales WHERE estado='ACTIVO'")
            count = 0
            for r in rows:
                fn = to_date(r["fecha_nacimiento"])
                if not fn:
                    p = self.db.query_one(
                        "SELECT fecha FROM partos WHERE id_cria = ? AND (vaca_id IS NULL OR vaca_id != ?) ORDER BY fecha DESC LIMIT 1",
                        (r["id_animal"], r["id_animal"]),
                    )
                    if p and p["fecha"]:
                        fn = to_date(p["fecha"])
                    elif r["madre_id"] and r["madre_id"] != r["id_animal"]:
                        p_m = self.db.query_one(
                            "SELECT fecha FROM partos WHERE vaca_id = ? ORDER BY fecha DESC LIMIT 1",
                            (r["madre_id"],),
                        )
                        if p_m and p_m["fecha"]:
                            fn = to_date(p_m["fecha"])
                if fn and (self.hoy - fn).days < 365:
                    count += 1
            # Fallback si no hay fecha_nacimiento: contar crías con id_cria no nulo en partos de animales activos
            if count == 0:
                row = self.db.query_one("SELECT COUNT(DISTINCT a.id_animal) as n FROM animales a JOIN partos p ON p.id_cria = a.id_animal WHERE a.estado='ACTIVO' AND (p.vaca_id IS NULL OR p.vaca_id != p.id_cria)")
                count = int(row["n"]) if row and row["n"] else 0
            return f"🐄 Total terneros (<12 meses): {count}."
        return self._inventario_general()

    def _ocupacion_potreros(self) -> str:
        return formatear_ocupacion_potreros(self.db, self.hoy)

    def _inventario_potreros(self, mostrar_vacios: bool = False, formato_sg: bool = False) -> str:
        if formato_sg:
            filas_sg = calcular_existencias_potreros_sg(self.db, self.hoy)
            return formatear_tabla_potreros_sg(filas_sg)

        potreros = self.db.query("SELECT * FROM potreros")
        if not potreros:
            return "No hay potreros registrados."

        potreros_by_id = {p["id"]: p for p in potreros}

        # Agrupación por nombre normalizado (case-insensitive, sin duplicados)
        grupos: dict[str, dict] = {}
        for p in potreros:
            # Descartar potreros históricos/abandonados con reposo excesivo (>365d)
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
                    "total": 0,
                }
            grupos[norm]["ids"].add(p["id"])

        # Contar animales activos por potrero (usando último traslado o potrero_id)
        animales = self.db.query(
            "SELECT id_animal, potrero_id FROM animales WHERE estado = 'ACTIVO'"
        )
        for a in animales:
            aid = a["id_animal"]
            ult = self.db.query_one(
                "SELECT potrero_destino FROM traslados WHERE animal_id=? ORDER BY fecha DESC, id DESC LIMIT 1",
                (aid,),
            )
            pid = ult["potrero_destino"] if (ult and ult["potrero_destino"] is not None) else a["potrero_id"]
            if pid is not None and pid in potreros_by_id:
                p_row = potreros_by_id[pid]
                raw_nom = (p_row["nombre"] or p_row["codigo"] or str(pid)).strip()
                norm = normalizar(raw_nom).strip().upper()
                if norm in grupos:
                    grupos[norm]["total"] += 1
                else:
                    grupos[norm] = {"display": raw_nom.upper(), "ids": {pid}, "total": 1}

        ocupados = [g for g in grupos.values() if g["total"] > 0]
        vacios = [g for g in grupos.values() if g["total"] == 0]

        # Ordenar ocupados descendente por total, luego alfabéticamente
        ocupados.sort(key=lambda x: (-x["total"], x["display"]))
        # Ordenar vacíos alfabéticamente
        vacios.sort(key=lambda x: x["display"])

        if not ocupados and not vacios:
            return "No hay potreros registrados."

        def fmt_num(n: int) -> str:
            return _fmt_es_co(n)

        if mostrar_vacios:
            if not vacios:
                return (
                    f"📍 <b>Inventario por potrero — Vacíos (0)</b>\n\n"
                    f"Todos los {len(ocupados)} potreros tienen animales asignados."
                )
            pre_lines = [v["display"] for v in vacios]
            lineas = [
                f"📍 <b>Inventario por potrero — Vacíos ({len(vacios)})</b>",
                "<pre>",
                "\n".join(pre_lines),
                "</pre>",
                f"Ocupados: {len(ocupados)} (ver con /potreros o inventario potreros)",
            ]
            return "\n".join(lineas)

        if not ocupados:
            return f"📍 <b>Inventario por potrero:</b> Todos los potreros ({len(vacios)}) están vacíos."

        total_animales = sum(o["total"] for o in ocupados)
        total_str = fmt_num(total_animales)

        max_nom_w = max(len(o["display"]) for o in ocupados)
        col_w = max(max_nom_w, 18)

        pre_lines = [
            f"{'Potrero'.ljust(col_w)}  {'Nro'.rjust(4)}  {'Distrib.'.rjust(8)}",
            "─" * (col_w + 16),
        ]
        for o in ocupados:
            nom = o["display"].ljust(col_w)
            num = fmt_num(o["total"]).rjust(4)
            pct = (o["total"] / total_animales * 100.0) if total_animales > 0 else 0.0
            pct_str = f"{pct:6.2f}%"
            pre_lines.append(f"{nom}  {num}  {pct_str}")

        pre_lines.append("─" * (col_w + 16))
        pre_lines.append(f"{'Total en potreros'.ljust(col_w)}  {total_str.rjust(4)}  {'100.00%'.rjust(8)}")

        lineas = [
            f"📍 <b>Inventario por potrero — Ocupados ({len(ocupados)})</b>",
            f"<pre>\n{html.escape(chr(10).join(pre_lines))}\n</pre>",
            f"Vacíos: {len(vacios)} (ver con /potreros vacios) · Total en potreros: {total_str}",
        ]
        return "\n".join(lineas)

    def _buscar_potrero(self, nombre_potrero: str):
        if not nombre_potrero:
            return None
        potreros = self.db.query("SELECT * FROM potreros")
        target_norm = normalizar(nombre_potrero)
        target_clean = re.sub(r"^potreros?\s+", "", target_norm).strip()
        target_vars = _potrero_variantes(target_clean) | _potrero_variantes(target_norm)

        # 1. Coincidencia exacta por nombre o código normalizado (con variantes I<->1)
        for p in potreros:
            p_nom = normalizar(p["nombre"]) if p["nombre"] else ""
            p_cod = normalizar(p["codigo"]) if p["codigo"] else ""
            p_nom_clean = re.sub(r"^potreros?\s+", "", p_nom).strip()
            p_vars = _potrero_variantes(p_nom) | _potrero_variantes(p_nom_clean) | {p_cod, p_nom, p_nom_clean}
            if target_vars & p_vars:
                return p
            if target_clean in (p_nom, p_cod, p_nom_clean) or target_norm in (p_nom, p_cod, p_nom_clean):
                return p

        # 2. Coincidencia por subcadena / contenencia (con variantes)
        for p in potreros:
            p_nom = normalizar(p["nombre"]) if p["nombre"] else ""
            p_cod = normalizar(p["codigo"]) if p["codigo"] else ""
            p_nom_clean = re.sub(r"^potreros?\s+", "", p_nom).strip()
            p_variants = _potrero_variantes(p_nom) | _potrero_variantes(p_nom_clean)
            if target_vars & p_variants:
                return p
            if target_clean and (target_clean == p_nom_clean or target_clean in p_nom_clean or p_nom_clean in target_clean):
                return p
            if target_norm and (target_norm in p_nom or p_nom in target_norm):
                return p
            # check variant containment
            for tv in target_vars:
                for pv in p_variants:
                    if tv in pv or pv in tv:
                        return p

        return None

    def _animales_en_potrero(self, nombre_potrero: str) -> str:
        p_row = self._buscar_potrero(nombre_potrero)
        if not p_row:
            potreros = self.db.query("SELECT * FROM potreros")
            disponibles = [
                p["nombre"] or p["codigo"] or str(p["id"])
                for p in potreros
                if (p["nombre"] or p["codigo"])
            ]
            pot_display = nombre_potrero.strip() if nombre_potrero else "desconocido"
            if disponibles:
                return f"Potrero '{pot_display}' no existe. Potreros disponibles: {', '.join(disponibles)}."
            return f"Potrero '{pot_display}' no existe. No hay potreros registrados."

        pid = p_row["id"]
        potrero_nom = p_row["nombre"] or p_row["codigo"] or str(pid)

        animales = self.db.query(
            "SELECT id_animal, tag, potrero_id, estado, sexo, fecha_nacimiento, nombre FROM animales "
            "WHERE estado = 'ACTIVO' ORDER BY id_animal"
        )

        tags_en_potrero: list[str] = []
        animales_en_este: list[dict] = []
        for a in animales:
            aid = a["id_animal"]
            ult_traslado = self.db.query_one(
                "SELECT potrero_destino FROM traslados WHERE animal_id = ? ORDER BY fecha DESC, id DESC LIMIT 1",
                (aid,),
            )
            if ult_traslado and ult_traslado["potrero_destino"] is not None:
                p_actual = ult_traslado["potrero_destino"]
            else:
                p_actual = a["potrero_id"]

            if p_actual == pid:
                tag_str = a["tag"] or str(aid)
                tags_en_potrero.append(tag_str)
                animales_en_este.append(a)

        total = len(tags_en_potrero)
        if total == 0:
            return f"No hay animales en el potrero '{potrero_nom}'."

        palabra_animal = "animal" if total == 1 else "animales"
        if total <= 10:
            tags_str = ", ".join(tags_en_potrero)
        else:
            primeros = tags_en_potrero[:10]
            sobrantes = total - 10
            tags_str = f"{', '.join(primeros)} y {sobrantes} más"

        resumen_base = f"🐄 Potrero '{potrero_nom}': {total} {palabra_animal} ({tags_str})"

        # Conteo por categorías zootécnicas Software Ganadero (SG)
        conteo_cat: dict[str, int] = {
            "Crías hembra (<1a)": 0,
            "Hembras levante (1-2a)": 0,
            "Novillas vientre (>2a)": 0,
            "Vacas paridas": 0,
            "Vacas secas": 0,
            "Crías macho (<1a)": 0,
            "Machos levante (1-2a)": 0,
            "Machos ceba": 0,
            "Toros reproductores": 0,
        }
        for a in animales_en_este:
            aid = a["id_animal"]
            sexo = (a["sexo"] or "").strip().lower()
            fnac = to_date(a["fecha_nacimiento"])
            edad_d = (self.hoy - fnac).days if fnac else None
            es_h = bool(sexo.startswith("h") or sexo.startswith("f") or sexo in ("vaca", "novilla", "ternera"))

            if es_h:
                if edad_d is not None and edad_d < 365:
                    conteo_cat["Crías hembra (<1a)"] += 1
                elif edad_d is not None and edad_d < 730:
                    conteo_cat["Hembras levante (1-2a)"] += 1
                else:
                    p_ult = self.db.ultimo_parto(aid)
                    if p_ult and p_ult["fecha"] and to_date(p_ult["fecha"]):
                        dp = (self.hoy - to_date(p_ult["fecha"])).days
                        if dp <= 305:
                            conteo_cat["Vacas paridas"] += 1
                        else:
                            conteo_cat["Vacas secas"] += 1
                    else:
                        conteo_cat["Novillas vientre (>2a)"] += 1
            else:
                nom_m = (a["nombre"] or "").upper()
                if "REPRODUCTOR" in nom_m or "PADRON" in nom_m or "TORO" in nom_m or (edad_d is not None and edad_d >= 1095):
                    conteo_cat["Toros reproductores"] += 1
                elif edad_d is not None and edad_d < 365:
                    conteo_cat["Crías macho (<1a)"] += 1
                elif edad_d is not None and edad_d < 730:
                    conteo_cat["Machos levante (1-2a)"] += 1
                else:
                    conteo_cat["Machos ceba"] += 1

        cats_activas = [f"• {k}: {v}" for k, v in conteo_cat.items() if v > 0]
        if cats_activas and total > 1:
            detalle_cat = "\n\n📋 <b>Composición zootécnica:</b>\n" + "\n".join(cats_activas)
            return f"{resumen_base}{detalle_cat}"

        return resumen_base

    def _fotos(self, tag) -> str:
        if not tag:
            fotos = self.db.ultimas_fotos(5)
            if not fotos:
                return "No hay fotos registradas en la bitácora."
            tags = [f["tag"] or "?" for f in fotos]
            return f"Hay {len(fotos)} fotos recientes (animales: {', '.join(tags)}). Usa /fotos para verlas."
        fotos = self.db.fotos_de(tag, 5)
        if not fotos:
            return f"No hay fotos registradas para la {tag}."
        return f"Hay {len(fotos)} foto(s) de la {tag}. Puedes verlas con el comando /foto {tag}."

    def _ayuda(self, texto: str = "") -> str:
        t = texto.strip() if texto else ""
        if t:
            return f"❓ No entendí \"{t}\".\n\n¿Querías alguna de estas?"
        return "❓ No entendí la consulta.\n\n¿Querías alguna de estas?"

    def sugerencias_fallback(self, texto: str = "") -> list[tuple[str, str]]:
        """Devuelve una lista de tuplas (texto_boton, callback_data) con opciones recomendadas."""
        return [
            ("🐄 Inventario", "cmd:inventario"),
            ("📋 Historial", "cmd:historial"),
            ("❓ Comandos", "cmd:ayuda"),
        ]

    def _tag_de(self, animal_id) -> str:
        row = self.db.query_one("SELECT tag FROM animales WHERE id_animal = ?", (animal_id,))
        return row["tag"] if row else str(animal_id)
