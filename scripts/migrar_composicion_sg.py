"""Migración de composición genética histórica desde Software Ganadero (SG).

Lee ``raza.dbf`` y ``hoja.dbf`` desde ``docs/Datos20260823.Zip`` (o el path provisto)
y siembra la tabla ``composicion_racial`` y actualiza ``animales.raza`` en SQLite.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import zipfile

from src.db.database import Database
from src.importers.dbf_importer import DBFReader

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

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


def migrar_composicion_desde_zip(db: Database, zip_path: str = "docs/Datos20260823.Zip"):
    if not os.path.exists(zip_path):
        logger.warning("No se encontró el archivo ZIP: %s", zip_path)
        return

    with zipfile.ZipFile(zip_path) as z:
        dbf_bytes = None
        if "Dbf.zip" in z.namelist():
            dbf_bytes = z.read("Dbf.zip")
        elif "dbf.zip" in z.namelist():
            dbf_bytes = z.read("dbf.zip")

    if not dbf_bytes:
        logger.warning("No se encontró Dbf.zip dentro de %s", zip_path)
        return

    catalogo_razas = dict(CATALOGO_RAZAS_SG_DEFECTO)

    with zipfile.ZipFile(io.BytesIO(dbf_bytes)) as z_dbf:
        # 1. Leer raza.dbf si existe
        nombres = {n.lower(): n for n in z_dbf.namelist()}
        if "raza.dbf" in nombres:
            reader_raza = DBFReader(z_dbf.read(nombres["raza.dbf"]))
            for r in reader_raza.records():
                cod = str(r.get("CODRAZA") or "").strip()
                nom = str(r.get("RAZA") or "").strip()
                if cod and nom:
                    catalogo_razas[cod] = nom

        if "hoja.dbf" not in nombres:
            logger.warning("No se encontró hoja.dbf en Dbf.zip")
            return

        reader_hoja = DBFReader(z_dbf.read(nombres["hoja.dbf"]))
        actualizados_comp = 0
        actualizados_tipo = 0

        for r in reader_hoja.records():
            tag = (r.get("CODANI") or "").strip()
            if not tag:
                continue

            aid = db.animal_id(tag)
            if not aid:
                continue

            # Extraer componentes raciales
            comp = []
            for i in range(1, 5):
                cod_g = str(r.get(f"CODGR{i}") or "").strip()
                por_g = r.get(f"PORGR{i}")
                if cod_g and por_g is not None:
                    try:
                        pct = float(por_g)
                    except (ValueError, TypeError):
                        pct = 0.0
                    if pct > 0.0:
                        nom_raza = catalogo_razas.get(cod_g) or f"Raza {cod_g}"
                        comp.append({"raza": nom_raza, "porcentaje": pct})

            if comp:
                # guardar_composicion_racial normaliza nombres, agrupa
                # variedades y actualiza animales.raza con el resumen; no se
                # vuelve a pisar con los componentes crudos del DBF.
                if db.guardar_composicion_racial(aid, comp):
                    actualizados_comp += 1
                else:
                    logger.warning("Composición SG inválida para %s (suma > 105%%): %s", tag, comp)
            else:
                tipo_raza = str(r.get("TIPORAZA") or "").strip().upper()
                if tipo_raza == "T":
                    # Solo reemplaza marcadores genéricos: una raza cebuina ya
                    # registrada ('Cebú Comercial', 'Tricross Cebú') no se
                    # relabela como Taurino.
                    db.execute("UPDATE animales SET raza = 'Taurino' WHERE id_animal = ? AND (raza IS NULL OR raza IN ('T', 'C', 'I'))", (aid,))
                    actualizados_tipo += 1
                elif tipo_raza == "C":
                    db.execute("UPDATE animales SET raza = 'Cebuino' WHERE id_animal = ? AND (raza IS NULL OR raza IN ('T', 'C', 'I'))", (aid,))
                    actualizados_tipo += 1
                elif tipo_raza == "I":
                    db.execute("UPDATE animales SET raza = 'Indeterminado' WHERE id_animal = ? AND (raza IS NULL OR raza IN ('T', 'C', 'I'))", (aid,))
                    actualizados_tipo += 1

        db.conn.commit()
        logger.info(
            "Migración SG completada: %d animales con composición multi-raza, %d actualizados con tipo general (Taurino/Cebuino/Indeterminado).",
            actualizados_comp, actualizados_tipo
        )


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/bitacora.db"
    zip_p = sys.argv[2] if len(sys.argv) > 2 else "docs/Datos20260823.Zip"
    db = Database(db_path)
    migrar_composicion_desde_zip(db, zip_p)
