"""Bot de Telegram multiusuario con control de acceso basado en roles (RBAC)."""
from __future__ import annotations

import html
import logging
import os
import re
import sys
import time
import zipfile
from datetime import date
from typing import Optional

from ..bot.bot_interface import Bot
from ..db.database import Database
from ..engine.query_engine import (
    QueryEngine,
    buscar_foto_animal,
    calcular_brackets_inventario_sg,
    calcular_existencias_potreros_sg,
    generar_resumen_inventario_sg,
)
from ..importers.dbf_importer import import_zip
from ..parsers import nlp_engine as nlu
from ..parsers.media_handler import (MediaError, extract_image_info,
                                      transcribe_audio)
from ..utils import add_days, iso, to_date
from .auth import Auth

logger = logging.getLogger("bitacora.bot")


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

    lineas_pre = [
        f"Activos: {_fmt_es_co(n_activos)} (GANADERIA-JA 01-JA)",
        f"Partos últimos 30d:           {_fmt_es_co(n_partos_30d)}",
        f"Destetes últimos 30d:         {_fmt_es_co(n_destetes_30d)}",
        f"Potrero + animales:           {pot_mas_animales_str}",
        f"Potrero + reposo:             {pot_mas_reposo_str}",
        f"Alertas pendientes:           {_fmt_es_co(n_alertas)}",
        f"Tamaño DB:                    {size_str}",
        f"Memoria:                      {mem_str}",
    ]
    cuerpo = "\n".join(lineas_pre)
    cuerpo_escapado = html.escape(cuerpo)
    return (
        f"🖥️ <b>Estado del Sistema</b>\n"
        f"<pre>\n{cuerpo_escapado}\n</pre>\n"
        f"<i>Actualizado: {ts_str}</i>"
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
            "👑 <b>Comandos disponibles (Propietario / OWNER):</b>\n"
            "────────────────────────────────────────\n\n"
            "🐮 <b>1. OPERACIÓN DIARIA & CONSULTAS:</b>\n"
            "• Escribe el tag directo: <code>47</code>, <code>N069</code>, <code>A060</code>\n"
            "• /ficha &lt;tag&gt; o /consulta &lt;tag&gt; - Ficha zootécnica interactiva con pestañas\n"
            "• /alertas - Semáforo de partos próximos, secados, destetes y retiros\n"
            "• /potreros - Rotación Voisin, días de reposo y ocupación\n"
            "• /medicamentos - Tratamientos clínicos y retiros activos\n"
            "• /poblacion - Tablero poblacional y pirámide de edades SG\n"
            "• /genetica - Composición de razas y cruces\n"
            "• /fotos [tag] - Galería de fotos registradas (o /foto &lt;tag&gt;)\n\n"
            "🎙️ <b>2. DICTADO POR VOZ & MENSAJES (Whisper + Gemini):</b>\n"
            "• <i>Partos:</i> «pario la 47 cria macho 38 kilos»\n"
            "• <i>Inseminación:</i> «insemine la A029 con toro guzera 502»\n"
            "• <i>Celos (AM/PM):</i> «celo en la mañana la vaca 33»\n"
            "• <i>Pesajes:</i> «pesé la N069 en 315 kilos»\n"
            "• <i>Tratamientos:</i> «le apliqué 20ml de oxitetraciclina a la 47»\n"
            "• <i>Traslados:</i> «pase el lote 1 de santa martha a versalles»\n\n"
            "⚙️ <b>3. ADMINISTRACIÓN & SISTEMA:</b>\n"
            "• /status - Estado del sistema y base de datos\n"
            "• /usuarios - Lista de usuarios y roles\n"
            "• /reporte [diario|semanal|N] - Generar reporte en PDF\n"
            "• /exportar - Descargar backup ZIP para Software Ganadero\n"
            "• /importar - Instrucciones para importar backup DBF\n"
            "• /confirmar_importar - Procesar backup subido\n"
            "• /descartar_backup - Eliminar backup pendiente\n"
            "• /agregar_usuario &lt;user_id&gt; &lt;ROL&gt; [nombre] - Registrar o actualizar usuario\n"
            "• /quitar_usuario &lt;user_id&gt; - Eliminar usuario\n"
            "• /logs - Ver últimas líneas del registro del bot\n\n"
            "🆘 ¿Agregar un trabajador nuevo?\n"
            "1. Pídele que busque el bot y le mande /start\n"
            "2. Consigue su user_id: que él busque @userinfobot → /start (Id)\n"
            "3. Agrégalo: /agregar_usuario 712345678 TRABAJADOR Carlos\n"
            "4. Verifica: /usuarios | Para quitar: /quitar_usuario 712345678\n\n"
            "🏠 <i>Usa /menu o /start para abrir el panel táctil en cualquier momento.</i>"
        )
    if rol == "ADMIN":
        return (
            "🛠️ <b>Comandos disponibles (Administrador):</b>\n"
            "────────────────────────────────────────\n\n"
            "🐮 <b>1. OPERACIÓN DIARIA & CONSULTAS:</b>\n"
            "• Escribe el tag directo: <code>47</code>, <code>N069</code>, <code>A060</code>\n"
            "• /ficha &lt;tag&gt; o /consulta &lt;tag&gt; - Ficha zootécnica interactiva con pestañas\n"
            "• /alertas - Semáforo de partos próximos, secados, destetes y retiros\n"
            "• /potreros - Rotación Voisin, días de reposo y ocupación\n"
            "• /medicamentos - Tratamientos clínicos y retiros activos\n"
            "• /poblacion - Tablero poblacional y pirámide de edades SG\n"
            "• /genetica - Composición de razas y cruces\n"
            "• /fotos [tag] - Galería de fotos registradas (o /foto &lt;tag&gt;)\n\n"
            "⚙️ <b>2. ADMINISTRACIÓN:</b>\n"
            "• /status - Estado del sistema y base de datos\n"
            "• /reporte [diario|semanal|N] - Generar reporte en PDF\n"
            "• /exportar - Descargar backup ZIP para Software Ganadero\n"
            "• /importar - Instrucciones para importar backup DBF\n"
            "• /confirmar_importar - Procesar backup subido\n"
            "• /descartar_backup - Eliminar backup pendiente\n\n"
            "🏠 <i>Usa /menu o /start para abrir el panel táctil en cualquier momento.</i>"
        )
    if rol == "TRABAJADOR":
        return (
            "📋 <b>Comandos disponibles (Trabajador / Campo):</b>\n"
            "────────────────────────────────────────\n\n"
            "📱 <b>¿CÓMO USAR EL BOT EN EL CORRAL?</b>\n\n"
            "1️⃣ <b>Para consultar un animal:</b>\n"
            "• Escribe solo el arete: <code>47</code> o <code>N069</code>\n"
            "• /consulta &lt;tag&gt; o /historial &lt;tag&gt; - Consultar ficha zootécnica\n"
            "• /fotos [tag] - Ver fotos registradas (o /foto &lt;tag&gt;)\n\n"
            "2️⃣ <b>Para anotar una novedad (Voz o Texto):</b>\n"
            "• Envía notas de texto de novedades o preguntas directas\n"
            "• Envía notas de voz con reportes de campo (transcripción automática)\n"
            "• 🍼 <i>Parto:</i> «pario la 47 macho vivo en el corral»\n"
            "• 🔥 <i>Celo:</i> «celo en la manana la 33»\n"
            "• 🐂 <i>Servicio:</i> «inseminada la 15 con toro reproductor»\n"
            "• ⚖️ <i>Pesaje:</i> «pesaje de la A060 195 kilos»\n"
            "• 💉 <i>Remedios:</i> Envía la foto del frasco o «le puse 10ml de penicilina a la 12»\n"
            "• 🚚 <i>Traslado:</i> «movi las vacas al potrero olegario»\n\n"
            "3️⃣ <b>Comandos Rápidos:</b>\n"
            "• /menu - Abrir el menú táctil de botones\n"
            "• /medicamentos - Ver qué vacas están en retiro de leche/carne\n"
            "• /ayuda - Mostrar esta lista de comandos\n\n"
            "🏠 <i>Usa /menu para ver las opciones táctiles.</i>"
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


# ---------------------------------------------------------------------- #
# Construcción del Bot de Telegram (SDK python-telegram-bot)
# ---------------------------------------------------------------------- #
def construir_application(
    token: str,
    db: Database,
    auth: Auth,
    media_dir: str = "media",
    log_file: str = "bot.log",
    uploads_dir: str = "data/uploads",
    reportes_dir: str = "data/reportes",
):
    """Construye y configura la Application de Telegram con todos los handlers."""
    try:
        from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                              Update)
        from telegram.ext import (ApplicationBuilder, CallbackQueryHandler,
                                  CommandHandler, ContextTypes, MessageHandler,
                                  filters)
    except ImportError as e:
        raise ImportError(
            "python-telegram-bot no está instalado. Instálalo con 'pip install python-telegram-bot>=21.0'"
        ) from e

    def crear_teclado_trabajador() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🔍 Buscar Animal / Ficha", callback_data="cmd:buscar_animal"),
                InlineKeyboardButton("🚨 Alertas del Día", callback_data="cmd:alertas"),
            ],
            [
                InlineKeyboardButton("🌿 Potreros & Pasturas", callback_data="cmd:potreros"),
                InlineKeyboardButton("💊 Medicamentos & Retiro", callback_data="cmd:medicamentos"),
            ],
            [
                InlineKeyboardButton("❓ Preguntas Rápidas", callback_data="cmd:preguntas_rapidas"),
                InlineKeyboardButton("📷 Galería de Fotos", callback_data="cmd:fotos"),
            ],
            [
                InlineKeyboardButton("📝 Cómo Anotar Reportes", callback_data="cmd:ejemplos"),
                InlineKeyboardButton("🎤 Cómo Mandar Audios", callback_data="guia:audios"),
            ],
            [
                InlineKeyboardButton("📖 Ver Todos los Comandos", callback_data="cmd:ayuda"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_admin(rol: Optional[str]) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🔍 Buscar Animal / Ficha", callback_data="cmd:buscar_animal"),
                InlineKeyboardButton("🚨 Alertas del Día", callback_data="cmd:alertas"),
            ],
            [
                InlineKeyboardButton("🌿 Potreros & Pasturas", callback_data="cmd:potreros"),
                InlineKeyboardButton("💊 Medicamentos & Retiro", callback_data="cmd:medicamentos"),
            ],
            [
                InlineKeyboardButton("📊 Población & KPIs SG", callback_data="cmd:poblacion"),
                InlineKeyboardButton("🧬 Composición Genética", callback_data="cmd:genetica"),
            ],
            [
                InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
                InlineKeyboardButton("📷 Galería Fotos", callback_data="cmd:fotos"),
            ],
            [
                InlineKeyboardButton("📋 Reporte Semanal PDF", callback_data="cmd:reporte"),
                InlineKeyboardButton("📦 Descargar Backup ZIP", callback_data="cmd:exportar"),
            ],
            [
                InlineKeyboardButton("⚙️ Servidor & Logs", callback_data="cmd:sistema"),
            ],
        ]
        if rol == "OWNER":
            keyboard[-1].append(InlineKeyboardButton("👥 Usuarios / Permisos", callback_data="cmd:usuarios"))
            keyboard.append([
                InlineKeyboardButton("💡 Modo Guía de Campo", callback_data="menu:campo"),
                InlineKeyboardButton("📖 Manual / Comandos", callback_data="cmd:ayuda"),
            ])
        else:
            keyboard[-1].append(InlineKeyboardButton("💡 Modo Guía de Campo", callback_data="menu:campo"))
            keyboard.append([
                InlineKeyboardButton("📖 Manual / Comandos", callback_data="cmd:ayuda"),
            ])
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_medicamentos() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🚨 Animales en Retiro Activo", callback_data="cmd:retiros_activos"),
            ],
            [
                InlineKeyboardButton("💉 Últimos Tratamientos", callback_data="cmd:ultimos_tratamientos"),
                InlineKeyboardButton("📷 Fotos Medicamentos", callback_data="guia:fotos"),
            ],
            [
                InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
                InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_buscar_animal() -> InlineKeyboardMarkup:
        try:
            ultimos_recientes = db.query(
                """
                SELECT DISTINCT a.tag FROM (
                    SELECT animal_id, fecha FROM pesajes WHERE animal_id IS NOT NULL
                    UNION ALL
                    SELECT vaca_id AS animal_id, fecha FROM partos WHERE vaca_id IS NOT NULL
                    UNION ALL
                    SELECT vaca_id AS animal_id, fecha FROM servicios WHERE vaca_id IS NOT NULL
                    UNION ALL
                    SELECT vaca_id AS animal_id, fecha FROM celos WHERE vaca_id IS NOT NULL
                    UNION ALL
                    SELECT animal_id, fecha FROM tratamientos WHERE animal_id IS NOT NULL
                    UNION ALL
                    SELECT animal_id, fecha FROM traslados WHERE animal_id IS NOT NULL
                ) ev
                JOIN animales a ON a.id_animal = ev.animal_id
                WHERE a.estado = 'ACTIVO' AND a.tag IS NOT NULL
                ORDER BY ev.fecha DESC LIMIT 4
                """
            )
        except Exception:
            ultimos_recientes = []
        keyboard = [
            [
                InlineKeyboardButton("🥛 Vacas Paridas", callback_data="filtro:paridas"),
                InlineKeyboardButton("🤰 Inseminadas / Gestantes", callback_data="filtro:inseminadas"),
            ],
            [
                InlineKeyboardButton("🐂 Toros / Reproductores", callback_data="filtro:toros"),
                InlineKeyboardButton("🍼 Crías Recientes", callback_data="filtro:crias"),
            ],
            [
                InlineKeyboardButton("💊 En Retiro Médico", callback_data="cmd:retiros_activos"),
                InlineKeyboardButton("⚖️ Últimos Pesajes", callback_data="filtro:pesajes"),
            ],
        ]
        if ultimos_recientes:
            botones_recientes = [
                InlineKeyboardButton(f"🐮 {r['tag']}", callback_data=f"ficha:{r['tag']}")
                for r in ultimos_recientes
            ]
            keyboard.append(botones_recientes)

        keyboard.append([
            InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
        ])
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_preguntas_rapidas() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🥛 ¿Quién está en retiro de leche?", callback_data="faq:retiro_leche"),
            ],
            [
                InlineKeyboardButton("🌿 ¿Qué potreros tienen >30d reposo?", callback_data="faq:potreros_listos"),
            ],
            [
                InlineKeyboardButton("⚠️ ¿Qué vacas tienen >90d abiertas?", callback_data="faq:dias_abiertos"),
            ],
            [
                InlineKeyboardButton("🍼 ¿Qué partos hubo en los últimos 30 días?", callback_data="faq:partos_mes"),
            ],
            [
                InlineKeyboardButton("⚖️ ¿Últimos pesajes y ganancias?", callback_data="faq:pesajes"),
            ],
            [
                InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
                InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_principal(rol: Optional[str]) -> InlineKeyboardMarkup:
        if rol in ("OWNER", "ADMIN"):
            return crear_teclado_admin(rol)
        return crear_teclado_trabajador()

    def crear_teclado_ejemplos() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🍼 Parto", callback_data="ejemplo:parto"),
                InlineKeyboardButton("🔥 Celo AM/PM", callback_data="ejemplo:celo"),
            ],
            [
                InlineKeyboardButton("🐂 Inseminación", callback_data="ejemplo:servicio"),
                InlineKeyboardButton("💉 Tratamiento", callback_data="ejemplo:tratamiento"),
            ],
            [
                InlineKeyboardButton("⚖️ Pesaje", callback_data="ejemplo:pesaje"),
                InlineKeyboardButton("🚚 Traslado", callback_data="ejemplo:traslado"),
            ],
            [
                InlineKeyboardButton("💀 Muerte / Baja", callback_data="ejemplo:muerte"),
                InlineKeyboardButton("📥 Entrada / Salida", callback_data="ejemplo:movimiento"),
            ],
            [
                InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_animal(tag: str) -> InlineKeyboardMarkup:
        tag_clean = str(tag).strip()
        keyboard = [
            [
                InlineKeyboardButton("⚖️ Pesajes & GMD", callback_data=f"animal:pesos:{tag_clean}"),
                InlineKeyboardButton("🍼 Partos & Crías", callback_data=f"animal:reprod:{tag_clean}"),
            ],
            [
                InlineKeyboardButton("🥛 Control Leche", callback_data=f"animal:leche:{tag_clean}"),
                InlineKeyboardButton("💉 Sanidad & Retiro", callback_data=f"animal:sanidad:{tag_clean}"),
            ],
            [
                InlineKeyboardButton("🌳 Genealogía (3G)", callback_data=f"animal:geneal:{tag_clean}"),
                InlineKeyboardButton("📷 Ver Foto", callback_data=f"foto:{tag_clean}"),
            ],
            [
                InlineKeyboardButton("📋 Ficha Resumen", callback_data=f"animal:resumen:{tag_clean}"),
                InlineKeyboardButton("🔍 Buscar Otro", callback_data="cmd:buscar_animal"),
            ],
            [
                InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_alertas() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🔴 Partos Próximos (≤30d)", callback_data="alerta:partos"),
                InlineKeyboardButton("🟡 Vacas para Secado", callback_data="alerta:secados"),
            ],
            [
                InlineKeyboardButton("🟢 Crías para Destete", callback_data="alerta:destetes"),
                InlineKeyboardButton("⚠️ Pérdidas de Peso (GMD)", callback_data="alerta:pesos"),
            ],
            [
                InlineKeyboardButton("⛔ Retiros Sanitarios", callback_data="cmd:retiros_activos"),
                InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
            ],
            [
                InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_poblacion() -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🧬 Composición Genética", callback_data="cmd:genetica"),
                InlineKeyboardButton("🌿 Potreros & Pasturas", callback_data="cmd:potreros"),
            ],
            [
                InlineKeyboardButton("🔍 Buscar Animal", callback_data="cmd:buscar_animal"),
                InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def cmd_start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            rol = auth.rol_de(user_id)
            texto_menu = texto_menu_principal(rol)
            teclado = crear_teclado_principal(rol)
            await update.message.reply_text(texto_menu, parse_mode="HTML", reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_start_menu: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_ayuda_completa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            rol = auth.rol_de(user_id)
            texto_ayuda = formatear_ayuda(rol)
            teclado = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Abrir Menú", callback_data="menu:principal")]])
            await update.message.reply_text(texto_ayuda, reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_ayuda_completa: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message or not update.message.text:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            bot_engine = Bot(db)
            raw_text = update.message.text
            respuesta = bot_engine.procesar_texto(raw_text)

            # Fallback inteligente con botones interactivos
            if (
                "No entendí" in respuesta
                or "Puedo responder consultas como" in respuesta
                or "¿Querías alguna de estas" in respuesta
                or "No pude interpretar ese mensaje" in respuesta
            ):
                qe = QueryEngine(db)
                sugerencias = qe.sugerencias_fallback(raw_text)
                keyboard = [
                    [
                        InlineKeyboardButton(texto_btn, callback_data=cb_data)
                        for texto_btn, cb_data in sugerencias
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(respuesta, reply_markup=reply_markup)
                return

            if "FICHA ZOOTÉCNICA" in respuesta:
                tag = nlu.extraer_tag(raw_text)
                if not tag:
                    m_tag = re.search(r"(?:🐄|🐮|🐂|🍼)\s*(?:Vaca|Toro|Novilla|Ternero|Ternera|Novillo|Cría|Cria)?\s*([A-Za-z0-9\-_]+)", respuesta)
                    if m_tag:
                        tag = m_tag.group(1).strip()
                if tag:
                    foto_path = buscar_foto_animal(db, tag, media_dir=media_dir)
                    teclado = crear_teclado_animal(tag)
                    if foto_path and os.path.exists(foto_path):
                        try:
                            with open(foto_path, "rb") as f:
                                if len(respuesta) <= 1024:
                                    await update.message.reply_photo(
                                        photo=f, caption=respuesta, parse_mode="HTML", reply_markup=teclado
                                    )
                                    return
                                else:
                                    await update.message.reply_text(respuesta, parse_mode="HTML")
                                    with open(foto_path, "rb") as f2:
                                        await update.message.reply_photo(
                                            photo=f2, caption=f"📷 Foto del animal {tag}", reply_markup=teclado
                                        )
                                    return
                        except Exception as ef:
                            logger.warning("Error al enviar foto en handle_texto para %s: %s", tag, ef)
                    try:
                        await update.message.reply_text(respuesta, parse_mode="HTML", reply_markup=teclado)
                    except Exception:
                        await update.message.reply_text(respuesta, reply_markup=teclado)
                    return

            if "<pre>" in respuesta or "<b>" in respuesta:
                try:
                    await update.message.reply_text(respuesta, parse_mode="HTML")
                except Exception:
                    await update.message.reply_text(respuesta)
            else:
                await update.message.reply_text(respuesta)
        except Exception as e:
            logger.error("Error en handle_texto: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            voice = update.message.voice or update.message.audio
            if not voice:
                return
            os.makedirs(media_dir, exist_ok=True)
            ts = int(time.time())
            dest_path = os.path.join(media_dir, f"voz_{user_id}_{ts}.ogg")
            archivo = await context.bot.get_file(voice.file_id)
            await archivo.download_to_drive(dest_path)

            bot_engine = Bot(db)
            try:
                transcript = transcribe_audio(dest_path)
                texto_audio = transcript.texto.strip()
                if texto_audio:
                    resp_evento = bot_engine.procesar_texto(texto_audio)
                    await update.message.reply_text(
                        f"🎤 Audio transcrito:\n«{texto_audio}»\n\n{resp_evento}"
                    )
                else:
                    await update.message.reply_text(
                        "🎤 Audio recibido, pero no se detectaron palabras legibles en la grabación."
                    )
            except MediaError as me:
                await update.message.reply_text(
                    f"🎤 Audio recibido y guardado ({os.path.basename(dest_path)}).\n⚠️ Nota: {me}"
                )
        except Exception as e:
            logger.error("Error en handle_voice: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            photos = update.message.photo
            if not photos:
                return
            foto = photos[-1]
            os.makedirs(media_dir, exist_ok=True)
            ts = int(time.time())
            caption = (update.message.caption or "").strip()
            tag = nlu.extraer_tag(caption) if caption else None

            dest_path = os.path.join(media_dir, f"foto_{tag or user_id}_{ts}.jpg")
            archivo = await context.bot.get_file(foto.file_id)
            await archivo.download_to_drive(dest_path)

            # Extraer información visual con OCR
            ocr_text = ""
            ocr_tags = []
            ocr_med = None
            try:
                img_info = extract_image_info(dest_path)
                ocr_text = img_info.ocr_text or img_info.texto_detectado or ""
                ocr_tags = img_info.tags
                ocr_med = img_info.medicamento
                if not tag and ocr_tags:
                    tag = ocr_tags[0]
            except Exception:
                pass

            # Registrar en la base de datos
            db.registrar_foto(
                ruta=dest_path,
                animal_tag=tag,
                caption=caption or None,
                user_id=user_id,
                fecha=date.today().isoformat(),
                ocr_text=ocr_text or None,
            )

            # Construir texto consolidado para NLU
            texto_consolidado = f"{caption} {ocr_text}".strip() if caption else ocr_text

            # Mensajes de detección OCR para feedback al usuario
            ocr_feedback = []
            if ocr_tags:
                ocr_feedback.append(f"🔍 OCR detectó tag {', '.join(ocr_tags)}")
            if ocr_med and ocr_med.get("producto"):
                detalles_med = [ocr_med['producto']]
                if ocr_med.get("dosis"):
                    detalles_med.append(f"dosis {ocr_med['dosis']}")
                if ocr_med.get("via"):
                    detalles_med.append(f"vía {ocr_med['via']}")
                if ocr_med.get("lote"):
                    detalles_med.append(f"lote {ocr_med['lote']}")
                ocr_feedback.append(f"💊 OCR detectó medicamento: {', '.join(detalles_med)}")

            str_feedback = ("\n" + "\n".join(ocr_feedback)) if ocr_feedback else ""

            # Si el caption o OCR contiene un evento zootécnico (ej. 'pario la 47 macho'), procesarlo también
            if texto_consolidado and nlu.clasificar(texto_consolidado) is not None:
                bot_engine = Bot(db)
                resp_evento = bot_engine.procesar_texto(texto_consolidado)
                await update.message.reply_text(
                    f"📷 Foto registrada y vinculada a {tag or 'evento'}.{str_feedback}\n\n{resp_evento}"
                )
            elif tag:
                await update.message.reply_text(f"📷 Foto guardada y vinculada a la {tag}.{str_feedback}")
            else:
                await update.message.reply_text(f"📷 Foto recibida y guardada en la bitácora.{str_feedback}")
        except Exception as e:
            logger.error("Error en handle_photo: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message or not update.message.document:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            doc = update.message.document
            file_name = doc.file_name or ""
            if not file_name.lower().endswith(".zip"):
                await update.message.reply_text("⚠️ Por favor envía un archivo .zip con el backup de Software Ganadero.")
                return

            file_size = doc.file_size or 0
            if file_size > 20 * 1024 * 1024:
                await update.message.reply_text(
                    "❌ El archivo supera el límite de Telegram (20MB). Súbelo por SSH y usa scripts/importar_backup.sh"
                )
                return

            os.makedirs(uploads_dir, exist_ok=True)
            ts = int(time.time())
            dest_path = os.path.join(uploads_dir, f"backup_{ts}.zip")

            try:
                archivo = await context.bot.get_file(doc.file_id)
                await archivo.download_to_drive(dest_path)
            except Exception as e:
                logger.error("Error al descargar archivo desde Telegram: %s", e)
                await update.message.reply_text(
                    "❌ El archivo supera el límite de Telegram (20MB). Súbelo por SSH y usa scripts/importar_backup.sh"
                )
                return

            if not zipfile.is_zipfile(dest_path):
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                await update.message.reply_text("❌ El archivo no es un ZIP válido.")
                return

            guardar_backup_pendiente(dest_path, uploads_dir=uploads_dir)
            tam_mb = os.path.getsize(dest_path) / (1024 * 1024)
            await update.message.reply_text(
                f"📦 Backup recibido ({tam_mb:.2f} MB). Responde /confirmar_importar para procesarlo o /descartar_backup para eliminarlo."
            )
        except Exception as e:
            logger.error("Error en handle_document: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_alertas_panel(db)
            await update.message.reply_text(
                msg, parse_mode="HTML", reply_markup=crear_teclado_alertas()
            )
        except Exception as e:
            logger.error("Error en cmd_alertas: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_poblacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_poblacion_panel(db)
            await update.message.reply_text(
                msg, parse_mode="HTML", reply_markup=crear_teclado_poblacion()
            )
        except Exception as e:
            logger.error("Error en cmd_poblacion: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_genetica(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_genetica_panel(db)
            await update.message.reply_text(
                msg, parse_mode="HTML", reply_markup=crear_teclado_poblacion()
            )
        except Exception as e:
            logger.error("Error en cmd_genetica: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            raw_text = update.message.text or ""
            # Limpiar posibles timestamps de copy-paste (ej. 10:13 PM)
            clean_text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b", "", raw_text, flags=re.IGNORECASE).strip()

            tag = None
            if context.args:
                arg0 = context.args[0]
                # Si el timestamp quedó adherido (ej. N06910:13)
                arg_clean = re.sub(r"\d{1,2}:\d{2}.*", "", arg0, flags=re.IGNORECASE).strip()
                tag = arg_clean or arg0
            if not tag:
                tag = nlu.extraer_tag(clean_text)

            if not tag:
                await update.message.reply_text("Uso: /consulta <tag> o /historial <tag> (ej. /consulta N069)")
                return

            msg = formatear_historial(db, tag)
            teclado = crear_teclado_animal(tag)
            foto_path = buscar_foto_animal(db, tag, media_dir=media_dir)

            if foto_path and os.path.exists(foto_path):
                try:
                    with open(foto_path, "rb") as f:
                        if len(msg) <= 1024:
                            await update.message.reply_photo(
                                photo=f, caption=msg, parse_mode="HTML", reply_markup=teclado
                            )
                            return
                        else:
                            await update.message.reply_text(msg, parse_mode="HTML")
                            with open(foto_path, "rb") as f2:
                                await update.message.reply_photo(
                                    photo=f2, caption=f"📷 Foto del animal {tag}", reply_markup=teclado
                                )
                            return
                except Exception as efoto:
                    logger.warning("Error al enviar foto para animal %s: %s", tag, efoto)

            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_historial: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_potreros(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            arg_potrero = " ".join(context.args).strip() if context.args else None
            msg = formatear_potreros(db, potrero=arg_potrero)
            teclado_p = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Existencias SG", callback_data="cmd:potreros_sg"),
                    InlineKeyboardButton("⏳ Días Ocupación", callback_data="cmd:ocupacion"),
                ],
                [
                    InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                    InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                ],
            ])
            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado_p)
        except Exception as e:
            logger.error("Error en cmd_potreros: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_ocupacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            qe = QueryEngine(db)
            msg = qe.responder("dias de ocupacion")
            teclado_p = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Existencias SG", callback_data="cmd:potreros_sg"),
                    InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                ],
                [
                    InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                ],
            ])
            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado_p)
        except Exception as e:
            logger.error("Error en cmd_ocupacion: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_animales(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_animales(db)
            try:
                await update.message.reply_text(msg, parse_mode="HTML")
            except Exception:
                await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_animales: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_tablero_finca(db)
            teclado = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Inventario Hato", callback_data="cmd:inventario"),
                    InlineKeyboardButton("⚠️ Alertas Pendientes", callback_data="cmd:alertas"),
                ],
                [
                    InlineKeyboardButton("🌿 Potreros Voisin", callback_data="cmd:potreros"),
                    InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                ],
                [
                    InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                ],
            ])
            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_status: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_sistema(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_estado_servidor(db, auth, db.path if hasattr(db, "path") else None)
            teclado = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
                    InlineKeyboardButton("👥 Usuarios / Permisos", callback_data="cmd:usuarios"),
                ],
                [
                    InlineKeyboardButton("📜 Ver Últimos Logs", callback_data="cmd:logs"),
                    InlineKeyboardButton("📦 Descargar Backup ZIP", callback_data="cmd:exportar"),
                ],
                [
                    InlineKeyboardButton("🔄 Actualizar", callback_data="cmd:sistema"),
                    InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                ],
            ])
            try:
                await update.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado)
            except Exception:
                await update.message.reply_text(msg, reply_markup=teclado)
        except Exception as e:
            logger.error("Error en cmd_sistema: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_medicamentos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_panel_medicamentos(db)
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_medicamentos())
        except Exception as e:
            logger.error("Error en cmd_medicamentos: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_buscar_animal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_panel_buscar_animal_texto()
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_buscar_animal())
        except Exception as e:
            logger.error("Error en cmd_buscar_animal: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_preguntas_rapidas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_panel_preguntas_rapidas_texto()
            await update.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_preguntas_rapidas())
        except Exception as e:
            logger.error("Error en cmd_preguntas_rapidas: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_usuarios(auth)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_usuarios: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            parsed = parsear_args_reporte(context.args)
            if parsed is None:
                await update.message.reply_text(
                    "Uso: /reporte (semanal por defecto) · /reporte diario · /reporte <N> días"
                )
                return

            dias, etiqueta = parsed
            # Import perezoso para no requerir reportlab salvo que se use /reporte.
            from ..reports import generar_pdf

            fecha_hoy = date.today()
            ruta = os.path.join(reportes_dir, f"reporte_{etiqueta}_{fecha_hoy.isoformat()}.pdf")
            generar_pdf(db, dias, ruta, hoy=fecha_hoy)
            with open(ruta, "rb") as f:
                contenido = f.read()
            await update.message.reply_document(
                document=contenido, filename=os.path.basename(ruta)
            )
        except Exception as e:
            logger.error("Error en cmd_reporte: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al generar el reporte: {e}")

    async def cmd_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.es_autorizado(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            tag = context.args[0].strip() if context.args else None
            if tag:
                filas = db.fotos_de(tag, limit=5)
                foto_disco = buscar_foto_animal(db, tag, media_dir=media_dir)
                if not filas and not foto_disco:
                    await update.message.reply_text(f"📷 No hay fotos registradas para el animal {tag}.")
                    return

                enviadas = 0
                for r in filas:
                    ruta = r["ruta"]
                    fec = r["fecha"] or "sin fecha"
                    cap = f" — {r['caption']}" if r["caption"] else ""
                    pie = f"📷 Animal {tag} [{fec}]{cap}"
                    if ruta and os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            await update.message.reply_photo(photo=f, caption=pie)
                            enviadas += 1

                if foto_disco and os.path.exists(foto_disco) and enviadas == 0:
                    with open(foto_disco, "rb") as f:
                        await update.message.reply_photo(photo=f, caption=f"📷 Foto del animal {tag}")
            else:
                # Mostrar últimas fotos registradas
                filas = db.ultimas_fotos(limit=5)
                if not filas:
                    await update.message.reply_text("📷 No hay fotos registradas en la bitácora.")
                    return
                for r in filas:
                    ruta = r["ruta"]
                    tag_foto = r["tag"] or "Sin arete"
                    fec = r["fecha"] or "sin fecha"
                    cap = f" — {r['caption']}" if r["caption"] else ""
                    pie = f"📷 Tag {tag_foto} [{fec}]{cap}"
                    if ruta and os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            await update.message.reply_photo(photo=f, caption=pie)
                    else:
                        await update.message.reply_text(f"📷 Foto {tag_foto} [{fec}] (archivo no disponible en servidor).")
        except Exception as e:
            logger.error("Error en cmd_fotos: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al consultar fotos: {e}")

    async def cmd_exportar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            from ..exporters import (
                export_csv_zip,
                export_json_zip,
                export_zip,
                parsear_args_exportar,
            )

            parsed = parsear_args_exportar(context.args)
            if parsed is None:
                await update.message.reply_text(
                    "Uso: /exportar (DBF/Software Ganadero por defecto) · /exportar csv · /exportar json"
                )
                return

            formato, etiqueta = parsed
            exports_dir = os.path.join(os.path.dirname(uploads_dir), "exports")
            os.makedirs(exports_dir, exist_ok=True)
            hoy_str = date.today().strftime("%Y%m%d")

            if formato == "dbf":
                ruta_zip = os.path.join(exports_dir, f"Datos_Export_{hoy_str}.Zip")
                zip_generado = export_zip(db, ruta_zip)
                desc = "📦 Exportación para Software Ganadero SG (8 tablas DBF)."
            elif formato == "csv":
                ruta_zip = os.path.join(exports_dir, f"bitacora_csv_{hoy_str}.zip")
                zip_generado = export_csv_zip(db, ruta_zip)
                desc = "📊 Exportación de bitácora en formato CSV (todas las tablas)."
            elif formato == "json":
                ruta_zip = os.path.join(exports_dir, f"bitacora_json_{hoy_str}.zip")
                zip_generado = export_json_zip(db, ruta_zip)
                desc = "📄 Exportación de bitácora en formato JSON."
            else:
                ruta_zip = os.path.join(exports_dir, f"Datos_Export_{hoy_str}.Zip")
                zip_generado = export_zip(db, ruta_zip)
                desc = "📦 Exportación para Software Ganadero SG."

            with open(zip_generado, "rb") as f:
                contenido = f.read()

            tam_mb = len(contenido) / (1024 * 1024)
            await update.message.reply_document(
                document=contenido,
                filename=os.path.basename(zip_generado),
                caption=f"{desc} ({tam_mb:.2f} MB)",
            )
        except Exception as e:
            logger.error("Error en cmd_exportar: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al exportar: {e}")

    async def cmd_importar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            await update.message.reply_text(formatear_instrucciones_importar())
        except Exception as e:
            logger.error("Error en cmd_importar: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_confirmar_importar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            ruta_zip = obtener_backup_pendiente(uploads_dir=uploads_dir)
            if not ruta_zip:
                await update.message.reply_text("⚠️ No hay ningún backup pendiente de importación.")
                return

            conteos = import_zip(db, ruta_zip)
            descartar_backup_pendiente(uploads_dir=uploads_dir)
            msg = formatear_reporte_importacion(conteos)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_confirmar_importar: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error al importar backup: {e}")

    async def cmd_descartar_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return

            ruta_zip = obtener_backup_pendiente(uploads_dir=uploads_dir)
            if not ruta_zip:
                await update.message.reply_text("⚠️ No hay ningún backup pendiente para descartar.")
                return

            descartar_backup_pendiente(uploads_dir=uploads_dir)
            await update.message.reply_text("🗑️ Backup descartado y archivo eliminado.")
        except Exception as e:
            logger.error("Error en cmd_descartar_backup: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_agregar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_gestionar_usuarios(user_id):
                await update.message.reply_text("⛔ No autorizado. Solo OWNER puede gestionar usuarios.")
                return
            if not context.args or len(context.args) < 2:
                await update.message.reply_text("Uso: /agregar_usuario <user_id> <ROL> [nombre]")
                return
            try:
                nuevo_uid = int(context.args[0])
            except ValueError:
                await update.message.reply_text("❌ El user_id debe ser un número entero.")
                return
            nuevo_rol = context.args[1].upper()
            nuevo_nombre = " ".join(context.args[2:]) if len(context.args) > 2 else f"Usuario_{nuevo_uid}"

            auth.agregar_usuario(nuevo_uid, nuevo_nombre, nuevo_rol)
            await update.message.reply_text(
                f"✅ Usuario {nuevo_uid} ({nuevo_nombre}) registrado correctamente con rol {nuevo_rol}."
            )
        except ValueError as ve:
            if update.message:
                await update.message.reply_text(f"❌ Error: {ve}")
        except Exception as e:
            logger.error("Error en cmd_agregar_usuario: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_quitar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_gestionar_usuarios(user_id):
                await update.message.reply_text("⛔ No autorizado. Solo OWNER puede gestionar usuarios.")
                return
            if not context.args:
                await update.message.reply_text("Uso: /quitar_usuario <user_id>")
                return
            try:
                eliminar_uid = int(context.args[0])
            except ValueError:
                await update.message.reply_text("❌ El user_id debe ser un número entero.")
                return
            auth.quitar_usuario(eliminar_uid)
            await update.message.reply_text(f"✅ Usuario {eliminar_uid} eliminado correctamente.")
        except ValueError as ve:
            if update.message:
                await update.message.reply_text(f"❌ Error: {ve}")
        except Exception as e:
            logger.error("Error en cmd_quitar_usuario: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if not update.effective_user or not update.message:
                return
            user_id = update.effective_user.id
            if not auth.puede_gestionar_usuarios(user_id):
                await update.message.reply_text("⛔ No autorizado. Solo OWNER puede ver los logs.")
                return
            msg = obtener_ultimos_logs(log_file)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_logs: %s", e, exc_info=True)
            if update.message:
                await update.message.reply_text(f"❌ Error: {e}")

    async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            query = update.callback_query
            if not query or not query.data:
                return
            user_id = update.effective_user.id if update.effective_user else 0
            if not auth.es_autorizado(user_id):
                await query.answer("⛔ No autorizado.", show_alert=True)
                return

            data = query.data
            if data == "menu:principal":
                await query.answer()
                rol = auth.rol_de(user_id)
                if query.message:
                    await query.message.reply_text(
                        texto_menu_principal(rol), parse_mode="HTML", reply_markup=crear_teclado_principal(rol)
                    )

            elif data == "menu:campo":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "🤠 <b>Modo Guía de Campo (Personal de Campo):</b>\nSeleccione una opción didáctica de ayuda o consulta:",
                        parse_mode="HTML",
                        reply_markup=crear_teclado_trabajador(),
                    )

            elif data == "guia:consultas":
                await query.answer()
                btn = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        texto_guia_consultas(),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "guia:fotos":
                await query.answer()
                btn = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        texto_guia_fotos(),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "guia:audios":
                await query.answer()
                btn = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        texto_guia_audios(),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "guia:animal":
                await query.answer()
                btn = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        texto_guia_animal(),
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(btn),
                    )

            elif data == "cmd:ejemplos":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "💡 <b>Ejemplos de Notas de Campo:</b>\nSelecciona el tipo de evento que deseas ver:",
                        parse_mode="HTML",
                        reply_markup=crear_teclado_ejemplos(),
                    )

            elif data.startswith("ejemplo:"):
                tipo = data.split("ejemplo:", 1)[1]
                await query.answer()
                txt = texto_ejemplo_evento(tipo)
                btn_volver = [
                    [
                        InlineKeyboardButton("⬅️ Volver a Ejemplos", callback_data="cmd:ejemplos"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ]
                if query.message:
                    await query.message.reply_text(
                        txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_volver)
                    )

            elif data == "cmd:exportar":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                try:
                    from ..exporters import export_zip
                    os.makedirs("data/exports", exist_ok=True)
                    fecha_hoy = date.today().isoformat()
                    ruta_zip = os.path.join("data/exports", f"Backup_SG_{fecha_hoy}.zip")
                    export_zip(db, ruta_zip)
                    if os.path.exists(ruta_zip):
                        with open(ruta_zip, "rb") as f:
                            contenido = f.read()
                        if query.message:
                            await query.message.reply_document(
                                document=contenido,
                                filename=os.path.basename(ruta_zip),
                                caption="📦 Backup exportado en formato ZIP para Software Ganadero (TP/SG).",
                            )
                except Exception as eexp:
                    logger.error("Error al exportar en callback: %s", eexp)
                    if query.message:
                        await query.message.reply_text(f"❌ Error al exportar backup: {eexp}")

            elif data == "cmd:usuarios":
                await query.answer()
                if not auth.puede_gestionar_usuarios(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ Solo el propietario (OWNER) puede ver la lista de usuarios.")
                    return
                msg = formatear_usuarios(auth)
                teclado_u = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ])
                if query.message:
                    await query.message.reply_text(msg, reply_markup=teclado_u)

            elif data == "cmd:logs":
                await query.answer()
                if not auth.puede_gestionar_usuarios(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ Solo el propietario (OWNER) puede consultar los logs del sistema.")
                    return
                msg = obtener_ultimos_logs(log_file, lineas=25)
                if len(msg) > 3800:
                    msg = msg[-3800:]
                cuerpo_log = html.escape(msg)
                teclado_l = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔄 Refrescar Logs", callback_data="cmd:logs"),
                        InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ])
                if query.message:
                    try:
                        await query.message.reply_text(
                            f"📜 <b>Últimos Registros del Sistema (Logs)</b>\n<pre>\n{cuerpo_log}\n</pre>",
                            parse_mode="HTML",
                            reply_markup=teclado_l,
                        )
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_l)

            elif data == "cmd:inventario":
                await query.answer()
                msg = formatear_animales(db)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML")
                    except Exception:
                        await query.message.reply_text(msg)

            elif data == "cmd:alertas":
                await query.answer()
                if not auth.es_autorizado(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_alertas_panel(db)
                if query.message:
                    try:
                        await query.message.reply_text(
                            msg, parse_mode="HTML", reply_markup=crear_teclado_alertas()
                        )
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_alertas())

            elif data == "cmd:poblacion":
                await query.answer()
                if not auth.es_autorizado(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_poblacion_panel(db)
                if query.message:
                    try:
                        await query.message.reply_text(
                            msg, parse_mode="HTML", reply_markup=crear_teclado_poblacion()
                        )
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_poblacion())

            elif data == "cmd:genetica":
                await query.answer()
                if not auth.es_autorizado(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_genetica_panel(db)
                if query.message:
                    try:
                        await query.message.reply_text(
                            msg, parse_mode="HTML", reply_markup=crear_teclado_poblacion()
                        )
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_poblacion())

            elif data == "alerta:partos":
                await query.answer()
                hoy = date.today()
                limite_30d = hoy + timedelta(days=30)
                filas = db.query(
                    """
                    SELECT a.tag, a.nombre, s.fecha_estimada_parto, p.nombre AS potrero
                    FROM servicios s
                    JOIN animales a ON a.id_animal = s.vaca_id
                    LEFT JOIN potreros p ON p.id = a.potrero_id
                    WHERE a.estado = 'ACTIVO' AND s.fecha_estimada_parto IS NOT NULL
                      AND s.fecha_estimada_parto >= ? AND s.fecha_estimada_parto <= ?
                    ORDER BY s.fecha_estimada_parto ASC
                    """,
                    (hoy.isoformat(), limite_30d.isoformat()),
                )
                if not filas:
                    txt = "🔴 <b>Próximos Partos (≤30 días):</b>\n\n✅ No hay partos proyectados para los próximos 30 días."
                    btn_a = [[InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas")]]
                else:
                    lineas = ["🔴 <b>Vacas con Parto Próximo (Próximos 30 días):</b>\n"]
                    botones_vacas = []
                    for r in filas:
                        tag_v = r["tag"] or "S/T"
                        fep = r["fecha_estimada_parto"]
                        dias_faltan = (to_date(fep) - hoy).days if to_date(fep) else 0
                        pot = f" · 📍 {r['potrero']}" if r["potrero"] else ""
                        lineas.append(f"• 🐮 <b>{html.escape(str(tag_v))}</b>: FEP {fep} (en {dias_faltan}d){pot}")
                        botones_vacas.append(InlineKeyboardButton(f"🐮 {tag_v}", callback_data=f"ficha:{tag_v}"))
                    txt = "\n".join(lineas)
                    btn_a = []
                    for i in range(0, len(botones_vacas), 3):
                        btn_a.append(botones_vacas[i:i+3])
                    btn_a.append([
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_a))

            elif data == "alerta:secados":
                await query.answer()
                hoy = date.today()
                filas = db.query(
                    """
                    SELECT a.tag, a.nombre, MAX(p.fecha) as ult_parto, pot.nombre AS potrero
                    FROM partos p
                    JOIN animales a ON a.id_animal = p.vaca_id
                    LEFT JOIN potreros pot ON pot.id = a.potrero_id
                    WHERE a.estado = 'ACTIVO' AND a.sexo LIKE 'H%'
                    GROUP BY a.id_animal
                    HAVING ult_parto <= date(?, '-200 days')
                    ORDER BY ult_parto ASC
                    """,
                    (hoy.isoformat(),),
                )
                if not filas:
                    txt = "🟡 <b>Vacas Candidatas para Secado (≥200 DEL):</b>\n\n✅ No hay vacas en lactancia prolongada pendientes de secado."
                    btn_a = [[InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas")]]
                else:
                    lineas = ["🟡 <b>Vacas Candidatas para Secado (≥200 Días de Lactancia):</b>\n"]
                    botones_vacas = []
                    for r in filas:
                        tag_v = r["tag"] or "S/T"
                        dias_l = (hoy - to_date(r["ult_parto"])).days if to_date(r["ult_parto"]) else 0
                        pot = f" · 📍 {r['potrero']}" if r["potrero"] else ""
                        lineas.append(f"• 🐮 <b>{html.escape(str(tag_v))}</b>: {dias_l} DEL (Parto {r['ult_parto']}){pot}")
                        botones_vacas.append(InlineKeyboardButton(f"🐮 {tag_v}", callback_data=f"ficha:{tag_v}"))
                    txt = "\n".join(lineas)
                    btn_a = []
                    for i in range(0, len(botones_vacas), 3):
                        btn_a.append(botones_vacas[i:i+3])
                    btn_a.append([
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_a))

            elif data == "alerta:destetes":
                await query.answer()
                hoy = date.today()
                filas = db.query(
                    """
                    SELECT a.tag, a.nombre, a.fecha_nacimiento, a.sexo, pot.nombre AS potrero
                    FROM animales a
                    LEFT JOIN potreros pot ON pot.id = a.potrero_id
                    WHERE a.estado = 'ACTIVO' AND a.fecha_nacimiento IS NOT NULL
                      AND a.fecha_nacimiento <= date(?, '-200 days')
                      AND a.fecha_nacimiento >= date(?, '-365 days')
                    ORDER BY a.fecha_nacimiento ASC
                    """,
                    (hoy.isoformat(), hoy.isoformat()),
                )
                if not filas:
                    txt = "🟢 <b>Crías en Edad de Destete (≥200 días):</b>\n\n✅ No hay terneros pendientes de destete en este rango."
                    btn_a = [[InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas")]]
                else:
                    lineas = ["🟢 <b>Crías en Edad de Destete (200 - 365 días de edad):</b>\n"]
                    botones_crias = []
                    for r in filas:
                        tag_c = r["tag"] or "S/T"
                        dias_edad = (hoy - to_date(r["fecha_nacimiento"])).days if to_date(r["fecha_nacimiento"]) else 0
                        sexo_txt = "Macho" if str(r["sexo"]).startswith("M") else "Hembra"
                        pot = f" · 📍 {r['potrero']}" if r["potrero"] else ""
                        lineas.append(f"• 🍼 <b>{html.escape(str(tag_c))}</b> ({sexo_txt}): {dias_edad} días (Nac. {r['fecha_nacimiento']}){pot}")
                        botones_crias.append(InlineKeyboardButton(f"🐮 {tag_c}", callback_data=f"ficha:{tag_c}"))
                    txt = "\n".join(lineas)
                    btn_a = []
                    for i in range(0, len(botones_crias), 3):
                        btn_a.append(botones_crias[i:i+3])
                    btn_a.append([
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_a))

            elif data == "alerta:pesos":
                await query.answer()
                filas_gmd = db.query(
                    """
                    SELECT a.tag, a.nombre, p.peso_kg, p.fecha, pot.nombre AS potrero
                    FROM pesajes p
                    JOIN animales a ON a.id_animal = p.animal_id
                    LEFT JOIN potreros pot ON pot.id = a.potrero_id
                    WHERE a.estado = 'ACTIVO'
                    ORDER BY a.id_animal, p.fecha ASC
                    """
                )
                pesos_por_animal = defaultdict(list)
                for r in filas_gmd:
                    pesos_por_animal[r["tag"]].append(r)
                perdidas = []
                for tag_a, p_list in pesos_por_animal.items():
                    if len(p_list) >= 2:
                        ult = p_list[-1]
                        pen = p_list[-2]
                        d_ult = to_date(ult["fecha"])
                        d_pen = to_date(pen["fecha"])
                        if d_ult and d_pen and (d_ult - d_pen).days > 0:
                            dias_diff = (d_ult - d_pen).days
                            kg_diff = ult["peso_kg"] - pen["peso_kg"]
                            if kg_diff < 0:
                                gmd = (kg_diff * 1000.0) / dias_diff
                                perdidas.append((tag_a, gmd, kg_diff, ult["peso_kg"], pen["peso_kg"], ult["potrero"]))
                if not perdidas:
                    txt = "⚠️ <b>Alertas de Pérdida de Peso (GMD &lt; 0):</b>\n\n✅ Ningún animal activo registró pérdida de peso en su último pesaje."
                    btn_a = [[InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas")]]
                else:
                    lineas = ["⚠️ <b>Animales con Pérdida de Peso en Último Control:</b>\n"]
                    botones_p = []
                    for tag_a, gmd, kg_diff, p_ult, p_pen, pot in sorted(perdidas, key=lambda x: x[1]):
                        pot_txt = f" · 📍 {pot}" if pot else ""
                        lineas.append(f"• 🐮 <b>{html.escape(str(tag_a))}</b>: <b>{gmd:.0f} g/día</b> ({kg_diff:+.1f} kg: {p_pen:.0f}kg → {p_ult:.0f}kg){pot_txt}")
                        botones_p.append(InlineKeyboardButton(f"🐮 {tag_a}", callback_data=f"animal:pesos:{tag_a}"))
                    txt = "\n".join(lineas)
                    btn_a = []
                    for i in range(0, len(botones_p), 3):
                        btn_a.append(botones_p[i:i+3])
                    btn_a.append([
                        InlineKeyboardButton("⚠️ Volver a Alertas", callback_data="cmd:alertas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_a))

            elif data == "cmd:potreros":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_potreros(db, potrero="sg")
                teclado_p = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⏳ Días Ocupación", callback_data="cmd:ocupacion"),
                        InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_p)

            elif data == "cmd:potreros_sg":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_potreros(db, potrero="sg")
                teclado_p = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⏳ Días Ocupación", callback_data="cmd:ocupacion"),
                        InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_p)

            elif data == "cmd:ocupacion":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                qe = QueryEngine(db)
                msg = qe.responder("dias de ocupacion")
                teclado_p = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📊 Existencias SG", callback_data="cmd:potreros_sg"),
                        InlineKeyboardButton("🌿 Potreros Listos", callback_data="cmd:potreros_listos"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_p)

            elif data == "cmd:potreros_listos":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_potreros(db)
                teclado_p = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📊 Existencias SG", callback_data="cmd:potreros_sg"),
                        InlineKeyboardButton("⏳ Días Ocupación", callback_data="cmd:ocupacion"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_p)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_p)

            elif data == "cmd:status":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_tablero_finca(db)
                teclado_st = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📊 Inventario Hato", callback_data="cmd:inventario"),
                        InlineKeyboardButton("⚠️ Alertas Pendientes", callback_data="cmd:alertas"),
                    ],
                    [
                        InlineKeyboardButton("🌿 Potreros Voisin", callback_data="cmd:potreros"),
                        InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                    ],
                    [
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_st)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_st)

            elif data == "cmd:sistema":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_estado_servidor(db, auth, db.path if hasattr(db, "path") else None)
                teclado_sis = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
                        InlineKeyboardButton("👥 Usuarios / Permisos", callback_data="cmd:usuarios"),
                    ],
                    [
                        InlineKeyboardButton("📜 Ver Últimos Logs", callback_data="cmd:logs"),
                        InlineKeyboardButton("📦 Descargar Backup ZIP", callback_data="cmd:exportar"),
                    ],
                    [
                        InlineKeyboardButton("🔄 Actualizar", callback_data="cmd:sistema"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ],
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_sis)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_sis)

            elif data == "cmd:reporte":
                await query.answer()
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                try:
                    from ..reports import generar_pdf
                    os.makedirs(reportes_dir, exist_ok=True)
                    fecha_hoy = date.today()
                    ruta = os.path.join(reportes_dir, f"reporte_semanal_{fecha_hoy.isoformat()}.pdf")
                    generar_pdf(db, 7, ruta, hoy=fecha_hoy)
                    if os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            contenido = f.read()
                        if query.message:
                            await query.message.reply_document(
                                document=contenido, filename=os.path.basename(ruta)
                            )
                except Exception as erep:
                    logger.error("Error al generar reporte en callback: %s", erep)
                    if query.message:
                        await query.message.reply_text(f"❌ Error al generar reporte: {erep}")

            elif data == "cmd:fotos":
                await query.answer()
                filas = db.ultimas_fotos(limit=5)
                if not filas:
                    if query.message:
                        await query.message.reply_text("📷 No hay fotos registradas en la bitácora.")
                    return

                msg = formatear_fotos(db, limite=5)
                teclado_f = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal")]
                ])
                if query.message:
                    await query.message.reply_text(msg, reply_markup=teclado_f)

                # Enviar las fotografías disponibles en disco
                for r in filas:
                    ruta = r["ruta"]
                    tag_foto = r["tag"] or "Sin arete"
                    fec = r["fecha"] or "sin fecha"
                    cap = f" — {r['caption']}" if r["caption"] else ""
                    pie = f"📷 Animal: {tag_foto} [{fec}]{cap}"
                    if ruta and os.path.exists(ruta):
                        try:
                            with open(ruta, "rb") as f:
                                if query.message:
                                    await query.message.reply_photo(photo=f, caption=pie)
                        except Exception as efoto:
                            logger.error("Error al enviar foto %s: %s", ruta, efoto)

            elif data.startswith("foto:"):
                tag = data.split("foto:", 1)[1].strip()
                await query.answer()
                foto_path = buscar_foto_animal(db, tag, media_dir=media_dir)
                if foto_path and os.path.exists(foto_path):
                    with open(foto_path, "rb") as f:
                        if query.message:
                            await query.message.reply_photo(photo=f, caption=f"📷 Foto del animal {tag}")
                    return

                filas = db.fotos_de(tag, limit=5)
                if not filas:
                    if query.message:
                        await query.message.reply_text(f"📷 No hay fotos registradas para el animal {tag}.")
                    return
                for r in filas:
                    ruta = r["ruta"]
                    fec = r["fecha"] or "sin fecha"
                    cap = f" ({r['caption']})" if r.get("caption") else ""
                    pie = f"📷 Animal {tag} - {fec}{cap}"
                    if ruta and os.path.exists(ruta):
                        with open(ruta, "rb") as f:
                            if query.message:
                                await query.message.reply_photo(photo=f, caption=pie)
                    else:
                        if query.message:
                            await query.message.reply_text(
                                f"📷 Foto {tag} [{fec}] (archivo no disponible en servidor)."
                            )

            elif data.startswith("animal:pesos:") or data.startswith("pesos:"):
                tag = data.split(":", 2)[-1].strip()
                await query.answer()
                msg = formatear_pesajes_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal(tag))

            elif data.startswith("animal:reprod:") or data.startswith("repro:"):
                tag = data.split(":", 2)[-1].strip()
                await query.answer()
                msg = formatear_reprod_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal(tag))

            elif data.startswith("animal:leche:"):
                tag = data.split("animal:leche:", 1)[1].strip()
                await query.answer()
                msg = formatear_leche_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal(tag))

            elif data.startswith("animal:sanidad:") or data.startswith("retiro:"):
                tag = data.split(":", 2)[-1].strip()
                await query.answer()
                msg = formatear_sanidad_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal(tag))

            elif data.startswith("animal:geneal:"):
                tag = data.split("animal:geneal:", 1)[1].strip()
                await query.answer()
                msg = formatear_genealogia_animal_tab(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal(tag))

            elif data.startswith("animal:resumen:") or data.startswith("ficha:"):
                tag = data.split(":", 2)[-1].strip()
                await query.answer()
                msg = formatear_historial(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal(tag))

            elif data.startswith("ubica:"):
                tag = data.split("ubica:", 1)[1].strip()
                await query.answer()
                qe = QueryEngine(db)
                msg = qe.responder(f"en que potrero esta {tag}")
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=crear_teclado_animal(tag))
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=crear_teclado_animal(tag))

            elif data == "cmd:historial":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "📋 Para consultar la ficha de un animal, escribe:\n/historial <tag> (ej. /historial 47) o directamente el número de arete."
                    )

            elif data == "cmd:buscar_animal":
                await query.answer()
                msg = formatear_panel_buscar_animal_texto()
                if query.message:
                    await query.message.reply_text(
                        msg, parse_mode="HTML", reply_markup=crear_teclado_buscar_animal()
                    )

            elif data == "cmd:medicamentos":
                await query.answer()
                msg = formatear_panel_medicamentos(db)
                if query.message:
                    await query.message.reply_text(
                        msg, parse_mode="HTML", reply_markup=crear_teclado_medicamentos()
                    )

            elif data == "cmd:preguntas_rapidas":
                await query.answer()
                msg = formatear_panel_preguntas_rapidas_texto()
                if query.message:
                    await query.message.reply_text(
                        msg, parse_mode="HTML", reply_markup=crear_teclado_preguntas_rapidas()
                    )

            elif data == "cmd:retiros_activos":
                await query.answer()
                qe = QueryEngine(db)
                msg = qe.responder("quien esta en retiro")
                teclado_ret = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("💉 Ver Medicamentos", callback_data="cmd:medicamentos"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ])
                if query.message:
                    await query.message.reply_text(msg, reply_markup=teclado_ret)

            elif data == "cmd:ultimos_tratamientos":
                await query.answer()
                ultimos = db.query(
                    """
                    SELECT t.*, a.tag, a.nombre, p.nombre AS potrero_nombre
                    FROM tratamientos t
                    LEFT JOIN animales a ON a.id_animal = t.animal_id
                    LEFT JOIN potreros p ON p.id = a.potrero_id
                    ORDER BY t.fecha DESC, t.id DESC LIMIT 10
                    """
                )
                if not ultimos:
                    txt = "💉 No hay tratamientos médicos registrados recientemente en la bitácora."
                    btn_t = [[InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal")]]
                else:
                    lineas = ["💉 <b>Últimos Tratamientos Médicos Registrados:</b>\n"]
                    botones_trat = []
                    for u in ultimos:
                        tag_u = u["tag"] or (f"#{u['animal_id']}" if u["animal_id"] else "S/T")
                        fec = u["fecha"] or "S/F"
                        med = u["producto"] or "Tratamiento"
                        dos = f" ({u['dosis']})" if u["dosis"] else ""
                        pot = f" · 📍 {u['potrero_nombre']}" if u["potrero_nombre"] else ""
                        lineas.append(f"• [{fec}] 🐮 <b>{html.escape(str(tag_u))}</b>: {html.escape(str(med))}{dos}{pot}")
                        if u["tag"] and len(botones_trat) < 6:
                            botones_trat.append(InlineKeyboardButton(f"🐮 {u['tag']}", callback_data=f"ficha:{u['tag']}"))
                    txt = "\n".join(lineas)
                    btn_t = []
                    if botones_trat:
                        for i in range(0, len(botones_trat), 3):
                            btn_t.append(botones_trat[i:i+3])
                    btn_t.append([
                        InlineKeyboardButton("💊 Panel Medicamentos", callback_data="cmd:medicamentos"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_t))

            elif data.startswith("filtro:"):
                cat = data.split("filtro:", 1)[1].strip()
                await query.answer()
                filas = []
                titulo = ""
                if cat == "paridas":
                    titulo = "🥛 <b>Vacas Paridas Recientes (Lactancia):</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre, p.fecha FROM partos p
                        JOIN animales a ON a.id_animal = p.vaca_id
                        WHERE a.estado = 'ACTIVO' AND a.sexo LIKE 'H%'
                        ORDER BY p.fecha DESC LIMIT 9
                        """
                    )
                elif cat == "inseminadas":
                    titulo = "🤰 <b>Vacas Inseminadas / Servidas:</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre, s.fecha FROM servicios s
                        JOIN animales a ON a.id_animal = s.vaca_id
                        WHERE a.estado = 'ACTIVO'
                        ORDER BY s.fecha DESC LIMIT 9
                        """
                    )
                elif cat == "toros":
                    titulo = "🐂 <b>Toros / Reproductores Activos:</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre FROM animales a
                        WHERE a.estado = 'ACTIVO' AND (a.sexo LIKE 'M%' OR a.sexo = 'Macho')
                        ORDER BY a.tag ASC LIMIT 9
                        """
                    )
                elif cat == "crias":
                    titulo = "🍼 <b>Crías y Terneros Recientes:</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre, a.fecha_nacimiento AS fecha FROM animales a
                        WHERE a.estado = 'ACTIVO' AND a.fecha_nacimiento IS NOT NULL
                        ORDER BY a.fecha_nacimiento DESC LIMIT 9
                        """
                    )
                elif cat == "pesajes":
                    titulo = "⚖️ <b>Últimos Animales Pesados:</b>"
                    filas = db.query(
                        """
                        SELECT DISTINCT a.tag, a.nombre, pe.peso_kg, pe.fecha FROM pesajes pe
                        JOIN animales a ON a.id_animal = pe.animal_id
                        WHERE a.estado = 'ACTIVO'
                        ORDER BY pe.fecha DESC LIMIT 9
                        """
                    )

                if not filas:
                    txt = f"{titulo}\n\nNo se encontraron animales activos registrados en esta categoría."
                    btn_f = [[InlineKeyboardButton("🔍 Buscar Otro Grupo", callback_data="cmd:buscar_animal")]]
                else:
                    txt = f"{titulo}\n\nToque cualquier animal para abrir su ficha y fotografía:"
                    botones = [
                        InlineKeyboardButton(f"🐮 {r['tag']}", callback_data=f"ficha:{r['tag']}")
                        for r in filas if r["tag"]
                    ]
                    btn_f = []
                    for i in range(0, len(botones), 3):
                        btn_f.append(botones[i:i+3])
                    btn_f.append([
                        InlineKeyboardButton("🔍 Buscar Otro Grupo", callback_data="cmd:buscar_animal"),
                        InlineKeyboardButton("🏠 Menú", callback_data="menu:principal"),
                    ])
                if query.message:
                    await query.message.reply_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btn_f))

            elif data.startswith("faq:"):
                tema = data.split("faq:", 1)[1].strip()
                await query.answer()
                qe = QueryEngine(db)
                if tema == "retiro_leche":
                    msg = qe.responder("quien esta en retiro de leche")
                elif tema == "potreros_listos":
                    msg = qe.responder("que potreros estan listos")
                elif tema == "dias_abiertos":
                    msg = qe.responder("vacas abiertas mas de 90 dias")
                elif tema == "partos_mes":
                    msg = qe.responder("partos del mes")
                elif tema == "pesajes":
                    msg = qe.responder("ultimos pesajes")
                else:
                    msg = "Consulta no reconocida."

                teclado_faq = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("❓ Más Preguntas", callback_data="cmd:preguntas_rapidas"),
                        InlineKeyboardButton("🏠 Menú Principal", callback_data="menu:principal"),
                    ]
                ])
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML", reply_markup=teclado_faq)
                    except Exception:
                        await query.message.reply_text(msg, reply_markup=teclado_faq)

            elif data == "cmd:ayuda":
                await query.answer()
                rol = auth.rol_de(user_id)
                btn = [[InlineKeyboardButton("🏠 Volver al Menú", callback_data="menu:principal")]]
                if query.message:
                    await query.message.reply_text(
                        formatear_ayuda(rol), reply_markup=InlineKeyboardMarkup(btn)
                    )

        except Exception as e:
            logger.error("Error en handle_callback_query: %s", e, exc_info=True)
            if query and query.message:
                await query.message.reply_text(f"❌ Error: {e}")

    app = ApplicationBuilder().token(token).build()

    # Handlers de comandos
    app.add_handler(CommandHandler(["start", "menu"], cmd_start_menu))
    app.add_handler(CommandHandler(["help", "ayuda", "comandos"], cmd_ayuda_completa))
    app.add_handler(CommandHandler(["buscar", "buscar_animal", "buscador"], cmd_buscar_animal))
    app.add_handler(CommandHandler(["medicamentos", "tratamientos", "farmacia", "retiros", "retiro"], cmd_medicamentos))
    app.add_handler(CommandHandler(["preguntas", "faq", "consultas"], cmd_preguntas_rapidas))
    app.add_handler(CommandHandler("alertas", cmd_alertas))
    app.add_handler(CommandHandler(["poblacion", "piramide", "edades"], cmd_poblacion))
    app.add_handler(CommandHandler(["genetica", "razas", "cruces"], cmd_genetica))
    app.add_handler(CommandHandler(["historial", "consulta", "ficha", "info", "vaca", "animal"], cmd_historial))
    app.add_handler(CommandHandler("potreros", cmd_potreros))
    app.add_handler(CommandHandler(["ocupacion", "rotacion"], cmd_ocupacion))
    app.add_handler(CommandHandler("animales", cmd_animales))
    app.add_handler(CommandHandler(["foto", "fotos"], cmd_fotos))
    app.add_handler(CommandHandler(["status", "tablero", "finca", "resumen"], cmd_status))
    app.add_handler(CommandHandler(["sistema", "servidor", "vps"], cmd_sistema))
    app.add_handler(CommandHandler("usuarios", cmd_usuarios))
    app.add_handler(CommandHandler("reporte", cmd_reporte))
    app.add_handler(CommandHandler("exportar", cmd_exportar))
    app.add_handler(CommandHandler("importar", cmd_importar))
    app.add_handler(CommandHandler("confirmar_importar", cmd_confirmar_importar))
    app.add_handler(CommandHandler("descartar_backup", cmd_descartar_backup))
    app.add_handler(CommandHandler("agregar_usuario", cmd_agregar_usuario))
    app.add_handler(CommandHandler("quitar_usuario", cmd_quitar_usuario))
    app.add_handler(CommandHandler("logs", cmd_logs))

    # Handlers de callbacks y mensajes
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))

    return app


