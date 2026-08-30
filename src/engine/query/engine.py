"""QueryEngine: enrutador de lenguaje natural que compone los mixins de dominio
(reproducción, sanidad, pasturas, inventario, historial) en una sola API pública."""
from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime

from ...db.database import Database

_logger_sin_entender = logging.getLogger("bitacora.consultas_sin_entender")


def _registrar_consulta_sin_entender(texto: str) -> None:
    """Registra en un archivo aparte las preguntas que el bot no entendió, para
    revisar periódicamente qué frases reales de campo hace falta soportar."""
    try:
        ruta = os.environ.get("CONSULTAS_SIN_ENTENDER_LOG", "data/consultas_sin_entender.log")
        directorio = os.path.dirname(ruta)
        if directorio and not os.path.exists(directorio):
            os.makedirs(directorio, exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')}\t{texto.strip()}\n")
    except Exception:
        _logger_sin_entender.debug("No se pudo registrar consulta sin entender: %s", texto, exc_info=True)
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

        # 1c-bis. Conteos de inventario por edad exacta o por estado (vendidos/muertos).
        # "cuant" (sin exigir la palabra completa) para tolerar errores de dictado
        # por voz como "cuantoa" en vez de "cuantos".
        m_edad = re.search(r"\b(\d+)\s*a[nñ]os?\b", t)
        if m_edad and re.search(r"\bcuant|\bhay\b", t) and not re.search(r"\bdias?\s+abiert", t):
            anios = int(m_edad.group(1))
            sexo_edad = None
            if re.search(r"\bvacas?\b|\bhembras?\b", t):
                sexo_edad = "hembra"
            elif re.search(r"\btoros?\b|\bmachos?\b", t):
                sexo_edad = "macho"
            return self._inventario_por_edad(anios, sexo=sexo_edad)

        # Ventas/compras acotadas a un periodo (ej. "vendieron este mes") usan
        # la tabla movimientos (con fecha real); van antes del conteo histórico
        # sin fecha para no perder el filtro de tiempo.
        if re.search(r"\bvendid[oa]s?\b|\bvend[ií][oó]\b|\bvendieron\b", t) and re.search(r"\beste\s+mes\b|\besta\s+semana\b|\bultimos?\s+\d+\s+dias\b", t):
            if re.search(r"\besta\s+semana\b", t):
                dias_venta = 7
            else:
                m_dv = re.search(r"ultimos?\s+(\d+)\s+dias", t)
                dias_venta = int(m_dv.group(1)) if m_dv else 30
            return self._movimientos_periodo("VENTA", dias_venta)
        if re.search(r"\bcomprad[oa]s?\b|\bcompr[oó]\b|\bcompraron\b", t) and re.search(r"\beste\s+mes\b|\besta\s+semana\b|\bultimos?\s+\d+\s+dias\b", t):
            if re.search(r"\besta\s+semana\b", t):
                dias_compra = 7
            else:
                m_dc = re.search(r"ultimos?\s+(\d+)\s+dias", t)
                dias_compra = int(m_dc.group(1)) if m_dc else 30
            return self._movimientos_periodo("COMPRA", dias_compra)

        if re.search(r"\bvendid[oa]s?\b|\bvend[ií][oó]\b|\bvendieron\b", t) and re.search(r"\bcuant|\bhay\b", t):
            sexo_vendido = "hembra" if re.search(r"\bvacas?\b|\bhembras?\b", t) else ("macho" if re.search(r"\btoros?\b|\bmachos?\b", t) else None)
            return self._conteo_por_estado("VENDIDO", sexo=sexo_vendido)
        if re.search(r"\bmuert[oa]s?\b|\bmuri[oó]\b|\bmurieron\b", t) and re.search(r"\bcuant|\bhay\b", t) and not tag:
            sexo_muerto = "hembra" if re.search(r"\bvacas?\b|\bhembras?\b", t) else ("macho" if re.search(r"\btoros?\b|\bmachos?\b", t) else None)
            return self._conteo_por_estado("MUERTO", sexo=sexo_muerto)

        # 1c. Consultas de lista de reproducción (varios animales a la vez, no un tag puntual)
        if re.search(r"\bdias?\s+abiert[oa]s?\b", t):
            m = re.search(r"(\d+)\s*dias?\s+abiert[oa]s?", t) or re.search(r"mas\s+de\s+(\d+)", t)
            umbral = int(m.group(1)) if m else 90
            return self._dias_abiertos_mayor(umbral)
        if re.search(r"\bpartos?\b", t) and re.search(r"\beste\s+mes\b|\besta\s+semana\b|\bultimos?\s+\d+\s+dias\b", t):
            if re.search(r"\besta\s+semana\b", t):
                dias_periodo = 7
            else:
                m = re.search(r"ultimos?\s+(\d+)\s+dias", t)
                dias_periodo = int(m.group(1)) if m else 30
            return self._partos_periodo(dias_periodo)
        if re.search(r"\btern|\bcrias?\b", t) and re.search(r"\bmacho[s]?\b|\bhembra[s]?\b", t) and re.search(r"\bcuant[oa]s?\b|\bnaci", t):
            sexo = "macho" if re.search(r"\bmacho", t) else "hembra"
            return self._crias_por_sexo(sexo)
        if re.search(r"\bproxim[ao]s?\s+a?\s*parir\b|\bvan\s+a\s+parir\b", t):
            return self._vacas_proximas_parir()
        if re.search(r"\bsecar\b", t) or (re.search(r"\blactancia\b", t) and re.search(r"\bdias\b", t)):
            return self._vacas_lactancia_larga()

        # 2. Partos y maternidad
        if re.search(r"\bcuant[oa]s?\s+partos\b", t):
            # nlu.extraer_tag no reconoce nombres propios tras "tiene" (solo tras "de");
            # se extrae aquí el candidato de forma local sin tocar el extractor compartido.
            m = re.search(r"\bcuant[oa]s?\s+partos\s+tiene\s+(?:la\s+|el\s+)?([a-z0-9]+)", t)
            tag_partos = tag or (m.group(1) if m else None)
            if tag_partos:
                return self._genealogia(tag_partos)
        if re.search(r"\bpari[oó]\b|\bparto\b", t):
            return self._ultimo_parto(tag)

        # 3. Servicios e Inseminación
        if re.search(r"\b(?:que\s+vacas?|cuales\s+vacas?|que\s+animales?|a\s+que\s+vacas?|hay\s+para\s+inseminar)\b", t) or not tag:
            if re.search(r"\binsemin|\bservicio\b|\bpajuela\b|\bmonta\b|\btoca.*servicio\b", t):
                return self._inseminacion_programada()
        if tag and (re.search(r"\binsemin|\bservicio\b|\bpajuela\b|\bmonta\b|\bsirvio\b|\bque\s+toro\b", t)):
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
        # 4a. Historial de tratamientos aplicados (distinto del estado de retiro activo)
        if tag and re.search(r"\btratamientos?\b|\bmedicamentos?\b|\baplic|\bpuso\b|\bpusieron\b", t) and re.search(r"\bcuand[oa]\b|\bultim[oa]s?\b|\bque\b", t):
            return self._tratamientos_animal(tag)
        if not tag and re.search(r"\btratamientos?\b", t) and re.search(r"\bultim[oa]s?\b|\baplicados?\b", t):
            return self._ultimos_tratamientos()
        if re.search(r"\bretiro\b|\bmedicamento\b|\bremedio\b|\bordena", t):
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
        if re.search(r"\bpes[oó]\b|\bpesaje\b|\bganancia\b|\bgmd\b|\bkg\b|\bkilos\b", t):
            return self._pesaje(tag)

        # Ocupación por lote (ej. "días de pastoreo del lote 1")
        if re.search(r"\blote\s+([a-z0-9]+)", t) and re.search(r"\bdias\b|\bpastoreo\b|\bocupaci[oó]n\b|\bdonde\b", t):
            m = re.search(r"\blote\s+([a-z0-9]+)", t)
            return self._lote_ocupacion(m.group(1))

        # Ocupación y rotación de potreros (Voisin)
        if re.search(r"\b(?:ocupaci[oó]n|dias\s+de\s+ocupaci[oó]n|tiempo\s+de\s+ocupaci[oó]n|rotaci[oó]n|rotacion\s+de\s+potreros|rotacion\s+voisin|sobreocupaci[oó]n)\b", t) or re.search(r"\bpotreros?\s+(?:estan\s+)?ocupados?\b", t):
            return self._ocupacion_potreros()

        # Existencias por potrero en formato Software Ganadero (SG)
        if re.search(r"\b(?:existencias?\s+por\s+potreros?|tabla\s+de\s+potreros?|potreros?\s+sg|potreros?\s+software\s+ganadero)\b", t) or (
            re.search(r"\bpotrero", t) and re.search(r"\b(?:existencias?|sg|categor[ií]as?)\b", t)
        ):
            return self._inventario_potreros(formato_sg=True)

        # Consultas combinadas: categoría + potrero en una sola pregunta
        # (ej. "vacas paridas que están en el potrero olegario 1"). Va antes
        # de la sección 8 para que la categoría no se pierda.
        if re.search(r"\bpotrero", t):
            categorias_combo = None
            for palabra, categorias in self.CATEGORIAS_FILTRO.items():
                if re.search(rf"\b{re.escape(palabra)}\b", t):
                    categorias_combo = categorias
                    break
            if categorias_combo:
                nom_pot_combo = extraer_nombre_potrero(texto)
                if nom_pot_combo:
                    return self._animales_en_potrero(nom_pot_combo, categorias_filtro=categorias_combo)

        # Nombre de potrero mencionado sin decir la palabra "potrero" delante
        # (ej. "cuántos animales hay donde olegario", "...en el corral santa
        # martha"). También antes de la sección 8: si no, "cuántos animales..."
        # siempre gana y muestra el resumen general en vez del potrero pedido.
        if re.search(r"\b(?:cuant[oa]s?|hay|donde|estan?|est[aá]n)\b", t):
            campo_pot_temprano = self._potrero_mencionado(t)
            if campo_pot_temprano:
                return self._animales_en_potrero(campo_pot_temprano)

        # 8. Inventario / conteos (consultas diarias: total ganado, total vacas, novillas, inventario potreros) — incluye typo gaando
        if re.search(r"\b(?:total|totales|inventario|cuantos?|cuantas?|cuanto)\b", t) or re.search(r"\bganad", t) or re.search(r"\bga+ndo\b", t):
            # inventario por potrero tiene prioridad si menciona potrero
            if re.search(r"\bpotrero", t):
                # "inventario potreros" o "total por potrero"
                if re.search(r"\b(?:total|inventario|listar|mostrar|resumen|conteo|distribuci[oó]n)\b", t):
                    mostrar_vacios = bool(re.search(r"\bvac[ií]os?\b", t))
                    return self._inventario_potreros(mostrar_vacios=mostrar_vacios)
            # conteos de ganado por categoría (ganado, gaando typo, animal/animales, inventario)
            if re.search(r"\b(?:ganado|ganad|ga+ndo|animales?|inventario)\b", t) or re.search(r"\btotal\b.*\b(?:vaca|toro|terner|novill)", t) or re.search(r"\b(?:vaca|toro|terner|novill).*\btotal\b", t):
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
            campo_pot = self._potrero_mencionado(t)
            if campo_pot:
                return self._animales_en_potrero(campo_pot)

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
        _registrar_consulta_sin_entender(texto)
        return self._ayuda(texto)

    _PALABRAS_GENERICAS_POTRERO = {"potrero", "potreros", "corral", "lote", "del", "los", "las"}

    def _potrero_mencionado(self, t: str) -> str | None:
        """Busca si el texto normalizado menciona el nombre o código de un
        potrero registrado, sin exigir la palabra 'potrero' delante ni el
        nombre completo (ej. 'donde olegario' -> OLEGARIO I, 'en el corral
        santa martha' -> CORRAL SANTAMART, aunque el dato en SG venga
        abreviado/truncado)."""
        palabras_texto = [w for w in t.split() if len(w) >= 4]
        if not palabras_texto:
            return None
        potreros = self.db.query("SELECT nombre, codigo FROM potreros")
        mejor_campo = None
        mejor_score = 0.0
        for p in potreros:
            for campo in (p["nombre"], p["codigo"]):
                if not campo:
                    continue
                campo_norm = normalizar(campo).strip()
                for var in _potrero_variantes(campo_norm):
                    if var and re.search(rf"\b{re.escape(var)}\b", t):
                        return campo  # coincidencia exacta del nombre completo: no hace falta seguir buscando

                palabras_pot = [w for w in campo_norm.split() if w not in self._PALABRAS_GENERICAS_POTRERO and len(w) >= 5]
                if not palabras_pot:
                    continue
                coincidencias = sum(
                    1 for w in palabras_pot
                    if any(w in wt or wt in w for wt in palabras_texto)
                )
                if coincidencias == 0:
                    continue
                score = coincidencias / len(palabras_pot)
                if score > mejor_score:
                    mejor_campo, mejor_score = campo, score
        return mejor_campo if mejor_score >= 0.5 else None

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
