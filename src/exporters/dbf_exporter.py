"""Exportador nativo a formato DBF (dBASE III / Software Ganadero SG).

Permite serializar los datos persistidos en SQLite a las 8 tablas estándar
esperadas por Software Ganadero:
  - hoja.dbf (animales)
  - partos.dbf (partos)
  - celos.dbf (celos)
  - iamn.dbf (servicios/inseminaciones)
  - pesos.dbf (pesajes)
  - potrero.dbf (potreros)
  - traslado.dbf (traslados de potrero)
  - causas.dbf (causas de baja)

Genera un contenedor ZIP ('Datos_Export_YYYYMMDD.Zip') con el 'Dbf.zip' interno,
100% compatible con el formato de respaldo de Software Ganadero TP/SG.
"""
from __future__ import annotations

import csv
import io
import json
import os
import struct
import zipfile
from datetime import date
from typing import Any, Optional, Sequence

from ..db.database import Database
from ..db.models import TABLAS
from ..engine.genetic_engine import normalizar_nombre_raza
from ..importers.dbf_importer import CATALOGO_RAZAS_SG_DEFECTO
from ..utils import to_date


# ---------------------------------------------------------------------------
# Escritor nativo DBF
# ---------------------------------------------------------------------------

class DBFWriter:
    """Serializador nativo de tablas DBF versión III en memoria."""

    def __init__(self, fields: Sequence[tuple[str, str, int, int]]):
        """Inicializa con una lista de tuplas (nombre, tipo, longitud, decimales)."""
        self.fields = fields
        self.records: list[list[Any]] = []

    def add_record(self, record: Sequence[Any]) -> None:
        """Agrega un registro con los valores en el orden de los campos."""
        self.records.append(list(record))

    def write_bytes(self) -> bytes:
        """Genera el contenido binario del archivo DBF III."""
        num_fields = len(self.fields)
        header_len = 32 + 32 * num_fields + 1
        record_len = 1 + sum(f[2] for f in self.fields)
        hoy = date.today()

        out = bytearray()
        # Cabecera principal (32 bytes)
        out += bytes([0x03, hoy.year % 100, hoy.month, hoy.day])
        out += struct.pack("<I", len(self.records))
        out += struct.pack("<H", header_len)
        out += struct.pack("<H", record_len)
        out += b"\x00" * 20

        # Descriptores de campo (32 bytes por campo)
        for (name, ftype, flen, fdec) in self.fields:
            name_bytes = name.encode("latin-1", "replace")[:11].ljust(11, b"\x00")
            out += name_bytes
            out += ftype.encode("ascii")
            out += b"\x00" * 4
            out += bytes([flen, fdec])
            out += b"\x00" * 14

        # Terminador de cabecera
        out += b"\x0d"

        # Registros
        for rec in self.records:
            out += b"\x20"  # 0x20 = registro activo (no borrado)
            for (name, ftype, flen, fdec), val in zip(self.fields, rec, strict=False):
                out += self._format_value(val, ftype, flen, fdec)

        # Fin de archivo dBASE (0x1A)
        out += b"\x1a"
        return bytes(out)

    @staticmethod
    def _format_value(val: Any, ftype: str, flen: int, fdec: int) -> bytes:
        if val is None or val == "":
            return b" " * flen

        if ftype == "D":
            # Fecha YYYYMMDD
            d = to_date(val)
            if d:
                s = f"{d.year:04d}{d.month:02d}{d.day:02d}"
                return s.encode("ascii").ljust(flen, b" ")[:flen]
            return b" " * flen

        if ftype in ("N", "F"):
            try:
                fval = float(val)
                if fdec > 0:
                    s = f"{fval:.{fdec}f}"
                else:
                    s = str(int(round(fval)))
                return s.encode("ascii").rjust(flen, b" ")[:flen]
            except (ValueError, TypeError):
                return b" " * flen

        if ftype == "L":
            # Booleano lógico T/F
            c = "T" if val in (True, "T", "t", "S", "s", 1, "1") else "F"
            return c.encode("ascii").ljust(flen, b" ")[:flen]

        # 'C' (Caracter / Texto)
        s = str(val).strip()
        encoded = s.encode("latin-1", "replace")
        return encoded.ljust(flen, b" ")[:flen]


# ---------------------------------------------------------------------------
# Mapeo y exportación por tabla
# ---------------------------------------------------------------------------

