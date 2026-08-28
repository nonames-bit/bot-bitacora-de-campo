"""Parser de eventos de campo en lenguaje natural.

Convierte una nota de voz/texto de un mayordomo en un :class:`ParsedEvent`
estructurado y normalizado, listo para persistir en SQLite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Union

from ..utils import iso, normalizar, parse_fecha
from . import nlp_engine as nlu


@dataclass
class ParsedEvent:
    """Evento normalizado extraído de una nota de campo."""
    tipo: str
    texto: str = ""
    animal_tag: Optional[str] = None
    fecha: Optional[str] = None  # ISO YYYY-MM-DD
    datos: dict = field(default_factory=dict)

    def get(self, clave, default=None):
        return self.datos.get(clave, default)


# Palabras que marcan una cría muerta / aborto.
MUERTE_CRIA_RE = re.compile(r"\b(?:nacio muert|naci[oó] muert|aborto|muert[oa])\b")


def _causa_muerte(texto_norm: str) -> Optional[str]:
    """Aísla la causa presunta tras el verbo de muerte."""
    t = texto_norm
    t = re.sub(r"\bse murio (?:el|la)\s+[a-z0-9]+\b", "", t)
    t = re.sub(r"\bmurio (?:el|la)\s+[a-z0-9]+\b", "", t)
    t = re.sub(r"\bse murio\b", "", t)
    t = re.sub(r"\bmurio\b", "", t)
    t = re.sub(r"^\s*(?:por|de)\s+", "", t)
    t = t.strip(" ,.;:-").strip()
    return t or None


class EventParser:
    """Clasifica y normaliza notas de campo en eventos estructurados.

    Implementa arquitectura NLU híbrida:
    - Capa 1: Expresiones regulares locales rápidas (sub-milisegundo).
    - Capa 2: Multi-agente Gemini en la nube (router determinista + extractores
      por dominio) para jerga compleja y múltiples eventos.
    """

    def __init__(self, hoy: date | None = None, use_llm: bool = True):
        self.hoy = hoy or date.today()
        self.use_llm = use_llm

    def _should_try_llm(self, texto: str, intento_regex: Optional[str]) -> bool:
        """Determina si la nota amerita consultar la Capa 2 (LLM en la nube)."""
        if not self.use_llm:
            return False

        t = normalizar(texto)
        palabras = t.split()

        # 1. Si regex no identificó intención conocida
        if intento_regex is None:
            return True

        # 2. Nota larga (> 20 palabras)
        if len(palabras) > 20:
            return True

        # 3. Conectores que sugieren múltiples eventos
        conectores_multiples = (
            r"\by\s+tambien\b", r"\by\s+ademas\b", r"\by\s+luego\b", r"\by\s+despues\b",
            r"\by\s+vacun", r"\by\s+insemin", r"\by\s+pari", r"\by\s+pes",
            r"\by\s+le\s+puse\b", r"\by\s+se\s+muri", r"\by\s+traslad", r"\by\s+pase\b",
            r"\by\s+le\s+di\b", r"\by\s+compre\b", r"\by\s+vendi\b",
        )
        for c in conectores_multiples:
            if re.search(c, t):
                return True

        # 4. Múltiples tags mencionados con múltiples intenciones posibles
        tags = nlu.extraer_tags(t)
        if len(tags) >= 2 and len(palabras) > 8:
            coincidencias = sum(1 for _, patrones in nlu.INTENTOS if any(re.search(p, t) for p in patrones))
            if coincidencias >= 2:
                return True

        return False

    def parse(self, texto: str) -> Union[ParsedEvent, list[ParsedEvent]]:
        if texto is None:
            texto = ""
        t = normalizar(texto)
        fecha = iso(parse_fecha(texto, self.hoy) or self.hoy)

        if nlu.es_consulta(texto):
            return ParsedEvent(tipo="consulta", texto=texto, fecha=fecha)

        intento = nlu.clasificar(texto)

        # Capa 2: Si el texto es complejo o desconocido, intentar LLM híbrido (Gemini primero, luego NVIDIA)
        if self._should_try_llm(texto, intento):
            try:
                from ..llm import try_hybrid_parse
                llm_res = try_hybrid_parse(texto, hoy=self.hoy)
                if llm_res is not None:
                    return llm_res
            except Exception:
                pass  # Fallback silencioso a Capa 1 (regex)

        # Capa 1: Regex local rápida
        if intento is None:
            return ParsedEvent(tipo="desconocido", texto=texto, fecha=fecha)

        tag = nlu.extraer_tag(texto)
        ev = ParsedEvent(tipo=intento, texto=texto, animal_tag=tag, fecha=fecha)

        handler = getattr(self, f"_parse_{intento}", None)
        if handler:
            handler(ev, t)
        return ev

    def parse_events(self, texto: str) -> list[ParsedEvent]:
        """Garantiza retornar una lista de ParsedEvent (1 o más)."""
        res = self.parse(texto)
        if isinstance(res, list):
            return res
        return [res]

    # ------------------------------------------------------------------ #
    # Handlers por evento
    # ------------------------------------------------------------------ #
    def _parse_parto(self, ev: ParsedEvent, t: str) -> None:
        sexo = nlu.extraer_sexo_cria(t)
        estado = "MUERTO" if MUERTE_CRIA_RE.search(t) else "VIVO"
        peso = nlu.extraer_peso(t)
        ev.datos["sexo_cria"] = sexo
        ev.datos["estado_cria"] = estado
        ev.datos["peso_nacimiento"] = peso
        # Una segunda mención numérica puede ser el tag de la cría.
        tags = nlu.extraer_tags(t)
        if len(tags) >= 2:
            ev.datos["id_cria"] = tags[1]

    def _parse_muerte(self, ev: ParsedEvent, t: str) -> None:
        ev.datos["causa_presunta"] = _causa_muerte(t)

    def _parse_servicio(self, ev: ParsedEvent, t: str) -> None:
        tipo = "MONTA" if re.search(r"\bmont", t) else "IA"
        toro = nlu.extraer_toro(t)
        ev.datos["tipo_servicio"] = tipo
        ev.datos["toro_pajilla"] = toro["toro"]
        ev.datos["raza_toro"] = toro["raza"]

    def _parse_celo(self, ev: ParsedEvent, t: str) -> None:
        ev.datos["am_pm"] = nlu.extraer_am_pm(t)

    def _parse_tratamiento(self, ev: ParsedEvent, t: str) -> None:
        producto = nlu.extraer_producto(t)
        dosis = nlu.extraer_dosis(t)
        via = nlu.extraer_via(t)
        dias = nlu.extraer_dias_retiro(t)
        ev.datos["producto"] = producto
        ev.datos["dosis"] = dosis
        ev.datos["via"] = via
        ev.datos["dias_retiro"] = dias
        # Desglose leche/carne: leche solo si se menciona; carne por defecto.
        retiro = nlu.retiro_leche_carne(t, dias)
        ev.datos["dias_retiro_leche"] = retiro["dias_retiro_leche"]
        ev.datos["dias_retiro_carne"] = retiro["dias_retiro_carne"]

    def _parse_pesaje(self, ev: ParsedEvent, t: str) -> None:
        peso = nlu.extraer_peso(t)
        evento = "Control"
        if re.search(r"\bdestete\b", t):
            evento = "DESTETE"
        elif re.search(r"\bnacimiento\b|\bnaci[oó]\b", t):
            evento = "NACIMIENTO"
        ev.datos["peso_kg"] = peso
        ev.datos["evento"] = evento

    def _parse_traslado(self, ev: ParsedEvent, t: str) -> None:
        potreros = nlu.extraer_potreros(t)
        ev.datos["lote"] = nlu.extraer_lote(t)
        ev.datos["potrero_origen"] = potreros[0] if len(potreros) >= 1 else None
        ev.datos["potrero_destino"] = potreros[1] if len(potreros) >= 2 else None

    def _parse_movimiento(self, ev: ParsedEvent, t: str) -> None:
        if re.search(r"\bcompra|compr[aeoó]|subasta|comprad[oa]", t):
            tipo = "COMPRA"
        elif re.search(r"\bventa|vend[ió]|vendid", t):
            tipo = "VENTA"
        elif re.search(r"\bsalio|salieron|sali[oó]", t):
            tipo = "SALIDA"
        else:
            tipo = "ENTRADA"
        ev.datos["tipo_movimiento"] = tipo
        ev.datos["cantidad"] = nlu.extraer_cantidad(t)
        ev.datos["procedencia_destino"] = "Subasta" if re.search(r"\bsubasta\b", t) else None
