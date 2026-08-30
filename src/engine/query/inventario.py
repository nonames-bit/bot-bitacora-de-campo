"""Mixin de consultas de inventario general, por categoría, pesaje y fotos."""
from __future__ import annotations

from ...utils import add_days, iso, to_date
from ..growth_engine import gmd
from .helpers import _fmt_es_co, calcular_brackets_inventario_sg, generar_resumen_inventario_sg


class InventarioQueryMixin:
    """Requiere self.db y self.hoy (ver QueryEngine)."""

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

    def _inventario_general(self) -> str:
        total = self.db.query_one("SELECT COUNT(*) as n FROM animales WHERE estado='ACTIVO'")
        n_total = int(total["n"]) if total else 0
        if n_total == 0:
            return "📊 Inventario: 0 animales activos en la finca."

        tabla_sg = generar_resumen_inventario_sg(self.db, self.hoy)
        datos = calcular_brackets_inventario_sg(self.db, self.hoy)
        n_hembras = datos["total_hembras"]
        n_machos = datos["total_machos"]
        terneros = datos["terneros_menor_12m"]

        detalle = f"🐄 Total en finca: {_fmt_es_co(n_total)} animales"
        partes = []
        if n_hembras:
            partes.append(f"{n_hembras} vacas")
        if n_machos:
            partes.append(f"{n_machos} toros")
        if partes:
            detalle += f" ({', '.join(partes)})"
        if terneros:
            detalle += f" — {terneros} terneros <12m incluidos"
        detalle += "."

        return f"{tabla_sg}\n{detalle}"

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
                has_parto = self.db.query_one("SELECT 1 FROM partos WHERE vaca_id=? AND (id_cria IS NULL OR id_cria != ?) LIMIT 1", (aid, aid))
                if not has_parto:
                    count += 1
            return f"🐄 Total novillas (hembras sin parto): {count}."
        if cat in ("terneros", "ternero", "terneras"):
            rows = self.db.query("SELECT id_animal, fecha_nacimiento, madre_id FROM animales WHERE estado='ACTIVO'")
            count = 0
            for r in rows:
                fn = to_date(r["fecha_nacimiento"])
                if not fn:
                    p = self.db.query_one(
                        "SELECT fecha FROM partos WHERE id_cria = ? AND (vaca_id IS NULL OR vaca_id != ?) ORDER BY fecha DESC LIMIT 1",
                        (r["id_animal"], r["id_animal"]),
                    )
                    if p and p["fecha"]:
                        fn = to_date(p["fecha"])
                    elif r["madre_id"] and r["madre_id"] != r["id_animal"]:
                        p_m = self.db.query_one(
                            "SELECT fecha FROM partos WHERE vaca_id = ? ORDER BY fecha DESC LIMIT 1",
                            (r["madre_id"],),
                        )
                        if p_m and p_m["fecha"]:
                            fn = to_date(p_m["fecha"])
                if fn and (self.hoy - fn).days < 365:
                    count += 1
            # Fallback si no hay fecha_nacimiento: contar crías con id_cria no nulo en partos de animales activos
            if count == 0:
                row = self.db.query_one("SELECT COUNT(DISTINCT a.id_animal) as n FROM animales a JOIN partos p ON p.id_cria = a.id_animal WHERE a.estado='ACTIVO' AND (p.vaca_id IS NULL OR p.vaca_id != p.id_cria)")
                count = int(row["n"]) if row and row["n"] else 0
            return f"🐄 Total terneros (<12 meses): {count}."
        return self._inventario_general()

    def _inventario_por_edad(self, anios: int, sexo: str | None = None) -> str:
        """Cuenta animales activos cuya edad en años cumplidos coincide con el
        valor pedido (ej. 'cuántos animales hay de 2 años' -> 2 <= edad < 3)."""
        rows = self.db.query(
            "SELECT id_animal, tag, sexo, fecha_nacimiento, madre_id FROM animales WHERE estado='ACTIVO'"
        )
        coincidencias = []
        for r in rows:
            fn = to_date(r["fecha_nacimiento"])
            if not fn:
                p_m = None
                if r["madre_id"]:
                    p_m = self.db.query_one(
                        "SELECT fecha FROM partos WHERE vaca_id = ? AND fecha IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                        (r["madre_id"],),
                    )
                if p_m and p_m["fecha"]:
                    fn = to_date(p_m["fecha"])
            if not fn:
                continue
            edad_anios = (self.hoy - fn).days // 365
            if edad_anios != anios:
                continue
            s = (r["sexo"] or "").strip().lower()
            if sexo == "hembra" and not (s.startswith("h") or s in ("vaca", "novilla", "ternera")):
                continue
            if sexo == "macho" and not (s.startswith("m") or s in ("toro", "novillo", "ternero")):
                continue
            coincidencias.append(r["tag"] or str(r["id_animal"]))

        etiqueta = {"hembra": "vacas/hembras", "macho": "toros/machos"}.get(sexo, "animales")
        n = len(coincidencias)
        if n == 0:
            return f"No hay {etiqueta} activos de {anios} años."
        muestra = ", ".join(coincidencias[:10])
        if n > 10:
            muestra += f" y {n - 10} más"
        return f"🎂 {etiqueta.capitalize()} de {anios} años: <b>{n}</b> ({muestra})"

    def _conteo_por_estado(self, estado: str, sexo: str | None = None) -> str:
        """Cuenta animales (de forma histórica, sin filtrar por ACTIVO) en un
        estado puntual como VENDIDO, MUERTO o HISTORICO."""
        estado_norm = estado.strip().upper()
        sql = "SELECT COUNT(*) as n FROM animales WHERE UPPER(estado) = ?"
        params: list = [estado_norm]
        if sexo == "hembra":
            sql += " AND UPPER(sexo) LIKE 'H%'"
        elif sexo == "macho":
            sql += " AND UPPER(sexo) LIKE 'M%'"
        row = self.db.query_one(sql, tuple(params))
        n = int(row["n"]) if row else 0
        etiquetas_m = {"VENDIDO": "vendidos", "MUERTO": "muertos", "HISTORICO": "históricos/dados de baja"}
        etiquetas_f = {"VENDIDO": "vendidas", "MUERTO": "muertas", "HISTORICO": "históricas/dadas de baja"}
        if sexo == "hembra":
            sujeto, etiqueta = "Vacas", etiquetas_f.get(estado_norm, estado_norm.lower())
        elif sexo == "macho":
            sujeto, etiqueta = "Toros", etiquetas_m.get(estado_norm, estado_norm.lower())
        else:
            sujeto, etiqueta = "Animales", etiquetas_m.get(estado_norm, estado_norm.lower())
        emoji = {"VENDIDO": "💰", "MUERTO": "⚰️"}.get(estado_norm, "📊")
        return f"{emoji} {sujeto} {etiqueta}: <b>{_fmt_es_co(n)}</b>."

    def _movimientos_periodo(self, tipo_movimiento: str, dias: int) -> str:
        """Cuenta movimientos (VENTA/COMPRA/SALIDA/ENTRADA) registrados por el
        bot en los últimos N días. Solo cubre movimientos dictados al bot
        (tienen fecha real); el histórico importado de SG solo marca
        estado VENDIDO/MUERTO sin fecha, así que no se puede acotar por
        periodo — para el total histórico sin fecha use _conteo_por_estado."""
        desde = iso(add_days(self.hoy, -dias))
        filas = self.db.query(
            "SELECT m.*, a.tag FROM movimientos m JOIN animales a ON a.id_animal = m.animal_id "
            "WHERE UPPER(m.tipo_movimiento) = ? AND m.fecha >= ? ORDER BY m.fecha DESC",
            (tipo_movimiento.upper(), desde),
        )
        etiquetas = {"VENTA": "vendidos", "COMPRA": "comprados", "SALIDA": "de salida", "ENTRADA": "de entrada"}
        etiqueta = etiquetas.get(tipo_movimiento.upper(), tipo_movimiento.lower())
        if not filas:
            return f"No hay animales {etiqueta} registrados en los últimos {dias} días (según movimientos dictados al bot)."
        lineas = [f"💰 <b>Animales {etiqueta} en los últimos {dias} días ({len(filas)}):</b>"]
        for f in filas[:15]:
            precio_str = f" · ${_fmt_es_co(f['precio'])}" if f["precio"] else ""
            lineas.append(f"• {f['fecha']} — {f['tag']}{precio_str}")
        if len(filas) > 15:
            lineas.append(f"<i>... y {len(filas) - 15} más.</i>")
        return "\n".join(lineas)

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
