"""Mixin de consultas de pasturas: ubicación, traslados, potreros listos/ocupados y rotación Voisin."""
from __future__ import annotations

import html
import re

from ...utils import normalizar, to_date
from .helpers import (
    REPOSO_LISTO_DIAS,
    _fmt_es_co,
    _potrero_variantes,
    calcular_existencias_potreros_sg,
    formatear_ocupacion_potreros,
    formatear_tabla_potreros_sg,
)


class PasturasQueryMixin:
    """Requiere self.db y self.hoy (ver QueryEngine)."""

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

    def _lote_ocupacion(self, lote: str) -> str:
        """Animales cuyo último traslado los asignó al lote indicado, y días desde ese traslado."""
        filas = self.db.query(
            """
            SELECT t.animal_id, t.fecha, t.lote, a.tag
            FROM traslados t
            JOIN animales a ON a.id_animal = t.animal_id
            WHERE a.estado = 'ACTIVO'
            ORDER BY t.fecha ASC, t.id ASC
            """
        )
        ultimos: dict[int, dict] = {}
        for f in filas:
            ultimos[f["animal_id"]] = f  # ordenado ascendente: el último gana

        lote_norm = normalizar(lote)
        del_grupo = [f for f in ultimos.values() if f["lote"] and normalizar(f["lote"]) == lote_norm]
        if not del_grupo:
            return f"No hay animales asignados actualmente al lote '{lote}'."

        fechas = [to_date(f["fecha"]) for f in del_grupo if to_date(f["fecha"])]
        fecha_reciente = max(fechas) if fechas else None
        dias_str = f"{(self.hoy - fecha_reciente).days} días" if fecha_reciente else "fecha desconocida"
        tags = [f["tag"] for f in del_grupo]
        tags_str = ", ".join(tags[:10]) + (f" y {len(tags) - 10} más" if len(tags) > 10 else "")
        return f"🌱 <b>Lote {lote}:</b> {len(tags)} animal(es) ({tags_str}) · {dias_str} de pastoreo."

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

    # Palabras clave de campo -> categoría zootécnica SG, para consultas combinadas
    # (ej. "vacas paridas en olegario 1"). Se compara contra el texto normalizado.
    # "terneros"/"ternero" genérico cubre ambos sexos (uso común de campo); las
    # variantes con "machos" explícito van antes para que el match de frase más
    # específica gane al iterar el diccionario en orden.
    CATEGORIAS_FILTRO: dict[str, list[str]] = {
        "paridas": ["Vacas paridas"],
        "parida": ["Vacas paridas"],
        "secas": ["Vacas secas"],
        "seca": ["Vacas secas"],
        "novillas": ["Novillas vientre (>2a)"],
        "novilla": ["Novillas vientre (>2a)"],
        "toros": ["Toros reproductores"],
        "toro": ["Toros reproductores"],
        "reproductores": ["Toros reproductores"],
        "reproductor": ["Toros reproductores"],
        "terneras": ["Crías hembra (<1a)"],
        "ternera": ["Crías hembra (<1a)"],
        "terneros machos": ["Crías macho (<1a)"],
        "ternero macho": ["Crías macho (<1a)"],
        "terneros": ["Crías hembra (<1a)", "Crías macho (<1a)"],
        "ternero": ["Crías hembra (<1a)", "Crías macho (<1a)"],
    }

    def _animales_en_potrero(self, nombre_potrero: str, categorias_filtro: list[str] | None = None) -> str:
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

        # Conteo y detalle por categorías zootécnicas Software Ganadero (SG)
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
        tags_por_categoria: dict[str, list[str]] = {k: [] for k in conteo_cat}
        for a in animales_en_este:
            aid = a["id_animal"]
            tag_a = a["tag"] or str(aid)
            sexo = (a["sexo"] or "").strip().lower()
            fnac = to_date(a["fecha_nacimiento"])
            edad_d = (self.hoy - fnac).days if fnac else None
            es_h = bool(sexo.startswith("h") or sexo.startswith("f") or sexo in ("vaca", "novilla", "ternera"))

            categoria = None
            if es_h:
                if edad_d is not None and edad_d < 365:
                    categoria = "Crías hembra (<1a)"
                elif edad_d is not None and edad_d < 730:
                    categoria = "Hembras levante (1-2a)"
                else:
                    p_ult = self.db.ultimo_parto(aid)
                    if p_ult and p_ult["fecha"] and to_date(p_ult["fecha"]):
                        dp = (self.hoy - to_date(p_ult["fecha"])).days
                        categoria = "Vacas paridas" if dp <= 305 else "Vacas secas"
                    else:
                        categoria = "Novillas vientre (>2a)"
            else:
                nom_m = (a["nombre"] or "").upper()
                if "REPRODUCTOR" in nom_m or "PADRON" in nom_m or "TORO" in nom_m or (edad_d is not None and edad_d >= 1095):
                    categoria = "Toros reproductores"
                elif edad_d is not None and edad_d < 365:
                    categoria = "Crías macho (<1a)"
                elif edad_d is not None and edad_d < 730:
                    categoria = "Machos levante (1-2a)"
                else:
                    categoria = "Machos ceba"

            conteo_cat[categoria] += 1
            tags_por_categoria[categoria].append(tag_a)

        # Consulta combinada: categoría + potrero (ej. "vacas paridas en olegario 1")
        if categorias_filtro:
            tags_filtrados: list[str] = []
            for cat in categorias_filtro:
                tags_filtrados.extend(tags_por_categoria.get(cat, []))
            etiqueta = " / ".join(categorias_filtro)
            if not tags_filtrados:
                return f"No hay animales de '{etiqueta}' en el potrero '{potrero_nom}'."
            n = len(tags_filtrados)
            palabra = "animal" if n == 1 else "animales"
            return f"🐄 <b>{etiqueta}</b> en potrero '{potrero_nom}': {n} {palabra} ({', '.join(tags_filtrados)})"

        cats_activas = [f"• {k}: {v}" for k, v in conteo_cat.items() if v > 0]
        if cats_activas and total > 1:
            detalle_cat = "\n\n📋 <b>Composición zootécnica:</b>\n" + "\n".join(cats_activas)
            return f"{resumen_base}{detalle_cat}"

        return resumen_base
