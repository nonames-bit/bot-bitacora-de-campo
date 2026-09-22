"""Extractor e importador histórico de datos zootécnicos profundos de Software Ganadero (SG).

Importa de forma idempotente y de alto rendimiento:
- `leche.dbf`: Controles históricos individuales de producción de leche (6,910+ registros).
- `tactos.dbf`: Diagnósticos de gestación / palpaciones rectales históricas (716+ registros).
- `condcorp.dbf`: Evaluaciones de Condición Corporal (727+ registros).
- `semen.dbf`: Inventario de pajuelas, toros y saldos genéticos (101+ registros).
- `termos.dbf`: Información del termo de nitrógeno líquido.

Diseñado para emancipar a Ganadería JA de SG comercial, consolidando toda la historia
en la base SQLite nativa.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import zipfile
from datetime import date
from typing import Optional

from ..db.database import Database
from ..importers.dbf_importer import DBFReader, _validar_zip_seguro
from ..utils import iso, to_date

logger = logging.getLogger(__name__)

# Mapeo de códigos de raza comunes en SG si aplica
MAPA_RAZAS_SG = {
    "01": "CEBU",
    "02": "BRAHMAN",
    "03": "HOLSTEIN",
    "04": "PARDO SUIZO",
    "05": "GYR",
    "06": "GUZERAT",
    "07": "BON",
    "08": "SIMMENTAL",
    "09": "ANGUS",
    "10": "BRANGUS",
    "11": "JERSEY",
    "12": "GIROLANDO",
    "13": "NORMANDO",
}


def extraer_datos_historicos_sg(
    db: Database,
    zip_path: str,
) -> dict[str, dict[str, int]]:
    """Extrae e inserta todas las tablas históricas profundas desde un backup SG (.Zip).

    Utiliza conjuntos en memoria para deduplicación O(1), permitiendo procesar decenas
    de miles de registros en pocos segundos dentro de una única transacción.
    """
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"No se encontró el archivo de backup: {zip_path}")

    db.create_tables()

    dbfs_a_leer = ["leche.dbf", "tactos.dbf", "condcorp.dbf", "semen.dbf", "termos.dbf"]
    dbf_bytes: dict[str, bytes] = {}

    with zipfile.ZipFile(zip_path) as outer:
        _validar_zip_seguro(outer)
        names_lower = {os.path.basename(n).lower(): n for n in outer.namelist()}

        if "dbf.zip" in names_lower:
            with zipfile.ZipFile(outer.open(names_lower["dbf.zip"])) as inner:
                _validar_zip_seguro(inner)
                inner_names = {os.path.basename(n).lower(): n for n in inner.namelist()}
                for req in dbfs_a_leer:
                    if req in inner_names:
                        dbf_bytes[req] = inner.read(inner_names[req])
        else:
            for req in dbfs_a_leer:
                if req in names_lower:
                    dbf_bytes[req] = outer.read(names_lower[req])

    # Pre-cargar mapeo de animales en memoria: tag -> id_animal
    filas_animales = db.query("SELECT id_animal, UPPER(tag) as tag_u FROM animales WHERE tag IS NOT NULL")
    tag_to_id: dict[str, int] = {r["tag_u"]: r["id_animal"] for r in filas_animales}

    def _resolver_o_crear_aid(tag: str, sexo: Optional[str] = None) -> Optional[int]:
        tag_clean = tag.strip()
        if not tag_clean:
            return None
        tag_u = tag_clean.upper()
        if tag_u in tag_to_id:
            return tag_to_id[tag_u]
        aid = db.resolve_animal(tag_clean, crear=True, sexo=sexo)
        if aid:
            tag_to_id[tag_u] = aid
        return aid

    resultados: dict[str, dict[str, int]] = {}

    with db.transaccion():
        # ------------------------------------------------------------------
        # 1. CONDICIÓN CORPORAL (condcorp.dbf)
        # ------------------------------------------------------------------
        if "condcorp.dbf" in dbf_bytes:
            reader_cc = DBFReader(dbf_bytes["condcorp.dbf"])
            existentes_cc = {
                (r["animal_id"], r["fecha"], r["valor"])
                for r in db.query("SELECT animal_id, fecha, valor FROM condicion_corporal")
            }
            nuevos_cc = 0
            duplicados_cc = 0

            for rec in reader_cc.records():
                tag = (rec.get("CODANI") or "").strip()
                if not tag:
                    continue
                aid = _resolver_o_crear_aid(tag)
                if aid is None:
                    continue

                fec = iso(rec.get("FECHA"))
                val = rec.get("CONDCORP")
                try:
                    val_float = float(val) if val is not None else None
                except (ValueError, TypeError):
                    val_float = None

                if val_float is None or val_float <= 0:
                    continue

                clave = (aid, fec, val_float)
                if clave in existentes_cc:
                    duplicados_cc += 1
                    continue

                db.conn.execute(
                    "INSERT INTO condicion_corporal (animal_id, fecha, valor, notas) VALUES (?, ?, ?, ?)",
                    (aid, fec, val_float, "Histórico SG (condcorp.dbf)"),
                )
                existentes_cc.add(clave)
                nuevos_cc += 1

            resultados["condicion_corporal"] = {"nuevos": nuevos_cc, "duplicados": duplicados_cc}

        # ------------------------------------------------------------------
        # 2. PRODUCCIÓN DE LECHE (leche.dbf)
        # ------------------------------------------------------------------
        if "leche.dbf" in dbf_bytes:
            reader_leche = DBFReader(dbf_bytes["leche.dbf"])
            existentes_leche = {
                (r["animal_id"], r["fecha"], r["litros"])
                for r in db.query("SELECT animal_id, fecha, litros FROM produccion_leche")
            }
            nuevos_leche = 0
            duplicados_leche = 0

            for rec in reader_leche.records():
                tag = (rec.get("CODANI") or "").strip()
                if not tag:
                    continue
                aid = _resolver_o_crear_aid(tag, sexo="Hembra")
                if aid is None:
                    continue

                fec = iso(rec.get("FECHA"))
                if not fec:
                    continue

                # En SG: 'AM' y 'PM' o campo 'TOTAL' / 'MUESTRA'
                am = rec.get("AM") or 0.0
                pm = rec.get("PM") or 0.0
                try:
                    litros = float(am) + float(pm)
                except (ValueError, TypeError):
                    litros = 0.0

                if litros <= 0:
                    # Intentar muestra o total si AM/PM venían en 0
                    try:
                        litros = float(rec.get("MUESTRA") or rec.get("TOTAL") or 0.0)
                    except (ValueError, TypeError):
                        litros = 0.0

                if litros <= 0:
                    continue

                # Redondear a 2 decimales para consistencia
                litros = round(litros, 2)
                clave = (aid, fec, litros)
                if clave in existentes_leche:
                    duplicados_leche += 1
                    continue

                db.conn.execute(
                    "INSERT INTO produccion_leche (animal_id, fecha, litros, notas) VALUES (?, ?, ?, ?)",
                    (aid, fec, litros, "Histórico SG (leche.dbf)"),
                )
                existentes_leche.add(clave)
                nuevos_leche += 1

            resultados["produccion_leche"] = {"nuevos": nuevos_leche, "duplicados": duplicados_leche}

        # ------------------------------------------------------------------
        # 3. DIAGNÓSTICOS DE GESTACIÓN / TACTOS (tactos.dbf)
        # ------------------------------------------------------------------
        if "tactos.dbf" in dbf_bytes:
            reader_tactos = DBFReader(dbf_bytes["tactos.dbf"])
            existentes_tactos = {
                (r["vaca_id"], r["fecha"], r["resultado"])
                for r in db.query("SELECT vaca_id, fecha, resultado FROM diagnosticos_gestacion")
            }
            nuevos_tactos = 0
            duplicados_tactos = 0

            for rec in reader_tactos.records():
                tag = (rec.get("CODANI") or "").strip()
                if not tag:
                    continue
                aid = _resolver_o_crear_aid(tag, sexo="Hembra")
                if aid is None:
                    continue

                fec = iso(rec.get("FECHA"))
                if not fec:
                    continue

                estado_raw = (rec.get("ESTADO") or "").strip().upper()
                if estado_raw == "P":
                    resultado = "PREÑADA"
                elif estado_raw in ("N", "R"):
                    resultado = "VACIA"
                else:
                    continue

                dias_gestacion = None
                if resultado == "PREÑADA":
                    d_fecha = to_date(rec.get("FECHA"))
                    d_prenez = to_date(rec.get("PRENEZ"))
                    if d_fecha and d_prenez and (d_fecha - d_prenez).days > 0:
                        dias_gestacion = (d_fecha - d_prenez).days

                clave = (aid, fec, resultado)
                if clave in existentes_tactos:
                    duplicados_tactos += 1
                    continue

                palpador = (rec.get("PALPO") or "").strip() or "Histórico SG"
                db.conn.execute(
                    """
                    INSERT INTO diagnosticos_gestacion
                    (vaca_id, fecha, resultado, dias_gestacion, responsable, creado_en)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (aid, fec, resultado, dias_gestacion, palpador, db._ahora()),
                )
                existentes_tactos.add(clave)
                nuevos_tactos += 1

            resultados["diagnosticos_gestacion"] = {"nuevos": nuevos_tactos, "duplicados": duplicados_tactos}

        # ------------------------------------------------------------------
        # 4. PAJUELAS / SEMEN (semen.dbf)
        # ------------------------------------------------------------------
        if "semen.dbf" in dbf_bytes:
            reader_semen = DBFReader(dbf_bytes["semen.dbf"])
            nuevos_pajuelas = 0
            actualizados_pajuelas = 0

            for rec in reader_semen.records():
                cod_ref = (rec.get("REF") or "").strip()
                nombre_toro = (rec.get("NOMSEM") or "").strip()
                if not cod_ref and not nombre_toro:
                    continue

                codigo_final = cod_ref or nombre_toro
                cod_raza = (str(rec.get("COD1") or "")).strip()
                raza = MAPA_RAZAS_SG.get(cod_raza, f"Raza {cod_raza}" if cod_raza else None)

                # Saldo en SG es 'EXT'
                saldo_raw = rec.get("EXT") or 0
                try:
                    cantidad = int(float(saldo_raw))
                    if cantidad < 0:
                        cantidad = 0
                except (ValueError, TypeError):
                    cantidad = 0

                # Costo en SG es 'VALOR'
                valor_raw = rec.get("VALOR") or 0.0
                try:
                    costo = float(valor_raw)
                except (ValueError, TypeError):
                    costo = 0.0

                fecha_ingreso = iso(rec.get("FECHA"))
                procedencia = (rec.get("COMEN") or "").strip() or nombre_toro

                existente = db.query_one(
                    "SELECT id FROM pajuelas_inventario WHERE codigo_toro = ? LIMIT 1",
                    (codigo_final,),
                )
                if existente:
                    db.conn.execute(
                        """
                        UPDATE pajuelas_inventario
                        SET raza = COALESCE(?, raza),
                            procedencia = COALESCE(?, procedencia),
                            cantidad = ?,
                            costo = ?,
                            fecha_ingreso = COALESCE(?, fecha_ingreso)
                        WHERE id = ?
                        """,
                        (raza, procedencia, cantidad, costo, fecha_ingreso, existente["id"]),
                    )
                    actualizados_pajuelas += 1
                else:
                    db.conn.execute(
                        """
                        INSERT INTO pajuelas_inventario
                        (codigo_toro, raza, procedencia, canastilla, cantidad, costo, fecha_ingreso, creado_en)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (codigo_final, raza, procedencia, "SG-CANASTA", cantidad, costo, fecha_ingreso, db._ahora()),
                    )
                    nuevos_pajuelas += 1

            resultados["pajuelas_inventario"] = {"nuevos": nuevos_pajuelas, "actualizados": actualizados_pajuelas}

        # ------------------------------------------------------------------
        # 5. TERMOS DE NITRÓGENO (termos.dbf)
        # ------------------------------------------------------------------
        if "termos.dbf" in dbf_bytes:
            reader_termos = DBFReader(dbf_bytes["termos.dbf"])
            for rec in reader_termos.records():
                fechac = iso(rec.get("FECHAC")) or "2024-01-01"
                existe_t = db.query_one("SELECT id FROM termo_nitrogeno LIMIT 1")
                if not existe_t:
                    db.conn.execute(
                        "INSERT INTO termo_nitrogeno (fecha_recarga, proxima_recarga, dias_intervalo, creado_en) VALUES (?, ?, 21, ?)",
                        (fechac, fechac, db._ahora()),
                    )
                    resultados["termo_nitrogeno"] = {"nuevos": 1}

    logger.info("Extracción histórica de SG finalizada: %s", resultados)
    return resultados


if __name__ == "__main__":
    db_path = "data/bitacora.db"
    backup_zip = "docs/Datos20260823.Zip"
    if len(sys.argv) > 1:
        backup_zip = sys.argv[1]
    if len(sys.argv) > 2:
        db_path = sys.argv[2]

    print(f"Iniciando extracción histórica desde '{backup_zip}' hacia '{db_path}'...")
    db_inst = Database(db_path)
    res = extraer_datos_historicos_sg(db_inst, backup_zip)
    print("\n--- RESULTADO DE LA EXTRACCIÓN HISTÓRICA ---")
    for tabla, stats in res.items():
        print(f"  * {tabla:25}: {stats}")
    print("--------------------------------------------")
    print("Base de datos enriquecida con éxito.")