# Raza normalizada -> código SG (CODGR). El primero del catálogo gana
# (ej. Holstein -> "03", aunque "08" Holstein Rojo normalice igual).
_CODIGO_RAZA_SG: dict[str, str] = {}
for _cod, _nom in sorted(CATALOGO_RAZAS_SG_DEFECTO.items()):
    _CODIGO_RAZA_SG.setdefault(normalizar_nombre_raza(_nom), _cod)
_TIPO_RAZA_SG = {"Taurino": "T", "Cebuino": "C", "Indeterminado": "I"}


def _campos_raza_sg(db: Database, a) -> tuple[str, list]:
    """TIPORAZA + 4 pares CODGR/PORGR desde composicion_racial.

    Antes se escribía el texto "1/2 Gyr + 1/2 Holstein" truncado a 10
    caracteres en TIPORAZA y al reimportar la composición quedaba como
    "Gyr 50%" (y 100% Gyr en los cruces). Las razas sin código SG (ej.
    "Desconocida") no se exportan: al reimportar su parte vuelve como
    Desconocida."""
    raza_txt = (a["raza"] or "").strip()
    comp = db.query(
        "SELECT raza, porcentaje FROM composicion_racial WHERE animal_id = ? ORDER BY porcentaje DESC",
        (a["id_animal"],),
    )
    pares: list = []
    for c in comp:
        cod = _CODIGO_RAZA_SG.get(normalizar_nombre_raza(c["raza"] or ""))
        if cod and len(pares) < 4:
            pares.append((cod, float(c["porcentaje"] or 0)))
    celdas: list = []
    for i in range(4):
        cod, pct = pares[i] if i < len(pares) else ("", "")
        celdas.extend([cod, pct])
    tipo = _TIPO_RAZA_SG.get(raza_txt)
    if tipo is None:
        tipo = (comp[0]["raza"] if comp else raza_txt) or ""
    return tipo, celdas


def export_hoja_dbf(db: Database) -> bytes:
    """Exporta tabla de animales a hoja.dbf."""
    fields = [
        ("CODANI", "C", 12, 0),
        ("NOMANI", "C", 20, 0),
        ("SEXO", "C", 1, 0),
        ("TIPORAZA", "C", 10, 0),
        ("FECNACE", "D", 8, 0),
        ("CODPOT", "C", 5, 0),
        ("ESTADO", "C", 5, 0),
        ("OBS", "C", 30, 0),
        ("MADRE", "C", 12, 0),
        ("PADRE", "C", 12, 0),
        ("TIPO", "C", 1, 0),
        ("FECMUERTE", "D", 8, 0),
        ("CAU", "C", 5, 0),
        ("MOTIVO", "C", 30, 0),
        ("CODGR1", "C", 3, 0), ("PORGR1", "N", 6, 2),
        ("CODGR2", "C", 3, 0), ("PORGR2", "N", 6, 2),
        ("CODGR3", "C", 3, 0), ("PORGR3", "N", 6, 2),
        ("CODGR4", "C", 3, 0), ("PORGR4", "N", 6, 2),
    ]
    w = DBFWriter(fields)
    animales = db.query("SELECT * FROM animales ORDER BY id_animal")
    for a in animales:
        sexo = "H" if (a["sexo"] or "").lower().startswith("h") else ("M" if a["sexo"] else "")
        madre = db.get_animal(a["madre_id"])["tag"] if a["madre_id"] else ""
        padre = db.get_animal(a["padre_id"])["tag"] if a["padre_id"] else ""
        potrero = ""
        if a["potrero_id"]:
            prow = db.query_one("SELECT codigo, nombre FROM potreros WHERE id = ?", (a["potrero_id"],))
            if prow:
                potrero = prow["codigo"] or prow["nombre"] or ""

        # Mapeo estado -> TIPO SG
        estado = (a["estado"] or "").upper()
        if estado == "MUERTO":
            tipo = "M"
        elif estado == "VENDIDO":
            tipo = "V"
        elif estado == "TRASLADADO":
            tipo = "T"
        elif estado == "OTRO":
            tipo = "O"
        else:
            tipo = ""

        # Si hay registro de muerte
        muerte = db.query_one("SELECT fecha, causa_presunta, notas FROM muertes WHERE animal_id = ? ORDER BY fecha DESC LIMIT 1", (a["id_animal"],))
        fec_muerte = muerte["fecha"] if muerte else ""
        cau = muerte["causa_presunta"] if muerte else ""
        motivo = muerte["notas"] if muerte else ""
        if muerte and not tipo:
            tipo = "M"

        tipo_raza, celdas_raza = _campos_raza_sg(db, a)
        w.add_record([
            a["tag"] or "",
            a["nombre"] or "",
            sexo,
            tipo_raza,
            a["fecha_nacimiento"] or "",
            potrero,
            "",  # ESTADO SG suele estar vacío
            a["notas"] or "",
            madre,
            padre,
            tipo,
            fec_muerte or "",
            cau or "",
            motivo or "",
            *celdas_raza,
        ])
    return w.write_bytes()


