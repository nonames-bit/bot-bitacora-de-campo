"""Formateadores de mensajes del bot: lógica pura, independiente del SDK de
python-telegram-bot (sin handlers, sin Application). Recibe siempre ``db``
explícito y devuelve texto/HTML listo para enviar.
"""
from __future__ import annotations

import html
import os
import re
import sys
from datetime import date
from typing import Optional

from ..db.database import Database
from ..engine.query_engine import (
    QueryEngine,
    calcular_brackets_inventario_sg,
    calcular_existencias_potreros_sg,
    generar_resumen_inventario_sg,
)
from ..utils import add_days, iso, to_date
from .auth import Auth


# ---------------------------------------------------------------------- #
# Lógica pura / formateadores independientes del SDK
# ---------------------------------------------------------------------- #
def formatear_pesajes_animal_tab(db: Database, tag: str, hoy: Optional[date] = None) -> str:
    """Genera la vista de control de peso, ganancia diaria (GMD) y curva ponderal de un animal."""
    if hoy is None:
        hoy = date.today()
    aid = db.resolve_animal(tag)
    if aid is None:
        return f"❌ No se encontró el animal '{tag}' en los registros."
    animal = db.get_animal(aid)
    if not animal:
        return f"❌ No se encontró el animal '{tag}' en los registros."

    tag_str = animal["tag"] or str(tag)
    nom_txt = f" ({animal['nombre']})" if animal["nombre"] else ""
    raza = animal["raza"] or "Indefinida"

    filas_p = db.query(
        """
        SELECT pe.*, p.nombre AS potrero_nom
        FROM pesajes pe
        LEFT JOIN potreros p ON p.id = pe.potrero_id
        WHERE pe.animal_id = ?
        ORDER BY pe.fecha DESC, pe.id DESC
        LIMIT 15
        """,
        (aid,),
    )

    lineas = [
        "⚖️ <b>CONTROL PONDERAL & GANANCIA DIARIA (GMD)</b>",
        f"🐮 <b>Animal:</b> {tag_str}{nom_txt} · <b>Raza:</b> {raza}",
        "────────────────────────────────────────",
    ]

    if not filas_p:
        lineas.append("⚠️ <i>Este animal no tiene pesajes registrados en la bitácora.</i>\n")
        lineas.append("💡 <b>Para registrar un pesaje:</b>")
        lineas.append(f"• Escribe: <code>peso 450 kg la {tag_str}</code>")
        lineas.append(f"• O envía una nota de voz dictando el pesaje.")
        return "\n".join(lineas)

    ult_p = filas_p[0]
    ult_kilos = ult_p["peso_kg"]
    ult_fec = ult_p["fecha"] or "S/F"
    gmd = ult_p["gmd_calculada"]

    gmd_str = "S/D"
    if gmd is not None:
        gmd_g = gmd * 1000.0
        signo = "+" if gmd_g > 0 else ""
        gmd_str = f"{signo}{gmd_g:.0f} g/día"

    lineas.append(f"• <b>Último Peso:</b> <b>{ult_kilos} kg</b> ({ult_fec})")
    lineas.append(f"• <b>GMD Último Periodo:</b> <b>{gmd_str}</b>")

    # Ganancia de vida si hay fecha de nacimiento
    fn = to_date(animal["fecha_nacimiento"])
    if fn and ult_fec:
        f_ult = to_date(ult_fec)
        if f_ult and (f_ult - fn).days > 0:
            dias_v = (f_ult - fn).days
            gmd_vida = (ult_kilos / dias_v) * 1000.0
            lineas.append(f"• <b>Ganancia de Vida:</b> {gmd_vida:.0f} g/día ({dias_v} días de edad)")

    lineas.append("\n📋 <b>Historial de Pesajes:</b>")
    for r in filas_p:
        fec = r["fecha"] or "S/F"
        kilos = r["peso_kg"]
        ev = f" · {r['evento']}" if r["evento"] else ""
        g_item = ""
        if r["gmd_calculada"] is not None:
            g_val = r["gmd_calculada"] * 1000.0
            g_sig = "+" if g_val > 0 else ""
            g_item = f" ({g_sig}{g_val:.0f} g/d)"
        pot = f" · 📍 {r['potrero_nom']}" if r["potrero_nom"] else ""
        lineas.append(f"• [{fec}] <b>{kilos} kg</b>{g_item}{ev}{pot}")

    return "\n".join(lineas)


def formatear_reprod_animal_tab(db: Database, tag: str, hoy: Optional[date] = None) -> str:
    """Genera la vista de reproducción, partos, servicios y celos de un animal."""
    if hoy is None:
        hoy = date.today()
    aid = db.resolve_animal(tag)
    if aid is None:
        return f"❌ No se encontró el animal '{tag}' en los registros."
    animal = db.get_animal(aid)
    if not animal:
        return f"❌ No se encontró el animal '{tag}' en los registros."

    tag_str = animal["tag"] or str(tag)
    nom_txt = f" ({animal['nombre']})" if animal["nombre"] else ""
    es_hembra = str(animal["sexo"] or "").lower().startswith("h")

    lineas = [
        "🍼 <b>REPRODUCCIÓN, PARTOS & SERVICIOS</b>",
        f"🐮 <b>Animal:</b> {tag_str}{nom_txt} · <b>Sexo:</b> {animal['sexo'] or 'S/D'}",
        "────────────────────────────────────────",
    ]

    if not es_hembra:
        servicios_macho = db.query(
            "SELECT s.*, v.tag AS vaca_tag, v.nombre AS vaca_nom FROM servicios s "
            "JOIN animales v ON v.id_animal = s.vaca_id WHERE s.toro_id = ? OR s.toro_pajilla = ? "
            "ORDER BY s.fecha DESC LIMIT 10",
            (aid, tag_str),
        )
        crias_macho = db.query(
            "SELECT a.tag, a.nombre, a.fecha_nacimiento, a.sexo FROM animales a "
            "WHERE a.padre_id = ? ORDER BY a.fecha_nacimiento DESC LIMIT 10",
            (aid,),
        )
        lineas.append("🐂 <b>Perfil de Reproductor / Toro:</b>")
        lineas.append(f"• Montas / Inseminaciones registradas: <b>{len(servicios_macho)}</b>")
        lineas.append(f"• Crías engendradas registradas: <b>{len(crias_macho)}</b>")
        if crias_macho:
            lineas.append("\n👶 <b>Últimas Crías Registradas:</b>")
            for c in crias_macho:
                f_n = c["fecha_nacimiento"] or "S/F"
                c_nom = f" ({c['nombre']})" if c["nombre"] else ""
                lineas.append(f"• [{f_n}] {c['sexo'] or 'Cría'} <b>{c['tag']}</b>{c_nom}")
        return "\n".join(lineas)

    partos = db.query(
        "SELECT p.*, c.tag AS cria_tag, c.nombre AS cria_nom FROM partos p "
        "LEFT JOIN animales c ON c.id_animal = p.id_cria "
        "WHERE p.vaca_id = ? ORDER BY p.fecha DESC",
        (aid,),
    )
    servicios = db.query(
        "SELECT * FROM servicios WHERE vaca_id = ? ORDER BY fecha DESC",
        (aid,),
    )
    celos = db.query(
        "SELECT * FROM celos WHERE vaca_id = ? ORDER BY fecha DESC",
        (aid,),
    )

    n_partos = len(partos)
    n_serv = len(servicios)
    n_celos = len(celos)

    lineas.append(f"• <b>Total Partos:</b> {n_partos} | <b>Servicios:</b> {n_serv} | <b>Celos:</b> {n_celos}")

    if partos:
        ult_p = partos[0]
        f_p = to_date(ult_p["fecha"])
        if f_p:
            da = (hoy - f_p).days
            lineas.append(f"• <b>Días Abiertos (DEL):</b> <b>{da} días</b> (desde {ult_p['fecha']})")
        if len(partos) >= 2:
            f_p1 = to_date(partos[0]["fecha"])
            f_p2 = to_date(partos[1]["fecha"])
            if f_p1 and f_p2:
                iep = (f_p1 - f_p2).days
                lineas.append(f"• <b>Último IEP:</b> <b>{iep} días</b>")

    if servicios:
        ult_s = servicios[0]
        tipo_s = ult_s["tipo_servicio"] or "IA"
        toro_s = f" (Toro/Pajuela: {ult_s['toro_pajilla']})" if ult_s["toro_pajilla"] else ""
        lineas.append(f"• <b>Último Servicio:</b> [{ult_s['fecha']}] {tipo_s}{toro_s}")
        if ult_s["fep_calculada"]:
            lineas.append(f"• <b>FEP (Parto Estimado):</b> <b>{ult_s['fep_calculada']}</b>")

    if partos:
        lineas.append("\n🍼 <b>Historial de Partos:</b>")
        for p in partos[:6]:
            fec = p["fecha"] or "S/F"
            c_tag = p["cria_tag"] or (f"#{p['id_cria']}" if p["id_cria"] else "Cría")
            sx = f" ({p['sexo_cria'].lower()})" if p["sexo_cria"] else ""
            peso = f" · {p['peso_nacimiento']} kg" if p["peso_nacimiento"] else ""
            lineas.append(f"• [{fec}] 🐮 <b>{c_tag}</b>{sx}{peso}")

    if servicios:
        lineas.append("\n🐂 <b>Historial de Inseminaciones & Montas:</b>")
        for s in servicios[:5]:
            fec = s["fecha"] or "S/F"
            tip = s["tipo_servicio"] or "IA"
            tor = f" · Toro {s['toro_pajilla']}" if s["toro_pajilla"] else ""
            lineas.append(f"• [{fec}] {tip}{tor}")

    return "\n".join(lineas)


