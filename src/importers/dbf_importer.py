"""Parser nativo de tablas DBF (dBASE/FoxPro) e importador a SQLite.

Lee las tablas ``hoja.dbf``, ``partos.dbf``, ``celos.dbf``, ``iamn.dbf``,
``pesos.dbf``, ``potrero.dbf``, ``traslado.dbf``, ``causas.dbf``,
``tactos.dbf``, ``leche.dbf`` y ``destete.dbf`` exportadas por Software
Ganadero TP/SG (dentro de ``docs/Datos20260823.Zip``) y siembra la base de
datos SQLite del bot. No requiere bibliotecas externas.
"""
from __future__ import annotations

import io
import logging
import os
import re
import struct
import zipfile
from datetime import date
from typing import Iterator, Optional

from ..db.database import Database
from ..db.models import TIPOS_EVENTO_PARTO
from ..engine.growth_engine import gmd
from ..engine.genetic_engine import generar_resumen_zootecnico
from ..engine.reproductive_engine import fecha_estimada_parto
from ..utils import hoy, iso, to_date

logger = logging.getLogger(__name__)

DBF_REQUERIDOS = [
    "hoja.dbf", "partos.dbf", "celos.dbf", "iamn.dbf",
    "pesos.dbf", "potrero.dbf", "traslado.dbf", "causas.dbf",
    "tactos.dbf", "leche.dbf", "destete.dbf", "condcorp.dbf",
    "semen.dbf", "termos.dbf", "raza.dbf",
]

CATALOGO_RAZAS_SG_DEFECTO = {
    "01": "Cebú Comercial",
    "02": "Pardo Suizo",
    "03": "Holstein Negro",
    "04": "Gyr",
    "05": "Guzerá",
    "06": "Brahman Gris",
    "07": "Hartón del Valle",
    "08": "Holstein Rojo",
    "09": "Santa Gertrudis",
    "10": "Costeño con Cuernos (CCC)",
    "11": "Jersey",
    "12": "Ayrshire",
    "13": "Angus Rojo",
    "14": "Angus Negro",
    "15": "Simmental",
    "16": "Criolla",
    "17": "Blanco Orejinegro (BON)",
    "18": "Normando",
    "19": "Pardo Colombiano",
    "20": "Sahiwal",
    "21": "Rubio Alemán",
    "22": "Shorthorn",
    "23": "Lucerna",
    "24": "Sanmartinero",
    "25": "Limonero",
    "26": "Velásquez",
    "27": "M.A.Z",
    "28": "Casanare",
    "29": "Nelore",
    "30": "Indubrasil",
    "31": "Brahman Rojo",
    "32": "Chino Santandereano",
    "33": "Romosinuano",
    "34": "Charolais",
    "35": "Cebú Rojo",
    "36": "Limousin",
    "37": "Chianina",
    "38": "Beefmaster",
    "39": "Guernsey",
    "40": "Carora",
    "41": "Piamontés",
    "42": "Hereford",
    "43": "Gelbvieh",
    "44": "Belga Azul",
    "45": "Mono Pinteño",
    "46": "Búfalo",
    "47": "Simmental Americano",
    "48": "Pardo Americano",
    "49": "Pardo Colombiano",
    "50": "Simmental Alemán",
    "51": "Montbéliarde",
    "52": "Girolando",
    "53": "7 Colores",
}

# Marcas de campo de Visual FoxPro.
TIPO_FECHA = "D"
TIPO_NUM = ("N", "F")
TIPO_ENTERO = "I"
TIPO_DATETIME = "T"

# Convención SG (Software Ganadero): el discriminador real del estado de un
# animal en ``hoja.dbf`` es el campo TIPO, no ESTADO (que suele llegar vacío o
# NULL). La regla es: '' (vivo/activo), M (muerto), V (vendido), T (trasladado)
# y O (otro). Cualquier valor desconocido se interpreta como ACTIVO por
# seguridad (default seguro).
TIPO_A_ESTADO = {
    "": "ACTIVO",
    "M": "MUERTO",
    "V": "VENDIDO",
    "T": "TRASLADADO",
    "O": "OTRO",
}

# ---------------------------------------------------------------------------
# Seguridad de Zips: Zip Slip + zip-bomb (H-12)
# ---------------------------------------------------------------------------
# Límites de descompresión validados ANTES de leer cualquier entrada de un
# zip. Calibrados contra los backups reales ``docs/Datos20260823.Zip`` y
# ``docs/Datos20260826.Zip`` (ambos pesan ~80 MB comprimidos y, al ser
# mayormente fotografías JPEG que ya no comprimen, su contenido descomprimido
# queda holgadamente por debajo del tope total de 1 GB, con margen de sobra
# para backups legítimos futuros con más fotos o más histórico).
LIMITE_DESCOMPRIMIDO_TOTAL = 1_000_000_000  # 1 GB por zip
LIMITE_DESCOMPRIMIDO_POR_ARCHIVO = 512 * 1024 * 1024  # 512 MB por entrada


