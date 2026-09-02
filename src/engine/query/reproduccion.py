"""Mixin de consultas de reproducción: partos, servicios/IA, genealogía, palpación y secado."""
from __future__ import annotations

import re
from typing import Optional

from ...utils import add_days, iso, to_date
from ..reproductive_engine import fecha_palpacion, fecha_secado


class ReproduccionQueryMixin:
    """Requiere self.db y self.hoy (ver QueryEngine)."""

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

    def _palpacion_pendiente(self) -> str:
        hoy = self.hoy
        servicios = self.db.query(
            """
            SELECT s.* FROM servicios s
            JOIN animales a ON a.id_animal = s.vaca_id
            WHERE a.estado = 'ACTIVO' AND s.fecha IS NOT NULL
            ORDER BY s.fecha
            """
        )
        pendientes = []
        for s in servicios:
            estado_s = s["estado"] if "estado" in s.keys() else None
            if (estado_s or "").upper() in ("CONFIRMADA", "FALLIDO", "VACIA", "VACÍA", "PREÑADA", "PRENADA"):
                continue
            diag = self.db.query_one(
                "SELECT id FROM diagnosticos_gestacion WHERE vaca_id = ? AND fecha >= ? LIMIT 1",
                (s["vaca_id"], s["fecha"]),
            )
            if diag:
                continue
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

    # ------------------------------------------------------------------ #
    # Consultas de lista (varios animales a la vez), no de un solo tag.
    # ------------------------------------------------------------------ #
    def _dias_abiertos_mayor(self, umbral: int = 90) -> str:
        """Vacas activas paridas cuyos días abiertos (desde el último parto, sin
        servicio posterior) superan el umbral indicado."""
        vacas = self.db.query(
            """
            SELECT a.id_animal, a.tag, a.nombre, MAX(p.fecha) AS ultimo_parto
            FROM partos p
            JOIN animales a ON a.id_animal = p.vaca_id
            WHERE a.estado = 'ACTIVO' AND p.fecha IS NOT NULL
              AND (p.id_cria IS NULL OR p.id_cria != a.id_animal)
            GROUP BY a.id_animal
            """
        )
        resultado = []
        for v in vacas:
            f_parto = to_date(v["ultimo_parto"])
            if not f_parto:
                continue
            dias = (self.hoy - f_parto).days
            if dias < umbral:
                continue
            ult_serv = self.db.ultimo_servicio(v["id_animal"])
            if ult_serv and ult_serv["fecha"] and to_date(ult_serv["fecha"]) and to_date(ult_serv["fecha"]) >= f_parto:
                continue
            nom = f" ({v['nombre']})" if v["nombre"] else ""
            resultado.append((dias, f"{v['tag']}{nom}: {dias} días"))

        if not resultado:
            return f"✅ No hay vacas con más de {umbral} días abiertos actualmente."
        resultado.sort(key=lambda x: -x[0])
        lineas = [f"⚠️ <b>Vacas con más de {umbral} días abiertos ({len(resultado)}):</b>"]
        lineas.extend(f"• {texto}" for _, texto in resultado[:20])
        if len(resultado) > 20:
            lineas.append(f"<i>... y {len(resultado) - 20} más.</i>")
        return "\n".join(lineas)

    def _partos_periodo(self, desde: str, hasta: str, etiqueta: str = "en el periodo") -> str:
        """Lista de partos ocurridos entre desde y hasta (fechas ISO), con conteo por sexo de cría."""
        partos = self.db.query(
            """
            SELECT p.*, a.tag, a.nombre
            FROM partos p
            JOIN animales a ON a.id_animal = p.vaca_id
            WHERE p.fecha >= ? AND p.fecha <= ? AND (p.id_cria IS NULL OR p.id_cria != a.id_animal)
            ORDER BY p.fecha DESC
            """,
            (desde, hasta),
        )
        if not partos:
            return f"No hubo partos registrados {etiqueta}."
        machos = sum(1 for p in partos if (p["sexo_cria"] or "").strip().lower().startswith("m"))
        hembras = sum(1 for p in partos if (p["sexo_cria"] or "").strip().lower().startswith("h"))
        lineas = [f"🍼 <b>Partos {etiqueta} ({len(partos)}):</b> {hembras} hembra(s), {machos} macho(s)"]
        for p in partos[:15]:
            nom = f" ({p['nombre']})" if p["nombre"] else ""
            sexo = f" · cría {p['sexo_cria']}" if p["sexo_cria"] else ""
            lineas.append(f"• {p['fecha']} — {p['tag']}{nom}{sexo}")
        if len(partos) > 15:
            lineas.append(f"<i>... y {len(partos) - 15} más.</i>")
        return "\n".join(lineas)

    def _crias_por_sexo(self, sexo: str, desde: str | None = None, hasta: str | None = None, etiqueta: str = "") -> str:
        """Cuenta crías nacidas (vivas o no) filtradas por sexo, opcionalmente en un rango de fechas."""
        sexo_norm = "macho" if sexo.lower().startswith("m") else "hembra"
        query = (
            "SELECT p.* FROM partos p "
            "WHERE p.sexo_cria IS NOT NULL AND LOWER(p.sexo_cria) LIKE ? "
            "AND (p.id_cria IS NULL OR p.id_cria != p.vaca_id)"
        )
        params: list = [f"{sexo_norm}%"]
        if desde is not None:
            query += " AND p.fecha >= ? AND p.fecha <= ?"
            params.extend([desde, hasta or iso(self.hoy)])
        crias = self.db.query(query, tuple(params))
        etiqueta_periodo = f" {etiqueta}" if etiqueta else ""
        plural = "machos" if sexo_norm == "macho" else "hembras"
        return f"🐮 Crías {plural} nacidas{etiqueta_periodo}: <b>{len(crias)}</b>."

    def _vacas_proximas_parir(self, dias: int = 30) -> str:
        """Vacas activas con servicio vigente cuya FEP cae dentro de los próximos N días."""
        limite = iso(add_days(self.hoy, dias))
        hoy_iso = iso(self.hoy)
        servicios = self.db.query(
            """
            SELECT s.*, a.tag, a.nombre
            FROM servicios s
            JOIN animales a ON a.id_animal = s.vaca_id
            WHERE a.estado = 'ACTIVO' AND s.fep_calculada IS NOT NULL
              AND s.fep_calculada >= ? AND s.fep_calculada <= ?
            ORDER BY s.fep_calculada ASC
            """,
            (hoy_iso, limite),
        )
        if not servicios:
            return f"No hay vacas con parto próximo en los siguientes {dias} días."
        lineas = [f"🔴 <b>Partos próximos (≤{dias}d) — {len(servicios)} vaca(s):</b>"]
        for s in servicios[:20]:
            nom = f" ({s['nombre']})" if s["nombre"] else ""
            lineas.append(f"• {s['tag']}{nom}: FEP {s['fep_calculada']}")
        return "\n".join(lineas)

    def _partos_atrasados(self) -> str:
        """Hembras activas cuya Fecha Estimada de Parto (FEP) ya se venció y
        no tienen un parto registrado desde ese servicio: señal de aborto no
        reportado, servicio fallido o fecha de servicio mal registrada.
        Basado en la sección 13.13 del manual de Software Ganadero
        ('Hembras que debían haber parido'). Solo se considera el servicio
        más reciente de cada vaca."""
        hoy_iso = iso(self.hoy)
        servicios = self.db.query(
            """
            SELECT s.*, a.tag, a.nombre
            FROM servicios s
            JOIN animales a ON a.id_animal = s.vaca_id
            WHERE a.estado = 'ACTIVO' AND s.fep_calculada IS NOT NULL AND s.fep_calculada < ?
            ORDER BY s.fecha DESC
            """,
            (hoy_iso,),
        )
        vistas: set = set()
        atrasadas = []
        for s in servicios:
            if s["vaca_id"] in vistas:
                continue
            vistas.add(s["vaca_id"])
            parto = self.db.query_one(
                "SELECT id FROM partos WHERE vaca_id = ? AND fecha >= ? LIMIT 1",
                (s["vaca_id"], s["fecha"]),
            )
            if parto:
                continue
            fep_date = to_date(s["fep_calculada"])
            dias_atraso = (self.hoy - fep_date).days if fep_date else 0
            nom = f" ({s['nombre']})" if s["nombre"] else ""
            atrasadas.append((
                dias_atraso,
                f"{s['tag']}{nom}: FEP {s['fep_calculada']} ({dias_atraso} días de atraso)",
            ))

        if not atrasadas:
            return "✅ No hay hembras con parto atrasado: todas las FEP vencidas ya tienen parto registrado."
        atrasadas.sort(key=lambda x: -x[0])
        lineas = [f"🔴 <b>Hembras que debían haber parido ({len(atrasadas)}):</b>"]
        lineas.extend(f"• {texto}" for _, texto in atrasadas[:20])
        if len(atrasadas) > 20:
            lineas.append(f"<i>... y {len(atrasadas) - 20} más.</i>")
        lineas.append("")
        lineas.append(
            "<i>Revise si hubo aborto no reportado, servicio fallido o la fecha del servicio quedó mal registrada.</i>"
        )
        return "\n".join(lineas)

    def _vacas_lactancia_larga(self, umbral_del: int = 200) -> str:
        """Vacas activas con días en leche (DEL) desde el último parto por encima del umbral
        (candidatas a secado)."""
        vacas = self.db.query(
            """
            SELECT a.id_animal, a.tag, a.nombre, MAX(p.fecha) AS ultimo_parto
            FROM partos p
            JOIN animales a ON a.id_animal = p.vaca_id
            WHERE a.estado = 'ACTIVO' AND p.fecha IS NOT NULL
              AND (p.id_cria IS NULL OR p.id_cria != a.id_animal)
            GROUP BY a.id_animal
            """
        )
        resultado = []
        for v in vacas:
            f_parto = to_date(v["ultimo_parto"])
            if not f_parto:
                continue
            del_dias = (self.hoy - f_parto).days
            if del_dias < umbral_del:
                continue
            nom = f" ({v['nombre']})" if v["nombre"] else ""
            resultado.append((del_dias, f"{v['tag']}{nom}: {del_dias} DEL"))

        if not resultado:
            return f"✅ No hay vacas con más de {umbral_del} días de lactancia actualmente."
        resultado.sort(key=lambda x: -x[0])
        lineas = [f"🟡 <b>Vacas con más de {umbral_del} días de lactancia / candidatas a secado ({len(resultado)}):</b>"]
        lineas.extend(f"• {texto}" for _, texto in resultado[:20])
        if len(resultado) > 20:
            lineas.append(f"<i>... y {len(resultado) - 20} más.</i>")
        return "\n".join(lineas)

    # ------------------------------------------------------------------ #
    # Consultas Fase 5.1: Termo de Inseminación, Pajuelas y Diagnósticos
    # ------------------------------------------------------------------ #
    def _stock_pajuelas(self, codigo_toro: Optional[str] = None) -> str:
        """Consulta el inventario de pajuelas en el termo criogénico."""
        if codigo_toro:
            paj = self.db.obtener_pajuela(codigo_toro)
            if not paj:
                return f"🧪 No hay registro de pajuelas para el toro <b>{codigo_toro}</b>."
            can = f" (Canastilla {paj['canastilla']})" if paj["canastilla"] else ""
            raza = f" · {paj['raza']}" if paj["raza"] else ""
            alerta = " ⚠️ [STOCK CRÍTICO]" if paj["cantidad"] <= 2 else ""
            costo_str = f"\n• Costo unitario: ${paj['costo']:,.0f}" if paj["costo"] else ""
            return (
                f"🧪 <b>Pajuelas Toro {paj['codigo_toro']}{raza}</b>\n"
                f"• Stock disponible: <b>{paj['cantidad']} unidades</b>{alerta}\n"
                f"• Ubicación: {can or 'Sin canastilla asignada'}"
                f"{costo_str}"
            ).strip()

        pajuelas = self.db.listar_pajuelas()
        if not pajuelas:
            return "🧪 El termo criogénico no tiene pajuelas registradas actualmente."

        total_unidades = sum(p["cantidad"] for p in pajuelas)
        lineas = [f"🧪 <b>Inventario de Pajuelas ({len(pajuelas)} toros, {total_unidades} pajuelas):</b>"]
        for p in pajuelas:
            can = f" [Canastilla {p['canastilla']}]" if p["canastilla"] else ""
            raza = f" ({p['raza']})" if p["raza"] else ""
            aviso = " ⚠️ <i>(Bajo)</i>" if p["cantidad"] <= 2 else ""
            lineas.append(f"• <b>{p['codigo_toro']}</b>{raza}: {p['cantidad']} unid.{can}{aviso}")
        return "\n".join(lineas)

    def _estado_termo_nitrogeno(self) -> str:
        """Estado del tanque criogénico y días restantes para la próxima recarga de N2."""
        termo = self.db.ultimo_estado_termo(self.hoy)
        if not termo:
            return "❄️ No hay registro de recargas de nitrógeno en el termo criogénico."

        f_rec = termo["fecha_recarga"]
        prox = termo["proxima_recarga"]
        dias_desde = termo["dias_desde_recarga"]
        dias_rest = termo["dias_restantes"]

        if dias_rest < 0:
            icono = "🚨"
            estado_txt = f"<b>VENCIDO</b> (atraso de {abs(dias_rest)} días)"
        elif dias_rest <= 5:
            icono = "⚠️"
            estado_txt = f"<b>CRÍTICO</b> ({dias_rest} días restantes)"
        else:
            icono = "✅"
            estado_txt = f"<b>NORMAL</b> ({dias_rest} días restantes)"

        return (
            f"❄️ <b>Estado del Termo Criogénico (Nitrógeno Líquido)</b>\n"
            f"• Estado: {icono} {estado_txt}\n"
            f"• Última recarga: <b>{f_rec}</b> (hace {dias_desde} días)\n"
            f"• Próxima recarga: <b>{prox}</b>\n"
            f"• Intervalo seguro: cada {termo['dias_intervalo']} días"
        )

    def _kpis_concepcion_y_sc(self, toro: Optional[str] = None) -> str:
        """Reporte de Tasa de Concepción y Servicios por Concepción (S/C)."""
        kpis = self.db.kpis_reproductivos_concepcion(toro)
        if not kpis or (kpis["total_servicios"] == 0 and kpis["total_evaluados"] == 0):
            return "📊 No hay suficientes servicios o diagnósticos registrados para calcular KPIs de concepción."

        sc_str = f"{kpis['servicios_por_concepcion']:.2f}" if kpis["servicios_por_concepcion"] else "N/D"
        lineas = [
            "🧬 <b>KPIs Reproductivos — Eficiencia de Inseminación</b>",
            f"• Total servicios: <b>{kpis['total_servicios']}</b> | Evaluados: <b>{kpis['total_evaluados']}</b>",
            f"• Confirmadas preñadas: <b>{kpis['total_prenadas']}</b>",
            f"• Vacías / Fallidos: <b>{kpis['total_vacias']}</b>",
            f"• 🎯 <b>Tasa de Concepción: {kpis['tasa_concepcion']:.1f}%</b>",
            f"• 🐂 <b>Servicios por Concepción (S/C): {sc_str}</b> (Meta: ≤ 1.7)",
        ]

        if kpis.get("por_toro") and len(kpis["por_toro"]) > 1:
            lineas.append("\n<b>Desglose por Reproductor / Pajuela:</b>")
            for t in kpis["por_toro"][:8]:
                sc_t = f"{t['sc']:.2f}" if t['sc'] else "N/D"
                lineas.append(f"• <b>{t['toro']}</b>: {t['tasa_concepcion']:.1f}% concepción ({t['prenadas']}/{t['evaluados']}) | S/C: {sc_t}")

        return "\n".join(lineas)

    def _ultimos_diagnosticos_gestacion(self, limit: int = 10) -> str:
        """Lista los diagnósticos de gestación más recientes."""
        diags = self.db.listar_diagnosticos(limit=limit)
        if not diags:
            return "🩺 No hay diagnósticos de gestación registrados recientemente."

        lineas = [f"🩺 <b>Últimos {len(diags)} Diagnósticos de Gestación:</b>"]
        for d in diags:
            res_ico = "🤰" if (d["resultado"] or "").upper() == "PREÑADA" else "⭕"
            dias = f" ({d['dias_gestacion']}d gestación)" if d["dias_gestacion"] else ""
            nom = f" ({d['nombre']})" if d["nombre"] else ""
            lineas.append(f"• {d['fecha']} — {d['tag']}{nom}: {res_ico} <b>{d['resultado']}</b>{dias}")
        return "\n".join(lineas)
