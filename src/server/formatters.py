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
def _esc(val: object) -> str:
    """Escapa de forma segura caracteres especiales (&, <, >) para plantillas HTML de Telegram."""
    if val is None:
        return ""
    return html.escape(str(val))


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
        JOIN animales a2 ON a2.id_animal = pe.animal_id
        LEFT JOIN potreros p ON p.id = a2.potrero_id
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
        lineas.append("• O envía una nota de voz dictando el pesaje.")
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
    diagnosticos = db.query(
        "SELECT * FROM diagnosticos_gestacion WHERE vaca_id = ? ORDER BY fecha DESC, id DESC",
        (aid,),
    )

    n_partos = len(partos)
    n_serv = len(servicios)
    n_celos = len(celos)
    n_diags = len(diagnosticos)

    lineas.append(f"• <b>Total Partos:</b> {n_partos} | <b>Servicios:</b> {n_serv} | <b>Diagnósticos:</b> {n_diags} | <b>Celos:</b> {n_celos}")

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

    if diagnosticos:
        ult_d = diagnosticos[0]
        dias_g = ult_d["dias_gestacion"] if "dias_gestacion" in ult_d.keys() else None
        dias_d = f" ({dias_g}d)" if dias_g else ""
        res_ult = ult_d["resultado"] if "resultado" in ult_d.keys() else ult_d["resultado"]
        ico_d = "🤰" if (res_ult or "").upper() == "PREÑADA" else "⭕"
        lineas.append(f"• <b>Último Diagnóstico:</b> [{ult_d['fecha']}] {ico_d} <b>{res_ult}</b>{dias_d}")

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

    if diagnosticos:
        lineas.append("\n🩺 <b>Historial de Diagnósticos de Gestación:</b>")
        for d in diagnosticos[:5]:
            fec = d["fecha"] or "S/F"
            res = d["resultado"] or "PREÑADA"
            ico = "🤰" if res.upper() == "PREÑADA" else "⭕"
            dias_g2 = d["dias_gestacion"] if "dias_gestacion" in d.keys() else None
            dias = f" · {dias_g2}d gestación" if dias_g2 else ""
            lineas.append(f"• [{fec}] {ico} <b>{res}</b>{dias}")

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
        lineas.append("• <b>Alerta de Secado:</b> ⚠️ <i>Supera los 200 días de lactancia. Programar secado si la gestación supera los 220 días.</i>")

    controles = db.historial_leche(aid)
    if controles:
        ultimos = controles[-5:][::-1]
        lineas.append(f"\n🥛 <b>Últimos controles de leche ({len(controles)} total):</b>")
        for c in ultimos:
            litros_str = f"{c['litros']} L" if c["litros"] is not None else "S/D"
            lineas.append(f"  • {c['fecha']}: {litros_str}")
    else:
        lineas.append(
            "\n💡 <i>Sin controles de leche registrados todavía. Registre uno dictando o "
            "escribiendo, ej.: 'la 47 dio 12 litros de leche'.</i>"
        )
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
        JOIN animales a2 ON a2.id_animal = t.animal_id
        LEFT JOIN potreros p ON p.id = a2.potrero_id
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

    cc = db.ultima_condicion_corporal(aid)
    if cc:
        lineas.append(f"📏 <b>Condición Corporal:</b> {cc['valor']} (registrada el {cc['fecha']})")

    if not filas_t:
        lineas.append("\n📋 <i>Sin historial de tratamientos médicos registrados.</i>")
    else:
        lineas.append("\n📋 <b>Últimos Tratamientos Clínicos:</b>")
        for r in filas_t:
            fec = r["fecha"] or "S/F"
            med = r["producto"] or "Tratamiento"
            dos = f" ({r['dosis']})" if r["dosis"] else ""
            via = f" [{r['via']}]" if r["via"] else ""
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
    bisabuelos_p: list[str] = []
    if animal["padre_id"]:
        p_row = db.get_animal(animal["padre_id"])
        if p_row:
            p_nom = f" ({p_row['nombre']})" if p_row["nombre"] else ""
            padre_str = f"{p_row['tag']}{p_nom} [{p_row['raza'] or 'S/D'}]"
            if p_row["padre_id"]:
                ap = db.get_animal(p_row["padre_id"])
                if ap:
                    p_abuelo_p = f"{ap['tag']} [{ap['raza'] or 'S/D'}]"
                    if ap["padre_id"]:
                        bpp = db.get_animal(ap["padre_id"])
                        if bpp:
                            bisabuelos_p.append(f"Bisabuelo Pat. (PP): {bpp['tag']} [{bpp['raza'] or 'S/D'}]")
                    if ap["madre_id"]:
                        bpm = db.get_animal(ap["madre_id"])
                        if bpm:
                            bisabuelos_p.append(f"Bisabuela Pat. (PM): {bpm['tag']} [{bpm['raza'] or 'S/D'}]")
            if p_row["madre_id"]:
                am = db.get_animal(p_row["madre_id"])
                if am:
                    p_abuela_p = f"{am['tag']} [{am['raza'] or 'S/D'}]"
                    if am["padre_id"]:
                        bmp = db.get_animal(am["padre_id"])
                        if bmp:
                            bisabuelos_p.append(f"Bisabuelo Pat. (MP): {bmp['tag']} [{bmp['raza'] or 'S/D'}]")
                    if am["madre_id"]:
                        bmm = db.get_animal(am["madre_id"])
                        if bmm:
                            bisabuelos_p.append(f"Bisabuela Pat. (MM): {bmm['tag']} [{bmm['raza'] or 'S/D'}]")

    madre_str = "Desconocida"
    m_abuelo_m = "Desconocido"
    m_abuela_m = "Desconocida"
    bisabuelos_m: list[str] = []
    if animal["madre_id"]:
        m_row = db.get_animal(animal["madre_id"])
        if m_row:
            m_nom = f" ({m_row['nombre']})" if m_row["nombre"] else ""
            madre_str = f"{m_row['tag']}{m_nom} [{m_row['raza'] or 'S/D'}]"
            if m_row["padre_id"]:
                ap = db.get_animal(m_row["padre_id"])
                if ap:
                    m_abuelo_m = f"{ap['tag']} [{ap['raza'] or 'S/D'}]"
                    if ap["padre_id"]:
                        bpp = db.get_animal(ap["padre_id"])
                        if bpp:
                            bisabuelos_m.append(f"Bisabuelo Mat. (PP): {bpp['tag']} [{bpp['raza'] or 'S/D'}]")
                    if ap["madre_id"]:
                        bpm = db.get_animal(ap["madre_id"])
                        if bpm:
                            bisabuelos_m.append(f"Bisabuela Mat. (PM): {bpm['tag']} [{bpm['raza'] or 'S/D'}]")
            if m_row["madre_id"]:
                am = db.get_animal(m_row["madre_id"])
                if am:
                    m_abuela_m = f"{am['tag']} [{am['raza'] or 'S/D'}]"
                    if am["padre_id"]:
                        bmp = db.get_animal(am["padre_id"])
                        if bmp:
                            bisabuelos_m.append(f"Bisabuelo Mat. (MP): {bmp['tag']} [{bmp['raza'] or 'S/D'}]")
                    if am["madre_id"]:
                        bmm = db.get_animal(am["madre_id"])
                        if bmm:
                            bisabuelos_m.append(f"Bisabuela Mat. (MM): {bmm['tag']} [{bmm['raza'] or 'S/D'}]")

    crias = db.query(
        """
        SELECT a.tag, a.nombre, a.sexo, a.fecha_nacimiento, p.fecha
        FROM animales a
        LEFT JOIN partos p ON p.id_cria = a.id_animal
        WHERE a.madre_id = ? OR a.padre_id = ?
           OR (p.vaca_id = ? AND a.id_animal IS NOT NULL)
        GROUP BY a.id_animal
        ORDER BY COALESCE(p.fecha, a.fecha_nacimiento) DESC, a.id_animal DESC
        """,
        (aid, aid, aid),
    )
    partos_sin_cria = db.query(
        "SELECT 'Sin arete' AS tag, NULL AS nombre, sexo_cria AS sexo, NULL AS fecha_nacimiento, fecha "
        "FROM partos WHERE vaca_id = ? AND id_cria IS NULL ORDER BY fecha DESC",
        (aid,),
    )

    lineas = [
        "🌳 <b>ÁRBOL GENEALÓGICO & TRAZABILIDAD (3G)</b>",
        f"🐄 <b>Genealogía de {tag_str}{nom_txt}</b> · {raza}",
        "────────────────────────────────────────",
        f"🐂 <b>PADRE:</b> {padre_str}",
        f"   ├── 🐂 Abuelo Pat.: {p_abuelo_p}",
        f"   └── 🐄 Abuela Pat.: {p_abuela_p}",
    ]
    if bisabuelos_p:
        for b in bisabuelos_p:
            lineas.append(f"       └── 🧬 {b}")

    lineas.extend([
        "",
        f"🐄 <b>MADRE:</b> {madre_str}",
        f"   ├── 🐂 Abuelo Mat.: {m_abuelo_m}",
        f"   └── 🐄 Abuela Mat.: {m_abuela_m}",
    ])
    if bisabuelos_m:
        for b in bisabuelos_m:
            lineas.append(f"       └── 🧬 {b}")

    lineas.append("────────────────────────────────────────")
    if animal["madre_id"] and animal["padre_id"]:
        try:
            es_consang = db.verificar_consanguinidad(animal["madre_id"], animal["padre_id"])
            if es_consang:
                lineas.append("🧬 <b>Consanguinidad Parental:</b> ⚠️ POSITIVA (padres emparentados en 3G)")
            else:
                lineas.append("🧬 <b>Consanguinidad Parental:</b> ✅ 0.0% (sin parentesco en 3G)")
        except Exception:
            lineas.append("🧬 <b>Consanguinidad Parental:</b> ℹ️ No evaluable")
    else:
        lineas.append("🧬 <b>Consanguinidad Parental:</b> ℹ️ No evaluable (registro incompleto)")
    lineas.append("────────────────────────────────────────")

    todas_crias = list(crias) + list(partos_sin_cria)
    if todas_crias:
        plural_partos = "partos registrados" if len(todas_crias) != 1 else "parto registrado"
        lineas.append(f"🍼 <b>Descendencia / Crías Registradas ({len(todas_crias)} {plural_partos}):</b>")
        for c in todas_crias[:8]:
            c_tag = c["tag"] or "Sin arete"
            c_nom = f" ({c['nombre']})" if c["nombre"] else ""
            c_sx = f" · {c['sexo'].lower()}" if c["sexo"] else ""
            fec = c["fecha"] or c["fecha_nacimiento"]
            c_f = f" [{fec}]" if fec else ""
            lineas.append(f"• 🐮 <b>{c_tag}</b>{c_nom}{c_sx}{c_f}")
    else:
        lineas.append("🍼 <i>No tiene crías descendientes registradas.</i>")

    return "\n".join(lineas)


