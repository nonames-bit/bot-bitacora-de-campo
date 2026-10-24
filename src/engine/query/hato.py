"""Mixin de consultas sobre el hato presente: conteos por categoría, estado
reproductivo de las vacas, listas de trabajo de Tareas y leche del día.

Todo cuenta solo animales con ``estado = 'ACTIVO'`` (regla de inventario del
proyecto); las listas de trabajo salen de ``engine/tareas.py`` para que el
asistente diga lo mismo que la pantalla Tareas."""
from __future__ import annotations

import re
from datetime import timedelta

from ...utils import iso, to_date
from ..dashboard_data import SQL_VIENTRES_ACTIVOS
from ..lactancia import estados_lactancia
from ..tareas import EDAD_ADULTA_DIAS, _es_reproductor, _estado_actual, datos_tareas
from .helpers import _fmt_es_co

# Listas de Tareas que el asistente sabe nombrar: clave -> (título, detalle).
LISTAS_TAREAS: dict[str, tuple[str, str]] = {
    "palpar": ("Vacas para palpar", "fecha_servicio"),
    "servir": ("Vacas para servir (inseminar o monta)", "dias_abiertos"),
    "celos": ("Vacas con celo esperado", "proximo_celo"),
    "secar": ("Vacas para secar", "motivo"),
    "partos": ("Partos próximos", "fep"),
    "novillas": ("Novillas listas para servir", "edad_dias"),
    "castrar": ("Terneros para castrar", "edad_dias"),
    "topizar": ("Terneros para topizar (descornar)", "edad_dias"),
    "marcar": ("Animales para marcar (hierro)", "edad_dias"),
    "vac_brucelosis": ("Terneras para vacuna de brucelosis", "edad_dias"),
    "vac_aftosa": ("Animales pendientes de vacuna de aftosa", "ultima"),
    "venta": ("Animales con peso de venta", "peso_kg"),
    "descarte": ("Vacas candidatas a descarte", "motivo"),
    "bajo_peso": ("Animales ganando poco peso", "gmd_g"),
}


# Preguntas que NO son del hato presente: animal por raza, edad en años,
# eventos históricos o con periodo, umbral de peso. Esas tienen su rama.
_RE_NO_HATO = re.compile(
    r"\bvend|\bmuer|\bmuri|\bcompr|\bnaci|\bnacid|\bdestet|\bpari[oe]|\bpartos?\b|\braza\b"
    r"|\b\d+\s*(?:a[nñ]os?|meses)\b|\bmas\s+de\b|\bmenos\s+de\b|\bpesan?\b"
    r"|\beste\s+(?:mes|a[nñ]o)\b|\besta\s+semana\b|\bpasad[oa]\b|\bultim[oa]s?\b"
    r"|\binsemin|\bservir\b|\bservicios?\b|\bmonta\b"
    r"|\bpalpac|\bpendientes?\b|\bsecado\b|\blactancia\b|\bdias\b|\bretiro\b|\btratamiento|\bmedicamento"
    r"|\bperdiendo\b|\bbajando\b|\batrasad|\bdebian\b|\bproxim|\bvan\s+a\s+parir\b|\bdonde\b|\bpotreros?\b"
    r"|\b(?:holstein|gyr|brahman|cebu|pardo|ayrshire|normando|simental|angus|charolais|nelore|guzerat|romosinuano)\b"
)
_RE_CONTEO = re.compile(r"\bcuant|\bhay\b|\btotal\b|\bnumero\b|\bque\b|\bcual(?:es)?\b|\blista")

