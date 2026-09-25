"""Verificacion P2.12 en MODO PRODUCCION (sin BITACORA_TEST_MODE).

El gating cambia el comportamiento real: en produccion (sin el flag) la condicion
de potrero real es estricta (`geom_wkt_4326 IS NOT NULL`) y un potrero legacy sin
poligono NO cuenta como real. Este script arranca la app en modo produccion sobre
una COPIA de la DB real y comprueba que:
  1. `database._MODO_TEST` es False y `SQL_POTRERO_REAL` no incluye el fallback.
  2. `es_potrero_real` es False para un potrero legacy y True para uno con poligono.
  3. Las vistas principales responden 200 (no se rompen al endurecer la condicion).
"""
import os
import shutil
import sys
import tempfile

RAIZ = r"C:\Users\Owner\Documents\projects\finca\2026-08-24-bot-bitacora-de-campo"
sys.path.insert(0, RAIZ)

# Modo produccion: asegurar que el flag NO este seteado antes de importar.
os.environ.pop("BITACORA_TEST_MODE", None)

import src.db.database as dbmod  # noqa: E402
from src.pwa.app import crear_app  # noqa: E402

_db = os.path.join(tempfile.gettempdir(), "kilo", "p2_12_prod.db")
os.makedirs(os.path.dirname(_db), exist_ok=True)
shutil.copyfile(os.path.join(RAIZ, "data", "bitacora.db"), _db)

ok = True


def check(nombre, cond):
    global ok
    print(f"  [{'OK ' if cond else 'FALLO'}] {nombre}")
    ok = ok and bool(cond)


print("1. Modo produccion (sin flag):")
check("_MODO_TEST es False", dbmod._MODO_TEST is False)
check("SQL_POTRERO_REAL estricto (sin NOT EXISTS)", "NOT EXISTS" not in dbmod.SQL_POTRERO_REAL)
check("potreros_reales_where sin fallback", "NOT EXISTS" not in dbmod.potreros_reales_where())

print("2. es_potrero_real con la DB real:")
d = dbmod.Database(_db)
try:
    con_geo = d.query_one("SELECT * FROM potreros WHERE geom_wkt_4326 IS NOT NULL LIMIT 1")
    sin_geo = d.query_one("SELECT * FROM potreros WHERE geom_wkt_4326 IS NULL LIMIT 1")
    if con_geo is not None:
        check("potrero con poligono -> real", dbmod.es_potrero_real(d, con_geo) is True)
    else:
        print("  (aviso: la DB no tiene potreros con poligono)")
    if sin_geo is not None:
        check("potrero sin poligono -> NO real (estricto)", dbmod.es_potrero_real(d, sin_geo) is False)
    else:
        print("  (aviso: la DB no tiene potreros sin poligono)")
finally:
    d.close()

print("3. Vistas principales (modo produccion):")
app = crear_app(db_path=_db, users_file=os.path.join(RAIZ, "src", "server", "users.json"),
                password="test-master-password")
app.config.update({"TESTING": True, "SESSION_COOKIE_SECURE": False})
from flask import session  # noqa: E402


def auto():
    session["autenticado"] = True
    session["rol"] = "OWNER"
    session["nombre"] = "Jaime"
    session["user_id"] = 1


app.before_request_funcs.setdefault(None, []).insert(0, auto)
c = app.test_client()
for ruta in ["/", "/api/tablero", "/api/inventario", "/api/pasturas", "/api/mapa/datos", "/api/toros"]:
    r = c.get(ruta)
    check(f"GET {ruta} -> 200", r.status_code == 200)

print("P2.12 modo produccion: TODO OK" if ok else "P2.12 modo produccion: HAY FALLOS")
sys.exit(0 if ok else 1)
