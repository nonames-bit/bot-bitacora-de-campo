"""Capa de acceso a datos SQLite para la bitácora de campo zootécnico."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Optional

from ..utils import iso, to_date
from .models import SCHEMA_SQL


class Database:
    """Envoltorio de sqlite3 con helpers de resolución tag → id y CRUD."""

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

    # ------------------------------------------------------------------ #
    # Ciclo de vida y utilidades de bajo nivel
    # ------------------------------------------------------------------ #
    def create_tables(self) -> "Database":
        self.conn.executescript(SCHEMA_SQL)
        # Migración idempotente para columnas añadidas
        try:
            cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(fotos)").fetchall()]
            if "ocr_text" not in cols:
                self.conn.execute("ALTER TABLE fotos ADD COLUMN ocr_text TEXT")
        except Exception:
            pass
        # Saneamiento idempotente de autorreferencias corruptas
        try:
            self.conn.execute("UPDATE animales SET madre_id = NULL WHERE madre_id = id_animal")
            self.conn.execute("UPDATE animales SET padre_id = NULL WHERE padre_id = id_animal")
            self.conn.execute("DELETE FROM partos WHERE vaca_id = id_cria AND vaca_id IS NOT NULL")
        except Exception:
            pass
        self.conn.commit()
        return self

    def close(self) -> None:
        self.conn.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchone()

    def insert(self, tabla: str, datos: dict) -> int:
        """Inserta una fila descartando claves None y devuelve el id generado."""
        datos = {k: v for k, v in datos.items() if v is not None}
        if not datos:
            raise ValueError("No hay datos para insertar")
        cols = ", ".join(datos.keys())
        marks = ", ".join("?" for _ in datos)
        cur = self.conn.execute(
            f"INSERT INTO {tabla} ({cols}) VALUES ({marks})", tuple(datos.values())
        )
        self.conn.commit()
        return cur.lastrowid

    def count(self, tabla: str) -> int:
        row = self.query_one(f"SELECT COUNT(*) AS n FROM {tabla}")
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------ #
    # Resolución de identificadores
    # ------------------------------------------------------------------ #
    def animal_id(self, tag) -> Optional[int]:
        if tag is None:
            return None
        t = str(tag).strip()
        if not t:
            return None
        row = self.query_one(
            "SELECT id_animal FROM animales WHERE tag = ? OR UPPER(tag) = UPPER(?) LIMIT 1", (t, t)
        )
        if row:
            return int(row["id_animal"])

        # Intentar coincidencia normalizada (sin guiones ni espacios)
        t_clean = t.upper().replace("-", "").replace(" ", "").replace(".", "")
        row = self.query_one(
            """
            SELECT id_animal FROM animales
            WHERE REPLACE(REPLACE(REPLACE(UPPER(tag), '-', ''), ' ', ''), '.', '') = ?
               OR UPPER(nombre) = UPPER(?)
            LIMIT 1
            """,
            (t_clean, t),
        )
        return int(row["id_animal"]) if row else None

    def resolve_animal(self, tag_or_id, crear: bool = False, **campos) -> Optional[int]:
        """Devuelve el id_animal a partir de un tag (o id ya resuelto)."""
        if isinstance(tag_or_id, int) and not isinstance(tag_or_id, bool):
            return tag_or_id
        tag = str(tag_or_id).strip() if tag_or_id is not None else ""
        if tag == "":
            return None
        aid = self.animal_id(tag)
        if aid is None and crear:
            datos = {"tag": tag, **campos}
            # Los animales creados sin estado explícito (ej. crías de partos
            # registrados por Telegram) se consideran ACTIVOS por defecto.
            if "estado" not in datos:
                datos["estado"] = "ACTIVO"
            aid = self.insert("animales", datos)
        return aid

    def get_animal(self, tag_or_id) -> Optional[sqlite3.Row]:
        aid = self.resolve_animal(tag_or_id)
        if aid is None:
            return None
        return self.query_one("SELECT * FROM animales WHERE id_animal = ?", (aid,))

    def potrero_id(self, codigo_o_nombre) -> Optional[int]:
        if codigo_o_nombre is None or codigo_o_nombre == "":
            return None
        v = str(codigo_o_nombre).strip()
        row = self.query_one(
            "SELECT id FROM potreros WHERE codigo = ? OR nombre = ?", (v, v)
        )
        return int(row["id"]) if row else None

    def resolve_potrero(self, codigo_o_nombre, crear: bool = False, **campos) -> Optional[int]:
        if isinstance(codigo_o_nombre, int) and not isinstance(codigo_o_nombre, bool):
            return codigo_o_nombre
        if codigo_o_nombre in (None, ""):
            return None
        pid = self.potrero_id(codigo_o_nombre)
        if pid is None and crear:
            pid = self.insert("potreros", {"nombre": str(codigo_o_nombre).strip(), **campos})
        return pid

    # ------------------------------------------------------------------ #
    # Registro de entidades (aceptan tags y resuelven a ids)
    # ------------------------------------------------------------------ #
    def registrar_animal(self, tag, nombre=None, sexo=None, raza=None,
                         fecha_nacimiento=None, madre_tag=None, padre_tag=None,
                         potrero=None, estado=None, notas=None) -> int:
        tag_str = str(tag).strip()
        existente = self.animal_id(tag_str)

        madre_id = self.resolve_animal(madre_tag) if madre_tag else None
        padre_id = self.resolve_animal(padre_tag) if padre_tag else None
        potrero_id = self.resolve_potrero(potrero) if potrero else None

        # Evitar autorreferencias (un animal no puede ser su propio padre ni madre)
        if madre_tag and str(madre_tag).strip().upper() == tag_str.upper():
            madre_id = None
        if padre_tag and str(padre_tag).strip().upper() == tag_str.upper():
            padre_id = None
        if existente is not None:
            if madre_id == existente:
                madre_id = None
            if padre_id == existente:
                padre_id = None

        campos = dict(
            nombre=nombre, sexo=sexo, raza=raza,
            fecha_nacimiento=iso(fecha_nacimiento), madre_id=madre_id,
            padre_id=padre_id, potrero_id=potrero_id, estado=estado, notas=notas,
        )
        if existente is not None:
            sets = ", ".join(f"{k} = ?" for k, v in campos.items() if v is not None)
            vals = tuple(v for v in campos.values() if v is not None)
            if vals:
                self.execute(
                    f"UPDATE animales SET {sets} WHERE id_animal = ?", vals + (existente,)
                )
            return existente
        return self.insert("animales", {"tag": tag_str, **campos})

    def registrar_potrero(self, nombre=None, codigo=None, area_has=None,
                          tipo_pasto=None, aforo_kg_m2=None, fecha_entrada=None,
                          fecha_salida=None, dias_reposo=None,
                          dias_ocupacion=None) -> int:
        return self.insert("potreros", dict(
            nombre=nombre, codigo=codigo, area_has=area_has, tipo_pasto=tipo_pasto,
            aforo_kg_m2=aforo_kg_m2, fecha_entrada=iso(fecha_entrada),
            fecha_salida=iso(fecha_salida), dias_reposo=dias_reposo,
            dias_ocupacion=dias_ocupacion,
        ))

    def registrar_parto(self, vaca_tag, fecha=None, sexo_cria=None,
                        estado_cria="VIVO", peso_nacimiento=None, id_cria_tag=None,
                        notas=None) -> int:
        tag_vaca_clean = str(vaca_tag).strip() if vaca_tag is not None else ""
        tag_cria_clean = str(id_cria_tag).strip() if id_cria_tag is not None else ""

        # Protección contra autorreferencias: si vaca y cría tienen el mismo tag
        if tag_cria_clean and tag_vaca_clean.upper() == tag_cria_clean.upper():
            id_cria = self.resolve_animal(tag_cria_clean, crear=True, sexo=sexo_cria, fecha_nacimiento=iso(fecha))
            if id_cria is not None:
                if sexo_cria:
                    self.execute("UPDATE animales SET sexo = COALESCE(sexo, ?) WHERE id_animal = ?", (sexo_cria, id_cria))
                if fecha:
                    self.execute("UPDATE animales SET fecha_nacimiento = COALESCE(fecha_nacimiento, ?) WHERE id_animal = ?", (iso(fecha), id_cria))
            return 0

        vaca_id = self.resolve_animal(vaca_tag, crear=True, sexo="Hembra")
        id_cria = self.resolve_animal(id_cria_tag, crear=True, sexo=sexo_cria, fecha_nacimiento=iso(fecha)) if id_cria_tag else None

        if id_cria is not None and vaca_id is not None and id_cria == vaca_id:
            return 0

        if id_cria is not None:
            if vaca_id is not None and id_cria != vaca_id:
                self.execute(
                    "UPDATE animales SET madre_id = COALESCE(madre_id, ?) WHERE id_animal = ? AND (madre_id IS NULL OR madre_id != ?)", (vaca_id, id_cria, id_cria)
                )
            if sexo_cria:
                self.execute(
                    "UPDATE animales SET sexo = COALESCE(sexo, ?) WHERE id_animal = ?", (sexo_cria, id_cria)
                )
            if fecha:
                self.execute(
                    "UPDATE animales SET fecha_nacimiento = COALESCE(fecha_nacimiento, ?) WHERE id_animal = ?", (iso(fecha), id_cria)
                )
        return self.insert("partos", dict(
            vaca_id=vaca_id, fecha=iso(fecha), sexo_cria=sexo_cria,
            estado_cria=estado_cria, peso_nacimiento=peso_nacimiento,
            id_cria=id_cria, notas=notas,
        ))

    def registrar_muerte(self, animal_tag, fecha=None, causa_presunta=None,
                         notas=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        return self.insert("muertes", dict(
            animal_id=animal_id, fecha=iso(fecha), causa_presunta=causa_presunta,
            notas=notas,
        ))

    def registrar_servicio(self, vaca_tag, fecha=None, tipo_servicio=None,
                           toro_pajilla=None, raza_toro=None, inseminador=None,
                           fep_calculada=None, estado=None) -> int:
        vaca_id = self.resolve_animal(vaca_tag, crear=True, sexo="Hembra")
        return self.insert("servicios", dict(
            vaca_id=vaca_id, fecha=iso(fecha), tipo_servicio=tipo_servicio,
            toro_pajilla=toro_pajilla, raza_toro=raza_toro, inseminador=inseminador,
            fep_calculada=iso(fep_calculada), estado=estado,
        ))

    def registrar_celo(self, vaca_tag, fecha=None, am_pm=None, notas=None) -> int:
        vaca_id = self.resolve_animal(vaca_tag, crear=True, sexo="Hembra")
        return self.insert("celos", dict(
            vaca_id=vaca_id, fecha=iso(fecha), am_pm=am_pm, notas=notas,
        ))

    def registrar_tratamiento(self, animal_tag, fecha=None, producto=None,
                              principio_activo=None, dosis=None, via=None,
                              dias_retiro_leche=0, dias_retiro_carne=0,
                              fecha_fin_retiro_leche=None, fecha_fin_retiro_carne=None,
                              diagnostico=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        return self.insert("tratamientos", dict(
            animal_id=animal_id, fecha=iso(fecha), producto=producto,
            principio_activo=principio_activo, dosis=dosis, via=via,
            dias_retiro_leche=dias_retiro_leche, dias_retiro_carne=dias_retiro_carne,
            fecha_fin_retiro_leche=iso(fecha_fin_retiro_leche),
            fecha_fin_retiro_carne=iso(fecha_fin_retiro_carne),
            diagnostico=diagnostico,
        ))

    def registrar_traslado(self, animal_tag, fecha=None, lote=None,
                           potrero_origen=None, potrero_destino=None,
                           motivo=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        origen = self.resolve_potrero(potrero_origen) if potrero_origen else None
        destino = self.resolve_potrero(potrero_destino) if potrero_destino else None
        return self.insert("traslados", dict(
            animal_id=animal_id, lote=lote, fecha=iso(fecha),
            potrero_origen=origen, potrero_destino=destino, motivo=motivo,
        ))

    def registrar_pesaje(self, animal_tag, fecha=None, peso_kg=None,
                         gmd_calculada=None, evento=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        return self.insert("pesajes", dict(
            animal_id=animal_id, fecha=iso(fecha), peso_kg=peso_kg,
            gmd_calculada=gmd_calculada, evento=evento,
        ))

    def registrar_movimiento(self, animal_tag, fecha=None, tipo_movimiento=None,
                             procedencia_destino=None, precio=None, notas=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        return self.insert("movimientos", dict(
            animal_id=animal_id, fecha=iso(fecha), tipo_movimiento=tipo_movimiento,
            procedencia_destino=procedencia_destino, precio=precio, notas=notas,
        ))

    def registrar_alerta(self, animal_tag, tipo_alerta, fecha_programada=None,
                         estado="PENDIENTE", descripcion=None) -> int:
        animal_id = self.resolve_animal(animal_tag) if animal_tag else None
        return self.insert("alertas", dict(
            animal_id=animal_id, tipo_alerta=tipo_alerta,
            fecha_programada=iso(fecha_programada), estado=estado,
            descripcion=descripcion,
        ))

    def registrar_foto(self, ruta: str, animal_tag=None, fecha=None,
                       caption=None, user_id=None, notas=None, ocr_text=None) -> int:
        tag_str = str(animal_tag).strip() if animal_tag else None
        animal_id = self.resolve_animal(tag_str, crear=True) if tag_str else None
        fecha_iso = iso(fecha) or date.today().isoformat()
        return self.insert("fotos", dict(
            animal_id=animal_id, tag=tag_str, fecha=fecha_iso,
            ruta=ruta, caption=caption, user_id=user_id, notas=notas,
            ocr_text=ocr_text,
        ))

    def fotos_de(self, animal_tag_or_id, limit: int = 5) -> list[sqlite3.Row]:
        aid = self.resolve_animal(animal_tag_or_id)
        tag_str = str(animal_tag_or_id).strip()
        if aid is not None:
            return self.query(
                "SELECT * FROM fotos WHERE animal_id = ? OR tag = ? ORDER BY id DESC LIMIT ?",
                (aid, tag_str, limit),
            )
        return self.query(
            "SELECT * FROM fotos WHERE tag = ? ORDER BY id DESC LIMIT ?",
            (tag_str, limit),
        )

    def ultimas_fotos(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM fotos ORDER BY id DESC LIMIT ?", (limit,))

    # ------------------------------------------------------------------ #
    # Consultas frecuentes
    # ------------------------------------------------------------------ #
    def ultimo_parto(self, animal_tag_or_id) -> Optional[sqlite3.Row]:
        aid = self.resolve_animal(animal_tag_or_id)
        if aid is None:
            return None
        animal = self.get_animal(aid)
        if animal and (animal["sexo"] or "").strip().lower().startswith("m"):
            # Machos nunca tienen partos propios
            return None
        return self.query_one(
            "SELECT * FROM partos WHERE vaca_id = ? AND (id_cria IS NULL OR id_cria != ?) ORDER BY fecha DESC LIMIT 1", (aid, aid)
        )

    def ultimo_servicio(self, animal_tag_or_id) -> Optional[sqlite3.Row]:
        aid = self.resolve_animal(animal_tag_or_id)
        if aid is None:
            return None
        animal = self.get_animal(aid)
        if animal and (animal["sexo"] or "").strip().lower().startswith("m"):
            # Machos nunca tienen servicios reproductivos de hembra
            return None
        return self.query_one(
            "SELECT * FROM servicios WHERE vaca_id = ? ORDER BY fecha DESC LIMIT 1", (aid,)
        )

    def ultimos_pesajes(self, animal_tag_or_id, n: int = 2) -> list[sqlite3.Row]:
        aid = self.resolve_animal(animal_tag_or_id)
        if aid is None:
            return []
        return self.query(
            "SELECT * FROM pesajes WHERE animal_id = ? ORDER BY fecha DESC LIMIT ?", (aid, n)
        )

    def historial(self, animal_tag_or_id) -> dict[str, list[sqlite3.Row]]:
        aid = self.resolve_animal(animal_tag_or_id)
        if aid is None:
            return {}
        animal = self.get_animal(aid)
        tag = animal["tag"] if animal else str(aid)
        es_macho = bool(animal and (animal["sexo"] or "").strip().lower().startswith("m"))

        partos_propios = [] if es_macho else self.query(
            "SELECT * FROM partos WHERE vaca_id = ? AND (id_cria IS NULL OR id_cria != ?) ORDER BY fecha", (aid, aid)
        )
        servicios = [] if es_macho else self.query(
            "SELECT * FROM servicios WHERE vaca_id = ? ORDER BY fecha", (aid,)
        )
        celos = [] if es_macho else self.query(
            "SELECT * FROM celos WHERE vaca_id = ? ORDER BY fecha", (aid,)
        )
        return {
            "partos": partos_propios,
            "nacimiento": self.query("SELECT * FROM partos WHERE id_cria = ? ORDER BY fecha", (aid,)),
            "servicios": servicios,
            "celos": celos,
            "muertes": self.query("SELECT * FROM muertes WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "tratamientos": self.query("SELECT * FROM tratamientos WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "traslados": self.query("SELECT * FROM traslados WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "pesajes": self.query("SELECT * FROM pesajes WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "movimientos": self.query("SELECT * FROM movimientos WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "fotos": self.query("SELECT * FROM fotos WHERE animal_id = ? OR tag = ? ORDER BY fecha", (aid, tag)),
        }

    # ------------------------------------------------------------------ #
    # Genealogía y consanguinidad (skill ``@trazabilidad-ganadera``)
    # ------------------------------------------------------------------ #
    def _ancestros(self, animal_id: Optional[int], generaciones: int = 3) -> set[int]:
        """IDs de ancestros (madre/padre) hasta ``generaciones`` niveles."""
        vistos: set[int] = set()
        if animal_id is None:
            return vistos
        frontera = {animal_id}
        for _ in range(generaciones):
            nuevos: set[int] = set()
            for aid in frontera:
                row = self.query_one(
                    "SELECT madre_id, padre_id FROM animales WHERE id_animal = ?", (aid,)
                )
                if row is None:
                    continue
                for pid in (row["madre_id"], row["padre_id"]):
                    if pid is not None and pid != aid and pid not in vistos:
                        vistos.add(pid)
                        nuevos.add(pid)
            frontera = nuevos
        return vistos

    def parientes_3_generaciones(self, animal_tag_or_id) -> set[int]:
        """Devuelve los ancestros del animal en 3 generaciones (sin incluirlo)."""
        aid = self.resolve_animal(animal_tag_or_id)
        return self._ancestros(aid, 3)

    def verificar_consanguinidad(self, animal_id_hembra, toro_id) -> bool:
        """True si hembra y toro comparten ancestro en 3 generaciones (cruzamiento
        consanguíneo) o si uno es ancestro directo del otro."""
        ha = self.resolve_animal(animal_id_hembra)
        ta = self.resolve_animal(toro_id)
        if ha is None or ta is None:
            return False
        ancestros_h = self._ancestros(ha, 3)
        ancestros_t = self._ancestros(ta, 3)
        return bool(ancestros_h & ancestros_t) or ta in ancestros_h or ha in ancestros_t