def export_partos_dbf(db: Database) -> bytes:
    """Exporta tabla de partos a partos.dbf."""
    fields = [
        ("CODANI", "C", 12, 0),
        ("FECHA", "D", 8, 0),
        ("CRIA", "C", 1, 0),
        ("HIJO", "C", 12, 0),
        ("PESNAC", "N", 6, 2),
        ("ABORTO", "C", 1, 0),
        ("DETALLE", "C", 30, 0),
    ]
    w = DBFWriter(fields)
    partos = db.query("SELECT * FROM partos WHERE vaca_id IS NOT NULL AND (id_cria IS NULL OR id_cria != vaca_id) ORDER BY fecha")
    for p in partos:
        vaca = db.get_animal(p["vaca_id"])["tag"] if p["vaca_id"] else ""
        cria_tag = db.get_animal(p["id_cria"])["tag"] if p["id_cria"] else ""
        if vaca and cria_tag and vaca == cria_tag:
            continue
        sexo = "H" if (p["sexo_cria"] or "").lower().startswith("h") else ("M" if p["sexo_cria"] else "")
        tipo_evento = (p["tipo_evento"] or "PARTO").upper() if "tipo_evento" in p.keys() else "PARTO"
        aborto = "T" if (p["estado_cria"] or "").upper() == "MUERTO" else ""
        # Software Ganadero solo tiene el booleano ABORTO -- para no perder
        # la granularidad de nuestro catálogo (Gemelar/Reabsorción/
        # Momificación/Maceración/Muerte fetal) en el round-trip, se codifica
        # como prefijo "[TIPO]" en DETALLE; dbf_importer.py lo reconoce al
        # reimportar.
        notas = p["notas"] or ""
        if tipo_evento not in ("PARTO", "ABORTO"):
            notas = f"[{tipo_evento}] {notas}".strip()
        w.add_record([
            vaca,
            p["fecha"] or "",
            sexo,
            cria_tag,
            p["peso_nacimiento"] or "",
            aborto,
            notas[:30],
        ])
    return w.write_bytes()


def export_celos_dbf(db: Database) -> bytes:
    """Exporta tabla de celos a celos.dbf."""
    fields = [
        ("CODANI", "C", 12, 0),
        ("FECHA", "D", 8, 0),
        ("HORA", "C", 8, 0),
        ("DETALLE", "C", 30, 0),
    ]
    w = DBFWriter(fields)
    celos = db.query("SELECT * FROM celos ORDER BY fecha")
    for c in celos:
        vaca = db.get_animal(c["vaca_id"])["tag"] if c["vaca_id"] else ""
        w.add_record([
            vaca,
            c["fecha"] or "",
            c["am_pm"] or "",
            c["notas"] or "",
        ])
    return w.write_bytes()


def export_iamn_dbf(db: Database) -> bytes:
    """Exporta tabla de servicios/inseminaciones a iamn.dbf."""
    fields = [
        ("CODANI", "C", 12, 0),
        ("FECHA", "D", 8, 0),
        ("TIPO", "C", 2, 0),
        ("TORO", "C", 12, 0),
        ("INSEMINA", "C", 20, 0),
        ("EST", "C", 5, 0),
    ]
    w = DBFWriter(fields)
    servicios = db.query("SELECT * FROM servicios ORDER BY fecha")
    for s in servicios:
        vaca = db.get_animal(s["vaca_id"])["tag"] if s["vaca_id"] else ""
        tipo = "MN" if (s["tipo_servicio"] or "").upper() in ("MONTA", "MN") else "IA"
        w.add_record([
            vaca,
            s["fecha"] or "",
            tipo,
            s["toro_pajilla"] or "",
            s["inseminador"] or "",
            s["estado"] or "",
        ])
    return w.write_bytes()


