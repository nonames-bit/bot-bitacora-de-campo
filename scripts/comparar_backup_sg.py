import zipfile
import io
import sys
import os

sys.path.insert(0, "/root/bitacora")
from src.importers.dbf_importer import DBFReader, _estado_desde_tipo
from src.db.database import Database

db = Database("/root/bitacora/data/bitacora.db")

zip_path = "/tmp/Datos20260913.Zip"
z = zipfile.ZipFile(zip_path)
zdbf = zipfile.ZipFile(io.BytesIO(z.read("Dbf.zip")))
reader = DBFReader(zdbf.read("hoja.dbf"))

sg_activos = {}
sg_todos = {}
for r in reader.records():
    tag = str(r.get("CODANI", "")).strip()
    if not tag:
        continue
    codpot = str(r.get("CODPOT", "")).strip() or None
    tipo = str(r.get("TIPO", "")).strip()
    activo_campo = str(r.get("ACTIVO", "")).strip().upper()
    est = _estado_desde_tipo(tipo, codpot=codpot)
    sg_todos[tag] = {
        "estado": est,
        "tipo": tipo,
        "codpot": codpot,
        "activo_flag": activo_campo,
        "nombre": str(r.get("NOMANI", "")).strip(),
    }
    if est == "ACTIVO":
        sg_activos[tag] = sg_todos[tag]

db_activos = {
    r["tag"]: dict(r)
    for r in db.query("SELECT tag, nombre, estado, potrero_id FROM animales WHERE estado='ACTIVO'")
}

print(f"Total activos en SG (hoja.dbf en {os.path.basename(zip_path)}): {len(sg_activos)}")
print(f"Total activos en BD Bitácora (SQLite): {len(db_activos)}")

solo_en_sg = set(sg_activos.keys()) - set(db_activos.keys())
solo_en_db = set(db_activos.keys()) - set(sg_activos.keys())

print(f"\nSolo en SG (activos en SG pero no en BD): {len(solo_en_sg)}")
for tag in sorted(solo_en_sg):
    row_db = db.query_one("SELECT tag, estado, potrero_id FROM animales WHERE tag=?", (tag,))
    db_info = dict(row_db) if row_db else "NO EXISTE"
    print(f"  Tag {tag}: en SG={sg_activos[tag]} | en BD={db_info}")

print(f"\nSolo en BD (activos en BD pero no en SG): {len(solo_en_db)}")
for tag in sorted(solo_en_db):
    print(f"  Tag {tag}: en BD={db_activos[tag]} | en SG={sg_todos.get(tag, 'NO EXISTE')}")

# Comparar potreros de animales activos coincidentes
coincidentes = set(sg_activos.keys()) & set(db_activos.keys())
diferencias_potrero = []
for tag in sorted(coincidentes):
    sg_codpot = sg_activos[tag]["codpot"]
    db_pot_id = db_activos[tag]["potrero_id"]
    pot_row = db.query_one("SELECT id, codigo, nombre FROM potreros WHERE id=?", (db_pot_id,)) if db_pot_id else None
    db_cod = pot_row["codigo"] if pot_row else None
    if sg_codpot and db_cod and sg_codpot != db_cod:
        diferencias_potrero.append((tag, sg_codpot, db_cod, pot_row["nombre"] if pot_row else ""))

print(f"\nDiferencias de potrero en animales activos: {len(diferencias_potrero)}")
for tag, sg_cod, db_cod, nom in diferencias_potrero[:15]:
    print(f"  Tag {tag}: SG={sg_cod} vs BD={db_cod} ({nom})")

db.close()