def html_telegram_a_texto_compartible(texto: str) -> str:
    """Convierte el HTML de parse_mode="HTML" (<b>, <i>) del bot a *negrita*/_cursiva_
    estilo WhatsApp, para paneles pensados para copiar y pegar a mano en un chat
    (donde <b>/<i> no se interpretan y quedarían literales)."""
    texto = re.sub(r"<b>(.*?)</b>", r"*\1*", texto, flags=re.DOTALL)
    texto = re.sub(r"<i>(.*?)</i>", r"_\1_", texto, flags=re.DOTALL)
    return texto


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
        WHERE a.estado = 'ACTIVO'
          AND ((t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
               OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?))
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
        "🚨 <b>CENTRO DE CONTROL & ALERTAS GANADERAS</b>",
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
    """Genera el reporte ejecutivo de población y pirámide de edades, con datos
    reales del hato (no valores de ejemplo)."""
    if hoy is None:
        hoy = date.today()
    datos = calcular_brackets_inventario_sg(db, hoy)
    activos = _contar_activos(db)
    hb = datos["h_brackets"]
    mb = datos["m_brackets"]

    # Reutiliza la misma clasificación SG (CH/HL/NV/VP/VS/CM/ML/MC/RP) que ya
    # se usa en "Existencias por Potrero", sumada a nivel de finca, para que
    # los números de este panel siempre coincidan con esa tabla.
    filas_sg = calcular_existencias_potreros_sg(db, hoy)
    tot_ch = sum(f["ch"] for f in filas_sg)
    tot_hl = sum(f["hl"] for f in filas_sg)
    tot_nv = sum(f["nv"] for f in filas_sg)
    tot_vp = sum(f["vp"] for f in filas_sg)
    tot_vs = sum(f["vs"] for f in filas_sg)
    tot_cm = sum(f["cm"] for f in filas_sg)
    tot_ml = sum(f["ml"] for f in filas_sg)
    tot_mc = sum(f["mc"] for f in filas_sg)
    tot_rep = sum(f["rep"] for f in filas_sg)
    tot_vacas = tot_vp + tot_vs
    tot_crias = tot_ch + tot_cm

    # Días abiertos promedio: vacas paridas activas sin servicio posterior al último parto.
    da = db.dias_abiertos_promedio_hato(hoy)
    dias_abiertos_prom = da["dias_abiertos_promedio"] if da else None
    n_dias_abiertos = da["n"] if da else 0

    lineas = [
        "📊 <b>TABLERO POBLACIONAL & KPIs DEL HATO</b>",
        f"🏷️ <i>Finca: 01-JA-GANADERIA-JA · Total: {activos} Cabezas</i>",
        "────────────────────────────────────────",
        "🐄 <b>ESTRUCTURA DE POBLACIÓN:</b>",
        f"• 🥛 <b>Vacas Totales:</b> {tot_vacas} ({tot_vp} paridas · {tot_vs} secas)",
        f"• 🤰 <b>Novillas de Vientre:</b> {tot_nv}",
        f"• 🍼 <b>Crías (&lt;1a):</b> {tot_crias} ({tot_ch} hembras · {tot_cm} machos)",
        f"• 📈 <b>Levante Hembras (1-2a):</b> {tot_hl}",
        f"• 📈 <b>Levante/Ceba Machos (1-2a):</b> {tot_ml + tot_mc}",
        f"• 🐂 <b>Toros / Reproductores:</b> {tot_rep}",
        "────────────────────────────────────────",
        "🎂 <b>PIRÁMIDE POR RANGOS DE EDAD:</b>",
        f"• 0 a 1 Año:   <b>{hb['menor_1'] + mb['menor_1']}</b> animales (♀ {hb['menor_1']} · ♂ {mb['menor_1']})",
        f"• 1 a 2 Años:  <b>{hb['1_2'] + mb['1_2']}</b> animales (♀ {hb['1_2']} · ♂ {mb['1_2']})",
        f"• 2 a 4 Años:  <b>{hb['2_4']}</b> hembras",
        f"• 4 a 8 Años:  <b>{hb['4_8']}</b> hembras adultas",
        f"• 8 a 10 Años: <b>{hb['8_10']}</b> hembras",
        f"• &gt; 10 Años:  <b>{hb['mayor_10']}</b> hembras",
        "────────────────────────────────────────",
        "📈 <b>INDICADORES REPRODUCTIVOS:</b>",
    ]
    if dias_abiertos_prom is not None:
        lineas.append(f"• <b>Días Abiertos (promedio del hato):</b> {dias_abiertos_prom} días ({n_dias_abiertos} vaca(s) sin servicio tras su último parto)")
    else:
        lineas.append("• <b>Días Abiertos:</b> sin datos suficientes (no hay vacas paridas activas sin servicio posterior)")
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
        "🧬 <b>COMPOSICIÓN GENÉTICA & RAZAS</b>",
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
    lineas.append("💡 <i>El registro incluye cruces de Holstein, Gyr, Ayrshire y Pardo Suizo.</i>")
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


def formatear_tablero_sistema(
    db: Database, auth: Optional[Auth] = None, db_path: Optional[str] = None
) -> str:
    """Genera el diagnóstico ejecutivo de infraestructura y sincronización para el rol OWNER."""
    tam_str = "0 MB"
    if db_path and db_path != ":memory:" and os.path.exists(db_path):
        tam_str = f"{os.path.getsize(db_path) / (1024 * 1024):.2f} MB"
    activos = _contar_activos(db)
    row_tot = db.query_one("SELECT COUNT(*) as n FROM animales")
    tot_animales = int(row_tot["n"]) if row_tot else 0

    # Sincronización SG
    ult_sync = db.ultimo_import_sg()
    if ult_sync:
        f_sync = str(ult_sync["fecha_iso"] or "")[:16].replace("T", " ")
        arch_sync = ult_sync["archivo"] or "backup.zip"
        nuevos = ult_sync["nuevos"] or 0
        dup = ult_sync["duplicados"] or 0
        sync_str = f"{f_sync} ({arch_sync} · +{nuevos} nuevos, {dup} existentes)"
    else:
        sync_str = "Sin registro de sincronización previo"

    # Termo
    termo = db.query_one("SELECT * FROM termo_nitrogeno ORDER BY fecha_recarga DESC LIMIT 1")
    termo_str = f"Última recarga {termo['fecha_recarga']}" if termo else "No configurado"

    # Usuarios
    n_usr = len(auth.listar_usuarios()) if auth else 0

    return (
        f"🖥️ <b>Infraestructura & Base de Datos Ganadería JA</b>\n\n"
        f"• <b>Base de Datos:</b> {html.escape(tam_str)} (Modo WAL activo)\n"
        f"• <b>Hato Activo:</b> {_fmt_es_co(activos)} animales activos ({_fmt_es_co(tot_animales)} históricos)\n"
        f"• <b>Sincronización SG:</b> {html.escape(sync_str)}\n"
        f"• <b>Termo N₂:</b> {html.escape(termo_str)}\n"
        f"• <b>Usuarios Autorizados:</b> {n_usr} cuentas RBAC configuradas\n\n"
        f"<i>Panel reservado exclusivamente para la administración y supervisión del Propietario.</i>"
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
        """
        SELECT DISTINCT t.animal_id FROM tratamientos t
        JOIN animales a ON a.id_animal = t.animal_id
        WHERE a.estado = 'ACTIVO'
          AND ((t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
               OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?))
        """,
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
        "🐮 <b>Tablero de Control — Ganadería JA</b>",
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
    ultimo_import = db.ultimo_import_sg()
    if ultimo_import and ultimo_import["fecha_iso"]:
        f_import = ultimo_import["fecha_iso"][:16].replace("T", " ")
        import_str = f"{f_import} — {ultimo_import['archivo']} ({ultimo_import['nuevos']} nuevos)"
    else:
        import_str = "⚠️ Nunca (no se ha importado ningún backup de SG desde que existe este registro)"
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
        f"• <b>Último backup importado:</b> {import_str}",
        "",
        f"👥 <b>USUARIOS AUTORIZADOS ({len(usuarios)}):</b>",
        f"• 👑 Dueño (OWNER): <b>{n_owner}</b>",
        f"• 🛠️ Administradores (ADMIN): <b>{n_admin}</b>",
        f"• 🤠 Personal de Campo (TRABAJADOR): <b>{n_trab}</b>",
        "",
        "🧠 <b>INTEGRACIÓN DE MODELOS & APIS:</b>",
        f"• 🤖 <b>NLU / LLM:</b> {gemini_status}",
        "• 🎤 <b>Notas de Voz:</b> 🟢 Whisper (transcripción local en español)",
        "• 📷 <b>OCR Visión:</b> 🟢 Pytesseract (lectura aretes y medicamentos)",
    ]
    return "\n".join(salida)


