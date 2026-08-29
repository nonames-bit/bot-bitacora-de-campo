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
from ..utils import add_days, iso
from .auth import Auth

logger = logging.getLogger("bitacora.bot")


# ---------------------------------------------------------------------- #
# Lógica pura / formateadores independientes del SDK
# ---------------------------------------------------------------------- #
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
    """Devuelve el texto del comando /start o /help adaptado al rol del usuario."""
    if rol == "OWNER":
        return (
            "👑 Comandos disponibles (Propietario / OWNER):\n\n"
            "📝 Bitácora & Consultas:\n"
            "• Envía cualquier nota de texto (ej. 'pario la 47 ternero macho')\n"
            "• Envía preguntas (ej. '¿cuándo parió la 47?')\n"
            "• Envía notas de voz o fotos de aretes/frascos\n\n"
            "📊 Administración:\n"
            "• /alertas - Ver alertas pendientes\n"
            "• /historial <tag> - Historial de un animal\n"
            "• /potreros - Potreros listos para pastoreo\n"
            "• /animales - Resumen de inventario\n"
            "• /fotos [tag] - Ver fotos registradas (o /foto <tag>)\n"
            "• /status - Estado del sistema y base de datos\n"
            "• /usuarios - Lista de usuarios y roles\n"
            "• /reporte [diario|semanal|N] - Generar reporte en PDF\n"
            "• /exportar - Descargar backup ZIP para Software Ganadero\n"
            "• /importar - Instrucciones para importar backup DBF\n"
            "• /confirmar_importar - Procesar backup subido\n"
            "• /descartar_backup - Eliminar backup pendiente\n\n"
            "⚙️ Gestión de Usuarios & Sistema:\n"
            "• /agregar_usuario <user_id> <ROL> [nombre] - Registrar o actualizar usuario\n"
            "• /quitar_usuario <user_id> - Eliminar usuario\n"
            "• /logs - Ver últimas líneas del registro del bot\n\n"
            "🆘 ¿Agregar un trabajador nuevo?\n"
            "1. Pídele que busque el bot y le mande /start (verá \"No autorizado\")\n"
            "2. Consigue su user_id: que él busque @userinfobot → /start (Id) o revisa \"grep no autorizado /root/bitacora/bot.log\"\n"
            "3. Agrégalo: /agregar_usuario 712345678 TRABAJADOR Carlos\n"
            "4. Verifica: /usuarios | Para quitar: /quitar_usuario 712345678\n"
            "Roles: TRABAJADOR (solo reporta), ADMIN (ve reportes), OWNER (todo)"
        )
    if rol == "ADMIN":
        return (
            "🛠️ Comandos disponibles (Administrador):\n\n"
            "📝 Bitácora & Consultas:\n"
            "• Envía cualquier nota de texto (ej. 'pario la 47 ternero macho')\n"
            "• Envía preguntas (ej. '¿cuándo parió la 47?')\n"
            "• Envía notas de voz o fotos de aretes/frascos\n\n"
            "📊 Administración:\n"
            "• /alertas - Ver alertas pendientes\n"
            "• /historial <tag> - Historial de un animal\n"
            "• /potreros - Potreros listos para pastoreo\n"
            "• /animales - Resumen de inventario\n"
            "• /fotos [tag] - Ver fotos registradas (o /foto <tag>)\n"
            "• /status - Estado del sistema y base de datos\n"
            "• /usuarios - Lista de usuarios y roles\n"
            "• /reporte [diario|semanal|N] - Generar reporte en PDF\n"
            "• /exportar - Descargar backup ZIP para Software Ganadero\n"
            "• /importar - Instrucciones para importar backup DBF\n"
            "• /confirmar_importar - Procesar backup subido\n"
            "• /descartar_backup - Eliminar backup pendiente"
        )
    if rol == "TRABAJADOR":
        return (
            "📋 Comandos disponibles (Trabajador / Campo):\n\n"
            "📝 Bitácora & Consultas:\n"
            "• Envía notas de texto de eventos (partos, celos, servicios, tratamientos, pesajes, etc.)\n"
            "• Haz preguntas en lenguaje natural (ej. '¿cuándo parió la 47?')\n"
            "• Envía notas de voz con reportes de campo (transcripción automática)\n"
            "• Envía fotos de aretes o tratamientos\n"
            "• /consulta <tag> o /historial <tag> - Consultar ficha zootécnica de un animal\n"
            "• /fotos [tag] - Ver fotos registradas (o /foto <tag>)\n"
            "• /menu - Abrir el menú táctil de botones\n"
            "• /ayuda - Mostrar esta lista de comandos"
        )
    return "⛔ No autorizado."


