"""Mixin de consultas de reproducción: partos, servicios/IA, genealogía, palpación y secado."""
from __future__ import annotations

import re

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