def formatear_usuarios(auth: Auth, presencias: Optional[dict] = None) -> str:
    """Genera la lista de usuarios registrados con sus roles y estado de conexión en vivo (si es OWNER)."""
    usuarios = auth.listar_usuarios()
    if not usuarios:
        return "No hay usuarios registrados en el sistema."

    lineas = [f"👥 <b>Usuarios registrados ({len(usuarios)}):</b>"]
    if presencias is not None:
        en_linea_cnt = sum(1 for u in usuarios if presencias.get(str(u.get("user_id")), {}).get("en_linea"))
        lineas.append(f"🟢 <i>Usuarios en línea ahora: {en_linea_cnt}</i>")
    lineas.append("────────────────────────────────────────")

    for u in usuarios:
        uid = str(u.get("user_id"))
        nom = u.get("nombre", "Sin nombre")
        rol = u.get("rol", "TRABAJADOR")
        tg = u.get("telegram_id")
        tg_txt = f" · TG: <code>{tg}</code>" if tg else ""

        info_linea = f"• ID: <b>{uid}</b> | <b>{nom}</b> | Rol: <code>{rol}</code>{tg_txt}"
        if presencias is not None:
            p = presencias.get(uid, {})
            if p.get("en_linea"):
                canal = p.get("canal", "PWA")
                info_linea += f"\n  └─ 🟢 <b>En línea</b> ({canal} · {p.get('hace_texto', 'activo')})"
            elif p.get("estado") == "reciente":
                canal = p.get("canal", "PWA")
                info_linea += f"\n  └─ 🟡 <b>Reciente</b> ({canal} · {p.get('hace_texto')})"
            else:
                info_linea += f"\n  └─ ⚪ <i>Desconectado ({p.get('hace_texto', 'Sin registro')})</i>"
        lineas.append(info_linea)
    return "\n".join(lineas)


