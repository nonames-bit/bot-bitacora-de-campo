"""Mixin de la ficha zootécnica completa (_historial): la vista más consultada del bot."""
from __future__ import annotations

from ...utils import iso, to_date
from ..growth_engine import gmd
from ..reproductive_engine import fecha_estimada_parto, fecha_palpacion, fecha_secado
from .helpers import formatear_edad_zootecnica


class HistorialQueryMixin:
    """Requiere self.db y self.hoy (ver QueryEngine)."""

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
        raza = animal["raza"] or "Sin especificar"
        sexo_raw = animal["sexo"] or ""
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

        # Registro de nacimiento como cría (excluyendo autorreferencias)
        p_nac = self.db.query_one(
            "SELECT * FROM partos WHERE id_cria = ? AND (vaca_id IS NULL OR vaca_id != ?) ORDER BY fecha DESC LIMIT 1",
            (aid, aid),
        )
        if not p_nac and animal["madre_id"] and animal["madre_id"] != aid:
            p_nac = self.db.query_one(
                "SELECT * FROM partos WHERE vaca_id = ? AND (id_cria = ? OR id_cria IS NULL) ORDER BY fecha DESC LIMIT 1",
                (animal["madre_id"], aid),
            )

        # Normalización e inferencia de sexo
        sexo_norm = sexo_raw.strip().lower()
        if not sexo_norm or sexo_norm in ("i", "indefinido", "indeterminado", "desconocido", "?"):
            if p_nac and p_nac["sexo_cria"]:
                sexo_norm = p_nac["sexo_cria"].strip().lower()

        es_macho = bool(sexo_norm.startswith("m") or sexo_norm in ("macho", "toro", "ternero", "novillo", "buey"))
        es_hembra = not es_macho

        # Historial de eventos (machos no tienen partos dados por ellos ni servicios de hembra)
        h = self.db.historial(tag_str)
        def _row_get(row, key, default=None):
            try:
                return row[key]
            except Exception:
                try:
                    return row.get(key, default)  # type: ignore
                except Exception:
                    return default
        partos = [] if es_macho else [p for p in h.get("partos", []) if p["vaca_id"] != _row_get(p, "id_cria")]
        servicios = [] if es_macho else h.get("servicios", [])
        celos = [] if es_macho else h.get("celos", [])
        tratamientos = h.get("tratamientos", [])
        pesajes = h.get("pesajes", [])
        fotos = h.get("fotos", [])

        # Cálculo de fecha de nacimiento y edad
        f_nac = to_date(animal["fecha_nacimiento"])
        if not f_nac and p_nac and p_nac["fecha"]:
            f_nac = to_date(p_nac["fecha"])

        # Si aún no hay f_nac pero tiene madre_id válida, inferir desde partos recientes de la madre (<15 meses)
        if not f_nac and animal["madre_id"] and animal["madre_id"] != aid:
            ult_p_madre = self.db.query_one(
                "SELECT fecha, peso_nacimiento FROM partos WHERE vaca_id = ? AND fecha IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                (animal["madre_id"],),
            )
            if ult_p_madre and ult_p_madre["fecha"]:
                d_madre = to_date(ult_p_madre["fecha"])
                if d_madre and (self.hoy - d_madre).days <= 450:
                    f_nac = d_madre
                    if not p_nac:
                        p_nac = ult_p_madre

        edad_dias = (self.hoy - f_nac).days if f_nac else None

        # Categoría etaria / zootécnica alineada fielmente a Software Ganadero (SG)
        # Estados típicos SG:
        # - Machos: <8m CRÍA MACHO / Ternero, 8-18m LEVANTE / Novillo, 18-30m TORETE / Torete, >30m TORO / Toro
        # - Hembras con partos:
        #   - da <= 305d: VACA PARIDA (o VACA PARIDA SERVIDA / SIN PALPAR si tiene servicio)
        #   - da > 305d: VACA SECA (o VACA ESCOTERA si tiene >1 parto sin servicio)
        # - Hembras sin partos:
        #   - <12m: CRÍA HEMBRA / Ternera
        #   - 12-18m: NOVILLA LEVANTE / Novilla
        #   - >=18m: NOVILLA VIENTRE / Novilla (o NOVILLA VIENTRE SERVIDA si tiene servicio)
        if es_macho:
            if edad_dias is not None:
                if edad_dias < 243:  # < 8 meses
                    tipo_animal = "Ternero"
                    estado_reprod = "CRÍA MACHO"
                elif edad_dias < 548:  # 8 a 18 meses
                    tipo_animal = "Novillo"
                    estado_reprod = "LEVANTE"
                elif edad_dias < 913:  # 18 a 30 meses
                    tipo_animal = "Torete"
                    estado_reprod = "TORETE"
                else:  # > 30 meses
                    tipo_animal = "Toro"
                    estado_reprod = "TORO"
            else:
                # Edad desconocida: evitar clasificar como Toro reproductor
                if (animal["madre_id"] and animal["madre_id"] != aid) or p_nac:
                    tipo_animal = "Ternero"
                    estado_reprod = "CRÍA MACHO"
                else:
                    tipo_animal = "Macho joven"
                    estado_reprod = "LEVANTE / EDAD POR CONFIRMAR"
        else:
            ult_parto = partos[-1] if partos else None
            ult_servicio = servicios[-1] if servicios else None

            if partos:
                tipo_animal = "Vaca"
                f_up = to_date(ult_parto["fecha"]) if ult_parto else None
                da = (self.hoy - f_up).days if f_up else 0
                f_us = to_date(ult_servicio["fecha"]) if ult_servicio else None
                serv_post_parto = bool(f_us and f_up and f_us >= f_up)

                if da > 305:
                    if len(partos) > 1 and not serv_post_parto:
                        estado_reprod = "VACA ESCOTERA"
                    elif serv_post_parto:
                        estado_reprod = "VACA SECA SERVIDA"
                    else:
                        estado_reprod = "VACA SECA"
                else:
                    # da <= 305 días (vaca parida en lactancia activa)
                    if serv_post_parto:
                        estado_reprod = "VACA PARIDA SERVIDA / SIN PALPAR"
                    else:
                        estado_reprod = "VACA PARIDA SIN PALPAR"
            elif edad_dias is not None:
                if edad_dias < 365:  # < 12 meses
                    tipo_animal = "Ternera"
                    estado_reprod = "CRÍA HEMBRA"
                elif edad_dias < 548:  # 12 a 18 meses
                    tipo_animal = "Novilla"
                    estado_reprod = "NOVILLA LEVANTE"
                else:  # >= 18 meses (edad apta para vientre)
                    tipo_animal = "Novilla"
                    if ult_servicio:
                        estado_reprod = "NOVILLA VIENTRE SERVIDA"
                    else:
                        estado_reprod = "NOVILLA VIENTRE"
            else:
                if (animal["madre_id"] and animal["madre_id"] != aid) or p_nac:
                    tipo_animal = "Ternera"
                    estado_reprod = "CRÍA HEMBRA"
                elif ult_servicio:
                    tipo_animal = "Novilla"
                    estado_reprod = "NOVILLA VIENTRE SERVIDA"
                else:
                    tipo_animal = "Novilla"
                    estado_reprod = "NOVILLA VIENTRE"

        bloques = []

        # Encabezado
        nom_txt = f" ({animal['nombre']})" if animal["nombre"] else ""
        header = [
            "📋 <b>FICHA ZOOTÉCNICA</b>",
            f"🐄 <b>{tipo_animal} {tag_str}{nom_txt}</b>",
            f"🏷️ <b>Raza:</b> {raza}",
            f"📍 <b>Potrero:</b> {potrero_nom}",
        ]
        if f_nac:
            edad_str = formatear_edad_zootecnica(f_nac, self.hoy)
            header.append(f"🎂 <b>Edad:</b> {edad_str}")
        header.append(f"● <b>Estado:</b> {estado}")
        if estado == "HISTORICO":
            header.append(
                "⚠️ <i>Histórico: no hace parte del hato activo. Se conserva solo por genealogía.</i>"
            )
        header.extend([
            f"🧬 <b>Reproductivo:</b> {estado_reprod}",
            "───────────────────",
        ])
        bloques.append("\n".join(header))

        # Sección Reproducción
        reprod = ["🍼 <b>REPRODUCCIÓN & PARTOS</b>"]
        if es_hembra:
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
        else:
            reprod.append("• partos: 0 registro(s).")
            reprod.append("• servicios: 0 registro(s).")

        # Datos de origen / nacimiento si el animal nació en la finca o tiene madre registrada
        madre_id = animal["madre_id"] or (p_nac["vaca_id"] if p_nac else None)
        madre_tag = None
        if madre_id and madre_id != aid:
            m_animal = self.db.get_animal(madre_id)
            if m_animal and m_animal["tag"] != tag_str:
                madre_tag = m_animal["tag"]

        if f_nac or madre_tag:
            origen_parts = []
            if f_nac:
                origen_parts.append(f"Fecha: {iso(f_nac)}")
            if madre_tag:
                origen_parts.append(f"Madre: {madre_tag}")
            if p_nac and p_nac["peso_nacimiento"]:
                origen_parts.append(f"Peso al nacer: {p_nac['peso_nacimiento']} kg")
            reprod.append(f"• Origen / Nacimiento: {', '.join(origen_parts)}")

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