def export_pesos_dbf(db: Database) -> bytes:
    """Exporta tabla de pesajes a pesos.dbf."""
    fields = [
        ("CODANI", "C", 12, 0),
        ("FECHA", "D", 8, 0),
        ("PESO", "N", 7, 2),
        ("EVENTO", "C", 15, 0),
    ]
    w = DBFWriter(fields)
    pesajes = db.query("SELECT * FROM pesajes ORDER BY fecha")
    for p in pesajes:
        tag = db.get_animal(p["animal_id"])["tag"] if p["animal_id"] else ""
        w.add_record([
            tag,
            p["fecha"] or "",
            p["peso_kg"] or "",
            p["evento"] or "",
        ])
    return w.write_bytes()


def export_potrero_dbf(db: Database) -> bytes:
    """Exporta tabla de potreros a potrero.dbf."""
    fields = [
        ("CODPOT", "C", 5, 0),
        ("NOMPOT", "C", 20, 0),
        ("HAS", "N", 8, 2),
        ("KGHA", "N", 8, 2),
        ("DIA_OCU", "N", 4, 0),
        ("FEC_ENT", "D", 8, 0),
        ("FEC_SAL", "D", 8, 0),
        ("PASTO1", "C", 15, 0),
        ("TIPO", "C", 5, 0),
    ]
    w = DBFWriter(fields)
    potreros = db.query("SELECT * FROM potreros ORDER BY id")
    for p in potreros:
        kgha = (p["aforo_kg_m2"] * 10000.0) if p["aforo_kg_m2"] is not None else ""
        w.add_record([
            p["codigo"] or "",
            p["nombre"] or "",
            p["area_has"] or "",
            kgha,
            p["dias_ocupacion"] or "",
            p["fecha_entrada"] or "",
            p["fecha_salida"] or "",
            p["tipo_pasto"] or "",
            "",
        ])
    return w.write_bytes()


def export_traslado_dbf(db: Database) -> bytes:
    """Exporta tabla de traslados a traslado.dbf."""
    fields = [
        ("CODANI", "C", 12, 0),
        ("FECHA", "D", 8, 0),
        ("TIPMOV", "C", 1, 0),
        ("CODPOT", "C", 5, 0),
        ("LOTE", "C", 10, 0),
        ("REGISTROTR", "C", 30, 0),
    ]
    w = DBFWriter(fields)
    traslados = db.query("SELECT * FROM traslados ORDER BY fecha")
    for t in traslados:
        tag = db.get_animal(t["animal_id"])["tag"] if t["animal_id"] else ""
        potrero_cod = ""
        tipmov = "I"
        pid = t["potrero_destino"] or t["potrero_origen"]
        if pid:
            prow = db.query_one("SELECT codigo, nombre FROM potreros WHERE id = ?", (pid,))
            if prow:
                potrero_cod = prow["codigo"] or prow["nombre"] or ""
        if t["potrero_origen"] and not t["potrero_destino"]:
            tipmov = "S"

        w.add_record([
            tag,
            t["fecha"] or "",
            tipmov,
            potrero_cod,
            t["lote"] or "",
            t["motivo"] or "",
        ])
    return w.write_bytes()


def export_causas_dbf(db: Database) -> bytes:
    """Exporta catálogo de causas a causas.dbf."""
    fields = [
        ("CODIGO", "C", 5, 0),
        ("DESC", "C", 30, 0),
    ]
    w = DBFWriter(fields)
    # Obtener causas únicas desde muertes
    causas = db.query("SELECT DISTINCT causa_presunta FROM muertes WHERE causa_presunta IS NOT NULL AND causa_presunta != ''")
    for i, c in enumerate(causas, 1):
        desc = c["causa_presunta"]
        cod = f"{i:02d}"
        w.add_record([cod, desc[:30]])
    return w.write_bytes()


# ---------------------------------------------------------------------------
# Empaquetado completo a ZIP compatible con Software Ganadero
# ---------------------------------------------------------------------------

def export_all_dbfs(db: Database) -> dict[str, bytes]:
    """Genera las 8 tablas DBF requeridas como un diccionario {nombre: bytes}."""
    return {
        "hoja.dbf": export_hoja_dbf(db),
        "partos.dbf": export_partos_dbf(db),
        "celos.dbf": export_celos_dbf(db),
        "iamn.dbf": export_iamn_dbf(db),
        "pesos.dbf": export_pesos_dbf(db),
        "potrero.dbf": export_potrero_dbf(db),
        "traslado.dbf": export_traslado_dbf(db),
        "causas.dbf": export_causas_dbf(db),
    }


