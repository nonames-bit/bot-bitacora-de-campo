"""Interfaz principal del bot: enrutamiento de mensajes y registro de eventos."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ..db.database import Database
from ..engine.growth_engine import gmd
from ..engine.health_engine import fecha_fin_retiro
from ..engine.query_engine import QueryEngine
from ..engine.reproductive_engine import (fecha_ecografia, fecha_estimada_parto,
                                          fecha_palpacion, fecha_secado,
                                          programar_inseminacion)
from ..parsers.event_parser import EventParser, ParsedEvent
from ..parsers.media_handler import (MediaError, extract_image_info,
                                     transcribe_audio)
from ..utils import add_days, iso, to_date


class Bot:
    """Procesa mensajes (texto, audio, imagen), guarda en SQLite y responde."""

    def __init__(self, db: Database, hoy: Optional[date] = None):
        self.db = db
        self.hoy = hoy or date.today()
        self.parser = EventParser(hoy=self.hoy)
        self.queries = QueryEngine(db, hoy=self.hoy)

    # ------------------------------------------------------------------ #
    # Entradas
    # ------------------------------------------------------------------ #
    def procesar_texto(self, texto: str, user_id: Optional[int] = None) -> str:
        resultado = self.parser.parse(texto)
        eventos = resultado if isinstance(resultado, list) else [resultado]

        # Agrupa partos GEMELAR de la misma vaca/fecha dentro de un mismo
        # mensaje (ej. "pario mellizos, la 47 tuvo cria macho y cria hembra"
        # -> el LLM puede emitir dos eventos 'parto' separados con
        # tipo_evento=GEMELAR): el primero fija el grupo, el segundo lo
        # referencia. Vive solo durante esta llamada (no cruza mensajes).
        grupo_gemelar: dict[tuple, int] = {}

        respuestas: list[str] = []
        for ev in eventos:
            if ev.tipo == "consulta":
                respuestas.append(self.queries.responder(ev.texto or texto))
            elif ev.tipo == "desconocido":
                if len(eventos) == 1:
                    return "No pude interpretar ese mensaje. Intente una nota como " \
                           "'pario la 47, ternero macho' o una pregunta."
            else:
                self._registrar(ev, user_id, grupo_gemelar)
                self._generar_alertas(ev)
                respuestas.append(self._confirmacion(ev))

        if not respuestas:
            return "No pude interpretar ese mensaje. Intente una nota como " \
                   "'pario la 47, ternero macho' o una pregunta."
        return "\n".join(respuestas)

    def procesar_audio(self, audio_path: str, user_id: Optional[int] = None) -> str:
        try:
            transcript = transcribe_audio(audio_path)
        except MediaError as e:
            return f"No se pudo transcribir el audio: {e}"
        return self.procesar_texto(transcript.texto, user_id=user_id)

    def procesar_imagen(self, image_path: str, caption: Optional[str] = None,
                        animal_tag: Optional[str] = None, user_id: Optional[int] = None) -> str:
        tag = animal_tag
        texto_evento = caption or ""
        info = None
        try:
            info = extract_image_info(image_path)
            if info.tags and not tag:
                tag = info.tags[0]
            if info.texto_detectado and not texto_evento:
                texto_evento = info.texto_detectado
        except MediaError:
            pass

        ocr_txt = info.ocr_text if info and info.ocr_text else None
        self.db.registrar_foto(
            ruta=image_path, animal_tag=tag, fecha=iso(self.hoy),
            caption=caption or (info.texto_detectado if info else None),
            user_id=user_id,
            ocr_text=ocr_txt,
        )

        if texto_evento:
            return self.procesar_texto(texto_evento)

        if info:
            partes = []
            if info.tags:
                partes.append("arete(s): " + ", ".join(info.tags))
            if info.frascos:
                partes.append("frasco(s): " + ", ".join(info.frascos))
            if partes:
                return "Foto recibida. " + "; ".join(partes) + "."
            return "Foto recibida, sin información relevante detectada."

        if tag:
            return f"📷 Foto recibida y asociada al animal {tag}."
        return "📷 Foto recibida y guardada."

    # ------------------------------------------------------------------ #
    # Registro de eventos en SQLite
    # ------------------------------------------------------------------ #
    def _registrar(self, ev: ParsedEvent, user_id: Optional[int] = None,
                   grupo_gemelar: Optional[dict] = None) -> None:
        d = ev.datos
        if ev.tipo == "parto":
            tipo_evento = d.get("tipo_evento", "PARTO")
            clave_grupo = (ev.animal_tag, ev.fecha)
            grupo_parto_id = grupo_gemelar.get(clave_grupo) if (grupo_gemelar and tipo_evento == "GEMELAR") else None
            nuevo_id = self.db.registrar_parto(
                vaca_tag=ev.animal_tag, fecha=ev.fecha,
                sexo_cria=d.get("sexo_cria"), estado_cria=d.get("estado_cria", "VIVO"),
                peso_nacimiento=d.get("peso_nacimiento"), id_cria_tag=d.get("id_cria"),
                registrado_por=user_id, tipo_evento=tipo_evento,
                grupo_parto_id=grupo_parto_id,
            )
            if grupo_gemelar is not None and tipo_evento == "GEMELAR" and clave_grupo not in grupo_gemelar and nuevo_id:
                grupo_gemelar[clave_grupo] = nuevo_id
        elif ev.tipo == "muerte":
            self.db.registrar_muerte(
                animal_tag=ev.animal_tag, fecha=ev.fecha,
                causa_presunta=d.get("causa_presunta"),
                registrado_por=user_id,
            )
        elif ev.tipo == "diagnostico_gestacion":
            self.db.registrar_diagnostico(
                vaca_tag=ev.animal_tag, fecha=ev.fecha,
                resultado=d.get("resultado", "PREÑADA"),
                dias_gestacion=d.get("dias_gestacion"),
                responsable=d.get("responsable"),
                registrado_por=user_id,
            )
        elif ev.tipo == "servicio":
            self.db.registrar_servicio(
                vaca_tag=ev.animal_tag, fecha=ev.fecha,
                tipo_servicio=d.get("tipo_servicio", "IA"),
                toro_pajilla=d.get("toro_pajilla"), raza_toro=d.get("raza_toro"),
                fep_calculada=fecha_estimada_parto(ev.fecha), estado="SERVIDA",
                registrado_por=user_id,
            )
        elif ev.tipo == "celo":
            self.db.registrar_celo(
                vaca_tag=ev.animal_tag, fecha=ev.fecha, am_pm=d.get("am_pm"),
                registrado_por=user_id,
            )
        elif ev.tipo == "tratamiento":
            dias = d.get("dias_retiro")
            leche = d.get("dias_retiro_leche") or 0
            carne = d.get("dias_retiro_carne", dias) or 0
            self.db.registrar_tratamiento(
                animal_tag=ev.animal_tag, fecha=ev.fecha,
                producto=d.get("producto"), dosis=d.get("dosis"), via=d.get("via"),
                dias_retiro_leche=leche, dias_retiro_carne=carne,
                fecha_fin_retiro_leche=fecha_fin_retiro(ev.fecha, leche) if leche else None,
                fecha_fin_retiro_carne=fecha_fin_retiro(ev.fecha, carne) if carne else None,
                registrado_por=user_id,
            )
        elif ev.tipo == "pesaje":
            gmd_calc = self._calcular_gmd(ev.animal_tag, ev.fecha, d.get("peso_kg"))
            self.db.registrar_pesaje(
                animal_tag=ev.animal_tag, fecha=ev.fecha, peso_kg=d.get("peso_kg"),
                gmd_calculada=gmd_calc, evento=d.get("evento"),
                registrado_por=user_id,
            )
        elif ev.tipo == "condicion_corporal":
            self.db.registrar_condicion_corporal(
                animal_tag=ev.animal_tag, fecha=ev.fecha, valor=d.get("valor"),
                registrado_por=user_id,
            )
        elif ev.tipo == "leche":
            self.db.registrar_leche(
                animal_tag=ev.animal_tag, fecha=ev.fecha, litros=d.get("litros"),
                registrado_por=user_id,
            )
        elif ev.tipo == "traslado":
            self.db.registrar_traslado(
                animal_tag=ev.animal_tag, fecha=ev.fecha, lote=d.get("lote"),
                potrero_origen=d.get("potrero_origen"),
                potrero_destino=d.get("potrero_destino"),
                registrado_por=user_id,
            )
        elif ev.tipo == "movimiento":
            notas = None
            if d.get("cantidad"):
                notas = f"{d['cantidad']} animales"
            self.db.registrar_movimiento(
                animal_tag=ev.animal_tag, fecha=ev.fecha,
                tipo_movimiento=d.get("tipo_movimiento"),
                procedencia_destino=d.get("procedencia_destino"), notas=notas,
                registrado_por=user_id,
            )
        elif ev.tipo == "pluviometria":
            self.db.registrar_pluviometria(
                mm_lluvia=d.get("mm_lluvia", 0.0), fecha=ev.fecha,
                estacion_o_sector=d.get("estacion_o_sector"),
                registrado_por=user_id,
            )
        elif ev.tipo == "aforo":
            self.db.registrar_aforo(
                potrero_id_o_nom=d.get("potrero") or 1,
                aforo_kg_m2=d.get("aforo_kg_m2", 0.0), fecha=ev.fecha,
                registrado_por=user_id,
            )

    def _calcular_gmd(self, tag, fecha, peso) -> Optional[float]:
        if not tag or peso is None:
            return None
        previos = self.db.ultimos_pesajes(tag, 1)
        if not previos:
            return None
        prev = previos[0]
        d1, d2 = to_date(prev["fecha"]), to_date(fecha)
        if d1 and d2 and (d2 - d1).days > 0 and prev["peso_kg"] is not None:
            return gmd(float(peso), float(prev["peso_kg"]), (d2 - d1).days)
        return None

    # ------------------------------------------------------------------ #
    # Alertas automáticas
    # ------------------------------------------------------------------ #
    def _generar_alertas(self, ev: ParsedEvent) -> None:
        tag = ev.animal_tag
        if ev.tipo == "servicio":
            fep = fecha_estimada_parto(ev.fecha)
            self.db.registrar_alerta(tag, "ECOGRAFIA", fecha_ecografia(ev.fecha),
                                     descripcion="Ecografía programada (día 35)")
            self.db.registrar_alerta(tag, "PALPACION", fecha_palpacion(ev.fecha),
                                     descripcion="Palpación rectal programada (día 60)")
            self.db.registrar_alerta(tag, "SECADO", fecha_secado(fep),
                                     descripcion="Secado programado (FEP - 60 días)")
            self.db.registrar_alerta(tag, "PARTO_ESPERADO", fep,
                                     descripcion="Fecha estimada de parto")
        elif ev.tipo == "diagnostico_gestacion":
            if (ev.datos.get("resultado") or "").upper() == "PREÑADA":
                dias = ev.datos.get("dias_gestacion")
                if dias and int(dias) > 0:
                    dias_rest = 283 - int(dias)
                    fep = add_days(ev.fecha, dias_rest)
                    self.db.registrar_alerta(tag, "SECADO", fecha_secado(fep),
                                             descripcion="Secado programado (FEP - 60 días)")
                    self.db.registrar_alerta(tag, "PARTO_ESPERADO", fep,
                                             descripcion="Fecha estimada de parto confirmada")
        elif ev.tipo == "celo":
            prog = programar_inseminacion(ev.fecha, ev.datos.get("am_pm"))
            if prog["fecha"]:
                self.db.registrar_alerta(
                    tag, "INSEMINACION_PROGRAMADA", prog["fecha"],
                    descripcion=f"Inseminación programada (regla AM-PM) en la {prog['franja']}")
        elif ev.tipo == "tratamiento":
            d = ev.datos
            dias = d.get("dias_retiro")
            leche = d.get("dias_retiro_leche") or 0
            carne = d.get("dias_retiro_carne", dias) or 0
            if leche:
                self.db.registrar_alerta(tag, "RETIRO_LECHE",
                                         fecha_fin_retiro(ev.fecha, leche),
                                         descripcion="Fin del retiro de leche")
            if carne:
                self.db.registrar_alerta(tag, "RETIRO_CARNE",
                                         fecha_fin_retiro(ev.fecha, carne),
                                         descripcion="Fin del retiro de carne")

    # ------------------------------------------------------------------ #
    # Respuestas
    # ------------------------------------------------------------------ #
    def _confirmacion(self, ev: ParsedEvent) -> str:
        d = ev.datos
        tag = ev.animal_tag or "lote"
        if ev.tipo == "parto":
            tipo_evento = d.get("tipo_evento", "PARTO")
            etiquetas = {
                "GEMELAR": "parto gemelar", "ABORTO": "aborto",
                "REABSORCION": "reabsorción embrionaria", "MOMIFICACION": "momificación fetal",
                "MACERACION": "maceración fetal", "MUERTE_FETAL": "muerte fetal",
            }
            if tipo_evento in etiquetas:
                return f"Registrado {etiquetas[tipo_evento]} de la {tag}."
            sexo = d.get("sexo_cria") or "?"
            return f"Registrado parto de la {tag} (cría {sexo.lower()})."
        if ev.tipo == "muerte":
            return f"Registrada muerte del animal {tag}."
        if ev.tipo == "diagnostico_gestacion":
            res = d.get("resultado", "PREÑADA")
            dias_str = f" ({d['dias_gestacion']} días)" if d.get("dias_gestacion") else ""
            return f"Registrado diagnóstico de gestación de la {tag}: {res}{dias_str}."
        if ev.tipo == "servicio":
            return f"Registrado servicio ({d.get('tipo_servicio', 'IA')}) de la {tag}."
        if ev.tipo == "celo":
            return f"Registrado celo de la {tag}."
        if ev.tipo == "tratamiento":
            return f"Registrado tratamiento de {tag}: {d.get('producto') or 'fármaco'}."
        if ev.tipo == "pesaje":
            return f"Registrado pesaje de la {tag}: {d.get('peso_kg')} kg."
        if ev.tipo == "condicion_corporal":
            return f"Registrada condición corporal de la {tag}: {d.get('valor')}."
        if ev.tipo == "leche":
            return f"Registrada producción de leche de la {tag}: {d.get('litros')} litros."
        if ev.tipo == "traslado":
            return f"Registrado traslado (lote {d.get('lote') or '?'})."
        if ev.tipo == "movimiento":
            return f"Registrado movimiento ({d.get('tipo_movimiento', '')})."
        if ev.tipo == "pluviometria":
            sector = f" en {d['estacion_o_sector']}" if d.get("estacion_o_sector") else ""
            return f"🌧️ Registrada lluvia: {d.get('mm_lluvia')} mm{sector} el {ev.fecha}."
        if ev.tipo == "aforo":
            pot = f" en potrero {d['potrero']}" if d.get("potrero") else ""
            return f"🌿 Registrado aforo de pasto: {d.get('aforo_kg_m2')} kg/m²{pot} el {ev.fecha}."
        return "Evento registrado."