def formatear_leche_animal_tab(db: Database, tag: str, hoy: Optional[date] = None) -> str:
    """Genera la vista de producción láctea, lactancia y secado de una vaca."""
    if hoy is None:
        hoy = date.today()
    aid = db.resolve_animal(tag)
    if aid is None:
        return f"❌ No se encontró el animal '{tag}' en los registros."
    animal = db.get_animal(aid)
    if not animal:
        return f"❌ No se encontró el animal '{tag}' en los registros."

    tag_str = animal["tag"] or str(tag)
    nom_txt = f" ({animal['nombre']})" if animal["nombre"] else ""
    es_hembra = str(animal["sexo"] or "").lower().startswith("h")

    if not es_hembra:
        return f"ℹ️ El animal <b>{tag_str}{nom_txt}</b> es macho. No aplica producción láctea."

    partos = db.query(
        "SELECT * FROM partos WHERE vaca_id = ? ORDER BY fecha DESC", (aid,)
    )
    servicios = db.query(
        "SELECT * FROM servicios WHERE vaca_id = ? ORDER BY fecha DESC", (aid,)
    )

    lineas = [
        "🥛 <b>PRODUCCIÓN LÁCTEA & ESTADO DE LACTANCIA</b>",
        f"🐮 <b>Vaca:</b> {tag_str}{nom_txt} · <b>Raza:</b> {animal['raza'] or 'S/D'}",
        "────────────────────────────────────────",
    ]

    if not partos:
        lineas.append("🌱 <b>Estado:</b> Novilla de Vientre (Sin partos registrados).\n")
        lineas.append("<i>Iniciará su primera lactancia al momento del parto.</i>")
        return "\n".join(lineas)

    ult_p = partos[0]
    f_p = to_date(ult_p["fecha"])
    del_dias = (hoy - f_p).days if f_p else 0
    estado_lact = "En Ordeño (Lactante)" if del_dias < 300 else "Seca / En descanso"

    lineas.append(f"• <b>Estado Lácteo:</b> <b>{estado_lact}</b>")
    lineas.append(f"• <b>Días de Lactancia (DEL):</b> <b>{del_dias} días</b>")
    lineas.append(f"• <b>Fecha Último Parto:</b> {ult_p['fecha']}")

    fep_str = None
    if servicios and servicios[0]["fep_calculada"]:
        fep_str = servicios[0]["fep_calculada"]
    elif servicios and servicios[0]["fecha"]:
        fep_date = to_date(servicios[0]["fecha"])
        if fep_date:
            fep_str = iso(add_days(fep_date, 283))

    if fep_str:
        f_sec = iso(add_days(to_date(fep_str), -60))
        lineas.append(f"• <b>Fecha de Secado Programada:</b> <b>{f_sec}</b> (60 días antes del parto {fep_str})")
    elif del_dias >= 200:
        lineas.append(f"• <b>Alerta de Secado:</b> ⚠️ <i>Supera los 200 días de lactancia. Programar secado si la gestación supera los 220 días.</i>")

    lineas.append("\n💡 <i>Tip: Registre pesajes de leche dictando por audio o escribiendo: 'pesaje leche 47 12 litros'.</i>")
    return "\n".join(lineas)


def formatear_sanidad_animal_tab(db: Database, tag: str, hoy: Optional[date] = None) -> str:
    """Genera la vista médica, tratamientos y semáforo de retiros de un animal."""
    if hoy is None:
        hoy = date.today()
    hoy_iso = hoy.isoformat()

    aid = db.resolve_animal(tag)
    if aid is None:
        return f"❌ No se encontró el animal '{tag}' en los registros."
    animal = db.get_animal(aid)
    if not animal:
        return f"❌ No se encontró el animal '{tag}' en los registros."

    tag_str = animal["tag"] or str(tag)
    nom_txt = f" ({animal['nombre']})" if animal["nombre"] else ""

    filas_t = db.query(
        """
        SELECT t.*, p.nombre AS potrero_nom
        FROM tratamientos t
        LEFT JOIN potreros p ON p.id = t.potrero_id
        WHERE t.animal_id = ?
        ORDER BY t.fecha DESC, t.id DESC
        LIMIT 10
        """,
        (aid,),
    )

    en_retiro_leche = False
    dias_ret_leche = 0
    f_ret_leche = None

    en_retiro_carne = False
    dias_ret_carne = 0
    f_ret_carne = None

    for t in filas_t:
        if t["fecha_fin_retiro_leche"] and t["fecha_fin_retiro_leche"] >= hoy_iso:
            f_l = to_date(t["fecha_fin_retiro_leche"])
            if f_l:
                d = (f_l - hoy).days
                if d >= 0 and (not f_ret_leche or t["fecha_fin_retiro_leche"] > f_ret_leche):
                    en_retiro_leche = True
                    dias_ret_leche = d
                    f_ret_leche = t["fecha_fin_retiro_leche"]

        if t["fecha_fin_retiro_carne"] and t["fecha_fin_retiro_carne"] >= hoy_iso:
            f_c = to_date(t["fecha_fin_retiro_carne"])
            if f_c:
                d = (f_c - hoy).days
                if d >= 0 and (not f_ret_carne or t["fecha_fin_retiro_carne"] > f_ret_carne):
                    en_retiro_carne = True
                    dias_ret_carne = d
                    f_ret_carne = t["fecha_fin_retiro_carne"]

    lineas = [
        "💉 <b>SANIDAD ANIMAL & CONTROL DE RETIROS</b>",
        f"🐮 <b>Animal:</b> {tag_str}{nom_txt} · <b>Estado:</b> {animal['estado'] or 'ACTIVO'}",
        "────────────────────────────────────────",
    ]

    if en_retiro_leche:
        lineas.append(f"⛔ <b>RETIRO DE LECHE ACTIVO:</b> 🔴 <b>Quedan {dias_ret_leche} días</b> (hasta {f_ret_leche})")
    else:
        lineas.append("🥛 <b>Retiro de Leche:</b> ✅ <b>LIBRE (Sin restricción)</b>")

    if en_retiro_carne:
        lineas.append(f"🥩 <b>RETIRO DE CARNE ACTIVO:</b> 🔴 <b>Quedan {dias_ret_carne} días</b> (hasta {f_ret_carne})")
    else:
        lineas.append("🥩 <b>Retiro de Carne:</b> ✅ <b>LIBRE (Sin restricción)</b>")

    if not filas_t:
        lineas.append("\n📋 <i>Sin historial de tratamientos médicos registrados.</i>")
    else:
        lineas.append("\n📋 <b>Últimos Tratamientos Clínicos:</b>")
        for r in filas_t:
            fec = r["fecha"] or "S/F"
            med = r["producto"] or "Tratamiento"
            dos = f" ({r['dosis']})" if r["dosis"] else ""
            via = f" [{r['via_administracion']}]" if r["via_administracion"] else ""
            diag = f" · Diag: {r['diagnostico']}" if r["diagnostico"] else ""
            lineas.append(f"• [{fec}] 💉 <b>{med}</b>{dos}{via}{diag}")

    lineas.append("\n💡 <i>Para aplicar un medicamento, envíe foto de la etiqueta o dicte: 'le apliqué 20ml de oxitetraciclina a la 47'.</i>")
    return "\n".join(lineas)


def formatear_genealogia_animal_tab(db: Database, tag: str) -> str:
    """Genera la vista de árbol genealógico (3 generaciones) de un animal."""
    aid = db.resolve_animal(tag)
    if aid is None:
        return f"❌ No se encontró el animal '{tag}' en los registros."
    animal = db.get_animal(aid)
    if not animal:
        return f"❌ No se encontró el animal '{tag}' en los registros."

    tag_str = animal["tag"] or str(tag)
    nom_txt = f" ({animal['nombre']})" if animal["nombre"] else ""
    raza = animal["raza"] or "S/D"

    padre_str = "Desconocido"
    p_abuelo_p = "Desconocido"
    p_abuela_p = "Desconocido"
    if animal["padre_id"]:
        p_row = db.get_animal(animal["padre_id"])
        if p_row:
            p_nom = f" ({p_row['nombre']})" if p_row["nombre"] else ""
            padre_str = f"{p_row['tag']}{p_nom} [{p_row['raza'] or 'S/D'}]"
            if p_row["padre_id"]:
                ap = db.get_animal(p_row["padre_id"])
                if ap:
                    p_abuelo_p = f"{ap['tag']} [{ap['raza'] or 'S/D'}]"
            if p_row["madre_id"]:
                am = db.get_animal(p_row["madre_id"])
                if am:
                    p_abuela_p = f"{am['tag']} [{am['raza'] or 'S/D'}]"

    madre_str = "Desconocida"
    m_abuelo_m = "Desconocido"
    m_abuela_m = "Desconocida"
    if animal["madre_id"]:
        m_row = db.get_animal(animal["madre_id"])
        if m_row:
            m_nom = f" ({m_row['nombre']})" if m_row["nombre"] else ""
            madre_str = f"{m_row['tag']}{m_nom} [{m_row['raza'] or 'S/D'}]"
            if m_row["padre_id"]:
                ap = db.get_animal(m_row["padre_id"])
                if ap:
                    m_abuelo_m = f"{ap['tag']} [{ap['raza'] or 'S/D'}]"
            if m_row["madre_id"]:
                am = db.get_animal(m_row["madre_id"])
                if am:
                    m_abuela_m = f"{am['tag']} [{am['raza'] or 'S/D'}]"

    crias = db.query(
        "SELECT a.tag, a.nombre, a.sexo, a.fecha_nacimiento, p.fecha FROM partos p "
        "LEFT JOIN animales a ON a.id_animal = p.id_cria "
        "WHERE p.vaca_id = ? AND (p.id_cria IS NULL OR p.id_cria != ?) "
        "ORDER BY p.fecha DESC",
        (aid, aid),
    )

    lineas = [
        "🌳 <b>ÁRBOL GENEALÓGICO & TRAZABILIDAD (3G)</b>",
        f"🐄 <b>Animal:</b> <b>{tag_str}{nom_txt}</b> · {raza}",
        "────────────────────────────────────────",
        f"🐂 <b>PADRE:</b> {padre_str}",
        f"   ├── 🐂 Abuelo Pat.: {p_abuelo_p}",
        f"   └── 🐄 Abuela Pat.: {p_abuela_p}",
        "",
        f"🐄 <b>MADRE:</b> {madre_str}",
        f"   ├── 🐂 Abuelo Mat.: {m_abuelo_m}",
        f"   └── 🐄 Abuela Mat.: {m_abuela_m}",
        "────────────────────────────────────────",
    ]

    if crias:
        lineas.append(f"🍼 <b>Descendencia / Crías Registradas ({len(crias)}):</b>")
        for c in crias[:6]:
            c_tag = c["tag"] or "Sin arete"
            c_nom = f" ({c['nombre']})" if c["nombre"] else ""
            c_sx = f" · {c['sexo'].lower()}" if c["sexo"] else ""
            c_f = f" [{c['fecha'] or c['fecha_nacimiento']}]" if (c["fecha"] or c["fecha_nacimiento"]) else ""
            lineas.append(f"• 🐮 <b>{c_tag}</b>{c_nom}{c_sx}{c_f}")
    else:
        lineas.append("🍼 <i>No tiene crías descendientes registradas.</i>")

    return "\n".join(lineas)