def export_zip(db: Database, output_path: Optional[str] = None) -> str:
    """Genera el paquete ZIP con Dbf.zip interno compatible con Software Ganadero.

    Estructura generada:
      Datos_Export_YYYYMMDD.Zip
        └── Dbf.zip
             ├── hoja.dbf
             ├── partos.dbf
             ├── celos.dbf
             ├── iamn.dbf
             ├── pesos.dbf
             ├── potrero.dbf
             ├── traslado.dbf
             └── causas.dbf

    Devuelve la ruta absoluta del archivo ZIP generado.
    """
    hoy = date.today().strftime("%Y%m%d")
    if output_path is None:
        exports_dir = os.path.join(os.getcwd(), "data", "exports")
        os.makedirs(exports_dir, exist_ok=True)
        output_path = os.path.join(exports_dir, f"Datos_Export_{hoy}.Zip")
    else:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    # 1. Crear Dbf.zip interno en memoria
    dbf_files = export_all_dbfs(db)
    inner_buffer = io.BytesIO()
    with zipfile.ZipFile(inner_buffer, "w", zipfile.ZIP_DEFLATED) as inner_zip:
        for name, data in dbf_files.items():
            inner_zip.writestr(name, data)

    inner_bytes = inner_buffer.getvalue()

    # 2. Crear ZIP externo con Dbf.zip dentro
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as outer_zip:
        outer_zip.writestr("Dbf.zip", inner_bytes)

    return output_path


# ---------------------------------------------------------------------------
# Exportación adicional: CSV y JSON
# ---------------------------------------------------------------------------

def export_csv_zip(db: Database, output_path: Optional[str] = None) -> str:
    """Genera un archivo ZIP con todas las tablas del sistema en formato CSV.

    Incluye archivos individuales para cada tabla de TABLAS y un archivo
    consolidado `eventos_bitacora.csv` con el registro cronológico.
    """
    hoy = date.today().strftime("%Y%m%d")
    if output_path is None:
        exports_dir = os.path.join(os.getcwd(), "data", "exports")
        os.makedirs(exports_dir, exist_ok=True)
        output_path = os.path.join(exports_dir, f"bitacora_csv_{hoy}.zip")
    else:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for tabla in TABLAS:
            filas = db.query(f"SELECT * FROM {tabla}")
            buf = io.StringIO()
            writer = csv.writer(buf)
            if filas:
                columnas = list(filas[0].keys())
                writer.writerow(columnas)
                for f in filas:
                    writer.writerow([f[col] for col in columnas])
            else:
                # Escribir solo cabecera si no hay filas
                col_info = db.query(f"PRAGMA table_info({tabla})")
                columnas = [c["name"] for c in col_info]
                writer.writerow(columnas)
            zf.writestr(f"{tabla}.csv", buf.getvalue().encode("utf-8-sig"))

    return output_path


def export_json_zip(db: Database, output_path: Optional[str] = None) -> str:
    """Genera un archivo ZIP con el volcado completo de la bitácora en formato JSON."""
    hoy = date.today().strftime("%Y%m%d")
    if output_path is None:
        exports_dir = os.path.join(os.getcwd(), "data", "exports")
        os.makedirs(exports_dir, exist_ok=True)
        output_path = os.path.join(exports_dir, f"bitacora_json_{hoy}.zip")
    else:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    data = {
        "version": "1.0",
        "fecha_exportacion": date.today().isoformat(),
        "tablas": {},
    }
    for tabla in TABLAS:
        filas = db.query(f"SELECT * FROM {tabla}")
        data["tablas"][tabla] = [dict(f) for f in filas]

    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bitacora.json", json_str.encode("utf-8"))

    return output_path


def parsear_args_exportar(args: Optional[Sequence[str]]) -> Optional[tuple[str, str]]:
    """Interpreta los argumentos de /exportar -> (formato, etiqueta) o None si es inválido.

    - Sin argumentos: DBF (compatible con Software Ganadero SG).
    - "dbf" o "sg": DBF.
    - "csv": CSV.
    - "json": JSON.
    - Cualquier otro caso: None.
    """
    if not args:
        return ("dbf", "dbf")
    if len(args) > 1:
        return None
    arg = str(args[0]).lower().strip()
    if arg in ("dbf", "sg"):
        return ("dbf", "dbf")
    if arg == "csv":
        return ("csv", "csv")
    if arg == "json":
        return ("json", "json")
    return None