# (patrón, claves de _categorias_hato, título). El orden importa: lo más
# específico primero ("terneros machos" antes que "machos").
_CATEGORIAS_PREGUNTA: list[tuple[str, list[str], str]] = [
    (r"\b(?:terneros?|crias?|becerros?)\s+machos?\b|\bmachos?\s+terneros?\b|\bterneritos?\b", ["terneros"], "Terneros machos (menores de 1 año)"),
    (r"\b(?:terneras?|crias?|becerras?)\s+hembras?\b|\bterneras?\b|\bbecerras?\b", ["terneras"], "Terneras (hembras menores de 1 año)"),
    (r"\bterneros?\b|\bcrias?\b|\bbecerros?\b", ["terneros", "terneras"], "Terneros y terneras (menores de 1 año)"),
    (r"\btoretes?\b|\bnovillos?\b|\bmachos?\s+(?:de\s+)?levante\b|\blevante\s+machos?\b|\bmachos?\s+de\s+ceba\b|\bcebas?\b",
     ["levante_m", "machos_adultos"], "Machos de levante y ceba (toretes, novillos)"),
    (r"\bnovillas?\b|\bvaquillas?\b|\bhembras?\s+de\s+(?:reemplazo|levante)\b|\blevante\s+hembras?\b",
     ["levante_h", "novillas"], "Novillas y hembras de levante (sin parto)"),
    (r"\btoros?\b|\breproductor(?:es)?\b|\bsementales?\b", ["toros"], "Toros reproductores"),
    (r"\bvacas?\s+secas?\b|\bsecas\b", ["vacas_secas"], "Vacas secas"),
    (r"\b(?:en\s+)?ordeno\b|\bordenando\b|\ben\s+produccion\b|\bdan\s+leche\b|\blecheras?\b|\bparidas?\b",
     ["vacas_ordeno"], "Vacas en ordeño (paridas)"),
    (r"\bvacas?\b", ["vacas_ordeno", "vacas_secas"], "Vacas (hembras que ya parieron)"),
    (r"\bmachos?\b", ["machos"], "Machos"),
    (r"\bhembras?\b", ["hembras"], "Hembras"),
]
_NOTA_CATEGORIAS = "Cría: menos de 1 año · levante: 1 a 2 años · toro: marcado como toro o de 3 años en adelante."


def _sexo(s) -> str:
    s = str(s or "").strip().lower()
    if s.startswith("h") or s.startswith("f"):
        return "h"
    if s.startswith("m"):
        return "m"
    return ""


