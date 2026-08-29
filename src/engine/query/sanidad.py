"""Mixin de consultas sanitarias: retiros de leche/carne por tratamiento."""
from __future__ import annotations

from ...utils import to_date


class SanidadQueryMixin:
    """Requiere self.db y self.hoy (ver QueryEngine)."""

    def _retiro_animal(self, tag) -> str:
        if not tag:
            return self._en_retiro()
        aid = self.db.resolve_animal(tag)
        if aid is None:
            return f"No se encontró el animal '{tag}'."
        animal = self.db.get_animal(aid)
        tag_str = animal["tag"] if animal else str(tag)
        nombre = f" ({animal['nombre']})" if animal and animal["nombre"] else ""

        tratamientos = self.db.query(
            "SELECT * FROM tratamientos WHERE animal_id = ? ORDER BY fecha DESC LIMIT 5", (aid,)
        )
        if not tratamientos:
            return f"✅ {tag_str}{nombre} no tiene tratamientos registrados. Está libre de retiro."

        hoy = self.hoy
        bloqueos = []
        for t in tratamientos:
            for tipo, fin in (
                ("leche", t["fecha_fin_retiro_leche"]),
                ("carne", t["fecha_fin_retiro_carne"]),
            ):
                if fin and to_date(fin) and to_date(t["fecha"]) <= hoy <= to_date(fin):
                    dias_rest = (to_date(fin) - hoy).days
                    prod = t["producto"] or "Fármaco"
                    bloqueos.append(f"⚠️ Retiro de {tipo} por {prod} hasta el {fin} (faltan {dias_rest} días)")

        if bloqueos:
            return f"💊 <b>Tratamiento en {tag_str}{nombre}</b>:\n" + "\n".join(bloqueos)
        return f"✅ {tag_str}{nombre} no tiene retiros activos actualmente. Está libre para consumo/ordeño."

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
