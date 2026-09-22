"""Herramienta de Auditoría y Comparación: Software Ganadero (SG) vs Bitácora JA.

Permite contrastar cualquier copia/backup de Software Ganadero (.Zip) con la base de datos
nativa de Bitácora JA (SQLite) para detectar discrepancias de inventario, diferencias de
ubicación en potreros y desgloses por categorías zootécnicas.

Uso:
    python scripts/comparar_backup_sg.py [ruta_zip] [--db ruta_sqlite] [--excel archivo.xlsx] [--json]

Ejemplo:
    python scripts/comparar_backup_sg.py docs/Datos20260823.Zip
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys
import zipfile
from typing import Any, Optional

# Asegurar path raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.database import Database
from src.importers.dbf_importer import DBFReader, _estado_desde_tipo, _validar_zip_seguro


def encontrar_backup_por_defecto() -> Optional[str]:
    """Busca el archivo de backup más reciente en docs/ o en carpetas locales."""
    candidatos = glob.glob("docs/Datos*.Zip") + glob.glob("docs/*.zip") + glob.glob(r"C:\Copias\*.Zip")
    if candidatos:
        # Ordenar por fecha de modificación más reciente
        candidatos.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidatos[0]
    return None


def clasificar_categoria(sexo: Optional[str], edad_meses: Optional[float], estado_prod: Optional[str] = None) -> str:
    """Clasificación zootécnica de referencia."""
    s = (sexo or "").strip().lower()
    es_macho = s in ("m", "macho")
    meses = edad_meses or 0.0

    if meses < 10:
        return "Terneros" if es_macho else "Terneras"
    elif meses < 24:
        return "Toretes/Levante" if es_macho else "Novillas Levante"
    elif es_macho:
        return "Toros"
    else:
        if estado_prod and "ordeñ" in estado_prod.lower():
            return "Vacas Ordeño"
        elif estado_prod and "seca" in estado_prod.lower():
            return "Vacas Secas"
        return "Vacas Adultas"


def comparar_sistemas(db: Database, zip_path: str) -> dict[str, Any]:
    """Ejecuta la comparación completa entre el backup SG y la BD SQLite."""
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"No se encontró el archivo ZIP: {zip_path}")

    # 1. Leer hoja.dbf desde el backup
    with zipfile.ZipFile(zip_path) as outer:
        _validar_zip_seguro(outer)
        names_lower = {os.path.basename(n).lower(): n for n in outer.namelist()}
        if "dbf.zip" in names_lower:
            with zipfile.ZipFile(outer.open(names_lower["dbf.zip"])) as inner:
                _validar_zip_seguro(inner)
                hoja_bytes = inner.read("hoja.dbf")
        else:
            hoja_bytes = outer.read(names_lower["hoja.dbf"])

    reader = DBFReader(hoja_bytes)
    sg_activos: dict[str, dict] = {}
    sg_todos: dict[str, dict] = {}

    for r in reader.records():
        tag = str(r.get("CODANI") or "").strip()
        if not tag:
            continue
        codpot = str(r.get("CODPOT") or "").strip() or None
        tipo = str(r.get("TIPO") or "").strip()
        est = _estado_desde_tipo(tipo, codpot=codpot)
        nombre = str(r.get("NOMANI") or "").strip()
        sexo = str(r.get("SEXO") or "").strip()
        raza = str(r.get("TIPORAZA") or "").strip()
        fecnace = r.get("FECNACE")

        sg_todos[tag] = {
            "tag": tag,
            "nombre": nombre,
            "estado": est,
            "tipo_sg": tipo,
            "codpot": codpot,
            "sexo": "Hembra" if sexo.upper() in ("H", "HEMBRA") else "Macho",
            "raza": raza,
            "fecha_nacimiento": fecnace,
        }
        if est == "ACTIVO":
            sg_activos[tag] = sg_todos[tag]

    # 2. Consultar animales activos en Bitácora JA (filtrando estrictamente por estado = 'ACTIVO')
    sql_db = """
        SELECT a.tag, a.nombre, a.sexo, a.raza, a.fecha_nacimiento, a.estado,
               p.codigo as potrero_codigo, p.nombre as potrero_nombre
        FROM animales a
        LEFT JOIN potreros p ON p.id = a.potrero_id
        WHERE a.estado = 'ACTIVO' AND a.tag IS NOT NULL
    """
    db_activos = {r["tag"]: dict(r) for r in db.query(sql_db)}

    # 3. Discrepancias de inventario
    tags_sg = set(sg_activos.keys())
    tags_db = set(db_activos.keys())

    solo_en_sg = sorted(list(tags_sg - tags_db))
    solo_en_db = sorted(list(tags_db - tags_sg))
    coincidentes = sorted(list(tags_sg & tags_db))

    detalles_solo_en_sg = []
    for tag in solo_en_sg:
        row = db.query_one("SELECT tag, nombre, estado FROM animales WHERE tag = ?", (tag,))
        estado_en_db = row["estado"] if row else "NO REGISTRADO EN BITÁCORA"
        detalles_solo_en_sg.append({
            "tag": tag,
            "nombre": sg_activos[tag]["nombre"],
            "estado_sg": "ACTIVO",
            "estado_en_bitacora": estado_en_db,
            "potrero_sg": sg_activos[tag]["codpot"],
        })

    detalles_solo_en_db = []
    for tag in solo_en_db:
        info_sg = sg_todos.get(tag)
        estado_en_sg = info_sg["estado"] if info_sg else "NO EXISTE EN SG"
        detalles_solo_en_db.append({
            "tag": tag,
            "nombre": db_activos[tag]["nombre"],
            "estado_en_bitacora": "ACTIVO",
            "estado_sg": estado_en_sg,
            "potrero_bitacora": db_activos[tag]["potrero_codigo"],
        })

    # 4. Discrepancias de potreros en animales activos coincidentes
    diferencias_potrero = []
    for tag in coincidentes:
        sg_pot = (sg_activos[tag]["codpot"] or "").strip().upper()
        db_pot = (db_activos[tag]["potrero_codigo"] or "").strip().upper()
        if sg_pot and db_pot and sg_pot != db_pot:
            diferencias_potrero.append({
                "tag": tag,
                "nombre": sg_activos[tag]["nombre"],
                "potrero_sg": sg_pot,
                "potrero_bitacora": db_pot,
                "nombre_potrero_bitacora": db_activos[tag]["potrero_nombre"],
            })

    # 5. Totales por sexo / tipo
    sg_hembras = sum(1 for a in sg_activos.values() if a["sexo"] == "Hembra")
    sg_machos = sum(1 for a in sg_activos.values() if a["sexo"] == "Macho")
    db_hembras = sum(1 for a in db_activos.values() if (a.get("sexo") or "").capitalize() == "Hembra")
    db_machos = sum(1 for a in db_activos.values() if (a.get("sexo") or "").capitalize() == "Macho")

    reporte = {
        "archivo_backup": os.path.basename(zip_path),
        "total_activos_sg": len(sg_activos),
        "total_activos_bitacora": len(db_activos),
        "activos_coincidentes": len(coincidentes),
        "desglose_sexo": {
            "sg": {"hembras": sg_hembras, "machos": sg_machos},
            "bitacora": {"hembras": db_hembras, "machos": db_machos},
        },
        "solo_en_sg": detalles_solo_en_sg,
        "solo_en_bitacora": detalles_solo_en_db,
        "diferencias_potrero": diferencias_potrero,
    }
    return reporte


def imprimir_reporte_consola(rep: dict[str, Any]) -> None:
    """Imprime el balance comparativo de manera elegante y legible en la terminal."""
    print("\n" + "=" * 70)
    print("      BALANCE COMPARATIVO: SOFTWARE GANADERO vs BITÁCORA JA")
    print("=" * 70)
    print(f"Archivo de Backup evaluado: {rep['archivo_backup']}")
    print("-" * 70)
    print(f"  TOTAL ANIMALES ACTIVOS EN SOFTWARE GANADERO : {rep['total_activos_sg']:>5}")
    print(f"  TOTAL ANIMALES ACTIVOS EN BITÁCORA JA (BD)   : {rep['total_activos_bitacora']:>5}")
    print(f"  ANIMALES COINCIDENTES EN AMBOS SISTEMAS      : {rep['activos_coincidentes']:>5}")
    print("-" * 70)
    print(f"  Desglose SG       -> Hembras: {rep['desglose_sexo']['sg']['hembras']:<4} | Machos: {rep['desglose_sexo']['sg']['machos']:<4}")
    print(f"  Desglose Bitácora -> Hembras: {rep['desglose_sexo']['bitacora']['hembras']:<4} | Machos: {rep['desglose_sexo']['bitacora']['machos']:<4}")
    print("=" * 70)

    # 1. Solo en SG
    solo_sg = rep["solo_en_sg"]
    print(f"\n[!] ANIMALES ACTIVOS EN SG PERO NO ACTIVOS EN BITÁCORA JA ({len(solo_sg)}):")
    if not solo_sg:
        print("    -> Ninguno. El inventario está perfectamente respaldado.")
    else:
        for it in solo_sg[:20]:
            nom = it['nombre'] or ''
            pot = it['potrero_sg'] or 'N/A'
            print(f"    - Tag: {it['tag']:<8} | Nombre: {nom:<15} | Potrero SG: {pot:<6} | Estado en Bitácora: {it['estado_en_bitacora']}")
        if len(solo_sg) > 20:
            print(f"    ... y {len(solo_sg) - 20} animales más.")

    # 2. Solo en Bitácora JA
    solo_db = rep["solo_en_bitacora"]
    print(f"\n[+] ANIMALES ACTIVOS EN BITÁCORA JA NO ACTIVOS EN SG ({len(solo_db)}):")
    if not solo_db:
        print("    -> Ninguno.")
    else:
        for it in solo_db[:20]:
            nom = it['nombre'] or ''
            pot = it['potrero_bitacora'] or 'N/A'
            print(f"    - Tag: {it['tag']:<8} | Nombre: {nom:<15} | Potrero: {pot:<6} | Estado en SG: {it['estado_sg']}")
        if len(solo_db) > 20:
            print(f"    ... y {len(solo_db) - 20} animales más.")

    # 3. Diferencias de potrero
    dif_pot = rep["diferencias_potrero"]
    print(f"\n[~] DISCREPANCIAS DE POTRERO EN ANIMALES ACTIVOS ({len(dif_pot)}):")
    if not dif_pot:
        print("    -> Todos los animales coincidentes tienen la misma ubicación.")
    else:
        for it in dif_pot[:15]:
            nom = it['nombre'] or ''
            print(f"    - Tag: {it['tag']:<8} ({nom:<12}) -> SG: {it['potrero_sg']:<6} vs Bitácora: {it['potrero_bitacora']:<6} ({it['nombre_potrero_bitacora'] or ''})")
        if len(dif_pot) > 15:
            print(f"    ... y {len(dif_pot) - 15} discrepancias más.")

    print("\n" + "=" * 70 + "\n")


def exportar_excel(rep: dict[str, Any], ruta_excel: str) -> None:
    """Exporta el reporte comparativo a un libro de Excel (.xlsx) estructurado."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        print("[!] Advertencia: openpyxl no está instalado. No se pudo generar el archivo Excel.")
        return

    wb = openpyxl.Workbook()

    # Hoja 1: Resumen
    ws_resumen = wb.active
    ws_resumen.title = "Resumen General"
    ws_resumen.append(["AUDITORÍA COMPARATIVA: SOFTWARE GANADERO vs BITÁCORA JA"])
    ws_resumen.append(["Archivo analizado:", rep["archivo_backup"]])
    ws_resumen.append([])
    ws_resumen.append(["Métrica", "Software Ganadero", "Bitácora JA", "Diferencia"])
    diff_total = rep["total_activos_bitacora"] - rep["total_activos_sg"]
    ws_resumen.append(["Total Animales Activos", rep["total_activos_sg"], rep["total_activos_bitacora"], diff_total])
    ws_resumen.append(["Hembras Activas", rep["desglose_sexo"]["sg"]["hembras"], rep["desglose_sexo"]["bitacora"]["hembras"], ""])
    ws_resumen.append(["Machos Activos", rep["desglose_sexo"]["sg"]["machos"], rep["desglose_sexo"]["bitacora"]["machos"], ""])
    ws_resumen.append(["Animales Coincidentes", rep["activos_coincidentes"], rep["activos_coincidentes"], 0])
    ws_resumen.append(["Discrepancias de Potrero", len(rep["diferencias_potrero"]), "", ""])

    # Hoja 2: Solo en SG
    ws_sg = wb.create_sheet(title="Solo en SG")
    ws_sg.append(["Tag", "Nombre", "Estado en SG", "Estado en Bitácora JA", "Potrero en SG"])
    for r in rep["solo_en_sg"]:
        ws_sg.append([r["tag"], r["nombre"], r["estado_sg"], r["estado_en_bitacora"], r["potrero_sg"]])

    # Hoja 3: Solo en Bitácora
    ws_db = wb.create_sheet(title="Solo en Bitácora")
    ws_db.append(["Tag", "Nombre", "Estado en Bitácora JA", "Estado en SG", "Potrero Bitácora"])
    for r in rep["solo_en_bitacora"]:
        ws_db.append([r["tag"], r["nombre"], r["estado_en_bitacora"], r["estado_sg"], r["potrero_bitacora"]])

    # Hoja 4: Diferencias de Potrero
    ws_pot = wb.create_sheet(title="Diferencias Potrero")
    ws_pot.append(["Tag", "Nombre", "Potrero en SG", "Potrero en Bitácora", "Nombre Potrero Bitácora"])
    for r in rep["diferencias_potrero"]:
        ws_pot.append([r["tag"], r["nombre"], r["potrero_sg"], r["potrero_bitacora"], r["nombre_potrero_bitacora"]])

    wb.save(ruta_excel)
    print(f"[OK] Reporte Excel generado exitosamente en: {ruta_excel}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara backup de Software Ganadero (.Zip) con la BD de Bitácora JA.")
    parser.add_argument("zip", nargs="?", help="Ruta al archivo .Zip exportado por Software Ganadero.")
    parser.add_argument("--db", default="data/bitacora.db", help="Ruta a la base de datos SQLite (def: data/bitacora.db).")
    parser.add_argument("--excel", help="Ruta para exportar el reporte en formato Excel (.xlsx).")
    parser.add_argument("--json", action="store_true", help="Imprime el resultado en formato JSON puro.")

    args = parser.parse_args()

    zip_file = args.zip or encontrar_backup_por_defecto()
    if not zip_file:
        print("[ERROR] No se especificó ningún archivo ZIP y no se encontró ninguno en docs/ o C:\\Copias\\.")
        sys.exit(1)

    db = Database(args.db)
    reporte = comparar_sistemas(db, zip_file)

    if args.json:
        print(json.dumps(reporte, indent=2, ensure_ascii=False))
    else:
        imprimir_reporte_consola(reporte)

    if args.excel:
        exportar_excel(reporte, args.excel)

    db.close()


if __name__ == "__main__":
    main()
