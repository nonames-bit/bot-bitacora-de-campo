"""Capa de acceso a datos SQLite para la bitácora de campo zootécnico."""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from typing import Optional

from ..utils import add_days, iso
from .models import SCHEMA_SQL


class Database:
    """Envoltorio de sqlite3 con helpers de resolución tag → id y CRUD."""

    # Tablas de eventos elegibles para el registro de auditoría y el
    # comando /deshacer (excluye animales/potreros/alertas/fotos, que no
    # son "eventos de campo" puntuales en el mismo sentido).
    TABLAS_EVENTOS = (
        "partos", "muertes", "servicios", "celos", "tratamientos",
        "traslados", "pesajes", "movimientos", "condicion_corporal",
    )

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
        # Columnas de auditoría (quién y cuándo registró cada evento) para
        # poder listar y deshacer registros equivocados (comando /deshacer).
        # Las tablas creadas antes de esta migración no tenían estas columnas.
        try:
            for tabla in self.TABLAS_EVENTOS:
                cols = [r["name"] for r in self.conn.execute(f"PRAGMA table_info({tabla})").fetchall()]
                if "creado_en" not in cols:
                    self.conn.execute(f"ALTER TABLE {tabla} ADD COLUMN creado_en TEXT")
                if "registrado_por" not in cols:
                    self.conn.execute(f"ALTER TABLE {tabla} ADD COLUMN registrado_por INTEGER")
        except Exception:
            pass
        # Saneamiento idempotente de autorreferencias corruptas
        try:
            self.conn.execute("UPDATE animales SET madre_id = NULL WHERE madre_id = id_animal")
            self.conn.execute("UPDATE animales SET padre_id = NULL WHERE padre_id = id_animal")
            self.conn.execute("DELETE FROM partos WHERE vaca_id = id_cria AND vaca_id IS NOT NULL")
            self.vincular_fotos_huerfanas()
            self.marcar_historicos_sg()
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
                        notas=None, registrado_por=None) -> int:
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
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def registrar_muerte(self, animal_tag, fecha=None, causa_presunta=None,
                         notas=None, registrado_por=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        return self.insert("muertes", dict(
            animal_id=animal_id, fecha=iso(fecha), causa_presunta=causa_presunta,
            notas=notas,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def _ahora(self) -> str:
        """Marca de tiempo de inserción (para /ultimos y /deshacer), distinta
        de ``fecha`` que es la fecha del evento de campo reportada por el
        usuario (pueden ser días distintos: se reporta hoy algo de ayer)."""
        return datetime.now().isoformat(timespec="seconds")

    def _id_si_ya_existe(self, tabla: str, condiciones: dict) -> Optional[int]:
        """Busca una fila que coincida exactamente en las columnas dadas (usa
        IS para que los None comparen correctamente contra NULL) y devuelve
        su id, o None si no existe. Usado por los registrar_* de eventos en
        vivo para que un reintento/doble envío no duplique la fila."""
        where = " AND ".join(f"{k} IS ?" for k in condiciones)
        fila = self.query_one(f"SELECT id FROM {tabla} WHERE {where}", tuple(condiciones.values()))
        return fila["id"] if fila else None

    def registrar_servicio(self, vaca_tag, fecha=None, tipo_servicio=None,
                           toro_pajilla=None, raza_toro=None, inseminador=None,
                           fep_calculada=None, estado=None, registrado_por=None) -> int:
        vaca_id = self.resolve_animal(vaca_tag, crear=True, sexo="Hembra")
        f = iso(fecha)
        # Idempotente por (vaca, fecha, tipo, toro/pajilla): dos servicios
        # reales el mismo día con distinto toro sí deben quedar ambos.
        existente = self._id_si_ya_existe("servicios", {
            "vaca_id": vaca_id, "fecha": f, "tipo_servicio": tipo_servicio, "toro_pajilla": toro_pajilla,
        })
        if existente:
            return existente
        return self.insert("servicios", dict(
            vaca_id=vaca_id, fecha=f, tipo_servicio=tipo_servicio,
            toro_pajilla=toro_pajilla, raza_toro=raza_toro, inseminador=inseminador,
            fep_calculada=iso(fep_calculada), estado=estado,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def registrar_celo(self, vaca_tag, fecha=None, am_pm=None, notas=None, registrado_por=None) -> int:
        vaca_id = self.resolve_animal(vaca_tag, crear=True, sexo="Hembra")
        f = iso(fecha)
        existente = self._id_si_ya_existe("celos", {"vaca_id": vaca_id, "fecha": f, "am_pm": am_pm})
        if existente:
            return existente
        return self.insert("celos", dict(
            vaca_id=vaca_id, fecha=f, am_pm=am_pm, notas=notas,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def registrar_tratamiento(self, animal_tag, fecha=None, producto=None,
                              principio_activo=None, dosis=None, via=None,
                              dias_retiro_leche=0, dias_retiro_carne=0,
                              fecha_fin_retiro_leche=None, fecha_fin_retiro_carne=None,
                              diagnostico=None, registrado_por=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        f_dosis = iso(fecha) or date.today().isoformat()
        fin_leche = iso(fecha_fin_retiro_leche)
        if not fin_leche and dias_retiro_leche and int(dias_retiro_leche) > 0:
            fin_leche = iso(add_days(f_dosis, int(dias_retiro_leche)))
        fin_carne = iso(fecha_fin_retiro_carne)
        if not fin_carne and dias_retiro_carne and int(dias_retiro_carne) > 0:
            fin_carne = iso(add_days(f_dosis, int(dias_retiro_carne)))

        # Idempotente por (animal, fecha, producto, dosis, via): dos
        # tratamientos reales el mismo día con distinta dosis/vía sí quedan.
        existente = self._id_si_ya_existe("tratamientos", {
            "animal_id": animal_id, "fecha": f_dosis, "producto": producto, "dosis": dosis, "via": via,
        })
        if existente:
            return existente
        return self.insert("tratamientos", dict(
            animal_id=animal_id, fecha=f_dosis, producto=producto,
            principio_activo=principio_activo, dosis=dosis, via=via,
            dias_retiro_leche=dias_retiro_leche, dias_retiro_carne=dias_retiro_carne,
            fecha_fin_retiro_leche=fin_leche,
            fecha_fin_retiro_carne=fin_carne,
            diagnostico=diagnostico,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def registrar_traslado(self, animal_tag, fecha=None, lote=None,
                           potrero_origen=None, potrero_destino=None,
                           motivo=None, registrado_por=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        origen = self.resolve_potrero(potrero_origen) if potrero_origen else None
        destino = self.resolve_potrero(potrero_destino) if potrero_destino else None
        f = iso(fecha)
        existente = self._id_si_ya_existe("traslados", {
            "animal_id": animal_id, "fecha": f, "potrero_destino": destino,
        })
        if existente:
            return existente
        return self.insert("traslados", dict(
            animal_id=animal_id, lote=lote, fecha=f,
            potrero_origen=origen, potrero_destino=destino, motivo=motivo,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def registrar_pesaje(self, animal_tag, fecha=None, peso_kg=None,
                         gmd_calculada=None, evento=None, registrado_por=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        f = iso(fecha)
        # Mismo animal + misma fecha + mismo peso exacto: en la práctica
        # siempre es la misma nota reenviada, no dos pesajes reales idénticos.
        existente = self._id_si_ya_existe("pesajes", {
            "animal_id": animal_id, "fecha": f, "peso_kg": peso_kg,
        })
        if existente:
            return existente
        return self.insert("pesajes", dict(
            animal_id=animal_id, fecha=f, peso_kg=peso_kg,
            gmd_calculada=gmd_calculada, evento=evento,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def registrar_movimiento(self, animal_tag, fecha=None, tipo_movimiento=None,
                             procedencia_destino=None, precio=None, notas=None,
                             registrado_por=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        f = iso(fecha)
        # Idempotente por (animal_id, fecha, tipo_movimiento): un animal no se
        # vende/compra dos veces el mismo día, así que una nota repetida
        # (doble envío, reintento de red) no debe duplicar el movimiento.
        existente = self._id_si_ya_existe("movimientos", {
            "animal_id": animal_id, "fecha": f, "tipo_movimiento": tipo_movimiento,
        })
        if existente:
            return existente
        return self.insert("movimientos", dict(
            animal_id=animal_id, fecha=f, tipo_movimiento=tipo_movimiento,
            procedencia_destino=procedencia_destino, precio=precio, notas=notas,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def registrar_condicion_corporal(self, animal_tag, fecha=None, valor=None,
                                     notas=None, registrado_por=None) -> int:
        animal_id = self.resolve_animal(animal_tag, crear=True)
        f = iso(fecha)
        # Mismo animal + misma fecha + mismo valor: nota reenviada, no dos
        # evaluaciones reales idénticas el mismo día.
        existente = self._id_si_ya_existe("condicion_corporal", {
            "animal_id": animal_id, "fecha": f, "valor": valor,
        })
        if existente:
            return existente
        return self.insert("condicion_corporal", dict(
            animal_id=animal_id, fecha=f, valor=valor, notas=notas,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def ultima_condicion_corporal(self, animal_tag_or_id) -> Optional[sqlite3.Row]:
        aid = self.resolve_animal(animal_tag_or_id)
        if aid is None:
            return None
        return self.query_one(
            "SELECT * FROM condicion_corporal WHERE animal_id = ? ORDER BY fecha DESC LIMIT 1", (aid,)
        )

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

    def vincular_fotos_huerfanas(self) -> int:
        """Vincula fotos existentes donde tag o animal_id sea NULL si el caption, ocr o ruta tiene un tag reconocible."""
        from ..parsers import nlp_engine as nlu
        filas = self.query(
            "SELECT id, caption, ruta, ocr_text FROM fotos "
            "WHERE animal_id IS NULL OR tag IS NULL OR UPPER(tag) = 'SIN TAG'"
        )
        vinculadas = 0
        for f in filas:
            cand_tag = None
            if f["caption"]:
                cand_tag = nlu.extraer_tag(f["caption"])
            if not cand_tag and f["ocr_text"]:
                cand_tag = nlu.extraer_tag(f["ocr_text"])
            if not cand_tag and f["ruta"]:
                cand_tag = nlu.extraer_tag(f["ruta"])
            if cand_tag:
                aid = self.resolve_animal(cand_tag, crear=False)
                self.conn.execute(
                    "UPDATE fotos SET tag = ?, animal_id = ? WHERE id = ?",
                    (cand_tag, aid, f["id"]),
                )
                vinculadas += 1
        if vinculadas > 0:
            self.conn.commit()
        return vinculadas

    def fotos_de(self, animal_tag_or_id, limit: int = 5) -> list[sqlite3.Row]:
        aid = self.resolve_animal(animal_tag_or_id)
        tag_str = str(animal_tag_or_id).strip()
        tag_like = f"%{tag_str}%"
        if aid is not None:
            return self.query(
                "SELECT * FROM fotos WHERE animal_id = ? "
                "   OR UPPER(tag) = UPPER(?) "
                "   OR UPPER(caption) LIKE UPPER(?) "
                "   OR UPPER(ocr_text) LIKE UPPER(?) "
                "   OR UPPER(ruta) LIKE UPPER(?) "
                "ORDER BY id DESC LIMIT ?",
                (aid, tag_str, tag_like, tag_like, tag_like, limit),
            )
        return self.query(
            "SELECT * FROM fotos WHERE UPPER(tag) = UPPER(?) "
            "   OR UPPER(caption) LIKE UPPER(?) "
            "   OR UPPER(ocr_text) LIKE UPPER(?) "
            "   OR UPPER(ruta) LIKE UPPER(?) "
            "ORDER BY id DESC LIMIT ?",
            (tag_str, tag_like, tag_like, tag_like, limit),
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

    def detectar_duplicados_geneticos(self) -> list[dict]:
        """Agrupa animales ACTIVOS por (madre_id, padre_id, fecha_nacimiento) y
        devuelve los grupos con más de un animal: casi siempre el mismo
        nacimiento importado dos veces bajo tags distintos (ej. 'N065' vs
        'NO65', confusión letra O / dígito 0 al transcribir o en el DBF).
        Requiere madre_id y fecha_nacimiento no nulos para evitar falsos
        positivos entre animales sin genealogía registrada. Excluye grupos
        donde TODOS los animales tienen en sus notas una marca de mellizos
        (ej. 'GEMELA1'/'GEMELA2'): un parto doble real no es un duplicado."""
        grupos_raw = self.query(
            """
            SELECT madre_id, padre_id, fecha_nacimiento, COUNT(*) AS n
            FROM animales
            WHERE estado = 'ACTIVO' AND madre_id IS NOT NULL AND fecha_nacimiento IS NOT NULL
            GROUP BY madre_id, padre_id, fecha_nacimiento
            HAVING COUNT(*) > 1
            ORDER BY fecha_nacimiento DESC
            """
        )
        patron_mellizos = re.compile(r"gemel|melliz", re.IGNORECASE)
        grupos = []
        for g in grupos_raw:
            animales = self.query(
                "SELECT id_animal, tag, notas FROM animales "
                "WHERE estado = 'ACTIVO' AND madre_id = ? "
                "AND (padre_id IS ? ) AND fecha_nacimiento = ?",
                (g["madre_id"], g["padre_id"], g["fecha_nacimiento"]),
            )
            if animales and all(a["notas"] and patron_mellizos.search(a["notas"]) for a in animales):
                continue  # parto múltiple real (mellizos), no un duplicado
            madre = self.get_animal(g["madre_id"])
            grupos.append({
                "madre_id": g["madre_id"],
                "madre_tag": madre["tag"] if madre else str(g["madre_id"]),
                "fecha_nacimiento": g["fecha_nacimiento"],
                "ids": [a["id_animal"] for a in animales],
                "tags": [a["tag"] for a in animales],
                "n": g["n"],
            })
        return grupos

    def ultimos_registros(self, limite: int = 15) -> list[sqlite3.Row]:
        """Últimos eventos registrados en cualquiera de las tablas de
        TABLAS_EVENTOS, ordenados por momento de inserción (no por fecha del
        evento). Usado por /ultimos y /deshacer para que un admin pueda ver
        y corregir un registro reciente hecho por error (propio o de un
        trabajador). Los registros creados antes de esta migración no tienen
        creado_en y quedan al final."""
        return self.query(
            """
            SELECT * FROM (
                SELECT 'partos' AS tabla, p.id AS id, a.tag AS tag, p.fecha AS fecha,
                       ('Parto' || CASE WHEN p.sexo_cria IS NOT NULL THEN ' - cría ' || p.sexo_cria ELSE '' END) AS resumen,
                       p.creado_en AS creado_en, p.registrado_por AS registrado_por
                FROM partos p LEFT JOIN animales a ON a.id_animal = p.vaca_id
                UNION ALL
                SELECT 'muertes', m.id, a.tag, m.fecha,
                       ('Muerte' || CASE WHEN m.causa_presunta IS NOT NULL THEN ' - ' || m.causa_presunta ELSE '' END),
                       m.creado_en, m.registrado_por
                FROM muertes m LEFT JOIN animales a ON a.id_animal = m.animal_id
                UNION ALL
                SELECT 'servicios', s.id, a.tag, s.fecha,
                       ('Servicio ' || COALESCE(s.tipo_servicio, '')),
                       s.creado_en, s.registrado_por
                FROM servicios s LEFT JOIN animales a ON a.id_animal = s.vaca_id
                UNION ALL
                SELECT 'celos', c.id, a.tag, c.fecha,
                       ('Celo ' || COALESCE(c.am_pm, '')),
                       c.creado_en, c.registrado_por
                FROM celos c LEFT JOIN animales a ON a.id_animal = c.vaca_id
                UNION ALL
                SELECT 'tratamientos', t.id, a.tag, t.fecha,
                       ('Tratamiento' || CASE WHEN t.producto IS NOT NULL THEN ' - ' || t.producto ELSE '' END),
                       t.creado_en, t.registrado_por
                FROM tratamientos t LEFT JOIN animales a ON a.id_animal = t.animal_id
                UNION ALL
                SELECT 'traslados', tr.id, a.tag, tr.fecha,
                       'Traslado',
                       tr.creado_en, tr.registrado_por
                FROM traslados tr LEFT JOIN animales a ON a.id_animal = tr.animal_id
                UNION ALL
                SELECT 'pesajes', pe.id, a.tag, pe.fecha,
                       ('Pesaje' || CASE WHEN pe.peso_kg IS NOT NULL THEN ' ' || pe.peso_kg || 'kg' ELSE '' END),
                       pe.creado_en, pe.registrado_por
                FROM pesajes pe LEFT JOIN animales a ON a.id_animal = pe.animal_id
                UNION ALL
                SELECT 'movimientos', mo.id, a.tag, mo.fecha,
                       ('Movimiento ' || COALESCE(mo.tipo_movimiento, '')),
                       mo.creado_en, mo.registrado_por
                FROM movimientos mo LEFT JOIN animales a ON a.id_animal = mo.animal_id
                UNION ALL
                SELECT 'condicion_corporal', cc.id, a.tag, cc.fecha,
                       ('Condición corporal' || CASE WHEN cc.valor IS NOT NULL THEN ' ' || cc.valor ELSE '' END),
                       cc.creado_en, cc.registrado_por
                FROM condicion_corporal cc LEFT JOIN animales a ON a.id_animal = cc.animal_id
            )
            ORDER BY creado_en IS NULL, creado_en DESC, id DESC
            LIMIT ?
            """,
            (limite,),
        )

    def detalle_registro(self, tabla: str, id_registro: int) -> Optional[dict]:
        """Detalle legible de una fila puntual de una tabla de eventos, para
        que /deshacer muestre qué se va a borrar antes de confirmar."""
        if tabla not in self.TABLAS_EVENTOS:
            return None
        fk_animal = "vaca_id" if tabla in ("partos", "servicios", "celos") else "animal_id"
        fila = self.query_one(f"SELECT * FROM {tabla} WHERE id = ?", (id_registro,))
        if fila is None:
            return None
        animal = self.get_animal(fila[fk_animal]) if fila[fk_animal] is not None else None
        tag = animal["tag"] if animal else "?"
        resumenes = {
            "partos": lambda f: f"Parto de {tag} — cría {f['sexo_cria'] or '?'}",
            "muertes": lambda f: f"Muerte de {tag}" + (f" — {f['causa_presunta']}" if f["causa_presunta"] else ""),
            "servicios": lambda f: f"Servicio de {tag} ({f['tipo_servicio'] or '?'})",
            "celos": lambda f: f"Celo de {tag} ({f['am_pm'] or '?'})",
            "tratamientos": lambda f: f"Tratamiento de {tag}" + (f" — {f['producto']}" if f["producto"] else ""),
            "traslados": lambda f: f"Traslado de {tag} (lote {f['lote'] or '?'})",
            "pesajes": lambda f: f"Pesaje de {tag}" + (f" — {f['peso_kg']}kg" if f["peso_kg"] is not None else ""),
            "movimientos": lambda f: f"Movimiento de {tag} ({f['tipo_movimiento'] or '?'})",
            "condicion_corporal": lambda f: f"Condición corporal de {tag}" + (f" — {f['valor']}" if f["valor"] is not None else ""),
        }
        return {
            "tabla": tabla, "id": id_registro, "tag": tag,
            "fecha": fila["fecha"], "resumen": resumenes[tabla](fila),
            "creado_en": fila["creado_en"], "registrado_por": fila["registrado_por"],
        }

    def eliminar_registro(self, tabla: str, id_registro: int) -> bool:
        """Elimina una fila puntual de una tabla de eventos por id (comando
        /deshacer). Restringido a TABLAS_EVENTOS por allow-list: nunca borra
        de animales/potreros u otras tablas por esta vía."""
        if tabla not in self.TABLAS_EVENTOS:
            raise ValueError(f"Tabla no permitida para /deshacer: {tabla}")
        cur = self.conn.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_registro,))
        self.conn.commit()
        return cur.rowcount > 0

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
            "condicion_corporal": self.query(
                "SELECT * FROM condicion_corporal WHERE animal_id = ? ORDER BY fecha", (aid,)
            ),
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

    def marcar_historicos_sg(self) -> int:
        """Marca como HISTORICO los animales asignados a potreros numéricos viejos (01-23) de SG."""
        cur = self.conn.execute(
            """
            UPDATE animales
            SET estado = 'HISTORICO'
            WHERE estado = 'ACTIVO'
              AND potrero_id IN (
                  SELECT id FROM potreros
                  WHERE codigo GLOB '[0-9][0-9]' OR codigo GLOB '[0-9]'
              )
            """
        )
        self.conn.commit()
        return cur.rowcount
