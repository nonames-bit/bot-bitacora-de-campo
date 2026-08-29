"""QueryEngine: enrutador de lenguaje natural que compone los mixins de dominio
(reproducción, sanidad, pasturas, inventario, historial) en una sola API pública."""
from __future__ import annotations

import re
from datetime import date

from ...db.database import Database
from ...parsers import nlp_engine as nlu
from ...utils import normalizar
from .helpers import _potrero_variantes, extraer_nombre_potrero
from .historial import HistorialQueryMixin
from .inventario import InventarioQueryMixin
from .pasturas import PasturasQueryMixin
from .reproduccion import ReproduccionQueryMixin
from .sanidad import SanidadQueryMixin


class QueryEngine(
    HistorialQueryMixin,
    InventarioQueryMixin,
    PasturasQueryMixin,
    SanidadQueryMixin,
    ReproduccionQueryMixin,
):
    """Responde preguntas frecuentes del personal de campo."""

    extraer_nombre_potrero = staticmethod(extraer_nombre_potrero)

    def __init__(self, db: Database, hoy: date | None = None):
        self.db = db
        self.hoy = hoy or date.today()

    def responder(self, texto: str) -> str:
        t = normalizar(texto)
        tag = nlu.extraer_tag(texto)

        # 1. Ubicación y potrero del animal (ej. "¿en qué potrero está patricia?", "¿dónde está la vaca 47?")
        if (
            re.search(r"\b(?:donde\s+esta|donde\s+anda|donde\s+se\s+encuentra|en\s+que\s+potrero|ubicacion)\b", t)
            or (tag and re.search(r"\bpotrero\b", t) and re.search(r"\b(?:esta|anda|se\s+encuentra|quedo)\b", t))
        ):
            return self._ubicacion_animal(tag)

        # 1b. Traslados y movimientos de potrero (ej. "¿cuándo se movió patricia?", "¿cuándo fue el traslado de la 47?")
        if tag and re.search(r"\b(?:cuando\s+se\s+movi[oó]|cuando\s+se\s+traslad[oó]|cuando\s+se\s+cambi[oó]|cuando\s+fue\s+el\s+traslado|cuando\s+entr[oó]|traslados?|movimientos?)\b", t):
            return self._ultimo_traslado(tag)

        # 2. Partos y maternidad
        if re.search(r"\bpari[oó]\b|\bparto\b", t):
            return self._ultimo_parto(tag)

        # 3. Servicios e Inseminación
        if re.search(r"\b(?:que\s+vacas?|cuales\s+vacas?|que\s+animales?|a\s+que\s+vacas?|hay\s+para\s+inseminar)\b", t) or not tag:
            if re.search(r"\binsemin|\bservicio\b|\bpajuela\b|\bmonta\b|\btoca.*servicio\b", t):
                return self._inseminacion_programada()
        if tag and (re.search(r"\binsemin|\bservicio\b|\bpajuela\b|\bmonta\b", t)):
            return self._ultimo_servicio(tag)
        if re.search(r"\bpalpacion", t) and re.search(r"\bpendiente", t):
            return self._palpacion_pendiente()
        if re.search(r"\binsemin", t) or (
            re.search(r"\b(?:toca|tocan|debo|deben|debemos|tengo que|servir)\b", t)
            and re.search(r"\bservicio\b|\bia\b", t)
        ):
            return self._inseminacion_programada()

        # 4. Secado y retiros
        if re.search(r"\bsecado\b", t):
            return self._secado(tag)
        if re.search(r"\bretiro\b|\bmedicamento\b|\bremedio\b", t):
            if tag:
                return self._retiro_animal(tag)
            return self._en_retiro()

        # 5. Genealogía y familia
        if tag and re.search(r"\b(?:madre|padre|mama|papa|genealogia|familia|hijos?|hijas?|crias?)\b", t):
            return self._genealogia(tag)

        # 6. Ficha zootécnica
        if re.search(r"\b(?:historial|ficha|hoja de vida|consulta|info|informacion|datos|buscar|ver)\b", t) and tag:
            return self._historial(tag)
        if re.search(r"\b(?:historial|ficha|consulta)\b", t):
            return self._historial(tag)

        # 7. Pesaje y crecimiento
        if re.search(r"\bpes[oó]\b|\bganancia\b|\bgmd\b|\bkg\b|\bkilos\b", t):
            return self._pesaje(tag)

        # Ocupación y rotación de potreros (Voisin)
        if re.search(r"\b(?:ocupaci[oó]n|dias\s+de\s+ocupaci[oó]n|tiempo\s+de\s+ocupaci[oó]n|rotaci[oó]n|rotacion\s+de\s+potreros|rotacion\s+voisin)\b", t):
            return self._ocupacion_potreros()

        # Existencias por potrero en formato Software Ganadero (SG)
        if re.search(r"\b(?:existencias?\s+por\s+potreros?|tabla\s+de\s+potreros?|potreros?\s+sg|potreros?\s+software\s+ganadero)\b", t) or (
            re.search(r"\bpotrero", t) and re.search(r"\b(?:existencias?|sg|categor[ií]as?)\b", t)
        ):
            return self._inventario_potreros(formato_sg=True)

        # 8. Inventario / conteos (consultas diarias: total ganado, total vacas, novillas, inventario potreros) — incluye typo gaando
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
        # Ficha directa por arete o nombre corto (ej. "N069", "JA26", "patricia", "47")
        if tag and len(t.split()) <= 2 and not re.search(r"\b(?:pari|murio|insemin|celo|peso|retiro|potrero|foto|total|inventario|vacas|toros|terneros|novillas)\b", t):
            return self._historial(tag)

        # Fallback: consulta por nombre de potrero sin la palabra "potrero" (ej. "cuantos hay en olegario 1")
        if re.search(r"\b(?:que\s+vacas?|que\s+animales?|cuantas?|cuantos?|hay|estan?|est[aá]n|listar|mostrar)\b", t):
            potreros = self.db.query("SELECT nombre, codigo FROM potreros")
            for p in potreros:
                for campo in (p["nombre"], p["codigo"]):
                    if not campo:
                        continue
                    for var in _potrero_variantes(normalizar(campo)):
                        # Coincidencia de palabra completa para evitar que código '06' matchee dentro de 'n069'
                        if var and re.search(rf"\b{re.escape(var)}\b", t):
                            return self._animales_en_potrero(campo)

        # Si el mensaje es solo el nombre exacto de un potrero (ej. "olegario 1" o "olegario 1?" )
        if len(t.split()) <= 3:
            t_clean = re.sub(r"[?!.,;:¿¡]+$", "", t.strip())
            potreros = self.db.query("SELECT nombre, codigo FROM potreros")
            for p in potreros:
                for campo in (p["nombre"], p["codigo"]):
                    if not campo:
                        continue
                    for var in _potrero_variantes(normalizar(campo)):
                        if var and var == t_clean:
                            return self._animales_en_potrero(campo)
        if re.search(r"\bfoto[s]?\b|\bimagen(?:es)?\b", t):
            return self._fotos(tag)
        if re.search(r"\bpari[oó]\b|\bparto\b", t):
            return self._ultimo_parto(tag)
        if tag and len(t.split()) <= 3 and not re.search(r"\b(?:pari|murio|insemin|celo|peso|retiro|potrero|foto)\b", t):
            return self._historial(tag)
        return self._ayuda(texto)

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