def _validar_zip_seguro(
    zf: zipfile.ZipFile,
    limite_total_descomprimido: int = LIMITE_DESCOMPRIMIDO_TOTAL,
    limite_por_archivo: int = LIMITE_DESCOMPRIMIDO_POR_ARCHIVO,
) -> None:
    """Rechaza un zip inseguro (Zip Slip o zip-bomb) sin leer ninguna entrada.

    Recorre ``zf.infolist()`` y para cada miembro que NO es directorio valida:
    (a) ``os.path.normpath(name)`` no empieza por ``..`` ni contiene ``..``
        como componente de path (ataque Zip Slip clásico);
    (b) el nombre no es una ruta absoluta (ni POSIX ``/`` ni drive Windows
        ``C:\\``/``C:/``);
    (c) el nombre normalizado no escapa del directorio de trabajo actual;
    (d) el tamaño descomprimido declarado de cada miembro y la suma acumulada
        de todos los miembros no exceden los límites (zip-bomb).

    Ante cualquier violación lanza ``ValueError`` con un mensaje claro.
    """
    total_descomprimido = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        nombre = info.filename or ""
        nombre_posix = nombre.replace("\\", "/")

        # (b) Ruta absoluta POSIX ("/etc/passwd") o con drive Windows ("C:...").
        if nombre.startswith(("/", "\\")) or (
            len(nombre) >= 2 and nombre[0].isalpha() and nombre[1] == ":"
        ):
            raise ValueError(f"Zip inseguro: entrada peligrosa '{nombre}' rechazada")

        # (a) '..' como componente de path (../, a/../../etc).
        if ".." in nombre_posix.split("/"):
            raise ValueError(f"Zip inseguro: entrada peligrosa '{nombre}' rechazada")

        # (c) El nombre normalizado no debe escapar del directorio de trabajo.
        normalizado = os.path.normpath(nombre_posix).replace("\\", "/")
        if normalizado == ".." or normalizado.startswith("../"):
            raise ValueError(f"Zip inseguro: entrada peligrosa '{nombre}' rechazada")

        # (d) Límite de tamaño descomprimido por archivo y total (zip-bomb).
        if info.file_size > limite_por_archivo:
            raise ValueError(
                f"Zip inseguro: entrada '{nombre}' demasiado grande "
                f"({info.file_size} bytes descomprimidos)"
            )
        total_descomprimido += info.file_size
        if total_descomprimido > limite_total_descomprimido:
            raise ValueError(
                f"Zip demasiado grande: {total_descomprimido} bytes descomprimidos "
                f"superan el límite de {limite_total_descomprimido}"
            )


def _estado_desde_tipo(tipo, codpot=None) -> str:
    """Deriva el estado del animal desde el campo TIPO de SG (strip + upper)."""
    estado = TIPO_A_ESTADO.get((tipo or "").strip().upper(), "ACTIVO")
    if estado == "ACTIVO" and codpot:
        cod_s = str(codpot).strip()
        # En Software Ganadero histórico, los potreros numéricos 01..23 corresponden
        # a lotes cerrados del histórico 2008-2018. Los potreros activos del hato
        # presente usan nomenclatura con letra (A01..A04, B01..B02, C01..C14).
        if cod_s.isdigit() and int(cod_s) <= 23:
            return "HISTORICO"
    return estado


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


def import_potreros(db: Database, records) -> dict:
    """Siembra potreros de forma idempotente y devuelve conteo de nuevos y duplicados."""
    nuevos = 0
    duplicados = 0
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
            nuevos += 1
        else:
            duplicados += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


