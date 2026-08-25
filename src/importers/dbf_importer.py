"""Parser nativo de tablas DBF (dBASE/FoxPro) e importador a SQLite.

Lee las tablas ``hoja.dbf``, ``partos.dbf``, ``celos.dbf``, ``iamn.dbf``,
``pesos.dbf``, ``potrero.dbf``, ``traslado.dbf`` y ``causas.dbf`` exportadas
por Software Ganadero TP/SG (dentro de ``docs/Datos20260823.Zip``) y siembra
la base de datos SQLite del bot. No requiere bibliotecas externas.
"""
from __future__ import annotations

import struct
import zipfile
from datetime import date
from typing import Iterator, Optional

from ..db.database import Database
from ..engine.growth_engine import gmd
from ..engine.reproductive_engine import fecha_estimada_parto
from ..utils import iso, to_date

DBF_REQUERIDOS = [
    "hoja.dbf", "partos.dbf", "celos.dbf", "iamn.dbf",
    "pesos.dbf", "potrero.dbf", "traslado.dbf", "causas.dbf",
]

# Marcas de campo de Visual FoxPro.
TIPO_FECHA = "D"
TIPO_NUM = ("N", "F")
TIPO_ENTERO = "I"
TIPO_DATETIME = "T"


def _dbf_fecha(raw: str) -> Optional[str]:
    """Convierte una fecha DBF 'YYYYMMDD' a ISO 'YYYY-MM-DD' (o None)."""
    s = (raw or "").strip()
    if len(s) == 8 and s.isdigit():
        d = to_date(s)
        return d.isoformat() if d else None
    return None


class DBFReader:
    """Lector nativo de archivos DBF (dBASE III/IV y Visual FoxPro)."""

    def __init__(self, data: bytes):
        if len(data) < 32:
            raise ValueError("Archivo DBF demasiado corto")
        self.data = data
        self.num_records = struct.unpack("<I", data[4:8])[0]
        self.header_len = struct.unpack("<H", data[8:10])[0]
        self.record_len = struct.unpack("<H", data[10:12])[0]
        self._fields = self._parse_fields()

    @classmethod
    def from_path(cls, path: str) -> "DBFReader":
        with open(path, "rb") as f:
            return cls(f.read())

    def _parse_fields(self) -> list[dict]:
        fields = []
        pos = 32
        while pos < self.header_len:
            if self.data[pos] == 0x0D:
                break
            name = self.data[pos:pos + 11].split(b"\x00")[0].decode("latin-1")
            ftype = chr(self.data[pos + 11])
            flen = self.data[pos + 16]
            fdec = self.data[pos + 17]
            fields.append({"name": name, "type": ftype, "length": flen, "decimals": fdec})
            pos += 32
        return fields

    @property
    def field_names(self) -> list[str]:
        return [f["name"] for f in self._fields]

    def records(self) -> Iterator[dict]:
        base = self.header_len
        for i in range(self.num_records):
            offset = base + i * self.record_len
            raw = self.data[offset:offset + self.record_len]
            if not raw or raw[0:1] in (b"*",):
                continue
            yield self._decode_record(raw)

    def _decode_record(self, raw: bytes) -> dict:
        rec = {}
        p = 1  # saltar el byte de borrado
        for f in self._fields:
            val = raw[p:p + f["length"]]
            p += f["length"]
            rec[f["name"]] = self._decode_value(f, val)
        return rec

    @staticmethod
    def _decode_value(field: dict, val: bytes):
        ftype = field["type"]
        if ftype == TIPO_FECHA:
            return _dbf_fecha(val.decode("latin-1", "replace"))
        if ftype in TIPO_NUM:
            s = val.decode("latin-1", "replace").strip()
            if s == "":
                return None
            try:
                return float(s)
            except ValueError:
                return None
        if ftype == TIPO_ENTERO:
            return struct.unpack("<i", val[:4])[0] if len(val) >= 4 else None
        if ftype == TIPO_DATETIME:
            if len(val) >= 8 and val[:4] != b"\x00\x00\x00\x00":
                jd = struct.unpack("<I", val[:4])[0]
                return _julian_a_iso(jd)
            return None
        if ftype == "L":
            c = val[0:1].decode("latin-1", "replace").upper()
            return c in ("T", "Y")
        # 'C' (char) y 'M' (memo puntero) → texto crudo.
        return val.decode("latin-1", "replace").strip()


