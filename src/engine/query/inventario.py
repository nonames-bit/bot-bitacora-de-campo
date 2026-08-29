"""Mixin de consultas de inventario general, por categoría, pesaje y fotos."""
from __future__ import annotations

from ...utils import to_date
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