def _entero(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def import_animales(db: Database, records, causas: dict, catalogo_razas: Optional[dict] = None) -> dict:
    """Siembra animales y muertes; devuelve conteos con nuevos y duplicados."""
    tags = []  # para segunda pasada de madre/padre
    nuevos_animales = 0
    duplicados_animales = 0
    traslados_detectados = 0
    fecha_import_hoy = iso(hoy())
    cat = catalogo_razas or CATALOGO_RAZAS_SG_DEFECTO

    for r in records:
        tag = (r.get("CODANI") or "").strip()
        if not tag:
            continue
        raw_sex = (r.get("SEXO") or "").strip().upper()
        if raw_sex in ("H", "HEMBRA"):
            sexo = "Hembra"
        elif raw_sex in ("M", "MACHO"):
            sexo = "Macho"
        elif raw_sex:
            sexo = "Macho" if raw_sex.startswith("M") else ("Hembra" if raw_sex.startswith("H") else raw_sex)
        else:
            sexo = None

        existente = db.animal_id(tag)
        estado_previo = None
        potrero_id_previo = None
        if existente is None:
            nuevos_animales += 1
        else:
            duplicados_animales += 1
            fila_previa = db.get_animal(existente)
            if fila_previa:
                estado_previo = fila_previa["estado"]
                potrero_id_previo = fila_previa["potrero_id"]

        codpot = (r.get("CODPOT") or "").strip() or None
        estado_nuevo = _estado_desde_tipo(r.get("TIPO"), codpot=codpot)
        hierro = (r.get("HIE") or "").strip() or None

        # Extracción de composición racial de Software Ganadero
        comp_sg = []
        for i in range(1, 5):
            cod_g = str(r.get(f"CODGR{i}") or "").strip()
            por_g = r.get(f"PORGR{i}")
            if cod_g and por_g is not None:
                try:
                    pct_g = float(por_g)
                except (ValueError, TypeError):
                    pct_g = 0.0
                if pct_g > 0.0:
                    nom_r = cat.get(cod_g) or f"Raza {cod_g}"
                    comp_sg.append({"raza": nom_r, "porcentaje": pct_g})

        if comp_sg:
            raza_val = generar_resumen_zootecnico(comp_sg)
        else:
            tipo_rz = str(r.get("TIPORAZA") or "").strip().upper()
            if tipo_rz == "T":
                raza_val = "Taurino"
            elif tipo_rz == "C":
                raza_val = "Cebuino"
            elif tipo_rz == "I":
                raza_val = "Indeterminado"
            else:
                raza_val = (r.get("TIPORAZA") or "").strip() or None

        aid = db.registrar_animal(
            tag=tag,
            nombre=(r.get("NOMANI") or "").strip() or None,
            sexo=sexo,
            raza=raza_val,
            fecha_nacimiento=r.get("FECNACE"),
            potrero=codpot,
            estado=estado_nuevo,
            notas=(r.get("OBS") or "").strip() or None,
            hierro=hierro,
        )

        if comp_sg and aid is not None:
            db.guardar_composicion_racial(aid, comp_sg)
        # hoja.dbf (este archivo) solo trae el potrero ACTUAL del animal, sin
        # fecha ni historial -- si el mayordomo lo mueve en SG sin pasar por
        # la pantalla de Traslados (traslado.dbf, importado aparte en
        # import_traslados), el cambio queda invisible en "Últimos Eventos"
        # del Tablero aunque Inventario/Mapa ya lo muestren bien (ambos leen
        # animales.potrero_id directo). Se deja constancia igual con fecha
        # aproximada = fecha de esta importación, solo para animales activos
        # que ya tenían un potrero antes (evita ruido en altas nuevas).
        if estado_nuevo == "ACTIVO" and potrero_id_previo is not None and codpot:
            potrero_id_nuevo = db.resolve_potrero(codpot)
            if potrero_id_nuevo is not None and potrero_id_nuevo != potrero_id_previo:
                db.registrar_traslado(
                    animal_tag=tag, fecha=fecha_import_hoy,
                    potrero_origen=potrero_id_previo, potrero_destino=potrero_id_nuevo,
                    motivo="Detectado en import SG (cambio de potrero en hoja.dbf)",
                )
                traslados_detectados += 1
        tags.append((tag, r, estado_previo, estado_nuevo))

    nuevas_muertes = 0
    duplicadas_muertes = 0
    nuevas_ventas = 0
    ventas_fecha_aproximada = 0
    nota_fecha_aprox = (
        "Fecha aproximada: SG (Software Ganadero) marcó este animal como {estado} en el "
        "respaldo importado, pero ese registro no trae la fecha exacta -- se usó la fecha "
        "de esta importación como referencia."
    )
    # Segunda pasada: enlazar madre/padre ya presentes (evitando autorreferencias).
    for tag, r, estado_previo, estado_nuevo in tags:
        madre = (r.get("MADRE") or "").strip()
        padre = (r.get("PADRE") or "").strip()
        aid = db.animal_id(tag)
        if aid is None:
            continue
        if madre and madre.upper() != tag.upper() and db.animal_id(madre):
            m_id = db.animal_id(madre)
            if m_id != aid:
                db.execute("UPDATE animales SET madre_id = ? WHERE id_animal = ? AND (madre_id IS NULL OR madre_id = ?)",
                           (m_id, aid, aid))
        if padre and padre.upper() != tag.upper() and db.animal_id(padre):
            p_id = db.animal_id(padre)
            if p_id != aid:
                db.execute("UPDATE animales SET padre_id = ? WHERE id_animal = ? AND (padre_id IS NULL OR padre_id = ?)",
                           (p_id, aid, aid))
        # FECMUERTE es, pese al nombre, el campo genérico de "fecha de baja"
        # que SG llena para TIPO 'M' (muerte) y también 'V' (venta) -- no es
        # exclusivo de muertes. Confirmado inspeccionando un respaldo real:
        # animales con TIPO='V' traen FECMUERTE poblado con la fecha real de
        # venta (coincide con el informe de indicadores de ventas de SG).
        fecha_baja_raw = r.get("FECMUERTE")

        # Muerte: TIPO == 'M' con fecha de baja y causa.
        if (r.get("TIPO") or "").strip() == "M":
            fecmuerte_raw = fecha_baja_raw
            causa_cod = (r.get("CAU") or "").strip()
            causa = causas.get(causa_cod) or causa_cod or None
            if fecmuerte_raw:
                fec = iso(fecmuerte_raw)
                if fec is not None:
                    existe = db.query_one(
                        "SELECT 1 FROM muertes WHERE animal_id = ? AND fecha = ? LIMIT 1",
                        (aid, fec),
                    )
                else:
                    existe = db.query_one(
                        "SELECT 1 FROM muertes WHERE animal_id = ? AND fecha IS NULL LIMIT 1",
                        (aid,),
                    )
                if existe:
                    duplicadas_muertes += 1
                else:
                    db.registrar_muerte(
                        animal_tag=tag, fecha=fecmuerte_raw,
                        causa_presunta=causa,
                        notas=(r.get("MOTIVO") or "").strip() or None,
                    )
                    nuevas_muertes += 1
            else:
                # SG marcó el animal como muerto pero el respaldo no trae
                # FECMUERTE: sin esto, la muerte nunca queda registrada como
                # evento fechado (solo animales.estado='MUERTO', invisible
                # para cualquier feed/reporte ordenado por fecha).
                existe = db.query_one("SELECT 1 FROM muertes WHERE animal_id = ? LIMIT 1", (aid,))
                if existe:
                    duplicadas_muertes += 1
                else:
                    db.registrar_muerte(
                        animal_tag=tag, fecha=fecha_import_hoy,
                        causa_presunta=causa,
                        notas=(nota_fecha_aprox.format(estado="MUERTO") + " " + (r.get("MOTIVO") or "").strip()).strip(),
                    )
                    nuevas_muertes += 1

        # Venta: TIPO == 'V'. Sin esto la venta solo queda como
        # animales.estado='VENDIDO', sin ningún evento fechado que la haga
        # visible en "Últimos Eventos" ni en reportes por periodo. Usa la
        # fecha real (FECMUERTE) cuando SG la trae; si no, aproxima con la
        # fecha de esta importación.
        # La idempotencia se valida contra la tabla movimientos (no con estado_previo),
        # garantizando que respaldos previos o reimportaciones completen las ventas faltantes.
        if estado_nuevo == "VENDIDO":
            existe_venta = db.query_one(
                "SELECT 1 FROM movimientos WHERE animal_id = ? AND UPPER(tipo_movimiento) = 'VENTA' LIMIT 1",
                (aid,),
            )
            if not existe_venta:
                destino = (r.get("VENDIDOA") or "").strip() or None
                valor = r.get("VALOR") or None
                if fecha_baja_raw:
                    db.registrar_movimiento(
                        animal_tag=tag, fecha=fecha_baja_raw, tipo_movimiento="VENTA",
                        procedencia_destino=destino, precio=valor,
                        notas=(r.get("MOTIVO") or "").strip() or None,
                    )
                else:
                    db.registrar_movimiento(
                        animal_tag=tag, fecha=fecha_import_hoy, tipo_movimiento="VENTA",
                        procedencia_destino=destino, precio=valor,
                        notas=nota_fecha_aprox.format(estado="VENDIDO"),
                    )
                    ventas_fecha_aproximada += 1
                nuevas_ventas += 1
        elif estado_nuevo == "ACTIVO":
            # Si el animal figura como ACTIVO en SG (ej. corrección de un animal
            # que antes estaba truncado o marcado erróneamente como vendido),
            # se eliminan movimientos de VENTA obsoletos para mantener consistencia.
            db.execute(
                "DELETE FROM movimientos WHERE animal_id = ? AND UPPER(tipo_movimiento) = 'VENTA'",
                (aid,),
            )
    return {
        "animales": {
            "nuevos": nuevos_animales, "duplicados": duplicados_animales,
            "ventas_registradas": nuevas_ventas,
            "ventas_fecha_aproximada": ventas_fecha_aproximada,
            "traslados_detectados": traslados_detectados,
        },
        "muertes": {"nuevos": nuevas_muertes, "duplicados": duplicadas_muertes},
    }


def import_partos(db: Database, records) -> dict:
    """Siembra partos deduplicando por vaca_id + fecha (+ id_cria)."""
    nuevos = 0
    duplicados = 0
    for r in records:
        vaca = (r.get("CODANI") or "").strip()
        if not vaca:
            continue
        id_cria_tag = (r.get("HIJO") or "").strip() or None

        # Protección autorreferencia: una cría no puede ser su propia madre
        if id_cria_tag and vaca.upper() == id_cria_tag.upper():
            continue

        raw_sexo = (r.get("CRIA") or "").strip().upper()
        if raw_sexo in ("M", "MACHO"):
            sexo_cria = "Macho"
        elif raw_sexo in ("H", "HEMBRA"):
            sexo_cria = "Hembra"
        elif raw_sexo:
            sexo_cria = "Macho" if raw_sexo.startswith("M") else ("Hembra" if raw_sexo.startswith("H") else raw_sexo)
        else:
            sexo_cria = None

        estado = "MUERTO" if (r.get("ABORTO") or "").strip() else "VIVO"
        detalle = (r.get("DETALLE") or "").strip()
        # Software Ganadero solo trae el booleano ABORTO; el catálogo fino
        # (Gemelar/Reabsorción/Momificación/Maceración/Muerte fetal) viaja
        # codificado como prefijo "[TIPO] " en DETALLE cuando el backup viene
        # de nuestro propio exportador (ver dbf_exporter.export_partos_dbf).
        m_tipo = re.match(r"^\[([A-Z_]+)\]\s*(.*)$", detalle)
        if m_tipo and m_tipo.group(1) in TIPOS_EVENTO_PARTO:
            tipo_evento = m_tipo.group(1)
            detalle = m_tipo.group(2)
        elif estado == "MUERTO":
            tipo_evento = "ABORTO"
        elif re.search(r"gemel|melliz", detalle, re.IGNORECASE):
            tipo_evento = "GEMELAR"
        else:
            tipo_evento = "PARTO"
        peso = r.get("PESNAC")
        if peso is not None and float(peso) <= 0:
            peso = None

        fec = iso(r.get("FECHA"))

        # Resolver tag -> id ANTES del chequeo
        vaca_id = db.resolve_animal(vaca, crear=True, sexo="Hembra")
        id_cria = db.resolve_animal(id_cria_tag, crear=True, sexo=sexo_cria, fecha_nacimiento=fec) if id_cria_tag else None

        if id_cria is not None and vaca_id is not None and id_cria == vaca_id:
            continue

        # Primera capa de deduplicación (la segunda está en
        # Database.registrar_parto, con la misma clave cuando hay cría:
        # (vaca_id, fecha, id_cria); sin cría ambas capas distinguen por
        # tipo_evento para no colapsar ABORTO vs REABSORCIÓN el mismo día).
        if id_cria is not None:
            if fec is not None:
                existe = db.query_one(
                    "SELECT 1 FROM partos WHERE vaca_id = ? AND fecha = ? AND id_cria = ? LIMIT 1",
                    (vaca_id, fec, id_cria),
                )
            else:
                existe = db.query_one(
                    "SELECT 1 FROM partos WHERE vaca_id = ? AND fecha IS NULL AND id_cria = ? LIMIT 1",
                    (vaca_id, id_cria),
                )
            if not existe and fec is not None:
                # Una vaca no puede parir dos veces el mismo día: si ya hay un
                # parto de esa vaca en esa fecha sin cría vinculada (ej. se
                # anotó en el bot antes de ponerle la chapeta definitiva), es
                # el mismo evento -- se completa con la cría en vez de crear
                # un parto nuevo. Si hay más de un huérfano ese día (ambiguo,
                # p. ej. mellizos sin cría todavía) no se arriesga a adivinar.
                huerfanos = db.query(
                    "SELECT id FROM partos WHERE vaca_id = ? AND fecha = ? AND id_cria IS NULL",
                    (vaca_id, fec),
                )
                if len(huerfanos) == 1:
                    parto_id = huerfanos[0]["id"]
                    db.execute(
                        "UPDATE animales SET madre_id = COALESCE(madre_id, ?) WHERE id_animal = ?",
                        (vaca_id, id_cria),
                    )
                    db.execute(
                        """
                        UPDATE partos SET id_cria = ?,
                            sexo_cria = COALESCE(sexo_cria, ?),
                            peso_nacimiento = COALESCE(peso_nacimiento, ?)
                        WHERE id = ?
                        """,
                        (id_cria, sexo_cria, peso, parto_id),
                    )
                    duplicados += 1
                    continue
        else:
            if fec is not None:
                existe = db.query_one(
                    "SELECT 1 FROM partos WHERE vaca_id = ? AND fecha = ? AND id_cria IS NULL LIMIT 1",
                    (vaca_id, fec),
                )
            else:
                existe = db.query_one(
                    "SELECT 1 FROM partos WHERE vaca_id = ? AND fecha IS NULL AND id_cria IS NULL LIMIT 1",
                    (vaca_id,),
                )

        if existe:
            duplicados += 1
            continue

        res = db.registrar_parto(
            vaca_tag=vaca, fecha=r.get("FECHA"), sexo_cria=sexo_cria,
            estado_cria=estado, peso_nacimiento=peso,
            id_cria_tag=id_cria_tag,
            notas=detalle or None,
            tipo_evento=tipo_evento,
        )
        # TODO: registrar_parto retorna None ante rechazo por autorreferencia
        # (vaca == cría), que no es un duplicado real; hoy se cuenta como
        # duplicado para no cambiar la forma del dict {"nuevos", "duplicados"}
        # que los tests y llamadores comparan por igualdad exacta.
        if res:
            nuevos += 1
        else:
            duplicados += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


def import_celos(db: Database, records) -> dict:
    """Siembra celos deduplicando por vaca_id + fecha."""
    nuevos = 0
    duplicados = 0
    for r in records:
        vaca = (r.get("CODANI") or "").strip()
        if not vaca:
            continue
        vaca_id = db.resolve_animal(vaca, crear=True, sexo="Hembra")
        fec = iso(r.get("FECHA"))
        if fec is not None:
            existe = db.query_one(
                "SELECT 1 FROM celos WHERE vaca_id = ? AND fecha = ? LIMIT 1",
                (vaca_id, fec),
            )
        else:
            existe = db.query_one(
                "SELECT 1 FROM celos WHERE vaca_id = ? AND fecha IS NULL LIMIT 1",
                (vaca_id,),
            )

        if existe:
            duplicados += 1
            continue

        hora = r.get("HORA")
        am_pm = _am_pm(hora)
        db.registrar_celo(
            vaca_tag=vaca, fecha=r.get("FECHA"), am_pm=am_pm,
            notas=(r.get("DETALLE") or "").strip() or None,
        )
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


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


def import_servicios(db: Database, records) -> dict:
    """Siembra servicios e inseminaciones deduplicando por vaca_id + fecha + tipo_servicio."""
    nuevos = 0
    duplicados = 0
    for r in records:
        vaca = (r.get("CODANI") or "").strip()
        if not vaca:
            continue
        tipo = (r.get("TIPO") or "").strip().upper()
        tipo_servicio = "MONTA" if tipo == "MN" else "IA"
        fecha = r.get("FECHA")
        fec = iso(fecha)
        vaca_id = db.resolve_animal(vaca, crear=True, sexo="Hembra")

        if fec is not None:
            existe = db.query_one(
                "SELECT 1 FROM servicios WHERE vaca_id = ? AND fecha = ? AND tipo_servicio = ? LIMIT 1",
                (vaca_id, fec, tipo_servicio),
            )
        else:
            existe = db.query_one(
                "SELECT 1 FROM servicios WHERE vaca_id = ? AND fecha IS NULL AND tipo_servicio = ? LIMIT 1",
                (vaca_id, tipo_servicio),
            )

        if existe:
            duplicados += 1
            continue

        fep = fecha_estimada_parto(fecha)
        db.registrar_servicio(
            vaca_tag=vaca, fecha=fecha, tipo_servicio=tipo_servicio,
            toro_pajilla=(r.get("TORO") or "").strip() or None,
            raza_toro=None,
            inseminador=(r.get("INSEMINA") or "").strip() or None,
            fep_calculada=fep,
            estado=(r.get("EST") or "").strip() or None,
        )
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


def import_pesajes(db: Database, records) -> dict:
    """Siembra pesajes con GMD deduplicando por animal_id + fecha + peso_kg."""
    nuevos = 0
    duplicados = 0
    ultimo: dict[int, tuple[Optional[str], float]] = {}
    for r in records:
        tag = (r.get("CODANI") or "").strip()
        peso = r.get("PESO")
        if not tag or peso is None:
            continue
        fecha = r.get("FECHA")
        fec = iso(fecha)
        peso_float = float(peso)
        aid = _get_or_create_animal(db, tag)
        if aid is None:
            continue

        if fec is not None:
            existe = db.query_one(
                "SELECT 1 FROM pesajes WHERE animal_id = ? AND fecha = ? AND peso_kg = ? LIMIT 1",
                (aid, fec, peso_float),
            )
        else:
            existe = db.query_one(
                "SELECT 1 FROM pesajes WHERE animal_id = ? AND fecha IS NULL AND peso_kg = ? LIMIT 1",
                (aid, peso_float),
            )

        gmd_calc = None
        if aid in ultimo:
            f_ant, p_ant = ultimo[aid]
            d1, d2 = to_date(f_ant), to_date(fecha)
            if d1 and d2 and (d2 - d1).days > 0:
                gmd_calc = gmd(peso_float, p_ant, (d2 - d1).days)
        ultimo[aid] = (fecha, peso_float)

        if existe:
            duplicados += 1
            continue

        db.registrar_pesaje(
            animal_tag=tag, fecha=fecha, peso_kg=peso_float,
            gmd_calculada=gmd_calc,
            evento=(r.get("EVENTO") or "").strip() or None,
        )
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


def import_tactos(db: Database, records) -> dict:
    """Siembra diagnósticos de gestación (tactos/palpaciones) deduplicando
    por vaca_id + fecha + resultado. Campo ESTADO de SG: 'P' preñada,
    'N' vacía/negativa, 'R' repite (vuelve a servicio) -- ambas últimas se
    tratan como vacía para el módulo de reproducción. PRENEZ es la fecha
    estimada de concepción cuando ESTADO='P'; de ahí se calculan los días
    de gestación al momento del tacto."""
    nuevos = 0
    duplicados = 0
    for r in records:
        tag = (r.get("CODANI") or "").strip()
        if not tag:
            continue
        fec = iso(r.get("FECHA"))
        if fec is None:
            continue

        estado_raw = (r.get("ESTADO") or "").strip().upper()
        if estado_raw == "P":
            resultado = "PREÑADA"
        elif estado_raw in ("N", "R"):
            resultado = "VACIA"
        else:
            continue  # estado desconocido/vacío: no hay diagnóstico real que sembrar

        dias_gestacion = None
        if resultado == "PREÑADA":
            d_fecha = to_date(r.get("FECHA"))
            d_prenez = to_date(r.get("PRENEZ"))
            if d_fecha and d_prenez and (d_fecha - d_prenez).days > 0:
                dias_gestacion = (d_fecha - d_prenez).days

        aid = _get_or_create_animal(db, tag)
        if aid is None:
            continue

        existe = db.query_one(
            "SELECT 1 FROM diagnosticos_gestacion WHERE vaca_id = ? AND fecha = ? AND resultado = ? LIMIT 1",
            (aid, fec, resultado),
        )
        if existe:
            duplicados += 1
            continue

        db.registrar_diagnostico(
            vaca_tag=tag, fecha=r.get("FECHA"), resultado=resultado,
            dias_gestacion=dias_gestacion,
        )
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


def import_leche(db: Database, records) -> dict:
    """Siembra controles de producción de leche deduplicando por
    animal_id + fecha + litros. SG guarda el control en AM/PM (kg del
    ordeño de la mañana/tarde); litros del control = AM + PM."""
    nuevos = 0
    duplicados = 0
    for r in records:
        tag = (r.get("CODANI") or "").strip()
        if not tag:
            continue
        fec = iso(r.get("FECHA"))
        if fec is None:
            continue

        am = r.get("AM") or 0
        pm = r.get("PM") or 0
        try:
            litros = float(am) + float(pm)
        except (TypeError, ValueError):
            continue
        if litros <= 0:
            continue  # fila administrativa de SG sin muestra real ese día

        aid = _get_or_create_animal(db, tag)
        if aid is None:
            continue

        existe = db.query_one(
            "SELECT 1 FROM produccion_leche WHERE animal_id = ? AND fecha = ? AND litros = ? LIMIT 1",
            (aid, fec, litros),
        )
        if existe:
            duplicados += 1
            continue

        db.registrar_leche(animal_tag=tag, fecha=r.get("FECHA"), litros=litros)
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


def import_condcorp(db: Database, records) -> dict:
    """Siembra evaluaciones de condición corporal deduplicando por
    animal_id + fecha + valor."""
    nuevos = 0
    duplicados = 0
    for r in records:
        tag = (r.get("CODANI") or "").strip()
        if not tag:
            continue
        fec = iso(r.get("FECHA"))
        if not fec:
            continue
        val = r.get("CONDCORP")
        try:
            val_float = float(val) if val is not None else None
        except (ValueError, TypeError):
            val_float = None
        if val_float is None or val_float <= 0:
            continue

        aid = _get_or_create_animal(db, tag)
        if aid is None:
            continue

        existe = db.query_one(
            "SELECT 1 FROM condicion_corporal WHERE animal_id = ? AND fecha = ? AND valor = ? LIMIT 1",
            (aid, fec, val_float),
        )
        if existe:
            duplicados += 1
            continue

        db.registrar_condicion_corporal(animal_tag=tag, fecha=r.get("FECHA"), valor=val_float, notas="Histórico SG (condcorp.dbf)")
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


def import_semen(db: Database, records) -> dict:
    """Siembra inventario de pajuelas/toros desde semen.dbf."""
    nuevos = 0
    actualizados = 0
    for r in records:
        cod_ref = (r.get("REF") or "").strip()
        nombre_toro = (r.get("NOMSEM") or "").strip()
        if not cod_ref and not nombre_toro:
            continue
        codigo_final = cod_ref or nombre_toro
        cod_raza = (str(r.get("COD1") or "")).strip()
        saldo_raw = r.get("EXT") or 0
        try:
            cantidad = max(0, int(float(saldo_raw)))
        except (ValueError, TypeError):
            cantidad = 0
        try:
            costo = float(r.get("VALOR") or 0.0)
        except (ValueError, TypeError):
            costo = 0.0

        fecha_ingreso = iso(r.get("FECHA"))
        procedencia = (r.get("COMEN") or "").strip() or nombre_toro

        existente = db.query_one("SELECT 1 FROM pajuelas_inventario WHERE codigo_toro = ? LIMIT 1", (codigo_final,))
        db.registrar_pajuela_inventario(
            codigo_toro=codigo_final,
            raza=f"Raza {cod_raza}" if cod_raza else None,
            procedencia=procedencia,
            canastilla="SG-CANASTA",
            cantidad=cantidad,
            costo=costo,
            fecha_ingreso=fecha_ingreso,
        )
        if existente:
            actualizados += 1
        else:
            nuevos += 1
    return {"nuevos": nuevos, "actualizados": actualizados}



def import_traslados(db: Database, records) -> dict:
    """Siembra traslados deduplicando por animal_id + fecha (+ potrero_destino)."""
    nuevos = 0
    duplicados = 0
    for r in records:
        tag = (r.get("CODANI") or "").strip()
        if not tag:
            continue
        tipmov = (r.get("TIPMOV") or "").strip().upper()
        potrero = (r.get("CODPOT") or "").strip() or None
        origen = potrero if tipmov == "S" else None
        destino = potrero if tipmov == "I" else None

        aid = _get_or_create_animal(db, tag)
        if aid is None:
            continue

        destino_id = db.resolve_potrero(destino) if destino else None
        fec = iso(r.get("FECHA"))

        if destino_id is not None:
            if fec is not None:
                existe = db.query_one(
                    "SELECT 1 FROM traslados WHERE animal_id = ? AND fecha = ? AND potrero_destino = ? LIMIT 1",
                    (aid, fec, destino_id),
                )
            else:
                existe = db.query_one(
                    "SELECT 1 FROM traslados WHERE animal_id = ? AND fecha IS NULL AND potrero_destino = ? LIMIT 1",
                    (aid, destino_id),
                )
        else:
            if fec is not None:
                existe = db.query_one(
                    "SELECT 1 FROM traslados WHERE animal_id = ? AND fecha = ? LIMIT 1",
                    (aid, fec),
                )
            else:
                existe = db.query_one(
                    "SELECT 1 FROM traslados WHERE animal_id = ? AND fecha IS NULL LIMIT 1",
                    (aid,),
                )

        if existe:
            duplicados += 1
            continue

        db.registrar_traslado(
            animal_tag=tag, fecha=r.get("FECHA"),
            lote=(r.get("LOTE") or "").strip() or None,
            potrero_origen=origen, potrero_destino=destino,
            motivo=(r.get("REGISTROTR") or "").strip() or None,
        )
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


def import_destetes(db: Database, records) -> dict:
    """Siembra secados/destetos deduplicando por cría_id + fecha.

    A diferencia de partos.dbf (donde CODANI es la vaca y HIJO es la cría
    aparte), destete.dbf de SG -- pantalla "Secados/Destetos" -- registra
    el evento sobre la VACA: CODANI es la madre que se seca, y no trae
    ningún campo de arete de cría. La tabla `destetes` de este bot está
    indexada por la cría (igual que la pantalla de Captura de la PWA), así
    que acá se resuelve la cría activa sin destetar de esa vaca con
    `cria_activa_de_madre()`. Si SG trae un secado de una vaca cuya cría no
    se puede resolver (ej. el parto correspondiente no se importó, o la
    cría ya fue vendida/no quedó activa), el registro se cuenta como
    "sin_cria" en vez de perderse en silencio, para poder revisarlo a mano.
    """
    nuevos = 0
    duplicados = 0
    sin_cria = 0
    for r in records:
        vaca = (r.get("CODANI") or "").strip()
        if not vaca:
            continue
        vaca_id = db.animal_id(vaca)
        if vaca_id is None:
            continue

        # El chequeo de duplicado va ANTES de resolver la cría activa: una
        # vez que el destete ya quedó registrado, esa cría deja de estar
        # "activa sin destetar" (por diseño de cria_activa_de_madre) -- si
        # se resolviera primero, reimportar el mismo backup nunca
        # encontraría la cría de nuevo y el secado se contaría como
        # "sin_cria" en vez de como duplicado.
        fec = iso(r.get("FECHA"))
        if fec is not None:
            existe = db.query_one(
                "SELECT 1 FROM destetes WHERE madre_id = ? AND fecha = ? LIMIT 1",
                (vaca_id, fec),
            )
        else:
            existe = db.query_one(
                "SELECT 1 FROM destetes WHERE madre_id = ? AND fecha IS NULL LIMIT 1",
                (vaca_id,),
            )
        if existe:
            duplicados += 1
            continue

        cria = db.cria_activa_de_madre(vaca)
        if not cria:
            sin_cria += 1
            continue

        motivo = (r.get("MOTIVO") or "").strip()
        detalle = (r.get("DETALLE") or "").strip()
        notas = " -- ".join(p for p in (motivo, detalle) if p) or None

        db.registrar_destete(
            cria_tag=cria["tag"], fecha=r.get("FECHA"),
            potrero_madre=(r.get("CODPOT") or "").strip() or None,
            notas=notas,
        )
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados, "sin_cria": sin_cria}


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def import_fotos(
    db: Database,
    fotos_source: bytes | dict[str, bytes] | zipfile.ZipFile,
    media_dir: str = "media",
) -> dict:
    """Extrae imágenes de Fotos.Zip a media_dir y registra fotos en SQLite de forma idempotente."""
    os.makedirs(media_dir, exist_ok=True)
    nuevos = 0
    duplicados = 0
    errores = 0

    fotos_map: dict[str, bytes] = {}
    if isinstance(fotos_source, bytes):
        try:
            with zipfile.ZipFile(io.BytesIO(fotos_source)) as zf:
                # Seguridad (H-12): rechazar Zip Slip / zip-bomb antes de leer nada.
                _validar_zip_seguro(zf)
                for name in zf.namelist():
                    if not name.endswith("/") and not os.path.basename(name).startswith("._"):
                        ext = os.path.splitext(name)[1].lower()
                        if ext in (".jpg", ".jpeg", ".png", ".bmp"):
                            fotos_map[os.path.basename(name)] = zf.read(name)
        except ValueError as e:  # _validar_zip_seguro: Zip Slip / zip-bomb
            logger.error("Fotos.Zip rechazado por validación de seguridad: %s", e)
            return {"nuevos": 0, "duplicados": 0, "errores": 0,
                    "error": f"Fotos.Zip inseguro (Zip Slip / zip-bomb): {e}"}
        except Exception as e:
            logger.error("No se pudo procesar Fotos.Zip (bytes corruptos o ZIP inválido): %s", e)
            return {"nuevos": 0, "duplicados": 0, "errores": 0,
                    "error": f"Fotos.Zip corrupto o no es un ZIP válido: {e}"}
    elif isinstance(fotos_source, zipfile.ZipFile):
        try:
            # Seguridad (H-12): validar el zip de fotos antes de iterar sus entradas.
            _validar_zip_seguro(fotos_source)
            for name in fotos_source.namelist():
                if not name.endswith("/") and not os.path.basename(name).startswith("._"):
                    ext = os.path.splitext(name)[1].lower()
                    if ext in (".jpg", ".jpeg", ".png", ".bmp"):
                        fotos_map[os.path.basename(name)] = fotos_source.read(name)
        except ValueError as e:  # _validar_zip_seguro: Zip Slip / zip-bomb
            logger.error("Fotos.Zip rechazado por validación de seguridad: %s", e)
            return {"nuevos": 0, "duplicados": 0, "errores": 0,
                    "error": f"Fotos.Zip inseguro (Zip Slip / zip-bomb): {e}"}
        except Exception as e:
            logger.error("No se pudo procesar Fotos.Zip (ZipFile inválido): %s", e)
            return {"nuevos": 0, "duplicados": 0, "errores": 0,
                    "error": f"Fotos.Zip corrupto o no es un ZIP válido: {e}"}
    elif isinstance(fotos_source, dict):
        fotos_map = fotos_source

    for fname, data in fotos_map.items():
        base_name = os.path.basename(fname).strip()
        if not base_name or base_name.startswith("."):
            continue
        ext = os.path.splitext(base_name)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".bmp"):
            continue

        tag = os.path.splitext(base_name)[0].strip()
        if not tag:
            continue

        dest_path = os.path.join(media_dir, base_name)
        dest_norm = dest_path.replace("\\", "/")

        # Guardar en disco si no existe o difiere en tamaño
        try:
            if not os.path.exists(dest_path) or os.path.getsize(dest_path) != len(data):
                with open(dest_path, "wb") as f:
                    f.write(data)
        except OSError as e:
            logger.error("No se pudo escribir foto '%s' en '%s': %s", base_name, dest_path, e)
            errores += 1
            continue
        except Exception as e:
            logger.error("No se pudo escribir foto '%s' en '%s': %s", base_name, dest_path, e)
            errores += 1
            continue

        # Idempotencia: comprobar si ya existe en tabla fotos (por ruta o por tag y sufijo/caption)
        existe = db.query_one(
            "SELECT 1 FROM fotos WHERE ruta = ? OR ruta = ? OR (tag = ? AND (ruta LIKE ? OR caption = 'Backup SG')) LIMIT 1",
            (dest_norm, dest_path, tag, f"%{base_name}"),
        )

        if existe:
            duplicados += 1
        else:
            db.registrar_foto(
                ruta=dest_norm,
                animal_tag=tag,
                caption="Backup SG",
                notas="Importado desde Fotos.Zip",
            )
            nuevos += 1

    resultado: dict = {"nuevos": nuevos, "duplicados": duplicados}
    if errores:
        resultado["errores"] = errores
        resultado["error"] = f"{errores} foto(s) no pudieron escribirse a disco"
    return resultado