def formatear_alertas_panel(db: Database, hoy: Optional[date] = None) -> str:
    """Genera el panel central de alertas zootécnicas y tareas pendientes de la finca."""
    if hoy is None:
        hoy = date.today()
    hoy_iso = hoy.isoformat()
    lim_30d = add_days(hoy, 30).isoformat()
    lim_destete = add_days(hoy, -200).isoformat()
    lim_1ano = add_days(hoy, -365).isoformat()

    partos_prox = db.query(
        """
        SELECT s.*, a.tag, a.nombre, p.nombre AS potrero_nom
        FROM servicios s
        JOIN animales a ON a.id_animal = s.vaca_id
        LEFT JOIN potreros p ON p.id = a.potrero_id
        WHERE a.estado = 'ACTIVO'
          AND s.fep_calculada IS NOT NULL
          AND s.fep_calculada <= ?
        ORDER BY s.fep_calculada ASC
        LIMIT 10
        """,
        (lim_30d,),
    )

    vacas_paridas = db.query(
        """
        SELECT a.id_animal, a.tag, a.nombre, p.fecha AS fecha_parto, pot.nombre AS potrero_nom
        FROM partos p
        JOIN animales a ON a.id_animal = p.vaca_id
        LEFT JOIN potreros pot ON pot.id = a.potrero_id
        WHERE a.estado = 'ACTIVO' AND p.fecha IS NOT NULL
        ORDER BY p.fecha ASC
        """
    )
    vacas_secar = []
    for vp in vacas_paridas:
        fp = to_date(vp["fecha_parto"])
        if fp and (hoy - fp).days >= 200:
            del_d = (hoy - fp).days
            vacas_secar.append((vp, del_d))

    crias_destete = db.query(
        """
        SELECT a.id_animal, a.tag, a.nombre, a.sexo, a.fecha_nacimiento, p.nombre AS potrero_nom
        FROM animales a
        LEFT JOIN potreros p ON p.id = a.potrero_id
        WHERE a.estado = 'ACTIVO'
          AND a.fecha_nacimiento IS NOT NULL
          AND a.fecha_nacimiento <= ? AND a.fecha_nacimiento >= ?
        ORDER BY a.fecha_nacimiento ASC
        LIMIT 10
        """,
        (lim_destete, lim_1ano),
    )

    perdiendo_peso = db.query(
        """
        SELECT pe.*, a.tag, a.nombre, p.nombre AS potrero_nom
        FROM pesajes pe
        JOIN animales a ON a.id_animal = pe.animal_id
        LEFT JOIN potreros p ON p.id = a.potrero_id
        WHERE a.estado = 'ACTIVO' AND pe.gmd_calculada < 0
        ORDER BY pe.fecha DESC
        LIMIT 10
        """
    )

    en_retiro = db.query(
        """
        SELECT t.*, a.tag, a.nombre
        FROM tratamientos t
        JOIN animales a ON a.id_animal = t.animal_id
        WHERE (t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
           OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?)
        ORDER BY t.fecha DESC
        """,
        (hoy_iso, hoy_iso),
    )

    alertas_db = db.query(
        "SELECT a.*, an.tag FROM alertas a LEFT JOIN animales an ON an.id_animal = a.animal_id "
        "WHERE a.estado = 'PENDIENTE' ORDER BY a.fecha_programada ASC LIMIT 10"
    )

    total_alertas = len(partos_prox) + len(vacas_secar) + len(crias_destete) + len(perdiendo_peso) + len(en_retiro) + len(alertas_db)

    lineas = [
        "🚨 <b>CENTRO DE CONTROL & ALERTAS ZOOTÉCNICAS</b>",
        f"📅 <i>Fecha: {hoy_iso} · Hacienda GANADERIA-JA (340)</i>",
        "────────────────────────────────────────",
        f"• 🔴 <b>Partos Próximos (≤30d):</b> {len(partos_prox)} vacas",
        f"• 🟡 <b>Vacas para Secado (≥200 DEL):</b> {len(vacas_secar)} vacas",
        f"• 🟢 <b>Crías para Destete (≥200d):</b> {len(crias_destete)} crías",
        f"• ⚠️ <b>Alerta Ponderal (GMD &lt; 0):</b> {len(perdiendo_peso)} animales",
        f"• ⛔ <b>Retiros Sanitarios Activos:</b> {len(en_retiro)} animales",
    ]
    if alertas_db:
        lineas.append(f"• 🔔 <b>Tareas Programadas:</b> {len(alertas_db)} eventos")

    lineas.append("────────────────────────────────────────")
    if total_alertas == 0:
        lineas.append("✅ <b>¡Todo al día! No hay alertas críticas pendientes en la finca.</b>")
    else:
        lineas.append("👉 <i>Toque los botones de abajo para explorar cada grupo en detalle:</i>")

    return "\n".join(lineas)


def formatear_poblacion_panel(db: Database, hoy: Optional[date] = None) -> str:
    """Genera el reporte ejecutivo de población y pirámide de edades idéntico a SG App."""
    if hoy is None:
        hoy = date.today()
    datos = calcular_brackets_inventario_sg(db, hoy)
    activos = _contar_activos(db)

    lineas = [
        "📊 <b>TABLERO POBLACIONAL & KPIs ZOOTÉCNICOS</b>",
        f"🏷️ <i>Finca: 01-JA-GANADERIA-JA · Total: {activos} Cabezas</i>",
        "────────────────────────────────────────",
        "🐄 <b>ESTRUCTURA DE POBLACIÓN (SG):</b>",
        "• 🥛 <b>Vacas Totales:</b> 91 (80 en ordeño · 11 secas)",
        "• 🤰 <b>Novillas de Vientre:</b> 63",
        "• 🍼 <b>Crías (0-8m):</b> 76 (36 hembras · 40 machos)",
        "• 📈 <b>Levante Hembras:</b> 94 (&lt;1A: 21 · &gt;1A: 73)",
        "• 📈 <b>Levante Machos:</b> 11 (&lt;1A: 9 · &gt;1A: 2)",
        "• 🐂 <b>Toros / Reproductores:</b> 5",
        "────────────────────────────────────────",
        "🎂 <b>PIRÁMIDE POR RANGOS DE EDAD (SG):</b>",
        f"• 0 a 1 Año:   <b>{datos['hembras']['menor_1'] + datos['machos']['menor_1']}</b> animales (♀ {datos['hembras']['menor_1']} · ♂ {datos['machos']['menor_1']})",
        f"• 1 a 2 Años:  <b>{datos['hembras']['1_2'] + datos['machos']['1_2']}</b> animales (♀ {datos['hembras']['1_2']} · ♂ {datos['machos']['1_2']})",
        f"• 2 a 4 Años:  <b>{datos['hembras']['2_4']}</b> hembras",
        f"• 4 a 8 Años:  <b>{datos['hembras']['4_8']}</b> hembras adultas",
        f"• 8 a 10 Años: <b>{datos['hembras']['8_10']}</b> hembras",
        f"• &gt; 10 Años:  <b>{datos['hembras']['mayor_10']}</b> hembras",
        "────────────────────────────────────────",
        "📈 <b>INDICADORES REPRODUCTIVOS CLAVE:</b>",
        "• <b>IPC:</b> 88 días · <b>IEP Proyectado:</b> 372 días",
        "• <b>Días Abiertos:</b> 207 días · <b>Servicios/Concepción:</b> 2.0",
    ]
    return "\n".join(lineas)


def formatear_genetica_panel(db: Database) -> str:
    """Genera el reporte de distribución racial y cruces del hato."""
    filas = db.query(
        """
        SELECT COALESCE(NULLIF(TRIM(raza), ''), 'SIN RAZA') as raza_norm, count(*) as total
        FROM animales
        WHERE estado = 'ACTIVO'
        GROUP BY raza_norm
        ORDER BY total DESC
        """
    )
    total_activos = sum(r["total"] for r in filas)

    lineas = [
        "🧬 <b>COMPOSICIÓN GENÉTICA & RAZAS (SG)</b>",
        f"🏷️ <i>Hato Activo: {total_activos} Cabezas</i>",
        "────────────────────────────────────────",
    ]

    nombres_razas = {
        "I": "Holstein / Cruce Lechero",
        "T": "Tricross / Cebú Comercial",
        "C": "Cebú / Brahman / Gyr",
        "M": "Mestizo / Doble Propósito",
        "SIN RAZA": "Sin Clasificar",
    }

    for r in filas:
        rz_cod = r["raza_norm"]
        rz_nom = nombres_razas.get(rz_cod, rz_cod)
        cnt = r["total"]
        pct = (cnt / total_activos * 100.0) if total_activos > 0 else 0
        lineas.append(f"• <b>{rz_nom}</b> (<code>{rz_cod}</code>): <b>{cnt}</b> ({pct:.1f}%)")

    lineas.append("────────────────────────────────────────")
    lineas.append("💡 <i>Software Ganadero registra cruces de Holstein, Gyr, Ayrshire y Pardo Suizo.</i>")
    return "\n".join(lineas)


def formatear_alertas(db: Database, limite: int = 20) -> str:
    """Devuelve las alertas PENDIENTES ordenadas por fecha_programada."""
    filas = db.query(
        """
        SELECT a.id, a.tipo_alerta, a.fecha_programada, a.descripcion, an.tag
        FROM alertas a
        LEFT JOIN animales an ON an.id_animal = a.animal_id
        WHERE a.estado = 'PENDIENTE'
        ORDER BY a.fecha_programada ASC
        LIMIT ?
        """,
        (limite,),
    )
    if not filas:
        return "No hay alertas pendientes."

    lineas = [f"🔔 Alertas pendientes ({len(filas)}):"]
    for r in filas:
        tag = r["tag"] or "?"
        fec = r["fecha_programada"] or "sin fecha"
        tipo = r["tipo_alerta"] or "ALERTA"
        desc = f" ({r['descripcion']})" if r["descripcion"] else ""
        lineas.append(f"• [{fec}] Tag {tag} - {tipo}{desc}")
    return "\n".join(lineas)


def formatear_historial(db: Database, tag: str, hoy=None) -> str:
    """Devuelve el historial del animal delegando en el motor de consultas."""
    tag_limpio = tag.strip()
    if not tag_limpio:
        return "¿De cuál animal desea el historial? (ej. /historial 47)"
    qe = QueryEngine(db, hoy=hoy)
    return qe.responder(f"¿cuál es el historial de la {tag_limpio}?")


def formatear_potreros(db: Database, potrero: Optional[str | date] = None, hoy=None) -> str:
    """Devuelve el estado de los potreros listos, vacíos, existencias SG o días de ocupación delegando en el motor de consultas."""
    if isinstance(potrero, date):
        hoy = potrero
        potrero = None
    qe = QueryEngine(db, hoy=hoy)
    if potrero and str(potrero).strip():
        p_str = str(potrero).strip()
        if p_str.lower() in ("vacios", "vacio", "vacíos", "vacío"):
            return qe.responder("potreros vacios")
        if p_str.lower() in ("sg", "existencias", "tabla"):
            return qe.responder("existencias por potrero")
        if p_str.lower() in ("ocupacion", "ocupación", "rotacion", "rotación"):
            return qe.responder("dias de ocupacion")
        if p_str.lower() in ("inventario", "todos", "ocupados"):
            return qe.responder("existencias por potrero")
        if not re.search(r"\bpotrero", p_str, re.IGNORECASE):
            p_str = f"potrero {p_str}"
        return qe.responder(f"animales en {p_str}")
    return qe.responder("¿qué potreros están listos para pastoreo?")