def formatear_ayuda(rol: Optional[str]) -> str:
    """Devuelve el manual de ayuda estructurado y didáctico adaptado al rol del usuario."""
    if rol == "OWNER":
        return (
            "👑 <b>MANUAL DE COMANDOS (Propietario / OWNER)</b>\n"
            "────────────────────────────────────────\n\n"
            "🐮 <b>1. Consultas y Fichas de Animales:</b>\n"
            "• Escribe el arete directo: <code>47</code>, <code>N069</code>, <code>A060</code>\n"
            "• <code>/ficha [tag]</code> o <code>/consulta [tag]</code> — Ficha interactiva con pestañas\n"
            "• <code>/alertas</code> — Semáforo de partos, secados, destetes y retiros\n"
            "• <code>/guia</code> — Cómo hacer preguntas al chat en lenguaje natural\n"
            "• <code>/potreros</code> — Matriz de potreros y rotación Voisin\n"
            "• <code>/ocupacion</code> — Días de ocupación y descanso de praderas\n"
            "• <code>/medicamentos</code> — Panel de fármacos y retiros activos\n"
            "• <code>/poblacion</code> — Pirámide de edades y categorías\n"
            "• <code>/genetica</code> — Composición racial y cruces del hato\n"
            "• <code>/fotos [tag]</code> — Galería fotográfica del ganado\n"
            "• <code>/grafico [tag]</code> — Curva de crecimiento (peso vs edad)\n"
            "• <code>/grafico_leche [tag]</code> — Curva de lactancia (litros vs días en leche)\n"
            "• <code>/graficos</code> — Panel de gráficos generales de la finca\n\n"
            "🎙️ <b>2. Registro por Voz o Texto (Whisper + IA):</b>\n"
            "• 🍼 <i>Partos:</i> «pario la 47 ternero macho 38 kilos»\n"
            "• 🐂 <i>Servicios:</i> «insemine la A029 con toro brahman 502»\n"
            "• 🔥 <i>Celos:</i> «celo en la mañana la vaca 33»\n"
            "• ⚖️ <i>Pesajes:</i> «pesé la N069 en 315 kilos»\n"
            "• 💉 <i>Remedios:</i> «le puse 20ml de oxitetraciclina a la 47»\n"
            "• 🚚 <i>Traslados:</i> «pase el lote 1 de santa martha a versalles»\n\n"
            "⚙️ <b>3. Administración & Sistema:</b>\n"
            "• <code>/status</code> — Tablero ejecutivo de la finca\n"
            "• <code>/sistema</code> — Métricas del servidor VPS y base SQLite\n"
            "• <code>/reporte</code> — Generar reporte semanal en PDF\n"
            "• <code>/exportar</code> — Descargar backup del sistema (paquete ZIP)\n"
            "• <code>/importar</code> — Instrucciones para importar backup DBF\n"
            "• <code>/confirmar_importar</code> — Procesar backup subido\n"
            "• <code>/descartar_backup</code> — Eliminar backup pendiente\n"
            "• <code>/usuarios</code> — Lista de usuarios y estado en vivo\n"
            "• <code>/agregar_usuario [ID] [ROL] [Nombre]</code> — Dar de alta\n"
            "• <code>/quitar_usuario [ID]</code> — Revocar acceso\n"
            "• <code>/logs</code> — Ver últimas líneas del registro del sistema\n"
            "• <code>/duplicados</code> — Posibles animales duplicados por genealogía\n"
            "• <code>/ultimos</code> — Últimos eventos registrados (quién y cuándo)\n"
            "• <code>/deshacer [tabla] [id]</code> — Corregir/borrar un registro por error (pide confirmación)\n"
            "• <code>/renombrar_animal [tag_viejo] [tag_nuevo]</code> — Cambiar el código temporal de una cría por su chapeta definitiva (conserva el historial)\n\n"
            "🆘 ¿Agregar un trabajador nuevo?\n"
            "1. Pídele que busque el bot y le mande /start\n"
            "2. Consigue su user_id: que él busque @userinfobot → /start (Id)\n"
            "3. Agrégalo: /agregar_usuario 712345678 TRABAJADOR Carlos\n"
            "4. Verifica: /usuarios | Para quitar: /quitar_usuario 712345678\n\n"
            "🆘 ¿Un trabajador o el ADMIN registró algo por error (ej. una muerte, "
            "parto o pesaje que no era)?\n"
            "1. /ultimos — busca la línea del registro equivocado\n"
            "2. Copia y envía el comando /deshacer que te muestra en esa línea\n"
            "3. Revisa lo que dice que va a borrar y confirma con /confirmar_deshacer\n"
            "   (o /cancelar_deshacer si te arrepientes)\n"
            "Si el problema es grande (muchos registros dañados, no solo uno), eso ya "
            "no es para el chat: pide que restauren el respaldo automático de anoche "
            "desde el VPS (scripts/restaurar_backup.sh) — esa es la otra red de "
            "seguridad, separada del respaldo general.\n\n"
            "🏠 <i>Toca /menu o /start para abrir el panel táctil interactivo.</i>"
        )
    if rol == "ADMIN":
        return (
            "🛠️ <b>MANUAL DE COMANDOS (Administrador / ADMIN)</b>\n"
            "────────────────────────────────────────\n\n"
            "🐮 <b>1. Consultas y Fichas de Animales:</b>\n"
            "• Escribe el arete directo: <code>47</code>, <code>N069</code>, <code>A060</code>\n"
            "• <code>/ficha [tag]</code> o <code>/consulta [tag]</code> — Ficha interactiva con pestañas\n"
            "• <code>/alertas</code> — Semáforo de partos, secados, destetes y retiros\n"
            "• <code>/guia</code> — Cómo hacer preguntas al chat en lenguaje natural\n"
            "• <code>/potreros</code> — Matriz de potreros y rotación Voisin\n"
            "• <code>/ocupacion</code> — Días de ocupación y descanso de praderas\n"
            "• <code>/medicamentos</code> — Panel de fármacos y retiros activos\n"
            "• <code>/poblacion</code> — Pirámide de edades y categorías\n"
            "• <code>/genetica</code> — Composición racial y cruces del hato\n"
            "• <code>/fotos [tag]</code> — Galería fotográfica del ganado\n"
            "• <code>/grafico [tag]</code> — Curva de crecimiento (peso vs edad)\n"
            "• <code>/grafico_leche [tag]</code> — Curva de lactancia (litros vs días en leche)\n"
            "• <code>/graficos</code> — Panel de gráficos generales de la finca\n\n"
            "⚙️ <b>2. Informes y Sincronización:</b>\n"
            "• <code>/status</code> — Tablero ejecutivo de la finca\n"
            "• <code>/reporte</code> — Generar reporte semanal en PDF\n"
            "• <code>/exportar</code> — Descargar backup del sistema (paquete ZIP)\n"
            "• <code>/importar</code> — Instrucciones para importar backup DBF\n"
            "• <code>/confirmar_importar</code> — Procesar backup subido\n"
            "• <code>/descartar_backup</code> — Eliminar backup pendiente\n"
            "• <code>/duplicados</code> — Posibles animales duplicados por genealogía\n"
            "• <code>/ultimos</code> — Últimos eventos registrados (quién y cuándo)\n"
            "• <code>/deshacer [tabla] [id]</code> — Corregir/borrar un registro por error (pide confirmación)\n"
            "• <code>/renombrar_animal [tag_viejo] [tag_nuevo]</code> — Cambiar el código temporal de una cría por su chapeta definitiva (conserva el historial)\n\n"
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
            "• <code>/fotos [tag]</code> — Ver galería o fotos del animal\n"
            "• <code>/grafico [tag]</code> — Curva de crecimiento (peso vs edad)\n"
            "• <code>/grafico_leche [tag]</code> — Curva de lactancia (litros vs días en leche)\n"
            "• <code>/graficos</code> — Panel de gráficos generales de la finca\n\n"
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
            "• <code>/medicamentos</code> — Ver qué vacas están en retiro de leche/carne\n"
            "• <code>/sos [qué pasó]</code> — Emergencia: avisa de inmediato al Dueño/Administrador\n\n"
            "📶 <b>¿Sin señal en el potrero?</b>\n"
            "Escribe o graba la nota igual — Telegram la guarda en tu celular y la envía sola "
            "apenas recuperes cobertura, no hace falta reintentar.\n\n"
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
            "💡 <i>Regla de manejo:</i> Celo en la mañana se insemina en la tarde; celo en la tarde se insemina en la mañana siguiente."
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
        "condicion_corporal": (
            "📏 <b>Ejemplo de Condición Corporal:</b>\n"
            "<code>condición corporal de la 47 es 3.5</code>\n"
            "<code>la 12 tiene condición corporal 3</code>\n\n"
            "💡 <i>Uso:</i> Se guarda por fecha, igual que un pesaje; sirve para ver la tendencia nutricional del animal."
        ),
        "leche": (
            "🥛 <b>Ejemplo de Control de Leche:</b>\n"
            "<code>la 47 dio 12 litros de leche</code>\n"
            "<code>ordeñé 8.5 litros a la 12</code>\n\n"
            "💡 <i>Uso:</i> No hace falta a diario — con un control semanal ya se puede armar la curva de lactancia."
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
        "¡Bienvenido! Este bot cuenta con Inteligencia Artificial Ganadera y entiende <b>español normal de campo</b>.\n\n"
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
        "• <i>«ganancia diaria de la 47»</i>\n"
        "• <i>«condición corporal de la 47»</i>\n"
        "• <i>«litros de leche de la 47»</i>\n\n"
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
        "• <i>«dónde está el lote 2»</i>\n\n"
        "🔢 <b>Conteos por Edad, Raza, Peso o Estado:</b>\n"
        "• <i>«cuántos animales hay de 2 años»</i>\n"
        "• <i>«cuántas vacas de 6 años hay»</i>\n"
        "• <i>«cuántas vacas holstein hay»</i>\n"
        "• <i>«cuántos animales pesan más de 400 kilos»</i>\n"
        "• <i>«qué potrero tiene más animales»</i>\n"
        "• <i>«cuántos animales vendidos hay»</i>\n"
        "• <i>«cuántos animales vendieron este mes»</i>\n"
        "• <i>«cuántas vacas se han muerto»</i>"
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
        "• <i>«vacas con celo pendiente de servicio»</i>\n"
        "• <i>«¿qué vacas debían haber parido?»</i> (FEP vencida, revisar)\n"
        "• <i>«¿qué animales están perdiendo peso?»</i>\n\n"
        "🍼 <b>Partos del Hato:</b>\n"
        "• <i>«¿qué partos hubo este mes?»</i>\n"
        "• <i>«partos de los últimos 30 días»</i>\n"
        "• <i>«cuántos partos hubo el mes pasado»</i>\n"
        "• <i>«cuántos partos hubo este año»</i>\n"
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
        "• <b>Fotos de Aretes:</b> Envía una foto clara del arete y el bot abre su ficha de inmediato.\n"
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
        "4. El bot transcribe sus palabras, reconoce el evento de campo y lo registra automáticamente en la base de datos."
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


def formatear_duplicados_geneticos(grupos: list[dict]) -> str:
    """Formatea los grupos de animales activos que comparten madre+padre+fecha
    de nacimiento (probable mismo nacimiento importado dos veces con tags
    distintos, ej. 'N065' vs 'NO65')."""
    if not grupos:
        return "✅ No se detectaron animales activos duplicados por genealogía (misma madre, padre y fecha de nacimiento)."
    lineas = [f"⚠️ <b>Posibles animales duplicados ({len(grupos)} grupo(s)):</b>", ""]
    for g in grupos[:15]:
        tags_str = ", ".join(g["tags"])
        lineas.append(f"• Madre <b>{g['madre_tag']}</b>, nacido {g['fecha_nacimiento']}: {tags_str}")
    if len(grupos) > 15:
        lineas.append(f"<i>... y {len(grupos) - 15} grupo(s) más.</i>")
    lineas.append("")
    lineas.append("<i>Revise cuál tag es el correcto en los registros antes de decidir cuál conservar.</i>")
    return "\n".join(lineas)


_ETIQUETAS_TABLA_EVENTO = {
    "partos": "🐣 Parto", "muertes": "⚰️ Muerte", "servicios": "💉 Servicio",
    "celos": "🔥 Celo", "tratamientos": "💊 Tratamiento", "traslados": "🚚 Traslado",
    "pesajes": "⚖️ Pesaje", "movimientos": "📦 Movimiento",
}


def formatear_ultimos_registros(filas: list, auth: Optional[Auth] = None) -> str:
    """Formatea la lista de últimos eventos registrados (comando /ultimos),
    numerada para que el admin pueda referenciar cuál deshacer con
    /deshacer <tabla> <id> tal como aparece en cada línea."""
    if not filas:
        return "No hay eventos registrados todavía."
    lineas = ["🕒 <b>Últimos eventos registrados:</b>", ""]
    for f in filas:
        etiqueta = _ETIQUETAS_TABLA_EVENTO.get(f["tabla"], f["tabla"])
        tag = f["tag"] or "?"
        quien = ""
        if f["registrado_por"] and auth is not None:
            rol_usuario = auth.rol_de(f["registrado_por"])
            nombre = None
            for u in auth.listar_usuarios():
                if u.get("user_id") == f["registrado_por"]:
                    nombre = u.get("nombre")
                    break
            if nombre:
                quien = f" · por {nombre}"
            elif rol_usuario:
                quien = f" · por ID {f['registrado_por']}"
        cuando = f" ({f['creado_en']})" if f["creado_en"] else ""
        lineas.append(
            f"• <code>/deshacer {f['tabla']} {f['id']}</code> — {etiqueta} de {tag}, {f['fecha']}{quien}{cuando}"
        )
    lineas.append("")
    lineas.append("<i>Envía el comando /deshacer de la línea que quieras corregir. Pedirá confirmación antes de borrar.</i>")
    return "\n".join(lineas)


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
            linea = f"• {tabla}: {n} nuevos, {d} duplicados"
            if res.get("errores"):
                linea += f", {res.get('errores')} errores"
            if res.get("error"):
                linea += f" (error: {res.get('error')})"
            lineas_tablas.append(linea)

    lineas = [
        "📦 Reporte de Importación de Backup:",
        f"• Total consolidado: {total_nuevos} nuevos, {total_duplicados} duplicados",
        "",
        "📋 Detalle por tabla:",
    ] + lineas_tablas

    duplicados_geneticos = conteos.get("duplicados_geneticos")
    if duplicados_geneticos:
        lineas.append("")
        lineas.append(f"⚠️ <b>{len(duplicados_geneticos)} posible(s) animal(es) duplicado(s)</b> por genealogía (misma madre/padre/fecha de nacimiento bajo tags distintos). Use /duplicados para ver el detalle.")

    info_animales = conteos.get("animales") or {}
    ventas_registradas = info_animales.get("ventas_registradas")
    ventas_aprox = info_animales.get("ventas_fecha_aproximada")
    if ventas_registradas:
        lineas.append("")
        detalle_aprox = f" ({ventas_aprox} sin fecha exacta en SG, aproximadas a hoy)" if ventas_aprox else ""
        lineas.append(f"💰 <b>{ventas_registradas} venta(s)</b> nueva(s) detectada(s) en este backup{detalle_aprox}.")

    return "\n".join(lineas)


def formatear_instrucciones_importar() -> str:
    """Devuelve las instrucciones para subir un backup mediante Telegram o SSH."""
    return (
        "📦 Para importar un backup del sistema:\n\n"
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
        WHERE a.estado = 'ACTIVO'
          AND ((t.fecha_fin_retiro_leche IS NOT NULL AND t.fecha_fin_retiro_leche >= ?)
               OR (t.fecha_fin_retiro_carne IS NOT NULL AND t.fecha_fin_retiro_carne >= ?))
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
        "🔍 <b>Buscador de Animales & Fichas Técnicas</b>\n"
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
        "Seleccione una pregunta para obtener la respuesta al instante:"
    )


def formatear_despacho_matutino(db: Database, hoy: Optional[date] = None, finca_nombre: str = "GANADERÍA JA", pronostico: Optional[dict] = None) -> str:
    """Genera el Despacho Matutino (Morning Briefing) con las tareas críticas del día:
    1. Ordeño & Retiros sanitarios (solo si hay alertas activas).
    2. Inseminaciones AM por regla AM-PM (celos de ayer PM) y programadas.
    3. Recordatorios programados del día (tareas, rotaciones, vacunas).
    4. Calendario reproductivo (ecografías d35, palpaciones d60, partos próximos 7d).
    """
    if hoy is None:
        hoy = date.today()
    hoy_iso = hoy.isoformat()
    ayer = add_days(hoy, -1)
    ayer_iso = ayer.isoformat()
    lim_7d = add_days(hoy, 7).isoformat()

    dias_sem = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    nombre_dia = dias_sem[hoy.weekday()]
    fecha_bonita = f"{nombre_dia}, {hoy.day} de {meses_es[hoy.month]} de {hoy.year}"

    lineas = [
        f"🌅 <b>DESPACHO MATUTINO — {finca_nombre}</b>",
        f"📅 <i>{fecha_bonita} · 05:30 AM</i>",
        "────────────────────────────────────────",
    ]

    # 0. ⛅ Clima & pronóstico (primera sección; solo si hay datos).
    # Si pronostico es None la salida queda EXACTAMENTE igual que antes.
    if pronostico is not None:
        try:
            from ..engine.pronostico import formatear_pronostico_despacho

            bloque_clima = formatear_pronostico_despacho(pronostico)
        except Exception:
            bloque_clima = ""
        if bloque_clima:
            lineas.append(bloque_clima)
            lineas.append("")

    # 1. 🥛 Control de Ordeño & Retiros Sanitarios (Solo alerta si hay vacas en retiro)
    retiros_leche = db.query(
        """
        SELECT t.*, a.tag, a.nombre, p.nombre AS potrero_nom
        FROM tratamientos t
        JOIN animales a ON a.id_animal = t.animal_id
        LEFT JOIN potreros p ON p.id = a.potrero_id
        WHERE a.estado = 'ACTIVO'
          AND t.fecha_fin_retiro_leche IS NOT NULL
          AND t.fecha_fin_retiro_leche >= ?
        ORDER BY t.fecha_fin_retiro_leche ASC
        """,
        (hoy_iso,),
    )

    retiros_carne = db.query(
        """
        SELECT t.*, a.tag, a.nombre
        FROM tratamientos t
        JOIN animales a ON a.id_animal = t.animal_id
        WHERE a.estado = 'ACTIVO'
          AND t.fecha_fin_retiro_carne IS NOT NULL
          AND t.fecha_fin_retiro_carne >= ?
        ORDER BY t.fecha_fin_retiro_carne ASC
        """,
        (hoy_iso,),
    )

    if retiros_leche:
        lineas.append(f"⛔ <b>¡ALERTA DE ORDEÑO! VACAS EN RETIRO ({len(retiros_leche)}):</b>")
        lineas.append("⚠️ <i>NO echar esta leche al tanque bajo ninguna circunstancia:</i>")
        for r in retiros_leche:
            tag_nom = r["tag"] or f"#{r['animal_id']}"
            if r["nombre"]:
                tag_nom += f" ({r['nombre']})"
            f_fin = to_date(r["fecha_fin_retiro_leche"])
            d_quedan = (f_fin - hoy).days if f_fin else 0
            d_txt = f"Quedan {d_quedan}d" if d_quedan > 0 else "Último día hoy"
            med = r["producto"] or "Fármaco"
            lineas.append(f"• 🔴 <b>{_esc(tag_nom)}</b> — {_esc(med)} (⛔ {d_txt}, hasta {r['fecha_fin_retiro_leche']})")
        lineas.append("")

    if retiros_carne:
        lineas.append(f"🥩 <b>Retiro de Carne:</b> ⚠️ {len(retiros_carne)} animales en carencia (no aptos para sacrificio).\n")

    # 2. 🧬 Inseminaciones de la Mañana (Regla AM-PM)
    celos_ayer_pm = db.query(
        """
        SELECT c.*, a.tag, a.nombre, p.nombre AS potrero_nom
        FROM celos c
        JOIN animales a ON a.id_animal = c.vaca_id
        LEFT JOIN potreros p ON p.id = a.potrero_id
        WHERE a.estado = 'ACTIVO'
          AND c.fecha = ?
          AND (UPPER(c.am_pm) LIKE '%PM%' OR UPPER(c.am_pm) = 'TARDE')
        ORDER BY c.id DESC
        """,
        (ayer_iso,),
    )

    alertas_ia_hoy = db.query(
        """
        SELECT al.*, a.tag, a.nombre
        FROM alertas al
        JOIN animales a ON a.id_animal = al.animal_id
        WHERE a.estado = 'ACTIVO'
          AND al.tipo_alerta = 'INSEMINACION_PROGRAMADA'
          AND al.estado = 'PENDIENTE'
          AND al.fecha_programada = ?
        """,
        (hoy_iso,),
    )

    vacas_inseminar = []
    vistos_ia = set()
    for c in celos_ayer_pm:
        tag_v = c["tag"] or f"#{c['vaca_id']}"
        nom_v = f" ({c['nombre']})" if c["nombre"] else ""
        if c["vaca_id"] not in vistos_ia:
            vistos_ia.add(c["vaca_id"])
            vacas_inseminar.append(f"• 💉 <b>{_esc(tag_v)}{_esc(nom_v)}</b> — Celo observado ayer PM <i>(Inseminar antes de las 10:00 AM)</i>")

    for al in alertas_ia_hoy:
        tag_v = al["tag"] or f"#{al['animal_id']}"
        nom_v = f" ({al['nombre']})" if al["nombre"] else ""
        if al["animal_id"] not in vistos_ia:
            vistos_ia.add(al["animal_id"])
            vacas_inseminar.append(f"• 💉 <b>{_esc(tag_v)}{_esc(nom_v)}</b> — Inseminación programada para hoy")

    if vacas_inseminar:
        lineas.append(f"🔥 <b>INSEMINACIONES DE ESTA MAÑANA ({len(vacas_inseminar)}):</b>")
        lineas.extend(vacas_inseminar)
        lineas.append("")
    else:
        lineas.append("🧬 <b>Inseminaciones AM:</b> Sin servicios de regla AM-PM programados para hoy.\n")

    # 3. 📌 Recordatorios Programados
    try:
        recordatorios = db.listar_recordatorios_pendientes(fecha=hoy_iso)
    except Exception:
        recordatorios = []

    if recordatorios:
        lineas.append(f"📌 <b>RECORDATORIOS PROGRAMADOS ({len(recordatorios)}):</b>")
        for rec in recordatorios:
            h_txt = f"[{rec['hora']}] " if rec["hora"] else ""
            lineas.append(f"• ⏰ {h_txt}<b>{_esc(rec['mensaje'])}</b>")
        lineas.append("")
    else:
        lineas.append("📌 <b>Recordatorios:</b> Sin recordatorios programados.\n")

    # 4. 🤰 Calendario Reproductivo & Veterinario
    partos_7d = db.query(
        """
        SELECT s.*, a.tag, a.nombre, p.nombre AS potrero_nom
        FROM servicios s
        JOIN animales a ON a.id_animal = s.vaca_id
        LEFT JOIN potreros p ON p.id = a.potrero_id
        WHERE a.estado = 'ACTIVO'
          AND s.fep_calculada IS NOT NULL
          AND s.fep_calculada >= ? AND s.fep_calculada <= ?
        ORDER BY s.fep_calculada ASC
        LIMIT 5
        """,
        (hoy_iso, lim_7d),
    )

    servicios_eco = db.query(
        """
        SELECT s.*, a.tag, a.nombre
        FROM servicios s
        JOIN animales a ON a.id_animal = s.vaca_id
        WHERE a.estado = 'ACTIVO'
          AND s.fecha IS NOT NULL
          AND s.fecha = ?
        """,
        (add_days(hoy, -35).isoformat(),),
    )

    servicios_palp = db.query(
        """
        SELECT s.*, a.tag, a.nombre
        FROM servicios s
        JOIN animales a ON a.id_animal = s.vaca_id
        WHERE a.estado = 'ACTIVO'
          AND s.fecha IS NOT NULL
          AND s.fecha = ?
        """,
        (add_days(hoy, -60).isoformat(),),
    )

    tareas_vet = []
    if servicios_eco:
        for se in servicios_eco:
            tag_v = se["tag"] or f"#{se['vaca_id']}"
            tareas_vet.append(f"• 🔬 <b>Ecografía (Día 35):</b> Vaca <b>{_esc(tag_v)}</b> (Servicio del {se['fecha']})")

    if servicios_palp:
        for sp in servicios_palp:
            tag_v = sp["tag"] or f"#{sp['vaca_id']}"
            tareas_vet.append(f"• 🩺 <b>Palpación (Día 60):</b> Vaca <b>{_esc(tag_v)}</b> (Servicio del {sp['fecha']})")

    if partos_7d:
        for p7 in partos_7d:
            tag_v = p7["tag"] or f"#{p7['vaca_id']}"
            f_fep = to_date(p7["fep_calculada"])
            d_fep = (f_fep - hoy).days if f_fep else 0
            d_fep_txt = "¡Hoy o mañana!" if d_fep <= 1 else f"en {d_fep} días"
            tareas_vet.append(f"• 🍼 <b>Parto próximo:</b> Vaca <b>{_esc(tag_v)}</b> — FEP: {p7['fep_calculada']} ({d_fep_txt})")

    if tareas_vet:
        lineas.append(f"🤰 <b>CALENDARIO REPRODUCTIVO & VETERINARIO ({len(tareas_vet)}):</b>")
        lineas.extend(tareas_vet)
        lineas.append("")

    # 5. ❄️ Alerta de Nitrógeno Líquido (Termo Criogénico)
    termo = db.ultimo_estado_termo(hoy)
    if termo and termo["dias_restantes"] <= 3:
        d_rest = termo["dias_restantes"]
        if d_rest < 0:
            alerta_n2_txt = f"🚨 <b>Nitrógeno VENCIDO hace {abs(d_rest)} días</b> (última recarga: {termo['fecha_recarga']})"
        elif d_rest == 0:
            alerta_n2_txt = "⚠️ <b>Nitrógeno recargar HOY</b> (vence hoy)"
        elif d_rest == 1:
            alerta_n2_txt = "⚠️ <b>Nitrógeno recargar en 1 día</b>"
        else:
            alerta_n2_txt = f"⚠️ <b>Nitrógeno recargar en {d_rest} días</b>"
        lineas.append("❄️ <b>ALERTA DE TERMO CRIOGÉNICO (N₂):</b>")
        lineas.append(f"• {alerta_n2_txt} (Próxima recarga programada: {termo['proxima_recarga']})\n")

    lineas.append("────────────────────────────────────────")
    lineas.append("💡 <i>¡Excelente y productiva jornada para todo el equipo de campo!</i>")

    return "\n".join(lineas)


# ---------------------------------------------------------------------- #
# Módulo Reproducción & Termo Criogénico (Fase 5.1)
# ---------------------------------------------------------------------- #
def formatear_panel_reproduccion(db: Database, hoy: Optional[date] = None) -> str:
    """Panel principal del módulo de Reproducción y Termo Criogénico."""
    if hoy is None:
        hoy = date.today()

    termo = db.ultimo_estado_termo(hoy)
    pajuelas = db.listar_pajuelas()
    kpis = db.kpis_reproductivos_concepcion()

    total_pajuelas = sum(p["cantidad"] for p in pajuelas)
    n_toros = len(pajuelas)
    criticas = [p for p in pajuelas if p["cantidad"] <= 2]

    lineas = [
        "🤰 <b>MÓDULO DE REPRODUCCIÓN & TERMO CRIOGÉNICO</b>",
        "────────────────────────────────────────",
    ]

    # Estado del termo
    if termo:
        dias_rest = termo["dias_restantes"]
        if dias_rest < 0:
            ico_t = "🚨"
            t_txt = f"VENCIDO ({abs(dias_rest)} días de atraso)"
        elif dias_rest <= 3:
            ico_t = "⚠️"
            t_txt = f"CRÍTICO ({dias_rest} días restantes)"
        else:
            ico_t = "✅"
            t_txt = f"OK ({dias_rest} días restantes)"
        lineas.append(f"❄️ <b>Termo N₂:</b> {ico_t} <b>{t_txt}</b> | Próx: {termo['proxima_recarga']}")
    else:
        lineas.append("❄️ <b>Termo N₂:</b> <i>Sin recargas registradas</i> (use <code>/recarga_n2</code>)")

    # Stock de pajuelas
    aviso_crit = f" ⚠️ ({len(criticas)} en stock bajo)" if criticas else ""
    lineas.append(f"🧪 <b>Banco de Pajuelas:</b> <b>{total_pajuelas}</b> unidades ({n_toros} reproductores){aviso_crit}")

    # KPIs de concepción
    if kpis and kpis["total_evaluados"] > 0:
        sc_txt = f"{kpis['servicios_por_concepcion']:.2f}" if kpis["servicios_por_concepcion"] else "N/D"
        lineas.append(f"🎯 <b>Tasa Concepción:</b> <b>{kpis['tasa_concepcion']:.1f}%</b> | <b>S/C:</b> {sc_txt}")
    else:
        lineas.append("🎯 <b>Tasa Concepción:</b> <i>Sin diagnósticos suficientes</i>")

    lineas.append("────────────────────────────────────────")
    lineas.append("💡 <i>Seleccione una opción o use los comandos rápidos:</i>")
    lineas.append("• <code>/pajuela_stock</code> — Ver inventario detallado de pajuelas")
    lineas.append("• <code>/pajuela_add &lt;toro&gt; &lt;cantidad&gt;</code> — Añadir pajuelas")
    lineas.append("• <code>/termo</code> — Ver nivel y recargas de nitrógeno")
    lineas.append("• <code>/recarga_n2</code> — Registrar recarga de nitrógeno")
    lineas.append("• <code>palpé la 47 confirmada preñada 60 días</code> — Registrar diagnóstico")

    return "\n".join(lineas)


def formatear_stock_pajuelas(db: Database) -> str:
    """Formatea la lista completa de inventario de pajuelas en el termo criogénico."""
    pajuelas = db.listar_pajuelas()
    if not pajuelas:
        return (
            "🧪 <b>INVENTARIO DE PAJUELAS (TERMO CRIOGÉNICO)</b>\n"
            "────────────────────────────────────────\n"
            "⚠️ <i>No hay pajuelas registradas en el inventario.</i>\n\n"
            "💡 <b>Para registrar ingreso de pajuelas:</b>\n"
            "• Use el comando: <code>/pajuela_add 502 10 Brahman C1 35000</code>\n"
            "  (Formato: <code>/pajuela_add &lt;toro&gt; &lt;cantidad&gt; [raza] [canastilla] [costo]</code>)"
        )

    total_unidades = sum(p["cantidad"] for p in pajuelas)
    criticos = sum(1 for p in pajuelas if p["cantidad"] <= 2)

    lineas = [
        "🧪 <b>INVENTARIO DE PAJUELAS — TERMO CRIOGÉNICO</b>",
        f"📊 <b>Total:</b> <b>{total_unidades} pajuelas</b> ({len(pajuelas)} toros/lotes)",
        "────────────────────────────────────────",
    ]

    for p in pajuelas:
        toro = _esc(p["codigo_toro"])
        cant = p["cantidad"]
        raza = f" · {_esc(p['raza'])}" if p["raza"] else ""
        can = f" [Canastilla {_esc(p['canastilla'])}]" if p["canastilla"] else ""
        costo = f" · ${_fmt_es_co(p['costo'])}" if p["costo"] else ""
        aviso = " ⚠️ <b>[BAJO]</b>" if cant <= 2 else ""

        lineas.append(f"• 🐂 <b>{toro}</b>{raza}: <b>{cant} unid.</b>{can}{costo}{aviso}")

    if criticos > 0:
        lineas.append("────────────────────────────────────────")
        lineas.append(f"⚠️ <i>Atención: {criticos} reproductor(es) tienen 2 o menos pajuelas disponibles.</i>")

    lineas.append("\n💡 <i>Para agregar stock use: <code>/pajuela_add &lt;toro&gt; &lt;cantidad&gt; [raza] [canastilla] [costo]</code></i>")
    return "\n".join(lineas)


def formatear_estado_termo(db: Database, hoy: Optional[date] = None) -> str:
    """Formatea el estado actual del termo criogénico y el historial de recargas."""
    if hoy is None:
        hoy = date.today()

    termo = db.ultimo_estado_termo(hoy)
    recargas = db.listar_recargas_nitrogeno(limit=5)

    if not termo:
        return (
            "❄️ <b>TERMO CRIOGÉNICO & NITRÓGENO LÍQUIDO</b>\n"
            "────────────────────────────────────────\n"
            "⚠️ <i>No hay recargas de nitrógeno registradas en el sistema.</i>\n\n"
            "💡 <b>Para registrar una recarga:</b>\n"
            "• Use: <code>/recarga_n2</code> (registra hoy con intervalo estándar de 21 días)\n"
            "• O especifique: <code>/recarga_n2 2026-08-31 28</code>"
        )

    dias_rest = termo["dias_restantes"]
    if dias_rest < 0:
        ico = "🚨"
        nivel = f"<b>VENCIDO</b> (atraso de {abs(dias_rest)} días)"
    elif dias_rest <= 3:
        ico = "⚠️"
        nivel = f"<b>CRÍTICO</b> ({dias_rest} días restantes)"
    else:
        ico = "✅"
        nivel = f"<b>ÓPTIMO</b> ({dias_rest} días restantes)"

    lineas = [
        "❄️ <b>ESTADO DEL TERMO CRIOGÉNICO (N₂ LÍQUIDO)</b>",
        "────────────────────────────────────────",
        f"• Estado del tanque: {ico} {nivel}",
        f"• Última recarga: <b>{termo['fecha_recarga']}</b> (hace {termo['dias_desde_recarga']} días)",
        f"• Próxima recarga programada: <b>{termo['proxima_recarga']}</b>",
        f"• Intervalo de seguridad: cada {termo['dias_intervalo']} días",
        "────────────────────────────────────────",
    ]

    if recargas:
        lineas.append("📜 <b>Últimas Recargas:</b>")
        for r in recargas:
            lineas.append(f"• {r['fecha_recarga']} (Intervalo: {r['dias_intervalo']}d → Próx: {r['proxima_recarga']})")
        lineas.append("")

    lineas.append("💡 <i>Para registrar una nueva recarga use: <code>/recarga_n2 [fecha] [dias]</code></i>")
    return "\n".join(lineas)


def formatear_kpis_reproduccion(db: Database) -> str:
    """Formatea el reporte detallado de tasa de concepción y S/C."""
    kpis = db.kpis_reproductivos_concepcion()
    if not kpis or (kpis["total_servicios"] == 0 and kpis["total_evaluados"] == 0):
        return (
            "🎯 <b>KPIs REPRODUCTIVOS & CONCEPCIÓN</b>\n"
            "────────────────────────────────────────\n"
            "⚠️ <i>No hay suficientes servicios o diagnósticos registrados para calcular indicadores.</i>"
        )

    sc_str = f"{kpis['servicios_por_concepcion']:.2f}" if kpis["servicios_por_concepcion"] else "N/D"
    lineas = [
        "🎯 <b>KPIs REPRODUCTIVOS & TASA DE CONCEPCIÓN</b>",
        "────────────────────────────────────────",
        f"• Servicios totales registrados: <b>{kpis['total_servicios']}</b>",
        f"• Servicios evaluados con diagnóstico: <b>{kpis['total_evaluados']}</b>",
        f"• Vacas confirmadas preñadas: <b>{kpis['total_prenadas']}</b>",
        f"• Vacías / servicios fallidos: <b>{kpis['total_vacias']}</b>",
        f"• 🎯 <b>Tasa de Concepción: {kpis['tasa_concepcion']:.1f}%</b>",
        f"• 🐂 <b>Servicios por Concepción (S/C): {sc_str}</b> (Meta ideal: ≤ 1.7)",
        "────────────────────────────────────────",
    ]

    if kpis.get("por_toro") and len(kpis["por_toro"]) > 0:
        lineas.append("🏆 <b>Ranking de Fertilidad por Reproductor / Pajuela:</b>")
        for t in kpis["por_toro"][:10]:
            sc_t = f"{t['sc']:.2f}" if t['sc'] else "N/D"
            lineas.append(
                f"• <b>{_esc(t['toro'])}</b>: <b>{t['tasa_concepcion']:.1f}%</b> concepción "
                f"({t['prenadas']}/{t['evaluados']} preñadas) | S/C: {sc_t}"
            )

    return "\n".join(lineas)


def formatear_diagnosticos_recientes(db: Database) -> str:
    """Formatea la lista de diagnósticos de gestación recientes."""
    diags = db.listar_diagnosticos(limit=15)
    if not diags:
        return (
            "🩺 <b>DIAGNÓSTICOS DE GESTACIÓN / PALPACIONES</b>\n"
            "────────────────────────────────────────\n"
            "⚠️ <i>No hay diagnósticos de gestación registrados aún.</i>\n\n"
            "💡 <b>Para registrar diagnósticos en lenguaje natural:</b>\n"
            "• <code>palpé la 47 confirmada preñada 60 días</code>\n"
            "• <code>la 12 vacía</code>\n"
            "• <code>diagnóstico de gestación vaca 105 preñada 90 días</code>"
        )

    lineas = [
        f"🩺 <b>ÚLTIMOS {len(diags)} DIAGNÓSTICOS DE GESTACIÓN</b>",
        "────────────────────────────────────────",
    ]

    for d in diags:
        tag = _esc(d["tag"])
        nom = f" ({_esc(d['nombre'])})" if d["nombre"] else ""
        res = (d["resultado"] or "").upper()
        ico = "🤰" if res == "PREÑADA" else "⭕"
        dias = f" · <b>{d['dias_gestacion']}d gestación</b>" if d["dias_gestacion"] else ""
        resp = f" (Por: {_esc(d['responsable'])})" if d["responsable"] else ""

        lineas.append(f"• <b>{d['fecha']}</b> — <b>{tag}</b>{nom}: {ico} <b>{res}</b>{dias}{resp}")

    lineas.append("────────────────────────────────────────")
    lineas.append("💡 <i>Para registrar: <code>palpé la 47 confirmada preñada 60 días</code> o <code>la 12 vacía</code></i>")
    return "\n".join(lineas)


def formatear_clima_panel(db: Database, hoy: Optional[date] = None) -> str:
    """Genera el panel interactivo de pluviometría, lluvias y clima IDEAM."""
    ref = hoy or date.today()
    from ..integrations.ideam_clima import ClimaIDEAM
    res = db.resumen_pluviometrico(hoy=ref)
    info = ClimaIDEAM.clasificar_estacionalidad(res["ultimos_30d_mm"])
    hist = db.obtener_pluviometria(limite=5)

    # Pronóstico 7 días Open-Meteo al inicio del panel (solo si hay datos).
    # Envuelto en try/except: un fallo de red nunca debe romper /clima.
    _bloque_pron = ""
    _tabla_pron = ""
    try:
        from ..engine.pronostico import (
            formatear_pronostico_despacho,
            formatear_tabla_pronostico,
            obtener_pronostico_para_despacho,
        )

        _pron = obtener_pronostico_para_despacho(db)
        if _pron:
            _bloque_pron = formatear_pronostico_despacho(_pron)
            _tabla_pron = formatear_tabla_pronostico(_pron)
    except Exception:
        _bloque_pron = ""
        _tabla_pron = ""

    lineas = [
        "🌧️ <b>PLUVIOMETRÍA & CLIMA AGROPECUARIO (IDEAM)</b>",
        f"📅 <b>Fecha:</b> {ref.isoformat()}",
        "────────────────────────────────────────",
        f"• <b>Lluvia Hoy:</b> <b>{res['hoy_mm']:.1f} mm</b>",
        f"• <b>Últimos 7 días:</b> <b>{res['ultimos_7d_mm']:.1f} mm</b>",
        f"• <b>Últimos 30 días (Mes móvil):</b> <b>{res['ultimos_30d_mm']:.1f} mm</b>",
        f"• <b>Mes actual en curso:</b> <b>{res['mes_actual_mm']:.1f} mm</b>",
        f"• <b>Acumulado Anual ({ref.year}):</b> <b>{res['anio_actual_mm']:.1f} mm</b>",
    ]
    if _bloque_pron:
        lineas.append(_bloque_pron)
        if _tabla_pron:
            lineas.append(_tabla_pron)
        lineas.append("────────────────────────────────────────")
    if res.get("satelital_mm") is not None:
        lineas.append(
            f"🛰️ <b>Estimado Satelital (CHIRPS, {res['satelital_dias']}d hasta {res['satelital_fecha']}):</b> "
            f"<b>{res['satelital_mm']:.1f} mm</b> · registrado: {res['ultimos_30d_mm']:.1f} mm"
        )
    lineas += [
        "────────────────────────────────────────",
        f"{info['icono']} <b>Temporada Actual:</b> <b>{info['estacion']}</b>",
        f"🌿 <b>Factor Rebrote Forrajero:</b> <b>{info['factor_clima']}x</b>",
        f"⏳ <b>Descanso Sugerido Voisin:</b> <b>{info['dias_reposo_sugeridos']} días</b>",
        f"💡 <b>Manejo Ganadero:</b> <i>{info['recomendacion']}</i>",
    ]

    if hist:
        lineas.append("\n📋 <b>Últimos Registros Pluviométricos:</b>")
        for h in hist:
            sec = f" ({_esc(h['estacion_o_sector'])})" if h['estacion_o_sector'] else ""
            lineas.append(f"• [{h['fecha']}] <b>{h['mm_lluvia']:.1f} mm</b>{sec}")

    lineas.append("\n💡 <i>Para anotar lluvia: <code>llovió 35 mm hoy</code> o <code>/lluvia 25</code></i>")
    return "\n".join(lineas)


def formatear_balance_forrajero_panel(db: Database, hoy: Optional[date] = None) -> str:
    """Genera el panel zootécnico de balance forrajero y oferta de materia seca (MS)."""
    ref = hoy or date.today()
    from ..engine.pasture_engine import PastureEngine

    res_lluvia = db.resumen_pluviometrico(hoy=ref)
    mm_30d = res_lluvia["ultimos_30d_mm"]
    f_clima = res_lluvia["factor_crecimiento"]

    # 1. Hato Activo y Demanda
    # Regla Fundamental de Inventario: estado = 'ACTIVO'
    animales_activos = db.query("SELECT id_animal, sexo, fecha_nacimiento FROM animales WHERE estado = 'ACTIVO'")
    total_animales = len(animales_activos)
    if total_animales == 0:
        return "⚖️ No hay animales activos registrados para calcular el balance forrajero."

    total_ugg = 0.0
    for a in animales_activos:
        ult_p = db.query_one("SELECT peso_kg FROM pesajes WHERE animal_id = ? ORDER BY fecha DESC LIMIT 1", (a["id_animal"],))
        if ult_p and ult_p["peso_kg"]:
            total_ugg += PastureEngine.ugg_de_peso(ult_p["peso_kg"])
        else:
            es_h = str(a["sexo"] or "").lower().startswith("h")
            fn = to_date(a["fecha_nacimiento"])
            ed = (ref - fn).days if fn else 1000
            if ed < 365:
                total_ugg += 0.35
            elif ed < 730:
                total_ugg += 0.65
            else:
                total_ugg += 1.00 if es_h else 1.30

    demanda_ms = total_ugg * 12.6

    # 2. Oferta de Potreros
    potreros = db.query("SELECT * FROM potreros WHERE area_has IS NOT NULL AND area_has > 0")
    total_has = sum(float(p["area_has"] or 0) for p in potreros)
    oferta_neta_total = 0.0
    for p in potreros:
        aforo = float(p["aforo_kg_m2"] or 1.2)
        has = float(p["area_has"] or 0)
        oferta_neta_total += PastureEngine.kg_ms_disponibles(aforo, has) * f_clima

    if total_has == 0:
        total_has = 50.0
        oferta_neta_total = PastureEngine.kg_ms_disponibles(1.2, total_has) * f_clima

    bal = PastureEngine.balance_forrajero(oferta_neta_total, demanda_ms, dias_rotacion=33)
    carga_act = round(total_ugg / total_has, 2) if total_has > 0 else 0.0
    carga_sug = PastureEngine.capacidad_carga_dinamica_ha(1.2, dias_rotacion=33, mm_lluvia_30d=mm_30d)

    signo = "+" if bal["balance_diario_kg_ms"] > 0 else ""
    lineas = [
        "🌾 <b>BALANCE FORRAJERO & MATERIA SECA (MS)</b>",
        f"🌧️ <b>Lluvia (30d):</b> {mm_30d:.1f} mm · <b>Ajuste Clima:</b> {f_clima:.2f}x",
        "────────────────────────────────────────",
        f"🐮 <b>Inventario Activo:</b> <b>{total_animales} animales</b> (<b>{total_ugg:.1f} UGG</b>)",
        f"🌱 <b>Superficie Pasturas:</b> <b>{total_has:.1f} hectáreas</b>",
        f"• <b>Carga Animal Actual:</b> <b>{carga_act} UGG/ha</b>",
        f"• <b>Carga Sostenible Sugerida:</b> <b>{carga_sug} UGG/ha</b>",
        "────────────────────────────────────────",
        f"📥 <b>Demanda Diaria Hato (2.8% PV):</b> <b>{bal['demanda_diaria_kg_ms']:.1f} kg MS/día</b>",
        f"🌾 <b>Oferta Diaria Sostenible:</b> <b>{bal['oferta_diaria_kg_ms']:.1f} kg MS/día</b>",
        f"⚖️ <b>Balance Diario Neto:</b> <b>{signo}{bal['balance_diario_kg_ms']:.1f} kg MS/día</b>",
        f"📈 <b>Índice de Suficiencia:</b> <b>{bal['indice_suficiencia_pct']:.1f}%</b>",
        "────────────────────────────────────────",
        f"{bal['icono']} <b>Diagnóstico:</b> <b>{bal['estado']}</b>",
        f"💡 <b>Recomendación:</b> <i>{bal['recomendacion']}</i>",
    ]
    return "\n".join(lineas)


def formatear_ndvi_panel(db, limite: int = 10) -> str:
    """Genera el panel interactivo de telemetría satelital NDVI (Sentinel-2)."""
    res_ndvi = db.resumen_ndvi_finca()
    potreros = res_ndvi.get("potreros", [])
    if not potreros:
        return "🛰️ <b>MONITOREO SATELITAL NDVI (SENTINEL-2)</b>\n\nNo hay potreros registrados para monitoreo satelital."

    lineas = [
        "🛰️ <b>MONITOREO SATELITAL DE PASTURAS (SENTINEL-2)</b>",
        f"📊 <b>Índice Verde Promedio:</b> <b>{res_ndvi['promedio_ndvi']:.3f}</b> {res_ndvi['emoji_finca']}",
        f"🌿 <b>Estado General:</b> <b>{res_ndvi['categoria_finca']}</b>",
        f"ℹ️ <i>{res_ndvi['descripcion_finca']}</i>",
        "────────────────────────────────────────",
        "🌱 <b>POTREROS ORDENADOS POR VIGOR FORRAJERO:</b>",
    ]

    for p in res_ndvi.get("ranking", [])[:limite]:
        alerta_str = " ⚠️ <i>(Estrés/Sobrepastoreo)</i>" if p["alerta"] else ""
        lineas.append(
            f"• {p['emoji']} <b>{p['potrero_nombre']}</b> ({p['area_has']} ha) — <b>NDVI: {p['ndvi']:.3f}</b>\n"
            f"   └ <i>Aforo satelital:</i> {p['aforo_kg_m2']} kg/m² · <i>Biomasa:</i> {p['biomasa_ms_ha']} kg MS/ha{alerta_str}"
        )

    alertas = res_ndvi.get("alertas_sobrepastoreo", [])
    if alertas:
        lineas.append("────────────────────────────────────────")
        lineas.append(f"⚠️ <b>ALERTA DE DESCANSO OBLIGATORIO ({len(alertas)} potreros):</b>")
        for a in alertas:
            lineas.append(f"• 🔴 <b>{a['potrero_nombre']}</b>: NDVI {a['ndvi']:.3f} ({a['categoria']})")

    lineas.append("────────────────────────────────────────")
    lineas.append("💡 <i>Imágenes Sentinel-2 L2A corregidas atmosféricamente (10m resolución).</i>")
    return "\n".join(lineas)


def formatear_deteccion_potrero_gps(
    det: Optional[dict],
    usuario_nombre: str = "",
    punto: str = "telegram",
    fecha: Optional[str] = None,
    hora: Optional[str] = None,
) -> str:
    """Genera el mensaje HTML del resultado de detectar el potrero por GPS (Telegram/PWA)."""
    from datetime import datetime

    ahora = datetime.now()
    fecha_txt = fecha or ahora.strftime("%Y-%m-%d")
    hora_txt = hora or ahora.strftime("%H:%M")
    quien = f" · 👤 {_esc(usuario_nombre)}" if usuario_nombre else ""
    if not det:
        return (
            "📍 <b>Ubicación recibida</b>, pero estás <b>fuera del área de los potreros</b> de la finca.\n"
            f"🕒 <i>{_esc(fecha_txt)} {_esc(hora_txt)}{quien}</i>\n"
            "No se registró ninguna ronda."
        )
    nombre = _esc(det.get("nombre") or det.get("codigo") or "Potrero")
    dentro = bool(det.get("dentro"))
    try:
        dist_m = float(det.get("distancia_m") or 0.0)
    except (TypeError, ValueError):
        dist_m = 0.0
    area = det.get("area_has")
    try:
        area_txt = f"{float(area):.1f} ha" if area is not None else "S/D"
    except (TypeError, ValueError):
        area_txt = "S/D"
    if dentro or dist_m <= 0:
        ubic_txt = "✅ <b>Estás DENTRO del potrero</b>"
    else:
        ubic_txt = f"📏 Estás <b>a {dist_m:.0f} m del lindero</b> de este potrero"
    lineas = [
        "📍 <b>¿En qué potrero estoy? — Detección GPS</b>",
        f"🌿 <b>Potrero:</b> <b>{nombre}</b>",
        f"• {ubic_txt}",
        f"• <b>Área:</b> {area_txt}",
        f"🕒 <i>{_esc(fecha_txt)} {_esc(hora_txt)}{quien}</i> · 📌 <i>{_esc(punto)}</i>",
        "✅ <i>Ronda guardada en la bitácora de campo.</i>",
        "────────────────────────────────────────",
        "💡 <i>Puedes ver la ocupación con /ocupacion</i>",
    ]
    return "\n".join(lineas)