def import_dbfs(
    db: Database,
    dbf_data: dict[str, bytes],
    fotos_data: Optional[bytes | dict[str, bytes]] = None,
    media_dir: str = "media",
) -> dict:
    """Siembra la base de datos a partir de un dict {nombre.dbf: bytes} y opcionalmente fotos."""
    lectores = {n: DBFReader(dbf_data[n]) for n in DBF_REQUERIDOS if n in dbf_data}
    conteos: dict = {}

    causas = import_causas(db, lectores["causas.dbf"].records()) if "causas.dbf" in lectores else {}
    cat_razas = dict(CATALOGO_RAZAS_SG_DEFECTO)
    if "raza.dbf" in lectores:
        for rz in lectores["raza.dbf"].records():
            c_rz = str(rz.get("CODRAZA") or "").strip()
            n_rz = str(rz.get("RAZA") or "").strip()
            if c_rz and n_rz:
                cat_razas[c_rz] = n_rz

    if "potrero.dbf" in lectores:
        conteos["potreros"] = import_potreros(db, lectores["potrero.dbf"].records())
    if "hoja.dbf" in lectores:
        conteos.update(import_animales(db, lectores["hoja.dbf"].records(), causas, catalogo_razas=cat_razas))
    if "partos.dbf" in lectores:
        conteos["partos"] = import_partos(db, lectores["partos.dbf"].records())
    if "celos.dbf" in lectores:
        conteos["celos"] = import_celos(db, lectores["celos.dbf"].records())
    if "iamn.dbf" in lectores:
        conteos["servicios"] = import_servicios(db, lectores["iamn.dbf"].records())
    if "pesos.dbf" in lectores:
        conteos["pesajes"] = import_pesajes(db, lectores["pesos.dbf"].records())
    if "tactos.dbf" in lectores:
        conteos["diagnosticos_gestacion"] = import_tactos(db, lectores["tactos.dbf"].records())
    if "leche.dbf" in lectores:
        conteos["produccion_leche"] = import_leche(db, lectores["leche.dbf"].records())
    if "traslado.dbf" in lectores:
        conteos["traslados"] = import_traslados(db, lectores["traslado.dbf"].records())
    if "destete.dbf" in lectores:
        conteos["destetes"] = import_destetes(db, lectores["destete.dbf"].records())
    if "condcorp.dbf" in lectores:
        conteos["condicion_corporal"] = import_condcorp(db, lectores["condcorp.dbf"].records())
    if "semen.dbf" in lectores:
        conteos["pajuelas_inventario"] = import_semen(db, lectores["semen.dbf"].records())

    # Fotos si vienen en fotos_data o en dbf_data ("Fotos.Zip" o "fotos.zip")
    fotos_source = fotos_data
    if fotos_source is None:
        for k in dbf_data:
            if k.lower() in ("fotos.zip", "foto.zip") or k.lower().endswith("fotos.zip"):
                fotos_source = dbf_data[k]
                break

    if fotos_source:
        conteos["fotos"] = import_fotos(db, fotos_source, media_dir=media_dir)

    if "hoja.dbf" in lectores or "partos.dbf" in lectores:
        # El backup pudo traer el mismo nacimiento bajo un tag ligeramente
        # distinto al ya existente (ej. "N065" vs "NO65"); el dedup de partos
        # es por id_cria ya resuelto, así que no lo detecta por sí solo.
        duplicados = db.detectar_duplicados_geneticos()
        if duplicados:
            conteos["duplicados_geneticos"] = duplicados

    return conteos