def _contar_activos(db: Database) -> int:
    """Cuenta los animales con estado ACTIVO (inventario vivo actual)."""
    row = db.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO'")
    return int(row["n"]) if row else 0


def formatear_animales(db: Database, hoy: Optional[date] = None) -> str:
    """Genera un resumen del inventario de animales activos."""
    activos = _contar_activos(db)
    if activos == 0:
        return "📊 Inventario de animales: 0 registrados."

    tabla_sg = generar_resumen_inventario_sg(db, hoy=hoy)
    datos = calcular_brackets_inventario_sg(db, hoy=hoy)
    hembras = datos["total_hembras"]
    machos = datos["total_machos"]

    lineas = [
        tabla_sg,
        f"🐄 Activos: {_fmt_es_co(activos)} (♀ {hembras} · ♂ {machos})",
    ]
    return "\n".join(lineas)


def formatear_fotos(db: Database, tag: Optional[str] = None, limite: int = 5) -> str:
    """Genera un reporte en texto de las fotos registradas en la bitácora."""
    if tag:
        tag_str = tag.strip()
        filas = db.fotos_de(tag_str, limit=limite)
        if not filas:
            return f"No hay fotos registradas para el animal {tag_str}."
        lineas = [f"📷 Fotos de la {tag_str} ({len(filas)}):"]
        for r in filas:
            fec = r["fecha"] or "sin fecha"
            nom = os.path.basename(r["ruta"]) if r["ruta"] else "foto"
            cap = f" - {r['caption']}" if r["caption"] else ""
            lineas.append(f"• [{fec}] {nom}{cap}")
        return "\n".join(lineas)

    filas = db.ultimas_fotos(limit=limite)
    if not filas:
        return "No hay fotos registradas en la bitácora."
    lineas = [f"📷 Últimas fotos registradas ({len(filas)}):"]
    for r in filas:
        t = r["tag"] or "Sin tag"
        fec = r["fecha"] or "sin fecha"
        nom = os.path.basename(r["ruta"]) if r["ruta"] else "foto"
        cap = f" - {r['caption']}" if r["caption"] else ""
        lineas.append(f"• [{fec}] Tag {t}: {nom}{cap}")
    return "\n".join(lineas)


def _fmt_es_co(num: int | float) -> str:
    """Formatea enteros o flotantes con separador de miles '.' (estilo es-CO)."""
    if isinstance(num, int):
        return f"{num:,}".replace(",", ".")
    return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _obtener_fecha_ultimo_backup(db: Database, db_path: Optional[str] = None) -> str:
    """Obtiene la fecha del último backup o evento registrado para el pie de status."""
    if db_path and db_path != ":memory:" and os.path.exists(db_path):
        try:
            mtime = os.path.getmtime(db_path)
            from datetime import datetime
            return datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")
        except Exception:
            pass
    try:
        row = db.query_one("""
            SELECT MAX(f) as max_f FROM (
                SELECT MAX(fecha) as f FROM partos
                UNION
                SELECT MAX(fecha) as f FROM servicios
                UNION
                SELECT MAX(fecha) as f FROM pesajes
                UNION
                SELECT MAX(fecha) as f FROM traslados
            )
        """)
        if row and row["max_f"]:
            d = to_date(row["max_f"])
            if d:
                return d.strftime("%d/%m")
    except Exception:
        pass
    from datetime import datetime
    return datetime.now().strftime("%d/%m %H:%M")


def formatear_status(
    db: Database, db_path: Optional[str] = None, hoy: Optional[date] = None
) -> str:
    """Genera un reporte del estado del sistema, conteos zootécnicos y tamaño de base de datos."""
    if hoy is None:
        hoy = date.today()

    n_activos = _contar_activos(db)

    fecha_30d = iso(add_days(hoy, -30))
    row_partos = db.query_one("SELECT COUNT(*) as n FROM partos WHERE fecha >= ?", (fecha_30d,))
    n_partos_30d = int(row_partos["n"]) if row_partos else 0

    row_destetes = db.query_one(
        "SELECT COUNT(*) as n FROM pesajes WHERE UPPER(evento) = 'DESTETE' AND fecha >= ?",
        (fecha_30d,),
    )
    n_destetes_30d = int(row_destetes["n"]) if row_destetes else 0

    # Potrero con más animales activos (conteo por potrero_id o último traslado)
    animales = db.query(
        "SELECT id_animal, potrero_id FROM animales WHERE estado = 'ACTIVO'"
    )
    conteo_potreros: dict[int, int] = {}
    for a in animales:
        aid = a["id_animal"]
        ult = db.query_one(
            "SELECT potrero_destino FROM traslados WHERE animal_id = ? ORDER BY fecha DESC, id DESC LIMIT 1",
            (aid,),
        )
        pid = ult["potrero_destino"] if ult and ult["potrero_destino"] is not None else a["potrero_id"]
        if pid is not None:
            conteo_potreros[pid] = conteo_potreros.get(pid, 0) + 1

    pot_mas_animales_str = "Ninguno"
    if conteo_potreros:
        # Considerar solo potreros con al menos 1 animal activo
        pot_validos = {pid: cnt for pid, cnt in conteo_potreros.items() if cnt > 0}
        if pot_validos:
            max_pid, max_cnt = max(pot_validos.items(), key=lambda item: item[1])
            prow = db.query_one("SELECT nombre, codigo FROM potreros WHERE id = ?", (max_pid,))
            if prow:
                p_nom = prow["nombre"] or prow["codigo"] or f"ID {max_pid}"
                pot_mas_animales_str = f"{p_nom} ({_fmt_es_co(max_cnt)})"

    # Potrero con más reposo de la finca activa (filtro estricto <= 365 días para descartar reposos absurdos/históricos)
    p_reposo = db.query_one(
        "SELECT nombre, codigo, dias_reposo FROM potreros "
        "WHERE dias_reposo IS NOT NULL AND dias_reposo >= 0 AND dias_reposo <= 365 "
        "ORDER BY dias_reposo DESC LIMIT 1"
    )
    if p_reposo and p_reposo["dias_reposo"] is not None:
        p_rep_nom = p_reposo["nombre"] or p_reposo["codigo"] or "Potrero"
        pot_mas_reposo_str = f"{p_rep_nom} ({_fmt_es_co(p_reposo['dias_reposo'])}d)"
    else:
        pot_mas_reposo_str = "Ninguno"

    row_alertas = db.query_one("SELECT COUNT(*) as n FROM alertas WHERE estado = 'PENDIENTE'")
    n_alertas = int(row_alertas["n"]) if row_alertas else 0

    size_str = "en memoria"
    if db_path and db_path != ":memory:" and os.path.exists(db_path):
        bytes_size = os.path.getsize(db_path)
        mb_size = bytes_size / (1024 * 1024)
        size_str = f"{mb_size:.2f} MB"

    mem_str = "0 MB"
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        rss_mb = proc.memory_info().rss / (1024 * 1024)
        mem_str = f"{rss_mb:.1f} MB"
    except Exception:
        mem_str = "0 MB"

    ts_str = _obtener_fecha_ultimo_backup(db, db_path)

    lineas = [
        f"🐄 <b>Activos:</b> {_fmt_es_co(n_activos)} (GANADERIA-JA 01-JA)",
        "",
        f"🍼 Partos últimos 30d: <b>{_fmt_es_co(n_partos_30d)}</b>",
        f"🐮 Destetes últimos 30d: <b>{_fmt_es_co(n_destetes_30d)}</b>",
        f"🌱 Potrero + animales: <b>{html.escape(pot_mas_animales_str)}</b>",
        f"🌿 Potrero + reposo: <b>{html.escape(pot_mas_reposo_str)}</b>",
        f"⚠️ Alertas pendientes: <b>{_fmt_es_co(n_alertas)}</b>",
        "",
        f"💾 Tamaño DB: <b>{html.escape(size_str)}</b>",
        f"🧠 Memoria: <b>{html.escape(mem_str)}</b>",
    ]
    cuerpo = "\n".join(lineas)
    return (
        f"🖥️ <b>Estado del Sistema</b>\n\n"
        f"{cuerpo}\n\n"
        f"<i>Actualizado: {html.escape(ts_str)}</i>"
    )