class HatoQueryMixin:
    """Requiere self.db y self.hoy (ver QueryEngine)."""

    def _responder_hato(self, t: str) -> str | None:
        """Enrutador de preguntas sobre el hato presente (texto normalizado).
        Devuelve None si la pregunta no es de este tipo."""
        # Traslados entre potreros en un periodo ("movimientos de potrero este mes").
        if re.search(r"\btraslad|\bmovimientos?\b|\bmovieron\b|\bcambios?\s+de\s+potrero", t) and re.search(r"potrero|\btraslad", t):
            rango = self._rango_periodo(t) or (iso(self.hoy - timedelta(days=30)), iso(self.hoy), "en los últimos 30 días")
            return self._traslados_periodo(*rango)
        # Tareas asignadas al equipo: dependen de quién pregunta (cada rol ve
        # solo las suyas), y el asistente no sabe quién es; se remite a la pantalla.
        if re.search(r"\btareas?\b", t) and re.search(r"\basi[g]?nad|\bcomplet|\bequipo\b|\bhechas?\b|\boperario|\btrabajador", t):
            return ("📋 Las tareas asignadas al equipo (pendientes y completadas, con su foto) están en el "
                    "<b>Tablero → Tareas Asignadas al Equipo</b> y en la <b>Agenda</b>. Cada persona ve las que le "
                    "corresponden según su rol.\n<i>Si busca el trabajo con los animales, pregunte 'qué tareas hay'.</i>")
        if re.search(r"\bdestetad[oa]s\b", t) and re.search(r"\bcuant|\bhay\b|\bque\b|\bcuales\b", t):
            return self._destetados_activos(t)
        if re.search(r"\bsincroniz|\biatf\b|\bprotocolo", t):
            return self._lista_tareas("servir") + "\n<i>Son las vacas vacías que ya pasaron la espera posparto: candidatas para sincronizar (IATF).</i>"
        # Listas de Tareas: "qué vacas hay para palpar", "terneros para castrar".
        if re.search(r"\bpala?par\b|\bsin\s+palpa", t):
            return self._lista_tareas("palpar")
        if re.search(r"\bcastrar\b|\bcapar\b", t):
            return self._lista_tareas("castrar")
        if re.search(r"\btopizar\b|\bdescornar\b", t):
            return self._lista_tareas("topizar")
        if re.search(r"\bmarcar\b|\bherrar\b|\bsin\s+hierro\b", t):
            return self._lista_tareas("marcar")
        if re.search(r"\bvacun", t):
            if re.search(r"\bbrucel", t):
                return self._lista_tareas("vac_brucelosis")
            if re.search(r"\baftosa\b", t):
                return self._lista_tareas("vac_aftosa")
            return self._lista_tareas("vac_aftosa") + "\n\n" + self._lista_tareas("vac_brucelosis")
        if re.search(r"\b(?:para|a|hay\s+que|toca|debo|deben|debemos)\s+secar\b", t):
            return self._lista_tareas("secar")
        if re.search(r"\bdescart", t):
            return self._lista_tareas("descarte")
        if re.search(r"\b(?:para|por|listos?\s+para|de)\s+(?:vender|venta)\b|\bpeso\s+de\s+venta\b", t):
            return self._lista_tareas("venta")
        if re.search(r"\bcelos?\b", t) and re.search(r"\bque\b|\bcuales\b|\bcuant|\bhay\b|\bestan?\b|\besperad", t):
            return self._lista_tareas("celos")
        if re.search(r"\bnovillas?\b", t) and re.search(r"\bservir|\binsemin|\bentor|\blistas?\b", t):
            return self._lista_tareas("novillas")
        if re.search(r"\btareas?\b|\bque\s+(?:hay|toca)\s+(?:que\s+)?hacer\b|\bpendientes\s+(?:de|para)\s+hoy\b", t):
            return self._resumen_tareas()

        if _RE_NO_HATO.search(t) or not _RE_CONTEO.search(t):
            return None
        # Con un potrero mencionado, la rama de potreros da la composición.
        if re.search(r"\bpotreros?\b|\bcorral\b|\blote\b", t) or self._potrero_mencionado(t):
            return None

        # Estado reproductivo.
        if re.search(r"\bprenad|\bcargadas?\b|\bgestantes?\b|\bpre[nñ]ez\b", t):
            return self._vacas_estado_reproductivo("PRENADA")
        if re.search(r"\bvacias?\b|\babiertas?\b|\bhorras?\b", t):
            return self._vacas_estado_reproductivo("VACIA")
        if re.search(r"\bsin\s+diagnostico\b|\ben\s+espera\b", t):
            return self._vacas_estado_reproductivo("EN_ESPERA")

        if re.search(r"\bhato\b", t) and not re.search(r"\bvacas?\b|\btoros?\b|\bterner|\bnovill|\bmachos?\b|\bhembras?\b", t):
            return self._inventario_general()
        # "cuántos animales hay" es el resumen general (sección 8).
        if re.search(r"\banimales?\b|\bganado\b|\binventario\b", t):
            return None
        for patron, claves, titulo in _CATEGORIAS_PREGUNTA:
            if re.search(patron, t):
                return self._conteo_hato(claves, titulo, _NOTA_CATEGORIAS)
        return None

    # ------------------------------------------------------------------ #
    # Conteos por categoría
    # ------------------------------------------------------------------ #
    def _categorias_hato(self) -> dict[str, list[str]]:
        """Tags de los animales activos por categoría. Hembras y machos por
        sexo (igual que el Tablero); edades: cría < 1 año, levante 1-2 años."""
        estados_lac = estados_lactancia(self.db, self.hoy)
        partos = {r["vaca_id"] for r in self.db.query(
            "SELECT DISTINCT vaca_id FROM partos WHERE id_cria IS NULL OR id_cria != vaca_id")}
        cats: dict[str, list[str]] = {k: [] for k in (
            "hembras", "machos", "terneros", "terneras", "levante_h", "levante_m",
            "novillas", "vacas", "vacas_ordeno", "vacas_secas", "toros", "machos_adultos")}
        for a in self.db.query(
            "SELECT id_animal, tag, nombre, sexo, fecha_nacimiento, notas FROM animales WHERE estado = 'ACTIVO'"
        ):
            tag = a["tag"] or str(a["id_animal"])
            fn = to_date(a["fecha_nacimiento"])
            edad = (self.hoy - fn).days if fn else None
            sexo = _sexo(a["sexo"])
            if sexo == "h":
                cats["hembras"].append(tag)
                if edad is not None and edad < 365:
                    cats["terneras"].append(tag)
                elif a["id_animal"] in partos:
                    cats["vacas"].append(tag)
                    lac = estados_lac.get(a["id_animal"])
                    if lac and lac["estado"] in ("EN_ORDENO", "PAUSADA"):
                        cats["vacas_ordeno"].append(tag)
                    else:
                        cats["vacas_secas"].append(tag)
                elif edad is not None and edad < 730:
                    cats["levante_h"].append(tag)
                else:
                    cats["novillas"].append(tag)
            elif sexo == "m":
                cats["machos"].append(tag)
                if _es_reproductor(dict(a)) or (edad is not None and edad >= 1095):
                    cats["toros"].append(tag)
                elif edad is not None and edad < 365:
                    cats["terneros"].append(tag)
                elif edad is not None and edad < 730:
                    cats["levante_m"].append(tag)
                else:
                    cats["machos_adultos"].append(tag)
        return cats

    def _conteo_hato(self, claves: list[str], titulo: str, nota: str = "") -> str:
        cats = self._categorias_hato()
        tags = [t for k in claves for t in cats[k]]
        lineas = [f"🐄 <b>{titulo}: {_fmt_es_co(len(tags))}</b> (activos)"]
        if len(claves) > 1:
            nombres = {"terneros": "terneros", "terneras": "terneras", "levante_h": "hembras de levante (1-2 años)",
                       "levante_m": "machos de levante (1-2 años)", "novillas": "novillas (sin parto, +2 años)",
                       "machos_adultos": "machos +2 años no reproductores", "vacas_ordeno": "en ordeño",
                       "vacas_secas": "secas"}
            lineas.append(" · ".join(f"{len(cats[k])} {nombres.get(k, k)}" for k in claves))
        if tags and len(tags) <= 30:
            lineas.append(", ".join(tags))
        if nota:
            lineas.append(f"<i>{nota}</i>")
        return "\n".join(lineas)

    # ------------------------------------------------------------------ #
    # Estado reproductivo de las vacas
    # ------------------------------------------------------------------ #
    def _vientres_por_estado(self) -> dict[str, list[str]]:
        """Hembras adultas activas (con parto o de 15 meses en adelante) por
        estado reproductivo: preñada, vacía o servida sin diagnóstico."""
        out: dict[str, list[str]] = {"PRENADA": [], "VACIA": [], "EN_ESPERA": []}
        for r in self.db.query(SQL_VIENTRES_ACTIVOS):
            fn = to_date(r["fecha_nacimiento"])
            edad = (self.hoy - fn).days if fn else None
            if not r["n_partos"] and (edad is None or edad < EDAD_ADULTA_DIAS):
                continue
            estado = _estado_actual(r)
            clave = estado if estado in ("PRENADA", "EN_ESPERA") else "VACIA"
            out[clave].append(r["tag"] or str(r["id_animal"]))
        return out

    def _vacas_estado_reproductivo(self, estado: str) -> str:
        grupos = self._vientres_por_estado()
        titulos = {"PRENADA": "Vacas preñadas", "VACIA": "Vacas vacías (abiertas)",
                   "EN_ESPERA": "Vacas servidas sin diagnóstico"}
        tags = grupos[estado]
        lineas = [f"🐄 <b>{titulos[estado]}: {_fmt_es_co(len(tags))}</b>"]
        if tags and len(tags) <= 30:
            lineas.append(", ".join(tags))
        lineas.append(
            f"<i>Resumen: {len(grupos['PRENADA'])} preñadas · {len(grupos['VACIA'])} vacías · "
            f"{len(grupos['EN_ESPERA'])} servidas sin diagnóstico. Cuenta vacas y novillas activas "
            "según el último diagnóstico o servicio.</i>"
        )
        return "\n".join(lineas)

    def _dias_abiertos_animal(self, tag) -> str:
        aid = self.db.resolve_animal(tag)
        fila = next((r for r in self.db.query(SQL_VIENTRES_ACTIVOS) if r["id_animal"] == aid), None) if aid else None
        if fila is None:
            return f"No encontré una hembra activa con el arete {tag}."
        estado = _estado_actual(fila)
        if estado == "PRENADA":
            return f"La {fila['tag']} está preñada (diagnóstico del {fila['ult_diag_fecha']}), no tiene días abiertos."
        ult_parto = to_date(fila["ult_parto"])
        if not ult_parto:
            return f"La {fila['tag']} no tiene partos registrados."
        dias = (self.hoy - ult_parto).days
        extra = " Ya fue servida; falta el diagnóstico." if estado == "EN_ESPERA" else ""
        return f"La {fila['tag']} lleva <b>{dias} días abiertos</b> (último parto: {iso(ult_parto)}).{extra}"

    # ------------------------------------------------------------------ #
    # Listas de trabajo (pantalla Tareas)
    # ------------------------------------------------------------------ #
    def _lista_tareas(self, clave: str) -> str:
        titulo, campo = LISTAS_TAREAS[clave]
        lista = datos_tareas(self.db, self.hoy)[clave]
        if not lista:
            return f"✅ {titulo}: ninguno por ahora."
        lineas = [f"📋 <b>{titulo}: {len(lista)}</b>"]
        for x in lista[:20]:
            valor = x.get(campo)
            if campo == "edad_dias" and valor is not None:
                valor = f"{valor // 30} meses"
            elif campo == "peso_kg" and valor is not None:
                valor = f"{valor:.0f} kg"
            elif campo == "dias_abiertos" and valor is not None:
                valor = f"{valor} días abierta"
            elif campo == "gmd_g" and valor is not None:
                valor = f"{valor} g/día"
            extra = f" — {valor}" if valor not in (None, "") else ""
            lineas.append(f"• {x['tag']}{extra} · {x['potrero']}")
        if len(lista) > 20:
            lineas.append(f"<i>... y {len(lista) - 20} más (ver Tareas).</i>")
        return "\n".join(lineas)

    def _resumen_tareas(self) -> str:
        conteos = datos_tareas(self.db, self.hoy)["conteos"]
        nombres = dict((k, v[0]) for k, v in LISTAS_TAREAS.items())
        nombres["destetar"] = "Crías para destetar"
        filas = [f"• {nombres[k]}: {conteos[k]}" for k in nombres if conteos.get(k)]
        if not filas:
            return "✅ No hay tareas pendientes por ahora."
        return "📋 <b>Tareas pendientes:</b>\n" + "\n".join(filas) + "\n<i>Pregunte por una para ver la lista, ej. 'qué vacas hay para palpar'.</i>"

    # ------------------------------------------------------------------ #
    # Leche del hato
    # ------------------------------------------------------------------ #
    def _leche_hato(self, fecha: str | None = None) -> str:
        if fecha is None:
            fila = self.db.query_one("SELECT MAX(fecha) f FROM produccion_leche WHERE litros > 0")
            fecha = fila["f"] if fila else None
            if not fecha:
                return "No hay producción de leche registrada."
        dia = self.db.query_one(
            "SELECT SUM(litros) l, COUNT(*) n FROM produccion_leche WHERE fecha = ? AND litros > 0", (fecha,))
        if not dia or not dia["l"]:
            return f"No hay producción de leche registrada el {fecha}."
        desde = iso(to_date(fecha) - timedelta(days=6))
        sem = self.db.query_one(
            "SELECT SUM(litros) l, COUNT(DISTINCT fecha) d FROM produccion_leche "
            "WHERE fecha >= ? AND fecha <= ? AND litros > 0", (desde, fecha))
        texto = f"🥛 Leche del {fecha}: <b>{_fmt_es_co(int(round(dia['l'])))} litros</b>"
        if sem and sem["d"] and sem["d"] > 1:
            texto += f"\nPromedio de los últimos 7 días: {_fmt_es_co(int(round(sem['l'] / sem['d'])))} litros/día"
        return texto

    # ------------------------------------------------------------------ #
    # Destetes y traslados
    # ------------------------------------------------------------------ #
    def _destetados_activos(self, t: str) -> str:
        """Animales activos con destete registrado (opcionalmente por sexo)."""
        filas = self.db.query(
            "SELECT a.tag, a.sexo, MAX(d.fecha) fecha FROM destetes d "
            "JOIN animales a ON a.id_animal = d.animal_id WHERE a.estado = 'ACTIVO' GROUP BY a.id_animal"
        )
        quien = "Animales destetados"
        if re.search(r"\bhembras?\b|\bterneras?\b", t):
            filas, quien = [f for f in filas if _sexo(f["sexo"]) == "h"], "Terneras destetadas"
        elif re.search(r"\bmachos?\b", t):
            filas, quien = [f for f in filas if _sexo(f["sexo"]) == "m"], "Terneros machos destetados"
        lineas = [f"🐮 <b>{quien}: {len(filas)}</b> (activos con destete registrado)"]
        if filas and len(filas) <= 30:
            lineas.append(", ".join(f["tag"] for f in filas))
        return "\n".join(lineas)

    def _traslados_periodo(self, desde: str, hasta: str, etiqueta: str) -> str:
        filas = self.db.query(
            "SELECT t.fecha, a.tag, po.nombre origen, pd.nombre destino FROM traslados t "
            "JOIN animales a ON a.id_animal = t.animal_id "
            "LEFT JOIN potreros po ON po.id = t.potrero_origen "
            "LEFT JOIN potreros pd ON pd.id = t.potrero_destino "
            "WHERE t.fecha >= ? AND t.fecha <= ? ORDER BY t.fecha DESC, t.id DESC",
            (desde, hasta),
        )
        if not filas:
            return f"No hay traslados de potrero registrados {etiqueta}."
        grupos: dict[tuple, list[str]] = {}
        for f in filas:
            grupos.setdefault((f["fecha"], f["origen"] or "sin dato", f["destino"] or "sin dato"), []).append(f["tag"])
        lineas = [f"🚚 <b>Traslados de potrero {etiqueta}: {len(filas)} animales</b>"]
        for (fecha, origen, destino), tags in list(grupos.items())[:15]:
            lineas.append(f"• {fecha} — {origen} → {destino}: {len(tags)} ({', '.join(tags[:5])}{'…' if len(tags) > 5 else ''})")
        if len(grupos) > 15:
            lineas.append(f"<i>... y {len(grupos) - 15} movimientos más.</i>")
        return "\n".join(lineas)