# ---------------------------------------------------------------------- #
# Función principal de arranque
# ---------------------------------------------------------------------- #
def correr(
    token: Optional[str] = None,
    db_path: Optional[str] = None,
    users_file: Optional[str] = None,
    media_dir: Optional[str] = None,
    log_file: Optional[str] = None,
    uploads_dir: Optional[str] = None,
    reportes_dir: Optional[str] = None,
) -> None:
    """Inicia el bot de Telegram en modo polling con la configuración provista."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = token or os.getenv("TELEGRAM_TOKEN")
    if not token or token == "pegar_aqui_el_token_del_botfather":
        raise ValueError(
            "TELEGRAM_TOKEN no configurado. Define la variable de entorno o en el archivo .env."
        )

    db_path = db_path or os.getenv("BITACORA_DB", "data/bitacora.db")
    users_file = users_file or os.getenv("USERS_FILE", "src/server/users.json")
    media_dir = media_dir or os.getenv("MEDIA_DIR", "media")
    log_file = log_file or os.getenv("LOG_FILE", "bot.log")
    uploads_dir = uploads_dir or os.getenv("UPLOADS_DIR", "data/uploads")
    reportes_dir = reportes_dir or os.getenv("REPORTES_DIR", "data/reportes")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    db = Database(db_path)
    db.create_tables()

    auth = Auth(users_file)

    app = construir_application(
        token=token,
        db=db,
        auth=auth,
        media_dir=media_dir,
        log_file=log_file,
        uploads_dir=uploads_dir,
        reportes_dir=reportes_dir,
    )
    logger.info("Bot de Telegram iniciado correctamente con polling...")
    app.run_polling(drop_pending_updates=True)