def _julian_a_iso(jd: int) -> Optional[str]:
    """Convierte un día juliano (Visual FoxPro) a fecha ISO.

    VFP almacena en los campos ``T`` (DateTime) un día juliano astronómico en
    los primeros 4 bytes (el resto son milisegundos desde medianoche). El
    desfase a ``date.fromordinal`` es ``-1721425``: JD 2451545 == 2000-01-01.
    """
    try:
        d = date.fromordinal(jd - 1721425) if jd > 0 else None
        return d.isoformat() if d else None
    except (ValueError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Importadores por tabla
# ---------------------------------------------------------------------------

def _get_or_create_animal(db: Database, tag: str, **campos) -> Optional[int]:
    if not tag:
        return None
    aid = db.resolve_animal(tag, crear=True, **campos)
    return aid


def import_causas(db: Database, records) -> dict:
    """Devuelve un diccionario código → descripción de causas."""
    causas = {}
    for r in records:
        codigo = (r.get("CODIGO") or "").strip()
        if codigo:
            causas[codigo] = (r.get("DESC") or "").strip()
    return causas


def import_potreros(db: Database, records) -> int:
    n = 0
    for r in records:
        codigo = (r.get("CODPOT") or "").strip()
        nombre = (r.get("NOMPOT") or "").strip()
        if not codigo and not nombre:
            continue
        aforo_kg_m2 = None
        kgha = r.get("KGHA")
        if kgha not in (None, 0):
            aforo_kg_m2 = float(kgha) / 10_000.0
        # 2ª Ley de Voisin (ocupación): DIA_OCU es tiempo de ocupación, no de reposo.
        dias_ocupacion = _entero(r.get("DIA_OCU"))
        # 1ª Ley de Voisin (reposo): días desde la última salida de los animales.
        dias_reposo = None
        fec_sal = r.get("FEC_SAL")
        if fec_sal:
            fs = to_date(fec_sal)
            if fs is not None:
                dias_reposo = max((date.today() - fs).days, 0)
        if db.potrero_id(codigo or nombre) is None:
            db.registrar_potrero(
                nombre=nombre or codigo, codigo=codigo,
                area_has=r.get("HAS"),
                tipo_pasto=(r.get("PASTO1") or r.get("TIPO") or "").strip() or None,
                aforo_kg_m2=aforo_kg_m2,
                fecha_entrada=r.get("FEC_ENT"),
                fecha_salida=fec_sal,
                dias_reposo=dias_reposo,
                dias_ocupacion=dias_ocupacion,
            )
            n += 1
    return n


def _entero(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def import_animales(db: Database, records, causas: dict) -> dict:
    """Siembra animales y muertes; devuelve conteos."""
    tags = []  # para segunda pasada de madre/padre
    muertes = 0
    for r in records:
        tag = (r.get("CODANI") or "").strip()
        if not tag:
            continue
        sexo = {"H": "Hembra", "M": "Macho"}.get((r.get("SEXO") or "").strip(),
                                                  (r.get("SEXO") or "").strip() or None)
        db.registrar_animal(
            tag=tag,
            nombre=(r.get("NOMANI") or "").strip() or None,
            sexo=sexo,
            raza=(r.get("TIPORAZA") or "").strip() or None,
            fecha_nacimiento=r.get("FECNACE"),
            potrero=(r.get("CODPOT") or "").strip() or None,
            estado=(r.get("ESTADO") or "").strip() or None,
            notas=(r.get("OBS") or "").strip() or None,
        )
        tags.append((tag, r))
    # Segunda pasada: enlazar madre/padre ya presentes.
    for tag, r in tags:
        madre = (r.get("MADRE") or "").strip()
        padre = (r.get("PADRE") or "").strip()
        aid = db.animal_id(tag)
        if aid is None:
            continue
        if madre and db.animal_id(madre):
            db.execute("UPDATE animales SET madre_id = ? WHERE id_animal = ?",
                       (db.animal_id(madre), aid))
        if padre and db.animal_id(padre):
            db.execute("UPDATE animales SET padre_id = ? WHERE id_animal = ?",
                       (db.animal_id(padre), aid))
        # Muerte: TIPO == 'M' con fecha de muerte y causa.
        if (r.get("TIPO") or "").strip() == "M" and r.get("FECMUERTE"):
            causa_cod = (r.get("CAU") or "").strip()
            db.registrar_muerte(
                animal_tag=tag, fecha=r.get("FECMUERTE"),
                causa_presunta=causas.get(causa_cod) or causa_cod or None,
                notas=(r.get("MOTIVO") or "").strip() or None,
            )
            muertes += 1
    return {"animales": len(tags), "muertes": muertes}


def import_partos(db: Database, records) -> int:
    n = 0
    for r in records:
        vaca = (r.get("CODANI") or "").strip()
        if not vaca:
            continue
        sexo_cria = {"H": "Hembra", "M": "Macho"}.get((r.get("CRIA") or "").strip())
        estado = "MUERTO" if (r.get("ABORTO") or "").strip() else "VIVO"
        peso = r.get("PESNAC")
        if peso is not None and float(peso) <= 0:
            peso = None
        id_cria_tag = (r.get("HIJO") or "").strip() or None
        if id_cria_tag:
            _get_or_create_animal(db, id_cria_tag, sexo=sexo_cria)
        db.registrar_parto(
            vaca_tag=vaca, fecha=r.get("FECHA"), sexo_cria=sexo_cria,
            estado_cria=estado, peso_nacimiento=peso,
            id_cria_tag=id_cria_tag,
            notas=(r.get("DETALLE") or "").strip() or None,
        )
        n += 1
    return n


def import_celos(db: Database, records) -> int:
    n = 0
    for r in records:
        vaca = (r.get("CODANI") or "").strip()
        if not vaca:
            continue
        hora = r.get("HORA")
        am_pm = _am_pm(hora)
        db.registrar_celo(
            vaca_tag=vaca, fecha=r.get("FECHA"), am_pm=am_pm,
            notas=(r.get("DETALLE") or "").strip() or None,
        )
        n += 1
    return n


def _am_pm(hora) -> Optional[str]:
    if not hora:
        return None
    s = str(hora).upper()
    if "PM" in s:
        return "PM"
    if "AM" in s:
        return "AM"
    # Hora 'HH:MM' (24h)
    import re
    m = re.match(r"(\d{1,2})", s.strip())
    if m:
        return "AM" if int(m.group(1)) < 12 else "PM"
    return None


def import_servicios(db: Database, records) -> int:
    n = 0
    for r in records:
        vaca = (r.get("CODANI") or "").strip()
        if not vaca:
            continue
        tipo = (r.get("TIPO") or "").strip().upper()
        tipo_servicio = "MONTA" if tipo == "MN" else "IA"
        fecha = r.get("FECHA")
        fep = fecha_estimada_parto(fecha)
        db.registrar_servicio(
            vaca_tag=vaca, fecha=fecha, tipo_servicio=tipo_servicio,
            toro_pajilla=(r.get("TORO") or "").strip() or None,
            raza_toro=None,
            inseminador=(r.get("INSEMINA") or "").strip() or None,
            fep_calculada=fep,
            estado=(r.get("EST") or "").strip() or None,
        )
        n += 1
    return n


def import_pesajes(db: Database, records) -> int:
    n = 0
    ultimo: dict[int, tuple[Optional[str], float]] = {}
    for r in records:
        tag = (r.get("CODANI") or "").strip()
        peso = r.get("PESO")
        if not tag or peso is None:
            continue
        fecha = r.get("FECHA")
        aid = _get_or_create_animal(db, tag)
        gmd_calc = None
        if aid is not None and aid in ultimo:
            f_ant, p_ant = ultimo[aid]
            d1, d2 = to_date(f_ant), to_date(fecha)
            if d1 and d2 and (d2 - d1).days > 0:
                gmd_calc = gmd(float(peso), p_ant, (d2 - d1).days)
        if aid is not None:
            ultimo[aid] = (fecha, float(peso))
        db.registrar_pesaje(
            animal_tag=tag, fecha=fecha, peso_kg=float(peso),
            gmd_calculada=gmd_calc,
            evento=(r.get("EVENTO") or "").strip() or None,
        )
        n += 1
    return n


def import_traslados(db: Database, records) -> int:
    n = 0
    for r in records:
        tag = (r.get("CODANI") or "").strip()
        if not tag:
            continue
        tipmov = (r.get("TIPMOV") or "").strip().upper()
        potrero = (r.get("CODPOT") or "").strip() or None
        origen = potrero if tipmov == "S" else None
        destino = potrero if tipmov == "I" else None
        db.registrar_traslado(
            animal_tag=tag, fecha=r.get("FECHA"),
            lote=(r.get("LOTE") or "").strip() or None,
            potrero_origen=origen, potrero_destino=destino,
            motivo=(r.get("REGISTROTR") or "").strip() or None,
        )
        n += 1
    return n


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def import_dbfs(db: Database, dbf_data: dict[str, bytes]) -> dict:
    """Siembra la base de datos a partir de un dict {nombre.dbf: bytes}."""
    lectores = {n: DBFReader(dbf_data[n]) for n in DBF_REQUERIDOS if n in dbf_data}
    conteos: dict = {}

    causas = import_causas(db, lectores["causas.dbf"].records()) if "causas.dbf" in lectores else {}
    if "potrero.dbf" in lectores:
        conteos["potreros"] = import_potreros(db, lectores["potrero.dbf"].records())
    if "hoja.dbf" in lectores:
        conteos.update(import_animales(db, lectores["hoja.dbf"].records(), causas))
    if "partos.dbf" in lectores:
        conteos["partos"] = import_partos(db, lectores["partos.dbf"].records())
    if "celos.dbf" in lectores:
        conteos["celos"] = import_celos(db, lectores["celos.dbf"].records())
    if "iamn.dbf" in lectores:
        conteos["servicios"] = import_servicios(db, lectores["iamn.dbf"].records())
    if "pesos.dbf" in lectores:
        conteos["pesajes"] = import_pesajes(db, lectores["pesos.dbf"].records())
    if "traslado.dbf" in lectores:
        conteos["traslados"] = import_traslados(db, lectores["traslado.dbf"].records())
    return conteos


def import_zip(db: Database, zip_path: str) -> dict:
    """Lee ``Datos20260823.Zip`` (con ``Dbf.zip`` interno) y siembra la DB."""
    with zipfile.ZipFile(zip_path) as outer:
        names = outer.namelist()
        if "Dbf.zip" in names:
            with zipfile.ZipFile(outer.open("Dbf.zip")) as inner:
                dbf_data = {n: inner.read(n) for n in DBF_REQUERIDOS}
        else:
            dbf_data = {n: outer.read(n) for n in DBF_REQUERIDOS if n in names}
    return import_dbfs(db, dbf_data)
