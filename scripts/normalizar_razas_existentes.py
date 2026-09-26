"""Script de migración y normalización de razas en bitacora.db.

Unifica:
- 'Holstein Negro' -> 'Holstein'
- Variantes de Cebú ('CEBÚ COMERC', 'Cebú Rojo', 'Cebuino', etc.) -> 'Cebú Comercial'
- 'HOLSTEÍN R.' / 'Holstein R.' -> 'Holstein Rojo'
- Otras variantes ('GUZERAT' -> 'Guzerá', 'SHORTON' -> 'Shorthorn', etc.)

Actualiza:
1. Tabla composicion_racial (unificando porcentajes repetidos por animal).
2. Campo animales.raza (recalculado con generar_resumen_zootecnico).
"""
import os
import sys
import sqlite3

# Añadir raíz al sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.engine.genetic_engine import normalizar_nombre_raza, generar_resumen_zootecnico


def normalizar_razas_db(db_path: str = "data/bitacora.db"):
    if not os.path.exists(db_path):
        print(f"[WARN] Base de datos no encontrada en {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print(f"[INFO] Conectado a {db_path}...")

    # 1. Procesar composicion_racial agrupada por animal_id
    cur.execute("SELECT DISTINCT animal_id FROM composicion_racial")
    animal_ids = [r["animal_id"] for r in cur.fetchall()]
    print(f"[INFO] Encontrados {len(animal_ids)} animales con composición multi-raza...")

    actualizados_comp = 0
    for aid in animal_ids:
        cur.execute("SELECT id, raza, porcentaje FROM composicion_racial WHERE animal_id = ?", (aid,))
        filas = cur.fetchall()

        # Agrupar y sumar por raza normalizada
        raza_pct = {}
        hubo_cambio = False
        for f in filas:
            rz_orig = f["raza"] or ""
            rz_norm = normalizar_nombre_raza(rz_orig) or "Mestizo"
            if rz_norm != rz_orig:
                hubo_cambio = True
            pct = float(f["porcentaje"] or 0.0)
            raza_pct[rz_norm] = raza_pct.get(rz_norm, 0.0) + pct

        # Si hubo un cambio de nombre o fusión de filas duplicadas
        if hubo_cambio or len(raza_pct) < len(filas):
            actualizados_comp += 1
            # Borrar filas viejas del animal
            cur.execute("DELETE FROM composicion_racial WHERE animal_id = ?", (aid,))
            # Insertar filas unificadas
            limpias = []
            for rz, pct in sorted(raza_pct.items(), key=lambda x: x[1], reverse=True):
                cur.execute(
                    "INSERT INTO composicion_racial (animal_id, raza, porcentaje) VALUES (?, ?, ?)",
                    (aid, rz, round(pct, 2))
                )
                limpias.append({"raza": rz, "porcentaje": pct})

            # Actualizar string en animales
            if limpias:
                resumen = generar_resumen_zootecnico(limpias)
                cur.execute("UPDATE animales SET raza = ? WHERE id_animal = ?", (resumen, aid))

    # 2. Actualizar animales que no tienen composicion_racial pero sí tienen string en animales.raza
    cur.execute("""
        SELECT id_animal, raza FROM animales 
        WHERE raza IS NOT NULL AND id_animal NOT IN (SELECT DISTINCT animal_id FROM composicion_racial)
    """)
    filas_solas = cur.fetchall()
    print(f"[INFO] Revisando {len(filas_solas)} animales con raza de texto simple...")

    actualizados_solos = 0
    for a in filas_solas:
        aid = a["id_animal"]
        rz_orig = a["raza"] or ""
        # Reemplazar términos conocidos en strings
        rz_mod = rz_orig
        rz_mod = rz_mod.replace("Holstein Negro", "Holstein")
        rz_mod = rz_mod.replace("HOLSTEIN NEG", "Holstein")
        rz_mod = rz_mod.replace("Cebú Rojo Puro", "Cebú Comercial")
        rz_mod = rz_mod.replace("Cebú Comercial Puro", "Cebú Comercial")
        rz_mod = rz_mod.replace("Cebuino", "Cebú Comercial")
        rz_mod = rz_mod.replace("CEBÚ COMERC", "Cebú Comercial")
        rz_mod = rz_mod.replace("GUZERAT", "Guzerá")
        rz_mod = rz_mod.replace("SHORTON", "Shorthorn")

        if rz_mod != rz_orig:
            actualizados_solos += 1
            cur.execute("UPDATE animales SET raza = ? WHERE id_animal = ?", (rz_mod, aid))

    conn.commit()
    conn.close()
    print("[SUCCESS] Normalización completada:")
    print(f" - Animales con composición multi-raza unificada: {actualizados_comp}")
    print(f" - Animales con string simple actualizado: {actualizados_solos}")


if __name__ == "__main__":
    db_target = sys.argv[1] if len(sys.argv) > 1 else "data/bitacora.db"
    normalizar_razas_db(db_target)
