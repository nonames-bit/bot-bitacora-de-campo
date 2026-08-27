"""Motor de consultas: respuestas zootécnicas a preguntas en lenguaje natural."""
from __future__ import annotations

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


class QueryEngine:
    """Responde preguntas frecuentes del personal de campo."""

    def __init__(self, db: Database, hoy: date | None = None):
        self.db = db
        self.hoy = hoy or date.today()

    def responder(self, texto: str) -> str:
        t = normalizar(texto)
        tag = nlu.extraer_tag(texto)

        if re.search(r"\bpalpacion", t) and re.search(r"\bpendiente", t):
            return self._palpacion_pendiente()
        if re.search(r"\binsemin", t) or (
            re.search(r"\b(?:toca|tocan|debo|deben|debemos|tengo que|servir)\b", t)
            and re.search(r"\bservicio\b|\bia\b", t)
        ):
            return self._inseminacion_programada()
        if re.search(r"\bsecado\b", t):
            return self._secado(tag)
        if re.search(r"\bretiro\b", t):
            return self._en_retiro()
        if re.search(r"\b(?:historial|ficha|hoja de vida|consulta|info|informacion|datos)\b", t) and tag:
            return self._historial(tag)
        if re.search(r"\bhistorial\b|\bficha\b", t):
            return self._historial(tag)
        if re.search(r"\bpes[oó]\b|\bganancia\b|\bkg\b|\bkilos\b", t):
            return self._pesaje(tag)
        if re.search(r"\bpotrero", t) and re.search(r"\blisto|pastoreo|pastar", t):
            return self._potreros_listos()
        if re.search(r"\bfoto[s]?\b|\bimagen(?:es)?\b", t):
            return self._fotos(tag)
        if re.search(r"\bpari[oó]\b|\bparto\b", t):
            return self._ultimo_parto(tag)
        return self._ayuda()

    # ------------------------------------------------------------------ #
    def _ultimo_parto(self, tag) -> str:
        if not tag:
            return "¿De cuál animal desea saber el parto? (ej. '¿cuándo parió la 47?')"
        parto = self.db.ultimo_parto(tag)
        if parto is None:
            return f"No hay registro de parto para la {tag}."
        return f"La {tag} parió el {parto['fecha']}."

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
        sexo = animal["sexo"] or "Hembra"
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

        # Historial de eventos
        h = self.db.historial(tag_str)
        partos = h.get("partos", [])
        servicios = h.get("servicios", [])
        celos = h.get("celos", [])
        tratamientos = h.get("tratamientos", [])
        pesajes = h.get("pesajes", [])
        fotos = h.get("fotos", [])

        # Estado reproductivo
        ult_parto = partos[-1] if partos else None
        ult_servicio = servicios[-1] if servicios else None

        estado_reprod = "VACÍA / SIN SERVICIO"
        if sexo.lower().startswith("h"):
            if ult_parto and not ult_servicio:
                estado_reprod = "PARIDA SIN PALPAR"
            elif ult_parto and ult_servicio:
                if to_date(ult_servicio["fecha"]) and to_date(ult_parto["fecha"]) and to_date(ult_servicio["fecha"]) >= to_date(ult_parto["fecha"]):
                    estado_reprod = "PARIDA SERVIDA / SIN PALPAR"
                else:
                    estado_reprod = "PARIDA SIN PALPAR"
            elif ult_servicio:
                estado_reprod = "SERVIDA / PENDIENTE PALPACIÓN"
            elif not partos and not servicios:
                estado_reprod = "NOVILLA / SIN REPORTES"
        else:
            estado_reprod = "MACHO REPRODUCTOR"

        secciones = [
            f"╔══════════════════════════════════════════════════════════════════════╗",
            f"║ FICHA ZOOTÉCNICA: Vaca {tag_str}{nombre} · Raza: {raza} · Potrero: {potrero_nom}",
            f"╠══════════════════════════════════════════════════════════════════════╣",
            f"║ 📍 ESTADO: {estado} · Estado Reproductivo: {estado_reprod}",
            f"║",
            f"║ 🍼 REPRODUCCIÓN & PARTOS:",
        ]

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
            secciones.append(f"║ • partos: {len(partos)} registro(s) · Último Parto: {p['fecha']}{cria_str}")

            f_parto = to_date(p["fecha"])
            if f_parto:
                da = (self.hoy - f_parto).days
                secciones.append(f"║ • Días Abiertos: {da} días (desde el último parto)")
        else:
            secciones.append("║ • partos: 0 registro(s).")

        if servicios:
            s = ult_servicio
            toro_info = f" (Toro/Pajilla {s['toro_pajilla']})" if s["toro_pajilla"] else ""
            tipo_srv = s["tipo_servicio"] or "IA"
            secciones.append(f"║ • servicios: {len(servicios)} registro(s) · Último Servicio: {s['fecha']} [{tipo_srv}]{toro_info}")

            if s["fecha"]:
                fep = s["fep_calculada"] or iso(fecha_estimada_parto(s["fecha"]))
                f_eco = iso(fecha_ecografia(s["fecha"]))
                f_palp = iso(fecha_palpacion(s["fecha"]))
                f_sec = iso(fecha_secado(fep))
                secciones.append(f"║ • Palpación Rectal: PENDIENTE (Programada: {f_palp}, día 60)")
                secciones.append(f"║ • FEP (Fecha Estimada Parto): {fep} (+283 días)")
                secciones.append(f"║ • Secado Programado: {f_sec} (FEP − 60 días)")
        else:
            secciones.append("║ • servicios: 0 registro(s).")

        if celos:
            c = celos[-1]
            turno = f" [{c['am_pm']}]" if c["am_pm"] else ""
            secciones.append(f"║ • celos: {len(celos)} registro(s) · Último Celo: {c['fecha']}{turno}")

        secciones.append("║")
        secciones.append("║ ⚖️ PESAJE & CRECIMIENTO:")
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
            secciones.append(f"║ • pesajes: {len(pesajes)} registro(s) · Último Peso: {ult_p['peso_kg']} kg el {ult_p['fecha']}{gmd_str}")
        else:
            secciones.append("║ • pesajes: 0 registro(s).")

        secciones.append("║")
        secciones.append("║ 💉 SANIDAD & RETIROS:")
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
            secciones.append(f"║ • tratamientos: {len(tratamientos)} registro(s) · Tratamiento: {prod}{dosis} ({retiro_info})")
        else:
            secciones.append("║ • tratamientos: 0 registro(s) · (Sin retiro activo).")

        secciones.append("║")
        if fotos:
            secciones.append(f"║ 📷 FOTOS: {len(fotos)} foto(s) registrada(s) (ver con /foto {tag_str})")
        else:
            secciones.append(f"║ 📷 FOTOS: 0 fotos registradas para este animal.")

        secciones.append("╚══════════════════════════════════════════════════════════════════════╝")
        return "\n".join(secciones)

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

    def _ayuda(self) -> str:
        return (
            "Puedo responder consultas como: '¿cuándo parió la 47?', "
            "'¿qué vacas tienen palpación pendiente?', '¿qué vacas debo "
            "inseminar?', '¿a qué vacas les toca servicio/IA?', '¿cuándo le "
            "toca el secado a la 47?', '¿qué animales están en tiempo de "
            "retiro?', '¿cuál es el historial de la vaca 47?', '¿cuánto pesó "
            "la 12 y cuál fue su ganancia diaria?' y '¿qué potreros están "
            "listos para pastoreo?'."
        )

    def _tag_de(self, animal_id) -> str:
        row = self.db.query_one("SELECT tag FROM animales WHERE id_animal = ?", (animal_id,))
        return row["tag"] if row else str(animal_id)
