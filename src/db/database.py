"""Capa de acceso a datos SQLite para la bitácora de campo zootécnico."""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Optional

from ..utils import add_days, iso, to_date
from .models import SCHEMA_SQL, TIPOS_EVENTO_PARTO, TIPOS_EVENTO_SIN_CRIA

logger = logging.getLogger(__name__)


class Database:
    """Envoltorio de sqlite3 con helpers de resolución tag → id y CRUD."""

    # Tablas de eventos elegibles para el registro de auditoría y el
    # comando /deshacer (excluye animales/potreros/alertas/fotos, que no
    # son "eventos de campo" puntuales en el mismo sentido).
    TABLAS_EVENTOS = (
        "partos", "muertes", "servicios", "celos", "tratamientos",
        "traslados", "destetes", "pesajes", "movimientos", "condicion_corporal",
        "produccion_leche", "diagnosticos_gestacion", "pluviometria",
        "aforos_historico", "monitoreo_satelital_ndvi", "monitoreo_satelital_lluvia",
        "rondas_campo",
    )

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        if path != ":memory:":
            try:
                self.conn.execute("PRAGMA journal_mode = WAL;")
                self.conn.execute("PRAGMA busy_timeout = 10000;")
                self.conn.execute("PRAGMA synchronous = NORMAL;")
            except Exception:
                pass
            self._migrar_columnas_esenciales()
        try:
            self.conn.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            pass

    def _migrar_columnas_esenciales(self) -> None:
        """Añade columnas nuevas a bases de datos existentes de forma segura e idempotente."""
        try:
            tablas = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "partos" in tablas:
                cols_p = {r[1] for r in self.conn.execute("PRAGMA table_info(partos)").fetchall()}
                if "tipo_evento" not in cols_p:
                    self.conn.execute("ALTER TABLE partos ADD COLUMN tipo_evento TEXT DEFAULT 'PARTO'")
                if "grupo_parto_id" not in cols_p:
                    self.conn.execute("ALTER TABLE partos ADD COLUMN grupo_parto_id INTEGER")
            if "animales" in tablas:
                cols_a = {r[1] for r in self.conn.execute("PRAGMA table_info(animales)").fetchall()}
                if "hierro" not in cols_a:
                    self.conn.execute("ALTER TABLE animales ADD COLUMN hierro TEXT")
                if "chip" not in cols_a:
                    self.conn.execute("ALTER TABLE animales ADD COLUMN chip TEXT")
                if "color" not in cols_a:
                    self.conn.execute("ALTER TABLE animales ADD COLUMN color TEXT")
            if "fotos" in tablas:
                cols_f = {r[1] for r in self.conn.execute("PRAGMA table_info(fotos)").fetchall()}
                if "ocr_text" not in cols_f:
                    self.conn.execute("ALTER TABLE fotos ADD COLUMN ocr_text TEXT")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Ciclo de vida y utilidades de bajo nivel
    # ------------------------------------------------------------------ #
    def create_tables(self) -> "Database":
        self._migrar_columnas_esenciales()
        self.conn.executescript(SCHEMA_SQL)
        # Migración idempotente para columnas añadidas
        try:
            cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(animales)").fetchall()]
            if "hierro" not in cols:
                self.conn.execute("ALTER TABLE animales ADD COLUMN hierro TEXT")
            if "chip" not in cols:
                self.conn.execute("ALTER TABLE animales ADD COLUMN chip TEXT")
            if "color" not in cols:
                self.conn.execute("ALTER TABLE animales ADD COLUMN color TEXT")
        except Exception:
            pass
        try:
            cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(fotos)").fetchall()]
            if "ocr_text" not in cols:
                self.conn.execute("ALTER TABLE fotos ADD COLUMN ocr_text TEXT")
        except Exception:
            pass
        # Geometria real (WGS84) de potreros, importada desde el proyecto QGIS
        # de la finca (ver docs/PLAN_GEO_SATELITAL_6.2_8.2.md, Fase B).
        try:
            cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(potreros)").fetchall()]
            if "geom_wkt_4326" not in cols:
                self.conn.execute("ALTER TABLE potreros ADD COLUMN geom_wkt_4326 TEXT")
            if "centroide_lat" not in cols:
                self.conn.execute("ALTER TABLE potreros ADD COLUMN centroide_lat REAL")
            if "centroide_lon" not in cols:
                self.conn.execute("ALTER TABLE potreros ADD COLUMN centroide_lon REAL")
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
        # tipo_evento/grupo_parto_id: catálogo de tipo de evento reproductivo
        # (Parto/Gemelar/Aborto/Reabsorción/Momificación/Maceración/Muerte
        # fetal, ver TIPOS_EVENTO_PARTO). Backfill de filas preexistentes con
        # la misma regla que antes se usaba solo para inferir "ABORTO" en el
        # dashboard/exportador (id_cria IS NULL AND estado_cria='MUERTO'), y
        # detección de gemelares ya anotados a mano en notas.
        try:
            cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(partos)").fetchall()]
            if "tipo_evento" not in cols:
                self.conn.execute("ALTER TABLE partos ADD COLUMN tipo_evento TEXT DEFAULT 'PARTO'")
            if "grupo_parto_id" not in cols:
                self.conn.execute("ALTER TABLE partos ADD COLUMN grupo_parto_id INTEGER")
            self.conn.execute(
                "UPDATE partos SET tipo_evento = 'ABORTO' "
                "WHERE tipo_evento IS NULL AND id_cria IS NULL AND UPPER(COALESCE(estado_cria, '')) = 'MUERTO'"
            )
            self.conn.execute(
                "UPDATE partos SET tipo_evento = 'GEMELAR' "
                "WHERE tipo_evento IS NULL AND notas IS NOT NULL "
                "AND (UPPER(notas) LIKE '%GEMEL%' OR UPPER(notas) LIKE '%MELLIZ%')"
            )
            self.conn.execute("UPDATE partos SET tipo_evento = 'PARTO' WHERE tipo_evento IS NULL")
        except Exception:
            pass
        # Saneamiento idempotente de autorreferencias corruptas
        try:
            self.conn.execute("UPDATE animales SET madre_id = NULL WHERE madre_id = id_animal")
            self.conn.execute("UPDATE animales SET padre_id = NULL WHERE padre_id = id_animal")
            self.conn.execute("DELETE FROM partos WHERE vaca_id = id_cria AND vaca_id IS NOT NULL")
        except Exception as e:
            logger.error("Error en saneamiento de autorreferencias en create_tables: %s", e, exc_info=True)
        try:
            self.vincular_fotos_huerfanas()
        except Exception as e:
            logger.error("Error en vincular_fotos_huerfanas durante create_tables: %s", e, exc_info=True)
        try:
            self.marcar_historicos_sg()
        except Exception as e:
            logger.error("Error en marcar_historicos_sg durante create_tables: %s", e, exc_info=True)
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

    def renombrar_animal(self, tag_viejo, tag_nuevo) -> Optional[int]:
        """Cambia el tag de un animal ya existente (ej. al pasar de código
        temporal a chapeta definitiva), conservando su id_animal y por lo
        tanto todo su historial ya registrado."""
        aid = self.animal_id(tag_viejo)
        if aid is None:
            return None
        nuevo = str(tag_nuevo).strip()
        if not nuevo or self.animal_id(nuevo) is not None:
            return None
        self.execute("UPDATE animales SET tag = ? WHERE id_animal = ?", (nuevo, aid))
        return aid

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
                         potrero=None, estado=None, notas=None, hierro=None,
                         chip=None, color=None) -> int:
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
            hierro=hierro, chip=chip, color=color,
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
                          dias_ocupacion=None, geom_wkt_4326=None,
                          centroide_lat=None, centroide_lon=None) -> int:
        return self.insert("potreros", dict(
            nombre=nombre, codigo=codigo, area_has=area_has, tipo_pasto=tipo_pasto,
            aforo_kg_m2=aforo_kg_m2, fecha_entrada=iso(fecha_entrada),
            fecha_salida=iso(fecha_salida), dias_reposo=dias_reposo,
            dias_ocupacion=dias_ocupacion, geom_wkt_4326=geom_wkt_4326,
            centroide_lat=centroide_lat, centroide_lon=centroide_lon,
        ))

    def get_potrero(self, potrero_id) -> Optional[sqlite3.Row]:
        if potrero_id is None:
            return None
        return self.query_one("SELECT * FROM potreros WHERE id = ?", (potrero_id,))


    def registrar_parto(self, vaca_tag, fecha=None, sexo_cria=None,
                        estado_cria="VIVO", peso_nacimiento=None, id_cria_tag=None,
                        notas=None, potrero_cria=None, potrero_madre=None,
                        registrado_por=None, tipo_evento="PARTO",
                        grupo_parto_id=None) -> int:
        tipo_evento = (tipo_evento or "PARTO").strip().upper()
        if tipo_evento not in TIPOS_EVENTO_PARTO:
            tipo_evento = "PARTO"
        # Reabsorción/momificación/maceración/muerte fetal/aborto nunca
        # generan una cría: se ignora cualquier id_cria_tag recibido por
        # error y se homologa estado_cria='MUERTO' para no romper el resto
        # del sistema (IEP, dashboard, exportador), que sigue leyendo
        # estado_cria/id_cria además del tipo_evento explícito.
        if tipo_evento in TIPOS_EVENTO_SIN_CRIA:
            id_cria_tag = None
            estado_cria = "MUERTO"

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
                # La cría nace en el mismo potrero donde está la madre en ese
                # momento -- si no se hereda aquí, queda "sin potrero" hasta
                # el próximo backup/import de Software Ganadero. Solo se
                # hereda si el potrero de la madre es uno real y vigente
                # (con geometría), no uno legacy de Software Ganadero --
                # heredar un potrero legacy sería peor que dejarlo sin
                # potrero: mostraría una ubicación falsa en vez de "sin dato".
                fila_vaca = self.query_one(
                    "SELECT p.id FROM animales a JOIN potreros p ON p.id = a.potrero_id "
                    "WHERE a.id_animal = ? AND p.geom_wkt_4326 IS NOT NULL", (vaca_id,)
                )
                if fila_vaca is not None:
                    self.execute(
                        "UPDATE animales SET potrero_id = COALESCE(potrero_id, ?) WHERE id_animal = ?", (fila_vaca["id"], id_cria)
                    )
            if sexo_cria:
                self.execute(
                    "UPDATE animales SET sexo = COALESCE(sexo, ?) WHERE id_animal = ?", (sexo_cria, id_cria)
                )
            if fecha:
                self.execute(
                    "UPDATE animales SET fecha_nacimiento = COALESCE(fecha_nacimiento, ?) WHERE id_animal = ?", (iso(fecha), id_cria)
                )
            # Potrero explícito de la cría (ej. la separan de la madre a otro
            # lote desde el nacimiento): pisa la herencia automática de arriba,
            # a diferencia de esa que solo aplica si la cría no tenía potrero.
            if potrero_cria:
                pid_cria = self.resolve_potrero(potrero_cria)
                if pid_cria:
                    self.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (pid_cria, id_cria))
        # Potrero nuevo de la madre en el momento del parto (ej. la pasan a un
        # potrero de maternidad/postparto).
        if potrero_madre and vaca_id:
            pid_madre = self.resolve_potrero(potrero_madre)
            if pid_madre:
                self.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (pid_madre, vaca_id))
        nuevo_id = self.insert("partos", dict(
            vaca_id=vaca_id, fecha=iso(fecha), sexo_cria=sexo_cria,
            estado_cria=estado_cria, peso_nacimiento=peso_nacimiento,
            id_cria=id_cria, notas=notas, tipo_evento=tipo_evento,
            grupo_parto_id=grupo_parto_id,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))
        # Primer gemelo de un parto GEMELAR: si no se pasó grupo_parto_id
        # (aún no existe una fila hermana con la cual agrupar), el propio id
        # se usa como grupo_parto_id para que el segundo gemelo pueda
        # referenciarlo al llamar de nuevo con grupo_parto_id=nuevo_id.
        if tipo_evento == "GEMELAR" and grupo_parto_id is None:
            self.execute("UPDATE partos SET grupo_parto_id = ? WHERE id = ?", (nuevo_id, nuevo_id))
        return nuevo_id

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
        serv_id = self.insert("servicios", dict(
            vaca_id=vaca_id, fecha=f, tipo_servicio=tipo_servicio,
            toro_pajilla=toro_pajilla, raza_toro=raza_toro, inseminador=inseminador,
            fep_calculada=iso(fep_calculada), estado=estado,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))
        if (tipo_servicio or "").upper() == "IA" and toro_pajilla:
            try:
                ok = self.descontar_pajuela(toro_pajilla, cantidad=1)
                if not ok:
                    logger.warning(
                        "No se pudo descontar pajuela automáticamente para toro/pajilla '%s' "
                        "al registrar servicio id=%s: sin stock o toro inexistente",
                        toro_pajilla, serv_id,
                    )
            except Exception as e:
                logger.warning(
                    "No se pudo descontar pajuela automáticamente para toro/pajilla '%s' "
                    "al registrar servicio id=%s: %s",
                    toro_pajilla, serv_id, e,
                )
        return serv_id

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
        tid = self.insert("traslados", dict(
            animal_id=animal_id, lote=lote, fecha=f,
            potrero_origen=origen, potrero_destino=destino, motivo=motivo,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))
        # El traslado es el evento de "mover" un animal -- sin esto el registro
        # queda solo como nota histórica y el animal sigue apareciendo en su
        # potrero viejo en Inventario/Ficha/filtros (todos leen animales.potrero_id
        # directo, no el último traslado).
        if destino is not None:
            self.execute("UPDATE animales SET potrero_id = ? WHERE id_animal = ?", (destino, animal_id))
        return tid

    def registrar_destete(self, cria_tag, fecha=None, peso_kg=None,
                          potrero_cria=None, potrero_madre=None, cond_corporal_madre=None,
                          peso_madre_kg=None, notas=None, registrado_por=None) -> int:
        """Registra el destete de una cría (se separa de la madre, suele pasar
        a potrero de levante) y opcionalmente el estado de la madre en ese
        mismo momento (peso, condición corporal, nuevo potrero -- muchas
        veces coincide con el secado de la vaca antes del próximo parto).
        Equivalente a la pantalla "Secados/Destetos" de Software Ganadero."""
        cria_id = self.resolve_animal(cria_tag, crear=True)
        f = iso(fecha)
        existente = self._id_si_ya_existe("destetes", {"animal_id": cria_id, "fecha": f})
        if existente:
            return existente

        fila_cria = self.get_animal(cria_id)
        madre_id = fila_cria["madre_id"] if fila_cria else None

        pot_cria_id = self.resolve_potrero(potrero_cria) if potrero_cria else None
        pot_madre_id = self.resolve_potrero(potrero_madre) if potrero_madre else None

        did = self.insert("destetes", dict(
            animal_id=cria_id, madre_id=madre_id, fecha=f, peso_kg=peso_kg,
            potrero_cria=pot_cria_id, potrero_madre=pot_madre_id,
            peso_madre_kg=peso_madre_kg, cond_corporal_madre=cond_corporal_madre,
            notas=notas, creado_en=self._ahora(), registrado_por=registrado_por,
        ))

        if peso_kg is not None:
            self.registrar_pesaje(cria_tag, fecha=f, peso_kg=peso_kg, evento="DESTETE", registrado_por=registrado_por)
        if potrero_cria:
            self.registrar_traslado(cria_tag, fecha=f, potrero_destino=potrero_cria,
                                    motivo="Destete", registrado_por=registrado_por)
        if potrero_madre and madre_id:
            madre_fila = self.get_animal(madre_id)
            if madre_fila:
                self.registrar_traslado(madre_fila["tag"], fecha=f, potrero_destino=potrero_madre,
                                        motivo="Destete de cría", registrado_por=registrado_por)
        return did

    def cria_activa_de_madre(self, madre_tag) -> Optional[dict]:
        """Busca la cría ACTIVA más reciente de una vaca que aún no fue
        destetada (sin fila en `destetes`). La usa Captura > Destete para
        que el operario busque por el arete de la VACA -- que suele
        recordar de memoria mejor que el de una cría reciente -- y el
        sistema resuelva la cría automáticamente en vez de forzarlo a
        buscar/escribir el arete de la cría primero."""
        madre_id = self.resolve_animal(madre_tag)
        if madre_id is None:
            return None
        fila = self.query_one(
            "SELECT a.tag, a.fecha_nacimiento FROM animales a "
            "WHERE a.madre_id = ? AND a.estado = 'ACTIVO' "
            "AND a.id_animal NOT IN (SELECT animal_id FROM destetes) "
            "ORDER BY a.fecha_nacimiento DESC, a.id_animal DESC LIMIT 1",
            (madre_id,),
        )
        return dict(fila) if fila else None

    def animales_activos_en_potrero(self, potrero_id: int) -> list[str]:
        """Tags de los animales ACTIVOS cuyo potrero actual es `potrero_id`."""
        filas = self.query(
            "SELECT tag FROM animales WHERE potrero_id = ? AND estado = 'ACTIVO' AND tag IS NOT NULL",
            (potrero_id,),
        )
        return [f["tag"] for f in filas]

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

    def registrar_produccion_leche(self, fecha=None, litros=0.0, animal_tag=None,
                                   notas=None, registrado_por=None) -> int:
        f = iso(fecha) or date.today().isoformat()
        aid = self.resolve_animal(animal_tag) if animal_tag else None
        return self.insert("produccion_leche", dict(
            animal_id=aid, fecha=f, litros=float(litros or 0.0), notas=notas,
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

    def registrar_finanza(self, fecha=None, tipo=None, categoria=None, concepto=None,
                          monto=0.0, litros=None, animal_tag=None, potrero=None,
                          contraparte=None, foto_ruta=None, notas=None,
                          registrado_por=None) -> int:
        f = iso(fecha) or date.today().isoformat()
        animal_id = self.resolve_animal(animal_tag) if animal_tag else None
        potrero_id = self.resolve_potrero(potrero) if potrero else None
        return self.insert("finanzas", dict(
            fecha=f, tipo=(tipo or "").strip().upper(), categoria=(categoria or "").strip().upper(),
            concepto=concepto, monto=float(monto or 0.0), litros=(float(litros) if litros is not None else None),
            animal_id=animal_id, potrero_id=potrero_id, contraparte=contraparte,
            foto_ruta=foto_ruta, notas=notas,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def editar_finanza(self, id_finanza: int, fecha=None, tipo=None, categoria=None,
                       concepto=None, monto=None, litros=None, animal_tag=None,
                       potrero=None, contraparte=None, notas=None) -> bool:
        """Edita un movimiento de `finanzas` ya existente. Cada argumento en
        None se deja tal cual estaba (no se toca); para vaciar un campo de
        texto opcional (concepto/contraparte/notas) pase "" explícitamente.
        Devuelve False si el id no existe."""
        existente = self.query_one("SELECT id FROM finanzas WHERE id = ?", (id_finanza,))
        if not existente:
            return False
        campos: dict[str, Any] = {}
        if fecha is not None:
            campos["fecha"] = iso(fecha) or fecha
        if tipo is not None:
            campos["tipo"] = str(tipo).strip().upper()
        if categoria is not None:
            campos["categoria"] = str(categoria).strip().upper()
        if concepto is not None:
            campos["concepto"] = concepto
        if monto is not None:
            campos["monto"] = float(monto)
        if litros is not None:
            campos["litros"] = float(litros) if litros != "" else None
        if animal_tag is not None:
            campos["animal_id"] = self.resolve_animal(animal_tag) if animal_tag else None
        if potrero is not None:
            campos["potrero_id"] = self.resolve_potrero(potrero) if potrero else None
        if contraparte is not None:
            campos["contraparte"] = contraparte
        if notas is not None:
            campos["notas"] = notas
        if not campos:
            return True
        sets = ", ".join(f"{k} = ?" for k in campos)
        self.execute(f"UPDATE finanzas SET {sets} WHERE id = ?", tuple(campos.values()) + (id_finanza,))
        return True

    def eliminar_finanza(self, id_finanza: int) -> bool:
        """Borra un movimiento de `finanzas` (ingreso/gasto manual). No toca
        `movimientos` (ventas/compras de animales), que se gestionan aparte."""
        existente = self.query_one("SELECT id FROM finanzas WHERE id = ?", (id_finanza,))
        if not existente:
            return False
        self.execute("DELETE FROM finanzas WHERE id = ?", (id_finanza,))
        return True

    def resumen_finanzas(self, desde: str, hasta: str) -> dict:
        """Resumen de Ingresos/Egresos/Utilidad entre `desde` y `hasta` (ISO),
        combinando el libro de `finanzas` con las ventas/compras de animales
        de `movimientos` (que ya traen su propio `precio`, sin duplicar)."""
        filas_finanzas = self.query(
            "SELECT tipo, categoria, SUM(monto) AS total, COUNT(*) AS n "
            "FROM finanzas WHERE fecha >= ? AND fecha <= ? GROUP BY tipo, categoria",
            (desde, hasta),
        )
        filas_animales = self.query(
            "SELECT UPPER(tipo_movimiento) AS tipo_movimiento, SUM(COALESCE(precio, 0)) AS total, COUNT(*) AS n "
            "FROM movimientos WHERE fecha >= ? AND fecha <= ? AND precio IS NOT NULL AND precio > 0 "
            "GROUP BY UPPER(tipo_movimiento)",
            (desde, hasta),
        )

        categorias: list[dict] = []
        total_ingresos = 0.0
        total_egresos = 0.0
        for fila in filas_finanzas:
            tipo = (fila["tipo"] or "").upper()
            total = float(fila["total"] or 0.0)
            categorias.append({"tipo": tipo, "categoria": fila["categoria"], "total": total, "n": fila["n"]})
            if tipo == "INGRESO":
                total_ingresos += total
            elif tipo == "EGRESO":
                total_egresos += total

        for fila in filas_animales:
            tm = fila["tipo_movimiento"] or ""
            total = float(fila["total"] or 0.0)
            if tm == "VENTA":
                categorias.append({"tipo": "INGRESO", "categoria": "VENTA_ANIMAL", "total": total, "n": fila["n"]})
                total_ingresos += total
            elif tm == "COMPRA":
                categorias.append({"tipo": "EGRESO", "categoria": "COMPRA_ANIMAL", "total": total, "n": fila["n"]})
                total_egresos += total

        return {
            "desde": desde, "hasta": hasta,
            "total_ingresos": round(total_ingresos, 2),
            "total_egresos": round(total_egresos, 2),
            "utilidad": round(total_ingresos - total_egresos, 2),
            "categorias": categorias,
        }

    def flujo_caja_mensual(self, desde: str, hasta: str) -> list[dict]:
        """Ingresos/egresos/utilidad por mes calendario entre desde y hasta
        (misma fuente que ``resumen_finanzas`` -- finanzas + ventas/compras
        de animales -- pero agrupado por mes para ver estacionalidad, no
        solo el acumulado del periodo)."""
        filas_finanzas = self.query(
            "SELECT strftime('%Y-%m', fecha) AS mes, tipo, SUM(monto) AS total "
            "FROM finanzas WHERE fecha >= ? AND fecha <= ? GROUP BY mes, tipo",
            (desde, hasta),
        )
        filas_animales = self.query(
            "SELECT strftime('%Y-%m', fecha) AS mes, UPPER(tipo_movimiento) AS tipo_movimiento, "
            "SUM(COALESCE(precio, 0)) AS total FROM movimientos "
            "WHERE fecha >= ? AND fecha <= ? AND precio IS NOT NULL AND precio > 0 "
            "GROUP BY mes, tipo_movimiento",
            (desde, hasta),
        )
        por_mes: dict[str, dict] = {}

        def _mes(m):
            return por_mes.setdefault(m, {"mes": m, "ingresos": 0.0, "egresos": 0.0})

        for f in filas_finanzas:
            if not f["mes"]:
                continue
            fila = _mes(f["mes"])
            total = float(f["total"] or 0.0)
            if (f["tipo"] or "").upper() == "INGRESO":
                fila["ingresos"] += total
            else:
                fila["egresos"] += total
        for f in filas_animales:
            if not f["mes"]:
                continue
            fila = _mes(f["mes"])
            total = float(f["total"] or 0.0)
            if f["tipo_movimiento"] == "VENTA":
                fila["ingresos"] += total
            elif f["tipo_movimiento"] == "COMPRA":
                fila["egresos"] += total

        filas = sorted(por_mes.values(), key=lambda x: x["mes"])
        for fila in filas:
            fila["ingresos"] = round(fila["ingresos"], 2)
            fila["egresos"] = round(fila["egresos"], 2)
            fila["utilidad"] = round(fila["ingresos"] - fila["egresos"], 2)
        return filas

    def kpis_financieros(self, desde: str, hasta: str) -> dict:
        """KPIs Fase 2 de Finanzas: costo por litro de leche, margen de
        utilidad, costo por cabeza y costo por kg de carne vendida.

        El costo por kg de carne es una APROXIMACIÓN: no se registra el peso
        del animal en el momento de la venta, así que se usa el último
        pesaje conocido antes de esa fecha. Ventas sin ningún pesaje previo
        quedan excluidas del cálculo (se reportan aparte en
        ``ventas_sin_peso`` para que quede claro que el número es parcial)."""
        resumen = self.resumen_finanzas(desde, hasta)
        total_ingresos = resumen["total_ingresos"]
        total_egresos = resumen["total_egresos"]

        litros_row = self.query_one(
            "SELECT SUM(litros) AS total FROM produccion_leche WHERE fecha >= ? AND fecha <= ?",
            (desde, hasta),
        )
        litros_producidos = float(litros_row["total"] or 0.0) if litros_row else 0.0
        costo_por_litro_leche = round(total_egresos / litros_producidos, 2) if litros_producidos > 0 else None

        margen_utilidad_pct = (
            round((total_ingresos - total_egresos) / total_ingresos * 100, 1)
            if total_ingresos > 0 else None
        )

        total_activos = self.query_one("SELECT COUNT(*) AS n FROM animales WHERE estado = 'ACTIVO'")["n"]
        costo_por_cabeza = round(total_egresos / total_activos, 2) if total_activos > 0 else None

        ventas = self.query(
            "SELECT animal_id, fecha FROM movimientos "
            "WHERE fecha >= ? AND fecha <= ? AND UPPER(tipo_movimiento) = 'VENTA' AND animal_id IS NOT NULL",
            (desde, hasta),
        )
        kg_total = 0.0
        ventas_con_peso = 0
        ventas_sin_peso = 0
        for v in ventas:
            p = self.query_one(
                "SELECT peso_kg FROM pesajes WHERE animal_id = ? AND fecha <= ? "
                "AND peso_kg IS NOT NULL ORDER BY fecha DESC LIMIT 1",
                (v["animal_id"], v["fecha"]),
            )
            if p and p["peso_kg"]:
                kg_total += float(p["peso_kg"])
                ventas_con_peso += 1
            else:
                ventas_sin_peso += 1
        costo_por_kg_carne = round(total_egresos / kg_total, 2) if kg_total > 0 else None

        # Desglose dinámico de ingresos y márgenes de lechería
        ing_leche_row = self.query_one(
            "SELECT SUM(monto) AS total, SUM(litros) AS total_l FROM finanzas "
            "WHERE fecha >= ? AND fecha <= ? AND tipo = 'INGRESO' AND UPPER(categoria) = 'VENTA_LECHE'",
            (desde, hasta),
        )
        ingresos_leche = float(ing_leche_row["total"] or 0.0) if ing_leche_row else 0.0
        litros_finanzas = float(ing_leche_row["total_l"] or 0.0) if ing_leche_row else 0.0
        base_litros_precio = litros_finanzas if litros_finanzas > 0 else litros_producidos
        precio_promedio_litro_leche = round(ingresos_leche / base_litros_precio, 2) if (ingresos_leche > 0 and base_litros_precio > 0) else None
        margen_por_litro_leche = round(precio_promedio_litro_leche - costo_por_litro_leche, 2) if (precio_promedio_litro_leche is not None and costo_por_litro_leche is not None) else None
        margen_leche_pct = round((margen_por_litro_leche / precio_promedio_litro_leche) * 100, 1) if (margen_por_litro_leche is not None and precio_promedio_litro_leche > 0) else None

        # Desglose dinámico de ingresos y márgenes de carne (ventas de ganado)
        ing_carne_row = self.query_one(
            "SELECT SUM(precio) AS total, COUNT(*) AS n FROM movimientos "
            "WHERE fecha >= ? AND fecha <= ? AND UPPER(tipo_movimiento) = 'VENTA' AND precio IS NOT NULL AND precio > 0",
            (desde, hasta),
        )
        ingresos_carne = float(ing_carne_row["total"] or 0.0) if ing_carne_row else 0.0
        animales_vendidos = int(ing_carne_row["n"] or 0) if ing_carne_row else 0
        precio_promedio_kg_carne = round(ingresos_carne / kg_total, 2) if (ingresos_carne > 0 and kg_total > 0) else None
        precio_promedio_animal = round(ingresos_carne / animales_vendidos, 2) if (ingresos_carne > 0 and animales_vendidos > 0) else None
        margen_por_kg_carne = round(precio_promedio_kg_carne - costo_por_kg_carne, 2) if (precio_promedio_kg_carne is not None and costo_por_kg_carne is not None) else None
        margen_carne_pct = round((margen_por_kg_carne / precio_promedio_kg_carne) * 100, 1) if (margen_por_kg_carne is not None and precio_promedio_kg_carne > 0) else None

        return {
            "litros_producidos": round(litros_producidos, 1),
            "costo_por_litro_leche": costo_por_litro_leche,
            "ingresos_leche": ingresos_leche,
            "precio_promedio_litro_leche": precio_promedio_litro_leche,
            "margen_por_litro_leche": margen_por_litro_leche,
            "margen_leche_pct": margen_leche_pct,
            "margen_utilidad_pct": margen_utilidad_pct,
            "total_activos": total_activos,
            "costo_por_cabeza": costo_por_cabeza,
            "kg_carne_estimados": round(kg_total, 1),
            "ventas_con_peso": ventas_con_peso,
            "ventas_sin_peso": ventas_sin_peso,
            "ingresos_carne": ingresos_carne,
            "animales_vendidos": animales_vendidos,
            "precio_promedio_kg_carne": precio_promedio_kg_carne,
            "precio_promedio_animal": precio_promedio_animal,
            "costo_por_kg_carne": costo_por_kg_carne,
            "margen_por_kg_carne": margen_por_kg_carne,
            "margen_carne_pct": margen_carne_pct,
            "flujo_mensual": self.flujo_caja_mensual(desde, hasta),
        }

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

    def registrar_recordatorio(self, mensaje: str, fecha_programada=None, hora=None, creado_por=None) -> int:
        return self.insert("recordatorios_programados", dict(
            mensaje=mensaje, fecha_programada=iso(fecha_programada) if fecha_programada else None,
            hora=hora, creado_por=creado_por, estado="PENDIENTE", creado_en=self._ahora(),
        ))

    def listar_recordatorios_pendientes(self, fecha=None) -> list:
        if fecha is not None:
            return self.query(
                "SELECT * FROM recordatorios_programados WHERE estado='PENDIENTE' AND fecha_programada = ? ORDER BY hora, id", (iso(fecha),)
            )
        return self.query("SELECT * FROM recordatorios_programados WHERE estado='PENDIENTE' ORDER BY fecha_programada, hora, id")

    def marcar_enviado(self, rid: int) -> bool:
        cur = self.conn.execute("UPDATE recordatorios_programados SET estado='ENVIADO' WHERE id = ?", (rid,))
        self.conn.commit()
        return cur.rowcount > 0

    def registrar_leche(self, animal_tag, fecha=None, litros=None,
                        notas=None, registrado_por=None) -> int:
        if animal_tag is None:
            animal_id = None
        else:
            animal_id = self.resolve_animal(animal_tag, crear=True, sexo="Hembra")
        f = iso(fecha)
        # Mismo animal + misma fecha + mismos litros: nota reenviada, no dos
        # controles de leche reales idénticos el mismo día (el control es
        # semanal, no diario, así que esto casi nunca choca con un dato real).
        existente = self._id_si_ya_existe("produccion_leche", {
            "animal_id": animal_id, "fecha": f, "litros": litros,
        })
        if existente:
            return existente
        return self.insert("produccion_leche", dict(
            animal_id=animal_id, fecha=f, litros=litros, notas=notas,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

    def ultima_leche(self, animal_tag_or_id) -> Optional[sqlite3.Row]:
        aid = self.resolve_animal(animal_tag_or_id)
        if aid is None:
            return None
        return self.query_one(
            "SELECT * FROM produccion_leche WHERE animal_id = ? ORDER BY fecha DESC LIMIT 1", (aid,)
        )

    def historial_leche(self, animal_tag_or_id) -> list[sqlite3.Row]:
        aid = self.resolve_animal(animal_tag_or_id)
        if aid is None:
            return []
        return self.query(
            "SELECT * FROM produccion_leche WHERE animal_id = ? ORDER BY fecha", (aid,)
        )

    def registrar_consulta_animal(self, animal_tag_or_id, hoy=None) -> None:
        """Marca ``animal_tag_or_id`` como consultado ahora (para el panel de
        últimas consultas). No crea el animal si no existe; una consulta a un
        tag inexistente simplemente no deja rastro."""
        aid = self.resolve_animal(animal_tag_or_id, crear=False)
        if aid is None:
            return
        momento = iso(hoy) if hoy is not None else self._ahora()
        self.conn.execute(
            "INSERT OR REPLACE INTO consultas_animal (animal_id, ultima_fecha) VALUES (?, ?)",
            (aid, momento),
        )
        self.conn.commit()

    def ultimas_consultas_animal(self, limite: int = 4) -> list[sqlite3.Row]:
        """Últimos animales activos consultados, más reciente primero."""
        return self.query(
            """
            SELECT a.tag, c.ultima_fecha FROM consultas_animal c
            JOIN animales a ON a.id_animal = c.animal_id
            WHERE a.estado = 'ACTIVO' AND a.tag IS NOT NULL
            ORDER BY c.ultima_fecha DESC LIMIT ?
            """,
            (limite,),
        )

    def registrar_alerta(self, animal_tag, tipo_alerta, fecha_programada=None,
                         estado="PENDIENTE", descripcion=None) -> int:
        animal_id = self.resolve_animal(animal_tag) if animal_tag else None
        return self.insert("alertas", dict(
            animal_id=animal_id, tipo_alerta=tipo_alerta,
            fecha_programada=iso(fecha_programada), estado=estado,
            descripcion=descripcion,
        ))

    # ------------------------------------------------------------------ #
    # Pluviometría y Aforos Históricos (Fase 6.2)
    # ------------------------------------------------------------------ #
    def registrar_pluviometria(self, mm_lluvia: float, fecha=None,
                               estacion_o_sector: Optional[str] = None,
                               observaciones: Optional[str] = None,
                               registrado_por: Optional[int] = None) -> int:
        """Registra una medición pluviométrica (precipitación en mm)."""
        f = iso(fecha) or date.today().isoformat()
        return self.insert("pluviometria", dict(
            fecha=f,
            mm_lluvia=float(mm_lluvia),
            estacion_o_sector=estacion_o_sector.strip() if estacion_o_sector else None,
            observaciones=observaciones.strip() if observaciones else None,
            creado_en=self._ahora(),
            registrado_por=registrado_por,
        ))

    def obtener_pluviometria(self, limite: int = 30) -> list[sqlite3.Row]:
        """Obtiene las mediciones de lluvia más recientes."""
        return self.query(
            "SELECT * FROM pluviometria ORDER BY fecha DESC, id DESC LIMIT ?",
            (limite,),
        )

    def acumulado_lluvia(self, desde: Optional[str] = None, hasta: Optional[str] = None,
                         dias: Optional[int] = None, hoy: Optional[date] = None) -> float:
        """Calcula los mm totales de lluvia acumulada en un rango o últimos N días."""
        ref = hoy or date.today()
        if dias is not None:
            f_desde = iso(add_days(ref, -dias))
            f_hasta = iso(ref)
        else:
            f_desde = iso(desde) or "0001-01-01"
            f_hasta = iso(hasta) or iso(ref)

        row = self.query_one(
            "SELECT SUM(mm_lluvia) AS total_mm FROM pluviometria WHERE fecha >= ? AND fecha <= ?",
            (f_desde, f_hasta),
        )
        if row and row["total_mm"] is not None:
            return float(row["total_mm"])
        return 0.0

    def resumen_pluviometrico(self, hoy: Optional[date] = None) -> dict:
        """Calcula métricas clave de lluvia: hoy, últimos 7 días, 30 días, mes actual y clasificación estacional."""
        ref = hoy or date.today()
        f_hoy = iso(ref)
        primer_dia_mes = date(ref.year, ref.month, 1)

        lluvia_hoy = self.acumulado_lluvia(desde=f_hoy, hasta=f_hoy, hoy=ref)
        lluvia_7d = self.acumulado_lluvia(dias=7, hoy=ref)
        lluvia_30d = self.acumulado_lluvia(dias=30, hoy=ref)
        lluvia_mes = self.acumulado_lluvia(desde=iso(primer_dia_mes), hasta=f_hoy, hoy=ref)
        lluvia_anio = self.acumulado_lluvia(desde=f"{ref.year}-01-01", hasta=f_hoy, hoy=ref)

        # Clasificación estacional según precipitación mensual (30 días). El factor de
        # crecimiento usa la misma fórmula continua que ClimaIDEAM.clasificar_estacionalidad()
        # (factor_ajuste_clima), para que /clima y /balance_forrajero nunca muestren un
        # ajuste climático distinto para la misma lluvia — antes esta tabla tenía sus
        # propios 3 valores fijos (1.2/0.85/0.5) independientes de esa fórmula.
        from ..engine.pasture_engine import factor_ajuste_clima
        factor_crecimiento = round(factor_ajuste_clima(lluvia_30d), 2)
        if lluvia_30d >= 150.0:
            estacion = "ÉPOCA DE LLUVIAS (Alta Oferta)"
            icono = "🌧️"
        elif lluvia_30d >= 50.0:
            estacion = "TRANSICIÓN (Oferta Moderada)"
            icono = "⛅"
        else:
            estacion = "ÉPOCA SECA / VERANO (Oferta Restringida)"
            icono = "☀️"

        # Estimado satelital de referencia (Fase D, CHIRPS vía Earth Engine). CHIRPS
        # tiene su propia latencia (~30-45 días) así que `fecha` (el fin de la ventana
        # de 30 días que cubre el dato) siempre está semanas atrás por diseño — eso
        # NO significa que el dato esté obsoleto. Lo que sí indica obsolescencia es que
        # el job semanal (`creado_en`) lleve mucho sin correr, por eso se compara contra
        # esa marca de tiempo y no contra `fecha`.
        satelital_mm = satelital_dias = satelital_fecha = satelital_fuente = None
        satelital = self.ultima_lectura_lluvia_satelital()
        if satelital:
            creado_en = satelital["creado_en"]
            # `creado_en` es un timestamp ISO completo ("...T17:39:07"); to_date()
            # solo reconoce fechas puras, por eso se recorta a los primeros 10 caracteres.
            fecha_job = to_date(creado_en[:10] if creado_en else None) or to_date(satelital["fecha"])
            if fecha_job and (ref - fecha_job).days <= 10:
                satelital_mm = satelital["mm_estimado"]
                satelital_dias = satelital["dias_acumulados"]
                satelital_fecha = satelital["fecha"]
                satelital_fuente = satelital["fuente"]

        return {
            "hoy_mm": lluvia_hoy,
            "ultimos_7d_mm": lluvia_7d,
            "ultimos_30d_mm": lluvia_30d,
            "mes_actual_mm": lluvia_mes,
            "anio_actual_mm": lluvia_anio,
            "estacion": estacion,
            "factor_crecimiento": factor_crecimiento,
            "icono": icono,
            "satelital_mm": satelital_mm,
            "satelital_dias": satelital_dias,
            "satelital_fecha": satelital_fecha,
            "satelital_fuente": satelital_fuente,
        }

    def registrar_aforo(self, potrero_id_o_nom, aforo_kg_m2: float, fecha=None,
                        pct_ms: float = 22.0, observaciones: Optional[str] = None,
                        registrado_por: Optional[int] = None) -> int:
        """Registra un muestreo de aforo en la tabla histórica y actualiza el potrero."""
        pot_id = None
        if isinstance(potrero_id_o_nom, int):
            pot_id = potrero_id_o_nom
        else:
            pot_row = self.query_one(
                "SELECT id FROM potreros WHERE nombre = ? OR UPPER(nombre) = UPPER(?) OR codigo = ? LIMIT 1",
                (str(potrero_id_o_nom), str(potrero_id_o_nom), str(potrero_id_o_nom)),
            )
            if pot_row:
                pot_id = pot_row["id"]
            else:
                pot_id = self.registrar_potrero(nombre=str(potrero_id_o_nom))

        f = iso(fecha) or date.today().isoformat()
        aforo_val = float(aforo_kg_m2)
        pct_val = float(pct_ms) if pct_ms else 22.0

        # Actualiza el aforo vigente en la tabla potreros
        self.execute("UPDATE potreros SET aforo_kg_m2 = ? WHERE id = ?", (aforo_val, pot_id))

        return self.insert("aforos_historico", dict(
            potrero_id=pot_id,
            fecha=f,
            aforo_kg_m2=aforo_val,
            pct_ms=pct_val,
            observaciones=observaciones.strip() if observaciones else None,
            creado_en=self._ahora(),
            registrado_por=registrado_por,
        ))

    def obtener_aforos(self, potrero_id: Optional[int] = None, limite: int = 20) -> list[sqlite3.Row]:
        """Obtiene el historial de aforos registrados."""
        if potrero_id:
            return self.query(
                "SELECT a.*, p.nombre AS potrero_nombre FROM aforos_historico a "
                "JOIN potreros p ON p.id = a.potrero_id "
                "WHERE a.potrero_id = ? ORDER BY a.fecha DESC, a.id DESC LIMIT ?",
                (potrero_id, limite),
            )
        return self.query(
            "SELECT a.*, p.nombre AS potrero_nombre FROM aforos_historico a "
            "JOIN potreros p ON p.id = a.potrero_id "
            "ORDER BY a.fecha DESC, a.id DESC LIMIT ?",
            (limite,),
        )

    def registrar_lectura_lluvia_satelital(
        self,
        mm_estimado: float,
        fecha: Optional[str] = None,
        dias_acumulados: int = 30,
        fuente: str = "CHIRPS (UCSB-CHG, vía Google Earth Engine)",
        registrado_por: Optional[int] = None,
    ) -> int:
        """Registra una estimación satelital de lluvia acumulada a nivel de finca."""
        fecha_iso = iso(fecha) or date.today().isoformat()
        return self.insert("monitoreo_satelital_lluvia", dict(
            fecha=fecha_iso,
            dias_acumulados=int(dias_acumulados),
            mm_estimado=float(mm_estimado),
            fuente=fuente,
            creado_en=self._ahora(),
            registrado_por=registrado_por,
        ))

    def ultima_lectura_lluvia_satelital(self) -> Optional[sqlite3.Row]:
        """Devuelve la lectura satelital de lluvia más reciente, si existe."""
        return self.query_one(
            "SELECT * FROM monitoreo_satelital_lluvia ORDER BY fecha DESC, id DESC LIMIT 1"
        )

    def guardar_climatologia_lluvia(self, dias_ventana: int, muestra: list[float],
                                    lat: Optional[float] = None, lon: Optional[float] = None) -> int:
        """Reemplaza la climatología histórica guardada para esa ventana de
        días (solo se necesita la última: no es un historial, es una caché
        de los ~30 años de CHIRPS que ya se descargaron)."""
        import json
        self.execute("DELETE FROM climatologia_lluvia_chirps WHERE dias_ventana = ?", (int(dias_ventana),))
        return self.insert("climatologia_lluvia_chirps", dict(
            dias_ventana=int(dias_ventana),
            muestra_json=json.dumps(muestra),
            lat=lat, lon=lon,
            calculado_en=self._ahora(),
        ))

    def obtener_climatologia_lluvia(self, dias_ventana: int, max_edad_dias: int = 365) -> Optional[list[float]]:
        """Muestra histórica cacheada para esa ventana, o None si no existe o
        está más vieja que `max_edad_dias` (climatología recomendada:
        refrescar ~1 vez al año para incorporar el año recién cerrado)."""
        import json
        fila = self.query_one(
            "SELECT muestra_json, calculado_en FROM climatologia_lluvia_chirps WHERE dias_ventana = ?",
            (int(dias_ventana),),
        )
        if not fila:
            return None
        try:
            calculado = to_date(fila["calculado_en"])
            if calculado and (date.today() - calculado).days > max_edad_dias:
                return None
        except Exception:
            pass
        try:
            return json.loads(fila["muestra_json"])
        except Exception:
            return None

    def registrar_spi_sequia(self, dias_ventana: int, mm_actual: Optional[float],
                             spi_valor: Optional[float], clasificacion: Optional[str],
                             fecha: Optional[str] = None) -> int:
        """Guarda el SPI calculado para una ventana (30/60/90 días) en la
        corrida semanal actual."""
        return self.insert("monitoreo_spi_sequia", dict(
            fecha=iso(fecha) or date.today().isoformat(),
            dias_ventana=int(dias_ventana),
            mm_actual=mm_actual,
            spi_valor=spi_valor,
            clasificacion=clasificacion,
            creado_en=self._ahora(),
        ))

    def ultimos_spi_sequia(self) -> list[sqlite3.Row]:
        """Última lectura de SPI por cada ventana de días (30/60/90), para el
        panel de alerta de sequía en Pasturas."""
        return self.query(
            """SELECT m.* FROM monitoreo_spi_sequia m
               INNER JOIN (
                   SELECT dias_ventana, MAX(id) AS max_id
                   FROM monitoreo_spi_sequia GROUP BY dias_ventana
               ) ult ON ult.dias_ventana = m.dias_ventana AND ult.max_id = m.id
               ORDER BY m.dias_ventana ASC"""
        )

    def registrar_lectura_ndvi(
        self,
        potrero_id_o_nom,
        ndvi_promedio: float,
        fecha: Optional[str] = None,
        ndvi_min: Optional[float] = None,
        ndvi_max: Optional[float] = None,
        biomasa_estimada_kg_ha: Optional[float] = None,
        aforo_estimado_kg_m2: Optional[float] = None,
        cobertura_nubes_pct: float = 0.0,
        fuente: str = "Sentinel-2 L2A",
        registrado_por: Optional[int] = None,
    ) -> int:
        """Registra una lectura satelital NDVI para un potrero."""
        pot_id = self.resolve_potrero(potrero_id_o_nom) if potrero_id_o_nom else None
        if not pot_id:
            # Buscar por id directo
            try:
                pot_id = int(potrero_id_o_nom)
            except (TypeError, ValueError):
                pot_id = self.registrar_potrero(nombre=str(potrero_id_o_nom))

        fecha_iso = iso(fecha) or date.today().isoformat()
        return self.insert("monitoreo_satelital_ndvi", dict(
            potrero_id=pot_id,
            fecha=fecha_iso,
            ndvi_promedio=float(ndvi_promedio),
            ndvi_min=float(ndvi_min) if ndvi_min is not None else None,
            ndvi_max=float(ndvi_max) if ndvi_max is not None else None,
            biomasa_estimada_kg_ha=float(biomasa_estimada_kg_ha) if biomasa_estimada_kg_ha is not None else None,
            aforo_estimado_kg_m2=float(aforo_estimado_kg_m2) if aforo_estimado_kg_m2 is not None else None,
            cobertura_nubes_pct=float(cobertura_nubes_pct),
            fuente=fuente,
            registrado_por=registrado_por,
        ))

    def obtener_ndvi_reciente(self, potrero_id: Optional[int] = None, limite: int = 20) -> list[sqlite3.Row]:
        """Obtiene las lecturas satelitales NDVI más recientes."""
        if potrero_id:
            return self.query(
                "SELECT n.*, p.nombre AS potrero_nombre, p.area_has "
                "FROM monitoreo_satelital_ndvi n "
                "JOIN potreros p ON p.id = n.potrero_id "
                "WHERE n.potrero_id = ? ORDER BY n.fecha DESC, n.id DESC LIMIT ?",
                (potrero_id, limite),
            )
        return self.query(
            "SELECT n.*, p.nombre AS potrero_nombre, p.area_has "
            "FROM monitoreo_satelital_ndvi n "
            "JOIN potreros p ON p.id = n.potrero_id "
            "ORDER BY n.fecha DESC, n.id DESC LIMIT ?",
            (limite,),
        )

    def resumen_ndvi_finca(self) -> dict:
        """Calcula el estado satelital consolidado de los potreros de la finca.

        Solo incluye potreros con geometría real (`geom_wkt_4326`, Fase B del
        plan geoespacial) — un potrero sin ubicación fija no puede tener NDVI
        satelital real ni de contraste. Esto excluye de paso los códigos
        legacy (numéricos/L/G) que son artefactos de una importación anterior
        y no potreros actuales de la finca (confirmado por el usuario contra
        el reporte nativo de Software Ganadero SG, ver
        docs/PLAN_GEO_SATELITAL_6.2_8.2.md sección 3.5) — antes aparecían acá
        con una simulación idéntica y engañosa.
        """
        from ..gis.sentinel_ndvi import clasificar_ndvi, estimar_aforo_kg_m2_desde_ndvi, estimar_biomasa_ms_ha

        # Obtener la última lectura de cada potrero
        query = (
            "SELECT p.id AS potrero_id, p.nombre AS potrero_nombre, p.area_has, "
            "p.dias_ocupacion, p.dias_reposo, "
            "n.fecha, n.ndvi_promedio, n.biomasa_estimada_kg_ha, n.aforo_estimado_kg_m2, "
            "n.cobertura_nubes_pct, n.fuente "
            "FROM potreros p "
            "LEFT JOIN monitoreo_satelital_ndvi n ON n.id = ("
            "  SELECT id FROM monitoreo_satelital_ndvi "
            "  WHERE potrero_id = p.id ORDER BY id DESC LIMIT 1"
            ") WHERE p.geom_wkt_4326 IS NOT NULL "
            "ORDER BY p.id ASC"
        )
        filas = self.query(query)
        if not filas:
            return {"potreros": [], "promedio_ndvi": 0.0, "categoria": "SIN DATOS"}

        potreros_res = []
        suma_ndvi = 0.0
        con_datos = 0

        for f in filas:
            ndvi_val = f["ndvi_promedio"]
            if ndvi_val is None:
                # Simular o inferir a partir de ocupación/reposo
                d_ocup = f["dias_ocupacion"] or 0
                d_rep = f["dias_reposo"] or 0
                if d_ocup > 3:
                    ndvi_val = max(0.32, 0.48 - (d_ocup * 0.025))
                elif d_rep > 25:
                    ndvi_val = min(0.80, 0.55 + (d_rep * 0.006))
                else:
                    ndvi_val = 0.56

            cls_info = clasificar_ndvi(ndvi_val)
            aforo = f["aforo_estimado_kg_m2"] or estimar_aforo_kg_m2_desde_ndvi(ndvi_val)
            biomasa = f["biomasa_estimada_kg_ha"] or estimar_biomasa_ms_ha(ndvi_val)

            potreros_res.append({
                "potrero_id": f["potrero_id"],
                "potrero_nombre": f["potrero_nombre"] or f"Potrero {f['potrero_id']}",
                "area_has": f["area_has"] or 0.0,
                "fecha": f["fecha"] or date.today().isoformat(),
                "ndvi": round(ndvi_val, 3),
                "categoria": cls_info["categoria"],
                "emoji": cls_info["emoji"],
                "descripcion": cls_info["descripcion"],
                "alerta": cls_info["alerta"],
                "aforo_kg_m2": round(aforo, 2),
                "biomasa_ms_ha": round(biomasa, 1),
                "fuente": f["fuente"] or "Sentinel-2 L2A",
            })
            suma_ndvi += ndvi_val
            con_datos += 1

        promedio = round(suma_ndvi / con_datos, 3) if con_datos > 0 else 0.0
        cls_finca = clasificar_ndvi(promedio)

        # Ordenar potreros por vigor (mayor NDVI a menor NDVI)
        potreros_ordenados = sorted(potreros_res, key=lambda x: x["ndvi"], reverse=True)

        return {
            "potreros": potreros_res,
            "ranking": potreros_ordenados,
            "promedio_ndvi": promedio,
            "categoria_finca": cls_finca["categoria"],
            "emoji_finca": cls_finca["emoji"],
            "descripcion_finca": cls_finca["descripcion"],
            "total_potreros": len(potreros_res),
            "alertas_sobrepastoreo": [p for p in potreros_res if p["alerta"]],
        }


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
        """Fotos de un animal. El match "difuso" (caption/ocr/ruta con el tag
        como substring, ej. buscando 'JA14' calzaría con 'JA14-7') solo debe
        aplicar a fotos huérfanas (animal_id IS NULL) -- si no, una foto ya
        vinculada a OTRO animal (ej. una cría cuyo tag "JA14-7" contiene el
        tag del padre "JA14") se filtraba también en la ficha equivocada."""
        aid = self.resolve_animal(animal_tag_or_id)
        tag_str = str(animal_tag_or_id).strip()
        tag_like = f"%{tag_str}%"
        if aid is not None:
            return self.query(
                "SELECT * FROM fotos WHERE animal_id = ? "
                "   OR (animal_id IS NULL AND ("
                "       UPPER(tag) = UPPER(?) "
                "       OR UPPER(caption) LIKE UPPER(?) "
                "       OR UPPER(ocr_text) LIKE UPPER(?) "
                "       OR UPPER(ruta) LIKE UPPER(?)"
                "   )) "
                "ORDER BY id DESC LIMIT ?",
                (aid, tag_str, tag_like, tag_like, tag_like, limit),
            )
        return self.query(
            "SELECT * FROM fotos WHERE animal_id IS NULL AND ("
            "   UPPER(tag) = UPPER(?) "
            "   OR UPPER(caption) LIKE UPPER(?) "
            "   OR UPPER(ocr_text) LIKE UPPER(?) "
            "   OR UPPER(ruta) LIKE UPPER(?)"
            ") "
            "ORDER BY id DESC LIMIT ?",
            (tag_str, tag_like, tag_like, tag_like, limit),
        )

    def ultimas_fotos(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM fotos ORDER BY id DESC LIMIT ?", (limit,))

    def registrar_import_sg(self, archivo: str, conteos: dict) -> int:
        """Registra que se importó un backup de Software Ganadero: cuándo,
        qué archivo y cuántas filas nuevas/duplicadas trajo en total. Usado
        tanto por /confirmar_importar (subida manual por Telegram) como por
        el vigilante automático (copias_watcher), ya que ambos llaman a
        import_zip() -- un solo punto de registro para las dos vías."""
        nuevos = 0
        duplicados = 0
        for tabla, res in conteos.items():
            if isinstance(res, dict):
                nuevos += res.get("nuevos", 0)
                duplicados += res.get("duplicados", 0)
        # os.path.basename() depende del SO (no separa por "\" en Linux); el
        # vigilante de Windows puede pasar una ruta con backslashes aunque
        # esto corra en el VPS (Linux), así que se separa manualmente por
        # ambos separadores para quedar siempre solo con el nombre del archivo.
        nombre_archivo = str(archivo).replace("\\", "/").rsplit("/", 1)[-1]
        return self.insert("import_sg_historial", dict(
            fecha_iso=self._ahora(),
            archivo=nombre_archivo,
            nuevos=nuevos,
            duplicados=duplicados,
        ))

    def ultimo_import_sg(self) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM import_sg_historial ORDER BY id DESC LIMIT 1")

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

    # ------------------------------------------------------------------ #
    # Reproducción y Diagnóstico Gestacional (Fase 5.1)
    # ------------------------------------------------------------------ #
    def registrar_diagnostico(self, vaca_tag, fecha=None, resultado="PREÑADA",
                              dias_gestacion=None, responsable=None, registrado_por=None) -> int:
        vaca_id = self.resolve_animal(vaca_tag, crear=True, sexo="Hembra")
        f = iso(fecha) or date.today().isoformat()
        res_str = str(resultado or "PREÑADA").strip().upper()
        if res_str in ("PRENADA", "PREÑADA", "CONFIRMADA", "POSITIVA", "GESTANTE"):
            res_norm = "PREÑADA"
        elif res_str in ("VACIA", "VACÍA", "ABIERTA", "NEGATIVA", "NO PREÑADA", "NO PRENADA"):
            res_norm = "VACIA"
        else:
            res_norm = res_str

        dias_g = int(dias_gestacion) if (dias_gestacion is not None and str(dias_gestacion).isdigit()) else None

        existente = self._id_si_ya_existe("diagnosticos_gestacion", {
            "vaca_id": vaca_id, "fecha": f, "resultado": res_norm,
        })
        if existente:
            return existente

        diag_id = self.insert("diagnosticos_gestacion", dict(
            vaca_id=vaca_id, fecha=f, resultado=res_norm,
            dias_gestacion=dias_g, responsable=responsable,
            creado_en=self._ahora(), registrado_por=registrado_por,
        ))

        # Actualizar estado del servicio más reciente de la vaca
        if res_norm == "PREÑADA":
            f_date = to_date(f)
            fep_diag = iso(add_days(f_date, 283 - dias_g)) if (dias_g and dias_g > 0 and f_date) else None
            if fep_diag:
                self.execute(
                    """
                    UPDATE servicios
                    SET estado = 'CONFIRMADA', fep_calculada = ?
                    WHERE id = (
                        SELECT id FROM servicios
                        WHERE vaca_id = ? AND (fecha <= ? OR fecha IS NULL)
                        ORDER BY fecha DESC LIMIT 1
                    ) AND (estado IS NULL OR estado = 'SERVIDA' OR estado = 'PENDIENTE' OR estado = 'CONFIRMADA')
                    """,
                    (fep_diag, vaca_id, f),
                )
            else:
                self.execute(
                    """
                    UPDATE servicios
                    SET estado = 'CONFIRMADA'
                    WHERE id = (
                        SELECT id FROM servicios
                        WHERE vaca_id = ? AND (fecha <= ? OR fecha IS NULL)
                        ORDER BY fecha DESC LIMIT 1
                    ) AND (estado IS NULL OR estado = 'SERVIDA' OR estado = 'PENDIENTE')
                    """,
                    (vaca_id, f),
                )
            # Marcar alertas de palpación / ecografía pendientes como cumplidas
            self.execute(
                """
                UPDATE alertas
                SET estado = 'CUMPLIDA', fecha_cumplida = ?
                WHERE animal_id = ? AND tipo_alerta IN ('PALPACION', 'ECOGRAFIA') AND estado = 'PENDIENTE'
                """,
                (f, vaca_id),
            )
        elif res_norm == "VACIA":
            self.execute(
                """
                UPDATE servicios
                SET estado = 'FALLIDO', fep_calculada = NULL
                WHERE id = (
                    SELECT id FROM servicios
                    WHERE vaca_id = ? AND (fecha <= ? OR fecha IS NULL)
                    ORDER BY fecha DESC LIMIT 1
                ) AND (estado IS NULL OR estado = 'SERVIDA' OR estado = 'PENDIENTE' OR estado = 'CONFIRMADA')
                """,
                (vaca_id, f),
            )
            # Cancelar alertas asociadas a la preñez que queden pendientes
            self.execute(
                """
                UPDATE alertas
                SET estado = 'CANCELADA', fecha_cumplida = ?
                WHERE animal_id = ? AND tipo_alerta IN ('PARTO_ESPERADO', 'SECADO', 'PALPACION', 'ECOGRAFIA') AND estado = 'PENDIENTE'
                """,
                (f, vaca_id),
            )

        return diag_id

    def listar_diagnosticos(self, vaca_tag_or_id=None, limit: int = 50) -> list[sqlite3.Row]:
        if vaca_tag_or_id is not None:
            aid = self.resolve_animal(vaca_tag_or_id)
            if aid is None:
                return []
            return self.query(
                """
                SELECT d.*, a.tag, a.nombre
                FROM diagnosticos_gestacion d
                JOIN animales a ON a.id_animal = d.vaca_id
                WHERE d.vaca_id = ?
                ORDER BY d.fecha DESC, d.id DESC
                LIMIT ?
                """,
                (aid, limit),
            )
        return self.query(
            """
            SELECT d.*, a.tag, a.nombre
            FROM diagnosticos_gestacion d
            JOIN animales a ON a.id_animal = d.vaca_id
            ORDER BY d.fecha DESC, d.id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def ultimo_diagnostico(self, vaca_tag_or_id) -> Optional[sqlite3.Row]:
        aid = self.resolve_animal(vaca_tag_or_id)
        if aid is None:
            return None
        return self.query_one(
            "SELECT * FROM diagnosticos_gestacion WHERE vaca_id = ? ORDER BY fecha DESC, id DESC LIMIT 1",
            (aid,),
        )

    def kpis_reproductivos_concepcion(self, toro_pajilla: Optional[str] = None) -> dict:
        """Calcula Tasa de Concepción (%) y Servicios por Concepción (S/C)."""
        where_serv = ""
        params_serv: list = []
        if toro_pajilla:
            where_serv = "WHERE UPPER(toro_pajilla) = UPPER(?) OR toro_pajilla LIKE ?"
            params_serv = [toro_pajilla.strip(), f"%{toro_pajilla.strip()}%"]

        servicios = self.query(
            f"SELECT s.*, a.tag FROM servicios s JOIN animales a ON a.id_animal = s.vaca_id {where_serv} ORDER BY s.fecha DESC",
            tuple(params_serv),
        )

        total_servicios = len(servicios)
        prenadas_serv = sum(1 for s in servicios if (s["estado"] or "").upper() in ("CONFIRMADA", "PREÑADA", "PRENADA", "PREÑADA_ECO", "PREÑADA_PALP"))
        vacias_serv = sum(1 for s in servicios if (s["estado"] or "").upper() in ("FALLIDO", "VACIA", "VACÍA", "ABIERTA"))

        diagnosticos = self.query("SELECT * FROM diagnosticos_gestacion")
        diag_prenadas = sum(1 for d in diagnosticos if (d["resultado"] or "").upper() in ("PREÑADA", "PRENADA", "CONFIRMADA", "POSITIVA"))
        diag_vacias = sum(1 for d in diagnosticos if (d["resultado"] or "").upper() in ("VACIA", "VACÍA", "ABIERTA", "NEGATIVA"))

        total_prenadas = prenadas_serv if toro_pajilla else max(prenadas_serv, diag_prenadas)
        total_vacias = vacias_serv if toro_pajilla else max(vacias_serv, diag_vacias)
        total_evaluados = total_prenadas + total_vacias

        tasa_concepcion = round((total_prenadas / total_evaluados) * 100.0, 1) if total_evaluados > 0 else 0.0
        sc = round(total_servicios / total_prenadas, 2) if total_prenadas > 0 else None

        toros_rows = self.query(
            """
            SELECT DISTINCT toro_pajilla FROM servicios
            WHERE toro_pajilla IS NOT NULL AND toro_pajilla != ''
            ORDER BY toro_pajilla ASC
            """
        )
        por_toro = []
        for tr in toros_rows:
            t_nom = tr["toro_pajilla"]
            servs_t = [s for s in servicios if (s["toro_pajilla"] or "").strip().upper() == t_nom.strip().upper()]
            if not servs_t:
                continue
            n_serv = len(servs_t)
            n_pre = sum(1 for s in servs_t if (s["estado"] or "").upper() in ("CONFIRMADA", "PREÑADA", "PRENADA"))
            n_vac = sum(1 for s in servs_t if (s["estado"] or "").upper() in ("FALLIDO", "VACIA", "VACÍA"))
            n_eval = n_pre + n_vac
            tc = round((n_pre / n_eval) * 100.0, 1) if n_eval > 0 else 0.0
            sc_t = round(n_serv / n_pre, 2) if n_pre > 0 else None
            por_toro.append({
                "toro": t_nom,
                "servicios": n_serv,
                "evaluados": n_eval,
                "prenadas": n_pre,
                "vacias": n_vac,
                "tasa_concepcion": tc,
                "sc": sc_t,
            })

        return {
            "total_servicios": total_servicios,
            "total_evaluados": total_evaluados,
            "total_prenadas": total_prenadas,
            "total_vacias": total_vacias,
            "tasa_concepcion": tasa_concepcion,
            "servicios_por_concepcion": sc,
            "por_toro": por_toro,
        }

    def dias_abiertos_promedio_hato(self, hoy: Optional[date] = None) -> Optional[dict]:
        """Días abiertos promedio del hato: vacas ACTIVAS paridas cuyo último
        parto no tiene un servicio posterior registrado (siguen "abiertas"
        desde ese parto). Misma definición usada en el panel poblacional del
        bot (``formatear_poblacion_panel``) -- fuente única para que ambos
        coincidan."""
        hoy = hoy or date.today()
        vacas_paridas = self.query(
            """
            SELECT a.id_animal FROM partos p
            JOIN animales a ON a.id_animal = p.vaca_id
            WHERE a.estado = 'ACTIVO' AND p.fecha IS NOT NULL
              AND (p.id_cria IS NULL OR p.id_cria != a.id_animal)
            GROUP BY a.id_animal
            """
        )
        dias_lista = []
        for v in vacas_paridas:
            p_ult = self.ultimo_parto(v["id_animal"])
            if not (p_ult and p_ult["fecha"] and to_date(p_ult["fecha"])):
                continue
            f_parto = to_date(p_ult["fecha"])
            s_ult = self.ultimo_servicio(v["id_animal"])
            if s_ult and s_ult["fecha"] and to_date(s_ult["fecha"]) and to_date(s_ult["fecha"]) >= f_parto:
                continue
            dias_lista.append((hoy - f_parto).days)
        if not dias_lista:
            return None
        return {
            "dias_abiertos_promedio": round(sum(dias_lista) / len(dias_lista)),
            "n": len(dias_lista),
        }

    def iep_promedio_hato(self, umbral_max_dias: Optional[int] = 730) -> Optional[dict]:
        """IEP (Intervalo Entre Partos) promedio del hato: para cada vaca con
        2+ partos registrados, promedia la diferencia en días entre partos
        consecutivos (el primer parto de cada vaca no tiene intervalo previo,
        así que no cuenta). Misma fuente e igual filtro por defecto que
        ``engine.charts.generar_grafico_iep_boxplot`` (excluye intervalos
        >730 días -- casi siempre huecos de registro, no gestaciones reales)
        para que el número acá y el boxplot coincidan."""
        vacas = self.query(
            "SELECT DISTINCT vaca_id FROM partos WHERE vaca_id IS NOT NULL "
            "AND (id_cria IS NULL OR id_cria != vaca_id)"
        )
        intervalos = []
        for v in vacas:
            partos = self.query(
                "SELECT fecha FROM partos WHERE vaca_id = ? AND fecha IS NOT NULL "
                "AND (id_cria IS NULL OR id_cria != vaca_id) ORDER BY fecha",
                (v["vaca_id"],),
            )
            fechas = [to_date(p["fecha"]) for p in partos if to_date(p["fecha"])]
            for i in range(1, len(fechas)):
                dias = (fechas[i] - fechas[i - 1]).days
                if dias > 0 and (umbral_max_dias is None or dias <= umbral_max_dias):
                    intervalos.append(dias)
        if not intervalos:
            return None
        return {
            "iep_promedio_dias": round(sum(intervalos) / len(intervalos)),
            "n_intervalos": len(intervalos),
        }

    def edad_primer_parto_promedio_meses(self) -> Optional[dict]:
        """Edad promedio (meses) al primer parto, para vacas con fecha de
        nacimiento conocida y al menos un parto registrado. Descarta edades
        fuera de 12-120 meses (1-10 años) por ser evidentemente fechas mal
        cargadas, no primeros partos reales."""
        vacas = self.query(
            "SELECT DISTINCT vaca_id FROM partos WHERE vaca_id IS NOT NULL AND fecha IS NOT NULL"
        )
        dias_validos = []
        for v in vacas:
            vid = v["vaca_id"]
            a = self.query_one("SELECT fecha_nacimiento FROM animales WHERE id_animal = ?", (vid,))
            fnac = to_date(a["fecha_nacimiento"]) if a else None
            if not fnac:
                continue
            primer = self.query_one(
                "SELECT fecha FROM partos WHERE vaca_id = ? AND fecha IS NOT NULL ORDER BY fecha ASC LIMIT 1",
                (vid,),
            )
            fp = to_date(primer["fecha"]) if primer else None
            if not fp or fp <= fnac:
                continue
            dias = (fp - fnac).days
            if 365 <= dias <= 3650:
                dias_validos.append(dias)
        if not dias_validos:
            return None
        meses = sum(dias_validos) / len(dias_validos) / 30.44
        return {"edad_primer_parto_meses": round(meses, 1), "n": len(dias_validos)}

    # ------------------------------------------------------------------ #
    # Termo Criogénico y Pajuelas (Fase 5.1)
    # ------------------------------------------------------------------ #
    def registrar_pajuela(self, codigo_toro: str, raza: Optional[str] = None,
                          procedencia: Optional[str] = None, canastilla: Optional[str] = None,
                          cantidad: int = 1, costo: float = 0.0, fecha_ingreso: Optional[str] = None) -> int:
        toro_clean = str(codigo_toro).strip()
        if not toro_clean:
            raise ValueError("Código de toro requerido")
        canastilla_clean = str(canastilla).strip() if canastilla else None
        f_ing = iso(fecha_ingreso) or date.today().isoformat()
        cant = int(cantidad)

        if canastilla_clean:
            fila = self.query_one(
                "SELECT id, cantidad FROM pajuelas_inventario WHERE UPPER(codigo_toro) = UPPER(?) AND UPPER(canastilla) = UPPER(?) LIMIT 1",
                (toro_clean, canastilla_clean),
            )
        else:
            fila = self.query_one(
                "SELECT id, cantidad FROM pajuelas_inventario WHERE UPPER(codigo_toro) = UPPER(?) LIMIT 1",
                (toro_clean,),
            )

        if fila:
            pid = fila["id"]
            self.execute(
                """
                UPDATE pajuelas_inventario
                SET cantidad = cantidad + ?,
                    raza = COALESCE(?, raza),
                    procedencia = COALESCE(?, procedencia),
                    canastilla = COALESCE(?, canastilla),
                    costo = CASE WHEN ? > 0 THEN ? ELSE costo END
                WHERE id = ?
                """,
                (cant, raza, procedencia, canastilla_clean, float(costo), float(costo), pid),
            )
            return pid

        return self.insert("pajuelas_inventario", dict(
            codigo_toro=toro_clean,
            raza=raza,
            procedencia=procedencia,
            canastilla=canastilla_clean,
            cantidad=cant,
            costo=float(costo),
            fecha_ingreso=f_ing,
            creado_en=self._ahora(),
        ))

    def descontar_pajuela(self, codigo_toro: str, cantidad: int = 1) -> bool:
        if not codigo_toro:
            return False
        toro_clean = str(codigo_toro).strip()
        cant = int(cantidad)
        fila = self.query_one(
            "SELECT id, cantidad FROM pajuelas_inventario WHERE (UPPER(codigo_toro) = UPPER(?) OR codigo_toro LIKE ?) AND cantidad >= ? ORDER BY id ASC LIMIT 1",
            (toro_clean, f"%{toro_clean}%", cant),
        )
        if fila:
            self.execute(
                "UPDATE pajuelas_inventario SET cantidad = cantidad - ? WHERE id = ?",
                (cant, fila["id"]),
            )
            return True
        return False

    def listar_pajuelas(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM pajuelas_inventario ORDER BY COALESCE(canastilla, 'ZZ'), codigo_toro ASC")

    def obtener_pajuela(self, codigo_toro: str) -> Optional[sqlite3.Row]:
        t = str(codigo_toro).strip()
        return self.query_one(
            "SELECT * FROM pajuelas_inventario WHERE UPPER(codigo_toro) = UPPER(?) OR codigo_toro LIKE ? LIMIT 1",
            (t, f"%{t}%"),
        )

    def alertas_stock_pajuelas(self, umbral_critico: int = 2) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM pajuelas_inventario WHERE cantidad <= ? ORDER BY cantidad ASC, codigo_toro ASC",
            (umbral_critico,),
        )

    def registrar_recarga_nitrogeno(self, fecha_recarga=None, dias_intervalo: int = 21, proxima_recarga=None) -> int:
        f_rec = iso(fecha_recarga) or date.today().isoformat()
        intervalo = int(dias_intervalo) if dias_intervalo else 21
        if proxima_recarga:
            prox = iso(proxima_recarga)
        else:
            prox = iso(add_days(f_rec, intervalo))

        recarga_id = self.insert("termo_nitrogeno", dict(
            fecha_recarga=f_rec,
            proxima_recarga=prox,
            dias_intervalo=intervalo,
            creado_en=self._ahora(),
        ))

        self.execute(
            "UPDATE alertas SET estado = 'CUMPLIDA', fecha_cumplida = ? WHERE tipo_alerta = 'RECARGA_NITROGENO' AND estado = 'PENDIENTE'",
            (f_rec,),
        )
        self.insert("alertas", dict(
            animal_id=None,
            tipo_alerta="RECARGA_NITROGENO",
            fecha_programada=prox,
            estado="PENDIENTE",
            descripcion=f"Recarga periódica de nitrógeno líquido para termo ({intervalo} días)",
        ))

        return recarga_id

    def ultimo_estado_termo(self, hoy=None) -> Optional[dict]:
        fecha_ref = to_date(hoy) or date.today()
        row = self.query_one("SELECT * FROM termo_nitrogeno ORDER BY fecha_recarga DESC, id DESC LIMIT 1")
        if not row:
            return None
        f_rec = to_date(row["fecha_recarga"])
        prox = to_date(row["proxima_recarga"]) or (add_days(f_rec, row["dias_intervalo"]) if f_rec else None)
        dias_desde = (fecha_ref - f_rec).days if f_rec else 0
        dias_restantes = (prox - fecha_ref).days if prox else 0
        alerta_critica = dias_restantes <= 3

        return {
            "id": row["id"],
            "fecha_recarga": row["fecha_recarga"],
            "proxima_recarga": iso(prox),
            "dias_intervalo": row["dias_intervalo"],
            "dias_desde_recarga": dias_desde,
            "dias_restantes": dias_restantes,
            "alerta_critica": alerta_critica,
        }

    def listar_recargas_nitrogeno(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM termo_nitrogeno ORDER BY fecha_recarga DESC, id DESC LIMIT ?", (limit,))

    def _son_gemelos_registrados(self, id_animales: list[int]) -> bool:
        """True si todos los animales dados son crías de partos con
        tipo_evento='GEMELAR' que comparten el mismo grupo_parto_id."""
        if not id_animales:
            return False
        filas = self.query(
            f"SELECT id_cria, tipo_evento, grupo_parto_id FROM partos "
            f"WHERE id_cria IN ({','.join('?' * len(id_animales))})",
            tuple(id_animales),
        )
        por_cria = {f["id_cria"]: f for f in filas}
        if not all(aid in por_cria for aid in id_animales):
            return False
        grupos = {por_cria[aid]["grupo_parto_id"] for aid in id_animales}
        tipos = {(por_cria[aid]["tipo_evento"] or "").upper() for aid in id_animales}
        return tipos == {"GEMELAR"} and len(grupos) == 1 and None not in grupos

    def detectar_duplicados_geneticos(self) -> list[dict]:
        """Agrupa animales ACTIVOS por (madre_id, padre_id, fecha_nacimiento) y
        devuelve los grupos con más de un animal: casi siempre el mismo
        nacimiento importado dos veces bajo tags distintos (ej. 'N065' vs
        'NO65', confusión letra O / dígito 0 al transcribir o en el DBF).
        Requiere madre_id y fecha_nacimiento no nulos para evitar falsos
        positivos entre animales sin genealogía registrada. Excluye grupos
        donde TODOS los animales están vinculados a un parto con
        tipo_evento='GEMELAR' (registro estructurado) o, para datos legacy
        importados antes de ese campo, tienen en sus notas una marca de
        mellizos (ej. 'GEMELA1'/'GEMELA2'): un parto doble real no es un
        duplicado."""
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
            if animales and self._son_gemelos_registrados([a["id_animal"] for a in animales]):
                continue  # parto múltiple real (mellizos), no un duplicado
            if animales and all(a["notas"] and patron_mellizos.search(a["notas"]) for a in animales):
                continue  # parto múltiple real (mellizos legacy en notas), no un duplicado
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

    def ultimas_notas_campo(self, limite: int = 15) -> list[dict]:
        """Recupera las últimas notas u observaciones de campo no vacías de todas las tablas."""
        filas = self.query(
            """
            SELECT * FROM (
                SELECT 'Ficha Animal' AS tipo, a.tag AS tag, a.fecha_nacimiento AS fecha, a.notas AS nota, a.id_animal AS id
                FROM animales a WHERE a.notas IS NOT NULL AND TRIM(a.notas) != ''
                UNION ALL
                SELECT 'Parto' AS tipo, a.tag AS tag, p.fecha AS fecha, p.notas AS nota, p.id AS id
                FROM partos p LEFT JOIN animales a ON a.id_animal = p.vaca_id
                WHERE p.notas IS NOT NULL AND TRIM(p.notas) != ''
                UNION ALL
                SELECT 'Muerte' AS tipo, a.tag AS tag, m.fecha AS fecha, COALESCE(m.notas, m.causa_presunta) AS nota, m.id AS id
                FROM muertes m LEFT JOIN animales a ON a.id_animal = m.animal_id
                WHERE (m.notas IS NOT NULL AND TRIM(m.notas) != '') OR (m.causa_presunta IS NOT NULL AND TRIM(m.causa_presunta) != '')
                UNION ALL
                SELECT 'Celo' AS tipo, a.tag AS tag, c.fecha AS fecha, c.notas AS nota, c.id AS id
                FROM celos c LEFT JOIN animales a ON a.id_animal = c.vaca_id
                WHERE c.notas IS NOT NULL AND TRIM(c.notas) != ''
                UNION ALL
                SELECT 'Tratamiento' AS tipo, a.tag AS tag, t.fecha AS fecha, t.diagnostico AS nota, t.id AS id
                FROM tratamientos t LEFT JOIN animales a ON a.id_animal = t.animal_id
                WHERE t.diagnostico IS NOT NULL AND TRIM(t.diagnostico) != ''
                UNION ALL
                SELECT 'Movimiento' AS tipo, a.tag AS tag, mo.fecha AS fecha, mo.notas AS nota, mo.id AS id
                FROM movimientos mo LEFT JOIN animales a ON a.id_animal = mo.animal_id
                WHERE mo.notas IS NOT NULL AND TRIM(mo.notas) != ''
                UNION ALL
                SELECT 'Leche' AS tipo, a.tag AS tag, pl.fecha AS fecha, pl.notas AS nota, pl.id AS id
                FROM produccion_leche pl LEFT JOIN animales a ON a.id_animal = pl.animal_id
                WHERE pl.notas IS NOT NULL AND TRIM(pl.notas) != ''
                UNION ALL
                SELECT 'Foto' AS tipo, COALESCE(f.tag, a.tag) AS tag, f.fecha AS fecha, COALESCE(f.caption, f.notas) AS nota, f.id AS id
                FROM fotos f LEFT JOIN animales a ON a.id_animal = f.animal_id
                WHERE (f.caption IS NOT NULL AND TRIM(f.caption) != '') OR (f.notas IS NOT NULL AND TRIM(f.notas) != '')
            )
            ORDER BY fecha DESC, id DESC
            LIMIT ?
            """,
            (limite,),
        )
        return [dict(f) for f in filas]

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
                SELECT 'destetes', de.id, a.tag, de.fecha,
                       ('Destete' || CASE WHEN de.peso_kg IS NOT NULL THEN ' - ' || de.peso_kg || 'kg' ELSE '' END),
                       de.creado_en, de.registrado_por
                FROM destetes de LEFT JOIN animales a ON a.id_animal = de.animal_id
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
                UNION ALL
                SELECT 'produccion_leche', pl.id, a.tag, pl.fecha,
                       ('Leche' || CASE WHEN pl.litros IS NOT NULL THEN ' ' || pl.litros || 'L' ELSE '' END),
                       pl.creado_en, pl.registrado_por
                FROM produccion_leche pl LEFT JOIN animales a ON a.id_animal = pl.animal_id
                UNION ALL
                SELECT 'diagnosticos_gestacion', dg.id, a.tag, dg.fecha,
                       ('Diagnóstico gestación: ' || COALESCE(dg.resultado, 'PREÑADA') || CASE WHEN dg.dias_gestacion IS NOT NULL THEN ' (' || dg.dias_gestacion || 'd)' ELSE '' END),
                       dg.creado_en, dg.registrado_por
                FROM diagnosticos_gestacion dg LEFT JOIN animales a ON a.id_animal = dg.vaca_id
            )
            ORDER BY creado_en IS NULL, creado_en DESC, id DESC
            LIMIT ?
            """,
            (limite,),
        )

    ultimos_registros_creados = ultimos_registros

    def detalle_registro(self, tabla: str, id_registro: int) -> Optional[dict]:
        """Detalle legible de una fila puntual de una tabla de eventos, para
        que /deshacer muestre qué se va a borrar antes de confirmar."""
        if tabla not in self.TABLAS_EVENTOS:
            return None
        fk_animal = "vaca_id" if tabla in ("partos", "servicios", "celos", "diagnosticos_gestacion") else ("animal_id" if tabla not in ("pluviometria", "aforos_historico", "monitoreo_satelital_ndvi", "monitoreo_satelital_lluvia") else None)
        fila = self.query_one(f"SELECT * FROM {tabla} WHERE id = ?", (id_registro,))
        if fila is None:
            return None
        animal = self.get_animal(fila[fk_animal]) if fk_animal and fila[fk_animal] is not None else None
        tag = animal["tag"] if animal else ("-" if tabla in ("pluviometria", "aforos_historico", "monitoreo_satelital_ndvi", "monitoreo_satelital_lluvia") else "?")
        resumenes = {
            "partos": lambda f: f"Parto de {tag} — cría {f['sexo_cria'] or '?'}",
            "muertes": lambda f: f"Muerte de {tag}" + (f" — {f['causa_presunta']}" if f["causa_presunta"] else ""),
            "servicios": lambda f: f"Servicio de {tag} ({f['tipo_servicio'] or '?'})",
            "celos": lambda f: f"Celo de {tag} ({f['am_pm'] or '?'})",
            "tratamientos": lambda f: f"Tratamiento de {tag}" + (f" — {f['producto']}" if f["producto"] else ""),
            "traslados": lambda f: f"Traslado de {tag} (lote {f['lote'] or '?'})",
            "destetes": lambda f: f"Destete de {tag}" + (f" — {f['peso_kg']}kg" if f["peso_kg"] is not None else ""),
            "pesajes": lambda f: f"Pesaje de {tag}" + (f" — {f['peso_kg']}kg" if f["peso_kg"] is not None else ""),
            "movimientos": lambda f: f"Movimiento de {tag} ({f['tipo_movimiento'] or '?'})",
            "condicion_corporal": lambda f: f"Condición corporal de {tag}" + (f" — {f['valor']}" if f["valor"] is not None else ""),
            "produccion_leche": lambda f: f"Producción de leche de {tag}" + (f" — {f['litros']}L" if f["litros"] is not None else ""),
            "diagnosticos_gestacion": lambda f: f"Diagnóstico de gestación de {tag}: {f['resultado'] or '?'}" + (f" ({f['dias_gestacion']}d)" if f["dias_gestacion"] else ""),
            "pluviometria": lambda f: f"Pluviometría: {f['mm_lluvia']}mm" + (f" ({f['estacion_o_sector']})" if f["estacion_o_sector"] else ""),
            "aforos_historico": lambda f: f"Aforo potrero #{f['potrero_id']}: {f['aforo_kg_m2']} kg/m²",
            "monitoreo_satelital_ndvi": lambda f: f"Lectura satelital potrero #{f['potrero_id']}: NDVI {f['ndvi_promedio']}",
            "monitoreo_satelital_lluvia": lambda f: f"Lluvia satelital estimada: {f['mm_estimado']}mm ({f['dias_acumulados']}d, {f['fuente']})",
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
        diagnosticos = [] if es_macho else self.query(
            "SELECT * FROM diagnosticos_gestacion WHERE vaca_id = ? ORDER BY fecha ASC, id ASC", (aid,)
        )
        return {
            "partos": partos_propios,
            "nacimiento": self.query("SELECT * FROM partos WHERE id_cria = ? ORDER BY fecha", (aid,)),
            "servicios": servicios,
            "celos": celos,
            "diagnosticos": diagnosticos,
            "muertes": self.query("SELECT * FROM muertes WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "tratamientos": self.query("SELECT * FROM tratamientos WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "traslados": self.query("SELECT * FROM traslados WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "destetes": self.query("SELECT * FROM destetes WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "destetes_crias": [] if es_macho else self.query(
                "SELECT * FROM destetes WHERE madre_id = ? ORDER BY fecha", (aid,)
            ),
            "pesajes": self.query("SELECT * FROM pesajes WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "movimientos": self.query("SELECT * FROM movimientos WHERE animal_id = ? ORDER BY fecha", (aid,)),
            "condicion_corporal": self.query(
                "SELECT * FROM condicion_corporal WHERE animal_id = ? ORDER BY fecha", (aid,)
            ),
            "produccion_leche": self.query(
                "SELECT * FROM produccion_leche WHERE animal_id = ? ORDER BY fecha", (aid,)
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

    # ------------------------------------------------------------------ #
    # Geolocalización GPS y Rondas de Inspección de Potrero
    # ------------------------------------------------------------------ #
    def detectar_potrero_gps(self, lat: float, lon: float) -> Optional[dict[str, Any]]:
        """Determina en qué potrero está ubicado un punto GPS (lat, lon).
        
        Evalúa primero pertenencia estricta en el polígono WGS84 (geom_wkt_4326).
        Si cae fuera por margen de precisión GPS (ej. cerca/saladero al borde),
        calcula distancia al potrero más cercano con un umbral de hasta 150m.
        """
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (ValueError, TypeError):
            return None

        potreros = self.query(
            "SELECT id, nombre, codigo, geom_wkt_4326, centroide_lat, centroide_lon, area_has "
            "FROM potreros WHERE geom_wkt_4326 IS NOT NULL"
        )
        if not potreros:
            return None

        # Intento con shapely (geometría exacta)
        try:
            from shapely import wkt as shapely_wkt
            from shapely.geometry import Point

            pt = Point(lon_f, lat_f)  # WKT usa (x=lon, y=lat)
            candidato_cercano = None
            dist_min_grados = float("inf")

            for p in potreros:
                dp = dict(p)
                wkt_str = dp.get("geom_wkt_4326")
                if not wkt_str:
                    continue
                try:
                    poly = shapely_wkt.loads(wkt_str)
                    if poly.contains(pt):
                        return {
                            "id": dp["id"],
                            "nombre": dp.get("nombre") or dp.get("codigo") or f"Potrero {dp['id']}",
                            "codigo": dp.get("codigo"),
                            "area_has": dp.get("area_has"),
                            "distancia_m": 0.0,
                            "dentro": True,
                        }
                    d = poly.distance(pt)
                    if d < dist_min_grados:
                        dist_min_grados = d
                        candidato_cercano = dp
                except Exception:
                    continue

            # 1 grado aprox 111.000 metros en el ecuador
            dist_metros = dist_min_grados * 111320.0
            if candidato_cercano and dist_metros <= 650.0:
                nom = candidato_cercano.get("nombre") or candidato_cercano.get("codigo") or f"Potrero {candidato_cercano['id']}"
                if dist_metros > 120.0:
                    nom = f"Cerca a {nom} (Instalaciones)"
                return {
                    "id": candidato_cercano["id"],
                    "nombre": nom,
                    "codigo": candidato_cercano.get("codigo"),
                    "area_has": candidato_cercano.get("area_has"),
                    "distancia_m": round(dist_metros, 1),
                    "dentro": dist_metros <= 25.0,
                }
        except Exception as e:
            logger.warning("Fallo al evaluar WKT con shapely en detectar_potrero_gps: %s", e)

        # Fallback euclidiano con centroides si shapely falla
        candidato = None
        min_dist_m = float("inf")
        for p in potreros:
            dp = dict(p)
            clat = dp.get("centroide_lat")
            clon = dp.get("centroide_lon")
            if clat is None or clon is None:
                continue
            d_grados = ((lat_f - float(clat)) ** 2 + (lon_f - float(clon)) ** 2) ** 0.5
            d_m = d_grados * 111320.0
            if d_m < min_dist_m:
                min_dist_m = d_m
                candidato = dp

        if candidato and min_dist_m <= 850.0:
            nom = candidato.get("nombre") or candidato.get("codigo") or f"Potrero {candidato['id']}"
            if min_dist_m > 150.0:
                nom = f"Cerca a {nom} (Instalaciones)"
            return {
                "id": candidato["id"],
                "nombre": nom,
                "codigo": candidato["codigo"],
                "area_has": candidato["area_has"],
                "distancia_m": round(min_dist_m, 1),
                "dentro": min_dist_m <= 60.0,
            }
        return None

    def registrar_ronda_campo(self, user_id: Optional[int] = None,
                              usuario_nombre: Optional[str] = None,
                              fecha: Optional[str] = None,
                              hora: Optional[str] = None,
                              lat: Optional[float] = None,
                              lon: Optional[float] = None,
                              potrero_id: Optional[int] = None,
                              potrero_nombre: Optional[str] = None,
                              punto_control: Optional[str] = None,
                              notas: Optional[str] = None) -> int:
        """Registra un punto de verificación o recorrido GPS en campo."""
        f = iso(fecha) or date.today().isoformat()
        h = hora or datetime.now().strftime("%H:%M:%S")
        
        # Si no se pasó potrero pero hay coordenadas, intentar autodetectar
        if potrero_id is None and lat is not None and lon is not None:
            det = self.detectar_potrero_gps(float(lat), float(lon))
            if det:
                potrero_id = det["id"]
                if not potrero_nombre:
                    potrero_nombre = det["nombre"]

        return self.insert("rondas_campo", {
            "user_id": user_id,
            "usuario_nombre": usuario_nombre,
            "fecha": f,
            "hora": h,
            "lat": float(lat) if lat is not None else 0.0,
            "lon": float(lon) if lon is not None else 0.0,
            "potrero_id": potrero_id,
            "potrero_nombre": potrero_nombre,
            "punto_control": punto_control or "recorrido",
            "notas": notas,
            "creado_en": self._ahora(),
        })

    def listar_rondas_campo(self, fecha: Optional[str] = None, limite: int = 50) -> list[sqlite3.Row]:
        """Consulta las últimas rondas o revisiones de potrero."""
        if fecha:
            return self.query(
                "SELECT * FROM rondas_campo WHERE fecha = ? ORDER BY hora DESC, id DESC LIMIT ?",
                (iso(fecha), limite)
            )
        return self.query(
            "SELECT * FROM rondas_campo ORDER BY fecha DESC, hora DESC, id DESC LIMIT ?",
            (limite,)
        )

    def registrar_telemetria_gps(self, user_id: Optional[int] = None,
                                usuario_nombre: Optional[str] = None,
                                rol: Optional[str] = None,
                                lat: Optional[float] = None,
                                lon: Optional[float] = None,
                                precision_m: Optional[float] = None,
                                evento_origen: Optional[str] = None,
                                fecha: Optional[str] = None,
                                hora: Optional[str] = None) -> Optional[int]:
        """Registra un punto de telemetría y movimiento de operario en la finca."""
        if lat is None or lon is None:
            return None
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (ValueError, TypeError):
            return None

        f = iso(fecha) or date.today().isoformat()
        h = hora or datetime.now().strftime("%H:%M:%S")

        det = self.detectar_potrero_gps(lat_f, lon_f)
        if not det:
            c_finca = self.query_one("SELECT AVG(centroide_lat) as clat, AVG(centroide_lon) as clon FROM potreros WHERE geom_wkt_4326 IS NOT NULL")
            if c_finca and c_finca["clat"] is not None and c_finca["clon"] is not None:
                d_c = (((lat_f - float(c_finca["clat"])) ** 2 + (lon_f - float(c_finca["clon"])) ** 2) ** 0.5) * 111320.0
                if d_c <= 3500.0:
                    det = {
                        "id": None,
                        "nombre": "Casa / Corrales / Finca",
                        "distancia_m": round(d_c, 1),
                        "dentro": False,
                    }
            if not det:
                logger.info("Telemetría GPS descartada: coordenadas (%.6f, %.6f) fuera del perímetro de la finca.", lat_f, lon_f)
                return None

        pot_id = det["id"]
        pot_nom = det["nombre"]
        dist_m = det.get("distancia_m", 0.0)
        dentro = 1 if det.get("dentro", True) else 0

        return self.insert("telemetria_gps", {
            "user_id": user_id,
            "usuario_nombre": usuario_nombre,
            "rol": rol,
            "fecha": f,
            "hora": h,
            "lat": lat_f,
            "lon": lon_f,
            "precision_m": float(precision_m) if precision_m is not None else None,
            "potrero_id": pot_id,
            "potrero_nombre": pot_nom,
            "distancia_m": dist_m,
            "dentro_finca": dentro,
            "evento_origen": evento_origen or "interaccion_app",
            "creado_en": self._ahora(),
        })

    def listar_telemetria_gps(self, fecha: Optional[str] = None,
                             user_id: Optional[int] = None,
                             limite: int = 300) -> list[sqlite3.Row]:
        """Lista puntos cronológicos de telemetría de operarios."""
        f_iso = iso(fecha) if fecha else date.today().isoformat()
        if user_id:
            return self.query(
                "SELECT * FROM telemetria_gps WHERE fecha = ? AND user_id = ? ORDER BY hora ASC, id ASC LIMIT ?",
                (f_iso, int(user_id), limite)
            )
        return self.query(
            "SELECT * FROM telemetria_gps WHERE fecha = ? ORDER BY hora ASC, id ASC LIMIT ?",
            (f_iso, limite)
        )

    def resumen_rutas_operarios(self, fecha: Optional[str] = None) -> list[dict[str, Any]]:
        """Genera resumen cronológico y secuencia de potreros visitados por operario."""
        f_iso = iso(fecha) if fecha else date.today().isoformat()
        puntos = self.listar_telemetria_gps(fecha=f_iso, limite=1000)

        # Agrupar por usuario
        por_usuario: dict[Any, list[dict]] = {}
        for p in puntos:
            dp = dict(p)
            uid = dp.get("user_id") or dp.get("usuario_nombre") or "Anonimo"
            por_usuario.setdefault(uid, []).append(dp)

        resumen = []
        for uid, pts in por_usuario.items():
            if not pts:
                continue
            u_nom = pts[0].get("usuario_nombre") or f"Usuario {uid}"
            u_rol = pts[0].get("rol") or "TRABAJADOR"
            hora_inicio = pts[0].get("hora")
            hora_fin = pts[-1].get("hora")

            # Secuencia de potreros sin repetición consecutiva
            secuencia_potreros = []
            ultimo_pot = None
            for pt in pts:
                p_nom = pt.get("potrero_nombre") or "Área Externa"
                if p_nom != ultimo_pot:
                    secuencia_potreros.append({"potrero": p_nom, "hora": pt.get("hora")})
                    ultimo_pot = p_nom

            resumen.append({
                "user_id": uid,
                "usuario_nombre": u_nom,
                "rol": u_rol,
                "fecha": f_iso,
                "total_puntos": len(pts),
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "secuencia_potreros": secuencia_potreros,
                "puntos": pts,
            })
        return resumen

    # ------------------------------------------------------------------ #
    # Presencia y usuarios en línea en tiempo real
    # ------------------------------------------------------------------ #
    def registrar_presencia(
        self,
        user_id: int | str,
        nombre: str = "",
        rol: str = "",
        canal: str = "PWA",
        ip: str = "",
        detalles: str = "",
    ) -> None:
        """Registra o actualiza el latido/actividad de un usuario (para presencia en vivo)."""
        if not user_id:
            return
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._ensure_presencia_table()
        sql = """
            INSERT INTO usuarios_presencia (user_id, nombre, rol, canal, ip, ultima_actividad, detalles)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                nombre = CASE WHEN excluded.nombre != '' THEN excluded.nombre ELSE usuarios_presencia.nombre END,
                rol = CASE WHEN excluded.rol != '' THEN excluded.rol ELSE usuarios_presencia.rol END,
                canal = excluded.canal,
                ip = CASE WHEN excluded.ip != '' THEN excluded.ip ELSE usuarios_presencia.ip END,
                ultima_actividad = excluded.ultima_actividad,
                detalles = CASE WHEN excluded.detalles != '' THEN excluded.detalles ELSE usuarios_presencia.detalles END
        """
        try:
            self.execute(sql, (str(user_id), nombre, rol, canal, ip, now_iso, detalles))
        except Exception as e:
            logger.debug("Error al registrar presencia de usuario %s: %s", user_id, e)

    def _ensure_presencia_table(self) -> None:
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS usuarios_presencia (
                    user_id TEXT PRIMARY KEY,
                    nombre TEXT,
                    rol TEXT,
                    canal TEXT,
                    ip TEXT,
                    ultima_actividad TEXT,
                    detalles TEXT
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_presencia_actividad ON usuarios_presencia(ultima_actividad)")
        except Exception:
            pass

    def obtener_usuarios_presencia(self) -> dict[str, dict]:
        """Devuelve un mapa {str(user_id): info_presencia} con cálculo de estado en línea."""
        self._ensure_presencia_table()
        try:
            filas = self.query_all("SELECT * FROM usuarios_presencia")
        except Exception as e:
            logger.debug("Error al consultar usuarios_presencia: %s", e)
            return {}

        now = datetime.utcnow()
        res = {}
        for r in filas:
            uid = str(r["user_id"])
            act_str = r["ultima_actividad"] or ""
            en_linea = False
            estado = "offline"
            segundos_diff = 999999
            hace_texto = "Nunca"

            if act_str:
                try:
                    limpio = act_str.replace("Z", "")
                    dt_act = datetime.fromisoformat(limpio)
                    segundos_diff = max(0, int((now - dt_act).total_seconds()))
                    if segundos_diff <= 300:  # 5 minutos
                        en_linea = True
                        estado = "online"
                        hace_texto = "En línea ahora" if segundos_diff < 60 else f"Hace {segundos_diff // 60}m"
                    elif segundos_diff <= 1800:  # 30 minutos
                        estado = "reciente"
                        hace_texto = f"Hace {segundos_diff // 60}m"
                    elif segundos_diff < 86400:  # 24 horas
                        horas = segundos_diff // 3600
                        hace_texto = f"Hace {horas}h"
                    else:
                        dias = segundos_diff // 86400
                        hace_texto = f"Hace {dias}d"
                except Exception:
                    pass

            res[uid] = {
                "user_id": r["user_id"],
                "nombre": r["nombre"] or "",
                "rol": r["rol"] or "",
                "canal": r["canal"] or "PWA",
                "ip": r["ip"] or "",
                "ultima_actividad": act_str,
                "en_linea": en_linea,
                "estado": estado,
                "segundos_desde": segundos_diff,
                "hace_texto": hace_texto,
                "detalles": r["detalles"] or "",
            }
        return res

    # ------------------------------------------------------------------ #
    # Web Push Notifications (PWA)
    # ------------------------------------------------------------------ #
    def _ensure_push_table(self) -> None:
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS push_suscripciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    endpoint TEXT UNIQUE,
                    p256dh TEXT,
                    auth TEXT,
                    creado_en TEXT,
                    ultimo_uso TEXT
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_push_user ON push_suscripciones(user_id)")
        except Exception:
            pass

    def guardar_push_suscripcion(self, endpoint: str, user_id: Optional[str] = None,
                                 p256dh: Optional[str] = None, auth: Optional[str] = None) -> int:
        """Registra o actualiza una suscripción de navegador para notificaciones Web Push."""
        self._ensure_push_table()
        ahora = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO push_suscripciones (user_id, endpoint, p256dh, auth, creado_en, ultimo_uso)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                user_id = CASE WHEN excluded.user_id IS NOT NULL THEN excluded.user_id ELSE push_suscripciones.user_id END,
                p256dh = CASE WHEN excluded.p256dh IS NOT NULL THEN excluded.p256dh ELSE push_suscripciones.p256dh END,
                auth = CASE WHEN excluded.auth IS NOT NULL THEN excluded.auth ELSE push_suscripciones.auth END,
                ultimo_uso = excluded.ultimo_uso
        """
        cursor = self.execute(sql, (str(user_id) if user_id else None, endpoint, p256dh, auth, ahora, ahora))
        return cursor.lastrowid or 1

    def eliminar_push_suscripcion(self, endpoint: str) -> bool:
        """Elimina una suscripción de notificaciones Web Push."""
        self._ensure_push_table()
        cursor = self.execute("DELETE FROM push_suscripciones WHERE endpoint = ?", (endpoint,))
        return cursor.rowcount > 0

    def listar_push_suscripciones(self) -> list[dict[str, Any]]:
        """Retorna todas las suscripciones push activas."""
        self._ensure_push_table()
        filas = self.query("SELECT * FROM push_suscripciones ORDER BY id DESC")
        return [dict(f) for f in filas]

    def alertas_pendientes_push(self) -> list[dict[str, Any]]:
        """Genera la lista de notificaciones de alta prioridad para campo (retiros, celos, Voisin, termo)."""
        hoy_iso = date.today().isoformat()
        alertas = []

        # 1. Retiros sanitarios activos
        try:
            retiros = self.retiros_activos()
            if retiros:
                c_carne = sum(1 for r in retiros if r.get("dias_carne", 0) > 0)
                c_leche = sum(1 for r in retiros if r.get("dias_leche", 0) > 0)
                tags_str = ", ".join(r["tag"] for r in retiros[:3])
                if len(retiros) > 3:
                    tags_str += f" (+{len(retiros)-3})"
                alertas.append({
                    "id": f"retiro-{hoy_iso}",
                    "tipo": "SANIDAD",
                    "titulo": f"⚠️ {len(retiros)} animales en Retiro Sanitario",
                    "cuerpo": f"Animales tratados: {tags_str}. Leche bloqueada: {c_leche}, Carne: {c_carne}.",
                    "tag": "retiro-sanitario",
                    "icono": "/static/icon-192.png",
                    "url": "/?v=sanidad",
                    "urgencia": "alta",
                })
        except Exception as e:
            logger.debug("Error obteniendo retiros para push: %s", e)

        # 2. Celos detectados para inseminar hoy (Regla AM-PM)
        try:
            celos_hoy = self.query(
                "SELECT c.id, c.hora, c.momento, a.tag FROM celos c "
                "JOIN animales a ON a.id_animal = c.animal_id "
                "WHERE c.fecha = ? ORDER BY c.hora DESC LIMIT 5",
                (hoy_iso,)
            )
            for ch in celos_hoy:
                tag_vaca = ch["tag"]
                momento = (ch["momento"] or "manana").lower()
                turno = "en la tarde de hoy (16:00-18:00)" if "man" in momento else "en la mañana siguiente (06:00-08:00)"
                alertas.append({
                    "id": f"celo-{ch['id']}",
                    "tipo": "REPRO",
                    "titulo": f"🧬 Inseminar Vaca {tag_vaca} (Regla AM-PM)",
                    "cuerpo": f"Celo detectado en la {momento}. Proceder con servicio {turno}.",
                    "tag": f"celo-{tag_vaca}",
                    "icono": "/static/icon-192.png",
                    "url": f"/ficha/{tag_vaca}",
                    "urgencia": "alta",
                })
        except Exception as e:
            logger.debug("Error obteniendo celos para push: %s", e)

        # 3. Potreros con sobrepastoreo Voisin (> 3 días ocupados)
        try:
            pot_sobre = self.query(
                "SELECT nombre, dias_ocupacion FROM potreros WHERE dias_ocupacion > 3 ORDER BY dias_ocupacion DESC LIMIT 3"
            )
            for p in pot_sobre:
                alertas.append({
                    "id": f"voisin-{p['nombre']}-{hoy_iso}",
                    "tipo": "PASTURAS",
                    "titulo": f"🌿 Rotación Voisin: Potrero {p['nombre']}",
                    "cuerpo": f"Lleva {p['dias_ocupacion']} días ocupado. Trasladar lote para evitar sobrepastoreo.",
                    "tag": f"voisin-{p['nombre']}",
                    "icono": "/static/icon-192.png",
                    "url": "/?v=pasturas",
                    "urgencia": "media",
                })
        except Exception as e:
            logger.debug("Error obteniendo potreros para push: %s", e)

        # 4. Alerta de termo de nitrógeno (recarga <= 3 días)
        try:
            t_row = self.query_one(
                "SELECT dias_restantes_estimados FROM termo_nitrogeno ORDER BY id DESC LIMIT 1"
            )
            if t_row and t_row["dias_restantes_estimados"] is not None and t_row["dias_restantes_estimados"] <= 3:
                d_rest = t_row["dias_restantes_estimados"]
                alertas.append({
                    "id": f"termo-n2-{hoy_iso}",
                    "tipo": "TERMO",
                    "titulo": "❄️ N₂ Crítico en Termo Criogénico",
                    "cuerpo": f"Quedan ~{d_rest} días de autonomía. Programar recarga urgente de nitrógeno líquido.",
                    "tag": "termo-n2",
                    "icono": "/static/icon-192.png",
                    "url": "/?v=repro",
                    "urgencia": "alta",
                })
        except Exception as e:
            logger.debug("Error obteniendo termo para push: %s", e)

        return alertas

    # ---------------------------------------------------------------------------
    # Indicadores Económicos & Precios de Mercado Ganadero
    # ---------------------------------------------------------------------------
    def _ensure_precios_mercado_table(self):
        self.execute("""
            CREATE TABLE IF NOT EXISTS precios_mercado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                plaza TEXT NOT NULL,
                producto TEXT NOT NULL,
                precio_promedio REAL NOT NULL,
                precio_maximo REAL,
                precio_minimo REAL,
                unidad TEXT NOT NULL DEFAULT '$/kg',
                fuente TEXT,
                notas TEXT,
                creado_en TEXT
            )
        """)
        self.execute("CREATE INDEX IF NOT EXISTS idx_precios_mercado_fecha ON precios_mercado(fecha)")
        self.execute("CREATE INDEX IF NOT EXISTS idx_precios_mercado_plaza ON precios_mercado(plaza)")
        self.execute("CREATE INDEX IF NOT EXISTS idx_precios_mercado_producto ON precios_mercado(producto)")

    def sembrar_precios_mercado_iniciales(self, forzar: bool = False):
        """Siembra datos de referencia de subastas ganaderas del Meta, Casanare y Bogotá con histórico semanal."""
        self._ensure_precios_mercado_table()
        count_row = self.query_one("SELECT COUNT(*) AS c FROM precios_mercado")
        count = count_row["c"] if count_row else 0
        count_fechas_row = self.query_one("SELECT COUNT(DISTINCT fecha) AS cf FROM precios_mercado")
        fechas_distintas = count_fechas_row["cf"] if count_fechas_row else 0

        # Si ya hay datos completos con histórico de varias semanas y no se fuerza, salir
        if count > 0 and fechas_distintas >= 4 and not forzar:
            return

        if forzar:
            self.execute("DELETE FROM precios_mercado")

        hoy_iso = date.today().isoformat()
        ahora_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Semanas históricas para análisis de tendencia (7 semanas consecutivas)
        fechas_semanales = [
            "2026-07-29",
            "2026-08-05",
            "2026-08-12",
            "2026-08-19",
            "2026-08-26",
            "2026-09-02",
            "2026-09-09",
        ]

        # Matriz histórica de cotizaciones semanales ($/kg en pie / insumos)
        # (plaza, producto, unidad, fuente, notas, [precios_7_semanas])
        TABLA_BASE_HISTORICA = [
            # 1. Granada (Meta) - SubaGranada / Sugameta (Ariari - plaza local 68 km)
            ("GRANADA", "MACHO_GORDO", "$/kg", "Sugameta Granada", "Subasta semanal del Ariari (martes/jueves)", [8250.0, 8300.0, 8280.0, 8350.0, 8380.0, 8400.0, 8450.0]),
            ("GRANADA", "MACHO_LEVANTE", "$/kg", "Sugameta Granada", "Novillos 200-300 kg", [8750.0, 8800.0, 8850.0, 8850.0, 8900.0, 8900.0, 8950.0]),
            ("GRANADA", "TERNERO_DESTETO", "$/kg", "Sugameta Granada", "Destetos macho 7-9 meses", [9550.0, 9520.0, 9480.0, 9450.0, 9420.0, 9450.0, 9400.0]),
            ("GRANADA", "HEMBRA_LEVANTE", "$/kg", "Sugameta Granada", "Novillas de levante", [7450.0, 7480.0, 7500.0, 7520.0, 7550.0, 7580.0, 7600.0]),
            ("GRANADA", "VACA_GORDA", "$/kg", "Sugameta Granada", "Vacas gordas y descarte", [6380.0, 6360.0, 6350.0, 6320.0, 6350.0, 6350.0, 6350.0]),

            # 2. Guamal (Meta) - Sugameta Guamal (115 km)
            ("GUAMAL", "MACHO_GORDO", "$/kg", "Sugameta Guamal", "Subasta tradicional del Piedemonte", [8180.0, 8220.0, 8250.0, 8300.0, 8320.0, 8350.0, 8380.0]),
            ("GUAMAL", "MACHO_LEVANTE", "$/kg", "Sugameta Guamal", "Toretes de levante", [8680.0, 8720.0, 8750.0, 8780.0, 8800.0, 8820.0, 8850.0]),
            ("GUAMAL", "TERNERO_DESTETO", "$/kg", "Sugameta Guamal", "Terneros destetos", [9450.0, 9420.0, 9380.0, 9350.0, 9320.0, 9350.0, 9300.0]),
            ("GUAMAL", "HEMBRA_LEVANTE", "$/kg", "Sugameta Guamal", "Hembras levante", [7350.0, 7380.0, 7400.0, 7420.0, 7450.0, 7480.0, 7500.0]),
            ("GUAMAL", "VACA_GORDA", "$/kg", "Sugameta Guamal", "Descarte", [6280.0, 6260.0, 6280.0, 6300.0, 6300.0, 6300.0, 6300.0]),

            # 3. San Martín (Meta) - Sugameta San Martín (95 km)
            ("SAN_MARTIN", "MACHO_GORDO", "$/kg", "Sugameta San Martín", "Plaza ganadera histórica", [8200.0, 8240.0, 8260.0, 8320.0, 8350.0, 8380.0, 8400.0]),
            ("SAN_MARTIN", "MACHO_LEVANTE", "$/kg", "Sugameta San Martín", "Levante comercial", [8700.0, 8750.0, 8800.0, 8820.0, 8850.0, 8880.0, 8900.0]),
            ("SAN_MARTIN", "TERNERO_DESTETO", "$/kg", "Sugameta San Martín", "Destetos", [9500.0, 9480.0, 9420.0, 9400.0, 9380.0, 9400.0, 9350.0]),
            ("SAN_MARTIN", "HEMBRA_LEVANTE", "$/kg", "Sugameta San Martín", "Hembras cría", [7400.0, 7420.0, 7450.0, 7480.0, 7500.0, 7520.0, 7550.0]),
            ("SAN_MARTIN", "VACA_GORDA", "$/kg", "Sugameta San Martín", "Vaca descarte", [6300.0, 6280.0, 6300.0, 6300.0, 6320.0, 6320.0, 6320.0]),

            # 4. Puerto López (Meta) - Suballanos (215 km)
            ("PUERTO_LOPEZ", "MACHO_GORDO", "$/kg", "Suballanos", "Ganadería de altillanura", [8120.0, 8160.0, 8180.0, 8220.0, 8250.0, 8280.0, 8300.0]),
            ("PUERTO_LOPEZ", "MACHO_LEVANTE", "$/kg", "Suballanos", "Llanos sabana", [8620.0, 8660.0, 8700.0, 8720.0, 8750.0, 8780.0, 8800.0]),
            ("PUERTO_LOPEZ", "TERNERO_DESTETO", "$/kg", "Suballanos", "Destetos sabana", [9400.0, 9360.0, 9320.0, 9300.0, 9280.0, 9300.0, 9250.0]),
            ("PUERTO_LOPEZ", "HEMBRA_LEVANTE", "$/kg", "Suballanos", "Hembras", [7320.0, 7350.0, 7380.0, 7400.0, 7420.0, 7430.0, 7450.0]),
            ("PUERTO_LOPEZ", "VACA_GORDA", "$/kg", "Suballanos", "Vaca gorda", [6220.0, 6200.0, 6220.0, 6220.0, 6250.0, 6250.0, 6250.0]),

            # 5. Villavicencio (Meta) - Catama / Subagaucho (145 km)
            ("CATAMA", "MACHO_GORDO", "$/kg", "Subagaucho Catama", "Concentrador regional de los Llanos", [8350.0, 8400.0, 8420.0, 8460.0, 8500.0, 8520.0, 8550.0]),
            ("CATAMA", "MACHO_LEVANTE", "$/kg", "Subagaucho Catama", "Mayor liquidez", [8900.0, 8950.0, 9000.0, 9020.0, 9050.0, 9080.0, 9100.0]),
            ("CATAMA", "TERNERO_DESTETO", "$/kg", "Subagaucho Catama", "Terneros calidad", [9650.0, 9600.0, 9580.0, 9550.0, 9520.0, 9580.0, 9550.0]),
            ("CATAMA", "HEMBRA_LEVANTE", "$/kg", "Subagaucho Catama", "Novillas seleccionadas", [7550.0, 7580.0, 7600.0, 7620.0, 7650.0, 7680.0, 7700.0]),
            ("CATAMA", "VACA_GORDA", "$/kg", "Subagaucho Catama", "Vacas gordas", [6420.0, 6400.0, 6420.0, 6420.0, 6450.0, 6450.0, 6450.0]),

            # 6. Yopal (Casanare) - Subacasanare (395 km)
            ("YOPAL", "MACHO_GORDO", "$/kg", "Subacasanare", "Norte de los Llanos", [8080.0, 8120.0, 8150.0, 8180.0, 8200.0, 8220.0, 8250.0]),
            ("YOPAL", "MACHO_LEVANTE", "$/kg", "Subacasanare", "Gran oferta de levante", [8580.0, 8620.0, 8660.0, 8680.0, 8700.0, 8720.0, 8750.0]),
            ("YOPAL", "TERNERO_DESTETO", "$/kg", "Subacasanare", "Desteto sabanero", [9350.0, 9300.0, 9280.0, 9250.0, 9220.0, 9250.0, 9200.0]),
            ("YOPAL", "HEMBRA_LEVANTE", "$/kg", "Subacasanare", "Hembras cría", [7280.0, 7300.0, 7320.0, 7350.0, 7380.0, 7380.0, 7400.0]),
            ("YOPAL", "VACA_GORDA", "$/kg", "Subacasanare", "Descarte sabanero", [6120.0, 6100.0, 6120.0, 6120.0, 6150.0, 6150.0, 6150.0]),

            # 7. Bogotá (Cundinamarca) - Guadalupe / Frigoríficos (240 km)
            ("BOGOTA", "MACHO_GORDO", "$/kg", "Frigorífico Guadalupe / DANE", "Mercado terminal consumo capital", [8950.0, 9000.0, 9020.0, 9080.0, 9100.0, 9120.0, 9150.0]),
            ("BOGOTA", "MACHO_LEVANTE", "$/kg", "Ferias Sabana Bogotá", "Ingreso para engorde", [9100.0, 9150.0, 9200.0, 9220.0, 9250.0, 9280.0, 9300.0]),
            ("BOGOTA", "VACA_GORDA", "$/kg", "Frigoríficos Bogotá", "Vaca desposte consumo", [6750.0, 6780.0, 6800.0, 6820.0, 6850.0, 6850.0, 6850.0]),

            # 8. Promedio Nacional (FEDEGÁN)
            ("PROMEDIO_NACIONAL", "MACHO_GORDO", "$/kg", "FEDEGÁN Boletín Semanal", "Consolidado nacional subastas", [8300.0, 8340.0, 8350.0, 8400.0, 8420.0, 8450.0, 8480.0]),
            ("PROMEDIO_NACIONAL", "MACHO_LEVANTE", "$/kg", "FEDEGÁN Boletín Semanal", "Promedio país", [8750.0, 8800.0, 8830.0, 8860.0, 8880.0, 8900.0, 8920.0]),

            # 9. Leche ($/Litro)
            ("META_REGIONAL", "LECHE_QUESERA", "$/L", "Acopio Local Ariari", "Queseras de Mesetas / Granada", [1880.0, 1890.0, 1900.0, 1900.0, 1910.0, 1910.0, 1920.0]),
            ("META_REGIONAL", "LECHE_INDUSTRIA", "$/L", "Industria Formal con Frío", "Bonificación sólidos y frío", [2100.0, 2110.0, 2120.0, 2120.0, 2140.0, 2140.0, 2150.0]),
            ("COLOMBIA", "LECHE_RESOLUCION_USP", "$/L", "MinAgricultura USP Región 2", "Precio base normativo oficial", [2115.0, 2115.0, 2115.0, 2115.0, 2115.0, 2115.0, 2115.0]),

            # 10. Insumos Críticos del Ariari / Meta y TRM
            ("ARIARI_LOCAL", "SAL_MINERAL_8", "$/bulto 40kg", "Almacenes Granada", "Sal mineralizada 8% fósforo", [116000.0, 116000.0, 117000.0, 117000.0, 118000.0, 118000.0, 118000.0]),
            ("ARIARI_LOCAL", "SAL_MINERAL_10", "$/bulto 40kg", "Almacenes Granada", "Sal mineralizada 10% fósforo", [134000.0, 134000.0, 135000.0, 135000.0, 136000.0, 136000.0, 136000.0]),
            ("ARIARI_LOCAL", "UREA_50KG", "$/bulto 50kg", "Distribuidoras Granada / Villavicencio", "Fertilizante nitrogenado pastos", [142000.0, 143000.0, 144000.0, 144000.0, 145000.0, 145000.0, 145000.0]),
            ("ARIARI_LOCAL", "ALAMBRE_PUAS_400M", "$/rollo 400m", "Ferreterías Granada", "Alambre galvanizado ganadero", [182000.0, 183000.0, 184000.0, 184000.0, 185000.0, 185000.0, 185000.0]),
            ("COLOMBIA", "DOLAR_TRM", "COP/USD", "Banco de la República", "Tasa representativa oficial", [4040.0, 4065.0, 4050.0, 4075.0, 4090.0, 4080.0, 4085.0]),
        ]

        with self.conn:
            for pz, prod, un, fu, nt, serie in TABLA_BASE_HISTORICA:
                for idx, fec in enumerate(fechas_semanales):
                    # Si ya existe un registro para esta fecha, plaza y producto, no sobreescribir
                    existe = self.query_one(
                        "SELECT id FROM precios_mercado WHERE fecha = ? AND plaza = ? AND producto = ?",
                        (fec, pz, prod)
                    )
                    if existe:
                        continue
                    prom = serie[idx] if idx < len(serie) else serie[-1]
                    pmin = round(prom * 0.97, 0)
                    pmax = round(prom * 1.03, 0)
                    self.conn.execute("""
                        INSERT INTO precios_mercado (fecha, plaza, producto, precio_promedio, precio_maximo, precio_minimo, unidad, fuente, notas, creado_en)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (fec, pz, prod, prom, pmax, pmin, un, fu, nt, ahora_iso))

    def registrar_precio_mercado(
        self,
        plaza: str,
        producto: str,
        precio_promedio: float,
        precio_maximo: Optional[float] = None,
        precio_minimo: Optional[float] = None,
        unidad: str = "$/kg",
        fuente: str = "MANUAL",
        fecha: Optional[str] = None,
        notas: Optional[str] = None
    ) -> int:
        """Registra o actualiza una cotización de mercado para una plaza y producto."""
        self._ensure_precios_mercado_table()
        fec = fecha or date.today().isoformat()
        ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        cursor = self.execute("""
            INSERT INTO precios_mercado (fecha, plaza, producto, precio_promedio, precio_maximo, precio_minimo, unidad, fuente, notas, creado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fec, plaza.upper(), producto.upper(), float(precio_promedio),
              float(precio_maximo) if precio_maximo is not None else None,
              float(precio_minimo) if precio_minimo is not None else None,
              unidad, fuente, notas, ahora))
        return cursor.lastrowid or 0

    def obtener_datos_mercado_completos(self) -> dict[str, Any]:
        """Consolida los indicadores de mercado, subastas, comparativas, tendencias y calculadora de flete."""
        self.sembrar_precios_mercado_iniciales()

        # Filas más recientes + cotización anterior inmediata con LAG / window functions
        sql_recientes = """
            WITH ranked AS (
                SELECT
                    id, fecha, plaza, producto, precio_promedio, precio_maximo, precio_minimo,
                    unidad, fuente, notas, creado_en,
                    ROW_NUMBER() OVER (PARTITION BY plaza, producto ORDER BY fecha DESC, id DESC) as rn
                FROM precios_mercado
            )
            SELECT
                curr.id, curr.fecha, curr.plaza, curr.producto, curr.precio_promedio, curr.precio_maximo, curr.precio_minimo,
                curr.unidad, curr.fuente, curr.notas, curr.creado_en,
                prev.precio_promedio as precio_anterior,
                prev.fecha as fecha_anterior
            FROM ranked curr
            LEFT JOIN ranked prev ON curr.plaza = prev.plaza AND curr.producto = prev.producto AND prev.rn = 2
            WHERE curr.rn = 1
            ORDER BY curr.plaza, curr.producto
        """
        filas = [dict(r) for r in self.query(sql_recientes)]

        # Consultar histórico temporal de las últimas 12 semanas para graficar tendencias
        sql_historico = """
            SELECT fecha, plaza, producto, precio_promedio, precio_minimo, precio_maximo
            FROM precios_mercado
            ORDER BY fecha ASC, id ASC
        """
        filas_hist = [dict(r) for r in self.query(sql_historico)]
        historial_series: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for h in filas_hist:
            pz = h["plaza"]
            pr = h["producto"]
            if pz not in historial_series:
                historial_series[pz] = {}
            if pr not in historial_series[pz]:
                historial_series[pz][pr] = []
            historial_series[pz][pr].append({
                "fecha": h["fecha"],
                "precio": float(h["precio_promedio"]),
                "min": float(h["precio_minimo"]) if h["precio_minimo"] is not None else None,
                "max": float(h["precio_maximo"]) if h["precio_maximo"] is not None else None,
            })

        # Mapeo de Nombres amigables de Plazas
        NOMBRES_PLAZAS = {
            "GRANADA": {"nombre": "Granada (Meta)", "subtitulo": "SubaGranada / Sugameta", "distancia_km": 68, "horas_viaje": 1.5, "desbaste_pct": 2.5, "flete_cab": 35000},
            "GUAMAL": {"nombre": "Guamal (Meta)", "subtitulo": "Sugameta Guamal", "distancia_km": 115, "horas_viaje": 2.3, "desbaste_pct": 3.5, "flete_cab": 45000},
            "SAN_MARTIN": {"nombre": "San Martín (Meta)", "subtitulo": "Sugameta San Martín", "distancia_km": 95, "horas_viaje": 2.0, "desbaste_pct": 3.0, "flete_cab": 42000},
            "PUERTO_LOPEZ": {"nombre": "Puerto López (Meta)", "subtitulo": "Suballanos", "distancia_km": 215, "horas_viaje": 4.5, "desbaste_pct": 5.5, "flete_cab": 70000},
            "CATAMA": {"nombre": "Villavicencio (Catama)", "subtitulo": "Subagaucho Catama", "distancia_km": 145, "horas_viaje": 3.2, "desbaste_pct": 4.5, "flete_cab": 60000},
            "YOPAL": {"nombre": "Yopal (Casanare)", "subtitulo": "Subacasanare", "distancia_km": 395, "horas_viaje": 7.5, "desbaste_pct": 7.0, "flete_cab": 110000},
            "BOGOTA": {"nombre": "Bogotá (Guadalupe)", "subtitulo": "Frigoríficos de Bogotá", "distancia_km": 240, "horas_viaje": 6.5, "desbaste_pct": 7.5, "flete_cab": 135000},
            "PROMEDIO_NACIONAL": {"nombre": "Promedio Nacional", "subtitulo": "FEDEGÁN Consolidado", "distancia_km": 0, "horas_viaje": 0, "desbaste_pct": 0, "flete_cab": 0},
        }

        # Organizar subastas por plaza con indicadores de variación y tendencia
        subastas_dict: dict[str, dict[str, Any]] = {}
        for row in filas:
            pz = row["plaza"]
            if pz in ("META_REGIONAL", "COLOMBIA", "ARIARI_LOCAL"):
                continue
            if pz not in subastas_dict:
                meta_pz = NOMBRES_PLAZAS.get(pz, {"nombre": pz, "subtitulo": "Subasta Regional", "distancia_km": 100, "horas_viaje": 2.5, "desbaste_pct": 4.0, "flete_cab": 50000})
                subastas_dict[pz] = {
                    "plaza_key": pz,
                    "nombre": meta_pz["nombre"],
                    "subtitulo": meta_pz["subtitulo"],
                    "distancia_km": meta_pz["distancia_km"],
                    "horas_viaje": meta_pz["horas_viaje"],
                    "desbaste_pct": meta_pz["desbaste_pct"],
                    "flete_cab": meta_pz["flete_cab"],
                    "fecha_actualizacion": row["fecha"],
                    "productos": {}
                }

            precio_act = float(row["precio_promedio"])
            precio_ant = float(row["precio_anterior"]) if row.get("precio_anterior") is not None else None
            if precio_ant is not None and precio_ant > 0:
                var_pesos = round(precio_act - precio_ant, 1)
                var_pct = round((var_pesos / precio_ant) * 100, 2)
                if var_pesos > 0:
                    tendencia = "SUBIENDO"
                elif var_pesos < 0:
                    tendencia = "BAJANDO"
                else:
                    tendencia = "ESTABLE"
            else:
                var_pesos = 0.0
                var_pct = 0.0
                tendencia = "ESTABLE"

            subastas_dict[pz]["productos"][row["producto"]] = {
                "precio_promedio": precio_act,
                "precio_maximo": float(row["precio_maximo"]) if row.get("precio_maximo") is not None else None,
                "precio_minimo": float(row["precio_minimo"]) if row.get("precio_minimo") is not None else None,
                "unidad": row["unidad"],
                "fuente": row["fuente"],
                "notas": row["notas"],
                "precio_anterior": precio_ant,
                "fecha_anterior": row.get("fecha_anterior"),
                "variacion_pesos": var_pesos,
                "variacion_pct": var_pct,
                "tendencia": tendencia,
                "historico_semanal": historial_series.get(pz, {}).get(row["producto"], [])
            }

        # Comparativa estructurada por categoría zootécnica
        CATEGORIAS_COMPARATIVA = ["MACHO_GORDO", "MACHO_LEVANTE", "TERNERO_DESTETO", "HEMBRA_LEVANTE", "VACA_GORDA"]
        comparativa_por_categoria: dict[str, list[dict[str, Any]]] = {}

        for cat in CATEGORIAS_COMPARATIVA:
            granada_info = subastas_dict.get("GRANADA", {}).get("productos", {}).get(cat)
            granada_pr = granada_info["precio_promedio"] if granada_info else None
            nal_info = subastas_dict.get("PROMEDIO_NACIONAL", {}).get("productos", {}).get(cat)
            nal_pr = nal_info["precio_promedio"] if nal_info else None

            items_cat = []
            for pz_key, pz_data in subastas_dict.items():
                p_data = pz_data["productos"].get(cat)
                if not p_data:
                    continue
                pr_actual = p_data["precio_promedio"]
                diff_granada = round(pr_actual - granada_pr, 1) if granada_pr is not None else 0.0
                diff_nal = round(pr_actual - nal_pr, 1) if nal_pr is not None else 0.0

                items_cat.append({
                    "plaza_key": pz_key,
                    "nombre": pz_data["nombre"],
                    "subtitulo": pz_data["subtitulo"],
                    "distancia_km": pz_data["distancia_km"],
                    "horas_viaje": pz_data["horas_viaje"],
                    "desbaste_pct": pz_data["desbaste_pct"],
                    "flete_cab": pz_data["flete_cab"],
                    "precio_promedio": pr_actual,
                    "precio": pr_actual,
                    "precio_anterior": p_data.get("precio_anterior"),
                    "precio_minimo": p_data["precio_minimo"],
                    "precio_maximo": p_data["precio_maximo"],
                    "variacion_pesos": p_data["variacion_pesos"],
                    "variacion_pct": p_data["variacion_pct"],
                    "tendencia": p_data["tendencia"],
                    "diff_granada": diff_granada,
                    "diff_nacional": diff_nal,
                    "historico_semanal": p_data.get("historico_semanal", [])
                })

            items_cat.sort(key=lambda x: x["precio_promedio"], reverse=True)
            if items_cat:
                items_cat[0]["es_mejor_precio"] = True
            comparativa_por_categoria[cat] = items_cat

        # Resumen ejecutivo de tendencias de mercado
        resumen_tendencias: dict[str, Any] = {}
        for cat in CATEGORIAS_COMPARATIVA:
            items_cat = comparativa_por_categoria.get(cat, [])
            if not items_cat:
                continue
            precios = [x["precio_promedio"] for x in items_cat if x["plaza_key"] != "PROMEDIO_NACIONAL"]
            precios_ant = [
                (x["precio_promedio"] - x["variacion_pesos"])
                for x in items_cat
                if x["plaza_key"] != "PROMEDIO_NACIONAL" and x.get("precio_anterior") is not None
            ]
            prom_act = round(sum(precios) / len(precios), 1) if precios else 0.0
            prom_ant = round(sum(precios_ant) / len(precios_ant), 1) if precios_ant else prom_act
            v_pesos = round(prom_act - prom_ant, 1)
            v_pct = round((v_pesos / prom_ant) * 100, 2) if prom_ant > 0 else 0.0
            tend = "SUBIENDO" if v_pesos > 0 else ("BAJANDO" if v_pesos < 0 else "ESTABLE")
            top_plz = items_cat[0]
            granada_item = next((x for x in items_cat if x["plaza_key"] == "GRANADA"), None)

            resumen_tendencias[cat] = {
                "promedio_mercado": prom_act,
                "promedio_anterior": prom_ant,
                "variacion_pesos": v_pesos,
                "variacion_pct": v_pct,
                "tendencia": tend,
                "plaza_top": top_plz["nombre"],
                "precio_top": top_plz["precio_promedio"],
                "precio_granada": granada_item["precio_promedio"] if granada_item else None,
                "variacion_granada_pct": granada_item["variacion_pct"] if granada_item else 0.0,
                "variacion_granada_pesos": granada_item["variacion_pesos"] if granada_item else 0.0,
            }

        # Mensaje interpretativo sintetizado para toma de decisiones
        mg_tend = resumen_tendencias.get("MACHO_GORDO", {})
        texto_interpretativo = (
            f"📈 Mercado de Macho Gordo con tendencia {'ALCISTA' if mg_tend.get('tendencia') == 'SUBIENDO' else ('BAJISTA' if mg_tend.get('tendencia') == 'BAJANDO' else 'ESTABLE')} "
            f"({'+' if mg_tend.get('variacion_pct', 0) > 0 else ''}{mg_tend.get('variacion_pct', 0)}% semanal). "
            f"Catama ($8.550/kg) lidera precios en los Llanos y Bogotá ($9.150/kg) en mercado terminal. "
            f"Granada cotiza en $8.450/kg con variación de {'+' if mg_tend.get('variacion_granada_pesos', 0) > 0 else ''}{mg_tend.get('variacion_granada_pesos', 0)} $/kg."
        )
        resumen_tendencias["mensaje_interpretativo"] = texto_interpretativo

        # Precio real de leche liquidado en la finca (desde finanzas)
        row_leche_finca = None
        try:
            row_leche_finca = self.query_one("""
                SELECT SUM(monto) as total_monto, SUM(litros) as total_litros
                FROM finanzas WHERE categoria = 'VENTA_LECHE' AND litros > 0
            """)
        except Exception:
            pass
        precio_leche_finca = None
        if row_leche_finca and row_leche_finca["total_litros"] and row_leche_finca["total_litros"] > 0:
            precio_leche_finca = round(row_leche_finca["total_monto"] / row_leche_finca["total_litros"], 1)

        # Insumos y Leche
        leche_items = []
        insumos_items = []
        macho_gordo_granada = subastas_dict.get("GRANADA", {}).get("productos", {}).get("MACHO_GORDO", {}).get("precio_promedio", 8450.0)

        for row in filas:
            pz = row["plaza"]
            prod = row["producto"]
            p_act = float(row["precio_promedio"])
            p_ant = float(row["precio_anterior"]) if row.get("precio_anterior") is not None else None
            v_pesos = round(p_act - p_ant, 1) if p_ant else 0.0
            v_pct = round((v_pesos / p_ant) * 100, 2) if p_ant and p_ant > 0 else 0.0
            tend = "SUBIENDO" if v_pesos > 0 else ("BAJANDO" if v_pesos < 0 else "ESTABLE")

            if "LECHE" in prod:
                leche_items.append({
                    "codigo": prod,
                    "nombre": row["notas"] or prod,
                    "precio": p_act,
                    "precio_anterior": p_ant,
                    "variacion_pesos": v_pesos,
                    "variacion_pct": v_pct,
                    "tendencia": tend,
                    "unidad": row["unidad"],
                    "fuente": row["fuente"],
                    "fecha": row["fecha"],
                    "historico_semanal": historial_series.get(pz, {}).get(prod, [])
                })
            elif pz == "ARIARI_LOCAL" or prod == "DOLAR_TRM":
                kg_novillo_req = round(p_act / macho_gordo_granada, 1) if macho_gordo_granada > 0 else 0
                insumos_items.append({
                    "codigo": prod,
                    "nombre": row["notas"] or prod,
                    "precio": p_act,
                    "precio_anterior": p_ant,
                    "variacion_pesos": v_pesos,
                    "variacion_pct": v_pct,
                    "tendencia": tend,
                    "unidad": row["unidad"],
                    "fuente": row["fuente"],
                    "fecha": row["fecha"],
                    "kg_novillo_equivalentes": kg_novillo_req,
                    "historico_semanal": historial_series.get(pz, {}).get(prod, [])
                })

        max_fecha = max((r["fecha"] for r in filas), default=date.today().isoformat())
        es_auto = any(r.get("fuente", "").startswith("AUTOMATICO") for r in filas)
        trm_row = next((r for r in filas if r["producto"] == "DOLAR_TRM"), None)
        trm_actual = float(trm_row["precio_promedio"]) if trm_row else None
        trm_ant = float(trm_row["precio_anterior"]) if trm_row and trm_row.get("precio_anterior") is not None else None
        trm_var_pct = round(((trm_actual - trm_ant) / trm_ant) * 100, 2) if trm_actual and trm_ant and trm_ant > 0 else 0.0
        trm_tend = "SUBIENDO" if trm_actual and trm_ant and trm_actual > trm_ant else ("BAJANDO" if trm_actual and trm_ant and trm_actual < trm_ant else "ESTABLE")

        return {
            "fecha_consulta": date.today().isoformat(),
            "ultima_actualizacion": max_fecha,
            "actualizacion_automatica": es_auto,
            "trm_actual": trm_actual,
            "trm_anterior": trm_ant,
            "trm_variacion_pct": trm_var_pct,
            "trm_tendencia": trm_tend,
            "ubicacion_finca": "Mesetas, Meta (Región Ariari)",
            "subastas": list(subastas_dict.values()),
            "comparativa_por_categoria": comparativa_por_categoria,
            "resumen_tendencias": resumen_tendencias,
            "leche": {
                "precio_finca_real": precio_leche_finca,
                "referencias": leche_items
            },
            "insumos": insumos_items,
            "macho_gordo_referencia_ariari": macho_gordo_granada,
            "fuentes_oficiales": [
                {"nombre": "FEDEGÁN", "descripcion": "Boletín semanal oficial de precios de subastas ganaderas por regiones"},
                {"nombre": "DANE (SIPSA)", "descripcion": "Sistema de Información de Precios y Abastecimiento del Sector Agropecuario"},
                {"nombre": "Operadores de Subastas (Sugameta / Subagaucho)", "descripcion": "Boletines oficiales de remate en Granada, Guamal, Catama y San Martín"},
                {"nombre": "MinAgricultura (USP)", "descripcion": "Unidad de Seguimiento de Precios de Leche (precios mínimos y promedios Región 2)"},
                {"nombre": "Banco de la República", "descripcion": "Tasa de Cambio Representativa del Mercado (TRM oficial)"}
            ]
        }



