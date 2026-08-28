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
        if re.search(r"\b(?:historial|ficha|hoja de vida|consulta|info|informacion|datos|buscar|ver)\b", t) and tag:
            return self._historial(tag)
        if re.search(r"\b(?:historial|ficha|consulta)\b", t):
            return self._historial(tag)
        if re.search(r"\bpes[oó]\b|\bganancia\b|\bkg\b|\bkilos\b", t):
            return self._pesaje(tag)
        # Inventario / conteos (consultas diarias: total ganado, total vacas, novillas, inventario potreros) — incluye typo gaando
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
        # Fallback: consulta por nombre de potrero sin la palabra "potrero" (ej. "cuantos hay en olegario 1")
        if re.search(r"\b(?:que\s+vacas?|que\s+animales?|cuantas?|cuantos?|hay|estan?|est[aá]n|listar|mostrar)\b", t):
            potreros = self.db.query("SELECT nombre, codigo FROM potreros")
            for p in potreros:
                for campo in (p["nombre"], p["codigo"]):
                    if not campo:
                        continue
                    for var in _potrero_variantes(normalizar(campo)):
                        if var and var in t:
                            return self._animales_en_potrero(campo)
        # Si el mensaje es solo el nombre del potrero (ej. "olegario 1" o "olegario 1?" )
        if len(t.split()) <= 3:
            t_clean = re.sub(r"[?!.,;:¿¡]+$", "", t.strip())
            potreros = self.db.query("SELECT nombre, codigo FROM potreros")
            for p in potreros:
                for campo in (p["nombre"], p["codigo"]):
                    if not campo:
                        continue
                    for var in _potrero_variantes(normalizar(campo)):
                        if var and (var == t_clean or var in t_clean):
                            return self._animales_en_potrero(campo)
        if re.search(r"\bfoto[s]?\b|\bimagen(?:es)?\b", t):
            return self._fotos(tag)
        if re.search(r"\bpari[oó]\b|\bparto\b", t):
            return self._ultimo_parto(tag)
        if tag and len(t.split()) <= 2 and not re.search(r"\b(?:pari|murio|insemin|celo|peso|retiro|potrero|foto)\b", t):
            return self._historial(tag)
        return self._ayuda(texto)

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

        bloques = []

        # Encabezado
        tipo_animal = "Toro" if sexo.lower().startswith("m") else "Vaca"
        nom_txt = f" ({animal['nombre']})" if animal["nombre"] else ""
        header = [
            "📋 <b>FICHA ZOOTÉCNICA</b>",
            f"🐄 <b>{tipo_animal} {tag_str}{nom_txt}</b>",
            f"🏷️ <b>Raza:</b> {raza}",
            f"📍 <b>Potrero:</b> {potrero_nom}",
            f"● <b>Estado:</b> {estado}",
            f"🧬 <b>Reproductivo:</b> {estado_reprod}",
            "───────────────────",
        ]
        bloques.append("\n".join(header))

        # Sección Reproducción
        reprod = ["🍼 <b>REPRODUCCIÓN & PARTOS</b>"]
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
        hembras = self.db.query_one("SELECT COUNT(*) as n FROM animales WHERE estado='ACTIVO' AND UPPER(sexo)='HEMBRA'")
        machos = self.db.query_one("SELECT COUNT(*) as n FROM animales WHERE estado='ACTIVO' AND UPPER(sexo)='MACHO'")
        n_hembras = int(hembras["n"]) if hembras else 0
        n_machos = int(machos["n"]) if machos else 0
        # Terneros aproximados: <12 meses
        terneros = 0
        try:
            rows = self.db.query("SELECT fecha_nacimiento FROM animales WHERE estado='ACTIVO' AND fecha_nacimiento IS NOT NULL")
            for r in rows:
                fn = to_date(r["fecha_nacimiento"])
                if fn and (self.hoy - fn).days < 365:
                    terneros += 1
        except Exception:
            terneros = 0
        detalle = f"🐄 Total en finca: {n_total} animales"
        partes = []
        if n_hembras:
            partes.append(f"{n_hembras} vacas")
        if n_machos:
            partes.append(f"{n_machos} toros")
        if partes:
            detalle += f" ({', '.join(partes)})"
        if terneros:
            detalle += f" — {terneros} terneros <12m incluidos"
        return detalle + "."

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
                has_parto = self.db.query_one("SELECT 1 FROM partos WHERE vaca_id=? LIMIT 1", (aid,))
                if not has_parto:
                    count += 1
            return f"🐄 Total novillas (hembras sin parto): {count}."
        if cat in ("terneros", "ternero", "terneras"):
            rows = self.db.query("SELECT fecha_nacimiento FROM animales WHERE estado='ACTIVO' AND fecha_nacimiento IS NOT NULL")
            count = 0
            for r in rows:
                fn = to_date(r["fecha_nacimiento"])
                if fn and (self.hoy - fn).days < 365:
                    count += 1
            # Fallback si no hay fecha_nacimiento: contar crías con id_cria no nulo en partos
            if count == 0:
                row = self.db.query_one("SELECT COUNT(DISTINCT id_cria) as n FROM partos WHERE id_cria IS NOT NULL")
                count = int(row["n"]) if row and row["n"] else 0
            return f"🐄 Total terneros (<12 meses): {count}."
        return self._inventario_general()

    def _inventario_potreros(self, mostrar_vacios: bool = False) -> str:
        potreros = self.db.query("SELECT * FROM potreros")
        if not potreros:
            return "No hay potreros registrados."

        potreros_by_id = {p["id"]: p for p in potreros}

        # Agrupación por nombre normalizado (case-insensitive, sin duplicados)
        grupos: dict[str, dict] = {}
        for p in potreros:
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
            return f"{n:,}".replace(",", ".")

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

        max_nom_w = max(len(o["display"]) for o in ocupados)
        max_num_w = max(len(fmt_num(o["total"])) for o in ocupados)
        col_w = max(max_nom_w, 16)

        pre_lines = []
        for o in ocupados:
            nom = o["display"].ljust(col_w)
            num = fmt_num(o["total"]).rjust(max_num_w)
            pre_lines.append(f"{nom}  {num}")

        total_animales = sum(o["total"] for o in ocupados)
        total_str = fmt_num(total_animales)

        lineas = [
            f"📍 <b>Inventario por potrero — Ocupados ({len(ocupados)})</b>",
            "<pre>",
            "\n".join(pre_lines),
            "</pre>",
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
            "SELECT id_animal, tag, potrero_id, estado FROM animales "
            "WHERE estado = 'ACTIVO' ORDER BY id_animal"
        )

        tags_en_potrero: list[str] = []
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

        return f"🐄 Potrero '{potrero_nom}': {total} {palabra_animal} ({tags_str})"

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