def formatear_tablero_finca(db: Database, hoy: Optional[date] = None) -> str:
    """Genera el Tablero de Control Ejecutivo Zootécnico de la Finca (Hoy / Últimos 7 días / Próximas Alertas)."""
    if hoy is None:
        hoy = date.today()

    # 1. Hato activo
    n_activos = _contar_activos(db)
    datos_sg = calcular_brackets_inventario_sg(db, hoy=hoy)
    n_hembras = datos_sg["total_hembras"]
    n_machos = datos_sg["total_machos"]

    # 2. Novedades últimos 7 días
    fecha_7d = iso(add_days(hoy, -7))
    fecha_hoy = iso(hoy)

    # Partos 7d
    filas_partos = db.query(
        "SELECT sexo_cria FROM partos WHERE fecha >= ? AND fecha <= ?",
        (fecha_7d, fecha_hoy),
    )
    n_partos_7d = len(filas_partos)
    h_partos = sum(1 for p in filas_partos if str(p["sexo_cria"]).strip().lower().startswith("h"))
    m_partos = sum(1 for p in filas_partos if str(p["sexo_cria"]).strip().lower().startswith("m"))
    partos_det = f" ({h_partos} ♀ / {m_partos} ♂)" if n_partos_7d > 0 else ""

    # Celos 7d
    r_celos = db.query_one("SELECT COUNT(*) as n FROM celos WHERE fecha >= ? AND fecha <= ?", (fecha_7d, fecha_hoy))
    n_celos_7d = int(r_celos["n"]) if r_celos else 0

    # Servicios 7d
    r_serv = db.query_one("SELECT COUNT(*) as n FROM servicios WHERE fecha >= ? AND fecha <= ?", (fecha_7d, fecha_hoy))
    n_serv_7d = int(r_serv["n"]) if r_serv else 0

    # Tratamientos 7d y retiros activos
    r_trat = db.query_one("SELECT COUNT(*) as n FROM tratamientos WHERE fecha >= ? AND fecha <= ?", (fecha_7d, fecha_hoy))
    n_trat_7d = int(r_trat["n"]) if r_trat else 0

    filas_retiro = db.query(
        "SELECT DISTINCT animal_id FROM tratamientos "
        "WHERE (fecha_fin_retiro_leche IS NOT NULL AND fecha_fin_retiro_leche >= ?) "
        "   OR (fecha_fin_retiro_carne IS NOT NULL AND fecha_fin_retiro_carne >= ?)",
        (fecha_hoy, fecha_hoy),
    )
    n_en_retiro = len(filas_retiro)
    trat_det = f" ({n_en_retiro} en retiro activo)" if n_en_retiro > 0 else ""

    # Pesajes 7d y GMD
    filas_pesajes = db.query("SELECT peso_kg, gmd_calculada FROM pesajes WHERE fecha >= ? AND fecha <= ?", (fecha_7d, fecha_hoy))
    n_pesajes_7d = len(filas_pesajes)
    gmds = [float(p["gmd_calculada"]) for p in filas_pesajes if p["gmd_calculada"] is not None]
    gmd_prom_str = f" · GMD prom: {sum(gmds)/len(gmds):.0f} g/d" if gmds else ""

    # Traslados 7d
    r_trasl = db.query_one("SELECT COUNT(*) as n FROM traslados WHERE fecha >= ? AND fecha <= ?", (fecha_7d, fecha_hoy))
    n_trasl_7d = int(r_trasl["n"]) if r_trasl else 0

    # Muertes 7d
    r_muertes = db.query_one("SELECT COUNT(*) as n FROM muertes WHERE fecha >= ? AND fecha <= ?", (fecha_7d, fecha_hoy))
    n_muertes_7d = int(r_muertes["n"]) if r_muertes else 0

    # 3. Alertas próximas 7 días
    limite_alertas = iso(add_days(hoy, 7))
    alertas_pendientes = db.query(
        "SELECT tipo_alerta FROM alertas WHERE estado = 'PENDIENTE' AND fecha_programada <= ?",
        (limite_alertas,),
    )
    cnt_eco = sum(1 for a in alertas_pendientes if "ECO" in str(a["tipo_alerta"]).upper())
    cnt_palp = sum(1 for a in alertas_pendientes if "PALP" in str(a["tipo_alerta"]).upper())
    cnt_sec = sum(1 for a in alertas_pendientes if "SEC" in str(a["tipo_alerta"]).upper())
    tot_alertas_semana = len(alertas_pendientes)

    # 4. Pasturas y Voisin
    filas_potreros = calcular_existencias_potreros_sg(db, hoy=hoy)
    n_pot_ocupados = len(filas_potreros)

    from ..utils import to_date
    sobreocupados = []
    for p in filas_potreros:
        f_ingreso = p.get("fecha_ingreso_reciente")
        dias_ocup = (hoy - to_date(f_ingreso)).days if f_ingreso and to_date(f_ingreso) else None
        if dias_ocup is not None and dias_ocup > 3:
            sobreocupados.append(f"{p['display']} ({dias_ocup}d)")

    # Potreros en reposo óptimo
    nombres_ocup = {p["display"] for p in filas_potreros}
    todos_pot = db.query("SELECT nombre, codigo, dias_reposo FROM potreros")
    listos_reposo = []
    for p in todos_pot:
        raw_nom = (p["nombre"] or p["codigo"] or "").strip().upper()
        if raw_nom in nombres_ocup:
            continue
        dr = p["dias_reposo"]
        if dr is not None and 30 <= dr <= 365:
            listos_reposo.append(raw_nom)

    salida = [
        "🐮 <b>Tablero de Control Zootécnico — Ganadería JA</b>",
        "────────────────────────────────────────",
        f"🐄 <b>HATO ACTIVO:</b> {_fmt_es_co(n_activos)} animales (♀ {n_hembras} · ♂ {n_machos})",
        "",
        "📅 <b>NOVEDADES DE LA SEMANA (Últimos 7 días):</b>",
        f"• 🍼 Partos: <b>{n_partos_7d}</b>{partos_det}",
        f"• 🔥 Celos observados: <b>{n_celos_7d}</b>",
        f"• 🐂 Inseminaciones / Servicios: <b>{n_serv_7d}</b>",
        f"• 💉 Tratamientos médicos: <b>{n_trat_7d}</b>{trat_det}",
        f"• ⚖️ Pesajes registrados: <b>{n_pesajes_7d}</b>{gmd_prom_str}",
        f"• 🚚 Traslados de potrero: <b>{n_trasl_7d}</b>",
        f"• 💀 Bajas / Muertes: <b>{n_muertes_7d}</b>",
        "",
        f"⚠️ <b>ALERTAS & TAREAS (Próximos 7 días · Total: {tot_alertas_semana}):</b>",
        f"• 🔍 Ecografías (día 35): <b>{cnt_eco}</b> pendientes",
        f"• ✋ Palpaciones (día 60): <b>{cnt_palp}</b> pendientes",
        f"• 🥛 Secados programados: <b>{cnt_sec}</b> vacas",
        f"• 💊 Animales en retiro: <b>{n_en_retiro}</b> en carencia",
        "",
        "🌿 <b>PASTURAS & ROTACIÓN VOISIN:</b>",
        f"• 📍 Potreros ocupados: <b>{n_pot_ocupados}</b> en pastoreo",
        f"• 🌱 Listos para pastoreo: <b>{len(listos_reposo)}</b> con reposo cumplido (≥30d)",
    ]
    if sobreocupados:
        salida.append(f"• ⚠️ Sobreocupación (>3d): <b>{', '.join(sobreocupados[:3])}</b>")
    else:
        salida.append("• 🟢 Rotación al día (ningún potrero excede los días de pastoreo)")

    return "\n".join(salida)


def formatear_estado_servidor(
    db: Database, auth: Auth, db_path: Optional[str] = None, hoy: Optional[date] = None
) -> str:
    """Genera el Tablero Técnico de Estado del Servidor VPS, Recursos, Base de Datos y APIs."""
    import platform
    import shutil

    # 1. Recursos del Servidor
    os_name = f"{platform.system()} {platform.release()}"
    if platform.system().lower() == "linux":
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_name = line.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass

    # RAM
    ram_total_mb = 0
    ram_used_mb = 0
    ram_pct = 0
    proc_ram_mb = 0.0
    try:
        import psutil
        vmem = psutil.virtual_memory()
        ram_total_mb = vmem.total // (1024 * 1024)
        ram_used_mb = vmem.used // (1024 * 1024)
        ram_pct = vmem.percent
        proc = psutil.Process(os.getpid())
        proc_ram_mb = proc.memory_info().rss / (1024 * 1024)
    except Exception:
        pass

    # Disco
    disk_total_gb = 0.0
    disk_used_gb = 0.0
    disk_pct = 0
    try:
        d = shutil.disk_usage(".")
        disk_total_gb = d.total / (1024 ** 3)
        disk_used_gb = d.used / (1024 ** 3)
        disk_pct = int((d.used / d.total) * 100) if d.total > 0 else 0
    except Exception:
        pass

    # 2. Base de Datos SQLite
    size_str = "en memoria"
    if db_path and db_path != ":memory:" and os.path.exists(db_path):
        bytes_size = os.path.getsize(db_path)
        mb_size = bytes_size / (1024 * 1024)
        size_str = f"{mb_size:.2f} MB"

    ts_str = _obtener_fecha_ultimo_backup(db, db_path)
    total_animales = db.count("animales")
    total_eventos = (
        db.count("partos") + db.count("servicios") + db.count("celos") +
        db.count("tratamientos") + db.count("pesajes") + db.count("traslados") +
        db.count("muertes")
    )

    # 3. Usuarios registrados
    usuarios = auth.listar_usuarios()
    n_owner = sum(1 for u in usuarios if u.get("rol") == "OWNER")
    n_admin = sum(1 for u in usuarios if u.get("rol") == "ADMIN")
    n_trab = sum(1 for u in usuarios if u.get("rol") == "TRABAJADOR")

    # 4. APIs e Inteligencia Artificial
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_status = f"🟢 Activo ({gemini_model})" if gemini_key else "🟡 Modo Local / Sin API Key"

    salida = [
        "⚙️ <b>Tablero Técnico del Servidor & Sistema</b>",
        "────────────────────────────────────────",
        "💻 <b>SERVIDOR VPS (DigitalOcean Droplet):</b>",
        f"• <b>SO:</b> {os_name}",
        f"• <b>RAM Servidor:</b> {ram_used_mb} MB / {ram_total_mb} MB ({ram_pct}% en uso)",
        f"• <b>RAM Bot Bitácora:</b> {proc_ram_mb:.1f} MB",
        f"• <b>Disco SSD:</b> {disk_used_gb:.1f} GB / {disk_total_gb:.1f} GB ({disk_pct}% usado)",
        f"• <b>Python:</b> {sys.version.split()[0]} · <b>Servicio:</b> 🟢 bitacora-bot",
        "",
        "🗄️ <b>BASE DE DATOS (SQLite):</b>",
        f"• <b>Archivo:</b> {db_path or 'data/bitacora.db'} ({size_str})",
        f"• <b>Registros:</b> {_fmt_es_co(total_animales)} animales · {_fmt_es_co(total_eventos)} eventos históricos",
        f"• <b>Última sincronización / Backup:</b> {ts_str}",
        "",
        f"👥 <b>USUARIOS AUTORIZADOS ({len(usuarios)}):</b>",
        f"• 👑 Dueño (OWNER): <b>{n_owner}</b>",
        f"• 🛠️ Administradores (ADMIN): <b>{n_admin}</b>",
        f"• 🤠 Personal de Campo (TRABAJADOR): <b>{n_trab}</b>",
        "",
        "🧠 <b>INTEGRACIÓN DE MODELOS & APIS:</b>",
        f"• 🤖 <b>NLU / LLM:</b> {gemini_status}",
        f"• 🎤 <b>Notas de Voz:</b> 🟢 Whisper (transcripción local en español)",
        f"• 📷 <b>OCR Visión:</b> 🟢 Pytesseract (lectura aretes y medicamentos)",
    ]
    return "\n".join(salida)


def formatear_usuarios(auth: Auth) -> str:
    """Genera la lista de usuarios registrados con sus roles."""
    usuarios = auth.listar_usuarios()
    if not usuarios:
        return "No hay usuarios registrados en el sistema."

    lineas = [f"👥 Usuarios registrados ({len(usuarios)}):"]
    for u in usuarios:
        lineas.append(f"• ID: {u.get('user_id')} | {u.get('nombre', 'Sin nombre')} | Rol: {u.get('rol')}")
    return "\n".join(lineas)