def import_zip(db: Database, zip_path: str, media_dir: str = "media") -> dict:
    """Lee ``Datos20260823.Zip`` (con ``Dbf.zip`` y opcionalmente ``Fotos.Zip`` internos) y siembra la DB."""
    fotos_raw = None
    with zipfile.ZipFile(zip_path) as outer:
        # Seguridad (H-12): validar el zip externo antes de leer cualquier entrada.
        _validar_zip_seguro(outer)
        names = outer.namelist()
        names_lower = {os.path.basename(n).lower(): n for n in names}

        if "dbf.zip" in names_lower:
            dbf_zip_name = names_lower["dbf.zip"]
            with zipfile.ZipFile(outer.open(dbf_zip_name)) as inner:
                # Seguridad (H-12): el zip interno (Dbf.zip) también se valida.
                _validar_zip_seguro(inner)
                inner_names_lower = {os.path.basename(n).lower(): n for n in inner.namelist()}
                dbf_data = {}
                for req in DBF_REQUERIDOS:
                    if req.lower() in inner_names_lower:
                        actual_name = inner_names_lower[req.lower()]
                        dbf_data[req] = inner.read(actual_name)
        else:
            dbf_data = {}
            for req in DBF_REQUERIDOS:
                if req.lower() in names_lower:
                    actual_name = names_lower[req.lower()]
                    dbf_data[req] = outer.read(actual_name)

        if "fotos.zip" in names_lower:
            fotos_zip_name = names_lower["fotos.zip"]
            fotos_raw = outer.read(fotos_zip_name)

    # Todo el import en una sola transacción SQLite: sin esto, cada uno de
    # los ~1500+ registros se commitea por separado (ver Database.execute)
    # y un lector concurrente (ej. el Tablero de la PWA) puede caer justo a
    # mitad del import y ver un conteo de animales genuinamente parcial.
    with db.transaccion():
        conteos = import_dbfs(db, dbf_data, fotos_data=fotos_raw, media_dir=media_dir)
    # Registro de auditoría (una sola vez aquí cubre tanto /confirmar_importar
    # como el vigilante automático copias_watcher, ya que los dos llaman a
    # import_zip): permite responder "¿está usando el backup de hoy?" sin
    # adivinar a partir de la fecha de modificación del archivo .db.
    try:
        db.registrar_import_sg(zip_path, conteos)
    except Exception:
        pass
    return conteos
