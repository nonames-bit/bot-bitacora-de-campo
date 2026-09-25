"""Script para sincronizar y normalizar los strings de raza en animales con fracciones zootécnicas."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.database import Database
from src.engine.genetic_engine import generar_resumen_zootecnico, normalizar_nombre_raza

def normalizar_razas_db(db_path: str = "data/bitacora.db"):
    db = Database(db_path)
    print(f"Normalizando razas en {db_path}...")
    
    # 1. Animales con composición multi-raza
    cur = db.query("""
        SELECT DISTINCT animal_id FROM composicion_racial
    """)
    animal_ids = [r["animal_id"] for r in cur]
    actualizados_comp = 0
    
    for aid in animal_ids:
        rows = db.query(
            "SELECT raza, porcentaje FROM composicion_racial WHERE animal_id = ? ORDER BY porcentaje DESC",
            (aid,)
        )
        if not rows:
            continue
            
        suma = sum(float(r["porcentaje"] or 0.0) for r in rows)
        factor = 100.0 / suma if suma > 0 else 1.0
        
        comp = []
        for r in rows:
            rz = normalizar_nombre_raza(r["raza"])
            pct = round(float(r["porcentaje"] or 0.0) * factor, 2)
            if pct > 0:
                comp.append({"raza": rz, "porcentaje": pct})
                
        if comp:
            resumen = generar_resumen_zootecnico(comp)
            db.execute("UPDATE animales SET raza = ? WHERE id_animal = ?", (resumen, aid))
            actualizados_comp += 1
            
    print(f"-> {actualizados_comp} animales actualizados con fracciones zootécnicas estandarizadas.")
    
    # 2. Animales con letras SG simples (T, C, I)
    db.execute("UPDATE animales SET raza = 'Taurino' WHERE TRIM(raza) = 'T'")
    db.execute("UPDATE animales SET raza = 'Cebuino' WHERE TRIM(raza) = 'C'")
    db.execute("UPDATE animales SET raza = 'Indeterminado' WHERE TRIM(raza) = 'I'")
    
    print("-> Códigos T/C/I normalizados a Taurino/Cebuino/Indeterminado.")
    
if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/bitacora.db"
    normalizar_razas_db(path)
