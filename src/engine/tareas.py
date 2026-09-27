"""Listas de trabajo del día (PWA): qué hay que hacer hoy en la finca.

Cada lista recorre el hato ACTIVO completo por tipo de tarea; la PWA las
agrupa por potrero para ir a trabajar. Reglas comunes:

- Solo animales ``estado='ACTIVO'``.
- Los datos viejos no generan tareas: en reproducción solo cuentan hembras
  con algún dato del último año (las demás van a ``chequeo``) y las listas
  por edad usan ventanas acotadas.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta
from typing import Any, Optional

try:
    from .dashboard_data import (
        POTRERO_ACTUAL_EXPR,
        SIN_POTRERO_LABEL,
        SQL_VIENTRES_ACTIVOS,
        ULT_TRASLADO_CTE,
        Database,
        _estado_reproductivo_vigente,
        _filas_dict,
        to_date_safe,
    )
except ImportError:  # ejecución directa
    from src.engine.dashboard_data import (  # type: ignore
        POTRERO_ACTUAL_EXPR,
        SIN_POTRERO_LABEL,
        SQL_VIENTRES_ACTIVOS,
        ULT_TRASLADO_CTE,
        Database,
        _estado_reproductivo_vigente,
        _filas_dict,
        to_date_safe,
    )

logger = logging.getLogger(__name__)

# --- Umbrales (reglas de negocio) -------------------------------------------
GESTACION = 283
DIAS_DATO_VIGENTE = 365
DIAS_PALPAR_MIN = 35
DIAS_SECAR = 220
DIAS_GESTACION_MAX = 300
DIAS_SERVIR_POSPARTO = 45
DIAS_SERVICIO_RECIENTE = 21
DIAS_PARTO_PROXIMO = 30
DIAS_DEBIO_PARIR_MAX = 90
CICLO_CELO = 21
CICLOS_CELO_MAX = 4
CELO_VENTANA = (-1, 3)
SERVICIOS_REPETIDORA = 3
DIAS_ABIERTA_PROBLEMA = 150
EDAD_ADULTA_DIAS = 450
EDAD_NOVILLA_MAX = 1095  # > 3 años sin datos: vaca con historial perdido -> chequeo
PESO_ENTORE_KG = 300
EDAD_DESTETE = (240, 365)
EDAD_TOPIZAR = (30, 120)
EDAD_CASTRAR = (90, 365)
EDAD_MARCAR = (180, 730)
EDAD_BRUCELOSIS = (90, 240)
DIAS_TRATAMIENTO_SEGUIMIENTO = 7
DIAS_RETIRO_PROXIMO = 7
DEL_ALTO = (305, 600)
DIAS_PAUSA_LARGA = 15
DIAS_PESAJE_RECIENTE = 180
GMD_MIN_KG = 0.30
PESO_VENTA_KG = 400
EDAD_DESCARTE_DIAS = 3650
DIAS_SIN_PARTO_DESCARTE = 730
CAMBIOS_CATEGORIA = (365, 730)
DIAS_CAMBIO_CATEGORIA = 30
CACHE_SEGUNDOS = 60

CLAVES = (
    "chequeo", "palpar", "secar", "servir", "novillas", "partos", "celos", "repetidoras",
    "destetar", "topizar", "castrar", "marcar", "vac_brucelosis", "vac_aftosa",
    "tratamientos", "del_alto", "pausas", "bajo_peso", "venta", "descarte", "categoria",
)

_RE_REPRODUCTOR = re.compile(r"\b(?:TORO|REPRODUCTOR|PADRON|SEMEN|PAJILLA)\b")
_cache: dict[tuple, tuple[float, dict]] = {}


def invalidar_cache() -> None:
    """Se llama tras registrar eventos (``/api/sync``)."""
    _cache.clear()


def _es_hembra(sexo: Any) -> bool:
    s = str(sexo or "").strip().lower()
    return s.startswith("h") or s.startswith("f")


def _es_macho(sexo: Any) -> bool:
    return str(sexo or "").strip().lower().startswith("m")


def _es_reproductor(a: dict) -> bool:
    return bool(_RE_REPRODUCTOR.search(f"{a.get('nombre') or ''} {a.get('notas') or ''}".upper()))


def _ultimo_dato_reproductivo(r) -> tuple[Optional[date], Optional[str]]:
    """Fecha y tipo del evento reproductivo más reciente de un vientre."""
    candidatos = [
        (to_date_safe(r["ult_parto"]), "Parto"),
        (to_date_safe(r["ult_serv_fecha"]), "Servicio"),
        (to_date_safe(r["ult_diag_fecha"]), "Diagnóstico"),
        (to_date_safe(r["ult_celo_fecha"]), "Celo"),
    ]
    candidatos = [c for c in candidatos if c[0]]
    if not candidatos:
        return None, None
    return max(candidatos, key=lambda c: c[0])


def _estado_actual(r) -> str:
    """Estado reproductivo teniendo en cuenta un parto posterior al último
    servicio/diagnóstico: en ese caso la vaca está ``PARIDA`` (vacía)."""
    ult_parto = to_date_safe(r["ult_parto"])
    refs = [d for d in (to_date_safe(r["ult_serv_fecha"]), to_date_safe(r["ult_diag_fecha"])) if d]
    if ult_parto and (not refs or ult_parto >= max(refs)):
        return "PARIDA"
    return _estado_reproductivo_vigente(r)


def _dias_gestacion_estimados(r, hoy: date) -> Optional[int]:
    """Gestación estimada hoy: diagnóstico positivo con días + lo transcurrido,
    o, si no trae días, los días desde el último servicio."""
    diag_f = to_date_safe(r["ult_diag_fecha"])
    dias_diag = r["ult_diag_dias"]
    if diag_f and dias_diag:
        try:
            return int(dias_diag) + (hoy - diag_f).days
        except (TypeError, ValueError):
            pass
    serv_f = to_date_safe(r["ult_serv_fecha"])
    if serv_f and (diag_f is None or serv_f <= diag_f):
        return (hoy - serv_f).days
    return None


def _ciclo_aftosa(hoy: date) -> tuple[date, str]:
    if hoy.month <= 6:
        return date(hoy.year, 1, 1), f"{hoy.year}-I"
    return date(hoy.year, 7, 1), f"{hoy.year}-II"


def _vacio() -> dict[str, Any]:
    return {k: [] for k in CLAVES}


def _cargar(db: Database) -> dict[str, Any]:
    """Todas las lecturas en pocas consultas (sin N+1 por animal)."""
    animales = _filas_dict(db.query(f"""
        WITH {ULT_TRASLADO_CTE}
        SELECT a.id_animal, a.tag, a.nombre, a.sexo, a.fecha_nacimiento, a.hierro, a.notas,
               a.madre_id, m.tag AS madre, pt.nombre AS potrero
        FROM animales a
        LEFT JOIN animales m ON m.id_animal = a.madre_id
        LEFT JOIN ult_traslado ut ON ut.animal_id = a.id_animal AND ut.rn = 1
        LEFT JOIN potreros pt ON pt.id = {POTRERO_ACTUAL_EXPR}
        WHERE a.estado = 'ACTIVO'"""))
    manejos: dict[int, dict[str, str]] = {}
    for r in db.query("SELECT animal_id, tipo, MAX(fecha) f FROM manejos GROUP BY animal_id, tipo"):
        manejos.setdefault(r["animal_id"], {})[r["tipo"]] = r["f"] or ""
    # Vacunas registradas antes como tratamiento (producto/diagnóstico).
    for r in db.query(
        "SELECT animal_id, fecha, LOWER(COALESCE(producto,'') || ' ' || COALESCE(diagnostico,'')) txt "
        "FROM tratamientos WHERE txt LIKE '%aftosa%' OR txt LIKE '%brucel%'"
    ):
        tipo = "VACUNA_AFTOSA" if "aftosa" in r["txt"] else "VACUNA_BRUCELOSIS"
        m = manejos.setdefault(r["animal_id"], {})
        if (r["fecha"] or "") > m.get(tipo, ""):
            m[tipo] = r["fecha"] or ""
    pesos: dict[int, list] = {}
    for r in db.query(
        "SELECT animal_id, fecha, peso_kg FROM (SELECT animal_id, fecha, peso_kg, "
        "ROW_NUMBER() OVER (PARTITION BY animal_id ORDER BY fecha DESC, id DESC) rn "
        "FROM pesajes WHERE peso_kg IS NOT NULL) WHERE rn <= 2"
    ):
        pesos.setdefault(r["animal_id"], []).append((to_date_safe(r["fecha"]), float(r["peso_kg"])))
    servicios: dict[int, list[date]] = {}
    for r in db.query("SELECT vaca_id, fecha FROM servicios WHERE fecha IS NOT NULL"):
        f = to_date_safe(r["fecha"])
        if f:
            servicios.setdefault(r["vaca_id"], []).append(f)
    return {
        "animales": animales,
        "vientres": _filas_dict(db.query(SQL_VIENTRES_ACTIVOS)),
        "secados": {r["animal_id"]: r["f"] for r in db.query(
            "SELECT animal_id, MAX(fecha) f FROM secados GROUP BY animal_id")},
        "destetados": {r["animal_id"] for r in db.query("SELECT DISTINCT animal_id FROM destetes")},
        "manejos": manejos,
        "pesos": pesos,
        "servicios": servicios,
        "pausas": _filas_dict(db.query(
            "SELECT animal_id, fecha_inicio, motivo FROM pausas_ordeno WHERE fecha_fin IS NULL")),
        "tratamientos": _filas_dict(db.query(
            "SELECT animal_id, fecha, producto, fecha_fin_retiro_leche, fecha_fin_retiro_carne "
            "FROM tratamientos ORDER BY fecha DESC")),
    }


def _reproduccion(out: dict, datos: dict, info: dict, hoy: date) -> None:
    for r in datos["vientres"]:
        aid = r["id_animal"]
        a = info.get(aid)
        if not a:
            continue
        base = a["base"]
        edad = a["edad"]
        n_partos = int(r["n_partos"] or 0)
        if not (n_partos > 0 or edad is None or edad >= EDAD_ADULTA_DIAS):
            continue
        f_dato, tipo_dato = _ultimo_dato_reproductivo(r)
        vigente = f_dato is not None and (hoy - f_dato).days <= DIAS_DATO_VIGENTE
        peso = a["peso"]
        if not vigente:
            if f_dato is None and n_partos == 0 and edad is not None and edad <= EDAD_NOVILLA_MAX:
                # Novilla nunca servida: no es un dato viejo, está por entorar.
                if peso is None or peso >= PESO_ENTORE_KG:
                    out["novillas"].append({**base, "edad_dias": edad, "peso_kg": peso})
                continue
            out["chequeo"].append({**base, "ultimo_dato": tipo_dato,
                                   "fecha_ultimo_dato": f_dato.isoformat() if f_dato else None})
            continue

        estado = _estado_actual(r)
        serv_f = to_date_safe(r["ult_serv_fecha"])
        ult_parto = to_date_safe(r["ult_parto"])
        posparto = (hoy - ult_parto).days if ult_parto else None
        serv_desde_parto = [f for f in datos["servicios"].get(aid, []) if not ult_parto or f > ult_parto]

        # Repetidoras: muchos servicios sin preñez o vacía mucho tiempo.
        motivos_rep = []
        if estado != "PRENADA" and len(serv_desde_parto) >= SERVICIOS_REPETIDORA:
            motivos_rep.append(f"{len(serv_desde_parto)} servicios sin preñez")
        if estado in ("ABIERTA", "PARIDA") and n_partos and posparto and posparto > DIAS_ABIERTA_PROBLEMA:
            motivos_rep.append(f"{posparto} d vacía posparto")
        if motivos_rep:
            out["repetidoras"].append({**base, "motivo": " · ".join(motivos_rep)})
        a["repetidora"] = bool(motivos_rep)
        a["estado_repro"] = estado
        a["posparto"] = posparto

        if estado == "EN_ESPERA" and serv_f and (hoy - serv_f).days >= DIAS_PALPAR_MIN:
            out["palpar"].append({**base, "fecha_servicio": r["ult_serv_fecha"],
                                  "toro": r["ult_serv_toro"], "dias": (hoy - serv_f).days})

        if estado in ("PRENADA", "EN_ESPERA"):
            gest = _dias_gestacion_estimados(r, hoy)
            if gest is not None:
                faltan = GESTACION - gest
                if estado == "PRENADA" or faltan <= DIAS_PARTO_PROXIMO:
                    if 0 <= faltan <= DIAS_PARTO_PROXIMO:
                        out["partos"].append({**base, "fep": (hoy + timedelta(days=faltan)).isoformat(),
                                              "en_dias": faltan, "estado": "PROXIMO"})
                    elif -DIAS_DEBIO_PARIR_MAX <= faltan < 0:
                        out["partos"].append({**base, "fep": (hoy + timedelta(days=faltan)).isoformat(),
                                              "en_dias": faltan, "estado": "ATRASADO"})
            if estado == "PRENADA" and gest is not None and DIAS_SECAR <= gest < DIAS_GESTACION_MAX:
                ult_sec = to_date_safe(datos["secados"].get(aid))
                ref = max([d for d in (ult_parto, to_date_safe(r["ult_diag_fecha"])) if d], default=None)
                if not (ult_sec and (ref is None or ult_sec >= ref)):
                    out["secar"].append({**base, "dias_gestacion": gest,
                                         "fep": (hoy + timedelta(days=GESTACION - gest)).isoformat(),
                                         "dias_para_parto": max(0, GESTACION - gest)})

        if estado in ("ABIERTA", "PARIDA"):
            libre = not r["tiene_prog_ia"] and not (serv_f and (hoy - serv_f).days <= DIAS_SERVICIO_RECIENTE)
            if n_partos == 0:
                if libre and (peso is None or peso >= PESO_ENTORE_KG):
                    out["novillas"].append({**base, "edad_dias": edad, "peso_kg": peso})
            elif libre and posparto is not None and posparto > DIAS_SERVIR_POSPARTO:
                out["servir"].append({**base, "ultimo_parto": r["ult_parto"], "dias_abiertos": posparto})

            # Celo esperado: ciclos de 21 d desde el último celo o servicio.
            refs = [d for d in (to_date_safe(r["ult_celo_fecha"]), serv_f) if d]
            if refs:
                ref = max(refs)
                ciclos = max(1, -(-((hoy - ref).days - CELO_VENTANA[1]) // CICLO_CELO))
                if ciclos <= CICLOS_CELO_MAX:
                    prox = ref + timedelta(days=CICLO_CELO * ciclos)
                    en = (prox - hoy).days
                    if CELO_VENTANA[0] <= en <= CELO_VENTANA[1]:
                        out["celos"].append({**base, "proximo_celo": prox.isoformat(), "en_dias": en,
                                             "fecha_base": ref.isoformat()})


def _manejo_y_categoria(out: dict, datos: dict, info: dict, hoy: date) -> None:
    ini_aftosa, ciclo = _ciclo_aftosa(hoy)
    out["ciclo_aftosa"] = ciclo
    for aid, a in info.items():
        base, edad, m = a["base"], a["edad"], datos["manejos"].get(aid, {})
        hembra, macho = _es_hembra(a["sexo"]), _es_macho(a["sexo"])
        if edad is not None:
            if a["madre_id"] and EDAD_DESTETE[0] <= edad <= EDAD_DESTETE[1] and aid not in datos["destetados"]:
                out["destetar"].append({**base, "madre": a["madre"], "edad_dias": edad})
            if EDAD_TOPIZAR[0] <= edad <= EDAD_TOPIZAR[1] and "TOPIZADO" not in m:
                out["topizar"].append({**base, "edad_dias": edad})
            if (macho and EDAD_CASTRAR[0] <= edad <= EDAD_CASTRAR[1] and not a["reproductor"]
                    and "CASTRACION" not in m and "ENTERO" not in m):
                out["castrar"].append({**base, "edad_dias": edad})
            if EDAD_MARCAR[0] <= edad <= EDAD_MARCAR[1] and not str(a["hierro"] or "").strip() and "MARCACION" not in m:
                out["marcar"].append({**base, "edad_dias": edad})
            if hembra and EDAD_BRUCELOSIS[0] <= edad <= EDAD_BRUCELOSIS[1] and "VACUNA_BRUCELOSIS" not in m:
                out["vac_brucelosis"].append({**base, "edad_dias": edad})
            for limite in CAMBIOS_CATEGORIA:
                if limite <= edad < limite + DIAS_CAMBIO_CATEGORIA and not (macho and a["reproductor"]):
                    if limite == 365:
                        cambio = "Cría → Levante"
                    else:
                        cambio = "Levante → Novilla" if hembra else "Levante → Ceba"
                    out["categoria"].append({**base, "edad_dias": edad, "cambio": cambio})
        if m.get("VACUNA_AFTOSA", "") < ini_aftosa.isoformat():
            out["vac_aftosa"].append({**base, "ultima": m.get("VACUNA_AFTOSA") or None})


def _sanidad_leche_carne(out: dict, datos: dict, info: dict, hoy: date) -> None:
    hoy_iso = hoy.isoformat()
    lim_ret = (hoy + timedelta(days=DIAS_RETIRO_PROXIMO)).isoformat()
    desde_trat = (hoy - timedelta(days=DIAS_TRATAMIENTO_SEGUIMIENTO)).isoformat()
    por_animal: dict[int, dict] = {}
    for t in datos["tratamientos"]:
        a = info.get(t["animal_id"])
        if not a:
            continue
        partes = []
        if (t["fecha"] or "") >= desde_trat:
            partes.append(f"Tratado {t['fecha']}: {t['producto'] or 'sin producto'}")
        for campo, nombre in (("fecha_fin_retiro_leche", "leche"), ("fecha_fin_retiro_carne", "carne")):
            f = t[campo]
            if f and hoy_iso <= f <= lim_ret:
                partes.append(f"Retiro de {nombre} termina {f}")
        if partes:
            fila = por_animal.setdefault(t["animal_id"], {**a["base"], "detalle": []})
            fila["detalle"].extend(p for p in partes if p not in fila["detalle"])
    out["tratamientos"] = [{**f, "detalle": " · ".join(f["detalle"])} for f in por_animal.values()]

    for aid, a in info.items():
        if not _es_hembra(a["sexo"]) or not a["ult_parto"]:
            continue
        del_d = (hoy - a["ult_parto"]).days
        ult_sec = to_date_safe(datos["secados"].get(aid))
        if DEL_ALTO[0] <= del_d <= DEL_ALTO[1] and not (ult_sec and ult_sec >= a["ult_parto"]):
            out["del_alto"].append({**a["base"], "dias_en_leche": del_d,
                                    "prenada": a.get("estado_repro") == "PRENADA"})
    for p in datos["pausas"]:
        a = info.get(p["animal_id"])
        f = to_date_safe(p["fecha_inicio"])
        if a and f and (hoy - f).days > DIAS_PAUSA_LARGA:
            out["pausas"].append({**a["base"], "desde": p["fecha_inicio"], "dias": (hoy - f).days,
                                  "motivo": p["motivo"]})

    for aid, a in info.items():
        pes = datos["pesos"].get(aid) or []
        if len(pes) == 2 and pes[0][0] and pes[1][0] and (hoy - pes[0][0]).days <= DIAS_PESAJE_RECIENTE:
            dias = (pes[0][0] - pes[1][0]).days
            if dias >= 14:
                gmd = (pes[0][1] - pes[1][1]) / dias
                if gmd < GMD_MIN_KG:
                    out["bajo_peso"].append({**a["base"], "gmd_g": round(gmd * 1000), "peso_kg": pes[0][1],
                                             "fecha": pes[0][0].isoformat()})
        if _es_macho(a["sexo"]) and not a["reproductor"] and a["peso"] is not None and a["peso"] >= PESO_VENTA_KG:
            out["venta"].append({**a["base"], "peso_kg": a["peso"], "edad_dias": a["edad"]})
        if _es_hembra(a["sexo"]):
            motivos = []
            if a["edad"] is not None and a["edad"] > EDAD_DESCARTE_DIAS:
                motivos.append(f"{a['edad'] // 365} años")
            if a.get("repetidora"):
                motivos.append("repetidora")
            if a.get("estado_repro") in ("ABIERTA", "PARIDA") and a.get("posparto") and a["posparto"] > DIAS_SIN_PARTO_DESCARTE:
                motivos.append(f"sin parto hace {a['posparto'] // 30} meses")
            if motivos:
                out["descarte"].append({**a["base"], "motivo": " · ".join(motivos)})


def datos_tareas(db: Database, hoy: Optional[date] = None, usar_cache: bool = False) -> dict:
    """Todas las listas de trabajo y sus conteos."""
    hoy = hoy or date.today()
    clave = (getattr(db, "path", None), hoy.isoformat())
    if usar_cache and clave in _cache and time.monotonic() - _cache[clave][0] < CACHE_SEGUNDOS:
        return _cache[clave][1]
    out: dict[str, Any] = _vacio()
    try:
        datos = _cargar(db)
    except Exception as e:
        logger.error("datos_tareas: lectura fallo", exc_info=True)
        out["errores"] = {"tareas": str(e)}
        out["conteos"] = {k: 0 for k in CLAVES}
        return out

    info: dict[int, dict] = {}
    partos = {r["id_animal"]: to_date_safe(r["ult_parto"]) for r in datos["vientres"]}
    for a in datos["animales"]:
        fnac = to_date_safe(a["fecha_nacimiento"])
        pes = datos["pesos"].get(a["id_animal"]) or []
        info[a["id_animal"]] = {
            **a,
            "base": {"tag": a["tag"], "nombre": a["nombre"], "potrero": a["potrero"] or SIN_POTRERO_LABEL},
            "edad": (hoy - fnac).days if fnac else None,
            "peso": pes[0][1] if pes else None,
            "reproductor": _es_reproductor(a),
            "ult_parto": partos.get(a["id_animal"]),
        }
    for nombre, fn in (("reproduccion", _reproduccion), ("manejo", _manejo_y_categoria),
                       ("sanidad", _sanidad_leche_carne)):
        try:
            fn(out, datos, info, hoy)
        except Exception as e:
            logger.error("datos_tareas: seccion %s fallo", nombre, exc_info=True)
            out.setdefault("errores", {})[nombre] = str(e)

    out["palpar"].sort(key=lambda x: -x["dias"])
    out["secar"].sort(key=lambda x: x["dias_para_parto"])
    out["servir"].sort(key=lambda x: -(x["dias_abiertos"] or 0))
    out["partos"].sort(key=lambda x: x["en_dias"])
    out["celos"].sort(key=lambda x: x["en_dias"])
    out["destetar"].sort(key=lambda x: -(x["edad_dias"] or 0))
    out["bajo_peso"].sort(key=lambda x: x["gmd_g"])
    out["venta"].sort(key=lambda x: -x["peso_kg"])
    out["chequeo"].sort(key=lambda x: (x["potrero"], x["tag"]))
    out["conteos"] = {k: len(out[k]) for k in CLAVES}
    if usar_cache:
        _cache[clave] = (time.monotonic(), out)
    return out
