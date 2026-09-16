"""Inventario presente: solo potreros reales, conteos Inventario == Pasturas.

Asienta que `_por_potrero()` / `conteos_tablero()` listan únicamente
potreros con `geom_wkt_4326` (los legacy DBF nunca aparecen), cuentan solo
`estado='ACTIVO'` por potrero vigente (último traslado) y cuadran con
`datos_pasturas()`.
"""
from src.engine import dashboard_data as dd


def _mk_potrero(db, nombre, real=True):
    return db.registrar_potrero(
        nombre=nombre, codigo=nombre,
        geom_wkt_4326="POLYGON((0 0,1 0,1 1,0 0))" if real else None,
    )


def test_solo_reales_mas_sin_potrero(db):
    preal = _mk_potrero(db, "REAL-A", real=True)
    _mk_potrero(db, "LEGACY-01", real=False)
    db.registrar_animal("A1", sexo="Hembra", estado="ACTIVO", potrero=preal)
    db.registrar_animal("A2", sexo="Macho", estado="ACTIVO")  # sin potrero
    db.registrar_animal("A3", sexo="Hembra", estado="VENDIDO", potrero=preal)

    filas = dd._por_potrero(db)
    nombres = [f["potrero"] for f in filas]
    assert "REAL-A" in nombres
    assert not any("LEGACY" in n for n in nombres)
    assert "Sin potrero" in nombres
    assert sum(f["n"] for f in filas) == 2  # solo ACTIVOS

    tab = dd.conteos_tablero(db)
    tab_nombres = [f["potrero"] for f in tab["por_potrero"]]
    assert "REAL-A" in tab_nombres
    assert not any("LEGACY" in n for n in tab_nombres)
    assert "Sin potrero" in tab_nombres


def test_suma_cuadra_con_pasturas(db):
    p1 = _mk_potrero(db, "REAL-A", real=True)
    p2 = _mk_potrero(db, "REAL-B", real=True)
    _mk_potrero(db, "LEGACY-01", real=False)
    for i, p in enumerate([p1, p1, p2]):
        db.registrar_animal(f"B{i}", sexo="Hembra", estado="ACTIVO", potrero=p)
    db.registrar_animal("BS", sexo="Hembra", estado="ACTIVO")  # sin potrero
    db.registrar_animal("BX", sexo="Hembra", estado="MUERTO", potrero=p1)

    inv = dd._por_potrero(db)
    past = dd.datos_pasturas(db)
    suma_inv_ocup = sum(f["n"] for f in inv if f["potrero"] != "Sin potrero")
    suma_past = sum(p["total_animales"] for p in past["potreros"])
    assert suma_inv_ocup == suma_past == 3
    assert sum(f["n"] for f in inv) == 4  # no supera total de activos (4)
    assert past["sin_potrero"] == 1


def test_trasladado_cuenta_en_nuevo(db):
    viejo = _mk_potrero(db, "REAL-VIEJO", real=True)
    nuevo = _mk_potrero(db, "REAL-NUEVO", real=True)
    db.registrar_animal("T1", sexo="Hembra", estado="ACTIVO", potrero=viejo)
    db.registrar_traslado("T1", fecha="2026-09-01", potrero_origen=viejo, potrero_destino=nuevo)
    # Divergencia típica del import DBF: potrero_id estático quedó obsoleto;
    # el vigente (último traslado) debe mandar igual.
    db.execute("UPDATE animales SET potrero_id = ? WHERE tag = 'T1'", (viejo,))

    filas = {f["potrero"]: f["n"] for f in dd._por_potrero(db)}
    assert filas.get("REAL-NUEVO") == 1
    assert "REAL-VIEJO" not in filas
    assert db.animales_activos_en_potrero(nuevo) == ["T1"]
    assert db.animales_activos_en_potrero(viejo) == []


def test_legacy_nunca_aparece_ni_con_traslado(db):
    real = _mk_potrero(db, "REAL-A", real=True)
    leg = _mk_potrero(db, "LEGACY-99", real=False)
    db.registrar_animal("L1", sexo="Hembra", estado="ACTIVO", potrero=real)
    # Animal cuyo vigente es legacy: no crea fila legacy, cae a Sin potrero.
    db.registrar_animal("L2", sexo="Hembra", estado="ACTIVO", potrero=real)
    db.registrar_traslado("L2", fecha="2026-09-02", potrero_origen=real, potrero_destino=leg)

    inv = dd._por_potrero(db)
    nombres = [f["potrero"] for f in inv]
    assert not any("LEGACY" in n for n in nombres)
    assert {f["potrero"]: f["n"] for f in inv} == {"REAL-A": 1, "Sin potrero": 1}

    from src.engine.query.helpers import (
        calcular_existencias_potreros_sg,
        contar_animales_sin_potrero,
    )

    filas_sg = calcular_existencias_potreros_sg(db)
    assert all("LEGACY" not in f["display"] for f in filas_sg)
    assert sum(f["total"] for f in filas_sg) == 1
    assert contar_animales_sin_potrero(db) == 1