def texto_menu_principal(rol: Optional[str]) -> str:
    """Devuelve el texto corto y visual para el menú principal con botones (/start o /menu)."""
    if rol == "OWNER":
        return (
            "👑 <b>Panel de Control (Dueño)</b>\n"
            "Bienvenido a la <i>Bitácora de Campo Ganadero</i>.\n\n"
            "Selecciona una opción del menú o escribe directamente tu consulta o nota:"
        )
    if rol == "ADMIN":
        return (
            "🛠️ <b>Panel de Control (Administrador)</b>\n"
            "Bienvenido a la <i>Bitácora de Campo Ganadero</i>.\n\n"
            "Selecciona una opción del menú o escribe tu consulta o nota:"
        )
    if rol == "TRABAJADOR":
        return (
            "🤠 <b>Menú del Trabajador de Campo</b>\n"
            "¡Bienvenido! Este bot es su cuaderno digital de la finca.\n\n"
            "Seleccione una opción o envíe su nota de voz, foto o mensaje:"
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
                InlineKeyboardButton("📝 Cómo Anotar Reportes", callback_data="cmd:ejemplos"),
                InlineKeyboardButton("🔍 Cómo Hacer Preguntas", callback_data="guia:consultas"),
            ],
            [
                InlineKeyboardButton("📷 Fotos Aretes y Remedios", callback_data="guia:fotos"),
                InlineKeyboardButton("🐮 Consultar un Animal", callback_data="guia:animal"),
            ],
            [
                InlineKeyboardButton("🎤 Cómo Mandar Audios", callback_data="guia:audios"),
                InlineKeyboardButton("📷 Galería de Fotos", callback_data="cmd:fotos"),
            ],
            [
                InlineKeyboardButton("📖 Ver Todos los Comandos", callback_data="cmd:ayuda"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def crear_teclado_admin(rol: Optional[str]) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("📊 Inventario Hato", callback_data="cmd:inventario"),
                InlineKeyboardButton("🐮 Tablero de la Finca", callback_data="cmd:status"),
            ],
            [
                InlineKeyboardButton("⚠️ Alertas Pendientes", callback_data="cmd:alertas"),
                InlineKeyboardButton("🌿 Potreros Voisin", callback_data="cmd:potreros"),
            ],
            [
                InlineKeyboardButton("📋 Reporte Semanal PDF", callback_data="cmd:reporte"),
                InlineKeyboardButton("📦 Descargar Backup ZIP", callback_data="cmd:exportar"),
            ],
            [
                InlineKeyboardButton("⚙️ Servidor & Sistema", callback_data="cmd:sistema"),
                InlineKeyboardButton("📷 Galería Fotos", callback_data="cmd:fotos"),
            ],
        ]
        if rol == "OWNER":
            keyboard.append([
                InlineKeyboardButton("👥 Usuarios / Permisos", callback_data="cmd:usuarios"),
                InlineKeyboardButton("💡 Modo Guía de Campo", callback_data="menu:campo"),
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("💡 Modo Guía de Campo", callback_data="menu:campo"),
            ])
        keyboard.append([
            InlineKeyboardButton("📖 Comandos", callback_data="cmd:ayuda"),
        ])
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
                InlineKeyboardButton("⚖️ Pesajes", callback_data=f"pesos:{tag_clean}"),
                InlineKeyboardButton("🧬 Reproducción", callback_data=f"repro:{tag_clean}"),
            ],
            [
                InlineKeyboardButton("🌱 Potrero", callback_data=f"ubica:{tag_clean}"),
                InlineKeyboardButton("💊 Retiro", callback_data=f"retiro:{tag_clean}"),
            ],
            [
                InlineKeyboardButton("📷 Ver Foto", callback_data=f"foto:{tag_clean}"),
                InlineKeyboardButton("📋 Ficha Completa", callback_data=f"ficha:{tag_clean}"),
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
            if not auth.puede_administrar(user_id):
                await update.message.reply_text("⛔ No autorizado.")
                return
            msg = formatear_alertas(db)
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error("Error en cmd_alertas: %s", e, exc_info=True)
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
                    ruta = r.get("ruta")
                    tag_foto = r.get("tag") or "Sin arete"
                    fec = r.get("fecha") or "sin fecha"
                    cap = f" — {r['caption']}" if r.get("caption") else ""
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
                if not auth.puede_administrar(user_id):
                    if query.message:
                        await query.message.reply_text("⛔ No autorizado.")
                    return
                msg = formatear_alertas(db)
                if query.message:
                    await query.message.reply_text(msg)

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
                    ruta = r.get("ruta")
                    tag_foto = r.get("tag") or "Sin arete"
                    fec = r.get("fecha") or "sin fecha"
                    cap = f" — {r['caption']}" if r.get("caption") else ""
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

            elif data.startswith("pesos:"):
                tag = data.split("pesos:", 1)[1].strip()
                await query.answer()
                qe = QueryEngine(db)
                msg = qe.responder(f"cuanto peso la {tag}")
                if query.message:
                    await query.message.reply_text(msg)

            elif data.startswith("repro:"):
                tag = data.split("repro:", 1)[1].strip()
                await query.answer()
                qe = QueryEngine(db)
                msg = qe.responder(f"servicio de {tag}")
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML")
                    except Exception:
                        await query.message.reply_text(msg)

            elif data.startswith("ubica:"):
                tag = data.split("ubica:", 1)[1].strip()
                await query.answer()
                qe = QueryEngine(db)
                msg = qe.responder(f"en que potrero esta {tag}")
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML")
                    except Exception:
                        await query.message.reply_text(msg)

            elif data.startswith("retiro:"):
                tag = data.split("retiro:", 1)[1].strip()
                await query.answer()
                qe = QueryEngine(db)
                msg = qe.responder(f"retiro de {tag}")
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML")
                    except Exception:
                        await query.message.reply_text(msg)

            elif data.startswith("ficha:"):
                tag = data.split("ficha:", 1)[1].strip()
                await query.answer()
                msg = formatear_historial(db, tag)
                if query.message:
                    try:
                        await query.message.reply_text(msg, parse_mode="HTML")
                    except Exception:
                        await query.message.reply_text(msg)

            elif data == "cmd:historial":
                await query.answer()
                if query.message:
                    await query.message.reply_text(
                        "📋 Para consultar la ficha de un animal, escribe:\n/historial <tag> (ej. /historial 47) o directamente el número de arete."
                    )

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
    app.add_handler(CommandHandler("alertas", cmd_alertas))
    app.add_handler(CommandHandler(["historial", "consulta", "ficha", "info", "vaca", "animal", "buscar"], cmd_historial))
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