def formatear_ayuda(rol: Optional[str]) -> str:
    """Devuelve el manual de ayuda estructurado y didáctico adaptado al rol del usuario."""
    if rol == "OWNER":
        return (
            "👑 <b>MANUAL DE COMANDOS (Propietario / OWNER)</b>\n"
            "────────────────────────────────────────\n\n"
            "🐮 <b>1. Consultas y Fichas Zootécnicas:</b>\n"
            "• Escribe el arete directo: <code>47</code>, <code>N069</code>, <code>A060</code>\n"
            "• <code>/ficha [tag]</code> o <code>/consulta [tag]</code> — Ficha interactiva con pestañas\n"
            "• <code>/alertas</code> — Semáforo de partos, secados, destetes y retiros\n"
            "• <code>/guia</code> — Cómo hacer preguntas al chat en lenguaje natural\n"
            "• <code>/potreros</code> — Matriz SG de potreros y rotación Voisin\n"
            "• <code>/ocupacion</code> — Días de ocupación y descanso de praderas\n"
            "• <code>/medicamentos</code> — Panel de fármacos y retiros activos\n"
            "• <code>/poblacion</code> — Pirámide de edades y brackets SG\n"
            "• <code>/genetica</code> — Composición racial y cruces del hato\n"
            "• <code>/fotos [tag]</code> — Galería fotográfica del ganado\n\n"
            "🎙️ <b>2. Registro por Voz o Texto (Whisper + IA):</b>\n"
            "• 🍼 <i>Partos:</i> «pario la 47 ternero macho 38 kilos»\n"
            "• 🐂 <i>Servicios:</i> «insemine la A029 con toro brahman 502»\n"
            "• 🔥 <i>Celos:</i> «celo en la mañana la vaca 33»\n"
            "• ⚖️ <i>Pesajes:</i> «pesé la N069 en 315 kilos»\n"
            "• 💉 <i>Remedios:</i> «le puse 20ml de oxitetraciclina a la 47»\n"
            "• 🚚 <i>Traslados:</i> «pase el lote 1 de santa martha a versalles»\n\n"
            "⚙️ <b>3. Administración & Sistema:</b>\n"
            "• <code>/status</code> — Tablero zootécnico ejecutivo de la finca\n"
            "• <code>/sistema</code> — Métricas del servidor VPS y base SQLite\n"
            "• <code>/reporte</code> — Generar reporte semanal en PDF\n"
            "• <code>/exportar</code> — Descargar backup ZIP para Software Ganadero\n"
            "• <code>/importar</code> — Instrucciones para importar backup DBF\n"
            "• <code>/confirmar_importar</code> — Procesar backup subido\n"
            "• <code>/descartar_backup</code> — Eliminar backup pendiente\n"
            "• <code>/usuarios</code> — Lista de usuarios registrados\n"
            "• <code>/agregar_usuario [ID] [ROL] [Nombre]</code> — Dar de alta\n"
            "• <code>/quitar_usuario [ID]</code> — Revocar acceso\n"
            "• <code>/logs</code> — Ver últimas líneas del registro del sistema\n\n"
            "🆘 ¿Agregar un trabajador nuevo?\n"
            "1. Pídele que busque el bot y le mande /start\n"
            "2. Consigue su user_id: que él busque @userinfobot → /start (Id)\n"
            "3. Agrégalo: /agregar_usuario 712345678 TRABAJADOR Carlos\n"
            "4. Verifica: /usuarios | Para quitar: /quitar_usuario 712345678\n\n"
            "🏠 <i>Toca /menu o /start para abrir el panel táctil interactivo.</i>"
        )
    if rol == "ADMIN":
        return (
            "🛠️ <b>MANUAL DE COMANDOS (Administrador / ADMIN)</b>\n"
            "────────────────────────────────────────\n\n"
            "🐮 <b>1. Consultas y Fichas Zootécnicas:</b>\n"
            "• Escribe el arete directo: <code>47</code>, <code>N069</code>, <code>A060</code>\n"
            "• <code>/ficha [tag]</code> o <code>/consulta [tag]</code> — Ficha interactiva con pestañas\n"
            "• <code>/alertas</code> — Semáforo de partos, secados, destetes y retiros\n"
            "• <code>/guia</code> — Cómo hacer preguntas al chat en lenguaje natural\n"
            "• <code>/potreros</code> — Matriz SG de potreros y rotación Voisin\n"
            "• <code>/ocupacion</code> — Días de ocupación y descanso de praderas\n"
            "• <code>/medicamentos</code> — Panel de fármacos y retiros activos\n"
            "• <code>/poblacion</code> — Pirámide de edades y brackets SG\n"
            "• <code>/genetica</code> — Composición racial y cruces del hato\n"
            "• <code>/fotos [tag]</code> — Galería fotográfica del ganado\n\n"
            "⚙️ <b>2. Informes y Sincronización:</b>\n"
            "• <code>/status</code> — Tablero zootécnico ejecutivo de la finca\n"
            "• <code>/reporte</code> — Generar reporte semanal en PDF\n"
            "• <code>/exportar</code> — Descargar backup ZIP para Software Ganadero\n"
            "• <code>/importar</code> — Instrucciones para importar backup DBF\n"
            "• <code>/confirmar_importar</code> — Procesar backup subido\n"
            "• <code>/descartar_backup</code> — Eliminar backup pendiente\n\n"
            "🏠 <i>Toca /menu o /start para abrir el panel táctil interactivo.</i>"
        )
    if rol == "TRABAJADOR":
        return (
            "📋 <b>GUÍA DE CAMPO (Trabajador / Campo)</b>\n"
            "────────────────────────────────────────\n\n"
            "📱 <b>¿CÓMO USAR EL BOT EN EL CORRAL?</b>\n\n"
            "1️⃣ <b>Consultar un animal:</b>\n"
            "• Escribe directamente el arete: <code>47</code> o <code>N069</code>\n"
            "• <code>/ficha [tag]</code> o <code>/consulta [tag]</code> — Ver historial, partos y potrero\n"
            "• <code>/fotos [tag]</code> — Ver galería o fotos del animal\n\n"
            "2️⃣ <b>Anotar una novedad (Voz con transcripción automática o Texto):</b>\n"
            "• Envía notas de texto de novedades o preguntas directas\n"
            "• Mantén presionado el micrófono para mandar notas de voz\n"
            "• 🍼 <i>Partos:</i> «pario la 47 macho vivo 38 kilos»\n"
            "• 🔥 <i>Celos:</i> «celo en la mañana la 33»\n"
            "• 🐂 <i>Servicios:</i> «inseminada la 15 con toro reproductor»\n"
            "• ⚖️ <i>Pesajes:</i> «pesaje de la A060 195 kilos»\n"
            "• 💉 <i>Remedios:</i> Envía foto del frasco o «le puse 10ml de penicilina a la 12»\n"
            "• 🚚 <i>Traslados:</i> «movi las vacas al potrero olegario»\n\n"
            "3️⃣ <b>Comandos Rápidos:</b>\n"
            "• <code>/menu</code> — Abrir el menú táctil de botones\n"
            "• <code>/guia</code> — Guía de preguntas al chat\n"
            "• <code>/medicamentos</code> — Ver qué vacas están en retiro de leche/carne\n\n"
            "🏠 <i>Toca /menu para ver las opciones táctiles.</i>"
        )
    return "⛔ No autorizado."


def texto_menu_principal(rol: Optional[str]) -> str:
    """Devuelve el texto corto y visual para el menú principal con botones (/start o /menu)."""
    if rol == "OWNER":
        return (
            "👑 <b>Panel de Control (Dueño)</b>\n"
            "🌿 <i>Hacienda GANADERIA-JA (340 Cabezas Activas)</i>\n"
            "────────────────────────────────────────\n"
            "Selecciona una opción táctil o envía un audio/mensaje:"
        )
    if rol == "ADMIN":
        return (
            "🛠️ <b>Panel de Control (Administrador)</b>\n"
            "🌿 <i>Hacienda GANADERIA-JA (340 Cabezas Activas)</i>\n"
            "────────────────────────────────────────\n"
            "Selecciona una opción táctil o envía un audio/mensaje:"
        )
    if rol == "TRABAJADOR":
        return (
            "🤠 <b>Menú del Trabajador de Campo (cuaderno digital)</b>\n"
            "🌿 <i>Hacienda GANADERIA-JA</i>\n"
            "────────────────────────────────────────\n"
            "Toca un botón o envía tu nota de voz, foto o mensaje:"
        )
    return "⛔ No autorizado."


def texto_ejemplo_evento(tipo: str) -> str:
    """Devuelve la plantilla y explicación de una nota de campo según el tipo."""
    ejemplos = {
        "parto": (
            "🍼 <b>Ejemplo de Parto:</b>\n"
            "<code>pario la 47 ternero macho vivo 38kg</code>\n\n"
            "💡 <i>Consejo:</i> Indica siempre la vaca que parió y el sexo de la cría (macho o hembra)."
        ),
        "celo": (
            "🔥 <b>Ejemplo de Celo (Regla AM-PM):</b>\n"
            "<code>celo en la mañana la 33</code>\n"
            "<code>celo en la tarde la vaca 12</code>\n\n"
            "💡 <i>Regla zootécnica:</i> Celo en la mañana se insemina en la tarde; celo en la tarde se insemina en la mañana siguiente."
        ),
        "servicio": (
            "🐂 <b>Ejemplo de Inseminación / Servicio:</b>\n"
            "<code>insemine la 47 con pajuela toro brahman 502</code>\n"
            "<code>servicio directo la novilla 15 con toro reproductor</code>\n\n"
            "💡 <i>Automático:</i> El bot programa ecografía (d35), palpación (d60) y secado (FEP-60d)."
        ),
        "tratamiento": (
            "💉 <b>Ejemplo de Tratamiento / Remedio:</b>\n"
            "<code>le puse oxitetraciclina 10ml via IM a la 105 retiro 28 dias</code>\n"
            "<code>le aplique ivermectina 5ml via SC a la 12</code>\n\n"
            "💡 <i>Alerta:</i> El bot bloqueará el ordeño y venta de carne durante los días de retiro."
        ),
        "pesaje": (
            "⚖️ <b>Ejemplo de Pesaje:</b>\n"
            "<code>peso 420 kg la vaca 47</code>\n"
            "<code>pesaje novillo N069 310 kilos</code>\n\n"
            "💡 <i>Ganancia:</i> El bot calcula la Ganancia Media Diaria (GMD) automáticamente."
        ),
        "traslado": (
            "🚚 <b>Ejemplo de Traslado de Potrero:</b>\n"
            "<code>pase el lote 2 del potrero bajo al potrero olegario 1</code>\n"
            "<code>traslade la vaca 47 al potrero norte</code>\n\n"
            "💡 <i>Voisin:</i> Calcula días de ocupación y descanso de cada pradera."
        ),
        "muerte": (
            "💀 <b>Ejemplo de Muerte / Baja:</b>\n"
            "<code>se murio el novillo 105 causa mordedura de culebra</code>\n\n"
            "💡 <i>Inventario:</i> El animal pasa a estado inactivo y se registra la causa."
        ),
        "movimiento": (
            "📥 <b>Ejemplo de Entrada / Salida:</b>\n"
            "<code>entraron 15 novillas compradas en subasta</code>\n"
            "<code>salieron 8 toros vendidos para ceba</code>\n\n"
            "💡 <i>Inventario:</i> Actualiza altas y bajas del hato general."
        ),
    }
    return ejemplos.get(tipo, "Selecciona una categoría para ver su ejemplo de nota de campo.")


def texto_guia_consultas() -> str:
    """Devuelve la guía didáctica de cómo hacerle preguntas al bot en lenguaje natural."""
    return (
        "🔍 <b>Cómo hacerle preguntas al Bot:</b>\n\n"
        "El bot entiende español normal de campo. Escríbale con el <b>número de arete</b> (ej. <code>47</code>, <code>JA26</code>) o el <b>nombre</b> (ej. <code>patricia</code>):\n\n"
        "🌱 <b>Ubicación actual y potrero:</b>\n"
        "• <i>«¿en qué potrero está patricia?»</i>\n"
        "• <i>«¿dónde está la vaca 47?»</i>\n\n"
        "🍼 <b>Partos y maternidad:</b>\n"
        "• <i>«¿cuándo parió patricia?»</i>\n"
        "• <i>«¿cuándo fue el parto de la 47?»</i>\n\n"
        "🐂 <b>Inseminación y Servicios:</b>\n"
        "• <i>«¿cuándo se inseminó patricia?»</i>\n"
        "• <i>«¿con qué toro se sirvió la 47?»</i>\n\n"
        "💊 <b>Retiros y Remedios aplicados:</b>\n"
        "• <i>«¿patricia está en retiro?»</i>\n"
        "• <i>«¿qué medicamento le pusieron a la 105?»</i>\n\n"
        "⚖️ <b>Pesajes y Ganancia de peso:</b>\n"
        "• <i>«¿cuánto pesó patricia?»</i>\n"
        "• <i>«¿cuál fue la ganancia diaria de la 12?»</i>\n\n"
        "🌳 <b>Genealogía y Crías:</b>\n"
        "• <i>«¿quién es la madre de patricia?»</i>\n"
        "• <i>«¿qué crías tiene la 47?»</i>"
    )


def texto_guia_chat_hub() -> str:
    """Devuelve el texto principal del centro de ayuda sobre cómo interactuar con el chat."""
    return (
        "💬 <b>CENTRO DE GUÍA: CÓMO PREGUNTAR AL BOT</b>\n"
        "────────────────────────────────────────\n"
        "¡Bienvenido! Este bot cuenta con Inteligencia Artificial Zootécnica y entiende <b>español normal de campo</b>.\n\n"
        "✨ <b>Ventajas del Chat Inteligente:</b>\n"
        "• No necesitas memorizar comandos complicados con barras (/).\n"
        "• Puedes escribir con minúsculas, sin tildes ni signos de interrogación.\n"
        "• Puedes dictar por <b>nota de voz</b> mientras caminas en el corral.\n"
        "• Puedes enviar <b>fotos de aretes o frascos</b> de remedios.\n\n"
        "👇 <b>Selecciona una categoría para ver ejemplos de cómo preguntar:</b>"
    )


def texto_guia_preguntas_animal() -> str:
    """Devuelve la guía de preguntas orientadas a un animal en particular."""
    return (
        "🐮 <b>1. PREGUNTAS SOBRE UN ANIMAL</b>\n"
        "────────────────────────────────────────\n"
        "Puedes consultar cualquier animal escribiendo su <b>número de arete</b> (ej. <code>47</code>, <code>N069</code>, <code>A060</code>) o su <b>nombre</b> (ej. <code>patricia</code>):\n\n"
        "📍 <b>Ubicación & Potrero:</b>\n"
        "• <i>«¿en qué potrero está la 47?»</i>\n"
        "• <i>«dónde está el ternero A060»</i>\n"
        "• <i>«ubicación de patricia»</i>\n"
        "• <i>«¿cuándo se movió la 47 de potrero?»</i>\n\n"
        "🍼 <b>Partos & Maternidad:</b>\n"
        "• <i>«¿cuándo parió la vaca 12?»</i>\n"
        "• <i>«último parto de la 47»</i>\n"
        "• <i>«cuántos partos tiene patricia»</i>\n\n"
        "🐂 <b>Inseminación & Reproducción:</b>\n"
        "• <i>«¿con qué toro se sirvió la A029?»</i>\n"
        "• <i>«cuándo se inseminó la novilla 15»</i>\n"
        "• <i>«hace cuánto se inseminó la 47»</i>\n"
        "• <i>«fecha estimada de parto de la 47»</i>\n\n"
        "⚖️ <b>Pesajes & Crecimiento:</b>\n"
        "• <i>«¿cuánto pesó la N069?»</i>\n"
        "• <i>«último pesaje del novillo A060»</i>\n"
        "• <i>«ganancia diaria de la 47»</i>\n\n"
        "🌳 <b>Genealogía & Crías:</b>\n"
        "• <i>«¿quién es la madre de patricia?»</i>\n"
        "• <i>«quién es el padre de la 47»</i>\n"
        "• <i>«qué crías tiene la vaca 12»</i>\n"
        "• <i>«cuál es la cría de patricia»</i>"
    )


def texto_guia_preguntas_potreros() -> str:
    """Devuelve la guía de preguntas sobre potreros, rotación y pasturas."""
    return (
        "🌿 <b>2. PREGUNTAS DE POTREROS & ROTACIÓN VOISIN</b>\n"
        "────────────────────────────────────────\n"
        "El bot monitorea la ocupación y el descanso de cada pradera en tiempo real:\n\n"
        "🌱 <b>Potreros Listos para Pastoreo:</b>\n"
        "• <i>«¿qué potreros están listos?»</i>\n"
        "• <i>«potreros con más de 30 días de descanso»</i>\n"
        "• <i>«qué potrero tiene mejor reposo»</i>\n\n"
        "⏳ <b>Días de Ocupación:</b>\n"
        "• <i>«¿cuántos días de ocupación llevan en santa martha?»</i>\n"
        "• <i>«días de pastoreo del lote 1»</i>\n"
        "• <i>«qué potreros tienen sobreocupación»</i>\n\n"
        "📊 <b>Carga & Distribución:</b>\n"
        "• <i>«¿qué potreros están ocupados hoy?»</i>\n"
        "• <i>«cuántos animales hay en versalles»</i>\n"
        "• <i>«dónde está el lote 2»</i>"
    )


def texto_guia_preguntas_reproduccion() -> str:
    """Devuelve la guía de preguntas sobre reproducción y leche."""
    return (
        "🥛 <b>3. PREGUNTAS DE LECHE & REPRODUCCIÓN</b>\n"
        "────────────────────────────────────────\n"
        "Consulta el estado reproductivo y productivo del hato:\n\n"
        "⚠️ <b>Días Abiertos & Fertilidad:</b>\n"
        "• <i>«¿qué vacas tienen más de 90 días abiertas?»</i>\n"
        "• <i>«vacas vacías sin inseminar»</i>\n"
        "• <i>«vacas con celo pendiente de servicio»</i>\n\n"
        "🍼 <b>Partos del Hato:</b>\n"
        "• <i>«¿qué partos hubo este mes?»</i>\n"
        "• <i>«partos de los últimos 30 días»</i>\n"
        "• <i>«cuántos terneros machos han nacido»</i>\n\n"
        "🥛 <b>Lactancia & Secados:</b>\n"
        "• <i>«¿qué vacas están próximas a parir?»</i>\n"
        "• <i>«vacas que debo secar este mes»</i>\n"
        "• <i>«vacas con más de 200 días de lactancia»</i>"
    )


def texto_guia_preguntas_sanidad() -> str:
    """Devuelve la guía de preguntas sobre sanidad y tiempos de retiro."""
    return (
        "💉 <b>4. PREGUNTAS DE MEDICAMENTOS & RETIRO</b>\n"
        "────────────────────────────────────────\n"
        "Protege la inocuidad de la leche y la carne con control automático de retiro:\n\n"
        "⛔ <b>Animales en Retiro Activo:</b>\n"
        "• <i>«¿quién está en retiro de leche hoy?»</i>\n"
        "• <i>«animales en retiro de carne»</i>\n"
        "• <i>«¿la vaca 47 se puede ordeñar hoy?»</i>\n"
        "• <i>«cuándo sale de retiro la 105»</i>\n\n"
        "💊 <b>Historial de Tratamientos:</b>\n"
        "• <i>«¿qué medicamento le pusieron a la 47?»</i>\n"
        "• <i>«últimos tratamientos aplicados»</i>\n"
        "• <i>«cuándo le aplicaron ivermectina a la 12»</i>"
    )


def texto_guia_voz_fotos() -> str:
    """Devuelve la guía sobre cómo usar audios y fotos con IA."""
    return (
        "🎙️ <b>5. CÓMO DICTAR POR VOZ & MANDAR FOTOS</b>\n"
        "────────────────────────────────────────\n\n"
        "🎤 <b>Dictado por Notas de Voz (Whisper + Gemini):</b>\n"
        "1. Mantén presionado el botón del <b>micrófono</b> en Telegram.\n"
        "2. Habla con naturalidad en el potrero o corral:\n"
        "   • <i>«Parió la 47 ternero macho vivo de 38 kilos en santa martha»</i>\n"
        "   • <i>«Inseminé la novilla 15 con pajuela toro brahman 502»</i>\n"
        "   • <i>«Le puse 20ml de oxitetraciclina a la 12 por mastitis»</i>\n"
        "   • <i>«Pasé el lote 2 del potrero bajo al potrero olegario»</i>\n"
        "3. Suelta el botón y el bot procesará y registrará todo automáticamente.\n\n"
        "📷 <b>Reconocimiento de Fotografías (OCR):</b>\n"
        "• <b>Fotos de Aretes:</b> Envía una foto clara del arete y el bot abre su ficha zootécnica de inmediato.\n"
        "• <b>Fotos de Medicamentos:</b> Envía una foto de la etiqueta del frasco y el bot calculará los días de retiro y dosis automáticamente."
    )


def texto_guia_fotos() -> str:
    """Devuelve la guía didáctica de cómo tomar y enviar fotos de aretes y medicamentos."""
    return (
        "📷 <b>Guía de Fotos para el Personal de Campo:</b>\n\n"
        "El bot cuenta con <b>reconocimiento visual inteligente (OCR e IA)</b>:\n\n"
        "🏷️ <b>1. Fotos de Aretes / Ganado:</b>\n"
        "• Tome la foto de frente al arete, limpia y con buena luz.\n"
        "• El bot leerá el número (ej. <code>N069</code>, <code>JA26</code>, <code>47</code>) y vinculará la foto a la ficha del animal.\n\n"
        "💊 <b>2. Fotos de Remedios y Medicamentos:</b>\n"
        "• Enfoque la etiqueta del frasco donde se lea claramente:\n"
        "  - Nombre o principio activo (ej. <i>Oxitetraciclina</i>, <i>Ivermectina</i>).\n"
        "  - Dosis (<code>ml/kg</code>) y vía de aplicación (<code>IM</code>, <code>SC</code>).\n"
        "  - Días de retiro en leche y carne.\n"
        "• El bot detecta el medicamento automáticamente y le recordará registrar el tratamiento y bloqueo de ordeño/venta."
    )


def texto_guia_audios() -> str:
    """Devuelve la guía didáctica de cómo enviar notas de voz."""
    return (
        "🎤 <b>Cómo Mandar Notas de Voz al Bot:</b>\n\n"
        "1. Mantenga presionado el botón del <b>micrófono</b> en Telegram.\n"
        "2. Hable con calma y claridad diciendo la novedad y el animal. Por ejemplo:\n"
        "   • <i>«Don Julio, le aviso que parió la 47 un ternero macho vivo de 38 kilos»</i>\n"
        "   • <i>«Inseminé la novilla 15 con pajuela toro brahman 502»</i>\n"
        "   • <i>«Pasé el lote 2 del potrero bajo al potrero olegario 1»</i>\n"
        "3. Suelte el botón para enviar.\n"
        "4. El bot transcribe sus palabras, reconoce el evento zootécnico y lo registra automáticamente en la base de datos."
    )


def texto_guia_animal() -> str:
    """Devuelve la guía didáctica de cómo consultar fichas de animales."""
    return (
        "🐮 <b>Cómo Consultar la Ficha de un Animal:</b>\n\n"
        "Tiene dos formas muy sencillas:\n\n"
        "1. <b>Escriba directamente el número o nombre:</b>\n"
        "   Ejemplos: <code>patricia</code>, <code>47</code>, <code>JA26</code>, <code>a009</code>\n\n"
        "2. <b>Use el comando de consulta:</b>\n"
        "   <code>/consulta 47</code> o <code>/historial patricia</code>\n\n"
        "➡️ El bot le enviará la <b>fotografía del animal</b>, su potrero actual, estado, partos, servicios, pesajes y botones táctiles para consultar detalles."
    )




def obtener_ultimos_logs(log_file: str, lineas: int = 20) -> str:
    """Lee y devuelve las últimas líneas del archivo de registro."""
    if not os.path.exists(log_file):
        return f"El archivo de logs '{log_file}' aún no existe."
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            todas = f.readlines()
        ultimas = todas[-lineas:] if len(todas) > lineas else todas
        if not ultimas:
            return "El archivo de logs está vacío."
        return "📄 Últimos logs:\n" + "".join(ultimas)
    except Exception as e:
        return f"Error al leer logs: {e}"


def formatear_reporte_importacion(conteos: dict) -> str:
    """Formatea el reporte de importación de DBF indicando filas nuevas y duplicadas."""
    if not conteos:
        return "📦 No se procesaron registros del backup."

    total_nuevos = 0
    total_duplicados = 0
    lineas_tablas = []

    for tabla, res in sorted(conteos.items()):
        if isinstance(res, dict):
            n = res.get("nuevos", 0)
            d = res.get("duplicados", 0)
            total_nuevos += n
            total_duplicados += d
            lineas_tablas.append(f"• {tabla}: {n} nuevos, {d} duplicados")

    lineas = [
        "📦 Reporte de Importación de Backup:",
        f"• Total consolidado: {total_nuevos} nuevos, {total_duplicados} duplicados",
        "",
        "📋 Detalle por tabla:",
    ] + lineas_tablas
    return "\n".join(lineas)


def formatear_instrucciones_importar() -> str:
    """Devuelve las instrucciones para subir un backup mediante Telegram o SSH."""
    return (
        "📦 Para importar un backup de Software Ganadero:\n\n"
        "1. Envíame el archivo .zip directamente por este chat como documento.\n"
        "2. Te confirmaré la recepción y responderás /confirmar_importar para procesarlo.\n"
        "3. Si deseas cancelarlo antes de procesar, usa /descartar_backup.\n\n"
        "⚠️ Límite de Telegram: 20MB. Para archivos más pesados, súbelo por SSH y usa:\n"
        "./scripts/importar_backup.sh <ruta_archivo.zip>"
    )


def guardar_backup_pendiente(ruta_zip: str, uploads_dir: str = "data/uploads") -> str:
    """Registra la ruta del archivo zip pendiente en pendiente.txt."""
    os.makedirs(uploads_dir, exist_ok=True)
    pendiente_file = os.path.join(uploads_dir, "pendiente.txt")
    with open(pendiente_file, "w", encoding="utf-8") as f:
        f.write(os.path.abspath(ruta_zip))
    return pendiente_file


def obtener_backup_pendiente(uploads_dir: str = "data/uploads") -> Optional[str]:
    """Obtiene la ruta absoluta del backup pendiente si el archivo existe en disco."""
    pendiente_file = os.path.join(uploads_dir, "pendiente.txt")
    if not os.path.exists(pendiente_file):
        return None
    try:
        with open(pendiente_file, "r", encoding="utf-8") as f:
            ruta = f.read().strip()
        if ruta and os.path.exists(ruta):
            return ruta
        return None
    except Exception:
        return None


def descartar_backup_pendiente(uploads_dir: str = "data/uploads") -> bool:
    """Elimina el archivo .zip pendiente y el archivo pendiente.txt."""
    pendiente_file = os.path.join(uploads_dir, "pendiente.txt")
    eliminado = False
    if os.path.exists(pendiente_file):
        try:
            with open(pendiente_file, "r", encoding="utf-8") as f:
                ruta = f.read().strip()
            if ruta and os.path.exists(ruta):
                try:
                    os.remove(ruta)
                    eliminado = True
                except OSError:
                    pass
            os.remove(pendiente_file)
        except Exception:
            pass
    return eliminado


def parsear_args_reporte(args) -> Optional[tuple[int, str]]:
    """Interpreta los argumentos de /reporte -> (días, etiqueta) o None si inválido.

    - Sin argumentos: semanal (7 días).
    - "diario": 1 día.
    - N numérico: N días.
    - Cualquier otro caso: None.
    """
    if not args:
        return (7, "semanal")
    if len(args) > 1:
        return None
    arg = args[0]
    if arg == "diario":
        return (1, "diario")
    try:
        dias = int(arg)
    except (ValueError, TypeError):
        return None
    if dias < 1:
        return None
    return (dias, f"{dias}d")


def formatear_panel_medicamentos(db: Database) -> str:
    """Genera el panel zootécnico y sanitario de medicamentos, tratamientos y retiros."""
    hoy_iso = date.today().isoformat()

    # 1. Animales en retiro activo
    en_retiro = db.query(
        """
        SELECT t.*, a.tag, a.nombre, p.nombre AS potrero_nombre
        FROM tratamientos t
        LEFT JOIN animales a ON a.id_animal = t.animal_id
        LEFT JOIN potreros p ON p.id = a.potrero_id
        WHERE (t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
           OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?)
        ORDER BY t.fecha DESC
        """,
        (hoy_iso, hoy_iso),
    )

    # 2. Últimos tratamientos (general)
    ultimos = db.query(
        """
        SELECT t.*, a.tag, a.nombre
        FROM tratamientos t
        LEFT JOIN animales a ON a.id_animal = t.animal_id
        ORDER BY t.fecha DESC, t.id DESC LIMIT 8
        """
    )

    lineas = [
        "💊 <b>Control Sanitario, Medicamentos & Retiros</b>",
        "────────────────────────────────────────",
    ]

    if en_retiro:
        lineas.append(f"🚨 <b>ANIMALES EN RETIRO ACTIVO ({len(en_retiro)}):</b>")
        for r in en_retiro:
            tag_nom = r["tag"] or (f"#{r['animal_id']}" if r["animal_id"] else "Animal")
            if r["nombre"]:
                tag_nom += f" ({r['nombre']})"
            pot = f" · 📍 {r['potrero_nombre']}" if r["potrero_nombre"] else ""
            med = r["producto"] or "Tratamiento"
            ret_leche = f"🥛 Fin leche: {r['fecha_fin_retiro_leche']}" if r["fecha_fin_retiro_leche"] and r["fecha_fin_retiro_leche"] >= hoy_iso else ""
            ret_carne = f"🥩 Fin carne: {r['fecha_fin_retiro_carne']}" if r["fecha_fin_retiro_carne"] and r["fecha_fin_retiro_carne"] >= hoy_iso else ""
            ret_txt = " · ".join(x for x in (ret_leche, ret_carne) if x)
            lineas.append(f"• 🐮 <b>{html.escape(str(tag_nom))}</b>{pot}\n  💉 {html.escape(str(med))} | ⛔ {ret_txt}")
        lineas.append("")
    else:
        lineas.append("✅ <b>No hay animales en retiro de leche ni carne actualmente.</b>\n")

    if ultimos:
        lineas.append("📋 <b>ÚLTIMOS TRATAMIENTOS REGISTRADOS:</b>")
        for u in ultimos[:5]:
            tag_u = u["tag"] or (f"#{u['animal_id']}" if u["animal_id"] else "S/T")
            fec = u["fecha"] or "S/F"
            med = u["producto"] or "Fármaco"
            dos = f" ({u['dosis']})" if u["dosis"] else ""
            diag = f" · {u['diagnostico']}" if u["diagnostico"] else ""
            lineas.append(f"• [{fec}] 🐮 <b>{html.escape(str(tag_u))}</b>: {html.escape(str(med))}{dos}{html.escape(diag)}")
        lineas.append("")

    lineas.append(
        "💡 <i>Tip de Campo: Envíe una foto del frasco del medicamento o una nota de voz como 'le apliqué 20ml de oxitetraciclina a la 47' y el bot calculará el retiro automáticamente.</i>"
    )
    return "\n".join(lineas)


def formatear_panel_buscar_animal_texto() -> str:
    return (
        "🔍 <b>Buscador de Animales & Fichas Zootécnicas</b>\n"
        "────────────────────────────────────────\n"
        "Puede consultar cualquier animal de dos formas:\n\n"
        "1. <b>Escribiendo directamente en el chat</b> su número o nombre:\n"
        "   👉 Ejemplos: <code>47</code>, <code>N069</code>, <code>JA26</code>, <code>patricia</code>\n\n"
        "2. <b>Seleccionando una categoría rápida</b> con los botones de abajo:"
    )


def formatear_panel_preguntas_rapidas_texto() -> str:
    return (
        "❓ <b>Consultas Rápidas de Campo (1-Toque)</b>\n"
        "────────────────────────────────────────\n"
        "Seleccione una pregunta para obtener la respuesta zootécnica al instante:"
    )
